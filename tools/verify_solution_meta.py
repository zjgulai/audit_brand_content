#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_solution_meta.py —— 技术方案头部那些数字，必须与文档实况一致

存在的理由：方案头曾写「12 条 critical，见 §8」，
而文档**根本没有 §8**、实际 critical 只有 9 条。
那是 AGENTS.md §2.2 第 1 条的病：**文档里的数字要算出来，不能写进去**。

判据：
  M-1  头部声称的模块数 == 实际表中的模块行数
  M-2  头部声称的判据归属行 == 实际
  M-3  头部声称的 critical 数 == 实际 `### [critical]` 标题数
  M-4  头部声称的 high 数 == 实际
  M-5  头部引用的基线 hash == Playbook 的真实 hash（前 8 位）

退出码：0 通过 / 1 不一致 / 2 读不到（未测）
"""
from __future__ import annotations
import hashlib, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOL = ROOT / "Playbook" / "技术解决方案-v1.md"
PB = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"


def main() -> int:
    if not SOL.exists() or not PB.exists():
        print("✗ 读不到文件 —— 未测，不是通过", file=sys.stderr)
        return 2
    s = SOL.read_text(encoding="utf-8")
    head = s[:4000]

    actual = {
        "模块数": len(re.findall(r"^\| \d+ \| `", s, re.M)),
        "判据归属行": len(re.findall(r"^\| `[A-Z][A-Za-z0-9\-]+` \| `", s, re.M)),
        "critical": len(re.findall(r"^### \[critical\]", s, re.M)),
        "high": len(re.findall(r"^### \[high\]", s, re.M)),
    }
    claimed = {}
    for k, pat in (("模块数", r"\|\s*模块数\s*\|\s*\*\*(\d+)\*\*"),
                   ("判据归属行", r"\|\s*判据归属行\s*\|\s*\*\*(\d+)\*\*"),
                   ("critical", r"标注的 critical\s*\|\s*\*\*(\d+)\*\*"),
                   ("high", r"另 high\s*(\d+)\s*条")):
        m = re.search(pat, head)
        claimed[k] = int(m.group(1)) if m else None

    pb_h = hashlib.sha256(PB.read_bytes()).hexdigest()[:8]
    m = re.search(r"基于的 Playbook \| `([0-9a-f]{8})", head)
    claimed_hash = m.group(1) if m else None

    bad = []
    print("=" * 58)
    print("方案头读数对拍")
    print("=" * 58)
    for k in actual:
        c, a = claimed.get(k), actual[k]
        ok = (c == a)
        print(f"  {'✅' if ok else '❌'} {k:10s} 头部 {c} / 实际 {a}")
        if not ok:
            bad.append(k)
    ok_h = (claimed_hash == pb_h)
    print(f"  {'✅' if ok_h else '❌'} 基线 hash   头部 {claimed_hash} / 实际 {pb_h}")
    if not ok_h:
        bad.append("基线hash")

    if bad:
        print(f"\n✗ {len(bad)} 项不一致：{bad}")
        return 1
    print("\n✅ 头部数字与文档实况一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
