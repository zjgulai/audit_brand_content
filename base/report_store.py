#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/report_store.py —— 唯一报告载体/发布器（T1-12）

## 职责边界（技术方案 §2 #19）

  - `report_id` **内容寻址**：由渲染文本 + `ReviewIR` 身份（id/version/指纹）算出；
  - 报告是**不可变静态对象**：写 `reports/<report_id>.md`，已存在时只允许字节相同；
  - `reports/index.jsonl` **只追加**；同一 report_id 不重复追加；
  - URL 指向静态 `.md` 文件，不指向渲染服务；
  - 回读先过 ACL：无权限 → `{ok:false, url:null}`，**不返回 URL**；
  - 从 `ReviewIR` 可重建同内容（`rebuild`）；文件被删后可重新 publish 恢复。

## 不做什么

  - 不渲染报告内容（`render_fn` 由 report_renderer 注入）；
  - 不产 IR、不存 IR/回执/媒体字节（artifact_store）；
  - 不判状态、不发送、不决定保存期/ACL 政策。

## R1/R2/R3

  - **R1**：渲染文本必须含 `source_ir_version: <version>` 与
    `source_ir_fingerprint: <sha256(IR)>`；缺一或指纹不符 → 拒发布。
  - **R2**：IR 版本变 → 新 report_id（即使渲染文本相同）；旧文件不改不删。
  - **R3**：URL 只由静态 base 拼出，必须是 `.../reports/<id>.md`。

## 失败语义

  - 读失败：`{ok:false, url:null, detail: ...}`；
  - 发布失败：`{ok:false, url:null, detail: ...}`；
  - 数据根不允许在仓库内（仓库是公开的，报告可能含客户内容）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
import urllib.parse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from base.send_gateway import FORBIDDEN_RECEIPT_WORDS
except Exception:  # noqa: BLE001
    from send_gateway import FORBIDDEN_RECEIPT_WORDS


FINDING_LINE_RE = re.compile(r"^\s*-\s+(\S+)\s+·\s*控制点：\s*(\S+)", re.M)
STATE_LINE_RE = re.compile(r"^\s*-\s*状态：\s*(.+?)\s*$", re.M)


def rendered_report_mismatches(ir, text):
    """C-59：报告渲染文本与 IR 的独立对拍。

    ★ 「解析不到 finding 行」不能当成「零不一致」：IR 有 findings 而文本里
      一行都解析不出 → `ir_render_unparsable`，由 publish 直接阻断。
    """
    errs = []
    if not isinstance(text, str):
        return ["ir_render_unparsable:text_not_str"]
    findings = (ir or {}).get("findings")
    decision = (ir or {}).get("decision")
    if not isinstance(findings, list) or not isinstance(decision, dict):
        return ["ir_render_unparsable:ir_missing_findings_or_decision"]

    lines = FINDING_LINE_RE.findall(text)
    if findings and not lines:
        return ["ir_render_unparsable:no_finding_lines"]

    ir_pairs = [(str(f.get("finding_id")), str(f.get("control_code")))
                for f in findings if isinstance(f, dict)]
    ir_ids = {i for i, _ in ir_pairs}
    ir_by_id = {i: c for i, c in ir_pairs}
    seen = {}
    for fid, code in lines:
        seen[(fid, code)] = seen.get((fid, code), 0) + 1
    parsed_ids = {i for i, _ in lines}
    for fid, code in ir_pairs:
        if (fid, code) not in seen:
            errs.append("missing_or_wrong_finding:%s:%s" % (fid, code))
    for (fid, code), n in seen.items():
        if fid not in ir_ids:
            errs.append("unexpected_finding:%s" % fid)
        elif ir_by_id.get(fid) != code:
            errs.append("wrong_control_code:%s:%s!=%s" % (fid, code, ir_by_id.get(fid)))
        if n > 1:
            errs.append("duplicate_finding_line:%s" % fid)

    state = decision.get("state")
    if state is not None:
        states = [s.strip() for s in STATE_LINE_RE.findall(text)]
        if not states:
            errs.append("ir_render_unparsable:no_state_line")
        elif any(s != state for s in states):
            errs.append("state_mismatch:%r!=%r" % (states[0], state))
    return errs


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _iso_now(now):
    if now is not None:
        return now
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _receipt_hits(text):
    """回执禁词：与 send_gateway 共用同一编译正则，不复制词表。"""
    hits = []
    for m in FORBIDDEN_RECEIPT_WORDS.finditer(text):
        hits.append({"word": m.group(0), "start": m.start(), "end": m.end()})
    return hits


