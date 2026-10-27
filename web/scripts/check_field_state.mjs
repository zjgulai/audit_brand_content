#!/usr/bin/env node
/**
 * check_field_state.mjs —— ADR-0021 · W-2 的执行点
 *
 * ## 它守的是什么
 *
 * 界面把「缺失」渲染成「确定状态」共六处（审计 2026-10-27）：
 *
 *   ContentUnitViewer.tsx:116   parse_status ?? "ok"
 *   AdminGrantsPage.tsx:330     product_line ?? "all"      ← all 是权限语义
 *   AdminGrantsPage.tsx:338     徽标 ?? "active"
 *   TakedownPage.tsx:543        tenant ?? "t1"             ← t1 是真实租户号
 *   ReleasePage.tsx:205         submitter_id: null 写死
 *   ReleasePage.tsx:278-280     三元两分支文案相同
 *
 * 这一份守的是「统一写法本身不撒谎」，以及**六处是否真的改成了它**。
 *
 * ## 分组
 *
 *   A 三态判定（fieldStateKind）      —— ok / missing / unreadable 互不相同
 *   B ★ 不许默认值                    —— 缺值绝不能输出一个看起来正常的值
 *   C ★ 反向对照                      —— 把兜底写法喂回去，判据必须红
 *   D ★★ 六处站点的扫描              —— 源码里那四个兜底字面量必须消失
 *
 * ## 退出码
 *
 * 0 全过 / 1 有红 / 2 未测（源码读不出等）
 *
 * ★ 为什么要扫源码而不是只测组件：组件写得再对，六处不改等于没做。
 *   但**光**扫源码也不够 —— 那是「名字出现过」那类恒真判据（§2.4）。
 *   所以 C 组喂坏样本，D 组查具体兜底字面量，两者成对。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, "..");
const SRC = path.join(WEB, "src");

let pass = 0;
const fails = [];
const untested = [];

function ok(name) {
  pass += 1;
  console.log(`PASS: ${name}`);
}
function bad(name, detail = "") {
  fails.push(`${name}${detail ? `  ${detail}` : ""}`);
  console.log(`FAIL: ${name}${detail ? `  ${detail}` : ""}`);
}
function skip(name, detail = "") {
  untested.push(`${name}${detail ? `  ${detail}` : ""}`);
  console.log(`UNTESTED: ${name}${detail ? `  ${detail}` : ""}`);
}
function check(cond, name, detail = "") {
  if (cond) ok(name);
  else bad(name, detail);
}

// ── 直接 import 真身 ────────────────────────────────────────────────
//
// ★ 第一版是「用正则从 .tsx 源码里抠出函数体，再 new Function 执行」。
//   它当场失败：函数体里有可选链（`props.missingReason?.trim()`），
//   eval 的语法环境不认 —— 报 `Unexpected token '?'`。
//
//   但更根本的问题是：抠出来的是**一段文本**，不是被 TS 检查过的真身。
//   源码里改个参数名，正则可能还是能抠到，于是测的东西与跑的东西悄悄分叉。
//
//   所以把纯逻辑抽到 `fieldState.logic.ts`（无 JSX），
//   用 Node 24 的 --experimental-strip-types 直接 import。
//   **测真身，不测副本。**
//
// ★ 这个脚本必须用 `node --experimental-strip-types` 跑；
//   直接 `node` 会在 import .ts 时报错，那时本脚本退 2（未测），不是 0。
let fieldStateKind;
let fieldStateText;
try {
  const mod = await import("../src/ui/fieldState.logic.ts");
  fieldStateKind = mod.fieldStateKind;
  fieldStateText = mod.fieldStateText;
  if (typeof fieldStateKind !== "function" || typeof fieldStateText !== "function") {
    throw new Error("导出的不是函数");
  }
} catch (e) {
  skip(
    "import fieldState.logic.ts",
    `${e.message}（本脚本需用 node --experimental-strip-types 运行）`,
  );
  process.exit(2);
}

// ═══════════════════════════════════════════════ A 三态判定
const A = [
  ["有值 → ok", fieldStateKind("brief") === "ok"],
  ["数字 0 → ok（★ 0 是合法值，真值判断会吞掉它）", fieldStateKind(0) === "ok"],
  ["null → missing", fieldStateKind(null) === "missing"],
  ["undefined → missing", fieldStateKind(undefined) === "missing"],
  ["空串 → missing", fieldStateKind("") === "missing"],
  ["全空白 → missing", fieldStateKind("   ") === "missing"],
  ["NaN → missing（数字但不可用）", fieldStateKind(Number.NaN) === "missing"],
  ["给了 unreadableReason → unreadable", fieldStateKind("x", "接口 500") === "unreadable"],
  [
    "★★ unreadable 优先于有值（读不出时不许显示旧值）",
    fieldStateKind("x", "接口 500") !== fieldStateKind("x"),
  ],
];
for (const [name, cond] of A) check(cond, `A ${name}`);

// ═══════════════════════════════════════════════ B ★ 不许默认值
const B = [
  [
    "★ missing 时输出「未测」而不是空",
    fieldStateText({ value: null }).includes("未测"),
  ],
  [
    "★★ missing 时不输出任何看起来像值的字符",
    !/\d/.test(fieldStateText({ value: null })),
  ],
  [
    "★ 带 label 时是「阶段：未测」",
    fieldStateText({ value: null, label: "阶段" }) === "阶段：未测",
  ],
  [
    "有原因时「未测（原因）」—— 说清为什么",
    fieldStateText({ value: null, missingReason: "后端未返回" }) ===
      "未测（后端未返回）",
  ],
  [
    "★★★ unreadable 与 missing 文案必须不同",
    fieldStateText({ value: null, unreadableReason: "接口 500" }) !==
      fieldStateText({ value: null }),
  ],
  [
    "unreadable 带「读不出」三个字（不能读成「没测」）",
    fieldStateText({ value: null, unreadableReason: "接口 500" }).includes("读不出"),
  ],
  [
    "ok 时原样加单位",
    fieldStateText({ value: 3.7, unit: " ms" }) === "3.7 ms",
  ],
  [
    "★ ok 时带 label",
    fieldStateText({ value: "brief", label: "阶段" }) === "阶段：brief",
  ],
];
for (const [name, cond] of B) check(cond, `B ${name}`);

// ═══════════════════════════════════════════════ C ★ 反向对照
//
// ★ 这一段是整份文件的重点：把六处**原来的兜底写法**重放一遍，
//   确认统一写法给出的答案与它们不同。若哪天有人把兜底逻辑加回组件，
//   这些用例会立刻发现「两者又变一样了」。
const fallbackCases = [
  ["parse_status ?? \"ok\"", fieldStateText({ value: null, label: "状态" }) !== "状态：ok"],
  ["product_line ?? \"all\"", fieldStateText({ value: null }) !== "all"],
  ["徽标 ?? \"active\"", fieldStateText({ value: null }) !== "active"],
  ["tenant ?? \"t1\"", fieldStateText({ value: null }) !== "t1"],
  ["submitter_id: null", fieldStateText({ value: null }) !== "null"],
];
for (const [name, cond] of fallbackCases) {
  check(cond, `C ★★ 兜底写法「${name}」已被替代（输出不是那个值）`);
}

// C6 ★ 好样本必须绿 —— 否则上面全是恒真（组件永远输出「未测」也能过）
check(
  fieldStateText({ value: "pump" }) === "pump",
  "C6 ★ 好样本：有值时必须原样输出（否则上面全是恒真）",
);

// ═══════════════════════════════════════════════ D ★★ 六处站点
//
// 每个条目的判据是「这个文件里**不再出现**那个兜底写法」。
// ★ 只查字面量，不查语义 —— 这是有意的：语义检查靠 A/B/C 三组，
//   这里只负责「有没有真的改到那六个地方」。
const SITES = [
  {
    file: "components/ContentUnitViewer.tsx",
    forbidden: [/parse_status\s*\?\?\s*"ok"/],
    what: 'parse_status ?? "ok"',
  },
  {
    file: "pages/AdminGrantsPage.tsx",
    forbidden: [/product_line\s*\?\?\s*"all"/, /g\.state\s*\?\?\s*g\.status\s*\?\?\s*"active"/],
    what: 'product_line ?? "all" / ?? "active"',
  },
  {
    file: "pages/TakedownPage.tsx",
    forbidden: [/t\.tenant\s*\?\?\s*"t1"/],
    what: 'tenant ?? "t1"',
  },
  {
    file: "pages/ReleasePage.tsx",
    forbidden: [/submitter_id:\s*null/, /\?\s*"不可自签"\s*:\s*"不可自签"/],
    what: "submitter_id: null / 三元两分支同文案",
  },
];

/**
 * 剥注释（整行 + 块注释）。
 *
 * ★ 第一次跑 D 组时三条全红，而代码其实已经改好了 —— 红的是**我自己的注释**：
 *   "改前 `parse_status ?? \"ok\"` 会显示…"。判据把解释文字当成了违规代码。
 *   这是 AGENTS.md §2.4.4 那条教训（被自己的解释文字绊倒）在本次执行里重演，
 *   与 `verify_shouheng_ops.py` 的 C5、`verify_cards.mjs` 的 J1a 同一条读法：
 *   **注释不算代码。**
 *
 * ★ 只剥 `//` 与 `/* *\/`，不剥字符串里的 `//`（URL 会误伤）——
 *   本目录没有 URL 字面量，这是已知且可接受的粗法。
 */
function stripComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((line) => {
      const i = line.indexOf("//");
      return i >= 0 ? line.slice(0, i) : line;
    })
    .join("\n");
}

for (const site of SITES) {
  const p = path.join(SRC, site.file);
  let body;
  try {
    body = fs.readFileSync(p, "utf8");
  } catch {
    skip(`D ${site.file}`, "读不出");
    continue;
  }
  const hits = site.forbidden.filter((rx) => rx.test(stripComments(body)));
  check(
    hits.length === 0,
    `D ★★ ${site.file} 不再有 ${site.what}`,
    hits.length ? `仍有 ${hits.map(String).join(" , ")}` : "",
  );
}

// D5 ★ 反向对照：扫描器必须**真的会红** —— 拿一个已知含兜底的字符串试一次。
//   没有这一条，上面四条在扫描器坏掉时仍然全绿。
{
  const probe = 'const x = unit?.parse_status ?? "ok";';
  const caught = SITES[0].forbidden.some((rx) => rx.test(probe));
  check(caught, "D5 ★★ 反向对照：扫描器对已知坏样本必须红（证明它活着）");
}

// ── 汇总 ──────────────────────────────────────────────────────────────
console.log("─".repeat(70));
if (fails.length) {
  console.log(`❌ ${pass} 过 · ${fails.length} 红 · ${untested.length} 未测`);
  process.exit(1);
}
if (untested.length) {
  console.log(`⚠️ ${pass} 过 · ${untested.length} 未测 —— 未测不是通过`);
  process.exit(2);
}
console.log(`✅ ${pass}/${pass} 全过`);
