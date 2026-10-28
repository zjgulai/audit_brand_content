import { useCallback, useEffect, useRef, useState } from "react";
import {
  loadPhase,
  onVisibilityChange,
  shouldTick,
  type LoadPhase,
} from "./polling.logic";

export { loadPhase, shouldSurfaceFailures } from "./polling.logic";
export type { LoadPhase } from "./polling.logic";

/**
 * 列表页轮询（ADR-0021 · W-3）。
 *
 * ## 它为什么存在
 *
 * 2026-10-27 审计：全仓 `setInterval` **0 命中**、`WebSocket` / `EventSource` 0、
 * `visibilitychange` 0。也就是说——**队列页不会自动刷新**，审核员必须手动 F5
 * 才能看到新案件。多人协作时，这会让案件被重复领取，或者压根没人看到。
 *
 * ## 三条口径（缺一条就会变成负资产）
 *
 * ### ① 标签页隐藏时不跑
 *
 * `document.visibilityState === "hidden"` 时清掉定时器。否则：
 * · 十个审核员开着十个后台标签页 = 每 20 秒十次无意义请求；
 * · 更糟的是**回来时看到的是 20 秒前的旧数据却以为是新的** ——
 *   它不会自己再刷一次，因为定时器还在跑，下一次要等满一个周期。
 * 所以「重新可见」时**立刻拉一次**，而不是等下一个 tick。
 *
 * ### ② 静默刷新：重新取数时**不清空**已有数据
 *
 * 三个列表页原本的写法都是 `setRows(null); fetch(...)`。那是首屏加载的写法 ——
 * 搬到轮询里，列表会每 20 秒闪一次「加载中」再恢复。
 * 所以本 hook 区分两种状态：
 *   `loading`  —— **首次**加载（此时没有旧数据可留，显示骨架屏是对的）
 *   `refreshing` —— 后续刷新（**保留旧数据**，只在角落显示「更新中」）
 *
 * ### ③ 写动作期间暂停
 *
 * 审核员正在认领 / 填复核意见时，一次自动刷新会把界面数据换掉。
 * 轻则闪一下，重则**冲掉未保存的草稿**。所以调用方传 `paused: busy`。
 *
 * ## 为什么不上 WebSocket
 *
 * 它需要后端长连接 + 重连退避 + 心跳，而本项目当前连轮询都没有。
 * 先有轮询（20 秒足够：审核动作是分钟级），需要时再换代 ——
 * 但那时 `visibilitychange` / 暂停这些口径仍然要保留。
 */

/** 默认轮询间隔。20 秒：审核动作是分钟级，更快只会浪费请求。 */
export const DEFAULT_POLL_MS = 20_000;

export interface UsePollingOptions {
  /** 是否启用。`false` 时不拉也不计时（如开发身份未就绪）。 */
  enabled?: boolean;
  /** 暂停：写动作进行中传 `true`，避免刷新覆盖用户操作。 */
  paused?: boolean;
  /** 间隔毫秒。默认 20 秒。 */
  intervalMs?: number;
}

export interface UsePollingState {
  /** **首次**加载中（无旧数据）。调用方此时显示骨架屏。 */
  loading: boolean;
  /** 后续刷新中（有旧数据）。调用方**不要**清空内容。 */
  refreshing: boolean;
  /** 三态合成：initial / refreshing / idle。调用方优先用这个。 */
  phase: LoadPhase;
  /** 最近一次成功的时间（毫秒时间戳）。供「刚更新」提示用。 */
  lastLoadedAt: number | null;
  /** 手动触发一次。 */
  refresh: () => void;
  /** 本次 tick 失败次数（连续失败后可以提示「后台刷新失败」）。 */
  failures: number;
}

/**
 * @param loader 取数函数。**必须是稳定引用**（用 `useCallback` 包），
 *               否则每次渲染都会重置定时器 —— 那等于没有轮询。
 */
