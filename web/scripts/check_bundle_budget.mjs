#!/usr/bin/env node
/**
 * check_bundle_budget.mjs —— 体积预算门（F11 的唯一实现）
 *
 * 方案 §6.9 / §6.12：Python 侧 F11 只 `subprocess` 调本脚本并解析 `ok/reds/untested`，
 * **不在 Python 里重写一套**。预算值来自 `web/budgets.json`。
 *
 * ## 为什么没有 manifest 就退 2
 *
 * `vite.config.ts` 在批次 0 **不动**（方案 L887），`build.manifest: true` 是 Stage 1 的事。
 * 没有 `dist/.vite/manifest.json` 时，initial / route 的切分只能靠猜 ——
 * 方案 §6.9 明写「没有 dist 或 manifest → 未测（2），不是绿，也不是红」。
 * 所以本脚本不拿 `dist/assets/*` 冒充 initial，缺 manifest 一律退 2。
 *
 * 输出契约（§6.12 / L857）：`{ ok, reds[], untested[], waived[], details[] }`
 * 退出码：0 全绿 / 1 有红 / 2 未测。
 *
 * 用法：
 *   node web/scripts/check_bundle_budget.mjs --dir dist
 *   node web/scripts/check_bundle_budget.mjs --json --dir dist
 *   node web/scripts/check_bundle_budget.mjs --selftest
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");

function flag(n) { return process.argv.includes(`--${n}`); }
function arg(n, f) {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
}
const JSON_OUT = flag("json");

// ── 纯函数：给定文件大小与 manifest，算预算结论 ──────────────────────────
//
// `sizeOf(relPath) -> bytes`（gzip 后）。抽成纯函数是为了反向对照能直接喂坏样本，
// 不必造一个真的超预算构建。
function evaluate(manifest, sizeOf, limits, entryKey = "index.html") {
  const reds = [], details = [];
  const entry = manifest[entryKey];
  if (!entry) return { reds: [`manifest 里没有入口 ${entryKey}`], details };

  const seen = new Set();
  let initial = 0;
  (function walk(key) {
    const m = manifest[key];
    if (!m || seen.has(key)) return;
    seen.add(key);
    initial += sizeOf(m.file);
    for (const c of m.css || []) initial += sizeOf(c);
    for (const k of m.imports || []) walk(k);
  })(entryKey);

  const all = new Set();
  const routeChunks = [];
  for (const [key, m] of Object.entries(manifest)) {
    if (!m || typeof m !== "object") continue;
    if (m.file) all.add(m.file);
    for (const c of m.css || []) all.add(c);
    for (const k of m.dynamicImports || []) {
      const dm = manifest[k];
      if (dm?.file) routeChunks.push([k, dm.file]);
    }
  }
  let total = 0;
  for (const f of all) total += sizeOf(f);
  const css = [...all].filter((f) => f.endsWith(".css")).reduce((a, f) => a + sizeOf(f), 0);
  const route = routeChunks.length
    ? Math.max(...routeChunks.map(([, f]) => sizeOf(f))) : 0;

  details.push(`initial ${initial} / ${limits.initial_js} B gzip`);
  details.push(`total ${total} / ${limits.total_js} B gzip`);
  details.push(`css ${css} / ${limits.css} B gzip`);
  details.push(routeChunks.length
    ? `route max ${route} / ${limits.route_js} B gzip（${routeChunks.length} 个动态 chunk）`
    : "route 0（manifest 无 dynamicImports）");

  if (initial > limits.initial_js) reds.push(`initial ${initial} > 预算 ${limits.initial_js}（超 ${initial - limits.initial_js} B）`);
  if (total > limits.total_js) reds.push(`total ${total} > 预算 ${limits.total_js}（超 ${total - limits.total_js} B）`);
  if (css > limits.css) reds.push(`css ${css} > 预算 ${limits.css}（超 ${css - limits.css} B）`);
  if (route > limits.route_js) reds.push(`route max ${route} > 预算 ${limits.route_js}（超 ${route - limits.route_js} B）`);
  return { reds, details, sizes: { initial, total, css, route } };
}

function gzipSize(file) {
  const g = zlib.gzipSync(fs.readFileSync(file), { level: 9 });
  return g.length;
}

function main() {
  const dir = path.resolve(WEB, arg("dir", "dist"));
  const budgetsPath = path.join(WEB, "budgets.json");
  let budgets;
  try {
    budgets = JSON.parse(fs.readFileSync(budgetsPath, "utf8"));
  } catch (e) {
    return emit([], [`budgets.json 读不出（${e.message}）—— 未测`], []);
  }
  const manifestPath = path.join(dir, ".vite", "manifest.json");
  if (!fs.existsSync(dir)) {
    return emit([], [`${path.relative(WEB, dir)}/ 不存在 —— 先 npm run build；未测`], []);
  }
  if (!fs.existsSync(manifestPath)) {
    return emit([], [
      `dist/.vite/manifest.json 不存在 —— vite.config 在批次 0 不动，manifest:true 是 Stage 1 的事；` +
      "没有 manifest 不猜 initial/route，按方案 §6.9 退 2（未测）",
    ], [`dist 存在（${path.relative(WEB, dir)}）；基线读数见 web/budgets.json`]);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const sizeOf = (rel) => {
    const p = path.join(dir, rel);
    return fs.existsSync(p) ? gzipSize(p) : 0;
  };
  const r = evaluate(manifest, sizeOf, budgets.limits);
  return emit(r.reds, [], r.details);
}

function emit(reds, untested, details) {
  const payload = { ok: reds.length === 0 && untested.length === 0, reds, untested, waived: [], details };
  if (JSON_OUT) console.log(JSON.stringify(payload, null, 2));
  else {
    for (const d of details) console.log(`  · ${d}`);
    for (const u of untested) console.log(`  ⚠ 未测 ${u}`);
    for (const r of reds) console.log(`  ✗ ${r}`);
    console.log(payload.ok ? "✅ 体积预算全绿" : reds.length ? "❌ 超预算" : "⚠ 未测");
  }
  if (reds.length) return 1;
  if (untested.length) return 2;
  return 0;
}

// ── 反向对照：好样本必须绿、超 1 字节必须红 ──────────────────────────────
function selftest() {
  const LIM = { initial_js: 1000, total_js: 2000, css: 200, route_js: 500 };
  const manifest = {
    "index.html": { file: "assets/index.js", css: ["assets/index.css"], imports: ["_shared.js"], dynamicImports: ["src/pages/A.tsx"] },
    "_shared.js": { file: "assets/shared.js" },
    "src/pages/A.tsx": { file: "assets/A.js", css: ["assets/A.css"] },
  };
  const sizes = {
    "assets/index.js": 500, "assets/index.css": 100, "assets/shared.js": 200,
    "assets/A.js": 300, "assets/A.css": 50,
  };
  const of = (f) => sizes[f] ?? 0;
  const good = evaluate(manifest, of, LIM);
  const bad = evaluate(manifest, (f) => of(f) + (f === "assets/index.js" ? 600 : 0), LIM);
  const cases = [
    ["BS-C1 好样本（全部在预算内）→ 必须绿", good.reds.length === 0, good.reds.join("; ")],
    ["BS-C2 入口 JS 多 1 字节以上 → 必须红（initial 超预算）", bad.reds.some((r) => r.includes("initial")), bad.reds.join("; ")],
    ["BS-C3 initial 递归计入静态 imports 与 css", good.sizes.initial === 800, `initial=${good.sizes.initial}`],
    ["BS-C4 route 取动态 chunk 的 gzip 最大值", good.sizes.route === 300, `route=${good.sizes.route}`],
  ];
  let ok = true;
  for (const [label, pass, detail] of cases) {
    console.log(`${pass ? "✓" : "✗"} ${label}${pass ? "" : `  ← ${detail}`}`);
    if (!pass) ok = false;
  }
  return ok ? 0 : 1;
}

if (flag("selftest")) process.exit(selftest());
process.exit(main());
