#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_finding_store.py —— finding_store 的契约验收（L2-5 / §3.3.4.1 / §3.3.4.2）

七条必须同时成立：
  A. append-only —— 实质变化新建一条、旧条只标 superseded、其余字段不动、produced_by 保持
  B. 三要素合取 —— control_code / authority_ref / location 缺一拒收
  C. finding_id 全局唯一 —— 重放账本也不许碰撞
  D. produced_by × status 白名单 —— 表外组合拒收
  E. 行 16 补强（2026-10-24）—— finding_id 非空字符串、derived_from 是 string|null、
     全量账本无自指/悬空指针（mutprobe 实测 E_ID/E_TYPE 守卫关掉后 33/33 仍全绿）
  F. 行 17 补强（2026-10-24）—— 枚举负样本（pending/unknown/model/system）、
     12 组合穷举、ALLOWED 表结构钉（mutprobe 实测两处塞宽都全绿）
  G. 行 23 补强（2026-10-24）—— 唯一判定表 15 链 + I4 逐格对拍独立期望表
     （mutprobe 实测链7/链14/I4 三处改坏本验证器全绿）

**每一条都要能在反向对照里变红。** 没红过的断言不算验证过它（AGENTS §2.4.1）。
★ 枚举期望值**写死在本文件**，不 import 生产常量 —— 读死常量的断言拦不住
  「常量自己被改宽」（mutprobe 实测：VALID_STATUS / ALLOWED 塞进 "pending" 都绿）。
★ 枚举负样本直接喂生产 check_record，**不包验证器自己的闸** —— 包一层会把
  生产代码挡在变异探针够不到的地方，等于白测。

--controls：E/F/G 三组新断言的反向对照（好样本必须绿、坏样本必须红）。

退出码：0 全绿 / 1 有红 / 2 未测（模块 import 不到）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.finding_store import (  # noqa: E402
        FindingStore, FindingRejected, ALLOWED, check_record,
    )
    from base.decision_table import decide  # noqa: E402  （行 23 G 段对拍用）
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import finding_store/decision_table 失败（{type(e).__name__}: {e}）"
          f"—— 未测不是通过", file=sys.stderr)
    sys.exit(2)


def base_finding(**over) -> dict:
    """一条合法的 confirmed，逐条反向对照都从它出发改一个字段。"""
    rec = {
        "finding_id": "f-1",
        "control_code": "H01",
        "detected_by": "P0",
        "authority_ref": [{"entry_id": "EXT-021", "article": "S7-03"}],
        "authority_state": "ok",
        "severity": "L4",
        "status": "confirmed",
        "location": {"char_start": 0, "char_end": 10},
        "quote": "治愈疾病",
        "produced_by": "rule",
        "derived_from": None,
    }
    rec.update(over)
    return rec


# ── 行 16/17/23 补强用的构件（main 与 --controls 共用）────────────────
# ★ 期望值写死在本文件（判据原文的口径），不从生产代码导入 —— 见文件头。

# 行 17 的独立期望：status / produced_by 取值域（验收行 17 原文）
EXPECTED_STATUSES = frozenset({"candidate", "confirmed", "rejected", "superseded"})
EXPECTED_PRODUCED_BY = frozenset({"rule", "semantic", "human"})
# 行 17 的独立期望：白名单表逐格（「semantic 接受 candidate/rejected/superseded
# 以及满足 C1-C4 的 confirmed」—— C1-C4 的 confirmed 由 M1 标记另测）
EXPECTED_ALLOWED = {
    "rule": frozenset({"confirmed", "rejected", "superseded"}),
    "semantic": frozenset({"candidate", "confirmed", "rejected", "superseded"}),
    "human": frozenset({"confirmed", "rejected", "superseded"}),
}


def allowed_problems(actual: dict) -> list:
    """行 17 结构钉：生产 ALLOWED 必须逐格等于判据原文的表（空 = 一致）。"""
    problems = []
    for pb in sorted(set(EXPECTED_ALLOWED) | set(actual)):
        want = EXPECTED_ALLOWED.get(pb)
        got = actual.get(pb)
        if got is None:
            problems.append(f"生产 ALLOWED 缺 producer `{pb}`")
        elif want is None:
            problems.append(f"生产 ALLOWED 多出 producer `{pb}`: {sorted(got)}")
        elif got != want:
            problems.append(f"ALLOWED[`{pb}`] 期望 {sorted(want)}，实际 {sorted(got)}")
    return problems


def df_scan_problems(records) -> list:
    """行 16 的账本指针扫描：自指 / 悬空 / 非串，逐条报出（空 = 干净）。"""
    ids = {r.get("finding_id") for r in records}
    problems = []
    for r in records:
        fid = r.get("finding_id")
        df = r.get("derived_from")
        if df is None:
            continue
        if not isinstance(df, str):
            problems.append(f"{fid!r} 的 derived_from 非串非null: {df!r}")
        elif df == fid:
            problems.append(f"{fid!r} 的 derived_from 指向自身（自指）")
        elif df not in ids:
            problems.append(f"{fid!r} 的 derived_from 悬空（账本无此 id）: {df!r}")
    return problems


