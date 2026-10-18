#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/sandbox.py — T0-08：不可信输入沙箱（G-5）

在受限子进程中运行不可信解析代码：
- 独立 cwd（临时目录）+ 清空环境（仅白名单）；
- RLIMIT_CPU / RLIMIT_FSIZE / RLIMIT_AS；
- 墙钟超时；
- 子进程内禁用 socket（含 `_socket` 底层模块）；
- 返回 {ok, exit_code, stdout, stderr, timed_out, limit_hit, memory_limit_mode}，
  超限与普通失败可区分。

★ 已知残余（明着留，不假装是 OS 级安全边界）：
  1. 网络禁用是 Python 层 monkeypatch（`socket` / `_socket`）。子进程、原生扩展、
     已打开的 fd 仍可绕过 —— 真正的网络隔离要靠容器/网络命名空间。
  2. 内存限制优先 `RLIMIT_AS`；本机 macOS 实测 `setrlimit(RLIMIT_AS)` 抛
     `ValueError: current limit exceeds maximum limit`，此时降级为**进程内 RSS 轮询**
     （`ru_maxrss`，5ms 一次，超限 `os._exit(70)`）。同进程的不可信代码可以杀掉线程
     或伪造读数，所以这只是 best-effort，不是安全边界。
  3. `limit_hit` 只认**返回码/信号**：CPU=SIGXCPU、FSIZE=退出码 71（macOS 实测是
     `OSError(EFBIG)` 而不是 SIGXFSZ）、内存=退出码 70。
     不再根据 stderr 字符串猜测（那可以被用户代码一行 print 伪造）。

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

_MEMORY_EXIT = 70
_FSIZE_EXIT = 71
_LIMIT_EXITS = {_MEMORY_EXIT, _FSIZE_EXIT}
_LIMIT_SIGNALS = {signal.SIGXCPU, signal.SIGXFSZ, signal.SIGKILL}

_NETWORK_BLOCK = (
    "socket.socket = _blocked\n"
    "socket.create_connection = _blocked\n"
    "socket.getaddrinfo = _blocked\n"
    "_socket.socket = _blocked\n"
)

_RUNNER = r'''
import _socket, os, resource, socket, sys, threading, time

def _blocked(*args, **kwargs):
    raise RuntimeError("network_disabled")

__NETWORK_BLOCK__

def _rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024

def _watch_memory(cap):
    while True:
        try:
            if _rss_bytes() > cap:
                os._exit(70)
        except Exception:
            return
        time.sleep(0.005)

_mode = "none"
try:
    with open("memlimit.mode", encoding="utf-8") as f:
        _mode = f.read().strip()
except OSError:
    pass
if _mode == "rss_watch":
    _cap = int(os.environ.get("SANDBOX_MEMORY_BYTES", "0") or "0")
    if _cap > 0:
        threading.Thread(target=_watch_memory, args=(_cap,), daemon=True).start()

with open(sys.argv[1], "rb") as f:
    code = compile(f.read(), sys.argv[1], "exec")
try:
    exec(code, {"__name__": "__main__"})
except MemoryError:
    os._exit(70)
except OSError as exc:
    if getattr(exc, "errno", None) == 27:  # EFBIG
        os._exit(71)
    raise
'''


def run_untrusted(code, timeout=5.0, cpu_seconds=1,
                  memory_bytes=512 * 1024 * 1024,
                  file_size_bytes=1024 * 1024,
                  no_network=True):
    """运行不可信代码；返回值含超限/超时/内存限制方式的读数。"""
    workdir = tempfile.mkdtemp(prefix="sandbox-")
    try:
        user_path = os.path.join(workdir, "user_code.py")
        runner_path = os.path.join(workdir, "runner.py")
        mode_path = os.path.join(workdir, "memlimit.mode")
        with open(user_path, "w", encoding="utf-8") as f:
            f.write(code)
        runner = _RUNNER.replace(
            "__NETWORK_BLOCK__", _NETWORK_BLOCK if no_network else "")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(runner)

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "TMPDIR": workdir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "SANDBOX_MEMORY_BYTES": str(memory_bytes),
        }

        def _limits():
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
            mode = "none"
            if memory_bytes and memory_bytes > 0:
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
                    mode = "rlimit_as"
                except (ValueError, OSError):
                    # macOS：RLIMIT_AS 可能不可设置 —— 不静默吞掉，落盘降级方式。
                    mode = "rss_watch"
            try:
                with open(mode_path, "w", encoding="utf-8") as f:
                    f.write(mode)
            except OSError:
                pass

        kwargs = {
            "cwd": workdir,
            "env": env,
            "capture_output": True,
            "text": True,
            "preexec_fn": _limits,
            "timeout": timeout,
        }

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
        except subprocess.SubprocessError as exc:
            timed_out = False
            stdout = ""
            stderr = "sandbox_pre_exec_failed: %s" % exc
            rc = None

        try:
            with open(mode_path, encoding="utf-8") as f:
                memory_limit_mode = f.read().strip() or "unknown"
        except OSError:
            memory_limit_mode = "unknown"

        # 只认返回码/信号；stderr 字符串可以被用户代码伪造。
        limit_hit = bool(
            rc in _LIMIT_EXITS
            or (rc is not None and rc < 0 and (-rc) in _LIMIT_SIGNALS))
        ok = (rc == 0 and not timed_out and not limit_hit)
        return {
            "ok": ok,
            "exit_code": rc,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "limit_hit": limit_hit,
            "memory_limit_mode": memory_limit_mode,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
