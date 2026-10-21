#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_control_points.py —— 控制点主表与路由表的契约验收（L6-1…L6-6 / L3-1 / L3-2）

**它修的是什么**：技术方案 §1ter.3 写着「执行点：`verify_control_points.py` 的集合恒等断言」，
而这个文件**当时并不存在** —— 那是一个假执行点（坑点台账 K-06 的形状）。
本文件把它变成真的：下面每一条断言都指得出会红的那一行。

**三条口径必须分清**（本项目反复踩的坑）：

  设计完整度   —— 表结构写没写全          → 看 JSON 有没有那九个字段
  主合同同步度 —— Playbook/验收表接没接   → **不是本脚本管**，归 verify_solution_meta / verify_acceptance_index
  实现验证度   —— 有没有执行点且跑过      → **就是本脚本**

**退出码（三态，不许混）**：
  0  全绿
  1  有红
  2  未测（文件读不到 / 结构缺失到无法判断）—— **2 既不是通过也不是红**

用法：
  python3 tools/verify_control_points.py            # 正式表
  python3 tools/verify_control_points.py --json     # 机器可读
  python3 tools/verify_control_points.py --selftest # 反向对照（含 4 个坏样本 + 1 个好样本）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ★ 让 `from base.control_points import ...` 能解析 —— 本脚本原先不 import 仓库模块，
#   所以没有这一行；C-78 的数量口径检查要读 base 的纯函数，补上。
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TABLE = ROOT / "research" / "governance" / "control-points-v1.json"
ROUTING = ROOT / "research" / "governance" / "routing-v1.json"
HISTORY = ROOT / "research" / "governance" / "control-points-history.json"
RULES = ROOT / "research" / "governance" / "skeleton" / "rules-v1.json"
WHITELIST = ROOT / "research" / "governance" / "skeleton" / "whitelist-v1.json"
#: 行 69 的 11 项一级分类 → 七族映射（D-128：权威来源为
#: `规则清单-P0-P3-按等级-20261016.xlsx` 的「所属类别」，11 个唯一值）。
#: 文件存在时按下面的格式校验；不存在时 `--row 69` 退 2（未测），默认检查不把它当红。
#: 格式：
#:   {"schema_version": "category-to-family/v1", "count": 11,
#:    "categories": [{"category": "<一级分类>", "family": "<cp.families 之一>",
#:                    "reason": "<映射理由>"}, ...]}
CATEGORY_MAP = ROOT / "research" / "governance" / "category-to-family-v1.json"

#: 行 71 的首批真码：H01–H09 / M01–M07 / U01–U04。**由区间算出，不写 20 这个数字。**
FIRST_BATCH_CODES = tuple(
    [f"H{i:02d}" for i in range(1, 10)]
    + [f"M{i:02d}" for i in range(1, 8)]
    + [f"U{i:02d}" for i in range(1, 5)]
)
EXPECTED_CATEGORY_COUNT = 11

# Playbook §5.3.1 的九个字段（parent 允许为空值，但**字段必须存在**）
REQUIRED_CP_FIELDS = (
    "control_code", "control_name", "family", "judge_type",
    "authority_kind", "authority_ref", "parent", "version", "status",
)

# ★ routing 的字段是 6 个，不是 A-3 最初写的 4 个。
#   2026-10-18 更正：原 4 字段（owner/due/escalation/appeal）漏了 `layer`，
#   导致「谁结这一层」（DP3 审核员 vs DP4 法务）无处可查。
#   这里**读文件自己的 field_set.count**，不把 6 写死 —— 否则下次加字段又要改这个脚本，
#   那正是「文档里的数字要写死」的同一个病。
REQUIRED_RT_FIELDS_FALLBACK = (
    "control_code", "owner", "layer", "due", "escalation", "appeal",
)

VALID_LAYERS = ("DP3", "DP4")
VALID_JUDGE_TYPES = ("literal", "semantic", "mixed")
VALID_AUTHORITY_KINDS = ("external", "internal")
VALID_STATUS = ("active", "deprecated", "draft")


# ─────────────────────────── 基础 ───────────────────────────

def _blank(v) -> bool:
    """空值的判定：None / 空串 / 纯空白都算空。**空列表不算空** —— 见 _empty_list。"""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    return False


def _check(cid: str, ok: bool, detail: str) -> dict:
    return {"id": cid, "ok": bool(ok), "detail": detail}


def load(path: Path):
    """读 JSON。读不到返回 (None, 错误串) —— 调用方据此落「未测」，不是「红」。"""
    if not path.exists():
        return None, f"{path} 不存在"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), ""
    except (OSError, ValueError) as e:
        return None, f"{path} 读不出：{type(e).__name__}: {e}"


# ─────────────────────── 主表断言（L6）───────────────────────

def check_control_points(cp: dict) -> list:
    out = []
    rows = cp.get("control_points")
    if not isinstance(rows, list):
        return [_check("CP-0", False, "control_points 不是数组 —— 结构坏到无法判断")]

    # ── L6-1：九字段齐全且可解析 ──────────────────────────────
    missing, bad_enum, bad_type = [], [], []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            bad_type.append(f"#{i} 不是对象")
            continue
        code = r.get("control_code") or f"#{i}"
        lack = [f for f in REQUIRED_CP_FIELDS if f not in r]
        if lack:
            missing.append(f"{code} 缺 {lack}")
        if r.get("judge_type") not in VALID_JUDGE_TYPES:
            bad_enum.append(f"{code}.judge_type={r.get('judge_type')!r}")
        if r.get("authority_kind") not in VALID_AUTHORITY_KINDS:
            bad_enum.append(f"{code}.authority_kind={r.get('authority_kind')!r}")
        if r.get("status") not in VALID_STATUS:
            bad_enum.append(f"{code}.status={r.get('status')!r}")
        if not isinstance(r.get("authority_ref"), list):
            bad_enum.append(f"{code}.authority_ref 不是数组")
    out.append(_check("CP-1", not (missing or bad_enum or bad_type),
                      f"{len(rows)} 行；缺字段 {len(missing)}；枚举/类型错 {len(bad_enum)}；非对象 {len(bad_type)}"
                      + (f" · 首个：{(missing + bad_enum + bad_type)[0]}" if (missing or bad_enum or bad_type) else "")))

    # ── L6-2：control_code 唯一 ──────────────────────────────
    codes = [r.get("control_code") for r in rows if isinstance(r, dict)]
    dup = sorted({c for c in codes if c and codes.count(c) > 1})
    out.append(_check("CP-2", not dup, f"{len(codes)} 个码；重复 {len(dup)}" + (f"：{dup}" if dup else "")))

    # ── L6-2b：停用码必须仍在表内（体现「永不复用、永不改号」）──
    # 判据：status=deprecated 的码**不许从表里消失**。它一旦消失，就没有东西阻止
    # 将来把同一个码分配给新含义 —— 那才是「复用」。
    deprecated = {r.get("control_code") for r in rows
                  if isinstance(r, dict) and r.get("status") == "deprecated"}
    gap_codes = {g.get("code") for g in (cp.get("known_gaps") or []) if isinstance(g, dict)}
    vanished = sorted(gap_codes - set(codes))
    out.append(_check("CP-2b", not vanished,
                      f"停用 {len(deprecated)} 个；known_gaps 记了 {len(gap_codes)} 个；"
                      f"记了但不在表里 {len(vanished)}" + (f"：{vanished}" if vanished else "")))

    # ── L6-4：active 码的 authority_ref 非空 ─────────────────
    empty_active = [r.get("control_code") for r in rows
                    if isinstance(r, dict) and r.get("status") == "active"
                    and not (r.get("authority_ref") or [])]
    out.append(_check("CP-4", not empty_active,
                      f"active 且 authority_ref 为空：{len(empty_active)}"
                      + (f"：{empty_active}" if empty_active else "")))

    # ── L6-4b：deprecated 码必须带豁免 + known_gaps 记录 ─────
    # 这一条是「静默退役」的拦截器：空 authority_ref 可以豁免，
    # 但**必须**同时有 exemption 与一条记录，否则与 active 缺依据没有区别。
    bad_dep = []
    for r in rows:
        if not isinstance(r, dict) or r.get("status") != "deprecated":
            continue
        code = r.get("control_code")
        ex = r.get("authority_ref_exemption")
        has_gap = code in gap_codes
        if not isinstance(ex, dict) or not ex.get("applies"):
            bad_dep.append(f"{code} 缺 authority_ref_exemption")
        elif not has_gap:
            bad_dep.append(f"{code} 缺 known_gaps 记录")
        elif _blank(r.get("deprecated_note")):
            bad_dep.append(f"{code} 缺 deprecated_note")
    out.append(_check("CP-4b", not bad_dep,
                      f"deprecated {len(deprecated)} 个；不合格 {len(bad_dep)}"
                      + (f"：{bad_dep}" if bad_dep else "")))

    # ── L6-6：table_version 非空 ─────────────────────────────
    tv = cp.get("table_version")
    out.append(_check("CP-6", not _blank(tv), f"table_version={tv!r}"))

    return out


