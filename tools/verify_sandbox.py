#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_sandbox.py — T0-08：不可信输入沙箱（G-5）

覆盖：
  C0 正常样本 → ok，退出 0
  C1 CPU rlimit：死循环 → limit_hit（与普通失败可区分）
  C2 墙钟超时：长跑 → timed_out
  C3 cwd 隔离：样本打印的 cwd 必须在临时目录，不在仓库
  C4 网络禁用：socket 连接 → 失败，且不是 limit/timeout
  C5 文件大小 rlimit：写大文件 → limit_hit
  C6 普通失败：SystemExit(3) → exit=3，limit_hit=False，timed_out=False
  R1 去掉 CPU 限制 → 死循环不再 limit_hit（而是 timed_out）
  R2 去掉超时 → 长跑样本返回 ok（反向对照成立）
  R3 去掉 cwd 隔离 → cwd 落在仓库（反向对照成立）
  R4 正常样本必须绿（防“全拦”）

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.sandbox import run_untrusted
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.sandbox: %s" % exc)
    sys.exit(2)


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

    # C0 正常样本
    r = run_untrusted("print('ok')", timeout=5, cpu_seconds=2)
    report(r["ok"] and r["exit_code"] == 0, "C0 正常样本 → ok", repr(r))

    # C1 CPU 限制
    r = run_untrusted("while True:\n    pass\n", timeout=5, cpu_seconds=1)
    report(r["limit_hit"] is True and r["ok"] is False,
           "C1 死循环 → limit_hit", repr(r))

    # C2 墙钟超时
    r = run_untrusted("import time\ntime.sleep(1)\nprint('done')", timeout=0.3, cpu_seconds=2)
    report(r["timed_out"] is True and r["ok"] is False,
           "C2 长跑 → timed_out", repr(r))

    # C3 cwd 隔离
    r = run_untrusted("import os\nprint(os.path.abspath('.'))", timeout=5, cpu_seconds=2)
    out = (r["stdout"] or "").strip()
    report(r["ok"] and out and REPO_ROOT not in out and out.startswith("/"),
           "C3 样本 cwd 不在仓库", "out=%r" % out)

    # C4 网络禁用
    r = run_untrusted(
        "import socket\nsocket.create_connection(('example.com', 80), timeout=1)\n",
        timeout=5, cpu_seconds=2)
    report(r["ok"] is False and r["limit_hit"] is False and r["timed_out"] is False
           and "network_disabled" in (r["stderr"] or ""),
           "C4 网络访问 → 失败（network_disabled）", repr(r))

    # C5 文件大小限制
    r = run_untrusted(
        "open('big.bin','wb').write(b'x'*(2*1024*1024))\nprint('written')",
        timeout=5, cpu_seconds=2, file_size_bytes=1024*1024)
    report(r["limit_hit"] is True and r["ok"] is False,
           "C5 超文件大小 → limit_hit", repr(r))

    # C6 普通失败与 limit/timeout 可区分
    r = run_untrusted("raise SystemExit(3)", timeout=5, cpu_seconds=2)
    report(r["exit_code"] == 3 and r["limit_hit"] is False and r["timed_out"] is False
           and r["ok"] is False,
           "C6 普通失败 exit=3（非 limit/timeout）", repr(r))

    # R1 去掉 CPU 限制 → 死循环不 limit_hit（由墙钟超时兜底）
    r = run_untrusted("while True:\n    pass\n", timeout=2, cpu_seconds=1,
                      bad_mode="no_cpu")
    report(r["limit_hit"] is False and r["timed_out"] is True,
           "R1 去掉 CPU 限制 → 不再 limit_hit（反向对照成立）", repr(r))

    # R2 去掉超时 → 长跑样本返回 ok
    r = run_untrusted("import time\ntime.sleep(1)\nprint('done')", timeout=0.3,
                      cpu_seconds=2, bad_mode="no_timeout")
    report(r["ok"] is True and r["timed_out"] is False,
           "R2 去掉超时 → 长跑返回 ok（反向对照成立）", repr(r))

    # R3 去掉 cwd 隔离 → cwd 落在仓库
    r = run_untrusted("import os\nprint(os.path.abspath('.'))", timeout=5,
                      cpu_seconds=2, bad_mode="no_cwd")
    out = (r["stdout"] or "").strip()
    report(r["ok"] and out and out.startswith(REPO_ROOT),
           "R3 去掉 cwd 隔离 → cwd 落在仓库（反向对照成立）", "out=%r" % out)

    # R4 正常样本必须绿（防全拦）
    report(run_untrusted("print('still-ok')", timeout=5, cpu_seconds=2)["ok"] is True,
           "R4 正常样本必须绿（防全拦）", "")

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
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
