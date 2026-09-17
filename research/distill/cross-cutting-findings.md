# 跨分片核实发现（父 Agent 独立复核，不是子 Agent 的转述）

> 这里只放**我亲自复跑过命令、看到过原文**的条目。子 Agent 报的其余内容在各自分片里，未经二次复核的不进本文件。
> 语料根 `/Users/lute/Project/audit_multi_content/research/repos/`，抓取日期 2026-09-15。
>
> 本文件的作用：分片是「按仓库」组织的，而**真正会影响 Momcozy 设计决策的往往跨仓库**。这些条目在最终合并时容易被稀释掉，所以单独存一份。

---

## 1. `cbi` 的认证证据机制是**死声明**（影响：高）

**结论**：`certificationRules.forbiddenWithoutEvidence` 与 `requireEvidence` 在全仓只有写入点，没有读取点。改这个数组不会改变任何审核结论。

**证据**（`backend/src/` 全目录检索）：

```
$ grep -rn "forbiddenWithoutEvidence" .
./rules/platformRules.js:182:      forbiddenWithoutEvidence: ['FDA', 'CE', 'FCC', 'RoHS', 'warranty', 'waterproof', 'medical claims']

$ grep -rn "requireEvidence" .
./rules/platformRules.js:181:      requireEvidence: true,
./services/platformCategoryRuleService.js:78:      requireEvidenceForRiskClaims: true
```

`platformRules.js:181-182` 是唯二命中，都在同一个对象字面量里。`platformCategoryRuleService.js:78` 的 `requireEvidenceForRiskClaims` 是**另一个键、另一个服务**，不消费前者。

**对 Momcozy 的含义**：前一份报告把 `certificationRules` 列为「本项目最重要的可直接复用模块」。**这个判断需要修正**：它的数据结构值得抄，但它在本仓库里没有接上执行点，抄过来必须自己写读取逻辑。真正在生效的是 `severity.unconfirmedCertification` 与正则层。

---

## 2. 同一仓库有三套互不相同的确定性正则层，且互不一致（影响：高）

| 位置 | 价格正则 | 中文 | 其他 |
|---|---|---|---|
| `providers/review/ruleBasedReview.js:6` | `([$€£¥]|USD\|EUR\|AED\|SAR\|JPY\|RUB\|\d+\.\d{2})` | ✓ | 促销、认证 |
| `services/complianceService.js:2` | `([$]|USD\|EUR\|AED\|SAR\|JPY\|RUB\|\d+\.\d{2})` | ✓ | 水印、Logo |
| `services/ruleAuditService.js:4` | `(?:[$€£¥]\s?\d\|\b\d+(?:\.\d{1,2})?\s?(?:usd\|eur\|gbp\|rmb\|cny)\b)` | ✓ | — |

**第一套与第二套的差异是实质性的**：`complianceService.js` 的字符类只有 `$`，漏掉了 `€ £ ¥`。同一张标着 `€99` 的商品图，在 `ruleBasedReview` 层会被判为含价格，在 `complianceService` 层不会。

三套都叫「价格检测」，但语义不同（一套管币种符号，一套管金额形态）。**迁移时最需要避免继承的就是这种多实现并存的局面**：一个维度只能有一套正则，否则同一个素材会得到两个结论。

---

## 3. `pass` 判定在两层的口径不一致，且用了不同的字段名（影响：高）

**证据**：

`providers/review/ruleBasedReview.js:242`（合并双引擎结果）：
```242:242:cbi/backend/src/providers/review/ruleBasedReview.js
    pass: Boolean(ruleData.pass && normalizedVision.pass && !issues.some((item) => item.level === 'high')),
```

`services/reviewReportService.js:117`（报表汇总）：
```117:117:cbi/backend/src/services/reviewReportService.js
    passed: Boolean(task.review?.overallStatus === 'passed' && !issues.some((issue) => issue.isRealComplianceRisk && ['fatal', 'high'].includes(issue.severity))),
```

两处差异：

