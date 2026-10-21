#!/usr/bin/env bash
# gate.sh —— web 的静态/构建门**唯一入口**
#
# 为什么要有它（方案 §6.10 / L1318）：
#   一个没有触发者的检查器等于一句承诺。本脚本是那个触发者：
#   `package.json` 的 `verify:static` / `verify:build` 都只调它，不各自拼命令。
#
# 用法：
#   bash web/scripts/gate.sh --stage static          # DT-1…DT-8
#   bash web/scripts/gate.sh --stage build           # F11 体积预算 + 生产边界门
#   bash web/scripts/gate.sh --stage static --json   # 机器读
#
# 退出码：0 全绿 / 1 有红 / 2 有未测（**未测 ≠ 通过 ≠ 红**）。
#
# ★ 本脚本自己不做检查，只**汇总**；每条判据仍只有一个实现在各自的 .mjs 里。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WEB="$(cd "${HERE}/.." && pwd)"
STAGE="static"
JSON=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --stage) STAGE="${2:-}"; shift 2 ;;
    --stage=*) STAGE="${1#*=}"; shift ;;
    --json) JSON=1; shift ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

if [ "${STAGE}" != "static" ] && [ "${STAGE}" != "build" ]; then
  echo "未知 stage：${STAGE}（只支持 static | build）" >&2
  exit 2
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/web_gate.XXXXXX")"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

# ── 运行一个输出固定 JSON 契约的检查器 ──────────────────────────────────
# 参数：<名字> <命令...>；产物写到 ${TMP}/<名字>.json
run_json_check() {
  local name="$1"; shift
  "$@" > "${TMP}/${name}.json" 2> "${TMP}/${name}.err"
  local rc=$?
  echo "${rc}" > "${TMP}/${name}.rc"
}

# ── 运行一个只有退出码的检查器（生产边界门）──────────────────────────────
run_rc_check() {
  local name="$1"; shift
  "$@" > "${TMP}/${name}.out" 2>&1
  local rc=$?
  echo "${rc}" > "${TMP}/${name}.rc"
}

if [ "${STAGE}" = "static" ]; then
  run_json_check design_tokens node "${HERE}/check_design_tokens.mjs" --check --json
else
  # build 阶段：dist 必须已经由 `npm run build` 产好（verify:build 的顺序就是这样）
  run_json_check bundle_budget node "${HERE}/check_bundle_budget.mjs" --dir "${WEB}/dist" --json
  run_rc_check production_bundle node "${HERE}/check_production_bundle.mjs" --dir "${WEB}/dist"
fi

# ── 汇总（python3 只做合并，不重写任何判据）──────────────────────────────
python3 - "${TMP}" "${STAGE}" "${JSON}" <<'PY'
import json
import os
import sys

tmp, stage, as_json = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
reds, untested, waived, details = [], [], [], []

for name in sorted(os.listdir(tmp)):
    if not name.endswith(".rc"):
        continue
    stem = name[:-3]
    try:
        rc = int(open(os.path.join(tmp, name), encoding="utf-8").read().strip())
    except Exception:
        rc = 2
    jp = os.path.join(tmp, stem + ".json")
    if os.path.exists(jp):
        try:
            doc = json.load(open(jp, encoding="utf-8"))
            reds.extend("[%s] %s" % (stem, x) for x in doc.get("reds", []))
            untested.extend("[%s] %s" % (stem, x) for x in doc.get("untested", []))
            waived.extend("[%s] %s" % (stem, x) for x in doc.get("waived", []))
            details.extend("[%s] %s" % (stem, x) for x in doc.get("details", []))
        except Exception as e:
            untested.append("[%s] 输出不是合法 JSON（%s）" % (stem, e))
    else:
        out = ""
        op = os.path.join(tmp, stem + ".out")
        if os.path.exists(op):
            out = open(op, encoding="utf-8", errors="replace").read().strip()
        # 只有退出码的检查器：0 → details；1 → reds；2 → untested
        if rc == 0:
            details.append("[%s] 通过（rc=0）" % stem)
        elif rc == 1:
            reds.append("[%s] 失败（rc=1）：%s" % (stem, out.splitlines()[-1] if out else ""))
        else:
            untested.append("[%s] 未测（rc=%d）：%s" % (stem, rc, out.splitlines()[-1] if out else ""))

ok = not reds and not untested
payload = {"ok": ok, "reds": reds, "untested": untested, "waived": waived, "details": details}
if as_json:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    for d in details:
        print("  · %s" % d)
    for w in waived:
        print("  ~ WAIVED %s" % w)
    for u in untested:
        print("  ⚠ 未测 %s" % u)
    for r in reds:
        print("  ✗ %s" % r)
    print(("✅ gate[%s] 全绿" % stage) if ok else
          ("❌ gate[%s] %d 项红" % (stage, len(reds)) if reds else
           "⚠ gate[%s] 有 %d 项未测" % (stage, len(untested))))
sys.exit(1 if reds else (2 if untested else 0))
PY

exit $?
