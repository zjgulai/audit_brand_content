#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/normalizer.py — T1-02：normalizer（ContentUnit v1）

唯一归一化点：
- **只产 ContentUnit**（`contract_version=content-unit-v1`），不产 ReviewIR；
- builder、unit_id、content_key、双指纹全部复用 `base/contract.py`，
  本文件不新造 builder、不重算 unit_id；
- `covers` / `does_not_cover` 是**必填参数，没有默认值**：缺参数直接 TypeError，
  空 covers / 非 list 直接 ValueError；
- `parse_status ∈ {ok, partial, failed}`：
    ok      → 可进判定、可 PASS
    partial → 可进判定、**永不 PASS**
    failed  → 不产正文、不进判定、无 ir_id；由上层回退到 Attempt 语义
- failed 必须带四种 `failure_kind` 之一与非禁用 `reason`。

边界：不判定、不产 finding、不算 coverage_state、不组装/落盘 ReviewIR。
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from base import contract as C  # noqa: E402

# ContentUnit schema 的 12 个 required 字段（reference_verdict 是可选第 13 个）。
REQUIRED_UNIT_FIELDS = (
    "contract_version",
    "unit_id",
    "content_key",
    "source",
    "fingerprint",
    "normalization",
    "composition",
    "textification",
    "text",
    "has_text",
    "routing",
    "context",
)

PARSE_STATUSES = ("ok", "partial", "failed")
FAILURE_KINDS = C.FAILURE_KINDS
BANNED_REASONS = ("其他", "其他错误", "未知", "未知错误")
REVIEW_IR_FIELDS = ("findings", "decision", "coverage_state", "ir_id")

# C-21：统一 location 契约（contracts/location-v1.schema.json）
LOCATION_KINDS = ("text_span", "image_region", "video_timecode")
ASR_NO_TIMECODE_GAP = "ASR 无逐句时间码：字幕类位置不可用（D14）"


def _num(v):
    return type(v) in (int, float) and v == v and abs(v) != float("inf")


def _tenth_ok(v):
    """时间精度到 0.1 秒：1.23 这类超精度值拒绝。"""
    return _num(v) and abs(round(v * 10) - v * 10) <= 1e-9


def _bbox_canonical(bbox):
    """旧对象 {x,y,w,h} → 规范数组 [x1,y1,x2,y2]；数组原样返回。

    只转换键恰好是 x/y/w/h 且全为数字的对象；坏对象留给校验器报错，
    避免在「归一化」这一步把非法输入悄悄变成合法输入。
    """
    if isinstance(bbox, dict) and set(bbox) == {"x", "y", "w", "h"} \
            and all(_num(bbox[k]) for k in ("x", "y", "w", "h")):
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        return [round(x, 12), round(y, 12), round(x + w, 12), round(y + h, 12)]
    return bbox


def _bbox_problems(bbox):
    """bbox 的规范形状是 [x1,y1,x2,y2]；旧对象由 _bbox_canonical 先转。"""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return ["bbox 必须是长度 4 的数组 [x1,y1,x2,y2]"]
    if not all(_num(v) for v in bbox):
        return ["bbox 的四个值必须都是数字"]
    x1, y1, x2, y2 = bbox
    p = []
    if not (0 <= x1 < x2 <= 1):
        p.append("bbox 必须满足 0 <= x1 < x2 <= 1")
    if not (0 <= y1 < y2 <= 1):
        p.append("bbox 必须满足 0 <= y1 < y2 <= 1")
    return p


def frame_no_for(time_start, offset_seconds=0.0, interval_seconds=1.0):
    """抽帧帧号：round((time_start - offset) / interval)。采样参数由回执提供。"""
    return int(round((time_start - offset_seconds) / interval_seconds))


def _canonical_location(loc, text):
    if not isinstance(loc, dict):
        return loc
    out = dict(loc)
    kind = out.get("kind")
    if kind in ("image_region", "video_timecode") and "bbox" in out:
        out["bbox"] = _bbox_canonical(out["bbox"])
    if kind == "text_span" and "quote" not in out:
        st, en = out.get("start"), out.get("end")
        if type(st) is int and type(en) is int and 0 <= st < en <= len(text):
            out["quote"] = text[st:en]
    return out


