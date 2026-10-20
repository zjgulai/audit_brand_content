#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gold_sample_check.py —— gold 试点样本的配对与可读性自检（阶段 3 · 10 OCR + 5 ASR）

**它是什么**：在把样本交给 `tools/benchmark_media.py` 算准确率**之前**，
先回答一个更基础的问题：**这批样本齐不齐、读不读得出来。**

**它不是什么**：它不跑 OCR/ASR、不算 CER/WER、不下载任何模型、不安装任何工具。
它只读文本与文件头，**零依赖**（纯标准库）。

--------------------------------------------------------------------------
★ 三条本文件刻意做死的事
--------------------------------------------------------------------------

**一、缺配对的样本必须逐条报，不许静默跳过**

    只报一个「15 个样本」的计数，读的人会以为「15 个都对」。
    而真实情况可能是「20 个文件里有 5 个没有 gold」。
    ★ 这正是 `benchmark_media.py` 里「没有 gold 记 untested 而不是 0 错误」
      的同一条纪律，只是提前到样本准备阶段。

**二、不认识的扩展名要报出来，不许当它不存在**

    一个 `.tiff` 会被 `benchmark_media.py` 静默忽略（它只认 png/jpg/jpeg/webp）。
    如果本检查器也忽略它，报告会写「全部配对，很好」，而那张图**从没被检查过**。
    所以：未知扩展名 → 逐条列出 + 退 1。

**三、三态退出码，与全项目一致**

    0  全部配对且可读
    1  有缺失 / 有坏 gold / manifest 不合格
    2  目录不存在或读不出 —— **未测不是通过**

用法
----
    # 只看这批样本齐不齐
    python3 tools/gold_sample_check.py --samples /path/to/stage3-samples

    # 带 manifest 校验（每个文件要有 sha256，路径必须在仓外）
    python3 tools/gold_sample_check.py --samples /path/to/stage3-samples \\
        --manifest /path/to/stage3-samples/manifest.csv

    # 自证（用 /tmp 造好坏两组样本，不碰任何真实数据）
    python3 tools/gold_sample_check.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ★ 与 `tools/benchmark_media.py` 的 OCR_EXTS / ASR_EXTS **必须一致**。
#   两边不一致会造成一个很难查的分裂：本检查器说「齐了」，benchmark 却认为
#   那张图根本不存在。改这里就要同步改那边（自证里有断言钉这条）。
OCR_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
ASR_EXTS = {".wav", ".mp3", ".mp4", ".mov"}
MEDIA_EXTS = OCR_EXTS | ASR_EXTS

GOLD_SUFFIX = ".gold.txt"
BOM = b"\xef\xbb\xbf"

# ★ 除了 gold，样本目录里还会有两类**合法**旁挂文件：
#     · 需求文档里写的可选 `<id>.bbox.json` / `<id>.timecode.json`（本版 harness 不消费）
#     · manifest 自己（csv/json）—— 它通常就放在样本目录里
#   不把它们排除掉，「未知扩展名」会天天报它们，然后没人看这个报告。
#   （§2.1.1：一个会误报的检查器比没有检查器更糟。）
SIDECAR_SUFFIXES = (".gold.txt", ".bbox.json", ".timecode.json")
MANIFEST_NAMES = ("manifest.csv", "manifest.json")

# manifest 里每条记录必须具备的字段
MANIFEST_REQUIRED = ("path", "sha256")


class CheckError(Exception):
    """输入层面读不出 —— 对应退出码 2（未测）。"""


# ═══════════════════════ ① 文件发现 ═══════════════════════

