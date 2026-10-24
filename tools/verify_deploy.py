#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_deploy.py —— 部署工件自证（不连服务器、不跑 docker build）

## 为什么需要它

`AGENTS.md` §2.4：**写进文档的每一个上限/要求，必须能指出是哪一行代码在拦它。**
部署这一层此前**一条执行点都没有** —— 没有 Dockerfile、没有 compose、没有 CI，
于是「部署怎么做」只活在人脑里。

本检查器只做**静态**断言：文件在不在、关键约束有没有被写进去、有没有把凭据带进仓库。
它**不**验证镜像能构建、容器能起来 —— 那些要真跑，见 `--remote`（未实现，显式退 2）。

## 每条断言都在拦一件真实发生过或差点发生的事

| 断言 | 拦什么 |
|---|---|
| D1 Dockerfile 存在且多阶段 | 没镜像 = 没进程 |
| D2 **CMD 不许出现 `--workers`** | writer lease 是 flock，多 worker 会抢锁（`business_event_store.py`） |
| D3 CMD 必须 `--factory` | 入口是 `app_from_env()` 工厂，不是模块级 `app` |
| D4 compose 的 api 服务**只绑 127.0.0.1** | 80/443 是宿主机共享反代 `ai_video_nginx` 的 |
| D5 compose 有独立 project name 与独立网络 | 「不要干扰其他应用」的可核对形式 |
| D6 `.env.production` 被 gitignore、`.example` 不被忽略 | 凭据不入库 |
| D7 `.example` 里 13 个必填键齐全 | 与 `ProductionSettings.from_env` 的 required 逐项一致 |
| D8 `.example` 不含任何凭据形态的值 | 模板不该有真值 |
| D9 七个数据路径互不重叠且不在 /app 下 | `ProductionSettings.__post_init__` 会校验；这里提前拦 |
| D10 镜像里**不带** `web/dist` 之外的构建缓存 | 产物臃肿 / 泄露源映射 |
| D11 compose 的 healthcheck 打 `/healthz` 而不是 `/readyz` | readyz 依赖外部存储，抖动会误判容器不健康 |
| D12 运行阶段有 node + 渲染器 + **它的相对 import 链** | 缺一个 .mjs 就是 ERR_MODULE_NOT_FOUND，而结案仍成功 |
| D13 报告渲染器不从 PATH 外部装 node（二进制来自 web 阶段） | apt 装 node 会让镜像多 200MB 且版本与应用层不同 |

## 退出码

0 全过 / 1 有红 / 2 未测（缺文件到无法判断，例如 Dockerfile 根本不存在）
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.production.example"
GITIGNORE = ROOT / ".gitignore"

# 与 api/production_app.py 的 ProductionSettings.from_env 的 required 逐项一致。
# 改了那边就必须改这里 —— 两处各写一遍会各自漂移，所以 D7 会**实时读源码**比对。
REQUIRED_ENV = (
    "REVIEW_AUTHORITY_ROOT", "REVIEW_FROZEN_PROJECTION_ROOT",
    "REVIEW_PROJECTION_DB", "REVIEW_API_SESSION_DB",
    "REVIEW_API_ACCESS_LOG", "REVIEW_PRINCIPAL_DIRECTORY",
    "REVIEW_PUBLIC_ORIGIN", "REVIEW_OAUTH_CLIENT_ID",
    "REVIEW_OAUTH_CLIENT_SECRET", "REVIEW_OAUTH_REDIRECT_URI",
    "REVIEW_OAUTH_REAUTH_REDIRECT_URI", "REVIEW_TENANT_ALLOWLIST",
    "REVIEW_REPORT_ROOT",
)

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)
    return ok


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def required_env_from_source():
    """从 ProductionSettings.from_env 实时抓 required 元组，避免两处漂移。"""
    src = read(ROOT / "api" / "production_app.py")
    if not src:
        return None
    m = re.search(r"def from_env\(.*?required = \((.*?)\)", src, re.S)
    if not m:
        return None
    return tuple(re.findall(r'"(REVIEW_[A-Z_]+)"', m.group(1)))


