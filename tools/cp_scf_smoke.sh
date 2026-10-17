#!/usr/bin/env bash
#
# cp_scf_smoke.sh — 安全复制契约(secure copy from external)
# 来自 fb(audit-multi-content-fb) 的 8 条边界 + AGENTS.md §2.4 + §2.6 综合
#
# 用法:
#   tools/cp_scf_smoke.sh <src> <dst>          # 单文件
#   tools/cp_scf_smoke.sh --batch <list.tsv>   # 批量(每行: src\tdst\tkind\tseries)
#   tools/cp_scf_smoke.sh --selftest           # 跑 8 条反向对照
#
# 单文件契约(§四 步骤 1-6):
#   1. 写临时文件 dst.tmp.<pid>.<ts>
#   2. cp -p src → dst.tmp
#   3. 原子 rename dst.tmp → dst (POSIX 保证)
#   4. 校验:size 恒等 + sha256 恒等 + (图)magic-byte
#   5. 冲突:dst 已存在且 sha 一致 = skip;不一致 = bak-<ts> + quarantine
#   6. 写 _logs/cp_<kind>.jsonl
#
# 通用脚本,可被 9a 复用(brand_agent → audit_multi_content 安全复制)。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS_DIR="${REPO_ROOT}/PMO/_logs"
QUAR_DIR="${REPO_ROOT}/PMO/_quarantine"
mkdir -p "$LOGS_DIR" "$QUAR_DIR"

log_action() {
  local action="$1" src="$2" dst="$3" src_sha="$4" src_size="$5" src_mtime="$6"
  local src_type="$7" src_lic="$8" dst_sha="$9" dst_size="${10}" status="${11}"
  local kind="${12:-file}" series="${13:-unknown}" note="${14:-}"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"ts":"%s","action":"%s","src_path":"%s","src_sha256":"%s","src_size":%s,"src_mtime":"%s","src_type":"%s","src_license_status":"%s","dst_path":"%s","dst_sha256":"%s","dst_size":%s,"kind":"%s","series":"%s","status":"%s","note":"%s"}\n' \
    "$ts" "$action" "$src" "$src_sha" "$src_size" "$src_mtime" "$src_type" "$src_lic" \
    "$dst" "$dst_sha" "$dst_size" "$kind" "$series" "$status" "$note" \
    >> "$LOGS_DIR/cp_$(echo "$action" | tr -dc '[:alnum:]_').jsonl"
}

detect_type() {
  case "$(file -b --mime-type "$1" 2>/dev/null || echo unknown)" in
    text/plain)        echo "text/plain" ;;
    text/markdown)     echo "text/markdown" ;;
    text/css)          echo "text/css" ;;
    application/json)  echo "application/json" ;;
    application/toml)  echo "application/toml" ;;
    image/jpeg)        echo "image/jpeg" ;;
    image/png)         echo "image/png" ;;
    image/webp)        echo "image/webp" ;;
    *)                 echo "application/octet-stream" ;;
  esac
}

magic_check() {
  local f="$1" t="$2"
  case "$t" in
    image/jpeg)
      head -c 3 "$f" | xxd -p | grep -qi '^ffd8ff' ;;
    image/png)
      head -c 8 "$f" | xxd -p | grep -qi '^89504e470d0a1a0a' ;;
    image/webp)
      local hdr
      hdr="$(head -c 12 "$f" | xxd -p)"
      [[ "${hdr:0:8}" == "52494646" && "${hdr:16:8}" == "57454250" ]] ;;
    *)
      return 0 ;;  # 非图类不强校 magic
  esac
}

# ── 判据必须比内容,不能比 stat/shasum ──────────────────────────────
# 2026-10-17 实测(AGENTS.md §2.1.1 原话):本机存在"填充态"文件,
#   stat / wc -c / macOS shasum 都会读出比真实内容多 4096 B 的视图,
#   而 Python open().read() 读到的是真内容。
#   首版用 shasum 做校验 → 76 个 caption 全部误报 size_mismatch,
#   而 Python 内容级比对 153/153 全等。
# 所以:sha256 与 size 一律用 Python 读真内容计算。
sha256_of() {
  python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
}

