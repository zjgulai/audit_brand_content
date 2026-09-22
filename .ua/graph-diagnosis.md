# 图结构诊断（由 knowledge-graph.json 直接算出）

节点 1362 / 边 2657 / 层 12 / 导览 11 步

## 1. 层规模分布

| 层 id | 名称 | 文件级节点 |
|---|---|---|
| `layer:research-findings` | 调研发现与方法论层 | 131 |
| `layer:third-party-references` | 第三方技能库与外部参考资料层 | 123 |
| `layer:ops-scripts` | 运维脚本与一次性迁移/探查工具 | 77 |
| `layer:resource-index-landing` | 飞书资源索引与落地页实测数据层 | 57 |
| `layer:shouheng-daemon` | 守衡守护进程（飞书对外答复运行时） | 32 |
| `layer:verification-harness` | 自证与反向对照层 | 32 |
| `layer:rule-data-contracts` | 规则与契约数据层 | 31 |
| `layer:knowledge-base` | 需求知识库层 | 28 |
| `layer:compliance-engine` | 合规判定引擎（base 契约与骨架运行时） | 27 |
| `layer:foundation-rules` | 基线与约束层（项目宪法与决策记录） | 23 |
| `layer:pmo-operations` | PMO 运营与事故记录层 | 16 |
| `layer:upstream-requirements` | 上游需求与基线层 | 9 |

## 2. 跨层耦合矩阵（行=源层，列=目标层；只列非零）

| 源层 | 目标层 | 边数 | 占源层出边比 |
|---|---|---|---|
| third-party-references | third-party-references ←层内 | 221 | 89.1% |
| research-findings | research-findings ←层内 | 135 | 76.3% |
| pmo-operations | shouheng-daemon | 66 | 50.4% |
| ops-scripts | ops-scripts ←层内 | 63 | 75.9% |
| knowledge-base | knowledge-base ←层内 | 54 | 85.7% |
| shouheng-daemon | shouheng-daemon ←层内 | 53 | 100.0% |
| foundation-rules | foundation-rules ←层内 | 52 | 33.8% |
| rule-data-contracts | rule-data-contracts ←层内 | 50 | 56.8% |
| compliance-engine | compliance-engine ←层内 | 41 | 65.1% |
| resource-index-landing | resource-index-landing ←层内 | 29 | 58.0% |
| foundation-rules | research-findings | 26 | 16.9% |
| foundation-rules | compliance-engine | 24 | 15.6% |
| upstream-requirements | upstream-requirements ←层内 | 22 | 44.0% |
| ops-scripts | research-findings | 19 | 22.9% |
| pmo-operations | verification-harness | 16 | 12.2% |
| rule-data-contracts | compliance-engine | 16 | 18.2% |
| foundation-rules | verification-harness | 14 | 9.1% |
| verification-harness | ops-scripts | 14 | 50.0% |
| compliance-engine | rule-data-contracts | 13 | 20.6% |
| foundation-rules | rule-data-contracts | 12 | 7.8% |
| pmo-operations | pmo-operations ←层内 | 12 | 9.2% |
| research-findings | verification-harness | 12 | 6.8% |
| research-findings | foundation-rules | 12 | 6.8% |
| rule-data-contracts | ops-scripts | 12 | 13.6% |
| research-findings | third-party-references | 11 | 6.2% |

层内边 737 / 跨层边 451 → 层内占比 62.0%

## 3. 枢纽节点（文件级，按出入度）

| 节点 | 层 | 出度 | 入度 | 总度 |
|---|---|---|---|---|
| `file:tools/agent/feishu.mjs` | shouheng-daemon | 35 | 18 | 53 |
| `file:tools/feishu_index.py` | ops-scripts | 45 | 7 | 52 |
| `file:tools/ws_daemon.mjs` | shouheng-daemon | 37 | 11 | 48 |
| `file:research/governance/skeleton/judge.py` | compliance-engine | 40 | 4 | 44 |
| `file:research/governance/audit_citation_fidelity.py` | verification-harness | 43 | 0 | 43 |
| `file:tools/agent/agent.mjs` | shouheng-daemon | 32 | 8 | 40 |
| `file:research/governance/skeleton/score.py` | compliance-engine | 28 | 11 | 39 |
| `file:tools/agent/prd_baseline.mjs` | shouheng-daemon | 33 | 6 | 39 |
| `document:ADR/ADR-0013-基座接口冻结与仓库入库分级.md` | foundation-rules | 27 | 7 | 34 |
| `file:tools/kb_query.py` | knowledge-base | 31 | 3 | 34 |
| `file:research/governance/skeleton/engine_manifest.py` | compliance-engine | 29 | 4 | 33 |
| `file:base/media.py` | compliance-engine | 30 | 3 | 33 |
| `document:kb2agent-research/raw/E-守衡落地建议.md` | third-party-references | 27 | 3 | 30 |
| `file:tools/reply-cards/cards.mjs` | shouheng-daemon | 26 | 2 | 28 |
| `file:base/contract.py` | compliance-engine | 22 | 6 | 28 |
| `document:PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md` | pmo-operations | 24 | 4 | 28 |
| `document:PRD/PRD差异对照-20260921.md` | upstream-requirements | 21 | 7 | 28 |
| `document:research/governance/README.md` | foundation-rules | 22 | 5 | 27 |
| `document:research/governance/R5-category-and-competitors.md` | research-findings | 5 | 22 | 27 |
| `file:tools/offline_replay.py` | verification-harness | 20 | 7 | 27 |

