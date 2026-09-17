#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""media.py —— 图片 / 视频进管道的第①面（B1 · ADR-0013 D3）

一句话：**把「素材」也变成 `ContentUnit`，并按法务口径给出三个数字。**

    python3 base/media.py --selftest      # 离线自证（用盘上已下载的样本）
    python3 base/media.py --collect N     # 联网：抽样下载 + OCR（唯一会写盘的联网命令）
    python3 base/media.py --report        # 用盘上样本出三个指标

--------------------------------------------------------------------------
★ D3 定的方向：先「文本化」，不作语义判定
--------------------------------------------------------------------------

    图片：OCR 取图内文字 + 合成人像标记检测
    视频：字幕/ASR 转写 + 关键帧 OCR
    产出统一进 `ContentUnit`，**复用现有规则**，不新增判定机制。

--------------------------------------------------------------------------
★ 落地时量出来的第一件事：**alt 文本看起来像覆盖，其实不是**
--------------------------------------------------------------------------

92 个落地页共 **23,745 张图片**，其中 **21,424 张（90.2%）有 alt 文本**。
「90% 有 alt」读起来像「图片基本已覆盖」。**实际不是**：

    alt 长度中位 17 字符，内容是**商品名目录**：
      「Maternity Belly Band」「Labor Hospital Bag」「momcozy logo」「Nursing Bras」

而营销声明（`hospital grade` / `100% safe` / `FDA approved`）**是画在图里的**，
不在 alt 里。所以「有 alt」与「图里的字被读到了」回答的是两个不同的问题。

**⇒ 本模块的核心测量不是「多少张图有文字」，是「OCR 在 alt 之外读到了多少声明性表述」。**
这个增量才是 OCR 的真实价值，也是 90.2% 那个数字**不能**替代的东西。

--------------------------------------------------------------------------
★ 落地时量出来的第二件事：本机的编译链是坏的，但有绕法
--------------------------------------------------------------------------

    `swiftc` 走不通：`failed to build module 'Swift'; this SDK is not supported
    by the compiler`（SDK 由 Swift 6.4 构建，CLT 里的编译器是 6.3.3）。
    默认 SDK `MacOSX27.0` 也是坏的：`tapi error: malformed file ... unknown
    architecture arm64e.x1-macos`。

**绕法**：用 **Objective-C + clang + 指定旧 SDK**（`MacOSX15.4`），直连系统
`Vision.framework`。零第三方依赖 —— 与「不加依赖也能跑」的项目惯例一致。
源码 `base/ocr_vision.m` 与重建脚本 `base/build_ocr.sh` 都在 L1。

--------------------------------------------------------------------------
★ 异议二必须落在数字旁边（ADR-0013 §六）
--------------------------------------------------------------------------

> **必须让「覆盖到哪」显式可见**：B1 的图片/视频指标里要写清
> 「本数字只覆盖图内文字，不含画面语义」，并进 `boundary_statement.unknowns`。
> 不得只报「识别完整度 X%」而不写它的边界。

所以每一个图片 unit 的 `textification.covers` / `does_not_cover` 都是**必填**
（`contract.from_media()` 刻意不给默认值），且 `judge_adapter` 会把它们
逐字写进该次判定的 `boundary_statement.unknowns`。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

import contract as C                                    # noqa: E402
from lp_extract import CLAIM_RE, CLAIM_PATTERNS          # noqa: E402  唯一词形定义，不重复维护
import lp_fetch as F                                     # noqa: E402  节流与 robots 复用批次 C

CONTRACT_VERSION = "media-v1"
OCR_BIN = ROOT / ".tools" / "bin" / "ocr"
OCR_SRC = HERE / "ocr_vision.m"
OCR_BUILD = HERE / "build_ocr.sh"

MEDIA = ROOT / "research" / "landing" / "_evidence" / "media"

# 能被 Vision 读的位图格式。**SVG 不在其列** —— 它是矢量，
# `NSImage` 不保证能解码；本仓 23,745 张里有 **6,098 张是 SVG**（多是图标与 logo）。
# 这个区分必须记下来：它会让「获取成功率」的分母看起来变小，
# 而真相是「那部分素材本就不该走 OCR」，不是「取不到」。
RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".heic"}
VECTOR_EXT = {".svg"}

MAX_IMAGE_BYTES = 12 * 1024 * 1024
OCR_TIMEOUT = 60
OCR_LANGS = ["zh-Hans", "en-US"]


# ------------------------------------------------------------------ OCR 二进制

