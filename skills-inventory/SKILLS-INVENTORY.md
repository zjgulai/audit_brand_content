# Momcozy 品牌内容审计 Agent —— 本地技能库盘点报告

> **盘点对象**：`/Users/lute/Project/audit_multi_content/skills/`
> **产出**：本报告 + `index.json`（964 条结构化索引）+ `refs/`（18 个关键技能原文留档）
> **方法**：全量枚举 → 逐包解压 → frontmatter 解析 → 关键词信号打分 → 人工复核高价值项
> **口径说明**：本报告所有数字均由脚本实测得出，命令见 §10。凡引用第三方技能原文处均标注来源路径与许可状态。

---

## 0. 一页结论

| 结论 | 内容 |
|---|---|
| **规模** | 全库 **964 条**装载条目，去重后 **629 个**真实技能——实际条目数是任务书估算（~510）的 **1.9 倍** |
| **最大遗漏** | 任务书未提及的 **`MinMaxDesign/`（107 个）**，却是与"视频拆解 / 品牌广告 / 社媒文案 / 电商图规"重合度最高的一批 |
| **最强单点复用** | `Manus/skill01/seo-content-audit.skill` —— 已经是完整的 pre-publish gate 形态，**改 rubric 就能用** |
| **最大工程陷阱** | 442/777 个压缩包**直接读会得到乱码**（不是编码问题，是文件系统层面的读取异常），必须先 `cp` 再处理 |
| **最大缺口** | CPSC/CPSIA、NAD、TikTok/Meta/YouTube/Amazon 平台政策、UGC 披露（#ad/#sponsored）、健康宣称 **全部 0 命中**；FTC 无任何技能以其为职责 |
| **权属** | **682/964（70.7%）未声明许可证**；`MinMaxDesign` 107 个**全部未声明**，`Manus` 496/670 未声明 |
| **可直接借的评测脚手架** | 11 个 Manus 技能自带 `evals/evals.json`（prompt + expected_output + assertions），是全库唯一的"样例库"形态 |
| **相关性分布（按内容去重 629）** | high 28 / medium 151 / low 229 / none 221 —— 约 4.5% 真正高相关，另有 35% 与内容审计完全无关 |

---

## 1. 规模修正

### 1.1 实测构成

| 来源目录 | 载体 | 条目数 | 内容去重后 |
|---|---|---:|---:|
| `skills/Manus/skill01/` | `*.skill`（ZIP 容器） | 335 | 335 |
| `skills/Manus/skill02/` | `*.zip`（ZIP 容器） | 335 | **0（与 skill01 完全重复）** |
| `skills/MinMaxDesign/` | `*.zip`（ZIP 容器） | 107 | 107 |
| `skills/kimi/skills/` | 普通目录 | 170 | 170 |
| `skills/MinMax/skills/` | 普通目录 | 17 | 17 |
| **合计** | | **964** | **629** |

> `kimi` 的 170 条来自 **133 个顶层目录**：其中 `gitlab-cli-guide` 一个目录内含 **38 个子技能**（`glab-mr`、`glab-issue`、`glab-ci`…），按 SKILL.md 计为 38 条。

### 1.2 与任务书估算的差异

任务书估 ~510 条，实测 964 条。差额来自两处：

1. **`MinMaxDesign/` 整目录未在任务书列举范围**（+107）。这是本次盘点最有价值的发现——它覆盖视频解构、品牌广告、平台文案、电商图规等领域，与审计 Agent 的重合度高于 `Manus`。
2. **`Manus` 双目录重复装载**（skill02 是 skill01 的完整副本，335 条冗余）。

按内容去重后为 **629**：即便只按去重口径，也高于 510（差额主要来自 `MinMaxDesign` 107 + `kimi` 的 38 个 `gitlab-cli-guide` 子技能）。

### 1.3 相关性分布

按 964 条原始条目统计：

| 相关性 | 条数 | 占比 |
|---|---:|---:|
| high（可直接进审计管线） | 40 | 4.1% |
| medium（改造后可用） | 237 | 24.6% |
| low（结构可借、内容无关） | 338 | 35.1% |
| none（与内容审计无关） | 349 | 36.2% |

按内容去重（629）统计：**high 28 / medium 151 / low 229 / none 221**——真正高相关的仅 4.5%。

按管线阶段统计（964 条原始条目 / 629 条去重后）：