## 4. 孤立节点

零边节点 113 / 1362（8.3%）

按类型：document=94 · config=11 · file=6 · table=2

文件级孤立节点（前 30）：

- `document:research/distill/scratch/_t1.md` — Markdown 解析探针的最小正例：一个一级标题加一行正文，用来确认标题抽取与段落切分能跑通，不含项目内容。
- `document:research/distill/scratch/_t2.md` — Markdown 解析探针：验证含中点分隔符「·」与英文词的标题能被完整抽取，标题文本与 S1 分片主标题前半段同形。
- `document:research/distill/scratch/_t3.md` — Markdown 解析探针：全文只有一行引用块，且没有标题 —— 用来确认扫描器在「零 section」时不会伪造标题、也不报错。
- `document:research/distill/scratch/_t4.md` — Markdown 解析探针：一行带中点与全角括号的中文一级标题，用来确认 CJK 标题在无正文时仍被登记为一个 section。
- `document:research/distill/scratch/_t5.md` — Markdown 解析探针：两行连续引用块，内容是 S1 分片的出处声明（快照抓取日期与行号口径），用来确认多行 blockquote 被合并成一段而不是切成两
- `document:research/distill/scratch/_t6.md` — Markdown 解析探针：一行纯中文字符串，无标题、无标记 —— 确认非 ASCII 正文不会被判成空文件。
- `document:research/distill/scratch/_t7.md` — Markdown 解析探针：中文标题加全角括号「中文标题（测试）」，用来确认中文标题的括号与标点不被当成语法标记截断。
- `document:research/distill/scratch/_t8.md` — Markdown 解析探针：与 _t4.md 几乎同形，但中点写成半角连字符（「S1 - ad-review-agent」），是「·」被 ASCII 化时的对照
- `document:research/distill/scratch/_t9.md` — Markdown 解析探针：一行引用块，内容是字节级转义串而非中文字符 —— 生成它的时候非 ASCII 被写成了字面量，所以它测的是「转义文本」而不是原意要测
- `document:research/feishu/README.md#一页纸现状` — README 的读数表，被 <!-- facts:begin --> 注释包裹，集中列出本轮实扫的 12 个关键读数（454 条候选、25 条本租户、24/25
- `document:research/feishu/README.md#三件必须说清楚的事` — README 的核心纠偏段：①「能看见」远大于「它自己的」（云盘 2 个文件 vs 搜索命中 455 条，只看云盘会漏 99%）；②「能看见」又远大于「是我们的
- `document:research/feishu/可达清单.md#0-先说清楚-25-是怎么来的` — 对「25」这个数的交代：40 词搜索矩阵扫出 455 条，但 drive/v1/metas/batch_query 对每条回一个 url、域名就是它挂在哪个租户
- `document:research/feishu/可达清单.md#1-处理方式口径` — 六档处理记号的定义表：🟢 接入（抽正文→结构化→入知识库，是运行输入）、🟡 订阅（登记为发布后监测对象，不进知识库）、🔵 登记（只记录存在与用途）、⚪ 不
- `document:research/feishu/可达清单.md#2-项目自有-5-条` — MINE 白名单里的 5 条资产逐条展开，是「我们可以改、可以依赖、可以对外承诺」的部分：需求框架整理（业务源头需求书，10 个待评估能力 + EDM/US 官
- `document:research/feishu/可达清单.md#3-在跑的内容生产项目-7-条` — 待审内容的直接来源，逐条给出预算/交付/形态并分派处理：BD002 折叠床 TVC（视频类，正好用作打样）、BW04 社媒需求（文案+图片素材，已出现需证据支撑
- `document:research/feishu/可达清单.md#4-产品事实依据-2-条` — 规则要引用的证据库：全球产品小百科（9 张品类表 / 96 条，字段逐参数展开：Max Suction、Suction Levels、Working Sound
- `document:research/feishu/可达清单.md#5-运营-需求侧参考-3-条` — 只登记不接入的三条，每条都写明了「以后可能怎么用」：亚马逊运营 SOP（问题定位→适用条件/操作路径/风险点/完成标准，可作为审核清单的结构参考）、AAA 外部
- `document:research/feishu/可达清单.md#6-公司通用-与内容合规无关-8-条` — 诚实列出 8 条本公司租户内但与内容合规无关的资源（行政服务指南、行政差旅/会议室 Q&A、IT 知识库、被搬进本租户的飞书帮助中心内容、EPROS 审批 SO
- `document:research/feishu/可达清单.md#7-群与聊天记录` — 唯一能进的群「内容治理-守衡Agent-测试」（3 人、78 条可见消息、已翻到底非截断），并指出这 78 条讲的是联调过程本身而不是业务内容；从中留档三条运维
- `document:research/feishu/可达清单.md#8-缺口` — 把「拿不到」拆成两类而不是一张表：一类是权限/范围不够（通讯录人名已解、Wiki 0 个空间、更多群可争取），另一类是接口根本不存在（幻灯片正文、思维笔记正文、
- `document:research/feishu/可达清单.md#9-一页纸-我会怎么处理这-25-条` — 收口汇总：🟢 接入 7 条 + 🟡 订阅 4 条 + 🔵 只登记 5 条 + ⚪ 不接 8 条 + ⛔ 红线不取 1 条 + 🔴 待解 0 条 = 25
- `document:research/feishu/资源索引.md#一-先说清楚-可达-是什么意思` — 索引的口径起点：实测到一个与直觉相反的事实并据此定下整份索引的读法——守衡云盘里它自己的文件只有 2 个，而搜索接口能命中 454 条，其中真正挂在本公司租户下
- `document:research/feishu/资源索引.md#二-一页纸现状` — 生成版的读数表（454 条候选 → core 25 / reference 28 / noise 401，可读性 454/454，本租户抽到正文 24/25），
- `document:research/feishu/资源索引.md#三-本公司租户层-core` — 25 条本租户资源的逐条明细，每条给出 token、形态、revision、命中搜索词、正文字数与多维表格逐表结构（表名/字段数/记录数/table_id）及字
- `document:research/feishu/资源索引.md#四-参考层` — 28 条「别人家/官方的、话题沾边的」资源表格（标题/形态/域名/rev/命中词），明确这层不抽正文，并断言这层里本公司租户的条数为 0——本租户的全部 25 
- `document:research/feishu/资源索引.md#五-噪音层` — 401 条噪音只给聚合读数（多维表格 246 / 云文档 65 / 电子表格 50 / 幻灯片 37 / 思维笔记 3），并说明理由是「全部列为正文会让索引不可
- `document:research/feishu/资源索引.md#六-群与聊天记录-链接` — 两条聚合读数：能进的群 1 个（内容治理-守衡Agent-测试，group 模式、非外部群、可见消息 78 条），从群消息与核心层正文里抽出链接 9 条（来源标
- `document:research/feishu/资源索引.md#七-怎么用` — 给生成物的使用方式：三条重扫命令（全量重扫 / --check 只比对、退出码非 0 表示过期 / --no-extent 跳正文抽取），外加两条内联 Pyth
- `document:research/feishu/资源索引.md#八-诚实状态表` — 逐条列出索引的未知边界：40 词搜索的并集不保证是全集（换词就换结果）、owner 是查得到 19 个而查不到 3 个、守衡不在任何 Wiki 知识库成员里、只
- `document:research/feishu/资源索引.md#九-权限与能力缺口` — 权限与能力的逐面现状表（通讯录接口/数据范围/姓名字段已通，部门名未授，Wiki 0 空间，群只有 1 个，附件按红线不下载，幻灯片与思维笔记接口不存在，卡片交

