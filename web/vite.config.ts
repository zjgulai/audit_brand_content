import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/**
 * 开发能力必须同时满足：
 *   1. Vite 正在 serve（任何 build 都关闭，即使 --mode development）；
 *   2. REVIEW_DEV_IDENTITY=1；
 *   3. APP_ENV=dev。
 *
 * 这比 import.meta.env.DEV 更严格：Vite 的 DEV/PROD 受 NODE_ENV 影响，不能拿来
 * 作为安全边界。这里由 `command` 决定并编译成布尔常量，生产 bundle 可 tree-shake。
 */
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const devIdentityEnabled =
    command === "serve" &&
    env.REVIEW_DEV_IDENTITY === "1" &&
    env.APP_ENV === "dev";
  const proxyTarget = env.REVIEW_API_PROXY ?? "http://127.0.0.1:8010";

  return {
    plugins: [react()],
    define: {
      __REVIEW_DEV_IDENTITY__: JSON.stringify(devIdentityEnabled),
      __REVIEW_WRITE_ENABLED__: JSON.stringify(devIdentityEnabled),
    },
    server: {
      port: 5173,
      proxy: {
        ...(devIdentityEnabled
          ? {
              "/dev": {
                target: proxyTarget,
                changeOrigin: false,
              },
            }
          : {}),
        "/review-api": {
          target: proxyTarget,
          changeOrigin: false,
          rewrite: (path: string) => path.replace(/^\/review-api/, "/api/v1"),
        },
      },
    },
  };
});
