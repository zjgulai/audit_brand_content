import { request } from "./client";

/**
 * 签发与撤回专属客户端（G-1 / Wave D 落 G-05 决策）。
 *
 * ★ 门禁契约（A4 & check_production_bundle.mjs）：
 *   1. 全前端只有本模块允许发起 `/release-decision` 与 `/release-revoke` 请求；
 *   2. 每次调用必须显式传入非空 `stepUpToken`、`nonce` 与 `reason`（满足 AU-13 / AU-14 / AU-20）。
 */

export interface ReleaseReadiness {
  ready?: boolean;
  label?: string;
  checks?: Record<string, boolean>;
  missing?: string[];
  obligations?: string[];
  binding_preview?: Record<string, unknown>;
}

export interface ReleasePendingItem {
  case_id: string;
  tenant?: string;
  product_line?: string;
  state?: string;
  release_status?: string;
  submitter_id?: string | null;
  final_reviewer_id?: string | null;
  case_version?: number;
  ir_id?: string;
}

export const releaseClient = {
  listPending: () => request<ReleasePendingItem[]>("/release/pending"),

  getReadiness: (caseId: string) =>
    request<ReleaseReadiness>(
      `/cases/${encodeURIComponent(caseId)}/release-readiness`,
    ),

  decide: (
    caseId: string,
    params: {
      decision: "sign" | "reject";
      version: number;
      stepUpToken: string;
      nonce: string;
      reason: string;
      idempotencyKey: string;
    },
  ) => {
    if (!params.stepUpToken.trim() || !params.nonce.trim()) {
      return Promise.reject(
        new Error("step_up_required: 签发/拒绝必须携带有效的 step_up_token 与 nonce"),
      );
    }
    return request<Record<string, unknown>>(
      `/cases/${encodeURIComponent(caseId)}/release-decision`,
      {
        method: "POST",
        body: {
          decision: params.decision,
          version: params.version,
          step_up_token: params.stepUpToken.trim(),
          nonce: params.nonce.trim(),
          reason: params.reason.trim(),
        },
        idempotencyKey: params.idempotencyKey,
      },
    );
  },

  revoke: (
    caseId: string,
    params: {
      version: number;
      stepUpToken: string;
      nonce: string;
      reason: string;
      idempotencyKey: string;
    },
  ) => {
    if (!params.stepUpToken.trim() || !params.nonce.trim()) {
      return Promise.reject(
        new Error("step_up_required: 撤回签名必须携带有效的 step_up_token 与 nonce"),
      );
    }
    if (!params.reason.trim()) {
      return Promise.reject(
        new Error("missing_reason: 撤回签名必须填写书面理由"),
      );
    }
    return request<Record<string, unknown>>(
      `/cases/${encodeURIComponent(caseId)}/release-revoke`,
      {
        method: "POST",
        body: {
          version: params.version,
          step_up_token: params.stepUpToken.trim(),
          nonce: params.nonce.trim(),
          reason: params.reason.trim(),
        },
        idempotencyKey: params.idempotencyKey,
      },
    );
  },
};
