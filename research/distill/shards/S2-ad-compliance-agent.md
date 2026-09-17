# S2 · `ad-compliance-agent`：证据驱动审核原则与评测体系

> 源码核对基于 `research/repos/` 下仓库快照（2026-09-15 抓取）。
> `ad-compliance-agent` 快照不含 `.git`，实跑 `git rev-parse HEAD` 返回 `fatal: not a git repository`，因此没有 commit 可核；
> 行号口径 `splitlines()`，仓库共 84 个文件。下面每个行号都是本轮实读得到的，不是候选值。

这一片的复用价值集中在两件事上：把「命中不等于违规」写成了可执行的五条原则与三段分支，以及一套能复算的确定性评分加评测口径。规则库本身是中国《广告法》语境，法域问题在 S2-10 单列。

---

### S2-01 证据驱动审核原则（五条原则 + 七条收尾提醒）

- **出处**：`ad-compliance-agent/backend/review_agents/orchestrator.py:10-72`、`ad-compliance-agent/backend/review_agents/orchestrator.py:255-263`（已实读核实）
- **一句话**：整份 system prompt 用五条编号原则规定了 Agent 先理解语义、再把敏感词当信号、再用规则做主要依据、再让案例只做参考、最后区分「明确违规」与「证据不足」，并以七条提醒收尾，其中三条直接压制关键词一刀切。
- **原文**：
```10:20:ad-compliance-agent/backend/review_agents/orchestrator.py
INSTRUCTIONS = """你是一名资深广告合规审核专家 Agent，负责对广告素材进行基于证据的智能合规审核。

你的职责不是简单匹配敏感词，也不是机械地根据历史案例复制结论，而是综合：

- 广告完整语义
- 敏感词检测结果
- 法律法规与平台审核规则
- 历史相似案例
- 广告中的事实主张及可验证性

进行证据驱动的审核判断。
```
```24:36:ad-compliance-agent/backend/review_agents/orchestrator.py
## 一、核心审核原则

### 原则 1：先理解，再判断

在调用工具和输出结论前，必须先理解广告完整语义，包括：

- 推广对象：推广什么产品、服务或活动
- 广告类型：电商、品牌、金融、医疗、教育或其他
- 核心营销主张、功效承诺、价格承诺
- 对比性表述、绝对化表述、真实性主张
- 可能影响消费者决策的重要信息

**禁止仅根据单个词语判断违规。必须结合完整上下文。**
```
```52:62:ad-compliance-agent/backend/review_agents/orchestrator.py
### 原则 3：规则是主要裁决依据

search_ad_rules 返回的规则是判断合规性的核心依据。审核时必须明确建立链路：

广告具体表达 → 对应规则 → 规则适用条件 → 是否满足违规条件 → 审核结论

不得只写"命中规则，因此违规"。必须判断该规则是否真正适用于当前广告。

### 原则 4：案例只能辅助判断，不得单独决定结论

历史案例用于辅助理解边界场景、提供审核一致性参考。不得因为相似案例 = reject 就直接判定当前广告 reject。
```
```255:263:ad-compliance-agent/backend/review_agents/orchestrator.py
## 重要提醒

1. **必须调用所有三个工具**后再给出结论
2. **敏感词命中不等于违规**，必须结合上下文判断
3. **规则相关度不等于违规概率**，必须判断规则是否适用
4. **案例只能辅助**，不能直接决定结论
5. **无法验证不等于虚假**，信息不足时优先 manual_review
6. **风险不等于违规**，综合风险分不能单独决定结论
7. **最终结论优先级**：明确违规证据 > 规则适用性 > 维度风险评分 > 综合风险分
```
- **为什么这样做 / 不这样做会出什么事**：`check_sensitive_words` 返回的文本本身就长得像结论。命中时它会输出「检测到 N 个敏感词/违禁词」并在 high 严重度上追加「建议立即修改」（`ad-compliance-agent/backend/review_agents/tools/sensitive_words.py:46-50`）。模型拿到这样的工具输出，如果 prompt 里没有反向约束，就会把工具回显当成裁决。五条原则里的第 2、3、4 条与提醒 2、3、4 是同一个意思的两次表述，这种重复说明作者在实际运行中遇到过这个词表依赖问题。
- **代价与局限**：五条原则全部只活在 prompt 字符串里。全仓检索 `claim_list`、`absolute_claim`、`evidence_confirmed` 只命中 `orchestrator.py` 的几行 prompt 文本，没有任何 schema、枚举校验或断言。模型可以不按链路输出，系统无从察觉。输出模板里 `claim_list` 退化成 `["主张1", "主张2"]`（`orchestrator.py:211`），第 5 条原则要求的四种证据状态在输出结构里没有对应字段。
- **Momcozy 迁移形态**：五条原则整段进入 system prompt；把「广告表达 → 对应规则 → 规则适用条件 → 是否满足违规条件 → 结论」做成报告模板的固定小节，`backend/api/batch.py:442-446` 已有同构写法可以直接改字段名复用。发布前把关的报告里每条 claim 都要带这五个格，缺格视为报告不合格。
- **横向对比**：`ad-review-agent` 把同类阈值外置到 `ad-review-agent/harness/constraints.yaml:34-58`（`auto_pass: 0.92`、`human_review_forced: 0.70`），并在 YAML 注释里标注对应源码行号；`ad-compliance-agent` 的阈值散在 `scoring.py` 的 if 分支里，调阈值等于改代码。另一侧的代价是多了一层配置加载与版本管理（`constraints.yaml` 要求改后更新 version 并重跑 Eval），换来的是阈值可审计、可对比历史。
- **证据强度**：已实读核实

---

### S2-02 「敏感词命中 ≠ 违规」的三分支处理，与代码层的反例

- **出处**：`ad-compliance-agent/backend/review_agents/orchestrator.py:38-50`、`ad-compliance-agent/backend/evaluation/scoring.py:186-201`（已实读核实）
- **一句话**：prompt 把命中分成「命中 + 规则支持 + 语义构成违规 → reject」「命中但上下文无法确认 → manual_review」「命中但完整语义不构成违规 → 不得 reject」三支；同一仓库的确定性评分器没有这三支，任何 high 严重度命中直接 reject。
- **原文**：
```38:50:ad-compliance-agent/backend/review_agents/orchestrator.py
### 原则 2：敏感词命中不等于最终违规

check_sensitive_words 的结果仅作为风险信号。当检测到敏感词时，必须进一步判断：

- 该词在当前上下文中的实际含义是什么？
- 是否构成广告中的营销宣传？
- 是否触发相关法律或审核规则？
- 是否存在明确的例外、限定条件或上下文豁免？

因此：
- 敏感词命中 + 明确规则支持 + 语义构成违规 → 可判定 reject
- 敏感词命中，但上下文无法确认违规 → manual_review
- 敏感词命中，但完整语义不构成违规 → 不得仅因此 reject
```
```186:201:ad-compliance-agent/backend/evaluation/scoring.py
def _determine_conclusion(result: ScoringResult) -> tuple[str, str]:
    """判定结论和风险等级"""
    has_high_severity = any(sw.get("severity") == "high" for sw in result.sensitive_words_found)
    has_medium_severity = any(sw.get("severity") == "medium" for sw in result.sensitive_words_found)

    # 规则1：合规性风险分 ≥ 80 且有明确规则依据 → reject
    if result.compliance_risk_score >= 80 and result.rule_match_score > 15:
        return "reject", "high"

    # 规则2：有高危敏感词 → reject
    if has_high_severity:
        return "reject", "high"

    # 规则3：综合风险分 ≥ 80 且有违规证据 → reject
    if result.composite_risk_score >= 80 and (result.sensitive_word_score > 10 or result.rule_match_score > 10):
        return "reject", "high"
```
- **为什么这样做 / 不这样做会出什么事**：词表命中是字符串包含判断（`rule_manager.match_sensitive_words` 用 `if word in text`，`ad-compliance-agent/backend/knowledge/rule_manager.py:66`），没有上下文。把命中等同违规，会把「本店没有国家级认证，请勿轻信」这类反例一起拦掉；反过来完全不看命中，又会漏掉真正的硬违规。三分支的写法给中间态留了出口，manual_review 承接不确定。
- **代价与局限**：这是本仓库最值得记录的一处内部不一致，也是迁移时必须先在架构上解决的点。批量路径的结论取 `scoring_result.conclusion`（`ad-compliance-agent/backend/api/batch.py:222`），不经过 prompt；单条路径才走 LLM 编排（`ad-compliance-agent/backend/api/review.py:75`）。同一份素材走批量与走单条，可能得到两种口径的结论。`_determine_conclusion` 的第 2 条分支（`scoring.py:195-197`）没有任何上下文豁免入口。
- **Momcozy 迁移形态**：三分支照搬；同时规定裁决只能由一处产生。建议发布前把关场景让确定性层出 verdict，LLM 只做解释、证据链书写与改写建议，避免两个裁决源。若保留 LLM 裁决，则把 `scoring_result` 降级为「风险信号集合」并改名，禁止下游直接读它的 conclusion 字段。
- **横向对比**：`ad-review-agent` 把违禁词检测放在 Tool 里、把 verdict 放在 `DecisionEngine._determine_verdict`（`ad-review-agent/src/agents/decision_engine.py:159-190`），Tool 只产出违规项，引擎按置信度与阈值出结论，判定权只有一处；代价是 Tool 与引擎之间必须靠 `ToolResultSet` 这类结构传递，接口面更大。
- **证据强度**：已实读核实

---

### S2-03 Claim 七分类与证据状态四分

