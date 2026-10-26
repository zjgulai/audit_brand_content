#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_regression_signoff.py —— 法务签署的**存在性执行点**

## 这一条补的是什么缺口

行 86 第 ② 段要求「逐条检查**涉及法规的条目**是否带法务确认记录（确认人 + 时间）」。
盘上原先有两条字面相近、**对象不同**的检查，都不能替代本条：

| 已有的 | 它判的对象 | 能不能替本条 |
|---|---|---|
| `verify_regression_governance.py` 的 G-LEGAL | 按「命中带 external_ref 的规则」圈出的 **7 条**，要求 `legal_confirmation` | ❌ 只覆盖**引擎今天命中的** 7 条；`trap_negative` 4 条与其余 8 条 should_hit 全不在内 |
| `regression-set-manual-v1.json` | 人工台账 4 项的 status/evidence/owner/date | ❌ 是「人核原件」的留痕，不是逐条样本的签署字段 |

也就是说：**把「法务已签」写进样本文件之后，没有任何东西会因为某一条缺签署而变红。**
本条就是那个执行点 —— 指不出来的承诺等于没有承诺（AGENTS.md §2.4.2）。

## 断言（S 段）

  S1 顶层 `signoff` 存在，且**样本 id 集合**与 `signoff` 的键集合**互等**
     （缺一条 → 红；多一个孤儿键 → 红）
  S2 每条的 `signoff.by` / `signoff.at` / `signoff.basis` 三项非空
  S3 每条的 `signoff.at` 是**可解析的日期**，且**不在未来**（`--today` 可注入）
  S4 **`expected.kind == "should_hit"` 的每一条都必须带 signoff**（9 条，签「该拦」）
  S5 **`expected.kind == "trap_negative"` 的每一条都必须带 signoff**（4 条，验收表点名的陷阱）
  S6 `signoff.kind_signed` 必须等于该样本**当前**的 `expected.kind` ——
     否则「签的是哪一层」与「盘上现在是哪一层」脱钩（改过 kind 却没重签）
  S7 `GS-011` 必须**维持 `should_hit`**，且 `signoff_meta.待裁定` 里必须点名它
     —— 本条守的是「不许悄悄把这条改掉」：它同时被两种做法影响（改标签 / 改规则），
     而两种都不是本脚本能替法务做的决定

## **本文件不证明什么**（结论行必须照抄）

* **不证明签名真实。** 填上 `by: "法务"` 就能让本条变绿 —— 签名真伪只能人核原件或
  审批流（行 86 第 ③ 段，如实留 manual）。这是**字段在不在**的检查。
* **不证明签署内容正确。** 它证明「每一条都有署名」，不证明署名人读懂了那一条。
* **不证明 S7 那条冲突已解决。** 它只断言「冲突仍被记录着、没被静默抹掉」。

## 退出码

  0 全过 · 1 有红 · 2 未测（回归集读不出）

## 用法

    python3 tools/verify_regression_signoff.py
    python3 tools/verify_regression_signoff.py --controls
    python3 tools/verify_regression_signoff.py --today=2026-10-26
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGRESSION = ROOT / "research" / "governance" / "regression-set-v1.json"

#: 必须带签署的两层。`trap_negative` 是验收表行 85 逐字点名的四条陷阱；
#: `should_hit` 是唯一「该拦」的一层 —— 签错这两层的方向代价最大。
REQUIRED_KINDS = ("should_hit", "trap_negative")

#: S7 守的那条。它同时被「改标签」和「改规则」两种做法影响，
#: 而两种都不是本脚本能替法务做的决定 —— 所以只能断言「它仍被记录着」。
PINNED_ID = "GS-011"
PINNED_KIND = "should_hit"

REQUIRED_FIELDS = ("by", "at", "basis")


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def parse_date(s, today=None):
    """把 `at` 解析成 date。接受 `YYYY-MM-DD` 与完整 ISO8601（取前 10 位）。

    返回 (date, err)。err 非 None 表示解析失败。
    """
    if not isinstance(s, str) or not s.strip():
        return None, "空值"
    raw = s.strip()
    head = raw[:10]
    try:
        d = _dt.date.fromisoformat(head)
    except ValueError:
        return None, "不是可解析的日期：%r" % raw
    # 完整时间戳若带时区，按 UTC 日期读；这里只用到「不晚于今天」这一档精度
    if today is not None and d > today:
        return d, "日期在未来：%s > 今天 %s" % (d, today)
    return d, None


def check_coverage(samples, signoff):
    """S1：样本 id 集合 与 signoff 键集合 互等。"""
    problems = []
    if not isinstance(signoff, dict):
        return ["顶层没有 signoff 段（或不是对象）—— 签署没有落成可核验记录"]
    ids = {s.get("id") for s in samples}
    keys = set(signoff)
    missing = sorted(ids - keys)
    orphan = sorted(keys - ids)
    if missing:
        problems.append("%d 条样本没有 signoff：%r" % (len(missing), missing[:6]))
    if orphan:
        problems.append("%d 个 signoff 键在样本里不存在（孤儿）：%r"
                        % (len(orphan), orphan[:6]))
    return problems


