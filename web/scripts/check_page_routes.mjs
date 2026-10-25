#!/usr/bin/env node
/**
 * check_page_routes.mjs —— 「页面文件 ↔ 路由」双向可达（纯静态，不启浏览器、不跑服务）。
 *
 * ## 它回答的是哪一个问题
 *
 * 执行票 T-413 的原始描述（「8 页文件存在但未接路由，App.tsx 仅有 6 条路由」）早已过期：
 * 提交 `2e59ca8` 之后 `App.tsx` 有 19 条 `<Route>`，12 个页面全部接上了。
 * 但**没有任何东西能自动判断这件事** —— 页面接没接路由，只能靠人逐页点。
 * 本脚本把这一条变成秒级可跑、退出码三态的断言。
 *
 * ## 为什么是「双向」
 *
 * 单向只查一半，两个方向会各自漏掉一类真实缺口：
 *
 * | 方向 | 漏掉时会怎样 |
 * |---|---|
 * | 磁盘 → 路由 | 新写的页面文件躺着没人用，`npm run build` 照绿（Vite 不报未引用模块），谁也不知道它没接 |
 * | 路由 → 磁盘 | `App.tsx` 里写着 `./pages/Foo` 而文件已被改名/删除，只有真跑到那条路径才炸，且是运行时 404 |
 *
 * 所以两个方向都单独成断言，各自能独立变红。
 *
 * ## 为什么不引依赖、不上浏览器
 *
 * `pairing_check.mjs` / `check_pages.mjs` 是**运行时**断言（起 Chrome、点真页面），
 * 需要 dev-up 与服务在跑，分钟级。它们验的是「点下去对不对」。
 * 本脚本验的是「**文件与路由表是否对得上**」—— 这是一件纯静态、毫秒级、可以挂在
 * `verify:*` 里天天跑的事。用 CDP 去验它等于为了看一个 import 起一台浏览器。
 *
 * 因此这里只做**两种极简解析**（够用即可，不写完整的 TS 解析器）：
 *   1. 组件名 → 模块路径：`import X from "./pages/Y"` 与 `const X = lazy(() => import("./pages/Y"))`
 *   2. `<Route path="…" element={…}/>` 的 path 与 element 里出现的组件名
 *
 * ## 退出码
 *
 * `0` 双向都过 / `1` 有缺漏 / `2` 未测（读不到 App.tsx 或 pages 目录，或两侧都空）。
 *
 * 用法：
 *   node scripts/check_page_routes.mjs
 *   node scripts/check_page_routes.mjs --json
 *   node scripts/check_page_routes.mjs --selftest
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, "..");

const JSON_OUT = process.argv.includes("--json");
const SELFTEST = process.argv.includes("--selftest");

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

// ── 解析前先去注释：注释不算代码 ────────────────────────────────────────
/**
 * 把 `//`、`/* *\/` 与 JSX 的 `{/* *\/}` 注释换成等长空白（保留偏移量）。
 *
 * ## 为什么这一步**不能省**（这是本脚本第一版真栽过的坑）
 *
 * 「把某条路由注释掉」是路由在现实里失效的**最常见写法**。第一版直接在原始
 * 源码上跑正则，于是：
 *
 * ```jsx
 * {/* P-08 下线任务台 —— DEMO: 路由临时注释掉 *\/}
 * {/*
 * <Route path="/takedown" element={<TakedownPage />} />
 * *\/}
 * ```
 *
 * 脚本读到 `<Route` 与 `<TakedownPage />`，判定「页面接上了」，**退 0 全绿** ——
 * 而这条路由此刻根本不生效。演示反向对照时当场撞上。
 *
 * 这与 `verify_shouheng_ops.py` 的 C5、`verify_cards.mjs` 的 J1a 是同一条读法：
 * **注释不算代码**。三个扫描器各写一遍就会各漏一遍，所以这里明写着它是同一条规矩。
 */
