#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_multimodal_observation.py — T-433：L1 观察落地 + 报告成节

## 这一票的边界（最容易被做错的一处）

finding 的三要素是**合取**：`control_code` / `authority_ref` / `location`
（`base/finding_store.py:69`，缺一即拒）。多模态能给 `location`，
给不出前两项 —— 它们是知识库产物。

所以「先打通 + 落 candidate finding + 知识库慢慢建」三条**不能同时成立**：

  L1 观察 → `case.multimodal_observations`（进权威、报告单独成节、标候选待确认）
  L2 候选 → 现有 finding 表（等一批 control_code，T-434）

**L1 不是降级，是照实说。** 一条没有 control_code 的「画面语义」今天就不是 finding，
是观察。把观察伪装成 finding，后果是复核时**无法申诉** —— 没有 control_code
就无法对照规则。

## 断言分组

  L1  观察进权威：state 里有、能重放、与 ir.findings 分开
  L2  三态可分：ok / untested / error 在数据上长得不一样（空 ≠ 没问题）
  L3  reducer 拒坏形状：ok 无 statement / 非 ok 无 reason / finding 用语混入
  L4  judge_entry 的收集：未注入 analyze / 非媒体载体 / analyze 抛异常 /
      provider 少给任务 / ok 但空 observations —— 每种都不许被读成「看过没问题」
  L5  报告快照：判定时冻结，不是渲染时现取（同一个量两个口径）
  L6  finding 表没被污染：produced_by=multimodal 仍不在白名单（T-434 才做）

## 直接主体

- `base/judge_entry.py` —— 观察的**收集**点（`_collect_multimodal_observations`）
  与报告快照的装配点（`_with_observations`）
- `base/review_reducer.py` —— 观察的**准入**点（`multimodal_observations` 的形状校验）
- `base/finding_store.py` —— 只读引用：证明本票**没有**放宽 finding 的准入三要素

退出码：0 全过 / 1 有红 / 2 未测（导入失败）。
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


try:
    from base import contract as C
    from base import judge_entry as J
    from base import review_reducer as RR
    from base import finding_store as FS
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 L1 观察链: %s" % exc)
    sys.exit(2)


ACTOR = "u-verify"
CASE = "case-verify"


def _payload(**over):
    base = {
        "case_id": CASE, "submission_id": "sub-1", "submission_hash": "h" * 8,
        "tenant": "t-1", "product_line": "p-1", "submitter_id": "u-1",
        "content": {"unit_id": "cu-1",
                    "fingerprint": {"text_sha256": "t" * 64}},
        "ir": {"ir_id": "ir-1", "findings": [],
               "decision": {"state": "REVIEW"},
               "control_points_version": "cp-1"},
        "judgment": {"run_state": "OK", "label": "REVIEW"},
        "kb_snapshot_hash": "a" * 64, "conflict_table_version": "cp-1",
        "multimodal_observations": [],
    }
    base.update(over)
    return base


def _run(payload):
    out = RR.reduce_command(RR.initial_state(CASE), "ingest_submission", ACTOR, 0,
                            payload=payload)
    return out[0] if isinstance(out, tuple) else out


def _expect_reject(payload):
    try:
        _run(payload)
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__
    return None


# ── L1：观察进权威 ────────────────────────────────────────────────────

def check_authority():
    obs = [
        {"status": "ok", "task": "scene_semantics",
         "statement": "画面演示婴儿睡眠场景", "reason": "", "confidence": 0.82},
        {"status": "untested", "task": "mark_symbol", "reason": "未接入"},
    ]
    state = _run(_payload(multimodal_observations=obs))
    got = state.get("multimodal_observations")
    report(got == obs, "L1-1 ★ 观察原样进 state（逐字，不改写）", repr(got)[:120])
    report(isinstance(state.get("ir"), dict)
           and state["ir"].get("findings") == [],
           "L1-2 ★★ 观察**不**进 ir.findings（finding 准入是三要素合取）",
           repr((state.get("ir") or {}).get("findings")))
    # 重放：投影重建就是重放 state 快照，所以观察必须随 state 走
    report("multimodal_observations" in RR.initial_state(CASE),
           "L1-3 初始 state 有该键（键不许是临时加上的）")
    # 缺省 → 空列表，不是缺字段
    state2 = _run(_payload())
    report(state2.get("multimodal_observations") == [],
           "L1-4 没观察时是 []，不是缺字段", repr(state2.get("multimodal_observations")))


