#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_video_ingest.py — T-435：视频抽帧（balanced）+ 音画对齐前提

## 这一票为什么能在**没有视频素材、没有 ffmpeg** 的机器上交判据

抽帧的业务判据 —— 去重是否有效、上限是否生效、时间戳是否单调、同输入是否
同输出、V1 五项表态对不对 —— **与 ffmpeg 无关**。它们可以在合成帧上真验。

所以本验收器分两层，**两层都要自证，缺一层就是「逻辑对但跑不起来」或反之**：

  · **E 层（engine）**：用合成帧序列真跑 `dedupe_frames` / `plan_times` /
    `video_covers` / `av_alignment_ready`。不需要 ffmpeg。
  · **X 层（execution）**：ffmpeg/ffprobe 在不在。**不在就落未测，退 2** ——
    「工具缺失」与「抽帧逻辑正确」是两件事，不许用一个绿的退出码盖住另一件。

## 断言分组

  E1  去重有效：静止片段去重后显著少于去重前（给具体阈值）
  E2  去重不误伤：明显不同的帧必须留下
  E3  渐变不塌成 1 帧（与「上一枚保留的帧」比，不是与前一帧比）
  E4  `dedup=False` 时不去重（反向对照：证明 E1 不是因为帧本来就少）
  E5  上限：`max_frames` 是**硬上限**，抽帧前就截断
  E6  均匀兜底：时刻在 (0, duration) 内、单调、不取两端
  E7  静止画面回落 uniform（切变点不够就换路）
  E8  V1 五项：无音轨必须 not_applicable；0 帧不许说已评；
      **完整画面语义永远不许是「已评」**
  E9  音画对齐前提：只有 video → 拒，且点名缺 audio
  E10 常量恒等：V1_KEYS 与 report_render.mjs 的 V1_KEYS 同名同序；
      V1_VALUES 与 V1_KEYS_OUTSIDE 的允许断言一致
  X1  ffprobe 读事实（工具缺失 → 未测）
  X2  抽帧真跑 + 帧清单指纹可复现（同输入同输出）
  X3  无音轨视频的 V1 音轨 = not_applicable（真文件，不是合成）

退出码：0 全过 / 1 有红 / 2 未测（工具缺失或导入失败）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: " + name + ((" " + detail) if detail else ""))


try:
    from base import media_ingest as MI
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base/media_ingest.py: %s" % exc)
    sys.exit(2)


# ── 合成帧 ────────────────────────────────────────────────────────────

def _thumb(color: int, size: int = 16) -> bytes:
    """纯色缩略图（RGB 三通道同值）。"""
    return bytes([color]) * (size * size * 3)


def _frame(ts: float, color: int, size: int = 16) -> MI.Frame:
    data = b"frame-%d-%f" % (color, ts)
    return MI.Frame(ts=ts, width=512, height=0,
                    sha256=hashlib.sha256(data).hexdigest(),
                    source_uri="inline:synthetic", data=data,
                    thumb=_thumb(color, size))


# ── E1–E4：去重 ──────────────────────────────────────────────────────

