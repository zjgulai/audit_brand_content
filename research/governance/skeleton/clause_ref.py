#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clause_ref.py —— 回执的证据引用（T4）：条款地址 + 未确认声明

## 这个模块治的病

PRD §5.3 的三个示例，**每一个都以「依据《文档名》第 X 条」结尾**。
而在此之前，判定回执里没有这一句：

* `rules-v1.json` 的 `external_ref` 说了「**这条规则**依据什么」（T3 落的）；
* 回执只说了「命中了哪条规则」。

中间那一跳**没有任何落点** —— 所以「依据第 X 条」在回执上写不出来。
本模块补的就是这一跳：**回执 → 条款 → 原文**（本方案 §3.1 的第 ④ 段）。

## 为什么这一个模块在**引擎侧**（而不是 `tools/`）

回执是引擎制品，`evidence_ref` 必须在 `judge()` **内部**产出。放在调用方，
「任一判定回执能反查到条款」就退化成「调用方传没传」—— 而 `judge()` 的调用方
不止一个（CLI / 批量 / `push_receipts` / 守衡的 `judge_copy`），
只要有一个不传，那条回执就永远点不开依据，**而且没有任何东西会红**。

而本仓的依赖方向是**单向**的：`tools/*` 可以 import `research/governance/skeleton/*`，
**反向一次都没有发生过**（全仓 grep 可核，T4c 会断言这一点）。
所以条款地址的词汇只能定义在引擎侧；`tools/kb_clause.py` **转发**这里的定义 ——
与它转发 `evidence_origin.py` 的 `ORIGINS` 是同一种做法，不是第二份定义。

## 三个字段，各治一件事

| 字段 | 说的是 | 空着会怎样 |
|---|---|---|
| `evidence_ref[]` | 这条判定**依据了哪几条**（库名 + 条目ID + 条文号 + 链接 + 指纹 + origin） | 「依据第 X 条」写不出来 |
| `evidence_absence[]` | 命中的规则里**哪些声明了自己没有外部依据**（T3 的 `no_external_basis` + 理由） | 「本来就没有外部依据」与「忘了填」长得一模一样 |
| `ratified` + `unconfirmed_notice` | 引用的条款**有没有经过法务确认** | 一次研究会被读成一次法务裁定 |

## ★★ `ratified` 不许是声明，必须是派生

这是本模块里最容易做错的一处。今天 62 条外部标准**全部** `status=research`、
`未确认标记=研究稿·未经法务确认`（复现：`python3 tools/kb_clause.py`）。

若只往回执里加一个手填的 `ratified: false`，那么法务确认了第一条之后，
**没有任何东西会红**，而回执会继续告诉每一个读者「未经确认」——
这正是 `AGENTS.md` §2.4.1 第 5 行的形状：**一个会过期的读数，没有任何东西在它过期时变红。**

所以这里的 `ratified` 是**算出来的**：`all(被引用的条目 status == 'ratified')`，
且 `unconfirmed_notice` 必须**逐条点名**没确认的那些条目 ——
一句「本判定引用了未经确认的条款」不带对象，读者无法据此行动。

## `evidence_status`：读不到时要说「未测」

条款库读不出来时（文件缺失 / 损坏），**不许产出空 `evidence_ref` 了事** ——
那与「这条判定本来就没引用任何条款」（零命中 / catch_all）长得一模一样。
所以那一路落 `evidence_status="unavailable"` + 理由，判据据此放行，
但 T4a 会断言**正常路径下它必须是 `ok`**：退化路径不许成为常态
（`AGENTS.md` §2.2 第 7 条：靠外部文件取的读数，取不到时必须说「未测」）。

## 用法

不单独跑；被 `judge.py`（产出）与 `tools/kb_clause.py` / verifier（判据）调用。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import evidence_origin as EO  # noqa: E402  证据来源四档（T19）

LIB_NAME = "外部标准库"
#: 条款库本体。`research/governance/skeleton/` → `research/kb/`
EXT_PATH = HERE.parents[1] / "kb" / "外部标准库-v1.json"

# 结构化条款地址的必需字段（= T4 的 `evidence_ref` 形状 + T18 的指纹）
REF_FIELDS = ("库名", "条目ID", "条文号", "指纹")

# 回执里那个证据块的字段。**一个都不许省** —— 省掉哪个，哪个就变成「可选的」。
BLOCK_FIELDS = ("evidence_ref", "evidence_absence", "ratified",
                "unconfirmed_notice", "evidence_status")
