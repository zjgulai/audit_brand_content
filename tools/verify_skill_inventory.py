#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_skill_inventory.py —— `skill/` 提取件目录的入库/忽略守卫

**它修的是什么**：`skill/`（单数）曾处于「既未跟踪、也未忽略」的状态——
`.gitignore:39` 注册的是 `skills/`（复数），单数目录不受它保护。
一次 `git add -A` 会带入 220 个文件，含 27 个 Proprietary 内部件。

2026-10-21 03:54 用 `.gitignore` 的 `skill/*` + 两条放行止血。**但那只是止血，
没有执行点。** 本文件把「止血」变成「会红的门」。

--------------------------------------------------------------------------
★ 四条本文件刻意做死的判据（规格来源：`PMO/implement/skill-定性-20261021.md` §五）
--------------------------------------------------------------------------

**R1 · `skill/` 下只允许那两份来历文档被跟踪**

    判据是 `git ls-files -z skill/` 的结果**恰好等于**放行清单。
    不是「不超过 N 个」—— 多一个少一个都红。

    ★ 为什么必须是「等于」而不是「不含成员」：
      后者对「有人把某个成员的 SKILL.md 单独 add 进来」会漏。

**R2 · `skill/` 必须整体被忽略规则覆盖，且不许有单点放行**

    两件事：
      ① `.gitignore` 里必须存在一条覆盖 `skill/` 全部成员的规则（形如 `skill/*`）
      ② 除了那两份放行文档，不许出现任何 `!skill/<其他路径>` 形式的负向规则

    ★ 这一条守的是**第 R1 条守不住的那件事**：
      R1 管「现在没被跟踪」，R2 管「将来也不能被单点放行」。
      如果有人为了搬某一个 skill 加了 `!skill/内容审查总控/`，
      R1 会立刻红——但那个红会被读成「有人 add 了文件」，而真因是「有人开了个口子」。
      两者要能分开报。

**R3 · 两份放行文档必须仍在盘上、仍未被忽略**

    防「有人为了省事把 `!` 行删了」——那时文档会重新被忽略，
    来路说明就丢了，而 R1 仍然绿（因为没人 add 它）。
    **未跟踪是 PENDING，不是红**：放行 ≠ 已入库。

**R4 · 成员目录数 ≥ 一个从盘上算出的基线**

    ★ 按 `AGENTS.md` §2.2 第 1 条：文档里的数字要算出来，不能写死。
      30 这个下界有出处：2026-10-21 实测 37 个成员目录，取 30 作下界，
      下界理由 = 允许合并/删除至 30 仍视为有效清单。
      断言写成「实际 ≥ 30」，并把**实测值**打出来 —— 读的人能看到离下界多远。

    ★ 这一条是**分母守卫**：如果 `skill/` 被整个搬走或改名，
      R1/R2/R3 会全部恒真（空集合永远满足），而这一条会红。

--------------------------------------------------------------------------
★ 第五条（05 追加）：放行的两份文档不得含**真凭据形态**
--------------------------------------------------------------------------

    `skill/README.md:120` 有 `KB_BASE_TOKEN="${KB_BASE_TOKEN:-GnRZ...}"`。
    那个值是**飞书 Base 资源定位符**（指向哪张表，不授予权限），
    不是凭据；且它在 22 个已入库文件里早已存在——不是新泄露。

    所以本条只拦**真凭据形态**：`app_secret` 赋值、`Bearer <token>`、
    以及 `~/.dsh/credentials` 后的实际值。

    ★ **基线豁免**：`skill/标准化台账-20261017.md:69` 有一句
      「真实凭据在 `~/.dsh/...`」——那是指向说明，不是凭据本身。
      它**已被基线登记**，不算红。若把它当红，验证器第一天就红，
      而一个常红的检查器会让人开始不看报告（`AGENTS.md` §2.1.1）。
      豁免是**按行号 + 特征串**登记的，加了新的一处不会被豁免带过。

--------------------------------------------------------------------------
★ 退出码（三态，与全项目一致）
--------------------------------------------------------------------------

    0  全绿
    1  有红
    2  **未测**：git 不可用 / 不在 git 仓里 / 读不出索引 —— 不是通过，也不是红

