#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_normalizer.py — T1-02：normalizer / ContentUnit v1

覆盖：
  C0  ContentUnit 12 个 required 字段 + 双指纹；parse_status/failure_kind 域
  C0b schema fingerprint.required 必须声明双指纹、raw_sha256 pattern 为 64 位十六进制
  C0c 缺 raw_sha256 / 缺 text_sha256 的 unit 由 schema 拒绝（验收行 4 第二支）
  C1  free_text ok：复用 contract builder、unit_id/content_key 不重算
  C2  ad_record / image：同样复用 contract builder
  C3  partial：可进判定，但 can_pass=False（永不 PASS）
  C4  failed 四种 failure_kind：不产正文、不进判定、无 ir_id
  C5  covers / does_not_cover 必填且无默认值（缺失/空 covers 必拒）
  C6  parse_status / failure_kind / reason 合法性
  C7  text_sha256 == sha256(text)，text_chars == len(text)
  C7b 双指纹独立复算：raw 用原件字节、text 用正文、unit_id 按声明公式
      （验收行 4「用原件字节重算 raw_sha256」+ 行 5「独立复算」——
       参照是本文件自带的 hashlib，**不**复用 base.contract 的实现，
       否则生产公式删掉 raw 位时自比恒真：2026-10-23 实测 #5 的 survived 形状）
  C8  同输入两次 unit_id 相同；新进程 + 全新 pycache 仍相同
  C9  只产 ContentUnit，不产 ReviewIR（findings/decision/coverage_state/ir_id 必拒）
  R1  删掉 covers 默认补齐 → 红（C5 缺失参数用例）
  R2  failed 产出正文 → 红（C4）
  R3  text_sha256 与 sha256(text) 脱钩 → 红（C7）
  R4  同输入两次 unit_id 不同 → 红（C8）
  R4b 跨进程**直接**比对 text_sha256 / raw_sha256（验收行 10：
      不借 unit_id 的道 —— #10 实测 unit_id 退化成 cu0000… 时这个代理被击穿）

--controls：N1–N6 新断言的反向对照（坏样本必须红；§2.4.1 没红过的断言不算验证过）。

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import base64
import copy
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

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


def tiny_png() -> bytes:
    """生成一张 1×1 RGBA PNG，供 frame_thumb 的「可解码」断言使用。"""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\x00\x00\x00\x00"  # filter + 1 个 RGBA 像素
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def thumb_problems(ref: str) -> list:
    """读取 frame_thumb 并检查图片魔数/结构；返回问题清单。"""
    if not isinstance(ref, str) or not ref.strip():
        return ["frame_thumb 不是非空字符串"]
    try:
        if ref.startswith("data:image/png;base64,"):
            data = base64.b64decode(ref.split(",", 1)[1], validate=True)
        else:
            path = ref[5:] if ref.startswith("file:") else ref
            if not os.path.isabs(path):
                path = os.path.join(REPO_ROOT, path)
            with open(path, "rb") as f:
                data = f.read()
    except Exception as exc:  # noqa: BLE001
        return ["frame_thumb 读不到：%s" % exc]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 33 or data[12:16] != b"IHDR":
            return ["frame_thumb PNG 缺 IHDR"]
        w, h = struct.unpack(">II", data[16:24])
        if w <= 0 or h <= 0:
            return ["frame_thumb PNG 尺寸非法"]
        if b"IEND" not in data[-32:]:
            return ["frame_thumb PNG 缺 IEND"]
        return []
    if data.startswith(b"\xff\xd8") and data.rstrip().endswith(b"\xff\xd9"):
        return []
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return []
    return ["frame_thumb 不是可解码的 PNG/JPEG/WebP"]


def ind_sha_text(t: str) -> str:
    """独立参照实现：本文件自带的 sha256，不复用 base.contract 的函数。

    ★ 为什么必须独立：#5 实测的 survived 形状是「把 raw_sha256 从 _unit_id
      公式里删掉仍全绿」—— 生产 validate() 的 H7 用同一个 _unit_id 复算，
      自比恒真。参照必须长在验收器这边。
    """
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def raw_sha_problem(unit: dict, raw_bytes) -> list:
    """验收行 4 第一支：用**原件字节**重算 raw_sha256，与字段相等。"""
    fp = unit.get("fingerprint") or {}
    if not isinstance(raw_bytes, (bytes, bytearray)):
        return ["无原件字节可复算 raw_sha256（该样本没声明 raw）"]
    want = hashlib.sha256(bytes(raw_bytes)).hexdigest()
    if fp.get("raw_sha256") != want:
        return ["raw_sha256=%r != 原件字节重算 %r"
                % (fp.get("raw_sha256"), want)]
    return []


