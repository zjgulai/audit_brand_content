import Icon, { type IconName } from "../ui/icon";

/**
 * 状态四轴统一徽标组件（修 D-01 / D-02 / D-03 / D-13，满足断言 A2 / A6 / AX-10）。
 *
 * 四轴正交语义：
 *   1. decision（五标签）：BLOCK / REVIEW / PASS / 待自决 / 未审查 / 未测（缺值绝不折叠成 —）
 *   2. coverage（覆盖证明）：仅显式 "full" 才使用 pass 绿；"partial" 用 warn；其余（not_evaluated / 缺失）一律用 untested 紫/灰，严禁默认 pass！
 *   3. authority（依据核验）：缺失（null/undefined/""）一律渲染为 "未测"，严禁默认 "ok"（可核）！
 *   4. severity（严重度 L0–L5）：L4/L5 高危用 bad，L2/L3 用 warn，L0/L1 用 muted，与覆盖 partial 视觉分离。
 *
 * 所有状态徽标均输出 `data-status-badge` 供 A6 门禁扫描 DOM 计算样式（绝不使用品牌红 #6A2C3A），
 * 且每个五标签附带不同几何形状 SVG 图标（满足 WCAG AX-10 不只靠颜色区分）。
 */

export function resolveDecisionBadge(state: string | null | undefined): {
  cls: string;
  text: string;
  icon: IconName;
} {
  switch (state) {
    case "BLOCK":
      return { cls: "badge badge--block", text: "违规拦截", icon: "octagon-x" };
    case "REVIEW":
      return { cls: "badge badge--review", text: "待人工复核", icon: "alert-triangle" };
    case "PASS":
      return { cls: "badge badge--pass", text: "审核通过", icon: "check-circle" };
    case "待自决":
      return { cls: "badge badge--pending", text: "品牌自决", icon: "clock" };
    case "未审查":
      return { cls: "badge badge--untested", text: "待检测", icon: "help-circle" };
    default:
      // ★ 断言 A2：未测是独立状态，不许折叠成「—」或空
      return { cls: "badge badge--untested", text: "未测", icon: "help-circle" };
  }
}

export function resolveCoverageBadge(coverageState: string | null | undefined): {
  cls: string;
  text: string;
  icon: IconName;
  isPartial: boolean;
} {
  if (coverageState === "full") {
    return { cls: "badge badge--pass", text: "全规则覆盖", icon: "check-circle", isPartial: false };
  }
  if (coverageState === "partial") {
    return { cls: "badge badge--partial", text: "部分规则覆盖", icon: "layers", isPartial: true };
  }
  if (coverageState === "not_evaluated") {
    return { cls: "badge badge--untested", text: "尚未评估", icon: "help-circle", isPartial: false };
  }
  return {
    cls: "badge badge--untested",
    text: coverageState && coverageState.trim() ? coverageState : "未测",
    icon: "help-circle",
    isPartial: false,
  };
}

export function resolveAuthorityState(authorityState: string | null | undefined): {
  key: "ok" | "expired" | "missing" | "conflict" | "untested";
  text: string;
  cls: string;
} {
  if (authorityState === null || authorityState === undefined || authorityState.trim() === "") {
    // ★ 修 D-01 / 断言 A2d：缺失绝不能默认 "ok"（可核），必须明说「未测」
    return { key: "untested", text: "未测", cls: "badge badge--untested" };
  }
  switch (authorityState) {
    case "ok":
      return { key: "ok", text: "可核", cls: "badge badge--pass" };
    case "expired":
      return { key: "expired", text: "依据已过期", cls: "badge badge--warn" };
    case "missing":
      return { key: "missing", text: "依据缺失", cls: "badge badge--block" };
    case "conflict":
      return { key: "conflict", text: "依据冲突", cls: "badge badge--block" };
    default:
      return { key: "untested", text: authorityState, cls: "badge badge--untested" };
  }
}

export function resolveSeverityBadge(severity: string | null | undefined): {
  cls: string;
  text: string;
  icon: IconName;
} {
  const s = (severity ?? "").trim().toUpperCase();
  if (s === "L4" || s === "L5") {
    return { cls: "badge badge--severity-high", text: `${s} 极高危`, icon: "shield-alert" };
  }
  if (s === "L2" || s === "L3") {
    return { cls: "badge badge--severity-med", text: `${s} 中风险`, icon: "alert-triangle" };
  }
  if (s === "L0" || s === "L1") {
    return { cls: "badge badge--sample", text: `${s} 低风险`, icon: "layers" };
  }
  return { cls: "badge badge--untested", text: s || "未测", icon: "help-circle" };
}

export interface StatusBadgeProps {
  axis?: "decision" | "coverage" | "authority" | "severity" | "sample";
  value: string | null | undefined;
}

export function StatusBadge({ axis = "decision", value }: StatusBadgeProps) {
  if (axis === "sample") {
    return (
      <span className="badge badge--sample" data-status-badge="">
        <Icon name="sparkles" size={11} />
        <span>{value || "样例数据"}</span>
      </span>
    );
  }
  if (axis === "coverage") {
    const cov = resolveCoverageBadge(value);
    return (
      <span className={cov.cls} data-status-badge="">
        <Icon name={cov.icon} size={11} />
        <span>{cov.text}</span>
      </span>
    );
  }
  if (axis === "authority") {
    const auth = resolveAuthorityState(value);
    return (
      <span className={auth.cls} data-status-badge="">
        <span>{auth.text}</span>
      </span>
    );
  }
  if (axis === "severity") {
    const sev = resolveSeverityBadge(value);
    return (
      <span className={sev.cls} data-status-badge="">
        <Icon name={sev.icon} size={11} />
        <span>{sev.text}</span>
      </span>
    );
  }
  const dec = resolveDecisionBadge(value);
  return (
    <span className={dec.cls} data-status-badge="">
      <Icon name={dec.icon} size={11} />
      <span>{dec.text}</span>
    </span>
  );
}

export default StatusBadge;
