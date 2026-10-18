#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_semantic_judge.py — T1-05 semantic_judge（适配 semantic_settle）

6d 原 30 项语义 + 5 类变异，适配盘上 449 行 `semantic_settle` 实现（sha 17e8eb55）。

5 类变异与对应断言（删掉修复必须红）：
  M1 去 C1–C4 任一 → 只能 candidate       → C3–C11 / C14–C16
  M2 开关默认关 → 不得 confirmed          → C1/C2
  M3 confirmed 无 bbox → 拒               → C18/C20
  M4 candidate 直出 BLOCK → 红            → C19/C20
  M5 stub 失败 → untested，不伪造命中      → C0/C9–C12

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    import base.semantic_judge as SJ
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.semantic_judge: %s" % exc)
    sys.exit(2)


def unit_spec(**over):
    d = {
        "judge_type": "literal",
        "object": "安全座椅",
        "attribute": "未使用",
        "can_recheck": True,
    }
    d.update(over)
    return d


def model_out(**over):
    d = {
        "kind": "visual",
        "object": "安全座椅",
        "attribute": "未使用",
        "x1": 0.1, "y1": 0.2, "x2": 0.4, "y2": 0.6,
        "severity": "L4",
        "reason": "画面可见",
        "model_id": "model-1",
    }
    d.update(over)
    return d


def make_model(outputs=None, available=True, fail=False, calls=None):
    class M:
        def available(self):
            return available

        def call(self, method=None, **kwargs):
            if calls is not None:
                calls.append((method, kwargs))
            if fail:
                raise SJ.ModelUnavailableError("model down")
            out = outputs[0] if outputs else {}
            return dict(out)
    return M()


def settle(spec=None, model=None, control_switch=None, control_code="H01", **kwargs):
    return SJ.semantic_settle(
        spec if spec is not None else unit_spec(),
        model=model,
        control_code=control_code,
        control_switch=control_switch,
        **kwargs,
    )


def bbox_ok(b):
    if isinstance(b, dict):
        vals = [b.get(k) for k in ("x1", "y1", "x2", "y2")]
    elif isinstance(b, (list, tuple)) and len(b) == 4:
        vals = list(b)
    else:
        return False
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return False
    x1, y1, x2, y2 = vals
    return 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1