def text_sha_problem(unit: dict) -> list:
    """验收行 4 第二支的 text 半边：用解析出的正文重算 text_sha256。"""
    fp = unit.get("fingerprint") or {}
    want = hashlib.sha256((unit.get("text") or "").encode("utf-8")).hexdigest()
    if fp.get("text_sha256") != want:
        return ["text_sha256=%r != 正文重算 %r"
                % (fp.get("text_sha256"), want)]
    return []


def unit_id_formula_problem(unit: dict) -> list:
    """验收行 5「按声明的复算算法独立重算」：cu + sha256('cu-v1|kind|raw|text')[:16]。

    ★ 判据原文要求 raw_sha256 **参与**公式 —— 同正文不同原件必须拿到不同的
      unit_id。这里用独立 hashlib 复算，生产公式删掉 raw 位（#5 的变异）时
      本函数与生产值对不上，必须红。
    """
    fp = unit.get("fingerprint") or {}
    kind = (unit.get("source") or {}).get("kind")
    want = "cu" + ind_sha_text(
        "cu-v1|%s|%s|%s" % (kind, fp.get("raw_sha256"), fp.get("text_sha256"))
    )[:16]
    if unit.get("unit_id") != want:
        return ["unit_id=%r != 独立复算 cu-v1|kind|raw|text → %r"
                % (unit.get("unit_id"), want)]
    return []


def fp_schema_errors(fp, fp_schema: dict) -> list:
    """验收行 4 第三支：缺 raw_sha256 / 缺 text_sha256 由 **schema** 拒绝。

    判据读自 base/content-unit-v1.schema.json 的 fingerprint.required 与
    逐字段 pattern —— 验收器只查顶层 required（:157-164）时
    fingerprint.required 被删掉是不可见的（#4 第二支的 survived 形状）。
    """
    if not isinstance(fp, dict):
        return ["fingerprint 必须是 dict，收到 %s" % type(fp).__name__]
    errs = []
    for req in fp_schema.get("required") or []:
        if req not in fp:
            errs.append("缺必填指纹字段 %r" % req)
    props = fp_schema.get("properties") or {}
    for k, v in fp.items():
        sub = props.get(k) or {}
        pat = sub.get("pattern")
        if isinstance(pat, str) and isinstance(v, str) and not re.match(pat, v):
            errs.append("fingerprint.%s=%r 不匹配 schema pattern %r" % (k, v, pat))
    return errs


def fp_required_ok(fp_schema: dict) -> bool:
    """C0b 的判据：schema 的 fingerprint 子声明必须点名双指纹 + text_chars，
    且 raw_sha256 带 64 位十六进制 pattern。schema 被收窄（required 清空 /
    pattern 删掉）时必须判 False —— 那正是 #4 第二支的变异面。"""
    req = set(fp_schema.get("required") or [])
    if req != {"raw_sha256", "text_sha256", "text_chars"}:
        return False
    pat = (fp_schema.get("properties") or {}).get("raw_sha256", {}).get("pattern")
    return pat == "^[0-9a-f]{64}$"


def fp_pair_problem(a: dict, b: dict) -> list:
    """验收行 10：两次运行（含跨进程）的指纹**直接**逐项比对。

    ★ 不借 unit_id 的道 —— #10 实测 sha256_text(...)[:16] 全零填充时
      unit_id 退化成 cu0000000000000000，R4 的代理反而通过。
    """
    problems = []
    for k in ("raw_sha256", "text_sha256", "unit_id"):
        if a.get(k) != b.get(k):
            problems.append("两次运行 %s 不一致：%r vs %r" % (k, a.get(k), b.get(k)))
    return problems


def free_raw(text="FDA approved wearable breast pump", uri="inline:test",
             raw_bytes=None):
    raw = {"kind": "free_text", "text": text, "uri": uri}
    if raw_bytes is not None:
        raw["raw_bytes"] = raw_bytes
    return raw


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
    loc = [{"kind": "image_region", "image_id": "img-1",
            "bbox": [0.1, 0.1, 0.3, 0.3]}]
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


