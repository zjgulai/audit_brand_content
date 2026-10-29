#!/usr/bin/env node
/**
 * make_ops_guide.mjs —— 生成「生产逐页验收与操作指引」HTML。
 *
 * ## 为什么用脚本生成，而不是手写一份 HTML
 *
 * 手写的指引里，**每一个数字都会过期**（AGENTS.md §2.2 第 1 条）：
 * 「15 条路由」「109 字」「425 KB」—— 下次部署就变了，而没人会记得改。
 * 所以这份 HTML 的读数全部来自 `verify_prod_pages.mjs` 的落盘 JSON。
 *
 * ## 它会说清「验到了什么」和「没验到什么」
 *
 * 本轮最大的风险是**把「15/15 绿」读成「15 个业务页面都能用」**。
 * 那个绿只是「未登录时每一条都被正确送回登录页」。HTML 里这一点
 * 必须显眼，而不是藏在脚注里 —— 一份让人高估覆盖度的指引，比没有更糟。
 *
 * 用法：
 *   node web/scripts/verify_prod_pages.mjs --out /tmp/prod-pages.json
 *   node web/scripts/make_ops_guide.mjs --readings /tmp/prod-pages.json --out 操作指引.html
 */
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

function arg(name, fallback = "") {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const READINGS = arg("readings", "/tmp/prod-pages.json");
const OUT = arg("out", "生产验收与操作指引.html");
const SHOTS = arg("shots", "");

function main() {
  if (!fs.existsSync(READINGS)) {
    console.error(`⚠ 未测：读数文件不存在 ${READINGS}`);
    console.error(`  先跑：node web/scripts/verify_prod_pages.mjs --out ${READINGS}`);
    return 2;
  }
  const d = JSON.parse(fs.readFileSync(READINGS, "utf8"));
  const R = d.results || [];
  const allLogin = R.every((r) => r.checks?.routedToLogin);
  const green = R.filter((r) => r.ok).length;

  // 部署版本与镜像 tag —— 从 git 取，不手写。
  let commit = "";
  let commitSubject = "";
  try {
    commit = execFileSync("git", ["rev-parse", "--short", "HEAD"], { encoding: "utf8" }).trim();
    commitSubject = execFileSync("git", ["log", "-1", "--format=%s"], { encoding: "utf8" }).trim();
  } catch {
    commit = "（读不到）";
  }

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  const rows = R.map(
    (r) => `
      <tr class="${r.ok ? "ok" : "bad"}">
        <td><code>${esc(r.path)}</code></td>
        <td>${esc(r.name)}</td>
        <td class="c">${r.ok ? "✅" : "❌"}</td>
        <td class="c">${r.reading?.rootChildren}</td>
        <td class="c">${r.reading?.textLen}</td>
        <td class="c">${r.reading?.h1?.length ?? 0}</td>
        <td class="c">${r.reading?.focusables ?? 0}</td>
        <td>${esc((r.reading?.h1 || [])[0] || "")}</td>
      </tr>`,
  ).join("");

  // ★ 截图默认**内嵌成 data URI**，让这份 HTML 自包含。
  //
  //   第一版用的是 `file://` 绝对路径 —— 只有在这台机器上、且文件还在
  //   那个目录里时才打得开。把它发给别人（或挪个位置）就全是坏图，
  //   而页面本身看起来仍然「生成成功」。
  //
  // ★★ 但内嵌有**体积上限**：整页截图 757 KB → base64 后 1 MB，
  //   而这份 HTML 是要进公开仓的（多媒体/大字节都不该进）。
  //   规则是：单张超过 EMBED_MAX 就**跳过并打印**，不静默丢。
  //   登录页那两张各 30–34 KB，内嵌后约 87 KB，可以接受；
  //   整页那张 757 KB，跳过 —— 它本来也只是给我自己看排版的。
  const EMBED_MAX = 120 * 1024;
  const embed = !process.argv.includes("--no-embed");
  const skipped = [];
  const shotBlocks = SHOTS && fs.existsSync(SHOTS)
    ? fs
        .readdirSync(SHOTS)
        .filter((f) => f.endsWith(".png"))
        .sort()
        .filter((f) => {
          const size = fs.statSync(path.join(SHOTS, f)).size;
          if (embed && size > EMBED_MAX) {
            skipped.push(`${f}（${Math.round(size / 1024)} KB > ${EMBED_MAX / 1024} KB）`);
            return false;
          }
          return true;
        })
        .map((f) => {
          const p = path.join(SHOTS, f);
          const src = embed
            ? `data:image/png;base64,${fs.readFileSync(p).toString("base64")}`
            : f;
          return `
        <figure>
          <img src="${src}" alt="${esc(f)}" />
          <figcaption>${esc(f)}</figcaption>
        </figure>`;
        })
        .join("")
    : "";
  if (skipped.length) {
    console.log(`   ⚠ 未内嵌（体积超限，不是失败）：${skipped.join("、")}`);
  }

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>生产验收与操作指引 · ca.luteos.com</title>
<style>
  :root {
    --bg: #faf8f6; --card: #fff; --ink: #241f1d; --muted: #6b615c;
    --line: #e6ded8; --brand: #8c3f56; --ok: #1c7a4a; --bad: #b3261e;
    --warn: #8a5a00; --warnbg: #fff8e6;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2.5rem 1.25rem 5rem;
    background: var(--bg); color: var(--ink);
    font: 15px/1.7 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
  }
  .wrap { max-width: 960px; margin: 0 auto; }
  h1 { font-size: 1.65rem; margin: 0 0 .35rem; letter-spacing: -.01em; }
  h2 { font-size: 1.12rem; margin: 2.6rem 0 .8rem; padding-bottom: .45rem; border-bottom: 1px solid var(--line); }
  h3 { font-size: .98rem; margin: 1.6rem 0 .5rem; }
  .sub { color: var(--muted); font-size: .92rem; margin-bottom: 2rem; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1.25rem 1.4rem; }
  .callout { border-radius: 10px; padding: 1rem 1.2rem; margin: 1.2rem 0; border: 1px solid; }
  .callout.warn { background: var(--warnbg); border-color: #f0dca8; }
  .callout.truth { background: #f4f7fb; border-color: #cfdcec; }
  .callout b { display: block; margin-bottom: .35rem; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; margin: .8rem 0 1rem; }
  th, td { text-align: left; padding: .5rem .55rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { background: #f6f2ef; font-weight: 600; font-size: .82rem; color: var(--muted); }
  td.c { text-align: center; font-variant-numeric: tabular-nums; }
  tr.bad td { background: #fff5f4; }
  code { font: .86em/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; background: #f3eeeb; padding: .1em .35em; border-radius: 4px; }
  pre { background: #22201f; color: #e9e2dd; padding: .85rem 1rem; border-radius: 8px; overflow-x: auto; font: .82rem/1.6 ui-monospace, Menlo, monospace; }
  pre code { background: none; padding: 0; color: inherit; }
  ol, ul { padding-left: 1.35rem; }
  li { margin: .35rem 0; }
  .kpi { display: flex; gap: .8rem; flex-wrap: wrap; margin: 1rem 0 0; }
  .kpi div { flex: 1 1 150px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: .7rem .9rem; }
  .kpi span { display: block; font-size: .74rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .kpi strong { font-size: 1.18rem; font-variant-numeric: tabular-nums; }
  figure { margin: 0 0 1rem; }
  figure img { max-width: 100%; border: 1px solid var(--line); border-radius: 8px; display: block; }
  figcaption { font-size: .8rem; color: var(--muted); margin-top: .3rem; }
  .badge { display: inline-block; font-size: .74rem; padding: .12em .5em; border-radius: 999px; border: 1px solid; }
  .badge.done { color: var(--ok); border-color: #b9dcc7; background: #f0f9f3; }
  .badge.todo { color: var(--warn); border-color: #f0dca8; background: var(--warnbg); }
  .badge.no { color: var(--bad); border-color: #f3c4c0; background: #fdf3f2; }
  footer { margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .82rem; }
</style>
</head>
<body>
<div class="wrap">

  <h1>生产验收与操作指引</h1>
  <p class="sub">
    目标站点 <code>${esc(d.base)}</code> · 部署提交 <code>${esc(commit)}</code> ${esc(commitSubject)}<br />
    本页所有数字由 <code>web/scripts/verify_prod_pages.mjs</code> 在
    <code>${esc(d.at)}</code> 实测落盘，非手写。
  </p>

  <div class="callout warn">
    <b>先读这一段：这份报告**没有**验完 15 个业务页面</b>
    生产需要飞书 OAuth 会话。未登录时，全部 ${R.length} 条路由都渲染成
    <strong>同一个登录页</strong>（可见文本完全相同）。
    所以下表全绿的意思是
    <strong>「每条路径都被正确送回登录页，且外壳无 JS 错、无溢出、单 h1、无资源失败」</strong>，
    <strong>不是</strong>「${R.length} 个业务页面都能用」。业务页要在登录后人工过一遍
    —— 见第 2 节。
  </div>

  <div class="kpi">
    <div><span>路由被正确送回登录页</span><strong>${green} / ${R.length}</strong></div>
    <div><span>页面挂载（#root 有内容）</span><strong>${R.filter((r) => r.checks?.mounted).length} / ${R.length}</strong></div>
    <div><span>无 JS 未捕获异常</span><strong>${R.filter((r) => r.checks?.noJsError).length} / ${R.length}</strong></div>
    <div><span>无横向溢出</span><strong>${R.filter((r) => r.checks?.noOverflow).length} / ${R.length}</strong></div>
  </div>

  <h2>1. 自动探针的读数（未登录态，只读）</h2>
  <table>
    <thead>
      <tr>
        <th>路由</th><th>页面</th><th>结论</th>
        <th>#root 子节点</th><th>可见文本字数</th><th>h1 数</th><th>可聚焦元素</th><th>h1 文本</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>
  <p class="sub">
    ★「可聚焦元素 = 1」是登录页的正确形态 —— 唯一入口就是那一个飞书登录链接，
    已逐个枚举确认（见 <code>probe_prod_login_detail.mjs</code>）。这不是缺陷。
  </p>

  ${shotBlocks ? `<h3>登录页两视口实测截图（1280×720 / 320×800）</h3><div>${shotBlocks}</div>` : ""}

  <h2>2. 人工验收：登录后逐页过一遍</h2>
  <p>
    自动探针在无凭据的情况下到此为止。下面这部分<strong>必须有人登录后操作</strong>，
    因为「页面能挂载」和「业务数据正确」是两件事。
  </p>

  <h3>第 1 步 · 登录</h3>
  <ol>
    <li>用 <strong>桌面 Chrome（版本 155 或 156）</strong>打开 <code>${esc(d.base)}/login</code>
        —— 页脚写明支持范围；其他浏览器会看到「不支持」横幅，但**不阻断**访问。</li>
    <li>用手机飞书扫页面上的二维码。扫码后手机会弹出确认，点确认即可。</li>
    <li>回到浏览器，应自动跳进工作台。若停在登录页，刷新一次。</li>
  </ol>

  <h3>第 2 步 · 逐页走一遍（12 个业务页）</h3>
  <p>每一页只用做四件事，任一不满足就记一条：<strong>① 有没有内容 ② 数字对不对 ③ 点得动吗 ④ 报错吗</strong>。</p>
  <table>
    <thead><tr><th>顺序</th><th>页面</th><th>入口</th><th>具体看什么</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>复核队列</td><td><code>/queue</code></td><td>列表有没有行；点一条能否进详情；「待自决 / 最新」排序切换是否生效</td></tr>
      <tr><td>2</td><td>案件详情</td><td>从队列点进去</td><td>IR / 回执 / 双指纹是否并列显示；未评部分是否写明「未评原因」而不是空着</td></tr>
      <tr><td>3</td><td>认领与草稿</td><td>详情页</td><td>点「认领」后按钮变「释放草稿」；保存草稿后刷新页面，草稿还在</td></tr>
      <tr><td>4</td><td>案件总览</td><td><code>/cases</code></td><td>筛选条件叠加后结果数量随之变化；点「重置」能清空</td></tr>
      <tr><td>5</td><td>收件箱</td><td><code>/inbox</code></td><td>未读有几条；标已读后数字减少且刷新不回退</td></tr>
      <tr><td>6</td><td>提交内容审查</td><td><code>/submit</code></td><td>空内容应被拦；提交后能看到回执与案件号</td></tr>
      <tr><td>7</td><td>申诉中心</td><td><code>/appeals</code></td><td>列表与详情能对上；受理 / 驳回按钮有理由输入</td></tr>
      <tr><td>8</td><td>签发中心</td><td><code>/release</code></td><td>四个前置条件是否显示；不满足时签发按钮应禁用并说明原因</td></tr>
      <tr><td>9</td><td>下线任务台</td><td><code>/takedown</code></td><td>任务状态推进（开始 / 重试）后刷新是否保持</td></tr>
      <tr><td>10</td><td>报告索引</td><td><code>/reports</code></td><td>点报告能打开详情；链接带 <code>exp</code> 与 <code>sig</code> 两个参数</td></tr>
      <tr><td>11</td><td>分类规范与规则</td><td><code>/taxonomy</code></td><td>七轴筛选能用；规则详情只读（不应出现编辑框）</td></tr>
      <tr><td>12</td><td>授权名单 / 会话审计</td><td><code>/admin/grants</code>、<code>/admin/sessions</code></td><td>能列出条目；撤权 / 续期按钮的二次确认会弹出</td></tr>
    </tbody>
  </table>

  <h3>第 3 步 · 键盘与缩放（这 4 项机器测不了）</h3>
  <ol>
    <li><strong>纯键盘走一遍</strong>：只用 Tab / Enter / 方向键，从队列进详情再回到队列，全程不碰鼠标。</li>
    <li><strong>焦点可见</strong>：每按一次 Tab，当前元素必须有明显的焦点框（不能靠鼠标才知道在哪）。</li>
    <li><strong>200% 缩放</strong>：Chrome 里 <code>Cmd +</code> 按两次，文字不重叠、不截断。</li>
    <li><strong>400% 缩放</strong>：按到 400%，页面变成单列且<strong>不出现横向滚动条</strong>。</li>
  </ol>
  <p class="sub">
    ★ 动效这一项已有一半自动化了（<code>a11y_check.mjs</code> 在模拟
    <code>prefers-reduced-motion: reduce</code> 下读真实渲染样式，确认零动画零过渡）。
    剩下那一半仍需人看：系统开启「减少动态效果」后，页面用起来是否仍然顺畅。
  </p>

  <h2>3. 发现问题时怎么记录</h2>
  <p>按这个格式记，别人才能复现：</p>
  <pre><code>页面：/queue
操作：点了列表第 3 条
期望：进入案件详情
实际：页面停在原地，控制台报 TypeError
视口：1280×720（或 320px / 200%）
能否稳定复现：刷新后仍能</code></pre>
  <p>控制台错误在 Chrome 里按 <code>Cmd + Option + J</code> 打开，把红色那几行一起贴上。</p>

  <h2>4. 复跑自动探针</h2>
  <pre><code># 逐页渲染探针（未登录态）
node web/scripts/verify_prod_pages.mjs --out /tmp/prod-pages.json

# 登录页细节 + 两视口截图
node web/scripts/probe_prod_login_detail.mjs --outdir ~/audit-data/prod-shots

# 重新生成本页
node web/scripts/make_ops_guide.mjs \\
  --readings /tmp/prod-pages.json \\
  --shots ~/audit-data/prod-shots \\
  --out 生产验收与操作指引.html</code></pre>
  <p class="sub">
    截图默认写到仓库外（<code>~/audit-data/prod-shots</code>）—— 本仓库是公开的，
    媒体二进制不进版本库（<code>verify_download_governance.py</code> 的 DG-3 会拦）。
  </p>

  <h2>5. 这份报告没覆盖什么</h2>
  <ul>
    <li><span class="badge no">未测</span> <strong>登录后的 12 个业务页面</strong> —— 无飞书会话，自动探针进不去。</li>
    <li><span class="badge no">未测</span> <strong>图片 / 视频多模态判定</strong> —— 线上 <code>.env.production</code> 没有
        <code>MULTIMODAL_*</code> 任何键，运行时如实报 <code>untested</code>。</li>
    <li><span class="badge no">未测</span> <strong>真实用户 / 读屏用户测试</strong> —— 需要辅助技术用户参与。</li>
    <li><span class="badge todo">部分</span> <strong>无障碍（WCAG 2.2 AA）</strong> —— 机器半边 0 违规、13 项 AA 全过；
        9 项真人签收（键盘流程 / 读屏语义 / 焦点顺序 / 动态播报 / 200% / 400% / 动效体验 / 图文对比 / 真实用户）尚未完成。</li>
  </ul>

  <footer>
    由 <code>web/scripts/make_ops_guide.mjs</code> 生成 ·
    读数来源 <code>${esc(READINGS)}</code> ·
    生成时提交 <code>${esc(commit)}</code>
  </footer>
</div>
</body>
</html>
`;

  fs.mkdirSync(path.dirname(path.resolve(OUT)), { recursive: true });
  fs.writeFileSync(OUT, html, "utf8");
  console.log(`✅ 已生成：${OUT}（${Buffer.byteLength(html, "utf8")} 字节）`);
  console.log(`   读数：${green}/${R.length} 条路由 ${allLogin ? "均被送回登录页" : "（不是全部回登录页）"}`);
  return 0;
}

process.exit(main());
