#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_coverage_composer.py —— coverage_composer 的契约验收（Playbook §3.3.5 / L1-6）

五条必须成立（每条都要能红）：
  A. 四项覆盖证明必填
  B. 三态派生：missing / partial / full 的边界
  C. 空族记「未做·无控制点」，**不得**记 not_applicable
  D. parse_status=failed → missing（不是 partial）
  E. partial 永不 PASS

★ 特别说明一条测试设计：
  当前主表有 4 个空族，按规则每份内容都是 partial —— 所以「full 分支」在真实数据下
  **不可达**。如果不单独测 full，全拦的实现也会全绿。
  因此本文件用「空族=[]」注入一份无空族的场景，专门测 full 分支；
  同时用「空族=真实四族」测 partial。两组都必须存在。

退出码：0 全绿 / 1 有红 / 2 未测（import 不到或主表读不到）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.coverage_composer import (  # noqa: E402
        CoverageRejected, compose, check, derive_state, compose_and_derive,
        may_pass, load_empty_families, load_all_families, REASONS,
    )
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import coverage_composer 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(2)

try:
    REAL_EMPTY = load_empty_families()
    REAL_FAMILIES = load_all_families()
except CoverageRejected as e:
    print(f"⚠ 未测：主表读不到（{e}）—— 空族未知时无法验「空族记未做」这一条", file=sys.stderr)
    sys.exit(2)


def base_kwargs(**over) -> dict:
    """一份齐全的覆盖证明输入。默认用「无空族」以便测 full；测 partial 时显式传真实空族。"""
    kw = dict(
        modalities_evaluated=["text"],
        rules_version={"version": "r-1.2", "fingerprint": "sha256:abc"},
        control_points_by_family={f: "ran" for f in REAL_FAMILIES},
        not_run_reasons=[],
        does_not_cover=[],
        empty_families=[],
    )
    kw.update(over)
    return kw


def expect_reject(name, fn, want_code=None):
    try:
        fn()
    except CoverageRejected as e:
        ok = (want_code is None) or (e.code == want_code)
        return (name, ok, f"拒收 {e.code}" + ("" if ok else f"（期望 {want_code}）"))
    except Exception as e:  # noqa: BLE001
        return (name, False, f"抛了非 CoverageRejected：{type(e).__name__}: {e}")
    return (name, False, "**没有拒收** —— 这条断言是假的")


def expect_state(name, kwargs, want_state, *, parse_status="ok", all_families=None):
    try:
        r = compose_and_derive(parse_status=parse_status, all_families=all_families, **kwargs)
    except Exception as e:  # noqa: BLE001
        return (name, False, f"抛错：{type(e).__name__}: {e}")
    got = r["coverage_state"]
    return (name, got == want_state, f"期望 {want_state}，实际 {got}")


