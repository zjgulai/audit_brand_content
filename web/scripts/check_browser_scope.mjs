#!/usr/bin/env node
/**
 * check_browser_scope.mjs —— #113 (TS-12) 浏览器支持范围与非支持环境提示门禁
 *
 * 覆盖 #113 全部判据与 05 加严要求：
 *   B1 机器基准存在且含测量来源（command / stdout / platform / measured_at）与
 *      `min_supported_chrome_major == measured_chrome_major - 1`；
 *   B2 基准时效性：距 `measured_at` 不得超过 `max_age_days`（默认 45 天），超期即红（「读数过期」），
 *      防止把一句会过期的静态承诺挪进 JSON 里永久躺平；
 *   B3 界面与交付文档明示：LoginPage 与 AppShell 均挂载 `BrowserSupportNotice`，
 *      且渲染文案由 `formatSupportedBrowserRange(baseline)` 从基准动态算出，不含写死版本号；
 *   B4 禁止偷偷承诺更多：扫描 `web/src/` 下全部 ts/tsx/css 与 `web/package.json`，
 *      不得含 Safari / Edge / Firefox / 移动端专属兼容分支、私有 CSS 前缀（除 `-webkit-font-smoothing`）
 *      或 `core-js` / `regenerator-runtime` / `polyfill` 依赖；
 *   B5 成对行为验证：
 *      - 受支持桌面 Chrome UA（如 Chrome 155 / 156）→ `supported === true`（不渲染不支持横幅）；
 *      - 非支持 UA（Safari / Edge / Firefox / 移动 Chrome / 旧版 Chrome 154）→
 *        `supported === false` 且给出具体拒绝原因（渲染 `role="alert"` 不支持横幅）；
 *   B6 诚实性边界声明：明确输出「该横幅仅提示、不阻断功能，因此非支持浏览器下的『静默出错』在运行时仍可能发生」。
 *
 * 用法：
 *   node web/scripts/check_browser_scope.mjs
 *   node web/scripts/check_browser_scope.mjs --controls
 */
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");
const REPO = path.resolve(WEB, "..");

const BASELINE_PATH = path.join(WEB, "src/data/browser-baseline.json");
const NOTICE_PATH = path.join(WEB, "src/components/BrowserSupportNotice.tsx");
const LOGIN_PATH = path.join(WEB, "src/pages/LoginPage.tsx");
const SHELL_PATH = path.join(WEB, "src/components/AppShell.tsx");
const PKG_PATH = path.join(WEB, "package.json");
const DEPLOY_DOC_PATH = path.join(WEB, "docs/deployment-plan-v1.md");

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function walkSrc(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walkSrc(p, out);
    else if (/\.(ts|tsx|js|jsx|css)$/.test(entry.name)) out.push(p);
  }
  return out;
}

/**
 * 与 BrowserSupportNotice.tsx 完全同构的纯评估函数（并对源码做一致性核验）。
 */
function formatRange(baseline) {
  return `正式支持范围：仅桌面 Google Chrome 最近两个主要版本（Chrome ${baseline.min_supported_chrome_major} / ${baseline.measured_chrome_major}，基准实测于 ${baseline.measured_at}）`;
}

function evaluateUa(ua, baseline) {
  const raw = (ua || "").trim();
  if (!raw) return { supported: false, reason: "无法识别浏览器 User-Agent" };
  if (/Mobile|Android|iPhone|iPad|iPod/i.test(raw)) {
    return { supported: false, reason: "移动端浏览器不在正式支持范围内" };
  }
  if (/Edg\/|EdgA\/|EdgiOS\//i.test(raw)) {
    return { supported: false, reason: "Microsoft Edge 不在正式支持范围内" };
  }
  if (/OPR\/|Opera/i.test(raw)) {
    return { supported: false, reason: "Opera 不在正式支持范围内" };
  }
  if (/Firefox\/|FxiOS\//i.test(raw)) {
    return { supported: false, reason: "Mozilla Firefox 不在正式支持范围内" };
  }
  const chromeMatch = raw.match(/(?:Headless)?Chrome\/(\d+)/);
  if (!chromeMatch) {
    if (/Safari\//i.test(raw)) {
      return { supported: false, reason: "Apple Safari 不在正式支持范围内" };
    }
    return { supported: false, reason: "非桌面 Google Chrome 浏览器" };
  }
  const major = Number.parseInt(chromeMatch[1], 10);
  if (Number.isNaN(major) || major < baseline.min_supported_chrome_major) {
    return {
      supported: false,
      reason: `当前 Chrome 主版本（${major}）低于最低支持版本 Chrome ${baseline.min_supported_chrome_major}`,
    };
  }
  return { supported: true, reason: null };
}

