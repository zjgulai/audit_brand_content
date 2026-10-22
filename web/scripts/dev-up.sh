#!/usr/bin/env bash
# dev-up.sh —— 本地前后端联调（只读）：临时投影 + 真实 review-api + Vite + 页面断言
#
# 幂等：每次用新的临时目录与空闲端口；退出时清理自己启动的进程。
# 失败退非零；成功打印 API/Web/队列/页面读数。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WEB="${ROOT}/web"
PY="${ROOT}/.venv/bin/python"
UV="${ROOT}/.venv/bin/uvicorn"

free_port() {
  python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

API_PORT="${REVIEW_API_PORT:-$(free_port)}"
WEB_PORT="${WEB_PORT:-$(free_port)}"
if [ "${API_PORT}" = "${WEB_PORT}" ]; then
  WEB_PORT="$(free_port)"
fi

RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/review-web-integration.XXXXXX")"
DATA="${RUN_DIR}/projection"
mkdir -p "${DATA}"

API_PID=""
WEB_PID=""

cleanup() {
  rc=$?
  if [ -n "${WEB_PID}" ]; then kill "${WEB_PID}" 2>/dev/null || true; fi
  if [ -n "${API_PID}" ]; then kill "${API_PID}" 2>/dev/null || true; fi
  wait "${WEB_PID}" 2>/dev/null || true
  wait "${API_PID}" 2>/dev/null || true
  echo "日志与截图：${RUN_DIR}"
  if [ "${rc}" -ne 0 ]; then
    echo "--- api.log（末 20 行）---"
    tail -20 "${RUN_DIR}/api.log" 2>/dev/null || true
    echo "--- web.log（末 20 行）---"
    tail -20 "${RUN_DIR}/web.log" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap cleanup EXIT

echo "[1/11] smoke 生成临时投影（不写仓内）"
SMOKE_DUMP_IR="${DATA}" python3 "${ROOT}/tools/smoke_end_to_end.py" \
  > "${RUN_DIR}/smoke.log" 2>&1
test -s "${DATA}/cases.json"
"${PY}" "${WEB}/scripts/seed_projection.py" --projection "${DATA}" \
  > "${RUN_DIR}/seed.log" 2>&1
test -s "${DATA}/reports.json"

# 夹具：把 21 条确定性样例案件**合并**进临时投影（保留 case-smoke 这条真实案件）。
# 不合并就没法看队列形态 —— smoke 只造 1 条，且它是 BLOCK，本身不该出现在待办队列里。
# 夹具每条带 sample:true，界面据此显示「样例数据」。
"${PY}" "${WEB}/scripts/seed_fixture.py" --out "${DATA}" --merge --edge \
  >> "${RUN_DIR}/seed.log" 2>&1
grep -q '"sample": true' "${DATA}/cases.json"

echo "[2/11] 构建生产包 + 开发入口 fail-closed 自证"
( cd "${WEB}" && npm run build ) > "${RUN_DIR}/build.log" 2>&1
test -d "${WEB}/dist"
"${PY}" "${WEB}/scripts/review_api_dev_selftest.py" \
  > "${RUN_DIR}/dev-selftest.log" 2>&1
# 反向对照：即使 mode/NODE_ENV/开发开关全部误设，只要 command=build，
# __REVIEW_* 仍必须是 false。检查器必须指向这个新目录，不能误读 web/dist。
( cd "${WEB}" && REVIEW_DEV_IDENTITY=1 APP_ENV=dev NODE_ENV=development \
  exec ./node_modules/.bin/vite build --mode development \
    --outDir "${RUN_DIR}/hostile-build" --emptyOutDir ) \
  > "${RUN_DIR}/hostile-build.log" 2>&1
node "${WEB}/scripts/check_production_bundle.mjs" \
  --dir "${RUN_DIR}/hostile-build" \
  > "${RUN_DIR}/hostile-bundle-check.log" 2>&1

echo "[3/11] 创建队列口径检查 session（u_dp3 / t1）"
QUEUE_COOKIE="$("${PY}" "${WEB}/scripts/make_session.py" \
  --db "${RUN_DIR}/sessions.db" --principal u_dp3 --tenant t1)"
test -n "${QUEUE_COOKIE}"

echo "[4/11] 启动 review-api :${API_PORT}"
APP_ENV=dev \
REVIEW_DEV_IDENTITY=1 \
REVIEW_API_DATA_ROOT="${DATA}" \
REVIEW_API_SESSION_DB="${RUN_DIR}/sessions.db" \
"${UV}" review_api_dev:app --app-dir "${WEB}/scripts" \
  --host 127.0.0.1 --port "${API_PORT}" \
  > "${RUN_DIR}/api.log" 2>&1 &
API_PID=$!

echo "[5/11] 启动 Vite dev :${WEB_PORT}（/review-api 代理到 :${API_PORT}）"
( cd "${WEB}" && APP_ENV=dev REVIEW_DEV_IDENTITY=1 REVIEW_API_PROXY="http://127.0.0.1:${API_PORT}" \
  exec ./node_modules/.bin/vite --host 127.0.0.1 --port "${WEB_PORT}" --strictPort ) \
  > "${RUN_DIR}/web.log" 2>&1 &
WEB_PID=$!

ready=0
for _ in $(seq 1 80); do
  if curl --max-time 2 -fsS "http://127.0.0.1:${API_PORT}/openapi.json" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.25
done
if [ "${ready}" -ne 1 ]; then
  echo "review-api 未就绪"
  exit 1
fi

ready=0
for _ in $(seq 1 80); do
  if curl --max-time 2 -fsS "http://127.0.0.1:${WEB_PORT}/" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.25
done
if [ "${ready}" -ne 1 ]; then
  echo "Vite dev server 未就绪"
  exit 1
fi

echo "[6/11] curl /api/v1/queue"
HTTP_STATUS="$(curl --max-time 5 -s -o "${RUN_DIR}/queue.json" \
  -w '%{http_code}' \
  -H "Cookie: session=${QUEUE_COOKIE}" \
  "http://127.0.0.1:${API_PORT}/api/v1/queue")"
if [ "${HTTP_STATUS}" != "200" ]; then
  echo "curl /api/v1/queue → ${HTTP_STATUS}"
  exit 1
fi

# ★ 2026-10-20：这里从「断言 case-smoke 在队列里」改成「队列里不许有非待办标签」。
#   旧断言是错的：case-smoke 是 BLOCK，而 BLOCK 本来就不该进待办队列 ——
#   旧断言反而在保护那个 bug（它走的还是「全部可读案件」的联调别名）。
#   新判据是**否定式**：任何一条不属于 {REVIEW, 待自决} 就红。
QUEUE_OFF="$(python3 - "${RUN_DIR}/queue.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))
allowed = {"REVIEW", "待自决"}
bad = [r.get("case_id") for r in rows if str(r.get("state")) not in allowed]
print(",".join(bad[:5]))
PY
)"
if [ -n "${QUEUE_OFF}" ]; then
  echo "队列里出现了非待办标签的案件：${QUEUE_OFF}"
  echo "（/api/v1/queue 只应有 REVIEW 与 待自决；出现别的说明口径坏了）"
  exit 1
