#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_citation_fidelity.py — 引文保真度门（交付物最后一道保险）

对报告里每一处 `【原文】` 引文，回查它**是否真的存在于所引证据文件里**。
本会话已实证出现过三类「看起来像引文、实际无法定位」的内容 ——

  1. 证据文件**文件名与内容不符**（`rulefit-arxiv.txt` 实为组合数学论文
     `arXiv:0811.3652`、`ke-llm-drops.txt` 实为编程题生成论文、
     `ck-thesis-uva.txt` 实为 "Record not found"）——见 `_evidence/_KNOWN_MISLABELS.md`
  2. 两文件**逐字节相同**却声称是两个来源 —— 引用时会误当作两条独立证据，
     样本量虚增（本脚本对命中文件顺带做同尺寸同哈希别名检测）
  3. **检索工具静默截断**造成假阴性 —— Amazon 政策页正文躺在单行
     11,405 / 29,989 字符的转义 JSON 里，任何按行抽取的工具都会丢内容，
     于是「查不到」被误判成「引文是编的」

因此本脚本的四条硬约束：

  · **整文件字节级读取**：不用 readline、不对行长设上限、不按行索引
    （超长行在本项目里是常态，不是异常）
  · **前缀/分段匹配**：引文常以 `…` 截断，全串匹配会大量假阴性；
    且 `…` 可能出现在**句中**（`A … B`），所以切成若干段，要求每段
    （长度达阈值的）都在**同一文件**里命中
  · **多形态归一化**：去粗体 `**`、去反引号、去 blockquote `>`、压缩空白、
    统一引号（`'` `'` `"` `"` → ASCII）、统一破折号（`—` `–` `−` → `-`）、
    全角→半角（NFKC）、去零宽字符
  · **承载形态展开**：证据文件存的常是引文的**编码形态**而非渲染后文本 ——
    JSON 转义（`\\n` `\\"` `\\uXXXX`）、HTML 标签 + 实体（`&amp;` `&#39;`）、
    PDF 压缩流（FlateDecode + `Tj`/`TJ` 算子）。三者都要还原后再匹配

它**不**判断引文是否支持结论（那需要人读）。本脚本能抓出「伪造引证 / 转述冒充
原文 / 张冠李戴 / 来源重复计数」，抓不出「引文为真但被过度解读」。

输出
----
  · 终端清单：状态 / 匹配级别 / 承载形态 / 来源文件 / 行号
  · `_evidence/_citation_fidelity_report.json`
  · 未命中项给出**最可能来源文件**（按最长公共子串排序）+ **已核验的最长片段**
  · 命中项的**声明来源校验**：若引文旁标注了 `_evidence/...` 路径，单独报告
    「命中文件 == 声明文件」还是「命中了，但不在你声明的那一个里」

退出码
------
  0  全部引文已核验（EXACT / WS / NORM / TIGHT / PREFIX）
  1  存在 MISS 或 PARTIAL（必须人工复核）
  2  用法错误 / 找不到目标文件

用法
----
    python3 audit_citation_fidelity.py                          # 主交付物 + _shards/
    python3 audit_citation_fidelity.py 规范-审核规则库完整设计.md
    python3 audit_citation_fidelity.py R3-rule-engineering.md --quiet
    python3 audit_citation_fidelity.py --list                   # 只打印抽取结果（调试解析器）
    python3 audit_citation_fidelity.py --no-pdf                 # 跳过 PDF 解压轮
    python3 audit_citation_fidelity.py --min-len 45             # 只核验 >=45 字符的引文

作者注：本脚本的唯一目的是让「这条引文在不在来源里」变成一个别人可以重复执行的
机械判断，而不是一个需要信任作者的说法。
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
import unicodedata
import zlib

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EVIDENCE = os.path.join(ROOT, "_evidence")
DEFAULT_SHARDS = os.path.join(ROOT, "_shards")
DEFAULT_MAIN = os.path.join(ROOT, "规范-审核规则库完整设计.md")
DEFAULT_JSON = os.path.join(ROOT, "_evidence", "_citation_fidelity_report.json")

# ---------------------------------------------------------------- 可调阈值

MIN_SEGMENT = 12        # 截断引文分段：短于此长度的段不作为必要条件
MIN_SEGMENT_FAIL = 40   # 分段缺失且该段长于此值 => PARTIAL（失败）；更短的段只记警告
ANCHOR_WORD_STRONG = 6  # 预筛锚词最短长度（英文字长，不是连续字母数字串）
ANCHOR_WORD_LOOSE = 5   # 补漏轮锚词最短长度
MAX_VARIANT_BYTES = 24 * 1024 * 1024   # 超过此大小的文件只展开最忠实的两种形态
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_HAY_BYTES = 1200 * 1024 * 1024  # 已读入文件的缓存上限（按字节）；PDF 轮需要装下全部 PDF
MAX_EXPAND_BYTES = 8 * 1024 * 1024    # 超过此大小只做 txt 形态，不做 json/html 展开
MAX_FILES_REPORT = 5    # 未命中时列出几个候选来源
MAX_LCS_POOL = 60       # 未命中时最多对多少个候选文件做最长公共子串定位
MAX_RARE_WORD_FILES = 400       # 锚词命中文件数超过此值即视为无区分度，不参与求交
MAX_CANDS_PER_CIT = 80          # 单条引文最多核验多少个候选文件
MAX_CAND_BYTES = 16 * 1024 * 1024   # 单条引文的候选文件体积预算

TAG_RANK = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}

# 目录排除：浏览器 profile / 依赖库 / 隔离区，不是研究证据
EXCLUDE_DIR_PARTS = (
    "_chromeprof", "_cfprof", "_pylibs", "_tools", "_r4b_tools",
    "_wrong-id-quarantine", "node_modules", ".git", "__pycache__",
    "_scratch", "_ttcheck",
)

BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svgz",
    ".tflite", ".wasm", ".so", ".dylib", ".dll", ".a", ".o", ".bin",
    ".db", ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".otf",
    ".zip", ".gz", ".bz2", ".xz", ".7z", ".tar", ".crx", ".pma",
    ".mp4", ".mov", ".mp3", ".wav", ".class", ".pyc", ".pyd", ".node",
    ".binarypb", ".curlerr", ".lock", ".pb",
}
TEXT_EXT = {
    ".txt", ".md", ".markdown", ".html", ".htm", ".xhtml", ".xml", ".json",
    ".jsonl", ".ndjson", ".csv", ".tsv", ".log", ".rdf", ".ttl", ".nt",
    ".n3", ".yaml", ".yml", ".js", ".css", ".py", ".sh", ".sample", ".raw",
    ".old", ".rst", ".srt", ".vtt", ".text", ".geojson", ".mjs", ".cjs",
}

# ---------------------------------------------------------------- 归一化

ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, 0x00AD], None)

QUOTE_MAP = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x2032: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"', 0x2033: '"',
    0x00AB: '"', 0x00BB: '"', 0x2039: "'", 0x203A: "'",
    0x0060: "'", 0x00B4: "'", 0x02BC: "'", 0x02BB: "'",
}
DASH_MAP = {
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-",
    0x2015: "-", 0x2212: "-", 0x2043: "-", 0xFE58: "-", 0xFE63: "-",
    0xFF0D: "-", 0x2E3A: "-", 0x2E3B: "-",
}
SPACE_MAP = dict.fromkeys(
    [0x00A0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
     0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000, 0x2028, 0x2029],
    " ")
for _c in (0x0009, 0x000B, 0x000C, 0x000D):
    SPACE_MAP[_c] = " "

_WS_RUN = re.compile(r"\s+")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")      # [text](url) -> text
MD_REFLINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")  # [text][ref] -> text


def fold(s):
    """引号 / 破折号 / 全角半角 / 零宽归一化。引文侧与证据侧施加同一函数。"""
    if not s:
        return s
    s = s.translate(ZERO_WIDTH)
    s = s.translate(QUOTE_MAP)
    s = s.translate(DASH_MAP)
    s = s.translate(SPACE_MAP)
    s = unicodedata.normalize("NFKC", s)
    return s


