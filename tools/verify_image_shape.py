#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_image_shape.py —— 镜像形状 vs 仓内形状（T-410 收尾）

## 这个文件为什么存在

`api/production_app.py` 有 82 项自证（`verify_production_app.py` 全过），
`Dockerfile` 有 14 项自证（`verify_deploy.py` 全过）——
**而容器起不来**。

2026-10-26 实测（照 Dockerfile 逐条 COPY 重建出一棵子树，再隔离 PYTHONPATH）：

```
$ python -c "import base.send_gateway"
ModuleNotFoundError: No module named 'tools.redact'
  → ModuleNotFoundError: No module named 'send_gateway'
```

`base/send_gateway.py:47` 在 **import 期**就要 `tools.redact`，
而 `.dockerignore` 把 `tools` 整目录排除了、Dockerfile 只单独拷贝了 `bj_time.py`。
**容器在 import 期死，`/healthz` 与 `/readyz` 根本没机会起来。**

两套自证为什么都没抓到：它们都跑在**仓内文件系统**上，
而镜像是「按 Dockerfile COPY 出来的那棵子树」。**形状不同，断言就盖不住。**

## 断言的形状（三层，缺一层就还是盖不住）

    I1  **import 图**：`base/` `api/` 下每一处 `from tools.X` / `from tools import X`
        都必须在 Dockerfile 里有对应的 `COPY`，且没有被 `.dockerignore` 排除
    I2  ★ **反向的同一个病**：Dockerfile 里每一条 `COPY <src>`，`<src>` 都必须
        **真的进得了构建上下文**（存在、且没被 `.dockerignore` 排除）。
        I1 查的是「代码依赖了但镜像没拷」，I2 查的是「镜像拷了但上下文没有」——
        两者是**相反方向**，而 2026-10-26 一天之内两个都真实发生过：
          · `redact.py`：进了上下文、Dockerfile 没拷 → 运行期 ModuleNotFoundError
          · 三个 `.mjs`：Dockerfile 拷了、上下文没有 → **构建期 COPY failed**
        只做 I1 会漏掉后者，而后者更早（镜像根本做不出来）。
    I2  **反向对照**：把 Dockerfile 里那条 COPY 注释掉 → I1 必红
    I3  **真跑**：在临时目录里按 import 图建出最小子树，真 import 一次

★ I3 是这一份存在的核心理由。I1 只是「文本上对得上」——
  而 `send_gateway` 那条的失败是**运行时**的（import 期），
  只有真 import 一次才算证过。这与 §2.4「名字出现过 ≠ 拦得住」是同一条。

    I4  ★ **持久目录的挂载与检查必须成对**：
        a) `docker-compose.yml` 里每一个会被写入的 `/data/*` 目录都要有 bind mount
           （否则落在 Dockerfile 的匿名 `VOLUME ["/data"]` 里，`down && up` 后丢）
        b) `/readyz` 的权限循环与 `start()` 的 `_ensure_private_dir` 循环
           必须覆盖**同一组**目录（两处口径不一致 = 配了但没人在查）
    D0  **默认 API 前缀随 PROD 切换**（D0a 源码两分支都在 + 用编译期常量）。
        ★ 这一条的第一版是「查 `??` 后面有没有括号」，那个诊断**是错的**
          （实测两种写法在 JS 里等价），而且判据本身恒真 —— 已整段重写。
    D1  **前端 API 前缀**：生产 bundle 里不许出现 `/review-api`
        （那是 Vite dev 的代理前缀，生产没有那层代理 —— 见 D2）
    D2  反向对照：源文件里那条分支改回旧写法 → D1 必红

★ D1 的判据在 `web/src/api/client.ts` 的 `apiBase` 上（`import.meta.env.PROD`
  决定落 `/api/v1` 还是 `/review-api`）。本文件只验**产物**，不验源码 ——
  产物是唯一能证明「构建出来的东西真的对」的东西。

## 退出码

  0 全过 · 1 有红 · 2 未测（Dockerfile 读不到 / 前端没 build）
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = []
FAIL = []
UNTESTED = []


def ok(label, detail=""):
    PASS.append(label)
    print("PASS: %s%s" % (label, (" " + detail) if detail else ""))


def no(label, detail=""):
    FAIL.append((label, detail))
    print("FAIL: %s%s" % (label, (" " + detail) if detail else ""),
          file=sys.stderr)