size_of() {
  python3 -c 'import sys;print(len(open(sys.argv[1],"rb").read()))' "$1"
}

mtime_of() {
  stat -f%Sm "$1" | sed 's/$/ /'
}

cp_one() {
  local src="$1" dst="$2" kind="${3:-file}" series="${4:-unknown}"
  local tmp
  tmp="${dst}.tmp.$$.$(date +%s)"
  local src_sha src_size src_mtime src_type
  src_sha="$(sha256_of "$src")"
  src_size="$(size_of "$src")"
  src_mtime="$(mtime_of "$src")"
  src_type="$(detect_type "$src")"

  # 已存在 dst 处理(冲突 §四.5 + Q9)
  if [ -e "$dst" ]; then
    local ex_sha
    ex_sha="$(sha256_of "$dst")"
    if [ "$ex_sha" = "$src_sha" ]; then
      log_action skip "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$ex_sha" "$(size_of "$dst")" "ok" "$kind" "$series" "already_present"
      echo "SKIP (sha match): $dst"
      return 0
    fi
    # 不一致 → 备份 + 暂存
    local ts bak
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    bak="${dst}.bak-${ts}"
    mv "$dst" "$bak" || true
    mv "$bak" "$QUAR_DIR/" || true
    log_action conflict "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$ex_sha" "$(size_of "$QUAR_DIR/$(basename "$bak")")" "conflict" "$kind" "$series" "moved_to_quarantine"
    echo "CONFLICT: $dst → $QUAR_DIR/$(basename "$bak")"
  fi

  mkdir -p "$(dirname "$dst")"
  # 步骤 1-2: 写临时
  cp -p "$src" "$tmp"
  # 步骤 3: 原子 rename
  mv "$tmp" "$dst"
  # 步骤 4: 校验
  local dst_sha dst_size
  dst_sha="$(sha256_of "$dst")"
  dst_size="$(size_of "$dst")"
  if [ "$src_size" != "$dst_size" ]; then
    log_action cp "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$dst_sha" "$dst_size" "size_mismatch" "$kind" "$series" "expected_${src_size}_got_${dst_size}"
    echo "FAIL (size mismatch): $dst" >&2
    return 1
  fi
  if [ "$src_sha" != "$dst_sha" ]; then
    log_action cp "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$dst_sha" "$dst_size" "sha256_mismatch" "$kind" "$series" "src=${src_sha}_dst=${dst_sha}"
    echo "FAIL (sha mismatch): $dst" >&2
    return 1
  fi
  if ! magic_check "$dst" "$src_type"; then
    log_action cp "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$dst_sha" "$dst_size" "magic_mismatch" "$kind" "$series" "type=${src_type}"
    echo "FAIL (magic mismatch): $dst" >&2
    return 1
  fi
  log_action cp "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$dst_sha" "$dst_size" "ok" "$kind" "$series" ""
  echo "OK: $dst"
}

case "${1:-}" in
  --batch)
    list="${2:?usage: --batch <list.tsv>}"
    while IFS=$'\t' read -r src dst kind series; do
      [ -z "$src" ] && continue
      cp_one "$src" "$dst" "$kind" "$series" || true
    done < "$list"
    ;;
  --selftest)
    # 8 条反向对照(占位,主流程先把 153 文件落盘,selftest 在落盘后跑)
    echo "selftest TBD after main run"
    ;;
  "")
    echo "usage: $0 <src> <dst> [kind] [series]" >&2
    echo "       $0: --batch <list.tsv>" >&2
    echo "       $0: --selftest" >&2
    exit 2
    ;;
  *)
    src="$1"; dst="$2"; kind="${3:-file}"; series="${4:-unknown}"
    cp_one "$src" "$dst" "$kind" "$series"
    ;;
esac