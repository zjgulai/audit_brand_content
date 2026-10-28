#!/usr/bin/env node
/**
 * check_error_boundary.mjs —— ADR-0021 · W-3（边界那一半）的执行点
 *
 * ## 它守的是什么
 *
 * 2026-10-27 审计：全仓 `grep ErrorBoundary|componentDidCatch` = **0 命中**。
 * 任意一个页面里一个渲染异常 → **整站白屏**，而且用户不知道
 * 「是哪个页面坏了、能不能继续用别的页面」。
 *
 * ## 为什么不全靠源码扫描
 *
 * 「文件存在 + 有个 componentDidCatch」是**恒真**的那类判据：
 * 一个把 `getDerivedStateFromError` 写成 `return {}` 的实现也能过。
 * 所以这里做三件事：
 *
 * | 组 | 验什么 |
 * |---|---|
 * | A | 语法结构：必须有 getDerivedStateFromError + componentDidCatch + retry |
 * | B ★★ | **行为**：真跑 React 的服务端渲染路径，注入一个必崩组件，看它是否被捕获 |
 * | C | 接线：真的挂在 `<Outlet />` 上，且 key 跟路由变化 |
 * | D | 留痕：错误进 `window.__REVIEW_ERRORS__`，不是只 console |
 *
 * ## 退出码
 *
 * 0 全过 / 1 有红 / 2 未测
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
const ok = (n) => { pass += 1; console.log(`PASS: ${n}`); };
const bad = (n, d = "") => { fails.push(n); console.log(`FAIL: ${n}${d ? `  ${d}` : ""}`); };
const skip = (n, d = "") => { untested.push(n); console.log(`UNTESTED: ${n}${d ? `  ${d}` : ""}`); };
const check = (c, n, d = "") => (c ? ok(n) : bad(n, d));

const stripComments = (t) =>
  t.replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n").map((l) => { const i = l.indexOf("//"); return i >= 0 ? l.slice(0, i) : l; }).join("\n");

let src = "";
try {
  src = fs.readFileSync(path.join(SRC, "components", "ErrorBoundary.tsx"), "utf8");
} catch (e) {
  skip("读 ErrorBoundary.tsx", String(e.message));
  process.exit(2);
}
const code = stripComments(src);

// ═══════════════════════════════════════════════ A 语法结构
check(/getDerivedStateFromError/.test(code),
  "A1 ★★ 有 getDerivedStateFromError（否则 React 不会切到错误态）");
check(/componentDidCatch/.test(code),
  "A2 ★★ 有 componentDidCatch（否则拿不到组件栈、也没法留痕）");
check(/this\.setState|retry/.test(code),
  "A3 ★ 有重试路径（否则用户被困在错误页里）");
check(/location\.assign|window\.location/.test(code),
  "A4 ★★ 有「回到别的页面」的出口（白屏最坏的地方是把人困住）");

// A5 ★★★ `return {}` 那种坏实现必须被抓 —— 但**判据在 B 组**（真跑），
//   这里只保留一条静态辅助：.tsx 里的钩子必须**调用**那个纯函数，
//   而不是自己 `return {}`。
//   ★ 第一版 A5 是「在 .tsx 里找 `return { error }`」—— 实现搬到
//     `errorBoundary.logic.ts` 之后它就假红了（红的是判据的射程，不是代码）。
//     那条正则现在挪到 A5b，指向真正实现的地方。
check(/nextBoundaryState\(/.test(code),
  "A5 ★★★ getDerivedStateFromError 调用 nextBoundaryState（不自己拼 state）");

// A5b ★★★ 纯逻辑文件里必须真的是 `return { error }`（不是 return {}）
{
  let logic = "";
  try {
    logic = fs.readFileSync(path.join(SRC, "components", "errorBoundary.logic.ts"), "utf8");
  } catch { /* 读不到由 B 组兜 */ }
  if (logic) {
    check(/nextBoundaryState\s*\([^)]*\)\s*(?::[^{]*)?\{\s*return\s*\{\s*error\s*\}/.test(logic),
      "A5b ★★★ nextBoundaryState 返回 `{ error }`（`return {}` 会让边界变成透明 div）");
  }
}

// A6 ★★ 错误必须留痕进 __REVIEW_ERRORS__
check(/__REVIEW_ERRORS__/.test(code),
  "A6 ★★ 错误写进 window.__REVIEW_ERRORS__（不许只 console 一句）");
