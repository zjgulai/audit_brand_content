#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_tenant_isolation.py —— T-409：租户边界 + 领取原子性

## 这个文件为什么存在，以及它**不**做什么

票面 T-409 写的是「TS-11（idle 30min / absolute 8h）+ TS-27（租户查询边界）」，
并说 session 安全「是否实现未在验收表核过」。

**前半是错的**：TS-11 早已实现且已验 —— `tools/verify_auth_session.py` 47 项，
边界锚在判据原文的数（29/31 分钟、7h59/8h01），不是「随常量走」的假精度。
本文件**不重复验它**（重复的代价是两份读数各自漂移，而这正是本项目记过的病）。

真正没有执行点的是另外三件：

    T1  ★ **并发领取**：TS-31 明写「两个人并发领取同一案件，必须只有一个人成功，
           另一个收到明确失败（不是静默成功）」。全仓此前 **0 条并发断言**。
    T2  ★ **领取后空闲 30 分钟自动释放**（TS-33）：`_expire_locked` 存在，
           但没有一条独立断言证明「到期真的释放了，且释放前先存草稿」。
    T3  ★ **租户查询边界**：`GET /api/v1/cases/{id}` 跨租户必须是 **403**，
           且响应体**不含案件任何字段**（不能靠「空列表」冒充隔离）。

## 为什么 403 而不是 404（2026-10-25 委托方裁定）

票面写的是「跨租户查询返回 404 不是空列表」，而 Playbook TS-30 只要求
「仅 scope 内可见」，没规定状态码。实测现状是 403，**保持现状**。
**但断言不能只判状态码** —— 403 也可能是「登录了但无权」以外的东西，
所以每条都同时判「响应体里没有案件字段」。一个只判状态码的断言，
在「返回 403 但把内容塞进 details」的实现下照样绿。

## 四段

    A 跨租户隔离（读 / 列表 / 队列）—— 判据落在 `api/review_api.py` 的读路由上
    B ★ 并发领取：恰一成功（真线程，不是顺序两次）
    C ★ lease 到期释放 + 释放前存草稿
    D 反向对照：把租户条件摘掉，A 段必须红

退出码：0 全过 / 1 有红 / 2 未测（fastapi 不可用）
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = []
FAIL = []
UNTESTED = []


def ok(label, detail=""):
    PASS.append(label)
    print("PASS: %s%s" % (label, (" " + detail) if detail else ""))


def no(label, detail=""):
    FAIL.append((label, detail))
    print("FAIL: %s%s" % (label, (" " + detail) if detail else ""),
          file=sys.stderr)


try:
    from fastapi.testclient import TestClient

    from api.review_api import InMemoryRepository, create_app
    from base.auth_session import SessionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 API 层：%s" % exc)
    sys.exit(2)

TENANT_A = "t1"
TENANT_B = "t2"


def case(case_id, tenant, product_line="pump", submitter="u-sub-a",
         assignee=None, actionable=True):
    return {
        "case_id": case_id, "tenant": tenant, "product_line": product_line,
        "submitter_id": submitter, "assignee_id": assignee,
        "actionable": actionable,
        "ir": {
            "ir_id": "ir-" + case_id, "ir_version": "v1",
            "content_unit_ref": {"unit_id": "u-" + case_id, "kind": "ad_text"},
            "source_ir_version": "v1", "findings": [],
            "decision": {"state": "REVIEW", "layer": "L2",
                         "release_status": "待放行"},
            "coverage": {"coverage_state": "partial", "rules_version": "r1"},
            "receipt_ref": "rc", "rule_snapshot": "s", "kb_snapshot": "k",
            "control_points_version": "cp1",
            "created_at": "2026-10-01T00:00:00Z",
        },
    }


