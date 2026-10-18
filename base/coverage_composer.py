#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coverage_composer.py —— 唯一覆盖证明合成与 coverage_state 派生（Playbook §3.3.5）

    coverage = 评过的模态 + 规则版本(号+指纹) + 适用控制点逐族跑过/没跑 + 未跑的为什么

    coverage_state ∈ {missing, partial, full}
        missing  四项里缺字段，或评过模态为空       → 结论只能落「未审查」
        partial  四项齐全，但有东西没跑             → 可以出结论，但**永不 PASS**
        full     四项齐全且没有任何未跑项           → 唯一够格 PASS 的档

--------------------------------------------------------------------------
★ 本文件刻意做死的四件事
--------------------------------------------------------------------------

**一、`missing` 与 `partial` 是两件被压成一件事的东西**

    missing = **我说不清我做了什么**（连「评了什么」都答不出来）
    partial = **我说得清，但确实有一块没做**

    两者对结论的影响不同：前者只能落「未审查」，后者可以出结论但不许 PASS。
    把它们混成一个「覆盖不全」，会让「我们根本没能力审」和「我们审了但没审全」
    在报告上长得一样。

**二、空族记「未做·无控制点」，**不记** `not_applicable`**

    空族的意思是「这一族我们一个控制点都还没定」——**是待办，不是已决定不做**。
    写成 `not_applicable` 会让一个「还没做」看起来像「决定不做」，
    那正是本项目台账 K-05（未做被报成已清）的形状。

    执行点：`compose()` 遇到空族自动补一条 reason=no_control_points，
    而 `check()` 见到 not_applicable 直接拒。

**三、`parse_status=failed` → 一律 missing**

    抓取/解析失败时，连「评过哪些模态」都答不出来。
    这不是 partial —— partial 的前提是四项齐全。

**四、当前真实数据下 `full` 不可达 —— 这是事实，不是 bug**

    `research/governance/control-points-v1.json` 现在有 4 个空族（场景/权利/渠道/品牌）。
    按规则，空族计入 partial，所以**每一份内容都是 partial、PASS 永远出不来**。
    这与 Playbook §5.3 的连带结论一致。

    本文件因此把 `empty_families` 做成**可注入参数**：
      · 传当前四族 → 派生 partial（测真实行为）
      · 传空列表   → 可能派生 full（测「干净时真的会出 full」，防全拦）
    两组测试都必须存在，否则「永远 partial」会把 full 分支的 bug 全遮住。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CP_TABLE = ROOT / "research" / "governance" / "control-points-v1.json"

# 「未跑的为什么」的封闭集合。
# 前三个来自 Playbook §3.3.5（无能力 / 无规则 / 未接线）；
# 第四个 `no_control_points` 是空族的专用标签（验收表第 30 项要求逐字出现「未做·无控制点」）。
REASONS = frozenset({"no_capability", "no_rule", "not_wired", "no_control_points"})

# ★ 明确禁止的写法：把「还没做」写成「决定不做」
FORBIDDEN_REASONS = frozenset({"not_applicable", "n/a", "none", "skip"})

STATES = frozenset({"missing", "partial", "full"})

REQUIRED_KEYS = (
    "modalities_evaluated",     # 评过的模态（非空）
    "rules_version",            # {version, fingerprint} 两个都要
    "control_points_by_family", # 七个控制族逐族 ran/not_run
    "not_run_reasons",          # [{what, why}]
)


class CoverageRejected(Exception):
    """拒收。每条都要说清是哪个字段、为什么。"""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# ─────────────────────── 读空族（可注入）───────────────────────

def load_empty_families(table_path: str | os.PathLike | None = None) -> list[str]:
    """
    读主表的 `empty_families`。读不到**抛错**而不是返回 [] ——
    返回空列表会让「读不到」与「没有空族」长得一样，于是静默给出 full。
    """
    p = Path(table_path) if table_path is not None else DEFAULT_CP_TABLE
    if not p.exists():
        raise CoverageRejected("E_TABLE", f"读不到 {p} —— 空族未知，不能当作「没有空族」")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CoverageRejected("E_TABLE", f"{p} 读不出：{type(e).__name__}: {e}")
    fams = d.get("empty_families")
    if not isinstance(fams, list):
        raise CoverageRejected("E_TABLE", f"{p} 缺 empty_families 数组")
    return [f.get("family") for f in fams if isinstance(f, dict)]


def load_all_families(table_path: str | os.PathLike | None = None) -> list[str]:
    p = Path(table_path) if table_path is not None else DEFAULT_CP_TABLE
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CoverageRejected("E_TABLE", f"{p} 读不出：{type(e).__name__}: {e}")
    fams = d.get("families")
    if not isinstance(fams, list) or not fams:
        raise CoverageRejected("E_TABLE", f"{p} 缺 families 数组")
    return list(fams)


# ─────────────────────── 合成 ───────────────────────

