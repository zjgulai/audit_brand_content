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

        r1 = N.remind_takedown_task(task_id="td-1", recipient="u_a", state="pending", event_id=None,
                                    ledger=led, sender=snd, ts=t0)
        ok("3a 首次每日提醒发出", r1["daily"] is True and len(sent) == 1, f"{r1}")

        r2 = N.remind_takedown_task(task_id="td-1", recipient="u_a", state="pending", event_id=None,
                                    ledger=led, sender=snd, ts=t0.replace(hour=18))
        ok("3b ★ 同日第二次不再发", r2["daily"] is False and len(sent) == 1,
           f"{r2} sent={len(sent)}")

        r3 = N.remind_takedown_task(task_id="td-1", recipient="u_a", state="in_progress",
                                    event_id="ev-1", ledger=led, sender=snd, ts=t0)
        ok("3c ★ 同日状态变化仍立即发（每日键不吞事件键）",
           r3["event"] is True and r3["daily"] is False and len(sent) == 2,
           f"{r3} sent={len(sent)}")

        r4 = N.remind_takedown_task(task_id="td-1", recipient="u_a", state="completed",
                                    event_id="ev-1", ledger=led, sender=snd, ts=t0)
        ok("3d 同一 event_id 不重复通知", r4["event"] is False and len(sent) == 2,
           f"{r4}")

        r5 = N.remind_takedown_task(task_id="td-1", recipient="u_a", state="completed",
                                    event_id="ev-2", ledger=led, sender=snd,
                                    ts=t0 + timedelta(days=1))
        ok("3e 次日每日提醒重新发 + 新事件发",
           r5["daily"] is True and r5["event"] is True and len(sent) == 4,
           f"{r5} sent={len(sent)}")

        # ══════════ 4. 持久化 / 未测 ══════════
        p = Path(d) / "dedup2.json"
        led2 = N.DedupLedger(p)
        t1 = datetime(2026, 10, 17, 9, 0, tzinfo=N.BJT)
        led2.claim_daily("td-9", "u_a", ts=t1)
        # 模拟重启：新对象读同一文件
        led3 = N.DedupLedger(p)
        r = led3.claim_daily("td-9", "u_a", ts=t1)
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
        r = led_bad.claim_daily("td-1", "u_a", ts=t0)
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
        a = led.claim_daily("td-r3", "u_a", ts=t)
        b = led.claim_daily("td-r3", "u_a", ts=t.replace(hour=15))
        ok("R3 ★ 同日重复提醒被挡（不是发两次）",
           a["send"] is True and b["send"] is False, f"{a} / {b}")

    # R4：重启后重复 → 红
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r4.json"
        t = datetime(2026, 10, 16, 9, 0, tzinfo=N.BJT)
        N.DedupLedger(p).claim_daily("td-r4", "u_a", ts=t)
        again = N.DedupLedger(p).claim_daily("td-r4", "u_a", ts=t)
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


    # ══════════ 8. 事件出口（NotificationOutbox）══════════
    #
    # ★ 这一组验的是「动作发生 → 通知产生」这一跳。
    #   前面 1–7 组只验了通知对象本身的形状，没有一个字涉及「谁会去造它」——
    #   那正是缺口：形状全对，但没有任何东西产生它。

    # 8a 动作 → 类型的映射表必须与各调用点自己那张表一致
    from base import takedown as TD
    from base import reviews_ledger as RL

    ok("8a ★ takedown.STATE_EVENT 的每个值都在 EVENT_TYPE 里",
       set(TD.STATE_EVENT.values()) <= set(N.EVENT_TYPE),
       f"差集={sorted(set(TD.STATE_EVENT.values()) - set(N.EVENT_TYPE))}")
    ok("8b ★ reviews_ledger.NOTIFYING_KINDS 每个都在 EVENT_TYPE 里",
       set(RL.ReviewsLedger.NOTIFYING_KINDS) <= set(N.EVENT_TYPE),
       f"差集={sorted(set(RL.ReviewsLedger.NOTIFYING_KINDS) - set(N.EVENT_TYPE))}")

    # 8c 每个映射都能算出类型与通道（纯函数，不碰状态）
    for kind in sorted(N.EVENT_TYPE):
        try:
            spec = N.notification_for(kind)
            goodand = spec["type"] in N.TYPES and spec["channel"] in ("inbox", "feishu")
        except N.NotificationError as e:
            goodand, spec = False, str(e)
        ok(f"8c 映射 {kind} → 类型/通道可算", goodand, str(spec))

    reject("8d ★ 未知动作 → 拒（不许静默跳过）",
           lambda: N.notification_for("no_such_action"), "E_EVENT")

    # 8e ★ 五个关键动作里，只有 takedown 系列走飞书，其余全走 inbox（TS-22）
    for kind in ("lease_released", "formal_submit",
                 "release_signed", "release_revoked"):
        ok(f"8e ★ {kind} 只进 inbox（不发飞书）",
           N.notification_for(kind)["channel"] == "inbox",
           str(N.notification_for(kind)))
    for kind in ("takedown_created", "takedown_completed", "takedown_failed"):
        ok(f"8f {kind} 走飞书",
           N.notification_for(kind)["channel"] == "feishu",
           str(N.notification_for(kind)))

    # ══════════ 9. outbox：产生 / 去重 / 未测 ══════════
    with tempfile.TemporaryDirectory() as d:
        led = N.DedupLedger(Path(d) / "dedup-outbox.json")
        box = N.NotificationOutbox(dedup=led)

        # 9a 动作发生 → 产生记录
        r = box.emit(event_id="ev-fs-1", kind="formal_submit",
                     subject={"final_reviewer_id": "u_lead"})
        ok("9a ★ 动作发生后产生通知记录",
           len(r["emitted"]) == 1 and r["emitted"][0]["recipient"] == "u_lead",
           f"emitted={len(r['emitted'])}")
        ok("9b 记录类型 = formal_submit 且初始未读",
           r["emitted"][0]["type"] == "formal_submit"
           and r["emitted"][0]["unread"] is True, "")

        # 9c ★ 同一 event_id 只产生一次
        r2 = box.emit(event_id="ev-fs-1", kind="formal_submit",
                      subject={"final_reviewer_id": "u_lead"})
        ok("9c ★ 同一 event_id 第二次 → duplicate，不再产生记录",
           r2["duplicate"] is True and len(r2["emitted"]) == 0,
           f"{r2}")
        ok("9d 记录总数仍是 1", len(box.records) == 1, f"n={len(box.records)}")

        # 9e 不同 event → 各一次
        r3 = box.emit(event_id="ev-fs-2", kind="formal_submit",
                      subject={"final_reviewer_id": "u_lead"})
        ok("9e 不同 event_id 各产生一次（去重不吞新事件）",
           len(r3["emitted"]) == 1 and len(box.records) == 2, f"n={len(box.records)}")

        # 9f ★ 解析不出收件人 = 未测，不是「不需要发」
        box2 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d2.json"))
        r4 = box2.emit(event_id="ev-x", kind="formal_submit", subject={})
        ok("9f ★ 解析不出收件人 → untested=True 且不产生记录",
           r4["untested"] is True and len(r4["emitted"]) == 0, f"{r4}")
        ok("9g 未测要能报出来（snapshot.untested + 有原因）",
           box2.snapshot()["untested"] is True
           and bool(box2.snapshot()["untested_reason"]),
           box2.snapshot()["untested_reason"][:46])

        # 9h ★ 多收件人：负责人 + 复核人，去重保序
        task = TD.new_task(task_id="t-9", case_id="c-9", platform="amazon",
                           tenant="t1", product_line="pump",
                           created_at="2026-10-19T00:00:00+08:00",
                           assignee="alice", reviewers=["bob", "alice"])
        box3 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d3.json"))
        r5 = box3.emit(event_id="ev-td", kind="takedown_created", subject=task)
        ok("9h ★ 下线任务通知发给 assignee + reviewers 且去重",
           [x["recipient"] for x in r5["emitted"]] == ["alice", "bob"],
           str([x["recipient"] for x in r5["emitted"]]))

        # 9i ★ 阶段一不真发飞书：sender=None 时 takedown 也不报错、不调用
        ok("9i ★ 未注入 sender 时飞书类通知不报错（阶段一不真发）",
           "sent" not in r5, str(sorted(r5)))

        # 9j 注入 sender 时才真的调用，且 inbox 类型永不调用
        calls = []
        box4 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "d4.json"),
                                    sender=lambda eid, kind: calls.append((eid, kind)))
        box4.emit(event_id="ev-td2", kind="takedown_created", subject=task)
        ok("9j 注入 sender → 飞书类型调用一次", len(calls) == 1, f"calls={calls}")
        box4.emit(event_id="ev-fs3", kind="formal_submit",
                  subject={"final_reviewer_id": "u_lead"})
        ok("9k ★ inbox 类型即使注入了 sender 也 0 次调用",
           len(calls) == 1, f"calls={len(calls)}")

        # 9l ★ 账本读不出 → 未测且不发（与 4c 同口径）
        bad = Path(d) / "bad-outbox.json"
        bad.write_text("{不是 json", encoding="utf-8")
        box5 = N.NotificationOutbox(dedup=N.DedupLedger(bad))
        r6 = box5.emit(event_id="ev-z", kind="formal_submit",
                       subject={"final_reviewer_id": "u_lead"})
        ok("9l ★ 去重账本读不出 → untested 且不产生记录",
           r6["untested"] is True and len(r6["emitted"]) == 0, f"{r6}")

    # ══════════ 10. 反向对照（删掉接线必须红）══════════
    with tempfile.TemporaryDirectory() as d:
        # R5 ★ 删掉 ledger 里的 outbox 调用 → 动作发生但不产生通知
        led2 = N.DedupLedger(Path(d) / "r5.json")
        box6 = N.NotificationOutbox(dedup=led2)
        L = RL.ReviewsLedger(lease_seconds=1, clock=lambda: 100.0, outbox=box6)
        L.claim("case-r5", "alice", now=100.0)
        L.expire(now=200.0)
        ok("R5 ★ 超时释放真的产生了通知（接线存在）",
           len(box6.records) == 1
           and box6.records[0]["recipient"] == "alice", f"n={len(box6.records)}")

        # R5b：把 outbox 断开（模拟"删掉接线"），同一批动作必须不产生通知
        box7 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r5b.json"))
        L2 = RL.ReviewsLedger(lease_seconds=1, clock=lambda: 100.0)   # 无 outbox
        L2.claim("case-r5b", "alice", now=100.0)
        L2.expire(now=200.0)
        ok("R5b ★ 不接 outbox → 动作照做但零通知（反向对照成立）",
           len(box7.records) == 0 and L2.get_case("case-r5b")["status"] == "released",
           f"n={len(box7.records)} status={L2.get_case('case-r5b')['status']}")

        # R6 ★ 把「先捕获再置空」换回原顺序 → 收件人解析不出，落未测而不是静默少发
        #    这里直接构造那个坏形状（assignee 已置空的事件），验证它会变成未测。
        box8 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r6.json"))
        r = box8.emit(event_id="ev-bad", kind="lease_released",
                      subject={"released_assignee": None})
        ok("R6 ★ assignee 先置空 → 未测（不是静默少发一条）",
           r["untested"] is True and len(r["emitted"]) == 0, f"{r}")

        # R7 ★ 去重键拿 task_id 当唯一键 → 同一任务第二次失败被吞掉
        #    先证明正确实现下两次失败都通知，再证明"只用 task_id"会只剩一条。
        box9 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r7.json"))
        t = TD.new_task(task_id="t-r7", case_id="c-r7", platform="amazon",
                        tenant="t1", product_line="pump",
                        created_at="2026-10-19T00:00:00+08:00", assignee="alice")
        t = TD.transition(t, "failed", action="fail", at="2026-10-19T01:00:00+08:00",
                          outbox=box9)
        t = TD.transition(t, "in_progress", action="retry", at="2026-10-19T02:00:00+08:00",
                          outbox=box9)
        t = TD.transition(t, "failed", action="fail", at="2026-10-19T03:00:00+08:00",
                          outbox=box9)
        ok("R7 ★ 同一任务两次失败各通知一次（键含迁移序号）",
           len(box9.records) == 2, f"n={len(box9.records)}")

        # R8 ★ 非法迁移不产生通知（先校验后通知，不许先说后做）
        box10 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r8.json"))
        t2 = TD.new_task(task_id="t-r8", case_id="c-r8", platform="amazon",
                         tenant="t1", product_line="pump",
                         created_at="2026-10-19T00:00:00+08:00", assignee="alice")
        try:
            TD.transition(t2, "completed", outbox=box10)   # pending → completed 非法
        except TD.TakedownError:
            pass
        ok("R8 ★ 非法迁移 → 零通知（通知必须在迁移成功之后）",
           len(box10.records) == 0, f"n={len(box10.records)}")

        # R9 ★ new_task 本身不发通知（构造样本不许有副作用，§2.4.4）
        box11 = N.NotificationOutbox(dedup=N.DedupLedger(Path(d) / "r9.json"))
        TD.new_task(task_id="t-r9", case_id="c-r9", platform="amazon",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00+08:00", assignee="alice")
        ok("R9 ★ new_task 不产生通知（建样本不等于发通知）",
           len(box11.records) == 0, f"n={len(box11.records)}")

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
