#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_cpu_first.py —— 验收表行 119 / TS-17「阶段一 CPU 优先，不预设 GPU」

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:262`）

> 断言编排定义里没有默认 GPU 依赖（缺 GPU 时必须能起）。构造一次时延或准确率不达标的场景，
> 断言系统**输出显式读数**（慢多少、差多少、卡在哪）并要求人决策，而不是自动扩容或静默降级。

## 这个验证器覆盖哪一半，**不覆盖**哪一半（先说清楚，结论行才不许写大）

| 行里的要求 | 本文件 | 怎么验 |
|---|---|---|
| 编排定义里没有默认 GPU 依赖 | ✅ | 静态：compose / Dockerfile / pyproject / uv.lock |
| 不达标时输出**显式读数** | ✅ **行为级** | 真造「慢且错 / 缺 gold / 引擎抛异常」三张样本，断言逐条读数与 reason |
| 不自动扩容 / 不静默降级 | ✅ | 静态扫代码 + 行为断言「异常一律 untested，不许 ok 兜底」 |
| **「缺 GPU 时必须能起」** | ❌ **未测** | 见下 |
| 要求**人**决策 | ⚠ 部分 | 只断言「没有任何一处写 released/已放行」，见 D 段 |

> ★ **「缺 GPU 时必须能起」这一条本文件不验，也不许把它算作已验。**
> 真验它要拉镜像、起容器、看 RestartCount —— 那是 `verify_deploy.py` 的 `--remote`
> （至今未实现，见其文件头第 12 行）与部署批次的事。本文件只做**静态**断言：
> 编排定义与依赖里不存在任何 GPU 依赖。
> 两者是**不同的事**：静态无 GPU 依赖 ≠ 在无 GPU 机器上真的起得来。
> 把前者写成后者，就是 `AGENTS.md` §2.4.1 的「这句话比我的输入大」。

## 断言

  A1  编排定义（compose/Dockerfile）**剥掉整行注释后**无 GPU 预留键
  A2  基础镜像不是 GPU 镜像（nvidia/cuda、pytorch/pytorch、rocm/*）
  A3  依赖清单（pyproject/uv.lock）无 GPU-only 包
  A4  **反向对照（每次主检查都跑）**：注释里写 `nvidia` → 必须**不**报；真配置 → 必须报
  B1  慢且错 → 同时给出 `ms` 与 `cer` 两个读数（「慢多少」「差多少」）
  B2  缺 gold → `untested` + 非空 `reason`，且 **`cer`/`ms` 必须是 null 不是 0**（「卡在哪」）
  B3  引擎抛异常 → `untested` + 非空 reason，不许 ok
  C1  代码里无自动扩容（autoscaling / replicas / --scale / service scale）
  C2  **反向对照**：只在注释与 docstring 里出现这些词 → 必须**不**报
  D1  media / benchmark 路径没有一处写 `released` / `已放行`

## 退出码

  0 全过 · 1 有红 · 2 未测（读不出源文件 / 依赖部件导入失败）

## 已知盲区（明着留着，不藏）

* 只剥**整行**注释。行尾注释仍会被扫到 —— 与 `verify_deploy.py` 的 D2、
  `verify_shouheng_ops.py` 的 C5、`verify_cards.mjs` 的 J1a 同一条读法、同一个盲区。
* 文件发现走 `git ls-files`：`research/repos/ad-review-agent/` 下有一份**未跟踪**的
  Dockerfile/compose 副本（`.gitignore:46`），用 `find **/Dockerfile` 会多抓一份
  （实测那份里 GPU 相关是 0 命中，抓了也不会红，但「扫了什么」会说不清）。

## 用法

    python3 tools/verify_cpu_first.py
    python3 tools/verify_cpu_first.py --controls
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"
PYPROJECT = ROOT / "pyproject.toml"
UVLOCK = ROOT / "uv.lock"

# ── 判据词表（逐个点名，不用模糊匹配）──────────────────────────────────
#   ★ 为什么不用 `gpu|nvidia|cuda` 一把扫：本仓有已知假阳性 ——
#     `base/media.py:1153` 的规则词表里有 "medical device"（内容合规用词），
#     `tools/node_modules/@larksuiteoapi/node-sdk` 的 "meetingPullSubtitle" 里含 `gPu`。
#     误报比不报更糟（§2.1.1）：一个会误报的检查器会让人开始不看报告。
GPU_RESERVE_KEYS = (
    "deploy.resources.reservations.devices",
    "capabilities: [gpu]",
    "driver: nvidia",
    "runtime: nvidia",
    "gpus:",
    "NVIDIA_VISIBLE_DEVICES",
    "--gpus",
)
GPU_BASE_IMAGES = (
    "nvidia/cuda",
    "nvcr.io/nvidia",
    "pytorch/pytorch",
    "tensorflow/tensorflow:",
    "rocm/",
)
GPU_PACKAGES = (
    "torch",
    "cupy",
    "paddlepaddle-gpu",
    "onnxruntime-gpu",
    "tensorflow-gpu",
    "jax[cuda",
    "nvidia-cuda",
)
AUTOSCALE_WORDS = (
    "autoscaling",
    "auto_scaling",
    "scale_out",
    "scale_out_policy",
    "service scale",
    "--scale",
    "deploy.replicas",
    "horizontalpodautoscaler",
)
# ★ `replicas:` 单独不列 —— compose 里它也可以是合法的单副本声明。
#   行 119 要的是「不自动扩容」，所以只拦「自动」的那几种写法。

RELEASE_WORDS = ("released", "已放行", "release_status = \"放行")


# ── 通用 ──────────────────────────────────────────────────────────────
def strip_line_comments(text: str) -> list[tuple[int, str]]:
    """剥掉**整行**注释，返回 (原始行号, 内容)。

    与 `verify_deploy.py:112-114` / `verify_shouheng_ops.py:312` 同一条读法：
    整行以 `#` 开头（允许前置空白）就不算代码。
    ★ 已知盲区：行尾注释仍会被扫到 —— 宁可偶尔吵，不可漏。
    """
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        out.append((i, ln))
    return out


def code_only(text: str) -> str:
    return "\n".join(ln for _, ln in strip_line_comments(text))


def strip_py_docstrings(text: str) -> str:
    """剥 Python 的 docstring 与整行注释。

    ★ 为什么要剥 docstring：`benchmark_media.py` 的 docstring 里写着
      「未测 ≠ 通过 ≠ 红」等说明文字，`base/media.py` 的 docstring 里解释
      「为什么不能编数字」。不剥的话，`C2` 的反向对照会把这些**说明**当成违规。
    """
    text = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', "", text, flags=re.S)
    text = re.sub(r"'''(?:[^'\\]|\\.|'(?!''))*'''", "", text, flags=re.S)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def git_tracked(pattern: str) -> list[str]:
    """只用 git 的跟踪集合发现文件 —— `find` 会抓到 gitignored 的第三方副本。"""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", pattern],
                             capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return []
        return [ln for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        return []


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def check_gpu_keys(compose_text, dockerfile_text):
    """A1/A2：编排定义里不许有 GPU 预留键与 GPU 基础镜像。返回问题列表。"""
    problems = []
    for label, text in (("docker-compose.yml", compose_text),
                        ("Dockerfile", dockerfile_text)):
        code = code_only(text)
        for key in GPU_RESERVE_KEYS:
            if key in code:
                problems.append("%s 出现 GPU 预留键 %r" % (label, key))
    # ★ 陷阱：Dockerfile 里的 `AS runtime` 是**阶段别名**，不是 compose 的 `runtime:` 键。
    #   所以 `runtime:` 只在 compose 上查，Dockerfile 只查 `runtime: nvidia` 这种完整形态
    #   （已在 GPU_RESERVE_KEYS 里，不会误伤 `AS runtime`）。
    code_df = code_only(dockerfile_text)
    for img in GPU_BASE_IMAGES:
        if img in code_df:
            problems.append("Dockerfile 使用 GPU 基础镜像 %r" % img)
    return problems


def check_gpu_packages(pyproject_text, uvlock_text):
    """A3：依赖清单里不许有 GPU-only 包。"""
    problems = []
    for label, text in (("pyproject.toml", pyproject_text), ("uv.lock", uvlock_text)):
        for pkg in GPU_PACKAGES:
            # 逐行匹配「包名出现在依赖位」，避免 `torch` 命中 `torchvision` 之外的说明文字
            pat = re.compile(r'(^|[\s"\'\[])' + re.escape(pkg) + r'([\s"\'<>=！!,\]]|$)',
                             re.M)
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                problems.append("%s:%d 依赖出现 GPU 包 %r" % (label, line, pkg))
    return problems


def check_autoscale(sources):
    """C1：`sources` 是 [(label, 已剥注释与 docstring 的代码)]，不许出现自动扩容。"""
    problems = []
    for label, code in sources:
        for word in AUTOSCALE_WORDS:
            if word in code:
                problems.append("%s 出现自动扩容写法 %r" % (label, word))
    return problems


def check_release_words(sources):
    """D1：media / benchmark 路径不许自己写「已放行」。"""
    problems = []
    for label, code in sources:
        for word in RELEASE_WORDS:
            if word in code:
                problems.append("%s 出现 %r —— 放行只能由人做" % (label, word))
    return problems


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 119 / TS-17 · 阶段一 CPU 优先，不预设 GPU")
    print("=" * 72)

    missing = [p.name for p in (COMPOSE, DOCKERFILE, PYPROJECT) if not p.exists()]
    if missing:
        print("  ⚠ 读不到 %s —— 未测，不是通过" % missing)
        return 2

    compose = COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    uvlock = UVLOCK.read_text(encoding="utf-8") if UVLOCK.exists() else ""

    # ── A1/A2 ─────────────────────────────────────────────────────────
    gpu_problems = check_gpu_keys(compose, dockerfile)
    check("A1/A2", not gpu_problems,
          "编排定义无 GPU 预留键、无 GPU 基础镜像"
          if not gpu_problems else "发现 GPU 依赖：%s" % gpu_problems)

    # ── A3 ────────────────────────────────────────────────────────────
    pkg_problems = check_gpu_packages(pyproject, uvlock)
    check("A3", not pkg_problems,
          "依赖清单无 GPU-only 包（pyproject %d 行 / uv.lock %d 行已扫）"
          % (len(pyproject.splitlines()), len(uvlock.splitlines()))
          if not pkg_problems else "发现 GPU 包：%s" % pkg_problems)

    # ── A4 反向对照：剥注释这件事本身必须被证伪 ────────────────────────
    #   ★ 这一组**每次主检查都真跑**，不藏在 --controls 后面。
    #     理由是它正是 D2 踩过的那个坑：Dockerfile 注释里写着「这里不写 --workers」，
    #     第一版把它当成真参数报了红。**成对**才成立：
    #       只喂「注释里提到」→ 必须绿（否则剥注释无效）
    #       只喂「真配置」     → 必须红（否则剥注释剥过头，把真违规也剥掉了）
    ghost = "# 部署时不要用 runtime: nvidia，也不要加 gpus:\nFROM python:3.12-slim\n"
    real = "services:\n  api:\n    deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n"
    ghost_clean = not check_gpu_keys("", ghost)
    real_red = bool(check_gpu_keys(real, ""))
    check("A4", ghost_clean and real_red,
          "反向对照成对成立：注释里提 nvidia → 不报；真配置 → 报"
          if (ghost_clean and real_red) else
          "剥注释口径失效：注释样本 %s / 真配置样本 %s"
          % ("未被误报" if ghost_clean else "**被误报**",
             "已拦下" if real_red else "**漏掉了**"))

    # ── B 段：显式读数（行为级，调用真部件）────────────────────────────
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import benchmark_media as BM
    except Exception as exc:  # noqa: BLE001
        print("  ⚠ B 段：无法导入 tools/benchmark_media.py（%s）—— 该段未测" % exc)
        BM = None

    if BM is not None:
        # ★ 用真实的 `run_benchmark(modality, samples_dir, *, probe, runner)` 签名：
        #   它吃一个**采样目录**、逐样本找 `<stem>.gold.txt`，返回 (report, exit_code)。
        #   `runner(modality, path, ctx) -> str`。
        #   第一版我按「传 samples 列表 + config」写的 —— 签名是我凭印象编的，
        #   一跑就 TypeError。改成照 `:346-356` 的真实签名调用。
        bdir = tempfile.mkdtemp(prefix="cpu-first-b-")
        try:
            bpath = Path(bdir)
            # (a) 慢且错：有 gold，runner 返回完全错的文本
            (bpath / "slow-wrong.png").write_bytes(b"\x89PNG-not-really")
            (bpath / "slow-wrong.gold.txt").write_text("正确文本", encoding="utf-8")
            # (b) 缺 gold：只有图，没有 .gold.txt
            (bpath / "no-gold.png").write_bytes(b"\x89PNG-not-really")
            # (c) 引擎抛异常：有 gold，runner 抛
            (bpath / "boom.png").write_bytes(b"\x89PNG-not-really")
            (bpath / "boom.gold.txt").write_text("x", encoding="utf-8")

            def fake_probe():
                # ★ 实测签名（`benchmark_media.py:165-173`）：返回
                #   {tool: {"ok": bool, "path": ...}}，**不是** (tools, missing) 元组。
                #   我第一版按元组写的，一跑就 AttributeError —— 又一个「签名凭印象编」。
                return {"tesseract": {"ok": True, "path": "/usr/bin/tesseract"},
                        "ffmpeg": {"ok": True, "path": "/usr/bin/ffmpeg"},
                        "faster_whisper": {"ok": False},
                        "whisper": {"ok": False}}

            def runner_slow_wrong(modality, path, ctx):
                if path.stem == "boom":
                    raise RuntimeError("ocr-engine-crashed")
                return "完全错的文本"

            report, _rc = BM.run_benchmark(
                "ocr", bpath, probe=fake_probe, runner=runner_slow_wrong,
                ocr_lang="chi_sim")
            recs = {r["id"]: r for r in (report.get("samples") or [])}

            rec = recs.get("slow-wrong", {})
            has_ms = isinstance(rec.get("ms"), (int, float))
            has_err = isinstance(rec.get("cer"), (int, float)) and rec["cer"] > 0
            check("B1", has_ms and has_err,
                  "不达标样本同时给出「慢多少」ms=%r 与「差多少」cer=%r"
                  % (rec.get("ms"), rec.get("cer"))
                  if (has_ms and has_err) else
                  "不达标时读数缺失：ms=%r cer=%r（缺一个就无法判断慢在哪）"
                  % (rec.get("ms"), rec.get("cer")))

            rec2 = recs.get("no-gold", {})
            ok2 = (rec2.get("status") == "untested"
                   and rec2.get("reason") == "no_gold"
                   and rec2.get("cer") is None and rec2.get("ms") is None)
            check("B2", ok2,
                  "缺 gold → untested + reason='no_gold'，且 cer/ms 为 null（不是 0）"
                  if ok2 else
                  "缺 gold 时不许伪装成 0：status=%r reason=%r cer=%r ms=%r"
                  % (rec2.get("status"), rec2.get("reason"),
                     rec2.get("cer"), rec2.get("ms")))

            rec3 = recs.get("boom", {})
            ok3 = (rec3.get("status") == "untested"
                   and bool(str(rec3.get("reason") or "").strip()))
            check("B3", ok3,
                  "引擎抛异常 → untested + reason=%r（不静默降级成 ok）"
                  % (rec3.get("reason"),)
                  if ok3 else
                  "引擎异常被吞掉了：status=%r reason=%r"
                  % (rec3.get("status"), rec3.get("reason")))

            # ★ B4：本段必须**真的跑过**至少一个 tested 样本 ——
            #   否则上面三条都可能因为「一个样本都没跑到」而恰好成立（假绿）。
            n_tested = sum(1 for r in recs.values() if r.get("status") == "tested")
            check("B4", n_tested >= 1,
                  "B 段真的跑到了 tested 样本（%d 个），三条读数断言不是空转" % n_tested
                  if n_tested >= 1 else
                  "B 段一个 tested 样本都没有 —— 上面三条是空转，不能算验过")
        finally:
            shutil.rmtree(bdir, ignore_errors=True)

    # ── C 段：不自动扩容 ───────────────────────────────────────────────
    scan_targets = git_tracked("*.py") + git_tracked("*.mjs") + git_tracked("*.js")
    scan_targets = [p for p in scan_targets
                    if p.startswith(("api/", "base/", "tools/"))
                    and "node_modules" not in p and "verify_cpu_first" not in p]
    sources = []
    for rel in scan_targets:
        try:
            sources.append((rel, strip_py_docstrings((ROOT / rel).read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    auto_problems = check_autoscale(sources)
    check("C1", not auto_problems,
          "扫 %d 个文件（api/ base/ tools/）无自动扩容写法" % len(sources)
          if not auto_problems else "发现自动扩容：%s" % auto_problems[:4])

    # C2 反向对照：只在注释 / docstring 里出现 → 必须不报
    comment_sample = ("# 这里不要写 autoscaling，也不要 --scale\n"
                      '"""说明：本项目不自动扩容（autoscaling / --scale 均未使用）。"""\n'
                      "x = 1\n")
    c2_clean = not check_autoscale([("sample", strip_py_docstrings(comment_sample))])
    c2_red = bool(check_autoscale([("sample", 'x = autoscaling.update()\n')]))
    check("C2", c2_clean and c2_red,
          "反向对照成对成立：注释/docstring 里提到 → 不报；真调用 → 报"
          if (c2_clean and c2_red) else
          "C2 口径失效：注释样本 %s / 真调用 %s"
          % ("未被误报" if c2_clean else "**被误报**",
             "已拦下" if c2_red else "**漏掉了**"))

    # ── D 段：放行只能由人做（静态）──────────────────────────────────
    media_sources = [(lbl, code) for lbl, code in sources
                     if lbl.startswith(("tools/benchmark_media.py", "base/media.py"))]
    release_problems = check_release_words(media_sources)
    check("D1", not release_problems,
          "media / benchmark 路径无 released / 已放行（扫 %d 个文件）" % len(media_sources)
          if not release_problems else "发现自动放行：%s" % release_problems)

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    # ★ 结论行必须**标明构成**（2026-10-22）：`10/10` 这个数字本身会被读成
    #   「10 条覆盖」。实际其中 2 条（A4 / C2）是「剥注释口径」的**成对反向对照**，
    #   不是覆盖项 —— 它们证明的是扫描器不误报、不漏报，不是被测系统合规。
    #   这里按断言 id 实时分组，不手写数字（§2.2 第 1 条：数字要算出来）。
    _control_ids = {"A4", "C2"}
    n_cover = sum(1 for cid, _, _ in results if cid not in _control_ids)
    n_ctrl = len(results) - n_cover
    print("  共 %d 项 · 通过 %d · 失败 %d（其中 %d 条覆盖 + %d 条成对反向对照）"
          % (len(results), passed, failed, n_cover, n_ctrl))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 其中 %d 条覆盖 + %d 条成对反向对照"
          "（注释样本必须绿、真配置必须红）" % (n_cover, n_ctrl))
    print("     全过只证明：编排与依赖里没有 GPU 依赖、不达标会出读数、"
          "不自动扩容、不自动放行")
    print("     ★ 不证明「在无 GPU 的机器上真的起得来」—— 那要起容器看 RestartCount，")
    print("       属 verify_deploy.py --remote / 部署批次，本文件不冒充。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照：每个坏样本必须红，好样本必须绿。

    ★ 样本从**真实文件**派生（`copy.deepcopy` 后只改一处），不手写整份假真源 ——
      手写的假真源会让「扫描器能不能读真文件」这件事失去证据
      （与 `verify_brand_rules.py:252-303` 同一做法）。
    """
    if not (COMPOSE.exists() and DOCKERFILE.exists() and PYPROJECT.exists()):
        print("  ⚠ 真源缺失 —— 未测，不是通过")
        return 2

    compose = COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    cases = []

    # 好样本：真实文件原样
    cases.append(("好样本：真实编排定义", lambda: check_gpu_keys(compose, dockerfile), []))
    cases.append(("好样本：真实依赖清单", lambda: check_gpu_packages(pyproject, ""), []))

    # 坏样本 1：compose 加了 GPU 预留
    bad_compose = compose + (
        "\n# 下面这行是真的配置，不是注释（对照 A4 的另一半）\n"
        "  deploy:\n    resources:\n      reservations:\n        devices:\n"
        "          - driver: nvidia\n")
    cases.append(("坏样本：compose 有设备预留",
                  lambda: check_gpu_keys(bad_compose, dockerfile), ["--"]))
    # 坏样本 2：GPU 基础镜像
    cases.append(("坏样本：Dockerfile 用 nvidia/cuda",
                  lambda: check_gpu_keys(compose, dockerfile.replace(
                      "FROM python:3.12-slim", "FROM nvidia/cuda:12.4-runtime")), ["--"]))
    # 坏样本 3：GPU 依赖
    cases.append(("坏样本：依赖里加 torch",
                  lambda: check_gpu_packages(pyproject + '\n    "torch==2.4.0",\n', ""), ["--"]))
    # 坏样本 4：真自动扩容
    cases.append(("坏样本：代码里真调 autoscaling",
                  lambda: check_autoscale([("x.py", "autoscaling.update()\n")]), ["--"]))
    # 坏样本 5：真写「已放行」
    cases.append(("坏样本：media 路径写 released",
                  lambda: check_release_words([("x.py", 'status = "released"\n')]), ["--"]))

    # ★ 关键一对（05 点名要求的「剥注释必须能被证伪」）
    cases.append((
        "★ 注释里提到 nvidia → 必须绿（剥注释有效）",
        lambda: check_gpu_keys(
            "# runtime: nvidia 千万别用\n# gpus: all\nservices: {}\n",
            "# 不要用 FROM nvidia/cuda\nFROM python:3.12-slim\n"), []))
    cases.append((
        "★ 真配置 nvidia → 必须红（剥注释没剥过头）",
        lambda: check_gpu_keys(
            "services:\n  api:\n    runtime: nvidia\n", ""), ["--"]))
    cases.append((
        "★ 注释里提到 autoscaling → 必须绿",
        # ★ 2026-10-22：这一条第一次写时**漏了剥注释这一步**，直接把原文喂给
        #   check_autoscale，于是它正确地报了红，而对照期望是绿 ——
        #   红的是我的对照写法，不是扫描器。剥注释是 check_autoscale 的**前置**，
        #   必须在喂样本之前做，与主检查里的调用顺序保持一致。
        lambda: check_autoscale([("x.py", strip_py_docstrings(
            "# 不要写 autoscaling\n"
            '"""本项目不自动扩容（autoscaling / --scale 都未使用）。"""\n'
            "x = 1\n"))]), []))

    print("=" * 72)
    print("verify_cpu_first · --controls（反向对照）")
    print("=" * 72)
    bad = 0
    for name, fn, want in cases:
        try:
            problems = fn()
        except Exception as exc:  # noqa: BLE001
            print("  ✗ %s —— 对照自身异常：%s" % (name, exc))
            bad += 1
            continue
        want_red = bool(want)
        got_red = bool(problems)
        ok = (got_red == want_red)
        print(("  ✓ " if ok else "  ✗ ") + name
              + ("" if ok else "  期望%s，实际%s：%s"
                 % ("红" if want_red else "绿", "红" if got_red else "绿", problems[:2])))
        bad += int(not ok)

    print("-" * 72)
    if bad:
        print("❌ %d/%d 不符 —— 断言或对照本身有问题" % (bad, len(cases)))
        return 1
    print("✅ %d/%d 全过：好样本绿；坏样本各自红；注释样本不误报" % (len(cases), len(cases)))
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--controls", action="store_true")
    # ★ 一次处理 --help 与未知参数：argparse 默认对未知参数退 2，
    #   而验收执行器把退 2 读成「未测」—— 手误会被静默吞成未测。
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