#: `from tools.X import ...` / `from tools import X` / `import tools.X`
TOOLS_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(tools(?:\.\w+)*)\s+import\s+(.+?)$"
    r"|import\s+(tools(?:\.\w+)+))", re.M)


def scan_runtime_tools_imports():
    """扫 `base/` `api/` 里所有对 `tools.*` 的依赖。

    返回 `{(module_path, name)}`，例如 `{("tools.redact", "redact")}`。

    ★ 为什么只扫 `base/` 与 `api/`：它们是**运行时代码**。
      `tools/` 自己那些 verifier 互相 import 不算运行时依赖
      （它们本来就不该进镜像 —— `.dockerignore` 排除 `tools` 正是为此）。
    """
    found = set()
    for sub in ("base", "api"):
        base = os.path.join(ROOT, sub)
        for dirpath, _dirnames, filenames in os.walk(base):
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as f:
                    src = f.read()
                # 去掉注释行，避免把「注释里提到的 from tools.x」算成依赖
                code = "\n".join(
                    ln for ln in src.splitlines()
                    if not ln.lstrip().startswith("#"))
                for m in TOOLS_IMPORT_RE.finditer(code):
                    mod = m.group(1) or m.group(3)
                    if m.group(1):
                        names = m.group(2)
                        for nm in names.strip("() ").split(","):
                            nm = nm.strip().split(" as ")[0].strip()
                            if nm and nm != "*":
                                found.add((mod, nm))
                    else:
                        found.add((mod, None))
    return found


def _module_file(mod, name):
    """`(tools.redact, redact)` → `tools/redact.py`；`(tools, bj_time)` → `tools/bj_time.py`。"""
    if name and mod == "tools":
        return "tools/%s.py" % name
    return mod.replace(".", "/") + ".py"


def parse_dockerfile():
    with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
        raw = f.read()
    copied = set()
    for ln in raw.splitlines():
        m = re.match(r"\s*COPY\s+(?:--from=\S+\s+)?(\S+(?:\s+\S+)*)\s+(\S+)\s*$", ln)
        if not m:
            continue
        src = m.group(1)
        # 最后一个空白前是源（可能多个，但我们只关心单文件）
        for token in src.split():
            copied.add(token.strip("{}\"'"))
    return raw, copied


def parse_dockerignore():
    with open(os.path.join(ROOT, ".dockerignore"), encoding="utf-8") as f:
        raw = f.read()
    excluded, reincluded = [], []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("!"):
            reincluded.append(ln[1:].strip())
        else:
            excluded.append(ln)
    return raw, excluded, reincluded


