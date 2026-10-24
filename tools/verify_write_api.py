#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_write_api.py — T2-02：review-api 写端点

覆盖：
  C0  claim/unclaim/reassign：接 reviews_ledger；409 冲突；403 越权；Idempotency-Key
  C1  actions：confirm/reject 走 finding_store 新建条目 + derived_from；版本冲突 409
  C2  appeals：open/pause/migrate/withdraw/stale；非原申诉人 migrate → 403
  C3  takedown：start/complete/fail/retry/reassign/waive 接 base/takedown，回填校验
      T-312b：六条路由接能力（execute / waive 两把钥匙 + 改派走 TD-12）、
      complete 落 completed_by（取已认证 principal）、六条进生产能力表。
      实测变异（全部命中）：去掉 require_takedown → 5 红；waive 复用 execute
      → 1 红；改派复用 execute → 2 红；complete 不落 completed_by → 2 红；
      actor 写死 → 1 红；actor 取 task.assignee → 2 红；
      改派不限 coordinator → 2 红；改派完全不判 → 2 红。
  C4  release-decision/revoke → 501「release_gate 未实现」，不得假成功
  C5  静态扫描：API 层不 import 判定实现、不计算 state
  R1  Idempotency-Key 重复请求不得产生第二条
  R2  越权 → 403
  R3  appeal 非原申诉人 migrate → 403
  R4  release 占位返回 200 → 红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from api.review_api import create_app, InMemoryRepository, WRITE_PATHS
    from api.write_api import AppealStore, IMPLEMENTED_WRITE_PATHS
    from api.production_app import PRODUCTION_WRITE_PATHS
    from base.auth_session import SessionStore
    from base.finding_store import FindingStore
    from base.reviews_ledger import ReviewsLedger
    from base import takedown as TD
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入写 API 依赖: %s" % exc)
    sys.exit(2)


def call(app, method, path, cookie=None, key=None, body=None):
    headers = [(b"host", b"testserver")]
    if cookie:
        headers.append((b"cookie", ("session=" + cookie).encode()))
    if key is not None:
        headers.append((b"idempotency-key", key.encode()))
    raw = b""
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": headers,
        "client": ("test", 1234), "server": ("testserver", 80),
        "root_path": "",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in messages
                       if m["type"] == "http.response.body")
    parsed = json.loads(payload.decode("utf-8")) if payload else None
    return start["status"], parsed


def ir(ir_id="ir-1", state="BLOCK"):
    return {
        "ir_id": ir_id, "ir_version": "review-ir-v1",
        "source_ir_version": "cu-1",
        "content_unit_ref": {"unit_id": "cu-1", "kind": "image"},
        "findings": [],
        "decision": {"state": state, "layer": "DP2",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "partial",
                     "modalities_evaluated": ["image"],
                     "rules_version": "rules-v1",
                     "control_points_applied": ["H01"]},
        "receipt_ref": "rc-1", "rule_snapshot": "rs-1",
        "kb_snapshot": "kb-1", "control_points_version": "cp-v1",
        "created_at": "2026-10-19T00:00:00Z",
    }


def release_case(case_id):
    h = "a" * 64
    return {
        "case_id": case_id, "tenant": "t1", "product_line": "pump",
        "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
        "assignee_id": "u_dp3", "actionable": True,
        "ir": ir(case_id + "-ir"),
        "case_version": 1,
        "ir_id": case_id + "-ir", "ir_version": "review-ir-v1",
        "raw_sha256": h, "text_sha256": h,
        "conflict_table_version": "ct-v1",
        "frame_manifest_hash": h, "keyframe_set_hash": h,
        "ocr_output_hash": h, "asr_output_hash": h,
        "model_config_hash": h, "sampling_config_hash": h,
        "rule_snapshot": {"version": "rules-v1", "hash": h},
        "kb_snapshot": {"version": "kb-v1", "hash": h},
        "used_authority_refs": [], "media_fingerprints": [],
    }


# ── --controls（RL-12④ / #100 的反向对照）────────────────────────────────
# 断言函数抽出来给 --controls 复用：好样本（真 AppealStore）绿；
# 坏样本（pause 偷改 reason / open 改写 reason 的桩）必须红。
# 没红过的断言不算验证过它（AGENTS.md §2.4.1）。
RL12_PAUSE_FIELDS = {"state", "pause_reason", "paused_at"}


