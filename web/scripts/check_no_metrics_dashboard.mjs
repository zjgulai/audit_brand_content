#!/usr/bin/env node
/**
 * check_no_metrics_dashboard.mjs —— #129 (TS-26) 阶段一不做独立指标看板，只显示必要计数与未测
 *
 * 覆盖 #129 全部判据：
 *   M1 路由表（`web/src/App.tsx`）与页面目录（`web/src/pages/`）**不存在**任何独立指标看板路由或页面
 *      （如 `/metrics`、`/dashboard`、`/analytics`、`MetricsPage`、`DashboardPage`）；
 *      前端 `web/src/` 与 `web/package.json` 不引入任何图表库（`recharts`、`echarts`、`chart.js`、`d3`、`victory`）；
 *   M2 案件页（`CaseDetailPage.tsx`）、队列页（`QueuePage.tsx`）、报告页（`ReportPage.tsx`）
 *      均挂载 `InlineMetricSummary`，且 `InlineMetricSummary` 严格有且仅有
 *      「必要计数（`data-metric-counts`）+ 趋势摘要（`data-metric-trend`）+ 未测/样本不足（`data-metric-untested`）」三类显示元素；
 *   M3 四指标输出七要素校验（`validateMetricSevenElements`）：
 *      `numerator` / `denominator` / `window` / `sampling_layer` / `min_n` / `status` / `target` 七要素齐全才有效；
 *      `status="未测"` 精确显示「未测」（不显示 `0`、`0%`、`N/A` 或空串）；
 *      `n < min_n` 显示「样本不足」且无比率；
 *   M4 反向对照（`--controls`）：
 *      - C1 正样本：无独立看板 + 三页三元摘要齐全 + 四指标七要素校验与 `base/metrics_read_model.py` 对拍通过；
 *      - C2 坏样本（有图表但七要素不全）：传入含 `chart: { type: "bar", series: [95, 98] }` 但缺 `sampling_layer` 或 `min_n` 的指标对象 →
 *           必须被标为 `valid: false`、`displayStatus: "不可用"`（绝不因画得好看而算数）；
 *      - C3 坏样本（逐个删掉七要素中任一字段，共 7 轮）：每一轮都必须返回 `valid: false`；
 *      - C4 坏样本（未测与样本不足）：`status="未测"` 必须输出精确字符串 `"未测"`（非 `"0"` / `"N/A"`）；
 *           `denominator=12 < min_n=30` 必须输出 `"样本不足"` 且不含百分比符号 `%`；
 *      - C5 坏样本（植入 `/metrics` 路由或 `recharts` 依赖）：必须被 M1 抓到判红。
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");
const REPO = path.resolve(WEB, "..");

const APP_PATH = path.join(WEB, "src/App.tsx");
const INLINE_PATH = path.join(WEB, "src/components/InlineMetricSummary.tsx");
const QUEUE_PATH = path.join(WEB, "src/pages/QueuePage.tsx");
const CASE_PATH = path.join(WEB, "src/pages/CaseDetailPage.tsx");
const REPORT_PATH = path.join(WEB, "src/pages/ReportPage.tsx");
const PKG_PATH = path.join(WEB, "package.json");

const SEVEN_KEYS = [
  "numerator",
  "denominator",
  "window",
  "sampling_layer",
  "min_n",
  "status",
  "target",
];

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function checkNoDashboardRoutesAndLibs(appSrc, pageNames, pkgJson) {
  const problems = [];
  const cleanApp = stripComments(appSrc);
  const routePaths = [
    ...cleanApp.matchAll(/path\s*=\s*["']([^"']+)["']/g),
  ].map((m) => m[1]);
  for (const p of routePaths) {
    if (/^\/?(?:metrics|dashboard|analytics|kpi)\b/i.test(p)) {
      problems.push(`M1 App.tsx 存在禁止的独立指标看板路由：${p}`);
    }
  }
  for (const name of pageNames) {
    if (/(?:Metrics|Dashboard|Analytics|Kpi).*Page/i.test(name)) {
      problems.push(`M1 pages/ 目录存在独立指标看板页面文件：${name}`);
    }
  }
  const deps = {
    ...(pkgJson.dependencies || {}),
    ...(pkgJson.devDependencies || {}),
  };
  for (const d of Object.keys(deps)) {
    if (/^(?:recharts|echarts|chart\.js|react-chartjs-2|d3|victory|nivo|highcharts)$/i.test(d)) {
      problems.push(`M1 package.json 含阶段一禁止的独立图表库依赖：${d}`);
    }
  }
  return problems;
}

function checkThreePagesInlineSummary(inlineSrc, queueSrc, caseSrc, reportSrc) {
  const problems = [];
  const cleanInline = stripComments(inlineSrc);

  // 断言 InlineMetricSummary 仅有 data-metric-counts / data-metric-trend / data-metric-untested 三类显示槽
  const metricSlots = [
    ...new Set(
      [...cleanInline.matchAll(/data-metric-([a-z-]+)=/g)].map((m) => m[1]),
    ),
  ].sort();
  const expectedSlots = ["counts", "trend", "untested"];
  if (JSON.stringify(metricSlots) !== JSON.stringify(expectedSlots)) {
    problems.push(
      `M2 InlineMetricSummary 的指标元素槽位必须恰好为 [counts, trend, untested]，实际为 ${JSON.stringify(metricSlots)}`,
    );
  }
  if (/<(?:svg|canvas)\b|<Chart\b|<Sparkline\b/i.test(cleanInline)) {
    problems.push("M2 InlineMetricSummary 内出现了禁止的图表/画布 JSX 元素");
  }

  for (const [label, src, scope] of [
    ["QueuePage.tsx", queueSrc, "queue"],
    ["CaseDetailPage.tsx", caseSrc, "case"],
    ["ReportPage.tsx", reportSrc, "report"],
  ]) {
    const clean = stripComments(src);
    if (!clean.includes("InlineMetricSummary") || !clean.includes(`scope="${scope}"`)) {
      problems.push(`M2 ${label} 未挂载 <InlineMetricSummary scope="${scope}" />`);
    }
  }
  return problems;
}

/**
 * 与 InlineMetricSummary.tsx 中 validateMetricSevenElements 完全同构的校验逻辑，
 * 并验证源码中確實定义了全部 7 个键与相同状态规则。
 */
