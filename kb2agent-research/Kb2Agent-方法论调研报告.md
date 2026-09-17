# Kb2Agent（MKD · Knowledge to Agent）方法论调研报告

## 0. 元数据（GitHub API 实测）

| 字段 | 值 |
|---|---|
| 仓库 | https://github.com/zjgulai/Kb2Agent |
| description | **从知识到agent** |
| language | JavaScript（实为 Node.js ESM，无 TS 工具链） |
| stars / watchers / forks | **2 / 2 / 0**（冷门仓库） |
| open_issues | 0 |
| created_at | 2026-07-25T04:42:49Z |
| pushed_at | 2026-08-18T03:21:14Z |
| default_branch | main |
| topics | `[]`（空） |
| license | **null（无许可证）** |
| homepage | null；有 GitHub Pages（`has_pages: true`，`base: '/Kb2Agent/'`） |
| size | 7510 KB |
| npm name/version | `mkd-guide` 1.0.0，`engines.node >= 22.19.0` |

**关键观察：仓库根目录没有 README.md**（`/main/README.md` 返回 404，`/master/README.md` 同）。"README" 实质是 VitePress 首页 `docs/index.md`（仅 172 字节，挂载 `<MkdProductHome />` 组件）。全部实质内容在 `docs/knowledge/`（23 个方法论章节）、`docs/architecture/`（设计/ADR/审计）、`reference/`（可运行运行时与 Schema）、`knowledge-system/`（知识对象注册表与验收契约）。

**⚠️ 重要陷阱（后续使用者必读）**：`package.json` 的 `docs:qa` 脚本引用了大量**在仓库里不存在的文件**——例如 `scripts/build-m1c-release.mjs`、`scripts/build-mkd-distill-package.mjs`、`scripts/run-g6-a9-public-p9.mjs`、`playwright.g6-a9-public.config.mjs`、`scripts/preview-local.mjs`、`tests/content/m1c-*.test.mjs` 等。也就是说 **`npm run docs:qa` 在当前 main 分支上不可能跑通**。可跑的只有引用真实存在文件的子集（`reference:build`、`reference:test`、`reference:contracts`、`agent:build`、`agent:test`、`docs:metrics` 等）。许多 g4/g5/g6-a5..a11/g7 文档与脚本是历史阶段产物，已从仓库中移除但 package.json 未同步。

---

## 1. 仓库定位与一句话描述

> **官网原文**：`title: 'MKD · Knowledge to Agent'`
> `description: '把多格式资料编译成可审查、可复放、可追溯的智能体行动包'`

> **产品合同（`docs/architecture/m1-a-product-contract.md`）的一句话价值**：
> 「把多格式资料编译为有来源、有关系、有边界、可评测的知识对象，再由 E2 受控 Agent 生成可审查、可批准、可复放的决策行动包。」

**一句话**：Kb2Agent 不是"知识库工具"，也不是"Agent 框架"，而是一套 **Knowledge → Agent 的编译方法论 + 可运行 Reference Lab**——它把 PDF/视频/音频/网页/代码/专家经验等多模态资料，经"蒸馏 → 治理 → 编译"变成一种受权限约束、只读、零副作用的**决策行动包（ActionPackage）**，并为每一步留下可复放的密码学回执。

仓库由**两条产品线**组成（ADR-001 强制分账，成熟度不可互相继承）：

| 产品线 | 用户任务 | 权威资产 | 当前最大声明 |
|---|---|---|---|
| **Guide** | 学会判断知识系统的设计、风险和验证方法 | 文档、概念、Claim、来源、学习路径 | 具备本地知识治理基础 |
| **Reference Lab** | 运行并审查"资料→行动包"的固定闭环 | Schema、fixture、compiler、task、trace、eval、receipt | M1-A Schema 与本地原型候选 |

---

## 2. 完整方法论

### 2.0 到底"转"的是什么：DIKW → LoD 蒸馏阶梯

方法论的第一性原理来自 **DIKW 四层递进**（`01-framework.md`）：

```txt
数据 (Data)：尚未被赋予问题语境的原始观察
  例：一本 300 页 PDF 的字符、页码、图像与版面坐标

信息 (Information)：经过语境化、可被描述和定位的数据
  例：一本 300 页的《精益创业》PDF → 包含 80,000 字，约 1,500 个句子

知识 (Knowledge)：经过结构化处理、可被检索和引用的信息
  例：《精益创业》中关于"MVP 验证"的 12 条可执行原则
      → 从 80,000 字中提炼，信噪比提升 100 倍

智慧 (Wisdom)：可指导 Agent 行动的可执行判断框架
  例：一个 SKILL.md
      触发条件："当用户问我的产品/功能该不该做时"
      执行步骤：先问这三个验证问题...
      禁忌：不要在未验证假设前就开始开发
      → Agent 收到问题时直接调用，无需二次推理
```

> **核心误区（原文）**：「直接把原始 PDF 放进向量库，是把"信息"当成了"智慧"——中间缺失了两个等级的转化。这就是为什么简单的 RAG 系统经常给出"感觉对但执行不了"的答案。」

**三种存储方式的本质差异（原文表）**：

| 做法 | 你存的是什么 | Agent 每次调用代价 | 答案质量 |
|---|---|---|---|
| **Raw RAG**（原文切块） | 信息碎片 | 每次重新推理理解 | 不稳定，易幻觉 |
| **知识库蒸馏**（结构化提炼） | 知识命题 | 理解成本低，检索精准 | 稳定，可追溯 |
| **Skill 蒸馏**（可执行契约） | 行动指令 | 零推理，直接执行 | 最高，有边界 |

> **选层原则（原文）**：「对知识的加工越彻底，Agent 运行时的推理成本越低，答案质量越高——但蒸馏的前期投入越大。正确的架构是**分层**：高频使用的知识做 Skill 蒸馏，低频全量的知识做知识库蒸馏，归档型内容做 Raw 存储。」

**五级蒸馏阶梯（LoD, Level of Distillation）**：

| 层级 | 形态 | 核心操作 | 典型工具 | Agent 效果 |
|---|---|---|---|---|
| **L0 平铺** | 文本 Chunks | 滑动窗口切片 + 向量化 | LangChain | 单跳 60%，多跳 <10% |
| **L1 实体增强** | 富化 Chunks | LLM 抽实体附着在 Chunk 尾 | UnWeaver | 零图谱成本，超早期 GraphRAG |
| **L2 层级导航** | 目录树 | 分层聚类 → INDEX.md | Corpus2Skill | F1 超 Dense 检索 27% |
| **L3 知识图谱** | 实体关系网络 | 提取三元组 → 图谱 + 社区摘要 | LightRAG | 全局主题综合霸主 |
| **L4 可执行契约** | SKILL.md | 方法论提炼为触发→执行→边界 | cangjie-skill | qsv 成功率 98.85% |

**框架映射总表（原文）**——这是全书统一坐标系：

| DIKW 层 | L0-L4 蒸馏层 | 存储形态 | 建设工具 | 检索方式 | 最适合的场景 |
|---|---|---|---|---|---|
| Data（数据） | L0 平铺 | 文本 Chunks | LangChain / LlamaIndex | 向量相似度 | 快速 PoC，低预算 |
| Information（信息） | L1 实体增强 | 富化 Chunks + 实体标注 | UnWeaver | 向量 + 元数据过滤 | 低成本超越早期 GraphRAG |
| Knowledge（知识） | L2 层级导航 | INDEX.md 目录树 | Corpus2Skill | 导航 + 精确检索 | 单域文档，Agent 主动导航 |
| Knowledge Network | L3 知识图谱 | 实体关系网络 | LightRAG / GraphRAG | 图遍历 + 社区摘要 | 跨文档推理，全局主题综合 |
| Wisdom（智慧） | L4 可执行契约 | SKILL.md | cangjie-skill / R2S | 直接执行，无检索 | 高频决策流程，零推理 |

**核心数据结构：四层金字塔**（L1–L2 的内部结构）

```
Level 1: Atomic Insights       最小粒度事实，SVO 格式
Level 2: Concepts              多个原子事实聚合为主题群
Level 3: Document Abstracts    单文档的目的/范围/主题概览
Level 4: Cross-Doc Recollections 多文档涌现的模式、对比、矛盾
```
> 压缩比：「每页约 13 个 Atomic Insight → 1 个 Concept（13:1 压缩）」
> 检索路由：精确事实查询 → L1；探索性理解 → L2–L3；跨文档对比 → L4

**Karpathy LLM-Wiki 目录约定（原文，可直接照抄）**：

```text
knowledge-base/
├── raw/                    ← 只读原始资料，永不删除
│   ├── books/
│   ├── transcripts/
│   └── images/
│
└── wiki/                   ← LLM 持续更新的编译结果
    ├── index.md            # 总目录，每次 ingest 自动更新
    ├── log.md              # 时序操作日志（可审计）
    ├── entity_pages/       # 实体页：人物/组织/产品/工具
    ├── concept_pages/      # 概念页：技术术语/领域方法论
    └── summaries/          # 每个 source 的摘要页
```
> 「每次 Ingest 固定五步：解析 → 写摘要页 → 更新总目录 → 合并实体/概念页 → 追加日志。」

### 2.1 反蒸馏：哪些知识"不该"被结构化（四类禁区）

| 类型 | 说明 | 正确处理 |
|---|---|---|
| **情境依赖型知识** | 法律条款解释、临床推理、设计取舍背景 | 保留全文原始存储 + 语义索引，检索到后由 Agent 在上下文中推理 |
| **负向知识（知道什么不能做）** | 失败经验、踩坑记录、被否决方案 | 用 **ADR 格式原文保存**（背景→决策→被否决选项→后果），可建索引但不要摘要化 |
| **高度个人化的隐性知识** | 专家直觉、"手感" | 访谈录音 + 逐字稿原文；只生成"提问引导词"供人类查阅，不生成"决策函数" |
| **快速迭代的操作性知识** | CLI 参数、SDK 签名、三方平台条款 | 只存"指针"（URL + 访问时间戳 + 摘要），不存内容本体 |

> **蒸馏前的灵魂三问（原文）**：
> 1. 这条知识六个月后还准确吗？
> 2. 它离开完整语境后，还能被正确理解吗？
> 3. 有没有人会因为 Agent 拿它做决策而承担现实后果？
> 三个问题有任何一个答案是"不确定"，先不要蒸馏。

### 2.2 反模式：什么情况下"做比不做更糟"（5 条，含信号）

| # | 反模式 | 识别信号（原文） |
|---|---|---|
| 1 | 把规则系统做成 RAG | 「你发现自己在给 RAG 写大量带有 `if-else` 逻辑的 prompt，说明你在用 LLM 仿真规则引擎」 |
| 2 | 把实时运营数据入库 | 「你的知识库里有大量 `updated_at` 距今不到 48 小时的条目」 |
| 3 | 为了"感觉先进"而建库 | 「知识库查询量每天不足 50 次，但你在维护一套完整的索引管道」 |
| 4 | 让自进化系统无监督运行 | 「你的自进化 pipeline 上次触发人工干预是三周前」 |
| 5 | 知识库成为组织信息孤岛 | 「团队成员在查询知识库之前，会先发消息问同事"这个库里的内容还准吗？"」 |

**知识劣化的四个生产机制（原文）**：① 写作者与使用者的责任分离 → 对策：指定 **Knowledge Owner**；② 新鲜感偏见 → 对策：用"使用次数 × 正向反馈率 × 作者信誉"替代纯时间衰减权重；③ 沉默的低质量知识没有成本（"零查询=安全"是假安全）→ 对策：定期受控退化；④ 语言磨损（Linguistic Drift）→ 对策：维护"术语变更日志"。

