#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_migration_fidelity.py —— 旧规则集 → 骨架 v1 的**迁移保真度对账**

## 为什么要有这个脚本

D15 立案时写的是：「**源表的规则扫描漏放 3 条**」。这是一句指控。
做完对账后，这句话是**错的**，而且错的方向很具体 —— 被指控的是源表，
真正出问题的是**我们自己的迁移**。

这个脚本存在的理由，就是让这类指控**不必靠回忆**：源表那次扫描的结果
（`records.json` 的 `_hit_rules`，用的还是旧的 H/M/U 编号）在盘上，
新引擎在盘上，于是**两次扫描可以逐行对账**。
R2 §2989 说过「这两次扫描谁更全，今天没有任何东西在比」—— 本脚本就是那个「比」。

## 四条轴

| 轴 | 问的问题 | 病灶 |
|---|---|---|
| 0 证据 | 旧规则的 `exceptions` 到底是「放行」还是「降级」？ | 语义前提，必须先钉死 |
| 1 例外语义 | 94 个旧豁免词迁到新系统后，语义有没有被翻转？ | `treat yourself` 被翻成降级 |
| 2 检出覆盖 | 旧关键词/正则有没有在新规则里丢掉？ | 旧词无归属 = 潜在漏检 |
| 3 逐行对账 | 同一批 291 行，两次扫描分歧在哪、为什么？ | 分歧必须逐条归因，不许笼统 |

## 轴 0 为什么能钉死语义

旧规则 `H01` 的 `exceptions` 里有 `treat yourself`，`keywords` 里有 `treat`。
源表里同一批次 `Savannah-20260825` 的三条记录构成天然对照组：

    i=265  含 `treat` + 含 `treat yourself`  →  源表 0 命中，`合规·绿`
    i=270  不含 `treat`                       →  源表命中 H07,U04，`高危·红`
    i=271  不含 `treat`                       →  源表命中 H07,U04，`高危·红`

同一次扫描、同一批次：**没有 `treat yourself` 的都红了，有的绿了**。
所以旧 `exceptions` = **放行**（不命中），不是降级 —— 这是实测出来的，
不是从文档抄的。本脚本把这条对照**每次重跑**，它一旦不成立，整个结论就该推翻。

## 用法

  python3 research/governance/audit_migration_fidelity.py           # 对账 + 写账
  python3 research/governance/audit_migration_fidelity.py --check    # 只比对不改盘
  python3 research/governance/audit_migration_fidelity.py --md       # 只打印
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

GOV = Path(__file__).resolve().parent
SKEL = GOV / "skeleton"
DATA = SKEL / "_data"
RECORDS = DATA / "records.json"
RULES_RAW = DATA / "rules_raw.json"
RULES_NEW = SKEL / "rules-v1.json"
WHITELIST = SKEL / "whitelist-v1.json"
GUARDS = SKEL / "context-guards-v1.json"
OUT = DATA / "迁移保真度.json"

sys.path.insert(0, str(SKEL))
import judge as J  # noqa: E402
import score as S  # noqa: E402

CONTRACT_VERSION = "migration-fidelity-v1"

# ── 守卫类型里哪些「本来就不该降级」 ────────────────────────────────────────
# ★ 用制品自己的分类，不自造分类器。
#   设计文档 §F 的教条是「免责声明不是许可证」—— 那条教条**只对否定式成立**：
#   一句写着「not intended to treat」的话，把它当免罪符是危险的，降级是对的。
#   但一句写着「treat yourself」的话里**根本没有医疗主张**，它不是免责声明，
#   是词义消歧；对它降级 = 把一个正确放行的广告标成可疑。
DISCLAIMER_TYPES = {"免责声明", "否定"}