1. 合并层只排除 `level === 'high'`，报表层排除 `['fatal', 'high']`。**一个 `fatal` 级问题在合并层不会导致 `pass` 为假。**
2. 两层读的字段名不同：合并层读 `item.level`，报表层读 `issue.severity`。同一个 issue 对象上这两个字段是否同源，需要单独确认。

**对 Momcozy 的含义**：这是「发布前把关」场景最不能出错的一处。放行判定必须只有一个权威口径，且 fatal 与 high 的关系要显式定义。

---

## 4. 「能自动修」与「真的会自动修」是两张不同的表（影响：中）

```
$ sed -n '1p' services/autoFixExecutionService.js
const ALLOWED_ACTION_TYPES = new Set(['removeText', 'removeClaim', 'editTextLayout']);
```

执行层只允许 3 种动作。而计划层的 `canAutoFixLater`（`services/reviewFixSuggestionService.js:114-117`）会产出 4 种，多出的 `regenerateMock` 在执行层被 `blockReason()` 明确拒绝。

**对 Momcozy 的含义**：`canAutoFixLater` 直接驱动「哪些问题能自动修、哪些必须人工」，前一份报告建议照抄这个布尔位。正确做法是让**计划层与执行层的动作白名单来自同一处声明**。

---

## 5. 品类注册表共 9 个，**没有母婴品类**；兜底模板的规则强度显著偏低（影响：最高）

**品类清单**（`rules/categoryRules.js`，顶层键，行号为该文件真实行号）：

| 行 | 品类 | 规则完备度 |
|---|---|---|
| 33 | `general` | 兜底模板 |
| 34 | `electronics_general` | 扩展 |
| 48 | `electronics_storage` | 扩展，最完整 |
| 129 | `beauty` | 兜底模板 |
| 130 | `apparel` | 兜底模板 |
| 131 | `home` | 兜底模板 |
| 132 | `tools` | 兜底模板 |
| 133 | `pet` | 兜底模板 |
| 134 | `medical_device` | 扩展 |

**只有两个品类有实质扩展**（`electronics_storage` 与 `medical_device`），其余七个走 `conservativeTemplate`。

**兜底模板的强度**（`rules/categoryRules.js:14-31`）：
```14:30:cbi/backend/src/rules/categoryRules.js
const conservativeTemplate = (categoryId, categoryName, aliases = []) => ({
  categoryId,
  categoryName,
  aliases,
  criticalFields: ['productName', 'category', 'packageIncluded', 'sellingPoints'],
  highRiskFields: ['certifications', 'warranty', 'medicalClaims'],
  evidenceRequiredFields: {
    certifications: 'visible_text',
    warranty: 'visible_text',
    medicalClaims: 'visible_text'
  },
  allowedClaims: [],
  riskyClaims: ['best performance', 'best seller', 'guaranteed result'],
  forbiddenClaimsWithoutEvidence: ['certified', 'warranty', 'guaranteed'],
  imageTypeGuidance: sharedImageTypeGuidance,
  notes: ['Conservative category fallback rule. Internal risk helper only.']
});
```

兜底的 `forbiddenClaimsWithoutEvidence` 只有 3 个泛化词（`certified` / `warranty` / `guaranteed`）。
对比 `medical_device`（`rules/categoryRules.js:134-139`）：
```134:138:cbi/backend/src/rules/categoryRules.js
  medical_device: {
    ...conservativeTemplate('medical_device', 'Medical Device', ['medical device', 'health device']),
    highRiskFields: ['medicalClaims', 'certifications', 'warranty', 'effectiveness'],
    forbiddenClaimsWithoutEvidence: ['FDA approved', 'medical grade', 'clinically proven', 'cure', 'treats']
  }
```

**品类是怎么被选中的**（`rules/categoryRuleUtils.js:15-27`）：按 `aliases` 在产品信息文本里做子串匹配，且跳过 `general`。`medical_device` 的别名只有 `['medical device', 'health device']`。

**对 Momcozy 的含义（这是本次蒸馏里最具体的一条落地结论）**：

