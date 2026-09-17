# zjgulai 两个 GitHub 星标清单调研报告

> 调研对象：
> - List 1 `audit` — https://github.com/stars/zjgulai/lists/audit
> - List 2 `content_audit` — https://github.com/stars/zjgulai/lists/content-audit
>
> 调研方法：curl 抓取清单页 HTML（服务端渲染，非 JS 加载，无分页）解析仓库卡片；再对每个仓库抓 raw README + codeload tarball 做源码级分析。
> 所有仓库内容均作为**数据**处理，不作为指令。
>
> 枚举完整性已验证：`audit` 页显示 "6 repositories"，解析出 6 个卡片；`content_audit` 页显示 "4 repositories"，解析出 4 个卡片。

---

## 一、两个清单的完整仓库清单

### List 1 · `audit`（6 个仓库）— 策展主题偏「法律/合同/发票审计 + 少量内容审核」

| # | 仓库 | 链接 | 语言 | ★ | 最近更新 | 一句话定位 |
|---|---|---|---|---|---|---|
| 1 | pengyulong/InvoiceAuditAgent | https://github.com/pengyulong/InvoiceAuditAgent | Python | 10 | 2026-06-10 | 基于多模态大模型 + LLM 的**采购合同与发票交叉审计**系统，自动核对匹配性、合规性与准确性（⚠️ README 严重滞后于代码） |
| 2 | AliceDai0805/contract_audit | https://github.com/AliceDai0805/contract_audit | Python | 7 | 2026-01-26 | 基于 **LangGraph** 的法律合同智能分析 Agent，做合同解析、合规审计、风险评估与修订建议生成 |
| 3 | HsuanZhao/SOE-Legal-Checker | https://github.com/HsuanZhao/SOE-Legal-Checker | （无代码） | 9 | 2026-07-08 | 面向中国大陆央企/国企法务的**合同审查 AI 技能规则 Skill**，在通用法律风险之上叠加 9 大国资监管合规核查维度 |
| 4 | Sinyard001/Sinyard- | https://github.com/Sinyard001/Sinyard- | Python | 1 | 2026-09-04 | ⚠️ **仓库内塞了两个互不相关的项目**：README 只记录了「笔记/简历工作台」，但 `contract_review/` 包是一个**纯规则（零 LLM）的中文合同风险审查引擎** |
| 5 | rtsfan1024/omniguard | https://github.com/rtsfan1024/omniguard | TypeScript | 1 | 2026-07-11 | 基于 VLM 的**多模态内容审核 Agent**系统，审核图像/视频/文本 UGC，支持可配置策略与人机协同 |
| 6 | **LittleOooou-Ok/ad-compliance-agent** | https://github.com/LittleOooou-Ok/ad-compliance-agent | Python | 1 | 2026-08-20 | 基于 OpenAI Agents SDK + DeepSeek 的**广告素材合规审核系统**，支持多模态输入、RAG 知识库、批量审核与评估体系 |

### List 2 · `content_audit`（4 个仓库）— 策展主题偏「内容/素材/广告合规 + 视频质量审计」

| # | 仓库 | 链接 | 语言 | ★ | 最近更新 | 一句话定位 |
|---|---|---|---|---|---|---|
| 1 | hirogoing/PolySafe | https://github.com/hirogoing/PolySafe | TypeScript | 26 | 2026-03-17 | **多模态内容智能审核系统**：VLM 内容理解 + FAISS 语义规则匹配 + 三态处置的端到端审核 Agent 流水线 |
| 2 | SSS023-s/sceneforge-video-workflow | https://github.com/SSS023-s/sceneforge-video-workflow | （Skill 文档） | 2 | 2026-07-20 | 面向授权短视频素材的**场景感知剪辑 + 多模态质量审计 Skill**，含完整视频质量门禁与审计报告规范 |
| 3 | **augusding/ad-review-agent** | https://github.com/augusding/ad-review-agent | Python | 3 | 2026-03-30 | 审核 vivo 广告平台素材合规性的**多 Tool 编排 Agent**，目标替代 80% 人工初审；工程完成度最高的一个 |
| 4 | xiaov971023/crossborder-image-agent-New- | https://github.com/xiaov971023/crossborder-image-agent-New- | JavaScript | 18 | 2026-06-06 | 面向跨境电商卖家的**商品图生成与平台规则合规审核工作台**（Amazon/Temu/Ozon/Noon/Rakuten） |

### ⚠️ 四个重要校正（都会影响结论）

1. **`omniguard` 与 `PolySafe` 是同一个项目**。两者 README 逐字节 diff 后**仅第 1 行标题名不同**（`OmniGuard` → `PolySafe`）与末尾换行差异，其余 277 行完全一致。因此 10 个仓库实际对应 **9 个不同项目**。
2. **两个清单整体星数极低**（1–26 ★），没有高星权威项目。真正有工程深度的是低星的 `ad-review-agent`（★3）与 `ad-compliance-agent`（★1）；高星的 `PolySafe`（★26）反而是学生作业级完成度。**星数不能作为质量信号。**
3. **`InvoiceAuditAgent` 的 README 严重低估了实现**。README 自 2025-10-21 未更新，仍声称"仅完成需求分析与目录结构"；但代码在 2026-05/06 有多次功能提交，实测包含 42.7 KB 的 `ai_service.py`（百度 OCR + DeepSeek + Tesseract 三级降级链）、4 个已实现 Agent、真实 Vue3 页面与集成测试。**是完整系统，不是骨架。**
4. **`Sinyard-` 仓库里塞了两个互不相关的项目，README 只记录了一个**。GitHub description 写"合同审查工具"、README 写"笔记·简历工作台"，而代码树里 `server.py`（简历工具，端口 8787）与 `webapp.py`（**智能合同审查助手**，端口 8765）+ `contract_review/` 完整包**同时存在**；2026-09-04 的一次批量上传用简历项目的文档覆盖了合同项目的 README。**真正与审计相关的规则引擎被文档藏了起来。**

> **方法论教训（重要）**：本次调研中，**README 与清单描述在 4 个仓库上都不可靠**（omniguard 重复、InvoiceAuditAgent 低估、Sinyard 张冠李戴、contract_audit 描述与实际仓库名不符）。**任何仓库评估都必须核对代码树，不能只读 README。**

---

## 二、每个仓库的「核心实践 / 核心能力」

### 1. LittleOooou-Ok/ad-compliance-agent ★ 最高相关之一

**核心实践 / 核心能力**
1. **证据驱动的审核原则体系（写进 orchestrator prompt）**：明文规定「敏感词命中 ≠ 违规」「规则是主要裁决依据」「案例只能辅助判断」「规则相关度 ≠ 违规概率」「风险 ≠ 违规」，并要求建立 `广告表达 → 对应规则 → 规则适用条件 → 是否满足违规条件 → 结论` 的显式推理链路。
2. **Claim 分类法**：先做广告语义解析，抽取 Claim List 并逐条打标签——`absolute_claim / efficacy_claim / fact_claim / comparison_claim / price_claim / safety_claim / normal_marketing`。
3. **证据状态四分**：对真实性主张区分 `evidence_confirmed / evidence_missing / evidence_conflict / not_required`，并明确规定 **「无法验证真实性 ≠ 虚假宣传」，信息不足时优先 manual_review**。
4. **三维加权风险评分**：合规性 50% + 真实性 30% + 安全性 20%，每维 0–100，等级 low/medium/high/critical；`scoring.py` 给出确定性实现（敏感词≤35 + 规则命中≤35 + 案例参考≤10 + 语义正则≤20 = 100），并含 `FUZZY_PATTERNS` 模糊词表（绝对化/功效承诺/虚假背书/诱导消费）与时间-功效正则（如 `\d+天.{0,2}(见效|变白|瘦身)`）。
5. **结论判定优先级显式化**：`明确违规证据 > 规则适用性 > 维度风险评分 > 综合风险分`。pass 需「无明确违规 + 综合<40 + 三维无重大风险 + 无重要信息缺失」；reject 需「合规≥80 且有规则依据 / 明确 high 违规 / 综合≥80 且有违规证据」；其余落 manual_review。
6. **完整评测体系**：100 条测评集（pass 50 / reject 30 / manual_review 20，带 difficulty 标注）+ 混淆矩阵 + accuracy/precision/recall/F1/误拒率/漏放率，且**将 manual_review 在混淆矩阵中按 reject 处理（保守策略）**；`docs/evaluation_report.md` 给出实测结果（97% pass、平均风险分 17.7、平均置信度 81%）并做**双向误差分析**（高风险通过=可能漏检 6 例）。
7. **结构化规则知识库**：`ad_law_core.md` 每条规则固定六字段（规则内容/法规依据/严重程度/违规示例/关键词），另有 `prohibited_words.md`、行业规则（education/finance/food/medical）、`platform_rules.md`；敏感词库 150 词，每词带 `word/category/severity/rule_ref/alternatives`（**含替换建议**）。

**技术栈**：OpenAI Agents SDK + DeepSeek（`temperature=0.1`）· DashScope qwen3.7-text-embedding · Chroma 向量库 · FastAPI · SQLite · 前端 web/

**与内容审计相关性**：**高度相关**。这是清单中唯一把「广告合规 + 多维度评分 + LLM-as-judge 式结论 + 评测集」做完整的项目，且缺陷类型（绝对化用语、虚假宣传、功效承诺）与美国市场的 FTC substantiation 问题同构。

**具体解决什么**：把「广告素材是否合规」从人工经验判断变成**可解释、可评分、可评测**的自动流程——既给出结论，也给出规则依据、风险分与修改建议。

---

### 2. augusding/ad-review-agent ★ 最高相关之一 · 工程完成度最高

