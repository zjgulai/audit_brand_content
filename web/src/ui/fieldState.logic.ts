/**
 * fieldState.logic.ts —— 文本字段三态的**纯逻辑**（ADR-0021 · W-2）
 *
 * ★ 为什么从 `FieldState.tsx` 里抽出来：
 *   自证脚本 `web/scripts/check_field_state.mjs` 要测的正是这两个函数。
 *   若它们和 JSX 待在同一个 `.tsx` 里，脚本就只能「用正则从源码里抠函数体
 *   再 eval」—— 那条路我试过一次，可选链直接把 eval 打挂了，而且抠出来的
 *   是**一段文本**，不是被 TS 检查过的真身。
 *
 *   抽成 `.ts` 之后，Node 24 的 `--experimental-strip-types` 能直接 import，
 *   测的就是真源码。**测真身，不是测副本。**
 *
 * ★ 这个文件里**不许出现任何 JSX** —— 一出现就不能被 strip-types 加载了。
 */

/** 三态。 */
export type FieldStateKind = "ok" | "missing" | "unreadable";

export interface FieldStateInput {
  /** 字段值。null / undefined / 空串 / 全空白 都算 missing。 */
  value?: string | number | null;
  /** 字段名，用于「阶段：未测」这种带名称的展示。留空则只输出值本身。 */
  label?: string;
  /** 缺失时显示的文案。**必须是明确表示缺失的词**（未测 / 未提供 / 待采集）。 */
  emptyText?: string;
  /** 缺失原因（可选）。有就说，没有就不说 —— 不许编。 */
  missingReason?: string;
  /** 读不出来的原因。给了它 → 状态是 unreadable，不是 missing。 */
  unreadableReason?: string;
  /** 单位（如 " ms"）。留空表示原样。 */
  unit?: string;
}

/**
 * 判一个值在不在。
 *
 * ★ 0 是合法值 —— 不许用真值判断，那会把 0 吞掉。
 *   `fieldStateKind(0)` 必须是 `ok`（实测用例 A2）。
 */
export function fieldStateKind(
  value: string | number | null | undefined,
  unreadableReason?: string,
): FieldStateKind {
  if (unreadableReason) return "unreadable";
  if (value === null || value === undefined) return "missing";
  if (typeof value === "number") return Number.isFinite(value) ? "ok" : "missing";
  if (!value.trim()) return "missing";
  return "ok";
}

/**
 * 纯文本形态，给渲染 / aria / 日志 / 自证共用。
 *
 * ★ 这是 `FieldState` 与自证脚本**共用**的一份口径 —— 两处各拼一遍必然漂移。
 *
 * ★★ 三态必须长得不一样（AGENTS.md §2.4.1 第 4 行同一条）：
 *     「未测」  = 这条数据本来就没有
 *     「读不出」= 我该拿到但没拿到（采集失败）
 *     混在一起会让人以为系统没采集，而实际是采集失败了。
 */
export function fieldStateText(props: FieldStateInput): string {
  const kind = fieldStateKind(props.value, props.unreadableReason);
  const label = props.label ? `${props.label}：` : "";
  if (kind === "unreadable") {
    return `${label}读不出：${props.unreadableReason}`;
  }
  if (kind === "missing") {
    const word = props.emptyText ?? "未测";
    const why = props.missingReason?.trim();
    return why ? `${label}${word}（${why}）` : `${label}${word}`;
  }
  return `${label}${String(props.value).trim()}${props.unit ?? ""}`;
}
