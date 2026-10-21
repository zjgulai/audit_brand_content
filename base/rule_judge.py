#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/rule_judge.py —— 规则判定：只产 P0 字面命中（T1-04）

## 职责边界（技术方案 §2 #6）

  - 读规则快照的**字面部分**（keywords / patterns / exclude_patterns /
    require_context），对 ContentUnit.text 做匹配；
  - 每条命中：`control_code / rule_key / start / end / quote / severity / detected_by`；
  - `detected_by` 恒为 `P0`（检测层：正则/关键词 —— **不是严重度**）；
  - `severity` 恒为规则快照里的 `L0–L5`；
  - `quote` 必须逐字等于 `text[start:end]`（由切片生成，并在 `validate_hit` 里复核）。

## 不做什么

  - 不产 candidate（semantic_judge）；不判 state / layer / obligations（decision_table）；
  - 不写回执、不查权威依据（evidence_sync）、不写 finding_store；
  - 不裁决提前停（第一阶段没有 stop gate）。
  - **permit 规则不参与判定**：它不是违规命中，也没有可归属的控制点；
  - `enabled=false` 的规则不装载、不产命中（停用规则不参与判定）。

## 口径

  - 关键词与 require_context 按 `re.IGNORECASE` 字面匹配；pattern / exclude_patterns
    按快照原样编译（同样忽略大小写）。
  - require_context 是规则级 OR 前置条件；exclude_patterns 只删除与其区间重叠的
    候选 span，同一文本里其他真命中仍保留。
  - 同一条规则内，重叠匹配只保留「起点最早、同起点最长」的那一个；
    不同规则之间不去重（它们属于不同控制点，各自都是独立命中）。
  - 快照只读：构造时算 `rule_snapshot_sha256`，运行期不写回。
