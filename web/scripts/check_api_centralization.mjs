#!/usr/bin/env node
/**
 * check_api_centralization.mjs —— ADR-0021 · W-1 的执行点
 *
 * ## 它守的是什么
 *
 * 2026-10-27 审计：`pages/` 下有 **18 处裸 `request()`**，与 `api/client.ts`
 * 的封装并存。同一个接口在两处拼 URL，一处写对一处写错就 404，而没有东西会发现。
 *
 * 这不是「风格不统一」：
 * · `ReleasePage` 那处是**裸 `fetch`**，路径写成 `/auth/reauth/start`
 *   （后端是 `/api/v1/reauth/start`），期望 JSON（后端返 302），且不带 CSRF。
 *   三个缺陷叠在一起，而症状是「未开启此功能」—— 读起来像功能没做。
 *
 * ## 分组
 *
 * | 组 | 验什么 |
 * |---|---|
 * | A | `pages/` 下裸 `request(` / 裸 `fetch(` 出现次数为 0 |
 * | B | `api/` 下确实有这些方法（否则 A 是把调用删了而不是搬走） |
 * | C ★ | 反向对照：扫描器对坏样本必须红 |
 * | D ★★ | 路径只在一处出现：每个后端路径在 `pages/` 里出现次数为 0 |
 *
 * ## 为什么 A 不能只查 `request(`
 *
 * 因为 `ReleasePage` 那处的病是**裸 fetch**，不是 `request`。
 * 只查 `request(` 会让最严重的那一处一直绿。
 *
 * 退出码：0 全过 / 1 有红 / 2 未测
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, "..");
const SRC = path.join(WEB, "src");
const PAGES = path.join(SRC, "pages");
const API = path.join(SRC, "api");

let pass = 0;
const fails = [];
const untested = [];

const ok = (n) => { pass += 1; console.log(`PASS: ${n}`); };
const bad = (n, d = "") => { fails.push(n); console.log(`FAIL: ${n}${d ? `  ${d}` : ""}`); };
const skip = (n, d = "") => { untested.push(n); console.log(`UNTESTED: ${n}${d ? `  ${d}` : ""}`); };
const check = (c, n, d = "") => (c ? ok(n) : bad(n, d));

// ── 剥注释 ──────────────────────────────────────────────────────────────
//
// ★ 必须剥：本次改动的每一个文件里，我都在注释里写了「原先是 request(...)」
//   这类说明。不剥就会把解释文字当成违规代码 —— 这个坑今天已经踩过一次
//   （check_field_state.mjs 的 D 组），同一条读法：注释不算代码。
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

function readAll(dir) {
  const out = [];
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) out.push(...readAll(p));
    else if (/\.(ts|tsx)$/.test(name)) out.push([name, fs.readFileSync(p, "utf8")]);
  }
  return out;
}

let pageFiles;
let apiFiles;
try {
  pageFiles = readAll(PAGES);
  apiFiles = readAll(API);
} catch (e) {
  skip("读源码", String(e.message));
  process.exit(2);
}

// ═══════════════════════════════════════════════ A 裸调用为 0
//
// 口径要精确，否则会误报：
// · `request<...>(` 与 `request(` 都算
// · `fetch(` 算（ReleasePage 那处就是它）
// · 但 `requestGeneration.current` **不算** —— 那是 CaseDetailPage 的一个
//   useRef 变量，名字里恰好含 "request"。实测它曾让计数从 18 变成 22。
const BARE_REQUEST = /\brequest\s*(?:<[^>]*>)?\s*\(/g;
const BARE_FETCH = /(?<![.\w])fetch\s*\(/g;
// `request` 后面直接跟 `.` 是属性访问（requestGeneration.current / api.request）
const BARE_REQUEST_ATTR = /\brequest\s*\./g;

function scanBare(files) {
  const hits = [];
  for (const [name, src] of files) {
    const code = stripComments(src);
    for (const rx of [BARE_REQUEST, BARE_FETCH]) {
      rx.lastIndex = 0;
      for (const m of code.matchAll(rx)) {
        // 排除 `requestGeneration.current` 这类：匹配到的位置前面若不是
        // 标识符边界后的独立 `request`，就不算
        const at = m.index ?? 0;
        const before = code.slice(Math.max(0, at - 3), at);
        if (/[.\w]/.test(before.slice(-1))) continue;
        const line = code.slice(0, at).split("\n").length;
        hits.push(`${name}:${line}  ${m[0].trim()}`);
      }
    }
  }
  return hits;
}

/**
 * 允许存在的裸 `fetch` —— **逐个点名**，不许模糊放行。
 *
 * 加一条就要改这里，于是「又出现一个绕过封装的调用」会被逼着做一次决定
 * （与 `verify_openapi_spec.py` 的 UNCLAIMED_ALLOWED 同一条做法）。
 *
 * 为什么 `ReleasePage` 的 reauth 必须是裸 fetch：
 * · `request()` 会**强制 `res.json()`**，而这个端点回的是 **302**
 *   —— 走封装必然在解析那步抛，又被 catch 成「未开启」。
 * · 它要 `redirect: "manual"` 才能把 302 拿在手里而不跟随跨域跳转。
 * · 它必须带 CSRF 头（该端点不在 gate 豁免名单里）。
 * 三条都做不到用 `request()` 表达。**这是例外，不是先例。**
 */
