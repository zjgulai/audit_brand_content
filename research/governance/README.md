# 规则库搭建与自迭代 · 调研与审计索引

> 委托问题：**审核规则库应该如何定义？是「国家 × 品类 × 平台 × 内容类型」还是其他？规则怎么萃取？需要错题本还是规则库、严重等级？没有规则怎么办？其他跨境电商企业怎么做？**
>
> 目标产出：**规则库的搭建骨架 + 自迭代骨架 + SOP**，附标准案例。
>
> 起始日期：2026-09-15　｜　最近更新：2026-09-15（R2 / R5 落地）

---

## 目录

### 第一部分 · 内部证据（把委托方自己的数据当数据集跑）

| 文件 | 回答什么 | 关键读数 |
|---|---|---|
| `01-内部证据-规则表现状审计.md` | 现有 21 条规则表，作为**可执行规则库**成色如何？ | 正则层复现率 **13.8%**；`检查人` 填写率 **0/291**；**20.3%** 记录引擎看不到却落绿；6 条规则零命中；38.1% 的人工命中词在规则表里查不到 |
| `02-内部证据-维度有效性检验.md` | 「国家 × 品类 × 平台 × 内容类型」这四个维度**真的会改变判定吗**？ | 四维中**只有语种**经得起统计检验；市场与模态的差异来自「输入分布不同」而非「规则不同」；291 条记录实际只有 **163 条不同素材**（1.7× 伪重复）。**§7 已更正**：平台维度的原结论被推翻，改为「样本失衡，不可检验」 |
| `03-内部证据-声明的判定一致性.md` | 同一句声称，是不是每次都判一样？ | 无痛/等级背书/静音 **100% 稳定**；排名最高级 **78%**；首创/唯一族 **0% 覆盖**；`trusted by 6 million` 是字面量，`4.5M+`/`5M+`/`1,740` 全部漏；H05「口径放开」与 M03 词表**直接冲突** |
| `04-内部证据-字段可用性与平台抽样偏差.md` | **记录本身能不能被审计？** | `投放地区` 74.2% 落「其他」，而数据其实完好（三字段交叉验证 8/10 账号零例外）——**是数据字典漏了 5 个国家**；真实最大市场是**美国 100 条**；`检查人` 是 27 字段中唯一 0.0%；`命中规则` 把 `EMPTY` 记成了规则编号 |
| `05-内部证据-记录表分歧结构与错题本现状.md` | **「错题本」到底缺什么？现有数据能回答「机器判得对不对」吗？** | **没有任何一列能承载人工复核结论**；`风险等级 × 处理状态` **完全对角**（291/291）→ **判定从未被校准**；132 条待复核 = 近 7 天 **$19,913.24（46.2%）**；424 个检测关键词中**小语种词 0 个**（实际非英语文案 28.2%）；**8 条规则无正则**（含 H03/H04 两条红线）；`秒杀` 是**已发生的假阴性**；**§9 含两次判据自我更正** |

**四份内部证据的关系**：01 审计「规则判得准不准」，04 审计「记录能不能被追责」。
一个团队可以判定得很准、同时记录得无法追责——**后者在监管问询时才是致命的那一个。**

### 第二部分 · 可执行工具（每月体检用）

| 文件 | 用途 |
|---|---|
| `audit_rule_table.py` | 规则表层审计：正则覆盖率、豁免词自捕获、编号族一致性、适用产品字段 |
| `audit_records.py` | 记录层审计：字段可解析性、等级自洽性、填写率、规则共现 |
| `audit_dimensions.py` | 维度有效性检验：卡方检验 + 伪重复校正 |
| `audit_field_profile.py` | **字段可用性剖面**：填充率阶梯、「其他」桶检验、三字段交叉验证、平台抽样偏差（`04` 号的复算脚本） |
| `audit_escape_layers.py` | **转义层审计**：`\|` 是 Markdown 保护符不是内容；三种切分方式的字段完整性对照；规则正则还原后有效性 |
| `lint_rules.py` | **规则库体检记分卡**，14 项检查，当前健康度 **21%**（通过 3 / 告警 6 / 失败 5） |
| `audit_records_deep.py` | **记录表分歧分析**：判定分布、规则触发频次、错题本规模测算、渠道可见性缺口（`05` 号的复算脚本） |
| `audit_rule_consistency.py` | **规则交叉一致性检验**：T1 关键词重叠 / T2 豁免词↔检测词 / T3 检测通道完整性 / T3b「会漏且真的出现过」/ T4 两列冗余。判险规则间冲突 **0 组**；8 条无正则；12 个词会漏且出现过 |
| `audit_make_errorbook.py` | **错题本生成器**：产出 `errorbook/`（143 行 × 25 列 CSV + schema + 说明），可重复运行 |

```bash
cd /Users/lute/Project/audit_multi_content
python3 research/governance/lint_rules.py             # 一次跑完体检
python3 research/governance/audit_rule_table.py
python3 research/governance/audit_records.py
python3 research/governance/audit_dimensions.py
python3 research/governance/audit_field_profile.py    # 加 --json 输出机器可读结果
python3 research/governance/audit_escape_layers.py    # 加 --json
```

所有脚本**只读** `PRD/内容治理需求文档.md`，不修改任何输入。机器可读结果落在 `_evidence/`。

