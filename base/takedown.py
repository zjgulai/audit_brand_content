#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/takedown.py —— 强制下线任务（RL-7 / RL-8 / RL-9 / RL-13）

**它是什么**：一条已发布内容被撤回或自动失效后生成的「去平台上把它弄下来」的任务。
**它不是什么**：它**不调用任何外部平台**。系统只跟踪任务；真正下线由有权限的人执行并回填。

--------------------------------------------------------------------------
★ 六条本文件刻意做死的事（每条都对应一条判据，且都有反向对照）
--------------------------------------------------------------------------

**一、状态机：`pending → in_progress → completed / failed`，failed 可 retry / reassign / waive**

**二、只有「已发布」才建任务**

    没发布过的东西没有需要下线的对象。给它建任务会制造一条永远做不完的假待办。

**三、回填最小证据：无证据不得 complete**

    `platform` + `executed_by` + `executed_at` 必填；
    **至少**一个：平台回执号 / 可访问结果链接；两者都没有时截图可替代
    （截图落**仓外**、记 sha256、**不进公开仓**）。

**四、waive 是两道独立的门，缺一不可**

    ① **两个人**（不同的人）
    ② 两人都具备**匹配 scope** 的 `takedown.waive` 权限
    ③ **执行人不能自批**
    ④ **原签发人可作其中一人，但不得是唯一一人**
    ⑤ `reason` + `evidence` 必填

**五、提醒去重 + 无硬时限**

    每日提醒去重键 = `task_id + 北京日期`
    状态变化去重键 = `event_id`
    **没有 deadline 字段**，且**指标里不许出现「正常 / 未超时」** ——
    只许显示**任务年龄**与**未完成数**。

    ★ 这是 RL-8 最容易被做错的一条：一个没有截止日的任务，
      在绝大多数看板上会显示成「进行中（正常）」—— 那是**用缺省值伪装成判断**。

**六、系统不碰外部平台**

    本文件里没有任何 HTTP 调用。这条由 verify 的静态断言守住。
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

# ★ 「今天」与 +08:00 只有一处来源：tools/bj_time.py（2026-10-21 统一）。
_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from bj_time import BJ as BJT, bj_today  # noqa: E402

# ── 状态机 ──────────────────────────────────────────────
STATES = ("pending", "in_progress", "completed", "failed")

# 允许的迁移。**封闭集合** —— 不在表里的迁移一律拒。
TRANSITIONS = {
    "pending":     {"in_progress", "failed"},
    "in_progress": {"completed", "failed"},
    "failed":      {"in_progress", "pending", "completed"},  # retry / reassign 回到 in_progress 或 pending
    "completed":   set(),                                     # 终态
}

# failed 之后的三种人工处置
FAILED_ACTIONS = frozenset({"retry", "reassign", "waive"})

# 回填必填
EVIDENCE_REQUIRED = ("platform", "executed_by", "executed_at")

# ★ 状态迁移 → 通知动作名。**封闭集合**：不在表里的迁移不产生通知。
#   键必须同时出现在 notifications.EVENT_TYPE 里，由 verify_notifications 断言
#   —— 两处各写一遍就会各自漂移，所以要有一条断言钉住它们相等。
STATE_EVENT = {
    "completed": "takedown_completed",
    "failed": "takedown_failed",
}

# 取证方式：三选一（前两个是首选，截图是兜底）
EVIDENCE_KINDS = frozenset({"receipt_id", "result_url", "screenshot"})

# 明确禁止出现在指标文案里的词（RL-8）
FORBIDDEN_STATUS_WORDS = (
    "正常", "未超时", "按期", "按时", "on_time", "on_track", "healthy", "no_delay",
)


class TakedownError(Exception):
    """业务拒绝。带 code 便于断言；每条都要说清是哪一条不满足。"""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def bj_date(ts: datetime | float | None = None) -> str:
    """北京日期 YYYY-MM-DD。**所有「日」的口径都用它**，不用 UTC 日期。"""
    if ts is None:
        return bj_today().isoformat()
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, BJT)
    else:
        dt = ts.astimezone(BJT) if ts.tzinfo else ts.replace(tzinfo=timezone.utc).astimezone(BJT)
    return dt.strftime("%Y-%m-%d")


# ═══════════════════════ ① 创建条件 ═══════════════════════