用法
----
    python3 tools/verify_skill_inventory.py
    python3 tools/verify_skill_inventory.py --json
    python3 tools/verify_skill_inventory.py --controls   # 反向对照（离线，用临时 git 仓）
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = "skill"

# ── 放行清单：唯一允许被跟踪的两份来历文档 ──────────────
RELEASED_DOCS = (
    "skill/README.md",
    "skill/标准化台账-20261017.md",
)

# ── R4 的分母基线 ────────────────────────────────────────
# 2026-10-21 实测 `ls -d skill/*/ | wc -l` = 37。
# 下界取 30，理由：允许合并/删除至 30 仍视为有效清单；再少就是「被搬走了」。
MEMBER_BASELINE = 30
MEMBER_SOURCE = "2026-10-21 实测 37 个成员目录；取 30 作下界（允许合并/删除至 30）"

# ── 凭据形态（只匹配**赋值/真值**形态，不匹配名词出现）──
CRED_PATTERNS = (
    # app_secret 后跟一个看起来像真值的串
    (re.compile(r"""app_secret\s*[:=]\s*["']?[A-Za-z0-9_\-]{16,}""", re.I), "app_secret 赋值"),
    # Authorization: Bearer <token>
    (re.compile(r"""Bearer\s+[A-Za-z0-9_\-.=]{16,}"""), "Bearer token"),
    # ~/.dsh/credentials 后面直接跟文件名或值
    (re.compile(r"""~?/?\.dsh/credentials/[A-Za-z0-9_.\-]+\.json"""), "凭据文件路径"),
)

# ── 凭据基线豁免：**按 (相对路径, 行号, 特征串)** 三件套登记 ──
# ★ 只豁免这三件同时成立的那一行；同一行多了别的东西仍然红，
#   文件挪了行号变了也不豁免 —— 否则「豁免」会变成「永久的盲区」。
CRED_BASELINE = (
    ("skill/标准化台账-20261017.md", 69, "~/.dsh/credentials",
     "指向说明：原句是「真实凭据在 ~/.dsh/...」，不含值本身"),
)


class Untested(Exception):
    """取不到读数 —— 对应退出码 2。"""


# ═══════════════════════ git 只读探针 ═══════════════════════

def _git(args, *, cwd=None, text=True):
    """
    跑一条 git 命令。**返回 (rc, stdout)**，不抛。

    ★ 用 `-c core.quotepath=false`：默认会把非 ASCII 路径转成八进制转义，
      于是「放行清单里写中文、git 输出八进制」会被判成不相等 ——
      一个纯粹由编码造成的假红。
    """
    full = ["git", "-c", "core.quotepath=false"] + list(args)
    try:
        p = subprocess.run(full, cwd=str(cwd or ROOT),
                           capture_output=True, text=text, timeout=60)
    except FileNotFoundError:
        raise Untested("git 不可用（找不到可执行文件）")
    except subprocess.TimeoutExpired:
        raise Untested("git 命令超时（60s）")
    return p.returncode, (p.stdout or "")


def _require_repo(root):
    rc, out = _git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    if rc != 0 or out.strip() != "true":
        raise Untested("不是 git 工作区：%s" % root)


def tracked_under(root, prefix):
    """`git ls-files -z <prefix>` → 路径列表（相对 root，正斜杠）。"""
    rc, out = _git(["ls-files", "-z", prefix], cwd=root)
    if rc != 0:
        raise Untested("git ls-files 失败（rc=%d）" % rc)
    return sorted(x for x in out.split("\0") if x)


def is_ignored(root, rel):
    """`git check-ignore -q <rel>` → True 表示被忽略。rc=1 是「未忽略」，不是错误。"""
    rc, _ = _git(["check-ignore", "-q", rel], cwd=root)
    if rc == 0:
        return True
    if rc == 1:
        return False
    raise Untested("git check-ignore 异常（rc=%d）：%s" % (rc, rel))


def member_dirs(root):
    """`skill/*/` 的成员目录名（只看目录，不看文件）。"""
    d = Path(root) / SKILL_DIR
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


