#!/usr/bin/env python3
"""

★★ 2026-09-23（Q46 = 选项 A 裁定）：**这个文件已经不是生成器了，它是一次性迁移脚本。**

   守卫表 `context-guards-v1.json` 从今天起是一份**手工维护的契约** —— `wired` / `status` 由
   逐词裁定写入（Q23 接通 18 个、Q26 接通 16 个、Q24 剔除 1 个、Q25 移出 3 个），
   **不是**从这个脚本重算出来的。判据在 `tools/verify_engine_contract.py`
   （V45a–V45d / V57a–V57c / V58a–V58c / **V59a–V59b**），不在「重新生成一遍」上。

   ★ 为什么必须写这一句：本脚本的 `wired` 是按 `rules-v1.json` 的 `downgrade_band.keywords`
     重算的，而那批词在 **ADR-0008 分表时已经搬进本表**、原字段早已清空 ——
     所以它今天重算出的「已接线」是 **0**，而入库值是 **79**。
     实测跑一次：**353 插入 / 457 删除**，而输出照样打印「✅ 已写入」。
     这与 `AGENTS.md` §2.1 的 `readdoc > 文件`、§2.4.4 的 `--selftest` 是同一个形状：
     **照文档里的命令做，就会破坏它要保护的东西。**

   ★ 现在的两道防线（缺一条都不够）：
     ① 写盘前的锁：重算结果与入库值不一致 → **拒绝写盘并退 2**（`--force` 才覆盖）；
     ② 表头如实描述（`derivation_note` / `source`）—— 表不再声称自己可以重新生成。

   ★ 文件名保留 `build_context_guards.py` 是**故意的**：改名要动那份派生物索引
     （`research/kb/索引-本地资产.json`，可重算），而收益只是名字好听一点。
     名字会骗人这件事，这里**明着写出来**，而不是靠读者从文件名推断角色。

跑法（它现在只有两个有意义的开法）：
  python3 research/governance/skeleton/build_context_guards.py --dry-run   # 只算不写，看差异
  python3 research/governance/skeleton/build_context_guards.py --force     # 明知会抹掉接线决定才用
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
LIVE = ROOT / "research/governance/_evidence/rulelib-live.json"
OUT = HERE / "context-guards-v1.json"

SAFE_TYPE = "安全词白名单"


def split_terms(raw):
    return [x.strip() for x in re.split(r"[/,，;；\n]", raw or "") if x.strip()]


def band_target(rule):
    eff = str((rule.get("downgrade_band") or {}).get("effect") or "").strip()
    return eff.split("→")[-1].strip() if "→" in eff else ("none" if eff in ("none", "") else eff)


def lang_of(word):
    """按字符集判语种 —— 与 whitelist 表保持同一口径（不猜、可复现）。"""
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", word))
    if has_cjk and re.search(r"[A-Za-z]", word):
        return "mixed"
    if has_cjk:
        return "zh"
    if re.search(r"[àâçéèêëîïôûùüÿœæ]", word, re.I):
        return "fr"
    if re.search(r"[äöüß]", word, re.I):
        return "de"
    if re.search(r"[áéíóúñ¿¡]", word, re.I):
        return "es"
    return "en"


# ── 守卫类型的机器推导 ────────────────────────────────────────────────
# ★ 只按**表面词素**分类，不声称语义。语义归属是法务的事（ADR-0008 §三分工表）。
NEG = re.compile(
    r"(does\s?n[o']t|does not|do not|don'?t|won'?t|cannot|can'?t|not\s|no\s|never"
    r"|不|无法|并非|不可|不是|非)", re.I)
DISCLAIM = re.compile(r"(not a |not an |not intended|不是.{0,6}设备|不用于)", re.I)
RISK = re.compile(r"(risk of|reduce the risk|reduces the risk|reducing the risk)", re.I)
PROV = re.compile(r"(inspired by|参考|借鉴|灵感|设计思路|natural|自然)", re.I)
SOFT = re.compile(
    r"(relieve|relieves|relieving|relief|ease|eases|easing|soothe|soothes|gentle|comfort"
    r"|support|may help|缓解|放松)", re.I)


def guard_type(word):
    if DISCLAIM.search(word):
        return "免责声明"
    if NEG.search(word):
        return "否定"
    if RISK.search(word):
        return "风险降低表述"
    if PROV.search(word):
        return "溯源/同源表述"
    if SOFT.search(word):
        return "弱化/替代表述"
    return "未归类"


# ★ Q24 = 选项 A（2026-09-23 裁定）：**不是守卫的词** —— 从守卫表剔除，单独立项为「旧规则假阴孔」。
#
#   判据不是「它长得像不像守卫」，而是：**它就是它所在规则要抓的那个主张本身**。
#   `乳腺炎治疗设备` 里的 `乳腺炎` 是 H02 的匹配词 —— 而旧系统 `exceptions` 的语义是**放行**
#   （同批次天然对照：`Savannah-20260825` 的 i=265 含豁免词 → 源表 0 命中·绿）。
#   也就是说：**旧系统对写着「乳腺炎治疗设备」的文案是放行的。**
#
#   这个洞今天是被**意外**关上的，不是被决定关上的（它 `wired=false` → 拿不到带 → 按满档判险）。
#   三个方向都试过，只有「剔除 + 立为假阴孔」是对的：
#     · 忠实迁移 → 把这个洞搬进新系统，重现旧行为；
#     · 当成普通降级词 → 与它的**否定**（`不是乳腺炎治疗设备`）同处一档，这一档就失去区分力；
#     · 静默留在表里 → 下一个人按 Q23 批量接通时**会顺手把它接上，而没人知道它曾经开着**。
#
#   ★ 改这里而不是改生成物：本表是 `build_context_guards.py` 生成的，手改会被下次重生成抹掉。
NOT_GUARDS = {
    "乳腺炎治疗设备": {
        "kind": "旧规则假阴孔",
        "why": ("它**就是 H02 要抓的那个主张本身**（`乳腺炎` 是 H02 的匹配词），不是免责声明 —— "
                "旧系统把它写在 `豁免词` 里，等于对这条主张放行。"),
        "decision": "Q24",
        "action": "交法务确认是否补召回；**不要**迁移成放行项，也不要当成普通降级词",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="★ 明知重算结果与已入库的表不一致、仍要覆盖（会抹掉 46 条接线决定）")
    a = ap.parse_args()

    live = json.loads(LIVE.read_text())
    wl = json.loads((HERE / "whitelist-v1.json").read_text())
    wset = {w["word"].lower(): w for w in wl["words"]}
    rules = json.loads((HERE / "rules-v1.json").read_text())["rules"]

    by_key = {r["rule_key"]: r for r in rules}
    by_parent = defaultdict(list)
    for r in rules:
        by_parent[r.get("parent_rule")].append(r["rule_key"])

    # 每条骨架规则的带成员 + 通道落点
    wired_band = {}      # rule_key → set(lower word)
    for r in rules:
        wired_band[r["rule_key"]] = {
            k.strip().lower() for k in (r.get("downgrade_band") or {}).get("keywords") or []}
    # 反向索引：词 → 它实际占据的 (rule_key, 通道落点)
    occupies = defaultdict(list)
    for r in rules:
        for k in (r.get("downgrade_band") or {}).get("keywords") or []:
            occupies[k.strip().lower()].append((r["rule_key"], band_target(r)))

    records = [x for x in live if x["规则编号"] != "安全词"]
    words, dup = [], []
    false_neg = []          # ★ Q24：被剔除的「不是守卫」的词（假阴孔），单独成区
    for x in records:
        legacy = x["规则编号"]
        terms = split_terms(x["豁免词"])
        if not terms:
            continue
        candidates = by_parent.get(legacy, [])
        for term in terms:
            low = term.lower()
            # ① 白名单词的重复登记 → 不属于本表
            if low in wset:
                dup.append({"word": term, "legacy_rule": legacy,
                            "belongs_to": "whitelist-v1.json",
                            "whitelist_status": wset[low]["status"]})
                continue
            # ★ Q24 = 选项 A：**不是守卫的词**在查通道**之前**就剔除 ——
            #   它的问题不是「落在哪个带」，而是「它根本不该在这张表里」。
            if low in NOT_GUARDS:
                false_neg.append({"word": term, "legacy_rule": legacy, **NOT_GUARDS[low]})
                continue
            # ② 该词实际占据了哪些带？—— 先按事实查，再谈归属
            occ = occupies.get(low, [])
            if occ:
                tgts = [k for k, _ in occ]
                channels = [c for _, c in occ]
            else:
                # 未接线：按同源规则的检测词表重合度挑一个「本应属于」的目标
                best, best_score = None, -1
                for k in candidates:
                    kw = by_key[k]["match"]["keywords"]
                    score = sum(1 for w in kw if w.lower() in low or low in w.lower())
                    if score > best_score:
                        best, best_score = k, score
                tgts = [best] if best else (candidates or ["<未映射>"])
                channels = ["none"]
            tgt = tgts[0]
            b = (by_key.get(tgt) or {}).get("downgrade_band") or {}
            # ★ wired 的含义严格限定为「落在降级带」。落 auto_pass 带不是接线成功，
            #   是 G3 违反 —— 那说明这个词其实是白名单词，走错了通道。
            wired = "manual_review" in channels
            g3 = [k for k, c in occ if c == "auto_pass"]
            words.append({
                "word": term,
                "lang": lang_of(term),
                "guard_type": guard_type(term),
                "guard_type_derivation": "机器推导（表面词素）· 语义归属待法务确认",
                "downgrades": tgts,
                "downgrades_legacy": [legacy],
                "effect_target": channels[0] if occ else "none",
                "effect": b.get("effect", "") if occ else "",
                "wired": wired,
                "channel_verdict": ("downgrade" if wired
                                    else "pass" if "auto_pass" in channels else "none"),
                "g3_violation": g3 or None,
                "status": ("active" if wired else "misrouted" if g3 else "pending"),
                "status_note": (
                    None if wired else
                    "走错通道：落在放行带，属白名单机制，待 Owner/法务裁定"
                    if g3 else
                    "待法务定性：现网登记了，骨架未收录 —— 删除，或补一条规则"),
                "source_legacy": legacy,
            })

    # 接线缺口的成因归类（让「看不见的东西」可见）
    sk_guard_words = {k for k, v in occupies.items() if any(c == "manual_review" for _, c in v)}
    for w in words:
        if w["wired"]:
            w["wire_gap"] = None
            continue
        if w["g3_violation"]:
            w["wire_gap"] = ("走错通道：落在 auto_pass 带 —— 该词证成主张，属白名单机制，"
                             "不应登记为语境守卫")
            continue
        low = w["word"].lower()
        kin = [k for k in sk_guard_words if k != low and k.split()[0] == low.split()[0]]
        w["wire_gap"] = (f"同族已接线（{kin[0]}）—— 词形未补全" if kin
                         else "骨架未收录 —— 需确认是「有意剔除」还是「抄漏」")

    # ── ③ 骨架独有：现网 `豁免词` 里没有、但骨架降级带里有 ──────────────
    # 两张来源必须合并，否则「表」只覆盖现网侧，骨架侧的守卫会静默消失。
    seen = {w["word"].lower() for w in words}
    skel_only = []
    for r in rules:
        if band_target(r) != "manual_review":
            continue
        for k in (r.get("downgrade_band") or {}).get("keywords") or []:
            low = k.strip().lower()
            if low in seen or low in wset:
                continue          # 已在现网侧登记 / 属白名单表
            seen.add(low)
            skel_only.append({
                "word": k.strip(),
                "lang": lang_of(k.strip()),
                "guard_type": guard_type(k.strip()),
                "guard_type_derivation": "机器推导（表面词素）· 语义归属待法务确认",
                "downgrades": [r["rule_key"]],
                "downgrades_legacy": [],
                "effect_target": "manual_review",
                "effect": (r.get("downgrade_band") or {}).get("effect", ""),
                "wired": True,
                "channel_verdict": "downgrade",
                "g3_violation": None,
                "status": "active",
                "status_note": None,
                "source_legacy": None,
                "source": "骨架独有（现网 `豁免词` 未登记）",
                "wire_gap": None,
            })
    words.extend(skel_only)
    for w in words:
        w.setdefault("source", "现网 `豁免词`" if w.get("source_legacy") else "骨架独有")

    stats = {
        "live_field_total": sum(len(split_terms(x["豁免词"])) for x in records),
        "duplicated_from_whitelist": len(dup),
        "guards": len(words),
        "from_live": sum(1 for w in words if w.get("source_legacy")),
        "from_skeleton_only": len(skel_only),
        "wired": sum(1 for w in words if w["wired"]),
        "not_wired": sum(1 for w in words if not w["wired"]),
        "g3_violations": sum(1 for w in words if w["g3_violation"]),
        "by_status": {s: sum(1 for w in words if w["status"] == s)
                      for s in ("active", "pending", "misrouted")},
        "by_type": dict(sorted(
            {t: sum(1 for w in words if w["guard_type"] == t)
             for t in {w["guard_type"] for w in words}}.items(),
            key=lambda kv: -kv[1])),
        "by_lang": dict(sorted(
            {t: sum(1 for w in words if w["lang"] == t)
             for t in {w["lang"] for w in words}}.items(),
            key=lambda kv: -kv[1])),
    }

    doc = {
        "$schema_version": "context-guards-v1",
        "$note": [
            "★ ADR-0009（决策 4）：本表是独立的「语境守卫」表，**不得与白名单或判定规则同表混放**。",
            "现网把本表内容塞在规则库的 `豁免词` 字段里，与 10 个白名单词共用字段，",
            "与 `安全词` 是同一种病 —— 通道由字段里的字符串决定，而不是由结构决定。",
            "本表唯一用途：把 `downgrades` 列出的规则从 auto_reject 降到 manual_review。",
            "**不放行任何东西**。放行是白名单表的唯一职责（whitelist-v1.json）。",
        ],
        "mechanism": {
            "name": "语境守卫",
            "semantics": "出现在文案中时，表明该规则所指的主张**并未被作出**"
                         "（否定 / 免责 / 溯源 / 弱化替代），从而把该规则降级，而不是放行。",
            "channel": "downgrade only",
            "structural_difference": (
                "白名单证成主张 → 落 auto_pass 带；语境守卫取消或弱化主张 → 落 manual_review 带。"
                "判别式是 band 的 effect 落点，不是词表归属。"),
            "why_not_a_flag": (
                "现网靠 `边界类型 == \"安全词白名单\"` 这种字符串开关区分机制。"
                "开关会因写错条件、字段改名、换读取路径而失效；分表不会。"),
        },
        "admission_criterion": {
            "rule": "该词出现时，能否合理地把「主张未被作出」与「主张被作出」区分开",
            "note": "判不出者不得进本表 —— 否则降级通道会变成误报的垃圾桶。",
        },
        "invariants": [
            "G1 disjointness ｜ active 守卫词不得出现在任何规则的 match.keywords 中",
            "   ← 违反即「否定表述本身被判险」：`does not cure` 触发 `cure` 规则且无降级信号 → 误报。",
            "G2 attribution ｜ 每个守卫词必须声明至少一条 downgrades（否则是死重：加了不生效）",
            "G3 direction   ｜ 守卫词只允许落 manual_review 带；**落 auto_pass 带即违反**",
            "   ★ G3 是白名单与本表的结构分界：守卫绝不放行。",
            "G4 cross-table ｜ 守卫词不得与**未隔离**的白名单词重名（隔离的白名单词可走降级通道）",
            "G5 wiring      ｜ wired=false 的守卫不计入失败，但必须逐条给出 wire_gap 成因（退出码 2）",
        ],
        "derivation_note": [
            "`guard_type` 是按**表面词素**的机器推导，不是语义裁定。",
            "按 ADR-0008 §三分工表，「一条语境规则该不该存在」是法务的决定，",
            "开发者不得自行增删。本表因此只记录与呈现，不做语义裁决。",
        ],
        "source": {
            "snapshot": "snapshot-20260916T050845Z.json",
            "legacy_field": "品线内容边界规则库.豁免词",
            "legacy_field_total": stats["live_field_total"],
            "split_rule": "现网豁免词 − 白名单表已有词 = 语境守卫表",
        },
        "stats": stats,
        "duplicated_from_whitelist": dup,
        # ★ Q24（选项 A）：「**不是守卫**的词」独立成区 —— 既不迁移，也不静默留在表里。
        #   与 `duplicated_from_whitelist` 同一个形状：**剔除的东西要留下名字与理由**，
        #   否则下一个人只会看到「表里 85 个词」，看不出这里少了一个。
        "$false_negative_words": {
            "$note": [
                "★ Q24 = 选项 A（2026-09-23）：这些词**不是语境守卫** —— 它们（或其中的关键词）",
                "**就是所在规则要抓的那个主张本身**。旧系统 `exceptions` 的语义是放行，",
                "所以旧系统对写着这些词的文案是**放行**的：**旧规则的一条假阴孔**。",
                "★ 它们今天还没造成后果，只是因为 `wired=false`（拿不到带 → 按满档判险）——",
                "这个洞是**被意外关上的，不是被决定关上的**。忠实迁移会把它搬进新系统。",
                "★ 处置：不进守卫表；单独立项，交法务确认是否补召回。",
                "判据见 `tools/verify_engine_contract.py` 的 V57a–V57c。",
            ],
            "items": false_neg,
        },
        "words": sorted(words, key=lambda w: (w.get("source_legacy") or "ZZ", w["word"])),
    }

    print(f"现网 `豁免词` 条目        ：{stats['live_field_total']}")
    print(f"  − 白名单词重复登记      ：{stats['duplicated_from_whitelist']}")
    print(f"  = 现网侧守卫            ：{stats['from_live']}")
    print(f"  + 骨架独有（现网未登记）：{stats['from_skeleton_only']}")
    print(f"  = 语境守卫表            ：{stats['guards']}")
    print(f"      已接线（落降级带）  ：{stats['wired']}")
    print(f"      未接线              ：{stats['not_wired']}（含 G3 违反 {stats['g3_violations']}）")
    print(f"      类型分布 {stats['by_type']}")
    print(f"      语种分布 {stats['by_lang']}")

    if a.dry_run:
        print("\n（--dry-run，未写文件）")
        return 0

    # ★★ 2026-09-23 实测撞上的**破坏性路径**：本脚本今天**重算不出**已入库的那张表。
    #
    #   根因：`wired` 是按 `rules-v1.json` 的 `downgrade_band.keywords` 重算的，而那批词在
    #   ADR-0008 分表时**已经搬进本表**，`downgrade_band.keywords` 早已清空 ——
    #   于是重算出的「已接线」是 **0**，而入库值是 **46**。实测跑一次：353 插入 / 457 删除，
    #   46 条接线决定被抹成 0 条，而输出照样打印「✅ 已写入」。
    #
    #   这与 `AGENTS.md` §2.1 的 `readdoc > 文件`、§2.4.4 的 `--selftest` 是**同一个形状**：
    #   **照文档里的命令做，就会破坏它要保护的东西。**
    #
    #   所以这里加一道锁，而不是把数字改对 —— 数字改不对（输入 `_evidence/rulelib-live.json`
    #   还不在版本库内、`.gitignore:45`），但**「不一致就不许静默覆盖」是能做到的**。
    #   要做的是「重建生成器」这件事本身 —— 那是 Q46。
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8")).get("stats") or {}
        except (OSError, ValueError):
            old = {}
        drift = [(k, old.get(k), stats.get(k)) for k in ("guards", "wired", "not_wired")
                 if k in old and old.get(k) != stats.get(k)]
        if drift and not a.force:
            print("\n❌ 拒绝写盘：重算结果与**已入库的那张表**不一致 ——")
            for k, o, n in drift:
                print(f"     {k}: 入库 {o} → 重算 {n}")
            print("   ★ 这不是「表旧了」，是**生成器旧了**：`wired` 按 `downgrade_band.keywords` 重算，")
            print("     而那批词在 ADR-0008 分表时已搬进本表 —— 覆盖一次会抹掉那 46 条接线决定。")
            print("   ★ 要重建生成器，这是一个决定（Q46），不是一个命令。")
            print("   ★ 确实知道后果仍要覆盖：加 `--force`（它只关掉这道锁，不改变结果）。")
            return 2
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"\n✅ 已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