def should_create_task(*, trigger: str, published: bool) -> dict:
    """
    要不要建下线任务。

    `trigger` ∈ {revoke, invalidated}（撤回 / 自动失效）
    `published` —— 这条内容**到底有没有发到平台上**

    返回 {"create": bool, "reason": str}
    ★ 未发布 → create=False 且 reason=「not_applicable」。
      注意这里用 not_applicable 是**对的** —— 它真的不适用，与覆盖证明里
      「空族不许写 not_applicable」是两回事（那里是「还没做」被伪装成「不适用」）。
    """
    if trigger not in ("revoke", "invalidated"):
        raise TakedownError("E_TRIGGER", f"trigger={trigger!r} 不在 revoke/invalidated")
    if not published:
        return {"create": False, "reason": "not_applicable",
                "detail": "内容从未发布，没有需要下线的对象"}
    return {"create": True, "reason": trigger,
            "detail": "已发布内容被撤回/失效，生成强制下线任务"}


# ═══════════════════════ ② 状态机 ═══════════════════════

def check_transition(old: str, new: str, *, action: str | None = None) -> None:
    """校验一次状态迁移。非法即抛。"""
    if old not in STATES:
        raise TakedownError("E_STATE", f"未知状态 {old!r}")
    if new not in STATES:
        raise TakedownError("E_STATE", f"未知状态 {new!r}")
    if new not in TRANSITIONS[old]:
        raise TakedownError(
            "E_TRANSITION", f"不允许 {old} → {new}（允许：{sorted(TRANSITIONS[old]) or '终态'}）")
    if old == "failed" and action is not None and action not in FAILED_ACTIONS:
        raise TakedownError(
            "E_ACTION", f"failed 之后的处置 action={action!r} 不在 {sorted(FAILED_ACTIONS)}")


# ═══════════════════════ ③ 回填校验 ═══════════════════════

def check_evidence(evidence: dict | None, *, repo_root: str | None = None) -> dict:
    """
    回填最小证据校验。**无证据不得 complete。**

    返回规范化后的 evidence（供落盘）。

    截图通道的三个硬条件（任一不满足即拒）：
      · 路径必须是**仓外**（`repo_root` 前缀判定）
      · 必须带 sha256
      · 必须标 `never_tracked: true`
    """
    if not isinstance(evidence, dict):
        raise TakedownError("E_EVIDENCE", "回填证据必须是对象（无证据不得 complete）")

    for k in EVIDENCE_REQUIRED:
        v = evidence.get(k)
        if not isinstance(v, str) or not v.strip():
            raise TakedownError("E_EVIDENCE", f"回填缺必填字段 `{k}`")

    kinds = [k for k in EVIDENCE_KINDS if evidence.get(k)]
    if not kinds:
        raise TakedownError(
            "E_EVIDENCE",
            "至少要有一个：平台回执号 / 可访问结果链接 / 截图（三者都没有 = 无证据）")

    out = dict(evidence)

    if "screenshot" in kinds:
        shot = evidence.get("screenshot")
        if not isinstance(shot, dict):
            raise TakedownError("E_SCREENSHOT", "screenshot 必须是对象（path/sha256/never_tracked）")
        path = str(shot.get("path") or "")
        if not path:
            raise TakedownError("E_SCREENSHOT", "screenshot 缺 path")
        if not str(shot.get("sha256") or "").strip():
            raise TakedownError("E_SCREENSHOT", "screenshot 必须记 sha256（否则无法证明没被换过）")
        if shot.get("never_tracked") is not True:
            raise TakedownError(
                "E_SCREENSHOT", "screenshot 必须标 `never_tracked: true` —— 不许进公开仓")
        # 仓外判定
        if repo_root:
            rp = repo_root.rstrip("/") + "/"
            if path.startswith(rp) or path == repo_root.rstrip("/"):
                raise TakedownError(
                    "E_SCREENSHOT", f"截图路径 {path!r} 在仓库内 —— 不许进公开仓")

    return out


# ═══════════════════════ ④ waive 双人审批 ═══════════════════════

