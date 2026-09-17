#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_evidence_integrity.py — 证据文件完整性审计

背景：本项目的证据目录 `_evidence/` 下累积了上千个抓取文件。调研过程中发现
**文件名/标注与实际内容不符** 的实例（例如 R8 的 `rulefit-arxiv.txt` 实为组合
数学论文 `arXiv:0811.3652`；`ke-llm-drops.txt` 实为编程练习题生成论文）。
这类错误若被分片报告引用，就会变成**伪造引证**进入交付物。

本脚本对全部证据文件做机械核验，输出风险分级清单。它不能判断「内容是否
正确回答了研究问题」——那需要人读；但它能机械地抓出下面六类**可判定**的缺陷：

  E1  声明字节数与实际字节数不符          → 文件被替换/写坏
  E2  HTTP 4xx/5xx                        → 抓取失败却留下文件
  E3  反爬/挑战页（Just a moment / Incapsula / 请稍候）→ 假成功
  E4  HTTP 200 但正文极小（< 300B 有效文本）→ 空壳页
  E5  转录文本有效内容过少（< 5% 非空行）  → PDF/JS 壳提取失败
  E6  不同文件名内容完全相同（哈希碰撞）    → 复制粘贴导致的张冠李戴

输出：`_evidence/_integrity_report.json` + 终端摘要。退出码：有 E2/E3 级缺陷时非 0。

用法：
    python3 audit_evidence_integrity.py                 # 全量扫描
    python3 audit_evidence_integrity.py --shard R8      # 只扫某个分片
    python3 audit_evidence_integrity.py --quiet         # 只输出摘要
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
EVIDENCE = os.path.join(ROOT, "_evidence")

# 反爬 / 挑战页特征（小写匹配）
CHALLENGE_MARKERS = [
    "just a moment",
    "enable javascript and cookies to continue",
    "_incapsula_resource",
    "请稍候",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "cf-browser-verification",
    "ddos protection by",
    "verifying you are human",
    "robot check",
    "are you a robot",
]

# 抓取失败但仍留文件时的常见正文标记
FAILURE_MARKERS = [
    "page not found",
    "record not found",
    "404 not found",
    "the page you requested is unavailable",
    "does not exist",
    "pagenotfound",
]

# 站点标题 + 管道符 + 失败短语 —— 有些站点把「记录不存在」渲染成一个**看起来
# 像正常页面**的壳（标题栏是站点名），HTTP 仍是 200。实测：
#   `UvA DARE | Record not found`（R8/ck-thesis-uva.txt，文件头写 HTTP: 200）
# 单看 HTTP 状态码会误判为成功抓取，因此单独识别这个形态。
SHELL_FAILURE_RE = re.compile(
    r"[^\n|]{2,60}\|\s*(record not found|page not found|not found|"
    r"404|error|access denied)\b",
    re.I)

# 客户端渲染折叠组件的信号：正文在 JS bundle 里，未展开时不进 HTML。
# 这是最隐蔽的一类缺陷 —— HTTP 200、文件不小、看起来正常，但**关键正文缺失**，
# 而研究者容易把「结构性推断」误当成「逐字引文」写进报告。
COLLAPSED_MARKERS = [
    "expand all",
    "expand all sections",
    "show more",
    "see more",
]
# 客户端渲染痕迹：出现这些说明正文依赖 JS 才能显示
JS_RENDER_MARKERS = [
    "aac-chrome-api",
    "__next_data__",
    "__nuxt__",
    "data-reactroot",
    "ng-app",
]

HEADER_RE = re.compile(r"^([A-Z_]+):\s*(.*)$")

# 从原始 HTML 还原「可见文本」，用于 E7b 的正文回查
TAG_STRIP_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>",
                          re.S | re.I)
TAG_BLOCK_RE = re.compile(r"<[^>]+>")
MIN_BYTES_FOR_200 = 300
MIN_EFFECTIVE_RATIO = 0.05
MIN_DUP_BYTES = 2_000      # 判重的最小体量，低于此值的碰撞无意义
DUP_SMALL_MAX = 20_000     # 超过此体量的同哈希，多半是同站样板文字而非张冠李戴


def read_head(path: str, limit: int = 4096) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def parse_headers(text: str) -> dict:
    out = {}
    for line in text.splitlines()[:40]:
        m = HEADER_RE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def effective_ratio(path: str, cap: int = 400_000) -> float:
    """非空行占比 —— 用于发现「提取失败的转录文本」（大量空行）。"""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(cap).decode("utf-8", "replace")
    except OSError:
        return 0.0
    lines = raw.splitlines()
    if not lines:
        return 0.0
    nonempty = sum(1 for ln in lines if ln.strip())
    return nonempty / len(lines)


def sha1_of(path: str, cap: int = 2_000_000) -> str | None:
    try:
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            h.update(fh.read(cap))
        return h.hexdigest()
    except OSError:
        return None


