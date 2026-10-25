#!/usr/bin/env node
/**
 * verify_frontend_stack_contract.mjs —— 前端技术栈契约的执行点（#109 / #110 / #111 / #128）
 *
 * 为什么单独有这个文件，而不是直接接 `check_frontend_gates.mjs`：
 *   那支检查器把「今天就能判的」与「必须等 T-333 才成立的」混在同一个退出码里，
 *   于是四行都恒定退 1。恒红的断言等于没有断言 —— 它会被人无视（AGENTS.md §2.4 同款）。
 *
 * 本文件把每条断言显式分成两类：
 *
 *   A 类（今天就能建成真判据）：不依赖迁移是否发生，删掉被断言的代码就必红。
 *   B 类（必须等迁移）：断言「必须是 TanStack Router / pnpm / Radix / TanStack Query·Table」。
 *        今天断言它**必红**，且**红得没有信息量** —— 因为偏差是被书面接受的现状，
 *        不是新出现的问题。所以 B 类不许计入红，也不许计入绿，只落**未测**。
 *
 * 三态退出码（全项目约定，见 tools/verify_acceptance_run.py 的 docstring）：
 *   0 = A 类全绿 且 B 类也全部满足（迁移已完成）
 *   1 = A 类有红（真的坏了，该有人去改代码）
 *   2 = A 类全绿，但 B 类仍被阻断 —— **未测 ≠ 通过 ≠ 红**
 *
 * ★ 为什么 B 类退 2 而不是退 1：`untested` 到 `passed` 之间隔着一次迁移，
 *   而 `failed` 的意思是「验了不通过」。把「还没迁」记成「验不过」，
 *   会让这四行永远红着，红到没人再看它 —— 这正是本项目 §2.4 点名过的病。
 *
 * B 类阻断还必须**指得出凭据**：每条 B 断言会去 `PMO/audit/waiver-v1.json` 里
 * 找一条真的点名了它的豁免。找不到 → 仍然退 2，但结论行明确标「⚠ 无豁免凭据」，
 * 因为「等迁移」与「有人书面同意等迁移」是两件事，后者才有到期日。
 *
 * 用法：
 *   node web/scripts/verify_frontend_stack_contract.mjs                  # 全跑
 *   node web/scripts/verify_frontend_stack_contract.mjs --row 110
 *   node web/scripts/verify_frontend_stack_contract.mjs --controls       # 反向对照
 *   node web/scripts/verify_frontend_stack_contract.mjs --root <dir>     # 对 fixture 树跑（自证用）
 *   node web/scripts/verify_frontend_stack_contract.mjs --json
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
// DT-3 裸值判据的**唯一实现**。行 111 不另写一份 —— 同一判断只许有一处实现（AGENTS.md §2.5）。
import { parseBareEntries } from "./dt3-bare.mjs";

const HERE = path.dirname(new URL(import.meta.url).pathname);

// ── 小工具 ───────────────────────────────────────────────────────────────
function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function flag(name) {
  return process.argv.includes(`--${name}`);
}
function readText(p) {
  try {
    return fs.readFileSync(p, "utf8");
  } catch {
    return null;
  }
}
function readJson(p) {
  const t = readText(p);
  if (t === null) return null;
  try {
    return JSON.parse(t);
  } catch {
    return "PARSE_ERROR";
  }
}
/** 整行注释不算代码 —— 与 verify_shouheng_ops.py 的 C5 / verify_cards.mjs 的 J1a 同一条读法。 */
function stripComments(src) {
  return String(src)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}
function walk(dir, extRe, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, extRe, out);
    else if (extRe.test(e.name)) out.push(p);
  }
  return out;
}

// ── 快照：一次读齐，通道写清楚（不只查 package.json）────────────────────
const ROUTER_FAMILIES = [
  { lib: "@tanstack/react-router", family: "@tanstack/react-router" },
  // react-router 与 react-router-dom 是同一套实现的两种包名，算同族。
  { lib: "react-router-dom", family: "react-router" },
  { lib: "react-router", family: "react-router" },
  { lib: "wouter", family: "wouter" },
  { lib: "next/navigation", family: "next" },
  { lib: "next/router", family: "next" },
  { lib: "@reach/router", family: "@reach/router" },
];
const QUERY_LIBS = [
  "@tanstack/react-query",
  "react-query",
  "swr",
  "@apollo/client",
  "@urql/core",
  "@reduxjs/toolkit/query",
];
const TABLE_LIBS = [
  "@tanstack/react-table",
  "ag-grid-react",
  "ag-grid-community",
  "handsontable",
  "mui-datatables",
  "react-data-table-component",
];
const SHADCN_LIBS = ["shadcn", "shadcn-ui", "@shadcn/ui"];

function loadSnapshot(root) {
  const webDir = path.join(root, "web");
  const pkg = readJson(path.join(webDir, "package.json"));
  const ciDir = path.join(root, ".github", "workflows");

  const srcByRel = {};
  for (const f of walk(path.join(webDir, "src"), /\.(ts|tsx)$/)) {
    srcByRel[path.relative(webDir, f)] = readText(f) || "";
  }
  const pagesDir = path.join(webDir, "src", "pages");
  const pageFiles = fs.existsSync(pagesDir)
    ? fs.readdirSync(pagesDir).filter((x) => x.endsWith(".tsx")).sort()
    : [];

  return {
    root,
    webDir,
    pkg: pkg && pkg !== "PARSE_ERROR" ? pkg : null,
    pkgBroken: pkg === "PARSE_ERROR",
    lockNpm: fs.existsSync(path.join(webDir, "package-lock.json")),
    lockNpmTools: fs.existsSync(path.join(root, "tools", "package-lock.json")),
    lockPnpmWeb: fs.existsSync(path.join(webDir, "pnpm-lock.yaml")),
    lockPnpmRoot: fs.existsSync(path.join(root, "pnpm-lock.yaml")),
    lockYarnWeb: fs.existsSync(path.join(webDir, "yarn.lock")),
    lockShrinkwrap: fs.existsSync(path.join(webDir, "npm-shrinkwrap.json")),
    ciFiles: fs.existsSync(ciDir)
      ? fs.readdirSync(ciDir).filter((x) => /\.ya?ml$/.test(x)).sort()
      : [],
    ciDir,
    srcByRel,
    pageFiles,
    appSrc: readText(path.join(webDir, "src", "App.tsx")) || "",
    stylesSrc: readText(path.join(webDir, "src", "styles.css")) || "",
    baseline: readJson(path.join(webDir, "design-baseline.json")),
    waivers: readJson(path.join(root, "PMO", "audit", "waiver-v1.json")),
  };
}

function depsOf(pkg) {
  return pkg ? { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) } : {};
}

