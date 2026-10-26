# audit_multi_content · 内容合规审查 + 守衡飞书机器人

> 这份文件**不是项目简介**，是**入口**。判断标准只有一个：
> 从它出发，能不能走到仓里每一份该被读到的文档。
> 这条有执行点：`python3 tools/verify_doc_reachability.py`（口径与断言写在文件头）。

在这个仓里干活的 agent，**先读 `AGENTS.md`** —— 它是本项目的宪法，
优先级高于任何单次会话的默认行为。本文件负责「东西在哪」，`AGENTS.md` 负责「怎么干」。

```
git ls-files -z | tr '\0' '\n' | grep -c .                      # 497  已入库文件（2026-09-22 15:0x 读数）
git ls-files -z | tr '\0' '\n' | grep -cE '\.(md|mdx|rst|txt)$' # 238  其中文档
```

> 这两个数**会动**（本轮就一直在动：同一分钟内另一个会话连着提交了三次）。
> 所以它们是「读数」不是「常量」—— 要引用就自己跑一遍上面两条命令。

> ⚠️ **取这两个数必须带 `-z`。** 不带时 git 会把含中文的路径转义成
> `"PMO/\344\270\212..."`，任何 `\.md$` 过滤都会静默漏掉它们 ——
> 实测同一时刻「不带 `-z` 得 160 / 带 `-z` 得 226」，差的 66 份全是中文名。
> 一个「看起来扫完了」的过滤器，和一个真扫完了的过滤器，读数不一样但长得一样。

---

## 一、三份必读

| 文件 | 为什么 |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | 项目宪法：改代码前先跑自证、文档里的数字必须算出来、上限必须有执行点、红线、重启守衡的闸门 |
| [`ADR/README.md`](./ADR/README.md) | 决策台账。14 份 ADR 的索引与决策地图（`git ls-files -z \| tr '\0' '\n' \| grep -cE '^ADR/ADR-'`） |
| [`tools/verifier-coverage.json`](./tools/verifier-coverage.json) | 「谁验什么」的机器可读登记表 —— 每个 `verify_*` 各自覆盖哪些文件（名册由 `python3 tools/verify_coverage.py` 反证） |

---

## 二、目录地图

### 决策 · `ADR/`

[`ADR/README.md`](./ADR/README.md) 是唯一入口（台账表 + mermaid 决策地图）。
按 ADR-0013 定的**仓库三层分级**（L1 入历史 / L2 入盘不入历史 / L3 永不入盘）看制品归属，
那份 ADR 同时是分级规则本身：`ADR/ADR-0013-基座接口冻结与仓库入库分级.md`。

### 委托与产品 · `PRD/`

| 文件 | 是什么 |
|---|---|
| [`PRD/内容治理需求文档.md`](./PRD/内容治理需求文档.md) | 委托方需求原文（本地证据的源头之一） |
| [`PRD/内容治理-TUI产品提案.md`](./PRD/内容治理-TUI产品提案.md) | 产品提案 |
| [`PRD/PRD差异对照-20260921.md`](./PRD/PRD差异对照-20260921.md) | 上游两版 PRD 的逐条差异 |
| [`PRD/feishu/README.md`](./PRD/feishu/README.md) | **上游飞书文档的本地副本**：指纹、重拉步骤、落盘配方 |
| [`PRD/feishu/索引-v1.json`](./PRD/feishu/索引-v1.json) | 上游基线指纹（被 `tools/verify_prd_baseline.py` 消费） |

### 守衡（飞书机器人）· `PMO/`

守衡在飞书群里替我们答话。它的**架构、规程、事故记录**都在这里。
`AGENTS.md` §2.2 把事故记录当作「别再踩的坑」的唯一存档，所以它们必须走得到：

| 文件 | 事故 / 内容 |
|---|---|
| [`PMO/守衡-架构说明.md`](./PMO/守衡-架构说明.md) | 链路与服务结构 |
| [`PMO/守衡-链路打通确认.md`](./PMO/守衡-链路打通确认.md) | 「界面上看得见 ≠ 已经生效」那条教训的原始记录 |
| [`PMO/守衡-飞书打通测试报告.md`](./PMO/守衡-飞书打通测试报告.md) | 打通实测 |
| [`PMO/守衡-回复卡片模版与语域规程.md`](./PMO/守衡-回复卡片模版与语域规程.md) | 卡片模版与语域（本文件与 `tools/reply-cards/` 必须一致） |
| [`PMO/守衡-发送者身份修复记录.md`](./PMO/守衡-发送者身份修复记录.md) | 群历史发送者身份丢失 |
| [`PMO/守衡-回复截断修复记录.md`](./PMO/守衡-回复截断修复记录.md) | 回复被截断 |
| [`PMO/守衡-时间基准修复记录.md`](./PMO/守衡-时间基准修复记录.md) | 报错的时间基准 |
| [`PMO/守衡-查名修复记录.md`](./PMO/守衡-查名修复记录.md) | 「查不到谁在说话」 |
| [`PMO/守衡-看不见的东西要说出来.md`](./PMO/守衡-看不见的东西要说出来.md) | 它看到的群历史比它以为的还残缺 |
| [`PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md`](./PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md) | 讨论稿（不是 ADR，不改代码） |

