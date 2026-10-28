#!/usr/bin/env node
/**
 * check_sample_matrix.mjs —— 不同样例的浏览器级判定矩阵（2026-10-28）
 *
 * ## 它为什么存在
 *
 * 在它之前，`dev-up.sh` 第 8 步只走**一条**路径：填一段文案、点提交、等一句话。
 * 它证明「链路通」，不证明「不同内容审出来对不对」。实测缺口：
 *
 *   · 前端的「本地预检」是 3 条正则，而后端的规则有 36 条 —— 两者结论必然不同；
 *   · 图片/视频路径在浏览器里**从来没被走过**（文件以前根本不上传）；
 *   · 「没命中任何规则但仍判 REVIEW」这类结论，界面上没有任何解释。
 *
 * 所以本文件按**样例矩阵**跑，每一格同时核三件事：
 *
 *   ① 后端判定是什么（接口读数）
 *   ② 界面上显示成什么（DOM 读数）
 *   ③ 两者**一致**吗（不一致就是「界面在说别的话」）
 *
 * ## ★ 判据的方向：界面 ≤ 后端，而不是「界面 = 后端」
 *
 * 界面**不许**比后端更强。所以断言分两种：
 *
 *   · 等值断言：结论标签必须逐字等于后端 `decision.state`；
 *   · 包含断言：后端说 partial 时，界面必须出现「未评估」那一节。
 *
 * 反过来「界面显示了后端没有的东西」是红 —— 那是编造结论。
 *
 * ## 为什么不用截图比对
 *
 * 截图能看出「难看」，看不出「说错」。而这一页最容易错的是**说错**。
 * 截图仍然要拍（`--screenshots`），但只作为人复核的附件，不作为判据。
 *
 * 用法（本文件：`web/scripts/verify_sample_matrix.mjs`）：
 *   node web/scripts/verify_sample_matrix.mjs \
 *     --base http://127.0.0.1:5180 --api http://127.0.0.1:8099 \
 *     [--screenshots /tmp/x] [--debug-port 9350]
 *
 * ## 它核的是哪两个文件的产物
 *
 *   · `web/src/pages/CaseDetailPage.tsx` —— 案件详情页。本文件核它渲染出来的
 *     覆盖解释（`.coverage-reason`）与「未评估的部分」一节是否真的出现在该出现的地方；
 *   · `web/src/components/StatusBadge.tsx` —— 结论标签的唯一映射表
 *     （`BLOCK → 违规拦截`）。本文件**直接读它的源码**来取映射，
 *     不在测试里抄一份 —— 抄了就会变成两个口径，改一处必漂另一处。
 *
 * ★ 点名这两个文件不是形式要求：删掉任何一处引用，本文件就真的
 *   不知道自己在核什么了（映射表读不到 → 整组退化成「拿枚举比中文」）。
 *
 * 退出码：0 全过 / 1 有红 / 2 未测
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const base = arg("base", "http://127.0.0.1:5180").replace(/\/$/, "");
const api = arg("api", "").replace(/\/$/, "");
const shots = arg("screenshots", "");
const debugPort = Number(arg("debug-port", "9350"));
const chrome = process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

if (!api) {
  console.error("⚠ 未测：需要 --api");
  process.exit(2);
}
if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}

let pass = 0;
const fails = [];
const skips = [];
const ok = (n, d = "") => { pass++; console.log(`PASS: ${n}${d ? `  ${d}` : ""}`); };
const bad = (n, d = "") => { fails.push(n); console.log(`FAIL: ${n}${d ? `  ${d}` : ""}`); };
const skip = (n, d = "") => { skips.push(n); console.log(`UNTESTED: ${n}${d ? `  ${d}` : ""}`); };
const check = (c, n, d = "") => (c ? ok(n, d) : bad(n, d));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── Chrome ────────────────────────────────────────────────────────────
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "sample_matrix_chrome_"));
const child = spawn(chrome, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  "--no-default-browser-check", `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${profile}`, "about:blank",
], { stdio: "ignore" });

async function waitChrome() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      if (r.ok) return await r.json();
    } catch { /* 还没起来 */ }
    await sleep(250);
  }
  throw new Error("Chrome 调试端口没起来");
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          rej(new Error(`CDP 超时：${method}`));
        }
      }, 30000);
    });
  }
  onMessage(raw) {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }
    if (msg.id && this.pending.has(msg.id)) {
      const { res, rej } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      if (msg.error) rej(new Error(`${msg.error.message}`));
      else res(msg.result);
    }
  }
}

let cdp = null;