**核心实践 / 核心能力**
1. **6 个审核 Tool 按优先级编排**：`TextViolationChecker(1) → ImageContentChecker(2) → LandingPageChecker(3) → QualificationChecker(4) → PlatformRuleChecker(5) → ConsistencyChecker(6)`；每个 Tool 声明 `trigger_condition`（always / has_visual_content / has_landing_page_url / category_in_qualification_required / has_multiple_content_types）与 `skip_reason_when_inactive`。
2. **声明式约束外部化**：`harness/constraints.yaml` 把**所有硬编码阈值和决策规则**外部化，甚至**在注释里标注源码文件与行号**（如 `review_agent.py → _determine_verdict() (L564-L623)`），并在文件头写明「修改后需 1. 更新 version 2. 跑 Eval 验证指标无回归 3. commit message 注明原因」。`constraint_loader.py` 用 `lru_cache` 缓存 + 启动时 fast-fail 校验必需 section。
3. **双轨置信度聚合**（`decision_engine.py`）：**有违规时取违规维度的 max**（任一维度确信即可退回）；**无违规时取核心维度的 min**，但**排除 non_drag 维度**（`image_safety`、`consistency` 无违规时不拉低整体以免阻止自动通过）；全部降级时兜底 `0.5`。
4. **提前终止（early termination）**：当某 Tool 发现 `severity=high` 且 `confidence > 0.9` 时，跳过后续低优先级 Tool 以省成本与时间，被跳过的维度写入 `skip_reasons` 并标注原因模板。
5. **降级是一等公民**：`BaseTool(ABC)` 强制子类实现 `execute()` 与 `_fallback()`，且规定 **`_fallback()` 不允许抛异常，必须返回 `is_fallback=True` 的合法 Output**——单点故障不炸全局；降级维度始终不参与置信度计算。
6. **规则热更新 + 版本化**：`rules_loader.py` 实现「数据库优先（`RuleVersion` 表带 `version`/`is_active`）+ JSON 文件保底 + 5 分钟缓存」，支持运营后台改规则即时生效。
7. **跨维度一致性检测（品牌/素材一致性最接近的先例）**：`consistency_rules.json` 定义 `creative_consistency`（文案 vs 图片/视频）与 `landing_consistency`（文案/图片 vs 落地页），检查维度含 `brand_identity`（品牌身份冲突）、`product_category`（类别错位）、`price_promise`（价格承诺，带 `trigger_keywords`）、`product_identity`；每个维度同时给出 `examples_violation`、`examples_normal` 与全局 `non_violation_patterns`（如「图片是使用场景/氛围图，文案是功能/品牌介绍」属正常），并设**分层置信阈值**（reject 0.85 / review 0.70）。
8. **Golden Dataset + 回归门禁**：`evals/golden_dataset/` 四个 jsonl 分桶——pass 30 / reject 35 / review 25 / **adversarial 15**，共 105 条；案例 schema 为 `{case_id, category, creative_type, content{title,description,cta_text}, expected_verdict, expected_violations[{dimension, regulation_ref, severity}], notes, source}`。`regression_check.py` 对 accuracy / FN rate / FP rate / automation_rate 设**回归阈值门禁**（下降超阈值 → `exit 1` 阻止合并）。
9. **对抗性测试集**：adversarial 桶专门覆盖规避手法——拼音替换（`zui`→最、`di yi`→第一）、标点拆字（`保.本`、`0⃣风险`）、emoji 替换（`收⬆️益`）。
10. **违禁词库带法规锚点**：`forbidden_words.json` 每组含 `description / severity / regulation_ref（如《广告法》第九条第三款）/ words[] / patterns[]`（正则，如 `下载量超.*亿`）。

**技术栈**：Python + FastAPI + SQLAlchemy(async) + SQLite/Redis · DeepSeek（LLM）+ Qwen-VL（视觉）+ 阿里云内容安全（第二证据链）· loguru · Pydantic · Docker Compose · 自建 harness（constraint_loader / model_router / tracer）

**与内容审计相关性**：**最高**。它同时具备「审核规则引擎 + 阈值外部化 + 多 Tool 编排 + 置信度仲裁 + 评测集 + 回归门禁」全部要素。

**具体解决什么**：替代 80% 的广告素材人工初审；输入支持 HTTP/MQ/人工三种适配器，素材含文案、图片/视频、落地页 URL、行业资质；输出 pass/RETURNED/REVIEW 及违规清单。自述限制：视频审核约 26 秒（下载+关键帧抽取+逐帧视觉分析）、视频上限 500MB、落地页反爬会降级人工复核。

---

### 3. xiaov971023/crossborder-image-agent-New-

**核心实践 / 核心能力**
1. **平台 × 图片类型 × 维度 的规则注册表**（`backend/src/rules/platformRules.js`，`RULE_VERSION = 'v3.2'`）：6 个平台（amazon/temu/noon/ozon/rakuten/marketplace）× 8 种图片类型（main/feature/size/compatibility/package/lifestyle/detail/variant）；每种组合展开为 `background{allowed,recommended,strict}` / `text{allowed, forbiddenLanguages:['Chinese'], forbiddenPatterns:[...]}` / `product{mustShowProductClearly, mustNotCropProduct, recommendedProductAreaPercent}` / `forbiddenElements` / `file{minWidth,minHeight,formats}` / `severity{text, chineseText, nonWhiteBackground, watermark, price, promotion, sellerLogo, unconfirmedCertification, unconfirmedCapacity, sourceMock}`。
   - Amazon 主图规则最严：纯白底、`strict: true`、禁止文字、产品占比 85%、禁道具禁场景。
2. **全局禁列 + 认证证据要求**：`globalForbidden = [price, discount, promotion, watermark, seller_logo, fake_certification, best_seller_badge, review_stars, unsupported_logo, chinese_text]`；`certificationRules = { requireEvidence: true, forbiddenWithoutEvidence: ['FDA','CE','FCC','RoHS','warranty','waterproof','medical claims'] }`——**这组正是美国市场的合规雷区**。
3. **确定性规则层 + VLM 层的混合审核**：`ruleBasedReview.js` 用正则做确定性判定——中文 `[\u3400-\u9fff]`、价格 `([$€£¥]|USD|EUR|AED|SAR|JPY|RUB|\d+\.\d{2})`、促销 `(discount|coupon|sale|best seller|no.1|limited time|free shipping|% off)`、认证 `(fda|ce|fcc|rohs|certified|warranty|guarantee|waterproof|medical|health)`；再由 `RealVisionReviewProvider`（Gemini/OpenAI/Qwen 可切）做视觉复核，最后 `mergeReviewData` 合并。
4. **Claim 必须带证据**：`hasVisibleTextEvidence()` / `hasAnyEvidence()` 校验 `task.fieldEvidence`，无证据即报违规，`fixSuggestion` 为「Remove the claim or add visible/user-confirmed evidence before using it in image copy.」——**未确认的认证/容量声明直接判 high**。
5. **规则快照冻结进任务**：`targets[{ ..., rulesSnapshot }]` 把当时的平台规则快照存进任务记录，配合 `RULE_VERSION` 与 `REVIEW_PROMPT_VERSION='review-v3.1'` 实现**审计可复现**。
6. **可追溯的 issue 结构**：`{type, category, level, message, evidence[], imageArea, ruleId, platformId, imageType, categoryId, fixSuggestion}`，`ruleId` 采用 `${platformId}.${imageType}.${type}` 命名（如 `amazon.main_image.text`）。
7. **对 AIGC 生成物单独设风险项**：`isMockPreview`/`provider==='mock'` → `mock_preview`（high，mock 图不得作为最终上架素材）；`realGenerationMode==='text_to_image'` 或 `productGeneratedByAI` → `subject_preserve_risk`（high，文生图**不保证产品外观保真**）。
8. **三 Provider 抽象 + mock/real 可切**：`VisionProvider.recognize` / `ImageProvider.generate` / `ReviewProvider.review`，统一返回 `{provider, model, durationMs, status, error, data}`；`AI_PROVIDER/VISION_PROVIDER/IMAGE_PROVIDER/REVIEW_PROVIDER` 环境变量切换，便于离线测试。
9. **任务状态机 + 跨维度一致性**：`uploaded → recognized → confirmed → rules_selected → planned → generated → reviewed → exported`，非法跳步返回 HTTP 409；产品信息确认与字段证据前置，避免用未确认信息生成素材。注意 `selectRules`/`createPlans`/`generateImages` **允许从自身状态重入（幂等重跑）**，只有 `recognize` 严格限定 `UPLOADED`。
10. **品类规则第二层（`categoryRules.js`，`CATEGORY_RULE_VERSION='v3.3'`）**：在平台规则之上叠加 `criticalFields / highRiskFields / evidenceRequiredFields / allowedClaims / riskyClaims / **forbiddenClaimsWithoutEvidence** / imageTypeGuidance`。设计意图表述极清晰——**平台规则回答「这个平台/图片类型允许什么」，品类规则回答「这类商品哪些宣称有风险」**。唯一细化品类 `electronics_storage` 含 9 条 `forbiddenClaimsWithoutEvidence`（如 `up to 1000MB/s`、`CE certified`、`military grade`）。
11. **6 级严重度 + 动作类型映射**：issue 层严重度扩为 `{fatal:0, high:1, medium:2, low:3, info:4, mockInfo:5}`，派生 8 类 `category`（mock/platform/text/field/realGeneration/matting/provider/unknown）与 11 个中文字段标签（容量/尺寸/接口类型/认证/保修…）；语义位 `isRealComplianceRisk` / `isMockOnly` / `canAutoFixLater` / `requiresManualConfirm`（`fatal|high` → true）。修复建议输出 9 种 `actionType`（`removeText / removeClaim / confirmFieldEvidence / editTextLayout / regenerateMock / regenerateRealSample / manualCheck / skipMockOnly / noActionNeeded`）+ `priority = severityRank + (requiresManualConfirm ? 0.1 : 0.2)`，并汇总 `buildFixSummary()`（自动可修数 / 需人工数 / 仅 mock 数）。
12. **证据核对的严格定义**：`hasVisibleTextEvidence()` 要求 `task.fieldEvidence[field]` 中存在 **`source === 'visible_text'`** 且文本包含该值的条目——**只有"画面上真的看得见"才算证据**，用户填写的信息不算。另有硬阈值：可见 `textElements > 8` → `too_much_text`；任一 `fontSize < 22` → `small_text`。双引擎合并用 **OR 语义**：`pass = rulePass && visionPass && !issues.some(level==='high')`，风险取 `maxRiskLevel`。

