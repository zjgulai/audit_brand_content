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
import xml.etree.ElementTree as ET
import zipfile
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
    "推车",
    "背带",
    "温奶器",
    "哺乳内衣",
)

#: 哪些载体产「文案四维体检」。图片/视频各自有另一套四维。
TEXT_CARRIERS: Tuple[str, ...] = ("free_text", "ad_text", "structured_json", "feishu_doc", "landing_url")

#: 五条品线的确定性识别词表（按特异性排序；英文词要求词边界避免子串误判）
#: 品线的确定性识别词表。**键必须是 9 族之一** —— 推断循环遍历的是
#: `VALID_PRODUCT_LINES`，键写成三级分类（如「推车」）就永远查不到。
#:
#: ★ 2026-11-05：取值域收敛到 GTM 品线 9 族之后，原先这张表的键
#:   （推车/背带/温奶器/哺乳内衣）全部成为孤儿键 —— 实测后果：
#:   `stroller` 识别不出推车、`nursing bra` 识别不出内衣，一律回落成吸奶器。
#:   现在按族重建，三级分类的词统一并进它所属的族（归属依据见
#:   research/governance/品线映射-v1.md §2.2）。
PRODUCT_LINE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "吸奶器": (
        "吸奶器", "吸乳器", "吸乳", "集奶器", "喇叭罩",
        "breast pump", "pumping", "lactation", "flange",
        "s12 pro", "s9 pro", "m5", "m6", "m9", "v1 pro", "v2 pro",
    ),
    "服纺": (
        "哺乳内衣", "哺乳文胸", "孕妇内衣", "授乳内衣", "文胸", "运动内衣", "塑身服",
        "nursing bra", "maternity bra", "pumping bra", "hands-free bra",
        "内衣", "家居服",
    ),
    "家纺": (
        "推车", "婴儿车", "婴儿推车", "伞车", "溜娃神器",
        "背带", "腰凳", "背巾", "孕妇枕", "哺乳枕", "襁褓睡袋", "床品", "四件套",
        "stroller", "baby wagon", "pram", "pushchair",
        "baby carrier", "infant carrier", "baby wrap", "hipseat", "hip seat",
    ),
    "喂养": (
        "温奶器", "暖奶器", "热奶器", "恒温壶", "调奶器",
        "奶瓶", "消毒器", "奶瓶清洗机", "吸奶器配件", "储奶袋",
        "bottle warmer", "milk warmer", "water warmer", "bottle sterilizer",
    ),
    "婴幼儿": (
        "婴儿背带", "婴儿秋千", "电动秋千", "高脚椅", "餐椅", "监视器", "尿布桶",
        "婴儿监护", "摇椅", "安抚椅", "吸鼻器",
        "baby monitor", "high chair", "baby swing",
    ),
    "孕产": ("孕产", "孕妇", "孕期", "产妇", "pregnancy pillow", "maternity"),
    "护肤": ("护肤", "面霜", "身体乳", "洗面奶", "精华", "skincare", "lotion"),
    "快消": (
        "牙胶", "牙刷", "婴儿湿巾", "湿巾", "纸尿裤", "拉拉裤", "洗护套装",
        "沐浴片", "沐浴炸弹", "teether", "diaper", "wipes",
    ),
    "家居": ("家居", "收纳", "除甲醛"),
}

#: 进件失败 / 解析失败的回退标签与处置层。
#: ★ 唯一来源是 base/decision_table.py 的契约词表 —— 桥接层**不产第二套判定**：
#:   这些值只表达「没进判定链」（未审查/DP0），与 decision_table 对 parse_status=failed
#:   的契约回退同源同字；J1 白名单语义是「判定逻辑只在判定表」，这里只做**透传**。
from base.decision_table import (  # noqa: F401  # 契约同源声明
    AUDIT_FALLBACK_LABEL,
    AUDIT_FALLBACK_LAYER,
)

FEISHU_DOC_RE = re.compile(
    r"https?://[a-zA-Z0-9._-]+\.(?:feishu\.cn|larksuite\.com)/(docx|wiki)/([A-Za-z0-9_-]{10,})"
)

HTTP_URL_RE = re.compile(r"https?://[^\s<>\"'`]+")


def _is_inside_repo(p: Path) -> bool:
    resolved = p.expanduser().resolve()
    return resolved == REPO_ROOT or REPO_ROOT in resolved.parents


# ══════════════════════════════════════════════════════════════════════
# Office 附件正文抽取（.docx / .xlsx）—— 纯 stdlib，不引第三方包
# ══════════════════════════════════════════════════════════════════════

#: 抽取到的正文行之间用这个分隔。**不用空行**：
#: 空行在渲染成卡片 markdown 时会被折叠掉，而用户要看到的是「原文哪里断的」。
_OFFICE_LINE_SEP = "\n"

#: WordprocessingML 命名空间。`w:` 前缀在每个文件里可能绑到不同的 URI，
#: 所以**按 URI 匹配**，不按前缀 —— 手写/转换器产出的 docx 前缀并不统一。
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: SpreadsheetML 命名空间（xlsx）。
_S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _docx_part_text(xml_bytes: bytes) -> List[str]:
    """从一个 document/header/footer 部件里按段落取文本。

    ★ 为什么要按 `<w:p>` 分组而不是 `itertext()` 全捞：
    全捞会把表格里两格间的换行、以及 `<w:tab/>` 全糊成一行，
    而「哪一句挨着哪一句」正是文案审查要看的东西（一句搭配另一句才构成宣称）。
    ★ 表格行 `<w:tr>` 单独成行、单元格之间用 ` | ` 隔开，
    与 xlsx 的口径一致 —— 同一次审查里两种表格长得不该不一样。
    """
    root = ET.fromstring(xml_bytes)
    out: List[str] = []

    # ★ 按**文档顺序**走，不按「先表格再段落」。
    #   文档顺序是文案审查要看的：一句宣称作标题、表格给它数字、
    #   下一段再补条件 —— 打乱之后读到的是另一件事。
    #   做法是一个显式栈：遇到 `<w:tbl>` 就地整块转成行，不再往里走；
    #   其余节点递归，遇到 `<w:p>` 收一段。这样表格里的段落不会被再收一遍
    #   （原先按 id 去重也行，但那只治重复、治不了顺序）。
    def walk(el) -> None:
        tag = el.tag
        if tag == f"{_W_NS}tbl":
            for tr in el.findall(f"{_W_NS}tr"):
                cells = []
                for tc in tr.findall(f"{_W_NS}tc"):
                    cells.append("".join(t.text or "" for t in tc.iter(f"{_W_NS}t")).strip())
                row = " | ".join(cells).strip()
                if row.strip(" |"):
                    out.append(row)
            return
        if tag == f"{_W_NS}p":
            text = "".join(t.text or "" for t in el.iter(f"{_W_NS}t")).strip()
            if text:
                out.append(text)
            return
        for child in el:
            walk(child)

    walk(root)
    return out


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    """读 `xl/sharedStrings.xml`。不存在时返回空表（不是错误：内联字符串的表格没有这个部件）。"""
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    strings: List[str] = []
    for si in root.iter(f"{_S_NS}si"):
        # `<si>` 里可能是 `<t>`，也可能是一串富文本 `<r><t>` —— 全要。
        strings.append("".join(t.text or "" for t in si.iter(f"{_S_NS}t")))
    return strings


