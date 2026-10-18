#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_rbac.py — T0-07 切片 2：RBAC / 对象 ACL

覆盖：
  C0 角色与能力集合
  C1 提交人仅自己案件
  C2 DP3 tenant+product_line+assigned/actionable
  C3 DP4 同上
  C4 签发人 scope + SoD（非提交人、非最终复核人）
  C5 项目统筹 tenant 内全部
  C6 IT 仅元数据，不含内容
  C7 机器仅既定 API，无人类能力
  C8 grant 提案/执行/审批三方不同人
  C9 角色→能力矩阵（含 takedown.* 不得是死能力）
  C10 多角色并集：不得被第一个匹配角色短路
  C11 每个能力至少一个角色持有（死能力检测）
  C12 release.revoke 的 scope + SoD
  R1 去掉 scope → 跨租户被放行（测试注入）
  R2 去掉 SoD → 自签被放行（测试注入）
  R3 去掉 IT 内容限制 → IT 可读内容（测试注入）
  R4 “全拒”坏实现必须被“有权样本必须通过”抓出

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.rbac import (
        ROLES, CAPABILITIES, role_capabilities,
        can_act, can_read_content, can_read_metadata,
        validate_grant_actors, deny_all,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.rbac: %s" % exc)
    sys.exit(2)


def P(pid, roles, tenant="t1", product_lines=None):
    return {
        "id": pid,
        "roles": roles,
        "tenant": tenant,
        "product_lines": product_lines or ["pump"],
    }


def C(cid, submitter="u_sub", reviewer="u_dp3", assignee="u_dp3",
      tenant="t1", product_line="pump", actionable=True):
    return {
        "id": cid,
        "tenant": tenant,
        "product_line": product_line,
        "submitter_id": submitter,
        "final_reviewer_id": reviewer,
        "assignee_id": assignee,
        "actionable": actionable,
    }


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    p_sub = P("u_sub", ["submitter"])
    p_dp3 = P("u_dp3", ["dp3"])
    p_dp4 = P("u_dp4", ["dp4"])
    p_signer = P("u_signer", ["signer"])
    p_coord = P("u_coord", ["coordinator"])
    p_it = P("u_it", ["it"])
    p_machine = P("u_machine", ["machine"])

    case_own = C("case-own", submitter="u_sub", reviewer="u_dp3", assignee="u_dp3")
    case_other = C("case-other", submitter="u_other", reviewer="u_dp3", assignee="u_dp3")
    case_other_tenant = C("case-t2", assignee="u_dp3", tenant="t2")
    case_other_pl = C("case-pl", assignee="u_dp3", product_line="other")
    case_unassigned = C("case-unassigned", assignee=None, actionable=False)
    case_self_review = C("case-self-review", submitter="u_other",
                         reviewer="u_signer", assignee="u_dp3")
    case_signer_submitted = C("case-signed-sub", submitter="u_signer",
                              reviewer="u_dp3", assignee="u_dp3")

    # C0
    report(set(ROLES) == {"submitter", "dp3", "dp4", "signer",
                          "coordinator", "it", "machine"},
           "C0 角色集合", "roles=%r" % (ROLES,))
    report(set(CAPABILITIES) == {"case.review", "appeal.handle",
                                 "release.sign", "release.revoke",
                                 "takedown.execute", "takedown.waive",
                                 "admin.grant.execute", "admin.grant.approve"},
           "C0 能力集合", "caps=%r" % (CAPABILITIES,))

    # C1
    report(can_read_content(p_sub, case_own) is True, "C1 提交人读自己案件", "")
    report(can_read_content(p_sub, case_other) is False, "C1 提交人读他人案件 → 拒", "")

    # C2
    report(can_read_content(p_dp3, case_other) is True, "C2 DP3 同 scope+assigned 可读", "")
    report(can_read_content(p_dp3, case_other_tenant) is False, "C2 DP3 跨租户 → 拒", "")
    report(can_read_content(p_dp3, case_other_pl) is False, "C2 DP3 跨品线 → 拒", "")
    report(can_read_content(p_dp3, case_unassigned) is False, "C2 DP3 未指派/非 actionable → 拒", "")
    report(can_act(p_dp3, "case.review", case_other) is True, "C2 DP3 case.review 允许", "")

    # C3
    report(can_read_content(p_dp4, case_other) is True, "C3 DP4 同 scope+assigned 可读", "")
    report(can_read_content(p_dp4, case_other_tenant) is False, "C3 DP4 跨租户 → 拒", "")
    report(can_act(p_dp4, "appeal.handle", case_other) is True, "C3 DP4 appeal.handle 允许", "")

    # C4
    report(can_act(p_signer, "release.sign", case_other) is True,
           "C4 签发人非提交人/非复核人可签", "")
    report(can_act(p_signer, "release.sign", case_signer_submitted) is False,
           "C4 签自己提交的案件 → 拒", "")
    report(can_act(p_signer, "release.sign", case_self_review) is False,
           "C4 签自己复核的案件 → 拒", "")
    report(can_act(p_signer, "release.sign", case_other_tenant) is False,
           "C4 签发人跨租户 → 拒", "")

    # C5
    report(can_read_content(p_coord, case_other) is True, "C5 统筹租户内可读", "")
    report(can_read_content(p_coord, case_other_tenant) is False, "C5 统筹跨租户 → 拒", "")

    # C6
    # C6 元数据按对象收敛：IT 读身份/运维元数据可以，读内容一律拒
    report(can_read_metadata(p_it, "identity") is True, "C6 IT 读身份元数据 → 允许", "")
    report(can_read_metadata(p_it, "ops") is True, "C6 IT 读运维元数据 → 允许", "")
    report(can_read_metadata(p_it, "case_content") is False, "C6 IT 读案件内容 → 拒", "")
    report(can_read_metadata(p_it, "report") is False, "C6 IT 读报告 → 拒", "")
    report(can_read_metadata(p_it, "evidence") is False, "C6 IT 读证据 → 拒", "")
    report(can_read_metadata(p_it, "some_new_kind") is False,
           "C6 未知对象类型 → 拒（fail closed）", "")

    # C6b 不给对象就没有答案
    try:
        can_read_metadata(p_it)
        report(False, "C6b 不传 kind → 必须抛（不许默认放行）", "居然返回了")
    except ValueError:
        report(True, "C6b 不传 kind → 必须抛（不许默认放行）", "ValueError")
    except Exception as exc:  # noqa: BLE001
        report(False, "C6b 不传 kind → 必须抛（不许默认放行）",
               "%s: %s" % (type(exc).__name__, exc))

    # C7
    report(can_read_content(p_machine, case_own) is False, "C7 机器读内容 → 拒", "")
    report(can_act(p_machine, "release.sign", case_other) is False,
           "C7 机器签发 → 拒", "")

    # C8 grant 三方不同人 + 授予范围不得越出自身
    scope_ok = {"tenant": "t1", "product_lines": ["pump"]}
    report(validate_grant_actors(p_dp4, p_it, p_coord, granted_scope=scope_ok) is True,
           "C8 grant 三方不同人 + 同 scope → 允许", "")
    report(validate_grant_actors(p_dp4, p_dp4, p_coord, granted_scope=scope_ok) is False,
           "C8 提案=执行 → 拒", "")
    report(validate_grant_actors(p_dp4, p_it, p_it, granted_scope=scope_ok) is False,
           "C8 执行=审批 → 拒", "")
    report(validate_grant_actors(p_dp4, p_it, p_dp3, granted_scope=scope_ok) is False,
           "C8 审批无 approve 能力 → 拒", "")

    # C8b ★ 授予范围越界 —— 三种越法各一条
    report(validate_grant_actors(
               p_dp4, p_it, p_coord,
               granted_scope={"tenant": "t2", "product_lines": ["pump"]}) is False,
           "C8b ★ 跨租户授予（t1 的人授 t2）→ 拒", "")
    report(validate_grant_actors(
               p_dp4, p_it, p_coord,
               granted_scope={"tenant": "t1", "product_lines": ["other"]}) is False,
           "C8b ★ 越品线授予（授一条自己没有的品线）→ 拒", "")
    report(validate_grant_actors(
               p_dp4, p_it, p_coord,
               granted_scope={"tenant": "t1", "product_lines": []}) is False,
           "C8b ★ 授予空品线集合 → 拒（空不是通配）", "")

    # ★ 三者的 scope **各自**都要够 —— 不是只看提案人
    p_dp4_narrow = P("u_dp4n", ["dp4"], product_lines=["other"])
    report(validate_grant_actors(p_dp4_narrow, p_it, p_coord,
                                 granted_scope=scope_ok) is False,
           "C8b ★ 提案人自己没有该品线 → 拒（不是只看执行人）", "")
    p_it_narrow = P("u_itn", ["it"], product_lines=["other"])
    report(validate_grant_actors(p_dp4, p_it_narrow, p_coord,
                                 granted_scope=scope_ok) is False,
           "C8b ★ 执行人自己没有该品线 → 拒", "")
    p_coord_narrow = P("u_coordn", ["coordinator"], product_lines=["other"])
    report(validate_grant_actors(p_dp4, p_it, p_coord_narrow,
                                 granted_scope=scope_ok) is False,
           "C8b ★ 审批人自己没有该品线 → 拒", "")

    # ★ 忘了传 scope = 不能调，不是「跳过检查」
    try:
        validate_grant_actors(p_dp4, p_it, p_coord)
        report(False, "C8c ★ 不传 granted_scope → 必须 TypeError（不许静默跳过）",
               "居然返回了")
    except TypeError:
        report(True, "C8c ★ 不传 granted_scope → 必须 TypeError（不许静默跳过）",
               "TypeError")
    except Exception as exc:  # noqa: BLE001
        report(False, "C8c ★ 不传 granted_scope → 必须 TypeError（不许静默跳过）",
               "%s: %s" % (type(exc).__name__, exc))

    # C9
    report({"case.review", "appeal.handle"} <= role_capabilities("dp3"),
           "C9 DP3 能力矩阵", "")
    report({"release.sign", "release.revoke"} <= role_capabilities("signer"),
           "C9 签发人能力矩阵", "")
    report("admin.grant.execute" in role_capabilities("it"),
           "C9 IT 能力矩阵", "")
    report("admin.grant.approve" in role_capabilities("coordinator"),
           "C9 统筹审批能力", "")
    report(role_capabilities("machine") == set(), "C9 机器无人类能力", "")
    report("takedown.execute" in role_capabilities("signer"),
           "C9 签发人下线执行能力", "")
    report("takedown.waive" in role_capabilities("signer")
           and "takedown.waive" in role_capabilities("coordinator"),
           "C9 下线豁免能力（signer/coordinator）", "")

    # C10 多角色并集：不得被第一个匹配角色短路
    p_multi = P("u_dp3", ["submitter", "dp3"])
    report(can_read_content(p_multi, case_other) is True,
           "C10 submitter+dp3：非提交人但 assigned 的 dp3 必须可读", "")
    p_multi_it_signer = P("u_isigner", ["it", "signer"])
    report(can_read_content(p_multi_it_signer, case_other) is True,
           "C10 it+signer：内容可见性按并集，不被 IT 短路", "")
    report(can_act(p_multi_it_signer, "release.sign", case_other) is True,
           "C10 it+signer：签发按并集，不被 IT 短路", "")

    # C11 每个能力至少一个角色持有（死能力检测）
    holders = {cap: [r for r in ROLES if cap in role_capabilities(r)]
               for cap in CAPABILITIES}
    dead = [cap for cap, rs in holders.items() if not rs]
    report(not dead, "C11 每个能力至少一个角色持有", "dead=%r" % (dead,))

    # C12 release.revoke：scope + SoD 与签发同口径
    report(can_act(p_signer, "release.revoke", case_other) is True,
           "C12 非提交人/非复核人可撤回", "")
    report(can_act(p_signer, "release.revoke", case_signer_submitted) is False,
           "C12 撤回自己提交的案件 → 拒", "")
    report(can_act(p_signer, "release.revoke", case_self_review) is False,
           "C12 撤回自己复核的案件 → 拒", "")
    report(can_act(p_signer, "release.revoke", case_other_tenant) is False,
           "C12 撤回跨租户案件 → 拒", "")

    # C13 下线权是**人级**的：角色只给资格，被点名才给权限
    #
    # ★ 默认名单是空的（fail closed）—— 先证明「空名单 = 全拒」，
    #   再点名两个人，证明「点名之后角色匹配的人才放行」。
    report(can_act(p_signer, "takedown.execute", case_other) is False,
           "C13 ★ 空 allowlist：签发人执行下线 → 拒（角色不等于授权）", "")
    report(can_act(p_coord, "takedown.waive", case_other) is False,
           "C13 ★ 空 allowlist：统筹参与豁免 → 拒", "")

    BOTH = {"takedown.execute": frozenset({"u_signer", "u_coord"}),
            "takedown.waive": frozenset({"u_signer", "u_coord"})}
    with mock.patch("base.rbac.TAKEDOWN_ALLOWLIST", BOTH):
        report(can_act(p_signer, "takedown.execute", case_other) is True,
               "C13 点名后签发人执行下线 → 允许", "")
        report(can_act(p_signer, "takedown.waive", case_other) is True,
               "C13 点名后签发人参与豁免审批 → 允许", "")
        report(can_act(p_coord, "takedown.waive", case_other) is True,
               "C13 点名后统筹参与豁免审批 → 允许", "")
        report(can_act(p_dp3, "takedown.execute", case_other) is False,
               "C13 DP3 无下线执行能力 → 拒", "")

        # ★ 反向：有角色但**没被点名**的人，即使角色完全匹配也拒
        p_signer2 = P("u_signer2", ["signer"])
        p_coord2 = P("u_coord2", ["coordinator"])
        report(can_act(p_signer2, "takedown.execute", case_other) is False,
               "C13 ★ 同角色未点名的人 → 拒（角色给资格，名单给许可）", "")
        report(can_act(p_coord2, "takedown.waive", case_other) is False,
               "C13 ★ 同角色未点名的统筹 → 拒", "")

        # ★ 反向：被点名但**跨租户**，scope 那道门仍然拦
        report(can_act(p_signer, "takedown.execute", case_other_tenant) is False,
               "C13 被点名但跨租户 → 拒（人级名单不替代 scope）", "")

        # ★ 反向：只被点了 execute，不许顺手拿到 waive
        #   两本名单按能力分开，正是为了这条：被派去下线的人
        #   不等于可以宣布「不用下线」的人。
        EXEC_ONLY = {"takedown.execute": frozenset({"u_signer"}),
                     "takedown.waive": frozenset()}
        with mock.patch("base.rbac.TAKEDOWN_ALLOWLIST", EXEC_ONLY):
            report(can_act(p_signer, "takedown.execute", case_other) is True,
                   "C13 ★ 只点 execute → 执行放行（正样本，证明桩没把路堵死）", "")
            report(can_act(p_signer, "takedown.waive", case_other) is False,
                   "C13 ★ 只点 execute → waive 仍拒（execute ≠ waive）", "")

        # ★ 无 id 的主体不许因为「id 是 None / 空」被当成通配
        p_noid = {"id": "", "roles": ["signer"], "tenant": "t1",
                  "product_lines": ["pump"]}
        report(can_act(p_noid, "takedown.execute", case_other) is False,
               "C13 ★ 无 id 主体 → 拒（不是通配）", "")

    # R1: 测试注入去掉 scope -> 跨租户被放行
    with mock.patch("base.rbac._scope_ok", lambda principal, case: True):
        report(can_act(p_dp3, "case.review", case_other_tenant) is True,
               "R1 去掉 scope → 跨租户被放行（反向对照成立）", "")

    # R2: 测试注入去掉 SoD -> 自签被放行
    with mock.patch("base.rbac._sod_ok", lambda principal, case: True):
        report(can_act(p_signer, "release.sign", case_signer_submitted) is True,
               "R2 去掉 SoD → 自签被放行（反向对照成立）", "")

    # R3: 测试注入去掉 IT 内容限制 -> IT 可读内容
    with mock.patch("base.rbac.IT_CAN_READ_CONTENT", True):
        report(can_read_content(p_it, case_own) is True,
               "R3 去掉 IT 内容限制 → IT 可读内容（反向对照成立）", "")

    # R4: 全拒坏实现必须被“有权样本必须通过”抓出
    authorized_ok = can_act(p_dp3, "case.review", case_other) is True
    deny_all_ok = deny_all(p_dp3, "case.review", case_other) is True
    report(authorized_ok and not deny_all_ok,
           "R4 全拒坏实现被有权样本抓出", "authorized=%r deny_all=%r" % (authorized_ok, deny_all_ok))

    # ══════════ R5–R7：三个新守卫各自的「删掉它必须变红」══════════
    #
    # ★ 这三条是本轮 G-4 的关键：断言本身全绿不算数，
    #   要能证明「守卫被删除之后，前面那些断言真的会红」。
    #   做法是把守卫替换成永真的桩，然后看**本应由它拦下的那条断言**是否翻转。

    # R5 ★ 删掉人级 allowlist → 同角色未点名的人被放行
    with mock.patch("base.rbac._takedown_allowed", lambda p, c: True):
        p_signer2 = P("u_signer2", ["signer"])
        leaked = can_act(p_signer2, "takedown.execute", case_other) is True
    report(leaked,
           "R5 ★ 去掉人级名单 → 未点名的人也放行（反向对照成立）", "leaked=%r" % leaked)

    # R6 ★ 把元数据闸门的「对象分类」摘掉 → IT 读到案件内容
    #
    # ★ 打的桩必须是 _metadata_kind_allowed（**模块内部**的全局名），
    #   不是 can_read_metadata —— 后者被本文件 `from base.rbac import ...`
    #   绑成了本地名字，patch 模块属性改不到它，那条反向对照会**恒真**。
    with mock.patch("base.rbac._metadata_kind_allowed", lambda kind: True):
        leaked_meta = can_read_metadata(p_it, "case_content") is True
    report(leaked_meta,
           "R6 ★ 摘掉对象分类 → IT 读到案件内容（反向对照成立）",
           "leaked=%r" % leaked_meta)

    # R7 ★ 删掉 grant 的 scope 越界检查 → 跨租户授予被放行
    with mock.patch("base.rbac._scope_contains", lambda outer, inner: True):
        leaked_grant = validate_grant_actors(
            p_dp4, p_it, p_coord,
            granted_scope={"tenant": "t2", "product_lines": ["pump"]}) is True
    report(leaked_grant,
           "R7 ★ 去掉 scope 包含判定 → 跨租户授予被放行（反向对照成立）",
           "leaked=%r" % leaked_grant)

    # R8 ★ 「空品线当通配」这个具体写法必须被抓出来
    #    （R7 证明「检查没了会漏」，R8 证明「检查写错了也会漏」）
    with mock.patch("base.rbac._scope_contains",
                    lambda outer, inner: (outer.get("tenant") == inner.get("tenant"))):
        # 桩 = 只看租户、把空 product_lines 当成"没限制"
        leaked_empty = validate_grant_actors(
            p_dp4, p_it, p_coord,
            granted_scope={"tenant": "t1", "product_lines": []}) is True
    report(leaked_empty,
           "R8 ★ 空品线被当成通配 → 授予空集合也放行（反向对照成立）",
           "leaked=%r" % leaked_empty)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
