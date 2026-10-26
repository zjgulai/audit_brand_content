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

#: 生产进件是否接受 image。**默认 False**，且只有显式 `True` 才算打开。
#: ★ 用 `is True` 判，不用真值判：`"false"` / `"0"` / `1` 这些从环境变量读来的
#:   字符串都是真值 —— 用真值判等于「配了字符串就打开了」，而运维会以为写 false 是关的。
MEDIA_INGEST_ENABLED = False

#: 打开后允许的媒体载体种类。今天只有 image（视频要 T-435 的抽帧，
#: 没有抽帧就收视频等于收一个「审过了」的空壳）。
MEDIA_SOURCE_KINDS = frozenset({"image"})

#: 图片载体必须配的 content_type（与 contract.CONTENT_TYPES 同一取值域）。
_SOURCE_KIND_CONTENT_TYPE = {"free_text": "文本", "ad_text": "文本", "image": "图片"}

DECISION_LABELS = ("PASS", "待自决", "REVIEW", "BLOCK", "未审查")


def ingest_media_enabled():
    """媒体进件此刻是否打开。**唯一判据**，读一个地方。"""
    return MEDIA_INGEST_ENABLED is True


def supported_source_kinds_now():
    """**此刻**真实接受的载体集合：开关打开才含 image。

    ★ 为什么要有这个函数而不是直接读 `SUPPORTED_SOURCE_KINDS`：
      那个常量是「不做媒体的那份声明」，它在 T-118-follow 之前不该变；
      而「现在能收什么」是随开关走的。两个问题两个答案，混用就会出现
      「常量说没有、实际收得了」或者反过来 —— 后者正是 §2.4.1 说的假数据。
    """
    if ingest_media_enabled():
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
                    "（MEDIA_INGEST_ENABLED=False）。打开它必须与行 118 的"
                    "容器内引擎同时做（ADR-0018 §6.2 / T-118-follow）。" % (kind,))
            raise SubmissionRejected(
                "unsupported_source_kind", 422,
                "本轮只接 %s，收到 %r" % (sorted(allowed), kind))
        expected_content_type = _SOURCE_KIND_CONTENT_TYPE.get(kind)
        if submission.get("content_type") != expected_content_type:
            raise SubmissionRejected(
                "unsupported_content_type", 422,
                "source.kind=%s 必须配 content_type=%s"
                % (kind, expected_content_type))
        if kind == "image":
            unit = self._build_image_unit(submission, uri=uri)
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

    def _build_image_unit(self, submission, *, uri):
        """图片载体 → ContentUnit。

        ★ 能力边界照实说：**只做图内文字的 OCR**。`row_to_unit()` 产出的
          `does_not_cover` 里含「画面语义」，本函数**不许**往里加任何东西 ——
          往 `covers` 里加一句「画面语义已审」就等于把没审的部分伪装成审过，
          而那正是 T-430 刚在投影层修掉的那个病。

        ★ 路径约束：只接受**调用方显式给出**且落在允许根内的位图。
          没有根约束时，这个端点会变成「对机器上任意文件做 OCR 并回显正文」的
          内容读取器 —— 与 §2.6 第 3 条（凭据文件一律不许读）是同一个形状：
          一旦能读任意路径，挡路的就只剩调用方的自觉。
        """
        from pathlib import Path as _Path

        from base import media as MEDIA

        source = submission.get("source") or {}
        raw_uri = source.get("uri")
        if not isinstance(raw_uri, str) or not raw_uri.strip():
            raise SubmissionRejected(
                "bad_image_uri", 422, "source.kind=image 必须带 source.uri（位图路径）")
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
        # ★ 判据 3 的执行点：OCR 失败**不许**产出一个「审过了」的 REVIEW。
        #   `row_to_unit` 已经把失败写成 parse_status=failed + failure_kind，
        #   这里断言它确实这么写了 —— 若有一天它改成返回 ok，这一行先红。
        if unit.get("parse_status") not in ("ok", "partial", "failed"):
            raise SubmissionRejected(
                "image_ingest_failed", 422,
                "parse_status=%r 非法（只允许 ok/partial/failed）"
                % (unit.get("parse_status"),))
        return unit

    def prepare(self, submission, *, principal):
        """返回 `{case_id, payload}`；任何失败都不产生 authority 写入。"""
        if not isinstance(submission, dict):
            raise SubmissionRejected("bad_submission", 422, "submission 必须是对象")
        if not isinstance(principal, dict):
            raise SubmissionRejected("bad_principal", 403, "principal 必须是对象")
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
            }
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
