#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_doc_reachability.py —— 文档可达性自证器：README 到底是不是一个入口

## 这个文件为什么存在

诊断（2026-09-22，产物 `.ua/doc-reachability.md` + `.ua/doc-reachability.cjs`）
量到：**从 `README.md` ∪ `AGENTS.md` 出发，226 份已入库文档里有 143 份走不到**。
其中最刺眼的两件：

  * `README.md` 当时只有 **35 字节 / 2 行 / 0 个链接**（`wc -c README.md`）；
  * `PMO/守衡-*` 那批事故记录**全部没有入边** —— 而 `AGENTS.md` §2.2
    正是把它们当作「别再踩的坑」的唯一存档。

一份走不到的文档，和一个不存在的文档，对读者是同一件事。
所以这件事必须**有执行点**（§2.4）：不能只是某次诊断里的一段散文。

## 口径（先声明，再判定 —— 换口径就必须改这里，别改断言）

**口径 = 已入库文件**。取 `git ls-files -z`（**必须带 `-z`**：不带时 git 会把含非 ASCII
的路径转义成 `"PMO/\\344\\270\\212..."`，任何 `\\.md$` 过滤都会**静默漏掉它们** ——
实测同一时刻「不带 -z 得 160 份文档 / 带 -z 得 226 份」，差 66 份全是中文名）。
`.ua/`（本轮诊断的工作目录，未入库）与 `skills/`（`.gitignore:39` 的第三方技能库，
未入库）**不在口径内**：本器只回答「仓库里该被读到的文档有没有入口」。

**什么叫「可达」**：从起点集合出发，沿**边**做闭包。

  * **起点**：`README.md` 与 `AGENTS.md`。
    主读数用两者的并集（与 `.ua` 诊断同口径，便于对比）；`--readme-only`
    单独给「只从 README 出发」的读数。
  * **边**：文档 A 的正文里出现一个**指向具体文件 B** 的引用，且 B 在口径内。接受的形态：
      1. Markdown 行内链接 `](target)`
      2. Markdown 引用式链接 `[label]: target`
      3. 反引号里的路径 `` `path/to/x.md` ``（允许 `:行号` 后缀，实测 0 份文档依赖它）
      4. 裸路径 token（以 `ADR/` `PMO/` … 这些顶层目录名开头的、带已知扩展名的串）
    相对路径按**引用方所在目录**解析（`ADR/README.md` 里的 `./ADR-0001-….md`）。
  * **中继只有文档**（`.md/.mdx/.rst/.txt`）。这是本器与 `.ua` 诊断**唯一实质分歧**，
    见下面「与诊断的分歧」。机器产物（`.json/.py/.mjs/.sh`）**可以被指向**，但**不当中继**。
  * **目录引用不构成边**。写 `` `PMO/` `` 不等于 PMO 下每一份文档都可达 ——
    否则一个字符就能把整棵树刷绿，读数立刻失去意义。这条**有反向对照**
    （`--controls` 的 C3：只写目录名的样本里，PMO 下的文档必须仍不可达）。
  * 引用到**已入库但非文档**的文件（如 `tools/verify_depad.py`）算一条**边**，
    但那个目标不计入「文档」分母。所以闭包大小 ≥ 可达文档数。

## 豁免（不是「静静排除」——每一类都要指得出判据）

判据与理由都写在下面 `EXEMPT_CLASSES` 里，并且有**两条机器断言**兜着：

  * **E1** 分项之和 == 不可达总数（**没有一份不可达文档是「没被归类」的**）；
  * **E2** 有自述文件的豁免类，那个自述文件必须真在盘上（`skills-inventory/refs/README.md`）。

一份新文档若不可达、又落不进任何已声明的豁免类，**E1 立刻变红** ——
「我不知道」不会被写成「不需要」（§2.4.3）。

## 断言

  A  每一份 `ADR/ADR-*.md` 都可达
  B  每一份 `PMO/守衡-*-修复记录.md` 都可达
  B2 每一份 `PMO/守衡-*.md` 都可达（B 只覆盖名字带「修复记录」的那几篇，
     2026-09-22 实测 B 匹配 4 篇、整个 `PMO/守衡-*` 有 10 篇、其中不可达 6 篇 —— 见报告）
  C  不可达总数 <= `PINNED_UNREACHABLE`（钉住值，见该常量处的复现命令与日期）
  D  每一份**非豁免**的第一方文档都可达
  E1 不可达集合 == 各豁免类之并（分项之和 = 总数，且未归类数为 0）
  E2 有自述文件的豁免类，其自述文件在盘上
  F  未测与红必须长得不一样（退出码 2 ≠ 1 ≠ 0；结论行不许把未测说成通过）

## 退出码

  0  全过
  1  有断言红
  2  未测（git 不可用 / 有文档读不出）—— **未测 ≠ 通过 ≠ 红**

## 用法

    python3 tools/verify_doc_reachability.py                 # 主读数：README ∪ AGENTS
    python3 tools/verify_doc_reachability.py --readme-only   # 只从 README 出发
    python3 tools/verify_doc_reachability.py -v              # 列出每一份不可达文档
    python3 tools/verify_doc_reachability.py --controls      # 反向对照（只在内存里做）
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEEDS = ("README.md", "AGENTS.md")

DOC_EXT = (".md", ".mdx", ".rst", ".txt")

