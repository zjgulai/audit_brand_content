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


if __name__ == "__main__":
    reg = ControlPointRegistry()
    print("table_version=%s active=%d" % (reg.table_version, len(reg.active_codes())))
