#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_openapi_spec.py —— T-408 / TS-10：OpenAPI 3.1 装配层与实现表双向对拍

## 这个文件为什么存在

`api/review_api.py` 一直在 `FastAPI(openapi_version="3.1.0")` 下产 spec，
`tools/verify_review_api.py` 的 C0 段也一直在断言「版本是 3.1」——
所以「没有 OpenAPI」这个说法（差距分析 GW-22）**按现状是错的**。

真正缺的是另外三件事，而它们都**没有任何断言**：

1. **`/api/openapi.json` 不存在**（只有 FastAPI 默认的 `/openapi.json`），
   而票面/前端约定的是带 `/api` 前缀的那条 —— 用它取 spec 得到 404。

2. **spec 对占位端点说了假话**。`WRITE_PATHS - implemented` 的五个端点
   （含 `POST /reports/{id}/resign`）被 FastAPI 声明为 **`200 Successful Response`**，
   而它们的 handler **永远** `raise HTTPException(501)`。
   读 spec 生成客户端的人会拿到一个「成功」的签名，运行期收到 501。
   ★ 这是本项目最忌讳的那个形状（§2.4.1）：**接口通、字段读得到、没有任何东西会红。**
   同一类假话还有三处：`READONLY_WRITE_PATHS` 的三个只读入口，spec 声明 200、
   实际恒 403。

3. **没有任何东西断言 spec ⊇ 实现表**。于是「实现了但 spec 里没有」
   （客户端拿不到）与「spec 里有但没实现」（客户端拿到 501）
   两个方向的漂移都不会被发现。

## 本文件断言什么

    S1  spec 版本是 3.1，且两个入口 `/openapi.json` 与 `/api/openapi.json`
        返回**逐字节相同**的内容（同一 app、同一缓存，不是复制一份）
    S2  `IMPLEMENTED_WRITE_PATHS ⊆ spec POST paths`（实现了的必须可见）
        —— 那张表定义在 `api/write_api.py`，本文件只读它、不复算它
    S3  `PRODUCTION_WRITE_PATHS ⊆ spec POST paths`（生产放行的必须可见）
    S4  `WRITE_PATHS ⊆ spec POST paths`（Appendix B 声明的必须存在）
    S5  ★ 占位端点：spec **只**声明 501，且**不含 200**
        —— 反向对照在 R1：把 `status_code=501` 去掉，S5 必须红
    S6  ★ 只读守卫：spec **只**声明 403，且**不含 200**（同上）
    S7  spec 里**没有** `/api/openapi.json` 自指条目（别名不该进 spec）
    S8  生产装配下 spec 里 `posts - (实现表 ∪ 生产表 ∪ 声明表 ∪ 只读表 ∪ {logout})`
        必须为空 —— 「谁都没认领的写端点」是一种漂移，不是无害的富余
    S9  API 层不重算判定（TS-10 的核心）：`api/review_api.py` 的源码里
        不得出现 `decision_table` / `rule_judge` 的**调用**（只看 import 不算）

## 为什么是独立文件，而不是加进 verify_review_api.py

`verify_review_api.py` 用的是**开发装配**（`create_app(...)`，不带
`enabled_write_capabilities`）。而 S3/S8 要验的是**生产装配**
（`create_production_app`，那里才有 `PRODUCTION_WRITE_PATHS` 与 `revoke`）。
把两套装配塞进一个文件，会重演「验证器形状 ≠ 生产形状」那条老病
（`verify_production_app.py` 开头自己写了这个教训）。

## 退出码

  0 全过 · 1 有红 · 2 未测（fastapi 缺失 / 生产装配起不来）

用法：
  python3 tools/verify_openapi_spec.py
  python3 tools/verify_openapi_spec.py --controls    # 反向对照（喂坏样本必须红）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


def untested(why):
    UNTESTED.append(why)
    print("UNTESTED: %s" % why, file=sys.stderr)


try:
    from fastapi.testclient import TestClient

    from api.oauth import FakeOAuthProvider, OAuthIdentity
    from api.production_app import (
        PRODUCTION_WRITE_PATHS, ProductionSettings, create_production_app)
    from api.review_api import READONLY_WRITE_PATHS, WRITE_PATHS, create_app
    from api.write_api import IMPLEMENTED_WRITE_PATHS
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入装配层：%s" % exc)
    sys.exit(2)


