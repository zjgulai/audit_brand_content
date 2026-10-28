#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/media_analyze.py —— 多模态分析的**生产接线**（ADR-0021 · 主线）

## 它为什么存在

`base/judge_entry.py` 早就有 `multimodal_analyze` 注入点，
`tools/multimodal_client.py` 也早就建成了（3 个任务、两个网关、回落链）。
**但生产链路一个参数都没传** —— 2026-10-28 实测：

    grep -rn "multimodal_analyze|analyze_with_fallback" base/submission_service.py
    → 0 命中

于是每张图、每段视频的 `multimodal_observations` 都是一句
「未接入多模态分析」。这是本项目第四次同形：
`due_at` / 工作流耗时 / `semantic_judge` / `skill_hash`，
现在多一个 **多模态**。

## 它做的三件事

1. 把 `judge_entry` 期望的 `analyze(media_ref, tasks)` 形状
   适配到 `multimodal_client` 的真实接口（`tasks → {kind: Path}`）。
2. **图片**：一图多任务（scene_semantics + mark_symbol）。
3. **视频**：真·视频语义 —— 整段视频字节直接送模型（`av_alignment` + 画面语义）。

## ★★ 三条不许破的口径

### ① 凭据未配 → `untested`，**不是**空列表

`multimodal_client.GatewayClient.from_env()` 在缺环境变量时抛
`ClientNotConfigured`。这里把它翻译成 `{"status": "untested", "reason": ...}`，
**逐字带上「缺哪个变量」**。

理由：空列表在报告里会被读成「画面语义这一节没有内容 = 没问题」。
而实际上它恰恰是「没看成」。**未测不是通过。**

### ② 视频不靠 ASR —— 直接送视频字节

`base/media.py` 的 `DEFAULT_ASR_ENGINE = None`，`DEFAULT_OCR_ENGINE = "host_vision"`
（macOS 专用）。这两个不接，媒体线永远只能落 failed。

但**多模态模型不需要它们**：本机模型清单里 8951 个模型有 **1689 个支持 video 输入**
（Gemini 3 Pro / GLM-4.6V / Qwen3.8 / Kimi K3…）。
所以视频路径是「整段视频字节 → 模型」，与 OCR / ASR 两条本地引擎**完全解耦**。

### ③ 找不到本地文件 → 落 `error` 并说清，**不许猜路径**

`media_ref` 只带 `uri` 与 `sha256`，而客户端要的是本地 `Path`。
两者不是一回事：`uri` 可能是 `submission:xxx` 这种逻辑标识，
也可能是调用方给的**相对路径**（进件时按 media_roots 解析过）。

所以本模块要求调用方通过 `resolve_path` 传一个**已经解析好**的路径 ——
不从 uri 反推。反推会在 media_roots 有多个时猜错根目录，
而猜错的后果是「审了另一张图」：**它不会报错，只会给出错误的观察**。

## 不做什么

* 不实现 HTTP（那是 `tools/multimodal_client.py` 的职责，全仓唯一有网络的地方）。
* 不做授权判断（那是 `base/multimodal_provider.py` 的闸门）。
* 不产出 `control_code` / `authority_ref` —— 多模态只落 **L1 观察**，
  不能自行成为 finding（客户端 `boundary_note()` 里写着同一条）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

#: 图片默认任务。与 `judge_entry._collect_multimodal_observations` 的
#: `DEFAULT_MEDIA_TASKS` 保持同一集合 —— 但**不 import 它**（那边是判定层，
#: 这边是媒体层，反向依赖会让判定层 import 出错时媒体层一起挂）。
DEFAULT_IMAGE_TASKS = ("scene_semantics", "mark_symbol")

#: 视频在此之上再加音画对齐。
VIDEO_EXTRA_TASKS = ("av_alignment",)

#: 网关环境变量名。★ 与本模块的 `readiness()` 共用，改一处即可。
TOKENHUB_ENV = ("MULTIMODAL_TOKENHUB_BASE_URL", "MULTIMODAL_TOKENHUB_API_KEY")
VOD_ENV = ("MULTIMODAL_VOD_BASE_URL", "MULTIMODAL_VOD_API_TOKEN")