def discover(root: Path, manifest: Path | None = None) -> dict:
    """
    扫一遍目录，把文件分成三类：媒体 / gold / 其他。

    ★ `其他` 不是垃圾桶 —— 它会被逐条报出来（见文件头第二条）。
      但**已知的旁挂文件**（gold 的可选 JSON、manifest 自己）不算「其他」，
      否则报告会天天报它自己，读的人就不看了。
    """
    if not root.exists():
        raise CheckError("目录不存在：%s" % root)
    if not root.is_dir():
        raise CheckError("不是目录：%s" % root)
    try:
        entries = list(root.rglob("*"))
    except OSError as e:
        raise CheckError("目录读不出：%s（%s）" % (root, e))

    man_resolved = None
    if manifest is not None:
        try:
            man_resolved = manifest.resolve()
        except OSError:
            man_resolved = None

    media, golds, others = [], [], []
    for p in entries:
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(GOLD_SUFFIX):
            golds.append(p)
        elif p.suffix.lower() in MEDIA_EXTS:
            media.append(p)
        elif name.endswith(SIDECAR_SUFFIXES) or name in MANIFEST_NAMES:
            continue          # 合法旁挂，不是样本
        elif man_resolved is not None and _safe_resolve(p) == man_resolved:
            continue          # manifest 用的是非常规文件名，也要排除
        else:
            others.append(p)
    return {"media": sorted(media), "golds": sorted(golds),
            "others": sorted(others)}


def _safe_resolve(p: Path) -> Path | None:
    try:
        return p.resolve()
    except OSError:
        return None


def _gold_for(media: Path) -> Path:
    """与 `benchmark_media.py` 的 `gold_path_for()` 同一口径。"""
    return media.with_name(media.stem + GOLD_SUFFIX)


def _id_of_gold(gold: Path) -> str:
    return gold.name[:-len(GOLD_SUFFIX)]


# ═══════════════════════ ② gold 文本校验 ═══════════════════════

def check_gold(gold: Path) -> list:
    """
    检查一个 `.gold.txt`。返回问题清单，空 = 没问题。

    四条，各自独立，**不许合并成一句「gold 有问题」** ——
    因为修法完全不同：有 BOM 去掉就行；不是 UTF-8 要重存；
    空的说明还没写；只有空白的说明写了但没内容。
    """
    problems = []
    try:
        raw = gold.read_bytes()
    except OSError as e:
        return ["读不出（%s）" % e]

    if raw.startswith(BOM):
        problems.append("有 BOM（应当是无 BOM 的 UTF-8）")

    body = raw[len(BOM):] if raw.startswith(BOM) else raw

    if not body:
        problems.append("为空（0 字节）")
        return problems        # 空的不用再判编码了

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as e:
        problems.append("不是合法 UTF-8（第 %d 字节起：%s）"
                        % (e.start, e.reason))
        return problems

    if not text.strip():
        problems.append("只有空白字符（等于没写）")

    return problems


# ═══════════════════════ ③ manifest 校验 ═══════════════════════