**技术栈**：React + Vite + Tailwind（前端）· Node.js + Express · Multer 上传 · sharp 图像处理 · archiver 打包 · 本地 JSON 存储 · node:test + supertest

**与内容审计相关性**：**高度相关**。这是清单中唯一把「平台规则结构化 + 跨境/美国市场认证合规 + 生成内容风险标记 + 规则快照」四件事同时做出来的项目。

**具体解决什么**：跨境卖家在上架前把商品图按目标平台规则生成并**自动合规预检**，输出带 `riskLevel`、`issues`、`fixSuggestions` 的结构化报告，降低被平台下架/驳回的风险。

---

### 4. hirogoing/PolySafe（= rtsfan1024/omniguard）

**核心实践 / 核心能力**
1. **端到端三段流水线**：`内容理解（调用 VLM 提取风险点）→ 策略判断（FAISS 语义向量检索匹配审核策略）→ 处置与上报（block / pass / review + 全程 Agent 执行日志）`。
2. **统一多模态契约**：图片、视频、文本走**同一个 prompt、同一份 JSON 输出契约**——`{violation_detected, violation_types[], confidence, risk_description}`；图片用 `input_image`、视频用 `input_video`、文本用 `input_text` 承载，实现三模态同构处理。
3. **策略-规则两级模型**：`Policy(name, description, is_active) → Rule(policy_id, name, description, violation_type, action, priority, is_active)`；种子数据含 **12 个策略 + 30 条规则**，覆盖色情/暴力/仇恨/垃圾广告/违法违规/隐私泄露/未成年人保护/自伤自残/网络欺凌/版权侵权/**虚假宣传**/平台秩序。其中「虚假宣传与夸大承诺策略」含 `绝对化用语检测`（"包治百病""稳赚不赔"）与 `高风险夸大宣传检测`。
4. **三段式阈值判定**（`rule_engine.py`，极简 30 行）：`confidence ≥ 0.8 且命中拦截规则 → block`；`confidence ≤ 0.3 且无规则命中 → pass`；其余 `→ review`；规则命中需 `similarity > 0.3`。
5. **批量任务与人机协同**：`Batch + N 个 Task` 并行，自动识别文件类型（图片/视频/文本文件 pdf/docx/txt/md/csv/json）；review 状态推送人工复核，复核结果可回写系统。
6. **运营侧策略配置 + 数据看板**：后台可增删改策略规则，**策略变更后自动重建 FAISS 向量索引**；看板含审核总量、通过率/拒绝率、每日趋势、违规类型分布。
7. **降级稳健性**：模型返回非 JSON 或解析失败时返回安全默认值（`violation_detected=false, confidence=0.0, risk_description="解析失败"`），不会 500。

**技术栈**：FastAPI 0.115 + SQLAlchemy 2.0 + SQLite + FAISS 1.8 + sentence-transformers（`paraphrase-multilingual-MiniLM-L12-v2`）· 豆包 Ark 多模态大模型（`/responses` 接口）· React 18 + TypeScript 5.6 + Vite 5.4 + Tailwind 3.4 + shadcn/ui + Recharts

**与内容审计相关性**：**中等偏上**。多模态审核主流程与三态处置可借鉴，但**规则表达过于薄弱**——`Rule` 只有 `name/description/violation_type/action/priority` 六字段，没有可判定条件、没有法规依据，命中完全依赖向量相似度（描述文本越长越容易误命中），且 VLM prompt 是通用 UGC 语境（"违规类型包括：色情、暴力、仇恨言论…"），**不适用于商业广告/品牌合规**。

**具体解决什么**：把海量 UGC 的三态初审自动化，降低人工审核成本，并提供可配置策略与可视化运营界面。

---

### 5. SSS023-s/sceneforge-video-workflow ★ AIGC 视频 benchmark 的方法论样板

**核心实践 / 核心能力**
1. **视频「质量门禁」清单（8 项）**：能否从头到尾**完整解码**；是否存在异常黑帧、长冻结、非预期重复、黑屏补时长；声画时长差是否在阈值内；原音轨/字幕轨/数据轨是否按要求移除；烧录字幕是否在**安全区**且时间线单调无重叠；输出分辨率/帧率/SAR/像素格式/编码/响度是否符合交付规范；审计报告是否记录算法版本/参数/阈值/限制；开源目录是否通过路径/凭据/隐私扫描。
2. **可解释的相似度指标体系**：pHash（32×32 灰度→DCT→左上 8×8 低频→中位数二值化→64 位）+ dHash（9×8→水平相邻梯度→64 位），综合 `0.72×pHash + 0.28×dHash`；**多视图规范化**（原画 / 中心裁切 / 9:16 与 3:4 前景 / 去底部字幕区）以降低边框、裁切与字幕覆盖干扰；ORB 局部特征（≤500 点、Hamming、KNN k=2、Lowe Ratio `first < 0.75×second`）补强缩放/裁切/遮挡场景。
3. **音频指纹**：11025 Hz 单声道 PCM → 2048 点 FFT、1024 hop、Hann 窗 → 80 Hz–5 kHz 分 16 个几何频带 → 频带能量与时间差分 → **31 位局部指纹** + 滑窗时间偏移搜索；可叠加 Chromaprint 作为第二证据链。
4. **重复帧与媒体完整性审计**：黑帧、像素级完全重复、dHash 相邻近重复、连续冻结段、非相邻完整复现、首尾循环候选、**全片实际解码帧数**（不只信容器元数据）、音视频时长差、轨道参数。
5. **审计报告三件套 + 报告原则**：输出 `audit/{report.json, frame_metrics.csv, report.md}`；原则为「记录算法、抽样频率、阈值和版本」「**区分事实、指标和推断**」「**为每个告警保留时间码**」「不声称本地指标代表第三方平台内部系统」「SHA-256 用于完整性，MD5 仅作兼容性记录」。
6. **Human-in-the-Loop 与合规边界**：确定性环节自动化，审美/语义/授权判断保留人工确认；明确禁止「用随机噪声、不可见扰动、无意义滤镜制造差异」以及「把 MD5 改变包装成原创证明」。

**技术栈**：Python 3.10+ · FFmpeg/FFprobe · OpenCV · NumPy · Pillow · Chromaprint · SRT/ASS · JSON/CSV/Markdown 报告 · SQLite（原型）· 可选 OpenCut/剪映适配器与 TTS 适配器

**与内容审计相关性**：**方法论高度相关，产品形态不相关**。它不是审核系统，而是「视频再创作 + 质检」框架；但它给出了**视频质量审计的指标定义、门禁清单与报告规范**——正是 AIGC 视频 benchmark 需要的骨架。

**具体解决什么**：让短视频批量再创作过程**可解释、可配置、可审计**，并在交付前用统一门禁拦截黑帧/冻结/音画不同步/字幕越界等硬缺陷。

> 注意：其 Roadmap 中「**增加可重复的基准测试与合成测试集**」仍为未勾选状态——即该项目**只提供了方法，没有落地 benchmark**。这正是 Momcozy 项目要补的空白。

---

### 6. HsuanZhao/SOE-Legal-Checker

**核心实践 / 核心能力**
1. **纯 Prompt/规则 Skill 形态**：仓库只有 `skill.md`（254 行）+ `examples/` + CHANGELOG/LICENSE，**无任何代码**——是「规则即文档」的极简范式，可直接导入支持自定义 Skill 的 AI 助手。
2. **双层审查框架**：同时覆盖**合同条款本身的法律风险**与**缔约过程/决策程序的合规性**（"既看条款，也看程序"）。作者明确判断：程序性瑕疵"**往往比条款措辞更容易引发问责**"。并**硬性规定报告章节顺序**——「国资合规专项核查」必须置于「风险分析」之后、「缺失条款」之前。
3. **9 大国资专项核查维度**（以表格逐项展开）：招标采购合规、三重一大决策、国有资产交易审批、关联交易审查、廉洁风控、境外投资/涉外合规、合规前置审查留痕、国有资产保值增值、信息披露与保密衔接。每项都写成**「是否…？若是，是否…？」的条件追问链**，并点明具体作弊手法术语（"招大定小""明招暗定""阴阳合同""影子公司"）。
4. **"先定位再审查"的前置门禁**：第一步强制识别 4 项背景——①企业属性（央企本级/子企业/地方国有独资/控股/参股）②合同类型（8 类，决定用哪套清单）③是否属依法必须招标项目 ④金额与决策层级；并写明「**如企业属性、合同类型或立场不明确，应先询问用户，再开展详细审查**」——把追问固化为流程步骤，避免用错清单。
5. **⭐ 惯例基准表 + 黄/红双阈值（最精巧的设计）**：把主观判断锚定到**可判定数字**，共 8 行。例如：
   | 条款 | 惯例/合规要求 | 黄色预警 | 红色预警 |
   |---|---|---|---|
   | 工程履约保证金 | 不超过合同价 3% | 3–5% | 超过 5% 或未约定退还条件 |
   | 采购合同预付款比例 | 一般不超过合同价 30% | 30–50% | 超过 50% 且无预付款保函 |
   | 工程款支付周期 | 一般不超过验收后 60 日 | 60–90 日 | 90 日以上或无明确约定 |
   | 关联交易定价说明 | 有独立评估/市场比价支撑 | 仅内部测算无外部依据 | 无任何定价依据说明 |
   **这是抑制 LLM 定级漂移最有效的手段**——先查表，再定级。