def collapse_ws(s):
    return _WS_RUN.sub(" ", s).strip()


def nows(s):
    return _WS_RUN.sub("", s)


def strip_md_marks(s, mode):
    """去掉 markdown 强调标记。mode='del' 删除，mode='sp' 换成空格。

    两种模式都必须有：`**bold**` 与正文相邻时（见主交付物 §5.1 那条 NIST 引文，
    形如 `` impact` **`can affect ... ``），删除会把两个词粘成一个，只有换成
    空格才还原得回来。
    """
    rep = " " if mode == "sp" else ""
    # markdown 链接语法也是「标记」而不是内容：交付物里常写成 `[privacy complaint]`
    # 而来源里是 `[privacy complaint](https://...)`。不剥掉括号与 URL 就会假阴性。
    s = MD_LINK_RE.sub(r"\1", s)
    s = MD_REFLINK_RE.sub(r"\1", s)
    s = s.replace("**", rep).replace("__", rep).replace("~~", rep)
    s = s.replace("`", rep)
    if mode == "sp":
        s = _WS_RUN.sub(" ", s)
    return s.strip()


STOPWORDS = set("""
the and for that with this from have been were are was not but you your our its his her their them they will would shall
should could other which there these those about into than then when where what while who whom whose also such only more most
information content policy service account privacy review document change source user users provider providers platform platforms
commission regulation article section measure requirement statement process system number person public general however therefore
including accordance pursuant applicable same each both few many some any all may must can does did done
""".split())


def anchor_pool(s, minimum=6, want=4):
    """锚词池 = 引文里最长的若干个**非停用词**单词（转小写）。

    早先两版锚串方案都错了，记录在此以免再犯：

      1. 「20 个连续字母数字」—— 英文散文里几乎不存在这种串，绝大多数引文一个
         锚串都拿不到，于是全部静默 MISS（实测 426 条引文只有 69 条拿到锚串）；
      2. 「最长的词」—— 实测整个 `_evidence/` 里锚词命中集的**中位数是 209 个
         文件**；`content` / `policy` / `information` / `service` 这类词各自命中
         1,400–2,085 个文件。按长度选锚≈按常见度选锚，候选量必然爆炸。

    正确做法是**按实测稀有度选**（见 `pick_rarest`）。这里只负责给出候选池，
    真正的挑选要等一轮语料扫描拿到「每个词命中多少个文件」之后再做。
    """
    words = re.findall(r"[A-Za-z]{%d,}" % minimum, s)
    out, seen = [], set()
    for w in sorted(words, key=len, reverse=True):
        lw = w.lower()
        if lw in seen or lw in STOPWORDS:
            continue
        seen.add(lw)
        out.append(lw)
        if len(out) >= want:
            break
    return out


def head_words(s, want=6, minimum=3):
    """取片段**开头的连续若干词**（转小写）。

    为什么需要它：锚词池取的是「最长的词」，这些词在句子里往往不相邻，
    稀有度求交后仍可能剩下几百个候选（=> 被预算截断 => UNDECIDED）。
    而**开头连续 6 个词同时出现在同一文件**是极强的信号 —— 交集通常只剩
    个位数个文件，且这 6 个词本来就在一次语料扫描里能拿到命中集。
    """
    words = re.findall(r"[A-Za-z0-9]{%d,}" % minimum, s)
    out, seen = [], set()
    for w in words:
        lw = w.lower()
        if lw in seen:
            continue
        seen.add(lw)
        out.append(lw)
        if len(out) >= want:
            break
    return out


def phrase_words(s, want=10):
    """取片段**开头连续**的若干个词，**不去重、不筛长度**，专供轮 4 的正则用。

    这里绝不能用 `head_words`：它会去重、并要求词长 >= 3，于是
    `The assessment scales in this appendix can be used by organizations`
    会变成 `the assessment scales this appendix can used organizations`
    —— 一个**并不连续**的词序列，拼成的正则永远匹配不到原文
    （实测正是它把 `R8/nist-sp800-30r1.txt` 里明明存在的句子报成 MISS）。
    短语必须逐词照抄才叫短语。
    """
    words = re.findall(r"[A-Za-z0-9]+", s)
    return [w.lower() for w in words[:want]]


def pick_rarest(plan, hits, idx):
    """按**实测稀有度**挑锚词，返回它们的命中文件交集。

    稀有度 = 该词在 `_evidence/` 里命中多少个文件。取最稀有的词，再依次与
    其他够稀有的词求交；交集非空就用交集。这样候选通常压到个位数，
    而且「两个词共现」本身就是一条独立证据。
    """
    words = [w for w in plan[idx].get("pool", []) if w in hits]
    if not words:
        return None
    words.sort(key=lambda w: len(hits[w]))
    cand = set(hits[words[0]])
    for w in words[1:]:
        if len(hits[w]) > MAX_RARE_WORD_FILES:
            break
        inter = cand & hits[w]
        if inter:
            cand = inter
    return cand


# ---------------------------------------------------------------- 引文抽取

MARKER_RE = re.compile(r"【\s*原文[^】]*】|\[\s*原文[^\]\s]*\]")
BQ_RE = re.compile(r"^\s*(?:>\s?)+")
LABEL_OPEN, LABEL_CLOSE = "（(", "）)"
COLON_CHARS = "：:"
# 标记后紧随的粗体闭合符：`> **[原文]**（...）` 里的 `**`
BOLD_TAIL_RE = re.compile(r"^\s*(?:\*\*|__|\*|_)\s*")
# 反引号包起来的才是引文本身；行内的 `Meta：` / `（GitHub ToS）` 是归属说明
BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
# 行内归属前缀：`Meta：` / `TikTok：` / `YouTube：`
ATTRIB_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 .&/_-]{0,28}[:：]\s*")

SCAN_FWD = re.compile(r"(?:【|\[)\s*原文|【判断|【结论|【核验")   # 遇到即停止向后收集
STRUCT_START = re.compile(
    r"^\s*(?:#{1,6}\s|【|\[|来源\s*[:：]|URL\s*[:：]|https?://|```|\||>\s|"
    r"[-*·]\s|\d+[.)]\s|\*\*|（|\(|HTTP\s|METHOD\s*[:：]|FETCHED\s*[:：]|"
    r"BYTES\s*[:：]|SOURCE_URL\s*[:：])")

EV_PATH_RE = re.compile(
    r"_evidence/[A-Za-z0-9_\-./]+\.[A-Za-z0-9]{1,8}")
EV_BARE_RE = re.compile(r"`([A-Za-z0-9_\-.]+\.[A-Za-z0-9]{1,8})`")


class Citation(object):
    __slots__ = ("path", "line", "label", "body", "index", "declared", "ctx",
                 "spans")

    def __init__(self, path, line, label, body, index, declared, ctx, spans):
        self.path = path
        self.line = line
        self.label = label
        self.body = body
        self.index = index
        self.declared = declared      # 引文旁声明的证据文件（可能为空）
        self.ctx = ctx                # 上下文原文（供未命中时人工复核）
        self.spans = spans            # 反引号片段（>1 时说明引文是多段拼的）


def _balanced_label(s):
    if not s or s[0] not in LABEL_OPEN:
        return None, s
    depth = 0
    for i, ch in enumerate(s):
        if ch in LABEL_OPEN:
            depth += 1
        elif ch in LABEL_CLOSE:
            depth -= 1
            if depth == 0:
                return s[1:i], s[i + 1:]
    return None, s


