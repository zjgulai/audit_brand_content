#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_media.py —— 阶段 3 OCR/ASR benchmark harness（零安装、零下载）

## 它回答什么问题

阶段 3 要先回答「候选工具到底行不行」，而不是先接生产。这个脚本只做一件事：
**给定样本目录与 gold 文本，跑工具、算指标、把「测了 / 没测」分开报。**

它**不安装**任何工具、**不下载**任何模型。ASR 侧调用 faster-whisper 时显式
`local_files_only=True`；调用 openai-whisper 前先检查 `~/.cache/whisper/<model>.pt`
是否存在，不存在就记 `untested`，不会触发下载。

## 样本约定

OCR：
    <id>.png | .jpg | .jpeg | .webp
    <id>.gold.txt

ASR：
    <id>.wav | .mp3 | .mp4 | .mov
    <id>.gold.txt

`<id>` 是同一目录下的文件名主干（`foo.png` ↔ `foo.gold.txt`）。没有 gold 的样本
**逐条记 untested**，绝不算成「0 错误」。

## 指标口径

- CER：Unicode 字符级 Levenshtein 距离 / gold 字符数；**空白不计**，标点计入。
- WER：token 级 Levenshtein 距离 / gold token 数。tokenizer 为：
  CJK 逐字、拉丁/数字按连续段、标点与空白不计。对中文等价于字符级 WER ——
  这是为了避免「整句一个 token」让 WER 退化成 0/1。
- `ms`：单样本墙钟耗时（包含一次工具调用；ASR 首样本包含模型加载，后续样本复用模型）。

## 三态（不是二态）

- `tested`：有 gold、工具可跑、拿到了输出并算出了指标。
- `untested`：缺工具 / 缺 gold / gold 为空 / 模型不在本地 / 工具调用失败。
  每一条都带 `reason`，指标字段为 `null`（**不是 0**）。
- 退出码：`0` 表示至少有一条 tested；`2` 表示没有一条 tested（含工具缺失、无样本）；
  `1` 只表示 harness 自身用法/写盘错误。**未测 ≠ 通过 ≠ 红。**

## 用法

    python3 tools/benchmark_media.py --modality ocr --samples /path/to/samples --out /tmp/ocr.json
    python3 tools/benchmark_media.py --modality asr --samples /path/to/samples --out /tmp/asr.json
    python3 tools/benchmark_media.py --self-test

`--self-test` 用合成文本对与假工具/假 runner 验证 CER/WER 与三态语义，
不依赖 tesseract / ffmpeg / whisper，也不读写仓库内文件。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

OCR_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
ASR_EXTS = {".wav", ".mp3", ".mp4", ".mov"}


class UsageError(Exception):
    """CLI 用法错误（退 1；不退 2，2 专留给未测）。"""


class EngineError(Exception):
    """单样本工具调用失败（记 untested，不是红）。"""


# ── 文本与指标 ───────────────────────────────────────────────────────────

def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    return s.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").strip()


def _strip_ws(s: str) -> str:
    return "".join(s.split())


def _levenshtein(a: Any, b: Any) -> int:
    """通用序列编辑距离：字符串按字符，列表按 token。"""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """字符错误率；空白不计。gold 为空时抛 ValueError（调用方记 untested）。"""
    ref = _strip_ws(_norm_text(reference))
    hyp = _strip_ws(_norm_text(hypothesis))
    if not ref:
        raise ValueError("empty_reference")
    return _levenshtein(ref, hyp) / len(ref)


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x3400 <= o <= 0x4DBF
        or 0x4E00 <= o <= 0x9FFF
        or 0xF900 <= o <= 0xFAFF
        or 0x3040 <= o <= 0x30FF
        or 0xAC00 <= o <= 0xD7AF
    )


def _tokens(s: str) -> List[str]:
    """CJK 逐字、拉丁/数字连续段；标点与空白不计。"""
    out: List[str] = []
    buf: List[str] = []
    for ch in _norm_text(s).lower():
        if _is_cjk(ch):
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(ch)
        elif ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                out.append("".join(buf))
                buf = []
    if buf:
        out.append("".join(buf))
    return out