另外两份在库里：[`PMO/内容合规-阶段性复盘-20260916.md`](./PMO/内容合规-阶段性复盘-20260916.md)、
[`PMO/上游对接人表.md`](./PMO/上游对接人表.md)；待收承诺登记在
[`PMO/待收清单-v1.json`](./PMO/待收清单-v1.json)（由 `python3 tools/verify_pending.py` 验）。

### 知识库与工作流 · 2026-10-21 深度分析

[`PMO/内容审查Agent-知识库与工作流-深度分析-20261021.md`](./PMO/内容审查Agent-知识库与工作流-深度分析-20261021.md)
—— 回答委托方六个存疑点（负面样本 / 品牌一致性 / KB 调用 / 文件类型工作流 / 模型选型 / intent-skill）。
**先读它再动知识库那一侧**：它记录了三件反直觉的事实 ——
① 判定只吃 26 条规则，而分类基准有 638 条，其余四套库一条判决都影响不了；
② 品牌禁用词是「AIGC 提示词约束」，实测直接接进引擎会有 6–10% 误报（KB-GAP-21）；
③ 样本表是「设计审核群的聊天转录」，不是判例库（KB-GAP-19）。

> `PMO/` 下还有若干**本轮新写、尚未入库**的登记件
> （`PMO/守衡-上游第三版基线与影响登记-20260922.md`、`PMO/守衡-假否定登记-20260922.md`、
> `PMO/守衡-内容推送与被at登记-20260915至0922.md`、`PMO/守衡-回话草稿-M12材料逐条状态-20260922.md`、
> `PMO/守衡-知识库GAP分析与第一性原理决策-20260922.md`、`PMO/守衡-知识库构建完整方案-20260922.md`、
> **`PMO/守衡-知识库建设整体方案-PRD骨架-20260923.md`**、**`PMO/守衡-Utopia结合方案-20260923.md`**）。
> 它们不在本 README 的**可达性口径**内 —— 那个口径只算已入库文件。列出来用 `git status --porcelain PMO/`。
>
> ★ **后两份是一对**，读的时候别只读一半：
> 《知识库建设整体方案》是**骨架层**（以 PRD v1.2 的 S1–S5 五层为轴，把 D1–D6 与 T1–T16 挂进去），
> 《Utopia 结合方案》是**它的技术判断来源**（为什么只借设计不部署、移植哪三条、不移植哪四条）。
> 两份关系与「判据只有一处」的纪律写在骨架那份的 §〇。

### 调研与证据 · `research/`

| 入口 | 覆盖什么 |
|---|---|
| [`research/governance/README.md`](./research/governance/README.md) | **规则库搭建与自迭代**总索引：内部证据 01–05、外部一手调研 R1–R8、可执行骨架 `skeleton/`、错题本 `errorbook/`、主交付物《审核规则库完整设计》 |
| [`research/kb/README.md`](./research/kb/README.md) | **需求知识库**：文件地图 + 10 条黄金问题（每条配可复现命令） |
| [`research/feishu/README.md`](./research/feishu/README.md) | 守衡在飞书里**能拿到什么**（资源索引 / 可达清单） |
| [`research/landing/README.md`](./research/landing/README.md) | 落地页内容获取实测（批次 C） |
| [`research/landing/momcozy-高风险图片检查清单-20260924.md`](./research/landing/momcozy-高风险图片检查清单-20260924.md) | momcozy.com 官网图片高风险初筛清单（2026-09-24，含 11 张证据图；来历与边界写在文首） |
| [`research/method/调研报告-AI产品全流程方法与Kb2Agent编译链.md`](./research/method/调研报告-AI产品全流程方法与Kb2Agent编译链.md) | 知识工程调研报告（同目录另有 `Kb2Agent-方法论提炼.md`、`codex_research-方法论提炼.md`） |
| [`research/distill/00-写作规范.md`](./research/distill/00-写作规范.md) → [`01-大纲.md`](./research/distill/01-大纲.md) → [`cross-cutting-findings.md`](./research/distill/cross-cutting-findings.md) | 竞品仓库拆解：写作规范 → 大纲 → 跨分片发现；分片在 `research/distill/shards/` |
| [`research/replay/离线复现报告-20260916.md`](./research/replay/离线复现报告-20260916.md) | 离线复现报告 |
| [`research/star-lists-audit-report.md`](./research/star-lists-audit-report.md) | star 清单审计 |
| [`research/utopia/数据模型与规则机制.md`](./research/utopia/数据模型与规则机制.md) → [`运营面与接入成本.md`](./research/utopia/运营面与接入成本.md) | **`deeplethe/utopia` 的只读剖析**（v0.1.0，`dev@ef6495c`）：前者是数据模型 / 双时态 / 溯源链 / 推理与治理，后者是数据源 / 检索 / API / MCP / 部署 / 接入成本。**每条断言带 `文件:行`**；凡文档写着而代码里没有的单独标出。结论落在 `PMO/守衡-Utopia结合方案-20260923.md` |

**不要求逐份挂入口的四类**（判据、份数、以及「这一类里到底有几份其实是有入边的」，
都由 `python3 tools/verify_doc_reachability.py` 的分项表实时算出来，别从这份 README 抄数）：