## 5. 文档子图形态

文档节点 304，其中有任何边的 210（69.1%）
零边文档 94

被引用最多的文档（入度 Top 12）：

- 22 ← 入度  `document:research/governance/R5-category-and-competitors.md`
- 15 ← 入度  `document:research/governance/annotations/ANN-GUIDE-001-T1.4-T2.1.2.md`
- 15 ← 入度  `document:skills-inventory/refs/ecommerce-image/ecommerce-image/references/image-quality.md`
- 12 ← 入度  `document:PRD/内容治理需求文档.md`
- 11 ← 入度  `document:research/distill/shards/S1-ad-review-agent.md`
- 11 ← 入度  `document:research/governance/01-内部证据-规则表现状审计.md`
- 9 ← 入度  `document:ADR/ADR-0002-记录级溯源与版本化.md`
- 9 ← 入度  `document:ADR/ADR-0005-工具只补证据不替人过门.md`
- 8 ← 入度  `document:research/distill/cross-cutting-findings.md`
- 7 ← 入度  `document:ADR/ADR-0001-数据权威与双账本.md`
- 7 ← 入度  `document:ADR/ADR-0012-判定引擎产品化与处置分层.md`
- 7 ← 入度  `document:ADR/ADR-0013-基座接口冻结与仓库入库分级.md`

