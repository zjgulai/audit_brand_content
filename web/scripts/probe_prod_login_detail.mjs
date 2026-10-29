#!/usr/bin/env node
/**
 * 生产登录页的细节探针 + 截图（只读）。
 *
 * 目的只有一个：`verify_prod_pages.mjs` 报「可聚焦=1」—— 登录页只有 1 个
 * 可键盘到达的元素，这个数目低得可疑。把页面上的元素逐个列出来，
 * 让「少」这件事指得出对象，而不是一个数字。
 *
 * 同时产出两张截图给操作指引用（1280×720 与 320×800）。
 */
import fs from "node:fs";
import path from "node:path";
import { launch, HarnessUntested } from "./lib/browser_harness.mjs";

const BASE = (process.env.PROD_BASE || "https://ca.luteos.com").replace(/\/$/, "");
const OUTDIR = process.argv.includes("--outdir")
  ? process.argv[process.argv.indexOf("--outdir") + 1]
  : "";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  let s;
  try {
    s = await launch({ width: 1280, height: 720 });
  } catch (e) {
    if (e instanceof HarnessUntested) {
      console.log(`⚠ 未测：${e.message}`);
      return 2;
    }
    throw e;
  }
  if (OUTDIR) fs.mkdirSync(OUTDIR, { recursive: true });

  await s.send("Page.enable");
  await s.enableDiagnostics();

  const shots = [];
  for (const [w, h, label] of [
    [1280, 720, "desktop-1280x720"],
    [320, 800, "reflow-320"],
  ]) {
    await s.send("Emulation.setDeviceMetricsOverride", {
      width: w,
      height: h,
      deviceScaleFactor: 1,
      mobile: false, // ★ 绝不能用 true：会退化成 980px 布局视口（见 a11y_check.mjs 头注）
    });
    await s.send("Page.navigate", { url: BASE + "/login" });
    await sleep(1600);

    const detail = await s.eval(`(() => {
      const sel = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      const els = Array.from(document.querySelectorAll(sel));
      return {
        viewport: { w: window.innerWidth, h: window.innerHeight },
        scrollWidth: document.documentElement.scrollWidth,
        focusables: els.map(e => ({
          tag: e.tagName.toLowerCase(),
          text: (e.innerText || e.getAttribute("aria-label") || "").replace(/\\s+/g, " ").trim().slice(0, 60),
          href: e.getAttribute("href") || "",
          role: e.getAttribute("role") || "",
        })),
        imgs: Array.from(document.images).map(i => ({
          src: (i.currentSrc || i.src || "").split("/").pop(),
          alt: i.getAttribute("alt"),
          w: i.naturalWidth, h: i.naturalHeight,
          rendered: Math.round(i.getBoundingClientRect().width) + "x" + Math.round(i.getBoundingClientRect().height),
        })),
        // 有 role=alert / status 的地方（动态播报相关）
        liveRegions: Array.from(document.querySelectorAll('[aria-live], [role="alert"], [role="status"]')).map(e => ({
          tag: e.tagName.toLowerCase(),
          role: e.getAttribute("role") || "",
          live: e.getAttribute("aria-live") || "",
          text: (e.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 60),
        })),
      };
    })()`);

    if (OUTDIR) {
      const r = await s.send("Page.captureScreenshot", { format: "png" });
      const f = path.join(OUTDIR, `login-${label}.png`);
      fs.writeFileSync(f, Buffer.from(r.data, "base64"));
      shots.push({ label, file: path.basename(f), bytes: fs.statSync(f).size });
    }

    console.log("=".repeat(70));
    console.log(`登录页 · ${label}（innerWidth=${detail.viewport.w} scrollWidth=${detail.scrollWidth}）`);
    console.log("=".repeat(70));
    console.log(`可键盘到达的元素：${detail.focusables.length} 个`);
    for (const f of detail.focusables) {
      console.log(`  · <${f.tag}> ${f.text || "(无文本)"}${f.href ? " → " + f.href : ""}`);
    }
    console.log(`图片：${detail.imgs.length} 张`);
    for (const i of detail.imgs) {
      console.log(`  · ${i.src} alt=${JSON.stringify(i.alt)} 自然=${i.w}x${i.h} 渲染=${i.rendered}`);
    }
    console.log(`动态播报区域：${detail.liveRegions.length} 处`);
    for (const l of detail.liveRegions) {
      console.log(`  · <${l.tag}> role=${l.role || "-"} aria-live=${l.live || "-"} "${l.text}"`);
    }
  }

  await s.send("Emulation.clearDeviceMetricsOverride").catch(() => {});
  s.close();
  if (shots.length) {
    console.log("\n截图：");
    for (const x of shots) console.log(`  ${x.file}  ${x.bytes} 字节`);
  }
  return 0;
}

let rc = 2;
try {
  rc = await main();
} catch (e) {
  console.error(`⚠ 未测：${e?.message || e}`);
  rc = 2;
}
process.exit(rc);
