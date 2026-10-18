#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_finding_store.py —— finding_store 的契约验收（L2-5 / §3.3.4.1 / §3.3.4.2）

四条必须同时成立：
  A. append-only —— 实质变化新建一条、旧条只标 superseded、其余字段不动、produced_by 保持
  B. 三要素合取 —— control_code / authority_ref / location 缺一拒收
  C. finding_id 全局唯一 —— 重放账本也不许碰撞
  D. produced_by × status 白名单 —— 表外组合拒收

**每一条都要能在反向对照里变红。** 没红过的断言不算验证过它（AGENTS §2.4.1）。

退出码：0 全绿 / 1 有红 / 2 未测（模块 import 不到）
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.finding_store import (  # noqa: E402
        FindingStore, FindingRejected, ALLOWED, check_record,
    )
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import finding_store 失败（{type(e).__name__}: {e}）—— 未测不是通过",
          file=sys.stderr)
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


if __name__ == "__main__":
    sys.exit(main())
