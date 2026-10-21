#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_brand_rules.py —— 品牌用词候选规则的「排除逻辑只有一份」执行点。

## 问题形状（AGENTS.md §2.4）

候选 JSON 里每条规则原先有两处在说「什么情况下不算命中」：

    match.exclude_patterns : ["(?i)clinical\\s+(trial|study|research|evidence)", ...]  ← 执行点
    context_exclusion      : "引用竞品/法规/研究原文时排除……"                          ← 文本注释

这是同一个知识的两个副本，而**只有一个是执行点**。改了一处忘了另一处，
规则就会「说排除却仍然命中」，而没有任何东西会红。

现在 `context_exclusion` 是结构化数组：

    [{id, pattern, note}, ...]

`match.exclude_patterns` 必须由它的 `pattern` 派生。本脚本断言两者**集合恒等**，
不是包含；并检查 pattern 可编译、note 非空、两侧有/无一致。

## 只认一个真源

只读 `PMO/implement/品牌用词规则-候选-v1.json`。规则不复制进本文件 —— 否则又成两份。

## 退出码

- `0` 全过
- `1` 有红
- `2` **未测**：候选 JSON 不在盘上 / 读不出 / 顶层不是预期结构（与 AGENTS.md §2.4.2 的 L3 同口径）

## 用法

    python3 tools/verify_brand_rules.py
    python3 tools/verify_brand_rules.py --controls
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ★ 这个字符串必须与 tools/verifier-coverage.json 的 subjects 逐字相同（C 段反证）
CANDIDATE_REL = "PMO/implement/品牌用词规则-候选-v1.json"
CANDIDATE = ROOT / CANDIDATE_REL


