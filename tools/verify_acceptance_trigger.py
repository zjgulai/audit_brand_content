#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_acceptance_trigger.py —— T-142：验收执行器到底有没有「自动触发点」

## 一句话

`tools/verify_acceptance_run.py` 是全部验收判据的唯一执行入口。
**它只在有人手动敲命令时跑。** 本脚本把「有没有东西会自动跑它」拆成三条通道
分别读，并要求三条各自给读数 —— **不许用其中一条盖掉另外两条**。

| 通道 | 怎么读 | 读不到时 |
|---|---|---|
| CI | 扫六大 CI 家族的配置路径，再看内容里有不有引用验收执行器 | `none` |
| 本地 hook | `core.hooksPath` 指向的目录 / `.git/hooks/*`（非 `.sample`） | `none` |
| 远端分支保护 | 本机无 `gh`、无网 | **未测**（每次运行都照报） |

## 它判什么、**不判**什么

判的是 **「本机至少有一条自动路径会跑验收执行器」** —— 这是可离线判定的事实。

**不判**「远端分支保护真的拦住了一次合并」。那需要真开一个 PR 去撞门，
本机做不到。`verify_regression_set.py` 的 `GS-GATE` 有同一条免责，
两者分工是：那边验**判定函数对不对**，这边验**有没有人调用它**。

★ 这三件事经常被混成一句「我们配了 CI」：

1. 配了 CI
2. CI 会跑**验收执行器**（而不是只跑 `pytest` / `npm test`）
3. CI 真能**拦住合并**

**三个层级分开报，是本脚本存在的全部理由。** 只报第一层，读者会以为三件都成立。

## 「假触发」为什么单列

一份 CI 配置里出现了 `acceptance` / `验收` 字样，却**没有引用验收执行器** ——
这类配置比「完全没有 CI」更危险：它让人相信「验收已经自动在跑了」，
而实际上那条 job 跑的是别的东西。所以它单独判红，不与 `none` 混为一谈。

## 退出码

  0 至少一条通道会自动跑验收执行器（**不证明**远端拦得住合并）
  1 有红：没有任何通道会跑它 / 某条通道声称「验收」却不引用执行器（假触发）
  2 未测（本机读不到，且没有红）

## 用法

    python3 tools/verify_acceptance_trigger.py
    python3 tools/verify_acceptance_trigger.py --controls
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 被「触发」的那个东西 —— 全项目只有这一个验收执行入口。
GATE = "verify_acceptance_run"

#: ★ 2026-10-29：**间接**触发入口。`verify_acceptance_ratchet.py` 的 `--run`
#: 会 subprocess 调 `verify_acceptance_run.py`，所以它也是「会跑执行器」。
#: 钩子改成走棘轮之后（与 CI 同一判据），只测 `GATE` 会把它判成假触发。
RATCHET = "verify_acceptance_ratchet"

#: 「调用」与「提到」的区别。
#:
#: ★★★ 这条正则补的是一个**已经开始骗人的判据**。2026-10-29 实测：
#: 本文件此前写的是 `runs_gate = GATE in text` —— 一个**源码文本存在性测试**。
#: 我把 `tools/githooks/pre-push` 从「直接跑执行器」改成「跑棘轮」之后，
#: 钩子里**一次也没有调用**执行器了，而通道二仍打印
#: 「hook 已配且会跑验收执行器」—— 因为我留在钩子里的**注释**写着
#: 「这里原来直接跑 `verify_acceptance_run.py`」。一行解释话就让判据恒真。
#:
#: 这正是 AGENTS.md §2.4 点名的那个病：「名字出现过」不是「它跑得起来」。
#: 现在判据要求「真正的调用形状」：`python …/verify_acceptance_run.py`、
#: `bash tools/xxx.sh`、或把它写进 `run:` / `exec` 的参数里。
CALL_RE = re.compile(
    r"(?:python3?|py|exec|run:|-\s*run|=)\s*[^\n]*\b"
    r"(?:verify_acceptance_run|verify_acceptance_ratchet)\b"
)

