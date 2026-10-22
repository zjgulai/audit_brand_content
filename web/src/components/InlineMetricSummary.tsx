import StatusBadge from "./StatusBadge";

/**
 * 嵌入式指标摘要与四指标七要素校验条（#129 / TS-26）。
 *
 * 规则（UIUX §7.2 / Playbook TS-26 / 验收表 #129）：
 *   1. 阶段一**禁止独立指标看板（metrics dashboard）路由或页面**；
 *   2. 案件页（CaseDetailPage）、队列页（QueuePage）、报告页（ReportPage）各有且仅有
 *      「必要计数（counts）+ 趋势摘要（trend）+ 未测/样本不足（untested/insufficient_n）」三类显示元素；
 *   3. 当任何页面展示四指标输出（`recall_l4_l5` / `false_positive_l4_l5` / `uncovered_ratio` /
 *      `human_overturn_rate`）时，必须通过 `validateMetricSevenElements()` 逐项校验七要素
 *      （`numerator` / `denominator` / `window` / `sampling_layer` / `min_n` / `status` / `target`）：
 *      - 缺任一要素（哪怕带了 `chart` / `sparkline` 图表数据）→ 立即判为**不可用（invalid）**，绝不因画得好看而算数！
 *      - `status === "未测"` 时精确渲染「未测」，严禁渲染为 `0`、`0%`、`N/A` 或空白；
 *      - `status === "样本不足"`（`n < min_n`）时精确渲染「样本不足（n=…）」且不显示比率。
 */

export const SEVEN_METRIC_KEYS = [
  "numerator",
  "denominator",
  "window",
  "sampling_layer",
  "min_n",
  "status",
  "target",
] as const;

export interface MetricItem {
  id?: string;
  name?: string;
  numerator?: number | null;
  denominator?: number | null;
  n?: number | null;
  ratio?: number | null;
  window?: string | null;
  sampling_layer?: string | string[] | null;
  min_n?: number | null;
  status?: "ok" | "未测" | "样本不足" | string | null;
  target?: number | string | null;
  target_status?: string | null;
}

export interface MetricValidationResult {
  valid: boolean;
  missingKeys: string[];
  displayStatus: "ok" | "未测" | "样本不足" | "不可用";
  displayValue: string;
  reason?: string;
}

export function validateMetricSevenElements(
  metric: Record<string, unknown> | null | undefined,
): MetricValidationResult {
  if (!metric || typeof metric !== "object") {
    return {
      valid: false,
      missingKeys: [...SEVEN_METRIC_KEYS],
      displayStatus: "未测",
      displayValue: "未测",
      reason: "指标对象为空",
    };
  }

  const missingKeys: string[] = [];
  for (const k of SEVEN_METRIC_KEYS) {
    if (!(k in metric)) {
      missingKeys.push(k);
    }
  }

  // window、sampling_layer、min_n、status 必须有非空定义（即使带了 chart 图表，缺任一七要素也必须标为不可用）
  const win = metric.window;
  const layer = metric.sampling_layer;
  const minN = metric.min_n;
  const status = metric.status;

  if (typeof minN !== "number" || Number.isNaN(minN) || minN < 1) {
    if (!missingKeys.includes("min_n")) missingKeys.push("min_n");
  }
  if (
    layer === null ||
    layer === undefined ||
    (typeof layer === "string" && !layer.trim()) ||
    (Array.isArray(layer) && layer.length === 0)
  ) {
    if (!missingKeys.includes("sampling_layer")) {
      missingKeys.push("sampling_layer");
    }
  }
  if (typeof status !== "string" || !status.trim()) {
    if (!missingKeys.includes("status")) missingKeys.push("status");
  }

  if (missingKeys.length > 0) {
    return {
      valid: false,
      missingKeys,
      displayStatus: "不可用",
      displayValue: "不可用（七要素不全）",
      reason: `缺少七要素字段：${missingKeys.join(", ")}`,
    };
  }

  if (status === "未测" || win === null || win === undefined || String(win).trim() === "") {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "未测",
      displayValue: "未测",
    };
  }

  const num = typeof metric.numerator === "number" ? metric.numerator : null;
  const den = typeof metric.denominator === "number" ? metric.denominator : null;

  if (status === "样本不足" || (den !== null && den < (minN as number))) {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "样本不足",
      displayValue: `样本不足（n=${den ?? 0} < min_n=${String(minN)}）`,
    };
  }

  if (num === null || den === null || den <= 0) {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "未测",
      displayValue: "未测",
    };
  }

  const pct = ((num / den) * 100).toFixed(1);
  return {
    valid: true,
    missingKeys: [],
    displayStatus: "ok",
    displayValue: `${pct}%（n=${num}/${den}）`,
  };
}

export interface InlineMetricSummaryProps {
  scope: "queue" | "case" | "report";
  countsLabel: string;
  trendLabel?: string | null;
  untestedLabel?: string | null;
}

/**
 * 嵌入在队列页 / 案件页 / 报告页顶部的紧凑三元指标条：
 * 严格只包含 ① 必要计数（counts）· ② 趋势摘要（trend）· ③ 未测/样本不足状态（untested）。
 */
export default function InlineMetricSummary({
  scope,
  countsLabel,
  trendLabel,
  untestedLabel,
}: InlineMetricSummaryProps) {
  return (
    <div
      className="sample-banner"
      data-inline-metrics={scope}
      role="region"
      aria-label={`${scope} 必要计数与未测摘要`}
    >
      <span data-metric-counts="">
        <strong>必要计数：</strong>
        <span className="font-data">{countsLabel}</span>
      </span>
      <span data-metric-trend="">
        <strong>趋势摘要：</strong>
        <span>{trendLabel && trendLabel.trim() ? trendLabel : "未测（待周期基线）"}</span>
      </span>
      <span data-metric-untested="">
        <strong>未测 / 样本状态：</strong>
        <StatusBadge
          axis="coverage"
          value={untestedLabel && untestedLabel.trim() ? untestedLabel : "未测"}
        />
      </span>
    </div>
  );
}