### 第三部分 · 外部一手调研（分片）

| 分片 | 主题 | 状态 | 体量 |
|---|---|---|---|
| `00-调研任务书.md` | 共享背景、证据标准、分片边界 | ✓ | 8.5 KB |
| `R1-platform-policy-taxonomy.md` | Meta / Google / YouTube / TikTok / Amazon 政策库的**结构解剖** | ✓ 初稿 | 1,688 行 / 176 KB；证据 493 件 / 192 MB |
| `R2-adjudication-casebooks.md` | 英国 ASA / 美国 NAD / FTC / 欧盟的**裁决案例库机制** | ✓ 含 T1–T3 补取 | 3,189 行 / 311 KB；证据 213 件 / 82 MB |
| `R3-rule-engineering.md` | Rules-as-Code、LegalRuleML、ODRL、OPA、Cedar、DMN 的**规则建模标准** | ✓ 初稿 | 2,500+ 行 / 213 KB；证据 84 MB |
| `R4-trust-and-safety-ops.md` | Trust & Safety 的**规则生命周期、误差分析、度量、冷启动** | 进行中 | 证据 220 MB |
| `R5-category-and-competitors.md` | 吸奶器的**监管定性**（FDA/MDR/FTC）与**竞品合规表达**对照 | ✓ 初稿 | **2,670 行 / 331 KB**；证据 **810 件 / 260 MB**（其中 `_evidence/R5/materials/` 187 件为法源原文） |
| `R6-peer-practice-and-standards.md` | **同行怎么做**（IAB/GARM 标准、上市公司披露、岗位定义、Amazon Account Health） | ✓ | 1,459 行；含 IAB 官方**可运行**评测脚本 |
| **`_shards/R7-*.md`**（3 份） | **R7 规则库结构横剖与轴设计**：真实系统结构 / 五方案评估 / 品类参照与冷启动 | ✓ | **5,395 行**（W1 2,059 · W2 2,319 · W3 1,017）；【原文】321 块 |
| **`_shards/R8-*.md`**（3 份） | **R8 规则萃取与治理**：来源分类学 / 萃取方法学 / 错题本·严重等级·空白处理 | ✓ | **4,038 行**（W1 1,060 · W2 1,435 · W3 1,543）；【原文】151 块 |

> **关于 `_shards/`**：R7 与 R8 各拆成三份并行撰写（每份独立成文、边界互不重叠）。
> 原因：这两个分片的**单体任务两轮尝试都在写文件之前耗尽预算、产出 0 行**——
> 它们各抓了 18 MB / 15 MB 证据、读完所有材料，却一行未落。
> 拆分后改为「先 write 骨架 → 每完成一节立即 edit 追加」，六份全部落地，合计 **9,433 行**。
> 主交付物引用时按 `R7-W2 §4.1` / `R8-W3 §2.1.5` 形式标注。


证据原始件统一存于 `_evidence/R*/`，引用时给出 URL 与本地路径。**累计一手证据 ≈ 718 MB。**

### 第三部分之二 · 可执行骨架（★ 设计文档的证伪装置）

| 文件 | 说明 | 状态 |
|---|---|---|
| **`skeleton/topic-tree-v1.md`** | **完整主题树：9 主题 / 43 节点**。设计文档 §2.2 当时只有 T2 一棵子树、其余八个主题全是空壳 | ✓ |
| **`skeleton/rules-v1.json`** | **可执行规则库：26 条叶子规则**，由 21 条现行规则重写。含 `match` / `downgrade_band` / `escalation` / `detection_layer` | ✓ |
| **`skeleton/severity.py`** | 第三层：NIST `TABLE I-2` 查表实现（含全 25 格复现自检与封顶效应验证） | ✓ |
| **`skeleton/score.py`** | 评分引擎 + 主题树校验 + `rule_key` 改名漂移校验 | ✓ |
| **`skeleton/REWRITE_NOTES.md`** | **实测结论：跑出 5 处设计文档更正 + Q3 的确切答案** | ✓ |

**主结果**（291 条真实记录，`python3 skeleton/score.py`）：

```
Precision 0.970   Recall 0.962   F1 0.966      TP=229 FP=7 FN=9 TN=158
CATCH-ALL（未覆盖）159 条 = 54.6%
```

> **为什么要有这一层**：在这之前，那份 1,666 行的设计**从未在任何真实数据上跑过** ——
> 没有任何东西能证明它对。跑完之后的五处更正见 `skeleton/REWRITE_NOTES.md` §3，
> 其中三处是结构性的（绝对化不能当主题 / 安全词不是规则 / 跨主题规则实为 7 条）。

### 第四部分 · 综合（主交付物）