function stripComments(source) {
  const out = source.split("");
  const blank = (from, to) => {
    for (let k = from; k < to && k < out.length; k++) {
      if (out[k] !== "\n") out[k] = " ";
    }
  };
  let i = 0;
  while (i < source.length) {
    const c = source[i];
    const next = source[i + 1];

    // 字符串：整段跳过，免得把字符串里的 `//` 或 `/*` 当成注释开头。
    // 三种引号各处理一遍（模板串里的 `${…}` 不细究 —— 本文件里没有）。
    if (c === '"' || c === "'" || c === "`") {
      const quote = c;
      let j = i + 1;
      while (j < source.length && source[j] !== quote) {
        if (source[j] === "\\") j += 1;
        j += 1;
      }
      i = j + 1;
      continue;
    }

    if (c === "/" && next === "/") {
      let j = i;
      while (j < source.length && source[j] !== "\n") j += 1;
      blank(i, j);
      i = j;
      continue;
    }

    if (c === "/" && next === "*") {
      const close = source.indexOf("*/", i + 2);
      const end = close < 0 ? source.length : close + 2;
      blank(i, end);
      i = end;
      continue;
    }

    i += 1;
  }
  return out.join("");
}

// ── 解析：组件名 → 模块说明符 ────────────────────────────────────────────
// 只认「默认导入」和「lazy(() => import(...))」两种 —— 页面就是这两种写法
// （`App.tsx` 里 5 个静态导入 + 9 个 lazy）。命名导入（`{ Navigate, Route, Routes }`）
// 是 router 自己的东西，不属于页面映射，刻意不收。
function mapComponentModules(source) {
  const map = new Map();
  const staticRe =
    /import\s+([A-Za-z_$][\w$]*)\s+from\s+["']([^"']+)["']/g;
  const lazyRe =
    /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*lazy\(\s*\(\s*\)\s*=>\s*import\(\s*["']([^"']+)["']\s*\)\s*\)/g;
  let m;
  while ((m = staticRe.exec(source))) map.set(m[1], m[2]);
  while ((m = lazyRe.exec(source))) map.set(m[1], m[2]);
  return map;
}

// ── 解析：把 `<Route` 切成 chunk，各自取 path 与 element ────────────────
// 按 `<Route` 出现位置切分。父路由（`<Route element={<AppShell/>}>`）的 chunk 会
// 在下一个 `<Route` 处截断，所以它只含自己的 element —— 嵌套不会把子路由的
// 组件算到父路由头上。
function sliceRouteChunks(source) {
  const chunks = [];
  const re = /<Route\b/g;
  const starts = [];
  let m;
  while ((m = re.exec(source))) starts.push(m.index);
  for (let i = 0; i < starts.length; i++) {
    const end = i + 1 < starts.length ? starts[i + 1] : source.length;
    chunks.push(source.slice(starts[i], end));
  }
  return chunks;
}

// `element={ … }` 的花括号配对（`<Suspense fallback={…}>` 里还有嵌套花括号，
// 所以不能取到第一个 `}` 就停）。
function extractElementJsx(chunk) {
  const key = "element={";
  const at = chunk.indexOf(key);
  if (at < 0) return "";
  let i = at + key.length - 1; // 指向 `{`
  let depth = 0;
  for (; i < chunk.length; i++) {
    const c = chunk[i];
    if (c === "{") depth += 1;
    else if (c === "}") {
      depth -= 1;
      if (depth === 0) return chunk.slice(at + key.length, i);
    }
  }
  return chunk.slice(at + key.length);
}

function extractPath(chunk) {
  const m = /\bpath=(?:"([^"]*)"|\{"([^"]*)"\})/.exec(chunk);
  return m ? (m[1] ?? m[2]) : null;
}

// JSX 里的大写标识符 = 组件引用（小写的 `p` / `h2` 是原生标签，不算）。
function componentNamesIn(jsx) {
  const names = new Set();
  const re = /<([A-Z][\w$]*)/g;
  let m;
  while ((m = re.exec(jsx))) names.add(m[1]);
  return [...names];
}

