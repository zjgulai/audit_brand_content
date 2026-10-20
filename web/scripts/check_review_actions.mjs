#!/usr/bin/env node
/**
 * 浏览器真实写链：显式启用开发身份 → 认领 → 保存草稿 → 提交复核意见 → GET 回读。
 * 只对 dev-up 的临时投影/session 运行；生产构建不含这些控件。
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
const caseId = arg("case", "");
const debugPort = Number(arg("debug-port", "9341"));
const chrome = process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

if (!api || !caseId) {
  console.error("⚠ 未测：需要 --api / --case");
  process.exit(2);
}
if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "review_actions_chrome_"));
const child = spawn(chrome, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  "--no-default-browser-check", `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${profile}`, "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitChrome() {
  for (let i = 0; i < 60; i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      if (response.ok) return;
    } catch { /* retry */ }
    await sleep(200);
  }
  throw new Error("Chrome remote debugging 未就绪");
}
function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const pending = new Map();
    let nextId = 1;
    ws.onopen = () => resolve({
      send(method, params = {}) {
        const id = nextId++;
        return new Promise((res, rej) => {
          pending.set(id, { res, rej });
          ws.send(JSON.stringify({ id, method, params }));
        });
      },
      close() { ws.close(); },
    });
    ws.onerror = reject;
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !pending.has(message.id)) return;
      const { res, rej } = pending.get(message.id);
      pending.delete(message.id);
      message.error ? rej(new Error(JSON.stringify(message.error))) : res(message.result);
    };
  });
}
let activeCookie = cookie;
async function apiCase() {
  const response = await fetch(`${api}/api/v1/cases/${encodeURIComponent(caseId)}`, {
    headers: { Cookie: `session=${activeCookie}` },
  });
  if (!response.ok) throw new Error(`GET case → HTTP ${response.status}`);
  return response.json();
}

let cdp;
try {
  await waitChrome();
  const target = await (await fetch(
    `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  )).json();
  cdp = await connect(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");
  if (cookie) {
    await cdp.send("Network.setCookie", {
      name: "session", value: cookie, url: new URL(base).origin, path: "/",
    });
  }
  const ev = async (expression) => {
    const response = await cdp.send("Runtime.evaluate", { expression, returnByValue: true });
    if (response?.exceptionDetails) throw new Error(response.exceptionDetails.text);
    return response?.result?.value;
  };
  const body = () => ev("document.body?.innerText || ''");
  const waitText = async (needle, timeout = 15000) => {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      const text = await body();
      if (text.includes(needle)) return text;
      await sleep(150);
    }
    throw new Error(`页面未出现：${needle}`);
  };
  const waitEval = async (expression, label, timeout = 15000) => {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await ev(expression)) return;
      await sleep(150);
    }
    throw new Error(`等待超时：${label}`);
  };
  const click = async (text) => {
    const ok = await ev(`(() => {
      const el=[...document.querySelectorAll('button')].find(x=>x.textContent?.trim()===${JSON.stringify(text)});
      if(!el || el.disabled) return false; el.click(); return true;
    })()`);
    if (!ok) throw new Error(`按钮不可点：${text}`);
  };

  await cdp.send("Page.navigate", { url: `${base}/cases/${encodeURIComponent(caseId)}` });
  await waitText("启用本地开发身份");
  await click("启用本地开发身份");
  await waitEval(
    `document.querySelector('select[aria-label="切换本地开发身份"]')?.value === 'u_dp3'`,
    "DP3 session 已确认",
  );
  await waitText("复核动作");
  await waitEval(
    `[...document.querySelectorAll('button')].some(x=>x.textContent?.trim()==='认领' && !x.disabled)`,
    "认领按钮可用",
  );
  const devCookies = await cdp.send("Network.getCookies", { urls: [base] });
  activeCookie = devCookies.cookies?.find((item) => item.name === "session")?.value ?? "";
  if (!activeCookie || (cookie && activeCookie === cookie)) {
    throw new Error("开发身份没有签发新的 HttpOnly session cookie");
  }

  const before = await apiCase();
  if (before.review.status !== "unassigned" || before.review.version !== 0) {
    throw new Error(`初始台账不是 unassigned/v0：${JSON.stringify(before.review)}`);
  }

  await click("认领");
  await waitText("认领 已完成并回读台账");
  const claimed = await apiCase();
  if (claimed.review.status !== "claimed" || claimed.review.version !== 1 || claimed.review.assignee !== "u_dp3") {
    throw new Error(`认领回读不一致：${JSON.stringify(claimed.review)}`);
  }

  const typed = await ev(`(() => {
    const el=document.querySelector('#review-note'); if(!el) return false;
    const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
    set.call(el,'人工复核：需要补充依据'); el.dispatchEvent(new Event('input',{bubbles:true})); return true;
  })()`);
  if (!typed) throw new Error("无法填写复核理由");
  await click("存草稿");
  try {
    await waitText("存草稿 已完成并回读台账");
  } catch (error) {
    throw new Error(`${error instanceof Error ? error.message : error}; 页面=${JSON.stringify((await body()).slice(-1200))}`);
  }
  const drafted = await apiCase();
  if (drafted.review.version !== 2 || !drafted.review.primary_draft_id) {
    throw new Error(`草稿回读不一致：${JSON.stringify(drafted.review)}`);
  }

  await click("提交复核意见");
  await waitText("提交复核意见 已完成并回读台账");
  const submitted = await apiCase();
  if (submitted.review.status !== "closed" || submitted.review.version !== 3) {
    throw new Error(`提交回读不一致：${JSON.stringify(submitted.review)}`);
  }
  await waitText("formal-");
  const text = await body();
  if (!text.includes("人工意见不改变机器标签或放行状态")) {
    throw new Error("页面未显示 formal ID 或人工意见边界");
  }
  console.log(JSON.stringify({
    ok: true,
    case_id: caseId,
    versions: [before.review.version, claimed.review.version, drafted.review.version, submitted.review.version],
    draft_id: drafted.review.primary_draft_id,
    status: submitted.review.status,
  }, null, 2));
  process.exitCode = 0;
} catch (error) {
  console.error(`写动作页面断言失败：${error instanceof Error ? error.message : error}`);
  process.exitCode = 1;
} finally {
  try { cdp?.close(); } catch { /* ignore */ }
  try { child.kill("SIGKILL"); } catch { /* ignore */ }
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* ignore */ }
}
