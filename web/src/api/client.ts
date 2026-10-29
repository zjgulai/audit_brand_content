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
  // T-439：L1 多模态观察（与报告里「画面语义（候选 · 待人工确认）」同源）。
  // ★ 三态必须能分开：ok=看到了 / untested=没测成 / error=测了但失败。
  //   空数组 + note 才是「没看，原因是 note」。
  multimodal_observations?: MultimodalObservation[];
  multimodal_note?: string | null;
  /** T-451：工作流耗时读数（判定时冻结，接口不另算）。
   *  ★ `null` 表示**没测成**，不许渲染成 0ms —— 「没测」与「跑得极快」
   *    在界面上必须长得不一样（AGENTS.md §2.4.1）。 */
  workflow_timing?: WorkflowTiming | null;
  /** T-455：内容阶段的推断观察。三态原样，**不压成布尔**。 */
  intent_inference?: IntentInference | null;
  /** 判定回执里**报告要用的那几段**（后端逐字段点名透出，不是整份回执）。
   *  ★ 没有它就是「这份案件没留回执」，与「回执里字段为空」不同。 */
  receipt?: JudgmentReceipt | null;
}

/** T-451：工作流耗时。键的形状与报告「执行回执」那一行同源。 */
export interface WorkflowTiming {
  status: "ok" | "untested" | string;
  /** `untested` 时点名原因；`ok` 时为空串。 */
  reason?: string;
  /** 各步 `duration_ms` 求和。**没有读数时是 null，不是 0。** */
  total_ms?: number | null;
  step_count?: number;
  /** 降序，最多三步。 */
  slowest?: Array<{ name: string; duration_ms: number }>;
  source?: string;
}

/** T-455：内容阶段推断。三态 —— `inferred` / `untested` / `absent`。
 *
 *  ★ 为什么不是 `boolean`：`untested`（没有可推断的信号）与
 *    `absent`（调用方已明确给出，无需推断）对审核员含义完全不同 ——
 *    前者要说「判断不出来」，后者什么都不用说。压成 false 就把两者混了。
 */
export interface IntentInference {
  status: "inferred" | "untested" | "absent" | string;
  value?: string | null;
  declared?: string | null;
  confidence?: "high" | "low" | null;
  agrees_with_declared?: boolean | null;
  evidence?: Array<{ pattern?: string; hit?: string; why?: string }>;
  reason?: string;
  /** 判据版本，便于回溯「当时按什么规则推的」。 */
  判据?: string;
}

/** 判定回执里透出的几段。★ 后端逐个点名字段，这里跟着点。 */
export interface JudgmentReceipt {
  skill?: string;
  steps?: unknown[];
  workflow_timing?: WorkflowTiming;
  skipped?: unknown;
  source?: unknown;
}

/** T-439：一条 L1 观察。★ 它不是 finding —— 没有 control_code / authority_ref，
 *  所以界面上一律标「候选 · 待人工确认」，不许渲染成已确认的违规。 */
export interface MultimodalObservation {
  status: "ok" | "untested" | "error";
  task: string;
  statement?: string;
  reason?: string;
  model?: string | null;
  model_version?: string | null;
  ts?: string | null;
  bbox?: string | null;
  confidence?: number | null;
  egress_status?: string;
  created_at?: string;
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

  return readResponse<T>(res, path);
}

/**
 * 上传原始字节（`POST /api/v1/uploads`）。
 *
 * ## 为什么不复用 `request()`
 *
 * `request()` 强制 `JSON.stringify(body)` 且强制 `Content-Type: application/json`。
 * 上传要的是**文件原始字节**，文件名走 `X-Filename` 头 —— 后端就是这么设计的
 * （`api/write_api.py` 的上传端点：不引入 python-multipart，所以不是 multipart，
 * 而是裸字节 + 头）。用 `request()` 表达不了。
 *
 * ## ★ 这不是「新增一处裸 fetch」的借口
 *
 * 它写在 `api/client.ts` 里，是**封装的一部分**，不是页面里的裸调用 ——
 * `check_api_centralization.mjs` 的 A 段只扫 `pages/`，而 D 段要求
 * `/uploads` 这个路径在 `pages/` 里出现 0 次。两段都仍然成立。
 *
 * ★ 响应解析与 `request()` 共用 `readResponse()` —— 否则错误体翻译
 *   会长出第二份，而两份的差别通常只在某一边忘了读 `code`。
 */
export async function uploadBytes<T>(
  path: string,
  file: Blob,
  filename: string,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/octet-stream",
    "X-Filename": filename,
  };
  Object.assign(headers, csrfHeaders("POST", typeof document === "undefined" ? null : document.cookie));

  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers,
    credentials: "same-origin",
    body: file,
  });

  return readResponse<T>(res, path);
}