#: 注释不算代码。整行 `#` 开头与 YAML 的 `# ` 都剥掉再判。
#: ⚠️ 已知盲区（与 `verify_shouheng_ops.py` C5 同一条）：**行尾注释**仍会被扫到。
#:    明着留着，不用更复杂的语法分析 —— 一个会误报的检查器比没有更糟。
_COMMENT_LINE_RE = re.compile(r"^\s*#.*$", re.M)

#: 六大 CI 家族的代表路径。做成常量是为了让 controls 能复用同一张表
#: （两处各写一份，迟早有一份先改）。
CI_PATHS = (
    ".github/workflows",     # GitHub Actions：目录，含多个 *.yml
    ".gitlab-ci.yml",        # GitLab CI
    "Jenkinsfile",           # Jenkins
    ".circleci/config.yml",  # CircleCI
    "azure-pipelines.yml",   # Azure Pipelines
    ".travis.yml",           # Travis
)

#: 「声称跑验收」的痕迹。命中它却不引用执行器 = 假触发。
CLAIM_RE = re.compile(r"acceptance|验收", re.I)

#: 仓库内可供安装的 hook 脚本目录（受版本控制，clone 后仍在）。
HOOK_SCRIPTS_DIR = "tools/githooks"

RUNS_GATE = "runs_gate"
NO_GATE = "present_no_gate"
NOT_INSTALLED = "repo_scripts_not_installed"
NONE = "none"

STATE_ZH = {
    RUNS_GATE: "已配且会跑验收执行器（直接或经棘轮）",
    NO_GATE: "已配但**不跑**验收执行器",
    NOT_INSTALLED: "仓库里有 hook 脚本但**未安装**",
    NONE: "没有",
}


# ─────────────────────────── 判据：调用 vs 提到 ───────────────────────────


def runs_gate_in(text: str) -> bool:
    """这条通道的源码里，**真的会跑**验收执行器吗？

    ★ 2026-10-29 从 `GATE in text` 改过来。原来那个写法是「这个名字在源码里
      出现过吗」，而任何一行解释性注释都能满足它 —— 本文件自己就撞过：
      钩子改成跑棘轮后一次也没调执行器，却因为注释里还留着旧命令名而仍报
      「已配且会跑」。

    现在要求：剥掉整行注释后，仍有**调用形状** ——
    `python …/verify_acceptance_run.py`（直接）或
    `python …/verify_acceptance_ratchet.py --run`（间接）。
    """
    stripped = _COMMENT_LINE_RE.sub("", text)
    return bool(CALL_RE.search(stripped))


# ─────────────────────────── 通道一：CI ───────────────────────────


def scan_ci(root: Path) -> dict:
    """读 CI 通道。返回 {state, paths, runs_gate, claims}。"""
    found: list[Path] = []
    for rel in CI_PATHS:
        p = root / rel
        if p.is_dir():
            found.extend(sorted(x for x in p.rglob("*") if x.is_file()
                                and x.suffix in (".yml", ".yaml")))
        elif p.is_file():
            found.append(p)

    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in found)
    runs_gate = runs_gate_in(text)
    claims = bool(CLAIM_RE.search(text))
    if not found:
        state = NONE
    elif runs_gate:
        state = RUNS_GATE
    else:
        state = NO_GATE
    return {"state": state, "paths": [str(p.relative_to(root)) for p in found],
            "runs_gate": runs_gate, "claims": claims}


# ─────────────────────────── 通道二：本地 hook ───────────────────────────


def read_hooks_path(root: Path) -> tuple[str | None, str]:
    """读 `git config core.hooksPath`。返回 (值, 错误说明)。

    读不到时返回 (None, 原因) —— 调用方据此落「未测」，不落「没配」。
    """
    try:
        r = subprocess.run(["git", "config", "core.hooksPath"], cwd=str(root),
                           capture_output=True, text=True, timeout=10)
    except Exception as exc:                                    # noqa: BLE001
        return None, f"git config 不可用：{type(exc).__name__}: {exc}"
    # 退出码 1 = 这个键没设过（正常的「没配」），不是错误。
    if r.returncode == 1:
        return None, ""
    if r.returncode != 0:
        return None, f"git config 退出码 {r.returncode}：{(r.stderr or '').strip()[:120]}"
    val = (r.stdout or "").strip()
    return (val or None), ""


