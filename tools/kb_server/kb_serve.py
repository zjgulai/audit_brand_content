#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_serve.py —— 本地知识库只读 HTTP 服务（标准库实现，无第三方依赖）

## 它替代什么

`tools/agent/kb_client.mjs` 原先连的是另一台机器经 ngrok 暴露的服务，
2026-11-05 因 **ngrok 免费额度用尽（ERR_NGROK_727）** 断了 37 天。
本服务提供**逐字相同的接口契约**，客户端只改 `base_url` 一行即可切过来。

## 三个端点（与远端一致，见 kb_client.mjs:6-25）

    ⓪ GET /health                                  免鉴权、0 配额
    ① GET /openapi/v1/kb                           列子库（Bearer 鉴权）
    ② GET /openapi/v1/kb/{子库}/retrieve?q=&topK=  检索（key= 或 Bearer）

## 三条与远端**故意不同**的地方，都写在这里

1. **配额不设上限。** 远端是 60/分钟、1000/天（那是云端成本控制）。
   本地没有成本，所以不设限；但 `/health` 与检索响应仍然回 `quota` 字段，
   值恒为 `null` —— 客户端读到 null 会如实显示「来源 none」，
   **不会**把「没有上限」误读成「余额为 0」。

2. **scoreKind 只有 `bm25` 与 `positional` 两种**，与远端同语义：
   查询词按码点 ≥3 → bm25；<3 → positional（词频序）。
   这样客户端那句「只有 bm25 才算顺序可信」的判断不需要改。

3. **绑定 127.0.0.1，不监听 0.0.0.0。** 知识库里有客户素材与判例，
   默认不出本机。要跨机用，显式传 `--host`，并自己加 TLS 与鉴权。

## 鉴权

远端要 key。本地默认**不校验**（只绑回环）。传 `--api-key` 则要求
`?key=` 或 `Authorization: Bearer` 与之相等，否则 401。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_DB = Path(os.environ.get("KB_LOCAL_DB") or (Path.home() / ".shouheng" / "kb-local" / "kb.sqlite3"))
CONTRACT_VERSION = "kb-local-v1"
TOPK_MAX = 50
TOPK_DEFAULT = 10

#: 子库 id 必须与 kb_client.mjs 的 COLLECTIONS 逐字一致
COLLECTIONS = ["1_外部标准库", "2_内部正负样本库", "3_措辞表达库"]

_db_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None
_db_path: Optional[Path] = None


# ───────────────────────── 索引访问 ─────────────────────────

def _open(db_path: Path) -> sqlite3.Connection:
    global _conn, _db_path
    if _conn is not None and _db_path == db_path:
        return _conn
    if not db_path.exists():
        raise FileNotFoundError(
            f"本地索引不存在：{db_path}\n先跑：python3 tools/kb_server/kb_build.py")
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=1")      # 只读服务不许写库
    _conn, _db_path = conn, db_path
    return conn


def _meta(conn: sqlite3.Connection) -> Dict[str, str]:
    return dict(conn.execute("SELECT k,v FROM meta"))


def _collections(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT collection, COUNT(DISTINCT doc_id) d, COUNT(*) c, MIN(rowid) r "
        "FROM chunk GROUP BY collection ORDER BY collection").fetchall()
    out = []
    for r in rows:
        cid = r["collection"]
        # createdAt 在远端是「首次镜像进来的时刻」。本地没有那个概念，
        # 用索引构建时刻 —— 并**不**声称它是内容的诞生时间。
        built = _meta(conn).get("built_at")
        out.append({
            "id": cid,
            "name": cid,
            "description": _DESCR.get(cid, ""),
            "docCount": r["d"],
            "chunkCount": r["c"],
            "createdAt": built,
        })
    return out


_DESCR = {
    "1_外部标准库": "外部标准库：平台政策 / 法规 / 行业标准，条款级原文",
    "2_内部正负样本库": "内部正负样本：已审内容的原文与判定理由",
    "3_措辞表达库": "措辞表达库：规则、白名单、语境守卫",
}


# ───────────────────────── 检索 ─────────────────────────

_CJK = re.compile(r"[一-鿿]")


def _code_point_len(s: str) -> int:
    return len(s)


def _fts_query(q: str) -> Tuple[str, str]:
    """返回 (fts 表达式, scoreKind)。

    ★ 分叉轴是**查询词长度**，不是语言（kb_client.mjs:29-39 实测）。
      trigram 分词器要求 ≥3 个码点；不足时 FTS5 MATCH 会返回空，
      远端此时回退 like/positional。这里用同样的策略，并如实标 scoreKind。
    """
    if _code_point_len(q) >= 3:
        # FTS5 字符串字面量：双引号包裹，内部双引号翻倍
        return '"' + q.replace('"', '""') + '"', "bm25"
    return "", "positional"


