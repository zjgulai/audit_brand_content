#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 S4 分片。所有引用块直接从源文件切片，保证逐字节一致。"""
import os

REPOS = "/Users/lute/Project/audit_multi_content/research/repos"
OUT = "/Users/lute/Project/audit_multi_content/research/distill/shards/S4-rule-engine-and-scoring.md"

WANTED = [
    "sinyard/contract_review/risks.py",
    "sinyard/contract_review/stances.py",
    "sinyard/contract_review/missing.py",
    "sinyard/contract_review/classifier.py",
    "sinyard/contract_review/nlp.py",
    "sinyard/contract_review/training_data.py",
    "sinyard/contract_review/compare.py",
    "sinyard/contract_review/clauses.py",
    "sinyard/contract_review/report.py",
    "sinyard/requirements.txt",
    "invoice/backend/app/agents/cross_validator.py",
    "invoice/backend/app/agents/coordinator.py",
    "invoice/backend/app/agents/invoice_analyzer.py",
    "invoice/backend/app/services/ai_service.py",
    "invoice/backend/app/services/ocr_service.py",
    "invoice/README.md",
]

SRC = {}
for rel in WANTED:
    with open(os.path.join(REPOS, rel), encoding="utf-8") as fh:
        SRC[rel] = fh.read().splitlines()


def _find_first(src, seg):
    n, k = len(src), len(seg)
    if k > n:
        return None
    norm = [s.rstrip() for s in seg]
    for i in range(0, n - k + 1):
        if all(src[i + t].rstrip() == norm[t] for t in range(k)):
            return i
    return None


def C(rel, start, end):
    """引用块：切片后自检首次出现位置，防止 LINE_DRIFT。"""
    seg = SRC[rel][start - 1:end]
    idx = _find_first(SRC[rel], seg)
    assert idx == start - 1, "%s:%d-%d 首次匹配在 %s" % (rel, start, end, None if idx is None else idx + 1)
    return ("cite", rel, start, end)


def render(parts):
    out = []
    for p in parts:
        if isinstance(p, tuple) and p[0] == "cite":
            _, rel, start, end = p
            body = "\n".join(SRC[rel][start - 1:end])
            out.append("```%d:%d:%s\n%s\n```\n" % (start, end, rel, body))
        else:
            out.append(p)
    return "".join(out)


def manifest(parts):
    seen = {}
    order = []
    for p in parts:
        if isinstance(p, tuple) and p[0] == "cite":
            _, rel, start, end = p
            if rel not in seen:
                seen[rel] = []
                order.append(rel)
            seen[rel].append("%d-%d" % (start, end))
    rows = []
    for rel in order:
        rng = sorted(seen[rel], key=lambda s: int(s.split("-")[0]))
        rows.append("| `%s` | %s |\n" % (rel, "、".join(rng)))
    return "".join(rows)


DOC = []
A = DOC.append

