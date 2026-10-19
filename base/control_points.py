#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/control_points.py —— 控制点主表注册表（T1-04）

只做一件事：**把 `control-points-v1.json` 读成「active 码的注册表」**。

  - `ControlPointRegistry.get_active(code)`：只返回 `status=active` 的条目；
  - `status=deprecated` → `DeprecatedControlCode`；不存在 → `UnknownControlCode`；
  - `table_version` 原样暴露（回执要记实际使用的版本，L6-6）；
  - 不判 state / layer / obligations，不写回执，不碰规则内容。

口径（照实写）：主表里出现 `status` 既不是 active 也不是 deprecated 的条目时，
`get_active` 按「非 active」拒收，异常类型用 `DeprecatedControlCode`
（消息里写明实际 status）—— 本模块只区分「可用 / 不可用」，不发明第三套状态机。
"""
from __future__ import annotations

import json
import os

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research", "governance", "control-points-v1.json")

SCHEMA_VERSION = "control-points-v1"


class ControlPointError(Exception):
    pass


class UnknownControlCode(ControlPointError):
    pass


class DeprecatedControlCode(ControlPointError):
    pass


class ControlPointRegistry(object):
    def __init__(self, path=None):
        self.path = os.path.abspath(path or DEFAULT_PATH)
        with open(self.path, "rb") as f:
            raw = f.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ControlPointError("主表不是合法 JSON：%s" % e)
        if not isinstance(data, dict):
            raise ControlPointError("主表顶层必须是对象")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ControlPointError("schema_version=%r，期望 %r"
                                    % (data.get("schema_version"), SCHEMA_VERSION))
        tv = data.get("table_version")
        if not isinstance(tv, str) or not tv:
            raise ControlPointError("table_version 缺失或为空")
        cps = data.get("control_points")
        if not isinstance(cps, list) or not cps:
            raise ControlPointError("control_points 必须是非空数组")

        self._by_code = {}
        for cp in cps:
            if not isinstance(cp, dict):
                raise ControlPointError("control_points 里出现非对象")
            code = cp.get("control_code")
            if not isinstance(code, str) or not code:
                raise ControlPointError("control_code 缺失或非字符串")
            if code in self._by_code:
                raise ControlPointError("control_code 重复：%r" % code)
            self._by_code[code] = cp
        self.table_version = tv
        self.schema_version = data.get("schema_version")

    def active_codes(self):
        return frozenset(c for c, cp in self._by_code.items()
                         if cp.get("status") == "active")

    def get_active(self, code):
        """返回 active 控制点；未知 / 非 active 一律抛异常。"""
        cp = self._by_code.get(code)
        if cp is None:
            raise UnknownControlCode("未知 control_code：%r" % (code,))
        status = cp.get("status")
        if status != "active":
            raise DeprecatedControlCode(
                "control_code %r 不可用于判定（status=%r）" % (code, status))
        return dict(cp)


# ═══════════════ 控制点数量的口径（C-78 / SEC-5-33）═══════════════
#
# ★ 这一段存在的理由：**控制点数量的分母只有一个来源 —— 主表。**
#
#   `分类确认` 那张汇报表有 12 个一级、58 个二级条目。它不是控制点计数：
#   它是另一套分类，粒度不同、归属不同、且**权威清单至今没落盘**
#   （`research/governance/README.md` 明写「58 子类清单待补」）。
#
#   拿 58 当分母会得到什么：一个「已检查 58/58」的读数，而主表里只有 20 个控制点。
#   分子分母取自两套不同的东西，比率没有意义，但**它看起来像个比率** ——
#   这正是 K-02 的形状：数字读得出、算得出、没有任何东西会红。

# 报告里表示「控制点总数」的键 → 它该等于主表的哪个读数
MASTER_COUNT_KEYS = {
    "control_points_total": "total",     # 含 deprecated（主表全量）
    "control_points_active": "active",   # 只算 active
}

# 报告可以出现的子类统计键（**只做展示，永不做分母**）
SUBCLASS_COUNT_KEY = "subclass_counts"

# 分母来源里，哪些是「拿子类当控制点口径」——一律报警
SUBCLASS_DENOMINATOR_SOURCES = frozenset({
    "subclass", "subclass_count", "subclasses", "58", "58_subclasses",
})


def master_count(doc) -> dict:
    """
    主表条数口径。返回 `{"total": n, "active": m}`。

    ★ `total` 是**全量**（含 deprecated）。停用码不从表里消失（L6-2b），
      所以它当然算在「这张表有多少条」里；但「有多少条能用」是 active。
      两个数分开给，不许让调用方自己猜该用哪个。
    """
    rows = (doc or {}).get("control_points")
    if not isinstance(rows, list):
        return {"total": None, "active": None}
    return {
        "total": len(rows),
        "active": sum(1 for r in rows
                      if isinstance(r, dict) and r.get("status") == "active"),
    }


def control_point_denominator_problems(report, cp_doc) -> list:
    """
    报告里的控制点口径与主表对不对得上。**返回问题清单，空 = 没问题。**

    三条判据，各自独立：

      ① 报告声明了 `control_points_total` / `control_points_active`
         → 必须等于主表的 `total` / `active`
      ② 任何指标的分母来源是子类（`subclass` / `58` …）
         → **报警**（不是「按子类还是按主表都行」，是子类不许当分母）
      ③ 报告带了 `subclass_counts` 且**有数据**
         → 其和必须等于主表总数；**没数据时不判**（不许无中生有地报警）

    ★ 第 ③ 条的正样本很关键：绝大多数报告不带子类统计。
      如果「没有子类数据」也报警，这个检查器会天天红，然后没人看它。
      （§2.1.1：一个会误报的检查器比没有检查器更糟。）
    """
    problems = []
    if not isinstance(report, dict):
        return ["报告不是对象"]

    master = master_count(cp_doc)
    if master["total"] is None:
        # 主表读不出 —— 这不是「没问题」，是判不了
        return ["主表读不出 control_points，无法判定数量口径"]

    # ① 声明的总数必须等于主表
    for key, which in MASTER_COUNT_KEYS.items():
        if key not in report:
            continue
        want = master[which]
        got = report.get(key)
        if got != want:
            problems.append(
                f"{key}={got!r}，主表 {which}={want} —— 数量口径不是主表")

    # ② 分母来源：子类一律报警
    denoms = report.get("denominators")
    if isinstance(denoms, dict):
        for metric, src in denoms.items():
            if isinstance(src, str) and src.strip().lower() in SUBCLASS_DENOMINATOR_SOURCES:
                problems.append(
                    f"指标 {metric!r} 用 {src!r} 当分母 —— 控制点口径只能是主表")

    # ③ 子类统计只在**有数据时**才判
    subs = report.get(SUBCLASS_COUNT_KEY)
    if isinstance(subs, dict) and subs:
        vals = [v for v in subs.values() if isinstance(v, int)]
        if len(vals) != len(subs):
            problems.append(f"{SUBCLASS_COUNT_KEY} 里有非整数计数 —— 数不出来")
        elif sum(vals) != master["total"]:
            problems.append(
                f"{SUBCLASS_COUNT_KEY} 之和={sum(vals)}，主表 total={master['total']} "
                f"—— 两套口径不一致（子类只是展示，不得冒充控制点数）")

    return problems

    def get_active(self, code):
        """返回 active 控制点；未知 / 非 active 一律抛异常。"""
        cp = self._by_code.get(code)
        if cp is None:
            raise UnknownControlCode("未知 control_code：%r" % (code,))
        status = cp.get("status")
        if status != "active":
            raise DeprecatedControlCode(
                "control_code %r 不可用于判定（status=%r）" % (code, status))
        return dict(cp)


if __name__ == "__main__":
    reg = ControlPointRegistry()
    print("table_version=%s active=%d" % (reg.table_version, len(reg.active_codes())))