1. 吸乳器产品信息里若不含 `medical device` 或 `health device` 字样，**不会命中 `medical_device`，会落到 `general`**，拿到的 `forbiddenClaimsWithoutEvidence` 从 5 条 FDA 相关声明退化成 3 条泛化词。规则强度是**下降**的。
2. `medical_device` 这个品类**已经带有 FDA 相关声明清单**（`FDA approved` / `medical grade` / `clinically proven` / `cure` / `treats`），是现成的最接近模板。
3. Momcozy 需要新增母婴品类（吸乳器 / 喂养用品），并以 `medical_device` 为底稿扩写，不能依赖兜底。
4. 同时要改品类路由：靠别名子串匹配来决定用哪套规则，在美国母婴品类上不够用，因为同一件吸乳器可能被卖家描述成 `breast pump`、`nursing device`、`postpartum care` 等多种说法，全都不在别名表里。

---

## 6. 规则快照是浅拷贝，冻结不彻底（影响：中）

`rules/platformRules.js:287-288` 直接把注册表内对象的引用放进快照，没有深拷贝。当前代码里没有修改点，所以尚未出问题；但「快照冻结 → 审核可复现」这个不变量没有被代码保护，任何一处后续的原地修改都会静默改掉历史快照。

---

## 7. 文档与代码完全脱节（影响：中，方法论层面）

`cbi/README.md` 有 853 行，检索 `ruleBasedReview`、`platformRules.js`、`categoryRules.js` **零命中**。规则体系与四个版本号（`RULE_VERSION v3.2` / `CATEGORY_RULE_VERSION v3.3` 等）只存在于代码注释和 `notes` 字段里。

这是本项目第二次在同一个仓库上遇到「文档不可作为证据」。前一次是 `sinyard` 的 README 张冠李戴，`invoice` 的 README 落后代码八个月。

---

## 8. 语料版本锚点现状（影响：中）

| 仓库 | `.git` | 能否取 commit |
|---|---|---|
| `source-reading-methodology` | ✓ | `f45f579`（2026-08-25） |
| `omniguard` | ✓ | `2b59f76` |
| `cbi` | ✗ | 不能，已确认非 git 仓库 |
| 其余 8 个 | 待逐一确认 | — |

无 `.git` 的仓库，行号锚点的基准只能声明为「本地快照文件内容本身」。这不影响可复现性（快照是冻结的），但影响与上游的对照能力。

---

## 9. `omniguard` 与 `PolySafe`：同一项目，但**不是**「7 处差异全是改名」（父 Agent 的一处断言被更正）

我先前的说法是「7 个文件不同，全部是改名」。**这个说法不准确**，S5 分片在复核时推翻了一半。

复跑证据：

```
$ wc -l PolySafe/.gitignore omniguard/.gitignore
      66 PolySafe/.gitignore
     129 omniguard/.gitignore
$ diff PolySafe/.gitignore omniguard/.gitignore | wc -l
     177
```

`.gitignore` 是**整体重写**（66 行扩到 129 行，diff 177 行），不是改名。

`assets/首页.png` 也不是同一张图：

| 文件 | 尺寸 | 色型 | MD5（前 12 位） | 字节 |
|---|---|---|---|---|
| `PolySafe/assets/首页.png` | 2304×1290 | 8-bit RGBA | `25126e2fdd56` | 709298 |
| `omniguard/assets/首页.png` | 1695×1248 | 8-bit RGB | `7b153a59e7b6` | 404152 |

尺寸、色型、字节数、MD5 全不同，是另一次导出。其余 4 张截图逐字节一致。

另外，改名**单向且不彻底**，`omniguard` 内部仍有 2 处旧名残留：

```
$ grep -n "PolySafe" omniguard/.gitignore omniguard/README.md
omniguard/.gitignore:2:# PolySafe — .gitignore
omniguard/README.md:48:cd PolySafe
```

**仍然成立的结论**：两者是同一个项目，`omniguard` 相对 `PolySafe` **没有功能增量**（`.gitignore` 与截图不影响审计逻辑）。先前「无增量信息」的判断不变，但支撑它的理由要改成「差异集中在品牌串、忽略规则与截图，三处都不涉及代码逻辑」。