def run_controls() -> int:
    """--controls：N1–N6 新断言的反向对照。喂坏样本，断言必须红（§2.4.1：
    没红过的断言不算验证过它 —— 一条恒真的断言比没有更糟）。"""
    schema = json.loads(open(
        os.path.join(REPO_ROOT, "base", "content-unit-v1.schema.json"),
        encoding="utf-8").read())
    fp_schema = (schema.get("properties") or {}).get("fingerprint") or {}

    u = N.normalize(free_raw("controls base unit"), covers=["正文"],
                    does_not_cover=[])

    checks = []

    def check(cid, cond, detail=""):
        checks.append((cid, bool(cond), detail))

    # N1 raw_sha_problem：指纹抄错 → 必须红
    tampered = copy.deepcopy(u)
    tampered["fingerprint"]["raw_sha256"] = hashlib.sha256(b"other").hexdigest()
    check("N1 raw_sha_problem 对抄错的 raw_sha256 必须红",
          bool(raw_sha_problem(tampered, b"controls-base-raw")))
    check("N1b raw_sha_problem 对合法 unit 必须绿（不误报）",
          not raw_sha_problem(u, "controls base unit".encode("utf-8")))

    # N2 unit_id_formula_problem：unit_id 被手改成错值 → 必须红
    wrong_id = copy.deepcopy(u)
    wrong_id["unit_id"] = "cu" + "0" * 16
    check("N2 unit_id_formula_problem 对手改 id 必须红",
          bool(unit_id_formula_problem(wrong_id)))
    # ★ N2c（#5 的 survived 形状）：生产公式删掉 raw 位 → 独立复算必须红。
    #   判据：同一 unit 的 (kind, raw, text) 用独立 hashlib 复算的值
    #   与生产 unit_id 不等时红 —— 造一个 raw 位被删后**仍相等**的反例是不可能的
    #   （raw 变则 want 变），这里用「raw 抄错但 unit_id 不变」的假绿样本：
    fake = copy.deepcopy(u)
    fake["fingerprint"]["raw_sha256"] = hashlib.sha256(b"another-raw").hexdigest()
    # unit_id 没跟着 raw 变（这正是 #5 变异造成的形状）→ 必须红
    check("N2c raw 改了而 unit_id 没变 → 独立复算必须红",
          bool(unit_id_formula_problem(fake)))

    # N3 text_sha_problem：正文指纹脱钩 → 必须红
    decoupled = copy.deepcopy(u)
    decoupled["fingerprint"]["text_sha256"] = hashlib.sha256(b"other text").hexdigest()
    check("N3 text_sha_problem 对脱钩指纹必须红", bool(text_sha_problem(decoupled)))

    # N4 fp_schema_errors：缺 raw_sha256 / pattern 不符 → 必须红；合法 → 绿
    cut = copy.deepcopy(u)
    del cut["fingerprint"]["raw_sha256"]
    check("N4 缺 raw_sha256 的指纹必须被 schema 判据拒绝",
          bool(fp_schema_errors(cut["fingerprint"], fp_schema)))
    # ★ N4b（#4 第二支的反向对照）：schema 的 fingerprint.required 被清空 →
    #   C0b 判据必须红。判据若写成恒真（比如「required 存在就行」），
    #   这一喂必绿，controls 当场暴露。
    gutted = {"type": "object", "properties": fp_schema.get("properties")}
    check("N4b fingerprint.required 被清空 → C0b 判据必须红",
          not fp_required_ok(gutted))
    # ★ N4b2：pattern 被删 → C0b 判据必须红（同一条判据的另一半）。
    nopat = {"required": fp_schema.get("required"),
             "properties": {k: v for k, v in (fp_schema.get("properties") or {}).items()
                            if k != "raw_sha256"}}
    check("N4b2 raw_sha256 pattern 被删 → C0b 判据必须红",
          not fp_required_ok(nopat))
    check("N4b3 真 schema 必须过 C0b 判据（不误报）", fp_required_ok(fp_schema))
    check("N4c 合法指纹不被误拒", not fp_schema_errors(u["fingerprint"], fp_schema))

    # N5 fp_pair_problem：两次结果不一致 → 必须红；一致 → 绿
    check("N5 两次指纹不一致必须红",
          bool(fp_pair_problem({"text_sha256": "a", "raw_sha256": "a", "unit_id": "u1"},
                               {"text_sha256": "b", "raw_sha256": "a", "unit_id": "u1"})))
    check("N5b 两次指纹一致必须绿（不误报）",
          not fp_pair_problem({"text_sha256": "a", "raw_sha256": "a", "unit_id": "u1"},
                              {"text_sha256": "a", "raw_sha256": "a", "unit_id": "u1"}))

    # N6 schema 判据的负样本走真实 schema 值：pattern 被放宽 → 判据必须跟着失明
    # （判据取自 schema 而不是硬编码 —— schema 被改坏时这里的「放宽即失明」要能被看见）。
    loose = copy.deepcopy(fp_schema)
    loose["properties"] = {**(loose.get("properties") or {})}
    loose["properties"]["raw_sha256"] = {"type": "string"}
    check("N6 pattern 放宽后 pattern 不符样本不再被拦（判据确实取自 schema）",
          not fp_schema_errors(mangled := copy.deepcopy(u)["fingerprint"], loose))
    # —— N6 是「判据来源」的存在性对照：判据硬编码时 loose 改动不影响结果；
    #    判据取自 schema 时，放宽 = 失明。两者都可观察，不存在恒真。

    reds = [c for c in checks if not c[1]]
    print("=" * 60)
    print("--controls · verify_normalizer 新断言反向对照")
    print("=" * 60)
    for cid, ok, detail in checks:
        print("  %s %-52s %s" % ("✓" if ok else "✗", cid, detail))
    if reds:
        print("❌ %d/%d 红" % (len(reds), len(checks)), file=sys.stderr)
        return 1
    print("✅ %d/%d 全过（坏样本红、好样本不误报）" % (len(checks), len(checks)))
    return 0


