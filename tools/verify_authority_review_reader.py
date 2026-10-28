#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_authority_review_reader.py —— 台账摘要读 authority 的适配器

## 它守的是什么

开发装配启用写路径（`review_command_service`）之后，`claim` 写 **authority**，
而案件详情的 `review` 摘要原本从**内存 ReviewsLedger** 读 —— 两份数据分叉。
实测（2026-10-28，修前）：

    POST /cases/{id}/claim → 200  version=1
    GET  /cases/{id}       → review.status="unassigned"  version=0

界面上表现成「请求已接受，但台账回读未完成」，而请求**确实成功了**。

## 本文件断言什么

| 组 | 验什么 |
|---|---|
| A | 形状正确：state 上的键按 `_review_summary` 认得的名字摆出来 |
| B | ★★★ **缺失不许装成有值** —— 不存在的案件返回 None，不是空摘要 |
| C | ★★ 真的能回读到写结果（claim → get_case 看到 claimed / version+1） |
| D | ★★ `list_drafts` 与 state 上的 drafts 逐项一致（不复制、不裁剪） |
| E | 反向对照：构造坏样本，证明上面几条不是恒真 |

## 为什么 C 必须打在**真写路径**上

A 组只验「把 dict 摆成另一个 dict」—— 一个把字段名写错的实现也能过。
C 组走 `ReviewCommandService.claim` 真写一次，再看适配器读出来什么 ——
那才是「界面会不会显示成功」的那个判据。

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


class _FakeAuthority:
    """只实现 `state` 的最小替身 —— 适配器只调这一个方法。"""

    def __init__(self, states):
        self._states = states

    def state(self, case_id):
        return self._states.get(case_id)


# ─────────────────────────────────────────────── A 形状

def group_a():
    from base.authority_review_reader import AuthorityReviewReader

    full = {
        "status": "claimed", "assignee": "u1", "version": 3,
        "claimed_at": "2026-10-01T00:00:00Z",
        "last_activity": "2026-10-02T00:00:00Z",
        "lease_expires": 1234.5,
        "released_at": None, "released_draft_id": None,
        "primary_draft_id": "d-1",
        "drafts": [{"draft_id": "d-1"}],
        "fragment_references": [{"ref": 1}],
    }
    src = AuthorityReviewReader(_FakeAuthority({"c1": full}))
    got = src.get_case("c1") or {}

    # A1 好样本（否则下面全是恒红）
    report(isinstance(got, dict) and bool(got),
           "A1 ★ 好样本：state 在 → 读得出摘要（否则下面全是恒红）")

    # A2 ★★★ `_review_summary` 认得的键，一个都不许少
    #
    #   ★ 这份清单是**手写**的，不是 `from api.review_api import ...` 去取 ——
    #     如果从那边取，那边删掉一个键，这里跟着变绿（同一个口径两处漂移，
    #     而漂移的那一处正是判据）。手写才有得比。
    needed = {"case_id", "status", "assignee", "version", "claimed_at",
              "last_activity", "lease_expires", "released_at",
              "released_draft_id", "primary_draft_id", "drafts",
              "fragment_references"}
    report(needed <= set(got),
           "A2 ★★★ 摘要含 `_review_summary` 认得的全部键",
           "缺 %r" % (sorted(needed - set(got)),))

    # A3 值原样透传（不许改写类型）
    report(got.get("status") == "claimed" and got.get("version") == 3,
           "A3 ★ 值原样透传（status / version）",
           repr((got.get("status"), got.get("version"))))
    report(got.get("case_id") == "c1",
           "A4 ★ case_id 用传入的那个（不是从 state 里挖）", repr(got.get("case_id")))


# ─────────────────────────────────────────────── B 缺失不装成有值