# ─────────────────────── 路由表断言（L3-1）───────────────────────

def check_routing(rt: dict, cp: dict) -> list:
    out = []
    routes = rt.get("routes")
    if not isinstance(routes, list):
        return [_check("RT-0", False, "routes 不是数组 —— 结构坏到无法判断")]

    # 必填字段：读文件自己的声明，读不到才退到硬编码兜底
    fs = rt.get("field_set") or {}
    required = tuple(fs.get("fields") or REQUIRED_RT_FIELDS_FALLBACK)
    declared_n = fs.get("count")

    # ── RT-2：字段齐全 ───────────────────────────────────────
    lack = []
    for r in routes:
        if not isinstance(r, dict):
            lack.append("存在非对象的 route")
            continue
        miss = [f for f in required if f not in r]
        if miss:
            lack.append(f"{r.get('control_code')} 缺 {miss}")
    # field_set 声明的字段数必须与实际必需字段数一致（防「改了字段忘了改声明」）
    n_ok = (declared_n is None) or (declared_n == len(required))
    out.append(_check("RT-2", not lack and n_ok,
                      f"{len(routes)} 条；必填 {len(required)} 字段 {list(required)}；"
                      f"声明 count={declared_n}；缺字段 {len(lack)}"
                      + (f" · {lack[0]}" if lack else "")
                      + ("" if n_ok else " · field_set.count 与字段表不一致")))

    # ── RT-1：control_code 集合与主表恒等（L3-1 无空洞）──────
    cp_codes = {r.get("control_code") for r in (cp.get("control_points") or [])
                if isinstance(r, dict)}
    rt_codes = {r.get("control_code") for r in routes if isinstance(r, dict)}
    only_cp = sorted(cp_codes - rt_codes)
    only_rt = sorted(rt_codes - cp_codes)
    out.append(_check("RT-1", not (only_cp or only_rt),
                      f"主表 {len(cp_codes)} / 路由 {len(rt_codes)}；"
                      f"主表有路由没有 {len(only_cp)}{only_cp or ''}；"
                      f"路由有主表没有 {len(only_rt)}{only_rt or ''}"))

    # ── RT-3：owner 非空 ────────────────────────────────────
    no_owner = [r.get("control_code") for r in routes
                if isinstance(r, dict) and _blank(r.get("owner"))]
    placeholder = [r.get("control_code") for r in routes
                   if isinstance(r, dict) and str(r.get("owner") or "").strip() in ("待定", "TODO", "TBD", "-")]
    out.append(_check("RT-3", not (no_owner or placeholder),
                      f"owner 空 {len(no_owner)}；占位值 {len(placeholder)}"
                      + (f"：{(no_owner + placeholder)[:5]}" if (no_owner or placeholder) else "")))

    # ── RT-4：layer ∈ {DP3, DP4} ────────────────────────────
    bad_layer = [f"{r.get('control_code')}.layer={r.get('layer')!r}" for r in routes
                 if isinstance(r, dict) and r.get("layer") not in VALID_LAYERS]
    out.append(_check("RT-4", not bad_layer,
                      f"layer 非法 {len(bad_layer)}" + (f"：{bad_layer[:5]}" if bad_layer else "")))

    return out


# ────────────────────── 空族断言（双向）──────────────────────

def check_empty_families(cp: dict) -> list:
    rows = [r for r in (cp.get("control_points") or []) if isinstance(r, dict)]
    families = cp.get("families")
    if not isinstance(families, list) or not families:
        return [_check("EF-0", False, "families 缺失 —— 无法判断空族")]

    declared = [f.get("family") for f in (cp.get("empty_families") or []) if isinstance(f, dict)]
    actual_empty = [f for f in families if f not in {r.get("family") for r in rows}]

    # 双向：声明为空但实际有码 / 实际为空但没声明
    wrongly_declared = sorted(set(declared) - set(actual_empty))
    undeclared = sorted(set(actual_empty) - set(declared))
    unknown = sorted(set(declared) - set(families))

    ok = not (wrongly_declared or undeclared or unknown)
    out = [_check("EF-1", ok,
                  f"七族 {len(families)}；声明空 {len(declared)}{declared or ''}；"
                  f"实际空 {len(actual_empty)}{actual_empty or ''}；"
                  f"声明了但实际有码 {wrongly_declared or '无'}；"
                  f"实际空但没声明 {undeclared or '无'}；"
                  f"声明了不存在的族 {unknown or '无'}")]

    # 每条空族必须有「为什么空」的说明 —— 空着等于没解释
    no_reason = [f.get("family") for f in (cp.get("empty_families") or [])
                 if isinstance(f, dict) and _blank(f.get("reason"))]
    out.append(_check("EF-2", not no_reason,
                      f"空族缺 reason：{no_reason or '无'}"))
    return out


# ───────── C-78 / SEC-5-33：控制点数量的分母只能是主表 ─────────

def check_count_denominator(cp: dict, report: dict | None = None) -> list:
    """
    行 78 的第 ②③ 条：

      ② 控制点数量口径来自主表，不是 58 / 子类
      ③ 构造一份只按 58 子类统计的报告，与主表口径不一致时必须报警

    ★ 为什么单独一个函数而不是塞进 `check_control_points`：
      这两条判的是**报告怎么算数**，不是**主表长什么样**。
      混在一起会让「主表结构对不对」与「报告口径对不对」共用一个红项，
      出红时说不清是哪一边坏了。

    `report` 为 None 时只做 ② 的自证部分（主表自洽），
    传入报告时才判 ③。
    """
    from base.control_points import master_count, control_point_denominator_problems

    out = []
    m = master_count(cp)
    rows = cp.get("control_points") or []

    # ②a 主表自身：总数与 active 数必须算得出来，且 total == 行数
    out.append(_check(
        "CD-1", m["total"] == len(rows) and m["total"] > 0,
        f"主表 total={m['total']} active={m['active']}（行数 {len(rows)}）"))

    # ②b 主表自己声明的口径字段（若有）必须与行数一致 —— 防「表里写着 20，实际 19 条」
    declared = None
    for k in ("control_points_count", "count"):
        v = cp.get(k)
        if isinstance(v, int):
            declared = (k, v)
            break
    if declared is not None:
        out.append(_check(
            "CD-2", declared[1] == m["total"],
            f"表里声明 {declared[0]}={declared[1]}，实际 {m['total']} 条"))
    else:
        # 没声明不是红 —— 但如果将来加了，CD-2 会立刻生效
        out.append(_check("CD-2", True, "表里没有额外的条数字段（不适用，不算红）"))

    # ②c 空族不影响总数：空族是「这一族没有控制点」，不是「控制点少算了」
    empty = {f.get("family") for f in (cp.get("empty_families") or [])
             if isinstance(f, dict)}
    fam_of_rows = {r.get("family") for r in rows if isinstance(r, dict)}
    leaked = sorted(empty & fam_of_rows)
    out.append(_check(
        "CD-3", not leaked,
        f"空族 {sorted(empty)} 与实际有码的族 {sorted(fam_of_rows)} 无交集"
        + (f" · 冲突：{leaked}" if leaked else "")))

    # ③ 报告口径
    #
    # ★ 这里必须**每次主检查都真跑**，不能只在 --selftest 里跑。
    #   理由与 AGENTS.md 的 DG-4…DG-6 同一条：一条只在自测里活的断言，
    #   等于「我们测过这个形状」，不等于「这次交付它是对的」。
    #
    #   两种输入：
    #     传了 report  → 判那份报告
    #     没传        → **用真实主表造两份探针**：一份口径正确（必须不报警）、
    #                   一份拿 58 当总数（**必须报警**）。
    #                   后者是反向对照：证明这条判据不是恒真。
    if report is not None:
        probs = control_point_denominator_problems(report, cp)
        out.append(_check("CD-4", not probs, "；".join(probs) or "报告口径与主表一致"))
        return out

    good = {"control_points_total": m["total"],
            "control_points_active": m["active"]}
    bad = {"control_points_total": 58}
    good_probs = control_point_denominator_problems(good, cp)
    bad_probs = control_point_denominator_problems(bad, cp)

    out.append(_check("CD-4", not good_probs,
                      "口径=主表 → 不报警" + (f" · {good_probs}" if good_probs else "")))
    out.append(_check("CD-5", bool(bad_probs),
                      "★ 反向对照：58 当总数 → 必须报警"
                      + (f" · 命中 {bad_probs}" if bad_probs
                         else " · **没报警，说明判据是恒真的**")))
    return out


