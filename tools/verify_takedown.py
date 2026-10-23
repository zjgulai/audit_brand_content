#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_takedown.py —— 下线任务契约验收（RL-7 / RL-8 / RL-9 / RL-13）

八组断言，每组都有反向对照（坏样本必须红、好样本必须绿）：
  1. 状态机：合法迁移过、非法迁移拒、失败态三处置
  2. 创建条件：已发布才建、未发布 not_applicable、reason 必须是 trigger 本身
  3. 回填证据：三必填 + 三选一 + 截图三项硬条件
  4. waive：双人 / 都要 scope / 执行人不可自批 / 原签发人不得唯一 / reason+evidence
  5. 提醒去重：每日键=task_id+北京日期、事件键=event_id、**两种键不许混**
  6. 无硬时限：结构里没有 deadline、指标里没有「正常/未超时」；
     ★ 年龄读真实时钟（+1/+3/+6 三点逐一钉 + 归零反向对照）、禁词 8 词逐词动态断言
  7. 系统不碰外部平台（静态）
  8. ★ 通知链路（2026-10-24 行 95/101 补票）：建任务 notify_created 走**真实
     NotificationOutbox.emit**、failed/completed 迁移各发对应事件、
     三方收件人 = 负责人+全部复核人；全部不打桩 STATE_EVENT

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

# ★ 行 95/101 补票（2026-10-24）：通知链路断言必须走**真实** NotificationOutbox
#   —— 自己造一个 emit() 桩，等于把 STATE_EVENT 的两个值写进桩里再断言桩，
#   与生产代码零关联（探针 101b 正是这么 survive 的）。
#   notifications 真不在盘上时整组 8x 落 ⚠ 未测（退出码 2），不许当全绿。
try:
    from base import notifications as NF
except Exception as e:  # noqa: BLE001
    NF = None
    _NF_IMPORT_ERR = f"{type(e).__name__}: {e}"


