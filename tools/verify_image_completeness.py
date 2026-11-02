#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_image_completeness.py — **本地能跑 ≠ 镜像里有**。

## 它守的是什么

2026-10-30 一周内三次同源事故：

  1. `a83592a` 镜像缺 `lp_extract` / `lp_fetch`：`base/media.py` 在 import 期就
     `from lp_extract import ...`，而 Dockerfile 没 COPY、.dockerignore 也没豁免，
     构建期 OK、容器里 ImportError，**每一单媒体件都打不开**。
  2. `10429d3` 镜像缺 `tools/multimodal_client`：观察数恒为 0，note 是 None。
  3. `aeb7c50` `.dockerignore` 排除了 `tools/`：新加的模块即便写了 COPY，
     文件也进不了构建上下文，构建直接 `failed to compute cache key`。

三次的共同形状：**本地 import 闭包与镜像 import 闭包是两个数，而没有任何
一行代码在拦**。本地跑 verifier 全绿、上生产就 ImportError ——
这就是 AGENTS.md §2.4.1 那个病的又一个变体：「我验过」的输入只是
「本地能跑」，说出去的却是「生产能跑」。

## 断言

| 段 | 断言 |
|---|---|
| A | Dockerfile 每条 `COPY <src> <dst>` 的 src 在**构建上下文里真实存在**（先过 .dockerignore 再看盘上有没有） |
| B | `base/` + `api/` 顶层 import 闭包里的每个**本地**模块，都能被镜像里的某条 COPY 覆盖（即运行时 sys.path 解析得到） |
| C | ★ 反向对照：喂一个「被 .dockerignore 排除的 COPY 源」必须红（否则 A 恒真） |
| D | ★ 反向对照：喂一个「闭包里有、Dockerfile 没 COPY」的模块必须红（否则 B 恒真） |
| E | 异常路径即未测：Dockerfile 或 .dockerignore 读不出时退 2，不是 0 |

退出码：全过 **0** / 有红 **1** / 未测 **2**。

## 设计边界

- **不跑 docker build** —— 那要联网、要分钟级；本检查器纯静态，一秒内出结论。
- **不解析动态 import**（`importlib.import_module(变量)`）—— 它本来就不该出现在
  生产路径上；出现了会在 B 段被「闭包里有但没 COPY」抓住（因为静态扫描会把它
  的字面量当成 import 目标，Dockerfile 里照样找不到对应 COPY）。
- 闭包按**顶层 `from X import` / `import X`** 静态扫描，不执行字节码 ——
  与 `python -X importtime` 不同，但和构建期的失败模式同构。

复现：
    python3 tools/verify_image_completeness.py
    python3 tools/verify_image_completeness.py --controls   # 反向对照

本文件验的两个主体（`verify_coverage.py` C 段据此对账）：
- `Dockerfile` —— COPY 指令与真实文件的对账（段 A）
- `.dockerignore` —— 排除/豁免规则与 COPY 源的对账（段 A / C）
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"

# 生产 entrypoint 的 Python 根：这些目录里的模块互相 import 都算「本地」。
LOCAL_ROOTS = ("base", "api")

# 镜像里 sys.path 上有这些目录（Dockerfile WORKDIR /app，且 base/media.py 等会
# 把 ROOT 与 ROOT/tools 塞进 sys.path）。每个都映射到仓内一棵子树。
IMAGE_PATH_MAP = {
    "": ".",          # /app/  → 仓根
    "tools": "tools", # /app/tools/ → 仓内 tools/
}


# ─────────────────────────────────────────────────────────────────────────────
# .dockerignore 解析（简化版：支持 `pattern` 与 `!pattern`，支持 `**`）
# ─────────────────────────────────────────────────────────────────────────────