def dt_inp(parse="ok", fk=None, cov="full", findings=None, **over) -> dict:
    """行 23 对拍用的 decide 输入。"""
    inp = {"parse_status": parse, "failure_kind": fk,
           "coverage_state": cov, "findings": list(findings or [])}
    inp.update(over)
    return inp


def dconf(fid, sev, auth="ok", status="confirmed", **over) -> dict:
    """行 23 对拍用的 finding。authority_state 只有 confirmed 才带。"""
    f = {"finding_id": fid, "status": status, "severity": sev}
    if status == "confirmed":
        f["authority_state"] = auth
    f.update(over)
    return f


# 行 23 的独立期望表：15 条链 + I4，每行 (chain, state, layer, 输入工厂)。
# 手写自 Playbook §3.3.8.1 链序；L1–L5 各至少一格、L0 走 I4。
EXPECTED_TABLE = (
    (1, "未审查", "DP0", lambda: dt_inp(cov="missing")),
    (2, "未审查", "DP0", lambda: dt_inp(parse="failed", fk="unsupported")),
    (3, "未审查", "DP0", lambda: dt_inp(parse="failed", fk="parse_error")),
    (4, "REVIEW", "DP4", lambda: dt_inp(rule_conflict=True)),
    (5, "REVIEW", "DP4", lambda: dt_inp(findings=[dconf("c5", "L5", auth="conflict")])),
    (6, "REVIEW", "DP3", lambda: dt_inp(findings=[dconf("c6", "L4", auth="missing")])),
    (7, "BLOCK", "DP2", lambda: dt_inp(findings=[dconf("c7", "L4")])),
    (8, "REVIEW", "DP3", lambda: dt_inp(findings=[dconf("c8", "L3", auth="missing")])),
    (9, "REVIEW", "DP3", lambda: dt_inp(findings=[dconf("c9", "L3")])),
    (10, "REVIEW", "DP3", lambda: dt_inp(findings=[dconf("c10", "L1", auth="expired")])),
    (11, "REVIEW", "DP3", lambda: dt_inp(cov="partial")),
    (12, "REVIEW", "DP3", lambda: dt_inp(parse="partial")),
    (13, "REVIEW", "DP3", lambda: dt_inp(findings=[dconf("c13", "L2", status="candidate")])),
    (14, "待自决", "DP1", lambda: dt_inp(findings=[dconf("c14", "L2")])),
    (15, "PASS", "DP1", lambda: dt_inp()),
)


def dt_expect_problems(decide_fn, table=None) -> list:
    """把期望表逐行喂给一个 decide 实现，返回不一致清单（空 = 全一致）。"""
    problems = []
    for chain, state, layer, mk in (table if table is not None else EXPECTED_TABLE):
        try:
            r = decide_fn(mk())
        except Exception as e:  # noqa: BLE001
            problems.append(f"chain{chain} 抛 {type(e).__name__}: {e}")
            continue
        got = (r.get("chain"), r.get("state"), r.get("layer"))
        if got != (chain, state, layer):
            problems.append(f"chain{chain} 期望 {(chain, state, layer)}，实际 {got}")
    r0 = decide_fn(dt_inp(findings=[dconf("c0", "L0")]))
    if r0.get("run_state") != "ERROR" or r0.get("invariant_violation") != "I4":
        problems.append(f"confirmed L0 期望 ERROR/I4，实际 "
                        f"{r0.get('run_state')!r}/{r0.get('invariant_violation')!r}")
    return problems


# 行 17 穷举：3×4=12 组合的期望（判据原文：恰好 rule/human 的 candidate 拒）
EXHAUSTIVE_PB_ST = (
    ("rule", "confirmed", True), ("rule", "candidate", False),
    ("rule", "rejected", True), ("rule", "superseded", True),
    ("semantic", "candidate", True), ("semantic", "confirmed", True),
    ("semantic", "rejected", True), ("semantic", "superseded", True),
    ("human", "confirmed", True), ("human", "candidate", False),
    ("human", "rejected", True), ("human", "superseded", True),
)


def exhaustive_whitelist_problems(check_fn) -> list:
    """12 组合逐个喂 check_fn；应收被拒 / 应拒被收 / 拒收码不对 都记红。"""
    bad = []
    for pb, st, should_pass in EXHAUSTIVE_PB_ST:
        extra = ({"confirmed_by_rule_class": True}
                 if (pb, st) == ("semantic", "confirmed") else {})
        rec = base_finding(produced_by=pb, status=st, **extra)
        try:
            check_fn(rec)
        except FindingRejected as e:
            if should_pass:
                bad.append(f"`{pb}`×`{st}` 应收被拒（{e.code}）")
            elif e.code != "E_WHITELIST":
                bad.append(f"`{pb}`×`{st}` 拒收码 {e.code} ≠ E_WHITELIST")
        else:
            if not should_pass:
                bad.append(f"`{pb}`×`{st}` 应拒被收")
    return bad