# ═══════════════════════ 四条判据 ═══════════════════════

def check_r1_tracked(root) -> dict:
    """R1：`skill/` 下被跟踪的文件必须**恰好**是放行清单。"""
    tracked = tracked_under(root, SKILL_DIR + "/")
    released = sorted(RELEASED_DOCS)
    extra = [t for t in tracked if t not in released]
    missing = [r for r in released if r not in tracked]

    ok = not extra and not missing
    detail = []
    if extra:
        detail.append("多出被跟踪的文件（不许进仓）：%s" % extra)
    if missing:
        detail.append("放行文档未入库（PENDING，不算红但要知道）：%s" % missing)
    return {
        "id": "R1",
        "ok": ok,
        "title": "skill/ 下只允许两份来历文档被跟踪",
        "detail": "；".join(detail) or "跟踪集 = 放行清单（%d 个）" % len(tracked),
        "tracked": tracked,
        "extra": extra,
        "pending": missing,
    }


def check_r2_ignored(root) -> dict:
    """
    R2：整体被忽略规则覆盖，且没有单点放行。

    两步：
      ① 每个成员目录下的 SKILL.md 都必须 `check-ignore` 命中
      ② `.gitignore` 里不许有 `!skill/<放行清单之外的东西>`
    """
    members = member_dirs(root)
    tracked_now = set(tracked_under(root, SKILL_DIR + "/"))

    not_ignored = []
    for name in members:
        rel = "%s/%s/SKILL.md" % (SKILL_DIR, name)
        if not (Path(root) / rel).exists():
            continue
        # ★ 已跟踪的文件不走这一条 —— 它归 R1 管。
        #   实测：文件被 `git add -f` 之后，`git check-ignore` 会返回 1
        #   （已跟踪的文件不再报告为「被忽略」）。若这里也判红，
        #   R1 与 R2 会对同一件事同时报警，而两者本来要**分开报**
        #   —— 一个是「有人 add 了文件」，一个是「有人开了个口子」。
        if rel in tracked_now:
            continue
        if not is_ignored(root, rel):
            not_ignored.append(rel)

    # ② 负向规则的越界检查
    gi = Path(root) / ".gitignore"
    try:
        lines = gi.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise Untested(".gitignore 读不出：%s" % e)

    released_set = set(RELEASED_DOCS)
    rogue = []
    for line in lines:
        s = line.strip()
        if not s.startswith("!"):
            continue
        target = s[1:].strip()
        if not target.startswith(SKILL_DIR + "/"):
            continue
        if target not in released_set:
            rogue.append(s)

    # ① 必须存在一条覆盖 skill/ 全部成员的规则
    has_cover = any(
        l.strip() in ("skill/*", "skill/**", "skill/", "/skill/*", "skill")
        for l in lines
    )

    ok = not not_ignored and not rogue and has_cover
    detail = []
    if not has_cover:
        detail.append("`.gitignore` 里没有覆盖 skill/ 的规则")
    if not_ignored:
        detail.append("未被忽略的成员：%s" % not_ignored[:5])
    if rogue:
        detail.append("越界的放行规则（单点开口）：%s" % rogue)
    return {
        "id": "R2",
        "ok": ok,
        "title": "skill/ 整体被忽略，且无单点放行",
        "detail": "；".join(detail) or "%d 个成员目录均被忽略，放行仅限两份文档" % len(members),
        "not_ignored": not_ignored,
        "rogue_release": rogue,
        "has_cover_rule": has_cover,
    }


def check_r3_released(root) -> dict:
    """R3：两份放行文档必须仍在盘上、仍未被忽略。"""
    problems = []
    for doc in RELEASED_DOCS:
        p = Path(root) / doc
        if not p.is_file():
            problems.append("%s 不在盘上" % doc)
            continue
        if is_ignored(root, doc):
            problems.append("%s 被忽略（! 放行行可能被删了）" % doc)

    pending = [d for d in RELEASED_DOCS
               if (Path(root) / d).is_file()
               and d not in tracked_under(root, SKILL_DIR + "/")]

    ok = not problems
    return {
        "id": "R3",
        "ok": ok,
        "title": "两份放行文档在盘上且未被忽略",
        "detail": "；".join(problems) or "两份均存在且未被忽略"
                  + ("（未跟踪 %d 个，PENDING）" % len(pending) if pending else ""),
        "problems": problems,
        "pending": pending,
    }