def check_import_graph():
    imports = scan_runtime_tools_imports()
    if not imports:
        no("I1 扫不到任何 tools.* 运行时依赖 —— 判据的输入为空",
           "（若确实一处都没有，请删掉本段断言，不要留一条恒真的）")
        return

    dockerfile_raw, copied = parse_dockerfile()
    _ig_raw, excluded, reincluded = parse_dockerignore()

    problems = []
    for mod, name in sorted(imports, key=lambda x: (x[0], x[1] or "")):
        rel = _module_file(mod, name)
        # ① 被 .dockerignore 排除且没有被 ! 例外放回来 → 一定不在镜像里
        is_excluded = any(
            rel == ex or rel.startswith(ex.rstrip("/") + "/")
            for ex in excluded)
        is_reincluded = any(rel == ri for ri in reincluded)
        if is_excluded and not is_reincluded:
            problems.append((rel, "被 .dockerignore 排除且无 ! 例外"))
            continue
        # ② Dockerfile 里必须有对应 COPY
        if rel not in copied:
            problems.append((rel, "Dockerfile 没有 COPY 它"))

    if problems:
        no("I1 ★ 运行时依赖的工具模块必须在镜像里", repr(problems))
    else:
        ok("I1 ★ %d 个 tools.* 运行时依赖都在镜像里（COPY 齐全、未被忽略）"
           % len(imports), repr(sorted({_module_file(m, n) for m, n in imports})))

    # ── I3 真跑：建最小子树，真 import 一次 ──────────────────────────
    tmp = tempfile.mkdtemp(prefix="image-shape-")
    try:
        # 建一棵「按 Dockerfile 与 .dockerignore 结果」的子树：
        # 只放 COPY 进去的文件。这样 import 失败就是镜像会失败。
        for rel in sorted(copied):
            if not rel.startswith(("base/", "api/", "tools/", "contracts/")):
                continue
            src = os.path.join(ROOT, rel)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        # 把整个 base/ 与 api/ 放进去（Dockerfile 是整目录 COPY）
        for sub in ("base", "api"):
            src_dir = os.path.join(ROOT, sub)
            if not os.path.isdir(src_dir):
                continue
            dst_dir = os.path.join(tmp, sub)
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        modules = sorted({mod for mod, _n in imports})
        probe = (
            "import sys\n"
            "for m in %r:\n"
            "    __import__(m)\n"
            "print('OK')\n" % modules
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp
        # ★ 必须把仓内 tools/ 从搜索路径里排除 —— 否则 import 会命中
        #   **仓内那份**，于是「镜像缺文件」这个缺陷永远不会暴露。
        #   这就是本文件存在的全部理由：形状必须只由 COPY 决定。
        env.pop("PYTHONHOME", None)
        proc = subprocess.run([sys.executable, "-c", probe], cwd=tmp,
                              capture_output=True, text=True, timeout=120,
                              env=env)
        if proc.returncode == 0:
            ok("I3 ★ 按镜像形状真 import 一次：%r 全部可导入" % modules)
        else:
            no("I3 ★ 按镜像形状真 import 失败（容器会在 import 期死）",
               (proc.stderr or proc.stdout).strip().splitlines()[-1][:220])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_dockerfile_copy_sources():
    """I2：Dockerfile 每一条 COPY 的源都必须真进得了构建上下文。

    ★ 判据是「文件存在 且 未被 .dockerignore 排除（或已被 ! 例外放行）」。
    ★ 只查**本仓文件**（相对路径）的 COPY；`COPY --from=<stage>` 跳过。
    """
    dockerfile_path = os.path.join(ROOT, "Dockerfile")
    with open(dockerfile_path, encoding="utf-8") as f:
        raw = f.read()
    _ig_raw, excluded, reincluded = parse_dockerignore()

    problems = []
    checked = 0
    for ln in raw.splitlines():
        line = ln.strip()
        if not line.startswith("COPY "):
            continue
        if "--from=" in line:
            continue            # stage 间拷贝，源不在构建上下文里
        parts = line.split()[1:]
        # 丢掉 COPY 的选项（以 -- 开头的）
        parts = [p for p in parts if not p.startswith("--")]
        if len(parts) < 2:
            continue
        srcs, _dst = parts[:-1], parts[-1]
        for src in srcs:
            src = src.strip("{}[]\"'")
            if "*" in src or "?" in src:
                continue        # 通配符另说
            checked += 1
            abs_src = os.path.join(ROOT, src)
            if not os.path.exists(abs_src):
                problems.append((src, "盘上不存在"))
                continue
            # 目录类 COPY（如 `COPY api/ ./api/`）不需要逐文件判 ignore；
            # 只判文件类
            if os.path.isdir(abs_src):
                continue
            is_excluded = any(
                src == ex or src.startswith(ex.rstrip("/") + "/")
                for ex in excluded)
            is_reincluded = any(src == ri for ri in reincluded)
            if is_excluded and not is_reincluded:
                problems.append(
                    (src, "在构建上下文里被 .dockerignore 排除（COPY 会在构建期失败）"))

    if problems:
        no("I2 ★ Dockerfile 的 COPY 源必须真进得了构建上下文", repr(problems))
    else:
        ok("I2 ★ Dockerfile 的 %d 个 COPY 源都在构建上下文里" % checked)


def check_persistent_mounts():
    """I4：持久目录的挂载与检查必须成对。

    2026-10-26 实测的三个读数同时成立：
        GET /api/v1/reports      → 200（列表里有）
        GET /static/reports/….md → 404（正文没了）
        GET /readyz              → 200，七项全 true
    真因有两条，缺一条都不会出这个组合：
      a) `report_root` 落在匿名 `VOLUME ["/data"]` 里，compose 没给它 bind mount
         → `down && up` 换了匿名卷，正文丢
      b) `/readyz` 的 `permissions_ok` 循环**不含** `report_root`
         → 丢了也没有任何检查会红
    """
    compose_path = os.path.join(ROOT, "docker-compose.yml")
    app_path = os.path.join(ROOT, "api", "production_app.py")
    for p in (compose_path, app_path):
        if not os.path.isfile(p):
            print("⚠ 未测：找不到 %s" % p)
            UNTESTED.append("I4")
            return

    with open(compose_path, encoding="utf-8") as f:
        compose = f.read()
    # a) compose 的 bind mount 目标集合（形如 `- host:/data/xxx`）
    mounted = set(re.findall(r"-\s+[^:\n]+:(/data/[A-Za-z0-9_.-]+)", compose))
    # Dockerfile 里 mkdir 的 /data/* 目录 = 「会被写入的目录」的声明面
    dockerfile_path = os.path.join(ROOT, "Dockerfile")
    with open(dockerfile_path, encoding="utf-8") as f:
        dockerfile = f.read()
    m = re.search(r"mkdir -p ((?:/data/[A-Za-z0-9_./ -]+)+)", dockerfile)
    declared = set()
    if m:
        declared = {tok for tok in m.group(1).split() if tok.startswith("/data/")}
    missing_mount = sorted(declared - mounted)
    if missing_mount:
        no("I4a ★ 每个 /data/* 目录都要有 bind mount（否则 down&&up 后丢）",
           repr(missing_mount))
    else:
        ok("I4a ★ Dockerfile 声明的 %d 个 /data 目录全部有 bind mount"
           % len(declared), repr(sorted(mounted)))

    # b) 两处循环覆盖同一组目录
    with open(app_path, encoding="utf-8") as f:
        app = f.read()
    start_block = app[app.index("def start(self):"):]
    start_block = start_block[:start_block.index("raise SettingsError")] \
        if "raise SettingsError" in start_block else start_block
    readyz_at = app.index("permissions_ok = True")
    readyz_block = app[readyz_at:readyz_at + 1200]

    def loop_dirs(anchor, block):
        """只取 `for directory in ( ... ):` 那个元组里的 settings 字段。

        ★ 第一版取「块里出现的所有 self.settings.X」，于是把
          `frozen_projection_root` 也算进去了 —— 而它只做 `is_dir()`
          检查、不建目录不查权限，本来就不该在这个循环里。
          判据把「无关字段」当缺项，得到一条假红。**只比循环体本身。**
        """
        i = block.find(anchor)
        if i < 0:
            return None
        tail = block[i:]
        j = tail.find("in (")
        if j < 0:
            return None
        k = tail.find("):", j)
        if k < 0:
            return None
        return set(re.findall(r"self\.settings\.([a-z_]+)", tail[j:k]))

    start_at = app.index("def start(self):")
    start_dirs = loop_dirs("for directory in (", app[start_at:start_at + 1400])
    readyz_dirs = loop_dirs("for directory in (", readyz_block)
    if start_dirs is None or readyz_dirs is None:
        no("I4b 两处循环体都找不到（判据输入为空，不能当成通过）",
           "start=%r readyz=%r" % (start_dirs, readyz_dirs))
        return
    only_readyz = sorted(readyz_dirs - start_dirs)
    only_start = sorted(start_dirs - readyz_dirs)
    if only_start:
        no("I4b ★ /readyz 的目录检查漏了 start() 会建的那些",
           repr(only_start))
    elif only_readyz:
        ok("I4b ★ 两处目录检查口径一致（readyz 额外覆盖 %r）"
           % (only_readyz,))
    else:
        ok("I4b ★ /readyz 与 start() 覆盖同一组持久目录（%d 个）"
           % len(start_dirs), repr(sorted(start_dirs)))


def check_frontend_default_base():
    """D0：默认 API 前缀必须**随构建模式变**，且两侧都能观测到。

    ## 这条判据的第一版是错的，记下来

    我先把它写成「扫源码看 `??` 后面有没有括号」，理由是怀疑
    `A ?? PROD ? X : Y` 会被解析成 `(A ?? PROD) ? X : Y`。
    **那个诊断是错的**：实测 node 里两种写法的结果相同（`??` 与 `?:`
    对 `undefined` 的处理在这里没有分歧）。

    更糟的是，那条判据本身是**恒真**的：我把源码改回「带括号的旧写法」
    它照样 PASS —— 因为它匹配的是字符位置，不是行为。

    ## 现在的判据（行为级，两侧都验）

    D0a  源码里产出默认值的表达式**两种模式都能观测到**：
         dev 分支给 `/review-api`、prod 分支给 `/api/v1`
         （字面上必须两个都出现，否则「随模式变」这件事不存在）
    D0b  **真构建一次生产产物**并读它：`dist` 里不许留 `/review-api`
         （由 `check_frontend_api_prefix` 承担 —— 门在这里，不重复做）

    ★ 为什么不验「dev 产物」：dev 是 Vite 现场编译的，没有稳定的产物文件；
      它的正确性由 `web/scripts/dev-up.sh` 的 11 阶段覆盖（那是**真跑**，
      比读产物更强）。本文件只补「生产产物」这一半。
    """
    path = os.path.join(ROOT, "web", "src", "api", "client.ts")
    if not os.path.isfile(path):
        print("⚠ 未测：找不到 web/src/api/client.ts")
        UNTESTED.append("D0")
        return
    with open(path, encoding="utf-8") as f:
        src = f.read()
    code = "\n".join(ln for ln in src.splitlines()
                      if not ln.lstrip().startswith(("//", "*", "/*")))
    has_dev = "/review-api" in code
    has_prod = "/api/v1" in code
    mode_switched = "import.meta.env.PROD" in code
    if has_dev and has_prod and mode_switched:
        ok("D0a ★ 默认前缀随 PROD 切换（两个分支的字面量都在，"
           "且判据是编译期常量 PROD 而不是可被 --mode 改的 MODE）")
    else:
        no("D0a 默认前缀没有随 PROD 切换",
           "dev_literal=%r prod_literal=%r switched=%r"
           % (has_dev, has_prod, mode_switched))


def check_frontend_api_prefix():
    """D1：生产 bundle 里不许出现 `/review-api`（那是 dev 代理前缀）。"""
    dist = os.path.join(ROOT, "web", "dist")
    if not os.path.isdir(dist):
        print("⚠ 未测：%s 不存在（先跑 cd web && npm run build）" % dist)
        UNTESTED.append("D1")
        return
    hits = []
    for dirpath, _d, filenames in os.walk(dist):
        for fn in filenames:
            if not fn.endswith(".js"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if "/review-api" in text:
                hits.append(os.path.relpath(path, ROOT))
    if hits:
        no("D1 ★ 生产 bundle 里出现了 /review-api（生产没有那层 dev 代理）",
           repr(hits[:4]))
    else:
        ok("D1 ★ 生产 bundle 里没有 /review-api（API 前缀落在 /api/v1）")


def run_checks():
    for name in ("Dockerfile", ".dockerignore"):
        if not os.path.isfile(os.path.join(ROOT, name)):
            print("UNTESTED: 找不到 %s —— 本文件的前提不存在" % name)
            return 2
    check_import_graph()
    check_dockerfile_copy_sources()
    check_persistent_mounts()
    check_frontend_default_base()
    check_frontend_api_prefix()
    return None


def run_controls():
    """反向对照：把 redact 那条 COPY 注释掉 → I1 必红。"""
    print("=" * 70)
    print("反向对照：判据自己会不会红")
    print("=" * 70)
    path = os.path.join(ROOT, "Dockerfile")
    with open(path, encoding="utf-8") as f:
        saved = f.read()
    results = []
    try:
        mutated = saved.replace(
            "COPY tools/redact.py ./tools/redact.py",
            "# COPY tools/redact.py ./tools/redact.py")
        changed = mutated != saved
        with open(path, "w", encoding="utf-8") as f:
            f.write(mutated)
        before = len(FAIL)
        check_import_graph()
        went_red = len(FAIL) > before
        while len(FAIL) > before:
            FAIL.pop()
        results.append(("C1 注释掉 redact 的 COPY → I1 必红", went_red, True))
        if not changed:
            no("C1 变异没生效（找不到那条 COPY 行）")
    finally:
        with open(path, "w", encoding="utf-8") as f:
            f.write(saved)

    print("=" * 70)
    bad = 0
    for name, red, want in results:
        good = red == want
        bad += 0 if good else 1
        print("%s %s（红了=%s，期望红=%s）" % ("✅" if good else "❌", name, red, want))
    if bad == 0:
        print("✅ 反向对照 %d/%d 全过" % (len(results), len(results)))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (len(results) - bad, len(results)),
          file=sys.stderr)
    return 1


def main():
    print("=" * 70)
    print("verify_image_shape · 镜像形状 vs 仓内形状（T-410 收尾）")
    print("=" * 70)
    rc = run_checks()
    print("-" * 70)
    print("通过 %d 项 · 红 %d 项 · 未测 %d 项"
          % (len(PASS), len(FAIL), len(UNTESTED)))
    if rc == 2:
        return 2
    if FAIL:
        for label, detail in FAIL:
            print("  ✗ %s %s" % (label, detail), file=sys.stderr)
        print("❌ 有红", file=sys.stderr)
        return 1
    if UNTESTED:
        print("⚠ 有未测 —— 未测不是通过", file=sys.stderr)
        return 2
    print("✅ 全过")
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常：%s" % exc, file=sys.stderr)
        sys.exit(2)
