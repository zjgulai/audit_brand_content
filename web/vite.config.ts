import { defineConfig, loadEnv, type Plugin } from "vite";
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
/**
 * ★ 2026-10-22 T-210：生产 bundle 不许带内部判定数据。
 *
 * `taxonomy.json` 里的 `rule_examples`（内部判定理由原文）与
 * `meta.boundary_disputes`（未裁定的内部分歧）只用于开发/内部管理面；
 * 它们在 dev 里保留（A8、rule_id 查找测试要用），**只在 build 时剥离**。
 * 执行点：`scripts/check_production_bundle.mjs` 扫描 dist，出现任一字样即红。
 */
function stripInternalTaxonomy(): Plugin {
  return {
    name: "strip-internal-taxonomy",
    apply: "build",
    enforce: "pre",
    // ★ 返回的仍是 **JSON 文本**，让 Vite 的 json 插件继续把它转成模块。
    //   第一版在 load 里返回 `export default …`，Rollup 仍按 .json 解析，构建直接失败。
    transform(code, id) {
      if (!id.includes("/src/data/taxonomy.json")) return null;
      const data = JSON.parse(code);
      delete data.rule_examples;
      if (data.meta) delete data.meta.boundary_disputes;   // 只删这一个键，meta 其余键保留
      return { code: JSON.stringify(data), map: null };
    },
  };
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const devIdentityEnabled =
    command === "serve" &&
    env.REVIEW_DEV_IDENTITY === "1" &&
    env.APP_ENV === "dev";
  const proxyTarget = env.REVIEW_API_PROXY ?? "http://127.0.0.1:8010";

  return {
    plugins: [stripInternalTaxonomy(), react()],
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
