#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_verify_acceptance_run.py — T0-10 执行器的自测

只读验收表；反向对照使用临时表，不写真实验收表。
退出码：0 全过 / 1 有红。
"""

import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
RUNNER = os.path.join(REPO_ROOT, "tools", "verify_acceptance_run.py")
REAL_TABLE = os.path.join(
    REPO_ROOT, "PMO", "audit",
    "验收表-v3-覆盖全部判据-20261017.md")

try:
    from base.sandbox import run_untrusted
except Exception:  # noqa: BLE001
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

    # 真实表：0 passed / 0 failed / 136 untested，rc=2
    rc, out = _run(REAL_TABLE)
    report(rc == 2 and "passed=0 failed=0 untested=136" in out,
           "真实表 → 0/0/136 untested，rc=2", "rc=%s out=%s" % (rc, out[-200:]))

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

    # R-cwd：去掉 cwd 隔离 → 仓内出现（证明隔离有效）
    if run_untrusted is not None:
        code = ("import subprocess,sys\n"
                "sys.exit(subprocess.call(%r, shell=True))" % write_cmd)
        r = run_untrusted(code, timeout=10, cpu_seconds=5, bad_mode="no_cwd")
        report(r["ok"] and os.path.exists(probe),
               "R-cwd 去掉 cwd 隔离 → 仓内出现（反向对照成立）", repr(r))
        if os.path.exists(probe):
            os.unlink(probe)
    else:
        report(False, "R-cwd 无法导入 base.sandbox", "")

    for p in (t1, t2, t3, t4, fixture.name):
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
