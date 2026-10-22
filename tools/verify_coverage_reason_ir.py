#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_coverage_reason_ir.py —— 空族的「未做·无控制点」能不能从 IR 读到

## 为什么要有这个文件（T-120b）

`compose()` 那一层一直是对的：空族会补一条
`{"what": "场景控制", "why": "no_control_points", "label": "未做·无控制点"}`。
**问题全在它下游**：走到 IR 时三件事同时发生 ——

| # | 事实 | 位置 |
|---|---|---|
| 1 | `why` 被降级成 `not_wired` | `base/orchestrator.py` 的 `VALID_REASON` 只认三个值 |
| 2 | `label` 被整个丢掉 | `contracts/review-ir-v1.schema.json` 的 items 是 additionalProperties:false 且没有 label |
| 3 | 界面把 `not_wired` 说成「没接线」 | `web/src/pages/CaseDetailPage.tsx` 的 WHY_TEXT |

于是**产品对用户说错了话**：空族的真实含义是「这一族还没有控制点」，
界面说的是「接线没做」—— 两个不同的缺口，下一步动作也不同。
而验收表 #73 ② 要求「覆盖证明的『未跑的为什么』写着「未做·无控制点」」，
`tests/acceptance/verifier_map.json` 却把 #72/#73 指向只测 `compose()` 的
`verify_coverage_composer.py` —— 它从不走 IR，于是那一条在链路上不成立、却记着 passed。

## 断言

| 段 | 断言 |
|---|---|
| R1 | **契约**：`review-ir-v1.schema.json` 的 `not_evaluated_reason.items.properties.why.enum` 含 `no_control_points`，且 items 允许 `label` |
| R2 | **真实入口**：`judge_unit()` 读回 IR 后，每个空族逐族出现，`why == "no_control_points"`，`label == "未做·无控制点"` |
| R3 | **IR 符合分段契约**：每条 reason 有 what/why、why ∈ 枚举、label 是字符串、没有未知键 |
| R4 | **降级防护仍在**：未知 why（如 `something_new`）仍被降级成 `not_wired` 且原值保留在 what 里 —— 修 R2 不许把这道闸拆了 |
| R5 | **前端不再混为一谈**：`WHY_TEXT` 里有 `no_control_points` 自己的文案，且与 `not_wired` 不是同一句 |
| R6 | **映射指对了**：`verifier_map.json` 的 #72/#73 指向本文件（否则前五条白做——旧映射会继续指着只测 compose 的脚本） |

## 反向对照（`--controls`）

行为级，不是「源码里出现某个字」：

* 把 `base.orchestrator.VALID_REASON` 里的 `no_control_points` **临时拿掉**（内存里改，finally 复原）
  → 真实入口读回的 IR 必须退化，且 R2 的判据必须红；
* 拿掉 schema 的枚举值 / 拿掉 label 属性 → R1 必须红；
* 未知 why 的降级被删掉（不再降级）→ R4 必须红；
* 前端两个原因共用一句 → R5 必须红；
* 映射改回 `verify_coverage_composer.py` → R6 必须红；
* 台账/契约/映射任一读不出 → **退 2（未测）**，不是绿。

退出码：全过 **0** ／ 有红 **1** ／ 读不出或导入失败 **2**。

复现：
    python3 tools/verify_coverage_reason_ir.py
    python3 tools/verify_coverage_reason_ir.py --controls
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

#: 五个主体写成模块级常量：tools/verify_coverage.py 的 **C 段**要求
#: subjects 的文件名 + 至少一个父目录段在源码里**逐字出现**。
CP_TABLE = ROOT / "research" / "governance" / "control-points-v1.json"
IR_SCHEMA = ROOT / "contracts" / "review-ir-v1.schema.json"
CASE_PAGE = ROOT / "web" / "src" / "pages" / "CaseDetailPage.tsx"
VERIFIER_MAP = ROOT / "tests" / "acceptance" / "verifier_map.json"
ORCHESTRATOR = ROOT / "base" / "orchestrator.py"

EMPTY_LABEL = "未做·无控制点"
EMPTY_WHY = "no_control_points"
CLEAN_TEXT = "这款吸奶器采用食品级硅胶材质，容量 150ml。"
SELF_NAME = "verify_coverage_reason_ir.py"


class Untested(Exception):
    """读不出 / 导入失败 —— 退 2，不许当成绿。"""


