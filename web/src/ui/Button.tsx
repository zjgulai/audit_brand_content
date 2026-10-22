import type { ButtonHTMLAttributes } from "react";

/**
 * 统一按钮原语（DT-6 执行点）。
 *
 * 纪律（web/DESIGN.md §7 / 方案 §5.6）：
 *   1. 默认 variant 为 "secondary"（中性底，高对比边框 --input）；
 *   2. variant="primary"（品牌酒红 #6A2C3A）只允许用于人要做的高风险终结动作
 *      （submit / release-decision），且调用处必须显式声明 data-risk-action="submit|release-decision"。
 *      普通操作（如「认领」「存草稿」「查找」）严禁使用 primary。
 */

export type ButtonVariant = "secondary" | "primary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  "data-risk-action"?: string;
}

export function Button({
  variant = "secondary",
  className = "",
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const variantClass =
    variant === "primary"
      ? "btn btn--primary"
      : variant === "danger"
        ? "btn btn--danger"
        : variant === "ghost"
          ? "btn btn--ghost"
          : "btn";
  const merged = className ? `${variantClass} ${className}` : variantClass;

  return (
    <button type={type} className={merged} {...rest}>
      {children}
    </button>
  );
}

export default Button;
