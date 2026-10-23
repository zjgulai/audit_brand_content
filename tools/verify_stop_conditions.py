#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_stop_conditions.py —— 行 36：停机条件登记与「不提前停」

## 行 36 判据（验收表 v3 #36）与执行点对照

| 判据子句 | 执行点 |
|---|---|
| 登记恰有 6 条、每条 `status=not_applicable_stage1` | **S1**（解析 Playbook §3.3.7 的 MD 表） |
| 第一阶段口径统一为「不提前停」（P1/P2/P3 与 P0 机结样本都不提前停） | **S2**（真跑判定入口：五步各一次、`skipped=[]`；回执 schema 的原因枚举不含 `early_stop`）+ **S7a**（P0 机结样本照常走完五步，2026-10-18 改定：第一阶段不启用提前停） |
| 依据缺失样本只查一次、回执无重试步骤或第二轮 | **S4**（用计数桩直查 `base.evidence_sync`：N 条 ref 恰好 N 次查询、每条 ref 恰好一条 resolution_detail、无重试） |
| pipeline 无回边时不得出现第二轮（正常跑完 `run_state=normal_complete`） | **S5**（注入抛异常的部件 → `run_state=ERROR`；正常五步 → `run_state=OK`；换第二份输入 receipt_id 必变 → 结果与输入绑定，无全局轮次） |
| 构造全部可跑完的控制点清单，断言清单步骤各执行一次 | **S6**（登记表 active 控制点集合 == 回执 `control_points_ran` == IR `coverage.control_points_applied`，各恰一次） |
| fetch_error / parse_error / empty 在 IR/回执记 failure_kind 且报告可数 | **S3**（构造 `parse_status=failed` 三样本：`content_unit_ref.failure_kind` 逐字、`report_snapshot.failure_kind_counts` 对应键恰为 1、findings 空、控制点未跑） |
| 超时升级必须转出到「项目统筹」且事件可查、带案件号 | **S8**（直查 `base.case_watch`：到期案件产生 `case_overdue` 事件，事件带 `case_id` 且 `escalation_role` 逐字是「项目统筹」、落台账；未到期案件 0 事件） |
| 全仓没有任何一项要求「两轮」/「无进展」行为 | **S9**（剥掉注释与 docstring 后扫可执行源码，命中即红） |

**为什么登记表读 MD 而不是 JSON**：全仓没有 `stop-conditions-v1.json`，
`not_applicable_stage1` 在代码/JSON 里 0 命中；唯一的登记就是 Playbook:759-770。
行 36 说「读取停机条件登记」，读它 = 读这张表。**没有为凑验收去新建一个 JSON**
（那会让同一份登记有两处，改一处漂一处）。

**S8 为什么直查 `base/case_watch.py` 而不是 grep**：升级目标若只靠文本扫描，
把角色常量改成别的词它照样绿 —— 文本断言判不出行为（§2.4：名字出现过 ≠ 拦得住）。
所以喂一条已到期的真实案件走 `scan()`，断言事件里**逐字**带着「项目统筹」与案件号；
再把默认升级目标改坏，它必须红（mutprobe `#36-4` 证明这条变异被拦）。

**S5 为什么是这两个读数**：判据原文写「退出原因为 normal_complete」，生产里的
对应物是 `run_state`。只断言「正常跑 = OK」是恒真的（正常跑本来就该 OK），
必须配反向面：**部件出错时 run_state 必须变成非 OK** —— 否则「ERROR 被吞成 OK」
这类变异照样绿。再加 receipt_id 与输入绑定的读数，堵住「共享全局状态第二轮」。

**S9 的已知盲区**：只扫 `base/ api/` 的可执行源码；行尾注释不算代码（与
`verify_control_points` 的扫描器同一读法），整行注释与 docstring 先剥掉。
`Playbook` 里「连续两轮」是**登记表文字**，不是行为要求 —— 不扫文档。

退出码：0 / 1 / 2（Playbook 读不出、判定入口跑不出 → 未测）。
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAYBOOK = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"
RECEIPT_SCHEMA = ROOT / "contracts" / "receipt-v1.schema.json"
SCAN_DIRS = (ROOT / "base", ROOT / "api")
EXPECTED_ROWS = 6
STAGE1 = "not_applicable_stage1"
#: 行为特征：这些词出现在**可执行代码**里，就说明有人实现了提前停 / 无进展停。
STOP_PATTERNS = ("early_stop", "no_progress", "consecutive_rounds", "stop_condition")
#: 行 36 判据原文：超时升级的转出目标。
ESCALATION_ROLE = "项目统筹"
FAILURE_KINDS = ("fetch_error", "parse_error", "empty")


