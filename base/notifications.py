#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notifications.py —— 通知服务（TS-22 / RL-13）

**它管两类通知，规则完全不同，不能混：**

| 类别 | 走哪 | 为什么 |
|---|---|---|
| **失效 / 重审**（`invalidation` / `auto_rereview`） | **只进 Web inbox** | 它是「给责任人看的待办」；发到群里会把内部流程变成噪音，而且**群里看得到 ≠ 责任人看到了** |
| **下线任务提醒**（`takedown`） | **飞书** | 它是**对外动作的催办**：内容还在平台上挂着，漏了会出事 |

--------------------------------------------------------------------------
★ 五条本文件刻意做死的事
--------------------------------------------------------------------------

**一、文案只许说「已投递 / 已读」，不许说「已通知到人」**

    系统能证明的只有「投递了、读了」，证明不了「这个人知道了并处理了」。
    把前者说成后者，就是台账 K-05（未测被报成已清）的同一个形状。

**二、去重键必须持久化 —— 重启不重复**

    内存里的 set 一重启就没了，于是「每日提醒」会在每次重启后再发一遍。
    本文件把去重状态落到一个 JSON 文件，且**读不出时选择「不发」**（宁可少发一条，
    不可连发三条）——但要把这件事记成「未测」，不能静默静音。

**三、两种去重键不能混用**

    每日提醒 → `task_id + 北京日期`
    状态变化 → `event_id`
    混用的后果：拿 task_id+日期 去重状态变化，同一天三次变化只通知一次。

**四、失效/重审通知**绝不**调用飞书**

    这条由两个执行点守：`inbox_only` 的类型在发送前被拦，以及
    verify 的静态断言（本文件不 import 任何飞书发送模块）。

**五、读不到去重状态 = 未测，不是「没有发过」**

    返回 `untested=True`，调用方据此**不发并上报**。
    与 verify_solution_meta 的 `L3 未测退 2` 同一个口径。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

BJT = timezone(timedelta(hours=8))

# ── 通知类型 ────────────────────────────────────────────
TYPES = frozenset({"invalidation", "auto_rereview", "takedown",
                   "lease_released", "formal_submit",
                   "release_signed", "release_revoked"})

# 只进 Web inbox、不许发飞书的类型
INBOX_ONLY = frozenset({"invalidation", "auto_rereview",
                        "lease_released", "formal_submit",
                        "release_signed", "release_revoked"})

# 走飞书的类型（下线任务催办）
FEISHU_TYPES = frozenset({"takedown"})

# ── 文案约束 ────────────────────────────────────────────
# 只允许的两个事实：投递了、读了。
ALLOWED_CLAIM_WORDS = ("已投递", "未读", "已读", "已确认")

# **禁止**的措辞：把「投递」说成「人知道了」。
FORBIDDEN_CLAIMS = (
    "已通知到人", "已通知到", "已告知本人", "已传达", "已让本人知悉",
    "已确认收到", "已回复", "已知悉", "notified the person", "person notified",
    "acknowledged by user", "user has seen",
)


class NotificationError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def bj_date(ts: datetime | float | None = None) -> str:
    if ts is None:
        dt = datetime.now(BJT)
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, BJT)
    else:
        dt = ts.astimezone(BJT) if ts.tzinfo else ts.replace(tzinfo=timezone.utc).astimezone(BJT)
    return dt.strftime("%Y-%m-%d")


# ═══════════════════ ① 通知对象 ═══════════════════

def new_notification(*, notification_id: str, recipient: str, ntype: str,
                     payload: dict | None = None, created_at: str | None = None) -> dict:
    """
    建一条 in-app 通知。字段：recipient / type / unread / read_at / acked_at / payload

    ★ `read_at` 与 `acked_at` **都初始为 None，且必须是存在的键** ——
      「没读过」与「没记过」长得一样，所以要用两个字段区分：
        read_at  打开过这条通知
        acked_at 明确确认过（点过「我知道了」）
    """
    if ntype not in TYPES:
        raise NotificationError("E_TYPE", f"通知类型 {ntype!r} 不在 {sorted(TYPES)}")
    if not isinstance(recipient, str) or not recipient.strip():
        raise NotificationError("E_RECIPIENT", "recipient 必须是非空字符串")
    return {
        "notification_id": notification_id,
        "recipient": recipient,
        "type": ntype,
        "unread": True,
        "read_at": None,
        "acked_at": None,
        "payload": dict(payload or {}),
        "created_at": created_at,
    }


def channel_for(ntype: str) -> str:
    """
    这条通知该走哪。

    返回 "inbox" 或 "feishu"。
    ★ 这是**唯一一处**决定通道的地方 —— 与 send_gateway 的形态决策同一个纪律。
    """
    if ntype in INBOX_ONLY:
        return "inbox"
    if ntype in FEISHU_TYPES:
        return "feishu"
    raise NotificationError("E_TYPE", f"未知通知类型 {ntype!r}")


