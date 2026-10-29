/**
 * browserNotice.logic.ts —— 「浏览器支持提示该渲染成什么」的纯逻辑。
 *
 * ## 为什么单独抽出来（不是洁癖）
 *
 * 这段判据决定**每一个业务页面正文顶部有没有那条常驻横幅**。
 * 2026-10-29 实测过一次退化：组件无条件渲染一行「正式支持范围…」，
 * 于是 15 个页面全都在最显眼的位置挂着一行灰字，把当前任务往下压。
 *
 * 如果这个判断留在 `.tsx` 里，`check_browser_scope.mjs` 只能**正则扫源码**
 * 来验它 —— 而「源码里有 `return null`」这种判据在有注释的地方恒真，
 * 删掉真逻辑、留一行注释它照样绿（本仓库 §2.4 记过同一个形状）。
 *
 * 抽成纯函数之后，门禁可以 `await import()` 真身、喂真实入参、看返回值。
 * 这就是 `polling.logic.ts` / `fieldState.logic.ts` / `errorBoundary.logic.ts`
 * 已经在用的模式 —— 照抄，不发明第二套。
 *
 * ★ 本文件**不含 JSX**，Node 才能直接 import（`--experimental-strip-types`）。
 */

export type NoticeMode =
  /** 完全不渲染（受支持且未要求常显）—— 业务页面的默认结果 */
  | "none"
  /** 只渲染一行轻量范围说明（登录页页脚） */
  | "range-only"
  /** 渲染完整告警横幅（非支持浏览器） */
  | "alert";

export interface NoticeRenderInput {
  /** `evaluateUserAgent(...).supported` 的结果 */
  supported: boolean;
  /** 组件是否被显式要求「即使在受支持时也显示范围」 */
  alwaysShowRange?: boolean;
}

/**
 * 决定渲染模式。
 *
 * 判据只有两条，顺序也不能换：
 *
 * 1. **受支持** → 不告警。若调用方显式要求常显范围（登录页），给 `range-only`；
 *    否则 `none`。
 * 2. **不受支持** → `alert`，把原因 / 范围 / 更换指引一起给出。
 *
 * ★ 第 1 条是这次修复的核心：受支持的浏览器**不需要被告知它被支持**。
 *   那条信息属于「不合规环境」的告知，不是常驻横幅。
 */
export function noticeModeFor({ supported, alwaysShowRange = false }: NoticeRenderInput): NoticeMode {
  if (supported) return alwaysShowRange ? "range-only" : "none";
  return "alert";
}