def scan_hook(root: Path, hooks_path: str | None = None,
              hooks_path_err: str = "") -> dict:
    """读本地 hook 通道。

    `hooks_path` 为 None 时读真实 git 配置；controls 可显式注入。
    """
    if hooks_path is None and not hooks_path_err:
        hooks_path, hooks_path_err = read_hooks_path(root)
    if hooks_path_err:
        return {"state": "untested", "dir": None, "files": [],
                "runs_gate": False, "claims": False, "why": hooks_path_err,
                "tracked": False}

    if hooks_path:
        d = Path(hooks_path)
        if not d.is_absolute():
            d = root / d
        tracked_dir = True
    else:
        d = root / ".git" / "hooks"
        tracked_dir = False

    files: list[Path] = []
    if d.is_dir():
        files = sorted(x for x in d.iterdir()
                       if x.is_file() and not x.name.endswith(".sample"))
    text = "\n".join(x.read_text(encoding="utf-8", errors="ignore") for x in files)
    runs_gate = runs_gate_in(text)
    claims = bool(CLAIM_RE.search(text))

    repo_scripts = (root / HOOK_SCRIPTS_DIR)
    has_repo_scripts = repo_scripts.is_dir() and any(
        x.is_file() and not x.name.endswith(".md") for x in repo_scripts.iterdir())

    if runs_gate:
        state = RUNS_GATE
    elif files:
        state = NO_GATE
    elif has_repo_scripts:
        state = NOT_INSTALLED
    else:
        state = NONE
    return {"state": state, "dir": str(d), "files": [x.name for x in files],
            "runs_gate": runs_gate, "claims": claims, "why": "",
            "tracked": tracked_dir}


# ─────────────────────────── 通道三：远端分支保护 ───────────────────────────


def scan_remote(root: Path) -> dict:
    """远端分支保护：**本机读不到**。

    ★ 这里刻意不尝试网络请求：本脚本要在离线与沙箱里跑，
      而且带凭据的详情本来就读不到（2026-10-22 实测匿名 API 401）。
      所以它**永远**落未测 —— 但每次运行都照报，不许静默消失。
    """
    return {"state": "untested", "files": [], "runs_gate": False, "claims": False,
            "why": "本机无 gh、离线；带凭据的详情 401（2026-10-22 实测）"}


# ─────────────────────────── 判 ───────────────────────────


