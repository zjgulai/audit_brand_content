#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_password_login.py —— 账号密码登录通道（2026-10-29，委托方要求）

## 它守的是什么

`POST /auth/password` 是**绕过飞书租户校验**的登录通道，为测试便利而存在。
所以这个文件的重心不是「能不能登录成功」，而是**它在不该生效时必须不生效**。

## 五组判据

  P1 **默认关闭**：不配 `REVIEW_PASSWORD_LOGIN` → 端点返 **404**（不是 403）。
     ★ 404 与 403 的区别是刻意的：403 等于告诉探测者「这里有东西，只是不给你」，
       他能据此得知这个部署支持密码登录。
  P2 三项缺一即视为未配：只有开关、没有账号/口令 → 仍然 404。
     ★ 「半开」是这里最容易犯的错：端点存在但永远登录失败，读起来像 bug。
  P3 正确的账号口令 → 200，且**发出与 OAuth 同构的 session**：
     Set-Cookie 里有 session cookie、有 csrf cookie，之后 `/api/v1/me` 返 200。
  P4 错的账号 / 错的口令 / 两者都错 → 一律 401，且**错误码完全相同**
     （不能靠 code 区分是哪一项错 —— 那会让人先枚举出账号）。
  P5 principal 不在 `principals.json` → 403，**不凭空造 principal**。
     ★ 造了的话「登录成功但每个动作都落空」，比登录失败更难查。

另有 R 组反向对照：把 `hmac.compare_digest` 换成 `==`、把 404 换成 403、
把「不能区分账号错与口令错」改回可区分 —— 这三种变异都必须被抓住。

## 怎么跑

它**不联网、不碰生产**：在临时目录里造一套最小配置，用 `app_from_env` 起
真身 app，用 `TestClient` 打请求。所有路径都在 `tempfile.mkdtemp()` 下。

    python3 tools/verify_password_login.py            # 主检查
    python3 tools/verify_password_login.py --controls # 加跑反向对照

退出码：0 全过 / 1 有红 / 2 环境缺依赖（未测）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi.testclient import TestClient  # noqa: E402
except Exception as exc:  # noqa: BLE001
    print(f"⚠ 未测：fastapi.testclient 不可用：{exc}")
    raise SystemExit(2)

fails: list[str] = []
passes = 0


def report(ok: bool, name: str, detail: str = "") -> None:
    global passes
    if ok:
        passes += 1
        print(f"  ✅ {name}")
    else:
        fails.append(name)
        print(f"  ❌ {name}" + (f"  ← {detail}" if detail else ""))


# ─────────────────────────── 造一套最小生产配置 ───────────────────────────