def _xlsx_sheet_text(xml_bytes: bytes, shared: List[str]) -> List[str]:
    """一个 sheet 部件 → 每行一段，非空单元格用 ` | ` 隔开。"""
    root = ET.fromstring(xml_bytes)
    rows: List[str] = []
    for row in root.iter(f"{_S_NS}row"):
        cells: List[str] = []
        for c in row.findall(f"{_S_NS}c"):
            t = c.get("t")
            if t == "s":
                # 共享字符串：`<v>` 是索引
                v = c.find(f"{_S_NS}v")
                idx_txt = (v.text or "").strip() if v is not None else ""
                try:
                    val = shared[int(idx_txt)]
                except (ValueError, IndexError):
                    val = ""
            elif t == "inlineStr":
                is_el = c.find(f"{_S_NS}is")
                val = "".join(x.text or "" for x in is_el.iter(f"{_S_NS}t")) if is_el is not None else ""
            else:
                # 数值 / 公式结果 / 布尔：都落在 `<v>`
                v = c.find(f"{_S_NS}v")
                val = (v.text or "") if v is not None else ""
            val = str(val).strip()
            if not val and t != "inlineStr":
                # ★ 空格子不占位，否则每行尾部会拖一串 ` | | |`。
                #   但**行中**的空格子要保留占位 —— 否则第 3 列的值会挪到第 2 列，
                #   读表的人会把「199 元套装」读成「199 元单价」。
                cells.append(None if val == "" else val)
                continue
            cells.append(val)
        while cells and cells[-1] is None:
            cells.pop()
        if not cells:
            continue
        line = " | ".join(x or "" for x in cells).strip()
        if line.strip(" |"):
            rows.append(line)
    return rows


