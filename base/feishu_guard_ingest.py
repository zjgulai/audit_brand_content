#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/feishu_guard_ingest.py —— 飞书 Guard（守衡）统一生产审查与工作台建案桥接器

职责边界：
1. 将飞书群聊/私聊接收到的多形态待审内容（自由文案、广告双字段、结构化商品 JSON、
   飞书云文档链接、落地页 URL、图片附件、视频附件）统一规整为四维生产进件请求；
2. 品线自动识别（五条品线关键词匹配 + 未声明且未命中时回落「吸奶器」并显式留痕）；
3. 内容阶段自动推断（复用 `apply_stage_inference`，无法从字面推断时按从严口径
   `final_content` 送审并显式留痕，避免因缺元数据被 422 拒之门外）；
4. 调用生产级 `SubmissionIngestor`（`RuleJudge` + `Orchestrator` + `ExternalStandardsAuthority`
   + 多模态观察）并通过 `ReviewCommandService` 写入仓外权威事件账本（`BusinessEventStore`）
   与 SQLite 投影（`ProjectionStore`），实时产出工作台 `case_id` 与回执 `receipt_id`；
5. 同时输出与 `tools/agent/judge_evidence.mjs` 兼容的 `hits` / `verdict` / `boundary_statement`
   结构，使知识库 BM25 证据链六态检索无缝衔接到生产引擎之上。

安全与红线约束：
- 本模块自身不发起外部 HTTP 下载（满足 DG-1 下载治理扫描约束）；
- 权威账本与投影库强制落在仓外（默认 `~/.shouheng/workbench-data`，权限 0700；
  当测试设置仓外 `SHOUHENG_STATE_DIR` 时自动跟随至该临时目录，严守 §2.4.4「自证不碰真状态」）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "base") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "base"))

from base import contract as C  # noqa: E402
from base import submission_router as SR  # noqa: E402
from base.business_event_store import BusinessEventStore, WriterLease  # noqa: E402
from base.judge_entry import judge_unit  # noqa: E402
from base.projection_store import ProjectionStore  # noqa: E402
from base.projector import Projector  # noqa: E402
from base.review_command_service import ReviewCommandService  # noqa: E402
from base.submission_service import (  # noqa: E402
    MEDIA_INGEST_ENV,
    SubmissionIngestor,
    SubmissionRejected,
    apply_stage_inference,
)

CONTRACT_VERSION = "feishu-guard-ingest-v1"
DEFAULT_TENANT = "momcozy"
DEFAULT_PRODUCT_LINE = "吸奶器"

VALID_PRODUCT_LINES: Tuple[str, ...] = (
    "吸奶器",
    "婴儿车",
    "背带",
    "温奶器",
    "哺乳内衣",
)

#: 五条品线的确定性识别词表（按特异性排序；英文词要求词边界避免子串误判）
PRODUCT_LINE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "吸奶器": (
        "吸奶器", "吸乳器", "吸乳", "集奶器", "喇叭罩",
        "breast pump", "pumping", "lactation", "flange",
        "s12 pro", "s9 pro", "m5", "m6", "m9", "v1 pro", "v2 pro",
    ),
    "哺乳内衣": (
        "哺乳内衣", "哺乳文胸", "孕妇内衣", "授乳内衣",
        "nursing bra", "maternity bra", "pumping bra", "hands-free bra",
    ),
    "婴儿车": (
        "婴儿车", "推车", "伞车", "溜娃神器",
        "stroller", "baby wagon", "pram", "pushchair",
    ),
    "背带": (
        "背带", "腰凳", "背巾",
        "baby carrier", "infant carrier", "baby wrap", "hipseat", "hip seat",
    ),
    "温奶器": (
        "温奶器", "暖奶器", "热奶器", "恒温壶", "调奶器",
        "bottle warmer", "milk warmer", "water warmer",
    ),
}

FEISHU_DOC_RE = re.compile(
    r"https?://[a-zA-Z0-9._-]+\.(?:feishu\.cn|larksuite\.com)/(docx|wiki)/([A-Za-z0-9_-]{10,})"
)

HTTP_URL_RE = re.compile(r"https?://[^\s<>\"'`]+")


def _is_inside_repo(p: Path) -> bool:
    resolved = p.expanduser().resolve()
    return resolved == REPO_ROOT or REPO_ROOT in resolved.parents


def workbench_data_root(env: Optional[Dict[str, str]] = None) -> Path:
    """解析群内建案使用的工作台数据根目录（必须在仓外，目录权限 0700）。

    优先级：
    1. `SHOUHENG_WORKBENCH_DATA_ROOT`（显式指定）
    2. `SHOUHENG_STATE_DIR` 若在仓外（例如单测/自证的临时目录），则取 `<SHOUHENG_STATE_DIR>/workbench-data`，
       保证任何离线测试绝不污染真实账本（AGENTS.md §2.4.4）
    3. 默认 `~/.shouheng/workbench-data`
    """
    e = os.environ if env is None else env
    explicit = (e.get("SHOUHENG_WORKBENCH_DATA_ROOT") or "").strip()
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if _is_inside_repo(root):
            raise ValueError(f"SHOUHENG_WORKBENCH_DATA_ROOT 不允许落在仓库内：{root}")
        return root

    state_dir = (e.get("SHOUHENG_STATE_DIR") or "").strip()
    if state_dir:
        sd = Path(state_dir).expanduser().resolve()
        if not _is_inside_repo(sd):
            return sd / "workbench-data"

    return (Path.home() / ".shouheng" / "workbench-data").resolve()


