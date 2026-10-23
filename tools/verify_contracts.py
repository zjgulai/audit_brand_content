#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_contracts.py —— 五份契约 schema 的正/负样本校验（T1-C1）

**它修的是什么**：技术方案里到处引用 `contracts/*.schema.json`，而 `contracts/` 目录
此前根本不存在。这个脚本做两件事：
  ① 校验**五份 schema 文件本身**结构合法（不是空壳、required 非空、enum 非空）；
  ② 喂**正/负样本**给每份 schema，断言好样本过、坏样本必须被拒。

──────────────────────────────────────────────────────────────
为什么自己写校验器，不用 `jsonschema`
──────────────────────────────────────────────────────────────
本机没装 `jsonschema`（`import jsonschema` 直接 ImportError）。硬依赖一个没装的东西，
结果是「脚本跑不起来」，那不比没有更糟 —— 它看起来像个执行点。

所以这里实现一个**最小校验器**，只支持下面这些关键字。**这份清单就是它的诚实边界**：

  type / required / properties / additionalProperties / items / enum / const /
  minLength / minimum / format(date-time 近似) / if-then / not(required|enum) / contains

**不支持**（因此相关约束改由行为断言覆盖，不假装 schema 能拦）：
  · `minContains` / `maxContains` → 五步齐全改行为断言
  · 数组内唯一性（`uniqueItems` 对对象不可靠）→ finding_id 唯一改行为断言
  · `oneOf` / `anyOf` / `$ref` / `format` 的完整语义

★ 一条纪律：**不支持某关键字时，不许在 schema 里写一个看起来能拦的块。**
  一个只含 comment、`then: {}` 的 allOf 块，与没有它完全一样 —— 那是台账 K-06（名字出现过 ≠ 拦得住）。

──────────────────────────────────────────────────────────────
退出码：0 全绿 / 1 有红 / 2 未测（schema 文件读不到或整体结构坏到无法判断）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTRACTS = ROOT / "contracts"

SCHEMAS = (
    "attempt-v1",
    "receipt-v1",
    "review-ir-v1",
    "business-command-batch-v1",
    "projection-status-v1",
)

DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)

SUPPORTED = (
    "type", "required", "properties", "additionalProperties", "items", "enum",
    "const", "minLength", "minimum", "format", "if", "then", "not", "contains",
    "allOf",
)


# ═══════════════════════════ 最小校验器 ═══════════════════════════

def _type_ok(value, want: str) -> bool:
    # JSON Schema 的 "integer" 不接受 bool（Python 里 True 是 int 的子类）
    if want == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if want == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if want == "boolean":
        return isinstance(value, bool)
    if want == "string":
        return isinstance(value, str)
    if want == "array":
        return isinstance(value, list)
    if want == "object":
        return isinstance(value, dict)
    if want == "null":
        return value is None
    return True  # 未知类型名不判错（避免误报）


def validate(value, schema: dict, path: str = "$", errors: list | None = None) -> list:
    """返回错误列表。空列表 = 通过。"""
    if errors is None:
        errors = []
    if not isinstance(schema, dict):
        return errors

    def err(msg):
        errors.append(f"{path}: {msg}")

    # ── type（可为数组，表示多种允许类型）──
    if "type" in schema:
        want = schema["type"]
        wants = want if isinstance(want, list) else [want]
        if not any(_type_ok(value, w) for w in wants):
            err(f"类型应为 {wants}，实际 {type(value).__name__}")
            return errors  # 类型都不对，后面的断言没有意义

    # ── const ──
    if "const" in schema and value != schema["const"]:
        err(f"必须等于 {schema['const']!r}，实际 {value!r}")

    # ── enum ──
    if "enum" in schema and value not in schema["enum"]:
        err(f"必须属于 {schema['enum']}，实际 {value!r}")

    # ── 字符串 ──
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            err(f"长度须 ≥ {schema['minLength']}，实际 {len(value)}")
        if schema.get("format") == "date-time" and not DATE_TIME_RE.match(value):
            err(f"不是 ISO 8601 date-time：{value!r}")

    # ── 数值 ──
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            err(f"须 ≥ {schema['minimum']}，实际 {value}")

    # ── 对象 ──
    if isinstance(value, dict):
        for req in schema.get("required") or []:
            if req not in value:
                err(f"缺必填字段 {req!r}")
        props = schema.get("properties") or {}
        for k, v in value.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}", errors)
            elif schema.get("additionalProperties") is False:
                err(f"不允许的额外字段 {k!r}")

    # ── 数组 ──
    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, v in enumerate(value):
                validate(v, items, f"{path}[{i}]", errors)
        # contains：至少一项满足
        if isinstance(schema.get("contains"), dict):
            if not any(not validate(v, schema["contains"], f"{path}[{i}]", [])
                       for i, v in enumerate(value)):
                err(f"数组里没有任何一项满足 contains 条件")

    # ── not（只支持 required / enum 两种形态）──
    if isinstance(schema.get("not"), dict):
        n = schema["not"]
        if "required" in n:
            present = [k for k in n["required"] if isinstance(value, dict) and k in value]
            if present:
                err(f"字段 {present} 不允许出现")
        if "enum" in n and value in n["enum"]:
            err(f"取值 {value!r} 被显式禁止")

    # ── if / then ──
    if isinstance(schema.get("if"), dict):
        if not validate(value, schema["if"], path, []):
            then = schema.get("then")
            if isinstance(then, dict):
                validate(value, then, path, errors)

    # ── allOf：每一项都必须满足 ──
    # ★ 条件必填（accepted 必须有 ir_id、parse_status=failed 必须有 failure_kind）
    #   就靠它表达。不支持 allOf 会让这几条**静默通过** —— 那正是本轮实测抓到的：
    #   4 个负样本该红却全绿，原因不是 schema 写错，是校验器没实现这个关键字。
    for sub in schema.get("allOf") or []:
        if isinstance(sub, dict):
            validate(value, sub, path, errors)

    return errors