def _inline_quote(rest):
    """从标记行的剩余部分取引文，返回 (引文串, 反引号片段列表)。

    优先用反引号包起来的片段 —— 在本项目的版式里反引号**就是**引文边界：
    `Meta：`we ...`` 里的 `Meta：`、`（GitHub Terms of Service）` 是归属说明，
    把它们并进引文会让逐字比对必然失败（假阳性未命中）。
    """
    s = BQ_RE.sub("", rest)
    spans = BACKTICK_SPAN_RE.findall(s)
    if spans and sum(len(x) for x in spans) >= 8:
        return collapse_ws(" ".join(spans)), spans
    s = strip_md_marks(s, "sp").strip()
    lab, tail = _balanced_label(s)
    if lab is not None:
        s = tail.strip()
    s = ATTRIB_RE.sub("", s)
    return collapse_ws(s), []


def iter_citations(text, path, known_basenames):
    """按文档顺序抽取全部 【原文】 引文。

    同时处理两种在本项目里实际存在的版式：

      版式 A（主交付物）：`> **[原文]**（来源）` + 同行反引号内容 / 下一行 blockquote
      版式 B（分片）：    `【原文】（来源）` 独立成行 + 空行 + `> 引文正文` + `来源：...`

    关键约束：**只有标记行本身没有正文时才向后看**，否则相邻引文会互相吞掉
    （主交付物 §5.6 有三条引文紧挨着，§4.3 有连排的行内引文）。
    """
    lines = text.split("\n")
    n = len(lines)
    i = 0
    idx = 0
    while i < n:
        line = lines[i]
        m = MARKER_RE.search(line)
        if not m:
            i += 1
            continue

        rest = BOLD_TAIL_RE.sub("", line[m.end():])
        label, rest = _balanced_label(rest.lstrip())
        rest = rest.lstrip()
        while rest and rest[0] in COLON_CHARS:
            rest = rest[1:].lstrip()

        inline, spans = _inline_quote(rest)
        pieces = []
        end_line = i

        if len(inline) >= 8:
            pieces.append(inline)
        else:
            spans = []
            j = i + 1
            gaps = 0
            while j < n and lines[j].strip() == "" and gaps < 3:
                j += 1
                gaps += 1
            collected = []
            if j < n and lines[j].lstrip().startswith(">"):
                while j < n:
                    cur = lines[j]
                    if cur.strip() == "":
                        k = j + 1
                        while k < n and lines[k].strip() == "":
                            k += 1
                        if (k < n and lines[k].lstrip().startswith(">")
                                and not SCAN_FWD.search(lines[k])):
                            j = k
                            continue
                        break
                    if not cur.lstrip().startswith(">"):
                        break
                    if SCAN_FWD.search(cur):
                        break
                    collected.append(BQ_RE.sub("", cur))
                    j += 1
            elif j < n and lines[j].lstrip().startswith("```"):
                j += 1
                while j < n and not lines[j].lstrip().startswith("```"):
                    collected.append(lines[j])
                    j += 1
                j += 1
            else:
                while j < n:
                    cur = lines[j]
                    if cur.strip() == "" or STRUCT_START.match(cur):
                        break
                    collected.append(cur.strip())
                    j += 1
            if collected:
                body_txt = strip_md_marks(" ".join(collected), "sp").strip()
                lab2, tail2 = _balanced_label(body_txt)
                if lab2 is not None:
                    body_txt = tail2.strip()
                pieces.append(body_txt)
                end_line = j - 1
                spans = BACKTICK_SPAN_RE.findall(body_txt)
                if len(spans) < 2:
                    spans = []

        body = collapse_ws(" ".join(p for p in pieces if p))
        if body:
            ctx = "\n".join(lines[max(0, i - 3):min(n, max(end_line, i) + 9)])
            declared = _declared_files(ctx, known_basenames)
            idx += 1
            yield Citation(path, i + 1, (label or "").strip(), body, idx,
                           declared, ctx, spans)
        i = max(i + 1, end_line + 1)


def _declared_files(ctx, known_basenames):
    """从引文上下文里抽出它声明的证据文件路径。"""
    out = []
    for m in EV_PATH_RE.finditer(ctx):
        rel = m.group(0)
        if rel not in out:
            out.append(rel)
    for m in EV_BARE_RE.finditer(ctx):
        name = m.group(1)
        for full in known_basenames.get(name, ()):      # 仅接受唯一的 basename 匹配
            if full not in out:
                out.append(full)
    return out


def is_english(s):
    letters = sum(1 for c in s if c.isascii() and c.isalpha())
    nonspace = sum(1 for c in s if not c.isspace())
    if letters < 20 or nonspace == 0:
        return False
    if letters / float(nonspace) < 0.55:
        return False
    return len(re.findall(r"[A-Za-z]{2,}", s)) >= 4


ELLIPSIS_RE = re.compile(r"…|\.\.\.|\[\s*\.\.\.\s*\]")


def split_segments(s):
    return [p.strip() for p in ELLIPSIS_RE.split(s) if p.strip()]


CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]+")


def strip_cjk(s):
    """剥掉中日韩文字与全角标点。

    交付物里引文常被中文夹注包着（例如 `风险级「encoded in an orthogonal
    vector ... dynamically」`）。那些 CJK 字符**不在来源里**，直接拿整串去比对
    必然假阴性。所以额外生成一组「去 CJK」变体，排在所有原样变体之后。
    """
    return collapse_ws(CJK_RE.sub(" ", s))


def needle_variants(body, minimum):
    """从最严到最松生成待检索串。

    返回 [(rank, 标签, 串)]，按 rank 升序。

    rank = 去CJK标志 * 10 + 归一化级别：
      0..3   L0 原样 / L1 压空白 / L2 折引号破折号 / L3 去全部空白
      10..13 同上，但先剥掉中文夹注
    rank 小的优先，所以「逐字命中」永远胜过「剥掉中文夹注后才命中」。
    """
    txt = BQ_RE.sub("", body)
    txt = re.sub(r"(?m)^\s*[-*·]\s+", "", txt)
    txt = collapse_ws(txt)
    out, seen = [], set()
    for cjk in (0, 1):
        base = strip_cjk(txt) if cjk else txt
        if not base:
            continue
        for mode in ("del", "sp"):
            v0 = strip_md_marks(base, mode)
            if not v0:
                continue
            v1 = collapse_ws(v0)
            v2 = collapse_ws(fold(v1))
            v3 = nows(v2)
            for lvl, val in ((0, v0), (1, v1), (2, v2), (3, v3)):
                if len(val) < minimum or val in seen:
                    continue
                seen.add(val)
                out.append((cjk * 10 + lvl,
                            "L%d%s/%s" % (lvl, "+cjk" if cjk else "", mode),
                            val))
    out.sort(key=lambda x: x[0])
    return out


def build_parts(c):
    """把一条引文拆成若干**各自独立可核验**的片段。

    两种拆分理由，本项目里都真实存在：

      · 引文由多段反引号拼成（`… 第 6(1) 条 `Done at Brussels, 13 June 2024`，
        但同条 `shall apply from 2 August 2027``）—— 把它们用空格接起来会得到
        一个**在任何文件里都不存在**的串，全串匹配必然假阴性；
      · 引文以 `…` 截断，且省略号可能在**句中**（`A … B`）。

    返回 [(片段原文, 变体表)]，按片段长度降序 —— 最长的那段是主片段。
    """
    raw = list(c.spans) if len(c.spans) > 1 else [c.body]
    parts = []
    for p in raw:
        segs = split_segments(p)
        parts.extend(segs if segs else [p])
    parts = [collapse_ws(p) for p in parts]
    parts = [p for p in parts if len(p) >= MIN_SEGMENT]
    out = []
    for p in parts:
        v = needle_variants(p, MIN_SEGMENT)
        if v:
            out.append((p, v))
    out.sort(key=lambda x: -max(len(vv[2]) for vv in x[1]))
    return out


# ---------------------------------------------------------------- 承载形态

_JSON_ESC = re.compile(r"\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[nrtbf/\"'\\])")
_JSON_MAP = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
             "/": "/", '"': '"', "'": "'", "\\": "\\"}
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1\s*>", re.I | re.S)
_TAG_RE = re.compile(r"<[^<>]{0,400}?>", re.S)
_PDF_STR_RE = re.compile(rb"\((?:\\.|[^\\()])*\)", re.S)
_PDF_OCT_RE = re.compile(rb"\\([0-7]{1,3})")
_PDF_ESC_RE = re.compile(rb"\\([nrtbf()\\])")


