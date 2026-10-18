#!/usr/bin/env node
/**
 * a11y_check.mjs —— 三个页面的可自动化无障碍检查（WCAG 2.2 AA 基线，Chrome CDP）
 *
 * 自动检查（本脚本）：
 *   - html[lang] 非空
 *   - 每页恰好一个 h1
 *   - img 有非空 alt（本工程当前无 img）
 *   - input/select/textarea 有 label（label/for、包裹 label、aria-label/labelledby）
 *   - 按钮有可访问名称
 *   - skip-link 存在且指向 #main
 *   - 存在 :focus-visible 样式，且聚焦元素的 outline/box-shadow 可见
 *   - 文本颜色对比：普通文本 ≥4.5、大字 ≥3.0（跳过背景图/渐变/透明度非 1 的项并列入 unmeasured）
 *
 * 明确未测（人工）：
 *   键盘全流程、读屏语义/顺序、动态内容播报、200% 缩放与 reflow、减少动效、
 *   文本覆盖图片/渐变时的对比、真实用户测试。
 *
 * 退出码：0 无违规 / 1 有违规 / 2 环境不可用（Chrome 起不来）。
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const base = arg("base", "http://127.0.0.1:5180").replace(/\/$/, "");
const cookie = arg("cookie", "");
const pages = arg(
  "pages",
  "/queue,/cases/case-smoke,/reports/report-smoke",
).split(",").map((s) => s.trim()).filter(Boolean);
const outFile = arg("out", "");
const debugPort = Number(arg("debug-port", "9335"));
const chrome =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "web_a11y_chrome_"));
const child = spawn(
  chrome,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitVersion() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      if (r.ok) return;
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error("Chrome remote debugging 未就绪");
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const pending = new Map();
    let id = 1;
    ws.onopen = () =>
      resolve({
        send(method, params = {}) {
          const n = id++;
          return new Promise((res, rej) => {
            pending.set(n, { res, rej });
            ws.send(JSON.stringify({ id: n, method, params }));
          });
        },
        close: () => ws.close(),
      });
    ws.onerror = reject;
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (!msg.id || !pending.has(msg.id)) return;
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) rej(new Error(JSON.stringify(msg.error)));
      else res(msg.result);
    };
  });
}

const AUDIT = String.raw`
(() => {
  const checks = [];
  const violations = [];
  const unmeasured = [];
  const v = (kind, detail) => violations.push({ kind, ...detail });

  checks.push("html-lang");
  const lang = document.documentElement.getAttribute("lang");
  if (!lang || !lang.trim()) v("html-lang", { detail: "html[lang] 为空" });

  checks.push("h1-unique");
  const h1 = [...document.querySelectorAll("h1")];
  if (h1.length !== 1) v("h1-unique", { count: h1.length });

  checks.push("img-alt");
  const imgs = [...document.querySelectorAll("img")];
  for (const img of imgs) {
    const alt = img.getAttribute("alt");
    if (alt === null || !alt.trim()) {
      v("img-alt", { src: img.getAttribute("src"), detail: "img 缺非空 alt" });
    }
  }

  checks.push("control-label");
  const controls = [...document.querySelectorAll("input,select,textarea")];
  for (const el of controls) {
    const id = el.getAttribute("id");
    const labelled =
      el.getAttribute("aria-label") ||
      el.getAttribute("aria-labelledby") ||
      el.closest("label") ||
      (id && document.querySelector('label[for="' + CSS.escape(id) + '"]'));
    if (!labelled) v("control-label", { name: el.getAttribute("name") || el.tagName });
  }
  checks.push("button-name");
  const buttons = [...document.querySelectorAll("button")];
  for (const b of buttons) {
    const name =
      b.getAttribute("aria-label") ||
      (b.getAttribute("aria-labelledby") &&
        document.getElementById(b.getAttribute("aria-labelledby"))?.textContent) ||
      b.textContent;
    if (!name || !String(name).trim()) v("button-name", { detail: "button 无可访问名称" });
  }

  checks.push("skip-link");
  const skip = document.querySelector('a[href="#main"], a.skip-link');
  if (!skip) v("skip-link", { detail: "缺 skip-link" });
  else if (skip.getAttribute("href") !== "#main" || !document.querySelector("#main")) {
    v("skip-link", { detail: "skip-link 未指向存在的 #main" });
  }

  checks.push("focus-visible-style");
  let hasFocusRule = false;
  try {
    for (const sheet of document.styleSheets) {
      for (const rule of sheet.cssRules || []) {
        if (rule.selectorText && rule.selectorText.includes(":focus-visible")) {
          hasFocusRule = true;
        }
      }
    }
  } catch {
    unmeasured.push("跨域样式表无法读取 :focus-visible 规则");
  }
  if (!hasFocusRule) v("focus-visible-style", { detail: "没有 :focus-visible 规则" });

  checks.push("focus-visible-element");
  const focusables = [
    ...document.querySelectorAll(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
    ),
  ];
  if (focusables.length) {
    const el = focusables[0];
    el.focus();
    const cs = getComputedStyle(el);
    const visible =
      (cs.outlineStyle && cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0) ||
      (cs.boxShadow && cs.boxShadow !== "none");
    if (!visible) v("focus-visible-element", {
      tag: el.tagName,
      cls: el.className,
      outlineStyle: cs.outlineStyle,
      outlineWidth: cs.outlineWidth,
      boxShadow: cs.boxShadow,
      focused: document.activeElement === el,
      matchesFocus: el.matches(":focus"),
      href: el.getAttribute ? el.getAttribute("href") : null,
    });
  } else {
    unmeasured.push("页面没有可聚焦元素");
  }

  checks.push("color-contrast");
  function parseColor(s) {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(",").map((x) => parseFloat(x.trim()));
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function blend(fg, bg) {
    const a = fg[3];
    return [
      fg[0] * a + bg[0] * (1 - a),
      fg[1] * a + bg[1] * (1 - a),
      fg[2] * a + bg[2] * (1 - a),
      1,
    ];
  }
  function lum(c) {
    const f = (x) => {
      const y = x / 255;
      return y <= 0.03928 ? y / 12.92 : Math.pow((y + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  function ratio(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function bgOf(el) {
    let node = el;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return { image: true };
      const c = parseColor(cs.backgroundColor);
      if (c && c[3] > 0) return { color: c };
      node = node.parentElement;
    }
    return { color: [255, 255, 255, 1] };
  }
  let contrastChecked = 0;
  const textEls = [...document.querySelectorAll(
    "h1,h2,h3,p,td,th,a,li,span,code,strong,button,label,div",
  )].filter((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    if (parseFloat(cs.opacity) !== 1) return false;
    const ownText = [...el.childNodes].some(
      (n) => n.nodeType === 3 && n.textContent.trim().length > 0,
    );
    return ownText;
  });
  for (const el of textEls) {
    const cs = getComputedStyle(el);
    const fg0 = parseColor(cs.color);
    if (!fg0) continue;
    const bg = bgOf(el);
    if (bg.image) {
      unmeasured.push("文本背景为图片/渐变：" + (el.textContent || "").trim().slice(0, 30));
      continue;
    }
    const fg = fg0[3] < 1 ? blend(fg0, bg.color) : fg0;
    const size = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3.0 : 4.5;
    const r = ratio(fg, bg.color);
    contrastChecked += 1;
    if (r < need) {
      v("color-contrast", {
        text: (el.textContent || "").trim().slice(0, 40),
        tag: el.tagName,
        cls: String(el.className || ""),
        ratio: Math.round(r * 100) / 100,
        need,
      });
    }
  }
  checks.push("color-contrast-elements:" + contrastChecked);

  unmeasured.push("键盘全流程、读屏语义/顺序、动态播报、200% 缩放/reflow、减少动效、文本覆盖图片对比、真实用户测试");

  return {
    checks: checks.length,
    checkNames: checks,
    violations,
    unmeasured,
    counts: {
      h1: h1.length,
      imgs: imgs.length,
      controls: controls.length,
      buttons: buttons.length,
      focusables: focusables.length,
      contrastChecked,
    },
  };
})()
`;

async function main() {
  await waitVersion();
  const origin = new URL(base).origin;
  const tResp = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  );
  const target = await tResp.json();
  const cdp = await connect(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");
  // headless 下页面默认没有窗口焦点，:focus / :focus-visible 不会匹配；
  // 打开焦点模拟后，程序化 focus 才能得到真实焦点样式。
  try {
    await cdp.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  } catch {
    /* 老版本 Chrome 无此方法时，后续检查可能落 unmeasured */
  }
  if (cookie) {
    await cdp.send("Network.setCookie", {
      name: "session",
      value: cookie,
      url: origin,
      path: "/",
    });
  }

  const results = [];
  let totalViolations = 0;
  let totalChecks = 0;
  for (const p of pages) {
    await cdp.send("Page.navigate", { url: base + p });
    await sleep(1200);
    const r = await cdp.send("Runtime.evaluate", {
      expression: AUDIT,
      returnByValue: true,
    });
    const value = r?.result?.value ?? { violations: [{ kind: "audit-failed" }], checks: 0 };
    totalViolations += (value.violations || []).length;
    totalChecks += value.checks || 0;
    results.push({ page: p, ...value });
  }
  cdp.close();

  const out = {
    ok: totalViolations === 0,
    pages: results,
    totalViolations,
    totalChecks,
    unmeasured: [
      "键盘全流程（人工）",
      "读屏语义与焦点顺序（人工）",
      "动态内容播报（人工）",
      "200% 缩放 / reflow（人工）",
      "减少动效 prefers-reduced-motion（人工）",
      "文本覆盖图片/渐变时的对比（自动检查跳过）",
      "真实用户测试（人工）",
    ],
  };
  if (outFile) fs.writeFileSync(outFile, JSON.stringify(out, null, 2) + "\n");
  console.log(JSON.stringify(out, null, 2));
  return totalViolations === 0 ? 0 : 1;
}

let rc = 2;
try {
  rc = await main();
} catch (e) {
  console.error(`无障碍检查失败：${e instanceof Error ? e.message : e}`);
  rc = 1;
} finally {
  try {
    child.kill("SIGKILL");
  } catch {
    /* ignore */
  }
  try {
    fs.rmSync(profile, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
}
process.exit(rc);
