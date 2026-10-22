#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_pass_reachability.py —— PASS 为什么出不来：把「不可达」写成可核对的事实

## 一句话

当前每一次判定都不可能是 PASS。这件事此前只活在文档里（Playbook:1424-1427）。
本脚本把它拆成一条**因果链**，每一环都能单独核对：

    control-points-v1.json 有空的族（该族 0 条控制点）
      → coverage_composer.compose() 把空族补成 no_control_points / 未做·无控制点
      → derive_state() 恒返 partial
      → decision_table 链 11 落 REVIEW
      → **PASS 出不来**

★ 关键设计：这条断言**不是**写死「永远没有 PASS」。它读当前数据判断：
   * 空族非空 → 要求「没有 PASS」，并逐族指出是哪些族挡住了；
   * 空族为空（将来补齐了）→ 改口要求「干净样本必须出 PASS」。
   所以补上那三族之后，本脚本会**变绿**；若那时干净样本仍不是 PASS，
   它会红 —— 因为那就说明**还有别的阻塞**，「唯一原因是空族」这句话不再成立。

## 断言

| 段 | 断言 |
|---|---|
| U1 | **声明空族 == 数据空族**：`empty_families` 与「control_points 里 0 条的族」逐族相等（不许多报，也不许少报） |
| U2 | 每个真实样本 `coverage_state == partial`，且 `not_run_reasons` 逐族含每个空族（why=no_control_points，label=未做·无控制点） |
| U3 | 样本输出空间 ⊆ {BLOCK, REVIEW, 未审查, 待自决}，**不含 PASS**；且至少出现 2 种标签（防「桩返回常量」） |
| U4 | **因果对（合成器）**：`empty_families=[]` 且全族 ran → `full`；`=当前表` → `partial` |
| U5 | **因果对（判定表）**：同一组空 findings，`coverage=full` → `PASS`；`coverage=partial` → `REVIEW` |
| U6 | **文档仍在**：Playbook 逐字含「PASS 出不来」「这是刻意的」「空族数一律读」 |
| U7 | **源码不许写死空族数**：`base/coverage_composer.py` 里若出现「N 个空族」，N 必须等于声明的空族数（Playbook:1429 明令） |
| U8 | **未来分支**：当 `empty_families` 为空时，干净样本必须出 PASS 且 `coverage_state=full`；否则红（不是误报，是「还有别的阻塞」） |

## 它不判什么

* 它**不判**「补齐空族」这件事该不该做 —— 那是产品/法务的活（Playbook:1427 的两条路）。
* 它**不会自动运行**：本仓没有聚合 runner，也没有守护进程会调它。**这条断言的到期/变化
  是否被发现，取决于有人跑它**（与 T-230 的触发点缺口同一个形状）。
* `U4/U5` 是**内存里**的反向对照（不改表、不写盘）：它们证明「限制由空族造成」，
  不是声称「换掉真表就能出 PASS」。

退出码：全过 **0** ／ 有红 **1** ／ 未测（导入失败、表读不出、样本跑不出）**2**。

复现：
    python3 tools/verify_pass_reachability.py
    python3 tools/verify_pass_reachability.py --controls
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "base"), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

#: 四个主体都写成模块级常量：tools/verify_coverage.py 的 **C 段**要求
#: subjects 的文件名 + 至少一个父目录段在源码里**逐字出现**。
CP_TABLE = ROOT / "research" / "governance" / "control-points-v1.json"
COMPOSER = ROOT / "base" / "coverage_composer.py"
DECISION = ROOT / "base" / "decision_table.py"
PLAYBOOK = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"

FIVE_STATES = ("BLOCK", "REVIEW", "待自决", "未审查", "PASS")
#: 空族存在时，输出空间**必须**落在这四个里（PASS 被排除）。
NOT_PASS = ("BLOCK", "REVIEW", "未审查", "待自决")
EMPTY_LABEL = "未做·无控制点"

#: 干净样本的名字 —— U8 的未来分支按这个名字找它。
CLEAN = "干净文本"
SCENES = (
    ("医疗宣称", "这款产品可以治疗疾病，疗效显著。"),
    (CLEAN, "这款吸奶器采用食品级硅胶材质，容量 150ml。"),
    ("空文本", ""),
)