| 文件 | 说明 | 状态 |
|---|---|---|
| **`规范-审核规则库完整设计.md`** | **主交付物**。**不沿用**需求文档的四维笛卡尔积方案，依据八个分片（R1–R8）+ 实测**重建**完整体系：<br>§1 十条判断 · §2 规则库怎么定义（主题 × 正交属性 × 风险级三层，含 §2.3.4「五个属性在真实系统里各自住在哪」） · §3 怎么萃取（五个环 + 来源优先级 + §3.1.1「谁压谁是两个排序」 + 错题本关系 + §3.2.1 双库结构） · §4 严重等级（GARM 参照 + 六档 + §4.3.1 NIST 查表 + §4.3.2 DSA 三子维度 + §4.6.1 配合度升级轴 + α 校准） · §5 空白处理（未命中≠合规 + §5.5.1 `coverage_state` 独立字段 + 兜底规则 + 三维交叉表） · §6 落地路线 P0/P1/P2 | ✓ **1,455 行** |
| `audit_evidence_integrity.py` | **证据完整性门**：扫描全部 3,682 个证据文件，输出 11 类机械可判定的缺陷（见下文「证据卫生」） | ✓ 当前 111 项风险 |
| `fetch_seller_and_payment_policies.py` | 补抓**卖家平台与支付侧**政策结构（eBay / Etsy / Walmart / Stripe / Adyen / Google Ads / Meta） | ✓ 6/14 成功 |
| `errorbook/errorbook.csv` | **错题本种子**：**143 行 × 25 列**（132 条内容错题 + 11 条规则错题），UTF-8 BOM，可直接导入 | ✓ |
| `errorbook/错题本.md` | 错题本用法：怎么填、谁填、填完去哪 | ✓ |
| `errorbook/errorbook_schema.md` | 25 个字段的定义、取值枚举、依据出处 | ✓ |

### 第五部分 · 上面四部分漏挂的文件（2026-09-22 补录）

> **这一节为什么存在**：本索引原先只列了「有名字的分片」，于是下面这些文件**在仓里没有任何入边** ——
> 从 `README.md` 或 `AGENTS.md` 出发一份都走不到（实测：`python3 tools/verify_doc_reachability.py -v`）。
> 其中 `receipts.LOSS.md` 是一份**事故记录**，而 `AGENTS.md` §2.2 正是把事故记录当作
> 「别再踩的坑」的唯一存档 —— 走不到的事故记录等于没记。

| 文件 | 说明 |
|---|---|
| `R4-metrics-and-transparency-evidence.md` | **R4 的一手证据包**（抓取日期 2026-09-15，原件在 `_evidence/R4/`）。`R4-trust-and-safety-ops.md` 是它的正文；上面「第三部分」的 R4 一行只挂了正文，没挂证据包 |
| `判定引擎产品化-实测报告.md` | 批次 A + 第二批 D5–D11 的**实测报告**（语料 = `_data/records.json` 291 条真实广告记录）；配套决策是 `ADR/ADR-0012-判定引擎产品化与处置分层.md` |
| `skeleton/迁移手册-机器词表.md` | **白名单 / 语境守卫的飞书侧迁移手册**（依据 ADR-0008、ADR-0009）；`skeleton/migrate_misrouted_guards.py` 的文件头就指着它的 §五 |
| `skeleton/_data/receipts.LOSS.md` | ⚠ **事故记录**：2026-09-16 `cp` 参数写反，把真回执账本覆盖成 1 行测试回执。**这是「事故记录必须有入边」那条规矩的适用对象** |
| `skeleton/_data/遗留对账.md` | ADR-0013 `遗留#` 对账表（**只读产物**，由 `python3 tools/_recon_legacy.py --write` 生成，手改无效） |
| `annotations/annot_rater_A_notes.md` · `annotations/annot_rater_B_notes.md` | 两名标注者盲标的**备注**（TSV 严格三列，note 另存于此）；配套 `annotations/ANN-GUIDE-001-T1.4-T2.1.2.md` 与 `annotations/measure_alpha.py` |

---

## 已收敛的关键结论（随分片落地滚动更新）

### A. 维度模型：不是四维笛卡尔积 —— **四个分片独立收敛到同一结论**

这是本次调研最硬的一块结果：四条完全不同的路径（法域裁决制度 / 平台政策结构 / 规则工程标准 / 品类监管定性）
**没有互相参照，各自得出同一个结构性判断**。

| 分片 | 路径 | 结论 |
|---|---|---|
| **R1** | 解剖 5 家平台政策库的真实 DOM 与字段 | 四维不是并联的分区键，而是**「一个规则本体 + 一组适用范围参数」**。9 种「本体/范围分离」的可复用机制 |
| **R2** | 英国 ASA / FTC / 欧盟 / 中国的裁决制度 | ASA **不按国家分**（一国一法典）、**不按平台分**（`media_type` 只是检索维度且底层是 GUID），**按声称的语义类型分节** |
| **R3** | LegalRuleML / ODRL / XACML / Cedar / DMN / OpenFisca / DPV | 四维**全部属于 L2 作用域**。所有成熟体系都把「规则说什么」与「在哪些情形下适用」分开建模 |
| **R5** | 吸奶器的 FDA / MDR / MHRA 监管定性 | **「品类」不是维度，是判定前提**——同一台设备换一句文案就从「非器械」变「II 类器械」 |

**R3 给出的一条最锐利反证**：DPV（W3C 社区组最终报告）处理「同一概念在 N 个国家有 N 套规定」时，
做法是**给每个辖区一个独立的命名空间（ISO 3166-2）**，而不是给概念加一个 `jurisdiction` 字段。
合并建模的必然结果是：每改一次适用范围就要复制一遍规则体，规则条数按维度乘积膨胀，
副本之间必然漂移。

**两种分层视角（互补，不是冲突）：**