- **出处**：`ad-compliance-agent/backend/review_agents/orchestrator.py:64-72`、`ad-compliance-agent/backend/review_agents/orchestrator.py:85-86`、`ad-compliance-agent/backend/review_agents/orchestrator.py:210-212`（已实读核实）
- **一句话**：Step 0 要求把每条主张标成七类之一，第 5 条原则要求把可验证主张标成四种证据状态之一，其中「无法验证真实性」被明文禁止等同于虚假宣传，信息不足优先 manual_review。
- **原文**：
```64:72:ad-compliance-agent/backend/review_agents/orchestrator.py
### 原则 5：区分"明确违规"和"证据不足"

对于真实性、功效、销量、认证、价格等可验证主张，必须区分：
- evidence_confirmed：已有充分信息支持真实性
- evidence_missing：广告提出重要事实主张，但当前素材无法验证
- evidence_conflict：现有信息存在明显矛盾
- not_required：当前判断无需额外事实证明

**禁止将"无法验证真实性"直接等同于"虚假宣传"。信息不足时优先进入 manual_review。**
```
```85:86:ad-compliance-agent/backend/review_agents/orchestrator.py
同时提取 Claim List（广告主张清单），每个 Claim 标记为：
- absolute_claim / efficacy_claim / fact_claim / comparison_claim / price_claim / safety_claim / normal_marketing
```
```210:212:ad-compliance-agent/backend/review_agents/orchestrator.py
  "semantic_analysis": "广告语义解析结果",
  "claim_list": ["主张1", "主张2"],
  "dimensions": {
```
- **为什么这样做 / 不这样做会出什么事**：母婴与健康品类的 claim 绝大多数落在「提出了功效主张但素材里没有 substantiation」这一格。把这一格判成虚假宣传，会把大量正常素材拦在发布前，业务方很快会绕过系统。四状态里的 `evidence_missing` 对应的动作是补齐材料后重提，与 reject 是完全不同的处置路径。
- **代价与局限**：七类与四状态只存在于 prompt 文本。全仓检索 `absolute_claim`、`efficacy_claim`、`evidence_confirmed`、`evidence_missing`、`evidence_conflict`、`not_required` 六个标识符，命中位置只有 `orchestrator.py:67-70` 与 `orchestrator.py:86` 两处 prompt。输出 JSON 模板（`orchestrator.py:206-252`）里没有 claim 级字段，`claim_list` 是一维字符串数组。批量报告模板里有一列「证据状态」（`ad-compliance-agent/backend/api/batch.py:475`），仍由模型自由填写，没有枚举约束。
- **Momcozy 迁移形态**：落成 Pydantic 字段，把 prompt 约定升级成 schema 约束。`claim_type` 七枚举的美国版建议把 `efficacy_claim` 拆成 `health_claim`（FDA 语境下的疾病声称，需药品或器械路径）与 `structure_function_claim`（需免责声明、不得声称治疗），其余照搬；`evidence_status` 四枚举照搬，并把 `evidence_missing` 接到「补充 substantiation 后重提」的工作流分支，接 `evidence_conflict` 到人工裁决分支。
- **横向对比**：`ad-review-agent` 用 Pydantic 强制校验所有 LLM 输出，代码里能在多处看到 `_LLMResponse.model_validate_json(raw)`（`ad-review-agent/src/tools/text_checker.py:375`、`ad-review-agent/src/tools/landing_page.py:321`、`ad-review-agent/src/tools/consistency_checker.py:303`），裸 `json.loads` 被明令禁止；代价是每加一个字段都要同步改 schema 与测试。`ad-compliance-agent` 的字段活在字符串里，加字段零成本，也零约束。
- **证据强度**：已实读核实（prompt 文本已实读；「无代码承载」为全仓检索结论）

---

### S2-04 三维加权评分的确定性实现与「各分项上限如何凑到 100」

- **出处**：`ad-compliance-agent/backend/evaluation/scoring.py:100-105`、`ad-compliance-agent/backend/evaluation/scoring.py:117-171`、`ad-compliance-agent/backend/evaluation/scoring.py:380-398`（已实读核实）
- **一句话**：三个维度各自由若干信号拼出上限 100 的分，综合分按合规 0.5、真实性 0.3、安全 0.2 加权；合规面的 100 由敏感词 40、规则命中 35、案例参考 15、语义分析 10 四段拼成，四段的分母还写进了分数说明文本。
- **原文**：
```100:105:ad-compliance-agent/backend/evaluation/scoring.py
    # ── 计算综合风险分 ──
    result.composite_risk_score = (
        result.compliance_risk_score * 0.5 +
        result.authenticity_risk_score * 0.3 +
        result.safety_risk_score * 0.2
    )
```
```117:137:ad-compliance-agent/backend/evaluation/scoring.py
def _calculate_compliance_risk(result: ScoringResult) -> float:
    """计算合规性风险分"""
    score = 0.0

    # 敏感词贡献
    if result.sensitive_word_score > 0:
        score += min(40, result.sensitive_word_score * 1.5)

    # 规则命中贡献
    if result.rule_match_score > 0:
        score += min(35, result.rule_match_score * 1.2)

    # 案例参考贡献
    if result.reject_cases_count > 0:
        score += min(15, result.reject_cases_count * 5)

    # 语义分析贡献
    if result.semantic_score > 0:
        score += min(10, result.semantic_score * 0.8)

    return min(100.0, score)
```
```140:171:ad-compliance-agent/backend/evaluation/scoring.py
def _calculate_authenticity_risk(result: ScoringResult) -> float:
    """计算真实性风险分"""
    score = 0.0

    # 语义分析贡献（功效承诺、虚假宣传）
    if result.semantic_score > 0:
        score += min(50, result.semantic_score * 2.5)

    # 敏感词中的虚假宣传类
    false_ad_words = [sw for sw in result.sensitive_words_found if "虚假" in sw.get("category", "") or "夸大" in sw.get("category", "")]
    score += len(false_ad_words) * 15

    # 规则命中中的真实性相关
    truth_rules = [r for r in result.rules_matched if "虚假" in r.get("title", "") or "夸大" in r.get("title", "")]
    score += len(truth_rules) * 10

    return min(100.0, score)


def _calculate_safety_risk(result: ScoringResult) -> float:
    """计算安全性风险分"""
    score = 0.0

    # 高危敏感词贡献
    high_severity = [sw for sw in result.sensitive_words_found if sw.get("severity") == "high"]
    score += len(high_severity) * 20

    # 安全类敏感词
    safety_words = [sw for sw in result.sensitive_words_found if "安全" in sw.get("category", "") or "敏感" in sw.get("category", "")]
    score += len(safety_words) * 15

    return min(100.0, score)
```
```380:398:ad-compliance-agent/backend/evaluation/scoring.py
def _generate_breakdown(result: ScoringResult) -> str:
    """生成分数说明"""
    parts = [
        f"综合风险分: {result.composite_risk_score:.0f}/100 ({result.composite_risk_level})",
        f"",
        f"├─ 合规性风险: {result.compliance_risk_score:.0f}/100 ({result.compliance_risk_level})",
        f"│  敏感词得分: {result.sensitive_word_score:.1f}/35",
        f"│  规则命中得分: {result.rule_match_score:.1f}/35",
        f"│",
        f"├─ 真实性风险: {result.authenticity_risk_score:.0f}/100 ({result.authenticity_risk_level})",
        f"│  语义分析得分: {result.semantic_score:.1f}/20",
        f"│",
        f"├─ 安全性风险: {result.safety_risk_score:.0f}/100 ({result.safety_risk_level})",
        f"│  高危敏感词: {sum(1 for sw in result.sensitive_words_found if sw.get('severity') == 'high')} 个",
        f"",
        f"结论: {result.conclusion}",
    ]

    return "\n".join(parts)
```
- **为什么这样做 / 不这样做会出什么事**：发布前把关需要可复算。同一份素材重复提交必须得到同一个分，否则运营无法解释为什么昨天能发今天不能。确定性实现让分数可以逐项拆开对账，`_generate_breakdown` 输出的树形文本就是给这个用的。这个仓库同时把 LLM 的温度压到 0.1（`ad-compliance-agent/backend/review_agents/orchestrator.py:276`），用意相同。
- **代价与局限**：三个维度的上限分布很不均匀。真实性面在无敏感词时只有 `min(50, semantic_score * 2.5)` 一条来源（`scoring.py:145-146`），上限 50，因此单独的真实性风险永远不会触发 `_determine_conclusion` 第 5 条（该条要求某维度 ≥ 60）。安全面只认两种信号：`severity == "high"` 的词条，以及 category 里含「安全」或「敏感」的词条（`scoring.py:164-169`）；实测合并后的 73 个词条里含「安全」或「敏感」的 category 有 0 条，安全分实际上退化成「high 敏感词个数 × 20」。权重 0.5/0.3/0.2 硬编码在代码里，无法按品类或渠道调整。
- **Momcozy 迁移形态**：保留四信号拼分与分项分母可见的写法，换掉信号本身。合规面建议 40（平台规则命中）+ 35（FTC 条款或 FDA 法规命中）+ 15（对比广告不实）+ 10（披露缺失）；真实性面把 `min(50, semantic * 2.5)` 换成「无 substantiation 的 health claim 计数 × 15，上限 60」，让真实性面能独立把样本推进人工复核；安全面换成 FDA 禁用声明与母婴安全红线词表。权重从 `backend/config.py` 读，按渠道给两套。
- **横向对比**：`ad-review-agent` 把决策阈值与策略全部外置到 `ad-review-agent/harness/constraints.yaml`，连「哪些维度无违规时不拉低整体」都写成配置项 `non_drag_dimensions`（`ad-review-agent/src/agents/decision_engine.py:36-38` 读取，`:118-128` 使用）；`ad-compliance-agent` 的同类逻辑写在 `_determine_conclusion` 的 if 序列里，改动要碰代码。前者的代价是配置文件本身成了需要评审的产物，注释里要标源码行号以防漂移。
- **证据强度**：已实读核实（含对 73 个词条 category 的逐条统计）

---

### S2-05 结论判定优先级与七个可执行条件式

