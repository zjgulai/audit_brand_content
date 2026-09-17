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