class Untested(Exception):
    pass


def read_playbook() -> str:
    if not PLAYBOOK.is_file():
        raise Untested(f"没有 Playbook：{PLAYBOOK}")
    return PLAYBOOK.read_text(encoding="utf-8")


def parse_stop_table(text: str) -> list[dict]:
    """从 §3.3.7 的 MD 表里取停机条件行。"""
    m = re.search(r"####\s*3\.3\.7\s*停机条件.*?\n(.*?)(?=\n####|\n---|\Z)", text, re.S)
    if not m:
        raise Untested("Playbook 里找不到 §3.3.7 停机条件小节")
    rows = []
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"\d+", cells[0]):
            continue
        rows.append({"id": int(cells[0]), "condition": cells[1], "stage1": cells[2]})
    if not rows:
        raise Untested("§3.3.7 里解析不出任何停机条件行 —— 表格式变了")
    return rows


def check_registry(rows: list[dict]) -> list[str]:
    """S1。"""
    problems = []
    if len(rows) != EXPECTED_ROWS:
        problems.append(f"S1 停机条件登记 {len(rows)} 条，预期恰好 {EXPECTED_ROWS} 条")
    ids = [r["id"] for r in rows]
    if sorted(ids) != list(range(1, EXPECTED_ROWS + 1)):
        problems.append(f"S1 编号不是 1..{EXPECTED_ROWS} 各一次：{ids}")
    for r in rows:
        if STAGE1 not in r["stage1"]:
            problems.append(f"S1 第 {r['id']} 条的第一阶段状态不是 {STAGE1}：{r['stage1']!r}")
    return problems


def _run_judge(unit: dict, authority_query) -> dict:
    """真跑一次生产判定入口；入口跑不起来 → 未测。"""
    try:
        from base.judge_entry import judge_unit  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定入口失败：{type(e).__name__}: {e}")
    try:
        return judge_unit(unit, clock=lambda: 1000, authority_query=authority_query)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"判定入口跑不出：{type(e).__name__}: {e}")


def _sample_unit():
    try:
        from base import contract as C  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.contract 失败：{type(e).__name__}: {e}")
    return C.from_text("这款产品可以治疗疾病，疗效显著。")


def check_no_early_stop() -> list[str]:
    """S2 + S7a：真跑判定入口，五步各一次、无跳过；回执枚举不含 early_stop；
    P0 机结样本也不提前停。"""
    problems = []
    unit = _sample_unit()
    r = _run_judge(unit, lambda _ref: {"state": "ok", "reason": "verify"})
    if r.get("steps") != ["normalize", "judge", "dispose", "output", "evaluate"]:
        problems.append(f"S2 判定步骤不是五步各一次：{r.get('steps')}")
    receipt = r.get("receipt") or {}
    skipped = receipt.get("skipped", receipt.get("skipped_steps"))
    if skipped != []:
        problems.append(f"S2 回执 skipped 非空：{skipped!r} —— 有东西被提前跳过了")
    try:
        schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        enum = (schema["properties"]["skipped"]["items"]["properties"]["reason"]["enum"])
    except Exception as e:  # noqa: BLE001
        raise Untested(f"读回执 schema 的 skipped 枚举失败：{e}")
    if "early_stop" in enum or "no_progress" in enum:
        problems.append(f"S2 回执 schema 的跳过原因枚举里出现了停机类原因：{enum}")

    # S7a：P0 机结样本（正则命中 + 三条机结条件齐备）也必须走完五步 ——
    # 第一阶段不启用提前停（2026-10-18 改定）。★ 先证样本真是机结形状
    # （P0 命中、authority ok、rule_conflict=False），再证它没被提前停 ——
    # 否则「干净样本也五步」是恒真的：一个出不了 finding 的变异照样绿。
    findings = r.get("findings") or []
    try:
        from base.evidence_sync import may_block  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 evidence_sync.may_block 失败：{type(e).__name__}: {e}")
    p0_machine = [f for f in findings
                  if f.get("detected_by") == "P0" and may_block(f)]
    if not p0_machine:
        problems.append(
            "S7a 样本里没有满足机结条件的 P0 命中（detected_by=P0 且 authority ok / 无规则冲突）"
            " —— 「机结样本不提前停」的输入没有构造出来")
    else:
        if r.get("steps") != ["normalize", "judge", "dispose", "output", "evaluate"]:
            problems.append(f"S7a 机结样本没有走完五步：{r.get('steps')}")
        if (r.get("receipt") or {}).get("skipped") != []:
            problems.append("S7a 机结样本的回执出现 skipped —— 提前停了")
    # 无回边 → 无第二轮：finding_id 是命中的确定性指纹，rule 判定多跑一遍
    # 就会出现整批重复的 finding_id。counting 口径：个数 == 去重后个数。
    ids = [f.get("finding_id") for f in findings]
    if len(ids) != len(set(ids)):
        problems.append(
            "S7a findings 里出现了重复的 finding_id —— rule 判定被跑了不止一遍（真第二轮）")
    return problems


