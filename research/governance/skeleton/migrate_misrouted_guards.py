#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migrate_misrouted_guards.py —— 4 个走错通道的词：语境守卫表 → 白名单表

★ 这是一次**法务决定的落地**，不是重构。

  决定（法务，2026-09-16）：「3. 迁」—— 把 `lint_context_guards.py` G3 报出的
  4 个走错通道词移入白名单表。

  原问题（`迁移手册-机器词表.md` §五 第 1 项）：「移入白名单表，还是从词表删除？」
  答案：移入。依据：这 4 个词**证成主张**（`FDA 注册` = 一个真实可查的监管状态；
  `静音模式` / `silent mode` / `suction settings` = 产品功能名），
  按 `context-guards-v1.json` 的 `mechanism.structural_difference` 自己写的判别式
  ——「白名单证成主张 → 落 auto_pass 带；语境守卫取消或弱化主张 → 落 manual_review 带」
  ——它们本来就属于白名单表。登记在守卫表里是**登记错了表**。

★ 为什么必须用脚本而不是手改 JSON

  迁移要同时改两张表、两张表的 stats、以及 `duplicated_from_whitelist` 台账，
  任何一处漏改都会让「表说的」与「表里有的」不一致 —— 而本项目所有事故
  都起于这种不一致。脚本化之后：幂等（重复跑结果一致）、可回滚（自动备份）、
  可复核（dry-run 打印每一条的实际改动）。

★ 一个必须说清的语义变化：**这 4 个词在今天之前是死的。**

  `band_hits()` 放行带取词取自 `vocab.pass_bands`，而 `pass_bands` 唯一来源是
  白名单表的 `exempts_rule_keys`（`vocab.py:90-98`）。4 个词登记在守卫表里、
  状态 `misrouted`，而 `load_vocab` 只收 `status == "active"` 的守卫
  （`vocab.py:82`）—— 所以它们**既不在放行带、也不在降级带**。

  实测：三条规则（`T6.1` / `T2.2.quiet-claim` / `T2.2.suction-claim`）的
  `downgrade_band.keywords` **声明了**这 4 个词，运行时却一个都取不到
  ——「声明了但取不到」在行为上与「没声明」完全一样，且无任何提示。

  所以本次迁移是**一次真实的行为变化**，不是记账搬家。存量语料影响见实测报告。

用法：
  python3 migrate_misrouted_guards.py            # dry-run（缺省，不写盘）
  python3 migrate_misrouted_guards.py --write    # 落盘（先自动备份）
  python3 migrate_misrouted_guards.py --write --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WL_PATH = HERE / "whitelist-v1.json"
GD_PATH = HERE / "context-guards-v1.json"
RULES_PATH = HERE / "rules-v1.json"
BACKUP_DIR = HERE / "_data" / "backup-migration"

DECIDED_BY = "法务"
DECIDED_AT = "2026-09-16"

# word → 目的地。exempts 目标必须是 target=auto_pass 的规则（否则迁移方向就错了）。
MOVES = [
    {"word": "FDA 注册", "lang": "mixed", "to_rule": "T6.1.regulatory-status",
     "evidence_required": "certificate",
     "$why": "监管状态的事实标签（可查注册号）；与同带的 `FDA registered` 同族。"},
    {"word": "silent mode", "lang": "en", "to_rule": "T2.2.quiet-claim",
     "evidence_required": "product_spec",
     "$why": "模式名（一个可查的档位），不是「静音」这一主张本身。"},
    {"word": "静音模式", "lang": "zh", "to_rule": "T2.2.quiet-claim",
     "evidence_required": "product_spec",
     "$why": "同上，中文写法。注意它**包含**判险词 `静音`：短语级豁免是带机制的设计意图。"},
    {"word": "suction settings", "lang": "en", "to_rule": "T2.2.suction-claim",
     "evidence_required": "product_spec",
     "$why": "功能名（可调的档位设置），与同带的 `suction level` / `adjustable suction` 同族。"},
]


def band_words(rule: dict) -> list[str]:
    return [str(k).strip().lower()
            for k in ((rule.get("downgrade_band") or {}).get("keywords") or [])]


def detect_indent(text: str) -> int:
    """从原文里认出缩进宽度。

    ★ 为什么值得写这 6 行：本目录不是 git 仓库，审计只能靠**文件差异**。
      第一版脚本一律 `indent=2` 写回，而这两个文件原本是 `indent=1` ——
      结果是「删 4 个词条」变成了整文件 6 万字节的空白改动，
      真正改了什么被淹没在重排里。**审计靠 diff 时，格式就是证据的一部分。**
    """
    for line in text.splitlines()[1:]:
        if line.strip():
            return max(1, len(line) - len(line.lstrip(" ")))
    return 1


