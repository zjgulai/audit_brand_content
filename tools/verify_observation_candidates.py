#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_observation_candidates.py —— 观察升级成 candidate 的边界

## 它守的是什么

`base/observation_candidates.py` 把「确定性事实类」的观察升级成 candidate finding。
这一步的风险不是「漏」，是**越权和误报**：

| 越权 | 后果 |
|---|---|
| 产出 `confirmed` | 机器替人做了终审 —— 而 C1–C4 的闸门根本没走到 |
| `authority_state` 写成 `missing`/`ok` | 本层不查依据，写了就是编 |
| 升级「医疗宣称」这类法规判断 | 判据无法复核，人会开始不看队列 |
| 对着 `untested`/`error` 观察产 finding | 把「没看成」读成「看到了问题」 |
| 同码多条 | 一个水印在界面上读成两个问题 |

## 它跟哪个文件的接线最要紧

`base/judge_entry.py` —— 本模块的产出是在那里并进 `findings` 的
（`fact_candidates` 那一段）。**那个接线断掉时，本文件 A–F 组会全绿**，
因为它们测的是模块本身。

★ 所以接线由另一条断言守：`tools/verify_media_analyze.py` 的 H 组验
  「观察能到判定层」，而本文件的 C 组验「到了之后形状对不对」。
  两者缺一：只有 C 组 → 模块对了但没接上；只有 H 组 → 接上了但可能越权。

## 分组

| 组 | 验什么 |
|---|---|
| A | 四条规则的**正例**（实测过的真实观察原文，必须命中） |
| B | ★★★ **反例**：不该命中的一句都不许命中（防误报） |
| C | ★★★ 三态底线：只产 candidate / 不产 confirmed / authority_state=untested |
| D | 去重：同 control_code 一张图只出一条 |
| E | 非 ok 观察不产 finding（untested / error 不许读成「有问题」） |
| F | 反向对照：把规则判据改坏，A 组必须红 |

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


def obs(statement, *, task="scene_semantics", status="ok"):
    return {"task": task, "statement": statement, "status": status,
            "reason": "" if status == "ok" else "fake"}


# ─────────────────────────────────────────────── A 正例（真实观察原文）

def group_a():
    from base.observation_candidates import candidates_from_observations as C

    # ★ 每一条都逐字来自 2026-10-29 实测的多模态输出，不是我编的句子。
    #   编句子会让判据「恰好匹配我编的那句」，而真实输出换个说法就漏。
    CASES = [
        ("拼写错误",
         "可见文字Product Free Trail疑似Trial拼写错误，Recieve a opportunity及a free a等疑似拼写/语法错误，需人工复核文案准确性",
         "M01"),
        ("拼写异常（另一种说法）",
         "底部「Product Free Trail」条目疑似拼写错误（Trail/Trial），同页另见「Recieve」拼写异常",
         "M01"),
        ("货币混用",
         "同一页面混用A$与£两种货币符号（可见A$4.99、A$8、£20、£79），权益价值标注口径不一致，建议人工复核",
         "M02"),
        ("设计稿水印",
         "全画面多处重复出现「陈欣玮 2556 ROOT」字样水印，疑似素材或设计稿水印，需人工复核图片来源与授权情况",
         "M03"),
        ("清晰度不足",
         "左侧贺卡及礼盒上的小字图形细节分辨率不足，无法确认是否含微小认证符号，看不清",
         "M04"),
    ]
    for label, statement, want in CASES:
        got = C([obs(statement)], unit_id="u-a")
        codes = [c["control_code"] for c in got]
        report(codes == [want],
               "A ★ %s → %s" % (label, want), repr(codes))


# ─────────────────────────────────────────────── B 反例（不许命中）

