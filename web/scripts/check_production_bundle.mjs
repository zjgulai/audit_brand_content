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
  ["claim 请求路径", (text) => !/[`'\"]\/cases\/\$\{[^}]+\}\/claim/.test(text)],
  ["actions 请求模板", (text) => !/[`'\"]\/cases\/\$\{[^}]+\}\/actions/.test(text)],
];
const checks = forbiddenChecks.map(([label, predicate]) => [`不含${label}`, predicate(source)]);
checks.push(["不含写客户端 chunk", files.every((name) => !name.includes("write-client"))]);
checks.push(["生产界面明确只读", source.includes("只读 · 生产认证写入口未接入")]);
// 反向对照：已知坏样本必须让对应谓词失败，证明扫描器不是恒真。
checks.push([
  "反向对照：植入 /dev/session 必须被抓到",
  forbiddenChecks[0][1](source + '\nfetch("/dev/session")') === false,
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
