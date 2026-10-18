#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_reviews_ledger.py — T2-02a：复核台账 / 领取 / 草稿

覆盖：
  C0  claim 原子独占：并发两人只有一个成功，另一个明确 conflict；重复 claim 拒绝
  C1  lease：30 分钟空闲自动释放；释放前 draft 仍在；心跳延长；版本冲突明确
  C2  draft：全字段快照 + snapshot_seq/snapshot_at/content_hash/author；
      autosave 不产 formal；只有 explicit submit 才产 formal
  C3  adopt：新 assignee 只读前任 draft；显式 adopt 产新 draft + derived_from；
      非 primary 只能引用片段（source_draft_id+field_path+fragment）；原稿不变
  C4  抽样台账：PASS/待自决/REVIEW/未审查 四层分别抽样 + BLOCK 全量复核；
      未复核完 → untested + 已复核占比，不得用部分算比率
  R1  并发 claim 两个都成功 → 红
  R2  lease 释放丢 draft → 红
  R3  autosave 产生 formal finding → 红
  R4  adopt 无 derived_from → 红
  R5  原 draft 被修改 → 红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.reviews_ledger import (
        ReviewsLedger, LedgerConflict, LedgerNotFound, LedgerValidation,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.reviews_ledger: %s" % exc)
    sys.exit(2)


def claim(ledger, case_id, actor, now=0):
    return ledger.claim(case_id, actor, now=now)


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

    # C0/R1 并发 claim 恰好一个成功
    ledger = ReviewsLedger(lease_seconds=1800)
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(actor):
        barrier.wait()
        try:
            outcomes.append(("ok", actor, claim(ledger, "case-1", actor, now=0)))
        except LedgerConflict as exc:
            outcomes.append(("conflict", actor, exc.code))

    threads = [threading.Thread(target=worker, args=(a,))
               for a in ("alice", "bob")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    oks = [o for o in outcomes if o[0] == "ok"]
    conflicts = [o for o in outcomes if o[0] == "conflict"]
    report(len(oks) == 1 and len(conflicts) == 1
           and conflicts[0][2] == "already_claimed",
           "C0/R1 并发 claim 恰好一个成功、另一个明确冲突",
           repr(outcomes))
    winner = oks[0][1] if oks else "alice"
    try:
        claim(ledger, "case-1", winner, now=1)
        dup = None
    except LedgerConflict as exc:
        dup = exc.code
    report(dup is not None, "C0 重复 claim 被拒绝", repr(dup))

    # C1 lease：心跳延长 / 到期释放且 draft 仍在
    ledger = ReviewsLedger(lease_seconds=1800)
    c = claim(ledger, "case-2", "alice", now=0)
    d = ledger.autosave("case-2", "alice", c["version"],
                        form={"summary": "初稿"}, notes="note",
                        evidence_selections=["E-1"], references=[],
                        now=10)
    ledger.expire(now=1801)
    drafts = ledger.list_drafts("case-2")
    report(ledger.get_case("case-2")["status"] == "released",
           "C1 lease 30m 无活动 → released", repr(ledger.get_case("case-2")))
    report(len(drafts) == 1
           and drafts[0]["draft_id"] == d["draft"]["draft_id"]
           and drafts[0]["content_hash"] == d["draft"]["content_hash"],
           "C1/R2 释放前 draft 已保存且未丢", repr(drafts))

    ledger = ReviewsLedger(lease_seconds=1800)
    c = claim(ledger, "case-3", "alice", now=0)
    hb = ledger.heartbeat("case-3", "alice", c["version"], now=1000)
    ledger.expire(now=2000)
    report(ledger.get_case("case-3")["status"] == "claimed",
           "C1 心跳延长 lease（2000 未到期）", repr(ledger.get_case("case-3")))
    ledger.expire(now=2801)
    report(ledger.get_case("case-3")["status"] == "released",
           "C1 心跳延长后 2801 到期释放", repr(ledger.get_case("case-3")))
    try:
        ledger.heartbeat("case-3", "alice", hb["version"] - 1, now=10)
        stale = None
    except LedgerConflict as exc:
        stale = exc.code
    report(stale == "version_conflict", "C1 过期版本心跳 → 明确冲突", repr(stale))

    # C2 draft 全字段 + autosave 不产 formal；submit 才产 formal
    ledger = ReviewsLedger(lease_seconds=1800)
    c = claim(ledger, "case-4", "alice", now=0)
    d = ledger.autosave(
        "case-4", "alice", c["version"],
        form={"summary": "待确认", "fields": {"a": 1}},
        notes="notes", evidence_selections=["E-1", "E-2"],
        references=[{"ref": "R-1"}], now=20)
    draft = d["draft"]
    report(draft["snapshot_seq"] == 1
           and draft["author"] == "alice"
           and len(draft["snapshot_at"]) >= 20
           and len(draft["content_hash"]) == 64
           and draft["form"] == {"summary": "待确认", "fields": {"a": 1}}
           and draft["notes"] == "notes"
           and draft["evidence_selections"] == ["E-1", "E-2"]
           and draft["references"] == [{"ref": "R-1"}],
           "C2 draft 全字段快照 + seq/at/hash/author", repr(draft))
    report(ledger.formal_events() == [] and d.get("formal") is None,
           "C2/R3 autosave 不产 formal finding/decision", repr(ledger.formal_events()))
    sub = ledger.submit("case-4", "alice", d["version"],
                        conclusion={"status": "confirmed", "reason": "人工确认"},
                        now=30)
    events = ledger.formal_events()
    report(len(events) == 1 and sub["formal"]["from_draft_id"] == draft["draft_id"]
           and events[0]["from_draft_id"] == draft["draft_id"],
           "C2 explicit submit 才进 formal finding/decision", repr(events))

    # C3 adopt / fragment / 原稿不可变
    ledger = ReviewsLedger(lease_seconds=1800)
    c = claim(ledger, "case-5", "alice", now=0)
    d1 = ledger.autosave("case-5", "alice", c["version"],
                         form={"summary": "v1"}, notes="n1",
                         evidence_selections=[], references=[], now=10)
    d2 = ledger.autosave("case-5", "alice", d1["version"],
                         form={"summary": "v2"}, notes="n2",
                         evidence_selections=[], references=[], now=20)
    ledger.expire(now=2000)
    c2 = claim(ledger, "case-5", "bob", now=2001)
    readable = ledger.list_drafts("case-5")
    report(len(readable) == 2
           and {d["author"] for d in readable} == {"alice"},
           "C3 新 assignee 可只读前任 draft", repr(readable))
    # adopt 前：当前 primary（d2）只能显式 adopt，不能只引用片段。
    try:
        ledger.reference_fragment(
            "case-5", "bob", c2["version"],
            source_draft_id=d2["draft"]["draft_id"],
            field_path="form.summary", fragment="v2", now=2002)
        ref_primary = None
    except LedgerConflict as exc:
        ref_primary = exc.code
    report(ref_primary == "primary_requires_adopt",
           "C3 primary draft 必须显式 adopt，不许只引用片段", repr(ref_primary))

    before_d2 = dict(d2["draft"])
    adopt = ledger.adopt("case-5", "bob", c2["version"],
                         source_draft_id=d2["draft"]["draft_id"], now=2003)
    new_draft = adopt["draft"]
    report(new_draft["derived_from"] == d2["draft"]["draft_id"]
           and new_draft["author"] == "bob"
           and new_draft["content_hash"] == d2["draft"]["content_hash"],
           "C3/R4 adopt 产新 draft + derived_from", repr(new_draft))
    report(ledger.get_draft(d2["draft"]["draft_id"]) == before_d2,
           "C3/R5 adopt 不改原 draft", repr(ledger.get_draft(d2["draft"]["draft_id"])))
    try:
        ledger.adopt("case-5", "bob", adopt["version"],
                     source_draft_id=d1["draft"]["draft_id"], now=2004)
        non_primary = None
    except LedgerConflict as exc:
        non_primary = exc.code
    report(non_primary == "not_primary",
           "C3 非 primary draft 不许 adopt", repr(non_primary))
    ref = ledger.reference_fragment(
        "case-5", "bob", adopt["version"],
        source_draft_id=d1["draft"]["draft_id"],
        field_path="form.summary", fragment="v1", now=2005)
    report(ref["reference"]["source_draft_id"] == d1["draft"]["draft_id"]
           and ref["reference"]["field_path"] == "form.summary"
           and ref["reference"]["fragment"] == "v1"
           and len(ledger.list_drafts("case-5")) == 3,
           "C3 非 primary 仅引用片段，不自动 merge", repr(ref))

    # C4 抽样台账：四层分别抽 + BLOCK 全量
    ledger = ReviewsLedger()
    ledger.open_sampling([
        {"case_id": "c-pass", "label": "PASS"},
        {"case_id": "c-pending", "label": "待自决"},
        {"case_id": "c-review", "label": "REVIEW"},
        {"case_id": "c-unassessed", "label": "未审查"},
        {"case_id": "c-block", "label": "BLOCK"},
    ], reviewer="alice", now=0)
    st = ledger.sampling_status()
    report(st["status"] == "untested"
           and all(len(st["layers"][k]) == 1 for k in
                   ("PASS", "待自决", "REVIEW", "未审查"))
           and st["block"]["total"] == 1
           and st["block"]["reviewed"] == 0
           and st["block"]["reviewed_ratio"] == 0.0
           and st["block"]["false_positive_rate"] is None,
           "C4 四层分别抽样 + BLOCK 全量未复核 → untested + 占比",
           repr(st))
    ledger.record_block_review("c-block", "alice", "confirmed",
                               false_positive=False, now=10)
    st = ledger.sampling_status()
    report(st["status"] == "ok"
           and st["block"]["reviewed"] == 1
           and st["block"]["reviewed_ratio"] == 1.0
           and st["block"]["false_positive_rate"] == 0.0,
           "C4 BLOCK 全量复核完成 → ok + 比率", repr(st))
    try:
        ledger.record_block_review("c-block", "alice", "confirmed", now=11)
        dup = None
    except LedgerConflict as exc:
        dup = exc.code
    report(dup == "already_reviewed", "C4 BLOCK 重复复核拒绝", repr(dup))

    ledger = ReviewsLedger()
    ledger.open_sampling([
        {"case_id": "only-pass", "label": "PASS"},
        {"case_id": "only-block", "label": "BLOCK"},
    ], reviewer="alice", now=0)
    st = ledger.sampling_status()
    report(st["status"] == "untested"
           and set(st["missing_layers"]) == {"待自决", "REVIEW", "未审查"},
           "C4 缺层 → untested + missing_layers", repr(st))

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
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) == "reviews_ledger.py":
            print("FAIL: reviews_ledger 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
