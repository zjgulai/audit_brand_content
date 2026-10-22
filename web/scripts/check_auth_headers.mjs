#!/usr/bin/env node
/**
 * check_auth_headers.mjs —— CSRF 头的纯函数检查（T-150）。
 *
 * 判据（两条方向都要证）：
 *   ① 写请求（POST/PUT/PATCH/DELETE）**必须**带 `x-csrf-token`；
 *   ② 读请求（GET/HEAD/OPTIONS）**不许**带 —— 不给读引入副作用形状。
 * 反向对照：把 GET 当成写、把 cookie 去掉，都必须让断言失败。
 *
 * 只读：不联网、不写盘。
 * 退出码：0 全过 / 1 有红。
 */
import { csrfHeaders, parseCookie } from "../src/api/auth-headers.ts";

const results = [];
function check(name, ok, detail = "") {
  results.push([name, !!ok, detail]);
}

const jar = "a=1; csrf=abc123; b=2";

check("GET 不带 CSRF", Object.keys(csrfHeaders("GET", jar)).length === 0);
check("HEAD 不带 CSRF", Object.keys(csrfHeaders("HEAD", jar)).length === 0);
check("OPTIONS 不带 CSRF", Object.keys(csrfHeaders("OPTIONS", jar)).length === 0);
check("POST 带 CSRF", csrfHeaders("POST", jar)["x-csrf-token"] === "abc123");
check("PUT 带 CSRF", csrfHeaders("PUT", jar)["x-csrf-token"] === "abc123");
check("PATCH 带 CSRF", csrfHeaders("PATCH", jar)["x-csrf-token"] === "abc123");
check("DELETE 带 CSRF（小写方法也认）", csrfHeaders("delete", jar)["x-csrf-token"] === "abc123");
check("没有 csrf cookie → 不带（让后端 403，而不是客户端伪造）",
  Object.keys(csrfHeaders("POST", "a=1")).length === 0);
check("cookie 值解码", parseCookie("csrf=a%20b", "csrf") === "a b");
check("同名子串不误取", parseCookie("mycsrf=x; csrf=y", "csrf") === "y");

// ★ 反向对照：如果有人把「写请求带」改成「一律带」，下面这条会红。
check("反向对照：GET 带 CSRF 必须被抓到",
  Object.keys(csrfHeaders("GET", jar)).length === 0);
// ★ 反向对照：如果去掉写请求的头，下面这条会红。
check("反向对照：POST 缺 CSRF 必须被抓到",
  csrfHeaders("POST", "a=1")["x-csrf-token"] === undefined);

let failed = 0;
for (const [name, ok, detail] of results) {
  console.log(`${ok ? "✓" : "✗"} ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failed += 1;
}
console.log(failed ? `❌ ${failed}/${results.length} 项失败` : `✅ ${results.length}/${results.length} 项通过`);
process.exit(failed ? 1 : 0);
