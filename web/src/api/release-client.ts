import { request, apiBase } from "./client";
import { csrfHeaders } from "./auth-headers";

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

  /**
   * 发起 Step-Up 二次认证重定向。
   *
   * ## 为什么这个方法是裸 `fetch`，而不是走 `request()`
   *
   * `request()` 有三条硬形状，这里三条都不能用：
   *
   * 1. **它强制 `await res.json()`**。而 `/auth/reauth/start` 回的是
   *    **302 RedirectResponse** —— 走封装必然在解析那步抛，异常又被上层
   *    catch 成「功能未开启」，读起来像端点不存在。
   * 2. **它不设 `redirect`**。这里必须 `redirect: "manual"`：默认行为是
   *    **自动跟随** 302 去飞书域名，那是跨域页面，JS 读不到任何东西。
   * 3. 它无法表达「我要的是导航，不是响应体」这个语义。
   *
   * 三条都在 `web/scripts/check_api_centralization.mjs` 的
   * `ALLOWED_BARE_FETCH` 里登记过 —— **这是例外，不是先例**。
   *
   * ## 为什么最终还是搬进了 api 层（2026-11-03）
   *
   * 原先这段裸 `fetch` 写在 `pages/ReleasePage.tsx` 里。虽然检查器放行了它，
   * 但「HTTP 只活在 api 层」是本项目的一条结构约定 —— 页面只该知道
   * 「发起重定向」这件事，不该知道 302、CSRF 头、`redirect: "manual"`。
   * 搬进来之后页面少一个可错的地方：路径与头都在一处。
   *
   * @returns 三种可区分的形状，**不允许合并成 boolean**：
   *   - `{ kind: "redirected" }`  —— 拿到了 3xx/opaqueredirect
   *   - `{ kind: "url", url }`    —— 2xx 且带 authorize_url
   *   - `{ kind: "failed", status, message }` —— 其余，带真实状态码
   */
  startReauth: async (params: {
    caseId: string;
    action: string;
    nonce: string;
  }): Promise<
    | { kind: "redirected" }
    | { kind: "url"; url: string }
    | { kind: "failed"; status: number; message: string }
  > => {
    const res = await fetch(`${apiBase}/reauth/start`, {
      method: "POST",
      credentials: "same-origin",
      // ★ 关键：不跟随。跟了就是跨域页面，读不到 Location。
      redirect: "manual",
      headers: {
        "Content-Type": "application/json",
        ...csrfHeaders("POST", document.cookie),
      },
      body: JSON.stringify({
        case_id: params.caseId,
        action: params.action,
        nonce: params.nonce,
      }),
    });

    // `redirect: "manual"` 下 302 是 opaque 的，读不到 Location。
    // 所以接受两种可读的成功信号：3xx/opaqueredirect，或 2xx 带 authorize_url。
    if (res.type === "opaqueredirect" || (res.status >= 300 && res.status < 400)) {
      return { kind: "redirected" };
    }
    if (res.ok) {
      const data = (await res.json().catch(() => null)) as
        | { authorize_url?: string }
        | null;
      if (data?.authorize_url) return { kind: "url", url: data.authorize_url };
    }
    return {
      kind: "failed",
      status: res.status,
      message: `HTTP ${res.status}`,
    };
  },
};
