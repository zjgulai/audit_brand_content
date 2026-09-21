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
import hashlib
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "tools" / "restart_shouheng.sh"
LEDGER = ROOT / "PMO" / "logs" / "restart-ledger.jsonl"
DAEMON_LOG = ROOT / "PMO" / "logs" / "ws_daemon.log"
PLIST_REPO = ROOT / "tools" / "com.shouheng.lark.plist"
PLIST_LIVE = Path.home() / "Library" / "LaunchAgents" / "com.shouheng.lark.plist"
LABEL = "com.shouheng.lark"

results = []   # (id, ok, msg)


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    return bool(ok)


def run_gate(*args):
    p = subprocess.run(["bash", str(GATE), *args], capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


def daemon_pid():
    p = subprocess.run(["pgrep", "-f", r"ws_daemon\.mjs"], capture_output=True, text=True)
    return p.stdout.split()[0] if p.stdout.strip() else ""


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

PID = daemon_pid()
UP = bool(PID)

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
rc, out = run_gate("--yes")
check("A6", rc == 3 and "why" in out, f"--yes 不给理由 → 退出码 {rc}（应 3，重启必须留痕）")

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
print("\nE 它现在活着吗")
if UP:
    et = subprocess.run(["ps", "-o", "etime=", "-p", PID], capture_output=True, text=True).stdout.strip()
    check("E1", True, f"进程在跑 PID {PID}，已运行 {et}")
    log = DAEMON_LOG.read_text(encoding="utf-8", errors="replace") if DAEMON_LOG.exists() else ""
    check("E2", "长连接已启动" in log, f"日志里出现过启动横幅 {log.count('长连接已启动')} 次")
    age = (time.time() - DAEMON_LOG.stat().st_mtime) / 60 if DAEMON_LOG.exists() else 1e9
    check("E3", age < 12, f"日志 {age:.0f} 分钟前还在写（心跳每 5 分钟一次 → 没卡死）")
else:
    check("E1", False, "✗ 没有在跑 —— 群里现在没人在答话")

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

# ── 结论 ────────────────────────────────────────────────────────────────
n_fail = sum(1 for _, ok, _ in results if not ok)
print("\n" + "=" * 74)
for cid, ok, msg in results:
    print(f"  {'✅' if ok else '❌'} {cid}  {msg}")
print("=" * 74)
if n_fail:
    print(f"❌ {n_fail} 项红 / 共 {len(results)} 项")
    sys.exit(1)
if not UP:
    print(f"⚠ 断言全过，但**守衡没在跑** —— 这不是通过，是未测（退 2，与 §2.4.2 同口径）")
    sys.exit(2)
print(f"✅ {len(results)} 项全过（守衡在跑 PID {PID}）")
sys.exit(0)
