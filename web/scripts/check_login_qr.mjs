#!/usr/bin/env node
/**
 * check_login_qr.mjs —— 登录二维码的 round-trip 判据
 *
 * ## 它要回答的问题
 *
 * `LoginQr.tsx` 用 `qrcode` 生成一张 SVG。**怎么知道扫出来真的是那条登录 URL？**
 * 没有这条判据的话，「二维码」三个字就只是一句话 —— 生成器换一个参数、
 * 编码级别调错、或者哪天有人把 target 换成别的字符串，页面看起来一模一样，
 * 而扫码之后去的是别的地方。这类问题**不会让任何既有断言变红**。
 *
 * ## 判据（不是「有没有生成出来」，是「解出来是不是它」）
 *
 *   1. 用 `qrcode` 生成 SVG（与组件同一组参数）；
 *   2. 把**渲染出来的 SVG** 交给真实的 Chrome 光栅化成像素；
 *   3. 用 `jsqr`（**另一个实现**，不是 qrcode 库自己）解码；
 *   4. 断言解出的字符串**逐字等于** 目标 URL。
 *
 * ★ 为什么绕这么大一圈，而不是直接读 `QRCode.create()` 的矩阵：
 *   那只证明「库自己认为自己编码对了」。要证明的是**产物能扫**，
 *   所以必须经过「渲染 → 像素 → 解码」这一整条链，且解码用独立实现。
 *
 * ## 反向对照（缺了它，这条判据可能恒真）
 *
 *   · 换一个字符重新生成 → 解码结果必须**不等于**目标（证明比对不是恒等）；
 *   · 把 SVG 换成一张空白图 → jsqr 必须解不出（证明「解出空串」不会被当成通过）。
 *
 * ## 退出码
 *
 *   0 全过 · 1 有红 · 2 未测（Chrome 起不来 / jsqr 不可用）
 *   —— 未测 ≠ 通过 ≠ 红。
 *
 * ## 用法
 *
 *   node web/scripts/check_login_qr.mjs
 *   node web/scripts/check_login_qr.mjs --base https://example.com
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import QRCode from "qrcode";
import jsQR from "jsqr";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

/** 与 `LoginQr.tsx` 必须**逐项一致**；不一致时本判据验的就不是线上那张图。 */
const QR_OPTIONS = {
  type: "svg",
  errorCorrectionLevel: "M",
  margin: 1,
  width: 132,
  color: { dark: "#35141a", light: "#ffffff" },
};

const BASE = arg("base", "https://review.example.com").replace(/\/$/, "");
const TARGET = `${BASE}/auth/login`;

const chrome =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const debugPort = Number(arg("debug-port", "9417"));

const RED = [];
const UNTESTED = [];
function record(name, ok, detail = "") {
  if (ok === null) {
    UNTESTED.push(`${name}${detail ? "  " + detail : ""}`);
  } else if (ok) {
    console.log(`  ✓ ${name}`);
  } else {
    console.log(`  ✗ ${name}  ${detail}`);
    RED.push(name);
  }
}

async function renderSvg(target) {
  return QRCode.toString(target, QR_OPTIONS);
}

/**
 * 用 Chrome 把 SVG 光栅化成像素，返回 { data: Uint8ClampedArray, width, height }。
 * Chrome 不可用 → 抛错，由调用方落「未测」。
 */
async function rasterize(svgMarkup) {
  if (!fs.existsSync(chrome)) {
    throw new Error(`找不到 Chrome（${chrome}）`);
  }
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "qr_check_chrome_"));
  const child = spawn(
    chrome,
    [
      "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
      "--no-default-browser-check", `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profile}`, "about:blank",
    ],
    { stdio: "ignore" },
  );
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let ws = null;
  try {
    for (let i = 0; i < 60; i++) {
      try {
        const r = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
        if (r.ok) break;
      } catch {
        /* retry */
      }
      await sleep(200);
    }
    const target = await (
      await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, {
        method: "PUT",
      })
    ).json();
    ws = new WebSocket(target.webSocketDebuggerUrl);
    const pending = new Map();
    let nextId = 1;
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) {
        const p = pending.get(m.id);
        pending.delete(m.id);
        m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
      }
    };
    const send = (method, params = {}) =>
      new Promise((res, rej) => {
        const id = nextId++;
        pending.set(id, { res, rej });
        ws.send(JSON.stringify({ id, method, params }));
      });

    await send("Runtime.enable");
    // 把 SVG 放进页面，画到 canvas，取回 RGBA。
    // ★ 用 data: URL 加载而不是 document.write，避免转义问题。
    const html = `<!doctype html><html><body style="margin:0">
<div id="host" style="width:${QR_OPTIONS.width}px;height:${QR_OPTIONS.width}px">${svgMarkup}</div>
</body></html>`;
    await send("Page.navigate", {
      url: `data:text/html;charset=utf-8,${encodeURIComponent(html)}`,
    });
    await sleep(500);

    const result = await send("Runtime.evaluate", {
      expression: `(async () => {
        const svg = document.querySelector('#host svg');
        if (!svg) return { ok: false, reason: 'no svg' };
        // 固定成整数边长，避免 SVG 自身 width/height 与 CSS 不一致
        const size = ${QR_OPTIONS.width};
        svg.setAttribute('width', String(size));
        svg.setAttribute('height', String(size));
        const blob = new Blob([svg.outerHTML], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        try {
          const img = new Image();
          await new Promise((res, rej) => {
            img.onload = res; img.onerror = () => rej(new Error('img load failed'));
            img.src = url;
          });
          const canvas = document.createElement('canvas');
          canvas.width = size; canvas.height = size;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, size, size);
          ctx.drawImage(img, 0, 0, size, size);
          const data = ctx.getImageData(0, 0, size, size).data;
          // 转成普通数组，可靠地穿过 CDP 序列化
          return { ok: true, width: size, height: size,
                   data: Array.from(data), pixelCount: data.length / 4 };
        } finally {
          URL.revokeObjectURL(url);
        }
      })()`,
      returnByValue: true,
      awaitPromise: true,
    });
    const value = result?.result?.value;
    if (!value?.ok) {
      throw new Error(`光栅化失败：${value?.reason ?? "unknown"}`);
    }
    return {
      data: new Uint8ClampedArray(value.data),
      width: value.width,
      height: value.height,
      pixelCount: value.pixelCount,
    };
  } finally {
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
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
}