- **出处**：`ad-compliance-agent/backend/evaluation/scoring.py:186-216`、`ad-compliance-agent/backend/review_agents/orchestrator.py:161-188`、`ad-compliance-agent/backend/review_agents/orchestrator.py:262-263`（已实读核实）
- **一句话**：prompt 声明的优先级是「明确违规证据 > 规则适用性 > 维度风险评分 > 综合风险分」，代码把它落成七条顺序短路的分支；实测 reject 的三个入口里，实际生效的只有「命中任一 high 敏感词」。
- **原文**：
```186:216:ad-compliance-agent/backend/evaluation/scoring.py
def _determine_conclusion(result: ScoringResult) -> tuple[str, str]:
    """判定结论和风险等级"""
    has_high_severity = any(sw.get("severity") == "high" for sw in result.sensitive_words_found)
    has_medium_severity = any(sw.get("severity") == "medium" for sw in result.sensitive_words_found)

    # 规则1：合规性风险分 ≥ 80 且有明确规则依据 → reject
    if result.compliance_risk_score >= 80 and result.rule_match_score > 15:
        return "reject", "high"

    # 规则2：有高危敏感词 → reject
    if has_high_severity:
        return "reject", "high"

    # 规则3：综合风险分 ≥ 80 且有违规证据 → reject
    if result.composite_risk_score >= 80 and (result.sensitive_word_score > 10 or result.rule_match_score > 10):
        return "reject", "high"

    # 规则4：综合风险分 40-79 → manual_review
    if result.composite_risk_score >= 40:
        return "manual_review", "medium"

    # 规则5：某个维度风险分 ≥ 60 → manual_review
    if result.compliance_risk_score >= 60 or result.authenticity_risk_score >= 60 or result.safety_risk_score >= 60:
        return "manual_review", "medium"

    # 规则6：有中危敏感词 → manual_review
    if has_medium_severity:
        return "manual_review", "medium"

    # 规则7：通过
    return "pass", "low"
```
```161:188:ad-compliance-agent/backend/review_agents/orchestrator.py
## 四、最终审核结论判定

最终结论不能仅根据综合风险分决定。必须同时结合：是否存在明确违规、是否存在直接适用的规则、三个审核维度的风险情况、是否存在重要事实无法确认。

### pass

满足：
- 未发现明确违规
- 综合风险分低于 40
- 三个维度均未发现重大风险
- 不存在影响审核结论的重要信息缺失

### reject

满足以下任一条件：
- 合规性风险分 ≥ 80，且存在明确规则依据
- 存在明确 high 严重程度违规，并经过上下文确认
- 存在严重真实性或安全性违规
- 综合风险分 ≥ 80，且存在至少一项明确违规证据

### manual_review

满足以下任一条件：
- 存在明显风险，但证据不足
- 综合风险分在 40-79 之间
- 某个维度风险分 ≥ 60，但无法确认是否构成明确违规
- 存在真实性、安全性或行业资质需要进一步验证
- 规则适用存在关键不确定性
```
```262:263:ad-compliance-agent/backend/review_agents/orchestrator.py
6. **风险不等于违规**，综合风险分不能单独决定结论
7. **最终结论优先级**：明确违规证据 > 规则适用性 > 维度风险评分 > 综合风险分
```
- **为什么这样做 / 不这样做会出什么事**：优先级声明防止「分数高就拒」。综合风险分是加权合成量，权重一变结论就变，把它当唯一判据会让阈值调整变成玄学。顺序短路的分支写法让每个结论都能指到一条具体条件，审计时可以逐条对。
- **代价与局限**：【推断】第 1 条与第 3 条分支在实际数据上极难触发，reject 事实上由第 2 条独占。第 1 条同时要求 `compliance_risk_score >= 80` 与 `rule_match_score > 15`；合规面的四段上限是 40+35+15+10，凑到 80 分需要敏感词面、规则面、案例面三项同时接近满分（例如敏感词面满 40、规则面满 35、案例面满 15 得 90 分，对应 `rule_match_score >= 29.2/35` 且相似案例里至少有 3 条 reject）。第 3 条要求 `composite >= 80`，而安全面只由 high 敏感词贡献，任何能满足第 3 条的样本都已经先被第 2 条拦下。结论是这套评分在真实数据上接近「高危词二值判定」，三维加权主要起到解释作用。另外 `_get_risk_level`（`scoring.py:174-183`）用 20/40/60 分档，`orchestrator.py:152-157` 与 `ad-compliance-agent/backend/api/batch.py:468-472` 用 0-29/30-59/60-79/80-100 四档，同一份输出里的 `risk_level` 与 `composite_risk_level` 可能落到不同档位。
- **Momcozy 迁移形态**：保留顺序短路的写法。三个入口重排：reject 的第一入口改成不可豁免的硬红线（未披露的 paid partnership、无 substantiation 的 health claim、FDA 禁用声明、婴儿安全声称），词表命中降到 manual_review 入口，综合分只作为排序与抽检依据。风险等级分档只保留一套，写在配置里，报告文本引用同一常量。
- **横向对比**：`ad-review-agent` 的 `_determine_verdict` 把优先级表达成「置信度先分档，再看有无违规」（`ad-review-agent/src/agents/decision_engine.py:159-190`），并明确把 reject 留给人工、系统自动判定统一输出 `returned`（同文件 `:148-149` 注释与 `:176` 实现）；`ad-compliance-agent` 直接由系统输出 reject。前者的代价是业务侧要接受「系统不判死」这一约定，并且要有人工队列承接 returned。
- **证据强度**：已实读核实；「第 1、3 条分支难以触发」为【推断】，依据是 `scoring.py:117-171` 的分段上限与 `_determine_conclusion` 的分支顺序

---

### S2-06 模糊词表 `FUZZY_PATTERNS` 与时间-功效正则

- **出处**：`ad-compliance-agent/backend/evaluation/scoring.py:46-51`、`ad-compliance-agent/backend/evaluation/scoring.py:254-269`、`ad-compliance-agent/backend/evaluation/scoring.py:337-377`（已实读核实）
- **一句话**：词库打不中时用四个意图类别的模糊词表兜底（每条 5 分，上限 35），语义面再用三组正则各计一次分，其中一组是「数字 + 时间 + 效果」。
- **原文**：
```46:51:ad-compliance-agent/backend/evaluation/scoring.py
FUZZY_PATTERNS = {
    "绝对化": ["最好", "最佳", "最优", "第一", "唯一", "顶级", "极致", "完美", "无敌", "最强", "最低", "最高", "最大", "最小"],
    "功效承诺": ["见效", "治愈", "根治", "痊愈", "康复", "好转", "瘦身", "减肥", "美白", "祛斑", "祛痘", "丰胸", "壮阳", "增高", "排毒", "抗衰", "逆龄"],
    "虚假背书": ["推荐", "认证", "指定", "专供", "同款", "首选", "领先", "第一", "冠军", "王者"],
    "诱导消费": ["错过", "仅此", "最后", "即将", "售罄", "抢购", "秒杀", "疯抢", "亏本", "跳楼"],
}
```
```337:353:ad-compliance-agent/backend/evaluation/scoring.py
def _check_semantic(content: str) -> float:
    """语义分析"""
    score = 0.0
    content_lower = content.lower()

    import re

    # 模式1：数字+时间+效果
    time_effect_patterns = [
        r'\d+天.{0,2}(见效|变白|瘦身|治好|痊愈)',
        r'\d+周.{0,2}(见效|变白|瘦身)',
        r'(三天|一周|一个月).{0,4}(见效|变白|瘦身|治好)',
    ]
    for pattern in time_effect_patterns:
        if re.search(pattern, content):
            score += 8
            break
```
```355:377:ad-compliance-agent/backend/evaluation/scoring.py
    # 模式2：绝对化表述
    absolute_patterns = [
        r'任何.{0,6}(都|均|可以)',
        r'\d+%\s*(有效|通过|成功)',
        r'(所有|全部|任何).{0,4}(适用|有效|适合)',
    ]
    for pattern in absolute_patterns:
        if re.search(pattern, content):
            score += 6
            break

    # 模式3：功效承诺
    effect_patterns = [
        r'(治疗|治愈|根治|治好).{0,4}(病|症|炎|痛)',
        r'(消除|去除|祛除|去除).{0,4}(斑|痘|皱纹|黑眼圈)',
        r'(增强|提高|提升).{0,4}(免疫|体质|体力|精力)',
    ]
    for pattern in effect_patterns:
        if re.search(pattern, content):
            score += 6
            break

    return min(20.0, score)
```
- **为什么这样做 / 不这样做会出什么事**：「见效」「变白」「瘦身」这类词的同义变体太多，逐个入词库维护不动。时间加功效的组合（「三天见效」）是功效承诺最典型的句式，用正则抓住数字与时间单位再放宽两个字符，能覆盖「7 天见效」「十四天变白」这类写法的共同骨架。
- **代价与局限**：模糊匹配是子串判断（`scoring.py:260-261`），词表里的「推荐」「认证」「指定」「同款」「领先」在正常文案里高频出现，会持续误报；而且它只在精确词库返回空时才运行（`scoring.py:223-228`），一条文案只要命中任何一个词库词，模糊面整体失效，两个信号互斥。正则面每组命中后立刻 `break`（`scoring.py:350-353`、`361-364`、`372-375`），三组全中也是 8+6+6 共 20 分封顶，长文案里的多处违规被压成一次计分。三组正则全部是中文形态，`\d+天.{0,2}(见效|变白|瘦身|治好|痊愈)` 对英文文案零覆盖。
- **Momcozy 迁移形态**：模糊词表换成英文对照表并按渠道分层：`superlative`（best / #1 / world-class）、`efficacy`（works instantly / clinically proven）、`endorsement`（recommended by doctors / FDA approved）、`urgency`（only today / while supplies last）。时间-功效正则改成 `\d+\s*(days?|weeks?|hours?)\b.{0,20}\b(results?|whiter|slimmer|relief)` 与 `clinically (proven|tested)`。把「每组只计一次」改成按命中条数累计，并允许两类信号同时生效。
- **横向对比**：`ad-review-agent` 的违禁词库把正则与词表放进同一份 JSON 的不同组：`absolute_terms` 用 `words` 列举，`false_claims` 用 `patterns` 列正则（`ad-review-agent/src/rules/forbidden_words.json:18-27`），组级带 `severity` 与 `regulation_ref`。它的好处是一条规则的两个表达面可以同时生效；代价是规则分布在 JSON 里，检索时必须先加载整份文件。
- **证据强度**：已实读核实

---

### S2-07 指标目标值表，与 manual_review 计入混淆矩阵时的丢样本缺陷

