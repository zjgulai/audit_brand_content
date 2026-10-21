#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式主体目录：以 tenant_id + open_id 查本地受控角色/品线/capability。"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from pathlib import Path


class PrincipalDirectoryError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


class PrincipalDirectory:
    def __init__(self, path, *, require_authz_version=False):
        self.path = Path(path).resolve()
        self.require_authz_version = bool(require_authz_version)
        self._lock = threading.RLock()
        self._digest = None
        self._last_error = None
        self._by_key = {}
        self._by_id = {}
        self._reload(force=True)

    def _reload(self, *, force=False):
        try:
            raw_bytes = self.path.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            if not force and digest == self._digest:
                return
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise PrincipalDirectoryError("principal_directory_unreadable",
                                          type(exc).__name__) from exc
        rows = raw.get("principals") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise PrincipalDirectoryError("principal_directory_shape",
                                          "principals 必须是数组")
        by_key = {}
        by_id = {}
        for row in rows:
            item = self._validate(row)
            key = (item["tenant_id"], item["open_id"])
            if key in by_key or item["id"] in by_id:
                raise PrincipalDirectoryError("principal_duplicate", repr(key))
            by_key[key] = item
            by_id[item["id"]] = item
        # 先完整解析临时结构，再一次替换；坏更新不覆盖上一份可用目录。
        self._by_key = by_key
        self._by_id = by_id
        self._digest = digest
        self._last_error = None

    def _refresh(self):
        with self._lock:
            try:
                self._reload()
            except PrincipalDirectoryError as exc:
                self._last_error = exc.code
                raise

    def _validate(self, row):
        if not isinstance(row, dict):
            raise PrincipalDirectoryError("principal_shape", "记录必须是对象")
        item = {}
        for name in ("id", "tenant_id", "open_id"):
            value = row.get(name)
            if not isinstance(value, str) or not value.strip():
                raise PrincipalDirectoryError("principal_field", name)
            item[name] = value.strip()
        for name in ("roles", "product_lines", "capabilities"):
            value = row.get(name, [])
            if not isinstance(value, list) or not all(
                    isinstance(x, str) and x.strip() for x in value):
                raise PrincipalDirectoryError("principal_field", name)
            item[name] = sorted(set(x.strip() for x in value))
        product_line = row.get("product_line")
        if product_line is not None and product_line not in item["product_lines"]:
            raise PrincipalDirectoryError("principal_field", "product_line")
        item["product_line"] = product_line
        item["status"] = row.get("status", "active")
        if item["status"] not in ("active", "revoked"):
            raise PrincipalDirectoryError("principal_field", "status")
        explicit_version = row.get("authz_version")
        if explicit_version is not None:
            if not isinstance(explicit_version, str) or not explicit_version:
                raise PrincipalDirectoryError("principal_field", "authz_version")
            item["authz_version"] = explicit_version
        elif self.require_authz_version:
            raise PrincipalDirectoryError("principal_field", "authz_version")
        else:
            item["authz_version"] = hashlib.sha256(json.dumps(
                item, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest()
        return item

    def by_identity(self, tenant_id, open_id):
        self._refresh()
        row = self._by_key.get((tenant_id, open_id))
        if row is None or row["status"] != "active":
            return None
        return copy.deepcopy(row)

    def by_id(self, principal_id, tenant_id):
        self._refresh()
        row = self._by_id.get(principal_id)
        if row is None or row["tenant_id"] != tenant_id or row["status"] != "active":
            return None
        # review_api/RBAC 同时使用 tenant 与 tenant_id、open_id。
        out = copy.deepcopy(row)
        out["tenant"] = out["tenant_id"]
        return out

    def eligible_assignee(self, principal_id, case):
        self._refresh()
        row = self._by_id.get(principal_id)
        if row is None or row["status"] != "active":
            return False
        if row["tenant_id"] != case.get("tenant"):
            return False
        if case.get("product_line") not in row["product_lines"]:
            return False
        return bool({"dp3", "dp4"} & set(row["roles"]))

    def ready(self):
        try:
            self._refresh()
        except PrincipalDirectoryError:
            return False
        return bool(self._by_key)
