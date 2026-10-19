#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/case_watch.py —— 转出后的超时升级（C-51 / L3-2 / STOP-6）

**它是什么**：一个**纯扫描器**。给一批案件和一个时刻，返回「哪些已经到期该升级」。
**它不是什么**：它不调度自己。没有任何 while / sleep / 定时器 —— 谁按周期调它，
是集成方的事（见末尾「为什么不自己定时」）。

--------------------------------------------------------------------------
★ 三条本文件刻意做死的事
--------------------------------------------------------------------------

**一、`weekends_only` 必须被说出来，不许被读成「已考虑法定假日」**

    默认**不带任何节假日数据**。空的假日历不会报错，只会让「到期」比真实情况
    早那么几天 —— 而这恰好是**偏安全的方向**（早升级比晚升级好）。

    但「安全」不等于「可以不说」。所以每次扫描结果里都带：

        "calendar_coverage": "weekends_only"    # 或者 "configured"
        "holidays_configured": false

    ★ 这与 `tools/verify_pending.py` 里那条决定一致（「本仓没有节假日表，
      也不打算编一张」）。不内置真实节假日，是因为**凭记忆写一份没人核过的
      放假安排**，一旦错了不红，而且会把「该升级」推到假期之后 ——
      那正是 §2.4.1 记过的形状：数据看着像真的，错了没人知道。

**二、算不算到期，三态而不是两态**

    每条案件只有三种结果：

        due        —— 确定到期，该升级
        not_due    —— 确定没到期
        untested   —— **判不了**（没有 due_at 也没有 transferred_at，
                      或时间读不出）

    ★ `untested` 不许落进 `not_due`。一条永远判不出来的案件，
      如果被记成「还没到期」，它就会**永远不升级**，而看板上一片平静。
      这与 §2.4.2 的「L3 未测退 2」同一个口径。

**三、去重键用**到期时刻**，不是**扫描时刻**

        event_id = "case:<case_id>:due:<due_at ISO>"

    ★ 扫描是周期性的。拿扫描时刻当键，每次扫描都会是一条新事件 ——
      等于没去重，而且群里会每隔几分钟收到同一条提醒。
      用 due_at 当键：同一次到期只升级一次；到期时刻**变了**
      （重算、改阈值）才是新事件，那是应该再通知一次的。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# 北京时间 = UTC+8（无夏令时）。本文件的所有「日」都按它算。
BJT = timezone(timedelta(hours=8))

# 默认阈值：D-039「统一 2 个工作日」。
DEFAULT_THRESHOLD_DAYS = 2

# 默认升级目标（routing-v1.json 里 `escalation` 的取值）。
DEFAULT_ESCALATION_ROLE = "项目统筹"

# 只有这个放行状态是「还开着」的。其余都是终态，不升级。
OPEN_RELEASE_STATUS = "待放行"

# 判不了的案件也可能挂在别的状态上；这些是明确的终态。
TERMINAL_STATUS = frozenset({"closed", "cancelled", "withdrawn"})


class CaseWatchError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# ═══════════════════════ ① 工作日历 ═══════════════════════

class WorkCalendar:
    """
    工作日历。**默认空表 —— 只跳周六日。**

    两个集合都可配，语义不同，别混：

      `holidays`       —— 法定假日（本该上班的日子放假）
      `extra_workdays` —— 调休上班（本该休息的周末上班）

    ★ 查序：**先看 `extra_workdays`，再看 `holidays`，最后看星期几。**
      顺序反了的话，一个既标成假日又标成调休的日期会判成放假 ——
      现实中不会同时标，但把顺序写死比依赖「不会同时标」稳。
    """

    def __init__(self, holidays: Iterable[str] = (), extra_workdays: Iterable[str] = ()):
        self.holidays = frozenset(str(h) for h in (holidays or ()))
        self.extra_workdays = frozenset(str(h) for h in (extra_workdays or ()))

    # ── 单个日期 ──
    def is_workday(self, d: date) -> bool:
        key = d.isoformat()
        if key in self.extra_workdays:
            return True
        if key in self.holidays:
            return False
        return d.weekday() < 5

    # ── 口径自述 ──
    @property
    def holidays_configured(self) -> bool:
        return bool(self.holidays)

    def coverage(self) -> str:
        """
        这张日历到底覆盖了什么。**空表必须说 weekends_only。**

        ★ 这个词是给下游看的：`weekends_only` 意味着
          「我不知道你们公司哪天放假，所以只跳周末」。
          把它写成 `configured` 或干脆不写，读的人会以为已经考虑过法定假日。
        """
        return "configured" if self.holidays_configured else "weekends_only"

    def describe(self) -> dict:
        return {"calendar_coverage": self.coverage(),
                "holidays_configured": self.holidays_configured,
                "holidays_count": len(self.holidays),
                "extra_workdays_count": len(self.extra_workdays)}

    # ── 加减工作日 ──
    def add_business_days(self, dt: datetime, n: int) -> datetime:
        """`dt` 之后第 n 个工作日（同一时刻）。n<=0 原样返回。"""
        if n <= 0:
            return dt
        d, added = dt, 0
        while added < n:
            d = d + timedelta(days=1)
            if self.is_workday(d.date()):
                added += 1
        return d

    def business_days_between(self, d0: date, d1: date) -> int:
        """`d0` **之后**到 `d1`（含）的工作日数。`d1 <= d0` 回 0。纯函数。"""
        if d1 <= d0:
            return 0
        n, d = 0, d0
        while d < d1:
            d += timedelta(days=1)
            if self.is_workday(d):
                n += 1
        return n


