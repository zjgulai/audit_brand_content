#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""media_ingest.py — T-435：视频进件（ffprobe 读数 + balanced 抽帧 + 音画对齐前提）

## 这一层只做三件事

1. **读事实**：时长 / 分辨率 / 帧率 / **有没有音轨**（ffprobe）。
2. **抽帧**：`balanced` —— 场景切变优先，几乎静止时回落均匀采样；
   16×16 RGB 缩略图去重；上限 100；每帧带**源相对**时间戳与 sha256。
3. **说清覆盖边界**：V1 五项（字幕/内嵌文字/关键帧/音轨/完整画面语义）逐项表态，
   没有音轨时必须写 `not_applicable`，**不许**写「已评」。

## 为什么把 ffmpeg 做成可注入的 runner

两个理由，都是实测过的形状：

* **本机没有 ffmpeg**（2026-10-26 实测 `which ffmpeg` 为空）。如果把调用写死在
  函数体里，「抽帧逻辑对不对」这件事就永远只能等装了 ffmpeg 才能验 —— 而
  抽帧的业务判据（去重是否有效、上限是否生效、时间戳是否单调、同输入是否同输出）
  **与 ffmpeg 无关**。它们可以在合成帧上验。
* 反过来，「ffmpeg 缺失」必须落 `untested` 而不是绿。一个装不上工具的检查器
  报「13 项全过」，是本项目反复记的那个病。

所以：**解码/探测通过 `runner` 注入；业务判据在合成数据上真跑。**

## 为什么去重不用模型

claude-video 的做法：16×16 RGB 缩略图 + 均值通道差。用它是因为
**它不用模型也不花钱**，而且判据是确定的：同一段静止画面，去重前后的帧数
差多少是能算出来的。用模型做去重会让「去重有效」变成一句无法复核的话。

## 刻意与 claude-video 不同的一处

它按「帧数」控预算，我们还要记录**帧数 × 尺寸 × 模型**这一组读数 ——
同一段 30s 广告，100 帧 @512px 与 20 帧 @1024px 的信息量不同，token 可能差 5 倍。
它不管 ROI，我们管（虽然排在质量之后）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ──────────────────────────────────────────────────────────────────────
# balanced 帧策略：逐参数可配（方案 §三 的落地）
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FrameBudget:
    """`balanced` 档的逐参数。默认值就是方案 §三 那张表。"""

    #: 帧上限。★ 这是**硬上限**，不是提示 —— `extract_frames` 会在返回前截断。
    max_frames: int = 100
    #: 帧宽。含屏上文字时用 `width_with_text`（文字在 512px 下会糊成一片）。
    width: int = 512
    width_with_text: int = 1024
    #: 场景切变阈值（ffmpeg `select='gt(scene,T)'` 的 T）。0.3 是 claude-video 的口径。
    scene_threshold: float = 0.30
    #: 判「几乎静止」的下限：切变点少于这个数就回落均匀采样。
    min_scene_cuts: int = 3
    #: 均匀兜底时抽几帧。
    uniform_frames: int = 12
    #: 去重开关（对应 claude-video 的 `--no-dedup`）。关掉只为做反向对照。
    dedup: bool = True
    #: 缩略图边长。
    thumb: int = 16
    #: 均值通道差阈值（0–255 尺度）。低于它视为同一帧。
    dedup_threshold: float = 8.0

    def __post_init__(self):
        if self.max_frames <= 0:
            raise ValueError("max_frames 必须为正")
        if self.width <= 0 or self.width_with_text <= 0:
            raise ValueError("帧宽必须为正")
        if not (0.0 < self.scene_threshold < 1.0):
            raise ValueError("scene_threshold 必须在 (0,1) 之间")
        if self.thumb <= 0:
            raise ValueError("thumb 必须为正")
        if self.dedup_threshold < 0:
            raise ValueError("dedup_threshold 不得为负")


BALANCED = FrameBudget()


# ──────────────────────────────────────────────────────────────────────
# 探测：ffprobe
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    ok: bool
    duration_s: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok, "duration_s": self.duration_s,
            "width": self.width, "height": self.height, "fps": self.fps,
            "has_audio": self.has_audio, "reason": self.reason,
        }


#: `runner(args) -> (returncode, stdout_bytes, stderr_text)`
Runner = Callable[[Sequence[str]], Tuple[int, bytes, str]]