> **核心洞察（原文）**：「知识库质量管理的本质，不是技术问题，而是**激励设计问题**：谁为正确性负责？谁为错误付代价？谁有动力维护旧内容？在回答这三个问题之前，任何技术层面的"质量保障"都是在治标。」

**十个反直觉洞察（速览）**：① RAG 不是万能药（规则稳定+错误成本高 → 用规则引擎/微调）；② 知识库越多≠检索越好（噪音稀释）；③ 实时数据不该入库；④ 结构化提取成本可能高于 Fine-tuning；⑤ 强推理模型正在降低预处理必要性；⑥ 自进化系统可能自我毁灭（幻觉复利）；⑦ Top-K 有系统性偏见（偏爱高频/热门/规范文档）；⑧ 内部经营数据绝不发公网 LLM API（P0 红线）；⑨ Embedding 不是越新越好；⑩ 长上下文是 RAG 的竞争对手（低频+短文档+单任务 → 优先试全文直读基线）。

### 2.3 五步决策路由（**顺序不可颠倒**）

> **原文**：「很多团队先选工具、再想用途，最后发现架构根本跑不通。正确顺序是：第一步看知识半衰期 → 决定要不要入库…第二步选产品形态 → 第三步分类输入类型 → 第四步选输出形式 → 第五步处理混合输入例外。跳过任何一步都会导致后续返工。尤其不能先选「用不用 GraphRAG」——那是第四步的结果，不是起点。」

| 步骤 | 核心问题 | 跳过后果 |
|---|---|---|
| **Step 1 半衰期** | 3 个月后还有用吗？更新频率？ | 实时数据入向量库，Agent 拿过期事实作答 |
| **Step 2 产品形态** | 谁用？怎么接入？ | 架构与用户期望不匹配，做完才推倒重来 |
| **Step 3 输入类型** | 来自哪里？格式？ | 用错 SOP，丢失大量有效信息 |
| **Step 4 输出形式** | 知识以什么形式存储和调用？ | 蒸馏深度错误，要么白蒸馏要么用不了 |
| **Step 5 混合例外** | 是否跨多个类型？ | 强行归到单一场景，丢失跨模态信息 |

#### Step 1：知识半衰期表（原文）

| 半衰期 | 典型内容 | 推荐策略 | 错误做法 |
|---|---|---|---|
| **< 48小时** | 竞品价格、库存、广告投放数据 | 只存指针（URL+时间戳），实时 API 查询 | 入向量库，Agent 拿过期数据作答 |
| **1周 ~ 1个月** | 平台规则、竞品评论趋势、活动数据 | 缓存层（Redis/数据库），TTL 自动失效 | 做成 Skill，Skill 比数据更难更新 |
| **1个月 ~ 1年** | 行业报告、竞品分析、SOP 文档 | 完整入库，建更新提醒机制 | 不标注时间戳，让 Agent 永远相信它 |
| **> 1年** | 方法论、原理性知识、历史决策 | 深度蒸馏，L4 Skill，持久化 | 频繁重建，浪费资源 |

> **最低要求（原文）**：「每条入库的知识单元都必须带 `created_at` + `valid_until` 字段，没有 `valid_until` 的内容默认 90 天后触发人工复审。」

#### Step 2：五种产品形态

| 形态 | 描述 | 用户 | 技术接入 | 新鲜度要求 |
|---|---|---|---|---|
| A Chatbot | 对话式问答助手 | 终端用户 | WebSocket/HTTP | 日级更新 |
| B 自动化 Agent | 无人值守自动执行 | 系统/定时任务 | SDK/API | 小时级更新 |
| C Dashboard | 数据可视化看板 | 管理者 | REST API + 前端 | 日级更新 |
| D 嵌入式 API | 被其他系统调用 | 开发者 | REST/GraphQL | 按需更新 |
| **E MCP 工具** | **知识库作为通用 MCP Server** | **Claude/Cursor/Codex App** | **MCP 协议** | **实时同步** |

#### Step 3：输入类型 MECE 分类（10 种，含 J）

A 长文本（书籍/PDF/Word/论文）· B 视频（教程/演讲/B站）· C 音频（播客/会议录音/有声书）· D 网页/流媒体（博客/RSS/Twitter Thread）· E 代码仓库（GitHub Repo/API 文档）· F 人物/经验（专家访谈/同事知识/个人记录）· G 结构化数据（Excel/CSV/数据库）· H 图像/图表（架构图/白板/设计稿）· I 实时/动态（会议/直播/在线课程）· J 交互画布（BI 看板/SPA/WebGL）

#### Step 4：输出形式全谱（6 种，按粒度）

```text
细粒度                                                         粗粒度
  │                                                              │
  ▼                                                              ▼
Rules      原子笔记    Wiki 页面     Agent Skill    Fine-tune    知识图谱
JSONL      Markdown    Markdown      SKILL.md        JSONL        Neo4j
(bdistill) (Zettel.)   (LLM-Wiki)   (可执行)        (训练数据)   (关系库)
```

**决策矩阵（输入 × 输出最优匹配，原文）**：

| 输入类型 | 首选输出 | 备选输出 | 理由 |
|---|---|---|---|
| A 长文本 | Wiki 页面 + 四层金字塔 | Agent Skill（高频流程） | 文本密度高，适合完整建库 |
| B 视频 | Agent Skill | 原子笔记（知识类） | 时序操作→可执行流程最自然 |
| C 音频/播客 | Agent Skill（方法论类） | 人物 Skill（访谈类） | 对话提炼方法论 |
| D 网页文章 | 原子笔记（单篇）/ Wiki（聚合后） | 摘要卡片（资讯） | 碎片化，聚合后再提升 |
| E 代码仓库 | Agent Skill（使用模式） | 原子文档（API 参考） | 代码知识=使用方法 |
| F 人物/专家 | Agent Skill（人物 Skill） | Wiki 页面（传记） | 思维方式可执行化 |
| G 结构化数据 | Rules JSONL | 摘要卡片（带时效） | IF-THEN 规则最适合自动化 |
| H 图像/图表 | 原子笔记 + Mermaid | Agent Skill（架构/设计） | 先文字化，再结构化 |
| I 实时内容 | 行动项→任务系统 / 方法论→Skill | 决策记录（ADR 格式） | 双轨处理，不能混 |
| J 交互画布 | 扁平化表格 / API 原子笔记 | 状态机 Skill | 绕过视觉层抓取底层数据 |

#### Step 5：混合输入的三种分解策略

- **策略一：主体优先分解**——识别信息密度最高的主体类型走对应 SOP，其余作为附件（例：含截图 Markdown → 按 A 处理，截图送 VLM Caption 后作为 `附图说明` 字段）
- **策略二：并行流水线**——各成分地位等同则并行（例：讲解视频 → 音频轨 SenseVoice 转写 + 画面轨 VLM 提代码/架构图 → 合并为 `transcript` + `visual_notes` 双字段）
- **策略三：Triage 分诊**——输入复杂到无法预分类时，先用 LLM 做类型识别输出分解计划再路由

> **混合输入最小可行方案（原文）**：「遇到不确定的混合输入时，先回答这一个问题：**三个月后，会有人因为找不到这条信息而受损失吗？** 如果答案是否定的，直接归档原文，不要花时间拆解。」

### 2.4 十场景工程 SOP

每个场景严格遵循同一结构：**小白认知比喻 → 微观任务拆解 → GitHub 仓库选型表（分环境）→ 可运行 SOP → 天坑避免**。

**场景横向对比总表（原文）**：

| 场景 | 处理复杂度 | 需要 GPU | 首选工具 | 典型耗时（1000页/时） | 最常见失败点 |
|---|---|---|---|---|---|
| **A PDF/文档** | ⭐⭐⭐⭐ 高 | 推荐（可降级） | MinerU / Docling | 30-120 分钟 | 跨页表格撕裂、公式 OCR 失效 |
| **B 长视频** | ⭐⭐⭐ 中 | 否 | yt-dlp + SenseVoice | 视频时长 × 0.3 | 字幕语言切换、说话人混淆 |
| **C 播客/录音** | ⭐⭐ 中低 | 否 | SenseVoice / faster-whisper | 音频时长 × 0.1 | 背景噪音、多人重叠讲话 |
| **D 网页/RSS** | ⭐⭐ 低 | 否 | Firecrawl / Jina Reader | 实时 | 动态加载、反爬、内容更新快 |
| **E 代码仓库** | ⭐⭐⭐ 中 | 否 | Repomix / ast-grep | 15-60 分钟 | 依赖图提取缺失、注释与代码不一致 |
| **F 专家经验** | ⭐⭐⭐⭐⭐ 极高 | 否 | nuwa-skill / cangjie-skill | 无上限 | 隐性知识无法外显化 |
| **G 结构化数据** | ⭐ 低 | 否 | NL2SQL / pandas | 分钟级 | 把可计算字段入向量库 |
| **H 图像/图表** | ⭐⭐⭐ 中 | 推荐 | ColPali / GPT-4o VLM | 1-5 分钟/图 | 图中文字被忽略、Mermaid 转换失真 |
| **I 实时/直播** | ⭐⭐⭐⭐ 高 | 否 | 双轨：Action + Skill | 直播结束后 30-60 分钟 | 用流式内容代替结构化内容入库 |
| **J BI/SPA** | ⭐⭐⭐ 中 | 否 | Playwright CDP | 10-30 分钟/页 | DOM 状态无法截取、权限限制 |

**各场景要点摘录**：

- **A PDF**：核心比喻「PDF 不是文本文件，是"画在数字纸上的墨水"」；三个天坑=跨页表格撕裂 / 公式乱码 / 双栏阅读顺序灾难。书内图片分三类处理：纯图片文字→OCR、有语义图表→VLM Caption→Mermaid、纯装饰图→直接跳过。选型决策树：有 GPU 且跨页超长表格→`baidu/Unlimited-OCR`（32K 上下文一次吞入）；有 GPU 常规→`MinerU --effort high`；无 GPU 金融财报→`Docling`（TableFormer）。**约束**：不要用 Token 数切块，必须用 MinerU 的 JSON 结构（`type: table`）作为切块边界；Unlimited-OCR 单页 `ngram_window=128`，多页必须 `1024`（否则中间段重复性幻觉）。
- **B 视频**：核心比喻「视频是"时序状态机"，携带三路信号：口语文本（低密度）、时间序列操作（高价值）、视觉演示（高价值但不可检索）」。7 步 SOP，关键帧用 `ffmpeg -vf "select='gt(scene,0.3)'"` 场景变化检测（比固定间隔精准 3-5 倍）。天坑：字幕信噪比只有 30% 必须先清洗；cangjie 适合方法论、Resource2Skill 适合工程操作。
- **C 音频**：中文优先 `FunAudioLLM/SenseVoice`（带情绪标签 `<|NEUTRAL|>/<|HAPPY|>/<|ANGRY|>`，可用于权重标注，"感觉这句话对他有多重要"）。**天坑**：「飞书妙记生成的是摘要，不是知识：摘要丢失了大量细节，蒸馏前必须用原始转写，不是纪要」。
- **D 网页**：「单篇文章是矿渣，主题聚合才是矿脉」——Paul Graham 单篇 3 个 Insight，200 篇聚合起来就是完整决策系统。资讯类必须打 `expires` 标签定期清理。
- **E 代码仓库**：「代码不是知识，是知识的实现。」两条路线：理解架构→Ananta 主动探索；用库编程→`microsoft/Resource2Skill`。天坑：文档可能比代码旧 6-12 个月，必须用 Context7 MCP 补最新文档并在 Skill 里标注版本号。
- **F 专家经验**：「蒸馏人的核心不是语气，而是决策框架。**语气是噪音，决策框架才是信号。**」双轨提炼是铁律不可合并：能力轨（工作方法/心智模型/决策启发式→`work_skill.md`）+ 行为轨（沟通边界/表达风格→`persona_skill.md`）。
- **G 结构化数据**：「数字本身没有语义。`42000000` 是无意义的，但 `Q3 净利润 = 4200万，同比+23%，超分析师预期` 才是知识。」bdistill 工作流=描述需求→结构化提取→**对抗验证（5 种措辞重问）**→JSONL 持久化；不稳定=幻觉规则直接丢弃。
- **H 图像**：双轨 SOP——检索轨用 ColPali 原生视觉嵌入（图像直接变向量，无需 OCR）；执行轨用 VLM→Mermaid。天坑：不要对所有图像都做 VLM Caption（成本高且产生废话）。
- **I 实时内容**：「**双轨处理是铁律：行动项不入知识库，知识性内容不入任务系统。**」LLM 噪音过滤打标签 `[决策] [行动项] [技术判断] [方法论]`，决策走 ADR 格式模板。
- **J BI/SPA**：「BI 看板的数据是冰山，视觉只是水面上的 10%。」关键是 Playwright 拦截所有 API 响应（绕过 UI 直接拿数据立方体），再扁平化送场景 G。