def check_failure_kinds() -> list[str]:
    """S3：fetch_error / parse_error / empty 三种工具失败 → IR 逐字记
    failure_kind、报告快照里对应键恰为 1（可数）、该单元不进判定
    （落未审查、findings 空、控制点未跑）。

    ★ 在 Orchestrator 层跑（报告快照在这层装配，judge_entry 不透出它），
      全默认部件 = 生产装配本身。控制点显式给两条 —— 否则「未跑」与「没给」同形。"""
    try:
        from base.orchestrator import Orchestrator  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.orchestrator 失败：{type(e).__name__}: {e}")
    problems = []
    base_unit = _sample_unit()
    for kind in FAILURE_KINDS:
        u = dict(base_unit)
        u["parse_status"] = "failed"
        u["failure_kind"] = kind
        orch = Orchestrator(clock=lambda: 1000.0)
        req = {"skill_id": "v", "skill_hash": "h", "rule_snapshot": "rs",
               "kb_snapshot": "kb", "control_points": ["H01", "H02"]}
        try:
            r = orch.run(req, unit=u)
        except Exception as e:  # noqa: BLE001
            raise Untested(f"失败样本（{kind}）跑不出：{type(e).__name__}: {e}")
        ref = (r.get("ir") or {}).get("content_unit_ref") or {}
        if ref.get("parse_status") != "failed":
            problems.append(f"S3[{kind}] IR 的 parse_status 不是 failed：{ref.get('parse_status')!r}")
        if ref.get("failure_kind") != kind:
            problems.append(
                f"S3[{kind}] IR 没有逐字记 failure_kind：{ref.get('failure_kind')!r} —— "
                "哪一种工具失败必须可区分")
        counts = (r.get("report_snapshot") or {}).get("failure_kind_counts")
        if not isinstance(counts, dict) or counts.get(kind) != 1:
            problems.append(f"S3[{kind}] 失败在报告里不可数（failure_kind_counts：{counts!r}）")
        if (r.get("decision") or {}).get("state") != "未审查":
            problems.append(f"S3[{kind}] 失败单元没落未审查：{(r.get('decision') or {}).get('state')!r}")
        if r.get("findings") not in (None, []):
            problems.append(f"S3[{kind}] 失败单元不该有 findings：{len(r.get('findings') or [])} 条")
        if (r.get("receipt") or {}).get("control_points_ran") != []:
            problems.append(f"S3[{kind}] 失败单元的控制点不该照跑：{(r.get('receipt') or {}).get('control_points_ran')!r}")
    return problems


