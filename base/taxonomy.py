#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/taxonomy.py —— 规则归类（7 主轴 + 5 正交字段）

**边界**：本模块只做「规则归类」：读规则文本，回答「这条规则要求什么审查动作」。
它不审具体内容、不判违规、不查授权/规格/证据；那些属于运行期的 review_content
（本版未实现）。因此本模块的输入只有规则自身的文本与元数据。

判定顺序（首次命中即 primary）：
    CHAN → RIGHT → SCENE → DISC → BRAND → FACT → CLAIM

- `EDITORIAL` 不是 primary：返回 status=QUALITY_ONLY、quality_tag=[EDITORIAL]；
- `NOT_A_RULE` 不是 primary：返回 status=NOT_A_RULE、record_kind=not_a_rule；
- 聚合规则（needs_split）返回 status=SPLIT_REQUIRED、unknown_reason=
  aggregated_rule_needs_split，不硬给 primary；
- 规则文本为空 / 无任何依据 → status=UNKNOWN，不默认 PASS。

`derive_severity(primary, rule_nature, impact)` 的 impact 是三值枚举：
core / material / editorial；severity 不沿用原表值。
"""
from __future__ import annotations

import html
import re
import unicodedata

AXES = ("CHAN", "RIGHT", "SCENE", "DISC", "BRAND", "FACT", "CLAIM")
QUALITY_TAGS = ("EDITORIAL",)
RECORD_KINDS = ("not_a_rule", "policy_fragment")
IMPACTS = ("core", "material", "editorial")
NATURES = ("prohibition", "mandate", "disclosure", "substantiation",
           "recommendation")

# 子类先验：只作为文本动作规则都未命中时的兜底；不是答案表。

# 子类内的例外：文本动作命中时改判。每项 = (子类, 目标轴, 正则)。

EDITORIAL_CUES = (
    "文章导言", "删除或重写导言", "该节内容不相关", "补充反向压迫软化法",
    "表述不够准确", "调整章节结构", "术语表述", "修正序号", "表述笼统",
    "适用时间段", "整体表述格式", "拆分为两篇", "词语使用不够精确",
    "表述不当", "统一改为", "插入引用标识", "引用《", "方奶统一改为",
    "文章标题标签", "标题标签", "文章整体（建议重新写）", "删除重复",
    "补充初乳配图", "配图", "参考文献", "重新写", "删除该节", "移至更合适",
    "文章标题及导言", "术语使用不规范", "本文主题", "文章主题",
)
NOT_A_RULE_CUES = (
    "safe harbor", "liaison agreement", "truth-in-advertising",
    "ftc considers in determining", "studies taken together",
    "court need not look", "notify the fda", "whatever they say expressly",
    "sufficiently qualified", "deceptive use of such materials",
    "promotional product information", "fda law, such claims",
    "bayer had violated", "unfair or deceptive acts", "规则码 uncoded",
    "empty:", "规则停用", "不再判险", "未识别到处理动作",
)


def normalize(text):
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _text(rule):
    return normalize((rule.get("rule_text") or "") + " " + (rule.get("condition") or ""))


def is_editorial(rule):
    """纯形式建议：错别字/格式/引用规范/排版/术语统一等。

    这是**独立质量标记**，不是七轴 primary。没有证据/内容判断时返回 False。
    """
    text = _text(rule)
    return any(cue in text for cue in EDITORIAL_CUES)


def _is_not_a_rule(rule, text):
    low = text.lower()
    if any(cue in low for cue in NOT_A_RULE_CUES):
        return True
    if text.startswith("修订模式") and "改写" in text:
        return True
    if text.startswith(("边界：", "边界:")) \
            and ("触发词：" in text or "触发词:" in text) \
            and "处理：" not in text and "处理:" not in text:
        return True
    if re.search(r"处理[:：]\s*(verify|should use|ensure|keep)\b", text) \
            and "无显式条件" in text:
        return True
    if "should engage" in low and "无显式条件" in text:
        return True
    return False


def _infer_nature(text):
    low = text.lower()
    if re.search(r"禁止|不得|must not|prohibit|forbid", low):
        return "prohibition"
    if re.search(r"披露|disclose|标注|注明|显著|label|mark", low):
        return "disclosure"
    if re.search(r"证明|证据|substantiat|支持|substantiate", low):
        return "substantiation"
    if re.search(r"必须|应当|should|must|mandate|ensure", low):
        return "mandate"
    return "recommendation"


def _infer_jurisdiction(text):
    low = text.lower()
    if re.search(r"brazil|巴西", low):
        return "BR"
    if re.search(r"singapore|uk|united kingdom|英国|新加坡", low):
        return "MULTI"
    if re.search(r"europe|eu|欧盟", low):
        return "EU"
    if re.search(r"united states|u\.s\.|美国|ftc|fda", low):
        return "US"
    if re.search(r"平台|platform|amazon|tiktok|meta|google", low):
        return "PLATFORM"
    return "GLOBAL"


def _impact(primary, text):
    if primary is None:
        return "editorial"
    if re.search(r"一票否决|PRD §7\.3|BLOCK|危险行为|安全座椅|独留|AI 深度合成|未成年人", text, re.I):
        return "core"
    return "material"


def derive_severity(primary, rule_nature, impact):
    """主轴 + 义务形态 + 影响面 → severity 1..5；不沿用原 severity。"""
    if primary is None or impact == "editorial":
        return 1
    if primary == "RIGHT" or impact == "core":
        return 5 if rule_nature == "prohibition" else 4
    if impact == "material":
        return 3 if rule_nature in ("prohibition", "mandate", "disclosure",
                                    "substantiation") else 2
    return 1


def _fallback_by_actions(text):
    """没有子类先验时的 7 轴文本动作判定（顺序即优先级）。"""
    low = text.lower()
    rules = (
        ("CHAN", r"平台|版位|投放|渠道|素材提交|提交字段|禁投|禁售|listing"),
        ("RIGHT", r"肖像|隐私|未成年人出镜|AI 生成|深度合成|换脸|声音克隆|监护人"),
        ("SCENE", r"跌落|滑落|烫伤|窒息|溺水|中毒|触电|安全座椅|独留|睡姿|冰袋|冰敷|危险行为|危险动作"),
        ("DISC", r"披露|标注|注明|免责|显著|告知|警示|限定信息|风险提示"),
        ("BRAND", r"情绪|焦虑|挫败|立场|框架|口吻|语气|竞品|贬低|紧迫|限时"),
        ("FACT", r"事实|不准确|不符|数值|单位|月龄|剂量|指南|文献|参数|规格"),
        ("CLAIM", r"宣称|证明|证据|背书|认证|等级|对比|效果|功效|绝对化"),
    )
    for axis, pat in rules:
        if re.search(pat, text, re.I):
            return axis
    return None


def _primary_from_text(rule, text):
    """只用规则文本的七轴动作词，不读子类先验或 gold 派生表。"""
    axis = _fallback_by_actions(text)
    return axis, ("TEXT_ACTION" if axis else None)


def classify_rule(rule):
    """规则归类。输入只读规则自身字段，不读任何基准标签。"""
    if not isinstance(rule, dict):
        raise ValueError("rule 必须是对象")
    text = _text(rule)
    if rule.get("needs_split"):
        return _result("SPLIT_REQUIRED", None, rule, text,
                       unknown_code="U10",
                       unknown_reason="aggregated_rule_needs_split")
    if not text:
        return _result("UNKNOWN", None, rule, text, unknown_code="U3",
                       unknown_reason="empty_rule_text")
    if _is_not_a_rule(rule, text):
        return _result("NOT_A_RULE", None, rule, text,
                       record_kind="not_a_rule")
    primary, evidence = _primary_from_text(rule, text)
    if primary is None:
        return _result("UNKNOWN", None, rule, text, unknown_code="U9",
                       unknown_reason="no_axis_matched")
    nature = _infer_nature(text)
    jur = _infer_jurisdiction(text)
    impact = _impact(primary, text)
    return _result("CLASSIFIED", primary, rule, text,
                   rule_nature=nature, jurisdiction=jur,
                   severity=derive_severity(primary, nature, impact),
                   matched_condition=evidence,
                   confidence="high")


def _result(status, primary, rule, text, **kw):
    quality = list(kw.get("quality_tag") or [])
    return {
        "status": status,
        "primary": primary,
        "secondary": None,
        "rule_nature": kw.get("rule_nature"),
        "jurisdiction": kw.get("jurisdiction"),
        "severity": kw.get("severity"),
        "quality_tag": quality,
        "record_kind": kw.get("record_kind"),
        "topic": rule.get("subcategory_original") or rule.get("topic") or "",
        "confidence": kw.get("confidence") or "low",
        "matched_condition": kw.get("matched_condition"),
        "unknown_code": kw.get("unknown_code"),
        "unknown_reason": kw.get("unknown_reason"),
        "reasons": [kw.get("unknown_reason") or kw.get("matched_condition") or status],
    }


# ── 碰撞检测：同一谓词同时命中两轴才是 COLLISION ──────────────────
_PREDICATE_BY_AXIS = {axis: "P_" + axis for axis in AXES}


def axis_hits(rule, predicate_by_axis=None):
    """返回 {axis: predicate_id}；predicate 默认为每轴唯一。"""
    text = _text(rule)
    if not text:
        return {}
    mapping = predicate_by_axis or _PREDICATE_BY_AXIS
    hits = {}
    for axis, pat in (
        ("CHAN", r"平台|版位|投放|渠道|素材提交|提交字段"),
        ("RIGHT", r"肖像|隐私|未成年人出镜|AI 生成|深度合成|换脸"),
        ("SCENE", r"跌落|滑落|烫伤|窒息|安全座椅|独留|睡姿"),
        ("DISC", r"披露|标注|注明|免责|显著|告知|警示"),
        ("BRAND", r"情绪|焦虑|立场|框架|口吻|语气|竞品|贬低"),
        ("FACT", r"事实|不准确|不符|数值|单位|月龄|剂量|指南|参数"),
        ("CLAIM", r"宣称|证明|证据|背书|认证|等级|对比|效果|功效"),
    ):
        if re.search(pat, text, re.I):
            hits[axis] = mapping.get(axis, "P_" + axis)
    return hits


def detect_collisions(rule, predicate_by_axis=None):
    """同一 predicate_id 命中两个不同轴 → 碰撞。"""
    hits = axis_hits(rule, predicate_by_axis)
    by_pred = {}
    for axis, pred in hits.items():
        by_pred.setdefault(pred, []).append(axis)
    return [axes for axes in by_pred.values() if len(axes) > 1]