def compose(
    *,
    modalities_evaluated: Sequence[str],
    rules_version: dict | None,
    control_points_by_family: dict[str, str] | None,
    not_run_reasons: Iterable[dict] | None = None,
    does_not_cover: Iterable[str] | None = None,
    empty_families: Sequence[str] | None = None,
) -> dict:
    """
    合成一份覆盖证明。

    `empty_families` 传 None 时从主表读；传 [] 表示「没有空族」（测试 full 分支用）。

    ★ 空族会被**自动补**进 `not_run_reasons`，reason=no_control_points。
      调用方不需要记得补 —— 忘了补就漏掉一整块「没做」的东西。
    """
    if empty_families is None:
        empty_families = load_empty_families()
    empty = list(empty_families)

    by_family = dict(control_points_by_family or {})
    # 空族强制标 not_run（哪怕调用方写了 ran）
    for f in empty:
        by_family[f] = "not_run"

    reasons = [dict(r) for r in (not_run_reasons or [])]
    covered_whats = {r.get("what") for r in reasons}
    for f in empty:
        if f not in covered_whats:
            reasons.append({
                "what": f,
                "why": "no_control_points",
                "label": "未做·无控制点",
            })

    return {
        "modalities_evaluated": list(modalities_evaluated or []),
        "rules_version": dict(rules_version) if isinstance(rules_version, dict) else rules_version,
        "control_points_by_family": by_family,
        "not_run_reasons": reasons,
        "does_not_cover": list(does_not_cover or []),
    }


# ─────────────────────── 校验 ───────────────────────

def check(coverage: dict, *, all_families: Sequence[str] | None = None) -> None:
    """
    结构校验（**只校验「说得清」，不派生状态**）。抛 CoverageRejected。

    故意与 `derive_state()` 分开：一条记录可以「结构不完整」而仍然要能落 missing，
    所以结构不合格不等于拒收 —— 那是 derive 的事。这里拒的是**不该出现的写法**。
    """
    if not isinstance(coverage, dict):
        raise CoverageRejected("E_TYPE", f"coverage 必须是对象，实际 {type(coverage).__name__}")

    # ① 禁止写法：把空族/未做写成 not_applicable
    for r in coverage.get("not_run_reasons") or []:
        if not isinstance(r, dict):
            continue
        why = r.get("why")
        if why in FORBIDDEN_REASONS:
            raise CoverageRejected(
                "E_NOT_APPLICABLE",
                f"`{r.get('what')}` 用了 {why!r} —— 「还没做」≠「决定不做」"
                f"（空族应写 no_control_points / 未做·无控制点）")
        if why not in REASONS:
            raise CoverageRejected(
                "E_REASON", f"`{r.get('what')}` 的 why={why!r} 不在 {sorted(REASONS)}")

    # ② 规则版本：**不在这里拒收**。
    #    缺 version 或 fingerprint 属于「四项里缺字段」——按 §3.3.5，那是 `missing` **状态**，
    #    不是「不许写」的写法错误。在这里抛错会让缺失无法被表达成 missing，
    #    而 missing 恰恰是「我说不清我做了什么」该有的样子。
    #    ★ 2026-10-18 实测：原先在这里 raise，导致 A3/A4 两条「缺指纹→missing」测试全红——
    #      不是测试写错，是校验器把状态问题当成了格式问题。

    # ③ 逐族：值只能是 ran / not_run，且不许漏族
    by = coverage.get("control_points_by_family")
    if isinstance(by, dict):
        bad = {f: v for f, v in by.items() if v not in ("ran", "not_run")}
        if bad:
            raise CoverageRejected(
                "E_FAMILY_VALUE", f"逐族取值只能是 ran/not_run，这些不对：{bad}")
        if all_families:
            missing = [f for f in all_families if f not in by]
            if missing:
                raise CoverageRejected(
                    "E_FAMILY_MISSING",
                    f"漏了 {len(missing)} 个控制族：{missing} —— 逐族跑过/没跑必须逐个写")


# ─────────────────────── 派生 ───────────────────────

def derive_state(coverage: dict, *, parse_status: str = "ok") -> str:
    """
    从覆盖证明派生 state。**这是唯一一处能定 coverage_state 的地方。**

    顺序（先判 missing，再判 partial）：
      1. parse_status = failed / partial → missing
      2. 四项缺任一，或评过模态为空 → missing
      3. does_not_cover 非空，或有未跑项 → partial
      4. 否则 full
    """
    # ① 解析失败：连「评过什么」都答不出来
    if parse_status in ("failed", "partial"):
        return "missing"

    # ② 四项齐全性
    if not isinstance(coverage, dict):
        return "missing"
    for k in REQUIRED_KEYS:
        if k not in coverage or coverage[k] is None:
            return "missing"

    mods = coverage.get("modalities_evaluated")
    if not isinstance(mods, list) or not [m for m in mods if m]:
        return "missing"

    rv = coverage.get("rules_version")
    if not isinstance(rv, dict) or not str(rv.get("version") or "").strip() \
            or not str(rv.get("fingerprint") or "").strip():
        return "missing"

    by = coverage.get("control_points_by_family")
    if not isinstance(by, dict) or not by:
        return "missing"

    # ③ 有东西没跑 → partial
    if coverage.get("does_not_cover"):
        return "partial"
    if coverage.get("not_run_reasons"):
        return "partial"
    if any(v == "not_run" for v in by.values()):
        return "partial"

    # ④ 齐全且没有未跑项
    return "full"


def compose_and_derive(**kwargs) -> dict:
    """合成 + 校验 + 派生，一步到位。返回 {coverage, coverage_state}。"""
    parse_status = kwargs.pop("parse_status", "ok")
    all_families = kwargs.pop("all_families", None)
    cov = compose(**kwargs)
    check(cov, all_families=all_families)
    return {"coverage": cov, "coverage_state": derive_state(cov, parse_status=parse_status)}


def may_pass(coverage_state: str) -> bool:
    """PASS 资格闸之一：只有 full 才够格（L1-6：partial 永不 PASS）。"""
    if coverage_state not in STATES:
        raise CoverageRejected("E_STATE", f"未知 coverage_state={coverage_state!r}")
    return coverage_state == "full"