def main():
    if "--controls" in sys.argv:
        return run_controls()
    passed = 0
    failed = 0
    thumb_dir = tempfile.mkdtemp(prefix="normalizer-thumb-")
    thumb_path = os.path.join(thumb_dir, "frame.png")
    with open(thumb_path, "wb") as f:
        f.write(tiny_png())
    thumb_ref = "file:" + thumb_path

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

    # C0b schema 的 fingerprint 子声明（验收行 4 第三支的判据来源）。
    # ★ 只查顶层 required（原 :157-164）时 fingerprint.required 被删掉是不可见的
    #   —— #4 第二支 survived 的形状：fingerprint.required 从未被消费。
    fp_schema = (schema.get("properties") or {}).get("fingerprint") or {}
    fp_req = set(fp_schema.get("required") or [])
    report(fp_required_ok(fp_schema),
           "C0b schema fingerprint.required 声明双指纹 + text_chars（pattern 64hex）",
           "required=%r" % (fp_req,))

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
            and x.get("quote") == text[x["start"]:x["end"]]
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
    by_kind = {
        b.get("properties", {}).get("kind", {}).get("const"): set(b.get("required") or [])
        for b in branches
    }
    report(by_kind.get("text_span") == {"kind", "start", "end", "quote"},
           "C2b-0d text_span required = kind/start/end/quote",
           repr(by_kind.get("text_span")))
    report(by_kind.get("image_region") == {"kind", "image_id", "bbox"},
           "C2b-0e image_region required = kind/image_id/bbox",
           repr(by_kind.get("image_region")))
    report(by_kind.get("video_timecode") == {
               "kind", "video_id", "time_start", "time_end",
               "frame_no", "frame_thumb"},
           "C2b-0f video_timecode required = 五字段 + video_id/frame_thumb（bbox 可缺省）",
           repr(by_kind.get("video_timecode")))
    bbox_def = (loc_schema.get("definitions") or {}).get("bbox") or {}
    report(bbox_def.get("type") == "array" and bbox_def.get("minItems") == 4
           and bbox_def.get("maxItems") == 4,
           "C2b-0g bbox 定义为长度 4 的数组", repr(bbox_def))

    # 文本类：由 composition.parts 派生 text_span
    report(u.get("locations") and all(
               x["kind"] == "text_span"
               and isinstance(x.get("start"), int) and isinstance(x.get("end"), int)
               and 0 <= x["start"] < x["end"] <= len(u["text"])
               and x.get("quote") == u["text"][x["start"]:x["end"]]
               for x in u["locations"]),
           "C2b-1 文本 ContentUnit 自动派生 text_span（区间合法 + quote 等于切片）",
           repr(u.get("locations")))
    # 图片：显式 image_region 原样进入 unit.locations
    loc_img = [{"kind": "image_region", "image_id": "img-2",
                "frame_ref": "file:img",
                "bbox": [0.1, 0.2, 0.4, 0.6]}]
    u_img2 = N.normalize({
        "kind": "image", "raw": b"image-bytes", "text_from_media": "OCR 正文",
        "uri": "file:img2", "extractor": "ocr-v1", "locations": loc_img,
    }, covers=["图内文字"], does_not_cover=["画面语义"])
    report(u_img2.get("locations") == loc_img,
           "C2b-2 image_region 正样本原样落 ContentUnit.locations", repr(u_img2.get("locations")))
    # 视频：显式 video_timecode
    loc_vid = [{"kind": "video_timecode", "video_id": "vid-1",
                "time_start": 1.0, "time_end": 2.0, "frame_no": 12,
                "frame_thumb": thumb_ref, "bbox": [0.0, 0.0, 1.0, 1.0]}]
    u_vid = N.normalize({
        "kind": "video", "raw": b"video-bytes", "text_from_media": "ASR 正文",
        "uri": "file:vid", "extractor": "asr-v1", "locations": loc_vid,
        "asr": {"text": "ASR 正文", "timecodes": [1.0, 2.0]},
    }, covers=["字幕"], does_not_cover=["画面语义"])
    report(u_vid.get("locations") == loc_vid,
           "C2b-3 video_timecode 正样本原样落 ContentUnit.locations", repr(u_vid.get("locations")))

    # 负样本：缺字段 / 越界 / 未知 kind 必须拒
    bad_locations = [
        ("text_span 缺 end", {"kind": "text_span", "start": 0, "quote": "a"}),
        ("text_span quote 与切片不等",
         {"kind": "text_span", "start": 0, "end": 1, "quote": "z"}),
        ("text_span 越界", {"kind": "text_span", "start": 0, "end": 99999,
                            "quote": "a"}),
        ("text_span 空区间", {"kind": "text_span", "start": 2, "end": 2,
                              "quote": "x"}),
        ("image 缺 image_id", {"kind": "image_region", "bbox": [0, 0, 1, 1]}),
        ("image bbox 长度 3", {"kind": "image_region", "image_id": "img",
                               "bbox": [0, 0, 1]}),
        ("image bbox 宽为 0", {"kind": "image_region", "image_id": "img",
                               "bbox": [0, 0, 0, 1]}),
        ("image bbox 绝对像素", {"kind": "image_region", "image_id": "img",
                                 "bbox": [0, 0, 1280, 720]}),
        ("video 缺 video_id", {"kind": "video_timecode", "time_start": 0,
                               "time_end": 1, "frame_no": 1,
                               "frame_thumb": thumb_ref}),
        ("video 缺 frame_thumb", {"kind": "video_timecode", "video_id": "v",
                                  "time_start": 0, "time_end": 1, "frame_no": 1}),
        ("video 缺 time_end", {"kind": "video_timecode", "video_id": "v",
                               "time_start": 0, "frame_no": 1,
                               "frame_thumb": thumb_ref}),
        ("video start>end", {"kind": "video_timecode", "video_id": "v",
                             "time_start": 2, "time_end": 1, "frame_no": 1,
                             "frame_thumb": thumb_ref}),
        ("video 时间超精度", {"kind": "video_timecode", "video_id": "v",
                              "time_start": 1.23, "time_end": 2.0, "frame_no": 12,
                              "frame_thumb": thumb_ref}),
        ("video 缺 frame_no", {"kind": "video_timecode", "video_id": "v",
                               "time_start": 0, "time_end": 1,
                               "frame_thumb": thumb_ref}),
        ("未知 kind", {"kind": "natural_language", "text": "约第 12 秒"}),
        ("text_span 多字段", {"kind": "text_span", "start": 0, "end": 1,
                              "quote": "a", "extra": 1}),
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
    valid_loc = [{"kind": "text_span", "start": 0, "end": 1, "quote": "a"}]
    report(N._location_problems("abc", valid_loc) == [],
           "C2b-9 直接调用 _location_problems：合法样本返回空",
           repr(N._location_problems("abc", valid_loc)))
    direct_bad_locations = [
        ("locations 非数组", "abc", "not-a-list"),
        ("元素非对象", "abc", ["x"]),
        ("自然语言位置串", "abc", ["约第 12 秒，宝宝坐在副驾"]),
        ("未知 kind", "abc", [{"kind": "natural_language"}]),
        ("text 缺 quote", "abc", [{"kind": "text_span", "start": 0, "end": 1}]),
        ("text quote 不等于切片", "abc", [
            {"kind": "text_span", "start": 0, "end": 1, "quote": "z"}]),
        ("text 越界", "abc", [
            {"kind": "text_span", "start": 0, "end": 99, "quote": "a"}]),
        ("text 空区间", "abc", [
            {"kind": "text_span", "start": 2, "end": 2, "quote": "x"}]),
        ("image bbox 长度 3", "", [
            {"kind": "image_region", "image_id": "img", "bbox": [0, 0, 1]}]),
        ("image bbox 旧对象", "", [
            {"kind": "image_region", "image_id": "img",
             "bbox": {"x": 0, "y": 0, "w": 1, "h": 1}}]),
        ("video start>end", "", [
            {"kind": "video_timecode", "video_id": "v", "time_start": 2,
             "time_end": 1, "frame_no": 1, "frame_thumb": thumb_ref}]),
        ("video frame_no 负", "", [
            {"kind": "video_timecode", "video_id": "v", "time_start": 0,
             "time_end": 1, "frame_no": -1, "frame_thumb": thumb_ref}]),
        ("video 缺 frame_thumb", "", [
            {"kind": "video_timecode", "video_id": "v", "time_start": 0,
             "time_end": 1, "frame_no": 1}]),
        ("text_span 多字段", "abc", [
            {"kind": "text_span", "start": 0, "end": 1, "quote": "a",
             "extra": 1}]),
    ]
    for name, text, locations in direct_bad_locations:
        problems = N._location_problems(text, locations)
        report(bool(problems),
               "C2b-9 直接调用 _location_problems：%s → 有问题" % name,
               repr(problems))

    # C2c 验收行 21：三形态全字段、bbox 数组、frame_no 独立复算、thumb 可读
    def video_raw(loc, sampling=None):
        raw = {"kind": "video", "raw": b"video-bytes",
               "text_from_media": "ASR 正文", "uri": "file:vid",
               "extractor": "asr-v1", "locations": [loc],
               "asr": {"text": "ASR 正文", "timecodes": [1.0, 2.0]}}
        if sampling is not None:
            raw["frame_sampling"] = sampling
        return raw

    def image_raw(loc):
        return {"kind": "image", "raw": b"image-bytes",
                "text_from_media": "正文", "uri": "file:img",
                "extractor": "ocr-v1", "locations": [loc]}

    # 文本：quote 必填且等于 origin[start:end]；缺 quote 由 normalizer 从切片补齐
    text_auto = N.normalize(image_raw(
        {"kind": "text_span", "start": 0, "end": 1}),
        covers=["正文"], does_not_cover=["画面语义"])
    report(text_auto["locations"] == [
               {"kind": "text_span", "start": 0, "end": 1, "quote": "正"}],
           "C2c-1 text_span 缺 quote → normalizer 按 start/end 补切片",
           repr(text_auto["locations"]))

    # 图片：image_id + bbox 数组；旧对象输入规范化成数组
    img_legacy = N.normalize(image_raw(
        {"kind": "image_region", "image_id": "img-3",
         "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}}),
        covers=["正文"], does_not_cover=["画面语义"])
    report(img_legacy["locations"] == [
               {"kind": "image_region", "image_id": "img-3",
                "bbox": [0.1, 0.2, 0.4, 0.6]}],
           "C2c-2 image_region 旧对象 bbox → 规范数组 [x1,y1,x2,y2]",
           repr(img_legacy["locations"]))
    report(bool(N._location_problems("", [
               {"kind": "image_region", "image_id": "img",
                "bbox": [0.4, 0.2, 0.1, 0.6]}])),
           "C2c-3 bbox 倒置（x1>=x2）→ 拒绝", "")

    # 视频：五个必填字段；全画面允许 bbox 缺省
    vid_full = N.normalize(video_raw(
        {"kind": "video_timecode", "video_id": "v-1",
         "time_start": 1.0, "time_end": 2.0, "frame_no": 12,
         "frame_thumb": thumb_ref}),
        covers=["字幕"], does_not_cover=["画面语义"])
    report(vid_full["locations"][0].get("bbox") is None
           and vid_full["locations"][0]["video_id"] == "v-1"
           and vid_full["locations"][0]["frame_thumb"] == thumb_ref,
           "C2c-4 video 全画面断言允许 bbox 缺省，五必填字段齐全",
           repr(vid_full["locations"]))
    vid_equal = N.normalize(video_raw(
        {"kind": "video_timecode", "video_id": "v-2",
         "time_start": 1.0, "time_end": 1.0, "frame_no": 0,
         "frame_thumb": thumb_ref}),
        covers=["字幕"], does_not_cover=["画面语义"])
    report(vid_equal["locations"][0]["time_end"] == 1.0,
           "C2c-5 time_end == time_start 允许（判据是 ≥）",
           repr(vid_equal["locations"]))

    # frame_no 独立复算：本地公式与 production helper 对拍，换参数读数同步变化
    sampling = {"interval_seconds": 0.5, "offset_seconds": 0.0}
    frame_ok = N.normalize(video_raw(
        {"kind": "video_timecode", "video_id": "v-3",
         "time_start": 12.0, "time_end": 12.5, "frame_no": 24,
         "frame_thumb": thumb_ref}, sampling),
        covers=["字幕"], does_not_cover=["画面语义"])
    expected = int(round((12.0 - 0.0) / 0.5))
    report(expected == 24 and N.frame_no_for(12.0, 0.0, 0.5) == expected
           and frame_ok["locations"][0]["frame_no"] == expected,
           "C2c-6 frame_no 独立复算 = round((time_start-offset)/interval)",
           repr(frame_ok["locations"]))
    try:
        N.normalize(video_raw(
            {"kind": "video_timecode", "video_id": "v-4",
             "time_start": 12.0, "time_end": 12.5, "frame_no": 23,
             "frame_thumb": thumb_ref}, sampling),
            covers=["字幕"], does_not_cover=["画面语义"])
        frame_mismatch = False
    except ValueError:
        frame_mismatch = True
    report(frame_mismatch,
           "C2c-7 frame_no 与抽帧参数不一致 → 拒绝", "")
    sampling2 = {"interval_seconds": 0.25, "offset_seconds": 0.0}
    frame_ok2 = N.normalize(video_raw(
        {"kind": "video_timecode", "video_id": "v-5",
         "time_start": 12.0, "time_end": 12.5, "frame_no": 48,
         "frame_thumb": thumb_ref}, sampling2),
        covers=["字幕"], does_not_cover=["画面语义"])
    report(frame_ok2["locations"][0]["frame_no"] == 48,
           "C2c-8 换抽帧间隔 → frame_no 同步变化（24→48）",
           repr(frame_ok2["locations"]))
    try:
        N.normalize(video_raw(
            {"kind": "video_timecode", "video_id": "v-6",
             "time_start": 1.0, "time_end": 2.0, "frame_no": 1,
             "frame_thumb": thumb_ref}, "bad-sampling"),
            covers=["字幕"], does_not_cover=["画面语义"])
        bad_sampling = False
    except ValueError:
        bad_sampling = True
    report(bad_sampling, "C2c-8b frame_sampling 非对象 → 拒绝", "")

    # frame_thumb：实际读取并检查可解码
    report(thumb_problems(thumb_ref) == [],
           "C2c-9 frame_thumb file: 路径可读且 PNG 可解码",
           repr(thumb_problems(thumb_ref)))
    data_ref = "data:image/png;base64," + base64.b64encode(tiny_png()).decode()
    report(thumb_problems(data_ref) == [],
           "C2c-10 frame_thumb data: bytes 引用可解码",
           repr(thumb_problems(data_ref)))
    bad_thumb = os.path.join(thumb_dir, "not-image.txt")
    with open(bad_thumb, "w", encoding="utf-8") as f:
        f.write("not an image")
    report(bool(thumb_problems("file:" + bad_thumb)),
           "C2c-11 frame_thumb 非图片 → 拒绝", "")

    # validate_unit 本身也不接受旧对象 bbox（只有 normalizer 入口做兼容转换）
    bad_unit_obj = copy.deepcopy(u_img2)
    bad_unit_obj["locations"] = [{
        "kind": "image_region", "image_id": "img-2",
        "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}}]
    report(bool(N.validate_unit(bad_unit_obj)),
           "C2c-12 validate_unit 对旧对象 bbox 返回错误", "")
    print("NOTE: C2c 的「image bbox 裁剪后与 finding 描述一致」与"
          "「frame_thumb 重抽帧做感知哈希/人工比对」未纳入本验证器"
          "（当前没有媒体管道/裁图器/抽帧器）；本验证器只验几何契约、"
          "frame_thumb 可读可解码与 frame_no 可复算。")

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

    # C7b 双指纹 + unit_id **独立复算**（验收行 4 第一支 / 行 5）。
    # 参照是本文件自带的 hashlib，不复用 base.contract 的实现 ——
    # 生产 _unit_id 删掉 raw 位（#5 变异）时这里必须红，自比恒真不算数。
    # ★ 样本带原件字节：raw_sha256 答「看的是哪份原件」，必须有原件可对
    #   （#4 第一支 survived：验证器只查 64 位字符串，从不按原件字节重算）。
    recalc_samples = [
        # u 来自 C1 的 free_raw() 默认正文；raw_bytes 缺省时 raw_sha256=text UTF-8
        ("free_text(默认原件=text UTF-8)", u,
         "FDA approved wearable breast pump".encode("utf-8")),
        ("ad_record(整行 JSON)", u_ad,
         json.dumps({"Primary Text": "A", "Headline": "B", "外部广告ID": "ad-1"},
                    ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")),
        ("image(raw)", u_img, b"image-bytes"),
    ]
    recalc_bad = []
    for label, s, rbytes in recalc_samples:
        for prob in raw_sha_problem(s, rbytes):
            recalc_bad.append("%s: %s" % (label, prob))
        for prob in text_sha_problem(s):
            recalc_bad.append("%s: %s" % (label, prob))
        for prob in unit_id_formula_problem(s):
            recalc_bad.append("%s: %s" % (label, prob))
    # 同正文、不同原件 → unit_id 必须不同（raw 位真实参与公式的行为面）。
    probe_a = norm(free_raw("同正文不同原件 probe", uri="inline:probe-a"))
    probe_b = norm(free_raw("同正文不同原件 probe", uri="inline:probe-b",
                            raw_bytes=b"different-raw-bytes-for-probe-b"))
    if probe_a["unit_id"] == probe_b["unit_id"]:
        recalc_bad.append("同正文不同原件 probe: unit_id 撞了（raw 位没参与公式）")
    if probe_a["fingerprint"]["raw_sha256"] == probe_b["fingerprint"]["raw_sha256"]:
        recalc_bad.append("同正文不同原件 probe: raw_sha256 撞了（不该发生）")
    report(not recalc_bad,
           "C7b 双指纹+unit_id 独立复算（raw 用原件字节；公式吃 raw 位）",
           repr(recalc_bad[:3]))

    # C0c 缺指纹字段 / 指纹写坏 → schema 判据必须拒绝（验收行 4 第三支）。
    missing_fp_bad = []
    for miss in ("raw_sha256", "text_sha256"):
        cut = copy.deepcopy(u)
        del cut["fingerprint"][miss]
        if not fp_schema_errors(cut["fingerprint"], fp_schema):
            missing_fp_bad.append("缺 %s 的指纹未被 schema 判据拒绝" % miss)
    mangled = copy.deepcopy(u)
    mangled["fingerprint"]["raw_sha256"] = "zz" * 32
    if not fp_schema_errors(mangled["fingerprint"], fp_schema):
        missing_fp_bad.append("raw_sha256 不匹配 pattern 未被 schema 判据拒绝")
    if fp_schema_errors(u["fingerprint"], fp_schema):
        missing_fp_bad.append("合法指纹被 schema 判据误拒")
    report(not missing_fp_bad,
           "C0c 缺 raw_sha256/text_sha256 或 pattern 不符 → schema 判据拒绝",
           repr(missing_fp_bad))

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
            "import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "from base.normalizer import normalize\n"
            "u = normalize(%r, covers=%r, does_not_cover=%r)\n"
            "print(json.dumps({'unit_id': u['unit_id'],\n"
            "                  'fingerprint': u['fingerprint']}))\n"
            % (REPO_ROOT, raw2, ["正文"], []))
        proc = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                              env=env, capture_output=True, text=True)
        remote = {}
        try:
            remote = json.loads((proc.stdout or "").strip() or "{}")
        except ValueError:
            pass
        report(proc.returncode == 0 and remote.get("unit_id") == a["unit_id"],
               "R4 新进程 + 全新 pycache 后 unit_id 仍相同",
               "rc=%s out=%r err=%r" % (proc.returncode, proc.stdout[:200],
                                        proc.stderr[-200:]))
        # R4b（验收行 10）：跨进程**直接**比对 text_sha256 / raw_sha256，
        # 不借 unit_id 的道 —— #10 实测 unit_id 退化成 cu0000… 时该代理被击穿。
        cross_bad = []
        if proc.returncode != 0 or not remote:
            cross_bad.append("新进程没跑起来或输出不是 JSON：%r" % (proc.stdout or "")[:120])
        else:
            cross_bad += fp_pair_problem(
                {"raw_sha256": a["fingerprint"].get("raw_sha256"),
                 "text_sha256": a["fingerprint"].get("text_sha256"),
                 "unit_id": a["unit_id"]},
                {"raw_sha256": remote.get("fingerprint", {}).get("raw_sha256"),
                 "text_sha256": remote.get("fingerprint", {}).get("text_sha256"),
                 "unit_id": remote.get("unit_id")})
            # 行为面：text_sha256 不得退化成「固定串」——
            # 恒等函数两次运行相等是假绿，不同正文必须拿到不同指纹。
            if a["fingerprint"]["text_sha256"] == u_part["fingerprint"]["text_sha256"]:
                cross_bad.append("不同正文的 text_sha256 相同 —— 指纹退化了")
        report(not cross_bad,
               "R4b 跨进程直接比对 text_sha256/raw_sha256（不借 unit_id）",
               repr(cross_bad[:3]))
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

    shutil.rmtree(thumb_dir, ignore_errors=True)
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