# ★★ 2026-09-17 撤回：这里原本有一组按 `guard_type` 切出来的「甲/乙」分类，
#    结论是「甲 14 个根本不是主张 → 应改回放行」。**那个结论错了，已删除。**
#
#    错在哪：`guard_type` 是**机器推导**的（词条自己写着
#    `guard_type_derivation: 机器推导（表面词素）· 语义归属待法务确认`），
#    我拿一个待确认的启发式当了事实，并据此提出要改生产词表。
#    更具体地错了两处：
#      · 把 `natural let-down` 一类归成「无主张」—— 但源表自己的命中原因里
#        写明「放松叙事+限定语（natural let-down/may help）**走 M07 语境守卫**」，
#        即**改档**，不是放行。旧设计是三层，我压成了两层。
#      · 把 `gently` 算成「跟随白名单词根 gentle」—— 但 `gentle` 在飞书表里
#        是 `status=quarantined`，按 W3 隔离词**走降级带、不放行**。
#        所以 `gently` 与 `gentle` 同通道，不是缺陷。
#
#    教训与本项目反复在治的病同形：**读到一个字段就推一个语义**。
#    下面这组数字因此全部改成**实测**：拿词本身去问引擎，看它拿到什么带。
#    实测不需要相信任何分类，只需要相信引擎的输出。


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load():
    recs = json.loads(RECORDS.read_text(encoding="utf-8"))
    raw = json.loads(RULES_RAW.read_text(encoding="utf-8"))
    rules = json.loads(RULES_NEW.read_text(encoding="utf-8"))["rules"]
    wl = json.loads(WHITELIST.read_text(encoding="utf-8"))["words"]
    gd = json.loads(GUARDS.read_text(encoding="utf-8"))["words"]
    return recs, raw, rules, wl, gd


# ══════════════════════════════════════════════════════════════════════
#  轴 0 · 证据：旧 exceptions 是「放行」还是「降级」
# ══════════════════════════════════════════════════════════════════════
def axis0_exception_semantics(recs, raw):
    """同批次对照组。少了它，后面所有推论都建在一个未验证的假设上。"""
    by_rule = {r["rule_id"]: r for r in raw}
    h01 = by_rule["H01"]
    probe, exempt = "treat", "treat yourself"
    assert probe in h01["keywords"], "前提变了：H01 关键词里没有 treat"
    assert exempt in h01["exceptions"], "前提变了：H01 豁免词里没有 treat yourself"

    # 找出所有能构成对照的记录：命中集合里含有 H01（说明 treat 类词确实被扫过）
    # ★ 更严的取法：按「同一批次前缀」分组，组内必须既有含豁免词的、也有不含的。
    def batch_of(name: str) -> str:
        m = re.match(r"^([A-Za-z]+-\d{8})", name or "")
        return m.group(1) if m else ""

    groups: dict[str, list[int]] = collections.defaultdict(list)
    for i, r in enumerate(recs):
        b = batch_of(str(r.get("广告名称") or ""))
        if b:
            groups[b].append(i)

    controls = []
    for b, idxs in groups.items():
        with_ex = [i for i in idxs
                   if exempt.lower() in (S.rec_text(recs[i]) or "").lower()]
        without = [i for i in idxs
                   if exempt.lower() not in (S.rec_text(recs[i]) or "").lower()]
        if not with_ex or not without:
            continue
        # 对照点：不含豁免词的那一侧，源表必须**有命中**（否则不是有效对照）
        hit_side = [i for i in without if recs[i].get("_hit_rules")]
        if not hit_side:
            continue
        controls.append({
            "batch": b,
            "含豁免词_源表均未命中": all(not recs[i].get("_hit_rules") for i in with_ex),
            "含豁免词": [{"i": i, "命中": recs[i].get("_hit_rules"),
                        "风险等级": recs[i].get("风险等级")} for i in with_ex],
            "不含豁免词": [{"i": i, "命中": recs[i].get("_hit_rules"),
                          "风险等级": recs[i].get("风险等级")} for i in hit_side],
        })

    ok = bool(controls) and all(c["含豁免词_源表均未命中"] for c in controls)
    return {
        "$claim": "旧规则的 exceptions = **放行**（不命中），不是降级。",
        "$method": "同批次天然对照：同一次扫描里，含豁免词的记录绿、不含的红。",
        "对照组": controls,
        "成立": ok,
        "$若为否": "轴 1/轴 3 的全部推论都要推翻重做 —— 本脚本会直接报红。",
    }