def assert_pause_field_discipline(report, store, appeal_id, expected_reason):
    """对一次 pause 做逐字段比对：PAUSE_FIELDS 之外一个字段都不许变，
    且 pause_reason 必须逐字等于传入值。"""
    before = store.get(appeal_id)
    paused_rows = store.pause(before["case_id"], now=time.time())
    after = store.get(appeal_id)
    untouched = sorted(
        k for k in set(before) | set(after)
        if k not in RL12_PAUSE_FIELDS and before.get(k) != after.get(k))
    report(not untouched and set(before) <= set(after),
           "C2/RL-12④ pause 不改写 pause 三字段之外的任何字段",
           "changed=%r" % (untouched,))
    prow = next((x for x in paused_rows
                 if x["appeal_id"] == appeal_id), {})
    report(prow.get("state") == "paused_version_invalidated"
           and prow.get("pause_reason") == expected_reason
           and isinstance(prow.get("paused_at"), str)
           and prow.get("paused_at", "").endswith("Z"),
           "C2/RL-12① pause_reason 必须是调用方传入的那个值",
           "pause_reason=%r expected=%r"
           % (prow.get("pause_reason"), expected_reason))


def run_controls():
    """坏样本必须红；好样本必须绿。返回 0 / 1。"""
    ok_all = True
    print("verify_write_api · --controls（RL-12④ 申诉字段纪律反向对照）")

    def mk_report(tag):
        def report(ok, name, detail=""):
            nonlocal ok_all
            print("  %s [%s] %s%s"
                  % ("✅" if ok else "❌", tag, name,
                     "" if ok else "：%s" % detail))
            if not ok:
                ok_all = False
        return report

    # 好样本：真 AppealStore —— 两条断言都必须绿
    good = AppealStore()
    item = good.open("case-g", "u_a", "误判")
    assert_pause_field_discipline(mk_report("好样本"), good,
                                  item["appeal_id"], "version_invalidated")

    # 坏样本 1（#100 原样变异）：pause 把 reason 写成自选常量
    class BadPauseStore(AppealStore):
        def pause(self, case_id, reason="version_invalidated", now=None):
            rows = super().pause(case_id, reason=reason, now=now)
            for it in self._items.values():
                if it["case_id"] == case_id:
                    it["reason"] = "重审通过，原因待补"   # ← 变异：静默改写
            return rows

    bad1 = BadPauseStore()
    item = bad1.open("case-b1", "u_a", "误判")
    aid = item["appeal_id"]
    before_fails = [False]

    def report1(ok, name, detail=""):
        if "RL-12④" in name and not ok:
            before_fails[0] = True

    assert_pause_field_discipline(report1, bad1, aid, "version_invalidated")
    print("  %s 坏样本 1：pause 静默改写 reason → RL-12④ 红"
          % ("✅" if before_fails[0] else "❌"))
    ok_all = ok_all and before_fails[0]

    # 坏样本 2：pause_reason 被写成别的值（①的值断言红）
    bad2 = AppealStore()
    item = bad2.open("case-b2", "u_a", "误判")

    def bad2_pause(self, case_id, reason="version_invalidated", now=None):
        return AppealStore.pause(self, case_id, reason="已自动关闭", now=now)

    bad2.pause = bad2_pause.__get__(bad2, AppealStore)
    try:
        fails2 = []

        def report2(ok, name, detail=""):
            if "RL-12①" in name and not ok:
                fails2.append(name)

        assert_pause_field_discipline(report2, bad2, item["appeal_id"],
                                      "version_invalidated")
    finally:
        pass
    print("  %s 坏样本 2：pause_reason 换值 → RL-12① 红"
          % ("✅" if fails2 else "❌"))
    ok_all = ok_all and bool(fails2)

    print()
    if ok_all:
        print("✅ --controls 全过：好样本绿；坏样本各自红")
        return 0
    print("❌ --controls 有对照不符")
    return 1