fi
QUEUE_N="$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1],encoding='utf-8'))))" "${RUN_DIR}/queue.json")"
test "${QUEUE_N}" -gt 0 || { echo "队列为空，无法验证界面"; exit 1; }

# 从真实队列里取一条 t1 案件做写动作/详情页断言（不再硬编码 case-smoke）。
# 首选当前夹具投影的 assignee_id=u_dp3，避免选到 t2 或不可见品线。
FIRST_CASE="$(python3 -c "
import json,sys
rows=json.load(open(sys.argv[1],encoding='utf-8'))
pick=next((r for r in rows if r.get('tenant')=='t1' and r.get('assignee_id')=='u_dp3'), rows[0])
print(pick['case_id'])" "${RUN_DIR}/queue.json")"
echo "队列 ${QUEUE_N} 条 · 详情页取样：${FIRST_CASE}"

echo "[7/11] 页面断言：队列 → 案件详情 → 报告 → 分类规范"
node "${WEB}/scripts/check_pages.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --enable-dev-identity 1 \
  --case "${FIRST_CASE}" \
  --report "report-smoke" \
  --screenshots "${RUN_DIR}" \
  > "${RUN_DIR}/page.json" 2> "${RUN_DIR}/page.err"
cat "${RUN_DIR}/page.json"

echo "[8/11] 复核写动作：显式身份 → claim → draft → submit → GET 回读"
node "${WEB}/scripts/check_review_actions.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --case "${FIRST_CASE}" \
  > "${RUN_DIR}/actions.json" 2> "${RUN_DIR}/actions.err"
cat "${RUN_DIR}/actions.json"

echo "[9/11] 无障碍自动检查（12 页全量扫描 + 1280x720 + 320px Reflow）"
node "${WEB}/scripts/a11y_check.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --enable-dev-identity 1 \
  --pages "/submit,/inbox,/queue,/cases,/cases/${FIRST_CASE},/appeals,/release,/release/${FIRST_CASE},/takedown,/reports,/reports/report-smoke,/taxonomy,/admin/grants,/admin/sessions" \
  --out "${RUN_DIR}/a11y.json" \
  > "${RUN_DIR}/a11y.stdout" 2> "${RUN_DIR}/a11y.err"
cat "${RUN_DIR}/a11y.stdout"

echo "[10/11] 复核切片断言（A1–A9，含反向对照与边界夹具）"
node "${WEB}/scripts/check_review_slice.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --enable-dev-identity 1 \
  --require-edge \
  --out "${RUN_DIR}/slice.json" 2>&1 | tail -25
SLICE_RC=${PIPESTATUS[0]}
if [ "${SLICE_RC}" -ne 0 ]; then
  echo "复核切片断言未通过（rc=${SLICE_RC}；2=有未测，同样不算通过）"
  exit "${SLICE_RC}"
fi

echo "[11/11] 开发身份切换隔离"
node "${WEB}/scripts/check_identity_switch.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --case "${FIRST_CASE}" \
  > "${RUN_DIR}/identity-switch.json" 2> "${RUN_DIR}/identity-switch.err"
cat "${RUN_DIR}/identity-switch.json"

echo "API_PORT=${API_PORT}"
echo "WEB_PORT=${WEB_PORT}"
echo "RUN_DIR=${RUN_DIR}"
echo "curl_status=${HTTP_STATUS}"
echo "queue_summary=$(head -c 400 "${RUN_DIR}/queue.json")"
echo "api_log=$(tail -3 "${RUN_DIR}/api.log" | tr '\n' ' ')"