def validate_finding(f):
    p = []
    if not isinstance(f, dict):
        return ["finding 必须是 dict"]
    status = f.get("status")
    if status not in ("candidate", "confirmed", "untested"):
        p.append("status=%r 非法" % (status,))
    if f.get("produced_by") != "semantic":
        p.append("produced_by 必须是 semantic")
    if status == "confirmed":
        if f.get("confirmed_by_rule_class") is not True:
            p.append("confirmed 必须 confirmed_by_rule_class=true")
        loc = f.get("location") or {}
        if not bbox_ok(f.get("bbox")) and not bbox_ok(loc.get("bbox")):
            p.append("confirmed 必须有 bbox")
    if status == "candidate" and f.get("confirmed_by_rule_class") is not False:
        p.append("candidate 的 confirmed_by_rule_class 必须 false")
    for k in ("state", "layer", "decision"):
        if k in f:
            p.append("finding 不许出现 %s" % k)
    return p


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    # C0/M5 无模型 / 不可用 / 异常 → untested
    for label, m in (
            ("无模型", None),
            ("不可用", make_model(available=False)),
            ("调用异常", make_model(fail=True))):
        o = settle(model=m, control_switch=True)
        report(o.get("status") == "untested"
               and "object" not in o and "attribute" not in o and "bbox" not in o
               and not validate_finding(o),
               "C0/M5 %s → untested，不伪造命中" % label, repr(o))

    # C1/C2/M2 默认开关关 → candidate
    for sw in (None, False):
        o = settle(model=make_model([model_out()]), control_switch=sw)
        report(o.get("status") == "candidate"
               and o.get("confirmed_by_rule_class") is False
               and not validate_finding(o),
               "C1/C2/M2 control_switch=%r → candidate" % (sw,), repr(o))

    # C3 C1–C4 全满足 + 开关开 → confirmed
    o = settle(model=make_model([model_out()]), control_switch=True)
    report(o.get("status") == "confirmed"
           and o.get("confirmed_by_rule_class") is True
           and o.get("produced_by") == "semantic"
           and o.get("authority_state") == "untested"
           and bbox_ok(o.get("bbox"))
           and not validate_finding(o),
           "C3 开关开 + C1–C4 满足 → confirmed", repr(o))

    # C4/C5 C1 失败：judge_type != literal
    for bad_judge in ("semantic", "mixed", None):
        o = settle(spec=unit_spec(judge_type=bad_judge),
                   model=make_model([model_out()]), control_switch=True)
        report(o.get("status") == "candidate",
               "C4/M1 C1 失败（judge_type=%r）→ candidate" % (bad_judge,), repr(o))

    # C6/C7 C2 失败：object/attribute 缺失
    for label, spec in (("object 缺失", unit_spec(object="")),
                        ("attribute 缺失", unit_spec(attribute=""))):
        o = settle(spec=spec, model=make_model([model_out()]), control_switch=True)
        report(o.get("status") == "candidate",
               "C6/M1 C2 失败（%s）→ candidate" % label, repr(o))

    # C8 C2 空泛词（Playbook：氛围/感觉 不是可枚举对象+属性）
    vague = model_out(object="氛围", attribute="感觉")
    o = settle(spec=unit_spec(object="氛围", attribute="感觉"),
               model=make_model([vague]), control_switch=True)
    report(o.get("status") == "candidate",
           "C8/M1 C2 空泛（氛围/感觉）→ candidate", repr(o))

    # C9/C10 C4 失败：bbox 缺失 / 非法 / 只有 char 位置
    for label, out in (
            ("bbox 缺失", {k: v for k, v in model_out().items()
                           if k not in ("x1", "y1", "x2", "y2")}),
            ("bbox 倒置", model_out(x1=0.9, y1=0.9, x2=0.8, y2=0.8)),
            ("仅 char 位置", {"kind": "text", "object": "安全座椅",
                              "attribute": "未使用", "char_start": 0,
                              "char_end": 3, "severity": "L4"})):
        o = settle(model=make_model([out]), control_switch=True)
        report(o.get("status") == "candidate",
               "C9/M1 C4 失败（%s）→ candidate" % label, repr(o))

    # C11/C12/C13 模型输出缺 kind/object/attribute → candidate
    for label, out in (
            ("缺 kind", {k: v for k, v in model_out().items() if k != "kind"}),
            ("缺 object", {k: v for k, v in model_out().items() if k != "object"}),
            ("缺 attribute", {k: v for k, v in model_out().items() if k != "attribute"}),
            ("空 dict", {})):
        o = settle(model=make_model([out]), control_switch=True)
        report(o.get("status") == "candidate",
               "C11/M1 模型输出%s → candidate" % label, repr(o))

    # C14 untested 无命中字段
    o = settle(model=None, control_switch=True)
    report(o.get("status") == "untested"
           and all(k not in o for k in ("object", "attribute", "bbox", "location")),
           "C14/M5 untested 不带命中字段", repr(o))

    # C15 candidate 字段
    o = settle(model=make_model([model_out()]), control_switch=False)
    report(o.get("status") == "candidate"
           and o.get("confirmed_by_rule_class") is False
           and o.get("produced_by") == "semantic",
           "C15 candidate 字段正确", repr(o))

    # C16 confirmed bbox/location 结构
    o = settle(model=make_model([model_out()]), control_switch=True)
    report(bbox_ok(o.get("bbox"))
           and isinstance(o.get("location"), dict)
           and bbox_ok(o["location"].get("bbox")),
           "C16 confirmed 带合法 bbox/location", repr(o))

    # C17 candidate 可带 bbox，但不得 confirmed
    o = settle(model=make_model([model_out()]), control_switch=False)
    report(bbox_ok(o.get("bbox")) and o.get("status") == "candidate",
           "C17 candidate 可带 bbox 但不得 confirmed", repr(o))

    # C18/M3 confirmed 无 bbox → 本地契约校验红
    confirmed = settle(model=make_model([model_out()]), control_switch=True)
    no_box = {k: v for k, v in confirmed.items() if k not in ("bbox", "location")}
    report(bool(validate_finding(no_box)),
           "C18/M3 confirmed 无 bbox → 红", repr(validate_finding(no_box)))

    # C19/M4 candidate 直出 BLOCK → 红
    cand = dict(confirmed, status="candidate", confirmed_by_rule_class=False)
    cand_block = dict(cand, state="BLOCK")
    report(bool(validate_finding(cand_block)),
           "C19/M4 candidate 直出 BLOCK → 红", repr(validate_finding(cand_block)))

    # C20 result 带 state/layer → 红
    report(bool(validate_finding(dict(confirmed, state="BLOCK"))),
           "C20/M4 result 带 state → 红", repr(validate_finding(dict(confirmed, state="BLOCK"))))
    report(bool(validate_finding(dict(confirmed, layer="DP2"))),
           "C20/M4 result 带 layer → 红", repr(validate_finding(dict(confirmed, layer="DP2"))))

    # C21 模型自述 confirmed 不得绕过开关
    noisy = model_out(status="confirmed", confirmed_by_rule_class=True)
    o = settle(model=make_model([noisy]), control_switch=False)
    report(o.get("status") == "candidate"
           and o.get("confirmed_by_rule_class") is False,
           "C21 模型自述 confirmed 不得绕过开关", repr(o))

    # C22 模型调用注入与次数
    calls = []
    o = settle(model=make_model([model_out()], calls=calls), control_switch=True)
    report(len(calls) == 1 and calls[0][0] == "judge"
           and o.get("status") == "confirmed",
           "C22 模型调用可注入且只调一次", repr(calls))

    # C23/C24 参数校验
    try:
        settle(model=make_model([model_out()]), control_code="")
        ok23 = False
    except ValueError:
        ok23 = True
    report(ok23, "C23 control_code 为空 → ValueError", "")
    try:
        settle(model=make_model([model_out()]), control_switch="yes")
        ok24 = False
    except ValueError:
        ok24 = True
    report(ok24, "C24 control_switch 非 bool → ValueError", "")

    # C25 确定性
    a = settle(model=make_model([model_out()]), control_switch=True)
    b = settle(model=make_model([model_out()]), control_switch=True)
    report(a.get("status") == b.get("status")
           and a.get("object") == b.get("object")
           and a.get("bbox") == b.get("bbox"),
           "C25 同输入两次结果确定", repr((a.get("status"), b.get("status"))))

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) == "semantic_judge.py":
            print("FAIL: semantic_judge 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