def check_fields(samples, signoff):
    """S2：by / at / basis 三项非空。"""
    problems = []
    for s in samples:
        sid = s.get("id")
        e = signoff.get(sid) if isinstance(signoff, dict) else None
        if not isinstance(e, dict):
            continue          # S1 已报缺
        for k in REQUIRED_FIELDS:
            if not str(e.get(k) or "").strip():
                problems.append("%s 的 signoff 缺 %s" % (sid, k))
    return problems


def check_dates(samples, signoff, today=None):
    """S3：`at` 可解析且不在未来。"""
    today = today or _dt.date.today()
    problems = []
    for s in samples:
        sid = s.get("id")
        e = signoff.get(sid) if isinstance(signoff, dict) else None
        if not isinstance(e, dict):
            continue
        _, err = parse_date(e.get("at"), today=today)
        if err:
            problems.append("%s 的 signoff.at %s" % (sid, err))
    return problems


def check_required_kinds(samples, signoff):
    """S4 / S5：should_hit 与 trap_negative 的每一条都必须带 signoff。"""
    problems = []
    for s in samples:
        kind = (s.get("expected") or {}).get("kind")
        if kind not in REQUIRED_KINDS:
            continue
        sid = s.get("id")
        e = signoff.get(sid) if isinstance(signoff, dict) else None
        if not isinstance(e, dict) or not all(
                str(e.get(k) or "").strip() for k in REQUIRED_FIELDS):
            problems.append("%s（kind=%s）必须带完整 signoff —— 这一层签错方向代价最大"
                            % (sid, kind))
    return problems


def check_kind_signed(samples, signoff):
    """S6：签的层 == 盘上现在的层。

    抓的是哪种：有人改了 `expected.kind` 却把旧 signoff 原样留着
    （字段齐全 → S2 绿，id 也在 → S1 绿），于是「法务签的是不该拦，
    而盘上现在写着该拦」这种错位无人发现。
    """
    problems = []
    for s in samples:
        sid = s.get("id")
        e = signoff.get(sid) if isinstance(signoff, dict) else None
        if not isinstance(e, dict):
            continue
        signed = e.get("kind_signed")
        if signed is None:
            continue          # 老记录没有快照字段，不作假阳性（见已知盲区）
        actual = (s.get("expected") or {}).get("kind")
        if signed != actual:
            problems.append("%s 签的是 %r，而盘上现在是 %r —— 改过 kind 但没重签"
                            % (sid, signed, actual))
    return problems


def check_pinned(reg):
    """S7：GS-011 维持 should_hit，且冲突仍被记录在 signoff_meta.待裁定。

    ★ 为什么这条要单独存在：GS-011 的 `expected.kind` 同时被两件事影响 ——
      「改样本标签」与「改规则放行带」。两者都不是本脚本能替法务做的决定。
      本条只能守住「不许悄悄改掉、也不许把已记录的冲突抹掉」。
      它**不**证明冲突已解决。
    """
    problems = []
    samples = reg.get("samples") or []
    hit = [s for s in samples if s.get("id") == PINNED_ID]
    if not hit:
        return ["%s 不在样本里 —— 被守的那一条不见了" % PINNED_ID]
    kind = (hit[0].get("expected") or {}).get("kind")
    if kind != PINNED_KIND:
        problems.append(
            "%s 的 expected.kind 是 %r，而本条守的是 %r —— 若这是法务的明确裁定，"
            "必须同步：改 FROZEN_SET_FINGERPRINT + changelog + 本脚本的 PINNED_KIND + "
            "所有引用 should_hit 计数的断言与文档。**不许只改 JSON。**"
            % (PINNED_ID, kind, PINNED_KIND))

    meta = reg.get("signoff_meta") or {}
    pending = meta.get("待裁定")
    if not isinstance(pending, list) or not pending:
        problems.append(
            "signoff_meta.待裁定 为空 —— %s 与 D2 放行带的冲突没有记录在盘上" % PINNED_ID)
    else:
        named = [p for p in pending if isinstance(p, dict) and p.get("id") == PINNED_ID]
        if not named:
            problems.append(
                "signoff_meta.待裁定 里没有点名 %s —— 冲突被记在了别处或已被抹掉" % PINNED_ID)
        elif not str(named[0].get("needs") or "").strip():
            problems.append("%s 的待裁定条目没有写「需要谁确认什么」" % PINNED_ID)
    return problems


