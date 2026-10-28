import { Component, type ErrorInfo, type ReactNode } from "react";
import Button from "../ui/Button";
import {
  appendError,
  ERROR_BUFFER_MAX,
  nextBoundaryState,
  retryState,
  type BoundaryState,
  type CapturedError,
} from "./errorBoundary.logic";

/**
 * 路由级错误边界（ADR-0021 · W-3）。
 *
 * ## 它为什么存在
 *
 * 2026-10-27 审计：全仓 `grep ErrorBoundary|componentDidCatch` = **0 命中**。
 * 也就是说 —— **任意一个页面里一个渲染异常，整站白屏**。
 *
 * 这在本项目不是理论风险：13 个页面、660 行的 CaseDetailPage、
 * 大量 `?.` 与 `??` 兜底，任何一处对后端形状的假设错了，
 * 用户看到的就是一片白，而且**不知道是哪个页面坏了、也不知道能不能继续用别的页面**。
 *
 * ## 三条口径
 *
 * ### ① 崩溃要**说清是哪一块**坏了
 *
 * 不写「出错了」，写「这个页面渲染失败」+ 原始 message + 可展开的组件栈。
 * 用户至少能判断「是我的数据有问题，还是系统坏了」。
 *
 * ### ② 必须能**回到别的页面**
 *
 * 白屏最坏的地方是**把人困住**。所以：一个「重试」（重挂这一块）+ 一个
 * 「回到队列」（换页）。重试不刷新整页 —— 刷新会丢掉其它页面的状态。
 *
 * ### ③ ★ 不许把错误**吞掉**
 *
 * 不 `console.error` 一句就算完。错误要进 `window.__REVIEW_ERRORS__`
 * （一个环形缓冲），这样：
 * · 联调时 `pairing_check.mjs` / dev-up 的检查器能读到它；
 * · 用户报「白屏了」时，控制台里有一条机器可读的记录。
 * 静默的边界比没有边界更糟 —— 它让人以为页面正常。
 */

declare global {
  interface Window {
    __REVIEW_ERRORS__?: CapturedError[];
  }
}

function recordError(entry: CapturedError): void {
  if (typeof window === "undefined") return;
  // ★ 裁剪逻辑在 `errorBoundary.logic.ts`（纯函数），这里只负责落盘 ——
  //   两处各写一遍「环形缓冲」必然有一处忘记 shift()。
  window.__REVIEW_ERRORS__ = appendError(
    window.__REVIEW_ERRORS__,
    entry,
    ERROR_BUFFER_MAX,
  );
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  /** 边界名字。出现在记录里，用来定位「哪个页面崩了」。 */
  name: string;
  /** 崩溃时显示给用户的说明。默认通用文案。 */
  what?: string;
}



export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  BoundaryState
> {
  state: BoundaryState = { error: null, componentStack: null, attempt: 0 };

  // ★ 走纯函数：自证能 import 它去测，而这里只调用一次。
  static getDerivedStateFromError(error: Error): Partial<BoundaryState> {
    return nextBoundaryState(error);
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    const componentStack = info.componentStack ?? null;
    this.setState({ componentStack });
    // ★ 必须留痕，不许只 console 一句（见文件头 ③）
    recordError({
      at: new Date().toISOString(),
      message: error.message,
      stack: error.stack,
      componentStack: componentStack ?? undefined,
      boundary: this.props.name,
    });
  }

  private retry = (): void => {
    // ★ 只重挂这一块，不 `location.reload()` —— 刷新会丢掉其它页面的状态，
    //   而且用户只是想「再试一次这个页面」。
    this.setState((s) => retryState(s));
  };

  render(): ReactNode {
    const { error, componentStack, attempt } = this.state;
    if (!error) {
      // ★ key 用 attempt：重试时强制重挂子树，否则 React 会复用已经崩过的实例
      return <div key={attempt} data-error-boundary={this.props.name}>{this.props.children}</div>;
    }
    const what = this.props.what ?? "这个页面渲染失败";
    return (
      <section className="case" role="alert" data-error-boundary={this.props.name}>
        <h1>{what}</h1>
        <div className="state state--error">
          <h2>页面出错，其它页面仍可正常使用</h2>
          <p className="font-data">{error.message || String(error)}</p>
          <p className="hint">
            判定结果由后端产出，这次崩溃<b>没有改变任何案件的状态</b>。
            可以重试本页，或回到复核队列继续处理其它案件。
          </p>
          <div className="actions__row">
            <Button variant="secondary" onClick={this.retry}>
              重试本页
            </Button>
            {/* ★ 2026-10-28（DT-6 报红）：原先这里是 `variant="primary"`。
                设计规则是「primary 只用于高风险动作，且必须带 `data-risk-action`」
                —— 而「回到复核队列」是一次导航，不是高风险动作。
                写 primary 的后果不是好看难看：它让**唯一**那只红色按钮
                出现在一个安全动作上，于是「红色 = 要小心」这条视觉约定失效。
                改成 secondary，与「重试本页」同级。 */}
            <Button
              variant="secondary"
              onClick={() => {
                // 用 location.assign 而不是 history.push：这里是边界，
                // 处于 React 树之外的危险位置，换一条最简单的路径。
                window.location.assign("/queue");
              }}
            >
              回到复核队列
            </Button>
          </div>
          {componentStack && (
            <details>
              <summary className="hint">组件栈（排查用）</summary>
              <pre className="font-data" style={{ whiteSpace: "pre-wrap" }}>
                {componentStack}
              </pre>
            </details>
          )}
        </div>
      </section>
    );
  }
}