def dispatch(ntype: str, *, feishu_sender=None) -> dict:
    """
    派发一条通知。**inbox 类型永远不会碰到 feishu_sender。**

    返回 {"channel": "inbox"} 或 {"channel": "feishu", "sent": ...}

    ★ `feishu_sender` 对 inbox 类型是**根本不会被调用**的 —— 不是「调用了但忽略结果」。
      这个区别由 verify 的 2a/2b 断言（sender 调用计数必须为 0）守住。
    """
    ch = channel_for(ntype)
    if ch == "inbox":
        return {"channel": "inbox"}
    if feishu_sender is None:
        raise NotificationError("E_NO_SENDER", f"{ntype} 需要飞书发送器，但没有传入")
    return {"channel": "feishu", "sent": feishu_sender()}


# ═══════════════════ ② 文案约束 ═══════════════════

def check_wording(text: str) -> None:
    """
    通知文案不许声称「已通知到人」。

    ★ 为什么这条是硬约束：那句话一旦出现在界面上，
      读的人会据此认为责任人已经知道、不必再催 —— 而系统根本不知道。
    """
    s = str(text)
    hits = [w for w in FORBIDDEN_CLAIMS if w in s]
    if hits:
        raise NotificationError(
            "E_WORDING",
            f"文案里出现 {hits} —— 只允许说「已投递 / 未读 / 已读」，"
            f"不得声称「已通知到人」（系统只能证明投递与阅读，不能证明知悉与处理）")


def safe_wording(delivered: int, unread: int, read: int, acked: int = 0) -> str:
    """生成合规文案。**只陈述四个可核事实。**"""
    parts = [f"已投递 {delivered} 条", f"未读 {unread} 条", f"已读 {read} 条"]
    if acked:
        parts.append(f"已确认 {acked} 条")
    text = "，".join(parts)
    check_wording(text)   # 自证：生成器自己的输出也要过这道闸
    return text


# ═══════════════════ ③ 去重账本（持久化）═══════════════════

class DedupLedger:
    """
    持久化去重账本。两种键各管一件事：

      每日提醒 —— `daily` 集合，键 = `task_id|北京日期`
      事件通知 —— `events` 集合，键 = `event_id`

    ★ 读不出文件时 `untested=True`：调用方必须据此**不发**，而不是当成「空账本」重发。
    """

    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path is not None else None
        self._daily: set[str] = set()
        self._events: set[str] = set()
        self.untested = False
        self.untested_reason = ""
        if self.path is not None and self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.untested = True
            self.untested_reason = f"去重账本读不出：{type(e).__name__}: {e}"
            return
        if not isinstance(d, dict):
            self.untested = True
            self.untested_reason = "去重账本不是对象"
            return
        self._daily = set(d.get("daily") or [])
        self._events = set(d.get("events") or [])

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"daily": sorted(self._daily),
                                   "events": sorted(self._events)},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    # ── 每日提醒 ──
    def daily_key(self, task_id: str, ts: datetime | float | None = None) -> str:
        return f"{task_id}|{bj_date(ts)}"

    def claim_daily(self, task_id: str, *, ts: datetime | float | None = None) -> dict:
        """
        申请「今天发一次」。返回 {"send": bool, "untested": bool, "reason": str}

        ★ untested 时 **send=False** —— 读不出账本就不发。
          宁可少发一条，不可连发三条；而且要把未测报出去。
        """
        if self.untested:
            return {"send": False, "untested": True, "reason": self.untested_reason}
        k = self.daily_key(task_id, ts)
        if k in self._daily:
            return {"send": False, "untested": False, "reason": f"今日已提醒（{k}）"}
        self._daily.add(k)
        self._save()
        return {"send": True, "untested": False, "reason": ""}

    # ── 状态变化 ──
    def claim_event(self, event_id: str) -> dict:
        """申请「这条事件发一次」。同一 event_id 只发一次。"""
        if self.untested:
            return {"send": False, "untested": True, "reason": self.untested_reason}
        if event_id in self._events:
            return {"send": False, "untested": False, "reason": f"事件已通知（{event_id}）"}
        self._events.add(event_id)
        self._save()
        return {"send": True, "untested": False, "reason": ""}

    def snapshot(self) -> dict:
        return {"daily": sorted(self._daily), "events": sorted(self._events),
                "untested": self.untested}


# ═══════════════════ ④ 下线任务提醒 ═══════════════════