| 类 | 哪些 | 为什么 |
|---|---|---|
| `VENDORED_THIRD_PARTY` | `skills-inventory/refs/` | 第三方技能原文的逐字节留档（许可状态见 `refs/README.md`） |
| `EXTERNAL_SNAPSHOT` | `research/readmes/`、`x-recovery/` | **别人的文字**的逐字快照（别家产品 README、X 上一条帖子）。改它们等于篡改证据 |
| `RAW_MATERIAL` | `kb2agent-research/raw/` | 调研原始件（目录名就是 `raw`），成品是同目录的两份报告 |
| `SCRATCH` | `research/distill/scratch/`、`research/governance/_scratch/`、下划线开头的文件 | 草稿/探针，不承诺被引用 |

> ⚠️ **`RAW_MATERIAL` 这一类的成色要看那条分项读数**：该类 18 份里 15 份**是有入边的**
> （报告正文按件引用 raw 原件），剩下 3 份不可达 —— 那不是「本来就不该有入口」，
> 是**引用写法漏了**（报告里写的是 `B-part1..3.md` 这种**区间**写法，区间不解析成具体路径）。
> 详见交付报告里的「剩下的不可达」一节。

### 工程与自证 · `tools/`

[`tools/README.md`](./tools/README.md) 是 `tools/` 的工具索引（一行一个：什么时候用它、产物落哪，
含那些零引用的诊断探针）；各子系统自证入口仍在第三节，那才是真入口。

| 文件 | 是什么 |
|---|---|
| [`tools/reply-cards/README.md`](./tools/reply-cards/README.md) · [`tools/reply-cards/contract.md`](./tools/reply-cards/contract.md) | 飞书卡片元素白名单（**实测**出来的，不是从文档抄的） |
| [`tools/verifier-coverage.json`](./tools/verifier-coverage.json) | 覆盖登记表 |
| `tools/verify_*.py` · `verify_*.mjs` | 各子系统自证（第三节的表） |
| `tools/ws_daemon.mjs` | 守衡守护进程（形态决策只在它的 `replyTo` 里做） |
| `tools/restart_shouheng.sh` | **重启闸门：默认拒绝。** 用法见 `AGENTS.md` §2.7，别绕过 |

### 自有规程 vs 第三方技能

| 什么 | 放哪 | 入库 |
|---|---|---|
| **本项目自有的规程** | [`agent-skills/内容合规审查/SKILL.md`](./agent-skills/内容合规审查/SKILL.md)（判定引擎那套规程，`python3 tools/verify_skill.py` 验的就是它）· [`agent-skills/守衡语域/SKILL.md`](./agent-skills/守衡语域/SKILL.md) | ✅ |
| 第三方技能库与克隆 | `skills/` | ❌ **被忽略** |

`skills/` 为什么被忽略：`.gitignore` 第 39 行就是它（`sed -n '39p' .gitignore`），
注释写明是「第三方技能库与克隆（各自有自己的 `.git`）」。该目录下实有
`find skills -name 'SKILL.md' | wc -l` 个 `SKILL.md`。
**把自有规程写进 `skills/` 的后果是：`git status` 一片干净，看起来像什么都没发生，
实际上它不会进版本库。** 拦住这件事的是 `node tools/verify_cards.mjs` 的 H 段。
盘点结果在 [`skills-inventory/SKILLS-INVENTORY.md`](./skills-inventory/SKILLS-INVENTORY.md)；
第三方原文留档在 `skills-inventory/refs/`，入口是它自己的
[`refs/README.md`](./skills-inventory/refs/README.md)（留档目录 → 仓内原始路径 → 许可状态）。

### 其它

| 入口 | 内容 |
|---|---|
| [`base/README.md`](./base/README.md) | 基座：`ContentUnit` 契约 + `judge(unit)` 适配层 |
| [`.ua/README.md`](./.ua/README.md) | **2026-09-22 结构性诊断**（TOP20 的来源）：10 份正文 + 9 条复现入口，以及「哪些在库里、哪些只在盘上」的分级 |
| [`kb2agent-research/企业Agent知识库体系调研报告.md`](./kb2agent-research/企业Agent知识库体系调研报告.md) | 企业 Agent 知识库体系调研 |
| [`kb2agent-research/Kb2Agent-方法论调研报告.md`](./kb2agent-research/Kb2Agent-方法论调研报告.md) | Kb2Agent 方法论调研 |

---

## 二·补、第 1 阶段文档索引（2026-10-19）

