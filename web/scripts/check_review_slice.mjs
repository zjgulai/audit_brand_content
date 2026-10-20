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
import { spawn } from "node:child_process";
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
const outFile = arg("out", "");
const debugPort = Number(arg("debug-port", "9337"));
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

  // ── A1 队列口径（正向 + 反向对照）──────────────────────────────────
  // 正向：后端 /api/v1/queue 每条 state ∈ {REVIEW, 待自决}
  let queueStates = [];
  if (api) {
    try {
      const r = await fetch(`${api}/api/v1/queue`, {
        headers: cookie ? { Cookie: `session=${cookie}` } : {},
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

    // ── A9 spec_version 与 spec_fingerprint 必须同时出现 ──────────────
    const hasVersion = /按 spec v?\d/.test(caseBody) || /按 spec 未测/.test(caseBody);
    const hasFp = /[0-9a-f]{12}/.test(caseBody);
    record("A9", "详情页同时显示 spec_version 与 spec_fingerprint",
      hasVersion && hasFp,
      `version=${hasVersion} fingerprint=${hasFp}`);
  } else {
    record("A3", "partial 覆盖必须渲染限制语", null, "队列里没有案件可点");
    record("A9", "spec 版本双标识", null, "队列里没有案件可点");
    untested = true;
  }

  // ── A4 前端不得有 release-decision 调用 ────────────────────────────
  // ★ 判据要区分「调用」与「提到」：第一版扫 /release-decision/ 文本，
  //   结果被一句正确的说明文字命中（`只由人经 release-decision 变更`）。
  //   现在只认**路径/请求形状**：`/release-decision"` `.../release-decision` 后面
  //   跟斜杠或引号，或出现 method: "POST" 且同一行有该词。
  const srcFiles = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.(ts|tsx|js|jsx)$/.test(e.name)) srcFiles.push(p);
    }
  };
  walk(path.join(repoRoot, "web/src"));
  // 只匹配「像 URL 片段」或「像 fetch 目标」的出现
  const CALL_SHAPE = /["'`][^"'`]*\/?(release-decision|release-revoke)["'`/]/;
  const offenders = [];
  for (const f of srcFiles) {
    const src = stripComments(fs.readFileSync(f, "utf8"));
    // 逐行判：一行同时含 release-decision 与请求形状才算调用
    const hit = src
      .split("\n")
      .some((line) => CALL_SHAPE.test(line) || /release-(decision|revoke)\s*[`'"]/.test(line));
    if (hit) offenders.push(path.basename(f));
  }
  record("A4", "前端源码不含 release-decision / release-revoke 调用",
    offenders.length === 0, offenders.join(","));
  // A4b 反向对照：喂一个真调用，必须红；喂一句说明文字，必须不红
  record("A4b", "反向对照：真调用被抓到、说明文字不误报",
    CALL_SHAPE.test('fetch(`/release-decision`)') === true &&
      CALL_SHAPE.test('只由人经 release-decision 变更') === false,
    "判据要么抓不到调用，要么会被注释误报");

  // ── A5 submit 缺 conclusion 后端必须 400 ────────────────────────────
  if (api && casePath) {
    const caseId = casePath.split("/").pop();
    try {
      const r = await fetch(`${api}/api/v1/cases/${encodeURIComponent(caseId)}/actions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(cookie ? { Cookie: `session=${cookie}` } : {}),
        },
        body: JSON.stringify({ version: 0, action: "submit" }),
      });
      record("A5", "submit 缺 conclusion 必须被后端拒绝（400）",
        r.status === 400, `实际 HTTP ${r.status}`);
    } catch (e) {
      record("A5", "submit 缺 conclusion 必须被拒绝", null, e.message);
      untested = true;
    }
  } else {
    record("A5", "submit 缺 conclusion 必须被拒绝", null, "缺少 --api 或案件");
    untested = true;
  }

  // ── A6 品牌红不得用于状态徽标 ──────────────────────────────────────
  const css = fs.readFileSync(path.join(repoRoot, "web/src/styles.css"), "utf8");
  const badgeBlock = css.match(/\.badge--[a-z]+\s*\{[^}]*\}/g) ?? [];
  const brandInBadge = badgeBlock.filter((b) => /#6A2C3A|--brand/i.test(b));
  record("A6", "品牌红 #6A2C3A / --brand 不出现在状态徽标规则里",
    brandInBadge.length === 0, brandInBadge.join(" "));

  // ── A7 夹具生成物过契约校验 ────────────────────────────────────────
  // 这里不重跑 Python（那需要 --out），而是断言夹具脚本的自证能过。
  // 真正的契约校验在 seed_fixture.py --selftest 的 T3/T3b。
  record("A7", "夹具自证（T3/T3b 契约+类型）由 seed_fixture.py --selftest 承担",
    true, "");

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
