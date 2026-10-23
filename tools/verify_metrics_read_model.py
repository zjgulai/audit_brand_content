#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_metrics_read_model.py —— `base/metrics_read_model.py` 的判据（T1-14）

## 它验什么

  A **四个指标各自七要素**：numerator / denominator / window / sampling_layer /
    min_n / status / target 全部存在；每个比率带 n。
  B **未测不是 0**：数据源抛异常/读不出 → status=`未测`、分子分母为 None、
    ratio=None；不是 0、不是 N/A、不是空白。
  C **样本不足**：n < 最低 n → status=`样本不足`、ratio=None、仍显示 n。
  D **抽样层**：召回要求 PASS/待自决/REVIEW/未审查 四层分别抽样；
    误判要求 BLOCK 全量复核，未复核完 → `未测` + 已复核占比，不出比率。
  E **分母口径**：未覆盖分子只算 UNASSESSED，不含 CLEAN-CANDIDATE、
    ERROR、fetch_error；推翻率分母含申诉胜与败。
  F **目标线**：target 为 None/待基线，不得写死数值。
  G **确定性**：同一数据两次结果一致。
  H **边界与分子口径（#81/#83/#84 补票）**：
    · #81/#84 —— MIN_N 边界成对样本：分母 29 → `样本不足` 且无比率，
      分母 30 → ok 且给比率（只喂 n=10 查不出 29/30 边界）；
    · #83 —— MIN_N_UNCOVERED 边界：未覆盖分母=1 必须给比率，不许「样本不足」；
    · #84 —— 推翻率分子只计人工与机器**结论不同**的条数（标准集金标 46/48；
      分子口径改成 == 曾全绿，46→2 无人拦）。
  X **反向对照（--controls）**：上面每条判据各配变异形状（必须判假）与
    正常形状（必须判真）—— 判据自己没红过不算验证过它。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）；
  `--controls` 跑离线反向对照（同一退出码口径）。
"""
from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from metrics_read_model import MetricsReadModel
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/metrics_read_model.py 失败：%s" % e)
    sys.exit(1)

SEVEN = ["numerator", "denominator", "window", "sampling_layer", "min_n", "status", "target"]


def sample_insufficient(m):
    """#81/#84 判据的「样本不足」形状：status、分子分母 n 与无比率，一次说清。"""
    return (m.get("status") == "样本不足" and m.get("ratio") is None
            and m.get("n") == m.get("denominator"))


def gives_ratio(m):
    """边界另一侧：ok 且真的给出比率数值。"""
    return (m.get("status") == "ok" and isinstance(m.get("ratio"), float))


def case(**over):
    c = {
        "case_id": "c", "state": "PASS", "run_state": "OK", "failure_kind": None,
        "machine_max_sev": "none", "human_max_sev": None, "review_completed": True,
        "machine_conclusion": "PASS", "human_conclusion": None,
        "appeal_result": None, "clean_candidate": False,
    }
    c.update(over)
    return c


def dataset():
    cases = []
    # 40 条人工金标准 L4：32 条机器也判 L4（召回命中），8 条机器判 L2（漏报）
    for i in range(40):
        machine_l4 = i < 32
        state = ["PASS", "待自决", "REVIEW", "未审查"][i % 4]
        cases.append(case(
            case_id="gold_%d" % i, state=state,
            machine_max_sev="L4" if machine_l4 else "L2",
            human_max_sev="L4", review_completed=True,
            machine_conclusion=state,
            human_conclusion="BLOCK" if machine_l4 else "PASS",
            appeal_result="won" if i % 2 == 0 else "lost",
        ))
    # 8 条机器判 L4、人工撤销（误判分子）；都在 BLOCK 层
    for i in range(8):
        cases.append(case(
            case_id="fp_%d" % i, state="BLOCK", machine_max_sev="L4",
            human_max_sev="L2", review_completed=True,
            machine_conclusion="BLOCK", human_conclusion="PASS",
            appeal_result="won" if i % 2 else "lost",
        ))
    # 2 条机器 L4 未复核：不得进误判分子/分母
    for i in range(2):
        cases.append(case(
            case_id="unrev_%d" % i, state="BLOCK", machine_max_sev="L4",
            human_max_sev=None, review_completed=False,
            machine_conclusion="BLOCK", human_conclusion=None,
        ))
    # 未覆盖分子：10 条未审查（非 ERROR / 非 fetch_error）
    for i in range(10):
        cases.append(case(case_id="unassessed_%d" % i, state="未审查",
                          failure_kind="parse_error", machine_conclusion="未审查"))
    # 不计入分子：2 条 fetch_error、2 条 ERROR、3 条 CLEAN-CANDIDATE
    for i in range(2):
        cases.append(case(case_id="fetch_%d" % i, state="未审查",
                          failure_kind="fetch_error", machine_conclusion="未审查"))
    for i in range(2):
        cases.append(case(case_id="error_%d" % i, state=None, run_state="ERROR",
                          machine_conclusion=None))
    for i in range(3):
        cases.append(case(case_id="clean_%d" % i, state="PASS",
                          clean_candidate=True, machine_conclusion="PASS"))
    return cases