#: 生产装配里**不属于任何写表**的 POST —— 它是登录/登出生命周期的一部分，
#: 没有 capability 语义。**逐个点名**而不是模糊放行：加一条就要改这一行，
#: 于是「新增了一个没人认领的写端点」会在这里被逼着做一次决定。
UNCLAIMED_ALLOWED = frozenset({"/api/v1/logout"})

#: 生产装配里**用 POST 表达、但语义只读**的端点（T-454，2026-10-27 加）。
#:
#: ★ 为什么不与 `UNCLAIMED_ALLOWED` 合并：那一条的豁免理由是「登录/登出生命周期、
#:   没有 capability 语义」；这一个是「要传大段正文，塞 query 会被截断，
#:   而截断会让判据**静默判错**」。两条理由不同、将来会分别过期，混在一起
#:   就会出现「删掉一条时顺手把另一条的理由也删了」。
#:
#: ★ 一条纯豁免就是一句没有执行点的话（AGENTS.md §2.4.2）。所以这里配了两条硬约束，
#:   都在本文件的 S8b/S8c 里：
#:   ① 名单里的路径**必须真的还在** prod spec 里以 POST 出现 ——
#:      否则它是一条指不出对象的过期豁免；
#:   ② 名单里的路径**不许**同时出现在任何写表里（IMPLEMENTED_WRITE_PATHS /
#:      PRODUCTION_WRITE_PATHS / WRITE_PATHS / READONLY_WRITE_PATHS）——
#:      否则这条豁免就被用来夹带一个真正的写端点。
#:
#: ★ 行为级证明（「它真的不写」）不在本文件，在 `tools/verify_version_diff.py`
#:   的 D 组：真跑两次请求，断言 authority 的案件数与报告数一个没变。
#:   本文件只管「声明侧」，那边管「行为侧」—— 两件事分开是因为一个查 spec、
#:   一个要真跑 HTTP，混在一起会让本文件从「静态对拍」变成「集成测试」。
READONLY_POST_ALLOWED = frozenset({"/api/v1/version-diff"})


def _prod_settings(root):
    root = Path(root)
    frozen = root / "frozen"
    frozen.mkdir(parents=True, mode=0o700, exist_ok=True)
    (frozen / "cases.json").write_text("[]", encoding="utf-8")
    principal = root / "principals.json"
    principal.write_text(json.dumps({"principals": [{
        "id": "reviewer", "tenant_id": "t1", "open_id": "ou-reviewer",
        "roles": ["dp3"], "product_lines": ["pump"], "product_line": "pump",
        "capabilities": [], "status": "active", "authz_version": "r-v1",
    }]}), encoding="utf-8")
    return ProductionSettings(
        authority_root=root / "authority",
        frozen_projection_root=frozen,
        review_projection_db=root / "projection" / "review.db",
        session_db=root / "session" / "session.db",
        access_log_path=root / "audit" / "access.jsonl",
        principal_directory=principal,
        report_root=root / "reports",
        public_origin="https://ca.example",
        oauth_client_id="cli_openapi",
        oauth_client_secret="not-a-real-secret",
        oauth_redirect_uri="https://ca.example/auth/callback",
        oauth_reauth_redirect_uri="https://ca.example/auth/reauth/callback",
        oauth_scope="auth:user.id:read",
        tenant_allowlist=frozenset({"t1"}),
    )


def _post_paths(spec):
    return {p for p, item in (spec.get("paths") or {}).items()
            if isinstance(item, dict) and "post" in item}


def _placeholder_paths(app):
    """从**实际路由**读出哪些 POST 是占位 handler。

    ★ 为什么不在断言里用 `WRITE_PATHS - IMPLEMENTED_WRITE_PATHS` 算：
      那个差集在**开发装配**里恰好等于占位集，但在**生产装配**里不等 ——
      四条名单治理路由被 `register_admin_routes()` 注册成了真 handler
      （因为 service 非 None），而它们仍在 IMPLEMENTED_WRITE_PATHS 之外
      （那四条只进了生产表）。于是差集会把「已经实现的端点」判成「占位」，
      得到一条**假红**。
      T-408 第一版就是这么写的，当场红了两条 —— 而其中一条是假红。
      判据要问的是「这个 handler 是不是占位」，不是「它在不在某张表里」。
    """
    out = set()
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if getattr(endpoint, "__name__", "") != "placeholder":
            continue
        if "POST" not in (getattr(route, "methods", None) or set()):
            continue
        out.add(route.path)
    return out