/** 响应 → JSON 或抛 `ApiError`。`request` 与 `uploadBytes` 的唯一解析点。 */
async function readResponse<T>(res: Response, path: string): Promise<T> {
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

/** 申诉。★ 六个时间字段前端一个都没渲染（ADR-0021 C 级待办），
 *  但类型要留着 —— 删掉类型会让「有哪些状态可读」这件事消失。 */
export interface AppealItem {
  appeal_id: string;
  case_id: string;
  appellant: string;
  reason: string;
  state:
    | "open"
    | "paused_version_invalidated"
    | "migrated"
    | "stale"
    | "withdrawn"
    | "resolved"
    | string;
  opened_at?: string;
  paused_at?: string | null;
  pause_reason?: string | null;
  migrated_at?: string | null;
  stale_at?: string | null;
  withdrawn_at?: string | null;
  withdraw_reason?: string | null;
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

  /**
   * 账号密码登录（★ 仅测试便利，委托方 2026-10-29 要求开启）。
   *
   * ## 为什么不走 `request()`
   *
   * `request()` 会先算 CSRF 头（`csrfHeaders`）。而登录**还没有 session**，
   * 也就没有 csrf cookie —— 那一步会拿空值算出一个头，后端虽放行
   * （`/auth/password` 在中间件白名单里），但读起来像是「登录要求 CSRF」，
   * 下一个改这块的人会照着它去加页面级 csrf 初始化，**多绕一圈**。
   *
   * 这里直接 fetch，语义就是「登录前的裸请求」。
   *
   * ★ 后端未启用该通道时返 **404**（不是 403）。调用方据此区分
   *   「这个部署不支持密码登录」与「密码错了」—— 两者提示完全不同。
   */
  async passwordLogin(username: string, password: string): Promise<{ ok: boolean; principal: string }> {
    const res = await fetch(`${apiBase}/auth/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      let body: Record<string, unknown> | null = null;
      try {
        body = (await res.json()) as Record<string, unknown>;
      } catch {
        /* 非 JSON 错误体：交给 ApiError 用状态码兜底 */
      }
      throw new ApiError(res.status, body, "/auth/password");
    }
    return res.json();
  },

  // ── 以下为 ADR-0021 · W-1 收纳的裸调用 ────────────────────────────────
  //
  // ★ 这些方法原本散在 12 个页面的 `request(...)` 里。搬进来**只搬不改语义**，
  //   目的是让「路径」只在 `api/` 下出现一次 —— 两处拼 URL 就有一处写错的机会。

  /** 申诉列表。 */
  listAppeals: () => request<AppealItem[]>("/appeals"),

  /** 发起申诉。 */
  createAppeal: (body: { case_id: string; reason: string }, idempotencyKey: string) =>
    request<AppealItem>("/appeals", { method: "POST", body, idempotencyKey }),

  /** 原申诉人确认迁移。 */
  migrateAppeal: (appealId: string, idempotencyKey: string) =>
    request<AppealItem>(`/appeals/${encodeURIComponent(appealId)}/migrate`, {
      method: "POST",
      body: {},
      idempotencyKey,
    }),

  /** 撤销申诉（需理由）。 */
  withdrawAppeal: (appealId: string, reason: string, idempotencyKey: string) =>
    request<AppealItem>(`/appeals/${encodeURIComponent(appealId)}/withdraw`, {
      method: "POST",
      body: { reason },
      idempotencyKey,
    }),

  /** 规则库（只读投影）。★ 响应是原始行，形状未定 —— 见 W-2 的三态口径。 */
  listRules: () => request<Array<Record<string, unknown>>>("/rules"),

  /** 控制点（只读投影）。 */
  listControlPoints: () => request<Array<Record<string, unknown>>>("/control-points"),

  /** 处置路由表（只读投影）。 */
  listRouting: () => request<Array<Record<string, unknown>>>("/routing"),

  /**
   * 通知标已读 / 已确认。
   *
   * ★ body **必须带 `notification_id`** —— 后端 `NotificationItemBody` 把它列为必填
   *   （`api/write_api.py` 的 `_notification_command`）。改前页面发的是 `body: {}`，
   *   于是每次点「标记已读」都拿到 **422**，而页面把非 501 的失败吞进 catch 后
   *   **什么都没变**：通知还是未读、也没有报错条，读起来像「按钮没反应」。
   *   这是浏览器联调抓到的第一个真实接线缺陷。
   */
  markNotification: (
    notificationId: string,
    kind: "read" | "ack",
    idempotencyKey: string,
  ) =>
    request<Record<string, unknown>>(
      `/notifications/${encodeURIComponent(notificationId)}/${kind}`,
      { method: "POST", body: { notification_id: notificationId }, idempotencyKey },
    ),

  /** 重签报告：返回新链接（旧链接作废）。 */
  resignReport: (reportId: string, idempotencyKey: string) =>
    request<ReportSummary>(`/reports/${encodeURIComponent(reportId)}/resign`, {
      method: "POST",
      body: {},
      idempotencyKey,
    }),
};
