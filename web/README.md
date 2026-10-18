# Web 复核工作台 v0（脚手架）

阶段一 Web 工作台的最小前端骨架：Vite + React 19 + TypeScript + React Router。
**只做只读展示**，不实现业务逻辑，不调用 release / 签发 / 撤回接口。

## 工具链说明

- 本机 **pnpm 不可用**（`pnpm: command not found`），因此本工程用 **npm**。
- Node 版本：v24.21.0；npm：11.12.1。

## 启动

```bash
cd web
npm install
npm run dev          # 默认 http://localhost:5173
```

## 指向后端

API 基址由环境变量 `VITE_REVIEW_API_BASE` 注入，默认同源 `/review-api`：

```bash
VITE_REVIEW_API_BASE=http://127.0.0.1:8000/review-api npm run dev
```

页面右上角会显示当前 API 基址。生产构建同样在构建时注入：

```bash
VITE_REVIEW_API_BASE=https://example.com/review-api npm run build
```

## 路由（占位）

| 路由 | 页面 |
|---|---|
| `/login` | 登录占位（飞书 OAuth/SSO 后续接入） |
| `/queue` | 复核队列占位 |
| `/cases/:caseId` | 案件详情占位 |
| `/reports/:reportId` | 报告查看占位 |

## API client（只读）

`src/api/client.ts` 只有 GET：

- `GET /cases`
- `GET /queue`（联调别名 `/review-api/queue`，只读列出可读案件）
- `GET /cases/{id}`
- `GET /reports`
- `GET /reports/{id}`

**不包含** `release-decision` / `release-revoke` / `submissions` / claim / 任何写端点。
阶段一 Web 不提供签发、撤回或发布入口。

## 本地联调（真实后端）

前置：仓库根有 `.venv`（uv 环境），本机有 Chrome。

```bash
./scripts/dev-up.sh
```

脚本做的事（幂等，失败退非零）：

1. 用 `tools/smoke_end_to_end.py` 的 `SMOKE_DUMP_IR` 在**临时目录**生成投影（`cases.json`，含 `case-smoke`）；
2. 用 `scripts/seed_projection.py` 给临时投影补一条 `report-smoke`（仍只写临时目录）；
3. `npm run build`；
4. 建本地 session（`u_dp3` / `t1`），启动真实 `api/review_api.py`（经 `scripts/review_api_dev.py` 装配临时投影 + session store）；
5. 启动 Vite dev，`/review-api` 反向代理到后端；
6. `curl /review-api/queue` 断言 200 且含 `case-smoke`；
7. 用本机 Chrome（CDP）走 **队列 → 案件详情 → 报告查看** 三段：
   断言案件页渲染 `case-smoke / BLOCK / DP2 / 待放行 / 覆盖证明 / H01`，
   报告页渲染 `report-smoke / case-smoke / 发布时刻`；三张截图与日志落在临时目录。

端口默认自动选空闲端口；也可用 `REVIEW_API_PORT` / `WEB_PORT` 指定。
脚本只读：不调用任何写端点，不写仓库内文件。

开发代理：`vite.config.ts` 把 `/review-api` 代理到 `REVIEW_API_PROXY`（默认 `http://127.0.0.1:8010`），dev-up 会注入实际后端端口。
重写规则：`/review-api/queue` 保持原样（后端联调别名），其余 `/review-api/*` 重写到 `/api/v1/*`（cases / reports 只读端点）。

## 构建

```bash
npm run build        # tsc -b && vite build，产物在 dist/
npm run preview      # 本地预览构建产物
```

## 边界

- 不碰 `base/`、`api/`、`tools/`。
- 不写判定逻辑，不重算 state / coverage / authority。
- 报告是不可变静态存档；Web 不编辑、不重算。
