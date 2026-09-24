#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judge.py —— 判定引擎的**稳定契约**（批次 A 的产品化入口）

一句话：`judge(text, product_line=…) -> 一份可复核、可追溯、带边界声明的判定结果。`

★ 为什么需要它（盘点 §1.7 的结论）：

  `Engine.assess()` **本身已经是纯文本函数**（`score.py:179` 签名就是
  `def assess(self, text: str)`），绑死快照记录的是 `report()`/`rec_text()`，不是引擎。
  所以产品化的瓶颈**不在数据源解耦，在输出契约** —— 今天要判定一段新文案，
  必须自己写胶水，且拿到的东西缺六样：

    #  缺什么            盘点依据
    1  position           `Hit` 11 个字段无位置；`_find_literal` 算出 (i, i+len) 被丢弃
    2  matched_text       `matched` 存关键词；正则只回占位符 `re:<pat>`
    3  verdict            `assess` 返回 (list[Hit], bool)，bool 仅表示「零命中」
    4  rule_version       三份 JSON 只有 `$schema_version`（结构版本名，非内容版本）
    5  vocabulary_version 同上
    6  boundary_statement ADR-0005 约束 1 要求 `unknowns` 且不允许为空数组

★ 三条不越界的约束（本文件按它们写，不是事后补的）：

  1. **工具只补证据，不替人过门**（ADR-0005）。
     `suggestion` 是建议不是决定；`auto_pass` 的措辞是「机器无拦截理由」，
     **不是**「判定通过」。机器无权把任何状态写成「无需处理」。
  2. **未命中 ≠ 合规**（ADR-0004/0005 约束 3）。
     零命中时 `suggestion` 只能是「转人工」，且 `unknowns` 必须写明覆盖率不足。
     落进 CATCH-ALL 的记录**不进「合规」桶**，进**规则空白**桶。
  3. **逐字可核**（ADR-0008 §四）。
     每个 `matched_text` 都是原文的连续子串，且 `fragment in source_text` 可断言。
     核验口径（词干 / 前缀匹配）由法务定，本实现只执行、不复述。

用法：
  from judge import judge
  r = judge("FDA approved wearable breast pump", product_line="吸奶器")
  r["verdict"]["disposition"], r["verdict"]["layer"]["name"]

命令行：
  python3 judge.py --text "文案…" [--product-line 吸奶器] [--receipt] [--json]
  echo "文案…" | python3 judge.py --stdin [--json]
  python3 judge.py --batch _data/records.json --json     # 批量（不写回执）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import clause_ref as CR  # noqa: E402  T4：回执 → 条款 → 原文（证据引用）
import engine_manifest as manifest  # noqa: E402
import evidence_origin as EO  # noqa: E402  T19：证据来源四档 + PASS 收窄
import score as S  # noqa: E402
import severity as sev  # noqa: E402
from vocab import load_vocab, assert_channels, band_target  # noqa: E402

CONTRACT_VERSION = "judge-v1"
LAYERS_PATH = HERE / "disposition-layers-v1.json"
RECEIPTS_PATH = HERE / "_data" / "receipts.jsonl"

# ★ 处置的**从严到宽**次序。聚合时取最严的一条。
#   依据：这四档是规则文件里的既有取值（11 auto_reject / 12 manual_review /
#   1 auto_pass_with_note / 1 auto_pass），次序与 ADR-0005「默认不通过」一致。
DISPOSITION_PRECEDENCE = ["auto_reject", "manual_review", "auto_pass_with_note", "auto_pass"]
# T19：这两个是「直接发布」档 —— 证据来源收窄**只**作用在它们身上。
#   单独定义在这里是为了让「收窄作用域」只有一处定义，而不是散在条件里。
PASS_DISPOSITIONS = ("auto_pass", "auto_pass_with_note")

# ADR-0005 约束 1 的三值建议（**建议**，不是决定）
SUGGESTION_BY_DISPOSITION = {
    "auto_reject": "需修改",
    "manual_review": "转人工",
    "auto_pass_with_note": "直接发布",
    "auto_pass": "直接发布",
}
SUGGESTION_ON_NO_MATCH = "转人工"      # ★ ADR-0005 约束 3：不得是「直接发布」


# ---------------------------------------------------------------- 版本与指纹
def versions() -> dict:
    """规则与词表版本。**每一个判定都必须带上它** —— 否则答不了「这是哪版算的」。

    `rule_version` 与 `vocab_version` 由 `engine_manifest` 的制品指纹派生，
    不是手写的字符串：手写的版本号在第一次忘记改的时候就开始撒谎。
    """
    h = manifest.artifact_hashes()
    m = manifest.load_manifest()
    vocab_seed = f"whitelist:{h['whitelist']}\ncontext_guards:{h['context_guards']}"
    return {
        "engine_version": m["engine_version"],
        # ★ ADR-0005 约束 5 把回执字段列成 `rule_snapshot_sha256` **与** `agent_version`
        #   两项。前者=数据（engine_version），后者=代码（code_version）。
        #   只做前者的话，改一行契约代码，回执仍会指向同一个版本号 —— 那它就没证明力。
        "code_version": m.get("code_version"),
        "rule_version": "rules@" + h["rules"][:12],
        "vocab_version": "vocab@" + hashlib.sha256(vocab_seed.encode()).hexdigest()[:12],
        # ★ 处置分层映射必须有自己的版本号：它决定 `verdict.layer`（谁必须看它），
        #   而 `verdict_digest` 只证明「结论不同」，证明不了「哪张表改的」。
        #   法务改一次分层表，若版本号不动，旧回执就无法被解析回当时的表。
        "layers_version": "layers@" + h["disposition_layers"][:12],
        "topic_tree_version": "tree@" + h["topic_tree"][:12],
        "manifest_generated_at": m.get("generated_at"),
        "contract_version": CONTRACT_VERSION,
    }


def load_layers() -> dict:
    if not LAYERS_PATH.exists():
        raise SystemExit(f"❌ 找不到分层映射表 {LAYERS_PATH.name}。"
                         "判定结果必须能回答「谁处置它」——没有这张表就答不了。")
    return json.loads(LAYERS_PATH.read_text(encoding="utf-8"))


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 未接线守卫
_UNWIRED = None


def unwired_guards() -> list[dict]:
    """`status != active` 的语境守卫 —— 它们**今天不产生任何降级效果**。

    ★ 为什么要把它们单独拿出来算：盘点实测第 3 件「最容易搞错的事」——

        输入 `"… does not treat any disease"` → T1.1 `manual_review`，`downgraded=True`
        输入 `"… does not cure  any disease"` → T1.1 `auto_reject`，`downgraded=False`

      差一个词，从「降级」变成「红线」。原因不是规则错，是 `does not cure` 在
      `context-guards-v1.json` 里是 `status=pending` / `wired=false`，而 `cannot cure`
      是 active。**词表里有这个词 ≠ 它在生效。**

      对法务来说，「一条红线」和「一条本可以降级、因为词形没补全而成了红线」是
      **两个完全不同的问题**，处置也不同：前者要改文案，后者要补词表。
      旧输出把两者渲染成一模一样的一行 —— 差距就这样消失了。

    本函数让这个差距以**具名词条**的形式出现在判定结果里。
    """
    global _UNWIRED
    if _UNWIRED is None:
        doc = json.loads((HERE / "context-guards-v1.json").read_text(encoding="utf-8"))
        _UNWIRED = [w for w in doc.get("words", []) if w.get("status") != "active"]
    return _UNWIRED