def judge(ci: dict, hook: dict, remote: dict):
    """返回 (reds, greens, notes, untested) —— 四本账分开，永远不合并成一个数。

    ★ 2026-10-23 就地改（装上 CI 当天就踩到的两处，都不是笔误）：

    **① 「hook 脚本在仓库里但没安装」不许是红。**
       CI 里 `core.hooksPath` 永远是未设的（fresh clone），
       所以这条一旦是红，CI 上的触发点自检就**恒红** ——
       而那正是本文件开头批评的「永远红的 CI 会被无视」。
       它是「一个可选项没被采用」，不是「配置说了假话」。降为 note。

    **② 「已配但不跑执行器、且没提验收」也不许是红。**
       一份只跑 pytest 的 CI 不是在骗人 —— 它从没声称自己跑验收。
       真正的红只有两种：**假触发**（提了 acceptance 却不引用执行器），
       与**没有任何通道跑它**。前者是骗，后者是缺。缺要在 greens 空时才红。
    """
    reds: list[str] = []
    greens: list[str] = []
    notes: list[str] = []
    untested: list[str] = []

    if ci["state"] == RUNS_GATE:
        greens.append(f"CI 通道会跑验收执行器：{ci['paths']}")
    elif ci["state"] == NO_GATE:
        if ci["claims"]:
            reds.append(f"★ 假触发（CI）：{ci['paths']} 里出现了「验收」字样，"
                        f"却**没有引用** {GATE} —— 读它的人会以为验收已经自动在跑")
        else:
            notes.append(f"CI 已配但不跑验收执行器：{ci['paths']}"
                         f"（它没有声称跑验收，所以不算假触发；但也不为验收提供触发）")

    if hook["state"] == RUNS_GATE:
        greens.append(f"本地 hook 会跑验收执行器：{hook['dir']}")
    elif hook["state"] == NO_GATE:
        if hook["claims"]:
            reds.append(f"★ 假触发（hook）：{hook['dir']} 里出现了「验收」字样，"
                        f"却**没有引用** {GATE}")
        else:
            notes.append(f"本地 hook 已配但不跑验收执行器：{hook['dir']} {hook['files']}")
    elif hook["state"] == NOT_INSTALLED:
        # ★ 不是红：见上面 ①。装上 `git config core.hooksPath tools/githooks` 才会生效，
        #   而那会改变本工作区的推送行为 —— 那是使用者的决定，不是缺陷。
        notes.append(f"**仓库里有 hook 脚本（{HOOK_SCRIPTS_DIR}）但未安装** ——"
                     f"`git config core.hooksPath` 未设置。这是一个**未采用的选项**，"
                     f"不是缺陷；CI 里它永远是未设的。"
                     f"本 clone 想启用：`bash tools/install_hooks.sh`（T-411）")
    elif hook.get("why"):
        untested.append(f"本地 hook 通道读不出：{hook['why']}")

    if remote["state"] == "untested":
        untested.append(f"远端分支保护：{remote['why']}")

    if not greens:
        reds.append("**没有任何通道会自动跑验收执行器** —— 它只在有人手动敲命令时跑。"
                    "验收判据再多，没人跑就等于没有（§2.4.2「判据与触发者两层」）")
    return reds, greens, notes, untested


def report_line(name: str, ch: dict) -> str:
    state = ch["state"]
    zh = STATE_ZH.get(state) or ("读不到（未测）" if state == "untested" else state)
    extra = ""
    if state == "untested":
        extra = f" —— {ch.get('why') or '原因未记'}"
    elif ch.get("files"):
        extra = f" —— {ch['files']}"
    return f"  · {name:6s} {zh}{extra}"


# ─────────────────────────── 反向对照 ───────────────────────────


def _fake_ci(root: Path, body: str) -> None:
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "ci.yml").write_text(body, encoding="utf-8")


def _fake_hook(root: Path, body: str, name: str = "pre-commit") -> str:
    d = root / HOOK_SCRIPTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return str(d)


