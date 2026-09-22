#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_reference_census.py —— **零引用可执行文件**的棘轮：只许减，不许增

## 这个文件为什么存在

2026-09-22 的结构性诊断（P2 #18）量到：**已跟踪的可执行文件里有 31 个，没有任何
其它已跟踪文件提到过它们的名字** —— 既不被 import、也不被 spawn、也不在文档里出现。
（诊断原文写 32；复算为 31，差的一个见 `.ua/reference-census.md` 的口径说明。）

诊断本身**不是执行点**：它是 `.ua/` 下一份未入库的报告，靠人记得去看。
于是「死代码面」这件事就变成了 AGENTS.md §2.4 点名的那个形状 ——
**一个写下来的读数，没有任何一行代码在拦它继续变大**。本脚本就是那一行。

## 口径（先声明，再判定 —— 换口径必须改这里，不许偷偷改断言）

**口径 = 已入库文件**。取 `git ls-files -z`。**必须带 `-z`**：不带时 git 会把含非 ASCII
的路径转义成 `"PMO/\\344\\270\\212..."`，任何读取都会失败并**静默跳过**那些文件，
于是「被提到的次数」被系统性地低估、0 次桶被高估。这条不是推测：
诊断第一版就是这么算出「39 个零引用」的，改用 `-z` 后是 32（见 `.ua/reference-census.md`）。

  * **可执行面**：后缀落在 `exec_exts` 里的在册文件（默认 `.py .mjs .js .sh .plist`，
    与诊断脚本 `.ua/reference-census.cjs` 逐字同口径）。
  * **提及**：对可执行文件 F，数**其它**在册文本文件里有几个文件**逐字包含**
    F 的 basename（`body.includes(base)`，不是词边界匹配）。
    被提到不等于「它是活的」，可能只是散文里提了一句；**0 次才是信号**。
  * **二进制跳过**：含 NUL 字节的文件不进提及池（它提不了名字）。跳过的个数会打印出来。
  * **读不出的文件** → 退 2（未测）。静默跳过会让池子变小、0 次桶变大，
    而那正好是上面 `-z` 那个事故的形状 —— 所以它必须是「未测」，不许当成读数。

## ★ 排除集：不排除，这个棘轮会把自己刷成恒绿

基线文件必须**列出**它钉住的每一个零引用文件 —— 而「列出来」在口径里就等于
**提到它们**。若不排除，基线一落盘，那 31 个文件立刻各自多了一次提及、
零引用集合变成空集，于是**「0 个零引用」这个读数看起来完美，而它只是基线的倒影**。

所以提及池 = 在册文件 − {本脚本自身, 基线文件}。这不是装饰：
`--controls` 的 B2 就是**反面对照**（不排除时，基线上被点名的文件必须从零引用里消失）。

排除集**恰好**是那两个路径（A5 断言）—— 否则它会慢慢长成一张免死金牌。

## 断言

  A1 分母非空且装得下基线：`exe` 非空，且 `len(exe) >= len(baseline.files)`
     （git 取不到、口径写错、路径被转义 —— 都会先在这里塌，而不是伪装成「0 个零引用」）
  A2 **棘轮**：当前零引用集合 ⊆ 基线集合（出现新面孔即红）
  A3 零引用数 <= 基线数（棘轮的字面判据，与 A2 互为冗余，两条都留着）
  A4 基线里每个文件仍在册、且仍在可执行面内（否则基线在拿不存在的文件充数）
  A5 排除集恰好 == {本脚本, 基线文件}
  A6 已改善（基线里有、现在不再零引用）**不算红**，只报告 —— 棘轮只禁增长，
     而「锁住这次改善」需要人显式重钉基线（本脚本不会自动改基线，见 §2.4.4）
  A7 **池子里不许有人枚举这份名单**（同一个在册文件命中 ≥ `ENUM_RED` = 10 个基线
     文件名即算）。这是 #19 与 #18 的接口露出来的一处耦合：**若 `.ua/` 哪天进 L1**
     （Q38 的选项 A/C），`.ua/reference-census.md` 就会进池 —— 而它逐条列着这 31 个
     文件，于是每一个都变成「有人提及」、零引用集合清空、**棘轮变空但全绿**。
     实测（2026-09-22）：在册文件里最大命中数是 **1**，那份未入库的报告是 **31**。
     修法是显式的：把它加进排除集（A5 会一起要求改），或者重钉基线。
  B1–B9 `--controls`：纯函数喂合成树，正反两侧都证（§2.1：反向对照只在内存里做）