def _load(path: Path):
    """返回 (data, error)。error 非空 = 未测，不是「空规则」。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "文件不存在：%s" % path
    except OSError as exc:
        return None, "读不出 %s：%s" % (path, exc)
    except json.JSONDecodeError as exc:
        return None, "%s 不是合法 JSON：%s" % (path, exc)


def check(path: Path = CANDIDATE) -> dict:
    """对候选 JSON 跑 B1–B4。返回 {verdict, assertions, reds, untested}。"""
    data, err = _load(path)
    if err:
        return {"verdict": "untested", "assertions": [], "reds": [], "untested": [err]}
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        return {
            "verdict": "untested", "assertions": [], "reds": [],
            "untested": ["%s 顶层不是 {rules: [...]}（结构读不出）" % path],
        }

    assertions = []
    reds = []
    with_exclusion = []
    no_exclusion = []
    no_exclusion_with_note = []

    def add(aid, ok, reading):
        assertions.append({"id": aid, "ok": bool(ok), "reading": reading})
        if not ok:
            reds.append("%s：%s" % (aid, reading))

    for rule in data["rules"]:
        if not isinstance(rule, dict):
            add("B1", False, "规则条目不是对象")
            continue
        rk = str(rule.get("rule_key") or "?")
        match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
        ep_raw = match.get("exclude_patterns")
        ce_raw = rule.get("context_exclusion")

        # B1：context_exclusion 必须是数组；每项 {id, pattern, note} 都非空；id 不重复
        problems = []
        ce_patterns = []
        if not isinstance(ce_raw, list):
            problems.append("context_exclusion 不是数组（%s）" % type(ce_raw).__name__)
        else:
            seen_ids = set()
            for i, item in enumerate(ce_raw):
                if not isinstance(item, dict):
                    problems.append("[%d] 不是对象" % i)
                    continue
                for f in ("id", "pattern", "note"):
                    v = item.get(f)
                    if not isinstance(v, str) or not v.strip():
                        problems.append("[%d].%s 为空或非字符串" % (i, f))
                iid = item.get("id")
                if isinstance(iid, str) and iid:
                    if iid in seen_ids:
                        problems.append("[%d].id 重复：%s" % (i, iid))
                    seen_ids.add(iid)
                pat = item.get("pattern")
                if isinstance(pat, str) and pat.strip():
                    ce_patterns.append(pat)
        add("B1", not problems,
            "%s：context_exclusion %s；%s"
            % (rk, ("%d 项" % len(ce_raw)) if isinstance(ce_raw, list) else type(ce_raw).__name__,
               "、".join(problems) if problems else "schema/note/id 全部合规"))

        # B2：每个 pattern 必须能编译（逐条 pattern 计数）
        if isinstance(ce_raw, list):
            for i, item in enumerate(ce_raw):
                pat = item.get("pattern") if isinstance(item, dict) else None
                if not isinstance(pat, str) or not pat.strip():
                    add("B2", False, "%s：pattern[%d] 为空，无法编译" % (rk, i))
                    continue
                try:
                    re.compile(pat)
                    add("B2", True, "%s：pattern[%d] 编译通过" % (rk, i))
                except re.error as exc:
                    add("B2", False, "%s：pattern[%d] 编译失败：%s" % (rk, i, exc))

        # B3：match.exclude_patterns 与 context_exclusion[].pattern 集合恒等
        if ep_raw is None:
            ep = []
            ep_type_ok = True
        elif isinstance(ep_raw, list):
            ep = [str(x) for x in ep_raw]
            ep_type_ok = True
        else:
            ep = []
            ep_type_ok = False
        ep_set = set(ep)
        ce_set = set(ce_patterns)
        extra_ep = sorted(ep_set - ce_set)
        extra_ce = sorted(ce_set - ep_set)
        add("B3", ep_type_ok and ep_set == ce_set,
            "%s：exclude_patterns=%d / context_exclusion[].pattern=%d；"
            "多出 exclude=%s；多出 context_exclusion=%s%s"
            % (rk, len(ep_set), len(ce_set), extra_ep, extra_ce,
               "" if ep_type_ok else "；exclude_patterns 不是数组"))

        # B4：有 exclude_patterns 就必须有 context_exclusion，反之亦然
        has_ep = isinstance(ep_raw, list) and len(ep_raw) > 0
        has_ce = isinstance(ce_raw, list) and len(ce_raw) > 0
        add("B4", has_ep == has_ce,
            "%s：有 exclude_patterns=%s / 有 context_exclusion=%s"
            % (rk, has_ep, has_ce))

        # 结论行必须把「有排除项」与「没有排除项」分开：
        # 后者两侧都是空集，B1/B3/B4 的 ✅ 是空转，不能读成「排除逻辑已验证」。
        if ep_set or ce_set or has_ep or has_ce:
            with_exclusion.append(rk)
        else:
            no_exclusion.append(rk)
            note = match.get("context_note")
            if isinstance(note, str) and note.strip():
                no_exclusion_with_note.append({"rule_key": rk, "note": note.strip()})

    return {
        "verdict": "red" if reds else "pass",
        "assertions": assertions,
        "reds": reds,
        "untested": [],
        "with_exclusion": with_exclusion,
        "no_exclusion": no_exclusion,
        "no_exclusion_with_note": no_exclusion_with_note,
    }


def _print_result(result: dict):
    if result["verdict"] == "untested":
        print("⚠ 未测（退出码 2，不是通过，也不是红）：")
        for u in result["untested"]:
            print("   - %s" % u)
        print("   候选 JSON 读不出时只能记未测。")
        return
    n_pass = sum(1 for a in result["assertions"] if a["ok"])
    for a in result["assertions"]:
        print("%s %s  %s" % ("✅" if a["ok"] else "❌", a["id"], a["reading"]))
    print()
    n_with = len(result.get("with_exclusion") or [])
    n_no = len(result.get("no_exclusion") or [])
    notes = result.get("no_exclusion_with_note") or []
    print("✅ B3 集合恒等：%d 条有排除项的规则，exclude_patterns ≡ context_exclusion[].pattern"
          % n_with)
    print("⚠ %d 条规则没有排除项（context_exclusion=[] 且 exclude_patterns=[]）——" % n_no)
    print("   这不是「排除已验证」，是「没有声明排除」；要不要补 pattern 是产品/法务决定。")
    if notes:
        print("⚠ 其中 %d 条有文本说明但无执行点：" % len(notes))
        for x in notes:
            print("   - %s：%s" % (x["rule_key"], x["note"]))
    print()
    print("%s 品牌用词规则自证 %d/%d 项通过（B3：%d 条有排除项；%d 条无排除项）"
          % ("✅" if not result["reds"] else "❌",
             n_pass, len(result["assertions"]), n_with, n_no))
    if result["reds"]:
        print("❌ 排除逻辑两份副本已经漂移；改候选 JSON，不要改本脚本自动圆。")


# ── --controls：坏样本必须红，好样本必须绿 ────────────────────────────────

def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_case(name: str, path: Path, want_verdict: str, want_id: str | None = None) -> bool:
    result = check(path)
    ok = result["verdict"] == want_verdict
    if want_id:
        ok = ok and any(r.startswith(want_id + "：") for r in result["reds"])
    print("  %s %s：verdict=%s%s"
          % ("✅" if ok else "❌", name, result["verdict"],
             ("；红里含 %s" % want_id) if want_id else ""))
    if not ok:
        for r in result["reds"][:4]:
            print("       - %s" % r)
        for u in result["untested"][:3]:
            print("       ⚠ %s" % u)
    return ok


def run_controls() -> int:
    print("=" * 72)
    print("verify_brand_rules · --controls（从真实候选 JSON 派生坏样本）")
    print("=" * 72)
    data, err = _load(CANDIDATE)
    if err:
        print("⚠ 未测：%s" % err)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="brand-rules-controls-"))
    ok_all = True
    try:
        good = tmp / "good.json"
        _write(good, data)
        ok_all &= _run_case("好样本", good, "pass")

        # 1) 删掉一条 exclude_patterns → B3 集合不等
        bad = copy.deepcopy(data)
        target = next(r for r in bad["rules"]
                      if isinstance(r.get("match"), dict)
                      and isinstance(r["match"].get("exclude_patterns"), list)
                      and len(r["match"]["exclude_patterns"]) >= 2)
        target["match"]["exclude_patterns"].pop()
        p = tmp / "bad-missing-pattern.json"; _write(p, bad)
        ok_all &= _run_case("坏样本：删掉一条 exclude_patterns", p, "red", "B3")

        # 2) 删掉一条 context_exclusion → B3 集合不等
        bad = copy.deepcopy(data)
        target = next(r for r in bad["rules"]
                      if isinstance(r.get("context_exclusion"), list)
                      and len(r["context_exclusion"]) >= 2)
        target["context_exclusion"].pop()
        p = tmp / "bad-missing-context.json"; _write(p, bad)
        ok_all &= _run_case("坏样本：删掉一条 context_exclusion", p, "red", "B3")

        # 3) pattern 编译不过：两边同时改成 "("，集合仍相等，但 B2 必须红
        bad = copy.deepcopy(data)
        target = next(r for r in bad["rules"]
                      if isinstance(r.get("context_exclusion"), list)
                      and len(r["context_exclusion"]) >= 1)
        target["context_exclusion"][0]["pattern"] = "("
        if isinstance(target.get("match"), dict) and isinstance(target["match"].get("exclude_patterns"), list):
            target["match"]["exclude_patterns"] = [x["pattern"] for x in target["context_exclusion"]]
        p = tmp / "bad-regex.json"; _write(p, bad)
        ok_all &= _run_case("坏样本：pattern 编译不过", p, "red", "B2")

        # 4) note 为空 → B1
        bad = copy.deepcopy(data)
        target = next(r for r in bad["rules"]
                      if isinstance(r.get("context_exclusion"), list)
                      and len(r["context_exclusion"]) >= 1)
        target["context_exclusion"][0]["note"] = ""
        p = tmp / "bad-empty-note.json"; _write(p, bad)
        ok_all &= _run_case("坏样本：note 为空", p, "red", "B1")

        # 5) context_exclusion 仍是旧字符串 → B1
        bad = copy.deepcopy(data)
        target = next(r for r in bad["rules"]
                      if isinstance(r.get("context_exclusion"), list)
                      and len(r["context_exclusion"]) >= 1)
        target["context_exclusion"] = "旧的文本注释，还没结构化"
        p = tmp / "bad-string.json"; _write(p, bad)
        ok_all &= _run_case("坏样本：context_exclusion 仍是字符串", p, "red", "B1")

        # 6) 10 条全空：B3 恒等确实成立，但结论行必须把「没有排除项」单独说出来。
        #    若输出仍说「集合恒等，且可编译、note 非空」而没有 ⚠ 计数，就是空转被抹平。
        bad = copy.deepcopy(data)
        for r in bad["rules"]:
            if isinstance(r, dict):
                r["context_exclusion"] = []
                if isinstance(r.get("match"), dict):
                    r["match"]["exclude_patterns"] = []
        p = tmp / "all-empty.json"; _write(p, bad)
        r = check(p)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _print_result(r)
        out = buf.getvalue()
        ok = (r["verdict"] == "pass"
              and len(r.get("no_exclusion") or []) == 10
              and "✅ B3 集合恒等：0 条有排除项的规则" in out
              and "⚠ 10 条规则没有排除项" in out
              and "且可编译、note 非空" not in out)
        print("  %s 全空样本：B3 恒等通过，但必须报 10 条无排除项%s"
              % ("✅" if ok else "❌",
                 "" if ok else "（计数不对，或结论行仍在空转）"))
        if not ok:
            print("       output: %s" % out.replace("\n", " / ")[:300])
        ok_all &= ok

        # 7) 文件缺失 → 未测（退 2）
        p = tmp / "does-not-exist.json"
        ok_all &= _run_case("文件缺失", p, "untested")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if ok_all:
        print("✅ --controls 全过：好样本绿；坏样本各自红；文件缺失判未测")
        return 0
    print("❌ --controls 有对照不符；断言或对照本身有问题")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="品牌用词候选规则：排除逻辑单源断言")
    ap.add_argument("--controls", action="store_true", help="跑构造坏样本反向对照")
    ap.add_argument("--file", default=str(CANDIDATE), help="候选 JSON（默认真源）")
    args = ap.parse_args(argv)
    if args.controls:
        return run_controls()
    result = check(Path(args.file))
    _print_result(result)
    return {"pass": 0, "red": 1, "untested": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
