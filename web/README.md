# Web 复核工作台

Vite + React 19 + TypeScript + React Router。

**阶段二（2026-10-20 起）：只写人工动作，仅经写 API，仍不重算判定。**
判定逻辑的唯一产地是 `base/` 与 `PMO/implement/内容审查分类规范-v1.md`；
Web 只展示判定结果，并把复核员的动作（claim / save_draft / submit）发给写 API。
详见下方「边界」。

## 工具链说明

- 本机 **pnpm 不可用**（`pnpm: command not found`），因此本工程用 **npm**。
- Node 版本：v24.21.0；npm：11.12.1。

## 启动

```bash
cd web
npm install
npm run dev          # 默认 http://localhost:5173
```

一键联调（临时投影 + 真实 review-api + Vite + 页面断言 + 无障碍 + 切片断言）：

```bash
bash web/scripts/dev-up.sh
```

## 指向后端

API 基址由环境变量 `VITE_REVIEW_API_BASE` 注入，默认同源 `/review-api`：

```bash
VITE_REVIEW_API_BASE=http://127.0.0.1:8000/review-api npm run dev
```

生产构建同样在构建时注入：

```bash
VITE_REVIEW_API_BASE=https://example.com/review-api npm run build
```

## 路由

| 路由 | 页面 | 形态 |
|---|---|---|
| `/queue` | 复核队列 | A1 Triage queue —— 只列 REVIEW / 待自决 |
| `/cases/:caseId` | 案件详情 | A7 研究简报 —— 判定 + 证据链 + 复核动作 |
| `/reports/:reportId` | 报告查看 | 不可变静态存档的元信息 |
| `/taxonomy` | 分类规范 | 七轴 / 七步 / 正交字段 / rule_id 查找 / 欠定登记 |

## API client

`src/api/client.ts`：

**读（5 个 GET）**
- `GET /cases`
- `GET /queue` —— **真队列**，只返回 REVIEW 与 待自决
  （`api/review_api.py:459`。旧的 `/review-api/queue` 是「全部可读案件」的联调别名，已废弃）
- `GET /cases/{id}`
- `GET /reports`
- `GET /reports/{id}`

**写（只人工动作，不经这些端点改判定与放行）**
- `POST /cases/{id}/claim` · `/unclaim`
- `POST /cases/{id}/actions`（`save_draft` / `submit` / `confirm` / `reject`）

**不包含** `release-decision` / `release-revoke` / `submissions`。
阶段二 Web 仍不提供签发、撤回或发布入口 —— 这条由 `check_review_slice.mjs` 的 **A4** 断言。

## 本地身份切换器

`web/scripts/review_api_dev.py` 提供 `GET /dev/identities` 与 `POST /dev/session`，
页面右上角据此切换 DP3 / DP4 / 签发人。

**它只存在于本地联调入口**：生产入口 `api/review_api.py` 没有这些路由，一行都没改。
它也不是登录：不保存、不校验凭据，只接受已登记的几个 principal id。

## 样例数据

`web/scripts/seed_fixture.py` 生成 21 条确定性夹具（固定种子，两次构建逐字节相同），
覆盖五标签、partial/full 覆盖、依据失效、规则冲突、三种未评估原因、空/换行/超长原文。

```bash
python3 web/scripts/seed_fixture.py --out <dir> [--merge]
python3 web/scripts/seed_fixture.py --selftest   # 12 项反向对照
```

每条带 `sample: true`。`dev-up.sh` 用 `--merge` 与 `case-smoke` 这条真实案件并存。

## 断言

```bash
node web/scripts/check_review_slice.mjs --base <web> --api <api> --cookie <opaque>
```

覆盖 A1（队列口径，含**反向对照**：塞 PASS/BLOCK 必须不出现）、A2（不许把 null 折叠成 `—`）、
A3（partial 必须标「仅已覆盖部分可判」）、A4（前端不得有签发调用）、A5（submit 缺 conclusion 必被拒）、
A6（品牌红不得用于状态徽标）、A8（欠定条目渲染 underdetermined）、A9（spec 版本与指纹同时出现）。

退出码 `0` 通过 / `1` 有断言红 / `2` 有未测（**2 不是通过**）。

## 边界


## 本地联调（真实后端）

前置：仓库根有 `.venv`（uv 环境），本机有 Chrome。

```bash
./scripts/dev-up.sh
```

脚本做的事（幂等，失败退非零）：