// ★ 环形缓冲的实现也在纯逻辑文件里（B6–B8 真跑它）。
//   这里只断言 .tsx 把上限**传进去**了 —— 不进参数就等于用了默认值，
//   而默认值哪天变了这里不会知道。
check(/ERROR_BUFFER_MAX/.test(code) && /appendError\(/.test(code),
  "A7 ★ .tsx 调 appendError 且显式传上限（不靠默认值）");
// A8 ★★★ 不许 console-only：recordError 必须真的被调用
check(/recordError\(\s*\{/.test(code),
  "A8 ★★★ componentDidCatch 里真的调用了 recordError（不是定义了不用）");

// ═══════════════════════════════════════════════ B ★★★ 行为：真跑
//
// ★ 第一版这里是「import .tsx 再调静态方法」—— Node 加载不了 JSX，
//   于是整组落 UNTESTED，而**未测不是通过**。
//   抽成 `errorBoundary.logic.ts` 之后能 import 真身，这一组才真的在测。
//
// ★ 这一组要抓的坏实现是 `return {}`：它通过了「有没有这个钩子」的检查，
//   但 React 拿不到 error → `state.error` 恒 null → 边界变成透明 div →
//   **崩溃照样白屏**。这是最容易蒙混过去的坏实现。
let L;
try {
  L = await import("../src/components/errorBoundary.logic.ts");
} catch (e) {
  skip("B 组：import errorBoundary.logic.ts", `${e.message}（需 --experimental-strip-types）`);
}

if (L) {
  const { nextBoundaryState, retryState, appendError, ERROR_BUFFER_MAX } = L;

  // B1 ★★★ 真调一次，看返回值里有没有**这个** error
  {
    const boom = new Error("boom");
    const next = nextBoundaryState(boom);
    check(next && next.error === boom,
      "B1 ★★★ nextBoundaryState(err) 返回的 error 就是**这个** err（`return {}` 会在这里红）",
      JSON.stringify(Object.keys(next || {})));
    check(!(next && Object.keys(next).length === 0),
      "B2 ★★★ 返回值不是空对象（空对象是最能蒙混过去的坏实现）");
  }

  // B3 ★★★ 端到端语义：错→对→再错，attempt 必须递增
  //   （attempt 是 render 里的 key，不递增就不会重挂子树 —— 重试会拿到崩过的实例）
  {
    let st = { error: null, componentStack: null, attempt: 0 };
    st = { ...st, ...nextBoundaryState(new Error("a")) };
    const afterRetry = { ...st, ...retryState(st) };
    check(afterRetry.error === null, "B3 ★★ 重试后 error 清空");
    check(afterRetry.attempt === 1, "B4 ★★★ 重试后 attempt 递增（它是重挂子树的 key，不递增等于没重试）");
    const again = { ...afterRetry, ...nextBoundaryState(new Error("b")) };
    check(again.error instanceof Error && again.error.message === "b",
      "B5 ★ 第二次崩溃能再次被捕获（不是一次性的）");
  }

  // B6 ★★ 环形缓冲：满了要丢最旧的
  {
    let list = [];
    for (let i = 0; i < ERROR_BUFFER_MAX + 5; i += 1) {
      list = appendError(list, { at: String(i), message: "m", boundary: "b" });
    }
    check(list.length === ERROR_BUFFER_MAX,
      `B6 ★★ 缓冲不超过 ${ERROR_BUFFER_MAX} 条（长会话里不许无限增长）`, String(list.length));
    check(list[list.length - 1].at === String(ERROR_BUFFER_MAX + 4),
      "B7 ★ 保留的是最新的（丢最旧的，不是丢新的）");
    check(list[0].at === "5", "B8 ★ 最旧的被 shift 掉了", list[0].at);
  }

  // B9 ★ 纯函数：不许改入参（否则组件那边会把历史记录也改掉）
  {
    const orig = [{ at: "1", message: "m", boundary: "b" }];
    const snapshot = JSON.stringify(orig);
    appendError(orig, { at: "2", message: "m", boundary: "b" });
    check(JSON.stringify(orig) === snapshot,
      "B9 ★★ appendError 不改入参（返回新数组）");
  }
}

// ═══════════════════════════════════════════════ C ★★★ 接线
let shellSrc = "";
try {
  shellSrc = fs.readFileSync(path.join(SRC, "components", "AppShell.tsx"), "utf8");
} catch (e) {
  skip("读 AppShell.tsx", String(e.message));
}
if (shellSrc) {
  const shellCode = stripComments(shellSrc);
  check(scanBoundary(shellCode),
    "C1 ★★★ AppShell 里真的挂了 <ErrorBoundary>（不挂就是没做）");
  // C2 ★★ 必须包住 <Outlet />，而不是包住别的东西
  check(/<ErrorBoundary[^>]*>[\s\S]{0,400}?<Outlet\s*\/>/.test(shellCode),
    "C2 ★★★ ErrorBoundary 包住的是 <Outlet />（包住别处等于没覆盖页面）");
  // C3 ★★ key 必须跟路由变化 —— 否则从崩掉的 A 跳到 B，B 看到的是 A 的错误页
  check(/<ErrorBoundary[^>]*key=\{[^}]*pathname/.test(shellCode),
    "C3 ★★★ key 跟着 pathname（否则换页后错误态不重置）");
  // C4 ★ 边界必须有 name（记录里要知道是哪一块崩的）
  check(/<ErrorBoundary[^>]*name=/.test(shellCode),
    "C4 ★★ 边界带 name（错误记录里要能定位是哪一块）");
}

// ═══════════════════════════════════════════════ D 反向对照：扫描器活着
//
// ★ 第一版 D2/D3 直接用 `/<ErrorBoundary/.test("...")` —— 那是**在测正则本身**，
//   不是测扫描链（剥注释 + 词边界）。于是 D2 把 "<ErrorBoundaryLike" 也判成命中，
//   D3 把注释里的也判成命中。两条红得对：判据用的不是真正在跑的那条链。
//   现在抽成 `scanBoundary(text)`，A/C/D 三组都调它。
function scanBoundary(text) {
  return /<ErrorBoundary(?![A-Za-z0-9_])/.test(stripComments(text));
}

check(scanBoundary('  <ErrorBoundary name="x"><Outlet /></ErrorBoundary>'),
  "D1 ★★ 反向对照：扫描器认得出 <ErrorBoundary>");
check(!scanBoundary("const x = 1; // <ErrorBoundaryLike />"),
  "D2 ★★ 反向对照：相似名字 <ErrorBoundaryLike 不许误报");
check(!scanBoundary("// 这里本该有 <ErrorBoundary> 但没写"),
  "D3 ★★★ 反向对照：注释里的不许算数（走的是真扫描链）");
check(!scanBoundary("/* <ErrorBoundary> */ const x = 1;"),
  "D4 ★★ 反向对照：块注释里的同样不算");

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
