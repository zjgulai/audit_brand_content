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
