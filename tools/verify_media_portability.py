#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_media_portability.py —— 行 118：媒体能力不许用宿主原生

## 行 118 两半，结论不同

| 要求 | 本文件 | 当前读数 |
|---|---|---|
| 静态扫 macOS Vision/Speech 等宿主原生调用 | **M1**（剥注释/docstring 后扫可执行源码） | ⚠️ **数到 3 处，但按裁定「空真」** |
| 生产进件是否已打开媒体 | **G1/G2**（行为级读 `SUPPORTED_SOURCE_KINDS`） | ✅ 未打开；一旦打开立刻退 1 |
| Linux 容器内跑真实图片与视频并断言有结果 | — | ❌ **无对象**（无 docker daemon、镜像无引擎、无素材） |

> ★ 2026-10-24 更正：上表第一行原先写「❌ 红」，**那已经过期**。
> `verify_media_portability.py` 现在退 **0**，因为按裁定把「仓里有原生调用」
> 记成了**空真读数**（生产进件未开媒体），并把真正的守卫放在 G2：
> 一旦 `SUPPORTED_SOURCE_KINDS` 出现 image/video 就退 1。
> 实测（`mutprobe`）：把 `image` 加进 `base/submission_service.py` 的那个集合
> → 退 1，红项点名要先改 `base/ocr_vision.m`。
> **文件头写「红」而程序退 0，是同一个量两个口径 —— 已改成两行分开写。**

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


# ── T-118-follow：媒体进件一旦打开，行 118 必须从「空真」翻成「必须真验」──────
#
# ## 这条守卫防的是什么
#
# 2026-10-23 的裁定说：行 118 今天**空真** —— 仓里有 macOS Vision（`base/ocr_vision.m`），
# 但生产进件只接 `free_text` / `ad_text`，`image` 被 422 拒，所以那条链不在生产路径上。
#
# **空真会静默变成真违规。** 谁把 `image` 加进 `SUPPORTED_SOURCE_KINDS`，
# 那一天起「不用宿主原生」就从「无对象」变成「被违反」，
# 而**没有任何东西会告诉他**。本函数就是那个东西。
#
# ## 为什么必须是行为级
#
# 读 `submission_service.SUPPORTED_SOURCE_KINDS` 的**真实值**（import 进来），
# 不是 grep 源码字符串。两者的差别是：源码里写 `{"free_text","ad_text"}` 但运行时被覆盖
# （环境变量、子类、monkeypatch）时，grep 会绿而真实行为已经变了。
# 这正是 §2.4「名字出现过 ≠ 拦得住」。
MEDIA_KINDS = ("image", "video")


def supported_source_kinds():
    """读生产进件的真实支持集。读不出返回 None（调用方落未测）。"""
    try:
        from base import submission_service as S
        return frozenset(S.SUPPORTED_SOURCE_KINDS)
    except Exception:  # noqa: BLE001
        return None


