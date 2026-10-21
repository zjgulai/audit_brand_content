#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立飞书 Web OAuth provider 离线协议自证。

主体：api/oauth.py、api/production_app.py、base/auth_session.py。
不发网络、不读凭据；只以假 HTTP 响应验证当前授权/换 token/user_info 接线。
真实独立应用联调由 verify_feishu_web_oauth_live.py 单独以 rc=2/0 表达。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from api.oauth import (
        AUTHORIZE_URL, TOKEN_URL, USER_INFO_URL,
        FeishuWebOAuthProvider, OAuthError,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 OAuth provider: %s" % exc)
    sys.exit(2)


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


class Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return Response(self.responses.pop(0))


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    try:
        opener = Opener([
            {"access_token": "USER-ACCESS-SENTINEL", "token_type": "Bearer"},
            {"code": 0, "data": {
                "tenant_key": "tenant-1", "open_id": "ou-1",
                "union_id": "on-1", "name": "Reviewer",
            }},
        ])
        provider = FeishuWebOAuthProvider(
            client_id="cli_independent", client_secret="APP-SECRET-SENTINEL",
            opener=opener, timeout=7)
        url = provider.authorize_url(
            state="state-1", redirect_uri="https://ca.example/auth/callback",
            scope="auth:user.id:read")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        report(url.startswith(AUTHORIZE_URL + "?")
               and query == {
                   "client_id": ["cli_independent"],
                   "response_type": ["code"],
                   "redirect_uri": ["https://ca.example/auth/callback"],
                   "state": ["state-1"],
                   "scope": ["auth:user.id:read"],
               }, "C0 授权 URL 参数完整且 state/redirect 固定", url)

        reauth_url = provider.authorize_url(
            state="state-reauth", redirect_uri="https://ca.example/auth/reauth/callback",
            scope="auth:user.id:read", prompt="consent")
        reauth_query = parse_qs(urlparse(reauth_url).query)
        report(reauth_query.get("prompt") == ["consent"]
               and reauth_query.get("redirect_uri") ==
               ["https://ca.example/auth/reauth/callback"],
               "C0b reauth 使用官方 prompt=consent 独立回调", reauth_url)

        identity = provider.exchange_code(
            code="code-1", redirect_uri="https://ca.example/auth/callback")
        token_request, token_timeout = opener.requests[0]
        token_body = json.loads(token_request.data.decode("utf-8"))
        report(token_request.full_url == TOKEN_URL
               and token_request.get_method() == "POST"
               and token_timeout == 7
               and token_body == {
                   "grant_type": "authorization_code",
                   "client_id": "cli_independent",
                   "client_secret": "APP-SECRET-SENTINEL",
                   "code": "code-1",
                   "redirect_uri": "https://ca.example/auth/callback",
               }, "C1 code 走 v2 token endpoint", token_request.full_url)
        user_request, user_timeout = opener.requests[1]
        report(user_request.full_url == USER_INFO_URL
               and user_request.get_method() == "GET"
               and user_timeout == 7
               and user_request.get_header("Authorization") ==
               "Bearer USER-ACCESS-SENTINEL",
               "C2 user_access_token 只进 v1 user_info Bearer 头")
        report(identity.tenant_id == "tenant-1" and identity.open_id == "ou-1"
               and identity.union_id == "on-1" and identity.name == "Reviewer",
               "C3 tenant_key+open_id 映射正式身份")

        # provider 错误只暴露稳定 code，不回显 provider message/token/secret。
        bad = Opener([{
            "code": 999, "msg": "PROVIDER-SECRET-MESSAGE",
            "access_token": "LEAK-TOKEN",
        }])
        provider = FeishuWebOAuthProvider(
            client_id="cli_independent", client_secret="APP-SECRET-SENTINEL",
            opener=bad)
        try:
            provider.exchange_code(code="bad", redirect_uri="https://ca.example/auth/callback")
            denied = False
            detail = ""
        except OAuthError as exc:
            denied = exc.code == "oauth_provider_error"
            detail = str(exc)
        report(denied and "PROVIDER-SECRET-MESSAGE" not in detail
               and "LEAK-TOKEN" not in detail and "APP-SECRET-SENTINEL" not in detail,
               "C4 provider 错误不泄漏 message/token/secret", detail)

        missing_identity = Opener([
            {"access_token": "short-lived"},
            {"code": 0, "data": {"open_id": "ou-only"}},
        ])
        provider = FeishuWebOAuthProvider(
            client_id="cli_independent", client_secret="secret",
            opener=missing_identity)
        try:
            provider.exchange_code(code="bad-id", redirect_uri="https://ca.example/auth/callback")
            denied = False
        except OAuthError as exc:
            denied = exc.code == "oauth_identity"
        report(denied, "C5 缺 tenant_key fail closed")

        try:
            FeishuWebOAuthProvider(client_id="old-app-id", client_secret="secret")
            denied = False
        except OAuthError as exc:
            denied = exc.code == "oauth_config"
        report(denied, "C6 非 cli_* 独立应用配置拒绝")
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        return 2

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过（离线协议；不等于真实飞书应用）" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
