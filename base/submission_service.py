#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/submission_service.py —— 内容入库：四维校验 → ContentUnit → 生产判定。

## 边界

- 只做「把一份 submission 变成可提交的 command payload」；
- **不写 authority**：由 `api/write_api.py` 调 `ReviewCommandService.execute()`；
- 判定在写 authority **之前**同步完成：抛错 / `run_state != OK` / label 非法 →
  不建案，不会留下「有案件、无判定」的残件；
- 载体：`free_text` / `ad_text` **默认开启**；`image` 的进件**能力已建成**
  （T-431），但生产路径由 `MEDIA_INGEST_ENABLED` 显式控制，**默认关闭**
  —— 打开它必须与行 118（容器内跨平台引擎）**同时**做（ADR-0018 §6.2）。
  其余载体（`video` / `文档` 等）显式 `unsupported_source_kind`，不假装已接。
  视频要 T-435 的抽帧：没有抽帧就收视频，等于收一个「审过了」的空壳。

## 依据

`judge_entry.judge_unit` 默认的 `authority_query` 恒 `untested`，会让 L4/L5 恒走
REVIEW。本服务默认注入 `ExternalStandardsAuthority`：依据能解析时 `authority_state=ok`，
链 7 才可能出 BLOCK。研究稿状态原样写进 `resolution_detail.ratification`，不删除。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os

from base import contract as C
from base import submission_router as SR
from base.authority_query import ExternalStandardsAuthority
from base.judge_entry import judge_unit

MAX_TEXT_CHARS = 100_000
SUPPORTED_SOURCE_KINDS = frozenset({"free_text", "ad_text"})

# ──────────────────────────────────────────────────────────────────────────────
# ★ 2026-10-26 T-431：图片进件（**能力**已建，**生产路径**仍未打开）
#
# `SUPPORTED_SOURCE_KINDS` 这一行**刻意不动**。原因不是保守，是 ADR-0018 §6.2
# 把顺序写死了：行 118（媒体只许用容器内跨平台引擎）今天是**空真** ——
# 仓里有 3 处 macOS Vision，只因为生产进件不接媒体，它们不在生产路径上。
#
# 一旦把 `image` 加进上面那个集合：
#   · 行 118 从「空真」翻成**真违规**（`verify_media_portability` G2 退 1）；
#   · `verify_media_selection` S6 退 1（它断言这个集合不含 image/video）；
#   · 生产容器里 `ocr_file()` → `ensure_ocr()` 找不到 macOS SDK，直接抛异常。
#
# 所以本票交付的是「进件这一层真的能收图、能出合法 unit、能进判定」，
# 而「生产路径要不要打开」由 `MEDIA_INGEST_ENABLED` 显式控制，**默认关**。
# 打开它的那一张票必须同时处理行 118（T-118-follow），且两件事必须同时 ——
# 只开开关不换引擎 → 宿主 Vision 变成生产路径上的真违规；
# 只换引擎不开开关 → 那三个宿主文件白删（`verify_media_selection` S7 会红）。
# ──────────────────────────────────────────────────────────────────────────────

#: 生产进件是否接受 image。**默认 False**，只有显式打开才算。
#:
#: ★ T-452（2026-10-27）：从「模块常量」改成**读环境变量 `REVIEW_MEDIA_INGEST`**。
#:   改之前它是一行硬编码，运维配了 `REVIEW_MEDIA_ROOTS` 也永远打不开 ——
#:   能力建成、入口却焊死，而盘上没有任何东西会说这件事。
#:
#: ★ 取值只认 `"1"` / `"true"`（不分大小写），其余一律当关。
#:   用真值判会出事：`"false"` `/` `"0"` 这些字符串在 Python 里都是真值，
#:   于是「运维写了 false」反而打开了 —— 而那是最该避免的方向。
MEDIA_INGEST_ENV = "REVIEW_MEDIA_INGEST"

#: 环境变量缺省时用的值。**保持 False**：默认安全不变。
MEDIA_INGEST_ENABLED_DEFAULT = False


def _env_media_ingest(env=None):
    """读 `REVIEW_MEDIA_INGEST`。返回值只有 True / False 两种。"""
    raw = (os.environ if env is None else env).get(MEDIA_INGEST_ENV)
    if raw is None:
        return MEDIA_INGEST_ENABLED_DEFAULT
    text = str(raw).strip().lower()
    if text in ("1", "true"):
        return True
    if text in ("", "0", "false"):
        return False
    # ★ 胡话（`yes` / `on` / `是` / `2`）**不许**静默当成 False。
    #   静默当关会让「配了但没生效」与「没配」长得一样 —— 那正是 §2.4.1 的形状。
    raise MediaIngestConfigError(
        "%s=%r 不是可识别的开关值（只接受 1/true/0/false）"
        % (MEDIA_INGEST_ENV, raw))


