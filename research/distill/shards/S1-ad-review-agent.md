# S1 · ad-review-agent 资产卡（13 张）

> 源码核对基于 `research/repos/` 下仓库快照（2026-09-15 抓取），
> ad-review-agent commit 见 `research/repos/ad-review-agent/`，行号口径 `splitlines()`。

仓库快照内没有 `.git` 目录，无法给出 commit sha；仓库内文件时间戳统一为 2026-03-30。
本片所有引用均为实读核实，代码块与源文件逐字节一致。

---

## 零、开工前核实的三件事（影响后续所有引用）

### 0.1 `CLAUDE.md` 不是符号链接，是逐字节相同副本

`ls -la` 的权限位：`AGENTS.md` 与 `CLAUDE.md` 均为 `-rw-r--r--`（普通文件，链接位为空）。
inode 分别是 4347388 与 4347389（不同 inode，排除硬链接）。两者 `md5` 相同：
`1f2b8bc99f1851c432a13a93d6483e81`；`diff AGENTS.md CLAUDE.md` 无输出。两份都是 495 行。

`AGENTS.md` 的目标结构一节把它写成链接：

```127:129:ad-review-agent/AGENTS.md
ad-review-agent/
├── AGENTS.md                      ← 你正在读的文件（AHF 三段式）
├── CLAUDE.md                      ← 指向 AGENTS.md 的 symlink
```

快照里没有链接。真实原因记在 `progress.txt` 的 Known Issues：

```44:44:ad-review-agent/progress.txt
  - Windows 环境下 ln -s 无法创建真正的 symlink
```

本片全部引用指向 `ad-review-agent/AGENTS.md`。引用 `CLAUDE.md` 会得到同样内容，
但入库时应只保留一份，避免两份副本各自漂移（核对时两份 MD5 相同，说明此刻尚未漂移）。

### 0.2 `harness/` 下 5 个 YAML，只有 2 个被代码读取

| 文件 | 行数 | 代码引用点 |
|---|---|---|
| `constraints.yaml` | 198 | `src/harness/constraint_loader.py:15` 读取 |
| `model_router.yaml` | 208 | `src/harness/model_router.py:34` 读取 |
| `tool_masks.yaml` | 229 | 零处（`grep -rn "tool_masks" src/ evals/ scripts/` 无命中） |
| `observability.yaml` | 148 | 零处（`grep -rn "observability" src/ evals/ scripts/` 无命中） |

`constraints.yaml` 内部还分两半：`decision_thresholds` 与 `confidence_strategy` 两个段被
`DecisionEngine` 真实读取；`early_termination`、`tool_execution`、
`qualification_required_categories` 三个段只在启动时被检查「键存在」，取值从未被消费
（`constraint_loader.py:47` 只做 `s not in config` 判断）。这条区分贯穿 S1-01、S1-04、S1-11。

### 0.3 前一份报告的三处路径错误，实读核实结果

`research/star-lists-audit-report.md` 写的路径与快照不符，逐条核实如下。

- 它写 `ad-review-agent/decision_engine.py`。实际是 `ad-review-agent/src/agents/decision_engine.py`（190 行）。
- 它写 `ad-review-agent/rules_loader.py`。实际是 `ad-review-agent/src/rules_loader.py`（134 行）。
- 它写 `cbi/backend/src/rules/ruleBasedReview.js`（据大纲转述）。该文件在快照中不存在，
  与 S1 分片无关，此处仅登记已核实的一条：`cbi/backend/src/rules/` 下只有 4 个文件，
  分别是 `categoryRuleUtils.js`（85 行）、`categoryRules.js`（140 行）、
  `platformRuleUtils.js`（85 行）、`platformRules.js`（294 行）。

---

## S1-01 阈值集中声明式外部化

- **出处**：`ad-review-agent/harness/constraints.yaml:1-15`、`ad-review-agent/harness/constraints.yaml:34-58`、
  `ad-review-agent/src/harness/constraint_loader.py:17-24`、`ad-review-agent/src/harness/constraint_loader.py:27-51`、
  `ad-review-agent/src/agents/decision_engine.py:26-38`（已实读核实）
- **一句话**：所有决策阈值收敛到一个 YAML，文件头写明「改阈值 → 改版本号 → 跑 eval 防回归」三步规程，
  并在每个键上方用注释标注它对应的源码位置与源码表达式。

- **原文（文件头规程与版本号）**：

```1:15:ad-review-agent/harness/constraints.yaml
# =============================================================================
# constraints.yaml — 广告素材合规审核 Agent 声明式约束配置
# =============================================================================
#
# 本文件是 review_agent.py 中所有硬编码阈值和决策规则的外部化声明。
# Phase 3a（FEAT-AHF-003）实施后，代码将从此文件读取配置而非使用硬编码值。
#
# 修改本文件后：
#   1. 更新 version 字段
#   2. 运行 Eval 验证指标无回归
#   3. 在 commit message 中注明变更原因
# =============================================================================

version: "1.0.0"
updated_at: "2026-03-29"
```

- **原文（阈值本体，含每个键上方的源码指针）**：

```34:58:ad-review-agent/harness/constraints.yaml
decision_thresholds:
  # confidence ≥ 此值 且无违规 → 自动通过
  # 对应 src/config.py: auto_pass_threshold = 0.92
  # 对应 _determine_verdict(): confidence >= settings.auto_pass_threshold
  auto_pass: 0.92

  # confidence ≥ 此值 且有违规 → 退回修改（RETURNED）
  # 对应 _determine_verdict(): confidence >= settings.auto_pass_threshold + violations
  # 当前与 auto_pass 共用同一阈值
  auto_returned: 0.92

  # confidence < 此值 → 强制人工审核
  # 对应 src/config.py: human_review_lower = 0.70
  # 对应 _determine_verdict(): confidence < settings.human_review_lower → REVIEW
  human_review_forced: 0.70

  # human_review_forced ≤ confidence < auto_pass → 建议人工复核
  # 对应 _determine_verdict(): confidence < settings.auto_pass_threshold → REVIEW
  # 此区间无独立阈值，由 human_review_forced 和 auto_pass 的区间隐含定义
  human_review_suggested_lower: 0.70
  human_review_suggested_upper: 0.92

  # 图片检测独立阈值（当前值与通用阈值一致，预留可独立调整）
  # 对应 src/config.py: image_auto_threshold = 0.92
  image_auto_threshold: 0.92
```

- **原文（加载器只做存在性校验，取值不做范围校验）**：

```17:24:ad-review-agent/src/harness/constraint_loader.py
# 启动时必须存在的顶层字段
_REQUIRED_SECTIONS = (
    "decision_thresholds",
    "early_termination",
    "tool_execution",
    "qualification_required_categories",
    "confidence_strategy",
)
```

```27:51:ad-review-agent/src/harness/constraint_loader.py
@functools.lru_cache(maxsize=1)
def load_constraints() -> dict[str, Any]:
    """
    加载 harness/constraints.yaml 并校验关键字段。

    Returns:
        解析后的配置字典

    Raises:
        FileNotFoundError: constraints.yaml 不存在
        ValueError: 缺少必需的配置字段
    """
    if not _CONSTRAINTS_PATH.exists():
        raise FileNotFoundError(
            f"constraints.yaml not found: {_CONSTRAINTS_PATH}"
        )

    with open(_CONSTRAINTS_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    missing = [s for s in _REQUIRED_SECTIONS if s not in config]
    if missing:
        raise ValueError(
            f"constraints.yaml missing required sections: {missing}"
        )
```

- **原文（消费端：4 个键真正接进了决策）**：

```26:38:ad-review-agent/src/agents/decision_engine.py
    def __init__(self) -> None:
        """
        初始化决策引擎，从 constraints.yaml 加载配置。
        """
        config = load_constraints()

        thresholds = config["decision_thresholds"]
        self._auto_pass: float = thresholds["auto_pass"]
        self._human_review_forced: float = thresholds["human_review_forced"]

        strategy = config["confidence_strategy"]
        self._all_fallback_default: float = strategy["all_fallback_default"]
        self._non_drag_dimensions: set[str] = set(strategy["non_drag_dimensions"])
```

- **为什么这样做 / 不这样做会出什么事**：`AGENTS.md` 把这条写成了强制项，
  两处原文分别是 `「决策阈值定义在 harness/constraints.yaml，不得硬编码在 Python 代码中」`
  （`ad-review-agent/AGENTS.md:51`）与
  `「不许硬编码决策阈值在 Python 代码中（必须在 harness/constraints.yaml 定义）」`
  （`ad-review-agent/AGENTS.md:494`）。动机在 `ad-review-agent/AGENTS.md:11` 的规程里：
  阈值一改，`version` 字段与 eval 结果一起变，回归就有据可查。若不外部化，
  0.92 与 0.70 会散落在判定函数、reason 生成、评测指标三处，改一处忘一处，
  出现「verdict 变了但给审核员的说明还是旧阈值」这类静默不一致。

- **代价与局限（三条，全部有行级证据）**：

  1. **注释里的源码指针在拆分后全部失效，且无人更新。** `constraints.yaml:20-21` 写
     `源码位置: src/agents/review_agent.py → _determine_verdict() (L564-L623)`，
     但 `src/agents/review_agent.py` 只有 60 行，`_determine_verdict` 实际在
     `src/agents/decision_engine.py:132-190`。同一文件里 `constraints.yaml:63` 指向
     `review_agent.py → _should_early_terminate() (L518-L535)`，实际在
     `src/agents/orchestrator.py:409-426`。`constraints.yaml:88` 指向 `review_agent.py → review() (L101-L316)`，
     实际在 `src/agents/orchestrator.py:74-207`。四处可核对的指针全部指向拆分前的旧文件。

  2. **同一个阈值仍有两个来源。** `decision_thresholds.auto_pass` 走 YAML，
     而 `src/agents/result_builder.py:474-478` 仍在读环境变量版本：

```474:478:ad-review-agent/src/agents/result_builder.py
            if confidence < settings.auto_pass_threshold:
                lines.append(
                    f"- 综合置信度 {confidence:.2f}，"
                    f"未达自动通过阈值 {settings.auto_pass_threshold}"
                )
```

     这里的 `settings.auto_pass_threshold` 来自 `src/config.py:28`（默认 0.92，可被环境变量覆盖）。
     把 YAML 的 `auto_pass` 改成 0.99，verdict 会跟着变，reason 文本仍会打印 0.92。
     `result_builder.py:483` 用同一个 settings 值判断「哪些维度拉低了置信度」，同样不同步。

  3. **`auto_returned`、`human_review_suggested_lower`、`human_review_suggested_upper`、
     `image_auto_threshold` 四个键零消费。** `grep -rn "auto_returned\|human_review_suggested_lower\|image_auto_threshold" src/`
     在 Python 侧只命中 `src/config.py:29-31` 的 Settings 字段定义本身；
     `auto_returned` 在 `src/api.py:955` 出现的那次是同名局部变量（统计口径），与 YAML 键无关。
     `auto_returned` 的注释自称「当前与 auto_pass 共用同一阈值」，
     实现上没有共用，是两个独立数字。

- **横向对比**：`cbi` 走的是另一条路。它的平台规则是 JS 源码模块，
  版本号写成导出常量，规则本体与代码同处一个文件：

```1:5:cbi/backend/src/rules/platformRules.js
import { categoryRuleRegistry } from './categoryRules.js';

export const RULE_VERSION = 'v3.2';

const supportedCategoryIds = Object.keys(categoryRuleRegistry);
```

  `cbi/backend` 下没有 `.yaml` / `.yml` 文件（`find cbi/backend -name "*.yaml" -o -name "*.yml"` 无输出），
  规则全部写在 `platformRules.js`（294 行）与 `categoryRules.js`（140 行）里。
  `cbi` 能用这种方式，是因为它的规则是「平台 × 图片类型 × 维度」的结构化嵌套对象，
  改动频率低、且改动必须同步改 9 种 actionType 的处理分支，把规则和代码放在一起反而减少了错配。
  代价是调一条阈值要发版，运营无法自助。`ad-review-agent` 的阈值是四个标量，
  外部化的收益（改数字不动代码）明显大于成本，两边选型都算合理。

- **Momcozy 迁移形态**：建 `harness/constraints.yaml`，字段名直接沿用并扩三层：
  `decision_thresholds.auto_pass`（首发建议 0.90，母婴品类漏审代价高）、
  `confidence_strategy.non_drag_dimensions`、
  `evidence_thresholds.{claim_requires_evidence, substantiation_min_sources}`。
  法域字段新增 `jurisdiction: "US"` 与 `regulation_bodies: ["FTC", "FDA", "CPSC"]`，
  因为 `ad-review-agent` 的 `regulation_ref` 全是《广告法》系条文，
  迁到美国后第九条、第十七条、第二十五条、第二十八条四条锚点全部作废（见 S1-07）。
  同时把 `version` 改成日期戳（`2026-09-15.1`）并在 CI 里加一条断言：
  `harness/constraints.yaml` 的 `version` 变了而 `evals/results/` 没有新文件时报错。
  `ad-review-agent` 把这条规程写在注释里，没有做成检查，实测是失效的。

