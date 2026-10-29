#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/observation_candidates.py —— 把**确定性高的观察**升级为 candidate finding

## 它为什么存在

2026-10-29 实测：本系统对 5 张英文素材各产出 10–15 条**高质量观察**
（「Trail 疑为 Trial 拼写错误」「A$ 与 £ 混用」「画面遍布设计稿水印」），
而 `findings` 是 **0 条** —— 观察停在 L1，没进复核队列。

裸大模型对同样 5 张产出 21 条 finding。**它并不更准**（人工比对：
双方发现的是同一批问题），差别在于**它把观察直接写成了结论**。

所以真正缺的不是眼睛，是**从观察到待复核项的那一段**。

## ★★ 只升级「确定性事实」，不升级「法规判断」

| 可以自动升级 | 为什么 | 不可以自动升级 | 为什么 |
|---|---|---|---|
| 拼写 / 语法错误 | 客观、可复核、不依赖法规 | 医疗宣称 | 要看目标市场法规与上下文 |
| 货币 / 单位混用 | 同上 | 功效暗示 | 要看画面与文案的组合语义 |
| 设计稿水印 / 占位符 | 同上 | 极限词 | 中英差异大，靠字符串匹配脆弱 |
| 分辨率 / 清晰度不足 | 同上 | 品牌调性一致性 | 判据主观，无法复核 |

★ 这条边界不是保守，是**可复核性**：一条自动 finding 必须能让另一个人
  不带上下文地判断「对还是错」。判断不了的不许自动产出 ——
  那会让人开始不看队列。

## 与 `semantic_judge` 的关系

`semantic_judge` 的 C1–C4 是**把 candidate 升成 confirmed** 的条件，
比本模块严格得多。本模块**只产 candidate**，且 `confirmed_by_rule_class=False`、
`authority_state="untested"` —— 与 `semantic_judge.make_candidate()` 同一形状。

★ 不复用 `make_candidate()`：它要求调用方已经知道 control_code，
  而本模块的职责恰恰是**从观察文本判断该挂哪个码**。两者输入不同，
  混成一个函数会让「谁决定 control_code」变成两个地方。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

PRODUCED_BY = "verifiable-fact"