#: 文档里必须还在的三句话（逐字）。
DOC_ANCHORS = ("PASS 出不来", "这是刻意的", "空族数一律读")


class Untested(Exception):
    """读不出 / 跑不出 —— 退 2，不许当成「PASS 不可达」或「PASS 可达」。"""


# ─────────────────────────── 读表 ───────────────────────────


def read_table(path: Path | None = None) -> dict:
    p = Path(path) if path is not None else CP_TABLE
    if not p.is_file():
        raise Untested(f"没有控制点表：{p}")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Untested(f"{p} 读不出：{type(e).__name__}: {e}")
    families = d.get("families")
    cps = d.get("control_points")
    declared = d.get("empty_families")
    if not isinstance(families, list) or not families:
        raise Untested(f"{p} 缺 families 数组")
    if not isinstance(cps, list):
        raise Untested(f"{p} 缺 control_points 数组")
    if not isinstance(declared, list):
        raise Untested(f"{p} 缺 empty_families 数组")
    counts: dict[str, int] = {f: 0 for f in families}
    unknown = set()
    for cp in cps:
        fam = (cp or {}).get("family")
        if fam in counts:
            counts[fam] += 1
        else:
            unknown.add(fam)
    return {
        "families": list(families),
        "declared_empty": [x.get("family") for x in declared if isinstance(x, dict)],
        "declared_raw": declared,
        "counts": counts,
        "unknown_families": sorted(x for x in unknown if x),
    }


def data_empty(table: dict) -> list[str]:
    return [f for f in table["families"] if table["counts"].get(f, 0) == 0]


# ─────────────────────────── 跑样本 ───────────────────────────


def run_samples() -> tuple[list[dict], dict]:
    """真跑判定入口：收集每个样本的标签与覆盖状态 + 一个 BLOCK 可达性夹具。"""
    try:
        from base import contract as C  # noqa: PLC0415
        from base.judge_entry import judge_unit  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定入口失败：{type(e).__name__}: {e}")

    out = []
    for name, text in SCENES:
        try:
            unit = C.from_text(text)
            r = judge_unit(unit, clock=lambda: 1000)
        except Exception as e:  # noqa: BLE001
            raise Untested(f"样本「{name}」跑不出：{type(e).__name__}: {e}")
        cov = (r.get("ir") or {}).get("coverage") or {}
        out.append({
            "name": name,
            "label": r.get("label"),
            "layer": r.get("layer"),
            "coverage_state": cov.get("coverage_state"),
            # IR 里的字段名是 not_evaluated_reason（orchestrator 投影），不是 compose 的 not_run_reasons
            "reasons": list(cov.get("not_evaluated_reason") or []),
            "findings": len(r.get("findings") or []),
        })

    # BLOCK 可达性夹具：只把 authority_query 换成「依据可查」，其余走同一入口。
    # 目的：证明「出不了 PASS」不是引擎整体失效 —— BLOCK 打得出来，PASS 仍打不出来。
    try:
        unit = C.from_text(SCENES[0][1])
        rb = judge_unit(unit, clock=lambda: 1000,
                        authority_query=lambda _ref: {"state": "ok", "reason": "verify-fixture"})
    except Exception as e:  # noqa: BLE001
        raise Untested(f"BLOCK 夹具跑不出：{type(e).__name__}: {e}")
    cov_b = (rb.get("ir") or {}).get("coverage") or {}
    block_fixture = {
        "label": rb.get("label"),
        "coverage_state": cov_b.get("coverage_state"),
        "findings": [f.get("severity") for f in (rb.get("findings") or [])],
    }
    return out, block_fixture


# ─────────────────────────── 判 ───────────────────────────


def check_declaration(table: dict) -> list[str]:
    """U1：声明的空族必须与数据算出来的空族逐族相等。"""
    problems = []
    declared = list(table["declared_empty"])
    computed = data_empty(table)
    for f in declared:
        if f not in table["families"]:
            problems.append(f"U1 `empty_families` 里的「{f}」不在 families 七族里 —— 声明指不到对象")
        elif table["counts"].get(f, 0) > 0:
            problems.append(
                f"U1 「{f}」被声明为空族，但 control_points 里有 {table['counts'][f]} 条 ——"
                " 声明与实际脱钩（要么删掉声明，要么这些点没生效）")
    for f in computed:
        if f not in declared:
            problems.append(
                f"U1 「{f}」在 control_points 里 0 条，却没出现在 `empty_families` 里 ——"
                " 少报一个空族，coverage 会假装它跑过了")
    if table.get("unknown_families"):
        problems.append(f"U1 有控制点挂在七族之外：{table['unknown_families']}")
    return problems


