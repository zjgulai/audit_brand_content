#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骨架评分引擎：在 291 条真实记录上跑 rules-v1.json。

★ 这个脚本存在的唯一理由是**让设计文档可以被证伪**。
  在此之前，`规范-审核规则库完整设计.md` 的 §2（三层结构）与 §4（严重等级）
  从未在任何真实数据上跑过 —— 没有任何东西能证明它对。

产出：
  1. 新引擎 vs 现行人工判定的混淆矩阵（precision / recall）—— §2 的核心检验
  2. 语种缺口量化 —— Q3 的答案
  3. 严重等级查表 vs 现行四档的差异 —— §4 的核心检验
  4. 盲区（CATCH-ALL 命中数）—— §5 的核心检验

用法：
  python3 score.py                 # 全量报告
  python3 score.py --audit-channel # 只看语种缺口
  python3 score.py --json          # 机器可读输出
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import severity as sev  # noqa: E402
import matcher as _m  # noqa: E402  ★ 匹配原语只此一份；本文件不再自己实现

RULES_PATH = HERE / "rules-v1.json"
RECORDS_PATH = HERE / "_data" / "records.json"
TREE_PATH = HERE / "topic-tree-v1.md"
PRODUCT_LINES_PATH = HERE / "product-lines-v1.json"

# 合法主题节点：从 topic-tree-v1.md 抽取，防止 rules-v1.json 写出树上没有的节点
TREE_NODE_RE = re.compile(r"\*\*(T\d(?:\.\d){0,2})\*\*")