## 退出码

  0 全过 ／ 1 有红 ／ 2 未测（git 不可用、有文件读不出）—— **未测 ≠ 通过 ≠ 红**

## 用法

    python3 tools/verify_reference_census.py            # 主读数 + 逐条问题
    python3 tools/verify_reference_census.py --list     # 把当前零引用清单打出来（重钉基线用）
    python3 tools/verify_reference_census.py --controls # 反向对照（离线、不动盘）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: 本脚本自己（相对仓库根）。要**排除出提及池**，理由见 docstring。
SELF_REL = "tools/verify_reference_census.py"
#: 基线：钉住「某时某刻的零引用集合」。排除出提及池的理由同上。
BASELINE_REL = "tools/reference-census-baseline.json"
BASELINE = REPO / BASELINE_REL

#: 可执行面。与 `.ua/reference-census.cjs` 同口径（那一版没有 `.cjs`，这里是**继承**
#: 而不是修正 —— 换口径会让读数与诊断不可比，而可比性正是本棘轮要保住的东西）。
EXTS = (".py", ".mjs", ".js", ".sh", ".plist")

#: A7 的门槛：**同一个在册文件里出现 ≥ 这么多个基线文件名**，就认定它在「枚举这份名单」。
#: 实测（2026-09-22）全仓在册文件对基线 31 个 basename 的最大命中数是 **1**
#: （`tools/ws_watch.sh` / `tools/ws_raw_trace.mjs` / `tools/probe_cards*.mjs` /
#: `tools/build_product_line_matrix.py` 各 1），而**未入库**的 `.ua/reference-census.md`
#: 命中 **31**。门槛取 10：离现状足够远（不会误报），离真枚举足够近（抓得到）。
ENUM_RED = 10


class Unreadable(Exception):
    """读不出 —— 落未测（退 2），不许当成「没有零引用文件」。"""


# ── 采集 ─────────────────────────────────────────────────────────────────────

def git_tracked() -> list:
    """在册文件。**必须 `-z`**，理由见 docstring。取不到返回 None（= 未测）。"""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120,
        )
    except Exception:  # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    return sorted(x for x in out.stdout.decode("utf-8", "replace").split("\0") if x)


def read_pool(tracked: list):
    """把每个在册文件读成文本。返回 (texts, binary, unreadable)。"""
    texts, binary, unreadable = {}, [], []
    for f in tracked:
        p = REPO / f
        try:
            buf = p.read_bytes()
        except Exception as exc:  # noqa: BLE001
            unreadable.append(f"{f}（{exc}）")
            continue
        if b"\0" in buf:
            binary.append(f)
            continue
        texts[f] = buf.decode("utf-8", "replace")
    return texts, binary, unreadable


# ── 纯函数：口径与判定（`--controls` 直接喂它内存样本，不碰盘） ──────────────

def census(tracked, texts, exts=EXTS, exclude=(), watch=()):
    """纯函数：返回 exe / zero / one / watch（谁在枚举基线名单）。

    `watch` = 基线里那些 basename。A7 用它找出「池子里有人把这份名单抄了一遍」——
    那个文件一旦进池，它点名的每个文件都会变成「有人提及」，棘轮就空了。
    """

    def is_exe(f):
        return any(f.endswith(e) for e in exts)

    exe = sorted(f for f in tracked if is_exe(f))
    skip = set(exclude)
    pool = [(g, b) for g, b in texts.items() if g not in skip]
    zero, one = [], []
    for f in exe:
        base = f.rsplit("/", 1)[-1]
        refs = [g for g, b in pool if g != f and base in b]
        if not refs:
            zero.append(f)
        elif len(refs) == 1:
            one.append((f, refs[0]))
    enum = []
    if watch:
        for g, b in pool:
            n = sum(1 for w in watch if w in b)
            if n:
                enum.append((n, g))
        enum.sort(reverse=True)
    return {"exe": exe, "zero": zero, "one": one, "enum": enum}