def coverage(**over):
    c = {
        "sampled_layers": ["PASS", "待自决", "REVIEW", "未审查"],
        "block_review_complete": True,
        "block_total": 42,
        "block_reviewed": 42,
    }
    c.update(over)
    return c


def loader(cases=None, cov=None, raises=False, raw=None):
    def load(window):
        if raises:
            raise RuntimeError("source down")
        if raw is not None:
            return raw
        return {"cases": dataset() if cases is None else cases,
                "coverage": coverage() if cov is None else cov}
    return load


def main():
    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    # ── A 四指标七要素 + 主读数 ────────────────────────────────────
    out = MetricsReadModel(loader()).compute("2026-10")
    ms = out.get("metrics", {})
    T("A1 四个指标都存在",
      set(ms) == {"recall_l4_l5", "false_positive_l4_l5",
                  "uncovered_ratio", "human_overturn_rate"}, str(sorted(ms)))
    for mid, m in ms.items():
        T("A2 %s 七要素齐全" % mid, all(k in m for k in SEVEN), str(sorted(m)))
        T("A2b %s 带 n 且 n==denominator" % mid,
          "n" in m and m.get("n") == m.get("denominator"), "%r / %r" % (m.get("n"), m.get("denominator")))
        T("A2c %s target 为 None/待基线" % mid,
          m.get("target") is None and m.get("target_status") == "待基线",
          "%r / %r" % (m.get("target"), m.get("target_status")))
        T("A2d %s window 透传" % mid, m.get("window") == "2026-10", str(m.get("window")))

    recall = ms["recall_l4_l5"]
    T("A3 召回：40 条人工 L4，32 条机器命中 → 32/40",
      recall.get("numerator") == 32 and recall.get("denominator") == 40
      and recall.get("status") == "ok" and abs(recall.get("ratio") - 0.8) < 1e-9, str(recall))
    T("A4 召回抽样层 = 非 BLOCK 四层",
      set(recall.get("sampling_layer") or []) == {"PASS", "待自决", "REVIEW", "未审查"},
      str(recall.get("sampling_layer")))
    fp = ms["false_positive_l4_l5"]
    T("A5 误判：40 条已复核机器 L4，8 条被撤销 → 8/40（2 条未复核不计）",
      fp.get("numerator") == 8 and fp.get("denominator") == 40
      and fp.get("status") == "ok" and abs(fp.get("ratio") - 0.2) < 1e-9, str(fp))
    unc = ms["uncovered_ratio"]
    # ★ 分子 = 全部 state=未审查 且非 ERROR/非 fetch_error 的条数；
    #   数据里 10 条显式未审查 + 10 条 gold 抽样层恰为未审查 = 20。
    T("A6 未覆盖：分子 20，分母 67（含 ERROR/fetch_error/CLEAN-CANDIDATE）",
      unc.get("numerator") == 20 and unc.get("denominator") == 67
      and unc.get("status") == "ok", str(unc))
    T("A7 未覆盖分子不含 CLEAN-CANDIDATE / ERROR / fetch_error",
      unc.get("numerator") == 20 and unc.get("clean_candidate_count") == 3
      and unc.get("error_count") == 2 and unc.get("fetch_error_count") == 2, str(unc))
    ov = ms["human_overturn_rate"]
    # 分母：有机器结论且有对应人工结论的条数 = 40 gold + 8 fp = 48
    T("A8 推翻率：分母 48，分子按人工/机器结论不同计",
      ov.get("denominator") == 48 and ov.get("status") == "ok", str(ov))
    T("A9 推翻率分母含申诉胜与败",
      (ov.get("appeal_won") or 0) > 0 and (ov.get("appeal_lost") or 0) > 0, str(ov))
    # ★ #84 补票：分子只计人工与机器**结论不同**的条数。上面 48 条合格样本里
    #   恰有 2 条结论相同（gold_0/gold_1：机器 PASS、人工 PASS 的那种组合没有 ——
    #   实为 gold 每条 机器=state vs 人工 BLOCK/PASS，下式金标由构造保证 46）。
    #   分子口径从 != 改成 == 曾让分子 46→2 仍全绿（A8 只断言分母与 status）。
    T("A8b 推翻率分子只计结论不同（金标 46/48）",
      ov.get("numerator") == 46, "numerator=%r（应为 46）" % (ov.get("numerator"),))

    # ── B 未测不是 0 ────────────────────────────────────────────────
    for cid, load in (("B1 数据源抛异常", loader(raises=True)),
                      ("B2 数据源返回 None", lambda window: None),
                      ("B3 数据源返回坏结构", loader(raw={"cases": "x", "coverage": {}}))):
        o = MetricsReadModel(load).compute("2026-10")
        ok = True
        for mid, m in o["metrics"].items():
            if not (m.get("status") == "未测" and m.get("numerator") is None
                    and m.get("denominator") is None and m.get("ratio") is None):
                ok = False
        T("%s → 四指标全为未测且分子分母为 None" % cid, ok, str(o["metrics"])[:300])

    T("B4 空 window → 未测", all(m["status"] == "未测"
      for m in MetricsReadModel(loader()).compute("")["metrics"].values()), "")

    # ── C 样本不足 ──────────────────────────────────────────────────
    small = [case(case_id="g%d" % i, state="REVIEW", machine_max_sev="L4",
                  human_max_sev="L4", machine_conclusion="REVIEW",
                  human_conclusion="BLOCK") for i in range(10)]
    o = MetricsReadModel(loader(cases=small, cov=coverage())).compute("2026-10")
    T("C1 召回 n=10 < 30 → 样本不足且无比率",
      o["metrics"]["recall_l4_l5"]["status"] == "样本不足"
      and o["metrics"]["recall_l4_l5"]["ratio"] is None
      and o["metrics"]["recall_l4_l5"]["n"] == 10, str(o["metrics"]["recall_l4_l5"]))
    T("C2 推翻率 n=10 < 30 → 样本不足",
      o["metrics"]["human_overturn_rate"]["status"] == "样本不足"
      and o["metrics"]["human_overturn_rate"]["ratio"] is None, str(o["metrics"]["human_overturn_rate"]))
    empty = MetricsReadModel(loader(cases=[], cov=coverage())).compute("2026-10")
    T("C3 n=0 → 不出百分比（未覆盖分母 0）",
      empty["metrics"]["uncovered_ratio"]["status"] != "ok"
      and empty["metrics"]["uncovered_ratio"]["ratio"] is None, str(empty["metrics"]["uncovered_ratio"]))

    # ── C4/C5 ★ #81/#83/#84 补票：MIN_N 29/30 与 MIN_N_UNCOVERED 1/2 边界 ──────
    # 只用 n=10 查不出 29/30 边界：MIN_N 30→29 曾全绿，n=29 直接出比率（违判据）。
    b29 = [case(case_id="b%d" % i, state="REVIEW", machine_max_sev="L4",
                human_max_sev="L4", machine_conclusion="REVIEW",
                human_conclusion="BLOCK") for i in range(29)]
    ob29 = MetricsReadModel(loader(cases=b29, cov=coverage())).compute("2026-10")
    T("C4a #81 召回分母 29 < 30 → 样本不足且无比率",
      sample_insufficient(ob29["metrics"]["recall_l4_l5"]),
      str(ob29["metrics"]["recall_l4_l5"]))
    T("C4b #84 推翻率分母 29 < 30 → 样本不足且无比率",
      sample_insufficient(ob29["metrics"]["human_overturn_rate"]),
      str(ob29["metrics"]["human_overturn_rate"]))
    b30 = [case(case_id="b%d" % i, state="REVIEW", machine_max_sev="L4",
                human_max_sev="L4", machine_conclusion="REVIEW",
                human_conclusion="BLOCK") for i in range(30)]
    ob30 = MetricsReadModel(loader(cases=b30, cov=coverage())).compute("2026-10")
    T("C4c #81 召回分母 30 → ok 且给比率",
      gives_ratio(ob30["metrics"]["recall_l4_l5"]),
      str(ob30["metrics"]["recall_l4_l5"]))
    T("C4d #84 推翻率分母 30 → ok 且给比率",
      gives_ratio(ob30["metrics"]["human_overturn_rate"]),
      str(ob30["metrics"]["human_overturn_rate"]))
    # #83：MIN_N_UNCOVERED=1 → 分母 1 必须给比率；把它改成 2 曾让 den=1 变「样本不足」。
    one = [case(case_id="only", state="未审查", machine_conclusion="未审查")]
    o1 = MetricsReadModel(loader(cases=one, cov=coverage())).compute("2026-10")
    T("C5a #83 未覆盖分母 1 → 给比率而不是样本不足",
      gives_ratio(o1["metrics"]["uncovered_ratio"]),
      str(o1["metrics"]["uncovered_ratio"]))
    zero = MetricsReadModel(loader(cases=[], cov=coverage())).compute("2026-10")
    T("C5b #83 未覆盖分母 0 → 未测/不可计算形状",
      zero["metrics"]["uncovered_ratio"]["status"] in ("样本不足", "未测")
      and zero["metrics"]["uncovered_ratio"]["ratio"] is None,
      str(zero["metrics"]["uncovered_ratio"]))

    # ── D 抽样层 / BLOCK 全量复核 ──────────────────────────────────
    cov_missing = coverage(sampled_layers=["PASS", "待自决", "REVIEW"])
    o = MetricsReadModel(loader(cov=cov_missing)).compute("2026-10")
    T("D1 召回缺一层抽样 → 未测且无比率",
      o["metrics"]["recall_l4_l5"]["status"] == "未测"
      and o["metrics"]["recall_l4_l5"]["ratio"] is None, str(o["metrics"]["recall_l4_l5"]))
    cov_partial = coverage(block_review_complete=False, block_total=42, block_reviewed=30)
    o = MetricsReadModel(loader(cov=cov_partial)).compute("2026-10")
    T("D2 BLOCK 未全量复核 → 误判未测 + 已复核占比",
      o["metrics"]["false_positive_l4_l5"]["status"] == "未测"
      and o["metrics"]["false_positive_l4_l5"]["ratio"] is None
      and abs(o["metrics"]["false_positive_l4_l5"]["reviewed_coverage"] - 30 / 42) < 1e-9,
      str(o["metrics"]["false_positive_l4_l5"]))

    # ── E 分母口径 ──────────────────────────────────────────────────
    # 加入一条 CLEAN-CANDIDATE：分母 +1，未覆盖分子不变
    more = dataset() + [case(case_id="clean_extra", state="PASS",
                             clean_candidate=True, machine_conclusion="PASS")]
    o2 = MetricsReadModel(loader(cases=more, cov=coverage())).compute("2026-10")
    T("E1 CLEAN-CANDIDATE 不增未覆盖分子（分母 +1）",
      o2["metrics"]["uncovered_ratio"]["numerator"] == 20
      and o2["metrics"]["uncovered_ratio"]["denominator"] == 68, str(o2["metrics"]["uncovered_ratio"]))
    # 申诉胜/败都进推翻率分母：把一条 lost 改成 won，分母不变
    alt = [dict(c) for c in dataset()]
    for c in alt:
        if c.get("appeal_result") == "lost":
            c["appeal_result"] = "won"
    o3 = MetricsReadModel(loader(cases=alt, cov=coverage())).compute("2026-10")
    T("E2 申诉胜败都进推翻率分母（全改 won 分母不变）",
      o3["metrics"]["human_overturn_rate"]["denominator"]
      == o["metrics"]["human_overturn_rate"]["denominator"], "")

    # ── F 目标线不得写死 ────────────────────────────────────────────
    T("F1 所有指标 target 都不是数字",
      all(not isinstance(m.get("target"), (int, float)) for m in ms.values()), "")
    src = open(os.path.join(ROOT, "base", "metrics_read_model.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    numeric_targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "target" \
                        and isinstance(v, ast.Constant) and isinstance(v.value, (int, float)):
                    numeric_targets.append(v.value)
    T("F2 源码里没有数字 target 字面量", numeric_targets == [], str(numeric_targets))

    # ── G 确定性 ────────────────────────────────────────────────────
    oa = MetricsReadModel(loader()).compute("2026-10")
    ob = MetricsReadModel(loader()).compute("2026-10")
    T("G1 同一数据两次结果一致", oa == ob, "")

    if "--controls" in sys.argv:
        rc_controls = controls(sample_insufficient, gives_ratio)
        if fails:
            # 主检查红了就别让 --controls 报全绿 —— 退出码只看最红的那一侧。
            print("\n⚠ 主检查另有 %d 项红（--controls 不掩盖）：" % len(fails))
            for f in fails:
                print("  ❌ " + f)
            return 1
        return rc_controls

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_metrics_read_model %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


def controls(sample_insufficient, gives_ratio):
    """X 段 · --controls 离线反向对照：每条新判据都有「该红」与「该绿」两侧。

    「坏形状」直接模拟生产变异后的输出（与 mutprobe 的 old/new 同形）：
      · MIN_N 30→29       → n=29 被判 ok 且给比率
      · MIN_N_UNCOVERED 1→2 → den=1 被判「样本不足」
      · 分子口径 !=→==    → 标准集分子 46→2
    判据对这些坏形状必须判假、对正常输出必须判真 —— 缺一侧就没被验证过。
    """
    # 真形状：n=29 边界（真实跑出）
    b29 = [case(case_id="b%d" % i, state="REVIEW", machine_max_sev="L4",
                human_max_sev="L4", machine_conclusion="REVIEW",
                human_conclusion="BLOCK") for i in range(29)]
    o29 = MetricsReadModel(loader(cases=b29, cov=coverage())).compute("2026-10")
    # 坏形状：MIN_N 30→29 之后 n=29 的样子（ok + 比率）
    mutated_n29 = {"status": "ok", "ratio": 1.0, "n": 29, "denominator": 29}

    # 真形状：den=1（真实跑出）
    one = [case(case_id="only", state="未审查", machine_conclusion="未审查")]
    o1 = MetricsReadModel(loader(cases=one, cov=coverage())).compute("2026-10")
    # 坏形状：MIN_N_UNCOVERED 1→2 之后 den=1 的样子（样本不足 + 无比率）
    mutated_den1 = {"status": "样本不足", "ratio": None, "n": 1, "denominator": 1}

    # #84 分子：同一份标准集，真口径 vs 变异口径各自数出的分子
    eligible = [c for c in dataset()
                if c.get("machine_conclusion") is not None
                and c.get("human_conclusion") is not None]
    num_true = sum(1 for c in eligible if c["machine_conclusion"] != c["human_conclusion"])
    num_mutated = sum(1 for c in eligible if c["machine_conclusion"] == c["human_conclusion"])

    cases = [
        # ── 该绿（真形状过真判据）────────────────────────────────
        ("[C4] 真形状：n=29 → 判据判「样本不足」",
         lambda: sample_insufficient(o29["metrics"]["recall_l4_l5"])
         and sample_insufficient(o29["metrics"]["human_overturn_rate"])),
        ("[C4] 真形状：n=30 → 判据判 ok 且给比率",
         lambda: gives_ratio({"status": "ok", "ratio": 1.0, "n": 30, "denominator": 30})),
        ("[C5] 真形状：den=1 → 判据判给比率",
         lambda: gives_ratio(o1["metrics"]["uncovered_ratio"])),
        ("[C5] 真形状：den=0 → 判据判不出比率",
         lambda: not gives_ratio({"status": "样本不足", "ratio": None, "n": 0, "denominator": 0})),
        ("[A8b] 真口径在标准集上数出的分子 == 金标 46",
         lambda: num_true == 46),
        # ── 该红（变异形状必须被真判据抓住）──────────────────────
        ("[C4] 坏形状（MIN_N→29：n=29 判 ok 给比率）→ 被抓住",
         lambda: not sample_insufficient(mutated_n29)),
        ("[C5] 坏形状（den=1 判样本不足）被「样本不足」判据看清 → C5a 主检查必然红",
         lambda: sample_insufficient(mutated_den1)),
        ("[C5] 坏形状（MIN_N_UNCOVERED→2：den=1 判样本不足）→ 被抓住",
         lambda: not gives_ratio(mutated_den1)),
        ("[A8b] 坏口径（==）数出的分子 ≠ 46 → 被金标抓住",
         lambda: num_mutated != 46),
    ]
    fail = 0
    print("=" * 78)
    print("X 段 · metrics_read_model 判据反向对照（该红该绿都有）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, "（%s: %s）" % (type(e).__name__, e)
        if not ok:
            fail += 1
        print("  %s [%d/%d] %s%s" % ("✅" if ok else "❌", i, len(cases), name, err))
    print("-" * 78)
    if fail:
        print("❌ %d 项中 %d 项失败" % (len(cases), fail))
        return 1
    print("✅ %d 项全过（判据的红绿两侧都活着）" % len(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
