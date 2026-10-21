#!/usr/bin/env node
/**
 * check_visual.mjs —— 视觉基线（结构与计算样式快照，**不是截图比对**）
 *
 * 方案 §6.12：视觉检查的唯一实现，不把截图比较塞进 `check_pages.mjs`。
 * 方案 §1190：结构与计算样式快照；截图放 gitignored 运行目录，**不进公开仓**。
 *
 * 基线存在 `web/design-baseline.json` 的 `visual` 段（与 DT-3 的 `tokens` 段同一文件，
 * 因为批次 0 的新增文件清单里只有一个 design-baseline.json）。
 *
 * 输出契约：`{ ok, reds[], untested[], waived[], details[] }`
 * 退出码：0 无漂移 / 1 有漂移 / 2 未测（Chrome 起不来 / 没有基线 / 没有服务器）。
 *
 * 用法：
 *   node web/scripts/check_visual.mjs --base http://127.0.0.1:5180 --check
 *   node web/scripts/check_visual.mjs --base ... --update     # 显式重写基线
 *   node web/scripts/check_visual.mjs --selftest              # 纯函数反向对照
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");
const BASELINE = path.join(WEB, "design-baseline.json");

function flag(n) { return process.argv.includes(`--${n}`); }
function arg(n, f) {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
}
const JSON_OUT = flag("json");
const base = arg("base", "http://127.0.0.1:5180").replace(/\/$/, "");
const pages = arg("pages", "/queue,/taxonomy").split(",").map((s) => s.trim()).filter(Boolean);
const shots = arg("shots", "");
const chrome = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

// ── 纯函数：快照对比（反向对照直接喂它）───────────────────────────────────
function diffSnapshot(baseline, current) {
  const reds = [];
  const b = baseline?.pages || {};
  for (const [page, snap] of Object.entries(current?.pages || {})) {
    const old = b[page];
    if (!old) { reds.push(`${page}: 基线里没有这一页（新增页面需要 --update 并说明）`); continue; }
    if (JSON.stringify(old.structure) !== JSON.stringify(snap.structure)) {
      reds.push(`${page}: 结构变了`);
    }
    const oldStyles = new Map((old.styles || []).map((s) => [s.sel, s]));
    for (const s of snap.styles || []) {
      const o = oldStyles.get(s.sel);
      if (!o) { reds.push(`${page}: 新增选择器 ${s.sel}`); continue; }
      for (const k of ["color", "backgroundColor", "fontSize", "fontWeight", "borderRadius"]) {
        if (o[k] !== s[k]) reds.push(`${page}: ${s.sel}.${k} ${o[k]} → ${s[k]}`);
      }
    }
  }
  for (const page of Object.keys(b)) {
    if (!(page in (current?.pages || {}))) reds.push(`${page}: 基线里的页面这次没采到`);
  }
  return reds;
}

const SNAPSHOT = `(() => {
  const sels = ["h1", ".badge", ".btn", ".queue__row", ".queue__filter", ".shell__header", "main"];
  const styles = [];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const cs = getComputedStyle(el);
    styles.push({ sel, color: cs.color, backgroundColor: cs.backgroundColor,
      fontSize: cs.fontSize, fontWeight: cs.fontWeight, borderRadius: cs.borderRadius });
  }
  const count = (s) => document.querySelectorAll(s).length;
  return {
    structure: {
      h1: (document.querySelector("h1")?.textContent || "").trim(),
      badges: count("[data-status-badge], .badge"),
      rows: count(".queue__row"),
      buttons: count("button"),
      links: count("a[href]"),
      main: Boolean(document.querySelector("main")),
    },
    styles,
  };
})()`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const pending = new Map();
    let id = 1;
    ws.onopen = () => resolve({
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

function emit(reds, untested, details) {
  const payload = { ok: reds.length === 0 && untested.length === 0, reds, untested, waived: [], details };
  if (JSON_OUT) console.log(JSON.stringify(payload, null, 2));
  else {
    for (const d of details) console.log(`  · ${d}`);
    for (const u of untested) console.log(`  ⚠ 未测 ${u}`);
    for (const r of reds) console.log(`  ✗ ${r}`);
    console.log(payload.ok ? "✅ 视觉基线无漂移" : reds.length ? "❌ 视觉基线漂移" : "⚠ 未测");
  }
  if (reds.length) return 1;
  if (untested.length) return 2;
  return 0;
}

async function capture() {
  if (!fs.existsSync(chrome)) return { untested: [`找不到 Chrome（${chrome}）`] };
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "web_visual_"));
  const port = Number(arg("debug-port", "9339"));
  const child = spawn(chrome, [
    "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: "ignore" });
  try {
    let ready = false;
    for (let i = 0; i < 60 && !ready; i++) {
      try { ready = (await fetch(`http://127.0.0.1:${port}/json/version`)).ok; } catch { /* retry */ }
      if (!ready) await sleep(200);
    }
    if (!ready) return { untested: ["Chrome remote debugging 未就绪"] };
    const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
    const cdp = await connect(t.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    if (shots) fs.mkdirSync(shots, { recursive: true });
    const out = { generated_at: new Date().toISOString(), pages: {} };
    for (const p of pages) {
      await cdp.send("Page.navigate", { url: base + p });
      await sleep(1200);
      const r = await cdp.send("Runtime.evaluate", { expression: SNAPSHOT, returnByValue: true });
      out.pages[p] = r?.result?.value ?? { structure: {}, styles: [] };
      if (shots) {
        const png = await cdp.send("Page.captureScreenshot", { format: "png" });
        // ★ 截图只进运行目录（gitignored），**不进公开仓**（方案 §1291）
        fs.writeFileSync(path.join(shots, `${p.replace(/[^a-z0-9]+/gi, "_")}.png`),
          Buffer.from(png.data, "base64"));
      }
    }
    cdp.close();
    return { snapshot: out };
  } finally {
    try { child.kill("SIGKILL"); } catch { /* ignore */ }
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

async function main() {
  const doc = JSON.parse(fs.readFileSync(BASELINE, "utf8"));
  if (flag("update")) {
    const r = await capture();
    if (r.untested) return emit([], r.untested, []);
    doc.visual = r.snapshot;
    fs.writeFileSync(BASELINE, JSON.stringify(doc, null, 1) + "\n", "utf8");
    return emit([], [], [`基线已更新：${Object.keys(r.snapshot.pages).join(", ")}`]);
  }
  if (!doc.visual) {
    return emit([], ["design-baseline.json 没有 visual 段 —— 先跑 --update（需要服务器）"], []);
  }
  const r = await capture();
  if (r.untested) return emit([], r.untested, []);
  const reds = diffSnapshot(doc.visual, r.snapshot);
  return emit(reds, [], [`采样 ${Object.keys(r.snapshot.pages).length} 页`]);
}

function selftest() {
  const baseSnap = {
    pages: {
      "/queue": {
        structure: { h1: "复核队列", badges: 3, rows: 21, buttons: 2, links: 21, main: true },
        styles: [{ sel: "h1", color: "rgb(1, 2, 3)", backgroundColor: "rgba(0, 0, 0, 0)",
          fontSize: "24px", fontWeight: "600", borderRadius: "0px" }],
      },
    },
  };
  const same = JSON.parse(JSON.stringify(baseSnap));
  const changed = JSON.parse(JSON.stringify(baseSnap));
  changed.pages["/queue"].styles[0].color = "rgb(9, 9, 9)";
  const missing = { pages: {} };
  const cases = [
    ["VS-C1 快照相同 → 无漂移", diffSnapshot(baseSnap, same).length === 0, ""],
    ["VS-C2 计算样式变一个值 → 必须红", diffSnapshot(baseSnap, changed).length === 1, ""],
    ["VS-C3 页面消失 → 必须红", diffSnapshot(baseSnap, missing).length >= 1, ""],
  ];
  let ok = true;
  for (const [label, pass, detail] of cases) {
    console.log(`${pass ? "✓" : "✗"} ${label}${pass ? "" : `  ← ${detail}`}`);
    if (!pass) ok = false;
  }
  return ok ? 0 : 1;
}

if (flag("selftest")) process.exit(selftest());
main().then((rc) => process.exit(rc)).catch((e) => {
  console.error(`视觉检查失败：${e instanceof Error ? e.message : e}`);
  process.exit(2);
});
