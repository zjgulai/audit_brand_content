#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/intent_infer.py —— 内容阶段的**建议值**推断（T-455）

## 它为什么存在

上游 PRD `PRD/feishu/内容审查Agent-PRD-v1.0.md:137` 写着：
「Agent 自动识别内容类型和内容阶段（brief / final_content）」。

本仓 2026-10-27 的实测：

| 字段 | 真实状态 |
|---|---|
| `content_type` | **已经确定性推导**了 —— `base/submission_service.py:105` 的 `_SOURCE_KIND_CONTENT_TYPE` 把 `free_text`/`ad_text` → 文本、`image` → 图片，传错直接 422。**不需要"识别"，需要的是说出它已经发生过** |
| `content_stage` | 四维校验必填（`submission_router.py:82`），但**没有任何东西会推断它** —— 调用方不填就是 422 |

所以本模块只做一件事：**推断 `content_stage`，且只作建议值。**

## ★★ 一个必须如实说出来的事实：推断出来的值，今天没有规则消费它

`research/governance/skeleton/rules-v1.json` 的 36 条规则里：

    brief          出现 0 次
    final_content  出现 0 次
    content_stage  出现 0 次
    （正向对照：severity 出现 39 次、layer 38 次 —— 扫描器是活的）

`base/` 下它也只在两处出现：取值域校验、写进 `ContentUnit`。

**也就是说：本模块推断得再准，今天也不会改变任何一条判定。**

这句话必须能被机器读出来（`rule_consumer_status()`），否则「意图识别做完了」
会在表里读成「这个能力生效了」—— 那是本项目反复踩的形状
（`due_at`、工作流耗时、`semantic_judge` 三个先例）。

## 口径

* **只作建议值，绝不覆盖调用方。** 调用方给了值 → 一律采信，推断结果只落观察。
  理由：`content_type`/`content_stage` 是**调用方申报的事实**（这条内容是什么），
  不是模型可以改写的判断。自动识别覆盖它，等于把"用户说这是终稿"变成"模型觉得这是 brief"。
* **推断不出 → `untested` 并点名，不许默认成某个值。**
  默认成 `final_content` 会把 brief 阶段的文案按终稿标准判 —— 那是最坏的方向。
* **规则，不用模型。** 模型推断无法反向对照（同一输入两次结果可能不同），
  而这个模块的每一条判据都要求「什么变异让它红」。
* **证据必须能指出来。** 返回 `evidence` 是命中的那几个词/特征，
  不是一句"模型认为"。这样人复核时能立刻看出它凭什么这么判。

## 不做什么

* 不推断 `content_type`（已由 `source.kind` 确定性推导，再推断一遍就是两个口径）。
* 不判断"该用哪个 skill"（那是 `base/skill_registry.py`）。
* 不因为推断出 brief 就改变判定标准（见上：今天没有规则消费它）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

#: `content_stage` 的取值域。**与 `base/contract.py` 同源**，不在这里抄第二份值。
def stages() -> Tuple[str, ...]:
    from base import contract as C
    return tuple(C.CONTENT_STAGES)


#: 三态。与项目其他读数同一口径：有结论 / 没测成 / 根本没法测。
STATUS_INFERRED = "inferred"
STATUS_UNTESTED = "untested"
STATUS_ABSENT = "absent"          # 调用方已给值 → 本模块不推断

#: ★ 判据名。改了信号就必须改它 —— 一个结论离开它的判据就没有意义
#:   （与 `change_detect` 的 `claim-set-v1` 同一条理由）。
JUDGE = "stage-signals-v1"


# ── 信号表 ─────────────────────────────────────────────────────────────────
#
# ★ 每一条都必须能被指出「它凭什么」。所以这里只放**可逐字引用**的特征：
#   命令式/要求式的词、字数与规格约束、投放说明，这些都是 brief 的形状；
#   而终稿是**给消费者看的成品**，通常直接是产品话术。
#
# ★ 刻意不用「有没有 emoji」「有没有第一人称」这类弱特征 ——
#   它们在两类里都常见，加进来只会让判据变得无法反向对照。

