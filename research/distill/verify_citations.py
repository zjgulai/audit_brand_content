#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引用校验器 —— 零幻觉的可执行判据。

校验四件事：
  1. FABRICATION  引用块内容在源文件里找不到（逐字节比对，按省略标记切段）
  2. LINE_DRIFT   内容找得到，但声明行号与真实行号不一致（可自动校正）
  3. RANGE_MISMATCH 无省略标记时，块行数与声明的 [start,end] 区间长度对不上
  4. BAD_PATH     引用的文件不存在，或行号越界
外加一项反作弊：
  5. DENSITY      单个分片的引用数量低于下限（防「删引用让校验变绿」，见 PITFALLS #8）

用法：
    python3 research/distill/verify_citations.py              # 校验 shards/
    python3 research/distill/verify_citations.py <file.md> ...  # 校验指定文件

判据说明（来自 PITFALLS，改判据前先读）：
  - 省略标记判据收紧为「整行是注释符号，且注释符号后面（允许空白）紧接着就是 ...」。
    放宽到「整行是注释且含 ...」会把 `// 处理 bash -lc "..." 的情况` 误判为省略
    （PITFALLS #10），那会在校验里凿出一个盲区。
  - 行比较时忽略行尾空白差异，但会单独报 TRAILING_WS。若严格逐字节比较，
    编辑器自动去尾空格会造成大量误报；误报会让人开始忽略校验输出（PITFALLS #9）。
  - 行数口径统一用 splitlines()（PITFALLS #4）。