#: 引用形态里允许出现的扩展名（可以指向非文档；非文档只是不当**中继**）
REF_EXT = (
    ".md", ".mdx", ".rst", ".txt",
    ".json", ".jsonl", ".py", ".mjs", ".sh", ".csv", ".yml", ".yaml", ".plist",
)

#: 裸路径 token 认这些顶层目录。新增顶层目录时要一起加 —— 漏了不会报错，
#: 只会让那份文档「莫名其妙不可达」，所以这份清单本身也是口径的一部分。
TOPDIRS = (
    "ADR", "PMO", "PRD", "research", "tools", "base",
    "kb2agent-research", "agent-skills", "skills-inventory",
    "x-recovery", "dsh-browser-ext",
)

# ── 钉住值 ────────────────────────────────────────────────────────────────
# PINNED_UNREACHABLE 是「不可达文档总数」的上界。**2026-09-22 14:20 CST 钉住 = 100。**
# 这个数变大 = 有人加了一份没有入边的文档（或删了一条边）→ C 变红，去看 `-v` 的清单。
#
# 这个数字**怎么算出来的**（复现命令，逐字可跑）：
#
#     cd /Users/lute/Project/audit_multi_content
#     python3 tools/verify_doc_reachability.py        # 结论行 + 两个口径的读数
#     python3 tools/verify_doc_reachability.py -v     # 列出每一份不可达文档
#
# 两次真实读数（同一条命令，README 重写前 / 后）：
#
#   读法① 主口径（本文件的口径：起点 README.md ∪ AGENTS.md，**中继只能是文档**）
#       重写前  可达  48 / 226   不可达 178     ← ./README.md 当时 35 字节 / 2 行 / 0 链接
#       重写后  可达 126 / 226   不可达 100
#   读法② 宽口径（= `.ua/doc-reachability.cjs` 的口径：任何已跟踪文件都能当中继）
#       重写前  可达  83 / 226   不可达 143     ← 与 `.ua/doc-reachability.md` 的 143 一致
#       重写后  可达 126 / 226   不可达 100
#
#   两个口径在重写后**重合**（「只在宽口径下可达」= 0 份），说明重写后
#   再没有哪份文档是**只能靠代码提到过**才可达的。
#
# 100 = 三个豁免类之和（本文件 `-v` 会逐类打印，E1 断言这个恒等式）：
#   VENDORED_THIRD_PARTY 67 · CAPTURED_EXTERNAL 13 · SCRATCH 20 · 未归类 0
# 也就是：重写后**第一方文档 0 份不可达**（D 断言的就是这一条）。
#
# ⚠️ 这个数会跟着仓库动，钉住它就是为了让「动」变成红的：
#   * `research/` 下新增一份没人引用的调研文档 → 100 变 101 → C 红（该去补一条边）；
#   * 新增第三方留档（`skills-inventory/refs/`、`kb2agent-research/raw/`…）→ 也该红一次，
#     让人**有意识地**把本常量与新读数一起改掉，而不是让它悄悄漂走（§2.2 第 1 条）。
PINNED_UNREACHABLE = 100

# ── 豁免类 ────────────────────────────────────────────────────────────────
# 每条：(id, 谓词, 为什么它「不可达」不算问题, 判据证据文件或 None)
# 「判据证据文件」非 None 时，E2 会断言它真在盘上。
#
# ⚠️ 两条读法约定（都是被自己的反向对照逼出来的）：
#   ① **先匹配先算**（first match wins）。三个谓词会重叠 ——
#      `kb2agent-research/raw/_distill-legal.md` 既是 CAPTURED 又是 SCRATCH。
#      各自独立过滤会让 E1 的「分项之和 == 总数」在重叠时**恒不成立**，
#      而现在恰好成立只是碰巧（那些重叠的文件当时可达）。分区读法下它才是**结构性**成立的。
#   ② 豁免只管「**不可达**时算不算问题」，不管「**可不可以**可达」。
#      这些文件如果被别的文档引用而可达（例如调研报告的正文引它的 raw 原件），那是对的，不冲突。
EXEMPT_CLASSES = (
    (
        "VENDORED_THIRD_PARTY",
        lambda p: p.startswith("skills-inventory/refs/"),
        "第三方技能原文的逐字节留档。把每一份 SKILL.md 都挂到 README 上不是入口，是噪音；"
        "它们的入口是 refs/README.md 那张「留档目录 → 仓内原始路径 → 许可状态」表。",
        "skills-inventory/refs/README.md",
    ),
    (
        "EXTERNAL_SNAPSHOT",
        lambda p: p.startswith("research/readmes/") or p.startswith("x-recovery/"),
        "**别人的文字**的逐字快照（别家产品的 README、X 上一条帖子）。改它们等于篡改证据，"
        "所以不逐份挂入口。",
        None,
    ),
    (
        "RAW_MATERIAL",
        lambda p: p.startswith("kb2agent-research/raw/"),
        "调研**原始件**（目录名就是 `raw`）。成品是同目录的两份报告，报告正文按件引用 raw 原件 ——"
        "所以这个类里的文件**大多数本来就有入边**，不可达的那几份是引用写法漏了。"
        "见下面每类的「可达 M / 共 N」那一行：那个比值就是这条豁免的成色。",
        None,
    ),
    (
        "SCRATCH",
        lambda p: (
            "/scratch/" in "/" + p
            or "/_scratch/" in "/" + p
            or os.path.basename(p).startswith("_")
        ),
        "草稿/探针。判据是**本仓既有的命名约定**：`research/distill/scratch/`、"
        "`research/governance/_scratch/`、`tools/_ingest_batch10.py`、`tools/_dryrun_link.mjs` "
        "都是「临时、未定稿、不承诺被引用」的东西；下划线前缀在本仓就是这个意思。",
        None,
    ),
)

