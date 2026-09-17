#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run_shouheng.sh —— 守衡的启动器（给 launchd 用）
#
# 存在的理由：launchd 不继承你的 shell 环境，PATH 里没有 node。
# 而且这台机器上并没有独立安装 node —— 唯一在 PATH 里的 node 是
# Kimi.app 内置的运行时，拿它做守护服务意味着「Kimi 一升级守衡就死」。
#
# 所以这里做运行时自动探测：按稳定性排序尝试多个候选，第一个可用的胜出。
# 想固定用某一个，设环境变量 SHOUHENG_NODE=/path/to/node 即可。
# ─────────────────────────────────────────────────────────────
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HERE/../PMO/logs"
mkdir -p "$LOG_DIR"

find_node() {
  # 0) 显式指定优先
  if [ -n "${SHOUHENG_NODE:-}" ] && [ -x "$SHOUHENG_NODE" ]; then
    echo "$SHOUHENG_NODE"; return 0
  fi

  # 1) 系统/包管理器安装的 node（最稳定，若存在则首选）
  for p in /opt/homebrew/bin/node /usr/local/bin/node /usr/bin/node \
           "$HOME/.volta/bin/node" "$HOME/.local/bin/node"; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done

  # 2) nvm / fnm 管理的版本（取最新一个）
  for d in "$HOME/.nvm/versions/node" "$HOME/.fnm/node-versions"; do
    [ -d "$d" ] || continue
    local cand
    cand="$(find "$d" -maxdepth 3 -type f -name node -perm -u+x 2>/dev/null | sort -V | tail -1)"
    [ -n "$cand" ] && [ -x "$cand" ] && { echo "$cand"; return 0; }
  done

  # 3) DSH Desktop 自带的 Electron，以 ELECTRON_RUN_AS_NODE 方式当 node 用
  #    选它是因为守衡本来就是 DSH 体系的一部分；但它是兜底，不是首选。
  local dsh="/Applications/DSH Desktop.app/Contents/MacOS/DSH Desktop"
  if [ -x "$dsh" ] && ELECTRON_RUN_AS_NODE=1 "$dsh" --version >/dev/null 2>&1; then
    echo "$dsh"; return 0
  fi

  # 4) 最后手段：PATH 里能找到什么用什么
  if command -v node >/dev/null 2>&1; then command -v node; return 0; fi

  return 1
}

NODE_BIN="$(find_node)" || {
  echo "[launcher] ✗ 找不到任何可用的 node 运行时。请安装 node，或设置 SHOUHENG_NODE。" >&2
  exit 127
}

# Electron 当 node 用时必须带这个环境变量
case "$NODE_BIN" in
  *"DSH Desktop"*) export ELECTRON_RUN_AS_NODE=1 ;;
esac

cd "$HERE"
echo "[launcher] 运行时 = $NODE_BIN ($("$NODE_BIN" --version 2>&1))" >&2
echo "[launcher] 工作目录 = $HERE" >&2
echo "[launcher] 启动时间 = $(date '+%Y-%m-%d %H:%M:%S')" >&2

exec "$NODE_BIN" ws_daemon.mjs "$@"