# ══════════════════════════════════════════════════════════════════════
#  轴 1 · 94 个旧豁免词的去向与语义
# ══════════════════════════════════════════════════════════════════════
def axis1_exception_drift(recs, raw, rules, wl, gd):
    """旧豁免词今天还起不起作用 —— **实测**，不靠任何分类字段。

    ★ 判据：只有「**自己就会命中本规则**」的豁免词，豁免才真正起过作用。
      其余的词（例如 `不用于治疗` 之于关键词表）从来不自我触发，谈不上被翻转。
      对这些自我触发词，直接把词本身喂给引擎：
        band=pass       → 旧语义（放行）**保住了**
        band=downgrade  → 变成了**降级**
        无带            → 旧语义**彻底消失**，按满档判险
      三个桶之和必须等于自我触发词总数（守恒），否则判据漏了词。
    """
    wl_map = {w["word"].lower(): w for w in wl}
    gd_map = {w["word"].lower(): w for w in gd}

    rows = []
    for lr in raw:
        rid = lr["rule_id"]
        kws = [k.lower() for k in (lr.get("keywords") or [])]
        pats = lr.get("patterns") or []
        for w in (lr.get("exceptions") or []):
            k = w.lower()
            self_trigger = (any(k in kk or kk in k for kk in kws)
                            or any(re.search(p, w, re.I) for p in pats if p))
            g, wle = gd_map.get(k), wl_map.get(k)
            if g is not None:
                dest = "语境守卫"
                wired = bool(g.get("wired"))
            elif wle is not None:
                dest = "白名单"
                wired = wle.get("status") == "active"
            else:
                dest, wired = "无归属", False
            # 实测：把词本身喂给引擎，看它拿到什么带
            band, disp, sev, fired = "未自我触发", "", "", False
            if self_trigger:
                v = J.judge(w)
                fired = rid in v["verdict"]["rules_hit"]
                for h in v["hits"]:
                    if h["parent_rule"] == rid:
                        band = (h.get("band") or {}).get("kind") or "无带"
                disp, sev = v["verdict"]["disposition"], v["verdict"]["severity"]
            rows.append({
                "旧规则": rid, "词": w, "去向": dest, "已接线": wired,
                "自我触发": self_trigger, "实测带": band,
                "实测处置": disp, "实测等级": sev, "实测命中": fired,
            })

    st = [x for x in rows if x["自我触发"]]
    keep = [x for x in st if x["实测带"] == "pass"]
    down = [x for x in st if x["实测带"] == "downgrade"]
    gone = [x for x in st if x["实测带"] == "无带"]

    # 这条词实际翻掉了哪些记录：源表没命中、引擎命中了它所降级的那条规则
    flipped = collections.Counter()
    for i, r in enumerate(recs):
        src = set(r.get("_hit_rules") or [])
        t = (S.rec_text(r) or "").lower()
        v = J.judge(S.rec_text(r), product_line=(r.get("品线") or None),
                    ad_type=r.get("广告类型"))
        gained = set(v["verdict"]["rules_hit"]) - src
        for rr in rows:
            if rr["词"].lower() in t and rr["旧规则"] in gained:
                flipped[rr["词"]] += 1
                rr.setdefault("_flip_records", []).append(i)
    for rr in rows:
        rr["翻掉的记录数"] = flipped.get(rr["词"], 0)

    return {
        "旧豁免词总数": len(rows),
        "去向分布": dict(collections.Counter(x["去向"] for x in rows)),
        "守卫类型分布": dict(collections.Counter(
            (gd_map.get(x["词"].lower()) or {}).get("guard_type") for x in rows
            if gd_map.get(x["词"].lower()))),
        # ── 实测三桶（守恒：三者之和 = 自我触发词数）──────────────
        "自我触发词数": len(st),
        "仍放行": sorted(x["词"] for x in keep),
        "仍放行_条数": len(keep),
        "变成降级": sorted(x["词"] for x in down),
        "变成降级_条数": len(down),
        "满档判险_无带": sorted(x["词"] for x in gone),
        "满档判险_无带_条数": len(gone),
        "翻掉记录的词": dict(flipped),
        "逐词": rows,
    }