def make_env(root: Path, *, enabled: bool, user: str = "daisy",
             secret: str = "s3cret-for-test", principal: str = "u-zhoujian",
             tenant: str = "t1", seed_principal: bool = True) -> dict:
    """造一套能真的起 `app_from_env` 的环境变量。

    ★ 所有路径都在 `root` 下 —— `ProductionSettings.from_env` 会拒绝
      落在仓库内的路径（`external()` 那一层），临时目录天然合规。
    """
    # ★ 必须 0700：`ProductionRuntime.start()` 里 `_ensure_private_dir`
    #   会拒绝任何 group/other 有权限位的数据目录（`data_permissions`）。
    #   ★ 而且**只在目录不存在时** mkdir 的 mode 才生效 —— 先建后用 chmod 补，
    #   否则 `mode=0o700` 被静默忽略（mkdir 对已存在的目录不设权限）。
    for name in ("authority", "frozen", "reports"):
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        d.chmod(0o700)
    root.chmod(0o700)

    # ★ `seed_principal=False` 造「配置指向的 principal 不在目录里」那种情形。
    #   P5 的**第一版就错在这里**：它传了 principal="u-not-in-directory"，
    #   而同一个函数把这个 id 也写进了 principals.json —— 于是它当然存在、
    #   当然登录成功。那条红是**用例造错了**，不是代码有漏洞。
    #   一个测不到它声称要测的东西的用例，比没有用例更糟。
    # ★ 目录里**必须至少有一个 active 主体**（`principal_directory_empty`
    #   会让 app 起不来）。所以 seed_principal=False 时放一个**别人**，
    #   而配置指向的那个 id 不在里面 —— 这才是「配置写错了」的真实形状。
    _seed_id = principal if seed_principal else "u-someone-else"
    principals = {"principals": [{
            "id": _seed_id,
            "tenant_id": tenant,
            "open_id": "ou-" + principal,
            "name": "测试主体",
            "roles": ["dp3"],
            "product_lines": ["pump"],
            "status": "active",
            # ★ 必须是**非空字符串**（`_validate` 里 `isinstance(x, str)` 硬判）。
            #   写成数字 1 会报 `principal_field: authz_version` —— 那个错读起来
            #   像「字段缺失」，实际是「类型不对」。
            "authz_version": "1",
        }]
    }
    (root / "principals.json").write_text(
        json.dumps(principals, ensure_ascii=False), encoding="utf-8")
    (root / "frozen" / "cases.json").write_text("[]", encoding="utf-8")

    env = {
        "REVIEW_AUTHORITY_ROOT": str(root / "authority"),
        "REVIEW_FROZEN_PROJECTION_ROOT": str(root / "frozen"),
        "REVIEW_PROJECTION_DB": str(root / "projection.db"),
        "REVIEW_API_SESSION_DB": str(root / "session.db"),
        "REVIEW_API_ACCESS_LOG": str(root / "access.log"),
        "REVIEW_PRINCIPAL_DIRECTORY": str(root / "principals.json"),
        "REVIEW_REPORT_ROOT": str(root / "reports"),
        "REVIEW_PUBLIC_ORIGIN": "https://example.test",
        "REVIEW_OAUTH_CLIENT_ID": "cli_test",
        "REVIEW_OAUTH_CLIENT_SECRET": "oauth-secret",
        "REVIEW_OAUTH_REDIRECT_URI": "https://example.test/auth/callback",
        "REVIEW_OAUTH_REAUTH_REDIRECT_URI": "https://example.test/auth/reauth/callback",
        "REVIEW_TENANT_ALLOWLIST": tenant,
    }
    if enabled:
        env.update({
            "REVIEW_PASSWORD_LOGIN": "1",
            "REVIEW_PASSWORD_USER": user,
            "REVIEW_PASSWORD_SECRET": secret,
            "REVIEW_PASSWORD_PRINCIPAL": principal,
        })
    return env


def build_app(env: dict):
    """用真身 `app_from_env` 起 app。返回 (app, err)。

    ★ `app_from_env()` **不收参数** —— 它自己读 `os.environ`。
      所以这里必须真的把环境变量换掉，跑完再还原。
      第一版直接把 env 传进去，四个用例一起 TypeError 红掉了 ——
      那是我读错签名，不是它坏了。用 `create_production_app(ProductionSettings.from_env(env))`
      也能绕开，但那条路**不测 `app_from_env` 本身**，而生产跑的就是它。
    """
    from api.production_app import app_from_env

    saved = dict(os.environ)
    try:
        os.environ.update({k: str(v) for k, v in env.items()})
        # 清掉可能污染的上一次残留（否则「未启用」的用例会读到上一轮的开关）
        for key in ("REVIEW_PASSWORD_LOGIN", "REVIEW_PASSWORD_USER",
                    "REVIEW_PASSWORD_SECRET", "REVIEW_PASSWORD_PRINCIPAL",
                    "REVIEW_PASSWORD_TENANT"):
            if key not in env:
                os.environ.pop(key, None)
        return app_from_env(), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        os.environ.clear()
        os.environ.update(saved)


# ─────────────────────────── 主检查 ───────────────────────────

