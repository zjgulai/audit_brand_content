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

**Playbook / PRD**

- `Playbook/内容审查Agent-产品Playbook-v0.md`
- `Playbook/内容审查Agent-产品Playbook-v1.md`
- `Playbook/内容审查Agent-产品Playbook-v1.1.md`
- `Playbook/技术解决方案-v1.md`
- `Playbook/Playbook-v1-修订清单-20261017.md`
- `PRD/内容审查Agent-PRD-优化版-v2.0.md`
- `PRD/feishu/_history/内容审查Agent-PRD-v1.0@20260923T1806.md`

**PMO / audit / implement**

- `PMO/Momcozy-品牌资产落盘方案-20261017-v1.md`
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
