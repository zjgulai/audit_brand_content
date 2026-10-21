#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_model_selection.py —— 把「多模态与向量模型选型」里的每条清单断言变成可跑读数。

## 为什么要有它（AGENTS.md §2.4.1 第 5 行）

`PMO/implement/多模态与向量模型-选型-20261021.md` 的结论全部来自**清单声明的字段**：
`~/.cache/magpie/models.json`（232 provider / 9087 条目 / 4118 唯一 id）与
`~/.cache/magpie/models/{vod,tokenhub}.json`。清单会变（vod 今天没有 embedding，
明天可能加；`glm-5.3-flash` 今天没有 audio，权重升级后可能有），而文档不会自己变红。

所以这里只做一件事：**对着实时清单核文档里的断言**。对不上就红，并指出文档哪一句过期了。
不自动改文档（§2.4.4：检查器不许改掉它要保护的东西）。

## 只读哪里

- `~/.cache/magpie/models.json`
- `~/.cache/magpie/models/vod.json`
- `~/.cache/magpie/models/tokenhub.json`

**绝不读 `~/.config/magpie/`**（凭据，AGENTS.md §2.6 第 3 条）。本脚本无任何外呼。

## 退出码

- `0` 全过
- `1` 有红（某条断言与清单对不上，或 S8 规模越界）
- `2` **未测**：清单不在盘上 / 读不出（`~/.cache` 可能被清）。未测 ≠ 通过 ≠ 红。

## 用法

    python3 tools/verify_model_selection.py
    python3 tools/verify_model_selection.py --controls

`--controls` 用临时构造的清单跑反向对照：好样本必须绿，坏样本（塞 `bge-m3`、
给 glm 加 audio、ASR 少一条、provider 降到 19、vod 缺 gemini、Price 非空、
S8 规模越界）必须红；清单缺失必须判未测。**没红过的断言不算验证过它**（§2.4.1 末段）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# ── 读数口径（文档 §〇 / §五）────────────────────────────────────────────

CACHE_ROOT = Path(os.path.expanduser("~/.cache/magpie"))
MODELS_JSON = CACHE_ROOT / "models.json"
VOD_JSON = CACHE_ROOT / "models" / "vod.json"
TOKENHUB_JSON = CACHE_ROOT / "models" / "tokenhub.json"

# 文档 §〇 的复现命令用的就是这组词
EMBED_RE = re.compile(r"embed|bge|gte|rerank", re.I)
# 文档 §〇 表里 tokenhub 的 8 条 ASR：hy-asr-*、wand-asr-*、minimax-speech-*
ASR_RE = re.compile(r"asr|speech|transcri|whisper", re.I)

# 文档 §〇 的两个网关条目数（只作为读数，不作为断言 —— 清单会增减）
DOC_VOD_COUNT = 71
DOC_TOKENHUB_COUNT = 116

# S6：文档写 27；低于 20 说明 failover 论据不成立
GLM_MIN_PROVIDERS = 20
GLM_DOC_PROVIDERS = 27
#: 与文档声明值的允许差（provider 上下架的正常抖动）；超过即视为清单坏了。
GLM_DELTA_TOL = 3

# S8：文档 §五 的规模读数。容差是「同一数量级」，不是相等 —— 语料会增长。
DOC_INDEXABLE_MB = 8.9
DOC_INDEXABLE_FILES = 149
INDEXABLE_MIN_RATIO = 0.85
INDEXABLE_MAX_RATIO = 1.5
INDEXABLE_MIN_FILES = 100       # 文件数下界：防「范围被悄悄改小」后仍落在字节带里
INDEXABLE_MAX_FILES = 300       # 上界压到 300（2.0× 文档值）：首版 484 那种 3.2× 漂移必须红