```
R3 的「规则结构」视角（一条规则由什么组成）
  L1 本体      modality（义务/禁止/许可）+ 判定逻辑 + 结论
  L2 作用域    主体 · 客体 · 行为 · 辖区 · 时间      ← 国家/品类/平台/内容类型都在这里
  L3 约束      阈值 · 正则 · 枚举 · 豁免
  L4 治理元数据 稳定 ID · 版本 · 来源 · 强度 · 优先级 · 状态 · 责任人

R1/R2/R5 的「存储编排」视角（规则放在哪一层）
  L0 规则本体（慢变）         ASA 的 CAP Code 主码
  L1 适用范围（国家·平台·载体·受众）
  L2 本地实现（词表·阈值）     ASA 的 market slur lists，带年度审计
  L3 后果                     ASA 的 sanctions 阶梯
```

**最小可行改造（R1 §8.3）——只需 3 处改动**：
1. `适用产品` 拆成 `品类` + `型号`
2. 新增 `scope_jurisdiction[]`（**必须含 `Global`**）+ `scope_platform[]`
3. `风险等级` 拆成 `severity` + `consequence_type`

### B. 兜底条款：四个体系 + 一个平台层，全都是「举证责任倒置」（R2 §7.4）

| 体系 | 逐字原文 |
|---|---|
| UK CAP 规则 3.7 | `The ASA may regard claims as misleading in the absence of adequate substantiation.` |
| US FTC 1984 Policy Statement | `a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice` |
| EU UCPD Art 12(b) | `to consider factual claims as inaccurate if the evidence demanded … is not furnished or is deemed insufficient` |
| CN《广告法》第 28 条第 1 款第（三）项 | `使用虚构、伪造或者无法验证的科研成果…作证明材料的` |
| **US NAD（R2 T2 新取）** | 裁决词表里有一个独立类别叫 **`No Substantiation Received`** —— 证据不足本身即违规，不需要论证声称为假 |

**R3 从工程侧给出同一要求的强制形式**：Cedar 的 *implicit deny*、OPA 的 `default allow := false`、
DMN 的 hit policy、ODRL 的默认 `invalid` —— 都要求**把默认结论写出来**。
理由一致：**隐式默认让「没命中任何规则」和「命中了但结论为通过」不可区分，而这两件事的责任归属完全不同。**

→ 建议直接落一条兜底规则：**「凡属客观功效声称且无法出示证据者，一律判红」**，配一张「已备证据库」表。
**枚举「违禁词」是有限集，枚举「必须能证明什么」也是有限集——但后者随业务增长且每条有明确准入条件。**

### C. 「错题本 vs 规则库 vs 严重等级」是伪二选一：三个工件 + 一个连接键（R2）

| 工件 | 回答什么 | ASA 对应物 | 寿命 |
|---|---|---|---|
| 规则库 | 「不许做什么」 | CAP Code（Edition 12），规则号 3.7 / 12.1 / 15.1.1 | 长期 |
| 判例库 | 「这条规则在事实上怎么落地」 | ASA rulings，案件号 G26-1343656 | **公开 5 年后下架** |
| **释义层** | 「同类事实该怎么判」 | AdviceOnline / Advertising Guidance / Enforcement Notice | 长期 |

**连接键 = 规则编号**（ASA 可按规则号直接检索判例：`?capCode=3.7` → 373 条）。
**释义层是 Momcozy 完全没有、而最值得新建的一层。**

### D. 严重等级：现有四档缺 8 样东西（R1 §8.4）

① 缺「仅警告」档（四家平台都是「第一次只警告」）② 缺「合规但受限」档
③ 缺「一次触顶」通路（egregious / critical）④ 缺计数窗口与主键（90/180/365 天）
⑤ 缺升格方式（Amazon 是**乘数**：`negative point values double per repeat violation`）
⑥ 缺严重度判定轴（Amazon 明写两轴：**消费者受损程度 + 是否违反法规**）
⑦ 缺品牌调性独立轴 ⑧ 缺「非政策状态」（YouTube 货币化实为 8 个图标状态）

**R1 另发现：TikTok 的严重等级不是字段，而是「规则行所在的清单」**——
同一模板下三块 `NOT ALLOWED` / `FYF INELIGIBLE & AGE-RESTRICTED` / `ALLOWED`，写在哪块就决定后果。
Google 与 Amazon 相反：**按政策分别计 strike**（`maximum of one warning and 3 strikes per policy violation`），计数主键是「规则」。

### E. 三条对现行规则表的具体更正（R5 实测）

| 现行规则 | R5 的更正 | 依据 |
|---|---|---|
| H02「more milk 不能说」 | **是误判**。正确规则是「`more milk` 必须有 RCT 级证据，否则不能说」 | FTC HPCG 2022 p.13 + 竞品 5/7 在用 |
| H06「FDA cleared ≠ approved」 | 法源**不止一条，且比他们写的更强**。21 CFR 807.97 原文是 `constitutes misbranding`（掺假标识认定），不是提醒 | 21 CFR 807.97（本目录已独立复核逐字） |
| 「安全词」白名单 | **有三个词不是安全词，其中一个是反向风险词**。判别标准只有一条：**能否被第三方独立复核为真/假** | FTC Deception Policy 1983 脚注 42 的 puffery 界定 |