> 这些文档此前没有入边（`verify_doc_reachability.py` 的未归类清单）。本索引是它们的入口；
> 新增第一方文档时，先把它登记到这里，再跑一次可达性自证。
> `PMO/audit/momcozy-assets/` 是采集/训练资产包（89 份），入口是它自己的总索引，不逐份列。
>
> 2026-10-21 的 7 份无入边文档（规则归类/披露重抽/gold 试点/skill 定性）：
> [`PMO/implement/索引-20261021.md`](./PMO/implement/索引-20261021.md)。
>
> 2026-10-22 的上线就绪度盘点（六维审计 + 红队 + 最终 ticket 表）：
> [`PMO/上线Ticket清单-20261022.md`](./PMO/上线Ticket清单-20261022.md)（**唯一权威清单**）、
> [`PMO/上线前深度盘点-20261022.md`](./PMO/上线前深度盘点-20261022.md)（推理过程与我的错误记录）、
> [`PMO/并行会话分工-20261022.md`](./PMO/并行会话分工-20261022.md)（按链路环节重编的分工）。
> ★ 三份同一单元的产出。清单那份 §一 记着**红队推翻了合并清单的四处**，
> 而盘点那份 §一 记着我**否掉了自己发起的一轮投票**（守衡不是产品，是协作助手）。
>
> 2026-10-23 的 8 份无入边文档（裁定 / 证据包 / 审计报告 / 取证）：
> [`PMO/audit/裁定-R118-媒体宿主原生-20261023.md`](./PMO/audit/裁定-R118-媒体宿主原生-20261023.md)
> —— 裁定「宿主原生 OCR 不在生产路径上，所以行 118 今天是**空真**，不是已满足」；
> [`PMO/audit/授权记录-CI工作流入库-20261023.md`](./PMO/audit/授权记录-CI工作流入库-20261023.md)
> —— `.github/workflows/acceptance.yml` 入库的授权与边界（**不构成对外部 Action 的长期安全承诺**）；
> [`PMO/audit/语义BLOCK-证据包-20261023.md`](./PMO/audit/语义BLOCK-证据包-20261023.md)
> —— 行 121 的三方原文对拍 + `machine_finalizable` 六通道普查，**不含裁定**；
> [`PMO/audit/R118-容器半边-取证-20261023.md`](./PMO/audit/R118-容器半边-取证-20261023.md)
> —— 行 118 容器半边的四通道取证（结论：环境/构建是暂时缺、数据/适配是结构性缺）；
> [`PMO/audit/T240-ea交付声明自我审计报告-20261023.md`](./PMO/audit/T240-ea交付声明自我审计报告-20261023.md)
> —— ea 对自己 24 小时交付声明的 A/B/C/D 四分类回查（6 条 D 类 + 4 条 C 类）；
> [`PMO/audit/Web页面UIUX审计与12页全量优化方案-v1-20261022.md`](./PMO/audit/Web页面UIUX审计与12页全量优化方案-v1-20261022.md)
> —— 12 页工作台的审计与改造方案（Wave A–E）；
> [`PMO/implement/T-140-验收执行门定性-20261022.md`](./PMO/implement/T-140-验收执行门定性-20261022.md)
> —— 验收执行门 28 条待建的定性表；
> [`PMO/implement/交接-飞书三表建成-20261026.md`](./PMO/implement/交接-飞书三表建成-20261026.md)
> —— 飞书三表的建成记录与平台限制结论（另一会话产出，本次补登入口）；
> [`PMO/主线优先级与并行拆分-20261022.md`](./PMO/主线优先级与并行拆分-20261022.md)
> —— 按链路环节重排的主线优先级。
> ★ 这几份的共同点：**它们是「判断的记录」，不是「成果的说明」** ——
> 读它们是为了知道**当时凭什么这么定**，以及**哪些结论后来被推翻了**。
>
> 2026-10-24 的 9 份（7 份读数审计报告 + 1 份交付执行规格 + 1 份票清单）：
> [`PMO/audit/T111-styles裸值取证与可复算基线-20261023.md`](./PMO/audit/T111-styles裸值取证与可复算基线-20261023.md)
> —— 设计 Token 裸值 103→95 的逐条取证与可复算基线；
> [`PMO/audit/前端校验三个假绿形状-20261024.md`](./PMO/audit/前端校验三个假绿形状-20261024.md)
> —— `awaitPromise` 默认 false / `rem` 基数 13px / `Page.navigate` 丢内存态：三条恒真断言的识别特征；
> [`PMO/audit/变异探针审计-剩余42行-20261023.md`](./PMO/audit/变异探针审计-剩余42行-20261023.md)
> —— 首次全表覆盖：映射里 42 行逐行有 killed 变异，41 条 survived 是子条款缺口；
> [`PMO/audit/审计-verify_decision_table-16行-20261023.md`](./PMO/audit/审计-verify_decision_table-16行-20261023.md)
> —— 16 行里只有 4 行是行为覆盖的逐条依据；
> [`PMO/audit/覆盖率审计-剩余10组fanout-33行-20261023.md`](./PMO/audit/覆盖率审计-剩余10组fanout-33行-20261023.md)
> —— fan-out 把一次绿记到整组的证据，以及 30 行回退的判据；
> [`PMO/audit/验收读数审计-report与metrics共15行-20261023.md`](./PMO/audit/验收读数审计-report与metrics共15行-20261023.md)
> —— 报告渲染与指标读模型 15 行的假绿清单；
> [`PMO/implement/覆盖率审计-release_gate-与-normalizer-20261023.md`](./PMO/implement/覆盖率审计-release_gate-与-normalizer-20261023.md)
> —— `release_gate` 与 `normalizer` 两组的行为覆盖缺口；
> [`PMO/implement/内容审核工作台-交付执行计划-v1-20261024.md`](./PMO/implement/内容审核工作台-交付执行计划-v1-20261024.md)
> —— **P0–P4 四阶段、阶段门、DoD 七条、止损条件**（主规格）；
> [`PMO/implement/执行票清单-v1-20261024.md`](./PMO/implement/执行票清单-v1-20261024.md)
> —— `T-300..T-392` 的可派工粒度、依赖、可执行判据与执行记录；
> [`PMO/implement/T-310-施工单-签发撤回进权威-20261024.md`](./PMO/implement/T-310-施工单-签发撤回进权威-20261024.md)
> —— 第一张关键路径票的施工单：**签发绑定 11 个字段今天一个都没有生产者**这个事实、
> 拆成 a/b/c/d 四张子票、落进 state 的确切形状、三条断言与四个必红变异；
> [`PMO/implement/T-311-施工单-申诉进权威-20261024.md`](./PMO/implement/T-311-施工单-申诉进权威-20261024.md)
> —— 第二张：**申诉号是进程内自增计数器（重启撞号）**、`mark_stale` 在生产里 0 调用、
> 申诉记录没有 `tenant` 字段这三处真缺陷，以及 RL-12 的哪一半其实属 T-317；
> [`PMO/implement/T-312-施工单-下线任务进权威-20261024.md`](./PMO/implement/T-312-施工单-下线任务进权威-20261024.md)
> —— 第三张：**生产里没有任何创建下线任务的路径**（7 条写路径全是「对已有任务做迁移」）、
> 六条路由从不检查 `takedown.*` 能力、以及 `published` 这个事实全仓不存在；
> [`PMO/implement/T-314-施工单-名单治理写路径-20261024.md`](./PMO/implement/T-314-施工单-名单治理写路径-20261024.md)
> —— 第四张（P1 瓶颈，同时挡着 T-312b 与 T-315）：`@app.post("/api/v1/admin` 全仓 **0 个**、
> 两份 grants JSON **盘上不存在**、P-11 前端只有提案一段、
> `validate_grant_actors()` 写得完整但**零调用点**，以及 `release.*` 能力判定
> **有两套口径**（`release_gate` 读 `capabilities` 字段 / `can_act` 读角色矩阵）；
> [`PMO/implement/上线交付说明-20261024.md`](./PMO/implement/上线交付说明-20261024.md)
> —— **上线前唯一该读的一份**：哪些能上、哪些不能上、六条必跑命令、
> 两个待决策（报告要不要 Node / 结案无报告能否接受）、合入顺序与止损。
> [`PMO/implement/冷启动交接-Prompt-20261025.md`](./PMO/implement/冷启动交接-Prompt-20261025.md)
> —— **新会话冷启动的第一条消息**（整段复制给 Claude Code）。先清 pyc、
> 再跑 11 个验证器拿基线、交代未提交的 37 改 8 新、`.venv/bin/python`
> 已被沙箱脚本覆盖需重建、以及「零件对、接线错」这一类缺陷为什么只有
> 真实生产装配能抓到。
> [`PMO/implement/媒体审核落地执行方案-v1-20261026.md`](./PMO/implement/媒体审核落地执行方案-v1-20261026.md)
> —— **补一份失职**：`交付执行计划-v1` 全文 0 处提图片/视频。本方案给真实分层状态
> （图片实现完整但进件门关着、视频只有一个状态函数）、M0–M5 六层目标、
> `T-420`–`T-425` 六张带变异判据的票、三个待委托方定的事；并附一个真缺陷
> （`_coverage_ir` 丢 `does_not_cover`）。
> [`PMO/implement/媒体审核-外部API落地方案-v2-20261026.md`](./PMO/implement/媒体审核-外部API落地方案-v2-20261026.md)
> —— **v1 的替代版**（委托方已定：外部 API + magpie + Gemini、参考 claude-video、先打通功能）。
> 含一个结构性矛盾的处置（finding 三要素含知识库产物 → L1 观察 / L2 候选两级）、
> claude-video 的适配取舍、balanced 帧策略、`T-430`–`T-436` 七张票。
> [`PMO/implement/T-316-施工单-报告生产落盘-20261024.md`](./PMO/implement/T-316-施工单-报告生产落盘-20261024.md)
> —— 第五张（D5 阶段门最后一环）：**运行时镜像里没有 Node**，而唯一的报告渲染器是 Node 实现；
> 报告的 ACL 判据读 `principal["role"]`（单数大写），真实身份是 `roles`（复数小写）→
> **接上即全拒**；`report_snapshot` 被 `judge_entry` 丢掉；`/reports/{id}/resign` 只有路径没有语义。
> [`PMO/implement/收尾方案-v1-20261025.md`](./PMO/implement/收尾方案-v1-20261025.md)
> —— **P1 剩余任务的总方案**（2026-10-25）：六环节只剩签发一环；M1–M5 阶段目标与
> 三线并行顺序；`kb_snapshot_hash` 口径裁定（D1 已裁定）；11 条 unmapped 判据逐条归属；
> 一条共用契约（报告保持「判定时冻结」，T-310/315/317 都不动渲染器）。
> [`PMO/implement/T-313-施工单-通知进权威-20261025.md`](./PMO/implement/T-313-施工单-通知进权威-20261025.md)
> —— 第六张：`GET /notifications` 读 frozen 夹具、read/ack 是 501 占位、三个触发点
> 在生产路径**零生产者**；独立 aggregate + SCHEMA_VERSION 3 必须写**独立 `==2` 迁移分支**
> （「只加全新库→v2 老库静默跳过」是 v1→v2 崩溃的新变体）；投影必须先行部署。
> [`PMO/implement/T-315-施工单-撤权进权威-20261025.md`](./PMO/implement/T-315-施工单-撤权进权威-20261025.md)
> —— 第七张：全仓无 `revoke_grant`；**`gate.revoke` 不校验原签发人**（#123c 的判定今天不存在）；
> 撤权 = grant 状态迁移，授权版本就是聚合 version；名单只盖 `release.sign` 不盖 revoke。
> [`PMO/implement/T-317-施工单-全量重审进权威-20261025.md`](./PMO/implement/T-317-施工单-全量重审进权威-20261025.md)
> —— 第八张：`_new_job/complete_job` 是内存桩（在 release_gate.py，**票面写错成 orchestrator.py**）；
> 重判入口 `judge_unit` 已存在、无需重新 submission；`report_immutable` 守卫会挡住重审的新报告。
> 判据全落产物级（#98 在 10-23 曾假绿回退）。
> ★ 前 7 份是**读数审计**（回答「这个 passed 有多少是真的」）；
> 后 6 份是**执行规格**（回答「接下来按什么顺序做、做到什么算完」）。
> 两类不许混读：前者是证据，后者是计划；计划里的数字若与证据冲突，以证据为准。