def check_dedupe():
    # 静止片段：10 帧同色
    still = [_frame(i * 0.5, 100) for i in range(10)]
    kept, dropped = MI.dedupe_frames(still, threshold=8.0)
    report(len(kept) == 1,
           "E1 ★ 静止片段 10 帧 → 去重后 1 帧（判据 2：去重有效）",
           "kept=%d dropped=%d" % (len(kept), len(dropped)))
    report(len(dropped) == 9, "E1b 丢掉 9 帧（不是靠少抽达到的）",
           "dropped=%d" % len(dropped))

    # 明显不同：3 帧三色
    variety = [_frame(0.0, 10), _frame(1.0, 120), _frame(2.0, 240)]
    kept2, dropped2 = MI.dedupe_frames(variety, threshold=8.0)
    report(len(kept2) == 3,
           "E2 ★★ 三帧三色 → 全部保留（去重不误伤）",
           "kept=%d" % len(kept2))
    report(dropped2 == [], "E2b 没有误丢", repr(dropped2))

    # 微量差异（压缩伪影量级）：应该合并
    subtle = [_frame(0.0, 100), _frame(0.5, 103), _frame(1.0, 101)]
    kept3, _ = MI.dedupe_frames(subtle, threshold=8.0)
    report(len(kept3) == 1,
           "E3a 差 1–3 个色阶（伪影量级）→ 合并", "kept=%d" % len(kept3))

    # ★ 渐变：每一帧只比前一帧差一点点（4 个色阶 < 阈值 8），累计起来必须留下多帧。
    #
    #   第一版用的是 12 色阶/帧 —— 那**大于**阈值 8，于是「与前一帧比」也会
    #   留下每一帧，E3b 与 E3c 就分不出两种比法的差别。真变异实测过：
    #   把 dedupe 改成与前一帧比，E3b/E3c 仍然全绿。
    #   要区分两者，步长必须**小于**阈值：单步看不出，累计才看得出。
    gradient = [_frame(i * 0.5, min(255, 20 + i * 4)) for i in range(11)]
    kept4, _ = MI.dedupe_frames(gradient, threshold=8.0)
    report(2 <= len(kept4) < len(gradient),
           "E3b ★★ 细渐变 11 帧（每步差 4 < 阈值 8）→ 留下部分而非全部，"
           "也不塌成 1 帧（与保留帧比，不塌成 1 帧）",
           "kept=%d" % len(kept4))

    # 反向对照：与「前一帧」比时，单步 4 < 8 会被判成同帧 → 塌成 1 帧。
    # 这一条证明 E3b 的区间不是恒真：另一种比法落在区间之外。
    def _adjacent_only(frames, threshold):
        kept = []
        for index, frame in enumerate(frames):
            if not kept:
                kept.append(frame)
                continue
            if MI.mean_channel_diff(frames[index - 1].thumb, frame.thumb) >= threshold:
                kept.append(frame)
        return kept
    adjacent_kept = _adjacent_only(gradient, 8.0)
    report(len(adjacent_kept) == 1,
           "E3c ★★ 反证：与前一帧比 → 塌成 1 帧（落在 E3b 的区间之外，"
           "所以 E3b 不是恒真）",
           "adjacent=%d" % len(adjacent_kept))

    # 尺寸不同的缩略图 → 大差异 → 保留
    odd = [_frame(0.0, 100), MI.Frame(ts=1.0, width=512, height=0,
                                      sha256="x", source_uri="u",
                                      data=b"d", thumb=b"")]
    kept5, _ = MI.dedupe_frames(odd, threshold=8.0)
    report(len(kept5) == 2,
           "E3d 空缩略图 → 判为大差异并保留（宁可多留，不误合）",
           "kept=%d" % len(kept5))


# ── E5–E7：上限与抽帧策略 ────────────────────────────────────────────

def check_budget():
    # 上限：max_frames=3，切变点 10 个 → 只取 3 个
    budget = MI.FrameBudget(max_frames=3, min_scene_cuts=2)

    def fake_runner(args):
        # 伪 ffmpeg：为 showinfo 输出 10 个 pts_time
        if any("showinfo" in str(a) for a in args):
            lines = "\n".join(
                "[Parsed_showinfo_2 @ 0x1] n:%d pts:%d pts_time:%.3f" % (i, i, i * 1.0)
                for i in range(10))
            return 0, b"", lines
        if any("ffprobe" in str(a) for a in args):
            payload = {"format": {"duration": "10.0"},
                       "streams": [{"codec_type": "video", "width": 640,
                                    "height": 480, "avg_frame_rate": "30/1"}]}
            return 0, json.dumps(payload).encode(), ""
        return 0, b"", ""

    frames = MI.extract_frames("fake.mp4", budget=budget, runner=fake_runner)
    # 抽帧本身需要真 ffmpeg（image2pipe），这里只验「计划阶段就截断」
    cuts = MI.scene_cut_times("fake.mp4", budget=budget, runner=fake_runner)
    planned, strategy = MI.plan_times("fake.mp4", 10.0, budget=budget,
                                       runner=fake_runner)
    report(len(planned) <= budget.max_frames,
           "E5 ★★ max_frames 是硬上限（计划阶段就截断，不先抽再丢）",
           "planned=%d max=%d" % (len(planned), budget.max_frames))
    report(strategy == "scene", "E5b 切变点够多 → 走 scene", strategy)
    report(len(cuts) == 10, "E5c 切变时刻解析正确（10 个）", str(len(cuts)))
    report(cuts == sorted(cuts) and len(set(cuts)) == len(cuts),
           "E5d 切变时刻单调且去重", repr(cuts[:4]))

    # 均匀兜底
    u = MI.uniform_times(30.0, 5)
    report(len(u) == 5 and all(0 < t < 30.0 for t in u),
           "E6 ★ 均匀兜底：时刻都在 (0, duration) 内（不取两端黑场）", repr(u))
    report(u == sorted(u), "E6b 单调递增", repr(u))
    report(MI.uniform_times(0, 5) == [] and MI.uniform_times(30, 0) == [],
           "E6c 边界：duration=0 或 count=0 → 空列表（不抛）")

    # 几乎静止 → uniform
    def still_runner(args):
        if any("showinfo" in str(a) for a in args):
            # 只有 1 个切变点 < min_scene_cuts
            return 0, b"", "[Parsed_showinfo] n:0 pts_time:1.000"
        return 0, b"", ""

    _, strategy2 = MI.plan_times("still.mp4", 30.0, runner=still_runner)
    report(strategy2 == "uniform",
           "E7 ★★ 切变点不足（1 < min_scene_cuts=3）→ 回落 uniform",
           strategy2)

    # 反向对照：切变点够时必须走 scene，不许一律 uniform
    def busy_runner(args):
        if any("showinfo" in str(a) for a in args):
            return 0, b"", "\n".join(
                "pts_time:%.3f" % (i * 0.7) for i in range(6))
        return 0, b"", ""

    _, strategy3 = MI.plan_times("busy.mp4", 30.0, runner=busy_runner)
    report(strategy3 == "scene",
           "E7b 反证：切变点 6 个 → 必须走 scene（不是恒 uniform）", strategy3)