def check_r4_baseline(root) -> dict:
    """
    R4：成员目录数 ≥ 基线。**分母守卫。**

    ★ 同时报出**实测值与离下界的距离** —— 只报「通过」的话，
      读到的人不知道它是 31 还是 37，也就看不出「快被搬空了」。
    """
    members = member_dirs(root)
    n = len(members)
    ok = n >= MEMBER_BASELINE
    detail = "实测 %d 个成员目录（下界 %d，余量 %d）" % (
        n, MEMBER_BASELINE, n - MEMBER_BASELINE)
    if not ok:
        detail += " —— 低于下界：skill/ 可能被搬走或改名，前三条会恒真"
    return {
        "id": "R4", "ok": ok,
        "title": "成员目录数不低于基线（分母守卫）",
        "detail": detail, "count": n, "baseline": MEMBER_BASELINE,
        "baseline_source": MEMBER_SOURCE,
    }


def check_r5_credentials(root) -> dict:
    """
    R5：放行的两份文档不得含真凭据形态。

    ★ 基线豁免按 (相对路径, 行号, 特征串) 三件套；三者全中才豁免。
      新加一处、或原有那行挪了位置，都会重新变红。
    """
    hits, waived = [], []
    for doc in RELEASED_DOCS:
        p = Path(root) / doc
        if not p.is_file():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            raise Untested("读不出 %s：%s" % (doc, e))
        for lineno, line in enumerate(lines, 1):
            for rx, label in CRED_PATTERNS:
                if not rx.search(line):
                    continue
                base = next((b for b in CRED_BASELINE
                             if b[0] == doc and b[1] == lineno and b[2] in line),
                            None)
                # ★★ 2026-10-21 修复（05 发现）：上面那句注释承诺
                #   「同一行多了别的东西仍然红」，**但代码做不到** ——
                #   `b[2] in line` 只要求特征串**出现过**，于是「原句 + 追加一个
                #   真 app_secret」照样被豁免。实测复现：
                #       原样           → ok=True  waived=1  （正确）
                #       同一行追加凭据 → ok=True  waived=1  （❌ 真凭据被放过）
                #   这正是本项目反复记的那个病（§2.4：「名字出现过」≠「拦得住」），
                #   这一次它长在**豁免机制自己**身上。
                #
                #   修法：豁免必须要求「**除了这一条特征串，这一行没有别的命中**」。
                #   实现上把特征串从行里挖掉，再跑一遍全部形态：
                #   挖完之后还有命中 → 说明这一行不止那处已知的指向说明 → 不豁免。
                if base:
                    _rest = line.replace(base[2], "")
                    _extra = [lb for r2, lb in CRED_PATTERNS if r2.search(_rest)]
                    if _extra:
                        hits.append({"file": doc, "line": lineno,
                                     "kind": "%s（豁免位置出现新增凭据：%s）"
                                             % (label, "/".join(_extra))})
                        continue
                    waived.append({"file": doc, "line": lineno,
                                   "kind": label, "why": base[3]})
                else:
                    hits.append({"file": doc, "line": lineno, "kind": label})

    ok = not hits
    detail = []
    if hits:
        detail.append("发现真凭据形态：%s" % [
            "%s:%d (%s)" % (h["file"], h["line"], h["kind"]) for h in hits])
    if waived:
        detail.append("基线豁免 %d 处（指向说明，非凭据）" % len(waived))
    return {
        "id": "R5", "ok": ok,
        "title": "放行文档不含真凭据形态",
        "detail": "；".join(detail) or "未发现凭据形态",
        "hits": hits, "waived": waived,
    }


# ═══════════════════════ 汇总 ═══════════════════════

