#!/usr/bin/env node
/**
 * verify_prod_pages.mjs —— 对着**生产**逐页看真实渲染，只读、不写。
 *
 * ## 为什么不能只看 HTTP 状态码（本轮实测的假阳性）
 *
 * 2026-10-29 实测：对 `ca.luteos.com` 的 13 条路由逐个 `curl`，**全部 200**。
 * 但其中 12 条的响应体是**同一个 SPA 外壳**：
 *
 *     <div id="root"></div>
 *
 * 也就是「200」证明的是**静态文件服务器活着**，不证明任何页面渲染出来了。
 * 这是本项目 §2.4.1 第 5 行那个形状：一个读数比它的输入大。
 *
 * 所以本脚本用真实 Chrome 打开每页，读 **`#root` 里渲染出多少东西**，
 * 以及标题/可见文本/控制台错误 —— 那才是「页面能不能用」。
 *
 * ## 本脚本能测什么、不能测什么（必须说清）
 *
 * 生产需要飞书 OAuth 会话，未登录访问 `/api/v1/me` 是 401。所以：
 *
 *   ✅ 能测：未登录态是否正确跳转/提示（这本身就是一条验收）
 *   ✅ 能测：外壳、字体、配色、加载态、错误态是否渲染
 *   ✅ 能测：控制台有没有 JS 抛错、有没有资源 404
 *   ✅ 能测：横向溢出、可用焦点、语言属性
 *   ❌ 测不了：登录之后的业务页面（队列/详情/签发…）真业务数据下的表现
 *
 * ★ 不伪造登录：不塞假 cookie、不打开 dev identity（生产已正确地 403）。
 *
 * 退出码：0 全部符合预期 / 1 有红 / 2 环境不可用（Chrome 起不来）。
 */
import fs from "node:fs";
import path from "node:path";
import { launch, HarnessUntested } from "./lib/browser_harness.mjs";

const BASE = (process.env.PROD_BASE || "https://ca.luteos.com").replace(/\/$/, "");
const OUT = process.argv.includes("--out")
  ? process.argv[process.argv.indexOf("--out") + 1]
  : "";

/** 与 `web/src/App.tsx` 的 Route 一一对应。改路由要改这张表（照抄就是两个口径）。 */
const ROUTES = [
  { path: "/login", name: "登录页", expect: "login" },
  { path: "/submit", name: "提交内容审查", expect: "login" },
  { path: "/inbox", name: "收件箱与我的内容", expect: "login" },
  { path: "/my-cases", name: "我的内容", expect: "login" },
  { path: "/queue", name: "复核队列", expect: "login" },
  { path: "/cases", name: "案件总览", expect: "login" },
  { path: "/cases/case-prod", name: "案件详情", expect: "login" },
  { path: "/appeals", name: "申诉中心", expect: "login" },
  { path: "/release", name: "签发中心", expect: "login" },
  { path: "/takedown", name: "下线任务台", expect: "login" },
  { path: "/reports", name: "报告索引", expect: "login" },
  { path: "/reports/report-smoke", name: "报告详情", expect: "login" },
  { path: "/taxonomy", name: "分类规范与规则", expect: "login" },
  { path: "/admin/grants", name: "授权名单治理", expect: "login" },
  { path: "/admin/sessions", name: "会话与安全审计", expect: "login" },
];

/**
 * 判定「这一页渲染成了登录页」的标记。
 *
 * ★★★ 2026-10-29 实测教训：第一版把「出现 401」判成红，于是 8/15 页报红。
 *   而那些 401 是 `/api/v1/queue`、`/api/v1/cases` 这类**数据接口**在
 *   未登录时正常返回的 401 —— 正是它触发了「送回登录页」。
 *   **把正确的行为判成红**，比漏判更糟：它会让人开始无视报告（§2.1.1）。
 *
 * 所以未登录态的判据是「**被送回登录页**」，而不是「没有任何 4xx」。
 * 真正该红的是：白屏、JS 抛错、登录页本身渲染不出来。
 */
