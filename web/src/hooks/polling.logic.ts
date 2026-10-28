/**
 * polling.logic.ts —— 轮询的**判定逻辑**（ADR-0021 · W-3）
 *
 * ★ 为什么把这几行抽出来：`usePolling.ts` 里的判定全在 React 副作用里，
 *   而本仓没有 DOM 测试库（无 vitest / jsdom / happy-dom）。
 *   抽成纯函数之后，`check_polling.mjs` 能用 `--experimental-strip-types`
 *   直接 import 真身去测 —— **测真身，不测副本**（与 `fieldState.logic.ts` 同一条）。
 *
 * ★ 这个文件里不许出现 React / JSX / DOM API。
 */

/** 一轮 tick 该不该真的发请求。 */
export interface TickInput {
  /** hook 是否启用。 */
  enabled: boolean;
  /** 是否处于写动作中（认领 / 填意见）。 */
  paused: boolean;
  /** 上一轮是否还没回来。 */
  inFlight: boolean;
  /** 页面是否可见（`document.visibilityState !== "hidden"`）。 */
  visible: boolean;
}

/**
 * 返回该不该发，以及不发的原因（原因要能被人读，不能只是 `false`）。
 *
 * ★ 四条**各自独立**：任意一条为假都不发，且理由不同 ——
 *   把原因合并成一句「不该发」会让排查时无从下手。
 */
export function shouldTick(input: TickInput): { run: boolean; reason: string } {
  if (!input.enabled) return { run: false, reason: "disabled" };
  // ★ 可见性判断放在 paused 之前：隐藏时**根本不该有定时器**
  //   （见 usePolling 的 visibilitychange），这里再防一次是 defence in depth。
  if (!input.visible) return { run: false, reason: "hidden" };
  if (input.paused) return { run: false, reason: "paused" };
  if (input.inFlight) return { run: false, reason: "in-flight" };
  return { run: true, reason: "" };
}

/** 这一轮该显示哪个「加载」状态。 */
export type LoadPhase = "initial" | "refreshing" | "idle";

/**
 * ★ 三态，不是两态。
 *
 * · `initial`    —— 首次加载，**没有旧数据**，显示骨架屏是对的
 * · `refreshing` —— 后续刷新，**有旧数据**，必须保留内容，只在角落提示「更新中」
 * · `idle`       —— 不在加载
 *
 * 改前三个列表页都是 `setRows(null); fetch(...)` —— 那是首屏的写法。
 * 搬进轮询里就会「每 20 秒白一下」。所以这个区分是 W-3 的核心，不是细节。
 */
export function loadPhase(input: {
  loading: boolean;
  refreshing: boolean;
  /** 本次是不是首次（`startedRef` 的语义）。 */
  first: boolean;
}): LoadPhase {
  // ★ first 优先：首次加载时即使 refreshing 也被算成 initial，
  //   否则会出现「两个都为 true」的中间态，调用方不知道显示哪个。
  if (input.first) return input.loading ? "initial" : "idle";
  if (input.refreshing) return "refreshing";
  if (input.loading) return "initial";
  return "idle";
}

/**
 * 可见性变化时该做什么。
 *
 * ★ 隐藏要**停表**而不是「跳过」：跳过仍然每 20 秒唤起一次 JS。
 * ★ 回来要**立刻拉一次**：否则要等满一个周期才拿到新数据，
 *   而那期间显示的旧数据**看起来像新的**。
 */
export type VisibilityAction = "stop-timer" | "fetch-now-and-restart" | "noop";

export function onVisibilityChange(
  state: "visible" | "hidden" | "prerender",
  enabled: boolean,
): VisibilityAction {
  if (!enabled) return "noop";
  if (state === "hidden") return "stop-timer";
  return "fetch-now-and-restart";
}

/** 连续失败到几次时该在界面上提示「后台刷新失败」。 */
export const FAILURE_NOTICE_THRESHOLD = 2;

export function shouldSurfaceFailures(failures: number): boolean {
  return failures >= FAILURE_NOTICE_THRESHOLD;
}