def scan(shard: str | None = None, quiet: bool = False):
    base = os.path.join(EVIDENCE, shard) if shard else EVIDENCE
    if not os.path.isdir(base):
        print(f"[FATAL] 证据目录不存在：{base}")
        return 2

    files = []
    for dirpath, _dirnames, filenames in os.walk(base):
        # 跳过浏览器 profile / 缓存目录（非证据）
        if any(seg.startswith("_cfprof") or seg.startswith("_chromeprof")
               for seg in dirpath.split(os.sep)):
            continue
        for fn in filenames:
            if fn.startswith("."):
                continue
            files.append(os.path.join(dirpath, fn))
    files.sort()

    findings = defaultdict(list)
    hashes = defaultdict(list)
    total = len(files)

    for path in files:
        rel = os.path.relpath(path, EVIDENCE)
        ext = os.path.splitext(path)[1].lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            # 残留浏览器 profile 里的断链符号链接，不是证据
            continue

        # ---- E6 内容重复（对文本类文件做 sha1）----
        # 只对「有实质体量」的文件判重：空文件与错误占位页之间天然同哈希，
        # 那属于 E3/E4/E5b 的范畴，不是张冠李戴。
        if ext in (".txt", ".md", ".json", ".csv", ".tsv", ".xml") \
                and size >= MIN_DUP_BYTES:
            h = sha1_of(path)
            if h:
                hashes[h].append(rel)

        if ext not in (".txt", ".md"):
            continue  # 头部约定只适用于文本证据

        head = read_head(path)
        hdr = parse_headers(head)
        low = head.lower()

        # ---- E1 声明字节数 vs 实际 ----
        declared = hdr.get("BYTES", "")
        if declared.isdigit():
            dec = int(declared)
            # 转录文本必然小于原始抓取，只报「实际 > 声明」这种不可能的
            if size > dec * 1.05 and dec > 0:
                findings["E1_尺寸矛盾"].append(
                    f"{rel}  声明BYTES={dec} 实际={size}")

        # ---- E2 HTTP 错误 ----
        http = hdr.get("HTTP", "")
        if http and http.isdigit() and int(http) >= 400:
            findings[f"E2_HTTP{http}"].append(f"{rel}  ({size}B)")

        # ---- E3 反爬挑战页 ----
        hit = next((m for m in CHALLENGE_MARKERS if m in low), None)
        if hit:
            findings["E3_反爬挑战页"].append(f"{rel}  特征={hit!r} ({size}B)")

        # ---- E7 客户端渲染未展开（最隐蔽的一类：HTTP 200、有体量，但正文缺失）----
        # 注意：单看「.md 比 .html 小几十倍」不能证明截断 —— Amazon 这类站点 HTML 里
        # 大量是导航壳与 JS bundle。要证明截断，必须**逐个正文块回查原始 HTML**。
        #   判据 a：正文含折叠控件字样 → 折叠内内容很可能没进文本层
        #   判据 b：抽样 .md 的长正文行，回查同目录原始 .html 的可见文本，统计缺失率
        col = next((m for m in COLLAPSED_MARKERS if m in low), None)
        if http == "200" and col and size > 1_000:
            findings["E7a_折叠控件"].append(
                f"{rel}  含折叠控件={col!r} ({size}B) — 折叠内正文可能缺失")

        full = ""
        try:
            with open(path, "rb") as fh:
                full = fh.read().decode("utf-8", "replace")
        except OSError:
            pass
        if "<!-- source:" in full[:400]:
            stem = os.path.splitext(path)[0]
            rawpath = next((c for c in (stem + ".html", stem + ".raw")
                            if os.path.exists(c)), None)
            missing = checked = 0
            note = ""
            if rawpath and os.path.getsize(rawpath) < 8_000_000:
                try:
                    rawb = open(rawpath, "rb").read()
                    raw = rawb.decode("utf-8", "replace")

                    # ⚠️ 关键：现代站点把正文以**转义 JSON + 超长行**内嵌在 .html 里
                    # （Amazon 实测有单行 11,405 与 29,989 字符的行）。任何按行读取
                    # 或对行设长度上限的抽取器都会**静默丢掉这些正文**，导致
                    # 「HTML 里明明有、grep 却查不到」的假阴性。本脚本因此一律
                    # 在**整个文件字节串**上做判定，不做按行采样。
                    raw_unesc = (raw.replace("\\u003c", "<")
                                    .replace("\\u003e", ">")
                                    .replace('\\"', '"')
                                    .replace("\\n", "\n"))
                    vis = html_lib.unescape(TAG_STRIP_RE.sub(
                        " ", TAG_BLOCK_RE.sub(" ", raw_unesc)))
                    vis = re.sub(r"\s+", " ", vis)

                    # 抽「正常长度」的散文句（避开超长 JSON 行本身）
                    cands = [l.strip() for l in full.splitlines()
                             if 90 < len(l.strip()) < 400
                             and not l.strip().startswith("<!--")]
                    cands = sorted(cands, key=len, reverse=True)[:5]
                    for c in cands:
                        checked += 1
                        if re.sub(r"\s+", " ", c)[:80] not in vis:
                            missing += 1

                    # 超长行体检：是否存在按行读取会丢掉的正文
                    longest = max((len(l) for l in rawb.split(b"\n")), default=0)
                    if longest > 20_000:
                        note = f"（原始 HTML 含 {longest} 字符的超长行，按行抽取器会丢内容）"
                except OSError:
                    pass
            if checked and missing:
                findings["E7b_正文回查缺失"].append(
                    f"{rel}  抽样 {checked} 段长正文，{missing} 段在原始 "
                    f"{os.path.basename(rawpath)} 中查不到 {note}")
            elif checked:
                findings["E7c_回查通过"].append(
                    f"{rel}  抽样 {checked} 段长正文全部可在原始文件中查到 "
                    f"（.md 偏小系站点样板与 JS 所致，非截断）")

            # ---- E8 抽取件可能漏掉了内嵌 JSON 里的正文 ----
            # 若 .md 含折叠控件标题、而原始 HTML 的超长内嵌 JSON 里另有正文，
            # 说明 .md 是**不完整抽取**，引用前必须走解码件。
            if rawpath and col:
                try:
                    big = max((len(l) for l in open(rawpath, "rb")
                               .read().split(b"\n")), default=0)
                    if big > 10_000:
                        findings["E8_内嵌JSON正文未进md"].append(
                            f"{rel}  含折叠控件且原始 HTML 有 {big} 字符超长行 — "
                            f".md 疑为不完整抽取，请改用解码件或字节级检索")
                except OSError:
                    pass

        # ---- E4 HTTP200 但空壳 ----
        body = head
        if http == "200" and len(body.strip()) < MIN_BYTES_FOR_200:
            findings["E4_空壳页"].append(f"{rel}  ({size}B)")

        # ---- 抓取失败却留文件 ----
        fhit = next((m for m in FAILURE_MARKERS if m in low), None)
        if fhit:
            findings["E5b_失败页正文"].append(f"{rel}  特征={fhit!r} ({size}B)")

        # ---- E9 HTTP 200 的假壳页（标题栏样式，状态码骗人）----
        sh = SHELL_FAILURE_RE.search(full or head)
        if sh and size < 20_000:
            findings["E9_200假壳页"].append(
                f"{rel}  HTTP={http or '未标注'} 但正文含 {sh.group(0)[:60]!r} "
                f"({size}B) — 状态码不能证明内容有效")

        # ---- E5 提取失败的转录 ----
        if size > 50_000:
            r = effective_ratio(path)
            if r < MIN_EFFECTIVE_RATIO:
                findings["E5_提取失败"].append(
                    f"{rel}  非空行占比={r:.1%} ({size}B)")

    # 组装 E6：区分两种成因
    #   E6a 小体量同哈希 → 同一内容被当成两个来源，风险高（张冠李戴）
    #   E6b 大体量同哈希 → 多半是同站样板文字（导航/页脚）导致，风险中
    for h, rels in hashes.items():
        if len(rels) < 2:
            continue
        rels = sorted(rels)
        biggest = max(os.path.getsize(os.path.join(EVIDENCE, r)) for r in rels)
        key = "E6b_大文件同哈希(疑样板)" if biggest >= DUP_SMALL_MAX \
            else "E6a_小文件同哈希"
        findings[key].append(
            f"最大{biggest}B  " + "  ==  ".join(rels))

    report = {
        "scanned_files": total,
        "text_evidence": sum(1 for f in files
                             if os.path.splitext(f)[1].lower() in (".txt", ".md")),
        "findings": {k: sorted(v) for k, v in sorted(findings.items())},
        "counts": {k: len(v) for k, v in sorted(findings.items())},
    }

    out_path = os.path.join(EVIDENCE, "_integrity_report.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if not quiet:
        for k in sorted(findings):
            items = sorted(findings[k])
            print(f"\n=== {k}  ({len(items)}) ===")
            for it in items[:40]:
                print("   ", it)
            if len(items) > 40:
                print(f"    ... 另有 {len(items) - 40} 条，见 JSON")

    print(f"\n扫描文件 {total} 个（其中文本证据 {report['text_evidence']} 个）")
    print(f"风险项合计 {sum(report['counts'].values())} 条")
    for k in sorted(report["counts"]):
        print(f"  {k:22s} {report['counts'][k]:5d}")
    print(f"\n报告已写入 {os.path.relpath(out_path, ROOT)}")

    # 退出码：反爬/失败页属于「必须先修」的假成功
    fatal = (report["counts"].get("E3_反爬挑战页", 0)
             + report["counts"].get("E5b_失败页正文", 0)
             + report["counts"].get("E4_空壳页", 0))
    return 1 if fatal else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", help="只扫描某个分片目录，如 R8")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    return scan(a.shard, a.quiet)


if __name__ == "__main__":
    sys.exit(main())
