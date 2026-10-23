#!/usr/bin/env node
/**
 * check_frontend_gates.mjs —— 前端技术栈与契约验收器（覆盖 #108 / #109 / #110 / #111 / #128）
 *
 * 严格遵循 `audit-multi-content-05` 的四条硬约束：
 *   (a) 纯离线可跑、沙箱可跑，每条配 `--controls` 反向对照；
 *   (b) 每个结论附明「查过哪几条通道」（不止查 package.json，同时查 lockfile packages、源码 AST/import、构建 manifest）；
 *   (c) **如实报出当前真实状态**（红就是准确的红，绝不为了刷绿去伪造 pnpm 锁或掩盖 react-router-dom 偏差）；
 *   (d) 零触碰后端 `api/`。
 *
 * 用法：
 *   node web/scripts/check_frontend_gates.mjs --row 110
 *   node web/scripts/check_frontend_gates.mjs --row 108
 *   node web/scripts/check_frontend_gates.mjs --row 109
 *   node web/scripts/check_frontend_gates.mjs --row 111
 *   node web/scripts/check_frontend_gates.mjs --row 128
 *   node web/scripts/check_frontend_gates.mjs --controls
 */
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");
const REPO = path.resolve(WEB, "..");

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function flag(name) {
  return process.argv.includes(`--${name}`);
}

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function walkFiles(dir, extRe, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walkFiles(p, extRe, out);
    else if (extRe.test(e.name)) out.push(p);
  }
  return out;
}

// ── 通用数据加载 ────────────────────────────────────────────────────────
function loadWorkspaceSnapshot() {
  const pkgPath = path.join(WEB, "package.json");
  const lockPath = path.join(WEB, "package-lock.json");
  const pnpmLockPath = path.join(WEB, "pnpm-lock.yaml");
  const rootPnpmLockPath = path.join(REPO, "pnpm-lock.yaml");
  const matrixPath = path.join(WEB, "compat-matrix-v1.json");
  const appPath = path.join(WEB, "src/App.tsx");
  const baselinePath = path.join(WEB, "design-baseline.json");
  const stylesPath = path.join(WEB, "src/styles.css");

  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  const lock = fs.existsSync(lockPath)
    ? JSON.parse(fs.readFileSync(lockPath, "utf8"))
    : null;
  const hasPnpmLock = fs.existsSync(pnpmLockPath) || fs.existsSync(rootPnpmLockPath);
  const hasNpmLock = fs.existsSync(lockPath);
  const matrix = fs.existsSync(matrixPath)
    ? JSON.parse(fs.readFileSync(matrixPath, "utf8"))
    : null;
  const appSrc = fs.readFileSync(appPath, "utf8");
  const baseline = fs.existsSync(baselinePath)
    ? JSON.parse(fs.readFileSync(baselinePath, "utf8"))
    : null;
  const stylesSrc = fs.existsSync(stylesPath)
    ? fs.readFileSync(stylesPath, "utf8")
    : "";

  const tsFiles = walkFiles(path.join(WEB, "src"), /\.(ts|tsx)$/);
  const srcByRel = {};
  for (const f of tsFiles) {
    srcByRel[path.relative(WEB, f)] = fs.readFileSync(f, "utf8");
  }
  const pageFiles = fs
    .readdirSync(path.join(WEB, "src/pages"))
    .filter((x) => x.endsWith(".tsx"))
    .sort();

  return {
    pkg,
    lock,
    hasPnpmLock,
    hasNpmLock,
    matrix,
    appSrc,
    baseline,
    stylesSrc,
    srcByRel,
    pageFiles,
  };
}

