#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_dependency_lock.py —— 验收表行 106 / TS-3「依赖锁定安装：没有锁就装不上」

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md`，覆盖判据 `TS-3`）

> 依赖锁定安装：**没有锁就装不上**。

## 这一票真正要补的洞：一句注释没有执行点

`pyproject.toml:13` 写着：

    # 开发/CI/生产必须 `uv sync --locked`（G-02）；不许无锁安装。

那是**注释**。按 `AGENTS.md` §2.4「写进文档的每一个上限，必须能指出是哪一行代码在拦它」——
此前全仓指不出。实测：

    $ grep -c -- '--locked' tools/verify_deploy.py
    0

`verify_deploy.py` 的 D1–D11 里**没有一条**查依赖锁定。所以 G-02 这句话当时只是一句愿望。
本文件就是它的执行点。

## 断言

  L1  两个文件都在盘上，且**都被 git 跟踪**（未跟踪的锁文件在公开仓里等于没有锁）
  L2  `pyproject.toml` 与 `uv.lock` 的 `requires-python` **逐字相等**
  L3  每个直接依赖都精确 `==` 钉住，且 `uv.lock` 里同名包的 version **完全相等**
      （出现 `^` / `~` / `>=` 范围即红 —— 那正是「改了版本却不重锁」的入口）
  L4  **行为面（有锁）**：`uv sync --locked --dry-run --offline` rc=0
  L5  **行为面（无锁，本行核心判据）**：把 `pyproject.toml` 拷到临时空目录、
      **不拷 `uv.lock`**，同一命令必须 rc≠0 且 stderr 提到 lockfile
  L6  **G-02 的执行点**：`Dockerfile` 里每条 `uv sync` 都必须带 `--locked`；
      不允许出现不带 `--locked` 的 `uv sync` 或 `pip install`
  L7  `uv.lock` 不被 `.dockerignore` 排除（被排除 = 镜像里没有锁，L6 形同虚设）

## 反向对照（`--controls`）

  见 `run_controls()` —— 每条样本**先写预判、再跑、并列贴出**。
  这是 2026-10-22 定下的规矩：写对照时人想的是「这样应该会红」，
  而不是「这样真的会红吗」。预判与实测并列，差异处就是要查的地方。

## 退出码

  0 全过 · 1 有红 · 2 未测（uv 不在 PATH / 读不出文件）

## 已知盲区（明着留着）

* **L5 证明的是「`uv` 遇到 `--locked` 但没有锁文件会失败」**，不是「镜像里装不上东西」。
  真正「没有锁就装不上」的端到端证明要构建镜像，属部署批次。
  本文件只证明：**在 `--locked` 语义下，缺锁是一个明确错误而不是静默从网上解析**。
* `uv` 不在 PATH 时整份**退 2（未测）**，不退 0 —— 结构断言过了也不算数，
  因为 L4/L5 是本行的主体（「装不上」只能行为验证）。

## 用法

    python3 tools/verify_dependency_lock.py
    python3 tools/verify_dependency_lock.py --controls
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
UVLOCK = ROOT / "uv.lock"
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"

UV_TIMEOUT = 60


def find_uv():
    """找 uv 可执行文件。找不到返回 None（调用方据此退 2，不是退 1）。"""
    hit = shutil.which("uv")
    if hit:
        return hit
    for cand in (Path.home() / ".local" / "bin" / "uv",
                 Path("/opt/homebrew/bin/uv"),
                 Path("/usr/local/bin/uv")):
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def run_uv(uv, args, cwd):
    """跑一条 uv 命令，返回 (rc, stdout, stderr)。超时/找不到都折算成 None。"""
    try:
        p = subprocess.run([uv] + args, cwd=str(cwd), capture_output=True,
                           text=True, timeout=UV_TIMEOUT,
                           env={**os.environ, "UV_NO_PROGRESS": "1"})
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, OSError):
        return None, "", ""


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def direct_requirements(pyproject_text):
    """从 pyproject 里取出「直接依赖」的 (名字, 约束) 列表，含 dev 组。"""
    data = tomllib.loads(pyproject_text)
    specs = list(data.get("project", {}).get("dependencies") or [])
    for group in (data.get("dependency-groups") or {}).values():
        specs.extend(s for s in group if isinstance(s, str))
    out = []
    for spec in specs:
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$", spec)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def lock_versions(uvlock_text):
    """uv.lock 里 name → version（**不含根项目**）。

    ★ 2026-10-22 修正：`uv.lock` 里 15 个 `[[package]]` 块中，有 1 个是**根项目自己**
      （`source = { virtual = "." }`，名字就是 `audit-multi-content`），
      与 `pyproject.toml` 的 `[tool.uv] package = false` 对应。
      它不是一个可从 PyPI 装到的包，把它算进「依赖」会让计数口径失真
      （`uv` 自己也是分开报的：`Resolved 15 packages` / `Checked 14 packages`）。
      所以这里剔掉根项目，只返回 registry 包。
    """
    data = tomllib.loads(uvlock_text)
    out = {}
    for p in data.get("package") or []:
        if (p.get("source") or {}).get("virtual"):
            continue
        out[p["name"]] = p.get("version")
    return out


def lock_declared_requirements(uvlock_text):
    """读 `uv.lock` 里根项目自带的 **机器可读声明**（`[package.metadata]`）。

    ★ 2026-10-22 加固：`uv.lock:32-40` 的 `dependencies` / `dev-dependencies` 段
      **只记名字、不记版本**；带 specifier 的是 `:42-50` 的
      `metadata.requires-dist` 与 `metadata.requires-dev`。
      这段是 uv 自己写下的「我认为 pyproject 要求什么」——
      拿它和 pyproject 对拍，比只比 resolved version **多一层**：
      resolved version 相等只能证明「这次锁的碰巧对」，
      而 metadata 相等证明「uv 也认为 pyproject 是这么写的」。
      两者都过，才是「两处一致」。

    返回 (dist: {name: specifier}, dev: {name: specifier}, 根项目名)。
    """
    data = tomllib.loads(uvlock_text)
    roots = [p for p in data.get("package") or [] if (p.get("source") or {}).get("virtual")]
    if not roots:
        return None, None, None
    root = roots[0]
    meta = root.get("metadata") or {}
    dist = {d["name"]: d.get("specifier") for d in meta.get("requires-dist") or []}
    dev = {}
    for entries in (meta.get("requires-dev") or {}).values():
        for d in entries or []:
            dev[d["name"]] = d.get("specifier")
    return dist, dev, root.get("name")


def check_pins(pyproject_text, uvlock_text):
    """L3：直接依赖必须精确 ==，且 lock 里的版本相同 **且 lock 的 metadata 声明也相同**。"""
    problems = []
    locked = lock_versions(uvlock_text)
    declared_dist, declared_dev, _root = lock_declared_requirements(uvlock_text)
    declared = {}
    if declared_dist is not None:
        declared.update(declared_dist)
        declared.update(declared_dev or {})

    for name, cons in direct_requirements(pyproject_text):
        if not cons.startswith("=="):
            problems.append("%s 的约束是 %r —— 不是精确 ==（范围会让「改了版本不重锁」变成合法）"
                            % (name, cons or "（空）"))
            continue
        want = cons[2:].strip()
        got = locked.get(name)
        if got is None:
            problems.append("%s 在 uv.lock 里不存在（pyproject 要 %s）" % (name, want))
        elif got != want:
            problems.append("%s pyproject 钉 %s，uv.lock 里是 %s —— 两处不一致"
                            % (name, want, got))
        # ★ 第二层：lock 自己记的声明也必须与 pyproject 相同
        if declared_dist is not None:
            d = declared.get(name)
            if d != cons:
                problems.append("%s uv.lock 的 metadata 声明是 %r，pyproject 是 %r —— "
                                "锁文件没跟上 pyproject" % (name, d, cons))
    return problems


def check_requires_python(pyproject_text, uvlock_text):
    """L2：requires-python 逐字相等。"""
    py = tomllib.loads(pyproject_text).get("project", {}).get("requires-python")
    lk = tomllib.loads(uvlock_text).get("requires-python")
    if py is None or lk is None:
        return ["requires-python 缺失：pyproject=%r uv.lock=%r" % (py, lk)]
    if py != lk:
        return ["requires-python 不一致：pyproject=%r uv.lock=%r" % (py, lk)]
    return []


def check_dockerfile_locked(dockerfile_text):
    """L6：每条 uv sync 必须带 --locked；不许出现 pip install。返回问题列表。

    ★ 剥整行注释（与 verify_deploy.py 的 D2 同一条读法）：
      Dockerfile:11-12 的注释里写着「必须 uv sync --locked」，不剥就会把它
      当成一条真的 uv sync 命令 —— 而它没有 --locked，于是假红。
      **这正是 D2 第一版踩过的坑。**
    """
    problems = []
    code = "\n".join(ln for ln in dockerfile_text.splitlines()
                     if not ln.lstrip().startswith("#"))
    for i, ln in enumerate(code.splitlines(), 1):
        if "uv sync" in ln and "--locked" not in ln:
            problems.append("Dockerfile 有未加 --locked 的 uv sync：%r" % ln.strip())
        if re.search(r"\bpip\s+install\b", ln):
            problems.append("Dockerfile 用了 pip install（绕过锁）：%r" % ln.strip())
    if "uv sync" not in code:
        problems.append("Dockerfile 里一条 uv sync 都没有 —— 依赖是怎么装的？")
    return problems


def check_dockerignore(dockerignore_text):
    """L7：uv.lock 不许被 .dockerignore 排除。"""
    problems = []
    for ln in dockerignore_text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("!"):
            continue
        if s in ("uv.lock", "*.lock", "*.toml", "uv*", "*"):
            problems.append(".dockerignore 的 %r 会把 uv.lock 排除在构建上下文外 —— "
                            "镜像里就没有锁了" % s)
    return problems


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 106 / TS-3 · 依赖锁定安装：没有锁就装不上")
    print("=" * 72)

    missing = [p.name for p in (PYPROJECT, UVLOCK) if not p.exists()]
    if missing:
        print("  ⚠ 读不到 %s —— 未测，不是通过" % missing)
        return 2

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    uvlock = UVLOCK.read_text(encoding="utf-8")

    # ── L1 存在且入库 ────────────────────────────────────────────────
    tracked = []
    for name in ("pyproject.toml", "uv.lock"):
        p = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", name],
                           capture_output=True, text=True)
        tracked.append(p.returncode == 0)
    check("L1", all(tracked),
          "两个文件都在盘上且都被 git 跟踪（未跟踪的锁文件等于没有锁）"
          if all(tracked) else
          "pyproject 跟踪=%s / uv.lock 跟踪=%s" % tuple(tracked))

    # ── L2 requires-python ──────────────────────────────────────────
    rp = check_requires_python(pyproject, uvlock)
    check("L2", not rp, "requires-python 两处逐字相等" if not rp else str(rp))

    # ── L3 精确钉版本 + lock 一致 ───────────────────────────────────
    pins = check_pins(pyproject, uvlock)
    n_direct = len(direct_requirements(pyproject))
    check("L3", not pins,
          "%d 个直接依赖全部精确 == 且与 uv.lock 一致" % n_direct
          if not pins else str(pins[:4]))

    # ── L6 Dockerfile 必须 --locked（G-02 的执行点）──────────────────
    if DOCKERFILE.exists():
        df = check_dockerfile_locked(DOCKERFILE.read_text(encoding="utf-8"))
        check("L6", not df,
              "Dockerfile 的 uv sync 全部带 --locked（G-02 的执行点）"
              if not df else str(df[:3]))
    else:
        print("  ⚠ 无 Dockerfile —— L6 未测")

    # ── L7 .dockerignore 不许排除 uv.lock ───────────────────────────
    if DOCKERIGNORE.exists():
        di = check_dockerignore(DOCKERIGNORE.read_text(encoding="utf-8"))
        check("L7", not di, "uv.lock 未被 .dockerignore 排除"
              if not di else str(di[:2]))
    else:
        print("  ⚠ 无 .dockerignore —— L7 未测")

    # ── L4 / L5 行为面：uv 不可用 → 整份未测 ────────────────────────
    uv = find_uv()
    if uv is None:
        print("  ⚠ uv 不在 PATH，也找不到 ~/.local/bin、/opt/homebrew/bin —— "
              "L4/L5 无法实测")
        print("⚠ 未测：结构断言通过≠本行成立。本行的主体是「装不上」，只能行为验证。")
        return 2

    rc4, out4, err4 = run_uv(uv, ["sync", "--locked", "--dry-run", "--offline",
                                  "--no-install-project"], ROOT)
    if rc4 is None:
        print("  ⚠ uv 执行超时/失败 —— L4 未测")
        return 2
    check("L4", rc4 == 0,
          "有锁：uv sync --locked --dry-run --offline rc=0（锁可复现）"
          if rc4 == 0 else "有锁时 uv 失败 rc=%s：%s" % (rc4, (err4 or out4)[:200]))

    # L5 的核心：**只拷 pyproject，不拷 uv.lock**
    tmp = tempfile.mkdtemp(prefix="dep-lock-nolock-")
    try:
        shutil.copyfile(PYPROJECT, Path(tmp) / "pyproject.toml")
        rc5, out5, err5 = run_uv(uv, ["sync", "--locked", "--dry-run", "--offline",
                                      "--no-install-project"], tmp)
        if rc5 is None:
            print("  ⚠ uv 执行超时/失败 —— L5 未测")
            return 2
        blob = (err5 or "") + (out5 or "")
        said_lock = bool(re.search(r"lockfile|uv\.lock", blob, re.I))
        check("L5", rc5 != 0 and said_lock,
              "无锁：uv sync --locked rc=%s 且明确提到 lockfile（缺锁是错误，不是静默解析）"
              % rc5
              if (rc5 != 0 and said_lock) else
              "无锁时 rc=%s、提到 lockfile=%s —— 缺锁没有被拦成明确错误"
              % (rc5, said_lock))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 只证明：锁存在且入库、与 pyproject 一致、")
    print("     有锁能装、**无锁装不上**、Dockerfile 与 .dockerignore 都保住了锁。")
    print("     ★ 不证明镜像里真装得上/装不上 —— 那要 docker build，属部署批次。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出**（2026-10-22 定下的规矩）。

    为什么预判要写出来：写对照时人想的是「这样应该会红」，而不是
    「这样真的会红吗」。预判与实测并列，差异那一行就是该查的地方。
    """
    if not (PYPROJECT.exists() and UVLOCK.exists()):
        print("  ⚠ 真源缺失 —— 未测，不是通过")
        return 2

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    uvlock = UVLOCK.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.exists() else ""

    # (名称, 预判「会不会红」, 调用)
    cases = [
        ("好样本：真实 pyproject + 真实 uv.lock",
         False, lambda: check_pins(pyproject, uvlock)),

        ("坏样本：pyproject 把 fastapi 改成范围 ^",
         True, lambda: check_pins(
             pyproject.replace('"fastapi==0.115.6"', '"fastapi>=0.115.0"'), uvlock)),

        ("坏样本：pyproject 钉 0.115.5 但 lock 还是 0.115.6",
         True, lambda: check_pins(
             pyproject.replace('"fastapi==0.115.6"', '"fastapi==0.115.5"'), uvlock)),

        ("坏样本：lock 里删掉一个直接依赖",
         True, lambda: check_pins(
             pyproject,
             uvlock.replace('name = "uvicorn"', 'name = "uvicorn-not"' ))),

        # ★ 2026-10-22 加固层：resolved version 相同、但 lock 自己记的**声明**写成范围。
        #   只比 resolved version 抓不到这一条 —— 那道题必须靠 metadata 对拍。
        #   这一项存在的理由就是证明「加固那一层真的在拦」。
        ("★ 坏样本：resolved 相同但 lock metadata 声明是范围",
         True, lambda: check_pins(
             pyproject,
             uvlock.replace('specifier = "==0.115.6"', 'specifier = ">=0.115.0"'))),

        ("坏样本：requires-python 不一致",
         True, lambda: check_requires_python(
             pyproject.replace('requires-python = ">=3.12"',
                               'requires-python = ">=3.11"'), uvlock)),

        ("坏样本：Dockerfile 去掉 --locked",
         True, lambda: check_dockerfile_locked(
             dockerfile.replace("uv sync --locked", "uv sync"))),

        ("坏样本：Dockerfile 用 pip install",
         True, lambda: check_dockerfile_locked(
             dockerfile + "\nRUN pip install fastapi\n")),

        # ★ 这一条是「剥注释」的成对证伪：注释里写着 --locked 的那两行不能被当成
        #   真命令，否则会假红。Dockerfile:11-12 真实存在这样的注释。
        ("★ 只有注释里提 uv sync（无 --locked）→ 必须绿",
         False, lambda: check_dockerfile_locked(
             "# 必须 uv sync --locked\n# 不要用 pip install\n"
             "FROM python:3.12-slim\nRUN uv sync --locked --no-dev\n")),

        ("坏样本：.dockerignore 排除 uv.lock",
         True, lambda: check_dockerignore("uv.lock\n*.pem\n")),

        ("好样本：.dockerignore 只排无关项",
         False, lambda: check_dockerignore(".git\nnode_modules\n*.pem\n")),
    ]

    print("=" * 72)
    print("verify_dependency_lock · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-46s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 66)
    bad = 0
    for name, want_red, fn in cases:
        try:
            problems = fn()
            got_red = bool(problems)
            note = "" if (got_red == want_red) else "  ← " + str(problems[:2])[:90]
        except Exception as exc:  # noqa: BLE001
            got_red, note = None, "  对照自身异常：%s" % exc
        ok = (got_red is not None and got_red == want_red)
        bad += int(not ok)
        print("  %-46s %-6s %-6s %s%s"
              % (name[:46],
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
        # argparse 默认对未知参数退 2，而验收执行器把 2 读成「未测」。
        # 明说一句，否则手误会被静默吞成未测。
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
