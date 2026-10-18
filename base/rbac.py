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


def can_read_metadata(principal):
    """元数据（身份/审计/运维）可见性；IT 允许，机器不允许。"""
    return not _has_role(principal, "machine")


def validate_grant_actors(proposer, executor, approver):
    """grant 提案/执行/审批必须是三个不同主体，且各自具备对应能力。"""
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
    return True


def deny_all(principal, capability, case=None):
    """测试用坏实现：全拒。用于证明“有权样本必须通过”能抓出它。"""
    return False
