#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文风禁忌扫描：把硬性句式禁忌写成正则，交付前自动过一遍。

用法:
    python3 research/distill/style_scan.py <文件或目录> [...]

禁忌清单对应 00-写作规范.md 第四节。新增条目的唯一门槛是能写成正则；
判断不了的写进「表达偏好」交给人评审。

只扫面向读者的正文（分片卡片）。写作规范、大纲这类内部工作文档不在约束范围内，
扫它们会得到一堆无需处理的命中。

扫描前剥掉三类内容，否则会误报：
    代码块      源码里本来就有这些字符
    行内代码    `file.py:12`
    「」直接引用 规范自己要引用被禁的写法

退出码 0 表示干净，1 表示有命中。
"""
import re
import sys
from pathlib import Path

BANS = [
    ("破折号", r"——", "改成逗号、句号或拆句"),
    ("省略号", r"……", "省略号只用一半 …"),
    ("不是而是", r"不是[^，。；\n]{1,14}而是", "改成正向陈述"),
    ("而不是收尾", r"而不是[^，。；\n]{0,14}[。\n]", "改成正向陈述"),
    ("同义绕过", r"而非[^，。；\n]{0,14}[。\n]", "换词绕不过去，禁的是靠否定制造对比"),
    ("评价式转述", r"(非常巧妙|很简单|非常有道理|十分精妙|相当优雅|设计得很好|非常优雅)",
     "平铺转述，不给评价"),
    ("情绪词", r"(震撼|细思极恐|刺穿|愣住|炸裂|惊艳|完美地)", "描述具体行为"),
    ("解读前置", r"(这背后其实|这背后有一个|值得注意的是|有趣的是)", "直接说判断本身"),
    ("催感悟", r"你品品", "删掉"),
    ("自我感悟", r"(我一直觉得|我想到一个词)", "删掉"),
    ("绝对路径", r"/(Users|home)/[a-zA-Z]", "正文里的路径一律相对 research/repos/"),
    ("过程性语言", r"(大纲写|大纲说|和大纲不符|按规范要求|本次任务|我负责的这一章)",
     "读者没见过大纲和规范"),
    ("空话迁移", r"(可以参考|可借鉴其思路|有一定参考价值|值得关注)", "迁移形态要具体到字段名与维度名"),
]

# 这些词出现在「未找到」「README 声称但代码中未找到」的语境里是合规的，
# 逐行判断时若该行命中下列豁免词则跳过。
EXEMPT = re.compile(r"(未找到|查不到|不存在|README 声称|文档声称|代码中未找到|前一份报告)")


def strip_noise(text: str) -> str:
    # 围栏开栅栏可以是 3 个及以上反引号（```` 用于包裹正文里自带 ``` 的引用块），
    # 闭合围栏反引号数必须 >= 开栅栏，因此开/闭要分别捕获，
    # 否则 ```` 开 + ``` 闭会被当成合法配对，把引用块后半段当正文扫（假命中）。
    text = re.sub(
        r"(`{3,})[^\n]*\n.*?\n\1`*(?=\n|$)",
        "",
        text,
        flags=re.S,
    )
    text = re.sub(r"`[^`\n]*`", "", text)
    return re.sub(r"「[^」\n]*」", "", text)


def scan(path: Path, quiet: bool = False) -> int:
    body = strip_noise(path.read_text(encoding="utf-8", errors="replace"))
    hits = 0
    for name, pattern, fix in BANS:
        for m in re.finditer(pattern, body):
            line_start = body.rfind("\n", 0, m.start()) + 1
            line_end = body.find("\n", m.end())
            line = body[line_start: line_end if line_end != -1 else len(body)]
            if EXEMPT.search(line):
                continue
            if hits == 0 and not quiet:
                print("\n%s" % path)
            hits += 1
            around = body[max(0, m.start() - 30): m.end() + 26].replace("\n", " ")
            if not quiet:
                print("  [%s] …%s…" % (name, around))
                print("           改法：%s" % fix)
    return hits


def collect(args):
    files = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)
        else:
            print("路径不存在：%s" % p)
            raise SystemExit(2)
    return files


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    files = collect(sys.argv[1:])
    total = sum(scan(f) for f in files)
    print("\n共扫 %d 个文件，命中 %d 处" % (len(files), total))
    if total:
        print("禁忌必须清零才算交付。不要用同义替换绕过正则。")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
