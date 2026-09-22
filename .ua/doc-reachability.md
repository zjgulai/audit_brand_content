# 文档可达性（从 README.md 与 AGENTS.md 出发，沿链接/路径引用做闭包）

已跟踪文档（.md/.mdx/.rst/.txt）：**226**
已跟踪文件总数：464

| 起点 | 闭包内文件数 | 其中文档数 |
|---|---|---|
| `README.md` | 1 | 1 |
| `AGENTS.md` | 227 | 83 |
| 两者并集 | 227 | 83 |

## 结论：**143 / 226 个文档无法从 README 或 AGENTS.md 到达**（63.3%）

也就是说：一个新人（或一个 agent）读完入口两件之后，仍然只能看到 83 个文档，剩下 143 个**没有任何入口**。

### 可达的文档（83）

- `ADR/ADR-0001-数据权威与双账本.md`
- `ADR/ADR-0002-记录级溯源与版本化.md`
- `ADR/ADR-0003-敏感样本分级准入.md`
- `ADR/ADR-0004-第一阶段范围.md`
- `ADR/ADR-0005-工具只补证据不替人过门.md`
- `ADR/ADR-0006-两段式判定而非单张词表.md`
- `ADR/ADR-0007-判定词表按规则类型过滤.md`
- `ADR/ADR-0008-机制分离白名单独立成表.md`
- `ADR/ADR-0009-语境守卫独立成表.md`
- `ADR/ADR-0010-需求知识库权威源与归一化边界.md`
- `ADR/ADR-0011-落地页内容获取的边界与节流.md`
- `ADR/ADR-0012-判定引擎产品化与处置分层.md`
- `ADR/ADR-0013-基座接口冻结与仓库入库分级.md`
- `ADR/ADR-0014-未接线守卫词的归属.md`
- `ADR/README.md`
- `AGENTS.md`
- `PMO/上游对接人表.md`
- `PMO/内容合规-阶段性复盘-20260916.md`
- `PMO/守衡-回复卡片模版与语域规程.md`
- `PMO/守衡-架构说明.md`
- `PMO/守衡-链路打通确认.md`
- `PMO/守衡-飞书打通测试报告.md`
- `PRD/PRD差异对照-20260921.md`
- `PRD/feishu/README.md`
- `PRD/feishu/内容审查Agent-PRD-v1.0.md`
- `PRD/feishu/美国市场内容治理项目-一页纸计划书.md`
- `PRD/内容治理-TUI产品提案.md`
- `PRD/内容治理需求文档.md`
- `README.md`
- `agent-skills/守衡语域/SKILL.md`
- `base/README.md`
- `research/distill/00-写作规范.md`
- `research/distill/01-大纲.md`
- `research/distill/cross-cutting-findings.md`
- `research/distill/shards/S1-ad-review-agent.md`
- `research/distill/shards/S2-ad-compliance-agent.md`
- `research/distill/shards/S3-crossborder-image-agent.md`
- `research/distill/shards/S4-rule-engine-and-scoring.md`
- `research/distill/shards/S5-video-and-methodology.md`
- `research/feishu/可达清单.md`
- `research/feishu/资源索引.md`
- `research/governance/00-调研任务书.md`
- `research/governance/01-内部证据-规则表现状审计.md`
- `research/governance/02-内部证据-维度有效性检验.md`
- `research/governance/03-内部证据-声明的判定一致性.md`
- `research/governance/04-内部证据-字段可用性与平台抽样偏差.md`
- `research/governance/05-内部证据-记录表分歧结构与错题本现状.md`
- `research/governance/R1-platform-policy-taxonomy.md`
- `research/governance/R2-adjudication-casebooks.md`
- `research/governance/R3-rule-engineering.md`
- `research/governance/R4-trust-and-safety-ops.md`
- `research/governance/R5-category-and-competitors.md`
- `research/governance/R6-peer-practice-and-standards.md`
- `research/governance/README.md`
- `research/governance/_shards/R7-W1-structures.md`
- `research/governance/_shards/R7-W2-axis-design.md`
- `research/governance/_shards/R7-W3-category-and-coldstart.md`
- `research/governance/_shards/R8-W1-source-taxonomy.md`
- `research/governance/_shards/R8-W2-elicitation-methods.md`
- `research/governance/_shards/R8-W3-errorbook-severity-gaps.md`
- `research/governance/annotations/ANN-GUIDE-001-T1.4-T2.1.2.md`
- `research/governance/annotations/CONSULT-001-engorgement-permit.md`
- `research/governance/errorbook/errorbook_schema.md`
- `research/governance/errorbook/错题本.md`
- `research/governance/skeleton/REWRITE_NOTES.md`
- `research/governance/skeleton/topic-tree-v1.md`
- `research/governance/品线维度-待产品确认.md`
- `research/governance/引擎产品化-接口盘点.md`
- `research/governance/源表口径-风险等级-变更请求.md`
- `research/governance/端到端送审-演练报告.md`
- `research/governance/规范-审核规则库完整设计.md`
- `research/kb/README.md`
- `research/kb/查询手册.md`
- `research/kb/结构分析.md`
- `research/kb/缺口表.md`
- `research/kb/需求知识库-建设方案.md`
- `research/landing/内容获取实测报告.md`
- `research/landing/方案.md`
- `research/method/Kb2Agent-方法论提炼.md`
- `research/method/codex_research-方法论提炼.md`
- `research/replay/离线复现报告-20260916.md`
- `research/star-lists-audit-report.md`
- `tools/reply-cards/contract.md`