**Playbook / PRD**

- `Playbook/内容审查Agent-产品Playbook-v0.md`
- `Playbook/内容审查Agent-产品Playbook-v1.md`
- `Playbook/内容审查Agent-产品Playbook-v1.1.md`
- `Playbook/技术解决方案-v1.md`
- `Playbook/Playbook-v1-修订清单-20261017.md`
- `PRD/内容审查Agent-PRD-优化版-v2.0.md`
- `PRD/feishu/_history/内容审查Agent-PRD-v1.0@20260923T1806.md`

> **哪一版是权威、哪一版只是快照**：[`Playbook/README.md`](./Playbook/README.md) 与
> [`PRD/feishu/README.md`](./PRD/feishu/README.md)（2026-10-22）。
> 一句话：**唯一权威是上游飞书 docx，本地没有任何一份同时满足「最新 + 逐字 + 完整」** ——
> 本地那份文件名写 `v1.0` 的，正文实为 **v1.2**；上游已到 v1.3，但正文不在盘上。

**PMO / audit / implement**

- `PMO/Momcozy-品牌资产落盘方案-20261017-v1.md`
- `PMO/Momcozy-采集方案-20261017.md`（v1 现场留痕：HTML 翻页路线）
- `PMO/Momcozy-采集方案-20261017-v1.1.md`（主站改走 UCP/MCP；`tools/momcozy/README.md` 指向这份）
- `PMO/audit/内容审核Agent-输入类型与工作流剖析-20261020.html`（单文件 HTML，零外链）
- `PMO/audit/前端设计系统与依赖治理-优化方案-v1.1-20261021.md`
- `PMO/audit/Playbook-v1.1-专项核验-20261017.md`
- `PMO/audit/内容审查Agent-UIUX前后端规格草案-v1.md`
- `PMO/audit/内容审查Agent-决策总账-v2-20261018.md`
- `PMO/audit/内容审查Agent-常犯坑点与硬约束-v1.md`
- `PMO/audit/内容审查Agent-端到端工作流规格草案-v1.md`
- `PMO/audit/内容审查Agent-行业证据矩阵-v1.md`
- `PMO/audit/决策溯源账-v1-20261017.md`
- `PMO/audit/待确认-技术栈与工程选型-v1.md`
- `PMO/audit/故障登记-F-001-守衡启动链断裂-20261017.md`
- `PMO/audit/核验-收敛报告-20261017.md`
- `PMO/audit/红线冲突登记-CR-001-飞书附件入公开仓-20261017.md`
- `PMO/audit/验收表-v2-覆盖全部判据-20261017.md`
- `PMO/audit/验收表-v3-覆盖全部判据-20261017.md`
- `PMO/implement/T0-02-fetch-error-id-rule.md`
- `PMO/implement/T0-03-claim-owner.md`
- `PMO/implement/内容审查Agent-implement-阶段计划-v1.md`
- `PMO/implement/阶段3-准备评估.md`
- `PMO/implement/阶段3-gold样本需求.md`
- `PMO/implement/58子类-候选映射草案-20261019.md`
- `PMO/implement/阶段3-审查结论gold-评测说明-20261019.md`

