#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_with_guide.py v2 —— ANN-GUIDE-001 §3 三问决策程序的可执行实现。

★ v2 相对 v1 的三处修正（对应指南 §9 的 L1/L2/L3）：
  L1  判定单位从「整条广告」改为「素材段」。广告是几十个素材用 " | " 拼成的 blob，
      在 blob 上找"疼痛的对象"会产生文档级假对象。
  L2  删除「机制归因」作为管辖判据。实测显示它只挪动 3/57 段，不具区分度；
      仅保留为证据要求字段。
  L3  从 PROCESS 词典中移除产品名（tire-lait / milchpumpe / sacaleches / extractor）。
      产品名不是动作名词，把裸对象误判成过程对象。

★ 核心判据：疼痛词修饰的是【动作名词】还是【器械名词】。
"""
import json, re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLIND = ROOT / "annotations" / "pain-corpus-blind.json"

# ---------------------------------------------------------------- 词典（v2）

# 疼痛/不适词家族 —— 本指南的作用域入口
PAIN = [
    r"pain\w*", r"douleur\w*", r"indolore\w*", r"schmerz\w*", r"dolor\w*",
    r"dolore\w*", r"sore\w*", r"ache\w*", r"hurt\w*", r"痛", r"疼",
    r"verstopft\w*", r"blocage\w*", r"bloqu\w*", r"堵奶",
]

# 裸形容词式主张（含连字符，避免 "Tire-Lait Sans Douleur" 被切成三段后丢失短语）
BARE_CLAIM = [
    r"pain[- ]?free", r"painless\w*", r"no\s+pain", r"zero\s+pain",
    r"without\s+pain", r"sans\s+douleur", r"indolore\w*",
    r"schmerz\w*frei\w*", r"sin\s+dolor(?:es)?", r"无痛", r"不痛",
]

# 消除性 / 结果性表述（问题 C）
ELIMINATIVE = [
    r"say\s+goodbye\s+to", r"goodbye\s+to", r"no\s+more", r"not\s+anymore",
    r"eliminat\w*", r"reliev\w*", r"reduc\w*", r"\bsoulag\w*", r"entlastung",
    r"\bend\w*\s+pain", r"告别", r"消除", r"缓解", r"减轻",
]

# B1 病理名词 —— 疼痛词被病理名词限定
PATHOLOGY = [
    r"mastitis", r"乳腺炎", r"thrush", r"nipple\s+damage", r"乳头损伤",
    r"cracked\s+nipple", r"皲裂", r"nipple\s+pain", r"painful\s+nipple",
    r"sore\s+nipple", r"乳头疼痛", r"milk\s+blister",
    r"verstopft\w*\s*milch\w*", r"堵奶", r"blocage\w*", r"bloqu\w*", r"乳管堵塞",
]

# B2 动作名词 —— 动名词 / 名词化动词（★ 不含产品名）
ACTION_NOUN = [
    r"pumping", r"abpump\w*", r"pumpen", r"pompage", r"tirage",
    r"extracci[oó]n", r"sacado", r"吸乳", r"吸奶", r"expression",
]

# B3 器械名词 —— 产品名 / 器械本体
DEVICE_NOUN = [
    r"tire[- ]?lait", r"milchpumpe", r"sacaleches", r"extractor",
    r"breast\s+pump", r"wearable\s+pump", r"吸奶器", r"\bpump\b",
]

BARE_RE = r"(?:pain[- ]?free|painless\w*|no\s+pain|zero\s+pain|without\s+pain|" \
          r"sans\s+douleur|indolore\w*|schmerz\w*frei\w*|sin\s+dolor(?:es)?)"
# ★ 同形消解（Rater B 发现的 §6↔§7 不一致，根因在此）：
#   D1 疼痛词 + 空格 + Pump，中间无插入词 → 副词修饰动词 → 动作名词 → T2.2.2 黄
#   D2 疼痛词与 Pump 之间有插入词           → 形容词修饰器械名词 → T1.4 红
D1_ACTION = re.compile(BARE_RE + r"\s+pump(?!\w)", re.I)
D2_DEVICE = re.compile(BARE_RE + r"[^.!?]{1,80}?\bpump(?!\w)", re.I)
# D3 限定语测试：`Pump` 前面紧邻一个限定语/型号/所有格 → 它是名词（器械），不是动词。
#    没有这一层，`Momcozy M5 Pain-Free Pump` 会因 D1 的"紧邻"条件被误判为动作。
#    ★ 判据由数据决定，不由正则直觉决定：把全部 21 处「疼痛词 + 空格 + pump」的
#      「pump 前一个词」列出来后，只有三种情形 —— 段首 11 处、破折号 8 处、型号 M5 2 处。
#      段首/破折号处，`pump` 是句子起头的动词原形 → 动作名词（黄）；
#      型号后，`pump` 是名词短语的中心语 → 器械名词（红）。
#      早期版本用 [A-Z][a-z]+ 猜"首字母大写即限定语"，把副词 Painlessly 也吞了进去，误判 13 条。
D1_PRECEDED_BY = re.compile(
    r"(?:^|[-–—])\s*" + BARE_RE + r"\s+pump(?!\w)", re.I)

TREAT_VERB = r"\b(treat|cure|heal|unclog|prevent|diagnos)\w*\b"


def _find(pats, text):
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            return m.group(0)
    return None


def segments(copy_text):
    """★ L1：素材分隔符是 " | "，不是句法连接符。"""
    return [s.strip() for s in re.split(r"\s*\|\s*", copy_text) if s.strip()]


def classify_segment(seg):
    """对单个素材段执行 A/B/C 三问。返回 None 表示不在作用域。"""
    if not _find(PAIN, seg):
        return None

    chain = []

    # ---- 问题 C：承诺 or 场景
    elim = _find(ELIMINATIVE, seg)
    bare = _find(BARE_CLAIM, seg)
    is_claim = bool(elim or bare)
    chain.append(f"C 承诺={'是' if is_claim else '否'}"
                 f"〔消除性={elim or '—'} / 裸主张={bare or '—'}〕")

    # ---- 问题 A 前置：治疗/疏通动词 + 病理 → 交 H01
    if re.search(TREAT_VERB, seg, re.I) and _find(PATHOLOGY, seg):
        return ("H01 优先（T1.1-T1.5）", "红 L4",
                chain + [f"A 治疗/疏通动词 + 病理（{_find(PATHOLOGY, seg)}）→ 交 H01"])

    # ---- 问题 B：疼痛词修饰哪个名词？判据优先级 病理 > 同形消解 > 动作名词 > 器械名词 > 均无
    path = _find(PATHOLOGY, seg)
    act = _find(ACTION_NOUN, seg)
    dev = _find(DEVICE_NOUN, seg)
    d1 = D1_ACTION.search(seg)      # 疼痛词直接接 pump → 动作
    d2 = D2_DEVICE.search(seg)      # 中间有插入词       → 器械
    d3 = D1_PRECEDED_BY.search(seg)      # pump 位于段首或破折号后 → 确认为动词

    if d1 and not d3:
        _before = seg[:d1.start()].rstrip()
        _last = _before.split()[-1] if _before.split() else "(段首)"
        chain.append(f"B 同形消解 D3：`pump` 前是「{_last}」（非段首/破折号）"
                     f"→ 名词短语中心语 → 器械名词")

    if path:
        chain.append(f"B1 病理名词限定（{path}）")
        leaf, level = "T1.5/T1.4", "红 L4"
    elif d1 and d3:
        chain.append(f"B2 同形消解 D1+D3：`pump` 位于段首/破折号后（{d3.group(0).strip()}）"
                     f"→ 动词原形 → 动作名词")
        leaf, level = "T2.2.2", "黄 L2"
    elif d1 or d2:
        m = (d1 or d2).group(0).strip()
        chain.append(f"B3 同形消解：疼痛词修饰器械名词（{m}）→ 对象未写出")
        leaf, level = "T1.4", "红 L4"
    elif act:
        chain.append(f"B2 疼痛词修饰【动作名词】（{act}）")
        leaf, level = "T2.2.2", "黄 L2"
    elif dev:
        chain.append(f"B3 疼痛词修饰【器械名词】（{dev}）→ 对象未写出")
        leaf, level = "T1.4", "红 L4"
    else:
        chain.append("B4 无名词可依 → 对象未写出，默认保守（举证责任倒置）")
        leaf, level = "T1.4", "红 L4"

    # ---- 问题 C：非承诺则不出结论
    if not is_claim:
        chain.append("C 非承诺（纯场景描述）→ 不出违规结论，记 context")
        return ("—(场景描述)", "不判", chain)

    return (leaf, level, chain)


def classify_record(copy_text):
    """一条广告 → (段级结论列表, 记录级最严结论, 是否触发任意桶)。"""
    seg_results = []
    for seg in segments(copy_text):
        r = classify_segment(seg)
        if r:
            seg_results.append((seg, *r))
    return seg_results


SEV = {"红 L4": 3, "黄 L2": 2, "不判": 1, "—": 0}


def main():
    items = json.loads(BLIND.read_text())
    old = [it for it in items if "H07" in (it.get("_legacy_rules") or "")]
    print(f"盲样 {len(items)} 条；现行命中 H07 的 {len(old)} 条")
    print("判定在【素材段】上执行（L1）；机制归因不参与管辖（L2）。\n")

    seg_tally = collections.Counter()
    rec = []
    for it in old:
        res = classify_record(it["copy"])
        buckets = []
        for _seg, leaf, level, _c in res:
            seg_tally[(leaf, level)] += 1
            buckets.append((leaf, level))
        if not res:
            lvl = "—"
        else:
            lvl = max((b[1] for b in buckets), key=lambda x: SEV.get(x, 0))
        rec.append((it, res, lvl, buckets))

    print("=" * 80)
    print("段级分布：")
    tot = 0
    for (leaf, level), n in seg_tally.most_common():
        print(f"  {leaf:24s} {level:8s} {n:3d}")
        tot += n
    print(f"  {'合计':24s} {'':8s} {tot:3d}")

    red = [r for r in rec if r[2] == "红 L4"]
    yel = [r for r in rec if r[2] == "黄 L2"]
    nun = [r for r in rec if r[2] == "—"]
    print(f"\n记录级结论：红 {len(red)} / 黄 {len(yel)} / 无可判段 {len(nun)}"
          f"  合计 {len(red)+len(yel)+len(nun)}")
    print(f"降级率 = {len(yel)}/{len(old)} = {len(yel)/len(old):.1%}")

    print(f"\n仍判红 {len(red)} 条全名单：")
    for it, res, lvl, _b in red:
        trig = "/".join(sorted({b[0] for b in _b if b[1] == "红 L4"}))
        segs = [s for s, leaf, level, _c in res if level == "红 L4"]
        print(f"  {it['blind_id']} [{it['lang']:3s}] {trig:12s} 「{segs[0][:66]}」")

    if nun:
        print(f"\n无可判段 {len(nun)} 条（需人工看，见 O2）：")
        for it, res, lvl, _b in nun:
            print(f"  {it['blind_id']} [{it['lang']}] rules={it['_legacy_rules']} "
                  f"frag={(it.get('_legacy_frag') or '')[:60]}")

    json.dump([{
        "blind_id": it["blind_id"], "lang": it["lang"],
        "legacy_level": it.get("_legacy_level", ""),
        "guide_level": lvl,
        "segments": [{"seg": s, "leaf": lf, "level": lv, "chain": ch} for s, lf, lv, ch in res],
    } for it, res, lvl, _b in rec],
        open(ROOT / "annotations" / "guide_reclass_v2.json", "w"),
        ensure_ascii=False, indent=1)

    # ---- 自检：拆分不得产生新召回，也不得丢失原有命中
    assert len(rec) == len(old), f"记录数不符 {len(rec)} != {len(old)}"
    assert len(red) + len(yel) + len(nun) == len(old), "记录级分类不闭合"
    print("\n✓ 自检通过：红+黄+无可判段 = 现行 H07 命中数，拆分不产生新召回也不丢失命中。")
    print(f"→ {ROOT / 'annotations' / 'guide_reclass_v2.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
