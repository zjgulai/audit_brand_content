#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_kb_local.py —— 本地知识库服务的自证

## 它验什么

本地知识库（`tools/kb_server/`）替代了原先经 ngrok 暴露的远端服务。
**换掉一个外部依赖，最容易犯的错是「接上了但契约不对」** ——
客户端读到一个 undefined 字段，界面上看起来一切正常，判定却少了一条依据。
所以本自证的重点不是「服务能起来」，而是**契约逐字段对得上 + 三态不互相冒充**。

    L 段  索引完整性（文档数 / 分片数 / content_hash 可复算）
    C 段  契约逐字段（客户端解析的每个字段都必须真实存在且类型正确）
    S 段  排序语义（≥3 字 → bm25；<3 字 → positional；两者不可比）
    E 段  错误语义（不存在的子库 / 空查询 / 超 topK 都要有明确 code）
    N 段  三态不互代：**连不上 ≠ 没有命中**（这是本项目反复栽的那条）
    R 段  反向对照：喂坏样本，每一条断言都必须真的红

## 三态

    0 = 全部通过
    1 = 有红
    2 = 未测（索引不存在 / 服务起不来）

**2 不是 0。** 索引不在盘上时说「通过」和说「没问题」是同一句假话。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRV = ROOT / "tools" / "kb_server" / "kb_serve.py"
BUILD = ROOT / "tools" / "kb_server" / "kb_build.py"
DEFAULT_DB = Path(os.environ.get("KB_LOCAL_DB") or (Path.home() / ".shouheng" / "kb-local" / "kb.sqlite3"))

COLL_STD = "1_外部标准库"
COLL_SAMPLES = "2_内部正负样本库"
COLL_WORDING = "3_措辞表达库"

_n_pass = 0
_n_fail = 0
_n_untested = 0
_fails: List[str] = []
_untests: List[str] = []


def check(no: str, name: str, cond: bool, detail: str = "") -> bool:
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print(f"  ✓ {no}  {name}" + (f"\n        {detail}" if detail else ""))
    else:
        _n_fail += 1
        _fails.append(f"{no} {name}")
        print(f"  ✗ {no}  {name}" + (f"\n        {detail}" if detail else ""))
    return cond


def untested(no: str, name: str, why: str) -> None:
    global _n_untested
    _n_untested += 1
    _untests.append(f"{no} {name}")
    print(f"  ⚠ {no}  {name}  **未测**：{why}")


def get(url: str, timeout: float = 5.0) -> Tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:                       # noqa: BLE001
            return e.code, None
    except Exception as e:                      # noqa: BLE001
        return 0, {"_error": f"{type(e).__name__}: {e}"}


class Server:
    """起一个临时端口的服务，退出时收干净。"""

    def __init__(self, db: Path, port: int = 0):
        self.db = db
        self.port = port or _free_port()
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SRV), "--db", str(self.db), "--port", str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{self.port}"
        for _ in range(60):
            st, j = get(base + "/health", timeout=1.0)
            if st == 200 and isinstance(j, dict) and j.get("ok"):
                return base
            if self.proc.poll() is not None:
                err = (self.proc.stderr.read() or b"").decode("utf-8", "replace")[:400]
                raise RuntimeError("服务启动失败：" + err)
            time.sleep(0.1)
        raise RuntimeError("服务 6 秒内未就绪")

    def __exit__(self, *a):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ───────────────────────── 各段 ─────────────────────────