def _location_problems(text, locations, frame_sampling=None):
    """校验 ContentUnit.locations；返回问题清单（空 = 合法）。

    `frame_sampling` 来自回执：{"interval_seconds": >0, "offset_seconds": >=0}。
    有它时才独立复算 frame_no；没有时不假装复算过。
    """
    if locations is None:
        return []
    if not isinstance(locations, list):
        return ["locations 必须是数组"]
    p = []
    if frame_sampling is not None and not isinstance(frame_sampling, dict):
        p.append("frame_sampling 必须是对象 {interval_seconds, offset_seconds}")
    n = len(text) if isinstance(text, str) else 0
    for i, loc in enumerate(locations):
        tag = "locations[%d]" % i
        if not isinstance(loc, dict):
            p.append("%s 不是对象（自然语言位置必须拒绝）" % tag)
            continue
        kind = loc.get("kind")
        if kind not in LOCATION_KINDS:
            p.append("%s.kind=%r 不在 %r" % (tag, kind, LOCATION_KINDS))
            continue
        allowed = {
            "text_span": {"kind", "start", "end", "quote"},
            "image_region": {"kind", "image_id", "frame_ref", "frame_thumb", "bbox"},
            "video_timecode": {"kind", "video_id", "time_start", "time_end",
                               "frame_no", "frame_thumb", "bbox"},
        }[kind]
        extra = set(loc) - allowed
        if extra:
            p.append("%s 多出字段 %r" % (tag, sorted(extra)))
        if kind == "text_span":
            st, en = loc.get("start"), loc.get("end")
            if type(st) is not int or type(en) is not int:
                p.append("%s start/end 必须是整数" % tag)
            elif not (0 <= st < en <= n):
                p.append("%s 文本区间越界/为空：%r..%r（len=%d）" % (tag, st, en, n))
            else:
                quote = loc.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    p.append("%s.quote 必须是非空字符串" % tag)
                elif quote != text[st:en]:
                    p.append("%s.quote 必须等于 text[start:end]：%r != %r"
                             % (tag, quote, text[st:en]))
        elif kind == "image_region":
            if not isinstance(loc.get("image_id"), str) or not loc["image_id"].strip():
                p.append("%s.image_id 必须是非空字符串" % tag)
            if "frame_ref" in loc and not isinstance(loc["frame_ref"], str):
                p.append("%s.frame_ref 必须是字符串" % tag)
            if "frame_thumb" in loc and (not isinstance(loc["frame_thumb"], str)
                                         or not loc["frame_thumb"].strip()):
                p.append("%s.frame_thumb 必须是非空字符串" % tag)
            p.extend("%s.%s" % (tag, x) for x in _bbox_problems(loc.get("bbox")))
        else:
            if not isinstance(loc.get("video_id"), str) or not loc["video_id"].strip():
                p.append("%s.video_id 必须是非空字符串" % tag)
            ts, te = loc.get("time_start"), loc.get("time_end")
            if not _num(ts) or not _num(te) or not (0 <= ts <= te):
                p.append("%s time_start/time_end 必须满足 0 <= start <= end" % tag)
            elif not (_tenth_ok(ts) and _tenth_ok(te)):
                p.append("%s time_start/time_end 精度必须到 0.1 秒" % tag)
            fn = loc.get("frame_no")
            if type(fn) is not int or fn < 0:
                p.append("%s.frame_no 必须是非负整数" % tag)
            if not isinstance(loc.get("frame_thumb"), str) or not loc["frame_thumb"].strip():
                p.append("%s.frame_thumb 必须是非空字符串" % tag)
            if "bbox" in loc:
                p.extend("%s.%s" % (tag, x) for x in _bbox_problems(loc.get("bbox")))
            if isinstance(frame_sampling, dict) and _num(ts):
                iv = frame_sampling.get("interval_seconds")
                off = frame_sampling.get("offset_seconds", 0.0)
                if not _num(iv) or iv <= 0:
                    p.append("%s.frame_sampling.interval_seconds 必须 > 0" % tag)
                elif not _num(off) or off < 0:
                    p.append("%s.frame_sampling.offset_seconds 必须 >= 0" % tag)
                elif type(fn) is int and fn != frame_no_for(ts, off, iv):
                    p.append("%s.frame_no 与抽帧参数不一致：%r != round((%r-%r)/%r)=%r"
                             % (tag, fn, ts, off, iv, frame_no_for(ts, off, iv)))
    return p


