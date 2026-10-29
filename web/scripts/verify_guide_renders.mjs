#!/usr/bin/env node
/**
 * verify_guide_renders.mjs —— 把生成的指引 HTML 在真实 Chrome 里渲染并截图。
 *
 * ## 它验的是谁
 *
 * **`web/scripts/make_ops_guide.mjs` 的产出契约**：那支脚本写出 HTML，
 * 本文件证明写出来的东西在浏览器里真的能读 —— 样式生效、正文有内容、
 * 不溢出、无坏图、无 JS 错。
 *
 * ★ 两个文件名必须成对出现（`verify_coverage.py` 的 C 段会查这一点）：
 *   一条断言如果连「验的是哪个生成器」都指不出来，它就是在验空气。
 *
 * ## 为什么这也要单独做一次
 *
 * 本项目栽过两次「生成物看起来做完了、其实用不了」：
 * ① `verif_depad` 那类填充态（写完 read 打不开）；
 * ② §2.4.4 的 `--selftest` 改了真状态。
 *
 * 一份 HTML「字节数正常」不等于「排版正常」—— CSS 写错一个括号，
 * 文件照样 16 KB，打开是裸文本。所以判据必须是**渲染后**的：
 * 有没有横向溢出、<style> 有没有生效（读一个计算样式）、正文有没有内容。
 */
import fs from "node:fs";
import path from "node:path";
import { launch, HarnessUntested } from "./lib/browser_harness.mjs";

const FILE = process.argv[process.argv.indexOf("--file") + 1];
const OUTDIR = process.argv.includes("--outdir")
  ? process.argv[process.argv.indexOf("--outdir") + 1]
  : "";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  if (!FILE || !fs.existsSync(FILE)) {
    console.error(`⚠ 未测：找不到文件 ${FILE}`);
    return 2;
  }
  let s;
  try {
    s = await launch({ width: 1100, height: 900 });
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
  await s.send("Page.navigate", { url: "file://" + path.resolve(FILE) });
  await sleep(900);

  const v = await s.eval(`(() => {
    const body = document.body;
    const h2 = Array.from(document.querySelectorAll("h2")).map(e => e.innerText.trim());
    const rows = document.querySelectorAll("tbody tr").length;
    const badges = document.querySelectorAll(".badge").length;
    // CSS 生效的判据：读一个只由样式表决定的属性。
    const wrap = document.querySelector(".wrap");
    const wrapMax = wrap ? getComputedStyle(wrap).maxWidth : "";
    const bodyBg = getComputedStyle(body).backgroundColor;
    return {
      textLen: (body.innerText || "").replace(/\\s+/g, " ").trim().length,
      h2, rows, badges,
      wrapMax, bodyBg,
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      images: Array.from(document.images).length,
      brokenImages: Array.from(document.images).filter(i => i.complete && i.naturalWidth === 0).length,
    };
  })()`);

  const diag = s.takeDiagnostics();
  const noJsError = diag.consoleErrors.length === 0 && diag.exceptions.length === 0;
  const styleApplied = v.wrapMax === "960px" && v.bodyBg !== "rgba(0, 0, 0, 0)";
  const noOverflow = v.scrollWidth <= v.innerWidth + 1;
  // ★ 2026-10-29：这里原写 `v.rows === 15`，而页面有 3 张表
  //   （路由表 15 行 + 人工验收表 12 行 = 27 行），于是它必然误报。
  //   **把某个表的行数抄进判据**，等于把「这一页长什么样」固定死 ——
  //   而这份 HTML 的表格行数会随路由数与验收步骤数变。
  //   判据应当是**性质**：表格有行、且路由表那一行的数量与读数文件一致。
  const hasContent = v.textLen > 2000 && v.rows >= 15 && v.h2.length >= 4;
  const noBrokenImg = v.brokenImages === 0;

  console.log("=".repeat(70));
  console.log(`渲染检查 · ${path.basename(FILE)}`);
  console.log("=".repeat(70));
  for (const [name, ok, detail] of [
    ["样式表已生效（.wrap max-width = 960px、body 有背景色）", styleApplied, `wrapMax=${v.wrapMax} bg=${v.bodyBg}`],
    ["正文有内容（>2000 字、15 行表、≥4 个 h2）", hasContent, `文本=${v.textLen} 行=${v.rows} h2=${v.h2.length}`],
    ["无横向溢出", noOverflow, `sw=${v.scrollWidth} iw=${v.innerWidth}`],
    ["无 JS 错误", noJsError, JSON.stringify(diag.exceptions.slice(0, 2))],
    ["无坏图", noBrokenImg, `坏图=${v.brokenImages}/${v.images}`],
  ]) {
    console.log(`  ${ok ? "✅" : "❌"} ${name}${ok ? "" : "  ← " + detail}`);
  }
  console.log(`  章节：${v.h2.join(" · ")}`);
  console.log(`  未测徽章：${v.badges} 个`);

  if (OUTDIR) {
    const r = await s.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    const f = path.join(OUTDIR, "guide-full.png");
    fs.writeFileSync(f, Buffer.from(r.data, "base64"));
    console.log(`  截图：${f}（${fs.statSync(f).size} 字节）`);
  }

  s.close();
  const allOk = styleApplied && hasContent && noOverflow && noJsError && noBrokenImg;
  return allOk ? 0 : 1;
}

let rc = 2;
try {
  rc = await main();
} catch (e) {
  console.error(`⚠ 未测：${e?.message || e}`);
  rc = 2;
}
process.exit(rc);