def unsupported_keywords(schema, path="$") -> list:
    """
    扫 schema 里有没有用到本校验器不支持的关键字 —— 用了就报，不许静默忽略。

    ★ 2026-10-18 变异审计抓到的假绿：原先 `allOf` 不在递归名单里，
      于是往 allOf 里塞 `{"anyOf": []}` 时验证器仍全绿 ——
      一个不支持的组合关键字被埋在支持的容器里，扫不到。
      现在 `allOf` / `anyOf` / `oneOf` 的**列表元素**都递归；列表本身若不在
      SUPPORTED 里，先记一条「不支持」，再递归进去（两层都要报）。
    """
    found = []
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k.startswith("x-") or k.startswith("$") or k in (
                    "comment", "comment2", "description", "title"):
                continue
            if k in ("properties", "items", "contains", "if", "then", "not", "allOf"):
                if k == "properties":
                    for sk, sv in (v if isinstance(v, dict) else {}).items():
                        found += unsupported_keywords(sv, f"{path}.{sk}")
                elif k == "allOf":
                    # 列表的每个元素都要递归
                    for i, el in enumerate(v if isinstance(v, list) else []):
                        found += unsupported_keywords(el, f"{path}.allOf[{i}]")
                else:
                    found += unsupported_keywords(v if isinstance(v, dict) else {}, f"{path}.{k}")
                continue
            if k not in SUPPORTED:
                found.append(f"{path}.{k}")
                # ★ 不支持的组合关键字（anyOf/oneOf）里还可能埋着别的，继续往下扫
                if isinstance(v, list):
                    for i, el in enumerate(v):
                        found += unsupported_keywords(el, f"{path}.{k}[{i}]")
                elif isinstance(v, dict):
                    found += unsupported_keywords(v, f"{path}.{k}")
    elif isinstance(schema, list):
        for i, el in enumerate(schema):
            found += unsupported_keywords(el, f"{path}[{i}]")
    return found


# ═══════════════════════════ schema 自检 ═══════════════════════════

def check_schema_shape(name: str, schema: dict) -> list:
    """schema 文件本身要像个 schema，不是空壳。"""
    out = []

    def ok(cid, cond, detail):
        out.append({"id": cid, "ok": bool(cond), "detail": detail})

    ok(f"{name}/·1", schema.get("type") == "object", f"type={schema.get('type')!r}")
    req = schema.get("required") or []
    ok(f"{name}/·2", len(req) > 0, f"required 字段 {len(req)} 个")
    props = schema.get("properties") or {}
    ok(f"{name}/·3", len(props) > 0, f"properties {len(props)} 个")
    missing = [r for r in req if r not in props]
    ok(f"{name}/·4", not missing, f"required 里有 {len(missing)} 个未在 properties 定义：{missing or '无'}")
    unk = unsupported_keywords(schema)
    ok(f"{name}/·5", not unk, f"未支持关键字 {len(unk)} 个" + (f"：{unk[:6]}" if unk else ""))
    return out


# ═══════════════════════════ 样本 ═══════════════════════════