/** 源码里出现的某个库（整行注释已剥掉）。 */
function importedLibs(srcByRel, libs) {
  const hit = new Set();
  for (const raw of Object.values(srcByRel)) {
    const clean = stripComments(raw);
    for (const lib of libs) {
      const escaped = lib.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
      if (new RegExp(`from\\s+["']${escaped}["']`).test(clean)) hit.add(lib);
    }
  }
  return hit;
}

// ── 断言记录 ─────────────────────────────────────────────────────────────
// state: "pass" | "fail" | "blocked"（B 类未达成）| "untested"（环境读不到）
function A(id, label, ok, detail) {
  return { id, cls: "A", state: ok ? "pass" : "fail", label, detail: detail || "" };
}
function B(id, label, ok, detail) {
  // 凭据只在**阻断**时才有意义；已满足时写它出来会自相矛盾
  // （实测：表格库已装 @tanstack/react-table，详情却仍写「无豁免凭据」）。
  return { id, cls: "B", state: ok ? "pass" : "blocked", label, detail: ok ? "" : detail || "" };
}

/** B 类已满足时的读数（不掺豁免措辞）。 */
function bPassed(id, label, detail) {
  return { id, cls: "B", state: "pass", label, detail };
}
function U(id, cls, label, why) {
  return { id, cls, state: "untested", label, detail: why };
}

// ── B 类凭据：去豁免台账里找一条真的点名了它的 ──────────────────────────
// 判据是**逐字**：豁免的 item/理由 里必须出现该 token。
// 不做模糊匹配（AGENTS.md §2.6 第 3 条：模糊匹配会误报，误报比不报更糟）。
function waiverFor(snap, token) {
  const w = snap.waivers;
  if (!w || w === "PARSE_ERROR" || !Array.isArray(w.items)) return null;
  const today = new Date().toISOString().slice(0, 10);
  for (const it of w.items) {
    if (it["状态"] !== "active") continue;
    const hay = `${it.item || ""} ${it["理由"] || ""} ${it.ticket || ""}`;
    if (!hay.includes(token)) continue;
    const due = String(it["到期日"] || "");
    return { id: it.id, due, expired: due ? today >= due : false };
  }
  return null;
}
function blockedDetail(snap, token, what) {
  const w = waiverFor(snap, token);
  if (!w) return `${what}（⚠ 无豁免凭据：waiver-v1.json 里没有一条 active 豁免逐字点名「${token}」）`;
  if (w.expired) return `${what}（豁免 ${w.id} 已于 ${w.due} 到期 —— 该重做决定，不是继续等）`;
  return `${what}（豁免 ${w.id}，到期 ${w.due}）`;
}

// ══ #109 (TS-6)：依赖锁定，开发与 CI 一致 ═══════════════════════════════
//
// 验收原话有两半：
//   ① 「仓库有 pnpm 锁文件且 CI 使用同一份」      → B 类（今天没有 pnpm 锁）
//   ② 「两种锁文件并存即红」+「删掉锁文件后安装必须失败」→ A 类（与用哪个包管理器无关）
function check109(snap) {
  const out = [];
  const a = [];

  // A1：每个 lock root 恰好一种锁文件族。并存即红 —— 这是验收原话点名的形状。
  const webFamilies = [];
  if (snap.lockNpm || snap.lockShrinkwrap) webFamilies.push("npm");
  if (snap.lockPnpmWeb || snap.lockPnpmRoot) webFamilies.push("pnpm");
  if (snap.lockYarnWeb) webFamilies.push("yarn");
  a.push(
    A(
      "109/A1",
      "web 只有一个锁文件族（npm / pnpm / yarn 不得并存）",
      webFamilies.length === 1,
      webFamilies.length === 0
        ? "没有任何锁文件 —— 依赖未锁定"
        : webFamilies.length > 1
          ? `并存：${webFamilies.join(" + ")}`
          : `唯一族：${webFamilies[0]}`,
    ),
  );

  // A2：CI 的安装命令必须与实际存在的锁族一致。
  const ciText = snap.ciFiles
    .map((f) => readText(path.join(snap.ciDir, f)) || "")
    .join("\n");
  const ciInstall = [
    ["npm", /\bnpm\s+(ci|install)\b/g],
    ["pnpm", /\bpnpm\s+(install|i|ci)\b/g],
    ["yarn", /\byarn(\s+install)?\b/g],
  ]
    .flatMap(([mgr, re]) => [...stripComments(ciText).matchAll(re)].map(() => mgr));
  const ciManagers = [...new Set(ciInstall)];
  if (!ciText) {
    out.push(U("109/A2", "A", "CI 安装命令与锁族一致", "读不到 .github/workflows"));
  } else if (ciManagers.length === 0) {
    out.push(U("109/A2", "A", "CI 安装命令与锁族一致", "CI 里没有任何安装命令可判"));
  } else {
    const agrees =
      webFamilies.length === 1 && ciManagers.length === 1 && ciManagers[0] === webFamilies[0];
    out.push(
      A(
        "109/A2",
        "CI 安装命令与锁族一致",
        agrees,
        `CI=${ciManagers.join("+") || "无"} / 锁族=${webFamilies.join("+") || "无"}`,
      ),
    );
  }

  // A3（行为）：干净环境里删掉锁文件后，**CI 实际用的那条安装命令**必须失败。
  //
  // ★ 用差分判据，不用绝对判据：同一份环境、同一份 package.json，只改「有没有锁」。
  //   若两次都失败 → 环境问题（离线缓存缺失等），落未测，不许当成「锁在生效」；
  //   若两次都成功 → 锁根本没起作用，才是红。
  //   绝对判据会被缓存状态骗（实测过：--offline 有缓存时连无锁也能装上）。
  const behavior = lockEnforced(snap, webFamilies.length === 1 ? webFamilies[0] : null);
  out.push(behavior);

  out.push(
    B(
      "109/B1",
      "锁文件为 pnpm 且 packageManager 精确",
      snap.lockPnpmWeb && /^pnpm@\d+\.\d+\.\d+$/.test(String(snap.pkg?.packageManager || "")),
      blockedDetail(snap, "pnpm", `当前 npm 锁；packageManager=${JSON.stringify(snap.pkg?.packageManager ?? null)}`),
    ),
  );

  return [...a, ...out];
}

