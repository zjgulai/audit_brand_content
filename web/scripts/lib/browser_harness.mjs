#!/usr/bin/env node
/**
 * web/scripts/lib/browser_harness.mjs —— 前后端接线联调用的浏览器驱动（T-408 之后建）
 *
 * ## 它解决什么问题
 *
 * 本仓已有 8 个页面级脚本（check_pages / check_review_slice / a11y_check /
 * check_visual / check_login_qr / check_identity_switch / check_queue_page /
 * check_review_actions），合计 3000+ 行，**每个都自己实现了一遍「起 Chrome →
 * 连 CDP → 收消息 → 超时」**。复制 8 份的直接后果不是丑，是三条：
 *
 *   1. 修一个 CDP 缺陷要改 8 个地方，漏一个就有一条通道继续带着旧行为；
 *   2. 每个脚本的「未测」判定各自写（有的 `rc=2`、有的直接抛），
 *      于是「Chrome 起不来」在不同脚本里表现为不同的东西；
 *   3. 新写一个联调脚本，第一件事是**再复制一份**，因为它没有别的入口。
 *
 * 本模块只做那件重复的事：**起浏览器、连上去、按需调用、明确关掉**。
 * 它**不含**任何断言 —— 断言写在调用方（`web/scripts/pairing_check.mjs`），
 * 因为断言与场景绑定，而驱动与场景无关。
 *
 * ## 三条硬约束（每条都有对应断言，见 tools/verify_browser_harness.py）
 *
 * **一、Chrome 找不到 → 抛 `HarnessUntested`，不是抛普通异常。**
 *   调用方据此退 2（未测），而不是退 1（红）。「这台机器上没有 Chrome」
 *   与「页面坏了」是两件事，混成一个数就是 §2.4.1 那个病。
 *
 * **二、每个 CDP 调用都有超时。**
 *   没有超时的 await 在页面卡死时会挂住整条联调链，而挂住的表现
 *   （CI 一直跑、没有任何输出）比失败更难查。
 *
 * **三、`close()` 幂等，且进程退出时兜底杀 Chrome。**
 *   漏杀会留下 `--user-data-dir` 临时目录与一个占着端口的 Chrome。
 *   实测代价：连跑两轮联调时第二轮起不来，报的却是「端口被占用」——
 *   指向一个与本轮无关的方向。
 *
 * ## 用法（两种）
 *
 * ```js
 * import { launch, HarnessUntested } from "./lib/browser_harness.mjs";
 * const s = await launch();            // 起 Chrome + 连 CDP
 * try {
 *   await s.goto("http://127.0.0.1:5180/queue");
 *   const title = await s.text();
 * } finally {
 *   await s.close();                   // 幂等
 * }
 * ```
 *
 * CLI 方式（人工排查时最快）：
 *
 * ```bash
 * node web/scripts/lib/browser_harness.mjs goto http://127.0.0.1:5180/queue
 * node web/scripts/lib/browser_harness.mjs text
 * node web/scripts/lib/browser_harness.mjs shot /tmp/q.png
 * ```
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/** 「没测成」专用异常：调用方必须据此退 2，不许退 1。 */
export class HarnessUntested extends Error {
  constructor(message) {
    super(message);
    this.name = "HarnessUntested";
  }
}

/** 「测了但不符合预期」专用异常：调用方据此退 1。 */
export class HarnessFailed extends Error {
  constructor(message) {
    super(message);
    this.name = "HarnessFailed";
  }
}

const DEFAULT_TIMEOUT = 30_000;

