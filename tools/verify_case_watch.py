#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_case_watch.py —— 转出后超时升级（C-51 / L3-2 / STOP-6）

七组断言，每组都有反向对照：

  1. 工作日历口径：空表必须报 weekends_only；构造假日历后跨假期多等一天
  2. 到期判定：未到期 / 恰好到期 / 已超期（三态分明）
  3. 判不了 = 未测：缺 due_at 且缺 transferred_at 不许落进 not_due
  4. 终态不升级：closed / 取消 / 已离开待放行
  5. 去重：同一案件同一 due_at 连续两次扫描只产生一条通知与一条台账
  6. 通知：走 NotificationOutbox 唯一出口；解析不出接收人 → 未测而不是静默
  7. 反向对照：删掉守卫必须红

退出码：0 全过 / 1 有红 / 2 未测（import 失败）
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import case_watch as W
    from base import notifications as N
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(2)

BJT = W.BJT


def ts(s):
    return W.parse_ts(s)


def case(cid="c-1", **kw):
    """一条「转出后还没回音」的案件。默认：周一 09:00 转出，阈值 2 个工作日。"""
    base = {
        "case_id": cid,
        "status": "in_progress",
        "release_status": "待放行",
        "transferred_at": "2026-10-19T09:00:00+08:00",   # 周一
    }
    base.update(kw)
    return base


def _first(result, key, field=None, default=None):
    """
    安全取扫描结果的**第一条** `result[key][0][field]`。取不到返回 default。

    ★ 为什么要这个 helper：验证器要能在**坏实现**下报红，而不是崩。
      坏实现很可能让 `untested_items` 是空的（比如守卫被删掉、判不了的东西
      落进了 not_due）—— 那时 `result[key][0]` 抛 IndexError，
      整个验证器退 2。退 2 是「未测」，看起来像「验证器自己有毛病」，
      而不是「这条断言没通过」。**一个把红报成未测的验证器，等于把事故藏起来。**
      （这与 `verify_shouheng_ops.py` 的 E1 从 traceback 改成「⚠ 未测」是同一个病，
       但方向相反：那里是外部读数取不到、该报未测；这里是断言该报红、不许崩。）
    """
    items = (result or {}).get(key)
    if not isinstance(items, list) or not items:
        return default
    item = items[0]
    if field is None:
        return item
    return (item or {}).get(field, default) if isinstance(item, dict) else default