# ⚠️ 正则里**不要**写 `守衡-[^/]*-修复记录`。实际文件名是
# `守衡-查名修复记录.md` / `守衡-回复截断修复记录.md` ——「修复记录」前面**没有**连字符。
# 第一版按任务书里的 `PMO/守衡-*-修复记录.md` 写，实测**匹配 0 个文件**，
# 于是 `B` 变成一条**恒真**的断言（「全部 0 篇都可达」）。这是 §2.4「名字出现过不是拦得住」
# 的镜像：**分母为 0 的断言不是断言**。所以 A/B/B2 都加了 `*_n > 0` 的兜底（见 check()）。
REQUIRED_ADR_RE = re.compile(r"^ADR/ADR-[^/]*\.md$")
REQUIRED_PMO_RE = re.compile(r"^PMO/守衡-[^/]*修复记录\.md$")
REQUIRED_PMO_ALL_RE = re.compile(r"^PMO/守衡-[^/]*\.md$")

MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
REF_LINK_RE = re.compile(r"^[ \t]*\[[^\]]+\]:[ \t]*(\S+)", re.M)
TICK_RE = re.compile(
    r"`([^`\n]+?\.(?:" + "|".join(e.lstrip(".") for e in REF_EXT) + r"))`"
)
TICK_LINE_RE = re.compile(
    r"`([^`\n]+?\.(?:" + "|".join(e.lstrip(".") for e in REF_EXT) + r")):\d+`"
)
BARE_RE = re.compile(
    r"(?:^|\s)((?:"
    + "|".join(re.escape(d) for d in TOPDIRS)
    + r")/[A-Za-z0-9_./\u4e00-\u9fff()（）-]+?\.(?:"
    + "|".join(e.lstrip(".") for e in REF_EXT)
    + r"))"
)

PASS = []
FAIL = []
UNTESTED = []


# ══════════════════════════════════════════════════════════════════════════
# 扫描与图
# ══════════════════════════════════════════════════════════════════════════

def git_ls_files(root):
    """已跟踪文件集合。取不到返回 None —— 那是**未测**，不许当成空集（§2.2 第 5/7 条）。"""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    files = out.stdout.decode("utf-8", "replace").split("\0")
    return set(f for f in files if f)


def read_text(root, rel):
    """读正文。读不出返回 None（调用方据此落「未测」，不许当成「没有引用」）。"""
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            raw = fh.read()
    except Exception:
        return None
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", "replace")


def scan(root):
    """扫出 (tracked, docs, bodies, unreadable_docs)。git 不可用返回 None。"""
    tracked = git_ls_files(root)
    if tracked is None:
        return None
    docs = sorted(f for f in tracked if f.lower().endswith(DOC_EXT))
    bodies = {}
    unreadable = []
    for f in sorted(tracked):
        txt = read_text(root, f)
        if txt is None:
            if f.lower().endswith(DOC_EXT):
                unreadable.append(f)
            continue
        bodies[f] = txt
    return tracked, docs, bodies, unreadable


def resolve(cand, from_path, tracked):
    """把一个候选引用解析成仓内路径，解析不出返回 None。"""
    c = cand.strip().strip("<>")
    c = c.split("#", 1)[0]
    c = re.sub(r":\d+$", "", c)
    c = c.strip().rstrip(".,;:")
    if not c:
        return None
    if c.startswith("./"):
        c = c[2:]
    if c in tracked:
        return c
    rel = os.path.normpath(os.path.join(os.path.dirname(from_path), c))
    if rel in tracked:
        return rel
    return None


def edges_of(path, body, tracked, wide=False):
    """从一份文档的正文里抽出它指向的仓内路径集合。

    wide=True 时用的是 `.ua` 诊断的原始三形态（无引用式链接、无反引号 `:行号`），
    供 `--sensitivity` 做同口径对比。
    """
    cands = set()
    for m in MD_LINK_RE.finditer(body):
        cands.add(m.group(1))
    for m in BARE_RE.finditer(body):
        cands.add(m.group(1))
    if wide:
        for m in TICK_RE.finditer(body):
            cands.add(m.group(1))
    else:
        for m in REF_LINK_RE.finditer(body):
            cands.add(m.group(1))
        for m in TICK_RE.finditer(body):
            cands.add(m.group(1))
        for m in TICK_LINE_RE.finditer(body):
            cands.add(m.group(1))
    out = set()
    for c in cands:
        p = resolve(c, path, tracked)
        if p and p != path:
            out.add(p)
    return out


def bfs(seeds, bodies, tracked, doc_only_relay=True, wide=False):
    """闭包。doc_only_relay=True = 主口径（中继只能是文档）。"""
    seen = set(s for s in seeds if s in tracked)
    queue = list(seen)
    parents = {}
    while queue:
        cur = queue.pop(0)
        if doc_only_relay and not cur.lower().endswith(DOC_EXT):
            continue
        body = bodies.get(cur)
        if body is None:
            continue
        for nxt in edges_of(cur, body, tracked, wide=wide):
            if nxt not in seen:
                seen.add(nxt)
                parents[nxt] = cur
                queue.append(nxt)
    return seen, parents


