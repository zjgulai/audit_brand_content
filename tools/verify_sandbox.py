#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_sandbox.py — T0-08：不可信输入沙箱（G-5）

覆盖：
  C0 正常样本 → ok，退出 0
  C1 CPU rlimit：死循环 → limit_hit（SIGXCPU）
  C2 墙钟超时：长跑 → timed_out
  C3 cwd 隔离：样本打印的 cwd 必须在临时目录，不在仓库
  C4 网络禁用：socket 连接 → 失败，且不是 limit/timeout
  C5 文件大小 rlimit：写大文件 → limit_hit（SIGXFSZ）
  C6 普通失败：SystemExit(3) → exit=3，limit_hit=False，timed_out=False
  C7 内存限制：超限 → 专用退出码 70 或信号，limit_hit=True
  C8 stderr 伪造：打印 "MemoryError" 等但正常退出 → limit_hit 必须为 False
  C9 `_socket` 底层绕过：必须同样被 network_disabled 挡住
  R1 去掉 CPU 限制 → 死循环不再 limit_hit（而是 timed_out，测试注入）
  R2 去掉超时 → 长跑样本返回 ok（反向对照，测试注入）
  R3 去掉 cwd 隔离 → cwd 落在仓库（反向对照，测试注入）
  R4 正常样本必须绿（防“全拦”）

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    import base.sandbox as sb
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
    report(r["limit_hit"] is True and r["ok"] is False and r["exit_code"] == 71,
           "C5 超文件大小 → limit_hit（返回码 71）", repr(r))

    # C6 普通失败与 limit/timeout 可区分
    r = run_untrusted("raise SystemExit(3)", timeout=5, cpu_seconds=2)
    report(r["exit_code"] == 3 and r["limit_hit"] is False and r["timed_out"] is False
           and r["ok"] is False,
           "C6 普通失败 exit=3（非 limit/timeout）", repr(r))

    # C7 内存限制：本机若 RLIMIT_AS 不可设，走 RSS 轮询降级
    mem_code = (
        "import time\n"
        "chunks = []\n"
        "for _ in range(100):\n"
        "    chunks.append(bytearray(4 * 1024 * 1024))\n"
        "    time.sleep(0.01)\n"
        "print('allocated')\n")
    r = run_untrusted(mem_code, timeout=10, cpu_seconds=5,
                      memory_bytes=64 * 1024 * 1024)
    report(r["limit_hit"] is True and r["ok"] is False
           and r["exit_code"] in (70, -9)
           and r["memory_limit_mode"] in ("rlimit_as", "rss_watch"),
           "C7 超内存 → limit_hit（返回码 70/信号）", repr(r))

    # C8 stderr 字符串不得参与 limit_hit 判定
    r = run_untrusted(
        "import sys\n"
        "sys.stderr.write('MemoryError\\nFile too large\\nCannot allocate memory\\n')\n"
        "raise SystemExit(1)\n",
        timeout=5, cpu_seconds=2)
    report(r["limit_hit"] is False and r["exit_code"] == 1,
           "C8 伪造 stderr → 不得判 limit_hit", repr(r))

    # C9 `_socket` 底层绕过必须被挡
    r = run_untrusted(
        "import _socket\n_socket.socket()\n",
        timeout=5, cpu_seconds=2)
    report(r["ok"] is False and r["limit_hit"] is False
           and "network_disabled" in (r["stderr"] or ""),
           "C9 `_socket` 绕过 → 失败（network_disabled）", repr(r))

    # R1 去掉 CPU 限制 → 死循环不 limit_hit（由墙钟超时兜底）
    real_setrlimit = sb.resource.setrlimit

    def no_cpu(which, limits):
        if which == sb.resource.RLIMIT_CPU:
            return None
        return real_setrlimit(which, limits)

    with mock.patch.object(sb.resource, "setrlimit", no_cpu):
        r = run_untrusted("while True:\n    pass\n", timeout=2, cpu_seconds=1)
    report(r["limit_hit"] is False and r["timed_out"] is True,
           "R1 去掉 CPU 限制 → 不再 limit_hit（反向对照成立）", repr(r))

    # R2 去掉超时 → 长跑样本返回 ok
    real_run = sb.subprocess.run

    def no_timeout(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_run(*args, **kwargs)

    with mock.patch.object(sb.subprocess, "run", no_timeout):
        r = run_untrusted("import time\ntime.sleep(1)\nprint('done')",
                          timeout=0.3, cpu_seconds=2)
    report(r["ok"] is True and r["timed_out"] is False,
           "R2 去掉超时 → 长跑返回 ok（反向对照成立）", repr(r))

    # R3 去掉 cwd 隔离 → cwd 落在仓库
    def repo_cwd(*args, **kwargs):
        kwargs["cwd"] = REPO_ROOT
        return real_run(*args, **kwargs)

    with mock.patch.object(sb.subprocess, "run", repo_cwd):
        r = run_untrusted("import os\nprint(os.path.abspath('.'))",
                          timeout=5, cpu_seconds=2)
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