def _derive_locations(raw, unit):
    """唯一组装点：显式 locations 规范化；文本类无显式值时由 composition.parts 派生。"""
    if unit.get("parse_status") == "failed":
        return []
    text = unit.get("text") if isinstance(unit.get("text"), str) else ""
    explicit = raw.get("locations")
    if explicit is not None:
        return ([_canonical_location(x, text) for x in explicit]
                if isinstance(explicit, list) else explicit)
    kind = (unit.get("source") or {}).get("kind")
    # ★ contract.from_ad_record 的 source.kind 是 `ad_text`（见 base/contract.py:459），
    #   不是 raw_input 的 `ad_record`。原先这里写 `ad_record`，ad 记录的
    #   locations 永远派生不出来 —— 文本类判据默默漏掉了一个模态。
    if kind in ("free_text", "ad_text", "landing_page", "structured_json"):
        parts = (unit.get("composition") or {}).get("parts") or []
        return [{"kind": "text_span", "start": p["start"], "end": p["end"],
                 "quote": text[p["start"]:p["end"]]}
                for p in parts if isinstance(p, dict)
                and isinstance(p.get("start"), int) and isinstance(p.get("end"), int)
                and 0 <= p["start"] < p["end"] <= len(text)]
    return []


def _coverage_problems(covers, does_not_cover):
    p = []
    if not isinstance(covers, list) or not covers:
        p.append("covers 必须是非空 list（没有默认值）")
    elif not all(isinstance(x, str) and x.strip() for x in covers):
        p.append("covers 的每一项都必须是非空字符串")
    if not isinstance(does_not_cover, list):
        p.append("does_not_cover 必须是 list（没有默认值；可以为空 list）")
    elif not all(isinstance(x, str) and x.strip() for x in does_not_cover):
        p.append("does_not_cover 的每一项都必须是非空字符串")
    return p


def _reason_problem(reason):
    if not isinstance(reason, str) or not reason.strip():
        return "failed 的 reason 必须是非空字符串"
    rs = reason.strip()
    if rs in BANNED_REASONS or "未知错误" in rs:
        return "reason 不许写「其他 / 未知错误」这类无信息词：%r" % reason
    return None


def _uri(raw):
    return raw.get("uri") or "inline:normalizer"


def _build(raw, covers, does_not_cover):
    """调用 contract.py 的既有 builder（不新造、不重算 id）。"""
    kind = raw.get("kind")
    if kind == "free_text":
        return C.from_text(raw.get("text") or "", uri=_uri(raw),
                           raw_bytes=raw.get("raw_bytes"))
    if kind == "ad_record":
        return C.from_ad_record(raw.get("record") or {}, uri=raw.get("uri"))
    if kind in ("landing_page", "structured_json"):
        fetch = raw.get("fetch")
        if not isinstance(fetch, dict):
            raise ValueError("%s 需要 raw_input.fetch" % kind)
        label = "structured" if kind == "structured_json" else raw.get("label", "html")
        return C.from_landing_page(
            fetch, raw.get("extract"), label=label,
            evidence_dir=raw.get("evidence_dir"), uri=raw.get("uri"))
    if kind in ("image", "video"):
        return C.from_media(
            kind, raw.get("raw") or b"", raw.get("text_from_media") or "",
            uri=_uri(raw), extractor=raw.get("extractor") or "normalizer",
            covers=covers, does_not_cover=does_not_cover)
    raise ValueError("不认识的 raw_input.kind=%r" % (kind,))