def main() -> int:
    results = []

    # ══════════ A. 四项必填 ══════════
    for key in ("modalities_evaluated", "rules_version",
                "control_points_by_family", "not_run_reasons"):
        def mk(k=key):
            kw = base_kwargs()
            cov = compose(**kw)
            cov.pop(k)
            return lambda: derive_state(cov)
        results.append((f"A 缺 {key} → missing",
                        mk()() == "missing", "缺字段应落 missing"))

    # A2：评过模态为空 → missing（不是 partial）
    results.append(expect_state("A2 评过模态为空 → missing",
                                base_kwargs(modalities_evaluated=[]), "missing"))

    # A3：规则版本缺指纹 → missing
    results.append(expect_state("A3 规则版本缺指纹 → missing",
                                base_kwargs(rules_version={"version": "r-1.2"}), "missing"))

    # A4：规则版本缺 version → missing
    results.append(expect_state("A4 规则版本缺 version → missing",
                                base_kwargs(rules_version={"fingerprint": "sha256:abc"}), "missing"))

    # ══════════ B. 三态边界 ══════════
    # B1：干净样本（无空族）→ full ★ 防全拦
    results.append(expect_state("B1 干净样本（空族=[]）→ full",
                                base_kwargs(), "full",
                                all_families=REAL_FAMILIES))

    # B2：真实四空族 → partial
    results.append(expect_state("B2 真实四空族 → partial",
                                base_kwargs(empty_families=REAL_EMPTY), "partial",
                                all_families=REAL_FAMILIES))

    # B3：有未跑项 → partial
    results.append(expect_state("B3 not_run_reasons 非空 → partial",
                                base_kwargs(not_run_reasons=[
                                    {"what": "画面语义", "why": "no_capability"}]),
                                "partial"))

    # B4：does_not_cover 非空 → partial
    results.append(expect_state("B4 does_not_cover 非空 → partial",
                                base_kwargs(does_not_cover=["区域级未审"]), "partial"))

    # B5：逐族有 not_run → partial
    kw = base_kwargs()
    kw["control_points_by_family"] = {f: ("not_run" if f == REAL_FAMILIES[0] else "ran")
                                      for f in REAL_FAMILIES}
    results.append(expect_state("B5 某族 not_run → partial", kw, "partial"))

    # ══════════ C. 空族 ══════════
    # C1：空族自动补 no_control_points
    def c1():
        cov = compose(**base_kwargs(empty_families=REAL_EMPTY))
        whys = {r.get("what"): r.get("why") for r in cov["not_run_reasons"]}
        for f in REAL_EMPTY:
            assert whys.get(f) == "no_control_points", f"{f} 的 why={whys.get(f)!r}"
    try:
        c1(); results.append(("C1 空族自动补 no_control_points", True, "通过"))
    except AssertionError as e:
        results.append(("C1 空族自动补 no_control_points", False, str(e)))

    # C2：空族带「未做·无控制点」标签
    def c2():
        cov = compose(**base_kwargs(empty_families=REAL_EMPTY))
        labels = {r.get("what"): r.get("label") for r in cov["not_run_reasons"]}
        for f in REAL_EMPTY:
            assert labels.get(f) == "未做·无控制点", f"{f} 标签={labels.get(f)!r}"
    try:
        c2(); results.append(("C2 空族标签=未做·无控制点", True, "通过"))
    except AssertionError as e:
        results.append(("C2 空族标签=未做·无控制点", False, str(e)))

    # C3：空族即使调用方写 ran，也强制改 not_run
    def c3():
        cov = compose(**base_kwargs(empty_families=REAL_EMPTY))
        for f in REAL_EMPTY:
            assert cov["control_points_by_family"][f] == "not_run", \
                f"{f} 被写成 {cov['control_points_by_family'][f]}"
    try:
        c3(); results.append(("C3 空族强制 not_run（调用方写 ran 也改）", True, "通过"))
    except AssertionError as e:
        results.append(("C3 空族强制 not_run（调用方写 ran 也改）", False, str(e)))

    # C4：★ 空族记 not_applicable → 必须红
    def c4():
        cov = compose(**base_kwargs(empty_families=REAL_EMPTY))
        for r in cov["not_run_reasons"]:
            r["why"] = "not_applicable"
        check(cov)
    results.append(expect_reject("C4 空族记 not_applicable → 红", c4, "E_NOT_APPLICABLE"))

    # C5：未知 reason → 红
    def c5():
        cov = compose(**base_kwargs())
        cov["not_run_reasons"] = [{"what": "x", "why": "随便写的"}]
        check(cov)
    results.append(expect_reject("C5 unknown reason → 红", c5, "E_REASON"))

    # ══════════ D. parse_status ══════════
    results.append(expect_state("D1 parse_status=failed → missing（不是 partial）",
                                base_kwargs(empty_families=REAL_EMPTY), "missing",
                                parse_status="failed"))
    results.append(expect_state("D2 parse_status=partial → missing",
                                base_kwargs(empty_families=REAL_EMPTY), "missing",
                                parse_status="partial"))

    # ══════════ E. partial 永不 PASS ══════════
    def e1():
        assert may_pass("full") is True, "full 应够格"
        assert may_pass("partial") is False, "partial 不许 PASS（L1-6）"
        assert may_pass("missing") is False, "missing 不许 PASS"
    try:
        e1(); results.append(("E1 may_pass：full✓ partial✗ missing✗", True, "通过"))
    except AssertionError as e:
        results.append(("E1 may_pass：full✓ partial✗ missing✗", False, str(e)))

    # ══════════ 反向对照（五条必红）══════════
    # R1：空族记 not_applicable → 红（与 C4 同，但用 compose_and_derive 全链路）
    def r1():
        cov = compose(**base_kwargs(empty_families=REAL_EMPTY))
        for r in cov["not_run_reasons"]:
            r["why"] = "not_applicable"
        check(cov, all_families=REAL_FAMILIES)
    results.append(expect_reject("R1 全链路：空族 not_applicable → 红", r1, "E_NOT_APPLICABLE"))

    # R2：有未跑项却判 full → 红（这里「红」的形式是：state 不是 full）
    def r2():
        kw = base_kwargs(empty_families=REAL_EMPTY)
        st = compose_and_derive(all_families=REAL_FAMILIES, **kw)["coverage_state"]
        assert st != "full", f"有 4 个空族却判了 {st}"
    try:
        r2(); results.append(("R2 有未跑项→不许判 full", True, "通过"))
    except AssertionError as e:
        results.append(("R2 有未跑项→不许判 full", False, str(e)))

    # R3：缺规则版本指纹 → **必须落 missing**（不是 full，也不是拒收）
    # ★ 2026-10-18 更正：原先写成「拒收」。按 §3.3.5，缺字段是 `missing` **状态**，
    #   不是写法错误 —— 在 check() 里抛错会让「我说不清我做了什么」无法被表达。
    def r3():
        st = derive_state(compose(**base_kwargs(rules_version={"version": "r-1.2"})))
        assert st == "missing", f"缺指纹应落 missing，实际 {st}"
        st2 = derive_state(compose(**base_kwargs(rules_version={"fingerprint": "sha256:abc"})))
        assert st2 == "missing", f"缺 version 应落 missing，实际 {st2}"
        assert not may_pass("missing"), "missing 不许 PASS"
    try:
        r3(); results.append(("R3 缺规则版本指纹/号 → missing（不许拒收也不许 full）", True, "通过"))
    except AssertionError as e:
        results.append(("R3 缺规则版本指纹/号 → missing（不许拒收也不许 full）", False, str(e)))

    # R4：failed 判 partial → 红
    def r4():
        st = compose_and_derive(parse_status="failed",
                                all_families=REAL_FAMILIES,
                                **base_kwargs(empty_families=REAL_EMPTY))["coverage_state"]
        assert st == "missing", f"failed 应判 missing，实际 {st}"
    try:
        r4(); results.append(("R4 failed 必须判 missing（不许 partial）", True, "通过"))
    except AssertionError as e:
        results.append(("R4 failed 必须判 missing（不许 partial）", False, str(e)))

    # R5：合法干净样本 → full 通过（防全拦）
    def r5():
        st = compose_and_derive(all_families=REAL_FAMILIES,
                                **base_kwargs())["coverage_state"]
        assert st == "full", f"干净样本应 full，实际 {st}"
        assert may_pass(st) is True, "full 应够格 PASS"
    try:
        r5(); results.append(("R5 干净样本 → full 且够格（防全拦）", True, "通过"))
    except AssertionError as e:
        results.append(("R5 干净样本 → full 且够格（防全拦）", False, str(e)))

    # R6：逐族漏写 → 红
    def r6():
        kw = base_kwargs()
        kw["control_points_by_family"] = {REAL_FAMILIES[0]: "ran"}
        cov = compose(**kw)
        check(cov, all_families=REAL_FAMILIES)
    results.append(expect_reject("R6 逐族漏写 → 红", r6, "E_FAMILY_MISSING"))

    # ── 汇总 ──
    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 70)
    print("coverage_composer 契约验收")
    print("=" * 70)
    print(f"  主表空族（真实）：{REAL_EMPTY}")
    print(f"  七族：{REAL_FAMILIES}")
    print(f"  ★ 真实数据下 full 不可达（空族计入 partial）—— 故用空族=[] 单独测 full 分支")
    print()
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name:<48} {detail}")
    print()
    if ok == total:
        print(f"✅ {ok}/{total} 项全过")
        return 0
    reds = [n for n, p, _ in results if not p]
    print(f"✗ {ok}/{total} 项通过；红项：{reds}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