def main() -> int:
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def rejected(name, fn, want_code=None):
        try:
            fn()
        except W.CaseWatchError as e:
            good = (want_code is None) or (e.code == want_code)
            results.append((name, good, f"拒收 {e.code}"))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"抛了别的：{type(e).__name__}: {e}"))
        else:
            results.append((name, False, "**没有拒收** —— 这条断言是假的"))

    # ══════════ 1. 工作日历口径 ══════════
    cal_empty = W.WorkCalendar()
    ok("1a ★ 空表 → coverage = weekends_only",
       cal_empty.coverage() == "weekends_only", cal_empty.coverage())
    ok("1b ★ 空表 → holidays_configured = False",
       cal_empty.holidays_configured is False, "")

    cal_hol = W.WorkCalendar(holidays=["2026-10-21"])   # 周三放假
    ok("1c 配了假日 → coverage = configured",
       cal_hol.coverage() == "configured", cal_hol.coverage())
    ok("1d ★ 配了假日 → holidays_configured = True",
       cal_hol.holidays_configured is True, "")

    # 周一 +2 工作日：空表 = 周三；周三放假 = 周四
    mon = ts("2026-10-19T09:00:00+08:00")
    ok("1e 周一 +2 工作日（只跳周末）= 周三",
       cal_empty.add_business_days(mon, 2).date().isoformat() == "2026-10-21",
       cal_empty.add_business_days(mon, 2).date().isoformat())
    ok("1f ★ 同一算例，周三放假 → 顺延到周四",
       cal_hol.add_business_days(mon, 2).date().isoformat() == "2026-10-22",
       cal_hol.add_business_days(mon, 2).date().isoformat())

    # 跨周末：周五 +1 = 下周一
    fri = ts("2026-10-23T09:00:00+08:00")
    ok("1g 周五 +1 工作日 = 下周一",
       cal_empty.add_business_days(fri, 1).date().isoformat() == "2026-10-26",
       cal_empty.add_business_days(fri, 1).date().isoformat())

    # 调休：周六上班
    cal_extra = W.WorkCalendar(extra_workdays=["2026-10-24"])   # 周六调休
    ok("1h ★ 周六标成调休 → 算工作日",
       cal_extra.is_workday(datetime(2026, 10, 24).date()) is True, "")
    ok("1i ★ 调休优先于「周末」判定（周五 +1 = 周六调休那天）",
       cal_extra.add_business_days(fri, 1).date().isoformat() == "2026-10-24",
       cal_extra.add_business_days(fri, 1).date().isoformat())

    # 1j：假日与调休同时标 → 调休优先（顺序写死，不靠「不会同时标」）
    cal_both = W.WorkCalendar(holidays=["2026-10-24"],
                              extra_workdays=["2026-10-24"])
    ok("1j ★ 同时标成假日与调休 → 按调休（上班）",
       cal_both.is_workday(datetime(2026, 10, 24).date()) is True, "")

    # ══════════ 2. 到期判定三态 ══════════
    # 周一 09:00 转出，+2 工作日 = 周三 09:00 到期
    c = case()
    r = W.scan([c], "2026-10-21T08:59:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("2a 到期前 1 分钟 → not_due 且不在 due 里",
       len(r["not_due"]) == 1 and not r["due"], f"{r['not_due']}")

    r = W.scan([c], "2026-10-21T09:00:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("2b ★ 恰好到期 → due（now >= due_at）",
       len(r["due"]) == 1 and not r["not_due"], f"{r['due']}")

    r = W.scan([c], "2026-10-23T09:00:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("2c 超期 → due 且 overdue_workdays 算得出来",
       len(r["due"]) == 1 and _first(r, "due", "overdue_workdays") == 2,
       str(_first(r, "due", "overdue_workdays")))

    # 2d：显式 due_at 优先于按阈值算
    r = W.scan([case(due_at="2026-11-01T09:00:00+08:00")],
               "2026-10-21T10:00:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("2d ★ 给了 due_at 就用它（不被阈值覆盖）",
       len(r["not_due"]) == 1 and _first(r, "not_due", "due_source") == "due_at",
       str(r["not_due"]))

    # 2e：阈值可配
    r = W.scan([c], "2026-10-21T09:00:00+08:00", outbox=None,
               threshold_days=3, ledger=W.EscalationLedger())
    ok("2e ★ 阈值改成 3 个工作日 → 周三不算到期",
       len(r["not_due"]) == 1 and not r["due"], f"{r['not_due']}")

    # 2f：duration 文本解析
    ok("2f 「2 个工作日」→ 2",
       W.threshold_days_from("2 个工作日") == 2, "")
    ok("2g 读不出 → 用默认值",
       W.threshold_days_from("尽快") == W.DEFAULT_THRESHOLD_DAYS, "")

    # ══════════ 3. 判不了 = 未测 ══════════
    r = W.scan([{"case_id": "c-blind", "status": "in_progress",
                 "release_status": "待放行"}],
               "2026-10-21T09:00:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("3a ★ 既无 due_at 又无 transferred_at → untested，不许落 not_due",
       len(r["untested_items"]) == 1 and not r["not_due"] and not r["due"],
       f"untested={len(r['untested_items'])} not_due={len(r['not_due'])}")
    ok("3b ★ 外层 untested 汇总标志为 True",
       r["untested"] is True, "")
    ok("3c 未测带得出原因",
       bool(_first(r, "untested_items", "reason")),
       str(_first(r, "untested_items", "reason"))[:40])

    # 3d：坏时间串也算未测，不许当 0
    r = W.scan([case(due_at="不是时间")], "2026-10-21T09:00:00+08:00",
               outbox=None, ledger=W.EscalationLedger())
    ok("3d ★ 时间读不出 → untested（不是「还没到期」）",
       r["untested"] is True and not r["not_due"], f"{r}")

    # 3e：一条坏数据不拖死整轮
    r = W.scan([{"case_id": "c-bad"}, case("c-good")],
               "2026-10-21T09:00:00+08:00", outbox=None,
               ledger=W.EscalationLedger())
    ok("3e ★ 一条判不了不拖死其余案件",
       len(r["due"]) == 1 and r["untested"] is True, f"{r}")

    # 3f：now 读不出 → 直接拒，不许默认成「今天」
    rejected("3f ★ now 读不出 → 拒（不默认当前时刻）",
             lambda: W.scan([c], "不是时间"), "E_NOW")

    # ══════════ 4. 终态不升级 ══════════
    for st in ("closed", "cancelled", "withdrawn"):
        r = W.scan([case(status=st)], "2026-12-31T09:00:00+08:00",
                   outbox=None, ledger=W.EscalationLedger())
        ok(f"4 终态 {st} → skipped（不升级）",
           len(r["skipped"]) == 1 and not r["due"], f"{r['skipped']}")

    r = W.scan([case(release_status="已放行")], "2026-12-31T09:00:00+08:00",
               outbox=None, ledger=W.EscalationLedger())
    ok("4d ★ 已离开「待放行」→ skipped",
       len(r["skipped"]) == 1 and not r["due"], str(r["skipped"]))

    # ══════════ 5. 去重（同一 due_at 只升级一次）══════════
    with tempfile.TemporaryDirectory() as d:
        led = W.EscalationLedger(Path(d) / "esc.json")
        dedup = N.DedupLedger(Path(d) / "dedup.json")
        box = N.NotificationOutbox(dedup=dedup)

        r1 = W.scan([c], "2026-10-21T09:00:00+08:00",
                    ledger=led, outbox=box, escalation_recipients=["u_coord"])
        ok("5a 首次扫描 → due 且产生 1 条通知",
           len(r1["due"]) == 1 and len(box.records) == 1,
           f"due={len(r1['due'])} ntf={len(box.records)}")

        r2 = W.scan([c], "2026-10-21T09:05:00+08:00",       # 5 分钟后再扫
                    ledger=led, outbox=box, escalation_recipients=["u_coord"])
        ok("5b ★ 同一 due_at 连续扫描 → 不再产生通知",
           len(box.records) == 1, f"ntf={len(box.records)}")
        ok("5c ★ 第二次落进 already_escalated（说出来，不假装没发生）",
           len(r2["already_escalated"]) == 1, f"{r2['already_escalated']}")

        r3 = W.scan([c], "2026-10-21T09:10:00+08:00",
                    ledger=led, outbox=box, escalation_recipients=["u_coord"])
        ok("5d ★ 第三次扫描同样不产生（不是只挡第一次）",
           len(box.records) == 1 and len(r3["already_escalated"]) == 1, "")

        ok("5e 台账里只有一条该案件的升级事件",
           len(led.by_case("c-1")) == 1, f"n={len(led.by_case('c-1'))}")

        # 5f ★ due_at 变了 → 是新事件，应该再通知一次
        c_late = case(due_at="2026-10-22T09:00:00+08:00")
        r4 = W.scan([c_late], "2026-10-22T10:00:00+08:00",
                    ledger=led, outbox=box, escalation_recipients=["u_coord"])
        ok("5f ★ due_at 变化 → 产生第二条通知（键里含到期时刻）",
           len(box.records) == 2 and len(r4["due"]) == 1, f"ntf={len(box.records)}")

        # 5g 台账持久化：重建对象读同一文件
        led2 = W.EscalationLedger(Path(d) / "esc.json")
        ok("5g ★ 台账落盘后读得回（重启不重升级）",
           len(led2.by_case("c-1")) == 2 and not led2.untested,
           f"n={len(led2.by_case('c-1'))}")

        # 5h 台账读不出 → 整轮未测、不升级
        bad = Path(d) / "bad.json"
        bad.write_text("{不是 json", encoding="utf-8")
        led_bad = W.EscalationLedger(bad)
        box2 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d2.json"))
        r5 = W.scan([c], "2026-10-21T09:00:00+08:00",
                    ledger=led_bad, outbox=box2, escalation_recipients=["u_coord"])
        ok("5h ★ 台账读不出 → 整轮未测，且一条通知都不发",
           r5["untested"] is True and len(box2.records) == 0, f"{r5['untested_reasons']}")

    # ══════════ 6. 通知：唯一出口 + 未测语义 ══════════
    ok("6a case_overdue 走 inbox（不进飞书群）",
       N.notification_for("case_overdue")["channel"] == "inbox", "")

    with tempfile.TemporaryDirectory() as d:
        led = W.EscalationLedger(Path(d) / "e.json")
        box = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d.json"))

        # 6b 解析不出接收人 → 未测，不发通知、不写台账
        r = W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led, outbox=box)
        ok("6b ★ 解析不出接收人 → untested 且零通知",
           r["untested"] is True and len(box.records) == 0,
           f"{r['untested_reasons']}")
        ok("6c ★ 解析不出接收人 → 台账里也不许记「已升级」",
           len(led.by_case("c-1")) == 0, f"n={len(led.by_case('c-1'))}")

        # 6d 通知 payload 里必须带日历口径
        box2 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d2.json"))
        led2 = W.EscalationLedger(Path(d) / "e2.json")
        r = W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led2, outbox=box2,
                   escalation_recipients=["u_coord"])
        payload = (box2.records[0].get("payload") if box2.records else {}) or {}
        ok("6d ★ 通知 payload 带 calendar_coverage = weekends_only",
           payload.get("calendar_coverage") == "weekends_only",
           str(payload.get("calendar_coverage")))
        ok("6e ★ 通知 payload 带 holidays_configured = False",
           payload.get("holidays_configured") is False, "")

        # 6f 配了假日历 → payload 跟着变
        box3 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d3.json"))
        led3 = W.EscalationLedger(Path(d) / "e3.json")
        W.scan([c], "2026-10-23T09:00:00+08:00", ledger=led3, outbox=box3,
               calendar=W.WorkCalendar(holidays=["2026-10-21"]),
               escalation_recipients=["u_coord"])
        ok("6f 配了假日历 → payload 里 coverage = configured",
           ((box3.records[0].get("payload") or {}).get("calendar_coverage")
            if box3.records else None) == "configured",
           str((box3.records[0].get("payload") or {}).get("calendar_coverage")
               if box3.records else None))

        # 6g 升级目标角色可配
        box4 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d4.json"))
        led4 = W.EscalationLedger(Path(d) / "e4.json")
        W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led4, outbox=box4,
               escalation_role="法务", escalation_recipients=["u_legal"])
        ok("6g ★ 升级角色可配（默认项目统筹）",
           (led4.by_case("c-1")[0].get("escalation_role")
            if led4.by_case("c-1") else None) == "法务", "")
        ok("6h 默认升级角色 = 项目统筹",
           W.DEFAULT_ESCALATION_ROLE == "项目统筹", "")

    # ══════════ 7. 反按对照（删守卫必须红）══════════
    with tempfile.TemporaryDirectory() as d:
        # R1 ★ 去重键换成扫描时刻 → 两次扫描产生两条通知
        from unittest import mock
        n_ctr = {"i": 0}

        def bad_key(case_id, due_at_iso):
            n_ctr["i"] += 1
            return "case:%s:scan:%d" % (case_id, n_ctr["i"])

        with mock.patch("base.case_watch._event_key", bad_key):
            led = W.EscalationLedger(Path(d) / "r1.json")
            box = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r1d.json"))
            W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led, outbox=box,
                   escalation_recipients=["u_coord"])
            W.scan([c], "2026-10-21T09:05:00+08:00", ledger=led, outbox=box,
                   escalation_recipients=["u_coord"])
            leaked = len(box.records)
        ok("R1 ★ 去重键用扫描时刻 → 同一次到期被通知两次（反向对照成立）",
           leaked == 2, f"ntf={leaked}")

        # R2 ★ 判不出的案件落进 not_due → 「永远不升级」被伪装成「还没到期」
        with mock.patch("base.case_watch._due_at", lambda *a, **k: (None, "none")):
            r = W.scan([case()], "2026-10-21T09:00:00+08:00", outbox=None,
                       ledger=W.EscalationLedger())
        ok("R2 ★ 时间解析恒失败 → untested 而非 not_due（反向对照：若落 not_due 则此断言红）",
           r["untested"] is True and len(r["not_due"]) == 0, f"{r}")

        # R3 ★ 空日历被冒充成 configured
        fake = W.WorkCalendar()
        fake.coverage = lambda: "configured"     # 冒充「已考虑法定假日」
        ok("R3 ★ 空表冒充 configured 会被 1a 抓出（此处直接验冒充值）",
           fake.coverage() == "configured" and W.WorkCalendar().coverage() == "weekends_only",
           "")

        # R4 ★ 收件人解析不出时照样记「已升级」→ 案件永久沉默
        with mock.patch("base.case_watch._resolve_recipients", lambda *a, **k: []):
            led = W.EscalationLedger(Path(d) / "r4.json")
            box = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r4d.json"))
            r = W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led, outbox=box)
        ok("R4 ★ 解析不出接收人时不写台账（案件不会被永久静音）",
           len(led.by_case("c-1")) == 0 and r["untested"] is True, "")

        # R5 ★ 通知发失败后不记台账（否则「发过」是假的）
        class BrokenBox:
            def emit(self, **kw):
                return {"untested": True, "reason": "假的发送失败"}
        led = W.EscalationLedger(Path(d) / "r5.json")
        W.scan([c], "2026-10-21T09:00:00+08:00", ledger=led, outbox=BrokenBox(),
               escalation_recipients=["u_coord"])
        ok("R5 ★ 通知未测 → 台账不记（«已升级» 不许先于 «已通知»）",
           len(led.by_case("c-1")) == 0, f"n={len(led.by_case('c-1'))}")

        # R6 ★ 终态判定被删 → 已关闭案件也被升级
        with mock.patch.object(W, "TERMINAL_STATUS", frozenset()):
            r = W.scan([case(status="closed")], "2026-12-31T09:00:00+08:00",
                       outbox=None, ledger=W.EscalationLedger())
        ok("R6 ★ 去掉终态守卫 → 已关闭案件被升级（反向对照成立）",
           len(r["due"]) == 1, f"{r}")

    # ══════════ 8. 静态断言：不自己定时 ══════════
    src = (ROOT / "base" / "case_watch.py").read_text(encoding="utf-8")
    import re as _re
    timers = _re.findall(r"\b(?:while\s+True|asyncio\.sleep|time\.sleep|"
                         r"threading\.Timer|sched\.scheduler|apscheduler)\b", src)
    ok("8a ★ case_watch 不自己定时（纯扫描器，调度交给集成方）",
       not timers, f"命中 {timers or '无'}")
    ok("8b ★ 不 import orchestrator（避免与 C-46 热点撞车）",
       "orchestrator" not in src, "")

    # ── 汇总 ──
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 78)
    print("case_watch 契约验收（C-51 / L3-2 / STOP-6）")
    print("=" * 78)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<52} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return 0
    print(f"✗ {passed}/{total} 项通过；红项：{[n for n, p, _ in results if not p]}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"UNTESTED: 验收器自身异常: {type(exc).__name__}: {exc}")
        sys.exit(2)