DEFAULT_CALENDAR = WorkCalendar()


# ═══════════════════════ ② 时间解析 ═══════════════════════

def parse_ts(value) -> datetime | None:
    """
    把各种形状的时间读成带时区的 datetime。**读不出返回 None，不抛。**

    ★ 返回 None 是让调用方把它记成 untested 的 —— 「读不出时间」
      必须与「还没到期」长得不一样。这里抛异常会让整轮扫描挂掉，
      一条坏数据拖死全部案件。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, BJT)
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def threshold_days_from(text, default: int = DEFAULT_THRESHOLD_DAYS) -> int:
    """把 `"2 个工作日"` 这类文本读成天数。读不出用默认值。"""
    import re
    m = re.search(r"(\d+)\s*个工作日", str(text or ""))
    if m:
        return int(m.group(1))
    return default


# ═══════════════════════ ③ 升级台账 ═══════════════════════

class EscalationLedger:
    """
    升级事件台账。**可按案件号查** —— 这是验收 51 明写的要求。

    ★ 可持久化到 JSON；读不出时 `untested=True`，调用方据此上报，
      不许当成「空台账、没升级过」重来一遍。
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.events: list[dict] = []
        self.untested = False
        self.untested_reason = ""
        if self.path is not None and self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.untested = True
            self.untested_reason = f"升级台账读不出：{type(e).__name__}: {e}"
            return
        if not isinstance(d, list):
            self.untested = True
            self.untested_reason = "升级台账不是数组"
            return
        self.events = [e for e in d if isinstance(e, dict)]

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.events, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def record(self, event: dict) -> dict:
        self.events.append(dict(event))
        self._save()
        return event

    def by_case(self, case_id: str) -> list[dict]:
        return [e for e in self.events if e.get("case_id") == case_id]

    def has(self, event_id: str) -> bool:
        return any(e.get("event_id") == event_id for e in self.events)


# ═══════════════════════ ④ 单条判定 ═══════════════════════



def _due_at(case: dict, calendar: WorkCalendar, threshold_days: int):
    """
    算出这一条的到期时刻。返回 `(datetime | None, source_str)`。

    ★ 单独拆出来是为了它能被**替换成「恒返回 None」的坏实现**，
      从而证明「判不出 → 落未测」这条守卫真的在起作用。
      埋在 `_decide()` 里面的话，那条反向对照只能靠改源码，
      而改源码验出来的东西跟验证器里跑的代码不是同一份。
    """
    disp = case.get("disposition") if isinstance(case.get("disposition"), dict) else {}

    # ★ 「字段没有」与「字段有但读不出」必须分开 —— 这条是 3d 抓出来的真 bug：
    #
    #   原先写的是 `case.get("due_at") or disp.get("due_at")`，然后 if due is None
    #   就回落到 transferred_at。于是 due_at = "不是时间" 这种**坏数据**
    #   会被静默忽略，改用 transferred_at 算出一个**看起来正常**的到期时刻，
    #   最后报 not_due —— 一个字段坏了的案件，结论与字段完好时一模一样。
    #
    #   现在的判断：
    #     字段存在但读不出 → 直接 untested（坏数据必须浮出来，不许被替代值盖住）
    #     字段不存在       → 回落到 transferred_at + 阈值（这是正常路径）
    raw_due = case.get("due_at")
    if raw_due is None:
        raw_due = disp.get("due_at")
    if raw_due is not None:
        due = parse_ts(raw_due)
        if due is None:
            return None, "due_at_unparseable"
        return due, "due_at"

    raw_start = case.get("transferred_at")
    if raw_start is None:
        raw_start = disp.get("transferred_at")
    if raw_start is not None:
        start = parse_ts(raw_start)
        if start is None:
            return None, "transferred_at_unparseable"
        return (calendar.add_business_days(start, threshold_days),
                "computed_from_transferred_at+%d工作日" % threshold_days)

    return None, "none"