def _build_empty(raw, covers, does_not_cover):
    """failed 专用：用同一 builder 的空正文形态，保证 unit_id/指纹自洽。"""
    kind = raw.get("kind")
    if kind == "free_text":
        raw_bytes = raw.get("raw_bytes")
        if raw_bytes is None:
            raw_bytes = (raw.get("text") or "").encode("utf-8")
        return C.from_text("", uri=_uri(raw), raw_bytes=raw_bytes)
    if kind == "ad_record":
        return C.from_ad_record({"Primary Text": "", "Headline": ""},
                                uri=raw.get("uri"))
    if kind in ("landing_page", "structured_json"):
        fetch = raw.get("fetch")
        if not isinstance(fetch, dict):
            raise ValueError("%s 需要 raw_input.fetch" % kind)
        label = "structured" if kind == "structured_json" else raw.get("label", "html")
        empty_extract = {
            "html": {"body_text": ""},
            "structured": {"title": "", "description_text": ""},
        }
        return C.from_landing_page(
            fetch, empty_extract, label=label,
            evidence_dir=raw.get("evidence_dir"), uri=raw.get("uri"))
    if kind in ("image", "video"):
        return C.from_media(
            kind, raw.get("raw") or b"", "",
            uri=_uri(raw), extractor=raw.get("extractor") or "normalizer",
            covers=covers, does_not_cover=does_not_cover)
    raise ValueError("不认识的 raw_input.kind=%r" % (kind,))


def _apply_coverage(unit, covers, does_not_cover):
    textification = unit.get("textification")
    if not isinstance(textification, dict):
        textification = {}
    textification["covers"] = list(covers)
    textification["does_not_cover"] = list(does_not_cover)
    unit["textification"] = textification


def validate_unit(unit, frame_sampling=None):
    """ContentUnit + normalizer 语义校验；返回问题清单，空 = 合法。"""
    if not isinstance(unit, dict):
        return ["ContentUnit 必须是 dict，收到 %s" % type(unit).__name__]

    p = []
    missing = [k for k in REQUIRED_UNIT_FIELDS if k not in unit]
    if missing:
        p.append("缺少 required 字段 %r" % (missing,))
    leaked = [k for k in REVIEW_IR_FIELDS if k in unit]
    if leaked:
        p.append("ContentUnit 不许出现 ReviewIR 字段 %r" % (leaked,))

    p.extend("contract: " + x for x in C.validate(unit))

    status = unit.get("parse_status")
    if status not in PARSE_STATUSES:
        p.append("parse_status=%r 不在取值域 %r" % (status, PARSE_STATUSES))

    fp = unit.get("fingerprint") or {}
    text = unit.get("text")
    if isinstance(text, str):
        if fp.get("text_sha256") != C.sha256_text(text):
            p.append("text_sha256 != sha256(text)")
        if fp.get("text_chars") != len(text):
            p.append("text_chars=%r != len(text)=%d"
                     % (fp.get("text_chars"), len(text)))

    failure_kind = unit.get("failure_kind")
    if status == "failed":
        if failure_kind not in FAILURE_KINDS:
            p.append("failed 必须带 failure_kind ∈ %r，收到 %r"
                     % (FAILURE_KINDS, failure_kind))
        if text != "":
            p.append("failed 不许产出正文（text=%r）" % (text,))
        if unit.get("has_text") is not False:
            p.append("failed 的 has_text 必须为 False")
        reason_problem = _reason_problem(unit.get("reason"))
        if reason_problem:
            p.append(reason_problem)
    elif status in ("ok", "partial"):
        if "failure_kind" in unit:
            p.append("%s 不许带 failure_kind" % status)
        if not isinstance(text, str) or not text.strip():
            p.append("%s 必须有非空正文；没有正文应落 failed/empty" % status)
        if status == "partial":
            # 判定层必须能看见「仅已覆盖部分可判」；normalizer 只给状态，不判 PASS。
            pass

    if "locations" in unit:
        p.extend(_location_problems(text if isinstance(text, str) else "",
                                    unit.get("locations"),
                                    frame_sampling=frame_sampling))

    textification = unit.get("textification")
    if not isinstance(textification, dict):
        p.append("textification 必须是 dict（covers/does_not_cover 的既有位置）")
    else:
        covers = textification.get("covers")
        dnc = textification.get("does_not_cover")
        if not isinstance(covers, list) or not covers:
            p.append("textification.covers 必须是非空 list")
        if not isinstance(dnc, list):
            p.append("textification.does_not_cover 必须是 list")
    return p