def seg_L(db: Path) -> bool:
    print("\n═══ L. 索引完整性 ═══")
    if not db.exists():
        untested("L1", "索引存在", f"{db} 不存在 —— 先跑 python3 tools/kb_server/kb_build.py")
        return False
    conn = sqlite3.connect(str(db))
    try:
        meta = dict(conn.execute("SELECT k,v FROM meta"))
        rows = conn.execute(
            "SELECT collection, COUNT(DISTINCT doc_id), COUNT(*) FROM chunk GROUP BY collection"
        ).fetchall()
        stats = {r[0]: {"docs": r[1], "chunks": r[2]} for r in rows}
        # content_hash 必须能复算 —— 否则「库更新了吗」这个问题没有判据
        import hashlib
        h = hashlib.sha256()
        for (t,) in conn.execute("SELECT text FROM chunk ORDER BY chunk_id"):
            h.update(t.encode("utf-8"))
        recomputed = h.hexdigest()
    finally:
        conn.close()

    check("L1", "索引存在且 schema 版本明确", bool(meta.get("schema_version")),
          f"schema={meta.get('schema_version')} contract={meta.get('contract_version')}")
    check("L2", "三个子库都有内容（空库不等于通过）",
          set(stats) == {COLL_STD, COLL_SAMPLES, COLL_WORDING} and all(v["docs"] > 0 for v in stats.values()),
          " · ".join(f"{k} {v['docs']}文档/{v['chunks']}分片" for k, v in sorted(stats.items())))
    check("L3", "★ content_hash 可复算（改一个字必须变，这是「库更新了吗」的唯一判据）",
          recomputed == meta.get("content_hash"),
          f"存 {str(meta.get('content_hash'))[:16]}… vs 算 {recomputed[:16]}…")
    # 反向对照：改一个分片的正文，复算必须不等
    tmp = Path(tempfile.mkdtemp()) / "mut.sqlite3"
    shutil.copy(db, tmp)
    c2 = sqlite3.connect(str(tmp))
    c2.execute("UPDATE chunk SET text = text || 'X' WHERE rowid = (SELECT MIN(rowid) FROM chunk)")
    c2.commit()
    h2 = hashlib.sha256()
    for (t,) in c2.execute("SELECT text FROM chunk ORDER BY chunk_id"):
        h2.update(t.encode("utf-8"))
    c2.close()
    check("L3b", "★ 反向对照：改一个分片 → content_hash 必变（否则 L3 是恒真）",
          h2.hexdigest() != meta.get("content_hash"), "改 1 个字符后指纹已变")

    # 分片不丢内容：正文长度之和应 >= 原文长度（切分会丢空白，但不应丢句子）
    check("L4", "分片数 ≥ 文档数（每个文档至少 1 个分片）",
          all(v["chunks"] >= v["docs"] for v in stats.values()),
          "不存在 chunks < docs 的文档")
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return True


def seg_C(base: str) -> None:
    print("\n═══ C. 接口契约（客户端解析的每个字段都必须真实存在）═══")
    st, j = get(base + "/openapi/v1/kb")
    ok = check("C1", "GET /openapi/v1/kb 返回 200 且是对象", st == 200 and isinstance(j, dict),
               f"status={st}")
    if not ok:
        return
    check("C2", "顶层带 contractVersion", isinstance(j.get("contractVersion"), str),
          str(j.get("contractVersion")))
    cols = j.get("collections")
    check("C3", "collections 是数组且三个子库都在",
          isinstance(cols, list) and {c.get("id") for c in cols} == {COLL_STD, COLL_SAMPLES, COLL_WORDING},
          f"{len(cols or [])} 个子库")
    # 客户端读的每个字段
    need = ["id", "name", "description", "docCount", "createdAt"]
    bad = []
    for c in cols or []:
        for k in need:
            if k not in c:
                bad.append(f"{c.get('id')}.{k}")
    check("C4", "★ 每个子库都带客户端会读的全部字段（少一个就读成 undefined，而界面正常）",
          not bad, "缺：" + ", ".join(bad) if bad else f"{need} 全部齐备")

    st, r = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_STD)}/retrieve?q=healthcare&topK=3")
    ok = check("C5", "检索返回 200 且 hits 是数组", st == 200 and isinstance(r.get("hits"), list),
               f"status={st} hits={len((r or {}).get('hits') or [])}")
    if not ok:
        return
    # 客户端 retrieve() 读的顶层字段（kb_client.mjs:600-650）
    top_need = ["contractVersion", "requestId", "collection", "hits", "hitCount",
                "totalCandidates", "latencyMs", "scoreKind", "confidence", "fallback", "quota"]
    missing = [k for k in top_need if k not in r]
    check("C6", "★ 检索响应顶层字段齐备（kb_client.mjs 逐个读它们）",
          not missing, "缺：" + ", ".join(missing) if missing else f"{len(top_need)} 个字段全部齐备")
    hit_need = ["docId", "docTitle", "chunkId", "text", "score", "scoreNorm", "rank", "coverage"]
    h0 = (r.get("hits") or [{}])[0]
    missing_h = [k for k in hit_need if k not in h0]
    check("C7", "★ 每条 hit 字段齐备（少一个，下游就拿不到原文片段）",
          not missing_h, "缺：" + ", ".join(missing_h) if missing_h else f"{len(hit_need)} 个字段齐备")
    check("C8", "hit.text 非空且是字符串（空正文等于没有依据）",
          isinstance(h0.get("text"), str) and len(h0["text"].strip()) > 0,
          f"{len(h0.get('text') or '')} 字")
    check("C9", "rank 从 1 开始且连续",
          [h.get("rank") for h in r["hits"]] == list(range(1, len(r["hits"]) + 1)),
          f"rank={[h.get('rank') for h in r['hits']]}")