# ── L2：三态可分 ──────────────────────────────────────────────────────

def check_three_states():
    ok_obs = {"status": "ok", "task": "t", "statement": "看到了 X", "reason": ""}
    un_obs = {"status": "untested", "task": "t", "statement": "", "reason": "没看成"}
    er_obs = {"status": "error", "task": "t", "statement": "", "reason": "429"}
    for name, obs in (("ok", ok_obs), ("untested", un_obs), ("error", er_obs)):
        state = _run(_payload(multimodal_observations=[obs]))
        report(state.get("multimodal_observations") == [obs],
               "L2-%s 单条 %s 观察可落库" % (name, name))
    report(RR.OBSERVATION_STATUSES == frozenset({"ok", "untested", "error"}),
           "L2-4 ★ 观察状态域与 finding 的状态词**分开**（不含 candidate/confirmed）",
           repr(sorted(RR.OBSERVATION_STATUSES)))
    # ★ 独立一条、判直的写法：finding 的四个状态词一个都不许出现在观察状态里。
    #   第一版写成了一串 or 表达式，那是**恒真**的 —— 看似在断言，其实什么也没拦。
    forbidden = FS.VALID_STATUS
    report(not (RR.OBSERVATION_STATUSES & forbidden),
           "L2-5 ★ 观察状态里不含 finding 的任何状态词",
           repr(sorted(RR.OBSERVATION_STATUSES & forbidden)))


# ── L3：reducer 拒坏形状 ──────────────────────────────────────────────

def check_reducer_rejects():
    cases = (
        ("L3-1 ★ ok 但没有 statement → 必须拒（空观察不许读成『看过没问题』）",
         [{"status": "ok", "task": "t", "statement": "", "reason": ""}]),
        ("L3-2 ★ ok 但 statement 是空白 → 必须拒",
         [{"status": "ok", "task": "t", "statement": "   ", "reason": ""}]),
        ("L3-3 ★ untested 但没有 reason → 必须拒（未测不是没问题）",
         [{"status": "untested", "task": "t"}]),
        ("L3-4 ★ error 但没有 reason → 必须拒",
         [{"status": "error", "task": "t", "statement": ""}]),
        ("L3-5 ★ status 用了 finding 的词（confirmed）→ 必须拒",
         [{"status": "confirmed", "task": "t", "statement": "x"}]),
        ("L3-6 缺 task → 必须拒", [{"status": "ok", "statement": "x"}]),
        ("L3-7 观察不是对象 → 必须拒", ["裸字符串"]),
    )
    for name, obs in cases:
        code = _expect_reject(_payload(multimodal_observations=obs))
        report(code == "LedgerValidation", name, repr(code))
    code = _expect_reject(_payload(multimodal_observations={"not": "a list"}))
    report(code == "LedgerValidation",
           "L3-8 整体不是数组 → 必须拒", repr(code))


# ── L4：judge_entry 的收集 ────────────────────────────────────────────

def _image_unit():
    return {
        "unit_id": "cu-img-1", "contract_version": "content-unit-v1",
        "source": {"kind": "image", "uri": "inline:x", "raw_bytes": 10},
        "parse_status": "ok", "failure_kind": None, "text": "图内文字",
        "textification": {"covers": ["图内文字"], "does_not_cover": ["画面语义"]},
        "fingerprint": {"raw_sha256": "r" * 64, "text_sha256": "t" * 64},
        "context": {},
    }