- **出处**：`ad-compliance-agent/backend/evaluation/metrics.py:32-58`、`ad-compliance-agent/backend/evaluation/metrics.py:61-66`、`ad-compliance-agent/backend/evaluation/metrics.py:95-114`（已实读核实）
- **一句话**：目标值表把 accuracy ≥ 85%、precision ≥ 90%、recall ≥ 90%、F1 ≥ 88%、误拒率 ≤ 10%、漏放率 ≤ 10% 写进报告文本；矩阵口径把预测的 manual_review 折成 reject，但真实标签为 manual_review 的样本在四个分支里都没有位置，会被整体丢弃。
- **原文**：
```32:58:ad-compliance-agent/backend/evaluation/metrics.py
def calculate_confusion_matrix(
    actual_labels: list[str],
    predicted_labels: list[str]
) -> ConfusionMatrix:
    """
    计算混淆矩阵

    将 pass 视为 Negative，reject 视为 Positive
    manual_review 按 reject 处理（保守策略）
    """
    cm = ConfusionMatrix()

    for actual, predicted in zip(actual_labels, predicted_labels):
        # 将 manual_review 转换为 reject（保守处理）
        if predicted == "manual_review":
            predicted = "reject"

        if actual == "reject" and predicted == "reject":
            cm.tp += 1
        elif actual == "pass" and predicted == "pass":
            cm.tn += 1
        elif actual == "pass" and predicted == "reject":
            cm.fp += 1
        elif actual == "reject" and predicted == "pass":
            cm.fn += 1

    return cm
```
```61:66:ad-compliance-agent/backend/evaluation/metrics.py
def calculate_metrics(cm: ConfusionMatrix) -> EvalMetrics:
    """计算各项评估指标"""
    metrics = EvalMetrics()

    total = cm.tp + cm.tn + cm.fp + cm.fn
    if total == 0:
```
```95:114:ad-compliance-agent/backend/evaluation/metrics.py
def format_metrics_report(metrics: EvalMetrics, cm: ConfusionMatrix) -> str:
    """格式化指标报告"""
    report = f"""## 评估指标报告

### 核心指标
| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| 准确率 | ≥ 85% | {metrics.accuracy:.1%} | {'✅' if metrics.accuracy >= 0.85 else '⚠️'} |
| 精确率 | ≥ 90% | {metrics.precision:.1%} | {'✅' if metrics.precision >= 0.90 else '⚠️'} |
| 召回率 | ≥ 90% | {metrics.recall:.1%} | {'✅' if metrics.recall >= 0.90 else '⚠️'} |
| F1 分数 | ≥ 88% | {metrics.f1:.1%} | {'✅' if metrics.f1 >= 0.88 else '⚠️'} |
| 误拒率 | ≤ 10% | {metrics.false_rejection_rate:.1%} | {'✅' if metrics.false_rejection_rate <= 0.10 else '⚠️'} |
| 漏放率 | ≤ 10% | {metrics.false_acceptance_rate:.1%} | {'✅' if metrics.false_acceptance_rate <= 0.10 else '⚠️'} |

### 混淆矩阵
|  | 预测通过 | 预测拒绝 |
|--|---------|---------|
| 实际通过 | TN={cm.tn} | FP={cm.fp} |
| 实际拒绝 | FN={cm.fn} | TP={cm.tp} |
"""
```
- **为什么这样做 / 不这样做会出什么事**：把人工复审当拒绝是保守策略，避免边界案例被算成通过而拉高指标。发布前把关场景下，这个方向的选择是对的。
- **代价与局限**：用仓库自己的函数实跑复现了这个缺陷。输入 4 条 `actual=['pass','reject','manual_review','manual_review']`、`predicted=['pass','pass','pass','manual_review']`，矩阵只装下 2 条（`tp=0 tn=1 fp=0 fn=1`），accuracy 报 0.500。再取 100 条「50 条 pass 全对、30 条 reject 全对、20 条 manual_review 全部错判为 pass」，矩阵只装下 80 条，accuracy 报 1.000。原因是 `calculate_confusion_matrix` 只转换 predicted（`metrics.py:45-47`），actual 从未转换，而四个分支（`metrics.py:49-56`）都要求 actual 取 `pass` 或 `reject`；`calculate_metrics` 的分母取矩阵四项之和（`metrics.py:65`），丢弃样本时分母同步缩小。与之并存的 `_check_correct`（`ad-compliance-agent/backend/evaluation/evaluator.py:187-198`）会把 actual 与 predicted 两侧的 manual_review 都转换，两条口径不一致。
- **Momcozy 迁移形态**：用 3×3 矩阵（pass / reject / manual_review），或保留二态但把分母固定为样本总数并断言 `tp+tn+fp+fn == len(cases)`。若必须二态，同时输出两套口径（`boundary_as_reject` 与 `boundary_as_pass`），报告里并列展示，让阈值调整的方向可见。目标值表的六个阈值换成发布前把关的验收口径：漏放率 ≤ 2%、误拒率 ≤ 15%、边界案例自动复审率 100%。
- **横向对比**：`ad-review-agent` 的 `compute_metrics` 用标签分布当分母：`expected_verdict in ("reject", "returned")` 计入 `false_negative_total`，`expected_verdict == "pass"` 计入 `false_positive_total`，review 作为独立类别单独统计正确率（`ad-review-agent/evals/metrics.py:95-122`），`total_cases` 恒等于样本数（`ad-review-agent/evals/metrics.py:81`、`:125`）。它的代价是需要一份带三态标签的 golden dataset，仓库里对应四个 jsonl 文件（pass / reject / review / adversarial）。
- **证据强度**：已实读核实（含用仓库自带函数实跑复现）

---

### S2-08 双向误差分析的报告结构

- **出处**：`ad-compliance-agent/docs/evaluation_report.md:62-88`、`ad-compliance-agent/scripts/run_eval_100.py:109-111`、`ad-compliance-agent/scripts/run_eval_100.py:180-202`（已实读核实）
- **一句话**：报告固定分两栏，「高风险通过案例（可能漏检）」与「低风险拒绝案例（可能误判）」，两栏各由一个硬编码阈值筛选，各取前 5 例。
- **原文**：
```62:88:ad-compliance-agent/docs/evaluation_report.md
## 6. 典型案例分析

### 6.1 高风险通过案例（可能漏检）
共 6 例：

- **案例 33**：风险分 28.2，置信度 76%
  内容：【产品属性】类型#裙*版型#显瘦*材质#蕾丝*图案#线条*图案#蕾丝*裙型#包臀裙*裙长#连衣裙
【广告文案】这款由BRAND带来的<UNK>，通体以蕾丝钩花面料量体贴身裁剪而成，以弹力的面料配合修身...

- **案例 36**：风险分 28.8，置信度 76%
  内容：【产品属性】类型#上衣*颜色#墨绿色*风格#潮*衣样式#风衣*衣款式#口袋
【广告文案】紧跟潮流不一定就能穿对，但粉蓝衣橱的这款墨绿色风衣穿上绝对能让你美。衣身两侧的大口袋装饰，方便了日常的生活，而且...

- **案例 42**：风险分 25.1，置信度 77%
  内容：【产品属性】类型#裙*版型#宽松*版型#显瘦*颜色#纯色*风格#休闲*风格#性感*图案#纯色*裙型#直筒裙*裙长#连衣裙*裙款式#抽绳*裙款式#连帽
【广告文案】看似平淡无奇的连帽纯色连衣裙，却<UN...

- **案例 60**：风险分 25.9，置信度 77%
  内容：【产品属性】类型#裤*风格#街头*图案#印花*图案#撞色*裤长#九分裤*裤款式#破洞*裤款式#不规则
【广告文案】显高的九分裤版型，令这条裤子保留着很高的吸睛度。且表面还带有不羁的破洞设计，更可营造出...

- **案例 86**：风险分 26.6，置信度 77%
  内容：【产品属性】类型#裙*颜色#银色*风格#性感*裙长#连衣裙*裙款式#吊带
【广告文案】这款连衣裙，采用了超长款式设计，大气优雅，搭配着纯黑的搭配整体性极强。<UNK>性感的<UNK>吊带款式，宛若晚礼...

### 6.2 低风险拒绝案例（可能误判）
无
```
```109:111:ad-compliance-agent/scripts/run_eval_100.py
    # 高分案例（可能的误判）
    high_score_pass = [r for r in results if r["conclusion"] == "pass" and r["total_score"] > 25]
    low_score_reject = [r for r in results if r["conclusion"] == "reject" and r["total_score"] < 50]
```
```180:202:ad-compliance-agent/scripts/run_eval_100.py
## 6. 典型案例分析

### 6.1 高风险通过案例（可能漏检）
"""

    if high_score_pass:
        report += f"共 {len(high_score_pass)} 例：\n\n"
        for r in high_score_pass[:5]:
            report += f"- **案例 {r['index']}**：风险分 {r['total_score']:.1f}，置信度 {r['confidence']:.0%}\n"
            report += f"  内容：{r['content_preview']}...\n\n"
    else:
        report += "无\n\n"

    report += """### 6.2 低风险拒绝案例（可能误判）
"""

    if low_score_reject:
        report += f"共 {len(low_score_reject)} 例：\n\n"
        for r in low_score_reject[:5]:
            report += f"- **案例 {r['index']}**：风险分 {r['total_score']:.1f}，置信度 {r['confidence']:.0%}\n"
            report += f"  内容：{r['content_preview']}...\n\n"
    else:
        report += "无\n\n"
```
- **为什么这样做 / 不这样做会出什么事**：只报一个总分会掩盖方向。发布前把关最怕漏检（高风险素材被判通过），调严阈值之后最怕误杀，两栏并列才能看出该往哪边调。这个结构可以直接搬进 AIGC 视频的 benchmark 报告。
- **代价与局限**：两个阈值是硬编码的魔数，`total_score > 25` 与 `total_score < 50`（`run_eval_100.py:110-111`），而 `total_score` 是四项子分之和（`run_eval_100.py:79-84`），与报告里另一处出现的 `composite_risk_score` 不是同一个量，报告正文的「风险分」列用的是前者（`run_eval_100.py:129`、`:233`）。低风险拒绝栏在仓库的实测结果里恒为「无」（`docs/evaluation_report.md:88`）：reject 由 high 敏感词触发，而 high 敏感词会把四项子分抬到 50 以上，这一栏在现有评分下取不到样本，等于结构性失效。
- **Momcozy 迁移形态**：保留两栏。筛选口径换成与业务风险对齐的条件：漏检栏取「判 pass 但命中硬红线或 claim 无 substantiation」，误杀栏取「判 reject 但证据状态为 `evidence_missing`」。阈值从配置读，并在报告里打印当次阈值，便于跨版本对比。
- **横向对比**：`ad-review-agent` 把误差分析做成可横向比较的比率指标，漏放率是它的首要注意指标（`ad-review-agent/AGENTS.md` §1.2 目标 ≤ 5%，`ad-review-agent/evals/run_eval.py:309-312` 在超过 5% 时打印红字告警并参与回归比对）。两边的差别在于「看案例」与「看比率」：案例便于定位，比率便于设门禁，Momcozy 的 benchmark 报告两样都需要。
- **证据强度**：已实读核实