def group_b():
    from base.authority_review_reader import AuthorityReviewReader

    src = AuthorityReviewReader(_FakeAuthority({}))

    # B1 ★★★ 案件不存在 → None（不是全 None 的摘要）
    #
    #   ★ 这一条是本模块最容易犯的错：返回一个「键齐全但值全 None」的摘要，
    #     会让 404 分支永远走不到，于是「案件不存在」显示成「台账为空」。
    report(src.get_case("nope") is None,
           "B1 ★★★ 案件不存在 → None（不是空摘要；否则 404 永远走不到）",
           repr(src.get_case("nope")))

    # B2 ★★ state 存在但键缺 → 缺的就是 None，不许补 'unassigned' / 0
    thin = AuthorityReviewReader(_FakeAuthority({"c2": {"status": "claimed"}}))
    got = thin.get_case("c2") or {}
    report(got.get("version") is None,
           "B2 ★★ 缺 version → None（不许补 0 —— 「版本 0」是一个真实存在的版本）",
           repr(got.get("version")))
    report(got.get("assignee") is None,
           "B3 ★★ 缺 assignee → None（不许补某个默认人）", repr(got.get("assignee")))
    report(got.get("drafts") == [],
           "B4 ★ 缺 drafts → 空列表（列表的「没有」就是空，不是 None）",
           repr(got.get("drafts")))

    # B5 ★★ state 明说 unassigned / 0 时，必须**原样**给出 0 —— 与 B2 成对
    #
    #   只做 B2 的实现会用 `or None` 把 0 吃掉；只做 B5 的实现会补 0。
    #   两条一起才能卡住「区分真正的 0 与缺失」。
    zero = AuthorityReviewReader(_FakeAuthority({"c3": {"status": "unassigned", "version": 0}}))
    g3 = zero.get_case("c3") or {}
    report(g3.get("version") == 0,
           "B5 ★★★ 真正的 version=0 必须原样给出（不许被 `or None` 吃掉）",
           repr(g3.get("version")))


# ─────────────────────────────────────────────── C 真写路径

def group_c():
    """★ 这一组走**真实** `ReviewCommandService` + `BusinessEventStore`。

    只验「把 dict 摆成 dict」是不够的：字段名写错的实现也能过 A 组。
    这里真写一次 claim，再看适配器读出来的是不是那个写结果 ——
    那才是「界面上认领会不会显示成功」的判据。
    """
    try:
        from base.authority_review_reader import AuthorityReviewReader
        from base.business_event_store import BusinessEventStore, WriterLease
        from base.projection_store import ProjectionStore
        from base.review_command_service import ReviewCommandService
    except Exception as exc:  # noqa: BLE001
        untested("C 导入写路径部件", "%s: %s" % (type(exc).__name__, exc))
        return

    root = Path(tempfile.mkdtemp(prefix="arv-reader-"))
    lease = None
    try:
        lease = WriterLease(root / "authority" / "writer.lock")
        lease.acquire()
        authority = BusinessEventStore(root / "authority", lease=lease)
        service = ReviewCommandService(authority, ProjectionStore(root / "p.sqlite"))

        # 造一个最小案件（只要 reducer 认它是案件）
        _seed_case(authority, "case-a")
        reader = AuthorityReviewReader(authority)

        before = reader.get_case("case-a") or {}
        # ★ ingest 本身是一次权威写，所以写完之后版本已经是 1，不是 0。
        #   第一版断言「写前是 v0」并因此变红 —— 那不是适配器错，是我对
        #   「什么算一次写」的假设错了。判据改成「claim 让版本**前进**」，
        #   那才是界面关心的东西。
        v_before = before.get("version")
        report(before.get("status") == "unassigned",
               "C1 ★ 写前状态是 unassigned（否则 C2 的对比没有基准）",
               repr(before.get("status")))

        # ★ 走通用的 `execute`：`ReviewCommandService` 没有 `claim()` 方法，
        #   claim 是 `api/write_api.py` 用 `command="claim"` 调进来的。
        #   第一版写成 `service.claim(...)` 直接 AttributeError —— 而那样的
        #   报错会显示成「C 组失败」，读起来像适配器坏了。
        service.execute(
            aggregate_id="case-a", command="claim",
            actor={"principal_id": "u1", "tenant_id": "t1"},
            expected_version=v_before, payload={},
            idempotency_key="k-claim-1")

        after = reader.get_case("case-a") or {}
        report(after.get("status") == "claimed",
               "C2 ★★★ 写后适配器读到 claimed（读不到就是原来的分叉）",
               repr(after.get("status")))
        report(after.get("version") == (v_before or 0) + 1,
               "C3 ★★★ 写后版本前进一格"
               "（回读版本对不上，界面就会说「回读未完成」）",
               "%r → %r" % (v_before, after.get("version")))
        report(after.get("assignee") == "u1",
               "C4 ★★ 写后能读到 assignee", repr(after.get("assignee")))
    except Exception as exc:  # noqa: BLE001
        report(False, "C 真写路径", "%s: %s" % (type(exc).__name__, exc))
    finally:
        try:
            if lease is not None:
                lease.release()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(root, ignore_errors=True)