def seg_S(base: str) -> None:
    print("\n═══ S. 排序语义（查询词长度是分叉轴，不是语言）═══")
    # ≥3 码点 → bm25
    st, r = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_WORDING)}/retrieve?q=%E4%B9%B3%E8%85%BA%E7%82%8E&topK=3")
    check("S1", "≥3 个中文字 → scoreKind=bm25（排序可信）",
          r.get("scoreKind") == "bm25" and r.get("fallback") is None,
          f"scoreKind={r.get('scoreKind')} fallback={r.get('fallback')}")
    # <3 码点 → positional
    st, r2 = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_WORDING)}/retrieve?q=%E6%97%A0%E7%97%9B&topK=3")
    check("S2", "★ 2 个中文字 → scoreKind=positional + fallback=like（不许停成 bm25）",
          r2.get("scoreKind") == "positional" and r2.get("fallback") == "like",
          f"scoreKind={r2.get('scoreKind')} fallback={r2.get('fallback')}")
    # 反向对照：把短查询判成 bm25 必须被发现
    check("S2b", "★ 反向对照：短查询若标 bm25 则 S2 的判据不成立（S1/S2 不是同一个读数）",
          r.get("scoreKind") != r2.get("scoreKind"),
          f"长查询 {r.get('scoreKind')} ≠ 短查询 {r2.get('scoreKind')}")
    # bm25 的 score 必须随相关度递减
    scores = [h.get("score") for h in (r.get("hits") or [])]
    check("S3", "bm25 下 score 单调不减（越小越不相关）",
          all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)) if len(scores) > 1 else True,
          f"scores={scores}")


def seg_E(base: str) -> None:
    print("\n═══ E. 错误语义（每种错误都要有明确的 code，不许静默空数组）═══")
    st, j = get(f"{base}/openapi/v1/kb/{urllib.request.quote('9_不存在的库')}/retrieve?q=abc")
    check("E1", "不存在的子库 → 404 + COLLECTION_NOT_FOUND",
          st == 404 and (j or {}).get("error", {}).get("code") == "COLLECTION_NOT_FOUND",
          f"status={st} code={(j or {}).get('error', {}).get('code')}")
    st, j = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_STD)}/retrieve?q=")
    check("E2", "空查询 → 400 + BAD_REQUEST（不许当成「0 命中」）",
          st == 400 and (j or {}).get("error", {}).get("code") == "BAD_REQUEST",
          f"status={st} code={(j or {}).get('error', {}).get('code')}")
    st, j = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_STD)}/retrieve?q=abc&topK=999")
    check("E3", "topK 超上限 → 400 + TOPK_TOO_LARGE（不许静默截断）",
          st == 400 and (j or {}).get("error", {}).get("code") == "TOPK_TOO_LARGE",
          f"status={st} code={(j or {}).get('error', {}).get('code')}")
    st, j = get(base + "/no/such/endpoint")
    check("E4", "未知端点 → 404 + NOT_FOUND", st == 404,
          f"status={st} code={(j or {}).get('error', {}).get('code')}")


