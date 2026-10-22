#!/usr/bin/env node
/**
 * check_a11y_dual_gate.mjs —— #112 (TS-9) WCAG 2.2 AA 自动扫描 + 关键流程人工核验双半边门
 *
 * 为什么要有本脚本（对应 05 对 T-112 的要求）：
 *   验收表 #112 明写：「① 对全部工作台页面跑自动扫描，断言 0 个 serious/critical 违规；
 *   ② 人工核验关键流程（登录、复核、申诉、签发、撤回）的键盘可达性、读屏可读性、焦点顺序、
 *   对比度、目标尺寸、认证流程可访问性，逐项留存核验人/时间/结论。**两者缺一不可**。」
 *
 * 本脚本把这两半**分开计量、合起来判退出码**：
 *   1. **机器半边（Machine Half）**：
 *      - 集合恒等核验：比较 `web/src/pages/*.tsx` 全量 14 个工作台页面文件与
 *        `web/scripts/dev-up.sh` 中 `a11y_check.mjs --pages` 的扫描集合：
 *        - 已覆盖的 13 个页面组件：`SubmitPage`, `InboxPage`, `QueuePage`, `CasesPage`, `CaseDetailPage`,
 *          `AppealsPage`, `ReleasePage`, `TakedownPage`, `ReportsIndexPage`, `ReportPage`,
 *          `TaxonomyPage`, `AdminGrantsPage`, `AdminSessionsPage`（共 14 条路由 URL）；
 *        - **发现 1 处集合差（如实报出）**：`LoginPage.tsx`（`/login`）此前不在 `dev-up.sh` 的 `--pages` 列表里！
 *          （已在本次补齐进 `dev-up.sh` 与 `a11y_check.mjs --standalone`，使两者集合 14/14 完全相等）。
 *      - 实跑 `node web/scripts/a11y_check.mjs --standalone`（含 C1–C5 对照与真实 CSS 双视口 13 项 AA 审计）。
 *   2. **人工半边（Manual Half）**：
 *      - 读取 `web/a11y-manual-v1.json`，逐条核对 9 项人工核验记录（`status ∈ {signed, done}` 且 `evidence/owner/date` 齐全）；
 *      - **绝不伪造人工核验签收记录**：当前 9 项均为 `status: "not_run"`，如实落 `untested`。
 *   3. **合流退出码（两者缺一不可）**：
 *      - 机器半边有违规 或 人工台账结构损坏 → **退 1（failed / 红）**；
 *      - 机器半边 0 违规，但人工半边有未签收项 → **退 2（untested / 未测）**，绝不因机器半边全绿就退 0 报 passed！
 *      - 只有机器半边 0 违规 **且** 人工半边全部真实签收 → 才退 0（passed）。
 *
 * 用法：
 *   node web/scripts/check_a11y_dual_gate.mjs
 *   node web/scripts/check_a11y_dual_gate.mjs --controls
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");

function flag(n) {
  return process.argv.includes(`--${n}`);
}

const PAGE_TO_ROUTE_MAP = [
  { file: "LoginPage.tsx", route: "/login" },
  { file: "SubmitPage.tsx", route: "/submit" },
  { file: "InboxPage.tsx", route: "/inbox" },
  { file: "QueuePage.tsx", route: "/queue" },
  { file: "CasesPage.tsx", route: "/cases" },
  { file: "CaseDetailPage.tsx", route: "/cases/${FIRST_CASE}" },
  { file: "AppealsPage.tsx", route: "/appeals" },
  { file: "ReleasePage.tsx", route: "/release" },
  { file: "TakedownPage.tsx", route: "/takedown" },
  { file: "ReportsIndexPage.tsx", route: "/reports" },
  { file: "ReportPage.tsx", route: "/reports/report-smoke" },
  { file: "TaxonomyPage.tsx", route: "/taxonomy" },
  { file: "AdminGrantsPage.tsx", route: "/admin/grants" },
  { file: "AdminSessionsPage.tsx", route: "/admin/sessions" },
];

function checkPageCoverage(devUpSrc, diskPages) {
  const m = devUpSrc.match(/--pages\s+"([^"]+)"/);
  const configuredRoutes = m
    ? m[1].split(",").map((s) => s.trim()).filter(Boolean)
    : [];
  const missingInDevUp = [];
  for (const item of PAGE_TO_ROUTE_MAP) {
    if (!diskPages.includes(item.file)) {
      missingInDevUp.push(`磁盘缺少页面文件 ${item.file}`);
    } else if (!configuredRoutes.includes(item.route)) {
      missingInDevUp.push(`${item.file} 对应的路由 ${item.route} 未纳入 dev-up.sh --pages`);
    }
  }
  for (const df of diskPages) {
    if (!PAGE_TO_ROUTE_MAP.some((x) => x.file === df)) {
      missingInDevUp.push(`新增页面文件 ${df} 未登记进 #112 页面覆盖表`);
    }
  }
  return {
    configuredRoutes,
    diskPagesCount: diskPages.length,
    missingInDevUp,
  };
}

function evaluateManualLedger(doc) {
  const reds = [];
  const untested = [];
  if (!doc || typeof doc !== "object") {
    return { reds: ["a11y-manual-v1.json 不是合法对象"], untested, signed: 0, total: 0 };
  }
  const items = doc.items;
  if (!Array.isArray(items) || items.length === 0) {
    return { reds: ["a11y-manual-v1.json items 为空"], untested, signed: 0, total: 0 };
  }
  const accept = new Set(doc.accept_status || ["signed", "done"]);
  let signed = 0;
  for (const it of items) {
    const id = String(it.item || "").trim();
    const missingFields = ["evidence", "owner", "date"].filter(
      (k) => !String(it[k] || "").trim(),
    );
    if (!accept.has(String(it.status || ""))) {
      untested.push(`${id} (status=${it.status || "not_run"}, 待人工核验签收)`);
      continue;
    }
    if (missingFields.length > 0) {
      reds.push(`${id} 标为 ${it.status} 但缺少必填签收字段：${missingFields.join("/")}`);
      continue;
    }
    signed += 1;
  }
  return { reds, untested, signed, total: items.length };
}

/**
 * 纯决策函数：把机器半边与人工半边合成为最终三态退出码（0=passed, 1=failed, 2=untested）。
 */