def check_judge_entry():
    unit = _image_unit()
    # 未注入 analyze
    res = J.judge_unit(unit)
    report(res.get("multimodal_observations") == []
           and res.get("multimodal_note") == "未接入多模态分析",
           "L4-1 ★★ 未注入 analyze → 空观察 + note（不是静默空列表）",
           repr(res.get("multimodal_note")))
    # 非媒体载体
    text_unit = dict(unit, source={"kind": "free_text"})
    res2 = J.judge_unit(text_unit, multimodal_analyze=lambda ref, tasks: {})
    report(res2.get("multimodal_note") == "本载体无需多模态分析",
           "L4-2 文本载体 → note「无需多模态分析」", repr(res2.get("multimodal_note")))

    # analyze 抛异常 → 落 error 观察，不落空
    def boom(ref, tasks):
        raise RuntimeError("网关炸了")

    res3 = J.judge_unit(unit, multimodal_analyze=boom)
    obs3 = res3.get("multimodal_observations") or []
    report(len(obs3) == 1 and obs3[0]["status"] == "error"
           and "网关炸了" in obs3[0]["reason"],
           "L4-3 ★★ analyze 抛异常 → 落 error 观察（不落空列表）", repr(obs3)[:120])

    # provider 少给任务 → untested
    res4 = J.judge_unit(unit, multimodal_analyze=lambda ref, tasks: {
        "status": "ok", "model": "m", "tasks": {}})
    obs4 = res4.get("multimodal_observations") or []
    report(len(obs4) >= 1 and obs4[0]["status"] == "untested",
           "L4-4 ★ provider 没返回该任务 → untested（不许当成没问题）",
           repr(obs4)[:120])

    # ok 但 observations 空 → 自我矛盾，落 untested
    res5 = J.judge_unit(unit, multimodal_analyze=lambda ref, tasks: {
        "status": "ok", "model": "m",
        "tasks": {"scene_semantics": {"status": "ok", "observations": []}}})
    obs5 = res5.get("multimodal_observations") or []
    report(obs5 and obs5[0]["status"] == "untested",
           "L4-5 ★★ provider 报 ok 但 observations 空 → 落 untested（不是 ok）",
           repr(obs5)[:120])

    # 正常路径
    res6 = J.judge_unit(unit, multimodal_analyze=lambda ref, tasks: {
        "status": "ok", "model": "glm-5.3-flash",
        "tasks": {"scene_semantics": {"status": "ok", "observations": [
            {"statement": "画面演示婴儿床", "confidence": 0.8,
             "region": "中央"}]}}})
    obs6 = res6.get("multimodal_observations") or []
    # ★★ 2026-10-30 修：判据从「总条数 == 1」改成「按 task 定位那一条」。
    #
    #   旧判据写的时候 `DEFAULT_MEDIA_TASKS` 只有 `scene_semantics` 一个任务，
    #   于是「1 条观察」等价于「那个任务的那一条」。后来 H8 那条断言
    #   （"默认任务含 mark_symbol，否则标志/资质图标永远不识别"）把
    #   `mark_symbol` 加进默认集合 —— 桩只回了 scene_semantics，
    #   于是 mark_symbol 按契约落一条 untested 占位（**这是对的**：
    #   少一个任务必须说出来，不许静默消失），总数就变成 2。
    #
    #   改后判据问的是它真正要问的：**那一条 ok 观察有没有逐字段落下来**。
    #   总数不是这条断言的对象 —— 「有几个任务」由 H8 那条管。
    scene = [o for o in obs6 if o.get("task") == "scene_semantics"]
    report(len(scene) == 1 and scene[0]["status"] == "ok"
           and scene[0]["statement"] == "画面演示婴儿床"
           and scene[0]["confidence"] == 0.8
           and scene[0]["bbox"] == "中央",
           "L4-6 正常观察逐字段落下来（statement/confidence/bbox）", repr(obs6)[:140])
    # ★ 反向对照：另一条任务**必须**留下 untested 占位（不是消失）
    report(any(o.get("task") == "mark_symbol" and o.get("status") == "untested"
               for o in obs6),
           "L4-6b ★ 桩没给的那个任务留 untested 占位（少一个任务要说出来）",
           repr([(o.get("task"), o.get("status")) for o in obs6])[:120])
    report(obs6 and obs6[0].get("egress_status") == "authorized",
           "L4-7 观察带 egress_status（出境状态随观察走）")

    # 每条观察都必须能落进 reducer 的校验（两处口径不许分叉）
    code = _expect_reject(_payload(multimodal_observations=obs6))
    report(code is None,
           "L4-8 ★ judge_entry 产出的观察必须能过 reducer 的校验（口径一致）",
           repr(code))


# ── L5：报告快照冻结 ──────────────────────────────────────────────────