def _readonly_paths(app):
    """从实际路由读出只读守卫（按 handler 名前缀）。"""
    out = set()
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        name = getattr(endpoint, "__name__", "")
        if name.startswith("readonly_"):
            out.add(route.path)
    return out


def _bodies(*specs):
    """跑一遍全部断言。`specs` 允许注入（反向对照用坏样本）。"""
    for bad_name, spec, prod_spec in specs:
        _check_spec(bad_name, spec, prod_spec)


def _check_spec(tag, dev_spec, prod_spec, *, placeholders=None,
                readonly=None):
    paths = (dev_spec.get("paths") or {})
    posts = _post_paths(dev_spec)

    # ── S1 版本 ────────────────────────────────────────────────────────
    version = str(dev_spec.get("openapi") or "")
    ok("S1-%s OpenAPI 版本是 3.1（实测 %r）" % (tag, version),
       "") if version.startswith("3.1") else no(
        "S1-%s OpenAPI 版本必须是 3.1" % tag, repr(version))

    # ── S2/S3/S4 三个方向的覆盖 ────────────────────────────────────────
    missing_impl = sorted(set(IMPLEMENTED_WRITE_PATHS) - posts)
    if missing_impl:
        no("S2-%s 已实现写端点必须出现在 spec 里" % tag, repr(missing_impl[:6]))
    else:
        ok("S2-%s 已实现写端点 %d 条全在 spec 里"
           % (tag, len(IMPLEMENTED_WRITE_PATHS)))

    # ── S3 生产放行表 ⊆ spec ──────────────────────────────────────────
    #
    # ★ 只在**生产 spec** 上跑。开发装配不注册 `revoke`（它只在生产表里，
    #   不在 `WRITE_PATHS`），于是开发 spec 里没有它 —— 那是装配差异，
    #   不是 spec 缺陷。在开发 spec 上跑这一条会得到一条**假红**，
    #   而假红会逼人往下调判据（§2.1.1）。
    if prod_spec is not None:
        missing_prod = sorted(set(PRODUCTION_WRITE_PATHS) - posts)
        if missing_prod:
            no("S3-%s 生产放行的写端点必须出现在 spec 里" % tag,
               repr(missing_prod[:6]))
        else:
            ok("S3-%s 生产放行 %d 条全在 spec 里"
               % (tag, len(PRODUCTION_WRITE_PATHS)))

    missing_declared = sorted(set(WRITE_PATHS) - posts)
    if missing_declared:
        no("S4-%s Appendix B 声明的写端点必须存在" % tag,
           repr(missing_declared[:6]))
    else:
        ok("S4-%s Appendix B %d 条全在 spec 里" % (tag, len(WRITE_PATHS)))

    # ── S5 ★ 占位端点：只许声明 501，不许出现 200 ──────────────────────
    ph_set = set(placeholders) if placeholders is not None else set()
    bad_response = {}
    for p in sorted(ph_set):
        responses = ((paths.get(p) or {}).get("post") or {}).get("responses") or {}
        codes = set(responses)
        # 501 必须在；200 不许在 —— 两个方向都要查。
        if "501" not in codes or "200" in codes:
            bad_response[p] = sorted(codes)
    if bad_response:
        no("S5-%s ★ 占位端点 spec 只许声明 501（不许 200）" % tag,
           repr(bad_response))
    else:
        ok("S5-%s ★ %d 个占位端点均只声明 501（spec 不再对它们说成功）"
           % (tag, len(ph_set)))

    # ── S6 ★ 只读守卫：只许声明 403，不许出现 200 ──────────────────────
    ro_set = set(readonly) if readonly is not None else set()
    ro_bad = {}
    for p in sorted(ro_set):
        for method in ("post", "put", "patch", "delete"):
            item = (paths.get(p) or {}).get(method)
            if item is None:
                continue
            codes = set((item.get("responses") or {}))
            if "403" not in codes or "200" in codes:
                ro_bad["%s %s" % (method.upper(), p)] = sorted(codes)
    if ro_bad:
        no("S6-%s ★ 只读入口的写方法 spec 只许声明 403（不许 200）" % tag,
           repr(ro_bad))
    else:
        ok("S6-%s ★ 只读入口 %d 条的写方法均只声明 403"
           % (tag, len(ro_set)))

    # ── S7 spec 不许自指 ──────────────────────────────────────────────
    self_ref = sorted(p for p in paths if "openapi" in p)
    if self_ref:
        no("S7-%s spec 里不许出现 openapi 自指条目" % tag, repr(self_ref))
    else:
        ok("S7-%s spec 无 openapi 自指条目" % tag)

    # ── S8 生产装配下「无人认领的写端点」必须为空 ───────────────────────
    if prod_spec is not None:
        prod_posts = _post_paths(prod_spec)
        claimed = (set(IMPLEMENTED_WRITE_PATHS) | set(PRODUCTION_WRITE_PATHS)
                   | set(WRITE_PATHS) | set(READONLY_WRITE_PATHS)
                   | set(UNCLAIMED_ALLOWED) | set(READONLY_POST_ALLOWED))
        orphans = sorted(prod_posts - claimed)
        if orphans:
            no("S8-%s ★ 生产 spec 里不许有没人认领的写端点" % tag, repr(orphans))
        else:
            ok("S8-%s ★ 生产 spec 的 %d 条 POST 全部有主（实现/生产/声明/只读/白名单）"
               % (tag, len(prod_posts)))

        # ── S8b/S8c 只读 POST 白名单自己的两个方向 ────────────────────────
        # ★ 为什么要单独两条：`READONLY_POST_ALLOWED` 是一张**豁免表**，
        #   而豁免表最常见的坏法不是「漏了一条」，是「它说的东西已经不存在了」
        #   （路径改了名、端点被删），此时它看起来仍然合规，实际是一条死规则 ——
        #   下一个人照着它给一个**真写端点**开豁免就没人拦了。
        #   所以两个方向都查：名单里的必须真在、真在的必须不在写表里。
        stale = sorted(p for p in READONLY_POST_ALLOWED if p not in prod_posts)
        if stale:
            no("S8b-%s ★ 只读 POST 白名单里的路径必须真在 prod spec 里（否则是过期豁免）"
               % tag, repr(stale))
        else:
            ok("S8b-%s ★ 只读 POST 白名单 %d 条都指得出对象"
               % (tag, len(READONLY_POST_ALLOWED)))

        overlap = sorted(
            set(READONLY_POST_ALLOWED)
            & (set(IMPLEMENTED_WRITE_PATHS) | set(PRODUCTION_WRITE_PATHS)
               | set(WRITE_PATHS) | set(READONLY_WRITE_PATHS)))
        if overlap:
            no("S8c-%s ★ 只读 POST 豁免不许同时落在写表里（否则被用来夹带真写端点）"
               % tag, repr(overlap))
        else:
            ok("S8c-%s ★ 只读 POST 豁免与四张写表零重叠" % tag)