def run_controls() -> int:
    print("=" * 72)
    print("触发点三条通道 · 反向对照（离线；只在临时目录里造样本）")
    print("=" * 72)
    results: list[tuple[str, bool, str]] = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(f"  {'✅' if cond else '❌'} {name}" + (f"  {detail}" if not cond else ""))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1 空仓库：三条通道都没有
        ci = scan_ci(root)
        hook = scan_hook(root, hooks_path=None, hooks_path_err="")
        ok("空仓库 → CI 通道 = 没有", ci["state"] == NONE, repr(ci["state"]))
        ok("空仓库 → hook 通道 = 没有", hook["state"] == NONE, repr(hook["state"]))

        # 2 CI 引用了验收执行器 → runs_gate
        _fake_ci(root, f"jobs:\n  a:\n    steps:\n      - run: python3 tools/{GATE}.py\n")
        ci = scan_ci(root)
        ok("CI 引用验收执行器 → runs_gate", ci["state"] == RUNS_GATE, repr(ci))

        # 3 CI 存在但不引用 → present_no_gate（不许判绿）
        _fake_ci(root, "jobs:\n  a:\n    steps:\n      - run: pytest\n")
        ci = scan_ci(root)
        ok("CI 存在但不引用 → present_no_gate", ci["state"] == NO_GATE, repr(ci["state"]))

        # 4 ★ 假触发：提到 acceptance 却不引用执行器
        _fake_ci(root, "jobs:\n  acceptance:\n    steps:\n      - run: echo ok\n")
        ci = scan_ci(root)
        reds, _, _, _ = judge(ci, {"state": NONE}, {"state": "untested", "why": "x"})
        ok("★ 假触发：CI 写「acceptance」却不引用执行器 → 必须判红",
           ci["claims"] and not ci["runs_gate"] and any("假触发（CI）" in r for r in reds),
           repr(reds[:2]))

        # 5 hook 引用验收执行器 → runs_gate
        hp = _fake_hook(root, f"#!/bin/sh\npython3 tools/{GATE}.py\n")
        hook = scan_hook(root, hooks_path=hp)
        ok("hook 引用验收执行器 → runs_gate", hook["state"] == RUNS_GATE, repr(hook["state"]))

        # 6 hook 存在但不引用 → present_no_gate
        hp2 = _fake_hook(root, "#!/bin/sh\necho hi\n")
        hook = scan_hook(root, hooks_path=hp2)
        ok("hook 存在但不引用 → present_no_gate", hook["state"] == NO_GATE, repr(hook["state"]))

        # 6b ★★★ 只在注释里提到执行器 → 必须判 present_no_gate。
        #    这组的起因是真实事故（2026-10-29）：钩子改成跑棘轮后**一次也没调**
        #    执行器，而它仍报「已配且会跑」，因为钩子里的注释写着旧命令名。
        #    判据改成「调用形状」之后，这组必须转红 —— 否则等于没改。
        hp6b = _fake_hook(
            root,
            "#!/bin/sh\n"
            "# 这里原来跑 python3 tools/verify_acceptance_run.py，现在改了\n"
            "echo hi\n",
            name="pre-push",
        )
        hook = scan_hook(root, hooks_path=hp6b)
        ok("★ 只在注释里提到执行器 → 必须 present_no_gate（名字出现过 ≠ 会跑）",
           hook["state"] == NO_GATE, repr(hook["state"]))

        # 6c ★ 经棘轮**间接**调用 → 必须判 runs_gate。
        #    反向的那一半：只认直接调用会把钩子判成假触发（改完之后就是这种形状）。
        hp6c = _fake_hook(
            root,
            "#!/bin/sh\npython3 tools/verify_acceptance_ratchet.py --run\n",
            name="pre-push",
        )
        hook = scan_hook(root, hooks_path=hp6c)
        ok("★ 经 verify_acceptance_ratchet.py --run 间接调用 → 必须 runs_gate",
           hook["state"] == RUNS_GATE, repr(hook["state"]))

        # 7 ★ 仓库有 hook 脚本但未安装 → 单列，不与「没有」混为一谈
        _fake_hook(root, "#!/bin/sh\necho hi\n")
        hook = scan_hook(root, hooks_path=None, hooks_path_err="")
        ok("★ 有 hook 脚本但 core.hooksPath 未设 → repo_scripts_not_installed",
           hook["state"] == NOT_INSTALLED, repr(hook["state"]))

        # 8 ★ 四本账不许合并：未测时结论行必须报出未测
        reds, greens, _notes, unt = judge(
            {"state": RUNS_GATE, "paths": ["x"], "runs_gate": True, "claims": True},
            {"state": NONE},
            {"state": "untested", "why": "本机读不到"})
        ok("★ 有绿时也必须报出未测（远端不许静默消失）",
           bool(greens) and any("远端" in u for u in unt), repr(unt))

        # 9 ★ 无绿必红：没有任何通道跑它 → 必须红（否则这条票的整件事会静默通过）
        reds, greens, _, _ = judge({"state": NONE}, {"state": NONE},
                                   {"state": "untested", "why": "x"})
        ok("★ 没有任何通道会跑它 → 必须红（不是「未测就好」）",
           not greens and any("没有任何通道" in r for r in reds), repr(reds[-1:]))

        # 10 hook 通道读不出 → 未测，不许当成「没配」
        hook = scan_hook(root, hooks_path=None, hooks_path_err="git 不可用")
        ok("hook 读不出 → untested（不是 none）", hook["state"] == "untested", repr(hook["state"]))

    bad = [r for r in results if not r[1]]
    print("-" * 72)
    if bad:
        print(f"❌ {len(bad)}/{len(results)} 项不符")
        for n, _, d in bad:
            print(f"   {n}  {d}")
        return 1
    print(f"✅ {len(results)}/{len(results)} 项反向对照全过（该红、该绿、该未测三侧都在）")
    return 0


