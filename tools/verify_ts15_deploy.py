#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_ts15_deploy.py —— 验收表行 117 / TS-15「容器化部署：可复现、0700、健康检查、重启策略」

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:260`）

> 容器化部署：可复现、0700、健康检查、重启策略。

## 这一票补的是什么洞（三处，逐条实测过）

| # | 缺口 | 实测 |
|---:|---|---|
| 1 | **「数据目录必须 0700」没有任何断言** | `grep -rnE 'chmod|0o777' tools/verify_production_app.py tools/verify_deploy.py` → **空**。`api/production_app.py:208` 有实现（`mode & 0o077 → SettingsError('data_permissions')`），`/readyz` 也真的会因此 503（我实测 `chmod 0777` → 503 + `data_permissions=false`），**但 tools/ 里没有一条触发过它** |
| 2 | **「容器挂了会自动重启」没有任何断言** | `grep -rn 'restart' tools/*.py` → 只命中守衡守护进程的重启闸门，**与容器无关**；`unless-stopped` / `on-failure` 0 命中 |
| 3 | **`verify_deploy.py` 的 D11 是假断言** | `:226` 的 `want_healthz = "/healthz" in compose` 扫的是**整份 compose 文本（含注释）**。`docker-compose.yml:63-64` 的注释里就写着 `/healthz`，所以**即使把真正的 `test:` 两行删掉，D11 仍然绿** |

> ★ 第 3 条不在本票的成文范围里，但它与第 2 条是同一个形状（「注释里提到」被当成「配置里有」），
> 而且它让「健康检查」这一半也变成恒真。**我不改 `verify_deploy.py`**（那支有人管），
> 只在这里做**真正剥注释的**健康检查断言，并在结论行点名这个差异。

## 断言

  R1  `restart:` 的**真实值**是 `unless-stopped` 或 `always`（按缩进解析到 `services.<x>.restart`，不扫全文）
  R2  `restart` 的取值属于 compose 合法枚举（`no` / `always` / `on-failure` / `unless-stopped`）
  R3  healthcheck **段真的存在**且含 `test` / `interval` / `timeout` / `retries`
      （★ 剥整行注释后再判断；这一条与 D11 的差别写在结论里）
  R4  healthcheck 的 `test` 打的是 `/healthz` 而不是 `/readyz`
  P1  **行为级 0700**：把四个生产数据目录之一 `chmod 0777` → `/readyz` 必须 503 且
      `checks["data_permissions"] is False`
  P2  反向：恢复权限后 `/readyz` 回 200 且 `data_permissions is True`
      （P1/P2 成对 —— 只做 P1 无法区分「真检查了权限」与「readiness 恒 503」）
  B1  **可复现·静态**：Dockerfile 基础镜像不带浮动 tag（`latest` / 无 tag）
  B2  **可复现·静态**：依赖安装走锁定路径（`npm ci` 而非 `npm install`；
      `uv sync --locked` 而非裸 `uv sync`）

## **本文件不证明什么**（结论行必须照抄这一段，不许写大）

* **不证明容器真的会被拉起。** R1/R2 只证明**声明**是 `unless-stopped`。
  Docker 的 restart 策略由 **dockerd** 执行，验证它要起容器、`kill -9` 主进程、读
  `docker inspect --format '{{.RestartCount}}'` —— 那需要 docker daemon 与镜像，
  属部署批次。**「声明对」≠「真的会重启」。**
* **不证明镜像可复现。** B1/B2 只证明 Dockerfile 写的是锁定形式；
  真正「同一份源码构建出同一镜像」要两次 `docker build` 比 digest。
* **不证明目标机上的 compose 与仓内一致。** `docker-compose.yml:41` 的 `env_file`
  指向 `/opt/momcozy-audit-platform/.env.production`，仓内没有那份 compose 的副本。
* P1/P2 是**进程内**行为（TestClient + 真 `stat`），不是容器内行为。

## 退出码

  0 全过 · 1 有红 · 2 未测（读不出 compose/Dockerfile，或无法构造生产 app）

## 用法

    python3 tools/verify_ts15_deploy.py
    python3 tools/verify_ts15_deploy.py --controls
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"

VALID_RESTART = ("no", "always", "on-failure", "unless-stopped")
SAFE_RESTART = ("always", "unless-stopped")


# ── compose 的最小解析器（环境里没有 pyyaml，且只需要读两层）──────────
def compose_service_keys(compose_text, key):
    """按缩进读出 `services.<svc>.<key>` 的值，返回 [(svc, value), ...]。

    ## 为什么不用 `"restart:" in text`

    因为**注释里也可能有**。`docker-compose.yml:63-64` 的注释写着 `/healthz`，
    而 `verify_deploy.py:226` 正是扫全文找这个子串 —— 于是把真正的 `test:` 删掉，
    D11 仍然绿。这是 §2.4「名字出现过 ≠ 拦得住」在 YAML 上的形态。

    这里按缩进定位：`services:` 下缩进 2 的是服务名，服务名下缩进 4 的是键。
    ★ 已知盲区：不做 YAML 语义解析（引号内的 `#`、块标量、锚点都不处理）。
      对这些文件够用，但对任意 compose 不保证 —— 明着留着。
    """
    lines = compose_text.splitlines()
    out = []
    in_services = False
    svc = None
    for ln in lines:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue          # ★ 整行注释不算配置
        indent = len(ln) - len(ln.lstrip())
        s = ln.strip()
        if indent == 0:
            in_services = (s.rstrip() == "services:")
            svc = None
            continue
        if not in_services:
            continue
        if indent == 2 and s.endswith(":"):
            svc = s[:-1]
            continue
        if indent == 4 and svc is not None and s.startswith(key + ":"):
            out.append((svc, s[len(key) + 1:].strip()))
    return out


def compose_service_block(compose_text, service):
    """取某个服务的**原始文本块**（按缩进切），用于查嵌套段（如 healthcheck）。"""
    lines = compose_text.splitlines()
    out = []
    in_services = False
    cur = None
    for ln in lines:
        if not ln.strip():
            if cur == service:
                out.append(ln)
            continue
        indent = len(ln) - len(ln.lstrip())
        s = ln.strip()
        if indent == 0:
            in_services = (s.rstrip() == "services:")
            if cur == service:
                break
            cur = None
            continue
        if not in_services:
            continue
        if indent == 2 and s.endswith(":"):
            if cur == service:
                break
            cur = s[:-1]
            continue
        if cur == service:
            out.append(ln)
    return "\n".join(out)


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def check_restart(compose_text):
    """R1/R2：restart 的真实值必须是安全取值。返回问题列表。

    ★ 这里刻意**不**要求「必须存在 restart」以外的任何东西 ——
      没有 restart 就是 `no`（Docker 默认），那正是行 117 要防的。
    """
    problems = []
    found = compose_service_keys(compose_text, "restart")
    if not found:
        problems.append("没有任何服务声明 restart: —— Docker 默认是 no，容器挂了不会起来")
        return problems
    for svc, val in found:
        if val not in VALID_RESTART:
            problems.append("services.%s.restart = %r 不是合法枚举 %s"
                            % (svc, val, list(VALID_RESTART)))
        elif val not in SAFE_RESTART:
            problems.append("services.%s.restart = %r —— %r 不会在异常退出后自动拉起"
                            % (svc, val, val))
    return problems


def check_healthcheck(compose_text, service="api"):
    """R3/R4：healthcheck 段必须存在且完整，且打 /healthz。

    ★ 与 `verify_deploy.py` 的 D11 的关键差别：
      D11 用 `"/healthz" in compose`（全文，**含注释**），所以删掉真正的 test 行它照样绿。
      这里先按缩进切出 `services.<service>` 的块，再**剥整行注释**，然后才看字段。
    """
    problems = []
    block = compose_service_block(compose_text, service)
    if not block.strip():
        return ["找不到 services.%s 块" % service]
    # 剥整行注释后再查字段
    code = "\n".join(ln for ln in block.splitlines()
                     if not ln.lstrip().startswith("#"))
    if not re.search(r"^\s+healthcheck:\s*$", code, re.M):
        return ["services.%s 没有 healthcheck: 段（容器健康状态无从判断）" % service]
    hc = code[re.search(r"^\s+healthcheck:\s*$", code, re.M).end():]
    for field in ("test", "interval", "timeout", "retries"):
        if not re.search(r"^\s+%s:" % field, hc, re.M):
            problems.append("healthcheck 缺 %s" % field)
    if "/healthz" not in hc:
        problems.append("healthcheck 没打 /healthz")
    if re.search(r"['\"]?\d*/readyz", hc):
        problems.append("healthcheck 打了 /readyz —— 依赖抖动会被算成容器不健康")
    return problems