# ══════════════════════════════════════════════════════════════════════
#  轴 1b —— **已撤回（2026-09-17）**
#
#  原判据：同根词的形态变体被拆进语义相反的两张表（`comfort` 进白名单=放行、
#          `comfortable` 进语境守卫=降级，`gentle` 对 `gentler`/`gently`）。
#
#  **这个判据是错的，整段删除。** 错因是可复算的：白名单表里的 `comfort`/`gentle`
#  是 `status=quarantined`，而按 vocab.py 的组带逻辑
#  （`band_target(rule, w)`，逐词判落点）与不变量 W3「隔离词不得进入放行带」，
#  隔离词落到**降级带**。实测确认：
#
#      pain relief                    → auto_reject  无带
#      pain relief + gentle           → downgrade（词=gentle）
#      pain relief + comfort          → downgrade（词=comfort）
#      pain relief + comfortable      → downgrade（词=comfort, comfortable）
#      pain relief + gentler          → downgrade（词=gentle, gentler）
#
#  五个词**全在同一通道**，不存在「相反通道」。我此前只读了 `去向=白名单`
#  这一个字段就推出「放行」，而真正决定通道的是 `status` ——
#  与本项目反复在治的病同形：**读到一个字段就推一个语义**。
#
#  保留这段撤回记录而不是删干净，是因为「改口」本身要可审计：
#  下一版若有人再看到 `comfort` 在白名单里，不该重新犯同一个推断。
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
#  轴 2 · 关键词 / 正则的迁移覆盖
# ══════════════════════════════════════════════════════════════════════
def axis2_coverage(raw, rules, wl, gd):
    new_kw = collections.defaultdict(set)
    new_pat = collections.defaultdict(set)
    all_kw, all_pat = set(), set()
    for r in rules:
        ks = {k.lower() for k in (r["match"].get("keywords") or [])}
        ps = set(r["match"].get("patterns") or [])
        new_kw[r["parent_rule"]] |= ks
        new_pat[r["parent_rule"]] |= ps
        all_kw |= ks
        all_pat |= ps
    wlw = {w["word"].lower() for w in wl}
    gdw = {w["word"].lower() for w in gd}

    per_rule, orphan = [], []
    for lr in raw:
        rid = lr["rule_id"]
        old_kw = {k.lower() for k in (lr.get("keywords") or [])}
        old_pat = set(lr.get("patterns") or [])
        drop_kw = old_kw - new_kw[rid]
        drop_pat = old_pat - new_pat[rid]
        dest = collections.Counter()
        for k in drop_kw:
            if k in all_kw:
                dest["改归属到别的规则"] += 1
            elif k in wlw:
                dest["迁到白名单"] += 1
            elif k in gdw:
                dest["迁到语境守卫"] += 1
            elif any(re.search(p, k, re.I) for p in all_pat if p):
                dest["新正则仍覆盖"] += 1
            else:
                dest["★ 无归属且无覆盖"] += 1
                orphan.append({"旧规则": rid, "词": k})
        per_rule.append({
            "旧规则": rid, "旧关键词": len(old_kw), "新关键词": len(new_kw[rid]),
            "丢词": len(drop_kw), "旧正则": len(old_pat), "新正则": len(new_pat[rid]),
            "丢正则": len(drop_pat), "丢词去向": dict(dest),
            "无归属词": sorted(k for k in drop_kw if any(
                o["旧规则"] == rid and o["词"] == k for o in orphan)),
            "丢正则明细": sorted(drop_pat),
        })
    by_rule = collections.Counter(o["旧规则"] for o in orphan)
    return {
        "逐规则": per_rule,
        "无归属词总数": len(orphan),
        "无归属词按规则": dict(by_rule),
        "无归属词明细": orphan,
    }