/**
 * 纯函数：把一个 import 说明符展开成「可能存在的文件路径」候选列表。
 *
 * `App.tsx` 里写的是扩展名省略的 `./pages/LoginPage`（TS/Vite 的惯例）。
 * 拿这个串直接 `fs.existsSync` 会**一条都不存在** —— 于是每一个页面都被判成
 * 「路由引用了不存在的文件」，19 条红，而文件全在盘上。
 * 抽成纯函数是为了 `--selftest` 能直接断言这件事（见用例 7）。
 */
function candidatePaths(base) {
  return [
    base,
    `${base}.tsx`,
    `${base}.ts`,
    `${base}.jsx`,
    `${base}.js`,
    path.join(base, "index.tsx"),
    path.join(base, "index.ts"),
  ];
}

/**
 * 纯函数：输入是「App.tsx 源码 + pages 目录下的文件名 + 文件存在性判据」，
 * 输出是结论。抽成纯函数是为了 `--selftest` 能直接喂坏样本，
 * 不必在磁盘上真的造一个缺路由的 App.tsx（那会污染真仓库）。
 */
function analyze({ appSource: rawAppSource, pageFiles, specExists }) {
  // ★ 先剥注释再解析：注释掉的路由必须算「没有这条路由」（见 stripComments 的说明）。
  const appSource = stripComments(rawAppSource);
  const modules = mapComponentModules(appSource);
  const routes = [];
  const routedSpecs = new Set();

  for (const chunk of sliceRouteChunks(appSource)) {
    const jsx = extractElementJsx(chunk);
    const routePath = extractPath(chunk);
    const refs = [];
    for (const name of componentNamesIn(jsx)) {
      const spec = modules.get(name);
      // 只关心相对路径（仓库内模块）。`Navigate` 这种来自 npm 包的跳过。
      if (!spec || !spec.startsWith(".")) continue;
      refs.push({ name, spec });
      routedSpecs.add(spec);
    }
    routes.push({ path: routePath, refs });
  }

  const reds = [];

  // 方向一（路由 → 磁盘）：路由里引用的每个仓库内模块，文件必须还在。
  for (const route of routes) {
    for (const ref of route.refs) {
      if (!specExists(ref.spec)) {
        reds.push(
          `路由 ${route.path ?? "(无 path 的布局路由)"} 引用的 ${ref.spec}（组件 ${ref.name}）在磁盘上不存在`,
        );
      }
    }
  }

  // 方向二（磁盘 → 路由）：每个页面文件都必须被至少一条路由的元素引用。
  // 注意判据是「被 route element 引用」，不是「被 import 过」——
  // 一个 import 了却没接进任何 `<Route>` 的页面，正是这次要抓的那一类。
  const orphans = [];
  for (const file of pageFiles) {
    const spec = `./pages/${file.replace(/\.tsx$/, "")}`;
    if (!routedSpecs.has(spec)) orphans.push(file);
  }
  for (const file of orphans) {
    reds.push(`页面文件 src/pages/${file} 未被任何 <Route> 引用（漏接路由）`);
  }

  return { routes, routedSpecs, orphans, reds };
}