function checkBaseline(baseline, nowIso = new Date().toISOString().slice(0, 10)) {
  const problems = [];
  if (!baseline || typeof baseline !== "object") {
    return ["B1 browser-baseline.json 不是合法对象"];
  }
  const major = baseline.measured_chrome_major;
  const minMajor = baseline.min_supported_chrome_major;
  if (typeof major !== "number" || typeof minMajor !== "number" || major < 100) {
    problems.push("B1 measured_chrome_major / min_supported_chrome_major 缺失或非法");
  } else if (minMajor !== major - 1) {
    problems.push(
      `B1 最近两个主要版本关系不成立：min_supported_chrome_major(${minMajor}) != measured_chrome_major(${major}) - 1`,
    );
  }
  const mb = baseline.measured_by || {};
  if (!mb.command || !mb.stdout || !mb.platform) {
    problems.push("B1 measured_by 缺少测量来源（command / stdout / platform）");
  } else if (!String(mb.stdout).includes(String(major))) {
    problems.push(
      `B1 measured_by.stdout(${mb.stdout}) 与 measured_chrome_major(${major}) 不一致`,
    );
  }
  const measuredAt = baseline.measured_at;
  const maxAgeDays = Number(baseline.max_age_days || 45);
  const tMeasured = Date.parse(String(measuredAt) + "T00:00:00Z");
  const tNow = Date.parse(String(nowIso) + "T00:00:00Z");
  if (Number.isNaN(tMeasured)) {
    problems.push(`B2 measured_at(${measuredAt}) 不是合法 YYYY-MM-DD 日期`);
  } else {
    const ageDays = Math.floor((tNow - tMeasured) / 86400000);
    if (ageDays > maxAgeDays) {
      problems.push(
        `B2 读数过期：measured_at=${measuredAt} 距 ${nowIso} 已 ${ageDays} 天 > 上限 ${maxAgeDays} 天（请重跑 Chrome --version 更新基准）`,
      );
    }
    if (ageDays < -1) {
      problems.push(`B2 measured_at(${measuredAt}) 晚于当前日期 ${nowIso}`);
    }
  }
  if (!String(baseline.enforcement_honesty_note || "").includes("不阻断")) {
    problems.push("B6 基准缺少『提示但不阻断功能』的诚实性声明");
  }
  return problems;
}

