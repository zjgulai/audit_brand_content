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
let cdp;
async function currentSessionCookie() {
  if (cdp) {
    try {
      const devCookies = await cdp.send("Network.getCookies", { urls: [base] });
      const found = devCookies.cookies?.find((item) => item.name === "session")?.value;
      if (found) activeCookie = found;
    } catch {
      /* ignore */
    }
  }
  return activeCookie;
}
async function apiCase() {
  const sess = await currentSessionCookie();
  const response = await fetch(`${api}/api/v1/cases/${encodeURIComponent(caseId)}`, {
    headers: { Cookie: `session=${sess}` },
  });
  if (!response.ok) throw new Error(`GET case → HTTP ${response.status}`);
  return response.json();
}

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
  /**
   * 切换本地开发身份（AppShell 的 select）。
   *
   * ★ 为什么要有它：不同页面按**不同角色**断言 —— 下线台要 signer
   *   （`_ROLE_CAPS` 里只有它有 takedown.execute），复核台要 dp3。
   *   不切身份就会撞 403，而那个 403 长得像权限缺陷。
   *
   * ★ 切换会换一个 HttpOnly session cookie，所以切完之后
   *   `currentSessionCookie()` 必须重新读 —— 它已经是每次现读的，
   *   但 `activeCookie` 这个缓存变量要清掉，否则后续 fetch 用的还是旧 cookie
   *   （症状是「切了身份但看到的是上一个人的数据」）。
   */
  const switchDevIdentity = async (principalId) => {
    const changed = await ev(`(() => {
      const sel = document.querySelector('select[aria-label="切换本地开发身份"]');
      if (!sel) return 'NO_SELECT';
      const opt = [...sel.options].find(o => o.value === ${JSON.stringify(principalId)});
      if (!opt) return 'NO_OPTION';
      const setter = Object.getOwnPropertyDescriptor(
        HTMLSelectElement.prototype, 'value').set;
      setter.call(sel, ${JSON.stringify(principalId)});
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      return 'SWITCHING';
    })()`);
    if (changed !== "SWITCHING") {
      throw new Error(`切换开发身份失败：${changed}（目标 ${principalId}）`);
    }
    await waitEval(
      `document.querySelector('select[aria-label="切换本地开发身份"]')?.value === ${JSON.stringify(principalId)}`,
      `切到 ${principalId}`,
    );
    // 等身份生效（会换 session cookie）
    await sleep(400);
    activeCookie = "";
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

  // ★ D-3 修复与验证：证据链内 candidate finding 就地点击「确认违规」，后端不返回 404，前端显示「已确认 f-...」
  await waitEval(
    `[...document.querySelectorAll('[data-finding-adjudicate] button')].some(x=>x.textContent?.trim()==='确认违规' && !x.disabled)`,
    "确认违规按钮可用",
  );
  const confirmedFindingId = await ev(`(() => {
    const box = document.querySelector('[data-finding-adjudicate]');
    if (!box) return null;
    const fid = box.getAttribute('data-finding-adjudicate');
    const btn = [...box.querySelectorAll('button')].find(x => x.textContent?.trim() === '确认违规' && !x.disabled);
    if (!btn) return null;
    btn.click();
    return fid;
  })()`);
  if (!confirmedFindingId) {
    throw new Error("未找到可点击的确认违规按钮");
  }
  await waitText(`已确认 ${confirmedFindingId}`);

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

  // ★ D-4 新建 7 页（P-01 / P-02 / P-03 / P-06 / P-07 / P-08 / P-11 / P-12）真实浏览器交互覆盖：
  const spaGoto = async (href) => {
    const clickedNav = await ev(`(() => {
      const a = [...document.querySelectorAll('a')].find(x => x.getAttribute('href') === ${JSON.stringify(href)});
      if (a) { a.click(); return true; }
      window.history.pushState({}, '', ${JSON.stringify(href)});
      window.dispatchEvent(new PopStateEvent('popstate'));
      return true;
    })()`);
    if (!clickedNav) throw new Error(`SPA 导航失败：${href}`);
  };
  const fillInput = async (selector, val) => {
    await waitEval(
      `Boolean(document.querySelector(${JSON.stringify(selector)}))`,
      `等待控件渲染：${selector}`,
    );
    const ok = await ev(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const set = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (!set) return false;
      set.call(el, ${JSON.stringify(val)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`);
    if (!ok) throw new Error(`找不到输入框：${selector}`);
  };

  // 1) P-06 申诉中心（/appeals）：真实填写表单并提交发起申诉 + UI 状态与列表卡片回读
  await spaGoto("/appeals");
  // ★ 2026-10-26 术语：标题去掉内部票号（「申诉中心（P-06）」→「申诉中心」）。
  //   等待信号跟着改，否则断言会等一个界面上已不存在的串。
  await waitText("申诉中心");
  await fillInput("#appeal-case-id", caseId);
  await fillInput("#appeal-reason", "CDP 浏览器真实提交申诉测试：请求复核上下文");
  await click("提交申诉");
  await waitText("已受理（状态：open，SLA：2 个工作日）");
  let knownTakedownReadBack = null;
  const createdAppealId = await ev(`(() => {
    const m = document.body.innerText.match(/申诉\\s+(appeal-[\\w-]+|ap-[\\w-]+)\\s+已受理/);
    return m ? m[1] : null;
  })()`);
  if (!createdAppealId) {
    throw new Error("P-06 未在页面上显示新建的 appeal_id（appeal-...）");
  }

  // 2) P-08 下线任务台（/takedown）：真实点击 Start → 弹出回填框 Complete → GET /api/v1/takedown-tasks 回读
  //
  // ★ 必须先切到**签发人**身份。下线执行走的是「角色能力 + 人级名单」两道：
  //   `_ROLE_CAPS` 里只有 signer 有 `takedown.execute`（dp3/dp4 只有
  //   case.review / appeal.handle），所以 u_dp3 点 Start **必然** 403 ——
  //   而那个 403 读起来像权限缺陷，实际是「夹具用错了身份」。
  //   实测代价：`bash web/scripts/dev-up.sh` 在 [8/11] 恒失败 rc=1。
  //
  // ★ 不改成「把 takedown.execute 加给 dp3」：角色表是产品口径（UIUX §1.5
  //   把下线执行放在签发人），为了跑通夹具去改它，等于让本地行为与生产不一致。
  //   夹具该跟着产品走，不是反过来。
  await switchDevIdentity("u_signer");
  await spaGoto("/takedown");
  await waitText("违规下架");
  await waitText("td-smoke-1");
  await click("开始执行（Start）");
  await waitText("已执行 start → 当前状态：in_progress");
  await click("完成并回填证据（Complete）");
  await waitText("完成下线证据回填");
  await fillInput("#td-ev-receipt", "AMZ-RM-CDP-001");
  await click("提交回填并结案");
  await waitText("已完成证据回填并结案（completed，停止每日提醒）");
  const tdResp = await fetch(`${api}/api/v1/takedown-tasks`, {
    headers: { Cookie: `session=${await currentSessionCookie()}` },
  });
  if (!tdResp.ok) throw new Error(`GET /takedown-tasks → HTTP ${tdResp.status}`);
  const tdBody = await tdResp.json();
  // ★ `GET /api/v1/takedown-tasks` 返回的是 `{tasks, metrics}`（T-312d 起
  //   任务年龄由后端 metrics_view 算），**不是数组**。
  //   这里原先写的是 `Array.isArray(tdList) ? ... : null` —— 于是无论读写侧
  //   是否正常，它都得到 null，报「回读不是 completed」。
  //   也就是说这条断言**从来没有真正跑过**：它红的时候看起来像业务缺陷。
  const tdList = Array.isArray(tdBody) ? tdBody : (tdBody?.tasks ?? []);
  const completedTd = tdList.find((t) => t.task_id === "td-smoke-1") ?? null;
  if (!completedTd || completedTd.state !== "completed") {
    // ★ 读侧的另一处「写完读不回」（已登记 T-401b，本票不修）：
    //   开发装配的写落在内存 repo，而 GET 读 frozen `takedown-tasks.json`，
    //   于是 start/complete 都 200、读回仍是 pending。
    //   这里区分「写失败」与「写成功但读不回」，因为两者的下一步完全不同。
    if (completedTd && completedTd.state !== "completed") {
      // ★ 已知缺陷（T-401b 登记）：开发装配的写落在内存 repo，而 GET 读
      //   frozen `takedown-tasks.json` —— 于是「写 200、读回 pending」。
      //   这里**不把它算成通过**（`ok:false` 会进最终汇总），也**不静默忽略**：
      //   打一行显式告警，并把已知性写进返回体，让读的人分得清
      //   「新坏了一个」与「还是那个已登记的」。
      knownTakedownReadBack = {
        state: completedTd.state,
        known_issue: "T-401b: dev write goes to in-memory repo, GET reads frozen",
      };
      console.warn(
        `⚠ 已知缺陷 T-401b：下线任务写后读不回（state=${completedTd.state}）` +
          `—— 写落在内存 repo、读走 frozen。本步骤的写动作本身已成功。`,
      );
    }
    throw new Error(`下线任务回读里找不到 td-smoke-1：${JSON.stringify(tdList).slice(0, 200)}`);
  }

  // 切回 DP3：后面的提交/收件箱/授权治理按审核员口径断言（与步骤 1 同一身份）。
  await switchDevIdentity("u_dp3");

  // 3) P-07 签发中心（/release/:caseId）：真实填写理由与 step_up_token 并点击确认签发放行
  await spaGoto(`/release/${encodeURIComponent(caseId)}`);
  await waitText("飞书 SSO Step-Up 二次认证与受控签发");
  await fillInput("#release-reason", "CDP 签发门测试理由");
  await fillInput("#release-stepup", "stepup-test-token");
  await click("确认签发放行");
  await waitText("签发门拦截");

  // 4) P-01 提交审查页（/submit）：真实填写正文并点击提交审查单
  await spaGoto("/submit");
  await waitText("提交内容审查");
  await fillInput("#submit-text", "Momcozy 穿戴式吸奶器日常护理说明");
  await click("提交审查单");
  await waitEval(
    `document.body.innerText.includes('提交未通过') || document.body.innerText.includes('提交已受理')`,
    "P-01 提交响应已渲染",
  );

  // 5) P-02 收件箱（/inbox）：真实点击「标记已读（Read）」
  await spaGoto("/inbox");
  await waitText("待办收件箱");
  await waitText("notif-smoke-1");
  await click("标记已读（Read）");
  await waitText("notif-smoke-1 已");

  // 6) P-03 案件总览（/cases）：真实点击五标签筛选按钮
  await spaGoto("/cases");
  // ★ 2026-10-26 术语统一：页面文案改成业务话术，
  //   这里等的东西也跟着改 —— 等待信号必须指向**界面上真的存在**的字。
  //   「全量可读案件视图」→「支持检索已归档与处理中的全部送审内容」。
  //   ★ 同时把下面按钮文案的 'REVIEW' 换成「待人工复核」：五标签已经
  //     显示成业务名，再按英文匹配会找不到按钮（实测 0 个匹配）。
  await waitText("支持检索已归档与处理中的全部送审内容");
  const filterClicked = await ev(`(() => {
    const btn = [...document.querySelectorAll('.queue__filter')].find(x => x.textContent?.includes(${JSON.stringify("待人工复核")}));
    if (!btn) return false;
    btn.click();
    return true;
  })()`);
  if (!filterClicked) throw new Error("P-03 找不到「待人工复核」筛选按钮");
  await waitEval(
    `[...document.querySelectorAll('.queue__filter')].find(x => x.textContent?.includes(${JSON.stringify("待人工复核")}))?.getAttribute('aria-pressed') === 'true'`,
    "P-03 案件总览筛选按钮激活",
  );

  // 7) P-11 授权治理（/admin/grants）与 P-12 会话审计（/admin/sessions）
  await spaGoto("/admin/grants");
  await waitText("授权治理");
  await fillInput("#grant-user", "u_signer_2");
  await fillInput("#grant-reason", "CDP 授权提案测试");
  await click("提交授权提案");
  await waitText("提交响应（HTTP");

  await spaGoto("/admin/sessions");
  await waitText("安全审计");
  await waitText("安全与审计契约状态");

  console.log(JSON.stringify({
    ok: true,
    known_issues: knownTakedownReadBack ? [knownTakedownReadBack] : [],
    case_id: caseId,
    adjudicated_finding_id: confirmedFindingId,
    appeal_id: createdAppealId,
    takedown_task: { id: completedTd.task_id, state: completedTd.state },
    new_pages_interacted: ["P-01", "P-02", "P-03", "P-06", "P-07", "P-08", "P-11", "P-12"],
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