# ───────────── C-70 / C-74 / C-76：族变更留痕 / 新码准入 / 码分配 ─────────────

def _codes(cp):
    return [r.get("control_code") for r in (cp.get("control_points") or [])
            if isinstance(r, dict)]


def _family_map(cp):
    return {r.get("control_code"): r.get("family")
            for r in (cp.get("control_points") or []) if isinstance(r, dict)}


def _version_num(v):
    import re as _re
    m = _re.search(r"-v(\d+)$", str(v or ""))
    if not m:
        m = _re.search(r"^v(\d+)$", str(v or ""))
    return int(m.group(1)) if m else None


def check_registry(cp):
    """C-76：主表即码分配登记表；一个码只能属于一个族；跨族拆分必须显式批准。"""
    out = []
    families = cp.get("families")
    rows = [r for r in (cp.get("control_points") or []) if isinstance(r, dict)]
    bad_family = []
    for r in rows:
        code = r.get("control_code")
        fam = r.get("family")
        if not isinstance(fam, str) or fam not in (families or []):
            bad_family.append(f"{code}.family={fam!r}")
    out.append(_check("C76-1", not bad_family,
                      f"每行 family 必须是单值且在 families 内；非法 {len(bad_family)}"
                      + (f"：{bad_family[:5]}" if bad_family else "")))

    split = []
    for r in rows:
        code = r.get("control_code")
        cross = (isinstance(r.get("family"), list)
                 or "families" in r
                 or r.get("family_split") is True)
        if not cross:
            continue
        ap = r.get("family_split_approval")
        ok = (isinstance(ap, dict) and not _blank(ap.get("who"))
              and not _blank(ap.get("why"))
              and isinstance(ap.get("evidence"), list) and ap["evidence"])
        if not ok:
            split.append(code)
    out.append(_check("C76-2", not split,
                      f"跨族拆分必须带 family_split_approval(who/why/evidence)；缺 {len(split)}"
                      + (f"：{split}" if split else "")))

    # 同一 code 出现两次且 family 不同（CP-2 只查重复，这里查「重复且跨族」）
    seen = {}
    conflict = []
    for r in rows:
        c, f = r.get("control_code"), r.get("family")
        if c in seen and seen[c] != f:
            conflict.append(c)
        seen[c] = f
    out.append(_check("C76-3", not conflict,
                      f"同一 code 跨族 {len(conflict)}" + (f"：{conflict}" if conflict else "")))
    return out


def check_history(cp, history):
    """C-70：历史文件存在；最后一条与当前 table_version/码/族快照一致。"""
    out = []
    if not isinstance(history, dict):
        return [_check("H-1", False,
                       "control-points-history.json 不存在或不是对象 —— 族/码变更无留痕")]
    entries = history.get("entries")
    if not isinstance(entries, list) or not entries:
        return [_check("H-1", False, "history.entries 为空 —— 没有任何变更记录")]

    bad_entry = []
    bad_evidence = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            bad_entry.append(f"#{i} 不是对象")
            continue
        for k in ("version", "at", "who", "why"):
            if _blank(e.get(k)):
                bad_entry.append(f"#{i} 缺 {k}")
        ev = e.get("evidence")
        if not isinstance(ev, list) or not ev:
            bad_entry.append(f"#{i} 缺 evidence")
        else:
            for x in ev:
                if not isinstance(x, str) or not x.strip():
                    bad_evidence.append(f"#{i} evidence 项不是非空字符串")
                elif not (ROOT / x).exists():
                    bad_evidence.append(f"#{i} evidence 不存在：{x}")
    out.append(_check("H-2", not bad_entry,
                      f"{len(entries)} 条历史；字段不合格 {len(bad_entry)}"
                      + (f"：{bad_entry[:4]}" if bad_entry else "")))
    out.append(_check("H-2b", not bad_evidence,
                      f"evidence 路径不合格 {len(bad_evidence)}"
                      + (f"：{bad_evidence[:3]}" if bad_evidence else "")))

    last = entries[-1] if isinstance(entries[-1], dict) else {}
    out.append(_check("H-3", last.get("version") == cp.get("table_version"),
                      "最后一条历史 version=%r；主表 table_version=%r"
                      % (last.get("version"), cp.get("table_version"))))

    cur_codes = sorted(_codes(cp))
    hist_codes = last.get("codes")
    out.append(_check("H-4", hist_codes == cur_codes,
                      ("码集合与最后一条历史一致" if hist_codes == cur_codes else
                       "码集合与最后一条历史不一致（增/删码必须升版本并追加历史）："
                       "历史 %r / 当前 %r" % (hist_codes, cur_codes))))

    cur_fam = _family_map(cp)
    hist_fam = last.get("family_by_code")
    out.append(_check("H-5", hist_fam == cur_fam,
                      ("族归属与最后一条历史一致" if hist_fam == cur_fam else
                       "族归属与最后一条历史不一致（改族未升版本/未留痕即红）："
                       "历史 %r / 当前 %r" % (hist_fam, cur_fam))))
    return out


def check_new_codes(cp, history, rules):
    """C-74：相对上一条历史新增的码，必须有规则引用/依据引用/版本；版本必须递增。"""
    out = []
    if not isinstance(history, dict):
        return out
    entries = history.get("entries")
    if not isinstance(entries, list) or len(entries) < 2:
        return out  # 初始基线：没有「上一版」可对比
    prev = entries[-2] if isinstance(entries[-2], dict) else {}
    prev_codes = set(prev.get("codes") or [])
    current = _codes(cp)
    new = [c for c in current if c not in prev_codes]
    if not new:
        return out

    parents = set()
    if not isinstance(rules, dict) or not isinstance(rules.get("rules"), list):
        out.append(_check("C74-0", False, "E_RULES_UNREADABLE：有新增码但 rules-v1.json 读不出"))
    else:
        parents = {r.get("parent_rule") for r in rules["rules"] if isinstance(r, dict)}

    rows = {r.get("control_code"): r for r in (cp.get("control_points") or [])
            if isinstance(r, dict)}
    no_rule, no_auth, no_ver = [], [], []
    for code in new:
        r = rows.get(code) or {}
        if code not in parents:
            no_rule.append("E_CP_RULE_MISSING:%s" % code)
        if not (r.get("authority_ref") or []):
            no_auth.append("E_CP_AUTHORITY_MISSING:%s" % code)
        if _blank(r.get("version")):
            no_ver.append("E_CP_VERSION_MISSING:%s" % code)
    out.append(_check("C74-1", not no_rule, f"新增码缺规则引用 {len(no_rule)}：{no_rule}"))
    out.append(_check("C74-2", not no_auth, f"新增码缺依据引用 {len(no_auth)}：{no_auth}"))
    out.append(_check("C74-3", not no_ver, f"新增码缺版本号 {len(no_ver)}：{no_ver}"))

    pv, cv = _version_num(prev.get("version")), _version_num(cp.get("table_version"))
    inc_ok = pv is not None and cv is not None and cv > pv
    out.append(_check("C74-4", inc_ok,
                      "E_TABLE_VERSION_NOT_INCREMENTED：有新增码时 table_version 必须递增；"
                      "上一版 %r / 当前 %r" % (prev.get("version"), cp.get("table_version"))))
    return out


# ───────── 行 69：七族骨架 / 11 项一级分类映射 ─────────