**R5 另有两个必须处理的发现**：
- **Momcozy 自己已持有 FDA 510(k) clearance** → 规则库的 `适用产品` 与 `依据来源` 字段需要重写（本目录已独立复核，见 §G）
- **Momcozy 已引用一篇 RCT** → 「有证据可出示」的分级判定是可行的，不是空想

### F. 免责声明不是许可证（R5-C8）

FTC 明文：`Pro forma statements or disclaimers may not cure otherwise deceptive messages or practices.`
→ **`豁免词` 这个字段名本身就是错的**，正确语义是「本句已带证据标记」，命中后应降级到人工复核**而非自动放行**。
检验法：**把免责声明遮住，这句还成立吗？**

### G. 平台政策不是法源，而且可穿戴品类上比法源更严（R5-C9 + R1）

- **Meta 明文禁止** `Claims that results can be achieved solely by using wearable products`（**无任何法源对应**）
- **Meta Personal Attributes** 禁止 `Implied knowledge of Medical information` —— 这把 U04 从「语境判断」变成明确禁令，改写规则可执行
- **Google `Unreliable claims` 明文** `may defer to local regulatory guidelines` → **`平台 × 国家` 是联合键，不是两个可分离的轴**
- **⭐ Amazon Ads 政策逐字点名 `Breast Pump`**，归入 `Category 1 (low sensitivity products): Generally allowed`，但**仍带 supply 级限制与申报义务** —— 这是 Momcozy 品类在平台政策里的确切坐标
  （URL `advertising.amazon.com/help/GPSSMTEAA6AEWY3A`，本地 `_evidence/R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md`）
- **只有 Amazon 把阈值写成数字**（`85% of the image` / `RGB 255,255,255` / `title ≤ 75 characters` / `environmental claims must be dated within 24 months`）——**没有「适当」「明显」「大量」这类词**

### H. ⭐ G3 已结案：W1 的 FDA 状态（本目录独立复核，openFDA 一手数据）

R5 把「W1 的暖敷+按摩功能是否有 clearance 覆盖」列为最高优先级待核实项。**本目录直接查 openFDA 结案。**

**Momcozy 关联主体名下 510(k) 全量**（`applicant` 精确检索，2026-09-15）：

| 主体 | 条数 | 其中吸奶器 (HGX) | 其他 |
|---|---:|---:|---|
| **Shenzhen Root Innovation Technology** | **13** | 11 | 2（吸鼻器 BTA：K260134、K253629） |
| **Shenzhen Lutejiacheng Technology** | **3** | 3 | — |
| **合计** | **16** | **14** | 2 |

R5 说的「13 项」指 Root Innovation 一家，**实际关联主体共 16 项 / 14 项吸奶器**。
首个是 `K230776`（2023-06-09，`Momcozy Wearable Electric Breast Pump (Model: S9 Pro, S12 Pro)`）。

**G3 的答案：16 项 clearance 中，器械名含 `warm` / `massag` / `heat` / `wellness` 的 —— 零命中。**
唯一名字匹配的是 `K260864 Mother's Nature W1 Warming Wearable Breast Pump`（2026-06-09），
但**申请人是 `Shenzhen TPH Technology Co., Ltd.`（23 项 510(k)，代工厂，同时也持 `eufy` 系列），不是 Momcozy 主体**。

> **结论：W1 页面自称 `FDA 510(k) Cleared` 并写着 `supporting the natural release of oxytocin—the hormone that triggers milk let-down`
> （H02 明文禁用词），但其暖敷+按摩功能不在 Momcozy 任何关联主体的 clearance 覆盖范围内。**
> **待核实**：W1 是否通过 TPH 的 K260864 获得授权、或是否有未检索到的 clearance。
> 建议法律团队直接向 Root Innovation / 代工厂索取覆盖 W1 功能的 clearance 文件。

复算命令（精确 applicant 检索，避免全文匹配的 681 条噪声）：
```bash
curl -sL --compressed 'https://api.fda.gov/device/510k.json?search=applicant:%22Shenzhen+Root+Innovation+Technology%22&limit=100'
curl -sL --compressed 'https://api.fda.gov/device/510k.json?search=applicant:%22Shenzhen+TPH+Technology%22&limit=100'
```


---

## 四句话总结现状

1. **现有 21 条规则表是一份文档，不是一份可执行规则库。** 证据：它自带的正则跑在 291 条真实记录上，只能复现 13.8% 的人工判定，且从不多报一条——它已经被当成了「判完之后找位置」的工具，而不是「判断」的工具。
2. **团队困惑的真正来源不是「分类维度选哪几个」，而是「规则」这个词现在同时指两样东西**：一份给人看的政策文档，和一套给机器执行的判定逻辑。这两样已经分家了。
3. **「错题本 / 规则库 / 严重等级」不是三选一，是一条流水线。** 而现在这条流水线的第一环——错题本——缺三个字段（false positive、false negative、规则出处），所以规则库只能单向生长：只能加，不能改，不能删，也无法证明任何一条规则是对的。
4. **记录层的问题比规则层更致命。** `检查人` 0/291，`处理状态` 只有「待人工复核」和「无需处理」两个取值、没有任何一条进过终态——**他们的治理约束是「通过审查记录问责」，而这个机制当前在数据上完全没运行。**

