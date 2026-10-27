import type { ReactNode } from "react";
import { fieldStateKind, fieldStateText, type FieldStateInput } from "./fieldState.logic";

/**
 * 文本字段的三态展示（ADR-0021 · W-2）。
 *
 * ## 它为什么存在
 *
 * 2026-10-27 审计实测：界面把「缺失」渲染成「确定状态」共六处，
 * 它们本该是同一个病 —— 缺值被兜底成一个看起来正常的值：
 *
 *   ContentUnitViewer.tsx:116   parse_status ?? "ok"      → 没解析的图显示「已提取正文」
 *   AdminGrantsPage.tsx:330     product_line ?? "all"     → all 是**权限语义**
 *   AdminGrantsPage.tsx:338     徽标 ?? "active"           → 任何状态都长成「待定」
 *   TakedownPage.tsx:543        tenant ?? "t1"            → t1 是真实租户号格式
 *   ReleasePage.tsx:205         submitter_id: null 写死    → 自签检查恒 false
 *   ReleasePage.tsx:278-280     三元两分支文案相同          → 死分支
 *
 * 分散改六次，下次加第七处还会错。所以这里放**唯一**的正确写法。
 *
 * ## 逻辑在 `fieldState.logic.ts`
 *
 * 三态的判定与文案在纯逻辑文件里 —— 那样自证脚本能 import **真身**去测
 * （Node 的 `--experimental-strip-types` 加载不了 JSX）。本文件只负责挂 class。
 *
 * ## 不许做的事
 *
 * 本组件**不接受** `fallback` 之类的默认值参数。加了它就等于把这个病重新引进来。
 * 需要「缺失时显示别的」只有一个合法理由：那个值有**独立的数据来源** ——
 * 那种情况走 `emptyText`，且它只能是明确表示缺失的词。
 */

export interface FieldStateProps extends FieldStateInput {
  className?: string;
}

export default function FieldState(props: FieldStateProps): ReactNode {
  const kind = fieldStateKind(props.value, props.unreadableReason);
  const text = fieldStateText(props);
  // ★ 三态各自的类名不同 —— 让「未测 / 读不出」在视觉上也分得开，
  //   而不是只靠文字。`data-field-state` 供门禁扫描 DOM。
  const cls =
    kind === "ok"
      ? "field-state"
      : kind === "unreadable"
        ? "field-state field-state--unreadable"
        : "field-state field-state--missing";
  return (
    <span
      className={[cls, props.className].filter(Boolean).join(" ")}
      data-field-state={kind}
    >
      {text}
    </span>
  );
}