1. 用 `tools/smoke_end_to_end.py` 的 `SMOKE_DUMP_IR` 在**临时目录**生成投影（`cases.json`，含 `case-smoke`）；
2. 用 `scripts/seed_projection.py` 给临时投影补一条 `report-smoke`（仍只写临时目录）；
3. `npm run build`；
4. 建本地 session（`u_dp3` / `t1`），启动真实 `api/review_api.py`（经 `scripts/review_api_dev.py` 装配临时投影 + session store）；`review_api_dev.py` 里的 `u_dp3` / `u_signer` 是**本地替身 principal**（固定 `open_id` / `tenant_id`），仅供 dev 联调，不是生产 IdP 身份；
5. 启动 Vite dev，`/review-api` 反向代理到后端；
6. `curl /review-api/queue` 断言 200 且含 `case-smoke`；
7. 用本机 Chrome（CDP）走 **队列 → 案件详情 → 报告查看 → 分类规范** 四段：
   断言案件页渲染 `case-smoke / BLOCK / DP2 / 待放行 / 覆盖证明 / H01`，
   报告页渲染 `report-smoke / case-smoke / 发布时刻`，分类规范页渲染七个轴码、七步判定、正交字段与 rule_id 查找框；截图与日志落在临时目录。

端口默认自动选空闲端口；也可用 `REVIEW_API_PORT` / `WEB_PORT` 指定。
脚本只读：不调用任何写端点，不写仓库内文件。

只想单独断言队列页是否渲染出某个案件时，可直接用
`node scripts/check_queue_page.mjs --url http://127.0.0.1:5173/queue --cookie "$COOKIE" --expect case-smoke`；
它用本机 Chrome CDP，不依赖 Playwright，失败退 1、Chrome 起不来退 2。

开发代理：`vite.config.ts` 把 `/review-api` 代理到 `REVIEW_API_PROXY`（默认 `http://127.0.0.1:8010`），dev-up 会注入实际后端端口。
重写规则：`/review-api/queue` 保持原样（后端联调别名），其余 `/review-api/*` 重写到 `/api/v1/*`（cases / reports 只读端点）。

## 无障碍（WCAG 2.2 AA 基线）

`scripts/a11y_check.mjs` 对 `/queue`、`/cases/:caseId`、`/reports/:reportId`、`/taxonomy` 四页跑
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

**当前读数**：40 项检查 / 0 违规（四页各 10 项；以脚本实跑为准）。
**修复前（三页时）**：30 项 / 9 违规 —— 每页各 3 项：缺 skip-link、无 `:focus-visible` 规则、聚焦元素无可见轮廓。

**明确未测（必须人工）**：键盘全流程、读屏语义与焦点顺序、动态内容播报、
200% 缩放 / reflow、`prefers-reduced-motion`、文本覆盖图片/渐变时的对比、真实用户测试。
自动对比度是近似计算，不等同于完整 WCAG 审计。

## 构建

```bash
npm run build        # tsc -b && vite build，产物在 dist/
npm run preview      # 本地预览构建产物
```

## 边界

> **2026-10-20 改定**（委托方同意）：原第 1 条「不碰 `base/`、`api/`、`tools/`」与第 2 条开头
> 「不写判定逻辑」把「不重算」说成了「不写」—— 于是接复核动作时，边界看起来像被推翻了。
> 实际上**边界没有消失，只是换了一句话**：Web 仍然不重算判定，但它可以**经写 API 写人工动作**。
> 两条分开记，是因为它们本来是两个约束。

- **不重算判定。** `state` / `coverage` / `authority` / `release_status` 一律读后端返回，前端不做任何推导。
  改了这条就等于把「唯一判定」搬到浏览器里。
- **人工动作只经写 API。** 认领 / 存草稿 / 提交结论 / 确认驳回 / 申诉 / 签发撤回，只走
  `api/write_api.py` 已挂载的端点（它们在 `api/review_api.py:553` 注册）。**前端不得直接构造
  状态变更，也不得绕过端点改文件。** 这些端点各自有 `can_act` / `require_review` / 租户校验。
- **`release_status` 不出现任何可写控件。** 五标签全部止于「待放行」；只有
  `POST /cases/{id}/release-decision` 能改，且必须是人显式动作（含理由与 step-up）。
  前端不发送该字段 —— 这条是硬门，见 `web/docs/handoff-4b.md` 的断言 A4。
- **不碰 `base/`、`api/`、`tools/` 的源码。** 调它们的 HTTP 接口不算碰它们。
  需要改后端才能做的事，记成 ticket 交给后端，不在前端绕过去。
- **报告是不可变静态存档**；Web 不编辑、不重算。

> ⚠️ 以上第 1、2、3 条都必须在 `web/scripts/check_review_slice.mjs` 里有执行点。
> 只写在 README 里、指不出断言的上限，按 `AGENTS.md` §2.4 就是注释，不是约束。