function validateMetric(metric) {
  if (!metric || typeof metric !== "object") {
    return {
      valid: false,
      missingKeys: [...SEVEN_KEYS],
      displayStatus: "未测",
      displayValue: "未测",
    };
  }
  const missingKeys = [];
  for (const k of SEVEN_KEYS) {
    if (!(k in metric)) missingKeys.push(k);
  }
  const win = metric.window;
  const layer = metric.sampling_layer;
  const minN = metric.min_n;
  const status = metric.status;

  if (typeof minN !== "number" || Number.isNaN(minN) || minN < 1) {
    if (!missingKeys.includes("min_n")) missingKeys.push("min_n");
  }
  if (
    layer === null ||
    layer === undefined ||
    (typeof layer === "string" && !layer.trim()) ||
    (Array.isArray(layer) && layer.length === 0)
  ) {
    if (!missingKeys.includes("sampling_layer")) missingKeys.push("sampling_layer");
  }
  if (typeof status !== "string" || !status.trim()) {
    if (!missingKeys.includes("status")) missingKeys.push("status");
  }

  if (missingKeys.length > 0) {
    return {
      valid: false,
      missingKeys,
      displayStatus: "不可用",
      displayValue: "不可用（七要素不全）",
    };
  }

  if (status === "未测" || win === null || win === undefined || String(win).trim() === "") {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "未测",
      displayValue: "未测",
    };
  }

  const num = typeof metric.numerator === "number" ? metric.numerator : null;
  const den = typeof metric.denominator === "number" ? metric.denominator : null;
  if (status === "样本不足" || (den !== null && den < minN)) {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "样本不足",
      displayValue: `样本不足（n=${den ?? 0} < min_n=${String(minN)}）`,
    };
  }
  if (num === null || den === null || den <= 0) {
    return {
      valid: true,
      missingKeys: [],
      displayStatus: "未测",
      displayValue: "未测",
    };
  }
  const pct = ((num / den) * 100).toFixed(1);
  return {
    valid: true,
    missingKeys: [],
    displayStatus: "ok",
    displayValue: `${pct}%（n=${num}/${den}）`,
  };
}