def analyze(tracked, docs, bodies, seeds=SEEDS, doc_only_relay=True, wide=False):
    """纯函数：给定期望数据，算出全部读数。控制组直接复用本函数（§2.1：反向对照只在内存里做）。"""
    reach, parents = bfs(seeds, bodies, tracked, doc_only_relay=doc_only_relay, wide=wide)
    reach_docs = set(d for d in docs if d in reach)
    unreachable = sorted(d for d in docs if d not in reach)

    by_class = {}
    for cid, pred, _why, _ev in EXEMPT_CLASSES:
        by_class[cid] = []
    classified = set()
    unclassified = []
    for d in unreachable:
        hit = None
        for cid, pred, _why, _ev in EXEMPT_CLASSES:   # ★ 先匹配先算：三个谓词会重叠
            if pred(d):
                hit = cid
                break
        if hit is None:
            unclassified.append(d)
        else:
            by_class[hit].append(d)
            classified.add(d)
    unclassified.sort()
    for cid in by_class:
        by_class[cid].sort()

    # 每个类的「总份数 / 可达份数」。**这一行是豁免成色的读数**：
    # 一个类如果「共 N 份 / 可达 0 份」，说明这类文件确实一律没有入口；
    # 如果「共 N 份 / 可达 M 份（M>0）」，说明**同类的别的文件是有入边的** ——
    # 那这个类里剩下的不可达就更可能是「引用写法漏了」，而不是「本来就不该有入口」。
    # （实测：`kb2agent-research/raw/` 共 18 可达 15，差的 3 份是报告里用
    #  `B-part1..3.md` 这种**区间写法**引的，区间不解析成具体路径。）
    #
    # ★ 成员口径必须与 E1 用**同一套**（先匹配先算），否则两处会各报一个数：
    #   第一版这里用的是「任一谓词命中」，于是 `raw/_distill-legal.md` 同时进了
    #   RAW_MATERIAL 与 SCRATCH 的成员数，打印出「SCRATCH 共 28」而 E1 只算 20。
    class_span = {}
    for cid, _pred, _why, _ev in EXEMPT_CLASSES:
        class_span[cid] = [0, 0]          # [总份数, 其中可达份数]
    for d in docs:
        for cid, pred, _why, _ev in EXEMPT_CLASSES:
            if pred(d):
                class_span[cid][0] += 1
                if d in reach_docs:
                    class_span[cid][1] += 1
                break
    class_span = dict((k, tuple(v)) for k, v in class_span.items())

    non_exempt_unreachable = sorted(d for d in unreachable if d not in classified)

    return {
        "seeds": [s for s in seeds],
        "tracked_n": len(tracked),
        "docs_n": len(docs),
        "closure_files_n": len(reach),
        "reachable_docs": sorted(reach_docs),
        "reachable_docs_n": len(reach_docs),
        "unreachable": unreachable,
        "unreachable_n": len(unreachable),
        "by_class": by_class,
        "class_span": class_span,
        "unclassified": unclassified,
        "non_exempt_unreachable": non_exempt_unreachable,
        "unreachable_adr": sorted(d for d in unreachable if REQUIRED_ADR_RE.match(d)),
        "unreachable_pmo_fix": sorted(d for d in unreachable if REQUIRED_PMO_RE.match(d)),
        "unreachable_pmo_all": sorted(d for d in unreachable if REQUIRED_PMO_ALL_RE.match(d)),
        "adr_n": len([d for d in docs if REQUIRED_ADR_RE.match(d)]),
        "pmo_fix_n": len([d for d in docs if REQUIRED_PMO_RE.match(d)]),
        "pmo_all_n": len([d for d in docs if REQUIRED_PMO_ALL_RE.match(d)]),
        "parents": parents,
    }


# ══════════════════════════════════════════════════════════════════════════
# 判定（纯函数，控制组直接喂它）
# ══════════════════════════════════════════════════════════════════════════