def samples() -> dict:
    """正样本 + 每类负样本。负样本的 name 直接说明它测的是哪条约束。"""
    good_attempt = {
        "attempt_id": "at-1", "submission_id": "sub-1",
        "entered_at": "2026-10-18T10:00:00Z",
        "outcome": "accepted", "reason": "入口校验通过", "ir_id": "ir-1",
    }
    good_receipt = {
        "receipt_id": "rc-1", "unit_id": "u-1", "skill_id": "s", "skill_version": "1",
        "skill_hash": "abc", "started_at": "2026-10-18T10:00:00Z",
        "ended_at": "2026-10-18T10:00:03Z",
        "steps": [
            {"name": "normalize", "input_summary": "d1", "output_summary": "d2", "duration_ms": 10},
            {"name": "judge", "input_summary": "d3", "output_summary": "d4", "duration_ms": 20},
            {"name": "dispose", "input_summary": "d5", "output_summary": "d6", "duration_ms": 5},
            {"name": "output", "input_summary": "d7", "output_summary": "d8", "duration_ms": 5},
            {"name": "evaluate", "input_summary": "d9", "output_summary": "d10", "duration_ms": 3},
        ],
        "skipped": [],
        "rule_snapshot": "r1", "kb_snapshot": "k1",
        "obligations": [],
        "invariant_violation": None,
        "control_points_ran": ["H01"],
        "control_points_version": "cp-2026-10-18-v2",
        "video_sampling": None,
        "disposition": {"state": "REVIEW", "layer": "DP3", "release_status": "待放行"},
    }
    good_ir = {
        "ir_id": "ir-1", "ir_version": "v1", "source_ir_version": "v1",
        "content_unit_ref": {"unit_id": "u-1", "kind": "free_text", "parse_status": "ok"},
        "findings": [], "decision": {"state": "REVIEW", "layer": "DP3",
                                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "full", "modalities_evaluated": ["text"],
                     "rules_version": "r1", "control_points_applied": ["H01"]},
        "receipt_ref": "rc-1", "rule_snapshot": "r1", "kb_snapshot": "k1",
        "control_points_version": "cp-2026-10-18-v2",
        "created_at": "2026-10-18T10:00:00Z",
    }
    good_command = {
        "schema_version": "business-command-batch/v1",
        "command_id": "cmd-1",
        "authority_seq": 1,
        "prev_manifest_sha256": None,
        "aggregate_type": "review_case",
        "aggregate_id": "case-1",
        "expected_version": 0,
        "result_version": 1,
        "actor": {"principal_id": "ou-reviewer", "tenant_id": "t1"},
        "command": "claim",
        "occurred_at": "2026-10-20T10:00:00Z",
        "idempotency_key": "idem-1",
        "request_sha256": "a" * 64,
        "events": [{"type": "review.claimed", "version": 1}],
        "result": {"status": "claimed", "version": 1},
        "reconcile_token": "reconcile-token-000001",
    }
    good_projection = {
        "schema_version": "projection-status/v1",
        "status": "fresh",
        "authority": {
            "seq": 1,
            "manifest_sha256": "b" * 64,
            "committed_at": "2026-10-20T10:00:00Z",
        },
        "projection": {
            "applied_seq": 1,
            "manifest_sha256": "b" * 64,
            "schema_version": 1,
            "rebuilt_at": "2026-10-20T10:00:01Z",
        },
        "lag_commits": 0,
        "lag_seconds": 0,
        "last_error_code": None,
        "reconcile_token": None,
    }
    return {
        "attempt-v1": [
            ("好样本（accepted）", good_attempt, True),
            ("缺必填 reason", {k: v for k, v in good_attempt.items() if k != "reason"}, False),
            ("outcome 枚举外", {**good_attempt, "outcome": "weird"}, False),
            ("reason 是无信息词", {**good_attempt, "reason": "其他"}, False),
            ("accepted 却没有 ir_id", {k: v for k, v in good_attempt.items() if k != "ir_id"}, False),
            ("rejected_unsupported 却带 ir_id",
             {"attempt_id": "a", "submission_id": "s", "entered_at": "2026-10-18T10:00:00Z",
              "outcome": "rejected_unsupported", "failure_kind": "unsupported",
              "reason": "入口不支持", "ir_id": "ir-1"}, False),
            # ★ VC-1d：这两条是变异审计抓出来的。原先只有「带 ir_id」一条负样本，
            #   于是删掉 schema 里 `not:{required:["receipt_id"]}` 后验证器仍全绿 ——
            #   一个守卫没被测过，等于没有。
            ("rejected_unsupported 却带 receipt_id",
             {"attempt_id": "a", "submission_id": "s", "entered_at": "2026-10-18T10:00:00Z",
              "outcome": "rejected_unsupported", "failure_kind": "unsupported",
              "reason": "入口不支持", "receipt_id": "rc-1"}, False),
            ("failed 却带 receipt_id",
             {"attempt_id": "a", "submission_id": "s", "entered_at": "2026-10-18T10:00:00Z",
              "outcome": "failed", "failure_kind": "fetch_error",
              "reason": "抓取失败", "receipt_id": "rc-1"}, False),
            ("failed 却带 ir_id",
             {"attempt_id": "a", "submission_id": "s", "entered_at": "2026-10-18T10:00:00Z",
              "outcome": "failed", "failure_kind": "fetch_error",
              "reason": "抓取失败", "ir_id": "ir-1"}, False),
            ("失败却没 failure_kind",
             {"attempt_id": "a", "submission_id": "s", "entered_at": "2026-10-18T10:00:00Z",
              "outcome": "failed", "reason": "抓取失败"}, False),
            ("额外字段", {**good_attempt, "unknown_field": 1}, False),
            ("entered_at 不是时间", {**good_attempt, "entered_at": "昨天"}, False),
        ],
        "receipt-v1": [
            ("好样本", good_receipt, True),
            ("skipped 缺失（不是空数组）", {k: v for k, v in good_receipt.items() if k != "skipped"}, False),
            ("release_status 不是待放行", {**good_receipt, "disposition": {
                "state": "PASS", "layer": "DP1", "release_status": "已放行"}}, False),
            ("state 枚举外", {**good_receipt, "disposition": {
                "state": "OK", "layer": "DP1", "release_status": "待放行"}}, False),
            ("step 旧字段名 input_digest/elapsed_ms 必须拒绝", {
                **good_receipt,
                "steps": [{"name": "normalize", "input_digest": "d1",
                           "output_digest": "d2", "elapsed_ms": 1}]}, False),
            ("step 名枚举外", {**good_receipt, "steps": [
                {"name": "loop", "input_summary": "d",
                 "output_summary": "d", "duration_ms": 1}]}, False),
            ("skipped.reason 用了「提前停」（第一阶段不存在）", {**good_receipt, "skipped": [
                {"step": "judge", "reason": "early_stop"}]}, False),
            ("缺必填 skill_hash", {k: v for k, v in good_receipt.items() if k != "skill_hash"}, False),
            ("额外字段", {**good_receipt, "extra": 1}, False),
        ],
        "review-ir-v1": [
            ("好样本", good_ir, True),
            ("source_ir_version 缺失（R1 要求必填）",
             {k: v for k, v in good_ir.items() if k != "source_ir_version"}, False),
            ("coverage_state 枚举外", {**good_ir, "coverage": {
                **good_ir["coverage"], "coverage_state": "mostly"}}, False),
            ("release_status 不是待放行", {**good_ir, "decision": {
                **good_ir["decision"], "release_status": "已放行"}}, False),
            ("content_unit_ref.kind=ad_text", {**good_ir, "content_unit_ref": {
                "unit_id": "u-ad", "kind": "ad_text", "parse_status": "ok"}}, True),
            ("content_unit_ref.kind=structured_json", {**good_ir, "content_unit_ref": {
                "unit_id": "u-json", "kind": "structured_json", "parse_status": "ok"}}, True),
            ("content_unit_ref.kind 未知", {**good_ir, "content_unit_ref": {
                "unit_id": "u-bad", "kind": "hologram", "parse_status": "ok"}}, False),
            ("content_unit_ref 缺 unit_id", {**good_ir, "content_unit_ref": {
                "kind": "free_text", "parse_status": "ok"}}, False),
            ("parse_status=failed 却无 failure_kind", {**good_ir, "decision": {
                **good_ir["decision"], "state": "未审查"}, "content_unit_ref": {
                "unit_id": "u-1", "kind": "landing_page", "parse_status": "failed"}}, False),
            ("缺必填 receipt_ref", {k: v for k, v in good_ir.items() if k != "receipt_ref"}, False),
        ],
        "business-command-batch-v1": [
            ("好样本", good_command, True),
            ("缺 actor", {k: v for k, v in good_command.items() if k != "actor"}, False),
            ("actor 缺 tenant", {**good_command, "actor": {"principal_id": "ou-reviewer"}}, False),
            ("authority_seq=0", {**good_command, "authority_seq": 0}, False),
            ("expected_version=-1", {**good_command, "expected_version": -1}, False),
            ("未知 command", {**good_command, "command": "sign"}, False),
            ("缺 request_sha256", {k: v for k, v in good_command.items() if k != "request_sha256"}, False),
            ("额外字段", {**good_command, "secret": "no"}, False),
        ],
        "projection-status-v1": [
            ("好样本", good_projection, True),
            ("未知 status", {**good_projection, "status": "ok"}, False),
            ("authority seq 负数", {**good_projection, "authority": {
                **good_projection["authority"], "seq": -1}}, False),
            ("projection applied_seq 负数", {**good_projection, "projection": {
                **good_projection["projection"], "applied_seq": -1}}, False),
            ("lag_commits 负数", {**good_projection, "lag_commits": -1}, False),
            ("缺 last_error_code", {k: v for k, v in good_projection.items()
                                      if k != "last_error_code"}, False),
            ("额外路径泄漏字段", {**good_projection, "data_path": "/secret"}, False),
        ],
    }


