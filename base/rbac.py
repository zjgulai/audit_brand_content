#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/rbac.py — T0-07 切片 2：RBAC / 对象 ACL

边界：
- 只做授权判断；不查库、不发消息、不判 state。
- 角色：submitter / dp3 / dp4 / signer / coordinator / it / machine。
- 对象 ACL：提交人仅自己；DP3/DP4 tenant+product_line+assigned/actionable；
  签发人 scope+SoD；统筹 tenant 内全部；IT 仅元数据；机器仅既定 API。
- 多角色按**并集**判断：任一角色授予即可，不再由第一个匹配角色短路。
- 生产函数没有 bad_mode；反向对照由测试 monkeypatch 内部判据注入。

--------------------------------------------------------------------------
★ 三条「角色不够，还要再问一句」的守卫（2026-10-19 补齐，G-4 残差）
--------------------------------------------------------------------------

**一、下线权是「人级」的，不是「角色级」的**（`TAKEDOWN_ALLOWLIST`）

    角色只说明这个人**有资格**被授权；真正的授权是**被点名**。
    未被点名的人，即使角色完全匹配（signer / coordinator），也一律拒。
    名单为空 = 全拒（fail closed）——「没人被授权」比「谁都能下线」安全得多。

**二、元数据闸门**按对象**收敛，不是「元数据一律可读」（`can_read_metadata`）

    以前它只收一个 principal，于是任何拿到这个函数的人都能读走**任何**对象。
    现在必须带上对象：`identity` / `ops` 可读；`case_content` / `report` / `evidence`
    是**内容**，一律拒（要走 `can_read_content`）；**未知 kind 也拒**（fail closed）。

**三、授权不得越出操作者自身**（`validate_grant_actors(..., granted_scope=...)`）

    `admin.grant.execute/approve` 这两把钥匙能开的是「授予别人」，所以它们本身
    也必须被 scope 约束：一个 t1 的 IT 不能给某人开 t2 的权限。
    `granted_scope` 是**必填**关键字参数 —— 不给就没法调，不存在「忘了传于是跳过检查」。