def check_family_skeleton(cp):
    """行 69 的主表侧：七族存在、唯一、非空；空族也在族清单里。"""
    out = []
    families = cp.get("families")
    if not isinstance(families, list):
        return [_check("F-1", False, "families 不是数组 —— 七族骨架不存在")]
    clean = [f for f in families if isinstance(f, str) and f.strip()]
    out.append(_check(
        "F-1",
        len(families) == 7 and len(set(families)) == 7 and len(clean) == 7,
        "七族必须是 7 个非空且唯一的值；实际 %d 个 / 非空 %d / 去重 %d：%r"
        % (len(families), len(clean), len(set(families)), families),
    ))

    rows = [r for r in (cp.get("control_points") or []) if isinstance(r, dict)]
    bad = sorted({r.get("family") for r in rows
                  if r.get("family") not in (families or [])})
    out.append(_check("F-2", not bad,
                      f"每行 family 必须在七族内；越界值 {bad or '无'}"))

    declared_empty = [f.get("family") for f in (cp.get("empty_families") or [])
                      if isinstance(f, dict)]
    unknown_empty = sorted(set(declared_empty) - set(families or []))
    out.append(_check("F-3", not unknown_empty,
                      f"空族声明必须也是七族成员；不在族清单 {unknown_empty or '无'}"))
    return out


def check_category_mapping(cp, mapping):
    """行 69 的映射侧：**有表才判**；表不存在返回空（默认检查不造假）。

    `--row 69` 在调用方先判文件是否存在；不存在直接退 2，不会走到这里。
    """
    if mapping is None:
        return []
    families = cp.get("families") or []
    if not isinstance(mapping, dict) or not isinstance(mapping.get("categories"), list):
        return [_check("CAT-1", False,
                       "映射表必须是对象且含 categories 数组")]
    cats = mapping["categories"]
    bad_struct, dup, bad_family, bad_reason = [], [], [], []
    unclassified = []
    seen = set()
    for i, e in enumerate(cats):
        if not isinstance(e, dict):
            bad_struct.append(f"#{i} 不是对象")
            continue
        cat, fam = e.get("category"), e.get("family")
        if not isinstance(cat, str) or not cat.strip():
            bad_struct.append(f"#{i} category 为空")
        elif cat in seen:
            dup.append(cat)
        else:
            seen.add(cat)
        if not isinstance(fam, str) or not fam.strip():
            bad_struct.append(f"#{i} family 为空")
        elif fam in ("未归类", "其他"):
            unclassified.append(f"{cat or i}->{fam}")
            bad_family.append(f"{cat or i}->{fam}")
        elif fam not in families:
            bad_family.append(f"{cat or i}->{fam}")
        if _blank(e.get("reason")):
            bad_reason.append(cat or f"#{i}")

    declared = mapping.get("count")
    count_ok = (len(cats) == EXPECTED_CATEGORY_COUNT
                and (declared is None or declared == len(cats)))
    out = [
        _check("CAT-1", not bad_struct,
               f"{len(cats)} 项；结构不合格 {len(bad_struct)}"
               + (f"：{bad_struct[:3]}" if bad_struct else "")),
        _check("CAT-2", not dup, f"category 唯一；重复 {dup or '无'}"),
        _check("CAT-3", not bad_family,
               f"family 必须映射到已存在的族；越界 {bad_family or '无'}"),
        _check("CAT-4", count_ok,
               "一级分类必须是 %d 项，且 count 字段若存在必须等于实际项数；"
               "实际 %d 项 / count=%r"
               % (EXPECTED_CATEGORY_COUNT, len(cats), declared)),
        _check("CAT-5", not (unclassified or bad_reason),
               f"不允许「未归类/其他」；每条必须写 reason。"
               f"未归类 {unclassified or '无'}；缺理由 {bad_reason or '无'}"),
    ]
    return out


# ───────── 行 71：首批 20 真码 / 安全词 / 历史码保留 ─────────

def _rule_enabled(rule) -> bool:
    if not isinstance(rule, dict):
        return False
    if rule.get("enabled") is False:
        return False
    if rule.get("status") in ("deprecated", "retired"):
        return False
    return True


def _safe_word_retired(cp) -> bool:
    for key in ("retired_codes", "legacy_retired", "retired"):
        value = cp.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item == "安全词":
                return True
            if isinstance(item, dict) and item.get("code") == "安全词":
                return True
    return False


def check_first_batch(cp, rules, history, whitelist):
    """行 71：精确码集 / 安全词处置 / 规则与依据 / U02 / 历史码不消失。"""
    out = []
    rows = [r for r in (cp.get("control_points") or []) if isinstance(r, dict)]
    codes = [r.get("control_code") for r in rows]
    expected = set(FIRST_BATCH_CODES)

    extra = sorted(set(codes) - expected)
    missing = sorted(expected - set(codes))

    # ★ 2026-10-21 按验收表行 71 的两条子句拆开（05 裁定）：
    #   第一条「恰好等于」写的是**当时的表状态**；第二条「始终存在且从未被重新分配」
    #   才是长期不变量。品牌控制点 B01–B04 落地后第一条自动作废、第二条仍成立。
    #   B-1a：首批码必须全部仍在，且族归属与**历史基线**一致（防改号/改族）。
    entries = ((history or {}).get("entries")
               if isinstance(history, dict) else None) or []
    base_family = {}
    for e in entries:
        fb = e.get("family_by_code") if isinstance(e, dict) else None
        if isinstance(fb, dict):
            base_family = {k: v for k, v in fb.items() if k in expected}
            break
    fam_now = _family_map(cp)
    changed_family = sorted(
        c for c in expected
        if c in set(codes) and base_family.get(c) is not None
        and fam_now.get(c) != base_family.get(c))
    out.append(_check(
        "B-1a", not missing and not changed_family,
        "首批 20 码必须全部仍在且未改族；实际 %d 个；少 %r；改族 %r"
        % (len(codes), missing, changed_family)))

    # B-1b：首批之外的新增码必须能在**某条历史 entry 的 codes 快照**里找到。
    #   这把「可增长」与「可追溯」绑在一起 —— 没有它，任何人往主表塞码都不会红。
    hist_codes = set()
    for e in entries:
        if isinstance(e, dict):
            hist_codes |= set(e.get("codes") or [])
    untracked = sorted(c for c in extra if c not in hist_codes)
    out.append(_check(
        "B-1b", not untracked,
        "新增码必须在 history 里有 entry（可追溯来源）；未登记 %r；新增 %r"
        % (untracked, extra)))

    safe_rows = [r for r in rows if r.get("control_code") == "安全词"]
    out.append(_check(
        "B-2", not safe_rows and "安全词" not in set(codes),
        "安全词不是控制点码，主表里不许有 control_code=安全词 的行"))

    rules_list = (rules or {}).get("rules") if isinstance(rules, dict) else None
    if not isinstance(rules_list, list):
        rules_list = []
    safe_rule = any(
        isinstance(r, dict) and r.get("parent_rule") == "安全词"
        and (r.get("topic_only") is True or r.get("modality") == "permit")
        for r in rules_list
    )
    wl = whitelist if isinstance(whitelist, dict) else {}
    source = wl.get("source") if isinstance(wl.get("source"), dict) else {}
    wl_mapped = (source.get("legacy_rule_id") == "安全词"
                 and isinstance(wl.get("words"), list) and bool(wl["words"]))
    retired = _safe_word_retired(cp)
    out.append(_check(
        "B-3", wl_mapped or retired,
        "安全词必须已处置：白名单 source.legacy_rule_id=安全词（含 words）"
        "或显式 retired_codes；当前白名单=%s / 主题规则=%s / 退役=%s"
        % (wl_mapped, safe_rule, retired)))

    by_parent = {}
    for r in rules_list:
        if isinstance(r, dict):
            by_parent.setdefault(r.get("parent_rule"), []).append(r)
    active_codes = sorted(r.get("control_code") for r in rows
                          if r.get("status") == "active")
    no_rule = []
    for code in active_codes:
        ok = any(_rule_enabled(r)
                 and (r.get("external_ref") or r.get("authority_ref"))
                 for r in by_parent.get(code, []))
        if not ok:
            no_rule.append(code)
    out.append(_check(
        "B-4", not no_rule,
        "每个 active 控制点至少有一条 enabled 规则且 external_ref 非空；"
        "缺 %d：%r" % (len(no_rule), no_rule)))

    u02_rows = [r for r in rows if r.get("control_code") == "U02"]
    u02_enabled = [r for r in by_parent.get("U02", []) if _rule_enabled(r)]
    u02_ok = (len(u02_rows) == 1
              and u02_rows[0].get("status") == "deprecated"
              and not u02_enabled)
    out.append(_check(
        "B-5", u02_ok,
        "U02 必须存在且 status=deprecated，且没有 enabled 规则挂到它"
        "（行数=%d / status=%r / enabled 规则=%d）"
        % (len(u02_rows),
           u02_rows[0].get("status") if u02_rows else None,
           len(u02_enabled))))

    entries = (history or {}).get("entries") if isinstance(history, dict) else None
    if not isinstance(entries, list) or not entries:
        out.append(_check("B-6", False,
                          "history.entries 缺失或为空 —— 无法对拍历史码"))
        out.append(_check("B-7", True,
                          "历史无 name_by_code 快照；只对拍码集合，不冒充语义对拍"))
        return out

    missing_hist = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            missing_hist.append(f"#{i} 不是对象")
            continue
        cur = set(e.get("codes") or [])
        lack = sorted(expected - cur)
        if lack:
            missing_hist.append(f"#{i} 缺 {lack}")
    out.append(_check(
        "B-6", not missing_hist,
        "首批码必须出现在每一条历史快照里（消失后再出现 = 复用风险）；"
        "不合格 %d：%r" % (len(missing_hist), missing_hist[:4])))

    # 语义对拍只有历史里存了 name_by_code 时才能做；没有就不假装做过。
    hist_names = {}
    name_conflict = []
    for e in entries:
        nbc = e.get("name_by_code") if isinstance(e, dict) else None
        if not isinstance(nbc, dict):
            continue
        for code, name in nbc.items():
            if code in hist_names and hist_names[code] != name:
                name_conflict.append(f"{code}:{hist_names[code]!r}->{name!r}")
            hist_names[code] = name
    cur_names = {r.get("control_code"): r.get("control_name") for r in rows}
    for code, name in cur_names.items():
        if code in hist_names and hist_names[code] != name:
            name_conflict.append(f"{code}:{hist_names[code]!r}->{name!r}")
    has_name_snapshot = bool(hist_names)
    out.append(_check(
        "B-7", not name_conflict,
        ("历史 name_by_code 与当前 control_name 一致" if has_name_snapshot
         else "历史无 name_by_code 快照；只对拍码集合，不冒充语义对拍")
        + (f" · 冲突 {name_conflict[:4]}" if name_conflict else "")))
    return out