# ─────────────────────────── 主 ───────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--scope", choices=("all", "ci"), default="all",
                    help="all=三通道全读（默认，本地用）；"
                         "ci=只判 CI 通道（CI 里用，见下）")
    args = ap.parse_args()
    if args.controls:
        return run_controls()

    root = Path(args.root)
    ci = scan_ci(root)

    # ── `--scope ci`：CI 里只判它自己那一条通道 ──────────────────────────
    #
    # ★ 这个模式存在的理由，是**装上 CI 当天就踩到的一个自相矛盾**：
    #   三通道全读时，hook 通道在 fresh clone 里永远是「未安装」，
    #   远端分支保护永远读不到 —— 于是本脚本在 CI 里**必然退 2**。
    #   而 CI 步骤退 2 就是失败，于是这条 job 会**永远红**。
    #   那正是本文件开头批评的东西（「永远红的 CI 会被无视」），
    #   只不过这次犯在**触发点自己的自检**上。
    #
    #   两种错误修法，都别用：
    #     · 在 workflow 里写 `|| true` —— 假绿，等于没装；
    #     · 把 hook/远端降成永不判红 —— 那本地就失去了这两条读数。
    #
    #   正确做法是**换判据，不是放宽判据**：CI 里唯一能判、且该判的是
    #   「CI 配置存在且引用了验收执行器」。其余两条通道本机读不到就是读不到，
    #   让 CI 去判它既做不到、判出来的也不是这件事。
    if args.scope == "ci":
        print("=" * 72)
        print("T-145 · CI 通道自检（只看这一条；hook / 远端在 CI 里读不到，不在此判）")
        print("=" * 72)
        print(report_line("CI", ci))
        print()
        if ci["state"] == RUNS_GATE:
            print(f"  ✅ CI 会跑验收执行器：{ci['paths']}")
            print("-" * 72)
            print("✅ 退 0：CI 通道成立。")
            print("   ★ 不判 hook / 远端 —— 它们在这里读不到，判了也只是把"
                  "「读不到」写成「不成立」。")
            return 0
        if ci["state"] == NO_GATE and ci["claims"]:
            print(f"  ❌ ★ 假触发：{ci['paths']} 提了「验收」却不引用 {GATE}")
            print("-" * 72)
            print("❌ 退 1：这是「配置说了假话」，比没有 CI 更危险。")
            return 1
        if ci["state"] == NONE:
            print("  ❌ 没有任何 CI 配置 —— 那本 job 就不该被跑到")
            print("-" * 72)
            print("❌ 退 1：CI 通道不成立。")
            return 1
        print(f"  ❌ CI 已配但不引用 {GATE}：{ci['paths']}")
        print("-" * 72)
        print("❌ 退 1：CI 通道不成立。")
        return 1

    hook = scan_hook(root)
    remote = scan_remote(root)
    reds, greens, notes, untested = judge(ci, hook, remote)

    print("=" * 72)
    print("T-142 · 验收执行器有没有自动触发点（三条通道分别读）")
    print("=" * 72)
    print(report_line("CI", ci))
    print(report_line("hook", hook))
    print(report_line("远端", remote))
    print()

    for g in greens:
        print(f"  ✅ {g}")
    for r in reds:
        print(f"  ❌ {r}")
    for n in notes:
        print(f"  · {n}")
    for u in untested:
        print(f"  ⚠ {u}")

    print("-" * 72)
    if reds:
        print(f"❌ 退 1：{len(reds)} 项红" +
              (f"（另有 {len(untested)} 项未测，见上）" if untested else ""))
        return 1
    if untested:
        print(f"⚠ 退 2：无可判红项，但有 {len(untested)} 项未测 —— **不是通过**")
        return 2
    print("✅ 退 0：至少一条通道会自动跑验收执行器。")
    print(f"   ★ 不证明远端分支保护拦得住合并 —— 本机读不到（{remote['why']}）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
