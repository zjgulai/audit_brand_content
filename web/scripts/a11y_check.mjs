#!/usr/bin/env node
/**
 * a11y_check.mjs —— 可自动化无障碍与双视口 Reflow 门（WCAG 2.2 AA 基线 + TS-14 / #116，Chrome CDP）
 *
 * 自动检查（本脚本在 `desktop-1280x720` 与 `reflow-320` 两个视口下逐页真跑）：
 *   - html[lang] 非空
 *   - 每页恰好一个 h1
 *   - img 有非空 alt
 *   - input/select/textarea 有 label（label/for、包裹 label、aria-label/labelledby）
 *   - 按钮有可访问名称
 *   - skip-link 存在且指向 #main
 *   - 存在 :focus-visible 样式，且聚焦元素的 outline/box-shadow 可见
 *   - 非文本控件边框对比度 ≥ 3.0
 *   - 文本颜色对比：普通文本 ≥ 4.5、大字 ≥ 3.0
 *   - 视口无横向溢出（scrollWidth <= innerWidth）
 *   - 关键交互控件无横向裁切（control-clipped）与无几何重叠（control-overlap）
 *
 * ★ 2026-10-23 实测踩坑记录（必须留存，防后人改回）：
 *   桌面浏览器 400% zoom 的真实等价是 `Emulation.setDeviceMetricsOverride({ width: 320, height: 800, deviceScaleFactor: 1, mobile: false })`，
 *   **绝对不能传 `mobile: true`（或 `mobile: w < 600`）**！
 *   原因：当 `mobile: true` 且页面无 `<meta name="viewport">` 时，Chrome 移动端模拟会把默认 layout viewport
 *   放大到 980px（`window.innerWidth === 980`），导致 `@media (max-width: 400px)` 根本不触发、`500px < 980px`
 *   也测不出溢出 —— 坏样本静默全绿，不是因为页面好，是因为 320px 视口根本没生效！
 *
 * 三种运行方式：
 *   1. 在线联调模式（`dev-up.sh` 调用）：`--base http://127.0.0.1:PORT --pages ...`
 *   2. 独立反向对照（`--controls`，~2.7s）：跑 C1–C5 五组正反样本
 *   3. 独立沙箱全验模式（`--standalone`，~3.8s，供 `verifier_map.json` #116 直接调用）：
 *      先跑 C1–C5 反向对照，再直接加载真实 `web/src/styles/tokens.css` + `web/src/styles.css`
 *      在 `1280×720` 与 `320×800 (400% zoom)` 下对工作台核心 DOM 模板执行完整 13 项 AA + 几何 + Reflow 审计，
 *      并注入真实 CSS 下的溢出/窄屏对比度破坏探针验证必红。
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
function flag(name) {
  return process.argv.includes(`--${name}`);
}

const base = arg("base", "http://127.0.0.1:5180").replace(/\/$/, "");
const cookie = arg("cookie", "");
const pages = arg(
  "pages",
  "/queue,/cases/case-smoke,/reports/report-smoke",
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const outFile = arg("out", "");
const debugPort = Number(arg("debug-port", "9335"));
const enableDevIdentity = arg("enable-dev-identity", "0") === "1";
const runControlsOnly = flag("controls");
const runStandalone = flag("standalone");
const mode = arg("mode", "auto");
if (mode !== "auto" && mode !== "full") {
  console.error(`未知 --mode：${mode}（只支持 auto | full）`);
  process.exit(2);
}
const WEB = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const waiversPath = path.resolve(WEB, arg("waivers", "a11y-waivers-v1.json"));
const today = new Date().toISOString().slice(0, 10);
let waiverDoc = { waivers: [] };
try {
  waiverDoc = JSON.parse(fs.readFileSync(waiversPath, "utf8"));
} catch (e) {
  if (mode === "full") {
    console.error(`⚠ 未测：waiver 文件读不出（${waiversPath}）：${e.message}`);
    process.exit(2);
  }
}
const expiredWaivers = (waiverDoc.waivers || []).filter(
  (w) => w.expires && w.expires < today,
);
const liveWaivers = (waiverDoc.waivers || []).filter(
  (w) => !w.expires || w.expires >= today,
);
const waiverSelectors = liveWaivers
  .filter((w) => w.rule === "non-text-contrast")
  .map((w) => w.selector)
  .filter(Boolean);
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

const AUDIT_FN = String.raw`
((waivers) => {
  const checks = [];
  const violations = [];
  const waived = [];
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

  checks.push("non-text-contrast");
  const ntc = [...document.querySelectorAll("button,input,select,textarea,.queue__filter")]
    .filter((el) => !el.disabled);
  let ntcChecked = 0;
  for (const el of ntc) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    if (parseFloat(cs.borderTopWidth) === 0) continue;
    const bc = parseColor(cs.borderTopColor);
    if (!bc || bc[3] === 0) continue;
    const bg = bgOf(el);
    if (bg.image) { unmeasured.push("控件边框背景为图片/渐变：" + el.tagName); continue; }
    const r = ratio(bc, bg.color);
    ntcChecked++;
    if (r < 3) {
      const isWaived = (waivers || []).some((sel) => {
        try { return el.matches(sel); } catch { return false; }
      });
      const rec = { kind: "non-text-contrast", tag: el.tagName,
        cls: String(el.className || ""), ratio: Math.round(r * 100) / 100, need: 3 };
      if (isWaived) waived.push(rec); else v("non-text-contrast", rec);
    }
  }
  checks.push("non-text-contrast-elements:" + ntcChecked);

  checks.push("color-contrast");
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

  // ── #116 (TS-14) 关键控件几何可达性：无横向裁切 + 无互相重叠 ─────────────
  checks.push("control-geometry");
  const interactive = [...document.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a.btn, .queue__filter',
  )].filter((el) => {
    if (el.classList && el.classList.contains("skip-link")) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  });

  const vw = Math.min(window.innerWidth || 9999, document.documentElement.clientWidth || 9999);
  const boxes = [];
  for (const el of interactive) {
    const rect = el.getBoundingClientRect();
    const inScrollTable = Boolean(el.closest(".cases-table-wrap"));
    if (!inScrollTable && (rect.left < -1 || rect.right > vw + 1)) {
      v("control-clipped", {
        tag: el.tagName,
        text: (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 24),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        viewportWidth: vw,
      });
    }
    boxes.push({ el, rect });
  }

  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ix = Math.max(0, Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left));
      const iy = Math.max(0, Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top));
      if (ix > 2 && iy > 2) {
        v("control-overlap", {
          first: (a.el.textContent || a.el.tagName).trim().slice(0, 20),
          second: (b.el.textContent || b.el.tagName).trim().slice(0, 20),
          overlapW: Math.round(ix),
          overlapH: Math.round(iy),
        });
      }
    }
  }

  unmeasured.push("键盘全流程、读屏语义/顺序、动态播报、减少动效、文本覆盖图片对比、真实用户测试");

  return {
    checks: checks.length,
    waived,
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
      interactiveChecked: interactive.length,
    },
  };
})
`;

async function runControls(cdp) {
  const HARNESS_HTML = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root { --ring: 346.5 41.3% 29.4%; }
    body { margin: 0; font-family: sans-serif; background: #ffffff; color: #11161d; }
    a:focus-visible, button:focus-visible, a:focus, button:focus { outline: 3px solid hsl(var(--ring)); outline-offset: 2px; }
    .skip-link { position: absolute; left: 0; top: -4rem; }
    .btn { padding: 6px 12px; border: 1px solid #565f69; background: #ffffff; color: #11161d; }
    @media (max-width: 400px) {
      .narrow-low-contrast { color: #e8ecef !important; background: #ffffff !important; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main">跳到主内容</a>
  <main id="main">
    <h1>测试页</h1>
    <p id="probe-text">正常对比度正文</p>
    <button type="button" class="btn" id="btn-1">按钮一</button>
    <button type="button" class="btn" id="btn-2">按钮二</button>
  </main>
</body>
</html>`;

  const evalAudit = async (w, h, setupExpr = "") => {
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: w,
      height: h,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.navigate", {
      url: "data:text/html;charset=utf-8," + encodeURIComponent(HARNESS_HTML),
    });
    await sleep(200);
    if (setupExpr) {
      await cdp.send("Runtime.evaluate", {
        expression: setupExpr,
        returnByValue: true,
      });
    }
    const r = await cdp.send("Runtime.evaluate", {
      expression: `(() => {
        const audit = (${AUDIT_FN})([]);
        const sw = document.documentElement.scrollWidth;
        const iw = window.innerWidth;
        if (sw > iw) {
          audit.violations.push({ kind: "reflow-overflow", scrollWidth: sw, innerWidth: iw });
        }
        return audit;
      })()`,
      returnByValue: true,
    });
    return r?.result?.value ?? { violations: [{ kind: "eval-failed" }] };
  };

  const cases = [];

  const c1Desktop = await evalAudit(1280, 720);
  const c1Reflow = await evalAudit(320, 800);
  cases.push([
    "C1 正样本：合规页面在 1280×720 与 320px (400% zoom) 下均 0 违规",
    c1Desktop.violations.length === 0 && c1Reflow.violations.length === 0,
    `desktop=${c1Desktop.violations.length} reflow=${c1Reflow.violations.length}`,
  ]);

  const c2Reflow = await evalAudit(
    320,
    800,
    `(() => {
      const d = document.createElement('div');
      d.style.width = '500px';
      d.textContent = '横向溢出块';
      document.getElementById('main').appendChild(d);
    })()`,
  );
  cases.push([
    "C2 坏样本：注入 width:500px 元素 → reflow-320 必须报 reflow-overflow",
    c2Reflow.violations.some((v) => v.kind === "reflow-overflow"),
    JSON.stringify(c2Reflow.violations),
  ]);

  const c3Reflow = await evalAudit(
    320,
    800,
    `(() => {
      const b1 = document.getElementById('btn-1');
      const b2 = document.getElementById('btn-2');
      b1.style.position = 'absolute'; b1.style.left = '20px'; b1.style.top = '80px';
      b2.style.position = 'absolute'; b2.style.left = '25px'; b2.style.top = '82px';
    })()`,
  );
  cases.push([
    "C3 坏样本：两个按钮几何重叠 → 必须报 control-overlap",
    c3Reflow.violations.some((v) => v.kind === "control-overlap"),
    JSON.stringify(c3Reflow.violations),
  ]);

  const c4Reflow = await evalAudit(
    320,
    800,
    `(() => {
      const b1 = document.getElementById('btn-1');
      b1.style.position = 'absolute'; b1.style.left = '260px'; b1.style.width = '120px';
    })()`,
  );
  cases.push([
    "C4 坏样本：按钮超出视口被裁切 → 必须报 control-clipped",
    c4Reflow.violations.some((v) => v.kind === "control-clipped"),
    JSON.stringify(c4Reflow.violations),
  ]);

  const setupMediaProbe = `document.getElementById('probe-text').classList.add('narrow-low-contrast');`;
  const c5Desktop = await evalAudit(1280, 720, setupMediaProbe);
  const c5Reflow = await evalAudit(320, 800, setupMediaProbe);
  cases.push([
    "C5 视口特异性对照：仅窄屏降对比度的文本 → 1280×720 绿、320px 红（证明 320px 真跑了 AA）",
    c5Desktop.violations.length === 0 &&
      c5Reflow.violations.some((v) => v.kind === "color-contrast"),
    `desktop=${JSON.stringify(c5Desktop.violations)} reflow=${JSON.stringify(c5Reflow.violations)}`,
  ]);

  await cdp.send("Emulation.clearDeviceMetricsOverride").catch(() => {});
  return cases;
}

/**
 * 独立沙箱全验模式（`--standalone`）：
 * 直接读取真实 `web/src/styles/tokens.css` 与 `web/src/styles.css`，
 * 挂载工作台三大核心布局（复核队列 Master-Detail、案件双栏原件+证据链+复核动作、分类规范与签发核验台），
 * 在 1280×720 与 320px (400% zoom) 下执行完整 13 项 AA + 几何 + Reflow 检查，并附真实 CSS 下的破坏对照。
 */
