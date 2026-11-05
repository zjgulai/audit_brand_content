#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_build.py —— 用本仓库的源数据建一个本地 SQLite FTS5 索引

## 为什么要有它

原本「内容治理知识库」是**另一台机器**上的服务，通过 ngrok 隧道暴露给守衡。
2026-11-05 实测它已经断了 37 天，而断开的原因是 **ngrok 免费账户月度请求数用尽**
（`ERR_NGROK_727`）—— 不是配置错，是计费层。

而这三个子库的源数据**绝大部分就在本仓库里**：

  · 1_外部标准库      ← research/kb/外部标准库-v1.json（62 条）
  · 2_内部正负样本库  ← research/live/snapshot-20261020T162244Z.json（样本 186 条）
  · 3_措辞表达库      ← research/governance/skeleton/{rules,whitelist,context-guards}-v1.json

所以远端服务没有提供任何「本地做不到」的东西。本脚本把源数据灌进本地 SQLite，
由 `kb_serve.py` 按**与远端完全相同的接口契约**提供检索。

## 接口契约必须逐字保持

`tools/agent/kb_client.mjs` 是唯一的客户端。它解析这些字段：

  hits[]  → {docId, docTitle, chunkId, text, score, scoreNorm, rank, coverage}
  顶层    → {contractVersion, requestId, collection:{id}, hits, hitCount,
             totalCandidates, latencyMs, scoreKind, confidence, fallback, quota}

**少一个字段，客户端就会把它读成 undefined，而界面上看起来一切正常。**
本脚本建的表结构就是为了把这些字段都算得出来。

## 分词器

远端用 FTS5 `trigram`，要求查询词 ≥3 个字符，否则回退 like/positional
（`kb_client.mjs:29-39` 有实测记录）。本地**用同一个分词器**，
这样 `scoreKind` 的语义不变 —— 否则客户端那句「只有 bm25 才算顺序可信」会误判。

## 用法

    python3 tools/kb_server/kb_build.py            # 建/重建
    python3 tools/kb_server/kb_build.py --check    # 只报现状，不写
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = Path(os.environ.get("KB_LOCAL_DB") or (Path.home() / ".shouheng" / "kb-local" / "kb.sqlite3"))

CONTRACT_VERSION = "kb-local-v1"

#: 子库 id 必须与 kb_client.mjs 的 COLLECTIONS 逐字一致（它按 id 拼 URL 路径）
COLLECTIONS: Dict[str, str] = {
    "1_外部标准库": "外部标准库：平台政策 / 法规 / 行业标准，条款级原文",
    "2_内部正负样本库": "内部正负样本：已审内容的原文与判定理由",
    "3_措辞表达库": "措辞表达库：规则、白名单、语境守卫",
}

#: 一个「文档」切成多长的分片。远端没有取全文的端点，返回的是 chunk
#: （`kb_client.mjs:42` 记着「一个文档可能占多个 chunk」）。
#: 这里取 400 字 —— 与 judge_evidence 的 EVIDENCE_TEXT_LIMIT=400 同量级。
CHUNK_CHARS = 400

SCHEMA_VERSION = "kb-local-index-v1"


# ───────────────────────── 源数据读取 ─────────────────────────

