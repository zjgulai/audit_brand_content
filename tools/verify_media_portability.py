#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_media_portability.py —— 行 118：媒体能力不许用宿主原生

## 行 118 两半，结论不同

| 要求 | 本文件 | 当前读数 |
|---|---|---|
| 静态扫 macOS Vision/Speech 等宿主原生调用 | **M1**（剥注释/docstring 后扫可执行源码） | ❌ **红** |
| Linux 容器内跑真实图片与视频并断言有结果 | — | ❌ **无对象**（无 docker daemon、镜像无引擎、无素材） |

## 为什么 M1 今天是红的（不是误报）

仓内唯一在用的 OCR 就是 macOS Vision：
`base/ocr_vision.m:2` `#import <Vision/Vision.h>`、`:42` `VNRecognizeTextRequest`；
`base/build_ocr.sh:24-26` 用 `-framework Vision -framework AppKit` 编译；
`base/media.py:89/398` 把它当唯一 OCR 入口并写死 extractor 标签。
按行 118 的判据（「不使用宿主原生」），**今天的实现直接违反**。

★ 这不是「新写了一条断言把它弄红」，而是**把本来就存在的事实变成可核对的读数**。

## 已裁定（2026-10-23，见 `PMO/audit/裁定-R118-媒体宿主原生-20261023.md`）

裁定结论三句：

1. **`base/media.py` 及其 OCR 链不在生产路径上** —— 行为级读数：
   生产进件 `SUPPORTED_SOURCE_KINDS = {"free_text", "ad_text"}`，
   `source.kind=image` 被 `SubmissionRejected: unsupported_source_kind` 拒；
   且 `api/` 的 import 闭包（24 个文件）**不含 `base/media.py`**。
2. **所以行 118 的「不用宿主原生」今天是**空真**，不是已满足。**
   「今天不违规」与「今天做到了」是两件事 —— 把前者写成后者，就是
   AGENTS.md §2.4.1 那个形状。
3. **这条红保持红，不许改绿。** 但结论行必须说清**红的是什么**（见下）。

⚠️ **未来条件**：一旦生产真的接上媒体进件（`SUPPORTED_SOURCE_KINDS` 加入
`image`/`video`），今天这条空真**立刻变成真违规**，而**没有任何东西会提醒你**。
→ 打开媒体进件的那张票必须同时处理行 118（已登记为 T-118-follow）。

## 容器那半为什么无对象（五类通道）

1. 直接 import：无。
2. 传递依赖：无。
3. 代码实现：`Dockerfile:36` 是 `python:3.12-slim`，全文 0 处 `apt-get`；没有媒体镜像。
4. 数据：全仓 mp4/mov/webm/wav/mp3 **0 个**；`video_stage()` 自己返回 `cannot_measure`。
5. 运行时：本机 docker daemon 不可达（socket 不在 `/var/run/docker.sock`）。

退出码：0 / 1 / 2（源码读不出）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCAN_DIRS = (ROOT / "base", ROOT / "api")
EXTS = {".py", ".m", ".mm", ".swift", ".sh"}
EXCLUDE = {"__pycache__", ".venv", "node_modules"}
#: 宿主原生媒体能力特征。逐个点名，不做模糊匹配。
NATIVE = (
    "#import <Vision/", "VNRecognizeTextRequest", "VNImageRequestHandler",
    "#import <Speech/", "SFSpeechRecognizer", "SFSpeechAudioBufferRecognitionRequest",
    "#import <AVFoundation/", "AVCaptureSession", "-framework Vision",
    "-framework Speech", "-framework AVFoundation", "Quartz",
)


def strip_comments(src: str) -> str:
    """剥整行注释、三引号块、Objective-C 的 `//` 与 `/* */`。"""
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    src = re.sub(r"/\*(?:.|\n)*?\*/", "", src)
    out = []
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#") or s.startswith("//"):
            continue
        out.append(ln)
    return "\n".join(out)


def collect() -> dict[str, str]:
    out = {}
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.suffix not in EXTS:
                continue
            if any(part in EXCLUDE for part in p.parts):
                continue
            try:
                out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


def scan(sources: dict[str, str]) -> list[str]:
    hits = []
    for rel, src in sources.items():
        for i, line in enumerate(strip_comments(src).splitlines(), 1):
            for tok in NATIVE:
                if tok in line:
                    hits.append(f"{rel}:{i} 命中 {tok!r} —— {line.strip()[:70]}")
    return hits


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        good = {"base/x.py": "# VNRecognizeTextRequest 只在注释里\nimport json\n"}
        bad = {"base/x.m": "#import <Vision/Vision.h>\nVNRecognizeTextRequest *r;\n"}
        cases = [
            ("反向对照：只出现在注释里 → 不许误报", lambda: not scan(good)),
            ("★ 坏样本：可执行代码里出现 Vision → 必须命中", lambda: bool(scan(bad))),
            ("★ 坏样本：build 脚本里 -framework Vision → 必须命中",
             lambda: bool(scan({"base/b.sh": "clang -framework Vision x.m\n"}))),
        ]
        bad_n = 0
        print("=" * 78)
        print("行 118 · 宿主原生媒体调用扫描（离线对照）")
        print("=" * 78)
        for i, (name, fn) in enumerate(cases, 1):
            try:
                ok, err = bool(fn()), ""
            except Exception as e:  # noqa: BLE001
                ok, err = False, f"（{type(e).__name__}: {e}）"
            if not ok:
                bad_n += 1
            print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
        print("-" * 78)
        if bad_n:
            print(f"❌ {len(cases)} 项中 {bad_n} 项失败")
            return 1
        print(f"✅ {len(cases)} 项全过")
        return 0

    sources = collect()
    if not sources:
        print("⚠️ 未测：扫描目录里没有可读源码")
        return 2
    hits = scan(sources)
    print("=" * 78)
    print("行 118 · 媒体能力是否只用容器内跨平台引擎")
    print("=" * 78)
    print(f"  扫描 {len(sources)} 个可执行源码（剥掉整行注释 / docstring / /* */）")
    if hits:
        for h in hits:
            print(f"  ❌ {h}")
        print()
        print(f"❌ 退 1：{len(hits)} 处宿主原生调用。**这是事实读数，不是新引入的问题** ——")
        print("   仓内唯一 OCR 就是 macOS Vision。")
        print()
        print("   ★ 已裁定（2026-10-23）：`base/media.py` 与这条 OCR 链**不在生产路径上**")
        print("     —— 生产进件只接 free_text/ad_text，source.kind=image 直接 422；")
        print("     且 api/ 的 import 闭包（24 个文件）不含 base/media.py。")
        print("     **所以行 118 的「不用宿主原生」今天是空真，不是已满足。**")
        print("     这条红保持红：红的不是「生产违规了」，是「仓里有宿主原生实现，")
        print("     而生产恰好还没接媒体」。**两件事都不许省掉。**")
        print("     ⚠️ 一旦生产接上媒体进件，空真立刻变真违规 —— 那张票必须同时处理行 118（T-118-follow）。")
        print("   ⚠️ 容器那半（Linux 里真跑图片/视频）**无对象**：无 docker daemon、镜像无引擎、素材 0 个。")
        return 1
    print("✅ 退 0：没有宿主原生媒体调用。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
