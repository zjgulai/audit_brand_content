# DESIGN · 内容审核工作台

> 本文件是**设计语言的唯一说明**。§8 有一段机器可读的 token 台账
> （以 TOKENS 的 BEGIN/END 注释标记围起来），由
> `node web/scripts/check_design_tokens.mjs --check` 与
> `src/styles/tokens.css` 逐项比对（DT-5）。
>
> ★ 正文里**不要**写出那对标记的字面量：解析器用的是正则找第一对标记，
> 说明文字里出现一次就会把机器块的起点提前，于是「DESIGN 有 ---，tokens.css 没有」。

---

## 1. 原型

**A1 分诊队列，选中项以 A7 证据文件的形式打开。**

完成那句话：「审核员看着**一张按紧迫度排序的案件队列**，对**其中一条的判定**动手。」

- **A1**：进件、分派、回复、批准 —— 就是复核队列的形态。
- **A7**：选中一条后，右侧展开的是一份**结构化证据文件**（不是表单），每段带可追溯引用。
- **不是 A12 表单**：工作流是「机器已出结果 → 人看 → 定性」。结论**已经存在**，
  人是在审视与追加，不是填表。
- **不是 A2 看板**：BLOCK 是终态、REVIEW 才转人。看板会暗示一条不存在的流水线。

## 2. 颜色：Radix Colors（2026-10-26 起）