A("""# S4 · 硬规则引擎与加权评分（`sinyard` + `invoice`）

> 源码核对基于 `research/repos/` 下仓库快照（2026-09-15 抓取），
> 本片只核 `research/repos/sinyard/` 与 `research/repos/invoice/`，行号口径 `splitlines()`。

## 0. 两个仓库的可信边界

- `sinyard/README.md` 与 `sinyard/使用说明.md` 记录的是「笔记 · 简历工作台」（`server.py`，端口 8787），没有一处提到 `contract_review/`。与审计相关的入口是 `sinyard/webapp.py`（端口 8765），两份文档都没有提它。**README 与代码不符**。
- `invoice/README.md` 的「开发阶段」仍写着只完成「需求分析和技术架构设计」与「项目目录结构创建」，后端 FastAPI 与前端 Vue3 都已落地。**README 与代码不符**。

本片 15 张卡片的分布：`S4-01` 到 `S4-08` 来自 `sinyard/contract_review/`，`S4-09` 到 `S4-13` 来自 `invoice/backend/app/`，`S4-14` 是 `sinyard` 的版本增量机制，`S4-15` 是两组横向对比。

---

## 一、规则单元与判定形态（`sinyard/contract_review`）

### S4-01 规则单元 `RiskFinding` 的七字段 schema

- **出处**：`sinyard/contract_review/risks.py:16-35`（已实读核实）
- **一句话**：一条风险被压成七个字段，机器可读的 `code`、三档 `severity`、三个给人看的 `title`/`message`/`suggestion`，以及两个可空的定位字段 `clause_number`/`clause_label`；`to_dict()` 按固定顺序手写七个键，没有用 `asdict()`。
- **原文**：

""")
A(C("sinyard/contract_review/risks.py", 16, 35))
A("""
- **为什么这样做 / 不这样做会出什么事**：`code` 是稳定字符串，下游才能按规则聚合、做版本增量、挂白名单与豁免；`severity` 与 `code` 分离，同一类问题在不同条款下可以给不同级别。若把一条风险写成一整段自然语言，统计、去重、复检都无法机械化，只能靠人读。
- **代价与局限**：`message` 与 `suggestion` 是成品中文句子，规则命中后无法再做结构化断言，跨语言迁移时只能整句重写。定位字段依赖外部回填，`clause_number` 只在 `_clause_rule_risks` 里赋值，文档级规则留 `None`，HTML 渲染用一句兜底。原文：

""")
A(C("sinyard/contract_review/risks.py", 279, 282))
A("""
""")
A(C("sinyard/contract_review/report.py", 143, 150))
A("""
- **Momcozy 迁移形态**：Finding schema 定为 `{rule_id, severity, title, message, suggestion, asset_anchor, asset_kind}`。`asset_anchor` 承担 `clause_number` 的角色，取值规范按素材类型分三种，视频写 `"00:12-00:19"`、图片写 `"hero_top"`、文案写 `"chars[120:168]"`；`asset_kind` 取 `text` / `image` / `video` / `aigc_video`。`rule_id` 用大写稳定编码，例如 `CLAIM_NO_SUBSTANTIATION`、`CERT_CLAIM_UNVERIFIED`、`SUPERLATIVE_BANNED`。有了 `(rule_id, asset_anchor)` 这对键，「同一条规则在三个素材上各命中一次」才可枚举，后面的复检增量才有键可用。
- **证据强度**：已实读核实

### S4-02 稳定规则编码全表：10 条条款级 + 7 条文档级

- **出处**：`sinyard/contract_review/risks.py:50-349`（已实读核实，并用构造文本逐条实跑）
- **一句话**：条款级 10 条由 7 个 `_check_*` 函数按条款标签分派，文档级 7 条由两张表按「已识别条款标签集合」比对触发，17 条共用同一个 `RiskFinding`。分派表原文：

""")
A(C("sinyard/contract_review/risks.py", 263, 282))
A("""
全表如下，`severity` 与 `code` 的源码行号均在该行给出：

| # | code | severity | 判定函数 | 源码行 | 触发条件 | 实跑结果 |
|---|---|---|---|---|---|---|
| 1 | `BREACH_REMEDY_VAGUE` | medium | `_check_breach` | `risks.py:57-58` | 有违约责任表述，无金额口径 | `乙方逾期交付的，应当承担违约责任。` → 命中 |
| 2 | `ARBITRATION_BODY_MISSING` | high | `_check_dispute` | `risks.py:80-81` | 出现「仲裁」，无机构指称 | `协商不成的，提交仲裁解决。` → 命中 |
| 3 | `ARBITRATION_LITIGATION_CONFLICT` | high | `_check_dispute` | `risks.py:97-98` | 「仲裁」与「诉讼」或「法院」同现 | `协商不成的，可提交仲裁或向法院起诉。` → 命中 |
| 4 | `PAYMENT_DEADLINE_VAGUE` | medium | `_check_payment` | `risks.py:124-125` | 有模糊时间词，无明确日期词 | `甲方应及时付款。` → 命中 |
| 5 | `ACCEPTANCE_CRITERIA_MISSING` | medium | `_check_delivery` | `risks.py:150-151` | 有「验收」，无标准词也无期限词 | `甲方对乙方交付成果进行验收。` → 命中 |
| 6 | `DELIVERY_DEADLINE_MISSING` | medium | `_check_delivery` | `risks.py:168-169` | 有「交付/交货」，无期限词 | `乙方负责交付软件成果。` → 命中 |
| 7 | `UNBALANCED_TERMINATION` | high | `_check_termination` | `risks.py:198-199` | 甲方单方解除，且乙方不得解除或无补偿 | `甲方有权随时解除本合同，乙方不得解除合同。` → 命中 |
| 8 | `UNILATERAL_TERMINATION_CHECK` | low | `_check_termination` | `risks.py:215-216` | 只命中单方解除，未命中失衡条件 | `甲方有权提前终止本合同。` → 命中 |
| 9 | `CONFIDENTIALITY_NO_SURVIVAL` | medium | `_check_confidentiality` | `risks.py:232-233` | 保密义务随解除终止，且无存续约定 | `保密义务自合同解除时终止。` → 命中 |
| 10 | `FORCE_MAJEURE_NOTICE_MISSING` | low | `_check_force_majeure` | `risks.py:253-254` | 有「不可抗力」，无通知或证明词 | `因不可抗力导致不能履行的，双方互不承担责任。` → 命中 |
| 11 | `BREACH_CLAUSE_MISSING` | high | `contract_level_risks` | `risks.py:287-288` | 条款标签集合缺「违约责任」 | 必备表，缺则命中 |
| 12 | `DISPUTE_CLAUSE_MISSING` | high | `contract_level_risks` | `risks.py:294-295` | 条款标签集合缺「争议解决」 | 必备表，缺则命中 |
| 13 | `PAYMENT_CLAUSE_MISSING` | low | `contract_level_risks` | `risks.py:303` | 缺「付款条款」 | 建议表，severity 在 `risks.py:331` 硬编码 |
| 14 | `CONFIDENTIALITY_CLAUSE_MISSING` | low | `contract_level_risks` | `risks.py:304` | 缺「保密义务」 | 同上 |
| 15 | `IP_CLAUSE_MISSING` | low | `contract_level_risks` | `risks.py:305` | 缺「知识产权」 | 同上 |
| 16 | `ACCEPTANCE_CLAUSE_MISSING` | low | `contract_level_risks` | `risks.py:306` | 缺「交付与验收」 | 同上 |
| 17 | `TERM_CLAUSE_MISSING` | low | `contract_level_risks` | `risks.py:307` | 缺「期限与终止」 | 同上 |

- **与前一份报告的关系**：报告的规则清单只列了上表第 1 至第 10 条，并把它描述成「10 条规则由 7 个 `_check_*` 函数分派」，这一段与源码一致。文档级 7 条在同一份报告的第 7 点被单独描述，但没有计入规则总数。按 code 去重后，`contract_review` 的稳定规则编码是 **17 条**。
- **为什么这样做 / 不这样做会出什么事**：`code` 一旦稳定，测试就能直接对集合做断言，文案改写不会让断言失效。`sinyard/tests/test_review.py:68-73` 用 `{finding.code for finding in self.review.findings}` 断言四条核心规则命中。
- **代价与局限**：条款级规则之间没有互斥约束。实跑 `乙方逾期交付的，应当承担违约责任。` 同时命中 `BREACH_REMEDY_VAGUE`（违约表述且无金额）与 `DELIVERY_DEADLINE_MISSING`（出现「交付」且无期限词），而这句话讨论的是违约责任，交付期限并不在这一条里。文档级 7 条依赖分类器的标签，标签错了就整条漏判。
- **Momcozy 迁移形态**：`rule_id` 命名沿用「大类 + 缺陷」结构，建议起步 17 条同构清单，例如 `CLAIM_NO_SUBSTANTIATION`(high) / `CERT_BODY_MISSING`(high) / `CERT_CLAIM_UNVERIFIED`(high) / `SUPERLATIVE_NO_BASIS`(medium) / `BEFORE_AFTER_NO_DISCLOSURE`(medium) / `TESTIMONIAL_NO_DISCLOSURE`(medium) / `PRICE_CLAIM_EXPIRED`(medium) / `COMPARATIVE_NO_BASIS`(medium) / `AIGC_LABEL_MISSING`(low) / `AGE_RESTRICTION_MISSING`(high)，文档级 7 条对应「整份 campaign 的必备素材缺失」表。级别分布直接照搬 sinyard 的比例感：必备项给 high，提示项给 low。
- **证据强度**：已实读核实（表格中 10 条条款级规则的触发条件均用构造文本实跑确认）

### S4-03 「有 A 但缺 B」判定形态

- **出处**：`sinyard/contract_review/risks.py:38-72`（已实读核实 + 实跑）
- **一句话**：合取判定 `有违约责任表述 ∧ ¬有金额口径`，只有两半同时成立才报 `BREACH_REMEDY_VAGUE`(medium)。金额口径本身是一组正则的并集。
- **原文**：

""")
A(C("sinyard/contract_review/risks.py", 38, 47))
A("""
""")
A(C("sinyard/contract_review/risks.py", 50, 72))
A("""
- **为什么这样做 / 不这样做会出什么事**：两半单独看都不构成缺陷。只有 A 时，表面检查会认为「约定了违约责任」而放行；只有 B 时根本无需报。合取之后，规则报的是「写了但不可执行」，这是文本审计里最有价值的一类结论，因为它抓的是「看起来合规」。实跑对照：`乙方逾期交付的，应当承担违约责任。` 命中；同一句加上 `每逾期一日按合同总额万分之五支付违约金` 之后不再命中。
- **代价与局限**：`_AMOUNT_PATTERN` 是中文合同口径的枚举，取值域由作者手写，换语种或换行业就要重写。`违约金\s*(?:人民币)?\s*[0-9０-９壹贰叁肆伍陆柒捌玖拾佰仟万亿]+` 这一支只匹配「违约金」紧跟数字的写法，`违约金按合同总价的 5% 计算` 会因为中间插入文字而落到 `百分之` 那一支才被救回。B 的取值域与 A 在同一段文本内，同一句话自己写一句「按日万分之五」即可同时满足，规则无法分辨这个数字是否真实存在。
- **Momcozy 迁移形态**：这是本片最可直接迁移的一条，广告场景的 claim 与 substantiation 完全同构。建议写法：

  - A 集合（claim 触发词）：`_CLAIM = re.compile(r"(去除|缓解|预防|改善|修复|促进|增强|提升|抗菌|杀菌|消毒|无毒|无害|食品级|医用级|临床验证|医生推荐|经检测|FDA|专利|独家|最|第一|100%|99\\.9%)")`
  - B 集合（证据标记）：`_EVIDENCE = re.compile(r"(临床研究|临床试验|第三方检测|检测报告|认证编号|注册号|报告编号\\s*[:：]\\s*\\S+|n\\s*=\\s*\\d+|p\\s*[<=]\\s*0\\.\\d+|510\\(k\\)|PMA)")`
  - 判定：`if _CLAIM.search(copy_text) and not _EVIDENCE.search(evidence_blob): → ClaimNoSubstantiation(severity="high")`

  关键差别在 B 的取值域。sinyard 的 B 在同一段文本内，广告场景的 B 必须来自素材之外的证据包，也就是证书编号、检测报告编号、临床数据这类可外部核验的字段；否则文案自己补一句「经检测」就能过关，规则立刻失效。这条也决定了输入契约：审计接口除了素材本身，还要求调用方提交 `evidence_pack`，缺这个字段时对应规则只能输出 `insufficient_input`。
  法域提示：sinyard 这一条的 `suggestion` 引用《民法典》第 585 条，那是中国法。美国市场这一条落到 FTC 的「competent and reliable scientific evidence」标准上，健康类声明还要叠加 FDA 的器械与药品口径。规则形态可搬，法条引用不可搬。
- **证据强度**：已实读核实

### S4-04 具体性双重校验：机构指称 + 互斥冲突

- **出处**：`sinyard/contract_review/risks.py:43-47`、`risks.py:77-109`（已实读核实 + 实跑边界）
- **一句话**：同一个争议解决条款走两次独立检查，出现「仲裁」但没有任何机构指称报 `ARBITRATION_BODY_MISSING`(high)，「仲裁」与「诉讼」或「法院」同现报 `ARBITRATION_LITIGATION_CONFLICT`(high)。机构指称用一条正则枚举。
- **原文**：

""")
A(C("sinyard/contract_review/risks.py", 43, 47))
A("""
""")
A(C("sinyard/contract_review/risks.py", 77, 109))
A("""
- **为什么这样做 / 不这样做会出什么事**：具体性缺失与条款自相矛盾是两类缺陷，处置动作不同。前者要补机构名，后者要删掉一种方式。合成一条规则会让 `suggestion` 无法给出可执行动作。
- **代价与局限**：这条正则不是封闭白名单。第一个分支是泛化的 `仲裁委员会|仲裁院|仲裁中心`，任何以这三个后缀结尾的机构名都会通过，后面列的贸仲、北仲、深国仲等具体名称实际上是冗余的。实跑三例：`协商不成的，提交上海仲裁委员会仲裁。` 不命中；`协商不成的，提交杭州仲裁委员会仲裁。` 也不命中；`协商不成的，由合同签订地仲裁机构仲裁。` 命中，因为「仲裁机构」不含三个后缀。换句话说规则抓的是「有没有机构样式的词」，抓不到「机构是否真实存在」。另外两条规则是并列的 `if`，没有 `elif`，实跑 `协商不成的，可提交仲裁或向法院起诉。` 会同时命中两条 high。
- **Momcozy 迁移形态**：两层校验直接照搬。第一层把「提到认证」升级为「给出可核验编号」：`_CERT_BODY = re.compile(r"(FDA|CPSC|ASTM|JPMA|CPSIA|FCC|CE|TÜV|SGS|Intertek|Bureau Veritas)")` 加编号要求 `_CERT_ID = re.compile(r"(?:编号|No\\.?|#)\\s*[A-Z0-9\\-]{4,}")`，只命中前者不命中后者时报 `CERT_CLAIM_UNVERIFIED`(high)。第二层做互斥对表：`{("FDA 批准", "not evaluated by the FDA"), ("BPA-free", "contains BPA"), ("clinically proven", "results not typical")}`，同一素材内两侧同现报 `CLAIM_CONFLICT`(high)。互斥表比白名单更适合品牌内容，因为品牌文案里的冲突大多是「主图说 A、详情页说非 A」这种跨素材矛盾。
- **证据强度**：已实读核实

### S4-05 定量定级公式与 comment 映射

- **出处**：`sinyard/contract_review/stances.py:9-32`（已实读核实 + 实跑边界）
- **一句话**：`score = min(100, high*30 + medium*12 + low*5)`，等级三分支，每个等级绑一句 comment。
- **原文**：

""")
A(C("sinyard/contract_review/stances.py", 9, 32))
A("""
- **为什么这样做 / 不这样做会出什么事**：定级交给公式，模型不参与，同一份材料在任何机器上得到同一个分数与同一个等级。comment 把分数翻译成动作，三句对应三种处置：暂缓签署、逐项澄清、可签署。
- **代价与局限**：`score` 参与等级判定，低风险的数量可以独立抬高等级，严重度语义被计数淹没。实跑边界：

  | 输入 | score | level | comment |
  |---|---|---|---|
  | high=0 medium=0 low=3 | 15 | 低 | 可签署，但仍建议由专业人员复核 |
  | high=0 medium=0 low=4 | 20 | 中 | 建议签署前逐项澄清并修改中风险条款 |
  | high=0 medium=0 low=20 | 100 | 高 | 建议暂缓签署，先解决高风险条款 |
  | high=0 medium=1 low=0 | 12 | 低 | 可签署，但仍建议由专业人员复核 |
  | high=1 medium=0 low=0 | 30 | 中 | 建议签署前逐项澄清并修改中风险条款 |
  | high=2 medium=0 low=0 | 60 | 高 | 建议暂缓签署，先解决高风险条款 |

  20 条低风险能产出「建议暂缓签署」，而 1 条高风险只到「中」。对发布闸门来说这是方向性错误：一条 high 应当直接阻断。
- **Momcozy 迁移形态**：拆成两段。动作档只看最高严重度：存在 high → `block`；无 high 有 medium → `revise`；只有 low → `pass` 并记录。`score` 只做同档内排序与展示，不参与动作判定。若沿用 sinyard 的一体式公式，20 条「用语不规范」会直接触发阻断发布，闸门会因为噪声失去权威性。
- **证据强度**：已实读核实

### S4-06 多立场审查：同一份材料按立场给不同结论

- **出处**：`sinyard/contract_review/stances.py:35-122`（已实读核实 + 实跑）
- **一句话**：`_default_stance()` 把 code 映射到 `(不利方, 理由)`，`review_stances()` 再用缺陷文本里的「甲方/委托方」做四次特判覆盖，最后按两个当事人名分别汇总关注项计数。
- **原文**：

""")
A(C("sinyard/contract_review/stances.py", 35, 56))
A("""
""")
A(C("sinyard/contract_review/stances.py", 59, 98))
A("""
""")
A(C("sinyard/contract_review/stances.py", 100, 122))
A("""
- **为什么这样做 / 不这样做会出什么事**：同一处缺陷对不同签约方的分量不同。把「谁吃亏」显式建模之后，报告才能按立场分发，谈判清单也才能按立场排序。`_default_stance` 覆盖 15 个 code，未覆盖的 `UNBALANCED_TERMINATION` 与 `UNILATERAL_TERMINATION_CHECK` 由 `review_stances` 的特判分支通过缺陷文本判断不利方。
- **代价与局限**：`impact_for` 的比较对象不匹配。`adverse_party` 的取值域是一组角色名（`收款方`、`守约方`、`披露方`、`采购/委托方`、`成果出资方`、`主张免责方`、`双方`），`impact_for` 却拿它和真实当事人名（从合同要素里抽出的甲乙方名称）比较。实跑：`PAYMENT_DEADLINE_VAGUE` 的 adverse 为 `收款方`，两个当事人名都不等于它，于是两侧都返回「需按身份确认」。更严重的是 `count_for()` 只统计 adverse 等于当事人名或 `双方` 的项，这条风险在 `a_summary` 与 `b_summary` 里同时消失。实跑数据：matrix 5 条，`a_summary.concerns=2`，`b_summary.concerns=4`，2 加 4 只有 6 而其中两条 `双方` 被两侧各计一次，`收款方` 那条不计入任何一侧。
- **Momcozy 迁移形态**：立场轴换成 `brand` / `platform` / `consumer` 三值枚举。判定表用 `rule_id → 受影响方集合`，例如 `CLAIM_NO_SUBSTANTIATION → {brand, consumer}`、`AIGC_LABEL_MISSING → {platform, consumer}`、`PRICE_CLAIM_EXPIRED → {platform, brand}`。受影响方直接取枚举值，不要引入自由文本角色名，避免上面那类比较失配。汇总输出改成「每个受影响方的 high/medium 计数」，三侧各一份，口径就是集合成员判定。
- **证据强度**：已实读核实

### S4-07 文档级必备 / 建议条款缺失扫描与补丁模板

- **出处**：`sinyard/contract_review/risks.py:285-337` 与 `sinyard/contract_review/missing.py:9-78`（已实读核实）
- **一句话**：两张表按「已识别条款标签集合」做差集，必备类缺失直接报对应 severity（两条 high），建议类缺失统一报 low 并附「如确实不需要可忽略」；`missing.py` 另有 7 类模板，为每个缺失类目给出可直接落地的补充条款正文。
- **原文**：

""")
A(C("sinyard/contract_review/risks.py", 285, 308))
A("""
""")
A(C("sinyard/contract_review/risks.py", 311, 337))
A("""
""")
A(C("sinyard/contract_review/missing.py", 9, 27))
A("""
""")
A(C("sinyard/contract_review/missing.py", 56, 78))
A("""
- **位置纠正**：本片任务书沿用大纲的候选锚点表，把 `_REQUIRED_AFTER_CATEGORIES` 与 `_RECOMMENDED_AFTER_CATEGORIES` 记在 `sinyard/contract_review/missing.py`。实读：两张表都在 `sinyard/contract_review/risks.py:285-308`，由 `contract_level_risks()` 消费；`missing.py` 里的是 `_TEMPLATES`（7 个类目映射到 `(紧急度, 理由, 补充条款正文)`）。两个模块解决的是同一问题的两半：`risks.py` 产出机器可读的缺失项，`missing.py` 产出可以直接粘贴的补丁文本。
- **为什么这样做 / 不这样做会出什么事**：文档级检查与条款级检查的输入不同。条款级看单条文本，文档级看整份材料的类目集合，两者合起来才覆盖「写错了」与「根本没写」两种情形。建议类缺失带一句「如确实不需要可忽略」，把是否忽略的决定权交回读者，避免把提示堆成噪声。
- **代价与局限**：两套严重度词表并存。`risks.py` 用 `high/medium/low`，`missing.py` 的 `_TEMPLATES` 用 `高/中`，同一个「争议解决缺失」在前者是 high、在后者是 高，跨模块聚拢时要再做一次映射。模板正文用 `〔…〕` 占位，`build_gap_suggestions` 只替换甲乙方名，金额、日期、期限这些占位符留给读者手填。
- **Momcozy 迁移形态**：把「条款标签集合」换成「素材必备要素集合」。必备表建议为 `{风险提示语, 适用人群与年龄限制, 数据来源与测量条件, AIGC 标注}`，缺一项即 `block`；建议表建议为 `{售后与保修说明, 对比基准声明, 免责声明, 认证编号}`，缺一项记 low。两张表用同一套 `high/medium/low`，不要再造第二套词表。模板层的角色由「可直接插入文案」承担，例如缺 `AIGC 标注` 时给出可插入画面的标注句，缺 `数据来源` 时给出「基于第三方实验室 n=30 的测试结果」这类占位句式。
- **证据强度**：已实读核实

### S4-08 零依赖字符 n-gram 分类器：确定性基线的真实成色

- **出处**：`sinyard/contract_review/classifier.py:18-141`、`sinyard/contract_review/nlp.py:16-89`、`sinyard/contract_review/training_data.py:9-259`（已实读核实 + 实跑）
- **一句话**：手写 softmax 回归加动量 SGD，特征是字符 2 到 4 gram，训练语料由 157 条人工种子句乘 8 个通用前后缀扩增成 1256 条。
- **原文**：

""")
A(C("sinyard/contract_review/classifier.py", 18, 24))
A("""
""")
A(C("sinyard/contract_review/classifier.py", 32, 70))
A("""
""")
A(C("sinyard/contract_review/classifier.py", 121, 141))
A("""
""")
A(C("sinyard/contract_review/nlp.py", 16, 39))
A("""
""")
A(C("sinyard/contract_review/training_data.py", 228, 251))
A("""
""")
A(C("sinyard/requirements.txt", 1, 2))
A("""
- **为什么这样做 / 不这样做会出什么事**：条款分类是这条链路里唯一需要语义的一步。用可离线、可复现的小模型完成，整条链路没有任何网络调用，每次运行结果一致（`seed=42`）。作为 benchmark 的确定性基线，它给出的是「不用模型能做到什么程度」的下界，成本为零。
- **代价与局限**：三点，都可验证。

  第一，「零依赖」的说法要收紧。`sinyard/requirements.txt` 只有一行有效依赖 `numpy>=1.24`。准确表述是不依赖 sklearn、torch 与任何模型 API，NumPy 仍是硬依赖，实测在没有 NumPy 的环境里 `import contract_review` 直接 `ModuleNotFoundError`。

  第二，`evaluate()` 的准确率衡量的是模板记忆。语料里同一个种子句有 8 个前缀变体，而 `evaluate()` 在整份语料上做 20% 随机留出。复刻 `classifier.py:127-133` 的划分（`random.Random(7).shuffle` 加 20% 切分）实跑：语料 1256 条，测试集 251 条，覆盖 129 个种子句，这 129 个种子句 **100% 也出现在训练集里**（其余 7 个前缀变体落在训练侧）。这个数字不能用来估计泛化能力。

  第三，`training_data.py:2` 的 docstring 写「覆盖 12 类常见条款」，`CATEGORIES` 实际列了 13 类。**文档与代码不符**。另外 `build_training_corpus()` 里的 `if text.endswith("。"): pass` 是空分支，不产生任何行为。

- **Momcozy 迁移形态**：把 13 个条款类目换成素材维度，建议为 `功效声明` / `安全声明` / `认证声明` / `价格促销` / `对比贬低` / `人群适用` / `AIGC 标识` / `数据引用` 八类。种子句按美国市场 FTC 语境重写，前缀扩增机制可以保留。评测集必须与训练语料跨模板划分：先按种子句分组，整组进训练或整组进测试，否则会重复上面的泄漏，得到一个虚高的基线分。这个分类器只承担维度路由（决定该素材跑哪一组规则），不承担判定。
- **证据强度**：已实读核实

### S4-14 版本比对：按规则编码计算风险增量

- **出处**：`sinyard/contract_review/compare.py:34-154`（已实读核实）
- **一句话**：两个版本各自跑一遍完整审查，再按 `code` 做三个集合（removed / added / kept），并给出两版的 severity 计数；条款按「第X条」编号对齐，相似度不低于 0.98 且标签相同判为 unchanged。
- **原文**：

""")
A(C("sinyard/contract_review/compare.py", 118, 138))
A("""
""")
A(C("sinyard/contract_review/compare.py", 74, 81))
A("""
- **为什么这样做 / 不这样做会出什么事**：复检场景只需回答两件事，上次提的问题改了没有、有没有改出新问题。按 `code` 而不是按文本比对，「同一条规则不再命中」才成为可判定事实，也才能让测试断言 `risk_delta`。`sinyard/tests/test_web.py:155-160` 就是这么断言的：比对两个样例合同后，`ARBITRATION_BODY_MISSING` 与 `UNBALANCED_TERMINATION` 落在 `removed` 里，新版 high 计数为 0。
- **代价与局限**：`old_findings` 与 `new_findings` 用 dict 以 `code` 为键，同一 code 在多处命中时只剩一条，增量表会低估数量。条款对齐依赖编号，两个版本重排条文编号后对应关系错位，代码自己在 `note` 里提示需要人工复核：

""")
A(C("sinyard/contract_review/compare.py", 152, 154))
A("""
- **Momcozy 迁移形态**：键改成 `(rule_id, asset_anchor)`，让「同一条规则在三个素材上命中」保留三条。改稿后复检的输出直接进审批界面三张表：`removed` 是本次改稿的交付物，`added` 是回归项，`kept` 是未处理项。`old_summary` 与 `new_summary` 的 high 计数可以直接作为「本次改稿是否引入新高危」的门禁条件。
- **证据强度**：已实读核实

---

## 二、确定性规则 + 加权评分 + 降级（`invoice/backend`）

### S4-09 带阈值分档的量化规则

- **出处**：`invoice/backend/app/agents/cross_validator.py:91-217`（已实读核实）
- **一句话**：金额差异率 `>0.2` 判 high、`>0.05` 判 medium，每档的 `description` 用 f-string 带上真实数字与百分比、`recommendation` 给出下一步动作；另外三条确定性规则做当事人姓名逐张比对、重复发票汇总、合同商品集合与发票商品集合的双向差集。
- **原文**：

""")
A(C("invoice/backend/app/agents/cross_validator.py", 91, 124))
A("""
""")
A(C("invoice/backend/app/agents/cross_validator.py", 126, 160))
A("""
""")
A(C("invoice/backend/app/agents/cross_validator.py", 162, 217))
A("""
- **为什么这样做 / 不这样做会出什么事**：阈值把连续量变成可解释的结论，描述里带具体数字，读报告的人不用回头翻原始文件。早退分支让缺数据时保持沉默，`if not contract_amount: return issues` 避免用 0 当分母造出假阳性。四条规则全部不依赖模型，实跑可在无 API 密钥环境下给出完整结论。
- **代价与局限**：同一套「金额不符」规则在本仓库里有第二份实现，阈值与级别都不同。`coordinator.py:167-203` 的 `_basic_validation` 用 `diff / contract_amount > 0.1` 判 medium、标题为「金额差异较大」，主路径用的是 `>0.2` 判 high 与 `>0.05` 判 medium。降级路径与主路径对同一份数据给出不同级别的结论。商品的匹配用精确字符串集合运算 `contract_names - invoice_names`，名称里多一个空格或多一个规格后缀就算「未在发票中找到」。原文：

""")
A(C("invoice/backend/app/agents/coordinator.py", 180, 190))
A("""
- **Momcozy 迁移形态**：分档结构可搬，具体阈值必须用 Momcozy 自己的历史拒审样本重新标定，不能直接搬 0.2 与 0.05。每条量化规则必须内嵌实测数字与定位，形如「字幕『3 倍吸力』与口播『2 倍吸力』在第 00:12 处不一致，差异率 50%」。可量化的内容项建议为：文案与画面文字的 claim 不一致率、视频中口播与字幕的时间偏移、必填要素的缺字符占比。阈值只出现一处，避免出现 invoice 那样的双实现。
- **证据强度**：已实读核实

### S4-10 加权扣分与覆盖率因子

- **出处**：`invoice/backend/app/agents/cross_validator.py:219-254`（已实读核实 + 实跑）
- **一句话**：基础分 1.0，每个 high 扣 0.15、medium 扣 0.05、low 扣 0.01，再乘以覆盖率因子 `min(coverage/100, 1.0)`，下限 0.0；覆盖率在合同金额为 0 时返回 100.0，发票总额为 0 时返回 0.0。
- **原文**：

""")
A(C("invoice/backend/app/agents/cross_validator.py", 219, 254))
A("""
- **为什么这样做 / 不这样做会出什么事**：扣分制比命中计数更能反映严重度分布。覆盖率因子把「未开票部分」折算成折扣，避免只开了两成发票却因为查不出问题而拿到满分。
- **代价与局限**：乘性因子会把严重度一起压低，并且与状态判定脱节。实跑三例：合同金额 100、发票总额 50 时命中一条 high，覆盖率 50，最终 score 为 `(1 - 0.15) * 0.5 = 0.425`；合同金额 100、发票总额 10 时同样是 high，score 为 `0.85 * 0.1 = 0.085`；而完全无法分析时 issues 为空、覆盖率为 100，score 为 **1.00**。也就是说「什么都读不出来」在分数上高于「查到一条严重不符」。`_determine_status` 只看 issues 里的最高严重度，与 score 完全独立，会出现 score 0.42 配「不合规」、score 1.00 配「合规」这类互不解释的组合。
- **Momcozy 迁移形态**：覆盖率不要参与乘算。改成硬闸门：取到可分析文本的素材占比低于阈值（例如 100%，发布前一次性把关的场景可以要求全覆盖）时直接进 `insufficient_input` 状态，不产出分数。分数只由 issue 扣分决定，公式用 `max(0, 1 - (0.15*high + 0.05*medium + 0.01*low))`，并设一条「存在 high 时分数无意义」的短路规则，让闸门只看状态。
- **证据强度**：已实读核实

### S4-11 多级降级链：专用接口 → 通用接口 → 本地工具 → 本地解析

- **出处**：`invoice/backend/app/services/ai_service.py:601-803`、`invoice/backend/app/agents/invoice_analyzer.py:42`、`invoice/backend/app/services/ocr_service.py:91-95`（已实读核实 + 实跑）
- **一句话**：发票识别按四级推进，百度增值税发票专用接口 → 百度通用文字识别 → 本地 Tesseract（需显式开关）→ 正则本地解析；结构化失败时由 `_parse_invoice_text_locally` 兜底，OCR 与结构化全部失败时由 Agent 层 `_fallback_extract` 产出全空骨架并打 `_fallback: True`。
- **原文**：

""")
A(C("invoice/backend/app/services/ai_service.py", 601, 662))
A("""
""")
A(C("invoice/backend/app/services/ai_service.py", 718, 723))
A("""
""")
A(C("invoice/backend/app/services/ai_service.py", 774, 803))
A("""
- **`_fallback` 标记的消费者**：合同侧产出骨架时打上 `_fallback`，交叉验证读到它就跳过 AI 分析、只跑四条确定性规则。

""")
A(C("invoice/backend/app/agents/cross_validator.py", 43, 57))
A("""
- **与前一份报告的关系**：报告称这条链意味着「外部服务不可用时仍能产出结果」。实读有两处限制要补上。第一，Tesseract 那一级由 `allow_local_fallback` 把关且默认为 `False`，主流水线的调用点没有传这个参数，所以主流水线到不了 Tesseract 级。第二，合同侧没有本地兜底，`extract_contract_info` 在百度客户端缺失时直接抛异常：

""")
A(C("invoice/backend/app/agents/invoice_analyzer.py", 38, 50))
A("""
""")
A(C("invoice/backend/app/services/ai_service.py", 360, 362))
A("""
  只有独立的 OCR 接口路径会把开关透传下去：

""")
A(C("invoice/backend/app/services/ocr_service.py", 91, 95))
A("""
- **代价与局限**：降级链的末端把「无法分析」呈现成了「没有问题」。实读 `_check_amount_consistency`、`_check_party_match`、`_check_item_coverage` 的早退分支，合同信息为全空骨架时四条规则全部不产出 issue；`_determine_status` 在没有 issue 时返回 `合规`；`_calculate_coverage` 在合同金额为 0 时返回 100.0，于是 `_calculate_score` 返回 1.0。实跑完全降级的输入，得到 `status=合规 score=1.00 issues=0 ai_validated=False coverage=100.0`。降级本身是工程上正确的动作，缺的是把降级事实带进结论。
- **Momcozy 迁移形态**：降级必须在状态里留痕。最终状态建议四值 `pass` / `revise` / `block` / `insufficient_input`，任何素材取不到文本或证据包缺失时进 `insufficient_input`，禁止与 `pass` 合并。`_fallback` 这个布尔标记值得保留，语义从「本环节降级了」升级为「本素材未完成分析」，由聚合层读取并阻断放行。多级链的层数按可用性排，Momcozy 的四级建议为视觉模型 → 通用多模态模型 → 本地 OCR 加规则 → 纯规则，且每一级都要写入 issue 的 `analyzed_by` 字段，便于事后统计各级的准确率。
- **证据强度**：已实读核实

### S4-12 LLM 输出后置过滤：用正负关键词表清洗违规清单

- **出处**：`invoice/backend/app/agents/cross_validator.py:76-89`（已实读核实 + 实跑）
- **一句话**：LLM 返回的 issues 逐条拼 `title + description`，命中正面词且不命中负面词就丢弃，判据一行是 `if is_positive and not is_negative: continue`。
- **原文**：

""")
A(C("invoice/backend/app/agents/cross_validator.py", 76, 89))
A("""
- **调用点**：过滤器只作用在 LLM 分支上，确定性规则产出的四条不经过它。

""")
A(C("invoice/backend/app/agents/cross_validator.py", 30, 36))
A("""
""")
A(C("invoice/backend/app/agents/cross_validator.py", 47, 54))
A("""
- **为什么这样做 / 不这样做会出什么事**：模型经常把「已核对一致」这类结论塞进 issues 数组。如果不清理，报告会同时出现合规说明与违规条目，聚合层按 severity 统计时会误判。过滤放在 LLM 分支的上游，确定性规则的结果不受影响。
- **实跑结果**：把 `cross_validator.py:76-89` 逐字取出后执行，输入七条构造 issue：

  | 输入（title / description） | 结果 |
  |---|---|
  | 发票与合同一致 / 金额一致 | 丢弃 |
  | 一切正常 / 未发现问题 | 丢弃 |
  | 金额不一致 / 合同金额与发票总额不一致 | 保留 |
  | 卖方信息不匹配 / 发票 x 卖方甲与合同卖方乙不一致 | 保留 |
  | 发票包含合同外商品 / 发票商品不在合同中: C | 保留 |
  | 经核对，发票信息与合同一致 / 未发现异常 | **保留**（意外） |
  | 商品未在发票中找到 / 合同商品未在发票中匹配: A, B | **丢弃**（意外） |

- **代价与局限**：词表用的是子串匹配，`匹配` 是正面词，`未在发票中匹配` 会被判成正面陈述；`未发现异常` 里的 `异常` 命中负面词表，让一句正面陈述逃过过滤。当前实现只对 LLM 输出调用该过滤器，所以第二条意外暂时不会丢掉真实问题；一旦把它下沉成统一出口，`商品未在发票中找到` 这类真问题会被静默删除。改法有两条：把词表换成带边界的正则（例如 `(?<!不)一致`、`未发现(?!异常)`），或者改成白名单式过滤，只保留命中违规特征词的条目。两条都不改时，至少要把被丢弃的条目写进日志，让静默删除可审计。
- **Momcozy 迁移形态**：这一层任何用 LLM 产出违规清单的系统都需要抄。词表换成内容审计的动作词。正面词表取 `已核验` / `证据充分` / `符合要求` / `未发现违规` / `无需修改`；负面词表取 `缺失` / `未提供` / `不一致` / `超出` / `无效` / `过期` / `无法核验`。再加一条硬约束：`severity` 为 high 的条目一律不做关键词过滤，只在聚合层做去重，避免过滤器误杀最贵的结论。AIGC 视频 benchmark 场景还要多一层，模型对「美观度」「创意度」这类主观项的正面评价最容易混进问题列表，这类词应当在 prompt 层就限制输出，后置过滤只作为第二道。
- **证据强度**：已实读核实

### S4-13 三态状态判定与它的词表分裂

- **出处**：`invoice/backend/app/agents/cross_validator.py:233-240` 与 `invoice/backend/app/agents/coordinator.py:237-245`（已实读核实）
- **一句话**：`_determine_status` 只看 issues 里的最高严重度，有 high 判不合规、有 medium 判部分合规、否则判合规；同一个函数在协调器里又实现了一遍，返回值换成 `fail` / `warning` / `pass`。
- **原文**：

""")
A(C("invoice/backend/app/agents/cross_validator.py", 233, 240))
A("""
""")
A(C("invoice/backend/app/agents/coordinator.py", 237, 245))
A("""
- **为什么这样做 / 不这样做会出什么事**：三态与发布闸门天然对应，阻断、退回、放行。判定只看最高严重度，逻辑简单到可以单测，不依赖分数。
- **代价与局限**：状态词表在本仓库里有八种取值。`cross_validator` 用 `合规` / `部分合规` / `不合规`，`coordinator` 用 `fail` / `warning` / `pass`，降级路径另加 `需人工复核`：

""")
A(C("invoice/backend/app/agents/coordinator.py", 192, 194))
A("""
  以及合同信息为空时的 `未知`：

""")
A(C("invoice/backend/app/agents/coordinator.py", 170, 172))
A("""
  同一份 issues 从不同入口进来会得到不同字符串，前端要靠映射表兜。另外 `_determine_status` 完全忽略 low 与覆盖率，20 条 low 仍是「合规」，而 `_calculate_score` 可能已经掉到 0.8。
- **Momcozy 迁移形态**：状态定义收在一处，前端只读枚举。四值 `pass` / `revise` / `block` / `insufficient_input` 按最高严重度判定，`insufficient_input` 由覆盖率闸门给出。把「low 超过 N 条」显式建成一条规则，不要靠分数溢出间接表达。三态是发布前把关的最小集，第四值用于表达「材料不足」，这一值与其余三值的动作指向不同。
- **证据强度**：已实读核实

---

## 三、横向对比（必填）

### S4-15-A 同一个「判定并定级」问题，两个仓库的两条路

| 维度 | `sinyard/contract_review` | `invoice/backend/app/agents` |
|---|---|---|
| 判定来源 | 17 条正则规则，无模型调用 | 4 条确定性规则 + LLM 语义补充 |
| 定级来源 | 规则内硬编码 severity | 规则内硬编码 severity |
| 综合分 | `grade_findings` 公式，只看计数 | `_calculate_score` 公式，只看 severity |
| 模型能否改分 | 无模型 | 不能，LLM 返回的 `overall_score` 被丢弃，只取 `issues` |
| 可复现性 | 完全可复现，测试直接断言 code 集合 | 确定性部分可复现，LLM 部分不可复现 |
| 幻觉风险 | 无 | 需要 `_filter_actionable_issues` 兜底 |
| 覆盖边界 | 限于可正则化的形态 | 覆盖语义边界，例如「双方另行协商解决争议」这类没有关键词的写法 |
| 漏报的形态 | 规则未覆盖时静默通过 | 模型可能漏，也可能把正面结论塞进清单 |

两条路的代价说清楚：

`sinyard` 一侧的代价是覆盖窄，而且规则之间没有互斥约束。实跑 `乙方逾期交付的，应当承担违约责任。` 会同时触发违约与交付两条规则；`由合同签订地仲裁机构仲裁。` 能抓，`双方另行确定争议解决方式。` 抓不到，因为文本里没有「仲裁」字样。换来的是零成本、零网络依赖、结果 100% 可复现，以及一句 `assertIn("BREACH_REMEDY_VAGUE", codes)` 就能把规则钉进 CI。

`invoice` 一侧的代价是多一层模型调用、一张必须持续维护的正负关键词表，以及同一规则在两处实现（`cross_validator.py` 用 0.2 与 0.05，`coordinator.py` 用 0.1）。换来的是能覆盖「金额存在差异但两边都没写异常字样」这类语义情形。这里有一条值得单独拎出来的硬约束：**LLM 只能追加 issue，不能改写分数与状态**。分数由 `_calculate_score` 独立算，状态由 `_determine_status` 独立判，模型返回的 `overall_score` 与 `compliance_status` 字段根本没有被读取。这一条让模型即使返回一段自相矛盾的 JSON，也不会污染闸门结论，代价是放弃了大模型在模糊场景下的定级能力。

对 Momcozy 的结论：两条路各取一半。判定用 `sinyard` 的规则编码加合取形态做主干（FTC 的 claim 与 substantiation 关系是规则可表达的），LLM 只用于规则覆盖不到的语义边界，并且沿用 `invoice` 的权限约束，模型只追加候选 issue，分数、状态、动作档全部由代码算。后置过滤层两边都要，`sinyard` 一侧靠规则本身的确定性，`invoice` 一侧靠 `_filter_actionable_issues`。

### S4-15-B 严重度与状态词表：两个仓库各自的分裂点

`sinyard` 在严重度上分裂：`risks.py` 用 `high` / `medium` / `low`，`missing.py` 的 `_TEMPLATES` 用 `高` / `中`，同一个概念两套词。`invoice` 在严重度上统一用 `high` / `medium` / `low`，却在状态上分裂成八种取值。两个仓库都没有把「严重度枚举」与「状态枚举」定义在单一出处，而是各自在函数里硬编码字符串。

Momcozy 的取法：严重度、状态、动作档三张枚举表各定义一次，规则表只引用枚举值。规则表本身用与 `_REQUIRED_AFTER_CATEGORIES` 同样的形态，即 `code → {severity, title, message, suggestion}` 的字典，这样新增规则只改数据不改函数。

---

## 四、核查：与前一份报告及任务书的偏差

每一处都给出被质疑的原话、源码位置与那几行的原文。

1. **位置错记**。任务书与大纲候选锚点表把 `_REQUIRED_AFTER_CATEGORIES` / `_RECOMMENDED_AFTER_CATEGORIES` 挂在 `sinyard/contract_review/missing.py`（78 行）。实读两张表在 `sinyard/contract_review/risks.py:285-308`，`missing.py` 内是 `_TEMPLATES`。证据即 S4-07 的两段引用。

2. **行数口径**。前一份报告写 `risks.py`「约 380 行」。`splitlines()` 实读 349 行。本片所有引用按 349 行口径。

3. **白名单描述**。报告写「机构白名单用正则枚举（贸仲/北仲/上仲/广仲/深国仲/上海仲裁委员会/北京仲裁委员会…）」，读起来像一个封闭白名单。实读正则的前三个分支是泛化的 `仲裁委员会|仲裁院|仲裁中心`，后面列举的具体名称被前面的泛化分支覆盖，规则实际抓的是「有没有机构样式的词」。实跑：`提交杭州仲裁委员会仲裁。` 不命中，`由合同签订地仲裁机构仲裁。` 命中 `ARBITRATION_BODY_MISSING`。

4. **金额模式漏项**。报告列出的金额模式为 `日万分之|千分之|百分之|违约金+数字|违约金率|损失赔偿额`。实读 `risks.py:38-42`，另有 `日千分之`、`万分之`、`违约金标准`、`违约金计算方式` 四个分支，以及 `违约金\s*(?:人民币)?\s*` 这个可选组。

5. **降级链的成立范围**。报告写「多级 OCR 降级链……外部服务不可用时仍能产出结果」。实读有两处限制：Tesseract 级由 `allow_local_fallback` 把关且默认 `False`，主流水线调用点 `invoice_analyzer.py:42` 没有传该参数，只有独立 OCR 接口路径 `ocr_service.py:91-95` 会透传；合同侧 `ai_service.py:360-362` 在百度客户端缺失时直接抛异常，没有本地兜底。且真正保底的结果是全空骨架，实跑得到 `status=合规 score=1.00`。

6. **规则总数**。报告的清单只列条款级 10 条，未把文档级 7 条计入总数。按 `code` 去重，`contract_review` 的稳定规则编码是 17 条。

### README 与代码不符清单

- `sinyard/README.md` 与 `sinyard/使用说明.md` 记录的是「笔记 · 简历工作台」（`server.py`，`http://127.0.0.1:8787`），全篇没有提到 `contract_review/` 与 `webapp.py`（`http://127.0.0.1:8765`）。`contract_review/` 的 16 个模块、`web/` 前端与 `tests/test_review.py` 在文档里不存在。
- `invoice/README.md:35-37` 把「需求分析和技术架构设计」与「项目目录结构创建」列为仅有的两项已完成工作，实际后端与前端均已落地。
- `sinyard/contract_review/training_data.py:2` 的 docstring 写「覆盖 12 类常见条款」，`CATEGORIES` 实际 13 类。

---

## 五、引用清单

本片所有引用块的行号均来自 `splitlines()` 口径的实读，源文件位于 `research/repos/` 下。

| 文件 | 被引区间 |
|---|---|
@@MANIFEST@@
""")

text = render(DOC).replace("@@MANIFEST@@", manifest(DOC))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(text)
print("written:", OUT)
print("chars:", len(text), "lines:", len(text.splitlines()))
print("citation blocks:", text.count("\n```") // 2)