| 阶段 | 964 条 | 629 条 |
|---|---:|---:|
| 审计 | 93 | 56 |
| 拆解 | 51 | 37 |
| 优化 | 54 | 37 |
| 知识库 | 27 | 17 |
| 分析 | 62 | 41 |
| 采集 | 25 | 14 |
| 报告 | 123 | 79 |
| 无关 | 529 | 348 |

---

## 2. 格式真相

### 2.1 五类载体

| 载体 | 位置 | 数量 | 内部结构 |
|---|---|---:|---|
| `*.skill` | `Manus/skill01/` | 335 | ZIP。**330 个** `SKILL.md` 在包**根目录**，**5 个**在 `<name>/SKILL.md`；附 `references/`、`templates/`、`scripts/`、`evals/`、`examples/` |
| `*.zip` | `Manus/skill02/` | 335 | 同 skill01（内容逐字节相同） |
| `*.zip` | `MinMaxDesign/` | 107 | ZIP。**107/107** 都在 `<name>/SKILL.md`，且**每包必有** `<name>/meta.yaml` 与 `<name>/references/*`——**结构最规范** |
| 普通目录 | `kimi/skills/` | 170 | `<name>/SKILL.md` + 可选 `LICENSE`、`references/`、`scripts/` |
| 普通目录 | `MinMax/skills/` | 17 | `<name>/SKILL.md` + 1 个 `LICENSE` |

**共同点**：`SKILL.md` + YAML frontmatter 是全库唯一稳定的约定；`.skill` 与 `.zip` 只是扩展名不同，**同为 ZIP**。

### 2.2 内部文件规模

| 目录 | 压缩包 | 内部文件总数 | 平均/包 | 仅含单文件的包 |
|---|---:|---:|---:|---:|
| `Manus/skill01` | 335 | **2693** | 8.0 | 131 |
| `Manus/skill02` | 335 | **2610** | 7.8 | 132 |
| `MinMaxDesign` | 107 | **727** | 6.8 | 0 |

合计 **6030 个内部文件**，其中 `references/` 下 4409 个、`templates/` 下 215 个、脚本 625 个。

> ⚠️ **不要只看 SKILL.md**。`brand-docx` 一个包内就有 11 个文件（含 `reference/idoc.schema.json`、`reference/visual-audit.md`）；`ecommerce-image` 有 20 个（含 14 个品类专章和 `platform-specs.md`）。

### 2.3 读取陷阱（重要，会静默出错）

**实测**：`Manus/skill02/` 全部 335 个 + `MinMaxDesign/` 全部 107 个 = **442/777 个压缩包**，用不同方式读同一文件会得到不同结果：

```bash
$ f=MinMaxDesign/brand-ad.zip

$ head -c 4 "$f" | xxd -p
504b0304                       # ✅ 正确的 ZIP magic

$ od -An -tx1 -N4 "$f" | tr -d ' \n'
887d1c8d                       # ❌ 乱码

$ node -e "console.log(require('fs').readFileSync('$f').slice(0,4).toString('hex'))"
887d1c8d                       # ❌ 乱码

$ unzip -Z1 "$f"
End-of-central-directory signature not found.   # ❌ 读不了中央目录

$ md5 -q "$f"; cp "$f" /tmp/t.zip; md5 -q /tmp/t.zip
afed2520cc246146c1fb78d45bfcc232
e77b817581eb628164206995cdd22bbe   # ❌ 原文件 md5 与副本不等
```

**结论与处置**：

- 这 **442 个文件必须先 `cp` 到临时目录，对副本操作**；`cp` 之后一切正常（`unzip`、`readFileSync`、`md5` 全部正确）。
- 受影响的恰好是 `Manus/skill02/`（335）+ `MinMaxDesign/`（107）两组；`Manus/skill01/`（335）+ `kimi` + `MinMax` 可直接读。
- **危险点**：`fs.readFileSync` 会**成功返回 192 字节左右的乱码而不报错**，自写 ZIP 解析器（读 `csize`/`nlen`）会静默解析出 0 条目。任何"扫一遍库"的脚本若不做 PK magic 校验，会把这两组当成空技能跳过。
- 本报告与 `index.json` 的所有内容**均取自 `/tmp` 工作副本**，已规避该问题。

### 2.4 流式 ZIP 的次级陷阱