def _check_no_recompute():
    """S9：API 层不得重算判定（TS-10 的核心判据）。"""
    src = (ROOT / "api" / "review_api.py").read_text(encoding="utf-8")
    # ★ 去掉注释再扫 —— 注释里写着「不许调 decision_table」不算违规，
    #   而 §2.4.4 那条教训正是「被自己的解释文字绊倒」。
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#"))
    calls = []
    for name in ("decision_table", "rule_judge", "judge_unit", "decide("):
        for m in re.finditer(re.escape(name), code):
            line = code[:m.start()].count("\n") + 1
            # 只认「调用形状」：name 后面紧跟 ( 或 .
            tail = code[m.end():m.end() + 2]
            if tail.startswith("(") or tail.startswith("."):
                calls.append("%s@%d" % (name, line))
    if calls:
        no("S9 ★ API 层不得重算判定（TS-10）", repr(calls[:5]))
    else:
        ok("S9 ★ API 层不调用判定引擎（TS-10：判定仍由既有模块唯一计算）")


def run_checks(dev_app=None, prod_app=None):
    """跑全部断言；两个 app 可注入（反向对照用）。"""
    dev = dev_app or create_app(app_env="dev",
                                allow_simulated_identity=False)
    dev_spec = dev.openapi()
    dev_placeholders = _placeholder_paths(dev)
    dev_readonly = _readonly_paths(dev)

    # S1 的第二种形状：两个入口必须逐字节相同。
    # ★ 这一条只能在**同一个 app 实例**上比 —— 跨实例比会因 dict 顺序/缓存
    #   差异而假红，那种红会逼人把断言改松，也就是把判据毁掉。
    with TestClient(dev, base_url="https://ca.example") as client:
        a = client.get("/openapi.json")
        b = client.get("/api/openapi.json")
        if a.status_code != 200 or b.status_code != 200:
            no("S1b 两个 spec 入口都必须 200",
               "default=%s api=%s" % (a.status_code, b.status_code))
        elif a.content != b.content:
            no("S1b /openapi.json 与 /api/openapi.json 必须逐字节相同",
               "%d vs %d bytes" % (len(a.content), len(b.content)))
        else:
            ok("S1b /openapi.json 与 /api/openapi.json 逐字节相同（%d bytes）"
               % len(a.content))

    _check_spec("dev", dev_spec, None,
                placeholders=dev_placeholders, readonly=dev_readonly)

    prod_spec = None
    if prod_app is not None:
        prod_app_obj = prod_app
    else:
        prod_app_obj = None
    root = tempfile.mkdtemp(prefix="openapi-prod-")
    try:
        if prod_app_obj is None:
            provider = FakeOAuthProvider(
                {"good": OAuthIdentity("t1", "ou-reviewer")})
            prod_app_obj = create_production_app(
                _prod_settings(root), oauth_provider=provider)
        prod_spec = prod_app_obj.openapi()
        _check_spec("prod", prod_spec, prod_spec,
                    placeholders=_placeholder_paths(prod_app_obj),
                    readonly=_readonly_paths(prod_app_obj))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    _check_no_recompute()