def retrieve(db_path: Path, collection: str, q: str, top_k: int) -> Dict[str, Any]:
    conn = _open(db_path)
    t0 = datetime.now(timezone.utc)
    top_k = max(1, min(TOPK_MAX, int(top_k or TOPK_DEFAULT)))
    fts, score_kind = _fts_query(q)

    with _db_lock:
        if score_kind == "bm25":
            rows = conn.execute(
                "SELECT c.chunk_id, c.doc_id, c.title, c.text, c.collection, "
                "       bm25(chunk_fts) AS rank_score "
                "FROM chunk_fts JOIN chunk c ON c.rowid = chunk_fts.rowid "
                "WHERE chunk_fts MATCH ? AND c.collection = ? "
                "ORDER BY rank_score LIMIT ?",
                (fts, collection, top_k)).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM chunk_fts JOIN chunk c ON c.rowid = chunk_fts.rowid "
                "WHERE chunk_fts MATCH ? AND c.collection = ?",
                (fts, collection)).fetchone()[0]
        else:
            # 词频回退：与远端 positional 同口径（词频为序），且 order_is_meaningful=False
            like = f"%{q}%"
            rows = conn.execute(
                "SELECT chunk_id, doc_id, title, text, collection, 0.0 AS rank_score "
                "FROM chunk WHERE collection = ? AND text LIKE ? "
                "ORDER BY LENGTH(text) ASC, chunk_id LIMIT ?",
                (collection, like, top_k)).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM chunk WHERE collection = ? AND text LIKE ?",
                (collection, like)).fetchone()[0]

    # bm25() 返回的是**越小越相关**（负值），与远端的「越大越相关」相反。
    # 翻成远端口径：score = -bm25，再做 0..1 归一。
    raw = [(-float(r["rank_score"]) if score_kind == "bm25" else 0.0) for r in rows]
    lo, hi = (min(raw), max(raw)) if raw else (0.0, 0.0)

    hits = []
    for i, r in enumerate(rows):
        s = raw[i]
        norm = 0.0 if hi == lo else (s - lo) / (hi - lo)
        hits.append({
            "docId": r["doc_id"],
            "docTitle": r["title"],
            "chunkId": r["chunk_id"],
            "text": r["text"],
            "score": round(s, 4),
            "scoreNorm": round(norm, 4),
            "rank": i + 1,
            "coverage": None,
        })

    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {
        "contractVersion": CONTRACT_VERSION,
        "requestId": str(uuid.uuid4()),
        "collection": {"id": collection, "name": collection},
        "hits": hits,
        "hitCount": len(hits),
        "totalCandidates": total,
        "latencyMs": elapsed_ms,
        "scoreKind": score_kind,
        "confidence": None,
        "fallback": None if score_kind == "bm25" else "like",
        # ★ 恒为 null：本地没有配额概念。客户端读到 null 会显示「来源 none」，
        #   不会把「无上限」误读成「余额 0」。
        "quota": None,
    }


def health(db_path: Path) -> Dict[str, Any]:
    try:
        conn = _open(db_path)
        m = _meta(conn)
        n = conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
        return {"ok": True, "service": "kb-local", "db": str(db_path),
                "chunks": n, "schema_version": m.get("schema_version"),
                "contract_version": m.get("contract_version"),
                "content_hash": m.get("content_hash"), "built_at": m.get("built_at")}
    except Exception as e:                      # noqa: BLE001
        return {"ok": False, "service": "kb-local", "error": f"{type(e).__name__}: {e}"}