# ─────────────────────────── 读 ───────────────────────────


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise Untested(f"没有这个文件：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Untested(f"{path} 读不出：{type(e).__name__}: {e}")


def empty_families() -> list[str]:
    d = read_json(CP_TABLE)
    fams = d.get("empty_families")
    if not isinstance(fams, list):
        raise Untested(f"{CP_TABLE} 缺 empty_families 数组")
    return [x.get("family") for x in fams if isinstance(x, dict) and x.get("family")]


def run_entry() -> dict:
    """走真实入口，读回 IR 的 coverage 段与外部标签。"""
    try:
        from base import contract as C  # noqa: PLC0415
        from base.judge_entry import judge_unit  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定入口失败：{type(e).__name__}: {e}")
    try:
        r = judge_unit(C.from_text(CLEAN_TEXT), clock=lambda: 1000)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"真实入口跑不出：{type(e).__name__}: {e}")
    cov = (r.get("ir") or {}).get("coverage")
    if not isinstance(cov, dict):
        raise Untested("IR 里没有 coverage 段")
    return {"coverage": cov, "label": r.get("label"), "layer": r.get("layer")}


def schema_slice() -> dict:
    d = read_json(IR_SCHEMA)
    try:
        return d["properties"]["coverage"]["properties"]["not_evaluated_reason"]["items"]
    except KeyError:
        raise Untested("schema 里找不到 coverage.not_evaluated_reason.items —— 契约结构变了")


def why_enum(items: dict) -> list[str]:
    return list(((items.get("properties") or {}).get("why") or {}).get("enum") or [])


def read_why_text() -> dict[str, str]:
    """从前端源码里抠出 WHY_TEXT 映射（一行一个 key: "文案"）。"""
    if not CASE_PAGE.is_file():
        raise Untested(f"没有这个文件：{CASE_PAGE}")
    src = CASE_PAGE.read_text(encoding="utf-8")
    m = re.search(r"const WHY_TEXT[^=]*=\s*\{(.*?)\};", src, re.S)
    if not m:
        raise Untested("CaseDetailPage.tsx 里找不到 WHY_TEXT 映射 —— 口径可能改了")
    out = {}
    for k, v in re.findall(r'([A-Za-z_][\w]*)\s*:\s*"([^"]*)"', m.group(1)):
        out[k] = v
    if not out:
        raise Untested("WHY_TEXT 解析不出任何键")
    return out


def map_rows() -> dict:
    d = read_json(VERIFIER_MAP)
    rows = d.get("rows")
    if not isinstance(rows, dict):
        raise Untested("verifier_map.json 的 rows 不是对象")
    return rows


# ─────────────────────────── 判 ───────────────────────────


def check_contract(items: dict) -> list[str]:
    """R1：契约必须认识 no_control_points，并允许 label。"""
    problems = []
    enum = why_enum(items)
    if EMPTY_WHY not in enum:
        problems.append(
            f"R1 `review-ir-v1.schema.json` 的 why 枚举里没有 {EMPTY_WHY!r}（读到 {enum}）——"
            " 空族的原因落不进 IR")
    if "label" not in (items.get("properties") or {}):
        problems.append(
            "R1 schema 的 not_evaluated_reason.items 不允许 `label` ——"
            f" 「{EMPTY_LABEL}」这个字面量在 IR 里存不下来")
    if items.get("additionalProperties") is not False:
        problems.append("R1 items 的 additionalProperties 不是 false —— 未知字段会静默通过")
    return problems


def check_reasons(cov: dict, families: list[str], items: dict) -> list[str]:
    """R2 + R3：真实 IR 里逐族指得出，且整段符合契约。"""
    problems = []
    reasons = cov.get("not_evaluated_reason")
    if not isinstance(reasons, list):
        problems.append("R2 IR 的 coverage.not_evaluated_reason 不是数组")
        return problems

    for fam in families:
        hits = [r for r in reasons
                if isinstance(r, dict) and str(r.get("what") or "").startswith(fam)]
        if not hits:
            problems.append(f"R2 空族「{fam}」在 IR 的 not_evaluated_reason 里根本没出现")
            continue
        r = hits[0]
        if r.get("why") != EMPTY_WHY:
            problems.append(
                f"R2 空族「{fam}」在 IR 里的 why = {r.get('why')!r}，预期 {EMPTY_WHY!r}"
                " —— 产品会把「这一族还没有控制点」读成别的缺口")
        if r.get("label") != EMPTY_LABEL:
            problems.append(
                f"R2 空族「{fam}」在 IR 里的 label = {r.get('label')!r}，预期 {EMPTY_LABEL!r}")

    # R3：按 schema 分段校验（不引第三方库，只验这一段的三条硬约束）
    enum = why_enum(items)
    props = set((items.get("properties") or {}))
    required = set(items.get("required") or [])
    for i, r in enumerate(reasons):
        if not isinstance(r, dict):
            problems.append(f"R3 not_evaluated_reason[{i}] 不是对象")
            continue
        for k in required:
            if not r.get(k):
                problems.append(f"R3 not_evaluated_reason[{i}] 缺必填 `{k}`")
        if r.get("why") not in enum:
            problems.append(
                f"R3 not_evaluated_reason[{i}].why = {r.get('why')!r} 不在契约枚举 {enum} 里")
        if "label" in r and not (isinstance(r["label"], str) and r["label"].strip()):
            problems.append(f"R3 not_evaluated_reason[{i}].label 不是非空字符串")
        extra = set(r) - props
        if extra and items.get("additionalProperties") is False:
            problems.append(
                f"R3 not_evaluated_reason[{i}] 带了契约不允许的键 {sorted(extra)} ——"
                " 上线时会被 schema 拒")
    return problems