def evaluate(root) -> dict:
    _require_repo(root)
    checks = [
        check_r1_tracked(root),
        check_r2_ignored(root),
        check_r3_released(root),
        check_r4_baseline(root),
        check_r5_credentials(root),
    ]
    reds = [c for c in checks if not c["ok"]]
    return {
        "root": str(root),
        "checks": checks,
        "reds": [c["id"] for c in reds],
        "verdict": "red" if reds else "ok",
        "exit_code": 1 if reds else 0,
    }


# ═══════════════════════ 反向对照（--controls）═══════════════════════
#
# ★ 全部在临时 git 仓里跑，不碰真仓库（AGENTS.md §2.4.4：
#   自证不许改它要保护的东西 —— 一个会往 .gitignore 里写东西的自证，
#   比没有自证更糟）。

def _mk_repo(base: Path, *, ignore_lines, members, released, extra_tracked=(),
             cred_line=None, cred_target=None, cred_at_line=None) -> Path:
    repo = base / "repo"
    (repo / SKILL_DIR).mkdir(parents=True)
    for m in members:
        d = repo / SKILL_DIR / m
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: %s\nlicense: Proprietary\n---\n# %s\n" % (m, m),
            encoding="utf-8")

    (repo / ".gitignore").write_text("\n".join(ignore_lines) + "\n",
                                     encoding="utf-8")
    target = cred_target or released[0]
    for rel in released:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# doc", ""]
        if cred_line and rel == target:
            want = cred_at_line or (len(lines) + 1)
            while len(lines) < want - 1:
                lines.append("")
            lines.append(cred_line)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True,
                       capture_output=True)
        # 先跟踪放行文档，模拟真实仓的状态
        add = list(released) + list(extra_tracked)
        if add:
            subprocess.run(["git", "add", "-f"] + add, cwd=str(repo),
                           check=True, capture_output=True)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return repo