def near_miss_guards(text: str, rule_key: str) -> list[dict]:
    """本次文案里**出现了、但未接线**的守卫词 —— 即「若接线，本命中会被改写」。"""
    tl = text.lower()
    out = []
    for w in unwired_guards():
        if rule_key not in (w.get("downgrades") or []):
            continue
        if w["word"].strip().lower() in tl:
            out.append({
                "word": w["word"],
                "status": w.get("status"),
                "would_have_effect": w.get("effect") or "(未声明落点)",
                "wire_gap": w.get("wire_gap"),
                "status_note": w.get("status_note"),
            })
    return out


# ---------------------------------------------------------------- 引擎单例
_ENGINE = None


def engine() -> S.Engine:
    """进程内单例。构造即跑 `_validate_topics`（不通过 exit 2/3）与 `assert_channels`（exit 3）。"""
    global _ENGINE
    if _ENGINE is None:
        rules = json.loads((HERE / "rules-v1.json").read_text(encoding="utf-8"))
        V = load_vocab()
        assert_channels(V)
        _ENGINE = S.Engine(rules, V)
    return _ENGINE


# ---------------------------------------------------------------- 边界声明
def _boundary(eng: S.Engine, V, hits: list, product_line, locale) -> dict:
    """ADR-0005 约束 1：`unknowns` **不允许为空数组**。

    如果确实没有不确定项，也必须显式写「无 —— 但本判定未覆盖 X」。
    这条约束的目的不是让人写满，是**逼出覆盖边界**：一条说不出自己边界的判定，
    下游只能默认它哪儿都对。
    """
    n_guards = len(V.guards)
    n_all_guards = len(json.loads((HERE / "context-guards-v1.json").read_text())["words"])
    unwired = n_all_guards - n_guards
    disabled = [r["rule_key"] for r in eng.disabled]

    n_declared = sum(1 for r in eng.all_rules if r.get("product_lines"))
    n_filtered = len(eng.rules) - len(eng.rules_for(product_line))
    lf = eng.line_filter(product_line)
    if n_declared == 0:
        pl_note = (f"**品线维度尚未启用（机制已就绪、数据未填）**："
                   f"{len(eng.rules)} 条规则里**没有一条**声明 `product_lines`，"
                   f"所以传入的 product_line={product_line!r} 不产生任何过滤 —— "
                   f"它与不传是同一个结果。"
                   f"「本品线是否已被规则覆盖」这个问题，今天没有数据能回答。"
                   f"★ 这里是「支持但你还没填」，不是「不支持」："
                   f"产品给某条规则加上 `product_lines: [\"吸奶器\"]`，过滤立刻生效。")
    else:
        pl_note = (f"**品线维度已部分启用**：{n_declared}/{len(eng.all_rules)} 条规则声明了 "
                   f"`product_lines`；本次以 product_line={product_line!r} 过滤掉 "
                   f"{n_filtered} 条规则。**未声明品线的规则被视为「适用全部品线」** —— "
                   f"若某条规则实际只对特定品线成立却没声明，它会在别的品线上误报。")

    unknowns = [
        pl_note,
        f"**词表有未接线的部分**：语境守卫声明 {n_all_guards} 条，生效 {n_guards} 条，"
        f"{unwired} 条未接线（pending / misrouted）。未接线的守卫词**不会**产生降级 —— "
        f"同一个句式可能因为一个词没接线而从「降级」变成「红线」。",
        f"**停用规则不参与判定**：{[*disabled] or '无'}。语义相关的表达今天由 CATCH-ALL 兜底，"
        f"表现为「未覆盖」，不是「已检查且合规」。",
        "**L5 档从未被使用**：规则库现有严重等级只有 L0/L1/L2/L4，没有一条规则是 L5。"
        "`severity.py` 的 L5→Very High 映射因此**从未被真实数据触发过**。",
        "**未覆盖的载体**：本判定只看文本。图片、视频、落地页正文、A+ 详情页均不在输入内。"
        "批次 C 已产出落地页正文的获取能力，但**尚未接入本引擎**。",
        "**未覆盖的维度**：投放地区 / 平台政策差异不是规则维度。"
        "同一条英文文案在 US 与 DE 的合规结论可能不同，本判定给出的是同一个结果。",
        "**本引擎只在单一品线上被验证过**：291 条存量语料里 289 条品线=吸奶器、2 条为空。"
        "所以下面这份判定**在吸奶器以外的品线上从未被检验**，"
        "不知道它的误报率、也不知道词表覆盖是否成立。"
        "★ 已知的跨品线误报形态：`超强` / `静音` / `极致` 是各品线通用的营销词，"
        "「超强吸水」（家纺）与「超强吸力」（吸奶器）今天判的是同一条 `T2.2.suction-claim`。",
    ]

    # ── 品线：把「到底滤没滤、为什么没滤」逐字写出来 ────────────────
    if product_line:
        unknowns.append("**品线过滤实况**：" + lf["reason"])
    # ★ 2026-09-16（D16 实施时实测发现）：`$unknown_value_policy` 早就声明了
    #   「传入的品线不在取值域内 → 不过滤，并在边界声明里写明」，
    #   `Engine.line_value_known()` 也早就写好了这个区分（连注释都写了
    #   「未知取值域」与「已知取值域但不含此值」必须分开）——
    #   但 **`_boundary` 从来没有调用过它**。所以今天一个拼写错误
    #   （`吸奶器X`）与一个合法取值得到的边界声明**逐字相同**。
    #   这与 Q11（`within_chars` 声明了没人读）、Q7（风险描述从未被执行到）是同一种病：
    #   **能力写好了、文档写了、调用没接上。** 三类都只在「拿错字去试」时才显形。
    if product_line and not eng.line_value_known(product_line):
        unknowns.append(
            f"★★ **传入的品线 {product_line!r} 不在取值域内 —— 本次**未按品线过滤**。**"
            f"未知取值一律不过滤：若按「它不在任何规则的 product_lines 里」处理，"
            f"所有声明了品线的规则都会**静默消失** —— 一个拼写错误就变成一次大规模漏报。"
            f"取值域见 product-lines-v1.json（今天 {len(eng.line_domain or [])} 个取值，"
            f"其中只有「吸奶器」经产品确认）。")
    if lf["unknown_declared"]:
        unknowns.append(
            "★★ **有规则声明了不在取值域内的品线值 —— 这是漏报成因**："
            + "；".join(f"{x['rule_key']} 声明了 {x['declared']!r}"
                        for x in lf["unknown_declared"])
            + "。该值不会被任何传入品线命中，因此这条规则在这些品线上**静默不生效**。"
              "取值域见 product-lines-v1.json。")
    if not hits:
        unknowns.insert(0,
            "★ **本条零命中，不等于合规**（ADR-0005 约束 3）。它落进 CATCH-ALL 通道，"
            "含义是「规则库没有覆盖它」，不是「规则库检查过它」。"
            "零命中的成因至少有三种，本引擎**不区分**：新表达 / 新语种 / 规则边界不清。")
    if locale and locale not in ("en", "zh"):
        unknowns.append(
            f"**语种覆盖不均**：传入 locale={locale!r}。规则的多语种关键词覆盖以 en/zh 为主，"
            f"de/fr/es/pl 只有零星词条。非 en/zh 文案的零命中，更可能是词表缺口而非内容合规。")

    evals = {h.evaluability for h in hits} if hits else set()
    if not hits or "manual_only" in evals:
        confidence = "low"
    elif "auto_then_manual" in evals or "manual_only" in evals:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "coverage": ("hit" if hits else "no_rule_matched"),
        "confidence": confidence,
        "$confidence_basis": ("low = 零命中或含 manual_only 规则；"
                              "medium = 含 auto_then_manual；high = 全部 auto"),
        "rule_coverage": {
            "enabled_rules": len(eng.rules),
            "modifiers": len(eng.modifiers),
            "disabled": disabled,
            "guards_declared": n_all_guards,
            "guards_active": n_guards,
            "guards_unwired": unwired,
        },
        "unknowns": unknowns,
        "$unknowns_rule": "ADR-0005 约束 1：本数组不允许为空。它列的是「本判定判断不了什么」。",
        "not_covered_carriers": ["图片", "视频", "落地页正文", "A+ 详情页"],
    }


