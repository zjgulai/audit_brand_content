#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为本地联调创建一个 session，并把 opaque cookie 打到 stdout。

用法：
  python web/scripts/make_session.py --db /tmp/x/sessions.db \
      --principal u_dp3 --tenant t1
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from base.auth_session import SessionStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--principal", default="u_dp3")
    ap.add_argument("--tenant", default="t1")
    args = ap.parse_args()
    store = SessionStore(args.db)
    print(store.create_session(args.principal, tenant=args.tenant, now=time.time()))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
