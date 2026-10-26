#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multimodal_client.py — T-432：**全仓唯一有网络的地方**（多模态分析）

## 为什么网络只能在这里

`base/multimodal_provider.py` 的文件头写死：「本文件只做纯内存判断：没有 HTTP、
没有 URL、没有 socket、没有凭据读取。」理由是「一个需要联网才能验证的权限层，
在断网时最先失效」—— 而断网/限流/证书过期正是它最该工作的时候。

所以分工是：

    base/multimodal_provider.py   = 闸门 + 契约（一行网络都不许有）
    tools/multimodal_client.py    = 实现方（本文件，唯一发请求的地方）

调用链**必须**是：

    调用方 → provider_registry.analyze()
                → require_authorization(provider_id, task)   ← 闸门，未授权就抛
                → 实现方（本文件）发请求

★ 本文件**不自己判授权**。它假设「能被调用就说明已经过了闸门」，
  而这正是 `base/multimodal_provider.py` 的 `analyze()` 保证的事 ——
  两边各判一次看似更安全，实际会出现「闸门放行、客户端又拒」或反过来的分叉，
  届时没人说得清是哪一层拦的。

## 凭据

**只读环境变量，不读凭据文件。** 一个会去翻 `~/.dsh/credentials/` 的网络客户端，
等于把「谁可以读凭据」变成它的实现细节；而凭据目录的免读是 `AGENTS.md` §2.6
第 3 条的红线（`tools/agent/tools.mjs` 的 `secretGuard()` 在守）。

    MULTIMODAL_TOKENHUB_BASE_URL / MULTIMODAL_TOKENHUB_API_KEY
    MULTIMODAL_VOD_BASE_URL      / MULTIMODAL_VOD_API_TOKEN

## 没有凭据 / 没有网络 / 调用失败时返回什么