# ══════════════════════════════════════════════════════════════════════
#  轴 3 · 逐行对账（源表扫描 vs 新引擎）
# ══════════════════════════════════════════════════════════════════════
def axis3_line_by_line(recs, raw, rules):
    by_rule = {r["rule_id"]: r for r in raw}
    rows, agree = [], 0
    for i, r in enumerate(recs):
        text = S.rec_text(r)
        src = set(r.get("_hit_rules") or [])
        v = J.judge(text, product_line=(r.get("品线") or None),
                    ad_type=r.get("广告类型"))
        eng = set(v["verdict"]["rules_hit"])
        if src == eng:
            agree += 1
            continue
        low = (text or "").lower()

        def explain(rid):
            """引擎新增了 rid，源表没有 —— 为什么？"""
            ex = [e for e in (by_rule.get(rid, {}).get("exceptions") or [])
                  if e.lower() in low]
            if ex:
                return {"原因": "旧豁免词被翻成降级（迁移回归）", "旧豁免词": ex}
            return {"原因": "引擎新增检出", "旧豁免词": []}

        def lost(rid):
            """源表命中 rid，引擎没有 —— 为什么？

            ★ 三种原因必须分开，因为处置完全不同：
              ① 语料缺口  → 去修**采集**（源表扫描看到的资产比我们存下来的多）
              ② 改归属/改档 → 去**审规则归属**（词还在，但挂到了另一条、常常更轻的规则上）
              ③ 真丢了    → 去**补规则**（词在新系统里没有家）
            """
            lr = by_rule.get(rid, {})
            kw = [k for k in (lr.get("keywords") or []) if k.lower() in low]
            pat = [p for p in (lr.get("patterns") or [])
                   if re.search(p, text or "", re.I)]
            if not kw and not pat:
                # ② 的线索在源表自己的 命中片段 里 —— 它记了当时到底命中了什么
                frag = str(r.get("命中片段") or "")
                own = [p.partition(":")[2] for p in frag.split("/")
                       if p.strip().startswith(rid)]
                return {"原因": "★ 语料缺口：源表扫描看到的文案我们没采到",
                        "命中词": [], "命中正则": [],
                        "源表自报片段": own[0].split(",") if own else []}
            # 词能命中却不出结果 → 该词被挪到了别的规则（或别的档）
            holder = []
            for k in kw:
                for rr in rules:
                    if k in {x.lower() for x in (rr["match"].get("keywords") or [])}:
                        holder.append({"词": k, "现挂": rr["rule_key"],
                                       "现属旧规则": rr["parent_rule"],
                                       "现档": rr["severity"]})
            if holder:
                return {"原因": "★ 触发物被改归属到别的规则（档位可能被降）",
                        "命中词": kw[:8], "命中正则": pat[:3], "改归属": holder[:6]}
            return {"原因": "★ 规则迁移真丢了触发物（旧能命中，新不能）",
                    "命中词": kw[:8], "命中正则": pat[:3]}

        rows.append({
            "i": i,
            "广告名称": str(r.get("广告名称") or ""),
            "平台": str(r.get("平台") or ""),
            "投放USD": round(float(r.get("_spend") or 0), 2),
            "源表_命中": sorted(src),
            "引擎_命中": sorted(eng),
            "源表有引擎无": [{"规则": x, **lost(x)} for x in sorted(src - eng)],
            "引擎有源表无": [{"规则": x, **explain(x)} for x in sorted(eng - src)],
            "引擎_severity": v["verdict"]["severity"],
            "引擎_处置层": v["verdict"]["layer"]["id"],
        })
    kinds = collections.Counter()
    for x in rows:
        for y in x["引擎有源表无"]:
            kinds[y["原因"]] += 1
        for y in x["源表有引擎无"]:
            kinds[y["原因"]] += 1
    return {
        "记录数": len(recs),
        "两次扫描一致": agree,
        "有分歧": len(rows),
        "分歧原因分布": dict(kinds),
        "逐行": rows,
    }