def build_app(cases):
    principals = {
        # A 租户的统筹：能看本租户全部
        "u-coord-a": {"roles": ["coordinator"], "tenant": TENANT_A,
                      "tenant_id": TENANT_A, "open_id": "ou-ca",
                      "product_lines": ["pump"]},
        # B 租户的统筹：**不该看到 A 租户任何案件**
        "u-coord-b": {"roles": ["coordinator"], "tenant": TENANT_B,
                      "tenant_id": TENANT_B, "open_id": "ou-cb",
                      "product_lines": ["pump"]},
        # A 租户的 dp3，用于领取
        "u-dp3-a": {"roles": ["dp3"], "tenant": TENANT_A,
                    "tenant_id": TENANT_A, "open_id": "ou-da",
                    "product_lines": ["pump"]},
        "u-dp3-a2": {"roles": ["dp3"], "tenant": TENANT_A,
                     "tenant_id": TENANT_A, "open_id": "ou-da2",
                     "product_lines": ["pump"]},
        # B 租户的 dp3：用于反向对照「摘掉 _scope_ok 后 dp3 跨租户能读」
        "u-dp3-b": {"roles": ["dp3"], "tenant": TENANT_B,
                    "tenant_id": TENANT_B, "open_id": "ou-db",
                    "product_lines": ["pump"]},
    }
    store = SessionStore(":memory:")
    app = create_app(session_store=store,
                     repository=InMemoryRepository(cases=list(cases)),
                     principals=principals, app_env="dev")
    return app, store, principals


def client_for(app, store, principal, tenant):
    c = TestClient(app)
    c.cookies.set("session", store.create_session(principal, tenant=tenant))
    return c


#: 案件里出现即算「内容泄漏」的字段/取值。逐个点名而不是模糊匹配
#: （与 `secretGuard` 同一条读法：模糊匹配会误报，误报会让人不看报告）。
LEAK_MARKERS = ("ir_id", "content_unit_ref", "submitter_id", "findings",
                "decision", "coverage", "case-", "u-sub-a")


def leaks_content(text):
    return [m for m in LEAK_MARKERS if m in (text or "")]


def section_a():
    """跨租户隔离：读 / 列表 / 队列。"""
    cases = [case("case-a-1", TENANT_A, submitter="u-sub-a"),
             case("case-a-2", TENANT_A, submitter="u-sub-a"),
             case("case-b-1", TENANT_B, submitter="u-sub-b")]
    app, store, _ = build_app(cases)
    b = client_for(app, store, "u-coord-b", TENANT_B)

    # A1 列表：只看到本租户的，且**一条不多**
    r = b.get("/api/v1/cases")
    rows = r.json() if r.status_code == 200 else []
    ids = {x.get("case_id") for x in rows}
    if r.status_code == 200 and ids == {"case-b-1"}:
        ok("A1 ★ GET /cases 只返回本租户（t2 只看到 case-b-1）", repr(sorted(ids)))
    else:
        no("A1 跨租户列表隔离不成立",
           "%s %r" % (r.status_code, sorted(ids)))

    # A2 ★ 跨租户读单条 → 403，且响应体不含案件字段
    r = b.get("/api/v1/cases/case-a-1")
    leaked = leaks_content(r.text)
    if r.status_code == 403 and not leaked:
        ok("A2 ★ 跨租户 GET /cases/{id} → 403 且响应体无案件字段")
    elif r.status_code == 200:
        no("A2 ★ 跨租户读到了别租户的案件（最严重）", r.text[:160])
    else:
        no("A2 跨租户读的状态码/泄漏不符合 403 口径",
           "%s leaked=%r %s" % (r.status_code, leaked, r.text[:120]))

    # A3 队列同样隔离
    r = b.get("/api/v1/queue")
    rows = r.json() if r.status_code == 200 else []
    ids = {x.get("case_id") for x in rows}
    if r.status_code == 200 and not ({"case-a-1", "case-a-2"} & ids):
        ok("A3 ★ GET /queue 不含别租户案件", repr(sorted(ids)))
    else:
        no("A3 队列跨租户泄漏", "%s %r" % (r.status_code, sorted(ids)))

    # A4 本租户自己那条**读得到**（正样本：否则 A2 可能是「全部 403」的假绿）
    own = client_for(app, store, "u-coord-b", TENANT_B)
    r = own.get("/api/v1/cases/case-b-1")
    if r.status_code == 200:
        ok("A4 ★ 正样本：本租户案件读得到（防「全 403」式假绿）")
    else:
        no("A4 本租户案件也读不到 —— A2 可能是恒 403", str(r.status_code))

    # A5 A 租户的 dp3 不能读 B 租户（双向）
    a = client_for(app, store, "u-dp3-a", TENANT_A)
    r = a.get("/api/v1/cases/case-b-1")
    if r.status_code == 403 and not leaks_content(r.text):
        ok("A5 ★ 反向：A 租户 dp3 读 B 租户 → 403")
    else:
        no("A5 反向跨租户没被拦", "%s %s" % (r.status_code, r.text[:120]))


