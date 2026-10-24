#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/release_gate.py —— 唯一放行门（T2-03 / RL-1…RL-15）

## 状态机（RL-2）

    pending_release ──sign──> signed ──revoke──> revoked
          │                     │
          │                     └──invalidate──> invalidated
          └──reject──> rejected                    │
                                                   └─重审完成→ pending_release

## 放行只能由 sign 改

`release_status` 只在本模块的 `sign` / `reject` / `revoke` / `invalidate` 路径里变。
`apply_machine_patch()` 对任何含 `release_status` / `status` 的 patch **直接拒绝** ——
机器标签不可写放行（RL-3 / L3-5 的同一条纪律）。

## 签发绑定（UIUX §8.4 / SB-1…SB-11）

签名记录必须绑定 `case_version`、IR id/version、raw/text 指纹、rule/kb 快照
（version+hash）、`used_authority_refs[{ref_id,version}]`、`conflict_table_version`、
六类媒体指纹 + `media_fingerprints_root_hash`、`signature_version`、signer/signed_at/
step_up_ref/decision/reason。签名不可变：`signature_hash` 可复算，改一个字段即红。

## 失效（RL-6 / RL-11 / RL-14）

五类输入任一变化 → `invalidated` → **自动建全量重审 job（queued）**：
  1. raw/text 指纹（含媒体 root）
  2. rule_snapshot（version+hash）
  3. kb_snapshot（version+hash）
  4. **本次实际使用过的** authority_ref 版本（未使用的不触发）
  5. conflict_table_version

queued 期间连续变化合并 change_set；running 期间再变化建 successor；
同一 change_set 幂等；全部完成后回 pending_release。

## SoD / step-up