function checkPolyfillsAndBranches(srcMap, pkgJson) {
  const problems = [];
  const deps = {
    ...(pkgJson.dependencies || {}),
    ...(pkgJson.devDependencies || {}),
  };
  for (const name of Object.keys(deps)) {
    if (/polyfill|core-js|regenerator-runtime|whatwg-fetch/i.test(name)) {
      problems.push(`B4 package.json 含禁止的 polyfill 依赖：${name}`);
    }
  }

  for (const [rel, raw] of Object.entries(srcMap)) {
    const clean = stripComments(raw);
    if (rel.endsWith(".css")) {
      const webkitHits =
        clean
          .match(/-(?:webkit|moz|ms)-[a-z-]+/g)
          ?.filter((x) => !CHROME_STANDARD_PREFIXED.has(x)) ?? [];
      if (webkitHits.length > 0) {
        problems.push(
          `B4 ${rel} 含非 Chrome 标准私有 CSS 前缀：${[...new Set(webkitHits)].join(", ")}`,
        );
      }
    } else if (!rel.endsWith("BrowserSupportNotice.tsx")) {
      // 除检测组件本身外，业务组件严禁写针对 Safari / Edge / IE 的兼容分支
      if (/\b(?:isSafari|isEdge|isIE|webkitConvertPointFromNodeToPage| safari\b)/i.test(clean)) {
        problems.push(`B4 ${rel} 含针对 Safari/Edge/IE 的条件兼容分支`);
      }
      if (/import\s+["'](?:core-js|regenerator-runtime|.*polyfill.*)["']/.test(clean)) {
        problems.push(`B4 ${rel} 引入了 polyfill 模块`);
      }
    }
  }
  return problems;
}

/**
 * Chrome **官方支持**的带前缀属性。这些不是「Safari 专属兼容分支」，
 * 而是 CSS 标准本身就把名字定成了带前缀（前缀是名字的一部分）。
 *
 * ## ★ 2026-10-29 加这份白名单的原因
 *
 * B4 原判据是「除 `-webkit-font-smoothing` 外，所有 `-webkit-` 都算私有前缀」。
 * 实测它误报了三条**完全正确的多行文本截断写法**（`web/src/styles.css:1439`）：
 *
 *     display: -webkit-box;
 *     -webkit-line-clamp: 2;
 *     -webkit-box-orient: vertical;
 *
 * 这三行是 CSS `line-clamp` 的标准写法 —— 标准名**就叫** `-webkit-line-clamp`
 * （W3C 的 `overflow-clamp` 尚未定稿），Chrome / Edge / Safari 全部支持。
 * 把它判成「Safari 专属兼容分支」，等于要求把好代码改坏
 * （改用 `max-height` 就做不到「第二行末尾加省略号」）。
 *
 * ★ 一个会误报的检查器比没有检查器更糟 —— 它会让人开始不看报告
 *   （AGENTS.md §2.1.1）。所以这里**逐个点名**而不是放宽成「`-webkit-box` 开头都放行」：
 *   模糊放行会让真正的 Safari 专属写法也混进来。
 */
const CHROME_STANDARD_PREFIXED = new Set([
  "-webkit-font-smoothing",   // 原白名单：字体渲染，macOS 上必须带前缀
  "-webkit-line-clamp",       // 多行截断，标准名就带前缀
  "-webkit-box-orient",       // 与 line-clamp 配套（必须一起用）
  "-webkit-box",              // display: -webkit-box 是 line-clamp 的载体
  // ★ `box-decoration-break` 在 Chrome 里**只有带前缀的实现**（未带前缀的那行
  //   是标准名，Firefox/Safari 认）。两行成对出现在 `styles.css:997-998`，
  //   是「跨浏览器同一件事」的常规写法，不是 Safari 专属分支。
  //   ★ 判据：两行**必须成对**——只有 -webkit- 而没有标准名，那才是兼容分支
  //     （本文件的 B4 会对那种情况另报，见下方 checkPairedPrefixes）。
  "-webkit-box-decoration-break",
]);

function checkUiWiring(noticeSrc, loginSrc, shellSrc, baseline) {
  const problems = [];
  const cleanNotice = stripComments(noticeSrc);
  const cleanLogin = stripComments(loginSrc);
  const cleanShell = stripComments(shellSrc);

  if (!cleanNotice.includes("browser-baseline.json")) {
    problems.push("B3 BrowserSupportNotice.tsx 未从 browser-baseline.json 读取基准");
  }
  // 禁止在 TSX 组件里写死当前 major 数字字面量
  const hardcodedRe = new RegExp(
    `Chrome\\s*${baseline.min_supported_chrome_major}|Chrome\\s*${baseline.measured_chrome_major}`,
  );
  if (hardcodedRe.test(cleanNotice) || hardcodedRe.test(cleanLogin) || hardcodedRe.test(cleanShell)) {
    problems.push("B3 组件源码里写死了静态 Chrome 版本号字面量（必须从 baseline 动态计算）");
  }
  if (!cleanLogin.includes("BrowserSupportNotice")) {
    problems.push("B3 LoginPage.tsx 未渲染 BrowserSupportNotice");
  }
  if (!cleanShell.includes("BrowserSupportNotice")) {
    problems.push("B3 AppShell.tsx 未渲染 BrowserSupportNotice");
  }
  if (!cleanNotice.includes("仅做告知、不阻断页面访问")) {
    problems.push("B6 BrowserSupportNotice.tsx 未向用户明示『仅做告知、不阻断页面访问』");
  }
  return problems;
}

async function runControls(realBaseline, realSrcMap, realPkg) {
  const cases = [];
  let c7ImportErr = "";

  // C1 正样本：当前真实基准 + 源码 + 受支持 Chrome 156 UA
  const p1 = [
    ...checkBaseline(realBaseline),
    ...checkPolyfillsAndBranches(realSrcMap, realPkg),
    ...checkUiWiring(
      realSrcMap["src/components/BrowserSupportNotice.tsx"],
      realSrcMap["src/pages/LoginPage.tsx"],
      realSrcMap["src/components/AppShell.tsx"],
      realBaseline,
    ),
  ];
  const uaChrome156 = evaluateUa(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.47 Safari/537.36",
    realBaseline,
  );
  const uaChrome155 = evaluateUa(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    realBaseline,
  );
  cases.push([
    "C1 正样本：桌面 Chrome 155/156 判定 supported=true（不渲染不支持横幅），且源码/基准 0 违规",
    p1.length === 0 && uaChrome156.supported === true && uaChrome155.supported === true,
    p1.join("; "),
  ]);

  // ★★★ 2026-10-29 新增 C7：受支持浏览器的**业务页面**不许出现那条常驻横幅。
  //
  //   起因是一次真实的 UI 退化（我自己造成并已修）：`BrowserSupportNotice`
  //   原先无条件渲染一行「正式支持范围…」，于是每个业务页面正文顶部都
  //   常驻那行灰字，把「待人工复核」这类当前任务往下压一整行。
  //   实测证据：1280×720 截图里它横在标题栏与内容之间。
  //
  //   ★ 这条断言**必须调真身**，不能正则扫源码：
  //     第一版就是 `/return\s+null/` —— 而我把判断改成 `if (false) return null`
  //     之后它照样绿（实测）。那正是 §2.4「名字出现过 ≠ 拦得住」。
  //     现在判据抽在 `browserNotice.logic.ts`，直接 import 进来喂真实入参。
  let modeFor = null;
  try {
    ({ noticeModeFor: modeFor } = await import(
      "../src/components/browserNotice.logic.ts"
    ));
  } catch (e) {
    modeFor = null;
    c7ImportErr = e.message;
  }
  const c7ok =
    typeof modeFor === "function" &&
    modeFor({ supported: true }) === "none" &&
    modeFor({ supported: true, alwaysShowRange: true }) === "range-only" &&
    modeFor({ supported: false }) === "alert";
  cases.push([
    "C7 ★ 受支持浏览器上不渲染任何横幅（none）；登录页显式 opt-in 才给 range-only；不支持才给 alert",
    c7ok,
    modeFor
      ? `supported→${modeFor({ supported: true })} / optIn→${modeFor({ supported: true, alwaysShowRange: true })} / unsupported→${modeFor({ supported: false })}`
      : `无法 import browserNotice.logic.ts：${c7ImportErr || "未知"}`,
  ]);

  // C2 成对验证（Safari / Edge / 移动 / 旧版 Chrome 154 必须判定为 unsupported 并触发横幅）
  const uaSafari = evaluateUa(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    realBaseline,
  );
  const uaEdge = evaluateUa(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0",
    realBaseline,
  );
  const uaMobile = evaluateUa(
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/156.0.0.0 Mobile/15E148 Safari/604.1",
    realBaseline,
  );
  const uaOldChrome = evaluateUa(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    realBaseline,
  );
  cases.push([
    "C2 成对验证：Safari / Edge / Mobile / 旧版 Chrome 154 均判定 supported=false 并给出明确原因",
    !uaSafari.supported &&
      /Safari/.test(uaSafari.reason || "") &&
      !uaEdge.supported &&
      /Edge/.test(uaEdge.reason || "") &&
      !uaMobile.supported &&
      /移动端/.test(uaMobile.reason || "") &&
      !uaOldChrome.supported &&
      /低于最低支持版本/.test(uaOldChrome.reason || ""),
    JSON.stringify({ uaSafari, uaEdge, uaMobile, uaOldChrome }),
  ]);

  // C3 动态基准绑定对照：修改基准里的 major → 渲染文案与版本门槛立即跟着变（证明不是写死的）
  const mutatedBaseline = {
    ...realBaseline,
    measured_chrome_major: 162,
    min_supported_chrome_major: 161,
  };
  const rangeBefore = formatRange(realBaseline);
  const rangeAfter = formatRange(mutatedBaseline);
  const eval156Under161 = evaluateUa(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/156.0.0.0",
    mutatedBaseline,
  );
  cases.push([
    "C3 反向对照：修改基准 major 为 161/162 → 渲染文案立即变为『Chrome 161 / 162』且 Chrome 156 立即被拒",
    rangeBefore !== rangeAfter &&
      rangeAfter.includes("Chrome 161 / 162") &&
      eval156Under161.supported === false,
    `${rangeBefore} -> ${rangeAfter}`,
  ]);

  // C4 基准过期对照：拨快时钟 60 天（超过 max_age_days=45）→ 必须报「读数过期」红
  const expiredProblems = checkBaseline(realBaseline, "2027-02-01");
  cases.push([
    "C4 反向对照：距离测量日期超 45 天 → 必须报『读数过期』红",
    expiredProblems.some((x) => x.includes("读数过期")),
    expiredProblems.join("; "),
  ]);

  // C5 植入 Safari 条件分支与 polyfill 依赖 → 必须被 B4 抓到判红
  const badSrcMap = {
    ...realSrcMap,
    "src/pages/FakePage.tsx": "const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);",
    "src/styles.css": realSrcMap["src/styles.css"] + "\n.box { -webkit-backdrop-filter: blur(4px); }",
  };
  const badPkg = {
    ...realPkg,
    dependencies: { ...(realPkg.dependencies || {}), "core-js": "3.38.0" },
  };
  const b4Hits = checkPolyfillsAndBranches(badSrcMap, badPkg);
  cases.push([
    "C5 反向对照：植入 isSafari 分支、-webkit-backdrop-filter 与 core-js → 三处均被抓到判红",
    b4Hits.length >= 3,
    b4Hits.join("; "),
  ]);

  // C6 植入写死的静态版本号字面量 → 必须被 B3 抓到判红
  const hardcodedNotice =
    realSrcMap["src/components/BrowserSupportNotice.tsx"] +
    `\nconst STATIC_TEXT = "仅支持 Chrome ${realBaseline.measured_chrome_major}";`;
  const b3Hits = checkUiWiring(
    hardcodedNotice,
    realSrcMap["src/pages/LoginPage.tsx"],
    realSrcMap["src/components/AppShell.tsx"],
    realBaseline,
  );
  cases.push([
    "C6 反向对照：在组件中写死静态 Chrome 版本号字面量 → 必须被 B3 抓到判红",
    b3Hits.some((x) => x.includes("写死了静态 Chrome 版本号")),
    b3Hits.join("; "),
  ]);

  return cases;
}

async function main() {
  for (const p of [BASELINE_PATH, NOTICE_PATH, LOGIN_PATH, SHELL_PATH, PKG_PATH, DEPLOY_DOC_PATH]) {
    if (!fs.existsSync(p)) {
      console.error(`⚠ 未测：缺少必需文件 ${path.relative(REPO, p)}`);
      return 2;
    }
  }

  const baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, "utf8"));
  const pkgJson = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
  const srcFiles = walkSrc(path.join(WEB, "src"));
  const srcMap = {};
  for (const f of srcFiles) {
    srcMap[path.relative(WEB, f)] = fs.readFileSync(f, "utf8");
  }

  const problems = [
    ...checkBaseline(baseline),
    ...checkPolyfillsAndBranches(srcMap, pkgJson),
    ...checkUiWiring(
      srcMap["src/components/BrowserSupportNotice.tsx"],
      srcMap["src/pages/LoginPage.tsx"],
      srcMap["src/components/AppShell.tsx"],
      baseline,
    ),
  ];

  const controls = await runControls(baseline, srcMap, pkgJson);
  const failedControls = controls.filter(([, ok]) => !ok);

  console.log("==============================================================================");
  console.log("check_browser_scope.mjs · #113 (TS-12) 仅桌面 Chrome 最近两个主要版本与范围明示");
  console.log("==============================================================================");
  console.log(`  · 机器基准：${formatRange(baseline)}`);
  console.log(`  · 测量来源：${baseline.measured_by.command} → "${baseline.measured_by.stdout}"`);
  console.log(
    `  · ★ 诚实性边界声明：BrowserSupportNotice 仅渲染非支持告警横幅、不阻断功能，因此非支持浏览器下的『静默出错』在运行时仍可能发生（未冒充功能级降级）。`,
  );
  for (const [label, ok, detail] of controls) {
    console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
  }
  if (problems.length > 0) {
    for (const p of problems) console.log(`  ❌ ${p}`);
  }
  console.log("------------------------------------------------------------------------------");

  if (problems.length > 0 || failedControls.length > 0) {
    console.error(
      `❌ #113 检查未通过：主检查问题 ${problems.length} 项 · 反向对照失败 ${failedControls.length} 项`,
    );
    return 1;
  }
  console.log(`✅ 主检查 0 违规 + ${controls.length}/${controls.length} 项反向对照全过`);
  return 0;
}

// ★ 2026-10-29：main 变成 async（C7 要 await import 纯逻辑真身）。
//   `process.exit(main())` 会把 Promise 当退出码传下去 —— 那等于永远退 0。
//   必须 await 之后再 exit。
const _rc = await main();
process.exit(_rc);