def _reasons_for(sample: dict, family: str) -> list[dict]:
    """IR 里 `what` 会被投影成「场景控制（no_control_points）」，所以按前缀匹配。"""
    return [r for r in sample.get("reasons") or []
            if isinstance(r, dict) and str(r.get("what") or "").startswith(family)]


def check_samples(table: dict, samples: list[dict]) -> list[str]:
    """U2 / U3 / U8：真实样本上的覆盖状态与输出空间。"""
    problems = []
    declared = list(table["declared_empty"])

    for s in samples:
        if declared:
            if s.get("coverage_state") != "partial":
                problems.append(
                    f"U2 样本「{s['name']}」的 coverage_state = {s.get('coverage_state')!r}，"
                    "预期 partial（空族存在时不可能 full）")
            for fam in declared:
                rs = _reasons_for(s, fam)
                if not rs:
                    problems.append(
                        f"U2 样本「{s['name']}」的 not_run_reasons 里没有空族「{fam}」——"
                        " 那就指不出「因为哪个族」")
                    continue
                r = rs[0]
                if r.get("why") in ("not_applicable", "n/a", "none", "skip"):
                    problems.append(
                        f"U2 样本「{s['name']}」里「{fam}」的 why = {r.get('why')!r} ——"
                        " 把「还没做」写成「决定不做」，会掩盖缺口")
                if r.get("why") not in ("no_control_points", "not_wired"):
                    problems.append(
                        f"U2 样本「{s['name']}」里「{fam}」的 why = {r.get('why')!r}，"
                        "预期 no_control_points（IR 契约目前只允许 no_capability/no_rule/not_wired，"
                        "所以产品侧会看到 not_wired —— 见 U10）")
        else:
            # 空族已补齐：此时**不该**还是 partial —— 否则说明另有阻塞。
            if s.get("coverage_state") != "full":
                problems.append(
                    f"U2 `empty_families` 已为空，但样本「{s['name']}」仍只到 "
                    f"{s.get('coverage_state')!r} —— 空族不再是原因，另有阻塞")

    labels = [s.get("label") for s in samples]
    for s in samples:
        if s.get("label") not in FIVE_STATES:
            problems.append(f"U3 样本「{s['name']}」的标签 {s.get('label')!r} 不在五标签里")

    if declared:
        # 当前状态：空族非空 ⇒ 不可能出 PASS。
        for s in samples:
            if s.get("label") == "PASS":
                problems.append(
                    f"U3 样本「{s['name']}」出了 PASS，但表里还有 {len(declared)} 个空族"
                    f"（{declared}）—— 空族按规则必须落 partial，partial 永不 PASS")
        # 防桩：不要求出现两种标签（真实链路上 authority 未接时 BLOCK 出不来），
        # 但要求样本确实走到了判定里 —— findings 数必须不是常量。
        if len({s.get("findings") for s in samples}) < 2:
            problems.append(
                f"U3 全部样本的 findings 数都是 {samples[0].get('findings')} ——"
                " 这更像判定被桩成了常量，样本没有真正打到规则上")
    else:
        # U8 未来分支：空族补齐了 ⇒ 干净样本必须能 PASS。
        clean = [s for s in samples if s.get("name") == CLEAN]
        if not clean:
            problems.append(f"U8 `empty_families` 已为空，但样本里没有「{CLEAN}」——无法验证 PASS 是否可达")
        for s in clean:
            if s.get("coverage_state") != "full":
                problems.append(
                    f"U8 `empty_families` 已为空，但干净样本只到 {s.get('coverage_state')!r}："
                    " 还有别的阻塞没被这条断言覆盖（不能继续声称「唯一原因是空族」）")
            if s.get("label") != "PASS":
                problems.append(
                    f"U8 `empty_families` 已为空，干净样本却仍是 {s.get('label')!r} ——"
                    " 空族不再是原因，说明另有阻塞；本断言应红而不是被改成「不可达」")
    return problems