def _decide(case: dict, now: datetime, calendar: WorkCalendar,
            threshold_days: int) -> dict:
    """
    一条案件判到哪种状态。纯函数，不碰台账、不发通知。

    返回 {"verdict": due|not_due|skipped|untested, ...}
    """
    cid = case.get("case_id")
    if not isinstance(cid, str) or not cid:
        return {"verdict": "untested", "reason": "缺 case_id",
                "case_id": case.get("case_id")}

    # ① 终态不升级
    status = case.get("status")
    if isinstance(status, str) and status in TERMINAL_STATUS:
        return {"verdict": "skipped", "case_id": cid,
                "reason": f"status={status}（终态）"}
    release_status = case.get("release_status")
    if isinstance(release_status, str) and release_status and \
            release_status != OPEN_RELEASE_STATUS:
        return {"verdict": "skipped", "case_id": cid,
                "reason": f"release_status={release_status}（已离开待放行）"}

    # ② 到期时刻：先用 disposition 里现成的 due_at，没有再按阈值算
    due, due_source = _due_at(case, calendar, threshold_days)
    if due is None:
        # ★ 判不了就是判不了。不许返回 not_due。
        return {"verdict": "untested", "case_id": cid,
                "reason": "既没有 due_at，也没有 transferred_at —— 判不出到期时刻"}

    if now < due:
        return {"verdict": "not_due", "case_id": cid, "due_at": iso_z(due),
                "due_source": due_source,
                "workdays_left": calendar.business_days_between(now.date(), due.date())}

    return {"verdict": "due", "case_id": cid, "due_at": iso_z(due),
            "due_source": due_source,
            "overdue_workdays": calendar.business_days_between(due.date(), now.date())}


def _event_key(case_id: str, due_at_iso: str) -> str:
    """
    升级事件的去重键。**案件 + 到期时刻。**

    ★ 单独拆成一个函数，是为了它能被替换成坏实现来证明「去重真的靠它」——
      键直接拼在 `scan()` 里的话，判据只能靠「扫两次看结果」，
      而那样验不出「换个键会怎样」。
      （§2.4.7：判据盖不住的那一跳，就是事故所在的那一跳。）
    """
    return "case:%s:due:%s" % (case_id, due_at_iso)


# ═══════════════════════ ⑤ 扫描 ═══════════════════════