def group_b():
    from base.observation_candidates import candidates_from_observations as C

    # ★★★ 这一组比 A 组更重要：A 只证明「能命中」，
    #   B 才证明「不瞎命中」。而误报的代价是让人不再看队列。
    #
    #   下面每一句都是**真实观察里出现过的形态**，它们**不该**产生 finding：
    NEGATIVES = [
        # 「看不清」是模型主动说没看清（正确行为），不是图片质量问题
        ("只说看不清，没提分辨率",
         "画面中未清晰展示具体产品实物（看不清产品）"),
        # 否定式陈述：说「没发现」不是「发现了」
        ("明确说未发现拼写问题",
         "未见拼写或语法错误，文案表述规范"),
        # 提到水印但是否定（说没有）
        ("说没有水印",
         "画面干净，无水印、无占位符残留"),
        # 法规类判断不归本模块（要人看）
        ("医疗宣称类",
         "标题称催产素才能发挥其作用，涉及激素作用/功效的表述，需人工复核"),
        # 氛围/调性判断（C2 明确排除）
        ("品牌调性",
         "整体为粉白马卡龙配色，与母婴品牌定位一致"),
    ]
    for label, statement in NEGATIVES:
        got = C([obs(statement)], unit_id="u-b")
        report(got == [],
               "B ★★★ 反例不命中：%s" % label,
               repr([c["control_code"] for c in got]))

    # B6 ★★ 空输入 → 空列表（不是 None，也不是伪造一条）
    report(C([], unit_id="u") == [], "B6 ★★ 空观察 → 空列表")
    report(C(None, unit_id="u") == [], "B7 ★★ None → 空列表（不抛）")


# ─────────────────────────────────────────────── C 三态底线

def group_c():
    from base.observation_candidates import candidates_from_observations as C

    got = C([obs("可见文字疑似拼写错误，需复核")], unit_id="u-c")
    report(len(got) == 1, "C1 好样本产 1 条（否则下面全是恒真）")
    if not got:
        return
    f = got[0]

    # ★★★ 这三条是本模块的**全部底线**，缺一条就是越权。
    report(f.get("status") == "candidate",
           "C2 ★★★ 只产 candidate（绝不产 confirmed —— 机器不替人终审）",
           repr(f.get("status")))
    report(f.get("confirmed_by_rule_class") is False,
           "C3 ★★★ confirmed_by_rule_class=False（C1–C4 闸门根本没走到）",
           repr(f.get("confirmed_by_rule_class")))
    report(f.get("authority_state") == "untested",
           "C4 ★★★ authority_state=untested（本层不查依据，不知道就不许写别的）",
           repr(f.get("authority_state")))

    # C5 ★★ 可追溯：要能指回是哪条观察推出来的
    report(f.get("derived_from_observation", {}).get("statement"),
           "C5 ★★ 带 derived_from_observation（报告要说清它不是规则命中）",
           repr(f.get("derived_from_observation")))
    report(f.get("produced_by") == "verifiable-fact",
           "C6 ★★ produced_by 标明来源（与 semantic / rule 区分开）",
           repr(f.get("produced_by")))
    report(f.get("location") is None,
           "C7 ★★ location=None（没有 bbox 就不许编一个）",
           repr(f.get("location")))


# ─────────────────────────────────────────────── D 去重

def group_d():
    from base.observation_candidates import candidates_from_observations as C

    # ★ 实测形态：同一张图上两条观察都提到水印，句子不同。
    #   若按 finding_id 去重会产出两条，界面上读成「两个水印问题」。
    got = C([
        obs("全画面多处重复出现「陈欣玮 2556 ROOT」字样水印，疑似设计稿水印"),
        obs("画面上叠加有多个半透明「陈欣玮 2556 ROOT」字样水印，为版权水印"),
    ], unit_id="u-d")
    report(len(got) == 1,
           "D1 ★★★ 同一 control_code 一张图只出一条（两种说法＝同一个问题）",
           "%d 条：%r" % (len(got), [c["control_code"] for c in got]))

    # D2 ★★ 不同 control_code 各出一条（别把去重做成「只留第一条」）
    multi = C([
        obs("疑似拼写错误"),
        obs("同一页面混用A$与£两种货币，口径不一致"),
    ], unit_id="u-d2")
    report({c["control_code"] for c in multi} == {"M01", "M02"},
           "D2 ★★ 不同码各出一条（去重不许变成「只留第一条」）",
           repr([c["control_code"] for c in multi]))

    # D3 ★★ finding_id 稳定：同一输入两次跑结果相同
    a = C([obs("疑似拼写错误")], unit_id="u-d3")
    b = C([obs("疑似拼写错误")], unit_id="u-d3")
    report(a[0]["finding_id"] == b[0]["finding_id"],
           "D3 ★★ finding_id 稳定（随机 id 会让同一问题重复记）",
           a[0]["finding_id"][:14])