def readiness(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """多模态分析此刻能不能做。**返回可读读数**，不抛。

    这是「未配凭据」这件事的**唯一判定点** —— 界面、`/readyz`、报告都读它。
    分成两个网关是因为它们的任务覆盖面不同：
      · `tokenhub` 可做 `scene_semantics` / `mark_symbol`（图片两条）
      · `vod` 还多一个 `av_alignment`（视频）
    所以「tokenhub 配了、vod 没配」= 图片能审、视频不能 —— 这个区别必须能看见。
    """
    e = os.environ if env is None else env

    def _has(names: Tuple[str, ...]) -> bool:
        return all((e.get(n) or "").strip() for n in names)

    tokenhub_ok = _has(TOKENHUB_ENV)
    vod_ok = _has(VOD_ENV)
    missing = []
    if not tokenhub_ok:
        missing.extend(n for n in TOKENHUB_ENV if not (e.get(n) or "").strip())
    if not vod_ok:
        missing.extend(n for n in VOD_ENV if not (e.get(n) or "").strip())

    image_ok = tokenhub_ok or vod_ok
    video_ok = vod_ok

    return {
        "status": "ok" if image_ok else "untested",
        # ★ 图片与视频**分开报**：两者覆盖面不同，合并成一个布尔会让
        #   「视频不能审」被「图片能审」盖掉。
        "image": {"ready": image_ok,
                  "gateways": [g for g, ok in (("tokenhub", tokenhub_ok),
                                               ("vod", vod_ok)) if ok]},
        "video": {"ready": video_ok,
                  "gateways": ["vod"] if vod_ok else []},
        "missing_env": missing,
        "reason": (
            "" if image_ok
            else "多模态网关凭据未配（缺 %s）—— 图片/视频只能落「未测」，"
                 "不能报「没发现问题」" % "、".join(missing)
        ),
    }


def build_analyze(
    *,
    resolve_path: Callable[[Dict[str, Any]], Optional[Path]],
    env: Optional[Mapping[str, str]] = None,
    client_factory: Optional[Callable[..., Any]] = None,
) -> Optional[Callable[[Dict[str, Any], List[str]], Dict[str, Any]]]:
    """造一个符合 `judge_entry` 注入点契约的 `analyze(media_ref, tasks)`。

    ★ `resolve_path` 由调用方提供，**本模块不从 uri 反推**（见文件头 ③）。
      它拿到 `media_ref` 字典，返回本地 `Path` 或 `None`。

    ★ 返回 `None` 表示「现在做不了多模态」。调用方据此保持
      `multimodal_analyze=None` —— 那时 `judge_entry` 会落
      「未接入多模态分析」，与本模块的 `untested` 是两种不同原因，
      **两者都不许被读成「没问题」**。
    """
    ready = readiness(env)
    if not ready["image"]["ready"]:
        # 一个网关都没配 → 连 client 都不用建。
        return None

    def analyze(media_ref: Dict[str, Any], tasks: List[str]) -> Dict[str, Any]:
        kind = (media_ref or {}).get("kind")
        path = resolve_path(media_ref or {})
        if path is None:
            # ★ 找不到文件 → error，不是 untested：
            #   「我拿到了引用但读不到文件」与「我根本没测」是两件事。
            return {
                "status": "error",
                "reason": "无法把 media_ref 解析成本地文件：uri=%r"
                          % ((media_ref or {}).get("uri"),),
                "observations": [],
            }
        if not path.is_file():
            return {
                "status": "error",
                "reason": "媒体文件不存在：%s" % (path,),
                "observations": [],
            }

        # 视频要 av_alignment，而它只有 vod 支持 —— 未配 vod 时必须
        # **明说缺的是音轨那条**，而不是笼统「未测」。
        want = [t for t in tasks if t]
        if kind == "video" and not ready["video"]["ready"]:
            want = [t for t in want if t != "av_alignment"]
            dropped = "av_alignment"
        else:
            dropped = ""

        media = _media_map(kind, path)
        if not media:
            return {
                "status": "untested",
                "reason": "载体 %r 没有对应的多模态介质映射" % (kind,),
                "observations": [],
            }

        try:
            client = _make_client(env=env, client_factory=client_factory)
        except Exception as exc:  # noqa: BLE001
            # ★ 凭据缺失走这里。**不许吞成空列表** —— 那是「没看成」不是「没问题」。
            return {
                "status": "untested",
                "reason": "多模态客户端不可用：%s: %s" % (type(exc).__name__, exc),
                "observations": [],
            }

        try:
            raw = client.analyze(want, media)
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "observations": [],
            }

        out = _flatten(raw, want)
        if dropped:
            # 把「音轨那条没做」写进 reason，而不是让它静默少一个任务
            out["reason"] = ((out.get("reason") or "") +
                             ("；av_alignment 未做：vod 网关未配置" if not out.get("reason")
                              else "；av_alignment 未做：vod 网关未配置"))
        return out

    return analyze