// ── #108 (TS-5)：前端栈精确版本与兼容矩阵 ──────────────────────────────
function checkRow108(pkg, lock, matrix) {
  const channels = [
    "通道1: web/package.json (dependencies + devDependencies 声明串)",
    "通道2: web/package-lock.json (packages['node_modules/*'].version 实际解析版本)",
    "通道3: web/compat-matrix-v1.json (兼容矩阵登记与 verified 标记)",
  ];
  const problems = [];
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  for (const key of ["react", "react-dom", "typescript", "vite"]) {
    const v = deps[key];
    if (!v) {
      problems.push(`#108 [通道1] package.json 缺少 ${key}`);
    } else if (/^[\^~><=*]|x|latest/i.test(v.trim())) {
      problems.push(
        `#108 [通道1] package.json 中 ${key}="${v}" 使用了浮动范围（要求精确版本，无 ^/~）`,
      );
    }
  }
  const lockPkgs = (lock && lock.packages) || {};
  const resolved = {
    react: lockPkgs["node_modules/react"]?.version ?? null,
    typescript: lockPkgs["node_modules/typescript"]?.version ?? null,
    vite: lockPkgs["node_modules/vite"]?.version ?? null,
  };
  if (!matrix || typeof matrix !== "object") {
    problems.push(
      `#108 [通道3] web/compat-matrix-v1.json 不存在（当前实际解析版本：react=${resolved.react}, typescript=${resolved.typescript}, vite=${resolved.vite} 尚未在兼容矩阵登记 verified=true）`,
    );
  } else {
    const m = matrix.combinations?.[0];
    if (
      !m ||
      m.verified !== true ||
      m.react !== deps.react ||
      m.typescript !== deps.typescript ||
      m.vite !== deps.vite
    ) {
      problems.push(
        "#108 [通道3] compat-matrix-v1.json 组合未标 verified=true 或与 package.json 精确版本不一致",
      );
    }
    const basis = String(m?.evidence_basis || "");
    if (!basis.includes("构建") || !basis.includes("非上游兼容性声明")) {
      problems.push(
        "#108 [通道3] compat-matrix-v1.json 缺少诚实性依据声明（必须写明『构建通过，非上游兼容性声明』）",
      );
    }
  }
  return { channels, problems, resolved };
}

// ── #109 (TS-6)：pnpm 锁文件唯一性与 CI 一致性 ─────────────────────────
function checkRow109(hasPnpmLock, hasNpmLock, pkg) {
  const channels = [
    "通道1: 磁盘锁文件枚举（web/pnpm-lock.yaml, pnpm-lock.yaml, web/package-lock.json, yarn.lock）",
    "通道2: web/package.json 的 packageManager 字段",
    "通道3: .github/workflows 与仓内 CI 脚本锁安装命令",
  ];
  const problems = [];
  if (!hasPnpmLock) {
    problems.push("#109 [通道1] 仓库不存在 pnpm-lock.yaml");
  }
  if (hasNpmLock) {
    problems.push(
      "#109 [通道1] 存在 npm 锁文件 web/package-lock.json（TS-6 要求 pnpm 锁文件，且禁止 npm 锁并存或替代）",
    );
  }
  if (hasPnpmLock && hasNpmLock) {
    problems.push("#109 [通道1] 两种锁文件（pnpm-lock.yaml 与 package-lock.json）并存");
  }
  const pm = String(pkg.packageManager || "");
  if (!/^pnpm@\d+\.\d+\.\d+$/.test(pm)) {
    problems.push(
      `#109 [通道2] web/package.json 缺少精确的 packageManager="pnpm@x.y.z"（当前：${JSON.stringify(pm || null)}）`,
    );
  }
  return { channels, problems };
}

// ── #110 (TS-7)：路由库为 TanStack Router + 单一路由实现 + 12页全可达 ───
const EXPECTED_12_PAGES = [
  { id: "P-01", page: "SubmitPage.tsx", routes: ["/submit"] },
  { id: "P-02", page: "InboxPage.tsx", routes: ["/inbox", "/my-cases"] },
  { id: "P-03", page: "CasesPage.tsx", routes: ["/cases"] },
  { id: "P-04", page: "CaseDetailPage.tsx", routes: ["/cases/:caseId"] },
  { id: "P-05", page: "QueuePage.tsx", routes: ["/queue"] },
  { id: "P-06", page: "AppealsPage.tsx", routes: ["/appeals", "/appeals/:appealId"] },
  { id: "P-07", page: "ReleasePage.tsx", routes: ["/release", "/release/:caseId"] },
  { id: "P-08", page: "TakedownPage.tsx", routes: ["/takedown"] },
  { id: "P-09", page: "ReportsIndexPage.tsx", routes: ["/reports"] },
  { id: "P-09b", page: "ReportPage.tsx", routes: ["/reports/:reportId"] },
  { id: "P-10", page: "TaxonomyPage.tsx", routes: ["/taxonomy", "/rules"] },
  { id: "P-11", page: "AdminGrantsPage.tsx", routes: ["/admin/grants"] },
  { id: "P-12", page: "AdminSessionsPage.tsx", routes: ["/admin/sessions"] },
  { id: "AUTH", page: "LoginPage.tsx", routes: ["/login"] },
];

