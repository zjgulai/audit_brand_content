#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb_sample_extract.py —— 从样本表的 `原文反馈` 里**逐字**取出审核人原话

## 为什么需要它

2026-10-20 委托方指出样本表两个毛病，当场量化后：

  ① `具体原因/分析` **151/186（81.2%）** 至少命中一个聊天特征
     （`@某人` 131 条 / 寒暄催促 115 条 / 粘贴标记 108 条 /
      `【审核问题】` 前缀 51 条）。这一列存的是**整段群聊**，不是判定理由。
  ② `原因分类` **51/186（27.4%）为空** —— 与①同源：分类信息从来没被写进结构化字段。

但同时探明：`原文反馈` 里 **186/186** 都有 `【审核 · 时间 · 人名】` 段，
可解析出时间与人名，且 `审核人` 字段与段里的名字 **186 一致 / 0 不一致**。
也就是说 —— **理由能救，只是它不在理由列里，在反馈原文里。**

## 本文件刻意做死的四件事

**一、一个字都不改。** 取出的「原话」必须是 `原文反馈` 的**连续子串**，
   本文件用 `text.find()` 回切一遍并断言 —— 润色、补标点、纠错一律不做。
   gold 是评测的基准答案；改写基准答案，等于把「模型判得对不对」
   变成「模型像不像我改写的版本」。（与 `gold_pilot_fetch.py` 第三条同一口径。）

**二、切不出来就说切不出来。** 没有 `【审核】` 段的记录落进 `unparsed`，
   **不猜、不跳过、不记成空串**。空串与「没抽到」在报告里必须长得不一样
   （AGENTS.md §2.4.1）。

**三、只抽审核人原话，不拆要点。** 委托方 2026-10-20 明确选择「只重抽审核人原话」。
   `【问题要点】` 的拆分规则尚未拍板 —— 拆错比不拆更贵，因为拆出来的
   会被当成判据用。要拆的那天，另开一个函数并另配反向对照。

**四、`--check` 不写盘。** 写盘只在显式 `--write` 时发生。

## 已知做不到的事（写在这里，免得下一个人以为是 bug）

**图 ↔ 理由无法对应。** 344 个附件的文件名 100% 是飞书 API 原样返回的
`sN_N.png`（已核实：直接调 `bitable/v1/.../records` 拿到的就是这组名），
重命名发生在导入多维表之前。而正文里能同时满足
「编号条目数 = 附件数 = `!Image` 数」的只有 **3/129** 条。
所以本文件**不产出**逐图定位，只产出整条理由。见 KB-GAP-17。

用法
----
    python3 tools/kb_sample_extract.py --check    # 只报告，不写盘
    python3 tools/kb_sample_extract.py --write    # 写 research/kb/样本理由-v1.json
    python3 tools/kb_sample_extract.py --self-test  # 反向对照（不读快照）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# ★ 2026-10-20：逐字数据**不许进仓**。
#   本仓库是公开的（AGENTS.md §2.6），而这份产出里是**审核人真名 + 飞书内部原话**。
#   所以落盘分两处：
#     · 逐字明细 → 仓外 `~/audit-data/kb/samples/`（与 gold 试点同一个落地根）
#     · 聚合读数 → 仓内 `research/kb/样本理由-摘要-v1.json`（只有计数，无原文、无人名）
#   这与 `gold_pilot_fetch.py` 的「落盘目录必须在仓外，且 0700」是同一条口径。
OUT_VERBATIM = os.path.join(os.path.expanduser("~"), "audit-data", "kb", "samples",
                            "样本理由-v1.json")
OUT_SUMMARY = os.path.join(REPO, "research", "kb", "样本理由-摘要-v1.json")

# 段头：`【审核 · 2026-09-17 18:44 · 吴礼芳】` / `【项目方 · …】` / `【终审-@吴礼芳】`
SEG_RE = re.compile(r"^【([^】]{1,40})】", re.M)
AUDIT_RE = re.compile(r"^审核\s*(?:·\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*([0-9]{2}:[0-9]{2}))?\s*(?:·\s*(.+?))?\s*$")


def _load_snapshot():
    """读 `research/live/LATEST.json` 指向的快照里的样本表。读不到返回 None。"""
    ptr = os.path.join(REPO, "research", "live", "LATEST.json")
    if not os.path.exists(ptr):
        return None, None
    try:
        latest = json.load(open(ptr, encoding="utf-8"))
        path = os.path.join(REPO, "research", "live", latest["latest"])
        doc = json.load(open(path, encoding="utf-8"))
    except (OSError, KeyError, json.JSONDecodeError):
        return None, None
    return latest, (doc.get("sources") or {}).get("kb_samples")