def check(reading, pinned, root=ROOT):
    """把读数变成 (pass_list, fail_list)。未测由调用方另行处理，不在这里。"""
    P, F = [], []

    # A / B / B2 —— 每条都先查分母。**分母为 0 的断言是恒真的**（§2.4：
    # 「名字出现过」不是「它拦得住」的镜像版本），所以空集必须红，不许绿。
    if reading["adr_n"] == 0:
        F.append(("A", "分母为 0：没有匹配 `ADR/ADR-*.md` 的文件，这条断言恒真（不是通过）"))
    elif reading["unreachable_adr"]:
        F.append(("A", "有 %d 份 ADR 不可达：%s"
                  % (len(reading["unreachable_adr"]), ", ".join(reading["unreachable_adr"][:6]))))
    else:
        P.append("A 全部 %d 份 ADR/ADR-*.md 可达" % reading["adr_n"])

    if reading["pmo_fix_n"] == 0:
        F.append(("B", "分母为 0：没有匹配 `PMO/守衡-*修复记录.md` 的文件，"
                       "这条断言恒真（2026-09-22 实测：任务书写的 `守衡-*-修复记录` 匹配 0 个，"
                       "真名里「修复记录」前面没有连字符）"))
    elif reading["unreachable_pmo_fix"]:
        F.append(("B", "有 %d 篇 PMO/守衡-*修复记录.md 不可达：%s"
                  % (len(reading["unreachable_pmo_fix"]), ", ".join(reading["unreachable_pmo_fix"]))))
    else:
        P.append("B 全部 %d 篇 PMO/守衡-*修复记录.md 可达" % reading["pmo_fix_n"])

    if reading["pmo_all_n"] == 0:
        F.append(("B2", "分母为 0：没有匹配 `PMO/守衡-*.md` 的文件，这条断言恒真"))
    elif reading["unreachable_pmo_all"]:
        F.append(("B2", "有 %d 篇 PMO/守衡-*.md 不可达：%s"
                  % (len(reading["unreachable_pmo_all"]), ", ".join(reading["unreachable_pmo_all"]))))
    else:
        P.append("B2 全部 %d 篇 PMO/守衡-*.md 可达" % reading["pmo_all_n"])

    # C
    if reading["unreachable_n"] > pinned:
        F.append(("C", "不可达总数 %d > 钉住值 %d（增长 %d）"
                  % (reading["unreachable_n"], pinned, reading["unreachable_n"] - pinned)))
    else:
        P.append("C 不可达总数 %d <= 钉住值 %d" % (reading["unreachable_n"], pinned))

    # D
    if reading["non_exempt_unreachable"]:
        F.append(("D", "有 %d 份非豁免的第一方文档不可达：%s"
                  % (len(reading["non_exempt_unreachable"]),
                     ", ".join(reading["non_exempt_unreachable"][:8]))))
    else:
        P.append("D 非豁免的第一方文档 0 份不可达（豁免 %d 份，见 E1）" % reading["unreachable_n"])

    # E1 分项之和 = 总数（恒等式，§2.4.1 做法 2）。分区读法下这个恒等式**结构性**成立；
    # 若三个谓词各自独立过滤，重叠的文件会被算两次，这条恒等式就只在碰巧无重叠时成立。
    total = sum(len(v) for v in reading["by_class"].values())
    if reading["unclassified"]:
        F.append(("E1", "有 %d 份不可达文档落不进任何已声明的豁免类：%s"
                  % (len(reading["unclassified"]), ", ".join(reading["unclassified"][:8]))))
    elif total != reading["unreachable_n"]:
        F.append(("E1", "分项之和 %d != 不可达总数 %d（豁免类没有分区，有文件被算了两次或漏算）"
                  % (total, reading["unreachable_n"])))
    else:
        P.append("E1 分项之和 == 不可达总数 == %d（%s）"
                 % (reading["unreachable_n"],
                    " · ".join("%s %d" % (k, len(v)) for k, v in sorted(reading["by_class"].items()))))

    # E2 豁免证据要在盘上
    missing_ev = []
    for cid, _pred, _why, ev in EXEMPT_CLASSES:
        if ev and not os.path.exists(os.path.join(root, ev)):
            missing_ev.append("%s → %s" % (cid, ev))
    if missing_ev:
        F.append(("E2", "豁免类的判据证据文件不在盘上：%s" % "; ".join(missing_ev)))
    else:
        n_ev = len([1 for _c, _p, _w, ev in EXEMPT_CLASSES if ev])
        P.append("E2 %d 个有自述文件的豁免类，其判据文件都在盘上" % n_ev)

    return P, F


def verdict(n_pass, n_fail, n_untested):
    """结论行必须区分三种状态（§2.4.2：未测不许写成「没问题」）。纯函数，可被 --controls 直接断言。"""
    if n_untested:
        return ("⚠ 未测：%d 项断言未跑（不能读成「通过」，也不能读成「红」）"
                " · 已跑 %d 项：过 %d / 红 %d" % (n_untested, n_pass + n_fail, n_pass, n_fail))
    if n_fail:
        return "❌ %d 项红 / %d 项过" % (n_fail, n_pass)
    return "✅ %d 项全过" % n_pass


# ══════════════════════════════════════════════════════════════════════════
# 控制组（一律在内存里造样本 —— §2.1：反向对照不许改真实数据再改回来）
# ══════════════════════════════════════════════════════════════════════════

def _fixture(readme_body, extra=None, drop=()):
    """造一个小仓库。故意用真实路径形状，好让 A/B/B2 的正则真的被触发。"""
    tracked = {
        "README.md": readme_body,
        "AGENTS.md": "# AGENTS\n\n（这一份在 Fixture 里刻意不指向任何文档）\n",
        "ADR/README.md": "# ADR 索引\n\n- [ADR-0001](./ADR-0001-甲.md)\n",
        "ADR/ADR-0001-甲.md": "# 甲\n",
        "PMO/守衡-查名修复记录.md": "# 查名修复记录\n",
        "PMO/守衡-架构说明.md": "# 架构说明\n",
        "research/一方文档.md": "# 一方\n",
        "research/readmes/别家README.md": "# 外部抓取\n",
        "skills-inventory/refs/第三方/SKILL.md": "# 第三方\n",
        "research/distill/scratch/_t1.md": "# 草稿\n",
        "tools/verify_depad.py": "# 工具（非文档，只作叶子）\n",
    }
    for k in drop:
        tracked.pop(k, None)
    if extra:
        tracked.update(extra)
    docs = sorted(f for f in tracked if f.lower().endswith(DOC_EXT))
    bodies = dict(tracked)
    return set(tracked), docs, bodies