def check_decision(entry: dict, families: list[str]) -> list[str]:
    """R7：这条空族内容必须落 REVIEW（不是未审查），且不产出 PASS（验收表 #73 ①③）。"""
    problems = []
    label = entry.get("label")
    if families:
        if label != "REVIEW":
            problems.append(
                f"R7 空族仍在（{len(families)} 族），干净内容却落 {label!r}，预期 REVIEW"
                "（链 11：coverage=partial → REVIEW，不是未审查）")
    else:
        if label != "PASS":
            problems.append(
                f"R7 空族已补齐，干净内容仍是 {label!r}，预期 PASS —— 另有阻塞")
    return problems


def check_downgrade_guard(orchestrator_mod) -> list[str]:
    """R4：未知 why 的降级闸必须还在（修 R2 不许把它拆了）。"""
    problems = []
    view = getattr(orchestrator_mod, "_coverage_ir", None)
    if view is None:
        problems.append("R4 base/orchestrator.py 里找不到 `_coverage_ir` —— 口径变了")
        return problems
    fake = {"coverage_state": "partial", "modalities_evaluated": ["free_text"],
            "rules_version": "rs", "control_points_applied": [],
            "not_evaluated_reason": [{"what": "某个没登记的原因", "why": "something_new"}]}
    try:
        out = view(fake, {"control_points": [], "rule_snapshot": "rs"}, {})
    except Exception as e:  # noqa: BLE001
        problems.append(f"R4 投影函数对未知 why 抛了异常：{type(e).__name__}: {e}")
        return problems
    rs = out.get("not_evaluated_reason") or []
    if not rs:
        problems.append("R4 未知 why 被整个丢掉 —— 那就没有「未跑的为什么」了")
        return problems
    r = rs[0]
    if r.get("why") != "not_wired":
        problems.append(
            f"R4 未知 why 没有被降级，读到的 why = {r.get('why')!r}；"
            " 降级闸是防「没人认识的写法混进 IR」的，不能拆")
    if "something_new" not in str(r.get("what") or ""):
        problems.append("R4 降级时把原始 why 丢了 —— 那就查不出是谁写的")
    return problems


def check_frontend(text: dict[str, str]) -> list[str]:
    """R5：前端必须给空族一句自己的文案。"""
    problems = []
    if EMPTY_WHY not in text:
        return [f"R5 WHY_TEXT 里没有 {EMPTY_WHY} 这个键 —— 界面会直接显示原始串"
                f"（或退化成 {EMPTY_WHY!r} 的英文），且与「没接线」混为一谈"]
    if EMPTY_WHY in text and "not_wired" in text and text[EMPTY_WHY] == text["not_wired"]:
        problems.append("R5 空族与 not_wired 用了同一句文案 —— 两个不同的缺口又被混成一件事")
    if EMPTY_LABEL.split("·")[0] not in text.get(EMPTY_WHY, "") and "无控制点" not in text.get(EMPTY_WHY, ""):
        problems.append(
            f"R5 空族文案 {text.get(EMPTY_WHY)!r} 里看不出「无控制点」——"
            " 用户读到的是「没接线」的另一件事故")
    return problems


def check_mapping(rows: dict) -> list[str]:
    """R6：#72/#73 必须指到本文件。"""
    problems = []
    for tid in ("72", "73"):
        row = rows.get(tid)
        if not isinstance(row, dict):
            problems.append(f"R6 verifier_map.json 里没有 #{tid}")
            continue
        cmd = str(row.get("command") or "")
        if SELF_NAME not in cmd:
            problems.append(
                f"R6 #{tid} 的命令指向 {cmd!r}，不是 {SELF_NAME} ——"
                " 旧映射会继续指着只测 compose 的脚本，验收表就会继续报 passed")
    return problems


