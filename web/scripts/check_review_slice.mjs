#!/usr/bin/env node
/**
 * check_review_slice.mjs —— 复核切片的机器可执行断言（A1–A9）
 *
 * 为什么是断言而不是截图评分：
 *   「未测被折叠成 0」「队列里混进 PASS」这两种病**长得跟正常界面一模一样**，
 *   截图看不出来，而它们各自已经真实发生过一次。
 *
 * 退出码：
 *   0 = 全部通过
 *   1 = 有断言失败
 *   2 = 未测（Chrome 起不来 / 后端连不上）—— **不是通过**
 *
 * 用法：
 *   node web/scripts/check_review_slice.mjs --base http://127.0.0.1:5177 \
 *        --api http://127.0.0.1:8899 --cookie <opaque> [--out result.json]
 */
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const base = arg("base", "http://127.0.0.1:5180").replace(/\/$/, "");
const api = arg("api", "").replace(/\/$/, "");
const cookie = arg("cookie", "");
let activeCookie = cookie;
const outFile = arg("out", "");
const debugPort = Number(arg("debug-port", "9337"));
const enableDevIdentity = arg("enable-dev-identity", "0") === "1";
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const chrome =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const results = [];
let untested = false;

function record(id, label, ok, detail = "") {
  results.push({ id, label, ok, detail });
  const mark = ok === null ? "⚠" : ok ? "✓" : "✗";
  console.log(`  ${mark} ${id} ${label}${detail && ok !== true ? "  ← " + detail : ""}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "review_slice_chrome_"));
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

async function waitJsonVersion() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      if (r.ok) return await r.json();
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
    let nextId = 1;
    ws.onopen = () =>
      resolve({
        send(method, params = {}) {
          const id = nextId++;
          return new Promise((res, rej) => {
            pending.set(id, { res, rej });
            ws.send(JSON.stringify({ id, method, params }));
          });
        },
        close: () => ws.close(),
      });
    ws.onerror = (e) => reject(e);
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

async function main() {
  try {
    await waitJsonVersion();
  } catch {
    console.error("⚠ 未测：Chrome 起不来");
    process.exit(2);
  }

  const origin = new URL(base).origin;
  const targetResp = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  );
  const target = await targetResp.json();
  const cdp = await connect(target.webSocketDebuggerUrl);

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");
  if (cookie) {
    await cdp.send("Network.setCookie", {
      name: "session",
      value: cookie,
      url: origin,
      path: "/",
    });
  }

  const ev = async (expression) => {
    const r = await cdp.send("Runtime.evaluate", { expression, returnByValue: true });
    if (r?.exceptionDetails) return undefined;
    return r?.result?.value;
  };
  const bodyText = async () => (await ev("document.body ? document.body.innerText : ''")) ?? "";

  async function goto(urlPath) {
    await cdp.send("Page.navigate", { url: `${base}${urlPath}` });
    await sleep(1200);
    // 等到 h1 出现（最多 8 秒），避免读到空 body
    const end = Date.now() + 8000;
    while (Date.now() < end) {
      if ((await bodyText()).trim().length > 40) break;
      await sleep(200);
    }
  }

  async function clickNamedButton(name) {
    return ev(`(() => {
      const button=[...document.querySelectorAll('button')].find(
        (x) => x.textContent?.trim() === ${JSON.stringify(name)}
      );
      if (!button || button.disabled) return false;
      button.click();
      return true;
    })()`);
  }

  if (enableDevIdentity) {
    await goto("/queue");
    const enabled = await clickNamedButton("启用本地开发身份");
    if (!enabled) throw new Error("本地开发身份按钮不可点");
    const end = Date.now() + 8000;
    while (Date.now() < end) {
      if ((await bodyText()).includes("DP3 审核员（u_dp3）")) break;
      await sleep(150);
    }
    const cookies = await cdp.send("Network.getCookies", { urls: [base] });
    activeCookie = cookies.cookies?.find((item) => item.name === "session")?.value ?? "";
    if (!activeCookie) throw new Error("显式启用后没有新 session cookie");
  }

  // ── A1 队列口径（正向 + 反向对照）──────────────────────────────────
  // 正向：后端 /api/v1/queue 每条 state ∈ {REVIEW, 待自决}
  let queueStates = [];
  if (api) {
    try {
      const r = await fetch(`${api}/api/v1/queue`, {
        headers: activeCookie ? { Cookie: `session=${activeCookie}` } : {},
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      queueStates = (await r.json()).map((x) => String(x.state));
    } catch (e) {
      record("A1", "队列口径（正向）", null, `后端不可达：${e.message}`);
      untested = true;
    }
  } else {
    record("A1", "队列口径（正向）", null, "未给 --api");
    untested = true;
  }

  if (queueStates.length) {
    const bad = queueStates.filter((s) => !["REVIEW", "待自决"].includes(s));
    record(
      "A1",
      `队列只含 REVIEW/待自决（实测 ${queueStates.length} 条）`,
      bad.length === 0,
      `出现了 ${[...new Set(bad)].join(",")} × ${bad.length}`,
    );

    // 反向对照：造一条 PASS / BLOCK，断言「不在队列里」这个判据能抓到它
    const injected = [...queueStates, "PASS", "BLOCK"];
    const caught = injected.filter((s) => !["REVIEW", "待自决"].includes(s));
    record(
      "A1b",
      "反向对照：塞入 PASS/BLOCK 必须被抓到",
      caught.length === 2,
      "判据恒真 → 它保护不了任何东西",
    );
  } else if (!untested) {
    record("A1", "队列只含 REVIEW/待自决", null, "队列为空，无法判定");
    untested = true;
  }

  // 页面侧：队列页不得渲染出 BLOCK / PASS 徽标（这是 A1 的界面证据）
  await goto("/queue");
  const queueBody = await bodyText();
  const queueHasBadge = /(^|\n)\s*(BLOCK|PASS)\s*(\n|$)/.test(queueBody);
  record("A1c", "队列页不渲染 BLOCK / PASS 徽标", !queueHasBadge,
    queueHasBadge ? "页面上出现了非待办标签" : "");

  // ── A2 null 不得折叠成符号 ──────────────────────────────────────────
  // ★ 判据要**指得出对象**：只查「案件字段」被折叠，不查任意 `?? "—"`。
  //   第一版用 /\?\?\s*["'`]—["'`]/ 全量匹配，结果被「当前身份 ?? "—"」这种
  //   与数据语义无关的界面标签触发 —— 会误报的检查器比没有更糟（§2.1.1）。
  //   收窄为：字段名 ∈ {state, layer, release_status, assignee_id, product_line,
  //   coverage_state, ir_id, receipt_ref} 且右侧是破折号/减号占位符。
  const queueSrc = fs.readFileSync(
    path.join(repoRoot, "web/src/pages/QueuePage.tsx"),
    "utf8",
  );
  const caseSrc = fs.readFileSync(
    path.join(repoRoot, "web/src/pages/CaseDetailPage.tsx"),
    "utf8",
  );
  // 「注释不算代码」：把整行注释与块注释剥掉再判，否则判据会被自己的解释文字绊倒
  const stripComments = (src) =>
    src
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
  const FIELD_FOLD =
    /\.(state|layer|release_status|assignee_id|product_line|coverage_state|ir_id|receipt_ref)\s*\?\?\s*["'`][—\-–]["'`]/;
  const folded = [queueSrc, caseSrc]
    .map(stripComments)
    .filter((s) => FIELD_FOLD.test(s));
  record("A2", "案件字段没有 `?? \"—\"` 折叠（state/layer/release_status 等）",
    folded.length === 0, `${folded.length} 个文件仍有`);
  // A2b 反向对照：喂一个坏样本，判据必须红
  record("A2b", "反向对照：`{c.state ?? \"—\"}` 必须被抓到",
    FIELD_FOLD.test('{c.state ?? "—"}') && !FIELD_FOLD.test('{name ?? "—"}'),
    "判据要么恒真要么误报");

  // ── A2d / A2e 缺依据字段的 **DOM** 行为（方案 §7.2「A2 的具体改法」）──
  //   夹具由 `seed_fixture.py --edge` 写入；没 seed 时落**未测**，不落绿 ——
  //   「夹具不在投影里」与「页面做对了」长得完全不一样。
  const edgeMissing = arg("edge-case-missing", "case-edge-missing-authority");
  const edgeOk = arg("edge-case-ok", "case-edge-authority-ok");
  const AUTH_TEXT = ["可核", "未测", "依据已过期", "依据缺失"];
  const authOfPage = async (caseId) => {
    await goto(`/cases/${caseId}`);
    return ev(`(() => {
      const items=[...document.querySelectorAll('.evidence__item')];
      const texts=items.map((it) => {
        const t=[...it.querySelectorAll('span')]
          .map((s)=>s.textContent.trim())
          .filter((x)=>${JSON.stringify(AUTH_TEXT)}.includes(x));
        return t[0] || null;
      });
      return { path: location.pathname, items: items.length, texts };
    })()`);
  };
  const mEdge = await authOfPage(edgeMissing);
  const oEdge = await authOfPage(edgeOk);
  await goto("/queue");      // ★ 必须回来：A3/A9 依赖队列页上的案件链接
  const mLoaded = Boolean(mEdge) && mEdge.items > 0 && mEdge.path === `/cases/${edgeMissing}`;
  const oLoaded = Boolean(oEdge) && oEdge.items > 0 && oEdge.path === `/cases/${edgeOk}`;
  if (!mLoaded || !oLoaded) {
    // ★ dev-up.sh 在批次 0 冻结（方案 L887），不会 seed --edge；所以默认**不因此改退出码**，
    //   但把「本次没验」喊出来。独立验收用 `--require-edge`：那时缺夹具必须退 2（未测）。
    if (process.argv.includes("--require-edge")) {
      record("A2d", "缺 authority_state 的发现显示「未测」、不显示「可核」", null,
        `边界夹具不在投影里（missing=${mLoaded} ok=${oLoaded}）`);
      untested = true;
    } else {
      console.log(`  ⚠ A2d 本次未验证：边界夹具不在投影里（missing=${mLoaded} ok=${oLoaded}）；` +
        `要验请用 seed_fixture.py --edge 重 seed 后加 --require-edge`);
    }
  } else {
    const mOk = mEdge.texts.includes("未测") && !mEdge.texts.includes("可核");
    const oOk = oEdge.texts.includes("可核") && !oEdge.texts.includes("未测");
    record("A2d", "缺 authority_state 的发现显示「未测」、不显示「可核」", mOk,
      `实测 ${JSON.stringify(mEdge.texts)}`);
    record("A2e", "authority_state=ok 的发现显示「可核」、不显示「未测」", oOk,
      `实测 ${JSON.stringify(oEdge.texts)}`);
  }

  // ── A3 partial 必须显式说明 ────────────────────────────────────────
  const caseLinks = await ev(
    "[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).filter(h=>h&&h.startsWith('/cases/'))",
  );
  let casePath = null;
  if (Array.isArray(caseLinks) && caseLinks.length) {
    casePath = caseLinks[0];
    await goto(casePath);
    const caseBody = await bodyText();
    const hasPartialText = caseBody.includes("仅已覆盖部分可判");
    const showsPartial = caseBody.includes("partial");
    record(
      "A3",
      "partial 覆盖必须渲染「仅已覆盖部分可判」",
      showsPartial ? hasPartialText : true,
      showsPartial ? "标了 partial 但没写限制语" : "",
    );

    // ── A9 spec 版本双标识：必须同时出现，且指纹必须等于当前正文算出的那个 ──
    //
    // ★ 2026-10-20 收紧。第一版只断言「`按 spec vN` 与 12 位 hex 都出现了」，
    //   结果全绿而实际发生过一件事：规范正文被改了 53 行、`spec_fingerprint`
    //   从 562a90352c23 变成 9a8388d369c9，而 `spec_version` 是生成器里的
    //   **硬编码字面量**（`tools/gen_taxonomy_json.py:224`），仍是 v1.1。
    //   于是「版本没变、内容变了」——同号两版，正是这条断言本该防的形状。
    //
    //   现在比的是**磁盘上 JSON 与规范正文是否同步**，不是「界面上有没有字」。
    const hasVersion = /按 spec v?\d/.test(caseBody) || /按 spec 未测/.test(caseBody);
    const hasFp = /[0-9a-f]{12}/.test(caseBody);
    const taxJson = JSON.parse(
      fs.readFileSync(path.join(repoRoot, "web/src/data/taxonomy.json"), "utf8"),
    );
    const jsonFp = taxJson?.meta?.spec_fingerprint;
    const jsonVer = taxJson?.meta?.spec_version;
    // 界面显示的指纹必须是 JSON 里的那个（不允许界面写死一个）
    const fpMatchesJson = Boolean(jsonFp) && caseBody.includes(jsonFp);
    record(
      "A9",
      "详情页同时显示 spec_version 与 spec_fingerprint，且指纹与 taxonomy.json 一致",
      hasVersion && hasFp && fpMatchesJson,
      `version=${hasVersion} fp=${hasFp} fpMatchesJson=${fpMatchesJson}`,
    );

    // A9b ★ 版本漂移：规范正文变了 → 指纹必须变（这条能红）
    //   判据：正文指纹 == taxonomy.json 的指纹。相等才说明 JSON 跟上了正文。
    //   注意这不保证 spec_version 也跟上（生成器里它是字面量，见 A9c）。
    try {
      const body = fs.readFileSync(
        path.join(repoRoot, "PMO/implement/内容审查分类规范-v1.md"),
        "utf8",
      );
      const { execFileSync } = await import("node:child_process");
      const out = execFileSync(
        "python3",
        [path.join(repoRoot, "tools/gen_taxonomy_json.py"), "--check"],
        { encoding: "utf8", timeout: 60000 },
      );
      record("A9b", "taxonomy.json 与规范正文同步（gen_taxonomy_json --check）",
        /一致/.test(out), out.trim().split("\n").pop());
    } catch (e) {
      record("A9b", "taxonomy.json 与规范正文同步", null,
        `生成器不可用：${e?.message ?? e}`);
    }

    // A9c ★ 版本号是否真的跟随内容 —— 现在**必然红**，这是已知缺陷的读点
    //   生成器第 224 行 `"spec_version": "v1.1"` 是字面量，而 docstring 第 20 行
    //   说它「从规范正文算」。规范已被改过 53 行，版本号却没动。
    //   这条断言存在的目的不是让它绿，是让这个缺口**每次跑都看得见**。
    const genSrc = fs.readFileSync(
      path.join(repoRoot, "tools/gen_taxonomy_json.py"),
      "utf8",
    );
    const versionIsLiteral = /"spec_version":\s*"v[\d.]+"/.test(genSrc);
    record(
      "A9c",
      "spec_version 是从正文算的（不是字面量）",
      !versionIsLiteral,
      versionIsLiteral
        ? "生成器里是硬编码 \"v1.1\"，而 docstring 说「从正文算」——正文改了版本号不会变"
        : "",
    );
  } else {
    record("A3", "partial 覆盖必须渲染限制语", null, "队列里没有案件可点");
    record("A9", "spec 版本双标识", null, "队列里没有案件可点");
    untested = true;
  }

  // ── A4 受控签发边界：非签发专属模块不得有 release-decision / release-revoke 调用 ──
  // ★ 落 G-05 决策：
  //   1. 只有受控模块 `release-client.ts` 与 `ReleasePage.tsx` 允许包含签发路径，
  //      且 `release-client.ts` 必须强制校验 `step_up_token` 与 `nonce`；
  //   2. 任何其他前端源码文件（如 CaseDetailPage / QueuePage / ReviewActions）一旦出现
  //      `/release-decision` 或 `/release-revoke` 调用形状，立即判红！
  const srcFiles = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.(ts|tsx|js|jsx)$/.test(e.name)) srcFiles.push(p);
    }
  };
  walk(path.join(repoRoot, "web/src"));
  const ALLOWED_RELEASE_MODULES = new Set(["release-client.ts", "ReleasePage.tsx"]);
  const CALL_SHAPE = /["'`][^"'`]*\/?(release-decision|release-revoke)["'`/]/;
  const offenders = [];
  for (const f of srcFiles) {
    const baseName = path.basename(f);
    if (ALLOWED_RELEASE_MODULES.has(baseName)) continue;
    const src = stripComments(fs.readFileSync(f, "utf8"));
    const hit = src
      .split("\n")
      .some((line) => CALL_SHAPE.test(line) || /release-(decision|revoke)\s*[`'"]/.test(line));
    if (hit) offenders.push(baseName);
  }
  const releaseClientPath = path.join(repoRoot, "web/src/api/release-client.ts");
  const releaseClientSrc = fs.existsSync(releaseClientPath)
    ? stripComments(fs.readFileSync(releaseClientPath, "utf8"))
    : "";
  const hasStepUpGuard =
    releaseClientSrc.includes("step_up_token") &&
    releaseClientSrc.includes("nonce") &&
    releaseClientSrc.includes("step_up_required");
  record(
    "A4",
    "非受控模块不含 release-decision / release-revoke 调用，且受控客户端强制校验 step_up_token",
    offenders.length === 0 && hasStepUpGuard,
    offenders.length ? offenders.join(",") : "release-client 缺少 step_up_token 守卫",
  );
  // A4b 反向对照：喂一个真调用，必须红；喂一句说明文字，必须不红
  record("A4b", "反向对照：真调用被抓到、说明文字不误报",
    CALL_SHAPE.test('fetch(`/release-decision`)') === true &&
      CALL_SHAPE.test('只由人经 release-decision 变更') === false,
    "判据要么抓不到调用，要么会被注释误报");

  // ── A5 submit 缺 conclusion 后端必须 400 ────────────────────────────
  if (api && casePath) {
    const caseId = casePath.split("/").pop();
    try {
      const cookies = await cdp.send("Network.getCookies", { urls: [base] });
      activeCookie = cookies.cookies?.find((item) => item.name === "session")?.value ?? "";
      if (!activeCookie) throw new Error("A5 前没有当前 session cookie");
      const r = await fetch(`${api}/api/v1/cases/${encodeURIComponent(caseId)}/actions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "slice-a5-missing-conclusion",
          ...(activeCookie ? { Cookie: `session=${activeCookie}` } : {}),
        },
        body: JSON.stringify({ version: 0, action: "submit" }),
      });
      const response = await r.json();
      record("A5", "submit 缺 conclusion 被拒绝且原因正确（400）",
        r.status === 400 && response.message === "submit 必须带 conclusion",
        `HTTP ${r.status}: ${response.message}`);
    } catch (e) {
      record("A5", "submit 缺 conclusion 必须被拒绝", null, e.message);
      untested = true;
    }
  } else {
    record("A5", "submit 缺 conclusion 必须被拒绝", null, "缺少 --api 或案件");
    untested = true;
  }

  // ── A6 品牌红不得用于状态徽标（**DOM 计算样式**，不是源码文本）──────
  //   方案 §7.2 / §5.2：扩围扫描 /queue、/cases/:id、/release、/takedown 四个核心页面。
  const a6Pages = ["/queue", casePath || `/cases/${edgeOk}`, "/release", "/takedown"];
  const a6PageDetails = [];
  let a6TotalCount = 0;
  const a6TotalBad = [];
  let a6Meta = null;
  for (const p of a6Pages) {
    await goto(p);
    const res = await ev(`(() => {
      const hueOf = (rgb) => {
        const m = String(rgb).match(/rgba?\\(([^)]+)\\)/);
        if (!m) return null;
        const [r, g, b] = m[1].split(",").slice(0, 3).map(Number).map((x) => x / 255);
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max === min) return null;
        const d = max - min;
        let h;
        if (max === r) h = ((g - b) / d) % 6;
        else if (max === g) h = (b - r) / d + 2;
        else h = (r - g) / d + 4;
        h *= 60;
        return h < 0 ? h + 360 : h;
      };
      const probe = document.createElement("span");
      probe.style.color = "hsl(" +
        getComputedStyle(document.documentElement).getPropertyValue("--brand").trim() + ")";
      document.body.appendChild(probe);
      const brandRaw = getComputedStyle(document.documentElement).getPropertyValue("--brand").trim();
      const probeColor = getComputedStyle(probe).color;
      const brandHue = hueOf(probeColor);
      probe.remove();
      const scan = () => {
        const nodes = [...document.querySelectorAll("[data-status-badge], .badge")];
        const bad = [];
        for (const el of nodes) {
          const cs = getComputedStyle(el);
          for (const prop of ["color", "backgroundColor", "borderTopColor"]) {
            const h = hueOf(cs[prop]);
            if (h === null || brandHue === null) continue;
            let d = Math.abs(h - brandHue);
            if (d > 180) d = 360 - d;
            if (d < 5) bad.push({ page: ${JSON.stringify(p)}, prop, hue: Math.round(h), brandHue: Math.round(brandHue),
                                  text: (el.textContent || "").trim().slice(0, 20) });
          }
        }
        return { count: nodes.length, bad };
      };
      const before = scan();
      const injected = document.createElement("span");
      injected.className = "badge";
      injected.setAttribute("data-status-badge", "");
      injected.style.color = "#6A2C3A";
      injected.textContent = "反向对照";
      document.body.appendChild(injected);
      const after = scan();
      const injectedColor = getComputedStyle(injected).color;
      injected.remove();
      return { count: before.count, bad: before.bad, brandHue, brandRaw, probeColor,
               afterCount: after.count, afterBad: after.bad.length,
               injectedColor,
               controlCaught: after.bad.length > before.bad.length };
    })()`);
    if (res) {
      a6TotalCount += res.count;
      a6TotalBad.push(...res.bad);
      a6PageDetails.push(`${p}:${res.count}`);
      if (!a6Meta) a6Meta = res;
    }
  }
  const a6 = a6Meta
    ? { ...a6Meta, count: a6TotalCount, bad: a6TotalBad, pages: a6PageDetails }
    : null;
  record("A6", "四页（/queue·/cases/:id·/release·/takedown）状态徽标无一使用品牌红（DOM 计算样式，色相距离 <5°）",
    Boolean(a6) && a6.count > 0 && a6PageDetails.length === 4 && a6.bad.length === 0,
    a6 ? `四页 [${a6.pages.join(", ")}] 共 ${a6.count} 个徽标 · 品牌红命中 ${a6.bad.length} · brandHue=${a6.brandHue} ` +
         `· 注入后 ${a6.afterBad}（${a6.injectedColor}）${JSON.stringify(a6.bad.slice(0, 2))}`
       : "取不到 DOM");
  record("A6b", "反向对照：注入 style=color:#6A2C3A 的 .badge 必须被抓到",
    Boolean(a6?.controlCaught),
    a6 ? `brandRaw=${JSON.stringify(a6.brandRaw)} probeColor=${JSON.stringify(a6.probeColor)} ` +
         `brandHue=${a6.brandHue} afterBad=${a6.afterBad} afterCount=${a6.afterCount}`
       : "取不到 DOM（表达式抛异常）");
  // A6s 源码补充（Stage 5 删除 `.badge--*` 后这条会变成 vacuous，主判据仍是 A6）
  const css = fs.readFileSync(path.join(repoRoot, "web/src/styles.css"), "utf8");
  const badgeBlock = css.match(/\.badge--[a-z]+\s*\{[^}]*\}/g) ?? [];
  const brandInBadge = badgeBlock.filter((b) => /#6A2C3A|--brand/i.test(b));
  record("A6s", "（补充）品牌红 / --brand 不出现在 .badge--* 规则里",
    brandInBadge.length === 0, brandInBadge.join(" "));

  // ── A7 夹具生成物过契约校验 ────────────────────────────────────────
  try {
    const output = execFileSync(
      path.join(repoRoot, ".venv/bin/python"),
      [path.join(repoRoot, "web/scripts/seed_fixture.py"), "--selftest"],
      { encoding: "utf8", timeout: 60000 },
    );
    record(
      "A7",
      "夹具自证真实运行并通过",
      /\d+\/\d+ 项通过/.test(output),
      output.trim().split("\n").pop(),
    );
  } catch (e) {
    record("A7", "夹具自证真实运行", null, e?.message ?? String(e));
    untested = true;
  }

  // ── A8 争议条目渲染 underdetermined 且不硬给单轴 ───────────────────
  await goto("/taxonomy");
  const taxBody = await bodyText();
  const disputeCount = (taxBody.match(/underdetermined/g) ?? []).length;
  const specOk = /按 spec v?\d/.test(taxBody);
  record("A8", `分类规范页渲染欠定条目（实测 ${disputeCount} 处 underdetermined）`,
    disputeCount > 0, "没有渲染任何欠定条目");

  cdp.close();
  child.kill();

  // ── 汇总 ────────────────────────────────────────────────────────────
  const passed = results.filter((r) => r.ok === true).length;
  const failed = results.filter((r) => r.ok === false).length;
  const pending = results.filter((r) => r.ok === null).length;

  console.log(
    `\n通过 ${passed} · 失败 ${failed} · 未测 ${pending}（共 ${results.length}）`,
  );

  const payload = { passed, failed, pending, results };
  if (outFile) fs.writeFileSync(outFile, JSON.stringify(payload, null, 2) + "\n");

  if (failed > 0) return 1;
  // ★ 未测不许报成通过（AGENTS.md §2.4.2 同口径）
  if (pending > 0 || untested) {
    console.log("⚠ 有未测项 —— 这不等于通过");
    return 2;
  }
  console.log("✅ 全部通过");
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    console.error("⚠ 未测：", e?.message ?? e);
    process.exit(2);
  });