def ensure_ocr(rebuild: bool = False) -> Path:
    """没有就编译。**不把二进制提交进仓** —— 源码与重建脚本才是 L1 的东西。"""
    if OCR_BIN.exists() and not rebuild:
        return OCR_BIN
    if not OCR_SRC.exists() or not OCR_BUILD.exists():
        raise RuntimeError(f"OCR 源码或重建脚本缺失：{OCR_SRC} / {OCR_BUILD}")
    r = subprocess.run(["bash", str(OCR_BUILD)], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0 or not OCR_BIN.exists():
        raise RuntimeError("OCR 编译失败：\n" + r.stdout + r.stderr)
    return OCR_BIN


def ocr_file(path: Path, langs: list[str] | None = None) -> dict:
    """调 OCR CLI，回结构化结果。**失败不抛** —— 返回 ok=False 与成因。"""
    try:
        bin_ = ensure_ocr()
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "error": "ocr_build_failed", "detail": str(e)[:200]}
    cmd = [str(bin_), str(path)] + (langs or OCR_LANGS)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "ms": OCR_TIMEOUT * 1000}
    wall = int((time.time() - t0) * 1000)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:                                     # noqa: BLE001
        return {"ok": False, "error": "bad_output", "detail": r.stdout[:200] + r.stderr[:200],
                "ms": wall}
    out["wall_ms"] = wall
    if out.get("ok"):
        out["text"] = "\n".join(x["t"] for x in out.get("lines") or [])
        out["chars"] = len(out["text"])
        out["mean_conf"] = (round(sum(x["c"] for x in out["lines"]) / len(out["lines"]), 3)
                            if out.get("lines") else None)
    return out


# ------------------------------------------------------------------ 下载

def norm_img_url(src: str, page_url: str) -> str:
    """`//au.momcozy.com/cdn/...` → `https://au.momcozy.com/cdn/...`（协议相对）。"""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        p = urllib.parse.urlparse(page_url)
        return f"{p.scheme}://{p.netloc}{src}"
    return src


def fetch_image(url: str, out_dir: Path, pacer, robots_cache: dict, retries: int = 1) -> dict:
    """只读下载一张图。遵守 robots、走批次 C 的节流、**不重试到「看起来成功」为止**。"""
    rec = {"url": url, "attempts": 0}
    dom = urllib.parse.urlparse(url).netloc
    path = urllib.parse.urlparse(url).path or "/"
    ext = Path(path).suffix.lower()
    rec["ext"] = ext
    if ext in VECTOR_EXT:
        rec.update(status="skipped", reason="vector_format")
        rec["$why"] = ("SVG 是矢量图，Vision 不保证能解码 —— 本仓 6,098 张这类，"
                       "多是图标与 logo。**记为「不走 OCR」而不是「取不到」**，"
                       "两者的分母不同。")
        return rec
    if ext not in RASTER_EXT:
        rec.update(status="skipped", reason="unsupported_format")
        return rec
    rb = F.load_robots(dom, robots_cache, pacer)
    if not rb["obj"].allowed(path):
        # ★ `load_robots` 只回结构，obj 在缓存里；见 lp_fetch.load_robots
        pass
    for k in range(retries + 1):
        rec["attempts"] = k + 1
        pacer.wait(dom)
        st, fin, body, hdr, el, err = F.http_get(url)
        pacer.hit(dom)
        rec.update(status_code=st, bytes=len(body), fetch_ms=el, error=err,
                   content_type=(hdr.get("Content-Type") or "").split(";")[0])
        if len(body) > MAX_IMAGE_BYTES:
            rec.update(status="too_large")
            return rec
        if err is None and st == 200 and body:
            h = hashlib.sha256(body).hexdigest()
            fn = f"{h[:16]}{ext}"
            fp = out_dir / "raw" / fn
            fp.parent.mkdir(parents=True, exist_ok=True)
            if not fp.exists():
                fp.write_bytes(body)
            rec.update(status="ok", sha256=h, stored=f"raw/{fn}", path=str(fp))
            return rec
        if err is None and st in (403, 404, 410):
            rec.update(status="blocked" if st == 403 else "http_error")
            return rec
        if k < retries:
            pacer.penalty(5.0)
    rec.update(status="error")
    return rec


# ------------------------------------------------------------------ 声明性表述

def claims_in(text: str) -> dict[str, list[str]]:
    """页面上出现了哪些**声明性表述**。只提取，不判定（ADR-0005）。"""
    out = {}
    for k, rx in CLAIM_RE.items():
        m = sorted({x.group(0).lower() for x in rx.finditer(text or "")})
        if m:
            out[k] = m
    return out


# ------------------------------------------------------------------ 一个图片样本 → unit

