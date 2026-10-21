#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实独立飞书 Web OAuth 联调门。

主体：api/oauth.py、api/production_app.py；动态 evidence 由部署联调流程提供。
默认不读凭据、不发网络：没有显式联调 evidence 时退 2（未测）。真实浏览器完成
授权回调后，由部署联调流程写一个低敏 evidence JSON；本器只验证其形状、时效与
必要结果，绝不接受 fake provider 结果冒充真实联调。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


REQUIRED = {
    "provider": "feishu-independent-web-app",
    "flow": "authorization_code",
    "token_endpoint": "authen/v2/oauth/token",
    "user_info_endpoint": "authen/v1/user_info",
    "cookie_name": "__Host-session",
    "cookie_secure": True,
    "cookie_http_only": True,
    "tenant_open_id_verified": True,
    "oauth_state_single_use": True,
    "browser_binding_verified": True,
    "reauth_flow_verified": True,
    "fresh_consent_confirmed": True,
    "step_up_single_use": True,
    "step_up_token_hashed": True,
    "session_generation_verified": True,
}
MAX_AGE_SECONDS = 3600


def main():
    evidence_path = os.environ.get("REVIEW_FEISHU_OAUTH_LIVE_EVIDENCE")
    if not evidence_path:
        print("UNTESTED: 未提供真实独立飞书 Web OAuth 联调 evidence；fake/离线协议不算真实通过")
        return 2
    path = Path(evidence_path).expanduser().resolve()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        print("UNTESTED: 真实 OAuth evidence 读不出: %s" % type(exc).__name__)
        return 2
    if not isinstance(value, dict):
        print("FAIL: evidence 必须是 JSON object", file=sys.stderr)
        return 1
    errors = []
    for key, expected in REQUIRED.items():
        if value.get(key) != expected:
            errors.append("%s 不匹配" % key)
    completed_at = value.get("completed_at_epoch")
    if not isinstance(completed_at, (int, float)):
        errors.append("completed_at_epoch 缺失")
    elif abs(time.time() - float(completed_at)) > MAX_AGE_SECONDS:
        errors.append("evidence 超过 1 小时")
    forbidden = {"access_token", "refresh_token", "app_secret", "open_id", "tenant_key"}
    leaked = sorted(forbidden & set(value))
    if leaked:
        errors.append("evidence 含敏感字段: %s" % ",".join(leaked))
    if errors:
        for error in errors:
            print("FAIL: " + error, file=sys.stderr)
        return 1
    print("PASS: 真实独立飞书 OAuth evidence 已核（低敏、1小时内、非 fake）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