# ───────── 行 71b：规则指向的控制点必须真实存在 ─────────

# 规则里允许指向「不是控制点码」的父级，只有这一种。
# 安全词是白名单侧的处置对象，不是主表里的 control_code（B-2 明确禁止它入表）。
RULE_PARENT_NON_CODES = ("安全词",)


def check_rule_parents(cp, rules):
    """**每条规则的 `parent_rule` 必须指向一个真实存在的控制点。**

    这是 C74-1 的**反面**，而那个反面此前完全没有判据：

      * `C74-1`  问「主表新增了一个控制点，有没有规则引用它」—— 防的是**孤儿控制点**；
      * `C71-RP` 问「规则指向的那个东西，主表里存不存在」—— 防的是**悬空指针**。

    只查前一个方向时，一条规则的 `parent_rule` 写成 `__PENDING_CONTROL_POINT__`
    这类哨兵值，引擎 hit 会带出一个不属于任何控制点的字符串，而**全仓没有一个检查器会说话**
    （`verify_engine_contract.py:184` 的 V1c 判的是键在不在，哨兵能过）。

    ★ 为什么这条不能省：「规则还没想好归到哪个控制点」是**正常中间状态**，
      但如果它没有执行点，那个中间状态就会一路带进生产 hit 里 ——
      而它的表现不是报错，是「每条内容都命中一个不存在的控制点」。
    """
    if rules is None:
        # ★ 「没提供」与「提供了但不合法」必须分开：
        #   前者是调用方的事（main() 已在缺文件时落 **未测** 退 2），
        #   后者才是红。混在一起会让自测夹具全部假红 ——
        #   而一个会误报的检查器比没有检查器更糟（§2.1.1）。
        return []
    if not isinstance(rules, dict):
        return [_check("C71-RP", False,
                       "E_RULES_UNREADABLE：rules-v1.json 不是对象，无法核对规则指向")]
    rules_list = rules.get("rules")
    if not isinstance(rules_list, list):
        return [_check("C71-RP", False, "rules-v1.json 的 rules 不是数组")]

    known = set(_codes(cp)) | set(RULE_PARENT_NON_CODES)
    dangling = []
    blank = []
    for rule in rules_list:
        if not isinstance(rule, dict):
            continue
        parent = rule.get("parent_rule")
        ident = rule.get("rule_key") or rule.get("rule_id") or rule.get("id") or "?"
        if _blank(parent):
            blank.append(str(ident))
        elif parent not in known:
            dangling.append("%s→%r" % (ident, parent))

    out = []
    out.append(_check(
        "C71-RP1", not blank,
        "每条规则都必须有 parent_rule；缺 %d 条：%r" % (len(blank), blank[:10])))
    out.append(_check(
        "C71-RP2", not dangling,
        "规则的 parent_rule 必须属于「主表 control_code 全集 ∪ %r」；"
        "悬空 %d 条：%r（示例：%r）"
        % (list(RULE_PARENT_NON_CODES), len(dangling), dangling[:10],
           sorted(known)[:4])))
    return out


# ─────────────────────────── 汇总 ───────────────────────────

def evaluate(cp, rt, history=None, rules=None, require_history=False,
             report=None, rows=(), category_map=None, category_map2=None,
             whitelist=None) -> dict:
    checks = []
    checks += check_control_points(cp)
    checks += check_routing(rt, cp)
    checks += check_empty_families(cp)
    checks += check_count_denominator(cp, report)
    checks += check_registry(cp)
    if require_history or history is not None:
        checks += check_history(cp, history)
    checks += check_new_codes(cp, history, rules)
    if 69 in rows:
        checks += check_family_skeleton(cp)
        checks += check_category_mapping(cp, category_map)
        if category_map2 is not None:
            checks.append(_check(
                "CAT-6", category_map == category_map2,
                "同一映射表连跑两次结果必须一致"))
    if 71 in rows:
        checks += check_first_batch(cp, rules, history, whitelist)
    # ★ 不受 --row 限制：悬空 parent_rule 是**任何**行都该看见的问题。
    #   放进 `if 71 in rows` 里，会让 `--row 69` 那份读数对它默默无闻。
    checks += check_rule_parents(cp, rules)
    reds = [c for c in checks if not c["ok"]]
    return {"checks": checks, "reds": reds,
            "verdict": "red" if reds else "ok",
            "exit_code": 1 if reds else 0}


# ──────────────────── 反向对照（自测）────────────────────

def _fixtures():
    """造一对最小的合法样本。**不读盘** —— 自测必须能在没有主表时也跑。"""
    cp = {
        "table_version": "test-v1",
        "families": ["F1", "F2", "F3"],
        "known_gaps": [{"code": "X02", "issue": "test"}],
        "empty_families": [{"family": "F3", "state": "无控制点", "reason": "待签"}],
        "control_points": [
            {"control_code": "X01", "control_name": "a", "family": "F1",
             "judge_type": "literal", "authority_kind": "external",
             "authority_ref": [{"entry_id": "E1"}], "parent": None,
             "version": "v1", "status": "active"},
            {"control_code": "X02", "control_name": "b", "family": "F2",
             "judge_type": "semantic", "authority_kind": "internal",
             "authority_ref": [], "parent": None, "version": "v1", "status": "deprecated",
             "authority_ref_exemption": {"applies": True, "rule": "deprecated 豁免"},
             "deprecated_note": "停用码不参与 L6-4"},
        ],
    }
    rt = {
        "routing_version": "test-v1",
        "field_set": {"fields": ["control_code", "owner", "layer", "due", "escalation", "appeal"], "count": 6},
        "routes": [
            {"control_code": "X01", "owner": "法务", "layer": "DP4",
             "due": "2d", "escalation": "项目统筹", "appeal": "receipt_id"},
            {"control_code": "X02", "owner": "产品", "layer": "DP3",
             "due": "2d", "escalation": "项目统筹", "appeal": "receipt_id"},
        ],
    }
    return cp, rt


def _deep(obj):
    return json.loads(json.dumps(obj))