一律 `status="untested"` 或 `"error"`，**绝不允许**变成 `ok`。
一条「没看过图」的结果如果长得像「看过了、没问题」，下游会照它放行 ——
这是本项目反复记的那个病（AGENTS §2.4.1 与 `multimodal_provider` 文件头）。
"""

from __future__ import annotations

import base64
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 网关 → (base URL 环境变量, 凭据环境变量)
GATEWAY_ENV = {
    "tokenhub": ("MULTIMODAL_TOKENHUB_BASE_URL", "MULTIMODAL_TOKENHUB_API_KEY"),
    "vod": ("MULTIMODAL_VOD_BASE_URL", "MULTIMODAL_VOD_API_TOKEN"),
}

#: 默认网关。委托方 2026-10-26：「tokenhub 为主；vod 为辅」。
#: ★ 但**画面语义**走 tokenhub 成立、**音画对齐**不成立 —— 见 GATEWAY_MEDIA_NOTE。
DEFAULT_GATEWAY = "tokenhub"

GATEWAY_MEDIA_NOTE = {
    "tokenhub": (
        "tokenhub 的 glm-5.3-flash 系只有 image+pdf+text+video，**audio 0 家**；"
        "glm-5v-turbo / mimo-v2.6-* 声明了 audio 但未标价。"
        "所以 tokenhub 只能做 scene_semantics / mark_symbol，"
        "做 av_alignment 会被 provider 层的 required_media 闸门拒。"
    ),
    "vod": (
        "vod 有 gemini 家族（audio+image+pdf+text+video，12 个），"
        "是今天唯一能接 av_alignment 的一侧。"
    ),
}

#: 2026-10-26 实测读数（真调，1×1 纯色 PNG 探针，不是真实素材）：
#: 这一份是**某时某刻的读数**，不是常量 —— 模型上下线会变，
#: 复现命令见 verify_multimodal_client 的 --live 说明与 PMO 记录。
LIVE_PROBE_20261026 = {
    "tokenhub:glm-5.3-flash": "ok",
    "vod:gemini-3.1-flash-lite": "ok",
    "vod:gemini-3.5-flash": "ok",
    # ★ gemini-3.8-flash 当天返回 HTTP 429（request is limited）。
    #   所以 T-435 的音画对齐默认落 gemini-3.1-flash-lite，不是 3.8。
    "vod:gemini-3.8-flash": "error(429 rate_limited)",
}

#: 任务 → 需要送到模型的介质。与 base.multimodal_provider._REQUIRED_MEDIA 同一口径，
#: 但本文件**不 import 它**：那一层不许有网络，这一层不许依赖闸门的私有表。
#: 两边由 verify_multimodal_client 断言恒等（复制可以对，漂移不许）。
TASK_MEDIA = {
    "scene_semantics": ("image",),
    "mark_symbol": ("image",),
    "av_alignment": ("video", "audio"),
}

#: 任务 → 提给模型的指令。写死在这里，不从调用方自由文本拼 ——
#: 否则「分析什么」会随调用点漂移，同一张图两次问出两套结论。
TASK_PROMPTS = {
    "scene_semantics": (
        "你在为中文市场广告做合规审核的画面语义观察。只看画面，不要评价文案。"
        "请回答：①画面在演示什么使用场景；②画面是否暗示了具体功效或疗效；"
        "③品牌调性是否与产品一致；④画面里有没有需要人工复核的可疑元素。"
        "只描述你**确实看到**的；看不清就写「看不清」，不要推测。"
        "输出一行 JSON：{\"observations\":[{\"statement\":\"...\",\"confidence\":0-1,"
        "\"region\":\"画面位置描述\"}]}"
    ),
    "mark_symbol": (
        "你在为中文市场广告审核图标与认证标志。只看图形部分，不判断文字资质真伪。"
        "请回答：画面里出现了哪些认证徽章/图标，是否有伪造、改动或误导性使用迹象。"
        "看不清就写「看不清」。输出一行 JSON：{\"observations\":[{\"statement\":\"...\","
        "\"confidence\":0-1,\"region\":\"画面位置描述\"}]}"
    ),
    "av_alignment": (
        "你在为中文市场广告审核音画一致性。请同时看画面与听音轨，回答："
        "①字幕/口播说的内容与画面演示的是否一致；②音调节奏与画面情绪是否对得上；"
        "③有没有「说 A 演示 B」的错位。只描述确实观察到的不一致。"
        "输出一行 JSON：{\"observations\":[{\"statement\":\"...\",\"confidence\":0-1,"
        "\"timecode\":\"秒或区间\"}]}"
    ),
}


class ClientNotConfigured(RuntimeError):
    """网关或凭据没配。**不是**内容问题，是能力没接上。"""


# ──────────────────────────────────────────────────────────────────────
# 传输层：可注入
# ──────────────────────────────────────────────────────────────────────

@dataclass
class HttpResult:
    status: int
    body: str = ""
    error: str = ""


#: `post(url, headers, payload, timeout) -> HttpResult`
Transport = Callable[[str, Mapping[str, str], bytes, float], HttpResult]


def urllib_transport(url: str, headers: Mapping[str, str], payload: bytes,
                     timeout: float) -> HttpResult:
    """默认传输层。**唯一**真正发请求的代码。

    ★ 把传输层做成参数，是为了让所有判据能在**离线**下跑：
      两个实现（真 / 打桩）走同一套解析与状态映射，所以离线测的
      是「拿到响应之后怎么判」，而不是一个平行实现。
    """
    req = urllib.request.Request(url, data=payload, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return HttpResult(status=int(resp.status or 200),
                              body=raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return HttpResult(status=int(exc.code or 0), body=body, error="http_error")
    except urllib.error.URLError as exc:
        return HttpResult(status=0, error="url_error:%s" % (exc.reason,))
    except socket.timeout:
        return HttpResult(status=0, error="timeout")
    except Exception as exc:  # noqa: BLE001
        return HttpResult(status=0, error="%s:%s" % (type(exc).__name__, exc))


# ──────────────────────────────────────────────────────────────────────
# 媒体编码
# ──────────────────────────────────────────────────────────────────────

def _read_capped(path: Path, cap: int) -> bytes:
    with open(path, "rb") as f:
        data = f.read(cap + 1)
    if len(data) > cap:
        raise ValueError("媒体超过上限 %d 字节" % cap)
    return data


def _mime_of(path: Path) -> str:
    """按后缀给 MIME。★ 只用于**告诉网关**这是什么容器，
    不用它决定「能不能分析」—— 能力判定在闸门的 required_media 那一层。"""
    suffix = path.suffix.lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    }.get(suffix, "application/octet-stream")


def media_part(kind: str, path: Path, *, cap: int) -> Dict[str, Any]:
    """一个介质 → OpenAI 兼容 content part。

    图片走 `image_url`（data URL），音视频走 `video_url` / `input_audio`。
    ★ 容器里不带凭据、不带本地绝对路径 —— data URL 只含字节本身。
    """
    data = _read_capped(path, cap)
    b64 = base64.b64encode(data).decode("ascii")
    mime = _mime_of(path)
    if kind == "image":
        return {"type": "image_url",
                "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}}
    if kind == "video":
        return {"type": "video_url",
                "video_url": {"url": "data:%s;base64,%s" % (mime, b64)}}
    if kind == "audio":
        return {"type": "input_audio",
                "input_audio": {"data": b64,
                                "format": mime.split("/")[-1]}}
    raise ValueError("未知介质类型 %r" % (kind,))


# ──────────────────────────────────────────────────────────────────────
# 响应解析
# ──────────────────────────────────────────────────────────────────────

def _observations_from_text(text: str) -> Tuple[list, str]:
    """从模型回复里抽 observations。抽不出来返回 ([], 原因)。

    ★ 抽不出来**不是**「没有违规」，是「这一条没测成」。
      返回空列表 + 原因，由调用方落 untested —— 不许当成 ok 的空观察。
    """
    raw = (text or "").strip()
    if not raw:
        return [], "模型返回空正文"
    # 允许模型在 JSON 前后带解说：取第一个 { 到最后一个 }
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return [], "模型正文里没有 JSON 对象"
    try:
        parsed = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        return [], "JSON 解析失败：%s" % exc
    items = parsed.get("observations") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return [], "JSON 里没有 observations 数组"
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement") or "").strip()
        if not statement:
            continue
        entry = {"statement": statement}
        conf = item.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            entry["confidence"] = float(conf)
        for key in ("region", "timecode"):
            if isinstance(item.get(key), str) and item[key].strip():
                entry[key] = item[key].strip()
        out.append(entry)
    if not out:
        return [], "observations 数组里没有一条带 statement 的"
    return out, ""


def _openai_messages(task: str, parts: Sequence[Mapping[str, Any]]) -> list:
    content: list = [{"type": "text", "text": TASK_PROMPTS[task]}]
    content.extend(parts)
    return [{"role": "user", "content": content}]


# ──────────────────────────────────────────────────────────────────────
# 实现方：MultimodalProvider
# ──────────────────────────────────────────────────────────────────────

@dataclass
class GatewayClient:
    """一个网关连接。凭据只在**构造时**从环境读一次。"""

    gateway: str
    base_url: str
    api_key: str
    model: str
    timeout: float = 60.0
    transport: Transport = urllib_transport
    max_media_bytes: int = 24 * 1024 * 1024

    @classmethod
    def from_env(cls, gateway: str = DEFAULT_GATEWAY, *, model: str,
                 env: Optional[Mapping[str, str]] = None,
                 transport: Optional[Transport] = None,
                 timeout: float = 60.0) -> "GatewayClient":
        env = os.environ if env is None else env
        if gateway not in GATEWAY_ENV:
            raise ClientNotConfigured(
                "未知网关 %r；允许：%s" % (gateway, ", ".join(sorted(GATEWAY_ENV))))
        base_env, key_env = GATEWAY_ENV[gateway]
        base = (env.get(base_env) or "").strip()
        key = (env.get(key_env) or "").strip()
        missing = [n for n, v in ((base_env, base), (key_env, key)) if not v]
        if missing:
            raise ClientNotConfigured(
                "网关 %s 缺配置：%s（只读环境变量，不读凭据文件）"
                % (gateway, ", ".join(missing)))
        return cls(gateway=gateway, base_url=base.rstrip("/"), api_key=key,
                   model=model, timeout=timeout,
                   transport=transport or urllib_transport)

    def endpoint(self) -> str:
        return self.base_url + "/chat/completions"

    # ---- 单任务 -----------------------------------------------------

    def analyze_task(self, task: str, media: Mapping[str, Path]) -> Dict[str, Any]:
        """跑一个任务。返回该任务的 status 字典（与 provider 契约同形）。"""
        need = TASK_MEDIA.get(task)
        if need is None:
            return {"status": "untested", "reason": "未知任务 %r" % (task,),
                    "observations": []}
        missing = [k for k in need if k not in media]
        if missing:
            # ★ 缺介质不许降级：只有画面时 av_alignment 只能说缺音轨
            return {"status": "untested",
                    "reason": "缺介质 %s（本任务需要 %s）"
                              % (", ".join(missing), "+".join(need)),
                    "observations": [], "missing_media": missing}
        try:
            parts = [media_part(k, Path(media[k]), cap=self.max_media_bytes)
                     for k in need]
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "reason": "读媒体失败：%s" % exc,
                    "observations": []}
        payload = json.dumps({
            "model": self.model,
            "messages": _openai_messages(task, parts),
            "temperature": 0,
        }, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }
        result = self.transport(self.endpoint(), headers, payload, self.timeout)
        return self._interpret(task, result)

    def _interpret(self, task: str, result: HttpResult) -> Dict[str, Any]:
        """HTTP 结果 → provider 契约的 status 字典。

        ★ 状态映射是这一层最容易骗人的地方，逐条写死：
          没连上 / 超时 / 非 2xx / 空正文 / 解析不出 observations
          —— **全部**不许落 ok。
        """
        if result.status == 0:
            return {"status": "error",
                    "reason": "网络层失败：%s" % (result.error or "unknown"),
                    "observations": []}
        if not (200 <= result.status < 300):
            return {"status": "error",
                    "reason": "网关返回 HTTP %d：%s"
                              % (result.status, (result.body or "")[:300]),
                    "observations": [], "http_status": result.status}
        try:
            envelope = json.loads(result.body or "")
        except json.JSONDecodeError:
            return {"status": "error", "reason": "网关响应不是 JSON",
                    "observations": []}
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        if not isinstance(choices, list) or not choices:
            return {"status": "error", "reason": "网关响应没有 choices",
                    "observations": []}
        message = (choices[0] or {}).get("message") or {}
        text = message.get("content")
        if isinstance(text, list):
            # 有些实现把 content 给成分段数组
            text = "".join(str(p.get("text") or "") for p in text
                           if isinstance(p, dict))
        observations, why = _observations_from_text(str(text or ""))
        if why:
            return {"status": "untested", "reason": why, "observations": []}
        return {"status": "ok", "observations": observations, "reason": ""}

    def analyze(self, tasks: Sequence[str],
                media: Mapping[str, Path]) -> Dict[str, Any]:
        """跑多个任务，返回 provider 契约的完整形状。"""
        out: Dict[str, Any] = {"status": "ok", "tasks": {},
                               "model": "%s@%s" % (self.model, self.gateway),
                               "boundary": self.boundary_note()}
        worst = "ok"
        rank = {"ok": 0, "untested": 1, "error": 2}
        for task in tasks:
            entry = self.analyze_task(task, media)
            out["tasks"][task] = entry
            if rank.get(entry["status"], 2) > rank.get(worst, 0):
                worst = entry["status"]
        if not out["tasks"]:
            out["status"] = "untested"
            out["reason"] = "没有请求任何任务"
        else:
            out["status"] = worst
        return out

    @staticmethod
    def boundary_note() -> str:
        return ("只回答画面/图标/音画的**观察**，不产出 control_code 与 authority_ref；"
                "因此结果只能落 L1 观察，不能自行成为 finding。")


# ──────────────────────────────────────────────────────────────────────
# 与 provider 闸门对接：注册用的五件套
# ──────────────────────────────────────────────────────────────────────

#: 每个网关的**出境清单**（送什么、送给谁、送给哪些任务）。
#:
#: ★ 2026-10-26 修（T-438 抓到的）：第一版**没有写 `tasks`**。而 `EgressItem.tasks`
#:   为空 = 「适用于全部任务」—— 于是「只做画面语义」的部署，审计清单里也会列出
#:   音轨与整段视频。审计读到的出境面比实际大，与「少报了」是同一类错：
#:   一份看起来更严格的清单会让复核者跳过真正该看的项。
#:   每一项现在**逐个点名**它属于哪些任务，收窄才有执行点。
EGRESS_ITEMS = {
    "tokenhub": (
        {"item_id": "frame_image_b64",
         "description": "抽帧/原图的 base64 字节（含画面中的文字、人脸、场景）",
         # ★ 画面里可能有人脸与屏上文字，按 confidential 登记，不按 public。
         #   分级偏保守的代价只是审批严一点；偏松的代价是「以为送出去的是公开素材」。
         "data_class": "confidential",
         "tasks": ("scene_semantics", "mark_symbol")},
        {"item_id": "task_prompt_text",
         "description": "本文件写死的任务指令文本（不含任何客户数据）",
         "data_class": "internal",
         # 指令文本对每个任务都要送，所以列出全部 —— 但仍是**点名**，
         # 不是留空当「全都要」。留空会让新增任务时自动扩大出境面。
         "tasks": ("scene_semantics", "mark_symbol", "av_alignment")},
    ),
    "vod": (
        {"item_id": "frame_image_b64",
         "description": "抽帧/原图的 base64 字节（含画面中的文字、人脸、场景）",
         "data_class": "confidential",
         "tasks": ("scene_semantics", "mark_symbol")},
        {"item_id": "video_bytes_b64",
         "description": "整段视频字节（av_alignment 的 engine=direct 路径）",
         "data_class": "confidential",
         "tasks": ("av_alignment",)},
        {"item_id": "audio_bytes_b64",
         "description": "音轨字节（可能含人声，属 PII）",
         "data_class": "pii",
         "tasks": ("av_alignment",)},
        {"item_id": "task_prompt_text",
         "description": "本文件写死的任务指令文本（不含任何客户数据）",
         "data_class": "internal",
         "tasks": ("scene_semantics", "mark_symbol", "av_alignment")},
    ),
}

RECIPIENTS = {
    "tokenhub": "腾讯 TokenHub 网关（tokenhub.tencentmaas.com，境外可达性未核）",
    "vod": "腾讯云 VOD 网关（mmu.vod-qcloud.com）",
}


def gateway_supports(gateway: str, task: str) -> bool:
    """该网关在**今天**能不能做这个任务。

    ★ 这条不是配置，是事实读数（与 `PMO/implement/多模态与向量模型-选型-20261021.md`
      §四 对齐）：tokenhub 的 glm 家族 audio 为 0 家，所以做不了 av_alignment。
      把它写成函数而不是常量表，是因为它随模型清单变 —— 变的时候应当有人复核，
      而不是两个地方各写一份布尔值。
    """
    if gateway == "tokenhub":
        return task in ("scene_semantics", "mark_symbol")
    if gateway == "vod":
        return task in ("scene_semantics", "mark_symbol", "av_alignment")
    return False


def egress_items_for(gateway: str, tasks: Sequence[str]) -> Tuple[Dict[str, Any], ...]:
    """只登记**这次真要送**的项。

    ★ 全量登记会让出境清单变成一句「什么都可能送」，于是它不再能回答
      「这张图送出去的是什么」。按任务收窄，清单才有内容。
    """
    need = set()
    for task in tasks:
        need.update(TASK_MEDIA.get(task, ()))
    keys = set()
    for kind in need:
        if kind == "image":
            keys.add("frame_image_b64")
        elif kind == "video":
            keys.add("video_bytes_b64")
        elif kind == "audio":
            keys.add("audio_bytes_b64")
    keys.add("task_prompt_text")
    items = EGRESS_ITEMS.get(gateway, ())
    return tuple(i for i in items if i["item_id"] in keys)


def registration_for(gateway: str, *, model: str, tasks: Sequence[str],
                     authorized: bool = False):
    """造一条 `ProviderRegistration`（不注册，由调用方决定注册到哪个 registry）。

    ★ `authorized` 的默认值是 **False**。理由是 T-432 判据 2：
      「未授权时一次都不许调」。默认 True 等于「接上就出境」。
    """
    from base import multimodal_provider as MP

    tasks = tuple(t for t in tasks if gateway_supports(gateway, t))
    if not tasks:
        raise ValueError("网关 %s 不支持任何请求的任务 %r"
                         % (gateway, list(tasks)))
    required = {}
    for task in tasks:
        # 每个任务各自声明需要哪些授权项：内容出境与 PII 出境分开
        scopes = ["content_egress"]
        if "audio" in TASK_MEDIA.get(task, ()):
            scopes.append("pii_audio_egress")
        required[task] = tuple(scopes)
    return MP.ProviderRegistration(
        provider_id="%s:%s" % (gateway, model),
        egress_items=egress_items_for(gateway, tasks),
        recipient=RECIPIENTS[gateway],
        required_authorizations=required,
        authorized={task: bool(authorized) for task in tasks},
        granted_authorizations=tuple(
            sorted({s for scopes in required.values() for s in scopes})
        ) if authorized else (),
        note=("T-432：由 tools/multimodal_client.py 实现；"
              + GATEWAY_MEDIA_NOTE[gateway]),
    )


def _usage():
    print("用法：")
    print("  python3 tools/multimodal_client.py --whoami        # 只报配置是否齐（不打印密钥）")
    print("  python3 tools/multimodal_client.py --probe <image>  # 真调一次 scene_semantics")
    print("  ★ --probe 会真的把图片发出去。默认不做，必须显式点名文件。")


def main(argv: Sequence[str]) -> int:
    if "--whoami" in argv or not argv:
        print("=" * 70)
        print("多模态网关配置读数（**不打印密钥**）")
        print("=" * 70)
        for gw in sorted(GATEWAY_ENV):
            base_env, key_env = GATEWAY_ENV[gw]
            base = (os.environ.get(base_env) or "").strip()
            key = (os.environ.get(key_env) or "").strip()
            print("  %-9s base=%s key=%s"
                  % (gw,
                     base or "（未配）",
                     ("已配 %d 字符" % len(key)) if key else "（未配）"))
            print("           可做：%s"
                  % ", ".join(t for t in TASK_MEDIA if gateway_supports(gw, t)))
        _usage()
        return 0
    if "--probe" in argv:
        idx = argv.index("--probe")
        if idx + 1 >= len(argv):
            print("--probe 需要一个图片路径")
            return 1
        path = Path(argv[idx + 1])
        if not path.is_file():
            print("文件不存在：%s" % path)
            return 1
        model = os.environ.get("MULTIMODAL_MODEL") or "glm-5.3-flash"
        try:
            client = GatewayClient.from_env("tokenhub", model=model)
        except ClientNotConfigured as exc:
            print("未测：%s" % exc)
            return 2
        print("★ 即将把 %s 发给 %s" % (path.name, RECIPIENTS["tokenhub"]))
        result = client.analyze(["scene_semantics"], {"image": path})
        print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
        return 0 if result.get("status") == "ok" else 1
    _usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
