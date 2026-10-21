#!/usr/bin/env node
/**
 * check_pages.mjs —— 队列 → 案件详情 → 报告查看 的真实页面断言（Chrome CDP）。
 *
 * 只读：只点击链接，不提交表单、不调用写接口。
 * 退出码：0 三段都通过 / 1 失败 / 2 环境不可用（Chrome 起不来）。
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
const cookie = arg("cookie", "");
const expectCase = arg("case", "case-smoke");
const expectReport = arg("report", "report-smoke");
const shots = arg("screenshots", "");
const enableDevIdentity = arg("enable-dev-identity", "0") === "1";
// ★ 批次 0（方案 L1388）：1280×720 与 400% reflow（320 CSS px）是**显式开关**。
//   默认关 —— 这两个视口属于 Stage 7 的收口门，打开前不让它们改变现有联调结论。
//   自动 a11y 侧的同类检查在 a11y_check.mjs（Stage 0 已默认跑）。
const wantDesktop = process.argv.includes("--desktop");
const wantReflow = process.argv.includes("--reflow");
const debugPort = Number(arg("debug-port", "9334"));
const chrome =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

if (!fs.existsSync(chrome)) {
  console.error(`⚠ 未测：找不到 Chrome（${chrome}）`);
  process.exit(2);
}
if (shots) fs.mkdirSync(shots, { recursive: true });

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "web_pages_chrome_"));
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

  async function evalValue(expression) {
    const r = await cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
    });
    return r?.result?.value;
  }

  async function bodyText() {
    return (await evalValue("document.body ? document.body.innerText : ''")) ?? "";
  }

  async function waitBody(needle, timeoutMs = 20000) {
    const end = Date.now() + timeoutMs;
    let body = "";
    while (Date.now() < end) {
      body = await bodyText();
      if (body.includes(needle)) return body;
      await sleep(200);
    }
    return body;
  }

  async function shot(name) {
    if (!shots) return null;
    const file = path.join(shots, name);
    try {
      const png = await cdp.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(file, Buffer.from(png.data, "base64"));
      return file;
    } catch {
      return null;
    }
  }

  async function clickNamedButton(name) {
    return evalValue(`(() => {
      const button=[...document.querySelectorAll('button')].find(
        (x) => x.textContent?.trim() === ${JSON.stringify(name)}
      );
      if (!button || button.disabled) return false;
      button.click();
      return true;
    })()`);
  }

  if (enableDevIdentity) {
    await cdp.send("Page.navigate", { url: `${base}/queue` });
    await waitBody("启用本地开发身份");
    if (!(await clickNamedButton("启用本地开发身份"))) {
      throw new Error("本地开发身份按钮不可点");
    }
    await waitBody("DP3 审核员（u_dp3）");
  }

  // 1) 队列
  await cdp.send("Page.navigate", { url: `${base}/queue` });
  const queueBody = await waitBody(expectCase);
  const queueOk = queueBody.includes(expectCase) && queueBody.includes("复核队列");
  const queueShot = await shot("queue.png");

  // 2) 点进案件详情
  let clicked = false;
  for (let i = 0; i < 40 && !clicked; i++) {
    clicked = await evalValue(`(() => {
      const a = [...document.querySelectorAll('a')].find(
        (x) => x.getAttribute('href') === '/cases/${expectCase}'
      );
      if (!a) return false;
      a.click();
      return true;
    })()`);
    if (!clicked) await sleep(200);
  }
  // ★ 2026-10-20：原来等的是「案件详情」，而那个标题在**加载中**就已经出现，
  //   于是读到的是加载态（body 里只有「加载中…」）。改成等一个数据态标志。
  await waitBody("证据链");
  const caseBody = await waitBody("证据链");
  // ★ 不再硬编码 BLOCK / DP2 / H01 —— 取样案件来自真实队列，标签随数据变化。
  //   断言只锁「这一屏必须有的结构与铁律」，不锁某条案件的取值。
  const caseOk =
    clicked &&
    caseBody.includes("案件详情") &&
    caseBody.includes(expectCase) &&
    !caseBody.includes("加载中…") &&
    caseBody.includes("对外标签") &&
    caseBody.includes("待放行") &&          // 铁律：机器不得改放行状态
    caseBody.includes("覆盖证明") &&
    caseBody.includes("未评估") &&
    caseBody.includes("证据链") &&
    caseBody.includes("复核动作");
  const casePath = await evalValue("location.pathname");
  const caseShot = await shot("case.png");

  // 3) 点进报告
  // 3) 报告页 —— 直接按 URL 访问，不依赖「取样案件恰好有报告」。
  //    ★ 2026-10-20：原来靠点详情页里的报告链接，但夹具里只有 1/4 的案件有报告，
  //      取样的那条常常没有 → 断言失败但页面其实是好的。这是**夹具形态**的问题，
  //      不是页面的问题，所以改断言而不改夹具：没有报告是一个真实状态，要能单独验。
  await cdp.send("Page.navigate", { url: `${base}/reports/${expectReport}` });
  const reportBody = await waitBody("报告查看");
  await sleep(600);
  const reportBody2 = await waitBody("报告查看");
  const reportOk =
    reportBody2.includes("报告查看") &&
    reportBody2.includes(expectReport) &&
    !reportBody2.includes("加载中…") &&
    (reportBody2.includes("发布时刻") || reportBody2.includes("未发布"));
  const reportPath = await evalValue("location.pathname");
  const reportShot = await shot("report.png");

  // 4) 分类规范页（只读骨架：七轴、七步、正交字段、rule_id 查找框）
  await cdp.send("Page.navigate", { url: `${base}/taxonomy` });
  const taxonomyBody = await waitBody("分类规范");
  const taxonomyCodes = ["CHAN", "RIGHT", "SCENE", "DISC", "BRAND", "FACT", "CLAIM"];
  const taxonomyOk =
    taxonomyBody.includes("分类规范") &&
    taxonomyCodes.every((code) => taxonomyBody.includes(code)) &&
    taxonomyBody.includes("七步判定顺序") &&
    taxonomyBody.includes("正交字段");
  const taxonomyTyped = await evalValue(`(() => {
    const el = document.querySelector('#rule-lookup');
    if (!el) return false;
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      'value',
    ).set;
    setter.call(el, 'T1.1.medical-cure');
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  await sleep(200);
  await evalValue("document.querySelector('#rule-lookup')?.form?.requestSubmit()");
  await sleep(200);
  const taxonomyLookupBody = await bodyText();
  const taxonomyLookup =
    taxonomyTyped &&
    (taxonomyLookupBody.includes('未找到该 rule_id') ||
      taxonomyLookupBody.includes('归属轴'));
  const taxonomyPath = await evalValue("location.pathname");
  const taxonomyShot = await shot("taxonomy.png");

  // 5) 390px 窄屏：队列与详情不能横向溢出，队列行/主要控件至少 44px。
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await cdp.send("Page.navigate", { url: `${base}/queue` });
  await waitBody(expectCase);
  const queueMobile = await evalValue(`(() => {
    const row=document.querySelector('.queue__row');
    const controls=[...document.querySelectorAll('.queue__filter, .shell__header nav a, .shell__right select')];
    return {
      noOverflow: document.documentElement.scrollWidth <= window.innerWidth,
      rowHeight: row ? row.getBoundingClientRect().height : 0,
      controlsMin44: controls.every(x => x.getBoundingClientRect().height >= 44),
    };
  })()`);
  await cdp.send("Page.navigate", { url: `${base}/cases/${expectCase}` });
  await waitBody("证据链");
  const caseMobile = await evalValue(`(() => ({
    noOverflow: document.documentElement.scrollWidth <= window.innerWidth,
    actionButtonsMin44: [...document.querySelectorAll('.actions .btn')]
      .every(x => x.getBoundingClientRect().height >= 44),
  }))()`);
  const responsiveOk =
    Boolean(queueMobile?.noOverflow) &&
    Number(queueMobile?.rowHeight || 0) >= 44 &&
    Boolean(queueMobile?.controlsMin44) &&
    Boolean(caseMobile?.noOverflow) &&
    Boolean(caseMobile?.actionButtonsMin44);

  // ── 可选：1280×720 与 320px reflow（--desktop / --reflow）───────────────
  const viewportChecks = {};
  for (const [flagOn, w, h, key] of [
    [wantDesktop, 1280, 720, "desktop-1280x720"],
    [wantReflow, 320, 800, "reflow-320"],
  ]) {
    if (!flagOn) continue;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: w, height: h, deviceScaleFactor: 1, mobile: w < 600,
    });
    const rows = [];
    for (const p of ["/queue", `/cases/${expectCase}`]) {
      await cdp.send("Page.navigate", { url: `${base}${p}` });
      await waitBody(p === "/queue" ? expectCase : "证据链");
      rows.push(await evalValue(`({
        page: ${JSON.stringify(p)},
        noOverflow: document.documentElement.scrollWidth <= window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      })`));
    }
    viewportChecks[key] = { ok: rows.every((r) => r && r.noOverflow), rows };
  }
  const viewportOk = Object.values(viewportChecks).every((v) => v.ok);

  const result = {
    ok: queueOk && caseOk && reportOk && taxonomyOk && taxonomyLookup && responsiveOk && viewportOk,
    queue: { ok: queueOk, shot: queueShot, body: queueBody.slice(0, 500) },
    case: {
      ok: caseOk,
      clicked,
      path: casePath,
      shot: caseShot,
      body: caseBody.slice(0, 700),
    },
    report: {
      ok: reportOk,
      path: reportPath,
      shot: reportShot,
      body: reportBody2.slice(0, 600),
    },
    taxonomy: {
      ok: taxonomyOk && taxonomyLookup,
      path: taxonomyPath,
      lookup: taxonomyLookup,
      shot: taxonomyShot,
      body: taxonomyBody.slice(0, 700),
    },
    responsive: {
      ok: responsiveOk,
      viewport: "390x844",
      queue: queueMobile,
      case: caseMobile,
      ...viewportChecks,
    },
  };
  console.log(JSON.stringify(result, null, 2));
  cdp.close();
  return result.ok ? 0 : 1;
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