def check_snapshot():
    unit = _image_unit()
    res = J.judge_unit(unit, multimodal_analyze=lambda ref, tasks: {
        "status": "ok", "model": "m",
        "tasks": {"scene_semantics": {"status": "ok",
                                      "observations": [{"statement": "X"}]}}})
    snap = res.get("report_snapshot")
    report(isinstance(snap, dict), "L5-1 report_snapshot 存在")
    report(snap.get("multimodal_observations") == res.get("multimodal_observations"),
           "L5-2 ★★ 快照里的观察 == 返回值里的观察（判定时冻结，同源）")
    report(snap.get("multimodal_note") == res.get("multimodal_note"),
           "L5-3 快照带 note")
    # 空快照不许被造假壳
    report(J._with_observations(None, [{"a": 1}], "") is None,
           "L5-4 ★ 快照为 None 时原样返回 None（不凭观察造壳）")
    # 不许改动原快照
    original = {"ir": {"ir_id": "x"}, "multimodal_observations": ["旧"]}
    cloned = J._with_observations(original, [{"status": "ok"}], "")
    report(original["multimodal_observations"] == ["旧"]
           and cloned["multimodal_observations"] == [{"status": "ok"}],
           "L5-5 ★ 不改动传入的快照（拷贝而非原地改）")


# ── L6：finding 表没被污染 ────────────────────────────────────────────

def check_finding_table_untouched():
    report("multimodal" not in FS.ALLOWED,
           "L6-1 ★ multimodal 仍不在 finding 白名单（T-434 才做，需 control_code）",
           repr(sorted(FS.ALLOWED)))
    report(FS.ADMISSION_KEYS == ("control_code", "authority_ref", "location"),
           "L6-2 准入三要素未变（本票不去放宽它）", repr(FS.ADMISSION_KEYS))


# ── L7：报告与工作台两处措辞必须同口径 ────────────────────────────────

