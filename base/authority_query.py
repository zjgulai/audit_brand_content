#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/authority_query.py —— 生产依据查询器：把控制点的 authority_ref 解析成可判状态。

## 为什么需要它

`base/judge_entry.py` 的默认查询器恒返回 `untested`，`evidence_sync` 会把它压成
`missing`；于是 `decision_table` 的链 6（L4/L5 + missing → REVIEW）永远命中，
**BLOCK 结构性不可达**。这不是判定表写错，是「依据从来没查过」。

本模块只做一件事：给定一条 `authority_ref`，回答
`ok / missing / expired / conflict / untested`。它不判定、不写盘、不联网。

## 口径

- 外部引用（`entry_id` 形如 `EXT-021`）：在
  `research/kb/外部标准库-v1.json` 里按 `entry_id` 找条目，并校验
  `clause_no == article`、`变更指纹 == fingerprint`。
- 内部引用（带 `path`）：在仓库内读文本，校验 `quote` 逐字存在；
  若 `entry_id` 形如 `file.md:45`，再校验第 45 行确实包含该 quote。
- `status ∈ {disabled, retired}` → `missing`；其余状态（含 `research`）→ `ok`，
  但把 `ratification` 原样带进 reason——「研究稿·未经法务确认」是**可用但要看见**的事实，
  不是「依据不存在」。把它压成 missing 会让 BLOCK 永远出不来。
- 文件读不到 / 结构不认识 / 路径越界：**一律 `untested`**，由 `evidence_sync` 压成 missing。
  fail-closed，绝不 fail-open。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KB_PATH = ROOT / "research" / "kb" / "外部标准库-v1.json"

DISABLED_STATUSES = frozenset({"disabled", "retired"})


def _canonical_path(root: Path, rel: str) -> Path | None:
    """只接受仓库内相对路径；绝对路径、`..`、空串一律拒绝。"""
    if not isinstance(rel, str) or not rel.strip():
        return None
    value = Path(rel)
    if value.is_absolute() or ".." in value.parts:
        return None
    target = (root / value).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target


class ExternalStandardsAuthority:
    """只读依据解析器；构造时不读盘，第一次 query 才装载。"""

    def __init__(self, path=None, *, repo_root=None):
        self.path = Path(path) if path is not None else DEFAULT_KB_PATH
        self.repo_root = Path(repo_root) if repo_root is not None else ROOT
        self._entries = None
        self._snapshot = "kb-unavailable"
        self._load_error = None

    def _load(self):
        if self._entries is not None or self._load_error is not None:
            return
        try:
            raw = self.path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
            entries = data.get("entries")
            if not isinstance(entries, list):
                raise ValueError("entries 不是数组")
            table = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_id = entry.get("id")
                if isinstance(entry_id, str) and entry_id:
                    table[entry_id] = entry
            self._entries = table
            self._snapshot = "external-stdlib-v1:" + hashlib.sha256(raw).hexdigest()[:16]
        except Exception as exc:  # noqa: BLE001
            self._entries = None
            self._load_error = "%s: %s" % (type(exc).__name__, exc)
            self._snapshot = "kb-unavailable"

    @property
    def snapshot_id(self):
        self._load()
        return self._snapshot

    def _query_external(self, ref):
        self._load()
        if self._entries is None:
            return {"state": "untested", "reason": "kb_unreadable:%s" % self._load_error}
        entry = self._entries.get(ref.get("entry_id"))
        if entry is None:
            return {"state": "missing", "reason": "entry_not_found"}
        article = ref.get("article")
        if isinstance(article, str) and article:
            if entry.get("clause_no") != article:
                return {"state": "missing", "reason": "article_mismatch",
                        "expected": entry.get("clause_no"), "got": article}
        fingerprint = ref.get("fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            if entry.get("变更指纹") != fingerprint:
                return {"state": "missing", "reason": "fingerprint_mismatch",
                        "expected": entry.get("变更指纹"), "got": fingerprint}
        status = entry.get("status")
        if status in DISABLED_STATUSES:
            return {"state": "missing", "reason": "entry_%s" % status}
        return {
            "state": "ok",
            "reason": "resolved",
            "ratification": entry.get("未确认标记") or status,
            "origin": entry.get("origin"),
        }

    def _query_internal(self, ref):
        target = _canonical_path(self.repo_root, ref.get("path"))
        if target is None:
            return {"state": "missing", "reason": "path_outside_repository"}
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return {"state": "missing", "reason": "path_unreadable:%s" % type(exc).__name__}
        quote = ref.get("quote")
        if not isinstance(quote, str) or not quote:
            return {"state": "missing", "reason": "quote_absent"}
        if quote not in text:
            return {"state": "missing", "reason": "quote_not_found"}
        entry_id = ref.get("entry_id")
        if isinstance(entry_id, str) and ":" in entry_id:
            _, _, line_text = entry_id.rpartition(":")
            if line_text.isdigit():
                lines = text.splitlines()
                index = int(line_text) - 1
                if not (0 <= index < len(lines)) or quote not in lines[index]:
                    return {"state": "missing", "reason": "line_mismatch"}
        return {"state": "ok", "reason": "resolved_internal",
                "ratification": "internal"}

    def query(self, ref):
        """任何异常都落 untested；本函数不向外抛。"""
        try:
            if not isinstance(ref, dict):
                return {"state": "untested", "reason": "bad_ref"}
            if ref.get("path"):
                return self._query_internal(ref)
            if ref.get("entry_id"):
                return self._query_external(ref)
            return {"state": "untested", "reason": "ref_without_address"}
        except Exception as exc:  # noqa: BLE001
            return {"state": "untested", "reason": "resolver_error:%s" % type(exc).__name__}