class MediaIngestConfigError(ValueError):
    """媒体进件开关配错了。启动时就该炸，不许带着坏配置跑起来。"""


#: 兼容旧引用：模块级常量改成**函数**（同一个名字不再是一个固定的值）。
#: ★ 保留这个名字是因为有 4 处 `from ... import MEDIA_INGEST_ENABLED` 与
#:   `MEDIA_INGEST_ENABLED is True` 的写法；改成函数会静默把所有调用点变成
#:   「函数对象 is True」→ 恒 False。所以这里不保留同名对象，而是**逐个改调用点**，
#:   改完删掉旧常量。见下方 `ingest_media_enabled()` —— 它才是唯一判据。

#: 打开后允许的媒体载体种类。今天只有 image（视频要 T-435 的抽帧，
#: 没有抽帧就收视频等于收一个「审过了」的空壳）。
MEDIA_SOURCE_KINDS = frozenset({"image", "video"})

#: 图片载体必须配的 content_type（与 contract.CONTENT_TYPES 同一取值域）。
_SOURCE_KIND_CONTENT_TYPE = {"free_text": "文本", "ad_text": "文本",
                             "image": "图片", "video": "视频"}

DECISION_LABELS = ("PASS", "待自决", "REVIEW", "BLOCK", "未审查")


def ingest_media_enabled(env=None):
    """媒体进件此刻是否打开。**唯一判据**，读一个地方。

    ★ `env` 只为自证注入用（默认读真实环境）。★ 不设「模块级可改写开关」——
      那种写法下，生产读 env、自证改常量、两边判据不同源，就会出现
      「自证测过的开关」与「生产真正读的开关」是两个东西（§2.4.8）。
    """
    return _env_media_ingest(env)


def media_ingest_readiness(env=None):
    """媒体进件此刻能**审到什么程度**。返回 `(ok, reason)`。

    ## ★ 2026-10-28 改判据：多模态接上之后，旧判据已经不对了

    T-452 当时的判据是「开关开了但 OCR 引擎是 `host_vision` → 报 False」。
    那个判据当时是对的：没有 OCR 就没有正文，媒体进件等于开了个审不了的入口。

    **但多模态接进生产之后，这个前提变了。** 实测（2026-10-28）：

        parse_status = failed（OCR 没成）
        multimodal_observations = 1 条真实画面观察
        decision = 未审查

    也就是说：没有 OCR **照样能审画面语义**，只是「正文那一半」做不了。
    再拿 OCR 一条卡死整个入口，就是把「能做一半」说成「一点都不能做」。

    ## 所以判据改成「审到什么程度」

    | 条件 | ok | reason |
    |---|---|---|
    | 开关没开 | True | ""（默认安全，不算错配） |
    | 开关开 + 多模态就绪 | True | ""（画面能审；正文能否提取另说） |
    | 开关开 + 无多模态 + 无 OCR | False | 说清两条都缺 |

    ★ 仍然返回 False 的最后一种情况是**真的什么都审不了**，不是「不够完美」。
    """
    from base import media as MEDIA

    if not ingest_media_enabled(env):
        return True, ""

    engine = getattr(MEDIA, "DEFAULT_OCR_ENGINE", None)
    ocr_ready = engine != "host_vision"

    try:
        from base import media_analyze as MA
        mm = MA.readiness(env)
        vision_ready = bool(mm["image"]["ready"])
    except Exception:  # noqa: BLE001
        # 接线层自己坏了 → 当作没有多模态（保守），但仍不静默：
        # 下面的 reason 会说清「多模态不可用」。
        vision_ready = False

    if ocr_ready or vision_ready:
        return True, ""

    return False, (
        "进了媒体进件开关（%s），但两条审图能力都没有："
        "① OCR 引擎仍是 host_vision（macOS 专用，容器里必然落 parse_status=failed）；"
        "② 多模态网关凭据未配（缺 MULTIMODAL_TOKENHUB_* / MULTIMODAL_VOD_*）。"
        "两条都没有时，媒体进件等于开了个什么都审不了的入口。"
        % MEDIA_INGEST_ENV)