def scan(cases: Iterable[dict], now, *, calendar: WorkCalendar | None = None,
         threshold_days: int = DEFAULT_THRESHOLD_DAYS,
         escalation_role: str = DEFAULT_ESCALATION_ROLE,
         escalation_recipients=None,
         ledger: EscalationLedger | None = None,
         outbox=None) -> dict:
    """
    扫描一批案件，把到期的升级掉。

    **纯函数式入口**：不自己定时、不读全局状态。`now` 必须显式给。

    参数
    ----
    `cases`                 案件迭代器
    `now`                   当前时刻（datetime / 时间戳 / ISO 串）
    `calendar`              工作日历，默认只跳周末
    `threshold_days`        默认 2 个工作日（D-039）
    `escalation_role`       升级到哪个角色（默认「项目统筹」）
    `escalation_recipients` 具体接收人：list[str] 或 callable(role, case)->list[str]
    `ledger`                升级台账（`EscalationLedger`）
    `outbox`                `notifications.NotificationOutbox`。
                            **None = dry-run**：只报哪些到期，不发通知、不写台账、
                            也不需要收件人。试跑绝不许产生副作用（§2.4.4）。

    返回
    ----
    {
      "due": [...], "not_due": [...], "skipped": [...], "untested_items": [...],
      "already_escalated": [...],
      "calendar_coverage": "weekends_only"|"configured",
      "holidays_configured": bool,
      "untested": bool, "untested_reasons": [...]
    }

    ★ 外层那个 `untested` 是**汇总标志**：只要有一条判不了，它就是 True。
      调用方据此报「未测」—— `due` 为空**不代表一切正常**。
    """
    cal = calendar or DEFAULT_CALENDAR
    led = ledger if ledger is not None else EscalationLedger()
    now_dt = parse_ts(now)
    if now_dt is None:
        raise CaseWatchError("E_NOW", f"now 读不出时间：{now!r}")

    out = {"due": [], "not_due": [], "skipped": [], "untested_items": [],
           "already_escalated": [],
           "calendar_coverage": cal.coverage(),
           "holidays_configured": cal.holidays_configured,
           "untested": False, "untested_reasons": []}

    if led.untested:
        # ★ 台账读不出 = 不知道升级过没有。整轮记未测，不许照常升级后重复打扰。
        out["untested"] = True
        out["untested_reasons"].append(led.untested_reason)
        return out

    for case in cases:
        if not isinstance(case, dict):
            out["untested_items"].append({"case_id": None, "reason": "案件不是对象"})
            out["untested"] = True
            continue

        d = _decide(case, now_dt, cal, threshold_days)

        if d["verdict"] == "skipped":
            out["skipped"].append(d)
            continue
        if d["verdict"] == "not_due":
            out["not_due"].append(d)
            continue
        if d["verdict"] == "untested":
            out["untested_items"].append(d)
            out["untested"] = True
            out["untested_reasons"].append(d.get("reason", ""))
            continue

        # ── 到期 ──
        #
        # ★ 两种模式必须分开，否则「看一眼谁会到期」会被当成一次升级动作：
        #
        #    outbox 给了   → 真升级：解析收件人 → 发通知 → 写台账
        #    outbox 是 None → **dry-run**：只报「哪些到期」，不发、不写、
        #                     也不需要收件人（试跑时解析不出人不是错误）
        #
        #   把两者混成一个分支，试跑就会写台账 → 真到期时反而被去重挡住不发。
        cid = d["case_id"]
        role = case.get("escalation") or escalation_role

        if outbox is None:
            out["due"].append(dict(d, event_id=_event_key(cid, d["due_at"]),
                                   escalation_role=role, recipients=[],
                                   dry_run=True))
            continue

        who = _resolve_recipients(escalation_recipients, role, case)
        if not who:
            out["untested_items"].append({
                "case_id": cid, "due_at": d["due_at"],
                "reason": f"升级目标「{role}」解析不出具体接收人 —— 不是「没人需要知道」"})
            out["untested"] = True
            out["untested_reasons"].append(out["untested_items"][-1]["reason"])
            continue

        event_id = _event_key(cid, d["due_at"])

        subject = {
            "case_id": cid, "due_at": d["due_at"],
            "escalation_role": role,
            "escalation_recipients": list(who),
            "overdue_workdays": d.get("overdue_workdays"),
            "calendar_coverage": cal.coverage(),
            "holidays_configured": cal.holidays_configured,
        }

        # ── 发通知（走唯一出口）──
        #
        # ★ `subject` 只喂给收件人解析器，**不会**落进通知记录。
        #   所以要给读通知的人看到的东西（哪一条案件、什么口径算出的到期），
        #   必须作为 payload 显式再传一遍 —— 这不是重复，
        #   而是「解析用的输入」与「留给人看的记录」两件事。
        #   6d/6e/6f 三条断言就是钉这一点的：口径没进 payload，读的人就不知道
        #   这次升级是按什么日历算的。
        res = outbox.emit(event_id=event_id, kind="case_overdue",
                          subject=subject, now=now_dt,
                          case_id=cid, due_at=d["due_at"],
                          due_source=d.get("due_source"),
                          overdue_workdays=d.get("overdue_workdays"),
                          escalation_role=role,
                          calendar_coverage=cal.coverage(),
                          holidays_configured=cal.holidays_configured)
        if res.get("untested"):
            out["untested_items"].append({"case_id": cid, "due_at": d["due_at"],
                                          "reason": res.get("reason", "")})
            out["untested"] = True
            out["untested_reasons"].append(res.get("reason", ""))
            continue
        if res.get("duplicate"):
            out["already_escalated"].append({"case_id": cid, "event_id": event_id,
                                             "reason": res.get("reason", "")})
            continue

        # ── 写台账（通知之后；通知失败就不记「已升级」）──
        event = {
            "event_id": event_id, "case_id": cid, "kind": "case_overdue",
            "at": iso_z(now_dt), "due_at": d["due_at"],
            "due_source": d.get("due_source"),
            "overdue_workdays": d.get("overdue_workdays"),
            "escalation_role": role, "recipients": list(who),
            "calendar_coverage": cal.coverage(),
            "holidays_configured": cal.holidays_configured,
        }
        led.record(event)
        out["due"].append(dict(d, event_id=event_id, recipients=list(who),
                               escalation_role=role))

    return out


def _resolve_recipients(spec, role: str, case: dict) -> list[str]:
    """
    收件人解析。**解析不出返回空列表** —— 由调用方记成未测。

    优先级：可调用 → 显式列表 → 案件自带 → 空。
    空不是「没人需要知道」，是「我不知道该发给谁」。
    """
    if callable(spec):
        try:
            got = spec(role, case)
        except Exception:  # noqa: BLE001
            return []
        return [x for x in (got or []) if isinstance(x, str) and x]
    if isinstance(spec, (list, tuple)):
        return [x for x in spec if isinstance(x, str) and x]
    if isinstance(spec, str) and spec:
        return [spec]
    own = case.get("escalation_recipients")
    if isinstance(own, (list, tuple)):
        return [x for x in own if isinstance(x, str) and x]
    if isinstance(own, str) and own:
        return [own]
    return []