def run_main() -> int:
    print("=" * 74)
    print("verify_password_login · 账号密码登录通道（默认关 · 同构 session · 不可枚举）")
    print("=" * 74)

    # ── P1 / P2：不该开的时候必须不存在 ────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        app, err = build_app(make_env(Path(td), enabled=False))
        if app is None:
            report(False, "P1 起 app（未启用）", err)
        else:
            # ★ 必须用 `with` 形式：TestClient 只在上下文里跑 lifespan，
            #   而 `runtime.start()` 在 lifespan 里 —— 不跑就永远 503「未就绪」。
            #   第一版直接 TestClient(app) 调用，于是所有用例一起 503。
            with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
                r = c.post("/auth/password",
                           json={"username": "daisy", "password": "whatever"})
            report(r.status_code == 404,
                   "P1 ★ 未启用 → 端点返 404（不是 403：403 会告诉探测者功能存在）",
                   f"got {r.status_code}")

    # 半开：只给开关，不给账号/口令
    with tempfile.TemporaryDirectory() as td:
        env = make_env(Path(td), enabled=False)
        env["REVIEW_PASSWORD_LOGIN"] = "1"   # 只有开关
        app, err = build_app(env)
        if app is None:
            report(False, "P2 起 app（半开）", err)
        else:
            with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
                r = c.post("/auth/password",
                           json={"username": "daisy", "password": "whatever"})
            report(r.status_code == 404,
                   "P2 ★ 只配开关、没配账号/口令 → 仍按「未启用」处理（返 404）",
                   f"got {r.status_code}")

    # ── P3：启用后能登录，且 session 与 OAuth 同构 ────────────────────
    with tempfile.TemporaryDirectory() as td:
        app, err = build_app(make_env(Path(td), enabled=True))
        if app is None:
            report(False, "P3 起 app（启用）", err)
        else:
            # ★ 整个 P3/P4 必须留在同一个 `with` 里：session 是客户端
            #   自己持有的 cookie，出了 with 那个 c 就关了。
            #   第一版把 report 写在外面，于是 /api/v1/me 用的是已关闭的 client。
            with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
                r = c.post("/auth/password",
                           json={"username": "daisy", "password": "s3cret-for-test"})
                cookies = r.headers.get_list("set-cookie")
                me = c.get("/api/v1/me")
                r2 = c.post("/auth/password",
                            json={"username": "daisy", "password": "wrong"})
                r3 = c.post("/auth/password",
                            json={"username": "nobody", "password": "s3cret-for-test"})

            report(r.status_code == 200, "P3a 正确账号口令 → 200",
                   f"got {r.status_code} {r.text[:160]}")

            has_session = any(("sid" in x.lower() or "session" in x.lower())
                              for x in cookies)
            has_csrf = any(x.lower().startswith("csrf=") for x in cookies)
            report(bool(cookies) and has_csrf,
                   "P3b 发 csrf cookie（与 OAuth 回调同一条：httponly=false，供 JS 读）",
                   str(cookies)[:200])
            report(bool(cookies) and has_session,
                   "P3c 发 session cookie", str(cookies)[:200])

            # 同构判据：拿这个 session 真的能调业务接口
            report(me.status_code == 200,
                   "P3d ★ session 与 OAuth 同构：登录后 /api/v1/me 200",
                   f"got {me.status_code} {me.text[:120]}")
            if me.status_code == 200:
                body = me.json()
                report(body.get("principal") == "u-zhoujian",
                       "P3e /me 返回的是配置里的 principal",
                       json.dumps(body, ensure_ascii=False)[:160])

            # 密码错误：401，且与「账号错」不可区分（r2/r3 已在上面 with 内取好）
            report(r2.status_code == 401 and r3.status_code == 401,
                   "P4a 错口令 / 错账号 → 均 401",
                   f"pw={r2.status_code} user={r3.status_code}")

            # ★ 关键：两者的错误码必须**逐字相同**，否则可以枚举账号
            def code_of(resp):
                try:
                    return json.dumps(resp.json(), sort_keys=True, ensure_ascii=False)
                except Exception:  # noqa: BLE001
                    return resp.text
            report(code_of(r2) == code_of(r3),
                   "P4b ★ 错口令与错账号的响应体逐字相同（不可枚举账号）",
                   f"pw={code_of(r2)[:80]} vs user={code_of(r3)[:80]}")

    # ── P5：principal 不存在时拒绝，且不凭空造 ────────────────────────
    with tempfile.TemporaryDirectory() as td:
        env = make_env(Path(td), enabled=True, principal="u-ghost", seed_principal=False)
        app, err = build_app(env)
        if app is None:
            report(False, "P5 起 app（principal 不存在）", err)
        else:
            with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
                r = c.post("/auth/password",
                           json={"username": "daisy", "password": "s3cret-for-test"})
            report(r.status_code == 403,
                   "P5 ★ principal 不在 principals.json → 403（不凭空造）",
                   f"got {r.status_code} {r.text[:160]}")

    return 0 if not fails else 1


# ─────────────────────────── 反向对照 ───────────────────────────

