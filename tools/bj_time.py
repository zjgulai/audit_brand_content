#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北京时间的「今天」—— **全仓唯一来源**。

本项目所有到期日、承诺期限和「今天是否逾期」都按 **Asia/Shanghai（UTC+8）**
理解。此前各脚本各写一份：

* `tools/kb_gaps.py` 用 `date.today()`（本机时区）
* `tools/verify_pending.py` 自己定义 `bj_today()`
* `tools/kb_gap_ledger.py` 自己定义 `today_bj()`
* `research/kb/load.py` 自己定义 `CST` 与 `today()`
* `tools/verify_open_items.py` / `tools/verify_control_points.py` 用 `date.today()`

本机恰好是 `+08:00` 时它们读数一样，**但那是运气，不是设计**：换一台机器、
把 `TZ` 设成 `UTC` 或跨日运行时，两个检查器就可能对「今天」给出不同答案。
所以「今天」只允许从这个文件取。

用法：

    python3 tools/bj_time.py --selftest
    python3 tools/bj_time.py --probe      # 给 selftest 的子进程用，打印当前读数

`--selftest` 做两件事：
  ① AST 扫 `tools/`、`research/kb/`、`base/` 里的「取今天/取现在」调用点，
     除本文件外**一个都不许有**；每个命中都打印 path:line。
  ② 在 `TZ=UTC`、`TZ=Pacific/Kiritimati`、`TZ=Etc/GMT+12` 下各起一个子进程，
     断言所有消费者读到的都是**同一个北京日期**（不是各自的本机日期）。
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

BJ = timezone(timedelta(hours=8))


def bj_now() -> datetime:
    """北京时间的当前时刻（带 +08:00 时区）。"""
    return datetime.now(BJ)


def bj_today() -> date:
    """北京时间的日历日。**所有「今天」都从这里取。**"""
    return bj_now().date()


def bj_today_iso() -> str:
    """北京时间的日历日，`YYYY-MM-DD`。"""
    return bj_today().isoformat()


# ─────────────────────────── 自证 ───────────────────────────

#: 这些模块里出现「取今天/取现在」的本地实现，就是口径分裂。
_SCAN_DIRS = ("tools", "research/kb", "base")