**所有颜色来自 [Radix Colors](https://www.radix-ui.com/colors)，不再有自定义 HSL。**

色板与理由：

| 色板 | 角色 | 为什么是它 |
|---|---|---|
| **sand** | 中性（背景 / 面 / 文字 / 边框） | 暖灰，与品牌色同属暖区；界面不会一半暖一半冷 |
| **tomato** | 品牌（登录、主行动、选中） | hue≈12°，与 red（hue≈0°）距离够远，**状态红不会与品牌色混读** |
| **green** | 通过 / 合规 | — |
| **amber** | 待人工复核 / 部分覆盖 | — |
| **red** | 违规拦截 / 错误 | — |
| **blue** | 待检测 / 信息 | — |
| **purple** | 未测（独立状态） | 不与上面四个混用，避免「未测」被读成某种结论 |

### 2.1 十二步的固定用途（这是 Radix 的核心，不是色号排列）

| 步 | 用途 |
|---|---|
| 1 | 应用背景 |
| 2 | 次级背景（含槽位） |
| 3 | 组件背景（默认态） |
| 4 | 组件 hover 背景 |
| 5 | 组件 active / 选中背景 |
| 6 | 非交互细边框 |
| 7 | 边框 hover / 强分隔 |
| 8 | 边框 focus / 填充的强前景 |
| 9 | 实心填充（需要 3:1 对比的地方） |
| 10 | 实心 hover |
| 11 | 低对比文字（对第 2 步 ≥ 4.5:1） |
| 12 | 高对比文字 |

★ **业务 CSS 只许引用语义别名**（`--surface` / `--text-muted` / `--brand-surface`），
不许直接写 `--sand-7`。换色板只改 `tokens.css` 一处。

## 3. 字号：只有三档

字号只有三档，**值以 §8 台账为准**：

- **12px**（`text-sm`）：次要信息、表头、徽标、辅助说明。**最小可用尺寸。**
- **14px**（`text-base`）：正文、表单、列表、按钮。
- **18px**（`text-title`）：页面与区块标题。

**不足时不再加字号** —— 用**字重**（400 / 500 / 600）、**颜色**（`--text` vs `--text-muted`）
与**间距**建立层级。多一档字号就多一个「这个该用哪个」的判断。

## 4. 边框：0.5px

`--hairline: 0.5px`。1px 在 DPR≥2 的屏上会被放大成 2 物理像素，全部分隔都显得过重；
0.5px 才是一条线。

★ **已知取舍**：DPR=1 的老屏上 0.5px 可能被舍入为 0（边框不可见）。
本工作台的浏览器支持范围（桌面 Chrome 155+）实测 DPR≥2，所以按 0.5px 出图；
若将来要支持 DPR=1，应在 `@media (resolution: 1dppx)` 里回退到 1px，而不是改全局。

## 5. 圆角：两档，且嵌套同心

圆角只有两档，**值以 §8 台账为准**：

- **6px**（`radius-panel`）：面板 / 卡片 / 侧边栏。
- **4px**（`radius-control`）：面板内的控件（按钮 / 输入 / 徽标底）。

嵌套规则：**内层圆角 = 外层圆角 − 内边距**。面板 6px + 内边距 2px → 内层 4px，视觉同心。
药丸形（`999px`）只用于状态徽标与计数气泡，那是几何上「全圆」，与上面两档不冲突。

## 6. 阴影与色条：不使用

- **不使用阴影**：界面的层级由「面 + 0.5px 边框」表达，不靠投影。
  投影在亮色界面上会发灰，且每加一处就要判断「多深」——那是一处没有标准的判断。
- **不使用卡片左侧色条**：委托方 2026-10-26 明确要求移除。
  选中/状态一律用**背景色 + 字重**表达。

## 7. 动效

只有**一个时长**（`--motion: 250ms`）与**一条缓动**（`--ease: ease-out`），
且**只作用于颜色与边框**。不动的属性：`width` / `height` / `top` / `left`（会触发布局抖动）。

`prefers-reduced-motion: reduce` 下全部关闭。

## 8. 机器可读 Token 台账（DT-5 等式权威源）

<!-- TOKENS:BEGIN -->
| Token | Value | 用途说明 |
| :--- | :--- | :--- |
| `--sand-1` | #fdfdfc |  |
| `--sand-2` | #f9f9f8 |  |
| `--sand-3` | #f1f0ef |  |
| `--sand-4` | #e9e8e6 |  |
| `--sand-5` | #e2e1de |  |
| `--sand-6` | #dad9d6 |  |
| `--sand-7` | #cfceca |  |
| `--sand-8` | #bcbbb5 |  |
| `--sand-9` | #8d8d86 |  |
| `--sand-10` | #82827c |  |
| `--sand-11` | #63635e |  |
| `--sand-12` | #21201c |  |
| `--brandc-1` | #fdfafa | Momcozy 酒红 step 1 |
| `--brandc-2` | #faf3f4 | step 2 |
| `--brandc-3` | #f5e6e9 | step 3（淡底） |
| `--brandc-4` | #eed9dd | step 4 |
| `--brandc-6` | #dfb9c0 | step 6（细边框） |
| `--brandc-8` | #c98492 | step 8（focus 环） |
| `--brandc-9` | #a94159 | step 9（纯图形） |
| `--brandc-11` | #6a2b3a | Momcozy 酒红 #6A2B3A（logo 主色） |
| `--brandc-12` | #38121c | step 12（高对比） |
| `--tomato-1` | #fffcfc |  |
| `--tomato-2` | #fff8f7 |  |
| `--tomato-3` | #feebe7 |  |
| `--tomato-4` | #ffdcd3 |  |
| `--tomato-5` | #ffcdc2 |  |
| `--tomato-6` | #fdbdaf |  |
| `--tomato-7` | #f5a898 |  |
| `--tomato-8` | #ec8e7b |  |
| `--tomato-9` | #e54d2e |  |
| `--tomato-10` | #dd4425 |  |
| `--tomato-11` | #d13415 |  |
| `--tomato-12` | #5c271f |  |
| `--green-1` | #fbfefc |  |
| `--green-2` | #f4fbf6 |  |
| `--green-3` | #e6f6eb |  |
| `--green-4` | #d6f1df |  |
| `--green-5` | #c4e8d1 |  |
| `--green-6` | #adddc0 |  |
| `--green-7` | #8eceaa |  |
| `--green-8` | #5bb98b |  |
| `--green-9` | #30a46c |  |
| `--green-10` | #2b9a66 |  |
| `--green-11` | #218358 |  |
| `--green-12` | #193b2d |  |
| `--amber-1` | #fefdfb |  |
| `--amber-2` | #fefbe9 |  |
| `--amber-3` | #fff7c2 |  |
| `--amber-4` | #ffee9c |  |
| `--amber-5` | #fbe577 |  |
| `--amber-6` | #f3d673 |  |
| `--amber-7` | #e9c162 |  |
| `--amber-8` | #f2a600 |  |
| `--amber-9` | #ffc53d |  |
| `--amber-10` | #ffba18 |  |
| `--amber-11` | #ab6400 |  |
| `--amber-12` | #4f3422 |  |
| `--red-1` | #fffcfc |  |
| `--red-2` | #fff0f0 |  |
| `--red-3` | #feebec |  |
| `--red-4` | #ffdbdc |  |
| `--red-5` | #ffcdce |  |
| `--red-6` | #fdbdbe |  |
| `--red-7` | #f4a9aa |  |
| `--red-8` | #eb8e90 |  |
| `--red-9` | #e5484d |  |
| `--red-10` | #dc3e42 |  |
| `--red-11` | #ce2c31 |  |
| `--red-12` | #641723 |  |
| `--blue-1` | #fbfdff |  |
| `--blue-2` | #f4faff |  |
| `--blue-3` | #e6f4fe |  |
| `--blue-4` | #d5efff |  |
| `--blue-5` | #c2e5ff |  |
| `--blue-6` | #acd8fc |  |
| `--blue-7` | #8ec8f6 |  |
| `--blue-8` | #5eb1ef |  |
| `--blue-9` | #0090ff |  |
| `--blue-10` | #0588f0 |  |
| `--blue-11` | #0d74ce |  |
| `--blue-12` | #113264 |  |
| `--bg` | var(--sand-2) | 应用背景（sand-2） |
| `--surface` | #ffffff | 卡面（纯白） |
| `--surface-muted` | var(--sand-3) | 次级面与分段底（sand-3） |
| `--surface-hover` | var(--sand-4) | 组件 hover（sand-4） |
| `--surface-active` | var(--sand-5) | 组件 active（sand-5） |
| `--text` | var(--sand-12) | 主文字（sand-12） |
| `--text-muted` | var(--sand-11) | 次要文字（sand-11） |
| `--rule` | var(--sand-4) | 行内弱分隔（sand-4） |
| `--border` | var(--sand-5) | 容器与面板外沿（sand-5） |
| `--border-strong` | var(--sand-9) | 控件边框（sand-9，3.28:1） |
| `--brand` | var(--brandc-11) | 品牌实心底（brandc-11 #6A2B3A） |
| `--brand-hover` | var(--brandc-12) | 品牌 hover（brandc-12） |
| `--brand-graphic` | var(--brandc-9) | 纯图形品牌色（brandc-9） |
| `--brand-text` | var(--brandc-11) | 品牌文字（brandc-11） |
| `--brand-text-on-surface` | var(--brandc-12) | 品牌淡底上的文字（brandc-12） |
| `--brand-surface` | var(--brandc-3) | 品牌淡底（brandc-3） |
| `--brand-ring` | var(--brandc-8) | 焦点环（brandc-8） |
| `--ok` | var(--green-11) | 通过实心底（green-11） |
| `--ok-graphic` | var(--green-9) | 通过图形色（green-9） |
| `--ok-text` | var(--green-11) | 通过文字（green-11） |
| `--ok-surface` | var(--green-3) | 通过淡底（green-3） |
| `--warn` | var(--amber-11) | 待复核实心底（amber-11） |
| `--warn-graphic` | var(--amber-9) | 待复核图形色（amber-9） |
| `--warn-text` | var(--amber-11) | 待复核文字（amber-11） |
| `--warn-surface` | var(--amber-3) | 待复核淡底（amber-3） |
| `--bad` | var(--red-11) | 拦截实心底（red-11） |
| `--bad-graphic` | var(--red-9) | 拦截图形色（red-9） |
| `--bad-text` | var(--red-11) | 拦截文字（red-11） |
| `--bad-surface` | var(--red-3) | 拦截淡底（red-3） |
| `--info` | var(--blue-11) | 待检测实心底（blue-11） |
| `--info-graphic` | var(--blue-9) | 待检测图形色（blue-9） |
| `--info-text` | var(--blue-11) | 待检测文字（blue-11） |
| `--info-surface` | var(--blue-3) | 待检测淡底（blue-3） |
| `--untested-text` | var(--sand-11) | 未测文字（sand-11，中性灰） |
| `--untested-surface` | var(--sand-3) | 未测淡底（sand-3） |
| `--ring` | var(--brandc-8) | 焦点环（brandc-8） |
| `--hairline` | 0.5px | 边框宽度 0.5px |
| `--radius-panel` | 8px | 卡圆角 8px |
| `--radius-control` | 6px | 控件圆角 6px |
| `--radius-chip` | 4px | 徽标圆角 4px |
| `--text-sm` | 12px | 12px，仅徽标/表头/时间戳 |
| `--text-base` | 14px | 14px 正文 |
| `--text-section` | 16px | 16px 区块与卡标题 |
| `--text-title` | 20px | 20px 页面 h1 |
| `--leading-base` | 1.43 | 正文行高 1.43（14→20px） |
| `--leading-title` | 1.3 | 标题行高 1.3 |
| `--space-1` | 4px |  |
| `--space-2` | 8px |  |
| `--space-3` | 12px |  |
| `--space-4` | 16px |  |
| `--space-5` | 24px |  |
| `--space-6` | 32px |  |
| `--motion` | 250ms | 唯一过渡时长 250ms |
| `--ease` | ease-out | 唯一缓动 ease-out |
| `--on-brand` | #ffffff | 品牌实心底上的白字 |
| `--border-subtle` | var(--hairline) solid var(--border) | 0.5px 细边框 |
| `--border-dashed` | var(--hairline) dashed var(--border) | 0.5px 虚线边框 |
| `--border-control` | var(--hairline) solid var(--border-strong) | 0.5px 控件边框 |
| `--outline-active` | 2px solid var(--brand) | 激活轮廓 |
| `--page-max` | 96rem | 版心最大宽度 |
| `--sidebar-w` | 15rem | 侧边栏展开宽度 |
| `--sidebar-w-collapsed` | 4rem | 侧边栏收起宽度 |
| `--sidebar-w-narrow` | 2.75rem | 侧边栏极窄档 |
| `--topbar-h` | 3rem | 顶栏高度 48px |
| `--ui-font-sans` | -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif | 界面无衬线字体族 |
| `--ui-font-mono` | ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace | 等宽字体族 |
<!-- TOKENS:END -->

---

## 9. 文案规则（委托方 2026-10-26 第 1–3 条）

1. **不用中点「·」作分隔符。** 需要分隔时用逗号、换行，或直接分成两个元素。
2. **不加解释性描述。** 界面上的每一句话都要回答一个用户会问的问题；
   回答不了的话就不写。装饰性文案（「品牌内容在对外发布之前…」）一律删。
3. **文案面向审核员与业务方**：容易理解，但不过度口语化；长度与功能场景匹配；
   不自造词。术语对照见 §10。

## 10. 术语对照（界面用词，不是研发词）

| 系统内部 | 界面用词 |
|---|---|
| BLOCK | 违规拦截 |
| REVIEW | 待人工复核 |
| PASS | 审核通过 |
| 待自决 | 品牌自决 |
| 未审查 | 待检测 |
| ContentUnit | 原文内容 |
| coverage full / partial | 全规则覆盖 / 部分规则覆盖 |
| severity L4 / L5 | 极高危 |

## 11. 执行点

| 检查 | 命令 | 它验什么 |
|---|---|---|
| 设计 token | `node web/scripts/check_design_tokens.mjs --check` | 无裸值、tokens.css ≡ DESIGN 台账、无直接 lucide import、无 Unicode 图标、Button variant 合规 |
| 几何与布局 | `bash web/scripts/dev-up.sh` | 侧边栏一列不折行、主内容不被挤压、SPA 深链、44px 触控底线、320px reflow |
| 无障碍 | 同上（`a11y_check.mjs`） | 15 条路由 × 2 视口：对比度、h1 唯一、控件名称、焦点可见 |
| 视觉 | `node web/scripts/check_visual.mjs` | 截图基线比对 |