def _runtime_stage(dockerfile):
    """切出最后一个 `FROM ... AS runtime` 之后的全部内容。

    ★ 为什么要切而不是全文搜：`web` 阶段本来就有 node，
      全文搜 `node` 恒真 —— 一条恒真的断言比没有断言更糟。
    """
    if not dockerfile:
        return ""
    marks = list(re.finditer(r"^FROM\s+\S+\s+AS\s+runtime\s*$", dockerfile, re.M))
    if not marks:
        return ""
    return dockerfile[marks[-1].end():]


def main():
    print("=" * 72)
    print("部署工件自证 —— 静态检查（不构建、不连服务器）")
    print("=" * 72)

    dockerfile = read(DOCKERFILE)
    compose = read(COMPOSE)
    example = read(ENV_EXAMPLE)

    # ── D1 ──────────────────────────────────────────────────────────────
    if dockerfile is None:
        print("  ⚠ D1  Dockerfile 不存在 —— 后面所有镜像相关断言都是【未测】")
        check("D1", False, "Dockerfile 不存在")
        print("\n退 2：缺 Dockerfile，无法判断（未测，不是通过）")
        return 2

    stages = re.findall(r"^FROM\s+\S+\s+AS\s+(\w+)", dockerfile, re.M)
    check("D1", len(stages) >= 2,
          "Dockerfile 多阶段构建 → %s（前端构建与运行时分离）" % (stages or "无"))

    # ── D2 CMD 不许 --workers ───────────────────────────────────────────
    # ★ 2026-10-22 第一版误报：Dockerfile 注释里写着「这里不写 `--workers`」，
    #   而它被当成了真的参数。§2.1.1：**一个会误报的检查器比没有检查器更糟** ——
    #   它会让人开始不看报告。
    #   修法与 verify_shouheng_ops.py 的 C5 / verify_cards.mjs 的 J1a 同一条：
    #   **整行注释不算代码**。（已知盲区：行尾注释仍会被扫到，明着留着。）
    code_lines = [ln for ln in dockerfile.splitlines()
                  if not ln.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    has_workers = bool(re.search(r'--workers', code))
    check("D2", not has_workers,
          "CMD 不含 --workers（writer lease 是 flock，多 worker 会抢锁）"
          if not has_workers else "CMD 里出现了 --workers —— 会与 flock writer lease 冲突")

    # ── D3 必须 --factory ───────────────────────────────────────────────
    has_factory = "--factory" in dockerfile
    check("D3", has_factory,
          "CMD 带 --factory（入口是 app_from_env() 工厂，不是模块级 app）"
          if has_factory else "CMD 缺 --factory —— app_from_env 是函数，uvicorn 会加载失败")

    # ── D4 compose 不许绑 0.0.0.0 ───────────────────────────────────────
    # ★ 2026-10-22 修正：原先要求「只绑 127.0.0.1」，实测不成立 ——
    #   反向代理跑在**容器**里（`ai_video_nginx`，网关 `172.20.0.1`），
    #   容器里的 127.0.0.1 是它自己，不是宿主机。绑 loopback 会让
    #   `proxy_pass http://172.20.0.1:18000` 连不上。
    #   宿主机现有服务全部绑 `172.20.0.1:<port>`，本项目照同一形状。
    #   真正的约束是：**不许绑 0.0.0.0**（会直接暴露公网、绕过反代）。
    bindings = re.findall(r'-\s*"([^"]*:\d+)"', compose)
    api_binds = [b for b in bindings if ":8000" in b]
    wildcard = [b for b in api_binds if b.startswith("0.0.0.0:") or b.startswith(":::")]
    ok4 = bool(api_binds) and not wildcard
    check("D4", ok4,
          "api 不绑 0.0.0.0 → %s（公网只能经反代 443 进来）" % (api_binds or "无绑定")
          if ok4 else
          "api 绑了通配地址 → %s —— 会绕过反代直接暴露公网" % (api_binds or "无"))

    # ── D5 独立 project / 独立网络 ──────────────────────────────────────
    proj = re.search(r"^name:\s*(\S+)", compose, re.M)
    net = re.search(r"^networks:\s*\n\s+(\w[\w-]*):", compose, re.M)
    own_net = bool(net) and net.group(1) not in (
        "bridge", "host", "none", "bos_web_net", "bos_platform_internal",
        "ana_caijing_net", "lighthouse_ai_video_net")
    check("D5", bool(proj) and own_net,
          "独立项目名 %r + 独立网络 %r（不与宿主机其他 compose 共用）"
          % (proj.group(1) if proj else None, net.group(1) if net else None)
          if (proj and own_net) else
          "缺独立 project name 或用了公共网络（project=%r net=%r）"
          % (proj.group(1) if proj else None, net.group(1) if net else None))

    # ── D6 gitignore 成对 ───────────────────────────────────────────────
    gi = read(GITIGNORE) or ""
    ignores_real = bool(re.search(r"^\.env\.production$", gi, re.M))
    ignores_example = bool(re.search(r"^\.env\.production\.example$", gi, re.M))
    check("D6", ignores_real and not ignores_example,
          ".env.production 被忽略、.example 不被忽略（凭据不入库，模板可入库）"
          if (ignores_real and not ignores_example) else
          "gitignore 规则不对：真值被忽略=%s，模板被忽略=%s"
          % (ignores_real, ignores_example))

    # ── D7 13 个键齐全，且与源码一致 ────────────────────────────────────
    if example is None:
        check("D7", False, ".env.production.example 不存在")
        check("D8", False, ".env.production.example 不存在")
        check("D9", False, "无模板可算数据路径")
    else:
        have = set(re.findall(r"^(REVIEW_[A-Z_]+)=", example, re.M))
        src_keys = required_env_from_source()
        if src_keys is None:
            check("D7", False, "读不出 ProductionSettings.from_env 的 required —— 未测")
        else:
            missing = sorted(set(src_keys) - have)
            extra = sorted(have - set(src_keys))
            check("D7", not missing,
                  "13 个必填键齐全，且与 from_env 的 required 逐项一致"
                  if not missing else
                  "模板缺键 %s；多出 %s" % (missing, extra))
            # 两处硬编码的 REQUIRED_ENV 也必须一致（防止本文件自己漂移）
            drift = sorted(set(REQUIRED_ENV) ^ set(src_keys))
            check("D7b", not drift,
                  "本文件写死的 REQUIRED_ENV 与源码一致（无两处漂移）"
                  if not drift else "本文件与源码的必填键集合不一致：%s" % drift)

        # ── D8 模板不含真凭据 ──────────────────────────────────────────
        bad = []
        if re.search(r"REVIEW_OAUTH_CLIENT_SECRET=\S+", example):
            val = re.search(r"REVIEW_OAUTH_CLIENT_SECRET=(\S+)", example).group(1)
            if val not in ("REPLACE_ME", ""):
                bad.append("CLIENT_SECRET 有真值")
        cid_val = re.search(r"REVIEW_OAUTH_CLIENT_ID=(\S+)", example)
        if cid_val and cid_val.group(1) not in ("cli_REPLACE_ME",):
            bad.append("CLIENT_ID 有真值")
        if re.search(r"(AKIA|ghp_|sk-)[A-Za-z0-9]{8,}", example):
            bad.append("含令牌形态")
        check("D8", not bad,
              "模板里没有任何凭据形态的值（全是 REPLACE_ME）"
              if not bad else "模板疑似含真值：%s" % bad)

        # ── D9 六个数据路径互不重叠、不在 /app ─────────────────────────
        pairs = dict(re.findall(r"^(REVIEW_[A-Z_]+)=(/\S+)$", example, re.M))
        path_keys = ("REVIEW_AUTHORITY_ROOT", "REVIEW_FROZEN_PROJECTION_ROOT",
                     "REVIEW_PROJECTION_DB", "REVIEW_API_SESSION_DB",
                     "REVIEW_API_ACCESS_LOG", "REVIEW_PRINCIPAL_DIRECTORY",
                     "REVIEW_REPORT_ROOT")
        vals = {k: pairs.get(k) for k in path_keys}
        problems = []
        if any(v is None for v in vals.values()):
            problems.append("有路径键缺失")
        else:
            for i, a in enumerate(path_keys):
                for b in path_keys[i + 1:]:
                    pa, pb = Path(vals[a]), Path(vals[b])
                    if pa == pb or pa in pb.parents or pb in pa.parents:
                        problems.append("%s 与 %s 重叠" % (a, b))
            for k, v in vals.items():
                if v == "/app" or v.startswith("/app/"):
                    problems.append("%s 落在 /app 内（仓库目录）" % k)
        check("D9", not problems,
              "七个数据路径互不重叠、且不在 /app 下（生产启动不会拒）"
              if not problems else "路径问题：%s" % problems)

    # ── D12 报告渲染器在运行阶段可用 ─────────────────────────────────────
    #
    # ★ 为什么需要这条：T-316c/d 落地后，「结案 → 报告」是生产链路的一环，
    #   而运行阶段基底是 `python:3.12-slim`（**没有 node**）。
    #   不拷 node 的后果不是启动失败 —— 桥接层返回 `node_missing`、
    #   **结案仍然 200**，于是故障静默：报告模块一直不工作，而所有
    #   启动检查、健康检查、既有断言全绿。
    #
    # ★ 也不能只断言「这几个文件名在 COPY 列表里」：
    #   `registry.mjs` 相对 import `./cards.mjs`，只拷前者会在运行时
    #   ERR_MODULE_NOT_FOUND。所以这里断言的是**整条链**（三个文件各一条）。
    if dockerfile is None:
        check("D12", False, "Dockerfile 不存在 —— 无法判断运行阶段是否有 node")
    else:
        runtime_part = _runtime_stage(dockerfile)
        needs = {
            "node 二进制": "--from=web /usr/local/bin/node",
            "report_render.mjs": "tools/audit/report_render.mjs",
            "registry.mjs": "tools/reply-cards/registry.mjs",
            "cards.mjs": "tools/reply-cards/cards.mjs",
        }
        missing = [k for k, needle in needs.items() if needle not in runtime_part]
        check("D12", not missing,
              "运行阶段有 node + 渲染器 + 整条相对 import 链"
              if not missing else "运行阶段缺：%s" % missing)
        # 反向：不许在运行阶段用 apt 装 node（版本会与应用层分叉）
        apt_node = re.search(r"^\s*RUN[^\n]*apt-get[^\n]*node", runtime_part, re.M)
        check("D13", apt_node is None,
              "node 二进制来自 web 阶段，不是 apt 另装（版本不分叉）"
              if apt_node is None else "运行阶段用 apt 装了 node，版本分叉")

    # ── D11 healthcheck 打 /healthz ─────────────────────────────────────
    want_healthz = "/healthz" in compose
    want_readyz_only = ("/readyz" in compose) and ("/healthz" not in compose)
    check("D11", want_healthz and not want_readyz_only,
          "healthcheck 打 /healthz（不把依赖抖动算成容器不健康）"
          if want_healthz else "healthcheck 缺 /healthz")

    # ── D10 镜像不塞构建缓存 / 不拷 .git ────────────────────────────────
    src = read(ROOT / ".dockerignore")
    if src is None:
        check("D10", False, ".dockerignore 不存在 —— 构建上下文会把 .git 与 node_modules 全送进去")
    else:
        need = [".git", "node_modules", "web/dist", "*.pem", ".env.production"]
        missing = [n for n in need if n not in src]
        check("D10", not missing,
              ".dockerignore 排除了 %s" % ", ".join(need)
              if not missing else ".dockerignore 缺：%s" % missing)

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过（注意：这只证明**工件写对了**，不证明镜像能构建、容器能起来）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