---

### S2-09 【独立核查】「97% 通过率、平均风险分 17.7、平均置信度 81%」这条结论是否站得住

- **出处**：`ad-compliance-agent/docs/evaluation_report.md:3-18`、`ad-compliance-agent/docs/evaluation_report.md:137`、`ad-compliance-agent/data/test_set/test_cases.json:2-10`、`ad-compliance-agent/scripts/run_eval_100.py:59`、`ad-compliance-agent/scripts/run_eval_100.py:65`、`ad-compliance-agent/scripts/run_eval_100.py:104-107`、`ad-compliance-agent/scripts/run_eval_100.py:240-250`（已实读核实）
- **一句话**：这条结论按原样不可信。三个数字在快照里都没有可执行路径，97% 是系统自己判 pass 的比例，量纲与标签口径下的准确率不同，「测评集偏易」这一解释与仓库里真实存在的测评集对不上。
- **原文**：
```3:18:ad-compliance-agent/docs/evaluation_report.md
**评估时间**：2026-08-17 11:21:07
**测评集来源**：train.json 随机抽样
**测评集规模**：100 条

---

## 1. 核心指标

| 指标 | 数值 | 说明 |
|------|------|------|
| **总样本数** | 100 | 随机抽样 |
| **通过** | 97 (97.0%) | 判定为合规 |
| **拒绝** | 2 (2.0%) | 判定为违规 |
| **需复审** | 1 (1.0%) | 需人工确认 |
| **平均风险分** | 17.7/100 | 分数越高风险越大 |
| **平均置信度** | 81% | AI 判断把握程度 |
```
```135:137:ad-compliance-agent/docs/evaluation_report.md
| 20 | 【产品属性】类型#裙*版型#宽松*版型#显瘦*风格#休闲*风... | ✅ pass | 7.3 | 86% |

*（仅展示前 20 条，完整数据见 eval_results.json）*
```
```2:10:ad-compliance-agent/data/test_set/test_cases.json
  "metadata": {
    "version": "1.0",
    "created_at": "2026-08-13",
    "total_cases": 100,
    "distribution": {
      "pass": 50,
      "reject": 30,
      "manual_review": 20
    }
```
```55:74:ad-compliance-agent/scripts/run_eval_100.py
    for i, item in enumerate(items):
        content = extract_ad_text(item)

        # 计算评分
        scoring_result = calculate_risk_score(content)

        results.append({
            "index": i + 1,
            "content_preview": content[:100],
            "conclusion": scoring_result.conclusion,
            "confidence": scoring_result.confidence,
            "risk_level": scoring_result.risk_level,
            "total_score": scoring_result.total_score,
            "sensitive_word_score": scoring_result.sensitive_word_score,
            "rule_match_score": scoring_result.rule_match_score,
            "case_reference_score": scoring_result.case_reference_score,
            "semantic_score": scoring_result.semantic_score,
            "sensitive_words_count": len(scoring_result.sensitive_words_found),
            "rules_matched_count": len(scoring_result.rules_matched),
        })
```
```104:107:ad-compliance-agent/scripts/run_eval_100.py
    for r in results:
        for sw in r.get("sensitive_words_found", []):
            cat = sw.get("category", "其他")
            violation_types[cat] = violation_types.get(cat, 0) + 1
```
```240:250:ad-compliance-agent/scripts/run_eval_100.py
def main():
    """主函数"""
    print("=" * 60)
    print("广告素材合规审核 Agent - 评估")
    print("=" * 60)

    # 加载数据
    train_file = r"data\test_set\test_cases.json"  # 使用项目内的测评集
    print(f"\n从 {train_file} 随机抽取 100 条数据...")
    items = load_train_data(train_file, sample_size=100)
    print(f"已抽取 {len(items)} 条")
```
```63:69:ad-compliance-agent/scripts/run_eval.py
    # 保存报告
    report_path = DOCS_DIR / "evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 广告素材合规审核 Agent 评估报告\n\n")
        f.write(f"**评估时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**测评集规模**：{report['total_cases']} 条\n\n")
        f.write(report["report_text"])
```
```38:41:ad-compliance-agent/.gitignore
scripts/demo_*.py
scripts/check_*.py
docs/eval_results.json
docs/project_summary.html
```
- **核查过程与数字**：

  1. **数字的生成路径不含 LLM**。报告模板由 `run_eval_100.py` 生成（它的关键行与 `docs/evaluation_report.md` 逐条对应：来源声明、六项核心指标、四个分项均值、双向误差两栏），而该脚本第 14 行导入 `calculate_risk_score`、第 59 行调用它，全程不经过 Agent。同一路径下另有一个生成器 `scripts/run_eval.py`，它写同一份 `docs/evaluation_report.md` 但表头只有评估时间与测评集规模（`ad-compliance-agent/scripts/run_eval.py:64-69`），与现存报告的章节对不上，可以排除。报告第 18 行把平均置信度解释成「AI 判断把握程度」，与评分器路径不符。
  2. **脚本在当前快照上跑不起来**。第 65 行读 `scoring_result.confidence`，而 `ScoringResult` 的 20 个字段里没有 `confidence`（用 `ast` 数过：`conclusion`、`risk_level`、三个维度的分数与档位、`composite_risk_score`、`composite_risk_level`、`sensitive_words_found`、`rules_matched`、`reject_cases_count`、`pass_cases_count`、四个分项分、`total_score`、`score_breakdown`），第一条数据就会抛 `AttributeError`。第 247 行的输入路径是 `r"data\test_set\test_cases.json"`，反斜杠路径在 POSIX 上不存在（仓库自带 `Procfile` 与 `railway.toml`，部署目标是 Linux）。第 105 行读 `r.get("sensitive_words_found")`，而结果字典存的键是 `sensitive_words_count`（第 72 行），所以报告第 5 节「敏感词命中统计」的表永远为空，这与 `docs/evaluation_report.md:57-59` 的空表一致。
  3. **报告自称的数据源不在仓库里**。报告与脚本都写「测评集来源：train.json 随机抽样」，全仓检索 `train` 命中 `docs/evaluation_report.md:4`、`scripts/run_eval_100.py:2`、`:17`、`:116`、`:247-249`，全部是文件名与函数名，仓库里没有任何 `train.json` 或 `*.jsonl` 文件。报告第 137 行指向的 `docs/eval_results.json` 被 `.gitignore` 排除（第 40 行），也不在快照里。
  4. **报告内容与仓库测评集对不上**。附录展示的是服饰属性文案（`【产品属性】类型#裙*版型#显瘦*...`），而 `data/test_set/test_cases.json` 是单行电商文案（第 13 行 `TC001`「新款 iPhone 16 现已上市，限时优惠 500 元，点击了解详情」）。报告测的是另一份语料。
  5. **仓库真正的测评集是什么样**。100 条，标签分布 pass 50 / reject 30 / manual_review 20（`test_cases.json:6-10` 的 metadata 声明与逐条 `label` 实测一致）；difficulty 实测 easy 71 / medium 9 / hard 20，其中 20 条 hard 全部是 manual_review，9 条 medium 全部是 reject；reject 的 `violation_type` 实测为夸大功效 13、违禁词 7、虚假宣传 6、虚假背书 3、不正当竞争 1。这份集合被刻意做成了平衡集，标签层面不偏易。
  6. **报告里没有任何准确率指标**。检索 `准确率`、`精确率`、`召回`、`F1`、`混淆` 在 `docs/evaluation_report.md` 中命中 0 处。该文件的核心指标只有样本数、通过/拒绝/需复审计数、平均风险分、平均置信度。
  7. **报告内部算术自洽**。第 3 节的四项均值 1.4 + 15.4 + 0.8 + 0.1 = 17.7，正好等于第 1 节的「平均风险分 17.7」，两处都来自 `total_score`（`run_eval_100.py:90`、`:129`、`:151-154`）。这支持「报告由该脚本的模板产出」这一判断，同时说明那次运行的平均敏感词得分只有 1.4/35。
  8. **在仓库测评集上复现确定性路径，结果与 97% 相反**。按 `scoring.py` 的口径复刻四路信号（词库合并去重后 73 条，`rule_manager.load_sensitive_words` 的合并去重逻辑见 `ad-compliance-agent/backend/knowledge/rule_manager.py:38-47`），规则检索与案例检索在空向量库下返回 0，100 条测评集得到 pass 67 / reject 25 / manual_review 8，平均敏感词得分 6.48/35，平均综合风险分 7.90。标签交叉后：pass 标签 48 条判对，reject 标签 25 条判对、3 条判 pass、2 条判 manual_review，manual_review 标签 16 条判 pass、4 条判 manual_review。25 条 reject 判定与「命中至少一个 high 严重度词条」的 25 条 reject 标签样本完全重合；30 条 reject 标签里有 5 条不含任何词库词（`TC059`、`TC063`、`TC071`、`TC075`、`TC079`），全部漏放。
  9. **词库规模也解释不了 1.4/35**。只用 `words.json` 的 30 条复现，平均敏感词得分 3.79、17 条命中 high；两个文件合并后 25 条命中 high、平均 6.18。任何一个版本的词库都产生不出报告里那么低的命中量，差异更可能来自那次运行用的语料（服饰属性文案里的绝对化用语很少）。