def subprocess_runner(args: Sequence[str], *, timeout: float = 120.0):
    """真跑外部命令。**这是本文件唯一执行子进程的地方。**"""
    try:
        proc = subprocess.run(list(args), capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, b"", "command_not_found:%s" % exc
    except subprocess.TimeoutExpired:
        return 124, b"", "timeout"
    except Exception as exc:  # noqa: BLE001
        return 1, b"", "%s:%s" % (type(exc).__name__, exc)
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")


def tools_available(names: Sequence[str] = ("ffmpeg", "ffprobe")) -> Dict[str, bool]:
    """工具在不在。★ 缺失时必须让调用方落 `untested`，不许当成「没问题」。"""
    return {name: shutil.which(name) is not None for name in names}


def probe_video(path: str | Path, *, runner: Optional[Runner] = None) -> ProbeResult:
    """读视频事实。失败返回 ok=False + reason，**不抛**（与 ocr_file 同一口径）。"""
    p = Path(path).expanduser()
    if not p.is_file():
        return ProbeResult(ok=False, reason="file_not_found")
    run = runner or subprocess_runner
    rc, out, err = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(p),
    ])
    if rc != 0:
        return ProbeResult(ok=False, reason="ffprobe_failed:%s" % (err or rc))
    try:
        payload = json.loads(out.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return ProbeResult(ok=False, reason="ffprobe_not_json")
    streams = payload.get("streams") or []
    fmt = payload.get("format") or {}
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        # ★ 没有视频流 = 这不是视频。不许当成「零帧的合法视频」。
        return ProbeResult(ok=False, reason="no_video_stream",
                           has_audio=audio is not None)
    duration = 0.0
    for raw in (fmt.get("duration"), video.get("duration")):
        try:
            duration = float(raw)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            break
    fps = 0.0
    rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "")
    if "/" in rate:
        num, _, den = rate.partition("/")
        try:
            fps = float(num) / float(den) if float(den) else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            fps = 0.0
    return ProbeResult(
        ok=True, duration_s=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=fps, has_audio=audio is not None, reason="")


# ──────────────────────────────────────────────────────────────────────
# 场景切变 + 均匀兜底
# ──────────────────────────────────────────────────────────────────────

def scene_cut_times(path: str | Path, *, budget: FrameBudget = BALANCED,
                    runner: Optional[Runner] = None) -> List[float]:
    """场景切变时刻（源相对秒）。解析 ffmpeg `showinfo` 的 `pts_time`。"""
    run = runner or subprocess_runner
    rc, out, err = run([
        "ffmpeg", "-v", "info", "-i", str(path),
        "-filter:v", "select='gt(scene,%s)',showinfo" % budget.scene_threshold,
        "-f", "null", "-",
    ])
    text = (err or "") + (out or b"").decode("utf-8", "replace")
    times: List[float] = []
    for line in text.splitlines():
        marker = "pts_time:"
        if marker not in line:
            continue
        chunk = line.split(marker, 1)[1].strip().split()[0]
        try:
            value = float(chunk)
        except ValueError:
            continue
        if value >= 0:
            times.append(round(value, 3))
    # ★ 同一切变可能被报两次（showinfo 对 select 之后的帧），去重保序
    seen, out_times = set(), []
    for t in sorted(times):
        if t in seen:
            continue
        seen.add(t)
        out_times.append(t)
    return out_times


def uniform_times(duration_s: float, count: int) -> List[float]:
    """在 `(0, duration)` 内均匀取 count 个时刻（源相对秒）。

    ★ 刻意不取 0 与 duration：开头常是黑场/片头留白，末尾常是静帧，
      两端都抽会让「抽了 12 帧」里有 2 帧是废的。
    """
    if duration_s <= 0 or count <= 0:
        return []
    step = duration_s / (count + 1)
    return [round(step * (i + 1), 3) for i in range(count)]


def plan_times(path: str | Path, duration_s: float, *,
               budget: FrameBudget = BALANCED,
               runner: Optional[Runner] = None) -> Tuple[List[float], str]:
    """定抽帧时刻。返回 (时刻列表, 用的哪条路)。

    `balanced` 的定义就是这个函数：**切变点够多就用切变，否则回落均匀**。
    返回的第二项（"scene" / "uniform"）要写进读数 —— 否则「为什么只有 4 帧」
    在报告里查不出来。
    """
    cuts = scene_cut_times(path, budget=budget, runner=runner)
    if len(cuts) >= budget.min_scene_cuts:
        return cuts[:budget.max_frames], "scene"
    # 几乎静止（或切变检测不到）→ 均匀兜底。
    # ★ 段短到均匀也抽不出 min_scene_cuts 帧时，就用能抽出的那些，
    #   不要为了「凑够数」重复同一个时刻。
    times = uniform_times(duration_s, min(budget.uniform_frames, budget.max_frames))
    return times, "uniform"