def check_media_gate(kinds, native_hits):
    """判据：媒体进件是否已打开，以及行 118 该处于哪种状态。

    返回 (problems, state, detail)：
      · `state == "vacuous_true"`：媒体未开 + 有宿主原生实现 → **空真，允许**
      · `state == "must_fix"`     ：媒体已开 + 有宿主原生实现 → **真违规，红**
      · `state == "clean"`        ：媒体已开或未开，但没有宿主原生实现 → 绿

    ★ 反向对照成对：`kinds={"free_text","ad_text"}` 必须走 vacuous_true（绿），
      `kinds` 含 image 必须走 must_fix（红）。**只测一边，另一边就恒真。**
    """
    problems = []
    kinds = frozenset(kinds or ())
    opened = sorted(k for k in MEDIA_KINDS if k in kinds)

    if native_hits:
        if opened:
            problems.append(
                "媒体进件已打开（SUPPORTED_SOURCE_KINDS 含 %r），但仓内仍有 %d 处宿主原生"
                "媒体调用 —— 行 118 从「空真」变成了**真违规**。"
                "最先要改的是 `base/ocr_vision.m`（macOS Vision → 容器内跨平台引擎，"
                "见行 118 与 TS-16）。**打开媒体进件的那张票必须同时处理行 118（T-118-follow）。**"
                % (opened, len(native_hits)))
            state = "must_fix"
        else:
            state = "vacuous_true"
            detail = ("媒体未开（%r），宿主原生实现有 %d 处 —— 空真，允许"
                      % (sorted(kinds), len(native_hits)))
            return problems, state, detail
    else:
        state = "clean"
        return problems, state, "没有宿主原生媒体调用（%s）" % (
            "媒体已开" if opened else "媒体未开")

    return problems, state, "媒体已开 %r，宿主原生 %d 处" % (opened, len(native_hits))


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        good = {"base/x.py": "# VNRecognizeTextRequest 只在注释里\nimport json\n"}
        bad = {"base/x.m": "#import <Vision/Vision.h>\nVNRecognizeTextRequest *r;\n"}
        fake_hits = ["base/ocr_vision.m:2 命中 '#import <Vision/'"]
        cases = [
            ("反向对照：只出现在注释里 → 不许误报", lambda: not scan(good)),
            ("★ 坏样本：可执行代码里出现 Vision → 必须命中", lambda: bool(scan(bad))),
            ("★ 坏样本：build 脚本里 -framework Vision → 必须命中",
             lambda: bool(scan({"base/b.sh": "clang -framework Vision x.m\n"}))),

            # ── T-118-follow 守卫：成对，缺一边另一边就恒真 ──────────────
            ("★ G1 媒体未开 + 有宿主原生 → 空真，必须**绿**（当前真实状态）",
             lambda: not check_media_gate({"free_text", "ad_text"}, fake_hits)[0]),
            ("★★ G1 注入 image + 有宿主原生 → 必须**红**（空真翻成真违规）",
             lambda: bool(check_media_gate({"free_text", "ad_text", "image"}, fake_hits)[0])),
            ("★ G1 注入 video → 必须**红**",
             lambda: bool(check_media_gate({"free_text", "ad_text", "video"}, fake_hits)[0])),
            # 反向的另一侧：媒体开了但**没有**宿主原生 → 必须绿
            # （否则「媒体一开就红」会变成恒红，与恒绿一样骗人）
            ("★ G1 媒体已开但无宿主原生 → 必须**绿**（避免恒红）",
             lambda: not check_media_gate({"free_text", "image"}, [])[0]),
            ("G1 状态标注：空真 ≠ 已满足",
             lambda: check_media_gate({"free_text"}, fake_hits)[1] == "vacuous_true"),
            ("G1 状态标注：媒体开 + 宿主原生 → must_fix",
             lambda: check_media_gate({"image"}, fake_hits)[1] == "must_fix"),
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

    kinds = supported_source_kinds()
    print("=" * 78)
    print("行 118 · 媒体能力是否只用容器内跨平台引擎")
    print("=" * 78)
    print(f"  扫描 {len(sources)} 个可执行源码（剥掉整行注释 / docstring / /* */）")
    if kinds is None:
        print("  ⚠️ G0 未测：读不出 `SUPPORTED_SOURCE_KINDS` —— 无法判断媒体进件是否已开")
        print("     （**未测不是通过**：空真与真违规的界线正取决于这个值）")
        return 2
    print(f"  G0 生产进件真实支持集：{sorted(kinds)}（行为级 import，不是 grep 源码）")

    problems, state, detail = check_media_gate(kinds, hits)

    if state == "must_fix":
        for h in hits:
            print(f"  ❌ {h}")
        print()
        for p in problems:
            print(f"  ❌ G1 {p}")
        print()
        print("   ⚠️ 容器那半（Linux 里真跑图片/视频）**无对象**：无 docker daemon、镜像无引擎、素材 0 个。")
        print("   ★ 这条判据今天靠**手动跑**（不在 CI、不在验收执行器的任何映射行里）。")
        return 1

    if state == "clean":
        print(f"  ✅ G1 {detail}")
        return 0

    # vacuous_true：媒体未开 + 有宿主原生实现 —— 空真，允许，但必须**显式记录**
    print(f"  ✅ G1 空真状态被明确记录：{detail}")
    print()
    print(f"   ⚠️ 仓里有 {len(hits)} 处宿主原生媒体调用（`base/ocr_vision.m` 的 macOS Vision）——")
    print("      **这是事实读数，不是新引入的问题**，且今天**不构成违规**：")
    print("      生产进件只接 free_text/ad_text，source.kind=image 直接 422；")
    print("      且 api/ 的 import 闭包（24 个文件）不含 base/media.py。")
    print("   ★ 但「今天不违规」≠「今天做到了」。行 118 今天是**空真**。")
    print()
    print("   🔒 G2 守卫：一旦 `SUPPORTED_SOURCE_KINDS` 出现 image/video，本行立刻退 1，")
    print("      并指出最先要改的是 `base/ocr_vision.m`（macOS Vision → 容器内跨平台引擎）。")
    print("      打开媒体进件的那张票**必须同时处理行 118**（T-118-follow）。")
    print()
    print("   ★ 触发途径：本判据今天**只能手动跑**（不在 CI —— `.github/` 未跟踪且卡在权限闸门；")
    print("     也不在 verifier_map 的任何映射行里）。**如实写明，不假装有触发点。**")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
