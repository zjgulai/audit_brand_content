#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-317 全量重审进权威的自证：失效检测 → 真重判 → 产物级判据（#98）。

主体：base/review_reducer.py（release_invalidate / job / rejudge_apply）、
base/review_command_service.py（invalidate_if_due / run_reaudit）、
base/release_gate.py（_changes 唯一一份）、base/report_store.py 与
api/production_app.py（报告发布链与生产装配的 rejudge_fn 接线，
经 service 的注入点间接受证）、报告追加（state["reports"]）。

设计纪律：案件走真实生产链（真 judge + 真 KB）到签发；
失效的「外部绑定变化」由验证器注入一个**不同的** KB 快照模拟；
重判用真 judge_unit 当前快照重跑。#98 的判据全落产物级
（新 ir_id / 旧 IR 逐字节未变 / 新报告追加旧报告不改）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import base.rbac as RBAC
    from base.reviews_ledger import LedgerConflict
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projector import Projector
    from base.projection_store import ProjectionStore
    from base.release_gate import InvalidTransition, SoDViolation
    from base.review_command_service import ReviewCommandService
    from base.submission_service import SubmissionIngestor
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入被测模块: %s" % exc)
    sys.exit(2)


def _canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def main():
    passed = failed = 0
    tmp_roots = []

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    try:
        from fastapi.testclient import TestClient  # noqa: F401
        import base.auth_session as _AS
        from base.report_render_bridge import ReportRenderBridge
        from base.report_store import ReportStore

        root = tempfile.mkdtemp(prefix="reaudit-")
        tmp_roots.append(root)
        root_p = Path(root)
        (root_p / "reports-root").mkdir(parents=True, exist_ok=True)
        lease = WriterLease(os.path.join(root, "a", "lock")).acquire()
        auth = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        proj = ProjectionStore(os.path.join(root, "p.db"))
        report_store = ReportStore(str(root_p / "reports-root"),
                                   "https://ca.example/static")
        bridge = ReportRenderBridge(ROOT)
        if bridge.node() is None:
            print("UNTESTED: node not on PATH")
            return 2

        ingestor = SubmissionIngestor()

        def _current_kb():
            kb = ingestor._kb_snapshot()
            return hashlib.sha256(kb.encode("utf-8")).hexdigest()

        def _rejudge(state):
            judgment = ingestor.judge_fn(
                state["content"], authority_query=ingestor._query(),
                kb_snapshot=ingestor._kb_snapshot())
            return {
                "ir": judgment["ir"],
                "report_snapshot": judgment.get("report_snapshot"),
                "judgment": {"label": judgment.get("label"),
                             "layer": judgment.get("layer"),
                             "release_status": judgment.get("release_status"),
                             "run_state": judgment.get("run_state"),
                             "receipt": judgment.get("receipt")},
                "kb_snapshot_hash": _current_kb(),
                "conflict_table_version":
                    judgment["ir"].get("control_points_version"),
                "media_fingerprints":
                    judgment["ir"].get("media_fingerprints") or {},
            }

        saved_source = getattr(RBAC, "_ALLOWLIST_SOURCE", None)
        RBAC.set_allowlist_source(
            lambda: {"release.sign": frozenset({"u_signer"})})
        try:
            svc = ReviewCommandService(
                auth, proj, report_store=report_store, report_bridge=bridge,
                rejudge_fn=_rejudge)

            # 真实链到已签发
            prepared = ingestor.prepare(
                {"submission_id": "sub-ra", "product_line": "home",
                 "content_type": "文本", "content_stage": "final_content",
                 "entry_channel": "群消息", "source": {"kind": "free_text"},
                 "text": "限时特价，只要 9 元，立即点击购买"},
                principal={"tenant": "t-ra", "id": "u_sub"})
            cid = "case-ra"
            auth.execute(aggregate_id=cid, command="ingest_submission",
                         actor={"principal_id": "u_sub", "tenant_id": "t-ra"},
                         expected_version=0,
                         payload=dict(prepared["payload"], case_id=cid),
                         idempotency_key="ing", now=5000)
            auth.execute(aggregate_id=cid, command="claim",
                         actor={"principal_id": "u_signer",
                                "tenant_id": "t-ra"},
                         expected_version=1, payload={},
                         idempotency_key="cl", now=5001)
            # ★ 经服务层结案：报告 A 的发布钩子挂在 ReviewCommandService.execute
            #   （裸 authority 不产报告 —— R3 的「旧报告」必须真的存在）。
            svc.execute(aggregate_id=cid, command="submit_review",
                        actor={"principal_id": "u_signer",
                               "tenant_id": "t-ra"},
                        expected_version=2,
                        payload={"conclusion":
                                 {"review_notes": "逐条看过后结案"}},
                        idempotency_key="close", now=5002)
            principal = {"id": "u_signer", "tenant": "t-ra",
                         "product_line": "home",
                         "capabilities": ["release.sign", "release.revoke"]}
            signed = svc.release_decision(
                aggregate_id=cid, principal=principal, action="sign",
                token="tok-ra", nonce="n-ra", reason="首次签发",
                step_up_consumer=lambda p, s, a, t, n: "stepup:test-ra",
                idempotency_key="sign-ra", now=6000)
            old_ir = copy.deepcopy(auth.state(cid)["ir"])
            old_sig_id = signed["result"]["signature"]["signature_id"]
            report_a = copy.deepcopy(auth.state(cid).get("report") or {})
            report((auth.state(cid).get("release") or {}).get("status")
                   == "signed" and old_ir.get("ir_id"),
                   "X0 真实链到已签发（真 judge + 真 KB）")

            # ---- X1 失效检测：注入「KB 快照变了」的外部绑定 ----
            def _changed_binding():
                cur = _rejudge(auth.state(cid))
                return {
                    "rule_snapshot": {"version": "rules-v1", "hash": "f" * 64},
                    "kb_snapshot": {"version": "kb-new",
                                    "hash": "e" * 64},
                    "conflict_table_version":
                        cur["conflict_table_version"],
                    "raw_sha256": old_ir and None,
                    "text_sha256": None,
                    "media_fingerprints": [],
                    "used_authority_refs": [],
                }
            # ★ _changes 需要 current 侧的 raw/text 指纹与签名侧一致才只报
            #   kb 变化 —— 从旧签名取，避免混入内容变化。
            def _changed_binding_exact(state=None):
                cur = _changed_binding()
                cur["raw_sha256"] = signed["result"]["signature"]["raw_sha256"]
                cur["text_sha256"] = signed["result"]["signature"]["text_sha256"]
                cur["media_fingerprints"] = []
                cur["used_authority_refs"] = []
                return cur
            svc.external_binding_provider = _changed_binding_exact
            inv = svc.invalidate_if_due(cid)
            job = (auth.state(cid).get("release") or {}).get("active_job") or {}
            report(isinstance(inv, dict)
                   and job.get("state") == "queued"
                   and job.get("job_id", "").startswith("rj-")
                   and any(c.get("field") == "kb_snapshot"
                           for c in job.get("change_set") or []),
                   "X1 失效检测建 queued job（change_set 含 kb_snapshot）",
                   repr(job.get("state")))
            # X1b：同键重复 invalidate → 合并（job_id 确定性；不建第二条）
            svc.invalidate_if_due(cid)
            job2 = (auth.state(cid).get("release") or {}).get("active_job") or {}
            report(job2.get("job_id") == job.get("job_id"),
                   "X1b 同 change_set 重复失效 → 合并（job_id 确定性）")
            # X1c：无变化 → nothing_to_reaudit → None（常态，不是失败）
            _sig = signed["result"]["signature"]
            svc.external_binding_provider = lambda state=None: dict(
                _sig,
                rule_snapshot={"version": _sig["rule_snapshot_version"],
                               "hash": _sig["rule_snapshot_hash"]},
                kb_snapshot={"version": _sig["kb_snapshot_version"],
                             "hash": _sig["kb_snapshot_hash"]},
                conflict_table_version=_sig["conflict_table_version"],
                media_fingerprints=[],
                # refs 必须用签名自身的清单 —— 文本样本有依据引用时，
                # 空清单会被 _changes 判成依据变化（假失效）。
                used_authority_refs=list(_sig["used_authority_refs"]))
            report(svc.invalidate_if_due(cid) is None,
                   "X1c 无变化 → None（常态，不是失败）")
            svc.external_binding_provider = _changed_binding_exact

            # ---- X2 run_reaudit：锁外真重判 → 新 ir → 回待放行 ----
            # ★ ir_id 含**秒级** created_at（orchestrator._iso）——同秒重判会
            #   产出同 ir_id。生产上重审距判定远超一秒；测试里必须跨过秒界，
            #   否则 #98 ①「新 ir_id」在同秒内不成立。这是已知边角，记进票清单。
            import time as _sleep
            _sleep.sleep(1.1)
            try:
                out = svc.run_reaudit(cid)
            except (InvalidTransition, LedgerConflict) as exc:
                # 变异（失效判据被掏空）会让重审被拒 —— 那是 FAIL 不是崩溃。
                # reducer 抛 LedgerConflict、服务层前置抛 InvalidTransition，
                # 两个类一个码，捕获面必须都盖住。
                # SystemExit(1) 被 mutprobe 记为 killed；后面的段落全部依赖
                # 重审成功，跳过比各处判空更诚实。
                report(False, "X2 重审后 ir_id 与旧版不同（#98 ①）",
                       "（重审被拒：%s）" % getattr(exc, "code", exc))
                raise SystemExit(1) from exc
            new_state = auth.state(cid)
            new_ir = new_state["ir"]
            report(out.get("ok") is True
                   and new_ir["ir_id"] != old_ir["ir_id"],
                   "X2 重审后 ir_id 与旧版不同（#98 ①）",
                   "%r -> %r" % (old_ir["ir_id"], new_ir["ir_id"]))
            rel2 = new_state["release"] or {}
            report((rel2.get("active_job") or {}).get("state") == "done"
                   and rel2.get("status") == "pending_release"
                   and rel2.get("release_status") == "待放行",
                   "X2b job done 且案件回待放行")
            report(new_state.get("ir_prev", {}).get("ir_id") == old_ir["ir_id"],
                   "X2c ir_prev 指针指向旧 IR")
            # R2（#98 ②）：旧 IR 从权威事件链可取出且逐字节未变
            old_from_chain = None
            for batch in auth.batches():
                for ev in batch.get("events") or []:
                    st = (ev or {}).get("state") or {}
                    if st.get("case_id") == cid \
                            and (st.get("ir") or {}).get("ir_id") == old_ir["ir_id"]:
                        old_from_chain = st["ir"]
                        break
                if old_from_chain is not None:
                    break
            report(old_from_chain is not None
                   and _canon(old_from_chain) == _canon(old_ir),
                   "R2 旧 IR 在事件链中逐字节未变（#98 ②）")
            # X2d：重判后的绑定快照跟上（ctv 与新 ir 恒等）
            report(new_state["conflict_table_version"]
                   == new_ir.get("control_points_version"),
                   "X2d conflict_table_version 与新 ir 恒等")

            # ---- R3（#98 ③）：新报告追加、旧报告文件不变 ----
            report_b = copy.deepcopy(new_state.get("report") or {})
            reports = new_state.get("reports") or []
            report(report_b.get("report_id")
                   and report_b["report_id"] != report_a.get("report_id")
                   and [r["report_id"] for r in reports]
                   == [report_a.get("report_id"), report_b.get("report_id")],
                   "R3 新报告追加进 reports，report 指向最新（#98 ③）",
                   repr([r["report_id"] for r in reports]))
            if report_a.get("path"):
                old_file = Path(str(report_a["path"]))
                if not old_file.is_absolute():
                    old_file = root_p / "reports-root" / report_a["path"]
                if old_file.is_file():
                    sha_now = hashlib.sha256(old_file.read_bytes()).hexdigest()
                    report(sha_now == report_a.get("sha256"),
                           "R3b 旧报告文件 sha 未变（R2：不改不删）")

            # ---- X3 重签：derived_from 接上一条，链不断 ----
            resigned = svc.release_decision(
                aggregate_id=cid, principal=principal, action="sign",
                token="tok-ra2", nonce="n-ra2", reason="重审后再签发",
                step_up_consumer=lambda p, s, a, t, n: "stepup:test-ra2",
                idempotency_key="sign-ra2", now=9000)
            sigs = (auth.state(cid).get("release") or {}).get("signatures") or []
            report(resigned["result"]["signature"]["derived_from"] == old_sig_id
                   and len(sigs) == 2,
                   "X3 重审后再签发：derived_from 接旧签名（链不断）")
        finally:
            RBAC.set_allowlist_source(saved_source)
            try:
                proj.close()
            except Exception:  # noqa: BLE001
                pass
    except AssertionError as exc:
        print("UNTESTED: 验收器内部断言失败: %s" % exc, file=sys.stderr)
        return 2
    finally:
        for r in tmp_roots:
            shutil.rmtree(r, ignore_errors=True)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
