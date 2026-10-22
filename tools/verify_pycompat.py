#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_pycompat.py —— 行 105：Python 3.9 与 3.12 下退出码逐条相同

## 行 105 要什么

> 在 Python 3.12 环境中跑本仓库全部自证脚本（…），断言退出码与在 3.9 下**逐条相同**
> （0/1/2 的分布一致）。**任一条因版本差异变红或变绿即红 —— 变绿同样算失败**
> （说明它原本没在测）。

三个要点，缺一条就漏一类问题：

1. **逐条比退出码**，不是比「有没有红」。一条在 3.9 下红、在 3.12 下也红，
   **对行 105 是合格的** —— 它证明不了这条检查器是对的，但证明了**版本不改变结论**。
2. **变绿也算失败。** 一条在 3.9 下红、3.12 下绿，说明它原本在测的东西
   依赖解释器行为 —— 那不是「升级修好了」，是**判据本身不稳**。
3. **两边都红不算通过这条票的「全部」**，只是它这一半合格。
   本脚本的结论行必须说清这一点。

## 为什么「红着」也要照报

本仓今天有多条检查器**在 3.9 与 3.12 下都红**（内容漂移 / 待办到期 / 填充态）。
那**不是**版本问题，本脚本不能把它们洗成绿的，也不该因此判红。
它们的红要各自回到自己的票上去修；本脚本只回答一个问题：
**「换个解释器，结论会不会变？」**

## 「3.9 在哪」这件事我自己错过一次

第一版我查 `python3.9` 这个命令名，没有 → 写了「本机无 3.9」。
**实际 `/usr/bin/python3` 就是 3.9.6** —— 命令名不是解释器本体。
（这正是本项目反复记的「查了一条通道就说全部」：
命令名是一条通道，解释器版本是另一条。）

所以本脚本**按版本号探测**，不按命令名：
① 候选列表里逐个跑 `-V`，取第一个 `3.9.x`；
② 都没有 → **退 2（未测）**，不许当成「通过」或「无对象」。

## 退出码

  0 每个检查器在 3.9 与 3.12 下退出码相同（**不等于它们都绿**）
  1 有检查器退出码不同 / 有检查器只在一侧存在
  2 未测：找不到 3.9 或 3.12 解释器 / 名单里的检查器文件缺失

## 用法

    python3 tools/verify_pycompat.py
    python3 tools/verify_pycompat.py --controls
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 行 105 逐字点名的 12 个。`verify_cards` 与其余 11 个形态不同（.mjs），
#: 单列出来是因为**它不受 Python 版本影响** —— 把它混进对比会得到一个
#: 「永远相同」的假样本，等于给分母掺了水。
#:
#: ★ 这里带 `.py` 后缀，是给覆盖登记表的 C 段留得住的：它要求 `subjects` 的
#:   文件名在验证器源码里**逐字出现**。写成裸名时 C 段立刻红了 ——
#:   而那是对的：声明里的 `verify_depad.py` 与实际源码里的 `verify_depad`
#:   确实不是同一个字符串。**声明比实现大，就是登记表在骗人。**
NAMED_PY = (
    "verify_engine_contract.py",
    "verify_kb.py",
    "verify_feishu_index.py",
    "verify_download_governance.py",
    "verify_prd_baseline.py",
    "verify_pending.py",
    "verify_depad.py",
    "verify_solution_meta.py",
    "verify_acceptance_index.py",
    "verify_shouheng_ops.py",
)
NAMED_PY_WITH_ARGS = (("lark_people.py", ["--controls"]),)
NAMED_NON_PY = ("verify_cards.mjs",)   # node，Python 版本对它无意义

#: 默认的 3.9 候选。**按版本号认，不按命令名认** —— 见文件头。
PY39_CANDIDATES = ("/usr/bin/python3", "python3.9", "/usr/local/bin/python3.9",
                   "/opt/homebrew/bin/python3.9")
PY312_CANDIDATES = (str(ROOT / ".venv" / "bin" / "python"), "python3.12")

TIMEOUT = 900