const LOGIN_MARKERS = ["使用飞书账号登录", "扫码"];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  let s;
  try {
    s = await launch({ width: 1280, height: 720 });
  } catch (e) {
    if (e instanceof HarnessUntested) {
      console.log(`⚠ 未测：${e.message}`);
      return 2;
    }
    throw e;
  }

  // ★ 用 harness 自带的诊断通道（`enableDiagnostics` / `takeDiagnostics`），
  //   不用自己挂 `cdp.on` —— `Session` 没有 `on()`，事件是攒在 `_events` 里
  //   由调用方「取走」的。自己再造一套监听会与它抢同一条 WebSocket。
  await s.enableDiagnostics();

  // ★ 预热：在正式遍历之前先访问一次根路径，把 bundle 下载进浏览器缓存。
  //   不预热时第一个路由（/login）在 1400ms 内只看到 #root=0 —— bundle 还没执行完。
  //   后续路由因为 bundle 已在内存里，同样的等待时间绰绰有余。
  //   这正是「第一次用的工具要先热身」的典型形态：它不是 /login 特有的坏，
  //   而是 Chrome 冷启动时每个第一条都会发生。
  await s.send("Page.navigate", { url: BASE + "/" });
  await sleep(2400);
  await s.takeDiagnostics();

  const results = [];

  for (const r of ROUTES) {
    await s.takeDiagnostics(); // 清空上一页的账，否则上一页的失败会算到这一页
    await s.send("Page.navigate", { url: BASE + r.path });
    await sleep(1400); // SPA 挂载 + 首个请求

    const v = await s.eval(`(() => {
        const root = document.querySelector("#root");
        const txt = (root?.innerText || "").replace(/\\s+/g, " ").trim();
        const sw = document.documentElement.scrollWidth;
        const iw = window.innerWidth;
        const h1 = Array.from(document.querySelectorAll("h1")).map(e => e.innerText.trim());
        const focusables = document.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ).length;
        return {
          url: location.pathname,
          lang: document.documentElement.lang || "",
          title: document.title,
          rootChildren: root ? root.children.length : -1,
          textLen: txt.length,
          textHead: txt.slice(0, 160),
          h1Count: h1.length,
          h1: h1.slice(0, 2),
          focusables,
          scrollWidth: sw,
          innerWidth: iw,
          overflow: sw > iw + 1,
        };
      })()`);

    const diag = s.takeDiagnostics();
    // ★ 未登录访问业务页时，数据接口返 401 是**正确**的 —— 它正是「送回登录页」
    //   的触发条件。所以这里不再把 401 当失败。真正要看的失败是
    //   静态资源 404/500（bundle 缺块、图片丢了）。
    const netFailures = diag.responses
      .filter((x) => x.status >= 400)
      .map((x) => ({ status: x.status, url: String(x.url) }))
      .filter((x) => !/\/api\/v1\//.test(x.url)) // 接口 4xx 归业务态，不归资源
      .map((x) => `${x.status} ${x.url}`);
    const consoleErrors = [...diag.consoleErrors, ...diag.exceptions];

    // ── 判据 ────────────────────────────────────────────────────────────────
    // ① 挂载了：SPA 的 #root 必须有子节点。空壳 = 白屏，而 HTTP 仍是 200。
    const mounted = (v.rootChildren ?? 0) > 0;
    // ② 有可见文字。
    const hasText = (v.textLen ?? 0) > 0;
    // ③ 恰好一个 h1（无障碍基线）。
    const oneH1 = v.h1Count === 1;
    // ④ 无横向溢出（1280×720 下）。
    const noOverflow = !v.overflow;
    // ⑤ 无未捕获的 JS 错误。
    const noJsError = consoleErrors.length === 0;
    // ⑥ 静态资源无 4xx/5xx。
    const noNetFail = netFailures.length === 0;
    // ⑦ html lang 非空。
    const hasLang = !!v.lang;
    // ⑧ ★ 未登录态**被送回登录页**（这是本探针在无凭据下能验的核心一项）。
    const routedToLogin = LOGIN_MARKERS.some((m) => (v.textHead || "").includes(m));

    const ok =
      mounted &&
      hasText &&
      oneH1 &&
      noOverflow &&
      noJsError &&
      noNetFail &&
      hasLang &&
      routedToLogin;

    results.push({
      ...r,
      ok,
      checks: {
        mounted,
        hasText,
        oneH1,
        noOverflow,
        noJsError,
        noNetFail,
        hasLang,
        routedToLogin,
      },
      reading: {
        rootChildren: v.rootChildren,
        textLen: v.textLen,
        textHead: v.textHead,
        h1: v.h1,
        focusables: v.focusables,
        scrollWidth: v.scrollWidth,
        innerWidth: v.innerWidth,
        title: v.title,
        lang: v.lang,
      },
      consoleErrors: [...consoleErrors],
      netFailures: [...netFailures],
    });
  }

  s.close();

  const red = results.filter((r) => !r.ok);
  console.log("=".repeat(78));
  console.log(`生产逐页渲染探针 · ${BASE}（未登录态，只读）`);
  console.log("=".repeat(78));
  for (const r of results) {
    const mark = r.ok ? "✅" : "❌";
    const c = r.checks;
    const broken = Object.entries(c)
      .filter(([, ok]) => !ok)
      .map(([k]) => k);
    console.log(
      `  ${mark} ${r.path.padEnd(22)} ${r.name.padEnd(12)} ` +
        `#root=${String(r.reading.rootChildren).padStart(2)} ` +
        `文本=${String(r.reading.textLen).padStart(4)} ` +
        `h1=${r.reading.h1.length} ` +
        `可聚焦=${String(r.reading.focusables).padStart(2)}` +
        (broken.length ? `  ← ${broken.join("/")}` : ""),
    );
    if (!r.ok) {
      if (r.reading.textHead) console.log(`       文本: ${r.reading.textHead}`);
      if (r.consoleErrors.length)
        console.log(`       控制台: ${r.consoleErrors.slice(0, 2).join(" | ")}`);
      if (r.netFailures.length)
        console.log(`       请求失败: ${r.netFailures.slice(0, 3).join(" | ")}`);
    }
  }
  console.log("-".repeat(78));

  // ★★★ 2026-10-29：这一行必须说清**测到了什么**。
  //   15 条路由全部渲染成同一个登录页（文本完全相同），因为生产需要飞书 OAuth。
  //   所以「15/15 绿」的意思是「未登录时每一条都被正确送回登录页」，
  //   **不是**「15 个业务页面都能用」。写成后者就是本文件最该避免的谎。
  const allLogin = results.every((r) => r.checks.routedToLogin);
  if (red.length === 0) {
    if (allLogin) {
      console.log(
        `✅ ${results.length}/${results.length} 条路由：未登录时**均被正确送回登录页**` +
          `（外壳挂载、单 h1、无溢出、无 JS 错、无资源失败）`,
      );
      console.log(
        `   ⚠ 但这只证明了「路由守卫与登录页」这一件事 —— 15 条路径渲染的都是**同一个登录页**，` +
          `业务页面在无凭据下**一条都没有被验到**。`,
      );
      console.log(`   要验业务页需要真实飞书会话（见操作指引第 2 步）。`);
    } else {
      console.log(
        `✅ ${results.length}/${results.length} 页：已挂载、有文字、单 h1、无溢出、无 JS 错、无失败请求`,
      );
    }
  } else {
    console.log(`❌ ${red.length}/${results.length} 页有红`);
  }

  if (OUT) {
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    fs.writeFileSync(OUT, JSON.stringify({ base: BASE, at: new Date().toISOString(), results }, null, 2));
    console.log(`读数已落盘：${OUT}`);
  }
  return red.length ? 1 : 0;
}

let rc = 2;
try {
  rc = await main();
} catch (e) {
  console.error(`⚠ 未测：${e?.message || e}`);
  rc = 2;
}
process.exit(rc);