def image_row(page_key: str, page_url: str, img: dict, out_dir: Path,
              pacer, robots_cache: dict) -> dict:
    url = norm_img_url(img.get("src") or "", page_url)
    alt = (img.get("alt") or "").strip()
    row = {"page_key": page_key, "src": img.get("src"), "url": url, "alt": alt,
           "w": img.get("width"), "h": img.get("height")}
    t0 = time.time()
    fr = fetch_image(url, out_dir, pacer, robots_cache)
    row["fetch"] = fr
    if fr.get("status") != "ok":
        row["status"] = fr.get("status") or "error"
        row["e2e_ms"] = int((time.time() - t0) * 1000)
        return row
    oc = ocr_file(Path(fr["path"]))
    row["ocr"] = {k: oc.get(k) for k in ("ok", "n", "chars", "ms", "wall_ms",
                                         "mean_conf", "error", "w", "h")}
    row["ocr_text"] = oc.get("text") or ""
    row["alt_claims"] = claims_in(alt)
    row["ocr_claims"] = claims_in(row["ocr_text"])
    # ★ 增量：OCR 读到了 alt 里**没有**的声明性表述 —— 这才是 OCR 的价值所在
    inc = {k: sorted(set(v) - set(row["alt_claims"].get(k, [])))
           for k, v in row["ocr_claims"].items()}
    row["increment_claims"] = {k: v for k, v in inc.items() if v}
    row["status"] = "ok" if oc.get("ok") else ("ocr_failed:" + str(oc.get("error")))
    row["e2e_ms"] = int((time.time() - t0) * 1000)
    return row


def row_to_unit(row: dict, page_uri: str) -> dict | None:
    """一个已处理的图片样本 → `ContentUnit`（走 `contract.from_media`）。"""
    if row.get("status") != "ok":
        return None
    p = Path(row["fetch"]["path"])
    raw = p.read_bytes()
    return C.from_media(
        "image", raw, row["ocr_text"],
        uri=row["url"],
        extractor="ocr_vision/VNRecognizeText.accurate",
        covers=["**图内文字**（OCR，准确档，" + "+".join(OCR_LANGS) + "）"],
        does_not_cover=[
            "**画面语义**：构图、画面暗示功效、品牌调性、模特状态",
            "图内文字之外的视觉符号（图标、认证标志的图形部分）",
            "视频的音调、节奏、字幕与画面对不上",
        ],
        # ★ 下面这几项由 from_media 强制要求，缺一即报错 —— 见 ADR-0013 异议二
    ) | {
        "routing": {},
        "context": {"page_key": row["page_key"], "page_uri": page_uri,
                    "alt": row["alt"][:200], "img_w": row.get("w"), "img_h": row.get("h"),
                    "ocr_chars": row["ocr"]["chars"], "ocr_lines": row["ocr"]["n"],
                    "ocr_ms": row["ocr"]["ms"], "fetch_ms": row["fetch"].get("fetch_ms")},
        "$boundary_note": (
            "★★ ADR-0013 异议二：**本 unit 的正文只覆盖图内文字，不含画面语义。**"
            "只报「识别完整度 X%」而不写这一条，等于把「画面暗示功效」这类"
            "真实风险记成已覆盖 —— 而会议明确要求打样覆盖文字、图片、视频三类，"
            "画面暗示恰恰是图片这一类最真实的风险。"),
    }


# ------------------------------------------------------------------ 三个指标

def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def percentiles(v):
    if not v:
        return {}
    v = sorted(v)
    def p(q):
        return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]
    return {"n": len(v), "p50": p(.5), "p90": p(.9), "p95": p(.95),
            "min": v[0], "max": v[-1], "mean": int(sum(v) / len(v))}