# ══════════════════════════════════════════════════════════════════════
#  轴 4 · 语料完备性（用源表自己留下的证据量）
# ══════════════════════════════════════════════════════════════════════
def axis4_corpus(recs):
    """源表的 `命中片段` 列，记的是**它当时到底命中了什么字符串**。

    ★ 这是本项目一直没用起来的一份证据：132 条记录、272 个片段。
      拿它逐条回今天的语料里搜，搜不到的那部分 = **源表扫描看到的文案，
      我们没有**。它不是规则差异，是**输入差异** —— 处置是去修采集，
      不是去改规则。两者混在一起，就会把「去修拉取管道」记成「去改规则」。

    `EMPTY` / `<文案为空` 是源表给「整行没读到」留的哨兵值，不是片段，排除。
    """
    SENTINEL = {"", "empty", "<文案为空", "<文案为空>"}
    rows, total, miss = [], 0, 0
    for i, r in enumerate(recs):
        frag = str(r.get("命中片段") or "").strip()
        if not frag:
            continue
        t = (S.rec_text(r) or "").lower()
        if frag.lower() in SENTINEL:
            rows.append({"i": i, "哨兵": frag, "片段": [], "找不到": []})
            continue
        pairs = []
        for part in frag.split("/"):
            part = part.strip()
            if ":" not in part:
                continue
            rid, _, frs = part.partition(":")
            for f in frs.split(","):
                f = f.strip()
                if not f or f.lower() in SENTINEL:
                    continue
                total += 1
                ok = f.lower() in t
                if not ok:
                    miss += 1
                pairs.append({"规则": rid.strip(), "片段": f, "语料里找得到": ok})
        rows.append({"i": i, "广告名称": str(r.get("广告名称") or ""),
                     "平台": str(r.get("平台") or ""),
                     "语料长度": len(S.rec_text(r) or ""),
                     "片段": pairs, "找不到": [p["片段"] for p in pairs
                                            if not p["语料里找得到"]]})
    recs_with_miss = [x for x in rows if x.get("找不到")]
    return {
        "$claim": "源表扫描看到的文案 > 我们存下来的文案。差额由源表自己的 `命中片段` 列量化。",
        "有命中片段的记录": len(rows),
        "$sentinels": sorted(SENTINEL),
        "片段总数": total,
        "语料里找不到的片段": miss,
        "找不到占比": round(miss / total, 4) if total else None,
        "受影响记录数": len(recs_with_miss),
        "受影响记录": [{"i": x["i"], "广告名称": x["广告名称"], "平台": x["平台"],
                     "找不到": x["找不到"]} for x in recs_with_miss],
        "逐记录": rows,
    }


