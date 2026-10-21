/**
 * 内部判定数据 —— **只在 dev 构建加载**。
 *
 * 为什么单独一个模块（T-210，2026-10-22）：
 *   `taxonomy.json` 里的 `rule_examples`（内部判定理由原文）与
 *   `meta.boundary_disputes`（未裁定的内部分歧）不能进生产 bundle。
 *   但只剥 JSON 不够 —— 页面源码里的属性名本身也会被打进 chunk。
 *   所以把这些字段的**访问**整体挪到这里，并由 `TaxonomyPage` 用
 *   `if (import.meta.env.DEV) await import(...)` 动态加载：
 *   生产构建里 `import.meta.env.DEV` 是 `false`，Rollup 会把这条分支整个丢掉，
 *   本模块不产出 chunk，`rule_examples` / `boundary_disputes` 两个字符串也不出现。
 *
 * 执行点：`scripts/check_production_bundle.mjs` 扫 dist，出现任一字符串即红。
 */
import taxonomyJson from "./taxonomy.json";

type HasInternal = {
  rule_examples?: unknown[];
  meta?: { boundary_disputes?: unknown[] };
};

const doc = taxonomyJson as unknown as HasInternal;

export const ruleExamples = doc.rule_examples ?? [];
export const boundaryDisputes = doc.meta?.boundary_disputes ?? [];