- **判断**：
  - **「判定偏宽松」**：证据不足以下这个结论，而且方向要拆开看。97/2/1 那次运行测的是无标签的外部语料，无法判断宽松与否。在仓库自己的测评集上复现，漏放集中在边界案例（20 条 manual_review 里 16 条被判 pass），而 25 条命中高危词的 reject 案例全部判对。真正的问题是评分器只在命中高危词时拒绝，且 30 条 reject 里有 5 条不含任何词库词，属于词表覆盖问题。
  - **「测评集偏易」**：不成立。报告测的不是仓库测评集；仓库测评集是 50/30/20 的平衡集，并带 20 条 hard 边界案例。
  - **三个具体数字**：证据不足。`97%` 无法在快照里复现（脚本第 65 行必抛异常），`17.7` 与 `81%` 分别依赖被 gitignore 的 `eval_results.json` 和一个不存在的 `confidence` 字段。
  - **给 Momcozy 的可执行结论**：不要引用这三个数字。要引用的是仓库里两样能跑的东西：带三态标签的 100 条测评集结构，以及「评分器只在命中高危词时拒绝」这一实测行为。评测报告里必须同时给出指标的分子分母，并且断言分母等于样本总数（见 S2-07 的丢样本缺陷，那个缺陷会让任何准确率数字失去意义）。
- **代价与局限**：第 8 条是我按 `scoring.py` 的分段公式复刻的结果，不是运行仓库脚本的输出（脚本在第 65 行就中断），也未接入 Chroma 与 DashScope 的 embedding 服务，因此规则面与案例面按 0 计。这一复刻给出的是「规则与案例检索都为空」这个可复现条件下的分布，报告里那次的规则面均值是 15.4/35，两者不可直接互换。给出该复刻是为了判断「97% 通过率能不能由现有代码产生」，答案是能产生远高于 0 的拒绝率。
- **Momcozy 迁移形态**：benchmark 报告的首屏固定三件事：样本总数与三态标签分布、每个指标的分子分母、当次阈值。任何跨版本对比的表格都必须带上当次测评集哈希，避免报告与语料对不上而无人察觉。
- **横向对比**：`ad-review-agent` 的评测带回归门禁与历史存档，`evals/run_eval.py` 在漏放率超过 5% 时直接打印红字告警（`ad-review-agent/evals/run_eval.py:309-312`），并把上一次的 accuracy、false_negative_rate、automation_rate 读进来做逐项对比（`ad-review-agent/evals/run_eval.py:324-333`）。它之所以能做这件事，前提是 golden dataset 与模型输出都在版本控制里。`ad-compliance-agent` 的评测结果落在被 gitignore 的 `docs/eval_results.json`，报告文本留在仓库，两者一分离，数字就无法复核。
- **证据强度**：已实读核实（含全仓检索、按 `splitlines()` 逐条统计、用仓库自带函数实跑复现；第 8 条的复刻过程属【推断】性质的自建复现，条件已在「代价与局限」写明）

---

### S2-10 规则文档的字段结构与可机器读取的边界

- **出处**：`ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md:3-18`、`ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md:20-34`、`ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md:36-46`（已实读核实）
- **一句话**：规则的书写模板是「规则内容 / 法规依据 / 严重程度」三个必填字段，加「违规示例」「关键词」两个选填字段；按三必填两选填解析这份文件即可；固定六字段的读法会在 9 条规则上取到空值。
- **原文**：
```3:18:ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md
## 规则 R001：绝对化用语禁止
- **规则内容**：广告不得使用"国家级"、"最高级"、"最佳"等用语
- **法规依据**：《广告法》第九条第三款
- **严重程度**：高
- **违规示例**：
  - "全网最低价"
  - "行业第一品牌"
  - "国家级认证"
  - "世界领先技术"
  - "最佳选择"
  - "顶级品质"
  - "极品推荐"
  - "独一无二"
  - "无与伦比"
  - "史上最强"
- **关键词**：最佳、最好、第一、顶级、极品、国家级、世界级、最高级、最低、最强、最大、最优、首选、独家、唯一、独一无二、无与伦比、史无前例、前所未有、绝无仅有、首屈一指、出类拔萃、登峰造极、无以伦比、超级、终极、完美
```
```20:34:ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md
## 规则 R002：虚假广告禁止
- **规则内容**：广告不得含有虚假或者引人误解的内容，不得欺骗、误导消费者
- **法规依据**：《广告法》第四条、第二十八条
- **严重程度**：高
- **构成虚假广告的情形**：
  1. 商品或服务不存在
  2. 商品信息与实际情况不符，对购买行为有实质性影响
  3. 使用虚构、伪造或无法验证的科研成果等作证明材料
  4. 虚构使用效果
  5. 其他欺骗误导情形
- **违规示例**：
  - "100%有效，无效退款"
  - "经临床验证，治愈率99%"
  - "百万用户好评如潮"（无实际数据支撑）
- **关键词**：100%、百分百、绝对、保证、承诺、无效退款、假一赔十、治愈率、有效率
```
```36:46:ad-compliance-agent/data/knowledge_base/rules/ad_law_core.md
## 规则 R003：功效断言禁止
- **规则内容**：广告不得含有表示功效、安全性的断言或者保证
- **法规依据**：《广告法》第十六条、第十八条
- **严重程度**：高
- **违规示例**：
  - "三天瘦十斤"
  - "一夜变白"
  - "纯天然无副作用"
  - "包治百病"
  - "立竿见影"
- **关键词**：三天见效、一周变白、无副作用、纯天然、包治、根治、立竿见影、速效、特效
```
- **字段覆盖率实测**：15 条规则（R001 至 R015）。`规则内容` 15/15，`法规依据` 15/15（全部是中国《广告法》条款），`严重程度` 15/15（高 13、中 1、低 1），`违规示例` 6/15，`关键词` 3/15，另有 `构成虚假广告的情形` 只出现在 R002 一条。同时具备 `违规示例` 与 `关键词` 的只有 R001、R002、R003 三条；两个都没有的有 9 条（R005、R006、R007、R008、R009、R010、R011、R014、R015）。
- **为什么这样做 / 不这样做会出什么事**：字段是给检索链路分工用的。规则内容进向量库做语义检索，关键词进词表做精确命中，严重程度进评分。三必填保证了每条规则都能被检索到并给出法规依据，选填允许先立规则后补例子。
- **代价与局限**：严重程度没有机器可读的表示，`- **严重程度**：高` 是一行散文。`_check_rules` 判断规则严重程度靠字符串包含：`if "高" in rule_content and ("严重" in rule_content or "严重程度" in rule_content)`（`ad-compliance-agent/backend/evaluation/scoring.py:290-292`），也就是要规则正文里同时出现「高」和「严重」两个字才升级为 high。R004 至 R011 与 R014 只有严重程度行、没有违规示例与关键词，而这些行的正文片段是否落进向量库取决于 `scripts/init_knowledge_base.py` 的切块方式，规则面得分因此有系统性偏差。多法域并存时也没有字段可放。
- **法域提示与迁移边界**：这份文件 15 条全部是中国《广告法》语境，三条不能直接搬到美国市场。R001（绝对化用语禁止，依据第九条第三款）在美国没有对应的一律禁止规则，FTC 的执法点是「具体声称必须有依据」，泛泛的吹嘘（puffery）受容忍，词表里的「最佳」「第一」在美国不能作为拒绝理由。R002 的「构成虚假广告的情形」（对应第四条、第二十八条）要改写成 FTC Act 第 5 条的 deceptive 标准（materiality 与 reasonable consumer 两个要件），举证与判断口径都不同。R003（功效断言禁止，对应第十六条、第十八条）在 FDA 语境下必须拆成两类：disease claim 需要药品或器械路径，structure/function claim 需要免责声明且不得声称治疗；母婴品类还叠加吸乳器作为医疗器械的声明边界，R013（非医疗类禁止涉及疾病治疗）同样要按 FDA 的器械分类重写。
- **Momcozy 迁移形态**：规则改成结构化文件，字段建议 `rule_id / jurisdiction / statute / requirement / severity / applies_when / examples[] / keywords[] / evidence_required`。`jurisdiction` 承载法域（`US-FTC`、`US-FDA-21CFR`、`Amazon-HealthAndPersonalCare`），`severity` 用枚举，`applies_when` 写适用条件供推理链路第二格引用，`evidence_required` 与 S2-03 的证据状态对接。
- **横向对比**：`ad-review-agent` 的规则库是 JSON，组级带 `severity` 与 `regulation_ref`，文件级带 `version`、`updated_at`、`updated_by`（`ad-review-agent/src/rules/forbidden_words.json:1-16`），支持热更新与变更追溯；代价是非技术人员改规则要面对 JSON 语法，且规则散落在多个文件（`src/rules/` 下 5 个 json）。Markdown 规则的可读性更好，代价是结构化字段只能靠正文字符串猜。
- **证据强度**：已实读核实（覆盖率按 `splitlines()` 逐条统计）

---

### S2-11 敏感词库的 `alternatives` 字段与替换建议链路

