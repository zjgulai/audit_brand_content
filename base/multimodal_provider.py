#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multimodal_provider.py —— 多模态能力的「授权 + 出境声明 + 策略」层。

一句话：本文件只回答三个问题，且只回答这三个：

  1. 如果启用某个 provider，**会送出去什么、送给谁**？  → `egress_manifest()`
  2. 这次调用**允许送吗**？                            → `require_authorization()`
  3. 没有 provider / 没有授权 / provider 没给结果时，
     调用方拿到的是什么？                              → `status = "untested"`，**不是通过**

===========================================================================
★ 为什么这里一行网络实现都不许有
===========================================================================

这一层如果自己会发请求，它就无法再充当「授权闸门」：

  * 授权检查会变成「发请求之前顺手跑一下」，而不是「不通过就根本不发」；
  * provider 实现方会开始依赖本层帮它重试、拼 URL、选区域，
    于是「数据出境到哪」重新散落到多个文件里；
  * 本层也无法被离线测试 —— 一个需要联网才能验证的权限层，
    在断网、限流、证书过期时最先失效，而那正是它最该工作的时候。

所以本文件只做纯内存判断：**没有 HTTP、没有 URL、没有 socket、没有凭据读取。**
真正发请求的是 `MultimodalProvider` 的实现方；本层只规定它「必须做什么」与
「不许做什么」，并在调用它之前把授权闸门关死。

===========================================================================
★ 为什么「没有 provider」必须返回 untested，而不是 [] / None / pass
===========================================================================

本项目已经反复踩过同一个形状：**没做**和**做了没问题**在返回值上长得一样。
多模态场景尤其危险 —— 一张图没被任何模型看过，如果调用方拿到 `[]`，
它会读成「没有发现违规」；拿到 `None`，它可能读成「没有结论」然后当成通过。
两者都会让「未测」静默变成「已审查」。

因此：没有 provider、任务为空、provider 不支持该任务、provider 返回缺字段，
一律落到 `"status": "untested"`，并在 `reason` 里写明**为什么未测**。
**未测不是红，也不是绿；它必须和两者都长得不一样。**

===========================================================================
★ 为什么授权要按「任务」而不是按「provider」给
===========================================================================

不同任务出境的数据不同：

  * `scene_semantics` 可能只需要抽帧后的静态画面；
  * `mark_symbol` 可能只需要图标/徽标的局部裁图；
  * `av_alignment` 需要音频轨、字幕文本，往往还涉及人声（PII）。

如果只按 provider 给一个布尔开关，那么「为了看画面语义而开的授权」
会顺带把音频轨也送出去。所以登记表里每个任务各自列：
**需要哪些授权项、当前是否已授权**；`require_authorization(provider_id, task)`
逐任务检查，缺哪一项就在异常里点名。

===========================================================================
★ 本层能证明什么、不能证明什么（这条必须写进每个返回结果）
===========================================================================

能证明：
  * 调用 provider 之前，登记表里该任务的授权项确实齐全；
  * 调用时交给 provider 的任务集合，与调用方请求的交集是明确的；
  * 「若启用会送出什么」有一份机器可读、可计算指纹的清单。

不能证明：
  * provider 实际把数据发给了谁、发了多少、有没有额外带上下文；
  * provider 有没有在服务端缓存、转存、二次分发。

所以每个结果里的 `policy_boundary.actual_egress_status` 只可能是：
  * `"none"`     —— 本次**没有调用任何 provider**（例如无 provider、无授权、任务不支持），
                    本层可以断言「本层没有发起出境」；
  * `"untested"` —— 本次**调用过 provider**，但本层零网络，无法观测实际出境。

**不要把 `actual_egress_status = "untested"` 读成「没出境」。** 它恰恰是说
「出境已经可能发生，而我没有能力证明范围」。真正的网络目的地审计必须由
provider 侧日志 / 网关 / 代理来完成，不是这一层。

===========================================================================
★ 允许 import 的范围（硬约束）
===========================================================================