### 不可达的文档（143，按目录归并）

<details><summary><b>skills-inventory/refs</b> — 71 个</summary>

- `skills-inventory/refs/README.md`
- `skills-inventory/refs/agentic-eval/SKILL.md`
- `skills-inventory/refs/blog-factcheck/SKILL.md`
- `skills-inventory/refs/brand-ad/brand-ad/SKILL.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/adsqa-target-answers.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/brand-hero-emotional-structure.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/future-system-montage.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/product-h3-compile.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/product-motion.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/product-visual-techniques.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/sensory-visual-prompting.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/style-research.md`
- `skills-inventory/refs/brand-ad/brand-ad/references/voice-keyword-typography.md`
- `skills-inventory/refs/brand-docx/SKILL.md`
- `skills-inventory/refs/brand-docx/reference/block-catalog.md`
- `skills-inventory/refs/brand-docx/reference/comprehension.md`
- `skills-inventory/refs/brand-docx/reference/extraction.md`
- `skills-inventory/refs/brand-docx/reference/generation.md`
- `skills-inventory/refs/brand-docx/reference/profile-schema.md`
- `skills-inventory/refs/brand-docx/reference/qa.md`
- `skills-inventory/refs/brand-docx/reference/visual-audit.md`
- `skills-inventory/refs/compliance-review-planner/SKILL.md`
- `skills-inventory/refs/copy-editing/SKILL.md`
- `skills-inventory/refs/copy-editing/references/checklist.md`
- `skills-inventory/refs/copy-editing/references/content-refresh.md`
- `skills-inventory/refs/copy-editing/references/plain-english-alternatives.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/SKILL.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/01-womenswear.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/02-home.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/03-daily-goods.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/04-pet.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/05-baby.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/06-3c.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/07-jewelry.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/08-beauty.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/09-supplements.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/10-personal-care.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/11-menswear.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/12-footwear.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/13-bags.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/categories/14-sports.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/category-playbook.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/image-quality.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/platform-specs.md`
- `skills-inventory/refs/ecommerce-image/ecommerce-image/references/set-planning.md`
- `skills-inventory/refs/iflytek-text-proofread/README.md`
- `skills-inventory/refs/iflytek-text-proofread/SKILL.md`
- `skills-inventory/refs/koc-video/koc-video/SKILL.md`
- `skills-inventory/refs/koc-video/koc-video/references/creator-direction.md`
- `skills-inventory/refs/koc-video/koc-video/references/hook-decision.md`
- `skills-inventory/refs/koc-video/koc-video/references/production.md`
- `skills-inventory/refs/koc-video/koc-video/references/script-and-shots.md`
- `skills-inventory/refs/koc-video/koc-video/references/source-routing.md`
- `skills-inventory/refs/legal-risk-assessment/SKILL.md`
- `skills-inventory/refs/seo-content-audit/SKILL.md`
- `skills-inventory/refs/seo-content-audit/references/cite.md`
- `skills-inventory/refs/seo-content-audit/references/core-eeat.md`
- `skills-inventory/refs/seo-content-audit/templates/verdict.md`
- `skills-inventory/refs/social-caption/social-caption/SKILL.md`
- `skills-inventory/refs/subtitle-correction/subtitle-correction/SKILL.md`
- `skills-inventory/refs/subtitle-correction/subtitle-correction/references/srt-format.md`
- `skills-inventory/refs/subtitle-correction/subtitle-correction/references/terminology.md`
- `skills-inventory/refs/tos-risk-checker/SKILL.md`
- `skills-inventory/refs/video-deconstruct-analyzer/video-deconstruct-analyzer/SKILL.md`
- `skills-inventory/refs/video-deconstruct-analyzer/video-deconstruct-analyzer/references/core-analysis.md`
- `skills-inventory/refs/video-deconstruct-analyzer/video-deconstruct-analyzer/references/report-template.md`
- `skills-inventory/refs/video-deconstruct-analyzer/video-deconstruct-analyzer/references/seedance-prompt-grammar.md`
- `skills-inventory/refs/video-deconstruct/video-deconstruct/SKILL.md`
- `skills-inventory/refs/video-deconstruct/video-deconstruct/references/minimax-h3-multi-ref.md`
- `skills-inventory/refs/video-transcript/video-transcript/SKILL.md`
- `skills-inventory/refs/weighted-scoring/SKILL.md`