- **出处**：`ad-compliance-agent/data/knowledge_base/sensitive_words/words.json:1-15`、`ad-compliance-agent/data/knowledge_base/sensitive_words/words.json:101-105`、`ad-compliance-agent/backend/knowledge/rule_manager.py:59-83`、`ad-compliance-agent/backend/review_agents/tools/sensitive_words.py:32-40`（已实读核实）
- **一句话**：每个词条带一组同义替换词，工具输出把它拼成「建议替换为：优质、优选、精选」，命中直接变成可执行的改写建议。
- **原文**：
```1:15:ad-compliance-agent/data/knowledge_base/sensitive_words/words.json
{
  "metadata": {
    "version": "1.0",
    "created_at": "2026-08-13",
    "total_words": 150,
    "categories": ["绝对化用语", "虚假宣传", "夸大功效", "诱导性用语", "敏感内容"]
  },
  "words": [
    {
      "word": "最佳",
      "category": "绝对化用语",
      "severity": "high",
      "rule_ref": "广告法第九条第三款",
      "alternatives": ["优质", "优选", "精选"]
    },
```
```101:105:ad-compliance-agent/data/knowledge_base/sensitive_words/words.json
      "word": "100%",
      "category": "虚假宣传",
      "severity": "high",
      "rule_ref": "广告法第四条",
      "alternatives": ["高比例", "大部分"]
```
```73:80:ad-compliance-agent/backend/knowledge/rule_manager.py
                    matches.append({
                        "word": word,
                        "category": word_info["category"],
                        "severity": word_info["severity"],
                        "rule_ref": word_info["rule_ref"],
                        "alternatives": word_info.get("alternatives", []),
                        "position": {"start": idx, "end": idx + len(word)}
                    })
```
```32:40:ad-compliance-agent/backend/review_agents/tools/sensitive_words.py
    for i, match in enumerate(matches, 1):
        result_parts.append(f"【敏感词 {i}】")
        result_parts.append(f"词语：{match['word']}")
        result_parts.append(f"类别：{match['category']}")
        result_parts.append(f"严重程度：{match['severity']}")
        result_parts.append(f"法规依据：{match['rule_ref']}")
        if match.get("alternatives"):
            result_parts.append(f"建议替换为：{'、'.join(match['alternatives'])}")
        result_parts.append(f"位置：第{match['position']['start']}字符\n")
```
- **字段覆盖率实测**：`words.json` 30 条全部带 `alternatives`；`words_extended.json` 72 条一条都没有（0/72）；两文件按 word 去重合并后 73 条，其中 28 条有替换建议。`words.json` 的 metadata 声明 `total_words: 150`、`categories` 含「敏感内容」，实际词条 30 条、实际 category 里没有「敏感内容」；`words_extended.json` 声明 `total_words: 200`，实际 72 条；`data/knowledge_base/cases/cases.json` 声明 `total_cases: 50`，实际 20 条。三份知识库文件的 metadata 都高报了自己的规模。
- **为什么这样做 / 不这样做会出什么事**：发布前把关的输出要能直接改。只报「命中了《广告法》第九条第三款」等于把返工推回给文案，业务方会把系统当成审批障碍。带上替换词，工具输出就从判定变成建议，`sensitive_words.py` 的返回文本也按这个定位组织。
- **代价与局限**：替换词不带长度与版位约束，「最佳」换成「优质」在不同版位上字数不同，视频字幕与图片贴字场景会破坏排版。`rule_manager.match_sensitive_words` 用下标直接取键（`word_info["category"]`、`word_info["severity"]`、`word_info["rule_ref"]`，`rule_manager.py:75-77`），任何词条缺这三个键都会 `KeyError` 中断整次审核，扩展词库时没有 schema 校验。合并逻辑只按 `word` 去重（`rule_manager.py:38-47`），同名词在两份文件里的 severity 与 alternatives 以先加载的文件为准，`words*.json` 的 `sorted(glob)` 顺序决定了哪一份优先。
- **Momcozy 迁移形态**：`alternatives` 升级为按版位分层的改写建议，字段形如 `[{channel: "video_subtitle", alt: "...", max_chars: 12}, {channel: "amazon_bullet", alt: "..."}]`。词库加载时加 JSON Schema 校验（三个必填键加 alternatives 的类型），并在服务启动时做一次全量自检，在启动期把缺字段的词条打印出来，避免审核时才抛异常。声明字段与实际条数的一致性纳入 CI 断言。
- **横向对比**：`ad-review-agent` 的词库把 `severity` 与 `regulation_ref` 放在组级、替代表达靠正则组覆盖（`ad-review-agent/src/rules/forbidden_words.json:7-27`），一条组规则覆盖多个变体，维护成本低，给不出逐词的替换建议。两个仓库在这一点上互补：逐词替换建议适合给文案直接改，组级规则适合让检测不随词形变化而漏。
- **证据强度**：已实读核实（覆盖率按逐条统计）

---

### S2-12 确定性裁决 + LLM 叙述 + 模板降级的三段式

- **出处**：`ad-compliance-agent/backend/api/batch.py:322-352`、`ad-compliance-agent/backend/api/batch.py:389-411`、`ad-compliance-agent/backend/api/batch.py:486-488`、`ad-compliance-agent/backend/api/batch.py:497-538`、`ad-compliance-agent/backend/api/batch.py:541-549`（已实读核实）
- **一句话**：批量任务的结论直接取确定性评分器的 `conclusion`，LLM 只负责把四路证据写成可读报告，调用超时或异常时退回模板报告，裁决不受影响。
- **原文**：
```322:352:ad-compliance-agent/backend/api/batch.py
def _generate_detailed_report(content: str, scoring_result) -> str:
    """调用 Agent 生成详细审核报告（带超时）"""
    try:
        orchestrator = create_orchestrator()

        # 构建敏感词信息
        sensitive_words_info = ""
        if scoring_result.sensitive_words_found:
            for sw in scoring_result.sensitive_words_found[:5]:
                sensitive_words_info += f"- {sw['word']}（{sw['severity']}，{sw.get('category', '')}）\n"
        else:
            sensitive_words_info = "未检测到敏感词\n"

        # 构建规则信息
        rules_info = ""
        if scoring_result.rules_matched:
            for rule in scoring_result.rules_matched[:5]:
                rules_info += f"- {rule.get('title', '未知')}（相似度:{rule.get('similarity', 0):.0%}）\n"
        else:
            rules_info = "未命中相关规则\n"

        # 构建案例信息
        cases_info = f"拒绝案例: {scoring_result.reject_cases_count} 个, 通过案例: {scoring_result.pass_cases_count} 个"

        # 构建评分信息
        scores_info = f"""总风险分: {scoring_result.total_score:.1f}/100
- 敏感词得分: {scoring_result.sensitive_word_score:.1f}/35
- 规则命中得分: {scoring_result.rule_match_score:.1f}/35
- 案例参考得分: {scoring_result.case_reference_score:.1f}/10
- 语义分析得分: {scoring_result.semantic_score:.1f}/20"""

```
```393:411:ad-compliance-agent/backend/api/batch.py
在生成报告前，必须对提供的证据进行一次综合验证：
- 广告具体表达 → 风险识别 → 规则依据 → 规则是否适用 → 案例是否真正相似 → 最终审核结论

必须防止以下错误：
- 敏感词命中就直接判违规
- 规则检索命中就直接判违规
- 历史案例 reject 就直接判当前广告 reject
- 无法验证真实性就直接认定虚假
- 风险分高就直接替代规则判断

---

## 最终裁决原则

1. **广告原文优先**：所有判断必须回到广告原始表达，违规项必须能够定位到广告中的具体文字
2. **规则适用性优先**：规则检索相关度仅表示语义相关性，不代表已违反该规则
3. **案例参考原则**：案例只能辅助判断，不得单独决定结论
4. **真实性判断原则**：无法验证 ≠ 虚假宣传，信息不足时优先 manual_review

```
```486:488:ad-compliance-agent/backend/api/batch.py
**注意**：
- 综合风险分不能单独决定审核结论
- 明确违规证据 > 规则适用性 > 维度风险评分 > 综合风险分
```
```500:538:ad-compliance-agent/backend/api/batch.py
            """带超时的 Agent 调用"""
            try:
                return await asyncio.wait_for(
                    Runner.run(orchestrator, prompt),
                    timeout=30.0  # 30秒超时
                )
            except asyncio.TimeoutError:
                return None

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_with_timeout())

            if result is None:
                return _generate_report(content, scoring_result)

            output = result.final_output

            # 直接返回 Agent 输出（去掉可能的 JSON 块）
            if "```json" in output:
                try:
                    json_start = output.find("```json")
                    json_end = output.find("```", json_start + 7)
                    json_str = output[json_start + 7:json_end].strip()
                    data = json.loads(json_str)
                    if "report_markdown" in data:
                        return data["report_markdown"]
                except:
                    pass

            # 直接返回完整输出
            return output if len(output) > 100 else _generate_report(content, scoring_result)
        finally:
            loop.close()

    except Exception as e:
        # Agent 调用失败，降级为基本报告
        return _generate_report(content, scoring_result)
```
```541:549:ad-compliance-agent/backend/api/batch.py
def _generate_report(content: str, scoring_result) -> str:
    """生成详细审核报告"""
    emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(scoring_result.conclusion, "❓")
    label = {"pass": "通过", "reject": "拒绝", "manual_review": "需人工复审"}.get(scoring_result.conclusion, "未知")

    # 维度判定
    compliance_passed = scoring_result.sensitive_word_score < 10 and scoring_result.rule_match_score < 15
    authenticity_passed = scoring_result.semantic_score < 10
    safety_passed = not any(sw.get("severity") == "high" for sw in scoring_result.sensitive_words_found)
```
- **为什么这样做 / 不这样做会出什么事**：发布前一次性把关同时要两样东西，可复算的 verdict 与给人看的理由。verdict 交给 LLM 会引入不可复现，理由交给模板会丢掉证据链。三段式让 LLM 变成可选的增强项：它可用时报告带链路，不可用时结论照样出，批次不中断。`asyncio.wait_for(..., timeout=30.0)` 与降级分支（`batch.py:497-538`）保证了单条素材的 LLM 故障不会拖垮整批。
- **代价与局限**：降级模板里的维度判定与 LLM 报告不是同一套口径。模板用三个阈值直接算 `compliance_passed`、`authenticity_passed`、`safety_passed`（`batch.py:547-549`），LLM 报告则按 prompt 里的四段评分与七条分支自由叙述，同一条素材在 Agent 可用与不可用时可能给出两套解释。`"confidence": scoring_result.composite_risk_score / 100`（`batch.py:223`）把风险分当置信度用，风险越高「置信度」越高，与 `evaluator._extract_confidence`（`ad-compliance-agent/backend/evaluation/evaluator.py:167-185`，取不到时默认 0.5）的语义不一致。另外该文件里 `scoring_result.sensitive_words_found` 的每条记录被硬套成违规项（`batch.py:248`），建议文本统一是「删除'词'」，与词库里的 `alternatives` 没有接上。
- **Momcozy 迁移形态**：采用同一分工，并对降级链路提两个硬要求。降级模板与 LLM 报告必须调用同一个维度判定函数，避免两套口径。`confidence` 与 `risk` 分开建模：证据覆盖率（多少条 claim 带 substantiation、多少条规则给出了适用性判断）算置信度，规则严重程度算风险。发布前一次性把关的批次还要把「LLM 不可用」写进报告头部，让审核人知道这条理由的生成路径。
- **横向对比**：`ad-review-agent` 把降级做到维度粒度，置信度计算时跳过 `is_fallback` 的维度（`ad-review-agent/src/agents/decision_engine.py:101-105`），并在无违规时排除 `non_drag_dimensions` 里的辅助维度（同文件 `:118-128`），最后用 `all_fallback_default` 兜底（`:130`）。它多出来的成本是每个 Tool 都要实现降级路径并给出置信度，收益是部分维度故障时其余维度的结论仍然可用。`ad-compliance-agent` 的降级粒度更粗，实现更简单。
- **证据强度**：已实读核实

---

### S2-13 配置与文档的三处不一致（迁移前必须知道）

- **出处**：`ad-compliance-agent/backend/config.py:68-80`、`ad-compliance-agent/backend/review_agents/orchestrator.py:269-277`、`ad-compliance-agent/README.md:9-15`、`ad-compliance-agent/README.md:59-77`、`ad-compliance-agent/docs/architecture.md:61-90`、`ad-compliance-agent/docs/architecture.md:233-239`（已实读核实）
- **一句话**：阈值与模型选择写了两份，配置那份没有任何代码读取；README 宣称的四个专业 Agent 通过 handoff 串联在代码里不存在，生产路径是单 Agent 加三个工具。
- **原文**：
```68:80:ad-compliance-agent/backend/config.py
AGENT_CONFIG = {
    "model": DEEPSEEK_MODEL,
    "temperature": 0.1,  # 低温度，保证审核结果稳定性
    "max_tokens": 2000,
}