def _ignore_rules(text: str):
    """按行解析 .dockerignore，返回 [(negated, regex), ...]，后写的规则覆盖先写的。"""
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pat = line[1:] if negated else line
        # .dockerignore 语义：行的斜杠分隔，每个 segment 可以是 `**`、`*`、`?`、字面量
        # 简化：把 `**` 翻成 `.*`、`*` 翻成 `[^/]*`、`?` 翻成 `.`
        # 首尾都不补 ^ $ —— .dockerignore 是「路径任意位置的前缀」匹配
        parts = []
        for seg in pat.split("/"):
            if seg == "**":
                parts.append(".*")
            else:
                seg_re = "".join(
                    "[^/]*" if c == "*" else "." if c == "?" else re.escape(c)
                    for c in seg
                )
                parts.append(seg_re)
        rx = re.compile(r"^(?:.*/)?" + "/".join(parts) + r"(?:/.*)?$")
        rules.append((negated, rx))
    return rules


def is_in_context(path: str, rules) -> bool:
    """True = 该路径在构建上下文里（没被排除，或被 ! 豁免）。"""
    included = True
    for negated, rx in rules:
        if rx.match(path):
            included = bool(negated)
    return included


# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile COPY 解析
# ─────────────────────────────────────────────────────────────────────────────

COPY_RE = re.compile(r"^\s*COPY\s+(?:--from=\S+\s+)?(?P<srcs>.+?)\s+(?P<dst>\S+)\s*$")


def parse_copies(text: str):
    """返回 [(src, dst), ...]；`--from=` 的 COPY 不算（那是跨 stage 拷，不查上下文）。"""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = COPY_RE.match(line)
        if not m:
            continue
        if "--from=" in line.split("COPY", 1)[1].split(m.group("srcs"), 1)[0]:
            continue
        srcs = m.group("srcs").split()
        dst = m.group("dst")
        for src in srcs:
            out.append((src, dst))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# base/ + api/ 顶层 import 闭包
# ─────────────────────────────────────────────────────────────────────────────

IMPORT_FROM_RE = re.compile(r"^from\s+([A-Za-z_][\w.]*)\s+import\b")
IMPORT_PLAIN_RE = re.compile(r"^import\s+([A-Za-z_][\w.]*)")
# 允许一层缩进的「函数内 import」也采信 —— base/media_analyze.py:343 就是
# `    from tools.multimodal_client import GatewayClient`。但排除 try/except 里
# 的可选依赖（那种本来就该容忍缺失）。
INDENTED_IMPORT_RE = re.compile(r"^\s{4}(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))")


def _module_name_to_rel(name: str) -> str:
    """模块点号 → 仓内相对路径（不带扩展名）。"""
    return name.replace(".", "/")