**规则归类 / 基准复核（2026-10-19 ~ 10-20）**

> 七份一条链，按顺序读：提示词契约 → 首轮评测 → 边界回测 → 两条基准复核 → 抖动契约改动 → 待办执行票。
> 2026-10-21 补的入口。此前这七份从起点走不到，原因分两种：**六份在已入库文档里 0 条入边**；
> `基准复核-65条` 只被同样走不到的 `模型抖动` 引用。另有两点要说明口径 ——
> `规则归类-LLM提示词` 只被 `tools/llm_rule_axis_eval.mjs` 提到，而**机器产物不当中继**；
> `待办盘点` 与 `基准复核-65条` 其实也被 `ADR/ADR-0016` 引用 —— 但补入口时那份 ADR
> **尚未入库**、不在 `git ls-files` 口径里。**ADR-0016 已于 2026-10-21 入库**，
> 所以这两条现在有双入边；在这里补齐的意义是：**读数不再取决于另一份文档何时提交。**
> 它们不属于任何豁免类，`verify_doc_reachability.py` 的 **D** 与 **E1** 因此双红；
> 现在由 **D2**（按目录的断言）守着。

- `PMO/implement/规则归类-LLM提示词-v1.md`
- `PMO/implement/LLM规则归类-首轮评测-20261020.md`
- `PMO/implement/七轴边界修订-回测-20261019.md`
- `PMO/implement/基准复核-14条-20261020.md`
- `PMO/implement/基准复核-65条-循环第一轮-20261020.md`
- `PMO/implement/模型抖动-契约改动-20261020.md`
- `PMO/implement/待办盘点与执行票-20261020.md`