# ──────────────────────────────────────────────────────────────────────
# 抽帧 + 去重
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Frame:
    ts: float
    width: int
    height: int
    sha256: str
    source_uri: str
    data: bytes = b""
    #: 16×16 RGB 缩略图（去重依据）。落盘时不写进摘要，可用于排查。
    thumb: bytes = b""

    def to_dict(self, *, with_data: bool = False) -> Dict[str, Any]:
        out = {"ts": self.ts, "w": self.width, "h": self.height,
               "sha256": self.sha256, "source_uri": self.source_uri}
        if with_data:
            out["data"] = self.data
        return out


def mean_channel_diff(a: bytes, b: bytes) -> float:
    """两枚同尺寸 RGB 缩略图的均值通道差（0–255）。

    ★ 用「均值」而不是「最大」：单像素噪点（压缩伪影）会让最大值恒高，
      那样去重就永远不生效，而阈值怎么调都调不好。
    """
    if not a or not b or len(a) != len(b):
        # 尺寸不同 = 不是同一帧的候选；返回一个大值让调用方保留它
        return 255.0
    total = 0
    for x, y in zip(a, b):
        total += abs(x - y)
    return total / float(len(a))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_frame(path: str | Path, ts: float, *, width: int,
                  runner: Optional[Runner] = None) -> Optional[bytes]:
    """抽一帧（PNG 字节）。取不到返回 None —— 由调用方落「这一帧没抽到」。"""
    run = runner or subprocess_runner
    rc, out, err = run([
        "ffmpeg", "-v", "error", "-ss", "%.3f" % ts, "-i", str(path),
        "-frames:v", "1", "-vf", "scale=%d:-1" % width,
        "-f", "image2pipe", "-vcodec", "png", "-",
    ])
    if rc != 0 or not out:
        return None
    return out


def thumbnail_of(frame_bytes: bytes, *, size: int,
                 runner: Optional[Runner] = None) -> bytes:
    """帧字节 → size×size RGB 裸数据（用于去重）。

    ★ 为什么缩略图不走注入的 `runner`：`Runner` 的签名是 `args -> (rc, out, err)`，
      没有 stdin 位置 —— 而缩略图必须把**帧字节**喂进去。硬塞一个
      「args 里含 <<<STDIN>>> 就替换」的约定会让 runner 契约变复杂，
      而它的唯一用途是让探测/抽帧能在没有 ffmpeg 时被替换掉。
      所以缩略图单独一条真子进程路径，缺失工具时返回 `b""`，
      由 `mean_channel_diff` 把「空缩略图」判成「尺寸不同 → 保留」——
      **宁可多留一帧，也不要把不同的帧去重成一张**。
    """
    return _thumbnail_via_subprocess(frame_bytes, size)


def _thumbnail_via_subprocess(frame_bytes: bytes, size: int) -> bytes:
    """真缩略图：把帧字节从 stdin 喂给 ffmpeg。"""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0",
             "-vf", "scale=%d:%d" % (size, size),
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            input=frame_bytes, capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001
        return b""
    if proc.returncode != 0:
        return b""
    return proc.stdout


def dedupe_frames(frames: Sequence[Frame], *,
                  threshold: float) -> Tuple[List[Frame], List[int]]:
    """按缩略图去重。返回 (保留的帧, 被丢掉的原始下标)。

    ★ 与**上一枚被保留的帧**比，而不是与前一帧比：连续渐变（缓慢推镜）
      下与前一帧比永远「差不多」，于是整段被压成一帧；与保留帧比才会
      在累计差异超阈值时留下第二帧。
    """
    kept: List[Frame] = []
    dropped: List[int] = []
    for index, frame in enumerate(frames):
        if not kept:
            kept.append(frame)
            continue
        diff = mean_channel_diff(kept[-1].thumb, frame.thumb)
        if diff < threshold:
            dropped.append(index)
        else:
            kept.append(frame)
    return kept, dropped