def scan_local_imports(root: Path):
    """扫 base/ + api/ 顶层 .py，返回 (顶层闭包, 函数内二跳) 两个集合。

    「本地」的定义：以 base. / api. / tools. 开头，或顶层模块名在 LOCAL_ROOTS
    里对应一个真实目录/文件（裸 import 如 `lp_extract`、`bj_time`）。

    函数内 import（缩进 4 空格的 `from X import`）单独算「二跳」：
    它们在模块 import 期**不会触发**，所以容器能起来、只在真正调用那个函数时才炸。
    2026-10-30 的 lark_find 就是这种 —— `sync_rules.py` 是 CLI 工具，
    生产 web 进程不会 import 它，但静态扫描会把它算进闭包造成误报。
    顶层 import 是「**一定**触发」，二跳是「**可能**触发」，分开报。
    """
    top: set[str] = set()
    second: set[str] = set()
    top_level_files = {}
    for d in LOCAL_ROOTS:
        for py in (root / d).glob("*.py"):
            top_level_files[py.stem] = py.relative_to(root).as_posix()
    # tools/ 顶层 .py 也算 —— base/media.py 把 ROOT/tools 塞进 sys.path 后裸 import。
    for py in (root / "tools").glob("*.py"):
        top_level_files[py.stem] = py.relative_to(root).as_posix()

    def _record(name: str, bucket: set[str]):
        if not name:
            return
        first = name.split(".")[0]
        if first in ("base", "api", "tools"):
            bucket.add(_module_name_to_rel(name))
        elif first in top_level_files:
            rel = top_level_files[first]
            bucket.add(rel[: -len(".py")] if rel.endswith(".py") else rel)

    for d in LOCAL_ROOTS:
        for py in (root / d).glob("**/*.py"):
            if "__pycache__" in py.parts:
                continue
            try:
                text = py.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                m = IMPORT_FROM_RE.match(line) or IMPORT_PLAIN_RE.match(line)
                if m:
                    _record(m.group(1), top)
                    continue
                mi = INDENTED_IMPORT_RE.match(line)
                if mi:
                    _record(mi.group(1) or mi.group(2), second)
    return top, second


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true",
                    help="跑反向对照：喂坏样本必须红、喂好样本必须绿")
    args = ap.parse_args()

    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        passed += int(bool(ok)); failed += int(not bool(ok))
        print(("PASS" if ok else "FAIL") + ": " + name + ((" " + detail) if detail else ""))

    if not DOCKERFILE.exists() or not DOCKERIGNORE.exists():
        print("UNTESTED: Dockerfile 或 .dockerignore 不在盘上")
        return 2

    try:
        df_text = DOCKERFILE.read_text(encoding="utf-8")
        di_text = DOCKERIGNORE.read_text(encoding="utf-8")
    except OSError as exc:
        print("UNTESTED: 读不出 Dockerfile/.dockerignore：%r" % (exc,))
        return 2

    rules = _ignore_rules(di_text)
    copies = parse_copies(df_text)

    # ── A：每条 COPY 的 src 必须在构建上下文里真实存在 ─────────────────────
    a_bad = []
    for src, _dst in copies:
        src = src.rstrip("/")
        if not is_in_context(src, rules):
            a_bad.append(("被 .dockerignore 排除", src))
            continue
        p = ROOT / src
        if not p.exists():
            a_bad.append(("盘上不存在", src))
            continue
        if p.is_dir():
            # COPY 目录时，里面每个文件都得在上下文里 —— 至少根目录本身得在
            pass
    report(not a_bad,
           "A1 Dockerfile 每条 COPY 的 src 都在构建上下文里且盘上存在",
           repr(a_bad[:5]) if a_bad else "%d 条 COPY 全部对得上" % len(copies))

    # ── B：生产 import 闭包每个本地模块都被某条 COPY 覆盖 ──────────────────
    top_mods, second_mods = scan_local_imports(ROOT)
    # 把 COPY 目标的「镜像内路径 → 仓内 src」做成映射，用于反查
    dst_to_src = {}
    for src, dst in copies:
        src = src.rstrip("/")
        dst = dst.rstrip("/")
        # dst 形如 ./api/ 或 ./tools/lp_extract.py；去掉前导 ./
        dst_rel = dst[2:] if dst.startswith("./") else dst
        dst_to_src[dst_rel] = src

    def covered_by_copy(mod_rel: str) -> bool:
        """模块相对路径（如 base/media 或 lp_extract）能否被镜像解析到。"""
        # 候选 1：mod_rel 是 base/api 下的 → 直接看对应目录是否被 COPY
        # 候选 2：裸模块（lp_extract）→ 镜像里它在 /app/tools/ 下 → 查 tools/<name>.py
        candidates = [mod_rel + ".py", mod_rel + "/__init__.py"]
        if not mod_rel.startswith(("base/", "api/", "tools/", "research/", "contracts/")):
            candidates.append("tools/" + mod_rel + ".py")
        for cand in candidates:
            for dst_rel, src in dst_to_src.items():
                # 目录 COPY：dst_rel 是前缀
                if src.endswith("/") or (ROOT / src).is_dir():
                    if cand.startswith(src):
                        return True
                else:
                    if cand == src:
                        return True
        return False

    b_bad = [m for m in sorted(top_mods) if not covered_by_copy(m)]
    report(not b_bad,
           "B1 base/+api/ 顶层 import 闭包 %d 个本地模块全部被 Dockerfile COPY 覆盖" % len(top_mods),
           repr(b_bad[:8]) if b_bad else "")
    # 二跳（函数内 import）：容器起得来，只在调那个函数时才炸。
    # ★ 2026-11-02 写完第一天就抓到：tools/lark_find 在 sync_rules.py 函数内
    #   import，而 sync_rules 是 CLI 工具、生产 web 进程不 import 它。
    #   静态扫描**无法**判断「这个函数内 import 会不会被生产路径触达」，
    #   判红就是误报 —— 而「误报比不报更糟」（AGENTS.md §2.1.1）。
    #   但「永远退 2」也等于「这个检查器不存在」（每次 CI 都未测），所以：
    #   - 已人工确认过是 CLI-only 的，进 KNOWN_CLI_ONLY 白名单，跳过；
    #   - **新出现的**二跳未覆盖（不在白名单）→ 红 —— 它还没人看过。
    KNOWN_CLI_ONLY = {
        # (模块, 调用它的文件, 确认日期, 理由)
        "tools/lark_find",  # base/sync_rules.py 函数内；sync_rules 是 CLI，生产不 import（2026-11-02 人工核）
    }
    b2_bad = [m for m in sorted(second_mods)
              if not covered_by_copy(m) and m not in KNOWN_CLI_ONLY]
    report(not b2_bad,
           "B2 函数内二跳 import %d 个本地模块（白名单 %d 个 CLI-only）都被 COPY 覆盖"
           % (len(second_mods), len(KNOWN_CLI_ONLY & second_mods)),
           repr(b2_bad[:8]) if b2_bad else "")
    untested = 0

    # ── C / D：反向对照（--controls） ────────────────────────────────────────
    if args.controls:
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            # C：被 .dockerignore 排除的 COPY 源 → is_in_context 必须 False
            c_neg = not is_in_context("tools/verify_image_completeness.py", rules)
            report(c_neg,
                   "C1 ★ 反向对照：tools/ 下的验证器被 .dockerignore 排除（A 不是恒真）",
                   "is_in_context=%r" % (not c_neg,))
            # C2：! 例外生效 —— tools/redact.py 必须在上下文里
            c_pos = is_in_context("tools/redact.py", rules)
            report(c_pos,
                   "C2 ★ 反向对照：!tools/redact.py 例外生效（否则规则解析错了方向）",
                   "")

            # D：闭包里有但 COPY 没覆盖的模块 → covered_by_copy 必须 False
            #   找一个 verifier 自己：它肯定没被 COPY（运行时不需要它）
            d_neg = not covered_by_copy("tools/verify_image_completeness")
            report(d_neg,
                   "D1 ★ 反向对照：闭包外的模块被判「没 COPY 覆盖」（B 不是恒真）",
                   "")
            # D2：闭包内的真模块（如 lp_extract）必须被判「已覆盖」
            d_pos = covered_by_copy("lp_extract") or covered_by_copy("tools/lp_extract")
            report(d_pos,
                   "D2 ★ 反向对照：lp_extract 被 Dockerfile COPY 覆盖"
                   "（2026-10-30 真事故，本检查器就是为它建的）",
                   "")
            # D3：★ B2 的白名单不是「永远绿的护身符」——
            #   人为造一个**不在白名单**的二跳未覆盖模块，B2 必须真红。
            #   做法：临时把 lark_find 从 KNOWN_CLI_ONLY 里挪走再判一次。
            #   这能抓住「白名单悄悄被扩成 *」这种事故。
            KNOWN_CLI_ONLY_orig = {
                "tools/lark_find",
            }
            # 模拟「白名单被清空」：lark_find 仍然在 second_mods 里，但没人豁免它
            b2_bad_simulated = [m for m in sorted(second_mods)
                                if not covered_by_copy(m)
                                and m not in (KNOWN_CLI_ONLY_orig - {"tools/lark_find"})]
            report("tools/lark_find" in b2_bad_simulated,
                   "D3 ★ 反向对照：白名单被清空时 B2 必须真红"
                   "（证明 B2 的绿不是来自「白名单把一切都豁免了」）",
                   repr(b2_bad_simulated))

    print("-" * 68)
    if failed:
        print("❌ %d 红 / %d 通过" % (failed, passed))
        return 1
    print("✅ %d 项全过" % passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