# ---------------------------------------------------------------- 分层映射
def _render_notice(tpl: str, ctx: dict) -> str:
    """把 `notice_template` 里的 `{key}` 用 ctx 填掉。

    ★ 未知占位符**不静默留着**，而是替换成 `(未提供:key)`：一条发出去的回执里
      留着 `{rule_keys}` 这种字面量，收件人会以为系统坏了；而如果直接把未知键
      悄悄删掉，就会出现「回执少了一句」这种没人能发现的信息缺失。
    """
    out = tpl
    for k, v in ctx.items():
        if isinstance(v, (list, tuple, set)):
            v = "、".join(str(x) for x in v) or "（无）"
        out = out.replace("{" + k + "}", str(v))
    import re as _re
    return _re.sub(r"\{([a-z_]+)\}", lambda m: f"(未提供:{m.group(1)})", out)


def _outbound(mp: dict, ctx: dict) -> dict | None:
    """出口声明 → 可发送的通知块。**没有出口声明就返回 None，不合成一个默认出口**。

    合成默认出口比没有出口更坏：它让「没人负责通知」看起来像「已经通知了」。
    """
    ob = mp.get("outbound")
    if not ob:
        return None
    return {
        "required": ob.get("required", False),
        "kind": ob.get("kind"),
        "to": ob.get("to"),
        "must_reach": ob.get("must_reach", False),
        "notice": _render_notice(ob.get("notice_template", ""), ctx),
        "must_not_say": ob.get("must_not_say", []),
        "appeal": ob.get("appeal"),
        "$why": ("★ `human_must_see` 说的是「拦截生效前要不要人看」，`must_reach` 说的是"
                 "「拦截之后提交人要不要知道」。两者今天事实上等价 —— 拦截即终结，"
                 "被误拦的人不知道、也无处说话（D10 补的是这一半）。"),
    }


def resolve_layer(disposition: str, hits: list, layers: dict, *,
                  has_text: bool = True, ctx: dict | None = None) -> dict:
    """`disposition` + 前置条件 + 升级条件 → 处置层。

    ★ 本函数**不硬编码任何层级名或落点**：全部读 `disposition-layers-v1.json`。
      法务改那张表即改处置，不需要开发者改代码（ADR-0008 §三分工表）。

    ★ 2026-09-16（D5）新增两个环节，次序是**前置条件 → 落点 → 升级**：

      `preconditions` 在升级之前判（`skips_escalation`），因为「有没有可判文本」
      是比「该不该升级」更靠前的问题 —— 一段没有文本的输入不属于任何主题，
      也就谈不上「跨主题共现」。若把次序反过来，无文案记录会先被升级规则捞走，
      于是 59 条空记录会顶着一条它们不满足的升级理由进 DP4。
    """
    ctx = dict(ctx or {})
    by_id = {l["id"]: l for l in layers["layers"]}
    escalated_by = []
    exemptions_applied = []
    pre_applied = None

    # ── 1. 前置条件（先于落点与升级）────────────────────────────────
    for pre in layers.get("preconditions", []):
        if not pre.get("$enabled"):
            continue
        if pre["id"] == "PRE-001" and not has_text:
            pre_applied = pre
            break

    # ── 2. 落点 ────────────────────────────────────────────────────
    mp = layers["mapping"].get(disposition)
    if mp is None:
        return {"id": None, "name": "（未在分层表中定义）", "who": None,
                "final_action": None, "machine_may_finalize": False,
                "human_must_see": True,
                "$error": f"disposition={disposition!r} 不在 {LAYERS_PATH.name} 的 mapping 里。"
                          f"这是**表缺行**，不是判定失败 —— 请法务补一行，不要让它静默放行。"}

    layer_id = mp["layer_id"]
    final_action = mp.get("final_action")
    enters_blank_register = bool(mp.get("enters_blank_register"))
    suggestion_override = None
    effective = mp

    if pre_applied:
        layer_id = pre_applied["layer_id"]
        final_action = pre_applied.get("final_action") or final_action
        enters_blank_register = bool(pre_applied.get("enters_blank_register"))
        suggestion_override = pre_applied.get("suggestion_override")
        # 出口用前置条件自己的；没有就退回 mapping 的（DP0 自带 coverage_notice）
        effective = {**mp, **({"outbound": pre_applied["outbound"]}
                              if pre_applied.get("outbound") else {})}

    # ── 3. 升级（前置条件声明跳过时不跑）────────────────────────────
    if not (pre_applied and pre_applied.get("skips_escalation")):
        for rule in layers.get("escalate_if", []):
            if not rule.get("$enabled"):
                continue
            eid = rule["id"]
            if eid == "ESC-001" and any(h.escalated for h in hits):
                layer_id = rule["to_layer_id"]
                escalated_by.append({"id": eid, "reason": rule["reason"],
                                     "evidence": [h.rule_key for h in hits if h.escalated]})
            elif eid == "ESC-002":
                # ★ 2026-09-16（D13 · 回答 Q7）：本条的判据是「规则自己声明机器不可采信」，
                #   但那是**规则级**声明，不等于「必须法务终审」—— 后者是处置决定。
                #   实测把两者绑在一起时，DP4 的 31 条 100% 由本条产生，其中 13 条原本是
                #   机器可独立拦截的（auto_reject）；即升级还**暂停了自动拦截**。
                #   现在允许逐规则声明例外（`exempt_rule_keys`），例外写在分层表里 ——
                #   仍然是法务/Owner 的所有物，不是代码里的名单。
                _ex = set(rule.get("exempt_rule_keys") or [])
                _esc = [h for h in hits
                        if h.evaluability == "manual_only" and h.rule_key not in _ex]
                _exempted = sorted({h.rule_key for h in hits
                                    if h.evaluability == "manual_only"
                                    and h.rule_key in _ex})
                if _esc:
                    layer_id = rule["to_layer_id"]
                    escalated_by.append({"id": eid, "reason": rule["reason"],
                                         "evidence": [h.rule_key for h in _esc]})
                if _exempted:
                    # ★ 例外必须显形。一次「什么都没发生」的例外，读结果的人
                    #   分不出它是「没命中」还是「命中了但被豁免」——那正是本项目反复在治的病。
                    exemptions_applied.append({
                        "id": eid, "rule_keys": _exempted,
                        "would_have_gone_to": rule["to_layer_id"],
                        "$why": ("这些规则声明了 manual_only，本应被升级；"
                                 "分层表为它们声明了例外（`exempt_rule_keys`），"
                                 "因此落回各自的原生层。"),
                        "$decision": rule.get("$exempt_decision"),
                    })
            elif eid == "ESC-003":
                tops = {".".join(h.topic.split(".")[:1]) for h in hits}
                if len(tops) >= 2:
                    layer_id = rule["to_layer_id"]
                    escalated_by.append({"id": eid, "reason": rule["reason"],
                                         "evidence": sorted(tops)})

    L = by_id.get(layer_id, {})
    ctx.setdefault("run_id", ctx.get("run_id") or "（本次判定未发回执）")
    return {
        "id": layer_id,
        "name": L.get("name"),
        "who": L.get("who"),
        "can_finalize": L.get("can_finalize"),
        "final_action": final_action,
        "machine_may_finalize": mp.get("machine_may_finalize"),
        "human_must_see": mp.get("human_must_see"),
        "escalated_by": escalated_by,
        "exemptions_applied": exemptions_applied,
        "precondition_applied": ({"id": pre_applied["id"], "flag": pre_applied.get("flag"),
                                  "reason": pre_applied.get("$why")} if pre_applied else None),
        "suggestion_override": suggestion_override,
        "blank_register": {
            "enters": enters_blank_register,
            "$why": ("落进空白清单 = 这条记录是**规则缺口的候选**，由 DP4 定期复审。"
                     "无文案记录不进：它不是「规则没覆盖」，是「没有东西可以覆盖」。"
                     if not enters_blank_register else
                     "落进空白清单 = 这条记录是**规则缺口的候选**，由 DP4 定期复审"
                     "（R8-W3 §3.2.4 ④：复审与规则生产必须分人）。"),
        },
        "outbound": _outbound(effective, ctx),
        "table_status": layers.get("status"),
        "$table_note": _layer_note(layers.get("status"), layers.get("decided_at"),
                                   layers.get("decided_by")),
        "$authority_scope": {
            "legal_confirmed": (layers.get("ratification_scope") or {}).get("legal_confirmed"),
            "owner_decided": (layers.get("ratification_scope") or {}).get("owner_decided"),
            "pending_legal_review": (layers.get("ratification_scope") or {}).get(
                "pending_legal_review"),
            "$why": ("★ 表级 status 只说「本表处于已确认状态」，**不说**「每个字都被法务看过」。"
                     "要问这一行谁定的，看 disposition-layers 里这一行的 `$decision`；"
                     "逐项归属由 V24 机检。"),
        },
    }