def judge(cur, baseline_files, tracked, exclude) -> dict:
    """纯函数：给定现场读数与基线，返回 problems / new / improved。"""
    problems = []
    exe, zero = cur["exe"], set(cur["zero"])
    base = set(baseline_files)

    # A5 排除集恰好是两个路径（先判它：它错了，下面的读数就不可信）
    if set(exclude) != {SELF_REL, BASELINE_REL}:
        problems.append(
            "A5 排除集 == %s —— 实测是 %s。它长一条，棘轮就瞎一块"
            % (sorted({SELF_REL, BASELINE_REL}), sorted(exclude))
        )

    # A7 池子里不许有人枚举这份名单（#19 与 #18 的耦合，2026-09-22 补）
    hot = [(n, g) for n, g in (cur.get("enum") or []) if n >= ENUM_RED]
    if hot:
        problems.append(
            "A7 有 %d 个在册文件在**枚举基线名单**（命中 ≥ %d / %d）:\n      %s\n      "
            "→ 它一旦留在池子里，被它点名的文件就全变成「有人提及」，棘轮当场变空 —— "
            "这正是基线自己要被排除的那个理由，只是换了个文件重演。"
            "（典型来路：Q38 若选「把 `.ua/` 提进 L1」，`.ua/reference-census.md` 就会进池，"
            "它逐条列着这 31 个文件。）修法只有两条，都要显式做：把它加进排除集"
            "（`--controls` 的 A5 与本段会一起要求你改这句），或者重钉基线。"
            % (len(hot), ENUM_RED, len(base), "\n      ".join(f"{g}（{n} 个）" for n, g in hot))
        )

    # A1 分母
    if not tracked:
        problems.append("A1 `git ls-files -z` 一个文件都没返回 —— 口径塌了，不是「零引用为 0」")
    elif len(exe) < len(base):
        problems.append(
            "A1 可执行文件只有 %d 个，比基线的 %d 条还少 —— 分母装不下基线，读数不可信"
            % (len(exe), len(base))
        )

    # A2 棘轮
    new = sorted(zero - base)
    if new:
        problems.append(
            "A2 新出现 %d 个零引用文件（棘轮只许减）:\n      %s"
            % (len(new), "\n      ".join(new))
        )

    # A3 棘轮（字面判据）
    if len(zero) > len(base):
        problems.append("A3 零引用 %d 个 > 基线 %d 个" % (len(zero), len(base)))

    # A4 基线仍在册、仍在可执行面内
    gone = sorted(b for b in base if b not in set(tracked))
    if gone:
        problems.append(
            "A4 基线里有 %d 条已经不在册:\n      %s\n      "
            "→ 删掉死代码是好事，但基线必须跟着重钉（棘轮只许减，不许拿幽灵充数）"
            % (len(gone), "\n      ".join(gone))
        )
    notexe = sorted(b for b in base if b in set(tracked) and not any(b.endswith(e) for e in EXTS))
    if notexe:
        problems.append(
            "A4 基线里有 %d 条不再是可执行面文件（后缀不在 %s）:\n      %s"
            % (len(notexe), " ".join(EXTS), "\n      ".join(notexe))
        )

    return {
        "problems": problems,
        "new": new,
        "improved": sorted(base - zero),
        "n_zero": len(zero),
        "n_base": len(base),
        "n_exe": len(exe),
    }


def verdict(n_problems: int, untested: list) -> tuple:
    """纯函数：结论行与退出码。`--controls` 直接断言它**不许撒谎**（§2.4.2 H7 口径）。"""
    if n_problems:
        line = "❌ 有红 %d 处" % n_problems
        if untested:
            line += "；另有 %d 处**未测**（有红时也必须报出来）" % len(untested)
        return 1, line
    if untested:
        return 2, "⚠ %d 处未测 —— 这不是通过（退 2，与 §2.4.2 同口径）" % len(untested)
    return 0, "✅ 零引用面没有增长"


# ── 反向对照 ─────────────────────────────────────────────────────────────────