def extract_office_attachment_text(file_path: Path) -> Dict[str, Any]:
    """抽取 .docx / .xlsx 的可读正文。**纯 stdlib**（zipfile + ElementTree）。

    返回三种形状，彼此**不许冒充**（与 `ingestAttachment` 的 failure_kind 同口径）：

        {"ok": True,  "text": ..., "chars": n, "ext": ".docx"}
        {"ok": False, "failure_kind": "empty",       "error": "文档内未提取到可读文字"}
        {"ok": False, "failure_kind": "parse_error", "error": ...}

    ★ 为什么 `empty` 与 `parse_error` 必须分开：前者是「文件读到了、里面真的没字」
      （例如只有一张图片的 docx），后者是「文件根本解不开」（坏 zip / 不是 OOXML）。
      对用户的意思完全不同：前者要他补正文，后者要他重发文件。
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext not in (".docx", ".xlsx"):
        return {"ok": False, "failure_kind": "unsupported",
                "error": f"extract_office_attachment_text 只处理 .docx / .xlsx，收到 {ext or '（无扩展名）'}"}

    try:
        with zipfile.ZipFile(p) as zf:
            if ext == ".docx":
                parts = ["word/document.xml"]
                for name in zf.namelist():
                    if re.match(r"word/(header|footer)\d*\.xml$", name):
                        parts.append(name)
                lines: List[str] = []
                found_any = False
                for name in parts:
                    try:
                        raw = zf.read(name)
                    except KeyError:
                        continue
                    found_any = True
                    lines.extend(_docx_part_text(raw))
                if not found_any:
                    return {"ok": False, "failure_kind": "parse_error",
                            "error": "这个 .docx 里没有 word/document.xml —— 它可能不是 Word 文档，或已被改过后缀"}
            else:
                shared = _xlsx_shared_strings(zf)
                sheets = sorted(n for n in zf.namelist()
                                if re.match(r"xl/worksheets/sheet\d*\.xml$", n))
                if not sheets:
                    return {"ok": False, "failure_kind": "parse_error",
                            "error": "这个 .xlsx 里没有 xl/worksheets/sheet*.xml —— 它可能不是 Excel 工作簿"}
                lines = []
                for name in sheets:
                    lines.extend(_xlsx_sheet_text(zf.read(name), shared))
    except zipfile.BadZipFile as exc:
        return {"ok": False, "failure_kind": "parse_error",
                "error": f"不是有效的 Office 压缩包（{exc}）—— 可能文件损坏，或后缀是改的"}
    except ET.ParseError as exc:
        return {"ok": False, "failure_kind": "parse_error",
                "error": f"XML 解析失败（{exc}）—— 文件内容不是合法的 OOXML"}
    except OSError as exc:
        return {"ok": False, "failure_kind": "parse_error",
                "error": f"读不到文件（{exc}）"}

    text = _OFFICE_LINE_SEP.join(x for x in (s.strip() for s in lines) if x).strip()
    if not text:
        return {"ok": False, "failure_kind": "empty",
                "error": "文档内未提取到可读文字（可能只有图片、图表或空表格）"}
    return {"ok": True, "text": text, "chars": len(text), "ext": ext}


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


#: 工作台五品线之外、但群里天天会送审的**子品类**。
#: ★ 它只影响「卡片上写这叫什么东西」与「用哪条安全提醒审」，**不改变建案品线** ——
#:   工作台 RBAC 与投影库只认 `VALID_PRODUCT_LINES`，把「婴儿监护仪」塞进 value
#:   会让建案被拒。所以识别结果落在 `display_category`，`value` 仍是默认品线。
#: ★ 这段存在的理由是一次真事故：一张 Baby Monitor 送审被识别成「吸奶器」，
#:   于是安全提醒说的是「奶量倍增」，而它真正的红线是「不能暗示预防 SIDS」。
EXTENDED_CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "婴儿监护仪": (
        "婴儿监护", "监护仪", "监视器", "看护器",
        "baby monitor", "video monitor", "bm01", "bm03", "bm04", "bm08", "parent unit",
    ),
    "消毒与洗瓶机": (
        "消毒器", "消毒机", "烘干机", "洗瓶机", "奶瓶清洗", "清洁片", "除垢片",
        "sterilizer", "bottle washer", "descaling tablet", "detergent tablet", "kleanpal",
    ),
    "储奶袋与配件": (
        "储奶袋", "母乳储存袋", "storage bag", "breastmilk storage",
    ),
    "孕妇枕与睡眠": (
        "孕妇枕", "睡眠枕", "pregnancy pillow", "maternity pillow", "swaddle", "襁褓", "睡袋",
    ),
}


def _keyword_hit_count(haystack: str, keywords: Tuple[str, ...]) -> Tuple[int, Optional[str]]:
    """返回 `(命中词数, 第一个命中词)`。英文按词边界，中文按子串 —— 与五品线同一套读法。"""
    hit_count = 0
    first_kw: Optional[str] = None
    for kw in keywords:
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
    return hit_count, first_kw


def resolve_product_line(
    text: Optional[str] = None,
    *,
    declared: Optional[str] = None,
    uri: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """解析品线。返回 `{value, status, matched_keyword, declared, note, display_category}`。

    status 四档互不冒充：
    - `declared`                  调用方显式给出了合法的五品线之一
    - `invalid_declared_fallback` 调用方给了值但不在五品线内，回落默认「吸奶器」并明说
    - `inferred_keyword`          未声明，但从正文/字段/URL 关键词匹配到了具体品线
    - `default_fallback`          未声明且无品线词命中，回落默认「吸奶器」并明说

    `display_category` 是**给人看**的品类名（可以超出五品线，如「婴儿监护仪」）；
    `value` 始终是工作台可建的品线。两者分开的原因是工作台只认五品线（见
    `EXTENDED_CATEGORY_KEYWORDS` 的注释）。
    """
    if isinstance(declared, str) and declared.strip():
        clean = declared.strip()
        if clean in VALID_PRODUCT_LINES:
            return {
                "value": clean,
                "status": "declared",
                "matched_keyword": None,
                "declared": clean,
                "display_category": clean,
                "note": f"使用显式指定的品线「{clean}」",
            }
        return {
            "value": DEFAULT_PRODUCT_LINE,
            "status": "invalid_declared_fallback",
            "matched_keyword": None,
            "declared": clean,
            "display_category": clean,
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
            hit_count, first_kw = _keyword_hit_count(haystack, PRODUCT_LINE_KEYWORDS.get(line_name, ()))
            if hit_count > best_count:
                best_count = hit_count
                best_line = line_name
                best_kw = first_kw

    # 五品线没命中时再查子品类。**只在五品线零命中时查**：五品线是建案口径，
    # 子品类只是显示名，让子品类覆盖五品线的匹配等于把「吸奶器」改成「储奶袋」建案。
    ext_cat: Optional[str] = None
    ext_kw: Optional[str] = None
    if best_count == 0 and haystack:
        ext_best = 0
        for cat_name, kws in EXTENDED_CATEGORY_KEYWORDS.items():
            hit_count, first_kw = _keyword_hit_count(haystack, kws)
            if hit_count > ext_best:
                ext_best = hit_count
                ext_cat = cat_name
                ext_kw = first_kw

    if best_line is not None and best_count > 0:
        return {
            "value": best_line,
            "status": "inferred_keyword",
            "matched_keyword": best_kw,
            "declared": None,
            "display_category": best_line,
            "note": f"未显式声明品线，按内容关键词「{best_kw}」自动识别为「{best_line}」",
        }

    if ext_cat is not None:
        return {
            "value": DEFAULT_PRODUCT_LINE,
            "status": "default_fallback",
            "matched_keyword": ext_kw,
            "declared": None,
            "display_category": f"{ext_cat}（工作台归入通用/吸奶器队列）",
            "note": (
                f"识别为「{ext_cat}」（关键词「{ext_kw}」）；"
                f"工作台五品线内按默认品线「{DEFAULT_PRODUCT_LINE}」建案"
            ),
        }

    return {
        "value": DEFAULT_PRODUCT_LINE,
        "status": "default_fallback",
        "matched_keyword": None,
        "declared": None,
        "display_category": f"通用母婴（未声明品线，默认{DEFAULT_PRODUCT_LINE}建案）",
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


#: `overall` 的取值规则。**三个四维审查入口共用这一段**，各写一份必然漂移。
#: ★ 它存在的理由是一次真事故：VLM 把「底部建议补一句免责声明」读成
#:   「发现违规需修改」，卡片于是把一张合规的图打成红卡并叫人改图。
#:   免责提醒是**常规动作**，不是违规 —— 这条把它写进判据，而不是靠模型自觉。
OVERALL_RULE = (
    "overall 取值规则：只有画面/文案中存在明确违规词、高烧/心率等医疗监测数据、"
    "虚假认证图标或夸大数值时，才填「发现违规需修改」；"
    "若仅存在功能宣称需要核对检测报告，填「需人工确认」；"
    "若画面/文案本身合规、仅仅是常规提醒可以补充免责声明，必须填「初筛未见明显违规」。"
    "严禁因为常规免责提醒而填「发现违规需修改」。"
)


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
            + OVERALL_RULE + "\n"
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
            + OVERALL_RULE + "\n"
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


#: 文案的「功效与安全宣称」特征词。命中即说明这一维不是空的 —— 即使字面规则没抓到，
#: 读者也该在卡上看见「这里被看过一眼」。英文按词边界，中文按子串。
TEXT_EFFICACY_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"(?<![a-z0-9])(clinically|scientifically)\s+(proven|tested)(?![a-z0-9])", "临床/科学背书"),
    (r"(?<![a-z0-9])\d{1,3}\s*%\s*(more|faster|longer|less)(?![a-z0-9])", "带数字的效果承诺"),
    (r"(?<![a-z0-9])(100\s*%|completely|totally)\s*(safe|secure|risk[- ]free)(?![a-z0-9])", "绝对安全承诺"),
    (r"(?<![a-z0-9])(prevent|prevent(s|ing)?|cure|cures|treat|treats|heal|heals)(?![a-z0-9])", "疾病治疗/预防表述"),
    (r"(?<![a-z0-9])(fda|ce|iso)\s*(approved|certified|cleared)(?![a-z0-9])", "监管认证背书"),
    (r"(?<![a-z0-9])(sids|mastitis|reflux|colic|jaundice|infection)(?![a-z0-9])", "疾病名"),
    (r"(?<![a-z0-9])(hospital[- ]grade|medical[- ]grade|clinical[- ]grade)(?![a-z0-9])", "医疗级措辞"),
    (r"(?<![a-z0-9])(alerts?\s+you\s+to\s+risks?|danger\s+zone|covered\s+face|face[- ]down\s+sleeping)", "对具体危险场景的安全承诺"),
    (r"(零风险|无副作用|百分百|100%安全|绝对安全|彻底根除)", "绝对化表述"),
    (r"(临床验证|临床证明|医学证明|科学验证|权威认证)", "医学背书"),
    (r"(防窒息|预防窒息|治疗|治愈|根治|缓解疼痛|消炎)", "疾病治疗/预防表述"),
    (r"(FDA认证|FDA批准|CE认证|医院级|医疗级)", "监管认证背书"),
)

#: 归属「功效与安全宣称」维度的控制点族（其余落入字面维度）。
TEXT_CLAIM_CONTROL_CODES = frozenset({
    "H01", "H02", "H03", "H04", "H05", "H07", "H09",
    "M01", "M02", "M04", "M05", "M06", "M07",
    "U01", "U03", "U04", "B01",
})

#: 品线的品类合规提醒（第三维「品线与平台特殊规范」的实词）。
PRODUCT_LINE_SAFETY_HINT: Dict[str, str] = {
    "吸奶器": "吸奶器属母婴用品：禁止出现医疗级/治疗/奶量倍增等承诺，性能须可测（如 mmHg）。",
    "推车": "推车属儿童用品：禁止出现安全绝对化（如「绝不侧翻」），须标注适用年龄与承重。",
    "背带": "背带禁止出现防窒息/髋关节发育等医疗暗示，须标注承重与月龄区间。",
    "温奶器": "温奶器禁止出现杀菌/消毒疗效承诺，温度须标注实测范围。",
    "哺乳内衣": "哺乳内衣禁止出现催乳/预防乳腺炎等功效暗示。",
    "婴儿监护仪": (
        "婴儿监护仪属辅助看护电子设备：严禁暗示可预防婴儿猝死（SIDS）"
        "或监测生命体征/疾病，须声明不可替代成人直接看护。"
    ),
    "消毒与洗瓶机": (
        "消毒与洗瓶机禁止出现「杀菌率 99.9%」「彻底灭菌」等无报告支撑的绝对化承诺，"
        "须标注适用材质与实测除菌条件。"
    ),
    "储奶袋与配件": (
        "储奶袋与配件禁止宣称「可长期常温保存母乳」「无菌」，"
        "须标注材质等级、耐温范围与建议储存时长。"
    ),
    "孕妇枕与睡眠": (
        "孕妇枕与睡眠类禁止暗示「预防妊娠纹」「缓解耻骨痛」等医疗功效，"
        "须标注适用孕期与不可替代医嘱。"
    ),
}


def _text_has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _display_category_of(pl_res: Dict[str, Any], product_line: str) -> str:
    """取给人看的品类名（去掉「（工作台归入…）」那段解释）。

    提醒词表按品类名索引，所以必须先剥掉括注 —— 否则「婴儿监护仪（工作台归入…）」
    查不到表，卡片第三维又会退回一句通用话。
    """
    raw = str((pl_res or {}).get("display_category") or product_line or "").strip()
    return raw.split("（", 1)[0].strip() or str(product_line or "").strip()


def _safety_hint_for(pl_res: Dict[str, Any], product_line: str) -> str:
    cat = _display_category_of(pl_res, product_line)
    return PRODUCT_LINE_SAFETY_HINT.get(cat) or PRODUCT_LINE_SAFETY_HINT.get(product_line, "")


def _text_location_label(f: Dict[str, Any]) -> str:
    """把 finding 的 location 翻成运营能照着找的位置描述。**不猜段号** —— 猜错比给字符偏移更糟。"""
    loc = f.get("location") if isinstance(f.get("location"), dict) else {}
    start, end = loc.get("start"), loc.get("end")
    if isinstance(start, int) and isinstance(end, int):
        return f"字符 {start}-{end}"
    kind = str(loc.get("kind") or "").strip()
    return kind or "全文"


def _text_efficacy_hits(text: str) -> List[str]:
    hits: List[str] = []
    low = text.lower()
    for pat, label in TEXT_EFFICACY_PATTERNS:
        try:
            if re.search(pat, low if pat.isascii() else text):
                if label not in hits:
                    hits.append(label)
        except re.error:  # pragma: no cover - 词表本身写错时不许静默失效
            continue
    return hits


def _text_snippet_for(
    text: str, product_line: str, has_hits: bool, pl_res: Optional[Dict[str, Any]] = None,
) -> str:
    """可直接复制的替换件。英文文案给英文正文 + 中文说明，中文文案给中文。"""
    if _text_has_cjk(text):
        body = (
            "本产品为日常护理用品，非医疗器械，不能替代诊断或治疗；"
            "个体体验存在差异，请按说明书使用。"
        )
        lead = "（以下替换文案可直接贴回广告：）" if has_hits else "（以下免责贴条可直接补在广告页脚：）"
        return f"{lead}\n{body}"
    body = (
        "This product is a daily-care device, not a medical device. "
        "It does not diagnose, treat, cure, or prevent any disease. "
        "Individual results vary; please follow the user manual."
    )
    lead = "Copy-paste replacement:" if has_hits else "Copy-paste disclaimer:"
    hint = _safety_hint_for(pl_res or {}, product_line) or '该品线禁止医疗与绝对化表述。'
    note = f"（中文说明：{hint}）"
    return f"{lead}\n{body}\n{note}"


def _text_four_dim_deterministic(
    text: str,
    *,
    product_line: str,
    findings: List[Dict[str, Any]],
    pl_res: Dict[str, Any],
    label: str,
) -> Dict[str, Any]:
    """纯确定性四维（不联网）。离线、无凭据、模型失败时都用这一份。"""
    body = (text or "").strip()
    confirmed = [f for f in findings if isinstance(f, dict) and f.get("status") != "candidate"]

    literal_hits = [f for f in confirmed if str(f.get("control_code") or "") not in TEXT_CLAIM_CONTROL_CODES]
    claim_hits = [f for f in confirmed if str(f.get("control_code") or "") in TEXT_CLAIM_CONTROL_CODES]
    claim_words = _text_efficacy_hits(body)

    # ① 字面红线与医疗禁用词
    if literal_hits:
        codes = "、".join(sorted({str(f.get("control_code") or "规则") for f in literal_hits}))
        quotes = "、".join(f"「{str(f.get('quote') or '').strip()}」" for f in literal_hits[:3])
        literal_status = "有风险"
        literal_summary = f"命中 {codes}：{quotes}"
    else:
        literal_status = "正常"
        literal_summary = "未命中已知字面禁用与医疗红线词"

    # ② 功效与安全宣称
    claim_bits: List[str] = []
    if claim_hits:
        claim_bits.append("、".join(f"「{str(f.get('quote') or '').strip()}」" for f in claim_hits[:3]))
    if claim_words:
        claim_bits.append("、".join(claim_words[:3]))
    if claim_bits:
        claim_status = "有风险" if label == "BLOCK" else "需注意"
        claim_summary = f"出现{'；'.join(claim_bits)}——这类表述需要有来源或改成客观功能描述"
    else:
        claim_status = "正常"
        claim_summary = "未见明显夸大功效或安全承诺表述"

    # ③ 品线与平台特殊规范
    hint = _safety_hint_for(pl_res, product_line)
    pl_note = str(pl_res.get("note") or "").strip()
    platform_status = "需注意" if (claim_hits or claim_words) else "正常"
    platform_summary = "；".join(x for x in (pl_note, hint) if x) or "未触及平台特殊条款"

    # ④ 明细表
    if confirmed:
        region_rows = [
            {
                "region": _text_location_label(f),
                "issue": f"命中「{str(f.get('quote') or '').strip()}」（{str(f.get('control_code') or '规则')}）",
                "fix": f"删掉「{str(f.get('quote') or '').strip()}」或改为客观功能描述并补实测条件",
            }
            for f in confirmed[:5]
        ]
    elif claim_words:
        region_rows = [{
            "region": "全文·功效表述",
            "issue": f"字面规则未命中，但出现{'、'.join(claim_words[:3])}，语境仍需人工判断",
            "fix": "改为客观功能描述，并补一句不带疗效暗示的免责说明",
        }]
    else:
        region_rows = [{
            "region": "全文扫描",
            "issue": "未命中已知字面违规词",
            "fix": "转工作台人工复核语境后放行",
        }]

    total = len(confirmed)
    if total:
        overall = "发现违规需修改" if label == "BLOCK" else "需人工确认"
        one_line = f"文案含 {total} 处需改表述，触碰字面红线或功效承诺，需修改后再投放。"
        short_title = f"命中 {total} 处字面红线"
        quick_fix = "删掉或替换命中的表述，改为客观功能描述并补充实测条件说明。"
    else:
        # 空命中不是合规：它只说明这套规则没命中。所以结论一律落「需人工确认」，
        # 绝不产出「初筛未见违规」——那句话比输入大。
        overall = "需人工确认"
        one_line = ("未命中已知字面禁用词，但出现功效类表述，请人工确认语境。" if claim_words
                    else "未命中已知字面禁用词；空命中不等于合规，请人工确认语境。")
        short_title = "未见已知字面红线词" if not claim_words else "字面未命中但有效功效表述"
        quick_fix = ("把功效类表述改成客观功能描述，并补一句免责说明。" if claim_words
                     else "字面规则未命中不等于合规，转工作台人工复核语境。")

    return {
        "status": "ok",
        "media_kind": "text",
        "model": "deterministic",
        "overall": overall,
        "short_title": short_title,
        "one_line": one_line,
        "quick_fix": quick_fix,
        # 两套键名都写：字面维度用 literal_*，同时把同一句话挂到 ocr_* ——
        # JS 渲染器对文案读 literal_*，对手工构造的老数据读 ocr_*，两处都能出卡。
        "literal_status": literal_status, "literal_summary": literal_summary,
        "ocr_status": literal_status, "ocr_summary": literal_summary,
        "claim_status": claim_status, "claim_summary": claim_summary,
        "scene_status": claim_status, "scene_semantics": claim_summary,
        "platform_status": platform_status, "platform_summary": platform_summary,
        "symbol_status": platform_status, "visual_symbols": platform_summary,
        "region_rows": region_rows,
        "region_audit": [f"{r['region']}：{r['issue']} → {r['fix']}" for r in region_rows],
        "copy_paste_snippet": _text_snippet_for(body, product_line, bool(confirmed or claim_words), pl_res),
    }


def run_llm_text_four_dim_audit(
    text: str,
    *,
    product_line: str,
    findings: List[Dict[str, Any]],
    pl_res: Dict[str, Any],
    label: str = "REVIEW",
) -> Dict[str, Any]:
    """文案的四维体检。

    第一段是**确定性**的：只看引擎已经给出的 findings、品线解析与正文特征词，
    不联网、不要凭据，因此离线与模型故障时都拿得到完整四维。

    第二段是可选润色：`MULTIMODAL_VOD_API_TOKEN` 在场且正文够长时，请多模态网关
    把四句话写得更像人话（标题、卡点、怎么改、三维描述、明细行、替换件）。
    润色**任何一步失败整段丢弃**，回落第一段 —— 卡片不会因为模型挂了而消失，
    也不会因为模型编了而说错覆盖范围。
    """
    det = _text_four_dim_deterministic(
        text, product_line=product_line, findings=findings, pl_res=pl_res, label=label,
    )

    body = (text or "").strip()
    if not body or len(body) < 20:
        return det
    if not (os.environ.get("MULTIMODAL_VOD_API_TOKEN") or "").strip():
        return det
    if os.environ.get("SHOUHENG_TEXT_LLM_AUDIT") == "0":
        return det

    try:
        from tools.multimodal_client import GatewayClient

        model = (os.environ.get("MULTIMODAL_MODEL") or "").strip() or "gemini-3.1-flash-lite"
        client = GatewayClient.from_env("vod", model=model, timeout=35.0, retry_attempts=1)
        prompt = (
            "你是一名跨境电商与母婴广告合规审核员。下面是一段待审广告文案，"
            "已由规则引擎给出命中清单。请在此基础上写【文案四维体检】。\n"
            "输出必须全部讲大白话（适合 ADHD 3秒扫完，每点只写 1 句核心人话；"
            "关键违规词用「」括起来强调，严禁使用 *、**、`、# 等任何 Markdown 符号，严禁出现代码字段名）：\n"
            + OVERALL_RULE + "\n"
            f"品线：{_display_category_of(pl_res, product_line)}\n"
            f"引擎命中：{json.dumps([{ 'code': f.get('control_code'), 'quote': f.get('quote') } for f in findings[:8] if isinstance(f, dict)], ensure_ascii=False)}\n"
            f"正文：\n{body[:4000]}\n\n"
            "请严格输出一行 JSON（不要多余解释）：\n"
            "{\n"
            '  "overall": "发现违规需修改 或 需人工确认 或 初筛未见明显违规",\n'
            '  "short_title": "15字以内的直白核心问题标题",\n'
            '  "one_line": "42字以内的一句话核心卡点",\n'
            '  "quick_fix": "一句话直接告诉运营马上改哪两处",\n'
            '  "ocr_status": "有风险 或 需注意 或 正常",\n'
            '  "ocr_summary": "字面红线与医疗禁用词这一维看到了什么（1句话）",\n'
            '  "scene_status": "有风险 或 需注意 或 正常",\n'
            '  "scene_semantics": "功效与安全宣称这一维看到了什么（1句话）",\n'
            '  "symbol_status": "有风险 或 需注意 或 正常",\n'
            '  "visual_symbols": "品线与平台特殊规范这一维看到了什么（1句话）",\n'
            '  "region_rows": [\n'
            '    {"region": "第几段或字符区间", "issue": "命中的原句与问题", "fix": "建议替换写法"}\n'
            "  ],\n"
            '  "copy_paste_snippet": "可直接复制回广告的合规替换文案或免责贴条（英文文案给英文+中文说明，中文文案给中文）"\n'
            "}"
        )
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "temperature": 0,
        }, ensure_ascii=False).encode("utf-8")
        resp = client.transport(
            client.endpoint(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {client.api_key}"},
            payload,
            35.0,
        )
        if resp.status != 200 or not resp.body:
            return det
        body_obj = json.loads(resp.body)
        content_str = (
            ((body_obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        s_idx, e_idx = content_str.find("{"), content_str.rfind("}")
        if s_idx < 0 or e_idx <= s_idx:
            return det
        parsed = json.loads(content_str[s_idx:e_idx + 1])
        if not isinstance(parsed, dict) or not parsed.get("one_line"):
            return det

        raw_rows = parsed.get("region_rows")
        region_rows = []
        if isinstance(raw_rows, list):
            for r in raw_rows:
                if isinstance(r, dict) and (r.get("region") or r.get("issue")):
                    region_rows.append({
                        "region": str(r.get("region") or "全文").strip(),
                        "issue": str(r.get("issue") or "—").strip(),
                        "fix": str(r.get("fix") or "—").strip(),
                    })

        enriched = dict(det)
        for k in ("overall", "short_title", "one_line", "quick_fix",
                  "ocr_status", "ocr_summary", "scene_status", "scene_semantics",
                  "symbol_status", "visual_symbols", "copy_paste_snippet"):
            v = str(parsed.get(k) or "").strip()
            if v:
                enriched[k] = v
        if region_rows:
            enriched["region_rows"] = region_rows
            enriched["region_audit"] = [f"{r['region']}：{r['issue']} → {r['fix']}" for r in region_rows]
        # 字面维度与功效维度的两套键名保持一致，别让渲染器读到一份润色、一份确定性
        enriched["literal_status"], enriched["literal_summary"] = enriched["ocr_status"], enriched["ocr_summary"]
        enriched["claim_status"], enriched["claim_summary"] = enriched["scene_status"], enriched["scene_semantics"]
        enriched["platform_status"], enriched["platform_summary"] = enriched["symbol_status"], enriched["visual_symbols"]
        enriched["model"] = model
        enriched["status"] = "ok"
        # ★ 空证据不许被模型升级成拦截：标签不是 BLOCK、引擎零命中、正文也没有任何
        #   功效/安全特征词时，「发现违规需修改」没有任何输入支撑 —— 它比依据大。
        #   降成「需人工确认」而不是「初筛未见违规」：润色层没说它干净，我们只否掉最严那一档。
        confirmed_all = [f for f in findings if isinstance(f, dict) and f.get("status") != "candidate"]
        if (label != "BLOCK" and not confirmed_all and not _text_efficacy_hits(body)
                and str(enriched.get("overall") or "").startswith("发现违规")):
            enriched["overall"] = "需人工确认"
            enriched["overall_downgraded"] = (
                "引擎零命中且正文无功效特征词，润色层给的「发现违规需修改」无输入支撑，已降为需人工确认"
            )
        return enriched
    except Exception:  # noqa: BLE001
        return det


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
                    "label": AUDIT_FALLBACK_LABEL,
                    "layer": AUDIT_FALLBACK_LAYER,
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
                "label": AUDIT_FALLBACK_LABEL,
                "layer": AUDIT_FALLBACK_LAYER,
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
                "label": AUDIT_FALLBACK_LABEL,
                "layer": AUDIT_FALLBACK_LAYER,
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
                "label": AUDIT_FALLBACK_LABEL,
                "layer": AUDIT_FALLBACK_LAYER,
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
            "label": AUDIT_FALLBACK_LABEL,
            "layer": AUDIT_FALLBACK_LAYER,
            "release_status": "待放行",
            "parse_status": "failed",
            "failure_kind": "empty" if "empty" in exc.code or "0 字节" in exc.detail else "parse_error",
            "error": f"{exc.code}: {exc.detail}",
            "product_line_resolution": pl_res,
            "display_category": pl_res.get("display_category"),
            "stage_resolution": stage_res,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "contract_version": CONTRACT_VERSION,
            "carrier": carrier,
            "label": AUDIT_FALLBACK_LABEL,
            "layer": AUDIT_FALLBACK_LAYER,
            "release_status": "待放行",
            "parse_status": "failed",
            "failure_kind": "parse_error",
            "error": f"{type(exc).__name__}: {exc}",
            "product_line_resolution": pl_res,
            "display_category": pl_res.get("display_category"),
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
            # 桥接层不改写引擎标签（J1：判定逻辑只在 decision_table）。
            # VLM 的更严结论降为 four_dim_audit 上的建议标记，随卡片呈现，供人工复核采纳。
            four_dim_audit["overall"] = "发现违规需修改（VLM 建议，机器初筛为需人工确认）"
    elif carrier == "video" and file_path:
        four_dim_audit = run_vlm_video_four_dim_audit(Path(file_path).expanduser().resolve())
        if four_dim_audit and four_dim_audit.get("overall") == "发现违规需修改" and label == "REVIEW":
            # 桥接层不改写引擎标签（J1）：VLM 更严结论降为建议标记，随卡片呈现
            four_dim_audit["overall"] = "发现违规需修改（VLM 建议，机器初筛为需人工确认）"
    elif carrier in TEXT_CARRIERS:
        # 文案也要有自己的四维：字面红线 / 功效与安全宣称 / 品线与平台规范 / 明细表。
        # 确定性那一段永远可用；润色那一段失败就整段丢掉（见 run_llm_text_four_dim_audit）。
        four_dim_audit = run_llm_text_four_dim_audit(
            unit.get("text") or (submission.get("text") or ""),
            product_line=resolved_pl,
            findings=confirmed_findings,
            pl_res=pl_res,
            label=label,
        )

    # ★ 权威结论行：只有图片/视频有四维抬头时才改写成【<模态>审查：…】。
    #   文案**保持** `【审查结论：{label}】…（案件 {case_id}）。` —— 那条是
    #   `buildGuardVerdict` 的同款形状，`feishu_guard_ingest.test.mjs` 的 G3 与
    #   `tools.mjs` 的 pendingTurnVerdict 都按它对齐；文案卡的模态抬头由卡片 title 承担。
    if four_dim_audit and four_dim_audit.get("short_title") and carrier in ("image", "video"):
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
        "display_category": pl_res.get("display_category"),
        "content_stage": submission.get("content_stage"),
        "stage_resolution": stage_res,
        "extracted_text": (unit.get("text") or "")[:4000],
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


def _precedent_row_exists(queue_path: Path, case_id: str) -> Optional[bool]:
    """队列里有没有这个案件的判例回流行。

    ★ 返回 `Optional[bool]`：`None` 是**未测**（队列读不出来 / 有坏行），
      与 `False`（读出来了、确实没有）必须分得开 —— 前者我不能说「没入队」。
    """
    try:
        if not queue_path.exists():
            return False
        bad = 0
        for line in queue_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(rec, dict) and rec.get("case_id") == case_id:
                return True
        return None if bad else False
    except OSError:
        return None


def execute_thread_review(
    *,
    case_id: str,
    action: str,
    notes: str = "",
    actor_id: str = "",
    tenant: str = DEFAULT_TENANT,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """群里对某条审查卡回一句「确认放行 / 误报推翻」，就地把它落到权威与判例回流。

    ## 为什么要在群里做这件事

    审查卡已经带着单号发进群了。复核员看见「这条误报」，最自然的动作是在那条卡下
    回一句 —— 而不是切到工作台、找到单号、点三下。今天这条路径**不存在**：
    群里说什么都不改变案件状态，复核员只能去工作台。

    ## action 三态，映射到 reducer 真实认识的 verdict

    reducer 里 `review_and_close` 的 `verdict` **只有两个值**（`agree` / `overturn`），
    语义是「我认不认机器给的判定」。所以：

        confirm  → agree      认可机器结论并结案
        overturn → overturn   推翻（≠ 机器结论 → 由 ReviewCommandService 写进判例回流队列）
        revise   → 不调 review_and_close，返回「要改内容」的路径提示

    ★ `revise` **刻意不做一个看起来像成功的写**：「要求修改」在这套权威里是
      `submit_review` + `conclusion.verdict_choice=revise` 的形状，需要一个已认领的
      草稿态。在本函数里硬凑一个，会产出「命令说成功、案件状态却停在原处」——
      比明确拒绝更糟。所以它如实返回一条**可执行的替代路径**。

    ## 零副作用

    `data_root` 不给时走 `workbench_data_root()`（生产）；测试给临时目录。
    判例回流队列同理：给了 `data_root` 就落在它下面，**不进仓**
    （`research/governance/_evidence/` 是被跟踪的真实队列，自证不许往里写，§2.4.4）。
    """
    cid = str(case_id or "").strip()
    if not cid:
        return {"ok": False, "error": "缺少 case_id"}
    act = str(action or "").strip().lower()
    if act not in ("confirm", "overturn", "revise"):
        return {"ok": False, "error": f"不认识的复核动作 {action!r}；只接受 confirm / overturn / revise"}
    notes_txt = str(notes or "").strip()
    if act in ("overturn",) and not notes_txt:
        # 推翻机器结论必须留下理由 —— 它是判例回流里唯一能被人读懂的那部分。
        return {"ok": False, "error": "推翻机器结论必须写理由（── 例如「这是引用反例说明，不是我们的宣称」）"}

    root = data_root if data_root is not None else workbench_data_root()
    authority_dir = root / "authority"
    projection_db = root / "db" / "review.db"
    if not authority_dir.exists():
        return {"ok": False, "error": f"工作台权威目录不存在（{authority_dir}）—— 还没建过任何案件"}
    authority_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    projection_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    lease = WriterLease(authority_dir / "writer.lock")
    try:
        lease.acquire()
        authority = BusinessEventStore(authority_dir, lease=lease)
        projection = ProjectionStore(projection_db)
        # ★ 判例回流队列跟着 `data_root` 走。
        #   `ReviewCommandService` 不给 feedback_queue 时**根本不记判例**
        #   （见它对 None 的处理），所以这里必须显式给一个；
        #   给的路径必须是**这个 data_root 之下**，否则自证会往仓里那份
        #   被跟踪的真实队列追加行 —— 跑一次测试改一次生产数据（§2.4.4）。
        feedback_queue = root / "review_feedback_queue.jsonl"
        service = ReviewCommandService(authority, projection, feedback_queue=feedback_queue)

        state = authority.state(cid)
        if not isinstance(state, dict) or not state.get("case_id"):
            return {"ok": False, "not_found": True,
                    "error": f"未找到案件 {cid} —— 权威事件流里没有这个单号（核对单号是否完整）"}
        version = int(state.get("version") or 0)
        if version < 1:
            return {"ok": False, "not_found": True,
                    "error": f"案件 {cid} 还没进过任何版本（版本 {version}），不能复核"}
        if act == "revise":
            return {
                "ok": False, "needs_workbench": True, "case_id": cid,
                "error": "「要求修改」要先把内容改完再重新送审，群里这一句改不了正文。",
                "next_step": f"去工作台把单号 {cid} 领单并写修改意见；改完之后重新发一条送审即可建新单。",
            }

        if state.get("status") == "closed":
            return {"ok": False, "already_closed": True,
                    "error": f"案件 {cid} 已结案（版本 {version}）—— 再结一次没有意义"}

        principal = {
            "id": (actor_id or "feishu:guard").strip() or "feishu:guard",
            "tenant": tenant,
            "roles": ["submitter", "dp3"],
            "product_lines": list(VALID_PRODUCT_LINES),
        }
        verdict = "agree" if act == "confirm" else "overturn"
        # 幂等键必须**跟着动作走**：同一版本上用同一个键重放不重复写，
        # 但 confirm 与 overturn 是两个不同的决定，共用一个键会让第二个被当成重放。
        idem = f"thread-review:{cid}:v{version}:{act}"

        out = service.execute(
            aggregate_id=cid,
            command="review_and_close",
            actor={"principal_id": principal["id"], "tenant_id": principal["tenant"]},
            expected_version=version,
            payload={"verdict": verdict, "review_notes": notes_txt or "群内话题复核"},
            idempotency_key=idem,
        )
        result = (out or {}).get("result") or {}
        # ★ `_record_precedent_after` 的返回值**没有**挂回 response（见它的注释：
        #   永不抛、不回滚权威、不改 http_status）。所以这里不能读 `result["precedent"]`
        #   然后报「没入队」—— 那是把「我没读到」说成「没有」。
        #   判据改成**直接回读队列**：这个 case 的 formal 记录在不在里面。
        queued = _precedent_row_exists(root / "review_feedback_queue.jsonl", cid)
        return {
            "ok": True,
            "case_id": cid,
            "action": act,
            "verdict": verdict,
            "from_version": version,
            "to_version": result.get("version"),
            "status": result.get("status") or "closed",
            "release_status": (result.get("release") or {}).get("status"),
            # 判例回流：读**队列本身**，不读命令的返回值（见上一条注释）。
            # 三种情形必须分得开：入了 / 本来就不该入 / 队列读不出来（未测）。
            "precedent": {
                "queued": queued,
                "queue_path": str(root / "review_feedback_queue.jsonl"),
            },
            "workbench_data_root": str(root),
        }
    except Exception as exc:  # noqa: BLE001
        # 这里不吞类型：读的人要能分清「案件状态冲突」与「我这侧崩了」。
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            lease.release()
        except Exception:  # noqa: BLE001
            pass


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
    p.add_argument("--extract-office", metavar="PATH",
                   help="只抽取 .docx/.xlsx 正文并以 JSON 打印（不建案、不判审）")
    p.add_argument("--review-case", metavar="CASE_ID",
                   help="对已建案件执行一次人工复核结案（配合 --review-action）")
    p.add_argument("--review-action", choices=("confirm", "overturn", "revise"),
                   help="confirm=认可机器结论 / overturn=推翻（记误报判例）/ revise=要求修改（漏报回流）")
    p.add_argument("--review-notes", default="", help="复核说明（进权威与判例回流）")

    args = p.parse_args(argv)

    if args.extract_office:
        print(json.dumps(extract_office_attachment_text(Path(args.extract_office)), ensure_ascii=False))
        return 0

    if args.review_case:
        if not args.review_action:
            print(json.dumps({"ok": False, "error": "给了 --review-case 就必须给 --review-action"}, ensure_ascii=False))
            return 1
        rres = execute_thread_review(
            case_id=args.review_case,
            action=args.review_action,
            notes=args.review_notes or "",
            actor_id=args.sender_open_id or "",
        )
        print(json.dumps(rres, ensure_ascii=False))
        return 0 if rres.get("ok") else 1

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