# S8 的扫描范围 —— ★ **必须与文档 §五 里那段复现命令逐项相同**。
#
# 2026-10-21 更正（8a 首版这里是另一套范围，靠 0.5–2.0 的宽带给蒙过去了）：
#   首版 INDEXABLE_ROOTS 含 research/method + research/distill + research/feishu，
#   **不含 research/governance**；实测落 484 文件 / 8.04 MB。
#   而文档那段命令落 149 文件 / 8.96 MB。两者字节像，**文件数差 3 倍** ——
#   于是 S8 一直在验一个文档里根本没写的范围，而它自己是绿的。
#
#   这就是 §2.4「名字出现过 ≠ 拦得住」在**校验器自己身上**的第三次变体：
#   判据的范围与被验的对象不是同一个，而结论行照样打 ✅。
#   修法两条，缺一条都不算修好：
#     ① 范围逐项对齐文档的命令（下面这张表就是那段命令的转录）；
#     ② 同时断言**文件数**，不只是字节 —— 只比字节的话，范围改小一半仍可能落在带里。
INDEXABLE_ROOTS = [
    "research/kb", "research/governance", "agent-skills",
    "PRD", "PMO/implement", "ADR",
]
INDEXABLE_EXTS = {".md", ".json", ".txt"}
# 文档的命令是「路径任一段叫 _evidence 就跳过」，这里照抄；其余目录不额外排除。
INDEXABLE_SKIP_DIRS = {"_evidence"}


# ── 读数工具 ──────────────────────────────────────────────────────────────