`signer_id ≠ submitter_id` 且 `≠ final_reviewer_id`；必须持有 `release.sign`；
step-up token 由 `base/auth_session.SessionStore.consume_step_up()` **消费一次**，
重复使用 / 错 action / 错 nonce / 过期一律拒。
"""
from __future__ import annotations

import copy
import hashlib
import json

SIGNATURE_VERSION = "release-signature-v1"

SIGNATURE_FIELDS = (
    "signature_id", "signature_version", "case_id", "case_version",
    "ir_id", "ir_version", "raw_sha256", "text_sha256",
    "rule_snapshot_version", "rule_snapshot_hash",
    "kb_snapshot_version", "kb_snapshot_hash",
    "used_authority_refs", "conflict_table_version",
    "frame_manifest_hash", "keyframe_set_hash", "ocr_output_hash",
    "asr_output_hash", "model_config_hash", "sampling_config_hash",
    "media_fingerprints_root_hash", "signer_id", "signed_at",
    "step_up_ref", "decision", "reason", "derived_from", "signature_hash",
)

HEX64 = set("0123456789abcdef")


class ReleaseGateError(Exception):
    pass


class SignatureError(ReleaseGateError):
    pass


class StepUpError(ReleaseGateError):
    pass


class SoDViolation(ReleaseGateError):
    pass


class InvalidTransition(ReleaseGateError):
    pass


class MachineWriteDenied(ReleaseGateError):
    pass


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and set(v.lower()) <= HEX64


def media_root(items):
    """确定性媒体指纹 root（RFC 8785 风格的 canonical JSON → SHA-256）。

    按 (kind, stable_id) 稳定排序；不是 Merkle tree，只是确定性摘要。
    """
    canon = []
    for it in items or []:
        if not isinstance(it, dict):
            raise SignatureError("media item 必须是对象")
        canon.append({
            "kind": it.get("kind"),
            "stable_id": it.get("stable_id"),
            "sha256": it.get("sha256"),
        })
    canon.sort(key=lambda x: (str(x["kind"]), str(x["stable_id"])))
    return _sha(_canonical({"items": canon}))


def _snapshot(case, name):
    s = case.get(name)
    if not isinstance(s, dict):
        raise SignatureError("case.%s 缺失" % name)
    version, fingerprint = s.get("version"), s.get("hash")
    if not isinstance(version, str) or not version:
        raise SignatureError("%s.version 缺失" % name)
    if not _hex64(fingerprint):
        raise SignatureError("%s.hash 不是 64 位十六进制" % name)
    return version, fingerprint


def _binding(case):
    """校验 case 的签发绑定字段，返回规范化后的绑定值。"""
    if not isinstance(case, dict):
        raise SignatureError("case 必须是 dict")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise SignatureError("case_id 缺失")
    if not isinstance(case.get("case_version"), int):
        raise SignatureError("case_version 必须是整数")
    for k in ("ir_id", "ir_version", "raw_sha256", "text_sha256",
              "conflict_table_version", "frame_manifest_hash",
              "keyframe_set_hash", "ocr_output_hash", "asr_output_hash",
              "model_config_hash", "sampling_config_hash"):
        if not isinstance(case.get(k), str) or not case[k]:
            raise SignatureError("case.%s 缺失" % k)
    for k in ("raw_sha256", "text_sha256", "frame_manifest_hash",
              "keyframe_set_hash", "ocr_output_hash", "asr_output_hash",
              "model_config_hash", "sampling_config_hash"):
        if not _hex64(case[k]):
            raise SignatureError("case.%s 不是 64 位十六进制" % k)
    rv, rh = _snapshot(case, "rule_snapshot")
    kv, kh = _snapshot(case, "kb_snapshot")
    refs = case.get("used_authority_refs")
    if not isinstance(refs, list):
        raise SignatureError("used_authority_refs 必须是数组")
    norm_refs = []
    for r in refs:
        if not isinstance(r, dict) or not isinstance(r.get("ref_id"), str) \
                or not isinstance(r.get("version"), str) or not r["version"]:
            raise SignatureError("used_authority_refs 条目必须含 ref_id/version")
        norm_refs.append({"ref_id": r["ref_id"], "version": r["version"]})
    norm_refs.sort(key=lambda x: x["ref_id"])

    media = case.get("media_fingerprints") or []
    if not isinstance(media, list):
        raise SignatureError("media_fingerprints 必须是数组")
    root = media_root(media)
    if "media_fingerprints_root_hash" in case \
            and case["media_fingerprints_root_hash"] != root:
        raise SignatureError("media_fingerprints_root_hash 与条目重算不符")

    return {
        "case_id": case_id,
        "case_version": case["case_version"],
        "ir_id": case["ir_id"],
        "ir_version": case["ir_version"],
        "raw_sha256": case["raw_sha256"],
        "text_sha256": case["text_sha256"],
        "rule_snapshot_version": rv,
        "rule_snapshot_hash": rh,
        "kb_snapshot_version": kv,
        "kb_snapshot_hash": kh,
        "used_authority_refs": norm_refs,
        "conflict_table_version": case["conflict_table_version"],
        "frame_manifest_hash": case["frame_manifest_hash"],
        "keyframe_set_hash": case["keyframe_set_hash"],
        "ocr_output_hash": case["ocr_output_hash"],
        "asr_output_hash": case["asr_output_hash"],
        "model_config_hash": case["model_config_hash"],
        "sampling_config_hash": case["sampling_config_hash"],
        "media_fingerprints_root_hash": root,
    }


def signature_hash(sig):
    body = {k: v for k, v in sig.items() if k != "signature_hash"}
    return _sha(_canonical(body))


def validate_signature(sig):
    """复核签名记录；返回错误列表（空 = 通过）。"""
    errs = []
    if not isinstance(sig, dict):
        return ["not_object"]
    missing = [k for k in SIGNATURE_FIELDS if k not in sig]
    if missing:
        return ["missing_fields:%s" % ",".join(missing)]
    if sig.get("signature_version") != SIGNATURE_VERSION:
        errs.append("bad_signature_version")
    for k in ("case_id", "ir_id", "ir_version", "raw_sha256", "text_sha256",
              "rule_snapshot_version", "rule_snapshot_hash",
              "kb_snapshot_version", "kb_snapshot_hash",
              "conflict_table_version", "frame_manifest_hash",
              "keyframe_set_hash", "ocr_output_hash", "asr_output_hash",
              "model_config_hash", "sampling_config_hash",
              "media_fingerprints_root_hash", "signer_id", "signed_at",
              "step_up_ref", "decision", "reason"):
        if not isinstance(sig.get(k), str) or not sig[k]:
            errs.append("bad_%s" % k)
    for k in ("raw_sha256", "text_sha256", "rule_snapshot_hash",
              "kb_snapshot_hash", "frame_manifest_hash", "keyframe_set_hash",
              "ocr_output_hash", "asr_output_hash", "model_config_hash",
              "sampling_config_hash", "media_fingerprints_root_hash"):
        if not _hex64(sig.get(k)):
            errs.append("bad_hex:%s" % k)
    refs = sig.get("used_authority_refs")
    if not isinstance(refs, list):
        errs.append("bad_used_authority_refs")
    else:
        for r in refs:
            if not isinstance(r, dict) or not isinstance(r.get("ref_id"), str) \
                    or not isinstance(r.get("version"), str):
                errs.append("bad_used_authority_refs_item")
                break
    if not isinstance(sig.get("signature_id"), str) or not sig["signature_id"]:
        errs.append("bad_signature_id")
    if sig.get("derived_from") is not None and not isinstance(sig["derived_from"], str):
        errs.append("bad_derived_from")
    if sig.get("decision") not in ("signed", "rejected"):
        errs.append("bad_decision")
    if sig.get("signature_hash") != signature_hash(sig):
        errs.append("signature_hash_mismatch")
    return errs


class ReleaseGate(object):
    def __init__(self, sessions=None):
        self.sessions = sessions
        self._cases = {}

    # ── 状态 ──────────────────────────────────────────────────────────
    def _ensure(self, case):
        cid = case.get("case_id")
        if cid not in self._cases:
            self._cases[cid] = {
                "case": copy.deepcopy(case),
                "status": "pending_release",
                "release_status": "待放行",
                "signatures": [],
                "active_job": None,
                "successor": None,
                "events": [],
            }
        return self._cases[cid]

    def state(self, case_id):
        st = self._cases.get(case_id)
        if st is None:
            return None
        return {
            "status": st["status"],
            "release_status": st["release_status"],
            "case": copy.deepcopy(st["case"]),
            "active_job": copy.deepcopy(st["active_job"]),
            "successor": copy.deepcopy(st["successor"]),
            "events": copy.deepcopy(st["events"]),
        }

    def pending(self):
        return [cid for cid, st in self._cases.items()
                if st["status"] == "pending_release"]

    def signatures(self, case_id):
        st = self._cases.get(case_id)
        if st is None:
            return []
        return copy.deepcopy(st["signatures"])

    # ── 权限 / step-up ────────────────────────────────────────────────
    def _authorize(self, case, principal, action):
        if not isinstance(principal, dict):
            raise SoDViolation("principal 必须是对象")
        pid = principal.get("id")
        if pid == case.get("submitter_id"):
            raise SoDViolation("提交人不得签发自己提交的案件")
        if pid == case.get("final_reviewer_id"):
            raise SoDViolation("最终复核人不得签发自己复核的案件")
        if action in ("sign", "reject"):
            if "release.sign" not in (principal.get("capabilities") or []):
                raise SoDViolation("缺少 release.sign")
        if action == "revoke":
            caps = principal.get("capabilities") or []
            # ★ 2026-10-23 行 91：撤回权**不随**签发权自动获得。
            #   原写法 `revoke not in caps and sign not in caps` 等于「有签发权就能撤回」——
            #   实测：只有 release.sign 的账号发起撤回会被放行。
            #   修法是**只认 release.revoke**；把 `and` 直接换成 `or` 会变成
            #   「两个能力都必须有」，比行 91 的要求更严，也不对。
            if "release.revoke" not in caps:
                raise SoDViolation("缺少 release.revoke")
        if principal.get("tenant") != case.get("tenant"):
            raise SoDViolation("跨租户")
        if principal.get("product_line") != case.get("product_line"):
            raise SoDViolation("跨品线")

    def _consume(self, principal, case, action, token, nonce, now):
        if self.sessions is None:
            raise StepUpError("没有 session store —— step-up 无法消费，拒绝签发")
        if not isinstance(token, str) or not token:
            raise StepUpError("step-up token 缺失")
        ref = self.sessions.consume_step_up_ref(
            token, principal.get("id"), case.get("case_id"), action, nonce, now=now)
        if not ref:
            raise StepUpError("step-up token 无效（过期/已用/绑定不符）")
        return ref

    # ── sign / reject / revoke ───────────────────────────────────────
    def sign(self, case, principal, token, nonce, decision="signed",
             reason="", now=None):
        self._ensure(case)
        st = self._cases[case["case_id"]]
        if st["status"] != "pending_release":
            raise InvalidTransition("只有 pending_release 可签发，当前 %s" % st["status"])
        if decision not in ("signed", "rejected"):
            raise SignatureError("decision 必须是 signed/rejected")
        if not isinstance(reason, str) or not reason.strip():
            raise SignatureError("reason 必填")
        self._authorize(case, principal, "sign")
        binding = _binding(case)
        action = "reject" if decision == "rejected" else "sign"
        step_up_ref = self._consume(principal, case, action, token, nonce, now)

        sid = "sig-" + _sha(_canonical({
            "case_id": case["case_id"], "case_version": case["case_version"],
            "signed_at": now, "nonce": nonce, "n": len(st["signatures"]),
        }))[:16]
        sig = dict(binding)
        sig.update({
            "signature_id": sid,
            "signature_version": SIGNATURE_VERSION,
            "signer_id": principal["id"],
            "signed_at": str(now),
            "step_up_ref": step_up_ref,
            "decision": decision,
            "reason": reason,
            "derived_from": (st["signatures"][-1]["signature_id"]
                             if st["signatures"] else None),
        })
        sig["signature_hash"] = signature_hash(sig)
        errs = validate_signature(sig)
        if errs:
            raise SignatureError("签名不合法：%s" % "; ".join(errs))
        st["signatures"].append(copy.deepcopy(sig))
        st["status"] = "signed" if decision == "signed" else "rejected"
        st["release_status"] = "已放行" if decision == "signed" else "已拒绝"
        st["case"] = copy.deepcopy(case)
        return copy.deepcopy(sig)

    def reject(self, case, principal, token, nonce, reason="", now=None):
        return self.sign(case, principal, token, nonce, decision="rejected",
                         reason=reason, now=now)

    def revoke(self, case, principal, token, nonce, reason="", now=None):
        cid = case.get("case_id") if isinstance(case, dict) else case
        st = self._cases.get(cid)
        if st is None or st["status"] != "signed":
            raise InvalidTransition("只有 signed 可撤回，当前 %s"
                                    % (st["status"] if st else "missing"))
        # ★ T-315b / #123c：撤回绑定**原签发人**。此前任何持 release.revoke 者
        #   可撤任何人的签发 —— 票面 #123(c) 的判定当时不存在。边界（施工单
        #   §二）：名单只盖 release.sign 不盖 revoke；纯靠 grant 拿 revoke 的
        #   人被撤权后，撤回失效是预期（角色矩阵里的 revoke 不受名单影响）。
        sigs = st.get("signatures") or []
        last_signer = sigs[-1].get("signer_id") if sigs else None
        if (principal or {}).get("id") != last_signer:
            raise SoDViolation(
                "not_original_signer: 撤回只能由原签发人执行（#123c），"
                "该案签发人是 %r" % last_signer)
        self._authorize(st["case"], principal, "revoke")
        step_up_ref = self._consume(
            principal, st["case"], "revoke", token, nonce, now)
        st["status"] = "revoked"
        st["release_status"] = "已撤回"
        st["events"].append({
            "kind": "release_revoked", "at": now,
            "actor": principal.get("id"), "step_up_ref": step_up_ref,
            "reason": reason,
        })
        if isinstance(case, dict):
            st["case"] = copy.deepcopy(case)
        return {"status": st["status"], "release_status": st["release_status"]}

    # ── 失效 / 重审 job ──────────────────────────────────────────────
    @staticmethod
    def _changes(sig, case):
        changes = []
        if case.get("raw_sha256") != sig["raw_sha256"]:
            changes.append({"field": "raw_sha256", "old_version": sig["raw_sha256"],
                            "new_version": case.get("raw_sha256"),
                            "source": "content"})
        if case.get("text_sha256") != sig["text_sha256"]:
            changes.append({"field": "text_sha256", "old_version": sig["text_sha256"],
                            "new_version": case.get("text_sha256"),
                            "source": "content"})
        root = media_root(case.get("media_fingerprints") or [])
        if root != sig["media_fingerprints_root_hash"]:
            changes.append({"field": "media_fingerprints_root_hash",
                            "old_version": sig["media_fingerprints_root_hash"],
                            "new_version": root, "source": "content"})
        rv, rh = _snapshot(case, "rule_snapshot")
        if rv != sig["rule_snapshot_version"] or rh != sig["rule_snapshot_hash"]:
            changes.append({"field": "rule_snapshot",
                            "old_version": "%s/%s" % (sig["rule_snapshot_version"],
                                                      sig["rule_snapshot_hash"]),
                            "new_version": "%s/%s" % (rv, rh),
                            "source": "rule_snapshot"})
        kv, kh = _snapshot(case, "kb_snapshot")
        if kv != sig["kb_snapshot_version"] or kh != sig["kb_snapshot_hash"]:
            changes.append({"field": "kb_snapshot",
                            "old_version": "%s/%s" % (sig["kb_snapshot_version"],
                                                      sig["kb_snapshot_hash"]),
                            "new_version": "%s/%s" % (kv, kh),
                            "source": "kb_snapshot"})
        cur_refs = {}
        for r in case.get("used_authority_refs") or []:
            if isinstance(r, dict) and isinstance(r.get("ref_id"), str):
                cur_refs[r["ref_id"]] = r.get("version")
        for r in sig["used_authority_refs"]:
            if cur_refs.get(r["ref_id"]) != r["version"]:
                changes.append({"field": "used_authority_refs",
                                "old_version": "%s:%s" % (r["ref_id"], r["version"]),
                                "new_version": "%s:%s" % (r["ref_id"], cur_refs.get(r["ref_id"])),
                                "source": "authority_ref"})
        if case.get("conflict_table_version") != sig["conflict_table_version"]:
            changes.append({"field": "conflict_table_version",
                            "old_version": sig["conflict_table_version"],
                            "new_version": case.get("conflict_table_version"),
                            "source": "conflict_table"})
        return changes

    def _new_job(self, cid, change_set, now):
        return {
            "job_id": "job-" + _sha(_canonical({"case_id": cid, "at": now,
                                                "n": len(self._cases[cid]["events"]) }))[:16],
            "case_id": cid,
            "state": "queued",
            "change_set": copy.deepcopy(change_set),
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        }

    @staticmethod
    def _merge(change_set, extra):
        by_field = {}
        for c in change_set + extra:
            by_field[c["field"]] = c
        return list(by_field.values())

    def invalidate(self, case_id, current, now=None):
        st = self._cases.get(case_id)
        # invalidated 期间仍要看新变化：queued 合并、running 建 successor（RL-14）。
        if st is None or st["status"] not in ("signed", "invalidated") \
                or not st["signatures"]:
            return {"invalidated": False, "reason": "not_signed"}
        sig = st["signatures"][-1]
        changes = self._changes(sig, current)
        if not changes:
            return {"invalidated": False, "reason": "no_change", "change_set": []}
        key = "inv-" + _sha(_canonical({
            "case_id": case_id, "signature_id": sig["signature_id"],
            "changes": changes}))[:16]
        prior = st["events"][-1] if st["events"] else None
        if prior and prior.get("event_key") == key:
            return {"invalidated": False, "reason": "duplicate_event",
                    "change_set": changes,
                    "job": copy.deepcopy(st["active_job"] or st["successor"]),
                    "job_created": False}
        st["status"] = "invalidated"
        st["release_status"] = "已失效"
        job_created = False
        job = st["active_job"]
        if job is None or job["state"] == "done":
            job = self._new_job(case_id, changes, now)
            st["active_job"] = job
            job_created = True
        elif job["state"] == "queued":
            job["change_set"] = self._merge(job["change_set"], changes)
        else:  # running
            if st["successor"] is None:
                st["successor"] = self._new_job(case_id, changes, now)
                job_created = True
            else:
                st["successor"]["change_set"] = self._merge(
                    st["successor"]["change_set"], changes)
            job = st["successor"]
        st["events"].append({"event_key": key, "at": now,
                             "change_set": copy.deepcopy(changes),
                             "job_id": job["job_id"]})
        return {"invalidated": True, "change_set": changes,
                "job": copy.deepcopy(job), "job_created": job_created}

    def start_job(self, case_id, now=None):
        st = self._cases.get(case_id)
        if st is None:
            raise InvalidTransition("未知 case")
        job = st["active_job"]
        if job is None or job["state"] != "queued":
            raise InvalidTransition("没有 queued job")
        job["state"] = "running"
        job["started_at"] = now
        return copy.deepcopy(job)

    def complete_job(self, case_id, now=None):
        st = self._cases.get(case_id)
        if st is None:
            raise InvalidTransition("未知 case")
        job = st["active_job"]
        if job is None or job["state"] != "running":
            raise InvalidTransition("没有 running job")
        job["state"] = "done"
        job["completed_at"] = now
        if st["successor"] is not None:
            st["active_job"] = st["successor"]
            st["successor"] = None
            st["status"] = "invalidated"
        else:
            st["active_job"] = job  # 保留历史
            st["status"] = "pending_release"
            st["release_status"] = "待放行"
        return copy.deepcopy(st["active_job"])

    # ── 机器写入闸 ───────────────────────────────────────────────────
    def apply_machine_patch(self, case_id, patch):
        if not isinstance(patch, dict):
            raise MachineWriteDenied("patch 必须是对象")
        if "release_status" in patch or "status" in patch:
            raise MachineWriteDenied("机器标签不可写放行状态")
        st = self._cases.get(case_id)
        if st is None:
            raise InvalidTransition("未知 case")
        st["case"].update(copy.deepcopy(patch))
        return copy.deepcopy(st["case"])