export function chromeBinary() {
  return (
    process.env.CHROME_BIN ||
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  );
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * 起一个 Chrome 并连上第一个 page target。
 *
 * @param {object} [opts]
 * @param {number} [opts.port]        调试端口；默认随机空闲端口（避免连跑互相抢）
 * @param {number} [opts.width]
 * @param {number} [opts.height]
 * @param {boolean} [opts.headless=true]
 * @returns {Promise<Session>}
 */
export async function launch(opts = {}) {
  const chrome = chromeBinary();
  if (!fs.existsSync(chrome)) {
    // ★ 这一条必须是 HarnessUntested。写成普通 Error 的话，调用方
    //   catch 到它只能退 1（红），而「没装 Chrome」不是页面坏了。
    throw new HarnessUntested(`找不到 Chrome：${chrome}（可设 CHROME_BIN）`);
  }
  const port = opts.port ?? 0;
  const width = opts.width ?? 1280;
  const height = opts.height ?? 720;
  const headless = opts.headless !== false;
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "browser_harness_"));

  const args = [
    ...(headless ? ["--headless=new"] : []),
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    `--window-size=${width},${height}`,
    `--user-data-dir=${profile}`,
    // port=0 让 Chrome 自己挑，再从 DevToolsActivePort 读回来 ——
    // 先 free_port() 再交给 Chrome 有竞态（挑到别人抢走的号）。
    port === 0 ? "--remote-debugging-port=0" : `--remote-debugging-port=${port}`,
    "about:blank",
  ];

  const child = spawn(chrome, args, { stdio: "ignore" });
  let killed = false;
  const cleanup = () => {
    if (killed) return;
    killed = true;
    try {
      child.kill("SIGKILL");
    } catch {
      /* 已经退出 */
    }
    try {
      fs.rmSync(profile, { recursive: true, force: true });
    } catch {
      /* 清理失败不该影响结论 */
    }
  };
  // ★ 兜底：脚本异常退出时也不许留下 Chrome 与临时 profile。
  process.once("exit", cleanup);
  process.once("SIGINT", () => {
    cleanup();
    process.exit(2);
  });

  const deadline = Date.now() + 20_000;
  let httpPort = port;
  if (httpPort === 0) {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (;;) {
      if (Date.now() > deadline) {
        cleanup();
        throw new HarnessUntested("Chrome 未在 20s 内写出 DevToolsActivePort");
      }
      if (fs.existsSync(portFile)) {
        const first = fs.readFileSync(portFile, "utf8").split("\n")[0].trim();
        if (/^\d+$/.test(first)) {
          httpPort = Number(first);
          break;
        }
      }
      await sleep(100);
    }
  }

  let wsUrl = null;
  while (Date.now() < deadline) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${httpPort}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) {
        wsUrl = page.webSocketDebuggerUrl;
        break;
      }
    } catch {
      /* 还没起来 */
    }
    await sleep(120);
  }
  if (!wsUrl) {
    cleanup();
    throw new HarnessUntested("Chrome 起不来：拿不到 page target");
  }

  const session = new Session(wsUrl, cleanup, { width, height });
  //: 临时 profile 的真实路径。**对外暴露是为了让判据能验「关了之后它没了」**——
  //: 否则那条断言只能去猜目录（第一版猜 /tmp，在 macOS 上恒为 0 → 0，是假绿）。
  session._profileDir = profile;
  await session._connect();
  return session;
}

class Session {
  constructor(wsUrl, cleanup, size) {
    this.wsUrl = wsUrl;
    this._cleanup = cleanup;
    this._size = size;
    this._id = 0;
    this._pending = new Map();
    this._closed = false;
    this._events = [];
  }