def dumps_like(doc, original_text: str) -> str:
    """按原文的缩进与结尾换行写回，把 diff 限制在真正的改动上。"""
    out = json.dumps(doc, ensure_ascii=False, indent=detect_indent(original_text))
    return out + "\n" if original_text.endswith("\n") else out


def band_target(rule: dict) -> str:
    eff = str((rule.get("downgrade_band") or {}).get("effect") or "").strip()
    return eff.split("→")[-1].strip() if "→" in eff else "none"


def preflight(rules_doc: dict) -> list[str]:
    """迁移前把「方向错了」的情况全部挡下来。返回错误列表（空 = 可以迁）。"""
    errs: list[str] = []
    by_key = {r["rule_key"]: r for r in rules_doc["rules"]}
    for mv in MOVES:
        w = mv["word"]
        r = by_key.get(mv["to_rule"])
        if r is None:
            errs.append(f"{w}: 目的地规则 {mv['to_rule']} 不存在")
            continue
        # ① 目的地必须是放行带 —— 否则我们是在把词从错通道搬进另一个错通道
        if band_target(r) != "auto_pass":
            errs.append(f"{w}: {mv['to_rule']} 的落点是 {band_target(r)!r}，不是 auto_pass"
                        f"（白名单只服务放行带）")
        # ② 规则必须**声明过**这个词 —— 否则是「凭空加一条未登记的例外」
        if w.strip().lower() not in band_words(r):
            errs.append(f"{w}: {mv['to_rule']} 的 downgrade_band.keywords 里没有这个词；"
                        f"白名单不得凭空造出一条例外（W5b）")
        # ③ W1：active 白名单词不得出现在任何规则的判险词表里
        for rk, rr in by_key.items():
            kws = {str(k).strip().lower() for k in (rr.get("match") or {}).get("keywords", [])}
            if w.strip().lower() in kws:
                errs.append(f"{w}: 出现在 {rk} 的判险词表里（W1 会红）—— 「安全」不得证明「有风险」")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="落盘（缺省只 dry-run）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rules_doc = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    wl_orig = WL_PATH.read_text(encoding="utf-8")
    gd_orig = GD_PATH.read_text(encoding="utf-8")
    wl = json.loads(wl_orig)
    gd = json.loads(gd_orig)

    errs = preflight(rules_doc)
    if errs:
        print("❌ 迁移前置校验失败 —— 未写盘：", file=sys.stderr)
        for e in errs:
            print(f"    {e}", file=sys.stderr)
        return 1

    wl_by_word = {str(e["word"]).strip().lower(): e for e in wl["words"]}
    gd_by_word = {str(e["word"]).strip().lower(): e for e in gd["words"]}

    plan, skipped = [], []
    for mv in MOVES:
        w = mv["word"]
        lw = w.strip().lower()
        g = gd_by_word.get(lw)
        already = wl_by_word.get(lw)
        if g is None and already is not None:
            skipped.append(f"{w}: 已在白名单表且不在守卫表 —— 已迁移过，跳过")
            continue
        if g is None:
            plan.append(f"❌ {w}: 两张表里都找不到 —— 无法迁移")
            continue
        if g.get("status") != "misrouted":
            plan.append(f"⚠ {w}: 守卫状态是 {g.get('status')!r} 而非 misrouted —— 请先确认")
            continue
        if already is not None:
            plan.append(f"⚠ {w}: 白名单表里已有同名词 —— 需人工合并，脚本不猜")
            continue
        plan.append(
            f"✓ {w:<18} 守卫表({g.get('status')}) → 白名单表 "
            f"exempts={mv['to_rule']} evidence={mv['evidence_required']}")

    result = {"dry_run": not a.write, "plan": plan, "skipped": skipped,
              "moved": [], "wl_before": len(wl["words"]), "gd_before": len(gd["words"])}

    if not a.write:
        if a.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("migrate_misrouted_guards.py —— dry-run（未写盘）")
            print(f"  白名单 {len(wl['words'])} 词 ｜ 守卫表 {len(gd['words'])} 词")
            for line in skipped:
                print(f"  · {line}")
            for line in plan:
                print(f"  {line}")
            print("\n  落盘：python3 migrate_misrouted_guards.py --write")
        return 0

    # ── 落盘 ────────────────────────────────────────────────────────
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for p in (WL_PATH, GD_PATH):
        shutil.copy2(p, BACKUP_DIR / f"{p.stem}.{stamp}.bak")

    # exempts 用规则的 parent_rule（现行号），不是字符串截断 —— 与既有条目口径一致
    parent_of = {r["rule_key"]: r.get("parent_rule") for r in rules_doc["rules"]}

    for mv in MOVES:
        w, lw = mv["word"], mv["word"].strip().lower()
        g = gd_by_word.get(lw)
        if g is None or g.get("status") != "misrouted" or lw in wl_by_word:
            continue
        wl["words"].append({
            "word": mv["word"],
            "lang": mv["lang"],
            "status": "active",
            "quarantine_reason": None,
            "exempts": [parent_of.get(mv["to_rule"])],
            "exempts_rule_keys": [mv["to_rule"]],
            "evidence_required": mv["evidence_required"],
            "live_clash_with_detection": [],
            "source_legacy": g.get("source_legacy"),
            "channel": "pass",
            "$migrated_from": "context-guards-v1.json（原 status=misrouted）",
            "$why": mv["$why"],
            "$decision": f"D3 · 法务 {DECIDED_AT}：走错通道词迁入白名单表",
        })
        result["moved"].append(mv["word"])
        gd["words"] = [e for e in gd["words"] if str(e["word"]).strip().lower() != lw]
        # 台账：这些词来自现网 `豁免词` 字段，归白名单表所有
        gd.setdefault("duplicated_from_whitelist", []).append({
            "word": mv["word"],
            "legacy_rule": g.get("source_legacy"),
            "belongs_to": "whitelist-v1.json",
            "whitelist_status": "active",
            "$note": f"迁入（{DECIDED_AT}）；此前登记在守卫表里，状态 misrouted。",
        })

    # ── stats 一律重算，不手改 ──────────────────────────────────────
    wl_words = wl["words"]
    wl["stats"] = {
        "total": len(wl_words),
        "active": sum(1 for e in wl_words if e["status"] == "active"),
        "quarantined": sum(1 for e in wl_words if e["status"] == "quarantined"),
        "orphans_in_live": sum(1 for e in wl_words
                               if e["status"] == "active" and not (e.get("exempts_rule_keys") or [])),
    }
    gd_words = gd["words"]
    live_total = 94          # 现网 `豁免词` 字段的词数（快照事实，不随本地文件变化）
    dup = len(gd.get("duplicated_from_whitelist") or [])
    st = gd.get("stats") or {}
    gd["stats"] = {
        "live_field_total": live_total,
        "duplicated_from_whitelist": dup,
        "guards": len(gd_words),
        "from_live": live_total - dup,
        "from_skeleton_only": st.get("from_skeleton_only", 5),
        "wired": sum(1 for e in gd_words if e.get("wired")),
        "not_wired": sum(1 for e in gd_words if not e.get("wired")),
        "g3_violations": sum(1 for e in gd_words if e.get("g3_violation")),
        "by_status": {k: sum(1 for e in gd_words if e.get("status") == k)
                      for k in sorted({e.get("status") for e in gd_words})},
        "by_type": {k: sum(1 for e in gd_words if e.get("guard_type") == k)
                    for k in sorted({e.get("guard_type") for e in gd_words})},
        "by_lang": {k: sum(1 for e in gd_words if e.get("lang") == k)
                    for k in sorted({e.get("lang") for e in gd_words})},
    }
    result["wl_after"] = wl["stats"]
    result["gd_after"] = gd["stats"]

    WL_PATH.write_text(dumps_like(wl, wl_orig), encoding="utf-8")
    GD_PATH.write_text(dumps_like(gd, gd_orig), encoding="utf-8")

    result["backup_dir"] = str(BACKUP_DIR)
    result["wl_sha256"] = hashlib.sha256(WL_PATH.read_bytes()).hexdigest()[:16]
    result["gd_sha256"] = hashlib.sha256(GD_PATH.read_bytes()).hexdigest()[:16]

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✓ 迁移完成：{len(result['moved'])} 词 {result['moved']}")
        print(f"  白名单 {result['wl_before']} → {wl['stats']['total']} 词"
              f"（active {wl['stats']['active']} / 孤儿 {wl['stats']['orphans_in_live']}）")
        print(f"  守卫表 {result['gd_before']} → {len(gd_words)} 词"
              f"（G3 违反 {gd['stats']['g3_violations']}）")
        print(f"  备份：{BACKUP_DIR}")
        print("\n  下一步：python3 lint_whitelist.py && python3 lint_context_guards.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