def _receipt_error(hits):
    return {
        "ok": False, "url": None,
        "detail": "receipt_forbidden_word: %s" % ", ".join(
            "%s@[%d:%d]" % (h["word"], h["start"], h["end"]) for h in hits),
        "code": "receipt_forbidden_word",
        "hits": hits,
    }


def _ir_identity(ir):
    if not isinstance(ir, dict):
        raise ValueError("ReviewIR 必须是 dict")
    ir_id = ir.get("ir_id")
    if not isinstance(ir_id, str) or not ir_id:
        raise ValueError("ReviewIR.ir_id 必须是非空字符串")
    if "ir_version" not in ir:
        raise ValueError("ReviewIR.ir_version 缺失")
    version = ir["ir_version"]
    if not isinstance(version, (int, str)) or isinstance(version, bool) or version == "":
        raise ValueError("ReviewIR.ir_version 必须是非空 int/str")
    fp = _sha(_canonical(ir))
    return ir_id, version, fp


def _check_static_base(base):
    if not isinstance(base, str) or not base:
        raise ValueError("static_base 必须是非空字符串")
    u = urllib.parse.urlparse(base)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("static_base 必须是 http(s) 绝对地址")
    if u.query or u.fragment:
        raise ValueError("static_base 不允许带 query/fragment")
    segs = [s.lower() for s in u.path.split("/") if s]
    if any(s in ("api", "render", "renderer") for s in segs):
        raise ValueError("static_base 不能是渲染服务端点：%s" % base)


def _check_root(root):
    r = os.path.abspath(root)
    if r == REPO_ROOT or r.startswith(REPO_ROOT + os.sep):
        raise ValueError("报告数据根不允许在仓库内：%s" % r)
    return r


