#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三层：严重等级 = NIST TABLE I-2 查表（severity × exposure）。

★ 为什么不是乘法：见 `规范-审核规则库完整设计.md` §4.3.1。
  官方矩阵有一处乘法无法复现的效应 —— **低概率行会封顶**：
  `Low likelihood` 一行最高只到 `Moderate`，`Very Low` 一行最高只到 `Low`。
  乘法会系统性高估低曝光内容，把「高危但几乎没投」的文案排到不该有的优先级。

★ 为什么 exposure 缺两维：设计文档 §4.3.2 依据 DSA Recital (79) 要求三个子维度
  （触达人数 / 不可逆性 / 补救难度）。委托方**只有第一维**的数据。
  本模块**不伪造**后两维 —— 它们留 None，并在结果里显式标记 `incomplete_exposure`。
  **一条判定的可信度必须能被下游看见，而不是被默认值掩盖。**
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------- NIST 查表
# 来源：NIST SP 800-30 Rev.1, TABLE I-2: ASSESSMENT SCALE – LEVEL OF RISK
# 证据：_evidence/R8/nist-sp800-30r1.txt L4883–4896（已逐字复核）
LIKELIHOOD_LEVELS = ["Very Low", "Low", "Moderate", "High", "Very High"]
IMPACT_LEVELS = ["Very Low", "Low", "Moderate", "High", "Very High"]

# 行 = likelihood，列 = impact
TABLE_I2 = {
    "Very High": {"Very Low": "Very Low", "Low": "Low", "Moderate": "Moderate", "High": "High", "Very High": "Very High"},
    "High":      {"Very Low": "Very Low", "Low": "Low", "Moderate": "Moderate", "High": "High", "Very High": "Very High"},
    "Moderate":  {"Very Low": "Very Low", "Low": "Low", "Moderate": "Moderate", "High": "Moderate", "Very High": "High"},
    "Low":       {"Very Low": "Very Low", "Low": "Low", "Moderate": "Low", "High": "Low", "Very High": "Moderate"},
    "Very Low":  {"Very Low": "Very Low", "Low": "Very Low", "Moderate": "Very Low", "High": "Low", "Very High": "Low"},
}

# ------------------------------------------------- severity(L0..L5) → impact
SEVERITY_TO_IMPACT = {
    "L0": "Very Low",   # 未覆盖 —— 不是「低风险」，是「不知道」。查表会低估它，见下 note
    "L1": "Very Low",   # 合规但受限
    "L2": "Low",        # 审慎
    "L3": "Moderate",   # 需修
    "L4": "High",       # 高危
    "L5": "Very High",  # 一次触顶
}

IMPACT_TO_RANK = {k: i for i, k in enumerate(IMPACT_LEVELS)}


@dataclass
class Exposure:
    """DSA Recital (79) 三个子维度。缺的维度保持 None，不填默认值。"""
    reach: Optional[int] = None           # 触达人数（近7天展示）—— 已有
    irreversibility: Optional[str] = None  # {可撤回, 部分可撤, 不可撤} —— 无字段
    remediability: Optional[str] = None    # {有申诉通道, 需人工交涉, 不可补救} —— 无字段

    @property
    def complete(self) -> bool:
        return None not in (self.reach, self.irreversibility, self.remediability)


# 分箱阈值：按实测展示量分布取对数分位
# 实测（291 条）：138 条展示>0，最大 303,274。0–10k / 10k–50k / 50k–150k / >150k
REACH_BINS = [
    (0, 1, "Very Low"),          # 无展示
    (1, 10_000, "Low"),
    (10_000, 50_000, "Moderate"),
    (50_000, 150_000, "High"),
    (150_000, math.inf, "Very High"),
]


def reach_to_likelihood(reach: Optional[int]) -> str:
    if reach is None:
        return "Very Low"
    for lo, hi, label in REACH_BINS:
        if lo <= reach < hi:
            return label
    return "Very High"


def lookup_risk(severity: str, likelihood: str) -> str:
    """TABLE I-2 查表。未知档位直接报错，不静默取默认值。"""
    if severity not in SEVERITY_TO_IMPACT:
        raise ValueError(f"未知 severity: {severity}")
    if likelihood not in LIKELIHOOD_LEVELS:
        raise ValueError(f"未知 likelihood: {likelihood}")
    return TABLE_I2[likelihood][SEVERITY_TO_IMPACT[severity]]