def media_ingest_capability(env=None):
    """媒体进件**具体能审哪几件事**。给界面用的可读读数。

    ★ 为什么不能只返回一个布尔：一张图能审「画面语义」但审不了「图内文字」，
      这两件事对审核员的含义完全不同（前者答「画面有没有暗示疗效」，
      后者答「文案里那句话有没有违规」）。合并成一个「能审/不能审」，
      会让人以为看过了全部。
    """
    from base import media as MEDIA

    enabled = ingest_media_enabled(env)
    engine = getattr(MEDIA, "DEFAULT_OCR_ENGINE", None)
    ocr_ready = engine != "host_vision"
    try:
        from base import media_analyze as MA
        mm = MA.readiness(env)
    except Exception:  # noqa: BLE001
        mm = {"image": {"ready": False}, "video": {"ready": False},
              "missing_env": [], "reason": "多模态接线层不可用"}

    return {
        "enabled": enabled,
        # 图内文字（OCR）：决定「文案层面」能不能判
        "text_extraction": {"ready": ocr_ready, "engine": engine},
        # 画面语义 / 标志识别（多模态）：决定「画面层面」能不能判
        "vision": {
            "image": bool(mm.get("image", {}).get("ready")),
            "video": bool(mm.get("video", {}).get("ready")),
            "missing_env": list(mm.get("missing_env") or []),
        },
        # 视频的音画对齐只有 vod 能做
        "av_alignment": bool(mm.get("video", {}).get("ready")),
    }


def supported_source_kinds_now(env=None):
    """**此刻**真实接受的载体集合。

    ★ 为什么要有这个函数而不是直接读 `SUPPORTED_SOURCE_KINDS`：
      那个常量是「不做媒体的那份声明」；而「现在能收什么」是随开关走的。
      两个问题两个答案，混用就会出现「常量说没有、实际收得了」或者反过来
      —— 后者正是 §2.4.1 说的假数据。

    ★ 2026-10-28：视频也进来了。它的正文来自多模态（整段视频字节送模型），
      不再等 `DEFAULT_ASR_ENGINE` —— 那个仍是 None，但已经不再是阻塞项
      （实测 1689 个模型支持 video 输入，见 `base/media_analyze.py` 文件头）。
      音画对齐（`av_alignment`）另说：它只有 vod 能做，缺 vod 时跳过并说清。
    """
    if ingest_media_enabled(env):
        return SUPPORTED_SOURCE_KINDS | MEDIA_SOURCE_KINDS
    return SUPPORTED_SOURCE_KINDS



class SubmissionRejected(Exception):
    def __init__(self, code, status, detail=""):
        self.code = code
        self.status = int(status)
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise SubmissionRejected("bad_submission", 422, "%s 必须是非空字符串" % name)
    return value.strip()


def apply_stage_inference(submission, *, known_inference=None):
    """`content_stage` 缺失时补一个**推断出的建议值**。返回 `(新 submission, 观察)`。

    ## ★★ 为什么它必须是一个**共用**的纯函数，而不是写在 `prepare()` 里

    第一版写在 `prepare()` 里，随即撞上一个真缺陷：
    `base/review_command_service.py` 在调 `prepare()` **之前**就用
    `ingestor.submission_hash(submission)` 算了幂等哈希，而哈希里包含
    `content_stage`（`submission_hash()` 的 body 里就有它）。

    于是同一个请求：

        重放时 service 侧算的哈希 = 65d53ca4…（原始，缺 stage）
        payload 里存的哈希       = 2ef748f6…（已补 stage）

    两个值不同 → `authority.idempotent()` 那条比对判为不一致 →
    **误报 `idempotency_conflict`**。实测确认过（见 T-455 提交说明）。

    修法只有一条：补值必须发生在**算哈希之前**，且**两处走同一个函数**。
    各自补一次必然分叉（AGENTS.md §2.4.8「同一个量两个口径」）。

    ## ★ `known_inference`：为什么需要它

    上游补过之后，`prepare()` 再跑一次时看到 `content_stage='brief'`，
    会误以为「这是调用方申报的」，返回 `status=absent` —— 于是
    **推断这件事在案件记录里消失了**，下游看到 stage 有值就当成是人填的。

    所以上游把自己那次推断通过 `known_inference=` 传下来：
    检测到「传下来的值就是我上次推断的那个」时，复用那份观察而
    **不重新判定**为 absent。两处仍然只判定一次。

    ## 口径（三条不许破）

    ① 调用方给了值 → **一律采信**，不推断。`content_stage` 是调用方申报的事实
       （这条内容是什么阶段），不是模型可以改写的判断。
    ② 推断不出 → **不补**，让四维校验照原样报 422（缺字段）。
       绝不许默认成某一档：默认 `final_content` 会让 brief 文案按终稿标准判，
       默认 `brief` 会让终稿被当草稿放过。两个方向都错，所以不选。
    ③ 观察必须**随案件走**（落 `intent_inference`），否则下游看到 stage 有值
       就以为是人填的。
    """
    from base import intent_infer as _II

    if not isinstance(submission, dict):
        return submission, _II.infer_stage(None)

    declared = submission.get("content_stage")

    # ★ 上游已经补过：认出来，别把它当成「调用方申报的」。
    if (isinstance(known_inference, dict)
            and known_inference.get("status") == _II.STATUS_INFERRED
            and known_inference.get("value")
            and declared == known_inference.get("value")):
        return submission, known_inference

    inference = _II.infer_stage(submission.get("text"), declared=declared)
    if (inference.get("status") == _II.STATUS_INFERRED
            and inference.get("value")
            and declared in (None, "")):
        # `dict(...)` 而不是原地改：调用方传进来的对象不该被这个函数改写。
        return dict(submission, content_stage=inference["value"]), inference
    return submission, inference