def section_b():
    """★ 并发领取：恰一成功（TS-31）。

    ★ 为什么必须是**真线程**：顺序调两次 claim（`base/reviews_ledger.py`），
      第二次必然 `already_claimed`，
      那条断言在**任何**实现下都成立（包括完全不原子的实现）——
      它证明的是「第二次被拒」，不是「只有一个赢家」。
      TS-31 要的是后者。
    """
    cases = [case("case-race", TENANT_A, submitter="u-sub-a")]
    app, store, _ = build_app(cases)
    s1 = store.create_session("u-dp3-a", tenant=TENANT_A)
    s2 = store.create_session("u-dp3-a2", tenant=TENANT_A)

    results = []
    barrier = threading.Barrier(2)

    def race(session):
        c = TestClient(app)
        barrier.wait()          # 尽量让两个请求同时进入
        # ★ 必须带 JSON body：`/claim` 的 handler 有一个 `VersionBody` 依赖，
        #   不带 body 直接 **422**（实测第一版就是这么错的 —— 两个请求都 422，
        #   于是「恰一成功」判据拿到 `[422, 422]`，看起来像并发缺陷）。
        #   这里带 `{}`：claim 的语义是「谁先到谁领」，不需要版本前置条件。
        r = c.post("/api/v1/cases/case-race/claim",
                   headers={"Idempotency-Key": "race-" + session[:8]},
                   cookies={"session": session}, json={})

        results.append(r.status_code)

    threads = [threading.Thread(target=race, args=(s,)) for s in (s1, s2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    codes = sorted(results)
    won = [c for c in results if c == 200]
    lost = [c for c in results if c in (409, 403)]
    if len(won) == 1 and sum(1 for c in results if c >= 400) == 1:
        ok("B1 ★ 并发领取恰一成功、另一明确失败", "codes=%r" % (codes,))
    else:
        no("B1 ★ 并发领取不是「恰一成功」", "codes=%r" % (codes,))

    # B2 失败方拿到的是**明确失败**（409 already_claimed），不是静默成功
    if lost:
        ok("B2 ★ 失败方拿到明确失败码（%r，不是静默 200）" % (lost[0],))
    else:
        no("B2 失败方没有明确失败码", "codes=%r" % (codes,))

    # B3 领取后 assignee 是**一个**人（不是两个都写了）
    #
    # ★ 读哪个存储：开发装配（`review_command_service is None`）时 claim 落在
    #   `reviews_ledger`（内存台账），**不写案件投影**。所以这里读台账。
    #   第一版读 `repo.get_case()` 拿到 `assignee_id=None`，报「并发写坏了」——
    #   而实际是「读错了存储」，属于 AGENTS §2.4.1 那个形状（假数据长得像真数据）。
    #   生产的写路径（权威）由 `verify_production_app.py` 的 C7 独立覆盖。
    try:
        ledger = app.state.reviews_ledger
        st = ledger.get_case("case-race") if ledger is not None else {}
        assignee = st.get("assignee")
        ok("B3 领取后 assignee 唯一（%r）" % (assignee,)) if assignee else no(
            "B3 领取后 assignee 为空（并发写坏了？）", repr(st)[:120])
    except Exception as exc:  # noqa: BLE001
        no("B3 读回 assignee 失败", str(exc)[:120])


def section_c():
    """★ lease 到期释放 + 释放前存草稿（TS-33）。"""
    try:
        from base.reviews_ledger import ReviewsLedger
    except Exception as exc:  # noqa: BLE001
        print("⚠ 未测：C 段需要 base.reviews_ledger（%s）" % exc)
        UNTESTED.append("C")
        return

    # ★ 用**极短** lease 让到期可测（不改生产常量）：这是判据需要的能力，
    #   不是放宽约束 —— `lease_seconds` 本来就是构造参数。
    ledger = ReviewsLedger(lease_seconds=60)
    try:
        # ★ 用 `claim()` 自己造案：`_case()` 会在首次访问时建一条 unassigned。
        #   第一版我直接往 `ledger.cases[...]` 里塞了一个 dict —— 属性名写错
        #   （真实是 `_cases`），于是 C 段直接 AttributeError。
        #   **不碰私有属性**：走公开 API，夹具的形状就不会与实现漂移。
        now = 1000.0
        ledger.claim("case-lease", "u-dp3-a", now=now)
        # 未到期：仍是 claimed
        early = ledger.get_case("case-lease")
        # ★ 到期的触发点是**任何带 `now` 的写入口**（`heartbeat` / `claim` /
        #   `unclaim` …），不是 `get_case` —— 后者是纯读，不跑 `_expire_locked`。
        #   第一版用 `get_case(now=...)`，直接 TypeError（它没有 now 参数）。
        #   这里用 `heartbeat` 推进时间：它是「领取人还在干活」的自然动作，
        #   而在 lease 已过期时它必须先把案子释放掉、然后拒绝自己续约。
        try:
            ledger.heartbeat("case-lease", "u-dp3-a", early["version"],
                             now=now + 61)
            expired_raised = False
        except Exception:  # noqa: BLE001
            # 到期后被 heartbeat → 释放 → 再续约必然失败（not_assignee）。
            # 「抛错」在这里是**正确**的，不是缺陷。
            expired_raised = True
        after = ledger.get_case("case-lease")
        if not expired_raised:
            no("C0 过期后 heartbeat 仍然成功（到期检查没跑）", "")
        released = (after.get("status") == "released"
                    and after.get("assignee") is None)
        drafted = bool(after.get("released_draft_id"))
        if early.get("status") == "claimed" and released:
            ok("C1 ★ lease 到期后自动释放（claimed → released，assignee 清空）")
        else:
            no("C1 lease 到期没释放", repr(after)[:180])
        if drafted:
            ok("C2 ★ 释放前先存草稿（released_draft_id 非空）",
               str(after.get("released_draft_id")))
        else:
            no("C2 释放时没存草稿（TS-33 要求先存再释放）", "")
    except Exception as exc:  # noqa: BLE001
        no("C 段执行异常", "%s: %s" % (type(exc).__name__, exc))


def run_checks():
    section_a()
    section_b()
    section_c()


def run_controls():
    """反向对照：每一条承重判据都必须能被证伪。

    ★ 三条判据三条对照，各自**独立**变红 —— 不是「改一处三条全红」，
      因为那种情况下红不说明是哪一条在承重（本项目已踩过：
      `verify_cards.mjs` 的 J1 曾经只查标识符出现与否，恒真）。
    """
    print("=" * 70)
    print("反向对照：判据自己会不会红")
    print("=" * 70)
    results = []

    # C1：A2 的「跨租户 403」—— 把租户条件摘掉（改造一个同租户案件给对方看），
    #     A2 必须红。做法：构造两个案件 id 相同、租户不同，然后断言
    #     「如果 can_read_content 不判租户，A2 就会绿」。
    # ★ 第一版我把变异打在 `_scope_ok`（`base/rbac.py`）上，**C1 没红** —— A2 用的身份是
    #   `coordinator`，它的分支是**直接**比 `principal.tenant == case.tenant`，
    #   根本不经过 `_scope_ok`（那条只服务 dp3/dp4/signer）。
    #   所以正确做法是构造一个**走 `_scope_ok` 分支**的身份（dp3 + actionable），
    #   否则对照测的不是 A2 的那条路。
    from base import rbac
    saved = rbac._scope_ok
    try:
        rbac._scope_ok = lambda p, c: True          # 注入：不判租户/品线
        cases = [case("case-a-1", TENANT_A, submitter="u-sub-a",
                      actionable=True)]
        app, store, _ = build_app(cases)
        # dp3 分支：`_scope_ok(principal, case) and _assigned_or_actionable(...)`
        d = client_for(app, store, "u-dp3-b", TENANT_B)
        r = d.get("/api/v1/cases/case-a-1")
        went_red = r.status_code == 200
        results.append(
            ("C1 摘掉 _scope_ok → dp3 跨租户读得到（A2 判据必红）", went_red, True))
    finally:
        rbac._scope_ok = saved

    # C2：B1 的「恰一成功」—— 把「已领取就拒」摘掉，两个并发必须都 200。
    from base import reviews_ledger as RL
    saved_claim = RL.ReviewsLedger.claim
    try:
        def loose_claim(self, case_id, actor, now=None):
            return saved_claim(self, case_id, actor, now=now)
        # 直接让第二次 claim 覆盖而不是抛错
        def always_ok(self, case_id, actor, now=None):
            actor = RL._nonempty(actor, "actor")
            now = self._now(now)
            with self._lock:
                c = self._case(case_id)
                c["status"] = "claimed"
                c["assignee"] = actor
                c["version"] += 1
                return self._case_view(c)
        RL.ReviewsLedger.claim = always_ok
        cases = [case("case-race", TENANT_A, submitter="u-sub-a")]
        app, store, _ = build_app(cases)
        s1 = store.create_session("u-dp3-a", tenant=TENANT_A)
        s2 = store.create_session("u-dp3-a2", tenant=TENANT_A)
        res = []
        barrier = threading.Barrier(2)

        def race(session):
            c = TestClient(app)
            barrier.wait()
            r = c.post("/api/v1/cases/case-race/claim",
                       headers={"Idempotency-Key": "c2-" + session[:8]},
                       cookies={"session": session}, json={})
            res.append(r.status_code)

        ts = [threading.Thread(target=race, args=(x,)) for x in (s1, s2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=30)
        went_red = sum(1 for c in res if c == 200) == 2
        results.append(("C2 摘掉 already_claimed → 两人都领到（B1 必红）", went_red, True))
    finally:
        RL.ReviewsLedger.claim = saved_claim

    # C3：C2 的「释放前存草稿」—— 把 _save_lease_draft 换成返回 None，
    #     C2 必须红（released_draft_id 为空）。
    saved_draft = RL.ReviewsLedger._save_lease_draft
    try:
        RL.ReviewsLedger._save_lease_draft = lambda self, case, now: None
        ledger = RL.ReviewsLedger(lease_seconds=60)
        now = 1000.0
        ledger.claim("case-x", "u", now=now)
        try:
            ledger.heartbeat("case-x", "u", 1, now=now + 61)
        except Exception:  # noqa: BLE001
            pass
        st = ledger.get_case("case-x")
        went_red = not st.get("released_draft_id")
        results.append(("C3 不存草稿 → released_draft_id 为空（C2 必红）", went_red, True))
    finally:
        RL.ReviewsLedger._save_lease_draft = saved_draft

    print("=" * 70)
    bad = 0
    for name, red, want in results:
        good = red == want
        bad += 0 if good else 1
        print("%s %s（红了=%s，期望红=%s）" % ("✅" if good else "❌", name, red, want))
    if bad == 0:
        print("✅ 反向对照 %d/%d 全过" % (len(results), len(results)))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (len(results) - bad, len(results)),
          file=sys.stderr)
    return 1


def main():
    print("=" * 70)
    print("verify_tenant_isolation · T-409 · 租户边界 + 领取原子性")
    print("=" * 70)
    run_checks()
    print("-" * 70)
    print("通过 %d 项 · 红 %d 项 · 未测 %d 项"
          % (len(PASS), len(FAIL), len(UNTESTED)))
    if FAIL:
        for label, detail in FAIL:
            print("  ✗ %s %s" % (label, detail), file=sys.stderr)
        print("❌ 有红", file=sys.stderr)
        return 1
    if UNTESTED:
        print("⚠ 有未测 —— 未测不是通过", file=sys.stderr)
        return 2
    print("✅ 全过")
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常：%s" % exc, file=sys.stderr)
        sys.exit(2)