def _load_manifest(path: Path) -> list:
    """
    读 manifest。支持 CSV 与 JSON 两种（CSV 按 `阶段3-gold样本需求.md` 的建议格式，
    但**在它基础上要求 `path` 与 `sha256` 两列**）。

    读不出 → 抛 CheckError（退 2）。这不是「manifest 有问题」，是「没测到」。
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise CheckError("manifest 读不出：%s（%s）" % (path, e))
    except UnicodeDecodeError as e:
        raise CheckError("manifest 不是合法 UTF-8：%s（%s）" % (path, e))

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
        except ValueError as e:
            raise CheckError("manifest 不是合法 JSON：%s（%s）" % (path, e))
        if isinstance(data, dict):
            data = data.get("samples") or data.get("items") or []
        if not isinstance(data, list):
            raise CheckError("manifest JSON 的顶层应当是数组或含 samples 的对象")
        return [r for r in data if isinstance(r, dict)]

    try:
        rows = list(csv.DictReader(io.StringIO(raw)))
    except csv.Error as e:
        raise CheckError("manifest CSV 读不出：%s（%s）" % (path, e))
    return [r for r in rows if isinstance(r, dict)]


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _inside_repo(p: Path) -> bool:
    """路径是否落在仓库内。与 `base/takedown.py` 的仓外判定同一口径。"""
    try:
        rp = p.resolve()
        root = ROOT.resolve()
    except OSError:
        return False
    return rp == root or root in rp.parents


def check_manifest(manifest: Path, base_dir: Path) -> list:
    """
    校验 manifest。返回问题清单，空 = 没问题。

    每条记录要满足：
      · 有 `path` 与 `sha256` 两个字段（缺哪个报哪个）
      · `path` 指向的文件存在
      · `path` **在仓库外** —— 仓库是公开的，样本与逐字稿不许进
      · 实际 sha256 与声明一致（否则这份 manifest 是过期的）

    ★ 为什么要核对 sha256 而不是只看「写了没有」：
      一个写错的 sha256 与一个正确的长得一样，而它会让「这份 manifest 对应哪批文件」
      变成一句没人能验证的话。
    """
    problems = []
    try:
        rows = _load_manifest(manifest)
    except CheckError:
        raise

    if not rows:
        return ["manifest 是空的（0 条记录）"]

    for i, row in enumerate(rows, 1):
        label = row.get("id") or row.get("path") or "#%d" % i

        missing = [k for k in MANIFEST_REQUIRED
                   if not str(row.get(k) or "").strip()]
        if missing:
            problems.append("%s：缺字段 %s" % (label, missing))
            continue

        raw_path = str(row["path"]).strip()
        p = Path(raw_path)
        if not p.is_absolute():
            p = base_dir / p

        if _inside_repo(p):
            problems.append("%s：路径在仓库内（%s）—— 公开仓不许放样本"
                            % (label, raw_path))
            continue

        if not p.is_file():
            problems.append("%s：文件不存在（%s）" % (label, raw_path))
            continue

        declared = str(row["sha256"]).strip().lower()
        try:
            actual = _sha256_of(p)
        except OSError as e:
            problems.append("%s：读不出，无法核对 sha256（%s）" % (label, e))
            continue
        if declared != actual:
            problems.append("%s：sha256 不一致（声明 %s… / 实际 %s…）"
                            % (label, declared[:12], actual[:12]))

    return problems


# ═══════════════════════ ④ 总检查 ═══════════════════════

def check(root: Path, manifest: Path | None = None) -> dict:
    """
    跑一遍完整检查。返回结构化结果：

      {
        "root": str,
        "media": int, "golds": int, "paired": int,
        "missing_gold": [{"file":..., "expect":...}],
        "orphan_gold": [{"file":..., "expect":...}],
        "bad_gold": [{"file":..., "problems":[...]}],
        "unknown_ext": [str],
        "duplicate_id": [{"id":..., "files":[...]}],
        "manifest": {"path":..., "problems":[...]} | None,
        "problems_total": int,
        "untested": bool,
        "untested_reason": str,
      }
    """
    info = discover(root, manifest)
    media, golds = info["media"], info["golds"]

    gold_by_name = {g.name: g for g in golds}
    media_by_name = {m.name: m for m in media}

    missing_gold, bad_gold, used_golds = [], [], set()
    for m in media:
        g = _gold_for(m)
        if g.name not in gold_by_name:
            missing_gold.append({"file": str(m.relative_to(root)),
                                 "expect": g.name})
            continue
        used_golds.add(g.name)
        probs = check_gold(gold_by_name[g.name])
        if probs:
            bad_gold.append({"file": str(g.relative_to(root)), "problems": probs})

    # 反向：有 gold 但没有对应媒体（多半是改过文件名，或者没交付媒体）
    orphan_gold = []
    for g in golds:
        gid = _id_of_gold(g)
        if not any(m.stem == gid for m in media):
            orphan_gold.append({"file": str(g.relative_to(root)),
                                "expect": "%s.<媒体扩展名>" % gid})

    # 同 id 多个媒体 → 配对歧义（两个文件都想用同一份 gold）
    by_stem = {}
    for m in media:
        by_stem.setdefault(m.stem, []).append(m.name)
    duplicate_id = [{"id": sid, "files": sorted(names)}
                    for sid, names in sorted(by_stem.items()) if len(names) > 1]

    unknown_ext = [str(p.relative_to(root)) for p in info["others"]]

    man = None
    if manifest is not None:
        man = {"path": str(manifest)}

    result = {
        "root": str(root),
        "media": len(media), "golds": len(golds),
        "paired": len(media) - len(missing_gold),
        "missing_gold": missing_gold,
        "orphan_gold": orphan_gold,
        "bad_gold": bad_gold,
        "unknown_ext": unknown_ext,
        "duplicate_id": duplicate_id,
        "manifest": man,
        "untested": False,
        "untested_reason": "",
    }

    if manifest is not None:
        try:
            man["problems"] = check_manifest(manifest, manifest.parent)
        except CheckError as e:
            result["untested"] = True
            result["untested_reason"] = str(e)
            man["problems"] = []

    result["problems_total"] = (
        len(missing_gold) + len(orphan_gold) + len(bad_gold)
        + len(unknown_ext) + len(duplicate_id)
        + len((man or {}).get("problems") or []))
    return result


# ═══════════════════════ ⑤ 输出 ═══════════════════════

def report(result: dict) -> None:
    print("=" * 74)
    print("gold 样本自检")
    print("=" * 74)
    print("  目录：%s" % result["root"])
    print("  媒体 %d · gold %d · 配对 %d · 缺 gold %d · 孤儿 gold %d"
          % (result["media"], result["golds"], result["paired"],
             len(result["missing_gold"]), len(result["orphan_gold"])))
    print()

    for d in result["missing_gold"]:
        print("  ✗ %s  缺 gold（应为 %s）" % (d["file"], d["expect"]))
    for d in result["orphan_gold"]:
        print("  ✗ %s  没有对应媒体（应为 %s）" % (d["file"], d["expect"]))
    for d in result["bad_gold"]:
        for p in d["problems"]:
            print("  ✗ %s  %s" % (d["file"], p))
    for d in result["duplicate_id"]:
        print("  ✗ id %r 有多个媒体，配对歧义：%s" % (d["id"], d["files"]))
    for f in result["unknown_ext"]:
        print("  ✗ %s  扩展名不在允许列表内 —— 它不会被当成样本检查" % f)

    man = result.get("manifest")
    if man:
        print()
        print("  manifest：%s" % man["path"])
        if man.get("problems"):
            for p in man["problems"]:
                print("    ✗ %s" % p)
        else:
            print("    ✓ 每条都有 sha256、路径在仓外、指纹一致")
    print()


# ═══════════════════════ ⑥ 自证 ═══════════════════════

def self_test() -> int:
    """
    自证：用 /tmp 构造**好 / 坏**两组样本，断言三态。

    ★ 这里造的是**测试夹具**（几十字节的假文件），不是 gold 样本本身。
      真实 gold 必须人工标注 —— 本自证只在临时目录里跑，跑完就删。
    """
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def write(p: Path, data) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            p.write_text(data, encoding="utf-8")

    def run(root: Path, manifest=None) -> int:
        try:
            r = check(root, manifest)
        except CheckError as e:
            print("    ⚠ 未测：%s" % e)
            return 2
        if r["untested"]:
            print("    ⚠ 未测：%s" % r["untested_reason"])
            return 2
        return 0 if r["problems_total"] == 0 else 1

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        # ── ① 好样本：必须退 0 ──
        good = base / "good"
        write(good / "ocr_clear_001.png", b"\x89PNG fake")
        write(good / "ocr_clear_001.gold.txt", "美白精华 买一送一")
        write(good / "asr_clean_001.wav", b"RIFF fake")
        write(good / "asr_clean_001.gold.txt", "这是逐字稿")
        ok("S1 ★ 全部配对且可读 → 退 0", run(good) == 0, "")

        # ── ② 缺 gold ──
        miss = base / "miss"
        write(miss / "ocr_a.png", b"x")
        write(miss / "ocr_b.png", b"x")
        write(miss / "ocr_b.gold.txt", "有 gold")
        ok("S2 ★ 缺 gold → 退 1", run(miss) == 1, "")

        # ── ③ 孤儿 gold ──
        orphan = base / "orphan"
        write(orphan / "ocr_a.png", b"x")
        write(orphan / "ocr_a.gold.txt", "ok")
        write(orphan / "ocr_gone.gold.txt", "没有媒体")
        ok("S3 ★ 有 gold 无媒体 → 退 1", run(orphan) == 1, "")

        # ── ④ BOM ──
        bom = base / "bom"
        write(bom / "ocr_a.png", b"x")
        write(bom / "ocr_a.gold.txt", BOM + "带 BOM 的文本".encode("utf-8"))
        ok("S4 ★ gold 有 BOM → 退 1", run(bom) == 1, "")

        # ── ⑤ 空文件 ──
        empty = base / "empty"
        write(empty / "ocr_a.png", b"x")
        write(empty / "ocr_a.gold.txt", b"")
        ok("S5 ★ gold 为 0 字节 → 退 1", run(empty) == 1, "")

        # ── ⑥ 只有空白 ──
        blank = base / "blank"
        write(blank / "ocr_a.png", b"x")
        write(blank / "ocr_a.gold.txt", "  \n\t\n ")
        ok("S6 ★ gold 只有空白 → 退 1", run(blank) == 1, "")

        # ── ⑦ 非法 UTF-8（GBK 编码的中文）──
        gbk = base / "gbk"
        write(gbk / "ocr_a.png", b"x")
        write(gbk / "ocr_a.gold.txt", "中文".encode("gbk"))
        ok("S7 ★ gold 不是 UTF-8 → 退 1", run(gbk) == 1, "")

        # ── ⑧ 目录不存在 → 退 2（未测，不是失败）──
        ok("S8 ★ 目录不存在 → 退 2（未测）",
           run(base / "no_such_dir") == 2, "")

        # ── ⑨ 未知扩展名必须报出来，不许当它不存在 ──
        unk = base / "unk"
        write(unk / "ocr_a.png", b"x")
        write(unk / "ocr_a.gold.txt", "ok")
        write(unk / "ocr_b.tiff", b"x")          # benchmark 不认这个
        write(unk / "ocr_b.gold.txt", "ok")
        r_unk = check(unk)
        # ★ 这里**两件事都该报**：`.tiff` 不被认作样本；它的 gold 因此成了孤儿。
        #   只报其中一件会让另一半悄悄消失 —— 所以断言总数是 2，且两类都在。
        ok("S9 ★ 未知扩展名 → 退 1，且连带报出它的孤儿 gold",
           r_unk["problems_total"] == 2
           and r_unk["unknown_ext"] == ["ocr_b.tiff"]
           and len(r_unk["orphan_gold"]) == 1,
           "unknown=%r orphan=%r" % (r_unk["unknown_ext"], r_unk["orphan_gold"]))

        # ── ⑩ 配对歧义：同 id 两个媒体 ──
        dup = base / "dup"
        write(dup / "ocr_a.png", b"x")
        write(dup / "ocr_a.jpg", b"x")
        write(dup / "ocr_a.gold.txt", "ok")
        r_dup = check(dup)
        ok("S10 ★ 同 id 多个媒体 → 退 1（配对歧义）",
           bool(r_dup["duplicate_id"]), str(r_dup["duplicate_id"]))

        # ── ⑪ manifest：正确 ──
        man_dir = base / "with_manifest"
        write(man_dir / "ocr_a.png", b"x")
        write(man_dir / "ocr_a.gold.txt", "ok")
        sha = _sha256_of(man_dir / "ocr_a.png")
        man_csv = man_dir / "manifest.csv"
        man_csv.write_text(
            "id,modality,layer,source,authorization,pii_redacted,path,sha256\n"
            "ocr_a,ocr,clear,catalog,业务提供,yes,ocr_a.png,%s\n" % sha,
            encoding="utf-8")
        ok("S11 ★ manifest 合格（sha256 对、路径仓外）→ 退 0",
           run(man_dir, man_csv) == 0, "")

        # ── ⑫ manifest：sha256 不一致 ──
        man_bad = man_dir / "manifest_bad.csv"
        man_bad.write_text(
            "path,sha256\nocr_a.png,%s\n" % ("0" * 64), encoding="utf-8")
        ok("S12 ★ manifest sha256 不一致 → 退 1",
           run(man_dir, man_bad) == 1, "")

        # ── ⑬ manifest：路径在仓库内 ──
        in_repo = man_dir / "manifest_inrepo.csv"
        in_repo.write_text(
            "path,sha256\n%s,%s\n" % (ROOT / "tools" / "gold_sample_check.py", sha),
            encoding="utf-8")
        r_in = check(man_dir, in_repo)
        ok("S13 ★ manifest 路径在仓库内 → 拒",
           any("仓库内" in p for p in r_in["manifest"]["problems"]),
           str(r_in["manifest"]["problems"]))

        # ── ⑭ manifest：缺 sha256 ──
        man_nosh = man_dir / "manifest_nosh.csv"
        man_nosh.write_text("path\nocr_a.png\n", encoding="utf-8")
        ok("S14 ★ manifest 缺 sha256 → 退 1", run(man_dir, man_nosh) == 1, "")

        # ── ⑮ manifest 本身读不出 → 退 2（未测，不是「不合格」）──
        man_broken = man_dir / "manifest_broken.json"
        man_broken.write_text("{不是 json", encoding="utf-8")
        ok("S15 ★ manifest 读不出 → 退 2（未测，不是失败）",
           run(man_dir, man_broken) == 2, "")

        # ── ⑯ 扩展名口径与 benchmark_media 必须一致 ──
        try:
            src = (ROOT / "tools" / "benchmark_media.py").read_text(encoding="utf-8")
            same = ("OCR_EXTS = {\".png\", \".jpg\", \".jpeg\", \".webp\"}" in src
                    and "ASR_EXTS = {\".wav\", \".mp3\", \".mp4\", \".mov\"}" in src)
        except OSError:
            same = False
        ok("S16 ★ 扩展名与 benchmark_media.py 一致（否则两边会分裂）",
           same, "benchmark_media.py 的 EXTS 与预期不同")

        # ── ⑰ 子目录递归（ocr/ 与 asr/ 分开交付）──
        nested = base / "nested"
        write(nested / "ocr" / "a.png", b"x")
        write(nested / "ocr" / "a.gold.txt", "ok")
        write(nested / "asr" / "b.wav", b"x")
        write(nested / "asr" / "b.gold.txt", "ok")
        ok("S17 按 ocr/ asr/ 分子目录交付也能对上", run(nested) == 0, "")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 74)
    print("gold_sample_check · 自证")
    print("=" * 74)
    for name, p, detail in results:
        print("  %s %-52s %s" % ("✓" if p else "✗", name, detail))
    print()
    if passed == total:
        print("✅ %d/%d 项全过" % (passed, total))
        return 0
    print("✗ %d/%d 项通过；红项：%s"
          % (passed, total, [n for n, p, _ in results if not p]),
          file=sys.stderr)
    return 1


# ═══════════════════════ ⑦ CLI ═══════════════════════

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="gold 试点样本自检：配对 / UTF-8 / BOM / manifest / 仓外")
    ap.add_argument("--samples", help="样本目录（可含 ocr/ asr/ 子目录）")
    ap.add_argument("--manifest", default=None,
                    help="manifest.csv 或 manifest.json（可选）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--self-test", action="store_true", default=False)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    ns = ap.parse_args(argv)

    if ns.self_test:
        return self_test()

    if not ns.samples:
        ap.print_usage(sys.stderr)
        print("⚠ 未测：--samples 必填", file=sys.stderr)
        return 2

    manifest = Path(ns.manifest) if ns.manifest else None
    try:
        result = check(Path(ns.samples), manifest)
    except CheckError as e:
        print("⚠ 未测：%s" % e, file=sys.stderr)
        return 2

    if ns.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        report(result)

    if result["untested"]:
        print("⚠ 未测：%s" % result["untested_reason"], file=sys.stderr)
        return 2
    if result["problems_total"]:
        print("✗ %d 个问题 —— 这份样本还不能交给 benchmark"
              % result["problems_total"], file=sys.stderr)
        return 1
    print("✅ 全部配对且可读，可以交给 benchmark_media.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("UNTESTED: 检查器自身异常: %s: %s" % (type(exc).__name__, exc))
        sys.exit(2)
