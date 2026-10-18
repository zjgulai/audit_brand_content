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

## 无障碍（WCAG 2.2 AA 基线）

`scripts/a11y_check.mjs` 对 `/queue`、`/cases/:caseId`、`/reports/:reportId` 三页跑
可自动化检查（Chrome CDP；离线环境未引入 axe-core）：

- `html[lang]` 非空
- 每页恰好一个 `h1`
- `img` 有非空 `alt`（当前工程无图片）
- `input/select/textarea` 有 label（label/for、包裹 label、aria-label/labelledby）
- 按钮有可访问名称
- skip-link 存在且指向 `#main`
- 存在 `:focus-visible` 规则，聚焦元素有可见轮廓
- 文本颜色对比：普通文本 ≥4.5、大字 ≥3.0；背景图/渐变/透明度非 1 的项跳过并列入 `unmeasured`

`dev-up.sh` 第 8 步会跑它，失败非零。

**当前读数**：30 项检查 / 0 违规（三页各 10 项）。
**修复前**：30 项 / 9 违规 —— 每页各 3 项：缺 skip-link、无 `:focus-visible` 规则、聚焦元素无可见轮廓。

**明确未测（必须人工）**：键盘全流程、读屏语义与焦点顺序、动态内容播报、
200% 缩放 / reflow、`prefers-reduced-motion`、文本覆盖图片/渐变时的对比、真实用户测试。
自动对比度是近似计算，不等同于完整 WCAG 审计。

## 构建

```bash
npm run build        # tsc -b && vite build，产物在 dist/
npm run preview      # 本地预览构建产物
```

## 边界

- 不碰 `base/`、`api/`、`tools/`。
- 不写判定逻辑，不重算 state / coverage / authority。
- 报告是不可变静态存档；Web 不编辑、不重算。