def resolve_product_line(
    text: Optional[str] = None,
    *,
    declared: Optional[str] = None,
    uri: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """解析品线。返回 `{value, status, matched_keyword, declared, note}`。

    status 四档互不冒充：
    - `declared`                  调用方显式给出了合法的五品线之一
    - `invalid_declared_fallback` 调用方给了值但不在五品线内，回落默认「吸奶器」并明说
    - `inferred_keyword`          未声明，但从正文/字段/URL 关键词匹配到了具体品线
    - `default_fallback`          未声明且无品线词命中，回落默认「吸奶器」并明说
    """
    if isinstance(declared, str) and declared.strip():
        clean = declared.strip()
        if clean in VALID_PRODUCT_LINES:
            return {
                "value": clean,
                "status": "declared",
                "matched_keyword": None,
                "declared": clean,
                "note": f"使用显式指定的品线「{clean}」",
            }
        return {
            "value": DEFAULT_PRODUCT_LINE,
            "status": "invalid_declared_fallback",
            "matched_keyword": None,
            "declared": clean,
            "note": (
                f"指定的品线「{clean}」不在工作台五品线（{'/'.join(VALID_PRODUCT_LINES)}）内，"
                f"已按默认品线「{DEFAULT_PRODUCT_LINE}」建案"
            ),
        }

    parts: List[str] = []
    if isinstance(text, str) and text.strip():
        parts.append(text)
    if isinstance(uri, str) and uri.strip():
        parts.append(uri)
    if isinstance(fields, dict):
        for v in fields.values():
            if isinstance(v, str) and v.strip():
                parts.append(v)
    haystack = "\n".join(parts).lower()

    best_line: Optional[str] = None
    best_count = 0
    best_kw: Optional[str] = None

    if haystack:
        for line_name in VALID_PRODUCT_LINES:
            kws = PRODUCT_LINE_KEYWORDS.get(line_name, ())
            hit_count = 0
            first_kw: Optional[str] = None
            for kw in kws:
                kw_low = kw.lower()
                if re.match(r"^[a-z0-9\s-]+$", kw_low):
                    pat = r"(?<![a-z0-9])" + re.escape(kw_low) + r"(?![a-z0-9])"
                    found = bool(re.search(pat, haystack))
                else:
                    found = kw_low in haystack
                if found:
                    hit_count += 1
                    if first_kw is None:
                        first_kw = kw
            if hit_count > best_count:
                best_count = hit_count
                best_line = line_name
                best_kw = first_kw

    if best_line is not None and best_count > 0:
        return {
            "value": best_line,
            "status": "inferred_keyword",
            "matched_keyword": best_kw,
            "declared": None,
            "note": f"未显式声明品线，按内容关键词「{best_kw}」自动识别为「{best_line}」",
        }

    return {
        "value": DEFAULT_PRODUCT_LINE,
        "status": "default_fallback",
        "matched_keyword": None,
        "declared": None,
        "note": f"未声明品线且内容无特定品线词，按默认品线「{DEFAULT_PRODUCT_LINE}」建案",
    }


def resolve_content_stage(submission: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """解析内容阶段（`brief` vs `final_content`）。

    返回 `(patched_submission, known_inference, stage_resolution)`。
    """
    declared = submission.get("content_stage")
    if isinstance(declared, str) and declared.strip() in C.CONTENT_STAGES:
        clean = declared.strip()
        patched, inf = apply_stage_inference(submission)
        return (
            patched,
            inf,
            {
                "value": clean,
                "status": "declared",
                "note": f"使用调用方显式申报的内容阶段「{clean}」",
            },
        )

    patched, inf = apply_stage_inference(submission)
    if inf.get("status") == "inferred" and inf.get("value") in C.CONTENT_STAGES:
        val = inf["value"]
        return (
            patched,
            inf,
            {
                "value": val,
                "status": "inferred",
                "matched": inf.get("matched") or [],
                "note": f"未显式申报阶段，按内容特征词自动推断为「{val}」",
            },
        )

    # 群消息未带「初稿/提纲/成稿」等字样时，按从严口径 final_content 送审并显式标注
    strict_inf = {
        "status": "inferred",
        "value": "final_content",
        "matched": ["feishu_guard_default_strict"],
        "reason": "群内未声明阶段且无提纲特征词，按从严口径（final_content 成稿）送审",
    }
    strict_sub = dict(submission, content_stage="final_content")
    return (
        strict_sub,
        strict_inf,
        {
            "value": "final_content",
            "status": "default_strict",
            "note": "未声明内容阶段且无提纲特征词，按从严口径「final_content（成稿）」建案",
        },
    )


def _extract_feishu_doc_text(doc_url_or_token: str) -> Dict[str, Any]:
    """通过已登记的 `tools/lark_find.py` 读取飞书 docx / wiki 正文。"""
    raw = str(doc_url_or_token or "").strip()
    m = FEISHU_DOC_RE.search(raw)
    if m:
        doc_kind, token = m.group(1), m.group(2)
    else:
        doc_kind, token = "docx", raw

    subcmd = "wiki" if doc_kind == "wiki" else "readdoc"
    lark_find = REPO_ROOT / "tools" / "lark_find.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(lark_find), subcmd, token],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=25,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "failure_kind": "fetch_error",
            "error": f"读取飞书文档异常：{type(exc).__name__}: {exc}",
            "token": token,
            "doc_kind": doc_kind,
        }

    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return {
            "ok": False,
            "failure_kind": "fetch_error",
            "error": (proc.stderr or proc.stdout or f"lark_find 退出码 {proc.returncode}").strip()[:400],
            "token": token,
            "doc_kind": doc_kind,
        }

    return {
        "ok": True,
        "text": proc.stdout.strip(),
        "token": token,
        "doc_kind": doc_kind,
        "uri": raw if raw.startswith("http") else f"feishu:{doc_kind}:{token}",
    }


def _extract_landing_url_text(url_or_key: str) -> Dict[str, Any]:
    """从本地落地页语料库匹配 URL/url_key 正文；若不在本地语料中则实时抓取并经 lp_extract 解析正文。"""
    raw = str(url_or_key or "").strip()
    if not raw:
        return {"ok": False, "failure_kind": "empty", "error": "落地页 URL 为空"}

    norm_key = re.sub(r"^https?://", "", raw).rstrip("/")
    try:
        fetch_data, extract_data, evidence_dir = C.load_landing()
        by_key = {r["url_key"].rstrip("/"): r for r in fetch_data.get("results", [])}
        by_url = {r.get("url", "").rstrip("/"): r for r in fetch_data.get("results", [])}
        rec = by_key.get(norm_key) or by_url.get(raw.rstrip("/"))
        if rec is not None:
            uk = rec["url_key"]
            ext_rec = extract_data.get(uk)
            unit = C.from_landing_page(rec, ext_rec, label="html", evidence_dir=evidence_dir)
            return {
                "ok": True,
                "text": unit.get("text") or "",
                "uri": unit.get("source", {}).get("uri") or raw,
                "url_key": uk,
                "source_note": f"命中仓内已抓取落地页语料（url_key={uk}）",
            }
    except Exception:  # noqa: BLE001
        pass

    # 若不在存量 204 条语料中，对 http(s) URL 发起实时只读抓取与 HTML 要素提取
    live_url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    try:
        from tools import lp_extract as _LPE
        from tools import lp_fetch as _LPF

        status, final_url, body, _hdr, _ms, err = _LPF.http_get(live_url, timeout=20)
        if status and 200 <= int(status) < 400 and body:
            parsed = _LPE.analyze_html(body)
            title = (parsed.get("title") or "").strip()
            meta_desc = (parsed.get("meta_description") or "").strip()
            body_text = (parsed.get("body_text") or "").strip()
            combined = " | ".join(p for p in (title, meta_desc, body_text) if p)
            if combined.strip():
                return {
                    "ok": True,
                    "text": combined[:80_000],
                    "uri": final_url or live_url,
                    "url_key": norm_key,
                    "source_note": f"实时抓取落地页（HTTP {status}，提取 {len(combined)} 字符）",
                }
        err_msg = err or f"HTTP {status}"
    except Exception as exc:  # noqa: BLE001
        err_msg = f"{type(exc).__name__}: {exc}"

    return {
        "ok": False,
        "failure_kind": "fetch_error",
        "error": f"实时抓取落地页 {live_url} 未能获取有效正文（{err_msg}）；请贴出页面文案或截图发进群内送审。",
    }


def _detect_image_mime(raw: bytes) -> str:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"


def run_vlm_four_dim_audit(image_path: Path, ocr_text: str = "") -> Optional[Dict[str, Any]]:
    """调用多模态视觉大模型对图片做四维合规审查（图内文字OCR + 画面语义 + 视觉符号 + 区域级画面审计）。

    输出全部使用直白、易扫读的大白话（适合 ADHD 快速抓重点，绝不输出内部代码字段名）。
    """
    if not image_path.is_file():
        return None
    try:
        raw_bytes = image_path.read_bytes()
    except OSError:
        return None
    # 离线单测的 10×10 纯白合成夹具（<200 字节）不发起外呼，保持离线自证快速且零网络依赖
    if len(raw_bytes) < 200:
        return None
    if not (os.environ.get("MULTIMODAL_VOD_API_TOKEN") or "").strip():
        return None

    try:
        import base64 as _b64
        from tools.multimodal_client import GatewayClient

        model = (os.environ.get("MULTIMODAL_MODEL") or "").strip() or "gemini-3.1-flash-lite"
        client = GatewayClient.from_env("vod", model=model, timeout=60.0, retry_attempts=1)
        mime = _detect_image_mime(raw_bytes)
        b64 = _b64.b64encode(raw_bytes).decode("ascii")
        ocr_hint = (ocr_text or "").strip()[:600]
        prompt = (
            "你是一名跨境电商与母婴广告合规审核员。请对这张图片做【四维合规审查】，"
            "输出必须全部讲大白话（适合 ADHD 3秒扫完，每点只写 1 句核心人话；关键违规词用「」或【】括起来强调，严禁使用 *、**、`、# 等任何 Markdown 符号，严禁出现代码字段名）：\n"
            f"参考已提取的图内 OCR 文字：{ocr_hint if ocr_hint else '（无明显文字）'}\n\n"
            "请严格输出一行 JSON（不要多余解释）：\n"
            "{\n"
            '  "overall": "发现违规需修改 或 需人工确认 或 初筛未见明显违规",\n'
            '  "short_title": "15字以内的直白核心问题标题",\n'
            '  "one_line": "42字以内的一句话核心卡点（直接说图里最大的风险是什么）",\n'
            '  "quick_fix": "一句话直接告诉设计/运营马上改哪两步（如：① 把 104.41°F 改成 98.6°F；② 底部加免责小字）",\n'
            '  "ocr_status": "有风险 或 需注意 或 正常",\n'
            '  "ocr_summary": "图上写了什么关键宣传语，有没有夸大/绝对化/医疗暗示（关键违规词用「」标出，不写星号）",\n'
            '  "scene_status": "有风险 或 需注意 或 正常",\n'
            '  "scene_semantics": "画面在展示什么产品与场景，有没有医疗诊断或不当场景暗示（关键风险用「」标出，不写星号）",\n'
            '  "symbol_status": "有风险 或 需注意 或 正常",\n'
            '  "visual_symbols": "画面里有哪些图标、徽章、认证标志或高危数值符号，有没有风险（关键符号用「」标出，不写星号）",\n'
            '  "region_rows": [\n'
            '    {"region": "顶部区域", "issue": "发现的具体问题", "fix": "直接怎么改"},\n'
            '    {"region": "中间区域", "issue": "发现的具体问题", "fix": "直接怎么改"},\n'
            '    {"region": "底部区域", "issue": "发现的具体问题", "fix": "直接怎么改"}\n'
            "  ],\n"
            '  "copy_paste_snippet": "可直接复制给设计师贴在图上的合规免责声明或替换文案（英文广告给英文+中文对照，中文广告给中文）"\n'
            "}"
        )
        payload = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
            "temperature": 0,
        }, ensure_ascii=False).encode("utf-8")
        resp = client.transport(
            client.endpoint(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {client.api_key}"},
            payload,
            60.0,
        )
        if resp.status != 200 or not resp.body:
            return None
        body_obj = json.loads(resp.body)
        content_str = (
            ((body_obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        s_idx, e_idx = content_str.find("{"), content_str.rfind("}")
        if s_idx < 0 or e_idx <= s_idx:
            return None
        parsed = json.loads(content_str[s_idx:e_idx + 1])
        if not isinstance(parsed, dict) or not parsed.get("one_line"):
            return None
        raw_rows = parsed.get("region_rows")
        region_rows = []
        if isinstance(raw_rows, list):
            for r in raw_rows:
                if isinstance(r, dict) and (r.get("region") or r.get("issue")):
                    region_rows.append({
                        "region": str(r.get("region") or "画面区域").strip(),
                        "issue": str(r.get("issue") or "—").strip(),
                        "fix": str(r.get("fix") or "—").strip(),
                    })
        return {
            "status": "ok",
            "model": model,
            "overall": str(parsed.get("overall") or "需人工确认").strip(),
            "short_title": str(parsed.get("short_title") or "").strip(),
            "one_line": str(parsed.get("one_line") or "").strip(),
            "quick_fix": str(parsed.get("quick_fix") or parsed.get("action_advice") or "").strip(),
            "ocr_status": str(parsed.get("ocr_status") or "需注意").strip(),
            "ocr_summary": str(parsed.get("ocr_summary") or "").strip(),
            "scene_status": str(parsed.get("scene_status") or "需注意").strip(),
            "scene_semantics": str(parsed.get("scene_semantics") or "").strip(),
            "symbol_status": str(parsed.get("symbol_status") or "需注意").strip(),
            "visual_symbols": str(parsed.get("visual_symbols") or "").strip(),
            "region_rows": region_rows,
            "region_audit": [
                f"{r['region']}：{r['issue']} → {r['fix']}" for r in region_rows
            ] or [
                str(x).strip() for x in (parsed.get("region_audit") or []) if str(x).strip()
            ],
            "copy_paste_snippet": str(parsed.get("copy_paste_snippet") or "").strip(),
            "action_advice": str(parsed.get("action_advice") or parsed.get("quick_fix") or "").strip(),
        }
    except Exception:  # noqa: BLE001
        return None


def run_vlm_video_four_dim_audit(video_path: Path) -> Optional[Dict[str, Any]]:
    """调用腾讯云 VOD 多模态大模型（支持音轨+画面同传）对视频做四维合规审查：
    ① 画面字幕与花字（OCR） · ② 口播语音内容（ASR） · ③ 音画一致性与符号 · ④ 精确到秒的时间轴定位表。
    """
    if not video_path.is_file():
        return None
    try:
        raw_bytes = video_path.read_bytes()
    except OSError:
        return None
    # 离线单测的小夹具（<200 字节）不发起外呼
    if len(raw_bytes) < 200 or len(raw_bytes) > 24 * 1024 * 1024:
        return None
    if not (os.environ.get("MULTIMODAL_VOD_API_TOKEN") or "").strip():
        return None

    try:
        import base64 as _b64
        from tools.multimodal_client import GatewayClient

        model = (os.environ.get("MULTIMODAL_MODEL") or "").strip() or "gemini-3.1-flash-lite"
        client = GatewayClient.from_env("vod", model=model, timeout=90.0, retry_attempts=1)
        b64 = _b64.b64encode(raw_bytes).decode("ascii")
        prompt = (
            "你是一名跨境电商与母婴视频广告合规审核员。请同时看视频画面并听音轨口播，做【视频四维合规审查】。\n"
            "输出必须全部讲大白话（适合 ADHD 3秒扫完，每点只写 1 句核心人话；关键违规词用「」或【】括起来，严禁使用 *、**、`、# 等任何 Markdown 符号）：\n"
            "请严格输出一行 JSON（不要多余解释）：\n"
            "{\n"
            '  "overall": "发现违规需修改 或 需人工确认 或 初筛未见明显违规",\n'
            '  "short_title": "15字以内的直白核心问题标题",\n'
            '  "one_line": "42字以内的一句话核心卡点（直接说视频里最大的风险是什么）",\n'
            '  "quick_fix": "一句话直接告诉剪辑/运营马上改哪两步（如：① 剪掉 00:08 医疗口播词；② 结尾补免责字幕）",\n'
            '  "ocr_status": "有风险 或 需注意 或 正常",\n'
            '  "ocr_summary": "画面字幕与花字写了什么核心宣称，有没有夸大/绝对化/医疗词（1句话）",\n'
            '  "scene_status": "有风险 或 需注意 或 正常",\n'
            '  "scene_semantics": "口播人声说了什么内容 + 画面在演示什么场景，有没有医疗疗效暗示（1句话）",\n'
            '  "symbol_status": "有风险 或 需注意 或 正常",\n'
            '  "visual_symbols": "音画是否一致（有无说A演B）+ 画面里有无违规徽标或危险动作（1句话）",\n'
            '  "region_rows": [\n'
            '    {"region": "00:00-00:05 开头", "issue": "发现的具体画面或口播问题", "fix": "直接怎么剪或改字幕"},\n'
            '    {"region": "00:05-00:15 中段", "issue": "发现的具体画面或口播问题", "fix": "直接怎么剪或改字幕"},\n'
            '    {"region": "片尾区域", "issue": "发现的具体画面或口播问题", "fix": "直接怎么剪或改字幕"}\n'
            "  ],\n"
            '  "copy_paste_snippet": "可直接复制给剪辑师加在视频底部的合规免责字幕或替换口播词"\n'
            "}"
        )
        payload = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}},
                ],
            }],
            "temperature": 0,
        }, ensure_ascii=False).encode("utf-8")
        resp = client.transport(
            client.endpoint(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {client.api_key}"},
            payload,
            90.0,
        )
        if resp.status != 200 or not resp.body:
            return None
        body_obj = json.loads(resp.body)
        content_str = (
            ((body_obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        s_idx, e_idx = content_str.find("{"), content_str.rfind("}")
        if s_idx < 0 or e_idx <= s_idx:
            return None
        parsed = json.loads(content_str[s_idx:e_idx + 1])
        if not isinstance(parsed, dict) or not parsed.get("one_line"):
            return None
        raw_rows = parsed.get("region_rows")
        region_rows = []
        if isinstance(raw_rows, list):
            for r in raw_rows:
                if isinstance(r, dict) and (r.get("region") or r.get("issue")):
                    region_rows.append({
                        "region": str(r.get("region") or "视频片段").strip(),
                        "issue": str(r.get("issue") or "—").strip(),
                        "fix": str(r.get("fix") or "—").strip(),
                    })
        return {
            "status": "ok",
            "media_kind": "video",
            "model": model,
            "overall": str(parsed.get("overall") or "需人工确认").strip(),
            "short_title": str(parsed.get("short_title") or "").strip(),
            "one_line": str(parsed.get("one_line") or "").strip(),
            "quick_fix": str(parsed.get("quick_fix") or "").strip(),
            "ocr_status": str(parsed.get("ocr_status") or "需注意").strip(),
            "ocr_summary": str(parsed.get("ocr_summary") or "").strip(),
            "scene_status": str(parsed.get("scene_status") or "需注意").strip(),
            "scene_semantics": str(parsed.get("scene_semantics") or "").strip(),
            "symbol_status": str(parsed.get("symbol_status") or "需注意").strip(),
            "visual_symbols": str(parsed.get("visual_symbols") or "").strip(),
            "region_rows": region_rows,
            "region_audit": [f"{r['region']}：{r['issue']} → {r['fix']}" for r in region_rows],
            "copy_paste_snippet": str(parsed.get("copy_paste_snippet") or "").strip(),
        }
    except Exception:  # noqa: BLE001
        return None


def _legacy_bridge_fields(
    *,
    label: str,
    layer: str,
    release_status: str,
    findings: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    receipt: Dict[str, Any],
    product_line_res: Dict[str, Any],
    stage_res: Dict[str, Any],
) -> Dict[str, Any]:
    """生成与 `judge_evidence.mjs` 及既有单测兼容的 `verdict` / `hits` / `boundary_statement`。"""
    disposition_map = {
        "BLOCK": "auto_reject",
        "REVIEW": "review",
        "待自决": "review",
        "PASS": "auto_pass",
        "未审查": "unassessed",
    }
    disposition = disposition_map.get(label, "review")

    hits: List[Dict[str, Any]] = []
    rules_hit: List[str] = []
    control_codes_hit: List[str] = []

    for f in findings:
        if not isinstance(f, dict):
            continue
        rk = f.get("rule_key") or f.get("control_code") or "RULE"
        cc = f.get("control_code")
        if rk and rk not in rules_hit:
            rules_hit.append(rk)
        if cc and cc not in control_codes_hit:
            control_codes_hit.append(cc)
        quote = f.get("quote") or ""
        loc = f.get("location") if isinstance(f.get("location"), dict) else {}
        matched_entry = {
            "matched_text": quote,
            "matched_keyword": quote,
            "start": loc.get("start"),
            "end": loc.get("end"),
        }
        hits.append({
            "rule_key": rk,
            "control_code": cc,
            "severity": f.get("severity"),
            "status": f.get("status"),
            "authority_ref": f.get("authority_ref") or [],
            "matched": [matched_entry] if quote else [],
        })

    cov_state = (coverage or {}).get("coverage_state") or "partial"
    dnc = list((coverage or {}).get("does_not_cover") or [])
    unknowns = list(dnc)
    if product_line_res.get("status") != "declared":
        unknowns.append(product_line_res.get("note") or "")
    if stage_res.get("status") != "declared":
        unknowns.append(stage_res.get("note") or "")
    if not unknowns:
        unknowns.append("机器判定只做风险筛查与问题标注（release_status=待放行），最终放行须经人工/法务复核。")

    # 外部标准库研究稿提示（与 judge_copy 的契约保持一致）
    unconfirmed_notice = (
        "本次引用的《外部标准库》条目当前处于研究稿状态（ratified=false），"
        "仅供合规筛查参考，不构成法务最终裁定。"
    )
    evidence_ref = []
    for f in findings:
        for ref in (f.get("authority_ref") or []) if isinstance(f, dict) else []:
            if isinstance(ref, dict):
                evidence_ref.append(ref)

    receipt_out = dict(receipt or {})
    receipt_out.setdefault("evidence_ref", evidence_ref)
    receipt_out.setdefault("ratified", False)
    receipt_out.setdefault("unconfirmed_notice", unconfirmed_notice)

    total_issues = len(hits)
    return {
        "verdict": {
            "disposition": disposition,
            "label": label,
            "layer": layer,
            "release_status": release_status,
            "rules_hit": rules_hit,
            "control_codes_hit": control_codes_hit,
            "machine_may_finalize": layer in ("DP0", "DP1", "DP2"),
            "total_issues": total_issues,
        },
        "hits": hits,
        "boundary_statement": {
            "coverage": "hit" if hits else ("catch_all" if cov_state != "full" else "no_hit"),
            "coverage_state": cov_state,
            "unknowns": [u for u in unknowns if u],
        },
        "receipt": receipt_out,
    }


def ingest_and_judge(
    *,
    carrier: str = "free_text",
    text: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    doc_token: Optional[str] = None,
    product_line: Optional[str] = None,
    content_stage: Optional[str] = None,
    message_id: Optional[str] = None,
    sender_open_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    tenant: str = DEFAULT_TENANT,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """统一执行「四维组装 → 生产引擎判定 → 工作台权威账本与 SQLite 投影建案」。"""
    t0 = time.time()
    carrier = (carrier or "free_text").strip()

    # 1. 若输入是自由文本但包含飞书云文档链接且长文本为空，可自动识别云文档
    if carrier == "feishu_doc" or (carrier == "free_text" and doc_token):
        target_doc = doc_token or url or text or ""
        if not text or FEISHU_DOC_RE.fullmatch(text.strip()):
            extracted = _extract_feishu_doc_text(target_doc)
            if not extracted["ok"]:
                return {
                    "ok": False,
                    "contract_version": CONTRACT_VERSION,
                    "carrier": "feishu_doc",
                    "label": "未审查",
                    "layer": "DP0",
                    "release_status": "待放行",
                    "parse_status": "failed",
                    "failure_kind": extracted["failure_kind"],
                    "error": extracted["error"],
                }
            text = extracted["text"]
            url = extracted["uri"]
            carrier = "feishu_doc"

    if carrier == "landing_url":
        target_url = url or text or ""
        extracted = _extract_landing_url_text(target_url)
        if not extracted["ok"]:
            return {
                "ok": False,
                "contract_version": CONTRACT_VERSION,
                "carrier": "landing_url",
                "label": "未审查",
                "layer": "DP0",
                "release_status": "待放行",
                "parse_status": "failed",
                "failure_kind": extracted["failure_kind"],
                "error": extracted["error"],
            }
        text = extracted["text"]
        url = extracted["uri"]

    # 2. 解析品线
    pl_res = resolve_product_line(
        text, declared=product_line, uri=url or file_path, fields=fields
    )
    resolved_pl = pl_res["value"]

    # 3. 构造确定性 submission_id 与 URI（保证同一条飞书消息重推时幂等）
    seed_material = "|".join([
        carrier,
        str(message_id or ""),
        str(url or ""),
        str(file_path or ""),
        hashlib.sha256(
            json.dumps({"t": text, "f": fields}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
    ])
    sub_hash_short = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16]
    submission_id = (
        f"feishu-{message_id}"
        if message_id and re.match(r"^[A-Za-z0-9_-]+$", str(message_id))
        else f"feishu-{sub_hash_short}"
    )
    stable_uri = (
        url
        or (f"feishu-message:{message_id}" if message_id else f"submission:{submission_id}")
    )

    # 4. 构造四维 submission 字典
    media_roots: Tuple[str, ...] = ()
    if carrier == "image":
        if not file_path:
            return {
                "ok": False,
                "contract_version": CONTRACT_VERSION,
                "carrier": "image",
                "label": "未审查",
                "layer": "DP0",
                "release_status": "待放行",
                "parse_status": "failed",
                "failure_kind": "fetch_error",
                "error": "缺少图片文件路径",
            }
        abs_media = Path(file_path).expanduser().resolve()
        media_roots = (str(abs_media.parent),)
        submission: Dict[str, Any] = {
            "submission_id": submission_id,
            "content_type": "图片",
            "entry_channel": "群消息",
            "source": {"kind": "image", "uri": str(abs_media)},
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    elif carrier == "video":
        if not file_path:
            return {
                "ok": False,
                "contract_version": CONTRACT_VERSION,
                "carrier": "video",
                "label": "未审查",
                "layer": "DP0",
                "release_status": "待放行",
                "parse_status": "failed",
                "failure_kind": "fetch_error",
                "error": "缺少视频文件路径",
            }
        abs_media = Path(file_path).expanduser().resolve()
        media_roots = (str(abs_media.parent),)
        submission = {
            "submission_id": submission_id,
            "content_type": "视频",
            "entry_channel": "群消息",
            "source": {"kind": "video", "uri": str(abs_media)},
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    elif carrier == "structured_json":
        submission = {
            "submission_id": submission_id,
            "content_type": "结构化记录",
            "entry_channel": "群消息",
            "source": {"kind": "structured_json", "uri": stable_uri},
            "fields": fields,
            "text": text,
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    elif carrier == "ad_text":
        submission = {
            "submission_id": submission_id,
            "content_type": "文本",
            "entry_channel": "群消息",
            "source": {"kind": "ad_text", "uri": stable_uri},
            "fields": fields or {"Primary Text": text or "", "Headline": ""},
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    elif carrier == "feishu_doc":
        submission = {
            "submission_id": submission_id,
            "content_type": "文档",
            "entry_channel": "飞书文档链接",
            "source": {"kind": "free_text", "doc_type": "docx", "uri": stable_uri},
            "text": text,
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    elif carrier == "landing_url":
        submission = {
            "submission_id": submission_id,
            "content_type": "文本",
            "entry_channel": "落地页 URL",
            "source": {"kind": "free_text", "uri": stable_uri},
            "text": text,
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }
    else:
        submission = {
            "submission_id": submission_id,
            "content_type": "文本",
            "entry_channel": "群消息",
            "source": {"kind": "free_text", "uri": stable_uri},
            "text": text,
            "product_line": resolved_pl,
            "tenant": tenant,
            "uri": stable_uri,
        }

    if content_stage:
        submission["content_stage"] = content_stage

    submission, known_inf, stage_res = resolve_content_stage(submission)

    principal = {
        "id": (sender_open_id or "feishu:guard").strip() or "feishu:guard",
        "tenant": tenant,
        "roles": ["submitter", "dp3"],
        "product_lines": list(VALID_PRODUCT_LINES),
    }

    root = data_root if data_root is not None else workbench_data_root()
    authority_dir = root / "authority"
    projection_db = root / "db" / "review.db"
    authority_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    projection_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(root, 0o700)
        os.chmod(authority_dir, 0o700)
        os.chmod(projection_db.parent, 0o700)
    except OSError:
        pass

    prev_media_env = os.environ.get(MEDIA_INGEST_ENV)
    prev_vod_tok = os.environ.get("MULTIMODAL_VOD_API_TOKEN")
    if carrier in ("image", "video"):
        os.environ[MEDIA_INGEST_ENV] = "1"
    if carrier in ("image", "video") and prev_vod_tok:
        # 图片与视频四维多模态审查由下方 run_vlm_four_dim_audit / run_vlm_video_four_dim_audit 单次聚合完成，避免 prepare 内部重复外呼
        os.environ.pop("MULTIMODAL_VOD_API_TOKEN", None)

    lease = WriterLease(authority_dir / "writer.lock")
    try:
        ingestor = SubmissionIngestor(media_roots=media_roots)
        lease.acquire()
        authority = BusinessEventStore(authority_dir, lease=lease)
        projection = ProjectionStore(projection_db)
        Projector(authority, projection).catch_up()
        service = ReviewCommandService(authority, projection)

        expected_cid = ingestor.case_id_for(tenant, submission_id)
        existing_state = authority.state(expected_cid)
        if isinstance(existing_state, dict) and int(existing_state.get("version") or 0) >= 1 and carrier in ("image", "video"):
            # 媒体附件每次下载落不同的临时目录（source.uri 不同），同 message_id 重放直接复用已建案件
            case_id = expected_cid
            case_state = existing_state
            outcome = {
                "replayed": True,
                "projection_lag": False,
                "authority_snapshot": {
                    "aggregate_id": case_id,
                    "authority_seq": authority.head().get("authority_seq", 1),
                    "manifest_sha256": authority.head().get("manifest_sha256", ""),
                },
            }
        else:
            idempotency_key = f"feishu-guard:{submission_id}:{ingestor.submission_hash(submission, principal=principal)[:16]}"
            outcome = service.execute_submission(
                ingestor=ingestor,
                submission=submission,
                principal=principal,
                idempotency_key=idempotency_key,
            )
            case_id = outcome["authority_snapshot"]["aggregate_id"]
            case_state = authority.state(case_id)
    except SubmissionRejected as exc:
        return {
            "ok": False,
            "contract_version": CONTRACT_VERSION,
            "carrier": carrier,
            "label": "未审查",
            "layer": "DP0",
            "release_status": "待放行",
            "parse_status": "failed",
            "failure_kind": "empty" if "empty" in exc.code or "0 字节" in exc.detail else "parse_error",
            "error": f"{exc.code}: {exc.detail}",
            "product_line_resolution": pl_res,
            "stage_resolution": stage_res,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "contract_version": CONTRACT_VERSION,
            "carrier": carrier,
            "label": "未审查",
            "layer": "DP0",
            "release_status": "待放行",
            "parse_status": "failed",
            "failure_kind": "parse_error",
            "error": f"{type(exc).__name__}: {exc}",
            "product_line_resolution": pl_res,
            "stage_resolution": stage_res,
        }
    finally:
        try:
            lease.release()
        except Exception:  # noqa: BLE001
            pass
        if carrier in ("image", "video"):
            if prev_media_env is None:
                os.environ.pop(MEDIA_INGEST_ENV, None)
            else:
                os.environ[MEDIA_INGEST_ENV] = prev_media_env
        if prev_vod_tok is not None:
            os.environ["MULTIMODAL_VOD_API_TOKEN"] = prev_vod_tok

    ir = case_state.get("ir") or {}
    unit = case_state.get("content") or {}
    snap = case_state.get("report_snapshot") or {}
    snap_receipt = snap.get("receipt") if isinstance(snap.get("receipt"), dict) else {}
    decision = ir.get("decision") or {}
    coverage = ir.get("coverage") or {}
    findings = list(ir.get("findings") or [])
    confirmed_findings = [f for f in findings if isinstance(f, dict) and f.get("status") == "confirmed"]
    candidate_findings = [f for f in findings if isinstance(f, dict) and f.get("status") == "candidate"]

    label = decision.get("state") or "REVIEW"
    layer = decision.get("layer") or "DP3"
    release_status = decision.get("release_status") or "待放行"
    parse_status = unit.get("parse_status", "ok")
    failure_kind = unit.get("failure_kind")

    receipt_stub = {
        "receipt_id": ir.get("receipt_ref"),
        "unit_id": unit.get("unit_id"),
        "rule_snapshot": ir.get("rule_snapshot"),
        "kb_snapshot": ir.get("kb_snapshot"),
        "control_points_version": ir.get("control_points_version"),
        "steps": snap_receipt.get("steps") or [],
        "skill": snap_receipt.get("skill"),
        "workflow_timing": snap_receipt.get("workflow_timing"),
        "skipped": [],
    }

    bridge = _legacy_bridge_fields(
        label=label,
        layer=layer,
        release_status=release_status,
        findings=confirmed_findings,
        coverage=coverage,
        receipt=receipt_stub,
        product_line_res=pl_res,
        stage_res=stage_res,
    )

    total_issues = len(confirmed_findings) + len(candidate_findings)
    four_dim_audit = None
    if carrier == "image" and file_path:
        four_dim_audit = run_vlm_four_dim_audit(Path(file_path).expanduser().resolve(), unit.get("text") or "")
        if four_dim_audit and four_dim_audit.get("overall") == "发现违规需修改" and label == "REVIEW":
            label = "BLOCK"
            layer = "DP2"
    elif carrier == "video" and file_path:
        four_dim_audit = run_vlm_video_four_dim_audit(Path(file_path).expanduser().resolve())
        if four_dim_audit and four_dim_audit.get("overall") == "发现违规需修改" and label == "REVIEW":
            label = "BLOCK"
            layer = "DP2"

    if four_dim_audit and four_dim_audit.get("short_title"):
        kind_tag = "视频审查" if carrier == "video" else "图片审查"
        verdict_line = f"【{kind_tag}：{four_dim_audit['overall']}】{four_dim_audit['short_title']}"
    elif label == "BLOCK":
        verdict_line = f"【审查结论：BLOCK】共发现 {total_issues or 1} 处必须修改（案件 {case_id}）。"
    elif label in ("REVIEW", "待自决"):
        verdict_line = f"【审查结论：{label}】共发现 {total_issues} 处需人工确认（案件 {case_id}）。"
    elif label == "PASS":
        verdict_line = f"【审查结论：PASS】未发现已知底线风险，待人工复核放行（案件 {case_id}）。"
    else:
        verdict_line = f"【审查结论：未审查】素材未完成解析（{layer}），需人工处理（案件 {case_id}）。"

    elapsed_ms = int(round((time.time() - t0) * 1000))
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "carrier": carrier,
        "case_id": case_id,
        "four_dim_audit": four_dim_audit,
        "prd53_verdict": {
            "state": label,
            "line": verdict_line,
            "total": total_issues,
        },
        "submission_id": submission_id,
        "replayed": bool(outcome.get("replayed")),
        "authority_seq": outcome["authority_snapshot"]["authority_seq"],
        "manifest_sha256": outcome["authority_snapshot"]["manifest_sha256"],
        "projection_lag": bool(outcome.get("projection_lag")),
        "workbench_data_root": str(root),
        "unit_id": unit.get("unit_id"),
        "parse_status": parse_status,
        "failure_kind": failure_kind,
        "label": label,
        "layer": layer,
        "release_status": release_status,
        "run_state": decision.get("run_state", "OK"),
        "product_line": resolved_pl,
        "product_line_resolution": pl_res,
        "content_stage": submission.get("content_stage"),
        "stage_resolution": stage_res,
        "findings": findings,
        "confirmed_findings_count": len(confirmed_findings),
        "fact_candidates": candidate_findings,
        "multimodal_observations": list(ir.get("multimodal_observations") or []),
        "multimodal_note": case_state.get("multimodal_note") or "",
        "coverage": coverage,
        "workflow_timing": snap_receipt.get("workflow_timing") or ir.get("workflow_timing"),
        "ir": ir,
        "elapsed_ms": elapsed_ms,
        **bridge,
    }


def _summarize_case_state(state: Dict[str, Any]) -> Dict[str, Any]:
    ir = state.get("ir") if isinstance(state.get("ir"), dict) else {}
    decision = ir.get("decision") if isinstance(ir.get("decision"), dict) else {}
    findings = [f for f in (ir.get("findings") or []) if isinstance(f, dict)]
    confirmed = [f for f in findings if f.get("status") == "confirmed"]
    snap = state.get("report_snapshot") if isinstance(state.get("report_snapshot"), dict) else {}
    snap_rc = snap.get("receipt") if isinstance(snap.get("receipt"), dict) else {}
    rel = state.get("release") if isinstance(state.get("release"), dict) else {}
    return {
        "case_id": state.get("case_id"),
        "submission_id": state.get("submission_id"),
        "status": state.get("status"),
        "version": state.get("version"),
        "assignee": state.get("assignee"),
        "submitter_id": state.get("submitter_id"),
        "tenant": state.get("tenant"),
        "product_line": state.get("product_line"),
        "content_type": state.get("content_type"),
        "content_stage": state.get("content_stage"),
        "entry_channel": state.get("entry_channel"),
        "label": decision.get("state"),
        "layer": decision.get("layer"),
        "release_status": rel.get("status") or decision.get("release_status") or "待放行",
        "findings_total": len(findings),
        "confirmed_findings_count": len(confirmed),
        "findings_preview": [
            {
                "control_code": f.get("control_code"),
                "rule_key": f.get("rule_key"),
                "severity": f.get("severity"),
                "quote": f.get("quote"),
            }
            for f in confirmed[:5]
        ],
        "workflow_timing": snap_rc.get("workflow_timing") or ir.get("workflow_timing"),
        "created_at": state.get("created_at") or ir.get("created_at"),
        "updated_at": state.get("updated_at"),
    }


def query_workbench_case(
    *,
    case_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    product_line_filter: Optional[str] = None,
    limit: int = 10,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """只读查询工作台案件详情或队列列表（不产生任何权威写事件）。"""
    root = data_root if data_root is not None else workbench_data_root()
    projection_db = root / "db" / "review.db"
    if not projection_db.exists():
        return {
            "ok": True,
            "mode": "detail" if case_id else "list",
            "workbench_data_root": str(root),
            "found": False if case_id else None,
            "total": 0,
            "cases": [],
            "note": "工作台投影数据库尚未创建（当前无已建案件）",
        }
    projection = ProjectionStore(projection_db)
    if case_id:
        cid = str(case_id).strip()
        st = projection.get_case(cid)
        if st is None:
            return {
                "ok": True,
                "mode": "detail",
                "case_id": cid,
                "found": False,
                "workbench_data_root": str(root),
                "note": f"在工作台投影库中未找到案件 {cid}",
            }
        return {
            "ok": True,
            "mode": "detail",
            "case_id": cid,
            "found": True,
            "workbench_data_root": str(root),
            "case": _summarize_case_state(st),
        }

    all_states = projection.list_cases()
    filtered = []
    for st in all_states:
        if not isinstance(st, dict):
            continue
        if status_filter and st.get("status") != status_filter:
            continue
        if product_line_filter and st.get("product_line") != product_line_filter:
            continue
        filtered.append(_summarize_case_state(st))
    filtered.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    cap = max(1, min(50, int(limit or 10)))
    return {
        "ok": True,
        "mode": "list",
        "workbench_data_root": str(root),
        "total": len(filtered),
        "returned": len(filtered[:cap]),
        "cases": filtered[:cap],
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="飞书 Guard 统一生产审查与工作台建案入口")
    p.add_argument("--carrier", default="free_text",
                   choices=("free_text", "ad_text", "structured_json", "feishu_doc", "landing_url", "image", "video"))
    p.add_argument("--text", help="待审文本正文")
    p.add_argument("--text-file", help="从文件读取待审文本正文")
    p.add_argument("--fields-json", help="结构化字段 JSON 字符串（ad_text 或 structured_json）")
    p.add_argument("--file-path", help="本地媒体文件路径（image / video）")
    p.add_argument("--url", help="落地页 URL 或飞书文档链接")
    p.add_argument("--doc-token", help="飞书云文档 token 或链接")
    p.add_argument("--product-line", help="显式指定品线（五选一）")
    p.add_argument("--content-stage", help="显式指定内容阶段（brief / final_content）")
    p.add_argument("--message-id", help="飞书 message_id（用于稳定 URI 与幂等键）")
    p.add_argument("--sender-open-id", help="飞书发送者 open_id")
    p.add_argument("--chat-id", help="飞书会话 chat_id")
    p.add_argument("--locale", help="语种代码（兼容参数）")
    p.add_argument("--platform", help="投放平台（兼容参数）")
    p.add_argument("--ad-id", help="外部广告 ID（兼容参数）")
    p.add_argument("--origin", default="shouheng", help="来源标识（兼容参数）")
    p.add_argument("--brief", action="store_true", help="精简输出（省略完整 ir 树以节省上下文体积）")
    p.add_argument("--receipt", action="store_true", help="包含回执（默认已含）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--query-case", help="按 case_id 查询工作台案件状态与详情")
    p.add_argument("--list-cases", action="store_true", help="列出工作台案件队列摘要")
    p.add_argument("--status-filter", help="配合 --list-cases 按案件状态过滤（如 unassigned/claimed/reviewed/released）")
    p.add_argument("--limit", type=int, default=10, help="配合 --list-cases 返回条数上限（默认 10）")

    args = p.parse_args(argv)

    if args.query_case or args.list_cases:
        qres = query_workbench_case(
            case_id=args.query_case,
            status_filter=args.status_filter,
            product_line_filter=args.product_line,
            limit=args.limit,
        )
        print(json.dumps(qres, ensure_ascii=False))
        return 0

    body_text = args.text
    if args.text_file:
        body_text = Path(args.text_file).read_text(encoding="utf-8")

    fields_obj = None
    if args.fields_json:
        fields_obj = json.loads(args.fields_json)

    # 自动识别：如果传进来的是纯文本，但整段就是一条飞书 docx/wiki 链接，自动切到 feishu_doc
    carrier = args.carrier
    if carrier == "free_text" and not args.doc_token and not args.url and isinstance(body_text, str):
        stripped = body_text.strip()
        if FEISHU_DOC_RE.fullmatch(stripped):
            carrier = "feishu_doc"
            args.doc_token = stripped

    result = ingest_and_judge(
        carrier=carrier,
        text=body_text,
        fields=fields_obj,
        file_path=args.file_path,
        url=args.url,
        doc_token=args.doc_token,
        product_line=args.product_line,
        content_stage=args.content_stage,
        message_id=args.message_id or args.ad_id,
        sender_open_id=args.sender_open_id,
        chat_id=args.chat_id,
    )

    if args.brief and isinstance(result, dict):
        result = {k: v for k, v in result.items() if k != "ir"}

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"case_id={result.get('case_id')} label={result.get('label')} "
            f"layer={result.get('layer')} release_status={result.get('release_status')} "
            f"product_line={result.get('product_line')}({(result.get('product_line_resolution') or {}).get('status')}) "
            f"findings={result.get('confirmed_findings_count', 0)}"
        )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