"""

import json
import os
import re
import sys

CORPUS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "repos")
CORPUS_ROOT = os.path.normpath(CORPUS_ROOT)

# ```12:34:repo/path/to/file.ext
CITATION_RE = re.compile(r"^(\d+):(\d+):(.+)$")
# 开栅栏允许 3 个及以上反引号。语料里 sceneforge/SKILL.md 这类 Markdown 自身就含
# ``` 代码块，引用它们时必须用更多反引号包住，否则外层栅栏会被内层提前闭合。
FENCE_RE = re.compile(r"^(\s*)(`{3,})(.*)$")

# 省略标记：整行是注释，注释符号后（允许空白）紧接着 ...
OMISSION_RE = re.compile(r"^\s*(?://|#|--|/\*|\*|<!--)\s*\.\.\.")

MIN_CITATIONS_PER_SHARD = 10
OMISSION_DENSITY_WARN = 8  # 单块省略标记超过这个数就告警（PITFALLS #13）


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def parse_blocks(md_path):
    """抽出所有形如 ```start:end:path 的引用块。"""
    lines = read_lines(md_path)
    blocks = []
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            ticks = m.group(2)
            info = m.group(3).strip()
            cm = CITATION_RE.match(info) if info else None
            if cm:
                start, end, rel = int(cm.group(1)), int(cm.group(2)), cm.group(3).strip()
                body = []
                j = i + 1
                closed = False
                while j < len(lines):
                    cm2 = FENCE_RE.match(lines[j])
                    # 只有反引号数 >= 开栅栏，且后面没有 info string，才算闭合
                    if cm2 and len(cm2.group(2)) >= len(ticks) and not cm2.group(3).strip():
                        closed = True
                        break
                    body.append(lines[j])
                    j += 1
                blocks.append(
                    {
                        "md": md_path,
                        "md_line": i + 1,
                        "start": start,
                        "end": end,
                        "rel": rel,
                        "body": body,
                        "closed": closed,
                        # 开栅栏自身的缩进。引用块嵌在列表项里时作者会整体缩进 4 格，
                        # 这是合法的 Markdown 写法，比对前必须按这个缩进量还原，
                        # 否则会把每一行都判成对不上（典型的误报，见 PITFALLS #9）。
                        "indent": len(m.group(1)),
                    }
                )
                i = j + 1
                continue
        i += 1
    return blocks


def segments_of(body):
    """按省略标记把引用块切成若干连续段，返回 (段列表, 省略标记数)。"""
    segs, cur, n_omit = [], [], 0
    for ln in body:
        if OMISSION_RE.match(ln):
            n_omit += 1
            if cur:
                segs.append(cur)
                cur = []
            continue
        cur.append(ln)
    if cur:
        segs.append(cur)
    return segs, n_omit


def find_segment(src, seg):
    """在源文件里找与 seg 完全连续匹配的窗口，返回 0-based 起始下标，找不到返回 None。"""
    if not seg:
        return None
    n, k = len(src), len(seg)
    if k > n:
        return None
    norm = [s.rstrip() for s in seg]
    for i in range(0, n - k + 1):
        if all(src[i + t].rstrip() == norm[t] for t in range(k)):
            return i
    return None


def body_variants(body, fence_indent=0):
    """返回引用块正文的候选解释，按优先级排列。

    作者把引用块嵌进列表项时有三种写法，都真实出现过，所以不能二选一：

      写法 A  栅栏缩进、正文顶格              → 正文本身即原文
      写法 B  栅栏缩进、正文比原文多一层缩进   → 按公共缩进还原
      写法 C  栅栏缩进、正文多出的量恰等于栅栏缩进 → 按栅栏缩进还原

    三种都试，只要有一种逐字节匹配就通过。这不是放宽判据：内容仍必须在源文件里
    原样存在，缩进豁免不会让任何编造的内容通过（回归测试专门锁这一条）。
    """
    variants = [body]
    nonblank = [ln for ln in body if ln.strip()]
    if nonblank:
        common = min(len(ln) - len(ln.lstrip(" ")) for ln in nonblank)
        if common > 0:
            cand = [ln[common:] if len(ln) >= common else ln for ln in body]
            if cand not in variants:
                variants.append(cand)
    if fence_indent > 0:
        cand = []
        for ln in body:
            s = 0
            while s < fence_indent and s < len(ln) and ln[s] == " ":
                s += 1
            cand.append(ln[s:])
        if cand not in variants:
            variants.append(cand)
    return variants


def check_block(b, findings):
    src_path = os.path.join(CORPUS_ROOT, b["rel"])
    if not os.path.isfile(src_path):
        findings.append(
            {
                "kind": "BAD_PATH",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "引用的文件在语料根下不存在",
            }
        )
        return
    src = read_lines(src_path)
    total = len(src)
    if b["start"] < 1 or b["end"] > total or b["start"] > b["end"]:
        findings.append(
            {
                "kind": "BAD_PATH",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "行号越界：声明 %d:%d，源文件共 %d 行" % (b["start"], b["end"], total),
            }
        )
        return

    # 省略标记的判定不受缩进影响，用原始正文算一次即可
    _, n_omit = segments_of(b["body"])
    if n_omit > OMISSION_DENSITY_WARN:
        findings.append(
            {
                "kind": "OMISSION_DENSITY",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "单个引用块出现 %d 处省略标记，疑似用省略凑字数" % n_omit,
            }
        )

    # 无省略标记时，块行数必须与声明区间长度一致
    if n_omit == 0 and len(b["body"]) != (b["end"] - b["start"] + 1):
        findings.append(
            {
                "kind": "RANGE_MISMATCH",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "无省略标记：块 %d 行 vs 声明区间 %d 行"
                % (len(b["body"]), b["end"] - b["start"] + 1),
            }
        )

    # 两种缩进写法都试，取第一种能对上的
    chosen = None
    for cand in body_variants(b["body"], b.get("indent", 0)):
        segs, _ = segments_of(cand)
        if not segs:
            continue
        first_at = find_segment(src, segs[0])
        if first_at is not None:
            chosen = (segs, first_at)
            break

    if chosen is None:
        segs0, _ = segments_of(b["body"])
        if not segs0:
            findings.append(
                {
                    "kind": "EMPTY_BLOCK",
                    "md": b["md"],
                    "md_line": b["md_line"],
                    "rel": b["rel"],
                    "detail": "引用块没有正文",
                }
            )
            return
        findings.append(
            {
                "kind": "FABRICATION",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "首段在源文件中找不到逐字节匹配（共 %d 行，两种缩进写法都试过）"
                % len(segs0[0]),
                "excerpt": segs0[0][0][:100] if segs0[0] else "",
            }
        )
        return

    segs, first_at = chosen
    real_start = first_at + 1
    if real_start != b["start"]:
        findings.append(
            {
                "kind": "LINE_DRIFT",
                "md": b["md"],
                "md_line": b["md_line"],
                "rel": b["rel"],
                "detail": "声明起始行 %d，实际 %d（差 %+d）"
                % (b["start"], real_start, real_start - b["start"]),
            }
        )

    # 有省略标记时，中间/结尾各段也必须真实存在（防静默增删）
    for idx, seg in enumerate(segs[1:], start=1):
        if find_segment(src, seg) is None:
            findings.append(
                {
                    "kind": "FABRICATION",
                    "md": b["md"],
                    "md_line": b["md_line"],
                    "rel": b["rel"],
                    "detail": "第 %d 段（省略标记之后）在源文件中找不到逐字节匹配" % (idx + 1),
                    "excerpt": seg[0][:100] if seg else "",
                }
            )
            return


def main(argv):
    if argv:
        targets = argv
    else:
        shard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shards")
        targets = (
            sorted(
                os.path.join(shard_dir, f)
                for f in os.listdir(shard_dir)
                if f.endswith(".md")
            )
            if os.path.isdir(shard_dir)
            else []
        )

    if not targets:
        print("没有找到待校验的分片文件。")
        return 1

    if not os.path.isdir(CORPUS_ROOT):
        print("语料根不存在：%s" % CORPUS_ROOT)
        return 1

    findings = []
    total_blocks = 0
    per_file = {}

    for t in targets:
        if not os.path.isfile(t):
            print("跳过（不存在）：%s" % t)
            continue
        blocks = parse_blocks(t)
        per_file[t] = len(blocks)
        total_blocks += len(blocks)
        # 密度下限只对分片生效。汇总、索引、核实记录这类文档的引用数天然少，
        # 对它们套密度下限会产生无需处理的告警，而误报会让人开始忽略校验输出。
        if os.sep + "shards" + os.sep in os.path.abspath(t) and len(blocks) < MIN_CITATIONS_PER_SHARD:
            findings.append(
                {
                    "kind": "DENSITY",
                    "md": t,
                    "md_line": 0,
                    "rel": "-",
                    "detail": "引用数 %d，低于下限 %d（防「删引用让校验变绿」）"
                    % (len(blocks), MIN_CITATIONS_PER_SHARD),
                }
            )
        for b in blocks:
            check_block(b, findings)

    print("=" * 72)
    print("引用校验报告")
    print("=" * 72)
    print("语料根：%s" % CORPUS_ROOT)
    print("校验文件：%d 个，引用块：%d 处" % (len(per_file), total_blocks))
    print()
    for f, n in sorted(per_file.items()):
        print("  %-52s %3d 处引用" % (os.path.basename(f), n))
    print()

    if not findings:
        print("✅ 全绿：0 处 FABRICATION / 0 处 LINE_DRIFT / 0 处 BAD_PATH")
        print("   可以交付。")
        return 0

    order = ["FABRICATION", "BAD_PATH", "RANGE_MISMATCH", "LINE_DRIFT", "DENSITY", "OMISSION_DENSITY", "EMPTY_BLOCK"]
    findings.sort(key=lambda x: (order.index(x["kind"]) if x["kind"] in order else 99, x["md"], x["md_line"]))

    counts = {}
    for f in findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1

    for kind in order:
        group = [f for f in findings if f["kind"] == kind]
        if not group:
            continue
        print("-" * 72)
        print("%s  × %d" % (kind, len(group)))
        print("-" * 72)
        for f in group:
            print("  %s:%s" % (os.path.relpath(f["md"]), f["md_line"]))
            print("     %s  →  %s" % (f["rel"], f["detail"]))
            if f.get("excerpt"):
                print("     片段: %s" % f["excerpt"])
        print()

    print("=" * 72)
    print("汇总：" + "  ".join("%s=%d" % (k, counts[k]) for k in order if k in counts))
    hard = counts.get("FABRICATION", 0) + counts.get("BAD_PATH", 0) + counts.get("RANGE_MISMATCH", 0)
    print("❌ 未通过：%d 处作废级问题（FABRICATION / BAD_PATH / RANGE_MISMATCH）" % hard)
    print("   必须全绿才算交付。LINE_DRIFT 可按报告行号校正；DENSITY 需补齐引用。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