function decode(raster) {
  return jsQR(raster.data, raster.width, raster.height, {
    inversionAttempts: "dontInvert",
  });
}

async function main() {
  console.log("=".repeat(72));
  console.log(`登录二维码 round-trip  ·  目标 ${TARGET}`);
  console.log("=".repeat(72));

  // ── 1. 生成 ──────────────────────────────────────────────────────────────
  let svg;
  try {
    svg = await renderSvg(TARGET);
  } catch (e) {
    record("Q0 生成 SVG", false, String(e));
    return finish();
  }
  record("Q0 生成 SVG", typeof svg === "string" && svg.includes("<svg"), "");
  record(
    "Q0b 产物是纯 SVG（无 canvas / 无外链）",
    !/<canvas/i.test(svg) && !/https?:\/\/(?!www\.w3\.org)/i.test(svg),
    "产物里出现了 canvas 或外部 URL",
  );

  // ── 2. 光栅化 + 解码（Chrome 不可用 → 未测）──────────────────────────────
  let raster;
  try {
    raster = await rasterize(svg);
  } catch (e) {
    record("Q1 光栅化（Chrome）", null, `未测：${e.message}`);
    return finish();
  }
  record(
    "Q1 光栅化（Chrome）",
    raster.pixelCount === raster.width * raster.height,
    `${raster.width}×${raster.height}`,
  );

  // ── 3. round-trip：解出来的必须逐字等于目标 ──────────────────────────────
  let decoded = null;
  try {
    decoded = decode(raster);
  } catch (e) {
    record("Q2 jsqr 解码", false, String(e));
    return finish();
  }
  const decodedText = decoded?.data ?? null;
  record(
    "Q2 jsqr 解出内容（不是空白）",
    typeof decodedText === "string" && decodedText.length > 0,
    decodedText === null ? "jsqr 返回 null（图里没有可识别的二维码）" : "",
  );
  record(
    "Q3 ★ 解出的内容逐字等于登录 URL",
    decodedText === TARGET,
    `期望 ${JSON.stringify(TARGET)}，实得 ${JSON.stringify(decodedText)}`,
  );

  // ── 4. 反向对照：换一个字符，解码结果必须不同 ────────────────────────────
  //   缺这条的话，「解码恒返回目标字符串」的实现也能过。
  const MUTATED = `${TARGET}x`;
  try {
    const svg2 = await renderSvg(MUTATED);
    const raster2 = await rasterize(svg2);
    const decoded2 = decode(raster2);
    record(
      "Q4 反向对照：改动一个字符后解出的内容必须不同",
      Boolean(decoded2) && decoded2.data === MUTATED && decoded2.data !== TARGET,
      `实得 ${JSON.stringify(decoded2?.data ?? null)}`,
    );
  } catch (e) {
    record("Q4 反向对照（改动字符）", null, `未测：${e.message}`);
  }

  // ── 5. 反向对照：空白图必须解不出 ────────────────────────────────────────
  //   抓的是「jsqr 返回 null 时被当成通过」这种形状。
  const blank = {
    data: new Uint8ClampedArray(QR_OPTIONS.width * QR_OPTIONS.width * 4).fill(255),
    width: QR_OPTIONS.width,
    height: QR_OPTIONS.width,
  };
  const blankDecoded = decode(blank);
  record(
    "Q5 反向对照：纯白图必须解不出（空结果不算通过）",
    blankDecoded === null,
    `纯白图解出了 ${JSON.stringify(blankDecoded?.data ?? null)}`,
  );

  return finish();
}

function finish() {
  console.log("-".repeat(72));
  for (const u of UNTESTED) console.log(`  ⚠ 未测 ${u}`);
  if (RED.length) {
    console.log(`❌ ${RED.length} 项红：${RED.join("、")}`);
    return 1;
  }
  if (UNTESTED.length) {
    console.log(`⚠ 有 ${UNTESTED.length} 项未测 —— 未测不是通过`);
    return 2;
  }
  console.log("✅ 全部通过：二维码解出的就是登录 URL");
  return 0;
}

process.exit(await main());