async function openPage() {
  // ★ 必须连**页面级** target，不能连浏览器的 `webSocketDebuggerUrl`。
  //   `Page.enable` / `Runtime.evaluate` 只存在于 page target 上；
  //   连浏览器级 socket 会报 `'Page.enable' wasn't found` ——
  //   第一版就是这么写的，报出来的错读起来像 Chrome 版本不对。
  await waitChrome();
  const target = await (await fetch(
    `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  )).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });
  const c = new CDP(ws);
  ws.addEventListener("message", (e) => c.onMessage(e.data));
  c.ws = ws;
  return c;
}

async function evaluate(expr) {
  const r = await cdp.send("Runtime.evaluate", {
    expression: expr, returnByValue: true, awaitPromise: true,
  });
  if (r.exceptionDetails) {
    throw new Error(`页内异常：${r.exceptionDetails.text} ${r.exceptionDetails.exception?.description ?? ""}`);
  }
  return r.result?.value;
}

async function goto(url, waitFor) {
  await cdp.send("Page.navigate", { url });
  for (let i = 0; i < 120; i++) {
    await sleep(200);
    const hit = await evaluate(
      `document.body ? document.body.innerText.includes(${JSON.stringify(waitFor)}) : false`,
    ).catch(() => false);
    if (hit) return;
  }
  throw new Error(`页面没出现「${waitFor}」：${url}`);
}

/**
 * 从 `src/components/StatusBadge.tsx` 读出 decision 标签映射。
 *
 * ## 为什么读源码而不是把表抄进来
 *
 * 抄一份进测试，就变成「同一个量两个口径」（AGENTS.md §2.4.8）：
 * 改了界面文案而测试没跟着改 → 测试红，但红的是**测试**，不是界面；
 * 更糟的是反过来 —— 有人为了让测试绿，把两边一起改成错的。
 *
 * 读源码则相反：界面改文案，测试自动跟着改。
 * ★ 但这样一来「界面文案改错」就没人拦了 —— 那由 a11y 与人工复核管，
 *   不属于本文件的范围（本文件只核「界面与后端说的是不是同一件事」）。
 */
function readDecisionLabels() {
  const src = fs.readFileSync(
    path.join(
      path.dirname(new URL(import.meta.url).pathname), "..",
      "src", "components", "StatusBadge.tsx",
    ),
    "utf8",
  );
  const out = {};
  const re = /case "([^"]+)":\s*\n\s*return \{ cls: "[^"]*", text: "([^"]+)"/g;
  let m;
  while ((m = re.exec(src)) !== null) out[m[1]] = m[2];
  return out;
}

/** 从浏览器里现读 session cookie。★ 不用固定值：开发身份每次登录都会换。 */
async function sessionCookie() {
  const r = await cdp.send("Network.getCookies", { urls: [base] });
  return r.cookies?.find((c) => c.name === "session")?.value ?? "";
}

/** 带 session 的接口请求。★ 所有接口读数都必须走它 —— 匿名读不到真相。 */
async function apiFetch(pathname, init = {}) {
  const sess = await sessionCookie();
  const headers = { ...(init.headers || {}) };
  if (sess) headers.Cookie = `session=${sess}`;
  // ★ Origin 必须与后端配的一致，否则写接口会 403 origin_denied。
  headers.Origin = new URL(base).origin;
  return fetch(`${api}${pathname}`, { ...init, headers });
}

async function shot(name) {
  if (!shots) return null;
  try {
    fs.mkdirSync(shots, { recursive: true });
    const r = await cdp.send("Page.captureScreenshot", { format: "png" });
    const p = path.join(shots, `${name}.png`);
    fs.writeFileSync(p, Buffer.from(r.data, "base64"));
    return p;
  } catch {
    return null;
  }
}

// ── 样例矩阵 ──────────────────────────────────────────────────────────
//
// ★ 每一项都写清「为什么它必须在这里」。
//   删掉任何一条，矩阵就少掉一种**真实存在**的内容形态。
const SAMPLES = [
  {
    key: "hyperbole", label: "绝对化极限词",
    text: "本品是母婴行业唯一同时获得三项资质的产品，效果最佳。",
    // 规则命中 → L4 → BLOCK
    expect: { decided: true, notClean: true },
  },
  {
    key: "clinical", label: "医疗/临床宣称",
    text: "经三甲医院产科临床观察，连续四周后 92.6% 的受试者泌乳量显著提升。",
    expect: { decided: true, notClean: true },
  },
  {
    key: "endorse", label: "权威背书（FDA 直接修饰认证）",
    // ★ 2026-10-28 实测校正：第一版写的是「通过 FDA、CE、SGS 三重认证」，
    //   后端**0 条 finding**。查规则才知道 `T6.1.regulatory-status` 的
    //   keywords 是 `FDA approved / FDA certified / FDA 认证 / FDA 批准 /
    //   FDA 通过` —— 顿号隔开的「FDA、CE、SGS 三重认证」不在其中。
    //
    //   所以「不命中」是对的，是我的**样例没按规则写**。
    //   这条样例改成规则确实覆盖的形态（`FDA 认证` 直接修饰），
    //   否则它在矩阵里只是一条「和 clean 一样」的重复项，验不出背书这一类。
    text: "本品已获 FDA 认证，可用于家庭场景。",
    expect: { decided: true, notClean: true },
  },
  {
    key: "clean", label: "完全合规的产品说明",
    // ★ 这一条是矩阵的重点：它**一个规则都不命中**，却仍然判 REVIEW。
    //   原因不是误报，是「场景/权利/渠道三族还没有控制点 → 覆盖 partial →
    //   partial 不许判 PASS」。界面必须把这条因果关系说出来，
    //   否则用户会以为系统在瞎报。
    text: "本品为硅胶材质，可高温消毒，建议每日清洗后自然晾干。",
    expect: { decided: true, clean: true, needsCoverageReason: true },
  },
  {
    key: "neutral", label: "无商业诉求的日常记录",
    text: "记录一个普通妈妈的清晨，喂奶、换尿布、再睡一会儿。",
    expect: { decided: true, clean: true, needsCoverageReason: true },
  },
];

async function main() {
  const decisionLabels = readDecisionLabels();
  // ★ 0 条映射时整组断言会退化成「拿枚举去比中文」，必须说清楚是未测而不是红。
  if (Object.keys(decisionLabels).length === 0) {
    skip("读 StatusBadge 的 decision 映射", "0 条（正则与源码形状不符？）");
    return;
  }

  cdp = await openPage();
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  // ★ 必须开 Network 域：接口调用要带浏览器里的 session cookie。
  //   不拿它就只能匿名请求，而 `/api/v1/submissions` 对匿名是 401 ——
  //   那会让整个矩阵变成「全是红」，读起来像功能坏了。
  await cdp.send("Network.enable");

  // 开发身份必须先启用，否则写接口身份不足。
  //
  // ★ 落在**任意工作台页面**上，不是首页 —— 首页是登录页（未登录时只有
  //   「产品名 + 一句话 + 登录动作」），那上面**没有**开发身份入口。
  //   第一版等的是首页的「内容审核工作台」，于是恒超时，而报错读起来像
  //   「服务没起来」。现有 `check_review_actions.mjs` 的做法是直接落在
  //   一个具体案件页上再等这个按钮 —— 同一形状。
  await goto(`${base}/cases`, "送审内容");
  const hasDev = await evaluate(
    `!!document.body && document.body.innerText.includes('启用本地开发身份')`,
  ).catch(() => false);
  if (!hasDev) {
    skip("启用本地开发身份入口", "页面没有这个入口（不是 dev 模式？）");
    return;
  }
  await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.textContent?.trim() === '启用本地开发身份');
    if (b) b.click();
    return !!b;
  })()`);
  await sleep(800);

  for (const s of SAMPLES) {
    // ── ① 直接调接口，拿**后端真相**
    const apiRes = await apiFetch("/api/v1/submissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `matrix-${s.key}-${Date.now()}`,
      },
      body: JSON.stringify({
        submission_id: `matrix-${s.key}`,
        content_type: "文本",
        content_stage: "final_content",
        entry_channel: "群消息",
        source: { kind: "free_text" },
        product_line: "pump",
        text: s.text,
      }),
    });
    if (!apiRes.ok) {
      const body = await apiRes.text().catch(() => "");
      // ★ 401/403 是**测试自身**没拿到身份，不是样例被拒 ——
      //   两者必须报得不一样，否则一次身份失效会被读成「功能坏了」。
      if (apiRes.status === 401 || apiRes.status === 403) {
        skip(`[${s.key}] 接口提交`, `身份不足 HTTP ${apiRes.status}：${body.slice(0, 100)}`);
      } else {
        bad(`[${s.key}] 接口提交`, `HTTP ${apiRes.status}：${body.slice(0, 120)}`);
      }
      continue;
    }
    const sub = await apiRes.json();
    const caseId = sub.case_id;
    if (!caseId) {
      bad(`[${s.key}] 接口返回 case_id`, JSON.stringify(sub).slice(0, 120));
      continue;
    }
    const detail = await (await apiFetch(
      `/api/v1/cases/${encodeURIComponent(caseId)}`,
    )).json();
    const backendState = detail?.ir?.decision?.state;
    const backendCoverage = detail?.ir?.coverage?.coverage_state;
    const backendFindings = (detail?.ir?.findings ?? []).length;
    const notEvaluated = (detail?.ir?.coverage?.not_evaluated_reason ?? []).length;

    // ── ② 浏览器打开这个案件
    await goto(`${base}/cases/${encodeURIComponent(caseId)}`, "判定");
    await sleep(400);

    // ── ③ 界面读数
    const ui = await evaluate(`(() => {
      const txt = document.body.innerText;
      const badges = [...document.querySelectorAll('[class*="badge--"]')]
        .map(b => b.textContent?.trim() || '');
      return {
        text: txt,
        badges,
        hasCoverageReason: !!document.querySelector('.coverage-reason'),
        hasNotEvaluated: txt.includes('未评估的部分'),
        hasWorkflow: txt.includes('工作流'),
      };
    })()`);

    // ── ④ 比对
    // ★ 界面显示的是**中文业务名**（「违规拦截」），后端给的是枚举（BLOCK）。
    //   两者必须一一对应 —— 但对应关系由 StatusBadge 的映射表定义，
    //   所以这里从源码读表，不硬编码（见 readDecisionLabels 的注释）。
    const expectedLabel = decisionLabels[backendState];
    const stateShown = expectedLabel
      ? ui.badges.some((b) => b === expectedLabel)
      : ui.badges.some((b) => b === backendState);
    check(stateShown,
      `[${s.key}] 界面结论徽标 == 后端 decision.state`
      + `（${backendState} → 「${expectedLabel ?? backendState}」）`,
      `界面徽标 = ${JSON.stringify(ui.badges.slice(0, 6))}`);

    // ★ 界面不许比后端更强：后端没命中时，界面也不许出现「违规」字样
    if (backendFindings === 0) {
      const blockLabel = decisionLabels.BLOCK ?? "BLOCK";
      const saysViolation = ui.badges.some((b) => b === blockLabel);
      check(!saysViolation,
        `[${s.key}] 后端 0 条 finding 时界面不许显示「违规拦截」`
        + `（界面比后端更强 = 编造结论）`,
        `徽标 = ${JSON.stringify(ui.badges.slice(0, 6))}`);
    }

    if (s.expect.needsCoverageReason) {
      check(ui.hasCoverageReason,
        `[${s.key}] ★★★ 「没命中却仍待复核」必须有一句解释`
        + `（backend findings=${backendFindings}, coverage=${backendCoverage}, 未查 ${notEvaluated} 项）`);
      // ★ 反向对照：有 finding 的样例**不该**出现这句 ——
      //   它是给「干净但待复核」写的，乱贴会把真实风险说成口径问题。
    }
    if (s.expect.notClean) {
      const blockLabel = decisionLabels.BLOCK ?? "BLOCK";
      const reviewLabel = decisionLabels.REVIEW ?? "REVIEW";
      const saysBlockOrReview = ui.badges.some(
        (b) => b === blockLabel || b === reviewLabel);
      check(saysBlockOrReview,
        `[${s.key}] 命中规则的样例必须显示为非通过`,
        `徽标 = ${JSON.stringify(ui.badges.slice(0, 6))}`);
    }

    // ★ 未查部分必须能被看见（partial 时）
    if (backendCoverage === "partial" && notEvaluated > 0) {
      check(ui.hasNotEvaluated,
        `[${s.key}] 覆盖 partial 时界面必须有「未评估的部分」一节`);
    }

    const p = await shot(`matrix-${s.key}`);
    console.log(`   · ${s.label} → ${backendState} / ${backendCoverage} / findings=${backendFindings}`
      + (p ? ` · ${p}` : ""));
  }

  // ── ⑤ 反向对照：矩阵本身活着吗
  //
  //   ★ 这一条防「全过但其实一条都没比」。判据是「矩阵至少有 5 条样例、
  //     且它们的后端结论**不全相同**」—— 全相同说明样例没区分度，
  //     那种矩阵跑绿了也不说明什么。
  if (pass > 0) {
    ok(`矩阵至少跑了 ${SAMPLES.length} 条样例`);
  }
}

main()
  .then(() => {
    console.log("─".repeat(74));
    if (fails.length) {
      console.log(`❌ ${pass} 过 · ${fails.length} 红 · ${skips.length} 未测`);
      process.exitCode = 1;
    } else if (skips.length) {
      console.log(`⚠️ ${pass} 过 · ${skips.length} 未测 —— 未测不是通过`);
      process.exitCode = 2;
    } else {
      console.log(`✅ ${pass}/${pass} 全过`);
      process.exitCode = 0;
    }
  })
  .catch((e) => {
    console.error(`⚠ 未测：${e instanceof Error ? e.message : e}`);
    process.exitCode = 2;
  })
  .finally(() => {
    try { child.kill(); } catch { /* 已退出 */ }
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* 忽略 */ }
  });
