#!/usr/bin/env bash
# dev-up.sh —— 本地前后端联调（只读）：临时投影 + 真实 review-api + Vite + 页面断言
#
# 幂等：每次用新的临时目录与空闲端口；退出时清理自己启动的进程。
# 失败退非零；成功打印 API/Web/队列/页面读数。
set -euo pipefail

# ── --keep：跑完**不清理**，把 API/WEB 进程与端口号留着 ────────────────
#
# 为什么需要它：`pairing_check.mjs`（前后端接线联调）要对着一个**已经在跑**的
# 服务打请求。没有这个开关时，只有两种做法 —— 要么把联调塞进本脚本（于是
# 「起服务」与「验接线」耦合在一起，改一处动全身），要么手写一段起服务的
# 命令（于是又出现第二套启动口径，与这里必然漂移）。
#
# ★ 留着进程意味着**调用方必须自己收拾**：本脚本会把 API_PID / WEB_PID /
#   RUN_DIR 写到 stdout 最后三行，联调结束后用 `kill` 收尾。
#   不写这个提醒的话，`--keep` 跑几次就会堆一堆 Chrome/Vite/uvicorn。
KEEP=0
for _a in "$@"; do
  case "${_a}" in
    --keep) KEEP=1 ;;
    -h|--help)
      echo "用法：bash web/scripts/dev-up.sh [--keep]"
      echo "  --keep  跑完不杀进程（联调用）；会打印 API_PID/WEB_PID/RUN_DIR"
      exit 0
      ;;
    *) echo "未知参数：${_a}"; exit 2 ;;
  esac
done

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
  # --keep：成功时**不杀**（联调要用），失败时照杀（失败留下的进程没有用处）。
  if [ "${KEEP}" = "1" ] && [ "${rc}" -eq 0 ]; then
    echo "⚠ --keep：API/WEB 仍在运行，收尾请 kill ${API_PID} ${WEB_PID}"
    exit 0
  fi
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

echo "[1/12] smoke 生成临时投影（不写仓内）"
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

echo "[2/12] 构建生产包 + 开发入口 fail-closed 自证"
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

echo "[3/12] 创建队列口径检查 session（u_dp3 / t1）"
# ★ 2026-10-28：这条会话 cookie 是后面**四步**（队列口径 / 写动作建案 /
#   浏览器断言）的身份来源。实测过一次它返回空 —— 而 `test -n` 的失败
#   信息只有一个退出码，读起来像「脚本坏了」，实际是「一次会话没建出来」。
#   所以这里把取不到时的诊断打出来。
# ★ stderr 单独落文件，**不并进 stdout** —— 并进去就会让「一行 traceback」
#   变成一个非空字符串被当成 cookie 传下去，然后在更深的地方以 401 出现，
#   那时报的是「身份不足」，指向完全不同的方向。
#   （这是自证里最容易写错的一处：想看到错误，就把错误变成了数据。）
QUEUE_COOKIE="$("${PY}" "${WEB}/scripts/make_session.py" \
  --db "${RUN_DIR}/sessions.db" --principal u_dp3 --tenant t1 \
  2> "${RUN_DIR}/session.err")"
if [ -z "${QUEUE_COOKIE}" ] || [ "${#QUEUE_COOKIE}" -lt 20 ]; then
  echo "建队列会话失败（拿到的不是 cookie）："
  echo "  [${QUEUE_COOKIE}]"
  echo "  stderr:"; sed 's/^/    /' "${RUN_DIR}/session.err" 2>/dev/null | tail -5
  echo "这不是「跳过」—— 后面四步都要用它，没有身份就没法验。"
  exit 1
fi
# ★ 长度检查不是洁癖：cookie 是 43 字符的 urlsafe token，
#   而错误信息（如 traceback 一行）也能是「非空」。只查 -n 会把
#   「一行报错」当成 cookie 传下去，然后在更深的地方以 401 出现 ——
#   那时报的是「身份不足」，指向完全不同的方向。

echo "[4/12] 启动 review-api :${API_PORT}"
APP_ENV=dev \
REVIEW_DEV_IDENTITY=1 \
REVIEW_API_DATA_ROOT="${DATA}" \
REVIEW_API_SESSION_DB="${RUN_DIR}/sessions.db" \
"${UV}" review_api_dev:app --app-dir "${WEB}/scripts" \
  --host 127.0.0.1 --port "${API_PORT}" \
  > "${RUN_DIR}/api.log" 2>&1 &
API_PID=$!

echo "[5/12] 启动 Vite dev :${WEB_PORT}（/review-api 代理到 :${API_PORT}）"
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