- **证据强度**：已实读核实（阈值读取、加载器行为、四处失效指针、双来源阈值、四个未消费键均已逐行核对）

---

## S1-02 双轨置信度聚合

- **出处**：`ad-review-agent/src/agents/decision_engine.py:101-130`（已实读核实）
- **一句话**：有违规时取「发现违规的维度」里的 max，无违规时取「非降级、非 non_drag」维度的 min，
  两种口径都不成立时退回常量 0.5。

- **原文**：

```101:130:ad-review-agent/src/agents/decision_engine.py
        # 收集非降级维度的置信度
        normal_confidences: list[float] = []
        for r in dim_to_result.values():
            if r is not None and not getattr(r, "is_fallback", False):
                normal_confidences.append(r.confidence)

        if tool_results.all_violations and normal_confidences:
            # 双轨：取发现违规的维度中的最高置信度
            # 只要任一维度高置信度发现严重违规，就足够退回
            violation_dims = set(v.dimension for v in tool_results.all_violations)
            violation_confs = []
            for dim in violation_dims:
                r = dim_to_result.get(dim)
                if r and not getattr(r, "is_fallback", False):
                    violation_confs.append(r.confidence)
            return max(violation_confs) if violation_confs else min(normal_confidences)

        if normal_confidences:
            # 无违规：排除「无违规且 confidence 偏低」的辅助维度，
            # 这些维度无违规时不应拉低整体置信度阻止 pass
            filtered_confs = []
            for dim, r in dim_to_result.items():
                if r is None or getattr(r, "is_fallback", False):
                    continue
                if dim.value in self._non_drag_dimensions and not getattr(r, "violations", []):
                    continue
                filtered_confs.append(r.confidence)
            return min(filtered_confs) if filtered_confs else min(normal_confidences)

        return self._all_fallback_default
```

- **为什么这样做 / 不这样做会出什么事**：两个方向的风险不对称。退回（RETURNED）是保守动作，
  任一维度高置信度发现问题就够，取 max 让「文案发现绝对化用语，置信度 0.95」不被
  「平台规范维度置信度 0.72」稀释。通过（PASS）是激进动作，要求所有核心维度都确信，
  取 min。若两个方向都用平均，一次高置信度违规会被若干低置信度的通过项摊薄到阈值以下，
  素材进人工队列，自动通过率指标（`AGENTS.md:19` 目标 ≥ 80%）撑不住。

- **代价与局限（两条）**：

  1. **max 分支可能取到一个与违规无关的维度。** `decision_engine.py:110` 用
     `set(v.dimension for v in tool_results.all_violations)` 收集违规维度，
     再对每个维度取它的整体 `r.confidence`，而 `r.confidence` 是该 Tool 对整段素材的
     总体置信度，不是针对那一条违规的置信度。一个维度里同时有 high 和 low 两条违规时，
     max 口径无法区分是哪一条撑起了分数。

  2. **`normal_confidences` 为空但存在违规时，第一分支直接不进。** `decision_engine.py:107`
     的条件是 `tool_results.all_violations and normal_confidences`，两者同时成立才走 max。
     如果所有 Tool 都降级、同时又带着规则库命中的违规（`text_checker.py:246-254` 的降级路径会保留
     规则命中结果并把 `is_fallback` 置 True），则落到 `decision_engine.py:130` 返回 0.5，
     违规清单被忽略，置信度退化为常量。这条路径的实际判定结果仍是 REVIEW（0.5 < 0.70），
     行为安全，但 0.5 这个数字不再携带信息。

- **横向对比**：`ad-compliance-agent` 用加权总分代替双轨聚合，`cbi` 用
  `maxRiskLevel` 做双引擎合并。三者的共同点是都不在「有风险」方向做平均；
  差异在于 `ad-review-agent` 是唯一一个按「有无违规」切换聚合函数的。
  切换的代价是聚合结果不可跨场景比较：同一个 0.93 在有违规时含义是「最确信的那一条」，
  无违规时含义是「最不确信的那一项」。

- **Momcozy 迁移形态**：保留双轨，把维度名换成 Momcozy 的六维：
  `claim_substantiation`（宣称是否有证据）、`medical_device_boundary`（是否越界成医疗器械宣称）、
  `ingredient_safety`（成分安全表述）、`comparative_claims`（对比性宣称）、
  `pricing_and_promotion`（价格与促销）、`testimonial_and_review`（证言与评价）。
  新增一条约束：`violation_confs` 收集时按 `violation.severity == "high"` 过滤后再取 max，
  让置信度对应到具体违规条目，堵掉上面第 1 条局限。
  全降级兜底值不沿用 0.5，改为读 `confidence_strategy.all_fallback_default`，
  因为 Momcozy 的发布前一次性把关场景里，全降级必须走人工，兜底值只需保证落在
  `human_review_forced` 之下。

- **证据强度**：已实读核实

---

## S1-03 non_drag 维度的判定与配置

- **出处**：`ad-review-agent/harness/constraints.yaml:187-193`、
  `ad-review-agent/src/agents/decision_engine.py:118-128`、
  `ad-review-agent/src/agents/decision_engine.py:38`（已实读核实）
- **一句话**：把「图片安全」与「跨维度一致性」标为辅助维度，这两维在无违规时不参与
  min 聚合；一旦它们自己发现了违规，就重新参与。

- **原文（配置侧）**：

```187:193:ad-review-agent/harness/constraints.yaml
  # ── non_drag 维度（L272, L291）──
  # 图片和一致性维度在无违规时不参与 min 计算，
  # 避免这些辅助维度的低置信度阻止自动通过。
  # 对应: _NON_DRAG_TYPES = ("ImageCheckerOutput", "ConsistencyCheckOutput")
  non_drag_dimensions:
    - "image_safety"       # ImageCheckerOutput
    - "consistency"        # ConsistencyCheckOutput
```

- **原文（判定侧，配置里的字符串与该维度的违规列表共同决定是否排除）**：

```118:128:ad-review-agent/src/agents/decision_engine.py
        if normal_confidences:
            # 无违规：排除「无违规且 confidence 偏低」的辅助维度，
            # 这些维度无违规时不应拉低整体置信度阻止 pass
            filtered_confs = []
            for dim, r in dim_to_result.items():
                if r is None or getattr(r, "is_fallback", False):
                    continue
                if dim.value in self._non_drag_dimensions and not getattr(r, "violations", []):
                    continue
                filtered_confs.append(r.confidence)
            return min(filtered_confs) if filtered_confs else min(normal_confidences)
```

- **为什么这样做 / 不这样做会出什么事**：图片与一致性两个维度承担的任务是「找问题」，
  它们对「没问题」的表述天然偏保守（视觉模型的空场景置信度普遍低于文本模型）。
  若让它们进 min，一张氛围图的 0.78 会把整单压到 0.92 之下，素材全部进人工队列。
  `decision_engine.py:125` 的两个条件用 `and` 连接，语义是「这个维度既被标为辅助，
  又确实没抓到东西」才排除；辅助维度抓到违规时回到主聚合里，避免「辅助维度发现问题却被降权」。

- **代价与局限**：排除动作的判据是 `getattr(r, "violations", [])` 是否为空，
  判据里没有「该维度的最高严重度」这一项。一个 non_drag 维度抓到 low 级违规后在
  min 聚合里满权重参与，一张氛围图上的低危提示会把整体置信度拉到阈值下。
  另外 `constraints.yaml:190` 的注释写 `对应: _NON_DRAG_TYPES = ("ImageCheckerOutput", "ConsistencyCheckOutput")`，
  这个符号在快照里不存在：`grep -rn "_NON_DRAG_TYPES" --include=*.py --include=*.yaml .`
  只命中 YAML 注释自身。实现用的是维度字符串集合，
  `decision_engine.py:125` 比对的是 `dim.value`。注释描述的是重构前按 Pydantic 输出类型判断的版本。

- **Momcozy 迁移形态**：`non_drag_dimensions` 直接沿用机制，值换成
  `["visual_claim_consistency", "aigc_provenance"]`。
  母婴品类的图片维度风险高于游戏类，判定条件要从「无违规」改成
  「无 severity ≥ medium 的违规」：`not any(v.severity in ("high","medium") for v in r.violations)`。
  另外补一个反向名单 `drag_dimensions`（必进 min 的维度）：
  `claim_substantiation` 与 `medical_device_boundary` 在任何情况下都不允许被排除，
  这两维的漏判直接触发 FTC 层面的虚假宣传风险。

- **证据强度**：已实读核实（配置读取、判定逻辑、`_NON_DRAG_TYPES` 符号不存在均已逐行核对）

---

## S1-04 提前终止的触发条件与代价

- **出处**：`ad-review-agent/harness/constraints.yaml:60-83`、
  `ad-review-agent/src/agents/orchestrator.py:409-426`、
  `ad-review-agent/src/agents/orchestrator.py:428-453`（已实读核实）
- **一句话**：声明了「high 严重度且置信度 > 0.9 就跳过后续低优先级 Tool」，
  判定函数与「被跳过维度」的计算函数都写好了，但编排主流程里没有任何一处调用它们。

- **原文（声明）**：

```60:83:ad-review-agent/harness/constraints.yaml
# =============================================================================
# early_termination — 提前终止策略
# =============================================================================
# 源码位置: src/agents/review_agent.py → _should_early_terminate() (L518-L535)
#
# 当某个 Tool 检测出高严重度违规且置信度超过阈值时，
# 跳过后续低优先级 Tool，节约成本和时间。
# 被跳过的维度记录到 skip_reasons。

early_termination:
  enabled: true

  # 触发条件（AND 逻辑，两个条件同时满足才触发）
  conditions:
    # 违规严重度必须为 high
    # 对应: any(v.severity == ViolationSeverity.HIGH for v in violations)
    min_severity: "high"

    # 置信度必须严格大于此值（>，非 ≥）
    # 对应: confidence <= 0.9 → return False
    min_confidence: 0.9

  # 跳过的维度记入 skip_reasons，标注原因
  skip_reason_template: "提前终止：前序维度发现高严重度违规（confidence > {confidence}）"
```

- **原文（实现，含硬编码的 0.9）**：

```409:426:ad-review-agent/src/agents/orchestrator.py
    def _should_early_terminate(
        self, violations: list[ViolationItem], confidence: float
    ) -> bool:
        """
        判断是否应提前终止后续 Tool 执行。

        条件：存在 high 严重度违规且置信度 > 0.9。

        Args:
            violations: 当前 Tool 的违规项列表
            confidence: 当前 Tool 的置信度

        Returns:
            是否应提前终止
        """
        if confidence <= 0.9:
            return False
        return any(v.severity == ViolationSeverity.HIGH for v in violations)
```

- **原文（被跳过维度的计算，同样未被调用）**：

```428:453:ad-review-agent/src/agents/orchestrator.py
    def _remaining_dimensions(
        self,
        request: ReviewRequest,
        checked: list[ViolationDimension],
    ) -> list[ViolationDimension]:
        """
        计算因提前终止而被跳过的维度。

        Args:
            request: 审核请求（用于判断哪些维度本应执行）
            checked: 已执行的维度列表

        Returns:
            被跳过的维度列表
        """
        all_applicable: list[ViolationDimension] = [ViolationDimension.TEXT_VIOLATION]
        if request.content.image_urls or request.content.video_url:
            all_applicable.append(ViolationDimension.IMAGE_SAFETY)
        if request.content.landing_page_url:
            all_applicable.append(ViolationDimension.LANDING_PAGE)
        if request.ad_category in _QUALIFICATION_CATEGORIES:
            all_applicable.append(ViolationDimension.QUALIFICATION)
        all_applicable.append(ViolationDimension.PLATFORM_RULE)
        all_applicable.append(ViolationDimension.CONSISTENCY)

        return [d for d in all_applicable if d not in checked]
```