def judgment_gate(unit):
    """判定入口闸：failed 不进；partial 进但永不 PASS。"""
    status = unit.get("parse_status")
    if status == "failed":
        return {"enter": False, "can_pass": False,
                "reason": "parse_status=failed → 未审查/DP0"}
    if status == "partial":
        return {"enter": True, "can_pass": False,
                "reason": "partial：只判已覆盖部分，永不 PASS"}
    if status == "ok":
        return {"enter": True, "can_pass": True, "reason": ""}
    raise ValueError("parse_status=%r 不在取值域 %r" % (status, PARSE_STATUSES))


def attempt_hint(unit):
    """failed 的 Attempt 语义只读视图；真正写 Attempt 的仍是 submission_router。"""
    if unit.get("parse_status") != "failed":
        return None
    outcome = ("rejected_unsupported"
               if unit.get("failure_kind") == "unsupported" else "failed")
    return {
        "outcome": outcome,
        "failure_kind": unit.get("failure_kind"),
        "reason": unit.get("reason"),
    }


def normalize(raw_input, *, covers, does_not_cover, parse_status="ok",
              failure_kind=None, reason=None):
    """把一个受支持的 raw_input 归一化为 ContentUnit v1。

    ★ covers / does_not_cover 没有默认值：调用方必须显式给出。
    """
    if not isinstance(raw_input, dict):
        raise ValueError("raw_input 必须是 dict")
    coverage = _coverage_problems(covers, does_not_cover)
    if coverage:
        raise ValueError("；".join(coverage))
    if parse_status not in PARSE_STATUSES:
        raise ValueError("parse_status=%r 不在取值域 %r"
                         % (parse_status, PARSE_STATUSES))

    if parse_status == "failed":
        if failure_kind not in FAILURE_KINDS:
            raise ValueError("failed 必须带 failure_kind ∈ %r，收到 %r"
                             % (FAILURE_KINDS, failure_kind))
        reason_problem = _reason_problem(reason)
        if reason_problem:
            raise ValueError(reason_problem)
        unit = _build_empty(raw_input, covers, does_not_cover)
        unit["parse_status"] = "failed"
        unit["failure_kind"] = failure_kind
        unit["reason"] = reason.strip()
    else:
        if failure_kind is not None:
            raise ValueError("%s 不许带 failure_kind" % parse_status)
        if reason is not None:
            raise ValueError("reason 只用于 failed；%s 不许带 reason" % parse_status)
        unit = _build(raw_input, covers, does_not_cover)
        unit["parse_status"] = parse_status
        if not unit.get("text", "").strip():
            raise ValueError("%s 必须有非空正文；没有正文应落 failed/empty"
                             % parse_status)

    dnc = list(does_not_cover)
    asr = raw_input.get("asr")
    if isinstance(asr, dict) and not asr.get("timecodes"):
        if ASR_NO_TIMECODE_GAP not in dnc:
            dnc.append(ASR_NO_TIMECODE_GAP)

    _apply_coverage(unit, covers, dnc)
    unit["locations"] = _derive_locations(raw_input, unit)
    problems = validate_unit(unit, frame_sampling=raw_input.get("frame_sampling"))
    if problems:
        raise ValueError("ContentUnit 不合法：\n  - " + "\n  - ".join(problems))
    return unit
