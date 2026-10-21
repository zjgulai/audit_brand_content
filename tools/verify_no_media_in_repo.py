#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧 DL-3 兼容入口；现行唯一治理门是 verify_download_governance.py。

本文件已被 DG-1…DG-6 取代（AGENTS.md §2.6 与 coverage 登记均如此声明），
只为历史调用者保留三态输出：

- 仓内受控内容：直接调用现行 DG-3，不维护第二份二进制判据；
- AUDIT_MEDIA_ROOT：未配置/不存在记未测，仓内或权限错误才记红；
- 反向对照：临时仓里未登记 PNG 必须红，登记正确 sha256 后必须绿。

退出码：有红 1 / 只有未测 2 / 全部有读数且通过 0。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import verify_download_governance as DG  # noqa: E402

DOWNLOAD_ROOT_ENV = "AUDIT_MEDIA_ROOT"

# 旧实现按扩展名列出的候选数只作解释，不再参与判决。
MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".pdf",
    ".zip", ".rar", ".7z", ".tar", ".gz",
}

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 24


def state_of(result: dict) -> str:
    if result.get("reds"):
        return "fail"
    if result.get("untested"):
        return "untested"
    return "pass"


def legacy_extension_candidates(tracked: list[str]) -> list[str]:
    """旧按扩展名口径，仅用于解释旧报告的“17 个”；不作合规判决。"""
    return sorted(rel for rel in tracked
                  if os.path.splitext(rel)[1].lower() in MEDIA_EXTS)


def check_download_root(root: Path, env=None) -> tuple[str, str]:
    """旧 AUDIT_MEDIA_ROOT 兼容读数；取不到必须是未测。"""
    values = os.environ if env is None else env
    raw = str(values.get(DOWNLOAD_ROOT_ENV, "")).strip()
    if not raw:
        return "untested", "未配置 %s → 不判定（未测，不是通过）" % DOWNLOAD_ROOT_ENV
    path = Path(raw).expanduser().resolve()
    try:
        path.relative_to(root.resolve())
        return "fail", "下载数据根在仓库内"
    except ValueError:
        pass
    if not path.exists():
        return "untested", "下载数据根不存在 → 不判定（未测）"
    if not path.is_dir():
        return "fail", "下载数据根不是目录"
    mode = path.stat().st_mode & 0o777
    if mode != 0o700:
        return "fail", "下载数据根权限是 %s，应为 0o700" % oct(mode)
    return "pass", "下载数据根在仓外且权限 0700"


def reverse_control() -> dict:
    """同一 DG-3 判据：坏样本必须红，正确登记后必须绿。"""
    with tempfile.TemporaryDirectory(prefix="legacy-dl3-control-") as temp:
        root = Path(temp)
        probe = root / "probe.txt"  # 后缀伪装成文本，必须靠 magic bytes 抓到。
        probe.write_bytes(_PNG_BYTES)
        tracked = ["probe.txt"]
        bad = DG.evaluate_dg3(
            root, tracked=tracked, baseline={"assets": {}}, include_history=False)
        approved = DG.evaluate_dg3(
            root, tracked=tracked,
            baseline={"assets": {"probe.txt": {
                "source": "反向对照固定样本",
                "approved_by": "反向对照",
                "sha256": hashlib.sha256(_PNG_BYTES).hexdigest(),
            }}},
            include_history=False)
    ok = bool(bad.get("reds")) and not bad.get("untested") \
        and state_of(approved) == "pass"
    return {
        "ok": ok,
        "bad_state": state_of(bad),
        "bad_reds": len(bad.get("reds") or []),
        "approved_state": state_of(approved),
        "detail": "未登记 PNG→%s（红 %d）；登记正确 sha256→%s" % (
            state_of(bad), len(bad.get("reds") or []), state_of(approved)),
    }


def evaluate(repo_root=ROOT, env=None, include_history=True) -> dict:
    tracked, discovery_note = DG.discover_tracked(repo_root)
    if tracked is None:
        dg3 = {"id": "DG-3", "ok": False, "reds": [],
               "untested": [discovery_note], "detail": discovery_note,
               "tracked_files": 0}
        candidates = []
    else:
        dg3 = DG.evaluate_dg3(
            repo_root, tracked=tracked, include_history=include_history)
        candidates = legacy_extension_candidates(tracked)
    root_state, root_detail = check_download_root(Path(repo_root), env=env)
    control = reverse_control()

    reds = list(dg3.get("reds") or [])
    if root_state == "fail":
        reds.append(root_detail)
    if not control["ok"]:
        reds.append("反向对照失效：" + control["detail"])
    untested = list(dg3.get("untested") or [])
    if root_state == "untested":
        untested.append(root_detail)

    return {
        "schema_version": "legacy-dl3-wrapper/v2",
        "deprecated": True,
        "replacement": "tools/verify_download_governance.py",
        "dg3": {**dg3, "state": state_of(dg3)},
        "legacy_extension_candidates": {
            "count": len(candidates),
            "note": "仅解释旧扩展名读数；是否允许由 DG-3 + asset_baseline 判定",
        },
        "download_root": {"state": root_state, "detail": root_detail},
        "reverse_control": control,
        "reds": reds,
        "untested": untested,
        "verdict": "fail" if reds else ("untested" if untested else "pass"),
    }


def report(result: dict, as_json=False) -> int:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("=" * 66)
        print("旧 DL-3 兼容入口（deprecated；现行门 = DG-1…DG-6）")
        print("=" * 66)
        print("  DG-3 仓内受控内容   %-8s %s" % (
            result["dg3"]["state"], result["dg3"].get("detail")))
        print("  旧扩展名候选       %d 个（只作说明，不参与判决）" %
              result["legacy_extension_candidates"]["count"])
        print("  旧下载数据根       %-8s %s" % (
            result["download_root"]["state"], result["download_root"]["detail"]))
        print("  反向对照           %s %s" % (
            "✅" if result["reverse_control"]["ok"] else "❌",
            result["reverse_control"]["detail"]))
        if result["reds"]:
            print("\n红：")
            for item in result["reds"][:10]:
                print("  - " + str(item))
        if result["untested"]:
            print("\n未测：")
            for item in result["untested"][:10]:
                print("  - " + str(item))
        print("\n结论：%s" % result["verdict"])
    return 1 if result["verdict"] == "fail" else (
        2 if result["verdict"] == "untested" else 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-history", action="store_true",
                    help="测试/诊断用：DG-3 不扫描历史提交")
    args = ap.parse_args()
    return report(evaluate(include_history=not args.no_history), as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