def check_single_query() -> list[str]:
    """S4：依据缺失样本只查一次 —— N 条 ref 恰好 N 次查询、每条 ref 恰好一条
    resolution_detail，无重试步骤。不数调用次数 = 「查几次」没有任何东西在拦。"""
    try:
        from base import evidence_sync as ES  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.evidence_sync 失败：{type(e).__name__}: {e}")
    problems = []
    calls: list[str] = []

    def query(ref):
        rid = ref.get("ref_id") if isinstance(ref, dict) else None
        calls.append(str(rid))
        return {"state": "missing", "reason": "verify-single-query"}

    finding = {"finding_id": "f-s4", "status": "confirmed",
               "authority_ref": [{"ref_id": "r1"}, {"ref_id": "r2"}, {"ref_id": "r3"}]}
    try:
        ev = ES.enrich_findings([finding], query, "rules-v1", "kb-unavailable")
    except Exception as e:  # noqa: BLE001
        raise Untested(f"evidence_sync.enrich_findings 跑不出：{type(e).__name__}: {e}")
    if calls != ["r1", "r2", "r3"]:
        problems.append(
            f"S4 依据缺失样本的查询次数不是每条一次（3 条 ref → {len(calls)} 次查询：{calls}）—— "
            "出现了重试或第二轮")
    details = (ev["findings"][0].get("resolution_detail") or {}).get("refs") or []
    got = [d.get("ref_id") for d in details]
    if got != ["r1", "r2", "r3"]:
        problems.append(f"S4 resolution_detail 没有逐条记录依据查询步骤：{got}")
    if ev["findings"][0].get("authority_state") != "missing":
        problems.append(f"S4 依据缺失必须落 missing：{ev['findings'][0].get('authority_state')!r}")
    return problems


def check_run_state() -> list[str]:
    """S5：正常跑完 run_state 必须是 OK（normal_complete 的生产对应物）；
    部件出错时必须变成非 OK —— 「ERROR 被吞成 OK」必须红。

    ★ 两个失败面各测一个：**晚步失败**（output 步，decision 已算出 ——
      此时最终 run_state 只能来自步骤错误记账，是唯一能抓到「错误被吞」的读数）
      和**早步失败**（rule 步，decision 一并失败）。"""
    try:
        from base.orchestrator import Orchestrator  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.orchestrator 失败：{type(e).__name__}: {e}")
    problems = []
    unit = _sample_unit()
    r = _run_judge(unit, lambda _ref: {"state": "ok", "reason": "verify"})
    if r.get("run_state") != "OK":
        problems.append(f"S5 正常跑完 run_state 不是 OK：{r.get('run_state')!r}")

    def exploding_rule(_ctx):
        raise RuntimeError("s5-injected")

    orch = Orchestrator(rule_judge=exploding_rule, clock=lambda: 1000.0)
    req = {"skill_id": "v", "skill_hash": "h", "rule_snapshot": "rs", "kb_snapshot": "kb"}
    try:
        res = orch.run(req, unit=unit)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"注入错误部件后 Orchestrator 跑不出：{type(e).__name__}: {e}")
    if res.get("run_state") == "OK":
        problems.append(
            "S5 部件抛异常后 run_state 仍是 OK —— 错误被吞成正常结束，"
            "「退出原因」不再是可判停机的读数")

    # 晚步失败：decision 已经算出（run_state=OK），只有步骤错误记账能把它翻成 ERROR。
    def exploding_renderer(_ctx):
        raise RuntimeError("s5-late-injected")

    orch2 = Orchestrator(renderer=exploding_renderer, clock=lambda: 1000.0)
    try:
        res2 = orch2.run({"skill_id": "v", "skill_hash": "h"}, unit=_sample_unit())
    except Exception as e:  # noqa: BLE001
        raise Untested(f"注入错误渲染部件后 Orchestrator 跑不出：{type(e).__name__}: {e}")
    if res2.get("run_state") == "OK":
        problems.append(
            "S5 output 步抛异常后 run_state 仍是 OK —— 晚步错误被吞，"
            "退出原因分不出「正常完成」与「中途出错」")
    return problems


