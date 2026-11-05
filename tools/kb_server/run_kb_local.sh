#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run_kb_local.sh —— 本地知识库服务的启动器
#
# 为什么单独一个脚本：launchd 不继承 shell 环境，PATH 里没有 python3。
# 与 run_shouheng.sh 同一个理由，用同样的探测方式。
#
# 用法：
#   bash tools/kb_server/run_kb_local.sh           # 前台跑（调试用）
#   bash tools/kb_server/run_kb_local.sh --rebuild # 先重建索引再起
# ─────────────────────────────────────────────────────────────
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PORT="${KB_LOCAL_PORT:-8420}"

find_python() {
  for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 \
           "$HOME/.local/bin/python3"; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done
  command -v python3 2>/dev/null && return 0
  echo "❌ 找不到 python3" >&2
  return 1
}

PY="$(find_python)"
DB="${KB_LOCAL_DB:-$HOME/.shouheng/kb-local/kb.sqlite3}"

if [ "${1:-}" = "--rebuild" ] || [ ! -f "$DB" ]; then
  echo "→ 建索引…"
  "$PY" "$HERE/kb_build.py" --db "$DB"
fi

echo "→ 启动知识库服务 http://127.0.0.1:${PORT}"
exec "$PY" "$HERE/kb_serve.py" --db "$DB" --port "$PORT"