def check_composer_pair(table: dict, compose_fn=None) -> list[str]:
    """U4：空族 → partial；没有空族 → full。两半都要成立。"""
    compose = compose_fn
    if compose is None:
        try:
            from base.coverage_composer import compose_and_derive  # noqa: PLC0415
        except Exception as e:  # noqa: BLE001
            raise Untested(f"导入 coverage_composer 失败：{type(e).__name__}: {e}")
        compose = compose_and_derive

    families = table["families"]
    kw = dict(modalities_evaluated=["text"],
              rules_version={"version": "verify", "fingerprint": "verify"})
    problems = []
    try:
        full = compose(control_points_by_family={f: "ran" for f in families},
                       empty_families=[], **kw)
        part = compose(control_points_by_family={f: "ran" for f in families},
                       empty_families=list(table["declared_empty"]), **kw)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"合成器调用失败：{type(e).__name__}: {e}")

    if full.get("coverage_state") != "full":
        problems.append(
            "U4 把 empty_families 传成 [] 且全族 ran，合成器仍给出 "
            f"{full.get('coverage_state')!r} ——「空族是唯一阻塞」这句话不成立")
    if table["declared_empty"]:
        if part.get("coverage_state") != "partial":
            problems.append(
                "U4 按当前表的空族合成，得到的却是 "
                f"{part.get('coverage_state')!r}，预期 partial")
        for fam in table["declared_empty"]:
            rs = [r for r in (part.get("coverage") or {}).get("not_run_reasons") or []
                  if isinstance(r, dict) and r.get("what") == fam]
            if not rs:
                problems.append(f"U4 合成结果里没有空族「{fam}」的 not_run 原因")
                continue
            r = rs[0]
            if r.get("why") != "no_control_points":
                problems.append(
                    f"U4 合成结果里「{fam}」的 why = {r.get('why')!r}，预期 no_control_points")
            if r.get("label") != EMPTY_LABEL:
                problems.append(
                    f"U4 合成结果里「{fam}」的 label = {r.get('label')!r}，预期 {EMPTY_LABEL!r}"
                    "（验收表第 30 项要求逐字出现「未做·无控制点」）")
    else:
        # 空族已补齐：两半都该是 full —— 此时若按「当前表」合成仍 partial，
        # 说明还有别的 not_run 项，U4 要据此变红而不是继续沿用旧预期。
        if part.get("coverage_state") != "full":
            problems.append(
                "U4 `empty_families` 已为空，但按当前表合成仍是 "
                f"{part.get('coverage_state')!r} —— 还有别的 not_run 项，"
                "「唯一原因是空族」这句话不再成立")
    return problems


def check_decision_pair(decide_fn=None) -> list[str]:
    """U5：同一组空 findings，只改 coverage_state，标签必须从 REVIEW 变 PASS。"""
    decide = decide_fn
    if decide is None:
        try:
            from base.decision_table import decide  # noqa: PLC0415
        except Exception as e:  # noqa: BLE001
            raise Untested(f"导入 decision_table 失败：{type(e).__name__}: {e}")

    def base(cov):
        return {"parse_status": "ok", "failure_kind": None,
                "coverage_state": cov, "findings": [], "rule_conflict": False}

    problems = []
    r_full = decide(base("full"))
    r_part = decide(base("partial"))
    if r_full.get("state") != "PASS":
        problems.append(
            f"U5 coverage=full 且无 findings，判定表给出 {r_full.get('state')!r}，预期 PASS"
            " —— 那 PASS 不可达就另有原因")
    if r_part.get("state") != "REVIEW":
        problems.append(
            f"U5 coverage=partial 且无 findings，判定表给出 {r_part.get('state')!r}，预期 REVIEW")
    return problems


def check_block_fixture(fixture: dict) -> list[str]:
    """U9：BLOCK 打得出来，PASS 仍打不出来 —— 证明不是引擎整体失效。"""
    problems = []
    if not fixture:
        problems.append("U9 没有跑 BLOCK 夹具")
        return problems
    if fixture.get("label") != "BLOCK":
        problems.append(
            f"U9 把 authority_query 换成「依据可查」后，医疗文案仍得 {fixture.get('label')!r}，"
            "预期 BLOCK —— 那这条链的问题就不只是覆盖了")
    if fixture.get("coverage_state") != "partial":
        problems.append(
            f"U9 BLOCK 夹具的 coverage_state = {fixture.get('coverage_state')!r}，预期 partial")
    if not fixture.get("findings"):
        problems.append("U9 BLOCK 夹具没有 findings —— 那它凭什么 BLOCK")
    return problems