def _seed_case(authority, case_id, *, status="unassigned", version=0):
    """造一个最小案件。

    ★ 走 authority 的公开写入口（`execute`），不直接改内部文件 ——
      直接写文件会让本组测的变成「我能不能伪造状态」，而不是适配器。
    """
    authority.execute(
        aggregate_id=case_id, command="ingest_submission",
        actor={"principal_id": "sys", "tenant_id": "t1"},
        expected_version=0,
        payload=_minimal_ingest_payload(case_id),
        idempotency_key="seed-%s" % case_id,
    )
    return case_id


def _minimal_ingest_payload(case_id):
    """reducer 认的最小 ingest payload。逐字段照着 `review_reducer` 的校验给。"""
    import hashlib
    text = "合规测试正文"
    return {
        "submission_id": case_id,
        "submission_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "tenant": "t1",
        "product_line": "pump",
        "submitter_id": "u-sub",
        "content": {
            "unit_id": "unit-1", "kind": "free_text",
            "text": text, "has_text": True,
            "fingerprint": {
                "raw_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
        },
        "ir": {
            "ir_id": "ir-1", "ir_version": "ir-v1",
            "findings": [],
            "decision": {"state": "PASS", "layer": "L1", "release_status": "待放行"},
            "coverage": {"coverage_state": "full"},
            "control_points_version": "cp-test",
        },
        "judgment": {"run_state": "OK", "label": "PASS"},
        "kb_snapshot_hash": "a" * 64,
        "conflict_table_version": "cp-test",
        "media_fingerprints": {},
    }


# ─────────────────────────────────────────────── D 草稿

def group_d():
    from base.authority_review_reader import AuthorityReviewReader

    drafts = [{"draft_id": "d-1", "notes": "a"}, {"draft_id": "d-2", "notes": "b"}]
    src = AuthorityReviewReader(_FakeAuthority({"c9": {"drafts": drafts}}))
    got = src.list_drafts("c9")

    report(isinstance(got, list) and len(got) == 2,
           "D1 ★★ list_drafts 条数与 state 一致（不裁剪）", repr(len(got) if isinstance(got, list) else got))
    report(got == drafts,
           "D2 ★★★ 草稿内容逐项相同（不许在这里改写形状）", repr(got[:1]))
    report(src.list_drafts("nope") == [],
           "D3 ★ 不存在的案件 → 空列表（不是 None：调用方按可迭代用）")

    # D4 ★ 坏形状（drafts 不是 list）→ 空列表，不是把坏数据往下喂
    bad = AuthorityReviewReader(_FakeAuthority({"c8": {"drafts": "not-a-list"}}))
    report(bad.list_drafts("c8") == [],
           "D4 ★★ drafts 是坏形状 → 空列表（不把坏数据喂给界面）",
           repr(bad.list_drafts("c8")))


# ─────────────────────────────────────────────── E 反向对照

def group_e():
    """★ 证明 A/B 组抓的是真东西。

    A2 是「键齐全」，B1 是「不存在 → None」。这两条如果写错了（比如判据恒真），
    下面喂的反向样本必须让它们判假。
    """
    from base.authority_review_reader import AuthorityReviewReader, _summary_from_state

    # E1 ★★ 少一个键的实现会被 A2 抓到
    short = {"case_id": "c", "status": "claimed"}
    needed = {"case_id", "status", "assignee", "version", "drafts"}
    report(not (needed <= set(short)),
           "E1 ★★ 少键的摘要会被 A2 判红（证明 A2 不是恒真）",
           repr(sorted(needed - set(short))))

    # E2 ★★ 「返回空摘要」的实现会被 B1 抓到
    #
    #   这里直接构造那个坏形状：不存在的案件返回 `_summary_from_state("x", {})`
    #   而不是 None。判据是 `is None`，所以它必须判假。
    empty_summary = _summary_from_state("x", {})
    report(empty_summary is not None,
           "E2 ★★ 「空摘要」不是 None（所以 B1 的 `is None` 能区分两者）",
           repr(type(empty_summary).__name__))

    # E3 ★★ `or None` 写法会把 0 吃掉 —— B5 抓的就是它
    fake_or_none = {"version": 0}.get("version") or None
    report(fake_or_none is None,
           "E3 ★★★ `or None` 确实会吃掉 0（证明 B5 这条判据有实际作用）",
           repr(fake_or_none))

    # E4 ★ 真身与替身读出来的形状一致（否则 C 组测的是另一条路径）
    states = {"cx": {"status": "claimed", "version": 2, "drafts": []}}
    real = AuthorityReviewReader(_FakeAuthority(states)).get_case("cx")
    report(real is not None and real.get("version") == 2,
           "E4 ★ 适配器在替身上也读得出（C 组用的是真 store，形状应当相同）")


# ─────────────────────────────── F 装配真的用上了它（否则它就是一块零件）

def group_f():
    """F 组（2026-10-28）：适配器必须真的被**开发装配**接上去。

    ## 为什么这一组必须有

    A–E 组全绿也说明不了接线存在：把 `review_read_store=` 一行删掉，
    `web/scripts/review_api_dev.py` 会退回内存账本 —— 改前的分叉原样回来，
    而本文件前五组**一条都不会红**（它们测的是适配器自己）。

    这正是 AGENTS.md 里那个反复出现的形状：**零件对了，接线没接**。

    ## 判据为什么是「读装配源码 + 真跑一次」

    只读源码（`"AuthorityReviewReader" in src`）会漏掉「import 了但没传」——
    那行代码长得完全一样。所以这里两段：
      · F1/F2 源码级：import 了、且作为 `review_read_store=` 的值传进去了；
      · F3 行为级：真装配起来，`claim` 之后详情接口的 `review.version` 跟上。

    ★ F3 是本文件唯一一条走 HTTP 的判据。它慢（~1s），但它才是
      「界面会不会显示认领成功」的那个问题。
    """
    from pathlib import Path as _P

    dev = _P(__file__).resolve().parent.parent / "web" / "scripts" / "review_api_dev.py"
    if not dev.is_file():
        untested("F 读开发装配源码", str(dev))
        return
    src = dev.read_text(encoding="utf-8")

    # ★ 剥注释：本文件与装配里都写了大量「为什么」的说明，
    #   不剥会把解释文字当成代码（check_api_centralization 踩过同一个坑）。
    code = _strip_comments(src)

    report("AuthorityReviewReader" in code,
           "F1 ★★ 开发装配 import 了 AuthorityReviewReader",
           "命中" if "AuthorityReviewReader" in code else "零命中")
    # ★ 必须作为**参数值**出现，不是只出现在 import 行。
    report("review_read_store=AuthorityReviewReader(" in code.replace(" ", ""),
           "F2 ★★★ 它被作为 `review_read_store=` 传进 create_app"
           "（只 import 不传 = 改前的分叉原样回来）",
           "命中" if "review_read_store=" in code else "零命中")

    # F3 行为级：真装配 → claim → 详情回读 version 前进
    _f3_behaviour(dev)


def _strip_comments(text: str) -> str:
    """去掉 `#` 行注释与三引号块。**判据与实现共用一条读法**。"""
    import re as _re
    text = _re.sub(r'"""[\s\S]*?"""', "", text)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _f3_behaviour(dev_path):
    """真起装配、真 claim、真回读。"""
    import importlib.util
    import os
    import shutil
    import tempfile
    import time

    root = tempfile.mkdtemp(prefix="arv-behaviour-")
    keys = ("REVIEW_API_DATA_ROOT", "APP_ENV", "REVIEW_DEV_IDENTITY",
            "REVIEW_MEDIA_INGEST")
    saved_env = {k: os.environ.get(k) for k in keys}
    try:
        data = os.path.join(root, "projection")
        os.makedirs(data, exist_ok=True)
        os.environ["REVIEW_API_DATA_ROOT"] = data
        os.environ["APP_ENV"] = "dev"
        # ★ 开发装配的**硬闸门**：没有这个变量它会直接拒绝启动
        #   （`review_api_dev.py` 的第一道自检）。不是可选项。
        os.environ["REVIEW_DEV_IDENTITY"] = "1"

        spec = importlib.util.spec_from_file_location("_arv_dev_app", dev_path)
        if spec is None or spec.loader is None:
            untested("F3 载入开发装配", "spec 为空")
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        try:
            from fastapi.testclient import TestClient
        except Exception as exc:  # noqa: BLE001
            untested("F3 import TestClient", str(exc))
            return

        client = TestClient(mod.app, base_url="https://ca.example")
        tok = mod._store.create_session("u_dp3", tenant="t1", now=time.time())
        headers = {"Cookie": "session=" + tok, "Origin": "https://ca.example"}

        # 造一个真案件（走写路径，才能在 authority 里有可 claim 的聚合）
        import hashlib
        text = "适配器行为级测试正文"
        sub_id = "arv-behaviour-1"
        resp = client.post(
            "/api/v1/submissions",
            headers={**headers, "Idempotency-Key": "arv-sub-1"},
            json={
                "submission_id": sub_id, "content_type": "文本",
                "content_stage": "final_content", "entry_channel": "群消息",
                "source": {"kind": "free_text"}, "product_line": "pump",
                "text": text,
            })
        if resp.status_code != 200:
            untested("F3 提交建案", "%s %s" % (resp.status_code, resp.text[:100]))
            return
        case_id = resp.json()["case_id"]

        before = (client.get("/api/v1/cases/%s" % case_id, headers=headers).json()
                  .get("review") or {})
        v_before = before.get("version")
        report(before.get("status") == "unassigned",
               "F3 ★ 新案件初始是 unassigned（F4 的对比基准）",
               repr(before.get("status")))

        claimed = client.post("/api/v1/cases/%s/claim" % case_id,
                              headers={**headers, "Idempotency-Key": "arv-claim-1"},
                              json={})
        report(claimed.status_code == 200,
               "F4 ★ claim 成功", str(claimed.status_code))
        after = (client.get("/api/v1/cases/%s" % case_id, headers=headers).json()
                 .get("review") or {})
        report(after.get("status") == "claimed",
               "F5 ★★★ claim 后详情回读是 claimed"
               "（退回内存账本时这里会读到 unassigned —— 就是改前的分叉）",
               repr(after.get("status")))
        report(after.get("version") == (v_before or 0) + 1,
               "F6 ★★★ 回读版本跟上写响应"
               "（版本对不上，界面就会说「请求已接受，但台账回读未完成」）",
               "%r → %r" % (v_before, after.get("version")))
    except Exception as exc:  # noqa: BLE001
        report(False, "F3 行为级", "%s: %s" % (type(exc).__name__, exc))
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("=" * 74)
    print("authority_review_reader · 台账摘要读 authority（开发装配回读一致性）")
    print("=" * 74)
    try:
        import base.authority_review_reader  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        untested("导入 base/authority_review_reader", str(exc))
        return 2
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    group_f()
    print("-" * 74)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
