import {
  request,
  type DraftMutation,
  type LedgerMutation,
  type ReferenceMutation,
  type SubmitMutation,
} from "./client";

/** confirm / reject 的响应：台账变更 + 被裁决的 finding。 */
export type FindingMutation = LedgerMutation & { finding?: Record<string, unknown> };

/**
 * 人工写动作客户端（T-150 / T-170 / Wave B）。
 *
 * 每个方法都要求调用方显式给 Idempotency-Key。这里不偷偷生成 key，
 * 因为只有页面知道「这是不是同一个用户意图的重试」。
 */
export const reviewWriteApi = {
  claim: (caseId: string, idempotencyKey: string) =>
    request<LedgerMutation>(`/cases/${encodeURIComponent(caseId)}/claim`, {
      method: "POST",
      body: {},
      idempotencyKey,
    }),

  unclaim: (caseId: string, version: number, idempotencyKey: string) =>
    request<LedgerMutation>(`/cases/${encodeURIComponent(caseId)}/unclaim`, {
      method: "POST",
      body: { version },
      idempotencyKey,
    }),

  reassign: (caseId: string, version: number, assignee: string, idempotencyKey: string) =>
    request<LedgerMutation>(`/cases/${encodeURIComponent(caseId)}/reassign`, {
      method: "POST",
      body: { version, assignee },
      idempotencyKey,
    }),

  heartbeat: (caseId: string, version: number, idempotencyKey: string) =>
    request<LedgerMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: { version, action: "heartbeat" },
      idempotencyKey,
    }),

  saveDraft: (
    caseId: string,
    version: number,
    draft: {
      form?: Record<string, unknown>;
      notes?: string;
      evidence_selections?: unknown[];
      references?: unknown[];
    },
    idempotencyKey: string,
  ) =>
    request<DraftMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: { version, action: "save_draft", draft },
      idempotencyKey,
    }),

  /** UJ-2 Draft Handoff：显式 adopt 前任主草稿，生成带 derived_from 的新草稿。 */
  adoptDraft: (
    caseId: string,
    version: number,
    sourceDraftId: string,
    idempotencyKey: string,
  ) =>
    request<DraftMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: { version, action: "adopt_draft", source_draft_id: sourceDraftId },
      idempotencyKey,
    }),

  /** UJ-2 Draft Handoff：引用非主草稿片段（source_draft_id + field_path + fragment）。 */
  referenceFragment: (
    caseId: string,
    version: number,
    sourceDraftId: string,
    fieldPath: string,
    fragment: unknown,
    idempotencyKey: string,
  ) =>
    request<ReferenceMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: {
        version,
        action: "reference_fragment",
        source_draft_id: sourceDraftId,
        field_path: fieldPath,
        fragment,
      },
      idempotencyKey,
    }),

  /** T-170：逐条确认 / 驳回。reason 可选，作为裁决理由落 authority。 */
  confirmFinding: (
    caseId: string,
    version: number,
    findingId: string,
    reason: string,
    idempotencyKey: string,
  ) =>
    request<FindingMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: {
        version,
        action: "confirm",
        finding_id: findingId,
        ...(reason.trim() ? { reason: reason.trim() } : {}),
      },
      idempotencyKey,
    }),

  rejectFinding: (
    caseId: string,
    version: number,
    findingId: string,
    reason: string,
    idempotencyKey: string,
  ) =>
    request<FindingMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: {
        version,
        action: "reject",
        finding_id: findingId,
        ...(reason.trim() ? { reason: reason.trim() } : {}),
      },
      idempotencyKey,
    }),

  submitConclusion: (
    caseId: string,
    version: number,
    conclusion: Record<string, unknown>,
    idempotencyKey: string,
  ) =>
    request<SubmitMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: { version, action: "submit", conclusion },
      idempotencyKey,
    }),
};
