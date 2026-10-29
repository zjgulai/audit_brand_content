#!/usr/bin/env node
/**
 * verify_prod_pages_authed.mjs —— **登录后**逐页验收（只读，不写业务数据）。
 *
 * ## 与 `verify_prod_pages.mjs` 的分工
 *
 * · `verify_prod_pages.mjs`：无凭据，只能验「未登录是否被送回登录页」。
 * · 本文件：**连一个已经登录好的 Chrome**（由人手动登录），验真正的业务页面。
 *
 * 两件事必须分开，因为它们的失败含义完全不同：前者坏了是上线事故，
 * 后者坏了可能只是某个人的会话过期。
 *
 * ## 它绝不做什么（这决定它能不能在真生产上跑）
 *
 * 不点「认领 / 提交 / 签发 / 下线 / 撤权 / 转交」等**改变状态**的按钮。
 * 只做四件只读的事：
 *   ① 打开页面、等数据到位
 *   ② 读渲染结果（文字长度、标题、可聚焦元素、溢出、错误）
 *   ③ 读「空态 / 错误态 / 加载态」三态里实际是哪一个
 *   ④ 记录该页现有的按钮与控件清单（供人工验收时对照）
 *
 * ★ 判据里有一条很容易写错：「页面有内容」不等于「业务数据正确」。
 *   所以本文件对**每一页**都单独声明它该出现什么特征文本 —— 而不是统一
 *   判一个「文字 > 0」。统一判会让「加载失败的兜底文案」也算通过。
 *
 * 用法：
 *   node web/scripts/verify_prod_pages_authed.mjs --port 9444 --out /tmp/authed.json
 *
 * 退出码：0 全部符合 / 1 有红 / 2 未测（连不上、或未登录）
 */
import fs from "node:fs";
import path from "node:path";

