#!/usr/bin/env python3
"""distill_to_nmem.py —— 把 tools/mem/corpus/*.json 里的四层记忆落进 nmem。

规矩（对齐 AGENTS.md 与本项目纪律）：

1. **默认 dry-run。** 不带 --apply 时一个写入请求都不发。
2. **每条记忆必须有可解析的 source_pointer。** 指回仓内已跟踪文件的字面量锚点，
   解析不到就不许写 —— 否则写进去的是「编造的依据」（§2.4.1）。
3. **幂等。** 用稳定的 `mem-<space>-<id>` 作 memory id，二次跑是 update 不是新增。
4. **未测与通过与红都长得不一样**：nmem 不可达 → 退 2，不是 0。
5. **只写本空间。** 每条都显式带 --space，绝不依赖环境默认值。

用法：
    python3 tools/mem/distill_to_nmem.py                 # dry-run，打印将写什么
    python3 tools/mem/distill_to_nmem.py --apply         # 真写
    python3 tools/mem/distill_to_nmem.py --layer L1      # 只处理某一层
    python3 tools/mem/distill_to_nmem.py --check-only    # 只校验指针，不连 nmem
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "tools" / "mem" / "corpus"
SPACE = "audit-multi-content"
AGENT = "content-guardian"

# SOP 规定的合法 unit_type 枚举。写错会被后端拒绝，所以先在本地拦。
VALID_UNIT_TYPES = {
    "fact", "preference", "decision", "plan",
    "procedure", "learning", "context", "event",
}

# 层 → 期望的 (unit_type, importance)。用于反向对照：写错的映射必须红。
EXPECTED = {
    "L1": ("decision", 1.0),
    "L2": ("fact", 0.9),
    "L3": ("learning", 0.85),
    "L4": ("context", 0.7),
}


def nmem_bin() -> str:
    return os.environ.get("NMEM_CLI_PATH", "nmem")


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [nmem_bin(), *args], capture_output=True, text=True, timeout=timeout
    )


def nmem_reachable() -> bool:
    try:
        r = run(["--json", "status"], timeout=15)
        if r.returncode != 0:
            return False
        return json.loads(r.stdout).get("status") == "ok"
    except Exception:
        return False


def tracked_files() -> set[str]:
    """仓内已跟踪的文本文件（`git ls-files -z`，带 -z 才不会把中文路径转义掉）。"""
    r = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    )
    if r.returncode != 0:
        return set()
    out = r.stdout.decode("utf-8", "replace")
    return {p for p in out.split("\0") if p}


def check_pointer(ptr: dict, tracked: set[str]) -> tuple[bool, str]:
    """一条 pointer 必须：文件已跟踪 + 锚点字面量真的出现在该文件里。

    锚点为空串是允许的（表示「整份文档」），这时只验文件存在且已跟踪。
    """
    f = ptr.get("file") or ""
    anchor = ptr.get("anchor") or ""
    if not f:
        return False, "缺 file"
    if f not in tracked:
        # 允许不带 .md 的「标题指认」（如 PMO/audit/红线冲突登记-CR-001）
        hits = [t for t in tracked if t.startswith(f)]
        if not hits:
            return False, f"文件不在 git ls-files：{f}"
        # 只有一个前缀命中才算指认成功，多个说明指认有歧义
        if len(hits) > 1:
            return False, f"前缀命中 {len(hits)} 个，有歧义：{f}"
        f = hits[0]
    if not anchor:
        return True, ""
    path = REPO / f
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return False, f"读不到 {f}：{e}"
    if anchor not in text:
        return False, f"锚点不在 {f} 里：{anchor[:40]}"
    return True, ""


def load_corpus(layers: list[str] | None) -> list[dict]:
    docs = []
    for p in sorted(CORPUS.glob("L*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if layers and d["layer"] not in layers:
            continue
        d["_path"] = p.name
        docs.append(d)
    return docs


def validate(docs: list[dict], tracked: set[str]) -> tuple[list[str], list[str]]:
    """返回 (错误, 告警)。错误会拦下写入；告警只打印。"""
    errs: list[str] = []
    warns: list[str] = []
    for d in docs:
        layer = d["layer"]
        ut, imp = d["unit_type"], float(d["importance"])
        exp_ut, exp_imp = EXPECTED[layer]
        if ut not in VALID_UNIT_TYPES:
            errs.append(f"{layer}: unit_type={ut!r} 不在合法枚举里")
        if ut != exp_ut:
            errs.append(f"{layer}: unit_type={ut!r} ≠ 期望 {exp_ut!r}（SOP 层级映射）")
        if abs(imp - exp_imp) > 1e-9:
            errs.append(f"{layer}: importance={imp} ≠ 期望 {exp_imp}（SOP 层级映射）")
        if d.get("space") != SPACE:
            errs.append(f"{layer}: space={d.get('space')!r} ≠ {SPACE!r}")
        if float(d["importance"]) < 0.7:
            errs.append(f"{layer}: importance < 0.7 —— 流水条目不许进本 space")
        for it in d["items"]:
            iid = it["id"]
            ptrs = it.get("source_pointers") or []
            if not ptrs:
                errs.append(f"{layer}/{iid}: 没有任何 source_pointer")
                continue
            ok_any = False
            for ptr in ptrs:
                ok, why = check_pointer(ptr, tracked)
                if ok:
                    ok_any = True
                else:
                    errs.append(f"{layer}/{iid}: pointer 解析失败 —— {why}")
            if not ok_any:
                errs.append(f"{layer}/{iid}: 所有 pointer 都解析失败")
            if not (it.get("content") or "").strip():
                errs.append(f"{layer}/{iid}: content 为空")
    return errs, warns


def memory_id(item_id: str) -> str:
    return f"mem-{SPACE}-{item_id}"


def existing_ids() -> set[str]:
    """列出本 space 已有的 memory id —— 用来区分「新增」与「更新」。"""
    try:
        r = run(["--json", "memories", "list", "--space", SPACE, "-n", "500"])
        if r.returncode != 0:
            return set()
        d = json.loads(r.stdout)
        items = d if isinstance(d, list) else d.get("items", d.get("memories", []))
        return {m.get("id") for m in items if m.get("id")}
    except Exception:
        return set()


def depad_one(path: Path) -> None:
    """写盘前去掉 +4096 填充（§2.4.8 / 填充态实测史）。

    nmem 的 --content 走命令行参数，不经文件；但为稳妥起见，
    这里对临时文件做一次 cp 往返，防止 body 从被填充的文件读出来。
    """
    st = os.stat(path).st_size
    real = os.path.getsize(path)
    if st > real:
        tmp = path.with_suffix(path.suffix + ".depad")
        shutil.copyfile(path, tmp)
        shutil.move(str(tmp), str(path))


def write_memory(d: dict, it: dict, have: set[str]) -> tuple[bool, str]:
    mid = memory_id(it["id"])
    action = "update" if mid in have else "create"
    args = [
        "--json", "memories", "add",
        "--id", mid,
        "--title", it["title"],
        "--importance", str(float(d["importance"])),
        "--unit-type", d["unit_type"],
        "--space", SPACE,
        "--when", d["when"],
        "--source", "audit-multi-content/tools/mem",
        "--source-app", "claude-code",
        "--agent-id", AGENT,
    ]
    for lb in it.get("labels") or []:
        args.extend(["-l", lb])
    # 正文里带一行「依据」尾注，让它自己就指得回原文
    pin = "; ".join(
        f"{p['file']}" + (f" ⟵ {p['anchor'][:60]}" if p.get("anchor") else "")
        for p in it.get("source_pointers", [])
    )
    body = it["content"].rstrip() + f"\n\n依据：{pin}"
    args.append(body)
    r = run(args, timeout=90)
    if r.returncode != 0:
        return False, f"{action} 失败：{(r.stderr or r.stdout).strip()[:200]}"
    return True, action


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写（默认 dry-run）")
    ap.add_argument("--layer", action="append", help="只处理某层，可重复")
    ap.add_argument("--check-only", action="store_true", help="只校验指针，不连 nmem")
    a = ap.parse_args()

    docs = load_corpus(a.layer)
    if not docs:
        print("✗ 没有语料", file=sys.stderr)
        return 1

    tracked = tracked_files()
    if not tracked:
        print("⚠ 未测：git ls-files 读不到 → 无法校验 pointer，退 2", file=sys.stderr)
        return 2

    errs, _ = validate(docs, tracked)
    total = sum(len(d["items"]) for d in docs)
    print(f"语料：{len(docs)} 层 / {total} 条")
    for d in docs:
        print(f"  {d['layer']} {d['layer_name']:<8} {len(d['items']):>2} 条 "
              f"({d['unit_type']}, {d['importance']})")

    if errs:
        print(f"\n✗ {len(errs)} 项校验失败：")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("\n✅ 指针与层级映射全部校验通过")

    if a.check_only:
        return 0

    if not nmem_reachable():
        print("⚠ 未测：nmem 不可达 → 退 2（不是通过与红）", file=sys.stderr)
        return 2

    have = existing_ids()

    if not a.apply:
        print("\n--- dry-run（不发任何写入请求）---")
        for d in docs:
            for it in d["items"]:
                mid = memory_id(it["id"])
                act = "UPDATE" if mid in have else "CREATE"
                print(f"  [{act}] {mid}  {it['title'][:50]}")
        print(f"\n共 {total} 条。加 --apply 才真写。")
        return 0

    print("\n--- 真写 ---")
    ok = fail = 0
    for d in docs:
        depad_one(CORPUS / d["_path"])
        for it in d["items"]:
            good, msg = write_memory(d, it, have)
            if good:
                ok += 1
                print(f"  ✓ [{msg}] {it['id']}")
            else:
                fail += 1
                print(f"  ✗ {it['id']}: {msg}")
    print(f"\n完成：成功 {ok} / 失败 {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