/** 按锁族选命令；没有对应二进制时落未测，不许当成通过。 */
function lockEnforced(snap, family) {
  const id = "109/A3";
  const label = "删掉锁文件后安装必须失败（差分：有锁必须成功、无锁必须失败）";
  const pkgText = readText(path.join(snap.webDir, "package.json"));
  if (!pkgText) return U(id, "A", label, "读不到 web/package.json");
  if (!family) return U(id, "A", label, "没有唯一锁族可判（0 个或并存）");

  const [bin, args, lockName] =
    family === "npm"
      ? ["npm", ["ci", "--dry-run", "--offline", "--ignore-scripts"], "package-lock.json"]
      : family === "pnpm"
        ? ["pnpm", ["install", "--frozen-lockfile", "--offline"], "pnpm-lock.yaml"]
        : [null, null, null];

  if (!bin) return U(id, "A", label, `锁族 ${family} 无对应判据实现`);
  try {
    execFileSync(bin, ["--version"], { stdio: "pipe", timeout: 10000 });
  } catch {
    return U(id, "A", label, `本机没有 ${bin} 可执行，无法做安装差分`);
  }

  const lockText = readText(path.join(snap.webDir, lockName));
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "vfsc-lock-"));
  try {
    const probe = (withLock) => {
      const dir = path.join(tmp, withLock ? "with" : "without");
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "package.json"), pkgText);
      if (withLock && lockText !== null) fs.writeFileSync(path.join(dir, lockName), lockText);
      try {
        execFileSync(bin, args, {
          cwd: dir,
          stdio: "pipe",
          timeout: 25000,
          env: { ...process.env, npm_config_audit: "false", npm_config_fund: "false" },
        });
        return 0;
      } catch (e) {
        return typeof e.status === "number" ? e.status : -1;
      }
    };
    const rcWith = lockText !== null ? probe(true) : null;
    const rcWithout = probe(false);
    if (rcWith === null) return U(id, "A", label, `web 无 ${lockName}，差分判据不适用`);
    if (rcWith !== 0 && rcWithout !== 0) {
      return U(
        id,
        "A",
        label,
        `有锁 rc=${rcWith}、无锁 rc=${rcWithout} —— 两次都失败，是环境问题不是锁的问题（拒绝当成通过）`,
      );
    }
    return A(id, label, rcWith === 0 && rcWithout !== 0, `有锁 rc=${rcWith} / 无锁 rc=${rcWithout}`);
  } finally {
    try {
      fs.rmSync(tmp, { recursive: true, force: true });
    } catch {
      /* 临时目录清不掉不影响判据 */
    }
  }
}