部分 Manus `.skill` 是流式 zip —— **本地文件头 `csize=0`**，真实长度只写在中央目录。自写解析器若只扫本地头（`PK\x03\x04`）会因 `csize=0` 提前终止。可靠做法是用 `unzip`（读中央目录）或完整实现 EOCD → 中央目录 → 本地头三段解析。

---

## 3. 去重账

用 SHA-256 对全部 964 条 `SKILL.md` 正文做内容指纹：

| 指标 | 数值 |
|---|---:|
| 原始条目 | 964 |
| 唯一内容 | **629** |
| 冗余副本 | **335** |
| 重复组 | 330（325 组 ×2 副本 + 5 组 ×3 副本） |
| 重复是否跨来源 | **否**——335 条冗余**全部**在 `Manus` 内部 |

两组重复的成因不同：

1. **同名同内容（325 组）**：`skill01/X` 与 `skill02/X` 逐字节相同。329 个技能名在两目录都存在，且**全部文本一致**。
2. **`(1)` 后缀（5 组）**：`comparison-article-writer (1)`、`keyword-research (1)`、`manim-animator (1)`、`seo-audit (1)`、`video-generator (1)`——MAC 风格的重名下载副产物，与主文件逐字节相同。另有 `game-dev` 只在 skill01、`game-dev (1)` 只在 skill02，内容同样一致。

**跨来源同名 ≠ 重复**：`content-strategy` 在 `Manus` 与 `MinMaxDesign` 都有，但是两个不同技能（18533 vs 15471 字符）；`skill-creator` 在 `Manus`、`MinMaxDesign`、`kimi` 三处都有，是**三个不同实现**。

**处置建议**：索引与后续处理**以 `Manus/skill01/` 为 Manus 侧唯一真源**，`skill02` 可整体视为镜像。`index.json` 中每条都带 `duplicate_group_size` 与 `exact_duplicate_of` 字段，可据此过滤。

---

## 4. 元数据与权属

### 4.1 frontmatter 覆盖率

**964/964 全部带 frontmatter**，且**全部含 `name` + `description`**——这一点比预期好，可直接用于自动路由。

字段丰富度差异极大：

| 字段 | 出现次数 | 主要来源 |
|---|---:|---|
| `name` / `description` | 964 / 964 | 全库 |
| `license` | 266 | Manus、kimi、MinMax |
| `metadata` | 213 | Manus |
| `exported-by` | 107 | **MinMaxDesign 独有**（值恒为 `MiniMax-hub`） |
| `trigger-words` | 83 | MinMaxDesign 为主 |
| `allowed-tools` | 81 | kimi |
| `version` | 73 | Manus |
| `compatibility` | 53 | Manus |
| `slug` / `acceptLicenseTerms` | 44 / 44 | Manus（`acceptLicenseTerms: true` 是安装期同意标记，非许可证） |
| `category` / `user-invocable` | 26 / 26 | kimi |
| `languages` | 22 | kimi |
| `trigger-words`（中文 `触发词` 系） | 5 | kimi |

**结论**：`name` + `description` 是全库唯一可依赖的路由字段；**`trigger-words` 只有 MinMaxDesign 系统提供**，这正是最需要触发精度的一批（视频生成/拆解类）。

### 4.2 许可证状态

| 来源 | 已声明 | 未声明 | 声明率 |
|---|---:|---:|---:|
| `Manus` | 174 | 496 | 26.0% |
| `kimi` | 92 | 78 | 54.1% |
| `MinMax` | 16 | 1 | 94.1% |
| **`MinMaxDesign`** | **0** | **107** | **0%** |
| **合计** | **282** | **682** | **29.3%** |

归一后的许可证种类：

| 许可证 | 条数 |
|---|---:|
| MIT | 222 |
| Apache-2.0 | 36 |
| BSD-3-Clause | 10 |
| 指向 `LICENSE.txt`（未给全文） | 8 |
| 指向上游 GitHub LICENSE URL | 6 |
| **未声明** | **682** |

**风险分级**：

- 🟢 **可直接用**：`kimi` 的 3 个 MIT 技能（`compliance-review-planner`、`tos-risk-checker`、`weighted-scoring`）、`blog-factcheck`（MIT）、`markdown-mermaid-writing`（Apache-2.0）、`MinMax` 的 16 个。
- 🟡 **可用但需留意**：`Manus` 174 个声明了 license 的（多为 MIT），但只有 11 个包内**真的带 LICENSE 文件**，其余仅 frontmatter 一行声明。
- 🔴 **需确权**：`MinMaxDesign` **107 个全部未声明**；`Manus` 496 个未声明。它们恰是本次盘点中最有价值的一批（`brand-ad`、`video-deconstruct*`、`ecommerce-image`、`koc-video`、`social-caption`）。