def check_reproducible(dockerfile_text):
    """B1/B2：基础镜像不许浮动 tag；依赖安装必须走锁定路径。"""
    problems = []
    code = "\n".join(ln for ln in dockerfile_text.splitlines()
                     if not ln.lstrip().startswith("#"))
    for m in re.finditer(r"^FROM\s+(\S+)", code, re.M):
        img = m.group(1)
        if img.startswith("--"):      # FROM --platform=... 之类
            continue
        if ":" not in img:
            problems.append("基础镜像 %r 没有 tag（隐含 :latest，不可复现）" % img)
        elif img.rsplit(":", 1)[-1] in ("latest", "edge", "main", "master"):
            problems.append("基础镜像 %r 用了浮动 tag（不可复现）" % img)
    if re.search(r"\bnpm\s+install\b", code):
        problems.append("用了 npm install（不读 lockfile，版本会漂）")
    if re.search(r"\buv\s+sync\b(?![^\n]*--locked)", code):
        problems.append("有 uv sync 不带 --locked（会重新解析版本）")
    return problems


# ── 行为级 0700（P1/P2）───────────────────────────────────────────────
def probe_permissions():
    """P1/P2：真把目录 chmod 0777，看 /readyz 会不会红；再改回来，看会不会回绿。

    返回 (ok, detail)。无法构造生产 app 时返回 (None, 原因) —— 调用方落未测。
    """
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_vpa_for_ts15", str(ROOT / "tools" / "verify_production_app.py"))
    vpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vpa)
    from api.production_app import create_production_app
    from fastapi.testclient import TestClient

    root = tempfile.mkdtemp(prefix="ts15-perm-")
    try:
        cfg = vpa.settings(root)
        app = create_production_app(cfg, oauth_provider=None)
        with TestClient(app, base_url="https://ca.example") as client:
            rt = app.state.production_runtime
            rt.maintain_once()
            before = client.get("/readyz")
            if before.status_code != 200 or not before.json()["checks"]["data_permissions"]:
                return False, "好样本就不 ready（data_permissions=%r）—— 夹具有问题" % (
                    before.json().get("checks", {}).get("data_permissions"),)

            target = cfg.authority_root
            original = target.stat().st_mode & 0o777
            try:
                os.chmod(str(target), 0o777)
                after = client.get("/readyz")
                perms = after.json()["checks"]["data_permissions"]
                if not (after.status_code == 503 and perms is False):
                    return False, ("chmod 0777 之后 /readyz 是 %s、data_permissions=%r —— "
                                   "权限守卫没有生效" % (after.status_code, perms))
            finally:
                os.chmod(str(target), original)

            back = client.get("/readyz")
            if not (back.status_code == 200 and back.json()["checks"]["data_permissions"] is True):
                return False, ("恢复 %o 之后 /readyz 是 %s、data_permissions=%r —— "
                               "只证明了「会红」，没证明「红的是权限这一项」"
                               % (original, back.status_code,
                                  back.json()["checks"]["data_permissions"]))
            return True, "0777 → 503/False；恢复 %o → 200/True" % original
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 117 / TS-15 · 容器化部署：可复现、0700、健康检查、重启策略")
    print("=" * 72)

    if not COMPOSE.exists() or not DOCKERFILE.exists():
        print("  ⚠ 读不到 compose 或 Dockerfile —— 未测，不是通过")
        return 2

    compose = COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    rest = check_restart(compose)
    vals = dict(compose_service_keys(compose, "restart"))
    check("R1", not rest, "restart 真实取值 %r（会在异常退出后自动拉起）" % vals
          if not rest else str(rest[:2]))
    bad_enum = [p for p in rest if "不是合法枚举" in p]
    check("R2", not bad_enum, "restart 取值在 compose 合法枚举内"
          if not bad_enum else str(bad_enum[:2]))

    hc = check_healthcheck(compose)
    check("R3/R4", not hc,
          "healthcheck 段完整（test/interval/timeout/retries）且打 /healthz"
          if not hc else str(hc[:3]))

    perm_ok, perm_detail = probe_permissions()
    if perm_ok is None:
        print("  ⚠ P1/P2 无法构造生产 app（%s）—— 未测" % perm_detail)
        return 2
    check("P1/P2", perm_ok, "0700 守卫行为级：%s" % perm_detail)

    repro = check_reproducible(dockerfile)
    check("B1/B2", not repro,
          "基础镜像无浮动 tag、依赖安装走锁定路径（npm ci / uv sync --locked）"
          if not repro else str(repro[:3]))

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 只证明：restart 声明为 %s、healthcheck 段完整且打 /healthz、"
          % (vals.get("api", "?"),))
    print("     数据目录 0777 会让 /readyz 503 且恢复后回绿、Dockerfile 用锁定形式装依赖。")
    print("     ★ **不证明**容器真的会被拉起（那要 kill -9 后读 RestartCount，属部署批次）；")
    print("     ★ **不证明**镜像可复现（那要两次 build 比 digest）；")
    print("     ★ **不证明**目标机的 compose 与仓内一致（env_file 指向仓外）。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出。**

    ★ 两条必须成对的（缺一条另一个方向就恒真）：
      · 「注释里提到 restart」→ 必须**不**被当成配置（否则「注释不算配置」没被证）
      · 「真的删掉 restart 行」→ 必须红（否则「有 restart」这个断言可能恒绿）
    """
    if not COMPOSE.exists():
        print("  ⚠ compose 缺失 —— 未测，不是通过")
        return 2
    compose = COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.exists() else ""

    cases = [
        ("好样本：真实 compose", False, lambda: check_restart(compose)),
        ("好样本：真实 healthcheck", False, lambda: check_healthcheck(compose)),
        ("好样本：真实 Dockerfile", False, lambda: check_reproducible(dockerfile)),

        ("坏样本：restart 改成 no",
         True, lambda: check_restart(
             compose.replace("restart: unless-stopped", "restart: no"))),
        ("坏样本：restart 改成 on-failure",
         True, lambda: check_restart(
             compose.replace("restart: unless-stopped", "restart: on-failure"))),
        ("坏样本：删掉 restart 行",
         True, lambda: check_restart(
             "\n".join(l for l in compose.splitlines() if "restart:" not in l))),
        ("坏样本：restart 写成非法枚举",
         True, lambda: check_restart(
             compose.replace("restart: unless-stopped", "restart: sometimes"))),

        # ★ 成对一：注释里提到 restart / healthcheck → 不许当成配置
        ("★ 只有注释里提 restart: always → 必须红（因为真的没有 restart）",
         True, lambda: check_restart(
             "services:\n  api:\n    # restart: always\n    image: x\n")),
        ("★ 注释里提 /healthz、但真 test 行被删 → 必须红（D11 在这里会绿）",
         True, lambda: check_healthcheck(
             compose.replace(
                 '      test: ["CMD", "python3", "-c",\n'
                 '             "import urllib.request,sys;sys.exit(0 if '
                 "urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"
                 '.status==200 else 1)"]\n', ""))),

        ("坏样本：healthcheck 打 /readyz",
         True, lambda: check_healthcheck(
             compose.replace("8000/healthz", "8000/readyz"))),
        ("坏样本：healthcheck 缺 retries",
         True, lambda: check_healthcheck(
             "\n".join(l for l in compose.splitlines() if "retries:" not in l))),

        ("坏样本：基础镜像用 latest",
         True, lambda: check_reproducible(
             dockerfile.replace("python:3.12-slim", "python:latest"))),
        ("坏样本：npm install",
         True, lambda: check_reproducible(dockerfile + "\nRUN npm install\n")),
        ("坏样本：uv sync 去掉 --locked",
         True, lambda: check_reproducible(
             dockerfile.replace("uv sync --locked", "uv sync"))),
    ]

    print("=" * 72)
    print("verify_ts15_deploy · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-52s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 70)
    bad = 0
    for name, want_red, fn in cases:
        try:
            problems = fn()
            got_red = bool(problems)
            note = "" if got_red == want_red else "  ← " + str(problems[:2])[:80]
        except Exception as exc:  # noqa: BLE001
            got_red, note = None, "  对照自身异常：%s" % exc
        ok = (got_red is not None and got_red == want_red)
        bad += int(not ok)
        print("  %-52s %-6s %-6s %s%s"
              % (name[:52],
                 "红" if want_red else "绿",
                 "异常" if got_red is None else ("红" if got_red else "绿"),
                 "✓" if ok else "✗", note))

    print("-" * 72)
    if bad:
        print("❌ %d/%d 与预判不符 —— 差异那几行就是该查的地方" % (bad, len(cases)))
        return 1
    print("✅ %d/%d 预判全部命中：好样本绿、坏样本各自红、注释样本不误报"
          % (len(cases), len(cases)))
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--controls", action="store_true")
    args, unknown = ap.parse_known_args(argv)
    if unknown:
        print("  ⚠ 未知参数 %s —— 未测（不是通过）" % unknown)
        raise SystemExit(2)
    return args


if __name__ == "__main__":
    try:
        a = _parse_args(sys.argv[1:])
        sys.exit(run_controls() if a.controls else main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s: %s" % (type(exc).__name__, exc))
        sys.exit(2)
