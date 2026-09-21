#!/bin/bash
# ─────────────────────────────────────────────────────────────
# restart_shouheng.sh —— 守衡重启闸门
#
# 为什么需要闸门：守衡是在飞书群里**对外说话**的常驻进程。重启它不是
# 「让改动生效」这么中性的一件事 —— 重启窗口里群里发的消息不会被回答。
# 所以默认行为是**拒绝**：不带 --yes 时它只报告影响面，不改动任何东西。
#
# ★ 它拦住的第二件事比第一件更要紧：kill -TERM 会让守衡**永久静默**。
#
#   实测（2026-09-21，用与守衡同款 KeepAlive 配置的临时 launchd 作业）：
#     脚本 exit 0  →  launchd 只运行 1 次，之后再也没拉过
#     脚本 exit 1  →  9 秒内被拉起 5 次（ThrottleInterval 节流）
#
#   而 tools/ws_daemon.mjs 收到 SIGTERM 时走的是 process.exit(0)：
#     kill -TERM <pid> → 优雅退出 → 退出码 0 → launchd 按
#     KeepAlive{SuccessfulExit:false} 认定「这是正常停机」→ **不拉起**。
#   日志里只留一行「收到 SIGTERM，正在收尾… 本次统计：…」，
#   读起来完全像一次正常停机。**没有任何东西会红。**
#
#   ⇒ 唯一正确的重启方式是 launchctl kickstart -k。本脚本只用这一条。
#
# 用法：
#   bash tools/restart_shouheng.sh                 # 只报告影响面，拒绝（退 3）
#   bash tools/restart_shouheng.sh --check         # 同上，但退 0（纯查看）
#   bash tools/restart_shouheng.sh --yes --why="..."   # 真重启，必须留痕
#
# 它没在跑的时候不必问：那时这不是「重启」而是「救活」，失联每多一秒
# 都是净损失。闸门自己核这件事（不是听调用方说），并记为 mode=rescue。
# ─────────────────────────────────────────────────────────────
set -uo pipefail

LABEL="com.shouheng.lark"
DOMAIN="gui/$UID"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="$ROOT/PMO/logs/restart-ledger.jsonl"
EVENTS="$ROOT/PMO/logs/ws_events.jsonl"
DAEMON_LOG="$ROOT/PMO/logs/ws_daemon.log"

EXIT_REFUSED=3

YES=0; CHECK=0; WHY=""; SINCE=""
for a in "$@"; do
  case "$a" in
    --yes)   YES=1 ;;
    --check) CHECK=1 ;;
    --why=*) WHY="${a#--why=}" ;;
    # --since 只改「重启会生效」那块读数的参照时间，不参与要不要重启的决定。
    # 存在的理由：不加它，那块读数在最常见的时刻恒为「无」—— 恒真的读数等于没读。
    # 自证拿它做反向对照：--since=0 必须列出整个 import 图，--since=<未来> 必须为空。
    --since=*) SINCE="${a#--since=}" ;;
    -h|--help) sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数：$a" >&2; exit 2 ;;
  esac
done

# ── 读数：谁在跑 ────────────────────────────────────────────
pid_of() {
  local p
  p="$(launchctl print "$DOMAIN/$LABEL" 2>/dev/null | awk '/^[[:space:]]*pid = /{print $3; exit}')"
  [ -n "${p:-}" ] && [ "$p" != "0" ] && { echo "$p"; return; }
  pgrep -f 'ws_daemon\.mjs' 2>/dev/null | head -1
}

