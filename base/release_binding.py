#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/release_binding.py —— 签发绑定字段从权威 state 的提取（T-310a）。

`ReleaseGate._binding()` 要求的绑定字段今天在案件 state 里没有生产者；
本模块是**唯一**的提取器：`binding_from_state(state)` 的输出可以直接作为
`ReleaseGate.sign(case, ...)` 的 `case` 参数。判定函数仍只在 release_gate ——
这里不做任何校验语义的新发明，缺字段一律抛 `SignatureError`（fail closed）。

## 口径（T-310 施工单 §二 前置 A；D1 已于 2026-10-25 裁定）

- `kb_snapshot_hash` = `ExternalStandardsAuthority.snapshot_id` 的 sha256，
  由 `SubmissionIngestor` 在判定时写入 state；取不到不许签。
- `conflict_table_version` 与 `ir.control_points_version` 是**同一个量**（§2.4.8），
  reducer 在 ingest 时已断言两者一致。
- `used_authority_refs` 取 `ir.findings[*]` 中 `authority_state == "ok"` 的
  `authority_ref` 条目去重；**version 取 ref 自带的 `fingerprint`**
  （KB 条目的变更指纹，判定时 evidence_sync 已用它对过账）——
  不另造 `state["authority_versions"]`（同一个量不写第二个口径）。
  空数组合法：文本件无外部依据时确实为空。
- 六类媒体指纹：文本件（无媒体）用固定占位 `sha256(b"absent:<field>")` ——
  本单唯一允许的生成默认值：确定性、可复算、不等于任何真实指纹，
  且有一条断言钉住它不是字符串常量（`absent` → `not_available` 必红）。
  媒体件今天不可入库（只接 free_text/ad_text）；`ir.media_fingerprints`
  里给了的键原样透传，缺的键仍落占位 —— 透传值过不了 `_binding` 的 hex64
  就在签发时红，不许在这里放水。

本模块纯函数、无 IO、不 import reducer（保持可被 release_gate 侧复用）。
"""
from __future__ import annotations

import hashlib
import json

from base.release_gate import SignatureError, media_root

# 六类媒体指纹的绑定字段名（顺序即 canonical 顺序；与 SIGNATURE_FIELDS 一致）。
MEDIA_BINDING_FIELDS = (
    "frame_manifest_hash", "keyframe_set_hash", "ocr_output_hash",
    "asr_output_hash", "model_config_hash", "sampling_config_hash",
)

_HEX64 = set("0123456789abcdef")


def _hex64(value):
    return isinstance(value, str) and len(value) == 64 \
        and set(value.lower()) <= _HEX64


def media_placeholders(ir_media=None):
    """返回 (六类指纹 dict, media_root_hash)。

    `ir_media` 是 `ir["media_fingerprints"]`（判定时冻结的 dict，文本件为 {}）。
    占位 hash 确定性：同输入两次调用结果相同（A3 断言）。
    """
    if ir_media is None:
        ir_media = {}
    if not isinstance(ir_media, dict):
        raise SignatureError("ir.media_fingerprints 必须是对象")
    fields = {}
    for name in MEDIA_BINDING_FIELDS:
        value = ir_media.get(name)
        if isinstance(value, str) and value:
            fields[name] = value
        else:
            fields[name] = hashlib.sha256(
                b"absent:" + name.encode("utf-8")).hexdigest()
    # 无媒体条目：root 是对空列表的确定性摘要，签名里可复算。
    return fields, media_root([])


def binding_from_state(state):
    """从案件 state 组装 `_binding()` 需要的绑定字段 dict；缺即抛错。"""
    if not isinstance(state, dict):
        raise SignatureError("state 必须是 dict")
    ir = state.get("ir")
    if not isinstance(ir, dict):
        raise SignatureError("state.ir 缺失")
    for key in ("ir_id", "ir_version"):
        if not isinstance(ir.get(key), str) or not ir[key]:
            raise SignatureError("state.ir.%s 缺失" % key)
    content = state.get("content")
    fp = (content or {}).get("fingerprint") if isinstance(content, dict) else None
    if not isinstance(fp, dict):
        raise SignatureError("state.content.fingerprint 缺失")
    for key in ("raw_sha256", "text_sha256"):
        if not _hex64(fp.get(key)):
            raise SignatureError("state.content.fingerprint.%s 缺失或非 hex64" % key)
    coverage = ir.get("coverage") or {}
    rules_version = coverage.get("rules_version")
    # ★ 生产 IR 的真形状：_coverage_ir（orchestrator.py:117-120）把 rules_version
    #   规范化成 **JSON 字符串**（canonical JSON，sort_keys）。composer 直出的
    #   dict 形状只存在于过渡对象上；两种都收，解析失败 fail closed。
    if isinstance(rules_version, str):
        try:
            rules_version = json.loads(rules_version)
        except Exception as exc:  # noqa: BLE001
            raise SignatureError(
                "state.ir.coverage.rules_version 不是合法 JSON: %s" % exc) from exc
    if not isinstance(rules_version, dict) \
            or not isinstance(rules_version.get("version"), str) \
            or not rules_version["version"] \
            or not _hex64(rules_version.get("fingerprint")):
        raise SignatureError(
            "state.ir.coverage.rules_version 缺失（version/fingerprint）")
    kb_version = ir.get("kb_snapshot")
    if not isinstance(kb_version, str) or not kb_version:
        raise SignatureError("state.ir.kb_snapshot 缺失")
    kb_hash = state.get("kb_snapshot_hash")
    if not _hex64(kb_hash):
        raise SignatureError("state.kb_snapshot_hash 缺失（判定时未写入）")
    ctv = state.get("conflict_table_version")
    if not isinstance(ctv, str) or not ctv:
        raise SignatureError("state.conflict_table_version 缺失")

    # used_authority_refs：authority_state=ok 的 findings 的 authority_ref 去重。
    seen, refs = set(), []
    findings = ir.get("findings") or []
    if not isinstance(findings, list):
        raise SignatureError("state.ir.findings 必须是数组")
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("authority_state") != "ok":
            continue
        for ref in finding.get("authority_ref") or []:
            if not isinstance(ref, dict):
                continue
            entry_id, fingerprint = ref.get("entry_id"), ref.get("fingerprint")
            if not isinstance(entry_id, str) or not entry_id \
                    or not isinstance(fingerprint, str) or not fingerprint:
                continue
            if entry_id in seen:
                continue
            seen.add(entry_id)
            refs.append({"ref_id": entry_id, "version": fingerprint})
    refs.sort(key=lambda r: r["ref_id"])

    media_fields, root_hash = media_placeholders(ir.get("media_fingerprints"))
    return {
        "case_id": state.get("case_id"),
        "case_version": state.get("version"),
        "ir_id": ir["ir_id"],
        "ir_version": ir["ir_version"],
        "raw_sha256": fp["raw_sha256"],
        "text_sha256": fp["text_sha256"],
        "rule_snapshot": {"version": rules_version["version"],
                          "hash": rules_version["fingerprint"]},
        "kb_snapshot": {"version": kb_version, "hash": kb_hash},
        "used_authority_refs": refs,
        "conflict_table_version": ctv,
        **media_fields,
        "media_fingerprints": [],
        "media_fingerprints_root_hash": root_hash,
    }