def selftest(verbose: bool = False) -> int:
    results = []

    def expect(name, cp, rt, want_ok, history=None, rules=None):
        r = evaluate(cp, rt, history, rules)
        got = (r["verdict"] == "ok")
        results.append((name, got == want_ok, f"期望 {'绿' if want_ok else '红'}，实际 {r['verdict']}"
                        + ("" if got == want_ok else f"；红项={[c['id'] for c in r['reds']]}")))
        if verbose:
            print(f"    {'✓' if got == want_ok else '✗'} {name} → {r['verdict']}")

    cp0, rt0 = _fixtures()

    # ① 好样本必须绿
    expect("好样本", _deep(cp0), _deep(rt0), True)

    # ② 删一个码 → RT-1 红（集合不恒等）
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"].pop(0)
    expect("删一个码", cp, rt, False)

    # ③ 把 active 的 authority_ref 清空 → CP-4 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0]["authority_ref"] = []
    expect("active 缺依据", cp, rt, False)

    # ④ 改一个 route owner 为空 → RT-3 红
    cp, rt = _deep(cp0), _deep(rt0)
    rt["routes"][0]["owner"] = ""
    expect("owner 为空", cp, rt, False)

    # ⑤ 空族与数据不一致 → EF-1 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["empty_families"] = [{"family": "F1", "state": "无控制点", "reason": "x"}]  # F1 实际有码
    expect("空族不一致", cp, rt, False)

    # ⑥ 停用码被静默移除（不在表里但 known_gaps 记着）→ CP-2b 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"] = [r for r in cp["control_points"] if r["control_code"] != "X02"]
    rt["routes"] = [r for r in rt["routes"] if r["control_code"] != "X02"]
    expect("停用码消失", cp, rt, False)

    # ⑦ 停用码缺 exemption → CP-4b 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][1].pop("authority_ref_exemption")
    expect("停用码无豁免", cp, rt, False)

    # ⑧ layer 非法 → RT-4 红
    cp, rt = _deep(cp0), _deep(rt0)
    rt["routes"][0]["layer"] = "DP9"
    expect("layer 非法", cp, rt, False)

    # ⑨ 缺字段 → CP-1 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0].pop("judge_type")
    expect("缺九字段之一", cp, rt, False)

    # ⑩ table_version 空 → CP-6 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["table_version"] = ""
    expect("table_version 空", cp, rt, False)

    # ⑪ C-70/74/76：好样本 + 历史/规则
    cp, rt = _deep(cp0), _deep(rt0)
    hist = {
        "entries": [{
            "version": cp["table_version"], "at": "2026-10-18",
            "who": "test", "why": "baseline", "evidence": ["README.md"],
            "codes": [r["control_code"] for r in cp["control_points"]],
            "family_by_code": {r["control_code"]: r["family"]
                               for r in cp["control_points"]},
        }]
    }
    rules = {"rules": [{"parent_rule": r["control_code"]}
                       for r in cp["control_points"]]}
    expect("历史/规则好样本", cp, rt, True, hist, rules)

    # ⑫ 改族但版本/历史没跟 → H-5 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0]["family"] = "F2"
    expect("改族未升版本", cp, rt, False, hist, rules)

    # ⑬ 新增码缺规则/依据/版本 + 版本未递增 → C74 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"].append({
        "control_code": "X03", "control_name": "new", "family": "F1",
        "judge_type": "literal", "authority_kind": "external",
        "authority_ref": [], "parent": None, "version": "", "status": "active",
    })
    rt["routes"].append({"control_code": "X03", "owner": "法务", "layer": "DP4",
                         "due": "2d", "escalation": "项目统筹", "appeal": "receipt_id"})
    hist_cur = _deep(hist)
    hist_cur["entries"].append({
        "version": "test-v2", "at": "2026-10-19", "who": "test", "why": "add X03",
        "evidence": ["README.md"],
        "codes": [r["control_code"] for r in cp["control_points"]],
        "family_by_code": {r["control_code"]: r["family"] for r in cp["control_points"]},
    })
    cp["table_version"] = "test-v2"
    r_bad = evaluate(cp, rt, hist_cur, rules)
    ids = {c["id"] for c in r_bad["reds"]}
    results.append(("新增码缺三条件", {"C74-1", "C74-2", "C74-3"} <= ids,
                    f"红项={sorted(ids)}"))

    # ⑭ 新码三条件齐但版本未递增 → C74-4 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"].append({
        "control_code": "X03", "control_name": "new", "family": "F1",
        "judge_type": "literal", "authority_kind": "external",
        "authority_ref": [{"entry_id": "E3"}], "parent": None,
        "version": "v1", "status": "active",
    })
    rt["routes"].append({"control_code": "X03", "owner": "法务", "layer": "DP4",
                         "due": "2d", "escalation": "项目统筹", "appeal": "receipt_id"})
    hist_same = _deep(hist_cur)
    hist_same["entries"][-1]["version"] = cp["table_version"]
    rules_x3 = {"rules": rules["rules"] + [{"parent_rule": "X03"}]}
    r_bad2 = evaluate(cp, rt, hist_same, rules_x3)
    results.append(("新码版本未递增", "C74-4" in {c["id"] for c in r_bad2["reds"]},
                    f"红项={sorted({c['id'] for c in r_bad2['reds']})}"))

    # ⑮ 跨族拆分无批准 → C76-2 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0]["families"] = ["F1", "F2"]
    expect("跨族拆分无批准", cp, rt, False, hist, rules)

    # ⑯ 同一 code 跨族 → CP-2/C76-3 红
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"].append(dict(cp["control_points"][0], family="F2"))
    expect("同一 code 跨族", cp, rt, False, hist, rules)

    # ⑰b C-78 数量口径（行 78 的 ②③）
    #
    # ★ 这里的样本是**构造的**，因为盘上没有真实 58 子类清单（README 明写「待补」）。
    #   用构造样本验的是「口径不一致时会不会报警」，不是「58 到底几条」。
    from base.control_points import control_point_denominator_problems as _cdp

    cp, rt = _deep(cp0), _deep(rt0)
    _n = len(cp["control_points"])

    # 好样本：声明的总数等于主表
    good_report = {"control_points_total": _n,
                   "control_points_active": sum(1 for r in cp["control_points"]
                                                if r.get("status") == "active")}
    results.append((
        "口径=主表 → 不报警",
        _cdp(good_report, cp) == [],
        str(_cdp(good_report, cp))))

    # ★ 坏样本①：拿 58 当总数（本行要防的那个具体形状）
    bad58 = {"control_points_total": 58}
    results.append((
        "★ 58 当总数 → 必报警",
        bool(_cdp(bad58, cp)),
        str(_cdp(bad58, cp))))

    # ★ 坏样本②：分母来源是子类
    bad_denom = {"denominators": {"coverage": "subclass"}}
    results.append((
        "★ 子类当分母 → 必报警",
        bool(_cdp(bad_denom, cp)),
        str(_cdp(bad_denom, cp))))

    # ★ 坏样本③：子类计数之和 ≠ 主表（58 冒充控制点的变体）
    bad_sum = {"subclass_counts": {"a": 30, "b": 28}}
    results.append((
        "★ 子类计数之和≠主表 → 必报警",
        bool(_cdp(bad_sum, cp)),
        str(_cdp(bad_sum, cp))))

    # ★ 正样本：没有子类数据 → **不报警**（防恒红）
    results.append((
        "无子类数据 → 不误报",
        _cdp({}, cp) == [] and _cdp({"subclass_counts": {}}, cp) == [],
        str(_cdp({"subclass_counts": {}}, cp))))

    # ★ 正样本：子类计数之和 == 主表 → 不报警（展示用，一致就不算矛盾）
    ok_sum = {"subclass_counts": {"a": _n}}
    results.append((
        "子类之和=主板 → 不误报",
        _cdp(ok_sum, cp) == [],
        str(_cdp(ok_sum, cp))))

    # ★ 主表读不出 → 判不了，要说话（不是静默通过）
    results.append((
        "★ 主表坏 → 明说判不了",
        bool(_cdp({}, {})),
        str(_cdp({}, {}))))

    # ⑰ 跨族拆分有显式批准 → 不误报（反向对照：不是恒红）
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0]["families"] = ["F1", "F2"]
    cp["control_points"][0]["family_split_approval"] = {
        "who": "产品+法务", "why": "跨族拆分批准", "evidence": ["README.md"]}
    expect("跨族拆分有批准", cp, rt, True, hist, rules)

    # ⑰c C-70 正样本：改族 + 升版本 + 追加显式历史 → 绿；旧值仍可查。
    cp, rt = _deep(cp0), _deep(rt0)
    hist_new = _deep(hist)
    cp["table_version"] = "test-v2"
    cp["control_points"][0]["family"] = "F2"
    cp["empty_families"] = [
        {"family": f, "state": "无控制点", "reason": "test"}
        for f in ("F1", "F3")
    ]
    hist_new["entries"].append({
        "version": "test-v2", "at": "2026-10-19",
        "who": "产品+法务", "why": "改族",
        "evidence": ["README.md"],
        "codes": [r["control_code"] for r in cp["control_points"]],
        "family_by_code": {r["control_code"]: r["family"]
                           for r in cp["control_points"]},
    })
    r_pos = evaluate(cp, rt, hist_new, rules)
    results.append((
        "改族+升版本+追加历史 → 绿",
        r_pos["verdict"] == "ok",
        f"红项={[c['id'] for c in r_pos['reds']]}"))
    results.append((
        "旧 history 仍保留旧 family 值",
        hist_new["entries"][0]["family_by_code"].get("X01") == "F1",
        repr(hist_new["entries"][0].get("family_by_code"))))
    # 只升版本、不追加历史 → H-3 红（反向对照）
    cp_v, rt_v = _deep(cp0), _deep(rt0)
    cp_v["table_version"] = "test-v2"
    r_v = evaluate(cp_v, rt_v, hist, rules)
    results.append((
        "只升版本不追加历史 → 红",
        "H-3" in {c["id"] for c in r_v["reds"]},
        f"红项={[c['id'] for c in r_v['reds']]}"))

    # ⑰d C-76：U 前缀挂 F1 时按 family 字段走，不按首字母推断。
    cp_p, rt_p = _deep(cp0), _deep(rt0)
    hist_p, rules_p = _deep(hist), _deep(rules)
    pref = dict(_deep(cp0["control_points"][0]))
    pref.update({"control_code": "U99", "control_name": "prefix-u",
                 "family": "F1", "status": "active", "version": "v1"})
    cp_p["control_points"].append(pref)
    rt_p["routes"].append({"control_code": "U99", "owner": "法务",
                           "layer": "DP4", "due": "2d",
                           "escalation": "项目统筹", "appeal": "receipt_id"})
    rules_p["rules"].append({"parent_rule": "U99"})
    cp_p["table_version"] = "test-v2"
    hist_p["entries"].append({
        "version": "test-v2", "at": "2026-10-19",
        "who": "产品+法务", "why": "新增 U99",
        "evidence": ["README.md"],
        "codes": sorted(r["control_code"] for r in cp_p["control_points"]),
        "family_by_code": {r["control_code"]: r["family"]
                           for r in cp_p["control_points"]},
    })
    expect("U 前缀按 family=F1 走，不按首字母推断",
           cp_p, rt_p, True, hist_p, rules_p)

    # ⑱ 行 69/71 的纯函数断言（不依赖盘上是否存在 11 项清单）
    def red_ids(checks):
        return {c["id"] for c in checks if not c["ok"]}

    families7 = [f"F{i}" for i in range(1, 8)]
    batch_cp = {
        "families": families7,
        "empty_families": [],
        "control_points": [
            {"control_code": code, "control_name": "name-" + code,
             "family": "F1",
             "status": "deprecated" if code == "U02" else "active"}
            for code in FIRST_BATCH_CODES
        ],
    }
    batch_rules = {
        "rules": [
            {"parent_rule": code, "external_ref": [{"entry_id": "E"}]}
            for code in FIRST_BATCH_CODES if code != "U02"
        ] + [
            {"parent_rule": "U02", "enabled": False},
            {"parent_rule": "安全词", "topic_only": True},
        ]
    }
    batch_hist = {
        "entries": [{
            "codes": list(FIRST_BATCH_CODES),
            "family_by_code": {code: "F1" for code in FIRST_BATCH_CODES},
            "name_by_code": {code: "name-" + code for code in FIRST_BATCH_CODES},
        }]
    }
    batch_wl = {"source": {"legacy_rule_id": "安全词"},
                "words": [{"word": "safe"}]}

    good_cat = {"count": EXPECTED_CATEGORY_COUNT,
                "categories": [
                    {"category": "C%02d" % i,
                     "family": families7[i % len(families7)],
                     "reason": "test"}
                    for i in range(EXPECTED_CATEGORY_COUNT)
                ]}

    results.append(("行69 七族好样本", red_ids(check_family_skeleton(batch_cp)) == set(),
                    str(red_ids(check_family_skeleton(batch_cp)))))
    six = _deep(batch_cp); six["families"] = families7[:6]
    results.append(("行69 六族 → F-1 红", "F-1" in red_ids(check_family_skeleton(six)),
                    str(red_ids(check_family_skeleton(six)))))
    dupfam = _deep(batch_cp); dupfam["families"] = families7[:6] + ["F1"]
    results.append(("行69 重复族 → F-1 红", "F-1" in red_ids(check_family_skeleton(dupfam)),
                    str(red_ids(check_family_skeleton(dupfam)))))

    results.append(("行69 映射缺失 → 不误报",
                    check_category_mapping(batch_cp, None) == [], ""))
    results.append(("行69 映射好样本",
                    red_ids(check_category_mapping(batch_cp, good_cat)) == set(),
                    str(red_ids(check_category_mapping(batch_cp, good_cat)))))
    dupcat = _deep(good_cat); dupcat["categories"][1]["category"] = "C00"
    results.append(("行69 重复 category → CAT-2 红",
                    "CAT-2" in red_ids(check_category_mapping(batch_cp, dupcat)), ""))
    badfam = _deep(good_cat); badfam["categories"][0]["family"] = "未归类"
    shortcat = _deep(good_cat); shortcat["categories"] = shortcat["categories"][:10]
    shortcat["count"] = 11
    results.append(("行69 只有 10 项 → CAT-4 红",
                    "CAT-4" in red_ids(check_category_mapping(batch_cp, shortcat)), ""))
    noreason = _deep(good_cat); noreason["categories"][0].pop("reason")
    results.append(("行69 缺 reason → CAT-5 红",
                    "CAT-5" in red_ids(check_category_mapping(batch_cp, noreason)), ""))
    unclassified = _deep(good_cat); unclassified["categories"][0]["family"] = "未归类"
    results.append(("行69 未归类 → CAT-5 红",
                    "CAT-5" in red_ids(check_category_mapping(batch_cp, unclassified)), ""))

    results.append(("行71 好样本",
                    red_ids(check_first_batch(batch_cp, batch_rules,
                                               batch_hist, batch_wl)) == set(),
                    str(red_ids(check_first_batch(batch_cp, batch_rules,
                                                  batch_hist, batch_wl)))))
    wrong_codes = _deep(batch_cp)
    wrong_codes["control_points"] = wrong_codes["control_points"][:-1]
    results.append(("行71 码集少一个 → B-1a 红",
                    "B-1a" in red_ids(check_first_batch(wrong_codes, batch_rules,
                                                        batch_hist, batch_wl)), ""))
    changed_fam = _deep(batch_cp)
    changed_fam["control_points"][0]["family"] = "F2"
    results.append(("行71 首批码改族 → B-1a 红",
                    "B-1a" in red_ids(check_first_batch(changed_fam, batch_rules,
                                                        batch_hist, batch_wl)), ""))
    naked_new = _deep(batch_cp)
    naked_new["control_points"].append(
        {"control_code": "B99", "control_name": "naked", "family": "F1",
         "status": "draft"})
    results.append(("行71 塞 history 里没有的新码 → B-1b 红",
                    "B-1b" in red_ids(check_first_batch(naked_new, batch_rules,
                                                        batch_hist, batch_wl)), ""))
    tracked_new = _deep(batch_cp)
    tracked_new["control_points"].append(
        {"control_code": "B98", "control_name": "tracked", "family": "F1",
         "status": "draft"})
    tracked_hist = _deep(batch_hist)
    tracked_hist["entries"].append({"codes": list(FIRST_BATCH_CODES) + ["B98"],
                                    "family_by_code": dict(
                                        {c: "F1" for c in FIRST_BATCH_CODES}, B98="F1")})
    results.append(("行71 塞 history 里有的新码 → 必须绿",
                    red_ids(check_first_batch(tracked_new, batch_rules,
                                              tracked_hist, batch_wl)) == set(),
                    str(red_ids(check_first_batch(tracked_new, batch_rules,
                                                  tracked_hist, batch_wl)))))
    safe_row = _deep(batch_cp)
    safe_row["control_points"].append(
        {"control_code": "安全词", "control_name": "safe", "family": "F1",
         "status": "active"})
    results.append(("行71 安全词入表 → B-2 红",
                    "B-2" in red_ids(check_first_batch(safe_row, batch_rules,
                                                       batch_hist, batch_wl)), ""))
    no_wl = {"source": {}, "words": []}
    results.append(("行71 安全词无处置 → B-3 红",
                    "B-3" in red_ids(check_first_batch(batch_cp, batch_rules,
                                                       batch_hist, no_wl)), ""))
    no_ref = _deep(batch_rules)
    no_ref["rules"][0]["external_ref"] = []
    results.append(("行71 active 缺依据 → B-4 红",
                    "B-4" in red_ids(check_first_batch(batch_cp, no_ref,
                                                       batch_hist, batch_wl)), ""))
    u02_on = _deep(batch_cp)
    for r in u02_on["control_points"]:
        if r["control_code"] == "U02":
            r["status"] = "active"
    u02_rules = _deep(batch_rules)
    for r in u02_rules["rules"]:
        if r.get("parent_rule") == "U02":
            r["enabled"] = True
    results.append(("行71 U02 重新启用 → B-5 红",
                    "B-5" in red_ids(check_first_batch(u02_on, u02_rules,
                                                       batch_hist, batch_wl)), ""))
    bad_hist = _deep(batch_hist)
    bad_hist["entries"][0]["codes"] = bad_hist["entries"][0]["codes"][:-1]
    results.append(("行71 历史码消失 → B-6 红",
                    "B-6" in red_ids(check_first_batch(batch_cp, batch_rules,
                                                       bad_hist, batch_wl)), ""))
    bad_name = _deep(batch_hist)
    bad_name["entries"][0]["name_by_code"]["H01"] = "不同语义"
    results.append(("行71 历史语义变化 → B-7 红",
                    "B-7" in red_ids(check_first_batch(batch_cp, batch_rules,
                                                       bad_name, batch_wl)), ""))

    # ══════════════════ C71-RP：规则指向的控制点必须存在 ══════════════════
    #
    # 这一组存在的理由：这条断言在写下来的当天，用的是**真实仓里的规则**跑的，
    # 而真实仓现在全是绿的。一条从没红过的断言不算验证过它（§2.4.1 末段）。
    # 所以下面四条既是自测，也是这条断言自己的执行点。
    rp_cp = {"control_points": [
        {"control_code": "X01"}, {"control_code": "X02"},
    ]}

    # ① 好样本：26 条真实规则那种形状 → 绿
    rp_good = {"rules": [
        {"rule_key": "r1", "parent_rule": "X01"},
        {"rule_key": "r2", "parent_rule": "X02"},
        {"rule_key": "r3", "parent_rule": "安全词"},   # 白名单侧处置对象，不是控制点码
    ]}
    results.append(("C71-RP 好样本",
                    not red_ids(check_rule_parents(rp_cp, rp_good)), ""))

    # ② ★ 核心：哨兵值 → C71-RP2 红
    #    这正是本次派单的起因。候选规则 JSON 的 10 条 parent_rule 全是这个哨兵。
    rp_sentinel = {"rules": [
        {"rule_key": "r1", "parent_rule": "X01"},
        {"rule_key": "r2", "parent_rule": "__PENDING_CONTROL_POINT__"},
    ]}
    results.append(("C71-RP 哨兵值 → 红",
                    "C71-RP2" in red_ids(check_rule_parents(rp_cp, rp_sentinel)), ""))

    # ③ 拼错/已删除的控制点 → 红（不只是哨兵那一种写法）
    rp_typo = {"rules": [{"rule_key": "r1", "parent_rule": "X99"}]}
    results.append(("C71-RP 悬空码 → 红",
                    "C71-RP2" in red_ids(check_rule_parents(rp_cp, rp_typo)), ""))

    # ④ parent_rule 缺失 → C71-RP1 红（与「写错」分开报）
    rp_blank = {"rules": [{"rule_key": "r1"}]}
    results.append(("C71-RP 缺 parent_rule → 红",
                    "C71-RP1" in red_ids(check_rule_parents(rp_cp, rp_blank)), ""))

    # ⑤ 反向对照：rules 未提供时**不许误红**（自测夹具大多不传 rules）
    results.append(("C71-RP 未提供 rules → 不误报",
                    not check_rule_parents(rp_cp, None), ""))

    # ⑥ 反向对照：rules 提供了但不是对象 → 必须红，不许静默放过
    results.append(("C71-RP rules 非对象 → 红",
                    bool(red_ids(check_rule_parents(rp_cp, []))), ""))

    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 62)
    print("verify_control_points · 反向对照")
    print("=" * 62)
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name:<16} {detail}")
    print()
    if ok == total:
        print(f"✅ {ok}/{total} 项全过（反向对照全过：坏样本会红，好样本会绿）")
        return 0
    print(f"✗ {ok}/{total} 项通过，{total - ok} 项失败")
    return 1