# 读数：群里最后一条消息距今多久（判断重启时机的唯一硬依据）
last_msg_age() {
  # ⚠ ${EVENTS} 的花括号不是风格 —— macOS 自带 bash 3.2 会把紧跟变量的多字节
  #   字符首字节吃进变量名（`$EVENTS）` 被当成变量 EVENTS\xef），报一句
  #   莫名其妙的 unbound variable。凡是变量后面直接跟中文，必须加花括号。
  [ -f "$EVENTS" ] || { echo "未知（没有事件落盘 ${EVENTS}）"; return; }
  python3 - "$EVENTS" <<'PY' 2>/dev/null || echo "未知（落盘读不出来）"
import json, sys, time
best = None
with open(sys.argv[1], encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = ((d.get('data') or {}).get('message') or {}).get('create_time')
        try:
            ts = int(ts)
        except (TypeError, ValueError):
            continue
        if best is None or ts > best:
            best = ts
if best is None:
    print('未知（落盘里没有带时间的消息）')
else:
    age = (time.time() - best / 1000) / 60
    print('%.0f 分钟前' % age)
PY
}

# 读数：哪些**运行时文件**在进程启动之后被改过 —— 即「这次重启会让什么生效」
#
# ⚠ 这里只算 ws_daemon.mjs 真正 import 得到的 .mjs。不 import 的文件重启也
#   不会进新进程，把它们算进来就是「这句话比我的输入大」（§2.4.1 记过这个病：
#   一个 file 被改过 ≠ 它会被重新加载）。上一版就是这么错的 —— 它把闸门脚本
#   自己列成了「重启会生效」。
#
# ⚠ 2026-09-21 补第二段：**被 spawn 的脚本**（`path.join(REPO_ROOT,'tools','x.py')`）。
#   它和 import 的语义**不一样**，所以分行报、不混在一起：
#     脚本每次触发都是新起的进程 → **它自己的改动不用重启就会生效**；
#     但「调用它的那一行」若是新加的（在 import 表里），那它现在**根本没被调用**，
#     得靠这次重启才会开始跑。本轮 `tools/verify_pending.py` 正是这一种 ——
#   上一版只报 import 表，于是这一条在报告里**看不见**。
runtime_changed_since() {   # $1 = 进程启动的 epoch
  python3 - "$ROOT" "$1" <<'PY'
import os, re, sys
root, epoch = sys.argv[1], float(sys.argv[2])
entry = os.path.join(root, 'tools', 'ws_daemon.mjs')
rx = re.compile(r"""from\s+['"](\.[^'"]+)['"]|import\s+['"](\.[^'"]+)['"]""")
seen, stack = set(), [entry]
while stack:
    f = stack.pop()
    if f in seen or not os.path.isfile(f):
        continue
    seen.add(f)
    for m in rx.finditer(open(f, encoding='utf-8', errors='replace').read()):
        nxt = os.path.normpath(os.path.join(os.path.dirname(f), m.group(1) or m.group(2)))
        for cand in (nxt, nxt + '.mjs', os.path.join(nxt, 'index.mjs')):
            if os.path.isfile(cand):
                stack.append(cand)
                break
changed = [os.path.relpath(f, root) for f in seen if os.stat(f).st_mtime > epoch]

# spawn 目标：图内代码按 path.join(REPO_ROOT, 'tools', '…….py') 指到的脚本
spawn_rx = re.compile(r"""path\.join\(\s*REPO_ROOT\s*,\s*((?:'[^']*'\s*,\s*)*'[^']*')""")
spawn = set()
for f in seen:
    for m in spawn_rx.finditer(open(f, encoding='utf-8', errors='replace').read()):
        p = os.path.join(root, *re.findall(r"'([^']*)'", m.group(1)))
        if os.path.isfile(p):
            spawn.add(p)
spawned = sorted(os.path.relpath(p, root) for p in spawn if os.stat(p).st_mtime > epoch)

print('===IMPORT===')
print('\n'.join(sorted(changed)))
print('===SPAWN===')
print('\n'.join(spawned))
PY
}

PID="$(pid_of)"
echo "── 守衡重启闸门 ──────────────────────────────────────"
if [ -n "${PID:-}" ]; then
  START_EPOCH="$(ps -o lstart= -p "$PID" 2>/dev/null | xargs -I{} date -j -f '%a %b %d %T %Y' '{}' '+%s' 2>/dev/null)"
  echo "  现在在跑      PID ${PID}，已运行 $(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')"
  echo "  启动于        $(ps -o lstart= -p "$PID" 2>/dev/null | sed 's/^ *//')"
else
  START_EPOCH=""
  echo "  现在在跑      ✗ 没有在跑"
fi
echo "  群里最后一条  $(last_msg_age)"
echo "  重启方式      launchctl kickstart -k $DOMAIN/$LABEL"
echo "                ⚠ 不要用 kill -TERM —— 退出码 0 会让 launchd 认为这是正常停机，不再拉起（见本文件头部实测）"
if [ -n "${START_EPOCH:-}" ]; then
  RAW="$(runtime_changed_since "${SINCE:-$START_EPOCH}")"
  CHANGED="$(printf '%s\n' "$RAW" | sed -n '/^===IMPORT===/,/^===SPAWN===/p' | sed '1d;$d')"
  SPAWNED="$(printf '%s\n' "$RAW" | sed -n '/^===SPAWN===/,$p' | sed '1d')"
  if [ -n "$CHANGED" ] || [ -n "$SPAWNED" ]; then
    if [ -n "$CHANGED" ]; then
      echo "  重启会生效    $(printf '%s\n' "$CHANGED" | wc -l | tr -d ' ') 个被 import 的模块在启动后被改过："
      printf '%s\n' "$CHANGED" | sed 's/^/                  /'
    else
      echo "  重启会生效    没有被 import 的模块在启动后被改过"
    fi
    if [ -n "$SPAWNED" ]; then
      echo "  另（spawn）   $(printf '%s\n' "$SPAWNED" | wc -l | tr -d ' ') 个被调起的脚本在启动后被改过/新建："
      printf '%s\n' "$SPAWNED" | sed 's/^/                  /'
      echo "                · 脚本每次触发都是新起的进程 —— **它自己的改动不用重启就会生效**"
      echo "                · 但「调用它的那一行」若是新加的（见上面那张表），它现在**根本没被调用**，"
      echo "                  要靠这次重启才会开始跑。逐条看清是哪一种，别整段照读。"
    fi
  else
    echo "  重启会生效    无 —— 启动之后没有任何被 import 的模块或被调起的脚本被改过"
    echo "                （那这次重启不带来任何运行时变化，先想清楚为什么还要重启）"
  fi
fi

# ── 没在跑：这不是重启，是救活 ──────────────────────────────
if [ -z "${PID:-}" ]; then
  echo "──────────────────────────────────────────────────────"
  echo "  它现在根本没在跑 —— 这是**救活**，不是重启。"
  echo "  失联每多一秒都是净损失，所以救活不必等人同意；但要留痕。"
  if [ "$CHECK" = "1" ] && [ "$YES" = "0" ]; then echo "  （--check：以上为查看，未做任何动作）"; exit 0; fi
  if [ "$YES" = "0" ]; then echo "  确认救活：加 --yes"; exit "$EXIT_REFUSED"; fi
  MODE="rescue"
else
  # ── 在跑：这是重启，默认拒绝 ──────────────────────────────
  echo "──────────────────────────────────────────────────────"
  if [ "$CHECK" = "1" ] && [ "$YES" = "0" ]; then echo "  （--check：以上为查看，未做任何动作）"; exit 0; fi
  if [ "$YES" = "0" ]; then
    echo "  ✗ 拒绝重启：守衡正在对外说话，重启窗口内群里的消息不会被回答。"
    echo "    同意之后再执行：bash tools/restart_shouheng.sh --yes --why=\"<重启的理由>\""
    exit "$EXIT_REFUSED"
  fi
  if [ -z "$WHY" ]; then
    echo "  ✗ 拒绝重启：--yes 必须配 --why=\"<理由>\" —— 重启要留痕，理由就是痕迹。"
    exit "$EXIT_REFUSED"
  fi
  MODE="restart"
fi

# ── 执行 ───────────────────────────────────────────────────
PID_BEFORE="${PID:-none}"
echo "  执行          launchctl kickstart -k $DOMAIN/$LABEL  [$MODE]"
launchctl kickstart -k "$DOMAIN/$LABEL" || { echo "  ✗ kickstart 失败（退出码 ${?}）—— 它可能现在没在跑，或 label 不对"; exit 1; }

# 等它起来（最多 20 秒），并**证明它真的回来了** —— 只 kickstart 不验证，
# 等于把「重启完了」当成「重启好了」。
PID_AFTER=""
for _ in $(seq 1 20); do
  sleep 1
  PID_AFTER="$(pid_of)"
  [ -n "${PID_AFTER:-}" ] && [ "$PID_AFTER" != "$PID_BEFORE" ] && break
  PID_AFTER=""
done

echo "──────────────────────────────────────────────────────"
if [ -z "${PID_AFTER:-}" ]; then
  echo "  ✗ 20 秒内没看到新进程 —— 现在很可能**没人在群里答话**。"
  echo "    先看 $DAEMON_LOG 的尾部，再决定下一步。"
  RC=1
else
  echo "  ✓ 已回来      PID $PID_BEFORE → $PID_AFTER"
  BOOT="$(grep -c '长连接已启动' "$DAEMON_LOG" 2>/dev/null)"
  echo "    启动横幅在日志里出现过 $BOOT 次（每重启一次 +1，可据此核对真的是新进程）"
  RC=0
fi

# 留痕：用 shell 追加（本项目实测 —— Python 写出的文件会被 +4096 填充成 read 工具打不开，
# 账本是要给人读的，所以必须走「不会填充」的写出方式）
printf '{"at":"%s","mode":"%s","pid_before":"%s","pid_after":"%s","why":"%s","ok":%s}\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$MODE" "$PID_BEFORE" "${PID_AFTER:-none}" \
  "$(printf '%s' "$WHY" | tr -d '"\\')" "$([ "$RC" = 0 ] && echo true || echo false)" >> "$LEDGER"
echo "  已留痕        PMO/logs/restart-ledger.jsonl"
exit "$RC"
