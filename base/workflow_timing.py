# -*- coding: utf-8 -*-
"""workflow_timing.py — 一次审核从进件到出结论的**工作流耗时**读数

## 它为什么存在

`base/orchestrator.py` 早就在测每一步的 `duration_ms`（`:335-349`，用真时钟
`time.time`），`contracts/receipt-v1.schema.json` 也把它列为 `steps[]` 的 **required**。
但**没有任何东西把它读出来**：报告模板只打印 skill/版本/指纹/跳过步骤，
接口不返回它，`base/metrics_read_model.py` 的两个指标里也没有它。

也就是说：**测了，但用户看不见。** 这是 T-451 要补的那一段。

## ★ 为什么不用 `ended_at - started_at`

`base/orchestrator.py:54-55` 的 `_iso()` 精度只到**秒**：

    def _iso(ts):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))

而整条链实测只跑 **0.8–2.3 ms**（三次读数）。所以 `started_at` 与 `ended_at`
**恒相等**。拿秒差算总耗时，会得到一个**恒为 0 的读数** ——
它长得像「测过了、很快」，实际什么都没测。

这与 AGENTS.md §2.1.1 说「用 (mtime, size) 当判据」是同一个病：
**两个数相等并不是证据，它是常态。**

## 求和而不是秒差，还依赖一个前提

`:438-442` 五步是**顺序调用**的（normalize → judge → dispose → output → evaluate），
所以各步 `duration_ms` 可以相加。**将来若引入并行步骤，`total_ms` 必须重写**
（改成墙钟差 + 提高 `_iso` 精度），否则会漏算重叠部分。`source` 字段就是为此留的。

## 三态

与项目其他读数同一口径：**有读数 / 没测成（untested）/ 出错（error）**。
空步骤集与「0.0 ms 很快」长得一模一样，所以空集**必须**落 untested，不许报 0。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: 报告的「最慢三步」取几个
TOP_N = 3

#: `source` 的取值域 —— 说明这份总耗时是怎么算出来的。
#: ★ 加新算法必须同时加进这里，否则 `verify_workflow_timing` 会红。
SOURCE_STEP_SUM = "steps-duration-sum"

SOURCES = (SOURCE_STEP_SUM,)


def compute(receipt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从回执算工作流耗时读数。

    返回（键的形状是契约，接口与报告共用，**不许各自拼一份**）：

        {
          "status": "ok" | "untested",
          "reason": str,             # untested 时点名原因；ok 时为空串
          "total_ms": float | None,  # 各步求和
          "step_count": int,
          "slowest": [{"name": str, "duration_ms": float}, ...],  # 降序，最多 TOP_N
          "source": "steps-duration-sum",
        }
    """
    if not isinstance(receipt, dict):
        return _untested("回执缺失或不是对象")

    steps = receipt.get("steps")
    if not isinstance(steps, list) or not steps:
        # ★ 空集不许报 0 ms —— 「没跑」和「跑得极快」必须长得不一样。
        return _untested("回执里没有 steps（没有可测的步骤）")

    clean: List[Dict[str, Any]] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return _untested("steps[%d] 不是对象" % i)
        name = step.get("name")
        if not isinstance(name, str) or not name.strip():
            return _untested("steps[%d] 没有 name，无法归因" % i)
        dur = step.get("duration_ms")
        # bool 是 int 的子类，必须单独排除 —— 否则 True 会被当成 1.0 ms。
        if isinstance(dur, bool) or not isinstance(dur, (int, float)):
            return _untested("steps[%d]（%s）duration_ms 不是数字" % (i, name))
        if dur < 0:
            return _untested("steps[%d]（%s）duration_ms 为负 (%.3f)" % (i, name, dur))
        clean.append({"name": name, "duration_ms": round(float(dur), 3)})

    total = round(sum(s["duration_ms"] for s in clean), 3)
    slowest = sorted(clean, key=lambda s: (-s["duration_ms"], s["name"]))[:TOP_N]
    return {
        "status": "ok",
        "reason": "",
        "total_ms": total,
        "step_count": len(clean),
        "slowest": slowest,
        "source": SOURCE_STEP_SUM,
    }


def _untested(reason: str) -> Dict[str, Any]:
    return {
        "status": "untested",
        "reason": reason,
        "total_ms": None,
        "step_count": 0,
        "slowest": [],
        "source": SOURCE_STEP_SUM,
    }


def format_line(timing: Dict[str, Any]) -> str:
    """一行人读的耗时说明。报告与接口都要能复述它 —— 口径只在这里定义一次。

    ★ 未测时**不许**出现「0」「很快」「秒」这类读起来像读数的字眼。
    """
    if timing.get("status") != "ok":
        return "未测（%s）" % (timing.get("reason") or "原因不明")
    total = timing["total_ms"]
    steps = timing["step_count"]
    slow = timing.get("slowest") or []
    parts = ["总耗时 %.2f ms（%d 步求和）" % (total, steps)]
    if slow:
        parts.append("最慢：" + "、".join(
            "%s %.2f ms" % (s["name"], s["duration_ms"]) for s in slow))
    return "；".join(parts)