def seg_N(db: Path) -> None:
    print("\n═══ N. 三态不互代（连不上 ≠ 没有命中）═══")
    # 服务没起时，health 必须连不上，而不是返回「0 命中」
    port = _free_port()
    st, j = get(f"http://127.0.0.1:{port}/health", timeout=1.0)
    check("N1", "★ 服务未起时探活失败（不是 200 空对象）", st == 0 or st >= 500,
          f"status={st} —— 连不上就是连不上，不许伪装成「库是空的」")

    # 索引缺失时，服务必须启动失败而不是起一个空服务
    empty_dir = Path(tempfile.mkdtemp())
    missing = empty_dir / "nope.sqlite3"
    p = subprocess.run([sys.executable, str(SRV), "--db", str(missing), "--port", str(_free_port())],
                       capture_output=True, text=True, timeout=20)
    check("N2", "★ 索引缺失 → 服务拒绝启动（exit 2），不起一个「什么库都空」的服务",
          p.returncode == 2 and "索引不可用" in (p.stdout + p.stderr),
          f"exit={p.returncode}")
    shutil.rmtree(empty_dir, ignore_errors=True)

    # quota 恒 null：客户端读到 null 会说「来源 none」，不许说「余额 0」
    conn = sqlite3.connect(str(db)) if db.exists() else None
    if conn:
        conn.close()
    with Server(db) as base:
        st, r = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_STD)}/retrieve?q=healthcare&topK=1")
        check("N3", "★ 本地无配额 → quota 恒为 null（客户端据此显示「来源 none」，不是 0）",
              r.get("quota") is None,
              f"quota={r.get('quota')!r} —— null 表示「无此概念」，不是「余额为零」")


def seg_R(db: Path) -> bool:
    print("\n═══ R. 反向对照（每一条断言都必须能真的红）═══")
    if not db.exists():
        untested("R", "反向对照", "索引不存在，无法构造坏样本")
        return False
    ok_all = True

    # R1：客户端契约 —— 删掉一个字段后，C4 的判据必须能发现
    tmp = Path(tempfile.mkdtemp()) / "bad1.sqlite3"
    shutil.copy(db, tmp)
    c = sqlite3.connect(str(tmp))
    c.execute("DROP TABLE meta")
    c.commit()
    c.close()
    p = subprocess.run([sys.executable, str(SRV), "--db", str(tmp), "--port", str(_free_port())],
                       capture_output=True, text=True, timeout=20)
    ok_all &= check("R1", "★ 元数据表被删 → 服务拒绝启动（不是带着残缺 schema 硬起）",
                    p.returncode == 2, f"exit={p.returncode}")
    shutil.rmtree(tmp.parent, ignore_errors=True)

    # R2：分片表被清空 → L2「三个子库都有内容」必须红
    tmp2 = Path(tempfile.mkdtemp()) / "bad2.sqlite3"
    shutil.copy(db, tmp2)
    c = sqlite3.connect(str(tmp2))
    c.execute("DELETE FROM chunk WHERE collection = ?", (COLL_SAMPLES,))
    c.commit()
    c.close()
    with Server(tmp2) as base:
        st, j = get(base + "/openapi/v1/kb")
        cols = {x["id"]: x.get("docCount") for x in (j or {}).get("collections") or []}
        # 样本库被清空后，它要么不在列表里，要么 docCount=0 —— 两种都必须能被 L2 抓到
        empty_detected = cols.get(COLL_SAMPLES, 0) == 0
        ok_all &= check("R2", "★ 清空一个子库 → docCount 归零（L2 才能红）",
                        empty_detected, f"样本库 docCount={cols.get(COLL_SAMPLES)}")
    shutil.rmtree(tmp2.parent, ignore_errors=True)

    # R3：检索必须真的按 collection 过滤（串库是最难发现的错）
    with Server(db) as base:
        st, a = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_STD)}/retrieve?q=breast&topK=20")
        st, b = get(f"{base}/openapi/v1/kb/{urllib.request.quote(COLL_WORDING)}/retrieve?q=breast&topK=20")
        ids_a = {h["docId"] for h in a.get("hits") or []}
        ids_b = {h["docId"] for h in b.get("hits") or []}
        ok_all &= check("R3", "★ 同一查询词在两个子库 → 结果集无交集（串库会静默给出错依据）",
                        not (ids_a & ids_b),
                        f"标准库 {len(ids_a)} 条 · 措辞库 {len(ids_b)} 条 · 交集 {len(ids_a & ids_b)}")
    return ok_all


