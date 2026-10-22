/**
 * CSRF 头的唯一构造点（T-150）。
 *
 * 规则：**只有写请求**（POST/PUT/PATCH/DELETE）带 `x-csrf-token`；
 * GET/HEAD/OPTIONS 一律不带 —— 不给读请求引入副作用形状。
 * token 来自后端在 `/auth/callback` 下发的 `csrf` cookie（httponly=false）。
 *
 * 抽成纯函数是为了能被 `scripts/check_auth_headers.mjs` 直接测：
 * 那一条既证明「写请求带」，也证明「读请求不带」，反向对照可喂坏样本。
 */
export const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** 从 `document.cookie` 那样的字符串里取一个 cookie；取不到返回 null。 */
export function parseCookie(cookie: string | null | undefined, name: string): string | null {
  if (!cookie) return null;
  for (const part of cookie.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    if (part.slice(0, i).trim() === name) return decodeURIComponent(part.slice(i + 1));
  }
  return null;
}

/** 给定方法与 cookie 串，返回该请求应带的 CSRF 头（不需要时返回空对象）。 */
export function csrfHeaders(
  method: string,
  cookie: string | null | undefined,
): Record<string, string> {
  if (!UNSAFE_METHODS.has(String(method).toUpperCase())) return {};
  const token = parseCookie(cookie, "csrf");
  return token ? { "x-csrf-token": token } : {};
}