def _layer_note(status, decided_at, decided_by) -> str:
    """分层表的权威性说明。**随表的状态变** —— 一句写死的免责声明迟早会变成假话。

    第一版写死为「在法务确认前不得作为业务承诺引用」。2026-09-16 法务确认之后，
    这句话就反过来了：它不再是「未经确认」，而是**已确认** —— 此时还挂着旧免责，
    等于把一份已授权的处置映射说成草案，同样是在骗读它的人。
    """
    if status == "ratified":
        return (f"本行的层级落点来自 disposition-layers-v1.json，"
                f"该表已由{decided_by or '法务'}于 {decided_at or '（日期缺失）'} 逐条确认"
                f"（status=ratified）。★ 确认的是**该版本**：表一旦被改动，status 会退回 "
                f"proposed，本注也随之变回未确认。")
    return (f"本行的层级落点来自 disposition-layers-v1.json（status={status}）。"
            f"该表**尚未经法务确认**，不得作为业务承诺引用。")


# ---------------------------------------------------------------- 回执
def _rule_keys(verdict: dict) -> list:
    """从回执的入参里取「命中了哪几条规则」。

    ★ 这个入参叫 `verdict` 但它**装的是整份判定结果**（`verdict` 只是它下面的一个键）
      —— 落 T4 时我就是照着名字读、于是拿到一个空数组，而**没有任何东西会红**：
      `rule_keys_hit: []` 与「这条判定零命中」长得一模一样。
      所以这里两个位置都读，谁在都行（`receipt_evidence_problems()` 同理）。
    """
    if not isinstance(verdict, dict):
        return []
    inner = verdict.get("verdict")
    if isinstance(inner, dict) and inner.get("rule_keys_hit") is not None:
        return list(inner.get("rule_keys_hit") or [])
    return list(verdict.get("rule_keys_hit") or [])


def build_receipt(text: str, verdict: dict, vers: dict, *, issued_at: str,
                  run_id: str | None = None, origin: str = "cli",
                  evidence_origin: str = "stated",
                  evidence: dict | None = None,
                  obligations: dict | None = None) -> dict:
    """ADR-0005 约束 5：「**没有 receipt 的判定不算发生过。**」

    ★ 一个刻意的取舍：**回执里不存原文，也不存原文片段。**

      ADR-0008 决策 2 已定「RSA 完整素材不落库」。回执是**长期留存**的审计日志，
      往里面写广告原文等于用另一条路径把已决定不落库的东西落库了。
      所以回执只存 `input_sha256`：**有原文的人能验证，没原文的人拿不到。**

      代价必须说清：**光看回执无法还原当时判了什么**。要复核必须同时持有原文。
      这是「不落库」决策的直接代价，不是实现疏漏。

    ★ `origin` 的存在理由：**审计日志里必须分得出「测试」和「真判定」。**
      批次 A 实施时就踩到了 —— 开发期的验证调用把两条记录写进了正式账本，
      而账本当时没有任何字段能把它们标出来。事后才发现，说明字段本来就不够。
    """
    core = {
        "contract_version": vers["contract_version"],
        "origin": origin,
        # ★ 与上面那个 `origin` **不是一回事**（见 evidence_origin.py 抬头）。
        #   放在它正下方是刻意的：两个 origin 挨着，混淆的时候一眼能看见。
        "evidence_origin": evidence_origin,
        "input_sha256": _sha256(text),
        "input_chars": len(text),
        "engine_version": vers["engine_version"],
        "code_version": vers.get("code_version"),
        "rule_version": vers["rule_version"],
        "vocab_version": vers["vocab_version"],
        "layers_version": vers.get("layers_version"),
        "topic_tree_version": vers["topic_tree_version"],
        "verdict_digest": _sha256(json.dumps(verdict, ensure_ascii=False, sort_keys=True)),
        "issued_at": issued_at,
    }
    core["run_id"] = run_id or ("jr-" + core["input_sha256"][:10] + "-"
                                + hashlib.sha256(
                                    (core["input_sha256"] + core["engine_version"]
                                     + issued_at).encode()).hexdigest()[:8])
    core["$note"] = ("不含原文与片段（ADR-0008 决策 2）。"
                     "verdict_digest 把回执钉在**结论**上，不只是钉在输入上 —— "
                     "只记输入的回执无法证明当时判了什么。"
                     "origin 区分测试与真判定（cli / batch / shouheng）。"
                     "★ `evidence_ref[]` 是 T4 的那一跳：**回执 → 条款 → 原文**"
                     "（PRD §5.3）。它只存地址（库名/条目ID/条文号/链接/指纹）与"
                     "「怎么读到的」，仍不含任何原文片段。")

    # ── T4：回执 → 条款 → 原文（PRD §5.3 的「依据《文档名》第 X 条」）────
    # ★ 平铺在回执顶层，不是塞进一个子对象：`evidence_ref` / `ratified` /
    #   `unconfirmed_notice` 就是 T4 定的字段名，多包一层会让「回执里有没有这一项」
    #   变成一个需要知道嵌套路径才能回答的问题。
    core["rule_keys_hit"] = sorted(set(_rule_keys(verdict)))
    # ★ 为什么要记规则编号：`verdict_digest` 是个**哈希** —— 拿着回执的人
    #   无法据此判断「引用带全了没有」。规则编号不是广告原文（ADR-0008 决策 2
    #   约束的是原文），却是「这条回执该引哪几条条款」的唯一依据。
    if evidence:
        for _k in CR.BLOCK_FIELDS:
            core[_k] = evidence.get(_k)
        for _k in CR.BLOCK_AUX_FIELDS:
            if evidence.get(_k) is not None:
                core[_k] = evidence[_k]

    # ── 出口义务（D6 / D10）────────────────────────────────────────
    # ★ 为什么出口要进**回执**而不是只在判定结果里：判定结果是一次性的返回体，
    #   用完就没了；回执是长期留存的账。可申诉的关键不是「结果里写了申诉方式」，
    #   而是「三个月后拿出这条回执，能查到当时谁该受理、时限几天、凭什么撤」。
    #   D1-O3 欠的那一笔账正是这个：67 条/批被拦下，回执一个不少，但**出口是空的**。
    # ★ 回执里放的 notice 是**机器生成的模板文本**（含规则编号与 run_id），
    #   不含广告原文，也不含原文片段 —— 「不落库」这条约束没有被绕过。
    if obligations:
        core["obligations"] = obligations
    return core