# ── E8–E9：V1 五项与音画对齐前提 ─────────────────────────────────────

def check_covers():
    no_audio = MI.video_covers(has_audio=False, frames_kept=0)
    report(no_audio["音轨"] == "no",
           "E8-1 ★★ 无音轨 → 音轨=no（Playbook V1 原文就是「音轨 ⛔」）",
           repr(no_audio["音轨"]))
    report("没有音轨" in MI.audio_note(False),
           "E8-1b ★ 无音轨时 audio_note 说清「不是没审，是没有这项内容」",
           MI.audio_note(False)[:40])
    report(no_audio["关键帧"] == "no",
           "E8-2 ★ 0 帧 → 关键帧=no（0 帧不是「审完了 0 个问题」）",
           repr(no_audio["关键帧"]))

    with_audio_no_asr = MI.video_covers(has_audio=True, frames_kept=10)
    report(with_audio_no_asr["音轨"] == "no",
           "E8-3 ★★ 有音轨但没做 ASR → 音轨=no（有音轨不等于听过）",
           repr(with_audio_no_asr["音轨"]))
    report("未做 ASR" in MI.audio_note(True),
           "E8-3b ★ 有音轨但没转写时，note 与「本来没有音轨」长得不一样 "
           "（V1 取值同档，靠这行字分开）", MI.audio_note(True)[:40])
    report(with_audio_no_asr["字幕"] == "no",
           "E8-4 没做 ASR → 字幕=no", repr(with_audio_no_asr["字幕"]))

    full = MI.video_covers(has_audio=True, frames_kept=100,
                           transcript=True, ocr_on_frames=True,
                           scene_semantics=True)
    report(full["完整画面语义"] == "partial",
           "E8-5 ★★★ 完整画面语义**永远**不是 yes（100 帧也不是整段理解）",
           repr(full["完整画面语义"]))
    report(full["音轨"] == "partial",
           "E8-6 有音轨 + 有转写 → 音轨=partial", repr(full["音轨"]))
    report(set(full) == set(MI.V1_KEYS),
           "E8-7 五项齐全，键集与 V1_KEYS 恒等",
           repr(sorted(set(full) ^ set(MI.V1_KEYS))))
    report(all(v in MI.V1_VALUES for v in full.values()),
           "E8-8 取值都在允许域 %r 内" % (MI.V1_VALUES,),
           repr(sorted(set(full.values()))))
    # ★ 无条件那条：任何组合下「完整画面语义」都不许是 yes
    bad = []
    for has_audio in (True, False):
        for frames in (0, 10, 40, 100, 500):
            for sem in (True, False):
                c = MI.video_covers(has_audio=has_audio, frames_kept=frames,
                                    transcript=True, ocr_on_frames=True,
                                    scene_semantics=sem)
                if c["完整画面语义"] == "yes":
                    bad.append((has_audio, frames, sem))
    report(bad == [],
           "E8-9 ★★★ 穷举 20 种组合，「完整画面语义」无一为 yes", repr(bad))
    # ★ 展示层映射不许反过来影响判定：三个符号各对一个取值，且值域恒等
    report(set(MI.V1_LABELS) == set(MI.V1_VALUES),
           "E8-10 展示层符号与取值域一一对应（只做渲染，不参与判定）",
           repr(MI.V1_LABELS))

    # ★ E8-11：`has_audio` 不许偷偷抬升音轨的覆盖声明。
    #   一个「有音轨」的视频，若因为「它有声」就被标成 partial，
    #   等于用「有这个介质」冒充「看过这个介质」。
    lifted = []
    for transcript in (False, True):
        a = MI.video_covers(has_audio=True, frames_kept=30, transcript=transcript)
        b = MI.video_covers(has_audio=False, frames_kept=30, transcript=transcript)
        if a["音轨"] != b["音轨"]:
            lifted.append((transcript, a["音轨"], b["音轨"]))
    report(lifted == [],
           "E8-11 ★★ has_audio 不许影响覆盖声明（有音轨 ≠ 听过）", repr(lifted))
    # 反向对照：它**必须**影响说明文字，否则那行 note 就是恒真的摆设
    report(MI.audio_note(True) != MI.audio_note(False),
           "E8-12 ★ 反向对照：has_audio 必须影响 audio_note（两种成因要分得开）")
    report(MI.audio_note(True, transcript=True) != MI.audio_note(True),
           "E8-13 has_audio + transcript 的说明也与「没转写」不同")

    ok, why = MI.av_alignment_ready({"video": "x"})
    report(not ok and "audio" in why,
           "E9-1 ★★ 只有 video → 拒，且点名缺 audio", why)
    ok2, _ = MI.av_alignment_ready({"video": "x", "audio": "y"})
    report(ok2, "E9-2 两样都有 → 放行（不是恒拒）")
    ok3, why3 = MI.av_alignment_ready({})
    report(not ok3 and "video" in why3 and "audio" in why3,
           "E9-3 都没有 → 两样都点名", why3)


