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
    report(can_read_content(p_it, case_own) is False, "C6 IT 读内容 → 拒", "")
    report(can_read_metadata(p_it) is True, "C6 IT 读元数据 → 允许", "")

    # C7
    report(can_read_content(p_machine, case_own) is False, "C7 机器读内容 → 拒", "")
    report(can_act(p_machine, "release.sign", case_other) is False,
           "C7 机器签发 → 拒", "")

    # C8
    report(validate_grant_actors(p_dp4, p_it, p_coord) is True,
           "C8 grant 三方不同人 → 允许", "")
    report(validate_grant_actors(p_dp4, p_dp4, p_coord) is False,
           "C8 提案=执行 → 拒", "")
    report(validate_grant_actors(p_dp4, p_it, p_it) is False,
           "C8 执行=审批 → 拒", "")
    report(validate_grant_actors(p_dp4, p_it, p_dp3) is False,
           "C8 审批无 approve 能力 → 拒", "")

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

    # C13 takedown 能力可用且不越权
    report(can_act(p_signer, "takedown.execute", case_other) is True,
           "C13 签发人执行下线 → 允许", "")
    report(can_act(p_signer, "takedown.waive", case_other) is True,
           "C13 签发人参与豁免审批 → 允许", "")
    report(can_act(p_coord, "takedown.waive", case_other) is True,
           "C13 统筹参与豁免审批 → 允许", "")
    report(can_act(p_dp3, "takedown.execute", case_other) is False,
           "C13 DP3 无下线执行能力 → 拒", "")

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
