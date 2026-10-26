import { csrfHeaders, parseCookie } from "./auth-headers";

/**
 * review-api 客户端。
 *
 * 边界（web/README.md，2026-10-20 改定）：
 *   - **不重算判定**：state / coverage / authority / release_status 一律读后端返回。
 *   - **人工动作只经写 API**：claim / unclaim / reassign / save_draft / adopt_draft /
 *     reference_fragment / heartbeat / submit / confirm / reject 只走 api/write_api.py 已挂载的端点。
 *   - **release_status 不在本通用读客户端出现任何可写方法**（A4）。
 */

// ★ 默认 API 前缀必须随构建模式变：生产构建落 `/api/v1`，开发落 `/review-api`。
//
//   为什么要分：`/review-api` 是 **Vite 开发服务器**的代理前缀
//   （`vite.config.ts:66-70` rewrite 到 `/api/v1`）。生产没有那层代理，
//   于是请求落到 SPA 的 `/{full_path:path}` 兜底 —— **返回 index.html 且状态 200**，
//   前端把 HTML 当 JSON 解析，而 `/healthz`、`/readyz`、容器 healthcheck 全绿。
//   实测（2026-10-26，`web/dist` 里能直接读到 `nv="/review-api"`）：
//   `/review-api/cases` → 200 text/html。
//
//   ★ 判据用 `import.meta.env.PROD`（Vite 编译期常量），不用 `MODE`
//     —— 后者可被 `--mode` 改，不是可靠的运行环境判据。
//   ★ 抽成常量而不是内联在 `??` 右边：内联时三元与 `??` 混在一行，
//     读代码的人要多看一眼才知道哪个先算。抽出来两个分支都看得见。
const DEFAULT_API_BASE = import.meta.env.PROD ? "/api/v1" : "/review-api";

export const apiBase = (
  import.meta.env.VITE_REVIEW_API_BASE ?? DEFAULT_API_BASE
).replace(/\/$/, "");

/** 同源开发端点的根；只由开发身份模块使用。 */
export const appOrigin = apiBase.replace(/\/(review-api|api\/v1)$/, "");

/** 五标签。闭集 —— 出现别的值是后端坏了，不是新标签。 */
export const FIVE_LABELS = ["BLOCK", "REVIEW", "未审查", "待自决", "PASS"] as const;
export type Label = (typeof FIVE_LABELS)[number];

/** 队列只允许这两个标签（A1）。 */
export const QUEUE_LABELS: readonly string[] = ["REVIEW", "待自决"];

export interface Me {
  principal: string;
  tenant: string;
  roles: string[];
  product_lines: string[];
}

export interface CaseSummary {
  case_id: string;
  ir_id?: string | null;
  state?: string | null;
  layer?: string | null;
  release_status?: string | null;
  tenant?: string | null;
  product_line?: string | null;
  assignee_id?: string | null;
  sample?: boolean | null;
  entry_channel?: string | null;
  created_at?: string | null;
  title_or_excerpt?: string | null;
  high_severity_count?: number | null;
  coverage_state?: string | null;
}

export interface Finding {
  finding_id: string;
  control_code: string;
  status: string;
  severity: string;
  quote?: string | null;
  location?: { type?: string; start?: number; end?: number } | null;
  authority_state?: string | null;
  authority_ref?: Array<{ ref_id?: string }> | null;
  rule_conflict?: boolean | null;
  resolution_detail?: {
    refs?: Array<Record<string, unknown>>;
    reason?: string | null;
  } | null;
  detected_by?: string | null;
  produced_by?: string | null;
  derived_from?: string | null;
  adjudicated_by?: string | null;
  adjudicated_at?: string | null;
  adjudication_reason?: string | null;
}

export interface NotEvaluated {
  what?: string | null;
  why?: string | null;
  label?: string | null;
}

export interface DraftSnapshot {
  case_id: string;
  draft_id: string;
  snapshot_seq: number;
  snapshot_at: string;
  content_hash: string;
  author: string | null;
  derived_from?: string | null;
  snapshot_kind?: string;
  adopted_at?: string | null;
  form?: Record<string, unknown>;
  notes: string;
  evidence_selections?: unknown[];
  references?: Array<{
    source_draft_id: string;
    field_path: string;
    fragment: unknown;
  }>;
}

export interface FragmentReference {
  case_id: string;
  source_draft_id: string;
  field_path: string;
  fragment: unknown;
  author: string;
  at: string;
}

export interface ReviewSummary {
  case_id: string;
  status: "unassigned" | "claimed" | "released" | "closed" | string;
  assignee: string | null;
  version: number;
  claimed_at: string | null;
  last_activity: string | null;
  lease_expires: number | null;
  released_at: string | null;
  released_draft_id: string | null;
  primary_draft_id: string | null;
  primary_draft?: DraftSnapshot | null;
  drafts?: DraftSnapshot[];
  fragment_references?: FragmentReference[];
}

export interface ContentUnitData {
  unit_id: string;
  kind?: string;
  parse_status?: string;
  failure_kind?: string | null;
  text?: string | null;
  has_text?: boolean;
  fields?: Record<string, unknown> | null;
  textification?: {
    covers?: string[];
    does_not_cover?: string[];
  } | null;
  fingerprint?: {
    raw_sha256?: string;
    text_sha256?: string;
  } | null;
}

