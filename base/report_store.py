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
import hmac
import json
import os
import re
import sys
import time
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


# ── 报告链接的过期签名（ADR-0017 / T-403）─────────────────────────────
#
# 这一节**只做**「链接时效」，不做任何 ACL 判断。ACL 仍由 `authorize`
# 负责，两条同时成立才放行（ADR-0017 §三）。

#: 签名覆盖的查询串键集合。**恒等**于此，多一个少一个都判非法 ——
#: 允许额外键（如 `?sig=..&exp=..&next=..`）就等于给「签名只管一半」开门。
LINK_PARAM_KEYS = ("exp", "sig")

#: TTL 上限：30 天。超过就不是「过期签名」而是「长期外链」了。
LINK_TTL_MAX_SECONDS = 30 * 24 * 3600
#: 默认 TTL：1 小时。
LINK_TTL_DEFAULT_SECONDS = 3600


def _link_canonical(report_id, exp):
    """签名的规范化串：`report_id + "\\n" + str(exp)`（UTF-8）。

    ★ 只签这两项，不签 ACL / 租户 / 指纹 —— 签名回答的是「这个链接是不是
      我们发的、发到什么时候」，**不是「谁能看」**。把 ACL 签进去会让
      「同一条报告给两个参与人」需要两套签名，而可见性本来就该在验签之后判。
    """
    return ("%s\n%s" % (report_id, int(exp))).encode("utf-8")


def _link_sig(secret, report_id, exp):
    """HMAC-SHA256 的 hexdigest（64 hex）。跨语言可复算（ADR-0017 §六）。"""
    return hmac.new(secret.encode("utf-8"), _link_canonical(report_id, exp),
                    hashlib.sha256).hexdigest()


def parse_link_params(url, static_base):
    """从报告 URL 里拆出 `(report_id, exp, sig)`。

    返回 `dict`：`{"report_id", "exp"|None, "sig"|None, "error"}`。
    `error` 非空时 `report_id` 可能仍是有效的 —— 调用方据此区分
    「URL 根本不对」与「URL 对但签名部分坏了」。

    ★ 为什么单独拆出来：`_valid_url` 要判「形状对不对」，
      `read` 要判「签名对不对」与「过期没」。两件事需要同一份解析，
      而写两遍必然漂移（本项目已因「两处各写一遍」踩过多次）。
    """
    out = {"report_id": None, "exp": None, "sig": None, "error": None}
    if not isinstance(url, str) or not url.startswith(static_base + "/reports/"):
        out["error"] = "prefix"
        return out
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    # ★ 从 `/reports/` 这个**片段**切，不从 `len(static_base)` 切：
    #   `static_base` 可能是 `https://ca.example/static`，于是 path 是
    #   `/static/reports/rp....md` —— 第一版按 `path[len("/reports/"):]`
    #   切出来是 `eports/rp....md`（少切了 `static` 那 7 个字符），
    #   症状是**每一条签名都判 bad_signature**，而 URL 看起来完全正常。
    #   用 rindex 找最后一段 `/reports/`，与 `_rel_path` 拼法解耦。
    marker = "/reports/"
    cut = path.rfind(marker)
    if cut < 0 or not path.endswith(".md"):
        out["error"] = "not_md"
        return out
    out["report_id"] = path[cut + len(marker):-len(".md")]

    if not parsed.query:
        return out          # 无签名形态：合法（存量报告）
    pairs = urllib.parse.parse_qs(parsed.query, strict_parsing=False,
                                  keep_blank_values=True)
    # ★ 键集合必须**恒等**，不是「包含」：多出的键意味着有东西没被签，
    #   而调用方会以为它被签了。
    if tuple(sorted(pairs)) != LINK_PARAM_KEYS:
        out["error"] = "bad_params"
        return out
    raw_exp = (pairs.get("exp") or [""])[0]
    raw_sig = (pairs.get("sig") or [""])[0]
    if not raw_exp.isdigit():
        out["error"] = "bad_exp"
        return out
    out["exp"] = int(raw_exp)
    out["sig"] = raw_sig
    if len(raw_sig) != 64 or any(c not in "0123456789abcdef" for c in raw_sig):
        out["error"] = "bad_sig_shape"
        return out
    return out