残余（明着留）：
- `takedown.waive` 的“两名不同审批人”是流程层约束，本切片只判能力 + scope；
- `takedown.*` 的 platform scope 尚未建模（case/principal 只有 tenant/product_line）。
"""

ROLES = ("submitter", "dp3", "dp4", "signer",
         "coordinator", "it", "machine")

CAPABILITIES = (
    "case.review",
    "appeal.handle",
    "release.sign",
    "release.revoke",
    "takedown.execute",
    "takedown.waive",
    "admin.grant.execute",
    "admin.grant.approve",
)

_ROLE_CAPS = {
    "submitter": set(),
    "dp3": {"case.review", "appeal.handle"},
    "dp4": {"case.review", "appeal.handle"},
    # 签发人可执行下线；原 signer 也可作为 waive 的两名审批人之一（UIUX §1.5）。
    "signer": {"release.sign", "release.revoke",
               "takedown.execute", "takedown.waive"},
    # 统筹可参与 waive 审批；不能因此自动获得签发权。
    "coordinator": {"case.review", "appeal.handle",
                    "admin.grant.approve", "takedown.waive"},
    "it": {"admin.grant.execute"},
    "machine": set(),
}

# 测试注入点：默认 IT 不可读内容；反向对照把它置 True。
IT_CAN_READ_CONTENT = False

# ── 下线权的人级 allowlist ──────────────────────────────
# ★ 角色 ≠ 授权。signer / coordinator 只说明「有资格」，被点名才「有权限」。
#   这份名单由 admin.grant.* 流程维护（proposal → execute → approve），
#   本模块只做判定，不负责改写它。
#   空集合 = 全拒（fail closed）：宁可下线做不了、回头补人，也不许「谁都能下线」。
#
# ★ 按**能力**分两本，不是一本：`execute` 是「去把它下线」，
#   `waive` 是「宣布不用下线」。两者方向相反，共用一本等于
#   把「被派去干活的人」自动升级成「可以宣布不干的人」。
TAKEDOWN_ALLOWLIST = {
    "takedown.execute": frozenset(),
    "takedown.waive": frozenset(),
}

# 下线权的两个能力名，单独列出来是因为它们走人级名单，其余能力走角色矩阵。
TAKEDOWN_CAPS = frozenset({"takedown.execute", "takedown.waive"})

# ── 元数据对象的分类 ────────────────────────────────────
# ★ 「元数据」不是一个整体。IT 要能查「这个人是谁、系统跑得怎么样」，
#   但不能借此读到案件正文、报告、证据 —— 那是内容，得走 can_read_content。
#   分两类而不是「反正都是元数据」，是因为一旦合成一类，读内容的那条路就又开了。
METADATA_KINDS = frozenset({"identity", "ops"})
CONTENT_KINDS = frozenset({"case_content", "report", "evidence"})


def role_capabilities(role):
    return set(_ROLE_CAPS.get(role, set()))


def _roles_of(principal):
    return set(principal.get("roles") or [])


def _has_role(principal, role):
    return role in _roles_of(principal)


def _has_cap(principal, capability):
    return any(capability in role_capabilities(r) for r in _roles_of(principal))


def _scope_ok(principal, case):
    if principal.get("tenant") != case.get("tenant"):
        return False
    return case.get("product_line") in (principal.get("product_lines") or [])


def _assigned_or_actionable(principal, case):
    return (case.get("assignee_id") == principal.get("id")
            or bool(case.get("actionable")))


def _sod_ok(principal, case):
    return (principal.get("id") != case.get("submitter_id")
            and principal.get("id") != case.get("final_reviewer_id"))


def _takedown_allowed(principal, capability):
    """
    下线权的人级判定。**角色只给资格，被点名才给权限。**

    ★ 这里刻意不看角色：`can_act` 已经先过了角色矩阵，走到这里说明「有资格」。
      本条要回答的是另一件事 ——「这个人是不是被授权的那个」。
      两件事都成立才放行，任一不成立即拒。

    ★ 按能力分本查：`execute` 的名单不给 `waive` 作证。
    """
    pid = principal.get("id")
    if not isinstance(pid, str) or not pid:
        return False
    if capability not in TAKEDOWN_CAPS:
        return False
    return pid in (TAKEDOWN_ALLOWLIST.get(capability) or frozenset())


def can_act(principal, capability, case=None):
    """判断 principal 能否对 case 执行 capability。"""
    if capability not in CAPABILITIES:
        return False
    roles = _roles_of(principal)
    if not _has_cap(principal, capability):
        return False
    # 机器无人类能力（role_capabilities 为空，这里再显式挡一次）
    if "machine" in roles:
        return False
    # 仅 IT 角色时只做 admin.*；IT + 其他人类角色按角色并集判断。
    if roles == {"it"}:
        return capability.startswith("admin.")
    # ★ 下线权要在角色之外再过一道人级名单。放在 scope 判定**之前**，
    #   是因为「没被点名」与「scope 不匹配」是两回事，先答更根本的那个。
    if capability in TAKEDOWN_CAPS and not _takedown_allowed(principal, capability):
        return False
    # 无案件对象的全局能力（如 admin.grant.*）
    if case is None:
        return True
    if not _scope_ok(principal, case):
        return False
    if ("dp3" in roles or "dp4" in roles) and not _assigned_or_actionable(principal, case):
        return False
    if capability in ("release.sign", "release.revoke"):
        if not _sod_ok(principal, case):
            return False
    return True


def can_read_content(principal, case):
    """内容可见性；角色并集：任一角色授予即可；IT/机器默认不可读。"""
    roles = _roles_of(principal)
    if "machine" in roles:
        return False
    if roles == {"it"}:
        return IT_CAN_READ_CONTENT
    if "submitter" in roles and case.get("submitter_id") == principal.get("id"):
        return True
    if "coordinator" in roles and principal.get("tenant") == case.get("tenant"):
        return True
    if ("dp3" in roles or "dp4" in roles):
        if _scope_ok(principal, case) and _assigned_or_actionable(principal, case):
            return True
    if "signer" in roles and _scope_ok(principal, case):
        return True
    return False


def _metadata_kind_allowed(kind):
    """
    这个对象类型算不算「元数据」。**只回答分类，不回答谁看。**

    ★ 单独拆出来是为了它能被**替换成永真桩** ——
      反向对照要证明「这一行删掉，IT 就读得到案件内容」，
      而一个嵌在函数体里的 `kind in METADATA_KINDS` 没法从外面摘掉。
      （§2.4.7 的教训：判据盖不住的那一跳，就是事故所在的那一跳。）
    """
    if kind in CONTENT_KINDS:
        return False
    return kind in METADATA_KINDS


def can_read_metadata(principal, kind=None):
    """
    元数据可见性 —— **按对象收敛，不是「元数据一律可读」。**

    `kind` 必填，取值见 `METADATA_KINDS`（可读）与 `CONTENT_KINDS`（拒）。

    ★ 为什么参数从「一个 principal」改成「principal + 对象」：
      老签名只能回答「谁能读元数据」，回答不了「能读哪一份」。
      于是任何调用方拿到 True 之后，手上那把钥匙对**所有对象**都有效 ——
      而内容恰好也在同一批对象里。现在读内容必须走 `can_read_content`，
      那条路有逐案 ACL；这里一律拒。

    规则：
      · 机器角色：任何 kind 都拒（它只走既定 API，不读人看的元数据）
      · identity / ops：允许
      · case_content / report / evidence：拒（不是「元数据」，是内容）
      · 未知 kind：拒（fail closed —— 新对象类型不许默认放行）
    """
    if kind is None:
        # ★ 不给对象 = 问不出答案。这与 §2.4.1「否定结论的输入」同一个纪律：
        #   宁可抛，也不许默认放行。
        raise ValueError("can_read_metadata 必须指明对象 kind（identity/ops/...）")
    if _has_role(principal, "machine"):
        return False
    return _metadata_kind_allowed(kind)


def _scope_contains(outer, inner):
    """
    scope 包含判定：`inner` 是否完全落在 `outer` 之内。

    两边形状都是 `{"tenant": str, "product_lines": [str, ...]}`。
    ★ 空 product_lines 表示**一条品线都没有**，不是「全部品线」——
      把空当成通配是最常见的一种越权（`[] <= anything` 恒真）。
    """
    if not isinstance(outer, dict) or not isinstance(inner, dict):
        return False
    ot, it = outer.get("tenant"), inner.get("tenant")
    if not ot or not it or ot != it:
        return False
    opl = set(outer.get("product_lines") or [])
    ipl = set(inner.get("product_lines") or [])
    if not ipl:
        return False          # 授予空的品线集合 = 什么都没授予，不是「全部」
    return ipl <= opl


def validate_grant_actors(proposer, executor, approver, *, granted_scope):
    """
    grant 提案/执行/审批：三个不同主体 + 各自具备对应能力 + **不得越出自身 scope**。

    `granted_scope` —— 这次要授予的 scope，形如
    `{"tenant": "t1", "product_lines": ["pump"]}`。**必填**。

    ★ 为什么是必填关键字参数而不是可选：
      可选就会有人忘传，而忘传的默认行为只能是「跳过检查」——
      那就等于这条守卫不存在（§2.4：没有执行点的约束是注释）。
      必填则忘传直接 TypeError，不会静默放行。

    ★ 越界判定作用在**提案人与执行人两者**身上，不是只看一个人：
      执行人是他真正把权限写下去的那一刻，只审提案人等于审了一半。
      审批人是第三方制衡，他本身是 coordinator（租户内全部），
      让他也受同样的 scope 约束是多余的 —— 但也不放他越过自己的租户。
    """
    ids = [proposer.get("id"), executor.get("id"), approver.get("id")]
    if len(set(ids)) != 3:
        return False
    if not _has_role(proposer, "dp4"):
        return False
    if "admin.grant.execute" not in role_capabilities("it"):
        return False
    if not _has_role(executor, "it"):
        return False
    if "admin.grant.approve" not in set(
            cap for r in _roles_of(approver) for cap in role_capabilities(r)):
        return False

    # ★ 三项 scope 越界检查，缺一即拒。
    if not isinstance(granted_scope, dict):
        return False
    for who in (proposer, executor, approver):
        own = {"tenant": who.get("tenant"),
               "product_lines": list(who.get("product_lines") or [])}
        if not _scope_contains(own, granted_scope):
            return False
    return True


def deny_all(principal, capability, case=None):
    """测试用坏实现：全拒。用于证明“有权样本必须通过”能抓出它。"""
    return False