function checkInlineSourceContract(inlineSrc) {
  const problems = [];
  for (const k of SEVEN_KEYS) {
    if (!inlineSrc.includes(`"${k}"`)) {
      problems.push(`M3 InlineMetricSummary.tsx 缺少七要素键定义：${k}`);
    }
  }
  if (!inlineSrc.includes("不可用（七要素不全）")) {
    problems.push("M3 InlineMetricSummary.tsx 缺少七要素不全时的『不可用』阻断分支");
  }
  return problems;
}

function runControls(appSrc, pageNames, pkgJson, inlineSrc, queueSrc, caseSrc, reportSrc) {
  const cases = [];

  // C1 正样本：当前真实代码 + 后端 MetricsReadModel 真实输出双向对拍
  let pyBackendOk = false;
  try {
    const out = execFileSync(
      "python3",
      [
        "-c",
        "import sys, json; sys.path.insert(0, 'base'); from metrics_read_model import MetricsReadModel; " +
          "m = MetricsReadModel(lambda w: (_ for _ in ()).throw(RuntimeError('offline'))).compute('2026-10'); " +
          "print(json.dumps(m, ensure_ascii=False))",
      ],
      { cwd: REPO, encoding: "utf8", timeout: 8000 },
    );
    const parsed = JSON.parse(out.trim());
    const all = Object.values(parsed.metrics || {});
    // ★★★ 2026-10-29：这里原来硬编码 `all.length === 4`，于是 T-451
    //   （提交 80d42a6）加上第 5 个指标 `workflow_latency_ms` 之后，
    //   本项从那一刻起**一直是红的**，而没人发现。
    //
    //   ★ 病在判据写成了「恰好 4 个」而不是「**每个**都合规」：
    //     前者把「指标集合长什么样」抄进了检查器，后者只关心「每个指标的
    //     三态是否合规」。指标增加是正常演进，而「恰好 4」会让正常演进变红 ——
    //     更糟的是，红久了大家都当它是噪音，真正的红也看不见了。
    //
    //   改：判据改成「至少一个指标」+「**每个**都合规」。
    //   为什么不再钉个数：个数由 `base/metrics_read_model.py` 一处决定，
    //   抄一份到检查器就是两个口径（改了必漂——这次漂了 4 天没人发现）。
    //   真正的守卫是「每个都合规」，那是**性质**而不是**数量**。
    pyBackendOk =
      all.length > 0 &&
      all.every((item) => {
        const res = validateMetric(item);
        return res.valid && res.displayStatus === "未测" && res.displayValue === "未测";
      });
  } catch {
    pyBackendOk = false;
  }
  cases.push([
    "C1 正样本：无独立看板路由/页面 + 三页三元摘要齐全 + 后端 MetricsReadModel 全部指标断源输出精确为『未测』",
    pyBackendOk,
    "MetricsReadModel 对拍失败",
  ]);

  // C2 坏样本（验收表 #129 点名：「有图表但七要素不全」的样本必须被标为不可用）
  const chartButIncomplete = {
    id: "recall_l4_l5",
    name: "高危召回率",
    numerator: 48,
    denominator: 50,
    window: "2026-10",
    // 故意缺失 sampling_layer 与 min_n，但塞入漂亮的图表对象
    status: "ok",
    target: null,
    chart: {
      type: "area-sparkline",
      color: "#6A2C3A",
      points: [0.91, 0.94, 0.96],
    },
  };
  const c2Res = validateMetric(chartButIncomplete);
  cases.push([
    "C2 ★ 反向对照：『有图表但七要素不全』的样本 → 必须标为不可用（valid=false, displayStatus=不可用）",
    c2Res.valid === false &&
      c2Res.displayStatus === "不可用" &&
      c2Res.missingKeys.includes("sampling_layer") &&
      c2Res.missingKeys.includes("min_n"),
    JSON.stringify(c2Res),
  ]);

  // C3 坏样本：逐一删掉七要素中的每一个字段（7 个反例全部必须 valid=false）
  const fullSample = {
    numerator: 32,
    denominator: 40,
    window: "2026-10",
    sampling_layer: ["PASS", "待自决", "REVIEW", "未审查"],
    min_n: 30,
    status: "ok",
    target: null,
  };
  const deletedChecks = SEVEN_KEYS.map((k) => {
    const clone = { ...fullSample };
    delete clone[k];
    return [k, validateMetric(clone).valid === false];
  });
  cases.push([
    "C3 反向对照：逐个删除七要素任一字段（7/7 轮） → 每一轮都必须判为不可用（valid=false）",
    deletedChecks.every(([, ok]) => ok),
    JSON.stringify(deletedChecks),
  ]);

  // C4 未测与样本不足边界：未测不许显示 0/N/A；n=29 < min_n=30 必须显示「样本不足」且无百分比
  const untestedSample = {
    ...fullSample,
    numerator: null,
    denominator: null,
    status: "未测",
  };
  const lowNSample = {
    ...fullSample,
    numerator: 28,
    denominator: 29,
    status: "样本不足",
  };
  const rUntested = validateMetric(untestedSample);
  const rLowN = validateMetric(lowNSample);
  const rFull = validateMetric(fullSample);
  cases.push([
    "C4 边界对照：未测精确输出『未测』（非 0/N/A）；n=29<30 输出『样本不足』无比率；n=40>=30 输出『80.0%（n=32/40）』",
    rUntested.displayValue === "未测" &&
      rLowN.displayStatus === "样本不足" &&
      !rLowN.displayValue.includes("%") &&
      rLowN.displayValue.includes("n=29") &&
      rFull.displayValue === "80.0%（n=32/40）",
    JSON.stringify({ rUntested, rLowN, rFull }),
  ]);

  // C5 坏样本：植入 `/metrics` 独立看板路由、`MetricsDashboardPage.tsx` 与 `recharts` 依赖 → 必须全部被 M1 抓到
  const m1Hits = checkNoDashboardRoutesAndLibs(
    appSrc + '\n<Route path="/metrics" element={<div />} />',
    [...pageNames, "MetricsDashboardPage.tsx"],
    { dependencies: { recharts: "3.8.0" } },
  );
  cases.push([
    "C5 反向对照：植入 /metrics 路由、MetricsDashboardPage.tsx 与 recharts → 三处均被 M1 抓到判红",
    m1Hits.length === 3,
    m1Hits.join("; "),
  ]);

  return cases;
}