def sign_report_link(secret, static_base, report_id, ttl_seconds, now=None):
    """签一个新链接。返回 `{"url", "exp", ...}`，或 `{"error": ...}`。

    `secret` 为空时**返回 error，不是返回无签名 URL** —— 后者会让
    「没配密钥」看起来像「重签成功了」（ADR-0017 §四）。
    """
    if not isinstance(secret, str) or not secret.strip():
        return {"error": "secret_missing"}
    if len(secret.encode("utf-8")) < 32:
        return {"error": "secret_too_short"}
    try:
        ttl = int(ttl_seconds)
    except (TypeError, ValueError):
        return {"error": "bad_ttl"}
    if ttl <= 0 or ttl > LINK_TTL_MAX_SECONDS:
        return {"error": "ttl_out_of_range"}
    base_ts = int(now if now is not None else time.time())
    exp = base_ts + ttl
    sig = _link_sig(secret, report_id, exp)
    return {"url": "%s/reports/%s.md?exp=%d&sig=%s"
                   % (static_base, report_id, exp, sig),
            "exp": exp, "sig": sig, "ttl": ttl}


def verify_report_link(secrets, static_base, url, now=None):
    """验签 + 验期。`secrets` 是**列表**（ADR-0017 §四 的双密钥窗口）。

    返回 `{"ok": bool, "report_id": str|None, "reason": str}`。
    `reason` 区分五种情形 —— 调用方据此决定回哪个状态码，
    而**不是**把它们都并成「打不开」：

        no_signature  该链接本来就没签名（走 ACL 那条路）
        expired       过期
        bad_signature 签名不对（含篡改 / 换 report_id）
        bad_params    查询串形状不对
        no_secret     服务端没有可用密钥（因此无法验证）
    """
    parsed = parse_link_params(url, static_base)
    if parsed["error"]:
        return {"ok": False, "report_id": parsed["report_id"],
                "reason": parsed["error"]}
    if parsed["exp"] is None and parsed["sig"] is None:
        return {"ok": True, "report_id": parsed["report_id"],
                "reason": "no_signature"}
    candidates = [s for s in (secrets or []) if isinstance(s, str) and s.strip()]
    if not candidates:
        return {"ok": False, "report_id": parsed["report_id"],
                "reason": "no_secret"}
    expected = {_link_sig(s, parsed["report_id"], parsed["exp"])
                for s in candidates}
    # ★ compare_digest 逐个比，不用 `in` 集合查询 —— 后者会退化成哈希比较，
    #   虽然 set 查询本身的时序差异在实践中可忽略，但这里刻意保持
    #   「常数时间比较」的形状，因为它是密码学代码的阅读约定。
    matched = any(hmac.compare_digest(parsed["sig"], e) for e in expected)
    if not matched:
        return {"ok": False, "report_id": parsed["report_id"],
                "reason": "bad_signature"}
    base_now = int(now if now is not None else time.time())
    if parsed["exp"] <= base_now:
        return {"ok": False, "report_id": parsed["report_id"],
                "reason": "expired"}
    return {"ok": True, "report_id": parsed["report_id"], "reason": "signed"}


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
    def __init__(self, root, static_base, authorize=None,
                 link_secrets=None, link_ttl=LINK_TTL_DEFAULT_SECONDS):
        self.root = _check_root(root)
        _check_static_base(static_base)
        self.static_base = static_base.rstrip("/")
        self.reports_dir = os.path.join(self.root, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)
        self.index_path = os.path.join(self.reports_dir, "index.jsonl")
        self.authorize = authorize or self._default_authorize
        #: ADR-0017：链接签名密钥（列表，**新的在前**）。空列表 = 该部署不做签名，
        #: `resign` 会返回 503 —— **不许**降级成「发一个无签名的『新链接』」。
        self.link_secrets = [s for s in (link_secrets or [])
                             if isinstance(s, str) and s.strip()]
        self.link_ttl = int(link_ttl)

    # ── 重签（ADR-0017 / T-403）──────────────────────────────────────
    def resign(self, report_id, principal, *, now=None):
        """为一条**已发布**的报告签一个带过期的新链接。**不碰正文一个字节。**

        ## 三道门，顺序不能换

        1. `report_id` 在索引里（不存在 → `not_found`）；
        2. **ACL**：调用者必须是这条报告的参与人（`authorize`）——
           不许「谁都能给别人的报告造一条新链接」；
        3. **密钥**在（无密钥 → `no_secret`，调用方回 503，**不是** 200）。

        ★ 第 2 步在签名**之前**：签名本身不能替代 ACL（ADR-0017 §三）。
          若放在后面，一个没有权限的人也能拿到一条**有效**链接，
          然后靠它绕过 ACL —— 那正好把要防的事做成了。

        ## 为什么不改索引

        签名是**链接的属性**，不是报告的属性。写进索引会让「同一报告两个有效期」
        变成两条只追加记录，而索引是不可变账本（ADR-0017 §九）。
        """
        idx = self.read_index()
        if idx["error"] or idx["badLines"] or idx["duplicates"]:
            return {"ok": False, "url": None, "detail": "index_corrupt"}
        rec = next((r for r in idx["records"]
                    if r.get("report_id") == report_id), None)
        if rec is None:
            return {"ok": False, "url": None, "detail": "not_found"}
        if not self.authorize(principal, rec):
            return {"ok": False, "url": None, "detail": "forbidden"}
        signed = sign_report_link(self.link_secrets[0] if self.link_secrets else "",
                                  self.static_base, report_id,
                                  self.link_ttl, now=now)
        if signed.get("error"):
            return {"ok": False, "url": None, "detail": signed["error"],
                    #: 调用方据此区分「没配密钥」（503）与「参数不对」（400）。
                    "needs_secret": signed["error"] in
                    ("secret_missing", "secret_too_short")}
        return {"ok": True, "url": signed["url"], "report_id": report_id,
                "exp": signed["exp"], "ttl": signed["ttl"],
                "sha256": rec.get("sha256")}

    # ── 路径与 URL ──────────────────────────────────────────────────
    def _rel_path(self, report_id):
        return os.path.join("reports", report_id + ".md")

    def _url(self, report_id):
        return "%s/reports/%s.md" % (self.static_base, report_id)

    @staticmethod
    def _valid_url(url, static_base):
        """URL 形状校验（ADR-0017 §二 修订后的 R3）。

        仍然禁止：指向渲染服务 / `/api/` 端点 / 非 `.md` 结尾。
        新增允许：**一个**查询串，键集合恒等 `{exp, sig}`。

        ★ 为什么键集合要**恒等**而不是「包含」：多一个键意味着有东西没被签，
          而读的人会以为它被签了。这条与 `parse_link_params` 是同一个口径，
          两处共用它（不各写一遍）。
        ★ 签名本身对不对**不在这一层判**：这个方法没有密钥，只判形状。
          内容正确性在 `verify_report_link`。
        """
        if not isinstance(url, str):
            return False
        if not url.startswith(static_base + "/reports/"):
            return False
        low = url.lower()
        if "/api/" in low or "render" in low:
            return False
        parsed = urllib.parse.urlparse(url)
        if not parsed.path.endswith(".md"):
            return False
        if not parsed.query:
            return True
        return parse_link_params(url, static_base)["error"] is None

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

    def read(self, report_id, principal, *, link_url=None, now=None):
        """读报告正文。

        `link_url`（可选）：请求者**实际使用的那个链接**。给了就额外过一道
        签名校验（ADR-0017 §三）—— 因为「持有链接」与「是参与人」是两件事：

        | link_url | 含义 |
        |---|---|
        | `None` | 内部调用（页面/API），走原来的 session + ACL |
        | 无签名的报告 URL | 存量链接，走原来的 session + ACL（兼容） |
        | **带签名且有效** | ACL **仍然要过**，再加验签 |
        | **带签名但过期/被篡改** | **403，即使请求者是参与人** |

        ★ 最后一行是本 ADR 的核心：过期的意义就是「这扇门关了」。
          若参与人拿着过期链接仍能读，过期只是装饰。
        """
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

        # ① 链接时效（只在调用方给了 link_url 时判）
        if link_url is not None:
            checked = verify_report_link(self.link_secrets, self.static_base,
                                         link_url, now=now)
            if not checked["ok"]:
                # ★ 不把 reason 原样抛给调用方（它会把「过没过期」变成探测面），
                #   但必须留在 detail 里给日志 —— 否则排障时不知道是哪一种。
                return {"ok": False, "url": None,
                        "detail": "link_%s" % checked["reason"]}
            if checked["report_id"] != report_id:
                # 签名有效但**属于另一条报告**：换 report_id 复用链接。
                return {"ok": False, "url": None, "detail": "link_wrong_report"}

        # ② ACL（签名不能替代它）
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
