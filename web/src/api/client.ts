/**
 * review-api 只读客户端（阶段一 Web 只读）。
 *
 * - 基址由 VITE_REVIEW_API_BASE 注入，默认同源 /review-api。
 * - **只允许 GET**：这里没有 POST/PUT/PATCH/DELETE，也不暴露 release/签发接口。
 * - 不重算判定、不写权威；页面只展示后端返回。
 */

export const apiBase = (
  import.meta.env.VITE_REVIEW_API_BASE ?? "/review-api"
).replace(/\/$/, "");

export interface CaseSummary {
  case_id: string;
  ir_id?: string | null;
  state?: string | null;
  layer?: string | null;
  release_status?: string | null;
  tenant?: string | null;
  product_line?: string | null;
  assignee_id?: string | null;
}

export interface Finding {
  finding_id: string;
  control_code: string;
  status: string;
  severity: string;
  quote?: string | null;
  authority_state?: string | null;
  detected_by?: string | null;
}

export interface CaseDetail {
  case_id: string;
  ir: {
    ir_id: string;
    ir_version: string;
    source_ir_version?: string;
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
    };
    receipt_ref?: string;
    created_at?: string;
  };
  review?: Record<string, unknown> | null;
}

export interface ReportSummary {
  report_id: string;
  case_id?: string | null;
  ir_id?: string | null;
  url?: string | null;
  published_at?: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`${path} → HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const reviewApi = {
  listCases: () => getJson<CaseSummary[]>("/cases"),
  getQueue: () => getJson<CaseSummary[]>("/queue"),
  getCase: (caseId: string) =>
    getJson<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`),
  listReports: () => getJson<ReportSummary[]>("/reports"),
  getReport: (reportId: string) =>
    getJson<ReportSummary>(`/reports/${encodeURIComponent(reportId)}`),
};