def controls() -> int:
    """纯函数喂合成树：不动盘、不联网（§2.1「反向对照只在内存里做」）。"""
    A, B = SELF_REL, BASELINE_REL
    # 合成树：alpha 只因**基线**提到它；beta 被 notes.md 提到；gamma 谁都没提。
    tracked = [A, B, "tools/alpha.py", "tools/beta.py", "tools/gamma.py", "notes.md"]
    texts = {
        A: "本脚本不点名任何可执行文件",
        B: "基线列了：tools/alpha.py",
        "tools/alpha.py": "x",
        "tools/beta.py": "x",
        "tools/gamma.py": "x",
        "notes.md": "跑 tools/beta.py 就行",
    }
    excl = {A, B}
    full = census(tracked, texts, EXTS, excl)
    no_excl = census(tracked, texts, EXTS, {A})          # 反面：不排除基线
    exe_only_self = census(tracked, texts, EXTS, {SELF_REL})

    # ★ 这个合成树里 A 就是 SELF_REL 本身，而它**也是可执行面的一员** ——
    #   它被排除出提及池（没人能提到它），所以它自己必然落进零引用集合。
    #   基线里必须含它，否则每一条控制都会先撞上「A2 新面孔 = A」。
    #   （第一版控制忘了这一点，B1/B3/B7 三条全红 —— 红的是**期望**，不是代码。）
    base_ok = [SELF_REL, "tools/alpha.py", "tools/gamma.py"]
    j_ok = judge(full, base_ok, tracked, excl)

    # A7 的合成树：基线长到超过门槛（13 条），而池子里有一份把 13 条全抄了一遍的文档。
    # ★ 第一版直接拿 3 条的 base_ok 去喂，A7 当然不响（3 < 门槛 10）——
    #   红的是**期望**：门槛是 10，样本必须**跨过**它，否则这条控制证明不了任何事。
    many = [f"tools/filler{i:02d}.py" for i in range(10)]
    base_many = base_ok + many
    tracked_many = tracked + ["docs/census.md"] + many
    texts_many = dict(texts)
    texts_many["docs/census.md"] = "\n".join(base_many)
    watch_many = [b.rsplit("/", 1)[-1] for b in base_many]

    cases = [
        ("B1 探针：合成树里 alpha/gamma 零引用、beta 有提及（检测器活着）",
         lambda: full["zero"] == sorted([SELF_REL, "tools/alpha.py", "tools/gamma.py"])),
        ("B1b 探针：恰 1 次提及的桶也算得出来",
         lambda: full["one"] == [("tools/beta.py", "notes.md")]),
        ("★ B2 反面对照：**不排除基线**时，基线点名的 alpha 从零引用里消失 —— "
         "这正是「棘轮把自己刷成恒绿」的形状",
         lambda: ("tools/alpha.py" not in no_excl["zero"]) and ("tools/alpha.py" in full["zero"])),
        ("B2b 只排除自身也不够：基线仍在池里，alpha 照样消失",
         lambda: "tools/alpha.py" not in exe_only_self["zero"]),
        ("B3 棘轮有牙：基线漏掉一个零引用文件 → A2 必须红，且点得出是哪一个",
         lambda: (not j_ok["problems"]) and bool(
             judge(full, ["tools/gamma.py"], tracked, excl)["problems"]
         ) and "tools/alpha.py" in judge(full, ["tools/gamma.py"], tracked, excl)["new"]),
        ("B4 分母塌了（tracked 为空）→ 必须红，不许因为「没有零引用」而绿",
         lambda: bool(judge(census([], {}, EXTS, excl), base_ok, [], excl)["problems"])
         and any("A1" in p for p in judge(census([], {}, EXTS, excl), base_ok, [], excl)["problems"])),
        ("B5 基线拿不在册的文件充数 → A4 必须红",
         lambda: any("A4" in p for p in
                     judge(full, base_ok + ["tools/deleted.py"], tracked, excl)["problems"])),
        ("B6 排除集被扩成三条 → A5 必须红（免死金牌不许长大）",
         lambda: any("A5" in p for p in
                     judge(full, base_ok, tracked, excl | {"notes.md"})["problems"])),
        ("B7 改善不算红：基线里那条现在已经有人提及（beta）→ 只记 improved，不判红",
         lambda: (lambda j: (not j["problems"]) and j["improved"] == ["tools/beta.py"])(
             judge(full, base_ok + ["tools/beta.py"], tracked, excl))),
        ("B8 结论行不许撒谎：红 + 未测同时存在时，红优先**且必须报出未测**",
         lambda: verdict(1, ["x"])[0] == 1 and "未测" in verdict(1, ["x"])[1]),
        ("B8b 未测 ≠ 通过：只有未测时必须退 2，且那行里不许出现 ✅",
         lambda: verdict(0, ["x"])[0] == 2 and "✅" not in verdict(0, ["x"])[1]),
        ("B8c 反向对照：都干净时必须退 0",
         lambda: verdict(0, [])[0] == 0),
        ("★ B9 A7 有牙：池子里有个文件把基线名单抄了一遍（%d 条 ≥ 门槛 %d）→ 必须红"
         "（否则棘轮会被刷空）" % (len(base_many), ENUM_RED),
         lambda: any("A7" in p for p in judge(
             census(tracked_many, texts_many, EXTS, excl, watch_many),
             base_many, tracked_many, excl)["problems"])),
        ("★ B9b 反面对照：同一份枚举内容**被排除**之后，A7 必须闭嘴（证明它判的是池子，不是文本）",
         lambda: not any("A7" in p for p in judge(
             census(tracked_many, texts_many, EXTS, excl | {"docs/census.md"}, watch_many),
             base_many, tracked_many, excl)["problems"])),
        ("B9c 反向对照：只提一两个名字（正常散文引用）不许触发 A7",
         lambda: (lambda t: not any(
             "A7" in p for p in judge(
                 census(tracked + ["docs/note.md"], {**t, "docs/note.md": "见 tools/alpha.py"},
                        EXTS, excl, [b.rsplit("/", 1)[-1] for b in base_ok]),
                 base_ok, tracked + ["docs/note.md"], excl)["problems"]))(texts)),
    ]
    bad = 0
    print("=" * 72)
    print("零引用棘轮 · 反向对照（离线；纯函数、不动盘、不联网）")
    print("=" * 72)
    for label, fn in cases:
        try:
            good = bool(fn())
        except Exception as exc:  # noqa: BLE001
            good, label = False, f"{label} —— 抛异常 {exc!r}"
        print(f"  {'✅' if good else '❌'} {label}")
        bad += 0 if good else 1
    print("-" * 72)
    print(("✅ 反向对照 %d 项全过" % len(cases)) if not bad
          else "❌ 反向对照 %d/%d 项不通过" % (bad, len(cases)))
    return 0 if not bad else 1


