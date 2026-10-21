#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立飞书 Web OAuth provider 与测试 fake；不读守衡凭据。"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol


AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"


class OAuthError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


@dataclass(frozen=True)
class OAuthIdentity:
    tenant_id: str
    open_id: str
    union_id: str | None = None
    name: str | None = None


class OAuthProvider(Protocol):
    issuer: str

    def authorize_url(self, *, state: str, redirect_uri: str,
                      scope: str = "", prompt: str | None = None) -> str: ...

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthIdentity: ...


class FeishuWebOAuthProvider:
    issuer = "feishu-independent-web-app"

    def __init__(self, *, client_id: str, client_secret: str,
                 opener=None, timeout=10.0):
        if not isinstance(client_id, str) or not client_id.startswith("cli_"):
            raise OAuthError("oauth_config", "client_id 必须是独立飞书应用 cli_* id")
        if not isinstance(client_secret, str) or not client_secret:
            raise OAuthError("oauth_config", "client_secret 必填")
        self.client_id = client_id
        self._secret = client_secret
        self._open = opener or urllib.request.urlopen
        self.timeout = float(timeout)

    def authorize_url(self, *, state, redirect_uri, scope="", prompt=None):
        if not state or not redirect_uri:
            raise OAuthError("oauth_request", "state/redirect_uri 必填")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if scope:
            params["scope"] = scope
        if prompt is not None:
            if prompt != "consent":
                raise OAuthError("oauth_request", "prompt 只允许 consent")
            params["prompt"] = prompt
        return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)

    def _json_request(self, request):
        try:
            with self._open(request, timeout=self.timeout) as response:
                raw = response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise OAuthError("oauth_unavailable", type(exc).__name__) from exc
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise OAuthError("oauth_bad_response", "响应不是 JSON") from exc
        if not isinstance(body, dict) or body.get("code") not in (None, 0):
            raise OAuthError("oauth_provider_error", str((body or {}).get("code")))
        return body

    def exchange_code(self, *, code, redirect_uri):
        if not isinstance(code, str) or not code:
            raise OAuthError("oauth_code", "code 必填")
        payload = json.dumps({
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self._secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }, separators=(",", ":")).encode("utf-8")
        token_request = urllib.request.Request(
            TOKEN_URL, data=payload, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"})
        token = self._json_request(token_request)
        access = token.get("access_token")
        if not isinstance(access, str) or not access:
            raise OAuthError("oauth_bad_response", "缺 access_token")
        user_request = urllib.request.Request(
            USER_INFO_URL, method="GET",
            headers={"Authorization": "Bearer " + access})
        user_response = self._json_request(user_request)
        user = user_response.get("data")
        if not isinstance(user, dict):
            raise OAuthError("oauth_bad_response", "缺 user_info data")
        open_id = user.get("open_id")
        tenant = user.get("tenant_key")
        if not all(isinstance(v, str) and v for v in (open_id, tenant)):
            raise OAuthError("oauth_identity", "open_id/tenant_key 缺失")
        return OAuthIdentity(
            tenant_id=tenant,
            open_id=open_id,
            union_id=user.get("union_id") if isinstance(user.get("union_id"), str) else None,
            name=user.get("name") if isinstance(user.get("name"), str) else None,
        )


class FakeOAuthProvider:
    issuer = "fake-oauth"

    def __init__(self, identities=None):
        self.identities = dict(identities or {})
        self.exchanged = []

    def authorize_url(self, *, state, redirect_uri, scope="", prompt=None):
        params = {
            "response_type": "code", "state": state,
            "redirect_uri": redirect_uri, "scope": scope,
        }
        if prompt is not None:
            params["prompt"] = prompt
        return "https://fake.invalid/authorize?" + urllib.parse.urlencode(params)

    def exchange_code(self, *, code, redirect_uri):
        self.exchanged.append((code, redirect_uri))
        identity = self.identities.get(code)
        if identity is None:
            raise OAuthError("oauth_code", "fake code 无对应身份")
        return identity
