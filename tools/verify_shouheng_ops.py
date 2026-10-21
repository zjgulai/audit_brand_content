#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_shouheng_ops.py —— 守衡的运维面自证：**它为什么还活着？**

本项目已有的自证都在验「内容对不对」（引擎契约、知识库、卡片模版、上游基线），
**没有一条在验「守衡本身还是活的、而且重启它不会把它弄死」**。这一条补的是这个洞。

2026-09-21 一天里在这个面上撞到三件事，三件都属于本项目反复出现的那个形状
（看起来正常，其实没人跑了 / 读数比输入大）：

  1. `kill -TERM` 会让守衡**永久静默**。实测（同款 KeepAlive 的临时 launchd 作业）：
     exit 0 → 只跑 1 次就再也不拉；exit 1 → 9 秒内被拉起 5 次。
     而 ws_daemon.mjs 收到 SIGTERM 走 process.exit(0)。→ A/C 段。
  2. 重启闸门自己崩了：`$PID，` 在 macOS 自带 bash 3.2 上被吃成变量名 PID\\xef。
     → F 段。
  3. 闸门第一版报「重启会让 tools/restart_shouheng.sh 生效」—— 而守护进程根本
     不 import 它。**读数比输入大**（§2.4.1）。→ B 段。

退出码：0 全绿 / 1 有红 / **2 = 守衡没在跑（未测，不是通过）**。
"""
import datetime
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "tools" / "restart_shouheng.sh"
# 「同意凭证」的临时落点 —— 自证只碰这个，**永不碰真的那一份**（见 run_gate 的注释）。
CONSENT_TMP = Path(tempfile.mkdtemp(prefix="shouheng-consent-")) / "consent"
LEDGER = ROOT / "PMO" / "logs" / "restart-ledger.jsonl"
DAEMON_LOG = ROOT / "PMO" / "logs" / "ws_daemon.log"
PLIST_REPO = ROOT / "tools" / "com.shouheng.lark.plist"
PLIST_LIVE = Path.home() / "Library" / "LaunchAgents" / "com.shouheng.lark.plist"
LABEL = "com.shouheng.lark"

results = []   # (id, ok, msg)
untested = []  # (id, msg) —— 采不到的读数。**既不是通过，也不是红。**


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    return bool(ok)


def cannot_test(cid, msg):
    """采不到证据时用它，不要用另外两种写法。

    * `check(cid, True, ...)` = 把「没测」说成「没问题」（§2.4.2 明令禁止）；
    * `check(cid, False, ...)` = 把「没测」冤枉成「它坏了」—— 会让人去修一个没坏的东西
      （§2.4.1 第 5 行就是这么发生的：一条 09-16 的旧读数被当成今天的墙）。

    两者都是让结论比输入大。未测必须与通过与红**都长得不一样**。
    """
    untested.append((cid, msg))


def verdict(n_fail, up, n_untested):
    """把结论行拆成纯函数，好让 H 段能直接断言「这句话不许撒谎」。

    返回值 `(退出码, 结论文)`。四种退出码语义互不相同：

    | 码 | 含义 | 它**不**代表 |
    |---:|---|---|
    | 0 | 全部断言过，且守衡在跑 | —— |
    | 1 | 有断言变红（我这侧确实坏了） | —— |
    | 2 | **未测**：守衡没在跑，或有读数采不到 | **不等于通过**，也不等于断言失败 |
    """
    if not up:
        tail = f"（另有 {n_fail} 项红，见上表）" if n_fail else ""
        return 2, f"⚠ 守衡没在跑 —— 这不是通过，是未测（退 2，与 §2.4.2 同口径）{tail}"
    if n_fail:
        # 有红的时候更要把未测说出来：只看最后一行的人会以为「红的就这 3 项，其余都验过了」。
        tail = f"；另有 {n_untested} 项未测（见 ⚠ 行）" if n_untested else ""
        return 1, f"❌ {n_fail} 项红{tail}"
    if n_untested:
        return 2, f"⚠ {n_untested} 项未测 —— 这不是通过（退 2，与 §2.4.2 同口径）"
    return 0, "✅ 全过"


def run_gate(*args, consent=None):
    """
    跑闸门。**默认把「同意凭证」指到临时文件**（§2.4.4：自证不许改真状态）。

    不指走的话，A1 那一次「不带 --yes」的报告就会往真路径上写一份真凭证 ——
    而那份凭证在 5 分钟内是**能放行一次真重启的**。那不是「无害的残留」，
    那是「跑一次自证就给闸门留了一把钥匙」。
    """
    env = dict(os.environ)
    env["SHOUHENG_RESTART_CONSENT"] = str(consent or CONSENT_TMP)
    p = subprocess.run(["bash", str(GATE), *args], capture_output=True, text=True,
                       timeout=120, env=env)
    return p.returncode, p.stdout + p.stderr


def run_sandbox_gate(gate, env, *args):
    p = subprocess.run(["bash", str(gate), *args], capture_output=True, text=True,
                       timeout=120, env=env)
    return p.returncode, p.stdout + p.stderr


def make_sandbox_gate(*, remove_rescue_why=False):
    """把闸门复制到临时目录，用假的 launchctl/pgrep **强制 rescue 分支**。

    为什么 A6 不直接跑真闸门：2026-10-21 修前实测过，守衡没在跑时
    `--yes` 会真的 kickstart（rescue 分支漏了 --why 与 --no-kick）。
    自证不能因为闸门回归而重启生产进程（§2.4.4）。副本与源文件逐字节相同，
    只是 PATH 里换了 launchctl/pgrep；它测的是同一段代码。
    """
    src = GATE.read_text(encoding="utf-8")
    if remove_rescue_why:
        block = '''  if [ -z "$WHY" ]; then
    echo "  ✗ 拒绝救活：--yes 必须配 --why=\\"<理由>\\" —— 救活也要留痕，理由就是痕迹。"
    exit "$EXIT_REFUSED"
  fi
'''
        if block not in src:
            return None
        src = src.replace(block, "", 1)
    d = Path(tempfile.mkdtemp(prefix="shouheng-gate-"))
    (d / "tools").mkdir()
    (d / "PMO" / "logs").mkdir(parents=True)
    (d / "PMO" / "shouheng-state").mkdir(parents=True)
    gate = d / "tools" / "restart_shouheng.sh"
    gate.write_text(src, encoding="utf-8")
    bin_dir = d / "bin"
    bin_dir.mkdir()
    marker = d / "kick"
    # ★ 2026-10-22 补：`bootout` 必须有**自己的**探针。
    #   原先这里只有一个 `$MARKER`，而且只有 `kickstart` 写它 —— 于是
    #   「S4 的标记没被写」对 `--stop` 那条路**恒真**：`--stop` 走的是 `bootout`，
    #   永远不碰 `MARKER`。一个在它要测的那条路上恒真的断言，等于没测。
    #   这与 S4 原本要防的形状（§2.4：名字出现过 ≠ 它拦得住）是同一个 ——
    #   只不过那次长在判据里，这次长在**测试夹具**里。
    boot_marker = d / "boot"
    launch = ('#!/bin/bash\n'
              'if [ "$1" = "print" ]; then exit 1; fi\n'
              'if [ "$1" = "kickstart" ]; then echo x >> "$MARKER"; exit 0; fi\n'
              'if [ "$1" = "bootout" ]; then echo x >> "$BOOT_MARKER"; exit 0; fi\n'
              'exit 1\n')
    pgrep = '#!/bin/bash\nexit 1\n'
    (bin_dir / "launchctl").write_text(launch, encoding="utf-8")
    (bin_dir / "pgrep").write_text(pgrep, encoding="utf-8")
    for f in (bin_dir / "launchctl", bin_dir / "pgrep"):
        f.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["MARKER"] = str(marker)
    env["BOOT_MARKER"] = str(boot_marker)
    env["SHOUHENG_RESTART_CONSENT"] = str(CONSENT_TMP)
    return gate, env, marker, boot_marker


def daemon_pid():
    p = subprocess.run(["pgrep", "-f", r"ws_daemon\.mjs"], capture_output=True, text=True)
    return p.stdout.split()[0] if p.stdout.strip() else ""


# ── E 段用的读数：**全部不依赖 ps**（2026-09-22 加）────────────────────────
#
# 原先「它还在跑吗」读的是 `ps -o etime= -p <pid>`，而 `ps` 在受限环境里会被拒
# （`Operation not permitted`），于是 E1 永远落「未测」、整个自证退 2。
# **这是选型错误，不是环境限制**：
#   · 这个进程的生命周期由 launchd 的 KeepAlive 决定（§2.7）—— 权威在 launchd，ps 只是旁观者；
#   · 「活着」有两层：①进程存在 ②事件循环还在转。ps 只答①，而②要靠心跳。
# 下面三条读数都不需要 ps，且各自能被反向对照喂坏样本（`judge_liveness` 是纯函数）。
BEAT_MAX_MIN = 12          # 心跳每 5 分钟一次；超过这个数 = 在跑但可能卡住
RUN_STATE = ROOT / "PMO" / "shouheng-state" / "daemon-run.json"


def read_launchd():
    """launchd 怎么认为。回 `(state, pid, note)`；读不到 → `(None, None, 原因)`。"""
    try:
        p = subprocess.run(["launchctl", "print", "gui/%d/%s" % (os.getuid(), LABEL)],
                           capture_output=True, text=True)
    except (PermissionError, OSError) as e:
        return None, None, "跑不了 launchctl（%s: %s）" % (type(e).__name__, e)
    if p.returncode != 0:
        return None, None, "launchctl print 退 %d（作业没加载？）" % p.returncode
    m = re.search(r"^\s*state\s*=\s*(\S+)", p.stdout, re.M)
    n = re.search(r"^\s*pid\s*=\s*(\d+)", p.stdout, re.M)
    return (m.group(1) if m else None), (n.group(1) if n else None), "launchctl print 读到"


def pgrep_pids():
    """`pgrep -f ws_daemon.mjs` 的 pid 列表。**`None` = 跑不了 pgrep**（≠ 空列表）。"""
    try:
        p = subprocess.run(["pgrep", "-f", r"ws_daemon\.mjs"], capture_output=True, text=True)
    except (PermissionError, OSError):
        return None
    return p.stdout.split()


def kill_probe(pid):
    """存活探测：`os.kill(pid, 0)`。**系统调用，不需要 ps。**"""
    if not pid:
        return "nopid"
    try:
        os.kill(int(pid), 0)
        return "ok"
    except ProcessLookupError:
        return "ESRCH"          # 进程不存在 → 真的没在跑
    except PermissionError:
        return "EPERM"          # 权限受限，但**进程存在** —— 也是「活着」的证据
    except Exception:
        return "error"


def _iso_epoch(s):
    return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def uptime_minutes(pid):
    """「运行了多久」+ **这个数是从哪来的**。回 `(分钟, 来源)`；没来源 → `(None, 原因)`。

    ⚠️ 退到重启台账时有一条**必须**核对的恒等式：台账那条的 `pid_after` 要等于**现在这个 pid**。
    不核它就等于把「上一次重启的时刻」当成「这个进程的启动时刻」—— 而 launchd 的
    KeepAlive 自愈重启**不会进台账**，那时这两个数不是一回事。
    """
    now = time.time()
    try:
        d = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        if str(d.get("pid")) == str(pid) and d.get("startedAt"):
            return (now - _iso_epoch(d["startedAt"])) / 60.0, "run-state.startedAt"
    except Exception:
        pass
    try:
        recs = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
        for r in reversed(recs):
            if r.get("ok") and str(r.get("pid_after")) == str(pid) and r.get("at"):
                return (now - _iso_epoch(r["at"])) / 60.0, "重启台账最后一条（pid_after 对得上）"
    except Exception:
        pass
    return None, "没来源（run-state 未部署，且台账里没有 pid_after=%s 的记录）" % (pid or "?")


def beat_age_minutes():
    """最后一次心跳距今多少分钟 + 来源。优先 run-state（结构化），退日志 mtime。"""
    now = time.time()
    try:
        d = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        if d.get("lastBeatAt"):
            return (now - _iso_epoch(d["lastBeatAt"])) / 60.0, "run-state.lastBeatAt"
    except Exception:
        pass
    if DAEMON_LOG.exists():
        return (now - DAEMON_LOG.stat().st_mtime) / 60.0, "日志 mtime（run-state 尚未部署）"
    return None, "两处都读不到"


def judge_liveness(launchd_state, pid, pgrep_list, kill_result, beat_age_min):
    """纯函数：五个读数 → `(结论, 一句说明)`。结论只有四种，**四种不许长一样**：

    | 结论 | 含义 | 对应退出码 |
    |---|---|---|
    | `up` | 在跑，且事件循环还在转 | 通过 |
    | `down` | 真的没在跑 | 红（1） |
    | `stuck` | 进程在，但心跳过期 —— 卡住了 | 红（1） |
    | `untested` | 一个读数都没采到 | 未测（2） |

    拆成纯函数是为了让反向对照**直接喂坏样本**（§2.1：反向对照只在内存里做）——
    否则要验「进程死了它会红」，就得真去杀那个正在替我们答话的进程。
    """
    if kill_result == "ESRCH":
        return "down", "os.kill(pid,0) 报 ESRCH —— 进程不存在（pid=%s）" % (pid or "?")
    if pid and pgrep_list is not None and str(pid) not in [str(x) for x in pgrep_list]:
        return "down", ("pid %s 不在 `pgrep -f ws_daemon.mjs` 的结果里 —— "
                        "活着的那个进程**不是守护进程**" % pid)
    if launchd_state and launchd_state != "running":
        return "down", "launchd 说 state=%s —— 它没在跑" % launchd_state
    if beat_age_min is not None and beat_age_min > BEAT_MAX_MIN:
        return "stuck", ("最后一次心跳在 %.0f 分钟前（> %d 分钟）—— 进程在，但事件循环卡住了"
                         % (beat_age_min, BEAT_MAX_MIN))
    if not pid:
        return "untested", "既没读到 launchd 的 pid，也没读到 pgrep 的结果 —— 【未测】，不等于「没在跑」"
    why = "pid=%s 存活" % pid
    why = ("launchd state=running，" + why) if launchd_state == "running" else (why + "（launchd 那一格未测）")
    if beat_age_min is not None:
        why += "；最后一次心跳 %.0f 分钟前" % beat_age_min
    return "up", why


# ── 绕过闸门的写法：只扫**可执行代码**，不扫文档（文档里提它不是错） ──────────
BYPASS = [
    (r"launchctl\s+kickstart", "直接 kickstart"),
    (r"launchctl\s+(bootout|unload|stop)\b", "把守衡卸下/停掉"),
    (r"pkill\s+-f\s+[^\n]*ws_daemon", "pkill 守护进程"),
    (r"\bkill\b[^\n]*ws_daemon", "kill 守护进程"),
]
# 白名单只有两处，且各有理由：
#   闸门自己 —— 它就是唯一该 kickstart 的地方；
#   本文件   —— 它必须写出这些模式才能测它们（下面 C2 就是拿它们喂自己）。
ALLOWED_CODE = {"tools/restart_shouheng.sh", "tools/verify_shouheng_ops.py"}


def _code_lines(text):
    """两个扫描器共用一条读法：**整行注释不算代码**。

    第一版只给 bash 陷阱那个扫描器跳了注释，于是同一个仓库里躺着两套规则
    （一个说注释会报、一个说不报），读的人会记混。统一成一套。

    **已知的共同盲区**：行尾注释（`echo ok  # launchctl kickstart`）仍会被扫到。
    为了消这点噪去写 quote-aware 的解析器不值得 —— 宁可偶尔吵一句。
    """
    return [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if not ln.lstrip().startswith("#")]


def scan_bypass(text):
    return [why for i, ln in _code_lines(text) for rx, why in BYPASS if re.search(rx, ln)]


def scan_bash_trap(text):
    """$VAR 后面直接跟非 ASCII —— macOS 自带 bash 3.2 会把多字节字符的首字节
    吃进变量名（`$EVENTS）` 被当成变量 EVENTS\\xef），报一句莫名其妙的
    unbound variable。凡是变量后面直接跟中文，必须写成 ${VAR}。"""
    hits = []
    for i, line in _code_lines(text):
        for m in TRAP.finditer(line):
            if m.group(0).startswith("${"):
                continue
            hits.append((i, m.group(1), line.strip()[:70]))
    return hits


def code_files():
    out = []
    for pat in ("tools/**/*.sh", "tools/**/*.mjs", "tools/**/*.py", "*.sh"):
        for p in ROOT.glob(pat):
            if "node_modules" in p.parts:
                continue
            out.append(p)
    return sorted(set(out))


# ── bash 3.2 多字节陷阱：$VAR 后面直接跟非 ASCII ──────────────────────────
TRAP = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?(?=[^\x00-\x7F])")


def scan_bash_trap(text):
    """$VAR 后面直接跟非 ASCII —— macOS 自带 bash 3.2 会把多字节字符的首字节
    吃进变量名（`$EVENTS）` 被当成变量 EVENTS\\xef），报一句莫名其妙的
    unbound variable。凡是变量后面直接跟中文，必须写成 ${VAR}。"""
    hits = []
    for i, line in _code_lines(text):
        for m in TRAP.finditer(line):
            if m.group(0).startswith("${"):
                continue
            hits.append((i, m.group(1), line.strip()[:70]))
    return hits


print("=" * 74)
print("守衡运维面自证 · 它为什么还活着")
print("=" * 74)

PIDS = pgrep_pids()                 # None = 跑不了 pgrep（≠ 空列表 = 真的没有）
PID = PIDS[0] if PIDS else ""
UP = bool(PIDS)

# ── A 闸门会拒绝 ────────────────────────────────────────────────────────
print("\nA 闸门会拒绝（默认不改动任何东西）")
ledger_before = LEDGER.read_text(encoding="utf-8").count("\n") if LEDGER.exists() else 0
rc, out = run_gate()
check("A1", rc == 3, f"不带 --yes → 退出码 {rc}（应 3）")
check("A2", "拒绝重启" in out or "确认救活" in out, "拒绝时说明了原因与下一步")
pid_after = daemon_pid()
check("A3", pid_after == PID, f"拒绝时没动进程（{PID or '无'} → {pid_after or '无'}）")
ledger_after = LEDGER.read_text(encoding="utf-8").count("\n") if LEDGER.exists() else 0
check("A4", ledger_after == ledger_before, f"拒绝时没记账（{ledger_before} → {ledger_after} 行）")
rc, _ = run_gate("--check")
check("A5", rc == 0, f"--check → 退出码 {rc}（应 0，纯查看）")
# A6：救活分支也必须要求 --why。**不跑真闸门** —— 修前它会在 rescue 分支
# 直接 kickstart；自证不能重启生产进程（§2.4.4）。副本与源文件逐字节相同。
sb = make_sandbox_gate()
if sb is None:
    check("A6", False, "沙箱副本建不出来")
else:
    gate_s, env_s, marker_s, boot_s = sb
    rc, out = run_sandbox_gate(gate_s, env_s, "--yes", "--no-kick")
    check("A6", rc == 3 and "why" in out and not marker_s.exists(),
          f"--yes 不给理由 → 退出码 {rc}（应 3，救活/重启都必须留痕）")

    # A6b：反向对照 —— 带 --why + --no-kick 必须放行且**不 kickstart**
    rc, out = run_sandbox_gate(gate_s, env_s, "--yes", "--why=selftest", "--no-kick")
    check("A6b", rc == 0 and "--no-kick" in out and not marker_s.exists(),
          f"救活分支 --no-kick → 退出码 {rc}（应 0，进程未动）")

    # ── S1–S4  `--stop`：闸门必须也盖住「停」 ────────────────────────────
    # ★ 2026-10-22 真事故：委托方要求「先别往外发」，而唯一的停法是直接在 bash 里
    #   `launchctl bootout` —— **绕过了闸门**，也没留痕。C1 没红只因那句不在仓库代码里。
    #   停与起是同一种对外动作（群里从此没人答话，且不会有任何东西记下来），
    #   所以它必须走同一套 --yes / --why / 留痕。
    rc, out = run_sandbox_gate(gate_s, env_s, "--stop", "--check")
    check("S1", rc == 0 and "未做任何动作" in out and not marker_s.exists(),
          f"--stop --check → 退出码 {rc}（应 0，纯查看、不动进程）")

    rc, out = run_sandbox_gate(gate_s, env_s, "--stop")
    check("S2", rc == 3 and not marker_s.exists(),
          f"--stop 不给 --yes → 退出码 {rc}（应 3，停也要显式确认）")

    rc, out = run_sandbox_gate(gate_s, env_s, "--stop", "--yes")
    check("S3", rc == 3 and "why" in out and not marker_s.exists(),
          f"--stop --yes 不给理由 → 退出码 {rc}（应 3，停也要留痕）")

    # S4：反向对照 —— 带 --why + --no-kick 必须放行且**不 bootout**。
    # 判据不是「rc==0」，而是「rc==0 **且** bootout 探针没被写」—— 只查退出码的话，
    # 一个根本没走到 bootout 的实现也会绿（§2.4：名字出现过 ≠ 它拦得住）。
    # ★ 探针必须是 `BOOT_MARKER` 而不是 `MARKER`：`--stop` 走 bootout，
    #   永远不碰 kickstart 的那个 MARKER，拿它当判据会恒真。
    rc, out = run_sandbox_gate(gate_s, env_s, "--stop", "--yes", "--why=selftest", "--no-kick")
    check("S4", rc == 0 and "--no-kick" in out
          and not marker_s.exists() and not boot_s.exists(),
          f"--stop --no-kick → 退出码 {rc}（应 0，进程未动）")

    # S4r：反向对照 —— 去掉 --no-kick 时必须**真的写到** BOOT_MARKER。
    # 没有这一条，S4 的「探针没被写」就可能是**探针根本不会响**（夹具坏了），
    # 而不是实现正确。两者在 S4 里长得一模一样 —— 这正是 §2.1.1 那个形状。
    rc, out = run_sandbox_gate(gate_s, env_s, "--stop", "--yes", "--why=selftest")
    check("S4r", boot_s.exists(),
          f"不带 --no-kick → bootout 探针 {'已' if boot_s.exists() else '未'}触发"
          f"（应已触发，否则 S4 恒真）")

    # A6r：反向对照 —— 删掉 rescue 的 --why 检查，A6 必须红（不是空转）
    sb_r = make_sandbox_gate(remove_rescue_why=True)
    if sb_r is None:
        check("A6r", False, "反向对照的副本建不出来（源码里找不到 rescue 的 --why 块）")
    else:
        gate_r, env_r, marker_r, _boot_r = sb_r
        rc, out = run_sandbox_gate(gate_r, env_r, "--yes", "--no-kick")
        check("A6r", not (rc == 3 and "why" in out) and not marker_r.exists(),
              f"删掉 rescue 的 --why 检查 → A6 条件不再成立（rc={rc}，未 kickstart）")

# ── A7–A14 「同意」有保质期：读数与执行必须落在同一次对话里 ──────────────
#    ★ 2026-09-22 真事故：17:54 读的读数，17:55 **别人**重启了一次，18:03 我拿旧读数
#      去执行 —— 闸门当场打了「重启会生效 无」而我没有重读，于是白重启一次。
#      代价是运气好（0 条消息丢），不是设计上安全。
#    这一组就是把那次事故变成**能红的执行点**：缺凭证/过期/PID 变了/读数变了，四条各一。
print("\nA7–A14 「同意」的保质期（读数与执行不同一个调用 → 必须拒）")


def write_consent(path, at=None, pid=None, digest=None):
    path.write_text(f"at={at if at is not None else int(time.time())}\n"
                    f"pid={pid if pid is not None else (PID or 'none')}\n"
                    f"digest={digest if digest is not None else 'x'}\n", encoding="utf-8")


# A7 / A8–A11 只在**重启分支**可测。守衡没在跑时它们会落到 rescue 分支，
# 而 §2.7 的例外条款明确「救活不必等人同意」—— 此时它们不是红，是**不适用**。
# 未测必须与红、通过都长得不一样（cannot_test）。
if UP:
    # A7：**没有凭证** → 拒（这是「没先读就执行」）
    CONSENT_TMP.unlink(missing_ok=True)
    rc, out = run_gate("--yes", "--why=selftest", "--no-kick")
    check("A7", rc == 3 and "没有凭证" in out, f"没先读就执行 → 退出码 {rc}（应 3）")

# A13：**反向对照** —— A7 不是恒真：先跑一次报告，凭证必须真的被写下
# （rescue 分支也会写；它测的是「凭证块在分支之前」，不依赖重启分支）
rc, out = run_gate()
check("A13", CONSENT_TMP.exists(), "不带 --yes 那一次**应当**写下凭证（否则 A7 恒真）")

if UP:
    # A8：★ **反向对照** —— 新鲜且对得上的凭证**不许**被拒（否则闸门成了砖头，§2.1.1）
    pid_before = daemon_pid()
    rc, out = run_gate("--yes", "--why=selftest", "--no-kick")
    check("A8", rc == 0 and "凭证有效" in out, f"新鲜且匹配的凭证 → 退出码 {rc}（应 0，不许误报）")
    check("A14", daemon_pid() == pid_before, f"--no-kick 一个进程都不许动（{pid_before} → {daemon_pid()}）")

    # A9：凭证**过期** → 拒
    write_consent(CONSENT_TMP, at=int(time.time()) - 600)
    rc, out = run_gate("--yes", "--why=selftest", "--no-kick")
    check("A9", rc == 3 and "过期" in out, f"凭证过期 → 退出码 {rc}（应 3）")

    # A10：**PID 对不上** → 拒（= 那次事故的直接判据：这中间有一次别人的重启）
    write_consent(CONSENT_TMP, pid="99999")
    rc, out = run_gate("--yes", "--why=selftest", "--no-kick")
    check("A10", rc == 3 and "PID 对不上" in out, f"PID 变了 → 退出码 {rc}（应 3）")

    # A11：同一 PID、但**读数摘要变了** → 拒
    write_consent(CONSENT_TMP, digest="0" * 64)
    rc, out = run_gate("--yes", "--why=selftest", "--no-kick")
    check("A11", rc == 3 and "读数对不上" in out, f"摘要变了 → 退出码 {rc}（应 3）")
else:
    cannot_test("A7–A11", "守衡没在跑 → 重启分支的凭证校验无法实测（不是红）")

# A12：**`--check` 是纯查看，一个字节都不许落**
CONSENT_TMP.unlink(missing_ok=True)
run_gate("--check")
check("A12", not CONSENT_TMP.exists(), "--check 不许写凭证（它说的是「纯查看」）")

# ── B 那块读数必须会动 ──────────────────────────────────────────────────
print("\nB 「重启会生效」不是恒真的读数（§2.4.1：读数不许比输入大）")


def changed_modules(out):
    mods, inside = [], False
    for line in out.splitlines():
        if "重启会生效" in line:
            inside = True
            continue
        if inside:
            if line.startswith("  ─"):
                break
            t = line.strip()
            if t.startswith("tools/") and t.endswith(".mjs"):
                mods.append(t)
    return mods


def spawned_scripts(out):
    """闸门「另（spawn）」那一段列出的脚本（2026-09-21 新增那段读数）。"""
    mods, inside = [], False
    for line in out.splitlines():
        if "另（spawn）" in line:
            inside = True
            continue
        if inside:
            if line.startswith("  ─"):
                break
            t = line.strip()
            if t.startswith("tools/") and t.endswith(".py"):
                mods.append(t)
    return mods


rc, out = run_gate("--check", "--since=0")
mods_all = changed_modules(out)
check("B1", rc == 0 and "tools/ws_daemon.mjs" in mods_all and len(mods_all) >= 5,
      f"--since=0 → 列出 import 图 {len(mods_all)} 个模块（读得出来）")
rc, out = run_gate("--check", "--since=9999999999")
mods_none = changed_modules(out)
check("B2", rc == 0 and not mods_none and "无" in out,
      f"--since=未来 → 空（{len(mods_none)} 个），读数确实按时间过滤")
check("B3", not scan_bypass("find tools -newer ref"), "闸门不再用「改过的文件都算生效」那种粗读法")

# 第二段读数：**被 spawn 的脚本**（2026-09-21 补，因为上一版只报 import 表，
# `tools/verify_pending.py` 这种「靠重启才会开始被调用」的文件在报告里看不见）
rc, out = run_gate("--check", "--since=0")
sp_all = spawned_scripts(out)
check("B4", rc == 0 and "tools/verify_pending.py" in sp_all and len(sp_all) >= 2,
      f"--since=0 → 列出被 spawn 的脚本 {len(sp_all)} 个（含本轮新加的 verify_pending.py）")
rc, out = run_gate("--check", "--since=9999999999")
check("B5", rc == 0 and not spawned_scripts(out),
      "反向对照：spawn 那段也必须按时间过滤，不是一张常量表")
rc, out = run_gate("--check", "--since=0")
check("B6", rc == 0 and "tools/restart_shouheng.sh" not in changed_modules(out) + spawned_scripts(out),
      "★ 闸门自己不许出现在任何一张表里（它是既不 import 也不被 spawn 的 —— 这就是 §2.7 记的那个老错）")

# ── C 不许绕过闸门 ──────────────────────────────────────────────────────
print("\nC 绕过闸门的写法（全仓可执行代码）")
offenders = []
for f in code_files():
    rel = str(f.relative_to(ROOT))
    if rel in ALLOWED_CODE:
        continue
    for why in scan_bypass(f.read_text(encoding="utf-8", errors="replace")):
        offenders.append(f"{rel}: {why}")
check("C1", not offenders, f"除闸门与自证外，无人直接操作守护进程（{len(offenders)} 处）")
for o in offenders[:6]:
    print(f"      ✗ {o}")
# 反向对照：喂已知坏样本，扫描器必须红（在内存里做，不碰盘 —— §2.1）
fake = '#!/bin/bash\nlaunchctl kickstart -k gui/501/com.shouheng.lark\n'
check("C2", len(scan_bypass(fake)) == 1, "反向对照：喂一段 kickstart，扫描器报出 1 处")
fake2 = '#!/bin/bash\npkill -f ws_daemon.mjs\n'
check("C3", len(scan_bypass(fake2)) == 1, "反向对照：喂一段 pkill，扫描器报出 1 处")
check("C4", not scan_bypass('# 用 launchctl kickstart -k 重启\n'),
      "反向对照：整行注释里提它 → 不报（注释不可能被执行）")
check("C5", len(scan_bypass('echo ok  # launchctl kickstart\n')) == 1,
      "已知盲区（与 F 共用）：行尾注释仍会被扫到 —— 宁可偶尔吵，不可漏")

def keepalive_ok(raw):
    """崩了真的会被拉起来吗？判据只有一条：`KeepAlive.SuccessfulExit` 必须是 False。

    实测（2026-09-21，用同款配置的临时 launchd 作业）：
        脚本 exit 0 → launchd 只运行 1 次，之后再也没拉过
        脚本 exit 1 → 9 秒内被拉起 5 次
    而 ws_daemon.mjs 收到 SIGTERM 时走 process.exit(0) —— 所以这一位一旦被
    翻成 true，「崩了会自愈」就是一句空话，**而且没有任何东西会红**。
    这正是要断言它的理由：这份配置唯一的作用就是决定「它还活不活得过来」。

    拆成纯函数是为了能拿假样本喂它（本文件 D5/D6）—— 反向对照只在内存里做（§2.1）。
    """
    try:
        ka = plistlib.loads(raw).get("KeepAlive")
    except Exception:
        return False
    return isinstance(ka, dict) and ka.get("SuccessfulExit") is False


# ── D 自愈的前提还在吗 ──────────────────────────────────────────────────
print("\nD 「崩了会自愈」这个前提")
if not PLIST_LIVE.exists():
    check("D1", False, f"在跑的 plist 不存在：{PLIST_LIVE}")
else:
    h = lambda b: hashlib.sha256(b).hexdigest()[:12]
    same = PLIST_REPO.exists() and h(PLIST_REPO.read_bytes()) == h(PLIST_LIVE.read_bytes())
    check("D1", same, "仓库副本 ≡ 在跑的配置（否则你读到的不是生效的）")
    raw = PLIST_LIVE.read_bytes()
    try:
        pl = plistlib.loads(raw)
        check("D2", keepalive_ok(raw), f"KeepAlive.SuccessfulExit = {pl['KeepAlive'].get('SuccessfulExit')}（应 False）")
        check("D3", pl.get("Label") == LABEL, f"Label = {pl.get('Label')}")
        args = pl.get("ProgramArguments") or []
        runner = next((a for a in args if a.endswith(".sh")), "")
        rp = Path(runner)
        check("D4", rp.exists() and os.access(rp, os.X_OK), f"启动器存在且可执行：{runner}")
    except Exception as e:
        check("D2", False, f"plist 解不出来：{e}")
# 反向对照：喂假 plist，判据必须变红（内存里造，不碰盘）
fake_on = plistlib.dumps({"Label": LABEL, "KeepAlive": {"SuccessfulExit": True}})
check("D5", not keepalive_ok(fake_on), "反向对照：SuccessfulExit=true → 判红（那就不自愈了）")
check("D6", not keepalive_ok(plistlib.dumps({"Label": LABEL})), "反向对照：整个 KeepAlive 缺失 → 判红")
check("D7", not keepalive_ok(b"not a plist at all"), "反向对照：plist 解不出来 → 判红（不许静默当成通过）")

# ── E 它现在活着吗 ──────────────────────────────────────────────────────
# 2026-09-22 重写：原先 E1 读的是 `ps -o etime=`，而 `ps` 在本环境被拒 →
# 这一格**永远**是未测、整个自证恒退 2。现在四个子读数都不需要 ps，
# 且合起来由纯函数 `judge_liveness` 判 —— 它可以被喂坏样本（见 E1 的反向对照）。
print("\nE 它现在活着吗")
if UP is None:
    cannot_test("E1", "跑不了 `pgrep`（受限环境）—— 「在不在跑」【未测】，不等于「没在跑」")
elif UP:
    lstate, lpid, lnote = read_launchd()
    if lstate is None:
        cannot_test("E1a", "launchd 读不到（%s）→ 这一格未测；下面几格照给结论" % lnote)
    else:
        check("E1a", lstate == "running",
              "launchd state=%s pid=%s（权威在这里：KeepAlive 归它管）" % (lstate, lpid))
    use_pid = lpid or PID
    check("E1b", str(use_pid) in [str(x) for x in PIDS],
          "pid %s 在 `pgrep -f ws_daemon.mjs` 里（活着的确实是守护进程）" % use_pid)
    kres = kill_probe(use_pid)
    check("E1c", kres in ("ok", "EPERM"),
          "os.kill(%s,0) → %s%s" % (use_pid, kres,
                                    "（EPERM = 权限受限但进程存在）" if kres == "EPERM" else ""))
    up_min, up_src = uptime_minutes(use_pid)
    beat, beat_src = beat_age_minutes()
    if up_min is None:
        cannot_test("E1d", "运行时长【未测】：%s" % up_src)
    else:
        check("E1d", True, "已运行 %.0f 分钟（来源：%s）；最后一次心跳 %.0f 分钟前（来源：%s）"
              % (up_min, up_src, beat if beat is not None else -1, beat_src))
    concl, why = judge_liveness(lstate, use_pid, PIDS, kres, beat)
    if concl == "up":
        check("E1", True, why)
    elif concl == "untested":
        cannot_test("E1", why)
    else:
        check("E1", False, "✗ %s：%s" % (concl, why))
    log = DAEMON_LOG.read_text(encoding="utf-8", errors="replace") if DAEMON_LOG.exists() else ""
    check("E2", "长连接已启动" in log, f"日志里出现过启动横幅 {log.count('长连接已启动')} 次")
    age = (time.time() - DAEMON_LOG.stat().st_mtime) / 60 if DAEMON_LOG.exists() else 1e9
    check("E3", age < 12, f"日志 {age:.0f} 分钟前还在写（心跳每 5 分钟一次 → 没卡死）")
else:
    check("E1", False, "✗ 没有在跑 —— 群里现在没人在答话")

# E1 的反向对照：喂合成读数，四种结论必须**各自落对**（不碰真进程）
print("\nE1 的反向对照（纯函数，不碰真进程）")
for _args, _want, _name in [
    (("running", "3971", ["3971"], "ok", 1.0), "up", "正常在跑"),
    (("running", "3971", ["3971"], "EPERM", 2.0), "up", "kill 被拒(EPERM)但进程在 → 仍算活着"),
    (("running", "3971", ["3971"], "ESRCH", 1.0), "down", "进程真的没了"),
    (("running", "3971", ["9999"], "ok", 1.0), "down", "活着但不是守护进程"),
    (("exited", "3971", ["3971"], "ok", 1.0), "down", "launchd 说没在跑"),
    (("running", "3971", ["3971"], "ok", 20.0), "stuck", "在跑但心跳过期（卡住）"),
    ((None, None, [], "nopid", None), "untested", "一个读数都没采到"),
]:
    _got, _ = judge_liveness(*_args)
    check("E1r", _got == _want, "%s → %s（期望 %s）" % (_name, _got, _want))

# ── F bash 陷阱 ─────────────────────────────────────────────────────────
print("\nF macOS bash 3.2：变量后面直接跟中文")
trap_hits = []
for f in code_files():
    if f.suffix != ".sh":
        continue
    for ln, var, txt in scan_bash_trap(f.read_text(encoding="utf-8", errors="replace")):
        trap_hits.append(f"{f.relative_to(ROOT)}:{ln} ${var} → {txt}")
check("F1", not trap_hits, f"tools/ 下的 .sh 无此写法（{len(trap_hits)} 处）")
for t in trap_hits[:6]:
    print(f"      ✗ {t}")
check("F2", len(scan_bash_trap('echo "值 $P，中文"\n')) == 1, "反向对照：喂 $P， → 报出 1 处")
check("F3", not scan_bash_trap('echo "值 ${P}，中文"\n'), "反向对照：喂 ${P}， → 不报（花括号是正确写法）")
check("F4", not scan_bash_trap('# 说明：$EVENTS）会被吃成变量名\n'),
      "反向对照：整行注释里提它 → 不报（注释不可能被执行）")

# ── G 文档里的命令不许被自动执行 ────────────────────────────────────────
print("\nG 文档里的命令不许被自动执行（§2.7 那段 bash 里有会真重启的命令）")


def runs_doc_commands(src):
    """这个检查器会不会把 AGENTS.md 里的命令真跑一遍？

    本仓库里唯一会「把文档里的 bash 跑一遍」的是 `verify_skill.py`，它扫的是
    `skills/内容合规审查/SKILL.md`。**那个范围不许扩到 AGENTS.md** ——
    一旦扩了，§2.7 里那条 `--yes` 就会被它真执行，等于**未经同意重启守衡**。

    判据故意取得很粗：源码里出现 `AGENTS.md` 就报。因为它目前**没有任何理由**
    出现这个串（真正读 AGENTS.md 的是 `verify_feishu_index.py` 的 M4，不是它）。
    粗判据在这里是对的 —— 它只会因为「有人真的把 AGENTS.md 接进去了」而红，
    不会因为无关改动误报。
    """
    return "AGENTS.md" in src


SKILL_RUNNER = ROOT / "tools" / "verify_skill.py"
if not SKILL_RUNNER.exists():
    check("G1", False, "找不到 tools/verify_skill.py —— 那个「跑文档命令」的检查器不见了")
else:
    check("G1", not runs_doc_commands(SKILL_RUNNER.read_text(encoding="utf-8", errors="replace")),
          "verify_skill.py 的扫描范围里不含 AGENTS.md（§2.7 的 --yes 不会被它跑）")
check("G2", runs_doc_commands('SKILL = os.path.join(ROOT, "AGENTS.md")'),
      "反向对照：喂一个把 AGENTS.md 当扫描目标的假样本 → 报红")
check("G3", not runs_doc_commands('SKILL = os.path.join(ROOT, "skills", "x", "SKILL.md")'),
      "反向对照：正常的 SKILL.md 目标 → 不报")

# ── H 结论行自己不许撒谎（反向对照，全在内存里，不碰盘）─────────────────
print("\nH 结论行自己不许撒谎（未测 ≠ 通过 ≠ 红）")
check("H1", verdict(0, True, 0)[0] == 0, "全过 + 在跑 → 退 0")
check("H2", verdict(3, True, 0)[0] == 1, "有红 → 退 1")
check("H3", verdict(1, False, 0)[0] == 2,
      "**没在跑 → 退 2**（此前 n_fail 分支排在前面，这个 2 是死代码，永远到不了）")
check("H4", verdict(0, True, 2)[0] == 2, "**有未测 → 退 2**（不许当成通过）")
# 文案判据要区分「说」和「否认」：未测那句里必须出现「未测」，但不许出现 ✅。
# （本项目 V25b 踩过这个坑：只查「有没有『通过』二字」会把「这不是通过」也判成撒谎。）
check("H5", "未测" in verdict(0, True, 1)[1] and "✅" not in verdict(0, True, 1)[1],
      "未测的文案说「未测」且不带 ✅（不把没测说成没问题）")
check("H6", "✅" in verdict(0, True, 0)[1] and "✅" not in verdict(0, True, 2)[1],
      "只在真的全过时才出现 ✅")
check("H7", "未测" in verdict(2, True, 1)[1],
      "**有红时也必须报出有未测** —— 否则只看最后一行的人会以为「其余都验过了」")

# ── 结论 ────────────────────────────────────────────────────────────────
n_fail = sum(1 for _, ok, _ in results if not ok)
print("\n" + "=" * 74)
for cid, ok, msg in results:
    print(f"  {'✅' if ok else '❌'} {cid}  {msg}")
for cid, msg in untested:
    print(f"  ⚠ {cid}  {msg}")
print("=" * 74)
_code, _line = verdict(n_fail, UP, len(untested))
print(_line)
if n_fail:
    print(f"   （共 {len(results)} 项断言，{n_fail} 项红）")
sys.exit(_code)
