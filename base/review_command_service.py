#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威命令提交 + SQLite 投影协调；权威成功不因投影失败回滚。"""
from __future__ import annotations

import copy
import threading

from base.business_event_store import AuthorityConflict
from base.projector import Projector
from base.release_binding import binding_from_state
from base.release_gate import (SIGNATURE_VERSION, InvalidTransition,
                               ReleaseGate, SoDViolation, SignatureError,
                               _binding, _canonical, _sha, signature_hash,
                               validate_signature)
from base import rbac


class ReviewCommandService:
    def __init__(self, authority, projection, *,
                 report_store=None, report_bridge=None,
                 external_binding_provider=None, rejudge_fn=None,
                 takedown_assignment_policy=None):
        self.authority = authority
        self.projection = projection
        # T-316d：报告落盘。两者都可为 None —— 那时结案只是不产出报告，
        # 不影响任何既有行为（现有 6 个验证器直接 `ReviewCommandService(a, p)`，
        # 一行未动）。生产在 ProductionRuntime.start() 里注入真实实例。
        self.report_store = report_store
        self.report_bridge = report_bridge
        # WriterLease 只约束跨进程写者；FastAPI 同步 handler 会在线程池并发。
        # 权威提交 + 按序追投影必须在本进程再单飞，避免 seq2 先于 seq1 apply。
        self._lock = threading.RLock()
        # T-317c：重审执行体的两个注入点。None = 未装配（失效检测不可用，
        # 是「未测」不是「没有失效」——  production 在 start() 里接真身）。
        self.external_binding_provider = external_binding_provider
        self.rejudge_fn = rejudge_fn
        # T-312 红线 1 的触发点 seam：撤回/失效后的下线任务指派策略
        # （assignee / platform 是业务决定，不许在这里发明默认值）。
        self.takedown_assignment_policy = takedown_assignment_policy

    def status(self):
        with self._lock:
            self.authority.verify_integrity()
            return self.projection.status(self.authority.head())

    #: T-313c：这三个命令成功后要产通知。reducer 不发通知（纯函数纪律）；
    #: 服务层是唯一的生产装配点。
    _NOTIFY_ON = frozenset({"expire_lease", "unclaim", "reassign",
                            "takedown_create", "takedown_transition"})

    def execute(self, **command):
        with self._lock:
            before = None
            if command.get("command") in self._NOTIFY_ON:
                try:
                    before = self.authority.state(command.get("aggregate_id"))
                except Exception:  # noqa: BLE001
                    before = None
            committed = self.authority.execute(**command)
            response = self._respond(committed["batch"], committed["replayed"])
        # ★ 通知产出版在锁外（与报告发布同一条纪律）：emit 是一次权威写，
        #   失败不许拖垮主命令，也不许占着全局锁。
        self._emit_notifications(command, before)
        # ★ 报告发布在**锁外**：渲染是一次最长 30 秒的子进程调用。
        #   留在锁里会让「一人结案、渲染卡住」期间所有人的写请求排队 ——
        #   一次下游副作用变成全局写停顿。
        #
        # ★ 也不回滚、不改 http_status。权威已经提交，结案**已经成立**。
        #   把发布失败做成 500 会让用户以为结案没成功而重复提交，
        #   而第二次会因为 version_conflict 被拒 —— 用户看到的是「点两次都失败」。
        report = self._publish_report_after(command, response)
        if report is not None:
            # ★ 挂在 `result` 里，不挂顶层。
            #
            #   `api/write_api.py:run_review_command` 组装 HTTP body 时只取
            #   `outcome["result"]` 再补四个 authority 字段。挂顶层的话
            #   报告会**静默丢失**：结案 200、权威里也有报告，但响应里没有 ——
            #   前端拿不到 report_id，用户以为没发出报告而去重试。
            #   （第一版就是挂顶层，实测 P1 红而权威里已经有数据。）
            response["result"]["report"] = report
        return response

    def _publish_report_after(self, command, response):
        """结案 → 渲染 → 落盘 → 把 report 写回权威。**永不抛。**

        返回
          None                    没做（非结案 / 未装配）
          {"ok": False, ...}      做了但失败（原因可见）
          {"ok": True, ...}       成功

        ## 为什么失败也要返回一个明确的对象

        「报告没出来」有五种完全不同的原因（node 缺失 / 渲染器拒了 / IR 缺字段 /
        落盘冲突 / 权威写入失败），把五种压成一个「报告字段是空的」，
        下一次排障要从头再查一遍。这里每一种都带 `detail`。
        """
        # T-317c：rejudge_apply（重审后的新报告）走同一条发布链。
        if command.get("command") not in ("submit_review", "rejudge_apply"):
            return None
        if self.report_store is None or self.report_bridge is None:
            # 未装配：**不返回失败**。开发装配与所有既有验证器都走这条路，
            # 返回 {"ok": False} 会让它们凭空多出一个字段去断言。
            return None

        case_id = command.get("aggregate_id")
        # ★ 从**权威 state** 取，不从 `response["result"]` 取。
        #
        #   `public_case()` 是给 API 客户端的对外视图，它不含 `report_snapshot`
        #   （那是渲染入参，不是案件字段）。第一版从 result 里取，于是
        #   snapshot 永远是 None，发布钩子静默不做事 —— 而结案仍然成功，
        #   日志里只有一句「没有报告」。**这类静默分支必须靠 state 这一侧对齐。**
        case_state = self.authority.state(case_id)
        snapshot = case_state.get("report_snapshot")
        if not isinstance(snapshot, dict):
            return {"ok": False, "detail": "no_snapshot",
                    "hint": "判定时未产出 report_snapshot（T-316b 断链）"}
        rendered = self.report_bridge.render(snapshot)
        if not rendered.get("ok"):
            return {"ok": False, "detail": rendered.get("detail") or "render_failed",
                    "errors": rendered.get("errors") or []}

        markdown = rendered["markdown"]
        ir = snapshot.get("ir") or {}

        def render_fn(_ir, _text=markdown):
            # ★ ReportStore 的契约是 `render_fn(ir)`；我们手里已经有渲染结果了。
            #   这里**不重新渲染** —— 重渲染会让「持久化的正文」与
            #   「ReportStore 校验过的正文」变成两次调用，中间任何不确定性
            #   （时间戳、随机 id）都会让 `_check_r1` 判成不一致。
            return _text

        # ★ `assigned` 必须记**结案人**（这条命令的 actor），不能取
        #   `case_state["assignee"]`。
        #
        #   原因：`submit_review` 那条命令会把 `state["assignee"]` 清空
        #   （结案后不再有人持有该案）。于是发布这一刻 `case_state["assignee"]`
        #   已经是 None，`assigned` 落成 `[]` —— 而 `can_read_content` 对
        #   dp3/dp4 要求「在 assigned 里或 actionable」，两条都不成立，
        #   **结案人读不到自己刚结案的报告**。
        #
        #   实测：`verify_report_publishing.py` 的 P6c 就是这么红的。
        #   那不是判据错，是实现把 ACL 建立在一个「此刻恰好为空」的字段上。
        closer = (command.get("actor") or {}).get("principal_id")
        acl = {
            "tenant": case_state.get("tenant"),
            "product_line": case_state.get("product_line"),
            "submitter_id": case_state.get("submitter_id"),
            "assigned": [closer] if closer else [],
        }
        try:
            published = self.report_store.publish(ir, render_fn, acl)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False,
                    "detail": "publish_raised:%s" % type(exc).__name__}
        if not published.get("ok"):
            return {"ok": False, "detail": published.get("detail") or "publish_failed"}

        # ★ `publish()` 的返回里**没有** source_ir_fingerprint / created_at ——
        #   它们只在 index.jsonl 的那条记录里。不去改 ReportStore 的返回形状
        #   （它被 30+ 条既有断言约束），而是从**索引里取那一条**：
        #   索引才是「这份报告是谁、什么时候、依据哪个 IR」的唯一权威。
        #
        # ★ 取不到就判失败，不编一个默认值。缺指纹的报告在重建时无法证明
        #   「重建结果与当初发的是同一份」，那时没有任何断言会红。
        indexed = None
        try:
            idx = self.report_store.read_index()
            indexed = next((r for r in idx.get("records") or []
                            if r.get("report_id") == published["report_id"]), None)
        except Exception:  # noqa: BLE001
            indexed = None
        if not isinstance(indexed, dict):
            return {"ok": False, "detail": "index_record_missing",
                    "report_id": published.get("report_id"),
                    "file_persisted": True}
        record = {
            "report_id": published["report_id"],
            "url": published["url"],
            "path": published["path"],
            "sha256": published["sha256"],
            "source_ir_id": indexed.get("source_ir_id"),
            "source_ir_version": indexed.get("source_ir_version"),
            "source_ir_fingerprint": indexed.get("source_ir_fingerprint"),
            "created_at": indexed.get("created_at"),
            "renderer": "report_render.mjs@v1",
        }
        # ── 回写权威 ──────────────────────────────────────────────────
        #
        # ★ 报告**先落盘、后进权威**，顺序不许反：
        #   反过来的话，权威里有一条指向不存在文件的报告 —— 那是「真话说早了」。
        #   现在的顺序里最坏情况是「文件在、权威没有」：`report_store.read()`
        #   仍能按 report_id 打开它，下一次结案重放会幂等地把权威补上。
        #
        # ★ 幂等键用 report_id 派生：同一份报告重放不会产生第二条命令。
        #   不用 uuid —— 那会让每次重试都变成一条新命令。
        try:
            committed = self.authority.execute(
                aggregate_id=case_id,
                command="report_publish",
                actor={"principal_id": command.get("actor", {}).get("principal_id")
                       or "system", "tenant_id": command.get("actor", {}).get("tenant_id")
                       or case_state.get("tenant") or ""},
                expected_version=None,
                payload=record,
                idempotency_key="report:" + record["report_id"],
            )
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or type(exc).__name__
            return {"ok": False, "detail": "authority_write_failed:%s" % code,
                    "report_id": record["report_id"], "url": record["url"],
                    "file_persisted": True}
        try:
            Projector(self.authority, self.projection).catch_up()
        except Exception:
            # 投影落后不是发布失败：`GET /reports` 先读权威。
            pass
        return {"ok": True, "report_id": record["report_id"],
                "url": record["url"], "path": record["path"],
                "sha256": record["sha256"],
                "duplicate": bool(published.get("duplicate")),
                "restored": bool(published.get("restored")),
                "authority_seq": committed["batch"]["authority_seq"],
                "replayed": bool(committed.get("replayed"))}

    def _respond(self, batch, replayed):
        """权威已提交后的统一响应：投影追平成功 200，失败 202（不回滚权威）。"""
        try:
            # 不只 apply 当前批：前一次临时失败后，同 key 重试也应补齐所有缺批。
            Projector(self.authority, self.projection).catch_up()
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            try:
                self.projection.mark_error(code)
            except Exception:
                pass
            return {
                "http_status": 202,
                "projection_lag": True,
                "authority_snapshot": {
                    "command_id": batch["command_id"],
                    "authority_seq": batch["authority_seq"],
                    "aggregate_id": batch["aggregate_id"],
                    "result_version": batch["result_version"],
                    "manifest_sha256": batch["manifest_sha256"],
                },
                "reconcile_token": batch["reconcile_token"],
                "result": copy.deepcopy(batch["result"]),
                "replayed": replayed,
                "error_code": "projection_lag",
            }
        return {
            "http_status": 200,
            "projection_lag": False,
            "authority_snapshot": {
                "command_id": batch["command_id"],
                "authority_seq": batch["authority_seq"],
                "aggregate_id": batch["aggregate_id"],
                "result_version": batch["result_version"],
                "manifest_sha256": batch["manifest_sha256"],
            },
            "reconcile_token": batch["reconcile_token"],
            "result": copy.deepcopy(batch["result"]),
            "replayed": replayed,
        }

    def execute_submission(self, *, ingestor, submission, principal,
                           idempotency_key):
        """内容入库：先按输入哈希查幂等，命中直接回放；未命中才判定+提交。

        判定在 authority 提交之前同步完成；失败不会留下「有案件、无判定」的残件。
        整个过程在本进程锁内，避免并发同 key 时两个请求都判定、其中一个被
        authority 的 payload 哈希误判成 idempotency_conflict。
        """
        with self._lock:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise AuthorityConflict("idempotency_key_missing", "Idempotency-Key 必填")
            principal_id = (principal or {}).get("id")
            tenant = (principal or {}).get("tenant")
            if not all(isinstance(v, str) and v.strip()
                       for v in (principal_id, tenant)):
                raise AuthorityConflict("actor_missing", "principal id/tenant 必填")
            actor = {"principal_id": principal_id.strip(), "tenant_id": tenant.strip()}
            # ★ T-455：**在算幂等哈希之前**补 content_stage。
            #   `submission_hash()` 的 body 里含 `content_stage`，而下面的
            #   `prepare()` 也会补同一个值。若只在 `prepare()` 里补：
            #     重放时 service 侧算的哈希（原始，缺 stage）
            #     ≠ payload 里存的哈希（已补 stage）
            #   → 同 key 重放被误判成 `idempotency_conflict`（实测确认过）。
            #   所以补值必须发生在这里，且与 prepare() 走**同一个**函数。
            from base.submission_service import apply_stage_inference
            submission, _stage_inference = apply_stage_inference(submission)
            incoming = ingestor.submission_hash(submission, principal=principal)
            existing = self.authority.idempotent(actor, idempotency_key)
            if existing is not None:
                events = existing.get("events") or [{}]
                state = events[0].get("state") if isinstance(events[0], dict) else {}
                if (state or {}).get("submission_hash") != incoming:
                    raise AuthorityConflict(
                        "idempotency_conflict",
                        "同 key 已绑定不同的 submission")
                return self._respond(existing, True)
            # ★ 把上面那次推断传下去 —— 否则 prepare() 会把补上的值
            #   当成「调用方申报的」（status=absent），推断记录就丢了。
            prepared = ingestor.prepare(
                submission, principal=principal,
                known_inference=_stage_inference)
            committed = self.authority.execute(
                aggregate_id=prepared["case_id"], command="ingest_submission",
                actor=actor, expected_version=0, payload=prepared["payload"],
                idempotency_key=idempotency_key)
            return self._respond(committed["batch"], committed["replayed"])

    def reconcile(self):
        with self._lock:
            Projector(self.authority, self.projection).catch_up()
            return self.projection.status(self.authority.head())

    def emit_notification(self, *, tenant, recipient, ntype, dedup_key,
                          related_case_id=None, payload=None,
                          idempotency_key, actor_id="system"):
        """通知 emit 进权威（T-313c）。**永不抛**。

        返回 {"ok": True, "notification_id": ..., "replayed": ...} 或
        {"ok": False, "detail": ...} —— 失败可见、不压成一个空字段
        （与 _publish_report_after 同一条纪律：通知失败不许拖垮触发它的主命令）。
        幂等键由调用方给稳定串（触发点 + 对象 + 版本）。
        """
        try:
            committed = self.execute(
                aggregate_id="notifications:%s:%s" % (tenant, recipient),
                command="notification_emit",
                actor={"principal_id": actor_id, "tenant_id": tenant},
                expected_version=None,
                payload={"type": ntype, "dedup_key": dedup_key,
                         "related_case_id": related_case_id,
                         "payload": payload or {}},
                idempotency_key=idempotency_key)
            return {"ok": True,
                    "notification_id": (committed["result"].get("notification")
                                        or {}).get("notification_id"),
                    "replayed": committed["replayed"]}
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", "")
            return {"ok": False,
                    "detail": "%s: %s" % (type(exc).__name__,
                                          code or exc)}

    def _emit_notifications(self, command, before):
        """三个触发点的通知产出（T-313c）。**永不抛**。

        | 触发 | 收件人 | 类型 | 幂等键 |
        |---|---|---|---|
        | expire_lease / unclaim | 被释放的 assignee | lease_released | notify:{cmd}:{case}:{version} |
        | reassign（案件转交） | 被转走的人 | lease_released | 同上 |
        | takedown_create / transition(reassign) | 任务 assignee | takedown | notify:{cmd}:{task}:{version} |
        飞书通道刻意不接（票面判据「飞书调用次数 = 0」的反向对照）。
        """
        try:
            cmd = command.get("command")
            cid = command.get("aggregate_id")
            if before is None or not isinstance(before, dict):
                return
            tenant = before.get("tenant")
            if not tenant:
                return
            if cmd in ("expire_lease", "unclaim", "reassign"):
                who = before.get("assignee")
                if not who:
                    return
                new_assignee = (command.get("payload") or {}).get("assignee")
                if cmd == "reassign" and who == new_assignee:
                    return
                self.emit_notification(
                    tenant=tenant, recipient=who, ntype="lease_released",
                    dedup_key="%s:%s" % (cid, before.get("version")),
                    related_case_id=cid,
                    payload={"reason": cmd},
                    idempotency_key="notify:%s:%s:%s"
                    % (cmd, cid, before.get("version")))
                return
            # takedown_create / takedown_transition：指派与改派通知任务 assignee。
            payload = command.get("payload") or {}
            if cmd == "takedown_transition" \
                    and payload.get("action") not in (None, "reassign"):
                return
            who = payload.get("assignee")
            task_ref = payload.get("task_id") or cid
            if not who:
                return
            self.emit_notification(
                tenant=tenant, recipient=who, ntype="takedown",
                dedup_key="%s:%s:%s" % (task_ref, payload.get("action") or "create",
                                        before.get("version")),
                related_case_id=cid,
                payload={"task_id": task_ref, "action": payload.get("action")},
                idempotency_key="notify:%s:%s:%s"
                % (cmd, task_ref, before.get("version")))
        except Exception:  # noqa: BLE001
            return

    def invalidate_if_due(self, case_id, *, now=None):
        """失效检测（T-317c）：signed 案件的当前外部绑定 vs 签名绑定。

        ★ external_binding_provider 未装配时返回 None —— 那是「未测」，
          不是「没有失效」；production 在 start() 里接真身（规则表 +
          KB 快照的当前值）。「无变化」是常态，静默返回 None。
        """
        if self.external_binding_provider is None:
            return None
        with self._lock:
            state = self.authority.state(case_id)
            if (state.get("release") or {}).get("status") != "signed":
                return None
            current = self.external_binding_provider()
            if not isinstance(current, dict):
                return None
            try:
                return self.execute(
                    aggregate_id=case_id, command="release_invalidate",
                    actor={"principal_id": "release-sweeper",
                           "tenant_id": "system"},
                    expected_version=state["version"],
                    payload={"current": current},
                    idempotency_key="release-invalidate:%s:%s"
                    % (case_id, state["version"]), now=now)
            except Exception as exc:  # noqa: BLE001
                if getattr(exc, "code", "") == "nothing_to_reaudit":
                    return None
                raise

    def run_reaudit(self, case_id, *, now=None):
        """重审执行体（T-317c）：job start → **锁外**真重判 → rejudge_apply →
        complete。重判（judge_unit，可达秒级）留在这把锁里 = 一次下游
        副作用变成全局写停顿（报告渲染 30s 的同一条教训）。
        """
        import time as _time
        state = self.authority.state(case_id)
        if (state.get("release") or {}).get("status") != "signed":
            raise InvalidTransition("只有 signed 案件可重审")
        if self.rejudge_fn is None:
            raise AuthorityConflict(
                "reaudit_unwired", "rejudge_fn 未装配（T-317c）")
        with self._lock:
            st = self.authority.state(case_id)
            started = self.execute(
                aggregate_id=case_id, command="release_job_start",
                actor={"principal_id": "release-sweeper",
                       "tenant_id": "system"},
                expected_version=st["version"], payload={},
                idempotency_key="reaudit-start:%s:%s"
                % (case_id, st["version"]), now=now)
        prev_ir_id = (self.authority.state(case_id).get("ir")
                      or {}).get("ir_id")
        judged = self.rejudge_fn(self.authority.state(case_id))
        if not isinstance(judged, dict) or not isinstance(
                judged.get("ir"), dict):
            return {"ok": False, "detail": "rejudge_bad_output"}
        with self._lock:
            st2 = self.authority.state(case_id)
            applied = self.execute(
                aggregate_id=case_id, command="rejudge_apply",
                actor={"principal_id": "release-sweeper",
                       "tenant_id": "system"},
                expected_version=st2["version"],
                payload={**judged, "expected_prev_ir_id": prev_ir_id},
                idempotency_key="reaudit-apply:%s:%s" % (case_id, prev_ir_id),
                now=now)
            # ★ complete 的版本**现场重读**：rejudge_apply 之后发布钩子可能
            #   又追加了一条 report_publish —— 闭着眼睛 +1 会 version_conflict。
            done = self.execute(
                aggregate_id=case_id, command="release_job_complete",
                actor={"principal_id": "release-sweeper",
                       "tenant_id": "system"},
                expected_version=self.authority.state(case_id)["version"],
                payload={},
                idempotency_key="reaudit-done:%s:%s"
                % (case_id, prev_ir_id), now=now)
        return {"ok": True, "started": started["result"],
                "applied": applied["result"], "done": done["result"]}

    def notification_read(self, *, principal, notification_id,
                          idempotency_key):
        """已读进权威（T-313d）：聚合 = 当前 principal 自己的收件箱。"""
        tenant = (principal or {}).get("tenant")
        pid = (principal or {}).get("id")
        if not all(isinstance(v, str) and v.strip()
                   for v in (tenant, pid, notification_id or "")):
            raise AuthorityConflict("actor_missing",
                                    "principal/tenant/notification_id 必填")
        return self.execute(
            aggregate_id="notifications:%s:%s" % (tenant, pid),
            command="notification_read",
            actor={"principal_id": pid, "tenant_id": tenant},
            expected_version=None,
            payload={"notification_id": notification_id},
            idempotency_key=idempotency_key)

    def notification_ack(self, *, principal, notification_id,
                         idempotency_key):
        """已确认进权威（T-313d）；ack 前置 read 由 reducer 判。"""
        tenant = (principal or {}).get("tenant")
        pid = (principal or {}).get("id")
        if not all(isinstance(v, str) and v.strip()
                   for v in (tenant, pid, notification_id or "")):
            raise AuthorityConflict("actor_missing",
                                    "principal/tenant/notification_id 必填")
        return self.execute(
            aggregate_id="notifications:%s:%s" % (tenant, pid),
            command="notification_ack",
            actor={"principal_id": pid, "tenant_id": tenant},
            expected_version=None,
            payload={"notification_id": notification_id},
            idempotency_key=idempotency_key)

    def release_decision(self, *, aggregate_id, principal, action, token,
                         nonce, reason, step_up_consumer, idempotency_key,
                         now=None):
        """签发/驳回/撤回进权威（T-310c）。

        ① 读权威 state → ② SoD/能力校验 → ③ 消费 step-up → ④ 构造签名 →
        ⑤ authority.execute。

        ★ 顺序不能换，两段各自有理由：
          ③ 必须在 ② **之后** —— 顺序反了，一个没有 release.sign 的人
            也能烧掉别人的 step-up token（拒绝服务）；
          ③ 必须在 ⑤ **之前** —— 先消费后提交：权限之外任何一步失败，
            token 已烧、权威未动（P3 的判据「失败不落案」）。

        判定函数与开发装配是**同一份** ReleaseGate._authorize / _binding /
        validate_signature —— 两条分支不是两套逻辑，只是状态落点不同
        （开发装配落在内存 gate._cases，生产落在权威 state["release"]）。
        读代码的人不要在这里找第二套判定。

        step_up_consumer(principal, state, action, token, nonce) -> ref：
        由 API 层注入（它持有 runtime 的 session store）；service 不持有
        session —— 与 reducer 不消费 step-up 是同一条分工。

        ## 签名的构造位置

        gate.sign 在内存里构造签名；这里在服务层构造（reducer 只校验不构造，
        —— reducer 是纯函数，构造需要 step-up ref 与当前时间）。字段集与
        gate.sign 逐字段一致（含 sid 的哈希输入），唯一来源是本方法。
        """
        import time
        if action not in ("sign", "reject", "revoke"):
            raise ValueError("action 必须是 sign/reject/revoke")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise AuthorityConflict("idempotency_key_missing", "Idempotency-Key 必填")
        principal_id = (principal or {}).get("id")
        tenant = (principal or {}).get("tenant")
        if not all(isinstance(v, str) and v.strip() for v in (principal_id, tenant)):
            raise AuthorityConflict("actor_missing", "principal id/tenant 必填")
        actor = {"principal_id": principal_id.strip(), "tenant_id": tenant.strip()}
        state = self.authority.state(aggregate_id)
        if not isinstance(state, dict) or not state.get("case_id"):
            raise InvalidTransition("案件不存在或未入库：%r" % (aggregate_id,))

        gate = ReleaseGate(sessions=None)  # 只用它的判定函数，不落状态
        if action == "revoke":
            release = state.get("release")
            if (release or {}).get("status") != "signed":
                raise InvalidTransition(
                    "只有 signed 可撤回，当前 %r" % (release or {}).get("status"))
            gate._authorize(state, principal, "revoke")            # ②
            step_up_ref = step_up_consumer(principal, state,        # ③
                                           "revoke", token, nonce)
            committed = self.execute(                               # ⑤
                aggregate_id=aggregate_id, command="release_revoke",
                actor=actor, expected_version=state["version"],
                payload={"reason": reason or "", "step_up_ref": step_up_ref},
                idempotency_key=idempotency_key, now=now)
            return committed

        if state.get("status") != "closed":
            raise InvalidTransition(
                "未结案不许签发，当前案件状态 %r" % state.get("status"))
        release = state.get("release")
        if release is not None and release.get("status") != "pending_release":
            raise InvalidTransition(
                "只有 pending_release 可签发，当前 %r" % release.get("status"))
        gate._authorize(state, principal, "sign")                   # ②
        # ②'（T-315b）：人级名单 —— 角色与 SoD 之外还要被 release.sign
        # 名单点名（生产名单源读投影 approved grants；撤权后自动出局）。
        # 判定留 rbac（单一授权真相），gate 不加名单分支。
        if not rbac.can_sign_release(principal):
            raise SoDViolation("未被 release.sign 名单点名（T-315b）")
        step_up_action = "reject" if action == "reject" else "sign"
        step_up_ref = step_up_consumer(principal, state,            # ③
                                       step_up_action, token, nonce)
        decision = "rejected" if action == "reject" else "signed"
        signatures = (release or {}).get("signatures") or []
        timestamp = time.time() if now is None else float(now)
        sid = "sig-" + _sha(_canonical({
            "case_id": state["case_id"], "case_version": state["version"],
            "signed_at": timestamp, "nonce": nonce, "n": len(signatures),
        }))[:16]
        sig = dict(_binding(binding_from_state(state)))             # ④
        sig.update({
            "signature_id": sid,
            "signature_version": SIGNATURE_VERSION,
            "signer_id": principal_id,
            "signed_at": str(timestamp),
            "step_up_ref": step_up_ref,
            "decision": decision,
            "reason": reason or "",
            "derived_from": (signatures[-1]["signature_id"]
                             if signatures else None),
        })
        sig["signature_hash"] = signature_hash(sig)
        errs = validate_signature(sig)
        if errs:
            raise SignatureError("签名不合法：%s" % "; ".join(errs))
        return self.execute(                                        # ⑤
            aggregate_id=aggregate_id,
            command="release_sign" if decision == "signed" else "release_reject",
            actor=actor, expected_version=state["version"],
            payload={"signature": sig},
            idempotency_key=idempotency_key, now=now)

    def expire_if_due(self, aggregate_id, *, now=None,
                      actor_id="lease-sweeper"):
        with self._lock:
            state = self.authority.state(aggregate_id)
            lease_expires = state.get("lease_expires")
            if state.get("status") != "claimed" or lease_expires is None:
                return None
            import time
            current = time.time() if now is None else float(now)
            if current <= float(lease_expires):
                return None
            return self.execute(
                aggregate_id=aggregate_id, command="expire_lease",
                actor={"principal_id": actor_id, "tenant_id": "system"},
                expected_version=state["version"], payload={},
                idempotency_key="lease-expire:%s:%s" %
                (aggregate_id, state["version"]), now=current)

    def find_appeal_case(self, appeal_id, *, tenant):
        """appeal_id -> case_id；找不到返回 None。

        ## 为什么这个方法在服务层而不是 API 层

        `api/write_api.py` 有一条硬约束（C5）：「API 层不计算 state/decision」。
        按 appeal_id 反查所属案件需要读权威状态，那属于服务层。
        API 只拿结果，不碰 state —— 这样 C5 那条扫描继续成立。

        ## 为什么是线性扫

        申诉存在案件 aggregate 里，没有 appeal_id 的二级索引。
        规模是「本租户案件数」，当前可接受。**若案件上千，需要一条索引**——
        这条记在 T-311c 的票里，不在这里悄悄加缓存（缓存会与权威不一致）。
        """
        for case_id in self.authority.aggregate_ids():
            current = self.authority.state(case_id)
            if current.get("tenant") != tenant:
                continue
            for item in current.get("appeals") or []:
                if item.get("appeal_id") == appeal_id:
                    return case_id
        return None

    def mark_appeals_stale(self, *, now=None, days=30):
        """把「暂停超过 days 天」的申诉转成 stale。**扫全部案件。**

        ## 这是 `AppealStore.mark_stale()` 的第一个生产触发点

        T-311 施工单 §一 第 4 条：`mark_stale` 在全仓只有
        `tools/verify_write_api.py` 调过一次 —— **生产里 0 调用**。
        一条没有触发点的规则等于没有规则（AGENTS.md §2.4.2）。

        调用点必须挂在 `ProductionRuntime.maintain_once()`
        （30 秒一次的心跳），**不许挂在 `GET /appeals`**：
        读端点写状态会让「打开列表」变成一次写操作，且并发下会撞版本。

        ## 为什么返回计数而不是抛错

        stale 是「到期自动发生」的事，没有 open/paused 的申诉也完全正常。
        抛错会让每分钟的心跳变成一次错误日志噪音，而真正的故障
        （authority 写不进）会被淹掉。

        ## 每个 aggregate 单独 try

        一个案件的 stale 迁移失败（版本冲突等）不该阻断其余案件。
        失败的记进 errors，由调用方打日志；**不吞掉、也不上浮成整轮失败**。
        """
        import time

        stamp = time.time() if now is None else float(now)
        applied, errors = 0, []
        for aggregate_id in self.authority.aggregate_ids():
            with self._lock:
                state = self.authority.state(aggregate_id)
                if not any(a.get("state") == "paused_version_invalidated"
                           for a in state.get("appeals") or []):
                    continue
                try:
                    outcome = self.execute(
                        aggregate_id=aggregate_id, command="appeal_stale",
                        actor={"principal_id": "appeal-sweeper",
                               "tenant_id": state.get("tenant") or "system"},
                        expected_version=state["version"],
                        payload={"days": int(days)},
                        idempotency_key="appeal-stale:%s:%s" % (
                            aggregate_id, state["version"]),
                        now=stamp)
                except Exception as exc:  # noqa: BLE001
                    errors.append((aggregate_id,
                                   getattr(exc, "code", type(exc).__name__)))
                    continue
                staled = (outcome.get("result") or {}).get("staled") or []
                if staled:
                    applied += len(staled)
        return {"staled": applied, "errors": errors, "at": stamp}

    def list_published_reports(self):
        """所有带报告的案件状态（只读快照列表）。**不做 ACL。**

        ## 为什么这个方法在服务层

        `api/review_api.py` 有一条硬约束（C5）：「API 层不计算 state/decision」。
        第一版我在路由里直接 `state = service.authority.state(case_id)`，
        被 C5 的扫描器抓到。那条约束是对的：API 只编排、不碰状态。
        所以「按案件扫一遍找报告」留在服务层，API 只拿 list 再判 ACL。

        ## 为什么不在这里判 ACL

        ACL 需要 `can_read_content(principal, case)`，而 principal 是 API 层的东西。
        服务层不认识 HTTP 身份。**分工：服务层给数据，API 层判可见性。**
        """
        out = []
        for aggregate_id in self.authority.aggregate_ids():
            current = self.authority.state(aggregate_id)
            record = current.get("report")
            if not isinstance(record, dict):
                continue
            row = copy.deepcopy(record)
            row["case_id"] = current.get("case_id")
            row.setdefault("ir_id", record.get("source_ir_id"))
            # 判 ACL 需要的四个字段，随行带出 —— 再查一次 authority 会多一次 IO，
            # 且两次读之间可能变（结案后 assignee 会被清空）。
            row["_tenant"] = current.get("tenant")
            row["_product_line"] = current.get("product_line")
            row["_submitter_id"] = current.get("submitter_id")
            row["_assignee"] = current.get("assignee")
            out.append(row)
        return out

    def list_appeals(self, *, tenant=None):
        """该租户的全部申诉（跨案件聚合，只读）。**不做 ACL。**

        ## 为什么必须有这个方法（T-401a）

        `GET /api/v1/appeals` 改前只读 frozen `appeals.json`，而那个文件
        **盘上不存在** —— 于是它恒返 `[]`。后果不是「慢」，是**写完读不回**：
        `POST /api/v1/appeals` 返回 200、权威里确实有那条，而前端 P-06
        的列表永远是空的。这与 T-314c（名单）、T-316d（报告）是**同一个形状**，
        那两处已经修好（`review_api.py:732` / `:915` 有注释），唯独申诉漏了。

        ## 为什么按 aggregate 扫而不是按 appeal_id 索引

        申诉存在案件 aggregate 的 `state["appeals"]` 里，没有独立表。
        规模是「本租户案件数」，与 `list_published_reports` 同一个量级，
        同样的线性扫；T-311c 已记「上千案件需要索引」，不在这里悄悄加缓存
        （缓存会与权威不一致）。

        ## 为什么 tenant 是可选参数

        `None` = 不筛（服务层不认识 HTTP 身份）。**API 层必须显式传 tenant**
        —— 不传就是「把全部租户的申诉发给任何登录用户」，而那正是 TS-30 禁止的。
        这里不设默认为「全部」的便利写法：默认值本身就是一次授权决定。
        """
        out = []
        for aggregate_id in self.authority.aggregate_ids():
            current = self.authority.state(aggregate_id)
            rows = current.get("appeals")
            if not isinstance(rows, list):
                continue
            for item in rows:
                if not isinstance(item, dict):
                    continue
                if tenant is not None and item.get("tenant") != tenant:
                    continue
                row = copy.deepcopy(item)
                # 案件侧字段随行带出：前端申诉列表要显示「这条申诉是哪个案件」。
                row.setdefault("case_id", current.get("case_id"))
                row["_product_line"] = current.get("product_line")
                row["_submitter_id"] = current.get("submitter_id")
                row["_assignee"] = current.get("assignee")
                out.append(row)
        # 最近打开的在前 —— 与「先看到刚发生的事」一致；同刻用 appeal_id 定序，
        # 避免 Python 排序在同一时间戳上给出不稳定顺序（翻页时会重复/漏项）。
        out.sort(key=lambda r: (str(r.get("opened_at") or ""),
                                str(r.get("appeal_id") or "")), reverse=True)
        return out

    def read_your_write(self, reconcile_token, *, aggregate_id=None,
                        principal_id=None, tenant_id=None):
        if not isinstance(reconcile_token, str) or not reconcile_token:
            return None
        for batch in self.authority.batches():
            if batch.get("reconcile_token") != reconcile_token:
                continue
            actor = batch.get("actor") or {}
            if aggregate_id is not None and batch.get("aggregate_id") != aggregate_id:
                return None
            if principal_id is not None and actor.get("principal_id") != principal_id:
                return None
            if tenant_id is not None and actor.get("tenant_id") != tenant_id:
                return None
            return {
                "authority_snapshot": {
                    "command_id": batch["command_id"],
                    "authority_seq": batch["authority_seq"],
                    "aggregate_id": batch["aggregate_id"],
                    "result_version": batch["result_version"],
                    "manifest_sha256": batch["manifest_sha256"],
                },
                "result": copy.deepcopy(batch["result"]),
            }
        return None