def run_controls():
    """反向对照：四个坏样本必须红，好样本必须绿。

    ★ 每一条都直接改一份**深拷贝**的 spec，只看断言会不会红 ——
      不去改源码（改源码会让对照本身变成一次有副作用的运行，§2.4.4）。
    """
    print("=" * 70)
    print("反向对照：坏样本必须红 / 好样本必须绿")
    print("=" * 70)
    dev = create_app(app_env="dev", allow_simulated_identity=False)
    good = dev.openapi()
    ph_set = _placeholder_paths(dev)
    ro_set = _readonly_paths(dev)
    cases = []

    # 坏样本 1：占位端点声明 200（改前真实状态）
    bad1 = json.loads(json.dumps(good))
    ph = sorted(ph_set)[0]
    bad1["paths"][ph]["post"]["responses"] = {"200": {"description": "x"}}
    cases.append(("bad:占位端点声明200", bad1, False))

    # 坏样本 2：只读守卫声明 200
    bad2 = json.loads(json.dumps(good))
    ro = sorted(ro_set)[0]
    bad2["paths"][ro]["post"]["responses"] = {"200": {"description": "x"}}
    cases.append(("bad:只读守卫声明200", bad2, False))

    # 坏样本 3：实现表里的路径从 spec 里删掉
    bad3 = json.loads(json.dumps(good))
    bad3["paths"].pop(sorted(IMPLEMENTED_WRITE_PATHS)[0], None)
    cases.append(("bad:实现端点从spec消失", bad3, False))

    # 坏样本 4：版本不是 3.1
    bad4 = json.loads(json.dumps(good))
    bad4["openapi"] = "3.0.2"
    cases.append(("bad:版本3.0", bad4, False))

    # 好样本：原始 spec
    cases.append(("good:原始spec", json.loads(json.dumps(good)), True))

    results = []
    for name, spec, should_pass in cases:
        before_fail = len(FAIL)
        print("-" * 70)
        print("[%s]" % name)
        _check_spec(name, spec, None, placeholders=ph_set,
                    readonly=ro_set)
        went_red = len(FAIL) > before_fail
        results.append((name, went_red, should_pass,
                        went_red != should_pass))
        # 清掉本轮的通过/失败记录，避免污染下一轮与最终汇总
        while len(FAIL) > before_fail:
            FAIL.pop()

    print("=" * 70)
    bad_ok = sum(1 for _, red, want, good_ in results if good_)
    for name, red, want, good_ in results:
        print("%s %s（红了=%s，期望红=%s）"
              % ("✅" if good_ else "❌", name, red, not want))

    # ── S8/S8b/S8c 的反向对照 ────────────────────────────────────────
    # ★ 上面那个循环固定传 `prod_spec=None`，所以 S8 系列**一次都没跑到**。
    #   一组从不执行的反向对照等于没有 —— 所以这里单独跑一遍，并显式传 prod_spec。
    print("-" * 70)
    print("[S8 系列：只读 POST 白名单两个方向]")
    s8_results = _controls_s8(dev)

    total = len(results) + len(s8_results)
    passed = bad_ok + sum(1 for _, good_ in s8_results if good_)
    for name, good_ in s8_results:
        print("%s %s" % ("✅" if good_ else "❌", name))
    if passed == total:
        print("✅ 反向对照 %d/%d 全过" % (passed, total))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (passed, total), file=sys.stderr)
    return 1


