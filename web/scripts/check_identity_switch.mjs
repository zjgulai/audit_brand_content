#!/usr/bin/env node
/** 切换开发身份时，旧详情与备注必须立即消失；新 session 成功后再加载。 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const base = arg("base", "").replace(/\/$/, "");
const caseId = arg("case", "");
const api = arg("api", "").replace(/\/$/, "");
const debugPort = Number(arg("debug-port", "9343"));
const chrome = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
if (!base || !api || !caseId || !fs.existsSync(chrome)) process.exit(2);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "identity_switch_chrome_"));
const child = spawn(chrome, ["--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`http://127.0.0.1:${debugPort}/json/version`)).ok) break; } catch { /* retry */ }
    await sleep(200);
  }
  const target = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map(); let id = 1;
  const cdp = await new Promise((resolve, reject) => {
    ws.onopen = () => resolve({ send(method, params = {}) {
      const call = id++;
      return new Promise((res, rej) => { pending.set(call, { res, rej }); ws.send(JSON.stringify({ id: call, method, params })); });
    }});
    ws.onerror = reject;
    ws.onmessage = (event) => { const msg = JSON.parse(event.data); if (!pending.has(msg.id)) return;
      const pair = pending.get(msg.id); pending.delete(msg.id); msg.error ? pair.rej(msg.error) : pair.res(msg.result); };
  });
  await cdp.send("Page.enable"); await cdp.send("Runtime.enable"); await cdp.send("Network.enable");
  const ev = async (expression) => (await cdp.send("Runtime.evaluate", { expression, returnByValue: true }))?.result?.value;
  const body = () => ev("document.body?.innerText || ''");
  const wait = async (needle) => { for (let i = 0; i < 100; i++) { if ((await body()).includes(needle)) return; await sleep(120); } throw new Error(`缺文案：${needle}`); };
  const click = async (text) => { const ok = await ev(`(()=>{const x=[...document.querySelectorAll('button')].find(e=>e.textContent?.trim()===${JSON.stringify(text)});if(!x||x.disabled)return false;x.click();return true})()`); if (!ok) throw new Error(`不可点：${text}`); };
  await cdp.send("Page.navigate", { url: `${base}/cases/${encodeURIComponent(caseId)}` });
  await wait("启用本地开发身份"); await click("启用本地开发身份"); await wait("DP3 审核员（u_dp3）"); await wait("复核动作");
  await ev(`(()=>{const e=document.querySelector('#review-note');const s=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;s.call(e,'不得跨身份保留');e.dispatchEvent(new Event('input',{bubbles:true}));return true})()`);
  const cookiesBefore = await cdp.send("Network.getCookies", { urls: [base] });
  const beforeSwitchCookie = cookiesBefore.cookies?.find((cookie) => cookie.name === "session")?.value;
  if (!beforeSwitchCookie) throw new Error("切换前没有 HttpOnly session cookie");
  const selected = await ev(`(()=>{
    const e=document.querySelector('select[aria-label="切换本地开发身份"]');
    if(!e) return false;
    const set=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
    set.call(e,'u_dp4'); e.dispatchEvent(new Event('change',{bubbles:true})); return true
  })()`);
  if (!selected) throw new Error("无法切换身份");
  await wait("正在切换开发身份");
  const immediate = await body();
  if (immediate.includes("不得跨身份保留") || immediate.includes(caseId)) throw new Error("身份切换期间残留旧案件或备注");
  await wait("DP4 法务（u_dp4）"); await wait("复核动作");
  const after = await ev("document.querySelector('#review-note')?.value || ''");
  if (after !== "") throw new Error("新身份仍保留旧备注");
  const beforeResponse = await fetch(`${api}/api/v1/cases/${encodeURIComponent(caseId)}`, {
    headers: { Cookie: `session=${beforeSwitchCookie}` },
  });
  if (beforeResponse.status !== 401) {
    throw new Error(`旧 session 切换后未撤销：HTTP ${beforeResponse.status}`);
  }
  const cookiesAfter = await cdp.send("Network.getCookies", { urls: [base] });
  const afterSwitchCookie = cookiesAfter.cookies?.find((cookie) => cookie.name === "session")?.value;
  if (!afterSwitchCookie || afterSwitchCookie === beforeSwitchCookie) {
    throw new Error("切换后没有新 session cookie");
  }
  console.log(JSON.stringify({ ok: true, cleared: true, old_revoked: true, next: "u_dp4" }, null, 2));
}
let rc = 0;
try { await main(); } catch (e) { console.error(`身份切换断言失败：${e instanceof Error ? e.message : e}`); rc = 1; }
finally { try { child.kill("SIGKILL"); } catch {} try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} }
process.exit(rc);