# ═══════════════════════════ 行为断言（schema 表达不了的）═══════════════════════════

def skill_channel_problems(receipt: dict, declared: dict) -> list:
    """B-10 判据的纯函数面：receipt 的 skill_id/version/hash 必须等于
    调用方声明的 skill 身份。回执写假值 / 常量 fallback / unknown 顶账，
    通道一断这里就必须非空 —— --controls 用它喂坏样本。"""
    problems = []
    if not isinstance(receipt, dict):
        return ["receipt 必须是 dict，收到 %s" % type(receipt).__name__]
    for k in ("skill_id", "skill_version", "skill_hash"):
        want = declared.get(k)
        got = receipt.get(k)
        if got != want:
            problems.append("receipt.%s=%r != 调用方声明的 %r" % (k, got, want))
    return problems


def receipt_id_pair_problems(id1, id2) -> list:
    """B-11 判据的纯函数面：两次运行的 receipt_id 必须各自存在、互不相同、
    形如哈希（不许是常量）。--controls 用它喂「两次同 id」的坏样本。"""
    problems = []
    for label, rid in (("第一次", id1), ("第二次", id2)):
        if not isinstance(rid, str) or not rid:
            problems.append("%s的 receipt_id 为空或不是字符串：%r" % (label, rid))
            continue
        if len(rid) < 8:
            problems.append("%s的 receipt_id 形如常量（长度 %d）：%r"
                            % (label, len(rid), rid))
    if isinstance(id1, str) and id1 and id1 == id2:
        problems.append("两次运行 receipt_id 相同：%r（id 没有跟着运行开始时刻走）" % id1)
    return problems


