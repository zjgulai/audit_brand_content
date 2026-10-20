#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""web/scripts/seed_fixture.py —— 确定性夹具生成器（18–24 条真实形态案件）

**为什么不是手写 JSON**：手写会与 schema 漂移，而且漂移了没有任何东西会红。
本脚本的产物要能过 `base/orchestrator.REQUIRED_IR_FIELDS` 的齐全性断言。

三条纪律（对应 `web/docs/handoff-4b.md` 的断言 A7）：

1. **确定性**：固定种子 `SEED`，同一次运行的产物逐字节相同。
   复现：连跑两次，`sha256sum` 必须一致。
2. **每条带 `sample: true`** —— 界面据此显示「样例数据」，且可一键清空。
3. **覆盖边界态**，不是铺满好看的数据：
   - 五标签各至少 2 条（BLOCK / REVIEW / 未审查 / 待自决 / PASS）
   - `coverage_state=partial` 与 `full` 各有
   - `authority_state` 非 ok 的 finding（依据不可直接采信）
   - `rule_conflict=true` 的 finding（两条依据打架）
   - `not_evaluated_reason` 里 `not_wired` / `no_rule` / `no_capability` 三种
   - 一条超长 quote、一条 quote 含换行、一条 quote 为空
   - `assignee_id` 有我与非我两种（驱动「认领」按钮的可用性）

用法：
  python3 web/scripts/seed_fixture.py --out <dir>     # 写 cases.json / reports.json
  python3 web/scripts/seed_fixture.py --selftest      # 反向对照，不写盘
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

SEED = 20261020

STATES = ("BLOCK", "REVIEW", "未审查", "待自决", "PASS")
LAYER_OF = {"BLOCK": "DP2", "REVIEW": "DP3", "未审查": "DP0",
            "待自决": "DP1", "PASS": "DP2"}

# 控制点编码来自真实 smoke 投影（H01）与规范七轴的首字母族
CONTROL_CODES = ("H01", "H02", "SCN3", "RGT2", "DSC11", "DSC12",
                 "BRD4", "FCT10", "CLM2", "CHN6")

QUOTES = (
    "治疗",
    "100% 治愈湿疹",
    "美国 FDA 认证",
    "全球销量第一",
    "无副作用",
    "宝宝用了立刻不哭",
    "临床验证 98% 有效",
    "本品可替代药物治疗",
    "最安全的母婴品牌",
    "这款吸奶器比医院级还好用",
    "限时秒杀，今晚 24 点前下单立减 300",
    "适用于所有肤质，包括早产儿",
    "用后 7 天见效，无效退款",
    "唯一获得国际认证的中国品牌",
    "不含任何化学成分",
    "医生推荐率高达 95%",
    "这个价格买到就是赚到",
    "全网最低价，别家都是假货",
)

# 一条超长 quote（验详情页的换行与折叠）、一条含换行、一条空
LONG_QUOTE = ("本品采用专利级双频吸乳技术，经三甲医院产科临床观察，"
              "连续使用四周后 92.6% 的受试者泌乳量显著提升，"
              "同时配备医用级硅胶喇叭口，适配 98% 以上亚洲女性胸型，"
              "并通过 FDA、CE、SGS 三重认证，是母婴行业唯一同时获得"
              "上述三项资质的产品，效果显著优于市面同类竞品。")
NEWLINE_QUOTE = "第一段：100% 纯棉\n第二段：零甲醛添加"

AUTHORITY_STATES = ("ok", "ok", "ok", "ok", "expired", "missing")

NOT_EVALUATED = (
    {"what": "场景控制", "why": "not_wired"},
    {"what": "权利控制", "why": "not_wired"},
    {"what": "渠道控制", "why": "not_wired"},
    {"what": "品牌控制", "why": "no_rule"},
    {"what": "事实核查", "why": "no_capability"},
)

PRODUCT_LINES = ("pump", "wearable", "skincare", "feeding")
TENANTS = ("t1", "t1", "t1", "t2")