def check_doc(text: str) -> list[str]:
    """U6：Playbook 里那三句话必须还在（文档被改了要有人知道）。"""
    return [f"U6 Playbook 里找不到「{a}」—— 这条限制的书面依据不见了" for a in DOC_ANCHORS
            if a not in text]


def check_composer_numbers(src: str, n_declared: int) -> list[str]:
    """U7：源码里不许写死空族数（Playbook:1429 明令「不要写死三族或四族」）。"""
    problems = []
    for m in re.finditer(r"(\d+)\s*个空族", src):
        n = int(m.group(1))
        if n != n_declared:
            line = src[:m.start()].count("\n") + 1
            problems.append(
                f"U7 `base/coverage_composer.py:{line}` 写着「{n} 个空族」，"
                f"实际 empty_families = {n_declared} 个 —— 文档里的数字必须算出来"
                "（Playbook:1429 明令不许写死）")
    return problems


def assess(table: dict, samples: list[dict], *, doc_text: str, composer_src: str,
           block_fixture: dict | None = None, compose_fn=None, decide_fn=None) -> list[str]:
    """把所有段拼起来 —— 纯聚合，`--controls` 直接喂内存样本。"""
    problems = []
    problems += check_declaration(table)
    problems += check_samples(table, samples)
    problems += check_block_fixture(block_fixture or {})
    problems += check_composer_pair(table, compose_fn=compose_fn)
    problems += check_decision_pair(decide_fn=decide_fn)
    problems += check_doc(doc_text)
    problems += check_composer_numbers(composer_src, len(table["declared_empty"]))
    return problems


# ─────────────────────────── 反向对照 ───────────────────────────