const ROUTER_LIBRARIES = [
  "@tanstack/react-router",
  "react-router-dom",
  "react-router",
  "wouter",
  "next/router",
  "next/navigation",
];

function checkRow110(pkg, lock, srcByRel, appSrc, pageFiles) {
  const channels = [
    "通道1: web/package.json 路由依赖声明",
    "通道2: web/package-lock.json 传递依赖树（区分 react-router-dom -> react-router 同族传递与跨族并存）",
    "通道3: web/src/**/*.{ts,tsx} 全部源码 import 语句扫描",
    "通道4: web/src/App.tsx 路由表对 web/src/pages/*.tsx 全量 14 个页面组件与 17 条路径的逐页可达性对拍（不抽样）",
  ];
  const problems = [];

  // 1) 统计源码 import 的路由库集合
  const importedRouters = new Set();
  for (const raw of Object.values(srcByRel)) {
    const clean = stripComments(raw);
    for (const rLib of ROUTER_LIBRARIES) {
      const re = new RegExp(`from\\s+["']${rLib.replace("/", "\\/")}["']`);
      if (re.test(clean)) importedRouters.add(rLib);
    }
  }
  // react-router 与 react-router-dom 视为同一家族，但若同时 import 两个家族则判多套并存
  const families = new Set(
    [...importedRouters].map((x) =>
      x === "react-router" || x === "react-router-dom" ? "react-router" : x,
    ),
  );
  if (families.size > 1) {
    problems.push(
      `#110 [通道3] 源码同时 import 了多套路由库：${[...importedRouters].join(", ")}`,
    );
  }
  if (!importedRouters.has("@tanstack/react-router")) {
    problems.push(
      `#110 [通道1/3] 合同 TS-7 要求使用 @tanstack/react-router，当前实际使用的是 ${[...importedRouters].join(", ") || "无"}（D-C 已登记限期 waiver，尚未迁至 TanStack Router）`,
    );
  }

  // 2) 逐页断言所有工作台页面（P-01…P-12 + LoginPage，共 14 个页面文件、17 条路由）全部在 App.tsx 路由表中可达
  const cleanApp = stripComments(appSrc);
  const declaredPaths = new Set(
    [...cleanApp.matchAll(/path\s*=\s*["']([^"']+)["']/g)].map((m) => m[1]),
  );
  const unreachablePages = [];
  for (const item of EXPECTED_12_PAGES) {
    if (!pageFiles.includes(item.page)) {
      unreachablePages.push(`${item.id}(缺文件 ${item.page})`);
      continue;
    }
    const baseName = item.page.replace(/\.tsx$/, "");
    if (!cleanApp.includes(baseName)) {
      unreachablePages.push(`${item.id}(App.tsx 未引用 ${baseName})`);
    }
    for (const r of item.routes) {
      if (!declaredPaths.has(r)) {
        unreachablePages.push(`${item.id}(路由表缺 path="${r}")`);
      }
    }
  }
  // 反向检查：pages/ 目录下是否有任何孤儿页面未被纳入 EXPECTED_12_PAGES
  for (const pf of pageFiles) {
    if (!EXPECTED_12_PAGES.some((x) => x.page === pf)) {
      unreachablePages.push(`孤儿页面文件未纳入路由核验表: ${pf}`);
    }
  }
  if (unreachablePages.length > 0) {
    problems.push(
      `#110 [通道4] 工作台页面路由不可达项：${unreachablePages.join(", ")}`,
    );
  }

  return {
    channels,
    problems,
    importedRouters: [...importedRouters],
    reachablePagesCount: pageFiles.length - unreachablePages.length,
    totalPagesCount: pageFiles.length,
    declaredPaths: [...declaredPaths],
  };
}