function main() {
  for (const p of [APP_PATH, INLINE_PATH, QUEUE_PATH, CASE_PATH, REPORT_PATH, PKG_PATH]) {
    if (!fs.existsSync(p)) {
      console.error(`⚠ 未测：缺少文件 ${path.relative(REPO, p)}`);
      return 2;
    }
  }

  const appSrc = fs.readFileSync(APP_PATH, "utf8");
  const inlineSrc = fs.readFileSync(INLINE_PATH, "utf8");
  const queueSrc = fs.readFileSync(QUEUE_PATH, "utf8");
  const caseSrc = fs.readFileSync(CASE_PATH, "utf8");
  const reportSrc = fs.readFileSync(REPORT_PATH, "utf8");
  const pkgJson = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
  const pageNames = fs.readdirSync(path.join(WEB, "src/pages"));

  const problems = [
    ...checkNoDashboardRoutesAndLibs(appSrc, pageNames, pkgJson),
    ...checkThreePagesInlineSummary(inlineSrc, queueSrc, caseSrc, reportSrc),
    ...checkInlineSourceContract(inlineSrc),
  ];

  const controls = runControls(
    appSrc,
    pageNames,
    pkgJson,
    inlineSrc,
    queueSrc,
    caseSrc,
    reportSrc,
  );
  const failedControls = controls.filter(([, ok]) => !ok);

  console.log("==============================================================================");
  console.log("check_no_metrics_dashboard.mjs · #129 (TS-26) 无独立指标看板 + 三元摘要 + 七要素");
  console.log("==============================================================================");
  for (const [label, ok, detail] of controls) {
    console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
  }
  for (const p of problems) {
    console.log(`  ❌ ${p}`);
  }
  console.log("------------------------------------------------------------------------------");

  if (problems.length > 0 || failedControls.length > 0) {
    console.error(
      `❌ #129 未通过：主检查问题 ${problems.length} 项 · 反向对照失败 ${failedControls.length} 项`,
    );
    return 1;
  }
  console.log(`✅ 主检查 0 违规 + ${controls.length}/${controls.length} 项反向对照全过`);
  return 0;
}

process.exit(main());