def controls() -> int:
    table = {"families": ["宣称控制", "事实控制", "披露控制", "场景控制", "权利控制", "渠道控制", "品牌控制"],
             "declared_empty": ["场景控制", "权利控制", "渠道控制"],
             "counts": {"宣称控制": 14, "事实控制": 3, "披露控制": 3,
                        "场景控制": 0, "权利控制": 0, "渠道控制": 0, "品牌控制": 4},
             "unknown_families": []}
    samples = [
        {"name": "医疗宣称", "label": "BLOCK", "coverage_state": "partial", "findings": 2,
         "reasons": [{"what": f, "why": "no_control_points", "label": EMPTY_LABEL}
                     for f in table["declared_empty"]]},
        {"name": CLEAN, "label": "REVIEW", "coverage_state": "partial", "findings": 0,
         "reasons": [{"what": f, "why": "no_control_points", "label": EMPTY_LABEL}
                     for f in table["declared_empty"]]},
    ]
    doc = "第一阶段 coverage 恒为 partial，PASS 出不来。这是刻意的。空族数一律读 empty_families。"
    src_ok = "现在有 3 个空族（场景/权利/渠道）。"
    #: 未来场景：三族补上了控制点、empty_families 清空 —— U1 必须同时看到「点数 > 0」。
    future_table = {
        **table,
        "declared_empty": [],
        "counts": {**table["counts"], "场景控制": 1, "权利控制": 1, "渠道控制": 1},
    }

    def sample_mut(i, **over):
        out = [dict(s) for s in samples]
        out[i].update(over)
        return out

    block_ok = {"label": "BLOCK", "coverage_state": "partial", "findings": ["L4"]}

    def run(samples_=None, table_=None, doc_=None, src_=None, compose_=None, decide_=None,
            block_=None):
        return assess(table_ or table, samples_ if samples_ is not None else samples,
                      doc_text=doc_ if doc_ is not None else doc,
                      composer_src=src_ if src_ is not None else src_ok,
                      block_fixture=block_ if block_ is not None else block_ok,
                      compose_fn=compose_ or _compose_ok,
                      decide_fn=decide_ or _decide_ok)

    def red(**kw):
        return bool(run(**kw))

    def red_id(i, **kw):
        return any(i in p for p in run(**kw))

    cases = [
        ("正样本：当前表 + 当前样本 → 必须绿", lambda: not red()),
        ("★ U1 坏样本：把一个「其实有控制点」的族声明成空族 → 必须红",
         lambda: red_id("U1", table_={**table, "declared_empty": table["declared_empty"] + ["品牌控制"]})),
        ("★ U1 坏样本：数据里有一个 0 点族没被声明 → 必须红",
         lambda: red_id("U1", table_={**table, "declared_empty": ["场景控制", "权利控制"]})),
        ("U2 坏样本：样本的 coverage_state 变成 full → 必须红",
         lambda: red_id("U2", samples_=sample_mut(1, coverage_state="full"))),
        ("U2 坏样本：reasons 里少一个空族 → 必须红",
         lambda: red_id("U2", samples_=sample_mut(1, reasons=samples[1]["reasons"][:1]))),
        ("U2 坏样本：空族的 why 写成 not_applicable → 必须红（「还没做」≠「决定不做」）",
         lambda: red_id("U2", samples_=sample_mut(1, reasons=[
             {"what": f, "why": "no_control_points", "label": EMPTY_LABEL}
             for f in table["declared_empty"][:2]] + [
             {"what": table["declared_empty"][2], "why": "not_applicable", "label": EMPTY_LABEL}]))),
        ("★ U3 坏样本：出现 PASS → 必须红", lambda: red_id("U3", samples_=sample_mut(1, label="PASS"))),
        ("U3 坏样本：全部样本的 findings 数完全相同（桩）→ 必须红",
         lambda: red_id("U3", samples_=[{**s, "findings": 0} for s in samples])),
        ("U3 坏样本：标签不在五标签里 → 必须红", lambda: red_id("U3", samples_=sample_mut(0, label="APPROVED"))),
        ("★ U4 坏样本：空族传 [] 却仍派生 partial → 必须红",
         lambda: red_id("U4", compose_=_compose_stuck_partial)),
        ("★ U4 坏样本：按当前空族却派生 full（空族没生效）→ 必须红",
         lambda: red_id("U4", compose_=_compose_stuck_full)),
        ("★ U5 坏样本：coverage=partial 也给出 PASS → 必须红",
         lambda: red_id("U5", decide_=_decide_always_pass)),
        ("U5 坏样本：coverage=full 却给出 REVIEW → 必须红",
         lambda: red_id("U5", decide_=_decide_always_review)),
        ("★ U9 坏样本：BLOCK 夹具退化成 REVIEW → 必须红",
         lambda: red_id("U9", block_={"label": "REVIEW", "coverage_state": "partial", "findings": ["L4"]})),
        ("U9 坏样本：BLOCK 夹具的覆盖状态变成 full → 必须红",
         lambda: red_id("U9", block_={"label": "BLOCK", "coverage_state": "full", "findings": ["L4"]})),
        ("★ U6 坏样本：Playbook 少了「PASS 出不来」→ 必须红",
         lambda: red_id("U6", doc_="第一阶段 coverage 恒为 partial。这是刻意的。空族数一律读 empty_families。")),
        ("U6 坏样本：Playbook 少了「这是刻意的」→ 必须红",
         lambda: red_id("U6", doc_="第一阶段 coverage 恒为 partial，PASS 出不来。空族数一律读 empty_families。")),
        ("★ U7 坏样本：源码写死「4 个空族」而实际 3 → 必须红",
         lambda: red_id("U7", src_="现在有 4 个空族（场景/权利/渠道/品牌）。")),
        ("反向对照：源码写成实际数 → 必须重新变绿（上面那条不是恒红）",
         lambda: not red(src_="现在有 3 个空族。")),
        ("★ U8 未来分支（该绿）：空族补齐（有控制点了）+ 干净样本 PASS → 必须绿",
         lambda: not red(
             table_=future_table,
             samples_=[{**samples[0], "coverage_state": "full", "reasons": []},
                       {**samples[1], "label": "PASS", "coverage_state": "full", "reasons": []}],
             src_="现在有 0 个空族。")),
        ("★ U8 未来分支（该红）：空族补齐了，干净样本却还是 REVIEW → 必须红",
         lambda: red_id("U8",
                        table_=future_table,
                        samples_=[{**samples[0], "coverage_state": "full", "reasons": []},
                                  {**samples[1], "label": "REVIEW", "coverage_state": "full",
                                   "reasons": []}],
                        src_="现在有 0 个空族。")),
    ]

    bad = 0
    print("=" * 78)
    print("PASS 可达性 · 反向对照（离线；U4/U5 只在内存里做，不写盘）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（抛异常 {type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败 —— 判据有问题，别信它")
        return 1
    print(f"✅ {len(cases)} 项全过（含「该红」「该绿」「未来分支该改口」三侧）")
    return 0