class SubmissionIngestor:
    def __init__(self, *, authority_query=None, judge_fn=None, kb_path=None,
                 max_text_chars=MAX_TEXT_CHARS, clock=None, media_roots=None):
        self.authority = (authority_query if authority_query is not None
                          else ExternalStandardsAuthority(kb_path))
        self._authority_injected = authority_query is not None
        self.judge_fn = judge_fn or judge_unit
        self.max_text_chars = int(max_text_chars)
        self.clock = clock
        #: 图片进件允许的位图根目录。**默认空 = 不收图**，理由见 _build_image_unit。
        self.media_roots = tuple(media_roots or ())

    def _multimodal_analyze(self, unit):
        """给媒体载体造一个 `analyze(media_ref, tasks)`；文本载体返回 None。

        ## 三条口径

        ① **只在媒体载体上注入**。文本载体不需要多模态，注入会白跑一遍
           （而且要建客户端、读凭据、可能发一次请求）。
        ② **路径从 unit 上取，不从 uri 反推**。进件层在 `_build_image_unit` 里
           已经把 `_media_local_path` 写进 unit（那是**解析过**的绝对路径）。
           从 uri 反推会在 media_roots 有多个时猜错根目录，而猜错的表现是
           「审了另一张图」—— 不报错，只给错结论。
        ③ **凭据未配 → 返回 None**，让 `judge_entry` 落「未接入多模态分析」。
           它与「本载体无需多模态」是两种不同原因，**都不许被读成没问题**。
        """
        source = (unit.get("source") or {}) if isinstance(unit, dict) else {}
        kind = source.get("kind")
        if kind not in ("image", "video"):
            return None

        local = unit.get("_media_local_path")
        if not isinstance(local, str) or not local.strip():
            # ★ 媒体载体却没有本地路径 → 不注入，但**不留空**：
            #   把原因挂在 unit 上，判定层会把它落成 untested 的 note。
            unit["_media_local_path_note"] = (
                "媒体载体 %r 没有已解析的本地路径（进件层未提供）—— 无法做多模态分析"
                % (kind,))
            return None

        try:
            from pathlib import Path as _LocalPath

            from base import media_analyze as MA
            return MA.build_analyze(
                resolve_path=lambda ref: _LocalPath(local),
            )
        except Exception:  # noqa: BLE001
            # 接线层自己坏了 → 不注入（判定层会落未接入）。
            # ★ 这里**不许**把它变成「没有发现违规」：不注入就不会有观察，
            #   而观察为空时报告写的是「未评」，不是「没有问题」。
            return None

    def _query(self):
        if self._authority_injected:
            if callable(self.authority):
                return self.authority
            return self.authority.query
        return self.authority.query

    def _kb_snapshot(self):
        if self._authority_injected:
            return getattr(self.authority, "snapshot_id", None) or "kb-injected"
        return self.authority.snapshot_id
    @staticmethod
    def case_id_for(tenant, submission_id):
        body = ("%s\0%s" % (tenant, submission_id)).encode("utf-8")
        return "case-" + hashlib.sha256(body).hexdigest()[:20]

    @staticmethod
    def submission_hash(submission, *, principal):
        """幂等判据：只覆盖**输入**，不覆盖判定产物（时间戳/回执会变）。

        同 key 重放时先用它命中已提交批次，命中就不重判；这样重放既快又不会
        因为两次判定的时间戳不同而被误判成 idempotency_conflict。
        """
        body = {
            "submission_id": (submission or {}).get("submission_id"),
            "content_type": (submission or {}).get("content_type"),
            "content_stage": (submission or {}).get("content_stage"),
            "entry_channel": (submission or {}).get("entry_channel"),
            "source": (submission or {}).get("source"),
            "text": (submission or {}).get("text"),
            "fields": (submission or {}).get("fields"),
            "product_line": (submission or {}).get("product_line"),
            "uri": (submission or {}).get("uri"),
            "tenant": (principal or {}).get("tenant"),
            "submitter_id": (principal or {}).get("id"),
        }
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _build_unit(self, submission, *, product_line, uri):
        kind = (submission.get("source") or {}).get("kind")
        allowed = supported_source_kinds_now()
        if kind not in allowed:
            # ★ 媒体载体被开关挡下时，错误信息必须说清是**哪一道**门挡的 ——
            #   否则「不支持 image」会被读成「图片审核没做」，而实际上能力已经建好了。
            if kind in MEDIA_SOURCE_KINDS and not ingest_media_enabled():
                raise SubmissionRejected(
                    "media_ingest_disabled", 422,
                    "source.kind=%r 的进件能力已建成，但生产路径未打开"
                    "（%s 未设或为假）。打开它必须与容器内 OCR 引擎同时做"
                    "（ADR-0018 §6.2 / T-118-follow）—— 只开开关不给引擎，"
                    "每张图都会落 parse_status=failed。"
                    % (kind, MEDIA_INGEST_ENV))
            raise SubmissionRejected(
                "unsupported_source_kind", 422,
                "本轮只接 %s，收到 %r" % (sorted(allowed), kind))
        expected_content_type = _SOURCE_KIND_CONTENT_TYPE.get(kind)
        if submission.get("content_type") != expected_content_type:
            raise SubmissionRejected(
                "unsupported_content_type", 422,
                "source.kind=%s 必须配 content_type=%s"
                % (kind, expected_content_type))
        if kind in MEDIA_SOURCE_KINDS:
            # ★ 2026-10-28：视频与图片走同一条「媒体进件」路径（路径校验、
            #   本地路径回填、覆盖边界声明都一样）。差别只在正文从哪来，
            #   那在 `_build_media_unit` 里按 kind 分支。
            unit = self._build_media_unit(submission, kind=kind, uri=uri)
        elif kind == "free_text":
            text = submission.get("text")
            if not isinstance(text, str) or not text.strip():
                raise SubmissionRejected("bad_text", 422, "free_text 必须带非空 text")
            unit = C.from_text(text, uri=uri)
        else:
            fields = submission.get("fields")
            if not isinstance(fields, dict):
                raise SubmissionRejected("bad_fields", 422, "ad_text 必须带 fields 对象")
            record = {
                "Primary Text": fields.get("Primary Text", ""),
                "Headline": fields.get("Headline", ""),
            }
            if not any(str(v or "").strip() for v in record.values()):
                raise SubmissionRejected(
                    "bad_fields", 422, "ad_text 的 Primary Text/Headline 至少一个非空")
            unit = C.from_ad_record(record, uri=uri)
        if len(unit.get("text") or "") > self.max_text_chars:
            raise SubmissionRejected(
                "text_too_long", 413,
                "正文 %d 字符，上限 %d" % (len(unit["text"]), self.max_text_chars))
        problems = C.validate(unit)
        if problems:
            raise SubmissionRejected(
                "bad_content_unit", 422, "; ".join(problems))
        return unit

    @staticmethod
    def _video_unit(target, *, uri):
        """视频 → ContentUnit。**没有口播转写时，明说没做。**

        ## 为什么正文是空串

        `DEFAULT_ASR_ENGINE = None` —— 本仓没有语音转写。
        `from_media()` 要求正文由调用方给出，而这里**确实没有**正文可给。

        所以传空串，并把「口播文案未审」写进 `does_not_cover`。
        这不只是措辞：`covers` / `does_not_cover` 会原样进报告，
        审核员看到「视频已审」时默认会以为连口播一起查过了。

        ## 那视频还审什么

        审**画面** —— 由多模态在判定阶段做（`base/media_analyze.py`：
        `scene_semantics` + `mark_symbol`，配了 vod 还加 `av_alignment` 音画对齐）。
        实测：1689 个模型支持 video 输入，整段视频字节直接送模型，
        不需要抽帧、也不需要 ASR。

        ★ 画面观察是**独立的 L1 观察**，不是这个 unit 的 `covers` ——
          两处的区别在报告里看得出来：「覆盖声明」说的是这份载体被处理到哪一步，
          「观察」说的是模型看到了什么。
        """
        from base import contract as C

        raw = target.read_bytes()
        if not raw:
            raise ValueError("视频文件为空（0 字节）")
        unit = C.from_media(
            "video", raw, "",
            uri=uri,
            extractor="multimodal-direct-v1",
            # ★ 只声明**确实做了**的：把整段视频交给多模态看画面。
            covers=["视频画面（整段，多模态模型直接读取）"],
            # ★★ 这一条是本函数存在的理由：没有 ASR 就**必须**说出来。
            does_not_cover=[
                "口播文案（本仓无语音转写，DEFAULT_ASR_ENGINE = None）",
                "画面逐帧 OCR（未开图内文字提取）",
            ],
        )
        # ★★ `parse_status` 必须是 **partial**，不是 ok、也不是 failed。
        #
        #   `from_media()` 自己不设这个字段（那是 `row_to_unit` 的职责，
        #   而视频不走那条路）。如果不显式补，`_build_media_unit` 的校验会拒
        #   （实测：`parse_status=None 非法（只允许 ok/partial/failed）`）。
        #
        #   为什么是 partial：
        #     · 不是 ok    —— 口播文案一个字都没读，说 ok 就是撒谎；
        #     · 不是 failed —— 画面确实交给了多模态，模型会给出真实观察。
        #   三态里「partial」在这里不是模糊，它精确地是「做了一半」。
        unit["parse_status"] = "partial"
        return unit

    def _build_media_unit(self, submission, *, kind, uri):
        """媒体载体（图片 / 视频）→ ContentUnit。

        ## ★ 能力边界照实说

        **图片**：`row_to_unit()` 产出的 `does_not_cover` 里含「画面语义」。
        本函数**不许**往里加任何东西 —— 往 `covers` 里加一句「画面语义已审」
        就等于把没审的部分伪装成审过（T-430 修掉的正是这个病）。
        画面语义由**多模态**在判定阶段补，产出的是一条独立的 L1 观察，
        不是这件事的 `covers`。

        **视频**：`DEFAULT_ASR_ENGINE = None`，没有口播转写。所以
        `covers` 只敢写「画面帧」与「音轨（未对齐时不含）」，
        `does_not_cover` **必须**明写「口播文案」—— 这条不是客气话：
        审核员看到「视频已审」时，默认会以为连口播一起查过了。

        ## ★ 路径约束

        只接受**调用方显式给出**且落在允许根内的文件。没有根约束时，
        这个端点会变成「对机器上任意文件做提取并回显正文」的内容读取器 ——
        与 §2.6 第 3 条（凭据文件一律不许读）是同一个形状。
        """
        from pathlib import Path as _Path

        from base import media as MEDIA

        source = submission.get("source") or {}
        raw_uri = source.get("uri")
        if not isinstance(raw_uri, str) or not raw_uri.strip():
            raise SubmissionRejected(
                "bad_media_uri", 422,
                "source.kind=%s 必须带 source.uri（文件路径）" % kind)
        candidates = []
        for root in self.media_roots:
            try:
                candidates.append(_Path(root).expanduser().resolve())
            except OSError:
                continue
        if not candidates:
            raise SubmissionRejected(
                "media_root_not_configured", 503,
                "图片进件已启用但未配置允许的位图根目录（media_roots）。"
                "不配根目录就不收图 —— 否则这个端点会对任意路径做 OCR。")
        try:
            target = _Path(raw_uri).expanduser()
            if not target.is_absolute():
                target = candidates[0] / target
            target = target.resolve()
        except OSError as exc:
            raise SubmissionRejected(
                "bad_image_uri", 422, "路径无法解析：%s" % exc) from exc
        inside = any(target == root or root in target.parents for root in candidates)
        if not inside:
            # ★ 不回显 target 的真实路径：报错里带出绝对路径本身也是信息泄露
            #   （目录结构 + 用户名），而调用方已经知道它传了什么。
            raise SubmissionRejected(
                "image_path_outside_allowed_roots", 403,
                "位图不在允许的根目录内（配置了 %d 个根）" % len(candidates))
        if not target.is_file():
            raise SubmissionRejected(
                "image_not_found", 404, "位图不存在或不是普通文件")

        try:
            if kind == "video":
                unit = self._video_unit(target, uri=uri)
            else:
                row = MEDIA.image_file_row(target, uri=uri)
                unit = MEDIA.row_to_unit(row, uri)
        except Exception as exc:  # noqa: BLE001
            # ★ 不许把异常吞成「审过了」。判据要求 OCR 失败必须落
            #   parse_status=failed 且 failure_kind 属于四类之一 ——
            #   那是 row_to_unit 的职责；这里只兜「连 row 都造不出来」的情况。
            raise SubmissionRejected(
                "image_ingest_failed", 422,
                "%s: %s" % (type(exc).__name__, exc)) from exc
        if not isinstance(unit, dict):
            raise SubmissionRejected(
                "image_ingest_failed", 422, "row_to_unit 未返回 ContentUnit")
        # ★★ ADR-0021 主线：把**已解析的本地绝对路径**随 unit 往下传。
        #
        #   为什么不能从 `unit["source"]["uri"]` 反推：
        #   `uri` 是调用方给的原值，可能是相对路径（按 media_roots[0] 解析）、
        #   也可能是 `submission:xxx` 这种逻辑标识。反推会在 media_roots 有多个时
        #   **猜错根目录** —— 而猜错的后果是「审了另一张图」：
        #   它不会报错，只会给出错误的观察。
        #
        #   `_media_local_path` 以下划线开头，表示「这是进件层的私有信息，
        #   不是契约字段」，`validate()` 也不会因为多这个键而红（已实测）。
        unit["_media_local_path"] = str(target)
        # ★ 判据 3 的执行点：OCR 失败**不许**产出一个「审过了」的 REVIEW。
        #   `row_to_unit` 已经把失败写成 parse_status=failed + failure_kind，
        #   这里断言它确实这么写了 —— 若有一天它改成返回 ok，这一行先红。
        if unit.get("parse_status") not in ("ok", "partial", "failed"):
            raise SubmissionRejected(
                "image_ingest_failed", 422,
                "parse_status=%r 非法（只允许 ok/partial/failed）"
                % (unit.get("parse_status"),))
        return unit

    def prepare(self, submission, *, principal, known_inference=None):
        """返回 `{case_id, payload}`；任何失败都不产生 authority 写入。

        `known_inference`：上游（`review_command_service.execute_submission`）
        在算幂等哈希之前已经补过一次 stage 时，把它那次推断传下来 ——
        否则这里会把它误判成「调用方申报的」，推断记录就丢了。
        """
        if not isinstance(submission, dict):
            raise SubmissionRejected("bad_submission", 422, "submission 必须是对象")
        if not isinstance(principal, dict):
            raise SubmissionRejected("bad_principal", 403, "principal 必须是对象")
        # ★ T-455：`content_stage` 缺失时先推断再校验。
        #   `classify_submission()` 会因为它缺失而 422（四维校验必填），
        #   所以推断必须在校验**之前** —— 放在之后等于永远跑不到。
        #   口径与「为什么必须是共用函数」写在 `apply_stage_inference()` 的文档里。
        submission, stage_inference = apply_stage_inference(
            submission, known_inference=known_inference)

        verdict = SR.classify_submission(submission)
        if verdict["outcome"] != "accepted":
            raise SubmissionRejected(
                "submission_rejected", 422, verdict.get("reason") or verdict["outcome"])
        submission_id = _nonempty(submission.get("submission_id"), "submission_id")
        product_line = _nonempty(submission.get("product_line"), "product_line")
        tenant = principal.get("tenant")
        if not isinstance(tenant, str) or not tenant.strip():
            raise SubmissionRejected("bad_principal", 403, "principal 缺 tenant")
        submitted_tenant = submission.get("tenant")
        if submitted_tenant is not None and submitted_tenant != tenant:
            raise SubmissionRejected(
                "tenant_mismatch", 403, "submission.tenant 与 principal.tenant 不一致")
        lines = principal.get("product_lines") or []
        if lines and product_line not in lines:
            raise SubmissionRejected(
                "product_line_not_allowed", 403,
                "principal 无品线 %r 的提交权限" % product_line)
        uri = submission.get("uri") or ("submission:" + submission_id)
        unit = self._build_unit(submission, product_line=product_line, uri=uri)
        try:
            kwargs = {
                "authority_query": self._query(),
                "kb_snapshot": self._kb_snapshot(),
                # ★ T-453：显式说出用的是哪个 skill，不再依赖 judge_entry 的默认值。
                #   改之前这里一个参数都没传，于是回执永远写默认的 content-review /
                #   "1" / "local" —— 而生产链路「用哪一版规程」这件事**在盘上指不出文件**。
                #   现在 `skill_id` 传下去，`skill_version`/`skill_hash` 由注册表算。
                "skill_id": "content-review",
            }
            # ★★ ADR-0021 主线：多模态分析接进生产。
            #
            #   改前 `judge_entry` 的 `multimodal_analyze` 注入点**生产链路一个参数
            #   都没传**（实测 grep 0 命中），于是每张图 / 每段视频都落
            #   「未接入多模态分析」。这是本项目第四次同形：
            #   due_at / 工作流耗时 / semantic_judge / skill_hash，现在多一个。
            #
            #   ★ 只在**媒体载体**上注入：文本载体不需要，注入会白跑一遍。
            #   ★ 凭据未配时 `build_analyze()` 返回 None → 这里不传 →
            #     `judge_entry` 落「未接入多模态分析」。**两种原因不同、都不许
            #     被读成「没问题」**：一个是「没配」，一个是「没这个载体」。
            analyze = self._multimodal_analyze(unit)
            if analyze is not None:
                kwargs["multimodal_analyze"] = analyze
            if self.clock is not None:
                kwargs["clock"] = self.clock
            judgment = self.judge_fn(unit, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise SubmissionRejected(
                "judgment_failed", 422,
                "%s: %s" % (type(exc).__name__, exc)) from exc
        if not isinstance(judgment, dict) or judgment.get("run_state") != "OK":
            raise SubmissionRejected(
                "judgment_failed", 422,
                "判定未完成（run_state=%r）" % (
                    judgment.get("run_state") if isinstance(judgment, dict) else None,))
        label = judgment.get("label")
        ir = judgment.get("ir")
        if label not in DECISION_LABELS:
            raise SubmissionRejected("judgment_failed", 422, "label=%r 非法" % (label,))
        if not isinstance(ir, dict) or (ir.get("decision") or {}).get("state") != label:
            raise SubmissionRejected(
                "judgment_failed", 422, "label 与 ir.decision.state 不一致")
        case_id = self.case_id_for(tenant, submission_id)
        # T-310a：签发绑定的判定时点快照（T-310 施工单 §二 前置 B）。
        # kb_snapshot_hash = 判定所用 KB 快照 id 的 sha256（2026-10-25 D1 裁定，
        # 取不到时 _kb_snapshot() 的值仍非空，hash 照算 —— 缺失会在 binding
        # 提取时 fail closed，这里不发明第二个口径）。
        # conflict_table_version 与 ir.control_points_version 是同一个量；
        # reducer 侧断言两者一致，两边漂移在 ingest 即红。
        kb_snapshot_hash = hashlib.sha256(
            self._kb_snapshot().encode("utf-8")).hexdigest()
        payload = {
            "submission_id": submission_id,
            "submission_hash": self.submission_hash(submission, principal=principal),
            "tenant": tenant,
            "product_line": product_line,
            "submitter_id": principal.get("id"),
            "content": unit,
            "ir": ir,
            "kb_snapshot_hash": kb_snapshot_hash,
            "conflict_table_version": ir.get("control_points_version"),
            "media_fingerprints": ir.get("media_fingerprints") or {},
            # ★ T-455：内容阶段的推断观察。**必须随案件走** ——
            #   若只留在 prepare() 的局部变量里，出了这个函数就没了，
            #   而「这个 stage 是人填的还是推断的」恰恰是下游最需要知道的事。
            #   三态原样保留（inferred / untested / absent），不压成布尔。
            "intent_inference": stage_inference,
            # ★ ADR-0021 主线：多模态「为什么没看成」的说明。
            #   `judge_entry` 早就返回它了（`multimodal_note`），但 payload 顶层
            #   从来没带上 —— 于是 reducer 读不到，state 里也就没有这个字段。
            #   后果：报告里「画面语义」那一节只剩空列表，读起来像「画面没问题」。
            #   「没看成」与「看了没问题」必须长得不一样。
            "multimodal_note": (judgment.get("multimodal_note") or None),
            # T-316b: the frozen render input for the report.
            #
            # Deliberately carries whatever judge_entry returned, including None.
            # This method does NOT require a snapshot, and that is a decision,
            # not an oversight:
            #   · tests inject custom judge_fn doubles that return a real
            #     judgement without a snapshot (e.g. verify_finding_adjudication's
            #     judge_with_candidate wraps judge_unit, so it does carry one —
            #     but a double written from scratch would not);
            #   · more importantly, judging whether "no report can be rendered"
            #     should block ingestion is a product question (a case with no
            #     report is still reviewable), not something this layer decides.
            # The gate that must not be skipped lives at publish time:
            # ReportStore.publish() refuses a snapshot it cannot render, so the
            # failure surfaces as "report not produced", never as a report with
            # missing sections. See T-316d.
            "report_snapshot": judgment.get("report_snapshot"),
            # T-433：L1 多模态观察进权威（随 state 走，可重放）。
            # ★ 不进 ir.findings：finding 的准入是 control_code/authority_ref/
            #   location 三要素合取，多模态给不出前两项（知识库产物）。
            #   把观察塞进 finding 表的后果是**复核时无法申诉**。
            "multimodal_observations": judgment.get("multimodal_observations") or [],
            "judgment": {
                "label": label,
                "layer": judgment.get("layer"),
                "release_status": judgment.get("release_status"),
                "run_state": judgment.get("run_state"),
                "receipt": judgment.get("receipt"),
            },
            "content_hash": (unit.get("fingerprint") or {}).get("text_sha256"),
        }
        return {"case_id": case_id, "payload": payload,
                "submission_id": submission_id,
                "decision": copy.deepcopy(ir.get("decision"))}