def check_waive(*, approvers: Sequence[dict], executor: str,
                original_signer: str | None, reason: str | None,
                evidence: Any, required_scope: str = "takedown.waive") -> dict:
    """
    豁免审批。五条同时成立，缺一即拒。

    `approvers` 每项：{"actor": str, "scopes": [str, ...], "scope_match": {...}|None}

    ★ 「原签发人可作其中一人但不得唯一」这一条：
      允许原签发人参与，是因为他最了解这条内容为什么被签；
      不允许他唯一批准，是因为那等于让签发人自己撤销自己的判断，没有第二双眼睛。
    """
    if not isinstance(approvers, (list, tuple)) or len(approvers) != 2:
        raise TakedownError(
            "E_WAIVE_APPROVERS",
            f"waive 必须恰好两名审批人（实际 {len(approvers) if isinstance(approvers,(list,tuple)) else 'N/A'} 名）")

    actors = [str((a or {}).get("actor") or "") for a in approvers]
    if any(not x for x in actors):
        raise TakedownError("E_WAIVE_ACTOR", "审批人必须有 actor")
    if len(set(actors)) != 2:
        raise TakedownError("E_WAIVE_ACTOR", f"两名审批人必须是不同的人：{actors}")

    # ① 两人都要有匹配 scope 的权限
    for a in approvers:
        scopes = set(a.get("scopes") or [])
        if required_scope not in scopes:
            raise TakedownError(
                "E_WAIVE_SCOPE",
                f"{a.get('actor')!r} 没有 {required_scope} 权限（持有：{sorted(scopes)}）")
        if a.get("scope_match") is False:
            raise TakedownError(
                "E_WAIVE_SCOPE", f"{a.get('actor')!r} 的 scope 与本案不匹配（租户/品线/平台）")

    # ② 执行人不能自批
    if executor in actors:
        raise TakedownError(
            "E_SELF_APPROVE", f"执行人 {executor!r} 不能审批自己的任务")

    # ③ 原签发人可作其一，但不得唯一
    #    这里 len(set(actors)) == 2 已经保证不是唯一；再显式断言一次，
    #    是为了让「原签发人 + 他自己」这种退化写法也被抓住。
    if original_signer:
        if actors.count(original_signer) == 2:
            raise TakedownError(
                "E_SIGNER_ONLY", "原签发人不得作为唯一审批人（两个名额不能都是他）")

    # ④ reason + evidence 必填
    if not isinstance(reason, str) or not reason.strip():
        raise TakedownError("E_WAIVE_REASON", "waive 必须写 reason")
    if evidence is None or (isinstance(evidence, (list, dict, str)) and len(evidence) == 0):
        raise TakedownError("E_WAIVE_EVIDENCE", "waive 必须带 evidence")

    return {"approvers": actors, "executor": executor, "reason": reason}


# ═══════════════════════ ⑤ 提醒去重 + 无硬时限 ═══════════════════════

class ReminderLedger:
    """
    提醒去重。两种键，各管一件事：

      每日提醒  —— key = `task_id + 北京日期`        （RL-13：每日一次，不许多）
      状态变化  —— key = `event_id`                  （RL-13：变化立即通知，但不重复）

    ★ 两种键**不能混用**：拿 task_id+日期 去重状态变化，会让同一天的三次状态变化只通知一次。
    """

    def __init__(self) -> None:
        self._daily: set[str] = set()
        self._events: set[str] = set()

    def daily_key(self, task_id: str, ts: datetime | float | None = None) -> str:
        return f"{task_id}|{bj_date(ts)}"

    def should_remind_daily(self, task_id: str, ts: datetime | float | None = None) -> bool:
        """返回 True 表示「该发」，同时记账（同日第二次返回 False）。"""
        k = self.daily_key(task_id, ts)
        if k in self._daily:
            return False
        self._daily.add(k)
        return True

    def should_notify_event(self, event_id: str) -> bool:
        """状态变化去重：同一 event_id 只通知一次。"""
        if event_id in self._events:
            return False
        self._events.add(event_id)
        return True


def check_no_deadline(task: dict) -> None:
    """
    RL-8：**不设硬时限**。任务里不许出现 deadline 类字段。

    ★ 这条不是洁癖：一个 deadline 字段会让下游看板自动算出「未超时」的绿标，
      而那正是合同禁止的「用缺省值伪装成判断」。
    """
    banned = [k for k in task
              if k.lower() in ("deadline", "due_at", "expires_at", "sla_deadline", "due_date")]
    if banned:
        raise TakedownError(
            "E_NO_DEADLINE", f"下线任务不许有硬时限字段：{banned}（RL-8）")


