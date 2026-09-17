#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_skill.py —— **规程本身**的验收器（B3.3）

## 为什么需要它

`skills/内容合规审查/SKILL.md` 的用途是「任何 agent 按这一页就能调起一次审查」。
它最大的风险不是写错，是**腐烂**：命令改了、路径挪了、参数重命名了，
而这一页还停在那里，读起来完全正常。B3.0 已经在文档数字上吃过这个亏
（手册里的「可复现命令」复现不出手册里的数，见 ADR-0013 §15.3）。

所以本脚本做一件很土但有效的事：**把规程里每一条 bash 命令抽出来，真的跑一遍。**

  命令块标记 ` ```bash ` 必须配一条**期望**注释：`# expect: ok` 或 `# expect: fail`
  （`# expect: fail` 用于规程里刻意展示「这条会被拒绝」的命令）。
  命令退出码与期望不符 → 红。

另外断言规程里承诺过的字段名真的出现在输出里 —— 光「命令跑得动」不够，
规程说的是「这样调用能得到那样的东西」。

用法：
  python3 tools/verify_skill.py
  python3 tools/verify_skill.py --verbose
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "内容合规审查", "SKILL.md")

# 规程承诺的字段：第一条命中的规则生效（顺序敏感 —— `--json` 那条必须先判，
# 否则人类可读形态的字段要求会套到 JSON 输出上，变成假红）
PROMISES = [
    ("--json", ["contract_version", "rule_keys_hit", "layer", "unknowns",
                "boundary_statement"]),
    ("judge_adapter.py --from-text", ["判定", "处置层", "边界声明"]),
    ("verify_base.py", ["基座自证"]),
    ("verify_engine_contract.py", ["验收"]),
    ("verify_kb.py", ["G1", "E1"]),
    ("audit_risk_label.py", ["还原账与生成块"]),
]

SKIP = ("<外部广告ID>", "<url_key>", "<临时文件>")


def blocks(md):
    """抽出 bash 块里的**每一条**命令。

    ★ 第一版把整块当一个命令跑：于是「含占位符就跳过」会把同块里其它**能跑**的
      命令一起跳掉 —— 最主要的两条命令因此从来没被验过。逐行抽出来之后，
      占位符只影响它自己那一行。
    """
    out = []
    for m in re.finditer(r"```bash\n(.*?)```", md, re.S):
        for ln in m.group(1).split("\n"):
            if not ln.strip() or ln.strip().startswith("#"):
                continue
            exp = re.search(r"#\s*expect:\s*(ok|fail)", ln)
            out.append((ln.strip(), exp.group(1) if exp else "ok"))
    return out


def main():
    verbose = "--verbose" in sys.argv
    md = open(SKILL, encoding="utf-8").read()
    bs = blocks(md)
    print(f"═══ 规程自证 · {os.path.relpath(SKILL, ROOT)} ═══")
    print(f"抽出 {len(bs)} 个 bash 块\n")
    bad, ran, skipped = [], 0, 0
    for i, (cmd, expect) in enumerate(bs, 1):
        if any(s in cmd for s in SKIP):
            skipped += 1
            print(f"  ⏭️  #{i} 含占位符，跳过执行：{cmd.splitlines()[0][:60]}")
            continue
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                           timeout=900)
        ok = ((p.returncode == 0) == (expect == "ok"))
        out = p.stdout + p.stderr
        miss = []
        for pat, fs in PROMISES:
            if pat in cmd:
                miss = [f for f in fs if f not in out]
                break
        mark = "✅" if ok and not miss else "❌"
        print(f"  {mark} #{i} expect={expect} exit={p.returncode}"
              f"{'　缺字段 ' + str(miss) if miss else ''}　{cmd.splitlines()[0][:64]}")
        if verbose or not ok or miss:
            for ln in out.strip().splitlines()[:6]:
                print(f"        │ {ln[:110]}")
        if not ok:
            bad.append(f"#{i} 退出码 {p.returncode}，期望 {expect}")
        if miss:
            bad.append(f"#{i} 输出里缺 {miss}")
        ran += 1
    print(f"\n跑过 {ran} 条 · 跳过 {skipped} 条（占位符）")
    if bad:
        print(f"❌ {len(bad)} 项不符：{bad}")
        return 1
    print("✅ 规程里每条命令都跑得动，且输出里真的出现了它承诺的东西")
    return 0


if __name__ == "__main__":
    sys.exit(main())
