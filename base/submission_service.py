#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/submission_service.py —— 内容入库：四维校验 → ContentUnit → 生产判定。

## 边界

- 只做「把一份 submission 变成可提交的 command payload」；
- **不写 authority**：由 `api/write_api.py` 调 `ReviewCommandService.execute()`；
- 判定在写 authority **之前**同步完成：抛错 / `run_state != OK` / label 非法 →
  不建案，不会留下「有案件、无判定」的残件；
- 不解析图片/视频/文档；本轮只接文本载体（`free_text` / `ad_text`），
  其余显式 `unsupported_source_kind`，不假装已接。

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
DECISION_LABELS = ("PASS", "待自决", "REVIEW", "BLOCK", "未审查")


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
                 max_text_chars=MAX_TEXT_CHARS, clock=None):
        self.authority = (authority_query if authority_query is not None
                          else ExternalStandardsAuthority(kb_path))
        self._authority_injected = authority_query is not None
        self.judge_fn = judge_fn or judge_unit
        self.max_text_chars = int(max_text_chars)
        self.clock = clock

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
        if kind not in SUPPORTED_SOURCE_KINDS:
            raise SubmissionRejected(
                "unsupported_source_kind", 422,
                "本轮只接文本载体 free_text/ad_text，收到 %r" % (kind,))
        if submission.get("content_type") != "文本":
            raise SubmissionRejected(
                "unsupported_content_type", 422,
                "source.kind=%s 必须配 content_type=文本" % kind)
        if kind == "free_text":
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
        payload = {
            "submission_id": submission_id,
            "submission_hash": self.submission_hash(submission, principal=principal),
            "tenant": tenant,
            "product_line": product_line,
            "submitter_id": principal.get("id"),
            "content": unit,
            "ir": ir,
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