#: 可自动升级的事实类。**每个都点名一个 control_code**。
#:
#: ★ control_code 的选择依据是「这条观察说的东西属于哪一族的控制点」，
#:   不是「它有多严重」。全部用 `judge_type=literal` 且已启用的码 ——
#:   `get_active()` 会对未启用的码抛 `DeprecatedControlCode`（B01–B04、U02 今天不可用）。
#:
#: ★ 每条都带 `patterns` 与 `label`：`label` 进界面（审核员要一眼看懂
#:   「这是什么问题」），`patterns` 是判据（改了要写清新理由）。
RULES: List[Dict[str, Any]] = [
    {
        "key": "spelling",
        "control_code": "M01",
        "severity": "L2",
        "label": "拼写或语法错误",
        # ★ 观察原文里的说法（实测形态）：
        #   「可见文字Product Free Trail疑似Trial拼写错误」
        #   「Recieve a opportunity 及 a free a 等疑似拼写/语法错误」
        #   所以判据是「拼写|语法」+「错误|异常|疑似」两个词同时出现。
        "patterns": [
            r"拼写[^。；\n]{0,20}(错误|异常|问题)",
            r"(拼写|语法)[^。；\n]{0,12}疑似",
            r"疑似[^。；\n]{0,12}(拼写|语法)",
            r"spelling\s+(error|mistake)",
        ],
        "why": "客观可复核：把原文与建议写法并排放，另一个人立刻能判对错",
    },
    {
        "key": "currency-mix",
        "control_code": "M02",
        "severity": "L2",
        "label": "货币或计量单位混用",
        # 实测形态：「同一页面混用A$与£两种货币符号」「多处出现 CA$ 货币符号」
        # 「权益价值标注口径不一致」
        "patterns": [
            r"混用[^。；\n]{0,16}(货币|币种|单位)",
            r"(货币|币种)[^。；\n]{0,12}(混用|不一致)",
            r"口径不一致",
            r"currency[^.]{0,20}(mix|inconsisten)",
        ],
        "why": "客观可复核：符号在同一张图上，数得出几个币种",
    },
    {
        "key": "draft-marks",
        "control_code": "M03",
        "severity": "L3",
        "label": "设计稿水印或占位符残留",
        # 实测形态：「全画面多处重复出现「陈欣玮 2556 ROOT」字样水印，
        #   疑似素材或设计稿水印」「疑似非终稿或未授权素材」
        "patterns": [
            r"水印",
            r"非终稿",
            r"设计稿[^。；\n]{0,10}(残留|未清理)",
            r"占位(符|图|文本)",
            r"watermark",
        ],
        "why": "客观可复核：水印在画面上是可见的像素，不是判断",
    },
    {
        "key": "image-quality",
        "control_code": "M04",
        "severity": "L1",
        "label": "清晰度不足或无法辨认",
        # ★ 这一条要小心：观察里大量出现「看不清」「仅部分可辨认」，
        #   那是模型**主动说没看清**（正确行为），不是图片质量问题。
        #   所以判据要求「质量/分辨率」这类词与「不足/不达标」同时出现，
        #   而不是光看「看不清」—— 否则每条「看不清 X」都会变成一条 finding。
        "patterns": [
            r"(分辨率|清晰度|像素)[^。；\n]{0,10}(不足|过低|不达标)",
            r"图片[^。；\n]{0,8}(模糊|压缩过度)",
        ],
        "why": "客观可复核：像素尺寸是数得出来的",
    },
]


#: 否定前缀。★ 命中这些前缀的句子**一律不升级**。
#:
#: ## 为什么必须单独处理
#:
#: 实测（自证 B 组第一版）两条真误报：
#:
#:   「**未**见拼写或语法错误，文案表述规范」      → 被判成 M01（拼写错误）
#:   「画面干净，**无**水印、**无**占位符残留」    → 被判成 M03（设计稿水印）
#:
#: 规则只看到「拼写错误」「水印」这些词就命中了，完全没注意前面那个否定词。
#: 而这两句说的是**没问题** —— 把「没发现问题」写成「发现了问题」，
#: 是这一层最严重的方向性错误。
#:
#: ★ 判据是「否定词出现在被匹配片段**之前**的小窗口内」，
#:   不是「整句含否定词」—— 否则「未见拼写错误，但存在货币混用」
#:   里的否定词会把后半句也一起否掉。
_NEGATION = re.compile(
    r"(未|无|没有|不存在|未见|未发现|未检出|找不到|不含|未出现)"
    r"|\b(no|not|none|without|absent)\b",
    re.IGNORECASE,
)

#: 判定用的窗口长度：否定词要出现在匹配位置之前这么多字符内才算「否定这一处」。
#: ★ 12 是实测调出来的：中文观察里否定词离被否对象通常只有 2–8 个字
#:   （「未见拼写错误」「无水印」）；放宽到整句会误伤并列句。
_NEGATION_WINDOW = 12


def _is_negated(statement: str, match_start: int) -> bool:
    """被匹配到的片段是不是处于否定语境里。

    ★ 只看匹配位置**之前**的窗口，不看整句 —— 见 `_NEGATION_WINDOW` 的注释。
    """
    start = max(0, match_start - _NEGATION_WINDOW)
    return _NEGATION.search(statement[start:match_start]) is not None


def _compile(rules: Optional[List[Dict[str, Any]]] = None):
    """预编译。★ 只编译一次 —— 每张图重复 `re.compile` 是白花时间。"""
    out = []
    for rule in (RULES if rules is None else rules):
        out.append((rule, [re.compile(p, re.IGNORECASE) for p in rule["patterns"]]))
    return out