def assess(*, items: dict, entry: dict, families: list[str],
           orchestrator_mod, frontend: dict[str, str], rows: dict) -> list[str]:
    return (check_contract(items)
            + check_reasons(entry.get("coverage") or {}, families, items)
            + check_decision(entry, families)
            + check_downgrade_guard(orchestrator_mod)
            + check_frontend(frontend)
            + check_mapping(rows))


# ─────────────────────────── 反向对照 ───────────────────────────


def controls() -> int:
    items_ok = {"type": "object", "additionalProperties": False,
                "required": ["what", "why"],
                "properties": {"what": {"type": "string"},
                               "why": {"type": "string",
                                       "enum": ["no_capability", "no_rule", "not_wired", "no_control_points"]},
                               "label": {"type": "string"}}}
    fams = ["场景控制", "权利控制", "渠道控制"]
    cov_ok = {"not_evaluated_reason": [
        {"what": f, "why": EMPTY_WHY, "label": EMPTY_LABEL} for f in fams]}
    ui_ok = {"not_wired": "未接线（根本没跑，不是跑了没问题）",
             "no_rule": "无适用规则", "no_capability": "无该能力",
             EMPTY_WHY: "未做·无控制点（这一族还没有定控制点）"}
    map_ok = {"72": {"command": f"python3 tools/{SELF_NAME}"},
              "73": {"command": f"python3 tools/{SELF_NAME}"}}

    class FakeOrch:
        @staticmethod
        def _coverage_ir(value, request, unit):
            out = []
            for r in value.get("not_evaluated_reason") or []:
                why = r.get("why")
                if why in ("no_capability", "no_rule", "not_wired", EMPTY_WHY):
                    out.append(dict(r))
                else:
                    out.append({"what": "%s（%s）" % (r.get("what"), why), "why": "not_wired"})
            return {"not_evaluated_reason": out}

    class NoGuardOrch:
        @staticmethod
        def _coverage_ir(value, request, unit):
            return {"not_evaluated_reason": [dict(r) for r in value.get("not_evaluated_reason") or []]}

    def run(items_=None, cov_=None, entry_=None, fams_=None, orch_=None, ui_=None, rows_=None):
        entry = entry_ if entry_ is not None else {
            "coverage": cov_ or cov_ok, "label": "REVIEW"}
        return assess(items=items_ or items_ok, entry=entry, families=fams_ or fams,
                      orchestrator_mod=orch_ or FakeOrch,
                      frontend=ui_ if ui_ is not None else ui_ok,
                      rows=rows_ or map_ok)

    def red(i, **kw):
        return any(i in p for p in run(**kw))

    # 真·行为级：把 VALID_REASON 里的 no_control_points 临时拿掉，走真实入口。
    def live_ir_without_reason():
        import base.orchestrator as ORCH  # noqa: PLC0415
        original = getattr(ORCH, "VALID_REASON")
        try:
            ORCH.VALID_REASON = tuple(x for x in original if x != EMPTY_WHY)
            return run_entry()
        finally:
            ORCH.VALID_REASON = original

    cases = [
        ("正样本：契约 + 真实 IR + 前端 + 映射都齐 → 必须绿", lambda: not run()),
        ("★ R1 坏样本：schema 的 why 枚举删掉 no_control_points → 必须红",
         lambda: red("R1", items_={**items_ok, "properties": {
             **items_ok["properties"],
             "why": {"type": "string", "enum": ["no_capability", "no_rule", "not_wired"]}}})),
        ("★ R1 坏样本：schema 不再允许 label → 必须红",
         lambda: red("R1", items_={**items_ok, "properties": {
             "what": {"type": "string"},
             "why": {"type": "string", "enum": ["no_capability", "no_rule", "not_wired", EMPTY_WHY]}}})),
        ("★ R2 坏样本：IR 里 why 退化成 not_wired → 必须红",
         lambda: red("R2", cov_={"not_evaluated_reason": [
             {"what": f, "why": "not_wired"} for f in fams]})),
        ("R2 坏样本：IR 里 label 丢了 → 必须红",
         lambda: red("R2", cov_={"not_evaluated_reason": [
             {"what": f, "why": EMPTY_WHY} for f in fams]})),
        ("R2 坏样本：某个空族在 IR 里整条消失 → 必须红",
         lambda: red("R2", cov_={"not_evaluated_reason": [
             {"what": fams[0], "why": EMPTY_WHY, "label": EMPTY_LABEL}]})),
        ("★ R3 坏样本：IR 带了契约不允许的键 → 必须红",
         lambda: red("R3", cov_={"not_evaluated_reason": [
             {"what": fams[0], "why": EMPTY_WHY, "label": EMPTY_LABEL, "extra": 1}]})),
        ("R3 坏样本：why 不在枚举里 → 必须红",
         lambda: red("R3", cov_={"not_evaluated_reason": [
             {"what": fams[0], "why": "whatever", "label": EMPTY_LABEL}]})),
        ("★ R4 坏样本：把未知 why 的降级闸拆掉 → 必须红",
         lambda: red("R4", orch_=NoGuardOrch)),
        ("★ R7 坏样本：空族内容落「未审查」而不是 REVIEW → 必须红",
         lambda: red("R7", entry_={"coverage": cov_ok, "label": "未审查"})),
        ("R7 坏样本：空族内容出了 PASS → 必须红",
         lambda: red("R7", entry_={"coverage": cov_ok, "label": "PASS"})),
        ("★ R5 坏样本：空族没有自己的文案 → 必须红",
         lambda: red("R5", ui_={"not_wired": "未接线", "no_rule": "无适用规则",
                                "no_capability": "无该能力"})),
        ("★ R5 坏样本：空族与 not_wired 共用一句 → 必须红",
         lambda: red("R5", ui_={**ui_ok, EMPTY_WHY: "未接线（根本没跑，不是跑了没问题）"})),
        ("★ R6 坏样本：映射改回只测 compose 的脚本 → 必须红",
         lambda: red("R6", rows_={"72": {"command": "python3 tools/verify_coverage_composer.py"},
                                  "73": {"command": "python3 tools/verify_coverage_composer.py"}})),
        ("★ 行为级反向对照：把 VALID_REASON 里的 no_control_points 拿掉 → 真实 IR 必须退化且判据红",
         lambda: any("R2" in p for p in
                     check_reasons(live_ir_without_reason()["coverage"], fams, items_ok))),
        ("反向对照：复原 VALID_REASON 后，真实 IR 必须重新变绿（上面那条不是恒红）",
         lambda: not check_reasons(run_entry()["coverage"], fams, items_ok)),
    ]

    bad = 0
    print("=" * 78)
    print("空族原因能否从 IR 读到 · 反向对照（含一条真·行为级：改 VALID_REASON 后走真实入口）")
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
    print(f"✅ {len(cases)} 项全过（该红、该绿、以及真入口退化三条都在）")
    return 0


