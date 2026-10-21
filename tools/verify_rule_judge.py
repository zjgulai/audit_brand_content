#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_rule_judge.py —— `base/control_points.py` + `base/rule_judge.py` 的判据（T1-04）

## 它验什么

  A **控制点注册表**：只接受 `status=active`；deprecated / 未知码拒收；暴露 table_version。
  B **规则判定**：只产 P0 字面命中；命中带 control_code / 位置 / 逐字片段 / severity；
    severity 必须是 `L*`（P0 是检测层，不是严重度）；quote 必须 == text[start:end]。
  C **边界**：只产命中，不产 candidate / state / layer / obligations；不写回执、不查依据。
  D **反向对照**：未知码、deprecated 码、severity 写成 P 值、quote 与切片不符 —— 必须红。
  E **不是恒拒/恒过**：正常文本有命中；无关文本 0 命中；禁用规则不产命中。
  F **规则守卫**：exclude_patterns 只删重叠 span；require_context 是 OR 前置；
    三类表达式都在装载时预编译；当前真实 enabled 规则输出零变化。

## 退出码

  0 全过 · 1 有红 · 2 未测（读不到真实数据文件 / 建不出临时目录）

## 口径

  - 使用真实 `research/governance/control-points-v1.json` 与
    `research/governance/skeleton/rules-v1.json` 的**只读子集**；
  - 不联网、不写仓内文件；临时 fixture 全部落在临时目录；
  - 「quote == 切片」由本脚本独立重算，不信被测模块自报。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

CP_PATH = os.path.join(ROOT, "research", "governance", "control-points-v1.json")
RULES_PATH = os.path.join(ROOT, "research", "governance", "skeleton", "rules-v1.json")

try:
    from control_points import (
        ControlPointRegistry, UnknownControlCode, DeprecatedControlCode)
    from rule_judge import (
        RuleJudge, InvalidSeverity, validate_hit, HIT_FIELDS)
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/control_points.py / base/rule_judge.py 失败：%s" % e)
    sys.exit(1)

EXPECTED_HIT_FIELDS = {
    "control_code", "rule_key", "start", "end", "quote", "severity", "detected_by",
}