const ALLOWED_BARE_FETCH = {
  "ReleasePage.tsx": {
    max: 1,
    why: "reauth/start 返回 302 且要 redirect:manual + CSRF 头，request() 表达不了",
  },
};

const bare = scanBare(pageFiles);
const offenders = [];
for (const [name, hit] of bare.map((h) => [h.split(":")[0], h])) {
  const allow = ALLOWED_BARE_FETCH[name];
  if (allow && !offenders.some((o) => o.startsWith(name))) {
    // 该文件的第一处已登记；多于 max 才算违规（下面单独断言）
    if (allow.max >= 1) continue;
  }
  offenders.push(hit);
}

// 逐文件核「登记了几处、实际几处」
for (const [name, allow] of Object.entries(ALLOWED_BARE_FETCH)) {
  const n = bare.filter((h) => h.startsWith(name)).length;
  check(n <= allow.max,
    `A ★★ ${name} 的裸 fetch 数不超过登记值 ${allow.max}（实际 ${n}）——${allow.why}`);
}

check(
  offenders.length === 0,
  "A ★★★ pages/ 下没有**未登记**的裸 request( / fetch( 调用",
  offenders.length ? `仍有 ${offenders.length} 处：${offenders.slice(0, 5).join(" | ")}` : "",
);

// A2 反向对照：扫描器对已知坏样本必须命中
{
  const probe = 'const x = await request<Foo>("/cases");';
  BARE_REQUEST.lastIndex = 0;
  check(BARE_REQUEST.test(probe), "A2 ★★ 反向对照：裸 request 样本必须被抓到（证明扫描器活着）");
}
{
  const probe = 'const r = await fetch("/api/v1/reauth/start");';
  BARE_FETCH.lastIndex = 0;
  check(BARE_FETCH.test(probe), "A3 ★★ 反向对照：裸 fetch 样本必须被抓到");
}
{
  // ★ 这一条防误报：requestGeneration.current 不该算裸调用
  const probe = 'if (generation !== requestGeneration.current) return null;';
  BARE_REQUEST.lastIndex = 0;
  const matched = [...probe.matchAll(BARE_REQUEST)];
  check(matched.length === 0,
    "A4 ★★ 反向对照：requestGeneration.current **不许**被算成裸调用（否则计数虚高）",
    matched.map((m) => m[0]).join(","));
}

// ═══════════════════════════════════════════════ B api/ 下确实收下了
const apiSrc = apiFiles.map(([, s]) => s).join("\n");
const REQUIRED = [
  ["listAppeals", "申诉列表"],
  ["createAppeal", "发起申诉"],
  ["migrateAppeal", "确认迁移"],
  ["withdrawAppeal", "撤销申诉"],
  ["listRules", "规则库"],
  ["listControlPoints", "控制点"],
  ["listRouting", "处置路由"],
  ["markNotification", "通知已读/确认"],
  ["resignReport", "重签报告"],
  ["listGrants", "授权台账"],
  ["proposeGrant", "提授权提案"],
  ["transitionGrant", "授权执行/审批"],
  ["listSessions", "会话审计"],
  ["takedownApi", "下线任务"],
  ["submit:", "提交送审"],
];
for (const [needle, human] of REQUIRED) {
  check(apiSrc.includes(needle), `B api/ 下有 ${human}（${needle}）`);
}