def remind_takedown_task(*, task_id: str, state: str, event_id: str | None,
                         ledger: DedupLedger, sender,
                         ts: datetime | float | None = None) -> dict:
    """
    下线任务提醒。两条独立通道：

      每日一次（不论状态是否变）—— 键 = task_id + 北京日期
      状态变化时立即 —— 键 = event_id

    ★ 两种键**分开判**：同一天既发过每日提醒、又发生了状态变化，
      两条通知都要发。合并去重会吞掉状态变化。
    """
    out = {"daily": False, "event": False, "untested": False}
    # ★ 两个键都返回**显式布尔**，不用 None 表示「没发」——
    #   None 与 False 在三元判断里同真同假，但读日志的人分不清
    #   「今天不该发」和「今天该发但没发成」。

    d = ledger.claim_daily(task_id, ts=ts)
    out["untested"] = out["untested"] or d["untested"]
    out["daily_reason"] = d.get("reason", "")
    if d["send"]:
        sender(task_id, "daily")
        out["daily"] = True

    if event_id:
        e = ledger.claim_event(event_id)
        out["untested"] = out["untested"] or e["untested"]
        out["event_reason"] = e.get("reason", "")
        if e["send"]:
            sender(task_id, "event")
            out["event"] = True

    return out


# ═══════════════════ ⑤ inbox 视图 ═══════════════════

def inbox_view(notifications: Iterable[dict], *, recipient: str) -> dict:
    """某个人的 inbox 摘要。**只陈述计数，不做「他知道了」的推断。**"""
    mine = [n for n in notifications if n.get("recipient") == recipient]
    unread = [n for n in mine if n.get("unread")]
    read = [n for n in mine if n.get("read_at")]
    acked = [n for n in mine if n.get("acked_at")]
    return {
        "total": len(mine),
        "unread": len(unread),
        "read": len(read),
        "acked": len(acked),
        "notification_ids": [n.get("notification_id") for n in mine],
    }


def mark_read(n: dict, at: str) -> dict:
    """标已读。**未 ack 与已 ack 是两件事，不许合并。**"""
    import copy
    x = copy.deepcopy(n)
    x["unread"] = False
    x["read_at"] = at
    return x


def mark_acked(n: dict, at: str) -> dict:
    """标确认。**必须同时是已读** —— 没读就确认是矛盾的。"""
    import copy
    x = copy.deepcopy(n)
    if x.get("read_at") is None:
        raise NotificationError("E_ACK_WITHOUT_READ", "未读的通知不能确认（先 read 再 ack）")
    x["acked_at"] = at
    x["unread"] = False
    return x


# ═══════════════════ ⑥ 事件出口（唯一的一处）═══════════════════
#
# ★ 这一节存在的理由，是「通知散落在各处」这个失败模式。
#
#   动作（claim 超时释放、复核提交、签发、下线任务流转）分散在三个模块里，
#   如果每个动作自己拼通知对象、自己决定类型、自己去重，就会出现：
#     · 同一件事在 A 处叫 invalidation、在 B 处叫 auto_rereview；
#     · A 处去重了、B 处没有，于是重启后重复通知；
#     · 新加一个动作时忘了通知，而没有任何东西会红。
#
#   所以：**动作只报告「发生了什么」，由这里决定「通知什么、发给谁、发几次」。**

# 动作 → 通知类型。**纯映射，不查任何状态**，所以可以被直接断言。
# 不在表里的动作 = 不该产生通知（不是「忘了」）。
EVENT_TYPE = {
    "lease_released": "lease_released",
    "formal_submit": "formal_submit",
    "release_signed": "release_signed",
    "release_revoked": "release_revoked",
    "takedown_created": "takedown",
    "takedown_completed": "takedown",
    "takedown_failed": "takedown",
}


def notification_for(kind: str) -> dict:
    """
    动作 → 通知类型 + 通道。**纯函数，可被断言，不碰任何状态。**

    ★ 为什么单独拆出来：§2.4.7 的教训 —— 判据盖不住的那一跳，就是事故所在的那一跳。
      映射写在 `emit()` 里面，就只能靠「跑一次动作看产生了什么」来验，
      那验不了「表里每一条都映射正确」。
    """
    ntype = EVENT_TYPE.get(kind)
    if ntype is None:
        raise NotificationError(
            "E_EVENT", f"动作 {kind!r} 没有对应的通知类型（不在 EVENT_TYPE 表里）")
    return {"type": ntype, "channel": channel_for(ntype)}