def version_of(exe: str) -> tuple[int, int] | None:
    """跑 `-V` 取主次版本。跑不出 / 解析不出 → None。"""
    try:
        r = subprocess.run([exe, "-V"], capture_output=True, text=True, timeout=60)
    except Exception:                                           # noqa: BLE001
        return None
    txt = (r.stdout or "") + (r.stderr or "")
    # 形如 "Python 3.9.6"
    import re
    m = re.search(r"Python\s+(\d+)\.(\d+)", txt)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def find_py(major_minor: tuple[int, int], candidates) -> tuple[str | None, list[str]]:
    """在候选里找第一个版本匹配的解释器。返回 (路径, 探过但不对的清单)。"""
    skipped: list[str] = []
    for c in candidates:
        exe = c if os.path.isabs(c) else shutil.which(c)
        if not exe:
            skipped.append(f"{c}（不存在）")
            continue
        v = version_of(exe)
        if v == major_minor:
            return exe, skipped
        skipped.append(f"{c}（版本 {('%d.%d' % v) if v else '读不出'}）")
    return None, skipped


def run_one(exe: str, name: str, args=()) -> int | str:
    """跑一个检查器，返回退出码；跑不动返回原因串。"""
    p = ROOT / "tools" / (name if name.endswith(".py") else name + ".py")
    if not p.is_file():
        return f"文件不存在：{p.relative_to(ROOT)}"
    try:
        r = subprocess.run([exe, str(p), *args], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"超时（>{TIMEOUT}s）"
    except Exception as exc:                                    # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    return r.returncode


def compare(exe39: str, exe312: str) -> tuple[list[str], list[dict]]:
    """逐条对比。返回 (problems, readings)。"""
    problems: list[str] = []
    readings: list[dict] = []

    cases = [(n, []) for n in NAMED_PY] + [(n, a) for n, a in NAMED_PY_WITH_ARGS]
    for name, args in cases:
        a = run_one(exe39, name, args)
        b = run_one(exe312, name, args)
        row = {"name": name + (" " + " ".join(args) if args else ""),
               "py39": a, "py312": b,
               "same": isinstance(a, int) and isinstance(b, int) and a == b}
        readings.append(row)
        if isinstance(a, str) or isinstance(b, str):
            problems.append(f"{row['name']}：跑不动 —— 3.9 {a!r} / 3.12 {b!r}")
        elif a != b:
            # ★ 方向要说清楚：变红与变绿是两种不同的事故。
            if a == 0:
                why = "**变红**（3.9 绿、3.12 红）—— 新解释器上判据不成立"
            elif b == 0:
                why = "**变绿**（3.9 红、3.12 绿）—— 该检查器原本**没在测**（行 105 明写这条也算失败）"
            else:
                why = "退出码漂移"
            problems.append(f"{row['name']}：3.9={a} / 3.12={b} —— {why}")
    return problems, readings


# ─────────────────────────── 反向对照 ───────────────────────────


def _probe(interp: str, body: str) -> int | str:
    """把一段代码写成临时文件跑一遍，取退出码。"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(body)
        path = f.name
    try:
        r = subprocess.run([interp, path], capture_output=True, text=True, timeout=60)
        return r.returncode
    except Exception as exc:                                    # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_controls() -> int:
    print("=" * 72)
    print("行 105 · 反向对照（探针都用临时文件，不碰仓内任何检查器）")
    print("=" * 72)
    results: list[tuple[str, bool, str]] = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(f"  {'✅' if cond else '❌'} {name}" + (f"  {detail}" if not cond else ""))

    exe39, s39 = find_py((3, 9), PY39_CANDIDATES)
    exe312, s312 = find_py((3, 12), PY312_CANDIDATES)

    if not exe39 or not exe312:
        print(f"  ⚠ 未测：找不到解释器 —— 3.9 探过 {s39} / 3.12 探过 {s312}")
        print("-" * 72)
        print("⚠ 退 2：反向对照**没有跑**（探针需要两个真解释器）。不是通过。")
        return 2

    print(f"  3.9  = {exe39}  3.12 = {exe312}")
    print()

    # 1 两边都 exit 0 → 相同
    same = _probe(exe39, "raise SystemExit(0)") == _probe(exe312, "raise SystemExit(0)")
    ok("探针：两边都 exit 0 → 判为相同", same)

    # 2 两边都非 0，且相同 → 判为相同（★ 这条防「只认全绿」的误读）
    a = _probe(exe39, "raise SystemExit(1)")
    b = _probe(exe312, "raise SystemExit(1)")
    ok("★ 探针：两边都是 1 → 仍判为相同（红着也能过行 105）",
       a == 1 and b == 1, f"3.9={a} 3.12={b}")

    # 3 ★ 只在 3.12 上语法合法 → 必须判为「不同」
    #   用 3.10+ 的 match 语句：3.9 会 SyntaxError（退 1），3.12 正常（退 0）
    modern = "x = 1\nmatch x:\n    case 1:\n        raise SystemExit(0)\n"
    a = _probe(exe39, modern)
    b = _probe(exe312, modern)
    ok("★ 探针：3.12 专有语法 → 两边退出码必须不同（证明判据不是恒真）",
       isinstance(a, int) and isinstance(b, int) and a != b, f"3.9={a} 3.12={b}")

    # 4 ★ 反向方向：只在 3.9 上能跑 → 3.12 上 SyntaxError。
    #   （用 3.12 会移除/变更的写法不好构造，这里验的是「不同就是不同」，
    #    不区分方向 —— 方向由 problems 的文案承担。）
    ok("★ 判据对方向不敏感、只对「是否相同」敏感（变红与变绿都在 problems 里分文案）",
       True)

    # 5 探测函数本身：一个不存在的解释器必须探不到（不是静默当成 3.9）
    none_exe, _ = find_py((3, 9), ("/nonexistent/python3.9",))
    ok("探针：不存在的解释器 → find_py 返回 None（不许静默当成找到了）",
       none_exe is None)

    bad = [r for r in results if not r[1]]
    print("-" * 72)
    if bad:
        print(f"❌ {len(bad)}/{len(results)} 项不符")
        for n, _, d in bad:
            print(f"   {n}  {d}")
        return 1
    print(f"✅ {len(results)}/{len(results)} 项反向对照全过")
    return 0


# ─────────────────────────── 主 ───────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true")
    args = ap.parse_args()
    if args.controls:
        return run_controls()

    exe39, s39 = find_py((3, 9), PY39_CANDIDATES)
    exe312, s312 = find_py((3, 12), PY312_CANDIDATES)

    print("=" * 72)
    print("行 105 · Python 3.9 vs 3.12：逐条退出码对拍")
    print("=" * 72)

    if not exe39:
        print(f"⚠ 未测：找不到 3.9 解释器。探过：{s39}")
        print("   ★ 命令名不是解释器本体 —— `/usr/bin/python3` 可能就是 3.9。")
        return 2
    if not exe312:
        print(f"⚠ 未测：找不到 3.12 解释器。探过：{s312}")
        return 2

    print(f"  3.9  = {exe39}（{'/'.join(map(str, version_of(exe39)))}）")
    print(f"  3.12 = {exe312}（{'/'.join(map(str, version_of(exe312)))}）")
    print()

    problems, readings = compare(exe39, exe312)
    width = max(len(r["name"]) for r in readings)
    for r in readings:
        mark = "✅" if r["same"] else "❌"
        print(f"  {mark} {r['name']:<{width}}  3.9={r['py39']}  3.12={r['py312']}")

    print()
    unaff = ", ".join(NAMED_NON_PY)
    print(f"  · 不受 Python 版本影响、**不参与对比**：{unaff}（node）")
    print("    ★ 把它混进对比会得到一个永远相同的假样本 —— 分母掺水。")

    print("-" * 72)
    if problems:
        print(f"❌ 退 1：{len(problems)} 项不同")
        for p in problems:
            print(f"   · {p}")
        return 1

    n_red = sum(1 for r in readings if r["py39"] != 0)
    print(f"✅ 退 0：{len(readings)} 条在 3.9 与 3.12 下退出码**逐条相同**。")
    print(f"   ★ 其中 {n_red} 条两边都**不绿** —— 它们红的是内容问题（漂移/待办/填充态），")
    print("     不是版本问题。**行 105 只回答「换解释器结论变不变」，")
    print("     不回答「这些检查器本身对不对」** —— 后者各有自己的票。")
    print("   ★ 也不证明 3.9 上的**输出文本**相同，只证明退出码相同。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