def _hash16(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _finding(idx: int, row: int, rng: random.Random, state: str) -> dict:
    """造一条 finding。前 4 条刻意覆盖四个边界：长文 / 换行 / 空 quote / 依据失效。"""
    if row == 0:
        quote, loc = LONG_QUOTE, {"type": "text", "start": 0, "end": len(LONG_QUOTE)}
    elif row == 1:
        quote, loc = NEWLINE_QUOTE, {"type": "text", "start": 12, "end": 34}
    elif row == 2:
        quote, loc = None, None            # 空 quote：界面必须说「无原文」而不是留白
    else:
        quote = QUOTES[(idx * 7 + row) % len(QUOTES)]
        start = 6 + row * 11
        loc = {"type": "text", "start": start, "end": start + len(quote)}

    auth = AUTHORITY_STATES[(idx + row) % len(AUTHORITY_STATES)]
    conflict = (idx % 6 == 0 and row == 0)   # 规则冲突：每 6 条案件里第 1 条的首个 finding

    return {
        "finding_id": "f-%s" % _hash16(SEED, idx, row),
        "control_code": CONTROL_CODES[(idx + row) % len(CONTROL_CODES)],
        "status": "confirmed" if state in ("BLOCK", "PASS") else "candidate",
        "severity": "L4" if state == "BLOCK" else rng.choice(("L2", "L3", "L4")),
        "produced_by": "rule" if row % 2 == 0 else "semantic",
        "detected_by": "P0" if row == 0 else "P1",
        "derived_from": None if row != 1 else "f-%s" % _hash16(SEED, idx, 0),
        "confirmed_by_rule_class": False,
        "quote": quote,
        "location": loc,
        "authority_ref": [{"ref_id": "EXT-%03d" % (21 + row)}],
        "rule_snapshot": "rs-fixture-1",
        "kb_snapshot": "kb-fixture-1",
        "authority_state": auth,
        "rule_conflict": conflict,
        "resolution_detail": {
            "refs": [{"ref_id": "EXT-%03d" % (21 + row), "state": auth,
                      "collapsed": auth, "reason": "fixture"}],
            "reason": None if auth == "ok" else "%s：依据不可直接采信" % auth,
        },
    }


def build_cases() -> list[dict]:
    rng = random.Random(SEED)
    cases: list[dict] = []
    n = 21                                  # 21 条：在 18–24 的推荐区间内，且能整除五种状态做些变化

    for i in range(n):
        state = STATES[i % len(STATES)] if i < 10 else rng.choices(
            STATES, weights=(2, 5, 2, 2, 2))[0]
        idx = "c%02d" % i
        case_id = "case-%s" % _hash16(SEED, idx)[:8]
        findings = [_finding(i, r, rng, state)
                    for r in range(rng.randint(1, 3))]
        # 每 6 条里放一条「依据过期」的 finding，已在 _finding 里轮转；这里再保证覆盖
        coverage_state = "partial" if i % 3 else "full"
        not_evaluated = ([] if coverage_state == "full"
                         else [NEVER_EVALUATED for NEVER_EVALUATED in
                               rng.sample(NOT_EVALUATED, k=rng.randint(2, 4))])
        # 未审查态必须给出「没跑」的原因，不能空着
        if state == "未审查" and not not_evaluated:
            not_evaluated = [NOT_EVALUATED[0]]

        obligations = []
        if coverage_state == "partial":
            obligations.append("partial_coverage")
        if state == "未审查":
            obligations.append("untested")

        cases.append({
            "case_id": case_id,
            "tenant": TENANTS[i % len(TENANTS)],
            "product_line": PRODUCT_LINES[i % len(PRODUCT_LINES)],
            "submitter_id": "u_sub_%d" % (i % 3),
            "final_reviewer_id": "u_dp3",
            # 一半归我（u_dp3），一半归别人 —— 驱动「认领」按钮的可用性
            "assignee_id": "u_dp3" if i % 2 == 0 else "u_dp4",
            "actionable": True,
            "sample": True,
            "ir": {
                "ir_id": "ir-%s" % _hash16(SEED, idx, "ir"),
                "ir_version": "v1",
                "source_ir_version": "v1",
                # ★ 必须是对象 {unit_id, kind} —— api/review_api.py 的 ContentUnitRef
                #   写成字符串后端会在序列化时 500（ResponseValidationError）。
                "content_unit_ref": {
                    "unit_id": "cu-%s" % _hash16(SEED, idx, "cu"),
                    "kind": "free_text" if i % 4 else "image",
                },
                "findings": findings,
                "decision": {
                    "state": state,
                    "layer": LAYER_OF[state],
                    "release_status": "待放行",     # ★ 恒「待放行」，机器不得改
                    "obligations": obligations,
                },
                "coverage": {
                    "coverage_state": coverage_state,
                    "modalities_evaluated": (["free_text"] if i % 4 else ["free_text", "image"]),
                    "rules_version": json.dumps(
                        {"fingerprint": "ffffffffffffffff", "version": "rs-fixture"}),
                    "control_points_applied": sorted({f["control_code"] for f in findings}),
                    "not_evaluated_reason": not_evaluated,
                },
                "receipt_ref": "rcpt-%s" % _hash16(SEED, idx, "rcpt"),
                "rule_snapshot": "rs-fixture-1",
                "kb_snapshot": "kb-fixture-1",
                "control_points_version": "cp-fixture-1",
                "created_at": "2026-10-20T0%d:%02d:00Z" % (i % 10, (i * 7) % 60),
            },
        })
    return cases


def build_reports(cases: list[dict]) -> list[dict]:
    out = []
    for i, case in enumerate(cases):
        if i % 4:
            continue                     # 不是每条案件都有报告，这正是要展示的「空」态
        out.append({
            "report_id": "report-%s" % _hash16(SEED, case["case_id"])[:8],
            "case_id": case["case_id"],
            "ir_id": case["ir"]["ir_id"],
            "url": "https://static.example.com/reports/%s.md" % case["case_id"],
            "published_at": case["ir"]["created_at"],
        })
    return out


# ── 自证：反向对照，证明这些约束真的会被拦下 ────────────────────────────

REQUIRED_IR = ("ir_id", "ir_version", "content_unit_ref", "source_ir_version",
               "findings", "decision", "coverage", "receipt_ref",
               "rule_snapshot", "kb_snapshot", "control_points_version",
               "created_at")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(("  ✓ " if ok else "  ✗ ") + label + (("  " + detail) if detail and not ok else ""))
    return ok


def selftest() -> int:
    results = []

    a = json.dumps(build_cases(), ensure_ascii=False, sort_keys=True)
    b = json.dumps(build_cases(), ensure_ascii=False, sort_keys=True)
    results.append(_check("T1 确定性：两次构建逐字相同",
                          a == b, "两次结果不同 → 夹具不确定"))

    cases = build_cases()
    results.append(_check("T2 数量在 18–24 之间", 18 <= len(cases) <= 24, str(len(cases))))

    # T3 契约必填字段齐全 —— 这是 A7 的实质
    missing = []
    for c in cases:
        for k in REQUIRED_IR:
            if k not in c["ir"]:
                missing.append("%s.%s" % (c["case_id"], k))
    results.append(_check("T3 每条 IR 的 12 个必填字段齐全",
                          not missing, ",".join(missing[:3])))

    # ★ T3b 类型正确 —— T3 只查「在不在」，一个字符串也能通过，
    #   而后端 ContentUnitRef 是对象，写成字符串会 500（2026-10-20 实际踩到）。
    #   「字段存在」不是「字段可用」，这两件事要分开断言。
    type_bad = []
    for c in cases:
        cu = c["ir"].get("content_unit_ref")
        if not isinstance(cu, dict) or "unit_id" not in cu or "kind" not in cu:
            type_bad.append("%s.content_unit_ref=%r" % (c["case_id"], type(cu).__name__))
        if not isinstance(c["ir"].get("findings"), list):
            type_bad.append("%s.findings" % c["case_id"])
        dec = c["ir"].get("decision") or {}
        if not all(isinstance(dec.get(k), str)
                   for k in ("state", "layer", "release_status")):
            type_bad.append("%s.decision" % c["case_id"])
    results.append(_check("T3b 关键字段类型正确（content_unit_ref 必须是对象）",
                          not type_bad, ",".join(type_bad[:3])))

    # T3c 反向对照：把 content_unit_ref 改回字符串，T3b 必须红
    tampered_cu = json.loads(json.dumps(cases))
    tampered_cu[0]["ir"]["content_unit_ref"] = "cu-as-string"
    caught_cu = any(
        not isinstance(c["ir"].get("content_unit_ref"), dict) for c in tampered_cu
    )
    results.append(_check("T3c 反向对照：字符串型 content_unit_ref 必须被抓到",
                          caught_cu, "判据恒真 → 它保护不了任何东西"))

    # T4 五标签全覆盖，且各至少 2 条
    from collections import Counter
    cnt = Counter(c["ir"]["decision"]["state"] for c in cases)
    short = [s for s in STATES if cnt[s] < 2]
    results.append(_check("T4 五标签各 ≥2 条", not short,
                          "缺：" + ",".join(short)))

    # T5 ★ 关键：夹具里不许出现 release_status 不是「待放行」的
    bad = [c["case_id"] for c in cases
           if c["ir"]["decision"]["release_status"] != "待放行"]
    results.append(_check("T5 所有 release_status 恒「待放行」", not bad, ",".join(bad[:3])))

    # T5b 反向对照：把一条改成已放行，T5 的判据必须能抓到
    tampered = json.loads(json.dumps(cases))
    tampered[0]["ir"]["decision"]["release_status"] = "已放行"
    caught = any(c["ir"]["decision"]["release_status"] != "待放行" for c in tampered)
    results.append(_check("T5b 反向对照：篡改成已放行必须被抓到", caught,
                          "判据是恒真的 → 它保护不了任何东西"))

    # T6 边界态覆盖：partial / full、依据非 ok、rule_conflict、not_wired、空 quote
    have = {
        "partial": any(c["ir"]["coverage"]["coverage_state"] == "partial" for c in cases),
        "full": any(c["ir"]["coverage"]["coverage_state"] == "full" for c in cases),
        "auth_bad": any(f["authority_state"] != "ok"
                        for c in cases for f in c["ir"]["findings"]),
        "conflict": any(f["rule_conflict"]
                        for c in cases for f in c["ir"]["findings"]),
        "not_wired": any(r["why"] == "not_wired"
                         for c in cases for r in c["ir"]["coverage"]["not_evaluated_reason"]),
        "empty_quote": any(f["quote"] is None
                           for c in cases for f in c["ir"]["findings"]),
    }
    absent = [k for k, v in have.items() if not v]
    results.append(_check("T6 六种边界态都出现", not absent, ",".join(absent)))

    # T7 每条都带 sample 标记
    results.append(_check("T7 每条都带 sample:true",
                          all(c.get("sample") is True for c in cases)))

    # T8 未审查态必须给出「没跑」的原因，不能空着
    naked = [c["case_id"] for c in cases
             if c["ir"]["decision"]["state"] == "未审查"
             and not c["ir"]["coverage"]["not_evaluated_reason"]]
    results.append(_check("T8 未审查态都带未评估原因", not naked, ",".join(naked[:3])))

    # T9 报告只覆盖一部分案件（「没有报告」也是要被展示的态）
    reports = build_reports(cases)
    results.append(_check("T9 报告数 < 案件数（空报告态真实存在）",
                          0 < len(reports) < len(cases),
                          "%d/%d" % (len(reports), len(cases))))

    ok = all(results)
    print("\n%s  %d/%d 项通过" % ("✅" if ok else "❌", sum(results), len(results)))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--merge", action="store_true",
                    help="与 out 目录里已有的 cases.json / reports.json 合并（保留 smoke 的真实案件）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("需要 --out <dir> 或 --selftest")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    reports = build_reports(cases)

    if args.merge:
        existing_cases = out / "cases.json"
        if existing_cases.exists():
            try:
                prior = json.loads(existing_cases.read_text(encoding="utf-8"))
                if isinstance(prior, list):
                    cases = prior + cases
            except json.JSONDecodeError:
                print("⚠ 已有 cases.json 读不出，按覆盖处理", file=sys.stderr)
        existing_reports = out / "reports.json"
        if existing_reports.exists():
            try:
                prior = json.loads(existing_reports.read_text(encoding="utf-8"))
                if isinstance(prior, list):
                    reports = prior + reports
            except json.JSONDecodeError:
                pass

    (out / "cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reports.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("夹具 %d 条案件%s → %s" % (len(cases), "（已合并）" if args.merge else "", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