class NotificationOutbox:
    """
    **通知的唯一出口。** 动作发生 → 调用 `emit()` → 记录产生或明确拒绝。

    三件事在这里一次做掉，调用点不再重复：

      ① 类型映射（`notification_for`）
      ② 去重（复用 `DedupLedger` 的 `claim_event`，键 = `event_id`）
      ③ 落记录（内存列表；`path` 给了就一并持久化）

    ★ `sender` 默认是 `None` —— **阶段一不真发飞书**。
      只有 `takedown` 类型在给了 sender 时才会调用它；inbox 类型永远不会。
      （这条由 `dispatch()` 保证，不是本类自己再实现一遍。）

    ★ `resolve_recipients` 解析不出人时返回空列表 + `untested=True`。
      **不许把「我不知道该发给谁」静默成「没有人需要知道」。**
      两者的区别只有在这里记录才看得出来 —— 都没发出时，日志一模一样。
    """

    def __init__(self, *, dedup=None, sender=None, resolve_recipients=None,
                 record_path=None):
        self.dedup = dedup if dedup is not None else DedupLedger()
        self.sender = sender
        self.resolve = resolve_recipients or default_recipients
        self.record_path = Path(record_path) if record_path else None
        self.records: list[dict] = []
        self.untested = False
        self.untested_reason = ""
        self._seq = 0

    # ── 唯一入口 ──
    def emit(self, *, event_id: str, kind: str, subject: dict | None = None,
             now=None, **payload) -> dict:
        """
        产出一次通知。返回：

          {"emitted": [...], "duplicate": bool, "untested": bool, "reason": str}

        ★ `event_id` 是去重键，**必须由动作方给出且稳定** ——
          拿 `time.time()` 或随机串当键，去重就是假的。
        """
        out = {"emitted": [], "duplicate": False,
               "untested": False, "reason": ""}

        # ① 类型映射：不认识的动作直接抛，不许静默跳过
        spec = notification_for(kind)

        # ② 去重
        claim = self.dedup.claim_event(event_id)
        if claim.get("untested"):
            out["untested"] = True
            out["reason"] = claim.get("reason", "")
            self.untested = True
            self.untested_reason = out["reason"]
            return out
        if not claim.get("send"):
            out["duplicate"] = True
            out["reason"] = claim.get("reason", "")
            return out

        # ③ 收件人
        recipients = list(self.resolve(kind, subject or {}) or [])
        if not recipients:
            # ★ 事件已经认领（去重账本里记下了），但没发出去。
            #   这是**未测**，不是「不需要发」。记账后返回，让调用方上报。
            out["untested"] = True
            out["reason"] = f"{kind}: 解析不出收件人（不是「没人需要知道」）"
            self.untested = True
            self.untested_reason = out["reason"]
            return out

        # ④ 建记录
        for recipient in recipients:
            self._seq += 1
            n = new_notification(
                notification_id=f"ntf-{event_id}-{self._seq}",
                recipient=recipient,
                ntype=spec["type"],
                payload={"event_id": event_id, "kind": kind, **payload},
                created_at=_iso(now),
            )
            self.records.append(n)
            out["emitted"].append(n)

        # ⑤ 通道：只有飞书类型会碰 sender，且 sender 为 None 时不当作错误
        if spec["channel"] == "feishu" and self.sender is not None:
            out["sent"] = self.sender(event_id, kind)

        self._save()
        return out

    # ── 持久化（可选）──
    def _save(self) -> None:
        if self.record_path is None:
            return
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.record_path.with_suffix(self.record_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.records, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.record_path)

    def snapshot(self) -> dict:
        """读回现场。**未测要能报出来**，不能静默。"""
        return {"count": len(self.records),
                "untested": self.untested,
                "untested_reason": self.untested_reason,
                "records": list(self.records)}


def _iso(ts) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, BJT).isoformat()
    return ts.isoformat()


# ── 默认收件人解析 ─────────────────────────────────────
#
# ★ 只处理「手里真的有」的那几个。解析不出来的**返回空** ——
#   由 emit() 记成未测。不要在这里猜一个默认收件人：
#   猜错比空着坏，因为空着会被报出来，猜错不会。
def default_recipients(kind: str, subject: dict) -> list[str]:
    """
    默认的收件人解析。**宁可返回空，不许猜。**

    `subject` 是动作方给出的事实（案件/任务对象），不是查来的。
    """
    subj = subject or {}

    if kind == "lease_released":
        # 超时释放：通知**被释放的原领取人**。subject 必须带 released_assignee。
        who = subj.get("released_assignee")
        return [who] if isinstance(who, str) and who else []

    if kind == "formal_submit":
        # 复核提交：通知最终复核人。subject 必须带 final_reviewer_id。
        who = subj.get("final_reviewer_id")
        return [who] if isinstance(who, str) and who else []

    if kind in ("release_signed", "release_revoked"):
        # 签发/撤回：通知提交人（他知道结果）。
        who = subj.get("submitter_id")
        return [who] if isinstance(who, str) and who else []

    if kind.startswith("takedown_"):
        # 下线任务：负责人 + 复核人，去重保序。
        out = []
        for k in ("assignee", "reviewers"):
            v = subj.get(k)
            if isinstance(v, str) and v:
                out.append(v)
            elif isinstance(v, (list, tuple)):
                out.extend(x for x in v if isinstance(x, str) and x)
        return list(dict.fromkeys(out))

    return []
