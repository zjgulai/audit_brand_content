import { request } from "./client";

/**
 * 治理类只读/写入端点（ADR-0021 · W-1）。
 *
 * ## 它为什么存在
 *
 * 2026-10-27 审计：`pages/` 下有 **18 处裸 `request()`**，与 `api/client.ts`
 * 的封装并存。于是同一个接口可以在两处拼 URL（一处写对、一处写错就 404），
 * 而没有任何东西会发现。
 *
 * 这 18 处不是「风格不统一」这么轻：`ReleasePage` 那处是**裸 `fetch`**
 * （连 CSRF 头都没带），而 `POST /auth/reauth/start` 的路径还写错了
 * （后端是 `/api/v1/reauth/start`）。见 `release-client.ts` 里那条注释。
 *
 * ## 口径
 *
 * · 只搬不改语义 —— 搬完之后行为必须逐字相同，否则就不是重构是改需求。
 * · 写动作一律要求显式 `idempotencyKey`：只有页面知道「这是不是同一次意图的重试」。
 *   这里不偷偷生成 key（与 `write-client.ts` 同一条）。
 * · 每个方法的返回类型**必须写出来**。裸 `request<Record<string, unknown>>`
 *   等于把「后端回了什么」这个问题的答案留给运行时。
 */

/** 授权治理：signer / takedown 两类，形状相同，只有 capability 取值域不同。 */
export type GrantKind = "signer" | "takedown";

/**
 * 授权行。★ 字段全可选 —— 后端在不同状态下给的不一样，而**缺值必须由界面
 * 显示成「未测」**（见 `ui/FieldState.tsx`），不许兜底。
 *
 * ★ 从 `pages/AdminGrantsPage.tsx` 搬来这里，**只此一份** —— 两处各写一个
 * 同名接口，字段迟早会不一样（AGENTS.md §2.4.8）。
 */
export interface GrantRecord {
  grant_id?: string;
  id?: string;
  tenant?: string;
  product_line?: string;
  platform?: string;
  user_id?: string;
  capability?: string;
  status?: string;
  // T-314d：三态走 state（reducer 的真相源）；status 仅为旧数据兜底。
  state?: "proposed" | "executed" | "approved" | "revoked" | string;
  proposed_at?: string;
  executed_at?: string;
  approved_at?: string;
  revoked_by?: string;
  revoked_at?: string;
  revoke_reason?: string;
  proposed_by?: string;
  executed_by?: string;
  approved_by?: string;
  reason?: string;
}
export interface ProposeGrantBody {
  user_id: string;
  capability: string;
  product_line: string;
  /** 只有 takedown 才带 platform。 */
  platform?: string;
  reason: string;
}

/** 授权治理写动作的两种**二步流转**（三权分立）：执行 → 审批。 */
export type GrantTransition = "execute" | "approve";

function grantsPath(kind: GrantKind): string {
  // ★ 逐字拼在这里，**不在页面里拼** —— 两处拼就会有一处写错的机会。
  return kind === "signer" ? "/admin/signer-grants" : "/admin/takedown-grants";
}

export const adminApi = {
  listGrants: (kind: GrantKind) => request<GrantRecord[]>(grantsPath(kind)),

  proposeGrant: (kind: GrantKind, body: ProposeGrantBody, idempotencyKey: string) =>
    request<GrantRecord>(grantsPath(kind), {
      method: "POST",
      body,
      idempotencyKey,
    }),

  transitionGrant: (
    grantId: string,
    action: GrantTransition,
    idempotencyKey: string,
  ) =>
    request<GrantRecord>(
      `/admin/grants/${encodeURIComponent(grantId)}/${action}`,
      { method: "POST", body: {}, idempotencyKey },
    ),

  /** 会话与安全审计。★ 后端返回的是**原始 dict 列表**，不保证形状；
   *  这正是不许在页面里 `JSON.stringify` 就完事的原因（见 C 级页面待办）。 */
  listSessions: () => request<Array<Record<string, unknown>>>("/admin/sessions"),
};

/** 下线任务。★ `metrics` 与 `tasks` 同在一个响应里，不许只取 `tasks`。 */
export interface TakedownMetrics {
  open_count?: number;
  oldest_age_days?: number;
  /** ★ T-312d：年龄一律读 `metrics.ages`，不从 task 上算。
   *  两个字段都写实：`task_id` 是 join 键，`age_days` 是要显示的读数。 */
  ages?: Array<{ task_id: string; age_days: number }>;
}

/**
 * 下线任务。★ 从 `pages/TakedownPage.tsx` 搬来，**只此一份** ——
 * 两处各写一个同名接口，字段迟早不一样（AGENTS.md §2.4.8）。
 *
 * ★ `tenant` 是可选且可为 null —— 缺值时界面必须显示「未测」，
 *   **不许**兜底成 "t1"（t1 是真实租户号格式，见 `ui/FieldState.tsx`）。
 */
export interface TakedownTaskItem {
  task_id: string;
  case_id: string;
  platform: string;
  tenant?: string;
  product_line?: string;
  assignee?: string | null;
  state: "pending" | "in_progress" | "completed" | "failed" | "waived" | string;
  created_at?: string;
  reminder_count?: number;
  last_reminded_at?: string | null;
  version?: number;
  evidence?: Record<string, unknown> | null;
  waived?: Record<string, unknown> | null;
}
export interface TakedownList {
  tasks: TakedownTaskItem[];
  metrics?: TakedownMetrics;
}

/** 下线任务的六个流转。★ 全部要求 idempotencyKey。 */
export type TakedownAction =
  | "start"
  | "fail"
  | "retry"
  | "complete"
  | "waive"
  | "reassign";

export const takedownApi = {
  list: () => request<TakedownList>("/takedown-tasks"),

  act: (
    taskId: string,
    action: TakedownAction,
    body: Record<string, unknown>,
    idempotencyKey: string,
  ) =>
    request<TakedownTaskItem>(
      `/takedown-tasks/${encodeURIComponent(taskId)}/${action}`,
      { method: "POST", body, idempotencyKey },
    ),
};
