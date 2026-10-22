#!/usr/bin/env node
/**
 * 生产 bundle 边界检查。
 *
 * 输入是 npm run build 的 dist，不启动服务器、不改代码：
 * - 开发身份模块/写客户端不能成为生产 chunk；
 * - 不得出现 dev 端点、替身 principal 或真正的写 URL 形状；
 * - 只读提示里可以提到 `/actions`，但不能出现 fetch/request + write path。
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
const source = files.map((name) => fs.readFileSync(path.join(assets, name), "utf8")).join("\n");
const forbiddenChecks = [
  ["开发 session 端点", (text) => !text.includes("/dev/session")],
  ["开发身份列表端点", (text) => !text.includes("/dev/identities")],
  ["替身 principal", (text) => !/u_dp3|u_dp4|u_signer/.test(text)],
  ["开发身份启用控件", (text) => !text.includes("启用本地开发身份")],
];
const checks = forbiddenChecks.map(([label, predicate]) => [`不含${label}`, predicate(source)]);
// ★ T-170：生产写 UI 必须在包里（正向断言），且 CSRF 头存在。
checks.push(["生产包含写入口（/claim）", source.includes("/claim")]);
checks.push(["生产包含写入口（/actions）", source.includes("/actions")]);
checks.push(["生产包含 CSRF 头", source.includes("x-csrf-token")]);
// ★ T-210：内部判定数据只在**生产构建**里必须为空。
//   dev-up 的 hostile-build 是 `--mode development` 构建，本来就允许带 dev 模块，
//   所以那一次检查显式不带 `--production`，跳过这两条（不是放行生产）。
const hasInternalData = (text) =>
  text.includes("rule_examples") || text.includes("boundary_disputes");
checks.push(["不含内部判定数据（rule_examples / boundary_disputes）", !hasInternalData(source)]);
// ★ T-150：生产界面的边界从「完全只读」变成「可登录，但没有签发/撤回控件」。
//   登录/登出不是内容写；release-decision / release-revoke 仍然只许人经受控入口。
checks.push(["生产界面提供登录入口（/auth/login）", source.includes("/auth/login")]);
const hasReleasePath = (text) =>
  text.includes("/release-decision") || text.includes("/release-revoke");
checks.push(["不含签发/撤回请求路径（说明文字不算）", !hasReleasePath(source)]);
checks.push([
  "反向对照：植入 /release-decision 必须被抓到",
  hasReleasePath(source + '\nconst __probe = "/release-decision";') === true,
]);
// 反向对照：已知坏样本必须让对应谓词失败，证明扫描器不是恒真。
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