- **未接线的证据**：`grep -rn "_should_early_terminate" --include=*.py --include=*.yaml --include=*.md .`
  只命中两处，一处是 `constraints.yaml:63` 的注释，一处是 `orchestrator.py:409` 的定义。
  `grep -rn "_remaining_dimensions"` 只命中 `orchestrator.py:428` 的定义。
  `orchestrator.py:74-207` 的 `run()` 方法按 Step 1 到 Step 6 顺序执行六个 Tool，
  没有「若已触发则 break」的分支。`harness/observability.yaml:158` 定义了
  `early_termination_total` 指标，但没有代码写入它。
  `progress.txt:46` 的 Known Issues 里记录了
  `「Eval review 类边界案例准确率 44%（LLM 非确定性，非回归）」`，
  同时 `progress.txt:23` 记录最终 eval 为
  `「86.67% accuracy, FN 0%, FP 0%, pass 100%, reject 100%」`，与提前终止无关。

- **为什么这样做 / 不这样做会出什么事**：提前终止把「发现一个 high 违规」当作
  「不必再花后面的钱」的依据。`AGENTS.md:19` 的成本目标是单条素材 ≤ ¥0.05，
  图片/视频视觉检测是最贵的一步（`AGENTS.md:478` 记「图片分析用 Claude … 单次调用约 ¥0.01-0.03」）。
  若某条文案已被规则库判定绝对化用语（high，置信度 ≥ 0.92），跳过图片与落地页检测
  可以把单条成本压到十分之一。代价写在 `constraints.yaml:82-83` 的 `skip_reason_template` 里：
  被跳过的维度必须记入 `skip_reasons`，因为最终结论从「退回」变成了
  「退回，且另外四个维度未审」。对发布前一次性把关的场景，这个代价的关键在于
  广告主改完重提时必须重新全审，否则第二次提交会因为「文案已改，图片未看」而误放。

- **代价与局限**：`enabled: true` 在 YAML 里是打开状态，代码里没有任何开关读取点。
  一旦有人把 `_should_early_terminate` 接进 `run()`，`orchestrator.py:424` 会继续用
  硬编码的 `0.9`，YAML 的 `min_confidence` 与 `min_severity` 仍是死配置。
  另有一处语义细节：`constraints.yaml:78` 的注释写「严格大于此值（>，非 ≥）」，
  与 `orchestrator.py:424` 的 `if confidence <= 0.9: return False` 一致，
  这是全项目里少见的注释与实现完全对齐的地方。

- **横向对比**：`contract_audit` 用图状态机的条件路由实现同一目的
  （仅高风险样本进入最贵的改写节点），走的是显式条件边，判定依据写在图的状态转移里。
  图路由的代价是要引入 checkpointer 与状态契约；`ad-review-agent` 用过程式
  `run()` 步骤顺序，代价是「跳过」这件事只能靠 `_remaining_dimensions` 事后补记，
  无法在执行期表达。两者都能达到省钱目的，`ad-review-agent` 的方案更容易读，
  但也更容易在重构时被静默丢掉，本仓库的情况正是如此。

- **Momcozy 迁移形态**：发布前一次性把关的语义与提前终止冲突，建议默认
  `early_termination.enabled: false`，只保留 `early_termination_eligible` 这一层元数据。
  若确需启用，条件从「任意 high」收紧为「命中 `medical_device_boundary` 或
  `claim_substantiation` 的 high 违规且 confidence > 0.95」，
  并把 `_should_early_terminate` 的 0.9 改为读 `constraints.yaml`。
  每次提前终止必须在返回体里带上 `skipped_dimensions` 与
  `skip_reason: "early_termination_after:<dimension>"`，
  重提时强制 `full_recheck: true`。

- **证据强度**：已实读核实（声明、实现、未接线、指标未写入均已逐条核对）

---

## S1-05 降级契约

- **出处**：`ad-review-agent/src/tools/base_tool.py:54-67`、
  `ad-review-agent/src/tools/base_tool.py:84-102`、
  `ad-review-agent/src/tools/text_checker.py:246-261`、
  `ad-review-agent/src/tools/consistency_checker.py:624-630`（已实读核实）
- **一句话**：`_fallback()` 是抽象方法，契约在 docstring 里写死「不允许抛出异常，
  必须返回一个有效的 Output」，`run()` 用两个 `except` 分支保证任何异常都落到降级；
  降级结果的 `is_fallback=True` 让它在置信度聚合中被整体排除。

- **原文（契约本身）**：

```54:67:ad-review-agent/src/tools/base_tool.py
    @abstractmethod
    async def _fallback(self, error: Exception, input: Any) -> Any:
        """
        降级处理，在 execute() 失败时调用。
        此方法不允许抛出异常，必须返回一个有效的 Output。

        Args:
            error: 导致降级的异常
            input: 原始输入

        Returns:
            降级的 Output Pydantic Model 实例（is_fallback=True）
        """
        raise NotImplementedError
```

- **原文（兜底执行路径，`Exception` 分支让未预料异常也不外泄）**：

```84:102:ad-review-agent/src/tools/base_tool.py
        except (ToolExecutionError, ToolTimeoutError) as e:
            logger.warning(
                f"Tool {self.name} failed, using fallback",
                tool=self.name,
                error=str(e),
            )
            span.success = False
            span.error = f"{type(e).__name__}: {e}"
            return await self._fallback(e, input)
        except Exception as e:
            logger.error(
                f"Tool {self.name} unexpected error",
                tool=self.name,
                error=str(e),
                exc_info=True,
            )
            span.success = False
            span.error = f"{type(e).__name__}: {e}"
            return await self._fallback(e, input)
```

- **原文（降级时尽量保住确定性结果，兜底本身再套一层 try）**：

```246:261:ad-review-agent/src/tools/text_checker.py
        # 尝试保留规则库匹配结果
        rule_violations: list[ViolationItem] = []
        try:
            if isinstance(input, TextCheckerInput):
                rule_violations = self._rule_based_check(
                    input.text_content, input.ad_category
                )
        except Exception:
            pass  # 规则库也失败了，返回空列表

        return TextCheckerOutput(
            violations=rule_violations,
            confidence=0.5,
            is_fallback=True,
            fallback_reason=f"Tool fallback due to: {type(error).__name__}: {error}",
        )
```

- **原文（第六个 Tool 的降级值与其他五个不一致）**：

```624:630:ad-review-agent/src/tools/consistency_checker.py
        return ConsistencyCheckOutput(
            violations=[],
            confidence=1.0,
            checked_pairs=[],
            is_fallback=True,
            fallback_reason=f"一致性检测失败：{type(error).__name__}: {error}",
        )
```

- **为什么这样做 / 不这样做会出什么事**：审计系统的失败模式是「某个外部依赖挂了」，
  视觉模型超时、落地页 403、数据库不可用都会发生。若降级抛异常，一次超时会把整条
  审核请求打成 500，素材卡在网关，进不了人工队列。契约让降级成为一等公民：
  六个 Tool 的降级值分别是
  `text_checker.py:258` 的 0.5、`image_checker.py:388` 的 0.5、
  `landing_page.py:190` 的 0.5、`qualification.py:184` 的 0.5、
  `platform_rule.py:166` 的 0.5、`consistency_checker.py:626` 的 1.0。
  `decision_engine.py:104` 与 `decision_engine.py:123` 都用
  `getattr(r, "is_fallback", False)` 把降级维度整体排除在聚合之外，
  所以 0.5 这个数字本身不是「进人工」的开关，它只是「这个维度没说话」的占位。
  真正让请求进人工的是 `result_builder` 侧的 `has_fallback` 计数，
  以及聚合结果里剩下的维度。

- **代价与局限**：

  1. **`consistency_checker` 的降级值是 1.0，与其他五个相反。** 因为它被排除，
     当前不影响 verdict。但它同时把 `checked_pairs=[]` 置空，
     而 `orchestrator.py:185` 用 `if rs.consistency.checked_pairs:` 判断该维度是否计入
     `checked_dimensions`，所以降级的一致性维度会被记进 `skipped_dimensions`。
     任何未来绕过 `is_fallback` 直接读 `r.confidence` 的代码会拿到一个最大值 1.0。

  2. **`base_tool.py:93` 的宽 `except Exception` 与 `AGENTS.md:485` 的
     `「不许使用 except Exception: pass 或空 except」` 存在字面冲突。**
     实现上不是空 except（有 `logger.error` 与 `_fallback` 调用），
     `text_checker.py:253-254` 的 `except Exception: pass` 才是字面命中禁令的那一处，
     但那一处的注释说明了理由（规则库也失败时返回空列表），且外层已有 `error` 参数记录原始异常。

  3. **降级不区分「暂时失败」与「永久失败」。** 落地页 403 与视觉模型超时都记
     同一个 `is_fallback=True`，审核员从 `fallback_reason` 才能区分。
     `landing_page.py:121-130` 对不可访问的落地页直接返回降级结构并写
     `fallback_reason=f"落地页无法访问: {input.landing_page_url}，已标注待人工复查"`，
     没有重试。同一 URL 的第二次提交会再走一遍失败路径。

- **横向对比**：`invoice/backend/app/services/ai_service.py` 用显式参数
  `allow_local_fallback: bool = False` 把降级决策交给调用方
  （`ai_service.py:534`、`ai_service.py:605`），并在不允许降级时抛出带操作指引的异常
  （`ai_service.py:615-617`、`ai_service.py:651-654`）。两条路线的分歧点在于
  「降级是不是一个需要业务同意的动作」。发票识别允许「拒绝处理」，
  因为它可以要求用户重新提交；广告审核不允许拒绝处理，因为素材已经在提交管道里，
  必须先给出一个结论。`ad-review-agent` 的自动降级适合本场景，
  但代价是调用方失去了「这次不允许降级」的表达能力。

- **Momcozy 迁移形态**：保留契约结构，做三处收紧。
  一是把降级值统一为常量并从 `harness/constraints.yaml` 读
  `fallback_confidence: 0.0`，不用 0.5，理由是 0.5 落在
  `human_review_forced: 0.70` 之下的巧合容易被误读成「设计好的」。
  二是给 `_fallback` 加第二个强制字段 `degradation_class`，
  取值 `transient`（超时/限流）与 `permanent`（403/文件缺失），
  前者允许在编排层重试一次，后者直接进人工。
  三是把 `is_fallback` 从 Tool 输出提升到 `ReviewResult` 顶层的必需字段，
  并规定 `is_fallback=True` 的结论在发布前把关流程里一律不得输出 PASS，
  即使聚合置信度达标。最后一条与 `decision_engine.py:178-185` 的现有行为相反，
  该处允许「无违规 + 高置信度 + 有降级」判 PASS。

- **证据强度**：已实读核实（六个 Tool 的降级值、聚合排除、checked_pairs 分支均已逐行核对）

---

## S1-06 规则热更新与版本化

- **出处**：`ad-review-agent/src/rules_loader.py:14-16`、
  `ad-review-agent/src/rules_loader.py:30-42`、
  `ad-review-agent/src/rules_loader.py:106-124`（已实读核实）
- **一句话**：规则读取走「数据库优先，5 分钟内命中内存缓存，数据库不可用则读 JSON 文件」，
  文件读失败时返回空字典，不抛异常。

- **原文（缓存结构与检查间隔）**：

```14:16:ad-review-agent/src/rules_loader.py
# 缓存：rule_type → (content_dict, version_str, loaded_at_timestamp)
_cache: dict[str, tuple[dict, str, float]] = {}
_CHECK_INTERVAL = 300  # 每 5 分钟检查数据库版本
```

- **原文（三级读取顺序）**：

```30:42:ad-review-agent/src/rules_loader.py
    # 检查缓存是否需要刷新
    if rule_type in _cache:
        content, version, loaded_at = _cache[rule_type]
        if time.time() - loaded_at < _CHECK_INTERVAL:
            return content

    # 尝试从数据库加载
    db_content = await _load_from_db(rule_type)
    if db_content is not None:
        return db_content

    # 降级读取 JSON 文件
    return _load_from_file(rule_type)
```

- **原文（文件保底，未知类型与解析失败都返回空字典）**：

```106:124:ad-review-agent/src/rules_loader.py
    file_map = {
        "forbidden_words": "forbidden_words.json",
        "qualification_map": "qualification_map.json",
        "category_rules": "category_rules.json",
        "vivo_platform": "vivo_platform.json",
    }
    filename = file_map.get(rule_type)
    if not filename:
        logger.warning("Unknown rule type", rule_type=rule_type)
        return {}

    path = Path(settings.rules_dir) / filename
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        _cache[rule_type] = (content, content.get("version", "file"), time.time())
        return content
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load rules from file", path=str(path), error=str(e))
        return {}
```

- **为什么这样做 / 不这样做会出什么事**：违禁词库是运营资产，改词不该发版。
  数据库优先让运营后台改完 5 分钟内生效；文件保底保证数据库挂掉时审核还能跑，
  而且保底的是同一份 JSON 的磁盘副本，行为可预测。
  版本号参与缓存判断：`text_checker.py:120` 用
  `new_rules.get("version") != self._rules.get("version")` 决定是否替换内存规则，
  版本没变就不动，避免每次请求都重建规则对象。

