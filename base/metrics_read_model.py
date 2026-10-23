#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/metrics_read_model.py —— 唯一只读指标聚合（T1-14）

## 四个指标（Playbook §6.1）

  1. `recall_l4_l5`          高危（L4/L5）召回率
  2. `false_positive_l4_l5`  高危（L4/L5）误判率
  3. `uncovered_ratio`       未覆盖占比
  4. `human_overturn_rate`   人工推翻率

每个指标**各自七要素**：`numerator` / `denominator` / `window` /
`sampling_layer` / `min_n` / `status` / `target`。

## 口径

  - **未测**：数据源读不出 / 结构坏 / window 为空 → `status="未测"`，
    分子、分母、ratio 均为 `None` —— **不是 0，不是 N/A**。
  - **样本不足**：`n < min_n` → `status="样本不足"`，ratio=None，仍显示 n。
  - **召回抽样层**：PASS / 待自决 / REVIEW / 未审查 **四层分别抽样**；
    缺任一层 → 未测。
  - **误判**：BLOCK 层全量复核；未复核完 → `status="未测"` + `reviewed_coverage`，
    不许用部分样本出比率；未复核条目不计入分子/分母。
  - **未覆盖分子**：只算 `state=未审查` 且非 ERROR、非 fetch_error；
    CLEAN-CANDIDATE 不进入分子。ERROR / fetch_error 各自单列计数。
  - **推翻率分母**：有机器结论且有对应人工结论的全部条数；申诉胜、败都计入。
  - **目标线**：首次测量前 `target=None`、`target_status="待基线"`，不写死数值。

## 不做什么