def split_segments(text):
    """按 `^【…】` 段头切段。返回 [(header, body)]，body 是原文子串。

    ★ 刻意用切片而不是正则捕获来取 body：正则捕获会**重建**字符串，
      而重建过的字符串与原文「看起来一样」但 `==` 可能不等。本文件要的是子串，
      因为逐字校验（`_verify_verbatim`）比的就是「它还在不在原文里」。
    """
    marks = [(m.group(1), m.start(), m.end()) for m in SEG_RE.finditer(text)]
    out = []
    for i, (header, hstart, hend) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        body = text[hend:end].strip()
        out.append((header, body))
    return out


# 【审核】段里装的**不一定**是判定理由。实测 186 条里 79 条（42%）这一段
# 其实是需求简报（项目名/设计要求/业务背景/采购要求）—— 项目方连需求带图
# 一起发过来，审核人的回应被截在同一段里，或者这一段压根就是项目方的原话。
# 这个区分必须出现在产出里，否则「重抽出来的原话」会被当成 gold 直接喂评测。
BRIEF_RE = re.compile(r"(\*\*项目名|\*\*设计要求|业务背景|项目背景|采购要求"
                      r"|\*\*.{2,12}\*\*：)")
VERDICT_RE = re.compile(r"(建议|应该|可以|不对|去掉|不合适|应该是|需要改"
                        r"|问题|原因|注意|避免)")


def classify(text):
    """粗分「这段是需求简报还是判定理由」。**只作提示，不作判据。**

    返回 (brief_hits, verdict_hits, kind)：
      kind = "brief"      简报特征 ≥2 且判定特征 ≤1 —— **不能当 gold**
           = "verdict"    判定特征 ≥2 且有建议类动词
           = "mixed"      两者都有
           = "thin"       长度过短或两者都弱 —— 需人看
    """
    b = len(BRIEF_RE.findall(text))
    v = len(VERDICT_RE.findall(text))
    if b >= 2 and v <= 1:
        kind = "brief"
    elif v >= 2 and b == 0:
        kind = "verdict"
    elif b and v:
        kind = "mixed"
    else:
        kind = "thin"
    return b, v, kind


def extract(records):
    """逐条抽审核人原话。返回 (items, unparsed)。"""
    items, unparsed = [], []
    for rec in records:
        f = rec.get("fields") or {}
        text = str(f.get("原文反馈") or "")
        rid = rec.get("record_id")
        found = None
        for header, body in split_segments(text):
            m = AUDIT_RE.match(header.strip())
            if m:
                found = (m.group(1), m.group(2), (m.group(3) or "").strip(), body)
                break
        if not found:
            unparsed.append({"record_id": rid, "why": "原文反馈里没有可解析的【审核】段",
                             "has_feedback": bool(text)})
            continue
        _, _, who_in_text, body = found
        b_hits, v_hits, kind = classify(body)
        items.append({
            "record_id": rid,
            "审核人_字段": (f.get("审核人") or "").strip() or None,
            "审核人_原文": who_in_text or None,
            "分类": (f.get("分类") or None),
            "原因分类": (f.get("原因分类") or "").strip() or None,
            "品线": (f.get("品线") or None),
            "素材类型": (f.get("素材类型") or None),
            "渠道市场": (f.get("渠道/市场") or None),
            "原话": body,
            "原话字数": len(body),
            "图片数": len(f.get("图片素材") or []),
            # ★ 供下游判断「这一条能不能当 gold」，不是判据本身。
            #   brief 段是**需求简报**，重抽得再准也不能当判定理由用。
            "简报特征数": b_hits,
            "判定特征数": v_hits,
            "体裁": kind,
            "_原话非空": bool(body),
        })
    return items, unparsed


def _verify_verbatim(items, records):
    """反向对照：每条「原话」都必须是它自己那条 `原文反馈` 的连续子串。

    ★ 这一条是**内容级**断言，不是计数断言。只比「长度相同」或「条数相同」
      会在「抄错了一行」时仍然全绿 —— 本项目 §2.4 点过的假执行点。
    """
    by_id = {r.get("record_id"): str((r.get("fields") or {}).get("原文反馈") or "")
             for r in records}
    bad = []
    for it in items:
        src = by_id.get(it["record_id"], "")
        if it["原话"] and it["原话"] not in src:
            bad.append(it["record_id"])
    return bad


