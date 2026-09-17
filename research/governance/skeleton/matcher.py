#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""matcher.py —— 匹配原语：**唯一一份**「关键词/正则 → 命中」的实现

★ 本模块存在的理由：命中位置（`position`）在旧实现里算出来又被丢掉。

  盘点实测（`引擎产品化-接口盘点.md` §1.4）：
      score.py:92   `_find_literal` 返回 `(i, i+len(term_lower))`
      score.py:101-102  `if _find_literal(...): found.append(kw)`   ← 区间在这里被扔
      score.py:110  `return [f"re:{pat}"], "pattern"`               ← 正则只回占位符

  后果有两个，都直接打到法务验证表的第一层「能否定位到具体位置」：
    1. 下游拿 `matched` 回原文搜会**搜到不在原文里的串**：实测输入
       `Painlessly pump…` → `matched=['painlessly','painless']`，原文只有
       `Painlessly`，多出的 `painless` 是**前缀匹配**的产物。
    2. 正则命中连片段都没有，只有一个 `re:<模式>` 占位符。

  ADR-0008 §四 把「逐字可核」写成硬约束：`fragment` 必须是**原文的连续子串**，
  判定时必须能 `assert fragment in original_text`。旧实现给不出这样的片段。

★ 为什么把匹配放进独立模块，而不是在 score.py 上打补丁：

  本项目已经因为「同一件事两份实现」出过两次事 ——
  `vocab.assert_channels` 与 `tools/offline_replay.assert_disjoint` 是 W1 的两份
  独立实现；`now` 与 `recent_messages` 是时间基准的两份实现（导致守衡把 11:12 说成 23:12）。
  `judge.py` 要在同一份匹配上叠加契约，就不能再抄一遍。**一个实现，两个视图。**
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------- 字符类
def _cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _is_wordish(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


# ---------------------------------------------------------------- 位置映射
def lower_offsets_align(text: str) -> bool:
    """`text.lower()` 与原文是否**等长**（即偏移可 1:1 映射）。

    绝大多数文本等长。会变长的例子：`'İ'.lower()` 是 2 个字符（i + 组合点）。
    一旦不等长，「用小写串的下标去切原文」就会**静默切错位置** ——
    这种错不会抛异常，只会给出一个看起来合理、实际错位的片段。
    所以这里不猜：不等长就走 `_span_in_original` 的兜底，兜底也失败就**报 `None`**。
    """
    return len(text.lower()) == len(text)


def _span_in_original(text: str, term_lower: str):
    """小写串偏移不可用时的兜底：直接在原文里做不区分大小写的字面搜索。

    返回原文坐标 `(start, end)`，失败返回 `None`（**不返回一个猜的位置**）。
    """
    try:
        m = re.search(re.escape(term_lower), text, re.IGNORECASE)
    except re.error:
        return None
    return (m.start(), m.end()) if m else None


# ---------------------------------------------------------------- 字面匹配
def find_literal_all(text: str, term_lower: str) -> list[tuple[int, int]]:
    """找字面子串的**全部**非重叠出现，返回 `[(start, end), …]`（原文坐标）。

    **前缀匹配**：关键词视为词干，允许其后有后缀。

    ★ 为什么是前缀而不是词边界：实测三处现行命中的失败全部由此产生 ——
        `schmerzfrei`  不匹配 `schmerzfreies`      （德语变格）
        `hospital`     不匹配 `hospitalière`        （法语阴性）
        `krankenhaus`  不匹配 `krankenhausqualität` （德语复合词，关键词是长词的前缀）
      强制词尾边界会同时漏掉这三类。关键词在规则库里本来就是**词干**，
      收全屈折形式不可行（德语一个名词可达十几个形式）。

    ★ 但**词首边界仍然要求**：否则 `treat` 会命中 `retreat`、`pain` 会命中 `Spain`。
    ★ 中文没有词边界概念，不做任何边界要求（否则 `缓解疼痛` 永远匹配不上）。
    """
    tl = text.lower()
    exact = len(tl) == len(text)
    out: list[tuple[int, int]] = []
    start = 0
    while True:
        i = tl.find(term_lower, start)
        if i < 0:
            break
        if i > 0:
            prev = tl[i - 1]
            if _is_wordish(prev) and not _cjk(prev):
                start = i + 1
                continue
        end = i + len(term_lower)
        if exact:
            out.append((i, end))
        else:
            # 小写串偏移不可信：用原文重新定位。定位失败则**跳过这一处**并留给
            # find_matches 记 position_missing —— 宁可少报位置，不可错报位置。
            sp = _span_in_original(text[i:], term_lower)
            if sp:
                out.append((i + sp[0], i + sp[1]))
        start = end
    return out


def find_literal(text_lower: str, term_lower: str):
    """兼容旧签名的单次匹配：**入参是已小写化的串**，返回首个 `(start, end)` 或 `None`。

    保留它是因为 `score.audit_channel` 等旧调用点按此签名使用；
    新代码请用 `find_literal_all(text, term)`（吃原文、给全部位置）。
    """
    i = text_lower.find(term_lower)
    while i >= 0:
        if i == 0 or not (_is_wordish(text_lower[i - 1]) and not _cjk(text_lower[i - 1])):
            return (i, i + len(term_lower))
        i = text_lower.find(term_lower, i + 1)
    return None


# ---------------------------------------------------------------- 命中记录
@dataclass
class Match:
    """一处命中。`text` 恒为**原文的连续子串**（ADR-0008 §四 的逐字可核）。"""

    keyword: str                 # 规则里的词干（可能与原文写法不同 —— 这正是前缀匹配的目的）
    via: str                     # "keyword" | "pattern"
    text: str                    # ★ 原文片段，可 assert match.text in source_text
    start: int | None            # ★ 原文坐标；None = 有匹配但定位失败（原因见 reason）
    end: int | None
    reason: str = ""             # start is None 时的成因，不空着

    @property
    def position(self) -> dict:
        if self.start is None:
            return {"start": None, "end": None, "located": False, "reason": self.reason}
        return {"start": self.start, "end": self.end, "located": True}

    def as_dict(self) -> dict:
        d = {
            "matched_keyword": self.keyword,
            "matched_by": self.via,
            "matched_text": self.text,
            "position": self.position,
        }
        if self.reason:
            d["locate_failure"] = self.reason
        return d


def _locate(text: str, term_lower: str, kw_for_log: str, via: str,
            spans: list[tuple[int, int]], why: str) -> list[Match]:
    out = []
    for s, e in spans:
        frag = text[s:e]
        # 不变量：片段必须真的是原文子串。这条断言不依赖上面的偏移推导是否正确 ——
        # 它是**独立**的核验，所以能抓住偏移算错的情况。
        if frag.lower() != term_lower:
            out.append(Match(kw_for_log, via, frag, None, None,
                             reason=f"偏移校验失败：切出 {frag!r} 与词干 {term_lower!r} 不符"))
            continue
        out.append(Match(kw_for_log, via, frag, s, e))
    if not out:
        out.append(Match(kw_for_log, via, "", None, None, reason=why))
    return out


def find_matches(text: str, rule: dict) -> tuple[list[Match], str]:
    """返回 `(命中列表, 命中方式)`。关键词与正则是 OR 关系（与现行表一致）。

    与旧 `match_text` 的差别只有一处：**位置被保留了**。
    命中/不命中的判定逐字未变 —— 所以 `score.py` 的混淆矩阵不会因为本模块而改变。
    """
    tl = text.lower()
    exact = len(tl) == len(text)
    out: list[Match] = []

    for kw in rule["match"].get("keywords", []):
        term = kw.lower()
        spans = find_literal_all(text, term)
        if spans:
            out.extend(_locate(text, term, kw, "keyword", spans,
                               "" if exact else "大小写折叠改变长度且原文回搜失败"))
    if out:
        return out, "keyword"

    for pat in rule["match"].get("patterns", []):
        try:
            ms = list(re.finditer(pat, text, re.I))
        except re.error as e:
            raise SystemExit(f"规则 {rule['rule_key']} 的正则非法: {pat!r} → {e}")
        if ms:
            # 旧实现只报第一个匹配的模式名（占位符）；这里保留占位符语义 *并* 补上真实片段。
            out.append(Match(f"re:{pat}", "pattern", ms[0].group(0), ms[0].start(), ms[0].end()))
            for m in ms[1:]:
                if m.group(0) != ms[0].group(0) or m.start() != ms[0].start():
                    out.append(Match(f"re:{pat}", "pattern", m.group(0), m.start(), m.end()))
            return out, "pattern"

    return [], ""


def match_text(text: str, rule: dict):
    """`find_matches` 的**投影**：只回关键词列表 + 方式，供旧调用点使用。

    保留它是为了不改变 `score.py` 的既有输出（该输出已被 ADR 引用为基线）。
    新代码一律用 `find_matches`。
    """
    ms, how = find_matches(text, rule)
    if how == "pattern":
        return [ms[0].keyword], how
    seen, keys = set(), []
    for m in ms:
        if m.keyword not in seen:
            seen.add(m.keyword)
            keys.append(m.keyword)
    return keys, how
