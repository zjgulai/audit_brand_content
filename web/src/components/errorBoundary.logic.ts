/**
 * errorBoundary.logic.ts —— 错误边界的**判定逻辑**（ADR-0021 · W-3）
 *
 * ★ 为什么把这一行抽出来：
 *   `ErrorBoundary.tsx` 是 `.tsx`，Node 的 `--experimental-strip-types`
 *   加载不了它（需要 JSX 转换）。于是自证只能「用正则看源码里有没有
 *   getDerivedStateFromError」—— 而那是**恒真**的那类判据：
 *   一个 `return {}` 的实现也能过（React 会拿不到 error 对象，
 *   `state.error` 恒 null，边界永远显示正常内容，**等于没有边界**）。
 *
 *   抽成 `.ts` 之后，`check_error_boundary.mjs` 能 import 真身、
 *   真的调一次 `nextBoundaryState(new Error("boom"))` 看返回值。
 *
 * ★ 这个文件里不许出现 React / JSX / DOM API。
 */

/** 边界捕获到错误后应该进入的 state。 */
export interface BoundaryState {
  error: Error | null;
  componentStack: string | null;
  /** 每次「重试」自增，用作 key 强制重挂子树。 */
  attempt: number;
}

/**
 * React 的 `getDerivedStateFromError` 要返回的那一份。
 *
 * ★★★ **必须把 error 放进去。** 返回 `{}` 看起来「没崩」，
 *   但 React 拿不到 error，`state.error` 恒为 `null`，
 *   于是 `render()` 里 `if (!error) return children` 永远成立 ——
 *   边界变成了一个透明的 div，**崩溃照样白屏**。
 *   这是本项目最该防的那类坏实现：它通过了「有没有这个钩子」的检查。
 */
export function nextBoundaryState(error: Error): Partial<BoundaryState> {
  return { error };
}

/** 重试时的新 state：清掉错误，attempt 自增（用作 key，强制重挂子树）。 */
export function retryState(prev: BoundaryState): BoundaryState {
  // ★ 返回**完整** state 而不是 Partial：`setState` 的 updater 签名要求
  //   合并后的完整形状，用 Partial 会在 `error: Error | null | undefined`
  //   那一步报「不能把 undefined 赋给 Error | null」。
  return { error: null, componentStack: null, attempt: prev.attempt + 1 };
}

/** 一条留在 `window.__REVIEW_ERRORS__` 里的记录。 */
export interface CapturedError {
  at: string;
  message: string;
  stack?: string;
  componentStack?: string;
  /** 出错的边界挂了什么名字（`<ErrorBoundary name="route:/queue">`）。 */
  boundary: string;
}

/** 环形缓冲上限。长会话里不许无限增长。 */
export const ERROR_BUFFER_MAX = 20;

/**
 * 往缓冲里追加一条，并裁掉最旧的。
 *
 * ★ 纯函数（不改入参），返回**新数组** —— 这样自证能直接断言，
 *   而组件那边把它塞回 `window.__REVIEW_ERRORS__` 即可。
 */
export function appendError(
  list: CapturedError[] | undefined,
  entry: CapturedError,
  max: number = ERROR_BUFFER_MAX,
): CapturedError[] {
  const next = [...(list ?? []), entry];
  while (next.length > max) next.shift();
  return next;
}
