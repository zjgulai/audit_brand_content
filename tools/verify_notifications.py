#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_notifications.py —— 通知服务契约验收（TS-22 / RL-13）

五组断言，每组正反成对：
  1. 通知对象与通道：失效/重审只进 inbox、下线任务走飞书
  2. 文案约束：只许「已投递/已读」，不许「已通知到人」
  3. 下线提醒：每日一次 + 状态变化即时，两种键独立
  4. 去重持久化：重启不重复；读不出 → 未测且不发
  5. 反向对照（四条必红）：重审发飞书 / 文案越界 / 同日重复 / 重启重复

退出码：0 全绿 / 1 有红 / 2 未测（import 不到）
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import notifications as N
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import notifications 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def reject(name, fn, want_code=None):
        try:
            fn()
        except N.NotificationError as e:
            good = (want_code is None) or (e.code == want_code)
            results.append((name, good,
                            f"拒收 {e.code}" + ("" if good else f"（期望 {want_code}）")))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"抛了非 NotificationError：{type(e).__name__}: {e}"))
        else:
            results.append((name, False, "**没有拒收** —— 这条断言是假的"))

    # ══════════ 1. 通知对象与通道 ══════════
    n = N.new_notification(notification_id="n-1", recipient="alice",
                           ntype="invalidation", payload={"case_id": "c-1"})
    ok("1a 通知六字段齐全",
       all(k in n for k in ("recipient", "type", "unread", "read_at",
                            "acked_at", "payload")),
       f"keys={sorted(n)}")
    ok("1b read_at / acked_at 初始为 None 但键存在",
       n["read_at"] is None and n["acked_at"] is None
       and "read_at" in n and "acked_at" in n, "")
    ok("1c unread 初始 True", n["unread"] is True, "")

    ok("1d invalidation → inbox", N.channel_for("invalidation") == "inbox", "")
    ok("1e auto_rereview → inbox", N.channel_for("auto_rereview") == "inbox", "")
    ok("1f takedown → feishu", N.channel_for("takedown") == "feishu", "")
    reject("1g 未知类型 → 拒", lambda: N.channel_for("reminder"), "E_TYPE")
    reject("1h 建通知时未知类型 → 拒",
           lambda: N.new_notification(notification_id="x", recipient="a", ntype="bogus"),
           "E_TYPE")
    reject("1i recipient 为空 → 拒",
           lambda: N.new_notification(notification_id="x", recipient="  ", ntype="takedown"),
           "E_RECIPIENT")

    # ★ 1j/1k：inbox 类型**根本不调用** feishu_sender（不是调了忽略）
    calls = []

    def sender():
        calls.append(1)
        return {"ok": True}

    out = N.dispatch("auto_rereview", feishu_sender=sender)
    ok("1j ★ 重审通知派发后 feishu_sender 调用次数 == 0",
       out["channel"] == "inbox" and len(calls) == 0, f"calls={len(calls)}")

    out = N.dispatch("invalidation", feishu_sender=sender)
    ok("1k ★ 失效通知同理，飞书调用 0 次",
       out["channel"] == "inbox" and len(calls) == 0, f"calls={len(calls)}")

    out = N.dispatch("takedown", feishu_sender=sender)
    ok("1l takedown 派发走飞书且真的调用了一次",
       out["channel"] == "feishu" and len(calls) == 1, f"calls={len(calls)}")

    reject("1m takedown 但没传 sender → 拒（不许静默丢弃）",
           lambda: N.dispatch("takedown"), "E_NO_SENDER")

    # ══════════ 2. 文案约束 ══════════
    reject("2a ★ 文案含「已通知到人」→ 拒",
           lambda: N.check_wording("已通知到人，等待处理"), "E_WORDING")
    reject("2b ★ 文案含「已告知本人」→ 拒",
           lambda: N.check_wording("已告知本人"), "E_WORDING")
    reject("2c 文案含「已确认收到」→ 拒",
           lambda: N.check_wording("对方已确认收到"), "E_WORDING")

    for good in ("已投递 3 条，未读 2 条，已读 1 条",
                 "已投递 5 条，未读 5 条", "已读 2 条，已确认 1 条"):
        try:
            N.check_wording(good)
            ok(f"2d 合规文案放行：{good[:14]}…", True, "")
        except N.NotificationError as e:
            ok(f"2d 合规文案放行：{good[:14]}…", False, str(e))

    # 2e：生成器自己的输出也要过闸
    try:
        w = N.safe_wording(delivered=3, unread=2, read=1)
        ok("2e safe_wording 生成合规文案", "已投递" in w and "已读" in w, w)
    except N.NotificationError as e:
        ok("2e safe_wording 生成合规文案", False, str(e))

    # ══════════ 3. 下线提醒：两种键独立 ══════════
    with tempfile.TemporaryDirectory() as d:
        led = N.DedupLedger(Path(d) / "dedup.json")
        t0 = datetime(2026, 10, 16, 9, 0, tzinfo=N.BJT)
        sent = []
        snd = lambda tid, kind: sent.append((tid, kind))

        r1 = N.remind_takedown_task(task_id="td-1", state="pending", event_id=None,
                                    ledger=led, sender=snd, ts=t0)
        ok("3a 首次每日提醒发出", r1["daily"] is True and len(sent) == 1, f"{r1}")

        r2 = N.remind_takedown_task(task_id="td-1", state="pending", event_id=None,
                                    ledger=led, sender=snd, ts=t0.replace(hour=18))
        ok("3b ★ 同日第二次不再发", r2["daily"] is False and len(sent) == 1,
           f"{r2} sent={len(sent)}")

        r3 = N.remind_takedown_task(task_id="td-1", state="in_progress",
                                    event_id="ev-1", ledger=led, sender=snd, ts=t0)
        ok("3c ★ 同日状态变化仍立即发（每日键不吞事件键）",
           r3["event"] is True and r3["daily"] is False and len(sent) == 2,
           f"{r3} sent={len(sent)}")

        r4 = N.remind_takedown_task(task_id="td-1", state="completed",
                                    event_id="ev-1", ledger=led, sender=snd, ts=t0)
        ok("3d 同一 event_id 不重复通知", r4["event"] is False and len(sent) == 2,
           f"{r4}")

        r5 = N.remind_takedown_task(task_id="td-1", state="completed",
                                    event_id="ev-2", ledger=led, sender=snd,
                                    ts=t0 + timedelta(days=1))
        ok("3e 次日每日提醒重新发 + 新事件发",
           r5["daily"] is True and r5["event"] is True and len(sent) == 4,
           f"{r5} sent={len(sent)}")

        # ══════════ 4. 持久化 / 未测 ══════════
        p = Path(d) / "dedup2.json"
        led2 = N.DedupLedger(p)
        t1 = datetime(2026, 10, 17, 9, 0, tzinfo=N.BJT)
        led2.claim_daily("td-9", ts=t1)
        # 模拟重启：新对象读同一文件
        led3 = N.DedupLedger(p)
        r = led3.claim_daily("td-9", ts=t1)
        ok("4a ★ 重启后同日不重复（持久化生效）",
           r["send"] is False and r["untested"] is False, f"{r}")

        # 北京日期口径
        utc_late = datetime(2026, 10, 16, 23, 30, tzinfo=timezone.utc)
        ok("4b 去重键用北京日期（UTC 23:30 → 北京次日）",
           N.bj_date(utc_late) == "2026-10-17", N.bj_date(utc_late))

        # 4c：读不出 → 未测且不发
        bad = Path(d) / "corrupt.json"
        bad.write_text("{不是 json", encoding="utf-8")
        led_bad = N.DedupLedger(bad)
        r = led_bad.claim_daily("td-1", ts=t0)
        ok("4c ★ 账本读不出 → untested 且 send=False（不发）",
           r["untested"] is True and r["send"] is False, f"{r}")
        r = led_bad.claim_event("ev-x")
        ok("4d 未测时事件通道同样不发", r["untested"] is True and r["send"] is False, f"{r}")

        # 4e：未测状态要能报出来，不能静默
        ok("4e untested 带原因（不是空）",
           bool(led_bad.untested_reason), led_bad.untested_reason[:40])

    # ══════════ 5. 反向对照（四条必红）══════════
    # R1：重审通知触发飞书发送 → 红
    def r1():
        hit = []
        N.dispatch("auto_rereview", feishu_sender=lambda: hit.append(1))
        assert not hit, f"重审通知竟然调用了飞书 {len(hit)} 次"
    try:
        r1(); ok("R1 ★ 重审通知不触发飞书（反向对照成立）", True, "")
    except AssertionError as e:
        ok("R1 ★ 重审通知不触发飞书（反向对照成立）", False, str(e))

    # R2：文案含禁用词 → 红
    reject("R2 ★ 文案越界 → 红", lambda: N.check_wording("已通知到人"), "E_WORDING")

    # R3：同日重复提醒 → 红
    with tempfile.TemporaryDirectory() as d:
        led = N.DedupLedger(Path(d) / "r3.json")
        t = datetime(2026, 10, 16, 9, 0, tzinfo=N.BJT)
        a = led.claim_daily("td-r3", ts=t)
        b = led.claim_daily("td-r3", ts=t.replace(hour=15))
        ok("R3 ★ 同日重复提醒被挡（不是发两次）",
           a["send"] is True and b["send"] is False, f"{a} / {b}")

    # R4：重启后重复 → 红
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r4.json"
        t = datetime(2026, 10, 16, 9, 0, tzinfo=N.BJT)
        N.DedupLedger(p).claim_daily("td-r4", ts=t)
        again = N.DedupLedger(p).claim_daily("td-r4", ts=t)
        ok("R4 ★ 重启后同日不重复发", again["send"] is False, f"{again}")

    # ══════════ 6. inbox 视图 ══════════
    ns = [N.new_notification(notification_id=f"n-{i}", recipient="alice",
                             ntype="invalidation") for i in range(3)]
    ns.append(N.new_notification(notification_id="n-x", recipient="bob", ntype="takedown"))
    v = N.inbox_view(ns, recipient="alice")
    ok("6a inbox 只数自己的", v["total"] == 3 and v["unread"] == 3, f"{v}")

    r = N.mark_read(ns[0], "2026-10-16T09:00:00+08:00")
    ok("6b mark_read 后 unread=False 且 read_at 有值",
       r["unread"] is False and r["read_at"] is not None, "")
    ok("6c mark_read 不动 acked_at（未 ack 与已 ack 是两件事）",
       r["acked_at"] is None, "")

    reject("6d 未读就 ack → 拒",
           lambda: N.mark_acked(ns[0], "2026-10-16T10:00:00+08:00"),
           "E_ACK_WITHOUT_READ")

    a = N.mark_acked(r, "2026-10-16T10:00:00+08:00")
    ok("6e 先读后 ack 成功", a["acked_at"] is not None, "")

    # ══════════ 7. 静态断言：本文件不 import 飞书发送模块 ══════════
    src = (ROOT / "base" / "notifications.py").read_text(encoding="utf-8")
    bad_imports = re.findall(
        r"^\s*(?:from|import)\s+.*(?:feishu|lark_write|send_gateway)", src, re.M)
    ok("7a ★ notifications.py 不 import 任何飞书发送模块",
       not bad_imports, f"命中 {bad_imports or '无'}")

    # ── 汇总 ──
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 74)
    print("notifications 契约验收（TS-22 / RL-13）")
    print("=" * 74)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<48} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return 0
    print(f"✗ {passed}/{total} 项通过；红项：{[n for n, p, _ in results if not p]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