**场景前置：输入诊断器**（Python dataclass 实现，四档处置）：

| 诊断结果 | 行动 | 记录到 |
|---|---|---|
| `SKIP` | 原文归档，不处理 | `skipped_inputs.log` + 说明原因 |
| `CACHE` | Redis TTL 缓存，不进向量库 | `cache_layer`，过期自动清除 |
| `PROCESS` | 按 `primary_type` 进入对应场景 SOP | 正常流水线 |
| `ESCALATE` | 进入人工分诊队列，48h 内处理 | `escalation_queue.jsonl` |

五个判断维度：来源可信度 / 内容完整度 / 半衰期 / 信息密度 / 验证成本。

### 2.5 七阶段流水线（Stage 0–6）

> **原文**：「**七阶段流水线**：需求建模 → 内容接入 → 结构化提取 → 质量验证 → 入库路由 → 检索消费 → **MCP 封装（2026新增）**」
> 「**编号口径**：Stage 0 是进入工程流水线前的需求与验收门禁，不计入执行阶段数量；真正的数据处理与交付链路固定为 Stage 1-6。」

#### Stage 0：需求建模 —— 问题→证据→验收闭环

> **原文警告**：「:::danger 最常被跳过的阶段，也是最重要的阶段。所有后续阶段的质量上限，由 Stage 0 定义问题的质量决定。没有问题集，就没有验收标准；没有验收标准，就无法判断系统是否完成。::」

- **Step 1 定义黄金问题集**：20-50 个代表性问题，覆盖四类——精确事实（测检索精度）/ 多跳推理（测图谱推理）/ 跨文档综合（测全局理解）/ 执行指导（测 Skill 调用）
- **Step 2 为每个问题标注证据要求**（原文数据结构）：

```python
GOLDEN_QUESTION = {
    "id": "GQ-001",
    "question": "美国市场暖奶器价格带分布是什么？",
    "type": "factual",
    "required_evidence": {
        "source": "Amazon竞品数据 2026Q1",          # 答案应来自哪里
        "evidence_level": 3,                        # Level 1-5，见附录A
        "staleness_limit_days": 30,                 # 超过多少天答案失效
    },
    "acceptance_criteria": {
        "must_include": ["价格区间", "代表品牌数量"],  # 答案必须包含的要素
        "must_not_include": ["2024年数据"],           # 答案不能包含的内容
        "confidence_floor": 0.75,                    # 最低置信度要求
    },
    "failure_consequence": "选品方向错误，影响库存决策",  # 答错后果
    "owner": "选品负责人",
}
```

- **Step 3 运行验收测试**（每次架构变更或数据更新后跑）
- **Step 4 上线门控（原文阈值）**：

```text
验收结果
├── pass_rate >= 0.80 AND blocked == False → 允许上线
├── pass_rate >= 0.70 AND blocked == False → 有条件上线（需标注已知盲区）
└── pass_rate < 0.70 OR blocked == True   → 禁止上线，返回 Stage 0 重新定义问题
```
其中 `blocked` = 有关键问题失败（即该问题的 `failure_consequence` 非空）。

> **最低可行版本（原文）**：「没时间做完整黄金问题集？至少写下这五个问题：**"如果系统答错了这道题，会造成真实的业务损失。"** 这五个问题就是你的最小化验收集，每次上线前必跑。」

#### Stage 1：内容接入与解析

格式路由（`route_parser`）→ 统一 Markdown/JSON。**三条硬约束**：
- **绝对不能用 token 数切块**：必须按文档结构边界（标题/段落/表格）切
- **图片内文字必须二次处理**：MinerU 裁出图片后，图片内的文字要再送 VLM
- Unlimited-OCR 的 `ngram_window`：单页 128，多页必须 1024

切块配置：`strategy: "structural"`（结构化切块，不是 token 切块），`overlap_tokens: 128`，`min_chunk_tokens: 100`，`max_chunk_tokens: 1000`。

#### Stage 2：结构化提取（原"知识蒸馏"）

蒸馏类型路由：方法论/流程 → `skill`（cangjie-skill RIA-TV++）；事实/概念 → `pyramid`（四层金字塔）；规则/决策 → `rule`（bdistill IF-THEN）；人物经验 → `persona`（nuwa-skill 双轨）。

**RIA-TV++ 六阶段（cangjie-skill 核心，逐条照录）**：

```text
Phase 0: 整书理解（Adler 分析阅读法）
  → 四步拆解：结构 / 解释 / 批判 / 应用
  → 产物：BOOK_OVERVIEW.md

Phase 1: 5路并行提取器
  → 框架提取器 | 原则提取器 | 案例提取器 | 反例提取器 | 术语对齐器

Phase 1.5: 三重验证（淘汰率 50-75%）
  → 规则1：≥2 处独立佐证（必须跨章节）
  → 规则2：具备预测力（能回答文中未明说的问题）
  → 规则3：非常识（不是人尽皆知的废话）

Phase 2: RIA++ 结构化
  → R（原文引用）+ I（自己重写）+ A1（书中案例）
  + A2（未来触发场景）+ E（执行步骤）+ B（边界与盲点）

Phase 3: Zettelkasten 链接
  → 识别 Skill 之间的依赖/对比/组合关系
  → 生成 INDEX.md 和引用图

Phase 4: 压力测试
  → 每个 Skill 设计包含诱饵题的测试用例
  → 未通过 → 回炉 Phase 2
```

三个 Prompt 工程模板（原子事实提取 / 概念聚合 / 跨文档冲突检测）在原文给出，原子事实输出格式为 `{"fact": "...", "source_sentence": "...", "confidence": 0.0-1.0}`。

#### Stage 3：质量验证（三道闸门）

**闸门一：三重验证** —— 独立佐证（≥2 处跨章节）+ 预测力（>0.6）+ 独特性/非常识（>0.5）。综合分 `overall_score > 0.8 → keep`，`> 0.4 → review`，否则 `discard`。

**闸门二：对抗一致性检测** —— 用 5 种不同措辞问同一个问题，一致性得分低于 0.6 标记为幻觉。

**闸门三：Acceptance Predicate（5 项全过）**：

```python
def acceptance_predicate(entry: dict) -> bool:
    checks = [
        # 1. 结构完整性：所有必填字段已填写
        all(f in entry for f in ["name", "trigger", "steps", "boundary"]),
        # 2. 溯源可追：source_path 指向真实可访问的来源
        Path(entry.get("source_path", "")).exists() or
        entry.get("source_url", "").startswith("http"),
        # 3. 去重：与现有条目无语义重复
        not has_duplicate(entry, similarity_threshold=0.85),
        # 4. 代码可执行性（有 code_field 时）
        entry.get("code_field") is None or is_executable(entry["code_field"]),
        # 5. 模态一致性：声明的模态字段有实际内容
        entry.get("visual_examples") is None or
        all(Path(p).exists() for p in entry["visual_examples"]),
    ]
    return all(checks)
```

#### Stage 4：入库路由

```python
def route_to_storage(knowledge: dict) -> str:
    # 可执行流程/方法论 → Skill 库
    if ktype in ["methodology", "procedure", "workflow"]: return "skill"
    # 时态/随时间变化的事实 → 记忆层（Graphiti）
    if ktype == "temporal" or knowledge.get("expires"): return "memory"
    # 实体关系/需要多跳推理 → 知识图谱
    if ktype in ["entity_relation", "causal", "comparative"]: return "graph"
    # 其余声明性知识 → 向量库
    return "vector"
```

生产配置：`kv_storage: PostgreSQL` / `vector_storage: Qdrant` / `graph_storage: Neo4j` / `embedding_model: BAAI/bge-m3`（**一旦选定不能更换**）/ `rerank_model: BAAI/bge-reranker-v2-m3`（可随时更换）。混合桥接用 `QdrantNeo4jRetriever`：Qdrant 点 ID == Neo4j 节点 ID，`id_sync_strategy: hash_based`。

**三态一致性与级联删除（防知识腐败）**：源文件更新/删除时 → ① 软删除向量库关联 Chunks（Tombstone）② `MATCH (n {source_hash: $hash}) DETACH DELETE n` ③ 将相关 `SKILL.md` 的 `status: active` 改写为 `status: outdated` + `outdated_at`。

#### Stage 5：检索与消费

意图分类四类 → 四路检索：`FACTUAL`→向量 Top-K（LightRAG `local` 模式）；`ANALYTICAL`→图谱遍历（`mix` 模式）；`PROCEDURAL`→Skill 库加载；`CONVERSATIONAL`→记忆+向量混合。

**多模态 RAG 三范式**：文本化 RAG（图片→VLM 描述→向量库，简单但信息损失）/ 原生视觉 RAG ColPali（文档页→直接图像向量，比文本化高 **25-39%**，但推理成本高需 GPU）/ 多智能体分层检索 ViDoRAG（Seeker 粗检索→Inspector 精审→回答，视频文档最优）。

#### Stage 6：MCP 封装层（2026 新增）

把知识库封装为 MCP Server，让 Claude Desktop / Cursor / Codex App 等任意 MCP Client 直接调用，无需写适配代码。原文给了完整 `FastMCP("product_kb")` 最小实现（`search_products` + `get_market_overview`）与 Claude Desktop 配置路径。

**MCP 路由冲突与裁决：PTDS 四维优先级**：
| 优先级 | 维度 | 规则 |
|---|---|---|
| P1 | **精确性 Precision** | 更精确匹配任务意图的工具优先 |
| P2 | **时效性 Timeliness** | 要求实时时，新鲜度优先于深度 |
| P3 | **数据级别 Data Level** | 默认优先使用最低敏感级别能满足需求的来源 |
| P4 | **成本 Cost** | 同等质量下低成本路由优先 |