- `PMO/事故登记-ENV-001-4096污染-20261017.md`
- `PMO/回话草稿-外部标准库-20260922.txt`
- `PMO/守衡-四事闭环-归因优化验收-20260922.md`
- `PMO/飞书写通道-落地记录-20260922.md`

**research**

- `research/governance/control-points-README.md`
- `research/topo/README.md`

**Web 工作台**

- `web/README.md`

**资产包入口**

- `PMO/audit/momcozy-assets/index/asset_package_index.md`

---

> 2026-10-25/26 的 T-400 段（6 份）：
> [`PMO/implement/最终上线差距分析-v1-20261026.md`](./PMO/implement/最终上线差距分析-v1-20261026.md)
> —— GA-01..GA-10 + GW-01..GW-22 三十二**条差距（其中四条的前提经实测为错，见下两份）**；
> [`PMO/implement/执行票清单-v2-20261026.md`](./PMO/implement/执行票清单-v2-20261026.md)
> —— T-400 段 13 票，三批派工顺序；
> [`PMO/implement/执行方案-T400对账与施工-v1-20261025.md`](./PMO/implement/执行方案-T400对账与施工-v1-20261025.md)
> —— **开工前逐条复现八票前提**的对账结果（四票票面是错的）+ 六节施工记录 + 一次 `cat >>` 写坏中文文件的事故；
> [`PMO/implement/T400段-ready收尾报告-20261026.md`](./PMO/implement/T400段-ready收尾报告-20261026.md)
> —— 八票总账、四票票面错在哪、剩余四票 blocked 各自缺什么；
> [`PMO/implement/T-405-T390裁定申请-v1-20261026.md`](./PMO/implement/T-405-T390裁定申请-v1-20261026.md)
> —— 语义判定 P1 接入的 A/B/C 裁定申请书（含实测样本：选 B 会让 98/232 条零命中内容从 REVIEW 变 BLOCK）；
> [`PMO/implement/T-407-样本签署申请-v1-20261026.md`](./PMO/implement/T-407-样本签署申请-v1-20261026.md)
> —— 83 条冻结样本的分层签署申请（★ 捞到 `GS-011` 期望值与法务 D2 决定相反）；
> [`PMO/implement/T-412-OCR-ASR选型申请-v1-20261026.md`](./PMO/implement/T-412-OCR-ASR选型申请-v1-20261026.md)
> —— 容器内 OCR/ASR 的选型申请书（含 `verify_media_portability` 实测：行 118 今天是**空真**，不是违规）。
>
> [`PMO/implement/冷启动交接-Prompt-20261026.md`](./PMO/implement/冷启动交接-Prompt-20261026.md)
> —— 本轮开工时使用的冷启动提示词正文（含「先做这三件事」「硬约束」「已踩过的坑」）。
>
> ★ [`PMO/implement/生产部署方案-内容审查工作台-20261026.md`](./PMO/implement/生产部署方案-内容审查工作台-20261026.md)
> —— 生产部署方案（`ca.luteos.com`）：服务器现状、SSH 端口是 **22222** 不是 22、
> 六个阶段的命令与判据、七条回滚阈值、以及「回滚不是撤销」那条硬边界；
> [`PMO/implement/生产部署执行记录-20261026.md`](./PMO/implement/生产部署执行记录-20261026.md)
> —— 实际执行记录：备份被 `2>/dev/null` 吞掉一个失败、
> `missing_config:REVIEW_REPORT_ROOT` 导致 7 秒中断、以及 P0-D 在 `down && up` 后
> 被证明真的修好了（探针文件仍在）。
> ★ [`PMO/implement/放行带在哪-自查纠正-20261026.md`](./PMO/implement/放行带在哪-自查纠正-20261026.md)
> —— **一次自我推翻**：我原写「放行带已生效」，实测是「放行带只在分析引擎里、
> 生产引擎从不读它」（`downgrade` 在 `base/rule_judge.py` 出现 **0** 次，在
> `skeleton/score.py` 出现 **13** 次）。两个引擎对 `FDA approved … FDA cleared.`
> 给相反判定，而没有任何断言在比它们。已记 **T-417**。
> ★ [`PMO/implement/上线判断-GO-NOGO-20261026.md`](./PMO/implement/上线判断-GO-NOGO-20261026.md)
> —— 今天能不能上线的判断：技术侧 GO，卡在「谁执行」与「真实人员名单」；
> 含今天修掉的 4 个 P0 与一条回滚硬边界（**第一条通知产生后旧镜像就起不来**）；
> [`PMO/implement/上线执行单-20261026.md`](./PMO/implement/上线执行单-20261026.md)
> —— 1340 行、按时间顺序、每步含逐字段期望输出与「失败说明了什么」；
> [`PMO/implement/回滚方案-20261026.md`](./PMO/implement/回滚方案-20261026.md)
> —— 七条可观测阈值 + 数据侧处置 + ★「回滚不是撤销」；
> [`PMO/implement/T-410-点火清单-v1-20261026.md`](./PMO/implement/T-410-点火清单-v1-20261026.md)
> —— 七步点火清单（每步含前置、命令、逐字段期望输出、失败说明了什么）；
> [`PMO/implement/T-410-无凭据真跑-20261026.md`](./PMO/implement/T-410-无凭据真跑-20261026.md)
> —— ★ 不需要真实凭据的那部分真跑取证（捞到两个 P0：镜像缺 `tools/redact.py`
> 导致容器 import 期就死；生产 bundle 打 `/review-api` 而服务只提供 `/api/v1`）；
> [`PMO/audit/验收行109-110-111-128-执行点-分类与变异验证-20261026.md`](./PMO/audit/验收行109-110-111-128-执行点-分类与变异验证-20261026.md)
> —— 四行验收的 A/B 分类（A 类今天可判、B 类必须等 T-333）+ 8 条变异验证。
>
> Web 联调：`web/scripts/PAIRING-README.md`（browser harness 用法 + 第一次真跑抓到的四个真实缺陷，
> 以及「`dev-up.sh` 从来没跑通过」那三环）。