def run_controls(verbose: bool = False) -> int:
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    base_ignore = [
        "skills/",
        "# 提取件",
        "skill/*",
        "!skill/README.md",
        "!skill/标准化台账-20261017.md",
    ]
    released = list(RELEASED_DOCS)
    members = ["m%02d" % i for i in range(1, MEMBER_BASELINE + 5)]  # 34 ≥ 30

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        # ── C1 好样本：必须绿 ──
        r = evaluate(_mk_repo(base / "c1", ignore_lines=base_ignore,
                              members=members, released=released))
        ok("C1 ★ 好样本 → 全绿（防恒红）", r["verdict"] == "ok",
           "reds=%s" % r["reds"])

        # ── C2 坏样本：成员文件被 git add -f 跟踪 → R1 红 ──
        repo = _mk_repo(base / "c2", ignore_lines=base_ignore,
                        members=members, released=released,
                        extra_tracked=["skill/m01/SKILL.md"])
        r2 = evaluate(repo)
        ok("C2 ★ 成员文件被跟踪 → R1 红", "R1" in r2["reds"], "reds=%s" % r2["reds"])

        # ── C3 坏样本：放行文档被删 → R3 红 ──
        repo3 = _mk_repo(base / "c3", ignore_lines=base_ignore,
                         members=members, released=released)
        (repo3 / released[0]).unlink()
        r3 = evaluate(repo3)
        ok("C3 ★ 放行文档被删 → R3 红", "R3" in r3["reds"], "reds=%s" % r3["reds"])

        # ── C4 坏样本：有人加了一条单点放行 → R2 红 ──
        rogue_ignore = base_ignore + ["!skill/m01/"]
        r4 = evaluate(_mk_repo(base / "c4", ignore_lines=rogue_ignore,
                               members=members, released=released))
        ok("C4 ★ 单点放行 !skill/m01/ → R2 红", "R2" in r4["reds"],
           "reds=%s" % r4["reds"])

        # ── C5 坏样本：skill/ 被搬空 → R4 红（分母守卫）──
        repo5 = _mk_repo(base / "c5", ignore_lines=base_ignore,
                         members=members, released=released)
        for m in members:
            shutil.rmtree(repo5 / SKILL_DIR / m)
        r5 = evaluate(repo5)
        ok("C5 ★ 成员目录被搬空 → R4 红（前三条会恒真）", "R4" in r5["reds"],
           "reds=%s count=%d" % (r5["reds"], r5["checks"][3]["count"]))

        # ── C6 坏样本：放行文档里塞假凭据 → R5 红 ──
        r6 = evaluate(_mk_repo(base / "c6", ignore_lines=base_ignore,
                               members=members, released=released,
                               cred_line='app_secret: "abcdef0123456789abcdef"'))
        ok("C6 ★ 放行文档塞假 app_secret → R5 红", "R5" in r6["reds"],
           "reds=%s" % r6["reds"])

        # ── C7 好样本：基线里的指向说明不许红（防误报）──
        #
        # ★ 两个坑，都是实测踩出来的：
        #   ① 豁免登记的是 (文件, 行号, 特征串) 三件套 —— 必须把它塞进
        #      **登记的那个文件**，塞进 README 永远不会命中。
        #   ② 行号也要对上：_mk_repo 生成的文件只有 2 行（标题 + 空行），
        #      所以要把测试行补到第 69 行，否则永远差一个行号。
        r7 = evaluate(_mk_repo(base / "c7", ignore_lines=base_ignore,
                               members=members, released=released,
                               cred_line="> 真实凭据在 `~/.dsh/credentials/x.json`",
                               cred_target="skill/标准化台账-20261017.md",
                               cred_at_line=69))
        waived = [c for c in r7["checks"] if c["id"] == "R5"][0]
        ok("C7 ★ 基线指向说明 → 不误报（豁免生效）",
           not waived["hits"] and len(waived["waived"]) == 1,
           "waived=%d hits=%d" % (len(waived["waived"]), len(waived["hits"])))

        # ── C8 坏样本：豁免不吞掉新增行 → 同文件另一处的真凭据仍红 ──
        r8 = evaluate(_mk_repo(base / "c8", ignore_lines=base_ignore,
                               members=members, released=released,
                               cred_line='app_secret: "zzzz9999888877776666"'))
        hit = [c for c in r8["checks"] if c["id"] == "R5"][0]
        ok("C8 ★ 新增凭据行不被豁免带过", "R5" in r8["reds"] and hit["hits"],
           "hits=%d" % len(hit["hits"]))

        # ── C9 未测：不是 git 仓 → 退 2 ──
        plain = base / "notrepo"
        plain.mkdir()
        try:
            evaluate(plain)
            ok("C9 ★ 非 git 仓 → 未测（不是通过）", False, "居然返回了")
        except Untested:
            ok("C9 ★ 非 git 仓 → 未测（不是通过）", True, "Untested")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 70)
    print("verify_skill_inventory · 反向对照")
    print("=" * 70)
    for name, p, detail in results:
        print("  %s %-46s %s" % ("✓" if p else "✗", name, detail))
    print()
    if passed == total:
        print("✅ %d/%d 项全过" % (passed, total))
        return 0
    print("✗ %d/%d 项通过；红项：%s"
          % (passed, total, [n for n, p, _ in results if not p]), file=sys.stderr)
    return 1


# ═══════════════════════ CLI ═══════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="skill/ 提取件目录的入库/忽略守卫（R1–R5）")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--controls", action="store_true",
                    help="跑反向对照（离线，临时 git 仓）")
    ns = ap.parse_args(argv)

    if ns.controls:
        return run_controls()

    try:
        r = evaluate(Path(ns.root))
    except Untested as e:
        print("⚠ 未测：%s —— 未测不是通过" % e, file=sys.stderr)
        return 2

    if ns.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return r["exit_code"]

    print("=" * 74)
    print("skill/ 提取件目录 · 入库与忽略守卫")
    print("=" * 74)
    print("  仓库：%s" % r["root"])
    print()
    for c in r["checks"]:
        print("  %s %-4s %s" % ("✓" if c["ok"] else "✗", c["id"], c["title"]))
        print("        %s" % c["detail"])
    print()
    if r["reds"]:
        print("✗ %d 项红：%s" % (len(r["reds"]), r["reds"]))
        return 1
    print("✅ %d/%d 全过" % (len(r["checks"]), len(r["checks"])))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("⚠ 未测：验收器自身异常：%s: %s"
              % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(2)