def _load_json(path: Path):
    """返回 (data, error)。error 非空表示未测，不是「空清单」。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "文件不存在：%s" % path
    except OSError as exc:
        return None, "读不出 %s：%s" % (path, exc)
    except json.JSONDecodeError as exc:
        return None, "%s 不是合法 JSON：%s" % (path, exc)


def _manifest_ids(data) -> list:
    if not isinstance(data, dict):
        return []
    models = data.get("models")
    if not isinstance(models, list):
        return []
    return [str(m.get("ID")) for m in models if isinstance(m, dict) and m.get("ID")]


def _modal_inputs(model: dict) -> list:
    mods = (model or {}).get("modalities") or {}
    inp = mods.get("input") if isinstance(mods, dict) else None
    return [str(x) for x in inp] if isinstance(inp, list) else []


def _global_entries(global_data: dict, model_id: str):
    """返回 [(provider, model_dict)]；全局清单是 provider → {models: {id: model}}。"""
    out = []
    for provider, pdata in (global_data or {}).items():
        models = (pdata or {}).get("models") if isinstance(pdata, dict) else None
        if not isinstance(models, dict):
            continue
        m = models.get(model_id)
        if isinstance(m, dict):
            out.append((provider, m))
    return out


def _nonempty_count(models: list, field: str) -> int:
    return sum(1 for m in models
               if isinstance(m, dict) and m.get(field) not in (None, "", [], {}))


def _scan_indexable_bytes(repo_root: Path):
    """按显式口径扫描可索引文本；返回 (files, bytes, scope_note)。"""
    files = 0
    total = 0
    for root_rel in INDEXABLE_ROOTS:
        root = repo_root / root_rel
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in INDEXABLE_SKIP_DIRS]
            for name in filenames:
                if Path(name).suffix.lower() not in INDEXABLE_EXTS:
                    continue
                p = Path(dirpath) / name
                try:
                    total += p.stat().st_size
                    files += 1
                except OSError:
                    continue
    return files, total, "roots=%s；仅跳过名为 _evidence 的目录；扩展名 %s" % (
        ",".join(INDEXABLE_ROOTS), ",".join(sorted(INDEXABLE_EXTS)))


# ── 断言 ──────────────────────────────────────────────────────────────────

def check(manifest_root: Path, repo_root: Path) -> dict:
    """对给定清单根与仓库根跑 S1–S8；返回 {verdict, assertions, reds, untested}。

    `manifest_root` 下必须有三份文件：models.json、models/vod.json、models/tokenhub.json。
    任何一份缺失/读不出 → verdict='untested'（退出码 2），不把「没读过」说成通过或红。
    """
    models_path = manifest_root / "models.json"
    vod_path = manifest_root / "models" / "vod.json"
    tokenhub_path = manifest_root / "models" / "tokenhub.json"

    global_data, e1 = _load_json(models_path)
    vod_data, e2 = _load_json(vod_path)
    tokenhub_data, e3 = _load_json(tokenhub_path)
    errors = [e for e in (e1, e2, e3) if e]
    if errors:
        return {
            "verdict": "untested",
            "assertions": [],
            "reds": [],
            "untested": errors,
        }

    assertions = []
    reds = []

    def add(sid, ok, reading, doc_ref):
        assertions.append({"id": sid, "ok": bool(ok), "reading": reading, "doc_ref": doc_ref})
        if not ok:
            reds.append("%s：%s（文档：%s）" % (sid, reading, doc_ref))

    vod_ids = _manifest_ids(vod_data)
    th_ids = _manifest_ids(tokenhub_data)
    vod_models = vod_data.get("models") if isinstance(vod_data, dict) else []
    th_models = tokenhub_data.get("models") if isinstance(tokenhub_data, dict) else []

    # S1 / S2：两个网关的 embedding/rerank 命中数
    vod_embed = [i for i in vod_ids if EMBED_RE.search(i)]
    th_embed = [i for i in th_ids if EMBED_RE.search(i)]
    add("S1", len(vod_embed) == 0,
        "vod 条目 %d，embedding/rerank 命中 %d %s"
        % (len(vod_ids), len(vod_embed), vod_embed[:5]),
        "§〇 表：vod 含 embed/bge/gte/rerank = 0")
    add("S2", len(th_embed) == 0,
        "tokenhub 条目 %d，embedding/rerank 命中 %d %s"
        % (len(th_ids), len(th_embed), th_embed[:5]),
        "§〇 表：tokenhub 含 embed/bge/gte/rerank = 0")

    # S3：ASR 命中数
    vod_asr = [i for i in vod_ids if ASR_RE.search(i)]
    th_asr = [i for i in th_ids if ASR_RE.search(i)]
    add("S3", len(vod_asr) == 0 and len(th_asr) == 8,
        "vod ASR=%d %s；tokenhub ASR=%d %s"
        % (len(vod_asr), vod_asr[:5], len(th_asr), th_asr[:10]),
        "§〇 表：vod 含 ASR = 0；tokenhub 含 ASR = 8")

    # S4：glm-5.3-flash 不含 audio（文档 §四「不要用做音画对齐」的依据）
    glm = _global_entries(global_data, "glm-5.3-flash")
    glm_inputs = [_modal_inputs(m) for _, m in glm]
    glm_audio = [inp for inp in glm_inputs if "audio" in inp]
    glm_video = [inp for inp in glm_inputs if "video" in inp]
    add("S4", bool(glm) and len(glm_audio) == 0,
        "glm-5.3-flash provider=%d，含 audio 的输入组合=%d，含 video=%d"
        % (len(glm), len(glm_audio), len(glm_video)),
        "§四：glm-5.3-flash 有 video 没有 audio")

    # S5：两个 Gemini 的 input 同时含 audio+video，且出现在 vod
    for mid in ("gemini-3.1-flash-lite", "gemini-3.5-flash"):
        ents = _global_entries(global_data, mid)
        both = [_modal_inputs(m) for _, m in ents
                if "audio" in _modal_inputs(m) and "video" in _modal_inputs(m)]
        add("S5", bool(both) and mid in vod_ids,
            "%s provider=%d，同时含 audio+video 的输入组合=%d，vod 命中=%s"
            % (mid, len(ents), len(both), mid in vod_ids),
            "§四 表：两个 Gemini 同请求吃 audio+video，且走 vod")

    # S6：glm-5.3-flash provider 覆盖数 ≥ 20（文档写 27）
    providers = sorted({p for p, _ in glm})
    _delta = len(providers) - GLM_DOC_PROVIDERS
    add("S6", len(providers) >= GLM_MIN_PROVIDERS
              and abs(_delta) <= GLM_DELTA_TOL,
        "glm-5.3-flash provider 覆盖=%d（文档写 %d，差值 %+d，抖动容差 ±%d，可用下限 %d）%s"
        % (len(providers), GLM_DOC_PROVIDERS, _delta, GLM_DELTA_TOL,
           GLM_MIN_PROVIDERS, providers[:8]),
        f"§二：{GLM_DOC_PROVIDERS} 个 provider 覆盖，是 failover 论据")

    # S7：vod/tokenhub 的 Price/Provider/Released 全空
    for label, models in (("vod", vod_models), ("tokenhub", th_models)):
        counts = {f: _nonempty_count(models, f) for f in ("Price", "Provider", "Released")}
        add("S7", all(v == 0 for v in counts.values()),
            "%s：%d 条；非空 Price/Provider/Released=%s"
            % (label, len(models), counts),
            "§〇：两个网关的清单没有元数据（0/71、0/116）")

    # S8：可索引规模，与文档 §五 那段复现命令同口径。
    # ★ 两条一起断言：**字节量级** + **文件数区间**。
    #   只比字节的话，扫描范围改小一半仍可能落在 0.85–1.5× 带里（首版正是这样绿的）。
    n_files, n_bytes, scope = _scan_indexable_bytes(repo_root)
    mb = n_bytes / (1024 * 1024)
    ratio = mb / DOC_INDEXABLE_MB if DOC_INDEXABLE_MB else 0
    ok_bytes = INDEXABLE_MIN_RATIO <= ratio <= INDEXABLE_MAX_RATIO
    ok_files = INDEXABLE_MIN_FILES <= n_files <= INDEXABLE_MAX_FILES
    add("S8", ok_bytes and ok_files,
        "可索引 %d 文件 / %.2f MB（文档 %d 文件 / %.1f MB；字节比 %.2f，允许 %.2f–%.2f×；"
        "文件数允许 %d–%d）；%s"
        % (n_files, mb, DOC_INDEXABLE_FILES, DOC_INDEXABLE_MB, ratio,
           INDEXABLE_MIN_RATIO, INDEXABLE_MAX_RATIO,
           INDEXABLE_MIN_FILES, INDEXABLE_MAX_FILES, scope),
        "§五复现命令：%d 文件 / %.1f MB（范围须与 INDEXABLE_ROOTS 逐项相同）"
        % (DOC_INDEXABLE_FILES, DOC_INDEXABLE_MB))

    return {
        "verdict": "red" if reds else "pass",
        "assertions": assertions,
        "reds": reds,
        "untested": [],
        "counts": {
            "vod": len(vod_ids), "tokenhub": len(th_ids),
            "doc_vod": DOC_VOD_COUNT, "doc_tokenhub": DOC_TOKENHUB_COUNT,
        },
    }


def _print_result(result: dict):
    if result["verdict"] == "untested":
        print("⚠ 未测（退出码 2，不是通过，也不是红）：")
        for u in result["untested"]:
            print("   - %s" % u)
        print("   清单是 ~/.cache 缓存，被清掉时只能记未测。")
        return
    for a in result["assertions"]:
        print("%s %s  %s" % ("✅" if a["ok"] else "❌", a["id"], a["reading"]))
        if not a["ok"]:
            print("      文档：%s" % a["doc_ref"])
    print()
    if result["reds"]:
        print("❌ 选型文档有 %d 条断言与实时清单对不上；改文档，不要改脚本自动圆。" % len(result["reds"]))
    else:
        print("✅ S1–S8 全过（清单读数与选型文档一致）")


# ── --controls：构造好/坏清单，证明断言会红 ────────────────────────────────

def _write_manifest(root: Path, global_data: dict, vod_models: list, th_models: list):
    (root / "models").mkdir(parents=True, exist_ok=True)
    (root / "models.json").write_text(json.dumps(global_data, ensure_ascii=False), encoding="utf-8")
    (root / "models" / "vod.json").write_text(
        json.dumps({"fetched": "fixture", "base": "fixture", "models": vod_models}, ensure_ascii=False),
        encoding="utf-8")
    (root / "models" / "tokenhub.json").write_text(
        json.dumps({"fetched": "fixture", "base": "fixture", "models": th_models}, ensure_ascii=False),
        encoding="utf-8")


def _fixture_global(glm_providers: int = 20, glm_audio: bool = False) -> dict:
    out = {}
    for i in range(glm_providers):
        pid = "p%02d" % i
        out[pid] = {"models": {
            "glm-5.3-flash": {
                "id": "glm-5.3-flash",
                "modalities": {"input": ["text", "image", "video"] + (["audio"] if glm_audio else [])},
            },
        }}
    out.setdefault("google", {"models": {}})
    for mid in ("gemini-3.1-flash-lite", "gemini-3.5-flash"):
        out["google"]["models"][mid] = {
            "id": mid,
            "modalities": {"input": ["text", "image", "audio", "video", "pdf"]},
        }
    return out


def _fixture_vod(include_both: bool = True, with_embed: bool = False, price_nonempty: bool = False) -> list:
    models = []
    for mid in (("gemini-3.1-flash-lite", "gemini-3.5-flash") if include_both else ("gemini-3.1-flash-lite",)):
        models.append({"ID": mid, "Price": (1.0 if price_nonempty else None),
                       "Provider": "", "Released": ""})
    if with_embed:
        models.append({"ID": "bge-m3", "Price": None, "Provider": "", "Released": ""})
    models.append({"ID": "some-chat-model", "Price": None, "Provider": "", "Released": ""})
    if price_nonempty and models:
        models[0]["Price"] = 1.0
    return models


def _fixture_tokenhub(asr_count: int = 8) -> list:
    models = [{"ID": "hy-asr-%d" % i, "Price": None, "Provider": "", "Released": ""}
              for i in range(asr_count)]
    models.append({"ID": "some-chat-model", "Price": None, "Provider": "", "Released": ""})
    return models


def _fixture_repo(root: Path, total_bytes: int, n_files: int | None = None):
    """构造「好样本」语料：**文件数要与文档同量级**，不能只堆一个大文件。

    ★ 2026-10-21 更正：首版只写 1 个 `corpus.md`，靠总字节数落在 0.5–2× 带里过关。
      加了文件数断言之后它立刻变红 —— 这是**对照样本本身过期了**，不是断言写错。
      一个只有 1 个文件的「好样本」，恰好就是 S8 要防的那种范围缩水。
      所以这里按 DOC_INDEXABLE_FILES 切分，字节均摊。

    `n_files` 可覆盖，专门用于「字节不变、文件数缩水」的反向对照。
    """
    target_dir = root / "PMO" / "implement"
    target_dir.mkdir(parents=True, exist_ok=True)
    n = max(1, n_files or DOC_INDEXABLE_FILES)
    each = max(1, total_bytes // n)
    for i in range(n):
        with (target_dir / ("corpus-%03d.md" % i)).open("wb") as f:
            f.truncate(each)


def _run_case(name: str, manifest_root: Path, repo_root: Path,
              want_verdict: str, want_red: str | None = None) -> bool:
    result = check(manifest_root, repo_root)
    ok = result["verdict"] == want_verdict
    if want_red:
        ok = ok and any(want_red in r for r in result["reds"])
    print("  %s %s：verdict=%s%s" % (
        "✅" if ok else "❌", name, result["verdict"],
        ("；红里含 %s" % want_red) if want_red else ""))
    if not ok:
        for r in result["reds"][:3]:
            print("       - %s" % r)
        for u in result["untested"][:3]:
            print("       ⚠ %s" % u)
    return ok


def run_controls() -> int:
    print("=" * 72)
    print("verify_model_selection · --controls（构造清单反向对照）")
    print("=" * 72)
    tmp = Path(tempfile.mkdtemp(prefix="model-selection-controls-"))
    ok_all = True
    try:
        good = tmp / "good"
        repo_good = tmp / "repo-good"
        _write_manifest(good, _fixture_global(glm_providers=GLM_DOC_PROVIDERS), _fixture_vod(), _fixture_tokenhub())
        _fixture_repo(repo_good, int(DOC_INDEXABLE_MB * 1024 * 1024))
        ok_all &= _run_case("好样本", good, repo_good, "pass")

        bad = tmp / "bad-embed"
        _write_manifest(bad, _fixture_global(), _fixture_vod(with_embed=True), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：vod 塞 bge-m3", bad, repo_good, "red", "S1")

        bad = tmp / "bad-tokenhub-embed"
        th_with_embed = _fixture_tokenhub() + [
            {"ID": "text-embedding-3-large", "Price": None, "Provider": "", "Released": ""},
        ]
        _write_manifest(bad, _fixture_global(), _fixture_vod(), th_with_embed)
        ok_all &= _run_case("坏样本：tokenhub 塞 embedding", bad, repo_good, "red", "S2")

        bad = tmp / "bad-audio"
        _write_manifest(bad, _fixture_global(glm_audio=True), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：glm 加了 audio", bad, repo_good, "red", "S4")

        bad = tmp / "bad-asr"
        _write_manifest(bad, _fixture_global(), _fixture_vod(), _fixture_tokenhub(asr_count=7))
        ok_all &= _run_case("坏样本：tokenhub ASR 少一条", bad, repo_good, "red", "S3")

        bad = tmp / "bad-providers"
        _write_manifest(bad, _fixture_global(glm_providers=19), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：glm provider 降到 19", bad, repo_good, "red", "S6")

        bad5 = tmp / "bad-providers-5"
        _write_manifest(bad5, _fixture_global(glm_providers=5), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：glm provider 降到 5（差值超出 ±3）", bad5, repo_good, "red", "S6")

        ok26 = tmp / "ok-providers-26"
        _write_manifest(ok26, _fixture_global(glm_providers=26), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("边界样本：glm provider 26（抖动 ±1，必须绿）", ok26, repo_good, "pass")

        bad = tmp / "bad-vod"
        _write_manifest(bad, _fixture_global(), _fixture_vod(include_both=False), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：vod 缺 gemini-3.5-flash", bad, repo_good, "red", "S5")

        bad = tmp / "bad-price"
        _write_manifest(bad, _fixture_global(), _fixture_vod(price_nonempty=True), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：vod Price 非空", bad, repo_good, "red", "S7")

        bad = tmp / "bad-size"
        repo_bad = tmp / "repo-bad"
        _fixture_repo(repo_bad, int(DOC_INDEXABLE_MB * 0.1 * 1024 * 1024))
        _write_manifest(bad, _fixture_global(), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：可索引字节只有 0.1×", bad, repo_bad, "red", "S8")

        # ★ 文件数单独一条反向对照：字节仍是 8.9 MB，但文件数缩到 80。
        #   0.1× 那条只撞字节（149 文件仍在 100–400 内），**不能**证明文件数断言活着。
        bad = tmp / "bad-files"
        repo_bad_files = tmp / "repo-bad-files"
        _fixture_repo(repo_bad_files, int(DOC_INDEXABLE_MB * 1024 * 1024), n_files=80)
        _write_manifest(bad, _fixture_global(), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：字节 8.9MB 但文件数缩到 80", bad, repo_bad_files, "red", "S8")

        # 上限对照：原首版 484 文件的口径就落在这边；字节相同也必须红。
        bad = tmp / "bad-files-hi"
        repo_bad_files_hi = tmp / "repo-bad-files-hi"
        _fixture_repo(repo_bad_files_hi, int(DOC_INDEXABLE_MB * 1024 * 1024), n_files=420)
        _write_manifest(bad, _fixture_global(), _fixture_vod(), _fixture_tokenhub())
        ok_all &= _run_case("坏样本：字节 8.9MB 但文件数涨到 420", bad, repo_bad_files_hi, "red", "S8")

        missing = tmp / "missing"
        missing.mkdir()
        ok_all &= _run_case("清单缺失", missing, repo_good, "untested")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if ok_all:
        print("✅ --controls 全过：好样本绿；坏样本各自红；清单缺失判未测")
        return 0
    print("❌ --controls 有对照不符；断言或对照本身有问题，别当成通过")
    return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--controls" in argv:
        return run_controls()
    result = check(CACHE_ROOT, Path(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))))
    _print_result(result)
    return {"pass": 0, "red": 1, "untested": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