// ── 真身 ────────────────────────────────────────────────────────────────
function main() {
  const appFile = path.resolve(WEB, arg("app", "src/App.tsx"));
  const pagesDir = path.resolve(WEB, arg("pages", "src/pages"));

  if (!fs.existsSync(appFile)) {
    console.error(`⚠ 未测：读不到 ${appFile}`);
    return 2;
  }
  if (!fs.existsSync(pagesDir) || !fs.statSync(pagesDir).isDirectory()) {
    console.error(`⚠ 未测：读不到页面目录 ${pagesDir}`);
    return 2;
  }

  const appSource = fs.readFileSync(appFile, "utf8");
  const pageFiles = fs
    .readdirSync(pagesDir)
    .filter((n) => n.endsWith(".tsx"))
    .sort();

  // 空即未测（AGENTS.md §2.4「D 空即声明」）：目录空了会让
  // 「每个页面都接了路由」恒真 —— 那种「全过」是假的全过。
  if (pageFiles.length === 0) {
    console.error(`⚠ 未测：${pagesDir} 下没有 *.tsx，无法判断可达性`);
    return 2;
  }

  const existsCache = new Map();
  const specExists = (spec) => {
    if (!existsCache.has(spec)) {
      const base = path.resolve(WEB, "src", spec);
      existsCache.set(
        spec,
        candidatePaths(base).some((p) => fs.existsSync(p)),
      );
    }
    return existsCache.get(spec);
  };

  const { routes, routedSpecs, reds } = analyze({
    appSource,
    pageFiles,
    specExists,
  });

  const routedPages = [...routedSpecs].filter((s) =>
    s.startsWith("./pages/"),
  );
  if (routedPages.length === 0) {
    console.error(`⚠ 未测：${appFile} 里没有解析出任何页面级 <Route>`);
    return 2;
  }

  if (JSON_OUT) {
    console.log(
      JSON.stringify(
        {
          ok: reds.length === 0,
          appFile,
          pagesDir,
          routeCount: routes.length,
          pageFileCount: pageFiles.length,
          routedPageSpecCount: routedPages.length,
          reds,
          routes: routes.map((r) => ({
            path: r.path,
            components: r.refs.map((x) => x.name),
          })),
        },
        null,
        2,
      ),
    );
    return reds.length === 0 ? 0 : 1;
  }

  console.log(`路由表：${appFile}`);
  console.log(`页面目录：${pagesDir}`);
  console.log("");
  for (const route of routes) {
    const names = route.refs.map((r) => r.name).join(", ") || "—（无仓库内组件）";
    console.log(`  ${(route.path ?? "(布局路由)").padEnd(22)} ${names}`);
  }
  console.log("");
  console.log(
    `读数：<Route> ${routes.length} 条 · 页面文件 ${pageFiles.length} 个 · 被路由引用的页面模块 ${routedPages.length} 个`,
  );

  if (reds.length) {
    console.error("");
    for (const r of reds) console.error(`✗ ${r}`);
    console.error(`❌ ${reds.length} 项缺漏`);
    return 1;
  }
  console.log("✅ 双向可达：磁盘上的页面都在路由里，路由引用的页面文件都在磁盘上");
  return 0;
}