#: 随块一起走、但**按情形才出现**的字段（写进回执的同名键，判据按需读）。
BLOCK_AUX_FIELDS = ("evidence_unavailable_reason", "evidence_unresolved", "$ratified_note")

# `evidence_status` 的取值域（枚举，不许自由字符串 —— 与 origin 四档同一条规矩）
EVIDENCE_STATUS = ("ok", "unavailable")


# ── 条款地址：索引 / 指纹 / 链接 ─────────────────────────────────────

def load_index(ext_doc):
    """`clause_no → entry` 与 `id → entry` 两张表 + `id → source`。"""
    entries = (ext_doc or {}).get("entries") or []
    sources = {s.get("id"): s for s in ((ext_doc or {}).get("sources") or [])}
    by_no, by_id = {}, {}
    for e in entries:
        if e.get("clause_no"):
            by_no.setdefault(e["clause_no"], e)
        by_id[e.get("id")] = e
    return {"by_no": by_no, "by_id": by_id, "sources": sources, "entries": entries}


def load_library(path=None):
    """读条款库 → `(doc, index, problem)`。

    ★ **读不出来时不抛异常**，而是把理由当返回值交出去 —— 调用方据此落
      `evidence_status="unavailable"`。抛出去的话，条款库一坏，判定就整个没了，
      而这两件事的严重程度差着量级（§2.2 第 7 条）。
    """
    p = Path(path or EXT_PATH)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        return None, None, f"{p} 读不出来：{type(e).__name__}: {e}"
    return doc, load_index(doc), None


def source_of(ext_doc, sid):
    """按 `source_id` 取来源块（缺了就返回 `{}`，由判据去报悬空）。"""
    for s in ((ext_doc or {}).get("sources") or []):
        if s.get("id") == sid:
            return s
    return {}