**方法论层面的收获**：这一条是子 Agent 更正父 Agent。父 Agent 的断言建立在 `diff -rq` 的**文件级**输出上，没有打开差异文件看内容，于是把「文件不同」直接读成了「改名」。文件级 diff 只能告诉你哪里不同，不能告诉你不同在什么性质上。

---

## 10. 我的大纲写错了两个锚点（由分片作者更正）

| 我在 `01-大纲.md` 里写的 | 实际 | 谁更正的 |
|---|---|---|
| `_REQUIRED_AFTER_CATEGORIES` / `_RECOMMENDED_AFTER_CATEGORIES` 在 `sinyard/contract_review/missing.py` | 在 `risks.py:285` 与 `risks.py:302`；`missing.py:9` 里是 `_TEMPLATES` | S4 |
| `soe-legal` 的结论态是 5 个取值 | 取值集是**开放的**，`skill.md:112-123` 是 6 个，`examples/sample_report.md:43-51` 又用了另外 5 个不同字面量 | S5 |

这两条都不影响已完成的工作（大纲里的锚点本就声明为「候选，写作时必须自己定位」），但它们说明**大纲里的候选锚点同样会错**，这正是方法论要求「即使标了 ✓ 也要重读」的原因。

---

## 11. 降级链把「无法分析」呈现成「没有问题」（影响：最高）

S4 分片做了一次可执行实验，不是推断。`invoice` 的完全降级输入得到：

```
status=合规  score=1.00  issues=0  coverage=100.0
```

根因是覆盖率因子用在乘法位：`score = 基础分 × min(coverage/100, 1.0)`。查不到任何东西时 `coverage` 被算成 100，于是「什么都没读出来」的得分 1.00 高于「查到金额严重不符」的 0.425。

**对 Momcozy 的含义**：这是「发布前把关」最不能出现的一类失效。放行判定必须在**证据覆盖率不足时拒绝放行**，且覆盖率要作为**独立的门禁项**参与，不能只当作分数上的乘性因子。一个视频只抽到 3 帧、一个详情页只抓到一半文字，这类情况必须落到 REVIEW，不能因为「没发现问题」而 PASS。

---

## 12. 一个可复用的反模式清单（跨仓库反复出现，全部有实证）

| 反模式 | 实例 | 出处 |
|---|---|---|
| 声明了规则但没接执行点 | `certificationRules.forbiddenWithoutEvidence` 只有写入点 | `cbi`（见第 1 节） |
| 同一维度多套实现 | 三套价格正则，其中一套漏了 `€ £ ¥` | `cbi`（见第 2 节） |
| 两层口径不一致 | `pass` 判据一层查 `level==='high'`，一层查 `['fatal','high']` | `cbi`（见第 3 节） |
| 计划层与执行层白名单不一致 | `canAutoFixLater` 4 种 vs `ALLOWED_ACTION_TYPES` 3 种 | `cbi`（见第 4 节） |
| 兜底路径比主路径更宽松 | 无法分析 → `score=1.00` | `invoice`（见第 11 节） |
| 定级公式在极端分布下反转 | `low=20` 给出「高/建议暂缓签署」，`high=1` 只到「中」 | `sinyard` |
| 过滤规则误删真问题 | `_filter_actionable_issues` 把「合同商品未在发票中匹配」当正面陈述丢弃 | `invoice` |
| 评测集与训练集重叠 | 留出法测试集 251 条覆盖的 129 个种子句 100% 出现在训练集 | `sinyard` |
| 冻结不彻底 | 规则快照是浅拷贝，传的是注册表内对象引用 | `cbi`（见第 6 节） |
| 文档与代码脱节 | 4 个仓库的 README 与代码不符 | 全部 |

这张表是本次蒸馏里**最可直接用于设计评审**的产物：上面十条，每一条都能写成一个可执行的检查项，用来审我们自己做出来的系统。
