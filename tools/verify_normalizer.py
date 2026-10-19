#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_normalizer.py — T1-02：normalizer / ContentUnit v1

覆盖：
  C0  ContentUnit 12 个 required 字段 + 双指纹；parse_status/failure_kind 域
  C1  free_text ok：复用 contract builder、unit_id/content_key 不重算
  C2  ad_record / image：同样复用 contract builder
  C3  partial：可进判定，但 can_pass=False（永不 PASS）
  C4  failed 四种 failure_kind：不产正文、不进判定、无 ir_id
  C5  covers / does_not_cover 必填且无默认值（缺失/空 covers 必拒）
  C6  parse_status / failure_kind / reason 合法性
  C7  text_sha256 == sha256(text)，text_chars == len(text)
  C8  同输入两次 unit_id 相同；新进程 + 全新 pycache 仍相同
  C9  只产 ContentUnit，不产 ReviewIR（findings/decision/coverage_state/ir_id 必拒）
  R1  删掉 covers 默认补齐 → 红（C5 缺失参数用例）
  R2  failed 产出正文 → 红（C4）
  R3  text_sha256 与 sha256(text) 脱钩 → 红（C7）
  R4  同输入两次 unit_id 不同 → 红（C8）

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import json
import copy
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base import contract as C
    from base import normalizer as N
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.contract / base.normalizer: %s" % exc)
    sys.exit(2)

# ★ 独立字面量，不从 contract/normalizer 取值：后者可能互为别名（自比）。
EXPECTED_PARSE_STATUSES = ("ok", "partial", "failed")
EXPECTED_FAILURE_KINDS = ("fetch_error", "parse_error", "empty", "unsupported")


def free_raw(text="FDA approved wearable breast pump", uri="inline:test"):
    return {"kind": "free_text", "text": text, "uri": uri}


def landing_raw(label="html"):
    attempt_label = "structured" if label == "structured" else "html"
    kind = "structured_json" if label == "structured" else "landing_page"
    return {
        "kind": kind,
        "fetch": {
            "url_key": "lp-test-1",
            "url": "https://example.test/page",
            "attempts": [{
                "label": attempt_label, "sha256": "a" * 64,
                "bytes": 10, "target": "https://example.test/page",
                "status": 200,
            }],
        },
        "extract": ({"structured": {"title": "标题", "description_text": "描述"}}
                    if label == "structured"
                    else {"html": {"body_text": "页面正文"}}),
        "uri": "file:lp-test",
    }


