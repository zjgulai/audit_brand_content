# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# 内容审核工作台 · 生产镜像（阶段一）
#
# 三条设计约束，都来自本项目的实测教训：
#
# ① **单 worker**。`base/business_event_store.py` 用 flock 做 writer lease，
#    多 worker 启动会互相抢锁。这里不写 `--workers`，uvicorn 默认 1。
#    自证：`tools/verify_deploy.py` 会 grep 这一行。
#
# ② **依赖必须锁定**。`pyproject.toml` 写着「开发/CI/生产必须 uv sync --locked，
#    不许无锁安装」。镜像里照做，`uv.lock` 变了镜像就必须重建。
#
# ③ **数据目录不进镜像**。authority / projection / session / principals
#    全部走挂载，容器内只读代码与规则库。`ProductionSettings` 本身也会拒绝
#    把数据路径放进仓库目录。
# ─────────────────────────────────────────────────────────────────────────────

# ── 阶段 1：前端构建 ─────────────────────────────────────────────────────────
FROM node:22-bookworm-slim AS web

WORKDIR /build

# 先只拷依赖清单，让 npm ci 这一层能缓存
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./

# `npm run build` = tsc -b && vite build && check_production_bundle.mjs
# 最后那一步是执行点：内部判定数据（rule_examples / boundary_disputes）与
# 签发/撤回请求路径一旦进包，构建**在这里就失败**，不会做出一个泄露的镜像。
RUN npm run build

# ── 阶段 2：运行时 ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv：与本地同一套锁文件机制
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# 依赖层（可缓存）：只拷锁文件
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# 代码层
COPY api/ ./api/
COPY base/ ./base/
COPY contracts/ ./contracts/

# ★ tools/bj_time.py 是**运行时依赖**，不是开发工具。
#   `base/takedown.py:56` 与 `base/notifications.py:56` 都会把 `tools/` 加进 sys.path
#   然后 `from bj_time import BJ, bj_today` —— 本项目「今天」的唯一来源（2026-10-21 统一）。
#   第一次真实启动时报的错：ModuleNotFoundError: No module named 'bj_time'。
#   只拷这一个文件，不拷整个 tools/（那里有 75 个 verifier 与一堆非运行时脚本）。
COPY tools/bj_time.py ./tools/bj_time.py

# 运行时数据（规则库 / 控制点 / 路由 / 外部标准库）。
# 这些是**只读输入**，与 authority 那种可写数据分开：
#   - research/ 打进镜像（发版即固化，规则变了必须重建镜像 —— 这是有意的）
#   - authority/projection/session/principals 走挂载（见 compose）
COPY research/governance/skeleton/rules-v1.json ./research/governance/skeleton/rules-v1.json
COPY research/governance/control-points-v1.json ./research/governance/control-points-v1.json
COPY research/governance/routing-v1.json ./research/governance/routing-v1.json
COPY research/kb/外部标准库-v1.json ./research/kb/外部标准库-v1.json

# 前端静态产物（阶段 1 的输⼊）
COPY --from=web /build/dist ./web_dist

# 非 root 运行
# ★ /data 挂载点必须在 USER audit 之前由 root 建好并授权，
#   否则切换用户后 mkdir 会 Permission denied。
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin audit \
 && mkdir -p /data/authority /data/projection /data/logs \
 && chown -R audit:audit /app /data
USER audit

VOLUME ["/data"]

EXPOSE 8000

# ★ 单 worker，**不写 --workers**。writer lease 是 flock，多 worker 会抢锁。
# ★ --factory：入口是 `app_from_env()` 这个工厂函数，不是模块级 app 对象。
CMD ["uv", "run", "--no-sync", "uvicorn", "api.production_app:app_from_env", \
     "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