- **代价与局限（三条）**：

  1. **热更新的触发点是 Tool 的 `execute`，不是定时器。** `text_checker.py:151` 在每次
     执行开头调用 `await self._maybe_reload_rules()`。缓存 300 秒失效，所以
     「改完 5 分钟内生效」实际依赖「这 5 分钟内有请求进来」。低峰期改的规则
     可能几小时不生效。若改成后台定时器，代价是要引入一个常驻任务与锁。

  2. **DB 规则与文件规则没有一致性校验。** `_load_from_db` 成功就直接返回，
     不比对文件版本的 `updated_at`。文件里是新的、DB 里是旧的时，读取结果是旧的，
     且日志里只有一条 `logger.debug`（`rules_loader.py:84`，debug 级别默认不输出）。

  3. **`load_rules_sync` 只读文件，与异步版本语义不同。** `rules_loader.py:45-59` 的同步版本
     供 Tool 的 `__init__` 使用，它跳过数据库。这意味着服务启动瞬间用的是文件规则，
     之后靠 `_maybe_reload_rules` 切到数据库版本。第一次请求因此可能用旧规则判定，
     且 `text_checker.py:120` 的版本比较会发现版本不同并打印 `"Rules reloaded"`。

- **Momcozy 迁移形态**：保留三级读取，改动三处。
  一是规则文件按法域分目录：`rules/us/{claim_rules,forbidden_claims,ingredient_claims}.json`
  与 `rules/us/{ftc_guides,fda_claims}.json`，
  `rule_type` 改为 `f"{jurisdiction}:{rule_type}"`，避免中美规则在同一命名空间里冲突。
  二是给规则对象加 `effective_from` 与 `supersedes` 两个字段，
  因为 FTC 的指南与 FDA 的宣称分类会更新，审计结论必须能回答「当时用的是哪版」。
  三是把 `_CHECK_INTERVAL` 从 300 秒改成由 `constraints.yaml` 的
  `rules_cache_ttl_seconds` 驱动，并在审核结果里回写
  `rules_version_used: {forbidden_claims: "2026-09-15.1", ...}`，
  让每份审计报告自带规则快照。

- **证据强度**：已实读核实

---

## S1-07 违禁词库的数据结构

- **出处**：`ad-review-agent/src/rules/forbidden_words.json:1-57`、
  `ad-review-agent/src/tools/text_checker.py:286-316`（已实读核实）
- **一句话**：词库是「规则名 → {description, severity, regulation_ref, words[] 或 patterns[]}」的一层映射，
  同一条规则的 `words` 与 `patterns` 共用同一个 severity 和同一条法规引用。

- **原文（文件头与两条规则）**：

```6:28:ad-review-agent/src/rules/forbidden_words.json
  "rules": {
    "absolute_terms": {
      "description": "绝对化用语（广告法第九条）",
      "severity": "high",
      "regulation_ref": "《广告法》第九条第三款",
      "words": [
        "最好", "最佳", "最优", "最大", "最强", "最高", "最低", "最安全",
        "第一", "唯一", "顶级", "极致", "终极", "无与伦比",
        "国家级", "国际领先", "全球第一", "行业第一",
        "保证", "承诺效果"
      ]
    },
    "false_claims": {
      "description": "虚假宣传表述",
      "severity": "high",
      "regulation_ref": "《广告法》第二十八条",
      "patterns": [
        "下载量超.*亿",
        "好评率.*99",
        "用户数.*亿",
        "市值.*亿"
      ]
    },
```

- **原文（消费端：先按品类过滤规则，再逐词、逐正则匹配）**：

```286:318:ad-review-agent/src/tools/text_checker.py
            severity = ViolationSeverity(rule_config["severity"])
            regulation_ref = rule_config["regulation_ref"]
            description_prefix = rule_config["description"]

            # 关键词匹配
            for word in rule_config.get("words", []):
                if word in text_content:
                    violations.append(
                        ViolationItem(
                            dimension=ViolationDimension.TEXT_VIOLATION,
                            description=f"{description_prefix}：包含违禁词「{word}」",
                            regulation_ref=regulation_ref,
                            severity=severity,
                            evidence=word,
                        )
                    )

            # 正则模式匹配
            for pattern in rule_config.get("patterns", []):
                match = re.search(pattern, text_content)
                if match:
                    matched_text = match.group(0)
                    violations.append(
                        ViolationItem(
                            dimension=ViolationDimension.TEXT_VIOLATION,
                            description=f"{description_prefix}：匹配到违规模式「{pattern}」",
                            regulation_ref=regulation_ref,
                            severity=severity,
                            evidence=matched_text,
                        )
                    )

        return violations
```

- **实际规模（`splitlines()` 口径统计）**：`forbidden_words.json` 共 57 行，5 条规则。
  `absolute_terms` severity=high words=20 patterns=0；
  `false_claims` severity=high words=0 patterns=4；
  `inducement` severity=medium words=6 patterns=0；
  `game_specific` severity=high words=6 patterns=0；
  `finance_specific` severity=high words=7 patterns=0。
  合计 39 个关键词与 4 条正则。

- **为什么这样做 / 不这样做会出什么事**：`severity` 与 `regulation_ref` 挂在规则组上而不挂在
  单个词上，39 个词只需要维护 5 条法规引用。这让 `text_checker.py:181-183` 的置信度分档成立：
  规则库命中一律
  `confidence = max(0.92, llm_confidence)`（`text_checker.py:183`），
  理由是关键词匹配是确定性的，不需要 LLM 的把握度背书。
  若把 severity 下沉到每个词上，维护量涨到 39 处，且「同一个词在不同品类下严重度不同」
  这件事会变得难以表达（目前的表达方式是按品类拆规则组：
  `text_checker.py:281-284` 让 `game_specific` 只在 game 品类生效，
  `finance_specific` 只在 finance 品类生效）。

- **法域说明（迁美关键项）**：五条规则的 `regulation_ref` 全部是中国法域，
  逐条给出迁美处置：

  | 规则组 | 原文引用 | 迁美处置 |
  |---|---|---|
  | `absolute_terms` | `《广告法》第九条第三款` | 不能整条搬。美国没有「绝对化用语」这一独立违法类型，FTC 的对应抓手是「未获证实的优越性宣称」（unsubstantiated superiority claim）。39 个词里「最好/第一/唯一」在美国可合法使用，条件是广告主有实证支撑；`保证`、`承诺效果` 两个词则在母婴品类依然高危，因为它们指向效果担保。 |
  | `false_claims` | `《广告法》第二十八条` | 可迁移，落到 FTC Act Section 5 的 deceptive claims 标准，判定要件换成「是否具有实质性且可能误导合理消费者」。四条正则 `下载量超.*亿`、`好评率.*99`、`用户数.*亿`、`市值.*亿` 的形态可直接复用。 |
  | `inducement` | `《互联网广告管理办法》第九条` | 可迁移，美国对应 FTC 对 deceptive interface 与 negative option 的执法。六个词里 `系统检测到`、`您的手机存在风险` 属于「手机病毒恐吓」类型，与 Momcozy 的吸乳器品类无关，可整体删除。 |
  | `game_specific` | `《网络游戏管理暂行办法》` | 不迁移。这是中国游戏版号制度的配套规范，美国无对应制度。 |
  | `finance_specific` | `《广告法》第二十五条` | 部分迁移。`保本`、`保息`、`无风险`、`稳赚`、`零风险` 五个词在 FTC 下同样高危（收益保证类），但引用要换成 FTC 的 investment claims 指引；`年化收益.*%` 属 SEC/FINRA 管辖范围，Momcozy 不涉及。 |

  Momcozy 真正需要补的是这条规则组在原文中不存在：母乳/婴儿相关的健康功效宣称
  （如「增加奶量」「缓解胀痛」「改善婴儿肠绞痛」）在美国若指向疾病治疗或预防，
  会被 FDA 归入医疗器械或药品宣称，需要 510(k) 或 NDA，与「膳食补充剂」路径不同。
  这一条应新建 `health_efficacy_claims` 规则组，`regulation_ref` 写
  `FDA FD&C Act medical device claim boundary`，severity 定为 high。

- **Momcozy 迁移形态**：字段名沿用 `severity` / `regulation_ref` / `words` / `patterns`，
  新增两个字段：`jurisdiction`（`"US"`）与 `evidence_required`（布尔，
  表示命中后必须检查落地页/包装是否有实证支撑，而不只是删词）。
  规则组拆成六个：`unsubstantiated_superiority`（对应 FTC 的优越性宣称）、
  `deceptive_claims`、`health_efficacy_claims`（FDA 边界）、
  `ingredient_safety_claims`、`testimonial_claims`、`pricing_deception`。
  词库规模建议起步 120 至 180 个词，其中 `health_efficacy_claims` 一组的
  权重最高，因为它对应的是「产品被重新归类为医疗器械」这种不可逆后果。

- **证据强度**：已实读核实（结构、消费逻辑、规则条数与词数均已实际统计）

---

## S1-08 跨维度一致性规则的三段式写法

- **出处**：`ad-review-agent/src/rules/consistency_rules.json:7-48`、
  `ad-review-agent/src/tools/consistency_checker.py:263-284`、
  `ad-review-agent/src/tools/consistency_checker.py:306-311`（已实读核实）
- **一句话**：每个一致性维度用 `examples_violation`（该判违规的例子）、
  `examples_normal`（该判正常的例子）、`non_violation_patterns`（整组通用的免判清单）
  三段拼进 prompt，并把「违规 / 边界 / 放行」三个置信区间显式写成两个阈值。

- **原文（规则侧，第一组完整结构）**：

```7:48:ad-review-agent/src/rules/consistency_rules.json
  "creative_consistency": {
    "description": "文案 vs 图片/视频 一致性",
    "enabled": true,
    "confidence_threshold_reject": 0.85,
    "confidence_threshold_review": 0.70,
    "check_dimensions": [
      {
        "name": "brand_identity",
        "description": "品牌身份冲突检测",
        "enabled": true,
        "severity": "high",
        "examples_violation": [
          "图片出现百度Logo，文案声称是手机管家",
          "图片使用微信界面截图，文案推广另一款App"
        ],
        "examples_normal": [
          "图片是使用场景，文案是功能介绍",
          "图片是氛围图，文案是品牌宣传"
        ]
      },
      {
        "name": "product_category",
        "description": "产品类别明显错位检测",
        "enabled": true,
        "severity": "high",
        "examples_violation": [
          "图片展示食品，文案宣传手机App",
          "图片是整形对比图，文案是护肤品广告"
        ],
        "examples_normal": [
          "图片是游戏战斗画面，文案是策略手游介绍",
          "图片是App界面，文案是产品功能说明"
        ]
      }
    ],
    "non_violation_patterns": [
      "图片是使用场景/氛围图，文案是功能/品牌介绍",
      "图片是产品外观，文案是产品功能",
      "图片和文案风格匹配但不完全对应",
      "图片信息量少于文案（正常摘要关系）"
    ]
  },
```

- **原文（拼 prompt：三段合流，正常情形段是 `examples_normal` 与 `non_violation_patterns` 的拼接）**：

```263:284:ad-review-agent/src/tools/consistency_checker.py
        threshold_reject = rules.get("confidence_threshold_reject", 0.85)
        threshold_review = rules.get("confidence_threshold_review", 0.70)

        dimensions = rules.get("check_dimensions", [])
        enabled_dims = [d for d in dimensions if d.get("enabled")]

        violation_examples: list[str] = []
        normal_examples: list[str] = []
        for dim in enabled_dims:
            violation_examples.extend(dim.get("examples_violation", []))
            normal_examples.extend(dim.get("examples_normal", []))

        non_violation_patterns = rules.get("non_violation_patterns", [])

        prompt = (
            "你是广告合规审核专家，判断以下两部分广告内容是否存在明显不一致。\n\n"
            f"【内容A】\n{content_a}\n\n"
            f"【内容B】\n{content_b}\n\n"
            "【需要检测的违规情形】（以下情形应判为不一致）：\n"
            + "\n".join(f"- {e}" for e in violation_examples)
            + "\n\n【正常情形，不应判为违规】：\n"
            + "\n".join(f"- {e}" for e in normal_examples + non_violation_patterns)
```

- **原文（两个阈值把 LLM 的连续置信度切成三档，最低档直接丢弃）**：

```306:311:ad-review-agent/src/tools/consistency_checker.py
                if result.confidence >= threshold_reject:
                    severity = ViolationSeverity.HIGH
                elif result.confidence >= threshold_review:
                    severity = ViolationSeverity.MEDIUM
                else:
                    return {"violations": [], "confidence": result.confidence}
```

