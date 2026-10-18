#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/sandbox.py — T0-08b：不可信输入沙箱（G-5）

在受限子进程中运行不可信解析代码：
- 独立 cwd（临时目录）+ 清空环境（仅白名单）；
- 绝对路径读取守卫：只允许仓内、workdir、临时目录与解释器路径；
  `/etc`、`~/.ssh` 等仓外绝对路径直接拒绝；
- RLIMIT_CPU / RLIMIT_FSIZE / RLIMIT_AS；
- 墙钟超时；子进程在独立进程组中，超时/越界后杀**整个进程组**，回收孙进程；
- 子进程内禁用 socket（含 `_socket` 底层模块）；
- 返回 {ok, exit_code, stdout, stderr, timed_out, limit_hit, memory_limit_mode,
  memory_limit_untested, memory_limit_note}。

★ 已知残余（明着留，不假装是 OS 级安全边界）：
  1. 网络禁用与路径守卫是 Python 层（monkeypatch / audit hook）。子进程、
     原生扩展、已打开的 fd 仍可绕过 —— 真正隔离要靠容器/命名空间。
  2. 内存限制优先 `RLIMIT_AS`；本机 macOS 实测不可设置时降级为进程内 RSS
     轮询，并显式标 `memory_limit_untested=True`（未测 ≠ 通过）。
  3. `limit_hit` 只认返回码/信号：CPU=SIGXCPU、FSIZE=退出码 71、内存=退出码 70。
     不再根据 stderr 字符串猜测。
"""

import json
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
import _socket, json, os, resource, socket, sys, threading, time

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

_ALLOWED_ROOTS = []
try:
    _ALLOWED_ROOTS = json.loads(os.environ.get("SANDBOX_ALLOW_ROOTS", "[]"))
except ValueError:
    _ALLOWED_ROOTS = []

def _path_allowed(target):
    try:
        p = os.path.abspath(os.fsdecode(target))
    except Exception:
        return True
    for root in _ALLOWED_ROOTS:
        r = os.path.abspath(str(root))
        if p == r or p.startswith(r.rstrip(os.sep) + os.sep):
            return True
    return False

def _audit(event, args):
    if event != "open" or not args:
        return
    target = args[0]
    if isinstance(target, (str, bytes)) and os.path.isabs(os.fsdecode(target)):
        if not _path_allowed(target):
            raise PermissionError("sandbox_path_denied: " + os.fsdecode(target))

try:
    sys.addaudithook(_audit)
except Exception:
    pass

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


def _popen(args, **kwargs):
    """测试注入点：默认 Popen；反向对照可替换 cwd。"""
    return subprocess.Popen(args, **kwargs)


def _communicate(proc, timeout):
    """测试注入点：默认 communicate；反向对照可去掉 timeout。"""
    return proc.communicate(timeout=timeout)


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

        allow_roots = [
            workdir, REPO_ROOT, tempfile.gettempdir(),
            sys.prefix, sys.base_prefix, os.path.dirname(sys.executable),
        ]
        allow_roots += [os.path.abspath(p) for p in sys.path if p]
        # macOS 的 /var 与 /private/var 是同一路径：两边的写法都要放行。
        allow_roots += [os.path.realpath(p) for p in allow_roots]
        allow_roots = list(dict.fromkeys(allow_roots))
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "TMPDIR": workdir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "SANDBOX_MEMORY_BYTES": str(memory_bytes),
            "SANDBOX_ALLOW_ROOTS": json.dumps(allow_roots),
        }

        def _limits():
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE,
                               (file_size_bytes, file_size_bytes))
            mode = "none"
            if memory_bytes and memory_bytes > 0:
                try:
                    resource.setrlimit(resource.RLIMIT_AS,
                                       (memory_bytes, memory_bytes))
                    mode = "rlimit_as"
                except (ValueError, OSError):
                    # macOS：不可设置 —— 不静默吞掉，落盘降级方式。
                    mode = "rss_watch"
            try:
                with open(mode_path, "w", encoding="utf-8") as f:
                    f.write(mode)
            except OSError:
                pass

        proc = None
        timed_out = False
        stdout = ""
        stderr = ""
        rc = None
        try:
            proc = _popen(
                [sys.executable, "-B", runner_path, user_path],
                cwd=workdir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, preexec_fn=_limits, start_new_session=True,
            )
            try:
                stdout, stderr = _communicate(proc, timeout)
                timed_out = False
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    stdout, stderr = _communicate(proc, 2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = _communicate(proc, None)
                rc = None
        except subprocess.SubprocessError as exc:
            timed_out = False
            stdout = ""
            stderr = "sandbox_pre_exec_failed: %s" % exc
            rc = None
        finally:
            # 即使直接子进程已退出，也要回收同进程组里的孙进程。
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        try:
            with open(mode_path, encoding="utf-8") as f:
                memory_limit_mode = f.read().strip() or "unknown"
        except OSError:
            memory_limit_mode = "unknown"

        memory_limit_untested = memory_limit_mode != "rlimit_as"
        if memory_limit_mode == "rlimit_as":
            memory_limit_note = "RLIMIT_AS 已生效"
        elif memory_limit_mode == "rss_watch":
            memory_limit_note = (
                "未测：RLIMIT_AS 在本机不可设置；已降级为进程内 RSS 轮询 best-effort")
        else:
            memory_limit_note = "未测：未设置内存上限"

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
            "memory_limit_untested": memory_limit_untested,
            "memory_limit_note": memory_limit_note,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