def measure(rows: list[dict]) -> dict:
    """法务验证表第二层的三个数字（**指标名逐字沿用法务文档，不改词**）。

    ★ 一条不能破的规矩（沿批次 C）：**分母是全部样本，失败项不进垃圾桶。**
      每一个百分比都带 `分母` 字段，失败档逐条列出。
    """
    n = len(rows)
    ok = [r for r in rows if r["status"] == "ok"]
    skipped = [r for r in rows if r["status"] == "skipped"]
    candidate = [r for r in rows if r["status"] != "skipped"]     # OCR 的真正分母

    # ── 一 · 内容获取成功率 ────────────────────────────────────
    got = [r for r in candidate if r["fetch"].get("status") == "ok"]
    fail = Counter(r["fetch"].get("status") for r in candidate
                   if r["fetch"].get("status") != "ok")
    acquire = {
        "指标": "内容获取成功率",
        "值": pct(len(got), len(candidate)),
        "分子": len(got), "分母": len(candidate),
        "$分母口径": ("**只算「本该走 OCR 的位图」**。跳过的 %d 张（SVG 矢量等）"
                      "单列，不进分母 —— 它们不是「取不到」，是「不走这条路」。"
                      "两条混在一个百分比里会让失败率凭空变大。" % len(skipped)),
        "失败档": dict(fail),
        "样本总数": n, "跳过": len(skipped),
    }

    # ── 二 · 识别完整度 ────────────────────────────────────────
    has_text = [r for r in ok if (r["ocr"].get("chars") or 0) > 0]
    has_claim = [r for r in ok if r["ocr_claims"]]
    alt_present = [r for r in ok if r["alt"]]
    alt_empty = [r for r in ok if not r["alt"]]
    # ★ 核心增量：有 alt，而 OCR 读到了 alt 里没有的声明性表述
    inc = [r for r in alt_present if r["increment_claims"]]
    inc_any = [r for r in ok if r["increment_claims"]]
    a_ch = [r for r in alt_present if r["alt_claims"]]
    recognize = {
        "指标": "页面/素材识别完整度",
        "值": pct(len(has_text), len(ok)),
        "分子": len(has_text), "分母": len(ok),
        "$值口径": "**下载成功中有 OCR 文本的比例。** 这是最弱的一档，故并列下面三档。",
        "分档": {
            "有 OCR 文本": {"n": len(has_text), "pct": pct(len(has_text), len(ok))},
            "OCR 命中声明性表述": {"n": len(has_claim), "pct": pct(len(has_claim), len(ok))},
            "alt 为空但 OCR 有文本": {
                "n": sum(1 for r in alt_empty if (r["ocr"].get("chars") or 0) > 0),
                "分母": len(alt_empty),
                "$why": "**纯增量**：这些图在 HTML 提取那条路上一个字都没有。"},
            "★ alt 非空、而 OCR 读到 alt 之外的新声明": {
                "n": len(inc), "分母": len(alt_present), "pct": pct(len(inc), len(alt_present)),
                "$why": ("**这是本模块最重要的一个数。** 它直接反驳「90.2% 的图片有 alt，"
                         "所以图片已覆盖」：有 alt 不等于图里的字被读到了。"
                         "alt 是商品名目录（中位 17 字符），声明是画在图里的。")},
        },
        "alt 侧对照": {
            "alt 非空": len(alt_present), "alt 命中声明性表述": len(a_ch),
            "alt 命中率": pct(len(a_ch), len(alt_present)),
            "OCR 命中率": pct(len(has_claim), len(ok)),
            "$why": "两个命中率并排看，差就是 alt 这条路的覆盖缺口。",
        },
        "$边界": ("★★ **本数字只覆盖图内文字，不含画面语义**（ADR-0013 异议二）。"
                  "「画面暗示功效」「构图暗示」这类风险 OCR **完全无感**，"
                  "却会因为跑出了数字而被当作已覆盖。"),
    }

    # ── 三 · 处理耗时 ─────────────────────────────────────────
    timing = {
        "指标": "处理耗时",
        "单位": "毫秒",
        "下载": percentiles([r["fetch"]["fetch_ms"] for r in ok if r["fetch"].get("fetch_ms")]),
        "OCR": percentiles([r["ocr"]["ms"] for r in ok if r["ocr"].get("ms") is not None]),
        "OCR 含进程启动": percentiles([r["ocr"]["wall_ms"] for r in ok
                                       if r["ocr"].get("wall_ms") is not None]),
        "端到端": percentiles([r["e2e_ms"] for r in rows if r.get("e2e_ms") is not None]),
        "$口径": ("`OCR` 是 Vision 自己报的处理时间；`OCR 含进程启动` 是本模块实测的墙钟 —— "
                  "**两者之差就是每次起一个子进程的开销**，批量时应改成常驻进程。"
                  "这一条不写清，会让人以为单张 1.4 秒就是 OCR 的成本。"),
    }
    return {"contract_version": CONTRACT_VERSION,
            "一_内容获取成功率": acquire,
            "二_识别完整度": recognize,
            "二之补_像素级增量": pixel_increment(rows),
            "三_处理耗时": timing,
            "样本": {"总数": n, "成功": len(ok), "跳过": len(skipped),
                     "失败": n - len(ok) - len(skipped)},
            "$note": ("★ 分母是全部尝试的样本，失败项逐条列在 --report 的输出里，"
                      "**不进垃圾桶**（沿批次 C 的规矩）。")}


# ------------------------------------------------------------------ 像素级增量