function combineVerdict(machineOk, coverageMissing, manualResult) {
  if (!machineOk || coverageMissing.length > 0 || manualResult.reds.length > 0) {
    return { exitCode: 1, state: "failed" };
  }
  if (manualResult.untested.length > 0) {
    // ★ 核心约束：哪怕机器半边 0 违规，只要人工半边未签收，整体绝不许退 0（passed），必须退 2（untested）
    return { exitCode: 2, state: "untested" };
  }
  return { exitCode: 0, state: "passed" };
}

function runControls() {
  const cases = [];

  // C1 机器半边绿 + 人工半边未签收 → 必须退 2（untested），绝不能退 0（防机器半边掩盖人工半边）
  const v1 = combineVerdict(true, [], {
    reds: [],
    untested: ["keyboard-flow (status=not_run)"],
    signed: 8,
    total: 9,
  });
  cases.push([
    "C1 ★ 机器半边全绿 + 人工半边有未签收项 → 必须退 2（untested），绝不报 passed(0)",
    v1.exitCode === 2 && v1.state === "untested",
    JSON.stringify(v1),
  ]);

  // C2 机器半边红 + 人工半边全签收 → 必须退 1（failed）
  const v2 = combineVerdict(false, [], {
    reds: [],
    untested: [],
    signed: 9,
    total: 9,
  });
  cases.push([
    "C2 机器半边有违规 + 人工半边全签收 → 必须退 1（failed）",
    v2.exitCode === 1 && v2.state === "failed",
    JSON.stringify(v2),
  ]);

  // C3 页面覆盖漏掉 LoginPage.tsx → 必须退 1（failed）
  const v3 = combineVerdict(true, ["LoginPage.tsx 对应的路由 /login 未纳入"], {
    reds: [],
    untested: [],
    signed: 9,
    total: 9,
  });
  cases.push([
    "C3 页面扫描集合漏掉任一工作台页面（如 LoginPage.tsx） → 必须退 1（failed）",
    v3.exitCode === 1,
    JSON.stringify(v3),
  ]);

  // C4 人工台账假签收（标了 signed 但没填 evidence/owner/date）→ 必须退 1（failed）
  const fakeManual = evaluateManualLedger({
    accept_status: ["signed"],
    items: [{ item: "keyboard-flow", status: "signed", evidence: "", owner: "u", date: "" }],
  });
  const v4 = combineVerdict(true, [], fakeManual);
  cases.push([
    "C4 人工台账标 signed 但缺 evidence/date → 必须退 1（failed，防空头签收）",
    v4.exitCode === 1 && fakeManual.reds.length === 1,
    JSON.stringify(fakeManual),
  ]);

  // C5 机器半边全绿 + 14页全覆盖 + 人工半边 9 项证据/责任人/日期齐全 → 退 0（passed）
  const fullManual = evaluateManualLedger({
    accept_status: ["signed"],
    items: [{ item: "keyboard-flow", status: "signed", evidence: "vo.mp4", owner: "qa", date: "2026-10-23" }],
  });
  const v5 = combineVerdict(true, [], fullManual);
  cases.push([
    "C5 机器半边全绿 + 14页集合对齐 + 人工半边完整签收 → 退 0（passed）",
    v5.exitCode === 0 && v5.state === "passed",
    JSON.stringify(v5),
  ]);

  return cases;
}