> **路由治理的核心原则（原文）**：「协议标准化（MCP）解决的是接口问题，不解决语义冲突和责任归属。**每个 MCP Server 应该有明确的"服务边界声明"**：它承诺回答什么、不回答什么、精度保证范围是什么。没有边界声明的 Server 接入越多，路由器的不确定性越高。」

### 2.6 Skill 蒸馏四路线（九仓库深度解构）

| 路线 | 代表仓库 | 信息源 | 蒸馏对象 | 核心主张 | Agent 调用有效性 |
|---|---|---|---|---|---|
| **一 方法论蒸馏** | `kangarooking/cangjie-skill`(4.6K) | 书籍/视频/播客 | 方法论 | 把方法论拆成可调用工具包 | ★★★★★ |
| **二 人格克隆** | `alchaincyf/nuwa-skill` / `ex-skill`(5.9K) / `yourself-skill`(3.2K) | 公开资料/聊天记录/日记 | 人的思维方式 | 让名人给你打工 | ★★★★☆（ex-skill ★★☆☆☆） |
| **三 工程操作蒸馏** | `microsoft/Resource2Skill`(278) | 教程视频/代码/产物 | 可执行工程操作 | 从多模态资源提炼真正可运行的 Skill | 待复核 |
| **四 Skill 进化** | `alchaincyf/darwin-skill` | 已有 SKILL.md | Skill 本身 | 棘轮优化 | N/A（元工具）★★★★★ |

**Resource2Skill 的 Skill Wiki 条目结构（最值得照抄的设计）**：

```json
{
  "name": "skill_name",
  "text_body": "何时触发 / 为何使用 / 如何配置",
  "code_field": "目标：经 smoke test 的代码模板（含完整 import）",
  "visual_examples": ["操作前/操作后截图路径"],
  "source_path": "原始教程的章节路径",
  "acceptance_predicate": {
    "structural_completeness": true,
    "source_traceability": true,
    "code_executable": true,
    "no_duplication": true
  }
}
```

**darwin-skill 达尔文棘轮机制（原文）**：

```text
1. 基线评估（9维度加权打分，满分100）
        ↓
2. 单维度优化实验（每轮只改一个维度）
        ↓
3. validation-gated 验证（独立评委，不复用）
        ↓
   得分提升? → (OK) 保留（git commit）
   得分持平? → (X) 回滚（git revert）
   得分降低? → (X) 回滚 + 标注失败模式
```

**9 个评估维度（v2.0，对齐微软 SkillLens 论文）**：① 触发精确性 ② 执行步骤清晰度 ③ 可执行具体性（禁止"视情况而定"等模糊词）④ 边界与禁忌 ⑤ 失败模式编码 ⑥ 高风险行动黑名单（rm/force-push 等）⑦ 溯源可追 ⑧ 格式规范 ⑨ 上下文感知。

**darwin-skill 明文禁止的 8 条反模式（原文表，最有价值的工程经验）**：

| 反模式 | 原因 |
|---|---|
| 同一个 AI 又改又评 | LLM 自评准确率仅 46.4%（SkillLens 实证） |
| 用 `git reset --hard` 回滚 | 应用 `git revert`，保留变更历史 |
| 为凑分而堆冗余内容 | 评分提升但 Agent 调用时 context 膨胀 |
| 跳过 test-prompts 直接评分 | 等于没有验证 |
| 一轮内改多个维度 | 无法定位哪个改动带来了提升 |
| 干跑比例 > 30% | Skill 覆盖面不足的信号 |
| 静默跳过异常 | 掩盖失败，累积技术债 |
| 忽视维度相关簇 | 维度之间有耦合，需要联动调整 |

**四条混编设计模式**：① cangjie → darwin（方法论迭代，最常用，先上线 2-4 周收集反馈再启动 darwin）② R2S → cangjie（操作骨架 + 判断逻辑填充）③ nuwa → cangjie（风格层 + 方法论层双轨）④ 单独 darwin（仅优化已有 Skill）。**三条混编禁忌**：不要并行合并（血缘不清无法归因）／不要超过两条路线／不要在同一 Skill 里混用方法论层和人格层。

**三条核心整合原则（原文）**：
1. **方法论 Skill 必须用 RIA++ 结构，不能用摘要**。✓ 正确：`触发条件 + 执行步骤 + 边界说明`；✗ 错误：`本书的核心观点是...`
2. **人格 Skill 只提炼决策框架，不模仿语气**。✓ 正确：`当遇到 X 问题时，先算物理极限，再看实际路径是极限的几倍`；✗ 错误：`保持马斯克的口吻和语气风格`
3. **所有入库的 Skill 都必须接入达尔文棘轮**。

### 2.7 统一验证框架：VTRCE 五维（全书的最高裁决层）

> **原文**：「**VTRCE 框架**（Validity/Timeliness/Relevance/Cost/Error Cost）是全书统一的目标函数。」

| 维度 | 含义 | 典型度量 |
|---|---|---|
| **V** Validity | 知识是否正确 | 幻觉率、事实核查通过率 |
| **T** Timeliness | 知识是否及时 | 新鲜度得分、过期率 |
| **R** Relevance | 知识是否相关 | 查询命中率、Top-K 精度 |
| **C** Cost | 获取/维护成本是否可持续 | 全生命周期单位成本 |
| **E** Error Cost | 出错后的代价是否可控 | 错误代价分层、回滚时间 |

**场景权重 Profile（原文）**：

```python
VTRCE_PROFILES = {
    "合规/财务场景": {"V": 0.35, "T": 0.15, "R": 0.20, "C": 0.10, "E": 0.20},
    "选品/营销场景": {"V": 0.20, "T": 0.30, "R": 0.25, "C": 0.20, "E": 0.05},
    "工程操作场景": {"V": 0.30, "T": 0.10, "R": 0.30, "C": 0.15, "E": 0.15},
    "客服问答场景": {"V": 0.25, "T": 0.20, "R": 0.35, "C": 0.15, "E": 0.05},
}
```

**三阶段验证门控**：

- **门控一：上线前（Pre-Launch Gate）五个必答问题**：① 黄金问题集命中率 ≥ 70% ② 幻觉率 < 10%（引用幻觉为零）③ 数据分级完成：所有条目有 `data_level` + `valid_until` + `owner` 三个元数据 ④ 回滚机制就绪：存在最近验证通过的系统快照，可在 30 分钟内回滚 ⑤ 错误代价已评估
- **门控二：上线后 30 天（Post-Launch Check）三个信号**：使用模式是否与 Stage 0 预期一致 / 反馈信号是否真实（长期价值 vs 即时体验）/ 业务指标是否有早期相关迹象
- **门控三：季度复审（Quarterly Review）四组清单**：知识质量 / 进化健康 / 成本结构 / 组织健康（含"团队是否出现判断能力退化信号"）

**证据裁决三原则**：
- **原则一 最低证据门槛**：任何进入决策的知识声明至少满足其一——两个独立来源互印（非同一作者引用链）／一个来源 + 一个实验验证／一个来源 + 一个反例分析
- **原则二 证据强度分级**：Level 1 单一来源无验证 → Level 2 多来源互印 → Level 3 有实验/测试数据 → Level 4 长期业务数据（≥3 个月）→ Level 5 受控对照实验。**「知识条目的 `confidence` 字段应对应上述分级，而不是模型的自信度。」**
- **原则三 举证责任分配**：新知识入库由写入者举证（≥L2）／质疑现有知识由质疑者举证（≥L3）／删除知识由删除者举证（≥L3 或 Owner 签字）／覆盖冲突知识需两方都举证，由 Knowledge Owner 裁决

**横跨全书的四大盲区与解法**：① 目标函数分裂 → VTRCE ② 治理层空白 → 第十三章 §13.9 + 第十四章 §12.8 ③ 反向纠错缺席 → 第一章 §Skill 反向纠错链路 ④ 错误代价盲区 → 第十七章 §失败类型矩阵

**L4 纠正链路（对"怎么保证可追溯"最直接的回答）**：错误信号（用户"很像对的但方向不对"、下游指标无法解释下降、成功率 95%→85%、"正确但无用"输出）→ 五步回滚：

```text
L4 Skill 错误
  ↓ 步骤1：隔离受影响的 Skill 版本，暂停 darwin 迭代
  ↓ 步骤2：找到最近一次"业务验证通过"的 Skill 版本，回滚
  ↓ 步骤3：从 Skill 回退到 L3 层——检查支撑该 Skill 的知识图谱/社区摘要
  ↓ 步骤4：从 L3 回退到 L1/L0——找到原始来源文档，验证其是否仍然有效
  ↓ 步骤5：确认根因后，从正确的 LoD 层重新蒸馏
```

每个 Skill 必须记录的纠错锚点（YAML 原样）：

```yaml
skill: pdf-complex-parse
version: v2.3
created_from:                    # 向下追溯的锚点
  source_docs:
    - "MinerU官方文档 v2.1"
    - "内部经验总结 2025-Q3"
  knowledge_layer: L2            # 该Skill基于的知识层级
  raw_cases:                     # L0原始案例，出错时可回看
    - "cases/pdf-parse-failures-2025.jsonl"
rollback_to: v2.1                # 上一个验证版本
last_validated: "2026-06-01"
validated_by: "张工"
```

> **关键原则（原文）**：「每次 Skill 版本迭代，必须保留上一个"业务验证通过"的版本作为回滚点。不允许在没有前一版本锚点的情况下覆盖入库。这条原则成本极低（只是保存一个版本快照），但可以将 L4 错误的平均修复时间从"数天"缩短到"数小时"。」

### 2.8 知识库自进化：五层飞轮 + 评分器治理

**知识库三种死法**：知识老化 / 知识污染 / 知识孤岛。

**进化系统五层模型**：L1 新鲜度进化 → L2 质量进化 → L3 覆盖进化 → L4 关系进化 → **L5 治理进化**（校准评分器本身，防止漂移）→ 回流 L1。

**健康度六维度（含告警阈值，原文）**：

| 维度 | 衡量指标 | 告警阈值 |
|---|---|---|
| **新鲜度** | 距上次更新的天数 | >90天 |
| **一致性** | 冲突条目比例 | >5% |
| **覆盖率** | 查询命中率 | <80% |
| **幻觉率** | 幻觉检测比例 | >10% |
| **孤岛率** | 孤立节点占比 | >20% |
| **利用率** | 30 天内零查询的条目比例 | >30% |

**冲突仲裁三类**：数值冲突（有时间戳→新版覆盖旧版；无时间戳→标记冲突等人工）/ 时态冲突（自动标记 `supersedes`，旧版降权）/ 观点分歧（双向挂载，标注来源，**呈现分歧本身**）。

> **评分器的元治理原则（原文）**：「:::warning 评分器不能自我证明。永远不要用"darwin-skill优化的结果"来评估"darwin-skill评分器是否合理"。这是循环论证，相当于用考试成绩来证明考试题目出得好。评分器的校准标准必须来自外部——业务结果、用户满意度、黄金样本，而不是系统内部指标。:::」
> 治理分工：每个评分维度应有**维度负责人**；季度校准审计由**知识库负责人**主持，**不能委托给运行评分器的工程师**（存在利益冲突）；重大调整（权重变化超过 ±10%）需双人审核。

**评估三条铁律**：① **评估模型必须与生成模型不同**（LLM 自评准确率仅 46.4%）② **幻觉检测必须在句子级别，不是文档级别** ③ **每次知识库更新后必须跑完整基准测试**。

**对抗性测试四类**：边界溢出测试 / 知识版本攻击 / 合成悖论 / 权威诱导（用听起来权威的虚假前提提问，验证系统是否会顺着错误前提推理）。

