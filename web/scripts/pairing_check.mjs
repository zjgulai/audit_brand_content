#!/usr/bin/env node
/**
 * web/scripts/pairing_check.mjs —— 前后端**接线**联调（pairing）
 *
 * ## 它与 check_pages.mjs 的分工
 *
 * `check_pages.mjs`（既有 606 行）验的是「页面长得对」：队列 → 详情 → 报告的
 * 结构与几何。本文件验的是**接线**：
 *
 *   · 页面渲染时打出去的每一个 API 请求都拿到了 2xx（不是 4xx/5xx、不是 CORS 失败）
 *   · 页面**没有** console error、没有未捕获异常
 *   · 写入口点下去之后，后端确实收到了写请求（不是前端静默 no-op）
 *   · 点下去的写请求**不是 501**（那是「开发装配能点、生产返 501」的现场表现）
 *
 * 换句话说：`check_pages` 问「画对了没有」，本文件问「线接上了没有」——
 * 后者是 T-401/T-402/T-403/T-408 这一批票的验收面，也是「读数变绿 ≠ 能力建成」
 * 最容易漏掉的那一层。
 *
 * ## 前置
 *
 * 需要一个**已经在跑**的前后端。推荐：
 *
 * ```bash
 * bash web/scripts/dev-up.sh --keep      # 起服务并保留（会打印 WEB_PORT）
 * node web/scripts/pairing_check.mjs --base http://127.0.0.1:<WEB_PORT> \
 *      --cookie "session=<...>" --pages /queue,/cases,/appeals
 * ```
 *
 * ## 退出码（三态，全项目统一）
 *
 *   0 = 全部页面接线通过
 *   1 = 有页面接线失败（4xx/5xx、console error、未捕获异常）
 *   2 = 未测（Chrome 不在 / base 连不上 / 没有 cookie）
 *
 * ★ `2` 必须在 `1` 之前判：连不上服务时若报 `1`，读的人会以为「页面坏了」，
 *   而去改前端 —— 那是本项目反复记过的那个形状（§2.4.1 第 4 行）。
 */
import fs from "node:fs";
import path from "node:path";
import { launch, HarnessUntested, HarnessFailed } from "./lib/browser_harness.mjs";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const base = arg("base", process.env.PAIRING_BASE || "http://127.0.0.1:5180")
  .replace(/\/$/, "");
const cookie = arg("cookie", process.env.PAIRING_COOKIE || "");
const pagesArg = arg(
  "pages",
  "/queue,/cases,/submit,/inbox,/appeals,/release,/takedown,/reports,/taxonomy,/admin/grants,/admin/sessions",
);
const shots = arg("screenshots", "");
const expectWrite = arg("expect-write", ""); // 形如 "POST /api/v1/appeals"
// ★ 前端打后端走的是 Vite 的 `/review-api` 前缀（`vite.config.ts` 里 rewrites
//   到 `/api/v1`）。直接打 `/api/v1/...` 会落到 Vite 自己身上、拿 404 ——
//   而那个 404 看起来像「后端没这个端点」。
const API_PREFIX = arg("api-prefix", "/review-api");
const settle = Number(arg("settle", "700"));

const pages = pagesArg.split(",").map((s) => s.trim()).filter(Boolean);

/** 允许的 4xx：这些是**页面的正确反应**，不是接线断了。 */
const ALLOW_4XX = new Set([
  // 「未登录」是本轮联调的合法前提（不带 cookie 时每个页都该 401）
  "401",
]);

function loadCookie() {
  if (!cookie) return null;
  // 支持 "session=xxx; csrf=yyy" 形式
  return cookie;
}