# ───────────────────────── HTTP ─────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "kb-local/" + CONTRACT_VERSION
    db_path: Path = DEFAULT_DB
    api_key: Optional[str] = None

    #: 访问台账 —— 「谁在什么时候查了什么」。加它不是为了好看：
    #: 它是「Guard 到底有没有连本地库」这个问题的**唯一实测判据**。
    #: 环境变量出现在 launchd 里，不等于进程真的用了它。
    ACCESS_LOG = Path(os.environ.get("KB_LOCAL_ACCESS_LOG")
                      or (Path.home() / ".shouheng" / "kb-local" / "access.jsonl"))

    def log_message(self, fmt, *args):
        pass

    def _access(self, path: str, q: str, status: int, n: int) -> None:
        try:
            self.ACCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
            with self.ACCESS_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "path": path, "q": q, "status": status, "hits": n,
                    "ua": (self.headers.get("User-Agent") or "")[:60],
                    "pid": os.getpid(),
                }, ensure_ascii=False) + "\n")
        except Exception:                       # noqa: BLE001
            # 台账写不进去不该让检索失败。但这条**不许静默**——
            # 否则「没有访问记录」会被读成「没人访问过」，而实际是「没记下来」。
            pass

    # ── 工具 ──
    def _send(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, err_code: str, msg: str, **extra) -> None:
        self._send(code, {"error": {"code": err_code, "message": msg}, **extra})

    def _authed(self, qs: Dict[str, List[str]]) -> bool:
        if not self.api_key:
            return True
        if qs.get("key", [None])[0] == self.api_key:
            return True
        auth = self.headers.get("Authorization") or ""
        return auth.startswith("Bearer ") and auth[7:] == self.api_key

    # ── 路由 ──
    def do_GET(self):                            # noqa: N802
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        qs = parse_qs(u.query)

        if path == "/health":
            h = health(self.db_path)
            self._send(200 if h.get("ok") else 503, h)
            return

        if path == "/openapi/v1/kb":
            # 远端这一条**必须** Bearer（放 ?key= 会 401）—— 本服务两者都收，
            # 因为放宽不会让调用方出错，收紧会。
            if not self._authed(qs):
                self._err(401, "UNAUTHORIZED", "鉴权失败：需要 ?key= 或 Authorization: Bearer")
                return
            try:
                conn = _open(self.db_path)
                self._send(200, {"contractVersion": CONTRACT_VERSION,
                                 "collections": _collections(conn), "quota": None})
            except FileNotFoundError as e:
                self._err(503, "NO_INDEX", str(e))
            return

        m = re.fullmatch(r"/openapi/v1/kb/([^/]+)/retrieve", path)
        if m:
            coll = unquote(m.group(1))
            if coll not in COLLECTIONS:
                self._err(404, "COLLECTION_NOT_FOUND",
                          f"没有这个子库。可用：{' / '.join(COLLECTIONS)}")
                return
            if not self._authed(qs):
                self._err(401, "UNAUTHORIZED", "鉴权失败：需要 ?key= 或 Authorization: Bearer")
                return
            q = (qs.get("q", [""])[0] or "").strip()
            if not q:
                self._err(400, "BAD_REQUEST", "q 不能为空")
                return
            top_k = qs.get("topK", [str(TOPK_DEFAULT)])[0]
            try:
                top_k = int(top_k)
            except (TypeError, ValueError):
                self._err(400, "BAD_REQUEST", f"topK 必须是整数，收到 {top_k!r}")
                return
            if top_k > TOPK_MAX:
                self._err(400, "TOPK_TOO_LARGE", f"topK 超过上限（本地最大 {TOPK_MAX}）")
                return
            try:
                res = retrieve(self.db_path, coll, q, top_k)
                self._send(200, res)
                self._access(f"/openapi/v1/kb/{coll}/retrieve", q, 200, res.get("hitCount", 0))
            except FileNotFoundError as e:
                self._err(503, "NO_INDEX", str(e))
            except Exception as e:               # noqa: BLE001
                self._err(500, "INTERNAL", f"{type(e).__name__}: {e}")
            return

        self._err(404, "NOT_FOUND", f"没有这个端点：{path}")


def serve(db_path: Path, host: str, port: int, api_key: Optional[str]) -> None:
    h = health(db_path)
    if not h.get("ok"):
        print(f"❌ 索引不可用：{h.get('error')}", file=sys.stderr)
        print("   先跑：python3 tools/kb_server/kb_build.py", file=sys.stderr)
        raise SystemExit(2)
    Handler.db_path = db_path
    Handler.api_key = api_key
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"✅ 知识库服务已启动 http://{host}:{port}")
    print(f"   索引 {db_path}")
    print(f"   {h.get('chunks')} 分片 · content_hash {str(h.get('content_hash'))[:16]}…")
    print(f"   鉴权 {'开（--api-key）' if api_key else '关（只绑回环，不校验）'}")
    print(f"   探活 curl http://{host}:{port}/health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中断，停止。")
    finally:
        httpd.server_close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--host", default="127.0.0.1",
                    help="默认只绑回环。跨机访问请显式指定，并自行加 TLS 与鉴权")
    ap.add_argument("--port", type=int, default=8420)
    ap.add_argument("--api-key", default=os.environ.get("KB_LOCAL_API_KEY"))
    a = ap.parse_args()
    serve(Path(a.db).expanduser(), a.host, a.port, a.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
