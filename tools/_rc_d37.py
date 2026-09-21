#!/usr/bin/env python3
"""_rc_d37.py —— D37 的反向对照：往**真文件**里注入缺陷，证明判据真的会红。

绿只说明判据没响，不说明判据能响。所以每一项都：
    记 sha256 → 注入 → 跑真判据 → 断言它以**预期的那句话**报红 → 逐字节还原 → 复核 sha256

只要有一项「没红」或「红的原因不对」，本脚本退出码非 0。

用法：python3 tools/_rc_d37.py
"""

import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = "research/kb"
LEDGER = "research/governance/skeleton/legal-decisions-v1.json"

KBV = ["python3", "tools/verify_kb.py"]
ENV = ["python3", "tools/verify_engine_contract.py", "--only", "V30"]

# (说明, 文件, 旧文本, 新文本, 判据命令, 期望在输出里出现的报红特征)
CASES = [
    ("① 登记处重新裸写编号（`gaps[].id` 去掉前缀）",
     f"{KB}/缺口-v1.json", '"id": "KB-GAP-8"', '"id": "D8"',
     KBV, "缺口 id 裸写"),

    ("② 制品里把缺口编号写回裸 `D#`",
     f"{KB}/知识库-v1.json", '"缺口编号": "KB-GAP-8"', '"缺口编号": "D8"',
     KBV, "知识库-v1.json：实际"),

    ("③ 散文里新写一处裸 `〔缺口:D8〕`",
     f"{KB}/README.md", "## 一、一页纸现状", "〔缺口:D8〕\n\n## 一、一页纸现状",
     KBV, "README.md：实际"),

    ("④ 查询手册标题去掉前缀（KB-CHK-3 的计数门必须掉）",
     f"{KB}/查询手册.md", "## KB-Q-7.", "## Q7.",
     KBV, "查询手册"),

    ("⑤ 外部标准库把缺口引用写回裸 `D#`",
     f"{KB}/外部标准库-v1.json", "〔缺口:KB-GAP-10〕", "〔缺口:D10〕",
     KBV, "外部标准库-v1.json：实际"),

    ("⑥ 已答项回指一个不存在的决定（悬空回指）",
     LEDGER, '"record": "legal-decisions-v1.json · D37"',
     '"record": "legal-decisions-v1.json · D99"',
     ENV, "D99"),
]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    ok = True
    for name, rel, old, new, cmd, expect in CASES:
        p = os.path.join(ROOT, rel)
        before = sha(p)
        src = open(p, encoding="utf-8").read()

        if old not in src:
            print(f"  ❌ {name}\n     注入锚点找不到：{old[:60]!r} —— 判据没被测到")
            ok = False
            continue

        try:
            open(p, "w", encoding="utf-8").write(src.replace(old, new, 1))
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            out = r.stdout + r.stderr
            hit = expect in out
            red = r.returncode != 0
            if hit and red:
                line = next((l.strip() for l in out.splitlines() if expect in l), "")
                print(f"  ✅ {name}\n     → {line[:150]}")
            else:
                print(f"  ❌ {name}\n     退出码={r.returncode} 报红={'是' if red else '否'} "
                      f"命中预期特征={'是' if hit else '否'}")
                if not hit:
                    tail = [l for l in out.splitlines() if l.strip()][-3:]
                    print(f"     输出尾部：{tail}")
                ok = False
        finally:
            open(p, "w", encoding="utf-8").write(src)
            after = sha(p)
            if after != before:
                print(f"  ❌ {name}\n     还原失败！sha256 {before[:16]} → {after[:16]}")
                ok = False

    # 全还原之后，判据必须重新变绿 —— 否则「绿」可能只是判据坏了
    r = subprocess.run(KBV, cwd=ROOT, capture_output=True, text=True)
    green = "✅ G1 + G3 全部通过" in (r.stdout + r.stderr)
    print(f"\n  {'✅' if green else '❌'} 全部还原后 KB 验收重新全绿"
          f"（退出码 {r.returncode}）")
    ok = ok and green

    print("\n" + ("✅ 反向对照全部成立：判据真的会红，且红在预期的那一条上"
                  if ok else "❌ 反向对照未全部成立"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
