import process from "node:process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 只做前端构建；后端地址由 VITE_REVIEW_API_BASE 注入（默认同源 /review-api）。
// dev server 的 /review-api：
//   - /review-api/queue 保持原样（后端联调别名，列出全部可读案件）
//   - 其余 /review-api/* 重写到 /api/v1/*（cases / reports 的只读端点）
const proxyTarget = process.env.REVIEW_API_PROXY ?? "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/review-api": {
        target: proxyTarget,
        changeOrigin: false,
        rewrite: (path) =>
          path.startsWith("/review-api/queue")
            ? path
            : path.replace(/^\/review-api/, "/api/v1"),
      },
    },
  },
});