---

## 证据卫生（R7 / R8 阶段的系统性发现）

> 这一节是**方法学产出**，不只对本项目有效。R7 与 R8 的调研过程中发现：
> **「抓到了文件」与「文件可用」是两件事**，而且**HTTP 200 不能证明任何事**。
> 已固化为可复跑的机械门：`python3 audit_evidence_integrity.py`（当前 3,682 文件 / 111 项风险）。

### 十一类可机械判定的缺陷

| 编号 | 缺陷 | 检出数 | 为什么危险 |
|---|---|---:|---|
| **E1** | 声明字节数与实际不符 | 6 | 文件被替换或写坏 |
| **E2** | HTTP 4xx/5xx | 14 | 抓取失败却留下文件 |
| **E3** | 反爬挑战页（`Just a moment` / Incapsula） | 5 | **假成功**：有体量、无内容 |
| **E5b** | 失败页正文（`Page not found` / `does not exist`） | 15 | 同上 |
| **E6a** | 小文件同哈希（**张冠李戴**） | 9 | 同一内容被当成两个来源交叉印证 |
| **E6b** | 大文件同哈希（同站样板文字） | 10 | 多为导航/页脚所致，风险较低 |
| **E7b** | `.md` 正文回查原始 HTML 缺失 | 5 | 网页转文本时丢内容 |
| **E7c** | `.md` 回查通过 | 37 | 偏小系站点样板与 JS 所致，**非截断** |
| **E8** | 内嵌 JSON 正文未进 `.md` | 9 | 折叠组件内容只在超长行里 |
| **E9** | **HTTP 200 的假壳页** | 1 | 状态码骗人（`UvA DARE \| Record not found`） |

### 四条必须记住的取证教训

1. **HTTP 200 不等于内容可用。** 实测反例：`ck-thesis-uva.txt` 头部写 `HTTP: 200`，正文是 `Record not found`；`ebay-prohibited-restricted-items.txt` 是 HTTP 200 的「Security Measure / Please verify yourself」验证页；`ftc-com-disclosures.txt` 是 9 KB 纯导航壳（`clear and conspicuous` **0 命中**），而真正的 53 页 PDF 在另一个 URL。
2. **文件名可能与内容完全不符。** 实测两例：`rulefit-arxiv.txt` 的 `SOURCE_URL` 指向 `arXiv:0811.3652`，那是**组合数学**论文（真正的 RuleFit 是 `arXiv:0811.1679`）；`ke-llm-drops.txt` 实为**编程练习题生成**论文（ICPEC 2023）。
3. **不要按行读 HTML，也不要对行长设上限。** 现代站点把正文以**转义 JSON + 超长行**内嵌：Amazon 政策页实测有单行 **11,405** 与 **29,989** 字符。按行抽取或对行设长度上限会**静默丢掉正文**，制造「HTML 里明明有、grep 却查不到」的**假阴性**。
4. **同哈希是交叉印证的陷阱，而且同哈希的两个名字可能有一个是谎报的。** `R1/youtube-channel-terminations.md` 与 `R1/youtube-strike-expiry.md` **逐字节相同**（`sha256=9df83d53…`，`shasum` 与 `stat` 双重复核），却声称是两份不同政策。**进一步复核发现更严重的问题**：后者的正文里 `strike`=**0**、`expiry`=**0**、`90`=**0** 次——它不是「strike 到期政策」，而是**频道终止页**。**本项目全库没有任何 strike 到期 / 90 天窗口政策的正文**。同组还有 `R1/raw/_body_yt-{terminations,strike-expiry}.md`（另一哈希 `3251b52b…`，3,637 B，**此前被误与上一组合并**）。
   > **教训**：「文件名与内容不符」和「同内容两个文件名」是**两类不同的缺陷，可能叠加在同一个文件上**。只做同哈希检测会看到「重复」而看不到「谎报」；只做文件名抽查会看到「可疑」而不知道它其实逐字节等于另一个文件。

### 引文保真度：426 条【原文】已全部机械回查

`audit_citation_fidelity.py` 把每条引文拉伸为整语料搜索，命中即记录文件、字节偏移、原文上下文。完整结果见主交付物**附录 C** 与 `_evidence/_citation_fidelity_report.json`。

> ⚠️ **本轮最重要的一条发现，是核验工具自己有缺陷，而不是引文有缺陷。**
> 见下「自己证明自己」。

### ⚠️ 核验工具会「自己证明自己」—— 最危险的一类假通过

**`_evidence/` 顶层放着工具自己写出的分析产物**（`_KNOWN_MISLABELS.md`、`_citation_fidelity_misses.md`、`_citation_fidelity_report.json`、`_integrity_report.json`）。这些文件里**逐字复述了引文本身**。它们一旦被当成语料，就会出现：

```
第 1 轮：真实语料里找不到该引文 → 写入 _citation_fidelity_misses.md（记为 MISS）
第 2 轮：把这份报告也当语料 → 在里面找到了自己 → 判 EXACT（通过）
```

**实测事故**：`Table H-2 or Organization-defined` 在**任何真实证据文件里都不存在**，却被判 **`EXACT`**，命中文件 `_evidence/_citation_fidelity_misses.md` 偏移 504 —— 正是它自己上一轮的未命中报告（`grep -c` = **6**，与报出的 6 条 MISS 一一对应）。