def extract_frames(path: str | Path, *, budget: FrameBudget = BALANCED,
                   runner: Optional[Runner] = None,
                   has_text: bool = False,
                   source_uri: Optional[str] = None) -> Dict[str, Any]:
    """抽帧主入口。返回一份**可审计**的读数。

    返回：
      {
        "ok": bool, "reason": str,
        "strategy": "scene" | "uniform" | "",   # 用的哪条路
        "frames": [{ts,w,h,sha256,source_uri}],  # 去重后
        "raw_count": int, "kept_count": int, "dropped": int,
        "width": int, "has_audio": bool, "duration_s": float,
        "manifest_sha256": str,                  # 帧清单指纹（可复现判据）
      }

    ★ 同输入必须同输出：帧清单只由 (文件内容, budget, has_text) 决定，
      排序固定、时间戳固定、sha256 由帧字节算。`manifest_sha256` 是把这份
      清单规范化后算的指纹，两次跑必须相等 —— 这是「可复现」的可执行判据。
    """
    uri = source_uri or str(Path(path).expanduser().resolve())
    probe = probe_video(path, runner=runner)
    if not probe.ok:
        return {"ok": False, "reason": probe.reason, "strategy": "",
                "frames": [], "raw_count": 0, "kept_count": 0, "dropped": 0,
                "width": 0, "has_audio": False, "duration_s": 0.0,
                "manifest_sha256": ""}
    width = budget.width_with_text if has_text else budget.width
    times, strategy = plan_times(path, probe.duration_s, budget=budget,
                                 runner=runner)
    if len(times) > budget.max_frames:
        # ★ 硬上限：截断发生在抽帧**之前**，否则会白抽再丢（既慢又贵）
        times = times[:budget.max_frames]
    frames: List[Frame] = []
    for ts in times:
        data = extract_frame(path, ts, width=width, runner=runner)
        if data is None:
            continue
        thumb = thumbnail_of(data, size=budget.thumb, runner=runner)
        frames.append(Frame(
            ts=round(float(ts), 3), width=width, height=0,
            sha256=_sha256(data), source_uri=uri, data=data, thumb=thumb))
    raw_count = len(frames)
    dropped_indexes: List[int] = []
    if budget.dedup:
        frames, dropped_indexes = dedupe_frames(
            frames, threshold=budget.dedup_threshold)
    manifest = [f.to_dict() for f in frames]
    digest = hashlib.sha256(json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "ok": True, "reason": "",
        "strategy": strategy,
        "frames": manifest,
        "raw_count": raw_count,
        "kept_count": len(frames),
        "dropped": len(dropped_indexes),
        "width": width,
        "has_audio": probe.has_audio,
        "duration_s": probe.duration_s,
        "manifest_sha256": digest,
    }


# ──────────────────────────────────────────────────────────────────────
# V1 五项覆盖声明
# ──────────────────────────────────────────────────────────────────────

#: V1 五项（与 `tools/audit/report_render.mjs` 的 `V1_KEYS` 同名同序）。
#: ★ 两处各写一份是刻意：渲染器不许 import Python，本层不许 import Node。
#:   由 `verify_video_ingest` 断言两份**恒等**（漂移即红）。
V1_KEYS = ("字幕", "内嵌文字", "关键帧", "音轨", "完整画面语义")

#: 每一项的取值域。
#
# ★★ 2026-10-26：第一版我写的是中文枚举（已评/部分覆盖/未覆盖/not_applicable）——
#   那是**自己发明的第三套口径**。盘上已有两套、且它们是一回事：
#     · `Playbook/内容审查Agent-产品Playbook-v1.1.md:931` 用符号：✅ / ⛔ / ⚠️
#     · `tools/verify_report_render.mjs:141` 的 `V1_ENUM` 用英文：yes / no / partial
#   发明第三套的后果是报告里写着「部分覆盖」而校验器只认 "partial"，
#   于是每条视频报告都会被判红 —— 或者更糟，两边各自认为自己是对的。
#   本层照抄已确立的英文枚举，符号与中文只作为**展示层**映射（见 V1_LABELS）。
V1_VALUES = ("yes", "no", "partial")

#: 展示层映射：给定取值 → Playbook 里那个符号。**只用于渲染，不参与判定。**
V1_LABELS = {"yes": "✅", "no": "⛔", "partial": "⚠️"}


