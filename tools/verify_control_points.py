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

TABLE = ROOT / "research" / "governance" / "control-points-v1.json"
ROUTING = ROOT / "research" / "governance" / "routing-v1.json"
HISTORY = ROOT / "research" / "governance" / "control-points-history.json"
RULES = ROOT / "research" / "governance" / "skeleton" / "rules-v1.json"

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


# ─────────────────────────── 汇总 ───────────────────────────

def evaluate(cp, rt, history=None, rules=None, require_history=False) -> dict:
    checks = []
    checks += check_control_points(cp)
    checks += check_routing(rt, cp)
    checks += check_empty_families(cp)
    checks += check_registry(cp)
    if require_history or history is not None:
        checks += check_history(cp, history)
    checks += check_new_codes(cp, history, rules)
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

    # ⑰ 跨族拆分有显式批准 → 不误报（反向对照：不是恒红）
    cp, rt = _deep(cp0), _deep(rt0)
    cp["control_points"][0]["families"] = ["F1", "F2"]
    cp["control_points"][0]["family_split_approval"] = {
        "who": "产品+法务", "why": "跨族拆分批准", "evidence": ["README.md"]}
    expect("跨族拆分有批准", cp, rt, True, hist, rules)

    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 62)
    print("verify_control_points · 反向对照")
    print("=" * 62)
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name:<16} {detail}")
    print()
    if ok == total:
        print(f"✅ {ok}/{total} 项全过（4 类坏样本均会红，好样本会绿）")
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
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.verbose)

    cp, err1 = load(Path(args.table))
    rt, err2 = load(Path(args.routing))
    hist, err3 = load(Path(args.history))
    rules, err4 = load(Path(args.rules))

    # 读不到 → 未测（2），不是红（1），也不是通过（0）
    if cp is None or rt is None:
        msg = "；".join(e for e in (err1, err2) if e)
        if args.json:
            print(json.dumps({"verdict": "untested", "detail": msg}, ensure_ascii=False, indent=1))
        else:
            print(f"⚠ 未测：{msg} —— 未测不是通过", file=sys.stderr)
        return 2

    r = evaluate(cp, rt, hist, rules, require_history=True)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return r["exit_code"]

    print("=" * 62)
    print("控制点主表 ↔ 路由表 · 契约验收")
    print("=" * 62)
    print(f"  主表 {args.table}")
    print(f"  路由 {args.routing}")
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