def summary(items, unparsed, total):
    people_ok = sum(1 for it in items
                    if it["审核人_原文"] and it["审核人_字段"] == it["审核人_原文"])
    people_diff = [it for it in items
                   if it["审核人_原文"] and it["审核人_字段"] != it["审核人_原文"]]
    empty = sum(1 for it in items if not it["原话"])
    lens = sorted(it["原话字数"] for it in items) or [0]
    kinds = {}
    for it in items:
        kinds[it.get("体裁") or "?"] = kinds.get(it.get("体裁") or "?", 0) + 1
    return {
        "记录总数": total,
        "抽到审核段": len(items),
        "切不出审核段": len(unparsed),
        "原话为空": empty,
        "审核人_字段与原文一致": people_ok,
        "审核人_字段与原文不一致": len(people_diff),
        "不一致明细": [{"record_id": x["record_id"], "字段": x["审核人_字段"],
                        "原文": x["审核人_原文"]} for x in people_diff[:10]],
        "原话字数_p10": lens[len(lens) // 10],
        "原话字数_p50": lens[len(lens) // 2],
        "原话字数_p90": lens[len(lens) * 9 // 10],
        "原话字数_max": lens[-1],
        # ★ 体裁分布：这是本条最该被看见的数。brief 占比高，说明
        #   「重抽出来了」与「抽到的是判定理由」是两件事。
        "体裁分布": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
        "可直接当理由(verdict)": kinds.get("verdict", 0),
        "是需求简报(brief)": kinds.get("brief", 0),
    }


# ───────────────────────── 反向对照 ─────────────────────────

def self_test() -> int:
    """喂已知好/坏样本，证明抽取器**该对的对、该错的分得开**。不读快照。"""
    cases = []

    def ok(name, cond, detail=""):
        cases.append((name, bool(cond), detail))

    # 1) 标准两段
    t1 = ("【项目方 · 2026-09-17 18:44】@吴礼芳 看看呀\n!Image\n!Image\n"
          "【审核 · 2026-09-17 18:44 · 吴礼芳】@贺美霞 一般用吸奶器吸奶的时候，"
          "是不会这样抱着宝宝的")
    segs = split_segments(t1)
    body1 = [b for h, b in segs if h.startswith("审核")]
    ok("标准两段：切得出审核段", len(body1) == 1)
    ok("标准两段：原话是原文子串", body1 and body1[0] in t1,
       repr(body1[0][:20]) if body1 else "空")
    ok("标准两段：原话不含项目方那段", body1 and "画一个" not in body1[0])
    m = AUDIT_RE.match("审核 · 2026-09-17 18:44 · 吴礼芳")
    ok("段头解析：时间", m and m.group(1) == "2026-09-17", str(m and m.groups()))
    ok("段头解析：人名", m and (m.group(3) or "").strip() == "吴礼芳")

    # 2) 只有项目方段 → 必须进 unparsed，不许记成空串
    t2 = "【项目方 · 2026-09-05 00:00】麻烦看看呀"
    got, unp = extract([{"record_id": "r2", "fields": {"原文反馈": t2}}])
    ok("无审核段：进 unparsed 而不是空串", len(got) == 0 and len(unp) == 1,
       f"got={len(got)} unp={len(unp)}")

    # 3) 审核段为空正文 → 保留记录，但标记 _原话非空=False
    t3 = "【审核 · 2026-09-05 00:00 · 张悦】"
    got, unp = extract([{"record_id": "r3", "fields": {"原文反馈": t3}}])
    ok("空正文：仍然抽出条目（不丢记录）", len(got) == 1 and unp == [])
    ok("空正文：_原话非空=False", got and got[0]["_原话非空"] is False)

    # 4) 逐字断言必须能抓到「改写了一个字」
    recs = [{"record_id": "r4", "fields": {"原文反馈": t1}}]
    items, _ = extract(recs)
    ok("逐字对照：原件通过", _verify_verbatim(items, recs) == [])
    tampered = [dict(items[0])]
    tampered[0]["原话"] = items[0]["原话"].replace("不会", "不可能")
    ok("逐字对照：改一个字必须红", _verify_verbatim(tampered, recs) == ["r4"])

    # 5) 人名不一致要能被数出来（不是静默吞掉）
    recs5 = [{"record_id": "r5",
              "fields": {"原文反馈": "【审核 · 2026-09-05 00:00 · 张三】原话", "审核人": "李四"}}]
    it5, _ = extract(recs5)
    s5 = summary(it5, [], 1)
    ok("人名不一致：计数为 1", s5["审核人_字段与原文不一致"] == 1, json.dumps(s5, ensure_ascii=False)[:120])

    # 6) 无审核人字段时不许崩
    recs6 = [{"record_id": "r6", "fields": {"原文反馈": "【审核 · 2026-09-05 00:00 · 王五】原话"}}]
    it6, _ = extract(recs6)
    ok("审核人字段缺失：不崩，_字段=None", it6 and it6[0]["审核人_字段"] is None)

    passed = sum(1 for _, c, _ in cases if c)
    for name, cond, detail in cases:
        print(f"  {'✅' if cond else '❌'} {name}" + (f"　{detail}" if not cond and detail else ""))
    print(f"\n{'✅' if passed == len(cases) else '❌'} {passed}/{len(cases)} 项通过")
    return 0 if passed == len(cases) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="从样本表原文反馈里逐字取出审核人原话")
    ap.add_argument("--write", action="store_true", help="写 research/kb/样本理由-v1.json")
    ap.add_argument("--check", action="store_true", help="只报告，不写盘（默认）")
    ap.add_argument("--self-test", action="store_true", help="反向对照，不读快照")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    latest, src = _load_snapshot()
    if src is None:
        print("⚠️ 读不到样本快照（research/live/LATEST.json）。先跑 python3 tools/live_snapshot.py")
        return 2
    records = src.get("records") or []
    items, unparsed = extract(records)
    bad = _verify_verbatim(items, records)
    s = summary(items, unparsed, len(records))

    print("=" * 70)
    print(f"快照 {latest['latest']}　样本 {len(records)} 条")
    print("=" * 70)
    for k, v in s.items():
        if k != "不一致明细":
            print(f"  {k:26} {v}")
    print(f"  {'逐字校验（原话必须是原文子串）':26} "
          f"{'✅ 全部通过' if not bad else f'❌ {len(bad)} 条不符 {bad[:5]}'}")

    if bad:
        print("\n❌ 逐字校验失败 —— 原话是重建出来的，不是原文子串。不许写盘。")
        return 1

    if a.write:
        doc = {
            "schema": "sample-reasons/v1",
            "generated_by": "tools/kb_sample_extract.py",
            "snapshot": latest.get("latest"),
            "captured_at_utc": latest.get("captured_at_utc"),
            "$口径": "原话 = `原文反馈` 里 `【审核 · 时间 · 人名】` 段的逐字正文。"
                     "润色/补标点/纠错一律不做。切不出审核段的记录在 unparsed 里，不猜。",
            "$做不到": "图 ↔ 理由无法对应（附件名是导入前的占位名，见 KB-GAP-17）；"
                       "【问题要点】未拆分（委托方 2026-10-20 定为只抽原话）。",
            "summary": s,
            "unparsed": unparsed,
            "items": items,
        }
        # ① 逐字明细 → 仓外（含真名与原话，绝不进公开仓）
        d = os.path.dirname(OUT_VERBATIM)
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o700)
        # 仓外守卫：realpath 后仍在仓内 → 拒写（与 gold_pilot_fetch._prepare_landing 同口径）
        real_d = os.path.realpath(d)
        if real_d == os.path.realpath(REPO) or real_d.startswith(os.path.realpath(REPO) + os.sep):
            print(f"❌ 落地目录经 realpath 解析后在仓内：{real_d}。拒绝写入。")
            return 2
        with open(OUT_VERBATIM, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        os.chmod(OUT_VERBATIM, 0o600)

        # ② 聚合读数 → 仓内（只有计数与分布，无原文、无人名）
        pub = {
            "schema": "sample-reasons-summary/v1",
            "generated_by": "tools/kb_sample_extract.py --write",
            "snapshot": latest.get("latest"),
            "captured_at_utc": latest.get("captured_at_utc"),
            "$why_only_counts": "逐字明细（含审核人真名与飞书内部原话）落在仓外 "
                                "~/audit-data/kb/samples/，不进本公开仓。"
                                "这里只有聚合读数，因此可以安全入库与复算。",
            "$口径": "原话 = `原文反馈` 里 `【审核 · 时间 · 人名】` 段的逐字正文，不做任何改写。",
            "$做不到": ["图 ↔ 理由无法对应：附件名是导入前的占位名（KB-GAP-17）",
                        "【问题要点】未拆分：委托方 2026-10-20 定为只抽原话"],
            "summary": s,
            "逐字明细": {
                "路径": "~/audit-data/kb/samples/样本理由-v1.json",
                "在仓外": True,
                "权限": "0600",
                "行数": len(items),
            },
        }
        with open(OUT_SUMMARY, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(pub, ensure_ascii=False, indent=1) + "\n")
        print(f"\n✅ 逐字明细（仓外 0700/0600）：{OUT_VERBATIM}")
        print(f"   {len(items)} 条 + {len(unparsed)} 条未解析")
        print(f"✅ 聚合读数（仓内，可入库）：{os.path.relpath(OUT_SUMMARY, REPO)}")
    else:
        print("\n（只报告，未写盘。加 --write 落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
