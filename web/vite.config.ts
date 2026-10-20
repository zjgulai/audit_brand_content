import process from "node:process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * 只做前端构建；后端地址由 VITE_REVIEW_API_BASE 注入（默认同源 /review-api）。
 *
 * ★ 2026-10-20 修复（队列口径）：
 *   旧规则把 `/review-api/queue` **原样保留**给后端的联调别名，
 *   而那个别名列出的是「全部可读案件」—— BLOCK 与 PASS 也会进复核队列。
 *   现在 `/review-api/queue` 也改写到 `/api/v1/queue`（真队列：只 REVIEW + 待自决）。
 *
 *   这条修复**不能只改 client.ts**：代理是第二个口径来源，改一处另一处仍会返回全集。
 *   断言见 web/scripts/check_review_slice.mjs 的 A1（含反向对照）。
 */
const proxyTarget = process.env.REVIEW_API_PROXY ?? "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 只存在于本地联调入口（web/scripts/review_api_dev.py）的 /dev/*：
      // 身份切换器用它建 session。生产入口没有这些路由。
      "/dev": {
        target: proxyTarget,
        changeOrigin: false,
      },
      "/review-api": {
        target: proxyTarget,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/review-api/, "/api/v1"),
      },
    },
  },
});