def check_two_surfaces():
    """同一件事在两处渲染：报告（Node）与工作台（TSX）。

    ★ 为什么要有这一条：这两处是**两个独立实现**（渲染器不许 import Python，
      前端不 import Node），所以「候选 · 待人工确认」这句话会被各写一遍。
      两处各写一遍必然各自漂移 —— 而漂移的后果是群里收到的报告说「候选」、
      工作台上看到的是「已确认」，同一份观察两种定性。
      本项目已经因为「同一个量两个口径」栽过多次（§2.4.8）。
    """
    def _string_literals(source: str) -> str:
        """去掉整行注释与 `//` 之后的内容，只留**代码**。

        ★ 为什么需要它：L7-3/L7-4 会被注释里的解释文字喂饱（实测过）。
        """
        out = []
        for raw in source.splitlines():
            line = raw
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*") \
                    or stripped.startswith("/*"):
                continue
            if "//" in line:
                line = line.split("//", 1)[0]
            out.append(line)
        return "\n".join(out)

    report_mjs = (ROOT / "tools" / "audit" / "report_render.mjs").read_text(encoding="utf-8")
    viewer_tsx = (ROOT / "web" / "src" / "components"
                  / "ContentUnitViewer.tsx").read_text(encoding="utf-8")
    phrase_report = "候选 · 待人工确认"
    # ★★ 2026-10-27 更正：这条判据原先写死「两处都必须含『候选 · 待人工确认』」。
    #   另一个会话做文案返工时把工作台那处改成了「候选，待人工确认」（顿号换成逗号），
    #   于是 L7-2 变红 —— **它红得对**：判据本来就是为了防两处漂移而写的。
    #   但「红」本身不说明该改哪一边。真实含义是：
    #   **L7 要守的是「两处一致」，不是「必须用间隔号」。** 把标点写死进判据，
    #   等于替产品做了一个它没做的决定，还把一次文案返工误报成缺陷。
    #   所以改为：各自抽出这句话，断言**两边抽出来的完全相同**。
    PHRASE_RE = re.compile(r"候选\s*[·，,、]\s*待人工确认")

    def _phrase_in(text):
        found = PHRASE_RE.findall(text)
        return found[0] if found else None

    report(_phrase_in(_string_literals(report_mjs)) is not None,
           "L7-1 报告的**代码**里有「候选 · 待人工确认」这句话",
           repr(_phrase_in(_string_literals(report_mjs))))
    # ★ L7-2 必须只看**渲染出来的那一处**，不能看整份文件。
    #   第一版写成 `phrase in viewer_tsx` —— 于是把渲染处改掉之后它仍然绿，
    #   因为文件头注释里还有那句。真变异实测过。判据要精确到 JSX 元素。
    jsx_render = re.compile(
        r"<strong>\s*候选\s*[·，,、]\s*待人工确认\s*</strong>")
    report(bool(jsx_render.search(viewer_tsx)),
           "L7-2 ★★ 工作台**渲染的 JSX 元素**含同一句话（注释不算）")
    # ★★ 新加的核心判据：两处**必须一致**（这才是 L7 的立意）。
    report(_phrase_in(_string_literals(report_mjs)) == _phrase_in(viewer_tsx),
           "L7-2c ★★★ 报告与工作台用的是**逐字相同**的那句话"
           "（漂移就是这条判据要拦的东西）",
           "report=%r viewer=%r" % (_phrase_in(_string_literals(report_mjs)),
                                    _phrase_in(viewer_tsx)))
    # ★ 反向对照：改掉渲染处的措辞必须能红
    bad_sample = viewer_tsx.replace("<strong>候选，待人工确认</strong>",
                                    "<strong>已确认</strong>").replace(
        "<strong>候选 · 待人工确认</strong>", "<strong>已确认</strong>")
    report(bad_sample != viewer_tsx and not jsx_render.search(bad_sample),
           "L7-2b ★ 反证：改掉渲染处的措辞会红（判据不是被注释喂饱的）")
    # ★ 反向对照：两处用**不同**标点时，L7-2c 必须红（否则它恒真）
    report(_phrase_in("x = \"候选 · 待人工确认\"") != _phrase_in("x = \"候选，待人工确认\""),
           "L7-2d ★ 反证：两种标点抽出来不相等（L7-2c 不是恒真）")
    # ★ 两处都不许出现冒充表述 —— **只查源码里的字符串字面量，不查注释**。
    #
    #   这一条我自己踩过一次：第一版直接 `w in text`，于是命中了渲染器注释里那句
    #   「这里的措辞不许出现『已通过』/『画面正常』」。一句**解释这条规则为什么存在**
    #   的注释被判成违规 —— 与 T-432 的 N2 完全同一个形状。
    #   修法不是改注释，是让判据只读字面量（去掉整行注释与 `//` 之后的内容）。
    for name, text, label in (
            ("L7-3", report_mjs, "报告渲染器"),
            ("L7-4", viewer_tsx, "工作台组件")):
        body = _string_literals(text)
        bad = [w for w in ("已通过", "画面语义正常", "画面正常") if w in body]
        report(bad == [], "%s ★ %s 的**代码**里不含冒充表述 %r" % (name, label, bad),
               repr(bad))
    # ★ 反向对照：扫描器必须能抓到真的写进代码的冒充表述（否则 L7-3/4 恒真）
    report(bool([w for w in ("已通过",) if w in _string_literals('x = "已通过"')]),
           "L7-4b ★ 反证：真写进代码的冒充表述会被抓到（判据不是恒真）")
    report([w for w in ("已通过",) if w in _string_literals("// 不许写「已通过」")] == [],
           "L7-4c ★ 反证：只出现在注释里的不算违规")
    # ★ 空观察时的「未评」措辞也必须两处都有
    report("未评" in report_mjs and "未评" in viewer_tsx,
           "L7-5 ★ 两处都用「未评」表达空观察（不许一处写「无」一处写「未评」）")
    # ★ 前端类型必须真的声明了观察字段（否则 UI 拿不到数据）
    client_ts = (ROOT / "web" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    report("multimodal_observations" in client_ts
           and "MultimodalObservation" in client_ts,
           "L7-6 ★ 前端 CaseDetail 类型声明了观察字段")
    # ★ 页面必须真的把值传下去（声明了但没传 = 幽灵字段）
    page_tsx = (ROOT / "web" / "src" / "pages" / "CaseDetailPage.tsx").read_text(encoding="utf-8")
    report("observations={detail.multimodal_observations}" in page_tsx
           or "detail.multimodal_observations" in page_tsx,
           "L7-7 ★★ 案件详情页真的把观察传给查看器（声明≠传值）")


def main():
    print("=" * 78)
    print("T-433 · L1 观察落地 + 报告成节")
    print("=" * 78)
    check_authority()
    check_three_states()
    check_reducer_rejects()
    check_judge_entry()
    check_snapshot()
    check_finding_table_untouched()
    check_two_surfaces()
    print("-" * 78)
    if FAILED:
        print("❌ %d passed, %d failed" % (PASSED, FAILED))
        return 1
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