# ─── 审核阈值配置 ────────────────────────────────────────
REVIEW_THRESHOLDS = {
    "confidence_high": 0.85,      # 高置信度：自动通过/拒绝
    "confidence_low": 0.65,       # 低置信度：需人工复审
    "risk_level_high": 0.7,       # 高风险阈值
    "risk_level_medium": 0.4,     # 中风险阈值
}
```
```269:277:ad-compliance-agent/backend/review_agents/orchestrator.py
def create_orchestrator() -> Agent:
    """创建主编排 Agent"""
    from agents import ModelSettings
    return Agent(
        name="广告审核Agent",
        instructions=INSTRUCTIONS,
        model="deepseek-chat",
        model_settings=ModelSettings(temperature=0.1),
        tools=TOOLS,
```
```9:15:ad-compliance-agent/README.md
### 核心能力

- **多 Agent 自主编排**：4 个专业 Agent 通过 handoff 机制自动串联
- **RAG 知识库检索**：基于《广告法》和平台规范的审核规则库
- **多维度审核**：合规性、真实性、安全性三维审核
- **结构化报告**：自动生成 Markdown 审核报告
- **评估体系**：完整的测评集和评估指标
```
````59:77:ad-compliance-agent/README.md
## 项目结构

```
├── backend/                # 后端代码
│   ├── api/               # API 路由
│   ├── agents/            # Agent 定义
│   │   └── tools/         # Agent 工具
│   ├── knowledge/         # 知识库管理
│   ├── models/            # 数据模型
│   ├── storage/           # 存储层
│   └── evaluation/        # 评估模块
├── data/                   # 数据目录
│   ├── knowledge_base/    # 知识库原始文件
│   ├── test_set/          # 测评集
│   └── chroma_db/         # 向量数据库
├── docs/                   # 文档
├── scripts/                # 工具脚本
└── requirements.txt        # 依赖清单
```
````
````61:90:ad-compliance-agent/docs/architecture.md
### 2.1 Agent 角色定义

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **Orchestrator** | 编排整个审核流程 | 用户审核请求 | 最终审核报告 |
| **Parser Agent** | 解析广告素材 | 广告文案 | 结构化解析结果 |
| **Retrieval Agent** | 检索审核规则 | 解析结果 | 相关规则+敏感词+案例 |
| **Review Agent** | 多维度合规审核 | 规则+素材 | 各维度审核结果 |
| **Report Agent** | 风险评估+报告生成 | 审核结果 | 结构化审核报告 |

### 2.2 Handoff 机制

```
Orchestrator
    │
    │ handoff 1: "解析这个广告素材"
    ▼
Parser Agent
    │
    │ handoff 2: "根据解析结果检索规则"
    ▼
Retrieval Agent
    │
    │ handoff 3: "根据规则进行审核"
    ▼
Review Agent
    │
    │ handoff 4: "生成审核报告"
    ▼
Report Agent
````
```233:239:ad-compliance-agent/docs/architecture.md
### 6.1 新增 Agent

要新增一个 Agent（如"品牌调性审核 Agent"）：

1. 创建 `backend/agents/brand_agent.py`
2. 定义 Agent 的 instructions 和 tools
3. 在 `orchestrator.py` 中添加 handoff
```
- **三处实测**：

  1. `AGENT_CONFIG`（`config.py:68-72`）与 `REVIEW_THRESHOLDS`（`config.py:75-80`）在全仓只有定义处，没有任何读取点。五个 Agent 全部把模型名写死在代码里（`orchestrator.py:275`、`ad-compliance-agent/backend/review_agents/review_agent.py:89`、`ad-compliance-agent/backend/review_agents/report_agent.py:89`、`ad-compliance-agent/backend/review_agents/parser_agent.py:47`、`ad-compliance-agent/backend/review_agents/retrieval_agent.py:68`），`.env` 里的 `DEEPSEEK_MODEL`（`config.py:24`）唯一的下游是 `AGENT_CONFIG`，因此换模型必须改代码。风险等级阈值同样两套：`scoring.py:174-183` 用 20/40/60，`orchestrator.py:152-157` 与 `batch.py:468-472` 用 0-29/30-59/60-79/80-100。
  2. 全仓 `.py` 检索 `handoff` 命中 0 处。`create_parser_agent`、`create_retrieval_agent`、`create_review_agent`、`create_report_agent` 四个工厂函数只有定义、没有导入点与调用点；生产路径只有 `create_orchestrator`，被 `ad-compliance-agent/backend/api/review.py:75`、`ad-compliance-agent/backend/api/batch.py:325`、`ad-compliance-agent/backend/evaluation/evaluator.py:41` 使用。`ad-compliance-agent/backend/api/workflow.py:18` 导入后未使用。
  3. README 与 architecture 描述的是同一份设计稿，两者对进度口径不同。`README.md:11` 把「4 个专业 Agent 通过 handoff 机制自动串联」写进核心能力；`architecture.md:71-90` 给出 handoff 流程图；`architecture.md:239` 把「在 `orchestrator.py` 中添加 handoff」列在扩展性设计里，说明它当时是待办。README 的结构树在 `backend/` 下列的是 `agents/`（`README.md:62-65`），实际目录是 `backend/review_agents/`，`architecture.md:237` 与 `:245` 也有同样的路径偏差。
- **为什么必须记这一条**：迁移时如果照 README 的架构图设计系统，会按多 Agent handoff 划分模块，而参考实现里可复用的只有单 Agent 加三个工具。可复用的是 prompt 里的推理原则与 `scoring.py` 的评分口径，不是那五张 Agent 表格。
- **代价与局限**：这一条只影响对参考实现的判断，不影响结论。`review.py`、`batch.py`、`evaluator.py` 三条路径都真实存在，单 Agent 架构本身能跑；问题在于文档把待办写成了现状。
- **Momcozy 迁移形态**：阈值、模型名、权重一律走配置并在启动时打印生效值；文档里的能力清单只写已实装项，待办进 roadmap 独立小节。若确实需要多 Agent，按 `ad-review-agent` 的分工方式拆成 Tool 加决策引擎，判定权留在决策层，不让每个 Agent 各自出结论。
- **横向对比**：`ad-review-agent` 的 `harness/constraints.yaml` 把阈值、路由、工具掩码分成三个文件，并在注释里标注每个阈值对应的源码位置；代价是引入配置文件与代码漂移的风险，所以它同时要求改配置后更新 version 并重跑 Eval。`ad-compliance-agent` 的两份死配置说明另一侧的失败模式：配置写了没人读，比没有配置更难发现。
- **证据强度**：已实读核实（含全仓检索）

---

## 迁移到 Momcozy 的三条硬约束

1. **裁决只留一个来源**。这个仓库给了正反两个样本：prompt 的三分支是正面样本，`scoring.py` 的「high 词直接 reject」是反面样本，两者并存导致批量路径与单条路径口径不同（S2-02、S2-12）。发布前一次性把关的场景下，建议确定性层出 verdict，LLM 出理由。
2. **证据缺失要单独走一条路**。`evidence_missing` 的动作是补齐 substantiation 后重提，与 reject 的处置完全不同（S2-03）。母婴与健康品类的 claim 大量落在这一格，把它们并入 reject 会直接击穿发布流程。
3. **指标分母必须等于样本总数**。仓库自带的混淆矩阵会把真实标签为 manual_review 的样本整体丢弃，使 accuracy 在极端错判下仍报 1.000（S2-07）。任何要写进 benchmark 报告的指标，都要先断言 `tp + tn + fp + fn == len(cases)`。

## 与前一份报告的核实差异

- 前一份报告把「97% 通过率 + 平均风险分 17.7」当作评测结论并提醒「测评集可能偏易或判定偏宽松」。实读后：该报告测的是不在仓库里的 `train.json` 服饰属性语料，没有标签，因此 97% 是判 pass 的比例，不能按准确率读；生成它的脚本在当前快照里第 65 行就抛 `AttributeError`（`ScoringResult` 无 `confidence` 字段）；报告正文不含任何准确率、精确率、召回率、F1 或混淆矩阵。仓库自身那份带标签的 100 条测评集（pass 50 / reject 30 / manual_review 20）在报告里没有被使用。细节与数字见 S2-09。
- 前一份报告称 `ad_law_core.md` 是「六字段规则」。实测 15 条规则里 `规则内容`、`法规依据`、`严重程度` 三条 15/15，`违规示例` 6/15，`关键词` 3/15，同时具备后两者的只有 R001、R002、R003。按固定六字段去解析这份文件会在 9 条规则上取到空值（S2-10 给出逐条统计）。
- 前一份报告称 `ad-compliance-agent` 的敏感词结果「作为风险信号而非结论」。这句话对 prompt 成立，对 `batch.py` 的批量路径不成立：批量结论直接取 `scoring_result.conclusion`（`batch.py:222`），而 `_determine_conclusion` 第 2 条分支是 high 敏感词直接 reject（`scoring.py:195-197`）。同一仓库内两套口径，见 S2-02。
- 前一份报告引用的路径 `scoring.py`、`metrics.py` 缺少目录前缀，实际为 `ad-compliance-agent/backend/evaluation/` 下；本条只作路径校正，数值（accuracy ≥ 85% 等六个目标值）实读核实无误，见 S2-07。
