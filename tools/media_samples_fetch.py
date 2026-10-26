#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""media_samples_fetch.py — 取真实媒体素材（图片 / 视频）到仓外落盘根

## 它为什么存在

`WBPM-0090` 的验收标准是「语义、OCR 与 ASR **三类各自在真实载体上**通过」。
在此之前媒体线只用「落地页抓来的 120 条图」验过，视频一条都没有 ——
而 `verify_video_ingest` 的 X 层因此只能报「未测」。

这个工具把「真实载体」变成可重复取到的东西。**两种来源，优先用表里的**：

| 来源 | 判据 | 代价 |
|---|---|---|
| **A 飞书「守衡测试-源」表的直链** | 表里 `采集数据` 字段逐条带 `【图片】`/`【视频】` URL | 直接、免第三方、素材是业务方**真在用**的 |
| B apify actor | 表里没有的形态（如特定平台导出） | 要烧 apify 额度；多一层依赖 |

★ 2026-10-27 实测：表里 111 条里 **48 条带图片直链、15 条带视频直链**，
  且 `HEAD` 探针返回 `video/mp4` / 26.5MB —— 所以**不必先依赖 apify**。
  apify 保留为「表里没有的形态」的补充通道，不是主路。

## 红线（AGENTS.md §2.6）

下载物**不许进公开仓**。所以：
* 落盘根必须在**仓外**且 0700（默认 `~/audit-data/media-samples`）；
* 本文件是**已登记的下载调用点**（`tools/download_callers.json`），
  `verify_download_governance` 的 DG-1 要求每个调用点都能指出消费者与落盘路径；
* **不写仓内任何路径** —— 落盘前断言一次，写盘时不接受相对路径。

## 凭据

apify token **只读环境变量** `APIFY_API_KEY`，不读凭据文件（与
`tools/multimodal_client.py` 同一条规矩：网络客户端不翻凭据目录）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 默认落盘根：**仓外**，0700。★ 不设成仓内任何路径 —— 那是 §2.6 红线。
DEFAULT_LANDING = Path.home() / "audit-data" / "media-samples"

#: 素材表的坐标（飞书「内容治理问题描述」→「守衡测试-源」）
SOURCE_APP = "RY2UbCRjXaeeWwscUPScVN5AnQc"
SOURCE_TABLE = "tblTPsjiyOHYfUc0"

#: 从 `采集数据` 里抠 URL 的两种标签
_URL_RE = re.compile(r"【(图片|视频)】\s*(\S+)")

#: apify actor（B 路）。用前须显式 --via apify 且配好 APIFY_API_KEY。
DEFAULT_ACTOR = "apify/instagram-scraper"

MAX_BYTES = 200 * 1024 * 1024


class FetchError(RuntimeError):
    pass


# ──────────────────────────────────────────────────────────────────────
# 落盘根：仓外 + 0700
# ──────────────────────────────────────────────────────────────────────

def check_landing(root: str | Path) -> Path:
    """落盘根必须是**仓外**目录且 0700（不存在则建）。

    ★ 与 `verify_download_governance` DG-2 同一判据：它验登记表里的字符串，
      这里验运行时的真实路径。两处都查，因为字符串对不代表运行时对
      （环境变量、软链都能让它偏掉）。
    """
    path = Path(root).expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise FetchError(
            "落盘根不许在仓内（%s）—— 仓是公开的（AGENTS.md §2.6）" % path)
    path.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777
    if mode != 0o700:
        os.chmod(path, 0o700)
        mode = path.stat().st_mode & 0o777
    if mode != 0o700:
        raise FetchError("落盘根权限必须是 0700，实际 %o" % mode)
    return path


# ──────────────────────────────────────────────────────────────────────
# A 路：飞书表里的直链
# ──────────────────────────────────────────────────────────────────────