def json_unescape(s):
    def rep(m):
        e = m.group(0)[1:]
        if e[0] in "uU" and len(e) == 5:
            try:
                return chr(int(e[1:], 16))
            except ValueError:
                return m.group(0)
        if e[0] in "xX" and len(e) == 3:
            try:
                return chr(int(e[1:], 16))
            except ValueError:
                return m.group(0)
        return _JSON_MAP.get(e, m.group(0))
    return _JSON_ESC.sub(rep, s)


def html_to_text(s):
    s = _SCRIPT_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    try:
        return html_lib.unescape(s)
    except Exception:
        return s


def pdf_stream_text(data):
    """尽力从 PDF 取正文：解压 FlateDecode 流 + 抽取 Tj/TJ 字符串算子。"""
    chunks, total = [], 0
    for m in re.finditer(rb"stream\r?\n?", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        if len(raw) > 20_000_000:
            continue
        dec = None
        for cand in (raw, raw.rstrip(b"\r\n"), raw.lstrip(b"\r\n")):
            try:
                dec = zlib.decompress(cand)
                break
            except Exception:
                continue
        if not dec:
            continue
        total += len(dec)
        chunks.append(dec)
        if total > 80_000_000:
            break
    if not chunks:
        return ""
    blob = b"\n".join(chunks)
    pieces = []
    for m in _PDF_STR_RE.finditer(blob):
        s = m.group(0)[1:-1]
        s = _PDF_ESC_RE.sub(lambda mm: {b"n": b"\n", b"r": b"\r", b"t": b"\t",
                                        b"b": b" ", b"f": b" ", b"(": b"(",
                                        b")": b")", b"\\": b"\\"}[mm.group(1)], s)
        s = _PDF_OCT_RE.sub(lambda mm: bytes([int(mm.group(1), 8) & 0xFF]), s)
        pieces.append(s.decode("utf-8", "replace"))
    return " ".join(pieces)


class Hay(object):
    """一个证据文件的全部承载形态。惰性构造：只有候选文件才会被真正展开。"""

    __slots__ = ("path", "data", "is_pdf", "_pdf_text", "_txt", "_forms")

    def __init__(self, path, data, is_pdf=False):
        self.path = path
        self.data = data
        self.is_pdf = is_pdf
        self._pdf_text = None      # 记忆化：PDF 解压代价极高，绝不能每次重算
        self._txt = None           # 记忆化：decode 也只做一次
        self._forms = {}           # 记忆化：展开后的形态列表

    def iter_variants(self, want_pdf=False):
        """产出 (形态名, 文本)，从最忠实到最宽松。

        小文件与 PDF **整表记忆化**：同一条候选文件会被多条引文反复访问，
        不记忆就会把 decode / 反转义 / 标签剥离 / PDF 解压重复做几十遍
        （实测这正是把一趟核验拖到 20 分钟以上的原因）。
        大文件不记忆，避免内存失控。
        """
        key = bool(want_pdf)
        cached = self._forms.get(key)
        if cached is not None:
            for pair in cached:
                yield pair
            return

        memo = (self.is_pdf or len(self.data) <= MAX_EXPAND_BYTES)
        out = []
        for pair in self._generate(want_pdf):
            if memo:
                out.append(pair)
            yield pair
        if memo:
            self._forms[key] = out

    def _generate(self, want_pdf=False):
        """真正的形态展开逻辑（惰性）。"""
        def emit(name, text):
            """把一种基础文本展开成 raw / ws / fold / tight 四档。"""
            if not text:
                return
            yield name + ".raw", text
            if len(text) > MAX_VARIANT_BYTES:
                return
            t1 = collapse_ws(text)
            yield name + ".ws", t1
            t2 = collapse_ws(fold(t1))
            yield name + ".fold", t2
            yield name + ".tight", nows(t2)

        if self.is_pdf:
            if want_pdf:
                if self._pdf_text is None:
                    try:
                        self._pdf_text = pdf_stream_text(self.data)
                    except Exception:
                        self._pdf_text = ""
                for pair in emit("pdf", self._pdf_text):
                    yield pair
            return

        if self._txt is None:
            self._txt = self.data.decode("utf-8", "replace")
        text = self._txt
        for pair in emit("txt", text):
            yield pair

        # 形态展开只对中小文件做 —— 大文件的标签剥离 / 反转义代价过高，
        # 而它们的正文本来就能在 raw 形态里命中（锚词不受转义影响）
        if len(text) > MAX_EXPAND_BYTES:
            return

        head = text[:4000].lower()
        sample = text[:300000]
        looks_json = (self.path.lower().endswith((".json", ".jsonl", ".ndjson"))
                      or head.lstrip()[:1] in "{[" or "\\n" in sample
                      or "\\u" in sample)
        looks_html = ("<html" in head or "<!doctype html" in head
                      or "<body" in head
                      or self.path.lower().endswith((".html", ".htm", ".xhtml",
                                                     ".xml", ".rdf")))
        if self.path.lower().endswith((".md", ".markdown", ".html", ".htm",
                                        ".xhtml", ".txt")):
            stripped = MD_LINK_RE.sub(r"\1", text)
            if stripped != text:
                for pair in emit("nolink", stripped):
                    yield pair
            # 证据侧也必须剥 markdown 强调标记 —— 引文侧一直在剥（`**Note:**`
            # 变成 `Note:`），而证据侧原样保留 `**`，两边就永远对不上。
            # 实测 `R1/youtube-strike-basics.md` 里逐字存在的句子就是这么被
            # 报成 MISS 的。用 'sp' 模式（替换成空格）而不是直接删除，避免粘连。
            plain = strip_md_marks(text, "sp")
            if plain != text:
                for pair in emit("mdstrip", plain):
                    yield pair
        if looks_json:
            for pair in emit("json", json_unescape(text)):
                yield pair
        if looks_html:
            for pair in emit("html", html_to_text(text)):
                yield pair
            if looks_json:
                for pair in emit("json+html", html_to_text(json_unescape(text))):
                    yield pair


_SIZE = {}              # path -> 字节数（候选排序用）
_HAY_CACHE = {}
_HAY_BYTES = [0]        # 已缓存字节数：按**字节**限流，不按文件数


def load_hay(path, is_pdf=False):
    h = _HAY_CACHE.get(path)
    if h is None:
        data = read_bytes(path)
        if data is None:
            return None
        h = Hay(path, data, is_pdf)
        _HAY_BYTES[0] += len(data)
        if _HAY_BYTES[0] > MAX_HAY_BYTES:
            _HAY_CACHE.clear()
            _HAY_BYTES[0] = len(data)
        _HAY_CACHE[path] = h
    return h


def find_in_hay(hay, needles, want_pdf=False, early_stop_rank=1):
    """在 hay 的所有承载形态里找 needles（needles 已按 rank 升序）。

    返回 (rank, 级别标签, 形态名, 偏移, 形态文本) 或 None。
    先取 rank 最小的（逐字 L0 最优，剥中文夹注的排在最后），同级再取最忠实的形态。

    **命中即停**：一旦拿到 rank <= early_stop_rank（默认 L0/L1，即逐字或仅差空白）
    就直接返回 —— 这已是最强证据，没必要再去建 HTML/JSON 那些昂贵形态。
    只有弱命中（L2/L3/去CJK）才继续遍历完所有形态，以免漏掉更严的那一个。
    """
    best = None
    for order, (name, text) in enumerate(hay.iter_variants(want_pdf=want_pdf)):
        for rank, label, val in needles:
            if val in text:
                key = (rank, order)
                if best is None or key < best[0]:
                    best = (key, label, name, text.find(val), text)
                break
        if best is not None and best[0][0] <= early_stop_rank:
            break
    return best


def longest_common_substring(needle, hay, cap=300):
    """二分搜索最长公共子串。未命中时用来定位「疑似来源」与「已核验的最长片段」。"""
    if not needle or not hay:
        return (0, "")
    lo, hi = 0, min(len(needle), cap)
    best_len, best_sub = 0, ""
    while lo <= hi:
        mid = (lo + hi) // 2
        found = None
        if mid == 0:
            found = ""
        else:
            tried = set()
            for i in range(0, len(needle) - mid + 1):
                sub = needle[i:i + mid]
                if sub in tried:
                    continue
                tried.add(sub)
                if sub in hay:
                    found = sub
                    break
        if found is not None:
            best_len, best_sub = mid, found
            lo = mid + 1
        else:
            hi = mid - 1
    return (best_len, best_sub)


# ---------------------------------------------------------------- 语料

#: `_evidence/` 顶层、`_` 开头的分析产物文件名（本工具与 integrity 工具写出）。
#: 这些文件里**逐字复述了引文本身**，绝不可当语料。
SELF_ARTIFACT_NAMES = (
    "_known_mislabels.md", "_citation_fidelity_misses.md",
    "_citation_fidelity_report.json", "_integrity_report.json",
    "_citation_miss_attribution.md",
)


def _is_self_artifact(relpath):
    """判断路径是否为工具自身产物。接受两种形式：

    · `_KNOWN_MISLABELS.md`（相对 `_evidence/`，walk_evidence 用）
    · `_evidence/_KNOWN_MISLABELS.md`（相对 ROOT，判定逻辑用）

    只认 **`_evidence/` 顶层** 的产物 —— 深度 2 的
    `_evidence/R1/raw/_body_*.md` 等 427 个下划线开头文件是**真实证据**，必须保留。
    """
    p = (relpath or "").replace("\\", "/")
    if p.startswith("_evidence/"):
        p = p[len("_evidence/"):]
    return "/" not in p and p.lower() in SELF_ARTIFACT_NAMES


def walk_evidence(root):
    files, pdfs, size_index, basenames = [], [], {}, {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not any(p in os.path.join(dirpath, d)
                                  for p in EXCLUDE_DIR_PARTS)]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            # ---- 自污染防护（本轮实测发现，务必保留）----
            # 本工具与 audit_evidence_integrity.py 会在 _evidence/ 顶层写出
            # `_` 开头的**分析产物**（_KNOWN_MISLABELS / _citation_fidelity_* /
            # _integrity_report）。这些文件里**逐字复述了引文本身**，若被当成
            # 语料，就会出现：一条在任何真实证据里都不存在的引文，因为「在自己
            # 上一轮的未命中报告里找到了自己」而被判 EXACT。
            # 实测：`Table H-2 or Organization-defined` 因此在 MISS 与 EXACT 之间
            # 翻转。**这是最危险的一类假通过 —— 自己证明自己。**
            # 只排除顶层（depth ≤ 1）的内置产物；R*/raw/_body_*.md 等 427 个
            # 下划线开头的**真实证据**文件必须保留在语料内。
            rel = os.path.relpath(full, root)
            if _is_self_artifact(rel):
                continue
            ext = os.path.splitext(fn.lower())[1]
            try:
                sz = os.path.getsize(full)
            except OSError:
                continue
            if sz == 0:
                continue
            _SIZE[full] = sz
            size_index.setdefault(sz, []).append(full)
            basenames.setdefault(fn, []).append(os.path.relpath(full, ROOT))
            if ext == ".pdf":
                pdfs.append(full)
            elif ext in TEXT_EXT or ext == "":
                files.append(full)
    return sorted(files), sorted(pdfs), size_index, basenames


def read_bytes(path, cap=MAX_FILE_BYTES):
    try:
        with open(path, "rb") as fh:
            return fh.read(cap)
    except OSError:
        return None


def looks_binary(data):
    return b"\x00" in data[:8192]


def corpus_pass(files, anchors, label, quiet):
    """一轮语料扫描：每个文件只读一次，文件内对全部锚串做 bytes.find。

    返回 **{锚串(str): set(文件)}**。**不按行、不设行长上限、整文件读入。**

    注意键类型：`data` 是 bytes，而锚串从 Markdown 正文抽出来是 str，
    `str in bytes` 在 Python 3 会直接抛 TypeError。这里在**内部**统一编码，
    并用反查表把键还原成原始 str —— 调用方拿到的必须还是 str，
    否则 `assign()` 用 str 去查会查不到，变成「0 命中」的**静默错误**（比崩溃更糟）。
    """
    if not anchors:
        return {}
    b2a, order = {}, []
    for a in anchors:
        if not a:
            continue
        b = a.encode("utf-8").lower()
        if b in b2a:
            continue
        b2a[b] = a
        order.append(b)
    hits = {}
    total = 0
    t0 = time.time()
    for k, path in enumerate(files):
        data = read_bytes(path)
        if not data:
            continue
        if looks_binary(data):
            continue
        total += len(data)
        # 小写副本让锚串匹配大小写不敏感（引文句首大小写常与原文不同），
        # 一次 C 速度的 lower() 远比多轮变体搜索便宜
        low = data.lower()
        for b in order:
            if b in low:
                hits.setdefault(b2a[b], set()).add(path)
        if not quiet and k and k % 2000 == 0:
            sys.stderr.write("  [%s] %d/%d 文件 / %.0fMB / %.0fs\n"
                             % (label, k, len(files), total / 1048576.0,
                                time.time() - t0))
            sys.stderr.flush()
    if not quiet:
        sys.stderr.write("  [%s] 扫完 %d 文件 / %.0fMB / %.1fs，命中锚串 %d/%d\n"
                         % (label, len(files), total / 1048576.0,
                            time.time() - t0, len(hits), len(order)))
        sys.stderr.flush()
    return hits


# ---------------------------------------------------------------- 主体

def build_plan(cits, min_len):
    plan = {}
    for c in cits:
        disp = collapse_ws(c.body)
        truncated = bool(ELLIPSIS_RE.search(c.body))
        multipart = len(c.spans) > 1
        full = needle_variants(c.body, min_len)
        parts = build_parts(c)
        plan[c.index] = {"display": disp, "truncated": truncated,
                         "multipart": multipart, "full": full,
                         "parts": parts, "cands": [],
                         "verifiable": bool(full) or bool(parts)}
    return plan


def verify_one(plan, c, cands, want_pdf=False):
    """在指定候选文件里核验一条引文。返回结果 dict 或 None。

    两步：先试**整段逐字**（最强证据）；不行再退到**分段核验**
    （多段反引号拼接 / `…` 截断 / 省略号在句中的情况）。
    """
    info = plan[c.index]

    # 候选排序 + 截断：真来源几乎总在**小**文件里，大文件（整站 dump、RDF、
    # 拼接日志）又最贵。按体积升序、且设字节预算，可以在有限时间内覆盖最可能
    # 命中的那批。被截断且未命中时返回 UNDECIDED —— 不能谎报成 MISS。
    min_needle_len = max([len(v[2]) for v in info["full"]] or [0])
    sized = []
    for p in cands:
        sz = _SIZE.get(p)
        if sz is None:
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
        if min_needle_len and sz < min_needle_len:
            continue                      # 文件比引文还短，装不下
        sized.append((sz, p))
    sized.sort()
    capped = False
    picked, budget = [], MAX_CAND_BYTES
    for sz, p in sized:
        if len(picked) >= MAX_CANDS_PER_CIT or budget - sz < 0:
            capped = True
            break
        picked.append(p)
        budget -= sz

    haylist = [(pp, load_hay(pp, pp.lower().endswith(".pdf"))) for pp in picked]
    haylist = [(pp, h) for pp, h in haylist if h is not None]
    if not haylist:
        return {"undecided": True, "capped": capped} if capped else None

    def scan(needles, subset=None):
        pool = haylist if subset is None else [h for h in haylist if h[0] == subset]
        best = None
        for pp, h in pool:
            got = find_in_hay(h, needles, want_pdf=want_pdf)
            if got is None:
                continue
            key = got[0][0]
            if best is None or key < best[0]:
                best = (key, pp, got)
        return best

    def mk(kind, pp, g, missing, weak):
        return {"tag": g[1], "form": g[2], "offset": g[3], "text": g[4],
                "file": pp, "kind": kind, "partial": missing, "weak": weak,
                "cjk": "+cjk" in g[1], "capped": capped}

    # 1) 整段逐字
    if not info["truncated"] and info["full"]:
        got = scan(info["full"])
        if got is not None:
            _k, pp, g = got
            return mk("full", pp, g, [], [])

    # 2) 分段
    if not info["parts"]:
        return {"undecided": True, "capped": capped} if capped else None
    got = scan(info["parts"][0][1])
    if got is None:
        return {"undecided": True, "capped": capped} if capped else None
    _k, pp, g = got
    missing, weak = [], []
    for ptext, pvars in info["parts"][1:]:
        if scan(pvars, subset=pp) is None:
            (missing if len(ptext) >= MIN_SEGMENT_FAIL else weak).append(ptext)
    return mk("parts", pp, g, missing, weak)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="交付物 【原文】 引文保真度机械回查",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="要扫描的 Markdown 文件")
    ap.add_argument("--evidence", default=DEFAULT_EVIDENCE, help="证据根目录")
    ap.add_argument("--shards-dir", default=DEFAULT_SHARDS, help="分片目录")
    ap.add_argument("--json", dest="json_out", default=DEFAULT_JSON,
                    help="报告输出路径（'' 表示不写）")
    ap.add_argument("--min-len", type=int, default=24,
                    help="最短引文长度（默认 24；原版默认 45，会静默跳过短引文）")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总")
    ap.add_argument("--list", action="store_true", help="只列出抽取到的引文（调试解析器）")
    ap.add_argument("--no-pdf", action="store_true", help="跳过 PDF 解压轮")
    ap.add_argument("--no-declared", action="store_true",
                    help="关掉「声明来源优先」快路径，直接全语料扫描")
    ap.add_argument("--include-non-english", action="store_true",
                    help="连非英文引文一起核验")
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 条（调试用）")
    args = ap.parse_args(argv)

    # ---- 目标文件 ----
    targets = []
    for f in args.files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if os.path.isdir(p):
            targets.extend(sorted(os.path.join(p, x)
                                  for x in os.listdir(p) if x.endswith(".md")))
        elif os.path.isfile(p):
            targets.append(p)
        else:
            sys.stderr.write("找不到目标文件：%s\n" % f)
            return 2
    if not targets:
        if os.path.isfile(DEFAULT_MAIN):
            targets.append(DEFAULT_MAIN)
        if os.path.isdir(args.shards_dir):
            targets.extend(sorted(os.path.join(args.shards_dir, x)
                                  for x in os.listdir(args.shards_dir)
                                  if x.endswith(".md")))
    targets = [t for t in targets if os.path.isfile(t)]
    if not targets:
        sys.stderr.write("没有可扫描的目标文件。\n")
        return 2

    # ---- 语料索引（先建，因为引文抽取要用 basename 表解析声明来源）----
    files, pdfs, size_index, basenames = walk_evidence(args.evidence)
    if not args.quiet:
        print("证据索引：%d 个文本文件 / %d 个 PDF" % (len(files), len(pdfs)))

    # ---- 抽取引文 ----
    cits, skipped_cjk, skipped_short = [], 0, 0
    for t in targets:
        try:
            with open(t, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            sys.stderr.write("读不到 %s：%s\n" % (t, exc))
            continue
        for c in iter_citations(text, t, basenames):
            if not args.include_non_english and not is_english(c.body):
                skipped_cjk += 1
                continue
            if len(collapse_ws(c.body)) < args.min_len:
                skipped_short += 1
                continue
            cits.append(c)
    if args.limit:
        cits = cits[:args.limit]

    if args.list:
        for c in cits:
            print("%s:%d  [%s]  %s" % (os.path.basename(c.path), c.line,
                                       c.label[:50], c.body[:150]))
            if c.declared:
                print("        声明来源：%s" % ", ".join(c.declared[:3]))
        print("\n共 %d 条（跳过非英文 %d，过短 %d）"
              % (len(cits), skipped_cjk, skipped_short))
        return 0
    if not cits:
        print("没有抽到可核验的英文引文。")
        return 0

    if not args.quiet:
        print("引文抽取：%d 条（跳过非英文 %d，过短 %d）"
              % (len(cits), skipped_cjk, skipped_short))
        for t in targets:
            print("  - %s" % os.path.relpath(t, ROOT))
        print("")

    plan = build_plan(cits, args.min_len)
    results = {}

    def record(c, res):
        """登记结果。**真实结果可以覆盖 UNDECIDED 占位，反之不行。**

        这条规则不能写成 `if c.index not in results`：后加的轮次（2.5 / 4 / 3）
        专门去救前面被预算截断的引文，而那些引文在 results 里已经留了一个
        undecided 占位。用「不存在才写」会把后轮**真正找到**的结果丢掉，
        于是它们最后被归成 MISS —— 实测这一条让轮 4 找到的 12 条全部蒸发。
        """
        if res is None:
            return
        cur = results.get(c.index)
        if cur is not None and not cur.get("undecided"):
            return
        results[c.index] = res

    # ---- 轮 0：声明来源快路径（顺带校验「声明文件 == 实际命中文件」）----
    if not args.no_declared:
        n0 = 0
        todo0 = [c for c in cits if c.declared]
        for _i, c in enumerate(todo0):
            if not args.quiet and _i and _i % 100 == 0:
                sys.stderr.write("  [轮0] %d/%d\n" % (_i, len(todo0)))
                sys.stderr.flush()
            cands = [os.path.join(ROOT, d) if not os.path.isabs(d) else d
                     for d in c.declared]
            cands = [p for p in cands if os.path.isfile(p)]
            if not cands:
                continue
            res = verify_one(plan, c, cands)
            if res is not None:
                res["declared_ok"] = True
                record(c, res)
                n0 += 1
        if not args.quiet:
            print("轮 0：声明来源快路径命中 %d/%d 条" % (n0, len(cits)))

    # ---- 轮 1 / 轮 2：全语料锚词扫描（按实测稀有度压候选）----
    def word_round(pending, minimum, want, label, progress):
        if not pending:
            return
        for c in pending:
            info = plan[c.index]
            primary = info["parts"][0][0] if info["parts"] else info["display"]
            info["pool"] = anchor_pool(primary, minimum, want)
        pool = {}
        for c in pending:
            for w in plan[c.index]["pool"]:
                pool.setdefault(w, []).append(c.index)
        if not args.quiet:
            print("轮 %s：全语料锚词扫描（%d 字母、每引文 %d 词，共 %d 个不同词），"
                  "%d 条待查 …" % (label, minimum, want, len(pool), len(pending)))
        hits = corpus_pass(files, sorted(pool), label, args.quiet)
        for _i, c in enumerate(pending):
            info = plan[c.index]
            cand = pick_rarest(plan, hits, c.index)
            if cand:
                info["cands"] = sorted(set(info.get("cands") or []) | cand)
            if not args.quiet and _i and _i % 50 == 0:
                sys.stderr.write("  [轮%s 核验] %d/%d\n" % (label, _i, len(pending)))
                sys.stderr.flush()
            record(c, verify_one(plan, c, info["cands"]))

    pending = [c for c in cits if c.index not in results]
    if pending:
        word_round(pending, ANCHOR_WORD_STRONG, 4, "1", 50)

    pending = [c for c in cits if c.index not in results]
    if pending:
        word_round(pending, ANCHOR_WORD_LOOSE, 3, "2", 25)

    # ---- 轮 2.5：首词共现（专治「候选被预算截断」）----
    unresolved = [c for c in cits
                  if c.index not in results
                  or (results.get(c.index) or {}).get("undecided")]
    if unresolved:
        head_map = {}
        for c in unresolved:
            info = plan[c.index]
            primary = info["parts"][0][0] if info["parts"] else info["display"]
            hw = head_words(primary, 6, 3)
            info["head"] = hw
            for w in hw:
                head_map.setdefault(w, []).append(c.index)
        if not args.quiet:
            print("轮 2.5：首词共现（%d 条待查 / %d 个不同词）…"
                  % (len(unresolved), len(head_map)))
        hits3 = corpus_pass(files, sorted(head_map), "2.5", args.quiet)
        for _i, c in enumerate(unresolved):
            info = plan[c.index]
            hw = [w for w in info.get("head", []) if w in hits3]
            if hw:
                # 按命中集从小到大求交：先拿最小的，逐个小下去
                hw.sort(key=lambda w: len(hits3[w]))
                cand = set(hits3[hw[0]])
                for w in hw[1:]:
                    cand &= hits3[w]
                    if not cand:
                        break
                if cand:
                    info["cands"] = sorted(cand)
            # 首词共现没收敛时，退回到并集（比没有候选强），交由预算截断
            if not info.get("cands"):
                union = set()
                for w in hw[:3]:
                    union |= hits3[w]
                info["cands"] = sorted(union)
            if not args.quiet and _i and _i % 40 == 0:
                sys.stderr.write("  [轮2.5 核验] %d/%d\n" % (_i, len(unresolved)))
                sys.stderr.flush()
            record(c, verify_one(plan, c, info["cands"]))

    # ---- 轮 4：空白容忍短语正则（兜底，专治「候选被预算截断」）----
    # 前几轮都靠「词命中集求交」压候选，一旦求交不收敛就只能按预算截断，
    # 于是留下 UNDECIDED。这一轮改用**开头连续 8 个词、允许词间任意非字母
    # 字符（换行/标点/HTML 标签残渣）**的正则直接在语料里定位：候选是精确的，
    # 不再是「没查完」。代价是每个 pattern 都要扫一遍语料，所以只对前几轮
    # 没收敛的少数引文做。
    unresolved = [c for c in cits
                  if c.index not in results
                  or (results.get(c.index) or {}).get("undecided")]
    if unresolved:
        pats = []
        for c in unresolved:
            info = plan[c.index]
            primary = info["parts"][0][0] if info["parts"] else info["display"]
            words = phrase_words(primary, 10)
            if len(words) < 4:
                continue
            pats.append((c.index,
                         re.compile(rb"\W{0,4}".join(
                             re.escape(w.encode("ascii", "ignore"))
                             for w in words if w))))
        if not args.quiet:
            print("轮 4：空白容忍短语正则（%d 条待查 / %d 个模式）…"
                  % (len(unresolved), len(pats)))
        found = {}
        total = 0
        t0 = time.time()
        for _k, path in enumerate(files):
            data = read_bytes(path)
            if not data or looks_binary(data):
                continue
            total += len(data)
            low = data.lower()
            for idx, rx in pats:
                if idx in found:
                    continue
                if rx.search(low):
                    found.setdefault(idx, []).append(path)
            if not args.quiet and _k and _k % 2000 == 0:
                sys.stderr.write("  [4] %d/%d 文件 / %.0fMB / %.0fs，已定位 %d\n"
                                 % (_k, len(files), total / 1048576.0,
                                    time.time() - t0, len(found)))
                sys.stderr.flush()
        if not args.quiet:
            sys.stderr.write("  [4] 扫完 %d 文件 / %.0fMB / %.1fs，定位 %d/%d 条\n"
                             % (len(files), total / 1048576.0, time.time() - t0,
                                len(found), len(pats)))
            sys.stderr.flush()
        for _i, c in enumerate(unresolved):
            fs = found.get(c.index)
            if not fs:
                continue
            info = plan[c.index]
            info["cands"] = sorted(fs)
            record(c, verify_one(plan, c, info["cands"]))

        # 轮 4 是全语料穷尽扫描（允许词间任意非字母字符），做完之后仍然没有
        # 任何命中的，就不再是「没查完」而是「**在证据目录里定位不到**」。
        # 不清掉 undecided 标记会让这批永远停在 UNDECIDED，掩盖真实结论。
        for c in unresolved:
            r = results.get(c.index)
            if r is not None and r.get("undecided"):
                results.pop(c.index, None)

    # ---- 轮 3：PDF 流解压（只补仍没找到的）----
    # 循环必须**反过来写**：以 PDF 为外层、待查引文为内层。
    # 正着写（每条引文各遍历一遍 162 个 PDF）会把同一批 PDF 解压并归一化 37 遍，
    # 实测把这一轮从 1 分钟拖到 20 分钟以上还没结束。
    pending = [c for c in cits if c.index not in results]
    if pending and pdfs and not args.no_pdf:
        if not args.quiet:
            print("轮 3：PDF 流解压（外层 PDF × 内层待查引文），%d 条待查 / %d 个 PDF …"
                  % (len(pending), len(pdfs)))
        remaining = list(pending)
        for _pi, pp in enumerate(pdfs):
            if not remaining:
                break
            h = load_hay(pp, True)
            if h is None or not list(h.iter_variants(want_pdf=True)):
                continue
            still = []
            for c in remaining:
                # 不要写回 info["cands"]：那会让每条未命中引文的候选池最后
                # 只剩「循环结束后那一个 PDF」，未命中清单里的「最接近来源」
                # 于是变成随机 PDF（实测 4 条 MISS 全指向同一个 ftc-dotcom.pdf）
                res = verify_one(plan, c, [pp], want_pdf=True)
                if res is None:
                    still.append(c)
                else:
                    record(c, res)
            remaining = still
            if not args.quiet and _pi and _pi % 40 == 0:
                sys.stderr.write("  [轮3] %d/%d PDF，剩 %d 条\n"
                                 % (_pi, len(pdfs), len(remaining)))
                sys.stderr.flush()

    # ---- 未命中：LCS 定位疑似来源 ----
    misses = [c for c in cits
              if c.index not in results
              or (results.get(c.index) or {}).get("undecided")]
    for c in misses:
        info = plan[c.index]
        probe = nows(fold(strip_md_marks(info["display"], "sp")))
        pool = list(info.get("cands") or [])
        if not pool:
            pool = files[:MAX_LCS_POOL]
        scored = []
        for p in pool[:MAX_LCS_POOL]:
            h = load_hay(p, p.lower().endswith(".pdf"))
            if h is None:
                continue
            # 只用最忠实的一种形态做 LCS —— 逐形态全试是 O(形态数 × 二分搜索)，
            # 在几百个候选上会从秒级变成分钟级
            first = next(h.iter_variants(want_pdf=not args.no_pdf), None)
            if first is None:
                continue          # PDF 抽不出文本时生成器是空的，next() 会抛 StopIteration
            text = first[1]
            ln, frag = longest_common_substring(probe, nows(fold(text)))
            if ln:
                scored.append([ln, p, frag])
        scored.sort(key=lambda x: -x[0])
        info["lcs"] = scored[:MAX_FILES_REPORT]

    # ---- 别名检测（同一内容两个文件名 => 来源重复计数）----
    alias = {}
    _sha = {}

    def sha1_of(path):
        if path not in _sha:
            try:
                with open(path, "rb") as fh:
                    _sha[path] = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                _sha[path] = None
        return _sha[path]

    for c in cits:
        r = results.get(c.index)
        # UNDECIDED 结果只有 {"undecided": True}，没有 "file" —— 必须跳过，
        # 否则整个脚本会在最后一步 KeyError 崩掉（此坑已踩过一次）
        if not r or "file" not in r or r["file"] in alias:
            continue
        p = r["file"]
        if p.lower().endswith(".pdf"):
            continue
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        h = sha1_of(p)
        if h is None:
            continue
        same = [other for other in size_index.get(sz, [])
                if other != p and sha1_of(other) == h]
        if same:
            alias[p] = same

    # ---- 判级与输出 ----
    stats = {"exact": 0, "ws": 0, "norm": 0, "tight": 0,
             "prefix": 0, "multi": 0, "partial": 0, "miss": 0,
             "undecided": 0, "not_quote": 0, "self_ref": 0}
    rows = []
    for c in cits:
        info = plan[c.index]
        r = results.get(c.index)
        # ---- 自污染运行时断言（防御层，与 walk_evidence 的排除互为冗余）----
        # 排除逻辑若被改坏，这里必须把「命中来自工具自身产物」钉成 SELF_REF。
        # 实测事故：一条在任何真实证据里都不存在的引文，因为「在自己上一轮的
        # 未命中报告 `_citation_fidelity_misses.md` 里找到了自己」而被判 EXACT。
        # 这类假通过**自己证明自己**，比崩溃危险得多，故设此断言。
        if (r is not None and not r.get("undecided")
                and _is_self_artifact(os.path.relpath(r.get("file") or "", ROOT))):
            status = "SELF_REF"
            stats["self_ref"] += 1
        elif r is None:
            # `verifiable=False` 表示这条「引文」去掉链接/标记后剩下的正文不足
            # 12 个字符 —— 它根本不是引文（例如 `[GitHub](https://github.com/psf/policies)`
            # 这种光秃秃的链接）。报成 MISS 会让清单充满噪声，报成 NOT_QUOTE 才诚实。
            if not info.get("verifiable"):
                status = "NOT_QUOTE"
                stats["not_quote"] += 1
            else:
                status = "MISS"
                stats["miss"] += 1
        elif r.get("undecided"):
            status = "UNDECIDED"
            stats["undecided"] += 1
        elif r["partial"]:
            status = "PARTIAL"
            stats["partial"] += 1
        else:
            if info["truncated"]:
                status = "PREFIX"
            elif info["multipart"]:
                status = "MULTI"
            elif r["tag"].startswith("L0"):
                status = "EXACT"
            elif r["tag"].startswith("L1"):
                status = "WS"
            elif r["tag"].startswith("L2"):
                status = "NORM"
            else:
                status = "TIGHT"
            if r.get("cjk"):
                status += "+CJK"
            stats[status.split("+")[0].lower()] += 1
        rows.append((status, c, r, info))

    if not args.quiet:
        print("")
        print("=" * 104)
        cur = None
        for status, c, r, info in rows:
            base = os.path.basename(c.path)
            if base != cur:
                cur = base
                print("\n── %s ──" % base)
            if r is not None and "file" in r:
                line = ""
                if r["form"] == "txt.raw":
                    line = "  L%d" % (r["text"].count("\n", 0, r["offset"]) + 1)
                extra = ""
                if r["partial"]:
                    extra += "  缺段 %d" % len(r["partial"])
                if r.get("weak"):
                    extra += "  弱段 %d" % len(r["weak"])
                if r.get("declared_ok"):
                    extra += "  [声明来源]"
                elif c.declared:
                    extra += "  ⚠ 声明的是 %s" % os.path.basename(c.declared[0])
                print("  [%-7s] %-4s %-8s %-12s %s%s%s"
                      % (status, "L%d" % c.line, r["tag"], r["form"],
                         os.path.relpath(r["file"], ROOT), line, extra))
                print("            %s…" % info["display"][:84])
                for other in alias.get(r["file"], [])[:2]:
                    print("            ⚠ 同内容别名：%s"
                          % os.path.relpath(other, ROOT))
            else:
                print("  [%-7s] L%-4d %s" % (status, c.line, info["display"][:84]))
                if r is not None and r.get("undecided"):
                    print("            候选被预算截断且未命中 —— 这不是「未命中」，"
                          "加 --no-pdf 或调大 MAX_CANDS_PER_CIT 后可复检")
                for ln, p, frag in (info.get("lcs") or [])[:3]:
                    print("            最接近 %-4d 字符  %s"
                          % (ln, os.path.relpath(p, ROOT)))
                    if frag:
                        print("              片段：%s" % frag[:74])
                if not info.get("lcs"):
                    print("            未找到任何近似片段 —— 该引文可能不在证据目录内")
        print("\n" + "=" * 104)

    print("")
    print("汇总：共 %d 条英文引文（跳过非英文 %d，短于 %d 字符 %d）"
          % (len(cits), skipped_cjk, args.min_len, skipped_short))
    print("  EXACT   %-4d 逐字节一致（去掉 md 标记后）" % stats["exact"])
    print("  WS      %-4d 仅空白差异（证据文件里的换行折行）" % stats["ws"])
    print("  NORM    %-4d 仅引号/破折号/全角差异" % stats["norm"])
    print("  TIGHT   %-4d 归一到无空白后一致" % stats["tight"])
    print("  PREFIX  %-4d 截断引文，分段已核验" % stats["prefix"])
    print("  MULTI   %-4d 多段引文，各段均已核验" % stats["multi"])
    print("  PARTIAL %-4d 有实质性分段未核验" % stats["partial"])
    print("  MISS    %-4d 未在任何证据文件中定位" % stats["miss"])
    print("  UNDECIDED %-2d 候选文件超出预算被截断且未命中（**不等于未命中**，需人工或加大预算）"
          % stats["undecided"])
    print("  NOT_QUOTE %-2d 去掉链接/标记后正文不足，根本不是引文（不计为失败）"
          % stats["not_quote"])
    if stats["self_ref"]:
        print("  SELF_REF  %-2d **命中来自工具自身产物**（自证），一律不算通过"
              % stats["self_ref"])
    if stats["miss"] or stats["partial"] or stats["self_ref"]:
        print("\n未命中不必然是伪造 —— 常见真因：引文取自报告正文而非证据文件、"
              "引文经人工节译、或证据文件确实缺失。请逐条人工复核。")

    if args.json_out:
        payload = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "targets": [os.path.relpath(t, ROOT) for t in targets],
            "evidence_root": os.path.relpath(args.evidence, ROOT),
            "corpus": {"text_files": len(files), "pdfs": len(pdfs)},
            "stats": stats,
            "total": len(cits),
            "skipped": {"non_english": skipped_cjk, "too_short": skipped_short},
            "aliases": {os.path.relpath(k, ROOT): [os.path.relpath(x, ROOT) for x in v]
                        for k, v in alias.items()},
            "citations": [],
        }
        for status, c, r, info in rows:
            item = {"status": status,
                    "target": os.path.relpath(c.path, ROOT),
                    "line": c.line, "label": c.label,
                    "quote": info["display"],
                    "truncated": info["truncated"],
                    "multipart": info["multipart"],
                    "parts": [pt for pt, _v in info["parts"]],
                    "declared_sources": c.declared,
                    "context": c.ctx}
            if r is not None and "file" not in r:
                item["undecided"] = True
                item["capped"] = bool(r.get("capped"))
            elif r is not None:
                item["match"] = {
                    "tag": r["tag"], "form": r["form"],
                    "file": os.path.relpath(r["file"], ROOT),
                    "offset": r["offset"],
                    "declared_ok": bool(r.get("declared_ok")),
                    "cjk_glue_required": bool(r.get("cjk")),
                    "missing_segments": r["partial"],
                    "weak_segments": r.get("weak", []),
                }
                if r["form"] == "txt.raw":
                    item["match"]["line_in_source"] = \
                        r["text"].count("\n", 0, r["offset"]) + 1
            else:
                item["nearest"] = [
                    {"lcs": ln, "file": os.path.relpath(p, ROOT), "fragment": frag}
                    for ln, p, frag in (info.get("lcs") or [])]
            payload["citations"].append(item)
        try:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            print("\n报告已写入：%s" % os.path.relpath(args.json_out, ROOT))
        except OSError as exc:
            sys.stderr.write("写报告失败：%s\n" % exc)

    return 1 if (stats["miss"] or stats["partial"] or stats["undecided"]) else 0


if __name__ == "__main__":
    sys.exit(main())