_COMPILED = None


def _compiled():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = _compile()
    return _COMPILED


def _finding_id(unit_id: str, rule_key: str, statement: str) -> str:
    """稳定的 finding_id。同一条观察重复产出时 id 不变（便于去重与复核）。

    ★ 用 `(unit_id, rule_key, statement)` 三者算，不用随机数 ——
      随机 id 会让「同一条问题在图 A 上传两次」变成两条 finding。
    """
    import hashlib

    body = "|".join([unit_id or "", rule_key, statement or ""])
    return "fc-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:18]


def candidates_from_observations(
    observations: List[Mapping[str, Any]],
    *,
    unit_id: str = "",
) -> List[Dict[str, Any]]:
    """把观察里**确定性高的事实类**升级成 candidate finding。

    返回的每条都满足：
      · `status="candidate"`（**绝不产 confirmed** —— 机器判定不越权）
      · `confirmed_by_rule_class=False`
      · `authority_state="untested"`
      · 带 `derived_from_observation`（指回原观察的 task + statement 前 80 字）

    ★ `untested` 而不是 `missing`：本模块**不查**权威依据（那是 evidence_sync
      的职责），所以「依据查没查」这件事它不知道 —— 不知道就不许写成 missing。

    ★ 空观察 → 空列表。**不伪造**，也不返回 None（调用方按可迭代用）。
    """
    if not isinstance(observations, list):
        return []
    compiled = _compiled()
    out: List[Dict[str, Any]] = []
    # ★ 去重键是 `(rule_key, control_code)`，**不是** finding_id。
    #
    #   实测：同一张图上有两条观察都提到水印（「全画面多处重复出现…水印」
    #   与「叠加有多个半透明…水印」），句子不同所以 finding_id 不同，
    #   于是产出两条 M03 —— 而它们说的是**同一件事**。
    #   界面上两条一模一样的「设计稿水印」读起来像两个问题。
    #
    #   ★ 按 control_code 去重，而不是按文本相似度：同一 control_code
    #     在同一张图上就是同一个问题，无论模型用几种说法描述它。
    #     要保留多条就必须挂不同的码（那才是真的两个问题）。
    seen_codes = set()
    for obs in observations:
        if not isinstance(obs, Mapping):
            continue
        # ★ 只处理**成功**的观察。untested / error 条目里没有 statement，
        #   对着它们跑正则只会得到空匹配（白花时间），而「没看成」
        #   本身不该产生 finding —— 那是另一件事（要在界面说「未评」）。
        if obs.get("status") != "ok":
            continue
        statement = str(obs.get("statement") or "").strip()
        if not statement:
            continue
        for rule, pats in compiled:
            # ★ 命中判据必须**排除否定语境** —— 见 `_NEGATION` 的注释。
            #   任一 pattern 在**非否定**位置命中才算这一条成立。
            hit = False
            for p in pats:
                for m in p.finditer(statement):
                    if not _is_negated(statement, m.start()):
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                continue
            if rule["control_code"] in seen_codes:
                continue
            seen_codes.add(rule["control_code"])
            fid = _finding_id(unit_id, rule["key"], statement)
            out.append({
                "finding_id": fid,
                "control_code": rule["control_code"],
                "severity": rule["severity"],
                # ★ quote 存观察原文（截断）：复核时人要能对着图上那一块看。
                "quote": statement[:200],
                "location": None,
                "status": "candidate",
                "produced_by": PRODUCED_BY,
                "confirmed_by_rule_class": False,
                "authority_state": "untested",
                # ★ 这两个字段是**可追溯性**：报告里要说清「这条是机器从
                #   画面观察推出来的」，而不是「规则命中」。
                "derived_from_observation": {
                    "task": obs.get("task"),
                    "statement": statement[:80],
                },
                "fact_label": rule["label"],
                "fact_why": rule["why"],
            })
    return out
