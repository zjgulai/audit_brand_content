#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
disambiguate_pump.py —— 验证「英语 Pump 名词/动词同形」是否真的影响管辖结论。

背景：ANN-GUIDE-001 §3 的 B 步依赖「疼痛词修饰的是动作名词还是器械名词」。
      德语 Abpumpen / 法语 Tirage 是单义的；英语 Pump 兼具名词与动词，
      因此 Painlessly Pump / Pain-Free Pump 的管辖不唯一。这是指南 O3 记录的风险。

本脚本做两件事，都不改判定，只回答一个问题：
    「同形歧义」是纯理论问题，还是真的会改变 51 条记录的结论？
"""
import json, re, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLIND = ROOT / "annotations" / "pain-corpus-blind.json"

PAIN_ADJ = r"(?:pain[- ]?free|painless\w*|no\s+pain|zero\s+pain)"
# 规则 D1：疼痛词 + 空格 + Pump（中间无插入词）→ 副词修饰动词 → 动作
D1 = re.compile(PAIN_ADJ + r"\s+pump(?!\w)", re.I)
# 规则 D2：疼痛词 + 至少一个插入词 + Pump → 形容词修饰器械名词
D2 = re.compile(PAIN_ADJ + r"\s+\S+\s+.*?\bpump(?!\w)", re.I)
# 器械名词作为独立素材（全部出现位置）
DEVICE_ANYWHERE = re.compile(r"\b(pump|tire[- ]?lait|milchpumpe|sacaleches|extractor)\b", re.I)

def segments(t):
    return [s.strip() for s in re.split(r"\s*\|\s*", t) if s.strip()]

def main():
    items = json.loads(BLIND.read_text())
    old = [it for it in items if "H07" in (it.get("_legacy_rules") or "")]

    ambiguous, unambig = [], []
    for it in old:
        segs = segments(it["copy"])
        hits = []
        for s in segs:
            if not re.search(PAIN_ADJ, s, re.I):
                continue
            if re.search(r"\bpump(?!\w)", s, re.I):
                d1 = bool(D1.search(s))
                d2 = bool(D2.search(s))
                hits.append((s, d1, d2))
        if hits:
            ambiguous.append((it, hits))
        else:
            unambig.append(it)

    print("=" * 84)
    print(f"涉及英语 Pump 同形的记录：{len(ambiguous)} 条")
    print(f"不涉及（德语 Abpumpen / 法语 Tirage / 西语动词短语）：{len(unambig)} 条\n")

    print("逐条同形判定：")
    tally = collections.Counter()
    for it, hits in ambiguous:
        s, d1, d2 = hits[0]
        if d1 and not d2:
            r = "→ 动作（D1：疼痛词直接接 Pump）→ T2.2.2 黄"
        elif d1 and d2:
            r = "→ 歧义（同段既有 D1 又有 D2）"
        elif d2 and not d1:
            r = "→ 器械（D2：疼痛词与 Pump 之间有插入词）→ T1.4 红"
        else:
            r = "→ 未命中规则"
        tally[r] += 1
        print(f"  {it['blind_id']}   「{s[:58]}」")
        print(f"          {r}")

    print("\n同形消解结果分布：")
    for k, n in tally.most_common():
        print(f"  {n:3d}  {k}")

    # ---- 关键测试：『器械名词出现在该记录别处』是否与『该段是器械主张』一致？
    print("\n" + "=" * 84)
    print("关键测试：若某段判为『动作』，同一记录的别处是否也出现器械名词？")
    print("（若大量『动作』段所在记录的别处都有器械名，说明器械名词是模板背景，")
    print("  不足以推翻该段的动作管辖 → O3 的实际影响面小于表面）")
    both = 0
    act_only = 0
    for it, hits in ambiguous:
        for s, d1, d2 in hits:
            if d1 and not d2:                       # 本段判为动作
                others = [x for x in segments(it["copy"]) if x != s]
                if any(DEVICE_ANYWHERE.search(x) for x in others):
                    both += 1
                else:
                    act_only += 1
    print(f"  判为动作、且记录别处有器械名词 : {both} 段")
    print(f"  判为动作、且记录别处无器械名词 : {act_only} 段")

    json.dump({"ambiguous": len(ambiguous), "unambiguous": len(unambig),
               "distribution": dict(tally)},
              open(ROOT / "annotations" / "pump_ambiguity.json", "w"),
              ensure_ascii=False, indent=1)
    print(f"\n→ {ROOT / 'annotations' / 'pump_ambiguity.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