def check_behavior(schemas: dict) -> list:
    """
    这几条约束在本校验器的关键字支持范围内**表达不了**，所以由本函数做行为断言。

    ★ 2026-10-18 变异审计抓到过一次假绿：初版的 B-1…B-4 测的是函数内现写的局部 helper，
      与被测的 `contracts/*.schema.json` **零连接** —— 把 schemas 清空仍全绿。
      现在四条全部**从 schema 里读出判据**，schema 删掉对应结构即红。
    """
    out = []

    def ok(cid, cond, detail):
        out.append({"id": cid, "ok": bool(cond), "detail": detail})

    def dig(schema, *path):
        cur = schema
        for p in path:
            if isinstance(cur, dict):
                cur = cur.get(p)
            elif isinstance(cur, list):
                cur = cur[p] if isinstance(p, int) and p < len(cur) else None
            else:
                return None
        return cur

    # ── B-1 五步齐全：判据来自 receipt-v1 的 steps.items.name.enum ──
    enum = dig(schemas.get("receipt-v1"), "properties", "steps", "items",
               "properties", "name", "enum") or []
    need = set(enum)
    good_steps = [{"name": n} for n in enum]
    missing_one = [s for s in good_steps if s != good_steps[0]] if good_steps else []

    def five_steps_ok(steps) -> bool:
        return {s.get("name") for s in steps if isinstance(s, dict)} == need

    ok("B-1", bool(need) and five_steps_ok(good_steps) and not five_steps_ok(missing_one),
       f"五步判据取自 receipt-v1 的 enum={sorted(need)}；缺一步须 False")

    # ── B-2 finding_id 唯一：判据来自 review-ir-v1 的 findings.items 定义 ──
    fid_schema = dig(schemas.get("review-ir-v1"), "properties", "findings",
                     "items", "properties", "finding_id") or {}
    fid_required = "finding_id" in (dig(schemas.get("review-ir-v1"), "properties",
                                        "findings", "items", "required") or [])

    def ids_unique(fs) -> bool:
        ids = [f.get("finding_id") for f in fs if isinstance(f, dict) and f.get("finding_id")]
        return len(ids) == len(set(ids))

    f1 = {"finding_id": "f-1"}
    ok("B-2", bool(fid_schema) and fid_required
       and ids_unique([f1]) and not ids_unique([f1, dict(f1)]),
       f"finding_id 在 schema 中存在且 required={fid_required}；两条同 id 须 False")

    # ── B-3 confirmed 必须有 authority_state：判据来自 review-ir-v1 ──
    as_schema = dig(schemas.get("review-ir-v1"), "properties", "findings",
                    "items", "properties", "authority_state") or {}
    as_enum = set(as_schema.get("enum") or [])

    def confirmed_has_authority(fs) -> bool:
        return all(("authority_state" in f) for f in fs
                   if isinstance(f, dict) and f.get("status") == "confirmed")

    ok("B-3", bool(as_schema) and bool(as_enum)
       and confirmed_has_authority([{"status": "confirmed", "authority_state": "ok"}])
       and not confirmed_has_authority([{"status": "confirmed"}]),
       f"authority_state 在 schema 中且 enum={sorted(as_enum)}；confirmed 无它须 False")

    # ── B-4 accepted 必须带 ir_id：判据来自 attempt-v1 的 allOf 里那条 if/then ──
    allof = dig(schemas.get("attempt-v1"), "allOf") or []
    has_accepted_guard = False
    for sub in allof:
        if not isinstance(sub, dict):
            continue
        cond = dig(sub, "if", "properties", "outcome", "const")
        then_required = dig(sub, "then", "required") or []
        if cond == "accepted" and "ir_id" in then_required:
            has_accepted_guard = True
            break

    ok("B-4", has_accepted_guard,
       "attempt-v1 的 allOf 里有「accepted → 必须 ir_id」的条件守卫"
       + ("" if has_accepted_guard else "（**没有** —— schema 被改窄了）"))

    # ── B-5 rule_key 按 produced_by 逐条分流：判据来自 review-ir-v1 的
    #        findings.items.allOf 里那两条 if/then ────────────────────────
    #
    # ★ 这一条的两个坑，都是 2026-10-20 实测撞出来的：
    #   ① 条件**必须**下沉到 items.allOf。写成顶层 allOf + contains 时，
    #      「只要有一条是 rule 型，全部 finding 都要带 rule_key」—— 混合数组必被误拒。
    #      （我第一版就是这么写的，12 组正反例里「混合 rule+semantic」那一项当场红。）
    #   ② semantic/human 的 rule_key 必须是 null，不能借别的规则的键 ——
    #      它们没有规则身份，填了就是编。
    #
    # 所以下面的断言**不查文本，直接跑 validate**：正样本必须过、坏样本必须拒。
    # 这与 B-1…B-4「从 schema 读结构」是同一纪律：schema 改坏就红。
    ir_schema = schemas.get("review-ir-v1") or {}
    # 条件可以放在两处，两处都要认：
    #   (a) 顶层 allOf[] 的某个成员里 → properties.findings.items.allOf
    #   (b) findings.items 自己的 allOf 里
    # 只要任意一处有「produced_by 分流 rule_key」的 if/then，就算结构在。
    # ★ 不认同顶层 allOf 里直接挂 if/then（不带 properties）的写法 ——
    #   那种写法作用在整个数组上，就是下面要挡的那个 bug。
    cand = [dig(ir_schema, "properties", "findings", "items", "allOf") or []]
    for sub in (ir_schema.get("allOf") or []):
        cand.append(dig(sub, "properties", "findings", "items", "allOf") or [])
    item_allof = [x for lst in cand for x in lst]

    def _is_rule_branch(s) -> bool:
        return (dig(s, "if", "properties", "produced_by", "const") == "rule"
                and "rule_key" in (dig(s, "then", "required") or []))

    def _is_nonrule_branch(s) -> bool:
        enum = dig(s, "if", "properties", "produced_by", "enum") or []
        return (set(enum) >= {"semantic", "human"}
                and dig(s, "then", "properties", "rule_key", "type") == "null")

    def _rk_case(findings) -> bool:
        """构造一份最小合规 IR，塞入给定 findings，返回「是否通过校验」。"""
        base = {
            "ir_id": "ir-rk", "ir_version": "v1", "source_ir_version": "v1",
            "content_unit_ref": {"unit_id": "u-rk", "kind": "free_text", "parse_status": "ok"},
            "findings": list(findings),
            "decision": {"state": "REVIEW", "layer": "DP3",
                         "release_status": "待放行", "obligations": []},
            "coverage": {"coverage_state": "full", "modalities_evaluated": ["text"],
                         "rules_version": "r1", "control_points_applied": ["H01"]},
            "receipt_ref": "rc-rk", "rule_snapshot": "r1", "kb_snapshot": "k1",
            "control_points_version": "cp-2026-10-18-v2",
            "created_at": "2026-10-20T00:00:00Z",
        }
        return not validate(base, ir_schema, "$", [])

    def _f(**kw):
        f = {"finding_id": "f1", "control_code": "H01", "status": "candidate",
             "severity": "L3", "produced_by": "rule", "derived_from": None,
             "rule_key": "T1.1.medical-cure"}
        f.update(kw)
        return f

    rk_checks = [
        # 正样本：这些必须过
        ("rule+非空键", [_f()], True),
        ("semantic+null", [_f(produced_by="semantic", rule_key=None)], True),
        ("human+null", [_f(produced_by="human", rule_key=None)], True),
        ("空数组", [], True),
        # ★ 混合数组：这一项抓的就是「条件写在顶层」那个 bug
        ("混合 rule+semantic", [_f(),
                                _f(finding_id="f2", produced_by="semantic", rule_key=None)], True),
        # 坏样本：这些必须被拒
        ("rule+null键", [_f(rule_key=None)], False),
        ("rule+缺键", [{k: v for k, v in _f().items() if k != "rule_key"}], False),
        ("semantic+借键", [_f(produced_by="semantic", rule_key="T9.x")], False),
        ("混合里 rule 缺键", [_f(), _f(finding_id="f2", produced_by="rule", rule_key=None)], False),
    ]
    rk_bad = []
    for name, fs, want in rk_checks:
        got = _rk_case(fs)
        if got != want:
            rk_bad.append(f"{name}（期望{'过' if want else '拒'}，实际{'过' if got else '拒'}）")

    ok("B-5", bool(item_allof) and not rk_bad,
       "rule_key 按 produced_by 逐条分流"
       + ("" if not rk_bad else f"；{len(rk_bad)} 项不符：" + "、".join(rk_bad))
       + ("" if item_allof else "（findings.items.allOf 缺失 —— 条件被挪到顶层了？）"))

    # ── B-6 projection fresh 恒等式：字段合法还不够 ──
    ps = schemas.get("projection-status-v1") or {}
    good_ps = samples().get("projection-status-v1", [])[0][1]

    def projection_consistent(value) -> bool:
        if not isinstance(value, dict):
            return False
        authority = value.get("authority") or {}
        projection = value.get("projection") or {}
        if value.get("status") == "fresh":
            return (authority.get("seq") == projection.get("applied_seq")
                    and authority.get("manifest_sha256") ==
                    projection.get("manifest_sha256")
                    and value.get("lag_commits") == 0
                    and value.get("last_error_code") is None)
        return True

    bad_ps = {**good_ps,
              "projection": {**good_ps["projection"], "manifest_sha256": "c" * 64}}
    ok("B-6", bool(ps) and projection_consistent(good_ps)
       and not projection_consistent(bad_ps),
       "fresh 必须 authority.seq/hash == projection.applied_seq/hash 且 lag=0；坏样本须 False")

    # ── B-7 ReviewIR 的 ContentUnit kind 与 ContentUnit schema 同域（另含 unsupported 文档） ──
    ir_kinds = set(dig(schemas.get("review-ir-v1"), "properties", "content_unit_ref",
                       "properties", "kind", "enum") or [])
    content_schema_path = CONTRACTS.parent / "base" / "content-unit-v1.schema.json"
    try:
        content_schema = json.loads(content_schema_path.read_text(encoding="utf-8"))
        content_kinds = set(dig(content_schema, "properties", "source", "properties",
                                "kind", "enum") or [])
    except (OSError, ValueError):
        content_kinds = set()
    ok("B-7", bool(content_kinds) and content_kinds <= ir_kinds
       and {"ad_text", "structured_json"} <= ir_kinds,
       "ReviewIR content_unit_ref.kind 覆盖 ContentUnit 全部 kind；ad_text/structured_json 不漏")

    # ── B-8 真实 judge_entry 产出的图片 ReviewIR 必须过 schema ──
    try:
        from base import contract as content_contract
        from base.judge_entry import judge_unit as production_judge
        image_unit = content_contract.from_media(
            "image", b"contract-image", "hospital grade breast pump",
            uri="inline:contract-image", extractor="contract-test",
            covers=["图内文字"], does_not_cover=["画面语义"])
        image_unit["parse_status"] = "ok"
        judged = production_judge(image_unit, clock=lambda: 1000)
        real_ir = judged["ir"]
        real_receipt = judged["receipt"]
        real_errors = validate(real_ir, schemas["review-ir-v1"])
        receipt_errors = validate(real_receipt, schemas["receipt-v1"])
    except Exception as exc:  # noqa: BLE001
        real_errors = ["%s: %s" % (type(exc).__name__, exc)]
        receipt_errors = list(real_errors)
    ok("B-8", not real_errors,
       "真实 judge_entry 图片 ReviewIR 喂 schema：%s" %
       ("通过" if not real_errors else real_errors[:3]))
    ok("B-9", not receipt_errors,
       "真实 judge_entry 图片 receipt 喂 schema：%s" %
       ("通过" if not receipt_errors else receipt_errors[:3]))

    # ── B-10 receipt.skill_hash 必须等于**实际加载的 skill**（验收行 15 子判据）──
    #
    # ★ 2026-10-24 变异复查 #15a 抓到的假绿：schema 只要求 skill_hash 是
    #   非空 string，B-9 喂的 receipt 用的是**生产回执自己的值** ——
    #   把生产 receipt 的 skill_hash 换成假值后 80 项仍全过（自比恒真）。
    #   修法：receipt 的 skill_hash 必须与**调用方声明**的 skill 身份对拍 ——
    #   judge_unit(skill_id=…, skill_hash=…) 的回执必须原样带出这两个值；
    #   同时 skill_id / skill_version 也一并按「请求 → 回执」的通道核一遍
    #   （同一行判据的「skill_version 等于实际加载的 skill」半边）。
    b10_bad = []
    try:
        from base import contract as _cc
        from base.judge_entry import judge_unit as _judge
        _sk_args = dict(skill_id="contract-check-skill", skill_version="9.9",
                        skill_hash="contract-check-hash-777")
        _u = _cc.from_text("skill_hash 通道对拍样本", uri="inline:b10")
        _u["parse_status"] = "ok"
        _r = _judge(_u, clock=lambda: 1000, **_sk_args)["receipt"]
        b10_bad = skill_channel_problems(_r, _sk_args)
    except Exception as exc:  # noqa: BLE001
        b10_bad = ["%s: %s" % (type(exc).__name__, exc)]
    ok("B-10", not b10_bad,
       "receipt.skill_id/version/hash 必须原样带出调用方声明的 skill 身份：%s"
       % ("通过" if not b10_bad else b10_bad[:2]))

    # ── B-11 同一输入连跑两次 receipt_id 必须不同（验收行 15 末句）──
    #
    # ★ 2026-10-24 变异复查 #15b 抓到的假绿：receipt_id 固定成常量后 80 项
    #   仍全过 —— 脚本只跑一次 judge，从不比较两次执行的 receipt_id。
    #   ★ 判据的机制面：receipt_id 由「运行开始时刻」参与派生 ——
    #   两次运行必有不同的 started，所以必有不同的 id。
    #   实测修正：用**恒定时钟**（clock=lambda: 1000）两次 id 相同是幂等，
    #   不是缺陷 —— 真代码下同刻同 id。所以这里注入**递增时钟**：
    #   两次运行的 started 必然不同 → id 必须不同。常量变异（#15b）
    #   会把「id 跟着运行走」砍断，这里当场红。
    b11_bad = []
    try:
        from base import contract as _cc2
        from base.judge_entry import judge_unit as _judge2
        _u2 = _cc2.from_text("receipt_id 唯一性样本", uri="inline:b11")
        _u2["parse_status"] = "ok"
        _ticks = iter(range(1, 10_000))
        _r1 = _judge2(_u2, clock=lambda: next(_ticks))["receipt"]
        _r2b = _judge2(_u2, clock=lambda: next(_ticks))["receipt"]
        b11_bad = receipt_id_pair_problems(_r1.get("receipt_id"),
                                           _r2b.get("receipt_id"))
    except Exception as exc:  # noqa: BLE001
        b11_bad = ["%s: %s" % (type(exc).__name__, exc)]
    ok("B-11", not b11_bad,
       "两次运行的 receipt_id 必须不同（started 参与派生；恒时钟同 id 是幂等不算红）：%s"
       % ("通过" if not b11_bad else b11_bad[:2]))

    return out