def clause_fp(entry, source=None):
    """变更指纹。哈希「库名 + 来源ID + 条文号 + 条款原文」。

    **只哈希决策当时考虑过的输入。** 改了其中任意一个字节 → 指纹变 →
    引用它的规则与回执标记 stale。这比时间戳准：时间戳看不见「条款被改了一个字」，
    而改一个字恰恰是法务最常做的动作。

    ★ `条款位置`（自由文本）与 `摘要` **不进指纹** —— 它们是描述不是内容；
      改描述不该让引用失效，否则整理一次措辞就会让 26 条规则全部变 stale，
      那会让人开始无视这个信号（比没有信号更糟，`AGENTS.md` §2.1.1）。
    """
    payload = "\n".join([
        LIB_NAME,
        str(entry.get("source_id") or ""),
        str(entry.get("clause_no") or ""),
        str(entry.get("条款原文") or ""),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def clause_link(entry, source=None):
    """条款的可点开链接。**页内锚点不存在时不许编一个** —— 只给来源页。"""
    return (source or {}).get("url") or ""


def ref_problems(ref, index, where=""):
    """一条 `external_ref` / `evidence_ref` 的问题清单。返回 `[(类, 说明)]`。

    ★ 类只有两种：`悬空`（指不到东西）与 `失效`（指得到，但条款已经变了）。
      分开是因为**修法完全不同**：悬空要改指针，失效要重新确认内容。
      合成一句「引用有问题」，读的人还得自己去分辨。
    """
    bad = []
    tag = f"{where} " if where else ""
    if not isinstance(ref, dict):
        return [("悬空", f"{tag}引用不是结构化地址：{ref!r}")]
    missing = [f for f in REF_FIELDS if not str(ref.get(f) or "").strip()]
    if missing:
        bad.append(("悬空", f"{tag}地址缺字段 {missing} —— 「《外部标准库》第 X 条」要的三样缺一不可"))
        return bad
    if ref["库名"] != LIB_NAME:
        bad.append(("悬空", f"{tag}库名={ref['库名']!r} 不是 {LIB_NAME!r}"))
    e = index["by_id"].get(ref["条目ID"])
    if e is None:
        bad.append(("悬空", f"{tag}条目ID={ref['条目ID']!r} 在 {LIB_NAME} 里不存在（凭空关联）"))
        return bad
    if ref["条文号"] != e.get("clause_no"):
        bad.append(("悬空", f"{tag}条文号={ref['条文号']!r} ≠ {ref['条目ID']} 的 "
                            f"{e.get('clause_no')!r}"))
    # ★ `链接` 也必须是**派生值**，不许是自由文本。
    #   理由不是洁癖：回执一旦落盘就永久留存，而「回执里那段文字是链接还是原文」
    #   看的人是分不出来的。把地址的四样全部钉成派生值之后，
    #   `verify_engine_contract.py` 的 V7d（回执不落原文）才可以**只**把地址字段
    #   排除在扫描之外 —— 排除的是**派生字段**，不是一个说不清的字符串。
    if "链接" in ref and ref.get("链接") != clause_link(e, index["sources"].get(e.get("source_id"))):
        bad.append(("悬空", f"{tag}链接={str(ref.get('链接'))[:60]!r} ≠ {ref['条目ID']} 的来源页 "
                            f"{clause_link(e, index['sources'].get(e.get('source_id')))[:60]!r} —— "
                            f"地址的四样都是派生值，不许手写"))
    now = clause_fp(e, index["sources"].get(e.get("source_id")))
    if ref["指纹"] != now:
        bad.append(("失效", f"{tag}{ref['条目ID']} 的条款已改动：引用时记的是 "
                            f"{ref['指纹']}，现在重算是 {now} —— 这条引用是 stale 的，"
                            f"必须重新确认，不许继续当依据"))
    return bad


def evidence_ref_of(entry, index):
    """把一条条款条目变成一条**证据引用**（T4 的 `evidence_ref` 形状 + `origin`）。

    ★ 两套标识：`条目ID`（身份，稳定，不随改名变）与 `条文号`（token，派生的）。
      两个都留 —— `clause_no` 断了会被判据抓住，而 `条目ID` 永远指得回那一条。
    """
    src = index["sources"].get(entry.get("source_id"))
    return {
        "库名": LIB_NAME,
        "条目ID": entry.get("id"),
        "条文号": entry.get("clause_no"),
        "链接": clause_link(entry, src),
        "指纹": entry.get("变更指纹"),
        "origin": entry.get("origin"),
    }


def evidence_refs(ext_doc):
    """全部条目的 `evidence_ref`。**这条路径今天就有真实产出者**（62 条）。"""
    idx = load_index(ext_doc)
    return [evidence_ref_of(e, idx) for e in idx["entries"]]


def evidence_ref_problems(ref, index, where=""):
    """一条 `evidence_ref`：**地址**（不悬空、不失效）+ **来源**（四档内）。

    两类分开报，理由与 `ref_problems` 同：悬空要改指针，失效要重新确认内容。
    """
    if not isinstance(ref, dict):
        return [("悬空", f"{where} 证据引用不是结构化地址：{ref!r}")]
    tag = f"{where} " if where else ""
    missing = [f for f in REF_FIELDS + ("origin",) if not str(ref.get(f) or "").strip()]
    if missing:
        return [("悬空", f"{tag}证据引用缺字段 {missing} —— "
                        f"「《外部标准库》第 X 条」与「怎么读到的」缺一不可")]
    return ref_problems(ref, index, where=where) + \
        [("来源", m) for m in EO.evidence_problems([ref], where=tag.strip())]


# ── T4：命中的规则 → 回执的证据块 ────────────────────────────────────

def _rules_by_key(rules):
    rs = rules if isinstance(rules, list) else ((rules or {}).get("rules") or [])
    return {r.get("rule_key"): r for r in rs}


def evidence_refs_of_rules(rule_keys, rules):
    """命中的规则 → 证据引用。**只搬运，不解释**（解引用是判据的事）。

    返回 `(refs, absences, problems)`：

    * `refs` —— 去重后的引用列表（同一份条款被两条命中规则引用只留一条）；
    * `absences` —— 命中的规则里声明了 `no_external_basis` 的，**带上它自己写的理由**；
    * `problems` —— 命中的规则不在 rules 里（回执点得到规则名、点不到规则本身）。
    """
    byk = _rules_by_key(rules)
    refs, absences, problems = [], [], []
    seen = set()
    for rk in rule_keys or []:
        r = byk.get(rk)
        if r is None:
            problems.append(("悬空", f"命中的规则 {rk!r} 在 rules 里不存在 —— "
                                     f"回执点得到规则名，却点不到规则本身，更点不到条款"))
            continue
        er = r.get("external_ref")
        if not er:
            reason = str(r.get("no_external_basis") or "").strip()
            if reason:
                absences.append({"规则": rk, "理由": reason})
            else:
                problems.append(("悬空", f"{rk}: 既没有 external_ref，也没有 no_external_basis —— "
                                         f"「这条规则依据什么」空着不算答案（T3）"))
            continue
        for ref in er:
            key = (ref.get("库名"), ref.get("条目ID"), ref.get("条文号"))
            if key in seen:
                continue
            seen.add(key)
            refs.append(dict(ref))
    return refs, absences, problems


def ratification(refs, index):
    """**派生**「这批引用确认过没有」。返回 `(ratified, unconfirmed, unresolved)`。

    ★ 派生而不是声明 —— 见模块抬头。`ratified` 只有在**每一条**都
      `status == 'ratified'` 时才为真；一条没确认，整批判成未确认
      （判定引用的是**整批**依据，不是其中几条）。

    ★ 零引用时**不是**「真空为真」。`all([])` 在数学上是 True，但把
      `ratified=true` 写给一条零命中的判定，会被读成「这条判定已被确认」——
      而它连依据都没有。所以这里显式要求**至少一条**：零引用 → `ratified=False`，
      并另给一句说明它为什么是假（见 `evidence_block` 的 `$ratified_note`）。
    """
    unconfirmed, unresolved = [], []
    for ref in refs or []:
        e = index["by_id"].get(ref.get("条目ID")) if index else None
        if e is None:
            unresolved.append(ref.get("条目ID"))
            continue
        if e.get("status") != "ratified":
            unconfirmed.append({
                "条目ID": e.get("id"),
                "条文号": e.get("clause_no"),
                "状态": e.get("status"),
                "未确认标记": e.get("未确认标记"),
            })
    ratified = bool(refs) and not unconfirmed and not unresolved
    return ratified, unconfirmed, unresolved


def unconfirmed_notice(refs, unconfirmed):
    """未确认声明。**必须逐条点名** —— 不带对象的一句「未经确认」，读者无法据此行动。"""
    if not unconfirmed:
        return None
    ids = "、".join(f"{u['条目ID']}（{u['条文号']}，{u.get('状态') or '未知状态'}）"
                    for u in unconfirmed)
    marks = sorted({str(u.get("未确认标记") or "").strip()
                    for u in unconfirmed if str(u.get("未确认标记") or "").strip()})
    return (f"★ 本次判定引用的 {len(unconfirmed)}/{len(refs)} 条外部标准**未经法务确认**："
            f"{ids}。它们在库里的身份是「{marks[0] if marks else '研究稿'}」，"
            f"因此这条判定是**研究层结论，不是法务裁定** —— 不得作为业务承诺引用，"
            f"也不得据此对广告主说「平台不允许」。要升级成裁定，须由法务逐条确认"
            f"（确认/否决，不是从零写：口令已定，见 Q22）。")


def evidence_block(rule_keys, rules, index, *, library_problem=None, problems=None):
    """产出回执里的证据块。**这是 T4 唯一的产出点。**

    `library_problem` 非空（条款库读不出来）时落 `evidence_status="unavailable"` ——
    见模块抬头最后一段：那种情况下**不许**产出空 `evidence_ref` 了事。
    """
    block = {
        "evidence_ref": [],
        "evidence_absence": [],
        "ratified": False,
        "unconfirmed_notice": None,
        "evidence_status": "ok",
    }
    if library_problem or index is None:
        block["evidence_status"] = "unavailable"
        block["evidence_unavailable_reason"] = library_problem or "条款库索引为空"
        block["$note"] = ("★ 条款库这一跳今天读不到，所以**这条回执点不开任何条款**。"
                          "这不是「本次判定没有依据条款」—— 那两件事长得不一样，"
                          "所以这里显式记「未测」而不是留一个空数组。")
        return block

    refs, absences, probs = evidence_refs_of_rules(rule_keys, rules)
    probs = list(problems or []) + probs
    by_id = index["by_id"]
    for ref in refs:
        e = by_id.get(ref.get("条目ID")) or {}
        ref["origin"] = e.get("origin")
    ratified, unconfirmed, unresolved = ratification(refs, index)
    block["evidence_ref"] = refs
    block["evidence_absence"] = absences
    block["ratified"] = ratified
    block["unconfirmed_notice"] = unconfirmed_notice(refs, unconfirmed)
    if not refs:
        # ★ 零引用：`ratified=false` 说的是「没有可确认的依据」，不是「依据被否决了」。
        #   不写这一句，读回执的人会把 catch_all 读成一次失败的确认。
        block["$ratified_note"] = (
            "本次判定**没有引用任何外部条款**（零命中 / 命中的规则声明了 `no_external_basis`）"
            "—— `ratified=false` 的含义是「没有可确认的依据」，不是「依据未获确认」。"
            "★ 零命中 ≠ 合规：它走 catch_all，含义是规则库没有覆盖它。")
    block["$note"] = (
        "★ 这一块治的是 PRD §5.3 的「依据《文档名》第 X 条」：回执 → 条款 → 原文。"
        "`evidence_ref[]` 只搬 `rules-v1.json` 的 `external_ref`（T3 落的边），"
        "`origin` 取自条目本身（T19 四档）；`ratified` 是**算出来的**，不是填的。"
        "命中的规则若声明了 `no_external_basis`，它进 `evidence_absence` —— "
        "「本来就没有外部依据」与「忘了填」必须长得不一样。")
    if probs:
        block["evidence_unresolved"] = [f"[{k}] {m}" for k, m in probs]
    if unresolved:
        block["evidence_unresolved"] = (block.get("evidence_unresolved") or []) + [
            f"[悬空] 引用的条目 {i!r} 不在条款库里" for i in unresolved]
    return block


# ── T4 的判据：回执的证据块能不能反查到条款 ──────────────────────────

def evidence_block_problems(block, index, rule_keys=None, rules=None, where=""):
    """回执的证据块。返回 `[(类, 说明)]`。类 ∈ {`缺块`, `悬空`, `失效`, `未确认`, `覆盖`}。

    ★ 判据抽成**纯函数**，反向对照才能对**同一个判据**做变异
      （`tools/verify_kb.py` 的 T4a/T4b 就是喂它坏样本）。写成一段内联 `if`，
      反向对照就只能另写一份 —— 而「另写一份」的那一份不会跟着改。
    """
    tag = f"{where} " if where else ""
    if not isinstance(block, dict):
        return [("缺块", f"{tag}回执里没有证据块（T4：没有它，「依据第 X 条」写不出来）")]
    bad = []
    missing = [f for f in BLOCK_FIELDS if f not in block]
    if missing:
        return [("缺块", f"{tag}证据块缺字段 {missing}")]

    st = block.get("evidence_status")
    if st not in EVIDENCE_STATUS:
        bad.append(("缺块", f"{tag}evidence_status={st!r} 不在 {list(EVIDENCE_STATUS)} 内"))
    if st == "unavailable":
        if not str(block.get("evidence_unavailable_reason") or "").strip():
            bad.append(("缺块", f"{tag}自称读不到条款库，却没写理由 —— "
                                f"「未测」必须与「没有依据」长得不一样"))
        if block.get("evidence_ref"):
            bad.append(("缺块", f"{tag}自称读不到条款库，却带着 {len(block['evidence_ref'])} "
                                f"条引用 —— 二者互斥"))
        return bad

    refs = block.get("evidence_ref") or []
    absence = block.get("evidence_absence") or []
    if not isinstance(refs, list) or not isinstance(absence, list):
        return [("缺块", f"{tag}evidence_ref / evidence_absence 不是数组")]
    if index is None:
        return [("缺块", f"{tag}判据拿不到条款库索引，这条断言无从谈起（未测）")]

    for i, ref in enumerate(refs, 1):
        bad += evidence_ref_problems(ref, index, where=f"{tag}证据#{i}")

    # ── `ratified` 必须是派生的，且未确认声明必须点名 ────────────────
    rat_now, unconf, unres = ratification(refs, index)
    for i in unres:
        bad.append(("悬空", f"{tag}引用的条目 {i!r} 不在条款库里"))
    if bool(block.get("ratified")) != rat_now:
        bad.append(("未确认", f"{tag}ratified={block.get('ratified')!r}，"
                              f"按引用逐条重算应为 {rat_now!r}"
                              f"（引用 {len(refs)} 条、未确认 {len(unconf)} 条、"
                              f"悬空 {len(unres)} 条） —— "
                              f"这个字段是**算出来的**，不是填的"))
    notice = block.get("unconfirmed_notice")
    if refs and not rat_now:
        if not str(notice or "").strip():
            bad.append(("未确认", f"{tag}引用了 {len(unconf)} 条未经法务确认的条款，"
                                  f"却没有 unconfirmed_notice —— "
                                  f"一次研究会被读成一次法务裁定（Q22）"))
        else:
            nameless = [u["条目ID"] for u in unconf
                        if u["条目ID"] and u["条目ID"] not in notice]
            if nameless:
                bad.append(("未确认", f"{tag}未确认声明没有点名 {nameless} —— "
                                      f"不带对象的一句「未经确认」，读者无法据此行动"))
    elif rat_now and str(notice or "").strip():
        bad.append(("未确认", f"{tag}引用的条款**全部**已确认，却仍写未确认声明 —— "
                              f"把已授权的依据说成草案，同样在骗读者"))
    elif not refs and not str(block.get("$ratified_note") or "").strip():
        bad.append(("未确认", f"{tag}零引用的回执没有说明 `ratified=false` 的含义 —— "
                              f"那会被读成「依据未获确认」，而实际是「没有可确认的依据」"))

    # ── 覆盖：命中的规则要么有引用，要么在 absence 里（不许静默漏掉）────
    if rule_keys is not None and rules is not None:
        byk = _rules_by_key(rules)
        absent_keys = {a.get("规则") for a in absence if isinstance(a, dict)}
        cited_pairs = {(r.get("条目ID"), r.get("条文号")) for r in refs if isinstance(r, dict)}
        for rk in rule_keys or []:
            r = byk.get(rk) or {}
            er = r.get("external_ref") or []
            if er:
                hit = [(x.get("条目ID"), x.get("条文号")) for x in er]
                if not any(p in cited_pairs for p in hit):
                    bad.append(("覆盖", f"{tag}命中的规则 {rk} 有 {len(er)} 条 external_ref，"
                                        f"回执里却一条都没带上"))
            elif rk not in absent_keys:
                bad.append(("覆盖", f"{tag}命中的规则 {rk} 没有 external_ref，"
                                    f"也不在 evidence_absence 里 —— "
                                    f"「本来就没有外部依据」与「忘了记」长得一样"))
        for a in absence:
            if not isinstance(a, dict) or not str(a.get("理由") or "").strip():
                bad.append(("覆盖", f"{tag}evidence_absence 有一条没写理由：{a!r}"))
    return bad


def block_of(rc):
    """从一份回执里取出证据块。**平铺在回执顶层**（T4 的字段名就是回执的字段名）。"""
    if not isinstance(rc, dict):
        return None
    return {k: rc.get(k) for k in BLOCK_FIELDS + BLOCK_AUX_FIELDS}


def receipt_evidence_problems(rc, index, rules=None, where=""):
    """从回执里取出证据块并判它。**账本逐条反查与端到端判据共用这一条。**

    ★ 覆盖那一条要 `rule_keys_hit`：一份回执若只记了「命中了哪几条规则的**哈希**」，
      就**无法判断它的引用是不是带全了** —— 于是回执里也记 `rule_keys_hit`
      （规则编号，不是广告原文；`ADR-0008` 决策 2 约束的是原文，不是编号）。
    """
    if not isinstance(rc, dict):
        return [("缺块", f"{where} 回执不是 dict：{type(rc).__name__}")]
    keys = rc.get("rule_keys_hit")
    if keys is None and isinstance(rc.get("verdict"), dict):
        keys = rc["verdict"].get("rule_keys_hit")
    if keys is None:
        return [("缺块", f"{where} 回执没有 `rule_keys_hit` —— "
                        f"没有它，「引用带全了没有」这句话答不了（T4）")]
    return evidence_block_problems(block_of(rc), index,
                                   rule_keys=keys, rules=rules, where=where)


def main():
    """只读读数：条款库能不能读、几条引用、确认了几条。"""
    doc, index, problem = load_library()
    if problem:
        print(f"⚠ 未测：{problem}")
        return 2
    refs = evidence_refs(doc)
    rat, unconf, unres = ratification(refs, index)
    print(f"{LIB_NAME}：{len(refs)} 条")
    print(f"  ratified={rat} · 未确认 {len(unconf)} 条 · 悬空 {len(unres)} 条")
    print(f"  evidence_status 正常路径应为 ok；读不到时落 unavailable（见模块抬头）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
