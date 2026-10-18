#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_takedown.py —— 下线任务契约验收（RL-7 / RL-8 / RL-9 / RL-13）

六组断言，每组都有反向对照（坏样本必须红、好样本必须绿）：
  1. 状态机：合法迁移过、非法迁移拒、失败态三处置
  2. 创建条件：已发布才建、未发布 not_applicable
  3. 回填证据：三必填 + 三选一 + 截图三项硬条件
  4. waive：双人 / 都要 scope / 执行人不可自批 / 原签发人不得唯一 / reason+evidence
  5. 提醒去重：每日键=task_id+北京日期、事件键=event_id、**两种键不许混**
  6. 无硬时限：结构里没有 deadline，指标里没有「正常/未超时」

退出码：0 全绿 / 1 有红 / 2 未测
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import takedown as TD
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import takedown 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    results = []

    def ok(name, cond, detail):
        results.append((name, bool(cond), detail))

    def reject(name, fn, want_code=None):
        try:
            fn()
        except TD.TakedownError as e:
            good = (want_code is None) or (e.code == want_code)
            results.append((name, good,
                            f"拒收 {e.code}" + ("" if good else f"（期望 {want_code}）")))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"抛了非 TakedownError：{type(e).__name__}: {e}"))
        else:
            results.append((name, False, "**没有拒收** —— 这条断言是假的"))

    task = TD.new_task(
        task_id="td-1", case_id="case-1", platform="tiktok",
        tenant="momcozy", product_line="breast-pump",
        created_at="2026-10-15T00:00:00+08:00", assignee="alice",
        reviewers=["bob"])

    # ═════════ 1. 状态机 ═════════
    t = TD.transition(task, "in_progress", at="2026-10-15T10:00:00+08:00")
    ok("1a pending → in_progress 合法", t["state"] == "in_progress", t["state"])

    t2 = TD.transition(t, "completed", at="2026-10-15T12:00:00+08:00")
    ok("1b in_progress → completed 合法", t2["state"] == "completed", t2["state"])
    ok("1c 迁移留痕（history 长度递增）", len(t2["history"]) == 2, f"history={len(t2['history'])}")

    reject("1d completed 是终态，不许再迁", lambda: TD.transition(t2, "in_progress"),
           "E_TRANSITION")
    reject("1e pending → completed 跳步拒", lambda: TD.transition(task, "completed"),
           "E_TRANSITION")
    reject("1f 未知状态拒", lambda: TD.transition(task, "archived"), "E_STATE")

    tf = TD.transition(task, "failed", at="2026-10-15T11:00:00+08:00")
    ok("1g pending → failed 合法", tf["state"] == "failed", tf["state"])

    for act in ("retry", "reassign", "waive"):
        try:
            TD.check_transition("failed", "in_progress", action=act)
            ok(f"1h failed + {act} 合法", True, "通过")
        except TD.TakedownError as e:
            ok(f"1h failed + {act} 合法", False, str(e))

    reject("1i failed + 未知处置拒",
           lambda: TD.check_transition("failed", "in_progress", action="ignore"), "E_ACTION")

    # ═════════ 2. 创建条件 ═════════
    ok("2a revoke + 已发布 → 建任务",
       TD.should_create_task(trigger="revoke", published=True)["create"] is True, "")
    ok("2b invalidated + 已发布 → 建任务",
       TD.should_create_task(trigger="invalidated", published=True)["create"] is True, "")
    r = TD.should_create_task(trigger="revoke", published=False)
    ok("2c ★ 未发布 → 不建任务且 reason=not_applicable",
       r["create"] is False and r["reason"] == "not_applicable", f"{r}")
    reject("2d 未知 trigger 拒",
           lambda: TD.should_create_task(trigger="expired", published=True), "E_TRIGGER")

    # ═════════ 3. 回填证据 ═════════
    good_ev = {"platform": "tiktok", "executed_by": "alice",
               "executed_at": "2026-10-16T09:00:00+08:00", "receipt_id": "R-123"}
    try:
        TD.check_evidence(good_ev)
        ok("3a 完整证据通过", True, "通过")
    except TD.TakedownError as e:
        ok("3a 完整证据通过", False, str(e))

    for k in ("platform", "executed_by", "executed_at"):
        ev = dict(good_ev)
        ev.pop(k)
        reject(f"3b 缺必填 {k}", (lambda ev=ev: TD.check_evidence(ev)), "E_EVIDENCE")

    reject("3c ★ 三样取证都没有 → 无证据不得 complete",
           lambda: TD.check_evidence({"platform": "x", "executed_by": "a",
                                      "executed_at": "2026-10-16T09:00:00+08:00"}),
           "E_EVIDENCE")

    try:
        TD.check_evidence({"platform": "x", "executed_by": "a",
                           "executed_at": "2026-10-16T09:00:00+08:00",
                           "result_url": "https://tiktok.com/@x/video/1"})
        ok("3d 仅 result_url 也通过", True, "通过")
    except TD.TakedownError as e:
        ok("3d 仅 result_url 也通过", False, str(e))

    shot_ok = {"platform": "x", "executed_by": "a",
               "executed_at": "2026-10-16T09:00:00+08:00",
               "screenshot": {"path": "/tmp/shots/1.png", "sha256": "abc123",
                              "never_tracked": True}}
    try:
        TD.check_evidence(shot_ok, repo_root=str(ROOT))
        ok("3e 截图替代通过（仓外 + sha256 + never_tracked）", True, "通过")
    except TD.TakedownError as e:
        ok("3e 截图替代通过（仓外 + sha256 + never_tracked）", False, str(e))

    reject("3f ★ 截图在仓库内 → 拒",
           lambda: TD.check_evidence({**shot_ok, "screenshot": {
               **shot_ok["screenshot"], "path": str(ROOT / "shots/1.png")}},
               repo_root=str(ROOT)), "E_SCREENSHOT")
    reject("3g 截图无 sha256 → 拒",
           lambda: TD.check_evidence({**shot_ok, "screenshot": {
               "path": "/tmp/x.png", "never_tracked": True}}), "E_SCREENSHOT")
    reject("3h 截图未标 never_tracked → 拒",
           lambda: TD.check_evidence({**shot_ok, "screenshot": {
               "path": "/tmp/x.png", "sha256": "abc"}}), "E_SCREENSHOT")

    reject("3i ★ complete() 无证据直接拒（不是先完成后校验）",
           lambda: TD.complete(task, {}), "E_EVIDENCE")
    try:
        done = TD.complete(t, good_ev, at="2026-10-16T09:00:00+08:00")
        ok("3j complete() 带合法证据成功且落 evidence",
           done["state"] == "completed" and done["evidence"]["receipt_id"] == "R-123", "")
    except TD.TakedownError as e:
        ok("3j complete() 带合法证据成功且落 evidence", False, str(e))

    # ═════════ 4. waive ═════════
    A = {"actor": "carol", "scopes": ["takedown.waive"], "scope_match": True}
    B = {"actor": "dave", "scopes": ["takedown.waive"], "scope_match": True}

    def waive(approvers, executor="alice", signer="carol", reason="内容已过期",
              evidence=["截图1"]):
        return TD.check_waive(approvers=approvers, executor=executor,
                              original_signer=signer, reason=reason, evidence=evidence)

    try:
        waive([A, B])
        ok("4a 双人 + 都有 scope + 执行人不参与 → 通过", True, "通过")
    except TD.TakedownError as e:
        ok("4a 双人 + 都有 scope + 执行人不参与 → 通过", False, str(e))

    reject("4b ★ 只有一个审批人 → 拒", lambda: waive([A]), "E_WAIVE_APPROVERS")
    reject("4c ★ 执行人自批 → 拒",
           lambda: waive([{"actor": "alice", "scopes": ["takedown.waive"]}, B]),
           "E_SELF_APPROVE")
    reject("4d 两人是同一人 → 拒",
           lambda: waive([A, {"actor": "carol", "scopes": ["takedown.waive"]}]),
           "E_WAIVE_ACTOR")
    reject("4e 审批人缺 takedown.waive 权限 → 拒",
           lambda: waive([{"actor": "carol", "scopes": ["takedown.read"]}, B]),
           "E_WAIVE_SCOPE")
    reject("4f 审批人 scope 与本案不匹配 → 拒",
           lambda: waive([{"actor": "carol", "scopes": ["takedown.waive"],
                           "scope_match": False}, B]), "E_WAIVE_SCOPE")
    reject("4g ★ 原签发人不得唯一（两格都是他）→ 拒",
           lambda: waive([A, {"actor": "carol", "scopes": ["takedown.waive"]}]),
           "E_WAIVE_ACTOR")
    reject("4h 缺 reason → 拒", lambda: waive([A, B], reason="  "), "E_WAIVE_REASON")
    reject("4i 缺 evidence → 拒", lambda: waive([A, B], evidence=[]), "E_WAIVE_EVIDENCE")

    # 4j：原签发人作为**其中一人**是允许的 —— 防「一律拒绝」式误拦
    try:
        waive([A, B], signer="carol")   # carol 是 A，还有 dave
        ok("4j 原签发人可作其中一人（不是唯一）→ 通过", True, "通过")
    except TD.TakedownError as e:
        ok("4j 原签发人可作其中一人（不是唯一）→ 通过", False, str(e))

    # ═════════ 5. 提醒去重 ═════════
    led = TD.ReminderLedger()
    t0 = datetime(2026, 10, 16, 9, 0, tzinfo=TD.BJT)
    ok("5a 同日第一次提醒 → 该发", led.should_remind_daily("td-1", t0) is True, "")
    ok("5b 同日第二次提醒 → 不发（去重）",
       led.should_remind_daily("td-1", t0.replace(hour=20)) is False, "")
    ok("5c 次日 → 重新该发",
       led.should_remind_daily("td-1", t0 + timedelta(days=1)) is True, "")

    # 5d：★ 北京日期口径 —— UTC 23:30 是北京次日 07:30，必须算新的一天
    utc_late = datetime(2026, 10, 16, 23, 30, tzinfo=timezone.utc)
    ok("5d ★ 去重键用北京日期（UTC 23:30 → 北京次日）",
       TD.bj_date(utc_late) == "2026-10-17", f"bj_date={TD.bj_date(utc_late)}")

    ok("5e 同一 event_id 只通知一次",
       led.should_notify_event("ev-1") is True
       and led.should_notify_event("ev-1") is False, "")
    ok("5f 不同 event_id 各通知一次", led.should_notify_event("ev-2") is True, "")

    # 5g：★ 两种键不许混 —— 同日第二次状态变化仍须通知
    led2 = TD.ReminderLedger()
    led2.should_remind_daily("td-9", t0)
    ok("5g ★ 每日去重不影响当日状态变化通知（两种键独立）",
       led2.should_notify_event("ev-a") is True
       and led2.should_notify_event("ev-b") is True, "")

    # ═════════ 6. 无硬时限 ═════════
    try:
        TD.check_no_deadline(task)
        ok("6a 正常任务无 deadline 字段 → 通过", True, "通过")
    except TD.TakedownError as e:
        ok("6a 正常任务无 deadline 字段 → 通过", False, str(e))

    for bad_key in ("deadline", "due_at", "expires_at"):
        reject(f"6b ★ 任务带 {bad_key} → 拒",
               (lambda k=bad_key: TD.check_no_deadline({**task, k: "2026-11-01"})),
               "E_NO_DEADLINE")

    # 6c：指标视图只有年龄与未完成数
    mv = TD.metrics_view([task, dict(task, task_id="td-2", state="completed")],
                         now=datetime(2026, 10, 18, 0, 0, tzinfo=TD.BJT))
    ok("6c 指标：只数未完成、给出年龄",
       mv["open_count"] == 1 and mv["oldest_age_days"] == 3.0,
       f"open={mv['open_count']} oldest={mv['oldest_age_days']}")
    ok("6d ★ 指标结构里没有任何超时判定字段",
       not ({"overdue", "on_time", "healthy", "is_late"} & set(mv)),
       f"keys={sorted(mv)}")

    reject("6e ★ 指标文案出现「未超时」→ 拒",
           lambda: TD.check_metrics_wording("下线任务进行中（未超时）"), "E_METRICS_WORDING")
    reject("6f ★ 指标文案出现「正常」→ 拒",
           lambda: TD.check_metrics_wording("全部任务正常"), "E_METRICS_WORDING")
    try:
        TD.check_metrics_wording("未完成 3 个，最久的已挂 6 天")
        ok("6g 合规文案（年龄+未完成数）放行", True, "通过")
    except TD.TakedownError as e:
        ok("6g 合规文案（年龄+未完成数）放行", False, str(e))

    # ═════════ 7. 系统不碰外部平台（静态断言）═════════
    src = (ROOT / "base" / "takedown.py").read_text(encoding="utf-8")
    net_hits = re.findall(r"\b(requests|urllib\.request|httpx|aiohttp|fetch\()", src)
    ok("7a ★ takedown.py 里没有任何外部平台调用", not net_hits,
       f"命中 {set(net_hits) or '无'}")

    # ── 汇总 ──
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 72)
    print("takedown 契约验收（RL-7 / RL-8 / RL-9 / RL-13）")
    print("=" * 72)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<50} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return 0
    print(f"✗ {passed}/{total} 项通过；红项：{[n for n, p, _ in results if not p]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
