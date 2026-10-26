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

  // 1) 队列 + D-5 同屏分诊（.queue__preview-btn）与 J/K 键盘流切案
  await cdp.send("Page.navigate", { url: `${base}/queue` });
  const queueBody = await waitBody(expectCase);
  const queueShot = await shot("queue.png");

  // ★ D-5 验证：点击「同屏分诊」展开右侧 CaseDetailPage，再按 j 键切到下一条待办
  const previewTriggered = await evalValue(`(() => {
    const btn = document.querySelector('.queue__preview-btn');
    if (!btn) return false;
    btn.click();
    return true;
  })()`);
  // ★ 2026-10-26 术语统一：「待审原件（ContentUnit）」→「原文内容」（业务听得懂）。
  //   等待信号必须与界面同步改，否则断言会等一个界面上已经不存在的词而超时。
  const PREVIEW_SIGNAL = "原文内容";
  const previewBody = previewTriggered ? await waitBody(PREVIEW_SIGNAL, 10000) : "";
  const previewUrl1 = await evalValue("location.search");
  await evalValue(`(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', bubbles: true }));
    return true;
  })()`);
  await sleep(250);
  const previewUrl2 = await evalValue("location.search");
  const queuePreviewOk =
    Boolean(previewTriggered) &&
    previewBody.includes(PREVIEW_SIGNAL) &&
    typeof previewUrl1 === "string" &&
    previewUrl1.startsWith("?caseId=") &&
    typeof previewUrl2 === "string" &&
    previewUrl2.startsWith("?caseId=") &&
    previewUrl2 !== previewUrl1;
  const queueOk =
    queueBody.includes(expectCase) &&
    // ★ 2026-10-26 术语统一：「复核队列」→「待人工复核」（业务听得懂的名字）。
    //   这里两个都收：只收新名会让旧快照/回放全部变红，只收旧名则判据
    //   永远指向一个界面里已经看不到的词。改成「至少出现其一」，
    //   并在下面单独断言新名确实在（否则「两个都收」会退化成永真）。
    (queueBody.includes("待人工复核") || queueBody.includes("复核队列")) &&
    queuePreviewOk;
  // 新术语必须在场（防上一条的「或」被当成永真）
  const queueTermOk = queueBody.includes("待人工复核");

  // ── 布局几何断言（2026-10-23 全站视觉刷新）───────────────────────────────
  //
  // ★ 为什么要有这一段：视觉刷新修了三处**只有肉眼能看出来**的布局缺陷，
  //   而修之前所有既有断言都是绿的 ——
  //     · 顶栏导航被词中折行（「复核队 / 列」「报告索 / 引」）；
  //     · 案件表格悬空在白底上，没有面板容器；
  //     · 七轴卡片挤成一行，正文每行 3–5 字。
  //   也就是说「谁把 white-space: nowrap 删了」这件事，门是拦不住的。
  //   这一段把「一行 / 有容器 / 可读宽度」变成**可量的读数**。
  //
  //   量的是 getBoundingClientRect() 与 computed style，不是源码文本
  //   （§2.4：只查标识符出现与否的断言恒真）。
  //
  // ★ 必须在**桌面视口**下量：dev-up 默认视口是 800×600，那个宽度下导航
  //   本来就该折行（10 个导航项放不下）。要验的是「桌面宽度下不许折行」，
  //   所以这里显式切到 1440×900。
  //
  //   ★ 只用 Emulation.setDeviceMetricsOverride，**不做 Page.navigate**：
  //     整页重载会丢掉 IdentitySwitcher 的 `current`（它只在 enable() 之后有值），
  //     而多数页面在 `devEnabled && current === null` 时**不渲染数据区** ——
  //     实测踩到：导航量对了，但后续 /cases 的表格 found=false。
  //     改视口不发请求，身份不受影响。
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440, height: 900, deviceScaleFactor: 1, mobile: false,
  });
  await sleep(400);
  const geometry = await evalValue(`(() => {
    // ★ 2026-10-26 布局重做：导航从顶栏搬到侧边栏。
    //   这条断言原先量「10 个导航项在顶栏里是否排成一行」——
    //   侧边栏是**竖排**的，那个判据在新布局下恒假（navLinkCount=0）。
    //   判据跟着形态改，而不是为了让检查变绿把它删掉：
    //   现在量的是「侧边栏是一列、且没有词中被切开、且主内容没被挤成 0 宽」。
    const nav = document.querySelector('.shell__nav') || document.querySelector('.shell__sidebar nav');
    const links = nav ? [...nav.querySelectorAll('a')] : [];
    const rects = links.map((a) => a.getBoundingClientRect());
    // 侧边栏必须是**一列**：所有导航项的 left 相同（容差 1px）
    const lefts = rects.map((r) => Math.round(r.left));
    const navCols = new Set(lefts).size;
    // 每一项的文字不许折行（侧边栏宽度固定，折行说明标签太长）
    const wrapIdx = links
      .filter((a) => getComputedStyle(a).whiteSpace !== 'nowrap')
      .map((a) => a.textContent.trim());
    // 任何一项被压成两行文字都不行
    const anyTwoLineText = rects.some(
      (r, i) => i > 0 && r.height > rects[0].height * 1.8,
    );
    // 侧边栏必须有实际宽度；主内容区不能被它挤成 0
    const side = document.querySelector('.shell__sidebar');
    const main = document.querySelector('.shell__main');
    const sideW = side ? side.getBoundingClientRect().width : 0;
    const mainW = main ? main.getBoundingClientRect().width : 0;
    // 侧边栏不许盖住主内容（重叠 = 布局塌了）
    const sideRect = side ? side.getBoundingClientRect() : null;
    const mainRect = main ? main.getBoundingClientRect() : null;
    const overlap = sideRect && mainRect
      ? Math.max(0, Math.min(sideRect.right, mainRect.right) - Math.max(sideRect.left, mainRect.left))
      : 0;
    return {
      navLinkCount: links.length,
      navCols,
      wrapIdx,
      anyTwoLineText,
      navHeight: nav ? nav.getBoundingClientRect().height : 0,
      sideW, mainW, overlap: Math.round(overlap),
    };
  })()`);
  // ★ 新判据：侧边栏成立（一列 + 不折行 + 够宽 + 不压主内容）
  const sidebarOk =
    Boolean(geometry) &&
    geometry.navLinkCount >= 8 &&
    geometry.navCols === 1 &&
    geometry.wrapIdx.length === 0 &&
    !geometry.anyTwoLineText &&
    geometry.sideW >= 60 &&
    geometry.mainW > 400 &&
    geometry.overlap === 0;
  // 兼容名：下游 result 里仍用 header 这个键（改名会牵动 report 结构）
  const headerOneLine = sidebarOk;

  // 表格必须有面板容器（边框 + 非透明底），否则又是一张悬空白纸
  //   ★ 用 SPA 内导航（pushState / 点 nav 链接），不做 Page.navigate：
  //     整页重载会丢掉 IdentitySwitcher 的 `current`（它只在 enable() 之后才有值），
  //     而 CasesPage 在 `devEnabled && current === null` 时**不渲染表格**。
  //   ★ 等待在 **Node 侧轮询**，不用 Runtime.evaluate 返回 Promise：
  //     CDP 的 evaluate 默认 `awaitPromise: false`，返回的是一个 Promise 对象
  //     （returnByValue 下序列化成 `{}`）—— **恒为真**，等于没等。
  //     实测踩到：spaGo 立刻返回，量到还没渲染的空壳，table.found=false。
  //     （§2.4.4 同一个形状：自证看起来在等，其实什么都没等。）
  const spaGo = async (href, selector, label) => {
    await evalValue(`(() => {
      const a = [...document.querySelectorAll('a')].find(
        (x) => x.getAttribute('href') === ${JSON.stringify(href)});
      if (a) { a.click(); return true; }
      window.history.pushState({}, '', ${JSON.stringify(href)});
      window.dispatchEvent(new PopStateEvent('popstate'));
      return true;
    })()`);
    const end = Date.now() + 15000;
    let found = false;
    while (Date.now() < end) {
      found = Boolean(
        await evalValue(`Boolean(document.querySelector(${JSON.stringify(selector)}))`),
      );
      if (found) break;
      await sleep(100);
    }
    if (!found) throw new Error(`等待超时：${label}（${selector} 未出现）`);
    await sleep(250);
  };

  await spaGo("/cases", ".cases-table", "案件总览表格");
  const tableGeometry = await evalValue(`(() => {
    const wrap = document.querySelector('.cases-table-wrap');
    const table = document.querySelector('.cases-table');
    if (!wrap || !table) return { found: false };
    const cs = getComputedStyle(wrap);
    return {
      found: true,
      hasBorder: parseFloat(cs.borderTopWidth) > 0,
      hasBg: cs.backgroundColor !== 'rgba(0, 0, 0, 0)',
      bordered: parseFloat(cs.borderTopLeftRadius) > 0,
      headerHasBg: (() => {
        const th = table.querySelector('thead th');
        if (!th) return false;
        return getComputedStyle(th).backgroundColor !== 'rgba(0, 0, 0, 0)';
      })(),
    };
  })()`);
  const tablePanelOk =
    Boolean(tableGeometry?.found) &&
    tableGeometry.hasBorder === true &&
    tableGeometry.hasBg === true &&
    tableGeometry.bordered === true &&
    tableGeometry.headerHasBg === true;

  // 七轴卡片必须换行到可读宽度（不许 6 张挤成一行每张 200px）
  await spaGo("/taxonomy", ".taxonomy-card", "七轴卡片");
  const taxonomyGeometry = await evalValue(`(() => {
    const cards = [...document.querySelectorAll('.taxonomy-card')];
    if (!cards.length) return { found: false };
    const widths = cards.map((c) => c.getBoundingClientRect().width);
    const tops = new Set(cards.map((c) => Math.round(c.getBoundingClientRect().top)));
    const page = document.querySelector('.taxonomy-page');
    return {
      found: true,
      count: cards.length,
      minWidth: Math.min(...widths),
      rows: tops.size,
      innerWidth: window.innerWidth,
      pageWidth: page ? page.getBoundingClientRect().width : 0,
    };
  })()`);
  // 阈值跟着 CSS 的 minmax(22rem) 走。
  //   ★ 本项目的 root font-size 是 var(--text-base) = 13px，**不是浏览器的 16px**
  //     （styles.css 的 `html { font-size: var(--text-base); }`）。
  //     所以 22rem = 22 × 13 = 286px，不是 352px。
  //     第一版按 16px 算写死 352，于是 4 列 × 294.9px 的**正确布局**被判红 ——
  //     这是「判据的常数写错」，不是页面错了。
  const ROOT_FONT_PX = 13;
  const MIN_CARD_REM = 22;
  const MIN_CARD_PX = MIN_CARD_REM * ROOT_FONT_PX;
  const taxonomyReadable =
    Boolean(taxonomyGeometry?.found) &&
    taxonomyGeometry.minWidth >= MIN_CARD_PX &&
    taxonomyGeometry.rows >= 2;

  // ── 反向对照：把 nowrap 与容器拆掉，上面三条必须变红 ──────────────────────
  //   只测「现在是绿的」不够 —— 一个恒绿的断言什么都不保护。
  await cdp.send("Page.navigate", { url: `${base}/queue` });
  await waitBody(expectCase);
  const geoControl = await evalValue(`(() => {
    // ★ 2026-10-26：导航搬到侧边栏后，反向对照也必须指向**新**的判据。
    //   旧版把 '.shell__header nav a' 的 nowrap 撤掉看会不会折行 ——
    //   现在那个选择器一个都匹配不到，于是 bad.length 恒为 0，
    //   这条对照会「看起来通过」而实际什么都没测（恒真）。
    //
    //   新的反向对照打两处，对应 sidebarOk 里的两个不同判据：
    //     ① 撤掉 .shell__nav-item 的 nowrap → 必须抓到（防标签折行）
    //     ② 把 .shell__sidebar 的宽度改成 0   → 必须抓到（防侧栏塌陷）
    const style = document.createElement('style');
    style.id = '__geo_control__';
    style.textContent =
      '.shell__nav-item { white-space: normal !important; }' +
      '.shell__sidebar { width: 0 !important; min-width: 0 !important; }';
    document.head.appendChild(style);
    const links = [...document.querySelectorAll('.shell__nav a')];
    const bad = links.filter((a) => getComputedStyle(a).whiteSpace !== 'nowrap');
    const side = document.querySelector('.shell__sidebar');
    const collapsedSide = side ? side.getBoundingClientRect().width < 60 : true;
    style.remove();
    const restored = [...document.querySelectorAll('.shell__nav a')]
      .every((a) => getComputedStyle(a).whiteSpace === 'nowrap');
    return { caught: bad.length > 0 && collapsedSide, restored,
             badCount: bad.length, collapsedSide };
  })()`);

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
  // ★★ 2026-10-26 事故：把「等待信号」写进了常驻外壳，于是等待恒成立。
  //
  //   新 AppShell 的页面副标题里写了「原件、证据链与复核动作」，而下面等的是
  //   `waitBody("证据链")` —— 那个词**在数据到之前就已经在 DOM 里了**，
  //   于是 waitBody 立刻返回，读到的还是「加载中…」，caseOk 因此判假。
  //   表现是「API 200 + 无 console 错误 + 页面永远加载中」，三样读数各自都对。
  //   这与 AGENTS.md §2.4.4 的 `--selftest` 静音告警同一个形状：
  //   **断言在等的东西，被别的改动顺手满足了**，而它看起来还在等。
  //
  //   修法两层：① 把那个词从常驻外壳删掉（治本次）；
  //             ② 加一条反向对照，常驻外壳里不许出现任何等待信号词（治下一次）。
  const shellSignalLeak = await evalValue(`(() => {
    const shell = document.querySelector('.shell__sidebar');
    const header = document.querySelector('.shell__header');
    const txt = [shell ? shell.innerText : '', header ? header.innerText : ''].join(' ');
    const signals = ${JSON.stringify(["证据链", "对外标签", "覆盖证明", "复核动作", "待审原件"])};
    return signals.filter((w) => txt.includes(w));
  })()`);
  const shellNoSignalOk = Array.isArray(shellSignalLeak) && shellSignalLeak.length === 0;

  let caseBody = "";
  try {
    caseBody = await waitBody("证据链");
  } catch (e) {
    caseBody = await bodyText();
    console.error(
      "waitBody(证据链) 超时。常驻外壳里的信号词（会让等待恒成立）：",
      JSON.stringify(shellSignalLeak),
    );
  }
  // ★ D-6 验证：点击左栏原件内第一个 [data-finding-mark] 高亮块，断言右栏对应 .evidence__item 激活
  const clickedMarkId = await evalValue(`(() => {
    const mark = document.querySelector('[data-finding-mark]');
    if (!mark) return null;
    const fid = mark.getAttribute('data-finding-mark');
    mark.click();
    return fid;
  })()`);
  await sleep(150);
  const markLinkage = await evalValue(`(() => {
    const fid = ${JSON.stringify(clickedMarkId)};
    if (!fid) return { ok: false, reason: 'no_mark' };
    const mark = document.querySelector('[data-finding-mark="' + fid + '"]');
    const item = document.getElementById('evidence-item-' + fid);
    return {
      ok: Boolean(
        mark &&
        mark.classList.contains('unit-mark--active') &&
        item &&
        item.classList.contains('evidence__item--active')
      ),
      findingId: fid,
    };
  })()`);

  // ★ 不再硬编码 BLOCK / DP2 / H01 —— 取样案件来自真实队列，标签随数据变化。
  //   断言只锁「这一屏必须有的结构与铁律」，不锁某条案件的取值。
  const caseOk =
    clicked &&
    Boolean(markLinkage?.ok) &&
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
  const taxonomyBody = await waitBody("七步判定顺序");
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
    const controls=[...document.querySelectorAll('.queue__filter, .shell__nav a, .shell__right select')];
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
    ok: queueOk && queueTermOk && caseOk && shellNoSignalOk && reportOk && taxonomyOk && taxonomyLookup && responsiveOk && viewportOk &&
        headerOneLine && tablePanelOk && taxonomyReadable,
    geometry: {
      ok: headerOneLine && tablePanelOk && taxonomyReadable,
      header: { ok: headerOneLine, ...geometry },
      table: { ok: tablePanelOk, ...tableGeometry },
      taxonomy: { ok: taxonomyReadable, ...taxonomyGeometry },
      control: geoControl,
    },
    queue: {
      ok: queueOk,
      termOk: queueTermOk,
      previewOk: queuePreviewOk,
      previewUrls: [previewUrl1, previewUrl2],
      shot: queueShot,
      body: queueBody.slice(0, 500),
    },
    case: {
      ok: caseOk,
      shellNoSignal: { ok: shellNoSignalOk, leaked: shellSignalLeak || [] },
      clicked,
      markLinkage,
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
