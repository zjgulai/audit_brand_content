#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_api_dev 的 fail-closed 自证；只用临时目录，不启动服务。"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = Path(__file__).with_name("review_api_dev.py")


def load(name: str, env: dict[str, str]):
    old = dict(os.environ)
    try:
        for key in ("APP_ENV", "REVIEW_DEV_IDENTITY", "REVIEW_API_DATA_ROOT", "REVIEW_API_SESSION_DB"):
            os.environ.pop(key, None)
        os.environ.update(env)
        spec = importlib.util.spec_from_file_location(name, TARGET)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        os.environ.clear()
        os.environ.update(old)


def expect_exit(name: str, env: dict[str, str], needle: str) -> bool:
    try:
        load(name, env)
    except SystemExit as exc:
        ok = needle in str(exc)
        print(("✓" if ok else "✗"), name, repr(str(exc)))
        return ok
    print("✗", name, "未拒绝")
    return False


def main() -> int:
    checks = []
    with tempfile.TemporaryDirectory(prefix="review-dev-selftest-") as temp:
        base = {
            "REVIEW_API_DATA_ROOT": temp,
            "REVIEW_API_SESSION_DB": str(Path(temp) / "session.db"),
        }
        checks.append(expect_exit("missing_env", base, "APP_ENV=dev"))
        checks.append(expect_exit("prod_env", {**base, "APP_ENV": "production", "REVIEW_DEV_IDENTITY": "1"}, "APP_ENV=dev"))
        checks.append(expect_exit("missing_optin", {**base, "APP_ENV": "dev"}, "REVIEW_DEV_IDENTITY=1"))
        module = load("allowed", {**base, "APP_ENV": "dev", "REVIEW_DEV_IDENTITY": "1"})
        checks.append(module._loopback_host("127.0.0.1"))
        checks.append(module._loopback_host("::1"))
        checks.append(module._loopback_host("localhost"))
        checks.append(not module._loopback_host("192.168.204.92"))
        checks.append(not module._loopback_host("example.com"))
    for i, ok in enumerate(checks[3:], 4):
        print(("✓" if ok else "✗"), f"loopback-{i}")
    passed = sum(checks)
    print(f"{'✅' if passed == len(checks) else '❌'} {passed}/{len(checks)} 项通过")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