_BRIEF_SIGNALS: List[Tuple[str, str]] = [
    # (正则, 人读的理由)
    (r"需求|brief|任务说明|创作要求|文案要求|写作要求", "出现「需求/创作要求」这类工作说明"),
    (r"需包含|需体现|必须包含|必须体现|要求包含|要包含", "出现「需包含/必须体现」这类交付要求"),
    (r"不要出现|不得出现|避免使用|禁止使用|不可使用", "出现「不要出现/禁止使用」这类禁令"),
    (r"字数|不超过\s*\d+\s*字|控制在\s*\d+|限\s*\d+\s*字", "出现字数/篇幅约束"),
    (r"卖点方向|主打|定位|目标人群|调性|风格要求", "出现卖点方向/目标人群/调性这类策划语言"),
    (r"参考|对标|借鉴.{0,6}案例|示例文案", "出现参考/对标这类策划动作"),
    (r"待确认|待定|初稿|草稿|大纲|框架", "自称初稿/大纲/草稿"),
]

#: 终稿信号。★ 比 brief 信号弱，因为它靠"像成品"来判断，
#: 而"像成品"本身难有确定性特征 —— 所以它只在**没有 brief 信号**时起作用。
_FINAL_SIGNALS: List[Tuple[str, str]] = [
    (r"[™®©]|官方旗舰店|限时|到手价|立即购买|立即抢购|下单", "出现成品才有的商标/促销/行动号召"),
    (r"[，。！？；：]\s*$|\n.{20,}", "是成段的完整文案（不是要点式清单）"),
]