class ReportStore(object):
    def __init__(self, root, static_base, authorize=None):
        self.root = _check_root(root)
        _check_static_base(static_base)
        self.static_base = static_base.rstrip("/")
        self.reports_dir = os.path.join(self.root, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)
        self.index_path = os.path.join(self.reports_dir, "index.jsonl")
        self.authorize = authorize or self._default_authorize

    # ── 路径与 URL ──────────────────────────────────────────────────
    def _rel_path(self, report_id):
        return os.path.join("reports", report_id + ".md")

    def _url(self, report_id):
        return "%s/reports/%s.md" % (self.static_base, report_id)

    @staticmethod
    def _valid_url(url, static_base):
        if not isinstance(url, str):
            return False
        if not url.startswith(static_base + "/reports/"):
            return False
        if not url.endswith(".md"):
            return False
        low = url.lower()
        return "/api/" not in low and "render" not in low

    # ── 索引 ────────────────────────────────────────────────────────
    def read_index(self):
        try:
            with open(self.index_path, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            return {"records": [], "duplicates": [], "badLines": 0, "missing": True, "error": None}
        except OSError as e:
            return {"records": [], "duplicates": [], "badLines": 0,
                    "missing": False, "error": e.__class__.__name__}
        records = []
        bad = 0
        for line in raw.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                if not isinstance(r, dict) or not isinstance(r.get("report_id"), str):
                    raise ValueError("bad record")
                records.append(r)
            except ValueError:
                bad += 1
        seen = {}
        for r in records:
            seen[r["report_id"]] = seen.get(r["report_id"], 0) + 1
        duplicates = sorted(k for k, n in seen.items() if n > 1)
        return {"records": records, "duplicates": duplicates, "badLines": bad,
                "missing": False, "error": None}

    def _append_index(self, record):
        data = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self.index_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            view = memoryview(data)
            while view:
                n = os.write(fd, view)
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write_object(self, report_id, data):
        rel = self._rel_path(report_id)
        final = os.path.join(self.root, rel)
        tmp = final + ".tmp.%d" % os.getpid()
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            view = memoryview(data)
            while view:
                n = os.write(fd, view)
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, final)
        try:
            dfd = os.open(os.path.dirname(final), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
        return rel

    # ── R1 校验 ─────────────────────────────────────────────────────
    def _check_r1(self, text, version, fp):
        if not isinstance(text, str):
            return "render_not_text"
        if ("source_ir_version: %s" % version) not in text:
            return "missing_source_ir_version"
        if ("source_ir_fingerprint: %s" % fp) not in text:
            return "missing_source_ir_fingerprint"
        return None

    def _make_id(self, text, ir_id, version, fp):
        blob = ("%s\x1f%s\x1f%s\x1f%s" % (text, ir_id, version, fp)).encode("utf-8")
        return "rp" + _sha(blob)[:16]

    # ── 发布 ────────────────────────────────────────────────────────
    def publish(self, ir, render_fn, acl, now=None):
        try:
            ir_id, version, fp = _ir_identity(ir)
        except ValueError as e:
            return {"ok": False, "url": None, "detail": "bad_ir:%s" % e}
        try:
            text = render_fn(ir)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "url": None, "detail": "render_failed:%s" % type(e).__name__}
        # 回执禁词闸：命中即拒，不写盘、不进 index。
        hits = _receipt_hits(text)
        if hits:
            return _receipt_error(hits)
        # ★ C-59：IR ↔ 渲染文本独立对拍。不一致/解析不出 → 不落盘、不给 URL。
        mismatches = rendered_report_mismatches(ir, text)
        if mismatches:
            if mismatches[0].startswith("ir_render_unparsable"):
                return {"ok": False, "url": None, "detail": mismatches[0]}
            return {"ok": False, "url": None,
                    "detail": "ir_render_mismatch:" + ";".join(mismatches[:3])}
        # ★ R1 里的 `source_ir_version` 指的是报告里那一行；优先用 IR 的
        #   `source_ir_version` 字段（渲染器就是打印它），缺省才退回 ir_version。
        source_version = ir.get("source_ir_version") or version
        r1 = self._check_r1(text, source_version, fp)
        if r1 is not None:
            return {"ok": False, "url": None, "detail": "r1:%s" % r1}
        if not isinstance(acl, dict):
            return {"ok": False, "url": None, "detail": "bad_acl"}
        for k in ("tenant", "product_line", "submitter_id"):
            if not isinstance(acl.get(k), str) or not acl[k]:
                return {"ok": False, "url": None, "detail": "bad_acl:%s" % k}
        if not isinstance(acl.get("assigned"), list):
            return {"ok": False, "url": None, "detail": "bad_acl:assigned"}

        idx = self.read_index()
        if idx["error"] or idx["badLines"] or idx["duplicates"]:
            return {"ok": False, "url": None, "detail": "index_corrupt"}
        rid = self._make_id(text, ir_id, version, fp)
        data = text.encode("utf-8")
        sha = _sha(data)
        url = self._url(rid)
        rel = self._rel_path(rid)
        final = os.path.join(self.root, rel)

        existing = [r for r in idx["records"] if r.get("report_id") == rid]
        if existing:
            rec = existing[0]
            if rec.get("sha256") != sha:
                return {"ok": False, "url": None, "detail": "immutable_conflict"}
            if rec.get("url") != url or not self._valid_url(rec.get("url"), self.static_base):
                return {"ok": False, "url": None, "detail": "bad_url"}
            if os.path.exists(final):
                try:
                    cur = open(final, "rb").read()
                except OSError as e:
                    return {"ok": False, "url": None, "detail": "read_failed:%s" % e.__class__.__name__}
                if cur != data:
                    return {"ok": False, "url": None, "detail": "immutable_conflict"}
                return {"ok": True, "url": url, "report_id": rid, "path": rel,
                        "sha256": sha, "duplicate": True, "restored": False}
            # 索引在、文件被删：用同一 IR 恢复
            self._write_object(rid, data)
            return {"ok": True, "url": url, "report_id": rid, "path": rel,
                    "sha256": sha, "duplicate": True, "restored": True}

        if os.path.exists(final):
            try:
                cur = open(final, "rb").read()
            except OSError as e:
                return {"ok": False, "url": None, "detail": "read_failed:%s" % e.__class__.__name__}
            if cur != data:
                return {"ok": False, "url": None, "detail": "immutable_conflict"}
            rel = self._rel_path(rid)
        else:
            rel = self._write_object(rid, data)

        record = {
            "report_id": rid,
            "path": rel,
            "sha256": sha,
            "source_ir_id": ir_id,
            "source_ir_version": version,
            "source_ir_fingerprint": fp,
            "url": url,
            "created_at": _iso_now(now),
            "acl": dict(acl),
        }
        self._append_index(record)
        return {"ok": True, "url": url, "report_id": rid, "path": rel,
                "sha256": sha, "duplicate": False, "restored": False}

    # ── 重建 ────────────────────────────────────────────────────────
    def rebuild(self, ir, render_fn, expected_report_id=None):
        try:
            ir_id, version, fp = _ir_identity(ir)
        except ValueError as e:
            return {"ok": False, "detail": "bad_ir:%s" % e}
        try:
            text = render_fn(ir)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": "render_failed:%s" % type(e).__name__}
        hits = _receipt_hits(text)
        if hits:
            err = _receipt_error(hits)
            return {"ok": False, "detail": err["detail"],
                    "code": err["code"], "hits": err["hits"]}
        source_version = ir.get("source_ir_version") or version
        r1 = self._check_r1(text, source_version, fp)
        if r1 is not None:
            return {"ok": False, "detail": "r1:%s" % r1}
        rid = self._make_id(text, ir_id, version, fp)
        if expected_report_id is not None and rid != expected_report_id:
            return {"ok": False, "detail": "report_id_mismatch",
                    "report_id": rid, "expected": expected_report_id}
        return {"ok": True, "report_id": rid, "text": text,
                "sha256": _sha(text.encode("utf-8"))}

    # ── 回读 + ACL ──────────────────────────────────────────────────
    @staticmethod
    def _default_authorize(principal, rec):
        if not isinstance(principal, dict):
            return False
        role = principal.get("role")
        acl = rec.get("acl") or {}
        if role == "submitter":
            return principal.get("id") == acl.get("submitter_id")
        if role in ("DP3", "DP4", "reviewer"):
            return (principal.get("tenant") == acl.get("tenant")
                    and principal.get("product_line") == acl.get("product_line")
                    and principal.get("id") in (acl.get("assigned") or []))
        if role == "signer":
            return (principal.get("tenant") == acl.get("tenant")
                    and principal.get("product_line") == acl.get("product_line"))
        if role in ("coordinator", "admin", "项目统筹"):
            return principal.get("tenant") == acl.get("tenant")
        return False

    def read(self, report_id, principal):
        idx = self.read_index()
        if idx["error"]:
            return {"ok": False, "url": None, "detail": "index_unreadable"}
        if idx["badLines"]:
            return {"ok": False, "url": None, "detail": "index_corrupt"}
        if idx["duplicates"]:
            return {"ok": False, "url": None, "detail": "index_duplicate"}
        rec = next((r for r in idx["records"] if r.get("report_id") == report_id), None)
        if rec is None:
            return {"ok": False, "url": None, "detail": "not_found"}
        if not self.authorize(principal, rec):
            return {"ok": False, "url": None, "detail": "forbidden"}
        if not self._valid_url(rec.get("url"), self.static_base):
            return {"ok": False, "url": None, "detail": "bad_url"}
        path = os.path.join(self.root, rec.get("path", ""))
        if not os.path.isfile(path):
            return {"ok": False, "url": None, "detail": "missing_object"}
        try:
            data = open(path, "rb").read()
        except OSError as e:
            return {"ok": False, "url": None, "detail": "read_failed:%s" % e.__class__.__name__}
        if _sha(data) != rec.get("sha256"):
            return {"ok": False, "url": None, "detail": "integrity"}
        return {"ok": True, "url": rec["url"], "content": data.decode("utf-8"),
                "sha256": rec["sha256"]}

    # ── 完整性 ──────────────────────────────────────────────────────
    def verify_integrity(self):
        errs = []
        idx = self.read_index()
        if idx["error"]:
            errs.append("index_unreadable")
            return errs
        if idx["badLines"]:
            errs.append("index_bad_lines:%d" % idx["badLines"])
        for dup in idx["duplicates"]:
            errs.append("index_duplicate:%s" % dup)
        seen = set()
        for rec in idx["records"]:
            rid = rec.get("report_id")
            if rid in seen:
                continue
            seen.add(rid)
            if not self._valid_url(rec.get("url"), self.static_base):
                errs.append("bad_url:%s" % rid)
            path = os.path.join(self.root, rec.get("path", ""))
            if not os.path.isfile(path):
                errs.append("missing_object:%s" % rid)
                continue
            try:
                data = open(path, "rb").read()
            except OSError:
                errs.append("unreadable:%s" % rid)
                continue
            if _sha(data) != rec.get("sha256"):
                errs.append("integrity:%s" % rid)
        return errs
