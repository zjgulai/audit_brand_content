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
/** `POST /submissions` 的响应。
 *
 *  ★ `case_id` 是**分支依据**：有它 → 显示真判定（内嵌 CaseDetailPage）；
 *    没有它（如 501 未开写库）→ 显示本地预检。所以它必须是可选且显式的，
 *    不许用 `Record<string, unknown>` 糊过去。
 */
export interface SubmitResult {
  case_id?: string;
  submission_id?: string;
  http_status?: number;
  replayed?: boolean;
  authority_snapshot?: Record<string, unknown>;
  reconcile_token?: string;
  result?: Record<string, unknown>;
  [k: string]: unknown;
}

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

  /**
   * 内容入库（提交送审）。
   *
   * ★ 原本是 SubmitPage 里的一处裸 `request<Record<string, unknown>>("/submissions")`。
   *   搬进来的同时**把返回类型从 `Record<string, unknown>` 收紧**成
   *   `SubmitResult` —— 页面拿它读 `case_id` 来决定「显示真判定还是本地预检」，
   *   而 `Record<string, unknown>` 让这个判断在类型层面完全不受保护。
   */
  submit: (body: Record<string, unknown>, idempotencyKey: string) =>
    request<SubmitResult>("/submissions", {
      method: "POST",
      body,
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