def wer(reference: str, hypothesis: str) -> float:
    """词错误率；tokenizer 见模块 docstring。gold 为空时抛 ValueError。"""
    ref = _tokens(reference)
    hyp = _tokens(hypothesis)
    if not ref:
        raise ValueError("empty_reference")
    return _levenshtein(ref, hyp) / len(ref)


# ── 工具探测（只探测，不安装/不下载） ────────────────────────────────────

def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def probe_tools() -> Dict[str, Dict[str, Any]]:
    tesseract = shutil.which("tesseract")
    ffmpeg = shutil.which("ffmpeg")
    return {
        "tesseract": {"ok": bool(tesseract), "path": tesseract},
        "ffmpeg": {"ok": bool(ffmpeg), "path": ffmpeg},
        "faster_whisper": {"ok": _module_available("faster_whisper")},
        "whisper": {"ok": _module_available("whisper")},
    }


def _ok(tool: Optional[Dict[str, Any]]) -> bool:
    return bool(isinstance(tool, dict) and tool.get("ok"))


def missing_requirements(modality: str, tools: Dict[str, Dict[str, Any]]) -> List[str]:
    missing: List[str] = []
    if modality == "ocr":
        if not _ok(tools.get("tesseract")):
            missing.append("tesseract")
    elif modality == "asr":
        if not _ok(tools.get("ffmpeg")):
            missing.append("ffmpeg")
        if not (_ok(tools.get("faster_whisper")) or _ok(tools.get("whisper"))):
            missing.append("faster_whisper|whisper")
    else:
        raise UsageError("未知 modality: %s" % modality)
    return missing


# ── 样本发现 ─────────────────────────────────────────────────────────────

def sample_paths(modality: str, root: Path) -> List[Path]:
    exts = OCR_EXTS if modality == "ocr" else ASR_EXTS
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in exts
    )


def gold_path_for(sample: Path) -> Path:
    return sample.with_name(sample.stem + ".gold.txt")


# ── 真实工具 runner ──────────────────────────────────────────────────────