- **实际规模（`splitlines()` 口径统计）**：`consistency_rules.json` 共 113 行，3 组规则。
  `creative_consistency` 阈值 0.85 / 0.70，2 个维度，4 条 `non_violation_patterns`；
  `landing_consistency` 阈值 0.80 / 0.65，3 个维度，6 条 `allowed_patterns`；
  `image_landing_consistency` 阈值 0.85 / 0.72，1 个维度，无免判清单。

- **为什么这样做 / 不这样做会出什么事**：一致性检测是典型的「LLM 最容易过度报警」的维度。
  文案说「和朋友一起冒险」，图片是氛围图，模型很容易判成不一致。
  三段式的分工是：`examples_violation` 告诉模型什么算问题，
  `examples_normal` 告诉它同一维度内的对照，
  `non_violation_patterns` 处理跨维度的结构性豁免（「图片信息量少于文案」是正常摘要关系）。
  第三段单独提出来而不塞进每个维度里，是因为它是整组的共性，
  写在组级只需维护一份。两个阈值则把「模型说有点不一致」和「模型说确实不一致」分开，
  后者才产生违规项。

- **代价与局限（三条）**：

  1. **第三组的免判清单是空的。** `image_landing_consistency` 组（`consistency_rules.json:98-112`）
     只有 `examples_violation` 的维度定义，没有 `non_violation_patterns`，
     也没有 `allowed_patterns`。`consistency_checker.py:485` 读的是
     `rules.get("non_violation_patterns", [])`，取到空列表，
     拼出的「正常情形」段为空。这是三组里最容易误报的一组。

  2. **第三组多了一个代码里没读的键。** `consistency_rules.json:103` 写
     `"only_check_when": "图片包含明显品牌标识时才触发"`，
     但 `consistency_checker.py` 中 `only_check_when` 零命中。
     实际的触发条件在编排层：`orchestrator.py:355-357` 把
     `has_brand_in_image` 传给输入，由 `ConsistencyCheckInput`
     承接。规则文件里的这句话是给人读的说明，不驱动行为。

  3. **阈值分散在规则文件与代码默认值两处。** `consistency_checker.py:263-264`、
     `:361-362`、`:475-476` 三处各写一遍
     `rules.get("confidence_threshold_reject", 0.85)` 形式的默认值，
     其中 `:361` 的默认值是 0.80、`:362` 是 0.65，与其余两处的 0.85 / 0.70 不同。
     规则文件删掉阈值键时，三组会退回两套不同的默认值。

- **Momcozy 迁移形态**：三段式直接沿用，规则组改为两组：
  `claim_vs_evidence`（宣称与证据一致性，对应 Momcozy 的吸乳器功效表述与说明书/检测报告）
  与 `creative_vs_listing`（素材与商品详情页一致性，对应 Amazon 主图与五点描述）。
  `non_violation_patterns` 必须写满，母婴品类的合理差异比游戏类多：
  「场景图为哺乳室实拍而文案为产品功能」「模特着装与产品无直接关系」
  「A+ 页面风格与主图不同」都应列入免判清单。
  阈值改为读 `harness/constraints.yaml`，不写代码默认值。
  新增 `jurisdiction_note` 字段，因为美国的一致性判定要额外考虑
  「素材宣称与包装标签宣称是否一致」，这在中国版本里没有对应项。

- **证据强度**：已实读核实（三段结构、拼接逻辑、三档分档、`only_check_when` 未消费
  与三处默认值不一致均已逐行核对）

---

## S1-09 Golden Dataset 四桶 + case schema + 回归门禁

- **出处**：`ad-review-agent/evals/run_eval.py:39-44`、
  `ad-review-agent/evals/run_eval.py:109-130`、
  `ad-review-agent/evals/metrics.py:95-111`、
  `ad-review-agent/evals/regression_check.py:29-37`、
  `ad-review-agent/.github/workflows/ahf_check.yml:66-81`（已实读核实）
- **一句话**：四个 JSONL 分桶（pass 30 / reject 35 / review 25 / adversarial 15，合计 105 条），
  回归门禁比较四个指标并把阈值写成 1% 与 2%，但 CI 里的回归 job 是注释状态。

- **原文（四桶清单）**：

```39:44:ad-review-agent/evals/run_eval.py
DATASET_FILES = [
    "pass_cases.jsonl",
    "reject_cases.jsonl",
    "review_cases.jsonl",
    "adversarial_cases.jsonl",
]
```

- **原文（case schema 到 ReviewRequest 的映射）**：

```109:130:ad-review-agent/evals/run_eval.py
    content_data = case.get("content", {})
    category_str = case.get("category", "other")
    ad_category = _CATEGORY_MAP.get(category_str, AdCategory.OTHER)

    qualifications = _DEFAULT_QUALIFICATIONS.get(category_str, [])

    return ReviewRequest(
        request_id=case.get("case_id", str(uuid4())),
        advertiser_id="eval-advertiser",
        ad_category=ad_category,
        creative_type=CreativeType.TEXT,
        content=CreativeContent(
            title=content_data.get("title"),
            description=content_data.get("description"),
            cta_text=content_data.get("cta_text"),
            image_urls=content_data.get("image_urls", []),
            video_url=content_data.get("video_url"),
            landing_page_url=content_data.get("landing_page_url"),
        ),
        advertiser_qualification_ids=qualifications,
        platform=AdPlatform.OTHER,
    )
```

  单条 case 的实际字段（`evals/golden_dataset/pass_cases.jsonl:1`）：

```1:1:ad-review-agent/evals/golden_dataset/pass_cases.jsonl
{"case_id": "pass-001", "created_at": "2026-03-21T00:00:00Z", "category": "game", "creative_type": "text", "content": {"title": "精美画面丰富剧情", "description": "和朋友一起冒险，探索全新奇幻世界", "cta_text": "立即下载"}, "expected_verdict": "pass", "expected_violations": [], "notes": "游戏类合规文案，无绝对化用语", "source": "manual_annotation"}
```

- **原文（漏审优先于误拒的指标口径）**：

```95:111:ad-review-agent/evals/metrics.py
        # 漏审（expected=reject, actual=pass）
        # 注意：returned 视为 reject 的等价结论（系统自动输出 returned 代替 reject）
        if r.expected_verdict in ("reject", "returned"):
            m.false_negative_total += 1
            if r.actual_verdict == "pass":
                m.false_negative_count += 1
                m.missed_cases.append(r.case_id)

        # 误拒（expected=pass, actual=reject/returned）
        if r.expected_verdict == "pass":
            m.false_positive_total += 1
            if r.actual_verdict in ("reject", "returned"):
                m.false_positive_count += 1

        # 自动化率
        if r.confidence >= 0.92:
            m.auto_decision_count += 1
```

- **原文（门禁阈值表）**：

```29:37:ad-review-agent/evals/regression_check.py
# 关键指标及其回归阈值（绝对值下降超过此值即为回归）
# higher_is_better=True 的指标：下降为回归
# higher_is_better=False 的指标：上升为回归
_CHECKS = [
    {"key": "accuracy", "label": "Accuracy", "threshold": 0.01, "higher_is_better": True},
    {"key": "false_negative_rate", "label": "False Negative Rate", "threshold": 0.01, "higher_is_better": False},
    {"key": "false_positive_rate", "label": "False Positive Rate", "threshold": 0.01, "higher_is_better": False},
    {"key": "automation_rate", "label": "Automation Rate", "threshold": 0.02, "higher_is_better": True},
]
```

- **原文（门禁没接进 CI）**：

```66:81:ad-review-agent/.github/workflows/ahf_check.yml
  # eval-regression:
  #   name: Eval Regression Check
  #   runs-on: ubuntu-latest
  #   needs: test
  #   # Disabled: requires API keys not available in CI
  #   if: false
  #   steps:
  #     - uses: actions/checkout@v4
  #     - uses: actions/setup-python@v5
  #       with:
  #         python-version: "3.11"
  #     - run: pip install uv && uv sync
  #     - run: uv run python evals/regression_check.py --run-eval
  #       env:
  #         DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
  #         DASHSCOPE_API_KEY: ${{ secrets.DASHSCOPE_API_KEY }}
```

  文件内启用中的两个 job 是 `validate-harness`（YAML 语法与 `cleanup_check.py`）
  与 `test`（pytest，且
  `--ignore=tests/agents/test_review_agent.py --ignore=tests/tools/test_image_checker.py`，
  见 `ahf_check.yml:61`）。`progress.txt:20` 记
  `「eval-regression job 已注释（CI 缺 API Key）」`，与文件一致。

- **为什么这样做 / 不这样做会出什么事**：105 条人工标注样本构成唯一的客观基线。
  四桶的分工是：pass 与 reject 测判定方向，review 测边界（`review_cases.jsonl:1`
  的注释写 `"notes": "边界案例：效果显著属于模糊疗效暗示，需人工判断是否构成违规"`），
  adversarial 测规避手法。门禁只看四个数，不看具体案例，
  好处是阈值可解释、CI 里一行命令可跑。漏审阈值给 1% 而误拒同样给 1%，
  但 `metrics.py:97` 的注释与 `AGENTS.md:18` 的
  `「漏审率（False Negative）≤ 5%」` 表明业务侧对漏审更敏感，
  这里门禁比业务门槛更严。

- **代价与局限（四条）**：

  1. **`creative_type` 被硬编码。** `run_eval.py:119` 写死
     `creative_type=CreativeType.TEXT`，case 里的 `"creative_type": "text"`
     字段被完全忽略。数据集里所有 105 条都是 text 类型，所以目前不暴露问题；
     要加图片或视频样本时，这一行必须先改。

  2. **自动化率的分母是所有 case，不是可自动判定的 case。**
     `metrics.py:110-111` 对 `confidence >= 0.92` 计数，分母在
     `metrics.py:136-138` 用 `m.total_cases`，其中包含 review 桶的 25 条边界样本。
     边界样本的目标结论就是进人工，它们计入自动化率分母会系统性压低该指标。

  3. **`review_cases.jsonl` 的样本在指标里没有专门口径。**
     `run_eval.py:244` 把 `category=expected`，所以分类别准确率按
     pass / reject / review 三档统计，`progress.txt:46` 记录的
     `「review 类边界案例准确率 44%」` 就是这个口径。44% 被归因为
     `「LLM 非确定性波动，非回归」`，但 `_CHECKS` 里没有针对 review 档的独立阈值，
     44% 这个数不会触发任何门禁。

  4. **门禁的比较对象是「最近两个结果文件」。**
     `regression_check.py:69` 用 `sorted(RESULTS_DIR.glob("eval_*.json"))` 取文件名排序的最后两个，
     文件名格式是 `eval_%Y%m%d_%H%M%S`（`run_eval.py:167`），字典序与时间序一致，
     这一点没问题。风险在于没有固定的 baseline 文件：
     连续跑两次同一版本，第二次与第一次比，指标相同，门禁通过。
     只有显式传 `--baseline` 才能锁基线。

- **横向对比**：`ad-compliance-agent` 用 100 条测评集与 `scripts/run_eval_100.py`，
  走的是「单次批量评测 + 人工读报告」的路，没有门禁脚本，
  也就没有「哪两个文件比」的问题。`ad-review-agent` 多了一层门禁，
  代价是引入了 baseline 选择这件需要约定的事，而 CI 里这一层又是关闭的。
  两条路都成立：门禁的价值在自动化流水线里兑现，没有流水线时脚本与手工评测等价。

- **Momcozy 迁移形态**：四桶保留并按美国市场重写标注。
  `pass_cases` 需要包含「有绝对化用语但有实证支撑」的样本，
  这是美国与中国判定差异最大的地方，中国版本会判 reject，美国版本应判 pass。
  `adversarial_cases` 扩到 30 条以上，重点覆盖 FDA 边界话术
  （「帮助」与「治疗」的差别、「支持免疫系统」与「预防感染」的差别）。
  门禁改为固定 baseline 文件 `evals/baseline.json`，
  并在 CI 里必跑（用 mock LLM 或录制的响应回放，绕开 API Key 依赖，
  这是让 `ahf_check.yml` 里那个 `if: false` 消失的实际办法）。
  新增一个门禁项 `false_pass_on_medical_claim`，任何该维度的漏判直接把门禁判红，
  不给 1% 的宽容度。

- **证据强度**：已实读核实（四桶条数已用 `splitlines()` 统计，索引与阈值表逐行核对，CI 状态与 progress.txt 交叉验证一致）

---

## S1-10 对抗集覆盖的规避手法

- **出处**：`ad-review-agent/evals/golden_dataset/adversarial_cases.jsonl:1-4`、
  `ad-review-agent/evals/golden_dataset/adversarial_cases.jsonl:9-15`（已实读核实）
