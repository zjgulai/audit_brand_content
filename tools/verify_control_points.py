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


# ─────────────────────────── 汇总 ───────────────────────────

def evaluate(cp, rt) -> dict:
    checks = []
    checks += check_control_points(cp)
    checks += check_routing(rt, cp)
    checks += check_empty_families(cp)
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

    def expect(name, cp, rt, want_ok):
        r = evaluate(cp, rt)
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
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.verbose)

    cp, err1 = load(Path(args.table))
    rt, err2 = load(Path(args.routing))

    # 读不到 → 未测（2），不是红（1），也不是通过（0）
    if cp is None or rt is None:
        msg = "；".join(e for e in (err1, err2) if e)
        if args.json:
            print(json.dumps({"verdict": "untested", "detail": msg}, ensure_ascii=False, indent=1))
        else:
            print(f"⚠ 未测：{msg} —— 未测不是通过", file=sys.stderr)
        return 2

    r = evaluate(cp, rt)

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