> 「未声明」≠「无版权」，也 ≠「可自由使用」。在对外交付、商用或二次分发前需单独确权；`refs/` 中的留档仅供内部只读参考。

### 4.3 「正负样例库」现状

- **11 个唯一技能自带 `evals/evals.json`**（全在 Manus 侧）：`ai-seo`、`churn-prevention`、`cold-email`、`content-strategy`、`copy-editing`、`copywriting`、`marketing-ideas`、`marketing-psychology`、`programmatic-seo`、`revops`、`sales-enablement`。
- **格式**（以 `copy-editing` 为例）：

```json
{ "skill_name": "copy-editing",
  "evals": [ { "id": 1,
    "prompt": "Edit this homepage copy for us: 'Welcome to CloudSync! ...'",
    "expected_output": "Should check for product-marketing.md first. Should apply the Seven Sweeps Framework systematically. ...",
    "assertions": ["Checks for product-ma..."] } ] }
```

- **只有 1 个技能带 JSON Schema**：`brand-docx`（`reference/idoc.schema.json`、`reference/profile-schema.md`）。

**这是全库最接近"可评测资产"的形态**，但覆盖极窄（11/629 = 1.7%），且全部是**文案类**，没有一条覆盖视频/图片模态。

---

## 5. TOP 30 复用建议

**改造量标尺**：`小` = 换品牌口径/阈值即可用（≤0.5 天）；`中` = 需重写规则表、维度权重或输出 schema（1–2 天）；`大` = 需重接数据源或重构流程（≥3 天）。