def _load_product_lines() -> tuple:
    """读品线表 → `(取值域 or None, 归属声明 dict)`。缺失返回 `(None, {})`，**不猜**。"""
    if not PRODUCT_LINES_PATH.exists():
        return None, {}
    try:
        doc = json.loads(PRODUCT_LINES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, {}
    vals = [v.get("value") for v in (doc.get("values") or []) if isinstance(v, dict)]
    domain = {v for v in vals if v} or None
    asg = {k: list(v) for k, v in (doc.get("assignments") or {}).items()
           if not str(k).startswith("$") and isinstance(v, list)}
    return domain, asg


# ---------------------------------------------------------------- 匹配
@dataclass
class Hit:
    rule_key: str
    parent_rule: str
    topic: str
    severity: str
    disposition: str
    matched: list = field(default_factory=list)
    matched_by: str = ""          # keyword | pattern
    downgraded: bool = False
    downgrade_terms: list = field(default_factory=list)
    escalated: bool = False
    escalation_reason: str = ""
    # ── 以下为产品化补齐（批次 A）。全部有默认值，旧调用点不受影响。────────────
    matches: list = field(default_factory=list)
    """★ 命中位置与原文片段：`list[matcher.Match]`。
    旧实现只留关键词（`_find_literal` 算出的区间被丢弃），导致下游拿 `matched`
    回原文搜会搜到不在原文里的串。见 matcher.py 模块说明。"""
    disposition_declared: str = ""
    """规则文件里声明的 disposition（**被改写前**）。与 `disposition` 不等即说明
    本次判定被豁免带改写 —— 这个差值必须留痕，否则「谁把红线改成放行」查不出来。"""
    band_kind: str = ""           # "" | "pass" | "downgrade"
    """命中的是**哪条带**。带的方向由规则自己声明（`downgrade_band.effect` 的箭头右侧），
    不是由代码猜 —— 见 `band_hits()`。"""
    band_effect: str = ""
    evaluability: str = ""
    """规则的 `evaluability`（auto / auto_then_manual / manual_only）。
    分层映射要用它：法务把某条规则声明为 `manual_only`，就等于说「机器在这条上不可采信」
    —— 命中它的判定必须升级到法务，而不是停在机器层。"""


def _cjk(ch: str) -> bool:                       # noqa: D103  （委托 matcher，避免第二份实现）
    return _m._cjk(ch)


def _is_wordish(ch: str) -> bool:                # noqa: D103
    return _m._is_wordish(ch)


def _find_literal(text_lower: str, term_lower: str):
    """兼容旧调用点（`audit_channel` 等按「已小写化的串」调用）。实现委托 matcher。"""
    return _m.find_literal(text_lower, term_lower)


def match_text(text: str, rule: dict):
    """返回 (命中词列表, 命中方式)。实现委托 matcher —— 本文件不再有第二份匹配逻辑。"""
    return _m.match_text(text, rule)


def find_matches(text: str, rule: dict):
    """★ 带位置与原文片段的命中。产品化契约用这个，不用 `match_text`。"""
    return _m.find_matches(text, rule)


def band_hits(text: str, rule: dict, vocab=None):
    """★ 修缺陷 1：**按规则自己声明的方向选带**，而不是一律去降级带找词。

    盘点实测（`引擎产品化-接口盘点.md` §四 缺陷 10/11）：
      `vocab.py:64-65` 提供 `pass_of()`，但**全仓无消费者**；`Engine.assess` 只调
      `downgrade_of()`。而 3 条 `target=auto_pass` 的规则（`T6.1.regulatory-status` /
      `T2.2.quiet-claim` / `T2.2.suction-claim`）的**降级带全是空的** —— 它们的词
      （`fda cleared` / `quiet mode` / `adjustable suction` …）落在 `pass_bands` 里。

      于是 `score.py:197-200` 那两条 `→ auto_pass` 分支**不可达**，而 `main()` 还在
      打印「放行带 8 词次」。看到这行极易以为放行在生效。

    ★ 修法不是「把 pass_of 接上」，是「**别让代码决定方向**」：
      `downgrade_band.effect` 的箭头右侧（`band_target()`）就是这条规则声明的落点。
      落点是 `auto_pass` → 去放行带取词；落点是 `manual_review` → 去降级带取词。
      方向是**规则里的一个字符串**，是法务定的语义（ADR-0008 §三分工表），不是实现细节。

    返回 `(带内命中词列表, effect 字符串, 带类型, list[Match])`。

    ★ 2026-09-16（D9）：**两个带都取，再定谁生效。**
      原来按规则级落点二选一 —— 于是「放行」与「降级」成了整条规则的属性，
      同一个带里的词不可能有不同的待遇。而 T6.1 的带里恰恰有两种语义强度的词：
      `cleared`（器械层 510(k) 状态）与 `registered`（企业/设施层注册）。
      逐词落点（`keyword_effect_overrides`）把粒度细到词之后，一条规则就可能
      **同时**有放行词与降级词，所以这里必须两个带都看。

      冲突时的取舍是**保守**：只要降级带命中就按降级算，哪怕同时有放行词。
      理由与 ADR-0005 同向 —— 方向不明时选后果更轻的那个（少发一条 < 违规上线）。
      代价写清：`FDA approved. FDA cleared. FDA registered.` 判 manual_review，
      尽管作者确实写出了 `cleared`。宁可多一次人工，不赌一次放行。

      返回的 `terms` 是**决定落点的那些词**；`Match` 列表则含两个带的全部证据 ——
      判定依据不该因为「谁赢了」而消失。
    """
    if vocab is None:
        raise SystemExit("❌ 豁免带必须由 vocab 提供（ADR-0009）；拒绝从规则文件读词表。")

    band = rule.get("downgrade_band") or {}
    default_eff = str(band.get("effect") or "none")
    rk = rule["rule_key"]

    def _scan(words):
        terms, ms = [], []
        for k in sorted(words):
            got = _m.find_literal_all(text, k)
            if got:
                terms.append(k)
                for s, e in got:
                    ms.append(_m.Match(k, "band", text[s:e], s, e))
        return terms, ms

    p_terms, p_ms = _scan(vocab.pass_of(rk))
    d_terms, d_ms = _scan(vocab.downgrade_of(rk))
    if not p_terms and not d_terms:
        return [], default_eff, "", []

    def _eff_for(word, kind):
        """按「通道 → 词」取逐词落点（D18 / 回答 Q12）。

        ★ 2026-09-16：键从「词」改成「词 + 通道」。理由不是洁癖 ——
          落点已经是三级（规则 → 词 → 表），而覆盖的键只有词，
          于是「同一个词在两个通道各有一条覆盖」只能靠 dict 的遍历次序决定，
          表现为**同样的输入两次跑出不同落点**。今天没有跨通道重复词（实测），
          所以这是把一个隐式的顺序依赖改成显式的结构约束，行为零变化。
        ★ 旧形状（值是字符串）**硬失败**而不是兼容：兼容意味着两套写法都活着，
          而两套都活着时，读代码的人无法判断哪一套在生效 —— 这正是本项目治过的病。
        """
        ov = band.get("keyword_effect_overrides") or {}
        for k, v in ov.items():
            if isinstance(v, str):
                raise SystemExit(
                    f"❌ {rk} 的 keyword_effect_overrides 还是旧形状（键=词、值=字符串）。\n"
                    f"   D18 之后必须是「通道 → 词 → 落点」的两层结构，例如：\n"
                    f'     "keyword_effect_overrides": {{"downgrade": {{"FDA registered": '
                    f'"auto_reject → manual_review"}}}}')
        lw = str(word).strip().lower()
        for k, v in (ov.get(kind) or {}).items():
            if str(k).strip().lower() == lw:
                return str(v).strip()
        return default_eff

    if d_terms:                       # 降级优先（保守）
        return d_terms, _eff_for(d_terms[0], "downgrade"), "downgrade", d_ms + p_ms
    # ★ 放行通道现在也查覆盖。今天没有放行通道的覆盖词，所以行为零变化；
    #   但键里既然有通道这一维，两个通道就该走同一条查表路径 —— 否则那一维是装饰。
    return p_terms, _eff_for(p_terms[0], "pass") if p_terms else default_eff, "pass", p_ms


def in_downgrade_band(text: str, rule: dict, vocab=None):
    """兼容旧签名：只回 `(词列表, effect)`，丢掉位置。新代码用 `band_hits()`。"""
    terms, eff, _kind, _ms = band_hits(text, rule, vocab)
    return terms, eff


# ---------------------------------------------------------------- 引擎
class Engine:
    def __init__(self, rules_doc: dict, vocab=None):
        if vocab is None:
            raise SystemExit("❌ Engine 需要 vocab（ADR-0009）：词表来自独立表，不来自规则文件。")
        self.vocab = vocab
        # ★ 先查「两处真相」，再复制。查的是**传进来的原始文档**，因为下面会深一层复制 ——
        #   第一版直接原地改 rules_doc 里的规则对象，于是同一个 doc 建第二个 Engine 时
        #   会看到上一个 Engine 写进去的 product_lines 而误报「两处真相」。
        #   即：守卫本身成了顺序相关的隐藏状态。复制 + 在原始文档上查，两个问题一起消掉。
        self._reject_stray_line_declarations(rules_doc)
        # is_modifier 的规则不产生命中（见 rules-v1.json 的 $is_modifier_note）
        self.all_rules = [dict(r) for r in rules_doc["rules"] if r.get("enabled", True)]
        self.rules = [r for r in self.all_rules if not r.get("is_modifier")]
        self.modifiers = [r for r in self.all_rules if r.get("is_modifier")]
        self.disabled = [r for r in rules_doc["rules"] if not r.get("enabled", True)]
        self.catch_all = rules_doc["catch_all"]
        # 品线取值域。**可选**：缺文件时 line_domain=None（= 取值域未知），
        # 判定照常进行，但边界声明会写明「未按品线过滤」。不硬失败的理由：
        # 没有声明 product_lines 的部署里，这份表对判定没有任何影响，
        # 强制要求它存在只会让「跑判定」多一个无谓的前置条件。
        self.line_domain, self.line_assignments = _load_product_lines()
        self._apply_line_assignments()
        self._validate_topics()

    @staticmethod
    def _reject_stray_line_declarations(rules_doc: dict):
        """`product_lines` 只允许写在 `product-lines-v1.json` 的 `assignments` 里。

        ★ 为什么归属写在品线表、而不是写在规则文件里（2026-09-16 决定）：

          两个位置都能写 = 两处真相。本项目已经因为「同一件事两份实现/两份来源」
          出过三次事（`安全词` 与 `检测关键词` 同字段、匹配原语两份、白名单两条导入路径）。
          品线归属的 Owner 是**产品**，规则语义的 Owner 是**法务** ——
          让两个 Owner 改同一个 1269 行的文件，就是在制造第 4 次。

          所以规则文件里出现 `product_lines` 时**硬失败**并指出该写在哪，
          而不是让其中一处默默生效（那样两个人都以为自己的改动生效了）。
        """
        stray = [r["rule_key"] for r in rules_doc.get("rules", []) if r.get("product_lines")]
        if stray:
            raise SystemExit(
                "❌ rules-v1.json 里有规则声明了 `product_lines`：" + ", ".join(stray)
                + "\n   品线归属**只在** product-lines-v1.json 的 `assignments` 里写"
                  "（成员：产品）。\n   两个位置都能写 = 两处真相；把这条挪过去即可。")

    def _apply_line_assignments(self):
        """把 `product-lines-v1.json` 的归属声明**灌进**本引擎自己的规则副本。"""
        if not self.line_assignments:
            return
        by_key = {r["rule_key"]: r for r in self.all_rules}
        bad = [k for k in self.line_assignments if k not in by_key]
        if bad:
            raise SystemExit("❌ product-lines-v1.json 的 assignments 指向不存在的规则："
                             + ", ".join(bad))
        for rk, lines in self.line_assignments.items():
            by_key[rk]["product_lines"] = list(lines)

    def _validate_topics(self):
        """rules-v1.json 的 topic 必须都在 topic-tree-v1.md 里。不静默。"""
        tree_text = TREE_PATH.read_text(encoding="utf-8")
        nodes = set(TREE_NODE_RE.findall(tree_text))
        bad = []
        for r in self.all_rules:
            top = r["topic"]
            # T9 / L0 这类主题级挂载允许等于一级节点
            if top not in nodes and not any(n.startswith(top + ".") for n in nodes):
                bad.append((r["rule_key"], top))
        # rule_key 的主题段必须与 topic 一致（防止改名漂移）
        drift = []
        for r in self.all_rules:
            key_topic = ".".join(r["rule_key"].split(".")[:2])
            if not r["topic"].startswith(key_topic.split(".")[0]):
                continue
            if r["topic"] != r["rule_key"].rsplit(".", 1)[0] and not r["topic"].startswith(
                    ".".join(r["rule_key"].split(".")[:2])):
                drift.append((r["rule_key"], r["topic"]))
        if drift:
            print("✗ rule_key 的主题段与 topic 字段不一致（改名漂移）：", file=sys.stderr)
            for k, t in drift:
                print(f"    {k} → topic={t}", file=sys.stderr)
            raise SystemExit(3)

        if bad:
            print("✗ 规则引用了主题树上不存在的节点：", file=sys.stderr)
            for k, t in bad:
                print(f"    {k} → {t}", file=sys.stderr)
            print(f"  树上实际有 {len(nodes)} 个节点", file=sys.stderr)
            raise SystemExit(2)
        self.tree_nodes = nodes

    def rules_for(self, product_line: str | None) -> list:
        """按品线过滤规则。

        ★ 一个必须说清的现状：**26 条规则里没有一条声明过品线**（字段清单已核）。
          所以今天传任何 `product_line`，本函数返回的都是全集 —— 过滤"不生效"。

          那为什么还要写它？因为「不生效」有两种，长得一样但完全不同：

            (a) 机制不存在 —— 没有品线这个概念，永远不可能生效；
            (b) 机制存在、数据没填 —— 法务/产品一旦给规则加上 `product_lines`，立刻就生效。

          第一版是 (a)。(a) 的危险在于：**下游会以为「传了品线 = 判得更准」**，
          而实际上什么都没发生，且没有任何东西会提示他。

          现在是 (b)，并且 `judge()` 会在边界声明里逐字写明当前处于哪种状态、
          被过滤掉了几条。**「不支持」和「支持但你没填」必须由调用方看得见地分开。**

        规则侧的声明口径（留给产品，见 product-lines-v1.json）：
          - 不写 `product_lines`，或写成空数组 → **适用全部品线**（默认，向后兼容）
          - 写成 `["吸奶器", "暖奶器"]` → 只对这些品线生效

        ★ 2026-09-16 加的一道硬防护（决定 D4 的直接后果）：
          **传入的品线不在取值域内时，不过滤。**
          否则一个错字（`"吸奶器 "` 带尾空格）会让所有声明了品线的规则静默消失 ——
          拼写错误变成大规模漏报。宁可不过滤（判得多），也不能静默少判（判得少）。
          详见 `product-lines-v1.json` 的 `$unknown_value_policy`。
        """
        if product_line is None:
            return self.rules
        if not self.line_value_known(product_line):
            return self.rules
        keep = []
        for r in self.rules:
            declared = r.get("product_lines") or []
            if not declared or product_line in declared:
                keep.append(r)
        return keep

    # ------------------------------------------------------------ 品线取值域
    def line_value_known(self, product_line) -> bool:
        """传入的品线是否在取知域内。取值域未知（没有表）时一律返回 True。

        「未知取值域」与「已知取值域但不含此值」必须分开：
        前者是缺数据（不该因此改变判定），后者才是拼写/口径错误（该提示）。
        把两者合并成 `False` 会让「还没建表」变成「所有品线都不过滤」或反之。
        """
        if self.line_domain is None:
            return True
        return product_line in self.line_domain

    def unknown_declared_lines(self) -> list:
        """规则声明了、但不在取值域内的品线值。**这是漏报的成因，必须显形。**"""
        if self.line_domain is None:
            return []
        out = []
        for r in self.rules:
            for v in r.get("product_lines") or []:
                if v not in self.line_domain:
                    out.append({"rule_key": r["rule_key"], "declared": v})
        return out

    def line_filter(self, product_line: str | None) -> dict:
        """品线过滤的**可复核报告**（纯函数，不依赖上一次调用的状态）。

        ★ 为什么不复用 `rules_for()` 的返回值反推：那需要引擎记住「上次为什么这么滤」，
          于是判定变得依赖调用顺序 —— 同一个输入在不同顺序下给出不同边界声明。
          这里重算一遍，代价是几十次列表比较，换来的是**无隐藏状态**。
        """
        n_all = len(self.rules)
        declared_rules = [r["rule_key"] for r in self.rules if r.get("product_lines")]
        rep = {
            "product_line": product_line,
            "domain_known": self.line_domain is not None,
            "domain_size": len(self.line_domain) if self.line_domain is not None else None,
            "value_verified": self.line_value_known(product_line) if product_line else None,
            "rules_total": n_all,
            "rules_declaring_product_lines": len(declared_rules),
            "applied": False,
            "filtered_out": 0,
            "reason": "",
            "unknown_declared": self.unknown_declared_lines(),
        }
        if product_line is None:
            rep["reason"] = "未传品线 → 不过滤（与旧版行为一致）"
            return rep
        if self.line_domain is None:
            rep["reason"] = ("品线取值域未知（找不到 product-lines-v1.json）→ **不过滤**。"
                             "规则若声明了品线，本次判定不会按品线收窄。")
            return rep
        if not self.line_value_known(product_line):
            rep["reason"] = (f"传入的品线 {product_line!r} **不在取值域内** → **不过滤**"
                             f"（取值域 {rep['domain_size']} 项）。"
                             f"这是拼写或口径不一致的信号；按未知值过滤会让声明了品线的规则"
                             f"静默消失，那是一次没有提示的漏报。")
            return rep
        if not declared_rules:
            rep["reason"] = (f"取值域已确认（{rep['domain_size']} 项），但**没有任何规则声明品线**"
                             f" → 过滤不生效。这是「支持但数据没填」，不是「不支持」："
                             f"给某条规则加上 product_lines 后立刻生效。")
            return rep
        rep["filtered_out"] = n_all - len(self.rules_for(product_line))
        rep["applied"] = rep["filtered_out"] > 0
        rep["reason"] = (f"{len(declared_rules)}/{n_all} 条规则声明了品线；"
                         f"本次过滤掉 {rep['filtered_out']} 条。未声明品线的规则视为适用全部品线。")
        return rep

    def assess(self, text: str, product_line: str | None = None):
        """返回 (hits, catch_all_triggered)

        ★ 与旧版的**唯一**行为差异：豁免带现在按规则自己声明的方向选取
        （`band_hits()`），因此 3 条 `target=auto_pass` 的规则终于会走放行带。
        命中/不命中的判定逐字未变。

        `product_line` 缺省为 None —— 此时不过滤，行为与旧版完全一致
        （291 条存量语料因此零回归）。
        """
        hits = []
        for r in self.rules_for(product_line):
            # ★ Q25 = 选项 A（2026-09-23）：**非主张词形逐规则遮罩** —— 见 `matcher.mask_non_claims()`。
            #   它治的是「不该让规则因这个词形而命中」：`treat yourself` 命中的不是疗效主张，是裸 `treat`。
            #   `non_claims` 为空时逐字返回原文本 —— 行为与改动前**完全一致**。
            ms, how = find_matches(
                _m.mask_non_claims(text, r["rule_key"],
                                   getattr(self.vocab, "non_claims", None)), r)
            if not ms:
                continue
            keys, seen = [], set()
            for m in ms:
                if m.keyword not in seen:
                    seen.add(m.keyword)
                    keys.append(m.keyword)

            band_terms, dg_effect, band_kind, band_ms = band_hits(text, r, self.vocab)
            h = Hit(
                rule_key=r["rule_key"], parent_rule=r["parent_rule"], topic=r["topic"],
                severity=r["severity"], disposition=r["disposition"],
                matched=keys, matched_by=how,
                matches=ms + band_ms,
                disposition_declared=r["disposition"],
                band_kind=band_kind, band_effect=dg_effect,
                evaluability=r.get("evaluability", ""),
            )
            if band_terms:
                h.downgraded = band_kind == "downgrade"
                h.downgrade_terms = band_terms
                # ★ 落点由规则自己声明（`effect` 的箭头右侧），不由代码硬编码三条字符串。
                #   这正是 ADR-0008 §三 分工表里「降级后的处置等级 ✅ 法务定义」的落地：
                #   法务改一个字符串就能改处置，不需要开发者改代码。
                # ★ 2026-09-16（D9）：落点从 `dg_effect`（**生效的那个词的** effect）取，
                #   不再从 `band_target(r)`（规则默认 effect）取。差别就是
                #   `FDA registered` 生效时落 manual_review、`FDA cleared` 生效时落 auto_pass ——
                #   若这里仍读规则默认值，逐词覆盖会被这一行无声抹掉。
                from vocab import landing_of
                landing = landing_of(dg_effect)
                if landing in ("auto_pass", "manual_review", "auto_reject",
                               "auto_pass_with_note"):
                    h.disposition = landing
            hits.append(h)

        # 升级逻辑（U04 → H01/H07 的共现规则，原表只是文字）
        self._apply_escalation(text, hits)

        return hits, len(hits) == 0

    def _apply_escalation(self, text: str, hits: list):
        for h in hits:
            src = next((r for r in self.rules if r["rule_key"] == h.rule_key), None)
            if not src or "escalation" not in src:
                continue
            esc = src["escalation"]
            for other in hits:
                if other.rule_key in esc["when_cooccurring_with"]:
                    h.escalated = True
                    h.severity = esc["to_severity"]
                    h.disposition = esc["to_disposition"]
                    h.escalation_reason = esc["reason"]


# ---------------------------------------------------------------- 载入
def load():
    from vocab import load_vocab, assert_channels
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    recs = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    V = load_vocab()
    assert_channels(V)          # ★ 使用点硬断言：违反即 exit 3，不降级为警告
    return rules, recs, V


def rec_text(r: dict) -> str:
    return " | ".join(x for x in [r.get("Primary Text", ""), r.get("Headline", "")] if x)


# ---------------------------------------------------------------- 报告
def report(engine: Engine, recs: list, as_json: bool = False):
    out = {}

    # ---- 1. 新引擎 vs 现行人工判定 ----
    tp = fp = fn = tn = 0
    per_rule = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    catch_all_n = 0
    new_hits_total = 0

    rows = []
    for r in recs:
        text = rec_text(r)
        hits, is_catch_all = engine.assess(text)
        new_rules = {h.parent_rule for h in hits}
        legacy_rules = set(r["_hit_rules"])
        if is_catch_all:
            catch_all_n += 1
        new_hits_total += len(hits)

        both = new_rules & legacy_rules
        only_new = new_rules - legacy_rules
        only_legacy = legacy_rules - new_rules

        if new_rules and legacy_rules:
            tp += len(both); fp += len(only_new); fn += len(only_legacy)
        elif new_rules and not legacy_rules:
            fp += len(new_rules)
        elif legacy_rules and not new_rules:
            fn += len(legacy_rules)
        else:
            tn += 1

        for k in both: per_rule[k]["tp"] += 1
        for k in only_new: per_rule[k]["fp"] += 1
        for k in only_legacy: per_rule[k]["fn"] += 1

        rows.append({
            "id": r.get("外部广告ID", ""),
            "lang": r.get("文案语种", ""),
            "legacy": sorted(legacy_rules),
            "new": sorted(new_rules),
            "catch_all": is_catch_all,
        })

    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0

    out["headline"] = {
        "记录数": len(recs),
        "新引擎命中规则次": new_hits_total,
        "现行命中规则次": sum(len(r["_hit_rules"]) for r in recs),
        "precision": round(P, 4), "recall": round(R, 4), "f1": round(F1, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "CATCH_ALL命中": catch_all_n,
        "CATCH_ALL率": round(catch_all_n / len(recs), 4),
    }

    # ---- 2. 语种缺口 ----
    langstat = defaultdict(lambda: {"n": 0, "legacy_hit": 0, "new_hit": 0})
    for r in recs:
        lg = r.get("文案语种") or "(空)"
        langstat[lg]["n"] += 1
        if r["_hit_rules"]:
            langstat[lg]["legacy_hit"] += 1
        if any(True for _ in []):
            pass
    for row in rows:
        lg = row["lang"] or "(空)"
        if row["new"]:
            langstat[lg]["new_hit"] += 1
    out["by_language"] = {k: dict(v) for k, v in langstat.items()}

    # ---- 3. 严重等级差异 ----
    sev_diff = Counter()
    sev_rows = []
    for r in recs:
        hits, is_catch_all = engine.assess(rec_text(r))
        if not hits:
            continue
        worst = max(hits, key=lambda h: sev.IMPACT_TO_RANK[sev.SEVERITY_TO_IMPACT[h.severity]])
        exp = sev.Exposure(reach=int(r["_impr"]) if r["_impr"] else None)
        res = sev.assess(worst.severity, exp)
        legacy = r.get("风险等级", "")
        sev_diff[(worst.severity, res.risk_level, legacy)] += 1
        sev_rows.append({
            "id": r.get("外部广告ID", ""), "severity": worst.severity,
            "likelihood": res.likelihood, "risk_level": res.risk_level,
            "legacy": legacy, "spend": r["_spend"], "reach": exp.reach,
        })
    out["severity"] = {
        "样本（有命中）": len(sev_rows),
        "查表结果分布": dict(Counter(x["risk_level"] for x in sev_rows)),
        "现行等级分布": dict(Counter(x["legacy"] for x in sev_rows)),
    }

    # ---- 4. 规则级明细 ----
    out["per_rule"] = {
        k: {**v, "precision": round(v["tp"] / (v["tp"] + v["fp"]), 3) if v["tp"] + v["fp"] else None,
            "recall": round(v["tp"] / (v["tp"] + v["fn"]), 3) if v["tp"] + v["fn"] else None}
        for k, v in sorted(per_rule.items(), key=lambda kv: -(kv[1]["tp"] + kv[1]["fn"]))
    }

    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return out

    # ---- 打印 ----
    h = out["headline"]
    print("=" * 68)
    print("骨架评分引擎 · 291 条真实记录")
    print("=" * 68)
    print(f"  记录数              {h['记录数']}")
    print(f"  现行人工判定命中次   {h['现行命中规则次']}")
    print(f"  新引擎命中次         {h['新引擎命中规则次']}")
    print()
    print(f"  Precision  {h['precision']:.3f}   Recall  {h['recall']:.3f}   F1  {h['f1']:.3f}")
    print(f"  TP={h['tp']}  FP={h['fp']}  FN={h['fn']}  TN={h['tn']}")
    print()
    print(f"  ★ CATCH-ALL 命中 {h['CATCH_ALL命中']} 条（{h['CATCH_ALL率']*100:.1f}%）"
          f" —— 这些是**未覆盖**，不是合规")
    print()

    print("-" * 68)
    print("按语种：规则覆盖率")
    print("-" * 68)
    print(f"  {'语种':8s} {'记录':>5s} {'现行命中':>8s} {'新引擎命中':>10s}")
    for lg, v in sorted(out["by_language"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {lg:8s} {v['n']:5d} {v['legacy_hit']:8d} {v['new_hit']:10d}")
    print()

    print("-" * 68)
    print("按规则：新引擎 vs 现行")
    print("-" * 68)
    print(f"  {'规则':7s} {'TP':>4s} {'FP':>4s} {'FN':>4s} {'P':>6s} {'R':>6s}")
    for k, v in out["per_rule"].items():
        p = f"{v['precision']:.2f}" if v["precision"] is not None else "  -"
        rr = f"{v['recall']:.2f}" if v["recall"] is not None else "  -"
        print(f"  {k:7s} {v['tp']:4d} {v['fp']:4d} {v['fn']:4d} {p:>6s} {rr:>6s}")
    print()

    print("-" * 68)
    print("严重等级：查表结果 vs 现行四档")
    print("-" * 68)
    print(f"  样本（有命中）{out['severity']['样本（有命中）']}")
    print(f"  查表分布: {out['severity']['查表结果分布']}")
    print(f"  现行分布: {out['severity']['现行等级分布']}")
    print()
    return out


def audit_channel(engine: Engine, recs: list):
    """Q3 的直接答案：现行人工判定里有多少是规则本身复现不了的。"""
    print("=" * 68)
    print("语种缺口审计 —— 现行判定中，规则自己复现不了的部分")
    print("=" * 68)
    print()
    total_in = total_out = 0
    off_rules = defaultdict(set)
    for r in recs:
        for part in (r.get("命中片段", "") or "").split("/"):
            part = part.strip()
            if ":" not in part:
                continue
            rid, frag = part.split(":", 1)
            rid, frag = rid.strip(), frag.strip()
            if not frag:
                continue
            rule = next((x for x in engine.rules if x["parent_rule"] == rid), None)
            if rule is None:
                continue
            # ★ 委托 matcher，不在这里自己再写一遍匹配。
            #   旧实现在此处留了第二份实现（`_find_literal(tl, tl)` 恒真的死代码 +
            #   一条独立的 `re.search` 路径），意味着「什么叫命中」有两处定义。
            #   本项目已因「同一件事两份实现」出过两次事，这里是第三处的苗头。
            ok = bool(frag) and bool(find_matches(frag, rule)[0])
            if ok:
                total_in += 1
            else:
                total_out += 1
                off_rules[rid].add(frag)
    denom = total_in + total_out
    print(f"  现行命中片段总数        {denom}")
    print(f"  ✓ 规则可复现            {total_in}  ({total_in/denom*100:.1f}%)")
    print(f"  ✗ 规则无法复现（靠人工） {total_out}  ({total_out/denom*100:.1f}%)")
    print()
    print("  按规则拆解：")
    for rid, frags in sorted(off_rules.items(), key=lambda kv: -len(kv[1])):
        print(f"    {rid:6s} 规则外片段 {len(frags):2d} 个: {sorted(frags)}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-channel", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rules, recs, V = load()
    print("词表来源（ADR-0008/0009：三个来源物理分离）")
    for line in V.sources:
        print(f"  · {line}")
    print(f"  · 放行带 {sum(len(v) for v in V.pass_bands.values())} 词次 ｜ "
          f"降级带 {sum(len(v) for v in V.down_bands.values())} 词次")
    print()
    eng = Engine(rules, V)
    print(f"规则 {len(eng.rules)} 条产生命中 / {len(eng.modifiers)} 条为修饰符(不产生命中) / {len(eng.disabled)} 条停用"
          f"（停用: {[r['rule_key'] for r in eng.disabled]}）")
    print(f"主题树校验通过：{len(eng.tree_nodes)} 个节点")
    print()

    if a.audit_channel:
        audit_channel(eng, recs)
        return

    report(eng, recs, as_json=a.json)


if __name__ == "__main__":
    main()