// B2 ★ 反向对照：不存在的名字不该被找到（否则 B 那条是恒真）
check(!apiSrc.includes("noSuchMethodAnywhere"),
  "B2 ★ 反向对照：不存在的名字不许被找到（否则上面全是恒真）");

// ═══════════════════════════════════════════════ D 路径只在一处出现
//
// ★ 这条才是根治：即使有人又在页面里写了裸调用，只要路径不在页面里出现，
//   他就得先把路径写一遍 —— 而那会在这里红。
//
// ★★ 第一版直接 `src.includes(p)`，结果 `/appeals` 与 `/reports/` 报了红 ——
//   而它们是 **前端路由**（`<Link to="/appeals">`），不是 API 路径。
//   把两者混在一起查，得到的是一个会误报的判据；而误报的判据
//   会让人开始不看报告（AGENTS.md §2.1.1）。
//
//   所以只查**调用形状**：字符串字面量紧跟在 request/fetch 之后，
//   或者出现在 `reviewApi.xxx(...)` 的参数里时才算 API 路径。
//   前端路由（`to=` / `<Link>` / `navigate(`）一律豁免。
const BACKEND_PATHS = [
  "/admin/signer-grants",
  "/admin/takedown-grants",
  "/admin/grants/",
  "/admin/sessions",
  "/takedown-tasks",
  "/appeals",
  "/notifications/",
  "/reports/",
  "/control-points",
  "/routing",
];

/** 这个路径在源码里是**作为 API 调用参数**出现的吗？ */
function usedAsApiPath(code, p) {
  // ① 模板字符串或字符串字面量，前面 40 字符内出现 request/fetch/api 调用
  const idx = [];
  let from = 0;
  for (;;) {
    const i = code.indexOf(p, from);
    if (i < 0) break;
    idx.push(i);
    from = i + p.length;
  }
  for (const i of idx) {
    const lineStart = code.lastIndexOf("\n", i) + 1;
    const line = code.slice(lineStart, code.indexOf("\n", i) < 0 ? code.length : code.indexOf("\n", i));
    // 前端路由：同一行有 to= / <Link / navigate( / href= 就是路由，不是 API
    if (/\bto=|<Link|navigate\(|href=/.test(line)) continue;
    // 注释行（再剥一次，防块注释残留）
    if (line.trimStart().startsWith("*") || line.trimStart().startsWith("<!--")) continue;
    return true;
  }
  return false;
}

const pageBlob = pageFiles.map(([n, s]) => [n, stripComments(s)]);
for (const p of BACKEND_PATHS) {
  const hits = pageBlob.filter(([, s]) => usedAsApiPath(s, p)).map(([n]) => n);
  check(hits.length === 0,
    `D ★★ 路径 ${p} 不作为 API 路径出现在 pages/（只在 api/ 拼）`,
    hits.length ? `出现在：${hits.join(", ")}` : "");
}

// D2 ★★ 反向对照：前端路由必须**不**被判成 API 路径
check(
  !usedAsApiPath('<Link to="/reports/x">查看</Link>', "/reports/"),
  "D2 ★★★ 反向对照：前端路由 /reports/ 不许被判成 API 路径（否则 D 组会误报）",
);
check(
  usedAsApiPath('await request(`/reports/${id}/resign`);', "/reports/"),
  "D3 ★★★ 反向对照：真 API 调用里的 /reports/ 必须被抓到",
);

// ═══════════════════════════════════════════════ 汇总
console.log("─".repeat(72));
if (fails.length) {
  console.log(`❌ ${pass} 过 · ${fails.length} 红 · ${untested.length} 未测`);
  process.exit(1);
}
if (untested.length) {
  console.log(`⚠️ ${pass} 过 · ${untested.length} 未测 —— 未测不是通过`);
  process.exit(2);
}
console.log(`✅ ${pass}/${pass} 全过`);