# ══════════════════════════════════════════════════════════════════════
def build():
    recs, raw, rules, wl, gd = load()
    a0 = axis0_exception_semantics(recs, raw)
    a1 = axis1_exception_drift(recs, raw, rules, wl, gd)
    a3 = axis3_line_by_line(recs, raw, rules)
    a2 = axis2_coverage(raw, rules, wl, gd)
    a4 = axis4_corpus(recs)

    # ── 守恒等式 ───────────────────────────────────────────────────
    live_total = sum(len(r.get("exceptions") or []) for r in raw)
    d = a1["去向分布"]
    cons_ex = live_total == (d.get("语境守卫", 0) + d.get("白名单", 0) + d.get("无归属", 0))
    cons_scan = a3["记录数"] == a3["两次扫描一致"] + a3["有分歧"]
    # 引擎新增检出里，标为「迁移回归」的必须恰好能由旧豁免词解释
    regression = a3["分歧原因分布"].get("旧豁免词被翻成降级（迁移回归）", 0)

    led = {
        "schema_version": 1,
        "$note": "旧规则集（21 条，H/M/U 编号）→ 骨架 v1 的迁移保真度对账。"
                 "四条轴。改规则/词表/语料任一，本账即过期，`--check` 会红。",
        "contract_version": CONTRACT_VERSION,
        "generated_by": "research/governance/audit_migration_fidelity.py",
        "source": {
            "records": "research/governance/skeleton/_data/records.json",
            "rules_raw": "research/governance/skeleton/_data/rules_raw.json",
            "rules_new": "research/governance/skeleton/rules-v1.json",
            "whitelist": "research/governance/skeleton/whitelist-v1.json",
            "guards": "research/governance/skeleton/context-guards-v1.json",
        },
        "source_sha256": {
            "records.json": _sha256(RECORDS),
            "rules_raw.json": _sha256(RULES_RAW),
            "rules-v1.json": _sha256(RULES_NEW),
            "whitelist-v1.json": _sha256(WHITELIST),
            "context-guards-v1.json": _sha256(GUARDS),
        },
        "totals": {
            "旧豁免词总数": live_total,
            "旧豁免词_迁到语境守卫": d.get("语境守卫", 0),
            "旧豁免词_迁到白名单": d.get("白名单", 0),
            "旧豁免词_无归属": d.get("无归属", 0),
            "自我触发豁免词": a1["自我触发词数"],
            "仍放行": a1["仍放行_条数"],
            "变成降级": a1["变成降级_条数"],
            "满档判险_无带": a1["满档判险_无带_条数"],
            "已接线但非免责类": sum(
                1 for x in a1["逐词"]
                if x["去向"] == "语境守卫" and x["已接线"]
                and (x["实测带"] in ("downgrade", "无带"))),
            "无归属关键词": a2["无归属词总数"],
            "逐行分歧": a3["有分歧"],
            "分歧_迁移回归_假阳性": regression,
            "分歧_语料缺口": a3["分歧原因分布"].get(
                "★ 语料缺口：源表扫描看到的文案我们没采到", 0),
            "分歧_改归属改档": a3["分歧原因分布"].get(
                "★ 触发物被改归属到别的规则（档位可能被降）", 0),
            "分歧_真丢触发物": a3["分歧原因分布"].get(
                "★ 规则迁移真丢了触发物（旧能命中，新不能）", 0),
            "源表自报片段_语料里找不到": a4["语料里找不到的片段"],
        },
        "守恒": {
            "旧豁免词_去向之和等于总数": cons_ex,
            "豁免词_实测三桶之和等于自我触发词数":
                (a1["仍放行_条数"] + a1["变成降级_条数"]
                 + a1["满档判险_无带_条数"]) == a1["自我触发词数"],
            "逐行_一致加分歧等于总数": cons_scan,
            "轴0语义前提成立": a0["成立"],
        },
        "轴0_例外语义证据": a0,
        "轴1_例外漂移": {k: v for k, v in a1.items() if k != "逐词"},
        "轴2_检出覆盖": a2,
        "轴3_逐行对账": {k: v for k, v in a3.items() if k != "逐行"},
        "轴3_分歧逐行": a3["逐行"],
        "轴4_语料完备性": {k: v for k, v in a4.items() if k != "逐记录"},
        "轴4_逐记录": a4["逐记录"],
        "轴1_逐词": a1["逐词"],
    }
    return led