def _import_aliases(tree):
    """收集 `import datetime as X` / `from datetime import date, datetime` 的别名。"""
    mods, dates, dts = {"datetime"}, {"date"}, {"datetime"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "datetime":
                    mods.add(a.asname or "datetime")
        elif isinstance(n, ast.ImportFrom) and n.module == "datetime":
            for a in n.names:
                if a.name == "date":
                    dates.add(a.asname or "date")
                elif a.name == "datetime":
                    dts.add(a.asname or "datetime")
    # `import datetime as _dt` 之后，`_dt.date` / `_dt.datetime` 也是入口。
    dates |= mods
    dts |= mods
    return mods, dates, dts


def _is_chain(node, root_names, attr):
    """`X.attr` 或 `X.datetime.attr` 形状。"""
    if not isinstance(node, ast.Attribute) or node.attr != attr:
        return False
    v = node.value
    if isinstance(v, ast.Name):
        return v.id in root_names
    if isinstance(v, ast.Attribute) and v.attr in ("datetime", "date"):
        return isinstance(v.value, ast.Name) and v.value.id in root_names
    return False


def _local_now_sites(path):
    """返回这个文件里「取今天/取现在」的 [(line, 描述)]。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    mods, dates, dts = _import_aliases(tree)
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if _is_chain(f, dates, "today"):
            out.append((n.lineno, "date.today()"))
        elif _is_chain(f, dts, "now"):
            # 显式传了时区的 `now(UTC+8)` / `now(timezone.utc)` 是**时刻读数**，
            # 不是「本机今天」；只有裸 `now()` 或 `now(None)` 才是口径分裂。
            explicit_tz = bool(n.args) and not (
                isinstance(n.args[0], ast.Constant) and n.args[0].value is None)
            explicit_tz = explicit_tz or any(k.arg == "tz" for k in n.keywords)
            if not explicit_tz:
                out.append((n.lineno, "datetime.now()（本机时区）"))
        elif _is_chain(f, dts, "utcnow"):
            out.append((n.lineno, "datetime.utcnow()"))
        elif _is_chain(f, dts, "today"):
            out.append((n.lineno, "datetime.today()"))
    return out


def _scan_sites():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    me = os.path.abspath(__file__)
    bad = []
    for d in _SCAN_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in
                           {"__pycache__", "node_modules", ".git"}]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dirpath, fn)
                for line, what in _local_now_sites(pathlib_path(p)):
                    if os.path.abspath(p) != me:
                        bad.append((os.path.relpath(p, root), line, what))
    return bad


def pathlib_path(p):
    """延迟导入 pathlib，保持 selftest 的依赖只有标准库。"""
    from pathlib import Path
    return Path(p)


def _consumer_readings():
    """导入所有消费者，返回 {名字: 北京日期字符串}。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(root, "tools"), os.path.join(root, "research", "kb"), root):
        if p not in sys.path:
            sys.path.insert(0, p)
    import bj_time
    import verify_pending
    import kb_gaps
    import kb_gap_ledger
    import kb_backfill
    import verify_control_points
    import verify_open_items
    import verify_prd_baseline
    import load
    from base import takedown, notifications

    # 函数对象同一性：不是「文本里出现」，而是导入后真的是同一个函数。
    same = {
        "verify_pending.bj_today": verify_pending.bj_today is bj_time.bj_today,
        "kb_gaps.bj_today": getattr(kb_gaps, "bj_today", None) is bj_time.bj_today,
        "kb_gap_ledger.bj_today": getattr(kb_gap_ledger, "bj_today", None) is bj_time.bj_today,
        "kb_backfill.bj_today": getattr(kb_backfill, "bj_today", None) is bj_time.bj_today,
        "verify_control_points.bj_today": getattr(verify_control_points, "bj_today", None) is bj_time.bj_today,
        "verify_open_items.bj_today": getattr(verify_open_items, "bj_today", None) is bj_time.bj_today,
        "verify_prd_baseline.bj_now": getattr(verify_prd_baseline, "bj_now", None) is bj_time.bj_now,
        "load.bj_today": getattr(load, "bj_today", None) is bj_time.bj_today,
        "base.takedown.bj_today": getattr(takedown, "bj_today", None) is bj_time.bj_today,
        "base.notifications.bj_today": getattr(notifications, "bj_today", None) is bj_time.bj_today,
    }
    readings = {
        "bj_time": bj_time.bj_today_iso(),
        "verify_pending": verify_pending.bj_today().isoformat(),
        "kb_gaps": kb_gaps.bj_today().isoformat(),
        "kb_gap_ledger": kb_gap_ledger.today_bj(),
        "kb_backfill": kb_backfill.bj_today().isoformat(),
        "verify_control_points": verify_control_points.bj_today().isoformat(),
        "verify_open_items": verify_open_items.bj_today().isoformat(),
        "load": load.today(),
        "base.takedown.bj_date": takedown.bj_date(),
        "base.notifications.bj_date": notifications.bj_date(),
    }
    return same, readings


def _probe():
    _, readings = _consumer_readings()
    print(json.dumps(readings, ensure_ascii=False, sort_keys=True))


def _selftest() -> int:
    bad = _scan_sites()
    print("=== 本地取「今天/现在」的调用点 ===")
    if bad:
        for p, line, what in bad:
            print(f"  ❌ {p}:{line}  {what}")
    else:
        print("  ✅ 除 tools/bj_time.py 外，0 处本地取今天/现在")

    same, readings = _consumer_readings()
    print("\n=== 消费者与唯一来源同一性 ===")
    for k, ok in same.items():
        print(f"  {'✅' if ok else '❌'} {k}")
    print("\n=== 同一进程内读数 ===")
    for k, v in readings.items():
        print(f"  {k}: {v}")

    ok = not bad and all(same.values())
    want = readings["bj_time"]
    for tz in ("UTC", "Pacific/Kiritimati", "Etc/GMT+12"):
        env = os.environ.copy()
        env["TZ"] = tz
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--probe"],
                           env=env, capture_output=True, text=True)
        print(f"\n=== TZ={tz} 子进程（rc={p.returncode}）===")
        if p.returncode != 0:
            print((p.stderr or p.stdout)[-500:])
            ok = False
            continue
        try:
            got = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as e:
            print(f"  ❌ 读不出：{e}；{p.stdout[-300:]}")
            ok = False
            continue
        diff = {k: v for k, v in got.items() if v != want}
        if diff:
            print(f"  ❌ 与北京日期 {want} 不一致：{diff}")
            ok = False
        else:
            print(f"  ✅ 全部 = {want}（不随本机 TZ 变）")

    print("\n" + ("✅ 全过：唯一来源成立，且 TZ 不改变读数"
                  if ok else "❌ 有红：仍然存在本地日期口径"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--probe" in sys.argv:
        _probe()
        sys.exit(0)
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
    sys.exit(0)