# ── E10：两张表恒等 ──────────────────────────────────────────────────

def check_contract_alignment():
    """Python 的 V1_KEYS 与 report_render.mjs 的 V1_KEYS 必须同名同序。

    ★ 两处各写一份是刻意（渲染器不 import Python、本层不 import Node），
      所以要有一条断言守着它们不许漂移。名字漂了会让报告里出现
      「视频已审」却查不到对应的 covers 键 —— 而那是被 `assertVideoClaim` 拦的形状。
    """
    mjs = (ROOT / "tools" / "audit" / "report_render.mjs").read_text(encoding="utf-8")
    match = re.search(r'V1_KEYS\s*=\s*\[([^\]]+)\]', mjs)
    if not match:
        report(False, "E10-1 在 report_render.mjs 里找不到 V1_KEYS 定义")
        return
    names = tuple(re.findall(r'"([^"]+)"', match.group(1)))
    report(names == tuple(MI.V1_KEYS),
           "E10-1 ★★ V1 五项与 report_render.mjs 同名同序",
           "mjs=%r py=%r" % (names, tuple(MI.V1_KEYS)))

    verify_mjs = (ROOT / "tools" / "verify_report_render.mjs").read_text(encoding="utf-8")
    # ★ 取值域在 `V1_ENUM`（`V1_KEYS_OUTSIDE` 只是消费它）。
    #   第一版把正则指向 `V1_KEYS_OUTSIDE` 的**函数体**去找字符串，
    #   而它引的是 `V1_ENUM` —— 于是抓到空集合，判据恒红。
    #   判据要读**定义**，不要读消费点。
    ematch = re.search(r'V1_ENUM\s*=\s*\[([^\]]+)\]', verify_mjs)
    if not ematch:
        report(False, "E10-2 在 verify_report_render.mjs 里找不到 V1_ENUM 定义")
        return
    enum = tuple(re.findall(r'"([^"]+)"', ematch.group(1)))
    report(enum == tuple(MI.V1_VALUES),
           "E10-2 ★★ 取值域与 verify_report_render.mjs 的 V1_ENUM 恒等",
           "mjs=%r py=%r" % (enum, tuple(MI.V1_VALUES)))
    # ★ 反向对照：消费点确实在用这份定义（否则上面那条只是「两个常量相等」）
    report("V1_ENUM.includes" in verify_mjs,
           "E10-3 消费点 V1_KEYS_OUTSIDE 真的在用 V1_ENUM（判据不是空转）")