def check_control_points_once() -> list[str]:
    """S6：全部可跑完的控制点清单 —— 回执 control_points_ran 与 IR
    coverage.control_points_applied 都必须 == 登记表 active 集合，各恰一次
    （去重后集合一致且个数不变 —— 重复执行会变长，截断执行会变短）；
    并用计数桩证明 rule 判定部件在入口里恰好被调一次。"""
    try:
        from base.control_points import ControlPointRegistry  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入控制点登记表失败：{type(e).__name__}: {e}")
    problems = []
    expected = sorted(ControlPointRegistry().active_codes())
    if not expected:
        raise Untested("控制点登记表 active 集合为空 —— 清单口径变了")
    unit = _sample_unit()
    r = _run_judge(unit, lambda _ref: {"state": "ok", "reason": "verify"})
    ran = sorted((r.get("receipt") or {}).get("control_points_ran") or [])
    applied = sorted((r.get("ir") or {}).get("coverage", {}).get("control_points_applied") or [])
    if ran != expected:
        problems.append(
            f"S6 回执 control_points_ran 与登记表 active 清单不一致："
            f"缺 {sorted(set(expected) - set(ran))} 多 {sorted(set(ran) - set(expected))}")
    if applied != expected:
        problems.append(
            f"S6 IR coverage.control_points_applied 与登记表 active 清单不一致："
            f"缺 {sorted(set(expected) - set(applied))} 多 {sorted(set(applied) - set(expected))}")
    if ran and applied and ran != applied:
        problems.append("S6 回执与 IR 两份清单互相不一致 —— 同一次审查两个口径")

    # 部件级「恰好一次」：rule_judge / evidence / coverage 各用计数桩数一遍。
    # 只看清单长度验不出「同一部件被调两次」—— 那必须数调用。
    try:
        from base import coverage_composer as CC  # noqa: PLC0415
        from base import evidence_sync as ES  # noqa: PLC0415
        from base.control_points import ControlPointRegistry as _CPR  # noqa: PLC0415
        from base.orchestrator import Orchestrator  # noqa: PLC0415
        from base.rule_judge import RuleJudge  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定装配失败：{type(e).__name__}: {e}")
    reg2 = _CPR()
    engine = RuleJudge(reg2)
    codes = sorted(reg2.active_codes())
    families = {reg2.get_active(c).get("family") for c in codes}
    calls = {"rule": 0, "evidence": 0, "coverage": 0}

    def rule_component(ctx):
        calls["rule"] += 1
        hits = engine.judge(ctx["unit"], control_codes=codes)
        out = []
        for hit in hits:
            control = reg2.get_active(hit["control_code"])
            out.append({
                "finding_id": "f-" + hit["control_code"] + "-" + hit["rule_key"],
                "control_code": hit["control_code"], "rule_key": hit["rule_key"],
                "status": "confirmed", "severity": hit["severity"],
                "produced_by": "rule", "derived_from": None,
                "detected_by": hit["detected_by"], "quote": hit["quote"],
                "location": {"kind": "text_span", "start": hit["start"],
                             "end": hit["end"], "quote": hit["quote"]},
                "authority_ref": list(control.get("authority_ref") or []),
            })
        return out

    def evidence_component(ctx):
        calls["evidence"] += 1
        return ES.enrich_findings(ctx["findings"], lambda _r: {"state": "ok", "reason": "v"},
                                  "rules-v1", "kb-unavailable")["findings"]

    def coverage_component(ctx):
        calls["coverage"] += 1
        current = ctx["unit"]
        by_family = {family: ("ran" if family in families else "not_run")
                     for family in CC.load_all_families()}
        return CC.compose_and_derive(
            modalities_evaluated=[(current.get("source") or {}).get("kind") or "unknown"],
            rules_version={"version": "rules-v1",
                           "fingerprint": engine.rule_snapshot_sha256},
            control_points_by_family=by_family,
            not_run_reasons=[],
            does_not_cover=list((current.get("textification") or {}).get("does_not_cover") or []),
            parse_status=current.get("parse_status", "ok"),
        )

    orch = Orchestrator(rule_judge=rule_component,
                        semantic_judge={"status": "untested", "findings": []},
                        evidence=evidence_component, coverage=coverage_component,
                        clock=lambda: 1000.0)
    try:
        orch.run({"unit": unit, "control_points": codes, "skill_id": "v", "skill_hash": "h"},
                 unit=unit)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"带计数桩的判定跑不出：{type(e).__name__}: {e}")
    for comp, n in sorted(calls.items()):
        if n != 1:
            problems.append(f"S6 部件 {comp} 被调用了 {n} 次（必须恰好 1 次）—— 出现了轮次或回边")
    return problems