def run_controls() -> int:
    """反向对照：把**具体的实现写法**逐条钉住。

    ## 这里诚实地分成两类，不混着说

    **行为级**（P1–P5）已经在主检查里跑了真身：未启用是否 404、登录是否发
    同构 session、账号错与口令错是否不可区分、principal 不存在是否拒绝。
    那几项的判据是**响应**，改坏了会红。

    **实现属性级**（下面 R1–R5）判的是「这段代码怎么写的」，而不是
    「它返回什么」。有些东西**没有行为差异可观察** —— 最典型的是
    `hmac.compare_digest` 换成 `==`：单次请求的返回值完全一样，
    差别只在响应时间里的几十纳秒。那种属性只能看源码。

    ★ 所以下面每条都写清「为什么它是实现属性」，而不是假装它是行为验证。
      这也是本项目 §2.4 要求的：判据要能说清它拦的是什么。

    ★ 另外这个文件**不改仓库、不联网**：只读 `api/production_app.py` 的文本。
      第一版我想复制整个 api/ 目录到临时目录去真的跑变异，写了 80 行，
      然后发现它要重新装依赖、要处理 sys.modules 缓存、还要处理
      `principal_directory_empty` 这类起不来 —— 收益与复杂度完全不成比例。
      真正该行为化的那几条，主检查里已经行为化了。
    """
    print("=" * 74)
    print("verify_password_login · 反向对照（实现属性 · 逐条钉住写法）")
    print("=" * 74)
    src = (ROOT / "api" / "production_app.py").read_text(encoding="utf-8")
    local_fails: list[str] = []
    n = 0

    def check(name: str, ok: bool, why: str, detail: str = "") -> None:
        nonlocal n
        n += 1
        if ok:
            print(f"  ✅ {name}")
        else:
            local_fails.append(name)
            print(f"  ❌ {name}" + (f"  ← {detail}" if detail else ""))
        print(f"       （实现属性：{why}）")

    # ① 等时比对 —— 单次返回值不变，只有计时差异，行为级抓不到
    check(
        "R1 口令与账号都用 hmac.compare_digest 包住",
        "hmac.compare_digest(" in src
        and src.count("hmac.compare_digest(") >= 2,
        "`==` 会在第一个不同字符处提前返回，响应时间泄露「前几位猜对了」；"
        "而正确与错误的**返回值完全一样**，所以只能在源码上看",
        f"compare_digest 出现 {src.count('hmac.compare_digest(')} 次，应 ≥2",
    )

    # ② 未启用必须 404 而不是 403 —— 这条**行为级也测了**（P1），这里再钉写法
    check(
        'R2 未启用时 raise HTTPException(404, "not_found")',
        'raise HTTPException(404, "not_found")' in src,
        "403 会告诉探测者「这里有东西，只是不给你」；404 与「没有这个端点」不可区分",
    )

    # ③ 账号错/口令错共用同一条 401 —— P4b 从响应体逐字比对侧面验了
    check(
        'R3 账号错与口令错共用一条 raise HTTPException(401, "invalid_credentials")',
        'raise HTTPException(401, "invalid_credentials")' in src,
        "两者给不同 code 就能先枚举出账号；P4b 从响应逐字相同侧面验了同一条",
    )

    # ④ 三项 AND 才算启用 —— P2 用真身验了「半开」形状
    check(
        "R4 启用条件是 开关 AND 账号 AND 口令（三项同时成立）",
        'env.get("REVIEW_PASSWORD_LOGIN", "") == "1"' in src
        and 'bool(env.get("REVIEW_PASSWORD_USER"))' in src
        and 'bool(env.get("REVIEW_PASSWORD_SECRET"))' in src,
        "少写一项就成「半开」：端点存在但永远登录失败，读起来像 bug 不像没配；"
        "P2 已用真身验过这个形状",
    )

    # ⑤ 中间件白名单 —— 少了它登录会被 CSRF 拦成 403，P3a 会红
    check(
        "R5 /auth/password 在 CSRF 中间件白名单里",
        '"/auth/password")' in src or '"/auth/password",' in src,
        "它在 POST 且此时还没有 session；不在白名单里会被 CSRF 校验拦成 403，"
        "P3a 的 200 会直接变红",
    )

    # ⑥ ★★★ 前端拼的 URL 必须是 `/auth/password`，不是 `/api/v1/auth/password`
    #
    #   2026-10-29 实测事故：`client.ts` 里写成 `${apiBase}/auth/password`，
    #   而生产 `apiBase === "/api/v1"` —— 请求打到 `/api/v1/auth/password`，
    #   那个路径不在 CSRF 白名单里，被拦成 **403「CSRF 校验失败」**。
    #
    #   这个错的方向极具误导性：界面报的是 CSRF 失败，人就会去查 csrf cookie、
    #   查中间件、查 origin —— 而真相是 URL 多了一段前缀。
    #
    #   ★ 我原来的自证抓不到它：P1–P5 都是**直接打后端** `/auth/password`，
    #     从来没经过前端那次拼接。所以补这一条 —— 它读的是前端源码里的拼接形状。
    client_raw = (ROOT / "web" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    # ★★★ **注释不算代码** —— 这条判据的第一版没剥注释，于是它读到了我自己
    #   写在那段修复注释里的「原来写的是 `${apiBase}/auth/password`」，
    #   把 D 本来正确的代码判成红。
    #
    #   这是同一个坑今天第三次出现（前两次在 verify_acceptance_trigger.py 与
    #   check_browser_scope 的 C7）。统一读法：**先剥整行注释再判**。
    #   ⚠️ 已知盲区（与 check_browser_scope J1a、verify_shouheng_ops C5 同一条）：
    #      行尾注释仍会被扫到，明着留着。
    client_src = "\n".join(
        line.split("//")[0] for line in client_raw.splitlines()
    )
    check(
        "R7 ★★ 前端登录 URL 用 appOrigin 拼（不是 apiBase —— 后者带 /api/v1 前缀）",
        "${appOrigin}/auth/password" in client_src
        and "${apiBase}/auth/password" not in client_src,
        "生产 apiBase === '/api/v1'，用它拼会打到 /api/v1/auth/password；"
        "那不在 CSRF 白名单里，会被拦成 403「CSRF 校验失败」——"
        "错误信息指向 csrf/origin，真因在 URL",
        "client.ts 里仍用 ${apiBase}/auth/password",
    )

    # ⑧ ★★ 静态资源必须被压缩
    #
    #   2026-10-30 实测：`/assets/index-*.js` 427 KB，响应头**没有**
    #   content-encoding —— 整个前端包未压缩传输。而 `index.html` 有 gzip
    #   （那是上游 nginx 做的）。差别的原因是 js/css 由**本服务**的
    #   FileResponse 直出，`FileResponse` 不做压缩。
    #
    #   427 KB 压完约 120 KB，这一项省 70%。实测本机到服务器拉主 bundle
    #   要 42 秒，用户每次硬刷新都吃这个。
    # ★★★ 这条的第一版**测不出东西**：判据是 `"GZipMiddleware" in src`。
    #   把 `app.add_middleware(GZipMiddleware, ...)` 整行注释掉之后它**照样绿** ——
    #   因为 import 那一行还留着 `GZipMiddleware` 这个词。
    #   实测：注释掉 → R8 仍然 ✅。这是同一个病今天第四次出现。
    #
    #   修法两条：① 剥掉 `#` 注释再判；② 判的是**调用形状**
    #   `add_middleware(GZipMiddleware`（带左括号），不是类名出现。
    without_comments = "\n".join(
        line.split("#")[0] for line in src.splitlines()
    )
    check(
        "R8 ★★ 生产 app **真的调用了** add_middleware(GZipMiddleware)（不是只 import）",
        "add_middleware(GZipMiddleware" in without_comments,
        "js/css 由本服务的 FileResponse 直出，而 FileResponse 不压缩；"
        "上游 nginx 只压了 index.html。427 KB → 约 120 KB。"
        "★ 判据要求带左括号的调用形状 —— 只查类名在有 import 的地方恒真",
    )

    # ⑦ 绝不硬编码口令 —— 仓库是公开的
    check(
        "R6 ★ 源码里没有任何硬编码的口令字面量",
        not __import__("re").search(
            r'password_login_secret\s*=\s*["\'][^"\']+["\']', src),
        "本仓库是**公开**的：硬编码口令会永久留在 git 历史里。"
        "口令只能从 REVIEW_PASSWORD_SECRET 读",
    )

    print("-" * 74)
    if local_fails:
        print(f"❌ {len(local_fails)}/{n} 项不符")
        return 1
    print(f"✅ {n}/{n} 项反向对照全过")
    print("   ★ 这些都是实现属性（看写法），行为由 P1–P5 的真身请求覆盖。")
    return 0


def main() -> int:
    rc = run_main()
    if "--controls" in sys.argv:
        rc = max(rc, run_controls())
    print("-" * 74)
    if fails:
        print(f"❌ {len(fails)} 项红 · {passes} 项通过")
        return 1
    print(f"✅ {passes} 项全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