def main():
    try:
        TMP = tempfile.mkdtemp(prefix="rulejudge_")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    # ── A 控制点注册表 ────────────────────────────────────────────────
    try:
        reg = ControlPointRegistry(CP_PATH)
    except Exception as e:  # noqa: BLE001
        print("⚠ 未测：读不到真实控制点主表（%s）" % e)
        return 2

    cp_raw = json.load(open(CP_PATH, encoding="utf-8"))
    active = {c["control_code"] for c in cp_raw["control_points"]
              if c.get("status") == "active"}
    deprecated = {c["control_code"] for c in cp_raw["control_points"]
                  if c.get("status") != "active"}
    T("A1 table_version == JSON 实值",
      reg.table_version == cp_raw.get("table_version"), str(reg.table_version))
    T("A2 active_codes() 恰好等于 JSON 里 status=active 的集合",
      set(reg.active_codes()) == active, "%s vs %s" % (sorted(reg.active_codes()), sorted(active)))
    T("A3 已知 active 码可取", reg.get_active("H01")["control_code"] == "H01", "")
    dep = sorted(deprecated)[0] if deprecated else None
    if dep:
        try:
            reg.get_active(dep)
            T("A4 deprecated 码必须拒收", False, "未拒收 %s" % dep)
        except DeprecatedControlCode:
            T("A4 deprecated 码必须拒收", True, "")
    else:
        T("A4 deprecated 码必须拒收", False, "真实主表里没有非 active 码，无法验证")
    try:
        reg.get_active("ZZZ_NOT_A_CODE")
        T("A5 未知码必须拒收", False, "未拒收")
    except UnknownControlCode:
        T("A5 未知码必须拒收", True, "")
    T("A6 deprecated 码不在 active_codes 里",
      dep is None or dep not in set(reg.active_codes()), str(dep))

    # ── B 规则判定 ────────────────────────────────────────────────────
    try:
        judge = RuleJudge(reg, RULES_PATH)
    except Exception as e:  # noqa: BLE001
        print("⚠ 未测：读不到真实规则快照（%s）" % e)
        return 2

    text = "Our formula can cure disease and treat symptoms. 这款产品可以治疗疾病，治愈患者。"
    hits = judge.judge(text)
    T("B1 有命中", len(hits) > 0, "n=%d" % len(hits))
    T("B2 命中字段恰好 7 个（不夹带 state/layer/candidate）",
      all(set(h.keys()) == EXPECTED_HIT_FIELDS for h in hits),
      str(sorted({tuple(sorted(h.keys())) for h in hits})))
    T("B3 每条命中 detected_by=P0",
      all(h.get("detected_by") == "P0" for h in hits), "")
    T("B4 每条命中 severity 是 L0–L5",
      all(isinstance(h.get("severity"), str) and len(h["severity"]) == 2
          and h["severity"][0] == "L" and h["severity"][1] in "012345" for h in hits),
      str([h.get("severity") for h in hits]))
    T("B5 quote == text[start:end]（逐字切片）",
      all(h["quote"] == text[h["start"]:h["end"]] for h in hits),
      str([(h["start"], h["end"], h["quote"]) for h in hits]))
    T("B6 位置合法且 quote 非空",
      all(0 <= h["start"] < h["end"] <= len(text) and h["quote"] for h in hits), "")
    T("B7 命中含 H01（疾病治疗）", any(h["control_code"] == "H01" for h in hits),
      str(sorted({h["control_code"] for h in hits})))
    T("B8 中文关键词也命中（治疗 / 治愈）",
      any(h["quote"] in ("治疗", "治愈") for h in hits),
      str([h["quote"] for h in hits]))
    T("B9 H01 的 severity 与规则快照一致（L4）",
      all(h["severity"] == "L4" for h in hits if h["control_code"] == "H01"),
      str([h["severity"] for h in hits if h["control_code"] == "H01"]))
    T("B10 规则快照 sha256 可复算",
      judge.rule_snapshot_sha256 == hashlib.sha256(open(RULES_PATH, "rb").read()).hexdigest(),
      str(judge.rule_snapshot_sha256))

    # 无关文本 0 命中（不是恒过/恒拦的反向对照）
    clean = "新品上市：售价 199 元，容量 240ml，适合 0-6 个月宝宝。"
    T("B11 无关文本 0 命中", judge.judge(clean) == [], str(judge.judge(clean)))

    # control_code 过滤：只跑指定码，且未知码拒收
    mixed = "can cure disease，也能预防乳腺炎"
    only_h02 = judge.judge(mixed, control_codes={"H02"})
    T("B12 control_codes 过滤生效（有 H02 命中且返回码只有 H02）",
      len(only_h02) > 0 and all(h["control_code"] == "H02" for h in only_h02),
      str(only_h02))
    try:
        judge.judge(text, control_codes={"ZZZ_NOT_A_CODE"})
        T("B13 过滤里带未知码 → 拒", False, "未拒")
    except UnknownControlCode:
        T("B13 过滤里带未知码 → 拒", True, "")

    # 禁用规则不产命中：T6.3（U02，enabled=false）的关键词是 HSA/FSA/保险
    T("B14 禁用规则不产命中（HSA/保险）", judge.judge("HSA eligible，保险可报销") == [],
      str(judge.judge("HSA eligible，保险可报销")))

    # 确定性
    T("B15 同一输入连跑两次结果一致", judge.judge(text) == hits, "")

    # 输入可以是 ContentUnit（只读 text），结果与直接传 str 一致
    T("B16 接受 ContentUnit dict（只读 text）", judge.judge({"text": text}) == hits, "")
    try:
        judge.judge({"unit_id": "x"})
        T("B16b ContentUnit 缺 text → 明确报错", False, "未报错")
    except TypeError:
        T("B16b ContentUnit 缺 text → 明确报错", True, "")

    # 规则快照只读：判定前后文件 sha 不变
    sha_before = hashlib.sha256(open(RULES_PATH, "rb").read()).hexdigest()
    judge.judge(text)
    sha_after = hashlib.sha256(open(RULES_PATH, "rb").read()).hexdigest()
    T("B17 判定不写规则快照（前后 sha 相同）", sha_before == sha_after, "")

    # ── C 只产命中：不许出现 candidate / state / layer ────────────────
    forbidden = ("candidate", "state", "layer", "obligations", "receipt", "authority")
    T("C1 命中对象里没有越界字段",
      all(not (set(h) & set(forbidden)) for h in hits), str(forbidden))

    # ── D 反向对照：坏样本必须红 ─────────────────────────────────────
    def write_rules(name, rules):
        p = os.path.join(TMP, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"rules": rules}, f, ensure_ascii=False)
        return p

    base_rule = {
        "rule_key": "T.x.fixture",
        "parent_rule": "H01",
        "modality": "review",
        "severity": "L2",
        "match": {"keywords": ["治愈"], "patterns": []},
    }

    # D1 severity 写成 P 值 → 装载即拒
    bad = dict(base_rule, severity="P0")
    try:
        RuleJudge(reg, write_rules("bad_sev.json", [bad]))
        T("D1 severity=P0 → 装载必须拒", False, "未拒")
    except InvalidSeverity:
        T("D1 severity=P0 → 装载必须拒", True, "")

    # D2 deprecated 码 → 拒
    bad = dict(base_rule, parent_rule=dep or "U02")
    try:
        RuleJudge(reg, write_rules("bad_dep.json", [bad]))
        T("D2 deprecated 码 → 装载必须拒", False, "未拒")
    except DeprecatedControlCode:
        T("D2 deprecated 码 → 装载必须拒", True, "")

    # D3 未知码 → 拒
    bad = dict(base_rule, parent_rule="ZZZ_NOT_A_CODE")
    try:
        RuleJudge(reg, write_rules("bad_unknown.json", [bad]))
        T("D3 未知码 → 装载必须拒", False, "未拒")
    except UnknownControlCode:
        T("D3 未知码 → 装载必须拒", True, "")

    # D4 permit 规则不参与判定，也不因 parent 不是控制点而拒
    permit = dict(base_rule, rule_key="T.x.permit", parent_rule="安全词",
                  modality="permit", severity="L0",
                  match={"keywords": ["hospital"], "patterns": []})
    try:
        jp = RuleJudge(reg, write_rules("permit.json", [permit]))
        T("D4 permit 规则被跳过（不因未知 parent 拒载）",
          jp.judge("hospital") == [], str(jp.judge("hospital")))
    except Exception as e:  # noqa: BLE001
        T("D4 permit 规则被跳过（不因未知 parent 拒载）", False, repr(e))

    # D5 伪造命中：quote 与切片不符 → validate_hit 必须报错
    good = dict(hits[0]) if hits else {
        "control_code": "H01", "rule_key": "x", "start": 0, "end": 1,
        "quote": text[:1], "severity": "L4", "detected_by": "P0"}
    bad = dict(good, quote=good["quote"] + "X")
    T("D5 quote 与切片不符 → validate_hit 必须报错",
      validate_hit(bad, text) != [], str(validate_hit(bad, text)))

    # D6 伪造命中：severity=P0 → 必须报错
    bad = dict(good, severity="P0")
    T("D6 severity=P0 的命中 → validate_hit 必须报错",
      validate_hit(bad, text) != [], str(validate_hit(bad, text)))

    # D7 伪造命中：越界位置 → 必须报错
    bad = dict(good, start=len(text) + 1, end=len(text) + 2)
    T("D7 越界位置 → validate_hit 必须报错",
      validate_hit(bad, text) != [], str(validate_hit(bad, text)))

    # D8 合法命中 → validate_hit 通过（反向对照：不是恒拒）
    T("D8 合法命中 → validate_hit 通过", validate_hit(good, text, reg) == [],
      str(validate_hit(good, text, reg)))

    # D9 HIT_FIELDS 恰好与判据里的字段表一致（名字出现过 ≠ 拦得住）
    T("D9 HIT_FIELDS 与判据表一致", set(HIT_FIELDS) == EXPECTED_HIT_FIELDS,
      str(sorted(HIT_FIELDS)))

    # ── F exclude/context 守卫 + 真实语料零变化 ────────────────────────
    raw_rules = json.load(open(RULES_PATH, encoding="utf-8"))["rules"]
    guarded = [row for row in raw_rules
               if (row.get("match") or {}).get("exclude_patterns")
               or (row.get("match") or {}).get("require_context")]
    T("F1 真实快照恰有 5 条 guard 规则，且全部 disabled",
      len(guarded) == 5 and all(row.get("enabled") is False for row in guarded),
      repr([(row.get("rule_key"), row.get("enabled")) for row in guarded]))

    # 旧匹配语义（只 keywords/patterns），限定当前真正装载的 enabled 非 permit 规则。
    # guard 五条全 disabled 时，新旧输出必须逐条相等。
    def legacy_hits(text_value, allow=None):
        rows = []
        for raw_rule in raw_rules:
            if raw_rule.get("enabled") is False or raw_rule.get("modality") == "permit":
                continue
            if allow is not None and raw_rule.get("parent_rule") not in allow:
                continue
            match = raw_rule.get("match") or {}
            spans = []
            for keyword in match.get("keywords") or []:
                spans.extend((m.start(), m.end()) for m in
                             re.compile(re.escape(keyword), re.I | re.U).finditer(text_value)
                             if m.end() > m.start())
            for pattern in match.get("patterns") or []:
                spans.extend((m.start(), m.end()) for m in
                             re.compile(pattern, re.I | re.U).finditer(text_value)
                             if m.end() > m.start())
            spans = sorted(set(spans), key=lambda item: (item[0], -(item[1] - item[0])))
            chosen, last_end = [], -1
            for start, end in spans:
                if start < last_end:
                    continue
                chosen.append((start, end))
                last_end = end
            for start, end in chosen:
                rows.append({
                    "control_code": raw_rule["parent_rule"],
                    "rule_key": raw_rule["rule_key"],
                    "start": start, "end": end, "quote": text_value[start:end],
                    "severity": raw_rule["severity"], "detected_by": "P0",
                })
        rows.sort(key=lambda h: (h["start"], h["control_code"], h["rule_key"], h["end"]))
        return rows

    from contract import units_from_corpus
    ads, pages = units_from_corpus()
    changed = []
    before_hit_count = 0
    after_hit_count = 0
    before_digest = hashlib.sha256()
    after_digest = hashlib.sha256()
    for unit_value in ads + pages:
        before = legacy_hits(unit_value["text"])
        after = judge.judge(unit_value)
        before_hit_count += len(before)
        after_hit_count += len(after)
        before_bytes = json.dumps(
            {"unit_id": unit_value["unit_id"], "hits": before},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        after_bytes = json.dumps(
            {"unit_id": unit_value["unit_id"], "hits": after},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        before_digest.update(before_bytes + b"\n")
        after_digest.update(after_bytes + b"\n")
        if before_bytes != after_bytes:
            changed.append(unit_value["unit_id"])
    before_sha = before_digest.hexdigest()
    after_sha = after_digest.hexdigest()
    zero_change_detail = (
        "units=%d before_hits=%d after_hits=%d changed_units=%d "
        "before_sha256=%s after_sha256=%s" %
        (len(ads) + len(pages), before_hit_count, after_hit_count, len(changed),
         before_sha, after_sha))
    T("F2 接线前后真实 ContentUnit 输出逐字节相等",
      not changed and len(ads) + len(pages) == 427
      and before_hit_count == after_hit_count and before_sha == after_sha,
      zero_change_detail + " changed=%r" % changed[:3])
    print("  · F2 零变化读数：%s" % zero_change_detail)

    exclude_rule = copy.deepcopy(base_rule)
    exclude_rule["rule_key"] = "T.x.exclude"
    exclude_rule["match"] = {
        "keywords": ["clinical"], "patterns": [],
        "exclude_patterns": [r"clinical\s+(trial|study)"],
    }
    ex_judge = RuleJudge(reg, write_rules("exclude.json", [exclude_rule]))
    T("F3 只含被排除片段 → 0 命中",
      ex_judge.judge("clinical trial") == [],
      repr(ex_judge.judge("clinical trial")))
    mixed_text = "clinical trial；另一处 clinical benefit"
    ex_hits = ex_judge.judge(mixed_text)
    T("F4 同文被排除片段 + 真命中 → 只保留真命中",
      len(ex_hits) == 1 and ex_hits[0]["quote"] == "clinical"
      and ex_hits[0]["start"] == mixed_text.rfind("clinical"), repr(ex_hits))

    context_rule = copy.deepcopy(base_rule)
    context_rule["rule_key"] = "T.x.context"
    context_rule["match"] = {
        "keywords": ["slim"], "patterns": [],
        "require_context": ["postpartum", "belly band"],
    }
    ctx_judge = RuleJudge(reg, write_rules("context.json", [context_rule]))
    T("F5 缺全部 context 词 → 0 命中", ctx_judge.judge("slim design") == [], "")
    ctx_hits = ctx_judge.judge("Postpartum slim design")
    T("F6 命中任一 context 字面词 → 主规则命中",
      len(ctx_hits) == 1 and ctx_hits[0]["quote"].lower() == "slim", repr(ctx_hits))

    compiled = ex_judge.rules[0]
    T("F7 keywords/patterns/exclude/context 均在装载时预编译",
      all(isinstance(rx, re.Pattern) for name in (
          "keywords", "patterns", "exclude_patterns", "require_context")
          for rx in compiled[name]), repr({k: len(compiled[k]) for k in compiled
                                           if isinstance(compiled[k], list)}))

    for name, mutate, marker in (
        ("exclude 非数组", lambda rule: rule["match"].update(
            {"exclude_patterns": "clinical"}), "exclude_patterns"),
        ("context 含非字符串", lambda rule: rule["match"].update(
            {"require_context": [1]}), "require_context"),
        ("exclude 坏正则", lambda rule: rule["match"].update(
            {"exclude_patterns": ["("]}), "exclude_pattern"),
    ):
        bad_rule = copy.deepcopy(base_rule)
        mutate(bad_rule)
        try:
            RuleJudge(reg, write_rules("bad_guard_%s.json" % marker, [bad_rule]))
            rejected = False
        except Exception as exc:  # noqa: BLE001
            rejected = marker in str(exc)
        T("F8 %s → 装载拒绝" % name, rejected, "")

    # ── 结论 ────────────────────────────────────────────────────────
    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_rule_judge %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