</details>

<details><summary><b>research/distill</b> — 20 个</summary>

- `research/distill/scratch/_p10.md`
- `research/distill/scratch/_p20.md`
- `research/distill/scratch/_p30.md`
- `research/distill/scratch/_p40.md`
- `research/distill/scratch/_p5.md`
- `research/distill/scratch/_p50.md`
- `research/distill/scratch/_p60.md`
- `research/distill/scratch/_probe100.md`
- `research/distill/scratch/_probe200.md`
- `research/distill/scratch/_probe400.md`
- `research/distill/scratch/_t1.md`
- `research/distill/scratch/_t2.md`
- `research/distill/scratch/_t3.md`
- `research/distill/scratch/_t4.md`
- `research/distill/scratch/_t5.md`
- `research/distill/scratch/_t6.md`
- `research/distill/scratch/_t7.md`
- `research/distill/scratch/_t8.md`
- `research/distill/scratch/_t9.md`
- `research/distill/shards/S0-source-reading-methodology.md`

</details>

<details><summary><b>kb2agent-research/raw</b> — 18 个</summary>

- `kb2agent-research/raw/A-part1.md`
- `kb2agent-research/raw/A-企业知识助手案例.md`
- `kb2agent-research/raw/B-part1.md`
- `kb2agent-research/raw/B-part2.md`
- `kb2agent-research/raw/B-part3.md`
- `kb2agent-research/raw/C-part1.md`
- `kb2agent-research/raw/C-part2.md`
- `kb2agent-research/raw/D-part1.md`
- `kb2agent-research/raw/E-守衡落地建议.md`
- `kb2agent-research/raw/F-part1.md`
- `kb2agent-research/raw/_distill-ads.md`
- `kb2agent-research/raw/_distill-legal.md`
- `kb2agent-research/raw/_distill-medical.md`
- `kb2agent-research/raw/_sub-cx-vertical.md`
- `kb2agent-research/raw/_sub-health.md`
- `kb2agent-research/raw/_sub_ads.md`
- `kb2agent-research/raw/_sub_legal.md`
- `kb2agent-research/raw/_sub_medical.md`