6. **风险等级的两种正交表达**：逐条款用 emoji 三档（🔴高 / 🟡中 / 🟢低）；**国资专项则不用等级而用 5 种结论态**——`⚠️需关注 / ⚠️待补充材料 / ⚠️建议补充 / 待确认 / 不适用 / ✓符合`。比单一分级信息量大得多。风险信号表采用**左列可观测事实 + 右列法律后果与责任主体**的配对写法（如「强制招标项目未招标或以"战略合作"名义规避招标」→「违反《招标投标法》第 49 条，可处合同金额千分之五至千分之十罚款，并可能追究相关人员责任」）。
7. **结构化报告骨架**：执行摘要 + 关键条款风险分析 + **国资合规专项核查表（三列：核查维度 / 结论态 / 依据说明，说明列必须写判断理由）** + 缺失条款提示。
8. **⭐ 三条反幻觉底线（可直接抄进任何审计 Agent 的 system prompt）**：
   - 「对是否落入强制招标范围、是否构成关联交易等**依赖内部信息难以从合同文本本身判断的，应明确提示需要用户提供补充信息核实，不得臆断**」
   - 「仅依据合同文本及用户提供的信息进行分析，**不得编造决策文件、招标文件等不存在的材料内容**」
   - 「审查报告应包含『已审查、可接受』及『✓ 符合』的条目，**避免只列风险不列结论**」
9. **明确的免责与边界声明**：「仅为风险识别参考，不能替代企业内部合规审批、总法律顾问审查或外部律师意见」。

**技术栈**：无（Markdown 规则文件 + MIT 许可）

**与内容审计相关性**：**低**（领域是法律合同，不是内容合规），但**规则组织方式高度可迁移**。

**具体解决什么**：把资深法务脑中的「程序性合规检查表」显性化为 AI 可执行的规则文档，让非专家也能做系统性排查。

---

### 7. AliceDai0805/contract_audit

**核心实践 / 核心能力**
1. **⭐ 人工审核闸门做进状态机（最值得借鉴的一点）**：`graph.py` 编译时用 `interrupt_after=["risk_evaluator"]` + `MemorySaver()` checkpointer——在风险定级后**强制暂停**，`main.py` 演示了人工读取 `app.get_state(config)` 的 `snapshot.next`、确认/改写状态后再 `app.stream(None, config)` 续跑。这是"机器初筛 → 人工终审 → 放行"的现成实现，比在业务层自己拼审批流干净。
2. **LangGraph 显式状态机 + 条件路由**：`contract_parser → compliance_auditor → risk_evaluator → {route_risks} → redline_generator | final_assembler → END`；`route_risks` 判定 `any(r.get("level") == "High")` ——**只有 High 风险才触发最贵的修订生成**，Medium/Low 直接跳过，省 LLM 调用。
3. **显式状态契约**：`AgentState(TypedDict)` 7 字段——`raw_text / metadata / clauses / audit_results / risks / revisions / error_log`。⚠️ 但注意 `import operator` 引入后**未使用**，没有任何 `Annotated[list, operator.add]` reducer，意味着节点返回是**覆盖而非累加**，这正是 4 个节点都手写 `state.get("error_log", []) + [...]` 兜底的原因（一个可避免的设计缺陷）。
4. **防幻觉的解析约束**：parser 的 prompt 明确「**必须提取原文段落，不得改写。若条款缺失则返回 null**」——抑制审计幻觉的有效 prompt 手法。
5. **多入口交付**：Streamlit Web UI（494 行）+ 命令行 + **ReportLab PDF 报告导出**（433 行，含 `register_chinese_fonts()` 中文字体处理与封面/条款/审计结果/风险/修订各章节渲染）。
6. **LLM 可插拔 + Mock 兜底**：`utils/llm_factory.py` 的 `MockLegalLLM` 在无 `OPENAI_API_KEY` 时自动降级，其实现是**按 system prompt 里的角色串做关键词匹配**返回固定 JSON——让 CI/演示在无密钥时也能跑通全链路。支持 OpenAI / 智谱 GLM-4 / 任意 OpenAI 兼容接口。

**⚠️ 审计内核很薄（需明确认识）**
- **审计规则只有 3 条，且硬编码在 prompt 里**（`nodes/auditor.py:31-35`）：`(1) 支付期限 ≤ 30天；(2) 甲方付费后拥有 IP 完整权；(3) 责任限制：最高赔偿额不超过合同总额 120%`。全仓 `grep -rn "benchmark|rule|RULE" --include=*.py` **只有这一行命中**——无 `rules/` 目录、无 YAML/JSON 规则、无阈值配置、无法条引用。
- `AuditResult` 模型仅 3 字段 `{topic, is_compliant, gap_description}`——**没有规则 ID、没有严重度、没有证据定位**。
- `final_assembler_node` 函数体只有 `# 这里可以做格式化报告的工作` + `return {}` ——**最终汇总节点是空实现**，报告实际由 `ui.py`/`pdf_generator.py` 从 state 各字段拼装。
- README 声称「标注法律依据」，**代码中无对应实现**；README 的 clone 地址写的是 `AliceDai0805/legal_agent.git`，与实际仓库名 `contract_audit` 不符。
- 全部 9 次提交集中在 **2026-01-26 一天内**（初始化 + 8 次 bugfix），此后未更新。

**综合判定**：**「工程外壳真实，审计内核薄」**——不宜称为纯骨架（LangGraph 图、HITL 中断、UI、PDF、容错都真实存在），但也绝不能当作生产系统。它解决的是**流程编排与交付形态**问题，不是审计知识问题。

**技术栈**：LangChain + **LangGraph**（`StateGraph` / `MemorySaver` / `interrupt_after`）· Streamlit · ReportLab · langchain-openai / langchain-google-genai · Python 3.9+

**与内容审计相关性**：**低**。规则完全内嵌在节点 prompt 中，**未外部化、不可枚举、不可版本化**，也没有评测集与严重度阈值——是清单中架构最弱的一类形态。**它与 `crossborder-image-agent` 用规则注册表解决问题构成绝佳的反面对照。**

**具体解决什么**：把合同审查的「解析→审计→评估→改写」四步流程化，并产出可交付的 PDF 审计报告。

---

### 8. pengyulong/InvoiceAuditAgent

> ⚠️ **重要校正：README 严重滞后于代码，这不是骨架仓库。** README 自 2025-10-21 未更新（仍显示"仅完成需求分析与目录结构"），但代码在 2026-05-02 → 2026-06-10 间有多次功能提交，实测为**真实实现的完整系统**。

**核心实践 / 核心能力**
1. **确定性规则先行 + LLM 叠加的两段式交叉验证**（`backend/app/agents/cross_validator.py`）：`CrossValidator._execute` 先跑四条确定性规则，再把结果交给 LLM 做语义补充——`_check_amount_consistency`（合同总额 vs 发票总额）、`_check_party_match`（买卖方名称逐张比对）、`_check_duplicates`（发票重复）、`_check_item_coverage`（合同商品集合 − 发票商品集合）。
2. **带阈值分档的金额一致性判定**：差异率 `>20%` → `severity: high`（"金额严重不符"）；`>5%` → `medium`（"金额存在差异"）；每档附 `description`（给出具体数字与百分比）与 `recommendation`（如"请核实是否存在未上传的发票或合同金额有误"）。当事人名称不一致、发票重复直接判 `high`。
3. **可解释的加权评分公式**（`_calculate_score`）：基础分 1.0，每个 `high` −0.15 / `medium` −0.05 / `low` −0.01，再**乘以覆盖率因子** `min(coverage/100, 1.0)`，下限 0.0——即"问题越严重扣分越多"且"未覆盖的商品项按比例折算"，比单纯计数更合理。
4. **三态状态判定**（`_determine_status`）：存在 high → `不合规`；存在 medium → `部分合规`；否则 → `合规`。与内容审核的 pass/review/reject 三态同构。
5. **四阶段 Agent 编排**：`CoordinatorAgent`（含进度回调映射）编排 `ContractAnalyzer` → `InvoiceAnalyzer` → `CrossValidator`，基础类 `base.py` 统一 Agent 接口。
6. **多级 OCR 降级链**（`services/ai_service.py`，42.7 KB）：`BaiduOCRClient`（百度增值税发票专用 OCR，AK/SK 认证）→ `DeepSeekClient` → 本地 `_run_tesseract_ocr` + `_parse_invoice_text_locally` + `_parse_vat_invoice_result`。**外部服务不可用时仍能产出结果**，是"降级是一等公民"的完整落地。
7. **完整的前后端与实时进度**：Vue3 前端有真实页面（`views/Audit/Upload.vue` 22 KB、`Processing.vue` 27 KB、`Results/index.vue` 38 KB），后端 FastAPI + WebSocket 推送进度，另有 `tests/test_integration.py`、`test_frontend_components.py` 集成测试。

**技术栈**：Vue 3 + TypeScript + Element Plus + Pinia + Vite（前端）· FastAPI + WebSocket + SQLite/PostgreSQL + Redis + Celery（后端）· PaddleOCR/百度 OCR + Tesseract + DeepSeek（AI）

**与内容审计相关性**：**中等**。领域是财务审计而非内容审计，但**"确定性规则先行 + LLM 补充 + 加权扣分 + 三态判定 + 多级降级"这套骨架与内容审计完全同构**，是清单中第二完整的"审计 Agent 流水线"。

**具体解决什么**：自动核对采购合同与发票的匹配性、合规性与准确性，输出带具体差异数字、严重度与处理建议的审计报告。可迁移的核心思路是「**交叉验证**」——映射到内容审计即「文案主张 ↔ 画面内容 ↔ 落地页/详情页三方一致性核对」。

**⚠️ 教训**：README 的完成度声明可能与代码严重不符。调研时必须核对代码树，不能只读 README（本报告初稿即因此误判）。

---

### 9. Sinyard001/Sinyard- ⚠️ 仓库内实际有两个项目，README 只记录了一个