def _sent_kinds(*records):
    """从 outbox.records / snapshot 里取出 kind 序列（保序，含重复）。"""
    return [r.get("payload", {}).get("kind") or r.get("ntype") for r in records]


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

    # 2e：★ 2026-10-24 行 95 补票 —— 建任务时 reason 必须原样携带 trigger。
    #   探针 95b：reason 改成固定串 "hook-never-ran" 后验证器仍全绿 ——
    #   2a/2b 只看 create 布尔，reason 没有任何断言。两条都钉：
    #   是 trigger 本身、且不是别的已知 trigger（互斥，防「一律返回 revoke」恒真）。
    for _tg in ("revoke", "invalidated"):
        _r2 = TD.should_create_task(trigger=_tg, published=True)
        ok(f"2e ★ 已发布建任务 reason={_tg}（原样携带 trigger）",
           _r2["reason"] == _tg, f"reason={_r2['reason']!r}")
    _rx = TD.should_create_task(trigger="revoke", published=True)
    ok("2f ★ reason 不许是另一个 trigger（互斥反向对照）",
       _rx["reason"] != "invalidated", f"reason={_rx['reason']!r}")

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

    # 6c1–6c4：★ 2026-10-24 行 96 补票 —— 年龄必须读**真实时钟**。
    #   探针 96a：整行 `age = (now_dt - c.astimezone(BJT)).total_seconds() / 86400.0`
    #   换成常量 `age = 3.0` 后验证器仍全绿 —— 6c 的单一时点（3.0）恰好被常量对上，
    #   「年龄随 created 与 now 递增、随归零反向对照变化」没有任何断言。
    #   四个点连起来，常量 age 在至少两点上必然错：
    #     +1 天 → 1.0   +3 天 → 3.0   +6 天 → 6.0（三点逐一钉，防「常量撞单点」）
    #     归零反向对照：now == created → oldest 必须是 0.0（证明读的是真实差值）
    for _d, _want in ((1, 1.0), (3, 3.0), (6, 6.0)):
        _m = TD.metrics_view([task], now=datetime(2026, 10, 15, 0, 0, tzinfo=TD.BJT)
                             + timedelta(days=_d))
        _one = _m["ages"][0] if _m.get("ages") else {}
        ok(f"6c{_d} ★ 任务年龄 +{_d} 天 = {_want}（真实时钟，非常量）",
           _m["oldest_age_days"] == _want and _one.get("age_days") == _want,
           f"oldest={_m['oldest_age_days']} per_task={_one.get('age_days')}")
    _m0 = TD.metrics_view([task],
                          now=datetime(2026, 10, 15, 0, 0, tzinfo=TD.BJT))
    ok("6c0 ★ 反向对照：年龄归零（now=created）→ 0.0，不许是任何常量",
       _m0["oldest_age_days"] == 0.0, f"oldest={_m0['oldest_age_days']}")

    # 6d：指标结构里不许有超时判定字段
    ok("6d ★ 指标结构里没有任何超时判定字段",
       not ({"overdue", "on_time", "healthy", "is_late"} & set(mv)),
       f"keys={sorted(mv)}")

    # 6d1：★ 行 96 补票 —— 每条任务一行年龄，且 completed 不计数（未完成数递增）
    _tasks3 = [task,
               dict(task, task_id="td-2", state="in_progress"),
               dict(task, task_id="td-3", state="completed")]
    _m3 = TD.metrics_view(_tasks3, now=datetime(2026, 10, 18, 0, 0, tzinfo=TD.BJT))
    ok("6d1 ★ ages 每条未完成任务一行；completed 不入 ages 也不进 open_count",
       _m3["open_count"] == 2 and len(_m3["ages"]) == 2
       and {a["task_id"] for a in _m3["ages"]} == {"td-1", "td-2"},
       f"open={_m3['open_count']} ages={[a['task_id'] for a in _m3['ages']]}")

    # 6e'/6e''：★ 行 96/101 补票 —— 8 个禁词**逐词**动态断言。
    #   探针 96b2：把「按时」从 FORBIDDEN_STATUS_WORDS 里删掉后验证器仍全绿 ——
    #   静态的 6e/6f 只钉了「未超时 / 正常」两个词，其余 6 个词的删除没人管。
    #   两层判据：
    #   ① 6e1 钉**词表本身**（验收器持契约，生产词表是实现）—— 删词/换词/清空全红；
    #   ② 6e2 从生产词表读词、逐词喂坏文案 —— 词表正确时每个词都真被拦。
    #   反向对照：干净文案对**每一个词**都不许误报。
    _CANON_WORDS = ("正常", "未超时", "按期", "按时",
                    "on_time", "on_track", "healthy", "no_delay")
    _fw = tuple(getattr(TD, "FORBIDDEN_STATUS_WORDS", ()))
    ok("6e1 ★ FORBIDDEN_STATUS_WORDS 必须恰好是契约里的 8 个词（删词/换词全红）",
       set(_fw) == set(_CANON_WORDS),
       f"缺={sorted(set(_CANON_WORDS) - set(_fw))} 多={sorted(set(_fw) - set(_CANON_WORDS))}")
    for _w in _fw:
        reject(f"6e2 ★ 指标文案出现「{_w}」→ 拒（词表逐词钉死）",
               (lambda w=_w: TD.check_metrics_wording(f"下线任务进度：{_w}")),
               "E_METRICS_WORDING")
    try:
        TD.check_metrics_wording("未完成 3 个，最久的已挂 6 天")
        ok("6g 合规文案（年龄+未完成数）放行", True, "通过")
    except TD.TakedownError as e:
        ok("6g 合规文案（年龄+未完成数）放行", False, str(e))
    ok("6g2 ★ 反向对照：干净文案对每个禁词都不许误报",
       all(w not in "未完成 3 个，最久的已挂 6 天" for w in _fw),
       f"checked={len(_fw)} words")

    # ═════════ 7. 系统不碰外部平台（静态断言）═════════
    src = (ROOT / "base" / "takedown.py").read_text(encoding="utf-8")
    net_hits = re.findall(r"\b(requests|urllib\.request|httpx|aiohttp|fetch\()", src)
    ok("7a ★ takedown.py 里没有任何外部平台调用", not net_hits,
       f"命中 {set(net_hits) or '无'}")

    # ═════════ 8. 通知链路（2026-10-24 行 95/101 补票）═════════
    #
    #   探针 95a：notify_created 一进来就 raise → 本验证器 54/54 全绿
    #   （grep notify_created 0 命中，且该函数全仓 0 调用点）。
    #   探针 101b：STATE_EVENT 删掉 failed 一项 → 仍全绿（本脚本
    #   outbox/STATE_EVENT 0 命中；只有相邻的 verify_notifications 抓它）。
    #   三方收件人（负责人/复核侧）0 断言。
    #
    #   修法：**不造 emit 桩** —— 桩里的字面量会和 STATE_EVENT 各写一遍然后
    #   只断言桩自己（正是那个病）。这里用**真实** NotificationOutbox：
    #   transition/complete/notify_created 每个出口都真正穿过
    #   notification_for() → DedupLedger → default_recipients() 全链。
    #   notifications 不在盘上 → 整个验收器落 ⚠ 未测并退 2（与 import takedown
    #   失败同口径），不许静默全绿。
    if NF is None:
        print(f"⚠ 未测：import notifications 失败（{_NF_IMPORT_ERR}）"
              " —— 行 95/101 的通知链路断言全部未测", file=sys.stderr)
        return 2
    if True:
        def _box():
            return NF.NotificationOutbox(dedup=NF.DedupLedger())

        # 8a：建任务通知走真实 emit —— notify_created 不发就红
        _t_new = TD.new_task(
            task_id="td-95", case_id="case-1", platform="tiktok",
            tenant="momcozy", product_line="breast-pump",
            created_at="2026-10-15T00:00:00+08:00", assignee="alice",
            reviewers=["bob", "carol"])
        _b0 = _box()
        # ★ try/except 不是装饰：变异把 notify_created 改成「一进来就 raise」时，
        #   这里必须落一条红项，而不是让 traceback 把整个验收器打死 ——
        #   崩溃在 mutprobe 的口径里是 untested，红项才是 killed。
        try:
            TD.notify_created(_t_new, outbox=_b0, at="2026-10-15T00:00:00+08:00")
            _notify_err = ""
        except Exception as e:  # noqa: BLE001
            _notify_err = f"{type(e).__name__}: {e}"
        _kinds0 = _sent_kinds(*_b0.records)
        ok("8a ★ 建任务通知（notify_created → 真实 outbox emit takedown_created）",
           not _notify_err and _kinds0.count("takedown_created") == 3,
           _notify_err or f"kinds={_kinds0}")

        # 8b：failed 迁移立即通知 —— STATE_EVENT 删掉 failed 一项就红。
        #   走一次「失败 → retry 回 in_progress → 再失败」：
        #   同一个任务两次失败都必须各发一次（只拿 task_id 当键会吞掉第二次）。
        _b1 = _box()
        _tf95 = TD.transition(_t_new, "in_progress", at="2026-10-15T09:00:00+08:00",
                              outbox=_b1)
        _tf95 = TD.transition(_tf95, "failed", at="2026-10-15T10:00:00+08:00",
                              outbox=_b1)
        _tf95 = TD.transition(_tf95, "in_progress", action="retry",
                              at="2026-10-15T11:00:00+08:00", outbox=_b1)
        _tf95 = TD.transition(_tf95, "failed", at="2026-10-15T12:00:00+08:00",
                              outbox=_b1)
        _kinds1 = _sent_kinds(*_b1.records)
        ok("8b ★ failed 迁移 → 立即 emit takedown_failed（真实链路，两次失败各一次）",
           _kinds1.count("takedown_failed") == 6, f"kinds={_kinds1}")

        # 8c：completed 迁移发 takedown_completed（含 complete() 包装）
        _b2 = _box()
        _tc95 = TD.transition(_t_new, "in_progress", at="2026-10-15T09:00:00+08:00",
                              outbox=_b2)
        TD.complete(_tc95, {"platform": "tiktok", "executed_by": "alice",
                            "executed_at": "2026-10-16T09:00:00+08:00",
                            "receipt_id": "R-95"},
                    at="2026-10-16T09:00:00+08:00", outbox=_b2)
        _kinds2 = _sent_kinds(*_b2.records)
        ok("8c ★ completed 迁移 → emit takedown_completed",
           "takedown_completed" in _kinds2, f"kinds={_kinds2}")

        # 8d：迁移失败必须一个事件都不发（「必须事后」的反向对照）
        _b3 = _box()
        try:
            TD.transition(_t_new, "completed", at="2026-10-15T01:00:00+08:00",
                          outbox=_b3)   # pending → completed 跳步，必须拒
        except TD.TakedownError:
            pass
        ok("8d ★ 迁移失败 → 一个事件都不发（必须事后报）",
           len(_b3.records) == 0, f"records={len(_b3.records)}")

        # 8e：三方收件人 —— 负责人 + 每一位复核人，各一条 takedown
        _recips = [r.get("recipient") for r in _b0.records]
        _ntypes = {r.get("type") for r in _b0.records}
        ok("8e ★ 三方收件人：负责人 + 每一位复核人，各收到 takedown 通知",
           set(_recips) == {"alice", "bob", "carol"} and _ntypes == {"takedown"},
           f"recipients={_recips} types={sorted(_ntypes)}")

        # 8f：同一个任务两次失败的事件键互不相同（task_id+序号+状态）
        _evs = [r.get("payload", {}).get("event_id") for r in _b1.records]
        results.append(("8f ★ 同一任务两次失败的事件 event_id 互不相同（不许拿 task_id 当键）",
                        len(_evs) == 6 and len(set(_evs)) == 2
                        and all(_evs), f"event_ids={sorted(set(_evs))} n={len(_evs)}"))

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