</details>

<details><summary><b>research/readmes</b> — 10 个</summary>

- `research/readmes/ad_compliance.md`
- `research/readmes/ad_review.md`
- `research/readmes/contract_audit.md`
- `research/readmes/crossborder_img.md`
- `research/readmes/invoiceaudit.md`
- `research/readmes/omniguard.md`
- `research/readmes/polysafe.md`
- `research/readmes/sceneforge.md`
- `research/readmes/sinyard.md`
- `research/readmes/soe_legal.md`

</details>

<details><summary><b>research/governance</b> — 8 个</summary>

- `research/governance/R4-metrics-and-transparency-evidence.md`
- `research/governance/_scratch/R5-integration-scripts/_err.txt`
- `research/governance/annotations/annot_rater_A_notes.md`
- `research/governance/annotations/annot_rater_B_notes.md`
- `research/governance/skeleton/_data/receipts.LOSS.md`
- `research/governance/skeleton/_data/遗留对账.md`
- `research/governance/skeleton/迁移手册-机器词表.md`
- `research/governance/判定引擎产品化-实测报告.md`

</details>

<details><summary><b>PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md</b> — 1 个</summary>

- `PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md`

</details>

<details><summary><b>PMO/守衡-发送者身份修复记录.md</b> — 1 个</summary>

- `PMO/守衡-发送者身份修复记录.md`

</details>

<details><summary><b>PMO/守衡-回复截断修复记录.md</b> — 1 个</summary>

- `PMO/守衡-回复截断修复记录.md`

</details>

<details><summary><b>PMO/守衡-时间基准修复记录.md</b> — 1 个</summary>

- `PMO/守衡-时间基准修复记录.md`

</details>

<details><summary><b>PMO/守衡-查名修复记录.md</b> — 1 个</summary>

- `PMO/守衡-查名修复记录.md`

</details>

<details><summary><b>PMO/守衡-看不见的东西要说出来.md</b> — 1 个</summary>

- `PMO/守衡-看不见的东西要说出来.md`

</details>

<details><summary><b>kb2agent-research/Kb2Agent-方法论调研报告.md</b> — 1 个</summary>

- `kb2agent-research/Kb2Agent-方法论调研报告.md`

</details>

<details><summary><b>kb2agent-research/企业Agent知识库体系调研报告.md</b> — 1 个</summary>

- `kb2agent-research/企业Agent知识库体系调研报告.md`

</details>

<details><summary><b>research/feishu</b> — 1 个</summary>

- `research/feishu/README.md`

</details>

<details><summary><b>research/kb</b> — 1 个</summary>

- `research/kb/materials/202608-营销内容生命周期内容合规审核规范建设-需求框架整理.txt`

</details>

<details><summary><b>research/landing</b> — 1 个</summary>

- `research/landing/README.md`

</details>

<details><summary><b>research/method</b> — 1 个</summary>

- `research/method/调研报告-AI产品全流程方法与Kb2Agent编译链.md`

</details>

<details><summary><b>skills-inventory/SKILLS-INVENTORY.md</b> — 1 个</summary>

- `skills-inventory/SKILLS-INVENTORY.md`

</details>

<details><summary><b>tools/reply-cards</b> — 1 个</summary>

- `tools/reply-cards/README.md`

</details>

<details><summary><b>x-recovery/main-post-code-blocks.md</b> — 1 个</summary>

- `x-recovery/main-post-code-blocks.md`

</details>

<details><summary><b>x-recovery/manual-2026-PM-AI-plaintext.txt</b> — 1 个</summary>

- `x-recovery/manual-2026-PM-AI-plaintext.txt`

</details>