不判状态、不产 finding、不写报告；数据源由调用方注入（IR / reviews_ledger /
submissions+receipts 的只读聚合），本模块只算数与判定「未测/样本不足」。
"""
from __future__ import annotations

RECALL_LAYERS = ("PASS", "待自决", "REVIEW", "未审查")
MIN_N = 30
MIN_N_UNCOVERED = 1
HIGH_SEV = ("L4", "L5")

#: 失败类型四分类（验收表 #9 / L1-7 L1-8 SEC-8-10）。
#: ★ 与 `tools/audit/report_render.mjs` 的 `FAILURE_KINDS` **必须同名同序** ——
#:   报告侧按这四键逐项打印，指标侧按这四键分别计数；两边一旦漂移，
#:   报告会印出一个指标里根本没有的键（或反过来漏印）。
FAILURE_KINDS = ("fetch_error", "parse_error", "empty", "unsupported")


def _metric(mid, name, window, sampling_layer, min_n):
    return {
        "id": mid,
        "name": name,
        "numerator": None,
        "denominator": None,
        "n": None,
        "ratio": None,
        "window": window,
        "sampling_layer": sampling_layer,
        "min_n": min_n,
        "status": "未测",
        "target": None,
        "target_status": "待基线",
    }


def _finalize(m, numerator, denominator):
    m["numerator"] = numerator
    m["denominator"] = denominator
    m["n"] = denominator
    if denominator is None or denominator < m["min_n"]:
        m["status"] = "样本不足"
        m["ratio"] = None
    else:
        m["status"] = "ok"
        m["ratio"] = (float(numerator) / denominator) if denominator else None
    return m


def _untested():
    return {
        "recall_l4_l5": _metric("recall_l4_l5", "高危（L4/L5）召回率", None,
                                list(RECALL_LAYERS), MIN_N),
        "false_positive_l4_l5": _metric("false_positive_l4_l5", "高危（L4/L5）误判率", None,
                                        "BLOCK 全量", MIN_N),
        "uncovered_ratio": _metric("uncovered_ratio", "未覆盖占比", None,
                                   "全量", MIN_N_UNCOVERED),
        "human_overturn_rate": _metric("human_overturn_rate", "人工推翻率", None,
                                       "全量", MIN_N),
    }


class MetricsReadModel(object):
    def __init__(self, load):
        self.load = load

    def compute(self, window):
        if not isinstance(window, str) or not window.strip():
            metrics = _untested()
            for m in metrics.values():
                m["window"] = window
            return {"window": window, "metrics": metrics}

        try:
            data = self.load(window)
        except Exception:  # noqa: BLE001
            return {"window": window, "metrics": _untested()}
        if not isinstance(data, dict):
            return {"window": window, "metrics": _untested()}
        cases = data.get("cases")
        cov = data.get("coverage")
        if not isinstance(cases, list) or not isinstance(cov, dict):
            return {"window": window, "metrics": _untested()}
        if not all(isinstance(c, dict) for c in cases):
            return {"window": window, "metrics": _untested()}

        metrics = {}
        metrics["recall_l4_l5"] = self._recall(cases, cov, window)
        metrics["false_positive_l4_l5"] = self._false_positive(cases, cov, window)
        metrics["uncovered_ratio"] = self._uncovered(cases, window)
        metrics["human_overturn_rate"] = self._overturn(cases, window)
        return {"window": window, "metrics": metrics}

    # ── ① 召回 ──────────────────────────────────────────────────────
    def _recall(self, cases, cov, window):
        m = _metric("recall_l4_l5", "高危（L4/L5）召回率", window,
                    list(RECALL_LAYERS), MIN_N)
        human_pos = [c for c in cases if c.get("human_max_sev") in HIGH_SEV]
        numerator = sum(1 for c in human_pos if c.get("machine_max_sev") in HIGH_SEV)
        denominator = len(human_pos)
        sampled = set(cov.get("sampled_layers") or [])
        if not set(RECALL_LAYERS) <= sampled:
            m["numerator"] = numerator
            m["denominator"] = denominator
            m["n"] = denominator
            m["status"] = "未测"
            m["ratio"] = None
            return m
        return _finalize(m, numerator, denominator)

    # ── ② 误判 ──────────────────────────────────────────────────────
    def _false_positive(self, cases, cov, window):
        m = _metric("false_positive_l4_l5", "高危（L4/L5）误判率", window,
                    "BLOCK 全量", MIN_N)
        machine_pos = [c for c in cases if c.get("machine_max_sev") in HIGH_SEV]
        reviewed = [c for c in machine_pos if c.get("review_completed") is True]
        numerator = sum(1 for c in reviewed if c.get("human_max_sev") not in HIGH_SEV)
        denominator = len(reviewed)

        total = cov.get("block_total")
        seen = cov.get("block_reviewed")
        if isinstance(total, int) and isinstance(seen, int) and total > 0:
            m["reviewed_coverage"] = float(seen) / total
        else:
            m["reviewed_coverage"] = None

        if cov.get("block_review_complete") is not True:
            m["numerator"] = numerator
            m["denominator"] = denominator
            m["n"] = denominator
            m["status"] = "未测"
            m["ratio"] = None
            return m
        return _finalize(m, numerator, denominator)

    # ── ③ 未覆盖 ────────────────────────────────────────────────────
    def _uncovered(self, cases, window):
        m = _metric("uncovered_ratio", "未覆盖占比", window, "全量", MIN_N_UNCOVERED)
        numerator = sum(
            1 for c in cases
            if c.get("state") == "未审查"
            and c.get("run_state") != "ERROR"
            and c.get("failure_kind") != "fetch_error")
        denominator = len(cases)
        m["clean_candidate_count"] = sum(1 for c in cases if c.get("clean_candidate") is True)
        m["error_count"] = sum(1 for c in cases if c.get("run_state") == "ERROR")
        m["fetch_error_count"] = sum(1 for c in cases if c.get("failure_kind") == "fetch_error")
        # ★ 2026-10-24 补（验收表 #9 / L1-7 L1-8 SEC-8-10）：
        #   「造 empty 2 条、parse_error 3 条、fetch_error 1 条、unsupported 1 条的样本
        #    跑统计与报告；断言 empty=2 与其余 failed 合计=4 分别可见且可核对，
        #    而不是只有一个失败总数。」
        #
        #   此前这里**只算了三个键**（clean_candidate / error / fetch_error），
        #   `empty` / `parse_error` / `unsupported` 一个都没有 —— 于是
        #   「四个 failure_kind 分别可见」这件事**根本没有数据来源**，
        #   而验收表那一行却一直挂在 passed 上。
        #
        #   三键与 fetch_error_count 同源（都读 `failure_kind`），互相独立可核对：
        #   它们的和就是「按失败类型可归因的条数」，与 error_count（run_state=ERROR）
        #   是两个正交口径 —— 一个按失败原因，一个按运行状态。
        for _kind in FAILURE_KINDS:
            m["%s_count" % _kind] = sum(
                1 for c in cases if c.get("failure_kind") == _kind)
        # 「其余 failed 合计」= 四类之和减去 empty（验收表要 empty 与「其余」分开可见）
        m["failed_other_than_empty"] = sum(
            m["%s_count" % k] for k in FAILURE_KINDS if k != "empty")
        return _finalize(m, numerator, denominator)

    # ── ④ 人工推翻率 ────────────────────────────────────────────────
    def _overturn(self, cases, window):
        m = _metric("human_overturn_rate", "人工推翻率", window, "全量", MIN_N)
        eligible = [c for c in cases
                    if c.get("machine_conclusion") is not None
                    and c.get("human_conclusion") is not None]
        numerator = sum(1 for c in eligible
                        if c.get("machine_conclusion") != c.get("human_conclusion"))
        denominator = len(eligible)
        m["appeal_won"] = sum(1 for c in eligible if c.get("appeal_result") == "won")
        m["appeal_lost"] = sum(1 for c in eligible if c.get("appeal_result") == "lost")
        return _finalize(m, numerator, denominator)