只用标准库里纯内存的模块：`typing` / `enum` / `dataclasses` / `json` / `hashlib`。
不 import `requests` / `httpx` / `aiohttp` / `urllib.request` / `openai` / `anyio` /
`socket`，也不 import `os` / `sys` / `pathlib` —— 本层不碰文件系统、不读环境变量、
不解析命令行。文件末尾的自证只在 `python3 base/multimodal_provider.py` 时运行，
不写盘、不联网。
"""
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union


# ★ 2026-10-21 从 v1 升到 v2：`EgressItem` 加了 `tasks`、出境清单改成按任务展开、
#   并新增 `required_media` 闸门 —— **digest 的输入集合变了**。
#   版本号是让「旧 receipt 不被静默当成有效」的那把锁：见 `manifest_report_is_current()`。
SCHEMA_VERSION = "multimodal-provider-v2"

# 结果状态。`invalid_response` 是本层对「provider 返回结构坏了」的定性，
# 它既不是 provider 可以主动申报的状态，也不能被降级成 untested 之外的任何东西。
STATUS_OK = "ok"
STATUS_UNTESTED = "untested"
STATUS_ERROR = "error"
STATUS_INVALID_RESPONSE = "invalid_response"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_NOT_AUTHORIZED = "not_authorized"

_PROVIDER_STATUSES = (STATUS_OK, STATUS_UNTESTED, STATUS_ERROR)
_ALL_STATUSES = (
    STATUS_OK,
    STATUS_UNTESTED,
    STATUS_ERROR,
    STATUS_INVALID_RESPONSE,
    STATUS_NOT_CONFIGURED,
    STATUS_NOT_AUTHORIZED,
)

# 状态严重度：聚合时「坏的那个」优先。
# `invalid_response` 比 `error` 更靠前，因为结构坏了连「失败原因」都不可信。
_STATUS_ORDER = {
    STATUS_OK: 0,
    STATUS_UNTESTED: 1,
    STATUS_ERROR: 2,
    STATUS_INVALID_RESPONSE: 3,
    STATUS_NOT_CONFIGURED: 4,
    STATUS_NOT_AUTHORIZED: 5,
}

# 数据分级：审计需要知道「出境的是公开素材还是 PII」，不能只写「一些数据」。
DATA_CLASSES = frozenset({"public", "internal", "confidential", "pii"})

# 占位词。登记表里出现这些词，审计读到的不是「接收方」，而是一句空话。
# 本项目在下载治理里已经踩过 `consumer: "系统"` 这种假登记，这里提前拦。
_PLACEHOLDERS = frozenset(
    {"", "-", "todo", "tbd", "unknown", "n/a", "na", "系统", "未定", "待定", "待补"}
)

_HEX = frozenset("0123456789abcdef")

# `ref_sha256` 与 `content_sha256` 的区别必须写在结果里：
# 前者只是把同一个引用对上号，后者才是媒体内容指纹。混用会让「同一份文件」
# 这句话在没有内容指纹时变成假精度。
_MEDIA_REF_NOTE = (
    "ref_sha256 只用于把同一引用对上号，不是媒体内容指纹；"
    "本层不打开、不下载 media_ref。content_sha256 只有调用方显式提供时才存在。"
)


# ══════════════════════════════════════════════════════════════════════════
# ① 三类任务
# ══════════════════════════════════════════════════════════════════════════

class MultimodalTask(str, Enum):
    """本层允许请求的多模态任务。值一旦写进登记表/状态文件，就不许改名。"""

    # 画面语义：画面里在做什么、暗示了什么功效或使用场景、品牌调性与文案是否一致。
    SCENE_SEMANTICS = "scene_semantics"
    # 图标与认证标志的图形部分：认证徽章是否伪造、图标是否被改动或误导性使用。
    # 注意它只覆盖「图形部分」，认证文字真伪仍由文本/资质链路判定。
    MARK_SYMBOL = "mark_symbol"
    # 音视频对齐：音调/节奏/字幕/画面是否对不上（例如字幕说 A、画面演示 B）。
    AV_ALIGNMENT = "av_alignment"

    @property
    def required_media(self) -> Tuple[str, ...]:
        """这条任务**必须**拿到哪些介质才谈得上分析。

        ★ 这是 2026-10-21 补的闸门，起因是一个具体的读数：
          `glm-5.3-flash` 在 27 家 provider 上 `audio` 是 **0 家**
          （`image+pdf+text+video` 14 / `image+text` 6 / `image+text+video` 4 / `text` 3）。
          拿它做 `av_alignment` 做视频时，**不会报错**，只会返回一个
          「看起来分析过了」的结果 —— 音轨那一路它根本没看。

        所以「模态够不够」必须在**调用之前**判，且判据落在契约里而不是实现方脑子里。
        判不够就落 `untested` 并说清缺哪种介质；**不许**静默放行、**不许**抛异常。
        """
        return _REQUIRED_MEDIA[self]


# 任务 → 必需介质。空元组表示「不依赖具体介质」（当前没有这样的任务）。
_REQUIRED_MEDIA: Dict["MultimodalTask", Tuple[str, ...]] = {
    MultimodalTask.SCENE_SEMANTICS: ("image",),
    MultimodalTask.MARK_SYMBOL: ("image",),
    # 音画对齐要**同时**有画面与音轨：只有画面时它只能看字幕与画面的关系，
    # 而需求原话要的是「音调/节奏」——那在音轨里。缺音轨就必须说缺，不许降级成静图分析。
    MultimodalTask.AV_ALIGNMENT: ("video", "audio"),
}


TASK_DESCRIPTIONS = {
    MultimodalTask.SCENE_SEMANTICS.value: (
        "画面语义：画面在演示什么、暗示了什么功效/场景、品牌调性是否与文案一致"
    ),
    MultimodalTask.MARK_SYMBOL.value: (
        "图标与认证标志的图形部分：认证徽章是否伪造、图标是否被改动或误导性使用"
    ),
    MultimodalTask.AV_ALIGNMENT.value: (
        "音视频对齐：音调/节奏/字幕/画面的内容是否一致"
    ),
}

_TASK_ORDER = tuple(task.value for task in MultimodalTask)


def _coerce_task(value: Any) -> MultimodalTask:
    """把字符串或枚举统一成 MultimodalTask；未知值必须炸，不许静默忽略。"""
    if isinstance(value, MultimodalTask):
        return value
    if isinstance(value, str):
        try:
            return MultimodalTask(value)
        except ValueError:
            pass
    raise ValueError(
        "未知多模态任务 %r；允许值：%s" % (value, ", ".join(_TASK_ORDER))
    )


def normalize_tasks(tasks: Any) -> Tuple[MultimodalTask, ...]:
    """把单任务/序列统一成去重后的任务元组，保持调用方给定的顺序。"""
    if tasks is None:
        raise TypeError("tasks 不能为 None；没有任务时请传空序列，本层会返回 untested")
    if isinstance(tasks, (MultimodalTask, str)):
        raw = (tasks,)
    elif isinstance(tasks, Mapping):
        # dict 的迭代结果是键，容易被误当成任务序列；直接拒绝比猜更安全。
        raise TypeError("tasks 不能是映射；请传任务值序列，例如 ['scene_semantics']")
    else:
        try:
            raw = tuple(tasks)
        except TypeError:
            raise TypeError(
                "tasks 必须是单个任务或任务序列，收到 %r" % (type(tasks).__name__,)
            )

    out: List[MultimodalTask] = []
    seen = set()
    for item in raw:
        task = _coerce_task(item)
        if task in seen:
            # 重复任务不改变语义，但去重必须留在这里而不是交给 provider，
            # 否则 provider 可能把同一任务算两次、重复计费/重复出境。
            continue
        seen.add(task)
        out.append(task)
    return tuple(out)


# ══════════════════════════════════════════════════════════════════════════
# ② 媒体引用：只记录引用，不读取内容
# ══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MediaRef:
    """一个**不透明**的媒体引用。

    `uri` 可以是本地路径、对象存储 key、或调用方自己的句柄名。
    本层**不会**打开它、下载它、解析它；它只被交给 provider 实现方。

    `sha256` 是调用方**显式提供**的媒体内容指纹。没有提供时，本层不会
    拿 `uri` 的字符串哈希冒充内容指纹 —— 那是本项目反复纠正过的假精度。
    """

    uri: str
    sha256: Optional[str] = None
    mime: Optional[str] = None
    byte_size: Optional[int] = None
    kind: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", _require_text(self.uri, "MediaRef.uri"))
        if self.sha256 is not None:
            normalized = _normalize_sha256(self.sha256)
            if normalized is None:
                raise ValueError(
                    "MediaRef.sha256 必须是 64 位十六进制；收到 %r" % (self.sha256,)
                )
            object.__setattr__(self, "sha256", normalized)
        if self.mime is not None:
            object.__setattr__(self, "mime", _require_text(self.mime, "MediaRef.mime"))
        if self.kind is not None:
            object.__setattr__(self, "kind", _require_text(self.kind, "MediaRef.kind"))
        if self.byte_size is not None:
            if isinstance(self.byte_size, bool) or not isinstance(self.byte_size, int):
                raise ValueError("MediaRef.byte_size 必须是非负整数")
            if self.byte_size < 0:
                raise ValueError("MediaRef.byte_size 必须是非负整数")


def _normalize_sha256(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if len(candidate) != 64:
        return None
    if any(ch not in _HEX for ch in candidate):
        return None
    return candidate


def _sha256_text(value: str) -> str:
    # 只对「引用字符串」做摘要，不打开它指向的任何东西。
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _describe_media_ref(media_ref: Any) -> Dict[str, Any]:
    """把 media_ref 描述成审计可读的元信息；**任何输入都不许在这里炸**。

    原因：`analyze()` 的一条硬约定是「没有 provider 时返回 untested」。
    如果这里对奇怪的 media_ref 抛异常，调用方就连「未测」都拿不到，
    只会看到一个与授权无关的类型错误。所以这里降级成 `content_sha256_status`
    的 `"invalid"` / `"untested"`，把问题说清楚，而不是中断整个策略判断。
    """
    base: Dict[str, Any] = {
        "ref_type": type(media_ref).__name__,
        "ref_sha256": None,
        "content_sha256": None,
        "content_sha256_status": STATUS_UNTESTED,
        "content_sha256_reason": "本层没有拿到可识别的媒体引用。",
        "mime": None,
        "byte_size": None,
        "kind": None,
        "declared_fields": [],
        "note": _MEDIA_REF_NOTE,
    }

    if isinstance(media_ref, MediaRef):
        base.update(
            {
                "ref_type": "MediaRef",
                "ref_sha256": _sha256_text(media_ref.uri),
                "content_sha256": media_ref.sha256,
                "content_sha256_status": (
                    "provided" if media_ref.sha256 else STATUS_UNTESTED
                ),
                "content_sha256_reason": (
                    ""
                    if media_ref.sha256
                    else "调用方没有提供媒体内容 sha256；本层不打开 media_ref，无法自己算。"
                ),
                "mime": media_ref.mime,
                "byte_size": media_ref.byte_size,
                "kind": media_ref.kind,
            }
        )
        return base

    if isinstance(media_ref, str):
        if not media_ref.strip():
            base["content_sha256_reason"] = "media_ref 是空字符串，无法形成有效引用。"
            return base
        base.update(
            {
                "ref_type": "str",
                "ref_sha256": _sha256_text(media_ref),
                "content_sha256_status": STATUS_UNTESTED,
                "content_sha256_reason": (
                    "media_ref 是字符串引用；本层不打开它，所以没有内容指纹。"
                ),
            }
        )
        return base

    if isinstance(media_ref, Mapping):
        keys = sorted(str(k) for k in media_ref.keys())
        base["declared_fields"] = keys
        uri = media_ref.get("uri")
        if uri is None:
            uri = media_ref.get("ref")
        if uri is None:
            uri = media_ref.get("path")

        content_sha_raw = media_ref.get("sha256")
        content_sha = _normalize_sha256(content_sha_raw)
        if content_sha_raw is None:
            sha_status = STATUS_UNTESTED
            sha_reason = "调用方没有提供 sha256 字段；本层不读取 media_ref 指向的内容。"
        elif content_sha is None:
            sha_status = "invalid"
            sha_reason = "sha256 字段不是 64 位十六进制，已丢弃，不能当成内容指纹。"
        else:
            sha_status = "provided"
            sha_reason = ""

        mime = media_ref.get("mime")
        if mime is None:
            mime = media_ref.get("content_type")
        byte_size = media_ref.get("byte_size")
        if byte_size is None:
            byte_size = media_ref.get("size")
        kind = media_ref.get("kind")
        if kind is None:
            kind = media_ref.get("media_type")

        if isinstance(uri, str) and uri.strip():
            base["ref_type"] = "mapping"
            base["ref_sha256"] = _sha256_text(uri)
            base["content_sha256"] = content_sha
            base["content_sha256_status"] = sha_status
            base["content_sha256_reason"] = sha_reason
        else:
            base["content_sha256"] = content_sha
            base["content_sha256_status"] = sha_status if content_sha else STATUS_UNTESTED
            base["content_sha256_reason"] = (
                "media_ref 是映射但没有字符串 uri/ref/path；本层不能形成引用指纹。"
            )

        if isinstance(mime, str) and mime.strip():
            base["mime"] = mime
        if isinstance(byte_size, int) and not isinstance(byte_size, bool):
            base["byte_size"] = byte_size
        if isinstance(kind, str) and kind.strip():
            base["kind"] = kind
        return base

    # 未知类型：不猜、不 str() 它（可能触发对象的 __str__ 副作用）。
    base["content_sha256_reason"] = (
        "media_ref 类型 %r 不在本层认识范围内；本层不读取它，交由 provider 合约处理。"
        % (type(media_ref).__name__,)
    )
    return base


# ══════════════════════════════════════════════════════════════════════════
# ②b 介质充分性：任务要的介质，这个 media_ref 有没有
# ══════════════════════════════════════════════════════════════════════════

# kind / mime 里的介质线索。**刻意用「包含」而不是精确匹配**：
# `kind` 是调用方自由填的字符串（本层不做枚举改造 —— 那会把「未来新增媒体类型」
# 变成一次契约修订），所以这里只认得出常见的写法，认不出就落 untested。
#
# ★ 为什么同时读 kind **和** mime：实测这两个是独立字段，
#   `MediaRef(uri=..., mime="audio/mpeg")` 的 kind 是 None，
#   `MediaRef(uri=..., kind="video/mp4")` 的 mime 是 None。
#   只读 kind 会把「只填了 mime」的调用方误判成「什么都没给」。
_MEDIA_HINTS: Dict[str, Tuple[str, ...]] = {
    "image": ("image", "img", "picture", "photo", "jpg", "jpeg", "png",
              "webp", "gif", "bmp", "heic", "静图", "图片", "画面"),
    "video": ("video", "movie", "mp4", "mov", "mkv", "webm", "avi",
              "视频", "影片"),
    "audio": ("audio", "sound", "voice", "mp3", "wav", "aac", "m4a",
              "flac", "ogg", "音轨", "音频", "语音"),
}


def _declared_media(media: Mapping[str, Any]) -> Tuple[str, ...]:
    """从已归一化的 media 描述里读出「调用方声明了哪些介质」。"""
    blob = " ".join(
        str(media.get(field) or "") for field in ("kind", "mime")
    ).lower()
    if not blob.strip():
        return ()
    found = []
    for medium, hints in _MEDIA_HINTS.items():
        if any(hint in blob for hint in hints):
            found.append(medium)
    return tuple(sorted(found))


def _missing_media(
    task: MultimodalTask, media: Mapping[str, Any]
) -> Tuple[str, ...]:
    """该任务缺哪些介质；空的元组表示「要的都有」。

    ★ 语义上最要紧的一条：`required_media` 非空而**调用方什么都没声明**时，
      结果是「全都缺」，不是「不缺」。因为「没说是图片」不等于「是图片」，
      而这正是本项目反复纠正过的形状（没测被读成通过）。
    """
    required = task.required_media
    if not required:
        return ()
    declared = set(_declared_media(media))
    return tuple(medium for medium in required if medium not in declared)


# ══════════════════════════════════════════════════════════════════════════
# ③ provider 协议
# ══════════════════════════════════════════════════════════════════════════

class MultimodalProvider:
    """多模态分析实现方的协议（抽象基类）。

    这里**故意不 import `abc`**：本文件的硬约束是只用
    `typing` / `enum` / `dataclasses` / `json` / `hashlib`。
    继承本类不是运行时的强制条件（注册表只要求 `analyze` 可调用且
    `provider_id` 与登记表一致），但继承它能让实现方读到下面这份合约。

    ------------------------------------------------------------------
    实现方**必须**做
    ------------------------------------------------------------------
    1. 把 `provider_id` 设成与 `ProviderRegistration.provider_id` **完全一致**。
       不一致时，审计看到的名字和实际被调用的对象对不上，必须拒。
    2. `analyze(media_ref, tasks)` 返回一个 **dict**：
       {
         "status": "ok" | "untested" | "error",
         "tasks": {
           "<task value>": {
             "status": "ok" | "untested" | "error",
             "observations": [...],   # status=ok 时必须是列表；没话可说也要给 []
             "reason": "..."          # status != ok 时必须非空
           },
           ...
         },
         "model": "模型/版本标识（可选，但强烈建议）",
         "boundary": "这次分析覆盖不到什么（可选，但强烈建议）"
       }
    3. 只读取完成**已声明任务**所必需的媒体内容；只把内容发给
       `ProviderRegistration.recipient` 声明的接收方。
    4. 每个请求过的任务都要在 `tasks` 里有条目。做不到就写 `untested` 并说明原因。
    5. 任何不确定都落到 `untested` / `error`；**不要猜一个 `ok` 出来**。

    ------------------------------------------------------------------
    实现方**不许**做
    ------------------------------------------------------------------
    1. 不许把媒体或派生数据发给登记表 `recipient` 之外的任何一方，
       包括「备用区域」「免费额度节点」「日志/监控 SaaS」。
    2. 不许在未授权时自行降级到另一个服务或另一个账号。
    3. 不许把「没调用模型」「模型不可用」「超时」写成 `ok`。
    4. 不许在报告里自报 `authorized` / `egress` 让本层采信 ——
       授权状态只来自登记表，出境清单只来自 `egress_manifest()`。
    5. 不许持久化、缓存、转存原始媒体（除非另有明确的数据保留授权，
       且该保留动作本身要出现在 `egress_items` 里）。
    6. 不许读取凭据文件、环境变量里的密钥，或把密钥写进报告/日志。
    7. 不许返回 `None`、裸列表、裸字符串或生成器；结构必须可审计。
    """

    # 子类必须覆盖成与登记表一致的值。留空会让注册直接失败。
    provider_id: str = ""

    def analyze(
        self, media_ref: Any, tasks: Sequence[MultimodalTask]
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "MultimodalProvider.analyze 必须由实现方覆写；"
            "本基类不提供任何默认分析，也不允许把『没实现』当成通过。"
        )


# ══════════════════════════════════════════════════════════════════════════
# ④ 两个异常：没配 / 没授权
# ══════════════════════════════════════════════════════════════════════════

class MultimodalPolicyError(Exception):
    """策略层异常的公共基类；带 `to_dict()`，方便调用方把拒绝写成结构化状态。"""

    status = STATUS_ERROR

    def __init__(
        self,
        message: str,
        *,
        provider_id: Optional[str] = None,
        task: Optional[MultimodalTask] = None,
        missing: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.task = task
        self.missing = tuple(missing)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": str(self),
            "provider_id": self.provider_id,
            "task": self.task.value if self.task is not None else None,
            "missing": list(self.missing),
        }


class NotConfigured(MultimodalPolicyError):
    """没有 provider / provider 未注册 / provider 未声明该任务。

    这类情况不是「内容有问题」，而是「能力还没接上」。`analyze()` 对
    **空注册表**会直接返回 `untested`；只有调用方显式点名了一个不存在/不支持
    的 provider 时才抛这个异常，因为那是配置或拼写错误，不该被静默吞掉。
    """

    status = STATUS_NOT_CONFIGURED


class NotAuthorized(MultimodalPolicyError):
    """登记表里的授权项不齐，调用被拒绝。

    `missing` 必须**点名**缺的是哪一项 —— 只说「未授权」会让下一个人
    重新去猜是哪个 scope、哪个任务，最后往往变成「干脆全开」。
    """

    status = STATUS_NOT_AUTHORIZED

    def __init__(
        self,
        provider_id: str,
        task: MultimodalTask,
        missing: Sequence[str],
        message: Optional[str] = None,
    ) -> None:
        missing_tuple = tuple(missing) or ("task:%s" % task.value,)
        if message is None:
            message = (
                "未授权：provider %r 的任务 %r 缺少授权项 %s。"
                "本层不会调用 provider，也不会把『没授权』写成 untested 或通过。"
                % (provider_id, task.value, ", ".join(missing_tuple))
            )
        super().__init__(
            message, provider_id=provider_id, task=task, missing=missing_tuple
        )


# ══════════════════════════════════════════════════════════════════════════
# ⑤ 登记表：五件套
# ══════════════════════════════════════════════════════════════════════════

def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "%s 必须是字符串，收到 %r" % (field, type(value).__name__)
        )
    if not value.strip():
        raise ValueError("%s 不能为空" % field)
    if value.strip().lower() in _PLACEHOLDERS:
        raise ValueError(
            "%s 不能是占位词 %r；审计需要能指得出具体对象" % (field, value)
        )
    return value


def _normalize_scopes(value: Any, field: str) -> Tuple[str, ...]:
    # 单个字符串会被逐字符遍历，是最常见、也最难发现的错误输入。
    if isinstance(value, str):
        raise ValueError(
            "%s 必须是字符串序列，不能是单个字符串（否则每个字符都会被当成一项）"
            % field
        )
    try:
        raw = tuple(value)
    except TypeError:
        raise ValueError("%s 必须是字符串序列，收到 %r" % (field, type(value).__name__))
    out: List[str] = []
    for item in raw:
        out.append(_require_text(item, field + "[]"))
    if len(set(out)) != len(out):
        raise ValueError("%s 有重复项；重复授权项会让清单读数虚高" % field)
    # 授权项是集合语义；按字典序归一，保证 egress_manifest 的指纹不受
    # 调用方书写顺序影响。否则同一套授权换个顺序就会得到另一个 digest。
    return tuple(sorted(out))


def _normalize_task_names(value: Any, field: str) -> Tuple[str, ...]:
    """把「任务名序列」归一成去重、按枚举序排列的字符串元组。

    与 `_normalize_scopes` 同一条纪律：**单个字符串必须拒绝**，
    否则 `"scene_semantics"` 会被逐字符拆成 15 个任务名，
    而拼错的项又会在过滤时静默地什么都不命中 —— 清单于是变成空，看起来像「不出境」。
    """
    if isinstance(value, str):
        raise ValueError(
            "%s 必须是字符串序列，不能是单个字符串（否则每个字符都会被当成一个任务）"
            % field
        )
    try:
        raw = tuple(value)
    except TypeError:
        raise ValueError("%s 必须是字符串序列，收到 %r" % (field, type(value).__name__))
    seen = set()
    for item in raw:
        task = _coerce_task(item)      # 未知任务名在这里就炸，不许静默忽略
        if task.value in seen:
            raise ValueError("%s 有重复任务 %r" % (field, task.value))
        seen.add(task.value)
    # 按枚举序归一：同一套任务换个书写顺序必须得到同一份清单指纹。
    return tuple(name for name in _TASK_ORDER if name in seen)


def _normalize_required_map(value: Any) -> Dict[str, Tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise ValueError("required_authorizations 必须是 Mapping")
    if not value:
        raise ValueError(
            "required_authorizations 不能为空：没有声明任何任务/授权项的 provider "
            "不该经过本闸门"
        )
    out: Dict[str, Tuple[str, ...]] = {}
    for raw_task, raw_scopes in value.items():
        task = _coerce_task(raw_task)
        if task.value in out:
            raise ValueError("required_authorizations 重复任务 %r" % task.value)
        scopes = _normalize_scopes(
            raw_scopes, "required_authorizations[%s]" % task.value
        )
        if not scopes:
            # 空授权项等于「不需要授权」，会把闸门变成装饰。
            # 如果确实不需要授权，应该走本地路径，而不是登记一个 provider 再写空列表。
            raise ValueError(
                "required_authorizations[%s] 不能为空；"
                "没有授权项的任务不该经过本闸门" % task.value
            )
        out[task.value] = scopes
    # 按枚举顺序归一，保证 egress_manifest 的 JSON 顺序稳定、指纹可复现。
    return {task: out[task] for task in _TASK_ORDER if task in out}


def _normalize_authorized_map(
    value: Any, required_tasks: Sequence[str]
) -> Dict[str, bool]:
    # 五件套里的「是否已授权」既可以是逐任务 mapping（推荐），
    # 也可以是一个显式 bool 应用到全部已声明任务。**没有默认值**：
    # 不传、传 None、传 "yes" 都必须报错，不能让漏配变成放行。
    if isinstance(value, bool):
        return {task: value for task in required_tasks}
    if not isinstance(value, Mapping):
        raise ValueError(
            "authorized 必须是 Mapping（逐任务 True/False）或一个显式 bool"
        )
    out: Dict[str, bool] = {}
    for raw_task, raw_state in value.items():
        task = _coerce_task(raw_task)
        if task.value in out:
            raise ValueError("authorized 重复任务 %r" % task.value)
        # 只接受真正的 bool。字符串 "yes"/"1"、整数 1 都不行 ——
        # 一个模糊的「看起来像已授权」正是本层要消灭的东西。
        if not isinstance(raw_state, bool):
            raise ValueError(
                "authorized[%s] 必须是 True/False，收到 %r；"
                "默认值或真值转换会让『没配』悄悄变成『放行』"
                % (task.value, raw_state)
            )
        out[task.value] = raw_state
    return {task: out[task] for task in _TASK_ORDER if task in out}


@dataclass(frozen=True)
class EgressItem:
    """一项可能出境的数据。

    `data_class` 不是装饰：审计最先问的是「有没有 PII 出境」。
    把音频轨标成 `internal` 而它含人声，就是登记表在说谎。

    ★ `tasks`（2026-10-21 加）：这一项**对哪些任务**会出境。
      空元组 = 适用于全部任务（默认，等于旧行为）。

    **为什么必须加这个字段**：原先 `egress_items` 只挂在 provider 上，
    而任务挂在 `required_authorizations` 上 —— 于是「音轨只对 av_alignment 有意义」
    这件事在清单里表达不出来。后果有两个方向，都不响：

      * 一个只跑静图的部署，清单里也挂着 `audio_track` —— **审计读到的出境面比实际大**；
      * 实现方偷懒不登记音轨 —— **也没有东西会红**。

    这就是 `AGENTS.md` §2.4 那个病（写进文档的约束必须有执行点）长在审计件上。
    """

    item_id: str
    description: str
    data_class: str = "internal"
    tasks: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "item_id", _require_text(self.item_id, "egress_items[].item_id")
        )
        object.__setattr__(
            self,
            "description",
            _require_text(self.description, "egress_items[].description"),
        )
        data_class = _require_text(self.data_class, "egress_items[].data_class")
        data_class = data_class.strip().lower()
        if data_class not in DATA_CLASSES:
            raise ValueError(
                "egress_items[].data_class 必须是 %s 之一，收到 %r"
                % (", ".join(sorted(DATA_CLASSES)), data_class)
            )
        object.__setattr__(self, "data_class", data_class)
        object.__setattr__(
            self, "tasks", _normalize_task_names(self.tasks, "egress_items[].tasks")
        )

    def applies_to(self, task: Union["MultimodalTask", str]) -> bool:
        """这一项对某个任务是否出境。空 `tasks` = 全部任务。"""
        if not self.tasks:
            return True
        value = task.value if isinstance(task, MultimodalTask) else str(task)
        return value in self.tasks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "data_class": self.data_class,
            # ★ 显式写出来，不省略。省略会让读者分不清
            #   「适用于全部任务」与「这个字段还没人填」——两者长得一样。
            "tasks": list(self.tasks),
            "applies_to_all_tasks": not self.tasks,
        }


@dataclass(frozen=True)
class ProviderRegistration:
    """一条 provider 登记 = 五件套，缺一件都注册不了。

    1. `provider_id`              —— 谁
    2. `egress_items`             —— 送出去什么（逐项描述 + 数据分级）
    3. `recipient`                —— 送给谁（必须是可指认的接收方，不是「云端」）
    4. `required_authorizations`  —— 每个任务需要哪些授权项
    5. `authorized`               —— 每个任务当前是否已授权（逐任务 True/False；
                                     也可以用一个显式 bool 应用到全部任务）

    ★ `authorized` **没有默认值**，逐任务 mapping 的键集合必须与
      `required_authorizations` 完全相等。
      原因：如果允许缺省，那么「漏配一个任务」会变成「该任务默认放行」；
      而漏配恰恰是最常见的状态。缺键必须报错，不能猜。

    ★ `frozen=True` 只冻结字段重绑定，不冻结两个 dict 的内容。构造时已复制成
      新 dict；登记后请把它们视为只读。真正的执行点是 `require_authorization()`，
      不是 dataclass 的 frozen 装饰器。
    """

    provider_id: str
    egress_items: Tuple[EgressItem, ...]
    recipient: str
    required_authorizations: Mapping[str, Tuple[str, ...]]
    authorized: Mapping[str, bool]
    granted_authorizations: Tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        provider_id = _require_text(self.provider_id, "provider_id")
        recipient = _require_text(self.recipient, "recipient")

        if isinstance(self.egress_items, (str, bytes, Mapping)):
            raise ValueError(
                "egress_items 必须是 EgressItem/映射 的序列，不能是单个字符串或单个映射"
            )
        items = tuple(self.egress_items)
        if not items:
            raise ValueError(
                "egress_items 不能为空：本层登记的是会出境的 provider；"
                "如果确实不出境，请走本地路径，不要在这里写一个空的五件套"
            )
        seen_items = set()
        normalized_items: List[EgressItem] = []
        for item in items:
            if isinstance(item, Mapping):
                # 允许用 dict 写登记项，但 item_id/description 必须显式给出；
                # 不从裸字符串猜描述，也不替调用方填 data_class。
                try:
                    item = EgressItem(**dict(item))
                except TypeError as exc:
                    raise ValueError(
                        "egress_items 的映射项字段不合法（需要 item_id/description，"
                        "可选 data_class）：%s" % exc
                    )
            if not isinstance(item, EgressItem):
                raise ValueError(
                    "egress_items 的每一项都必须是 EgressItem 或包含 "
                    "item_id/description 的映射，收到 %r" % (type(item).__name__,)
                )
            if item.item_id in seen_items:
                raise ValueError("egress_items 重复 item_id %r" % item.item_id)
            seen_items.add(item.item_id)
            normalized_items.append(item)
        items = tuple(normalized_items)

        required = _normalize_required_map(self.required_authorizations)
        authorized = _normalize_authorized_map(self.authorized, tuple(required))
        if set(required) != set(authorized):
            missing = sorted(set(required) - set(authorized))
            extra = sorted(set(authorized) - set(required))
            raise ValueError(
                "authorized 的键必须与 required_authorizations 完全一致；"
                "缺少=%s，多出=%s。缺键不许默认成已授权。" % (missing, extra)
            )

        granted = _normalize_scopes(
            self.granted_authorizations, "granted_authorizations"
        )
        granted_set = set(granted)
        for task, scopes in required.items():
            if authorized[task]:
                absent = [scope for scope in scopes if scope not in granted_set]
                if absent:
                    raise ValueError(
                        "authorized[%s]=True，但 granted_authorizations 里缺少 %s；"
                        "『已授权』不能是一句声明，必须有对应的授权项" % (task, absent)
                    )

        if not isinstance(self.note, str):
            raise ValueError("note 必须是字符串")

        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "recipient", recipient)
        object.__setattr__(self, "egress_items", items)
        object.__setattr__(self, "required_authorizations", required)
        object.__setattr__(self, "authorized", authorized)
        object.__setattr__(self, "granted_authorizations", granted)

    @property
    def supported_tasks(self) -> Tuple[MultimodalTask, ...]:
        return tuple(MultimodalTask(task) for task in self.required_authorizations)

    @property
    def authorized_tasks(self) -> Tuple[MultimodalTask, ...]:
        return tuple(
            MultimodalTask(task)
            for task in self.required_authorizations
            if self.authorized.get(task) is True
        )

    @property
    def unauthorized_tasks(self) -> Tuple[MultimodalTask, ...]:
        return tuple(
            MultimodalTask(task)
            for task in self.required_authorizations
            if self.authorized.get(task) is not True
        )

    def egress_items_for(
        self, task: Union[MultimodalTask, str, None]
    ) -> Tuple[EgressItem, ...]:
        """某个任务会出境的项；`task=None` 返回全部。

        ★ 「按任务收窄」是这个方法的全部意义：只跑静图的部署，
          `av_alignment` 专用的 `audio_track` **不该出现在它的清单里**。
          否则审计读到的出境面比实际大（§2.4：不该报的报了）。
        """
        if task is None:
            return self.egress_items
        return tuple(item for item in self.egress_items if item.applies_to(task))

    def to_manifest_entry(
        self, task: Union[MultimodalTask, str, None] = None
    ) -> Dict[str, Any]:
        """一条「若启用，会送出什么」的机器可读记录。

        传 `task` 时，`egress_items` / `data_classes` 只算与**那个任务**相关的项；
        不传时返回全貌（旧行为）。两种口径并存是刻意的：
        审计要全貌，单次调用要「这一次到底会送什么」。
        """
        items = tuple(sorted(self.egress_items_for(task), key=lambda i: i.item_id))
        return {
            "provider_id": self.provider_id,
            # 按 item_id 排序，让同一套出境项换个书写顺序也得到同一份清单指纹。
            "egress_items": [item.to_dict() for item in items],
            "data_classes": sorted({item.data_class for item in items}),
            # ★ 这个字段回答「这条清单是按任务收窄过的吗」。
            #   省略它的话，一份全貌清单和一份收窄后恰好只剩一项的清单长得一样。
            "scoped_to_task": (
                None if task is None
                else (task.value if isinstance(task, MultimodalTask) else str(task))
            ),
            "recipient": self.recipient,
            "required_authorizations": {
                task_name: list(scopes)
                for task_name, scopes in self.required_authorizations.items()
            },
            "authorized": dict(self.authorized),
            "authorized_tasks": [t.value for t in self.authorized_tasks],
            "unauthorized_tasks": [t.value for t in self.unauthorized_tasks],
            "would_egress": bool(self.authorized_tasks),
            "granted_authorizations": list(self.granted_authorizations),
            "note": self.note,
        }


# ══════════════════════════════════════════════════════════════════════════
# ⑥ 政策边界与结果底座
# ══════════════════════════════════════════════════════════════════════════

def _policy_boundary(
    actual_egress_status: str = STATUS_UNTESTED, reason: Optional[str] = None
) -> Dict[str, Any]:
    if actual_egress_status not in ("none", STATUS_UNTESTED):
        raise ValueError("actual_egress_status 只能是 'none' 或 'untested'")
    if reason is None:
        if actual_egress_status == "none":
            reason = (
                "本次没有调用任何 provider（或调用前就被拒），因此本层可以断言"
                "『本层没有发起出境』；但这也意味着分析没有发生。"
            )
        else:
            reason = (
                "本次调用过 provider，但本层零网络，无法观测 provider 实际发了什么、"
                "发给了谁。actual_egress_status=untested 是对这条边界的明确承认，"
                "不是通过。"
            )
    return {
        "network_observed": False,
        "actual_egress_status": actual_egress_status,
        "enforcement": ["authorization_gate", "provider_contract"],
        "not_enforced": [
            "network_destination",
            "payload_after_provider_call",
            "provider_side_caching_or_resale",
        ],
        "reason": reason,
    }


def _semantics() -> str:
    return (
        "status=ok 只表示多模态分析已执行并返回了可读结果，不表示内容合规通过；"
        "合规结论必须由 judge 层给出。status=untested 表示没有执行或没有拿到"
        "可判读的结果，不能当成『没发现问题』。"
    )


def _task_descriptions(tasks: Sequence[MultimodalTask]) -> Dict[str, str]:
    return {task.value: TASK_DESCRIPTIONS[task.value] for task in tasks}


def _base_result(
    *,
    status: str,
    reason: str,
    reason_code: str,
    provider_id: Optional[str],
    requested: Sequence[MultimodalTask],
    media: Dict[str, Any],
    registration: Optional[ProviderRegistration] = None,
    results: Optional[Dict[str, Any]] = None,
    unsupported: Sequence[MultimodalTask] = (),
    authorizations_used: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    actual_egress_status: str = "none",
    boundary_reason: Optional[str] = None,
    provider_self_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if status not in _ALL_STATUSES:
        raise ValueError("内部错误：未知结果状态 %r" % (status,))
    per_task = results
    if per_task is None:
        per_task = {
            task.value: {
                "status": STATUS_UNTESTED,
                "observations": [],
                "reason": reason,
            }
            for task in requested
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "provider_id": provider_id,
        "provider_self_report": provider_self_report or {},
        "tasks": [task.value for task in requested],
        "task_descriptions": _task_descriptions(requested),
        "results": per_task,
        "unsupported_tasks": [task.value for task in unsupported],
        "egress_declared": (
            [item.to_dict() for item in registration.egress_items]
            if registration is not None
            else []
        ),
        "recipient": registration.recipient if registration is not None else None,
        "authorizations_used": authorizations_used or {},
        "media": media,
        "policy_boundary": _policy_boundary(
            actual_egress_status, boundary_reason
        ),
        "semantics": _semantics(),
        "warnings": warnings or [],
    }


def _untested_result(
    *,
    reason: str,
    reason_code: str,
    provider_id: Optional[str],
    requested: Sequence[MultimodalTask],
    media: Dict[str, Any],
    registration: Optional[ProviderRegistration] = None,
    unsupported: Sequence[MultimodalTask] = (),
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _base_result(
        status=STATUS_UNTESTED,
        reason=reason,
        reason_code=reason_code,
        provider_id=provider_id,
        requested=requested,
        media=media,
        registration=registration,
        unsupported=unsupported,
        warnings=warnings,
        actual_egress_status="none",
    )


# ══════════════════════════════════════════════════════════════════════════
# ⑦ provider 返回值的归一化：只接受可审计的结构
# ══════════════════════════════════════════════════════════════════════════

def _worst_status(*statuses: str) -> str:
    if not statuses:
        # 没有任务状态时绝不能返回 ok —— 那等于「什么都没做，但我宣布通过」。
        return STATUS_UNTESTED
    return max(statuses, key=lambda item: _STATUS_ORDER.get(item, 99))


def _observations_are_jsonable(value: Any) -> bool:
    # 结果要能进审计日志/状态文件。原始字节（b"...")或自定义对象既不可复核，
    # 也可能把媒体内容带进日志；宁可降级为 untested，也不让它们流出去。
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        return True
    except (TypeError, ValueError):
        return False


def _normalize_task_report(
    raw: Any, task: MultimodalTask, warnings: List[str]
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        warnings.append(
            "任务 %s 的结果不是映射（收到 %r），按 invalid_response 处理。"
            % (task.value, type(raw).__name__)
        )
        return {
            "status": STATUS_INVALID_RESPONSE,
            "observations": [],
            "reason": (
                "任务 %s 的结果不是映射（收到 %r）；本层不能从中读出可判读结论。"
                % (task.value, type(raw).__name__)
            ),
        }

    status = raw.get("status")
    if status not in _PROVIDER_STATUSES:
        warnings.append(
            "任务 %s 的 status=%r 非法，按 invalid_response 处理。"
            % (task.value, status)
        )
        return {
            "status": STATUS_INVALID_RESPONSE,
            "observations": [],
            "reason": (
                "任务 %s 的 status=%r 不在允许集合 %s 内；拒绝把它当成通过。"
                % (task.value, status, ", ".join(_PROVIDER_STATUSES))
            ),
        }

    observations_raw = raw.get("observations")
    if status == STATUS_OK and not isinstance(observations_raw, list):
        # 「ok 但没有 observations」是最危险的一种返回：它看起来成功，
        # 却没有任何可复核的观察。按未测处理，而不是按通过。
        warnings.append(
            "任务 %s 声称 ok 但没有 observations 列表，已降级为 untested。"
            % task.value
        )
        return {
            "status": STATUS_UNTESTED,
            "observations": [],
            "reason": (
                "任务 %s 声称 ok，但没有 observations 列表；"
                "没有可复核观察的 ok 不能当通过。" % task.value
            ),
        }

    if isinstance(observations_raw, list):
        if not _observations_are_jsonable(observations_raw):
            if status == STATUS_OK:
                warnings.append(
                    "任务 %s 的 observations 不可 JSON 序列化，已降级为 untested；"
                    "本层不接受可能含原始字节/自定义对象的结果。" % task.value
                )
                return {
                    "status": STATUS_UNTESTED,
                    "observations": [],
                    "reason": (
                        "任务 %s 的 observations 不可 JSON 序列化（可能含原始字节"
                        "或自定义对象）；本层不能把它当成可复核结论。" % task.value
                    ),
                }
            warnings.append(
                "任务 %s 的 observations 不可 JSON 序列化，已丢弃。" % task.value
            )
            observations = []
        else:
            observations = list(observations_raw)
    else:
        observations = []

    reason_raw = raw.get("reason")
    reason = reason_raw if isinstance(reason_raw, str) else ""
    if status != STATUS_OK and not reason.strip():
        reason = "provider 未说明任务 %s 处于 %s 的原因" % (task.value, status)

    out: Dict[str, Any] = {
        "status": status,
        "observations": observations,
        "reason": reason,
    }
    for key in ("model", "boundary", "confidence"):
        if key in raw:
            out[key] = raw[key]
    return out


def _normalize_provider_report(
    raw: Any,
    registration: ProviderRegistration,
    requested: Sequence[MultimodalTask],
    executed: Sequence[MultimodalTask],
    unsupported: Sequence[MultimodalTask],
    media: Dict[str, Any],
) -> Dict[str, Any]:
    warnings: List[str] = []
    actual_egress_status = STATUS_UNTESTED

    if not isinstance(raw, Mapping):
        return _base_result(
            status=STATUS_INVALID_RESPONSE,
            reason=(
                "provider %r 返回了 %r，不是 dict；本层拒绝把非结构化返回当成分析结果。"
                % (registration.provider_id, type(raw).__name__)
            ),
            reason_code="provider_return_not_mapping",
            provider_id=registration.provider_id,
            requested=requested,
            media=media,
            registration=registration,
            unsupported=unsupported,
            warnings=warnings,
            actual_egress_status=actual_egress_status,
        )

    # provider 自报的授权/出境字段一律不采信。权威来源只有登记表与 manifest。
    self_claimed = [
        key
        for key in ("authorized", "authorization", "egress", "egress_items", "recipient")
        if key in raw
    ]
    if self_claimed:
        warnings.append(
            "provider 报告里出现自报字段 %s，已忽略；授权与出境清单只采信"
            " ProviderRegistration 与 egress_manifest()。" % ", ".join(self_claimed)
        )

    raw_tasks = raw.get("tasks")
    if not isinstance(raw_tasks, Mapping):
        return _base_result(
            status=STATUS_INVALID_RESPONSE,
            reason=(
                "provider %r 的返回缺少可读的 tasks 映射；本层无法判断任何任务，"
                "不能把『没读到』当成通过。" % registration.provider_id
            ),
            reason_code="provider_tasks_missing",
            provider_id=registration.provider_id,
            requested=requested,
            media=media,
            registration=registration,
            unsupported=unsupported,
            warnings=warnings,
            actual_egress_status=actual_egress_status,
        )

    requested_values = {task.value for task in requested}
    extra_tasks: List[str] = []
    for key in raw_tasks.keys():
        # provider 可能拿 MultimodalTask 枚举当键；`str(枚举)` 在 Python 3.9
        # 会得到 "MultimodalTask.SCENE_SEMANTICS"，直接比较会把请求过的任务
        # 误报成「未请求」。所以先归一成值，再判断。
        try:
            key_value = _coerce_task(key).value
        except ValueError:
            key_value = str(key)
        if key_value not in requested_values:
            extra_tasks.append(key_value)
    extra_tasks.sort()
    if extra_tasks:
        # 未请求却返回的任务不参与结论；否则 provider 可以靠「多送一个任务」
        # 影响调用方对覆盖面的判断。
        warnings.append(
            "provider 返回了未请求的任务 %s；本层不采纳。" % ", ".join(extra_tasks)
        )

    results: Dict[str, Any] = {}
    task_statuses: List[str] = []
    for task in requested:
        if task in unsupported:
            results[task.value] = {
                "status": STATUS_UNTESTED,
                "observations": [],
                "reason": (
                    "provider %r 没有为任务 %s 登记授权项，本次没有执行该任务。"
                    % (registration.provider_id, task.value)
                ),
            }
            task_statuses.append(STATUS_UNTESTED)
            continue
        if task.value not in raw_tasks:
            results[task.value] = {
                "status": STATUS_UNTESTED,
                "observations": [],
                "reason": (
                    "provider 没有返回任务 %s 的结果；缺失不等于通过。" % task.value
                ),
            }
            task_statuses.append(STATUS_UNTESTED)
            continue
        normalized = _normalize_task_report(raw_tasks[task.value], task, warnings)
        results[task.value] = normalized
        task_statuses.append(normalized["status"])

    declared_status = raw.get("status")
    declared_for_aggregate: Optional[str]
    if declared_status is None:
        declared_for_aggregate = None
    elif declared_status in _PROVIDER_STATUSES:
        declared_for_aggregate = declared_status
    else:
        warnings.append(
            "provider 顶层 status=%r 不在允许集合内，按 invalid_response 处理。"
            % (declared_status,)
        )
        declared_for_aggregate = STATUS_INVALID_RESPONSE

    aggregate_inputs = list(task_statuses)
    if declared_for_aggregate is not None:
        aggregate_inputs.append(declared_for_aggregate)
    overall = _worst_status(*aggregate_inputs)

    if overall == STATUS_OK:
        reason = (
            "已执行：provider %r 对请求的任务返回了可读结果。"
            "注意 status=ok 只表示分析已执行，不表示内容合规通过。"
            % registration.provider_id
        )
        reason_code = "executed"
    elif overall == STATUS_UNTESTED:
        reason = (
            "未测：至少一个请求任务没有拿到可判读结果，整体不能算已覆盖；"
            "未测不是通过。"
        )
        reason_code = "partially_untested"
    elif overall == STATUS_ERROR:
        reason = (
            "错误：provider %r 报告了执行错误；这不是通过，也不是未测。"
            % registration.provider_id
        )
        reason_code = "provider_reported_error"
    else:
        reason = (
            "无效返回：provider %r 的返回结构不符合契约；本层拒绝把它当成通过。"
            % registration.provider_id
        )
        reason_code = "invalid_provider_response"

    provider_reason = raw.get("reason")
    if overall != STATUS_OK and isinstance(provider_reason, str) and provider_reason.strip():
        reason = "%s provider 自述：%s" % (reason, provider_reason)

    authorizations_used = {
        task.value: list(registration.required_authorizations[task.value])
        for task in executed
    }

    return _base_result(
        status=overall,
        reason=reason,
        reason_code=reason_code,
        provider_id=registration.provider_id,
        requested=requested,
        media=media,
        registration=registration,
        results=results,
        unsupported=unsupported,
        authorizations_used=authorizations_used,
        warnings=warnings,
        actual_egress_status=actual_egress_status,
        provider_self_report={
            "model": raw.get("model"),
            "boundary": raw.get("boundary"),
            "declared_status": declared_status,
        },
    )


def _manifest_digest(manifest: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        list(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def manifest_report_is_current(report: Any) -> bool:
    """一份**已落盘的**出境清单报告，还能不能和本层当前的算法比。

    存在的理由（`AGENTS.md` §2.4.1 第 5 行）：**一个会过期的读数，
    如果没有东西在它过期时变红，它就会一直被当成有效。**

    v1 → v2 时 `EgressItem` 加了 `tasks`、清单改成按任务展开 —— **digest 的输入集合变了**。
    于是同一个出境面在 v1 和 v2 下会算出**两个不同的值**。这不是 bug，
    但如果一份 v1 的报告被拿来和 v2 的当前值比，会得出「出境面变了」这个**假结论**；
    反过来，如果只比 digest 而不看版本，一份**早已过期**的报告也可能碰巧相等。

    所以判据是**两条一起**：

      1. `schema_version` 必须**等于**当前 `SCHEMA_VERSION`；
      2. 报告里必须同时有 `providers` 与 `digest_sha256`，且两者**自洽**
         （digest 必须能从它自己那份 providers 算出来）。

    第 2 条防的是「版本号对了，但内容是半截的」—— 那种报告比过期更危险，
    因为它通过了第一道门。

    ★ 任何一条不满足都返回 `False`（不可比），**不返回 None、不抛异常**：
      调用方需要的是一个能直接进 if 的判据，而不是三种情况的组合。
    """
    if not isinstance(report, Mapping):
        return False
    if report.get("schema_version") != SCHEMA_VERSION:
        return False
    providers = report.get("providers")
    digest = report.get("digest_sha256")
    if not isinstance(providers, list) or not isinstance(digest, str):
        return False
    # 自洽：digest 必须能由这份 providers 重算出来。
    # 只比 digest 不看内容，等于信任一份没人复核过的读数。
    try:
        return _manifest_digest(providers) == digest
    except (TypeError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════════════════
# ⑧ 注册表
# ══════════════════════════════════════════════════════════════════════════

class ProviderRegistry:
    """provider 注册表 + 授权闸门 + 出境清单。

    默认实例 `DEFAULT_REGISTRY` 给模块级便捷函数用；测试/多租户场景请自己
    `ProviderRegistry()`，避免共享可变状态把用例串在一起。

    ★ 注册表不加锁：provider 应在启动时注册完，请求路径上只读。
      如果确实要在运行时增删，请在外面加锁，并接受「清单与调用之间可能
      存在一个很短的窗口」——本层不假装自己解决了并发注册问题。
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Tuple[ProviderRegistration, Any]] = {}

    # ------------------------------------------------------------------
    # 注册 / 查询
    # ------------------------------------------------------------------

    def register(
        self, registration: ProviderRegistration, provider: Any
    ) -> ProviderRegistration:
        if not isinstance(registration, ProviderRegistration):
            raise TypeError(
                "registration 必须是 ProviderRegistration（五件套），收到 %r"
                % (type(registration).__name__,)
            )
        provider_id = registration.provider_id
        if provider_id in self._providers:
            raise ValueError(
                "provider_id %r 已注册；重复注册会让 egress_manifest 出现两套声明，"
                "而调用只会命中其中一套。" % provider_id
            )
        analyze = getattr(provider, "analyze", None)
        if not callable(analyze):
            raise TypeError(
                "provider %r 没有可调用的 analyze(media_ref, tasks)；"
                "本层不接受空壳。" % provider_id
            )
        declared_id = getattr(provider, "provider_id", None)
        if declared_id is not None and declared_id != provider_id:
            raise ValueError(
                "provider.provider_id=%r 与登记表 provider_id=%r 不一致；"
                "不一致时审计看到的名字和实际被调用的对象对不上。"
                % (declared_id, provider_id)
            )
        self._providers[provider_id] = (registration, provider)
        return registration

    def unregister(self, provider_id: str) -> bool:
        return self._providers.pop(provider_id, None) is not None

    def clear(self) -> None:
        self._providers.clear()

    def provider_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._providers))

    def registrations(self) -> Tuple[ProviderRegistration, ...]:
        return tuple(
            registration
            for _, (registration, _provider) in sorted(self._providers.items())
        )

    def registration(self, provider_id: str) -> ProviderRegistration:
        entry = self._providers.get(provider_id)
        if entry is None:
            raise NotConfigured(
                "未配置：provider %r 未注册。已注册：%s。"
                "空注册表时 analyze() 返回 untested，而不是通过。"
                % (provider_id, ", ".join(self.provider_ids()) or "(无)")
            )
        return entry[0]

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, provider_id: object) -> bool:
        return provider_id in self._providers

    # ------------------------------------------------------------------
    # 出境清单
    # ------------------------------------------------------------------

    def egress_manifest(
        self, task: Union[MultimodalTask, str, None] = None
    ) -> List[Dict[str, Any]]:
        """返回「若启用，会送出什么」的机器可读清单（按 provider_id 排序）。

        `task` 为 None 时是全貌（旧行为）；传了就按任务收窄 —— 每一项只算
        `applies_to(task)` 的出境项。**只跑静图的部署因此不会在清单里看到音轨。**
        """
        return [
            registration.to_manifest_entry(task)
            for registration in self.registrations()
        ]

    def egress_manifest_digest(
        self, task: Union[MultimodalTask, str, None] = None
    ) -> str:
        """清单的稳定指纹；用于发现「出境面悄悄变了」。"""
        return _manifest_digest(self.egress_manifest(task))

    def egress_manifest_report(self) -> Dict[str, Any]:
        """清单 + 本层边界 + 指纹。审计落地时建议整份存档。"""
        # ★ 清单只取一次，摘要也从同一份内存对象算。
        # 如果这里分别调两次，中间有并发注册/注销，报告就会出现
        # 「providers 是新清单、digest 是旧清单」的错位 —— 一份自相矛盾的审计件。
        manifest = self.egress_manifest()
        return {
            "schema_version": SCHEMA_VERSION,
            "provider_count": len(manifest),
            "providers": manifest,
            "digest_sha256": _manifest_digest(manifest),
            "policy_boundary": _policy_boundary(
                "none",
                "生成出境清单本身不调用任何 provider、不触网；"
                "它描述的是『若启用会送出什么』，不是『已经送出了什么』。",
            ),
        }

    # ------------------------------------------------------------------
    # 授权闸门
    # ------------------------------------------------------------------

    def require_authorization(
        self, provider_id: str, task: Union[MultimodalTask, str]
    ) -> ProviderRegistration:
        """逐任务检查授权；不齐就抛 `NotAuthorized` 并点名缺哪一项。

        返回登记项本身，方便调用方紧接着读取 `recipient` / `egress_items`
        并把它们写进本次调用的审计记录。
        """
        task_obj = _coerce_task(task)
        registration = self.registration(provider_id)

        if task_obj.value not in registration.required_authorizations:
            raise NotConfigured(
                "未配置：provider %r 没有为任务 %r 登记授权项；已登记任务：%s。"
                "未声明的任务不能临时借用别的任务的授权。"
                % (
                    provider_id,
                    task_obj.value,
                    ", ".join(
                        supported.value for supported in registration.supported_tasks
                    )
                    or "(无)",
                ),
                provider_id=provider_id,
                task=task_obj,
            )

        required = registration.required_authorizations[task_obj.value]
        if registration.authorized.get(task_obj.value) is not True:
            raise NotAuthorized(provider_id, task_obj, required)

        # 纵深防御：注册时已经校验过 authorized=True => scopes 齐全；
        # 这里再查一次，防止有人绕过 dataclass 直接改了内部 dict。
        missing = tuple(
            scope
            for scope in required
            if scope not in set(registration.granted_authorizations)
        )
        if missing:
            raise NotAuthorized(
                provider_id,
                task_obj,
                missing,
                message=(
                    "未授权：provider %r 的任务 %r 标记为已授权，但实际授权项缺少 %s；"
                    "本层按未授权处理，不调用 provider。"
                    % (provider_id, task_obj.value, ", ".join(missing))
                ),
            )
        return registration

    # ------------------------------------------------------------------
    # 分析入口
    # ------------------------------------------------------------------

    def analyze(
        self,
        media_ref: Any,
        tasks: Any,
        provider_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """调用指定 provider 分析 media_ref；**调用前先过授权闸门**。

        返回值永远是 dict，且 `status` 明确区分：
          * `ok`              —— 分析执行且返回可读结果（**不是内容合规通过**）；
          * `untested`        —— 没执行/没拿到可判读结果；
          * `error`           —— provider 调用失败或自报错误；
          * `invalid_response`—— provider 返回结构坏了。

        未授权时抛 `NotAuthorized`，**不会**先调用 provider 再报告 ——
        本层的顺序是「先授权，后出境」，不是「先出境，后补记录」。
        """
        requested = normalize_tasks(tasks)
        media = _describe_media_ref(media_ref)

        if not requested:
            return _untested_result(
                reason=(
                    "未测：tasks 为空，没有任何多模态任务被执行；"
                    "空任务不等于通过。"
                ),
                reason_code="no_tasks",
                provider_id=provider_id,
                requested=requested,
                media=media,
            )

        provider_ids = self.provider_ids()
        if not provider_ids:
            # 这是本文件最重要的默认行为：没有 provider 时返回 untested。
            # 不返回 []、不返回 None、不返回 True，也不抛异常 ——
            # 因为「还没接能力」不是一个错误，而是一个必须被看见的未测状态。
            return _untested_result(
                reason=(
                    "未测：当前没有注册任何多模态 provider。本层不发起网络调用，"
                    "也不会用空列表、None 或『无发现』冒充『已分析且没问题』。"
                    "要消除未测，必须注册 provider、声明出境项与接收方，并完成授权。"
                ),
                reason_code="no_provider_registered",
                provider_id=provider_id,
                requested=requested,
                media=media,
            )

        if provider_id is None:
            if len(provider_ids) > 1:
                raise NotConfigured(
                    "未配置：已注册多个 provider（%s），必须显式指定 provider_id。"
                    "本层不替调用方选一个把数据送出去。"
                    % ", ".join(provider_ids)
                )
            # 只有一个 provider 时目标无歧义；仍然会过授权闸门。
            provider_id = provider_ids[0]

        if provider_id not in self._providers:
            raise NotConfigured(
                "未配置：provider %r 未注册。已注册：%s。"
                % (provider_id, ", ".join(provider_ids)),
                provider_id=provider_id,
            )

        registration, provider = self._providers[provider_id]
        supported_set = set(registration.supported_tasks)
        executed = tuple(task for task in requested if task in supported_set)
        unsupported = tuple(task for task in requested if task not in supported_set)

        if not executed:
            return _untested_result(
                reason=(
                    "未测：provider %r 只为任务 %s 登记了授权，而本次请求的任务 %s "
                    "全不在其中；本层没有调用 provider。"
                    % (
                        provider_id,
                        ", ".join(task.value for task in registration.supported_tasks)
                        or "(无)",
                        ", ".join(task.value for task in requested),
                    )
                ),
                reason_code="tasks_not_supported",
                provider_id=provider_id,
                requested=requested,
                media=media,
                registration=registration,
                unsupported=unsupported,
            )

        # ★ 调用前的授权闸门：任何一个要执行的任务未授权，整次调用都不发。
        # 不做「先跑已授权的部分」—— 部分执行会让调用方误以为全部任务都看过了。
        for task in executed:
            self.require_authorization(provider_id, task)

        # ★ 调用前的介质闸门：任务要的介质，这个引用有没有。
        # ★ 顺序是刻意的：**授权在前、介质在后**。两者都不满足时先报授权 ——
        #   因为「缺介质」会让调用方以为补上 kind 就能跑，而真正的墙是没授权。
        #   报一个更靠外的阻塞，比报一个更靠内的更接近真相。
        # ★ 缺音轨时**一次都不发**，不做「先用画面凑合分析一下」：
        #   降级分析正是要消灭的失败模式 —— 它不报错，只是安静地少看一路。
        lacking = {
            task: _missing_media(task, media)
            for task in executed
            if _missing_media(task, media)
        }
        if lacking:
            return _untested_result(
                reason=(
                    "未测：本次请求的任务缺少必需介质，本层没有调用 provider。缺什么：%s。"
                    "`kind`/`mime` 都没声明时按「全都缺」处理 —— "
                    "没说是图片不等于它是图片。"
                    % ("；".join(
                        "任务 %s 缺 %s" % (task.value, "、".join(missing))
                        for task, missing in lacking.items()
                    ))
                ),
                reason_code="media_insufficient",
                provider_id=provider_id,
                requested=requested,
                media=media,
                registration=registration,
                unsupported=unsupported,
            )


        try:
            raw_report = provider.analyze(media_ref, executed)
        except Exception as exc:  # noqa: BLE001 - 实现方异常必须落成结构化错误
            # 不捕获 BaseException：KeyboardInterrupt/SystemExit 应该照常打断。
            # 这里也不能报「通过」：调用已经发生，但结果没拿到。
            return _base_result(
                status=STATUS_ERROR,
                reason=(
                    "错误：provider %r 调用失败（%s: %s）；"
                    "这不是通过，也不是未测。"
                    % (provider_id, type(exc).__name__, exc)
                ),
                reason_code="provider_exception",
                provider_id=provider_id,
                requested=requested,
                media=media,
                registration=registration,
                unsupported=unsupported,
                warnings=[
                    "provider 抛出异常时可能已经发出了部分数据；"
                    "本层零网络，无法判断实际出境范围。"
                ],
                actual_egress_status=STATUS_UNTESTED,
            )

        return _normalize_provider_report(
            raw_report,
            registration,
            requested,
            executed,
            unsupported,
            media,
        )


# ══════════════════════════════════════════════════════════════════════════
# ⑨ 模块级便捷入口（默认注册表）
# ══════════════════════════════════════════════════════════════════════════

DEFAULT_REGISTRY = ProviderRegistry()


def register_provider(
    registration: ProviderRegistration, provider: Any
) -> ProviderRegistration:
    """把一条五件套登记项与实现对象注册进默认注册表。"""
    return DEFAULT_REGISTRY.register(registration, provider)


def unregister_provider(provider_id: str) -> bool:
    """移除默认注册表里的一个 provider；返回是否真的移除了。"""
    return DEFAULT_REGISTRY.unregister(provider_id)


def clear_providers() -> None:
    """清空默认注册表。测试用；生产环境清空等于让所有分析回到 untested。"""
    DEFAULT_REGISTRY.clear()


def egress_manifest() -> List[Dict[str, Any]]:
    """默认注册表的「若启用，会送出什么」清单。"""
    return DEFAULT_REGISTRY.egress_manifest()


def egress_manifest_digest() -> str:
    """默认注册表出境清单的稳定 sha256 指纹。"""
    return DEFAULT_REGISTRY.egress_manifest_digest()


def egress_manifest_report() -> Dict[str, Any]:
    """默认注册表的清单 + 本层边界 + 指纹，适合整份存档审计。"""
    return DEFAULT_REGISTRY.egress_manifest_report()


def require_authorization(
    provider_id: str, task: Union[MultimodalTask, str]
) -> ProviderRegistration:
    """默认注册表的逐任务授权闸门；未授权时抛 `NotAuthorized`。"""
    return DEFAULT_REGISTRY.require_authorization(provider_id, task)


def analyze(
    media_ref: Any, tasks: Any, provider_id: Optional[str] = None
) -> Dict[str, Any]:
    """默认注册表的多模态分析入口。

    没有注册任何 provider 时返回 `status="untested"`，不是空列表、None 或通过。
    """
    return DEFAULT_REGISTRY.analyze(media_ref, tasks, provider_id)


# ══════════════════════════════════════════════════════════════════════════
# ⑩ 自证（只在本文件被直接执行时运行；不写盘、不联网）
# ══════════════════════════════════════════════════════════════════════════

def _selftest() -> None:
    checks = 0
    negative_checks = 0

    def check(condition: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError("selftest 失败：%s" % label)

    def expect_raises(exc_type, fn, label: str):
        nonlocal checks, negative_checks
        checks += 1
        negative_checks += 1
        try:
            fn()
        except exc_type as exc:
            return exc
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                "selftest 失败：%s（期望 %s，实际 %s）"
                % (label, exc_type.__name__, type(exc).__name__)
            )
        raise AssertionError("selftest 失败：%s（没有抛异常）" % label)

    # 1) 空注册表：必须是 untested，且 reason 说未测，不是 []/None/通过。
    empty_registry = ProviderRegistry()
    result = empty_registry.analyze("demo-frame-001.png", ["scene_semantics"])
    check(result["status"] == STATUS_UNTESTED, "空注册表返回 untested")
    check("未测" in result["reason"], "空注册表 reason 明说未测")
    check(result["results"]["scene_semantics"]["status"] == STATUS_UNTESTED,
          "空注册表逐任务也是 untested")
    check(result["policy_boundary"]["actual_egress_status"] == "none",
          "空注册表没有调用 provider，实出境为 none")

    # 2) 未授权：必须抛 NotAuthorized，点名缺哪一项，且 provider 一次都没被调用。
    class FakeProvider(MultimodalProvider):
        provider_id = "fake.local"

        def __init__(self) -> None:
            self.calls = 0
            self.report: Any = None

        def analyze(self, media_ref, tasks):
            self.calls += 1
            if self.report is not None:
                return self.report
            return {
                "status": STATUS_OK,
                "tasks": {
                    task.value: {
                        "status": STATUS_OK,
                        "observations": [{"task": task.value, "note": "selftest"}],
                    }
                    for task in tasks
                },
                "model": "fake-v1",
                "boundary": "selftest only",
            }

    registration = ProviderRegistration(
        provider_id="fake.local",
        egress_items=(
            EgressItem("media.frames", "抽帧后的静态画面", "internal"),
            EgressItem("media.audio", "音频轨（可能含人声）", "pii"),
        ),
        recipient="fake-vendor.example / us-east-1",
        required_authorizations={
            "scene_semantics": ("vendor.scene.read",),
            "mark_symbol": ("vendor.mark.read",),
            "av_alignment": ("vendor.av.read", "vendor.audio.pii"),
        },
        authorized={
            "scene_semantics": False,
            "mark_symbol": False,
            "av_alignment": False,
        },
        granted_authorizations=(),
        note="selftest 登记项",
    )
    provider = FakeProvider()
    registry = ProviderRegistry()
    registry.register(registration, provider)

    exc = expect_raises(
        NotAuthorized,
        lambda: registry.require_authorization("fake.local", "scene_semantics"),
        "未授权时 require_authorization 抛 NotAuthorized",
    )
    check(exc.missing == ("vendor.scene.read",), "NotAuthorized 点名缺失的授权项")
    check(provider.calls == 0, "未授权时没有调用 provider")

    expect_raises(
        NotAuthorized,
        lambda: registry.analyze("demo-frame-001.png", ["scene_semantics"]),
        "未授权时 analyze 在调用 provider 前拒绝",
    )
    check(provider.calls == 0, "analyze 拒绝时 provider 调用次数仍为 0")

    # 3) 已授权：能执行，结果逐任务 ok，并记录本次用到的授权项。
    authorized_registration = ProviderRegistration(
        provider_id="fake.local",
        egress_items=registration.egress_items,
        recipient=registration.recipient,
        required_authorizations=registration.required_authorizations,
        authorized={
            "scene_semantics": True,
            "mark_symbol": True,
            "av_alignment": True,
        },
        granted_authorizations=(
            "vendor.scene.read",
            "vendor.mark.read",
            "vendor.av.read",
            "vendor.audio.pii",
        ),
        note="selftest 已授权登记项",
    )
    authorized_registry = ProviderRegistry()
    authorized_registry.register(authorized_registration, provider)

    # ★ 介质夹具（2026-10-21 加 `required_media` 之后引入）。
    #
    # 下面 #3–#8 这几个用例原本验的是**授权 / 归一化 / 警告**，与介质无关。
    # 加了介质闸门后，它们若仍传裸字符串，就会在闸门处提前变成 `untested`，
    # 于是「原本该 ok 的仍然 ok」这条不再成立 —— 而那是它们各自的前提。
    # 所以这些点补上 `kind="image/png"`，让它们**仍然走到原来那条路径**。
    #
    # ★ 反过来，**有 6 处刻意不补**，因为它们本来就在介质闸门之前返回：
    #   #1 空注册表 / #2 未授权 / #9 任务全不支持 / #10 多 provider 未指定
    #   / #11 未知 provider / #15 空任务。
    #   它们保持原样，等于顺带断言了「闸门顺序：这些前置判断优先于介质」。
    #   给它们补介质反而会让这条顺序断言消失。
    frame_ref = MediaRef(uri="demo-frame-001.png", kind="image/png")

    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_OK, "已授权时返回 ok")
    check(provider.calls == 1, "已授权时 provider 被调用一次")
    check(
        result["authorizations_used"] == {"scene_semantics": ["vendor.scene.read"]},
        "结果记录本次用到的授权项",
    )
    check(result["policy_boundary"]["actual_egress_status"] == STATUS_UNTESTED,
          "调用过 provider 后实出境只能是 untested")

    # 4) provider 漏返回一个任务：整体不能是 ok，缺失任务必须是 untested。
    provider.report = {
        "status": STATUS_OK,
        "tasks": {
            "scene_semantics": {
                "status": STATUS_OK,
                "observations": [{"note": "ok"}],
            }
        },
    }
    result = authorized_registry.analyze(
        frame_ref, ["scene_semantics", "mark_symbol"]
    )
    check(result["status"] == STATUS_UNTESTED, "漏任务时整体 untested")
    check(result["results"]["mark_symbol"]["status"] == STATUS_UNTESTED,
          "漏掉的任务逐项 untested")
    check(result["results"]["scene_semantics"]["status"] == STATUS_OK,
          "返回了的任务仍保留自己的 ok，不被整体 untested 抹掉")

    # 5) status=ok 但没有 observations：按未测处理，不能当通过。
    provider.report = {
        "status": STATUS_OK,
        "tasks": {"scene_semantics": {"status": STATUS_OK}},
    }
    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_UNTESTED, "ok 但无 observations 时整体 untested")
    check(result["results"]["scene_semantics"]["status"] == STATUS_UNTESTED,
          "ok 但无 observations 的逐任务状态是 untested")

    # 6) provider 返回未请求的任务：只警告，不采纳，不影响请求任务的结论。
    provider.report = {
        "status": STATUS_OK,
        "tasks": {
            "scene_semantics": {
                "status": STATUS_OK,
                "observations": [{"note": "ok"}],
            },
            "av_alignment": {
                "status": STATUS_OK,
                "observations": [{"note": "偷跑的任务"}],
            },
        },
    }
    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_OK, "未请求任务不改变请求任务的结论")
    check("av_alignment" not in result["results"], "未请求任务不进入 results")
    check(any("未请求" in warning for warning in result["warnings"]),
          "未请求任务会留下警告")

    # 6a) observations 里塞原始字节：不可序列化，必须降级，不能带出本层。
    provider.report = {
        "status": STATUS_OK,
        "tasks": {
            "scene_semantics": {
                "status": STATUS_OK,
                "observations": [b"raw-media-bytes"],
            }
        },
    }
    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_UNTESTED,
          "不可序列化的 observations 让整体 untested")
    check(result["results"]["scene_semantics"]["observations"] == [],
          "原始字节不会进入结果")

    # 6b) provider 用枚举当 tasks 的键：不能被误判成「未请求任务」。
    #     Python 3.9 的 str(枚举) 不是枚举值，这个用例就是防那条回归。
    provider.report = {
        "status": STATUS_OK,
        "tasks": {
            MultimodalTask.SCENE_SEMANTICS: {
                "status": STATUS_OK,
                "observations": [{"note": "enum key"}],
            }
        },
    }
    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_OK, "枚举键也能被正确识别")
    check(not any("未请求" in warning for warning in result["warnings"]),
          "枚举键不会被误报为未请求任务")

    # 7) provider 自报 authorized/egress：不采信，必须留警告。
    provider.report = {
        "status": STATUS_OK,
        "authorized": True,
        "egress": ["everything"],
        "tasks": {
            "scene_semantics": {
                "status": STATUS_OK,
                "observations": [{"note": "ok"}],
            }
        },
    }
    result = authorized_registry.analyze(frame_ref, ["scene_semantics"])
    check(any("自报字段" in warning for warning in result["warnings"]),
          "provider 自报授权/出境字段被忽略并留痕")

    # 8) provider 抛异常：结构化 error，不能是 ok/untested 里的「通过」。
    class BrokenProvider(MultimodalProvider):
        provider_id = "fake.local"

        def analyze(self, media_ref, tasks):
            raise RuntimeError("model endpoint unavailable")

    broken_registry = ProviderRegistry()
    broken_registry.register(authorized_registration, BrokenProvider())
    result = broken_registry.analyze(frame_ref, ["scene_semantics"])
    check(result["status"] == STATUS_ERROR, "provider 异常落成 error")
    check("model endpoint unavailable" in result["reason"], "error 保留原因")
    check(result["results"]["scene_semantics"]["status"] == STATUS_UNTESTED,
          "provider 异常时该任务没拿到结果，为 untested")

    # 9) provider 不支持请求的任务：untested，不调用 provider。
    before_calls = provider.calls
    provider.report = None
    # mark_symbol 是支持的；造一个只支持 scene_semantics 的登记项来验「全不支持」。
    scene_only = ProviderRegistration(
        provider_id="fake.local",
        egress_items=registration.egress_items,
        recipient=registration.recipient,
        required_authorizations={"scene_semantics": ("vendor.scene.read",)},
        authorized={"scene_semantics": True},
        granted_authorizations=("vendor.scene.read",),
    )
    scene_only_registry = ProviderRegistry()
    scene_only_registry.register(scene_only, provider)
    result = scene_only_registry.analyze("demo-frame-001.png", ["av_alignment"])
    check(result["status"] == STATUS_UNTESTED, "任务全不支持时 untested")
    check(provider.calls == before_calls, "任务全不支持时没有调用 provider")
    check(result["unsupported_tasks"] == ["av_alignment"], "未支持任务被列出")

    # 10) 多个 provider 且未指定：必须拒绝，不能替调用方选一个把数据送出去。
    second = ProviderRegistration(
        provider_id="fake.second",
        egress_items=(EgressItem("media.frames", "抽帧画面", "internal"),),
        recipient="second-vendor.example",
        required_authorizations={"scene_semantics": ("vendor.scene.read",)},
        authorized={"scene_semantics": True},
        granted_authorizations=("vendor.scene.read",),
    )
    class SecondProvider(MultimodalProvider):
        provider_id = "fake.second"

        def analyze(self, media_ref, tasks):
            raise AssertionError("不应被调用")

    multi = ProviderRegistry()
    multi.register(authorized_registration, provider)
    multi.register(second, SecondProvider())
    expect_raises(
        NotConfigured,
        lambda: multi.analyze("demo-frame-001.png", ["scene_semantics"]),
        "多 provider 未指定时拒绝",
    )

    # 11) 显式点名不存在的 provider：NotConfigured。
    expect_raises(
        NotConfigured,
        lambda: authorized_registry.analyze(
            "demo-frame-001.png", ["scene_semantics"], provider_id="nope"
        ),
        "未知 provider 抛 NotConfigured",
    )

    # 12) 登记表五件套：缺 authorized 的键必须炸，不许默认放行。
    expect_raises(
        ValueError,
        lambda: ProviderRegistration(
            provider_id="bad.registration",
            egress_items=(EgressItem("media.frames", "抽帧画面", "internal"),),
            recipient="bad-vendor.example",
            required_authorizations={
                "scene_semantics": ("vendor.scene.read",),
                "mark_symbol": ("vendor.mark.read",),
            },
            authorized={"scene_semantics": True},
            granted_authorizations=("vendor.scene.read",),
        ),
        "authorized 缺键必须报错",
    )
    expect_raises(
        ValueError,
        lambda: ProviderRegistration(
            provider_id="bad.registration",
            egress_items=(EgressItem("media.frames", "抽帧画面", "internal"),),
            recipient="bad-vendor.example",
            required_authorizations={
                "scene_semantics": ("vendor.scene.read",),
                "mark_symbol": ("vendor.mark.read",),
            },
            authorized={"scene_semantics": True, "mark_symbol": False},
            granted_authorizations=(),
        ),
        "authorized=True 但授权项不齐必须报错",
    )
    expect_raises(
        ValueError,
        lambda: ProviderRegistration(
            provider_id="bad.registration",
            egress_items=(EgressItem("media.frames", "抽帧画面", "internal"),),
            recipient="bad-vendor.example",
            required_authorizations={"scene_semantics": ("vendor.scene.read",)},
            authorized={"scene_semantics": "yes"},
            granted_authorizations=("vendor.scene.read",),
        ),
        "authorized 只接受 bool，字符串 yes 必须报错",
    )

    # 13) 出境清单：五件套字段齐全、指纹稳定、清单本身不触网。
    manifest = authorized_registry.egress_manifest()
    check(len(manifest) == 1, "清单有一条 provider")
    entry = manifest[0]
    for key in (
        "provider_id",
        "egress_items",
        "recipient",
        "required_authorizations",
        "authorized",
    ):
        check(key in entry, "清单包含五件套字段 %s" % key)
    check(entry["recipient"] == registration.recipient, "清单记录接收方")
    check(entry["would_egress"] is True, "已授权任务让 would_egress 为 True")
    check(
        authorized_registry.egress_manifest_digest()
        == authorized_registry.egress_manifest_digest(),
        "同一登记表指纹稳定",
    )
    report = authorized_registry.egress_manifest_report()
    check(report["provider_count"] == 1, "清单报告带 provider 数")
    check(report["policy_boundary"]["actual_egress_status"] == "none",
          "生成清单本身不触网")

    # 14) media_ref：显式 sha256 才叫内容指纹；字符串引用只给 ref_sha256。
    media = _describe_media_ref(
        {"uri": "demo-frame-001.png", "sha256": "A" * 64}
    )
    check(media["content_sha256"] == "a" * 64, "显式 sha256 被归一为小写")
    check(media["content_sha256_status"] == "provided", "显式 sha256 标记 provided")
    media = _describe_media_ref("demo-frame-001.png")
    check(media["content_sha256"] is None, "字符串引用不冒充内容指纹")
    check(media["content_sha256_status"] == STATUS_UNTESTED,
          "没有内容指纹时明确标 untested")
    media = _describe_media_ref({"uri": "demo-frame-001.png", "sha256": "not-a-sha"})
    check(media["content_sha256_status"] == "invalid",
          "非法 sha256 标 invalid，不静默接受")

    # 15) 空任务：untested，不是通过。
    result = authorized_registry.analyze("demo-frame-001.png", [])
    check(result["status"] == STATUS_UNTESTED, "空任务返回 untested")
    check("空任务不等于通过" in result["reason"], "空任务 reason 明说")

    # ══════════════════════════════════════════════════════════════════
    # 16) 介质闸门（required_media）：模态不够时不许降级分析
    #
    # 起因是一个具体读数：`glm-5.3-flash` 27 家里 `audio` 是 0 家。
    # 拿它做 av_alignment 不会报错，只会安静地少看一路。
    # ══════════════════════════════════════════════════════════════════
    video_only = MediaRef(uri="demo-video-001.mp4", kind="video/mp4")
    before_calls = provider.calls
    provider.report = None
    result = authorized_registry.analyze(video_only, ["av_alignment"])
    check(result["status"] == STATUS_UNTESTED, "缺音轨时 av_alignment 是 untested")
    check(result["reason_code"] == "media_insufficient", "缺介质有专门的 reason_code")
    check("audio" in result["reason"], "reason 点名缺的是 audio")
    check(provider.calls == before_calls, "缺介质时一次都不调用 provider")

    # 反过来：kind 与 mime 各自单独提供，也必须能被认出来。
    # 这两个字段是独立的（实测 kind=None 而 mime='audio/mpeg' 是合法输入），
    # 只读一个会把「只填了另一个」的调用方误判成「什么都没给」。
    both = MediaRef(uri="demo-video-002.mp4", kind="video/mp4", mime="audio/mpeg")
    result = authorized_registry.analyze(both, ["av_alignment"])
    check(result["status"] == STATUS_OK, "kind+mime 齐全时 av_alignment 能执行")

    mime_only = MediaRef(uri="demo-video-003.mp4", mime="video/mp4")
    check(
        _missing_media(MultimodalTask.AV_ALIGNMENT, _describe_media_ref(mime_only))
        == ("audio",),
        "只填 mime 也能识别出 video，仍缺 audio",
    )

    # ★ 最要紧的一条：什么都没声明 → 缺全部，不是「不缺」。
    #   「没说是图片」不等于「它是图片」。
    bare = MediaRef(uri="demo-frame-002.png")
    check(
        _missing_media(MultimodalTask.SCENE_SEMANTICS, _describe_media_ref(bare))
        == ("image",),
        "kind/mime 都空时按「缺」处理，不是按「不缺」",
    )
    # ★ 基准必须在这一行之前取。上面那条 `both` 用例是**成功**调用，
    #   它已经把 calls 加过一次了；拿更早的基准比会得到一个假红。
    calls_before_bare = provider.calls
    result = authorized_registry.analyze(bare, ["scene_semantics"])
    check(result["status"] == STATUS_UNTESTED,
          "什么都没声明时不许静默当成满足")
    check(provider.calls == calls_before_bare,
          "没声明介质时也不调用 provider")

    # 闸门顺序：授权优先于介质。两者都不满足时报授权 —— 那是更靠外的阻塞。
    # 报「缺介质」会让调用方以为补上 kind 就能跑，而真正的墙是没授权。
    order_registry = ProviderRegistry()
    order_registry.register(registration, provider)      # 这个登记项三个任务全未授权
    exc = expect_raises(
        NotAuthorized,
        lambda: order_registry.analyze(video_only, ["av_alignment"]),
        "未授权且缺介质时，报的是授权而不是介质",
    )
    check(exc.missing, "顺序断言：异常里点名了缺的授权项")

    # ══════════════════════════════════════════════════════════════════
    # 17) 出境清单按任务收窄：只跑静图的部署不该在清单里看到音轨
    # ══════════════════════════════════════════════════════════════════
    scoped_registration = ProviderRegistration(
        provider_id="fake.scoped",
        egress_items=(
            EgressItem("frames", "抽帧画面", "internal"),
            EgressItem("audio_track", "视频音轨（可能含人声）", "pii",
                       tasks=("av_alignment",)),
        ),
        recipient="scoped-vendor.example",
        required_authorizations={
            "scene_semantics": ("vendor.scene.read",),
            "av_alignment": ("vendor.av.read",),
        },
        authorized={"scene_semantics": True, "av_alignment": True},
        granted_authorizations=("vendor.scene.read", "vendor.av.read"),
    )
    # ★ provider_id 必须与登记表一致 —— 注册表会拒掉不一致的（这本身是道闸门）。
    #   所以这里给收窄用例单独造一个同名 provider，而不是复用 fake.local。
    class ScopedProvider(MultimodalProvider):
        provider_id = "fake.scoped"

        def __init__(self) -> None:
            self.calls = 0

        def analyze(self, media_ref, tasks):
            self.calls += 1
            return {
                "tasks": {
                    task.value: {"status": STATUS_OK, "observations": [{"note": "scoped"}]}
                    for task in tasks
                }
            }

    scoped_provider = ScopedProvider()
    scoped_registry = ProviderRegistry()
    scoped_registry.register(scoped_registration, scoped_provider)

    scene_entry = scoped_registry.egress_manifest("scene_semantics")[0]
    ids = [item["item_id"] for item in scene_entry["egress_items"]]
    check(ids == ["frames"], "scene_semantics 的清单里没有 audio_track")
    check(not any(item["data_class"] == "pii" for item in scene_entry["egress_items"]),
          "按任务收窄后没有 pii 项")

    av_entry = scoped_registry.egress_manifest("av_alignment")[0]
    ids = [item["item_id"] for item in av_entry["egress_items"]]
    check(ids == ["audio_track", "frames"], "av_alignment 的清单里两项都在")

    full_entry = scoped_registry.egress_manifest()[0]
    check(len(full_entry["egress_items"]) == 2, "不传任务时返回全貌")
    check(full_entry["scoped_to_task"] is None, "全貌清单标明未按任务收窄")
    check(scene_entry["scoped_to_task"] == "scene_semantics",
          "收窄清单标明收窄到哪个任务")

    # 空 tasks = 适用全部任务：frames 在两边都应出现。
    frames_item = scoped_registration.egress_items[0]
    check(frames_item.applies_to("scene_semantics")
          and frames_item.applies_to("av_alignment"),
          "空 tasks 表示适用于全部任务")

    # 同一套出境项换个书写顺序，收窄后的指纹也必须相同。
    check(
        scoped_registry.egress_manifest_digest("scene_semantics")
        == scoped_registry.egress_manifest_digest("scene_semantics"),
        "按任务收窄后指纹仍然稳定",
    )

    # 18) EgressItem.tasks 的输入校验：单个字符串必须拒（会被逐字符拆开）
    expect_raises(
        ValueError,
        lambda: EgressItem("x", "d", "internal", tasks="av_alignment"),
        "tasks 传单个字符串必须拒",
    )
    expect_raises(
        ValueError,
        lambda: EgressItem("x", "d", "internal", tasks=("no_such_task",)),
        "tasks 里有未知任务必须拒",
    )
    expect_raises(
        ValueError,
        lambda: EgressItem("x", "d", "internal",
                           tasks=("scene_semantics", "scene_semantics")),
        "tasks 重复任务必须拒",
    )

    # ══════════════════════════════════════════════════════════════════
    # 19) 版本与新鲜度：旧 digest 不许被静默当成有效
    #
    # v1→v2 改了 digest 的输入集合。旧报告若被拿来比，会得出「出境面变了」
    # 这个假结论；只比 digest 不看版本，又可能碰巧相等。
    # ══════════════════════════════════════════════════════════════════
    report = scoped_registry.egress_manifest_report()
    check(report["schema_version"] == SCHEMA_VERSION, "报告带当前版本号")
    check(manifest_report_is_current(report), "当前形状的报告被判为可比")

    stale = dict(report)
    stale["schema_version"] = "multimodal-provider-v1"
    check(not manifest_report_is_current(stale),
          "v1 旧报告必须判成不可比，不许当成同一份")

    half = dict(report)
    half.pop("providers")
    check(not manifest_report_is_current(half),
          "缺 providers 的报告判成不可比（版本对也不行）")

    tampered = dict(report)
    tampered["digest_sha256"] = "0" * 64
    check(not manifest_report_is_current(tampered),
          "digest 与 providers 不自洽时判成不可比")

    check(not manifest_report_is_current({}), "空报告判成不可比")
    check(not manifest_report_is_current(None), "None 判成不可比，不抛异常")

    print(
        "✓ multimodal_provider selftest: %d checks passed（含 %d 条必红反向对照）"
        % (checks, negative_checks)
    )


if __name__ == "__main__":
    _selftest()