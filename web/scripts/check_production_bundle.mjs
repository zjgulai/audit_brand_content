#!/usr/bin/env node
/**
 * 生产 bundle 边界检查（T-150 / T-170 / T-210 / G-05 受控签发白名单）。
 *
 * 输入是 npm run build 的 dist，不启动服务器、不改代码：
 * - 不得出现 dev 端点、替身 principal 或内部判定数据（rule_examples / boundary_disputes）；
 * - 生产写入口（/claim, /actions）与 CSRF 头必须存在；
 * - 签发/撤回请求路径（/release-decision, /release-revoke）只允许出现在按需分包的
 *   `ReleasePage-*.js` 受控 chunk 中（且必须同时包含 `step_up_token` 绑定字段），
 *   主入口 chunk 与其他业务页面 chunk 一旦出现 `/release-decision` 立即判红！
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const web = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}
const dist = path.resolve(web, arg("dir", "dist"));
const assets = path.join(dist, "assets");
if (!fs.existsSync(assets)) {
  console.error(`⚠ 未测：${assets} 不存在，请先构建指定目录`);
  process.exit(2);
}

const files = fs.readdirSync(assets).filter((name) => name.endsWith(".js"));
const byFile = new Map(
  files.map((name) => [name, fs.readFileSync(path.join(assets, name), "utf8")]),
);
const source = [...byFile.values()].join("\n");
const nonReleaseSource = [...byFile.entries()]
  .filter(([name]) => !name.startsWith("ReleasePage-"))
  .map(([, text]) => text)
  .join("\n");
const releaseChunkSource = [...byFile.entries()]
  .filter(([name]) => name.startsWith("ReleasePage-"))
  .map(([, text]) => text)
  .join("\n");

const forbiddenChecks = [
  ["开发 session 端点", (text) => !text.includes("/dev/session")],
  ["开发身份列表端点", (text) => !text.includes("/dev/identities")],
  ["替身 principal", (text) => !/u_dp3|u_dp4|u_signer/.test(text)],
  ["开发身份启用控件", (text) => !text.includes("启用本地开发身份")],
];
const checks = forbiddenChecks.map(([label, predicate]) => [`不含${label}`, predicate(source)]);
checks.push(["生产包含写入口（/claim）", source.includes("/claim")]);
checks.push(["生产包含写入口（/actions）", source.includes("/actions")]);
checks.push(["生产包含 CSRF 头", source.includes("x-csrf-token")]);

const hasInternalData = (text) =>
  text.includes("rule_examples") || text.includes("boundary_disputes");
checks.push(["不含内部判定数据（rule_examples / boundary_disputes）", !hasInternalData(source)]);
checks.push(["生产界面提供登录入口（/auth/login）", source.includes("/auth/login")]);

const hasReleasePath = (text) =>
  text.includes("/release-decision") || text.includes("/release-revoke");
checks.push([
  "非签发 chunk 不含签发/撤回请求路径（受控隔离 G-05）",
  !hasReleasePath(nonReleaseSource),
]);
checks.push([
  "签发受控 chunk 强制绑定 step_up_token",
  releaseChunkSource.length > 0 && releaseChunkSource.includes("step_up_token"),
]);
checks.push([
  "反向对照：在非签发 chunk 植入 /release-decision 必须被抓到",
  hasReleasePath(nonReleaseSource + '\nconst __probe = "/release-decision";') === true,
]);
checks.push([
  "反向对照：植入 /dev/session 必须被抓到",
  forbiddenChecks[0][1](source + '\nfetch("/dev/session")') === false,
]);
checks.push([
  "反向对照：植入 rule_examples 必须被抓到",
  hasInternalData(source + '\nconst __probe = "rule_examples";') === true,
]);

let failed = 0;
for (const [label, ok] of checks) {
  console.log(`${ok ? "✓" : "✗"} ${label}`);
  if (!ok) failed += 1;
}
if (failed) {
  console.error(`❌ ${failed}/${checks.length} 项失败`);
  process.exit(1);
}
console.log(`✅ ${checks.length}/${checks.length} 项通过`);