  async _connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((res, rej) => {
      this.ws.onopen = res;
      this.ws.onerror = () => rej(new HarnessUntested("CDP WebSocket 连不上"));
    });
    this.ws.onmessage = (ev) => {
      let m;
      try {
        m = JSON.parse(ev.data);
      } catch {
        return;
      }
      // ★ 没有 id 的是**事件**（console / network / 页面异常），不是响应。
      //   第一版只处理带 id 的响应，把它们全丢了 —— 于是「页面报错」
      //   在驱动里完全不可见，调用方只能靠肉眼或截图判断。
      if (!m.id) {
        this._events.push(m);
        return;
      }
      if (!this._pending.has(m.id)) return;
      const { res, rej, timer } = this._pending.get(m.id);
      this._pending.delete(m.id);
      clearTimeout(timer);
      m.error ? rej(new HarnessFailed(JSON.stringify(m.error))) : res(m.result);
    };
  }

  /** 原始 CDP 调用。**每个都有超时**（约束二）。 */
  send(method, params = {}, timeout = DEFAULT_TIMEOUT) {
    if (this._closed) {
      return Promise.reject(new HarnessFailed("session 已关闭：" + method));
    }
    const id = ++this._id;
    return new Promise((res, rej) => {
      const timer = setTimeout(() => {
        this._pending.delete(id);
        rej(new HarnessFailed(`CDP 超时 ${timeout}ms：${method}`));
      }, timeout);
      this._pending.set(id, { res, rej, timer });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const r = await this.send("Runtime.evaluate", {
      expression: expr,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) {
      throw new HarnessFailed(
        "页面内求值抛错：" +
          (r.exceptionDetails.exception?.description || r.exceptionDetails.text),
      );
    }
    return r.result.value;
  }

  async goto(url, settleMs = 400) {
    await this.send("Page.enable");
    await this.send("Page.navigate", { url });
    const deadline = Date.now() + 20_000;
    for (;;) {
      const ready = await this.eval("document.readyState");
      if (ready === "complete") break;
      if (Date.now() > deadline) {
        throw new HarnessFailed(`导航超时：${url}`);
      }
      await sleep(80);
    }
    if (settleMs) await sleep(settleMs);
    return this.eval("location.href");
  }

  text() {
    return this.eval("document.body ? document.body.innerText : ''");
  }

  /**
   * 打开诊断采集：console 错误、未捕获异常、以及全部网络响应。
   *
   * 为什么必须显式打开而不是默认开：`Network.enable` 会让每个请求都多一条
   * 事件，几十个页面连跑时事件量可观；更实际的理由是 —— **调用方要清楚
   * 「从哪一刻开始记账」**，否则上一页的失败会算到下一页头上。
   */
  async enableDiagnostics() {
    await this.send("Runtime.enable");
    await this.send("Network.enable");
    this._events.length = 0;
    this._diagOn = true;
  }

  /** 取走从上次调用之后累积的诊断，并清空。 */
  takeDiagnostics({ reset = true } = {}) {
    const consoleErrors = [];
    const exceptions = [];
    const responses = [];
    for (const m of this._events) {
      if (m.method === "Runtime.consoleAPICalled" && m.params?.type === "error") {
        consoleErrors.push(
          (m.params.args || [])
            .map((a) => (a.value !== undefined ? String(a.value) : a.description || a.type))
            .join(" "),
        );
      } else if (m.method === "Runtime.exceptionThrown") {
        exceptions.push(
          m.params?.exceptionDetails?.exception?.description ||
            m.params?.exceptionDetails?.text ||
            "unknown",
        );
      } else if (m.method === "Network.responseReceived") {
        const r = m.params?.response || {};
        responses.push({
          url: r.url,
          status: r.status,
          type: m.params?.type,
        });
      }
    }
    if (reset) this._events.length = 0;
    return { consoleErrors, exceptions, responses };
  }

  /** 只取状态码 ≥ min 的响应（默认 400）。 */
  takeFailures(min = 400) {
    const { consoleErrors, exceptions, responses } = this.takeDiagnostics();
    return {
      consoleErrors,
      exceptions,
      failures: responses.filter((r) => r.status >= min),
      checked: responses.length,
    };
  }

  /** 等到选择器出现；超时抛 HarnessFailed（不是静默返回 null）。 */
  async waitFor(selector, timeout = 10_000) {
    const deadline = Date.now() + timeout;
    for (;;) {
      const found = await this.eval(
        `!!document.querySelector(${JSON.stringify(selector)})`,
      );
      if (found) return true;
      if (Date.now() > deadline) {
        throw new HarnessFailed(`等待超时：${selector} 未出现（${timeout}ms）`);
      }
      await sleep(100);
    }
  }

  async click(selector) {
    const out = await this.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return 'NOT_FOUND';
      el.scrollIntoView({ block: 'center' });
      el.click();
      return 'CLICKED';
    })()`);
    if (out === "NOT_FOUND") throw new HarnessFailed(`点击失败：${selector} 不存在`);
    return out;
  }

  async fill(selector, value) {
    const out = await this.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return 'NOT_FOUND';
      const proto = el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(el, ${JSON.stringify(value)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return 'FILLED';
    })()`);
    if (out === "NOT_FOUND") throw new HarnessFailed(`填写失败：${selector} 不存在`);
    return out;
  }

  async shot(filePath) {
    const r = await this.send("Page.captureScreenshot", { format: "png" });
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, Buffer.from(r.data, "base64"));
    return filePath;
  }

  /** 幂等（约束三）。 */
  async close() {
    if (this._closed) return;
    this._closed = true;
    try {
      this.ws?.close();
    } catch {
      /* 已关 */
    }
    this._cleanup();
  }
}

// ── CLI（人工排查用）───────────────────────────────────────────────────
const isCli = process.argv[1] && process.argv[1].endsWith("browser_harness.mjs");
if (isCli) {
  const [cmd, ...args] = process.argv.slice(2);
  const run = async () => {
    if (!cmd) {
      console.log(`用法：node ${process.argv[1]} <goto|text|eval|click|fill|wait|shot|size> [args]`);
      return 0;
    }
    const s = await launch({
      width: Number(process.env.BH_WIDTH || 1280),
      height: Number(process.env.BH_HEIGHT || 720),
    });
    try {
      switch (cmd) {
        case "goto":
          console.log(await s.goto(args[0]));
          break;
        case "text":
          console.log(await s.text());
          break;
        case "eval":
          console.log(JSON.stringify(await s.eval(args[0]), null, 2));
          break;
        case "click":
          console.log(await s.click(args[0]));
          break;
        case "fill":
          console.log(await s.fill(args[0], args[1]));
          break;
        case "wait":
          await s.waitFor(args[0], Number(args[1] || 10_000));
          console.log("OK " + args[0]);
          break;
        case "shot":
          console.log("saved " + (await s.shot(args[0])));
          break;
        case "size":
          console.log(JSON.stringify(s._size));
          break;
        default:
          console.error("未知命令：" + cmd);
          return 2;
      }
      return 0;
    } finally {
      await s.close();
    }
  };
  try {
    process.exit(await run());
  } catch (e) {
    // ★ 三态退出码全项目统一：2 = 未测，1 = 测了不符合预期。
    if (e instanceof HarnessUntested) {
      console.error("⚠ 未测：" + e.message);
      process.exit(2);
    }
    console.error("❌ " + (e instanceof Error ? e.message : String(e)));
    process.exit(1);
  }
}