function arg(name, fallback = "") {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const PORT = Number(arg("port", "9444"));
const OUT = arg("out", "");
const BASE = (arg("base", "https://ca.luteos.com")).replace(/\/$/, "");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * 每页的期望。`must` 是**该页独有的特征串**（不是通用词）：
 * 写成「内容审核工作台」这种全站都有的词，等于什么都没验。
 */
const PAGES = [
  {
    path: "/queue", name: "复核队列",
    must: ["待人工复核"],
    controls: ["认领", "草稿", "复核"],
  },
  {
    path: "/inbox", name: "收件箱与我的内容",
    must: ["待办收件箱"],
    controls: [],
  },
  {
    // ★★★ 2026-10-29 实测发现：`/my-cases` 路由渲染的是**和 `/inbox` 同一个组件**
    //   （`App.tsx:44-49` → `InboxPage`），页面内容逐字相同。
    //   而 `AppShell.tsx:71-91` 的侧边栏 11 个入口里**没有 `/my-cases`** ——
    //   也就是这条路由**界面上没有入口**，只能靠手输地址到达。
    //
    //   ★ 所以这里的 `must` 写的是该页**真实渲染出来的**内容（待办收件箱），
    //     不是 PRD 里那个页签名。写页签名会让这一页永远红，而红的原因
    //     是「路由和入口不一致」，不是「页面渲染坏了」—— 两件事要分开报。
    //     后者已单独记在 issue 侧（见提交说明与 WBPM-0144 的追加）。
    path: "/my-cases", name: "我的内容（无侧栏入口）",
    must: ["待办收件箱"],
    controls: [],
  },
  {
    path: "/cases", name: "案件总览",
    must: ["案件"],
    controls: ["筛选", "搜索", "重置"],
  },
  {
    path: "/submit", name: "提交内容审查",
    must: ["提交", "内容"],
    controls: ["提交"],
  },
  {
    path: "/appeals", name: "申诉中心",
    must: ["申诉"],
    controls: [],
  },
  {
    path: "/release", name: "签发中心",
    must: ["签发"],
    controls: ["签发"],
  },
  {
    path: "/takedown", name: "下线任务台",
    must: ["下线"],
    controls: [],
  },
  {
    path: "/reports", name: "报告索引",
    must: ["报告"],
    controls: [],
  },
  {
    path: "/taxonomy", name: "分类规范与规则",
    must: ["分类", "规则"],
    controls: [],
  },
  {
    path: "/admin/grants", name: "授权名单治理",
    must: ["授权"],
    controls: [],
  },
  {
    path: "/admin/sessions", name: "会话与安全审计",
    must: ["会话"],
    controls: [],
  },
];

/** 这些词出现 = 页面进了错误态。比「文字 > 0」有用得多。 */
const ERROR_MARKERS = [
  "加载失败", "请求失败", "网络错误", "出错了",
  "500", "Internal Server Error", "Failed to fetch",
];

async function main() {
  // ── 连上那个人已经登录好的标签页 ────────────────────────────────────────
  let target = null;
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    target = list.find((t) => t.type === "page" && t.url.includes("ca.luteos.com"));
  } catch (e) {
    console.log(`⚠ 未测：连不上调试端口 ${PORT}：${e.message}`);
    return 2;
  }
  if (!target) {
    console.log(`⚠ 未测：端口 ${PORT} 上没有 ca.luteos.com 的标签页`);
    return 2;
  }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = () => rej(new Error("WebSocket 连不上"));
  });

  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (!m.id) {
      events.push(m);
      return;
    }
    const p = pending.get(m.id);
    if (!p) return;
    pending.delete(m.id);
    m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
  };
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const i = ++id;
      pending.set(i, { res, rej });
      ws.send(JSON.stringify({ id: i, method, params }));
    });
  const evaluate = async (expr) => {
    const r = await send("Runtime.evaluate", {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (r?.exceptionDetails) {
      throw new Error(
        r.exceptionDetails.exception?.description || r.exceptionDetails.text,
      );
    }
    return r?.result?.value;
  };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");

  // ── 前置：确认仍然登录着 ────────────────────────────────────────────────
  const me = await evaluate(`(async () => {
    const r = await fetch('/api/v1/me', { credentials: 'include' });
    return { status: r.status, body: r.ok ? await r.json() : null };
  })()`);
  if (me?.status !== 200) {
    console.log(`⚠ 未测：当前标签页未登录（/api/v1/me = ${me?.status}）`);
    ws.close();
    return 2;
  }
  console.log("=".repeat(78));
  console.log(`登录后逐页验收 · ${BASE}（只读，不点任何改变状态的按钮）`);
  console.log(`身份：${JSON.stringify(me.body).slice(0, 200)}`);
  console.log("=".repeat(78));

  const results = [];

  for (const pg of PAGES) {
    events.length = 0;

    // ★★★ 2026-10-29 实测教训：第一版用 `history.pushState` + popstate 做 SPA 内跳，
    //   结果 /my-cases 报「缺特征我的内容」—— 而它读到的是**上一个页面**（/inbox）的内容。
    //   react-router 不吃手工 pushState 的事件，页面根本没换。
    //   ★ 这类失败最坑：它报的红是**脚本的错**，看起来却像页面坏了。
    //
    //   改成整页导航（Page.navigate）—— 慢一点，但「测的确实是这一页」。
    //   代价是每页重新拉静态资源，所以等待时间要按「冷」算，不能按「热」算。
    await send("Page.navigate", { url: BASE + pg.path });
    await sleep(600);

    // 等数据到位：等到「不再有骨架屏」或超时。
    // 直接 sleep 一个固定值会两头不讨好 —— 快了读到骨架屏，慢了白等。
    //
    // ★★★ 2026-10-29 实测：第一版这个循环**没起作用**。
    //   判据是 `busy.skeleton === 0 && busy.len > 80` —— 而骨架屏 + 页头
    //   就能凑够 80 字，于是循环第一次就 break，读到的是**加载中的页面**。
    //   表现：/queue 文本 272 → 189、骨架 0 → 4，却判成 ✅。
    //
    //   现在改成三点：① 骨架必须为 0；② 文本要超过**该页基线的一半**
    //   （基线取自上一轮稳定读数）；③ 连续两次读到相同文本才算稳定。
    //   稳定判据是关键 —— 只判「骨架为 0」会撞上「骨架刚撤、数据还没填」的那一瞬。
    let prevLen = -1;
    let stable = 0;
    for (let i = 0; i < 30; i++) {
      const busy = await evaluate(`(() => ({
        skeleton: document.querySelectorAll('.skeleton, [class*="skeleton"], [aria-busy="true"]').length,
        len: ((document.querySelector('#main') || document.body).innerText || '').trim().length,
      }))()`);
      const len = busy?.len ?? 0;
      const noSkeleton = (busy?.skeleton ?? 0) === 0;
      if (noSkeleton && len > 80 && len === prevLen) stable++;
      else stable = 0;
      if (stable >= 2) break;
      prevLen = len;
      await sleep(300);
    }

    const v = await evaluate(`(() => {
      const main = document.querySelector('#main') || document.body;
      const txt = (main.innerText || '').replace(/\\s+/g, ' ').trim();
      const sw = document.documentElement.scrollWidth;
      const iw = window.innerWidth;
      const btns = Array.from(document.querySelectorAll('button, a.btn, [role="button"]'))
        .map(b => (b.innerText || b.getAttribute('aria-label') || '').replace(/\\s+/g,' ').trim())
        .filter(Boolean);
      const h1 = Array.from(document.querySelectorAll('h1')).map(e => e.innerText.trim());
      // 三态探针：骨架屏 / 空态 / 错误
      const skeleton = document.querySelectorAll(
        '.skeleton, [class*="skeleton"], [aria-busy="true"]'
      ).length;
      const alerts = Array.from(document.querySelectorAll('[role="alert"]'))
        .map(e => (e.innerText || '').replace(/\\s+/g,' ').trim().slice(0, 80));
      return {
        path: location.pathname,
        textLen: txt.length,
        textHead: txt.slice(0, 260),
        h1,
        buttons: [...new Set(btns)].slice(0, 14),
        skeleton,
        alerts,
        overflow: sw > iw + 1,
        sw, iw,
      };
    })()`);

    const diag = events.filter(
      (m) => m.method === "Runtime.exceptionThrown",
    ).map((m) => m.params?.exceptionDetails?.exception?.description || "exception");
    const netFail = events
      .filter((m) => m.method === "Network.responseReceived")
      .map((m) => ({ s: m.params?.response?.status, u: String(m.params?.response?.url || "") }))
      .filter((x) => x.s >= 400)
      .map((x) => `${x.s} ${x.u}`);

    const txt = v?.textHead || "";
    const hitError = ERROR_MARKERS.filter((m) => txt.includes(m));
    const hitMust = pg.must.filter((m) => txt.includes(m));
    const missingMust = pg.must.filter((m) => !txt.includes(m));
    // ★ 先确认「测的确实是这一页」。第一版没这条，于是脚本自己的跳转失败
    //   被读成「页面缺特征」。有了它，跳转失败会单独指出来。
    const landed = v?.path === pg.path;

    const ok =
      landed &&
      (v?.textLen ?? 0) > 80 &&
      // ★ 骨架屏还在 = 页面没加载完。判绿等于把「加载中」当成「已可用」。
      (v?.skeleton ?? 0) === 0 &&
      missingMust.length === 0 &&
      hitError.length === 0 &&
      !v?.overflow &&
      diag.length === 0;

    results.push({
      ...pg, ok, landed,
      reading: v,
      missingMust, hitError,
      jsErrors: diag.slice(0, 3),
      netFail: netFail.filter((x) => !x.includes("/api/v1/me")).slice(0, 4),
    });

    const mark = ok ? "✅" : "❌";
    console.log(
      `  ${mark} ${pg.path.padEnd(18)} ${pg.name.padEnd(12)} ` +
      `文本=${String(v?.textLen ?? 0).padStart(5)} ` +
      `骨架=${v?.skeleton ?? 0} h1=${v?.h1?.length ?? 0} ` +
      `按钮=${v?.buttons?.length ?? 0}` +
      (ok ? "" : `  ← ${[
        landed ? "" : `跳转没到（实际停在 ${v?.path}）`,
        missingMust.length ? `缺特征「${missingMust.join("/")}」` : "",
        hitError.length ? `错误态「${hitError.join("/")}」` : "",
        (v?.skeleton ?? 0) > 0 ? `仍在加载（骨架屏 ${v?.skeleton}）` : "",
        diag.length ? "JS 异常" : "",
        v?.overflow ? "横向溢出" : "",
        (v?.textLen ?? 0) <= 80 ? "内容过少" : "",
      ].filter(Boolean).join(" / ")}`),
    );
    if (!ok) {
      console.log(`       实见：${(v?.textHead || "").slice(0, 160)}`);
      if (v?.alerts?.length) console.log(`       告警：${v.alerts.join(" | ")}`);
      if (diag.length) console.log(`       JS：${diag.slice(0, 2).join(" | ")}`);
      if (netFail.length) console.log(`       请求：${netFail.slice(0, 3).join(" | ")}`);
    } else {
      console.log(`       按钮：${(v?.buttons || []).join(" · ") || "（无）"}`);
    }
  }

  const red = results.filter((r) => !r.ok);
  console.log("-".repeat(78));
  console.log(
    red.length === 0
      ? `✅ ${results.length}/${results.length} 页：特征文本命中、无错误态、无 JS 异常、无溢出`
      : `❌ ${red.length}/${results.length} 页有红`,
  );

  if (OUT) {
    fs.mkdirSync(path.dirname(path.resolve(OUT)), { recursive: true });
    fs.writeFileSync(
      OUT,
      JSON.stringify({ base: BASE, at: new Date().toISOString(), me: me.body, results }, null, 2),
    );
    console.log(`读数已落盘：${OUT}`);
  }
  ws.close();
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