- **一句话**：15 条对抗样本覆盖六类规避手法：拼音替换、标点拆字、空格拆字、
  特殊数字符号替换、emoji 插入、成语同义替换。

- **原文（拼音替换与标点拆字）**：

```1:4:ad-review-agent/evals/golden_dataset/adversarial_cases.jsonl
{"case_id": "adversarial-001", "created_at": "2026-03-21T00:00:00Z", "category": "game", "creative_type": "text", "content": {"title": "全网zui好玩的手游", "description": "业界di yi品质，独yi无二的游戏体验", "cta_text": "立即下载"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第九条", "severity": "high"}], "notes": "对抗性案例：用拼音替换绝对化用语规避检测（zui→最，di yi→第一，yi→一）", "source": "manual_annotation"}
{"case_id": "adversarial-002", "created_at": "2026-03-21T00:00:00Z", "category": "finance", "creative_type": "text", "content": {"title": "稳健理财好帮手", "description": "保.本保.息，年化收⬆️益12%，0⃣风险投资", "cta_text": "立即投资"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第二十五条", "severity": "high"}], "notes": "对抗性案例：用标点拆字和emoji替换规避违禁词（保.本、收⬆️益、0⃣风险）", "source": "manual_annotation"}
{"case_id": "adversarial-003", "created_at": "2026-03-21T00:00:00Z", "category": "tool_app", "creative_type": "text", "content": {"title": "系统安全提醒", "description": "jian测到您的shou机存在高wei风xian！建议立即处理", "cta_text": "立即处理"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第二十八条", "severity": "high"}], "notes": "对抗性案例：拆字规避检测（jian测→检测，shou机→手机，wei风xian→危风险）", "source": "manual_annotation"}
{"case_id": "adversarial-004", "created_at": "2026-03-21T00:00:00Z", "category": "game", "creative_type": "text", "content": {"title": "边wan边zhuan", "description": "每天wan游戏就能zhuan到ling花qian，ti现秒到", "cta_text": "领取红bao"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第二十八条", "severity": "high"}], "notes": "对抗性案例：拼音替换核心违禁词（wan→玩，zhuan→赚，ling花qian→零花钱，ti→提，红bao→红包）", "source": "manual_annotation"}
```

- **原文（空格拆字、成语同义替换、emoji 插入）**：

```9:15:ad-review-agent/evals/golden_dataset/adversarial_cases.jsonl
{"case_id": "adversarial-009", "created_at": "2026-03-22", "category": "finance", "creative_type": "text", "content": {"title": "保 本 保 息", "description": "零 风 险，年 化 收 益 8%", "cta_text": "立即投资"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第二十五条", "severity": "high"}], "notes": "对抗性：空格拆字规避关键词匹配（保 本 保 息、零 风 险）", "source": "manual_annotation"}
{"case_id": "adversarial-010", "created_at": "2026-03-22", "category": "tool_app", "creative_type": "text", "content": {"title": "最 好 的 产 品", "description": "全 网 第 一，独 一 无 二", "cta_text": "立即体验"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第九条", "severity": "high"}], "notes": "对抗性：每字间插入空格规避整词匹配", "source": "manual_annotation"}
{"case_id": "adversarial-011", "created_at": "2026-03-22", "category": "health", "creative_type": "text", "content": {"title": "根 治 百 病", "description": "7天 见 效，一 个 疗 程 彻 底 治 愈", "cta_text": "立即购买"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第十七条", "severity": "high"}], "notes": "对抗性：空格拆字规避疗效类违禁词", "source": "manual_annotation"}
{"case_id": "adversarial-012", "created_at": "2026-03-22", "category": "ecommerce", "creative_type": "text", "content": {"title": "业内翘楚", "description": "品质冠绝同行，无出其右的性价比", "cta_text": "立即购买"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第九条", "severity": "high"}], "notes": "对抗性：同义替换绝对化用语（翘楚→第一，冠绝→最好，无出其右→唯一）", "source": "manual_annotation"}
{"case_id": "adversarial-013", "created_at": "2026-03-22", "category": "tool_app", "creative_type": "text", "content": {"title": "登峰造极的体验", "description": "出类拔萃，鹤立鸡群，碾压所有同类产品", "cta_text": "免费下载"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第九条", "severity": "high"}], "notes": "对抗性：用成语同义替换绝对化用语（登峰造极、出类拔萃→最好）", "source": "manual_annotation"}
{"case_id": "adversarial-014", "created_at": "2026-03-22", "category": "game", "creative_type": "text", "content": {"title": "最🔥好玩的游戏", "description": "第1⃣名品质，唯✨一免费大作", "cta_text": "立即下载"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第九条", "severity": "high"}], "notes": "对抗性：emoji插入违禁词中间规避检测（最🔥好、1⃣名、唯✨一）", "source": "manual_annotation"}
{"case_id": "adversarial-015", "created_at": "2026-03-22", "category": "tool_app", "creative_type": "text", "content": {"title": "⚠️系统警告⚠️", "description": "检测到📱手机存在🔴高危病毒❗立即安装🛡️防护", "cta_text": "🚨立即处理"}, "expected_verdict": "reject", "expected_violations": [{"dimension": "text_violation", "regulation_ref": "《广告法》第二十八条", "severity": "high"}], "notes": "对抗性：大量emoji装饰伪造系统告警增强紧迫感", "source": "manual_annotation"}
```

- **规模统计**：`adversarial_cases.jsonl` 共 15 行，每行一条，全部
  `expected_verdict: "reject"`，全部 `severity: "high"`，
  全部 `source: "manual_annotation"`。`created_at` 分两批：
  前 5 条为 2026-03-21，后 10 条为 2026-03-22。

- **为什么这样做 / 不这样做会出什么事**：规则库是字面匹配
  （`text_checker.py:292` 的 `if word in text_content`），
  「保 本 保 息」与「保本保息」在字符串层面完全不同，关键词库一条都命中不了。
  这 15 条样本的作用是证明「纯规则层不可靠」这件事，并给 LLM 语义层提供验收目标。
  `adversarial-012` 与 `adversarial-013` 尤其重要，它们不含任何违禁词，
  只有成语与同义替换，规则层的命中数为 0，
  结论完全依赖 `_llm_semantic_check`（`text_checker.py:320-368`）。

- **代价与局限（两条）**：

  1. **对抗集没有对应的归一化预处理。** 代码里没有「去空格」「拼音回转」
     「emoji 剥离」这类步骤。`grep -rn "normaliz\|normalize\|strip_emoji\|pinyin" src/tools/`
     在文本检测路径上无命中。这 15 条能否通过，实际是 LLM 语义层的运气。
     要稳定通过，需要在 `_rule_based_check` 之前插入一层归一化，
     或者在 `forbidden_words.json` 里为拆字形态手写正则。

  2. **对抗样本的 `expected_violations` 只给维度不给具体违规项。**
     15 条的 `expected_violations` 都是
     `[{"dimension": "text_violation", "regulation_ref": "...", "severity": "high"}]`，
     没有 `evidence` 字段指向具体命中的文字。
     `metrics.py` 的指标只比较 verdict，`violation_count` 仅记录不参与判定
     （`run_eval.py:250`），所以「判对了结论但理由不对」这种情况不会被门禁发现。

- **法域说明**：15 条里有 6 条依赖中国法域，
  其中 `adversarial-011`（`《广告法》第十七条`，疗效宣称）与
  `adversarial-002`（`《广告法》第二十五条`，金融收益）迁美后法条作废但手法仍成立：
  拼音/空格/emoji 拆字是针对中文输入的规避手法，
  美国市场的对应手法是英文的字符替换
  （`b3st`、`b.e.s.t`、`B E S T`）、Unicode 同形字
  （西里尔字母 `В` 冒充拉丁 `B`）与 emoji 插入。
  `adversarial-015` 的「伪造系统告警」迁美后仍属 FTC 的 deceptive claims 范畴，
  且与 Momcozy 品类无关，可删除。

- **Momcozy 迁移形态**：保留拆字与同义替换两类，
  把中文对抗手法换成英文对抗手法：`b3st`、`#1`、`No.1`、
  `clinically proven`（无出处）、`doctor recommended`（无具体医生）、
  `FDA approved`（若实际只是 FDA registered facility，这是美国市场最严重的错误宣称之一）。
  每条样本补 `expected_evidence` 字段，写明应该命中哪几个字，
  让门禁能区分「结论对但理由错」。目标规模 30 条，
  每季度从真实被拒素材里回收新手法补充。

- **证据强度**：已实读核实（15 条逐条读过，条数与字段分布已实际统计）

---

## S1-11 工具触发条件与 skip_reason 设计

- **出处**：`ad-review-agent/harness/constraints.yaml:93-119`、
  `ad-review-agent/harness/constraints.yaml:139-146`、
  `ad-review-agent/src/agents/orchestrator.py:98-112`、
  `ad-review-agent/src/agents/orchestrator.py:177-196`（已实读核实）
- **一句话**：六个 Tool 各配一个 `trigger_condition` 与 `skip_reason_when_inactive`，
  取值与代码里硬编码的 if/else 分支和跳过原因文本完全一致，
  但代码不读这份声明，声明只是文档。

- **原文（前三个 Tool 的声明）**：

```93:119:ad-review-agent/harness/constraints.yaml
tool_execution:
  - order: 1
    tool_name: "TextViolationChecker"
    # 源码 Step 1 (L136-L152): 文案检测（必跑）
    dimension: "text_violation"
    trigger_condition: "always"
    trigger_detail: "有文案内容时执行（title/description/cta_text 至少一个非空）；无文案则 skip"
    skip_reason_when_inactive: "无文案内容"
    early_termination_eligible: true

  - order: 2
    tool_name: "ImageContentChecker"
    # 源码 Step 2 (L154-L173): 图片/视频检测（有素材时）
    dimension: "image_safety"
    trigger_condition: "has_visual_content"
    trigger_detail: "request.content.image_urls 非空 或 request.content.video_url 非空"
    skip_reason_when_inactive: "无图片/视频素材"
    early_termination_eligible: true

  - order: 3
    tool_name: "LandingPageChecker"
    # 源码 Step 3 (L175-L191): 落地页检测（有 URL 时）
    dimension: "landing_page"
    trigger_condition: "has_landing_page_url"
    trigger_detail: "request.content.landing_page_url 非空"
    skip_reason_when_inactive: "无落地页URL"
    early_termination_eligible: true
```

- **原文（最后一个 Tool，触发条件依赖前序结果，不读请求字段）**：

```139:146:ad-review-agent/harness/constraints.yaml
  - order: 6
    tool_name: "ConsistencyChecker"
    # 源码 Step 6 (L225-L246): 跨维度一致性检测
    dimension: "consistency"
    trigger_condition: "has_multiple_content_types"
    trigger_detail: "至少有两种素材类型（文案+图片、文案+落地页等），checked_pairs 非空时才计入"
    skip_reason_when_inactive: "单一素材类型，无需比对"
    early_termination_eligible: false
```

- **原文（代码侧，Step 1 的 if/else 与 skip 原因）**：

```98:112:ad-review-agent/src/agents/orchestrator.py
        # ── Step 1: 文案检测（必跑） ──
        text_content = self._build_text_content(request)
        if text_content:
            rs.text = await self._run_text_check(
                text_content, request.ad_category.value, request.request_id
            )
            rs.checked_dimensions.append(ViolationDimension.TEXT_VIOLATION)
            rs.all_violations.extend(rs.text.violations)

            if rs.text.is_fallback:
                rs.has_fallback = True
                rs.fallback_reasons.append(rs.text.fallback_reason or "text_checker_fallback")
        else:
            rs.skipped_dimensions.append(ViolationDimension.TEXT_VIOLATION)
            rs.skip_reasons["text_violation"] = "无文案内容"
```

- **原文（代码侧，Step 6 用前序输出判定是否计入，不新增请求字段依赖）**：

```177:196:ad-review-agent/src/agents/orchestrator.py
        # ── Step 6: 跨维度素材一致性检测 ──
        rs.consistency = await self._run_consistency_check(
            request=request,
            image_result=rs.image,
            landing_result=rs.landing_page,
            video_summary="",
            request_id=request.request_id,
        )
        if rs.consistency.checked_pairs:
            rs.checked_dimensions.append(ViolationDimension.CONSISTENCY)
            rs.all_violations.extend(rs.consistency.violations)

            if rs.consistency.is_fallback:
                rs.has_fallback = True
                rs.fallback_reasons.append(
                    rs.consistency.fallback_reason or "consistency_fallback"
                )
        else:
            rs.skipped_dimensions.append(ViolationDimension.CONSISTENCY)
            rs.skip_reasons["consistency"] = "单一素材类型，无需比对"
```

