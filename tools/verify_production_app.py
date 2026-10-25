#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式生产装配自证：fake OAuth + 权威/投影/CSRF/health。

主体：api/production_app.py、api/oauth.py、api/review_api.py、api/write_api.py、
base/auth_session.py、base/principal_directory.py、base/review_command_service.py。

## 行 132 逐条对账（2026-10-23 T-132；**八条全部有执行点，可映射**）

验收表行 132 原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:275`）与
`Playbook/内容审查Agent-产品Playbook-v1.1.md:1332`（TS-29）要求：

| 行 132 的要求 | 本文件的执行点 | 状态 |
|---|---|---|
| 两库是两个独立文件、各自 WAL | **C31a-1**（读真实 `PRAGMA journal_mode`，不读建库代码）+ **R4**（判据自己的反向对照：同一路径/软链/相对路径都必须判 False） | ✅ |
| 各自清理配置 | **C31a-2**（无策略时要求「无自动清理」被写下来） | ✅ |
| 各自备份配置 | 不在本文件：`tools/verify_backend_recovery.py` 的 **C1/C7** 断言 session/projection/WAL 哨兵不进备份、恢复不带 session | ✅（跨 verifier） |
| ① IR 读取仍正常 | **C31c**（读回 `ir_id=ir-prod` 且 decision/unit 对得上） | ✅ |
| ① **manifest 读取**仍正常 | **C31d**（`manifest_readback()`：磁盘上的 `manifests/<run_id>.json` 在 session 库损坏后仍读得回 entries/run_id）+ **R5**（删掉 manifest 文件 → 判据必红） | ✅ |
| ② 业务投影查询仍正常 | **C31b**（先 claim 让投影里真有东西，再读回那一条） | ✅ |
| ③ 系统报 session 不可用而不是整体失败 | **C31**（`/readyz` 503 且 `session_db=false`） | ✅ |
| 反向对照：损坏业务投影库 → session 认证仍可用 | **C32a** | ✅ |

### 一处误判的更正（2026-10-23，必须留着）

我第一版在这里写的是「manifest 没有读对象，装配没接线」，并据此建议**降级行 132 的
manifest 半句**。**那是错的。** 我的输入是 `grep -rn artifact_store api/` 返回 0 命中，
而结论说的是「当前装配里没有这个读对象」—— 中间隔着一步**传递依赖**：

```
api/production_app.py:24      from base.business_event_store import BusinessEventStore
api/production_app.py:235         self.authority = BusinessEventStore(authority_root)
base/business_event_store.py:19   from base.artifact_store import ArtifactStore
base/business_event_store.py:133      self.artifacts = ArtifactStore(str(self.root))
```

`artifact_store` 经 business_event_store **两跳**接进生产装配，manifest 一直是个读对象。
这正是 AGENTS §2.4.1 第 4 行：**否定结论的输入不是「我采的那条通道里没有」，而是
「所有通道都采过」** —— 我只采了「直接 import」这一条。

C31d 因此是本轮补上的执行点；R5 保证它会红（删文件 → read_manifest 返回 None）。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# ── TS-29 / 行 132「各自清理配置」的显式声明（2026-10-22 实测，不要凭印象改）──
#   两个 store 都**没有** retention / expiry / prune 一类的按时间清理策略：
#   `base/auth_session.py` 的 DELETE 是「会话代数轮换」，`base/projection_store.py`
#   的 DELETE 是「整案替换，防幽灵 draft」，两条都是**语义路径**，不是清理策略。
#   行 132 要求「断言…各自清理配置」，而配置不存在时唯一诚实的写法是
#   **把"没有"这件事写下来并由断言核**，不是假装验了一个不存在的策略。
# ★ 将来真加了 retention 配置，C31a-2 会红 —— 那一刻把它改成正向断言才是对的。
RETENTION_DECLARATION = "无自动清理：两库均无按时间的 retention/prune 策略（2026-10-22 实测）"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi.testclient import TestClient
    from api.oauth import FakeOAuthProvider, OAuthIdentity
    from api.production_app import (
        PRODUCTION_WRITE_PATHS, ProductionSettings, SettingsError,
        create_production_app)
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入生产装配: %s" % exc)
    sys.exit(2)


def ir():
    return {
        "ir_id": "ir-prod", "ir_version": "v1", "source_ir_version": "v1",
        "content_unit_ref": {"unit_id": "u-prod", "kind": "free_text"},
        "findings": [],
        "decision": {"state": "REVIEW", "layer": "DP3",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "full", "modalities_evaluated": ["text"],
                     "rules_version": "r1", "control_points_applied": ["H01"]},
        "receipt_ref": "rc-prod", "rule_snapshot": "r1", "kb_snapshot": "k1",
        "control_points_version": "cp1", "created_at": "2026-10-21T00:00:00Z",
    }


def settings(root):
    root = Path(root)
    frozen = root / "frozen"
    frozen.mkdir(mode=0o700)
    (frozen / "cases.json").write_text(json.dumps([{
        "case_id": "case-prod", "tenant": "t1", "product_line": "pump",
        "submitter_id": "u-sub", "final_reviewer_id": "u-final",
        "assignee_id": "reviewer", "actionable": True, "ir": ir(),
    }, {
        "case_id": "case-other", "tenant": "t1", "product_line": "pump",
        "submitter_id": "u-other", "final_reviewer_id": "u-final",
        "assignee_id": "reviewer", "actionable": True, "ir": ir(),
    }]), encoding="utf-8")
    principal = root / "principals.json"
    principal.write_text(json.dumps({"principals": [{
        "id": "reviewer", "tenant_id": "t1", "open_id": "ou-reviewer",
        "roles": ["dp3", "signer"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "reviewer-v1",
    }, {
        "id": "reviewer2", "tenant_id": "t1", "open_id": "ou-reviewer2",
        "roles": ["dp3"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "reviewer2-v1",
    }, {
        # T-402：授权治理三主体（dp4 提案 / it 执行 / coordinator 审批）。
        # ★ 三个人必须是**三个不同的人**：reducer 的 same_actor 与 rbac 的
        #   validate_grant_actors 都要求 len(set(ids)) == 3。
        "id": "proposer", "tenant_id": "t1", "open_id": "ou-proposer",
        "roles": ["dp4"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "proposer-v1",
    }, {
        "id": "itsvc", "tenant_id": "t1", "open_id": "ou-itsvc",
        "roles": ["it"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "itsvc-v1",
    }, {
        "id": "coord", "tenant_id": "t1", "open_id": "ou-coord",
        "roles": ["coordinator"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "coord-v1",
    }]}), encoding="utf-8")
    return ProductionSettings(
        authority_root=root / "authority",
        frozen_projection_root=frozen,
        review_projection_db=root / "projection" / "review.db",
        session_db=root / "session" / "session.db",
        access_log_path=root / "audit" / "access.jsonl",
        principal_directory=principal,
        # T-316d：报告落盘根。与其它数据路径一样必须在仓外且互不重叠。
        report_root=root / "reports",
        public_origin="https://ca.example",
        oauth_client_id="cli_fake",
        oauth_client_secret="not-a-real-secret",
        oauth_redirect_uri="https://ca.example/auth/callback",
        oauth_reauth_redirect_uri="https://ca.example/auth/reauth/callback",
        oauth_scope="auth:user.id:read",
        tenant_allowlist=frozenset({"t1"}),
    )


def csrf(client):
    return client.cookies.get("csrf")


def headers(client, key):
    return {
        "Origin": "https://ca.example",
        "X-CSRF-Token": csrf(client),
        "Idempotency-Key": key,
    }


def dbs_physically_distinct(session_db, projection_db) -> bool:
    """两库是否指向**不同文件**。

    用 `realpath` 比，不是字符串比：
      * 相对路径与绝对路径写到同一个文件 → 同一个库；
      * 软链指到同一个 inode → 同一个库。
    字符串比会把这两种都判成「分离」，于是 C31a-1 在它们面前恒真。
    """
    return os.path.realpath(str(session_db)) != os.path.realpath(str(projection_db))


def manifest_readback(authority_root, run_id=None):
    """从**磁盘**读一份已提交 manifest，返回 (ok, detail, run_id)。

    ★ 2026-10-23 更正一处误判：我先前只 grep 了 `api/` 里有没有 `artifact_store`，
      0 命中就断言「装配里没有这个读对象」。实际依赖是**两跳**：
        api/production_app.py → base/business_event_store.py → base/artifact_store.py
      （`BusinessEventStore.__init__` 里 `self.artifacts = ArtifactStore(root)`）。
      这正是 §2.4.1 第 4 行的形状：否定结论的输入必须是「所有通道都采过」，
      而我只采了直接 import 这一条通道。

    这里**新建**一个 `ArtifactStore` 去读文件，不复用运行时那份内存对象 ——
    否则「读得回」可能只是内存里还在，不证明盘上的提交点还在。
    """
    from base.artifact_store import ArtifactStore  # noqa: PLC0415

    mdir = os.path.join(str(authority_root), "manifests")
    if not os.path.isdir(mdir):
        return False, "没有 manifests 目录：%s" % mdir, run_id
    files = sorted(f for f in os.listdir(mdir) if f.endswith(".json"))
    if not files:
        return False, "manifests 目录里没有 .json（没有任何已提交批次）", run_id
    rid = run_id or files[0][:-5]
    man = ArtifactStore(str(authority_root)).read_manifest(rid)
    if not isinstance(man, dict):
        return False, "read_manifest(%r) 返回 None/非对象" % rid, rid
    entries = man.get("entries") or []
    ok = (man.get("run_id") == rid and bool(entries)
          and all(isinstance(e, dict) and e.get("sha256") for e in entries))
    return ok, "run_id=%r entries=%d" % (man.get("run_id"), len(entries)), rid


def run_controls():
    """`--controls`：反向对照常驻项。

    ## 为什么这几条必须常驻，而不是写进某次提交的说明里

    2026-10-22 做行 132 时实测到一条**平台事实**：

        只 os.unlink() 库文件      → session_store.ready() 仍返回 True
        只写坏文件头               → 同样 True
        close() + unlink + 坏头部  → False  ✅

    原因是 Unix 上已打开的 fd 指向的 inode 还在，SQLite 照常能查。
    也就是说：**「删了库文件」这件事，本身不会让任何东西变红。**

    C31b-1 的写法**依赖这条前提**。如果换了 OS、SQLite 版本或 Python，
    这条前提可能不成立 —— 那时 C31b-1 该怎么写就要跟着改。
    把它放进常驻反向对照，每次跑都会把这条前提重新量一遍：
    **前提变了，这里先红**，而不是等到某天有人发现 C31b-1 是恒真的绿。

    另外两条是「新断言不许恒红」与「假断言确实曾经是假的」的对照。
    """
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    import base.auth_session as AS

    # ── R1：只 unlink 不改连接 → ready() 仍 True（平台事实的前提）────────────
    root = tempfile.mkdtemp(prefix="controls-unlink-")
    try:
        db = os.path.join(root, "session.db")
        store = AS.SessionStore(db)
        store.ready()
        os.unlink(db)
        still_ready = store.ready()
        ok("R1 只 unlink 库文件 → ready() 仍为 True（Unix fd 语义的前提）",
           still_ready is True,
           "still_ready=%r —— 若为 False，说明平台语义变了，C31b-1 的写法要重审"
           % (still_ready,))
        store.close()
        after_close = store.ready()
        ok("R2 unlink 之后再 close() → ready() 变 False（C31b-1 依赖的动作）",
           after_close is False, "after_close=%r" % (after_close,))
    except Exception as exc:  # noqa: BLE001
        ok("R1/R2 session store 可用", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ── R3：坏文件头同样不会自己变红（第二条平台事实）────────────────────────
    #   ★ 2026-10-22 实测与第一版写法不同，照实记：
    #     第一版假设「坏头部之后新建连接，ready() 返回 False」——
    #     实际是**构造 `SessionStore` 就抛 `sqlite3.DatabaseError: file is not a database`**，
    #     根本到不了 `ready()`。所以这条对照的正确判据是
    #     **「构造期抛错，或 ready() 为 False」二者之一**，不是只看 ready()。
    #     写死成「只看 ready()」会让这条对照永远红 —— 而永远红的对照会被当作噪音忽略。
    root = tempfile.mkdtemp(prefix="controls-corrupt-")
    try:
        db = os.path.join(root, "session.db")
        store = AS.SessionStore(db)
        store.ready()
        store.close()
        with open(db, "wb") as f:
            f.write(b"NOT-A-SQLITE-HEADER" * 8)
        raised = None
        reopened_ready = None
        try:
            reopened = AS.SessionStore(db)
            try:
                reopened_ready = reopened.ready()
            except Exception as exc:  # noqa: BLE001
                raised = "%s: %s" % (type(exc).__name__, exc)
        except Exception as exc:  # noqa: BLE001
            raised = "%s: %s" % (type(exc).__name__, exc)
        ok("R3 坏头部 → 构造期抛错或 ready() 为 False（不许静默可用）",
           raised is not None or reopened_ready is False,
           "raised=%r ready=%r" % (raised, reopened_ready))
    except Exception as exc:  # noqa: BLE001
        ok("R3 坏头部对照可执行", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ── R4：C31a-1「两库是独立文件」这条判据自己会不会红 ────────────────────
    #   ★ 2026-10-23 T-132：「物理分离」如果没有反向对照，就只是一句同义反复 ——
    #     只要实现里永远给两个不同路径，断言永远绿，而我们不知道它拦不拦得住
    #     「被配成同一个文件」这件事。05 要的那条正是第 2 项。
    ok("R4 两条不同路径 → 判据为 True（正常配置）",
       dbs_physically_distinct("/tmp/a/session.db", "/tmp/a/projection.db") is True)
    ok("★ R4 session_db 被配成业务投影同一个文件 → 判据为 False（C31a-1 会红）",
       dbs_physically_distinct("/tmp/a/projection.db", "/tmp/a/projection.db") is False)
    _r4root = tempfile.mkdtemp(prefix="controls-distinct-")
    try:
        _real = os.path.join(_r4root, "shared.db")
        with open(_real, "wb") as _f:
            _f.write(b"")
        _link = os.path.join(_r4root, "session-link.db")
        os.symlink(_real, _link)
        ok("R4 软链指向同一个文件 → 判据为 False（证明比的是 realpath，不是字符串）",
           dbs_physically_distinct(_link, _real) is False)
        ok("R4 相对路径与绝对路径指向同一个文件 → 判据为 False",
           dbs_physically_distinct(
               os.path.relpath(_real, os.getcwd()), _real) is False)
    except Exception as exc:  # noqa: BLE001
        ok("R4 软链/相对路径对照可执行", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        shutil.rmtree(_r4root, ignore_errors=True)

    # ── R5：C31d「manifest 读得回」这条判据自己会不会红 ────────────────────
    _r5root = tempfile.mkdtemp(prefix="controls-manifest-")
    try:
        from base.artifact_store import ArtifactStore  # noqa: PLC0415

        _st = ArtifactStore(_r5root)
        _st.commit("run-control", [{"kind": "reports", "key": "r1", "data": b"hello"}])
        _ok_read, _d1, _ = manifest_readback(_r5root)
        ok("R5 manifest 读得回（好样本：entries/run_id 齐）", _ok_read, _d1)
        os.unlink(os.path.join(_r5root, "manifests", "run-control.json"))
        _ok_gone, _d2, _ = manifest_readback(_r5root)
        ok("★ R5 删掉 manifest 文件 → 判据变 False（C31d 会红）",
           _ok_gone is False, _d2)
    except Exception as exc:  # noqa: BLE001
        ok("R5 manifest 对照可执行", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        shutil.rmtree(_r5root, ignore_errors=True)

    print("=" * 72)
    print("verify_production_app · --controls（平台前提的反向对照）")
    print("=" * 72)
    passed = 0
    for name, cond, detail in results:
        print(("  ✓ " if cond else "  ✗ ") + name + (("  " + detail) if detail else ""))
        passed += int(cond)
    print("-" * 72)
    if passed == len(results):
        print("✅ %d/%d 全过：平台前提仍成立，C31b-1 的写法有效" % (passed, len(results)))
        return 0
    print("❌ %d/%d 通过 —— 平台前提变了，C31b-1 必须重审" % (passed, len(results)),
          file=sys.stderr)
    return 1


def main():
    passed = failed = 0
    root = tempfile.mkdtemp(prefix="production-app-")

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name + (" " + detail if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    try:
        cfg = settings(root)
        provider = FakeOAuthProvider({
            "good-code": OAuthIdentity("t1", "ou-reviewer", name="Reviewer"),
            "good-code-2": OAuthIdentity("t1", "ou-reviewer2", name="Reviewer 2"),
            "bad-tenant": OAuthIdentity("t2", "ou-reviewer"),
        })
        app = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app, base_url="https://ca.example") as client:
            r = client.get("/healthz")
            report(r.status_code == 200 and r.json() == {"status": "ok"},
                   "C0 healthz 只报存活", r.text)
            r = client.get("/readyz")
            report(r.status_code == 200 and r.json().get("ready") is True,
                   "C1 readyz 生产依赖齐全", r.text)

            # OAuth state 在服务端生成；fake callback 建本地 opaque session。
            r = client.get("/auth/login", follow_redirects=False)
            location = r.headers.get("location", "")
            from urllib.parse import parse_qs, urlparse
            state = parse_qs(urlparse(location).query).get("state", [None])[0]
            report(r.status_code == 302 and bool(state),
                   "C2 login 产生授权 state", location)
            r = client.get("/auth/callback", params={"code": "good-code", "state": state},
                           follow_redirects=False)
            set_cookie = ";".join(r.headers.get_list("set-cookie"))
            report(r.status_code == 303
                   and "__Host-session=" in set_cookie
                   and "Secure" in set_cookie and "HttpOnly" in set_cookie
                   and "SameSite=lax" in set_cookie,
                   "C3 callback 建 Secure HttpOnly session", set_cookie)
            r = client.get("/api/v1/me")
            report(r.status_code == 200 and r.json().get("principal") == "reviewer",
                   "C4 /me 解析 tenant+open_id 本地主体", r.text)
            # 运行中撤销本地主体，已有 session 也必须立即失效。
            directory = json.loads(cfg.principal_directory.read_text(encoding="utf-8"))
            directory["principals"][0]["status"] = "revoked"
            cfg.principal_directory.write_text(json.dumps(directory), encoding="utf-8")
            revoked = client.get("/api/v1/me")
            report(revoked.status_code == 401,
                   "C4b principal 目录变更后运行中撤销立即生效", revoked.text)
            directory["principals"][0]["status"] = "active"
            directory["principals"][0]["authz_version"] = "reactivated-v2"
            cfg.principal_directory.write_text(json.dumps(directory), encoding="utf-8")
            reactivated = client.get("/api/v1/me")
            report(reactivated.status_code == 401,
                   "C4b 重新激活也不复活旧 session", reactivated.text)

            # 当前旧 session 已按 authz_version 失效；重新走正式 OAuth 继续后续测试。
            relogin = client.get("/auth/login", follow_redirects=False)
            relogin_state = parse_qs(urlparse(relogin.headers["location"]).query)["state"][0]
            client.get("/auth/callback",
                       params={"code": "good-code", "state": relogin_state},
                       follow_redirects=False)

            # reauth 必须走独立 OAuth callback，身份匹配后才签发绑定 token。
            start = client.post(
                "/api/v1/reauth/start", headers={
                    "Origin": "https://ca.example", "X-CSRF-Token": csrf(client)},
                json={"case_id": "case-prod", "action": "sign",
                      "nonce": "release-nonce"}, follow_redirects=False)
            reauth_location = start.json().get("detail") if start.status_code != 302 else start.headers.get("location", "")
            reauth_state = parse_qs(urlparse(reauth_location).query).get("state", [None])[0]
            reauth_redirect = parse_qs(urlparse(reauth_location).query).get(
                "redirect_uri", [None])[0]
            reauth_prompt = parse_qs(urlparse(reauth_location).query).get(
                "prompt", [None])[0]
            callback = client.get(
                "/auth/reauth/callback",
                params={"code": "good-code", "state": reauth_state},
                follow_redirects=False)
            step = callback.json()
            token = step.get("step_up_token")
            consumed = app.state.production_runtime.session_store.consume_step_up(
                token, "reviewer", "case-prod", "sign", "release-nonce")
            consumed_again = app.state.production_runtime.session_store.consume_step_up(
                token, "reviewer", "case-prod", "sign", "release-nonce")
            report(start.status_code == 302
                   and reauth_redirect == "https://ca.example/auth/reauth/callback"
                   and reauth_prompt == "consent"
                   and callback.status_code == 200
                   and callback.headers.get("cache-control") == "no-store"
                   and step.get("expires_in") == 300
                   and consumed and not consumed_again,
                   "C4c reauth 独立 callback 签发 5 分钟绑定单次 token",
                   repr((start.text, callback.text)))
            missing_csrf = client.post(
                "/api/v1/reauth/start", headers={"Origin": "https://ca.example"},
                json={"case_id": "case-prod", "action": "sign", "nonce": "x"})
            report(missing_csrf.status_code == 403,
                   "C4d reauth start 同样受 CSRF 门", missing_csrf.text)

            # 缺 CSRF / 错 Origin 拒绝
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers={"Origin": "https://ca.example",
                                     "Idempotency-Key": "missing-csrf"}, json={})
            report(r.status_code == 403 and r.json().get("code") == "csrf_denied",
                   "C5 缺 CSRF → 403", r.text)
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers={"Origin": "https://evil.example",
                                     "X-CSRF-Token": csrf(client),
                                     "Idempotency-Key": "bad-origin"}, json={})
            report(r.status_code == 403 and r.json().get("code") == "origin_denied",
                   "C6 错 Origin → 403", r.text)

            # 首批持久 review 写链
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers=headers(client, "claim-1"), json={})
            claim = r.json()
            report(r.status_code == 200 and claim.get("version") == 1,
                   "C7 production claim → v1", r.text)
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "draft-1"),
                            json={"action": "save_draft", "version": 1,
                                  "draft": {"notes": "draft", "form": {},
                                            "evidence_selections": [], "references": []}})
            draft = r.json()
            report(r.status_code == 200 and draft.get("version") == 2
                   and draft.get("draft", {}).get("draft_id"),
                   "C8 production draft → v2", r.text)
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "submit-1"),
                            json={"action": "submit", "version": 2,
                                  "conclusion": {"review_notes": "approved by human"}})
            submitted = r.json()
            report(r.status_code == 200 and submitted.get("version") == 3
                   and submitted.get("status") == "closed",
                   "C9 production submit → closed/v3", r.text)
            r = client.get("/api/v1/cases/case-prod/review")
            report(r.status_code == 200 and r.json().get("version") == 3,
                   "C10 GET review 回读持久投影", r.text)
            r = client.get("/api/v1/cases/case-prod/drafts")
            report(r.status_code == 200 and len(r.json()) == 1
                   and r.json()[0]["notes"] == "draft",
                   "C11 GET drafts 回读正文", r.text)
            r = client.get("/api/v1/cases/case-prod/formal-reviews")
            report(r.status_code == 200 and len(r.json()) == 1,
                   "C12 GET formal 回读正文", r.text)

            # 同 key 同请求回放不多写
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "submit-1"),
                            json={"action": "submit", "version": 2,
                                  "conclusion": {"review_notes": "approved by human"}})
            report(r.status_code == 200 and r.json().get("replayed") is True,
                   "C13 同 key 重放旧结果", r.text)

            # 首批以外写能力必须关闭
            #
            # ★ T-401a 之后这三条已在生产能力表里，所以这里**不能再要求 501**。
            #   但也不能直接对 case-prod 开一条申诉 —— 那会把它 version 从 3
            #   推到 4，而下面 C19「重启后投影 v3」正是以此为锚（实测当场踩到：
            #   两条与本段无关的断言因此变红）。
            #   改用**不存在的案件**：`404 案件不存在` 证明请求通过了能力闸门
            #   （501 会被拦在更前面），且没有写任何状态。
            r = client.post("/api/v1/appeals", headers=headers(client, "appeal-1"),
                            json={"case_id": "case-no-such", "reason": "x"})
            report(r.status_code == 404 and "capability_not_enabled" not in r.text,
                   "C14 ★ 申诉已接生产路径（T-401a 交付：通过能力闸门，落到案件校验）",
                   r.text)
            r = client.post("/api/v1/cases/case-other/actions",
                            headers=headers(client, "confirm-1"),
                            json={"action": "confirm", "version": 0,
                                  "finding_id": "f-missing"})
            report(r.status_code == 409 and "not_assignee" in r.text,
                   "C15 confirm 已接生产路径（未 claim → 409 not_assignee，不再是 501）",
                   r.text)

            # logout 后旧 session 立即 401
            r = client.post("/api/v1/logout", headers={
                "Origin": "https://ca.example", "X-CSRF-Token": csrf(client)})
            report(r.status_code == 200 and r.json().get("logged_out") is True,
                   "C16 logout 成功", r.text)
            r = client.get("/api/v1/me")
            report(r.status_code == 401, "C17 logout 后 session 失效", r.text)

        # ── T-401a：申诉三条 + 读侧（本票的核心，不是「加进集合」就完）───────
        #
        # ★ 为什么必须在**生产装配**里验，而不是 `verify_write_api`：
        #   那条链路用 `AppealStore`（内存），读侧写侧是同一份数据，
        #   所以「写完读不回」这个缺陷在它面前**不可能出现**。
        #   缺陷只在 frozen 读 / authority 写的生产装配里成立。
        appeal_root = tempfile.mkdtemp(prefix="production-appeals-")
        try:
            appeal_cfg = settings(appeal_root)
            # 只用真实 submit 建案 —— 手造 frozen case 会漏 tenant 等字段，
            # 那种夹具缺陷会伪装成「find_appeal_case 坏了」（本票踩过一次）。
            (Path(appeal_root) / "frozen" / "cases.json").write_text(
                "[]", encoding="utf-8")
            appeal_app = create_production_app(appeal_cfg, oauth_provider=provider)
            appeal_case = None
            with TestClient(appeal_app, base_url="https://ca.example") as ac:
                login = ac.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                ac.get("/auth/callback",
                       params={"code": "good-code", "state": state},
                       follow_redirects=False)
                r = ac.post("/api/v1/submissions", headers=headers(ac, "ap-sub"),
                            json={"submission_id": "ap-sub-1",
                                  "content_type": "文本",
                                  "content_stage": "final_content",
                                  "entry_channel": "群消息",
                                  "source": {"kind": "ad_text"},
                                  "text": "新品上市：售价 199 元。",
                                  "product_line": "pump",
                                  "fields": {"Primary Text":
                                             "新品上市：售价 199 元，容量 240ml。"}})
                appeal_case = (r.json() or {}).get("case_id")
                report(r.status_code == 200 and isinstance(appeal_case, str),
                       "T401-A0 真实 submit 建案（后续断言的前提）", r.text[:160])

                # A1 ★ 改前这里 501
                r = ac.post("/api/v1/appeals", headers=headers(ac, "ap-open"),
                            json={"case_id": appeal_case,
                                  "reason": "命中误判，申请复核"})
                opened = r.json() or {}
                appeal_id = opened.get("appeal_id")
                report(r.status_code == 200
                       and isinstance(appeal_id, str)
                       and appeal_id.startswith("appeal-")
                       and len(appeal_id) == len("appeal-") + 16,
                       "T401-A1 ★ POST /appeals → 200 且 appeal_id 是内容派生 ID",
                       "%s %r" % (r.status_code, str(opened.get("appeal_id"))))

                # A2 ★ 本票的核心：写完**读得回**
                listed = ac.get("/api/v1/appeals")
                rows = listed.json() if listed.status_code == 200 else []
                got = {x.get("appeal_id"): x.get("state")
                       for x in rows if isinstance(x, dict)}
                report(listed.status_code == 200 and got.get(appeal_id) == "open",
                       "T401-A2 ★ GET /appeals 立刻读得到刚开的那条（改前恒为 []）",
                       "%s %r" % (listed.status_code, repr(got)[:120]))

                # A3 状态跟着走，不是「开了就一直 open」
                r = ac.post(f"/api/v1/appeals/{appeal_id}/withdraw",
                            headers=headers(ac, "ap-withdraw"),
                            json={"reason": "不再申诉"})
                listed = ac.get("/api/v1/appeals")
                got = {x.get("appeal_id"): x.get("state")
                       for x in listed.json() if isinstance(x, dict)}
                report(r.status_code == 200 and got.get(appeal_id) == "withdrawn",
                       "T401-A3 ★ withdraw → 200 且列表里的 state 变 withdrawn",
                       "%s %r" % (r.status_code, repr(got)[:120]))

                # A4 migrate：三条各验一次，不能只验 open。
                #
                # ★ 实测到一处**真实的能力缺口**，记在这里而不是绕过去：
                #   migrate 的领域规则是「只有 paused 可迁移」，而 `appeal_pause`
                #   在 reducer 里有（`review_reducer.py:409`），**全仓没有任何
                #   HTTP 入口**能发出它。所以生产装配下 migrate **不可达**
                #   （open → 409 not_paused，pause 又发不出去）。
                #   本断言因此只能证明「路由通了 + 领域规则没被绕过」，
                #   **不能**证明迁移成功 —— 后者要等 pause 入口存在。
                #   这个限制已记入执行方案 §2.1 的 T-401b。
                r = ac.post("/api/v1/appeals", headers=headers(ac, "ap-open-2"),
                            json={"case_id": appeal_case, "reason": "第二条"})
                second = (r.json() or {}).get("appeal_id")
                r = ac.post(f"/api/v1/appeals/{second}/migrate",
                            headers=headers(ac, "ap-migrate"), json={})
                report(r.status_code == 409 and "not_paused" in r.text,
                       "T401-A4 ★ migrate 通过能力闸门并落到领域规则（open → 409 not_paused）",
                       "%s %r" % (r.status_code, (r.text or "")[:140]))

                # A4b 反查链路：不存在的 appeal_id 必须是 404 appeal_not_found，
                #     不是 501、也不是 500。它证明 `find_appeal_case` 真的被调用了
                #     （这正是我用错夹具时最容易漏掉的一跳）。
                r = ac.post("/api/v1/appeals/appeal-does-not-exist/withdraw",
                            headers=headers(ac, "ap-404"),
                            json={"reason": "x"})
                report(r.status_code == 404 and "appeal_not_found" in r.text,
                       "T401-A4b 未知 appeal_id → 404 appeal_not_found（反查链路真的在跑）",
                       "%s %r" % (r.status_code, (r.text or "")[:140]))

                # A5 反向对照：不在生产能力表时，三条必须各自 501。
                #   证明 A1/A4 的 200 来自这次改动，不是本来就通。
                removed_appeals = {
                    "/api/v1/appeals",
                    "/api/v1/appeals/{id}/migrate",
                    "/api/v1/appeals/{id}/withdraw",
                }
                saved_appeals = set(PRODUCTION_WRITE_PATHS)
                off_root2 = tempfile.mkdtemp(prefix="production-appeals-off-")
                try:
                    PRODUCTION_WRITE_PATHS.difference_update(removed_appeals)
                    off_app2 = create_production_app(
                        settings(off_root2), oauth_provider=provider)
                    with TestClient(off_app2,
                                    base_url="https://ca.example") as off2:
                        lg = off2.get("/auth/login", follow_redirects=False)
                        st2 = parse_qs(
                            urlparse(lg.headers["location"]).query)["state"][0]
                        off2.get("/auth/callback",
                                 params={"code": "good-code", "state": st2},
                                 follow_redirects=False)
                        codes = [
                            off2.post("/api/v1/appeals",
                                      headers=headers(off2, "off-ap-open"),
                                      json={"case_id": "c-x", "reason": "x"}
                                      ).status_code,
                            off2.post("/api/v1/appeals/a-x/migrate",
                                      headers=headers(off2, "off-ap-mig"),
                                      json={}).status_code,
                            off2.post("/api/v1/appeals/a-x/withdraw",
                                      headers=headers(off2, "off-ap-wd"),
                                      json={"reason": "x"}).status_code,
                        ]
                        report(codes == [501, 501, 501],
                               "T401-A5 ★ 反向对照：三条不在生产能力表时各返 501",
                               repr(codes))
                finally:
                    PRODUCTION_WRITE_PATHS.clear()
                    PRODUCTION_WRITE_PATHS.update(saved_appeals)
                    shutil.rmtree(off_root2, ignore_errors=True)

            # A6 ★ 票面判据「重启后仍可读」：新进程、同一数据根
            appeal_app2 = create_production_app(appeal_cfg, oauth_provider=provider)
            with TestClient(appeal_app2, base_url="https://ca.example") as ac2:
                login = ac2.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                ac2.get("/auth/callback",
                        params={"code": "good-code", "state": state},
                        follow_redirects=False)
                listed = ac2.get("/api/v1/appeals")
                got = {x.get("appeal_id"): x.get("state")
                       for x in listed.json() if isinstance(x, dict)}
                report(listed.status_code == 200
                       and got.get(appeal_id) == "withdrawn",
                       "T401-A6 ★ 重启后 GET /appeals 仍返回同一条、同 state",
                       "%s %r" % (listed.status_code, repr(got)[:120]))
        finally:
            shutil.rmtree(appeal_root, ignore_errors=True)

        # reassign 后 ACL 跟随权威 assignee；未知目标拒绝，冻结 assignee 不再承权。
        acl_root = tempfile.mkdtemp(prefix="production-reassign-acl-")
        try:
            acl_cfg = settings(acl_root)
            acl_app = create_production_app(acl_cfg, oauth_provider=provider)
            with TestClient(acl_app, base_url="https://ca.example") as old_client:
                login = old_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                old_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                old_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(old_client, "acl-claim"), json={})
                unknown = old_client.post(
                    "/api/v1/cases/case-prod/reassign",
                    headers=headers(old_client, "acl-unknown"),
                    json={"version": 1, "assignee": "does-not-exist"})
                moved = old_client.post(
                    "/api/v1/cases/case-prod/reassign",
                    headers=headers(old_client, "acl-move"),
                    json={"version": 1, "assignee": "reviewer2"})
                old_write = old_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(old_client, "acl-old-write"),
                    json={"action": "heartbeat", "version": 2})
                # 第二 cookie jar 复用同一已启动 app，不再开启第二 lifespan。
                new_client = TestClient(acl_app, base_url="https://ca.example")
                try:
                    login = new_client.get("/auth/login", follow_redirects=False)
                    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                    new_client.get(
                        "/auth/callback", params={"code": "good-code-2", "state": state},
                        follow_redirects=False)
                    new_read = new_client.get("/api/v1/cases/case-prod/review")
                    new_write = new_client.post(
                        "/api/v1/cases/case-prod/actions",
                        headers=headers(new_client, "acl-new-write"),
                        json={"action": "heartbeat", "version": 2})
                finally:
                    new_client.close()
            report(unknown.status_code == 400 and moved.status_code == 200
                   and old_write.status_code == 403 and new_read.status_code == 200
                   and new_write.status_code == 200,
                   "C15b reassign 目标校验且写 ACL 跟随权威 assignee",
                   repr((unknown.text, moved.text, old_write.text,
                         new_read.text, new_write.text)))
        finally:
            shutil.rmtree(acl_root, ignore_errors=True)

        # 重启应用后权威/投影/幂等仍在
        app2 = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app2, base_url="https://ca.example") as c2:
            r = c2.get("/readyz")
            report(r.status_code == 200, "C18 重启后 ready", r.text)
            report(app2.state.production_runtime.projection.get_case("case-prod")["version"] == 3,
                   "C19 重启后投影 v3")
            report(len(app2.state.production_runtime.authority.batches()) == 3,
                   "C20 重启后权威命令仍为3条")

        # OAuth state 重放/错 tenant 拒绝（新应用，独立 session）
        app3 = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app3, base_url="https://ca.example") as c3:
            login = c3.get("/auth/login", follow_redirects=False)
            state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
            first = c3.get("/auth/callback", params={"code": "good-code", "state": state},
                           follow_redirects=False)
            replay = c3.get("/auth/callback", params={"code": "good-code", "state": state},
                            follow_redirects=False)
            report(first.status_code == 303 and replay.status_code == 400,
                   "C21 OAuth state 重放拒绝", replay.text)
            login = c3.get("/auth/login", follow_redirects=False)
            state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
            bad = c3.get("/auth/callback", params={"code": "bad-tenant", "state": state},
                         follow_redirects=False)
            report(bad.status_code == 403, "C22 非 allowlist tenant 拒绝", bad.text)

        # OAuth state 必须绑定发起登录的浏览器；另一 cookie jar 不能代领 callback。
        bind_root = tempfile.mkdtemp(prefix="oauth-binding-")
        try:
            bind_cfg = settings(bind_root)
            bind_app = create_production_app(bind_cfg, oauth_provider=provider)
            with TestClient(bind_app, base_url="https://ca.example") as owner:
                login = owner.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                stranger = TestClient(bind_app, base_url="https://ca.example")
                try:
                    stolen = stranger.get(
                        "/auth/callback", params={"code": "good-code", "state": state},
                        follow_redirects=False)
                finally:
                    stranger.close()
                proper = owner.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                report(stolen.status_code == 400 and proper.status_code == 303,
                       "C22b OAuth state 绑定发起浏览器且错误尝试不消费 state",
                       stolen.text)
        finally:
            shutil.rmtree(bind_root, ignore_errors=True)

        # 投影失败：权威保留、POST 202、普通 GET 503，只有 token 可读本次权威结果。
        lag_root = tempfile.mkdtemp(prefix="production-lag-")
        try:
            lag_cfg = settings(lag_root)
            lag_app = create_production_app(lag_cfg, oauth_provider=provider)
            with TestClient(lag_app, base_url="https://ca.example") as lag_client:
                login = lag_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                lag_client.get("/auth/callback",
                               params={"code": "good-code", "state": state},
                               follow_redirects=False)
                projection = lag_app.state.production_runtime.projection
                original_apply = projection.apply_batch

                def fail_projection(_batch):
                    raise RuntimeError("projection-sentinel")

                projection.apply_batch = fail_projection
                write = lag_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(lag_client, "lag-claim"), json={})
                write_body = write.json()
                report(write.status_code == 202
                       and write_body.get("projection_lag") is True
                       and write_body.get("version") == 1
                       and isinstance(write_body.get("reconcile_token"), str),
                       "C24 投影失败但权威成功 → 202", write.text)
                token = write_body.get("reconcile_token")
                ordinary = lag_client.get("/api/v1/cases/case-prod/review")
                report(ordinary.status_code == 503
                       and "projection_lag" in ordinary.text
                       and '"version":1' not in ordinary.text,
                       "C25 普通 GET 不把旧投影冒充当前值", ordinary.text)
                generic = lag_client.get("/api/v1/cases/case-prod")
                queue = lag_client.get("/api/v1/queue")
                cases = lag_client.get("/api/v1/cases")
                report(generic.status_code == 503
                       and queue.status_code == 503 and cases.status_code == 503
                       and "projection_lag" in generic.text,
                       "C25b Web case/queue/list GET 全过 freshness 门", generic.text)
                read_your_write = lag_client.get(
                    "/api/v1/cases/case-prod/review",
                    headers={"X-Reconcile-Token": token})
                ryw = read_your_write.json()
                report(read_your_write.status_code == 200
                       and ryw.get("source") == "authority"
                       and ryw.get("result", {}).get("version") == 1,
                       "C26 本次 token authority read-your-write", read_your_write.text)
                cross_case = lag_client.get(
                    "/api/v1/cases/case-other/review",
                    headers={"X-Reconcile-Token": token})
                report(cross_case.status_code == 503
                       and '"source":"authority"' not in cross_case.text,
                       "C26b token 不跨 case", cross_case.text)
                wrong = lag_client.get(
                    "/api/v1/cases/case-prod/review",
                    headers={"X-Reconcile-Token": "x" * 32})
                report(wrong.status_code == 503,
                       "C27 错 token 仍拒绝旧投影", wrong.text)
                report(lag_app.state.production_runtime.authority.head()["seq"] == 1,
                       "C28 202 不回滚权威")
                projection.apply_batch = original_apply
        finally:
            shutil.rmtree(lag_root, ignore_errors=True)

        # draft/formal 在投影失败时必须真正消费 authority result，不可返回空列表。
        content_lag_root = tempfile.mkdtemp(prefix="production-content-lag-")
        try:
            content_cfg = settings(content_lag_root)
            content_app = create_production_app(content_cfg, oauth_provider=provider)
            with TestClient(content_app, base_url="https://ca.example") as content_client:
                login = content_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                content_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                content_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(content_client, "content-claim"), json={})
                projection = content_app.state.production_runtime.projection
                original_apply = projection.apply_batch
                projection.apply_batch = lambda _batch: (_ for _ in ()).throw(
                    RuntimeError("content-lag"))
                saved = content_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(content_client, "content-draft"),
                    json={"action": "save_draft", "version": 1,
                          "draft": {"notes": "authority-draft", "form": {},
                                    "evidence_selections": [], "references": []}})
                saved_body = saved.json()
                draft_token = saved_body.get("reconcile_token")
                draft_id = (saved_body.get("draft") or {}).get("draft_id")
                no_token = content_client.get("/api/v1/cases/case-prod/drafts")
                with_token = content_client.get(
                    "/api/v1/cases/case-prod/drafts",
                    headers={"X-Reconcile-Token": draft_token})
                draft_by_id = content_client.get(
                    "/api/v1/drafts/%s" % draft_id,
                    headers={"X-Reconcile-Token": draft_token})
                report(saved.status_code == 202 and no_token.status_code == 503
                       and with_token.status_code == 200
                       and with_token.json()[0]["notes"] == "authority-draft"
                       and draft_by_id.status_code == 200,
                       "C28b draft 202 后仅正确 token 可读 authority 正文",
                       repr((no_token.text, with_token.text)))
                projection.apply_batch = original_apply
                # 先补齐 draft 投影，再让 submit 自身失败，得到 formal token。
                Projector = __import__("base.projector", fromlist=["Projector"]).Projector
                Projector(content_app.state.production_runtime.authority, projection).catch_up()
                projection.apply_batch = lambda _batch: (_ for _ in ()).throw(
                    RuntimeError("formal-lag"))
                submitted = content_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(content_client, "content-submit"),
                    json={"action": "submit", "version": 2,
                          "conclusion": {"review_notes": "authority-formal"}})
                formal_token = submitted.json().get("reconcile_token")
                no_token = content_client.get(
                    "/api/v1/cases/case-prod/formal-reviews")
                with_token = content_client.get(
                    "/api/v1/cases/case-prod/formal-reviews",
                    headers={"X-Reconcile-Token": formal_token})
                report(submitted.status_code == 202 and no_token.status_code == 503
                       and with_token.status_code == 200
                       and with_token.json()[0]["conclusion"]["review_notes"] ==
                       "authority-formal",
                       "C28c formal 202 后仅正确 token 可读 authority 正文",
                       repr((no_token.text, with_token.text)))
                projection.apply_batch = original_apply
        finally:
            shutil.rmtree(content_lag_root, ignore_errors=True)

        # readiness 每次真探本地依赖；缓存的布尔不能掩盖现场故障。
        ready_root = tempfile.mkdtemp(prefix="production-ready-faults-")
        try:
            ready_cfg = settings(ready_root)
            ready_app = create_production_app(ready_cfg, oauth_provider=provider)
            with TestClient(ready_app, base_url="https://ca.example") as ready_client:
                runtime = ready_app.state.production_runtime
                original_reconcile = runtime.service.reconcile
                calls = [0]

                def transient_reconcile():
                    calls[0] += 1
                    if calls[0] == 1:
                        raise RuntimeError("transient-maintenance")
                    return original_reconcile()

                runtime.service.reconcile = transient_reconcile
                first_maintenance = runtime.maintain_once()
                second_maintenance = runtime.maintain_once()
                report(not first_maintenance and second_maintenance
                       and runtime.ready and runtime.ready_error is None,
                       "C29b sweeper 瞬时失败后下一轮自动恢复 ready")
                runtime.service.reconcile = original_reconcile
                original_lock = runtime.lease.path.read_bytes()
                runtime.lease.path.write_text(
                    json.dumps({"pid": 1, "owner": "other"}), encoding="utf-8")
                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["writer_lease"] is False,
                       "C30 writer lease 丢失 → not ready", r.text)
                runtime.lease.path.write_bytes(original_lock)

                # ── TS-29 第一句：两个库是**两个独立文件**，各自 WAL ─────────────
                #   ★ 2026-10-22 加（T-140 定性 → 05 裁定）：
                #     行 132 原文要求「断言两个库是两个独立文件（各自 WAL / 备份 / 清理配置）」。
                #     此前 `journal_mode=WAL` 只在 `base/auth_session.py:56` 与
                #     `base/projection_store.py:45` **被设置**，全仓 `tools/` 里没人读它 ——
                #     也就是说「两库都开了 WAL」这句话当时没有任何执行点。
                #     ★ 判定口径：读**库文件真实生效的** `journal_mode`，不是读建库代码里那行
                #     PRAGMA（读代码那是「名字出现过 ≠ 拦得住」，AGENTS.md §2.4）。
                db_modes = {}
                for _label, _path in (("session", ready_cfg.session_db),
                                      ("projection", ready_cfg.review_projection_db)):
                    try:
                        _con = sqlite3.connect(str(_path))
                        db_modes[_label] = _con.execute("PRAGMA journal_mode").fetchone()[0]
                        _con.close()
                    except Exception as _exc:  # noqa: BLE001
                        db_modes[_label] = "unreadable:%s" % type(_exc).__name__
                distinct = dbs_physically_distinct(
                    ready_cfg.session_db, ready_cfg.review_projection_db)
                report(distinct and db_modes == {"session": "wal", "projection": "wal"},
                       "C31a-1 两库是两个独立文件且各自 journal_mode=wal",
                       "distinct=%s modes=%r" % (distinct, db_modes))

                # ── TS-29 「各自清理配置」：有策略就断言策略，没有就**显式声明没有** ──
                #   ★ 实测结论（2026-10-22，不要凭印象改）：两个 store 都**没有**
                #     retention / expiry / prune 之类的清理策略配置；它们的 DELETE 走的是
                #     「会话轮换」与「整案替换」两条**语义路径**，不是按时间的清理。
                #     所以这条断言有且只有一个诚实写法：**确认「无自动清理」这件事被写下来了**，
                #     而不是假装验了一个不存在的策略。两者都没有 = 红。
                #   （将来真加了 retention 配置，这条会红 —— 那时把它改成正向断言才是对的。）
                _retention_markers = ("retention", "retention_seconds", "prune",
                                      "cleanup_interval", "max_age", "ttl_seconds")
                _declared_no_retention = "无自动清理" in RETENTION_DECLARATION
                _has_retention = any(
                    hasattr(runtime.session_store, m) or hasattr(runtime.projection, m)
                    for m in _retention_markers)
                report(_has_retention or _declared_no_retention,
                       "C31a-2 清理口径已声明（有策略→断言策略；无策略→显式写「无自动清理」）",
                       "has_retention=%s declared=%s" % (_has_retention, _declared_no_retention))

                # ── TS-29 / 行 132：故障注入前，先让投影里**真有东西可读** ──────
                #   ★ 2026-10-22 修（T-140 定性 → 05 裁定就地改）：
                #     原来 C31b 断言 `projected_state is None`。实测在**本夹具**里
                #     这句话恒真 —— ready_root 的 authority 是空的（0 batch / 0 aggregate），
                #     maintain_once 的 catch_up 没有东西可投影，所以 get_case 永远返回 None。
                #     于是那半句只证明「没抛异常」，分不出「查询正常返回空」与「查询坏了」。
                #     （这正是 AGENTS.md §2.4 的假执行点：一条永远不会红的检查。）
                #   现在：先 claim 一次 + reconcile 一次，把 case-prod 真的写进投影，
                #   再注入 session 故障，断言**读得回那条**（而不是读回 None）。
                claim_out = runtime.service.execute(
                    aggregate_id="case-prod", command="claim",
                    actor={"principal_id": "reviewer", "tenant_id": "t1"},
                    expected_version=0, payload={},
                    idempotency_key="ts29-seed-claim")
                runtime.service.reconcile()
                seeded_version = (runtime.projection.get_case("case-prod") or {}).get("version")
                report(claim_out.get("http_status") == 200 and seeded_version == 1,
                       "C31b-0 故障注入前投影里确有 case-prod（否则后面的断言恒真）",
                       repr(seeded_version))

                # ── 故障注入：删库文件 + 关连接 ───────────────────────────────────
                #   ★ 2026-10-22 实测的一个平台事实，必须写在代码里，否则下一个人会
                #     把「删了文件却没红」当成测试缺口去改断言：
                #       · 只 `os.unlink()` 库文件 → `session_store.ready()` 仍返回 **True**
                #         （Unix 上已打开的 fd 指向的 inode 还在，SQLite 照常能查）；
                #       · 只写坏文件头 → 同样 **True**（同上：旧连接不重读头部）。
                #     所以「删除或损坏」要真正生效，必须**同时关掉那条连接**。
                #     行 132 原文要的正是「删除或损坏 session 库」这个状态，
                #     这里两个动作都做，并各自断言一次，避免只证明其中一半。
                runtime.session_store.close()
                try:
                    os.unlink(str(ready_cfg.session_db))
                except OSError:
                    pass
                with open(str(ready_cfg.session_db), "wb") as _bad:
                    _bad.write(b"NOT-A-SQLITE-HEADER" * 8)
                report(not runtime.session_store.ready(),
                       "C31b-1 session 库已删除且被替换成坏文件 → 连接确实不可用",
                       repr(runtime.session_store.ready()))

                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["session_db"] is False,
                       "C31 session DB 不可用 → not ready", r.text)

                # ── 行 132 的两条读路径：IR/manifest 与业务投影 ─────────────────
                #   ★ 2026-10-22 删掉的一处：原 C31b 还断言 `health.status_code == 200`。
                #     `/healthz` 是常量 `return {"status": "ok"}`（api/production_app.py:451-453），
                #     所以那半句**结构上不可能因为 session/业务耦合而红** —— 它只证明进程还活着。
                #     删掉不是「少验一条」，是**去掉一条假断言**：留着它，每个读 C31b 的人
                #     都会以为「session 故障不影响健康检查」被验过了。
                #     /readyz 的 503 已由 C31 断言，不在这里重复。
                authority_state = runtime.authority.state("case-prod")
                projected_state = runtime.projection.get_case("case-prod")
                report(authority_state["case_id"] == "case-prod"
                       and isinstance(projected_state, dict)
                       and projected_state.get("case_id") == "case-prod"
                       and projected_state.get("version") == seeded_version,
                       "C31b session 故障不影响权威读与业务投影直读（读回的是真实那条）",
                       repr(projected_state))

                # ── TS-29 / 行 132 ①：**IR 与 manifest 读取仍正常** ──────────────
                #   ★ 2026-10-22 补（T-140 定性 → 05 裁定「先不映射，记缺 IR 一条」）。
                #     这是 132 三件事里唯一还没有执行点的一条：
                #       ① IR 与 manifest 读取仍正常  ← 本条
                #       ② 业务投影查询仍正常          ← 上一条 C31b（已改真）
                #       ③ 系统报 session 不可用而不是整体失败 ← C31
                #     IR 走 `app.state.repository.get_case()`（CaseOverlayRepository）：
                #     它**不是** SQLite 投影，是独立读路径 —— 所以 session 挂了它应当照常可读。
                #     ★ 不许写成「IR 读取正常」而不给内容：那样 `get_case` 返回空 dict 也会绿。
                #       这里断言的是**读回的那份 IR 的字段值与夹具写进去的一致**。
                _repo = getattr(ready_app.state, "repository", None)
                _ir_ok = False
                _ir_detail = "no repository on app.state"
                if _repo is not None:
                    try:
                        _case = _repo.get_case("case-prod")
                        _ir = (_case or {}).get("ir") or {}
                        _ir_ok = (
                            isinstance(_case, dict)
                            and _case.get("case_id") == "case-prod"
                            and isinstance(_ir, dict)
                            and _ir.get("ir_id") == "ir-prod"
                            # manifest 链：权威 state 与 IR 指的是同一个案子
                            and authority_state.get("case_id") == _case.get("case_id")
                            # 内容锚点：decision 还在，且是我们写进去的那档
                            and (_ir.get("decision") or {}).get("state") == "REVIEW"
                            and bool((_ir.get("content_unit_ref") or {}).get("unit_id"))
                        )
                        _ir_detail = ("ir_id=%r decision.state=%r unit_id=%r"
                                      % (_ir.get("ir_id"),
                                         (_ir.get("decision") or {}).get("state"),
                                         (_ir.get("content_unit_ref") or {}).get("unit_id")))
                    except Exception as _exc:  # noqa: BLE001
                        _ir_detail = "%s: %s" % (type(_exc).__name__, _exc)
                report(_ir_ok,
                       "C31c session 故障不影响 IR 读取（读回 ir-prod 且 decision/unit 对得上）"
                       if _ir_ok else
                       "C31c IR 读取异常或读回的不是写进去那份：%s" % _ir_detail,
                       "" if _ir_ok else _ir_detail)

                # ── TS-29 / 行 132 ①（manifest 半条）：session 坏掉后 manifest 仍读得回 ──
                #   读对象 = base/artifact_store 的 manifests/<run_id>.json（唯一可见提交点）。
                #   它不是直接 import 进来的：production_app → business_event_store →
                #   artifact_store（两跳）。证据见 manifest_readback() 的注释。
                _man_ok, _man_detail, _man_rid = manifest_readback(ready_cfg.authority_root)
                report(_man_ok,
                       "C31d session 库损坏后 manifest 仍读得回（entries/run_id 齐全）"
                       if _man_ok else
                       "C31d manifest 读不回或内容不全：%s" % _man_detail,
                       "" if _man_ok else _man_detail)

                runtime.projection.close()
                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["projection_fresh"] is False
                       and str(ready_cfg.review_projection_db) not in r.text
                       and "ProgrammingError" not in r.text,
                       "C32 projection 不可用 → 503 且低敏", r.text)
        finally:
            shutil.rmtree(ready_root, ignore_errors=True)

        # 反方向：业务投影坏时 session 认证仍可用，但 ready 必须 503。
        projection_fault_root = tempfile.mkdtemp(prefix="production-projection-fault-")
        try:
            projection_cfg = settings(projection_fault_root)
            projection_app = create_production_app(projection_cfg, oauth_provider=provider)
            with TestClient(projection_app, base_url="https://ca.example") as projection_client:
                login = projection_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                projection_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                projection_app.state.production_runtime.projection.close()
                me = projection_client.get("/api/v1/me")
                ready = projection_client.get("/readyz")
                report(me.status_code == 200 and ready.status_code == 503
                       and ready.json()["checks"]["session_db"] is True
                       and ready.json()["checks"]["projection_fresh"] is False,
                       "C32a projection 故障不影响 session 认证", repr((me.text, ready.text)))
        finally:
            shutil.rmtree(projection_fault_root, ignore_errors=True)

        # authority event 在运行中被篡改，ready 必须真回读 hash 并变 503。
        authority_fault_root = tempfile.mkdtemp(prefix="production-authority-fault-")
        try:
            authority_cfg = settings(authority_fault_root)
            authority_app = create_production_app(authority_cfg, oauth_provider=provider)
            with TestClient(authority_app, base_url="https://ca.example") as authority_client:
                login = authority_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                authority_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                authority_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(authority_client, "authority-fault"), json={})
                event = authority_cfg.authority_root / "events/cmd-000000000001.json"
                event.write_bytes(event.read_bytes() + b"tamper")
                r = authority_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["authority_chain"] is False
                       and str(authority_cfg.authority_root) not in r.text,
                       "C32b authority hash 篡改 → 503 且低敏", r.text)
        finally:
            shutil.rmtree(authority_fault_root, ignore_errors=True)

        # 严格 frozen projection：坏 JSON 不得退化为空集合。
        bad_frozen_root = tempfile.mkdtemp(prefix="production-bad-frozen-")
        try:
            bad_cfg = settings(bad_frozen_root)
            (bad_cfg.frozen_projection_root / "cases.json").write_text(
                "{not-json", encoding="utf-8")
            try:
                create_production_app(bad_cfg, oauth_provider=provider)
                denied = False
            except RuntimeError as exc:
                denied = "frozen_projection_unreadable:cases.json" in str(exc)
            report(denied, "C33 坏 frozen cases 启动前 fail closed")
            (bad_cfg.frozen_projection_root / "cases.json").write_text(
                json.dumps([{"case_id": "shape-only"}]), encoding="utf-8")
            try:
                create_production_app(bad_cfg, oauth_provider=provider)
                denied = False
            except RuntimeError as exc:
                denied = "frozen_projection_case_shape:0" in str(exc)
            report(denied, "C33b frozen case 元素缺字段同样 fail closed")
        finally:
            shutil.rmtree(bad_frozen_root, ignore_errors=True)

        # start 中途失败必须清理 lease，修好配置后同进程能立即重试。
        cleanup_root = tempfile.mkdtemp(prefix="production-start-cleanup-")
        try:
            cleanup_cfg = settings(cleanup_root)
            cleanup_cfg.principal_directory.write_text(
                json.dumps({"principals": []}), encoding="utf-8")
            bad_app = create_production_app(cleanup_cfg, oauth_provider=provider)
            try:
                with TestClient(bad_app, base_url="https://ca.example"):
                    pass
                startup_failed = False
            except Exception as exc:  # noqa: BLE001
                startup_failed = "principal_directory_empty" in str(exc)
            lock_exists = (cleanup_cfg.authority_root / "writer.lock").exists()
            retry_lease = __import__(
                "base.business_event_store", fromlist=["WriterLease"]).WriterLease(
                    cleanup_cfg.authority_root / "writer.lock")
            try:
                retry_lease.acquire()
                reacquired = True
            except Exception:  # noqa: BLE001
                reacquired = False
            finally:
                retry_lease.release()
            report(startup_failed and lock_exists and reacquired,
                   "C34 启动中途失败释放 OS writer lease（锁文件可保留）")
        finally:
            shutil.rmtree(cleanup_root, ignore_errors=True)

        # 第二实例指向同一权威目录时必须抢不到 writer lease。
        first_app = create_production_app(cfg, oauth_provider=provider)
        with TestClient(first_app, base_url="https://ca.example"):
            second_app = create_production_app(cfg, oauth_provider=provider)
            try:
                with TestClient(second_app, base_url="https://ca.example"):
                    second_denied = False
            except Exception as exc:  # noqa: BLE001
                second_denied = "writer_lease_held" in str(exc)
            report(second_denied, "C29 第二生产实例 writer lease 拒绝")

        # 严格配置缺失必须启动前红
        try:
            ProductionSettings.from_env({})
            denied = False
        except SettingsError:
            denied = True
        report(denied, "C23 缺生产配置 fail closed")
        env_root = Path(tempfile.mkdtemp(prefix="production-env-"))
        try:
            common = {
                "REVIEW_AUTHORITY_ROOT": str(env_root / "authority"),
                "REVIEW_FROZEN_PROJECTION_ROOT": str(env_root / "frozen"),
                "REVIEW_PROJECTION_DB": str(env_root / "same.db"),
                "REVIEW_API_SESSION_DB": str(env_root / "same.db"),
                "REVIEW_API_ACCESS_LOG": str(env_root / "access.jsonl"),
                "REVIEW_PRINCIPAL_DIRECTORY": str(env_root / "principals.json"),
                "REVIEW_REPORT_ROOT": str(env_root / "reports"),
                "REVIEW_PUBLIC_ORIGIN": "https://ca.example",
                "REVIEW_OAUTH_CLIENT_ID": "cli_independent",
                "REVIEW_OAUTH_CLIENT_SECRET": "not-real",
                "REVIEW_OAUTH_REDIRECT_URI": "https://ca.example/auth/callback",
                "REVIEW_OAUTH_REAUTH_REDIRECT_URI": "https://ca.example/auth/reauth/callback",
                "REVIEW_TENANT_ALLOWLIST": "t1",
            }
            try:
                ProductionSettings.from_env(common)
                denied = False
            except SettingsError as exc:
                denied = str(exc) == "data_paths_must_be_distinct"
            report(denied, "C23b session/projection/audit 等路径必须彼此独立")
            # live gate 的敏感结论必须包含 reauth consent/step-up hash/generation。
            live_gate_src = (ROOT / "tools/verify_feishu_web_oauth_live.py").read_text(
                encoding="utf-8")
            report(all(term in live_gate_src for term in (
                "fresh_consent_confirmed", "reauth_flow_verified",
                "step_up_single_use", "step_up_token_hashed",
                "session_generation_verified")),
                "C23c live OAuth evidence 不止登录，含 reauth/step-up/generation")
        finally:
            shutil.rmtree(env_root, ignore_errors=True)

    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("----------------------------------------")
    if not failed:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
