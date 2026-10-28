#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核台账纯 reducer：命令 + 旧状态 → 新状态 + 事件 + 返回值。

不读写文件、不持有锁、不发通知。生产权威写入由 BusinessEventStore 统一提交；
现有 ReviewsLedger 继续供开发装配和旧验证器使用。
"""
from __future__ import annotations

import copy
import calendar
import hashlib
import json
import time

from base.reviews_ledger import (
    LEASE_SECONDS,
    LedgerConflict,
    LedgerNotFound,
    LedgerValidation,
)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(now):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(now)))


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise LedgerValidation("bad_" + name, "%s 必须是非空字符串" % name)
    return value.strip()


def initial_state(case_id):
    aid = _nonempty(case_id, "case_id")
    # T-313a：通知聚合的初始形状。★ 必须在 initial_state 里分支 ——
    # BusinessEventStore.state() 对没见过的 aggregate_id 直接调
    # initial_state(aggregate_id)（business_event_store.py），只在命令分支里
    # 兜底的话，读一个空收件箱就会炸。case_id 槽仍放聚合 ID：
    # _event / apply_event / 投影的 aggregate_mismatch 校验都靠它当身份。
    if aid.startswith(NOTIFICATION_AGGREGATE_PREFIX):
        tenant, recipient = _notification_aggregate_parts(aid)
        return {
            "case_id": aid,
            "version": 0,
            "tenant": tenant,
            "recipient": recipient,
            "items": [],
            "archived_count": 0,
        }
    return {
        "case_id": aid,
        "status": "unassigned",
        "assignee": None,
        "version": 0,
        "claimed_at": None,
        "last_activity": None,
        "lease_expires": None,
        "released_at": None,
        "released_draft_id": None,
        "draft_seq": 0,
        "primary_draft_id": None,
        "drafts": [],
        "fragment_references": [],
        "formal_reviews": [],
        # 内容入库后由 ingest_submission 写入；authority 事件是完整状态快照，
        # 投影重建就是重放这些快照，所以内容随 state 走，不另设第二个权威。
        "submission_id": None,
        "submission_hash": None,
        # T-312a: 强制下线任务。与案件同一个 aggregate。
        "takedown_seq": 0,
        "takedown_tasks": [],
        # T-311a: 申诉。与案件同一个 aggregate（一条申诉天生属于一个案件）。
        # appeal_seq 落在 state 里 —— 否则重启后申诉号会撞（见 _appeal_id）。
        "appeal_seq": 0,
        "appeals": [],
        # T-314a: 名单治理聚合（aggregate_id = "grants:<tenant>"）。
        # 与案件同住一个 reducer，是因为 BusinessEventStore.execute()
        # 一次只提交一个 aggregate，而 grant 的状态迁移与案件一样是纯函数。
        "grant_seq": 0,
        "grants": [],
        "content": None,
        "ir": None,
        # T-310a：签发绑定的判定时点快照（T-310 施工单 §二 前置 A/B）。
        # kb_snapshot_hash = 判定所用 KB 快照 id 的 sha256（2026-10-25 D1 裁定）；
        # conflict_table_version 与 ir.control_points_version 是同一个量（§2.4.8），
        # ingest 时断言两者一致。取不到一律拒建案 —— 不许补默认值让签发「先跑通」。
        "kb_snapshot_hash": None,
        "conflict_table_version": None,
        "media_fingerprints": {},
        # T-433：L1 多模态**观察**（不是 finding）。
        #
        # ★ 为什么单独一个格子、不进 ir.findings：
        #   finding 的准入是三要素合取 —— control_code / authority_ref / location
        #   （base/finding_store.py:69）。多模态能给 location，给不出前两项
        #   （它们是知识库产物）。把观察塞进 finding 表，后果是复核时**无法申诉**：
        #   没有 control_code 就无法对照规则。
        #
        # ★ 为什么仍然进权威（随 state 走）：观察是「机器看过什么」的证据。
        #   放在 state 之外就等于放了一个没有重放能力的旁路 —— 重启后它消失，
        #   而报告里已经写过它。
        #
        # 每条含 {task, model, model_version, ts, bbox, statement, confidence,
        #        egress_status, status, created_at}；`status` 保留 untested/error
        # 的条目，好让「模型没看成」与「模型看了没问题」在数据上分开。
        "multimodal_observations": [],

        # T-310b：签发状态容器；active_job / successor 键为 T-317 重审预留。
        "release": None,
        # T-316b: 判定时冻结的报告渲染输入（与 ir 并列，不是 ir 的一部分）。
        # 为什么单独存而不在结案时重算：report_render 的 evidence/unassessed
        # 在判定时是空数组、结案后才有内容；重算会让「报告的 IR」与「报告的
        # 证据」来自两个时刻（AGENTS.md §2.4.8 同一个量两个口径）。
        "report_snapshot": None,
        # T-317b: 已发布报告的**追加列表**（重审产新报告时旧条目原样保留）；
        # `report` 键保留为「最新一份」兼容读侧。
        "reports": [],
        # T-316d: 已发布的报告。**由 `report_publish` 命令写入，不由 reducer 计算
        # report_id** —— 内容寻址需要渲染文本，reducer 拿不到（见 T-316 施工单 §五 第 2 条）。
        "report": None,
        "judgment": None,
        "tenant": None,
        "product_line": None,
        "submitter_id": None,
        "ingested_at": None,
    }


# 判定表五标签；ingest 时拒绝任何不在这五个值里的 label。
DECISION_LABELS = ("PASS", "待自决", "REVIEW", "BLOCK", "未审查")

#: T-433：一条多模态观察的状态域。
#: ★ 刻意**不含** "candidate"/"rejected" 这类 finding 用的词 ——
#:   观察不是 finding，共用一套状态名会让下游把两者混读。
#:   ok = 模型给出了观察；untested = 没测成；error = 测了但失败。
OBSERVATION_STATUSES = frozenset({"ok", "untested", "error"})


def public_case(state):
    return {
        key: copy.deepcopy(state.get(key))
        for key in (
            "case_id", "status", "assignee", "version", "claimed_at",
            "last_activity", "lease_expires", "released_at",
            "released_draft_id", "primary_draft_id",
        )
    } | ({"report": copy.deepcopy(state["report"])}
         if state.get("report") is not None else {})


def _draft(state, draft_id):
    return next((d for d in state["drafts"] if d["draft_id"] == draft_id), None)


def _require_claim(state, actor, expected_version, now):
    if state["status"] == "claimed" and state["lease_expires"] is not None:
        if float(now) > float(state["lease_expires"]):
            raise LedgerConflict("lease_expired", "领取 lease 已过期")
    if state["status"] != "claimed" or state["assignee"] != actor:
        raise LedgerConflict("not_assignee", "当前不是该案的 assignee")
    if state["version"] != expected_version:
        raise LedgerConflict(
            "version_conflict",
            "期望版本 %r，实际 %r" % (expected_version, state["version"]),
        )


def _new_draft(state, actor, now, content, *, kind, derived_from=None):
    seq = state["draft_seq"] + 1
    content_hash = _hash(content)
    draft_id = "draft-" + _hash({
        "case_id": state["case_id"], "seq": seq, "author": actor,
        "content_hash": content_hash, "kind": kind,
        "derived_from": derived_from,
    })[:16]
    draft = {
        "case_id": state["case_id"], "draft_id": draft_id,
        "snapshot_seq": seq, "snapshot_at": _iso(now),
        "content_hash": content_hash, "author": actor,
        "derived_from": derived_from, "snapshot_kind": kind,
        **copy.deepcopy(content),
    }
    if kind == "adopt":
        draft["adopted_at"] = _iso(now)
    state["draft_seq"] = seq
    state["drafts"].append(draft)
    state["primary_draft_id"] = draft_id
    return draft


def _event(command, state, actor, now, detail=None):
    return {
        "type": "review.%s" % command,
        "aggregate_type": aggregate_type_for(state.get("case_id")),
        "aggregate_id": state["case_id"],
        "version": state["version"],
        "actor": actor,
        "occurred_at": _iso(now),
        "detail": copy.deepcopy(detail or {}),
        "state": copy.deepcopy(state),
    }


TAKEDOWN_COMMANDS = frozenset({"takedown_create", "takedown_transition"})


def _takedown(state, command, actor, payload, now, detail):
    """takedown_create / takedown_transition 的纯状态迁移。

    ## 迁移表只有一份

    `takedown_transition` 一律调 `base.takedown.transition()`，
    **绝不在这里复制 `TD.TRANSITIONS`**。两份迁移表必然漂移，而漂移的后果
    是「reducer 允许、生产拒绝」或反过来 —— 两种都只有真跑一次才看得见。

    ## create 不判「该不该建」

    「已发布才建任务」在 `TD.should_create_task()`；reducer 只负责落盘。
    判断与落盘分开，才验得清是谁的错。
    """
    import base.takedown as TD

    tasks = state.setdefault("takedown_tasks", [])

    if command == "takedown_create":
        trigger = payload.get("trigger")
        if trigger not in ("revoke", "invalidated"):
            raise LedgerValidation(
                "bad_task", "trigger 必须是 revoke/invalidated，收到 %r" % (trigger,))
        platform = _nonempty(payload.get("platform"), "platform")
        assignee = _nonempty(payload.get("assignee"), "assignee")
        reviewers = payload.get("reviewers") or []
        if not isinstance(reviewers, list):
            raise LedgerValidation("bad_task", "reviewers 必须是数组")
        # 同案同 trigger 已有未完成任务 → 拒（否则会造出一条永远做不完的假待办）
        if any(t.get("trigger") == trigger
               and t.get("state") in ("pending", "in_progress")
               for t in tasks):
            raise LedgerConflict(
                "duplicate_task", "同案同 trigger 已有未完成的下线任务")

        seq = int(state.get("takedown_seq") or 0) + 1
        created_at = _iso(now)
        tid = "td-" + _hash({
            "case_id": state["case_id"], "seq": seq,
            "trigger": trigger, "created_at": created_at,
        })[:16]
        task = TD.new_task(
            task_id=tid, case_id=state["case_id"], platform=platform,
            tenant=payload.get("tenant") or state.get("tenant") or "",
            product_line=payload.get("product_line") or state.get("product_line") or "",
            created_at=created_at, assignee=assignee, reviewers=reviewers,
            trigger=trigger, reason=payload.get("reason") or trigger)
        task["version"] = 0
        tasks.append(task)
        state["takedown_seq"] = seq
        detail.update({"task_id": tid, "trigger": trigger})
        return

    tid = _nonempty(payload.get("task_id"), "task_id")
    target = next((t for t in tasks if t.get("task_id") == tid), None)
    if target is None:
        raise LedgerNotFound("task_not_found", "下线任务不存在：%s" % tid)
    to = _nonempty(payload.get("to"), "to")
    # ★ 迁移合法性交给 TD.transition（唯一迁移表）；它抛 TD.TakedownError，
    #   这里原样透出 code，不吞掉、不改写。
    try:
        new_task = TD.transition(target, to, action=payload.get("action"),
                                 at=_iso(now))
    except TD.TakedownError as exc:
        raise LedgerConflict(exc.code, exc.detail)
    new_task["version"] = int(target.get("version") or 0) + 1
    index = tasks.index(target)
    tasks[index] = new_task
    detail.update({"task_id": tid, "state": to})


REPORT_COMMANDS = frozenset({"report_publish"})


def _report(state, command, actor, payload, now, detail):
    """报告落盘回写（T-316d）。**只有一条命令。**

    ## 为什么 reducer 只接受算好的 report_id

    `report_id` 是**内容寻址**（`ReportStore._make_id`：正文 + ir_id + version +
    指纹的哈希）。reducer 里没有渲染文本，算不出来。
    两边各算一次 = 两份公式必然漂移，而漂移的表现是「重建出来的 id 与盘上文件名
    不一致」—— 那时报告文件还在，但**没有任何入口能打开它**。

    ## 前置条件：必须是已结案的案件

    未结案就发报告，等于给一个还能改判的案件发了「最终报告」。
    结案（`submit_review`）才是报告的唯一合法前驱。
    """
    if state.get("status") != "closed":
        raise LedgerConflict(
            "report_requires_closed",
            "报告只能为已结案的案件发布（当前 status=%r）" % (state.get("status"),))

    report_id = _nonempty(payload.get("report_id"), "report_id")
    # 格式校验，不是重算。`rp` + 16 位十六进制（与 ReportStore._make_id 一致）。
    if not (report_id.startswith("rp") and len(report_id) == 18
            and all(c in "0123456789abcdef" for c in report_id[2:])):
        raise LedgerValidation(
            "bad_report_id", "report_id 必须是 rp+16 位小写十六进制，收到 %r" % (report_id,))
    sha256 = _nonempty(payload.get("sha256"), "sha256")
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise LedgerValidation("bad_report", "sha256 必须是 64 位小写十六进制")
    url = _nonempty(payload.get("url"), "url")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise LedgerValidation("bad_report", "报告 url 必须是 http(s) 绝对地址")
    path = _nonempty(payload.get("path"), "path")

    existing = state.get("report")
    if isinstance(existing, dict) and existing.get("report_id") == report_id:
        # 幂等：同一条报告重放（发布成功但权威写入重试）不报错、不改字段。
        detail.update({"report_id": report_id, "replayed": True})
        return
    # T-317b：不同 id = 重审后的**新**报告 → 追加进 reports 列表，
    # `report` 键指向最新一份。旧条目原样保留（R2：旧报告不改不删）；
    # 文件侧天然共存（ReportStore 内容寻址 + index.jsonl 只追加）。
    reports = state.setdefault("reports", [])
    if isinstance(existing, dict) \
            and not any(r.get("report_id") == existing.get("report_id")
                        for r in reports):
        reports.append(copy.deepcopy(existing))

    state["report"] = {
        "report_id": report_id,
        "url": url,
        "path": path,
        "sha256": sha256,
        "source_ir_id": payload.get("source_ir_id"),
        "source_ir_version": payload.get("source_ir_version"),
        "source_ir_fingerprint": payload.get("source_ir_fingerprint"),
        "created_at": payload.get("created_at"),
        "published_at": _iso(now),
        "renderer": payload.get("renderer"),
        "published_by": actor,
    }
    if not any(r.get("report_id") == report_id for r in reports):
        reports.append(copy.deepcopy(state["report"]))
    detail.update({"report_id": report_id})


APPEAL_COMMANDS = frozenset({"appeal_open", "appeal_pause", "appeal_stale",
                             "appeal_migrate", "appeal_withdraw"})

#: 每条命令允许改写的字段。RL-12 ④ 的判据就落在这张表上。
APPEAL_WRITABLE = {
    "appeal_open": {"state", "opened_at"},
    "appeal_pause": {"state", "pause_reason", "paused_at"},
    "appeal_stale": {"state", "stale_at"},
    "appeal_migrate": {"state", "migrated_at"},
    "appeal_withdraw": {"state", "withdrawn_at", "withdraw_reason"},
}


def _appeal_id(case_id, seq, appellant, opened_at):
    """确定性申诉号。

    ★ 不用 `"appeal-%d" % seq`：那是进程内计数器，重启归零后与历史撞号
      （api/write_api.AppealStore 实测踩过）。这里把 case/seq/appellant/时刻
      一起哈希，seq 落在 state 里，跨重启连续。
    """
    return "appeal-" + _hash({
        "case_id": case_id, "seq": seq,
        "appellant": appellant, "opened_at": opened_at,
    })[:16]


def _appeal(state, command, actor, payload, now, detail):
    """appeal_* 五条命令的纯状态迁移。

    ## 边界

    - 不查案件是否存在（那是 API 层）；
    - 不查租户（reducer 拿不到 repo）；
    - 不消费任何 token。
    只做五态迁移、ID 生成、时间戳、留痕。

    ## 三条硬约束（各有断言）

    1. **只写该写的字段**（`APPEAL_WRITABLE`）。RL-12 ④ 要求「申诉记录一个字段
       都没被改写」—— pause/stale 只许动状态与时间戳，业务字段一个都不许碰。
    2. **pause/stale 不关闭**。状态只能是 paused_version_invalidated / stale，
       **不许出现 closed**。
    3. **migrate/withdraw 只能原申诉人做**。
    """
    appeals = state.setdefault("appeals", [])

    if command == "appeal_open":
        reason = _nonempty(payload.get("reason"), "reason")
        tenant = payload.get("tenant") or state.get("tenant")
        if not isinstance(tenant, str) or not tenant.strip():
            raise LedgerValidation("bad_appeal", "tenant 必填（申诉必须可被租户过滤）")
        seq = int(state.get("appeal_seq") or 0) + 1
        opened_at = _iso(now)
        aid = _appeal_id(state["case_id"], seq, actor, opened_at)
        if any(a.get("appeal_id") == aid for a in appeals):
            raise LedgerConflict("duplicate_appeal", "同一申诉已存在")
        record = {
            "appeal_id": aid,
            "case_id": state["case_id"],
            # ★ tenant 必须写进每条申诉：GET /api/v1/appeals 按它过滤，
            #   而内存版 AppealStore 从来没有这个字段（T-311 施工单 §一 第 7 条）。
            "tenant": tenant.strip(),
            "appellant": actor,
            "reason": reason,
            "state": "open",
            "opened_at": opened_at,
            "paused_at": None, "pause_reason": None,
            "stale_at": None,
            "migrated_at": None,
            "withdrawn_at": None, "withdraw_reason": None,
        }
        appeals.append(record)
        state["appeal_seq"] = seq
        detail.update({"appeal_id": aid})
        return

    if command == "appeal_pause":
        # 幂等：没有 open 的条目不是错误，返回空数组（与 AppealStore.pause 同义）
        paused = []
        for item in appeals:
            if item.get("state") == "open":
                item["state"] = "paused_version_invalidated"
                item["pause_reason"] = payload.get("reason") or "version_invalidated"
                item["paused_at"] = _iso(now)
                paused.append(copy.deepcopy(item))
        detail["paused"] = paused
        return

    if command == "appeal_stale":
        days = payload.get("days", 30)
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise LedgerValidation("bad_appeal", "days 必须是整数")
        marked = []
        for item in appeals:
            if item.get("state") != "paused_version_invalidated":
                continue
            paused_at = item.get("paused_at")
            if not paused_at:
                continue
            try:
                ts = calendar.timegm(
                    time.strptime(paused_at, "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                continue
            if float(now) - ts > days * 86400:
                item["state"] = "stale"
                item["stale_at"] = _iso(now)
                marked.append(copy.deepcopy(item))
        detail["staled"] = marked
        return

    aid = _nonempty(payload.get("appeal_id"), "appeal_id")
    target = next((a for a in appeals if a.get("appeal_id") == aid), None)
    if target is None:
        raise LedgerNotFound("appeal_not_found", "申诉不存在：%s" % aid)

    if command == "appeal_migrate":
        if actor != target.get("appellant"):
            raise LedgerConflict("not_original_appellant", "只有原申诉人可以确认迁移")
        if target.get("state") != "paused_version_invalidated":
            raise LedgerConflict(
                "not_paused", "只有 paused 的申诉可迁移，当前 %r" % target.get("state"))
        target["state"] = "migrated"
        target["migrated_at"] = _iso(now)
        detail.update({"appeal_id": aid, "state": "migrated"})
        return

    if command == "appeal_withdraw":
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise LedgerValidation("missing_reason", "撤销必须写 reason")
        if actor != target.get("appellant"):
            raise LedgerConflict("not_original_appellant", "只有原申诉人可以撤销")
        if target.get("state") not in ("open", "paused_version_invalidated"):
            raise LedgerConflict(
                "terminal_state", "终态申诉不能撤销，当前 %r" % target.get("state"))
        target["state"] = "withdrawn"
        target["withdrawn_at"] = _iso(now)
        target["withdraw_reason"] = reason
        detail.update({"appeal_id": aid, "state": "withdrawn"})
        return

    raise LedgerValidation("bad_command", "未知 appeal 命令 %r" % command)


GRANT_COMMANDS = frozenset({"grant_propose", "grant_execute", "grant_approve",
                            "grant_revoke"})
GRANT_AGGREGATE_PREFIX = "grants:"
# T-313a：通知聚合（收件箱按人一份）。类型清单是 base/notifications.py 的
# TYPES —— 同一个量不写第二份口径（§2.4.8）。
NOTIFICATION_AGGREGATE_PREFIX = "notifications:"
NOTIFICATION_AGGREGATE_TYPE = "notifications"
# D3（收尾方案 §四）：每人收件箱 200 条显式上限，超限先归档最旧已读，未读永不淘汰。
NOTIFICATION_INBOX_LIMIT = 200

# 延迟导入写法说明：模块级 import 会把 notifications.py 的 sys.path 侧效带进
# reducer 的每个使用方；这里是唯一消费点，函数内导入一次并缓存。
_NOTIFICATION_TYPES_CACHE = None


def _notification_types():
    global _NOTIFICATION_TYPES_CACHE
    if _NOTIFICATION_TYPES_CACHE is None:
        from base.notifications import TYPES as _TYPES
        _NOTIFICATION_TYPES_CACHE = frozenset(_TYPES)
    return _NOTIFICATION_TYPES_CACHE


def _notification_aggregate_parts(aggregate_id):
    """notifications:<tenant>:<recipient> -> (tenant, recipient)；形状不对即拒。"""
    parts = aggregate_id.split(":")
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise LedgerValidation(
            "bad_notification_aggregate",
            "通知聚合 ID 必须是 notifications:<tenant>:<recipient>")
    return parts[1], parts[2]


def aggregate_type_for(aggregate_id):
    """聚合 ID -> 聚合类型。**唯一一份判定。**

    ★ 为什么必须只有一份：权威批次、事件快照、投影分流三处都要知道
      「这是不是一个案件」。三处各写一遍判断，必然漂移 ——
      而漂移的后果不是报错，是某个聚合被当案件写进 review_cases
      （T-314a 实测过那个形状：GET /api/v1/cases 里出现 grants:on_x）。
    """
    if isinstance(aggregate_id, str) and aggregate_id.startswith(GRANT_AGGREGATE_PREFIX):
        return "grant_registry"
    if isinstance(aggregate_id, str) \
            and aggregate_id.startswith(NOTIFICATION_AGGREGATE_PREFIX):
        return NOTIFICATION_AGGREGATE_TYPE
    return "review_case"
GRANT_CAPABILITIES = frozenset({"release.sign", "release.revoke",
                               "takedown.execute", "takedown.waive"})


def _grant_id(capability, user_id, scope, seq):
    """确定性 grant_id。

    ★ 不用自增：进程内自增在重启后归零，会和历史撞号
      （`api/write_api.py` 的 AppealStore 踩过同一个坑，见 T-311 施工单 §一）。
      这里用 seq + 内容哈希，seq 落在 state 里，跨重启连续。
    """
    return "grant-" + _hash({
        "capability": capability, "user_id": user_id,
        "scope": scope, "seq": seq,
    })[:16]


def _grant(state, command, actor, payload, now, detail):
    """grant_propose / grant_execute / grant_approve 的纯状态迁移。

    ## 为什么三方不同人在这里**也**要判，而不是只靠 validate_grant_actors

    `base.rbac.validate_grant_actors()` 是**授予发生那一刻**的综合校验
    （还查角色、能力、scope 越界）。这里判的是**逐步的**：
    同一个人不许走完三步。两者不能互相替代 —— 前者证明「三个都合格」，
    后者证明「不能一个人冒充三个」。少了后者，一个人可以连续调三次
    API 走完全流程，而 validate_grant_actors 在最后一步只会看到
    三个 id 相同 → 拒，但那时前两步已经写进权威了。

    ## reason 不可改写

    `reason` 是「依据」。后续命令不许动它 —— 改了就等于换了理由而留痕看不出来。
    """
    grants = state.setdefault("grants", [])

    if command == "grant_propose":
        capability = _nonempty(payload.get("capability"), "capability")
        user_id = _nonempty(payload.get("user_id"), "user_id")
        reason = _nonempty(payload.get("reason"), "reason")
        if capability not in GRANT_CAPABILITIES:
            raise LedgerValidation(
                "bad_grant", "capability 必须是 %r" % (sorted(GRANT_CAPABILITIES),))
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            raise LedgerValidation("bad_grant", "scope 必须是对象")
        tenant = _nonempty(scope.get("tenant"), "scope.tenant")
        lines = scope.get("product_lines")
        if not isinstance(lines, list) or not lines:
            # ★ 空品线集合不是「全部品线」—— 见 rbac._scope_contains 的同一条纪律
            raise LedgerValidation(
                "bad_grant", "scope.product_lines 必须是非空数组（空不是通配）")
        if any(not isinstance(x, str) or not x.strip() for x in lines):
            raise LedgerValidation("bad_grant", "scope.product_lines 必须是非空字符串数组")

        seq = int(state.get("grant_seq") or 0) + 1
        gid = _grant_id(capability, user_id, scope, seq)
        if any(g.get("grant_id") == gid for g in grants):
            raise LedgerConflict("duplicate_grant", "同一 grant 已存在")
        grants.append({
            "grant_id": gid,
            "capability": capability,
            "user_id": user_id,
            "scope": copy.deepcopy(scope),
            "platform": payload.get("platform"),
            "reason": reason,
            "state": "proposed",
            "proposed_by": actor,
            "proposed_at": _iso(now),
            "executed_by": None, "executed_at": None,
            "approved_by": None, "approved_at": None,
            # T-315 才实现撤权；这里先把结构留好，免得那时改 schema
            "revoked_by": None, "revoked_at": None, "revoke_reason": None,
            "history": [{
                "action": "propose", "actor": actor, "at": _iso(now),
                "from": None, "to": "proposed", "note": reason,
            }],
        })
        state["grant_seq"] = seq
        detail.update({"grant_id": gid, "capability": capability,
                       "user_id": user_id})
        return

    gid = _nonempty(payload.get("grant_id"), "grant_id")
    target = next((g for g in grants if g.get("grant_id") == gid), None)
    if target is None:
        raise LedgerNotFound("grant_not_found", "grant 不存在：%s" % gid)

    if command == "grant_execute":
        if target.get("state") != "proposed":
            raise LedgerConflict(
                "not_proposed", "只有 proposed 可执行，当前 %r" % target.get("state"))
        if actor == target.get("proposed_by"):
            raise LedgerConflict("same_actor", "提案人不得自己执行（三权分立）")
        target["state"] = "executed"
        target["executed_by"] = actor
        target["executed_at"] = _iso(now)
        target["history"].append({
            "action": "execute", "actor": actor, "at": _iso(now),
            "from": "proposed", "to": "executed",
            "note": payload.get("note") or "",
        })
        detail.update({"grant_id": gid, "state": "executed"})
        return

    if command == "grant_approve":
        if target.get("state") != "executed":
            raise LedgerConflict(
                "not_executed", "只有 executed 可审批，当前 %r" % target.get("state"))
        if actor in (target.get("proposed_by"), target.get("executed_by")):
            raise LedgerConflict("same_actor", "审批人必须是第三方（三权分立）")
        target["state"] = "approved"
        target["approved_by"] = actor
        target["approved_at"] = _iso(now)
        target["history"].append({
            "action": "approve", "actor": actor, "at": _iso(now),
            "from": "executed", "to": "approved",
            "note": payload.get("note") or "",
        })
        detail.update({"grant_id": gid, "state": "approved"})
        return

    if command == "grant_revoke":
        # T-315a：撤权 = approved → revoked 的状态迁移（**不是删除**）。
        # 逐步校验在这里（validate_grant_actors 不能替代逐步校验，见 docstring）；
        # 能力级判定（谁有 admin.grant.approve/execute）在 service 层 ——
        # reducer 只判「这个人此刻能不能对这条 grant 做这件事」。
        if target.get("state") != "approved":
            raise LedgerConflict(
                "grant_not_active", "只有 approved 可撤权，当前 %r" % target.get("state"))
        if actor == target.get("user_id"):
            # 自己撤自己的授权 = 三权分立被绕开的最短路径。
            raise LedgerConflict(
                "self_revoke", "不许自己撤自己的授权（三权分立）")
        reason = _nonempty(payload.get("reason"), "revoke_reason")
        target["state"] = "revoked"
        target["revoked_by"] = actor
        target["revoked_at"] = _iso(now)
        target["revoke_reason"] = reason
        target["history"].append({
            "action": "revoke", "actor": actor, "at": _iso(now),
            "from": "approved", "to": "revoked", "note": reason,
        })
        detail.update({"grant_id": gid, "state": "revoked"})
        return

    raise LedgerValidation("bad_command", "未知 grant 命令 %r" % command)


NOTIFICATION_COMMANDS = frozenset(
    {"notification_emit", "notification_read", "notification_ack"})

RELEASE_COMMANDS = frozenset({
    "release_sign", "release_reject", "release_revoke",
    # T-317a：失效 / 重审 job / 重判应用。_changes 保持唯一一份
    # （复用 ReleaseGate._changes，不许复制第二份失效判据）。
    "release_invalidate", "release_job_start", "release_job_complete",
    "rejudge_apply"})


def _release_container():
    """T-310b：签发状态容器（T-310 施工单 §四 的 state 形状）。

    active_job / successor 为 T-317 重审预留；release 放在 case aggregate 里
    不另开聚合 —— 签名绑定 case_version，换聚合就要维护跨聚合一致。
    """
    return {"status": "pending_release", "release_status": "待放行",
            "signatures": [], "events": [], "active_job": None,
            "successor": None}


def _release(state, command, actor, payload, now, detail):
    """release_sign / release_reject / release_revoke 的纯状态迁移。

    不消费 step-up（reducer 无 session store）、不验权限（那是 service 层的事）。
    只做：状态机合法性、签名结构校验、派生链、事件追加。
    判定语义与 ReleaseGate.sign/revoke 保持同一份（gate 是开发装配的内存参照，
    这里的权威真相源；两边不一致时以本函数为准并修 gate）。

    与 gate 的两处刻意差异（都是形状统一，不是语义变更）：
    - 事件 at 用 _iso(now)（reducer 全部事件都是 ISO 串，gate 内存里用裸数）；
    - revoke 的 reason / step_up_ref 必填 —— gate 不判，但权威侧「谁撤的、
      凭什么 step-up」是留痕四元的必备项，缺了就是一条没法审计的撤回。
    """
    from base.release_gate import (ReleaseGate,  # noqa: PLC0415 纯函数，无环
                                   validate_signature)

    release = state.get("release")
    if command in ("release_sign", "release_reject"):
        # 红线 R2：未结案不许签发 —— 与「未裁决不许结案」合起来，
        # 「复核是一个真动作」才成立。少这道，签发可以绕开复核。
        if state["status"] != "closed":
            raise LedgerConflict(
                "invalid_transition", "未结案不许签发，当前案件状态 %r" % state["status"])
        if release is not None and release.get("status") != "pending_release":
            raise LedgerConflict(
                "invalid_transition", "只有 pending_release 可签发，当前 %r"
                % (release or {}).get("status"))
        expected_decision = "signed" if command == "release_sign" else "rejected"
        sig = payload.get("signature")
        if not isinstance(sig, dict):
            raise LedgerValidation("bad_signature", "signature 必须是对象")
        errs = validate_signature(sig)
        if errs:
            raise LedgerValidation(
                "bad_signature", "签名不合法：%s" % "; ".join(errs))
        if sig.get("decision") != expected_decision:
            raise LedgerValidation(
                "bad_signature",
                "命令与签名 decision 不一致：%r vs %r" % (command, sig.get("decision")))
        if sig.get("case_id") != state["case_id"]:
            raise LedgerValidation(
                "bad_signature", "签名绑定的是别的案件：%r" % sig.get("case_id"))
        # 签一个旧版本 = 绑定作废（防「看起来签过、其实绑的不是这份 state」）。
        if sig.get("case_version") != state["version"]:
            raise LedgerValidation(
                "bad_signature",
                "case_version 必须等于当前版本：%r vs %r"
                % (sig.get("case_version"), state["version"]))
        prev = (release or {}).get("signatures") or []
        expected_prev = prev[-1]["signature_id"] if prev else None
        if sig.get("derived_from") != expected_prev:
            raise LedgerValidation(
                "bad_signature",
                "derived_from 必须等于上一条签名 id：%r vs %r"
                % (sig.get("derived_from"), expected_prev))
        if release is None:
            release = _release_container()
            state["release"] = release
        release["signatures"].append(copy.deepcopy(sig))
        release["status"] = ("signed" if expected_decision == "signed"
                             else "rejected")
        release["release_status"] = ("已放行" if expected_decision == "signed"
                                     else "已拒绝")
        release["events"].append({
            "kind": "release_signed" if expected_decision == "signed"
            else "release_rejected",
            "at": _iso(now), "actor": actor,
            "step_up_ref": sig.get("step_up_ref"), "reason": sig.get("reason"),
        })
        detail.update({"signature_id": sig["signature_id"]})
        return

    # ── T-317a：失效 / 重审 job / 重判应用 ──────────────────────────
    if command == "release_invalidate":
        # payload["current"] = **当前**外部绑定快照（规则表版本 / KB 快照 /
        # 依据版本等，由服务层 sweeper 采集传入）。变化判定复用
        # ReleaseGate._changes —— 失效判据全仓只许这一份。
        if release is None or release.get("status") != "signed":
            raise LedgerConflict(
                "nothing_to_reaudit", "只有 signed 案件可失效重审，当前 %r"
                % ((release or {}).get("status") if release else None))
        sigs = release.get("signatures") or []
        if not sigs:
            raise LedgerConflict("nothing_to_reaudit", "没有签名可比对")
        current = payload.get("current")
        if not isinstance(current, dict):
            raise LedgerValidation(
                "bad_reaudit", "current 绑定缺失（外部快照未采集）")
        changes = ReleaseGate._changes(sigs[-1], current)
        if not changes:
            raise LedgerConflict("nothing_to_reaudit", "五类输入无变化，无需重审")
        # job_id 确定性派生（case + version + change_set）—— 幂等重放不漂移。
        # ★ 禁含 now：_grant_id/_appeal_id 注释记录的自增/时间戳撞号同族。
        # job_id = case + change_set（不含 version）：同案同变化集必须
        # 汇入同一个 job（merge 语义）；带 version 会让第二次失效永远
        # 建新 job —— 确定性与可合并不可兼得时，取可合并。
        job_id = "rj-" + _hash({"case_id": state["case_id"],
                                "changes": changes})[:16]
        active = release.get("active_job")
        if isinstance(active, dict) and active.get("job_id") == job_id \
                and active.get("state") in ("queued", "running"):
            detail.update({"job_id": job_id, "merged": True})
            return
        new_job = {"job_id": job_id, "state": "queued",
                   "change_set": copy.deepcopy(changes),
                   "queued_at": _iso(now), "successor": None}
        if isinstance(active, dict) and active.get("state") == "running":
            # running 建后继（gate complete_job 语义的镜像）：完成后顶上。
            new_job["predecessor"] = active["job_id"]
            release["successor"] = new_job
        else:
            release["active_job"] = new_job
        release["events"].append({
            "kind": "release_invalidated", "at": _iso(now), "actor": actor,
            "change_count": len(changes)})
        detail.update({"job_id": job_id, "change_count": len(changes)})
        return

    if command == "release_job_start":
        job = release.get("active_job") if release else None
        if not isinstance(job, dict) or job.get("state") != "queued":
            raise LedgerConflict(
                "invalid_transition", "只有 queued job 可启动，当前 %r"
                % ((job or {}).get("state") if job else None))
        job["state"] = "running"
        job["started_at"] = _iso(now)
        release["events"].append({"kind": "release_job_started",
                                  "at": _iso(now), "actor": actor})
        detail.update({"job_id": job["job_id"]})
        return

    if command == "release_job_complete":
        job = release.get("active_job") if release else None
        if not isinstance(job, dict) or job.get("state") != "running":
            raise LedgerConflict(
                "invalid_transition", "只有 running job 可完成，当前 %r"
                % ((job or {}).get("state") if job else None))
        job["state"] = "done"
        job["completed_at"] = _iso(now)
        succ = release.get("successor")
        if isinstance(succ, dict):
            release["active_job"] = succ
            release["successor"] = None
            release["events"].append({"kind": "release_job_done",
                                      "at": _iso(now), "actor": actor,
                                      "successor": succ.get("job_id")})
        else:
            # 重审完成 → 回 pending_release（再签发走 T-310 的 release_sign，
            # derived_from 接上一条签名 —— 链不断）。
            release["status"] = "pending_release"
            release["release_status"] = "待放行"
            release["events"].append({"kind": "release_job_done",
                                      "at": _iso(now), "actor": actor})
        detail.update({"job_id": job["job_id"]})
        return

    if command == "rejudge_apply":
        # 重判结果应用：换 ir / report_snapshot / judgment / 绑定快照。
        # ★ expected_prev_ir_id 乐观校验 —— 防并发重判互相覆盖。
        job = release.get("active_job") if release else None
        if not isinstance(job, dict) or job.get("state") != "running":
            raise LedgerConflict(
                "invalid_transition", "只有 running job 能应用重判")
        new_ir = payload.get("ir")
        if not isinstance(new_ir, dict) or not isinstance(
                new_ir.get("ir_id"), str) or not new_ir["ir_id"]:
            raise LedgerValidation("bad_rejudge", "ir 必须是含 ir_id 的对象")
        findings = new_ir.get("findings")
        if not isinstance(findings, list):
            raise LedgerValidation("bad_rejudge", "ir.findings 必须是数组")
        if not isinstance(new_ir.get("decision"), dict) \
                or new_ir["decision"].get("state") not in DECISION_LABELS:
            raise LedgerValidation(
                "bad_rejudge", "ir.decision.state 必须在五档内")
        prev_ir = state.get("ir") or {}
        if payload.get("expected_prev_ir_id") != prev_ir.get("ir_id"):
            raise LedgerConflict(
                "ir_moved", "重判基于的 ir 已变化：%r vs %r"
                % (payload.get("expected_prev_ir_id"), prev_ir.get("ir_id")))
        kb_hash = payload.get("kb_snapshot_hash")
        if not (isinstance(kb_hash, str) and len(kb_hash) == 64
                and set(kb_hash.lower()) <= set("0123456789abcdef")):
            raise LedgerValidation(
                "bad_rejudge", "kb_snapshot_hash 必须是 64 位十六进制")
        ctv = payload.get("conflict_table_version")
        if not isinstance(ctv, str) or not ctv.strip() \
                or ctv != new_ir.get("control_points_version"):
            raise LedgerValidation(
                "bad_rejudge",
                "conflict_table_version 与新 ir.control_points_version 不一致")
        media_fp = payload.get("media_fingerprints") or {}
        if not isinstance(media_fp, dict):
            raise LedgerValidation("bad_rejudge", "media_fingerprints 必须是对象")
        state["ir_prev"] = {"ir_id": prev_ir.get("ir_id"),
                            "ir_version": prev_ir.get("ir_version")}
        state["ir"] = copy.deepcopy(new_ir)
        new_snap = payload.get("report_snapshot")
        if new_snap is not None and not isinstance(new_snap, dict):
            raise LedgerValidation(
                "bad_rejudge", "report_snapshot 必须是对象或 null")
        state["report_snapshot"] = copy.deepcopy(new_snap)
        state["judgment"] = copy.deepcopy(payload.get("judgment") or {})
        state["kb_snapshot_hash"] = kb_hash
        state["conflict_table_version"] = ctv
        state["media_fingerprints"] = copy.deepcopy(media_fp)
        release["events"].append({"kind": "release_rejudged",
                                  "at": _iso(now), "actor": actor,
                                  "new_ir_id": new_ir["ir_id"]})
        detail.update({"ir_id": new_ir["ir_id"], "job_id": job["job_id"]})
        return

    if command != "release_revoke":
        raise LedgerValidation("bad_command", "未知 release 命令 %r" % command)
    # release_revoke：只改状态 + 追加事件，**不追加签名**（gate 同语义）。
    if release is None or release.get("status") != "signed":
        raise LedgerConflict(
            "invalid_transition", "只有 signed 可撤回，当前 %r"
            % ((release or {}).get("status") if release else None))
    # ★ T-315b / #123c：撤回绑定**原签发人**（权威判定点在 reducer；
    #   gate.revoke 的同款检查是开发装配镜像）。此前任何持 release.revoke
    #   者可撤任何人的签发 —— 该判定 2026-10-25 之前不存在。
    sigs = release.get("signatures") or []
    last_signer = (sigs[-1] or {}).get("signer_id") if sigs else None
    if actor != last_signer:
        raise LedgerConflict(
            "not_original_signer",
            "撤回只能由原签发人执行（#123c），该案签发人是 %r" % last_signer)
    reason = _nonempty(payload.get("reason"), "revoke_reason")
    step_up_ref = _nonempty(payload.get("step_up_ref"), "revoke_step_up_ref")
    release["status"] = "revoked"
    release["release_status"] = "已撤回"
    release["events"].append({
        "kind": "release_revoked", "at": _iso(now), "actor": actor,
        "step_up_ref": step_up_ref, "reason": reason,
    })
    detail.update({"revoked": True})
    return



def _notification_id(ntype, dedup_key, recipient):
    """确定性通知 id。★ 不用自增：自增在重启后归零撞号（_grant_id 同一条）。"""
    return "notif-" + _hash({
        "type": ntype, "dedup_key": dedup_key, "recipient": recipient,
    })[:16]


def _notification(state, command, actor, payload, now, detail):
    """notification_emit / read / ack 的纯状态迁移（T-313b）。

    语义映射自 base/notifications.py 的 mark_read / mark_acked：
    ack 必须先读（E_ACK_WITHOUT_READ -> LedgerConflict("ack_without_read")）。
    这里只做权威侧的状态迁移；飞书通道、去重台账都在 service 层 ——
    reducer 不发通知（文件头纪律）。
    """
    if state.get("tenant") is None:
        raise LedgerValidation(
            "bad_notification_aggregate", "通知聚合状态缺 tenant")
    items = state.setdefault("items", [])

    if command == "notification_emit":
        ntype = _nonempty(payload.get("type"), "notification_type")
        if ntype not in _notification_types():
            raise LedgerValidation(
                "bad_notification", "type 必须在 base.notifications.TYPES")
        dedup_key = _nonempty(payload.get("dedup_key"), "dedup_key")
        # ★ 关联案件用 related_case_id，不用 case_id：BusinessEventStore.execute
        #   会把 payload["case_id"] 无条件注入成 aggregate_id（案件聚合的约定），
        #   通知聚合若也读 case_id，读到的永远是收件箱自己的 id 而不是业务案件。
        case_ref = payload.get("related_case_id")
        if case_ref is not None and (not isinstance(case_ref, str) or not case_ref.strip()):
            raise LedgerValidation(
                "bad_notification", "related_case_id 必须是非空字符串或 null")
        nid = _notification_id(ntype, dedup_key, state["recipient"])
        if any(i.get("notification_id") == nid for i in items):
            raise LedgerConflict(
                "duplicate_notification",
                "同 (type, dedup_key, recipient) 的通知已存在：%s" % nid)
        # 超限归档（D3）：先归档最旧的已读条目；只剩未读时拒 —— 未读永不淘汰。
        active = [i for i in items if not i.get("archived")]
        if len(active) >= NOTIFICATION_INBOX_LIMIT:
            for old in sorted(active, key=lambda x: (x.get("created_at") or "",
                                                     x.get("notification_id") or "")):
                if old.get("read_at") is not None:
                    old["archived"] = True
                    state["archived_count"] = int(state.get("archived_count") or 0) + 1
                    break
            else:
                raise LedgerConflict(
                    "inbox_full",
                    "收件箱已满（%d 条未读），且没有可归档的已读条目" % len(active))
        item = {
            "notification_id": nid,
            "type": ntype,
            "dedup_key": dedup_key,
            "related_case_id": case_ref,
            "created_at": _iso(now),
            "read_at": None,
            "acked_at": None,
            "archived": False,
            "payload": copy.deepcopy(payload.get("payload") or {}),
        }
        items.append(item)
        detail.update({"notification_id": nid})
        return

    nid = _nonempty(payload.get("notification_id"), "notification_id")
    item = next((i for i in items if i.get("notification_id") == nid), None)
    if item is None or item.get("archived"):
        raise LedgerNotFound("notification_not_found", "通知不存在或已归档：%s" % nid)
    if command == "notification_read":
        if item.get("read_at") is not None:
            raise LedgerConflict("already_read", "通知已读：%s" % nid)
        item["read_at"] = _iso(now)
        detail.update({"notification_id": nid})
        return
    if command == "notification_ack":
        if item.get("read_at") is None:
            raise LedgerConflict(
                "ack_without_read", "通知必须先读才能确认（E_ACK_WITHOUT_READ）")
        if item.get("acked_at") is not None:
            raise LedgerConflict("already_acked", "通知已确认：%s" % nid)
        item["acked_at"] = _iso(now)
        detail.update({"notification_id": nid})
        return
    raise LedgerValidation("bad_command", "未知 notification 命令 %r" % command)


def _ingest_submission(state, actor, payload, now):
    """把一次已判定的 submission 写进案件初始状态；只在 version 0 上执行一次。"""
    if state["version"] != 0 or state.get("submission_id"):
        raise LedgerConflict("already_ingested", "该 submission 已建案")
    submission_id = _nonempty(payload.get("submission_id"), "submission_id")
    submission_hash = _nonempty(payload.get("submission_hash"), "submission_hash")
    content = payload.get("content")
    if not isinstance(content, dict):
        raise LedgerValidation("bad_content", "content 必须是 ContentUnit 对象")
    if not isinstance(content.get("unit_id"), str) or not content["unit_id"].strip():
        raise LedgerValidation("bad_content", "content.unit_id 必须是非空字符串")
    fingerprint = content.get("fingerprint")
    if not isinstance(fingerprint, dict) or not isinstance(
            fingerprint.get("text_sha256"), str) or not fingerprint["text_sha256"].strip():
        raise LedgerValidation("bad_content", "content.fingerprint.text_sha256 必须是非空字符串")
    ir = payload.get("ir")
    if not isinstance(ir, dict):
        raise LedgerValidation("bad_ir", "ir 必须是 ReviewIR 对象")
    if not isinstance(ir.get("ir_id"), str) or not ir["ir_id"].strip():
        raise LedgerValidation("bad_ir", "ir.ir_id 必须是非空字符串")
    findings = ir.get("findings")
    if not isinstance(findings, list):
        raise LedgerValidation("bad_ir", "ir.findings 必须是数组")
    decision = ir.get("decision")
    if not isinstance(decision, dict) or decision.get("state") not in DECISION_LABELS:
        raise LedgerValidation("bad_ir", "ir.decision.state 必须在 %r" % (DECISION_LABELS,))
    # T-316b: 报告渲染输入。允许缺省（None），但**不许是坏形状** ——
    # 「没有报告可渲染」由 publish 时判（ReportStore 会拒），
    # 「形状不对」必须在这里拒，否则坏快照会随权威一起被永久保存。
    report_snapshot = payload.get("report_snapshot")
    if report_snapshot is not None:
        if not isinstance(report_snapshot, dict):
            raise LedgerValidation(
                "bad_report_snapshot", "report_snapshot 必须是对象或 null")
        if not isinstance(report_snapshot.get("ir"), dict):
            raise LedgerValidation(
                "bad_report_snapshot", "report_snapshot.ir 必须是对象")
        if not isinstance(report_snapshot.get("failure_kind_counts"), dict):
            raise LedgerValidation(
                "bad_report_snapshot", "report_snapshot.failure_kind_counts 必须是对象")

    judgment = payload.get("judgment")
    if not isinstance(judgment, dict):
        raise LedgerValidation("bad_judgment", "judgment 必须是对象")
    if judgment.get("run_state") != "OK":
        raise LedgerValidation("bad_judgment", "judgment.run_state 必须是 OK")
    if judgment.get("label") not in DECISION_LABELS:
        raise LedgerValidation("bad_judgment", "judgment.label 必须在 %r" % (DECISION_LABELS,))
    if judgment.get("label") != decision.get("state"):
        raise LedgerValidation("bad_judgment", "judgment.label 与 ir.decision.state 不一致")
    # T-310a：签发绑定字段（T-310 施工单 §二 前置 A —— 取不到即拒，不许补默认值）。
    hex64 = set("0123456789abcdef")
    kb_hash = payload.get("kb_snapshot_hash")
    if not (isinstance(kb_hash, str) and len(kb_hash) == 64
            and set(kb_hash.lower()) <= hex64):
        raise LedgerValidation(
            "bad_binding_fields", "kb_snapshot_hash 必须是 64 位十六进制")
    ctv = payload.get("conflict_table_version")
    if not isinstance(ctv, str) or not ctv.strip():
        raise LedgerValidation(
            "bad_binding_fields", "conflict_table_version 必须是非空字符串")
    # 恒等断言：与 ir.control_points_version 是同一个量，两处漂移在这里红。
    if ctv != ir.get("control_points_version"):
        raise LedgerValidation(
            "bad_binding_fields",
            "conflict_table_version 与 ir.control_points_version 不一致")
    media_fp = payload.get("media_fingerprints")
    if media_fp is None:
        media_fp = {}
    if not isinstance(media_fp, dict):
        raise LedgerValidation(
            "bad_binding_fields", "media_fingerprints 必须是对象")
    # T-433：L1 多模态观察。形状在这里拒，**不许**坏数据随权威永久保存。
    observations = payload.get("multimodal_observations")
    if observations is None:
        observations = []
    if not isinstance(observations, list):
        raise LedgerValidation(
            "bad_multimodal_observations", "multimodal_observations 必须是数组")
    for index, entry in enumerate(observations):
        where = "multimodal_observations[%d]" % index
        if not isinstance(entry, dict):
            raise LedgerValidation("bad_multimodal_observations",
                                   "%s 必须是对象" % where)
        if str(entry.get("status") or "") not in OBSERVATION_STATUSES:
            raise LedgerValidation(
                "bad_multimodal_observations",
                "%s.status 必须在 %r" % (where, sorted(OBSERVATION_STATUSES)))
        if not isinstance(entry.get("task"), str) or not entry["task"].strip():
            raise LedgerValidation("bad_multimodal_observations",
                                   "%s.task 必须是非空字符串" % where)
        # ★ status=ok 的条目必须带非空 statement；未测/出错的条目带 reason。
        #   这条断言堵的是「一条空观察被读成『看过、没问题』」—— 本项目反复踩的形状。
        if entry["status"] == "ok":
            if not isinstance(entry.get("statement"), str) or not entry["statement"].strip():
                raise LedgerValidation(
                    "bad_multimodal_observations",
                    "%s 是 ok 却没有非空 statement" % where)
        else:
            if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
                raise LedgerValidation(
                    "bad_multimodal_observations",
                    "%s 非 ok 必须带非空 reason（未测不是没问题）" % where)
    state.update({
        "submission_id": submission_id,
        "submission_hash": submission_hash,
        "content": copy.deepcopy(content),
        "ir": copy.deepcopy(ir),
        "report_snapshot": copy.deepcopy(report_snapshot),
        "judgment": copy.deepcopy(judgment),
        "kb_snapshot_hash": kb_hash,
        "conflict_table_version": ctv,
        "media_fingerprints": copy.deepcopy(media_fp),
        "multimodal_observations": copy.deepcopy(observations),
        # ★ ADR-0021 主线：「为什么没看成」的说明。改前这里**没有**这个键，
        #   于是 payload 里带了也会被 reducer 丢掉 —— 与 T-455 的
        #   `intent_inference` 是同一个形状（payload 有、state 没有）。
        "multimodal_note": (payload.get("multimodal_note") or None),
        "tenant": _nonempty(payload.get("tenant"), "tenant"),
        "product_line": _nonempty(payload.get("product_line"), "product_line"),
        "submitter_id": _nonempty(payload.get("submitter_id"), "submitter_id"),
        "ingested_at": _iso(now),
    })
    return submission_id, ir["ir_id"]


def reduce_command(old_state, command, actor, expected_version, payload=None,
                   *, now=None, lease_seconds=LEASE_SECONDS):
    """返回 ``(new_state, [event], result)``；拒绝时不改变入参。"""
    state = copy.deepcopy(old_state or initial_state((payload or {}).get("case_id")))
    actor = _nonempty(actor, "actor")
    payload = copy.deepcopy(payload or {})
    now = time.time() if now is None else float(now)
    expected_version = int(expected_version)

    if state["version"] != expected_version:
        raise LedgerConflict(
            "version_conflict",
            "期望版本 %r，实际 %r" % (expected_version, state["version"]),
        )

    detail = {}
    if command == "ingest_submission":
        submission_id, ir_id = _ingest_submission(state, actor, payload, now)
        detail.update({"submission_id": submission_id, "ir_id": ir_id})
    elif command == "claim":
        if state["status"] == "claimed":
            raise LedgerConflict("already_claimed", "案件已被领取")
        if state["status"] == "closed":
            raise LedgerConflict("case_closed", "案件已提交，不能重新领取")
        state.update({
            "status": "claimed", "assignee": actor,
            "claimed_at": _iso(now), "last_activity": _iso(now),
            "lease_expires": now + int(lease_seconds),
        })
    elif command == "unclaim":
        _require_claim(state, actor, expected_version, now)
        if not state["drafts"]:
            content = {"form": {}, "notes": "", "evidence_selections": [],
                       "references": []}
            _new_draft(state, actor, now, content, kind="lease_release")
        state.update({
            "status": "released", "assignee": None,
            "released_at": _iso(now),
            "released_draft_id": state["primary_draft_id"],
            "lease_expires": None,
        })
    elif command == "reassign":
        _require_claim(state, actor, expected_version, now)
        new_assignee = _nonempty(payload.get("assignee"), "assignee")
        state["assignee"] = new_assignee
        state["last_activity"] = _iso(now)
        detail["new_assignee"] = new_assignee
    elif command == "heartbeat":
        _require_claim(state, actor, expected_version, now)
        state["last_activity"] = _iso(now)
        state["lease_expires"] = now + int(lease_seconds)
    elif command == "save_draft":
        _require_claim(state, actor, expected_version, now)
        form = payload.get("form", {})
        notes = payload.get("notes", "")
        evidence = payload.get("evidence_selections", [])
        references = payload.get("references", [])
        if not isinstance(form, dict):
            raise LedgerValidation("bad_form", "form 必须是 dict")
        if not isinstance(notes, str):
            raise LedgerValidation("bad_notes", "notes 必须是字符串")
        if not isinstance(evidence, list) or not isinstance(references, list):
            raise LedgerValidation("bad_draft", "evidence_selections/references 必须是 list")
        draft = _new_draft(
            state, actor, now,
            {"form": form, "notes": notes,
             "evidence_selections": evidence, "references": references},
            kind="autosave",
        )
        detail["draft_id"] = draft["draft_id"]
    elif command == "adopt_draft":
        _require_claim(state, actor, expected_version, now)
        source_id = _nonempty(payload.get("source_draft_id"), "source_draft_id")
        source = _draft(state, source_id)
        if source is None:
            raise LedgerNotFound("draft_not_found", "源 draft 不存在")
        if source_id != state["primary_draft_id"]:
            raise LedgerConflict("not_primary", "只能 adopt primary draft")
        draft = _new_draft(
            state, actor, now,
            {"form": source["form"], "notes": source["notes"],
             "evidence_selections": source["evidence_selections"],
             "references": source["references"]},
            kind="adopt", derived_from=source_id,
        )
        detail.update({"draft_id": draft["draft_id"], "derived_from": source_id})
    elif command == "reference_fragment":
        _require_claim(state, actor, expected_version, now)
        source_id = _nonempty(payload.get("source_draft_id"), "source_draft_id")
        field_path = _nonempty(payload.get("field_path"), "field_path")
        fragment = payload.get("fragment")
        if fragment is None or (isinstance(fragment, str) and not fragment.strip()):
            raise LedgerValidation("bad_fragment", "fragment 不能为空")
        source = _draft(state, source_id)
        if source is None:
            raise LedgerNotFound("draft_not_found", "源 draft 不存在")
        if source_id == state["primary_draft_id"]:
            raise LedgerConflict("primary_requires_adopt", "primary draft 必须显式 adopt")
        ref = {
            "case_id": state["case_id"], "source_draft_id": source_id,
            "field_path": field_path, "fragment": fragment,
            "author": actor, "at": _iso(now),
        }
        state["fragment_references"].append(ref)
        detail["reference"] = ref
    elif command == "adjudicate_finding":
        _require_claim(state, actor, expected_version, now)
        finding_id = _nonempty(payload.get("finding_id"), "finding_id")
        decision = payload.get("decision")
        if decision not in ("confirmed", "rejected"):
            raise LedgerValidation(
                "bad_decision", "decision 必须是 confirmed/rejected")
        ir = state.get("ir")
        if not isinstance(ir, dict) or not isinstance(ir.get("findings"), list):
            raise LedgerNotFound("finding_not_found", "案件没有可裁决的 IR findings")
        index = next((i for i, finding in enumerate(ir["findings"])
                      if isinstance(finding, dict)
                      and finding.get("finding_id") == finding_id), None)
        if index is None:
            raise LedgerNotFound("finding_not_found", "finding 不存在：%s" % finding_id)
        finding = ir["findings"][index]
        if finding.get("status") != "candidate":
            raise LedgerConflict(
                "invalid_finding_transition",
                "只有 candidate 可以做确认/驳回，当前是 %r" % finding.get("status"))
        updated = copy.deepcopy(finding)
        updated.update({
            "status": decision,
            "adjudicated_by": actor,
            "adjudicated_at": _iso(now),
            "adjudication_reason": payload.get("reason") or "",
        })
        ir["findings"][index] = updated
        state["ir"] = ir
        detail.update({"finding_id": finding_id, "finding_status": decision})
    elif command == "submit_review":
        _require_claim(state, actor, expected_version, now)
        conclusion = payload.get("conclusion")
        if not isinstance(conclusion, dict):
            raise LedgerValidation("bad_conclusion", "conclusion 必须是 dict")
        if not isinstance(conclusion.get("review_notes"), str) or not conclusion["review_notes"].strip():
            raise LedgerValidation("bad_conclusion", "review_notes 必须是非空字符串")
        # ★ 橡皮图章守卫：还有 candidate 未裁决，不许直接结案。
        #   candidate 只可能来自 semantic（rule 命中即 confirmed）；不认识的状态
        #   一律按未裁决处理（fail-closed），不把坏数据当成「已裁决」。
        pending = []
        ir = state.get("ir")
        if isinstance(ir, dict) and isinstance(ir.get("findings"), list):
            for finding in ir["findings"]:
                if not isinstance(finding, dict):
                    pending.append("<malformed>")
                    continue
                status = finding.get("status")
                # 当前 authority 链只会产出 confirmed/rejected（adjudicate_finding）。
                # `superseded` 只有旧 FindingStore 的独立路径会写，不属于本 reducer
                # 的状态；不把它算作已裁决（fail-closed）。将来若加 supersede 命令，
                # 必须在这里补上它的权威来源。
                if status not in ("confirmed", "rejected"):
                    pending.append(finding.get("finding_id") or "<unknown>")
        if pending:
            raise LedgerConflict(
                "unadjudicated_findings",
                "还有 %d 条 finding 未裁决：%s" % (
                    len(pending), ", ".join(str(x) for x in pending[:5])))
        formal_id = "formal-" + _hash({
            "case_id": state["case_id"], "actor": actor,
            "version": state["version"] + 1, "conclusion": conclusion,
        })[:16]
        formal = {
            "formal_id": formal_id, "case_id": state["case_id"],
            "author": actor, "submitted_at": _iso(now),
            "from_draft_id": state["primary_draft_id"],
            "conclusion": conclusion,
        }
        state["formal_reviews"].append(formal)
        state["status"] = "closed"
        state["lease_expires"] = None
        detail["formal_id"] = formal_id
    elif command in TAKEDOWN_COMMANDS:
        _takedown(state, command, actor, payload, now, detail)
    elif command in REPORT_COMMANDS:
        _report(state, command, actor, payload, now, detail)
    elif command in APPEAL_COMMANDS:
        _appeal(state, command, actor, payload, now, detail)
    elif command in GRANT_COMMANDS:
        _grant(state, command, actor, payload, now, detail)
    elif command in NOTIFICATION_COMMANDS:
        _notification(state, command, actor, payload, now, detail)
    elif command in RELEASE_COMMANDS:
        _release(state, command, actor, payload, now, detail)
    elif command == "expire_lease":
        if state["status"] != "claimed" or state["lease_expires"] is None:
            raise LedgerConflict("not_claimed", "没有可过期的 lease")
        if now <= float(state["lease_expires"]):
            raise LedgerConflict("lease_active", "lease 尚未过期")
        if not state["drafts"]:
            content = {"form": {}, "notes": "", "evidence_selections": [],
                       "references": []}
            _new_draft(state, state["assignee"], now, content,
                       kind="lease_release")
        detail["released_assignee"] = state["assignee"]
        state.update({
            "status": "released", "assignee": None,
            "released_at": _iso(now),
            "released_draft_id": state["primary_draft_id"],
            "lease_expires": None,
        })
    else:
        raise LedgerValidation("bad_command", "未知命令 %r" % command)

    state["version"] += 1
    event = _event(command, state, actor, now, detail)
    if command in NOTIFICATION_COMMANDS:
        # 通知聚合的结果是收件箱形状，不是 public_case 的案件形状。
        result = {
            "aggregate_id": state["case_id"],
            "tenant": state["tenant"],
            "recipient": state["recipient"],
            "version": state["version"],
            "items": copy.deepcopy(
                [i for i in state["items"] if not i.get("archived")]),
            "archived_count": state["archived_count"],
        }
        if "notification_id" in detail:
            result["notification"] = copy.deepcopy(next(
                i for i in state["items"]
                if i.get("notification_id") == detail["notification_id"]))
        return state, [event], result
    result = public_case(state)
    if command == "ingest_submission":
        result["submission_id"] = state["submission_id"]
        result["submission_hash"] = state["submission_hash"]
        result["ir_id"] = state["ir"]["ir_id"]
        result["decision"] = copy.deepcopy(state["ir"]["decision"])
    if "draft_id" in detail:
        result["draft"] = copy.deepcopy(_draft(state, detail["draft_id"]))
    if "formal_id" in detail:
        result["formal"] = copy.deepcopy(state["formal_reviews"][-1])
    if "reference" in detail:
        result["reference"] = copy.deepcopy(detail["reference"])
    if command == "adjudicate_finding":
        result["finding"] = copy.deepcopy(next(
            finding for finding in state["ir"]["findings"]
            if finding.get("finding_id") == detail["finding_id"]))
    if command in TAKEDOWN_COMMANDS and "task_id" in detail:
        # 结果装饰不崩命令（与 release 同款）：state 才是真相源。
        task_out = next((t for t in state["takedown_tasks"]
                         if t.get("task_id") == detail["task_id"]), None)
        if task_out is not None:
            result["takedown_task"] = copy.deepcopy(task_out)
    if command in APPEAL_COMMANDS:
        if "appeal_id" in detail:
            result["appeal"] = copy.deepcopy(next(
                a for a in state["appeals"]
                if a.get("appeal_id") == detail["appeal_id"]))
        for key in ("paused", "staled"):
            if key in detail:
                result[key] = copy.deepcopy(detail[key])
    if command in REPORT_COMMANDS and "report_id" in detail:
        result["report"] = copy.deepcopy(state.get("report"))
    if command in GRANT_COMMANDS and "grant_id" in detail:
        # 命令结果带出该条 grant 的完整快照 —— 调用方不用再回读 state
        grant_out = next((g for g in state["grants"]
                          if g.get("grant_id") == detail["grant_id"]), None)
        if grant_out is not None:
            result["grant"] = copy.deepcopy(grant_out)
    if command in RELEASE_COMMANDS:
        # 结果带出签发容器与（若有）本次签名 —— 调用方不用再回读 state
        result["release"] = copy.deepcopy(state.get("release"))
        if "signature_id" in detail:
            # ★ next(..., None) + 条件带出：结果装饰不许崩命令 —— state 才是
            #   真相源，装饰层拿不到（如变异/并发窗口）就少带一个字段，
            #   让调用方显式看见缺失，而不是 500。
            sig_out = next(
                (s for s in (state.get("release") or {}).get("signatures") or []
                 if s["signature_id"] == detail["signature_id"]), None)
            if sig_out is not None:
                result["signature"] = copy.deepcopy(sig_out)
    return state, [event], result


def apply_event(_old_state, event):
    if not isinstance(event, dict) or not isinstance(event.get("state"), dict):
        raise LedgerValidation("bad_event", "review 事件缺 state 快照")
    return copy.deepcopy(event["state"])