def _media_map(kind: Optional[str], path: Path) -> Dict[str, Path]:
    """`kind` → 客户端要的 `{介质种类: 本地路径}`。

    ★ 与 `multimodal_client.TASK_MEDIA` 同口径：
      `scene_semantics` / `mark_symbol` 只吃 `image`，
      `av_alignment` 吃 `video` + `audio`。
    视频这一路把**同一份文件**同时当 video 与 audio 传 —— 因为 mp4 里两者都有。
    """
    if kind == "image":
        return {"image": path}
    if kind == "video":
        return {"video": path, "audio": path}
    return {}


def _make_client(*, env: Optional[Mapping[str, str]], client_factory):
    """建客户端。★ 惰性 import：`tools/` 不在生产镜像里时，
    本模块被 import 本身不该炸（那时应当落 untested 而不是 ImportError）。"""
    if client_factory is not None:
        return client_factory(env=env)
    from tools.multimodal_client import GatewayClient  # noqa: WPS433

    # 图片优先 tokenhub（委托方 2026-10-26：tokenhub 为主）；视频只有 vod 能做，
    # 但那个判断在 `readiness()` 里已经做过，这里只负责建一个能用的。
    e = os.environ if env is None else env
    gateway = "tokenhub" if all((e.get(n) or "").strip() for n in TOKENHUB_ENV) else "vod"
    model = (e.get("MULTIMODAL_MODEL") or "").strip() or "glm-5.3-flash"
    return GatewayClient.from_env(gateway, model=model, env=dict(e))


def _flatten(raw: Dict[str, Any], tasks: List[str]) -> Dict[str, Any]:
    """把客户端的 `{status, tasks: {task: {observations: [...]}}}` 摊平成
    `judge_entry` 期望的 `{status, observations: [{task, statement, ...}]}`。

    ★ 摊平时**保留 task 名**：报告里要能说「这条观察来自画面语义还是标志识别」，
      否则两条任务的结果混在一起，人复核时分不清该看哪一处。
    """
    out: Dict[str, Any] = {"status": raw.get("status") or "untested",
                           "observations": []}
    per_task = raw.get("tasks") or {}
    for task in tasks:
        entry = per_task.get(task) or {}
        for obs in entry.get("observations") or []:
            if not isinstance(obs, dict):
                continue
            out["observations"].append(dict(obs, task=task))
        # 该任务的 failure 也要带出来（不许因为它没 observations 就消失）
        if entry.get("status") in ("error", "untested") and entry.get("reason"):
            out.setdefault("task_reasons", {})[task] = entry["reason"]

    if not out["observations"] and out["status"] == "ok":
        # ★ 客户端说 ok 却一条观察都没有 —— 那多半是它把「看不清」吞了。
        #   降成 untested：**「看了但没说出来」不是「没问题」**。
        out["status"] = "untested"
        out["reason"] = "多模态返回 ok 但没有任何观察（看不清也算结果，不该是空）"
    return out
