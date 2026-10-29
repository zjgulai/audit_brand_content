#!/usr/bin/env node
/**
 * check_polling.mjs —— ADR-0021 · W-3 的执行点
 *
 * ## 它守的是什么
 *
 * 2026-10-27 审计：全仓 `setInterval` **0 命中**、`WebSocket`/`EventSource` 0、
 * `visibilitychange` 0 —— **队列页不会自动刷新**，审核员必须手动 F5
 * 才能看到新案件。
 *
 * 但「加上轮询」本身不是难点；难的是三条口径，缺一条就变负资产：
 *
 * | 口径 | 不做的后果 |
 * |---|---|
 * | 隐藏时**停表**（不是跳过） | 十个后台标签页 = 每 20 秒十次无用请求 |
 * | 回来时**立刻拉**（不是等周期） | 20 秒内的旧数据**看起来像新的** |
 * | 刷新**不清空**已有数据 | 列表每 20 秒白一下（`setRows(null)` 搬进轮询的后果） |
 *
 * 另外两条：
 * · 写动作期间暂停（否则刷新会冲掉未保存草稿）
 * · `paused` 变化**不许**重建 `run`（否则首次加载的 effect 重跑、列表闪空）
 *
 * ## 为什么要扫源码而不是只测纯函数
 *
 * 纯函数测的是「判定对不对」；而「三个列表页到底挂了没有」是另一件事。
 * 组件只写对、页面没挂 = 什么都没发生（§2.4「常量定义了没人用」）。
 *
 * 退出码：0 全过 / 1 有红 / 2 未测
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

// ── import 纯逻辑真身 ────────────────────────────────────────────────────
let L;
try {
  L = await import("../src/hooks/polling.logic.ts");
} catch (e) {
  skip("import polling.logic.ts", `${e.message}（需 --experimental-strip-types）`);
  process.exit(2);
}
const { shouldTick, loadPhase, onVisibilityChange, shouldSurfaceFailures } = L;

// ═══════════════════════════════════════════════ A 该不该跑
const A = [
  ["全部就绪 → 跑", shouldTick({ enabled: true, paused: false, inFlight: false, visible: true }).run === true],
  ["enabled=false → 不跑", shouldTick({ enabled: false, paused: false, inFlight: false, visible: true }).run === false],
  ["★★★ 页面隐藏 → 不跑", shouldTick({ enabled: true, paused: false, inFlight: false, visible: false }).run === false],
  ["★★ 写动作中（paused）→ 不跑", shouldTick({ enabled: true, paused: true, inFlight: false, visible: true }).run === false],
  ["★★ 上一轮未回（inFlight）→ 不跑（防重入）", shouldTick({ enabled: true, paused: false, inFlight: true, visible: true }).run === false],
];
for (const [n, c] of A) check(c, `A ${n}`);

// A6 ★★★ 四种「不跑」的理由必须各不相同 —— 否则排查时无从下手
{
  const reasons = [
    shouldTick({ enabled: false, paused: false, inFlight: false, visible: true }).reason,
    shouldTick({ enabled: true, paused: false, inFlight: false, visible: false }).reason,
    shouldTick({ enabled: true, paused: true, inFlight: false, visible: true }).reason,
    shouldTick({ enabled: true, paused: false, inFlight: true, visible: true }).reason,
  ];
  check(new Set(reasons).size === 4,
    "A6 ★★★ 四种不跑的理由互不相同（合并成一句会让人查不出是哪一条挡的）",
    reasons.join(" / "));
}

// A7 ★★ 隐藏优先于 paused：隐藏时连理由都该说 hidden
check(
  shouldTick({ enabled: true, paused: true, inFlight: false, visible: false }).reason === "hidden",
  "A7 ★★ 隐藏与暂停同时成立时，理由说 hidden（隐藏是更根本的原因）",
);

// ═══════════════════════════════════════════════ B 三态加载
const B = [
  ["首次加载 → initial", loadPhase({ loading: true, refreshing: false, first: true }) === "initial"],
  ["★ 后续刷新 → refreshing（不是 initial）", loadPhase({ loading: false, refreshing: true, first: false }) === "refreshing"],
  ["空闲 → idle", loadPhase({ loading: false, refreshing: false, first: false }) === "idle"],
  ["★★★ refreshing 不许被算成 initial（否则列表会被清空）",
    loadPhase({ loading: false, refreshing: true, first: false }) !== "initial"],
];
for (const [n, c] of B) check(c, `B ${n}`);

// B5 ★★ 首次时即使两个标志都为 true，也只报 initial（不许有中间态）
check(
  loadPhase({ loading: true, refreshing: true, first: true }) === "initial",
  "B5 ★★ 首次时即使两个标志都为 true，也只报 initial（不许有调用方猜的中间态）",
);

// ═══════════════════════════════════════════════ C 可见性
const C = [
  ["★ 隐藏 → stop-timer（不是跳过）", onVisibilityChange("hidden", true) === "stop-timer"],
  ["★★★ 可见 → fetch-now-and-restart（回来立刻拉）",
    onVisibilityChange("visible", true) === "fetch-now-and-restart"],
  ["enabled=false 时任何可见性变化都 noop", onVisibilityChange("visible", false) === "noop"],
];
for (const [n, c] of C) check(c, `C ${n}`);

// C4 ★★ 反向对照：可见时**不许**返回 noop（那等于回来不刷新）
check(onVisibilityChange("visible", true) !== "noop",
  "C4 ★★ 反向对照：可见时必须有事发生（返回 noop 就等于回来不刷新）");

// ═══════════════════════════════════════════════ D 失败提示阈值
check(shouldSurfaceFailures(0) === false, "D1 0 次失败不提示");
check(shouldSurfaceFailures(1) === false, "D2 1 次失败不提示（偶发抖动不该打扰）");
check(shouldSurfaceFailures(2) === true, "D3 ★ 连续 2 次失败才提示");

// ═══════════════════════════════════════════════ E ★★ hook 源码口径
let hookSrc;
try {
  hookSrc = fs.readFileSync(path.join(SRC, "hooks", "usePolling.ts"), "utf8");
} catch (e) {
  skip("读 usePolling.ts", String(e.message));
  hookSrc = "";
}
const stripComments = (t) =>
  t.replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n").map((l) => { const i = l.indexOf("//"); return i >= 0 ? l.slice(0, i) : l; }).join("\n");

if (hookSrc) {
  const code = stripComments(hookSrc);
  // E1 ★★★ run 的依赖里**不许**出现 paused / loader
  //   ★ 这是 W-3 里最容易踩的一条：paused 进依赖 → run 重建 →
  //     首次加载 effect 重跑 → startedRef 清零 → 列表闪空。
  const depLine = (code.match(/\n\s*\[([^\]]*)\],\s*\n\s*\);/) || [])[1] || "";
  check(!/\bpaused\b/.test(depLine),
    "E1 ★★★ run 的依赖里不含 paused（否则 paused 一变就重建、列表闪空）", `依赖=${depLine.trim()}`);
  check(!/\bloader\b/.test(depLine),
    "E2 ★★★ run 的依赖里不含 loader（同上）", `依赖=${depLine.trim()}`);
  // E3 paused / loader 必须走 ref
  check(/pausedRef\.current/.test(code), "E3 ★★ paused 通过 ref 读取（不进闭包）");
  check(/loaderRef\.current\(\)/.test(code), "E4 ★★ loader 通过 ref 调用（不进闭包）");
  // E5 可见性必须真的注册监听
  check(/addEventListener\("visibilitychange"/.test(code),
    "E5 ★★ 真的注册了 visibilitychange 监听");
  check(/removeEventListener\("visibilitychange"/.test(code),
    "E6 ★★ 卸载时移除监听（否则切页之后还在拉）");
  // E7 判定走纯函数（防两套逻辑）
  check(/shouldTick\(/.test(code) && /onVisibilityChange\(/.test(code),
    "E7 ★★ 判定走纯函数（不在这里再写一套）");
}

// ═══════════════════════════════════════════════ F ★★★ 三个列表页真的挂了
//
// ★ 这一组是「组件写对了但页面没挂」的守卫 ——
//   那种情况下功能等于没做，而纯函数测试会全绿（§2.4 那个病）。
const LIST_PAGES = ["QueuePage.tsx", "InboxPage.tsx", "ReleasePage.tsx"];
for (const name of LIST_PAGES) {
  const p = path.join(SRC, "pages", name);
  let src;
  try { src = fs.readFileSync(p, "utf8"); } catch { skip(`F ${name}`, "读不出"); continue; }
  check(/usePolling\(/.test(src), `F ★★★ ${name} 挂上了 usePolling`);
}

// F5 ★★★ 挂轮询的页面，**清空数据的 effect 依赖里不许有 `current`**
//
//   2026-10-30 实测事故：`QueuePage` 的清空 effect 依赖 `[current, devEnabled,
//   sessionEpoch]`。而 `current` 在 `/api/v1/me` 返回时会从 null 变成对象 ——
//   那是**首屏加载过程中必然发生的一次变化**，不是「换了身份」。
//   于是清空 effect 会在取数请求还在飞的时候跑 `setRows(null)`，
//   谁先跑取决于两个请求的返回顺序 —— **竞态**。
//
//   实测表现：首屏永远停在 `全部待办（0）` + 4 条骨架屏，
//   而 20 秒后轮询的 tick 能把数据显示出来（那时 current 已稳定）。
//   「等一会儿就好了」是竞态最典型的症状。
//
//   ★ 判据只针对 **useEffect** 的依赖数组：
//     `useCallback(..., [current, devEnabled])` 是 loader 的依赖，**允许**有
//     current —— loader 重建只会更新 `loaderRef.current`，不会让 effect 重跑。
//     第一版写成「所有 `}, [...] )` 都查」，于是把 useCallback 一起判红，
//     两条都误报（那两条本来是对的）。**误报比漏报更糟**：
//     它会让读报告的人开始不信这份报告。
{
  const PAGES_WITH_CLEAR = ["QueuePage.tsx", "InboxPage.tsx"];
  for (const name of PAGES_WITH_CLEAR) {
    const p = path.join(SRC, "pages", name);
    let src;
    try { src = fs.readFileSync(p, "utf8"); } catch { skip(`F5 ${name}`, "读不出"); continue; }

    // ★ 注释不算代码。今天这个坑踩了三次（check_browser_scope J1a、
    //   verify_acceptance_trigger、这里）。
    const code = src
      .split("\n")
      .map((line) => line.replace(/\/\/.*$/, ""))
      .join("\n");

    // 只取 `useEffect(` 到它闭合的 `}, [...])` —— 用配对扫描而不是全局正则，
    // 否则会跨过 useCallback 的边界。
    const offenders = [];
    const effRe = /useEffect\s*\(/g;
    let e;
    while ((e = effRe.exec(code)) !== null) {
      // 从 useEffect( 起找它自己的依赖数组：向前扫到匹配的 `}, [ ... ] )`
      const tail = code.slice(e.index, e.index + 4000);
      const m = tail.match(/\n\s*\}, \s*\[([^\]]*)\]\s*\)/);
      if (!m) continue;
      const deps = m[1];
      if (/\bcurrent\b/.test(deps)) {
        offenders.push(deps.replace(/\s+/g, " ").trim());
      }
    }
    check(
      offenders.length === 0,
      `F5 ★★★ ${name} 的 useEffect 依赖里**不许有 current**（首屏 /me 返回会让它变，与取数形成竞态）`,
      offenders.length ? `违规依赖：[ ${offenders.join(" ] [ ")} ]` : "",
    );
  }
}

// F4 ★★★ 详情页**不许**挂轮询（有未保存草稿，自动刷新会冲掉）
{
  const p = path.join(SRC, "pages", "CaseDetailPage.tsx");
  let src = "";
  try { src = fs.readFileSync(p, "utf8"); } catch { /* 不存在则跳过 */ }
  if (src) {
    check(!/usePolling\(/.test(src),
      "F4 ★★★ CaseDetailPage **不许**挂轮询（有未保存草稿，刷新会冲掉）——这是有意的排除");
  }
}

// ═══════════════════════════════════════════════ G 反向对照：扫描器活着
{
  const probe = "const x = usePolling(load);";
  check(/usePolling\(/.test(probe), "G1 ★★ 反向对照：扫描器能认得 usePolling（否则 F 组恒红）");
  check(/usePolling\(/.test("  const p = usePolling(loader, { enabled });"),
    "G2 ★★ 反向对照：带参数的调用也要认得");
  check(!/usePolling\(/.test("const x = usePollingLike;"),
    "G3 ★★ 反向对照：相似名字不许误报");
}

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