| # | 技能 | 来源 | 许可 | 管线位置 | 复用什么 | 改造量 |
|---:|---|---|---|---|---|---|
| 1 | `seo-content-audit` | Manus | 未声明 | **审计**·判定内核 | E-E-A-T + CITE 多维评分；**veto 项与总分脱钩**；`publish / publish-with-fixes / no-publish` 三档裁决；`templates/verdict.md` 现成模板 | **小** |
| 2 | `weighted-scoring` | kimi | MIT | **审计**·配权与稳健性 | 三种配权法（直接/排序 ROC/两两对比）；**强制敏感性分析**（权重波动/评分波动/**逆转点**）；认知偏差检查清单 | **小** |
| 3 | `agentic-eval` | Manus | 未声明 | **审计**·评估循环 | Basic Reflection / **Evaluator-Optimizer** / Code Reflection 三模式；Outcome-based vs **LLM-as-Judge** vs Rubric-based 三策略 | **小** |
| 4 | `compliance-review-planner` | kimi | MIT | **审计**·合规规则库 | 「检查项 + 法规依据 + 风险等级 + 整改建议」四段式清单；**营销推送与广告专章**；风险等级判定标准 | **中**（法规清单需换成 US/母婴） |
| 5 | `tos-risk-checker` | kimi | MIT | **审计**·风险分类与分级输出 | R1–R7 风险分类法；🔴🟠🟡 三级报告结构；**通俗化解读原则**（把法条翻成人话） | **小** |
| 6 | `legal-risk-assessment` | Manus | 未声明 | **审计**·风险矩阵 | 严重性×可能性 → 评分 1–25 → GREEN/YELLOW/ORANGE/RED 四级阈值；10 段式风险备忘录；升级判据 | **小** |
| 7 | `blog-factcheck` | Manus | **MIT** | **审计**·宣称核验 | 抽取承重性宣称 → 校验引用 URL → 抓页面核对 → **匹配置信度打分（exact 1.0 / paraphrase 0.7–0.9 / not found 0.0）**；未引用标记 UNVERIFIED | **中**（需可访问的一手源） |
| 8 | `iflytek-text-proofread` | Manus | 未声明 | **审计**·中文硬错误层 | 中文 **27 类**错误校对（错别字/标点/语序/事实/敏感内容）；纯 stdlib | **中**（依赖讯飞 API Key，或换本地模型） |
| 9 | `audit-support` | Manus | 未声明 | **审计**·方法论 | **设计有效性 vs 运行有效性**；四种抽样法 + 样本量指引；底稿证据标准；缺陷三级分类（Deficiency / Significant / Material）与聚合规则 | **中** |
| 10 | `final-release-review` | Manus | 未声明 | **审计**·确定性闸门 | diff 映射 → 契约审计 → 证据化发现 → **ship/block** + Unblock checklist；"发布前放行"结构可直接照搬 | **中** |
| 11 | `dataset-health-audit` | kimi | MIT | **审计**·结果落盘模板 | 12 维审计 + 质量评分 + 问题详情 + 修复建议的 **JSON 输出骨架** | **小** |
| 12 | `applying-brand-guidelines` | Manus | 未声明 | **审计**·品牌规范 | 色板/字体/Logo/语调/标准用语/禁止元素 + `apply_brand.py` / `validate_brand.py` 校验脚本 | **大**（内容为 "Acme Corporation" 占位样例，须整体换血） |
| 13 | `social-caption` | MinMaxDesign | 未声明 | **审计**·平台规格前置 | FB/IG/TikTok/Pinterest/YouTube **五平台锁定规格表**；发布前 checklist；hashtag 规则；Pinterest 按搜索引擎处理 | **中**（需补 Amazon / TikTok Shop） |
| 14 | `brand-ad` | MinMaxDesign | 未声明 | **审计**·素材真实性与范围门 | 事实核验 → **官方广告 vs KOC 归属判定** → copy/CTA 交付契约 → 原生排版质量门 → Prompt 完整性锁；`references/adsqa-target-answers.md` 问答式合规层 | **中** |
| 15 | `koc-video` | MinMaxDesign | 未声明 | **审计**·KOC 披露边界 | review / testimonial / POV / hands-only 的**内容形态判定**与"非官方品牌片"分流；`hook-decision.md` 钩子判定 | **中** |
| 16 | `muapi-social-media-video` | Manus | 未声明 | **审计**·品牌档案消费 | 消费 `brand-identity.md` / `ICP.md` / `messaging.md` 三件套的范式——**"品牌档案 → 内容"的接线样例** | **中** |
| 17 | `brand-docx` | Manus | 未声明 | **知识库**·品牌档案引擎 | 七动词（EXTRACT / COMPREHEND / VERIFY / GENERATE …）+ 两阶段视觉审计；`profile-schema.md` 与 `idoc.schema.json` 是**全库唯一的品牌档案 schema** | **大**（引擎重，需 .docx 模板） |
| 18 | `video-deconstruct` | MinMaxDesign | 未声明 | **拆解** | 镜头 / 运动 / 声音 / 连贯性**四轨取证** → 复刻契约 → 执行计划；明确排除"评论与普通剪辑" | **小** |
| 19 | `video-deconstruct-analyzer` | MinMaxDesign | 未声明 | **拆解** | 六步法（读元数据 → 密集关键帧+画布证据链 → 对齐方向 → 报告 → 最小条数分镜 → 终检）；`references/report-template.md` **现成报告模板** | **小** |
| 20 | `video-transcript` | MinMaxDesign | 未声明 | **拆解** | ffmpeg 抽音归一 → 内置 ASR → Whisper 兜底；输出章节 + 摘要 + **可复用金句**；**五类失败处理分支** | **中**（ASR 引擎绑定 MiniMax 内置） |
| 21 | `subtitle-correction` | MinMaxDesign | 未声明 | **拆解** | **严格保留时间轴与编号**的 SRT 纠错；先问领域术语；四类错误模式（同音字/术语/中英混排/代码标识符）；`scripts/subtitle_tool.py` 校验 + HTML diff | **小** |
| 22 | `youtube-transcript` | Manus | 未声明 | **拆解** | 外部素材入口（YouTube 逐字稿抓取） | **小** |
| 23 | `video-to-subtitle-summary` | Manus | 未声明 | **拆解** | 短视频 URL / 本地文件 → 字幕 + 摘要一体；抖音/TikTok 类素材的落地路径 | **中** |
| 24 | `ecommerce-image` | MinMaxDesign | 未声明 | **拆解 + 审计** | **14 个行业纵含 mother & baby**（`references/categories/05-baby.md`）；Amazon/Shopify/TikTok Shop/IG Shop/Pinterest 及淘宝天猫京东拼多多抖音小红书**商品图规范** | **中** |
| 25 | `sn-da-non-spreadsheet-analysis` | Manus | 未声明 | **拆解** | Word/PDF/PPT 全量提取 + 表格数值化 + **图表理解** + 跨文档汇总 | **中** |
| 26 | `copy-editing` | Manus | 未声明 | **优化 + 审计** | **Seven Sweeps 七遍扫描**（清晰/语调/So-what/举证/具体/情绪/零风险）+ **Expert Panel Scoring** 多角色评委打分 + `evals/evals.json` 样例集 | **小** |
| 27 | `ecom-copy-assistant` | kimi | MIT | **优化** | 电商详情页文案（标题/卖点/规格/FAQ）+ 淘宝京东亚马逊三平台风格规范；含广告宣称约束 | **中** |
| 28 | `smart-web-scraper` | kimi | 未声明 | **采集** | Playwright 抓取 + Cloudflare 绕过；输出标题/正文/截图 | **中** |
| 29 | `markdown-mermaid-writing` | Manus | Apache-2.0 | **报告** | Markdown + Mermaid 图表写作规范，审计结论的可视化落盘层 | **小** |
| 30 | `content-strategy` | Manus | 未声明 | **分析** | 内容策略规划（决定做什么内容）；与 `copy-editing` 同源，共享 `evals/` 体系 | **中** |

> 另有 **2 个可视化作法值得额外留意**：`risk-heatmap`（kimi，MIT）把风险条目直接渲染成可交互 HTML 风险热力图；`aso-audit`（Manus）给出 **10 维加权记分卡**（权重 20/15/15/15/15/10/5/5/5/5）+ Quick Wins / High-Impact / Strategic 三档整改节奏。

---

## 6. 按管线阶段的装配建议

```
素材输入 ──► 拆解 ──► 分析 ──► 审计 ──► 优化 ──► 报告
               │        │        │        │        │
               └────────┴────────┴────────┴────────┘
                         品牌知识库（贯穿）
```

| 阶段 | 首选复用 | 备选 | 关键缺口 |
|---|---|---|---|
| **拆解** | `video-deconstruct`、`video-deconstruct-analyzer`、`video-transcript`、`subtitle-correction` | `youtube-transcript`、`video-to-subtitle-summary`、`sn-da-non-spreadsheet-analysis`、`vision-analysis`（MinMax） | 图片素材需接多模态模型；**无 OCR/版面还原专章** |
| **分析** | `content-strategy` | `competitive-seo-intel`、`split-test-evaluator`、`market-research-reports` | 无受众画像/人群模型 |
| **审计** | `seo-content-audit`（骨架） + `weighted-scoring`（配权） + `agentic-eval`（循环） | `compliance-review-planner`、`tos-risk-checker`、`legal-risk-assessment`、`blog-factcheck`、`iflytek-text-proofread`、`audit-support`、`final-release-review` | **见 §7，缺口最严重的一层** |
| **优化** | `copy-editing`（Seven Sweeps）、`ecom-copy-assistant` | `copy-editor`（kimi 中文版）、`humanizer-zh`、`grammar-check` | 无母婴品类改写模板 |
| **知识库** | `brand-docx`（品牌档案引擎） | `applying-brand-guidelines`（规范模板）、`ui-blueprint`（设计系统逆向）、`ddd-glossary-gen`（术语表 → **品牌用语表**） | 无品牌知识库的**检索层**（RAG 类技能均为通用基础设施） |
| **报告** | `markdown-mermaid-writing`、`risk-heatmap` | `dataset-health-audit`（JSON 骨架）、`seo-audit`（报告骨架） | 无固定格式的审计报告模板 |
| **采集** | `smart-web-scraper` | `scrapling`、`website-traffic-checker` | 无平台官方 API 接入（TikTok/Meta 等） |

### 6.1 建议的装配路径（三步）

1. **先立骨架**：以 `seo-content-audit` 为审计内核（保留 veto / 三档裁决 / 报告模板），以 `weighted-scoring` 补配权与敏感性分析，以 `agentic-eval` 补自评-优化循环。三者组合后**审计骨架即成型**，且改动量都在「小」档。
2. **再接多模态**：`video-deconstruct-analyzer`（视频）+ `video-transcript` / `subtitle-correction`（音频文本）+ `vision-analysis` / `ecommerce-image`（图片）三路并行接入拆解层。
3. **最后补规则库**：品牌口径取 `applying-brand-guidelines` 的模板结构 + `brand-docx` 的 schema；平台口径取 `social-caption` 的规格表 + `ecommerce-image` 的 `platform-specs.md`。

---

## 7. 缺口清单（对 629 个唯一技能全量检索）

以下为审计 Agent 的**必需能力**，在本地库中**实测 0 命中或仅有误命中**：

| 缺口 | 命中数 | 说明 |
|---|---:|---|
| **CPSC / CPSIA**（美国消费品安全，母婴强制） | **0** | 母婴品类的强制法规底座，全库无一字 |
| **NAD**（National Advertising Division） | **0** | 美国广告诉讼替代机制 |
| **TikTok 平台政策** | **0** | 仅有字符数/格式规格（`social-caption`），无政策判定规则 |
| **Meta 广告标准 / 社区准则** | **0** | 同上 |
| **YouTube 广告政策 / 社区准则** | **0** | 同上 |
| **Amazon Listing / 广告政策** | **0** | `ecommerce-image` 有图片规格，无政策判定 |
| **UGC 披露**（`#ad` / `#sponsored` / paid partnership / material connection） | **0** | 达人合作合规的判定入口完全缺失 |
| **FTC** | 2（均误命中） | `churn-prevention` 与 `tos-risk-checker` 各顺带提及一次；**无任何技能以 FTC 为职责** |
| **健康 / 医疗宣称**（structure-function claim、FDA） | 2（均误命中） | `database-lookup`、`ecommerce-image` 顺带提及 |
| **母婴品类语汇** | 12（约 7 条真实） | 真正把母婴当**行业维度**处理的只有 3 个：`ecommerce-image`（`categories/05-baby.md`）、`ecommerce-design`、`ecom-copy-assistant`；其余为示例文本顺带出现 |
| **平台官方 API 接入** | — | 采集层全靠爬虫 |
| **品牌知识库检索层** | — | RAG 类技能均为通用基础设施，无品牌语料适配 |
| **正负样例库** | 11/629（1.7%） | 仅 Manus 文案类自带 `evals/`；**视频/图片模态 0 覆盖** |

**结论**：**合规规则库必须自建**。本地库能提供的是**判定骨架、评分机制、报告结构、风险分级法**——即"怎么审"；但"按什么规则审"（法规条文、平台政策、品类宣称红线）**几乎全部空白**。

---

## 8. 低价值排除清单

以下类别**建议整类排除**，不必纳入后续评估：

| 类别 | 规模 | 代表 | 排除理由 |
|---|---:|---|---|
| 开发工具链 | 大 | `gitlab-cli-guide`（38 个子技能）、`k8s-cluster-ops`、`database-inspector`、`api-doc-gen` | 与内容审计无任何交集 |
| 代码审计 | 中 | `code-reviewer`、`code-safety-audit`、`web-security-audit`、`git-repo-audit`、`refactor` | "审计"同名但对象是代码 |
| 金融投研 | 中 | `equity-research-report-cn`、`value-invest-scorer`、`cashflow-valuation`、`fund-risk-analyzer`、`equity-earnings-review` | 领域无关；**版式可借，内容不可用** |
| 游戏 / 3D / 音乐生成 | 中 | `game-dev`、`blender-workflow`、`acestep`、`manim-animator`、`motion-graphics` | 生成型，不进审计管线 |
| AI 视频生成 | **大（MinMaxDesign 主体）** | `anime-pv-maker`、`short-drama-*`（4 个）、`pov-short-film-generator`、`surreal-spot`、`typography-product-tvc` 等 | MinMaxDesign 107 个中 **68 个**落在「无关」阶段，绝大多数是**创意生成**类，产出物而非判定物 |
| 生信 / 医疗 | 小 | `single-cell-rna-qc` | 领域无关 |
| 旅行 / 招聘 / 面试 | 小 | `interview-simulator`、`resume`、`cover-letter-generator`、travel 类 | 领域无关 |
| 产品需求文档 | 小 | `create-prd`、`prd`、`product-launch-planner` | 与内容审计无交集 |

> **注意**：`MinMaxDesign` 不能整目录排除——107 个中有 **8 个 high / 20 个 medium / 58 个 low / 21 个 none**，`brand-ad`、`video-deconstruct*`、`social-caption`、`ecommerce-image`、`koc-video` 都在其中，是本次盘点最重要的增量。**需逐个判别，不可按目录一刀切。**

---

## 9. `index.json` 字段说明

964 条，每条含：

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 仓内相对路径，如 `skills/Manus/skill01/seo-content-audit.skill`、`skills/kimi/skills/<name>/SKILL.md` |
| `name` | string | frontmatter `name`（964/964 均有） |
| `description` | string | frontmatter `description`，**截断至 200 字** |
| `source` | string | `manus` / `kimi` / `minmax` / `minmaxdesign` |
| `license` | string \| null | frontmatter 或 LICENSE 文件的**原始声明值**；未声明为 `null` |
| `license_normalized` | string \| null | 归一后：`MIT` / `Apache-2.0` / `BSD-3-Clause` / `SEE-LICENSE-FILE` / `SEE-UPSTREAM-URL` / `null` |
| `license_path` | string \| null | 许可证文件位置；包内文件用 `<archive>!<inner>` 表示 |
| `has_frontmatter` | boolean | 964/964 均为 `true` |
| `frontmatter_keys` | string[] | 该条 frontmatter 的全部键名（保留原始顺序） |
| `relevance` | string | `high` / `medium` / `low` / `none`——按本项目判断 |
| `pipeline_stage` | string | `拆解` / `分析` / `审计` / `优化` / `知识库` / `报告` / `采集` / `无关` |
| `body_chars` | number | 去掉 frontmatter 后的正文长度（字符） |
| `content_sha256_16` | string | 正文指纹前 16 位，用于去重 |
| `duplicate_group_size` | number | 同内容条目数（1 = 无重复） |
| `exact_duplicate_of` | string \| null | 若为重复副本，指向**保留的那一份**的 `path` |
| `curated` | boolean | `true` = 人工逐条判定过（共 262 条命中人工表）；`false` = 规则判定 |
| `note` | string | 判定理由或复用要点 |

**排序**：`source` → `relevance`（high→none）→ `name`。

**典型用法**：

```bash
# 取所有高相关的审计类技能
jq -r '.[] | select(.relevance=="high" and .pipeline_stage=="审计") | "\(.source)\t\(.name)"' index.json

# 取去重后的全部技能（排除镜像副本）
jq -r '.[] | select(.exact_duplicate_of==null) | .path' index.json | wc -l   # → 629
```

---

## 10. 附：方法与可复现命令

### 10.1 关键处置（务必遵守）

```bash
# ① Manus/skill02 与 MinMaxDesign 共 442 个压缩包：必须先复制
cp skills/Manus/skill02/<name>.zip /tmp/w/     # 直接 readFileSync / od / md5 会得到乱码
cp skills/MinMaxDesign/<name>.zip  /tmp/w/

# ② 解包（用 unzip 读中央目录，不要自写本地头解析器）
unzip -Z1 /tmp/w/<name>.zip                    # 列条目（含真实相对路径）
unzip -p  /tmp/w/<name>.zip SKILL.md           # 取正文

# ③ 校验：确认取到的是 ZIP 而非乱码
head -c 4 /tmp/w/<name>.zip | xxd -p           # 应为 504b0304
```

### 10.2 复现统计

```bash
# 规模
ls skills/Manus/skill01/*.skill | wc -l        # 335
ls skills/Manus/skill02/*.zip   | wc -l        # 335
ls skills/MinMaxDesign/*.zip    | wc -l        # 107
find skills/kimi/skills -name SKILL.md | wc -l # 170
find skills/MinMax/skills -name SKILL.md | wc -l  # 17

# 内容去重（629）
jq -r '.[] | select(.exact_duplicate_of==null) | .path' skills-inventory/index.json | wc -l
```

### 10.3 产出清单

| 路径 | 内容 |
|---|---|
| `skills-inventory/SKILLS-INVENTORY.md` | 本报告 |
| `skills-inventory/index.json` | 964 条结构化索引（约 800 KB） |
| `skills-inventory/refs/README.md` | 留档技能的来源与许可状态表 |
| `skills-inventory/refs/<skill>/` | 18 个关键技能原文，共 88 个文件 |

### 10.4 未做的事

- **未修改 `skills/` 目录本身**——全部解压与索引产物落在 `/tmp`。
- **未做完整的语义相关性标注**——`curated: false` 的 702 条为规则判定，存在误判；高价值项（262 条）已逐条人工复核。
- **未验证许可证的对外可用性**——「未声明」仅表示库内无声明，不等于可自由使用。