def read_source_rows(*, cred: Optional[str] = None) -> List[Dict[str, Any]]:
    """读「守衡测试-源」表，返回 [{spu, kind, url, product, channel, content_type}]。

    ★ 只读，不改表。凭据走 `~/.dsh/credentials/shouheng-lark.json`
      （与 `tools/lark_*.py` 同一份，仓外 0700）。
    """
    cred_path = Path(cred or os.path.expanduser(
        "~/.dsh/credentials/shouheng-lark.json"))
    if not cred_path.is_file():
        raise FetchError("凭据不存在：%s" % cred_path)
    cfg = json.loads(cred_path.read_text(encoding="utf-8"))
    base = "https://open.feishu.cn/open-apis"

    def req(url: str, token: Optional[str] = None, payload: Any = None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            url, data=data, method="POST" if data else "GET")
        if token:
            request.add_header("Authorization", "Bearer " + token)
        if data:
            request.add_header("Content-Type", "application/json; charset=utf-8")
        with urllib.request.urlopen(request, timeout=40) as resp:
            return json.loads(resp.read())

    got = req(base + "/auth/v3/tenant_access_token/internal", None,
              {"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]})
    if got.get("code") != 0:
        raise FetchError("取 token 失败：%r" % (got,))
    token = got["tenant_access_token"]

    rows: List[Dict[str, Any]] = []
    page_token = ""
    while True:
        url = ("%s/bitable/v1/apps/%s/tables/%s/records?page_size=200"
               % (base, SOURCE_APP, SOURCE_TABLE))
        if page_token:
            url += "&page_token=" + page_token
        got = req(url, token)
        if got.get("code") != 0:
            raise FetchError("读表失败：%r" % (got,))
        data = got.get("data") or {}
        for item in data.get("items") or []:
            fields = item.get("fields") or {}
            raw = str(fields.get("采集数据") or "")
            for kind, link in _URL_RE.findall(raw):
                kind_en = "image" if kind == "图片" else "video"
                rows.append({
                    "spu": fields.get("产品spu"),
                    "product": fields.get("产品中文名"),
                    "channel": fields.get("渠道"),
                    "content_type": fields.get("内容类型"),
                    "kind": kind_en,
                    "url": link,
                    "record_id": item.get("record_id"),
                })
        page_token = data.get("page_token") or ""
        if not data.get("has_more") or not page_token:
            break
    return rows


# ──────────────────────────────────────────────────────────────────────
# B 路：apify
# ──────────────────────────────────────────────────────────────────────

def apify_run(actor: str, payload: Dict[str, Any], *, token: str,
              timeout: float = 300.0) -> List[Dict[str, Any]]:
    """跑一个 apify actor 直到完成，返回 dataset items。

    ★ token **只从参数来**（调用方从环境变量读）。本函数不翻凭据目录。
    """
    endpoint = ("https://api.apify.com/v2/acts/%s/run-sync-get-dataset-items"
                "?token=%s" % (urllib.parse.quote(actor, safe="/"), token))
    data = json.dumps(payload).encode()
    request = urllib.request.Request(endpoint, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError("apify HTTP %s：%s"
                         % (exc.code, exc.read()[:300])) from exc
    except Exception as exc:  # noqa: BLE001
        raise FetchError("apify 调用失败：%s" % exc) from exc
    try:
        items = json.loads(raw or b"[]")
    except json.JSONDecodeError as exc:
        raise FetchError("apify 返回不是 JSON") from exc
    if not isinstance(items, list):
        raise FetchError("apify 返回不是数组：%r" % type(items).__name__)
    return items


# ──────────────────────────────────────────────────────────────────────
# 下载
# ──────────────────────────────────────────────────────────────────────

def _safe_name(row: Dict[str, Any], index: int) -> str:
    """给落盘文件起名：SPU + 类型 + 序号 + 原后缀。**不含 URL**（可能带签名）。"""
    suffix = Path(urllib.parse.urlparse(row["url"]).path).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"):
        suffix = ".bin"
    spu = re.sub(r"[^A-Za-z0-9_-]", "", str(row.get("spu") or "unknown"))
    return "%s-%s-%03d%s" % (spu, row["kind"], index, suffix)


def download(url: str, target: Path, *, timeout: float = 120.0) -> Dict[str, Any]:
    """下一个文件。返回 {ok, bytes, sha256, content_type, error?}。

    ★ 不写 `target` 之外的任何路径；`target` 必须是绝对路径且父目录已建。
    """
    if not target.is_absolute():
        raise FetchError("落盘路径必须是绝对路径：%s" % target)
    request = urllib.request.Request(url, method="GET")
    # 有些 CDN 对空 UA 直接 403；这不是伪装，是基本的礼貌标识。
    request.add_header("User-Agent", "audit-multi-content/1.0 (media sample fetch)")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            length = resp.headers.get("Content-Length")
            if length and int(length) > MAX_BYTES:
                return {"ok": False, "error": "too_large:%s" % length}
            chunks = []
            total = 0
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    return {"ok": False, "error": "too_large_stream"}
                chunks.append(chunk)
            blob = b"".join(chunks)
            content_type = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "http_%s" % exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s:%s" % (type(exc).__name__, exc)}
    digest = hashlib.sha256(blob).hexdigest()
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(blob)
    tmp.replace(target)
    return {"ok": True, "bytes": len(blob), "sha256": digest,
            "content_type": content_type, "path": str(target)}


def fetch_rows(rows: List[Dict[str, Any]], *, landing: Path,
               only: Optional[str] = None, limit: Optional[int] = None,
               dry_run: bool = True) -> Dict[str, Any]:
    """按行下载。`only` 取 image/video；`dry_run` 只报计划不落盘。"""
    picked = [r for r in rows if not only or r["kind"] == only]
    if limit is not None:
        picked = picked[:limit]
    plan = []
    for index, row in enumerate(picked, 1):
        target = landing / _safe_name(row, index)
        plan.append({"row": row, "target": target})
    if dry_run:
        return {"dry_run": True, "planned": len(plan),
                "items": [{"url": p["row"]["url"], "kind": p["row"]["kind"],
                           "target": str(p["target"])} for p in plan]}
    results = []
    for item in plan:
        out = download(item["row"]["url"], item["target"])
        out.update({"kind": item["row"]["kind"], "spu": item["row"].get("spu"),
                    "url": item["row"]["url"]})
        results.append(out)
    ok = [r for r in results if r.get("ok")]
    return {
        "dry_run": False, "attempted": len(results), "ok": len(ok),
        "failed": len(results) - len(ok),
        "results": results,
        "manifest": [{"kind": r["kind"], "spu": r.get("spu"),
                      "bytes": r.get("bytes"), "sha256": r.get("sha256"),
                      "path": r.get("path"), "error": r.get("error")}
                     for r in results],
    }


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main(argv) -> int:
    ap = argparse.ArgumentParser(
        description="取真实媒体素材到仓外落盘根（默认 dry-run）")
    ap.add_argument("--landing", default=str(DEFAULT_LANDING),
                    help="落盘根（必须在仓外，0700）")
    ap.add_argument("--only", choices=("image", "video"),
                    help="只取图片或视频")
    ap.add_argument("--limit", type=int, help="最多取几条")
    ap.add_argument("--via", choices=("table", "apify"), default="table",
                    help="来源：表里的直链（默认）或 apify")
    ap.add_argument("--actor", default=DEFAULT_ACTOR, help="apify actor id")
    ap.add_argument("--actor-input", help="apify 输入 JSON 文件")
    ap.add_argument("--apply", action="store_true", help="真下载（默认 dry-run）")
    args = ap.parse_args(argv)

    try:
        landing = check_landing(args.landing)
    except FetchError as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 2
    print("落盘根：%s（%o）" % (landing, landing.stat().st_mode & 0o777))

    if args.via == "apify":
        token = (os.environ.get("APIFY_API_KEY") or "").strip()
        if not token:
            print("未测：APIFY_API_KEY 未配（本工具只读环境变量，不读凭据文件）")
            return 2
        payload = {}
        if args.actor_input:
            payload = json.loads(Path(args.actor_input).read_text(encoding="utf-8"))
        try:
            items = apify_run(args.actor, payload, token=token)
        except FetchError as exc:
            print("❌ %s" % exc, file=sys.stderr)
            return 2
        rows = []
        for item in items:
            url = item.get("videoUrl") or item.get("displayUrl") or item.get("url")
            if not url:
                continue
            kind = "video" if str(url).endswith(".mp4") else "image"
            rows.append({"spu": item.get("shortCode") or "apify",
                         "kind": kind, "url": str(url)})
        print("apify 返回 %d 条可用素材" % len(rows))
    else:
        try:
            rows = read_source_rows()
        except FetchError as exc:
            print("❌ %s" % exc, file=sys.stderr)
            return 2
        print("表里共 %d 个素材直链（图片 %d / 视频 %d）"
              % (len(rows),
                 sum(1 for r in rows if r["kind"] == "image"),
                 sum(1 for r in rows if r["kind"] == "video")))

    out = fetch_rows(rows, landing=landing, only=args.only, limit=args.limit,
                     dry_run=not args.apply)
    if out.get("dry_run"):
        print("\n★ dry-run：将取 %d 条" % out["planned"])
        for item in out["items"][:10]:
            print("  [%s] %s → %s" % (item["kind"], item["url"][:70],
                                       Path(item["target"]).name))
        if out["planned"] > 10:
            print("  …… 还有 %d 条" % (out["planned"] - 10))
        print("\n确认后加 --apply 真下载。")
        return 0
    print("\n成功 %d / 失败 %d" % (out["ok"], out["failed"]))
    for res in out["results"]:
        if res.get("ok"):
            print("  ✅ %-34s %8d B  %s…" % (
                Path(res["path"]).name, res["bytes"], res["sha256"][:12]))
        else:
            print("  ❌ %-34s %s" % (res.get("spu"), res.get("error")))
    return 0 if out["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