export function usePolling(
  loader: () => Promise<void>,
  { enabled = true, paused = false, intervalMs = DEFAULT_POLL_MS }: UsePollingOptions = {},
): UsePollingState {
  const [loading, setLoading] = useState(enabled);
  const [refreshing, setRefreshing] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<number | null>(null);
  const [failures, setFailures] = useState(0);

  // 首次是否已完成。用 ref 而不是 state：它决定「清算空」这条分支，
  // 而这个判断发生在回调里，用 state 会读到闭包里的旧值。
  const startedRef = useRef(false);
  // 防重入：上一轮还没回来就不要再发。
  const inFlightRef = useRef(false);
  // ★ paused / loader 用 ref 持有，**不进 `run` 的依赖** ——
  //   否则：审核员点「认领」→ paused 变 true → `run` 重建 →
  //   首次加载那个 effect 重跑 → `startedRef` 清零 → 列表闪空一次。
  //   实测症状就是「点一下按钮列表白一下」。
  //   这里可以让 ref 滞后一个渲染周期：paused 只在**下一次 tick 前**生效，
  //   而这个 hook 的 tick 间隔是 20 秒 —— 一个渲染周期完全可以接受。
  const pausedRef = useRef(paused);
  const loaderRef = useRef(loader);
  pausedRef.current = paused;
  loaderRef.current = loader;
  // 卸载/换 deps 后到达的响应要丢弃。
  const aliveRef = useRef(true);

  const run = useCallback(
    async (reason: "initial" | "tick" | "visible" | "manual") => {
      // ★ 判定走纯函数（`polling.logic.ts`），这样自证能 import 真身去测。
      const gate = shouldTick({
        enabled,
        paused: pausedRef.current,
        inFlight: inFlightRef.current,
        visible:
          typeof document === "undefined" ||
          document.visibilityState !== "hidden",
      });
      if (!gate.run) return;
      inFlightRef.current = true;

      const first = !startedRef.current;
      if (first) setLoading(true);
      // ★ 只有**后续**刷新才叫 refreshing。首次加载不该同时挂两个状态 ——
      //   两个都为 true 时调用方会不知道该显示骨架屏还是旧内容。
      else setRefreshing(true);

      try {
        await loaderRef.current();
        if (!aliveRef.current) return;
        startedRef.current = true;
        setLastLoadedAt(Date.now());
        setFailures(0);
      } catch (e) {
        if (!aliveRef.current) return;
        // ★ 失败不清空数据、也不抛给调用方 —— 列表页已经把错误渲染在页面上；
        //   轮询失败不该把「已经显示的内容」换成错误页（那是更糟的信息损失）。
        //   只累计次数，由调用方决定怎么提示。
        setFailures((n) => n + 1);
        if (reason === "initial") {
          // 首次失败要让调用方知道（它需要显示错误态而不是空列表）
          setLoading(false);
        }
      } finally {
        inFlightRef.current = false;
        if (aliveRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [enabled],
  );

  // ── 首次 + deps 变化
  useEffect(() => {
    aliveRef.current = true;
    startedRef.current = false;
    void run("initial");
    return () => {
      aliveRef.current = false;
    };
  }, [run]);

  // ── 定时器 + 可见性
  useEffect(() => {
    if (!enabled) return;
    let timer: number | null = null;

    const clear = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };
    const start = () => {
      clear();
      timer = window.setInterval(() => void run("tick"), intervalMs);
    };

    const onVisibility = () => {
      if (typeof document === "undefined") return;
      const action = onVisibilityChange(
        document.visibilityState as "visible" | "hidden" | "prerender",
        enabled,
      );
      if (action === "stop-timer") clear();
      else if (action === "fetch-now-and-restart") {
        void run("visible");
        start();
      }
    };

    if (typeof document === "undefined" || document.visibilityState !== "hidden") {
      start();
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisibility);
    }
    return () => {
      clear();
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
      }
    };
  }, [enabled, intervalMs, run]);

  // ── 手动刷新
  const refresh = useCallback(() => {
    void run("manual");
  }, [run]);

  const phase: LoadPhase = loadPhase({
    loading,
    refreshing,
    first: !startedRef.current,
  });

  return { loading, refreshing, phase, lastLoadedAt, refresh, failures };
}