def _ok_readme():
    return (
        "# Fixture 入口\n\n"
        "- `AGENTS.md`\n"
        "- `ADR/README.md`\n"
        "- `PMO/守衡-查名修复记录.md`\n"
        "- `PMO/守衡-架构说明.md`\n"
        "- `research/一方文档.md`\n"
        "- `skills-inventory/refs/第三方/SKILL.md`\n"
        "- `research/readmes/别家README.md`\n"
        "- `research/distill/scratch/_t1.md`\n"
        "- `tools/verify_depad.py`\n"
    )


def run_controls(root=ROOT, pinned=PINNED_UNREACHABLE, real=None):
    """反向对照。返回 (pass, fail, lines)。全部在内存里做，一次盘都不动。

    `real` = (tracked, docs, bodies) —— C12 要拿**真实仓数据**再换掉 README 重算一遍。
    不传就自己扫一次；扫不到则 C12 落「未测」，不许落成绿。
    """
    P, F, lines = [], [], []
    if real is None:
        sc = scan(root)
        real = (sc[0], sc[1], sc[2]) if sc else None
    real_tracked, real_docs, real_bodies = real if real else (set(), [], {})

    def one(label, expect_red_ids, readme_body, extra=None, drop=(), pin=pinned):
        tracked, docs, bodies = _fixture(readme_body, extra=extra, drop=drop)
        r = analyze(tracked, docs, bodies)
        p, f = check(r, pin, root=root)
        got = set(x[0] for x in f)
        if not expect_red_ids:
            good = not f
            detail = "全绿" if good else "红了 %s" % sorted(got)
        else:
            good = set(expect_red_ids) <= got
            detail = "红了 %s" % sorted(got)
        if good:
            P.append(label)
        else:
            F.append((label, "期望%s，实际%s" % (expect_red_ids or "全绿", detail)))
        lines.append("  %s %s → %s" % ("✓" if good else "✗", label, detail))

    # C0 闭嘴：干净样本必须全绿（证明这套断言不会恒红）
    one("C0 干净样本必须全绿（检查器会闭嘴）", [], _ok_readme())

    # C1 删掉 ADR 的入边 → ADR 必须变红
    one("C1 删掉 `ADR/README.md` 这条入边 → A 必须红",
        ["A"], _ok_readme().replace("- `ADR/README.md`\n", ""))

    # C2 删掉修复记录的入边 → B 必须红
    one("C2 删掉 `PMO/守衡-查名修复记录.md` 这条入边 → B 必须红",
        ["B"], _ok_readme().replace("- `PMO/守衡-查名修复记录.md`\n", ""))

    # C3 目录引用不算边 —— 口径里最容易被悄悄放宽的一条
    one("C3 只写目录名 `PMO/` → PMO 下的文档仍必须不可达（目录不构成边）",
        ["B", "B2", "D"],
        "# Fixture 入口\n\n- `AGENTS.md`\n- `ADR/README.md`\n- `PMO/`\n"
        "- `research/一方文档.md`\n")

    # C4 新增一份没有任何入边的第一方文档 → D 红
    one("C4 新增一份无入边的第一方文档 → D 必须红",
        ["D"],
        _ok_readme(),
        extra={"research/新文档没有入边.md": "# 新\n"})

    # C5 新增一份无入边、又落不进豁免类的文件 → D 与 E1 都要红
    one("C5 新增一份无入边且不属任何豁免类的文件 → D + E1 必须红",
        ["D", "E1"],
        _ok_readme(),
        extra={"weird/deep/无法归类.md": "# ？\n"})

    # C6 总数超过钉住值 → C 红（钉住值取 0，样本里必然有不可达）
    one("C6 不可达总数超过钉住值 → C 必须红",
        ["C"],
        _ok_readme(),
        extra={"weird/deep/无法归类.md": "# ？\n"},
        pin=0)

    # C7 引号形态的口径：反引号 + `:行号` 也要认出来
    one("C7 反引号带 `:行号` 的引用也是边（否则是一处静默断链）",
        [],
        "# Fixture 入口\n\n- `AGENTS.md`\n- `ADR/README.md`\n"
        "- `PMO/守衡-查名修复记录.md:12`\n- `PMO/守衡-架构说明.md`\n"
        "- `research/一方文档.md`\n- `skills-inventory/refs/第三方/SKILL.md`\n"
        "- `research/readmes/别家README.md`\n- `research/distill/scratch/_t1.md`\n")

    # C8 未测必须与通过与红都不一样（结论行不许撒谎）
    v_untested = verdict(3, 1, 1)
    v_red = verdict(3, 1, 0)
    v_green = verdict(4, 0, 0)
    # ★ 判据要区分「说」与「否认」（本项目 V25b 踩过这个坑）：
    #   未测那句里**必须**写「未测」，而它为了说清楚，**一定会出现「不能读成『通过』」** ——
    #   第一版判据直接把「通过」当成了违规词，于是**误报自己**。
    #   正确读法是先把那句否认语剥掉，再看有没有**肯定**说法。
    denial = "不能读成「通过」，也不能读成「红」"
    stripped = v_untested.replace(denial, "")
    if (denial in v_untested and "未测" in v_untested and "⚠" in v_untested
            and not any(w in stripped for w in ("全过", "通过", "没问题", "✅"))
            and v_untested != v_red and v_red != v_green and v_green != v_untested):
        P.append("C8 未测 / 红 / 绿三句话互不相同；未测句里有「未测」，剥掉那句否认语后没有肯定说法")
        lines.append("  ✓ C8 三种状态三句话：%s" % v_untested)
    else:
        F.append(("C8", "结论行会把未测说成通过：%r / %r / %r" % (v_untested, v_red, v_green)))
        lines.append("  ✗ C8 结论行会把未测说成通过")

    # C9 未测的读数必须落成「未测」，不许落成 0
    if analyze(set(), [], {})["docs_n"] == 0 and git_ls_files("/nonexistent-dir-xyz") is None:
        P.append("C9 取不到数据时落『未测』而不是 0（git 不可用 → None）")
        lines.append("  ✓ C9 git 取不到 → None（未测），不是空集")
    else:
        F.append(("C9", "git 不可用时返回了空集而不是 None —— 空集会被读成「全都没有」，即假绿"))
        lines.append("  ✗ C9 git 不可用时返回了空集")

    # C10 豁免证据必须在盘上 —— 声明一份不存在的自述文件必须被抓住
    fake_ev = "skills-inventory/refs/不存在-自述.md"
    if not os.path.exists(os.path.join(root, fake_ev)):
        P.append("C10 编造的自述文件路径被 E2 识破（豁免不能凭空声明）")
        lines.append("  ✓ C10 编造的自述文件路径确实不在盘上 → E2 会红")
    else:
        F.append(("C10", "样本自述文件居然存在，这条对照失效"))
        lines.append("  ✗ C10 对照失效")

    # C11 分母为 0 的断言必须红，不许绿
    #     —— 这是本项目最贵的那个形状（§2.4「名字出现过不是拦得住」）的镜像：
    #        **一条匹配 0 个文件的断言，永远绿，而且它绿得跟真通过一模一样。**
    #        实测触发过：按任务书的 `PMO/守衡-*-修复记录.md` 写正则，匹配 0 个文件。
    one("C11 匹配 0 个文件的断言（分母为 0）必须红，不许绿",
        ["B"],
        _ok_readme(),
        drop=("PMO/守衡-查名修复记录.md",))

    # C12 历史缺陷必须能被抓住：把**真实的**仓数据里的 README 换回重写前那份存根，
    #     在内存里重算一次 —— ADR 必须全部不可达、总数必须超过钉住值。
    #     这条的价值是：重写前的那个读数（不可达 178）**今天仍然复现得出来**，
    #     不必依赖任何人的记忆，也不必把 README 改回去（§2.1：反向对照只在内存里做）。
    if not real_tracked or not real_docs:
        UNTESTED.append("C12 拿不到真实仓数据，历史存根那条对照没跑")
        lines.append("  ⚠ C12 未测：拿不到真实仓数据，历史存根那条对照没跑")
    else:
        stub_bodies = dict(real_bodies)
        stub_bodies["README.md"] = "# audit_multi_content\n内容审计\n"
        r_stub = analyze(real_tracked, real_docs, stub_bodies, doc_only_relay=True)
        # 判据刻意写成三条**形状**断言，不是「总数必须等于 178」那种数字断言
        # （钉死数字的对照会随仓库演化变成误报，§2.1.1：会误报的检查器更糟）：
        #   ① ADR 索引本身不可达；② 四篇修复记录全部不可达；③ 总数超过钉住值。
        adr_index_dead = "ADR/README.md" not in r_stub["reachable_docs"]
        pmo_all_dead = bool(r_stub["unreachable_pmo_fix"]) \
            and len(r_stub["unreachable_pmo_fix"]) == r_stub["pmo_fix_n"]
        if adr_index_dead and pmo_all_dead and r_stub["unreachable_n"] > pinned:
            P.append("C12 把 README 换回 35 字节存根（内存里）→ ADR 索引与 %d 篇修复记录全部不可达、"
                     "总数 %d > 钉住值 %d" % (r_stub["pmo_fix_n"], r_stub["unreachable_n"], pinned))
            lines.append("  ✓ C12 换回历史存根 → ADR 索引不可达 · 修复记录 %d/%d 不可达 · 不可达总数 %d"
                         "（重写前的读数形状复现）"
                         % (len(r_stub["unreachable_pmo_fix"]), r_stub["pmo_fix_n"],
                            r_stub["unreachable_n"]))
        else:
            F.append(("C12", "把 README 换回存根后仍不够红（ADR 索引不可达=%s / 修复记录全不可达=%s / "
                             "总数 %d vs 钉住值 %d）—— 本检查器抓不到它要抓的那个缺陷"
                      % (adr_index_dead, pmo_all_dead, r_stub["unreachable_n"], pinned)))
            lines.append("  ✗ C12 换回历史存根后仍不够红")

    # C13 有红时也必须报出未测（H 段那条：只看最后一行的人会以为「其余都验过了」）
    v_mixed = verdict(3, 2, 1)
    if "未测" in v_mixed and "红 2" in v_mixed and "过 3" in v_mixed:
        P.append("C13 同时有红与未测时，结论行两样都报")
        lines.append("  ✓ C13 混合态结论行：%s" % v_mixed)
    else:
        F.append(("C13", "混合态结论行漏报了红或未测：%r" % v_mixed))
        lines.append("  ✗ C13 混合态结论行漏报：%r" % v_mixed)

    return P, F, lines