def video_covers(*, has_audio: bool, frames_kept: int,
                 transcript: bool = False, ocr_on_frames: bool = False,
                 scene_semantics: bool = False) -> Dict[str, str]:
    """V1 五项各自表态（取值域 = `V1_VALUES` 的 yes/no/partial）。

    ★ 四条硬规矩（都是「不许把没做说成做了」的形状）：
      1. **没有音轨 → 音轨=no**。Playbook V1 的原始承诺就是「音轨 ⛔」；
         第一阶段不做 ASR，所以音轨一律 no。★ 注意这与「有音轨但没转写」
         也是 no —— 两者在数值上同档，区分靠 `has_audio` 另存进读数
         （报告里写清「本来没有音轨」还是「有但没听」，见 `audio_note()`）。
      2. 没做 ASR → 字幕=no，即使有音轨。有音轨不等于听过。
      3. 没抽到帧 → 关键帧=no（0 帧不是「审完了 0 个问题」）。
      4. 完整画面语义**永远**不可能是 yes：它要的是整段理解，
         抽帧只能给 partial。这条是本函数里唯一无条件的。
    """
    if frames_kept <= 0:
        keyframe = "no"
    elif frames_kept < 20:
        keyframe = "partial"
    else:
        keyframe = "yes"
    # ★ Playbook V1 原文是「音轨 ⛔」—— 第一阶段承诺音轨为未覆盖。
    #   所以 `has_audio` **刻意不影响**这里的取值：有音轨也不会把它升成 partial，
    #   因为没做 ASR 就等于没听。`has_audio` 只用于 `audio_note()` 把
    #   「本来没有音轨」与「有但没听」分开 —— 那是**说明**，不是覆盖声明。
    #   这条刻意不用参数的做法也有断言守着（见 verify_video_ingest 的 E8-11）。
    return {
        "字幕": "partial" if transcript else "no",
        "内嵌文字": "partial" if ocr_on_frames else "no",
        "关键帧": keyframe,
        "音轨": "partial" if transcript else "no",
        # ★ 无论抽了多少帧，都不是「整段理解」。写 yes 等于把
        #   「看了 100 张图」说成「看完了整段视频」。
        "完整画面语义": "partial" if scene_semantics else "no",
    }


def audio_note(has_audio: bool, *, transcript: bool = False) -> str:
    """音轨那一档的**人读说明**。

    ★ 为什么需要它：`音轨=no` 有两种成因（本来没有音轨 / 有但没转写），
      在 V1 的取值域里同档。不把成因写出来，统计时就会变成一条永远修不掉的
      缺口，而其中一半根本不是缺口。这与 `not_applicable` 想解决的是同一个问题，
      只是不改枚举、改用文字说清 —— 改枚举会让报告与既有校验器打架。
    """
    if not has_audio:
        return "本条视频**没有音轨**（不是没审，是没有这项内容）"
    if transcript:
        return "有音轨且已转写（部分覆盖）"
    return "有音轨，**未做 ASR**，音轨内容未看"


def av_alignment_ready(media: Dict[str, str]) -> Tuple[bool, str]:
    """音画对齐的**前提检查**：必须同时有视频与音轨。

    ★ 只有视频时它只能说「字幕与画面的关系」，而需求原话要的是
      「音调/节奏」—— 那在音轨里。缺音轨就必须说缺，**不许**降级成静图分析。
      这条与 `base/multimodal_provider.py` 的 `required_media` 同一口径。
    """
    missing = [k for k in ("video", "audio") if not media.get(k)]
    if missing:
        return False, "缺介质 %s（av_alignment 必须同时有 video 与 audio）" % ", ".join(missing)
    return True, ""


def _usage():
    print("用法：")
    print("  python3 base/media_ingest.py --probe <video>    # 只读事实，不抽帧")
    print("  python3 base/media_ingest.py --frames <video>   # 抽帧读数（不落盘）")
    print("  python3 base/media_ingest.py --tools            # ffmpeg/ffprobe 在不在")
    print("★ 本文件不下载、不写盘、不联网：抽到的帧以字节返回给调用方。")


def main(argv: Sequence[str]) -> int:
    argv = list(argv)
    if not argv or "--tools" in argv:
        avail = tools_available()
        print("=" * 70)
        print("视频工具读数")
        print("=" * 70)
        for name, present in avail.items():
            print("  %-8s %s" % (name, "在" if present else "**不在**"))
        if not all(avail.values()):
            print("\n⚠️ 工具缺失 → 抽帧能力**未测**，不是「没有视频问题」。")
            return 2
        _usage()
        return 0
    if "--probe" in argv or "--frames" in argv:
        flag = "--probe" if "--probe" in argv else "--frames"
        idx = argv.index(flag)
        if idx + 1 >= len(argv):
            print("%s 需要一个视频路径" % flag)
            return 1
        path = Path(argv[idx + 1])
        avail = tools_available()
        if not all(avail.values()):
            missing = [n for n, ok in avail.items() if not ok]
            print("未测：缺 %s —— 抽帧无法执行" % ", ".join(missing))
            return 2
        probe = probe_video(path)
        print(json.dumps(probe.to_dict(), ensure_ascii=False, indent=2))
        if flag == "--probe":
            return 0 if probe.ok else 1
        result = extract_frames(path)
        result.pop("frames", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    _usage()
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