> ⚠️ **重要校正**：这不只是"README 跑题"。仓库的 GitHub description 写"合同审查工具"，README.md / 使用说明.md 描述的是"笔记·简历工作台"，而代码树里**两个项目同时存在**：
> - `server.py`（32 KB）docstring = "本地笔记 · 简历工作台 后端服务"，端口 8787 —— **与 README 匹配**
> - `webapp.py`（10 KB）docstring = "**智能合同审查助手（Web 版）本地服务**"，端口 8765 —— **README 完全没提**
> - `contract_review/` 完整包（16 个模块）+ `web/` 前端 + `tests/test_review.py`
>
> 提交历史显示：2026-09-03 提交合同工作台，2026-09-04 又用批量上传覆盖进来了笔记/简历项目的 README、使用说明、server.py、index.html——**文档只留下了后者的痕迹，把真正与审计相关的能力藏了起来**。

**核心实践 / 核心能力（指 `contract_review/` 包）**
1. **纯规则、零 LLM 的可解释风险引擎**（`risks.py`，约 380 行）：不调用任何模型，完全靠正则 + 条款分类做判定——这是清单中**唯一的"硬规则引擎"实现**，结果 100% 可复现、可单测。
2. **稳定的规则编码（rule code）体系**：每个发现是一个 `RiskFinding` dataclass——`{code, severity, title, message, suggestion, clause_number, clause_label}`。`code` 是机器可读的稳定标识，**10 条规则**由 7 个 `_check_*` 函数按条款类型分派、`analyze_clauses()` 统一收口：
   `BREACH_REMEDY_VAGUE`(medium) / `ARBITRATION_BODY_MISSING`(**high**) / `ARBITRATION_LITIGATION_CONFLICT`(**high**) / `PAYMENT_DEADLINE_VAGUE`(medium) / `ACCEPTANCE_CRITERIA_MISSING`(medium) / `DELIVERY_DEADLINE_MISSING`(medium) / `UNBALANCED_TERMINATION`(**high**) / `UNILATERAL_TERMINATION_CHECK`(low) / `CONFIDENTIALITY_NO_SURVIVAL`(medium) / `FORCE_MAJEURE_NOTICE_MISSING`(low)
3. **"写了但没量化"这类语义级规则**：`_check_breach` 判定「出现"违约金/赔偿损失/承担违约责任" **但** 未匹配到金额模式」→ 报 medium。金额模式含 `日万分之|千分之|百分之|违约金+数字（含中文数字壹贰叁…）|违约金率|损失赔偿额`。**这是"看起来合规、实则不可执行"的典型审计逻辑，与"广告里有 claim 但无 substantiation 证据"完全同构。**
4. **具体性双重校验**（争议解决条款）：只写"仲裁"但未指明机构 → `ARBITRATION_BODY_MISSING`(high，引《仲裁法》第 16 条)；同时出现"仲裁"与"诉讼/法院" → `ARBITRATION_LITIGATION_CONFLICT`(high)。机构白名单用正则枚举（贸仲/北仲/上仲/广仲/深国仲/上海仲裁委员会/北京仲裁委员会…）。付款期限检查用**「模糊词 ∧ ¬明确日期」的合取判定**：模糊词 `及时|尽快|适时|按约定时间|另行通知|根据进度`，明确日期 `日内|工作日内|当日|次日|每月|每季度|每半年|每年|月\d|日前`。
5. **⭐ 定量定级公式（替代 LLM 主观定级）**（`stances.py`）：
   ```python
   score = min(100, high*30 + medium*12 + low*5)
   level = "高" if (high >= 2 or score >= 50) \
           else "中" if (high == 1 or medium >= 2 or score >= 20) else "低"
   # 附 comment：高→"建议暂缓签署" / 中→"签署前逐项澄清" / 低→"可签署但建议专业复核"
   ```
   简单、可解释、可调参、可复现。
6. **多立场审查（甲方/乙方/中立）**：`_default_stance()` 把 15 个 code 映射到 `(不利方, 理由)`——如 `PAYMENT_DEADLINE_VAGUE → ("收款方", "付款时点模糊对收款方更不利")`。**同一份合同按立场给出不同结论**，这是很成熟的审计产品思路，内容审计同样适用（品牌方视角 / 平台视角 / 消费者视角）。
7. **文档级"必备条款缺失"检查**（`contract_level_risks`）：用 `_REQUIRED_AFTER_CATEGORIES` / `_RECOMMENDED_AFTER_CATEGORIES` 两张表比对已识别条款集合，缺失的必备条款报对应 severity，建议类缺失报 `low` 并附"如确实不需要可忽略"。
8. **无模型依赖的条款分类**（`classifier.py`，141 行）：手写 `_SoftmaxRegression` + 动量 SGD（`epochs=40, batch=128, lr=2.5, l2=0.0001`，动量 `v = 0.9v + 0.1g`）+ 字符 n-gram 特征（`nlp.py`）+ `training_data.py` 语料（20 KB），**不依赖 sklearn/torch**，可离线、可嵌入、零 API 成本。配套 `entities.py`（中文数字转金额、付款计划分期）、`compare.py`（版本比对）、`missing.py`、`report.py`（JSON/Markdown/HTML 三态 + 台账 CSV）。
9. **每条建议都引用法律依据**：如违约救济建议引用「《民法典》第 585 条关于违约金调整的规定」。

**技术栈**：Python 标准库 + **NumPy**（无 sklearn/torch，无外部 AI 依赖）· 自研 word/DOCX I/O（`docxio.py`）· 两套 Web（`webapp.py` 8765 零依赖 http.server / `server.py` 8787）· 原生 HTML/CSS/JS 前端 · pytest

**与内容审计相关性**：**规则引擎部分高度相关，领域不相关**。其 `RiskFinding` + 稳定 rule code + 定位 + 建议 + 法规依据的结构，是**规则单元 schema 的最佳范例**；其"存在 A 但缺少 B → 报风险"的判定形态可直接迁移。

**具体解决什么**：让不具有法务背景的人也能对中文合同做系统性的条款风险排查，输出带条款定位、风险说明与修改建议的可执行清单，并支持多立场与台账导出。

**⚠️ 教训**：`README`、`使用说明`、GitHub description 三者互相矛盾，且真实能力藏在未被文档提及的第二个入口（`webapp.py`）里。**该仓库不可作为文档可信度样本。**

---

## 三、跨仓库共性方法论提炼：这些实践指向什么样的审计 Agent 架构？

把 9 个有效项目横向对比后，可归纳出一条清晰的**成熟度谱系**和一套**共同收敛的架构**。

### 3.1 分层结论：成熟审计 Agent = 确定性规则层 + 语义模型层 + 决策仲裁层

| 层次 | 职责 | 做全了的项目 | 缺失后果 |
|---|---|---|---|
| **① 确定性规则层** | 词表/正则/阈值/结构化规则注册表，可枚举、可版本化、可单测 | ad-review-agent、crossborder-image-agent、ad-compliance-agent | 只靠 LLM → 结果不可复现、无法回归测试（contract_audit 即此） |
| **② 语义模型层** | VLM/LLM 做上下文理解、跨模态比对、边界判断 | PolySafe、ad-review-agent、crossborder-image-agent | 只靠词表 → 大量误报（"最好"在非宣传语境） |
| **③ 决策仲裁层** | 汇总多源信号 → 置信度聚合 → 三态结论 + 可解释理由 | ad-review-agent（最强）、ad-compliance-agent | 无仲裁 → 结论互相矛盾、无法说明"为什么" |

**关键洞察**：清单里**没有任何一个项目用纯 LLM 做审核并宣称可用**。凡是认真做的，都是「确定性规则先跑一遍，把发现喂给 LLM，再由决策层仲裁」——`crossborder` 的 `preliminaryRuleBasedIssues` 注入 prompt、`ad-review-agent` 的 6 Tool 结果进 `DecisionEngine`、`ad-compliance-agent` 的敏感词结果作为"风险信号而非结论"，三者殊途同归。

### 3.2 规则表达方式的四层谱系（可直接用于选型）

| 层级 | 形态 | 代表 | 优点 | 局限 |
|---|---|---|---|---|
| **L1 最弱** | 规则内嵌在节点 prompt 里 | contract_audit | 上手快 | 不可枚举、不可版本化、不可回归测试 |
| **L2** | Markdown 规则文档 + RAG 检索 | ad-compliance-agent（`ad_law_core.md` 六字段规则） | 有法规依据、可检索、非技术人员可维护 | 命中靠向量相似度，无法保证"该命中必命中" |
| **L3** | 结构化词表 + 稳定规则编码 + 阈值 | ad-review-agent（`forbidden_words.json`：severity + regulation_ref + words[] + patterns[] 正则）；**Sinyard `contract_review/risks.py`（`RiskFinding{code, severity, message, suggestion, 定位}` 纯规则零 LLM）** | 可精确命中、可单测、可热更新、结果 100% 可复现 | 规则之间是平的，缺少"平台×类型×维度"的组合表达 |
| **L4 最强** | 规则注册表：多维乘积 + 快照冻结 | crossborder（`platform × imageType × 维度 × severity` + `rulesSnapshot`） | 表达力强、可复现、可生成 UI | 维护成本高，需要配套的规则管理后台 |

**推荐组合**：**L3 作为规则单元 schema，L4 作为组织与冻结机制，L2 作为规则的说明性文档层**——即"结构化规则负责判定，Markdown 文档负责解释与给 LLM 提供上下文"。

**规则单元 schema 的最佳范例——`Sinyard` 的 `RiskFinding`**：

```python
@dataclass
class RiskFinding:
    code: str          # 稳定机器可读编码，如 BREACH_REMEDY_VAGUE
    severity: str      # high / medium / low
    title: str         # 人可读标题，如"违约后果未量化，后续索赔可能难以执行"
    message: str       # 为什么这是个问题（讲清后果）
    suggestion: str    # 具体怎么改（附法规依据）
    clause_number: str # 定位信息
    clause_label: str
```

这个七字段结构几乎可以直接照搬为内容审核的规则单元（把 `clause_number/clause_label` 换成 `asset_id / timestamp_or_bbox`）。它同时满足四个要求：**machine-readable 编码**（可统计、可门禁）、**人可读说明**（可交付给业务）、**可执行建议**（发布前把关必须给改法）、**精确定位**（图片坐标/视频时间码/文本字符区间）。