def failed_modal_raws():
    """failed 空正文分支：每种模态都要真的走到 _build_empty。"""
    loc = [{"kind": "image_region",
            "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}]
    return {
        "ad_record": {"kind": "ad_record", "uri": "file:ad",
                      "record": {"Primary Text": "A", "Headline": "B"},
                      "locations": loc},
        "landing_page": dict(landing_raw("html"), locations=loc),
        "structured_json": dict(landing_raw("structured"), locations=loc),
        "image": {"kind": "image", "raw": b"img", "uri": "file:img",
                  "locations": loc},
        "video": {"kind": "video", "raw": b"vid", "uri": "file:vid",
                  "locations": loc},
    }


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    def norm(raw, covers=("正文",), dnc=(), status="ok", fk=None, reason=None):
        return N.normalize(raw, covers=list(covers), does_not_cover=list(dnc),
                           parse_status=status, failure_kind=fk, reason=reason)

    # C0 schema 12 required + 双指纹域
    schema = json.loads(open(
        os.path.join(REPO_ROOT, "base", "content-unit-v1.schema.json"),
        encoding="utf-8").read())
    required = tuple(schema.get("required") or [])
    report(len(required) == 12
           and set(required) == set(N.REQUIRED_UNIT_FIELDS)
           and len(N.REQUIRED_UNIT_FIELDS) == 12,
           "C0 ContentUnit 12 个 required 字段", repr(N.REQUIRED_UNIT_FIELDS))
    report(tuple(N.PARSE_STATUSES) == EXPECTED_PARSE_STATUSES
           and set(N.FAILURE_KINDS) == set(EXPECTED_FAILURE_KINDS)
           and len(N.FAILURE_KINDS) == len(EXPECTED_FAILURE_KINDS),
           "C0 parse_status / failure_kind 取值域（独立字面量对拍）",
           "%r %r" % (N.PARSE_STATUSES, N.FAILURE_KINDS))

    # C1 free_text ok
    raw = free_raw()
    u = norm(raw, covers=["调用方给出的正文"], dnc=[])
    report(u.get("parse_status") == "ok" and not N.validate_unit(u),
           "C1 free_text ok 合法", repr(N.validate_unit(u)))
    report(set(required) <= set(u), "C1 12 个 required 字段都在", repr(sorted(set(required) - set(u))))
    report(u["textification"]["covers"] == ["调用方给出的正文"]
           and u["textification"]["does_not_cover"] == [],
           "C1 covers/does_not_cover 使用显式值（不是 builder 默认）",
           repr(u.get("textification")))
    expected = C.from_text(raw["text"], uri=raw["uri"])
    report(u["unit_id"] == expected["unit_id"]
           and u["content_key"] == expected["content_key"],
           "C1 复用 contract builder，unit_id/content_key 不重算",
           "%s vs %s" % (u["unit_id"], expected["unit_id"]))
    gate = N.judgment_gate(u)
    report(gate.get("enter") is True and gate.get("can_pass") is True,
           "C1 ok 可进判定且可 PASS", repr(gate))

    # C2 ad_record / image 复用 builder
    rec = {"Primary Text": "A", "Headline": "B", "外部广告ID": "ad-1"}
    u_ad = N.normalize({"kind": "ad_record", "record": rec},
                       covers=["广告文案字段"], does_not_cover=["图内文字"])
    exp_ad = C.from_ad_record(rec)
    report(u_ad["unit_id"] == exp_ad["unit_id"]
           and u_ad["textification"]["covers"] == ["广告文案字段"],
           "C2 ad_record 复用 builder", "%s vs %s" % (u_ad["unit_id"], exp_ad["unit_id"]))

    media_raw = b"image-bytes"
    u_img = N.normalize({
        "kind": "image", "raw": media_raw, "text_from_media": "OCR 正文",
        "uri": "file:img", "extractor": "ocr-v1",
    }, covers=["图内文字"], does_not_cover=["画面语义"])
    exp_img = C.from_media(
        "image", media_raw, "OCR 正文", uri="file:img", extractor="ocr-v1",
        covers=["图内文字"], does_not_cover=["画面语义"])
    report(u_img["unit_id"] == exp_img["unit_id"],
           "C2 image 复用 builder", "%s vs %s" % (u_img["unit_id"], exp_img["unit_id"]))

    # C2a 文本类三种模态都必须从 composition.parts 派生 text_span。
    def has_valid_text_spans(unit):
        text = unit.get("text") or ""
        return bool(unit.get("locations")) and all(
            x.get("kind") == "text_span"
            and type(x.get("start")) is int and type(x.get("end")) is int
            and 0 <= x["start"] < x["end"] <= len(text)
            for x in unit["locations"])

    report(has_valid_text_spans(u_ad),
           "C2a ad_record 派生 text_span", repr(u_ad.get("locations")))
    u_lp = N.normalize(landing_raw("html"), covers=["页面正文"],
                        does_not_cover=["图内文字"])
    report(has_valid_text_spans(u_lp),
           "C2a landing_page 派生 text_span", repr(u_lp.get("locations")))
    u_sj = N.normalize(landing_raw("structured"), covers=["商品标题与描述"],
                        does_not_cover=[])
    report(has_valid_text_spans(u_sj),
           "C2a structured_json 派生 text_span", repr(u_sj.get("locations")))
    src = open(os.path.join(REPO_ROOT, "base", "normalizer.py"),
               encoding="utf-8").read()
    report("def _unit_id" not in src and "hashlib" not in src,
           "C2 未自造 unit_id 算法（无 _unit_id / hashlib）", "")
    report(N.attempt_hint(u) is None,
           "C2 ok/partial 不产 Attempt hint（只有 failed 回退）", repr(N.attempt_hint(u)))

    # C2b C-21：统一 location 契约（三种 kind + 唯一生产者 normalizer）
    loc_schema = json.load(open(os.path.join(
        REPO_ROOT, "contracts", "location-v1.schema.json"), encoding="utf-8"))
    branches = loc_schema.get("oneOf") or []
    kinds = {b.get("properties", {}).get("kind", {}).get("const") for b in branches}
    report(kinds == set(N.LOCATION_KINDS),
           "C2b-0 location schema 三种 kind", repr(sorted(kinds)))
    report(all(b.get("required") for b in branches),
           "C2b-0b location schema 每个分支都有 required", "")
    report(all(b.get("properties", {}).get("kind", {}).get("const") for b in branches),
           "C2b-0c location schema 每个分支都声明 kind", "")

    # 文本类：由 composition.parts 派生 text_span
    report(u.get("locations") and all(
               x["kind"] == "text_span"
               and isinstance(x.get("start"), int) and isinstance(x.get("end"), int)
               and 0 <= x["start"] < x["end"] <= len(u["text"])
               for x in u["locations"]),
           "C2b-1 文本 ContentUnit 自动派生 text_span（区间合法）", repr(u.get("locations")))
    # 图片：显式 image_region 原样进入 unit.locations
    loc_img = [{"kind": "image_region", "frame_ref": "file:img",
                "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}}]
    u_img2 = N.normalize({
        "kind": "image", "raw": b"image-bytes", "text_from_media": "OCR 正文",
        "uri": "file:img2", "extractor": "ocr-v1", "locations": loc_img,
    }, covers=["图内文字"], does_not_cover=["画面语义"])
    report(u_img2.get("locations") == loc_img,
           "C2b-2 image_region 正样本原样落 ContentUnit.locations", repr(u_img2.get("locations")))
    # 视频：显式 video_timecode
    loc_vid = [{"kind": "video_timecode", "time_start": 1.0, "time_end": 2.0,
                "frame_no": 12, "bbox": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}]
    u_vid = N.normalize({
        "kind": "video", "raw": b"video-bytes", "text_from_media": "ASR 正文",
        "uri": "file:vid", "extractor": "asr-v1", "locations": loc_vid,
        "asr": {"text": "ASR 正文", "timecodes": [1.0, 2.0]},
    }, covers=["字幕"], does_not_cover=["画面语义"])
    report(u_vid.get("locations") == loc_vid,
           "C2b-3 video_timecode 正样本原样落 ContentUnit.locations", repr(u_vid.get("locations")))

    # 负样本：缺字段 / 越界 / 未知 kind 必须拒
    bad_locations = [
        ("text_span 缺 end", {"kind": "text_span", "start": 0}),
        ("text_span 越界", {"kind": "text_span", "start": 0, "end": 99999}),
        ("text_span 空区间", {"kind": "text_span", "start": 2, "end": 2}),
        ("image bbox 缺 h", {"kind": "image_region", "bbox": {"x": 0, "y": 0, "w": 1}}),
        ("image bbox 宽为 0", {"kind": "image_region", "bbox": {"x": 0, "y": 0, "w": 0, "h": 1}}),
        ("video 缺 time_end", {"kind": "video_timecode", "time_start": 0,
                               "frame_no": 1, "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}),
        ("video start>=end", {"kind": "video_timecode", "time_start": 2, "time_end": 2,
                              "frame_no": 1, "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}),
        ("video 缺 frame_no", {"kind": "video_timecode", "time_start": 0, "time_end": 1,
                               "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}),
        ("video 缺 bbox", {"kind": "video_timecode", "time_start": 0, "time_end": 1,
                           "frame_no": 1}),
        ("未知 kind", {"kind": "natural_language", "text": "约第 12 秒"}),
        ("text_span 多字段", {"kind": "text_span", "start": 0, "end": 1, "extra": 1}),
    ]
    for name, loc in bad_locations:
        try:
            N.normalize({"kind": "image", "raw": b"x", "text_from_media": "正文",
                         "uri": "file:x", "locations": [loc]},
                        covers=["正文"], does_not_cover=["画面语义"])
            ok = False
        except Exception:  # noqa: BLE001
            ok = True
        report(ok, "C2b-4 %s → 拒绝" % name, "")

    # ASR 无逐句时间码：只落覆盖缺口，不伪造 video_timecode
    u_asr = N.normalize({
        "kind": "video", "raw": b"video-bytes", "text_from_media": "ASR 正文",
        "uri": "file:asr", "extractor": "asr-v1",
        "asr": {"text": "ASR 正文", "timecodes": None},
    }, covers=["字幕"], does_not_cover=["画面语义"])
    dnc = (u_asr.get("textification") or {}).get("does_not_cover") or []
    report(N.ASR_NO_TIMECODE_GAP in dnc,
           "C2b-5 ASR 无时码 → 落覆盖缺口", repr(dnc))
    report(not any(x.get("kind") == "video_timecode" for x in u_asr.get("locations", [])),
           "C2b-6 ASR 无时码 → 不伪造 video_timecode", repr(u_asr.get("locations")))

    # 唯一生产者：normalizer 之外的基础模块不得写 locations
    writers = []
    for name in sorted(os.listdir(os.path.join(REPO_ROOT, "base"))):
        if name.endswith(".py") and name != "normalizer.py":
            src = open(os.path.join(REPO_ROOT, "base", name), encoding="utf-8").read()
            if '["locations"]' in src or "'locations'" in src:
                writers.append(name)
    report(not writers, "C2b-7 normalizer 是 locations 唯一生产者", repr(writers))

    # validate_unit 本身也要拦住坏 location（不只 normalize 入口）
    bad_unit = copy.deepcopy(u)
    bad_unit["locations"] = [{"kind": "video_timecode", "time_start": 1}]
    report(bool(N.validate_unit(bad_unit)),
           "C2b-8 validate_unit 对坏 location 返回错误", repr(N.validate_unit(bad_unit)))

    # C2b-9 直接调用 _location_problems：不依赖 normalize/contract 的前置拦截。
    valid_loc = [{"kind": "text_span", "start": 0, "end": 1}]
    report(N._location_problems("abc", valid_loc) == [],
           "C2b-9 直接调用 _location_problems：合法样本返回空",
           repr(N._location_problems("abc", valid_loc)))
    direct_bad_locations = [
        ("locations 非数组", "abc", "not-a-list"),
        ("元素非对象", "abc", ["x"]),
        ("未知 kind", "abc", [{"kind": "natural_language"}]),
        ("text 越界", "abc", [{"kind": "text_span", "start": 0, "end": 99}]),
        ("text 空区间", "abc", [{"kind": "text_span", "start": 2, "end": 2}]),
        ("image bbox 缺 h", "", [
            {"kind": "image_region", "bbox": {"x": 0, "y": 0, "w": 1}}]),
        ("video start>=end", "", [
            {"kind": "video_timecode", "time_start": 2, "time_end": 2,
             "frame_no": 1, "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}]),
        ("video frame_no 负", "", [
            {"kind": "video_timecode", "time_start": 0, "time_end": 1,
             "frame_no": -1, "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}]),
        ("text_span 多字段", "abc", [
            {"kind": "text_span", "start": 0, "end": 1, "extra": 1}]),
    ]
    for name, text, locations in direct_bad_locations:
        problems = N._location_problems(text, locations)
        report(bool(problems),
               "C2b-9 直接调用 _location_problems：%s → 有问题" % name,
               repr(problems))

    # C3 partial：可进判定，永不 PASS
    u_part = norm(free_raw("partially parsed text"),
                  covers=["部分正文"], dnc=["未覆盖部分"], status="partial")
    gate = N.judgment_gate(u_part)
    report(u_part["parse_status"] == "partial"
           and u_part["text"] == "partially parsed text"
           and gate.get("enter") is True and gate.get("can_pass") is False,
           "C3 partial 可进判定但永不 PASS", repr(gate))

    # C4 failed 四种 failure_kind：无正文、不进判定、无 ir_id
    for fk in EXPECTED_FAILURE_KINDS:
        try:
            uf = norm(free_raw("这段正文必须在 failed 时被丢弃"),
                      covers=["未审"], dnc=["全部"], status="failed",
                      fk=fk, reason="upstream %s" % fk)
        except Exception as exc:  # noqa: BLE001
            report(False, "R2 failed(%s)：无正文、不进判定、无 ir_id" % fk,
                   "normalize 抛异常：%s: %s" % (type(exc).__name__, exc))
            continue
        gate = N.judgment_gate(uf)
        report(uf["parse_status"] == "failed"
               and uf.get("failure_kind") == fk
               and uf["text"] == "" and uf["has_text"] is False
               and gate.get("enter") is False and gate.get("can_pass") is False
               and "ir_id" not in uf
               and not N.validate_unit(uf),
               "R2 failed(%s)：无正文、不进判定、无 ir_id" % fk,
               "text=%r gate=%r problems=%r"
               % (uf.get("text"), gate, N.validate_unit(uf)))
        hint = N.attempt_hint(uf)
        expected_outcome = ("rejected_unsupported"
                            if fk == "unsupported" else "failed")
        report(hint is not None
               and hint.get("outcome") == expected_outcome
               and hint.get("failure_kind") == fk
               and hint.get("reason") == "upstream %s" % fk,
               "C4 failed(%s) → Attempt 语义（只读视图）" % fk, repr(hint))

    # C4b failed 的各模态空正文分支：真的走 _build_empty，且
    # _derive_locations 的 failed 分支必须丢弃显式 locations（返回 []）。
    for kind, raw in failed_modal_raws().items():
        try:
            uf = N.normalize(
                raw, covers=["已覆盖"], does_not_cover=["未覆盖"],
                parse_status="failed", failure_kind="parse_error",
                reason="upstream parse_error")
        except Exception as exc:  # noqa: BLE001
            report(False, "C4b failed(%s) 空正文分支 + failed locations=[]" % kind,
                   "normalize 抛异常：%s: %s" % (type(exc).__name__, exc))
            continue
        report(uf.get("parse_status") == "failed"
               and uf.get("failure_kind") == "parse_error"
               and uf.get("text") == "" and uf.get("has_text") is False
               and uf.get("locations") == []
               and not N.validate_unit(uf),
               "C4b failed(%s) 空正文分支 + failed locations=[]" % kind,
               "text=%r locations=%r problems=%r"
               % (uf.get("text"), uf.get("locations"),
                  N.validate_unit(uf)))

    # C5 covers / does_not_cover 必填且无默认值
    cases = [
        ("缺 covers", {"does_not_cover": []}),
        ("缺 does_not_cover", {"covers": ["正文"]}),
        ("covers 为空", {"covers": [], "does_not_cover": []}),
        ("covers 不是 list", {"covers": "正文", "does_not_cover": []}),
        ("does_not_cover 不是 list", {"covers": ["正文"], "does_not_cover": "无"}),
    ]
    for name, kwargs in cases:
        try:
            N.normalize(free_raw(), **kwargs)
            ok = False
        except Exception:  # noqa: BLE001
            ok = True
        report(ok, "R1 %s → 拒绝（无默认值）" % name, "")

    # C6 parse_status / failure_kind / reason 合法性
    bad_cases = [
        ("parse_status=unknown", dict(parse_status="unknown")),
        ("ok + failure_kind", dict(parse_status="ok", failure_kind="parse_error")),
        ("failed 缺 failure_kind", dict(parse_status="failed", reason="x")),
        ("failed 未知 failure_kind", dict(parse_status="failed", failure_kind="wat", reason="x")),
        ("failed 缺 reason", dict(parse_status="failed", failure_kind="parse_error")),
        ("failed reason=未知错误", dict(parse_status="failed", failure_kind="parse_error", reason="未知错误")),
    ]
    for name, kwargs in bad_cases:
        try:
            N.normalize(free_raw(), covers=["正文"], does_not_cover=[], **kwargs)
            ok = False
        except Exception:  # noqa: BLE001
            ok = True
        report(ok, "C6 %s → 拒绝" % name, "")

    # C7 指纹：text_sha256 == sha256(text)
    samples = [u, u_ad, u_img, u_part]
    samples += [norm(free_raw("drop"), covers=["未审"], dnc=[], status="failed",
                     fk="parse_error", reason="upstream parse_error")]
    bad = []
    for s in samples:
        fp = s.get("fingerprint") or {}
        if fp.get("text_sha256") != C.sha256_text(s.get("text", "")):
            bad.append((s.get("unit_id"), "text_sha256"))
        if fp.get("text_chars") != len(s.get("text", "")):
            bad.append((s.get("unit_id"), "text_chars"))
        if not isinstance(fp.get("raw_sha256"), str) or len(fp["raw_sha256"]) != 64:
            bad.append((s.get("unit_id"), "raw_sha256"))
    report(not bad, "R3 text_sha256 == sha256(text) 且双指纹齐全", repr(bad[:3]))

    # C8 确定性：同输入两次 + 新进程/新 pycache
    raw2 = free_raw("same input, deterministic")
    a = norm(raw2)
    b = norm(raw2)
    report(a["unit_id"] == b["unit_id"],
           "R4 同输入两次 unit_id 相同", "%s vs %s" % (a["unit_id"], b["unit_id"]))
    cache = tempfile.mkdtemp(prefix="normalizer-pycache-")
    try:
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = cache
        code = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "from base.normalizer import normalize\n"
            "u = normalize(%r, covers=%r, does_not_cover=%r)\n"
            "print(u['unit_id'])\n" % (REPO_ROOT, raw2, ["正文"], []))
        proc = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                              env=env, capture_output=True, text=True)
        report(proc.returncode == 0
               and (proc.stdout or "").strip() == a["unit_id"],
               "R4 新进程 + 全新 pycache 后 unit_id 仍相同",
               "rc=%s out=%r err=%r" % (proc.returncode, proc.stdout, proc.stderr[-200:]))
    finally:
        shutil.rmtree(cache, ignore_errors=True)

    # C9 只产 ContentUnit，不产 ReviewIR
    report(u.get("contract_version") == "content-unit-v1"
           and all(k not in u for k in ("findings", "decision",
                                        "coverage_state", "ir_id")),
           "C9 只产 ContentUnit，不产 ReviewIR", repr(sorted(u.keys())))
    bad = dict(u)
    bad["ir_id"] = "ir-1"
    report(bool(N.validate_unit(bad)),
           "C9 ContentUnit 带 ir_id → 拒绝", repr(N.validate_unit(bad)))
    bad2 = dict(u)
    bad2["findings"] = []
    report(bool(N.validate_unit(bad2)),
           "C9 ContentUnit 带 findings → 拒绝", repr(N.validate_unit(bad2)))

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) == "normalizer.py":
            print("FAIL: normalizer 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