echo "[6/12] curl /api/v1/queue"
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

echo "[7/12] 页面断言：队列 → 案件详情 → 报告 → 分类规范"
node "${WEB}/scripts/check_pages.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --enable-dev-identity 1 \
  --case "${FIRST_CASE}" \
  --report "report-smoke" \
  --screenshots "${RUN_DIR}" \
  > "${RUN_DIR}/page.json" 2> "${RUN_DIR}/page.err"
cat "${RUN_DIR}/page.json"

# ── 建一条**真实**案件给写动作测试（2026-10-28）────────────────────────
#
# ★ 为什么必须新建：`seed_fixture` 造的夹具案件**全部只存在于冻结投影**，
#   authority 里一条都没有（实测：队列 10 条，authority 里有 ir 的 0 条）。
#   对它们做写动作时，reducer 会为本库没有的案件造一个 `ir=None` 的空壳，
#   之后每个裁决动作都报 `finding_not_found` —— 而详情里明明有 finding。
#   （现在这条在 claim 处就被拒：`case_not_in_authority`。）
#
# ★ 这条变更同时钉住一件事：**冻结投影里的历史案件只能读，不能复核**。
#   以前它只是文档里的一句话，现在有执行点。
WRITE_CASE="$("${PY}" "${WEB}/scripts/dev_create_case.py" \
  --api-port "${API_PORT}" --cookie "${QUEUE_COOKIE}")"
if [ -z "${WRITE_CASE}" ]; then
  echo "无法新建写动作测试案件 —— 写动作段无法进行（这是失败，不是跳过）"
  exit 1
fi
echo "写动作测试案件（真实新建）：${WRITE_CASE}"

echo "[8/12] 复核写动作：显式身份 → claim → draft → submit → GET 回读"
node "${WEB}/scripts/check_review_actions.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --case "${WRITE_CASE}" \
  > "${RUN_DIR}/actions.json" 2> "${RUN_DIR}/actions.err"
cat "${RUN_DIR}/actions.json"

echo "[9/12] 样例矩阵：不同内容形态在浏览器里的判定与显示是否一致"
node "${WEB}/scripts/verify_sample_matrix.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --screenshots "${RUN_DIR}" \
  > "${RUN_DIR}/matrix.stdout" 2> "${RUN_DIR}/matrix.err"
MATRIX_RC=$?
cat "${RUN_DIR}/matrix.stdout"
if [ "${MATRIX_RC}" -ne 0 ]; then
  # ★ 2 是「未测」，同样不算通过（AGENTS.md §2.4：未测必须与通过/红长得不一样）。
  echo "样例矩阵未通过（rc=${MATRIX_RC}；2=有未测，同样不算通过）"
  cat "${RUN_DIR}/matrix.err" | tail -5
  exit "${MATRIX_RC}"
fi

echo "[10/12] 无障碍自动检查（全部工作台页面 15 条路由扫描 + 1280x720 + 320px Reflow）"
node "${WEB}/scripts/a11y_check.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --enable-dev-identity 1 \
  --pages "/login,/submit,/inbox,/queue,/cases,/cases/${FIRST_CASE},/appeals,/release,/release/${FIRST_CASE},/takedown,/reports,/reports/report-smoke,/taxonomy,/admin/grants,/admin/sessions" \
  --out "${RUN_DIR}/a11y.json" \
  > "${RUN_DIR}/a11y.stdout" 2> "${RUN_DIR}/a11y.err"
cat "${RUN_DIR}/a11y.stdout"

echo "[11/12] 复核切片断言（A1–A9，含反向对照与边界夹具）"
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

echo "[12/12] 开发身份切换隔离"
node "${WEB}/scripts/check_identity_switch.mjs" \
  --base "http://127.0.0.1:${WEB_PORT}" \
  --api "http://127.0.0.1:${API_PORT}" \
  --case "${FIRST_CASE}" \
  > "${RUN_DIR}/identity-switch.json" 2> "${RUN_DIR}/identity-switch.err"
cat "${RUN_DIR}/identity-switch.json"

echo "API_PORT=${API_PORT}"
echo "WEB_PORT=${WEB_PORT}"
echo "API_PID=${API_PID}"
echo "WEB_PID=${WEB_PID}"
echo "RUN_DIR=${RUN_DIR}"
echo "curl_status=${HTTP_STATUS}"
echo "queue_summary=$(head -c 400 "${RUN_DIR}/queue.json")"
echo "api_log=$(tail -3 "${RUN_DIR}/api.log" | tr '\n' ' ')"
