#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/rbac.py — T0-07 切片 2：RBAC / 对象 ACL

边界：
- 只做授权判断；不查库、不发消息、不判 state。
- 角色：submitter / dp3 / dp4 / signer / coordinator / it / machine。
- 对象 ACL：提交人仅自己；DP3/DP4 tenant+product_line+assigned/actionable；
  签发人 scope+SoD；统筹 tenant 内全部；IT 仅元数据；机器仅既定 API。
- 反向对照通过 bad_mode 暴露（no_scope / no_sod / it_content），仅测试使用。
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
    "signer": {"release.sign", "release.revoke"},
    "coordinator": {"case.review", "appeal.handle", "admin.grant.approve"},
    "it": {"admin.grant.execute"},
    "machine": set(),
}


def role_capabilities(role):
    return set(_ROLE_CAPS.get(role, set()))


def _has_role(principal, role):
    return role in (principal.get("roles") or [])


def _has_cap(principal, capability):
    return any(capability in role_capabilities(r) for r in (principal.get("roles") or []))


def _scope_ok(principal, case, bad_mode=None):
    if bad_mode == "no_scope":
        return True
    if principal.get("tenant") != case.get("tenant"):
        return False
    return case.get("product_line") in (principal.get("product_lines") or [])


def _assigned_or_actionable(principal, case):
    return (case.get("assignee_id") == principal.get("id")
            or bool(case.get("actionable")))


def _sod_ok(principal, case, bad_mode=None):
    if bad_mode == "no_sod":
        return True
    return (principal.get("id") != case.get("submitter_id")
            and principal.get("id") != case.get("final_reviewer_id"))


def can_act(principal, capability, case=None, bad_mode=None):
    """判断 principal 能否对 case 执行 capability。"""
    if capability not in CAPABILITIES:
        return False
    if not _has_cap(principal, capability):
        return False
    # 机器无人类能力（role_capabilities 为空，这里再显式挡一次）
    if _has_role(principal, "machine"):
        return False
    # IT 只做 admin.*，不碰案件动作
    if _has_role(principal, "it"):
        return capability.startswith("admin.")
    # 无案件对象的全局能力（如 admin.grant.*）
    if case is None:
        return True
    if not _scope_ok(principal, case, bad_mode):
        return False
    if _has_role(principal, "dp3") or _has_role(principal, "dp4"):
        if not _assigned_or_actionable(principal, case):
            return False
    if capability in ("release.sign", "release.revoke"):
        if not _sod_ok(principal, case, bad_mode):
            return False
    return True


def can_read_content(principal, case, bad_mode=None):
    """内容可见性；IT/机器默认不可读内容。"""
    if _has_role(principal, "it"):
        return bad_mode == "it_content"
    if _has_role(principal, "machine"):
        return False
    if _has_role(principal, "submitter"):
        return case.get("submitter_id") == principal.get("id")
    if _has_role(principal, "coordinator"):
        return principal.get("tenant") == case.get("tenant")
    if _has_role(principal, "dp3") or _has_role(principal, "dp4"):
        return _scope_ok(principal, case, bad_mode) and _assigned_or_actionable(principal, case)
    if _has_role(principal, "signer"):
        return _scope_ok(principal, case, bad_mode)
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
            cap for r in (approver.get("roles") or []) for cap in role_capabilities(r)):
        return False
    return True


def deny_all(principal, capability, case=None, bad_mode=None):
    """测试用坏实现：全拒。用于证明“有权样本必须通过”能抓出它。"""
    return False