# ═══════════════════ --controls：行 95/96/101 离线反向对照 ═══════════════════
#
# main() 里的判据吃的是**真实生产代码**；这一段喂构造的坏实现形状，
# 证明每个判据在该红时真的红、对好实现不许误报：
#   行 95 —— notify_created 出口：坏实现（不发事件）必须红、真实现必须绿
#   行 96 —— 年龄判据针：常量 age 在 +1/+6 两点上必错、归零对照必错；禁词逐词针
#   行 101 —— STATE_EVENT 出口：failed 不发事件必须红、completion 绿；
#             三方收件人针；干净文案不许被禁词针误伤
# 任何一条不成立 → 退 1。

def controls() -> int:
    fails = []
    n_cases = [0]

    def ok(name, cond, detail=""):
        n_cases[0] += 1
        cond = bool(cond)
        if not cond:
            fails.append(name)
        print("  %s %s %s" % ("✅" if cond else "❌", name, detail))

    print("=" * 78)
    print("takedown · 离线反向对照（--controls · 行 95/96/101 判据针）")
    print("=" * 78)

    task = TD.new_task(
        task_id="td-ctl", case_id="case-ctl", platform="tiktok",
        tenant="momcozy", product_line="breast-pump",
        created_at="2026-10-15T00:00:00+08:00", assignee="alice",
        reviewers=["bob", "carol"])
    created = datetime(2026, 10, 15, tzinfo=TD.BJT)

    # ── 行 95：建任务通知出口 ──
    # 坏实现形状 ①：notify_created 什么都不发（95d 变异「一进来就 raise」的
    #   等效形状 —— 出口被改没了）。8a 判据针对「零事件」必须红。
    class _SilentOutbox:
        records = []

    ok("95-坏① notify_created 不发事件（出口改没）→ 8a 判据针必须红",
       _sent_kinds(*_SilentOutbox.records).count("takedown_created") != 3,
       "kinds=[]")
    _bctl = NF.NotificationOutbox(dedup=NF.DedupLedger())
    TD.notify_created(task, outbox=_bctl, at="2026-10-15T00:00:00+08:00")
    _k = _sent_kinds(*_bctl.records)
    ok("95-好② 真实现 notify_created → 判据针不许误报",
       _k.count("takedown_created") == 3, f"kinds={_k}")

    # ── 行 96：年龄判据针 ──
    # 坏实现形状：age 读常量 3.0（即 96a 的变异）—— 三点 + 归零对照上必错
    class _ConstAge:
        """探针 96a 的坏实现形状：metrics_view 返回常量年龄。"""
        @staticmethod
        def view(tasks, *, now=None):
            n = len([t for t in tasks if t.get("state") != "completed"])
            return {"open_count": n, "oldest_age_days": 3.0,
                    "ages": [{"task_id": t.get("task_id"), "state": t.get("state"),
                              "age_days": 3.0} for t in tasks
                             if t.get("state") != "completed"]}

    _bad = []
    for _d, _want in ((1, 1.0), (6, 6.0)):
        _v = _ConstAge.view([task], now=created + timedelta(days=_d))
        if _v["oldest_age_days"] != _want:
            _bad.append(f"+{_d}d")
    _v0 = _ConstAge.view([task], now=created)
    if _v0["oldest_age_days"] != 0.0:
        _bad.append("zero")
    ok("96-坏① 常量年龄（age=3.0 形状）→ 三点/归零判据针至少两点红",
       len(_bad) >= 2, f"wrong_at={_bad}")
    _good_at = []
    for _d, _want in ((1, 1.0), (3, 3.0), (6, 6.0)):
        _v = TD.metrics_view([task], now=created + timedelta(days=_d))
        if _v["oldest_age_days"] != _want:
            _good_at.append(f"+{_d}d")
    _v0g = TD.metrics_view([task], now=created)
    ok("96-好② 真实现年龄 → 三点/归零判据针全部放行（不许误报）",
       not _good_at and _v0g["oldest_age_days"] == 0.0,
       f"ages={[_v['oldest_age_days'] for _v in (TD.metrics_view([task], now=created + timedelta(days=_d)) for _d in (1, 3, 6))]}")

    # ── 行 96：禁词判据针（逐词，词表从生产代码读）──
    _fw = tuple(getattr(TD, "FORBIDDEN_STATUS_WORDS", ()))
    clean = "未完成 3 个，最久的已挂 6 天"
    for _w in _fw:
        _hit_bad = _w in f"下线任务进度：{_w}"          # 坏文案：该词在场 → 必须抓
        _hit_clean = _w in clean                        # 好文案：不许误伤
        ok(f"96-词「{_w}」坏文案必须红、干净文案不许误伤",
           _hit_bad and not _hit_clean, f"bad={_hit_bad} clean={_hit_clean}")
    ok("96-表① 词表非空（清空词表的坏实现不许通过）", len(_fw) >= 8,
       f"words={list(_fw)}")

    # ── 行 101：STATE_EVENT 出口（failed / completed / 收件人）──
    # 坏实现形状 ②：STATE_EVENT 缺 failed（即 101b 的变异）→
    # failed 迁移在真实 outbox 上产生 0 条 failed 事件 → 8b 判据针必须红
    _orig = dict(TD.STATE_EVENT)
    try:
        TD.STATE_EVENT.pop("failed", None)
        _bmut = NF.NotificationOutbox(dedup=NF.DedupLedger())
        _tm = TD.transition(task, "in_progress", at="2026-10-15T09:00:00+08:00",
                            outbox=_bmut)
        TD.transition(_tm, "failed", at="2026-10-15T10:00:00+08:00",
                      outbox=_bmut)
        _km = _sent_kinds(*_bmut.records)
        ok("101-坏② STATE_EVENT 缺 failed → failed 迁移不发事件（8b 针必须红）",
           _km.count("takedown_failed") != 3, f"kinds={_km}")
    finally:
        TD.STATE_EVENT.clear()
        TD.STATE_EVENT.update(_orig)
    # 坏实现形状 ③：整个 STATE_EVENT 清空 → completed 也不发（8c 针必须红）
    try:
        TD.STATE_EVENT.clear()
        _bmut2 = NF.NotificationOutbox(dedup=NF.DedupLedger())
        _tm2 = TD.transition(task, "in_progress", at="2026-10-15T09:00:00+08:00",
                             outbox=_bmut2)
        TD.complete(_tm2, {"platform": "tiktok", "executed_by": "alice",
                           "executed_at": "2026-10-16T09:00:00+08:00",
                           "receipt_id": "R-ctl"},
                    at="2026-10-16T09:00:00+08:00", outbox=_bmut2)
        _km2 = _sent_kinds(*_bmut2.records)
        ok("101-坏③ STATE_EVENT 清空 → completed 也不发事件（8c 针必须红）",
           "takedown_completed" not in _km2, f"kinds={_km2}")
    finally:
        TD.STATE_EVENT.update(_orig)
    # 好样本：真实现两个出口都发、收件人三方
    _bg = NF.NotificationOutbox(dedup=NF.DedupLedger())
    _tg = TD.transition(task, "in_progress", at="2026-10-15T09:00:00+08:00",
                        outbox=_bg)
    TD.transition(_tg, "failed", at="2026-10-15T10:00:00+08:00", outbox=_bg)
    _kg = _sent_kinds(*_bg.records)
    _rg = [r.get("recipient") for r in _bg.records]
    ok("101-好④ 真实现 failed 出口 → 8b/8e 针不许误报（failed × 3 收件人）",
       _kg.count("takedown_failed") == 3
       and set(_rg) >= {"alice", "bob", "carol"},
       f"kinds={_kg} recipients={_rg}")

    print("-" * 78)
    if fails:
        print("❌ %d 项失败：%s" % (len(fails), fails))
        return 1
    print("✅ %d 项全过（该红、该绿都有）" % n_cases[0])
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"UNTESTED: 验收器自身异常: {exc}")
        sys.exit(2)