@dataclass
class RiskResult:
    severity: str
    likelihood: str
    risk_level: str
    exposure_complete: bool
    caveats: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def assess(severity: str, exposure: Exposure, *, is_catch_all: bool = False) -> RiskResult:
    """给一条命中定级。"""
    caveats = []

    if not exposure.complete:
        missing = [k for k in ("irreversibility", "remediability")
                   if getattr(exposure, k) is None]
        caveats.append(f"missing_exposure_dims:{','.join(missing)}")

    if is_catch_all:
        caveats.append("catch_all:未命中≠合规。L0 经查表会被压到 Very Low，"
                       "这是矩阵的结构性限制 —— L0 表示『不知道』而非『低风险』，"
                       "它必须走人工复核通道，不得用查表结果做优先级排序。")

    likelihood = reach_to_likelihood(exposure.reach)
    risk = lookup_risk(severity, likelihood)

    # impact 取最差：NIST TABLE H-4 第四列即 `Maximum Impact`，官方做法是取最差不取平均。
    # 目前只有 reach 一维有数据，这条逻辑先留出接口，等两维补齐后启用。
    if exposure.irreversibility == "不可撤" and IMPACT_TO_RANK[SEVERITY_TO_IMPACT[severity]] < IMPACT_TO_RANK["High"]:
        caveats.append("irreversibility_escalation:不可撤后果应把 impact 抬到至少 High（TABLE H-4 取最差），"
                       "当前 impact 未抬升 —— 该维度数据尚未采集，此处只记录不执行。")

    return RiskResult(severity, likelihood, risk, exposure.complete, caveats)


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    # 1. 复现 NIST 表格全部 25 格（防止手抄错）
    print("=== TABLE I-2 全格复现 ===")
    for lk in LIKELIHOOD_LEVELS:
        row = []
        for im in IMPACT_LEVELS:
            row.append(TABLE_I2[lk][im])
        print(f"  {lk:10s} | " + " | ".join(f"{x:9s}" for x in row))

    # 2. 证伪乘法：找出矩阵与乘法结论不同的格子
    print()
    print("=== 乘法 vs 查表：结论不同的格子（这是不能用乘法的证明）===")
    rank = {k: i for i, k in enumerate(IMPACT_LEVELS)}
    differ = 0
    for lk in LIKELIHOOD_LEVELS:
        for im in IMPACT_LEVELS:
            table = TABLE_I2[lk][im]
            # 乘法代理：两因子序数取平均后分档
            avg = (rank[lk] + rank[im]) / 2
            mult = IMPACT_LEVELS[min(int(round(avg)), 4)]
            if table != mult:
                differ += 1
                print(f"  likelihood={lk:10s} impact={im:10s} → 查表={table:9s} 乘法≈{mult}")
    print(f"  共 {differ}/25 格结论不同 —— 乘法不是这张矩阵的近似")

    # 3. 封顶效应
    print()
    print("=== 封顶效应（乘法无法复现）===")
    for lk in ["Very Low", "Low"]:
        vals = [TABLE_I2[lk][im] for im in IMPACT_LEVELS]
        print(f"  likelihood={lk:9s} 即使 impact=Very High → {vals[-1]}（最高只到 {max(vals, key=lambda v: rank[v])}）")

    # 4. 契约测试
    print()
    print("=== 契约测试 ===")
    cases = [
        ("L4", Exposure(300_000, "不可撤", "不可补救"), "High likelihood × High impact"),
        ("L4", Exposure(5_000, None, None), "Low likelihood × High impact → 应封顶"),
        ("L4", Exposure(0, None, None), "无展示"),
        ("L2", Exposure(300_000, None, None), "审慎 × 高触达"),
    ]
    for sev, exp, label in cases:
        r = assess(sev, exp)
        print(f"  {label}")
        print(f"    severity={sev} reach={exp.reach!r} → likelihood={r.likelihood} risk={r.risk_level}"
              f" 完整={r.exposure_complete}")
    try:
        lookup_risk("L9", "High")
        print("  ✗ 未拦截非法 severity")
    except ValueError as e:
        print(f"  ✓ 正确拦截非法 severity: {e}")