**评估集三层保鲜策略**：定期轮换（每季度替换 20-30%）/ 盲测隔离（调优集不出现在评估集，防 Goodhart 定律）/ 用户贡献注入（每月从真实查询日志抽 10-20 个失败案例人工标注后加入）。

**错误成本分层与层间归因**：

| 评估层 | 典型错误 | 错误成本量级 | 修复路径 |
|---|---|---|---|
| **检索层** | Top-K 召回了无关文档 | 低 | 调 embedding 或重排序参数（1-2天） |
| **生成层** | 模型根据正确文档给出错误结论 | 中 | 加强事实锚定+二次验证（1-2周） |
| **业务层** | 正确回答但用户做出错误决策 | 高 | 重新定义回答格式与决策上下文 |
| **治理层** | 系统以错误方式进化（评分器漂移） | 极高 | 回滚评分器，重建校准基准 |

> **跨层归因的常见错误（原文）**：「**不要把业务层失败当成检索层失败来修复。** 提升召回率解决不了"答案正确但用户不知道怎么用"的问题。」

### 2.9 Agent 设计与编排（第 22 章）

三种单 Agent 范式：ReAct（通用，工具调用密集）/ Plan-then-Execute（复杂多步，全局视图好）/ Reflection（质量驱动，延迟高）。

MAS 四种拓扑：顺序 Pipeline / 并行 Fan-out / 层级 Hierarchical / 图 Graph-Cyclic。

**反多 Agent 崇拜（实测数据，原文）**：

```
任务类型               单 Agent(GPT-4o)    MAS(3个Agent)
──────────────────────────────────────────────────────
简单问答               $0.002 / 2s          $0.008 / 8s   ❌ MAS更差
代码生成（<200行）      $0.015 / 8s          $0.04 / 25s   ❌ MAS更差
复杂研究报告（>3000字） $0.08 / 45s          $0.06 / 35s   ✅ MAS更好
多文件代码重构         $0.12 / 60s          $0.09 / 40s   ✅ MAS更好
```
**MAS 三个充分条件（满足任一）**：真正可并行的独立子任务 / 不同子任务需显著不同专业知识且 context 超单窗口（>100k tokens）/ 需要独立批评验证（Critic 模式）。

**Skill 库规模阈值（决定是否要 Skill 检索）**：< 50 → prompt caching 全量加载；50-200 → 单步 retrieve-and-rerank（SkillRouter）；200+ → 完整 Compositional Skill Routing（Decomposer → Bi-encoder FAISS → Skill-Aware 反馈循环（准确率 51%→67.7%）→ DAG 规划器）。

**Skill 原子性约束 The 3-7-1 Rule（原文）**：
> 「一个合格的 SKILL.md 必须满足：最多 **3** 层逻辑嵌套、最多 **7** 个主要执行步骤、单一的输入输出结构。
> - **降级拆解**：若蒸馏出的长视频或复杂流程超过 7 步，必须拆分为一个 `MASTER_SKILL.md` 引用多个子 Skill。
> - **硬编码降级**：若 Skill 中包含大量复杂的 IF-THEN 判断，不要用自然语言让 LLM 去猜，必须将其提取为 Python 脚本并封装为 MCP 工具，SKILL 仅负责调用该工具。」

**工具调用幂等性**：非幂等工具在 Agent 重试时会产生副作用（重复邮件/重复写入/重复支付），需 `IdempotencyStore` + `@idempotent_tool(key_params=[...])` 装饰器。

---

## 3. 仓库的实际目录结构

```
Kb2Agent/
├── .github/workflows/deploy.yml     # GitHub Pages 部署
├── .codegraph                       # symlink
├── .omo/run-continuation/*.json     # 26 个会话延续状态文件（工具遗留物）
│
├── docs/                            # ===== Guide 产品线（VitePress 站点）=====
│   ├── index.md                     # 首页（唯一"README"，172 字节，挂 <MkdProductHome/>）
│   ├── .vitepress/
│   │   ├── config.js                # 全站导航（基础篇/工程篇/进阶篇/实战篇四段）
│   │   ├── search-quality.mjs       # 搜索别名 & 意图路由加权（"评估"→第14章 等）
│   │   └── theme/components/        # 13 个 Vue 组件 + agent-lab/ 5 个组件
│   │       ├── EvidenceCatalog.vue / ConceptMap.vue / ClaimLedger.vue
│   │       ├── AcceptanceWorkbench.vue / ReferenceLab.vue / ReferenceSystemPage.vue
│   │       ├── MermaidDiagram.vue / MkdProductHome.vue
│   │       └── agent-lab/AgentLab.vue, AgentTaskPanel.vue,
│   │           AgentExecutionSpine.vue, AgentDecisionPanel.vue, AgentEvidenceDrawer.vue
│   │
│   ├── knowledge/                   # ★★ 23 个方法论章节（Guide 主体）★★
│   │   ├── 00-introduction.md       # 2026 全景 + 十个反直觉洞察 + 五反模式 + 四劣化机制
│   │   ├── 01-framework.md          # DIKW + LoD L0-L4 + 四层金字塔 + 反蒸馏 + L4纠错链路
│   │   ├── 02-decision-matrix.md    # 五步路由 + 半衰期 + 5产品形态 + 10输入 + 6输出 + Triage
│   │   ├── 03-scene-sops.md         # 十场景 SOP + 场景横向对比表 + 输入诊断器
│   │   ├── 04-architecture.md       # ★ Stage 0-6 七阶段全链路 ★
│   │   ├── 05-security-compliance.md / 05-graphrag.md
│   │   ├── 06-agent-call.md         # 三种调用模式 + MCP + PTDS 路由裁决 + 3-7-1 Rule
│   │   ├── 07-advanced-theory.md    # 架构选型 LoD 指南
│   │   ├── 08-tools-appendix.md     # 工具手册与决策树
│   │   ├── 09-reasoning-models.md / 09-skill-distillation-deep-dive.md  # 四路线九仓库
│   │   ├── 10-cost-model.md / 10-e2e-pipeline.md   # ★ 完整 Pipeline + config.yaml ★
│   │   ├── 11-kb-evolution.md       # 五层飞轮 + 六维健康度 + 评分器治理
│   │   ├── 12-evaluation.md         # 三层评估 + 幻觉检测 + 对抗测试 + 保鲜机制
│   │   ├── 15-codex-prompts.md / 16-voc-case-study.md / 17-failure-cases.md
│   │   ├── 18-tech-selection-2026.md / 19-tech-selection-vol2.md
│   │   ├── 20-ops-runbook.md / 21-data-collection.md / 22-agent-design.md
│   │   ├── 23-finetuning-vs-rag.md
│   │   └── appendix-validation.md   # ★ 附录A VTRCE 统一验证框架 ★
│   │
│   ├── architecture/                # ★ Reference 的设计规格与审计 ★
│   │   ├── adrs/{001..005,README}   # 5 条架构决策记录
│   │   ├── m1-a-product-contract.md # ★ 产品合同（一句话价值/双产品/E2边界/输出合同）★
│   │   ├── m1-a-schema-catalog.md / m1-a-test-blueprint.md / m1-a-design-audit.md
│   │   ├── m1-b-cross-audit.md / m1-b-implementation-receipt.md
│   │   ├── g6-a1-replay-first-e2-agent-design.md   # ★ Replay-first Agent 冻结设计 ★
│   │   ├── g6-a2..a11 / g7-a1..a2 系列 / mkd-design-spec.md / mkd-information-architecture.md
│   │   └── license-audit.md
│   │
│   ├── reference/{build,cases,evidence,map,ops}.md   # Reference 六个视图页
│   ├── agent-lab/index.md / lab/index.md, lab/runs/amazon-ads-replay-001.md
│   ├── acceptance.data.mjs / claims.data.mjs / concepts.data.mjs / knowledge.data.mjs
│   └── public/reference/
│       ├── g6/agent-lab-bundle.json
│       └── m1b/{canonical-dry-run,evaluation-report,extraction-receipt,knowledge-map,
│               m1-b-execution-receipt,review-packet,snapshot}.json
│           └── runs/RUN-AMZ-M1B-001/{action-package,receipt,replay-bundle,report.md,trace}.json
│
├── knowledge-system/                # ===== 知识治理注册表（YAML/JSON，机器可读）=====
│   ├── acceptance.yml               # ★ 3 份验收合同（均 approval-blocked）★
│   ├── acceptance/{datasets,receipts}/*.json
│   ├── claims.yml / concepts.yml / documents.yml   # Claim/概念/文档身份注册表
│   ├── capability-map.json / audit-baseline.json   # 能力地图 & 审计基线
│   ├── roles.json                   # 四类具名角色（CONTENT/EVIDENCE/TEST/APPROVER）
│   ├── product-{claims,decisions,lines}.json
│   ├── public-projection-manifest.json
│   ├── g6-a10-public-evidence-review-packet-accepted.json
│   ├── mkd-distill-g4r6-public-review-packet.json
│   └── schemas/                     # 26 个注册表侧契约（含 g6-a3/a5/a10/a11、g7-roadmap）
│
├── reference/                       # ===== Reference Lab 运行时 =====
│   ├── runtime/
│   │   ├── g6-agent.mjs             # ★★ 确定性 Agent Runner（8 工具 / 4 终态）★★
│   │   ├── compiler.mjs (16KB) / extract.mjs (12KB) / agent.mjs / cli.mjs
│   │   ├── g6-utils.mjs / utils.mjs
│   ├── schemas/                     # 19 个核心 Schema
│   │   ├── common.schema.json       # ★ identifier/hash/evidenceGrade/eLevel/baseObject
│   │   ├── knowledge-object.schema.json  # ★ Concept/Metric/MentalModel/DecisionModel/Heuristic/Case/Playbook（oneOf 7 类）★
│   │   ├── skill.schema.json / task-package.schema.json / action-package.schema.json
│   │   ├── governance.schema.json   # ★ 8 类治理对象 ★
│   │   ├── source/evidence/evaluation/relation/release-snapshot/run-trace/
│   │   │   knowledge-receipt/reference-package .schema.json
│   │   └── g6/{action-package, agent-execution-receipt, approval-decision,
│   │           capability-manifest, execution-plan, fixture-dataset,
│   │           refusal-receipt, tool-call-receipt}.schema.json
│   ├── ontology/{terms,relations,permissions}.json   # 术语/关系类型/权限三元组
│   ├── policies/g7/{deepseek-v4-flash-pricing-policy-2026-08-13,
│   │                provider-readiness-policy-v1}.json
│   ├── golden/amazon-ads-diagnosis-v1.json           # ★ 20 条 golden tasks ★
│   ├── corpus/amazon-ads-v1/{manifest.json, normal/*, negative/*}
│   │       # normal: .pdf/.docx/.pptx/.xlsx/.md/.json 六种真实格式合成语料
│   │       # negative: conflicting-guidance / missing-metrics /
│   │       #           outdated-context / scanned-empty
│   ├── fixtures/{positive,negative,g6,g7}/
│   │       # positive/amazon-ads-reference-package.json (19.5KB)
│   │       # negative/: case-auto-promotes-skill / invalid-e3-skill /
│   │       #   invalid-relation-endpoint / missing-locator /
│   │       #   snapshot-hash-mismatch / supersedes-cycle
│   │       # g6/agent-cases-v1.json（20 条门禁案例）
│   ├── adapters/guide-registry-map.json
│   └── reviews/                     # （package.json 引用，已被裁剪）
│
├── scripts/                         # 30 个校验/构建脚本
│   ├── check-{acceptance,capability-map,claims,concepts,content-metrics,
│   │          document-identity,evidence,links,lighthouse,preview-isolation,
│   │          reference-contracts,rendered-headings,semantic-links,
│   │          site-performance,snippets}.mjs
│   ├── {claim,concept,knowledge,acceptance}-registry.mjs
│   ├── build-{g6-agent,m1b}.mjs / docs-audit.mjs / markdown-metrics.mjs
│
├── fixtures/                        # 运行时 fixture 模块
│   ├── mock-pipeline.mjs            # ★ 唯一 smoke-tested 的确定性 mock pipeline ★
│   ├── acceptance-harness.mjs / cost-model.mjs /
│   │   evaluation-regression.mjs / security-governance.mjs
│   ├── response-contract.py / safe-delete.sh
│
├── tests/                           # node --test 内容契约测试
├── artifacts/                       # 设计审计截图（.png）
├── playwright{,.distill-public,.mermaid-hydration}.config.mjs
├── package.json (14KB, 130+ scripts)
├── content-audit.md (23KB) / design-qa.md / qa-receipt.md
├── knowledge-system-audit.md (15.4KB)
├── g2-1-claim-pilot-audit.md / g2-2-ownership-evidence-audit.md
├── g2-3-concept-usage-graph-audit.md / g2-4-acceptance-contract-audit.md
└── {fix_mermaid,patch_doc_v5,patch_doc_v6,patch_doc_v7,split_doc}.py
```