def check(led) -> int:
    bad = 0
    for name, p in [("records.json", RECORDS), ("rules_raw.json", RULES_RAW),
                    ("rules-v1.json", RULES_NEW), ("whitelist-v1.json", WHITELIST),
                    ("context-guards-v1.json", GUARDS)]:
        if _sha256(p) != led["source_sha256"][name]:
            print(f"❌ {name} 指纹变了 —— 迁移对账已过期，重跑本脚本")
            bad += 1
    for k, v in led["守恒"].items():
        if not v:
            print(f"❌ 守恒被打破：{k}")
            bad += 1
    if not OUT.exists():
        print("❌ 账不在盘上")
        bad += 1
    else:
        cur = json.loads(OUT.read_text(encoding="utf-8"))
        if cur.get("totals") != led["totals"]:
            print("❌ 盘上的账与本脚本算出的不一致 —— 重跑")
            bad += 1
    if bad == 0:
        print("✅ 迁移保真度对账新鲜、守恒成立")
    return 1 if bad else 0


def md(led):
    t = led["totals"]
    print("## 迁移保真度对账（旧规则集 → 骨架 v1）\n")
    print(f"- 旧豁免词 {t['旧豁免词总数']} 个 → 语境守卫 {t['旧豁免词_迁到语境守卫']}"
          f" / 白名单 {t['旧豁免词_迁到白名单']} / 无归属 {t['旧豁免词_无归属']}")
    print(f"- **旧豁免语义存活率（实测 {t['自我触发豁免词']} 个自我触发词）**："
          f"仍放行 {t['仍放行']} · 变成降级 {t['变成降级']} · "
          f"**满档判险 {t['满档判险_无带']}**")
    print(f"  · 仍放行：{', '.join('`'+w+'`' for w in led['轴1_例外漂移']['仍放行'])}")
    print(f"  · 变成降级：{', '.join('`'+w+'`' for w in led['轴1_例外漂移']['变成降级'])}")
    print(f"- 无归属关键词：{t['无归属关键词']} 个")
    print(f"- 逐行对账：{led['轴3_逐行对账']['两次扫描一致']}/{led['轴3_逐行对账']['记录数']} 一致，"
          f"{t['逐行分歧']} 条分歧")
    a4 = led["轴4_语料完备性"]
    print(f"- 源表自报片段 {a4['片段总数']} 个，语料里找不到 **{a4['语料里找不到的片段']}** 个"
          f"（{a4['找不到占比']}），涉及 {a4['受影响记录数']} 条记录")
    print()
    print("| 分歧原因 | 条数 |")
    print("|---|---:|")
    for k, v in sorted(led["轴3_逐行对账"]["分歧原因分布"].items(), key=lambda x: -x[1]):
        print(f"| {k} | {v} |")
    print()
    if led["轴1_例外漂移"]["翻掉记录的词"]:
        print("| 翻掉记录的旧豁免词 | 翻掉条数 |")
        print("|---|---:|")
        for k, v in led["轴1_例外漂移"]["翻掉记录的词"].items():
            print(f"| `{k}` | {v} |")
        print()
    print("| 满档判险（旧语义彻底消失）的豁免词 | 实测 |")
    print("|---|---|")
    _w = {x["词"]: x for x in led["轴1_逐词"]}
    for w in led["轴1_例外漂移"]["满档判险_无带"]:
        x = _w[w]
        print(f"| `{w}` | {x['实测处置']} · {x['实测等级']} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    led = build()
    if a.check:
        sys.exit(check(led))
    if a.md:
        md(led)
        return
    OUT.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    md(led)
    t = led["totals"]
    print(f"\n✅ 已写 {OUT.relative_to(GOV.parent.parent)}")
    if not led["轴0_例外语义证据"]["成立"]:
        print("❌ 轴 0 语义前提**不成立** —— 轴 1/轴 3 的结论全部作废，必须重做")
        sys.exit(1)
    print(f"   轴0 前提成立（同批次对照 {len(led['轴0_例外语义证据']['对照组'])} 组）")


if __name__ == "__main__":
    main()