// ── 反向对照：坏样本必须红 ──────────────────────────────────────────────
// AGENTS.md §2.4.1：一个断言如果没在坏样本上变红过，就不算验证过它。
function selftest() {
  const checks = [];
  const check = (label, ok) => checks.push([label, ok]);
  const allExist = () => true;

  const goodApp = `
    import { lazy } from "react";
    import { Route } from "react-router-dom";
    import Shell from "./components/Shell";
    import QueuePage from "./pages/QueuePage";
    const InboxPage = lazy(() => import("./pages/InboxPage"));
    export default function App() {
      return (
        <Routes>
          <Route element={<Shell />}>
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/inbox" element={
              <Suspense fallback={<p className="hint">加载…</p>}>
                <InboxPage />
              </Suspense>
            } />
          </Route>
        </Routes>
      );
    }
  `;

  // 1. 好样本：双向都对得上 → 不许红（否则这个检查器就是砖头）
  {
    const r = analyze({
      appSource: goodApp,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check("好样本零红", r.reds.length === 0);
    check("好样本解析出 2 条页面引用", r.routedSpecs.size >= 2);
  }

  // 2. 磁盘 → 路由：多一个页面文件没人接 → 必红
  {
    const r = analyze({
      appSource: goodApp,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx", "OrphanPage.tsx"],
      specExists: allExist,
    });
    check(
      "漏接路由的页面文件被抓到",
      r.reds.some((x) => x.includes("OrphanPage.tsx")),
    );
  }

  // 3. 路由 → 磁盘：路由引用的文件不存在 → 必红
  {
    const r = analyze({
      appSource: goodApp,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: (spec) => spec !== "./pages/InboxPage",
    });
    check(
      "路由引用了不存在的页面文件被抓到",
      r.reds.some((x) => x.includes("./pages/InboxPage")),
    );
  }

  // 4. 只 import 而没接进任何 <Route> → 等于漏接，必须红
  //    （这正是「名字出现过 ≠ 拦得住」那个坑：只查 import 存在性的断言会放过它）
  {
    const appSource = goodApp.replace(
      '<Route path="/inbox" element={\n              <Suspense fallback={<p className="hint">加载…</p>}>\n                <InboxPage />\n              </Suspense>\n            } />',
      '<Route path="/inbox" element={<Shell />} />',
    );
    const r = analyze({
      appSource,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check(
      "只 import 未接路由的页面被抓到",
      r.reds.some((x) => x.includes("InboxPage.tsx")),
    );
  }

  // 5. 布局路由没有 path 不许被当成缺漏
  {
    const r = analyze({
      appSource: goodApp,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check(
      "无 path 的布局路由不算红",
      !r.reds.some((x) => x.includes("(无 path")),
    );
  }

  // 6. 嵌套路由归父路由 chunk 的问题：子路由的组件不许算到父路由上
  {
    const r = analyze({
      appSource: goodApp,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    const shellRoute = r.routes.find((x) => x.path === null);
    check(
      "父路由只含自己的组件（无子路由的组件混入）",
      shellRoute && shellRoute.refs.every((x) => x.name === "Shell"),
    );
  }

  // 7. ★ 扩展名省略：`./pages/LoginPage` 必须解析到 `LoginPage.tsx`。
  //    这是一个**真的会全红**的 bug（第一版就栽在这里，19 条假红）。
  //    反向对照成对：候选里必须含 `.tsx`，且不能只等于裸路径。
  {
    const cands = candidatePaths("/x/src/pages/LoginPage");
    check("候选含裸路径", cands.includes("/x/src/pages/LoginPage"));
    check(
      "候选含 .tsx（省略扩展名能解析）",
      cands.includes("/x/src/pages/LoginPage.tsx"),
    );
    check(
      "裸路径本身不足以判存在（证明是扩展名那一步在起作用）",
      !cands.slice(0, 1).includes("/x/src/pages/LoginPage.tsx"),
    );
  }

  // 8. ★ 注释掉的路由必须算「没有这条路由」（`stripComments`）。
  //    这是本脚本第一版的真事故：把路由注释掉，脚本仍读到 `<Route` 与
  //    `<InboxPage />`，判定「接上了」，**退 0 全绿**。
  {
    // 两个方向都要证：注释掉必须红、没注释不许红（否则判据恒真）。
    const blockCommented = goodApp.replace(
      '            <Route path="/queue" element={<QueuePage />} />',
      '            {/* <Route path="/queue" element={<QueuePage />} /> */}',
    );
    const rBlock = analyze({
      appSource: blockCommented,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check(
      "块注释 {/* … */} 掉的路由算作没接",
      rBlock.reds.some((x) => x.includes("QueuePage.tsx")),
    );

    const lineCommented = goodApp.replace(
      '            <Route path="/queue" element={<QueuePage />} />',
      '            // <Route path="/queue" element={<QueuePage />} />',
    );
    const rLine = analyze({
      appSource: lineCommented,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check(
      "行注释 // 掉的路由算作没接",
      rLine.reds.some((x) => x.includes("QueuePage.tsx")),
    );

    // 反向对照：字符串里出现 `//` 或 `/*` 不许被当成注释吃掉后面真正的路由。
    const stringy = goodApp.replace(
      'import QueuePage from "./pages/QueuePage";',
      'import QueuePage from "./pages/QueuePage";\n    const url = "https://example.com/queue";',
    );
    const rStr = analyze({
      appSource: stringy,
      pageFiles: ["QueuePage.tsx", "InboxPage.tsx"],
      specExists: allExist,
    });
    check(
      "字符串里的 // 不吃掉后面的路由（反向对照）",
      rStr.reds.length === 0 && rStr.routedSpecs.has("./pages/QueuePage"),
    );
  }

  let failed = 0;
  for (const [label, ok] of checks) {
    console.log(`${ok ? "✓" : "✗"} ${label}`);
    if (!ok) failed += 1;
  }
  if (failed) {
    console.error(`❌ ${failed}/${checks.length} 项失败`);
    return 1;
  }
  console.log(`✅ ${checks.length}/${checks.length} 项通过`);
  return 0;
}

process.exit(SELFTEST ? selftest() : main());