async function main() {
  const ck = loadCookie();

  // 先确认服务活着 —— 这一步必须在起 Chrome 之前做。
  // 否则 Chrome 起得来、页面打开是「连接被拒」，会被记成「页面坏」。
  if (!ck && !process.env.PAIRING_ALLOW_ANON) {
    console.error("⚠ 未测：没有 cookie（用 --cookie 或 PAIRING_COOKIE 给）");
    return 2;
  }
  let healthy = false;
  try {
    const r = await fetch(`${base}/`, { signal: AbortSignal.timeout(5000) });
    healthy = r.status < 500;
  } catch {
    healthy = false;
  }
  if (!healthy) {
    console.error(`⚠ 未测：${base} 连不上（先起 dev-up.sh）—— 这不是页面坏了`);
    return 2;
  }

  const session = await launch();
  // ★ 必须**把 cookie 塞进浏览器**，不能只拿它当「跑不跑」的开关。
  //   第一版就是只当开关，于是 `--expect-write` 的请求带着浏览器自己的
  //   （空）会话打过去 → 401 → 而 401 会被读成「白名单没放开」的反面证据。
  //   实测症状：明明 `/api/v1/appeals` 已经放开，探针一直报 401。
  try {
    const origin = new URL(base).origin;
    for (const pair of ck.split(";")) {
      const idx = pair.indexOf("=");
      if (idx <= 0) continue;
      const name = pair.slice(0, idx).trim();
      const value = pair.slice(idx + 1).trim();
      await session.send("Network.setCookie", {
        name, value, domain: new URL(base).hostname, path: "/",
      });
      void origin;
    }
  } catch (e) {
    console.error("⚠ 未测：cookie 注入失败：" + e.message);
    await session.close();
    return 2;
  }
  const report = [];
  let failures = 0;
  try {
    await session.enableDiagnostics();
    for (const p of pages) {
      const url = `${base}${p}`;
      const row = { page: p, status: "?", failures: [], consoleErrors: [], exceptions: [] };
      try {
        // 清掉上一页残留的事件再导航。
        // ★ 顺便记一个**我一开始判错的读数**：每页 requests 都在 36 左右、
        //   而且几乎一样，看起来像「一份输入被重复读了 N 次」。实测
        //   （`takeFailures()` 连调两次，第二次 checked=0）证明缓冲区是正常
        //   清空的，36 是真的：Vite dev 按**文件**发 ESM 模块，一个页面就要
        //   几十个模块请求。页面之间的差异（release=37 / reports=38）也能看出来。
        //   —— 「数字整齐得可疑」不等于「判据坏了」，先去证它，不要先改它。
        await session.takeDiagnostics();
        await session.goto(url, settle);
        const diag = session.takeFailures(400);
        row.consoleErrors = diag.consoleErrors;
        row.exceptions = diag.exceptions;
        row.failures = diag.failures
          .filter((f) => !ALLOW_4XX.has(String(f.status)))
          // ★ favicon 是浏览器自己发起的，不是页面接的线。
          //   把它算成接线失败会让**每一个**页面都红，从而掩盖真正的 404。
          .filter((f) => !/\/favicon\.ico$/.test(f.url))
          .map((f) => `${f.status} ${f.url}`);
        row.checked = diag.checked;
        row.status = row.failures.length === 0
          && row.consoleErrors.length === 0
          && row.exceptions.length === 0
          ? "ok"
          : "fail";
      } catch (e) {
        row.status = "fail";
        row.error = e instanceof Error ? e.message : String(e);
      }
      if (shots) {
        try {
          await session.shot(path.join(shots, p.replace(/[^\w]+/g, "_") + ".png"));
        } catch {
          /* 截图失败不影响判据 */
        }
      }
      if (row.status !== "ok") failures += 1;
      report.push(row);
      const flag = row.status === "ok" ? "✅" : "❌";
      console.log(
        `${flag} ${p.padEnd(20)} requests=${row.checked ?? "-"} ` +
          `5xx/4xx=${row.failures.length} console=${row.consoleErrors.length} ` +
          `exc=${row.exceptions.length}`,
      );
      for (const f of row.failures) console.log(`     · ${f}`);
      for (const c of row.consoleErrors) console.log(`     · console: ${c.slice(0, 200)}`);
      for (const x of row.exceptions) console.log(`     · exception: ${x.slice(0, 200)}`);
    }

    // 可选：一次显式写请求的接线检查（点按钮 → 后端收到 → 不是 501）
    if (expectWrite) {
      const [method, rawPath] = expectWrite.split(" ");
      // 允许调用方写真正的后端路径（`/api/v1/...`），这里转成浏览器可达的前缀。
      const apiPath = rawPath.replace(/^\/api\/v1/, API_PREFIX);
      const res = await session.eval(`(async () => {
        const csrf = (document.cookie.split('; ').find(c => c.startsWith('csrf=')) || '').split('=')[1] || '';
        const r = await fetch(${JSON.stringify(apiPath)}, {
          method: ${JSON.stringify(method)},
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          credentials: 'include',
          body: '{}',
        });
        return { status: r.status, text: (await r.text()).slice(0, 300) };
      })()`);
      const code = Number(res?.status);
      // ★ 501 单独点名：它是「开发装配能点、生产返 501」的现场指纹。
      if (code === 404 && rawPath !== apiPath) {
        // 404 在「经代理的写请求」上有两种含义，必须分开说：
        //   a) 资源不存在（正常的业务 404）
        //   b) **代理/路由没接上**（请求根本没到后端）
        // 这里额外打一次后端直连探针来区分 —— 否则 404 会被读成 a，
        // 而实际是 b，然后有人去查业务代码。
        const probe = await session.eval(`(async () => {
          const r = await fetch(${JSON.stringify(apiPath)}, { method: "OPTIONS" });
          return r.status;
        })()`);
        console.log(`   · 404 归因探针：OPTIONS ${apiPath} → ${probe}`);
      }
      if (code === 501) {
        console.log(`❌ ${expectWrite} → 501 capability_not_enabled（白名单没放开）`);
        failures += 1;
      } else if (code >= 500) {
        console.log(`❌ ${expectWrite} → ${code}（服务端错误）`);
        failures += 1;
      } else {
        console.log(`✅ ${expectWrite} → ${code}（接线通，非 501）`);
      }
    }
  } finally {
    await session.close();
  }

  if (shots) {
    fs.mkdirSync(shots, { recursive: true });
    fs.writeFileSync(path.join(shots, "pairing-report.json"),
      JSON.stringify(report, null, 2));
  }
  console.log("----------------------------------------");
  if (failures === 0) {
    console.log(`✅ ${pages.length} 页接线全通`);
    return 0;
  }
  console.log(`❌ ${failures}/${pages.length} 页接线有问题`, );
  return 1;
}

try {
  process.exit(await main());
} catch (e) {
  if (e instanceof HarnessUntested) {
    console.error("⚠ 未测：" + e.message);
    process.exit(2);
  }
  if (e instanceof HarnessFailed) {
    console.error("❌ " + e.message);
    process.exit(1);
  }
  console.error("⚠ 未测（驱动自身异常）：" + (e instanceof Error ? e.message : String(e)));
  process.exit(2);
}