**关键文件作用速查**：

| 文件 | 作用 |
|---|---|
| `docs/knowledge/04-architecture.md` | 方法论主干：Stage 0-6 七阶段全链路 |
| `docs/knowledge/01-framework.md` | DIKW + LoD L0-L4 + 反蒸馏 + L4 纠错链路 |
| `docs/knowledge/02-decision-matrix.md` | 五步路由：半衰期→形态→输入→输出→Triage |
| `docs/knowledge/03-scene-sops.md` | 十场景工程 SOP + 输入诊断器 |
| `docs/knowledge/10-e2e-pipeline.md` | 可直接照抄的 `config.yaml` + `ingest.py`/`storage.py`/`retrieval.py` |
| `docs/knowledge/appendix-validation.md` | VTRCE 统一裁决层 + 三阶段门控 + 证据裁决 |
| `docs/architecture/m1-a-product-contract.md` | 产品合同：一句话价值 / E2 边界 / ActionPackage 输出合同 |
| `docs/architecture/g6-a1-replay-first-e2-agent-design.md` | ★ Agent 的冻结设计：8 合同对象 / 4 终态 / 20 案例矩阵 / 验收合同 |
| `reference/runtime/g6-agent.mjs` | ★★ Agent Runner 的唯一可执行真相 ★★ |
| `reference/schemas/common.schema.json` | 证据等级 / E-Level / baseObject 元数据 |
| `reference/schemas/knowledge-object.schema.json` | 知识对象的 7 种类型定义 |
| `docs/public/.../action-package.json` | Agent 的**真实产物样本** |

---

## 4. 生成出来的 Agent 长什么样

### 4.1 编译产物链（Compiler 视角）

方法论要求（`10-e2e-pipeline.md` §12.1 项目结构约定，可直接照抄）：

```text
kb-agent/
├── pipeline/
│   ├── ingest.py          # Stage 1+2+3：解析、蒸馏、验证
│   ├── storage.py         # Stage 4：入库路由
│   ├── retrieval.py       # Stage 5：检索
│   └── evolution.py       # 知识库进化
├── skills/                # ~/.agents/skills/ 的本地镜像
├── wiki/                  # LLM-Wiki 文件系统
│   ├── index.md
│   ├── log.md
│   ├── entity_pages/
│   └── summaries/
├── raw/                   # 只读原始资料
├── config.yaml            # 所有配置
├── requirements.txt
└── main.py                # 入口文件
```

L4 SKILL.md 的文件格式约定（`storage.py::_store_to_skill` 实际生成）：

```markdown
---
name: {skill_name}
status: active
source: {source_path}
created_at: {ISO8601}
---

# {name}

### 触发条件
{trigger}

### 执行步骤
{steps}

### 边界与禁忌
{boundary}

### 来源引用
{reference}
```

### 4.2 受控 Agent 的完整运行链（G6-A1 冻结设计）

**Agent 生成方式不是"写 prompt"，而是"装配合同对象"**。完整链路（原文）：

```text
G6 Fixture
  → input schema gate
  → CapabilityManifest / ToolPolicy
  → deterministic ExecutionPlan
  → tool executor registry
  → ToolCallReceipt[]
  → ActionPackage
  → ApprovalDecision 或 RefusalReceipt
  → AgentExecutionReceipt
  → immutable replay bundle
```

**八个合同对象**：
1. `CapabilityManifest v1`：Agent 身份、模式、工具白名单、禁止能力与预算
2. `ToolPolicy v1`：工具 mode、输入/输出合同、`sideEffect=false` 与失败策略
3. `ExecutionPlan v1`：固定步骤、工具、输入引用、预期输出和 guard 条件
4. `ToolCallReceipt v1`：每次真实本地函数调用的输入/输出 hash、状态、耗时常量和错误码
5. `ActionPackage v2`：事实、推断、未知、计算、选项、风险、停止条件与批准要求
6. `ApprovalDecision v1`：`pending` 状态和所需角色
7. `RefusalReceipt v1`：越权请求的规则、原因、请求摘要和安全替代路径
8. `AgentExecutionReceipt v1`：run、snapshot、task、agent、plan、tools、artifacts、终态和零副作用计数

**固定八个工具（每个都 `sideEffect: false`、`onFailure: 'fail-closed'`）**：

| toolId | mode | inputContract | outputContract |
|---|---|---|---|
| `TOOL-READ-SNAPSHOT` | read | snapshot reference | snapshot metadata |
| `TOOL-SEARCH-FTS` | read | bounded query | ranked local object refs |
| `TOOL-LOAD-CLOSURE` | read | task package ref | bounded object closure |
| `TOOL-CHECK-FRESHNESS` | calculate | evidence state | freshness decision |
| `TOOL-CHECK-PERMISSION` | calculate | requested capability | permission decision |
| `TOOL-CALCULATE-METRIC` | calculate | comparable metric inputs | deterministic ACOS delta |
| `TOOL-DRAFT-ACTION` | draft | facts and guard decisions | review-only action package |
| `TOOL-EMIT-RECEIPT` | draft | run artifacts | immutable execution receipt |

**能力预算（CapabilityManifest，硬编码为 const）**：

```js
budgets: {
  maxToolCalls: 8, maxExternalCalls: 0, maxSideEffects: 0,
  maxCanonicalWrites: 0, maxPlatformWrites: 0,
},
prohibitedCapabilities: [
  'live model invocation', 'external platform write', 'external message send',
  'canonical knowledge promotion', 'arbitrary file or URL input'
],
providerCallsAllowed: false, externalWritesAllowed: false, canonicalWritesAllowed: false
```

**四终态模型**：

| 终态 | 条件 | 允许输出 |
|---|---|---|
| `needs-approval` | 正常任务完成本地草案 | ActionPackage + pending ApprovalDecision |
| `needs-review` | 证据缺失、过期或冲突 | unknowns + next evidence，**不给精确行动结论** |
| `refused` | 请求写操作、发送或非白名单工具 | RefusalReceipt + 安全替代路径 |
| `failed` | fixture schema 或内部工具合同错误 | fail-closed error receipt，**不伪造行动包** |
| `completed` | 保留给未来已批准且完成的只读任务 | **本轮 20 条 case 不得出现** |

**输入白名单（防止任意输入注入）**：
```js
const ALLOWED_INPUT_KEYS = new Set([
  'caseId','comparisonWindow','focus','output','locale',
  'missingEvidence','conflicts','stale','requestedAction','requestedTool'
])
```

### 4.3 真实产物样本：ActionPackage

`docs/public/reference/m1b/runs/RUN-AMZ-M1B-001/action-package.json`（完整照录）：

```json
{
  "actionPackageId": "ACTION-AMZ-M1B-001",
  "taskPackageId": "TASK-AMZ-ADS-DIAGNOSIS-V1",
  "runId": "RUN-AMZ-M1B-001",
  "summary": "The immutable synthetic snapshot confirms an ACOS increase while preserving causal uncertainty and forbidding account changes.",
  "facts": [
    { "text": "Synthetic ACOS rises from 28.4% to 36.9% across comparable seven-day windows.",
      "evidenceRefs": ["EVID-AMZ-ACOS-DELTA"] }
  ],
  "inferences": [
    { "text": "CPC, CVR, price, or availability may contribute, but the snapshot does not establish a cause.",
      "evidenceRefs": ["DECISION-AMZ-ACOS-DIAGNOSIS"] }
  ],
  "unknowns": [
    { "question": "Did CPC, CVR, price, or availability change?",
      "impact": "No optimization path can be selected as a verified recommendation.",
      "nextEvidence": "Provide comparable, authorized evidence and rerun the local review gate." }
  ],
  "options": [
    { "optionId": "OPTION-AMZ-VERIFY-001",
      "label": "核验驱动证据",
      "action": "Compare CPC and CVR in identical windows and inspect price and retail availability.",
      "tradeoff": "Defers optimization but prevents unsupported account changes.",
      "externalWrite": false }
  ],
  "recommendation": "Request the missing comparable evidence and retain every optimization step as a human-reviewed manual draft.",
  "calculations": [
    { "metricRef": "METRIC-AMZ-ACOS",
      "formula": "ad_spend / attributed_sales * 100",
      "inputs": { "previousSpend": 284, "previousSales": 1000,
                  "latestSpend": 369, "latestSales": 1000 },
      "unit": "%", "window": "7d vs 7d",
      "result": "28.4% → 36.9% (+8.5pp)", "resultState": "exact" }
  ],
  "risks": [
    "Synthetic values cannot justify an account change",
    "Causal inputs are intentionally absent"
  ],
  "stopConditions": [
    "Do not modify bids, budgets, targeting, or campaign state",
    "Stop on stale, contradictory, missing, or permission-invalid input"
  ],
  "approvalRequirements": ["ROLE-AMAZON-ADS-DOMAIN", "ROLE-PRODUCT-CONTENT"],
  "evidenceRefs": ["EVID-AMZ-ACOS-DELTA", "EVID-AMZ-ACOS-DEFINITION", "EVID-AMZ-EVIDENCE-GATE"],
  "status": "draft-for-review"
}
```

**ActionPackage Schema 关键约束**（`action-package.schema.json`）：
- 每个 `assertion`（fact/inference）**必须**带 `evidenceRefs`（`minItems: 1`），`additionalProperties: false`
- `status` 只能是 `draft-for-review` / `blocked-insufficient-input` / `approved-for-manual-execution`——**没有"已执行"状态**
- `calculation.resultState` 四态：`exact` / `range` / `formula-only` / **`blocked`**（证据不足时只给公式、区间、未知项，**不允许伪造精确数值**）
- `option.externalWrite` 硬编码 `const: false`

### 4.4 Agent 的状态机与血缘链

**知识对象依赖链（`knowledge-map.json` 实测）**：