def run_controls() -> int:
    """--controls：B-10 / B-11 新断言的反向对照。坏样本必须红、好样本必须绿
    （§2.4.1：没红过的断言不算验证过它 —— 判据自己要先被喂红一次）。"""
    good_declared = {"skill_id": "s", "skill_version": "1", "skill_hash": "abc"}

    def ok_receipt():
        # 与 samples().good_receipt 同构的最小 receipt
        return {
            "receipt_id": "rc-" + "a" * 16,
            "skill_id": good_declared["skill_id"],
            "skill_version": good_declared["skill_version"],
            "skill_hash": good_declared["skill_hash"],
        }

    checks = []

    def check(cid, cond, detail=""):
        checks.append((cid, bool(cond), detail))

    # B-10 面：声明与回执一致 → 绿；写假值 / 顶 unknown → 红
    check("C-B10a 通道一致必须绿（不误报）",
          not skill_channel_problems(ok_receipt(), good_declared))
    fake = ok_receipt()
    fake["skill_hash"] = "fake-skill-hash"          # #15a 的变异形状
    check("C-B10b receipt.skill_hash 写假值必须红",
          bool(skill_channel_problems(fake, good_declared)))
    unknowned = ok_receipt()
    unknowned["skill_id"] = "unknown"               # 生产 fallback 的顶账形状
    check("C-B10c skill_id 顶 unknown 必须红",
          bool(skill_channel_problems(unknowned, good_declared)))
    missing = ok_receipt()
    del missing["skill_version"]
    check("C-B10d skill_version 缺失必须红",
          bool(skill_channel_problems(missing, good_declared)))

    # B-11 面：两次不同且形如哈希 → 绿；常量 / 撞 id → 红
    check("C-B11a 两次不同 id 必须绿（不误报）",
          not receipt_id_pair_problems("rc-1a2b3c4d5e6f7a8b",
                                       "rc-9f8e7d6c5b4a3210"))
    check("C-B11b 两次同 id 必须红",                # #15b 的变异形状
          bool(receipt_id_pair_problems("rc-fixed-constant", "rc-fixed-constant")))
    check("C-B11b2 常量 id（长度不足）必须红",
          bool(receipt_id_pair_problems("rc-1", "rc-2")))
    check("C-B11c 空 id 必须红",
          bool(receipt_id_pair_problems(None, "rc-9f8e7d6c5b4a3210")))

    reds = [c for c in checks if not c[1]]
    print("=" * 60)
    print("--controls · verify_contracts 新断言反向对照")
    print("=" * 60)
    for cid, okc, detail in checks:
        print("  %s %-40s %s" % ("✓" if okc else "✗", cid, detail))
    if reds:
        print("❌ %d/%d 红" % (len(reds), len(checks)), file=sys.stderr)
        return 1
    print("✅ %d/%d 全过（坏样本红、好样本不误报）" % (len(checks), len(checks)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--controls", action="store_true",
                    help="新断言（B-10/B-11）的反向对照：坏样本必须红")
    args = ap.parse_args()
    if args.controls:
        return run_controls()

    # 读 schema
    loaded, read_errors = {}, []
    for name in SCHEMAS:
        p = CONTRACTS / f"{name}.schema.json"
        if not p.exists():
            read_errors.append(f"{p.name} 不存在")
            continue
        try:
            loaded[name] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            read_errors.append(f"{p.name} 读不出：{e}")

    if read_errors:
        msg = "；".join(read_errors)
        if args.json:
            print(json.dumps({"verdict": "untested", "detail": msg}, ensure_ascii=False, indent=1))
        else:
            print(f"⚠ 未测：{msg} —— 未测不是通过", file=sys.stderr)
        return 2

    checks = []

    # ① schema 自检
    for name in SCHEMAS:
        checks += check_schema_shape(name, loaded[name])

    # ② 正/负样本
    for name, cases in samples().items():
        schema = loaded[name]
        for label, doc, want_ok in cases:
            errs = validate(doc, schema)
            got_ok = not errs
            checks.append({
                "id": f"{name}",
                "ok": got_ok == want_ok,
                "detail": f"{label} → 期望{'过' if want_ok else '拒'}，实际{'过' if got_ok else '拒'}"
                          + ("" if got_ok == want_ok else f"；错误={errs[:2]}"),
            })

    # ③ 行为断言
    checks += check_behavior(loaded)

    reds = [c for c in checks if not c["ok"]]
    exit_code = 1 if reds else 0

    if args.json:
        print(json.dumps({"checks": checks, "reds": reds,
                          "verdict": "red" if reds else "ok", "exit_code": exit_code},
                         ensure_ascii=False, indent=1))
        return exit_code

    print("=" * 66)
    print("契约 schema 校验（attempt-v1 / receipt-v1 / review-ir-v1）")
    print("=" * 66)
    print(f"  校验器支持的关键字：{', '.join(SUPPORTED)}")
    print(f"  不支持：minContains / 数组内唯一 / oneOf / anyOf / $ref —— 相关约束改行为断言")
    print()
    for c in checks:
        print(f"  {'✓' if c['ok'] else '✗'} {c['id']:<22} {c['detail']}")
    print()
    if reds:
        print(f"✗ {len(reds)} 项红 / 共 {len(checks)} 项")
        return 1
    print(f"✅ {len(checks)} 项全过（正样本过、负样本拒、行为断言双向成立）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