# ─────────────────────────────────────────────── E 非 ok 观察

def group_e():
    from base.observation_candidates import candidates_from_observations as C

    # ★★★ 「没看成」不是「看到了问题」。
    #
    #   untested 条目的 statement 是空串，但就算它写了字，也不许产 finding ——
    #   因为那个条目的语义是「这个任务没跑成」，不是「画面有什么」。
    for status in ("untested", "error"):
        got = C([obs("疑似拼写错误", status=status)], unit_id="u-e")
        report(got == [],
               "E ★★★ %s 观察不产 finding（没看成 ≠ 有问题）" % status,
               repr([c["control_code"] for c in got]))

    # E3 ★★ 混在一起时只取 ok 的
    mixed = C([
        obs("", status="untested"),
        obs("疑似拼写错误"),
    ], unit_id="u-e3")
    report(len(mixed) == 1,
           "E3 ★★ 混入时只取 ok 的那条", "%d 条" % len(mixed))


# ─────────────────────────────────────────────── F 反向对照

def group_f():
    from base import observation_candidates as OC

    # F1 ★★★ 规则列表非空且每条都有 control_code / patterns / why
    #
    #   ★ 只验「有 4 条」会让一个忘写 patterns 的规则也绿 ——
    #     而 pattern 为空时它永远不命中，等于那条规则不存在。
    bad = [r["key"] for r in OC.RULES
           if not r.get("control_code") or not r.get("patterns")
           or not r.get("why") or not r.get("label")]
    report(not bad,
           "F1 ★★★ 每条规则都有 control_code / patterns / why / label",
           repr(bad))

    # F2 ★★★ patterns 必须能编译（写坏一条正则会静默不命中）
    import re as _re
    broken = []
    for r in OC.RULES:
        for p in r["patterns"]:
            try:
                _re.compile(p)
            except _re.error:
                broken.append((r["key"], p))
    report(not broken, "F2 ★★★ 所有 patterns 可编译", repr(broken[:2]))

    # F3 ★★★ control_code 必须是**今天可用**的码
    #
    #   ★ 这一条拦的是「挂到一个 deprecated 的码上」——
    #     B01–B04 / U02 今天不可用，挂上去会让 downsteam 抛异常。
    try:
        from base import judge_entry as J
        reg = J.ControlPointRegistry()
        usable = set()
        for code in reg.active_codes():
            try:
                reg.get_active(code)
                usable.add(code)
            except Exception:  # noqa: BLE001
                continue
        declared = {r["control_code"] for r in OC.RULES}
        report(declared <= usable,
               "F3 ★★★ 所有 control_code 都是今天可用的码",
               "不可用 %r" % (sorted(declared - usable),))
    except Exception as exc:  # noqa: BLE001
        untested("F3 control_code 可用性", "%s: %s" % (type(exc).__name__, exc))

    # F4 ★★★ 反向对照：把某条规则的 patterns 清空，A 组必须红
    #
    #   ★ 证明 A 组不是恒真。做法：临时替换 RULES 并重置编译缓存，
    #     跑一次，再恢复。
    original = OC._COMPILED
    try:
        OC._COMPILED = OC._compile([
            {**r, "patterns": []} if r["key"] == "spelling" else r
            for r in OC.RULES
        ])
        got = OC.candidates_from_observations(
            [obs("疑似拼写错误，需复核")], unit_id="u-f4")
        report(got == [],
               "F4 ★★★ 反向对照：拼写规则 patterns 清空后不再命中（证明 A 组有效）",
               repr([c["control_code"] for c in got]))
    finally:
        OC._COMPILED = original
    # F5 ★★ 恢复之后必须又能命中（否则上一行可能是「本来就一直不命中」）
    got2 = OC.candidates_from_observations(
        [obs("疑似拼写错误，需复核")], unit_id="u-f5")
    report(len(got2) == 1, "F5 ★★ 恢复后重新命中（证明 F4 的变异真的被撤销了）",
           "%d 条" % len(got2))


def main():
    print("=" * 74)
    print("observation_candidates · 观察升级 candidate 的边界")
    print("=" * 74)
    try:
        import base.observation_candidates  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        untested("导入 base/observation_candidates", str(exc))
        return 2
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    group_f()
    print("-" * 74)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
