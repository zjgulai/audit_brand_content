#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/sandbox.py — T0-08：不可信输入沙箱（G-5）

在受限子进程中运行不可信解析代码：
- 独立 cwd（临时目录）+ 清空环境（仅白名单）；
- RLIMIT_CPU / RLIMIT_AS / RLIMIT_FSIZE；
- 墙钟超时；
- 子进程内禁用 socket（network_disabled）；
- 返回 {ok, exit_code, stdout, stderr, timed_out, limit_hit}，超限与普通失败可区分。

本模块只负责运行与隔离；不判内容、不做业务授权。
"""

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_RUNNER = r'''
import socket, sys

def _blocked(*args, **kwargs):
    raise RuntimeError("network_disabled")

socket.socket = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked

with open(sys.argv[1], "rb") as f:
    code = compile(f.read(), sys.argv[1], "exec")
exec(code, {"__name__": "__main__"})
'''

_LIMIT_SIGNALS = {signal.SIGXCPU, signal.SIGXFSZ, signal.SIGKILL}


def run_untrusted(code, timeout=5.0, cpu_seconds=1,
                  memory_bytes=512 * 1024 * 1024,
                  file_size_bytes=1024 * 1024,
                  no_network=True, bad_mode=None):
    """运行不可信代码；bad_mode 仅供反向对照（no_cpu/no_timeout/no_cwd）。"""
    workdir = tempfile.mkdtemp(prefix="sandbox-")
    try:
        user_path = os.path.join(workdir, "user_code.py")
        runner_path = os.path.join(workdir, "runner.py")
        with open(user_path, "w", encoding="utf-8") as f:
            f.write(code)
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(_RUNNER if no_network else _RUNNER.replace(
                "socket.socket = _blocked\nsocket.create_connection = _blocked\n"
                "socket.getaddrinfo = _blocked\n", ""))

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "TMPDIR": workdir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        cwd = REPO_ROOT if bad_mode == "no_cwd" else workdir

        def _limits():
            if bad_mode != "no_cpu":
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
            try:
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            except (ValueError, OSError):
                pass

        kwargs = {
            "cwd": cwd,
            "env": env,
            "capture_output": True,
            "text": True,
            "preexec_fn": _limits,
        }
        if bad_mode != "no_timeout":
            kwargs["timeout"] = timeout

        try:
            proc = subprocess.run(
                [sys.executable, "-B", runner_path, user_path], **kwargs)
            timed_out = False
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            rc = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            rc = None

        limit_hit = bool(rc is not None and rc < 0 and (-rc) in _LIMIT_SIGNALS)
        if not limit_hit:
            low = (stderr or "")
            if ("MemoryError" in low or "File too large" in low
                    or "Cannot allocate memory" in low):
                limit_hit = True
        ok = (rc == 0 and not timed_out and not limit_hit)
        return {
            "ok": ok,
            "exit_code": rc,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "limit_hit": limit_hit,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