async function runStandaloneSuite(cdp) {
  const tokensCss = fs.readFileSync(
    path.join(WEB, "src/styles/tokens.css"),
    "utf8",
  );
  const stylesCss = fs
    .readFileSync(path.join(WEB, "src/styles.css"), "utf8")
    .replace(/@import\s+["'][^"']+["'];?/g, "");
  const fullCss = `${tokensCss}\n${stylesCss}`;

  const TEMPLATES = [
    {
      name: "queue-master-detail",
      title: "复核队列",
      body: `
        <div class="queue">
          <div class="queue__list">
            <div class="sample-banner" data-sample-banner="">
              <span><span class="badge badge--sample">样例数据</span> 含 10 条确定性夹具</span>
              <button type="button" class="btn">清空样例</button>
            </div>
            <div class="queue__filters" role="group" aria-label="队列筛选">
              <button type="button" class="queue__filter" aria-pressed="true">全部待办（10）</button>
              <button type="button" class="queue__filter" aria-pressed="false">REVIEW（8）</button>
              <button type="button" class="queue__filter" aria-pressed="false">待自决（2）</button>
            </div>
            <div class="queue__item-wrap">
              <a href="#case-1" class="queue__row" aria-current="true">
                <span class="queue__row-top">
                  <span class="queue__row-id font-data">case-c4964393</span>
                  <span class="badge badge--review">REVIEW</span>
                </span>
                <span class="queue__row-excerpt">【Momcozy 北美上市送审素材】适用渠道与人群：北美职场妈妈</span>
                <span class="queue__row-meta">
                  <span class="font-data">DP3</span>
                  <span>wearable</span>
                  <span class="font-data">u_dp3</span>
                </span>
              </a>
            </div>
          </div>
          <div class="queue__detail-pane">
            <div class="queue__detail-header">
              <h1>复核队列</h1>
              <span class="hint">按 J / K 切换待办案件</span>
            </div>
          </div>
        </div>`,
    },
    {
      name: "case-dual-workbench",
      title: "案件详情",
      body: `
        <section class="case case--dual">
          <div class="case__top-bar">
            <div class="case__head">
              <h1>案件详情</h1>
              <span class="badge badge--review">REVIEW</span>
              <span class="font-data">case-c4964393</span>
            </div>
          </div>
          <div class="case__workspace">
            <aside class="unit-pane" aria-label="原文内容">
              <div class="unit-pane__head">
                <strong class="unit-pane__title">原文内容</strong>
                <div class="unit-pane__tabs" role="tablist">
                  <button type="button" class="btn">归一化正文</button>
                  <button type="button" class="btn">结构化字段</button>
                </div>
              </div>
              <div class="unit-pane__body">
                <div class="unit-text">临床级负压技术，能够<mark class="unit-mark unit-mark--active">治疗堵奶<sup class="unit-mark__tag font-data">[1:H01]</sup></mark>。</div>
              </div>
            </aside>
            <div class="case__inspector">
              <h2>判定与覆盖证明</h2>
              <dl class="facts">
                <dt>对外标签</dt>
                <dd><span class="badge badge--review">REVIEW</span></dd>
                <dt>覆盖状态</dt>
                <dd><span class="badge badge--partial">partial</span> <strong>仅已覆盖部分可判</strong></dd>
                <dt>依据核验</dt>
                <dd><span class="badge badge--untested">未测</span></dd>
                <!-- ★ 2026-10-27（ADR-0021 · a11y）：补上三个**从未被测过**的徽标。
                    改前模板里只有 review / partial / untested / sample 四种，
                    而 styles.css 里有 10 种。于是 badge--pass（实测 4.21）、
                    badge--pending（4.25）、badge--block 这些
                    **一直不达标却从来不会红** —— 一个不覆盖它的检查器
                    比没有更糟：它让人以为「徽标对比度已经查过了」。
                    实测：修 token 前 pass=4.21 / pending=4.25 / review=4.25，
                    三个都低于 4.5，而闸门只报了 review 一个。 -->
                <dt>通过态</dt>
                <dd><span class="badge badge--pass">PASS</span></dd>
                <dt>待定态</dt>
                <dd><span class="badge badge--pending">待自决</span></dd>
                <dt>拦截态</dt>
                <dd><span class="badge badge--block">BLOCK</span></dd>
              </dl>
              <div class="actions">
                <h2>复核动作</h2>
                <label for="review-note">复核理由 / 备注</label>
                <textarea id="review-note" placeholder="输入复核意见"></textarea>
                <div class="actions__row">
                  <button type="button" class="btn">认领</button>
                  <button type="button" class="btn">存草稿</button>
                  <button type="button" class="btn btn--primary" data-risk-action="submit">提交复核意见</button>
                </div>
              </div>
            </div>
          </div>
        </section>`,
    },
    {
      name: "taxonomy-and-release",
      title: "分类规范与签发核验",
      body: `
        <section class="taxonomy-page">
          <h1>分类规范</h1>
          <div class="taxonomy-grid">
            <article class="taxonomy-card">
              <h3><code>CHAN</code> · 渠道控制</h3>
              <dl class="taxonomy-fields">
                <dt>一句话定义</dt>
                <dd>审查平台与地区准入边界</dd>
              </dl>
            </article>
          </div>
          <form class="taxonomy-lookup">
            <label for="rule-lookup">rule_id</label>
            <input id="rule-lookup" name="rule_id" placeholder="例如 T1.1.medical-cure" />
            <button type="submit" class="btn">查找</button>
          </form>
        </section>`,
    },
    {
      name: "login-page",
      title: "登录页",
      body: `
        <section class="case">
          <h1>登录</h1>
          <div class="browser-support" data-browser-support="">
            <span class="hint">正式支持范围：仅桌面 Google Chrome 最近两个主要版本（Chrome 155 / 156，基准实测于 2026-10-23）</span>
          </div>
          <p>使用飞书账号登录后即可进入复核队列。</p>
          <p><a class="btn" href="#auth-login">使用飞书登录</a></p>
        </section>`,
    },
  ];

  const buildShellHtml = (innerBody) => `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>${fullCss}</style>
</head>
<body>
  <div class="shell">
    <a class="skip-link" href="#main">跳到主内容</a>
    <!-- ★ 2026-10-27（ADR-0021 · a11y）：模板改成**真实的** AppShell 结构。
         改前是「header 里塞一个 开发身份：<select>」——而真实页面里
         那个 select 在**侧边栏底部**（.shell__sidebar-foot > .shell__dev-id），
         header 里放的是品线 pill 与通知徽标。

         代价是实测出来的：reflow-320 下报「DP3 审核员 压住 认领 / 存草稿」
         （overlap 50×38 / 35×38）。把那个 select 拿掉，13/13 全过 ——
         说明**重叠是模板自己造出来的**，不是真实页面的缺陷。
         一份不忠实于真实结构的模板，报出的问题既不能直接修（真实页面没有那个元素），
         也不能忽略（它会让闸门一直红）—— 这正是「会误报的检查器比没有更糟」。 -->
    <aside class="shell__sidebar" aria-label="工作台导航">
      <div class="shell__brand-wrap">
        <span class="shell__brand">内容审核工作台</span>
        <span class="shell__brand-sub">内容审核工作台</span>
      </div>
      <nav class="shell__nav" aria-label="主导航">
        <div class="shell__nav-group">
          <p class="shell__nav-caption">审核流</p>
          <a class="shell__nav-item" href="#inbox"><span class="shell__nav-label">收件箱</span></a>
          <a class="shell__nav-item active" href="#queue"><span class="shell__nav-label">复核队列</span></a>
          <a class="shell__nav-item" href="#cases"><span class="shell__nav-label">案件总览</span></a>
          <a class="shell__nav-item" href="#release"><span class="shell__nav-label">签发台</span></a>
          <a class="shell__nav-item" href="#taxonomy"><span class="shell__nav-label">分类规范</span></a>
        </div>
      </nav>
      <div class="shell__sidebar-foot">
        <label class="shell__dev-id">
          <span class="shell__nav-caption">开发身份</span>
          <select aria-label="切换本地开发身份">
            <option>DP3 审核员</option>
            <option>DP4 签发人</option>
          </select>
        </label>
      </div>
    </aside>
    <div class="shell__body">
      <header class="shell__header">
        <div class="shell__heading">
          <div class="shell__heading-text">
            <p class="shell__title">复核队列</p>
            <p class="shell__subtitle">按紧迫度排序，J/K 切换</p>
          </div>
        </div>
        <div class="shell__right">
          <span class="shell__scope-pill font-data" title="授权产品线范围：pump / wearable">品线 2</span>
          <a class="shell__notif-badge" href="#inbox" aria-label="工作台通知：3 条未读">3</a>
        </div>
      </header>
      <main id="main" class="shell__main" tabindex="-1">${innerBody}</main>
      <footer class="shell__footer">判定由后端唯一产出，本页不重算；五标签一律止于「待放行」。</footer>
    </div>
  </div>
</body>
</html>`;

  const ctl = await runControls(cdp);
  const suiteResults = [...ctl];

  for (const tpl of TEMPLATES) {
    const html = buildShellHtml(tpl.body);
    for (const [w, h, vpLabel] of [
      [1280, 720, "desktop-1280x720"],
      [320, 800, "reflow-320"],
    ]) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: w,
        height: h,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await cdp.send("Page.navigate", {
        url: "data:text/html;charset=utf-8," + encodeURIComponent(html),
      });
      await sleep(200);
      const r = await cdp.send("Runtime.evaluate", {
        expression: `(() => {
          const audit = (${AUDIT_FN})([]);
          const sw = document.documentElement.scrollWidth;
          const iw = window.innerWidth;
          if (sw > iw) {
            audit.violations.push({ kind: "reflow-overflow", scrollWidth: sw, innerWidth: iw });
          }
          return { violations: audit.violations, checks: audit.checks, sw, iw };
        })()`,
        returnByValue: true,
      });
      const val = r?.result?.value ?? { violations: [{ kind: "eval-failed" }] };
      suiteResults.push([
        `S-${tpl.name}@${vpLabel}：真实 styles.css 渲染下 13 项 AA + 几何 + Reflow 零违规（sw=${val.sw}/${val.iw}）`,
        val.violations.length === 0,
        JSON.stringify(val.violations),
      ]);
    }
  }

  await cdp.send("Emulation.clearDeviceMetricsOverride").catch(() => {});
  return suiteResults;
}

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
  try {
    await cdp.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  } catch {
    /* ignore */
  }

  if (runControlsOnly || runStandalone) {
    const items = runStandalone
      ? await runStandaloneSuite(cdp)
      : await runControls(cdp);
    cdp.close();
    let failed = 0;
    console.log("==============================================================================");
    console.log(
      runStandalone
        ? "a11y_check.mjs --standalone · #116 (TS-14) 真实样式双视口 AA + Reflow + 反向对照"
        : "a11y_check.mjs --controls · #116 (TS-14) 视口与 400% Reflow 反向对照",
    );
    console.log("==============================================================================");
    for (const [label, ok, detail] of items) {
      console.log(`  ${ok ? "✅" : "❌"} ${label}${ok ? "" : " ← " + detail}`);
      if (!ok) failed += 1;
    }
    console.log("------------------------------------------------------------------------------");
    console.log(
      failed === 0
        ? `✅ ${items.length}/${items.length} 项全部通过`
        : `❌ ${failed}/${items.length} 项失败`,
    );
    return failed === 0 ? 0 : 1;
  }

  if (cookie) {
    await cdp.send("Network.setCookie", {
      name: "session",
      value: cookie,
      url: origin,
      path: "/",
    });
  }

  if (enableDevIdentity) {
    await cdp.send("Page.navigate", { url: `${base}/queue` });
    await sleep(300);
    await cdp.send("Runtime.evaluate", {
      expression: `(() => {
        const button=[...document.querySelectorAll('button')].find(
          x=>x.textContent?.trim()==='启用本地开发身份'
        );
        if(!button || button.disabled) return false;
        button.click(); return true;
      })()`,
      returnByValue: true,
    });
    await sleep(900);
  }

  const results = [];
  const reflow = [];
  const reflowWaived = [];
  let totalViolations = 0;
  let totalChecks = 0;

  for (const [w, h, label] of [
    [1280, 720, "desktop-1280x720"],
    [320, 800, "reflow-320"],
  ]) {
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: w,
      height: h,
      deviceScaleFactor: 1,
      mobile: false,
    });
    for (const p of pages) {
      await cdp.send("Page.navigate", { url: base + p });
      await sleep(950);
      const r = await cdp.send("Runtime.evaluate", {
        expression: `(() => {
          const audit = (${AUDIT_FN})(${JSON.stringify(waiverSelectors)});
          return {
            audit,
            sw: document.documentElement.scrollWidth,
            iw: window.innerWidth,
          };
        })()`,
        returnByValue: true,
      });
      const payload = r?.result?.value ?? {
        audit: { violations: [{ kind: "audit-failed" }], checks: 0, waived: [] },
        sw: 9999,
        iw: w,
      };
      const value = payload.audit;
      const good = Number(payload.sw) <= Number(payload.iw);

      if (!good) {
        const rec = {
          kind: "reflow-overflow",
          page: p,
          viewport: label,
          scrollWidth: payload.sw,
          innerWidth: payload.iw,
        };
        const wv = liveWaivers.find(
          (x) =>
            x.rule === "reflow-overflow" &&
            (!x.page || x.page === p) &&
            (!x.viewport || x.viewport === label),
        );
        if (wv) reflowWaived.push({ id: wv.id, ...rec });
        else value.violations.push(rec);
      }

      totalViolations += (value.violations || []).length;
      totalChecks += value.checks || 0;
      results.push({ page: p, viewport: label, ...value });
      reflow.push({
        viewport: label,
        page: p,
        ok: good && (value.violations || []).length === 0,
        scrollWidth: payload.sw,
        innerWidth: payload.iw,
        a11yViolations: (value.violations || []).length,
        checksRun: value.checks || 0,
      });
    }
  }
  await cdp.send("Emulation.clearDeviceMetricsOverride").catch(() => {});

  cdp.close();

  let manual = null;
  if (mode === "full") {
    const mf = path.resolve(WEB, "a11y-manual-v1.json");
    try {
      const doc = JSON.parse(fs.readFileSync(mf, "utf8"));
      const accept = new Set(doc.accept_status || ["signed", "done"]);
      const items = doc.items || [];
      const notSigned = items.filter(
        (it) =>
          !accept.has(String(it.status || "")) ||
          ["evidence", "owner", "date"].some((k) => !String(it[k] || "").trim()),
      );
      manual = {
        ok: notSigned.length === 0,
        total: items.length,
        untested: notSigned.map((it) => it.item),
      };
    } catch (e) {
      manual = { ok: false, total: 0, untested: [`台账读不出：${e.message}`] };
    }
  }

  const out = {
    ok: totalViolations === 0,
    pages: results,
    totalViolations,
    totalChecks,
    mode,
    waived: results.flatMap((r) => r.waived || []).concat(reflowWaived),
    waivedExpired: expiredWaivers.map((w) => w.id),
    reflow,
    manual,
    reds: totalViolations > 0 ? [`${totalViolations} 处违规`] : [],
    untested: mode === "full" && manual && !manual.ok ? manual.untested : [],
    unmeasured: [
      "键盘全流程（人工）",
      "读屏语义与焦点顺序（人工）",
      "动态内容播报（人工）",
      "减少动效 prefers-reduced-motion（人工）",
      "文本覆盖图片/渐变时的对比（自动检查跳过）",
      "真实用户测试（人工）",
    ],
  };
  if (outFile) fs.writeFileSync(outFile, JSON.stringify(out, null, 2) + "\n");
  console.log(JSON.stringify(out, null, 2));
  if (totalViolations > 0) return 1;
  if (expiredWaivers.length) {
    console.error(
      `❌ 有 ${expiredWaivers.length} 条 waiver 已过期：${expiredWaivers.map((w) => w.id).join(", ")}`,
    );
    return 1;
  }
  if (mode === "full" && manual && !manual.ok) {
    console.error(
      `⚠ 未测：人工项未签收 ${manual.untested.length} 条 —— full 模式退 2`,
    );
    return 2;
  }
  return 0;
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