function main() {
  if (flag("controls")) {
    const ctl = runControls();
    let failed = 0;
    console.log("==============================================================================");
    console.log("check_a11y_dual_gate.mjs --controls · #112 (TS-9) 机器+人工双半边门反向对照");
    console.log("==============================================================================");
    for (const [label, ok, detail] of ctl) {
      console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
      if (!ok) failed += 1;
    }
    console.log("------------------------------------------------------------------------------");
    console.log(failed === 0 ? `✅ ${ctl.length}/${ctl.length} 项反向对照全过` : `❌ ${failed} 项失败`);
    return failed === 0 ? 0 : 1;
  }

  const devUpSrc = fs.readFileSync(path.join(WEB, "scripts/dev-up.sh"), "utf8");
  const diskPages = fs
    .readdirSync(path.join(WEB, "src/pages"))
    .filter((x) => x.endsWith(".tsx"))
    .sort();
  const cov = checkPageCoverage(devUpSrc, diskPages);

  let machineOk = false;
  let machineSummary = "";
  try {
    const out = execFileSync(
      "node",
      [path.join(WEB, "scripts/a11y_check.mjs"), "--standalone"],
      { encoding: "utf8", timeout: 25000 },
    );
    machineOk = true;
    machineSummary = out.trim().split("\n").pop() || "通过";
  } catch (e) {
    machineOk = false;
    machineSummary = e instanceof Error ? e.message : String(e);
  }

  const manualDoc = JSON.parse(
    fs.readFileSync(path.join(WEB, "a11y-manual-v1.json"), "utf8"),
  );
  const manualRes = evaluateManualLedger(manualDoc);
  const verdict = combineVerdict(machineOk, cov.missingInDevUp, manualRes);

  console.log("==============================================================================");
  console.log("check_a11y_dual_gate.mjs · #112 (TS-9) 自动扫描 + 关键流程人工核验（两者缺一不可）");
  console.log("==============================================================================");
  console.log(
    `  [机器半边] 页面集合覆盖：磁盘 ${cov.diskPagesCount} 个页面组件 ↔ dev-up 扫描 ${cov.configuredRoutes.length} 条路由（缺漏 ${cov.missingInDevUp.length} 项）`,
  );
  for (const miss of cov.missingInDevUp) {
    console.log(`    ✗ 集合差：${miss}`);
  }
  console.log(
    `  [机器半边] a11y_check.mjs --standalone：${machineOk ? "✅ 0 违规（" + machineSummary + "）" : "❌ 失败（" + machineSummary + "）"}`,
  );
  console.log(
    `  [人工半边] a11y-manual-v1.json：共 ${manualRes.total} 项 · 已签收 ${manualRes.signed} 项 · 待真人核验签收 ${manualRes.untested.length} 项`,
  );
  for (const u of manualRes.untested) {
    console.log(`    ⚠ 未测：${u}`);
  }
  for (const r of manualRes.reds) {
    console.log(`    ✗ 台账错误：${r}`);
  }
  console.log("------------------------------------------------------------------------------");
  console.log(
    `结论：机器半边 ${machineOk && cov.missingInDevUp.length === 0 ? "0 违规（绿）" : "有缺口（红）"} / 人工半边 ${manualRes.untested.length} 项待真人签收（未测） → 综合状态=${verdict.state} (rc=${verdict.exitCode})`,
  );
  return verdict.exitCode;
}

process.exit(main());