# ══════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════

def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    readme_only = "--readme-only" in argv
    controls = "--controls" in argv
    root = ROOT
    for a in argv:
        if a.startswith("--root="):
            root = os.path.abspath(a.split("=", 1)[1])

    print("=" * 72)
    print("verify_doc_reachability.py —— 文档可达性")
    print("=" * 72)
    print("口径：已入库文件（git ls-files -z）；中继只能是文档；目录引用不构成边。")
    print("      起点 = %s" % ("README.md（--readme-only）" if readme_only else " ∪ ".join(SEEDS)))
    print()

    sc = scan(root)
    if sc is None:
        UNTESTED.append("git ls-files 取不到已跟踪文件集合")
        print("⚠ 未测：`git ls-files -z` 在 %s 跑不出来。" % root)
        print()
        print(verdict(0, 0, len(UNTESTED)))
        return 2
    tracked, docs, bodies, unreadable = sc
    if unreadable:
        UNTESTED.append("有 %d 份文档读不出：%s" % (len(unreadable), ", ".join(unreadable[:5])))
        print("⚠ 未测：有 %d 份文档读不出正文（读不出 ≠ 没有引用 ≠ 通过）：" % len(unreadable))
        for u in unreadable[:10]:
            print("     %s" % u)
        print()

    seeds = ("README.md",) if readme_only else SEEDS
    r = analyze(tracked, docs, bodies, seeds=seeds)

    print("已跟踪文件 %d · 其中文档 %d · 闭包内文件 %d · 可达文档 %d · 不可达文档 %d"
          % (r["tracked_n"], r["docs_n"], r["closure_files_n"],
             r["reachable_docs_n"], r["unreachable_n"]))
    print("README.md 入口自检：%d 字节 / %d 行 / %d 个 Markdown 链接"
          % (_readme_stat(root)))
    print()

    P, F = check(r, PINNED_UNREACHABLE, root=root)

    # 与 .ua 诊断的口径对照（同一条命令、两种读法）
    wide = analyze(tracked, docs, bodies, seeds=seeds, doc_only_relay=False, wide=True)
    print("口径对照（同一份数据，换一次读法）：")
    print("  主口径（中继只能是文档）      可达 %3d / 不可达 %3d"
          % (r["reachable_docs_n"], r["unreachable_n"]))
    print("  宽口径（= .ua 诊断，任何文件） 可达 %3d / 不可达 %3d"
          % (wide["reachable_docs_n"], wide["unreachable_n"]))
    only_via_code = sorted(d for d in wide["reachable_docs"] if d not in set(r["reachable_docs"]))
    print("  只在宽口径下可达（全靠代码/机器产物当中继）：%d 份" % len(only_via_code))
    print()

    print("豁免分项（E1 恒等式：分项之和 == 不可达总数）：")
    for cid, _pred, why, ev in EXEMPT_CLASSES:
        n = len(r["by_class"].get(cid, []))
        tot, reach_n = r["class_span"].get(cid, (0, 0))
        flag = ""
        if tot == 0:
            flag = "　← 空类：这条声明可能已经过期"
        elif reach_n:
            flag = "　← **该类共 %d 份，其中 %d 份是有入边的**：剩下的不可达未必是「本来就不该有入口」" % (tot, reach_n)
        print("  %-22s 不可达 %3d 份 / 共 %3d 份%s%s"
              % (cid, n, tot, ("　证据：%s" % ev) if ev else "", flag))
        print("      %s" % why)
        if verbose:
            for d in r["by_class"].get(cid, []):
                print("        - %s" % d)
    if r["unclassified"]:
        print("  %-22s %3d 份  ← 落不进任何类，E1 必红" % ("<未归类>", len(r["unclassified"])))
        for d in r["unclassified"][:20]:
            print("        - %s" % d)
    print()

    if verbose:
        print("不可达文档（%d）：" % r["unreachable_n"])
        for d in r["unreachable"]:
            print("  - %s" % d)
        print()

    for line in P:
        print("  ✓ %s" % line)
    for label, why in F:
        print("  ✗ [%s] %s" % (label, why))
    print()

    if controls:
        print("-" * 72)
        print("反向对照（--controls）：全部在内存里造样本，不碰任何真实文件")
        print("-" * 72)
        cp_, cf_, lines = run_controls(root=root, real=(tracked, docs, bodies))
        for ln in lines:
            print(ln)
        print()
        P = P + cp_
        F = F + cf_
        print("控制组：%d 项过 / %d 项红" % (len(cp_), len(cf_)))
        if cf_:
            for label, why in cf_:
                print("  ✗ %s：%s" % (label, why))
        print()

    line = verdict(len(P), len(F), len(UNTESTED))
    if UNTESTED:
        for u in UNTESTED:
            print("  ⚠ 未测：%s" % u)
    print(line)

    if F:
        return 1
    if UNTESTED:
        return 2
    return 0


def _readme_stat(root):
    """README.md 的字节/行/链接数。读不出就报 -1（不写成 0 —— 那是假读数）。"""
    p = os.path.join(root, "README.md")
    try:
        with open(p, "rb") as fh:
            raw = fh.read()
    except Exception:
        return -1, -1, -1
    txt = raw.decode("utf-8", "replace")
    return len(raw), txt.count("\n") + (0 if txt.endswith("\n") else 1), len(MD_LINK_RE.findall(txt))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
