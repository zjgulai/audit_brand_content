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

**开发验收写动作（只在 `vite serve` + `APP_ENV=dev` + `REVIEW_DEV_IDENTITY=1`）**
- `POST /cases/{id}/claim`
- `POST /cases/{id}/actions`（`save_draft` / `submit`）
- 每个用户意图带独立 Idempotency-Key；未知网络结果的显式重试复用同一 key/version/body
- 保存、提交均使用 GET 返回的台账 version，成功后再 GET 核对 version、草稿 ID 与 closed

**生产构建保持只读**：不含 `/dev/*`、替身 principal、写客户端 chunk、claim/actions 请求模板。
仍不包含 `release-decision` / `release-revoke` / `submissions`；confirm/reject 因后端权威写入与投影回读未闭继续禁用。
`check_production_bundle.mjs` 断言这条边界。

## 本地身份切换器

`web/scripts/review_api_dev.py` 提供 `GET /dev/identities` 与 `POST /dev/session`。
它默认拒绝启动，只有 `APP_ENV=dev` + `REVIEW_DEV_IDENTITY=1` 才注册使用；端点只接受 loopback client/Host/Origin。
页面不会自动建立替身身份，必须显式点击启用；切换会隐藏旧内容、清空备注并撤销旧 session。

**生产构建不包含开发身份模块**：Vite 按 `command === "serve"` 决定编译常量，任何 `build`（即使 mode/NODE_ENV 误配）都关闭开发身份与写模块。
正式入口 `api/review_api.py` 没有 `/dev/*`；部署网关仍须拒绝 `/dev/*`。

## 样例数据

`web/scripts/seed_fixture.py` 生成 21 条确定性夹具（固定种子，两次构建逐字节相同），
覆盖五标签、partial/full 覆盖、依据失效、规则冲突、三种未评估原因、空/换行/超长原文。

```bash
python3 web/scripts/seed_fixture.py --out <dir> [--merge]
python3 web/scripts/seed_fixture.py --selftest   # 13 项反向对照
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

## 部署准备（本轮不部署）

部署方案与上线阻塞清单见 [部署准备方案 v1](docs/deployment-plan-v1.md)。
目标机房环境以 `DEPLOY-01` 存本地部署记忆；内部地址、登录账号及凭据不进公开仓。
当前工作台是本地验收原型，**不是生产业务已就绪**：开发身份入口、写请求幂等/版本、
持久台账与投影新鲜度、真实认证与多模态等仍有上线前置；确认/驳回按钮继续禁用。

方案整理不等于部署授权。本轮不连接服务器、不上传、不改 DNS/TLS、不启动远端服务。

## 本地联调（非生产入口）

前置：仓库根有 `.venv`（uv 环境），本机有 Chrome。
从仓库根运行：

```bash
bash web/scripts/dev-up.sh
```

脚本做的事（失败退非零；不应拿到生产执行）：

1. 在临时目录生成 smoke 投影和报告，再合并 `seed_fixture.py` 的确定性样例；
2. 构建**生产包**并检查不含开发身份/写端点；运行 dev wrapper fail-closed 自证；
3. 显式建立每个浏览器自己的开发 session，检查队列与四页只读展示；
4. 真实执行认领→存草稿→提交复核意见→GET 回读，断言 version 0→1→2→3、草稿 ID 与 closed；
5. 跑 390px 无横向溢出/44px 触控门、无障碍、切片断言（A5 精确错误原因、A7 真跑夹具自证）与身份切换隔离；旧 session 必须撤销。

**边界说明**：所有写动作只针对临时内存台账，进程退出即丢；通过不代表生产持久化、真实 SSO、confirm/reject、draft/formal 全文恢复或投影重建已完成。
脚本会创建本地数据/session/审计并发出 POST，不是零副作用检查。最近实跑：11 阶段 rc=0，生产包 8/8、dev fail-closed 8/8、写链 version 0→1→2→3、无障碍 40 项 0 违规、切片 15/15、身份隔离与旧 session 撤销通过。

端口默认自动选空闲端口，可由 `REVIEW_API_PORT` / `WEB_PORT` 指定。
`check_queue_page.mjs` 的 `--expect` 只能取真实待办案件，不能再用 BLOCK 案件检验待办队列。

开发代理：`vite.config.ts` 把所有 `/review-api/*` 重写到 `/api/v1/*`，
包括 `/review-api/queue`；`/dev/*` 仅代理开发身份功能。
**Vite 代理不随静态构建发布**，正式部署需单独配置反代并拒绝 `/dev/*`。


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

`dev-up.sh` 第 9 步会跑它，失败非零。

**当前读数**（2026-10-21，批次 0）：**48 项检查 / 0 违规 / 8 条 WAIVED**
（7 条非文本对比 + 1 条 `/taxonomy` 1280×720 横向溢出 6px，见 `web/a11y-waivers-v1.json`；
每条有 owner + 到期日 + 票）。复现：`bash web/scripts/dev-up.sh` 的 [9/11]。
**修复前（三页时）**：30 项 / 9 违规 —— 每页各 3 项：缺 skip-link、无 `:focus-visible` 规则、聚焦元素无可见轮廓。

**明确未测（必须人工）**：键盘全流程、读屏语义与焦点顺序、动态内容播报、
200% 缩放 / reflow、`prefers-reduced-motion`、文本覆盖图片/渐变时的对比、真实用户测试。
自动对比度是近似计算，不等同于完整 WCAG 审计。
这些项在 `web/a11y-manual-v1.json` 里逐条登记，`npm run verify:a11y:manual` 对未签收退 2。

## 门禁（批次 0 · 2026-10-21）

`web/scripts/gate.sh` 是静态/构建门的**唯一入口**；`package.json` 只调它。

```bash
npm run verify:static        # DT-1…DT-8（设计 token）
npm run verify:build         # build + F11 体积预算 + 生产边界门
npm run verify:tokens        # 只跑 DT
npm run verify:budget        # 只跑 F11
npm run verify:visual        # 视觉基线（需要服务器）
npm run verify:a11y:manual   # TS-9 人工项签收台账
```

**退出码一律 0/1/2**：0 全绿，1 有红，**2 = 有未测（不是通过，也不是红）**。
每个新脚本都输出固定契约 `{ok, reds[], untested[], waived[], details[]}`，且**每次主检查
都真跑反向对照**（不是只在 `--selftest` 里跑）。

批次 0 的当前状态与「为什么有些是未测、有些是已知红」见
[`docs/frontend-baseline-v1.md`](docs/frontend-baseline-v1.md)。

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