def metrics_view(tasks: Iterable[dict], *, now: datetime | float | None = None) -> dict:
    """
    指标视图。**只许出现「任务年龄」与「未完成数」，不许出现超时判定。**

    返回 {"open_count": int, "oldest_age_days": float, "ages": [{task_id, age_days, state}]}
    ★ 没有 "on_time" / "overdue" / "healthy" 这类字段 —— 结构上就不给下游画绿标的机会。
    """
    if now is None:
        now_dt = datetime.now(BJT)
    elif isinstance(now, (int, float)):
        now_dt = datetime.fromtimestamp(now, BJT)
    else:
        now_dt = now.astimezone(BJT) if now.tzinfo else now.replace(tzinfo=timezone.utc).astimezone(BJT)

    ages, open_n = [], 0
    for t in tasks:
        st = t.get("state")
        if st in ("completed",):
            continue
        open_n += 1
        created = t.get("created_at")
        if isinstance(created, str):
            try:
                c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if not c.tzinfo:
                    c = c.replace(tzinfo=timezone.utc)
                age = (now_dt - c.astimezone(BJT)).total_seconds() / 86400.0
            except ValueError:
                age = None
        else:
            age = None
        ages.append({"task_id": t.get("task_id"), "state": st,
                     "age_days": round(age, 2) if age is not None else None})

    valid = [a["age_days"] for a in ages if a["age_days"] is not None]
    return {
        "open_count": open_n,
        "oldest_age_days": max(valid) if valid else None,
        "ages": ages,
    }


def check_metrics_wording(text: str) -> None:
    """指标文案里不许出现「正常 / 未超时」这类判定词。"""
    hits = [w for w in FORBIDDEN_STATUS_WORDS if w in str(text)]
    if hits:
        raise TakedownError(
            "E_METRICS_WORDING",
            f"指标文案里出现了超时判定词 {hits} —— RL-8 要求只显示任务年龄与未完成数")


# ═══════════════════════ 任务对象 ═══════════════════════

def new_task(*, task_id: str, case_id: str, platform: str, tenant: str,
             product_line: str, created_at: str, assignee: str,
             reviewers: Sequence[str] | None = None) -> dict:
    """建一个 pending 任务。**结构里没有 deadline。**"""
    return {
        "task_id": task_id,
        "case_id": case_id,
        "platform": platform,
        "tenant": tenant,
        "product_line": product_line,
        "state": "pending",
        "assignee": assignee,
        "reviewers": list(reviewers or []),
        "created_at": created_at,
        "history": [],
    }


def transition(task: dict, new_state: str, *, action: str | None = None,
               at: str | None = None, outbox=None) -> dict:
    """迁移并留痕。返回新任务副本（不改入参）。

    ★ `outbox` 可选：给了就在**迁移成功之后**报一次事件。
      必须是事后 —— 迁移失败（非法迁移）时不产生通知，
      否则群里会先收到「任务失败了」，然后才收到「其实没失败」。
    """
    import copy
    t = copy.deepcopy(task)
    check_transition(t.get("state"), new_state, action=action)
    t["history"].append({"from": t["state"], "to": new_state, "action": action, "at": at})
    old_state = t["state"]
    t["state"] = new_state
    if outbox is not None:
        kind = STATE_EVENT.get(new_state)
        if kind is not None:
            # ★ 去重键：任务 id + 迁移序号 + 新状态。
            #   同一个任务可以 failed 多次（retry 后再 fail），
            #   只拿 task_id 当键会把第二次失败吞掉。
            outbox.emit(event_id="takedown:%s:%d:%s" % (
                            t.get("task_id"), len(t["history"]), new_state),
                        kind=kind, subject=dict(t), now=at)
    return t


def complete(task: dict, evidence: dict, *, at: str | None = None,
             repo_root: str | None = None, outbox=None) -> dict:
    """完成任务。**证据不合格就不许完成** —— 这是 RL-9 的唯一执行点。"""
    ev = check_evidence(evidence, repo_root=repo_root)   # 先校验，再迁移
    t = transition(task, "completed", at=at, outbox=outbox)
    t["evidence"] = ev
    return t


def notify_created(task: dict, *, outbox, at: str | None = None) -> dict:
    """
    建任务时通知。**单独一个函数，不塞进 `new_task()`。**

    ★ 为什么：`new_task()` 是纯构造函数，验证器拿它造样本用了几十次。
      往里塞通知会让「造一个样本」变成「发一次通知」——
      这正是 §2.4.4 那个病（跑一次自检，改掉了它要保护的东西）。
    """
    if outbox is not None:
        outbox.emit(event_id="takedown:%s:created" % task.get("task_id"),
                    kind="takedown_created", subject=dict(task), now=at)
    return task
