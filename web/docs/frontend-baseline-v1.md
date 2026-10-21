# 前端基线 v1（批次 0 · 2026-10-21）

> **这份文件只记读数，不记结论。** 每个数字都带复现命令；没有命令的数字不写。
> 口径：`2026-10-21 10:5x CST` 在本机（macOS / Node 24 / Chrome headless）实测。
> 别人复跑差几 KB 属正常 —— 差一个数量级才是真变化。

---

## 1. 构建与体积

```bash
cd web && npm run build
python3 - <<'PY'
import gzip
from pathlib import Path
for p in sorted(Path("dist/assets").iterdir()):
    b = p.read_bytes(); print(p.name, len(b), len(gzip.compress(b, 9)))
PY
```

| 产物 | raw | gzip |
|---|---:|---:|
| `index-*.js` | 366,695 B | **120,141 B** |
| `index-*.css` | 9,499 B | **2,535 B** |
| `dist/.vite/manifest.json` | —— | **不存在**（`vite.config.ts` 批次 0 不动，Stage 1 才加 `manifest: true`） |

`web/budgets.json` 的 `baseline` 段就是这三个数；预算上限仍是方案 §6.9 的临时值
（initial 170,000 / total 240,000 / css 20,000 / route 80,000）。

## 2. 联调（`dev-up.sh`，11 阶段）

```bash
bash web/scripts/dev-up.sh     # rc=0
```

| 阶段 | 读数 |
|---|---|
| [2/11] 生产 bundle 边界 | 9/9（含 hostile-build 反向对照） |
| [7/11] 页面断言（队列/详情/报告/分类规范） | 通过；390×844 无横向溢出、控件 ≥44px |
| [8/11] 复核写动作 | claim → draft → submit → GET 回读，版本 0→1→2→3 |
| [9/11] **无障碍自动门** | **48 项检查 · 0 违规 · 8 条 WAIVED**（见 §4） |
| [10/11] 复核切片 | **17/17 通过 · 0 未测** |
| [11/11] 身份切换隔离 | 通过 |

★ `dev-up.sh` 的阶段数**仍是 11**（方案 L887：Stage 1 写链收口后才接 `gate.sh`；
批次 0 没有改它）。

## 3. 各门的当前状态

| 门 | 命令 | 状态 | 说明 |
|---|---|---|---|
| 设计 token | `npm run verify:static` | **退 2（未测）** | DT-1/2/3/8a 绿；DT-4/5/6/7/8b 的判据对象（`tokens.css` / `Button` / `icon.tsx`）Stage 2/5 才建 |
| 体积预算 | `npm run verify:build` / `verify:budget` | **退 2（未测）** | 没有 `dist/.vite/manifest.json`，不猜 initial/route（方案 §6.9） |
| 人工 a11y | `npm run verify:a11y:manual` | **退 2（未测）** | `web/a11y-manual-v1.json` 9 项全部 `not_run`；Stage 7 才签收 |
| 视觉基线 | `npm run verify:visual` | **退 2（未测）** | `design-baseline.json` 还没有 `visual` 段（需要服务器跑 `--update`） |
| 生产边界 | `npm run build` 内嵌 | **0** | 9/9 |

这些「退 2」不是坏消息：**未测 ≠ 通过 ≠ 红**。把它们写成绿才是坏消息。

## 4. Waiver 与已知红

`web/a11y-waivers-v1.json`（每条 owner + expires + ticket）：

| ID | 规则 | 读数 | 到期 | 票 |
|---|---|---|---|---|
| W-005 | 非文本对比 | 7 个控件边框 1.39:1（<3:1） | 2026-11-30 | T-WEB-02 |
| W-006 | 1280×720 reflow | `/taxonomy` scrollWidth 1286 > 1280（6px） | 2026-11-30 | T-WEB-05 |

**已知红（不豁免、必须保持可见）：**

- **A2d**：`case-edge-missing-authority` 的 finding 缺 `authority_state` 时，
  详情页因 `CaseDetailPage.tsx:101` 的 `?? "ok"` 显示 **「可核」**。
  复现：`seed_fixture.py --out <dir> --merge --edge` 后跑
  `check_review_slice.mjs --require-edge` → A2d 红、A2e 绿。
  **本项不是 waiver，是未修的真实缺陷；Stage 5 修（T-WEB-05）。**
  `web/src/**` 在批次 0 冻结（方案 L887），且方案 L932 的出口条款逐字要求
  「A2 在缺字段夹具上必须红」—— 开豁免等于把真 bug 登记成「已批准」。
  `dev-up.sh` 不 seed `--edge`，所以它不会在 [10/11] 里出现 —— 这是**未验证**，不是绿。

- **DT-8b**：正文仍使用 Unicode 图标（`←` `⚠`）3 个文件；合规入口 `src/ui/icon.tsx`
  Stage 2 建。当前报**未测**，并把命中文件列在 gate 的 `untested` 里。

## 5. 回退办法（含方案 L934 没覆盖的四个文件）

方案 L934 只写「删除新增脚本与文档，恢复三只门脚本与 `seed_fixture.py`」。
**`web/package.json`、`web/README.md`、`web/docs/handoff-4b.md`、`web/docs/deployment-plan-v1.md`
不在那句里**，逐条给出回退：

| 文件 | 回退 |
|---|---|
| `web/package.json` | 删掉 `verify:*` 六个 scripts（`static` / `build` / `visual` / `a11y:manual` / `tokens` / `budget`），其余一字不动；`dependencies` / `devDependencies` 批次 0 **没加任何包** |
| `web/README.md` | 删除「批次 0 门禁」一节（本文件对应段），恢复原文 |
| `web/docs/handoff-4b.md` | 删除「批次 0 交接」一节 |
| `web/docs/deployment-plan-v1.md` | 删除「批次 0 前端门禁」一节；**本节之前的后端装配改数不是本批次写的，不要一起回退** |
| 新增 10 项 | `git rm` 本文件 + `gate.sh`、`check_design_tokens.mjs`、`check_bundle_budget.mjs`、`check_visual.mjs`、`verify_manual_a11y.mjs`、`a11y-manual-v1.json`、`a11y-waivers-v1.json`、`design-baseline.json`、`budgets.json` |
| 三只门脚本 + `seed_fixture.py` | `git checkout -- web/scripts/check_review_slice.mjs web/scripts/a11y_check.mjs web/scripts/check_pages.mjs web/scripts/seed_fixture.py` |

零应用影响：这些文件都不进生产 bundle。

## 6. 批次 0 没做的（明确留给后续）

- `vite.config.ts` 的 `build.manifest`（Stage 1，文件在「不动」清单里）
- `dev-up.sh` 接 `gate.sh` 与人工 a11y（Stage 1 / Stage 7，文件冻结）
- `check_pages.mjs` 的 `--desktop` / `--reflow` 已实现但**默认关**（Stage 7 才启用）。
  实测（2026-10-21）：`--desktop --reflow` 下 `/queue` 与 `/cases/<id>` 在 1280×720 与
  320px 均无横向溢出（scrollWidth == innerWidth）；`/taxonomy` 的 6px 溢出由 a11y 侧 W-006 记着
- `tools/verify_frontend_deps.py`（Stage 1；本批次没有它，故 `package.json` 也没加 `verify:deps`）