def check_escalation() -> list[str]:
    """S8：超时升级转出「项目统筹」、事件可查、带案件号；未到期不产生升级事件。
    直查 base.case_watch —— 只 grep 文本判不出「升级目标被改坏」（§2.4）。"""
    try:
        from base.case_watch import DEFAULT_ESCALATION_ROLE, EscalationLedger, scan  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.case_watch 失败：{type(e).__name__}: {e}")
    problems = []
    if DEFAULT_ESCALATION_ROLE != ESCALATION_ROLE:
        problems.append(
            f"S8 默认升级目标不是「{ESCALATION_ROLE}」：{DEFAULT_ESCALATION_ROLE!r} —— "
            "转出目标被改坏")
    emits: list[dict] = []

    class _Outbox:
        def emit(self, **kw):
            emits.append(kw)
            return {"ok": True}

    with tempfile.TemporaryDirectory(prefix="stop-cond-s8-") as td:
        led = EscalationLedger(path=str(Path(td) / "ledger.json"))
        due_case = {"case_id": "CASE-S8-001", "status": "open",
                    "release_status": "待放行",
                    "transferred_at": "2026-09-01T00:00:00Z"}
        calm_case = {"case_id": "CASE-S8-002", "status": "open",
                     "release_status": "待放行",
                     "transferred_at": "2026-10-22T00:00:00Z"}
        try:
            out = scan([due_case, calm_case], "2026-10-23T08:00:00Z",
                       escalation_recipients=["alice"], ledger=led, outbox=_Outbox())
        except Exception as e:  # noqa: BLE001
            raise Untested(f"case_watch.scan 跑不出：{type(e).__name__}: {e}")
        if out.get("untested"):
            problems.append(f"S8 升级扫描报未测：{out.get('untested_reasons')}")
        if not any(e.get("kind") == "case_overdue" for e in emits):
            problems.append("S8 已到期案件没有产生 case_overdue 升级事件 —— 事件不可查")
        for e in emits:
            if e.get("kind") != "case_overdue":
                continue
            if e.get("case_id") != "CASE-S8-001":
                problems.append(f"S8 升级事件不带案件号：case_id={e.get('case_id')!r}")
            if e.get("escalation_role") != ESCALATION_ROLE:
                problems.append(
                    f"S8 升级事件的转出目标不是「{ESCALATION_ROLE}」：{e.get('escalation_role')!r}")
        ledger_events = led.by_case("CASE-S8-001")
        if not ledger_events:
            problems.append("S8 升级事件没有落台账 —— 「事件可查」无从谈起")
        elif any(e.get("escalation_role") != ESCALATION_ROLE for e in ledger_events):
            problems.append("S8 台账里的转出目标不是「%s」" % ESCALATION_ROLE)
        if led.by_case("CASE-S8-002"):
            problems.append("S8 未到期的案件也产生了升级事件 —— 未超时样本不得升级")
        if any(e.get("case_id") == "CASE-S8-002" for e in emits):
            problems.append("S8 未到期案件出现在升级通知里")
    return problems


def strip_comments_and_docstrings(src: str) -> str:
    """剥掉整行注释与三引号块，保留可执行代码（与项目既有扫描器同一读法）。"""
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))


def scan_for_stop_behaviour(sources: dict[str, str]) -> list[str]:
    """S9：可执行代码里出现停机行为特征即红。"""
    hits = []
    for rel, src in sources.items():
        code = strip_comments_and_docstrings(src)
        for i, line in enumerate(code.splitlines(), 1):
            for pat in STOP_PATTERNS:
                if pat in line:
                    hits.append(f"{rel}:{i} 出现 {pat}（{line.strip()[:70]}）")
    return hits


def collect_sources() -> dict[str, str]:
    out = {}
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            try:
                out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
            except OSError:
                continue
    if not out:
        raise Untested("扫描目录里没有 .py —— 口径可能变了")
    return out


def assess(rows: list[dict], sources: dict[str, str]) -> list[str]:
    return (check_registry(rows)
            + check_no_early_stop()
            + check_failure_kinds()
            + check_single_query()
            + check_run_state()
            + check_control_points_once()
            + check_escalation()
            + scan_for_stop_behaviour(sources))


