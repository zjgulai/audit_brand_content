#!/usr/bin/env node
/**
 * check_queue_page.mjs —— 用本机 Chrome（CDP）打开 /queue，断言渲染出指定案件。
 *
 * 不依赖 Playwright；只用 Node 24 内置 WebSocket + Chrome remote debugging。
 * 退出码：0 页面断言通过 / 1 失败 / 2 环境不可用（Chrome 起不来）。
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const pageUrl = arg("url", "http://127.0.0.1:5180/queue");
const cookie = arg("cookie", "");
const expect = arg("expect", "case-smoke");
const shot = arg("screenshot", "");
const debugPort = Number(arg("debug-port", "9333"));
const chrome =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "web_queue_chrome_"));
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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
        ws,
        send(method, params = {}) {
          const id = nextId++;
          return new Promise((res, rej) => {
            pending.set(id, { res, rej });
            ws.send(JSON.stringify({ id, method, params }));
          });
        },
        close() {
          ws.close();
        },
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
  await waitJsonVersion();
  const origin = new URL(pageUrl).origin;
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
  await cdp.send("Page.navigate", { url: pageUrl });

  let body = "";
  for (let i = 0; i < 80; i++) {
    try {
      const r = await cdp.send("Runtime.evaluate", {
        expression: "document.body ? document.body.innerText : ''",
        returnByValue: true,
      });
      body = r?.result?.value ?? "";
      if (body.includes(expect) && !body.includes("加载中…")) break;
    } catch {
      /* page not ready */
    }
    await sleep(200);
  }

  if (shot) {
    try {
      const png = await cdp.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(shot, Buffer.from(png.data, "base64"));
    } catch {
      /* 截图失败不改变页面断言 */
    }
  }

  const ok = body.includes(expect);
  console.log(
    JSON.stringify(
      {
        ok,
        page: pageUrl,
        expect,
        body: body.slice(0, 600),
        screenshot: shot || null,
      },
      null,
      2,
    ),
  );
  cdp.close();
  return ok ? 0 : 1;
}

let rc = 2;
try {
  rc = await main();
} catch (e) {
  console.error(`页面断言失败：${e instanceof Error ? e.message : e}`);
  rc = 1;
} finally {
  try {
    child.kill("SIGKILL");
  } catch {
    /* ignore */
  }
  try {
    fs.rmSync(profile, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
}
process.exit(rc);