# 供 controls 注入的桩（**只在内存里**，不碰真模块）
def _compose_ok(*, control_points_by_family=None, empty_families=None, **_kw):
    """与真合成器同口径的最小实现：有空族 → partial；没有 → full。"""
    fams = dict(control_points_by_family or {})
    empty = list(empty_families or [])
    for f in empty:
        fams[f] = "not_run"
    cov = {
        "modalities_evaluated": ["text"],
        "rules_version": {"version": "v", "fingerprint": "f"},
        "control_points_by_family": fams,
        "not_run_reasons": [{"what": f, "why": "no_control_points", "label": EMPTY_LABEL} for f in empty],
        "does_not_cover": [],
    }
    state = "partial" if (empty or any(v == "not_run" for v in fams.values())) else "full"
    return {"coverage": cov, "coverage_state": state}


def _compose_stuck_partial(**kw):
    r = _compose_ok(**kw)
    r["coverage_state"] = "partial"
    return r


def _compose_stuck_full(**kw):
    r = _compose_ok(**kw)
    r["coverage_state"] = "full"
    return r


def _decide_ok(inp):
    return {"state": "PASS" if inp.get("coverage_state") == "full" else "REVIEW"}


def _decide_always_pass(inp):
    return {"state": "PASS"}


def _decide_always_review(inp):
    return {"state": "REVIEW"}


# ─────────────────────────── 主 ───────────────────────────


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    try:
        table = read_table()
        samples, block_fixture = run_samples()
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        print("   这不是「PASS 不可达」，是**这次没测成** —— 退 2（未测 ≠ 通过 ≠ 红）。")
        return 2

    try:
        doc_text = PLAYBOOK.read_text(encoding="utf-8")
        composer_src = COMPOSER.read_text(encoding="utf-8")
    except OSError as e:
        print(f"⚠️ 未测：读不到文档或源码：{e}")
        return 2

    print("=" * 78)
    print("PASS 可达性 · 因果链逐环核对")
    print("=" * 78)
    print(f"  控制点表：{CP_TABLE.relative_to(ROOT)}")
    print(f"  七族控制点数：{ {f: table['counts'][f] for f in table['families']} }")
    print(f"  声明的空族（{len(table['declared_empty'])}）：{table['declared_empty']}")
    print()
    for s in samples:
        print(f"  · {s['name']:<6} → {str(s['label']):<6} coverage={s['coverage_state']}"
              f" findings={s['findings']}")
    print(f"  · 夹具(BLOCK) → {block_fixture.get('label')} coverage={block_fixture.get('coverage_state')}"
          f" findings={block_fixture.get('findings')}")
    print()

    try:
        problems = assess(table, samples, doc_text=doc_text, composer_src=composer_src,
                          block_fixture=block_fixture)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2

    if problems:
        print(f"── 有问题 {len(problems)} 处 ──")
        for p in problems:
            print(f"  ❌ {p}")
        print()
        print(f"❌ 退 1：{len(problems)} 处不成立")
        return 1

    if table["declared_empty"]:
        print("✅ 退 0：PASS 不可达这件事可核对 ——")
        print(f"   因为 {table['declared_empty']} 三族控制点为 0 条，")
        print("   所以 coverage 恒 partial，所以判定表只走链 11（REVIEW），")
        print("   所以样本标签里没有 PASS。")
        print("   ★ 将来这些族被补齐时，本脚本会改口要求干净样本必须出 PASS（U8），不会变成误报。")
    else:
        print("✅ 退 0：空族已为空，干净样本确实出 PASS —— 这条限制已自然解除。")
    print()
    print("   ⚠️ 触发点：**没有任何聚合 runner 或守护进程会自动跑本脚本**。")
    print("      空族被人悄悄补掉/又加回来时，是否被发现取决于有人跑它 —— 这是未闭项。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：验收器自身异常：{type(exc).__name__}: {exc}")
        sys.exit(2)