// ══ #110 (TS-7)：路由库与逐页可达 ══════════════════════════════════════
function check110(snap) {
  const out = [];
  const clean = {};
  for (const [rel, raw] of Object.entries(snap.srcByRel)) clean[rel] = stripComments(raw);
  const allSrc = Object.values(clean).join("\n");

  // A1：全仓只 import 一种路由库族。
  const imported = [];
  for (const { lib, family } of ROUTER_FAMILIES) {
    const escaped = lib.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
    if (new RegExp(`from\\s+["']${escaped}["']`).test(allSrc)) imported.push({ lib, family });
  }
  const families = [...new Set(imported.map((x) => x.family))];
  out.push(
    A(
      "110/A1",
      "全仓只 import 一种路由库族（无第二套实现）",
      families.length <= 1,
      families.length === 0
        ? "没有任何路由库 import —— 判据不成立，不是通过"
        : `族：${families.join(" + ")}（包：${imported.map((x) => x.lib).join("、")}）`,
    ),
  );
  if (families.length === 0) {
    out[out.length - 1].state = "fail";
    out[out.length - 1].detail += " ← 没有路由库也算红：验收要求「有一套且只有一套」";
  }

  // A2：逐页可达（不抽样）—— 从磁盘枚举页面，不写死清单。
  //   写死清单的检查器会在新增页面时静默漏掉（孤儿页），这正是「抽样」的形状。
  //
  // ★ 判据不是「页面名在 App.tsx 里出现过」—— 那是**恒真**的：
  //   每个页面都有一行 `const X = lazy(...)`,即使它的路由被整段删掉也照样命中。
  //   实测过：删掉 TakedownPage 的路由块后，旧判据仍报绿。
  //   所以判据落在「**出现在一条路由声明里**」这一层。
  //
  // ★ 还必须**两种路由写法都认**，否则迁移当天这条判据会误报：
  //   · react-router（今天）：`<Route path="/x" element={<XPage />} />`
  //   · TanStack Router（T-333 之后）：`createRoute({ path: '/x', component: XPage })`
  //   只认 <Route> 会在迁移后把所有页面判成孤儿页 —— 而它不是孤儿，是写法变了。
  const appClean = stripComments(snap.appSrc);
  const declared = [...appClean.matchAll(/path\s*[:=]\s*["']([^"']+)["']/g)].map((m) => m[1]);
  const dupPaths = declared.filter((p, i) => declared.indexOf(p) !== i);

  /** 从一个起点切出成对括号/标签的区块（跳过 {} 与 () 内的嵌套）。 */
  function sliceBalanced(src, start, openCh, closeCh) {
    let depth = 0;
    for (let k = start; k < src.length; k += 1) {
      const ch = src[k];
      if (ch === openCh) depth += 1;
      else if (ch === closeCh) {
        depth -= 1;
        if (depth === 0) return src.slice(start, k + 1);
      }
    }
    return null;
  }

  const routeRegions = [];
  // ① JSX 写法：<Route ...> ... </Route> 或自闭合。`element={<X />}` 里的 `/>`
  //    不构成结束 —— 用花括号深度挡住（实测：不挡就会在组件名之前切断）。
  {
    let i = 0;
    while (true) {
      const s = appClean.indexOf("<Route", i);
      if (s < 0) break;
      let e = -1;
      let depth = 0;
      for (let k = s; k < appClean.length; k += 1) {
        const ch = appClean[k];
        if (ch === "{") depth += 1;
        else if (ch === "}") depth = Math.max(0, depth - 1);
        else if (depth === 0 && appClean.startsWith("/>", k)) {
          e = k + 2;
          break;
        } else if (depth === 0 && appClean.startsWith("</Route>", k)) {
          e = k + "</Route>".length;
          break;
        }
      }
      if (e < 0) break;
      routeRegions.push(appClean.slice(s, e));
      i = e;
    }
  }
  // ② 对象写法：createRoute(...) / createFileRoute(...) / createRootRoute(...)
  for (const m of appClean.matchAll(/create(?:File|Root)?Route\s*\(/g)) {
    const region = sliceBalanced(appClean, m.index + m[0].length - 1, "(", ")");
    if (region) routeRegions.push(region);
  }

  const inRouteTable = (name) =>
    routeRegions.some(
      (b) => new RegExp(`<${name}[\\s/>]`).test(b) || new RegExp(`component\\s*[:=]\\s*\\{?\\s*${name}\\b`).test(b),
    );

  const orphans = [];
  for (const pf of snap.pageFiles) {
    const base = pf.replace(/\.tsx$/, "");
    if (!inRouteTable(base)) orphans.push(pf);
  }
  // 反向：路由表里 lazy/引用到的页面文件必须真的存在。
  const missing = [];
  for (const m of appClean.matchAll(/import\(\s*["']\.\/pages\/([A-Za-z0-9_]+)["']/g)) {
    if (!snap.pageFiles.includes(`${m[1]}.tsx`)) missing.push(`${m[1]}.tsx`);
  }
  const pagesOk = snap.pageFiles.length > 0 && orphans.length === 0 && missing.length === 0 && dupPaths.length === 0;
  out.push(
    A(
      "110/A2",
      `全部 ${snap.pageFiles.length} 个页面组件在路由表中可达`,
      pagesOk,
      [
        `页面 ${snap.pageFiles.length} 个 / 声明路径 ${declared.length} 条`,
        orphans.length ? `未进路由表：${orphans.join("、")}` : "",
        missing.length ? `路由指向不存在的页面：${missing.join("、")}` : "",
        dupPaths.length ? `重复 path：${[...new Set(dupPaths)].join("、")}` : "",
      ]
        .filter(Boolean)
        .join("；"),
    ),
  );

  out.push(
    B(
      "110/B1",
      "路由库为 @tanstack/react-router",
      imported.some((x) => x.lib === "@tanstack/react-router"),
      blockedDetail(snap, "TanStack Router", `当前：${imported.map((x) => x.lib).join("、") || "无"}`),
    ),
  );
  return out;
}

// ══ #111 (TS-8)：Radix 原语 + 自有 token，不依赖生成模板 ═══════════════
function check111(snap) {
  const out = [];

  // A1：任何源码直接 import shadcn 生成模板包 → 红。
  const bad = [];
  for (const [rel, raw] of Object.entries(snap.srcByRel)) {
    const clean = stripComments(raw);
    for (const lib of SHADCN_LIBS) {
      const esc = lib.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
      if (new RegExp(`from\\s+["']${esc}(?:/[^"']*)?["']`).test(clean)) bad.push(`${rel} ← ${lib}`);
    }
  }
  out.push(
    A("111/A1", "没有任何源码直接 import shadcn 生成模板包", bad.length === 0, bad.join("；") || "0 处"),
  );

  // A2：颜色/间距/字号裸值 —— 复用 dt3-bare.mjs（唯一实现），账面必须等于实算。
  const baselineCount = Array.isArray(snap.baseline?.tokens) ? snap.baseline.tokens.length : -1;
  const maxTokens =
    typeof snap.baseline?.max_tokens === "number" ? snap.baseline.max_tokens : baselineCount;
  const liveCount = snap.stylesSrc ? parseBareEntries(snap.stylesSrc).length : -1;
  if (!snap.stylesSrc) {
    out.push(U("111/A2", "A", "样式层裸值账面=实算且不超上限", "读不到 web/src/styles.css"));
  } else if (!Array.isArray(snap.baseline?.tokens)) {
    out.push(U("111/A2", "A", "样式层裸值账面=实算且不超上限", "读不到 web/design-baseline.json"));
  } else {
    out.push(
      A(
        "111/A2",
        "样式层裸值账面=实算且不超上限",
        liveCount <= maxTokens && liveCount === baselineCount,
        `实算 ${liveCount} 处 / 账面 ${baselineCount} 处 / 上限 ${maxTokens} 处`,
      ),
    );
  }

  const deps = depsOf(snap.pkg);
  const hasRadix = Object.keys(deps).some((k) => k === "radix-ui" || k.startsWith("@radix-ui/"));
  out.push(
    B(
      "111/B1",
      "组件基础为 Radix 原语",
      hasRadix,
      blockedDetail(snap, "Radix", "package.json 无 radix-ui / @radix-ui/*，src/ui 无 Radix import"),
    ),
  );
  return out;
}

// ══ #128 的行为探针：真库驱动，不是自造 mock ════════════════════════════
/**
 * 观察点：一个 queryFn 被调用的次数。
 * 做法：用 @tanstack/react-query 的 QueryClient，建一个 QueryObserver 订阅某 key，
 *       首次订阅会拉一次（计数 1）；`invalidateQueries({refetchType:'active'})` 后
 *       库自己会让活跃观察者重拉（计数 2）。
 *
 * 判据是**计数差值**，不是「调用了 invalidate」—— 后者是开关状态，不是证据。
 * 库不在盘上时**未测**（不是通过）：没有观察对象时说什么都是猜。
 */
function probeInvalidateRefetch(snap, queryLibs) {
  const id = "128/A3";
  const label = "查询被标失效后，依赖它的视图确实重新拉取（打桩计数）";

  let lib = null;
  for (const cand of ["@tanstack/react-query", "react-query"]) {
    if (queryLibs.has(cand)) lib = cand;
  }
  if (!lib) {
    return U(
      id,
      "A",
      label,
      queryLibs.size === 0
        ? "全仓无请求缓存库 —— 没有可注入计数的查询缓存，行为判据无观察对象（未测，不是通过）"
        : `全仓有请求缓存库（${[...queryLibs].join("、")}），但本探针只覆盖 @tanstack/react-query / react-query 的失效语义 —— 未测，不是通过`,
    );
  }
  try {
    const stdout = String(
      execFileSync(
        process.execPath,
        [
          "--input-type=module",
          "-e",
          `
        import { QueryClient, QueryObserver } from ${JSON.stringify(lib)};
        var calls = 0;
        var qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
        var obs = new QueryObserver(qc, {
          queryKey: ["vfsc-probe"],
          queryFn: async function () { calls += 1; return { version: calls }; },
          staleTime: Infinity,
        });
        var unsub = obs.subscribe(function () {});
        await new Promise(function (r) { setTimeout(r, 300); });
        var afterMount = calls;
        await qc.invalidateQueries({ queryKey: ["vfsc-probe"], refetchType: "active" });
        await new Promise(function (r) { setTimeout(r, 300); });
        var afterInvalidate = calls;
        unsub();
        qc.clear();
        console.log(JSON.stringify({ afterMount: afterMount, afterInvalidate: afterInvalidate }));
        `,
        ],
        {
          cwd: snap.webDir,
          stdio: "pipe",
          timeout: 20000,
          env: { ...process.env, NODE_PATH: path.join(snap.webDir, "node_modules") },
        },
      ),
    );
    const m = stdout.match(/\{"afterMount":\d+,"afterInvalidate":\d+\}/);
    if (!m) return U(id, "A", label, `${lib} 探针退出 0 但未产出读数（未测，不是通过）`);
    const { afterMount, afterInvalidate } = JSON.parse(m[0]);
    return A(
      id,
      label,
      afterMount === 1 && afterInvalidate === 2,
      `${lib}：挂载后 ${afterMount} 次 → 失效后 ${afterInvalidate} 次（期望 1 → 2）`,
    );
  } catch (e) {
    const why = String(e.stderr || e.message || "").split("\n").slice(0, 2).join(" ").trim();
    return U(id, "A", label, `${lib} 探针跑不起来：${why}（未测，不是通过）`);
  }
}

// ══ #128 (TS-25)：服务端状态与表格库锁定 ═══════════════════════════════
function check128(snap) {
  const out = [];
  const query = importedLibs(snap.srcByRel, QUERY_LIBS);
  const table = importedLibs(snap.srcByRel, TABLE_LIBS);

  // A1/A2：不超过一套实现。今天可以是 0 套（尚未接入），但第二套出现即红。
  out.push(
    A(
      "128/A1",
      "全仓只 import 一种请求缓存库（无第二套）",
      query.size <= 1,
      `${query.size} 种：${[...query].join("、") || "（尚未接入）"}`,
    ),
  );
  out.push(
    A(
      "128/A2",
      "全仓只 import 一种表格库（无第二套）",
      table.size <= 1,
      `${table.size} 种：${[...table].join("、") || "（尚未接入）"}`,
    ),
  );

  // A3（行为）：查询被标失效后，依赖它的视图确实重新拉取 —— 打桩计数，不靠肉眼。
  //
  // ★ 这条**只有请求缓存库真的在盘上**时才可判，因为探针要驱动**真库**：
  //   用 @tanstack/react-query 的 QueryClient + QueryObserver，挂一个计数器式 queryFn，
  //   首次挂载记 1 次；`invalidateQueries()` 之后由库自己触发重拉，计数变 2。
  //   这不是「本文件自己造的 mock」—— 那个形状是 `check_frontend_gates.mjs` 的 C-128：
  //   它拿一个手写 fakeQueryCache 跑一遍，验的是它自己写的东西。
  //
  //   库不在盘上 → 落**未测**（照 tools/verify_multimodal_provider.py 的 M 段：
  //   没接能力 ≠ 通过）。但一旦 T-333 迁完，这条会**自动变成可判**并真跑，
  //   而不是永远未测 —— 一个永远未测的判据与永远恒绿的判据是同一种病。
  out.push(probeInvalidateRefetch(snap, query));

  out.push(
    B(
      "128/B1",
      "服务端状态为 @tanstack/react-query",
      query.has("@tanstack/react-query"),
      blockedDetail(snap, "TanStack Query", `当前：${[...query].join("、") || "无"}`),
    ),
  );
  out.push(
    B(
      "128/B2",
      "表格库为 @tanstack/react-table",
      table.has("@tanstack/react-table"),
      blockedDetail(snap, "TanStack Table", `当前：${[...table].join("、") || "无"}`),
    ),
  );
  return out;
}

// ── 断言跑一行的组合 ─────────────────────────────────────────────────────
const ROWS = {
  "109": { criterion: "TS-6", fn: check109 },
  "110": { criterion: "TS-7", fn: check110 },
  "111": { criterion: "TS-8", fn: check111 },
  "128": { criterion: "TS-25", fn: check128 },
};

/**
 * 一行 → 三态。**纯函数**，让反向对照能直接断言「结论行不许撒谎」。
 * 顺序有意：A 类红 > A/B 未测 > 全绿。有红时必须仍然报出有未测（不许只剩最后一行）。
 */
function verdictOf(asserts) {
  const aFail = asserts.filter((x) => x.cls === "A" && x.state === "fail");
  const blocked = asserts.filter((x) => x.cls === "B" && x.state === "blocked");
  const untested = asserts.filter((x) => x.state === "untested");
  const aPass = asserts.filter((x) => x.cls === "A" && x.state === "pass");
  let code = 0;
  if (aFail.length > 0) code = 1;
  else if (blocked.length > 0 || untested.length > 0) code = 2;
  return { code, aFail, blocked, untested, aPass };
}

function lineOf(rowNo, criterion, asserts) {
  const v = verdictOf(asserts);
  const word =
    v.code === 0
      ? `✅ 通过：A 类 ${v.aPass.length} 项全绿，B 类 ${asserts.filter((x) => x.cls === "B").length} 项已满足`
      : v.code === 1
        ? `❌ 红：A 类 ${v.aFail.length} 项不成立`
        : `⚠ 未测：A 类 ${v.aPass.length} 项已绿；B 类 ${v.blocked.length} 项等迁移、${v.untested.length} 项无观察对象 —— 未测 ≠ 通过 ≠ 红`;
  return `#${rowNo} ${criterion} → ${word}`;
}

function runRows(root, only) {
  const snap = loadSnapshot(root);
  const nums = only ? [only] : Object.keys(ROWS);
  const results = [];
  for (const n of nums) {
    const row = ROWS[n];
    if (!row) throw new Error(`未知 --row：${n}`);
    const asserts = row.fn(snap);
    results.push({ row: n, criterion: row.criterion, asserts, verdict: verdictOf(asserts) });
  }
  return results;
}

function render(results) {
  let worst = 0;
  for (const r of results) {
    console.log("=".repeat(78));
    console.log(`#${r.row} ${r.criterion} 逐条读数（A 类=今天能判 / B 类=等迁移）`);
    console.log("=".repeat(78));
    for (const a of r.asserts) {
      const mark =
        a.state === "pass" ? "✅" : a.state === "fail" ? "❌" : a.state === "blocked" ? "⏸" : "⚠";
      const kind = a.state === "blocked" ? "阻断(等迁移)" : a.state === "untested" ? "未测" : "";
      console.log(`  ${mark} [${a.cls}] ${a.id} ${a.label}${kind ? " · " + kind : ""}`);
      if (a.detail) console.log(`        ${a.detail}`);
    }
    console.log("-".repeat(78));
    console.log("  " + lineOf(r.row, r.criterion, r.asserts));
    // 有红时也必须报出有未测：只看最后一行的人会以为「其余都验过了」
    const v = r.verdict;
    if (v.code === 1 && (v.blocked.length > 0 || v.untested.length > 0)) {
      console.log(
        `  ⚠ 同时仍有 ${v.blocked.length} 项阻断 / ${v.untested.length} 项未测 —— 红与未测互不抵消`,
      );
    }
    worst = Math.max(worst, v.code === 1 ? 1 : worst === 1 ? 1 : v.code === 2 ? 2 : worst);
    if (v.code === 1) worst = 1;
    else if (v.code === 2 && worst !== 1) worst = 2;
  }
  return worst;
}

// ── 反向对照：喂坏样本必须红、喂好样本必须绿、喂迁移完成的样本必须变 0 ────
function makeFixture(base, mutate) {
  const dir = fs.mkdtempSync(path.join(base, "vfsc-fx-"));
  const w = path.join(dir, "web");
  fs.mkdirSync(path.join(w, "src", "pages"), { recursive: true });
  fs.mkdirSync(path.join(w, "src", "ui"), { recursive: true });
  fs.mkdirSync(path.join(dir, ".github", "workflows"), { recursive: true });

  // 一份「好样本」：单一 npm 锁、CI 用 npm ci、一个路由族、0 裸值、无 shadcn。
  fs.writeFileSync(
    path.join(w, "package.json"),
    JSON.stringify({ dependencies: { react: "19.3.1" }, devDependencies: {} }, null, 2),
  );
  fs.writeFileSync(path.join(w, "package-lock.json"), JSON.stringify({ lockfileVersion: 3, packages: {} }));
  fs.writeFileSync(
    path.join(dir, ".github", "workflows", "acceptance.yml"),
    "jobs:\n  a:\n    steps:\n      - run: npm ci\n",
  );
  fs.writeFileSync(
    path.join(w, "src", "App.tsx"),
    'import { Route, Routes } from "react-router-dom";\n' +
      'import HomePage from "./pages/HomePage";\n' +
      'export default function App() { return <Routes><Route path="/" element={<HomePage />} /></Routes>; }\n',
  );
  fs.writeFileSync(path.join(w, "src", "pages", "HomePage.tsx"), "export default function HomePage(){return null}\n");
  fs.writeFileSync(path.join(w, "src", "styles.css"), ":root { --a: 1; }\n");
  fs.writeFileSync(path.join(w, "design-baseline.json"), JSON.stringify({ tokens: [], max_tokens: 0 }));

  const fx = {
    dir,
    p: (...s) => path.join(dir, ...s),
    write(rel, text) {
      const abs = path.join(dir, rel);
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      fs.writeFileSync(abs, text);
      return fx;
    },
    read(rel) {
      return fs.readFileSync(path.join(dir, rel), "utf8");
    },
    rm(rel) {
      fs.rmSync(path.join(dir, rel), { force: true });
      return fx;
    },
  };
  if (mutate) mutate(fx);
  return fx;
}

function runControls() {
  const cases = [];
  const base = os.tmpdir();
  const withFx = (mutate) => {
    const fx = makeFixture(base, mutate);
    try {
      return runRows(fx.dir, null);
    } finally {
      fs.rmSync(fx.dir, { recursive: true, force: true });
    }
  };
  // 需要先建 fixture、稍后再跑/再删的场合用这一个（withFx 会在返回前就删掉目录）
  const mkFx = (mutate) => makeFixture(base, mutate);
  const find = (results, row, id) =>
    results.find((r) => r.row === row).asserts.find((a) => a.id === id);

  // C1 好样本：A 类必须全绿（证明判据不会误报 —— 误报比不报更糟）
  {
    const res = withFx(null);
    const aFails = res.flatMap((r) => r.asserts).filter((a) => a.cls === "A" && a.state === "fail");
    cases.push([
      "C1 好样本 → A 类 0 红（不误报）",
      aFails.length === 0,
      aFails.map((a) => `${a.id}:${a.detail}`).join(" | "),
    ]);
  }

  // C2 #109 双锁并存 → A1 必红
  {
    const res = withFx((fx) => fx.write("web/pnpm-lock.yaml", "lockfileVersion: '9'\n"));
    const a = find(res, "109", "109/A1");
    cases.push(["C2 109/A1 双锁并存（package-lock + pnpm-lock）→ 必红", a.state === "fail", a.detail]);
  }

  // C3 #109 CI 用 pnpm 但只有 npm 锁 → A2 必红
  {
    const res = withFx((fx) =>
      fx.write(".github/workflows/acceptance.yml", "jobs:\n  a:\n    steps:\n      - run: pnpm install --frozen-lockfile\n"),
    );
    const a = find(res, "109", "109/A2");
    cases.push(["C3 109/A2 CI 用 pnpm 而锁是 npm → 必红", a.state === "fail", a.detail]);
  }

  // C4 #109 行为：删掉锁文件后安装必须失败（差分）。这里直接删锁 → A3 落未测（无 npm 锁可判），
  //    证明它不会在没有锁的情况下假装通过。
  {
    const res = withFx((fx) => fx.rm("web/package-lock.json"));
    const a = find(res, "109", "109/A3");
    cases.push(["C4 109/A3 无 npm 锁 → 未测（不许算通过）", a.state === "untested", a.detail]);
  }

  // C5 #110 第二套路由 → A1 必红
  {
    const res = withFx((fx) =>
      fx.write("web/src/pages/Evil.tsx", 'import { Router } from "wouter";\nexport default function E(){return null}\n'),
    );
    const a = find(res, "110", "110/A1");
    cases.push(["C5 110/A1 同时 import react-router-dom 与 wouter → 必红", a.state === "fail", a.detail]);
  }

  // C6 #110 孤儿页面（在 pages/ 里但没进路由表）→ A2 必红
  {
    const res = withFx((fx) => fx.write("web/src/pages/Orphan.tsx", "export default function O(){return null}\n"));
    const a = find(res, "110", "110/A2");
    cases.push(["C6 110/A2 孤儿页面未进路由表 → 必红", a.state === "fail", a.detail]);
  }

  // C7 #111 直接 import shadcn → A1 必红
  {
    const res = withFx((fx) =>
      fx.write("web/src/ui/Bad.tsx", 'import { Button } from "shadcn";\nexport default Button;\n'),
    );
    const a = find(res, "111", "111/A1");
    cases.push(["C7 111/A1 直接 import shadcn 生成模板 → 必红", a.state === "fail", a.detail]);
  }

  // C8 #111 样式层冒真裸值 → A2 必红
  {
    const res = withFx((fx) =>
      fx.write("web/src/styles.css", ":root { --a: 1; }\n.extra { color: #ff0000; padding: 12px; }\n"),
    );
    const a = find(res, "111", "111/A2");
    cases.push(["C8 111/A2 样式层出现真裸值 → 必红", a.state === "fail", a.detail]);
  }

  // C9 #128 第二套请求缓存库 → A1 必红
  {
    const res = withFx((fx) =>
      fx.write(
        "web/src/q.ts",
        'import { useQuery } from "@tanstack/react-query";\nimport useSWR from "swr";\n',
      ),
    );
    const a = find(res, "128", "128/A1");
    cases.push(["C9 128/A1 TanStack Query + SWR 并存 → 必红", a.state === "fail", a.detail]);
  }

  // C10 #128 第二套表格库 → A2 必红
  {
    const res = withFx((fx) =>
      fx.write(
        "web/src/t.ts",
        'import { useReactTable } from "@tanstack/react-table";\nimport { AgGridReact } from "ag-grid-react";\n',
      ),
    );
    const a = find(res, "128", "128/A2");
    cases.push(["C10 128/A2 TanStack Table + ag-grid 并存 → 必红", a.state === "fail", a.detail]);
  }

  // C11 ★ 迁移完成后必须真的变绿：B 类不许是写死的「阻断」。
  //    把样本改成 TanStack Router + pnpm + Radix + Query + Table，四行必须退 0。
  {
    const res = withFx((fx) => {
      fx.write(
        "web/package.json",
        JSON.stringify(
          {
            packageManager: "pnpm@9.15.0",
            dependencies: { react: "19.3.1", "@radix-ui/react-dialog": "1.1.0" },
            devDependencies: {},
          },
          null,
          2,
        ),
      );
      fx.rm("web/package-lock.json");
      fx.write("web/pnpm-lock.yaml", "lockfileVersion: '9'\n");
      fx.write(".github/workflows/acceptance.yml", "jobs:\n  a:\n    steps:\n      - run: pnpm install --frozen-lockfile\n");
      fx.write(
        "web/src/App.tsx",
        'import { createRoute } from "@tanstack/react-router";\n' +
          'import HomePage from "./pages/HomePage";\n' +
          'export const t = createRoute({ path: "/", component: HomePage });\n',
      );
      fx.write(
        "web/src/q.ts",
        'import { useQuery } from "@tanstack/react-query";\nimport { useReactTable } from "@tanstack/react-table";\n',
      );
      // 豁免台账指得出一条覆盖全部五个 token 的条目 —— 否则 B 类会被标「无豁免凭据」
      fx.write(
        "PMO/audit/waiver-v1.json",
        JSON.stringify({
          items: [
            {
              id: "WV-XX",
              item: "技术栈迁移",
              理由: "pnpm / TanStack Router / Radix / TanStack Query / TanStack Table",
              到期日: "2099-12-31",
              状态: "active",
            },
          ],
        }),
      );
    });
    const bBlocked = res
      .flatMap((r) => r.asserts)
      .filter((a) => a.cls === "B" && a.state === "blocked");
    const aFailed = res
      .flatMap((r) => r.asserts)
      .filter((a) => a.cls === "A" && a.state === "fail");
    const detail =
      `B 类仍阻断 ${bBlocked.length} 条：${bBlocked.map((a) => a.id).join(",") || "无"}` +
      ` | A 类红 ${aFailed.length} 条：${aFailed.map((a) => a.id).join(",") || "无"}`;
    cases.push([
      "C11 ★ 迁移完成后 B 类全部解除阻断（B 不是写死的），且 A 类不回归",
      bBlocked.length === 0 && aFailed.length === 0,
      detail,
    ]);
  }

  // C12 ★ 结论行不许撒谎：B 类阻断时 code 必须是 2，不是 0（未测 ≠ 通过）
  {
    const res = withFx(null);
    const c110 = res.find((r) => r.row === "110").verdict.code;
    cases.push([
      "C12 B 类阻断时退 2（不是 0）—— 未测 ≠ 通过",
      c110 === 2,
      `#110 code=${c110}`,
    ]);
  }

  // C13 ★ A 类有红时退 1，且不许被 B 类的「阻断」冲淡成 2
  {
    const res = withFx((fx) => fx.write("web/src/pages/Evil.tsx", 'import { Router } from "wouter";\nexport default 1;\n'));
    const c110 = res.find((r) => r.row === "110").verdict.code;
    cases.push(["C13 A 类有红 → 退 1（红优先于未测）", c110 === 1, `#110 code=${c110}`]);
  }

  // C14 ★ 结论行的判词：退 2 时不许出现「通过」/「没问题」
  {
    const res = withFx(null);
    const v = res.find((r) => r.row === "110").verdict;
    const line = lineOf("110", "TS-7", res.find((r) => r.row === "110").asserts);
    const lies = v.code === 2 && (/通过|没问题|全部满足/.test(line) && !/未测|等迁移/.test(line));
    cases.push(["C14 退 2 的结论行不含「通过/没问题」（只允许未测措辞）", !lies && /未测/.test(line), line]);
  }

  // C15 ★ B 类凭据是真读台账的：把豁免里那句理由删掉 → 必须改判「无豁免凭据」
  {
    const res = withFx((fx) =>
      fx.write(
        "PMO/audit/waiver-v1.json",
        JSON.stringify({ items: [{ id: "WV-XX", item: "别的", 理由: "无关内容", 到期日: "2099-12-31", 状态: "active" }] }),
      ),
    );
    const b = res.find((r) => r.row === "110").asserts.find((a) => a.id === "110/B1");
    cases.push([
      "C15 B 类凭据是现场读台账：无对应豁免 → 标「无豁免凭据」",
      /无豁免凭据/.test(b.detail),
      b.detail,
    ]);
  }

  // C16 ★ 整行注释不算代码：注释里写 import wouter 不许判红
  //    （否则一个会误报的检查器比没有检查器更糟 —— §2.1.1）
  {
    const res = withFx((fx) =>
      fx.write("web/src/pages/Note.tsx", '// import { Router } from "wouter";\nexport default function N(){return null}\n'),
    );
    const a = find(res, "110", "110/A1");
    cases.push(["C16 110/A1 注释里的第二套路由不算 import → 不许误报", a.state === "pass", a.detail]);
  }

  // C17 ★ #128/A3 探针自己必须能红：用同形状 stub 驱动「失效却**不**重拉」的坏库，
  //    探针必须判红而不是判过。否则它只是个恒绿的装饰 —— 恒绿与恒红是同一种病。
  //    （stub 只替我验**我写的驱动逻辑**；真库的行为是库的事，见下面 C18 的说明。）
  {
    const res = withFx((fx) => {
      fx.write(
        "web/node_modules/@tanstack/react-query/package.json",
        JSON.stringify({ name: "@tanstack/react-query", type: "module", main: "index.mjs", exports: "./index.mjs" }),
      );
      // 坏库：invalidate 之后什么都不做
      fx.write(
        "web/node_modules/@tanstack/react-query/index.mjs",
        `export class QueryClient {
           constructor(){ this.obs = new Set(); }
           invalidateQueries(){ return Promise.resolve(); }
           clear(){}
         }
         export class QueryObserver {
           constructor(qc, opts){ this.qc = qc; this.opts = opts; }
           subscribe(fn){ this.qc.obs.add(this); fn(); this.opts.queryFn(); return () => this.qc.obs.delete(this); }
         }
        `,
      );
      fx.write("web/src/q.ts", 'import { useQuery } from "@tanstack/react-query";\n');
    });
    const a = find(res, "128", "128/A3");
    cases.push([
      "C17 ★ 128/A3 探针会红：失效却不重拉的坏库 → 必须判红（不是恒绿）",
      a.state === "fail" && /1 次 →.*1 次|after/.test(a.detail + " after"),
      `${a.state} ${a.detail}`,
    ]);
  }

  // C18 ★ 好库：invalidate 后真的让活跃观察者重拉 → 探针必须判过（计数 1 → 2）。
  //    这条与 C17 成对：一条证明它会红，一条证明它不为红而红。
  {
    const res = withFx((fx) => {
      fx.write(
        "web/node_modules/@tanstack/react-query/package.json",
        JSON.stringify({ name: "@tanstack/react-query", type: "module", main: "index.mjs", exports: "./index.mjs" }),
      );
      fx.write(
        "web/node_modules/@tanstack/react-query/index.mjs",
        `export class QueryClient {
           constructor(){ this.obs = new Set(); }
           invalidateQueries(){ for (const o of this.obs) o.refetch(); return Promise.resolve(); }
           clear(){}
         }
         export class QueryObserver {
           constructor(qc, opts){ this.qc = qc; this.opts = opts; }
           refetch(){ this.opts.queryFn(); }
           subscribe(fn){ this.qc.obs.add(this); fn(); this.opts.queryFn(); return () => this.qc.obs.delete(this); }
         }
        `,
      );
      fx.write("web/src/q.ts", 'import { useQuery } from "@tanstack/react-query";\n');
    });
    const a = find(res, "128", "128/A3");
    cases.push([
      "C18 ★ 128/A3 好库（失效即重拉）→ 计数 1→2，探针必须判过",
      a.state === "pass",
      `${a.state} ${a.detail}`,
    ]);
  }

  // C19 ★ 110/A2 必须真会红：删掉页面的**路由声明**（页面文件仍在、lazy import 仍在）
  //    → 必须判红。这是「名字出现过 ≠ 拦得住」那条病的现场复现：
  //    旧判据查「页面名在 App.tsx 里出现过」，而 lazy import 那一行永远满足它。
  {
    const res = withFx((fx) => {
      const app = fx.read("web/src/App.tsx");
      // 保留 `import HomePage from ...`，只把 <Route> 去掉
      fx.write(
        "web/src/App.tsx",
        app.replace(/<Routes>[\s\S]*<\/Routes>/, "<Routes></Routes>"),
      );
    });
    const a = find(res, "110", "110/A2");
    cases.push([
      "C19 ★ 110/A2 删掉 <Route> 但保留 import → 必须红（名字出现过 ≠ 拦得住）",
      a.state === "fail",
      `${a.state} ${a.detail}`,
    ]);
  }

  // C20 ★ 110/A2 对 TanStack 写法同样有效（迁移后不许误报）：
  //    createRoute({ component: X }) 必须被认成「在路由表里」；删掉它则必须红。
  {
    const good = mkFx((fx) => {
      fx.write(
        "web/src/App.tsx",
        'import { createRoute } from "@tanstack/react-router";\n' +
          'import HomePage from "./pages/HomePage";\n' +
          'export const t = createRoute({ path: "/", component: HomePage });\n',
      );
    });
    let a1;
    try {
      a1 = runRows(good.dir, "110")[0].asserts.find((x) => x.id === "110/A2");
    } finally {
      fs.rmSync(good.dir, { recursive: true, force: true });
    }
    const bad = mkFx((fx) => {
      fx.write(
        "web/src/App.tsx",
        'import { createRoute } from "@tanstack/react-router";\n' +
          'import HomePage from "./pages/HomePage";\n',
      );
    });
    let a2;
    try {
      a2 = runRows(bad.dir, "110")[0].asserts.find((x) => x.id === "110/A2");
    } finally {
      fs.rmSync(bad.dir, { recursive: true, force: true });
    }
    cases.push([
      "C20 ★ 110/A2 认 TanStack createRoute 写法（迁移后不误报），删掉则红",
      a1.state === "pass" && a2.state === "fail",
      `good=${a1.state} bad=${a2.state}`,
    ]);
  }

  // C21 ★ 「只 import 一种」的语义：全仓只有 SWR（0→1）必须 **A1 判过** ——
  //    它不是「第二套实现」。但整行**不许因此变绿**：B1 必须仍是阻断。
  //    这条同时守住刚修的那个自相矛盾：B 类已满足时详情不许再写「无豁免凭据」。
  {
    const res = withFx((fx) =>
      fx.write("web/src/q.ts", 'import useSWR from "swr";\nexport const x = useSWR;\n'),
    );
    const r = res.find((x) => x.row === "128");
    const a1 = r.asserts.find((x) => x.id === "128/A1");
    const b1 = r.asserts.find((x) => x.id === "128/B1");
    cases.push([
      "C21 ★ 只有一套（SWR）→ A1 判过、但 B1 仍阻断（整行不许变绿）",
      a1.state === "pass" && b1.state === "blocked" && r.verdict.code === 2,
      `A1=${a1.state} B1=${b1.state} code=${r.verdict.code}`,
    ]);
  }

  // C22 ★ B 类已满足时详情里不许出现「无豁免凭据」（自相矛盾的读数）
  {
    const res = withFx((fx) => {
      fx.write("web/package.json", JSON.stringify({ dependencies: { "@tanstack/react-table": "8.0.0" } }));
      fx.write("web/src/t.ts", 'import { useReactTable } from "@tanstack/react-table";\n');
    });
    const b2 = res.find((r) => r.row === "128").asserts.find((a) => a.id === "128/B2");
    cases.push([
      "C22 ★ B2 已满足时不许写「无豁免凭据」（读数不许自相矛盾）",
      b2.state === "pass" && !/无豁免凭据/.test(b2.detail),
      `${b2.state} | ${b2.detail}`,
    ]);
  }

  return cases;
}

// ── 入口 ─────────────────────────────────────────────────────────────────
function main() {
  if (flag("controls")) {
    const cases = runControls();
    console.log("=".repeat(78));
    console.log("verify_frontend_stack_contract.mjs --controls · #109/#110/#111/#128 反向对照");
    console.log("=".repeat(78));
    let failed = 0;
    for (const [label, ok, detail] of cases) {
      console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
      if (!ok) failed += 1;
    }
    console.log("-".repeat(78));
    console.log(failed === 0 ? `✅ ${cases.length}/${cases.length} 项反向对照全过` : `❌ ${failed}/${cases.length} 项失败`);
    return failed === 0 ? 0 : 1;
  }

  const root = path.resolve(arg("root", path.resolve(HERE, "..", "..")));
  const only = arg("row", null);
  let results;
  try {
    results = runRows(root, only);
  } catch (e) {
    console.error(`未测：${e.message}`);
    return 2;
  }
  if (flag("json")) {
    console.log(JSON.stringify({ root, results }, null, 2));
    const codes = results.map((r) => r.verdict.code);
    return codes.includes(1) ? 1 : codes.includes(2) ? 2 : 0;
  }
  const code = render(results);
  return code;
}

process.exit(main());