- **值对照（逐条核对一致）**：`constraints.yaml:100` 的 `"无文案内容"` 与
  `orchestrator.py:112` 一致；`:109` 的 `"无图片/视频素材"` 与 `:131` 一致；
  `:118` 的 `"无落地页URL"` 与 `:147` 一致；`:127` 的 `"该品类无特殊资质要求"` 与 `:164` 一致；
  `:136` 的 `null` 对应 `:167-175` 的无条件执行；`:145` 的 `"单一素材类型，无需比对"`
  与 `:196` 一致。六个 Tool 的 `trigger_condition` 值
  （`always` / `has_visual_content` / `has_landing_page_url` /
  `category_in_qualification_required` / `always` / `has_multiple_content_types`）
  在 Python 侧零命中。

- **为什么这样做 / 不这样做会出什么事**：`skip_reasons` 是审核结论的一部分。
  一条素材判 PASS，如果 `skipped_dimensions` 里有 `landing_page`，
  审核员和广告主都需要知道「落地页没看」。`results.py:37-40` 把
  `skip_reasons` 定义为 `dict[str, str]` 并进入 API 返回体，
  这让「通过」这个结论附带它的适用范围。若不做这层记录，
  「因缺素材而跳过」和「因提前终止而跳过」会混在一起，
  重提时无法判断该补审哪些维度。

- **代价与局限（三条）**：

  1. **声明与实现是两份，靠人工保持一致。** 值目前完全一致，
     但 `constraints.yaml:96` 的注释写 `源码 Step 1 (L136-L152)`，
     实际代码在 `orchestrator.py:98-112`。这类行号注释在每次调整编排顺序时都要重抄一遍，
     而 `constraints.yaml:20`、`:63`、`:88`、`:151` 四处已经失效。

  2. **`harness/tool_masks.yaml` 是同一份逻辑的第三种表达。**
     它用 `masks` 段（`tool_masks.yaml:101` 起）把「条件 → 屏蔽哪些 Tool → skip_reason」
     写成声明式结构，例如 `no_text_content` mask 的
     `block: [{tool: "text_checker", skip_reason: "无文案内容"}]`。
     这个文件零代码引用。现在同一个跳过原因在
     `constraints.yaml`、`tool_masks.yaml`、`orchestrator.py` 三处各有一份。

  3. **`trigger_condition` 只覆盖「有没有素材」，不覆盖「素材类型是否匹配」。**
     `constraints.yaml:99` 写 `trigger_detail: "有文案内容时执行（title/description/cta_text 至少一个非空）"`，
     与 `orchestrator.py:381-388` 的 `_build_text_content` 一致。
     但 `request.creative_type` 这个字段在编排里没有被任何分支读取
     （`grep -rn "creative_type" src/agents/` 只命中构造 Tool 输入时传给
     `PlatformRuleCheckerInput`，见 `orchestrator.py:315`）。

- **Momcozy 迁移形态**：六维改成 Momcozy 的审计维度，
  每个维度补两个字段：`requires`（该维度需要哪些输入字段）与
  `absent_action`（缺字段时是 `skip` 还是 `review`）。
  对母婴品类，`claim_substantiation` 维度缺证据材料时不能 `skip`，
  应判 `review`，判 `skip` 会把「没有证据」误当成「无法检测」。
  另外把 `trigger_condition` 做成可执行的表达式字符串
  （如 `"len(content.image_urls) > 0 or content.video_url is not None"`），
  由编排层用受限求值器解释，让声明与实现合一。
  这是让 `tool_masks.yaml` 那套设计真正接线的最小改动。

- **证据强度**：已实读核实（六个 Tool 的声明值、六处 skip 原因文本、
  `trigger_condition` 在 Python 侧零命中均已逐条核对）

---

## S1-12 REJECT 仅由人工标记的责任边界

- **出处**：`ad-review-agent/harness/constraints.yaml:31-32`、
  `ad-review-agent/src/schemas/result.py:12-16`、
  `ad-review-agent/src/agents/decision_engine.py:148-149`、
  `ad-review-agent/src/api.py:720-742`、`ad-review-agent/evals/run_eval.py:343-371`（已实读核实）
- **一句话**：自动判定路径确实从不返回 REJECT，四个构造出口里没有一处产出它；
  但 `src/api.py:299` 与 `:320` 在异步审核的返回体里写了字面量
  `"text_verdict": "reject"`，且评测集的标注词表用的也是 `reject`，靠一层等价映射兜住。

- **原文（枚举定义处写明用途）**：

```12:16:ad-review-agent/src/schemas/result.py
class ReviewVerdict(str, Enum):
    PASS = "pass"
    REVIEW = "review"      # 需要人工复核
    RETURNED = "returned"  # 退回修改（有明确修改建议）
    REJECT = "reject"      # 保留用于极严重违规（涉政/色情/暴力），由人工标记
```

- **原文（声明层）**：

```31:32:ad-review-agent/harness/constraints.yaml
# 注意: REJECT 保留给极严重违规（涉政/色情/暴力），仅由人工审核员标记，
#       系统自动判定统一使用 RETURNED。
```

- **原文（决策层，判定函数只产出三种）**：

```148:149:ad-review-agent/src/agents/decision_engine.py
        注意：reject 保留用于极严重违规（涉政/色情/暴力），
        由人工审核员手动标记，系统自动输出统一用 returned。
```

- **原文（人工入口，只接受两个值，REJECT 从这里进入系统）**：

```720:742:ad-review-agent/src/api.py
class HumanDecision(BaseModel):
    """人工审核决定请求体。"""
    verdict: str = Field(description="人工审核结论：pass 或 reject")
    reviewer: str = Field(description="审核员标识")
    note: str = Field(default="", description="审核备注")


@app.post("/queue/{request_id}/decide")
async def decide_review(request_id: str, decision: HumanDecision) -> dict:
    """
    提交人工审核决定。

    更新 ReviewRecord 的人工审核字段，将 ReviewQueue 状态设为 done。

    Args:
        request_id: 请求 ID
        decision: 人工审核决定

    Returns:
        操作结果
    """
    if decision.verdict not in ("pass", "reject"):
        return {"error": "invalid_verdict", "message": "verdict must be 'pass' or 'reject'"}
```

- **原文（评测层用等价映射吸收两套词表的差异）**：

```343:371:ad-review-agent/evals/run_eval.py
def _verdict_match(expected: str, actual: str) -> bool:
    """
    判断实际 verdict 是否匹配预期。

    匹配规则：
    - 完全匹配为 True
    - expected=reject ↔ actual=returned 互相等价（系统用 returned 代替 reject）
    - expected=reject/returned, actual=review 视为安全侧偏差（不漏审）
    - expected=pass, actual=review 不算对（误拒进人工队列增加工作量）

    Args:
        expected: 预期 verdict
        actual: 实际 verdict

    Returns:
        是否匹配
    """
    if expected == actual:
        return True

    # reject ↔ returned 互相等价
    if {expected, actual} == {"reject", "returned"}:
        return True

    # reject/returned → review 是安全的（不会漏审，只是多了人工环节）
    if expected in ("reject", "returned") and actual == "review":
        return True

    return False
```

- **核实过程与结论**：`grep -rn "ReviewVerdict.REJECT\|verdict=ReviewVerdict" --include=*.py src/ evals/`
  共两处命中：`result_builder.py:525` 是读取判断
  （`elif verdict in (ReviewVerdict.RETURNED, ReviewVerdict.REJECT):`），
  `result.py:61` 是降级结果构造，写的是 `verdict=ReviewVerdict.REVIEW`。
  自动路径没有任何一处构造 `ReviewVerdict.REJECT`。
  `decision_engine.py:159-190` 的四个返回分支分别是 REVIEW、REVIEW、RETURNED、PASS，
  没有第五个分支。所以「系统自动判定统一 RETURNED」这条在决策链路上成立。

- **三条边界外的例外（实读发现，声明里没写）**：

  1. **厂商侧返回体里有字面量 `"reject"`。** `src/api.py:296-303` 在写异步任务的
     `sync_result_json` 时构造：

```298:302:ad-review-agent/src/api.py
                sync_result_json=json.dumps({
                    "text_verdict": "reject" if text_violations else "pass",
                    "text_violations": len(text_violations),
                    "text_confidence": text_confidence,
                }, ensure_ascii=False),
```

     `src/api.py:320` 在另一个返回体里重复同一表达式。
     这个 `text_verdict` 是独立于 `ReviewVerdict` 枚举的字符串字段，
     任何按字符串匹配 `"reject"` 的下游都会看到一个系统生成的 reject。

  2. **评测集的标注词表用 `reject`。** 105 条样本里 50 条标为
     `"expected_verdict": "reject"`（`reject_cases.jsonl` 35 条 +
     `adversarial_cases.jsonl` 15 条）。这些样本走的是自动判定路径，
     系统只会输出 `returned`，靠 `run_eval.py:363-365` 的等价映射算作匹配。
     等价关系写在评测层，不在 schema 层，也不在决策层。

  3. **`reject` 在统计口径里被合并。** `src/api.py:955-958` 把
     `verdict_dist.get("returned", 0) + verdict_dist.get("reject", 0)` 合并为
     `auto_returned`。这一步承认了 `reject` 会出现在历史数据里，
     来源是早期版本或人工标记。

- **为什么这样做 / 不这样做会出什么事**：`AGENTS.md:11` 的产品理念是
  `「核心产品理念：帮助广告主修改素材，而非简单拒绝。」`，
  而 `AGENTS.md:59` 把「不做最终审核决定」列为 Out of Scope。
  REJECT 在语义上意味着终局（不可修改、需下架或封禁），
  系统在发布前一次性把关的场景里没有权限给出终局。
  把这三种动作分成「系统可自动（PASS / RETURNED）」「系统不可自动（REJECT）」两类，
  责任边界清楚：广告主收到的 RETURNED 带修改建议，可重提；
  审核员给出的 REJECT 进入申诉流程。若不区分，
  系统会把「广告法第九条」这种可改的表述问题判成终局拒绝，
  广告主失去修改机会，误拒率指标（`AGENTS.md:20` 目标 ≤ 10%）也会被拉高。

- **代价与局限**：

  1. **责任边界靠注释与命名约定，没有运行时强制。** 没有任何断言或类型层约束
     阻止未来某段代码构造 `ReviewVerdict.REJECT`。要强制，
     需要把枚举拆成两个（`AutoVerdict` 与 `HumanVerdict`），
     或在 `Decision.decide()` 的返回值上加校验。

  2. **两条词表并存带来映射成本。** 评测层、统计层、人工入口三处都要知道
     `reject ↔ returned` 的等价关系。新增一处消费 `verdict` 的代码时，
     漏掉这个等价关系会产生静默的口径错误。

  3. **`api.py:741` 的人工入口只允许 pass 与 reject，没有 returned。**
     审核员面对一条系统判 RETURNED 的素材，只能二选一：
     确认合规（pass）或升级为终局拒绝（reject）。
     「系统判重了，应该是 returned」这种复核结论无法表达。

- **Momcozy 迁移形态**：责任边界保留，术语按美国市场的发布前把关重写。
  系统自动输出改为三态：`PASS`、`NEEDS_REVISION`（对应 RETURNED）、
  `ESCALATE`（证据不足或触及 FDA 边界，必须人工）。
  `REJECT` 仅由人工写入，对应「必须下架或封禁」的终局动作。
  评测集的标注词表直接改用系统词表，不再做等价映射，
  消除上面第 2 条映射成本。
  人工入口补第三选项 `NEEDS_REVISION`，
  对应「系统判得偏严但确实有问题」的中间结论。
  `api.py:299` 那类 `sync_result_json` 的字面量字段改名为
  `text_findings_present: true/false`，避免在返回体里出现任何名为 reject 的字段。

- **证据强度**：已实读核实（四个构造出口、人工入口、评测等价映射、
  异步返回体的字面量均已逐行核对）

---

## S1-13 模型路由（选做）

- **出处**：`ad-review-agent/harness/model_router.yaml:26-47`、
  `ad-review-agent/harness/model_router.yaml:139-156`、
  `ad-review-agent/src/harness/model_router.py:34`、
  `ad-review-agent/src/harness/model_router.py:128-147`（已实读核实）
- **一句话**：七个任务类型各自声明 provider、模型、超时、重试与降级动作，
  路由层支持声明的 `fallback_route` 二次调用，成本单价也放进同一份 YAML。

- **原文（三个 provider，其中一个是 SDK 调用）**：