"""
from __future__ import annotations

import hashlib
import json
import os
import re

DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research", "governance", "skeleton", "rules-v1.json")

# 命中对象的**恰好**字段：多一个（state/layer/candidate）都是越界。
HIT_FIELDS = (
    "control_code", "rule_key", "start", "end", "quote", "severity", "detected_by",
)

SEVERITY_RE = re.compile(r"^L[0-5]$")


class RuleJudgeError(Exception):
    pass


class InvalidSeverity(RuleJudgeError):
    pass


class InvalidRuleSnapshot(RuleJudgeError):
    pass


def _compile_rule(rule, registry):
    """校验并编译一条规则；返回内部结构。permit / disabled 由调用方先跳过。"""
    if not isinstance(rule, dict):
        raise InvalidRuleSnapshot("rules 里出现非对象")
    rule_key = rule.get("rule_key")
    if not isinstance(rule_key, str) or not rule_key:
        raise InvalidRuleSnapshot("rule_key 缺失或非字符串")
    code = rule.get("parent_rule")
    if not isinstance(code, str) or not code:
        raise InvalidRuleSnapshot("%s: parent_rule 缺失" % rule_key)
    registry.get_active(code)  # 未知 / deprecated 在这里抛

    severity = rule.get("severity")
    if not isinstance(severity, str) or not SEVERITY_RE.match(severity):
        # ★ 这里刻意点名 P 值：P0–P3 是检测层，不是严重度。
        raise InvalidSeverity(
            "%s: severity=%r 非法；必须是 L0–L5（P0 是检测层，不是严重度）"
            % (rule_key, severity))

    match = rule.get("match")
    if not isinstance(match, dict):
        raise InvalidRuleSnapshot("%s: match 缺失或不是对象" % rule_key)
    keywords = match.get("keywords", [])
    patterns = match.get("patterns", [])
    exclude_patterns = match.get("exclude_patterns", [])
    require_context = match.get("require_context", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) and k for k in keywords):
        raise InvalidRuleSnapshot("%s: match.keywords 必须是字符串数组" % rule_key)
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise InvalidRuleSnapshot("%s: match.patterns 必须是字符串数组" % rule_key)
    if not isinstance(exclude_patterns, list) or not all(
            isinstance(p, str) and p for p in exclude_patterns):
        raise InvalidRuleSnapshot(
            "%s: match.exclude_patterns 必须是非空字符串数组" % rule_key)
    if not isinstance(require_context, list) or not all(
            isinstance(item, str) and item for item in require_context):
        raise InvalidRuleSnapshot(
            "%s: match.require_context 必须是非空字符串数组" % rule_key)

    kw_res = [re.compile(re.escape(k), re.IGNORECASE | re.UNICODE) for k in keywords]
    ctx_res = [re.compile(re.escape(item), re.IGNORECASE | re.UNICODE)
               for item in require_context]

    def compile_patterns(values, field):
        compiled = []
        for value in values:
            try:
                compiled.append(re.compile(value, re.IGNORECASE | re.UNICODE))
            except re.error as exc:
                raise InvalidRuleSnapshot(
                    "%s: %s 编译失败（%s）：%r" %
                    (rule_key, field, exc, value)) from exc
        return compiled

    pat_res = compile_patterns(patterns, "pattern")
    exclude_res = compile_patterns(exclude_patterns, "exclude_pattern")

    return {
        "rule_key": rule_key,
        "control_code": code,
        "severity": severity,
        "keywords": kw_res,
        "patterns": pat_res,
        "exclude_patterns": exclude_res,
        "require_context": ctx_res,
    }


class RuleJudge(object):
    def __init__(self, registry, rules_path=None):
        self.registry = registry
        self.rules_path = os.path.abspath(rules_path or DEFAULT_RULES_PATH)
        with open(self.rules_path, "rb") as f:
            raw = f.read()
        self.rule_snapshot_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise InvalidRuleSnapshot("规则快照不是合法 JSON：%s" % e)
        rules = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(rules, list):
            raise InvalidRuleSnapshot("规则快照缺少 rules 数组")

        self.rules = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise InvalidRuleSnapshot("rules 里出现非对象")
            # 停用规则不装载；permit 不是违规命中，也不装载。
            if rule.get("enabled") is False:
                continue
            if rule.get("modality") == "permit":
                continue
            self.rules.append(_compile_rule(rule, registry))

    def judge(self, text_or_unit, control_codes=None):
        """返回命中列表。`text_or_unit` 可以是 str，或含 `text` 的 ContentUnit dict。"""
        if isinstance(text_or_unit, dict):
            text = text_or_unit.get("text")
        else:
            text = text_or_unit
        if not isinstance(text, str):
            raise TypeError("judge 需要 str 或含 text 的 ContentUnit dict")

        allow = None
        if control_codes is not None:
            allow = set(control_codes)
            for code in allow:
                self.registry.get_active(code)  # 未知 / deprecated 在这里抛

        hits = []
        for rule in self.rules:
            code = rule["control_code"]
            if allow is not None and code not in allow:
                continue
            if rule["require_context"] and not any(
                    rx.search(text) for rx in rule["require_context"]):
                continue
            excluded = [
                (match.start(), match.end())
                for rx in rule["exclude_patterns"] for match in rx.finditer(text)
                if match.end() > match.start()
            ]
            spans = []
            for rx in rule["keywords"]:
                for m in rx.finditer(text):
                    if m.end() > m.start():
                        spans.append((m.start(), m.end()))
            for rx in rule["patterns"]:
                for m in rx.finditer(text):
                    if m.end() > m.start():
                        spans.append((m.start(), m.end()))
            # 排除式只删除与其区间重叠的候选 span，不删除整条规则。
            spans = [
                (start, end) for start, end in spans
                if not any(start < ex_end and ex_start < end
                           for ex_start, ex_end in excluded)
            ]
            # 同规则内去重叠：起点最早优先；同起点取最长。
            spans = sorted(set(spans), key=lambda se: (se[0], -(se[1] - se[0])))
            chosen = []
            last_end = -1
            for s, e in spans:
                if s < last_end:
                    continue
                chosen.append((s, e))
                last_end = e
            for s, e in chosen:
                hits.append({
                    "control_code": code,
                    "rule_key": rule["rule_key"],
                    "start": s,
                    "end": e,
                    "quote": text[s:e],
                    "severity": rule["severity"],
                    "detected_by": "P0",
                })
        hits.sort(key=lambda h: (h["start"], h["control_code"], h["rule_key"], h["end"]))
        return hits


def validate_hit(hit, text, registry=None):
    """复核一条命中；返回错误列表（空 = 通过）。

    这是「quote == text[start:end]」「severity 不许写成 P 值」两条断言的执行点。
    """
    errs = []
    if not isinstance(hit, dict):
        return ["not_object"]
    keys = set(hit.keys())
    want = set(HIT_FIELDS)
    if keys != want:
        errs.append("fields:missing=%s extra=%s" % (sorted(want - keys), sorted(keys - want)))
        return errs  # 字段都不对，后面的检查没有意义

    if not isinstance(hit.get("control_code"), str) or not hit["control_code"]:
        errs.append("bad_control_code")
    if not isinstance(hit.get("rule_key"), str) or not hit["rule_key"]:
        errs.append("bad_rule_key")
    s, e = hit.get("start"), hit.get("end")
    if not (isinstance(s, int) and not isinstance(s, bool)
            and isinstance(e, int) and not isinstance(e, bool)):
        errs.append("bad_span_type")
    elif not (0 <= s < e <= len(text)):
        errs.append("span_out_of_range:%r..%r(len=%d)" % (s, e, len(text)))
    elif hit.get("quote") != text[s:e]:
        errs.append("quote_mismatch")
    sev = hit.get("severity")
    if not isinstance(sev, str) or not SEVERITY_RE.match(sev):
        # 点名 P 值，便于坏样本一眼看懂
        if isinstance(sev, str) and re.match(r"^P[0-3]$", sev):
            errs.append("severity_is_p_layer:%r（P0–P3 是检测层，不是严重度）" % sev)
        else:
            errs.append("bad_severity:%r" % (sev,))
    if hit.get("detected_by") != "P0":
        errs.append("detected_by_not_P0:%r" % (hit.get("detected_by"),))

    if registry is not None and isinstance(hit.get("control_code"), str):
        try:
            registry.get_active(hit["control_code"])
        except Exception as ex:  # noqa: BLE001
            errs.append("control_code_not_active:%s" % ex)
    return errs