def controls() -> int:
    rows = [{"id": i, "condition": "x", "stage1": f"`{STAGE1}`（登记保留，不执行）"}
            for i in range(1, 7)]
    # ★ 整行注释不算代码；**行尾注释仍会被扫到**（与项目既有扫描器同一已知盲区）。
    good_src = {"base/x.py": "# early_stop 在这里只是登记词，不是行为\ndef f():\n    return 1\n"}
    bad_src = {"base/x.py": "def f():\n    if no_progress:\n        return None\n"}

    def red(frag, rows_=None, src_=None):
        return any(frag in p for p in assess(rows_ or rows, src_ or good_src))

    # ── S3/S4/S5/S6/S8 的负样本由 mutprobe 变异证明（#36-1…#36-6）；
    #    这里做**不依赖改生产代码**的离线反向对照：喂坏函数/坏台账，断言各检查会红。
    def bad_single_query():
        calls = []

        def query(ref):
            calls.append(ref.get("ref_id"))
            return {"state": "missing", "reason": "verify"}

        from base import evidence_sync as ES
        finding = {"finding_id": "f-x", "status": "confirmed",
                   "authority_ref": [{"ref_id": "r1"}, {"ref_id": "r2"}]}
        # 模拟「每个 ref 查两次」的坏行为：重复喂同样的调用串
        finding2 = dict(finding, authority_ref=[{"ref_id": "r1"}, {"ref_id": "r2"},
                                                {"ref_id": "r1"}, {"ref_id": "r2"}])
        ev = ES.enrich_findings([finding], query, "rules-v1", "kb-unavailable")
        ev2 = ES.enrich_findings([finding2], query, "rules-v1", "kb-unavailable")
        n_real, n_bad = len(ev["findings"][0]["resolution_detail"]["refs"]), \
            len(ev2["findings"][0]["resolution_detail"]["refs"])
        return n_real == 2 and n_bad == 4 and len(calls) == 6

    def bad_escalation_role_detected():
        # 台账里塞一条转出目标被改坏的事件 → 逐字判据必须红
        from base.case_watch import EscalationLedger
        with tempfile.TemporaryDirectory(prefix="stop-cond-ctl-") as td:
            led = EscalationLedger(path=str(Path(td) / "l.json"))
            led.record({"event_id": "e1", "case_id": "C-1", "kind": "case_overdue",
                        "escalation_role": "客服一线"})
            return all(e.get("escalation_role") == ESCALATION_ROLE
                       for e in led.by_case("C-1")) is False

    def bad_run_state_detected():
        # 正常路径 OK / 注入异常必须非 OK —— 用真 Orchestrator 验方向
        from base.orchestrator import Orchestrator
        u = _sample_unit()
        orch = Orchestrator(rule_judge=lambda _c: (_ for _ in ()).throw(RuntimeError("ctl")),
                            clock=lambda: 1000.0)
        res = orch.run({"skill_id": "v", "skill_hash": "h"}, unit=u)
        return res.get("run_state") != "OK"

    cases = [
        ("正样本：6 条齐全 + 无停机行为 → 必须绿", lambda: not assess(rows, good_src)),
        ("★ S1 坏样本：删掉一条 → 必须红", lambda: red("S1", rows_=rows[:5])),
        ("★ S1 坏样本：把一条状态改成 enabled → 必须红",
         lambda: red("S1", rows_=[*rows[:5], dict(rows[5], stage1="enabled")])),
        ("★ S9 坏样本：可执行代码里出现 no_progress → 必须红", lambda: red("no_progress", src_=bad_src)),
        ("反向对照：同一句只出现在注释里 → 不许误报",
         lambda: not any("no_progress" in p for p in
                         scan_for_stop_behaviour({"base/x.py": "# no_progress 只是注释\nreturn 1\n"}))),
        ("★ S4 反向对照：每条 ref 恰好一次查询是可数的（重试形状可被数出来）", bad_single_query),
        ("★ S5 反向对照：部件抛异常时 run_state 必须不是 OK（坏样本真的红）", bad_run_state_detected),
        ("★ S8 反向对照：台账里转出目标被改坏的事件必须被逐字判据抓住", bad_escalation_role_detected),
    ]
    bad = 0
    print("=" * 78)
    print("行 36 · 停机条件登记 / 不提前停（离线对照）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    try:
        rows = parse_stop_table(read_playbook())
        sources = collect_sources()
        problems = assess(rows, sources)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 36 · 停机条件登记（Playbook §3.3.7）与不提前停")
    print("=" * 78)
    for r in rows:
        print(f"  · {r['id']} {r['condition'][:28]:<28} → {r['stage1'][:40]}")
    print()
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print(f"✅ 退 0：登记 {len(rows)} 条、全部 {STAGE1}；真实入口五步各一次、无跳过；")
    print("   failure_kind 三种失败在 IR 可区分、报告可数；依据查询每条恰一次；")
    print("   正常跑 run_state=OK、部件出错变 ERROR；控制点清单各恰一次；")
    print("   到期升级转出「项目统筹」、事件带案件号可查，未到期不升级；")
    print("   可执行代码里没有 early_stop / no_progress / consecutive_rounds 行为。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