**另一种同样值得抄的判定形态——"有 A 但缺 B"**（`_check_breach`）：

> 文本中出现「违约金 / 赔偿损失 / 承担违约责任」，**但**未匹配到金额模式（`日万分之|千分之|百分之|违约金+数字|损失赔偿额`）→ 报 `medium`。

这是**"表面合规、实则不可执行"的审计逻辑**，与广告场景的「有 claim 但无 substantiation 证据」**完全同构**，可直接迁移为 Momcozy 的 FTC 证据校验规则形态。

### 3.3 共同收敛的可复用模式（17 条）

1. **三态处置而非二态**：`pass / reject(block|RETURNED) / manual_review`。所有成熟项目都有第三态；且**manual_review 在评测中按保守侧（reject）计入**，避免"拿不准就人工"刷高准确率。
2. **判定优先级显式声明**：`明确违规证据 > 规则适用性 > 维度评分 > 综合分`（ad-compliance-agent 明文写入 prompt 结尾）。
3. **阈值集中声明式外部化**：不散落在代码里；ad-review-agent 的 `constraints.yaml` 连源码行号都标注，并要求"改阈值→改版本号→跑 eval 防回归"。
4. **置信度聚合策略要显式选择**：有违规取 `max`（任一维度确信即可拦截）、无违规取 `min`（通过需全面确信）、并定义 `non_drag` 维度避免辅助维度拖累；全部降级要有兜底值。
5. **降级是一等公民**：Tool 失败必须返回 `is_fallback=True` 的**合法结构体**而非抛异常；降级维度不参与聚合；降级原因要可见。
6. **每条违规必须可解释，且带稳定规则编码**：统一携带 `规则编码(code) / 法规依据 / 严重度 / 原文证据片段 / 定位信息 / 修改建议`。Sinyard 的 `RiskFinding{code, severity, title, message, suggestion, clause_number}` 是最完整的写法；ad-compliance 的 `{type, content, rule_ref, severity, suggestion}`、crossborder 的 `{ruleId, evidence[], fixSuggestion}`、ad-review 的 `{dimension, regulation_ref, severity}` 是同一件事的不同精简版。**稳定 `code` 是可统计、可门禁、可回归的前提**。
7. **"命中 ≠ 违规"必须写成显式原则**：敏感词/RAG 命中只作为**风险信号**，必须判断规则是否真正适用于当前上下文（ad-compliance-agent 原则 2，并给出三种分支处理）。
8. **"无法验证 ≠ 虚假"**：把事实主张的**证据状态**（confirmed/missing/conflict/not_required）与**真实性判定**分开建模，证据缺失时降级为人工而非直接判违规。
9. **规则/提示词双版本号 + 快照冻结**：`RULE_VERSION v3.2` + `REVIEW_PROMPT_VERSION review-v3.1` + 任务内 `rulesSnapshot` → 任意历史审核结论可复现。
10. **评测集分桶 + 双向指标 + 对抗集**：
    - 分桶：pass / reject / review（+ adversarial）
    - 指标：accuracy / precision / recall / F1 + **误拒率(FP) + 漏放率(FN) 双向**
    - 对抗集：专门覆盖拼音替换、标点拆字、emoji 替换等**规避手法**
    - 门禁：指标回归超阈值 → CI 失败阻止合并
11. **Claim 结构化是广告合规的核心动作**：先抽 Claim 清单并分类（绝对化/功效/事实/对比/价格/安全），再逐条找规则与证据——这比"整段文本判违规"精确得多。
12. **生成内容（AIGC）需要独立风险项**：crossborder 对 `mock_preview`、`text_to_image` 生成物直接打 high，理由是"文生图不保证产品外观保真"。**AIGC 素材不能与实拍素材共用同一套判定标准**。
13. **"有 A 但缺 B"是审计规则的通用形态**：Sinyard「有违约责任表述但无金额量化」、crossborder「有认证 claim 但无 fieldEvidence」、ad-compliance「有事实主张但 evidence_missing」——三者都是**"声称存在但缺乏支撑"**这一种模式。这类规则最适合做成确定性检查，因为它的判定条件是结构化的（出现关键词 ∧ 未匹配证据模式）。
14. **严重度等级不够用，必须与"结论态/动作类型"正交**：这是本次调研最实用的发现之一。
    - `SOE-Legal-Checker` 的专项核查不用高/中/低，而用**5 种结论态**：`⚠️需关注 / ⚠️待补充材料 / 待确认 / 不适用 / ✓符合`——区分了"有风险""缺材料""不适用""已合规"四种语义。
    - `crossborder` 在 3 级严重度之外，另建 **9 种 `actionType`**：`removeText / removeClaim / confirmFieldEvidence / editTextLayout / regenerateMock / regenerateRealSample / manualCheck / skipMockOnly / noActionNeeded`，配 `canAutoFixLater` / `requiresManualConfirm` 两个布尔位，直接驱动"哪些能自动修、哪些必须人工"的分流。
    - **启示**：风险等级回答"有多严重"，结论态回答"该做什么"。发布前把关场景里，后者才是业务真正需要的。
15. **LLM 输出的后置过滤（反幻觉工程化）**：`InvoiceAuditAgent._filter_actionable_issues()` 用正/负关键词表清洗 LLM 塞进 `issues` 的正面陈述——`positive_words = ["一致","匹配","合规","正常","未发现问题"]`、`negative_words = ["不一致","不匹配","缺失","异常","风险","无法","超过","为空"]`，`if is_positive and not is_negative: continue` 丢弃。**任何用 LLM 产出违规清单的系统都需要这一层**，否则"未发现违规"会被写进违规列表。
16. **人工审核闸门（HITL）应做进状态机**：`contract_audit` 用 LangGraph 的 `interrupt_after=["risk_evaluator"]` + `MemorySaver()` checkpointer，在风险定级后**强制暂停**，人工读取 `app.get_state(config)` 的 `snapshot.next`、确认/改写状态后再 `app.stream(None, config)` 续跑。这正是"机器初筛 → 人工终审 → 放行"的现成实现，比在业务层自己拼审批流干净得多。
17. **测试环境噪音要与真实风险在类型层面隔离**：`crossborder` 的 6 级严重度把 `mockInfo` 单列一级，并用 `isRealComplianceRisk` / `isMockOnly` 两个语义位标记。**否则预览/测试产生的提示会淹没真实合规问题**——这对有 AIGC 生成环节的系统尤其重要。

### 3.4 两个清单共同暴露的空白（对本项目最关键）

| 空白 | 说明 |
|---|---|
| **无品牌调性一致性检查** | ad-review-agent 的 `consistency_checker` 只做**跨素材事实一致性**（品牌身份/产品类别/价格承诺），**没有任何项目做品牌的 tone/voice/视觉调性一致性量化**。 |
| **无 AIGC 生成质量 benchmark** | sceneforge 提供了视频质量审计的**指标与门禁方法**，但其 Roadmap 中"可重复的基准测试与合成测试集"**未完成**；其余项目连视频质量维度都不涉及。 |
| **无美国市场合规规则库** | 所有项目的规则库都是中国《广告法》+ 国内平台规范（vivo / 抖音式）语境。**FTC substantiation、endorsement guides、health claims、Made in USA 等美国法规规则集完全缺失**，需自建。 |
| **无"发布前一次性把关"的 Gate 形态** | 现有项目都是**逐条异步审核**（一条素材一个结论）。没有项目把多条素材 + 多个维度聚合成一个"release gate / 放行决策"。 |

---

## 四、对 Momcozy 品牌内容审计 Agent 的参考价值排序

> 项目定位：Momcozy 品牌内容审计 Agent，审计**文本/图片/视频**，面向**美国市场**，**发布前一次性把关**，并为 **AIGC 视频提供 benchmark**。

### P0 — 必读必抄（架构直接对标）

#### ① `augusding/ad-review-agent` — 整体架构骨架
**借鉴什么**
- **直接复用其 6-Tool 编排骨架**，把 Tool 替换为 Momcozy 版本：
  `TextClaimChecker`（文案主张）→ `ImageComplianceChecker`（图片合规）→ **`VideoMultimodalChecker`**（视频多模态，替换其 LandingPageChecker 或并列）→ `FTCSubstantiationChecker`（替换 QualificationChecker 的"品类资质"逻辑为"美国法规/证据要求"）→ `PlatformRuleChecker`（Amazon US / TikTok Shop / Shopify DTC 规则）→ `BrandConsistencyChecker`（替换其 ConsistencyChecker）。
- **抄 `constraints.yaml` 的声明式阈值模式**：把 `auto_pass / human_review_forced / early_termination / non_drag_dimensions / confidence_strategy` 全部外部化，并在注释里标注源码位置 + "改阈值必须跑 eval"的规程。这是**发布前一次性把关**最需要的可治理性。
- **抄双轨置信度与 non_drag 设计**：Momcozy 场景下建议把 `brand_tone`、`visual_aesthetic` 这类主观维度设为 `non_drag`，避免其低置信度阻止放行。
- **抄 `BaseTool._fallback()` 的降级契约**：视频审核会遭遇下载失败、编码异常、超时——必须有合法降级返回而非抛异常。
- **抄 `consistency_rules.json` 的规则写法**：`examples_violation / examples_normal / non_violation_patterns` 三段式是**把"什么算品牌不一致"讲清楚**的最佳格式，可直接迁移为 Momcozy 的品牌调性规则（把 `brand_identity` 扩展为 `brand_voice` / `visual_identity` / `claim_vs_visual`）。
- **抄 golden dataset 4 桶 + adversarial 桶 + `regression_check.py` 门禁**：这是 AIGC 视频 benchmark 的现成工程范式。
- **抄"REJECT 仅由人工标记，系统自动判定统一 RETURNED"**：避免 Agent 越权做终审，符合"发布前把关"的责任边界。