def candidate(fid):
    return {
        "finding_id": fid, "control_code": "H01", "detected_by": "P1",
        "authority_ref": [], "authority_state": "ok", "severity": "L4",
        "status": "candidate", "location": {"bbox": {"x1": 0.1, "y1": 0.2,
                                                       "x2": 0.4, "y2": 0.6}},
        "quote": "原文", "produced_by": "semantic", "derived_from": None,
        "confirmed_by_rule_class": True,
    }


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    cases = [
        {"case_id": "case-1", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-1")},
        {"case_id": "case-2", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_other", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-2")},
        {"case_id": "case-3", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_other", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-3")},
        release_case("case-release"),
        release_case("case-release2"),
        release_case("case-release3"),
        release_case("case-release4"),
    ]
    tasks = [
        TD.new_task(task_id="t-1", case_id="case-1", platform="amazon",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-2", case_id="case-1", platform="tiktok",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-3", case_id="case-1", platform="meta",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-4", case_id="case-1", platform="amazon",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
    ]
    repo = InMemoryRepository(cases=cases, reports=[], takedown_tasks=tasks)
    principals = {
        "u_sub": {"open_id": "ou_u_sub", "tenant_id": "t1",
                  "roles": ["submitter"], "product_lines": ["pump"],
                  "product_line": "pump", "capabilities": ["release.sign"]},
        "u_dp3": {"open_id": "ou_u_dp3", "tenant_id": "t1",
                  "roles": ["coordinator"], "product_lines": ["pump"],
                  "product_line": "pump"},
        "u_it": {"open_id": "ou_u_it", "tenant_id": "t1",
                 "roles": ["it"], "product_lines": ["pump"],
                 "product_line": "pump"},
        "u_signer": {"open_id": "ou_u_signer", "tenant_id": "t1",
                     "roles": ["signer"], "product_lines": ["pump"],
                     "product_line": "pump",
                     "capabilities": ["release.sign", "release.revoke"]},
        # T-312b：下线执行人。**必须是 signer 或持有 takedown.execute 的角色**，
        # 且被点名进人级名单 —— 两条都成立才放行（见 C3c/C3d）。
        "u_exec": {"open_id": "ou_u_exec", "tenant_id": "t1",
                   "roles": ["signer"], "product_lines": ["pump"],
                   "product_line": "pump"},
        # 改派用的统筹：有 coordinator 角色，**没有** takedown.execute（TD-12）
        "u_coord2": {"open_id": "ou_u_coord2", "tenant_id": "t1",
                     "roles": ["coordinator"], "product_lines": ["pump"],
                     "product_line": "pump"},
    }
    store = SessionStore(":memory:")
    sub = store.create_session("u_sub", tenant="t1", now=time.time())
    coord = store.create_session("u_dp3", tenant="t1", now=time.time())
    signer = store.create_session("u_signer", tenant="t1", now=time.time())
    execu = store.create_session("u_exec", tenant="t1", now=time.time())
    fs = FindingStore()
    for fid in ("f-1", "f-2", "f-3"):
        fs.insert(candidate(fid))
    ledger = ReviewsLedger()
    appeals = AppealStore()
    app = create_app(session_store=store, repository=repo,
                     principals=principals, reviews_ledger=ledger,
                     finding_store=fs, appeals=appeals)

    # C0 claim / idempotency / unclaim / reassign
    st, claim = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                     "K-claim-1", {})
    report(st == 200 and claim["version"] == 1,
           "C0 claim 成功", "%s %r" % (st, claim))
    st2, claim2 = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                       "K-claim-1", {})
    claim_events = [e for e in ledger.events() if e["kind"] == "claim"
                    and e["case_id"] == "case-1"]
    report(st2 == 200 and claim2["version"] == claim["version"]
           and len(claim_events) == 1,
           "R1 同 Idempotency-Key 重复 claim 不产生第二条",
           "%s %r events=%d" % (st2, claim2, len(claim_events)))
    st, _ = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                 "K-claim-other", {})
    report(st == 409, "C0 不同 key 重复 claim → 409", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-3/claim", coord, None, {})
    report(st == 400, "C0 缺 Idempotency-Key → 400", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-3/claim", sub,
                 "K-claim-sub", {})
    report(st == 403, "R2 提交人 claim → 403", str(st))

    st, un = call(app, "POST", "/api/v1/cases/case-1/unclaim", coord,
                  "K-unclaim-1", {"version": claim["version"]})
    report(st == 200 and un["status"] == "released"
           and ledger.list_drafts("case-1"),
           "C0 unclaim → released 且 draft 已保存",
           "%s %r" % (st, un))
    st, claim3 = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                      "K-claim-2", {})
    st, reassigned = call(app, "POST", "/api/v1/cases/case-1/reassign", coord,
                          "K-reassign-1", {"version": claim3["version"],
                                           "assignee": "u_dp3b"})
    report(st == 200 and reassigned["assignee"] == "u_dp3b",
           "C0 reassign 成功", "%s %r" % (st, reassigned))

    # C1 actions：confirm 新建条目 + derived_from；版本冲突
    st, claim2 = call(app, "POST", "/api/v1/cases/case-2/claim", coord,
                      "K-claim-case2", {})
    st, act = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                   "K-action-confirm",
                   {"version": claim2["version"], "finding_id": "f-1",
                    "action": "confirm"})
    old = fs.get("f-1")
    report(st == 200 and act["finding"]["status"] == "confirmed"
           and act["finding"]["derived_from"] == "f-1"
           and act["finding"]["finding_id"] != "f-1"
           and old["status"] == "superseded",
           "C1 confirm：新条目 + derived_from，旧条 superseded",
           "%s %r old=%r" % (st, act, old))
    st, _ = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                 "K-action-stale",
                 {"version": 999, "finding_id": "f-2", "action": "confirm"})
    report(st == 409, "C1 版本冲突 → 409", str(st))
    st, rej = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                   "K-action-reject",
                   {"version": claim2["version"], "finding_id": "f-3",
                    "action": "reject"})
    report(st == 200 and rej["finding"]["status"] == "rejected"
           and rej["finding"]["derived_from"] == "f-3",
           "C1 reject：新条目 + derived_from", "%s %r" % (st, rej))

    # C2 appeals：pause / migrate / 非原申诉人 / stale / withdraw
    st, ap = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-1",
                  {"case_id": "case-1", "reason": "误判"})
    report(st == 200 and ap["state"] == "open", "C2 申诉 open", "%s %r" % (st, ap))
    st, _ = call(app, "POST", "/api/v1/appeals/%s/migrate" % ap["appeal_id"],
                 coord, "K-mig-wrong", {})
    report(st == 403, "R3 非原申诉人 migrate → 403", str(st))

    # RL-12 ④（#100 逐字段比对）：pause 前后快照全部字段，pause 只允许写
    # pause 相关的三个字段（state/pause_reason/paused_at），其余逐字段不变。
    # ★ 变异法实测：pause 静默改写 reason 字段时 61/61 全绿 —— 之前没有任何
    #   断言回读 reason/appellant/opened_at，这条把它变成红的。
    #   断言本体在模块级 assert_pause_field_discipline（--controls 复用同一份，
    #   不许出现「主判据一套、对照另一套」的漂移）。
    assert_pause_field_discipline(report, appeals, ap["appeal_id"],
                                  "version_invalidated")

    st, migrated = call(app, "POST",
                        "/api/v1/appeals/%s/migrate" % ap["appeal_id"],
                        sub, "K-mig-ok", {})
    report(st == 200 and migrated["state"] == "migrated",
           "C2 原申诉人 migrate → migrated", "%s %r" % (st, migrated))
    mig_before = appeals.get(ap["appeal_id"])
    # migrate 返回的是改写后的快照（migrated["migrated_at"] 已写入），
    # 回读时它已经迁移完成 —— 「改写前」的状态只能取调用返回值本身。
    mig_after = migrated
    MIGRATE_FIELDS = {"state", "migrated_at"}
    untouched = sorted(
        k for k in set(mig_before) | set(mig_after)
        if k not in MIGRATE_FIELDS
        and mig_before.get(k) != mig_after.get(k))
    report(not untouched,
           "C2/RL-12④ migrate 同样只写 state/migrated_at（逐字段比对）",
           "changed=%r" % (untouched,))
    MIGRATE_FIELDS = {"state", "migrated_at"}
    untouched = sorted(
        k for k in set(mig_before) | set(mig_after)
        if k not in MIGRATE_FIELDS
        and mig_before.get(k) != mig_after.get(k))
    report(not untouched,
           "C2/RL-12④ migrate 同样只写 state/migrated_at（逐字段比对）",
           "changed=%r" % (untouched,))

    st, ap2 = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-2",
                   {"case_id": "case-1", "reason": "再申诉"})
    appeals.pause("case-1", now=time.time())
    stale = appeals.mark_stale(now=time.time() + 31 * 86400)
    report(any(x["appeal_id"] == ap2["appeal_id"] and x["state"] == "stale"
               for x in stale),
           "C2 paused 超 30 天 → stale（不关闭）", repr(stale))
    # ④ 在 stale 这一步同样成立：stale 后 reason/appellant 仍是申诉时原值
    # （RL-12 的「记录完整保留」半边；stale 只许写 state/stale_at）
    stale_row = next((x for x in stale
                      if x["appeal_id"] == ap2["appeal_id"]), {})
    report(stale_row.get("pause_reason") == "version_invalidated"
           and stale_row.get("reason") == "再申诉"
           and stale_row.get("appellant") == "u_sub",
           "C2/RL-12④ stale 后 reason/appellant 仍是申诉时原值",
           repr({k: stale_row.get(k)
                 for k in ("reason", "appellant", "pause_reason", "stale_at")}))

    st, ap3 = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-3",
                   {"case_id": "case-1", "reason": "待撤"})
    st, _ = call(app, "POST", "/api/v1/appeals/%s/withdraw" % ap3["appeal_id"],
                 sub, "K-wd-bad", {})
    report(st == 400, "C2 withdraw 缺 reason → 400", str(st))
    st, wd = call(app, "POST", "/api/v1/appeals/%s/withdraw" % ap3["appeal_id"],
                  sub, "K-wd-ok", {"reason": "不需要了"})
    report(st == 200 and wd["state"] == "withdrawn",
           "C2 withdraw → withdrawn", "%s %r" % (st, wd))

    # C3 takedown —— T-312b：六条路由接能力 + 改派口径 + completed_by
    #
    # ★ 这一段的顺序是「先红后绿」，不是「先跑通再补断言」：
    #   C3a 在名单为空时打六条，**全部必须 403**。
    #   改前六条只调 require_tenant，任何同租户的人都能跑——
    #   于是 C3a 会是 200/409 而不是 403，红得非常明确。
    import base.rbac as _rbac
    TAKEDOWN_PATHS = {
        "start": ("/api/v1/takedown-tasks/t-1/start", {}),
        "complete": ("/api/v1/takedown-tasks/t-1/complete",
                     {"evidence": {"platform": "amazon", "executed_by": "u_exec",
                                   "executed_at": "2026-10-19T00:00:00Z",
                                   "receipt_id": "R-x"}}),
        "fail": ("/api/v1/takedown-tasks/t-1/fail", {}),
        "retry": ("/api/v1/takedown-tasks/t-1/retry", {}),
        "reassign": ("/api/v1/takedown-tasks/t-1/reassign",
                     {"assignee": "u_dp3b"}),
        "waive": ("/api/v1/takedown-tasks/t-1/waive",
                  {"approvers": [], "reason": "x", "evidence": {}}),
    }

    _saved_src = getattr(_rbac, "_ALLOWLIST_SOURCE", None)
    try:
        # ── C3a fail closed：名单空集 + 调用方不是 coordinator 改派 ──
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset(),
                     "takedown.waive": frozenset()})
        empty_codes = {}
        for name, (path, body) in TAKEDOWN_PATHS.items():
            code, _ = call(app, "POST", path, execu, "K-td-empty-%s" % name, body)
            empty_codes[name] = code
        report(all(c == 403 for c in empty_codes.values()),
               "C3a ★ 名单空集 → 六条路由全 403（fail closed，不是默认放行）",
               repr(empty_codes))

        # ── C3b 反向对照：只点名 execute，waive 仍必须 403 ──
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset({"u_exec"}),
                     "takedown.waive": frozenset()})
        st_exec, _ = call(app, "POST", "/api/v1/takedown-tasks/t-1/start",
                          execu, "K-td-x-only", {})
        st_waive, wb = call(
            app, "POST", "/api/v1/takedown-tasks/t-3/waive", execu,
            "K-td-x-waive",
            {"approvers": [
                {"actor": "u_a", "scopes": ["takedown.waive"], "scope_match": True},
                {"actor": "u_b", "scopes": ["takedown.waive"], "scope_match": True}],
             "reason": "已协商", "evidence": {"note": "ok"}})
        report(st_exec == 200 and st_waive == 403,
               "C3b ★ takedown.execute 不能作证 takedown.waive（两把钥匙分开）",
               "start=%s waive=%s %r" % (st_exec, st_waive, wb))

        # ── C3c 角色 ≠ 授权：有 execute 角色但未点名 → 403 ──
        #   u_coord2 是 coordinator，角色矩阵里**没有** takedown.execute；
        #   u_dp3 的 coordinator 同样没有。用它证明「角色给了也不行」。
        st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-1/fail", coord,
                     "K-td-coord-exec", {})
        report(st == 403, "C3c 角色无 takedown.execute 且未点名 → 403", str(st))

        # ── C3d 两向都断言：点名后同一主体由 403 变 200 ──
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset({"u_exec"}),
                     "takedown.waive": frozenset({"u_exec"})})
        st, t1 = call(app, "POST", "/api/v1/takedown-tasks/t-4/start", execu,
                      "K-td-start-4d", {})
        report(st == 200 and t1["state"] == "in_progress",
               "C3d 点名后 start 由 403 变 200（两向都断言）",
               "%s %r" % (st, t1))

        # ── C3e complete：evidence 校验 + completed_by 取 principal ──
        st, t1c = call(app, "POST", "/api/v1/takedown-tasks/t-1/complete", execu,
                       "K-td-complete-1",
                       {"evidence": {"platform": "amazon",
                                     "executed_by": "u_exec",
                                     "executed_at": "2026-10-19T00:00:00Z",
                                     "receipt_id": "R-1"}})
        report(st == 200 and t1c["state"] == "completed" and t1c.get("evidence"),
               "C3e takedown complete 回填校验通过", "%s %r" % (st, t1c))
        report(t1c.get("completed_by") == "u_exec",
               "C3e2 ★ completed_by 取已认证 principal（不是 body 自报）",
               "completed_by=%r" % (t1c.get("completed_by"),))
        # ★ C3e3 第一版是假判据：它往 body 里塞 `completed_by` 期望被忽略，
        #   但 `TakedownEvidence` 没有 `extra="allow"`，pydantic 会静默丢掉
        #   未声明字段 —— 于是那条断言在「actor 被写死成常量」的变异下**照样绿**
        #   （实测 M3 变异 0 条红）。塞不进去的东西，测不到。
        #
        # 换成能红的形状：**换一个调用人，completed_by 必须跟着换**。
        # 变异「actor 写死成 u_exec」或「actor 取 task.assignee」都会让这条红。
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset({"u_exec", "u_signer"}),
                     "takedown.waive": frozenset({"u_exec"})})
        st, t1c2 = call(app, "POST", "/api/v1/takedown-tasks/t-4/complete", signer,
                        "K-td-complete-signer",
                        {"evidence": {"platform": "amazon",
                                      "executed_by": "u_signer",
                                      "executed_at": "2026-10-19T00:00:00Z",
                                      "receipt_id": "R-9"}})
        report(t1c2.get("completed_by") == "u_signer"
               and t1c2.get("completed_by") != t1c.get("completed_by"),
               "C3e3 ★ 换调用人 completed_by 跟着换（不是写死/不是取 assignee）",
               "%s exec=%r signer=%r" % (st, t1c.get("completed_by"),
                                         t1c2.get("completed_by")))
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset({"u_exec"}),
                     "takedown.waive": frozenset({"u_exec"})})

        st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-2/start", execu,
                     "K-td-start-2", {})
        st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-2/complete", execu,
                     "K-td-empty", {"evidence": {}})
        report(st == 400, "C3f 无证据 complete → 400", str(st))

        # ── C3g TD-12 改派：coordinator 且同租户才能改派，与 execute 无关 ──
        _rbac.set_allowlist_source(
            lambda: {"takedown.execute": frozenset({"u_exec"}),
                     "takedown.waive": frozenset({"u_exec"})})
        st, re2 = call(app, "POST", "/api/v1/takedown-tasks/t-2/reassign", coord,
                       "K-td-reassign-2", {"assignee": "u_dp3b"})
        report(st == 200 and re2["assignee"] == "u_dp3b",
               "C3g ★ 统筹可改派（TD-12；它没有 takedown.execute）",
               "%s %r" % (st, re2))
        # 反向：执行人（signer，非 coordinator）改派 → 403
        st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-2/reassign", execu,
                     "K-td-reassign-exec", {"assignee": "u_dp3c"})
        report(st == 403, "C3g2 ★ 执行人不能改派（改派不是执行权）", str(st))

        # ── C3h fail → retry → waive 全链（waive 需独立钥匙 + 双人） ──
        call(app, "POST", "/api/v1/takedown-tasks/t-2/start", execu,
             "K-td-start-2b", {})
        st, failed_task = call(app, "POST", "/api/v1/takedown-tasks/t-2/fail",
                               execu, "K-td-fail-2", {})
        st, retried = call(app, "POST", "/api/v1/takedown-tasks/t-2/retry", execu,
                           "K-td-retry-2", {})
        report(failed_task["state"] == "failed" and retried["state"] == "pending",
               "C3h fail → retry", repr((failed_task.get("state"),
                                         retried.get("state"))))
        call(app, "POST", "/api/v1/takedown-tasks/t-3/start", execu,
             "K-td-start-3", {})
        call(app, "POST", "/api/v1/takedown-tasks/t-3/fail", execu,
             "K-td-fail-3", {})
        st, waived = call(
            app, "POST", "/api/v1/takedown-tasks/t-3/waive", execu, "K-td-waive-3",
            {"approvers": [
                {"actor": "u_a", "scopes": ["takedown.waive"], "scope_match": True},
                {"actor": "u_b", "scopes": ["takedown.waive"], "scope_match": True}],
             "reason": "已协商", "evidence": {"note": "ok"}})
        report(st == 200 and waived.get("waived", {}).get("approvers")
               == ["u_a", "u_b"],
               "C3h2 waive 双人审批通过", "%s %r" % (st, waived))
    finally:
        _rbac.set_allowlist_source(_saved_src)

    # C3i 生产能力表必须放行这六条（改前它们是 501）
    missing_prod = sorted(p for p in (
        "/api/v1/takedown-tasks/{id}/start",
        "/api/v1/takedown-tasks/{id}/complete",
        "/api/v1/takedown-tasks/{id}/fail",
        "/api/v1/takedown-tasks/{id}/retry",
        "/api/v1/takedown-tasks/{id}/reassign",
        "/api/v1/takedown-tasks/{id}/waive",
    ) if p not in PRODUCTION_WRITE_PATHS)
    report(not missing_prod,
           "C3i ★ 六条下线写路径已进 PRODUCTION_WRITE_PATHS（不再 501）",
           repr(missing_prod))
    # 反向：签发两条仍未放行（T-310 未交付，放行等于假成功）
    report("/api/v1/cases/{id}/release-decision" not in PRODUCTION_WRITE_PATHS
           and "/api/v1/cases/{id}/release-revoke" not in PRODUCTION_WRITE_PATHS,
           "C3j ★ release 两条仍未进生产能力表（避免假成功）")

    # C4 release-decision / revoke：真实 ReleaseGate + step-up + SoD + 版本
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 signer, "K-rel-nostep",
                 {"decision": "sign", "version": 1, "reason": "缺 step-up"})
    report(st == 403, "C4 缺 step-up → 403", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 sub, "K-rel-self",
                 {"decision": "sign", "version": 1, "reason": "自签"})
    report(st == 403, "C4 自签 → 403", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 signer, "K-rel-version",
                 {"decision": "sign", "version": 999, "reason": "旧版本"})
    report(st == 409, "C4 版本冲突 → 409", str(st))

    token = store.issue_step_up("u_signer", "case-release", "sign",
                                "n-sign", now=time.time())
    st, signed = call(app, "POST",
                      "/api/v1/cases/case-release/release-decision", signer,
                      "K-rel-sign",
                      {"decision": "sign", "version": 1, "reason": "签发",
                       "step_up_token": token, "nonce": "n-sign"})
    sig = (signed or {}).get("signature") or {}
    report(st == 200 and len(sig.get("signature_hash", "")) == 64
           and (signed or {}).get("release", {}).get("status") == "signed"
           and (signed or {}).get("release", {}).get("release_status") == "已放行",
           "C4/R4 sign 真实成功（签名 + signed/已放行；占位 200 不成立）",
           "%s %r" % (st, signed))

    token = store.issue_step_up("u_signer", "case-release", "revoke",
                                "n-revoke", now=time.time())
    st, revoked = call(app, "POST",
                       "/api/v1/cases/case-release/release-revoke", signer,
                       "K-rel-revoke",
                       {"version": 1, "reason": "撤回",
                        "step_up_token": token, "nonce": "n-revoke"})
    report(st == 200
           and (revoked or {}).get("release", {}).get("status") == "revoked"
           and (revoked or {}).get("release", {}).get("release_status") == "已撤回",
           "C4 revoke 真实成功（revoked/已撤回）", "%s %r" % (st, revoked))

    token = store.issue_step_up("u_signer", "case-release2", "reject",
                                "n-reject", now=time.time())
    st, rejected = call(app, "POST",
                        "/api/v1/cases/case-release2/release-decision", signer,
                        "K-rel-reject",
                        {"decision": "reject", "version": 1, "reason": "材料不足",
                         "step_up_token": token, "nonce": "n-reject"})
    report(st == 200
           and (rejected or {}).get("release", {}).get("status") == "rejected"
           and (rejected or {}).get("release", {}).get("release_status") == "已拒绝",
           "C4 reject 真实成功（rejected/已拒绝）", "%s %r" % (st, rejected))

    # C6 TS-1：每个写操作类别的身份矩阵（a 无 principal / b 缺字段 /
    # 模拟身份 / 跨租户）。完整 principal 的成功路径已由 C0–C4 各自覆盖：
    # claim / actions / appeal / sign / revoke / waive。
    tmp_audit = tempfile.mkdtemp(prefix="write_identity_")

    def missing_provider(pid, tenant):
        return {"id": pid, "tenant": tenant, "roles": ["coordinator"],
                "product_lines": ["pump"], "product_line": "pump"}

    def sim_provider(pid, tenant):
        return {"id": pid, "tenant": tenant, "open_id": "ou_" + pid,
                "tenant_id": tenant, "simulated": True,
                "roles": ["coordinator"], "product_lines": ["pump"],
                "product_line": "pump"}

    def cross_provider(pid, tenant):
        return {"id": pid, "tenant": "t2", "open_id": "ou_" + pid,
                "tenant_id": tenant, "roles": ["coordinator"],
                "product_lines": ["pump"], "product_line": "pump"}

    def matrix_app(provider):
        return create_app(
            session_store=store, repository=repo,
            principal_provider=provider, reviews_ledger=ledger,
            finding_store=fs, appeals=appeals,
            release_gate=app.state.release_gate,
            access_log_path=os.path.join(tmp_audit, "access.jsonl"))

    missing_app = matrix_app(missing_provider)
    sim_app = matrix_app(sim_provider)
    cross_app = matrix_app(cross_provider)
    # 给 revoke 矩阵准备一个已签发、尚未撤回的案件。
    p_signer = dict(principals["u_signer"])
    p_signer.update({"id": "u_signer", "tenant": "t1",
                     "open_id": "ou_u_signer", "tenant_id": "t1"})
    token = store.issue_step_up("u_signer", "case-release4", "sign",
                                "n-matrix-sign", now=time.time())
    app.state.release_gate.sign(
        repo.get_case("case-release4"), p_signer, token, "n-matrix-sign",
        reason="matrix setup", now=time.time())
    matrix = [
        ("claim", "/api/v1/cases/case-1/claim", {}, coord),
        ("actions", "/api/v1/cases/case-2/actions",
         {"version": 1, "action": "save_draft", "draft": {}}, coord),
        ("appeal", "/api/v1/appeals", {"case_id": "case-1", "reason": "x"}, sub),
        ("sign", "/api/v1/cases/case-release3/release-decision",
         {"decision": "sign", "version": 1, "reason": "x"}, signer),
        ("revoke", "/api/v1/cases/case-release4/release-revoke",
         {"version": 1, "reason": "x"}, signer),
        ("waive", "/api/v1/takedown-tasks/t-3/waive",
         {"approvers": [], "reason": "x", "evidence": {}}, coord),
    ]
    for name, path, body, cookie in matrix:
        st, _ = call(app, "POST", path, None, "K-id-a-%s" % name, body)
        report(st == 401, "C6 %s a：无 principal → 401" % name, str(st))
        st, _ = call(missing_app, "POST", path, cookie,
                     "K-id-b-%s" % name, body)
        report(st == 401, "C6 %s b：缺 open_id/tenant_id → 401" % name, str(st))
        st, _ = call(sim_app, "POST", path, cookie,
                     "K-id-sim-%s" % name, body)
        report(st == 403, "C6 %s 生产模拟身份 → 403" % name, str(st))
        st, _ = call(cross_app, "POST", path, cookie,
                     "K-id-x-%s" % name, body)
        report(st == 403, "C6 %s principal tenant≠案件 tenant → 403" % name,
               str(st))
    shutil.rmtree(tmp_audit, ignore_errors=True)

    # C5 静态扫描
    sources = [open(os.path.join(REPO_ROOT, "api", name),
                    encoding="utf-8").read()
               for name in ("review_api.py", "write_api.py")]
    forbidden = ["decision_table", "coverage_composer", "evidence_sync",
                 "semantic_judge", "rule_judge", "normalizer",
                 "orchestrator", "derive_state(", "decide("]
    leaked = [(name, token) for name, src in zip(("review_api.py", "write_api.py"), sources)
              for token in forbidden if token in src]
    report(not leaked, "C5 API 层不含判定实现", repr(leaked))
    computed = []
    for name, src in zip(("review_api.py", "write_api.py"), sources):
        computed += [(name, line) for line in src.splitlines()
                     if re.match(r"^\s*(state|decision|[a-z_]*_state)\s*=", line)]
    report(not computed, "C5 API 层不计算 state/decision", repr(computed[:3]))
    direct_release = []
    for name, src in zip(("review_api.py", "write_api.py"), sources):
        direct_release += [(name, line) for line in src.splitlines()
                           if re.match(r"^\s*release_status\s*=", line)]
    report(not direct_release,
           "C5 机器/前端不可直写 release_status", repr(direct_release[:3]))
    report("gate.sign(" in sources[1] and "gate.revoke(" in sources[1],
           "C5 release 只走 ReleaseGate", "")

    # C7 capability allowlist：显式空集合必须全关；不能用 `or defaults` 回退全开。
    empty_app = create_app(
        session_store=store, repository=repo, principals=principals,
        finding_store=fs, appeals=AppealStore(), enabled_write_capabilities=set())
    disabled_paths = [
        ("/api/v1/cases/case-1/claim", {}),
        ("/api/v1/appeals", {"case_id": "case-1", "reason": "x"}),
        ("/api/v1/takedown-tasks/t-1/start", {}),
        ("/api/v1/cases/case-release/release-decision",
         {"decision": "sign", "version": 1}),
    ]
    disabled_results = [
        call(empty_app, "POST", path, sub, "EMPTY-%d" % i, body=body)[0]
        for i, (path, body) in enumerate(disabled_paths)
    ]
    report(disabled_results == [501] * len(disabled_results),
           "C7 显式空 capability 集合不回退全开", repr(disabled_results))

    # T-102 写端点声明 ↔ 实现/占位 必须一致；release 不再有第二套口径。
    declared = set(WRITE_PATHS)
    implemented = set(IMPLEMENTED_WRITE_PATHS)
    route_names = {}
    for route in app.routes:
        if "POST" in (getattr(route, "methods", None) or set()):
            route_names.setdefault(route.path, set()).add(
                route.endpoint.__name__)
    wrong_impl = sorted(
        path for path in implemented
        if "placeholder" in route_names.get(path, set())
        or not route_names.get(path))
    wrong_placeholder = sorted(
        path for path in declared - implemented
        if "placeholder" not in route_names.get(path, set()))
    report(not wrong_impl,
           "T-102 已实现路径不得由 placeholder 兜底", repr(wrong_impl))
    report(not wrong_placeholder,
           "T-102 未实现路径必须有 placeholder", repr(wrong_placeholder))
    report(declared <= set(route_names),
           "T-102 Appendix B 写端点全部注册",
           repr(sorted(declared - set(route_names))))
    report("/api/v1/submissions" in implemented
           and "/api/v1/submissions" in PRODUCTION_WRITE_PATHS,
           "T-100 submissions 同时进入实现表与生产能力表",
           "impl=%r prod=%r" % ("/api/v1/submissions" in implemented,
                                "/api/v1/submissions" in PRODUCTION_WRITE_PATHS))

    prod_app = create_app(
        session_store=store, repository=repo, principals=principals,
        finding_store=fs, appeals=AppealStore(),
        enabled_write_capabilities=PRODUCTION_WRITE_PATHS)
    st, body = call(prod_app, "POST",
                    "/api/v1/cases/case-release/release-decision", signer,
                    "K-prod-rel", {"decision": "sign", "version": 1})
    message = str((body or {}).get("message") or "")
    report(st == 501 and "capability_not_enabled" in message
           and "release_gate 未实现" not in message,
           "T-102 生产 capability 下 release 只报 capability_not_enabled",
           "%s %r" % (st, message))

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) in (
                "write_api.py", "review_api.py", "reviews_ledger.py",
                "finding_store.py", "takedown.py"):
            print("FAIL: 写 API 依赖抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