**修正后重跑的对比（同一语料、同一输入）**：

| 判定 | 修复前 | 修复后 | 说明 |
|---|---:|---:|---|
| `EXACT` | 347 | **269** | **-78 条全是假通过** |
| `MISS` | 0 | **83** | 其中 **45 条**经穷尽归因确认**只存在于工具产物里** |

**这类缺陷的特征**：越跑越「干净」（未命中的引文被报告抄一遍，下一轮就「核验通过」）、自我强化（报告越长假通过越多）、**且在人类审阅时看不出来**（报告写着「EXACT + 命中文件」，比 MISS 更可信）。

**已修（两处，互为冗余）**：

1. `walk_evidence()` 排除 `_evidence/` **顶层**的 4 个产物文件名。**只排除顶层**——`R1/raw/_body_*.md` 等 **427 个**下划线开头的文件是**真实证据**，必须留在语料内（已用 10 条单元用例正反验证）。
2. 判定处加**运行时断言**：`match.file` 一旦落在产物集内，一律钉成新判定 **`SELF_REF`**，即使排除逻辑被改坏也不算通过。

> **由此得到本项目最值得外传的一条方法学结论**：
> **核验工具的产物绝不可进入它自己的语料。**
> 任何「证据卫生」工具都必须能回答：**我写出的报告，会不会在下一轮变成我的证据？**

### 机械核验工具的第二类失效：预算式搜索的假阴性

**「未命中」不等于「不存在」。** 83 条 MISS 中 **37 条**经**穷尽式搜索**证实**逐字存在于 `_evidence/` 内**——只是工具的锚词候选预算没覆盖到。同类实测：`R8/ftc-dotcom.txt`、`R3/raw/gdpr-cellar-*.rdf` 里的句子都被判过 MISS，而这些文件**确实在语料内**（已用 `walk_evidence()` 直接验证）。完整归因见 `_evidence/` 与附录 C。

**其他已固化的假阴性成因**（都被实测撞到过）：锚串取「20 个连续字母数字」（英文散文没有这种串 → 曾致 409/426 条全判 MISS）、取最长词作锚导致候选爆炸、头部词去重破坏连续序列、证据侧不剥 markdown。**回归用例见表附录 C.4。**

### 人工假阴性：我自己在本轮犯了两次

1. 一次对**不存在的路径**执行 `grep`，退出码 **0**，制造了「证据不存在」的结论；
2. 为主交付物统计【原文】时，`grep '【原文】'` 返回 **0**——因为主交付物用**半角** `**[原文]**`（31 处），而 6 个分片用**全角** `**【原文】**`（587 处）。

> **由此加一条设计规则**：**标记形态不统一会造成静默假通过。**
> 只写一种形态的正则会对其中一类报告「0 条引文、全部通过」——**这比报错危险得多**。
> 与上面第 3 条（按行读会丢内容）同源：**工具的静默不匹配 = 伪造「不存在」。**

### 一个真实的判断失误（已更正）

R7-W3 报出一条 Amazon Ads 的「英国放松型覆写」证据，**我最初判定它不存在并要求撤回**，依据是对 HTML 与文本层检索 `mailing address` / `study and date` / `postal` 均 0 命中。
**这个判断是错的**：该内容位于 `.html` 第 1336 行、**行长 11,405 字符**，我的检索封装跳过了超长行。字节级计数显示 `mailing address` → 1、`study and date` → 1、`PO box` → 1、`email address` → 1。
**R7-W3 拒绝撤回并给出了字节级反证 —— 它是对的。** 教训：**检索工具的静默截断会伪造「不存在」的结论**，而这与伪造「存在」同样有害。E7b / E8 两项检查即为防止此类假阴性而设。

### 由此产生的两条设计规则

> 1. **任何「未找到」的结论都必须写明检索口径**（检索了哪些词、在哪个文件、用什么方法）。
>    「查不到」本身可以是结论，但**没有口径的「查不到」不是结论**。
> 2. **判定不稳定时必须标出不稳定性，并给出最终归因。** 同语料同输入，工具报出的 MISS 数在多次运行间波动；更重要的是，**它的「通过」也曾靠自证刷出来**。**唯一的解法是穷尽式复核**：83 条 MISS 逐条搜索后，37 条追回、45 条为循环污染、1 条定位到原文（行号错 2 行）。**结论：0 条编造。**
>
> **最终数字：426 条引文 → 422 条完全可判定 → 377 条核验通过（89.3%）→ 确认编造 0 条。**
> 这个 89.3% **低于**工具最初自报的 97.7%，但它是真的。**保真度核验里，一个更低的诚实数字 > 一个更高的自证数字。**
>
> 附一条**读文件系统**的教训：`ls -l` 报的字节数可能陈旧。实测同一文件 `ls -l` 说 7,876 B、`stat` 说 7,876 B，而**同哈希的另一份只有 3,780 B** —— `readdir` 属性缓存不可信，**以 `stat()` / `sha256` 为准**。

---

## 复跑与校验说明