```26:55:ad-review-agent/harness/model_router.yaml
providers:
  deepseek:
    # 用途: 文案分析、语义理解、落地页分析、一致性文本比对、reason 生成
    # 源码: text_checker.py:428, landing_page.py:374, consistency_checker.py:657
    base_url_env: "DEEPSEEK_BASE_URL"
    base_url_default: "https://api.deepseek.com"
    api_key_env: "DEEPSEEK_API_KEY"
    default_model: "deepseek-chat"
    # 对应 src/config.py: deepseek_model = "deepseek-chat"
    api_format: "openai_compatible"
    endpoint_path: "/chat/completions"

  dashscope:
    # 用途: 图片/视频视觉理解、一致性视觉比对
    # 源码: image_checker.py:894, consistency_checker.py:514
    base_url_env: "DASHSCOPE_BASE_URL"
    base_url_default: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env: "DASHSCOPE_API_KEY"
    default_model: "qwen-vl-max"
    # 对应 src/config.py: qwen_vl_model = "qwen-vl-max"
    api_format: "openai_compatible"
    endpoint_path: "/chat/completions"

  dashscope_asr:
    # 用途: 视频音频语音转写
    # 源码: audio_checker.py:198-210（使用 dashscope SDK 原生调用，非 HTTP）
    api_key_env: "DASHSCOPE_API_KEY"
    default_model: "paraformer-realtime-v2"
    api_format: "dashscope_sdk"
    # 注意: 此 provider 使用 dashscope Python SDK 而非 httpx HTTP 调用
```

- **原文（唯一配了 fallback_route 的路由）**：

```139:156:ad-review-agent/harness/model_router.yaml
  consistency_visual:
    # ConsistencyChecker 的视觉维度一致性比对（Qwen VL）
    # 源码: src/tools/consistency_checker.py → _check_pair_visual() (L514-L582)
    #   url = f"{settings.dashscope_base_url}/chat/completions"
    #   headers = {"Authorization": f"Bearer {settings.dashscope_api_key}"}
    #   payload = {"model": settings.qwen_vl_model, ...}
    #   async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
    #   注意: 此路由无重试，失败后直接 fallback 到 consistency_text
    provider: "dashscope"
    model: "qwen-vl-max"
    timeout: 30.0           # settings.llm_timeout
    max_retries: 1          # 无重试循环，单次调用，失败 fallback 到 text
    retry_delay: 0
    temperature: 0.1
    supports_multimodal: true
    fallback_action: "fallback_to_consistency_text"
    fallback_route: "consistency_text"
    description: "跨维度一致性视觉比对（文案↔图片、图片↔落地页 品牌冲突检测）"
```

- **原文（路由失败后按声明换路重试，未声明则原样抛出）**：

```128:147:ad-review-agent/src/harness/model_router.py
        except Exception as primary_err:
            # 尝试 fallback route（如果配置了）
            fallback_route_name = route.get("fallback_route")
            if fallback_route_name and fallback_route_name in self._routes:
                logger.warning(
                    "Primary route failed, trying fallback",
                    task_type=task_type,
                    provider=provider_name,
                    fallback_route=fallback_route_name,
                    error=str(primary_err),
                )
                fallback_route = self._routes[fallback_route_name]
                return await self._call_provider(
                    task_type=task_type,
                    provider_name=fallback_route["provider"],
                    route=fallback_route,
                    messages=messages,
                    **kwargs,
                )
            raise
```

- **为什么这样做 / 不这样做会出什么事**：`AGENTS.md:52` 与 `:495` 都写了
  `「Tool 通过 ModelRouter 调用 LLM，不得直接构造 httpx 客户端调用」`。
  动机是换模型只改 YAML。视觉一致性检测配了 `fallback_route`，
  因为 `qwen-vl-max` 是七个路由里最贵且最不稳定的一条，
  视觉比对失败后降级到纯文本比对仍能覆盖品牌冲突这类主要场景。
  `progress.txt:57` 记 `「src/harness/model_router.py: 7 routes、3 providers」`，
  与文件一致（`routes` 段有 text_analysis、image_analysis、landing_page_analysis、
  consistency_text、consistency_visual、audio_transcription、reason_generation 七个键）。

- **代价与局限**：

  1. **`consistency_visual` 的降级是「静默换一种检测方式」。**
     `model_router.py:140-146` 用同一个 `task_type` 调用 fallback route，
     调用方拿到的返回体里 `model` 字段会变成 `deepseek-chat`，
     但 `task_type` 仍是 `consistency_text`（`model_router.py:141` 传的是原 `task_type`）。
     上层若不检查返回的 `model`，无法知道这次的「视觉比对」实际是文本比对。

  2. **成本单价写在 YAML 里，没有校验。**
     `model_router.yaml:193-208` 的 `cost_per_1k_tokens` 段注明
     `「价格为截至 2026-03 的公开定价，需定期核实更新」`，
     没有过期时间字段，也没有检查。`AGENTS.md:19` 的成本目标
     `「单条素材处理成本 ≤ ¥0.05」` 依赖这组数字成立。

  3. **`endpoint_path` 声明了但硬编码兼容。** 三个 provider 里两个写
     `endpoint_path: "/chat/completions"`，但 `model_router.py` 未在我核对的
     `:1-160` 区间内读取该键（该区间内 `endpoint_path` 零命中）。

- **Momcozy 迁移形态**：七个路由换成 Momcozy 的调用面：
  `claim_text_analysis`、`image_claim_extraction`、`video_keyframe_analysis`、
  `listing_vs_creative_consistency`、`label_vs_creative_consistency`、
  `reason_generation_us`、`aigc_provenance_check`（AIGC 视频的溯源与合成痕迹检查）。
  美国市场必须换供应商：`deepseek-chat` 与 `qwen-vl-max` 的数据出境与
  合规审查问题在美国市场的品牌内容审计里难以接受，
  改为在美国境内有数据处理的供应商。
  `cost_per_1k_tokens` 增加 `checked_at` 与 `source_url` 两个字段，
  加载时若 `checked_at` 超过 90 天则在启动日志里告警。
  视觉路由的 fallback 改为「降级到人工」而不是「降级到文本比对」，
  因为 AIGC 视频的视觉证据无法用文本替代。

- **证据强度**：已实读核实（路由数、provider 数、fallback 逻辑、成本段均已核对；
  `endpoint_path` 未消费一项仅在我读取的 `:1-160` 区间内核实）

---

## 十一、横向对比小结

| 机制 | ad-review-agent 的做法 | 对照仓库的做法 | 对照仓库为什么可以那样 |
|---|---|---|---|
| 阈值存放 | `harness/constraints.yaml` + 加载器 | `cbi` 的规则写在 `backend/src/rules/platformRules.js`（294 行），版本号是导出常量 `RULE_VERSION = 'v3.2'`，`backend` 下无 YAML/JSON 配置 | `cbi` 的规则是「平台 × 图片类型 × 维度」的嵌套对象，改一条必然连带改 actionType 处理分支，规则与代码同处减少错配 |
| 失败处理 | `BaseTool.run()` 自动降级，六个 Tool 各自实现 `_fallback` | `invoice/backend/app/services/ai_service.py` 用 `allow_local_fallback: bool = False` 参数把降级决定权交给调用方，不允许时抛出带操作指引的异常 | 发票识别可以要求用户重传，广告素材已在提交管道里，必须先给出结论 |
| 提前终止 | 过程式 `run()` 步骤顺序 + 事后补记被跳过维度 | `contract_audit` 用图状态机的条件路由，仅高风险样本进入最贵的改写节点 | 图路由需要 checkpointer 与显式状态契约，成本更高，适合节点少而单节点贵的场景 |
| 评测门禁 | `regression_check.py` 比四个指标，CI 里注释关闭 | `ad-compliance-agent` 用 100 条测评集与 `scripts/run_eval_100.py`，单次批量评测加人工读报告 | 没有自动化流水线时，门禁脚本与手工评测等价，多出的 baseline 约定反而增加维护面 |

## 十二、README 与文档声称但代码中未接线清单

以下六条均为「文档说 X 而代码里查不到 X」，逐条给出证据。

1. `progress.txt:29` 声称 `「Phase 3a: constraint_loader + DecisionEngine 全面读 YAML（零硬编码阈值）」`。
   决策引擎自身确实零硬编码（`decision_engine.py:32-38` 四个键全从 YAML 读），
   但 `orchestrator.py:424` 的 `if confidence <= 0.9:` 与
   `text_checker.py:183` 的 `confidence = max(0.92, llm_confidence)`
   是两个未外部化的硬编码阈值，且 0.9 正是 `constraints.yaml:80` 声明过的
   `min_confidence: 0.9`。`progress.txt:54` 的
   `「decision_engine.py: 零硬编码阈值」` 这一句在单个文件范围内成立。

2. `progress.txt:27` 与 `:74` 把 `tool_masks.yaml`、`observability.yaml` 与
   `constraints.yaml`、`model_router.yaml` 并列为「harness/ 声明式配置层」。
   前两个文件零代码引用（见 0.2 节的 grep 结果）。
   `tool_masks.yaml` 自己也写着
   `「Phase 3a（FEAT-AHF-003）实施后，Orchestrator 将从此文件决定每次审核实际执行哪些 Tool」`，
   用的是将来时，与 `progress.txt` 的完成时表述不一致。

3. `progress.txt:59` 声称
   `「grep "httpx.AsyncClient" src/tools/ 确认零直接 LLM 调用」`。
   实测 `grep -rn "httpx" src/tools/*.py` 命中 17 处，
   其中 `consistency_checker.py:596` 与 `image_checker.py:436`、`:582` 是
   `httpx.AsyncClient` 的使用点。这三处用于下载图片、下载视频、下载落地页，
   属素材抓取而非 LLM 调用，所以该条声称在
   「不直接构造 httpx 客户端调用 LLM」这个精确表述下成立，
   在「零 httpx 使用」这个宽泛理解下不成立。

4. `constraints.yaml:20-21`、`:63`、`:88`、`:151` 四处「源码位置」注释指向
   `src/agents/review_agent.py` 的不同行号。该文件只有 60 行，
   全部实现已拆到 `decision_engine.py` 与 `orchestrator.py`。

5. `constraints.yaml:190` 的 `对应: _NON_DRAG_TYPES = ("ImageCheckerOutput", "ConsistencyCheckOutput")`
   所引符号在仓库内不存在，只在 `constraints.yaml` 自身出现一次。

6. `consistency_rules.json:103` 的 `"only_check_when": "图片包含明显品牌标识时才触发"`
   在 Python 侧零命中，实际触发条件由 `orchestrator.py:355-357` 传入
   `has_brand_in_image` 决定。

## 十三、迁美的法条映射（S1 分片涉及的全部中国法条）

`ad-review-agent` 的规则库里出现的中国法条共 5 处，全部来自
`forbidden_words.json` 与对抗样本的 `regulation_ref`。逐条给出迁美处置：

| 出现位置 | 原文法条 | 覆盖内容 | 迁美处置 |
|---|---|---|---|
| `forbidden_words.json:10` | `《广告法》第九条第三款` | 绝对化用语，20 个词 | 不能整条搬。美国无此独立违法类型，对应 FTC 的未获证实优越性宣称；`保证`、`承诺效果` 仍列高危 |
| `forbidden_words.json:21` | `《广告法》第二十八条` | 虚假宣传，4 条正则 | 可迁移到 FTC Act Section 5 的 deceptive claims；四条正则形态可直接复用 |
| `forbidden_words.json:32` | `《互联网广告管理办法》第九条` | 诱导性表述，6 个词 | 部分迁移到 FTC 对 deceptive interface 的执法；手机病毒恐吓类词与母婴品类无关，删除 |
| `forbidden_words.json:41` | `《网络游戏管理暂行办法》` | 游戏买量禁用词，6 个词 | 不迁移。中国版号制度配套规范，美国无对应制度 |
| `forbidden_words.json:50` | `《广告法》第二十五条` | 金融收益承诺，7 个词 | 部分迁移。收益保证类词在 FTC 下同样高危；`年化收益.*%` 属 SEC/FINRA 管辖，Momcozy 不涉及 |
| `adversarial_cases.jsonl:11`（`adversarial-011`） | `《广告法》第十七条` | 疗效宣称 | 迁移后须换成 FDA 的医疗宣称边界判定；这是 Momcozy 最需要新建规则组的法域 |
| `consistency_checker.py:316-319` | `《互联网广告管理办法》第九条` | 一致性违规的引用文本 | 硬编码在代码里的一致性违规引用，迁美后改为读规则文件 |

需要新建的美国法域锚点（`ad-review-agent` 中不存在）：
FTC Act Section 5（deceptive acts or practices）、
FTC Health Products Compliance Guidance（健康类宣称的证据标准）、
FDA 医疗宣称边界（吸乳器相关功效表述在此边界上）、
CPSC 儿童产品安全宣称、
Amazon 平台对母婴品类的图片与文案规范。
