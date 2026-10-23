#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_lease_notifications.py —— 行 136 的通知半边：lease 释放只进工作台

## 行 136 原文那一句

> 断言原审核员与新领取人**只在工作台**收到通知（**飞书发送调用次数必须为 0**）。

**「调用次数 = 0」是可数的**，所以这半不是「无对象」—— 对象是
`base/notifications.py` 的 `NotificationOutbox(sender=…)` 与 `dispatch(ntype, feishu_sender=…)`：

* `channel_for("lease_released")` → `"inbox"`（`INBOX_ONLY`）；
* `dispatch()` 对 inbox 类型**根本不会调用** `feishu_sender`
  （`notifications.py:148-149` 原文：「根本不会被调用」，不是「调用了但忽略结果」）；
* `NotificationOutbox.emit()` 只在 `spec["channel"] == "feishu"` 且 sender 非空时才调用 sender。

## 断言

| 段 | 断言 |
|---|---|
| **N1** | 真实 `ReviewsLedger` 走「claim → 到期释放」，`lease_released` 通知落 `channel=inbox` |
| **N2** | **飞书 sender 的调用次数 = 0**（`calls == []`），且收件人是原领取人 |
| **N3** | 遍历全部 `INBOX_ONLY` 类型：即使传了 feishu sender，调用次数仍为 0 |
| **N4** | **反向对照**：`dispatch("takedown", feishu_sender=counter)` 必须让计数 +1 —— 证明计数器不是恒 0、sender 是真被调用的 |
| **N5** | 记录「从未调用」与「调用了但被桩住」的区别：N2 断言 sender 从未被调用，N4 证明同一个 sender 在 feishu 类型上会真的被调用 |

## 明写的局限

* **新领取人没有通知对象**：`NOTIFYING_KINDS = {lease_released, formal_submit}`（`reviews_ledger.py:118`），
  `claim` 不发通知。所以「新领取人收到通知」这半在今天**没有生产者** —— 不是「只在工作台收到」，
  是**什么都没收到**。本脚本只断言「没有飞到飞书」，不把「没发」写成「发对了」。
* **生产装配没有 outbox**：`api/` 下 `outbox` 0 命中，生产链一条通知都不产生。
  所以本脚本验的是 **ledger 这条路径**，不是生产运行时。

退出码：0 / 1 / 2（导入失败）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEASE = 1800
T0 = 1000.0


class Untested(Exception):
    pass


def _mods():
    try:
        from base import notifications as N  # noqa: PLC0415
        from base.reviews_ledger import ReviewsLedger  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入通知/台账失败：{type(e).__name__}: {e}")
    return N, ReviewsLedger


def run_release(N, ReviewsLedger):
    """claim → 到期释放；返回 (outbox, feishu_calls)。"""
    calls: list[tuple] = []

    def feishu_sender(event_id, kind):
        calls.append((event_id, kind))
        return {"ok": True}

    outbox = N.NotificationOutbox(sender=feishu_sender)
    ledger = ReviewsLedger(lease_seconds=LEASE, outbox=outbox)
    ledger.claim("case-notify", "alice", now=T0)
    released = ledger.expire(now=T0 + LEASE + 1)
    return outbox, calls, released


def check_release(outbox, calls, released) -> list[str]:
    problems = []
    recs = getattr(outbox, "records", []) or []
    inbox = [r for r in recs if r.get("type") == "lease_released"]
    if not inbox:
        problems.append(f"N1 lease_released 没有落 inbox（records={recs}）")
    if calls:
        problems.append(f"N2 飞书 sender 被调用了 {len(calls)} 次：{calls[:3]} —— 预期 0")
    if not released:
        problems.append("N1 到期没有释放任何案件 —— 这条通知路径没走到")
    if inbox:
        recipients = {r.get("recipient") for r in inbox}
        if "alice" not in recipients:
            problems.append(f"N2 收件人里没有原领取人 alice：{recipients}")
    return problems


def check_all_inbox_only(N) -> list[str]:
    """N3：每个 INBOX_ONLY 类型都不许碰 feishu sender。"""
    problems = []
    for ntype in sorted(N.INBOX_ONLY):
        calls = []

        def sender(*_a, _c=calls, **_k):
            _c.append("inbox-sender-called")
            return {"ok": True}

        try:
            out = N.dispatch(ntype, feishu_sender=sender)
        except Exception as e:  # noqa: BLE001
            problems.append(f"N3 dispatch({ntype!r}) 抛异常：{type(e).__name__}: {e}")
            continue
        if out.get("channel") != "inbox":
            problems.append(f"N3 {ntype} 的通道是 {out.get('channel')!r}，预期 inbox")
        if calls:
            problems.append(f"N3 {ntype} 调用了飞书 sender {len(calls)} 次 —— 预期 0")
    return problems