---

## 三、自证命令表（改了哪个子系统，就跑到它变绿）

`AGENTS.md` §2.1 是这张表的权威版本，本表与它必须一致。**退出码语义**：全过退 0；
有红退 1；**读不出 / 扫不了退 2 —— 未测 ≠ 通过 ≠ 红。**

```bash
python3 tools/verify_engine_contract.py                # 内容合规判定引擎：引擎契约
python3 tools/verify_kb.py                             # 知识库：G1 存在性 / E1 证据
python3 tools/verify_skill.py                          # 把规程文档里每条 bash 命令真跑一遍
node    tools/verify_cards.mjs                         # 守衡群回复模版 / 字段登记 / 文档三者一致 + 去 AI 味正反例
python3 tools/verify_feishu_index.py                   # 飞书可达资源索引：租户判定 / 可达性 / 原文抽取
python3 tools/lark_people.py --controls                # 责任人 → 投递地址（离线反向对照）
python3 tools/verify_prd_baseline.py                   # 上游 PRD 基线漂移（L3 未测退 2）
node    tools/agent/prd_baseline.mjs --selftest        # 基线漂移与待收到期的触发者（告警状态机）
python3 tools/verify_pending.py                        # 上游承诺有没有收到（承诺 vs 我方提问）
python3 tools/verify_landing.py                        # 落地页抓取指标
python3 tools/verify_external.py                       # 外部标准库：条目必须在来源快照中逐字命中
python3 tools/verify_vocab_lark.py                     # 词表飞书 ↔ 本地逐词一致
python3 tools/verify_coverage.py                       # 覆盖登记表自身：名册双向完整 / 主体可查
python3 tools/verify_depad.py                          # 全仓库生成物可读性（read 工具打不开的文件）
python3 tools/verify_doc_reachability.py               # 本 README 的可达性（口径与断言见文件头）
python3 tools/verify_doc_reachability.py --controls    # 上面那一个的反向对照
python3 tools/verify_reference_census.py               # 零引用可执行文件的棘轮（只许减不许增，基线 31）
python3 tools/verify_reference_census.py --controls    # 上面那一个的反向对照（含「基线自毁」那一格）
python3 tools/verify_shouheng_ops.py                   # 守衡自己还活着吗（没在跑 / 有读数未测 → 退 2）
```

另有两个在子系统目录里：`python3 research/distill/verify_citations.py`、
`python3 base/verify_base.py`。

> **落盘配方**：凡是 **Python** 进程写出的文件，都会进「+4096 填充态」——
> `read` 工具把它判成 `binary file`，正文一个字都读不出来，而 sha256 一切正常。
> 所以：`python3 <产出者> > '<目标文件>'` → `python3 tools/verify_depad.py --fix` → `python3 tools/verify_depad.py`。
> 三步都要，理由与实测见 `AGENTS.md` §2.1。

---

## 四、这份 README 自己也被验

「README 是唯一入口」这句话如果没人验，就只是一句安慰（`AGENTS.md` §2.4.2）。
验它的是 [`tools/verify_doc_reachability.py`](./tools/verify_doc_reachability.py)：

```bash
python3 tools/verify_doc_reachability.py               # 主读数：从 README ∪ AGENTS 出发
python3 tools/verify_doc_reachability.py --readme-only # 只看 README
python3 tools/verify_doc_reachability.py -v            # 列出每一份不可达文档
python3 tools/verify_doc_reachability.py --controls    # 反向对照（只在内存里造样本）
```

它断言：每一份 `ADR/ADR-*.md` 可达、每一篇 `PMO/守衡-*.md` 可达、
不可达总数不超过钉住值、**每一份非豁免的第一方文档都可达**，
且每一份不可达文档都落在一个**已声明判据**的豁免类里（分项之和 == 总数）。
