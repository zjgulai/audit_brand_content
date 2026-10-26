import type { SVGProps } from "react";

/**
 * 唯一图标入口（DT-8）。
 *
 * 规则：
 *   1. 业务组件禁止使用 Unicode 图标字符（← ⚠ ↓）或直接 import lucide-react；
 *   2. 装饰性图标默认输出 aria-hidden="true"；只有显式传入 label 时才作为语义图形；
 *   3. 五标签徽标用不同几何形状区分（AX-10：不只靠颜色）。
 */

export type IconName =
  | "arrow-left"
  | "arrow-down"
  | "arrow-up-right"
  | "alert-triangle"
  | "octagon-x"
  | "check-circle"
  | "clock"
  | "help-circle"
  | "layers"
  | "shield-alert"
  | "sparkles"
  | "bell"
  | "plus"
  | "file-text"
  | "inbox"
  | "search"
  | "history"
  | "user-check"
  | "chevron-left"
  | "chevron-right";

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
  label?: string;
}

export function Icon({ name, size = 12, label, className, ...rest }: IconProps) {
  const a11yProps = label
    ? { role: "img" as const, "aria-label": label }
    : { "aria-hidden": true as const };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ flex: "none", verticalAlign: "-0.125em" }}
      {...a11yProps}
      {...rest}
    >
      {name === "arrow-left" && (
        <>
          <path d="M13 8H3" />
          <path d="M7 4L3 8l4 4" />
        </>
      )}
      {name === "arrow-down" && (
        <>
          <path d="M8 3v10" />
          <path d="M4 9l4 4 4-4" />
        </>
      )}
      {name === "arrow-up-right" && (
        <>
          <path d="M4.5 11.5L11.5 4.5" />
          <path d="M6 4.5h5.5V10" />
        </>
      )}
      {name === "alert-triangle" && (
        <>
          <path d="M8 2.2L14.3 13H1.7L8 2.2z" />
          <path d="M8 6.5v3" />
          <circle cx="8" cy="11.3" r="0.6" fill="currentColor" stroke="none" />
        </>
      )}
      {name === "octagon-x" && (
        <>
          <polygon points="5.2,1.8 10.8,1.8 14.2,5.2 14.2,10.8 10.8,14.2 5.2,14.2 1.8,10.8 1.8,5.2" />
          <path d="M6 6l4 4M10 6l-4 4" />
        </>
      )}
      {name === "check-circle" && (
        <>
          <circle cx="8" cy="8" r="6" />
          <path d="M5.3 8.2l1.9 1.9 3.6-3.8" />
        </>
      )}
      {name === "clock" && (
        <>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 4.8V8l2.3 1.4" />
        </>
      )}
      {name === "help-circle" && (
        <>
          <circle cx="8" cy="8" r="6" strokeDasharray="2.2 1.8" />
          <path d="M6.4 6.3a1.7 1.7 0 0 1 3.1.8c0 1.1-1.5 1.4-1.5 2.3" />
          <circle cx="8" cy="11.6" r="0.6" fill="currentColor" stroke="none" />
        </>
      )}
      {name === "layers" && (
        <>
          <polygon points="8,2 14,5.5 8,9 2,5.5" />
          <path d="M2 8.5L8 12l6-3.5" />
          <path d="M2 11.2L8 14.5l6-3.3" />
        </>
      )}
      {name === "shield-alert" && (
        <>
          <path d="M8 1.8l5.5 2.2v4c0 3.5-2.4 5.4-5.5 6.4-3.1-1-5.5-2.9-5.5-6.4V4L8 1.8z" />
          <path d="M8 5.5v3.2" />
          <circle cx="8" cy="10.8" r="0.6" fill="currentColor" stroke="none" />
        </>
      )}
      {name === "sparkles" && (
        <>
          <path d="M8 2l1.4 3.6L13 7l-3.6 1.4L8 12 6.6 8.4 3 7l3.6-1.4L8 2z" />
        </>
      )}
      {name === "bell" && (
        <>
          <path d="M4 6.5a4 4 0 0 1 8 0c0 3 1.5 4.2 1.5 4.2h-11S4 9.5 4 6.5" />
          <path d="M6.8 13a1.4 1.4 0 0 0 2.4 0" />
        </>
      )}
      {name === "plus" && (
        <>
          <path d="M8 3.2v9.6M3.2 8h9.6" />
        </>
      )}
      {name === "file-text" && (
        <>
          <path d="M9.5 2H4.2a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h7.6a1 1 0 0 0 1-1V5.3L9.5 2z" />
          <path d="M9.2 2v3.5h3.5M5.5 8.5h5M5.5 11h3.5" />
        </>
      )}
      {name === "inbox" && (
        <>
          <path d="M2.2 9h3.2l1.1 1.8h3L10.6 9h3.2" />
          <rect x="2" y="3" width="12" height="10" rx="1.5" />
        </>
      )}
      {name === "search" && (
        <>
          <circle cx="7.2" cy="7.2" r="4.5" />
          <path d="M10.6 10.6L14 14" />
        </>
      )}
      {name === "history" && (
        <>
          <path d="M2.5 8a5.5 5.5 0 1 0 1.3-3.5L2.5 5.8" />
          <path d="M2.5 3v2.8h2.8M8 5.2V8l2 1.2" />
        </>
      )}
      {name === "chevron-left" && (
        <>
          <path d="M10 3.5L5.5 8l4.5 4.5" />
        </>
      )}
      {name === "chevron-right" && (
        <>
          <path d="M6 3.5L10.5 8 6 12.5" />
        </>
      )}
      {name === "user-check" && (
        <>
          <circle cx="6.2" cy="5.2" r="2.5" />
          <path d="M2.2 13c0-2.2 1.8-3.8 4-3.8s4 1.6 4 3.8" />
          <path d="M11 8.5l1.3 1.3 2.5-2.6" />
        </>
      )}
    </svg>
  );
}

export default Icon;