def _read_json(rel: str) -> Any:
    p = ROOT / rel
    if not p.exists():
        raise FileNotFoundError(f"源数据缺失：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def docs_from_standard() -> Iterator[Dict[str, Any]]:
    """外部标准库：一条条款 = 一个文档。"""
    d = _read_json("research/kb/外部标准库-v1.json")
    for e in d.get("entries") or []:
        clause = str(e.get("条款原文") or "").strip()
        summary = str(e.get("摘要") or "").strip()
        meaning = str(e.get("对判定的意义") or "").strip()
        # 正文按「原文 → 摘要 → 对判定的意义」拼：检索时要三段都能命中
        text = "\n".join(x for x in (clause, summary, meaning) if x)
        if not text.strip():
            continue
        yield {
            "doc_id": e.get("id"),
            "title": f"{e.get('clause_no') or e.get('id')} · {summary[:40] or clause[:40]}",
            "text": text,
            "meta": {
                "clause_no": e.get("clause_no"),
                "status": e.get("status"),
                "适用渠道": e.get("适用渠道"),
                "适用品线": e.get("适用品线"),
                "关联规则": e.get("关联规则"),
                "source_id": e.get("source_id"),
                "变更指纹": e.get("变更指纹"),
            },
        }


def docs_from_samples() -> Iterator[Dict[str, Any]]:
    """内部正负样本库：一条样本 = 一个文档。

    ★ 只索引**内容**字段（文字素材 / 具体原因 / 建议 / 备注），不索引人名。
      `审核人` / `填写/修改人` 是个人信息，不进公开仓的派生索引 ——
      虽然是本地文件，但「索引里有什么」是将来会被问的问题。
    """
    snap = _read_json("research/live/snapshot-20261020T162244Z.json")
    src = (snap.get("sources") or {}).get("kb_samples") or {}
    for rec in src.get("records") or []:
        f = rec.get("fields") or {}
        parts = [
            str(f.get("文字素材") or "").strip(),
            str(f.get("具体原因/分析") or "").strip(),
            str(f.get("建议") or "").strip(),
            str(f.get("备注（如处理结果/建议）") or "").strip(),
        ]
        text = "\n".join(p for p in parts if p)
        if not text.strip():
            continue
        title_bits = [str(f.get("品线") or ""), str(f.get("原因分类") or ""), str(f.get("渠道/市场") or "")]
        yield {
            "doc_id": rec.get("record_id") or rec.get("id"),
            "title": " · ".join(b for b in title_bits if b) or "（未分类样本）",
            "text": text,
            "meta": {
                "品线": f.get("品线"),
                "原因分类": f.get("原因分类"),
                "分类": f.get("分类"),
                "渠道/市场": f.get("渠道/市场"),
                "素材类型": f.get("素材类型"),
            },
        }


def docs_from_wording() -> Iterator[Dict[str, Any]]:
    """措辞表达库：规则 / 白名单 / 语境守卫，三类各成文档。"""
    rules = _read_json("research/governance/skeleton/rules-v1.json")
    for r in rules.get("rules") or []:
        m = r.get("match") or {}
        kws = [str(k) for k in (m.get("keywords") or [])]
        pats = [str(p) for p in (m.get("patterns") or [])]
        # 正文 = 关键词 + 正则 + 降级带说明：让「这个词属于哪条规则」可被检索到
        body = [
            f"规则 {r.get('rule_key')}（{r.get('parent_rule')}）",
            f"主题：{r.get('topic')} {r.get('topic_label')}",
            f"严重度：{r.get('severity')} · 处置：{r.get('disposition')}",
            f"关键词：{'、'.join(kws)}" if kws else "",
            f"正则：{' | '.join(pats)}" if pats else "",
        ]
        text = "\n".join(b for b in body if b)
        if not text.strip():
            continue
        yield {
            "doc_id": f"rule:{r.get('rule_key')}",
            "title": f"规则 {r.get('rule_key')} · {r.get('topic_label')}",
            "text": text,
            "meta": {"kind": "rule", "rule_key": r.get("rule_key"),
                     "severity": r.get("severity"), "keywords": kws},
        }

    wl = _read_json("research/governance/skeleton/whitelist-v1.json")
    for w in wl.get("words") or []:
        text = "\n".join(x for x in [
            f"白名单词：{w.get('word')}",
            f"状态：{w.get('status')} · 语言：{w.get('lang')}",
            f"豁免规则：{'、'.join(str(x) for x in (w.get('exempts_rule_keys') or []))}",
            f"隔离原因：{w.get('quarantine_reason')}" if w.get("quarantine_reason") else "",
        ] if x)
        yield {
            "doc_id": f"whitelist:{w.get('word')}",
            "title": f"白名单 {w.get('word')}",
            "text": text,
            "meta": {"kind": "whitelist", "word": w.get("word"), "status": w.get("status")},
        }

    cg = _read_json("research/governance/skeleton/context-guards-v1.json")
    for w in cg.get("words") or []:
        text = "\n".join(x for x in [
            f"语境守卫词：{w.get('word')}",
            f"类型：{w.get('guard_type')}",
            f"降级规则：{'、'.join(str(x) for x in (w.get('downgrades') or []))}",
            f"效果：{w.get('effect')}",
            f"接线状态：wired={w.get('wired')} · {w.get('status')}",
        ] if x)
        yield {
            "doc_id": f"guard:{w.get('word')}",
            "title": f"语境守卫 {w.get('word')}",
            "text": text,
            "meta": {"kind": "context_guard", "word": w.get("word"),
                     "wired": w.get("wired"), "status": w.get("status")},
        }


BUILDERS = {
    "1_外部标准库": docs_from_standard,
    "2_内部正负样本库": docs_from_samples,
    "3_措辞表达库": docs_from_wording,
}


# ───────────────────────── 分片 ─────────────────────────

_SENT_SPLIT = re.compile(r"(?<=[。！？；\n])|(?<=[.!?;])\s+")


def chunk_text(text: str, limit: int = CHUNK_CHARS) -> List[str]:
    """按句子边界切分片，尽量不切在句中。

    为什么按句而不是按固定长度切：一个被拦腰截断的条款，
    在检索结果里看起来像原文 —— 而它少了后半句的限定条件。
    这句「静默截断会让模型把半篇当全文」在本项目里记过一次（§2.4.1）。
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for piece in _SENT_SPLIT.split(text):
        if not piece:
            continue
        if len(cur) + len(piece) <= limit:
            cur += piece
            continue
        if cur.strip():
            out.append(cur.strip())
        # 单句本身就超长 → 硬切，但标记出来（见 chunk_note 的诚实说法）
        while len(piece) > limit:
            out.append(piece[:limit])
            piece = piece[limit:]
        cur = piece
    if cur.strip():
        out.append(cur.strip())
    return out or [text[:limit]]


# ───────────────────────── 建库 ─────────────────────────

def build(db_path: Path = DEFAULT_DB, verbose: bool = True) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp.sqlite3")
    for p in (tmp, Path(str(tmp) + "-wal"), Path(str(tmp) + "-shm")):
        if p.exists():
            p.unlink()

    conn = sqlite3.connect(str(tmp))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE doc (
          rowid     INTEGER PRIMARY KEY,
          doc_id    TEXT NOT NULL,
          collection TEXT NOT NULL,
          title     TEXT NOT NULL,
          meta_json TEXT NOT NULL,
          n_chunks  INTEGER NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE chunk (
          chunk_id  TEXT PRIMARY KEY,
          doc_rowid INTEGER NOT NULL,
          doc_id    TEXT NOT NULL,
          collection TEXT NOT NULL,
          title     TEXT NOT NULL,
          text      TEXT NOT NULL,
          ord       INTEGER NOT NULL
        )""")
    # trigram 分词器：与远端一致，保证 scoreKind 语义不变
    conn.execute("""
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
          text,
          content='chunk',
          content_rowid='rowid',
          tokenize='trigram'
        )""")
    conn.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")

    stats: Dict[str, Dict[str, int]] = {}
    for coll, builder in BUILDERS.items():
        n_doc = n_chunk = 0
        for d in builder():
            chunks = chunk_text(d["text"])
            if not chunks:
                continue
            cur = conn.execute(
                "INSERT INTO doc(doc_id,collection,title,meta_json,n_chunks) VALUES(?,?,?,?,?)",
                (d["doc_id"], coll, d["title"], json.dumps(d["meta"], ensure_ascii=False), len(chunks)))
            doc_rowid = cur.lastrowid
            for i, c in enumerate(chunks):
                cid = f"{d['doc_id']}#{i}"
                conn.execute(
                    "INSERT INTO chunk(chunk_id,doc_rowid,doc_id,collection,title,text,ord) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (cid, doc_rowid, d["doc_id"], coll, d["title"], c, i))
                n_chunk += 1
            n_doc += 1
        stats[coll] = {"docs": n_doc, "chunks": n_chunk}

    conn.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild')")

    # contentHash：与远端的同名概念对齐（内容真变了才变）。取全表正文的指纹。
    h = hashlib.sha256()
    for (t,) in conn.execute("SELECT text FROM chunk ORDER BY chunk_id"):
        h.update(t.encode("utf-8"))
    content_hash = h.hexdigest()

    conn.execute("INSERT INTO meta(k,v) VALUES(?,?)", ("schema_version", SCHEMA_VERSION))
    conn.execute("INSERT INTO meta(k,v) VALUES(?,?)", ("contract_version", CONTRACT_VERSION))
    conn.execute("INSERT INTO meta(k,v) VALUES(?,?)", ("content_hash", content_hash))
    conn.execute("INSERT INTO meta(k,v) VALUES(?,?)", ("built_at", _now_iso()))
    conn.commit()
    conn.execute("PRAGMA optimize")
    conn.close()

    tmp.replace(db_path)
    for p in (Path(str(tmp) + "-wal"), Path(str(tmp) + "-shm")):
        if p.exists():
            p.unlink()

    out = {"ok": True, "db": str(db_path), "content_hash": content_hash, "collections": stats}
    if verbose:
        total_d = sum(s["docs"] for s in stats.values())
        total_c = sum(s["chunks"] for s in stats.values())
        print(f"✅ 索引已建 {db_path}")
        for coll, s in stats.items():
            print(f"   {coll:<16} {s['docs']:>4} 文档 / {s['chunks']:>4} 分片")
        print(f"   {'合计':<16} {total_d:>4} 文档 / {total_c:>4} 分片")
        print(f"   content_hash = {content_hash[:16]}…")
    return out


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check(db_path: Path = DEFAULT_DB) -> Dict[str, Any]:
    if not db_path.exists():
        return {"ok": False, "reason": "索引不存在", "db": str(db_path)}
    conn = sqlite3.connect(str(db_path))
    try:
        meta = dict(conn.execute("SELECT k,v FROM meta"))
        rows = conn.execute(
            "SELECT collection, COUNT(DISTINCT doc_id), COUNT(*) FROM chunk GROUP BY collection"
        ).fetchall()
    finally:
        conn.close()
    return {"ok": True, "db": str(db_path), "meta": meta,
            "collections": {r[0]: {"docs": r[1], "chunks": r[2]} for r in rows}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报现状，不重建")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    a = ap.parse_args()
    db = Path(a.db).expanduser()
    try:
        r = build(db, verbose=not a.check) if not a.check else check(db)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if a.check:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
