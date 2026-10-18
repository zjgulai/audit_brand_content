#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地联调用的 review-api 入口（只读）。

不修改 `api/review_api.py`：这里只把它的 `create_app()` 用**临时投影 +
本地 session store + 最小 principal 表**装配起来，供前端 dev server 连。

  REVIEW_API_DATA_ROOT   投影目录（cases.json 等）
  REVIEW_API_SESSION_DB  session sqlite 路径（由 dev-up.sh 生成并写入 cookie）

启动：
  /path/to/.venv/bin/uvicorn review_api_dev:app --app-dir web/scripts
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from api.review_api import FileProjectionRepository, create_app  # noqa: E402
from base.auth_session import SessionStore  # noqa: E402

DATA_ROOT = os.environ.get("REVIEW_API_DATA_ROOT")
if not DATA_ROOT:
    raise SystemExit("REVIEW_API_DATA_ROOT 未设置")

SESSION_DB = os.environ.get("REVIEW_API_SESSION_DB", ":memory:")

PRINCIPALS = {
    "u_dp3": {
        "roles": ["coordinator"],
        "product_lines": ["pump"],
        "product_line": "pump",
    },
    "u_signer": {
        "roles": ["signer"],
        "product_lines": ["pump"],
        "product_line": "pump",
        "capabilities": ["release.sign", "release.revoke"],
    },
}

app = create_app(
    session_store=SessionStore(SESSION_DB),
    repository=FileProjectionRepository(DATA_ROOT),
    principals=PRINCIPALS,
)