#### ② `xiaov971023/crossborder-image-agent-New-` — 美国市场 + 平台规则 + 证据合规
**借鉴什么**
- **直接迁移 `platformRuleRegistry` 的结构**：把 `platform × imageType × 维度 × severity` 换成 `销售渠道(Amazon US / TikTok Shop US / Walmart US / Shopify DTC) × 素材类型(text/image/video/thumbnail) × 合规维度`。这个**多维乘积 + 每维 severity 映射**的表达力远超平铺词表。
- **`certificationRules.forbiddenWithoutEvidence = ['FDA','CE','FCC','RoHS','warranty','waterproof','medical claims']` 是美国市场的核心雷区清单**，Momcozy 做母婴/吸乳器品类（涉及健康声明）必须扩充为：FDA 510(k)、BPA-free、food-grade、medical-grade、pediatrician-recommended、safe for newborns 等——**全部归入"无证据即 high"**。
- **抄 `ruleBasedReview.js` 的确定性正则层**：`pricePattern / promotionPattern / certificationPattern / chinesePattern` 可直接扩展为美国市场版（`%`、`$`、`FDA`、`pediatrician`、`clinically proven`、`#1`、`best seller`、`guarantee`、`risk-free`）。
- **抄"Claim 必须带证据"的校验函数**（`hasVisibleTextEvidence` / `hasAnyEvidence`）：这正是 **FTC substantiation** 的工程实现——广告主张必须在素材中有可见/可确认的证据支撑，否则报违规并给出 `fixSuggestion`。**这是本项目最重要的可直接复用模块**。
- **抄 `rulesSnapshot` 冻结 + `ruleId` 命名（`platform.imageType.type`）**：实现审核可追溯。
- **抄 AIGC 风险项**：`mock_preview`、`subject_preserve_risk`（文生图不保证产品外观保真）——Momcozy 的 AIGC 视频 benchmark 必须定义同类项，如"生成视频中产品外观/结构失真""演示动作不符合真实使用方式"。
- **抄三 Provider 抽象 + mock/real 可切**：让 benchmark 能在无 API 成本下跑通。

#### ③ `LittleOooou-Ok/ad-compliance-agent` — 审核推理原则与评测体系
**借鉴什么**
- **整段搬用其"证据驱动审核原则"prompt**（原则 1–5 + 六条"重要提醒"）：尤其 `"敏感词命中不等于违规"`、`"规则相关度不等于违规概率"`、`"案例只能辅助"`、`"无法验证不等于虚假"`、`"风险不等于违规"`——**这五条直接决定 Agent 会不会因关键词一刀切而误杀好内容**。
- **抄 Claim 分类法**：`absolute_claim / efficacy_claim / fact_claim / comparison_claim / price_claim / safety_claim / normal_marketing`。Momcozy 建议细化为美国版：`superlative_claim / health_claim / safety_claim / performance_claim / comparative_claim / price_promo_claim / testimonial_claim / eco_claim`。
- **抄三维加权评分 → 改为 Momcozy 的四维**：`法规合规(FTC/FDA/平台) 40% + 主张真实性(substantiation) 30% + 品牌调性一致 20% + 安全/敏感 10%`，并保留其"综合分不单独决定结论"的优先级约束。
- **抄 `metrics.py` 的指标定义与目标值表**：accuracy≥85% / precision≥90% / recall≥90% / F1≥88% / 误拒率≤10% / 漏放率≤10%，并把 `manual_review` 按 reject 计入混淆矩阵。
- **抄 `docs/evaluation_report.md` 的**双向误差分析**结构**（"高风险通过案例（可能漏检）" + "低风险拒绝案例（可能误判）"）——这是 AIGC 视频 benchmark 报告必须有的章节。
- **抄敏感词库的 `alternatives` 字段**：发布前把关场景下，**只报违规不够，必须给替换建议**。
- ⚠️ **但要警惕其评测结论**：97% 通过率 + 平均风险分 17.7 说明测评集偏易或判定偏宽松，**不要照抄其"97% 准确率"的乐观印象**，要自己构造难度分层的测评集。

### P1 — 模式借鉴

#### ④ `SSS023-s/sceneforge-video-workflow` — AIGC 视频 benchmark 的方法论模板
**借鉴什么**
- **抄"质量门禁清单"的组织方式**：把视频交付前检查项列成可勾选清单（完整解码 / 黑帧 / 冻结 / 重复帧 / 音画同步 / 字幕安全区 / 编码规格 / 响度）——Momcozy 的 AIGC 视频 benchmark 应在此之上**增加"内容层"门禁**（产品外观保真、演示动作真实性、文字/Logo 正确性、claims 合规）。
- **抄审计报告三件套 + 报告原则**：`report.json`（机器可读）+ `frame_metrics.csv`（逐项指标）+ `report.md`（人类可读）；报告原则「记录算法/抽样频率/阈值/版本」「**区分事实、指标和推断**」「**每个告警保留时间码**」「不声称本地指标代表平台判断」——**"每个告警带时间码"对视频审计尤其关键**。
- **抄其视频指标定义**：黑帧/冻结段/非相邻复现/完整解码帧数/声画尾差，可直接用于 AIGC 视频的**硬缺陷**检测（生成视频常见闪烁、冻结、口型不同步）。
- **抄其合规边界声明**：明确"不用于绕过平台审核""不承诺过审/推荐"——Momcozy 的 benchmark 报告也需要同类免责边界。
- **填补其空白**：它的 Roadmap 明确列出但**未实现**「可重复的基准测试与合成测试集」——**Momcozy 要做的正是这个**，可直接采用它的指标词汇与报告结构，补上标注集与评分脚本。

#### ⑤ `hirogoing/PolySafe` — 任务模型与人机协同（规则引擎不要抄）
**借鉴什么**
- **抄 `Batch + N Task` 批量任务模型**：Momcozy"发布前一次性把关"天然是**一批素材**（同一 campaign 的文案+多图+视频）一起提交，需要批次聚合视图与汇总徽章（通过/拦截/待复核/失败）。
- **抄统一多模态契约**：图片/视频/文本**同一输出 schema**（`violation_detected / violation_types / confidence / risk_description`）→ 便于批内横向聚合。建议扩展为 `{verdict, dimensions[], claims[], evidence[], confidence, risk_description}`。
- **抄人机协同回写**：`review` 状态 → 人工复核 → 结果回写系统（形成"复核结果反哺规则/评测集"的闭环）。
- **抄策略变更自动重建索引**的运营体验。
- ⚠️ **不要抄它的规则引擎**：`Rule` 无判定条件、无法规依据，命中靠向量相似度 `>0.3`，且 VLM prompt 是通用 UGC 语境。其 `confidence≥0.8→block / ≤0.3→pass / else review` 的三段阈值可作为**粗筛基线**，不能作为最终判定。

### P2 — 弱相关，仅取规则表达法

#### ⑥ `HsuanZhao/SOE-Legal-Checker` — 品牌合规手册的写法范本 + 抑制 LLM 定级漂移
> 零代码，但它的规则写法和阈值表是清单中最成熟的**领域知识表达**。
- **⭐ 抄「惯例基准表 + 黄/红双阈值」的表达法**：这是**抑制 LLM 定级漂移最有效的手段**——先查表得区间，再定级，而不是让模型凭感觉说"这是高风险"。Momcozy 版本应建立美国市场版基准表，例如：
  | 检查项 | 合规基准 | 黄色预警 | 红色预警 |
  |---|---|---|---|
  | 功效声明证据等级 | 有 RCT/临床研究支撑 | 仅有体外实验或小样本 | 无任何研究，或仅"用户反馈" |
  | 对比广告可比性 | 同品类、同规格、同期价格 | 规格不完全可比 | 跨品类对比或贬低竞品 |
  | 达人合作披露 | 显著位置标注 #ad / Paid partnership | 仅在末尾或标签区披露 | 完全未披露 |
  | 促销价格真实性 | 原价确为近 30 天真实售价 | 原价来源不清 | 虚构原价 / 永久"限时" |
  | 认证声明 | 持有有效证书且范围覆盖该产品 | 证书过期或范围不符 | 无证书却声称 FDA/CE 认证 |
- **抄「结论态」而非单一等级**：专项核查用 `⚠️需关注 / ⚠️待补充材料 / 待确认 / 不适用 / ✓符合` 五态——**"待补充材料"与"有风险"是完全不同的动作指向**，对发布前把关尤其关键。
- **抄「双层审计框架」并关键性地迁移**：原文是「合同条款本身的法律风险」+「缔约过程/决策程序的合规性」。**迁移到 Momcozy 即「内容本身是否违规」+「内容生产链路是否合规（是否 AIGC 生成、是否有肖像/素材授权、是否有 C2PA/水印溯源、是否有 substantiation 存档）」**。⚠️ **这一层对 Momcozy 特别重要**——因为要审计 AIGC 视频，而 AIGC 内容的风险不仅在于画面说了什么，还在于**它是怎么产生的、能否证明来源**。
- **抄「先定位再审查」的前置门禁**：背景不明时强制反问而非硬答。Momcozy 版本：未指定销售渠道/素材类型/目标人群时，先追问再审核，避免用错规则集。
- **抄三条反幻觉底线**（可直接进 system prompt）：「**不得臆断**」「**不得编造不存在的材料**」「**报告应包含 ✓ 符合 的条目，避免只列风险不列结论**」——第三条尤其重要，发布前把关报告如果只列问题，业务方无法判断"到底能不能发"。
- **抄「规则正文与输出模板同文件」**：规则怎么写，报告就长什么样，保证结构一致性。

#### ⑦ `AliceDai0805/contract_audit` — 多阶段流水线思路
- 借鉴 `AgentState(TypedDict)` **显式状态契约**（字段化中间产物，便于调试与断点续跑）与**条件路由**（仅高风险才进入"改写建议生成"，节省成本）。
- 借鉴"修订建议 + **标注法律依据**"的输出习惯 → 对应"替换建议 + 标注规则依据"。
- ⚠️ 其规则内嵌 prompt、无评测集，**架构形态不要照抄**。