# ── 主检查 ────────────────────────────────────────────────────────────
def main(regression_path=None, today=None) -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("T-407 · 冻结回归集法务签署的存在性执行点")
    print("=" * 72)

    p = Path(regression_path) if regression_path else REGRESSION
    if not p.exists():
        print("  ⚠ 读不到回归集 %s —— 未测，不是通过" % p)
        return 2
    try:
        reg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("  ⚠ 解析失败：%s —— 未测" % exc)
        return 2

    samples = reg.get("samples") or []
    signoff = reg.get("signoff")
    today_d = _dt.date.fromisoformat(today) if today else _dt.date.today()

    cov = check_coverage(samples, signoff)
    check("S1", not cov,
          "signoff 与 %d 条样本 id 互等（无缺、无孤儿）" % len(samples)
          if not cov else str(cov[:2]))

    fld = check_fields(samples, signoff)
    check("S2", not fld,
          "每条 signoff 的 by / at / basis 三项齐全"
          if not fld else "%d 条有问题：%s" % (len(fld), fld[:2]))

    dates = check_dates(samples, signoff, today=today_d)
    check("S3", not dates,
          "每条 signoff.at 可解析且不晚于 %s" % today_d
          if not dates else "%d 条有问题：%s" % (len(dates), dates[:2]))

    n_should = sum(1 for s in samples if (s.get("expected") or {}).get("kind") == "should_hit")
    req = check_required_kinds(samples, signoff)
    check("S4/S5", not req,
          "should_hit %d 条 + trap_negative %d 条全部带完整 signoff"
          % (n_should, sum(1 for s in samples
                           if (s.get("expected") or {}).get("kind") == "trap_negative"))
          if not req else "%d 条缺：%s" % (len(req), req[:3]))

    kd = check_kind_signed(samples, signoff)
    check("S6", not kd,
          "每条 signoff.kind_signed 与盘上 expected.kind 一致"
          if not kd else "%d 条脱钩：%s" % (len(kd), kd[:3]))

    pin = check_pinned(reg)
    check("S7", not pin,
          "%s 维持 should_hit，且与 D2 的冲突仍记录在 signoff_meta.待裁定"
          % PINNED_ID if not pin else str(pin[:2]))

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 只证明：每条样本都有一条署名记录、三个字段齐全、"
          "日期可解析且不在未来、")
    print("     should_hit 与 trap_negative 两层逐条都有签署、签的层与盘上的层一致、")
    print("     且 GS-011 的冲突仍被记录着（**未被悄悄改掉或抹掉**）。")
    print("     ★ **不证明签名真实** —— 填上 by=\"法务\" 就能让本条变绿；")
    print("       真伪只能人核原件或审批流（行 86 第 ③ 段，如实留 manual）。")
    print("     ★ 不证明签署内容正确，也不证明 GS-011 那条冲突已解决。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出。**"""
    if not REGRESSION.exists():
        print("  ⚠ 真源缺失 —— 未测")
        return 2
    reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    samples = reg.get("samples") or []
    signoff = reg.get("signoff") or {}
    TODAY = _dt.date(2026, 10, 26)

    d = copy.deepcopy  # noqa: E731

    def drop(sid):
        s = d(signoff)
        s.pop(sid, None)
        return s

    def with_kind(sid, kind):
        s = d(signoff)
        s[sid]["kind_signed"] = kind
        return s

    first_should = next(s["id"] for s in samples
                        if (s.get("expected") or {}).get("kind") == "should_hit")
    first_trap = next(s["id"] for s in samples
                      if (s.get("expected") or {}).get("kind") == "trap_negative")

    def reg_with(**kw):
        r = d(reg)
        r.update(kw)
        return r

    def pending_without_pin():
        r = d(reg)
        m = d(r["signoff_meta"])
        m["待裁定"] = [p for p in m.get("待裁定") or [] if p.get("id") != PINNED_ID]
        r["signoff_meta"] = m
        return r

    cases = [
        # ── S1 覆盖 ──────────────────────────────────────────────────
        ("好样本：真实 signoff（83 条互等）", False,
         lambda: check_coverage(samples, signoff)),
        ("坏样本：删掉一条 signoff", True,
         lambda: check_coverage(samples, drop(first_should))),
        ("坏样本：signoff 段整个缺失", True,
         lambda: check_coverage(samples, None)),
        ("坏样本：多一个孤儿键", True,
         lambda: check_coverage(samples, dict(signoff, **{"GS-999": {}}))),
        ("坏样本：空 signoff 对象", True,
         lambda: check_coverage(samples, {})),

        # ── S2 字段 ──────────────────────────────────────────────────
        ("好样本：字段齐全", False,
         lambda: check_fields(samples, signoff)),
        ("坏样本：某条 basis 为空", True,
         lambda: check_fields(
             samples, dict(signoff, **{first_should: dict(signoff[first_should], basis="")}))),
        ("坏样本：某条 by 为空", True,
         lambda: check_fields(
             samples, dict(signoff, **{first_should: dict(signoff[first_should], by="  ")}))),
        ("坏样本：某条 at 为空", True,
         lambda: check_fields(
             samples, dict(signoff, **{first_should: dict(signoff[first_should], at=None)}))),

        # ── S3 日期 ──────────────────────────────────────────────────
        ("好样本：真实日期（不晚于 2026-10-26）", False,
         lambda: check_dates(samples, signoff, today=TODAY)),
        ("坏样本：日期在未来", True,
         lambda: check_dates(
             samples,
             dict(signoff, **{first_should: dict(signoff[first_should], at="2030-01-01")}),
             today=TODAY)),
        ("坏样本：日期不可解析", True,
         lambda: check_dates(
             samples,
             dict(signoff, **{first_should: dict(signoff[first_should], at="不是日期")}),
             today=TODAY)),

        # ── S4 / S5 两层必须带 ───────────────────────────────────────
        ("好样本：should_hit 与 trap_negative 都带", False,
         lambda: check_required_kinds(samples, signoff)),
        ("★ 坏样本：删掉一条 should_hit 的 signoff", True,
         lambda: check_required_kinds(samples, drop(first_should))),
        ("★ 坏样本：删掉一条 trap_negative 的 signoff", True,
         lambda: check_required_kinds(samples, drop(first_trap))),
        ("好样本：删掉一条 correctly_exempted 的 signoff 不触发本层（S1 仍会红）",
         False,
         lambda: check_required_kinds(
             samples, drop(next(s["id"] for s in samples
                                if (s.get("expected") or {}).get("kind")
                                == "correctly_exempted")))),

        # ── S6 签的层 vs 盘上的层 ───────────────────────────────────
        ("好样本：kind_signed 与 expected.kind 一致", False,
         lambda: check_kind_signed(samples, signoff)),
        ("★ 坏样本：改了 kind 没重签（kind_signed 仍是旧层）", True,
         lambda: check_kind_signed(samples, with_kind(first_should, "correctly_exempted"))),

        # ── S7 GS-011 ───────────────────────────────────────────────
        ("好样本：GS-011 维持 should_hit 且冲突有记录", False,
         lambda: check_pinned(reg)),
        ("★ 坏样本：GS-011 被悄悄改成 correctly_exempted", True,
         lambda: check_pinned(reg_with(samples=[
             dict(s, expected=dict(s["expected"], kind="correctly_exempted"))
             if s["id"] == PINNED_ID else s for s in samples]))),
        ("★ 坏样本：待裁定 里没点名 GS-011（冲突被抹掉）", True,
         lambda: check_pinned(pending_without_pin())),
        ("坏样本：待裁定 为空", True,
         lambda: check_pinned(reg_with(signoff_meta=dict(reg["signoff_meta"], 待裁定=[])))),
        ("坏样本：GS-011 从样本里消失", True,
         lambda: check_pinned(reg_with(samples=[
             s for s in samples if s["id"] != PINNED_ID]))),
    ]

    print("=" * 72)
    print("verify_regression_signoff · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-52s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 70)
    bad = 0
    for name, want_red, fn in cases:
        try:
            problems = fn()
            got_red = bool(problems)
            note = "" if got_red == want_red else "  ← " + str(problems[:2])[:70]
        except Exception as exc:  # noqa: BLE001
            got_red, note = None, "  对照自身异常：%s" % exc
        ok = (got_red is not None and got_red == want_red)
        bad += int(not ok)
        print("  %-52s %-6s %-6s %s%s"
              % (name[:52],
                 "红" if want_red else "绿",
                 "异常" if got_red is None else ("红" if got_red else "绿"),
                 "✓" if ok else "✗", note))

    print("-" * 72)
    if bad:
        print("❌ %d/%d 与预判不符 —— 差异那几行就是该查的地方" % (bad, len(cases)))
        return 1
    print("✅ %d/%d 预判全部命中（含两条「删 should_hit / 删 trap_negative 必须红」）"
          % (len(cases), len(cases)))
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--today", default=None,
                    help="注入「今天」用于反向对照（不落任何状态，§2.4.3）")
    args, unknown = ap.parse_known_args(argv)
    if unknown:
        print("  ⚠ 未知参数 %s —— 未测（不是通过）" % unknown)
        raise SystemExit(2)
    if args.today:
        try:
            _dt.date.fromisoformat(args.today)
        except ValueError:
            print("  ⚠ --today=%r 不是日期 —— 未测" % args.today)
            raise SystemExit(2)
    return args


if __name__ == "__main__":
    try:
        a = _parse_args(sys.argv[1:])
        if a.controls:
            sys.exit(run_controls())
        sys.exit(main(today=a.today))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s: %s" % (type(exc).__name__, exc))
        sys.exit(2)