# ── X 层：执行 ────────────────────────────────────────────────────────

def check_execution():
    avail = MI.tools_available()
    missing = [n for n, ok in avail.items() if not ok]
    if missing:
        untested("X0 ffmpeg/ffprobe 缺失（%s）—— 抽帧执行与真文件读数全部未测"
                 % ", ".join(missing))
        return
    videos, from_repo = _x_layer_videos()
    if not videos:
        untested("X0 盘上 0 个视频文件 —— 真跑无对象（判据 1/3/4 需要真素材）")
        return
    video = videos[0]
    probe = MI.probe_video(video)
    report(probe.ok and probe.duration_s > 0,
           "X1 ffprobe 读到时长与流信息", json.dumps(probe.to_dict())[:160])
    first = MI.extract_frames(video)
    second = MI.extract_frames(video)
    report(first.get("ok") and second.get("ok"),
           "X2 抽帧跑通（两次都 ok）")
    report(first.get("kept_count", 0) <= MI.BALANCED.max_frames,
           "X2b 帧数 ≤ 上限 100", str(first.get("kept_count")))
    report(first.get("manifest_sha256") == second.get("manifest_sha256"),
           "X2c ★★ 同输入同输出（帧清单指纹相等，判据 1）",
           "%s vs %s" % (first.get("manifest_sha256", "")[:12],
                         second.get("manifest_sha256", "")[:12]))
    report(all(isinstance(f.get("ts"), (int, float)) for f in first.get("frames") or []),
           "X2d 每帧都有时间戳")
    cover = MI.video_covers(has_audio=probe.has_audio,
                            frames_kept=first.get("kept_count", 0))
    # ★ 2026-10-27 补：这条原先就是 `音轨 == no`（Playbook V1 承诺音轨 ⛔）。
    #   接进真实素材后它红了，我第一反应是「断言写死了素材没音轨」，
    #   于是改成「有音轨→未覆盖」—— **改错了方向**：
    #   `base/media_ingest.video_covers` 的注释与 E8-11 都明写
    #   `has_audio` **刻意不影响**覆盖声明（有音轨 ≠ 听过）。
    #   真素材带音轨恰恰是这个设计要的情形，不是它的反例。
    report(cover["音轨"] == "no",
           "X3 ★ 音轨一律 no，与 has_audio 无关（判据 4：有音轨也≠听过）",
           "has_audio=%s → %r" % (probe.has_audio, cover["音轨"]))
    # 而这批素材**真有音轨**，于是「音轨=no」的两种成因在这里第一次同时存在：
    # 必须靠 `audio_note()` 说清是「本来没有」还是「有但没听」。
    # 这一条今天才有真对象验（此前 X 层一直是未测）。
    note = MI.audio_note(probe.has_audio)
    report(("没有音轨" in note) != probe.has_audio,
           "X3b ★ 音轨=no 的成因由 audio_note 说清（有音轨↔说没音轨 必须互斥）",
           "has_audio=%s note=%r" % (probe.has_audio, note))


def _x_layer_videos():
    """X 层要验的真视频从哪来。返回 (文件清单, 是否来自仓内)。

    ★ 两个来源，**仓内的优先但仓内不许有**：
      * 仓内 `research/landing/_evidence` —— 历史上落地页抓取留下的；
        但它**不许**再新增视频（仓是公开的，AGENTS.md §2.6）。
      * 仓外 `AUDIT_MEDIA_SAMPLE_ROOTS`（逗号分隔，默认 `~/audit-data/media-samples`）
        —— 与 `REVIEW_MEDIA_ROOTS` 同一个思路：**读进来的素材根**，
        允许在仓外任意可读位置。素材由 `tools/media_samples_fetch.py` 取、
        在该文件与 `tools/download_callers.json` 里登记（DG-1/DG-2）。

    ★ 为什么不让 X 层「没素材就跳过」：那样这一层永远是未测，
      而 `verify_video_ingest` 的说明里写着它验的是「判据 1/3/4」。
      拿真文件跑一次，才算验过。
    """
    suffixes = (".mp4", ".mov", ".webm", ".m4v")
    inner = sorted(p for p in (ROOT / "research" / "landing" / "_evidence").rglob("*")
                   if p.suffix.lower() in suffixes)
    if inner:
        return inner, True
    raw = os.environ.get("AUDIT_MEDIA_SAMPLE_ROOTS") or "~/audit-data/media-samples"
    outer = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        base = Path(piece).expanduser()
        if not base.is_dir():
            continue
        outer.extend(sorted(p for p in base.rglob("*")
                            if p.suffix.lower() in suffixes))
    return outer, False