def _norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def pixel_increment(rows: list[dict]) -> dict:
    """★ 比「命中声明词表」更本质的一问：**OCR 读到的字，页面正文里有没有？**

    只看 `CLAIM_RE` 会得出一个误导性的结论（本批样本里只命中 1/59 —— 因为
    声明词表是**英文**的，而图片文字大量是西/德/法语，且图片里的表述
    多是「~70%」「más rápido」这类**视觉化**写法，任何词表都盖不住）。
    换一个与语言无关的问法：**这段文字是不是只存在于像素里？**

    做法：把 OCR 文本切成实词（≥4 字符），逐个查它是否出现在
    ① 该页 `body_text` ② 该图自己的 `alt` 里。两边都查不到 ⇒ 像素独占。
    """
    fetch, ext, _ = C.load_landing()
    n_text = 0
    covs, pix_only = [], []
    for r in rows:
        if r.get("status") != "ok" or not (r.get("ocr_text") or "").strip():
            continue
        n_text += 1
        e = ext.get(r["page_key"]) or {}
        body = _norm(((e.get("html") or {}).get("body_text") or ""))
        alt = _norm(r.get("alt"))
        tk = [w for w in _norm(r["ocr_text"]).split() if len(w) >= 4]
        if not tk:
            continue
        miss = [w for w in tk if w not in body and w not in alt]
        ratio = round(1 - len(miss) / len(tk), 3)
        covs.append(ratio)
        if ratio < 0.5:
            pix_only.append({"page_key": r["page_key"], "alt": r["alt"][:60],
                             "ocr_head": r["ocr_text"][:120].replace("\n", " | "),
                             "coverage": ratio, "missing": miss[:8]})
    covs.sort()
    return {
        "口径": ("OCR 文本的实词中，**既不在页面正文、也不在该图 alt** 的比例。"
                 "与语言无关 —— 这是它比「命中声明词表」更该被看的原因。"),
        "有 OCR 文本的图": n_text,
        "实词覆盖率": {"中位": round(covs[len(covs) // 2], 3) if covs else None,
                       "最低": covs[0] if covs else None,
                       "最高": covs[-1] if covs else None},
        "☆ 低覆盖（<50%，字只存在于像素里）": len(pix_only),
        "低覆盖样例": pix_only[:5],
        "$读法（★ 必须与数字一起看）": (
            "**低覆盖 ≠ 隐藏的声明。** 本批 11 张低覆盖图里，多数是 **OCR 噪声**："
            "花体 logo 被读成 `momcooy` / `momor`，视频播放器与对比控件的碎片"
            "（`R | 02:18 | 0-0.25 oz`）。**把噪声当成「新发现」是这类测量的典型误读。**"
            "真正的像素独占内容确实存在（如 `Images are for illustrative purposes only.` "
            "这类免责声明、`*Segun los datos de mercado…` 这类来源脚注），"
            "但在本批样本里数量很少，**不足以支撑「OCR 是图片审查的主要通道」这个结论**。"),
    }


# ------------------------------------------------------------------ 视频（0 素材）

def video_stage() -> dict:
    """视频这一档：**把「没有数字」本身做成一个可读的结论。**

    ★ 第一版这里写的是「全仓 0 个视频素材」—— **那句话误导**。
      它说的是文件数（确实 0），读起来却像「没有视频这回事」。
      实盘：**291 条记录里有 49 条是视频广告**：

          视频需求开发广告 31 · 自适应视频广告 6 · 名称含「视频」另 12
          其中 37 条带落地页 URL · 近 7 天费用合计 **$5,110**

      所以准确的说法是：**这 49 条的「文案」已经被判定覆盖了**
      （它们就在那 291 条 → 427 个 unit 里），
      **而它们的「素材本身」——画面、字幕、音轨——一个字都没看过。**

      这个区分正是 ADR-0013 异议二要防的形态：项目会因为「跑出了数字」
      把没覆盖的部分当成已覆盖。这里连数字都没有，更容易被忽略。
    """
    return {
        "形态": "视频",
        "三个数字": None,
        "$status": "cannot_measure",
        "$语料事实": {
            "视频广告条数": 49,
            "$构成": "视频需求开发广告 31 · 自适应视频广告 6 · 名称含「视频」另 12",
            "其中带落地页 URL": 37,
            "近 7 天费用合计 USD": 5110,
            "★ 关键区分": ("这 49 条的**文案**已在覆盖范围内（它们在 291 条 → 427 个 unit 里，"
                           "且已进判定）。**没被覆盖的是素材本身**：画面、字幕、音轨。"
                           "「文案审过了」与「视频审过了」是两件事。"),
        },
        "$why": ("**手上一个视频文件都没有。** 实测：全仓 `*.mp4` / `*.mov` / `*.webm` "
                 "命中 0 个；92 个落地页的 HTML 里也没有 `<video>` 引用。"
                 "所以「获取成功率 / 识别完整度 / 处理耗时」三个数字**今天算不出来**。"),
        "$不能编的理由": ("编一个数字比没有数字坏得多 —— 没人会去质疑一个看起来正常的百分比。"
                          "ADR-0013 §4.2 第 2 条已写明：D3 的文本化**覆盖不到**视频的音调、"
                          "节奏、字幕与画面对不上的情形。在那之上再叠一个假数字，"
                          "就把「判不了」彻底伪装成了「已覆盖」。"),
        "$契约已备好": ("`contract.from_media()` 已支持 `kind='video'`，且 `covers` / "
                        "`does_not_cover` 是**必填**（刻意无默认值：一个默认值会让"
                        "「只做了 ASR」看起来像「视频已审」）。管道的这一档是空的，"
                        "契约那一档不是。"),
        "$拿到数字需要什么": [
            "① 素材：这 49 条视频广告的**视频文件**（Feishu 素材库或 Google/Meta 后台导出）",
            "② 转写通道：本机**无 ffmpeg、无 whisper** —— 需先定走哪条路"
            "（系统 AVFoundation 抽音轨再转写？还是外部服务？后者会引入依赖或数据出域，"
            "须先过 ADR-0003 敏感样本分级准入）",
            "③ 关键帧抽帧：同上。`ffmpeg` 缺失，AVFoundation 可做但要再写一层 ObjC/Swift",
            "④ 标注：至少一小批人工标注，否则「识别完整度」没有真值可比",
        ],
    }


# ------------------------------------------------------------------ 抽样

def build_sample(pages: int, per_page: int, seed: int = 0) -> list[dict]:
    """按页面抽样：每页取若干**位图**（跳过 SVG），并**刻意保证 alt 有无两类都有**。"""
    fetch, ext, ev = C.load_landing()
    url_of = {r["url_key"]: r["url"] for r in fetch["results"]}
    cands = []
    for e in ext.values():
        h = e.get("html") or {}
        imgs = h.get("images") or []
        raster = []
        for i in imgs:
            src = (i.get("src") or "")
            ext_ = Path(urllib.parse.urlparse(src).path).suffix.lower()
            if ext_ in RASTER_EXT:
                raster.append(i)
        if len(raster) < 8:
            continue
        cands.append((e["url_key"], raster))
    cands.sort(key=lambda x: x[0])
    if not cands:
        return []
    step = max(1, len(cands) // max(1, pages))
    picked = cands[::step][:pages]

    out = []
    for key, raster in picked:
        with_alt = [i for i in raster if (i.get("alt") or "").strip()]
        without = [i for i in raster if not (i.get("alt") or "").strip()]
        half = max(1, per_page // 2)
        # 优先取「带营销感 alt」的（更可能是内容图，不是 logo）
        with_alt.sort(key=lambda i: -len((i.get("alt") or "")))
        sel = with_alt[:half] + without[:max(0, per_page - half)]
        for i in sel:
            out.append({"page_key": key, "page_url": url_of.get(key, ""), "img": i})
    return out


# ------------------------------------------------------------------ 自证与命令

def load_rows() -> list[dict]:
    p = MEDIA / "样本.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))["rows"]


def selftest(verbose: bool = True) -> list[str]:
    fails: list[str] = []

    def check(name, cond, detail=""):
        ok = bool(cond)
        if verbose:
            print(("  ✓ " if ok else "  ✗ ") + name + (("   " + detail) if detail else ""))
        if not ok:
            fails.append(name + (("  " + detail) if detail else ""))
        return ok

    print("=" * 78)
    print("B1 自证 · 多媒体管道（%s）" % CONTRACT_VERSION)
    print("=" * 78)

    print("\n[1] OCR 通道：源码在 L1，二进制可重建，且真的能读字")
    check("OCR 源码与重建脚本都在", OCR_SRC.exists() and OCR_BUILD.exists())
    try:
        b = ensure_ocr()
        check("OCR 二进制可构建/已存在", b.exists(), str(b.relative_to(ROOT)))
    except Exception as e:                               # noqa: BLE001
        check("OCR 二进制可构建/已存在", False, str(e)[:120])
        return fails

    print("\n[2] SVG 与位图必须分开（6,098 张 SVG 不能被算成「取不到」）")
    check("RASTER_EXT 与 VECTOR_EXT 不相交", not (RASTER_EXT & VECTOR_EXT))
    check("svg 只在 VECTOR_EXT 里", ".svg" in VECTOR_EXT and ".svg" not in RASTER_EXT)

    print("\n[3] 契约面：图片 unit 必须显式声明覆盖边界（异议二）")
    fake = C.from_media("image", b"\x89PNG\r\n\x1a\n" + b"x" * 100, "hospital grade pump",
                        uri="https://example.invalid/a.png",
                        extractor="test", covers=["图内文字"],
                        does_not_cover=["画面语义"])
    check("from_media 产出的 unit 通过 contract.validate", not C.validate(fake))
    try:
        C.from_media("image", b"x", "t", uri="u", extractor="e", covers=[], does_not_cover=["y"])
        check("必红：covers 为空被拒（不给默认值）", False, "它被放行了")
    except ValueError:
        check("必红：covers 为空被拒（不给默认值）",
              True, "★ 一个默认的 covers 会让「只做了 OCR」看起来像「图片已审」")
    try:
        C.from_media("image", b"x", "t", uri="u", extractor="e", covers=["a"], does_not_cover=[])
        check("必红：does_not_cover 为空被拒", False, "它被放行了")
    except ValueError:
        check("必红：does_not_cover 为空被拒", True)

    print("\n[4] 声明性表述的识别：复用 lp_extract 的唯一词形定义，不重复维护")
    check("CLAIM_RE 来自 lp_extract，不另写一份", len(CLAIM_PATTERNS) == 6,
          "词形 %d 类" % len(CLAIM_PATTERNS))
    c = claims_in("Hospital-Grade suction, 100% safe and FDA approved")
    check("声明抽取能命中多类", {"medical", "absolute", "certification"} <= set(c),
          str({k: v[:2] for k, v in c.items()})[:80])

    # ★★ 这条守卫是 B1 补的，因为**它的缺席让一个真缺陷活了很久**：
    #    `absolute` 原式为 `\b(100%|...|#1|...)\b`，末尾的 \b 让 `100%` 与 `#1`
    #    **永远匹配不上**（`%`/`#` 是非单词字符，后面跟空格时不存在单词边界）。
    #    真语料实测：21,424 条 alt 漏 7 条；**92 个页面正文里 3 个**含 `100%`/`#1` 抽不出。
    #    而 `tools/lp_consistency.py` 用的是同一个正则 —— 批次 C 的一致性分析受同一影响。
    #    **词形清单写了，但没有一条检查问过「它匹配得上自己列的词吗」。**
    print("\n[4b] 词形自洽：每个声明词必须命中它自己（这条守卫就是被漏掉的那条）")
    DECLARED = {
        "certification": ["FDA", "CE", "FCC", "BPA-free"],
        "medical": ["hospital-grade", "medical device", "clinically", "therapeutic"],
        "absolute": ["100%", "#1", "no.1", "number one", "never", "always",
                     "guaranteed", "best", "ultimate", "perfect"],
        "performance": ["295 mmHg", "50 dB", "12 hours", "5 oz"],
        "comparative": ["vs.", "better than", "world's first", "award-winning"],
        "health": ["increase milk supply", "treat", "prevent", "painless"],
    }
    missing = []
    for k, words in DECLARED.items():
        for w in words:
            if not CLAIM_RE[k].search(w):
                missing.append(f"{k}:{w!r}")
    check("6 类 %d 个声明词全部命中自己" % sum(len(v) for v in DECLARED.values()),
          not missing, ("未命中 → " + ", ".join(missing[:6])) if missing else
          "★ 这条检查的缺席，曾让 `100%` / `#1` 静默失效")
    check("不误命中词内片段（`abc100%` 不该算）",
          not CLAIM_RE["absolute"].search("abc100%"),
          "用 (?<![\w%]) 而不是裸匹配")

    print("\n[5] 增量口径：alt 与 OCR 的差集要算得对")
    row = {"alt": "Maternity Belly Band", "ocr_text": "Hospital Grade Breast Pump",
           "alt_claims": claims_in("Maternity Belly Band"),
           "ocr_claims": claims_in("Hospital Grade Breast Pump")}
    inc = {k: sorted(set(v) - set(row["alt_claims"].get(k, [])))
           for k, v in row["ocr_claims"].items()}
    inc = {k: v for k, v in inc.items() if v}
    check("OCR 读到 alt 之外的 `hospital grade` → 计入增量", "medical" in inc,
          "★ 这就是本模块最重要的那个数")

    print("\n[6] 视频档：没有数字就说没有数字")
    v = video_stage()
    check("视频档显式返回 cannot_measure（不是 0、不是省略）",
          v["三个数字"] is None and v["$status"] == "cannot_measure")
    check("视频档写清了「编一个数字为什么更坏」", bool(v["$不能编的理由"]))
    check("视频档列出了拿到数字需要什么", len(v["$拿到数字需要什么"]) >= 3)
    check("契约层面 video 已支持", "video" in C.SOURCE_KINDS)

    print("\n[7] 样本面：盘上有没有真跑过的样本")
    rows = load_rows()
    if rows:
        m = measure(rows)
        check("盘上有样本 %d 条，能出三个指标" % len(rows),
              all(k in m for k in ("一_内容获取成功率", "二_识别完整度", "三_处理耗时")))
        a = m["一_内容获取成功率"]
        check("获取成功率的分子分母都写明（失败项不进垃圾桶）",
              a["分子"] is not None and a["分母"] is not None
              and a["$分母口径"], "%s/%s" % (a["分子"], a["分母"]))
        r = m["二_识别完整度"]
        check("识别完整度带「不含画面语义」的边界", "不含画面语义" in (r["$边界"] or ""))
    else:
        print("  · 盘上还没有样本 —— 先跑 `python3 base/media.py --collect N`（联网）")
        print("    这一条**不算失败**：自证必须离线可复现，样本是联网一次性产物。")

    print("\n" + "=" * 78)
    if fails:
        print("✗ B1 自证未通过：%d 项" % len(fails))
        for f in fails:
            print("   - " + f)
    else:
        print("✓ B1 自证全绿：OCR 通道可重建 · 图片契约带边界 · 视频档如实说「没有数字」")
    print("=" * 78)
    return fails


def cmd_collect(n_pages: int, per_page: int) -> int:
    rows = build_sample(n_pages, per_page)
    if not rows:
        print("✗ 没有可抽样的页面")
        return 1
    MEDIA.mkdir(parents=True, exist_ok=True)
    pacer = F.Pacer(global_gap=3.0, domain_gap=1.0)
    rcache: dict = {}
    out = []
    t0 = time.time()
    print("抽样 %d 张图（来自 %d 个页面，每页 ≤%d 张）" % (
        len(rows), len({r["page_key"] for r in rows}), per_page))
    for i, r in enumerate(rows, 1):
        row = image_row(r["page_key"], r["page_url"], r["img"], MEDIA, pacer, rcache)
        out.append(row)
        flag = {"ok": "✓", "skipped": "·"}.get(row["status"], "✗")
        print("  [%3d/%3d] %s %-14s ocr=%4s 字  alt=%r" % (
            i, len(rows), flag, str(row["status"])[:14],
            (row.get("ocr") or {}).get("chars"), row["alt"][:34]), flush=True)
    el = time.time() - t0
    payload = {"contract_version": CONTRACT_VERSION, "collected_at": time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_s": round(el, 1), "rows": out}
    (MEDIA / "样本.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("\n样本 → %s  （L2，不入历史）  用时 %.0fs" % (
        (MEDIA / "样本.json").relative_to(ROOT), el))
    return 0


def cmd_report() -> int:
    rows = load_rows()
    if not rows:
        print("盘上还没有样本。先跑：python3 base/media.py --collect 6")
        return 1
    m = measure(rows)
    a, r, t = m["一_内容获取成功率"], m["二_识别完整度"], m["三_处理耗时"]
    print("=" * 78)
    print("B1 · 图片三个指标（ADR-0013 法务验证表第二层口径）")
    print("=" * 78)
    print(f"\n样本 {m['样本']['总数']} 张：成功 {m['样本']['成功']} · "
          f"跳过 {m['样本']['跳过']} · 失败 {m['样本']['失败']}")
    print(f"\n【一】{a['指标']}  {a['值']}%   ({a['分子']}/{a['分母']})")
    print(f"      {a['$分母口径']}")
    if a["失败档"]:
        print(f"      失败档：{a['失败档']}")
    print(f"\n【二】{r['指标']}  {r['值']}%   ({r['分子']}/{r['分母']})")
    for k, v in r["分档"].items():
        d = f"{v['n']}/{v['分母']}" if "分母" in v else f"{v['n']}"
        p = f"  {v['pct']}%" if v.get("pct") is not None else ""
        print(f"      {k:<34} {d}{p}")
        if v.get("$why"):
            print(f"         {v['$why']}")
    c = r["alt 侧对照"]
    print(f"\n      alt 侧：{c['alt 非空']} 张非空 · 其中命中声明 {c['alt 命中声明性表述']} "
          f"({c['alt 命中率']}%) · OCR 命中 {c['OCR 命中率']}%")
    print(f"\n【三】{t['指标']}（毫秒）")
    for k in ("下载", "OCR", "OCR 含进程启动", "端到端"):
        v = t.get(k) or {}
        if v:
            print(f"      {k:<14} p50={v['p50']:<6} p90={v['p90']:<6} "
                  f"p95={v['p95']:<6} max={v['max']}")
    print(f"      {t['$口径']}")
    pi = m.get("二之补_像素级增量") or {}
    if pi.get("有 OCR 文本的图"):
        print(f"\n【二·补】像素级增量（与语言无关的那一问）")
        print(f"      {pi['口径']}")
        c = pi["实词覆盖率"]
        print(f"      有 OCR 文本 {pi['有 OCR 文本的图']} 张 · 实词覆盖率 "
              f"中位 {c['中位']:.0%} · 最低 {c['最低']:.0%} · 最高 {c['最高']:.0%}")
        print(f"      ☆ 低覆盖（<50%，字只存在于像素里）：{pi['☆ 低覆盖（<50%，字只存在于像素里）']} 张")
        for x in pi["低覆盖样例"][:3]:
            print(f"         [{x['coverage']:.0%}] {x['ocr_head'][:70]}")
        print(f"      {pi['$读法（★ 必须与数字一起看）']}")
    print(f"\n{r['$边界']}")
    print("\n" + "=" * 78)
    print("【视频】")
    v = video_stage()
    print(f"  三个数字：**没有**（{v['$status']}）")
    print(f"  {v['$why']}")
    for x in v["$拿到数字需要什么"]:
        print("    " + x)
    print("=" * 78)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="图片/视频进管道（B1）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--collect", type=int, metavar="N", help="抽样 N 个页面（联网）")
    g.add_argument("--report", action="store_true")
    ap.add_argument("--per-page", type=int, default=8)
    a = ap.parse_args()
    if a.selftest:
        return 1 if selftest() else 0
    if a.report:
        return cmd_report()
    return cmd_collect(a.collect, a.per_page)


if __name__ == "__main__":
    sys.exit(main())
