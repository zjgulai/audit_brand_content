#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️ **已被 `tools/verify_download_governance.py` 取代（2026-10-17）。不要再跑这个。**

**它为什么被取代**：第一版 DL-3 是**假绿**，同行审查指出 7 个绕过点 ——
登记表只有字符串数组、反向对照恒真、只扫 `research/feishu`、
靠源码含 `tempfile` 判定落盘（写个注释就满足）、只扫 `tools/*.py` 漏掉 `.mjs`、
把 58 个自有素材一刀切判红、以及 `AGENTS.md` 里写错的「.gitignore + verify_depad 两道」。

**留档的理由**：它记录了一版「看起来对、跑起来绿、其实拦不住」的检查器长什么样。
**要看现行实现**：`tools/verify_download_governance.py`（DG-1…DG-6，三条行为级反向对照）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 媒体与文档二进制。**逐个点名，不用通配** ——
# 通配会误伤（比如 .bin 在本仓是填充态残渣，不是媒体）。
MEDIA_EXTS = {
    # 图片
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic",
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv",
    # 音频
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    # 办公文档
    ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".pdf",
    # 压缩
    ".zip", ".rar", ".7z", ".tar", ".gz",
}

# 允许的例外：**必须在下面逐条写明理由**。
# 一个空的例外表比一个宽松的黑名单好 —— 空表意味着「现在一个都没有」。
ALLOWED_TRACKED = {
    # 例：("docs/logo.png", "品牌 logo，公开素材，2026-10-17 确认"),
}

DOWNLOAD_ROOT_ENV = "AUDIT_MEDIA_ROOT"


def git_tracked_files(root: Path) -> list[str] | None:
    """git ls-files —— 读不到时返回 None（未测），不是空数组。"""
    try:
        r = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(root), capture_output=True, check=False, timeout=120,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def scan_tracked_binaries(root: Path, tracked: list[str]) -> list[str]:
    hits = []
    for rel in tracked:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in MEDIA_EXTS:
            continue
        if (rel, "") in {(a, "") for a, _ in ALLOWED_TRACKED}:
            continue
        hits.append(rel)
    return hits


def check_download_root(root: Path) -> tuple[str, str]:
    """DL-3b：下载数据根必须在仓外且 0700。没配置 -> 未测。"""
    val = os.environ.get(DOWNLOAD_ROOT_ENV, "").strip()
    if not val:
        return "untested", f"未配置 {DOWNLOAD_ROOT_ENV} —— 未测，不是通过"
    p = Path(val).expanduser().resolve()
    try:
        p.relative_to(root.resolve())
        return "fail", f"{p} 在仓库内 —— 下载物会进版本库"
    except ValueError:
        pass  # 不在仓内，好
    if not p.exists():
        return "untested", f"{p} 不存在 —— 未测"
    mode = p.stat().st_mode & 0o777
    if mode != 0o700:
        return "fail", f"{p} 权限是 {oct(mode)}，应为 0o700"
    return "pass", f"{p} 在仓外，权限 0700"


def reverse_control() -> tuple[bool, str]:
    """DL-3c：喂一个已知二进制，检测器必须红。"""
    fake = ["totally/a/real/photo.png", "another/report.pdf", "x/video.mp4"]
    hits = scan_tracked_binaries(ROOT, fake)
    ok = len(hits) == len(fake)
    return ok, f"喂 {len(fake)} 个已知二进制，检出 {len(hits)} 个"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tracked = git_tracked_files(ROOT)
    if tracked is None:
        print("✗ git ls-files 跑不了 —— 未测，不是通过", file=sys.stderr)
        return 2

    hits = scan_tracked_binaries(ROOT, tracked)
    root_state, root_msg = check_download_root(ROOT)
    rc_ok, rc_msg = reverse_control()

    if args.json:
        import json
        print(json.dumps({
            "tracked_files": len(tracked),
            "binaries_in_repo": hits,
            "download_root": {"state": root_state, "detail": root_msg},
            "reverse_control": {"ok": rc_ok, "detail": rc_msg},
        }, ensure_ascii=False, indent=1))
    else:
        print("=" * 62)
        print("DL-3 · 下载物不许进公开仓")
        print("=" * 62)
        print(f"  已跟踪文件            {len(tracked):>5} 个")
        print(f"  DL-3a 仓内二进制        {len(hits):>5} 个")
        if hits:
            for h in hits[:15]:
                print(f"      - {h}")
        print(f"  DL-3b 下载数据根      {root_state}")
        print(f"      {root_msg}")
        print(f"  DL-3c 反向对照        {'✅' if rc_ok else '❌'} {rc_msg}")

    failed = bool(hits) or root_state == "fail" or not rc_ok
    untested = root_state == "untested"

    if failed:
        print("\n✗ DL-3 失败")
        return 1
    if untested:
        print(f"\n⚠ DL-3 部分未测（设 {DOWNLOAD_ROOT_ENV} 后可测全）—— 未测不是通过")
        return 2
    print("\n✅ DL-3 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