export interface CaseDetail {
  case_id: string;
  ir: {
    ir_id: string;
    ir_version: string;
    source_ir_version?: string;
    content_unit_ref?: {
      unit_id: string;
      kind: string;
      parse_status?: string;
      failure_kind?: string | null;
    };
    findings: Finding[];
    decision: {
      state: string;
      layer: string;
      release_status: string;
      obligations?: string[];
    };
    coverage: {
      coverage_state: string;
      modalities_evaluated?: string[];
      rules_version?: string;
      control_points_applied?: string[];
      not_evaluated_reason?: NotEvaluated[];
    };
    receipt_ref?: string;
    rule_snapshot?: string;
    kb_snapshot?: string;
    control_points_version?: string;
    created_at?: string;
  };
  review?: ReviewSummary | null;
  content_unit?: ContentUnitData | null;
}

export interface LedgerMutation {
  version: number;
  status?: string;
  assignee?: string | null;
  lease_expires?: number | null;
  primary_draft_id?: string | null;
}

export interface DraftMutation extends LedgerMutation {
  draft: DraftSnapshot;
  formal?: null;
}

export interface ReferenceMutation extends LedgerMutation {
  reference: FragmentReference;
}

export interface SubmitMutation extends LedgerMutation {
  formal: {
    formal_id: string;
    case_id: string;
    author: string;
    submitted_at: string;
    from_draft_id: string | null;
    conclusion: Record<string, unknown>;
  };
}

export interface ReportSummary {
  report_id: string;
  case_id?: string | null;
  ir_id?: string | null;
  url?: string | null;
  published_at?: string | null;
}

export interface NotificationItem {
  notification_id: string;
  recipient?: string | null;
  tenant?: string;
  type?: string;
  unread?: boolean;
  read_at?: string | null;
  acked_at?: string | null;
  payload?: Record<string, unknown> | null;
}

/** 后端错误体（api/review_api.py 的 _http_error）：{code,message,details,request_id} */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;

  constructor(status: number, body: Record<string, unknown> | null, path: string) {
    const message =
      (body && typeof body.message === "string" && body.message) ||
      `${path} → HTTP ${status}`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = body && typeof body.code === "string" ? body.code : String(status);
    this.requestId =
      body && typeof body.request_id === "string" ? body.request_id : "";
  }
}

/** 读 cookie。`csrf` 是后端在 `/auth/callback` 下发的（httponly=false，专供 JS 读）。 */
export function readCookie(name: string): string | null {
  const jar = typeof document === "undefined" ? null : document.cookie;
  return parseCookie(jar, name);
}

export async function request<T>(
  path: string,
  init?: { method?: string; body?: unknown; idempotencyKey?: string },
): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init?.body !== undefined) headers["Content-Type"] = "application/json";
  if (init?.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;
  Object.assign(headers, csrfHeaders(method, typeof document === "undefined" ? null : document.cookie));

  const res = await fetch(`${apiBase}${path}`, {
    method: init?.method ?? "GET",
    headers,
    // session 走 cookie；必须带上，否则 session_dep 直接 401
    credentials: "same-origin",
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });

  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try {
      body = (await res.json()) as Record<string, unknown>;
    } catch {
      /* 非 JSON 错误体（代理 502 等），保留 status */
    }
    throw new ApiError(res.status, body, path);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * 保证队列里只有 REVIEW / 待自决。
 *
 * 这不是「顺手过滤」—— 它是一个断言：后端若返回了别的标签，就是口径坏了。
 * 在这里静默 filter 掉会让 bug 永远看不见（A1 的反向对照要的就是「它不出现」）。
 * 所以：过滤 + 返回被过滤掉的条目，由页面显示「口径异常」而不是假装没事。
 */
export function splitQueue(rows: CaseSummary[]): {
  queued: CaseSummary[];
  offQueue: CaseSummary[];
} {
  const queued: CaseSummary[] = [];
  const offQueue: CaseSummary[] = [];
  for (const row of rows) {
    if (QUEUE_LABELS.includes(String(row.state ?? ""))) queued.push(row);
    else offQueue.push(row);
  }
  return { queued, offQueue };
}

export const reviewApi = {
  listCases: () => request<CaseSummary[]>("/cases"),

  /** 真正的待办队列（只 REVIEW + 待自决）。见文件头注释。 */
  getQueue: () => request<CaseSummary[]>("/queue"),

  getCase: (caseId: string) =>
    request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`),

  listReports: () => request<ReportSummary[]>("/reports"),

  getReport: (reportId: string) =>
    request<ReportSummary>(`/reports/${encodeURIComponent(reportId)}`),

  listNotifications: () => request<NotificationItem[]>("/notifications"),

  /** 当前登录主体（生产）。未登录 → 401。 */
  me: () => request<Me>("/me"),

  /** 登出：POST（带 CSRF），后端撤销 session 并清 cookie。 */
  logout: () => request<{ logged_out: boolean }>("/logout", { method: "POST" }),
};