# ── 主入口 ───────────────────────────────────────────────────────────────────

def load_baseline() -> list:
    if not BASELINE.is_file():
        raise Unreadable(f"没有基线文件：{BASELINE_REL}（棘轮必须先钉一个读数）")
    try:
        d = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise Unreadable(f"{BASELINE_REL} 不是合法 JSON：{exc}")
    files = d.get("files")
    if not isinstance(files, list) or not files:
        raise Unreadable(f"{BASELINE_REL} 的 `files` 读不出或为空 —— 空基线会让 A2 恒真")
    if not all(isinstance(x, str) for x in files):
        raise Unreadable(f"{BASELINE_REL} 的 `files` 里有非字符串条目")
    return files


def main(argv) -> int:
    if "--controls" in argv:
        return controls()

    untested, problems = [], []
    try:
        baseline_files = load_baseline()
    except Unreadable as exc:
        untested.append(str(exc))
        baseline_files = []

    tracked = git_tracked()
    if tracked is None:
        untested.append("`git ls-files -z` 取不到（git 不可用？）—— 在册集合未知")
        tracked = []

    cur = {"exe": [], "zero": [], "one": [], "enum": []}
    binary = []
    if tracked:
        texts, binary, unreadable = read_pool(tracked)
        if unreadable:
            untested.append(
                "%d 个在册文件读不出（静默跳过会让 0 次桶虚高）: %s"
                % (len(unreadable), "；".join(unreadable[:5]))
            )
        watch = sorted({b.rsplit("/", 1)[-1] for b in baseline_files})
        cur = census(tracked, texts, EXTS, {SELF_REL, BASELINE_REL}, watch)

    j = judge(cur, baseline_files, tracked, {SELF_REL, BASELINE_REL})
    problems = j["problems"]

    print("=" * 72)
    print("零引用可执行文件普查 · 棘轮")
    print("=" * 72)
    print(f"  口径        git ls-files -z · 可执行面 {' '.join(EXTS)}")
    print(f"  在册文件    {len(tracked)} 个（二进制跳过 {len(binary)} 个，不进提及池）")
    print(f"  可执行面    {j['n_exe']} 个")
    print(f"  零引用      {j['n_zero']} 个   ← 棘轮上界 {j['n_base']} 个（{BASELINE_REL}）")
    print(f"  恰 1 次提及 {len(cur['one'])} 个")
    hot = [(n, g) for n, g in (cur.get("enum") or []) if n >= ENUM_RED]
    print(f"  枚举基线者 {len(hot)} 个（同一文件里命中 ≥ {ENUM_RED} 个基线文件名即算；门槛理由见 ENUM_RED）")
    print(f"  排除出池    {SELF_REL} · {BASELINE_REL}（不排除，基线会把它自己点名的清单刷没）")
    if j["improved"]:
        print(f"  ★ 已改善    {len(j['improved'])} 个不再零引用（不判红；要锁住这次改善就重钉基线）:")
        for f in j["improved"]:
            print(f"      {f}")
    if "--list" in argv:
        print("\n── 当前零引用清单（重钉基线用）──")
        for f in cur["zero"]:
            print(f"      {f}")
    if untested:
        print("\n── 未测 %d 处 ──" % len(untested))
        for u in untested:
            print(f"  ⚠ {u}")
    if problems:
        print("\n── 有问题 %d 处 ──" % len(problems))
        for p in problems:
            print(f"  ❌ {p}")

    code, line = verdict(len(problems), untested)
    print("\n" + line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