RECEIPTS_CHAIN_PATH = RECEIPTS_PATH.with_suffix(".chain.json")


def _chain_update(p: Path, n_lines: int, after: str) -> None:
    """把「截至第 n 行的整文件 sha256」追加进链（前缀哈希链）。"""
    ch = []
    if RECEIPTS_CHAIN_PATH.exists():
        ch = json.loads(RECEIPTS_CHAIN_PATH.read_text(encoding="utf-8")).get("chain") or []
    ch.append({"n": n_lines, "sha256": hashlib.sha256(after.encode("utf-8")).hexdigest()})
    RECEIPTS_CHAIN_PATH.write_text(
        json.dumps({"$why": [
            "★ 前缀哈希链（2026-09-16）。回执账本是**只追加**的，而这件事此前只是口头约定 ——",
            "  一次写反的 `cp` 就把 5 条真回执覆盖成 1 条测试回执，且没有任何东西报警。",
            "  现在每追加一条就记下「截至第 N 行的整文件 sha256」，校验时逐条重算：",
            "  截断（行数变少）、改写（某一段哈希对不上）、覆盖（第 1 行就对不上）都会红。",
            "★ 它证明的是「今天这份文件是链上那份的前缀延伸」，不是「内容一定为真」——",
            "  后者要靠 verdict_digest 与原文复核，两者职责不同，都要有。",
        ], "chain": ch}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_receipt(rc: dict, path: Path | None = None) -> Path:
    p = path or RECEIPTS_PATH
    # ★ 闸门一：测试回执不得写进生产账本。
    #   本次事故的直接成因就是「一条测试回执进了真账本」，闸门就装在那一步。
    if p == RECEIPTS_PATH and rc.get("origin") == "test":
        raise SystemExit(
            "❌ 拒绝把 origin=test 的回执写进生产账本（_data/receipts.jsonl）。\n"
            "   测试请显式传 receipt_path=<临时文件>。理由见 _data/receipts.LOSS.md：\n"
            "   账本里混进测试记录之后，**没有任何字段能让下游把它认出来**。")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rc, ensure_ascii=False, sort_keys=True) + "\n")
    # ★ 闸门二：维护前缀哈希链。只对生产账本维护 —— 临时文件活不过一次调用。
    if p == RECEIPTS_PATH:
        _chain_update(p, len(p.read_text(encoding="utf-8").splitlines()),
                      p.read_text(encoding="utf-8"))
    return p