def _hits(text: str, table: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    out = []
    for pattern, why in table:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            out.append({"pattern": pattern, "hit": m.group(0)[:40], "why": why})
    return out


def infer_stage(text: Any, *, declared: Optional[str] = None) -> Dict[str, Any]:
    """推断 `content_stage`。**返回建议值，永远不改调用方给的值。**

    返回：

        {
          "判据": "stage-signals-v1",
          "status": "inferred" | "untested" | "absent",
          "value": "brief" | "final_content" | None,
          "declared": 调用方给的值（原样回显，便于对拍）,
          "agrees_with_declared": bool | None,   # None = 没有可比的
          "confidence": "high" | "low" | None,
          "evidence": [{"pattern","hit","why"}, ...],
          "reason": str,     # untested/absent 时说清为什么没推断
        }

    ★ `declared` 给了值时 **不做推断**（status=absent）——因为结果不会被采用，
      而"推断了一个不会被用的值"本身就是噪声。这与「只作建议值」是同一件事。
    """
    judge = {"判据": JUDGE, "declared": declared}

    if declared is not None:
        return dict(judge, status=STATUS_ABSENT, value=None,
                    agrees_with_declared=None, confidence=None,
                    evidence=[],
                    reason="调用方已给 content_stage=%r，不推断（只作建议值，不覆盖）"
                           % (declared,))

    if not isinstance(text, str) or not text.strip():
        return dict(judge, status=STATUS_UNTESTED, value=None,
                    agrees_with_declared=None, confidence=None, evidence=[],
                    reason="没有可读正文，无法推断内容阶段")

    brief_hits = _hits(text, _BRIEF_SIGNALS)
    final_hits = _hits(text, _FINAL_SIGNALS)

    # ★ brief 信号优先：brief 的特征是**命令式/要求式**的，误判方向是
    #   「把 brief 当终稿判」—— 那会把还没定稿的文案按终稿标准下结论，
    #   是最坏的方向。所以只要出现 brief 信号就先认 brief。
    if brief_hits:
        # 两条以上 brief 信号 → high；只有一条 → low（一条可能是巧合）
        conf = "high" if len(brief_hits) >= 2 else "low"
        return dict(judge, status=STATUS_INFERRED, value="brief",
                    agrees_with_declared=None, confidence=conf,
                    evidence=brief_hits,
                    reason="命中 %d 条 brief 信号" % len(brief_hits))

    if final_hits:
        return dict(judge, status=STATUS_INFERRED, value="final_content",
                    agrees_with_declared=None, confidence="low",
                    evidence=final_hits,
                    reason="未命中 brief 信号，命中 %d 条成品特征"
                           % len(final_hits))

    # ★★★ 这一条是本模块最重要的行为：两边都没命中 → **untested**，不许默认。
    #   默认成 final_content 会让 brief 文案被按终稿标准判；
    #   默认成 brief 会让终稿被当成草稿放过。两个方向都错，所以不选。
    return dict(judge, status=STATUS_UNTESTED, value=None,
                agrees_with_declared=None, confidence=None, evidence=[],
                reason="没有命中任何阶段信号（brief 与成品特征都是 0 条）——"
                       "不默认成任何一档，交由调用方申报")


def compare(declared: Optional[str], inferred: Dict[str, Any]) -> Dict[str, Any]:
    """调用方给的值 vs 推断值 → 一条**观察**（不阻断、不覆盖）。

    ★ 只在两者都有值且不一致时才有内容；其余情况 `agree` 为 None。
      「没有分歧」与「无法比较」必须长得不一样（前者 agree=True，后者 None）。
    """
    value = (inferred or {}).get("value")
    if declared is None or value is None:
        return {"agree": None, "note": "没有可比较的两方（一方为空）",
                "declared": declared, "inferred": value}
    if declared == value:
        return {"agree": True, "note": "调用方申报与推断一致",
                "declared": declared, "inferred": value}
    return {"agree": False,
            "note": "调用方申报 %r，推断 %r —— **以调用方为准**，此处仅记观察"
                    % (declared, value),
            "declared": declared, "inferred": value}


def rule_consumer_status() -> Dict[str, Any]:
    """★★★ 如实报出：今天有没有规则真的消费 `content_stage`。

    这个函数存在的唯一理由：让「推断得再准也不改变判定」**成为一条可读的读数**，
    而不是一句写在注释里的话。没有它，表里那条「意图识别已完成」会被读成
    「这个能力生效了」—— 本项目已有三个同形先例（due_at / 工作流耗时 /
    semantic_judge 桩）。

    ★ 判据是**数规则文件里出现几次**，且必须带正向对照：若某个确定性存在的
      字段（`severity`）也是 0 次，说明扫描器坏了，此时结论只能是 `untested`。
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    path = root / "research" / "governance" / "skeleton" / "rules-v1.json"
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        return {"status": "untested",
                "reason": "规则文件读不出：%s" % (type(exc).__name__,),
                "consumers": None}

    rules = data if isinstance(data, list) else (data.get("rules") or [])
    counts = {k: raw.count(k) for k in ("content_stage", "brief", "final_content")}
    # ★ 正向对照：这几个词在规则文件里一定有。若它们也是 0，说明我读错了文件。
    controls = {k: raw.count(k) for k in ("severity", "layer")}
    if not all(v > 0 for v in controls.values()):
        return {"status": "untested",
                "reason": "正向对照为 0（%r）—— 扫描对象可能不是我以为的那份文件"
                          % (controls,),
                "counts": counts, "controls": controls}

    consumed = sum(counts.values()) > 0
    verdict = _stage_consumption_verdict(counts, controls, len(rules))
    return {
        "status": "measured",
        "rule_count": len(rules),
        "counts": counts,
        "controls": controls,
        "consumed_by_rules": verdict["consumed_by_rules"],
        "conclusion": verdict["conclusion"],
    }


def _stage_consumption_verdict(counts, controls, rule_count):
    """把「数出几次」翻成结论。**本模块唯一的判定点**，自证也调这一个。

    ★ 为什么要把结论句也放在这里：自证要断言「抽出的判定函数与
      `rule_consumer_status()` 的结论逐字相同」（G8）。若结论句在别处拼，
      两处就会各自漂移 —— 而漂移的表现是「自证过的措辞」与「真发出去的措辞」
      不是同一句。
    """
    if sum(counts.values()) > 0:
        return {"consumed_by_rules": True,
                "conclusion": "有规则消费 content_stage"}
    return {
        "consumed_by_rules": False,
        "conclusion": (
            "**没有任何规则消费 content_stage** —— 推断值今天不改变任何判定"
            "（%d 条规则里 content_stage/brief/final_content 各出现 0 次；"
            "正向对照 severity=%d、layer=%d）"
            % (rule_count, controls["severity"], controls["layer"])),
    }
