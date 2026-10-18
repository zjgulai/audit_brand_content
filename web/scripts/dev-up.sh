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

echo "[1/8] smoke 生成临时投影（不写仓内）"
SMOKE_DUMP_IR="${DATA}" python3 "${ROOT}/tools/smoke_end_to_end.py" \
  > "${RUN_DIR}/smoke.log" 2>&1
test -s "${DATA}/cases.json"
"${PY}" "${WEB}/scripts/seed_projection.py" --projection "${DATA}" \
  > "${RUN_DIR}/seed.log" 2>&1
test -s "${DATA}/reports.json"

echo "[2/8] npm run build"
( cd "${WEB}" && npm run build ) > "${RUN_DIR}/build.log" 2>&1
test -d "${WEB}/dist"

echo "[3/8] 创建本地 session（u_dp3 / t1）"
COOKIE="$("${PY}" "${WEB}/scripts/make_session.py" \
  --db "${RUN_DIR}/sessions.db" --principal u_dp3 --tenant t1)"
test -n "${COOKIE}"

echo "[4/8] 启动 review-api :${API_PORT}"
REVIEW_API_DATA_ROOT="${DATA}" \
REVIEW_API_SESSION_DB="${RUN_DIR}/sessions.db" \
"${UV}" review_api_dev:app --app-dir "${WEB}/scripts" \
  --host 127.0.0.1 --port "${API_PORT}" \
  > "${RUN_DIR}/api.log" 2>&1 &
API_PID=$!

echo "[5/8] 启动 Vite dev :${WEB_PORT}（/review-api 代理到 :${API_PORT}）"
( cd "${WEB}" && REVIEW_API_PROXY="http://127.0.0.1:${API_PORT}" \
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

echo "[6/8] curl /review-api/queue"
HTTP_STATUS="$(curl --max-time 5 -s -o "${RUN_DIR}/queue.json" \
  -w '%{http_code}' \
  -H "Cookie: session=${COOKIE}" \
  "http://127.0.0.1:${API_PORT}/review-api/queue")"
if [ "${HTTP_STATUS}" != "200" ]; then
  echo "curl /review-api/queue → ${HTTP_STATUS}"
  exit 1
fi
if ! grep -q 'case-smoke' "${RUN_DIR}/queue.json"; then
  echo "queue 响应里没有 case-smoke"
  exit 1
fi

echo "[7/8] 页面断言：队列 → 案件详情 → 报告"
node "${WEB}/scripts/check_pages.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --cookie "${COOKIE}" \
  --case "case-smoke" \
  --report "report-smoke" \
  --screenshots "${RUN_DIR}" \
  > "${RUN_DIR}/page.json" 2> "${RUN_DIR}/page.err"
cat "${RUN_DIR}/page.json"

echo "[8/8] 无障碍自动检查（三页）"
node "${WEB}/scripts/a11y_check.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --cookie "${COOKIE}" \
  --pages "/queue,/cases/case-smoke,/reports/report-smoke" \
  --out "${RUN_DIR}/a11y.json" \
  > "${RUN_DIR}/a11y.stdout" 2> "${RUN_DIR}/a11y.err"
cat "${RUN_DIR}/a11y.stdout"

echo "API_PORT=${API_PORT}"
echo "WEB_PORT=${WEB_PORT}"
echo "RUN_DIR=${RUN_DIR}"
echo "curl_status=${HTTP_STATUS}"
echo "queue_summary=$(head -c 400 "${RUN_DIR}/queue.json")"
echo "api_log=$(tail -3 "${RUN_DIR}/api.log" | tr '\n' ' ')"