# ─────────────────────────── 主流程 ───────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--table", default=str(TABLE))
    ap.add_argument("--routing", default=str(ROUTING))
    ap.add_argument("--history", default=str(HISTORY))
    ap.add_argument("--rules", default=str(RULES))
    ap.add_argument("--whitelist", default=str(WHITELIST))
    ap.add_argument("--category-map", default=str(CATEGORY_MAP))
    ap.add_argument("--row", type=int, choices=(69, 71),
                    help="只跑验收表某一行需要的断言；69 缺映射表时退 2")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.verbose)

    cp, err1 = load(Path(args.table))
    rt, err2 = load(Path(args.routing))
    hist, err3 = load(Path(args.history))
    rules, err4 = load(Path(args.rules))
    whitelist, err5 = load(Path(args.whitelist))

    def untested(msg):
        if args.json:
            print(json.dumps({"verdict": "untested", "detail": msg},
                             ensure_ascii=False, indent=1))
        else:
            print(f"⚠ 未测：{msg} —— 未测不是通过", file=sys.stderr)
        return 2

    # 读不到 → 未测（2），不是红（1），也不是通过（0）
    if cp is None or rt is None:
        return untested("；".join(e for e in (err1, err2) if e))

    category_map = category_map2 = None
    if args.row == 69:
        category_map, err6 = load(Path(args.category_map))
        category_map2, err6b = load(Path(args.category_map))
        if category_map is None or category_map2 is None:
            return untested(
                "11 项一级分类清单未提供或读不出（%s：%s / %s）；"
                "本条保持 untested，不编造映射"
                % (args.category_map, err6, err6b))
    else:
        # 默认主检查：映射表存在就校验；不存在不造假，也不影响其它断言。
        if Path(args.category_map).exists():
            category_map, _err6 = load(Path(args.category_map))
            category_map2, _err6b = load(Path(args.category_map))
    # ★ 2026-10-21 改：原先是 `args.row == 71`，于是**默认路径**（row=None，
    #   实际 rows=(69,71)）反而绕过了这道闸 —— 规则读不出时不会落未测，
    #   而是带着 rules=None 往下跑。加 C71-RP 之后这必须堵上：
    #   「没测到规则指向」不许和「规则指向都正确」长得一样。
    #
    # ★ 两段分开判，因为覆盖面不同：
    #   * `rules` —— C71-RP **在每一行**都跑，所以每一行都需要它；
    #   * `hist` / `whitelist` —— 只有行 71（check_first_batch）用得到。
    #   合成一段会有一个方向错：`--row 69` 缺 rules 时，C71-RP 返回 [] 静默通过，
    #   而那正是「未测被读成通过」—— 本项目已经栽过好几次的那个形状。
    if rules is None:
        return untested(err4)
    if args.row in (None, 71):
        missing = []
        if hist is None:
            missing.append(err3)
        if whitelist is None:
            missing.append(err5)
        if missing:
            return untested("；".join(m for m in missing if m))

    rows = (args.row,) if args.row else (69, 71)
    r = evaluate(cp, rt, hist, rules, require_history=True,
                 rows=rows, category_map=category_map,
                 category_map2=category_map2, whitelist=whitelist)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return r["exit_code"]

    print("=" * 62)
    print("控制点主表 ↔ 路由表 · 契约验收")
    print("=" * 62)
    print(f"  主表 {args.table}")
    print(f"  路由 {args.routing}")
    if args.row:
        print(f"  验收行 {args.row}")
    if args.row is None and category_map is None:
        print("  ℹ 行 69：11 项一级分类清单未提供 —— 该行保持 untested（不造假）")
    print()
    for c in r["checks"]:
        print(f"  {'✓' if c['ok'] else '✗'} {c['id']:<7} {c['detail']}")
    print()
    if r["reds"]:
        print(f"✗ {len(r['reds'])} 项红：{[c['id'] for c in r['reds']]}")
        return 1
    print(f"✅ {len(r['checks'])} 项全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