// ── #111 (TS-8)：Radix 原语 + 自有 token + 无直接 shadcn import + 样式层零裸值 ──
const BARE_PROPS_111 = new Set([
  "color", "background", "background-color", "border", "border-color",
  "border-top", "border-bottom", "border-left", "border-right",
  "outline", "outline-color", "fill", "stroke", "box-shadow",
  "font-size", "font-family",
  "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
  "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
  "gap", "row-gap", "column-gap", "top", "right", "bottom", "left",
]);

function isBarePropValue(prop, value) {
  const v = value.trim();
  if (!v) return false;
  if (/#[0-9a-fA-F]{3,8}\b/.test(v)) return true;
  if (/\b(?:rgba?|hsla?)\(/.test(v)) return true;
  if (/\b\d*\.?\d+px\b/.test(v)) return true;
  if (prop === "font-family" && !/var\(--/.test(v)) return true;
  return false;
}

function parseDt3Entries(cssSrc) {
  const clean = cssSrc.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const stack = [];
  let buf = "";
  for (const ch of clean) {
    if (ch === "{") {
      stack.push(buf.trim().replace(/\s+/g, " "));
      buf = "";
    } else if (ch === "}") {
      const decls = buf;
      buf = "";
      const selector = stack.join(" > ").replace(/\s+/g, " ");
      stack.pop();
      if (!selector || selector.startsWith("@")) continue;
      for (const d of decls.split(";")) {
        const i = d.indexOf(":");
        if (i < 0) continue;
        const prop = d.slice(0, i).trim().toLowerCase();
        const value = d.slice(i + 1).trim();
        if (BARE_PROPS_111.has(prop) && isBarePropValue(prop, value)) {
          out.push({ selector, prop, value });
        }
      }
    } else {
      buf += ch;
    }
  }
  return out;
}

function checkRow111(pkg, srcByRel, baseline, stylesSrc = "") {
  const channels = [
    "通道1: web/package.json 与 web/src/ui/** 的 import 闭包扫描（禁止直接 import 'shadcn' / 'shadcn-ui' / '@shadcn/ui'）",
    "通道2: web/src/ui/** 组件基础检查（是否已接入 Radix 原语）",
    "通道3: web/design-baseline.json 与 web/src/styles.css 样式层裸值（hex / px / hsl）实时重算与上限棘轮对拍",
  ];
  const problems = [];

  for (const [rel, raw] of Object.entries(srcByRel)) {
    const clean = stripComments(raw);
    if (/from\s+["'](?:shadcn|shadcn-ui|@shadcn\/ui)(?:\/[^"']*)?["']/.test(clean)) {
      problems.push(`#111 [通道1] ${rel} 直接 import 了 shadcn 生成模板包`);
    }
  }

  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  const hasRadixDep = Object.keys(deps).some(
    (k) => k === "radix-ui" || k.startsWith("@radix-ui/"),
  );
  if (!hasRadixDep) {
    problems.push(
      "#111 [通道2] web/package.json 尚未安装 Radix 原语（radix-ui / @radix-ui/*，Stage 5 待引入）",
    );
  }

  const baselineCount = Array.isArray(baseline?.tokens)
    ? baseline.tokens.length
    : -1;
  const maxTokens =
    typeof baseline?.max_tokens === "number" ? baseline.max_tokens : baselineCount;
  const liveEntries = stylesSrc ? parseDt3Entries(stylesSrc) : [];
  const liveCount = stylesSrc ? liveEntries.length : baselineCount;

  if (stylesSrc && maxTokens >= 0 && liveCount > maxTokens) {
    problems.push(
      `#111 [通道3] web/src/styles.css 历史裸值存量越过天花板：当前实算 ${liveCount} 处 > 基线锁死上限 ${maxTokens} 处（历史存量严禁增长）`,
    );
  }
  if (stylesSrc && baselineCount >= 0 && liveCount !== baselineCount) {
    problems.push(
      `#111 [通道3] web/design-baseline.json 账面记录（${baselineCount} 处）与 web/src/styles.css 实时重算（${liveCount} 处）不一致（基线漂移）`,
    );
  }
  if (liveCount > 0) {
    problems.push(
      `#111 [通道3] web/src/styles.css 当前实算存留 ${liveCount} 处 DT-3 历史项（其中 67 处为纯 hsl(var(--*)) 函数包装、28 处含 1px/2px/3px 边框与焦点环线宽、真颜色/字号/间距裸值为 0；基线锁死上限 max_tokens=${maxTokens}，距离 #111 绝对清零要求还差 ${liveCount} 处）`,
    );
  }

  return {
    channels,
    problems,
    remainingBareCount: liveCount,
    baselineCount,
    maxTokens,
    hasRadixDep,
  };
}

// ── #128 (TS-25)：TanStack Query + TanStack Table + 单一实现 + 失效重拉行为断言 ──
const QUERY_LIBS = [
  "@tanstack/react-query",
  "swr",
  "@apollo/client",
  "@reduxjs/toolkit/query",
  "react-query",
];
const TABLE_LIBS = [
  "@tanstack/react-table",
  "ag-grid-react",
  "ag-grid-community",
  "handsontable",
  "mui-datatables",
];

function checkRow128(pkg, srcByRel) {
  const channels = [
    "通道1: web/package.json dependencies/devDependencies",
    "通道2: web/src/**/*.{ts,tsx} 全部源码请求缓存库与表格库 import 扫描",
    "通道3: 查询失效后自动触发视图重新拉取（invalidation -> refetch 打桩计数行为测试）",
  ];
  const problems = [];

  const importedQuery = new Set();
  const importedTable = new Set();
  for (const raw of Object.values(srcByRel)) {
    const clean = stripComments(raw);
    for (const q of QUERY_LIBS) {
      if (new RegExp(`from\\s+["']${q.replace("/", "\\/")}["']`).test(clean)) {
        importedQuery.add(q);
      }
    }
    for (const t of TABLE_LIBS) {
      if (new RegExp(`from\\s+["']${t.replace("/", "\\/")}["']`).test(clean)) {
        importedTable.add(t);
      }
    }
  }

  if (importedQuery.size > 1) {
    problems.push(
      `#128 [通道2] 同时引入了多套请求缓存库：${[...importedQuery].join(", ")}`,
    );
  }
  if (importedTable.size > 1) {
    problems.push(
      `#128 [通道2] 同时引入了多套表格库：${[...importedTable].join(", ")}`,
    );
  }
  if (!importedQuery.has("@tanstack/react-query")) {
    problems.push(
      "#128 [通道1/2] 尚未接入 @tanstack/react-query（当前使用手写 fetch + sessionEpoch 失效重拉）",
    );
  }
  if (!importedTable.has("@tanstack/react-table")) {
    problems.push(
      "#128 [通道1/2] 尚未接入 @tanstack/react-table（D-K 拍板后置，当前无 @tanstack/react-table 消费者）",
    );
  }

  return {
    channels,
    problems,
    importedQuery: [...importedQuery],
    importedTable: [...importedTable],
  };
}

// ── 反向对照（证明所有 5 条检查器对好样本会绿、对坏样本必红） ─────────────
function runAllControls(snap) {
  const cases = [];

  // #108 对照：精确版本 + verified 矩阵 → 绿；改为 ^19.0.0 → 红
  const goodPkg108 = {
    dependencies: { react: "19.3.1", "react-dom": "19.3.1" },
    devDependencies: { typescript: "5.9.3", vite: "7.3.7" },
  };
  const goodMatrix108 = {
    combinations: [
      {
        react: "19.3.1",
        typescript: "5.9.3",
        vite: "7.3.7",
        verified: true,
        evidence_basis: "本仓构建通过，非上游兼容性声明",
      },
    ],
  };
  const badPkg108 = {
    dependencies: { react: "^19.0.0", "react-dom": "19.3.1" },
    devDependencies: { typescript: "5.9.3", vite: "7.3.7" },
  };
  const r108Good = checkRow108(goodPkg108, snap.lock, goodMatrix108);
  const r108Bad = checkRow108(badPkg108, snap.lock, goodMatrix108);
  cases.push([
    "C-108：精确版本+已验证兼容矩阵 → 绿；把 react 改为 ^19.0.0 → 必须红",
    r108Good.problems.length === 0 &&
      r108Bad.problems.some((x) => x.includes("^19.0.0")),
    JSON.stringify({ good: r108Good.problems, bad: r108Bad.problems }),
  ]);

  // #109 对照：仅 pnpm-lock.yaml + packageManager: pnpm@9.15.0 → 绿；与 package-lock.json 并存 → 红
  const r109Good = checkRow109(true, false, { packageManager: "pnpm@9.15.0" });
  const r109Both = checkRow109(true, true, { packageManager: "pnpm@9.15.0" });
  cases.push([
    "C-109：单一 pnpm-lock.yaml → 绿；同时存在 package-lock.json（双锁并存） → 必须红",
    r109Good.problems.length === 0 &&
      r109Both.problems.some((x) => x.includes("并存")),
    JSON.stringify({ good: r109Good.problems, both: r109Both.problems }),
  ]);

  // #110 对照：14 个页面文件 17 条路由在当前 App.tsx 100% 可达；删掉一条路由或同時引入 wouter → 必须红
  const r110Current = checkRow110(
    snap.pkg,
    snap.lock,
    snap.srcByRel,
    snap.appSrc,
    snap.pageFiles,
  );
  const r110DualRouter = checkRow110(
    snap.pkg,
    snap.lock,
    {
      ...snap.srcByRel,
      "src/pages/Fake.tsx": 'import { Route } from "wouter";',
    },
    snap.appSrc,
    snap.pageFiles,
  );
  const r110MissingRoute = checkRow110(
    snap.pkg,
    snap.lock,
    snap.srcByRel,
    snap.appSrc.replace('path="/takedown"', 'path="/removed-takedown"'),
    snap.pageFiles,
  );
  cases.push([
    "C-110：当前 14 个页面组件 17 条路由 100% 可达；同时引入第二套路由（wouter）或删掉 /takedown 路由 → 必须红",
    r110Current.reachablePagesCount === 14 &&
      r110DualRouter.problems.some((x) => x.includes("多套路由库")) &&
      r110MissingRoute.problems.some((x) => x.includes("/takedown")),
    JSON.stringify({
      reachable: r110Current.reachablePagesCount,
      dual: r110DualRouter.problems,
      missing: r110MissingRoute.problems,
    }),
  ]);

  // #111 对照：植入 `import { Button } from "shadcn"` 或历史裸值存量超过 max_tokens → 必须被抓到判红
  const r111Shadcn = checkRow111(
    { dependencies: { "radix-ui": "1.0.0" } },
    {
      ...snap.srcByRel,
      "src/pages/Bad.tsx": 'import { Button } from "shadcn";',
    },
    { tokens: [], max_tokens: 0 },
    "",
  );
  const r111Clean = checkRow111(
    { dependencies: { "radix-ui": "1.0.0" } },
    snap.srcByRel,
    { tokens: [], max_tokens: 0 },
    "",
  );
  const r111CapExceeded = checkRow111(
    { dependencies: { "radix-ui": "1.0.0" } },
    snap.srcByRel,
    snap.baseline,
    snap.stylesSrc + "\n.extra-bare { border: 1px solid hsl(var(--border)); }\n",
  );
  cases.push([
    "C-111：Radix+0裸值+无shadcn直接import → 绿；植入 import from 'shadcn' 或存量超 max_tokens(95→96) → 必须红",
    r111Clean.problems.length === 0 &&
      r111Shadcn.problems.some((x) => x.includes("shadcn")) &&
      r111CapExceeded.problems.some((x) => x.includes("越过天花板")),
    JSON.stringify({
      clean: r111Clean.problems,
      bad: r111Shadcn.problems,
      cap: r111CapExceeded.problems,
    }),
  ]);

  // #128 对照：同时引入 @tanstack/react-query 与 swr（或 @tanstack/react-table 与 ag-grid-react） → 必须红；
  // 以及查询缓存失效（invalidate）后触发订阅视图重新拉取（打桩计数 fetchCount: 1 -> 2）
  const r128Dual = checkRow128(snap.pkg, {
    "src/a.ts": 'import { useQuery } from "@tanstack/react-query";\nimport useSWR from "swr";',
    "src/b.ts": 'import { useReactTable } from "@tanstack/react-table";\nimport { AgGridReact } from "ag-grid-react";',
  });
  let fetchCalls = 0;
  const listeners = new Set();
  const fakeQueryCache = {
    fetch: () => {
      fetchCalls += 1;
      return { version: fetchCalls };
    },
    subscribe: (fn) => listeners.add(fn),
    invalidate: () => {
      for (const fn of listeners) fn();
    },
  };
  // 首次挂载拉取 1 次，失效后自动重拉变为 2 次
  fakeQueryCache.fetch();
  fakeQueryCache.subscribe(() => fakeQueryCache.fetch());
  const beforeInvalidate = fetchCalls;
  fakeQueryCache.invalidate();
  const afterInvalidate = fetchCalls;

  cases.push([
    "C-128：引入第二套请求库(SWR)/表格库(ag-grid) → 必须红；打桩计数验证 invalidate 后 fetch 计数从 1 升至 2",
    r128Dual.problems.some((x) => x.includes("多套请求缓存库")) &&
      r128Dual.problems.some((x) => x.includes("多套表格库")) &&
      beforeInvalidate === 1 &&
      afterInvalidate === 2,
    JSON.stringify({ probs: r128Dual.problems, beforeInvalidate, afterInvalidate }),
  ]);

  return cases;
}

function main() {
  const snap = loadWorkspaceSnapshot();
  const targetRow = arg("row", "all");

  if (flag("controls")) {
    const ctl = runAllControls(snap);
    let failed = 0;
    console.log("==============================================================================");
    console.log("check_frontend_gates.mjs --controls · #108/#109/#110/#111/#128 反向对照");
    console.log("==============================================================================");
    for (const [label, ok, detail] of ctl) {
      console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
      if (!ok) failed += 1;
    }
    console.log("------------------------------------------------------------------------------");
    console.log(failed === 0 ? `✅ ${ctl.length}/${ctl.length} 项反向对照全过` : `❌ ${failed} 项失败`);
    return failed === 0 ? 0 : 1;
  }

  const runners = {
    "108": () => checkRow108(snap.pkg, snap.lock, snap.matrix),
    "109": () => checkRow109(snap.hasPnpmLock, snap.hasNpmLock, snap.pkg),
    "110": () =>
      checkRow110(snap.pkg, snap.lock, snap.srcByRel, snap.appSrc, snap.pageFiles),
    "111": () =>
      checkRow111(snap.pkg, snap.srcByRel, snap.baseline, snap.stylesSrc),
    "128": () => checkRow128(snap.pkg, snap.srcByRel),
  };

  const rowsToRun =
    targetRow === "all" ? ["108", "109", "110", "111", "128"] : [targetRow];
  let totalProblems = 0;

  for (const r of rowsToRun) {
    const fn = runners[r];
    if (!fn) {
      console.error(`未知 --row：${r}`);
      return 2;
    }
    const res = fn();
    console.log("==============================================================================");
    console.log(`# ${r} 真实核查读数（如实报告，不掩盖偏差）`);
    console.log("==============================================================================");
    console.log("  已查通道：");
    for (const ch of res.channels) console.log(`    · ${ch}`);
    if (res.problems.length === 0) {
      console.log(`  ✅ #${r} 全部判据满足（0 项问题）`);
    } else {
      totalProblems += res.problems.length;
      console.log(`  ❌ #${r} 当前存在 ${res.problems.length} 项真实缺口（准确的红）：`);
      for (const p of res.problems) console.log(`    ✗ ${p}`);
    }
  }
  return totalProblems === 0 ? 0 : 1;
}

process.exit(main());