```
CONCEPT-AMZ-ACOS (Concept)  ──defines──▶ CLAIM-AMZ-ACOS-RISING
                                            ▲ supports
                              EVID-AMZ-ACOS-DELTA (Evidence)
                                            │ defines
                                            ▼
METRIC-AMZ-ACOS (Metric) ◀──uses_metric── DECISION-AMZ-ACOS-DIAGNOSIS (DecisionModel)
                                            ▲ implements
                              PLAYBOOK-AMZ-ACOS-CHECK (Playbook)
                                            ▲ implements
                              SKILL-AMZ-ADS-DIAGNOSIS-V1 (Skill)
                                            ▲ implements
                              TASK-AMZ-ADS-DIAGNOSIS-V1 (TaskPackage)
                                            │ validated_by
                                            ▼
                              EVAL-AMZ-ADS-DIAGNOSIS-V1 (Evaluation)
                                            │
                              CASE-AMZ-ACOS-SYNTHETIC (Case)
```

即 **Concept → Metric/DecisionModel → Playbook → Skill → TaskPackage → Evaluation → ActionPackage** 的完整可追溯链。这正是"知识库如何转成 Agent"的答案：**TaskPackage 是把 Skill 绑到具体输入合同+闭包上限后的可执行单元**。

**TaskPackage Schema（L6）** 必填字段：
```
name, taskContract, requiredClosure{objectIds, allowedRelations, maxDepth(1-4), maxObjects(1-100)},
skillRef, outputSchemaRef(固定 = action-package.schema.json), evaluationRefs, eLevel, publicInput
publicInput: { freeText: false, fileUpload: false, urlInput: false, allowedParameters: [...] }
```

### 4.5 如何被调用

**① CLI**：
```bash
node reference/runtime/cli.mjs evaluate        # npm run reference:evaluate
npm run reference:build                        # node scripts/build-m1b.mjs
npm run reference:test                         # node --test tests/content/m1b-pipeline.test.mjs
npm run reference:contracts                    # node scripts/check-reference-contracts.mjs
npm run agent:build / agent:test               # G6 Agent 构建与测试
```
方法论层的 CLI 约定（Python 版）：
```bash
python main.py ingest "your_document.pdf"
python main.py ingest "https://paulgraham.com/founders.html"
python main.py query "如何验证产品假设？"
python main.py health
```

**② Agent Lab 网页回放**（`/agent-lab/`）：静态页面加载 `docs/public/reference/g6/agent-lab-bundle.json`，零网络请求，`useAgentReplay.mjs` 管理 idle/running/complete 状态。

**③ MCP**（方法论层设计，**Reference 尚未实现 adapter**）：`FastMCP("product_kb")` + `@mcp.tool() search_products(...)`，Claude Desktop 通过 `claude_desktop_config.json` 接入。

**④ 构建流程契约（`agent:build` 六步）**：
1. 验证冻结 M1-B snapshot/index parity
2. 读取并校验 20 个 fixture
3. 执行 G6 Runner 两次并比较 canonical JSON 字节
4. 写入 `reference/build/g6/`
5. 将最小审查 bundle 复制到 `docs/public/reference/g6/`
6. 生成 evaluation、artifact manifest 与 pending review packet

### 4.6 20 条门禁案例矩阵（Agent 的验收测试集）

| 类别 | 数量 | 预期终态 |
|---|---:|---|
| normal | 8 | `needs-approval` |
| missing evidence | 4 | `needs-review` |
| conflicting evidence | 3 | `needs-review` |
| unauthorized action/tool | 3 | `refused` |
| schema/tool fault | 2 | `failed` |

> 「所有案例均为 `LO-S-synthetic`，固定 ID、固定输入、固定输出 hash。评测必须验证 schema、citation、terminal state、tool policy、external calls=0、side effects=0、canonical writes=0 和 deterministic parity。」

---

## 5. 关键设计决策与约束

### 5.1 证据等级与执行权限（两套正交分级）

**证据等级 EvidenceGrade（6 级，`common.schema.json`）**：
```json
["L0-unverified", "L1-public-or-runtime", "LO-S-synthetic",
 "L2-fixture-or-dry-run", "L3-production-read-only", "L4-authorized-live"]
```
> `LO-S-synthetic`（合成数据）单独成级，**不与真实等级混同**——这是"合成数据不能证明业务有效性"的机器化表达。

**执行权限 E-Level（5 级）**：
```json
eLevel:       ["E0","E1","E2","E3","E4"]
publicELevel: ["E0","E1","E2"]     // 公网只允许 E0-E2
```
`TaskPackage.eLevel` 与 `PermissionRule.maxELevel` 都用 `publicELevel`，即**公网部署的 Agent 权限上限被 Schema 硬限制在 E2**（只读+计算+草案），E3/E4 需要另行授权。

**对象生命周期状态**：`["draft","candidate","approved","superseded","blocked"]`
**新鲜度状态**：`["current","due","expired","not-applicable"]`

### 5.2 知识库如何组织

1. **Git-native 权威 + SQLite 运行投影（ADR-002）**：
> 「JSON/YAML/Markdown、稳定 ID、typed relations 和 immutable snapshot 是权威合同。SQLite FTS5、edge table 和预计算向量是可重建运行投影，**不是 canonical source**。」
> 理由：「V1 的主要风险是语义、来源、版本与审批，而不是图查询吞吐。Git diff 与 snapshot hash 更适合审查和复放；SQLite 足以支持有界闭包。」
> 重新评估触发器：「只有出现经测量的对象规模、并发、复杂图算法或恢复时间瓶颈，才评估专用图/向量存储。」

2. **对象类型分层**：
   - **L2-L4 知识对象（7 类 `oneOf`）**：`Concept`（canonicalTerm/aliases/definition/examples）、`Metric`（formula/inputs/unit/window/**failureModes**）、`MentalModel`（trigger/inputs/reasoning/limits/**counterexample**）、`DecisionModel`（inputs/branches/outputs/**unknownPolicy**/stopConditions/reviewState）、`Heuristic`（trigger/recommendation/confidence/exceptions）、`Case`（…/**limitations**/dataClass: synthetic|deidentified-real|authorized-real）、`Playbook`（prerequisites/steps/checks/rollback/approval）
   - **L5 `Skill`**：必填 `inputContract.schemaRef`、`outputContract.schemaRef`、`tools[]`、`steps[]`、`eLevel`、`stopConditions[]`、**`rollback[]`**、**`tests[]`（minItems: 2）**、`promotionDecisionRef`
   - **L6 `TaskPackage`**：见 §4.4

3. **8 类治理对象（`governance.schema.json`）**：

| 类型 | 关键约束 |
|---|---|
| `Policy` | `enforcement: advisory \| blocking` |
| `FreshnessRule` | `maxAgeDays` + `onExpiry: warn \| block-context \| block-task` |
| `PermissionRule` | `maxELevel` + `allowedToolModes: [read, calculate, draft]` + **`externalWrite: const false`** |
| `Ownership` | **`roleRefs` 必须恰好 4 个**（minItems:4, maxItems:4）+ `acceptanceState` |
| `PromotionDecision` | `decision: pending \| approved \| rejected` + `reviewerRoleRefs` |
| `Acceptance` | 必须 4 个 roleRefs + `state: draft \| approval-blocked \| accepted` + **`productionReady: const false`** |
| `Observation` | `category: wrong-source \| stale \| missing-input \| unsafe-recommendation \| schema-error` + **`freeText: const false`** |
| `KnowledgeCandidate` | `proposedType` + `proposal` + **`canonicalWrite: const false`** |

### 5.3 如何保证可追溯（这是本仓库最强的部分）

1. **baseObject 五元组（所有对象强制）**：`id` + `objectType` + `revision` + `status` + `createdAt` + **`sourceRefs[]`**（+ 可选 `supersedes`、`freshness`、`risk`）
2. **sourceLocator（四元组定位到一个字符）**：
```json
{ "sourceRevisionId": "...", "structuralElementId": "...",
  "locator": "...", "contentHash": "sha256:..." }
```
3. **typed relations（`ontology/relations.json`）**：`derived_from` / `supports` / `contradicts` / `requires` / `implements` / `supersedes` / `defines` / `uses_metric` / `validated_by` 等，端点类型受约束
4. **AgentExecutionReceipt 的零副作用计数（全部 `const: 0`）**：
```json
"providerCalls": {"const": 0}, "externalCalls": {"const": 0},
"sideEffects": {"const": 0}, "canonicalWrites": {"const": 0}, "platformWrites": {"const": 0}
```
5. **artifactHashes**：`fixture` / `input` / `plan` / `toolCalls` 四个必填 + `actionPackage` / `approvalDecision` / `refusalReceipt` 条件必填，全部 `^sha256:[a-f0-9]{64}$`
6. **Receipt 的条件互斥（`allOf` + `if/then/not`）**——三种终态互斥且各自必有对应产物：

| 终态 | 必须有 | 必须不能有 |
|---|---|---|
| `needs-approval` / `needs-review` | `approvalRef` + `artifactHashes.actionPackage` + `artifactHashes.approvalDecision` | `refusalRef`、`error`、`artifactHashes.refusalReceipt` |
| `refused` | `refusalRef` + `artifactHashes.refusalReceipt` | `approvalRef`、`error`、`actionPackage`、`approvalDecision` |
| `failed` | `error` | `approvalRef`、`refusalRef`、`approvalDecision`/`refusalReceipt`/`actionPackage` hash |

7. **确定性可复放**：`issuedAt` 被硬编码为 `const: "2026-08-09T00:00:00Z"`，`durationMs: 1` 为常量，`agent.version` 为 `const: "g6-a1-v1"`——**所有时间与版本都是常量，保证两次运行 canonical JSON 字节一致**。
8. **Skill 纠错锚点**（见 §2.7 的 YAML）——向上追溯到 `source_docs` + `knowledge_layer` + `raw_cases`，向下有 `rollback_to`。

### 5.4 如何评估（硬门禁清单）

**G6-A1 验收合同（原文逐条）**：
> - 20/20 case 与分类计数精确通过。
> - 同一 case 两次运行的 canonical JSON 相同。
> - 全部产物通过对应 schema。
> - 每个事实至少一个 evidence ref；**禁止把推断写为事实**。
> - 8 个工具全部在 manifest，所有 `sideEffect=false`。
> - provider/external/platform/canonical writes 全部为 0。
> - unauthorized cases 100% refused；fault cases 100% failed。
> - 20 条 case 中 `completed=0`。
> - Agent Lab 在 1440、960、390px 无横向溢出，键盘可用，Axe 无 critical/serious。
> - 浏览器请求仅访问同源静态资源；**无自由文本、上传与 live 控件**。
> - 完整 content tests、VitePress build 与 `git diff --check` 通过。

**验收注册表机制（`knowledge-system/acceptance.yml`）**——这是"不达标就明确阻断"的机器可读实现。3 份合同（ACC-SECURITY-001 / ACC-COST-001 / ACC-EVALUATION-001）全部为：

```yaml
acceptanceScope: repository-content
productionReady: false
dataset: { kind: synthetic-fixture, authorizationState: synthetic-only,
           authorizationEvidenceRef: null }
thresholds:
  - { metric: passRate,     operator: gte, value: 1, status: illustrative,
      approvalEvidenceRef: null }
  - { metric: externalCalls, operator: eq,  value: 0, status: illustrative }
  - { metric: sideEffects,   operator: eq,  value: 0, status: illustrative }
regression: { maxPassRateDrop: 0 }
ownerRoleRefs: [ROLE-*-CONTENT, ROLE-*-EVIDENCE, ROLE-*-TEST, ROLE-*-APPROVER]
finalReceipt: { state: missing, evidenceRef: null }
declaredState: approval-blocked
declaredDecision: blocked
declaredBlockers:
  - DATASET_NOT_BUSINESS_AUTHORIZED
  - THRESHOLDS_NOT_APPROVED
  - OWNER_ACCEPTANCE_INCOMPLETE
  - FINAL_RECEIPT_MISSING
```