def expect_reject(name: str, fn, want_code: str | None = None) -> tuple[str, bool, str]:
    """喂一个应当被拒的样本；拒了且错误码对得上才算过。"""
    try:
        fn()
    except FindingRejected as e:
        ok = (want_code is None) or (e.code == want_code)
        return (name, ok, f"拒收 {e.code}"
                + ("" if ok else f"（期望 {want_code}）"))
    except Exception as e:  # noqa: BLE001
        return (name, False, f"抛了非 FindingRejected：{type(e).__name__}: {e}")
    return (name, False, "**没有拒收** —— 这条断言是假的")


def expect_ok(name: str, fn) -> tuple[str, bool, str]:
    try:
        fn()
        return (name, True, "通过")
    except Exception as e:  # noqa: BLE001
        return (name, False, f"不该拒却拒了：{type(e).__name__}: {e}")


def main() -> int:
    results = []

    # ═══════════ A. append-only ═══════════
    def a1():
        s = FindingStore()
        old = s.insert(base_finding())
        new = s.transition(old["finding_id"], new_status="rejected")
        assert new["finding_id"] != old["finding_id"], "新条目必须新 id"
        assert new["derived_from"] == old["finding_id"], "derived_from 必须指旧 id"
        after = s.get(old["finding_id"])
        assert after["status"] == "superseded", f"旧条应标 superseded，实际 {after['status']}"
        assert after["produced_by"] == old["produced_by"], "旧条 produced_by 必须保持原值"
        # 判断内容一个字段都不许变
        for k in ("control_code", "severity", "quote", "detected_by",
                  "authority_ref", "authority_state"):
            assert after[k] == old[k], f"旧条 {k} 被改了：{old[k]} → {after[k]}"
    results.append(expect_ok("A1 状态变化新建一条 / 旧条只标 superseded", a1))

    # A1b：旧条除 status 外逐字段不变（显式对比整条，不只挑几个）
    def a1b():
        s = FindingStore()
        old = dict(s.insert(base_finding()))
        s.transition(old["finding_id"], new_status="rejected")
        after = s.get(old["finding_id"])
        diff = {k: (old[k], after.get(k)) for k in old if old[k] != after.get(k)}
        assert set(diff) == {"status"}, f"除 status 外还有字段变了：{diff}"
    results.append(expect_ok("A1b 旧条除 status 外零字段变化", a1b))

    # A2：账本是纯追加（事件序列里没有「改字段」这种 op）
    def a2():
        s = FindingStore()
        old = s.insert(base_finding())
        s.transition(old["finding_id"], new_status="rejected")
        ops = [e["op"] for e in s.events()]
        assert ops == ["append", "append", "supersede"], f"事件序列异常：{ops}"
    results.append(expect_ok("A2 账本事件只有 append/supersede", a2))

    # A3：已 superseded 的条目不能再被派生
    def a3():
        s = FindingStore()
        old = s.insert(base_finding())
        s.transition(old["finding_id"], new_status="rejected")
        s.transition(old["finding_id"], new_status="confirmed")
    results.append(expect_reject("A3 已死的条目不许再派生", a3, "E_ALREADY_SUPERSEDED"))

    # ═══════════ FS-ADV1 / FS-ADV2 / FS-ADV3（变异审计抓出的存活假绿）═══════════
    # ADV1：REQUIRED_KEYS 原先定义了却从不迭代 → 缺 quote / 缺 derived_from 都能过
    def adv1a():
        r = base_finding()
        r.pop("quote")
        check_record(r)
    results.append(expect_reject("ADV1a 缺 quote", adv1a, "E_REQUIRED"))

    def adv1b():
        r = base_finding()
        r.pop("derived_from")
        check_record(r)
    results.append(expect_reject("ADV1b 缺 derived_from", adv1b, "E_REQUIRED"))

    def adv1c():
        check_record(base_finding(quote="   "))
    results.append(expect_reject("ADV1c quote 是空白串", adv1c, "E_REQUIRED"))

    # ADV2：active() 零覆盖 —— 改成恒返回 [] 仍 25/25 绿
    def adv2():
        s = FindingStore()
        confirmed = s.insert(base_finding(finding_id="a-c", status="confirmed"))
        candidate = s.insert(base_finding(finding_id="a-cand", produced_by="semantic",
                                          status="candidate"))
        rejected = s.insert(base_finding(finding_id="a-r", status="rejected"))
        # superseded 需要由 transition 产生
        sup_src = s.insert(base_finding(finding_id="a-src"))
        s.transition(sup_src["finding_id"], new_status="rejected")  # 旧条变 superseded

        act = {r["finding_id"] for r in s.active()}
        assert confirmed["finding_id"] in act, "confirmed 应参与状态计算"
        assert candidate["finding_id"] in act, "candidate 应参与状态计算（作 REVIEW 门）"
        assert rejected["finding_id"] not in act, "rejected 不参与"
        assert sup_src["finding_id"] not in act, "superseded 不参与"
        assert len(act) == 2, f"active() 应恰好 2 条，实际 {len(act)}：{act}"
    results.append(expect_ok("ADV2 active() 只含 confirmed+candidate", adv2))

    def adv2b():
        # 反向：全被取代后 active() 必须为空（防「恒返回全部」）
        s = FindingStore()
        a = s.insert(base_finding(finding_id="b-1"))
        s.transition(a["finding_id"], new_status="rejected")
        assert s.active() == [], f"全被取代后应空，实际 {s.active()}"
    results.append(expect_ok("ADV2b 全 superseded 后 active() 为空", adv2b))

    # ADV3：semantic 直接 confirmed 必须带 confirmed_by_rule_class=True（M1）
    def adv3a():
        r = base_finding(produced_by="semantic", status="confirmed")
        check_record(r)   # 缺 confirmed_by_rule_class
    results.append(expect_reject("ADV3a semantic+confirmed 缺 M1 标记", adv3a, "E_M1"))

    def adv3b():
        check_record(base_finding(produced_by="semantic", status="confirmed",
                                  confirmed_by_rule_class=False))
    results.append(expect_reject("ADV3b M1 标记为 False", adv3b, "E_M1"))

    def adv3c():
        # 正向：带了 True 就要过；且 rule 产出的 confirmed 不需要这个标记
        check_record(base_finding(produced_by="semantic", status="confirmed",
                                  confirmed_by_rule_class=True))
        check_record(base_finding(produced_by="rule", status="confirmed"))
        # semantic 产 candidate 也不需要
        check_record(base_finding(produced_by="semantic", status="candidate"))
    results.append(expect_ok("ADV3c M1=True 过 / rule 不要求 / candidate 不要求", adv3c))

    # ═══════════ B. 三要素合取 ═══════════
    for key in ("control_code", "authority_ref", "location"):
        def mk(k=key):
            r = base_finding()
            r.pop(k)
            return lambda: check_record(r)
        results.append(expect_reject(f"B 缺三要素：{key}", mk(), "E_ADMISSION"))

    # B2：authority_ref 为空数组**合法**（真的没有依据 ≠ 还没算过）
    def b2():
        check_record(base_finding(authority_ref=[], authority_state="missing"))
    results.append(expect_ok("B2 authority_ref=[] 合法（不是缺字段）", b2))

    # B3：confirmed 缺 authority_state → 拒（DraftFinding）
    def b3():
        r = base_finding()
        r.pop("authority_state")
        check_record(r)
    results.append(expect_reject("B3 DraftFinding（confirmed 无 authority_state）", b3, "E_DRAFT"))

    # B3b：candidate / rejected 不要求 authority_state
    def b3b():
        r = base_finding(produced_by="semantic", status="candidate")
        r.pop("authority_state")
        check_record(r)
        r2 = base_finding(status="rejected")
        r2.pop("authority_state")
        check_record(r2)
    results.append(expect_ok("B3b candidate/rejected 不要求 authority_state", b3b))

    # ═══════════ C. finding_id 唯一 ═══════════
    def c1():
        s = FindingStore()
        s.insert(base_finding(finding_id="dup"))
        s.insert(base_finding(finding_id="dup"))
    results.append(expect_reject("C1 同 id 两条", c1, "E_DUP_ID"))

    # C2：重放账本也不许碰撞 —— 写盘 → 读回 → 再写同一个 id
    def c2():
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            s1 = FindingStore(p)
            s1.insert(base_finding(finding_id="persist-1"))
            s2 = FindingStore(p)          # 从盘上读回
            assert s2.get("persist-1") is not None, "读回失败"
            s2.insert(base_finding(finding_id="persist-1"))   # 重放碰撞
    results.append(expect_reject("C2 重放账本后同 id 仍需拒", c2, "E_DUP_ID"))

    # C3：id 生成器撞了也要拒
    def c3():
        s = FindingStore(id_factory=lambda: "fixed")
        s.insert({"control_code": "H01", "detected_by": "P0",
                  "authority_ref": [], "authority_state": "ok", "severity": "L4",
                  "status": "confirmed", "location": {"char_start": 0},
                  "quote": "q", "produced_by": "rule", "derived_from": None},
                 assign_id=True)
        s.insert({"control_code": "H01", "detected_by": "P0",
                  "authority_ref": [], "authority_state": "ok", "severity": "L4",
                  "status": "confirmed", "location": {"char_start": 0},
                  "quote": "q", "produced_by": "rule", "derived_from": None},
                 assign_id=True)
    results.append(expect_reject("C3 id 生成器碰撞", c3, "E_DUP_ID"))

    # ═══════════ D. produced_by × status 白名单 ═══════════
    # ★ semantic×confirmed 现在多了 M1 守卫（必须带 confirmed_by_rule_class=true），
    #   所以这一格的合法样本要带上那个标记 —— 否则测的就不再是「白名单」而是「M1」。
    #   M1 自身另有 ADV3a/3b/3c 三条专门测。
    for pb, st, should_pass, extra in [
        ("rule", "confirmed", True, {}),
        ("rule", "candidate", False, {}),
        ("semantic", "candidate", True, {}),
        ("semantic", "confirmed", True, {"confirmed_by_rule_class": True}),
        ("human", "confirmed", True, {}),
        ("human", "candidate", False, {}),
        ("human", "superseded", True, {}),
    ]:
        def mk(pb=pb, st=st, extra=extra):
            return lambda: check_record(base_finding(produced_by=pb, status=st, **extra))
        if should_pass:
            results.append(expect_ok(f"D `{pb}`×`{st}` 合法", mk()))
        else:
            results.append(expect_reject(f"D `{pb}`×`{st}` 表外", mk(), "E_WHITELIST"))

    # ═══════════ E. 行 16 补强：finding_id / derived_from ═══════════
    # ★ mutprobe 实测（2026-10-24）：E_ID 守卫（16a）与 E_TYPE 守卫（16c）
    #   关掉后 33/33 仍全绿 —— 原验证器 0 处断言类型。此处直接喂负样本。

    # E1：finding_id 非空字符串（int / None / 空白串 / 缺失 → E_ID）
    for bad_fid in (123, None, "   ", ""):
        def mk_fid(v=bad_fid):
            return lambda: check_record(base_finding(finding_id=v))
        results.append(expect_reject(f"E1 finding_id={bad_fid!r} 必须拒", mk_fid(), "E_ID"))

    # E2：derived_from 类型必须是 string|null（123 / {} / [] → E_TYPE）
    for bad_df in (123, {}, ["f-0"], True):
        def mk_df(v=bad_df):
            return lambda: check_record(base_finding(derived_from=v))
        results.append(expect_reject(f"E2 derived_from={bad_df!r} 必须拒", mk_df(), "E_TYPE"))

    # E3：derived_from=null 是合法形态（新建 finding）
    results.append(expect_ok(
        "E3 derived_from=null 合法（新建条目）",
        lambda: check_record(base_finding(derived_from=None))))

    # E4：全量账本扫描 —— 无自指 / 无悬空（好账本零红）
    def e4():
        s = FindingStore()
        a = s.insert(base_finding(finding_id="e4-a"))
        s.transition(a["finding_id"], new_status="rejected")   # derived_from 指向 e4-a
        records = [s.get(i) for i in s.all_ids()]
        problems = df_scan_problems(records)
        assert problems == [], f"好账本不该报问题：{problems}"
    results.append(expect_ok("E4 好账本指针扫描零红", e4))

    # E4b：自指必须被扫描构件报出（反向对照：扫描器不许恒绿）
    def e4b():
        r = base_finding(finding_id="e4b-self", derived_from="e4b-self")
        problems = df_scan_problems([r])
        assert problems, "自指指针必须被报出"
        assert "自指" in problems[0], f"报出原因不对：{problems[0]}"
    results.append(expect_ok("E4b 扫描构件必须报出自指", e4b))

    # E4c：悬空必须被扫描构件报出（反向对照）
    def e4c():
        r = base_finding(finding_id="e4c-1", derived_from="ghost-id")
        problems = df_scan_problems([r])
        assert problems, "悬空指针必须被报出"
        assert "悬空" in problems[0], f"报出原因不对：{problems[0]}"
    results.append(expect_ok("E4c 扫描构件必须报出悬空", e4c))

    # E4d：derived_from 指向真实存在的 id —— transition 产生的账本满足（判据原文）
    def e4d():
        s = FindingStore()
        a = s.insert(base_finding(finding_id="e4d-a"))
        b = s.transition(a["finding_id"], new_status="rejected")
        assert b["derived_from"] == a["finding_id"], "新条必须指旧 id"
        assert a["finding_id"] in s.all_ids(), "被指的 id 必须真实存在"
    results.append(expect_ok("E4d derived_from 指向存在且在账本的 id", e4d))

    # ═══════════ F. 行 17 补强：枚举 + 白名单 ═══════════
    # ★ mutprobe 实测：VALID_STATUS 塞 "pending"（17a）/ semantic 白名单塞宽
    #   （17b）后 33/33 仍全绿 —— 取值域负样本与穷举两层都缺。
    #   期望值写死 EXPECTED_*，不 import 生产常量。

    # F1：status 域外负样本 → E_ENUM（判据原文点名 pending/unknown/model/system）
    for bad_st in ("pending", "unknown", "model", "system"):
        def mk_st(v=bad_st):
            return lambda: check_record(base_finding(status=v))
        results.append(expect_reject(f"F1 status={bad_st!r} 必须拒（E_ENUM）", mk_st(), "E_ENUM"))

    # F2：produced_by 域外负样本 → E_ENUM
    for bad_pb in ("model", "system", "llm", ""):
        def mk_pb(v=bad_pb):
            return lambda: check_record(base_finding(produced_by=v))
        results.append(expect_reject(f"F2 produced_by={bad_pb!r} 必须拒（E_ENUM）", mk_pb(), "E_ENUM"))

    # F3：12 组合穷举 —— 只认 E_WHITELIST 明确拒收，不许静默修正
    for pb, st, should_pass in EXHAUSTIVE_PB_ST:
        extra = ({"confirmed_by_rule_class": True}
                 if (pb, st) == ("semantic", "confirmed") else {})
        def mk(pb=pb, st=st, extra=extra):
            return lambda: check_record(base_finding(produced_by=pb, status=st, **extra))
        if should_pass:
            results.append(expect_ok(f"F3 `{pb}`×`{st}` 穷举应收", mk()))
        else:
            results.append(expect_reject(f"F3 `{pb}`×`{st}` 穷举必拒", mk(), "E_WHITELIST"))

    # F4：semantic 白名单独立期望逐格对拍 —— 生产 ALLOWED 必须等于判据原文的表
    # （17b 把 semantic 塞宽时这里红；写入死常量、直接对拍生产结构本身）
    def f4():
        problems = allowed_problems(ALLOWED)
        assert problems == [], "生产 ALLOWED 与判据原文的表不一致：%s" % problems
    results.append(expect_ok("F4 生产 ALLOWED ≡ 判据原文白名单（结构钉）", f4))

    # ═══════════ G. 行 23 补强：唯一判定表 15 链 + I4 ═══════════
    # ★ mutprobe 实测：链7 BLOCK 删除（23）/ 链14 待自决→PASS（23-c14）/
    #   I4 的 L0 检查关掉（23-i4）—— 本验证器当时 0 处提到 decision_table。
    #   独立期望表写在 EXPECTED_TABLE（手写链序），逐格对拍生产 decide。

    # G1：15 链逐格对拍（独立期望表 vs 生产 decide）
    def g1():
        problems = dt_expect_problems(decide)
        assert problems == [], "判定表与独立期望表不一致：%s" % problems
    results.append(expect_ok("G1 唯一判定表 15 链+I4 逐格对拍独立期望", g1))

    # G2：I4 反向对照 —— 没有那条 L0 检查的坏实现必须被对拍构件抓到。
    #     坏副本在验证器侧打桩（exec 生产源码的替换副本，不落盘、不动生产文件）。
    def g2():
        import base.decision_table as dtmod
        src = open(dtmod.__file__, encoding="utf-8").read()
        bad = src.replace(
            'if any(f.get("status") == "confirmed" and f.get("severity") == "L0" for f in findings):\n        return "I4"',
            'if False:\n        return "I4"')
        if bad == src:
            raise AssertionError("找不到 I4 判定原文（生产代码变了，对照过期）")
        ns = {"__name__": "dt_bad_i4_fs"}
        exec(compile(bad, "decision_table_bad_i4.py", "exec"), ns)
        problems = dt_expect_problems(ns["decide"])
        assert problems, "I4 关掉的坏副本必须被对拍构件抓到（否则构件恒绿）"
        assert any("I4" in p for p in problems), f"差异里应点到 I4：{problems}"
    results.append(expect_ok("G2 对拍构件必须抓到 I4 被关掉的坏副本", g2))

    # G3：链 7 反向对照 —— BLOCK 分支关掉后，对拍构件必须抓到。
    def g3():
        import base.decision_table as dtmod
        src = open(dtmod.__file__, encoding="utf-8").read()
        bad = src.replace(
            'elif max_sev in ("L4", "L5") and max_auth == "ok":\n'
            '        chain, state, layer = 7, "BLOCK", "DP2"',
            'elif max_sev in ("L4", "L5") and max_auth == "ok" and False:\n'
            '        chain, state, layer = 7, "BLOCK", "DP2"')
        if bad == src:
            raise AssertionError("找不到链 7 原文（生产代码变了，对照过期）")
        ns = {"__name__": "dt_bad_chain7_fs"}
        exec(compile(bad, "decision_table_bad_chain7.py", "exec"), ns)
        problems = dt_expect_problems(ns["decide"])
        assert problems, "链 7 关掉的坏副本必须被抓到"
        assert any("chain7" in p for p in problems), f"差异里应点到 chain7：{problems}"
    results.append(expect_ok("G3 对拍构件必须抓到链 7 被关掉的坏副本", g3))

    # ═══════════ 反向对照（四条必红）═══════════
    # R1：原地改 severity → 红。判据：新记录与旧记录的判断内容不一致时，
    #     说明有人试图「改历史」而不是「新建一条」。
    def r1():
        s = FindingStore()
        old = s.insert(base_finding())
        # 正确做法：新建一条（severity 属于判断内容，改它就等于换判断）
        new = s.transition(old["finding_id"], new_status="confirmed", severity="L5")
        # 旧条 severity 必须还是 L4；变了就是「原地改」
        assert s.get(old["finding_id"])["severity"] == "L4", \
            "旧条 severity 被原地改了 —— 这是改历史，不是 append-only"
        assert new["severity"] == "L5" and new["derived_from"] == old["finding_id"]
    results.append(expect_ok("R1 改 severity 必须走新条目（旧条不动）", r1))

    # R1b：反过来 —— 如果实现改成原地改，这条会红。构造「旧条被改」的坏样本并断言能识别。
    def r1b():
        s = FindingStore()
        old = s.insert(base_finding())
        before = dict(s.get(old["finding_id"]))
        s.transition(old["finding_id"], new_status="confirmed", severity="L5")
        after = s.get(old["finding_id"])
        changed = {k for k in before if before[k] != after.get(k)}
        assert changed == {"status"}, f"识别到越权改动：{changed}"
    results.append(expect_ok("R1b 可识别「旧条被改 severity」", r1b))

    # R2：同 id 两条 → 红（已在 C1，这里再验一次「拒收信息里带原因」）
    def r2():
        s = FindingStore()
        s.insert(base_finding(finding_id="x"))
        s.insert(base_finding(finding_id="x"))
    results.append(expect_reject("R2 同 id 两条（复验）", r2, "E_DUP_ID"))

    # R3：DraftFinding → 拒（已在 B3，这里验 store 的写入口也拒）
    def r3():
        s = FindingStore()
        r = base_finding()
        r.pop("authority_state")
        s.insert(r)
    results.append(expect_reject("R3 DraftFinding 进 store 必须拒", r3, "E_DRAFT"))

    # R4：旧条 produced_by 被改 → 红。
    #     构造：transition 时把 produced_by 也当判断内容改了，旧条必须保持原值。
    def r4():
        s = FindingStore()
        old = s.insert(base_finding(produced_by="rule"))
        s.transition(old["finding_id"], new_status="rejected", produced_by="human")
        assert s.get(old["finding_id"])["produced_by"] == "rule", \
            "旧条 produced_by 被改了 —— §3.3.4.1 要求保持原值"
    results.append(expect_ok("R4 旧条 produced_by 必须保持原值", r4))

    # ═══════════ 汇总 ═══════════
    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 68)
    print("finding_store 契约验收")
    print("=" * 68)
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name:<44} {detail}")
    print()
    if ok == total:
        print(f"✅ {ok}/{total} 项全过")
        return 0
    reds = [n for n, p, _ in results if not p]
    print(f"✗ {ok}/{total} 项通过；红项：{reds}")
    return 1