# ---------------------------------------------------------------- 主契约
def judge(text: str, *, product_line: str | None = None, locale: str | None = None,
          platform: str | None = None, campaign: str | None = None,
          ad_id: str | None = None, ad_type: str | None = None,
          ad_account: str | None = None,
          receipt: bool = False,
          receipt_path: Path | None = None, issued_at: str | None = None,
          origin: str = "cli",
          evidence_origin: str = "stated") -> dict:
    """★ 稳定契约。文案（+ 品线）→ 判定 / 命中规则编号 / 位置 / 降级证据 /
    规则与词表版本 / 边界声明 / 处置层 / 出口通知。

    纯函数的部分：给定 (text, 制品, 分层表)，除 `issued_at` 外的一切都是确定的。
    发回执时才引入时间 —— 因为回执的作用就是记录「这一次」。

    ★ `ad_type` 不是判定输入，是**路由输入**（D5）：文本为空的记录要走 DP0，
      而那条通知要说清「是哪种格式没有文本」。只说「没有文本」，收件人无法行动。

    ★★ 本函数有**两个 `origin`，它们不是一回事** —— 见 `evidence_origin.py` 抬头：

      * `origin=` 是**回执来源**（cli / batch / shouheng / test），回答「这次判定谁发起的」，
        它是 `push_receipts.py` 那道「测试不许进生产账本」闸门的依据；
      * `evidence_origin=` 是**证据来源**（stated / ocr / transcribed / described），
        回答「被审的材料是怎么读到的」，它决定结论能不能到 PASS。

      写成同一个名字就会撞车（`AGENTS.md` §2.4.5）：`origin="stated"` 会让那道闸门
      照常放行，而没有任何东西会红。两个取值域的交集由 `receipt_origin_problems()` 断言为空。
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise TypeError(f"text 必须是 str，收到 {type(text).__name__}")

    eng = engine()
    rules_by_key = {r["rule_key"]: r for r in eng.all_rules}
    hits, is_catch_all = eng.assess(text, product_line=product_line)
    vers = versions()
    layers = load_layers()
    has_text = bool(text.strip())

    # ── 命中明细：位置、原文片段、降级/放行证据 ──────────────────────
    out_hits = []
    for h in hits:
        src = rules_by_key.get(h.rule_key, {})
        band_words = [m for m in h.matches if m.via == "band"]
        claim_words = [m for m in h.matches if m.via != "band"]
        # 词干 vs 原文写法：前缀匹配下二者常常不同（`painless` 命中 `Painlessly`）。
        # 这个差值必须显式给出，否则下游拿 matched 回原文搜会搜不到。
        rewritten = [m for m in claim_words if m.text.lower() != m.keyword.lower()]
        out_hits.append({
            "rule_key": h.rule_key,
            "parent_rule": h.parent_rule,
            "topic": h.topic,
            "topic_label": src.get("topic_label"),
            "severity": h.severity,
            "disposition": h.disposition,
            "disposition_declared": h.disposition_declared,
            "disposition_rewritten": h.disposition != h.disposition_declared,
            "evaluability": src.get("evaluability"),
            "evidence_required": src.get("evidence_required"),
            "matched_by": h.matched_by,
            "matched_keywords": h.matched,
            "matched": [m.as_dict() for m in claim_words],
            "$stem_vs_verbatim": (
                "matched_keywords 是规则里的**词干**；matched[].matched_text 是**原文写法**。"
                "二者不同的有 " + str(len(rewritten)) + " 处 —— 拿词干回原文搜会搜不到，"
                "这正是旧实现把位置丢掉后下游会踩的坑。"),
            "band": {
                "kind": h.band_kind or None,
                "effect": h.band_effect,
                "words": h.downgrade_terms,
                "evidence": [m.as_dict() for m in band_words],
                "non_decisive_words": sorted(
                    {m.keyword for m in band_words} - set(h.downgrade_terms)),
                "$note": ("带的方向由规则自己声明（downgrade_band.effect 的箭头右侧，"
                          "可按词覆盖 keyword_effect_overrides）；"
                          "本命中的落点是 " + str(h.band_effect.split("→")[-1].strip()
                                                   if "→" in str(h.band_effect) else None)),
                "$non_decisive_note": ("★ 两个带都命中时，**降级优先**（保守，D9）。"
                                       "这里的词也出现在原文里、也进了 evidence，只是落点由更弱的那个决定。"),
            },
            "escalated": h.escalated,
            "escalation_reason": h.escalation_reason,
            "unwired_guard_near_miss": near_miss_guards(text, h.rule_key),
            "$near_miss_note": ("本次文案里出现了这些守卫词，但它们**未接线**，因此没有生效。"
                                "「一条红线」与「一条本可降级、因词形未补全而成了红线」"
                                "是两个不同的问题 —— 前者改文案，后者补词表。"),
            "rule_version": vers["rule_version"],
        })

    # ── 记录级结论 ────────────────────────────────────────────────
    if hits:
        # ★ 取最严。次序数组是 严→宽，所以索引**越小越严**，要的是 min。
        #   第一版写成 `max(..., key=索引)`，结果选出索引最大的 = 最宽的一档 ——
        #   命中 auto_reject 却报 manual_review（V5 抓到的）。
        #   这类错误不会抛异常，只会让判定偏松，正是最危险的方向。
        def severity_rank(sev_code: str) -> int:
            return sev.IMPACT_TO_RANK[sev.SEVERITY_TO_IMPACT.get(sev_code, "Very Low")]

        worst = min(out_hits, key=lambda x: (
            DISPOSITION_PRECEDENCE.index(x["disposition"])
            if x["disposition"] in DISPOSITION_PRECEDENCE else len(DISPOSITION_PRECEDENCE),
            -severity_rank(x["severity"]),
        ))
        disposition = worst["disposition"]
        severity = max((x["severity"] for x in out_hits), key=severity_rank)
        topic = worst["topic"]
    else:
        disposition, severity, topic = "catch_all", "L0", eng.catch_all.get("topic", "L0")

    # ── T4 · 命中的规则 → 证据引用（**在 `judge()` 内部产出，不可注入**）──────
    #   ★ 为什么不做成 `judge(evidence_refs=...)` 那样的入参：`judge()` 的调用方
    #     不止一个（CLI / 批量 / `push_receipts` / 守衡的 `judge_copy`），
    #     只要有一个不传，那条回执就永远点不开依据，**而且没有任何东西会红**。
    #     「任一判定回执能反查到条款」这句话只有在产出点唯一时才成立。
    #   ★ 算在这里（而不是回执那一段里）是因为下面那道**门二**要用它：
    #     条款的 `origin` 要真的参与收窄，不能只躺在回执里（§2.4「定义了没人用」）。
    _lib_doc, _lib_index, _lib_problem = CR.load_library()
    _evidence = CR.evidence_block(sorted({x["rule_key"] for x in out_hits}),
                                  eng.all_rules, _lib_index,
                                  library_problem=_lib_problem)

    # ── T19 · 证据来源收窄：非「原文照读」的证据不许单独把结论推到 PASS ──────
    #
    #   PRD §5.2 缺的那一档。图片走 OCR、视频走转写/画面转述 —— 它们**不比原文照读**，
    #   所以不能让它们单独把一条内容判成「可以发布」。有 stated 在场时它们可以当补充。
    #
    #   ★ 为什么收窄发生在**这里**（disposition 已算出、layer 还没解析）：
    #     落在这一步，`resolve_layer` / `suggestion` / `blank_register` 全都跟着走对了；
    #     写在出口那一跳，结论会与处置层对不上（`AGENTS.md` §2.5 的形态错位，同一个形状）。
    #
    #   ★ 今天不会触发：文字输入的判定一律 `evidence_origin=stated`。
    #     它触发的那一天，是图片/视频第一次进审查的那一天 —— 而那正是它该在的一天。
    #
    #   ★★ T4 接线（2026-09-23）：收窄现在是**两扇并列的门**，不是一扇。
    #
    #      | 门 | 看的是 | 为什么不能合成一扇 |
    #      |---|---|---|
    #      | 一 | **被审材料**怎么读到的（`input.evidence_origin`） | 判「这份材料我们读全了吗」 |
    #      | 二 | **所引条款**怎么读到的（`evidence_ref[].origin`） | 判「我们据以放行的那条标准，我们读准了吗」 |
    #
    #      ★ 合成的写法（把两者倒进同一个 `may_finalize_pass` 集合）**会放松今天的口径**：
    #        `may_finalize_pass` 的规矩是「有 stated 在场就放行，弱的只作补充」，
    #        于是「材料是 OCR、条款是 stated」这一组会被判成放行 ——
    #        而它正是门一要挡的那一组。**两件事各有各的方向，合并就是 §2.4.5。**
    #      ★ 门二只在**确实引用了条款**时开口：命中的规则若声明了 `no_external_basis`，
    #        「没有依据」不是「依据很弱」—— 那一条由规则自己的声明管，不由这扇门管。
    narrowed = None
    _mat_ok, _mat_why = (True, "")
    _ref_ok, _ref_why = (True, "")
    if disposition in PASS_DISPOSITIONS:
        if evidence_origin not in EO.PASS_ORIGINS:
            _mat_ok, _mat_why = EO.may_finalize_pass([{"origin": evidence_origin}
                                                      for _ in out_hits])
        _cited = _evidence.get("evidence_ref") or []
        if _cited and _evidence.get("evidence_status") == "ok":
            _ref_ok, _ref_why = EO.may_finalize_pass(_cited)
        if (not _mat_ok) or (not _ref_ok):
            _gates = ([f"材料来源（{evidence_origin}）：{_mat_why}"] if not _mat_ok else []) + \
                     ([f"所引条款来源：{_ref_why}"] if not _ref_ok else [])
            narrowed = {
                "from": disposition,
                "why": "；".join(_gates),
                "gate": ("both" if not _mat_ok and not _ref_ok
                         else ("material" if not _mat_ok else "cited_clauses")),
                "evidence_origin": evidence_origin,
                "cited_origins": sorted({r.get("origin") for r in (_cited or [])}),
                "$note": ("PRD §5.2 未写的那条规矩：OCR / 转写 / 画面转述可以**补充**证据，"
                          "但不能单独把结论推到 PASS。要放行必须先有一条原文照读的证据。"
                          "★ T4 之后这扇门有两道并列的闸：**材料**怎么读到的、"
                          "**所引条款**怎么读到的 —— 各有各的方向，不许合并成一个集合。"),
            }
            disposition = "manual_review"

    layer = resolve_layer(disposition, hits, layers, has_text=has_text, ctx={
        "rule_keys": sorted({x["rule_key"] for x in out_hits}),
        "run_id": ad_id or "",
        "ad_type": ad_type or "（未提供）",
        "sla_workdays": ((layers["mapping"].get(disposition, {})
                          .get("outbound", {}).get("appeal", {}) or {}).get("sla_workdays")),
    })
    suggestion = (SUGGESTION_ON_NO_MATCH if not hits
                  else SUGGESTION_BY_DISPOSITION.get(disposition, "转人工"))
    if layer.get("suggestion_override"):
        suggestion = layer["suggestion_override"]

    verdict = {
        "disposition": disposition,
        "severity": severity,
        "topic": topic,
        "topic_label": (eng.catch_all.get("topic_label") if not hits
                        else next((x["topic_label"] for x in out_hits if x["topic"] == topic), None)),
        "hit_count": len(out_hits),
        "rules_hit": sorted({x["parent_rule"] for x in out_hits}),
        "rule_keys_hit": [x["rule_key"] for x in out_hits],
        "rewritten_count": sum(1 for x in out_hits if x["disposition_rewritten"]),
        "escalated": any(x["escalated"] for x in out_hits),
        "layer": layer,
        "blank_register": layer["blank_register"],
        "$disposition_note": (
            ("★ catch_all 的含义是「规则库没有覆盖它」，**不是**「已检查且合规」。"
             "把它与 auto_pass 合并会让盲区率在数学上不可观测（设计文档 §5.1）。")
            if not hits else
            "disposition 取**最严**的一条命中；`disposition_rewritten` 标记被豁免带改写过的命中。"),
        # ★ 2026-09-17（D9 执行）：这一段原来是一个**写在判据里的语料统计量** ——
        #   「存量 291 条里这种记录有 59 条（20.3%），全部是 Google `产品广告`，
        #   近 7 天在花 $15,747」。逐行核对后，其中的断言有两个是错的：
        #     ① 那 59 条里有 2 条是**整行没读到**的空行（连广告都不是）；
        #     ② 因此也不是「全部是 Google」—— 另有 2 条 Meta。
        #   它们错得起，是因为它们是字面量：语料变了、口径改了，它不会红。
        #   一个**逐条**判定的函数本来也不该断言整个语料的统计量 —— 那是制品的
        #   职责。这里只说这一条自己的事，并把数字指向它唯一的家。
        "$unreviewable_note": (
            "★★ 本条**没有可判文本**（DP0，PRE-001）。它不是「合规」，不是「疑似规则空白」，"
            "而是**没有进入审查**：没有输入就没有结论，任何「通过」都是凭空产生的。"
            "存量语料里这种记录有多少条、带着多少投放金额、被记成了什么 —— 见 "
            "`research/governance/skeleton/_data/风险等级-还原.json`；"
            "复算：`python3 research/governance/audit_risk_label.py`。"
            if not has_text else None),
    }
    if narrowed:
        verdict["origin_narrowed"] = narrowed

    boundary = _boundary(eng, eng.vocab, hits, product_line, locale)
    if narrowed:
        #   边界声明也要说这一句 —— 它是「这次判定有什么不适用」的正式出口，
        #   只写在 verdict 里，读 boundary 的人（法务）就看不到结论为什么被压过。
        boundary.setdefault("unknowns", [])
        boundary["unknowns"].append(
            f"**证据来源收窄（T19）**：{narrowed['why']}。"
            f"结论因此从 `{narrowed['from']}` 落到 `manual_review`。")

    result = {
        "contract_version": CONTRACT_VERSION,
        "input": {
            "text_sha256": _sha256(text),
            "chars": len(text),
            # ★ 证据来源（T19）。与回执顶层的 `origin` **不是一回事** ——
            #   那个是「谁发起的这次判定」，这个是「材料是怎么读到的」。
            "evidence_origin": evidence_origin,
            "$evidence_origin_note": EO.ORIGIN_MEANING.get(evidence_origin, "未知来源"),
            "has_text": has_text,
            "product_line": product_line,
            "locale": locale,
            "platform": platform,
            "campaign": campaign,
            "ad_id": ad_id,
            "ad_type": ad_type,
            "ad_account": ad_account,
            "$has_text_note": ("★ `has_text` 不是判定输入，是**路由输入**（D5）："
                               "它为假时本条走 DP0，不落任何审查队列，也不进空白清单。"),
            "$product_line_note": ("已记录但**未参与判定** —— 规则文件没有品线字段。"
                                   "见 boundary_statement.unknowns[0]。"),
        },
        "verdict": verdict,
        "hits": out_hits,
        "suggestion": suggestion,
        "$suggestion_note": ("ADR-0005 约束 1：这是**建议，不是决定**。"
                             "机器不能把任何状态改成「无需处理」，不能关闭任何待复核项。"),
        "versions": vers,
        "boundary_statement": boundary,
        "receipt": None,
    }

    if receipt:
        ts = issued_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        ob = layer.get("outbound") or {}
        # ★ 2026-09-16（D14 · 回答 Q8）：回执必须带**可解析的路由键**。
        #   在此之前 `to` 写的是「文案提交人」—— 一个角色，不是一个人、也不是一个渠道。
        #   于是管道缺的从来不只是「推送程序」：**数据上就没有「送给谁」这一项**，
        #   5 条存量回执一个都没带。没有路由键的送达义务只能是一句愿望。
        _route_key = ad_account or ad_id
        obl = {
            "layer_id": layer.get("id"),
            "layer_name": layer.get("name"),
            "must_reach": ob.get("must_reach", False),
            "to": ob.get("to"),
            "kind": ob.get("kind"),
            "notice": ob.get("notice"),
            "notice_sha256": _sha256(ob.get("notice") or ""),
            "appeal": ob.get("appeal"),
            "route": {
                "key": _route_key,
                "kind": "ad_account" if ad_account else ("ad_id" if ad_id else None),
                "resolver": "_data/account-owners.csv",
                "$status": ("ready" if _route_key else "no_route_key"),
                "$why": ("`to` 回答「谁该收」，`route.key` 回答「按什么查到这个谁」。"
                         "缺前者是政策问题，缺后者是数据问题 —— 今天两者都缺，"
                         "而只有后者是代码能补的。" if _route_key else
                         "本次判定没传 `ad_account` / `ad_id`，回执无法被路由到人。"
                         "★ 这不是错误，是**如实记账**：送不出去的义务必须看得见，"
                         "不能在管道里被静默跳过。"),
            },
            "$note": ("本块是 D6/D10 的落地物：它让「被拦的人找谁说、多久有回音、"
                      "凭什么撤」随结论一起留痕。缺了它，回执只能证明拦过，"
                      "不能证明有人负责。"),
        }
        rc = build_receipt(text, {k: v for k, v in result.items() if k != "receipt"},
                           vers, issued_at=ts, origin=origin,
                           evidence_origin=evidence_origin,
                           evidence=_evidence, obligations=obl)
        result["receipt"] = rc
        append_receipt(rc, receipt_path)

    return result


# ---------------------------------------------------------------- 人读渲染
def render(r: dict) -> str:
    v, b = r["verdict"], r["boundary_statement"]
    L = v["layer"]
    lines = []
    lines.append("=" * 74)
    lines.append(f"判定  {v['disposition']}   严重等级 {v['severity']}   主题 {v['topic']}")
    lines.append(f"处置层  {L['id']} {L['name']}（{L['who']}） · 动作：{L['final_action']}")
    if L.get("precondition_applied"):
        lines.append(f"前置    {L['precondition_applied']['id']} "
                     f"[{L['precondition_applied']['flag']}] —— 先于落点与升级生效")
    lines.append(f"空白清单 {'进入（规则缺口候选）' if v['blank_register']['enters'] else '不进入'}")
    lines.append(f"建议    {r['suggestion']}（建议，不是决定）")
    ob = L.get("outbound")
    if ob:
        lines.append("-" * 74)
        lines.append(f"出口通知 → {ob['to']}   [must_reach={ob['must_reach']}]")
        lines.append(f"  {ob['notice']}")
        ap = ob.get("appeal") or {}
        if ap.get("available"):
            lines.append(f"  申诉：{ap['channel']}")
            lines.append(f"        受理 {ap['owner']}（{ap['owner_layer_id']}） · "
                         f"时限 {ap['sla_workdays']} 个工作日 · 撤销须附理由留痕")
            lines.append(f"        涉及规则本身则转 {ap['escalate_to_layer_id']}：{ap['escalate_when']}")
            if ap.get("$gap_not_implemented"):
                lines.append(f"        ★ 未实现：{ap['$gap_not_implemented']}")
    lines.append("=" * 74)
    if not r["hits"]:
        lines.append("  零命中 —— 落进 CATCH-ALL。★ 这是「规则库没覆盖」，不是「合规」。")
        if v.get("$unreviewable_note"):
            lines.append("  ★★ 但本条文本为空：它连 CATCH-ALL 都不是 —— 见上方 DP0 与出口通知。")
    for h in r["hits"]:
        lines.append(f"\n  ▸ {h['rule_key']}  [{h['parent_rule']}]  {h['severity']}  "
                     f"{h['disposition_declared']} → {h['disposition']}"
                     + ("  ★被改写" if h["disposition_rewritten"] else ""))
        for m in h["matched"]:
            p = m["position"]
            loc = f"@{p['start']}..{p['end']}" if p["located"] else f"(未定位: {p.get('reason','')})"
            lines.append(f"      命中原文 {loc}  {m['matched_text']!r}  ← 词干 {m['matched_keyword']!r}")
        for e in h["band"]["evidence"]:
            p = e["position"]
            lines.append(f"      {h['band']['kind']}证据 @{p['start']}..{p['end']}  "
                         f"{e['matched_text']!r}  ({h['band']['effect']})")
        if h["escalated"]:
            lines.append(f"      ⬆ 升级：{h['escalation_reason']}")
        for nm in h.get("unwired_guard_near_miss", []):
            lines.append(f"      ⚠ 未接线守卫 {nm['word']!r}（status={nm['status']}，"
                         f"若接线效果为 {nm['would_have_effect']}）")
            if nm.get("wire_gap"):
                lines.append(f"         成因：{nm['wire_gap']}")
    lines.append("\n" + "-" * 74)
    lines.append("边界声明（本判定判断不了什么）")
    for u in b["unknowns"]:
        lines.append(f"  · {u}")
    lines.append(f"\n  置信度 {b['confidence']}（{b['$confidence_basis']}）")
    lines.append(f"  版本   数据 {r['versions']['engine_version']} · "
                 f"代码 {r['versions'].get('code_version')} · "
                 f"{r['versions']['rule_version']} / {r['versions']['vocab_version']}")
    if r.get("receipt"):
        lines.append(f"  回执   {r['receipt']['run_id']} @ {r['receipt']['issued_at']}")
        # ★ T4：回执的证据链要在**人读视图**里看得见。
        #   只写进 JSONL 的话，「这条判定依据哪几条、那几条确认过没有」
        #   只有会读账本的人知道 —— 而 Q22 要防的正是「一次研究被读成一次法务裁定」。
        _ev = r["receipt"].get("evidence_ref") or []
        if _ev:
            lines.append(f"  依据   {len(_ev)} 条外部标准："
                         + "、".join(f"{x.get('条文号')}（{x.get('条目ID')}）" for x in _ev))
            if r["receipt"].get("unconfirmed_notice"):
                lines.append(f"  ⚠ {r['receipt']['unconfirmed_notice']}")
        elif r["receipt"].get("$ratified_note"):
            lines.append("  依据   本次判定没有引用任何外部条款"
                         "（零命中 / 命中的规则声明了 no_external_basis）")
    return "\n".join(lines)


# ---------------------------------------------------------------- 精简视图
def compact(obj):
    """递归删掉 `$` 开头的键。

    ★ 本文件里的 `$xxx` 一律是**写给读者自己的注解**（为什么这样设计、这个字段
      不可信在哪），不是判定数据。守衡把判定结果塞进模型上下文时，这些注解会
      挤掉真正的证据，所以给它一个 `--brief` 视图。

      但注解本身不能删掉 —— 它们是这个项目里最贵的部分（每一条都对应一次踩坑）。
      所以是**视图分离**，不是删除。
    """
    if isinstance(obj, dict):
        return {k: compact(v) for k, v in obj.items() if not k.startswith("$")}
    if isinstance(obj, list):
        return [compact(x) for x in obj]
    return obj


# ---------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="内容合规判定引擎 · 稳定契约入口")
    ap.add_argument("--text", help="要判定的文案")
    ap.add_argument("--text-file", help="从文件读文案（长文案用这个，避免命令行长度上限）")
    ap.add_argument("--stdin", action="store_true", help="从 stdin 读文案")
    ap.add_argument("--batch", help="批量：读一个 records.json，逐条判定")
    ap.add_argument("--product-line", default=None)
    ap.add_argument("--locale", default=None)
    ap.add_argument("--platform", default=None)
    ap.add_argument("--ad-id", default=None)
    ap.add_argument("--receipt", action="store_true", help="写一条回执（单条判定时）")
    ap.add_argument("--origin", default="cli",
                    help="回执来源标记（cli / batch / shouheng / test）。审计日志里必须分得出测试与真判定")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--brief", action="store_true", help="删掉 $ 注解（给模型上下文用）")
    a = ap.parse_args()

    if a.batch:
        recs = json.loads(Path(a.batch).read_text(encoding="utf-8"))
        rows = []
        for r in recs:
            text = S.rec_text(r)
            res = judge(text, product_line=r.get("品线") or None,
                        locale=r.get("文案语种") or None,
                        platform=r.get("平台") or None,
                        ad_id=r.get("外部广告ID") or None,
                        ad_type=r.get("广告类型") or None)
            rows.append({
                "ad_id": res["input"]["ad_id"],
                "ad_type": res["input"]["ad_type"],
                "has_text": res["input"]["has_text"],
                "disposition": res["verdict"]["disposition"],
                "severity": res["verdict"]["severity"],
                "layer": res["verdict"]["layer"]["id"],
                "blank_register": res["verdict"]["blank_register"]["enters"],
                "rules": res["verdict"]["rules_hit"],
                "suggestion": res["suggestion"],
            })
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for x in rows:
                print(f"  {str(x['ad_id']):16s} {x['disposition']:20s} {x['severity']:3s} "
                      f"{x['layer']:4s} {'清单' if x['blank_register'] else '  — '} "
                      f"{','.join(x['rules'])}")
        return 0

    if a.text_file:
        text = Path(a.text_file).read_text(encoding="utf-8")
    elif a.stdin or (a.text is None and not sys.stdin.isatty()):
        text = sys.stdin.read()
    elif a.text is not None:
        text = a.text
    else:
        ap.error("需要 --text / --text-file / --stdin / --batch 之一")

    res = judge(text, product_line=a.product_line, locale=a.locale,
                platform=a.platform, ad_id=a.ad_id, receipt=a.receipt,
                origin=a.origin)
    if a.brief:
        res = compact(res)
    print(json.dumps(res, ensure_ascii=False, indent=2) if (a.json or a.brief) else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
