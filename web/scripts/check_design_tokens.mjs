#!/usr/bin/env node
/**
 * check_design_tokens.mjs —— 设计语言的机器执行点（DT-1…DT-8）
 *
 * 为什么要有它：方案 §5.8 把「只用语义 token」写成规则，而规则没有执行点就是一段散文
 * （AGENTS.md §2.4）。本脚本是 DT 的唯一实现；`tools/verify_frontend_deps.py` 的 F13
 * 用 `--check --json` 调它，**不在 Python 里重写第二套正则**。
 *
 * ## 输出契约（方案 §6.12 / L857）
 *
 *   { ok, reds[], untested[], waived[], details[] }
 *
 * 退出码：0 = 全绿；1 = 有红；2 = 有未测（**未测 ≠ 通过 ≠ 红**）。
 *
 * ## 口径
 *
 *   * 文件发现只用 `git ls-files`（与 `verify_download_governance.py` 同一条纪律）。
 *     git 跑不了 → 退 2，不当成「没有文件」。
 *   * 注释不算代码：整行注释与块注释先剥掉再判（这是本项目被误报绊过多次的教训）。
 *   * 批次 0 里 `tokens.css` 还不存在（Stage 2 才建），所以 DT-4/5/6/7 报**未测**，
 *     不报绿 —— 判据对象不存在时说「通过」就是假绿。
 *   * DT-3 是**棘轮**：基线里的裸值可以保留，删除允许（shrink-only），
 *     基线之外新增一条就红。基线文件 `web/design-baseline.json`。
 *
 * ## 用法
 *
 *   node web/scripts/check_design_tokens.mjs --check
 *   node web/scripts/check_design_tokens.mjs --check --json
 *   node web/scripts/check_design_tokens.mjs --rebase-baseline   # 只在显式要求时改基线
 *   node web/scripts/check_design_tokens.mjs --selftest          # 在临时目录里跑全部反向对照
 *
 * ★ 自证无副作用（方案 §6.11）：`--selftest` 只在 mktemp 目录里造样本；
 *   指向真实仓库会被拒绝（反向对照 C20 的另一半：证明拒绝不是恒真）。
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
// ★ DT-3 裸值判据的**唯一实现**（2026-10-23 抽出）。
//   此前 check_frontend_gates.mjs 里还有一份副本，改一处必漏另一处 ——
//   实测就漏了：DT-3 改完口径归零，而 #111 通道3 仍按旧口径算出 95 处。
import { BARE_PROPS, bareValue, parseBareEntries, keyOf } from "./dt3-bare.mjs";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");
const REPO = path.resolve(WEB, "..");

function flag(name) {
  return process.argv.includes(`--${name}`);
}
function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const JSON_OUT = flag("json");
const CHECKS = [];   // {id, ok, reds[], untested[], waived[], details[]}

function push(id, reds, untested, waived, details) {
  CHECKS.push({ id, reds, untested, waived, details });
}

// ── 文本工具 ─────────────────────────────────────────────────────────────

/** 注释不算代码。块注释 + 整行 `//`；行尾注释保留（已知盲区，与 verify_shouheng_ops C5 同口径）。 */
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** 从源码里抽 className / 模板字符串里的类名串（只用于 DT-1/DT-2 的样本匹配）。 */
function classStrings(src) {
  const out = [];
  const re = /className\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*`([^`]*)`\s*\}|\{\s*"([^"]*)"\s*\}|\{\s*'([^']*)'\s*\})/g;
  let m;
  while ((m = re.exec(src))) out.push(m[1] ?? m[2] ?? m[3] ?? m[4] ?? m[5] ?? "");
  return out;
}

// ── DT-1 非语义颜色工具类 ────────────────────────────────────────────────
const PALETTE = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black";
const DT1_RE = new RegExp(
  `\\b(?:bg|text|border|ring|fill|stroke|from|to|via|divide|outline|decoration|placeholder|shadow)-(?:${PALETTE})(?:-\\d{2,3})?\\b`,
  "g",
);
function dt1Hits(src) {
  const hits = [];
  for (const s of classStrings(stripComments(src))) {
    const m = s.match(DT1_RE);
    if (m) hits.push(...m);
  }
  return [...new Set(hits)];
}

// ── DT-2 任意值绕过 token ────────────────────────────────────────────────
const DT2_RE = /\b[a-z][a-z0-9-]*-\[[^\]]+\]/g;
function dt2Hits(src) {
  const hits = [];
  for (const s of classStrings(stripComments(src))) {
    const m = s.match(DT2_RE);
    if (m) hits.push(...m);
  }
  return [...new Set(hits)];
}

// ── DT-3 样式层裸值棘轮 ──────────────────────────────────────────────────
//
// ★ 2026-10-23 就地改判据（行 111 口径校正）。改前 DT-3 报「95 处裸值」，实测拆开是：
//
//     67 处  hsl(var(--brand))            ← **不是裸值**，颜色来自 tokens.css
//     28 处  1px solid hsl(var(--border)) ← 线宽不是行 111 点名的三类之一
//      0 处  真裸值（hex / 非 var 颜色函数 / 裸间距 / 裸字号）
//
//   两个毛病都出在**判据**，不在验收表：
//
//   ① **假阳性**：旧写 `/\b(?:rgba?|hsla?)\(/` 只看见函数名 `hsl(` 就判裸值，
//      不看参数。而 `hsl(var(--brand))` 的通道值存在 tokens.css 里
//      （`--brand: 346.5 41.3% 29.4%`），**它是 token 引用**。
//   ② **越界**：行 111 原文是「**颜色/间距/字号**全部来自 token」。
//      `border: 1px solid …` 里的 `1px` 是**边框线宽**，不在这三类里；
//      但颜色若写死（`1px solid #ff0000`）仍然必须红 —— 所以不能整个属性跳过。
//
//   修法：**先把 token 引用整段抠掉，再在剩下的部分找裸值。**
//   `1px solid hsl(var(--border))` 抠掉后剩 `1px solid ` → 无裸值；
//   `1px solid #ff0000` 抠掉后仍含 `#ff0000` → 裸值。
//   这不是放宽判据，是**先认得出 token 引用**。
//
// ★ 2026-10-23：判据与解析器已抽到 `web/scripts/dt3-bare.mjs`（唯一实现）。
//   此前本文件与 `check_frontend_gates.mjs` 各有一份副本，改一处必漏另一处 ——
//   实测就漏了：本文件改完口径归零，#111 通道3 仍按旧口径算出 95 处。
//   现在两处都 import 同一份。**同一判断只许有一处实现（§2.5）。**

/** JSX 内联样式里的裸值（style={{ color: "#fff", fontSize: 13 }}）。 */
function inlineBare(src) {
  const hits = [];
  const re = /style\s*=\s*\{\{([\s\S]*?)\}\}/g;
  let m;
  while ((m = re.exec(stripComments(src)))) {
    const body = m[1];
    const propRe = /(\w+)\s*:\s*("([^"]*)"|'([^']*)'|(-?\d+(?:\.\d+)?))/g;
    let p;
    while ((p = propRe.exec(body))) {
      const prop = p[1];
      const value = p[3] ?? p[4] ?? p[5] ?? "";
      if (/^#|rgba?\(|hsla?\(|\d+px$/.test(value) ||
          (prop === "fontSize" && /^-?\d+(\.\d+)?$/.test(value))) {
        hits.push(`${prop}: ${value}`);
      }
    }
  }
  return hits;
}

// ── DT-4 只有 tokens.css 能定义 :root 自定义属性 ──────────────────────────
const DT4_RE = /:root\s*\{[^}]*--[a-z-]+\s*:/;
function dt4Hits(cssText) {
  return DT4_RE.test(cssText.replace(/\/\*[\s\S]*?\*\//g, "")) ? ["legacy :root 自定义属性"] : [];
}

// ── DT-6 品牌红只用于高风险动作 ─────────────────────────────────────────
const DT6_RE = /<Button\b[^>]*\bvariant\s*=\s*["'{]+(?:primary|default)\b/;
function dt6Hits(src) {
  const clean = stripComments(src);
  const hits = [];
  const tagRe = /<Button\b[^>]*>/g;
  let m;
  while ((m = tagRe.exec(clean))) {
    if (DT6_RE.test(m[0]) && !/data-risk-action\s*=\s*["'{]+(?:submit|release-decision)\b/.test(m[0])) {
      hits.push(m[0].replace(/\s+/g, " ").slice(0, 80));
    }
  }
  return hits;
}

// ── DT-8 图标入口唯一 ────────────────────────────────────────────────────
const DT8_RE = /import\s+[^;]*\bfrom\s+["']lucide-react["']/;
const DT8_STAR_RE = /import\s+\*\s+as\s+\w+\s+from\s+["']lucide-react["']/;
function dt8Hits(src, file) {
  const clean = stripComments(src);
  if (/\/icon\.tsx$/.test(file)) return [];         // 唯一允许的入口
  const hits = [];
  if (DT8_RE.test(clean)) hits.push("direct lucide import");
  if (DT8_STAR_RE.test(clean)) hits.push("import * as Icons");
  if (/[←⚠↓]/.test(clean)) hits.push("Unicode 图标字符");
  return hits;
}

// ── 仓库读取 ─────────────────────────────────────────────────────────────
function gitFiles(root) {
  try {
    const out = execFileSync("git", ["ls-files", "-z"], {
      cwd: root, encoding: "buffer", timeout: 120000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    return out.toString("utf8").split("\0").filter(Boolean);
  } catch {
    return null;              // 未测，不是空集
  }
}

function loadJson(p, fallback) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return fallback;
  }
}

/**
 * 全文件口径统计 legacy CSS（如 web/src/styles.css，不含 tokens.css）的字面量分布：
 * 区分「真裸值（非 var 的色值、字号/间距 px）」与「函数包装器 / 边框线宽 / 药丸圆角 / 44px 触控底线 / @media 断点」。
 */
function countCssLiterals(src) {
  const clean = src.replace(/\/\*[\s\S]*?\*\//g, "");
  const hex = (clean.match(/#[0-9a-fA-F]{3,8}\b/g) || []).length;
  const fnAll = clean.match(/\b(?:rgba?|hsla?)\([^)]*\)/g) || [];
  const fnWithVar = fnAll.filter((m) => /var\(--/.test(m)).length;
  const fnBare = fnAll.length - fnWithVar;
  const pxAll = (clean.match(/\b\d*\.?\d+px\b/g) || []).length;
  return { hex, fnAll: fnAll.length, fnWithVar, fnBare, pxAll };
}

// ── 主检查 ───────────────────────────────────────────────────────────────
function runCheck(root) {
  const files = gitFiles(root);
  if (files === null) {
    push("discovery", [], ["`git ls-files` 不可用 —— 未测（不是「没有文件」）"], [], []);
    return;
  }
  const webFiles = files.filter((f) => f.startsWith("web/"));
  const tsx = webFiles.filter((f) => /^web\/src\/.*\.(tsx|jsx)$/.test(f));
  const css = webFiles.filter((f) => /^web\/src\/.*\.css$/.test(f));
  const TOKENS = "web/src/styles/tokens.css";
  const legacyCss = css.filter((f) => f !== TOKENS);
  const tokensExists = files.includes(TOKENS);

  const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

  // DT-1 / DT-2
  const dt1 = [], dt2 = [];
  for (const f of tsx) {
    for (const h of dt1Hits(read(f))) dt1.push(`${f}: ${h}`);
    for (const h of dt2Hits(read(f))) dt2.push(`${f}: ${h}`);
  }
  push("DT-1", dt1, [], [], [`扫描 ${tsx.length} 个 tsx/jsx 的 className`]);
  push("DT-2", dt2, [], [], [`扫描 ${tsx.length} 个 tsx/jsx 的任意值类名`]);

  // DT-3 基线棘轮
  const baseline = loadJson(path.join(WEB, "design-baseline.json"), null);
  if (baseline === null) {
    push("DT-3", [], ["design-baseline.json 不存在 —— 未测（先跑 --rebase-baseline 记录基线）"], [], []);
  } else {
    const known = new Set((baseline.tokens || []).map((e) => keyOf(e.file, e)));
    const current = [];
    for (const f of legacyCss) {
      const rel = f.replace(/^web\//, "");
      for (const e of parseBareEntries(read(f))) current.push({ file: rel, ...e });
    }
    for (const f of tsx) {
      const rel = f.replace(/^web\//, "");
      for (const h of inlineBare(read(f))) {
        current.push({ file: rel, selector: "inline-style", prop: h.split(":")[0], value: h.split(": ")[1] });
      }
    }
    const seen = new Set();
    const newOnes = [];
    for (const e of current) {
      const k = keyOf(e.file, e);
      if (seen.has(k)) continue;
      seen.add(k);
      if (!known.has(k)) newOnes.push(`${e.file}: ${e.selector} { ${e.prop}: ${e.value} }`);
    }
    const removed = [...known].filter((k) => !seen.has(k)).length;
    const maxTokens = typeof baseline.max_tokens === "number" ? baseline.max_tokens : known.size;
    if (seen.size > maxTokens) {
      newOnes.push(`历史裸值存量越过天花板：当前 ${seen.size} > 上限 ${maxTokens}（严禁增长）`);
    }
    if (known.size > maxTokens) {
      newOnes.push(`design-baseline.json 的 tokens 条数（${known.size}）超出上限 max_tokens（${maxTokens}）`);
    }
    const lit = { hex: 0, fnAll: 0, fnWithVar: 0, fnBare: 0, pxAll: 0 };
    for (const f of legacyCss) {
      const c = countCssLiterals(read(f));
      lit.hex += c.hex;
      lit.fnAll += c.fnAll;
      lit.fnWithVar += c.fnWithVar;
      lit.fnBare += c.fnBare;
      lit.pxAll += c.pxAll;
    }
    if (lit.hex > 0 || lit.fnBare > 0) {
      newOnes.push(`legacy CSS 出现真颜色裸值：hex=${lit.hex}, non_var_rgb_hsl=${lit.fnBare}`);
    }
    const caps = baseline.category_caps;
    if (caps && typeof caps === "object") {
      if (typeof caps.px_literals_all_props === "number" && lit.pxAll > caps.px_literals_all_props) {
        newOnes.push(`legacy CSS 全文件 px 字面量增长：当前 ${lit.pxAll} > 上限 ${caps.px_literals_all_props}`);
      }
      if (typeof caps.hsl_var_wrappers_all_props === "number" && lit.fnWithVar > caps.hsl_var_wrappers_all_props) {
        newOnes.push(`legacy CSS 全文件 hsl(var(--*)) 包装数增长：当前 ${lit.fnWithVar} > 上限 ${caps.hsl_var_wrappers_all_props}`);
      }
    }
    push("DT-3", newOnes, [], [],
      [
        `基线 ${known.size} 条（上限 ${maxTokens}）· 当前 ${seen.size} 条 · 新增 ${newOnes.length} · 已删除 ${removed}（shrink-only）`,
        `全文件分项读数：裸 hex=${lit.hex} · 非 var rgb/hsl=${lit.fnBare} · hsl(var(--*))=${lit.fnWithVar} · px 字面量=${lit.pxAll}`,
      ]);
  }

  // DT-4 / DT-5 / DT-7：判据对象是 tokens.css（Stage 2 才建）
  if (!tokensExists) {
    const why = `tokens.css 不存在（${TOKENS}；Stage 2 才建）—— 判据对象还没有，不能报绿`;
    push("DT-4", [], [why], [], []);
    push("DT-5", [], [why], [], []);
    push("DT-7", [], [why], [], []);
  } else {
    const d4 = [];
    for (const f of legacyCss) {
      if (dt4Hits(read(f)).length) d4.push(`${f}: :root 自定义属性`);
    }
    push("DT-4", d4, [], [], [`扫描 ${legacyCss.length} 个 legacy CSS`]);

    const dt5 = dt5Check(root, read(TOKENS), files);
    push("DT-5", dt5.reds, dt5.untested, [], dt5.details);

    const d7 = [];
    for (const f of legacyCss) {
      const txt = stripComments(read(f));
      const m = txt.match(/font-family\s*:\s*([^;}]+)/g) || [];
      for (const x of m) if (!/var\(--/.test(x)) d7.push(`${f}: ${x.trim()}`);
    }
    push("DT-7", d7, [], [], [`扫描 ${legacyCss.length} 个 legacy CSS 的 font-family`]);
  }

  // DT-6：需要 Button 组件（Stage 5）
  const hasButton = tsx.some((f) => /Button\.(tsx|jsx|ts)$/.test(f)) ||
    files.some((f) => /web\/src\/.*Button\.(tsx|jsx|ts)$/.test(f));
  if (!hasButton) {
    push("DT-6", [], ["没有 Button 组件（Stage 5 引入）—— 判据对象不存在，不能报绿"], [], []);
  } else {
    const d6 = [];
    for (const f of tsx) {
      if (/\/ui\/button\.tsx$/.test(f)) continue;
      for (const h of dt6Hits(read(f))) d6.push(`${f}: ${h}`);
    }
    push("DT-6", d6, [], [], [`扫描 ${tsx.length} 个 tsx 的 Button variant`]);
  }

  // DT-8 —— 拆成两条，因为它们在批次 0 的可执行性不同：
  //   DT-8a（直接 import lucide / import *）今天就能判，且今天应当是绿的；
  //   DT-8b（正文 Unicode 图标）的**合规替代入口**是 src/ui/icon.tsx，而它 Stage 2 才建。
  //     没有入口时报红，会得到一扇**永远红到 Stage 2** 的门 —— 那正是 §2.1.1 说的
  //     「让人开始不看报告」。所以这一条报未测，并把命中数列出来（不让它静默消失）。
  const iconEntry = files.some((f) => /^web\/src\/ui\/icon\.(tsx|ts|jsx)$/.test(f));
  const d8a = [], d8b = [];
  for (const f of tsx) {
    for (const h of dt8Hits(read(f), f)) {
      if (h === "Unicode 图标字符") d8b.push(`${f}`);
      else d8a.push(`${f}: ${h}`);
    }
  }
  push("DT-8a", d8a, [], [], [`扫描 ${tsx.length} 个 tsx 的直接 lucide import`]);
  if (iconEntry) {
    push("DT-8b", d8b, [], [], [`扫描 ${tsx.length} 个 tsx 的正文 Unicode 图标`]);
  } else {
    push("DT-8b", [], [
      `没有 src/ui/icon.tsx（Stage 2 建）—— Unicode 图标没有合规替代入口；` +
      `当前命中 ${d8b.length} 个文件：${[...new Set(d8b)].slice(0, 5).join(", ")}`,
    ], [], []);
  }

  // 反向对照：每次主检查都真跑（方案 §6.11）
  const ctl = controls();
  for (const [id, ok, detail] of ctl) {
    push(id, ok ? [] : [detail], [], [], [detail]);
  }
}

/** DT-5：DESIGN.md 机器块 ↔ tokens.css ↔ @theme。Stage 2 才可能绿。 */
function dt5Check(root, tokensCss, files) {
  const design = files.find((f) => f === "web/DESIGN.md");
  const designPath = design ? path.join(root, design) : null;
  if (!designPath || !fs.existsSync(designPath)) {
    return { reds: [], untested: ["web/DESIGN.md 没有机器块（TOKENS:BEGIN/END）—— 未测"], details: [] };
  }
  const txt = fs.readFileSync(designPath, "utf8");
  const m = txt.match(/<!--\s*TOKENS:BEGIN\s*-->([\s\S]*?)<!--\s*TOKENS:END\s*-->/);
  if (!m) {
    return { reds: [], untested: ["web/DESIGN.md 没有 TOKENS:BEGIN/END 机器块 —— 未测"], details: [] };
  }
  const rows = [...m[1].matchAll(/^\|\s*`?--([a-z0-9-]+)`?\s*\|\s*([^|]+?)\s*\|/gm)]
    .map((x) => [x[1].trim(), x[2].trim()]);
  if (!rows.length) {
    return { reds: [], untested: ["DESIGN.md 机器块里解析不出 token 行 —— 未测"], details: [] };
  }
  const cssVars = new Map(
    [...tokensCss.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)].map((x) => [x[1].trim(), x[2].trim()]),
  );
  const reds = [];
  for (const [name, value] of rows) {
    if (!cssVars.has(name)) reds.push(`DESIGN 有 --${name}，tokens.css 没有`);
    else if (cssVars.get(name).replace(/\s+/g, "") !== value.replace(/\s+/g, "")) {
      reds.push(`--${name}: DESIGN=${value} vs tokens.css=${cssVars.get(name)}`);
    }
  }
  return { reds, untested: [], details: [`DESIGN 机器块 ${rows.length} 条 · tokens.css ${cssVars.size} 条`] };
}

// ── 反向对照（DT-C1…DT-C6；永远在内存里造样本）────────────────────────────
function controls() {
  const out = [];
  const c1 = dt1Hits('const x = <div className="bg-neutral-100" />;');
  const c3a = dt1Hits('const x = <div className="bg-background text-muted-foreground" />;');
  const c3b = dt2Hits('const x = <div className="bg-background text-muted-foreground" />;');
  out.push(["DT-C1", c1.includes("bg-neutral-100"),
    `坏样本 bg-neutral-100 → ${c1.includes("bg-neutral-100") ? "已抓到" : "**没抓到**"}`]);
  const c2 = dt2Hits('const x = <div className="text-[13px]" />;');
  out.push(["DT-C2", c2.includes("text-[13px]"),
    `坏样本 text-[13px] → ${c2.includes("text-[13px]") ? "已抓到" : "**没抓到**"}`]);
  out.push(["DT-C3", c3a.length === 0 && c3b.length === 0,
    `好样本（语义 token）→ ${c3a.length === 0 && c3b.length === 0 ? "未误报" : "**被误报**"}`]);
  const c4 = dt4Hits(".legacy { } :root { --border: 1px solid #fff; }");
  out.push(["DT-C4", c4.length > 0,
    `legacy :root → ${c4.length > 0 ? "已抓到" : "**没抓到**"}`]);
  const c5bad = dt6Hits('<Button variant="primary">筛选</Button>');
  const c5ok = dt6Hits('<Button variant="primary" data-risk-action="submit">提交</Button>');
  out.push(["DT-C5", c5bad.length > 0 && c5ok.length === 0,
    `筛选按钮 primary → ${c5bad.length > 0 ? "红" : "**没红**"} · submit 带 data-risk-action → ${c5ok.length === 0 ? "绿" : "**误报**"}`]);
  const c6bad = dt8Hits('import { Bell } from "lucide-react";', "web/src/pages/X.tsx");
  const c6ok = dt8Hits('import { Bell } from "./icon";', "web/src/ui/icon.tsx");
  out.push(["DT-C6", c6bad.length > 0 && c6ok.length === 0,
    `业务页直接 import lucide → ${c6bad.length > 0 ? "红" : "**没红**"} · icon.tsx 入口 → ${c6ok.length === 0 ? "绿" : "**误报**"}`]);
  return out;
}

// ── selftest：临时目录 + 拒绝真实仓库 ────────────────────────────────────
function selftest() {
  const root = arg("root", "");
  if (root) {
    const real = path.resolve(root) === REPO;
    if (real) {
      console.error("❌ --selftest 不许指向真实仓库（方案 §6.11）：自证会写基线/读真实文件。");
      return 2;
    }
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "dt_selftest_"));
  try {
    fs.mkdirSync(path.join(tmp, "web/src/pages"), { recursive: true });
    fs.writeFileSync(path.join(tmp, "web/src/pages/A.tsx"),
      'export const A = () => <div className="bg-background text-[13px]" />;\n');
    execFileSync("git", ["init", "-q"], { cwd: tmp });
    execFileSync("git", ["add", "-A"], { cwd: tmp });
    // 临时仓里跑主检查：DT-2 必须红，DT-1 不红
    const out = [];
    const before = CHECKS.length;
    runCheck(tmp);
    const dt1 = CHECKS.slice(before).find((c) => c.id === "DT-1");
    const dt2 = CHECKS.slice(before).find((c) => c.id === "DT-2");
    const ok = dt1 && dt2 && dt1.reds.length === 0 && dt2.reds.length > 0;
    out.push(["SELFTEST", ok, "临时仓主检查：DT-1 应绿、DT-2 应红"]);
    // 未测路径：非 git 目录
    const nogit = fs.mkdtempSync(path.join(os.tmpdir(), "dt_nogit_"));
    try {
      const b2 = CHECKS.length;
      runCheck(nogit);
      const d = CHECKS.slice(b2).find((c) => c.id === "discovery");
      out.push(["SELFTEST-NOGIT", Boolean(d && d.untested.length === 1),
        "非 git 目录应落未测而不是空集"]);
    } finally {
      fs.rmSync(nogit, { recursive: true, force: true });
    }
    for (const [id, good, detail] of out) {
      console.log(`${good ? "✓" : "✗"} ${id} ${detail}`);
    }
    return out.every((x) => x[1]) ? 0 : 1;
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

// ── 基线重写 ─────────────────────────────────────────────────────────────
function rebaseBaseline(root) {
  const files = gitFiles(root);
  if (files === null) {
    console.error("❌ `git ls-files` 不可用 —— 未测，不写基线");
    return 2;
  }
  const tokens = [];
  const seen = new Set();
  for (const f of files.filter((x) => /^web\/src\/.*\.css$/.test(x))) {
    if (f === "web/src/styles/tokens.css") continue;
    const rel = f.replace(/^web\//, "");
    for (const e of parseBareEntries(fs.readFileSync(path.join(root, f), "utf8"))) {
      const k = keyOf(rel, e);
      if (seen.has(k)) continue;
      seen.add(k);
      tokens.push({ file: rel, selector: e.selector, prop: e.prop, value: e.value });
    }
  }
  for (const f of files.filter((x) => /^web\/src\/.*\.(tsx|jsx)$/.test(x))) {
    const rel = f.replace(/^web\//, "");
    for (const h of inlineBare(fs.readFileSync(path.join(root, f), "utf8"))) {
      const [prop, value] = h.split(": ");
      const k = keyOf(rel, { selector: "inline-style", prop, value });
      if (seen.has(k)) continue;
      seen.add(k);
      tokens.push({ file: rel, selector: "inline-style", prop, value });
    }
  }
  const old = loadJson(path.join(WEB, "design-baseline.json"), {}) || {};
  const lit = { hex: 0, fnAll: 0, fnWithVar: 0, fnBare: 0, pxAll: 0 };
  for (const f of files.filter((x) => /^web\/src\/.*\.css$/.test(x))) {
    if (f === "web/src/styles/tokens.css") continue;
    const c = countCssLiterals(fs.readFileSync(path.join(root, f), "utf8"));
    lit.hex += c.hex;
    lit.fnAll += c.fnAll;
    lit.fnWithVar += c.fnWithVar;
    lit.fnBare += c.fnBare;
    lit.pxAll += c.pxAll;
  }
  const doc = {
    schema_version: 1,
    "$note": "DT-3 的裸值基线（file+selector+property+value，shrink-only）。只由 check_design_tokens.mjs --rebase-baseline 生成；手改会被下一次 --check 当成「新增裸值」。visual 段由 check_visual.mjs --update 维护。",
    "generated_by": "web/scripts/check_design_tokens.mjs --rebase-baseline",
    "generated_at": new Date().toISOString().slice(0, 10),
    max_tokens: tokens.length,
    category_caps: {
      hex_literals: lit.hex,
      non_var_rgb_hsl: lit.fnBare,
      hsl_var_wrappers_all_props: lit.fnWithVar,
      px_literals_all_props: lit.pxAll,
    },
    tokens,
    visual: old.visual ?? null,
  };
  fs.writeFileSync(path.join(WEB, "design-baseline.json"),
    JSON.stringify(doc, null, 1) + "\n", "utf8");
  console.log(`✅ 基线已写：${tokens.length} 条裸值 → web/design-baseline.json`);
  return 0;
}

// ── 输出 ─────────────────────────────────────────────────────────────────
function emit() {
  const reds = [], untested = [], waived = [], details = [];
  for (const c of CHECKS) {
    for (const r of c.reds) reds.push(`[${c.id}] ${r}`);
    for (const u of c.untested) untested.push(`[${c.id}] ${u}`);
    for (const w of c.waived) waived.push(`[${c.id}] ${w}`);
    for (const d of c.details) details.push(`[${c.id}] ${d}`);
  }
  const ok = reds.length === 0 && untested.length === 0;
  const payload = { ok, reds, untested, waived, details };
  if (JSON_OUT) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    for (const d of details) console.log(`  · ${d}`);
    for (const w of waived) console.log(`  ~ WAIVED ${w}`);
    for (const u of untested) console.log(`  ⚠ 未测 ${u}`);
    for (const r of reds) console.log(`  ✗ ${r}`);
    console.log(ok ? "✅ DT 全绿" : reds.length ? `❌ DT ${reds.length} 项红` : `⚠ DT 有 ${untested.length} 项未测`);
  }
  if (reds.length) return 1;
  if (untested.length) return 2;
  return 0;
}

// ── 入口 ─────────────────────────────────────────────────────────────────
if (flag("selftest")) {
  process.exit(selftest());
} else if (flag("rebase-baseline")) {
  process.exit(rebaseBaseline(REPO));
} else {
  runCheck(arg("root", REPO));
  process.exit(emit());
}