# ── --controls：E/F/G 新断言的反向对照 ────────────────────────────────
# 每条新断言都要指得出「喂什么必须红」；同时喂好样本证明它**不是恒红**
# （AGENTS §2.4.1：没红过的断言不算验证过它；§2.1.1：误报的检查器更糟）。
def run_controls() -> int:
    results = []

    def C(cond, name, detail=""):
        """登记一条对照结果：cond 为假即红（名字在前会恒真 —— 参数序吃过的亏）。"""
        results.append((name, bool(cond), detail))

    # ── E 段构件 ──
    for bad_fid in (123, None, "   ", ""):
        def mk_fid(v=bad_fid):
            return lambda: check_record(base_finding(finding_id=v))
        results.append(expect_reject(f"CE1 fid={bad_fid!r} 必须拒", mk_fid(), "E_ID"))

    for bad_df in (123, {}, ["f-0"], True):
        def mk_df(v=bad_df):
            return lambda: check_record(base_finding(derived_from=v))
        results.append(expect_reject(f"CE2 df={bad_df!r} 必须拒", mk_df(), "E_TYPE"))

    results.append(expect_ok(
        "CE3 好样本 fid='ok-1'/df=null 不许误报",
        lambda: check_record(base_finding(finding_id="ok-1", derived_from=None))))
    results.append(expect_ok(
        "CE4 好样本 df='ok-0'（串）不许误报",
        lambda: check_record(base_finding(finding_id="ok-1", derived_from="ok-0"))))

    good = base_finding(finding_id="g-1", derived_from=None)
    C(df_scan_problems([good]) == [],
      "CE5 好账本不许被指针扫描误报", str(df_scan_problems([good])))
    self_p = df_scan_problems([base_finding(finding_id="s-1", derived_from="s-1")])
    C(bool(self_p) and "自指" in self_p[0],
      "CE6 自指必须被报出", str(self_p))
    ghost_p = df_scan_problems([base_finding(finding_id="g-1", derived_from="ghost")])
    C(bool(ghost_p) and "悬空" in ghost_p[0],
      "CE7 悬空必须被报出", str(ghost_p))
    nonstr_p = df_scan_problems([base_finding(finding_id="n-1", derived_from=123)])
    C(bool(nonstr_p) and "非串非null" in nonstr_p[0],
      "CE8 非串指针必须被报出", str(nonstr_p))
    linked = base_finding(finding_id="g-1", derived_from=None)
    linked2 = base_finding(finding_id="g-2", derived_from="g-1")
    C(df_scan_problems([linked, linked2]) == [],
      "CE9 指向在册 id 的指针不许误报", str(df_scan_problems([linked, linked2])))

    # ── F 段构件 ──
    for bad_st in ("pending", "unknown", "model", "system"):
        def mk_st(v=bad_st):
            return lambda: check_record(base_finding(status=v))
        results.append(expect_reject(f"CF1 status={bad_st!r} 必须拒", mk_st(), "E_ENUM"))

    for bad_pb in ("model", "system", "llm", ""):
        def mk_pb(v=bad_pb):
            return lambda: check_record(base_finding(produced_by=v))
        results.append(expect_reject(f"CF2 produced_by={bad_pb!r} 必须拒", mk_pb(), "E_ENUM"))

    # F 段穷举构件：坏 EXPECTED 表必须被抓到、好表必须零红。
    C(exhaustive_whitelist_problems(check_record) == [],
      "CF3 真生产在 12 组合穷举下零红（不许恒红）",
      str(exhaustive_whitelist_problems(check_record)))
    bad_expected = tuple(
        (pb, st, (not okp) if (pb, st) == ("rule", "confirmed") else okp)
        for pb, st, okp in EXHAUSTIVE_PB_ST)

    def _exh_with(expected):
        saved = EXHAUSTIVE_PB_ST
        globals()["EXHAUSTIVE_PB_ST"] = expected
        try:
            return exhaustive_whitelist_problems(check_record)
        finally:
            globals()["EXHAUSTIVE_PB_ST"] = saved
    C(bool(_exh_with(bad_expected)), "CF4 期望表打坏后穷举构件必须报红",
      str(_exh_with(bad_expected)))
    C(allowed_problems(ALLOWED) == [],
      "CF5 好 ALLOWED 对拍零红（不许恒红）", str(allowed_problems(ALLOWED)))
    bad_allowed = dict(ALLOWED)
    bad_allowed["semantic"] = frozenset(set(ALLOWED["semantic"]) | {"pending"})
    C(bool(allowed_problems(bad_allowed)),
      "CF6 semantic 塞宽的坏表必须被对拍抓到", str(allowed_problems(bad_allowed)))

    # ── G 段构件 ──
    C(dt_expect_problems(decide) == [],
      "CG1 真生产判定表对拍零红（不许恒红）", str(dt_expect_problems(decide)))
    # 期望表打坏两处（链 7 / 链 14），构件两次都必须报出 —— 证明它真的在读。
    bad_t7 = tuple((c, ("REVIEW" if c == 7 else s), l, mk)
                   for c, s, l, mk in EXPECTED_TABLE)
    p7 = dt_expect_problems(decide, bad_t7)
    C(bool(p7) and any("chain7" in p for p in p7),
      "CG2 链7期望打坏后构件必须报出", str(p7))
    bad_t14 = tuple((c, ("PASS" if c == 14 else s), l, mk)
                    for c, s, l, mk in EXPECTED_TABLE)
    p14 = dt_expect_problems(decide, bad_t14)
    C(bool(p14) and any("chain14" in p for p in p14),
      "CG3 链14期望打坏后构件必须报出", str(p14))
    # 生产 decide 打坏（I4 关掉的坏副本）→ 构件必须报出 I4 行。
    try:
        src = open(os.path.join(ROOT, "base", "decision_table.py"),
                   encoding="utf-8").read()
        bad_i4 = src.replace(
            'if any(f.get("status") == "confirmed" and f.get("severity") == "L0" for f in findings):\n        return "I4"',
            'if False:\n        return "I4"')
        if bad_i4 == src:
            C(False, "CG4 找不到 I4 原文（生产代码变了，对照过期）", "")
        else:
            ns = {"__name__": "dt_bad_i4_ctrl"}
            exec(compile(bad_i4, "decision_table_badi4_ctrl.py", "exec"), ns)
            pi4 = dt_expect_problems(ns["decide"])
            C(bool(pi4) and any("I4" in p for p in pi4),
              "CG4 I4 关掉的坏副本必须被抓到", str(pi4))
    except Exception as e:  # noqa: BLE001
        C(False, "CG4 坏副本跑不起来", f"{type(e).__name__}: {e}")

    nok = sum(1 for _, p, _ in results if p)
    ntot = len(results)
    print("=" * 68)
    print("finding_store · --controls (E/F/G 反向对照)")
    print("=" * 68)
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name:<44} {detail}")
    print()
    if nok == ntot:
        print(f"✅ {nok}/{ntot} 项全过")
        return 0
    reds = [n for n, p, _ in results if not p]
    print(f"✗ {nok}/{ntot} 项通过；红项：{reds}")
    return 1


def _usage():
    print("用法：python3 tools/verify_finding_store.py [--controls]")


if __name__ == "__main__":
    if "--controls" in sys.argv:
        sys.exit(run_controls())
    if any(a.startswith("-") and a not in ("--controls", "-h", "--help")
           for a in sys.argv[1:]):
        _usage()
        sys.exit(2)
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