def _asr_engine(ctx: Dict[str, Any]):
    tools = ctx["tools"]
    if _ok(tools.get("faster_whisper")):
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise EngineError("faster_whisper_import_failed: %s" % exc) from exc
        try:
            return WhisperModel(
                ctx["model"],
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise EngineError("asr_model_not_local: %s" % exc) from exc

    if _ok(tools.get("whisper")):
        try:
            import whisper  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise EngineError("whisper_import_failed: %s" % exc) from exc
        cache = Path.home() / ".cache" / "whisper" / ("%s.pt" % ctx["model"])
        if not cache.is_file():
            raise EngineError("asr_model_not_local: %s" % cache)
        try:
            return whisper.load_model(
                ctx["model"], device="cpu", download_root=str(cache.parent)
            )
        except Exception as exc:  # noqa: BLE001
            raise EngineError("whisper_load_failed: %s" % exc) from exc

    raise EngineError("no_asr_engine")


def _engine_runner(modality: str, path: Path, ctx: Dict[str, Any]) -> str:
    if modality == "ocr":
        tesseract = ctx["tools"]["tesseract"]["path"]
        try:
            cp = subprocess.run(
                [tesseract, str(path), "stdout", "-l", ctx["ocr_lang"]],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=ctx["timeout"],
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineError("ocr_timeout: %.0fs" % ctx["timeout"]) from exc
        except OSError as exc:
            raise EngineError("ocr_spawn_failed: %s" % exc) from exc
        if cp.returncode != 0:
            raise EngineError(
                "tesseract_rc=%d: %s" % (cp.returncode, (cp.stderr or "")[-300:])
            )
        return cp.stdout

    engine = ctx.get("_asr_engine")
    if engine is None:
        engine = _asr_engine(ctx)
        ctx["_asr_engine"] = engine
    try:
        if _ok(ctx["tools"].get("faster_whisper")):
            segments, _info = engine.transcribe(
                str(path), language=ctx["language"], vad_filter=False
            )
            return "".join(getattr(s, "text", "") for s in segments)
        result = engine.transcribe(str(path), language=ctx["language"], fp16=False)
        return str(result.get("text") or "")
    except Exception as exc:  # noqa: BLE001
        raise EngineError("asr_transcribe_failed: %s" % exc) from exc


# ── 主流程（可注入 probe/runner，自证不依赖真工具） ──────────────────────

Runner = Callable[[str, Path, Dict[str, Any]], str]


def _record(
    modality: str,
    path: Path,
    root: Path,
    *,
    missing: List[str],
    runner: Runner,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    metric_key = "cer" if modality == "ocr" else "wer"
    rec: Dict[str, Any] = {
        "id": path.stem,
        "file": str(path.relative_to(root)),
        metric_key: None,
        "ms": None,
    }
    gold = gold_path_for(path)
    if missing:
        rec["status"] = "untested"
        rec["reason"] = "tool_missing:" + ",".join(missing)
        return rec
    if not gold.is_file():
        rec["status"] = "untested"
        rec["reason"] = "no_gold"
        return rec
    try:
        reference = gold.read_text(encoding="utf-8")
    except OSError as exc:
        rec["status"] = "untested"
        rec["reason"] = "gold_unreadable: %s" % exc
        return rec
    if not _strip_ws(_norm_text(reference)):
        rec["status"] = "untested"
        rec["reason"] = "empty_gold"
        return rec

    t0 = time.perf_counter()
    try:
        hypothesis = runner(modality, path, ctx)
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "untested"
        rec["reason"] = str(exc) or exc.__class__.__name__
        return rec
    ms = round((time.perf_counter() - t0) * 1000.0, 1)

    try:
        if modality == "ocr":
            rec[metric_key] = round(cer(reference, hypothesis), 6)
        else:
            rec[metric_key] = round(wer(reference, hypothesis), 6)
    except ValueError as exc:
        rec["status"] = "untested"
        rec["reason"] = str(exc)
        return rec

    rec["status"] = "tested"
    rec["ms"] = ms
    return rec


def run_benchmark(
    modality: str,
    samples: Path,
    *,
    probe: Optional[Callable[[], Dict[str, Dict[str, Any]]]] = None,
    runner: Optional[Runner] = None,
    ocr_lang: str = "chi_sim+eng",
    model: str = "tiny",
    language: str = "zh",
    timeout: float = 120.0,
) -> Tuple[Dict[str, Any], int]:
    """返回 (report, exit_code)。纯编排，probe/runner 可注入。"""
    if modality not in ("ocr", "asr"):
        raise UsageError("未知 modality: %s" % modality)
    if not samples.is_dir():
        raise UsageError("samples 目录不存在: %s" % samples)

    tools = (probe or probe_tools)()
    missing = missing_requirements(modality, tools)
    paths = sample_paths(modality, samples)
    ctx: Dict[str, Any] = {
        "tools": tools,
        "ocr_lang": ocr_lang,
        "model": model,
        "language": language,
        "timeout": timeout,
        "_asr_engine": None,
    }
    actual_runner: Runner = runner or _engine_runner
    records = [
        _record(modality, p, samples, missing=missing,
                runner=actual_runner, ctx=ctx)
        for p in paths
    ]
    tested = sum(1 for r in records if r["status"] == "tested")
    untested = len(records) - tested
    report: Dict[str, Any] = {
        "modality": modality,
        "tools": tools,
        "missing": missing,
        "samples": records,
        "summary": {"tested": tested, "untested": untested},
        "config": {
            "ocr_lang": ocr_lang,
            "asr_model": model,
            "asr_language": language,
            "timeout_s": timeout,
        },
    }
    if not paths:
        report["note"] = "no_samples"
    if missing or tested == 0:
        return report, 2
    return report, 0


# ── 输出 ─────────────────────────────────────────────────────────────────

def write_report(report: Dict[str, Any], out: Optional[str]) -> None:
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not out:
        print(data, end="")
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


# ── 自证 ─────────────────────────────────────────────────────────────────

def _fake_tools(*, ocr: bool = True, ffmpeg: bool = True,
                faster: bool = True) -> Dict[str, Dict[str, Any]]:
    return {
        "tesseract": {"ok": ocr, "path": "/fake/tesseract" if ocr else None},
        "ffmpeg": {"ok": ffmpeg, "path": "/fake/ffmpeg" if ffmpeg else None},
        "faster_whisper": {"ok": faster},
        "whisper": {"ok": False},
    }


def selftest() -> int:
    passed = 0
    failed: List[str] = []

    def check(cid: str, ok: bool, detail: str = "") -> None:
        nonlocal passed
        if ok:
            passed += 1
            print("PASS: %s" % cid)
        else:
            failed.append("%s %s" % (cid, detail))
            print("FAIL: %s %s" % (cid, detail), file=sys.stderr)

    def close(a: float, b: float) -> bool:
        return abs(a - b) < 1e-9

    # 1) 指标纯函数
    check("T1 CER 完全一致 = 0", close(cer("内容审查", "内容审查"), 0.0))
    check("T2 CER 单字替换 = 0.25", close(cer("内容审查", "内容审核"), 0.25),
          repr(cer("内容审查", "内容审核")))
    check("T3 CER 空白不计", close(cer("内容 审查\n", "内容审查"), 0.0))
    check("T4 CER 标点计入", close(cer("内容。", "内容"), 1.0 / 3.0),
          repr(cer("内容。", "内容")))
    check("T5 WER 英文 1 词错 = 0.5",
          close(wer("hello world", "hello would"), 0.5))
    check("T6 WER 中文逐字 = 0.25",
          close(wer("内容审查", "内容审核"), 0.25))
    check("T7 WER 忽略大小写/标点",
          close(wer("Hello, world!", "hello world"), 0.0))
    check("T8 空 gold 抛 ValueError",
          _raises(lambda: cer("", "x")) and _raises(lambda: wer("", "x")))

    no_call = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("工具缺失时不许调用 runner"))

    with tempfile.TemporaryDirectory(prefix="benchmark_media_selftest_") as td:
        base = Path(td)
        root = base / "ocr"
        root.mkdir()
        (root / "ocr_good.png").write_bytes(b"not-an-image")
        (root / "ocr_good.gold.txt").write_text("内容审查", encoding="utf-8")
        (root / "ocr_nogold.png").write_bytes(b"not-an-image")

        # 2) 有 gold + 工具在 → tested；无 gold → untested 且指标为 null
        report, rc = run_benchmark(
            "ocr", root, probe=lambda: _fake_tools(),
            runner=lambda *_a: "内容审查")
        by_id = {r["id"]: r for r in report["samples"]}
        check("T9 有 gold+工具 → tested 且 CER=0",
              rc == 0 and by_id["ocr_good"]["status"] == "tested"
              and by_id["ocr_good"].get("cer") == 0.0,
              repr(report["summary"]))
        check("T10 无 gold → untested，不是 0 分",
              by_id["ocr_nogold"]["status"] == "untested"
              and by_id["ocr_nogold"].get("cer") is None
              and by_id["ocr_nogold"].get("reason") == "no_gold",
              repr(by_id.get("ocr_nogold")))
        check("T11 部分 tested 时 summary 不把 untested 算成 tested",
              report["summary"] == {"tested": 1, "untested": 1},
              repr(report["summary"]))

        # 3) 只有无 gold → tested=0，退 2（未测不是通过）
        only_nogold = base / "only_nogold"
        only_nogold.mkdir()
        (only_nogold / "a.png").write_bytes(b"x")
        report2, rc2 = run_benchmark(
            "ocr", only_nogold, probe=lambda: _fake_tools(),
            runner=lambda *_a: "x")
        check("T12 全无 gold → tested=0 且退 2",
              rc2 == 2 and report2["summary"] == {"tested": 0, "untested": 1},
              repr(report2["summary"]))

        # 4) 工具缺失 → 整体 untested，退 2，且 runner 一次都不跑
        report3, rc3 = run_benchmark(
            "ocr", root, probe=lambda: _fake_tools(ocr=False),
            runner=no_call)
        check("T13 工具缺失 → 退 2 且 missing 指明 tesseract",
              rc3 == 2 and report3["missing"] == ["tesseract"],
              repr(report3.get("missing")))
        check("T14 工具缺失 → 每条 untested，不是 0 条/通过",
              all(r["status"] == "untested" for r in report3["samples"])
              and report3["summary"] == {"tested": 0, "untested": 2},
              repr(report3["summary"]))
        check("T15 工具缺失时指标为 null（不是 0）",
              all(r.get("cer") is None and r.get("ms") is None
                  for r in report3["samples"]))

        # 5) ASR：有 gold + 假 runner → WER；缺 ffmpeg → 2
        asr = base / "asr"
        asr.mkdir()
        (asr / "a.wav").write_bytes(b"x")
        (asr / "a.gold.txt").write_text("hello world", encoding="utf-8")
        report4, rc4 = run_benchmark(
            "asr", asr, probe=lambda: _fake_tools(),
            runner=lambda *_a: "hello would")
        check("T16 ASR 有 gold → WER=0.5",
              rc4 == 0 and report4["samples"][0].get("wer") == 0.5,
              repr(report4["samples"][0]))
        report5, rc5 = run_benchmark(
            "asr", asr, probe=lambda: _fake_tools(ffmpeg=False),
            runner=no_call)
        check("T17 ASR 缺 ffmpeg → 退 2 且 missing 指明 ffmpeg",
              rc5 == 2 and "ffmpeg" in report5["missing"],
              repr(report5.get("missing")))
        report5b, rc5b = run_benchmark(
            "asr", asr, probe=lambda: _fake_tools(faster=False),
            runner=no_call)
        check("T17b ASR 缺引擎 → 退 2 且 missing 指明 faster_whisper|whisper",
              rc5b == 2 and "faster_whisper|whisper" in report5b["missing"],
              repr(report5b.get("missing")))

        # 6) 无样本目录 → tested=0，退 2
        empty = base / "empty"
        empty.mkdir()
        report6, rc6 = run_benchmark(
            "ocr", empty, probe=lambda: _fake_tools(),
            runner=no_call)
        check("T18 无样本 → tested=0，退 2",
              rc6 == 2 and report6["summary"] == {"tested": 0, "untested": 0}
              and report6.get("note") == "no_samples",
              repr(report6))

    total = passed + len(failed)
    print("\n%s benchmark_media --self-test %d 项检查 · %d 项红"
          % ("✅" if not failed else "❌", total, len(failed)))
    for f in failed:
        print("  ❌ " + f, file=sys.stderr)
    return 0 if not failed else 1


def _raises(fn: Callable[[], Any]) -> bool:
    try:
        fn()
    except ValueError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


# ── CLI ──────────────────────────────────────────────────────────────────

class _Parser(argparse.ArgumentParser):
    """用法错误退 1；2 专留给「未测」。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        raise UsageError(message)


def main(argv: Optional[List[str]] = None) -> int:
    ap = _Parser(description="阶段 3 OCR/ASR benchmark harness（零安装、零下载）")
    ap.add_argument("--modality", choices=("ocr", "asr"))
    ap.add_argument("--samples")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true",
                    help="用合成文本对与假工具验证指标与三态语义")
    ap.add_argument("--ocr-lang", default="chi_sim+eng")
    ap.add_argument("--asr-model", default="tiny")
    ap.add_argument("--asr-language", default="zh")
    ap.add_argument("--timeout", type=float, default=120.0)
    try:
        args = ap.parse_args(argv)
        if args.self_test:
            return selftest()
        if not args.modality or not args.samples:
            raise UsageError("正常跑法需要 --modality 与 --samples；自证用 --self-test")
        report, rc = run_benchmark(
            args.modality, Path(args.samples),
            ocr_lang=args.ocr_lang, model=args.asr_model,
            language=args.asr_language, timeout=args.timeout,
        )
    except UsageError as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 1

    try:
        write_report(report, args.out)
    except OSError as exc:
        print("❌ 写输出失败：%s" % exc, file=sys.stderr)
        return 1

    s = report["summary"]
    print(
        "modality=%s tested=%d untested=%d missing=%s%s"
        % (report["modality"], s["tested"], s["untested"],
           ",".join(report["missing"]) or "none",
           (" note=%s" % report["note"]) if report.get("note") else ""),
        file=sys.stderr,
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
