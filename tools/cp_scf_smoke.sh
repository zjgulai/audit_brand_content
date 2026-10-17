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

# CP_SCF_ROOT 可覆盖(selftest 用临时目录,绝不碰真仓库 —— §2.4.4 自证不许有副作用)
REPO_ROOT="${CP_SCF_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
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

# 扩展名说是什么,内容就必须是什么(不信 MIME 探测、更不信 URL 后缀)
magic_check() {
  local f="$1"
  case "${f##*.}" in
    jpg|jpeg)
      head -c 3 "$f" | xxd -p | grep -qi '^ffd8ff' ;;
    png)
      head -c 8 "$f" | xxd -p | grep -qi '^89504e470d0a1a0a' ;;
    webp)
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

  # ── 故障注入:只在 selftest 下生效(证伪"校验器真的会红") ──────────
  if [ "${CP_SCF_SELFTEST:-0}" = "1" ]; then
    case "${CP_SCF_FAULT:-}" in
      truncate) python3 -c 'import sys;p=sys.argv[1];d=open(p,"rb").read();open(p,"wb").write(d[:max(0,len(d)-1)])' "$dst" ;;
      corrupt)  python3 -c 'import sys;p=sys.argv[1];b=bytearray(open(p,"rb").read());b[0]^=0xFF;open(p,"wb").write(bytes(b))' "$dst" ;;
    esac
  fi

  # 步骤 4: 校验(顺序:size → magic → sha —— magic 先于 sha,才能各自单独变红)
  local dst_sha dst_size
  dst_sha="$(sha256_of "$dst")"
  dst_size="$(size_of "$dst")"

  quarantine_failed() {
    local why="$1" note="$2"
    local q="${QUAR_DIR}/$(basename "$dst").failed-$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$dst" "$q" 2>/dev/null || true
    log_action cp "$src" "$dst" "$src_sha" "$src_size" "$src_mtime" "$src_type" "unknown" "$dst_sha" "$dst_size" "$why" "$kind" "$series" "$note"
    echo "FAIL ($why): $dst → $q" >&2
    return 1
  }

  if [ "$src_size" != "$dst_size" ]; then
    quarantine_failed "size_mismatch" "expected_${src_size}_got_${dst_size}"
    return 1
  fi
  if ! magic_check "$dst"; then
    quarantine_failed "magic_mismatch" "type=${src_type}"
    return 1
  fi
  if [ "$src_sha" != "$dst_sha" ]; then
    quarantine_failed "sha256_mismatch" "src=${src_sha}_dst=${dst_sha}"
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
    # ── 8 条反向对照:每条都要求"该红时必红、该闭嘴时必闭嘴" ──────────
    # 隔离:全部写入 mktemp 目录,真仓库一个字节都不碰(§2.4.4)
    tmp="$(mktemp -d /tmp/cp_scf_selftest.XXXXXX)"
    trap 'rm -rf "$tmp"' EXIT
    export CP_SCF_ROOT="$tmp"
    export CP_SCF_SELFTEST=1
    LOGS_DIR="$tmp/PMO/_logs"
    QUAR_DIR="$tmp/PMO/_quarantine"
    mkdir -p "$LOGS_DIR" "$QUAR_DIR" "$tmp/src" "$tmp/dst"

    pass=0; fail=0
    ok()  { echo "PASS: $1"; pass=$((pass+1)); }
    bad() { echo "FAIL: $1" >&2; fail=$((fail+1)); }

    printf 'hello momcozy\n' > "$tmp/src/good.txt"
    printf 'not really a jpeg\n' > "$tmp/src/fake.jpg"

    # S1 正常复制:内容一致 + 日志 status=ok + license=unknown
    if cp_one "$tmp/src/good.txt" "$tmp/dst/good.txt" selftest s1 >/dev/null 2>&1 \
       && python3 -c 'import sys;sys.exit(0 if open(sys.argv[1],"rb").read()==open(sys.argv[2],"rb").read() else 1)' "$tmp/src/good.txt" "$tmp/dst/good.txt"; then
      ok "S1 正常复制(内容级一致)"
    else
      bad "S1 正常复制"
    fi

    # S2 幂等:同内容重跑必须 SKIP,且不新增 cp 动作日志
    before=$(cat "$LOGS_DIR"/cp_*.jsonl 2>/dev/null | grep -c '"action":"cp"' || true)
    out=$(cp_one "$tmp/src/good.txt" "$tmp/dst/good.txt" selftest s2 2>&1 || true)
    after=$(cat "$LOGS_DIR"/cp_*.jsonl 2>/dev/null | grep -c '"action":"cp"' || true)
    if echo "$out" | grep -q '^SKIP' && [ "${before:-0}" = "${after:-0}" ]; then
      ok "S2 幂等重跑 SKIP 且无重复写"
    else
      bad "S2 幂等重跑 (before=$before after=$after out=$out)"
    fi

    # S3 冲突:内容不同 → 旧件进隔离区、新内容落位、显式记账
    printf 'hello momcozy CHANGED\n' > "$tmp/src/good.txt"
    out=$(cp_one "$tmp/src/good.txt" "$tmp/dst/good.txt" selftest s3 2>&1 || true)
    if echo "$out" | grep -q '^CONFLICT' \
       && ls "$QUAR_DIR"/good.txt.bak-* >/dev/null 2>&1 \
       && grep -q '"action":"conflict"' "$LOGS_DIR"/cp_conflict.jsonl 2>/dev/null; then
      ok "S3 冲突不覆盖 + 隔离 + 记账"
    else
      bad "S3 冲突处理: $out"
    fi

    # S4 size 反向:截断注入必须被 size_mismatch 拦下,失败件不进 dst
    printf 'abcdefghij\n' > "$tmp/src/size.txt"
    out=$(CP_SCF_FAULT=truncate cp_one "$tmp/src/size.txt" "$tmp/dst/size.txt" selftest s4 2>&1 || true)
    if echo "$out" | grep -q 'size_mismatch' && [ ! -f "$tmp/dst/size.txt" ] \
       && ls "$QUAR_DIR"/size.txt.failed-* >/dev/null 2>&1; then
      ok "S4 size 恒等拦截(失败件入隔离区)"
    else
      bad "S4 size 拦截: $out"
    fi

    # S5 magic 反向:扩展名 .jpg + 文本内容必须被拦下
    out=$(cp_one "$tmp/src/fake.jpg" "$tmp/dst/fake.jpg" selftest s5 2>&1 || true)
    if echo "$out" | grep -q 'magic_mismatch' && [ ! -f "$tmp/dst/fake.jpg" ]; then
      ok "S5 magic 与扩展名不符被拦下"
    else
      bad "S5 magic 拦截: $out"
    fi

    # S6 sha 反向:同长度翻一个字节必须被 sha256_mismatch 拦下
    printf 'abcdefghij\n' > "$tmp/src/sha.txt"
    out=$(CP_SCF_FAULT=corrupt cp_one "$tmp/src/sha.txt" "$tmp/dst/sha.txt" selftest s6 2>&1 || true)
    if echo "$out" | grep -q 'sha256_mismatch' && [ ! -f "$tmp/dst/sha.txt" ]; then
      ok "S6 sha256 恒等拦截"
    else
      bad "S6 sha 拦截: $out"
    fi

    # S7 license 强制 unknown(任何一行都不许出现非 unknown)
    badlic=$(cat "$LOGS_DIR"/cp_*.jsonl 2>/dev/null | grep -c '"src_license_status":"unknown"' || true)
    totlic=$(cat "$LOGS_DIR"/cp_*.jsonl 2>/dev/null | wc -l | tr -d ' ')
    if [ -n "$totlic" ] && [ "$badlic" = "$totlic" ]; then
      ok "S7 license_status 全 unknown ($totlic/$totlic)"
    else
      bad "S7 license 字段 ($badlic/$totlic)"
    fi

    # S8 原子性:全程不许残留临时文件;日志必须逐行可解析 JSON
    leftovers=$(find "$tmp" -name '*.tmp.*' 2>/dev/null | wc -l | tr -d ' ')
    if [ "$leftovers" = "0" ] && python3 -c '
import sys, glob, json
for p in glob.glob(sys.argv[1] + "/cp_*.jsonl"):
    for line in open(p, encoding="utf-8"):
        if line.strip():
            json.loads(line)
print("jsonl-ok")' "$LOGS_DIR" | grep -q 'jsonl-ok'; then
      ok "S8 无临时残留 + JSONL 可解析"
    else
      bad "S8 原子性/JSONL (leftovers=$leftovers)"
    fi

    echo "----------------------------------------"
    if [ "$fail" -eq 0 ]; then
      echo "✅ $pass/8 全过"
      exit 0
    else
      echo "❌ $pass passed, $fail failed" >&2
      exit 1
    fi
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