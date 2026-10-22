#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_verify_acceptance_run.py — T0-10 执行器的自测

只读验收表；反向对照使用临时表，不写真实验收表。
退出码：0 全过 / 1 有红。
"""

import os
import re
import subprocess
import sys
import tempfile
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
RUNNER = os.path.join(REPO_ROOT, "tools", "verify_acceptance_run.py")
REAL_TABLE = os.path.join(
    REPO_ROOT, "PMO", "audit",
    "验收表-v3-覆盖全部判据-20261017.md")

try:
    import base.sandbox as sb
    from base.sandbox import run_untrusted
except Exception:  # noqa: BLE001
    sb = None
    run_untrusted = None


def _run(table):
    proc = subprocess.run(
        [sys.executable, RUNNER, "--table", table],
        capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _make_table(method):
    f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    f.write("| # | 验收动作 | 覆盖判据 | 怎么验 | 可验性 |\n")
    f.write("|---|---|---|---|---|\n")
    f.write("| 1 | fake | X | %s | machine |\n" % method)
    f.close()
    return f.name


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    # 真实表：断言的是**执行器的三态语义**，不是某一时刻的快照。
    #
    # ★ 2026-10-23 改（T-141 同批）。原文要求 `rc==2` 且 `failed==0`，
    #   那是 #78 还绿着时的读数。自那一刻起 #78 被裁定 dormant
    #   （它要求「引用了未确认条款 → unknowns 要有 Q45」，而 62 条全改 ratified
    #   之后触发条件永不成立），于是这条断言**一直在红**——而它红了很久没人管，
    #   因为 `tools/test_*.py` 既不在验证器名册里，也没有任何触发点会跑它。
    #
    #   改成断言三态语义本身：计数之和必须是总行数、退出码必须与计数一致。
    #   这样 #78 转绿时它照样成立，别的行新红时它也照样成立。
    #   **一个把某天读数写死的断言，会在那天之后一直骗人。**
    rc, real_out = _run(REAL_TABLE)
    mm = re.search(r"mapped=(\d+)", real_out)
    mp = re.search(r"passed=(\d+) failed=(\d+) untested=(\d+)", real_out)
    if mm and mp:
        n_passed, n_failed, n_untested = (int(mp.group(i)) for i in (1, 2, 3))
        total = n_passed + n_failed + n_untested
        # 三态退出码的约定（本文件 docstring 第一句）：0 过 / 1 有红 / 2 未测
        want_rc = 1 if n_failed else (2 if n_untested else 0)
        ok_real = (rc == want_rc and int(mm.group(1)) > 0 and total == 136)
        detail = ("rc=%s want=%s passed=%d failed=%d untested=%d total=%d"
                  % (rc, want_rc, n_passed, n_failed, n_untested, total))
    else:
        ok_real = False
        detail = "rc=%s 解析不出 mapped/passed（out 尾部 %r）" % (rc, out[-200:])
    report(ok_real, "真实表 → 三态语义自洽（计数之和=136、rc 与计数一致）", detail)

    # 反向对照 1：test_id + fixture + command true → passed=1 rc=0
    fixture = tempfile.NamedTemporaryFile(delete=False)
    fixture.write(b"x")
    fixture.close()
    t1 = _make_table("test_id: T-1; fixture: %s; command: true" % fixture.name)
    rc, out = _run(t1)
    report(rc == 0 and "passed=1 failed=0 untested=0" in out,
           "command true → passed=1 rc=0", "rc=%s out=%s" % (rc, out[-200:]))

    # 反向对照 2：command false → failed=1 rc=1
    t2 = _make_table("test_id: T-2; fixture: %s; command: false" % fixture.name)
    rc, out = _run(t2)
    report(rc == 1 and "passed=0 failed=1 untested=0" in out,
           "command false → failed=1 rc=1", "rc=%s out=%s" % (rc, out[-200:]))

    # 反向对照 3：fixture 不存在 → untested rc=2
    t3 = _make_table("test_id: T-3; fixture: /tmp/__no_such_fixture__; command: true")
    rc, out = _run(t3)
    report(rc == 2 and "passed=0 failed=0 untested=1" in out,
           "fixture 不存在 → untested rc=2", "rc=%s out=%s" % (rc, out[-200:]))

    # T0-10b：命令写相对文件 → 必须在沙箱 cwd 内，不得落到仓库
    probe = os.path.join(REPO_ROOT, "t0_10b_probe.txt")
    if os.path.exists(probe):
        os.unlink(probe)
    write_cmd = "python3 -c \"open('t0_10b_probe.txt','w').write('x')\""
    t4 = _make_table("test_id: T-4; fixture: %s; command: %s" % (fixture.name, write_cmd))
    rc, out = _run(t4)
    report(rc == 0 and "passed=1 failed=0 untested=0" in out and not os.path.exists(probe),
           "命令写相对文件 → 仓内不得出现", "rc=%s out=%s exists=%s" % (
               rc, out[-200:], os.path.exists(probe)))
    if os.path.exists(probe):
        os.unlink(probe)

    # R-cwd：测试注入 cwd=仓库 → 仓内出现（证明隔离有效，生产函数无 bad_mode）
    if run_untrusted is not None and sb is not None:
        code = ("import subprocess,sys\n"
                "sys.exit(subprocess.call(%r, shell=True))" % write_cmd)
        real_popen = sb._popen

        def repo_cwd(*args, **kwargs):
            kwargs["cwd"] = REPO_ROOT
            return real_popen(*args, **kwargs)

        with mock.patch.object(sb, "_popen", repo_cwd):
            r = run_untrusted(code, timeout=10, cpu_seconds=5)
        report(r["ok"] and os.path.exists(probe),
               "R-cwd 去掉 cwd 隔离 → 仓内出现（反向对照成立）", repr(r))
        if os.path.exists(probe):
            os.unlink(probe)
    else:
        report(False, "R-cwd 无法导入 base.sandbox", "")

    # T-141（2026-10-23）：失败必须带现场。
    #   改前 run_row 只返回 `exit=%s`，把 run_untrusted 已经拿到的
    #   stdout/stderr 全丢了 —— `#135` 偶发红过一次，全文只有「exit=1」，
    #   三个人各查一遍仍然没有结论。
    #   判据是行为级：子进程打一个独有标记再 exit 1，标记必须出现在 detail 里。
    #   ★ 标记脚本写进独立文件，不写成 `python3 -c "..."`：
    #     parse_table 的 RE_COMMAND 以 `;` 为结束符，内联脚本会被截断
    #     （实测过，第一次就踩了）。
    MARK = "T141-DIAG-MARKER-%d" % os.getpid()
    marker_py = tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8")
    marker_py.write("import sys\nprint(%r, file=sys.stderr)\nsys.exit(1)\n" % MARK)
    marker_py.close()
    t5 = _make_table("test_id: T-5; fixture: %s; command: python3 %s"
                     % (fixture.name, marker_py.name))
    rc, out = _run(t5)
    report(rc == 1 and MARK in out,
           "T-141 失败时必须带子进程 stderr（标记可见）",
           "rc=%s marker_found=%s out=%s" % (rc, MARK in out, out[-400:]))

    # T-141 反向对照：通过的行不许被塞进无关输出（否则「带现场」= 一律打印）
    t6 = _make_table("test_id: T-6; fixture: %s; command: true" % fixture.name)
    rc, out = _run(t6)
    report(rc == 0 and "passed=1 failed=0 untested=0" in out,
           "T-141 反向对照：通过的行 detail 为空", "rc=%s out=%s" % (rc, out[-200:]))

    # T-143（2026-10-23）：`untested=N` 必须配口径 —— N 不是一个东西。
    #   表里有 7 条的可验性列写着 manual（「不作为执行验收项 / 按人工验收」），
    #   它们**永远不会有** machine 执行点；另外 17 条是 machine、执行点待建。
    #   两者下一步动作相反，却共用一个读数。执行器必须分开报。
    split = re.search(
        r"untested_split: machine=(\d+) manual=(\d+) unverifiable=(\d+) unknown=(\d+)",
        real_out)
    total_split = sum(int(split.group(i)) for i in (1, 2, 3, 4)) if split else -1
    n_untested = int(mp.group(3)) if mp else -1
    report(split is not None and total_split == n_untested,
           "T-143 untested 分两本账且分项之和 == untested",
           "split=%r total_split=%s untested=%s"
           % (split.group(0) if split else None, total_split, n_untested))

    # 反向对照：manual 与 machine 的**分界必须来自表里的那一列**，不是常量。
    #   造一张只有 manual 行的表 → machine 必须是 0。
    t7 = _make_table("test_id: T-7; fixture: %s; command: true" % fixture.name)
    # 把可验性列改成 manual
    _txt = open(t7, encoding="utf-8").read().replace("| machine |", "| manual |")
    with open(t7, "w", encoding="utf-8") as _f:
        _f.write(_txt)
    rc, out7 = _run(t7)
    s7 = re.search(r"untested_split: machine=(\d+) manual=(\d+)", out7)
    report(rc == 0 and s7 is not None and s7.group(1) == "0",
           "T-143 反向对照：manual 行不计入 machine 账",
           "rc=%s split=%r out=%s" % (rc, s7.group(0) if s7 else None, out7[-200:]))

    for p in (t1, t2, t3, t4, t5, t6, t7, fixture.name, marker_py.name):
        try:
            os.unlink(p)
        except OSError:
            pass

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