def check_tool_degradation():
    """P3：工具缺失时的降级路径必须是「未测」，不是空读数、不是静默绿。

    ★ 这一组能在**没有 ffmpeg 的机器上**验：它喂的是打桩 runner，
      验的是「外部命令失败时这一层怎么落」，不是「ffmpeg 装没装」。
      两件事分开，所以本条今天能真跑（而 X 层不能）。

    ★ 需要一个**真实存在的假文件**：`probe_video` 先判 `is_file()`，
      喂不存在的路径会在到达 runner 之前就返回 `file_not_found` ——
      那样测的是「文件不存在」而不是「工具失败」，判据会红得毫无意义。
      （第一版就是这么写的，四条全红。）
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "fake.mp4"
        fake.write_bytes(b"not a real video")
        _degradation_cases(fake)


def _degradation_cases(fake):
    def missing_runner(args):
        return 127, b"", "command_not_found"

    probe = MI.probe_video(fake, runner=missing_runner)
    report(probe.ok is False and probe.reason.startswith("ffprobe_failed"),
           "D1 ★★ ffprobe 缺失/失败 → ok=False 且 reason 点名（不是静默 0 时长）",
           repr(probe.reason))
    report(probe.duration_s == 0.0 and probe.width == 0,
           "D1b 失败时不编造时长/尺寸（都是 0，且 ok=False 说明它们无意义）")

    out = MI.extract_frames(fake, runner=missing_runner)
    report(out["ok"] is False,
           "D2 ★★ 抽帧失败 → ok=False（不是空清单冒充成功）", repr(out["ok"]))
    report(out["frames"] == [] and out["kept_count"] == 0,
           "D2b 失败时帧清单为空且计数为 0")
    report(out["reason"] != "",
           "D2c ★ 失败必须带 reason（空 reason 等于没说）", repr(out["reason"]))

    # ★ 反向对照：不是视频流 → 也必须是 ok=False，且 reason 说得清
    def audio_only_runner(args):
        payload = {"format": {"duration": "10.0"},
                   "streams": [{"codec_type": "audio"}]}
        return 0, json.dumps(payload).encode(), ""

    probe2 = MI.probe_video(fake, runner=audio_only_runner)
    report(probe2.ok is False and probe2.reason == "no_video_stream",
           "D3 ★★ 没有视频流 → no_video_stream（不是「零帧的合法视频」）",
           repr(probe2.reason))
    report(probe2.has_audio is True,
           "D3b 但 has_audio 如实为 True（识别出它是音频）")

    # ★ 反向对照：工具在的情况下不许误判成失败
    def good_runner(args):
        if any("ffprobe" in str(a) for a in args):
            payload = {"format": {"duration": "5.0"},
                       "streams": [{"codec_type": "video", "width": 640,
                                    "height": 480, "avg_frame_rate": "30/1"},
                                   {"codec_type": "audio"}]}
            return 0, json.dumps(payload).encode(), ""
        return 0, b"", ""

    probe3 = MI.probe_video(fake, runner=good_runner)
    report(probe3.ok and probe3.duration_s == 5.0 and probe3.has_audio,
           "D4 ★ 反证：正常的 ffprobe 输出必须 ok（否则 D1/D2 恒红）",
           repr(probe3.to_dict()))


def main():
    print("=" * 78)
    print("T-435 · 视频抽帧（balanced）+ 音画对齐前提")
    print("=" * 78)
    print("  E 层：抽帧业务判据（合成帧，不需要 ffmpeg）")
    check_dedupe()
    check_budget()
    check_covers()
    check_contract_alignment()
    print("  D 层：工具缺失时的降级（打桩 runner，今天就能跑）")
    check_tool_degradation()
    print("  X 层：执行（真 ffmpeg/真文件）")
    check_execution()
    print("-" * 78)
    if FAILED:
        print("❌ %d passed, %d failed, %d untested" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 项过 · %d 项未测 —— **未测不是通过**"
              "（E 层判据已真验；X 层缺工具或素材）" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