出度最高（引用别人最多）的文档 Top 12：

- 27 → 出度  `document:ADR/ADR-0013-基座接口冻结与仓库入库分级.md`
- 27 → 出度  `document:kb2agent-research/raw/E-守衡落地建议.md`
- 24 → 出度  `document:PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md`
- 22 → 出度  `document:research/governance/README.md`
- 21 → 出度  `document:PRD/PRD差异对照-20260921.md`
- 19 → 出度  `document:ADR/ADR-0012-判定引擎产品化与处置分层.md`
- 17 → 出度  `document:skills-inventory/refs/ecommerce-image/ecommerce-image/references/category-playbook.md`
- 15 → 出度  `document:research/governance/_shards/R8-W3-errorbook-severity-gaps.md`
- 14 → 出度  `document:ADR/README.md`
- 13 → 出度  `document:research/kb/README.md`
- 12 → 出度  `document:PMO/守衡-架构说明.md`
- 12 → 出度  `document:PMO/守衡-知识库GAP分析与第一性原理决策-20260922.md`

## 6. 函数/类在各文件的分布（Top 20，找上帝模块）

| 文件 | 函数/类节点数 |
|---|---|
| `base/media.py` | 28 |
| `research/governance/audit_citation_fidelity.py` | 25 |
| `base/contract.py` | 22 |
| `tools/feishu_index.py` | 22 |
| `tools/lp_stability.py` | 19 |
| `research/governance/skeleton/judge.py` | 18 |
| `research/governance/skeleton/score.py` | 18 |
| `tools/agent/feishu.mjs` | 17 |
| `tools/agent/prd_baseline.mjs` | 15 |
| `research/kb/load.py` | 14 |
| `tools/kb_query.py` | 14 |
| `tools/reply-cards/cards.mjs` | 13 |
| `base/sync_rules.py` | 13 |
| `tools/_recon_legacy.py` | 13 |
| `tools/verify_external.py` | 13 |
| `tools/verify_shouheng_ops.py` | 13 |
| `research/governance/skeleton/engine_manifest.py` | 12 |
| `base/text_stage.py` | 12 |
| `research/governance/audit_migration_fidelity.py` | 11 |
| `tools/verify_pending.py` | 11 |

## 7. 各层的边类型构成（诊断「层之间靠什么连」）

- **基线与约束层（项目宪法与决策记录）**：documents=160 · depends_on=20 · related=3 · defines_schema=2
- **合规判定引擎（base 契约与骨架运行时）**：contains=184 · exports=63 · documents=56 · depends_on=27 · imports=14
- **规则与契约数据层**：documents=43 · depends_on=41 · related=27 · contains=15 · configures=9
- **守衡守护进程（飞书对外答复运行时）**：contains=132 · exports=105 · documents=71 · calls=43 · imports=32
- **自证与反向对照层**：contains=202 · exports=122 · documents=40 · depends_on=26 · related=5
- **运维脚本与一次性迁移/探查工具**：contains=198 · exports=93 · documents=50 · depends_on=40 · related=28
- **上游需求与基线层**：documents=30 · depends_on=24 · related=13 · configures=2 · contains=2
- **PMO 运营与事故记录层**：documents=115 · depends_on=19 · related=5 · configures=2
- **调研发现与方法论层**：documents=117 · related=98 · depends_on=12 · contains=6 · defines_schema=1
- **需求知识库层**：contains=65 · exports=65 · related=30 · documents=25 · depends_on=25
- **飞书资源索引与落地页实测数据层**：documents=27 · depends_on=19 · contains=6 · related=3 · configures=3
- **第三方技能库与外部参考资料层**：related=126 · documents=116 · contains=19 · exports=19 · depends_on=13