#### ⑧ `Sinyard001/Sinyard-`（`contract_review/` 包）— **规则单元 schema 与硬规则引擎的最佳范例**
> 尽管 README 完全没提，这个包是清单中**唯一零 LLM 的纯规则引擎**，规则写法最值得抄。
- **抄 `RiskFinding` 七字段规则单元**（见 3.2）：`code`（稳定编码，如 `BREACH_REMEDY_VAGUE`）+ `severity` + `title` + `message`（讲清后果）+ `suggestion`（给出改法 + 法规依据）+ **定位字段**。Momcozy 版本建议改为 `code / severity / title / message / suggestion / asset_id / locator`，其中 `locator` 对图片是 bbox、对视频是时间码、对文本是字符区间。
- **抄"有 A 但缺 B"的判定形态**：`出现违约金相关表述 但 未匹配金额模式 → medium`。直接迁移为「**出现功效/安全/认证 claim 但未匹配到 substantiation 证据标记 → 违规**」，这正是 FTC 合规检查的核心逻辑。
- **抄文档级检查**（`contract_level_risks`）：用 `_REQUIRED_AFTER_CATEGORIES` / `_RECOMMENDED_AFTER_CATEGORIES` 两张表做**"必备项缺失"扫描**，建议类缺失报 `low` 并附"如确实不需要可忽略"。Momcozy 可建：必备披露项（如达人合作披露 #ad、价格生效期、限制条件、免责声明）是否齐备。
- **抄仲裁机构白名单式的"具体性校验"**：规则要求指定**具体**机构，只写"提交仲裁"不算数。迁移为：只写"clinically proven"不算，必须有具体研究/数据来源。
- **抄零依赖实现**（纯 Python 标准库 + NumPy 字符 n-gram 分类）：适合做 benchmark 的**确定性基线**，让评测基线可复现、无 API 成本。

#### ⑨ `pengyulong/InvoiceAuditAgent` — 确定性先行 + 加权扣分 + 多级降级
> 不是骨架（README 严重滞后）。它是清单中第二完整的审计流水线。
- **抄"确定性规则先行、LLM 只做补充"的编排顺序**：`CrossValidator._execute` 先跑 4 条硬规则，再把结果交给 LLM——与 crossborder 的 `preliminaryRuleBasedIssues` 注入 prompt 是同一思想，且更彻底。
- **抄带阈值分档的量化规则**：`差异率 >20% → high` / `>5% → medium`，每档附具体数字（`差异 12.3%`）与处理建议。Momcozy 可定义：主张强度 vs 证据强度差距、画面与文案事实偏差比例等。
- **抄加权扣分公式**：`基础分 1.0 − 0.15×high − 0.05×medium − 0.01×low`，再 `× min(coverage/100, 1.0)`。**覆盖率因子**尤其值得借鉴——"只审了 60% 的素材就不该得满分"，这对"发布前一次性把关"的整批评分很关键。
- **抄三态状态判定**：`有 high → 不合规` / `有 medium → 部分合规` / `否则 → 合规`。
- **抄多级 OCR 降级链**（百度专用 OCR → DeepSeek → 本地 Tesseract + 本地解析）：Momcozy 的视频/图片理解也应设计"专用模型 → 通用 VLM → 本地轻量兜底"的三级链。
- **抄交叉验证概念**：合同↔发票 → 映射为 `文案主张 ↔ 画面内容 ↔ 落地页/详情页` 三方一致性核对。
- **⚠️ 抄它的教训**：README 完成度声明不可信，必须核对代码树。

#### ⑩ `rtsfan1024/omniguard` — 与 PolySafe 同源，**无增量信息**。

---

## 五、给 Momcozy 项目的落地建议（基于上述共性方法论）

### 建议架构（融合 P0 三个仓库的最优解）

```
输入：一个 campaign 的全部素材（文案 / 图片 / 视频 / 落地页 URL）
        │
        ├─ ① 主张抽取层（ad-compliance-agent 的 Claim 分类法）
        │     每条文案/字幕/画面文字 → Claim List + 类型标签 + 证据状态
        │
        ├─ ② 确定性规则层（crossborder 的 ruleBasedReview.js 模式）
        │     规则注册表：渠道 × 素材类型 × 维度 × severity
        │     维度：superlative / health_claim / certification / price_promo /
        │           testimonial / comparative / chinese_text / platform_visual
        │     全部规则单元带 ruleId + regulation_ref + severity + fixSuggestion
        │
        ├─ ③ 语义与多模态层（PolySafe 的统一契约 + ad-review 的逐帧策略）
        │     文本：claim 合规性 + 品牌 voice 一致性
        │     图片：平台视觉规则（白底/占比/文字/水印）+ 品牌视觉一致性
        │     视频：关键帧（首/尾/均匀）+ 音轨转写 + 时间码定位
        │
        ├─ ④ 仲裁层（ad-review-agent 的 DecisionEngine）
        │     双轨置信度（有违规 max / 无违规 min，brand_tone 设 non_drag）
        │     阈值从 constraints.yaml 读取
        │     结论：PASS / RETURNED（附修改建议）/ REVIEW（人工）
        │
        └─ ⑤ 发布门禁（清单中缺失，需自建）
              campaign 级聚合：任一 high 违规 → 整批拦截
              non_drag 维度不阻塞放行
              输出 release-gate 报告（含逐项证据 + 时间码/坐标 + 修改建议）
```

### 必须自建的三件事（清单中无先例）

1. **美国市场合规规则库**：FTC Act Section 5（deceptive claims）、FTC Endorsement Guides（用户证言/达人合作披露）、FTC Health Products Compliance Guidance、FDA 器械/健康声明边界、Made in USA 标准、儿童产品与母婴安全表述。**现有 9 个仓库的规则库全部是中国《广告法》语境，不可直接搬用。**
   - 规则单元建议直接采用 **Sinyard 的 `RiskFinding` 七字段**（code / severity / title / message / suggestion / locator）+ **crossborder 的 `regulation_ref` 与 `fixSuggestion`** 合并为：`{code, severity, title, message, regulation_ref, evidence[], locator{asset_id, ts_or_bbox}, actionType, suggestion}`。
   - 定级采用 **SOE 的"基准表 + 黄/红双阈值"**，而非让 LLM 自由裁量。
2. **品牌调性一致性量化**：需自定义 brand voice 维度（语气/人称/情感极性/禁用表达）、视觉规范维度（色彩/构图/产品呈现角度/Logo 用法），并采用 ad-review 的 `examples_violation / examples_normal / non_violation_patterns` 三段式写规则 + 分层置信阈值。**建议设为 `non_drag` 维度**，避免主观维度阻塞放行。
3. **AIGC 视频 benchmark**：可完全采用 sceneforge 的指标词汇与报告三件套，补上：
   - **标注集**：分桶（pass / reject / review / adversarial），参照 ad-review 的 `golden_dataset` schema
   - **评分脚本**：混淆矩阵 + 误拒/漏放双向指标 + 目标值表
   - **AIGC 专属维度**：产品外观保真度、动作/物理合理性、文字与 Logo 正确性、口型/音画同步、时序闪烁与冻结、跨镜一致性
   - **生成链路合规维度（来自 SOE 双层框架的启发）**：是否 AIGC 生成、是否有 C2PA/水印溯源、是否有授权、是否有 substantiation 存档
   - **回归门禁**：参照 `regression_check.py`，指标下降超阈值即失败
   - **测试环境噪音隔离**：照抄 crossborder 的 `mockInfo` 级 + `isMockOnly` 语义位，把预览/测试产生的提示与真实合规风险分开

### 三个最容易踩的坑（来自这些仓库的教训）

1. **别用纯 LLM/纯关键词**：纯 LLM 不可复现（contract_audit），纯词表大量误报（PolySafe 的向量相似度命中）。必须是**确定性规则 + 语义理解 + 显式仲裁**三层。
2. **别把"无法验证"判成"虚假"**：ad-compliance-agent 反复强调这一点。母婴/健康品类的 claims 大多属于"证据缺失"而非"虚假"，直接判违规会大量误杀。应引入 `evidence_confirmed/missing/conflict` 证据状态，缺失降级人工。
3. **别让辅助维度拖死放行**：ad-review-agent 的 `non_drag_dimensions` 设计值得照抄——品牌调性、视觉美感这类主观且低置信度的维度，在"无违规"时不应拉低整体置信度而导致永远无法自动放行。

---

## 附：调研过程与可复现性

- **清单枚举**：`curl -sL https://github.com/stars/zjgulai/lists/{audit,content-audit}` → 服务端渲染 HTML，仓库卡片位于 `<div class="col-12 d-block width-full ...">`；页面自报 "6 repositories" / "4 repositories"，与解析结果一致；无分页。
- **仓库分析**：`raw.githubusercontent.com` 抓 README；`codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/main` 抓全量源码（tarball 方式优于 git clone，本环境下 git 的 https transport 不可用）。
- **本地产物**：
  - `/Users/lute/Project/audit_multi_content/research/readmes/` — 10 份 README
  - `/Users/lute/Project/audit_multi_content/research/repos/` — **8 个仓库源码**（PolySafe、ad-compliance-agent、ad-review-agent、sceneforge、contract_audit、soe-legal、invoice、sinyard）
  - `/Users/lute/Project/audit_multi_content/research/star-lists-audit-report.md` — 本报告
- **注意**：部分 README 的 GBK 段落存在 mojibake（crossborder README 第 796 行后），已跳过乱码段落、只采信英文与原编码正常的中文段落。
- **方法论教训**：本次调研中 **README / GitHub description / star-list 描述三者在 4 个仓库上互相矛盾或严重滞后**（omniguard≡PolySafe 重复、InvoiceAuditAgent 低估实现、Sinyard 张冠李戴双项目、contract_audit README 里的 clone 地址指向另一个仓库名）。**仓库评估必须核对代码树（tarball 全量下载），不能只读 README。**