> **「scopeNote（原文）」**：「本注册表只裁决知识页面能否升级为本仓库的可验收内容，不证明生产部署、法律合规、预算批准或真实模型效果。」
> **核心机制**：阈值的 `status: illustrative` + `approvalEvidenceRef: null` 意味着**阈值本身尚未被具名责任人批准**，因此四类阻断项自动生效——**哪怕测试 3/3 通过、回归差异为 0，页面也不能升级到 `acceptance / acceptance-tested`**。这是"证据成熟度 ≠ 部署状态"的强制分离。

**四类具名角色（`roles.json`）**：每个验收目标必须有 CONTENT / EVIDENCE / TEST / APPROVER 四类角色，且必须**具名、独立、可验证**。

### 5.5 五条架构决策记录（ADR）

| ADR | 决策 | 状态 |
|---|---|---|
| **ADR-001** | Guide 与 Reference **独立成熟度账本** | `accepted-design` |
| **ADR-002** | Git-native authority + SQLite runtime projection | `accepted-design` |
| **ADR-003** | **Replay-first 单 E2 Agent** | `accepted-design` |
| **ADR-004** | 公网固定输入、无上传、无自由文本 | `accepted-design` |
| **ADR-005** | **未选择许可证前阻断公开发布** | `proposed-blocking` |

**ADR-001 原文**：
> 「Guide 使用 `principle/solution/runnable/acceptance`；Reference 使用 `draft/replayable/live-candidate/accepted`。两套账本只能通过显式引用关联，**不允许互相继承等级**。」
> 后果：「Reference fixture 通过不改变 26 个 Guide 页面的成熟度。Guide Claim 通过也不允许把 runtime 标为 replayable。」

**ADR-003 原文**：
> 「默认产品证据是不可变 Replay。首版只使用单任务 E2 Agent 和确定性只读/计算工具；live 只作为同一 TaskPackage 的限频对比，**不覆盖 Replay 基线**。」
> 后果：「无 provider key 也必须能复放固定 bundle。模型、prompt、tool、snapshot 和 eval 版本写入 Receipt。**没有任何写工具、消息工具或 canonical promotion 工具。多 Agent 不进入 V1。**」

**ADR 变更流程（原文）**：
> 1. 新决策创建新 ADR，不静默改写已接受 ADR 的结论。
> 2. 替代旧决策时填写 `supersedes`，旧 ADR 改为 `superseded` 但保留。
> 3. 任何提高权限、改变证据语言、开放公网输入或改变权威存储的 ADR 必须由 Owner 重新确认。
> 4. **ADR 接受仅代表设计决策，不代表实现、验收或生产状态。**

### 5.6 其他关键约束

**公网输入合同（ADR-004 / `TaskPackage.publicInput`）**：
```json
{ "freeText": false, "fileUpload": false, "urlInput": false, "allowedParameters": [...] }
```
> 即：公网 Agent **不接受自由文本、不接受文件上传、不接受任意 URL**，只能通过枚举/数值参数调用。

**失败策略（原文）**：
> - fixture schema invalid：`failed`，不执行工具。
> - snapshot/index hash mismatch：整个 build 失败，不生成通过回执。
> - unknown tool：`failed` 或对用户请求返回 `refused`，取决于它是内部 plan fault 还是外部越权请求。
> - evidence missing/conflict：`needs-review`，停止计算精确结论。
> - action write/send request：`refused`，不调用 draft-action。
> - UI export 读取失败：显示本地 artifact error，**不降级到伪造示例**。

**异常优先设计（`10-e2e-pipeline.md` §12.9）**：
> 「**一个只测试 happy path 的 Pipeline，在生产环境里等于没有测试。**」
> 「:::info 核心原则：宁可停下来，不要静默通过。Pipeline 遇到不确定性时，应该**明确告警并等待处理**，而不是用默认值填充。一个静默通过的错误，在知识库里会以最高复用效率扩散；一个及时告警的停滞，只影响当次处理。:::」

异常三级告警：
```python
ALERT_LEVELS = {
    "CRITICAL": "schema_breaking_change | high_risk_field_conflict | >30%_extraction_failure",
    "WARNING":  "schema_additive_change | low_risk_conflict | 10-30%_extraction_failure",
    "INFO":     "first_new_source | fallback_extractor_used | <10%_extraction_failure",
}
```
抽取三层降级：主提取器 → 备用提取器 → 原文保存到人工审核队列，返回 `"never_silent": True`。多源冲突时**高风险字段**（`price` / `compliance_status` / `legal_requirement`）强制 `human_escalate`。

**授权边界（`m1-a-product-contract.md`）**：
> 「本轮只授权本地 P0–P2。`provider-call`、`deploy`、`canonical-write`、`external-send`、`commit`、`push` 和 `package-publish` 均需要新的明确授权。」

**M1-A 明确禁止的声明（原文）**：
> - "多格式编译器已经可运行。"
> - "Amazon Ads 诊断已经被领域专家验证。"
> - "Agent 已调用真实模型或真实平台。"
> - "Reference Lab 已可公开使用或可生产部署。"
> - "核心 Runner 已具备可发布许可证。"

---

## 6. 诚实的边界声明（务必与"已实现"区分）

采用这套方法论时必须分清三层：

1. **方法论层（Guide）**：`docs/knowledge/` 23 章极其详尽、可操作、含大量真实 GitHub 仓库选型与可运行示例。但每章末尾都标注 `maturity: solution` / `verification: pending` / `codeStatus: illustrative`，并统一附「**不能由本章证明什么**」小节。例如第 12 章 §12.9 明确：「最小 mock provider 评估 fixture 已覆盖成功、拒答、解析失败与退化阻断…**它不安装或运行 RAGAS，不调用真实模型，也不证明本章其他片段、业务数据集或阈值已经验收。**」

2. **Reference 层（可运行）**：真正 smoke-tested 的只有 `fixtures/mock-pipeline.mjs`、`fixtures/evaluation-regression.mjs`、G6 `g6-agent.mjs` Runner 与 M1-B pipeline。证据上限 **`L2-fixture-or-dry-run`** / `LO-S-synthetic`（全合成数据）。*「本轮不支持：production/live Agent、真实 provider、真实账户诊断、客户证据、外部平台操作、canonical knowledge 写入或公网 Agent 已发布。」*

3. **未实现**：MCP adapter 尚未实现（「MCP adapter 尚未实现，不作为 UI 运行必需依赖」）；多 Agent 明确排除在 V1 之外；所有 `docs:qa` 里的 g4/g5/g6-a5..a11/g7 脚本引用的文件**已不在仓库中**；许可证未选择（ADR-005 `proposed-blocking`，`license: null`）——**因此按仓库自己的规则，"公开发布"处于被阻断状态**。

**这些边界声明本身就是方法论的一部分**：它示范了"如何诚实地标注证据等级"，比结论更有迁移价值。

---

## 7. 关键原文引用汇总（可粘贴使用）

**关于蒸馏本质**：
> 「蒸馏的本质不是压缩，而是结构化。把"书里说了很多东西"变成"遇到问题 X 时执行 Y，边界是 Z"——这才是 Agent 能用的知识。」

**关于两种加工路线的分工**：
> 「**RAG 提供声明性证据（是什么），Skill 提供程序性指导（怎么做）。最佳实践是两者结合。**」
> 来自 Anything2Skill 论文实验数据：纯 RAG 95.41%（qsv）/ 76.50%（GitHub-CLI）；Anything2Skill + RAG **98.85%（qsv）/ 94.10%（GitHub-CLI）**。

**关于为什么必须分层**：
> 「- **基础层**是"完整性"——确保知识没有遗漏，供检索和人类阅读
> - **Skill 层**是"效率"——把最常用的方法论编译成 Agent 零推理就能执行的指令
> 只有 Skill 层：覆盖率不够，遇到新问题无法处理。只有基础层：每次 Agent 重新推理，速度慢且不稳定。」

**关于 Agent 的定位（全书贯穿概念锚点）**：
> 「**Agent（智能体）是在显式权限、证据与控制边界内选择工具并产生行动的执行单元**；它不是知识真实性的来源。」

**关于 MCP 的定位**：
> 「**MCP（Model Context Protocol）是本指南把受治理知识能力暴露给 Agent 的工具接口边界**；它不替代鉴权、路由、超时或责任治理。」

**关于 Reference 的定位**：
> 「把多格式资料编译为有来源、有关系、有边界、可评测的知识对象，再由 E2 受控 Agent 生成可审查、可批准、可复放的决策行动包。」

**关于为什么不用 MAS**：
> 「MAS 的协调开销（Orchestrator 轮次、上下文传递、边界歧义）在简单任务上会让总成本和延迟放大 3-10 倍，而输出质量不一定更高。」

**关于输出合同（ActionPackage 必须包含）**：
> 1. 任务与输入快照。
> 2. 事实、推断、未知项分栏。
> 3. 诊断假设与证据。
> 4. 决策选项和建议顺序。
> 5. 计算公式、输入、单位与窗口。
> 6. 风险、停止条件和批准要求。
> 7. 证据定位和 freshness。
> 8. Trace、eval、成本和版本。
> **「输入不足时只允许输出公式、区间、未知项和下一证据，不允许伪造精确数值。」**

---

## 8. 如果要落地应用，建议的最小实施顺序

1. **Stage 0 先做**：写 5 个"答错会造成真实业务损失"的问题 + 每个问题的 `failure_consequence` → 得到最小验收门禁（`04-architecture.md`）
2. **半衰期分类**：给现有全部资料打 `<48h / 1周-1月 / 1月-1年 / >1年`，把 <48h 的踢出知识库改成 API 查询（`02-decision-matrix.md`）
3. **输入诊断器**：给待入库资料跑 SKIP / CACHE / PROCESS / ESCALATE 四档路由，先止损再建设（`03-scene-sops.md` 附录）
4. **反蒸馏四禁区对照**：把情境依赖 / 负向知识 / 隐性知识 / 快速迭代知识挑出来，只存原文+指针（`01-framework.md` §1.4）
5. **按输入类型走场景 SOP**：从 `03-scene-sops.md` 选对应场景，照抄该场景的选型表与天坑清单
6. **建 L4 SKILL.md**：用 RIA++ 六段结构（触发条件/执行步骤/边界与禁忌/来源引用，见 §4.1），遵守 3-7-1 Rule，接 `test-prompts.json` 门控
7. **建 `config.yaml` + ingest/storage/retrieval 三段**：直接照抄 `10-e2e-pipeline.md` §12.3–12.7 的代码
8. **接 VTRCE + 三阶段门控**：立项定权重 → 上线前五问 → 30 天检查 → 季度复审（`appendix-validation.md`）
9. **上评分器治理**：如果做自进化，必须先有 9 维评分器 + 独立评委 + 季度校准审计（`11-kb-evolution.md` §11.9）
10. **学 Agent 侧的"少即是多"**：单 Agent + 确定性只读工具 + Replay-first + 四终态 + 零副作用回执，是这套方法论给出的**被冻结验证过的**最小可行 Agent 形态（`g6-a1-replay-first-e2-agent-design.md`）