def _controls_s8(dev):
    """S8b/S8c 的反向对照：三条必须红、一条必须绿。

    ★ 判据本身是「白名单不许过期」「豁免不许夹带真写端点」，
      所以要喂的是**构造出来的坏白名单**，而不是坏 spec ——
      这两条查的是名单与 spec/写表的关系，spec 本身可以完全正常。

    ★★ 必须用**真实的 prod spec**，不能用 dev spec 顶替。
      第一版就是用 dev spec 造的，好样本当场红了 ——
      但红的不是 S8，而是 S3（「生产放行的写端点必须出现在 spec 里」，
      dev 装配里根本没有生产路由）。那条红是真的，只是与本组无关；
      如果当时把它读成「误差」去过滤掉，就等于把一条真判据关掉了。
    """
    root = tempfile.mkdtemp(prefix="openapi-s8ctl-")
    try:
        provider = FakeOAuthProvider({"good": OAuthIdentity("t1", "ou-reviewer")})
        prod_app = create_production_app(_prod_settings(root),
                                         oauth_provider=provider)
        spec = json.loads(json.dumps(prod_app.openapi()))
        ph = _placeholder_paths(prod_app)
        ro = _readonly_paths(prod_app)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    results = []

    def _run(spec_obj, allow, want_red):
        before = len(FAIL)
        saved = globals()["READONLY_POST_ALLOWED"]
        globals()["READONLY_POST_ALLOWED"] = frozenset(allow)
        try:
            _check_spec("ctl", spec_obj, spec_obj, placeholders=ph, readonly=ro)
        finally:
            globals()["READONLY_POST_ALLOWED"] = saved
        went_red = len(FAIL) > before
        while len(FAIL) > before:
            FAIL.pop()
        return went_red == want_red

    # ① 好样本必须绿（当前真实名单）
    results.append(("good:当前真实白名单",
                    _run(spec, READONLY_POST_ALLOWED, want_red=False)))
    # ② ★ 白名单里塞一条 spec 里不存在的路径 → S8b 必须红（过期豁免）
    results.append(("bad:白名单指向不存在的路径",
                    _run(spec, set(READONLY_POST_ALLOWED) | {"/api/v1/no-such-post"},
                         want_red=True)))
    # ③ ★ 豁免与写表重叠 → S8c 必须红（被用来夹带真写端点）
    a_write = sorted(IMPLEMENTED_WRITE_PATHS)[0]
    results.append(("bad:豁免与写表重叠",
                    _run(spec, set(READONLY_POST_ALLOWED) | {a_write},
                         want_red=True)))
    # ④ ★ 把白名单整个换成一条真写端点 → 必须红
    #    这是 S8c 真正要拦的形状：豁免变成「让写端点免检」的后门。
    results.append(("bad:用白名单给真写端点开后门",
                    _run(spec, {a_write}, want_red=True)))
    return results


def main():
    print("=" * 70)
    print("verify_openapi_spec · T-408 / TS-10 · OpenAPI 3.1 装配层")
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
