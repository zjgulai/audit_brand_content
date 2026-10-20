import {
  request,
  type DraftMutation,
  type LedgerMutation,
  type SubmitMutation,
} from "./client";

/**
 * 人工写动作只在开发验收包中动态导入；生产构建不引用本模块。
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

  saveDraft: (
    caseId: string,
    version: number,
    draft: { form?: unknown; notes?: string; evidence_selections?: unknown[] },
    idempotencyKey: string,
  ) =>
    request<DraftMutation>(`/cases/${encodeURIComponent(caseId)}/actions`, {
      method: "POST",
      body: { version, action: "save_draft", draft },
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