- 所有数字均由 `research/governance/` 下的脚本从 `PRD/内容治理需求文档.md` 实测得出，命令在各文件内注明。
- 每份内部证据文件末尾都有一节「方法学自查」，记录**本次分析中我自己的测量错误及更正**。已记录的更正：
  - `01`：第一版把 `M07` 的正则误报为编译失败，实为解析器在逗号处切进了字符类
  - `02`：第一轮跑出「11/12 条规则在市场维度显著差异」，复核发现记录层存在 1.7× 伪重复
  - `02 §7`：平台维度原判「不构成维度」**被推翻**，改为「样本失衡，不可检验」——犯了「把未能拒绝原假设当成原假设成立」的错误
  - `04`：本会话曾判断「291 条数据里没有美国」，实为把 `投放地区` 的字段取值当成了真实分布；**美国有 100 条**
  - `R5`：对子任务交付的德国/欧盟法源报告做**独立复核**，首轮朴素子串匹配得出 3 条 FAIL —— **全部是假阴性**。原因是 gesetze-im-internet.de 原文以 HTML 实体编码（`&#167;` / `&#228;`）且声明 `charset=iso-8859-1`；**必须先解码实体再比对**，否则会把真引文误判成「引文不存在」。同一轮复核还出现 1 条**反向**假阴性：JRC134290 中 `EN 647` 只以列举省略式出现（`EN 645:1993, 647:1993 and 15519:2007`），正则会漏抓
  - `R5`：子任务报告只呈现 LFGB § 59(1) 的**刑事**分支，遗漏 **§ 60(1) Nr. 2 的「过失 = 行政违法」**分支（§ 59(1) Nr. 15/16/18 全部落在「Nummer 11 bis 21」区间内，而 § 59 自身无过失入罪条款）。**方向性错误也要改**：把过失情形写成刑事会高估风险一个量级 → 已更正入 R5-C10
  - `R5`：`BPA-free` 的 FTC 依据需收窄 —— 16 CFR Part 260 的正式标题是「Guides for the Use of **Environmental** Marketing Claims」，§ 260.9(b)(1) 亦明文限定 `environmental risks`，故 § 260.9(b)(2) 对 BPA 健康关切只能作**类比**，直接法源是 FTC Act § 5 与 FTC HPCG 2022 → 已更正入 R5-C11
- 外部调研分片的证据原始件存于 `_evidence/R*/`，引用时给出 URL 与本地路径。

## 已知缺口（不掩盖）

| # | 缺口 | 影响 |
|---|---|---|
| G0 | **`PRD/内容治理需求文档.md` 的「子页面1 内容审查Agent-知识库」无权限** | 那份多维表格大概率是真正的知识库。**本目录全部结论仅基于子页面2**，拿到权限后须重跑 |
| ~~G3~~ | ~~W1 的 FDA clearance 覆盖~~ | **已结案**，见 §H。16 项 clearance 中零命中 warm/massage；名字匹配的 K260864 申请人是代工厂 TPH 而非 Momcozy 主体 |
| ~~G4~~ | ~~DSA Art 34/35/42~~ | **已补取**（R2 §4.3，6 小节）。结论：DSA 对广告主是**间接**约束，正确用法是「与平台沟通时的依据引用」+「指标设计模板」 |
| ~~G2~~ | ~~NAD decision 全文~~ | **经替代路径补齐**（R2 §2.5b，三个 2026 年真实案件逐字段拆解 + `No Substantiation Received` 裁决类别）。decision 全文本身仍是**结构性不可得**（订阅制） |
| G5 | 吸奶器在中国的器械定性 | **NOT FOUND，已穷尽七条路径**（nmpa.gov.cn 全路径 412 反爬）。决定《广告法》适用第十六条还是第十七条。**不得用看似合理的答案填补** |
| G10 | 加拿大（SOR/98-282）监管定性未调研 | **Momcozy 有 14 条广告在跑，是真实空白**，且超出 R5 分片边界 |
| G20 | **Amazon BSA 新增 Section 19（automated agents / AI systems，2026-03-04 生效）只有标题级摘要** | 直接关系到 Momcozy 正在建的审查 Agent，建议优先补齐 |
| G21 | Meta 广告 strikes 的计数窗口与升级规则 | Transparency Center 无广告专属 strikes 页，**无公开原文** |
| G22 | ISO 13485 / IEC 60601-1 / ISO 10079-1 标准正文未取得 | **补齐前规则库不应把任何标准号写成「符合」** |
| G23 | **EN 1186 / EN 14372 的标题与范围未取得**（CEN 检索走 APEX POST，被其 WAF 挡为 HTTP 500）；**欧洲理事会 ResAP(2004)5 正文未取得**（coe.int / rm.coe.int / edqm.eu 对本网络出口 IP 返回 Cloudflare 403） | 三项均为**取数通道问题，不是文件不存在**，换网络出口即可。**在补齐前规则库不应引用这三项作为硅胶的依据**。与 G22 同源，建议合并处理 |
| G24 | **9 个州的 BPA 立法未核验**（IL / CT / VT / WI / WA / MD / VA / MA / NV） | 这些主机在本环境**网络层不可达** —— curl 与 web_fetch、带与不带浏览器 UA 均同样失败，且 archive.org 不可达、**无 Wayback 兜底**。BPA 结论建立在已核验的 CA / MN / NY / ME 四州上 |