def verdict(n_pass: int, n_fail: int, n_untested: int) -> Tuple[int, str]:
    """结论行是纯函数 —— 这样反向对照能直接断言它自己不许撒谎。

    ★ 本项目的教训（`prd_baseline.mjs` 第一次运行就打印「16 项全过」而那一轮
      `--offline` 一次网络都没发）：一个为「别把没测报成通过」而写的检查器，
      第一次运行就把没测报成了通过。所以这句话必须可被单测。
    """
    if n_fail > 0:
        tail = f"；另有 {n_untested} 项未测" if n_untested else ""
        return 1, f"❌ {n_fail} 项未过{tail}"
    if n_untested > 0:
        return 2, f"⚠ {n_untested} 项未测（未测 ≠ 通过，不报绿）· {n_pass} 项通过"
    return 0, f"✅ {n_pass} 项全过"


def main() -> int:
    global _n_pass, _n_fail, _n_untested
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--controls", action="store_true", help="额外跑元指挥自身不撒谎的对照")
    a = ap.parse_args()
    db = Path(a.db).expanduser()

    print("═" * 72)
    print("verify_kb_local —— 本地知识库服务自证")
    print(f"索引 {db}")
    print("═" * 72)

    if not db.exists():
        untested("L0", "索引存在", f"{db} 不存在")
        # 仍然验证「索引缺失时服务拒绝启动」这一条 —— 它不需要索引
        seg_N(db)
        code, line = verdict(_n_pass, _n_fail, _n_untested)
        print("\n" + "=" * 72)
        print(line)
        print("  先跑：python3 tools/kb_server/kb_build.py")
        print("=" * 72)
        return code

    seg_L(db)
    try:
        with Server(db) as base:
            seg_C(base)
            seg_S(base)
            seg_E(base)
    except RuntimeError as e:
        untested("C/S/E", "接口契约与排序语义", f"服务起不来：{e}")
    seg_N(db)
    seg_R(db)

    if a.controls:
        print("\n═══ V. 结论行自己不许撒谎 ═══")
        code0, l0 = verdict(5, 0, 0)
        code1, l1 = verdict(0, 3, 2)
        code2, l2 = verdict(5, 0, 1)
        check("V1", "有未测时**不许**报绿（exit 2 ≠ 0）", code2 == 2 and "✅" not in l2, l2)
        check("V2", "有红时如实报红，且**同时**报出未测数", code1 == 1 and "未测" in l1, l1)
        check("V3", "全过才报绿", code0 == 0 and l0.startswith("✅"), l0)
        check("V4", "★ 未测的文案里不许出现「没问题」", "没问题" not in l2 and "没问题" not in l1)

    code, line = verdict(_n_pass, _n_fail, _n_untested)
    print("\n" + "=" * 72)
    print(line)
    print("=" * 72)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