# ─────────────────────────── 主 ───────────────────────────


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    try:
        items = schema_slice()
        fams = empty_families()
        entry = run_entry()
        frontend = read_why_text()
        rows = map_rows()
        import base.orchestrator as ORCH  # noqa: PLC0415
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        print("   这不是「读得到」，是**这次没读成** —— 退 2（未测 ≠ 通过 ≠ 红）。")
        return 2

    problems = assess(items=items, entry=entry, families=fams, orchestrator_mod=ORCH,
                      frontend=frontend, rows=rows)

    print("=" * 78)
    print("空族原因在链路里读不读得到")
    print("=" * 78)
    print(f"  空族（{len(fams)}）：{fams}   · 干净内容判定 → {entry.get('label')}")
    for r in entry["coverage"].get("not_evaluated_reason") or []:
        print(f"    · {r.get('what')}  why={r.get('why')}  label={r.get('label')!r}")
    print(f"  前端 WHY_TEXT[{EMPTY_WHY}] = {frontend.get(EMPTY_WHY)!r}")
    print(f"  verifier_map #72/#73 → {rows.get('72', {}).get('command')}")
    print()
    if problems:
        print(f"── 有问题 {len(problems)} 处 ──")
        for p in problems:
            print(f"  ❌ {p}")
        print()
        print(f"❌ 退 1：{len(problems)} 处不成立")
        return 1
    print(f"✅ 退 0：{len(fams)} 个空族在 IR 里逐族读得到 why={EMPTY_WHY} / label={EMPTY_LABEL}；")
    print("   界面不再把它说成「没接线」；#72/#73 的映射指向本文件。")
    print()
    print("   ⚠️ 这句话**不**等于「覆盖证明完整」：empty_families 仍是"
          f" {len(fams)} 族、coverage 仍恒 partial —— 那是 T-120 那条，不在本票里。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：验收器自身异常：{type(exc).__name__}: {exc}")
        sys.exit(2)
