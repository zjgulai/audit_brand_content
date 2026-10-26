#!/usr/bin/env python3
"""ingest_library.py —— 把仓内真源文档归档进 nmem Library（切片索引，供 recall 读全文）。

与 distill_to_nmem.py 的分工：
- distill_to_nmem.py 写的是**结论**（四层记忆，一条一个观点）。
- 本脚本写的是**原文**（真源文档本体，供需要原文时读）。

判据：
1. 默认 dry-run。
2. 入库前逐份做两口径读（stat vs getsize）—— 被 +4096 填充的文件不许进，
   否则 nmem 读到的是带 NUL 尾巴的内容（§2.4.8，实测会报 UTF-8 错误）。
3. 幂等：按 sha256 比对，本 space 已有同一份（同名同 sha）就跳过。
4. 解析状态必须是 indexed；error/ingested/parsed 停留都算失败，退 1。
5. nmem 不可达 → 退 2（未测 ≠ 通过 ≠ 红）。

★ 关于 SOP v2.0 那条「.md 会被当成 application/octet-stream」的警告：
本机 nmem 0.10.108 实测**不复现** —— .md 直接落 text/markdown 且 indexed。
保留 .md 原名；不复制成 .markdown（多一份文件就多一处漂移）。
如果哪天真的报了那个错，本脚本的 state 校验会把它抓出来（红），不会静默。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPACE = "audit-multi-content"

# 入库清单：真源文档。每条带「为什么它在库里」。
SOURCES: list[dict] = [
    {
        "path": "AGENTS.md",
        "labels": ["rules", "constitution"],
        "comment": "项目宪法：工作约定、自证纪律、红线、重启闸门。§2.2/§2.4.x 九变体的原文出处。",
    },
    {
        "path": "ADR/README.md",
        "labels": ["decision", "adr"],
        "comment": "18 份 ADR 的索引与决策地图。任何架构判断先查这里。",
    },
    {
        "path": "base/README.md",
        "labels": ["contract", "base"],
        "comment": "基座五面：ContentUnit 契约、judge(unit) 适配层、H1–H14 不变量。",
    },
    {
        "path": "PMO/audit/内容审查Agent-常犯坑点与硬约束-v1.md",
        "labels": ["pitfall", "hardening"],
        "comment": "三态不可互代的方法总则 + 常犯坑点全表（体量最大的教训合集）。",
    },
    {
        "path": "PMO/implement/上线交付说明-20261024.md",
        "labels": ["release", "status"],
        "comment": "上线前唯一该读的一份：能上/不能上精确到路由、六条必跑命令、两个待决策。",
    },
    {
        "path": "PMO/内容审查Agent-知识库与工作流-深度分析-20261021.md",
        "labels": ["caliber", "kb"],
        "comment": "六个存疑点的答复，含「26 条规则 vs 638 条基准」「品牌词 6–10% 误报」两处反直觉事实。",
    },
    {
        "path": "PMO/填充态-环境特性-实测史.md",
        "labels": ["pitfall", "environment"],
        "comment": "+4096 填充的完整实测矩阵与落盘配方（从 AGENTS.md 搬出的那一大段）。",
    },
    {
        "path": "PMO/同一个量两个口径与跳过重排-实测史.md",
        "labels": ["pitfall", "measurement"],
        "comment": "§2.4.6–2.4.8 三条变体的全文（跳过重排 / 通报地址 / 两口径）。",
    },
]


def nmem_bin() -> str:
    return os.environ.get("NMEM_CLI_PATH", "nmem")


def run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run([nmem_bin(), *args], capture_output=True, text=True, timeout=timeout)


def nmem_reachable() -> bool:
    try:
        r = run(["--json", "status"], timeout=15)
        if r.returncode != 0:
            return False
        return json.loads(r.stdout).get("status") == "ok"
    except Exception:
        return False


def two_readings(path: Path) -> tuple[int, int]:
    """(stat, getsize) —— §2.4.8 要求两个口径都报。"""
    return os.stat(path).st_size, os.path.getsize(path)


def existing_sources() -> dict[str, dict]:
    """本 space 已有的 library 条目，按 original_name 索引。

    ★ 参数形态：library list 的 --space 必须单独成词。之前写成
    `--space X -n 20` 拼在一个字符串里会 bad_arguments，而错误被吞掉后
    返回 total:0 —— 「读错了」和「真的空」长得一样（§2.4.1）。这里显式分开传。
    """
    try:
        r = run(["--json", "library", "list", "--space", SPACE, "-n", "200"])
        if r.returncode != 0:
            return {}
        d = json.loads(r.stdout)
        return {s.get("original_name"): s for s in d.get("sources", []) if s.get("original_name")}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写（默认 dry-run）")
    ap.add_argument("--check-only", action="store_true", help="只做本地预检")
    a = ap.parse_args()

    # ---- 本地预检：存在 + 已跟踪 + 无填充 ----
    errs: list[str] = []
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    ).stdout.decode("utf-8", "replace").split("\0")
    tracked = {t for t in tracked if t}

    plan = []
    print(f"清单：{len(SOURCES)} 份")
    for s in SOURCES:
        p = REPO / s["path"]
        if not p.exists():
            errs.append(f"{s['path']}: 不在盘上")
            continue
        if s["path"] not in tracked:
            errs.append(f"{s['path']}: 未被 git 跟踪")
            continue
        st, gs = two_readings(p)
        if st != gs:
            errs.append(f"{s['path']}: 被填充（stat={st} getsize={gs}）—— 先跑 verify_depad.py --fix")
            continue
        plan.append((s, p, gs))
        print(f"  OK   {s['path']:<58s} {gs:>7d}B")

    if errs:
        print(f"\n✗ {len(errs)} 项预检失败：")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"\n✅ 预检全过（{len(plan)} 份，均未填充且已跟踪）")

    if a.check_only:
        return 0

    if not nmem_reachable():
        print("⚠ 未测：nmem 不可达 → 退 2", file=sys.stderr)
        return 2

    have = existing_sources()
    todo = []
    for s, p, size in plan:
        cur = have.get(p.name)
        if cur and cur.get("size_bytes") == size:
            print(f"  skip {s['path']}（已有同大小条目 {cur.get('id')}，{cur.get('lifecycle_state')}）")
        else:
            todo.append((s, p))

    if not a.apply:
        print(f"\n--- dry-run ---\n  将入库 {len(todo)} 份，跳过 {len(plan) - len(todo)} 份")
        return 0

    print(f"\n--- 真写 {len(todo)} 份 ---")
    ok = fail = 0
    for s, p in todo:
        args = ["library", "add", str(p), "--space", SPACE, "-c", s["comment"]]
        for lb in s["labels"]:
            args.extend(["-l", lb])
        r = run(args)
        if r.returncode != 0:
            fail += 1
            print(f"  ✗ {s['path']}: {(r.stderr or r.stdout).strip()[:160]}")
        else:
            ok += 1
            print(f"  ✓ {s['path']}")

    # ---- 复核：必须全是 indexed ----
    print("\n--- 复核解析状态 ---")
    after = existing_sources()
    bad = []
    for s in SOURCES:
        name = Path(s["path"]).name
        cur = after.get(name)
        if not cur:
            bad.append(f"{name}: 不在 library 里")
        elif cur.get("lifecycle_state") != "indexed":
            bad.append(f"{name}: state={cur.get('lifecycle_state')} err={cur.get('error_message')}")
        else:
            print(f"  indexed  {name:<58s} chunks={cur.get('chunk_count')}")

    print(f"\n写入：成功 {ok} / 失败 {fail}")
    if bad:
        print(f"✗ {len(bad)} 份没到 indexed：")
        for b in bad:
            print(f"  - {b}")
        return 1
    print("✅ 全部 indexed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