def check_counter_live(N) -> list[str]:
    """N4：反向对照 —— 飞书类型必须让计数器动。"""
    calls = []

    def sender(*_a, **_k):
        calls.append("takedown")
        return {"ok": True}

    out = N.dispatch("takedown", feishu_sender=sender)
    problems = []
    if out.get("channel") != "feishu":
        problems.append(f"N4 takedown 的通道是 {out.get('channel')!r}，预期 feishu")
    if len(calls) != 1:
        problems.append(f"N4 飞书 sender 调用次数 = {len(calls)}，预期 1 —— 计数器若恒 0，N2 就是假的")
    return problems


def assess(N, ReviewsLedger) -> list[str]:
    outbox, calls, released = run_release(N, ReviewsLedger)
    return (check_release(outbox, calls, released)
            + check_all_inbox_only(N) + check_counter_live(N))


def controls() -> int:
    N, ReviewsLedger = _mods()
    def _no_recipients_red():
        """N1 坏样本：解析不出收件人 → 没有 inbox 记录 → N1 必须红。"""
        calls = []
        ob = N.NotificationOutbox(sender=lambda *a, **k: calls.append(1),
                                  resolve_recipients=lambda kind, subject: [])
        led = ReviewsLedger(lease_seconds=LEASE, outbox=ob)
        led.claim("case-x", "alice", now=T0)
        released = led.expire(now=T0 + LEASE + 1)
        return bool(check_release(ob, calls, released))

    def _inbox_moved_red():
        """N3 坏样本：让 channel_for 把一个 inbox 类型判成 feishu → 必须红。"""
        orig = N.channel_for
        try:
            N.channel_for = lambda t: "feishu" if t == "invalidation" else orig(t)
            return bool(check_all_inbox_only(N))
        finally:
            N.channel_for = orig

    cases = [
        ("正样本：真实链路全绿", lambda: not assess(N, ReviewsLedger)),
        ("★ N1 坏样本：收件人解析为空 → 没有 inbox 记录 → 必须红", _no_recipients_red),
        ("★ N2 坏样本：把 lease_released 放进 FEISHU_TYPES → 必须红（用副本，不改模块）",
         lambda: _shifted(N, ReviewsLedger)),
        ("★ N3 坏样本：把一个 inbox 类型挪进 FEISHU_TYPES → 必须红", _inbox_moved_red),
        ("N4 反向对照：takedown 必须让飞书计数 +1（不是恒 0）",
         lambda: not check_counter_live(N)),
    ]
    bad = 0
    print("=" * 78)
    print("行 136 通知半边 · 工作台 vs 飞书（内存，不写盘）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过（含「该红」与「计数器不是恒 0」两侧）")
    return 0


def _shifted(N, ReviewsLedger) -> bool:
    """把 lease_released 临时挪进 FEISHU_TYPES（内存改，finally 复原），断言 N2 会红。"""
    orig_feishu = N.FEISHU_TYPES
    orig_inbox = N.INBOX_ONLY
    try:
        N.FEISHU_TYPES = frozenset(set(orig_feishu) | {"lease_released"})
        N.INBOX_ONLY = frozenset(set(orig_inbox) - {"lease_released"})
        outbox, calls, released = run_release(N, ReviewsLedger)
        return bool(check_release(outbox, calls, released))
    finally:
        N.FEISHU_TYPES = orig_feishu
        N.INBOX_ONLY = orig_inbox


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        try:
            return controls()
        except Untested as e:
            print(f"⚠️ 未测：{e}")
            return 2
    try:
        N, ReviewsLedger = _mods()
        problems = assess(N, ReviewsLedger)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 136 通知半边 · lease 释放只进工作台")
    print("=" * 78)
    print(f"  INBOX_ONLY（{len(N.INBOX_ONLY)}）：{sorted(N.INBOX_ONLY)}")
    print(f"  FEISHU_TYPES：{sorted(N.FEISHU_TYPES)}")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：lease 释放的通知落 inbox；飞书 sender 调用次数 = 0；")
    print("   takedown 反向对照让计数 +1（证明计数器不是恒 0）。")
    print("   ⚠️ 只覆盖 ledger 路径：生产装配没有 outbox（api/ 0 命中），")
    print("      新领取人也没有通知对象（claim 不在 NOTIFYING_KINDS）。")
    print("      所以「没发」不等于「发对了」—— #136 仍不映射。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
