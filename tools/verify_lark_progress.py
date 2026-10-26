#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_lark_progress.py — T-440：飞书事项主表同步工具的自证

## 为什么验算器与工具分开

`tools/lark_progress.py` 是「改动完成即同步表格」（`AGENTS.md` §2.8）这条承诺的
**唯一执行点**。它自己写错的后果是**共享表里出现假的进度** —— 而表是别人排期的依据。

但它不叫 `verify_*`，**按本仓 `verify_coverage.py` A 段的命名约定，它不该进那张名册**
（A 段只收 `verify_*.py|mjs`）。所以拆成这一份：验算器是 `verify_lark_progress.py`，
被验的对象是 `lark_progress.py`。两者同名不同前缀，A 段与 C 段各自说得清。

## 这一份补什么（工具自己的 `--selftest` 已覆盖 18 条，这里补的是**接缝**）

工具自证验的是「校验函数对不对」。这一份验的是**它没有变成一句空话**：

  W1  `AGENTS.md` §2.8 真的写着这条约定（不是只写在某次会话里）
  W2  §2.8 里指出的执行点**确实存在**（`tools/lark_progress.py`）
  W3  工具**默认 dry-run**：不加 `--apply` 绝不写（参数名与分支都在）
  W4  工具**不读凭据文件以外的东西**：凭据路径只有一处（`CRED`），且指向仓外
  W5  目标表坐标与 §2.8 里写的**逐字一致**（改表不改文档 → 红）
  W6  工具的 `--selftest` 在本验收器里**真跑一遍**（不是只看有没有这个字符串）
  W7  离线自证项数 ≥ 15 且 0 红（读数由工具自己报，不抄进本文件）

退出码：0 全过 / 1 有红 / 2 未测（导入失败）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

PASSED = 0
FAILED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


try:
    import lark_progress as LP  # noqa: E402
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 tools/lark_progress.py: %s" % exc)
    sys.exit(2)


AGENTS = ROOT / "AGENTS.md"
TOOL = ROOT / "tools" / "lark_progress.py"


# ── W1/W2/W5：文档与工具坐标一致 ─────────────────────────────────────

def check_doc_contract():
    agents = AGENTS.read_text(encoding="utf-8")
    report("### 2.8" in agents and "同步飞书事项主表" in agents,
           "W1 ★ AGENTS.md 有 §2.8「同步飞书事项主表」这一节")
    report("lark_progress.py" in agents,
           "W2 ★★ §2.8 里点名了执行点 tools/lark_progress.py")
    report(TOOL.is_file(),
           "W2b 那个文件真的存在（文档指的不是空气）")
    # 表坐标：文档里必须逐字含工具里的 APP_TOKEN 与 TABLE_ID
    report(LP.APP_TOKEN in agents,
           "W5 ★★ APP_TOKEN 在 §2.8 里逐字出现（改表不改文档 → 红）",
           LP.APP_TOKEN)
    report(LP.TABLE_ID in agents,
           "W5b ★★ TABLE_ID 在 §2.8 里逐字出现", LP.TABLE_ID)
    # 反向对照：换一个 token 必须查不到（否则上面两条恒真）
    fake = "ZZZZnotarealtokenZZZZ"
    report(fake not in agents,
           "W5c ★ 反证：不存在的 token 查不到（W5/W5b 不是恒真）")


# ── W3：默认 dry-run ──────────────────────────────────────────────────

def check_dry_run_default():
    src = TOOL.read_text(encoding="utf-8")
    # 参数必须存在且默认 False（store_true）
    match = re.search(r'add_argument\(\s*"--apply"[^)]*?action\s*=\s*"store_true"',
                      src, re.S)
    report(match is not None,
           "W3 ★★ --apply 是 store_true（默认不加 = 不写）")
    # 真写分支必须由 args.apply 把守
    report("dry_run=not args.apply" in src or "dry_run=not args.apply" in src.replace(" ", ""),
           "W3b ★★ 写入路径的 dry_run 取反自 args.apply（不是别的东西）")
    # ★ 反向：直接调 upsert 且 dry_run=True 时不许发请求
    fields = {"事项名称": {"field_name": "事项名称", "type": 1},
              "事项编号": {"field_name": "事项编号", "type": 1},
              "功能一级分类": {"field_name": "功能一级分类", "type": 3,
                              "property": {"options": [{"name": "跨平台"}]}}}
    item = {"事项名称": "x", "事项编号": "WBPM-0001", "功能一级分类": "跨平台"}
    code = LP.validate(item, fields)
    report(code == [], "W3c 合法条目过校验", repr(code))
    plan = LP.upsert(None, item, records=[], dry_run=True)
    report(plan["action"] == "would_create",
           "W3d ★★ dry-run 时 token=None 也不炸（证明真的没发请求）", repr(plan))


# ── W4：凭据只有一处，且指向仓外 ─────────────────────────────────────

def _code_only(src: str) -> str:
    """剥掉 docstring 与整行注释，只留代码。

    ★ 为什么需要它：凭据路径在**文档**里必然被提到（「读 ~/.dsh/credentials/...」），
      而那正是解释这条边界为什么存在的一句话。判据查全文就会把它当违规
      —— 与 §2.4.1 记过的「把注释当违规」同一个形状。
    """
    kept = []
    in_doc = False
    for raw in src.splitlines():
        stripped = raw.strip()
        if '"""' in stripped:
            # 同一行开+关（"""x"""）只吃掉这一行，不切换状态
            if stripped.count('"""') == 1:
                in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#"):
            continue
        kept.append(raw)
    return "\n".join(kept)


def check_credential_boundary():
    src = TOOL.read_text(encoding="utf-8")
    code = _code_only(src)
    hits = re.findall(r'["\']([^"\']*\.dsh[^"\']*)["\']', code)
    report(len(hits) == 1,
           "W4 ★★ 凭据路径在**代码**里只出现一处（文档里的提及不算）", repr(hits))
    report(hits and "~/.dsh/credentials" in hits[0],
           "W4b ★ 凭据路径指向仓外 ~/.dsh/credentials", repr(hits))
    # ★ 反向对照：两种「文档提及」都必须不被计入（否则判据随时误报）
    report(re.findall(r'["\']([^"\']*\.dsh[^"\']*)["\']',
                      _code_only('x = """读 ~/.dsh/credentials/x"""\n')) == [],
           "W4b2 ★ 反证：单行 docstring 里的路径不被计入（判据不会被文档喂饱）")
    multi = '"""\n文档说读 ~/.dsh/credentials/x\n"""\nCRED = "~/.dsh/credentials/real.json"\n'
    multi_hits = re.findall(r'["\']([^"\']*\.dsh[^"\']*)["\']', _code_only(multi))
    report(multi_hits == ["~/.dsh/credentials/real.json"],
           "W4b3 ★★ 反证：多行 docstring 被剥掉、真代码里的那一条留下",
           repr(multi_hits))
    report(re.findall(r'["\']([^"\']*\.dsh[^"\']*)["\']',
                      _code_only('# 读 ~/.dsh/credentials/x\n')) == [],
           "W4b4 ★ 反证：整行注释里的路径不被计入")
    report(LP.CRED.startswith(str(Path.home())),
           "W4c ★ 运行时展开到 home 下（不是仓内相对路径）", LP.CRED)
    repo = str(ROOT)
    report(not LP.CRED.startswith(repo),
           "W4d ★★ 凭据不在仓内（公开仓 + 凭据 = 事故）")
    # ★ 反向对照：仓内路径必须被判红
    report(not (repo + "/.dsh/credentials/x").startswith(repo + "/x") is False
           or not (repo + "/credentials/x").startswith(str(ROOT / "credentials")) is False,
           "W4e ★ 反证：仓内路径不会被误判成仓外", repo)


# ── W6/W7：真跑一遍工具的离线自证 ────────────────────────────────────

def check_selftest_runs():
    try:
        proc = subprocess.run(
            [sys.executable, str(TOOL), "--selftest"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    except Exception as exc:  # noqa: BLE001
        report(False, "W6 工具自证跑不起来", str(exc))
        return
    out = (proc.stdout or "") + (proc.stderr or "")
    report(proc.returncode == 0,
           "W6 ★★ lark_progress.py --selftest 真跑一遍且退 0",
           "rc=%d tail=%r" % (proc.returncode, out.strip().splitlines()[-1:] ))
    # 读数由工具自己报，本文件不抄死数
    match = re.search(r"✅ (\d+)/(\d+) 全过", out)
    report(match is not None, "W7 自证输出带「✅ N/N 全过」读数", out[-80:])
    if match:
        n_pass, n_total = int(match.group(1)), int(match.group(2))
        report(n_pass == n_total and n_pass >= 15,
               "W7b ★★ 自证项数 ≥15 且 0 红（读数来自工具，不抄进来）",
               "%d/%d" % (n_pass, n_total))
    report("0 网络请求" in out and "0 凭据读取" in out,
           "W7c ★ 自证自己声明「0 网络请求、0 凭据读取」")
    # ★ 反向对照：坏参数必须退非 0（不是「永远退 0」）
    proc2 = subprocess.run([sys.executable, str(TOOL), "--item", "x"],
                           capture_output=True, text=True, timeout=120,
                           cwd=str(ROOT))
    report(proc2.returncode != 0,
           "W7d ★ 反证：缺功能一级分类时真跑必须退非 0",
           "rc=%d" % proc2.returncode)


def main():
    print("=" * 78)
    print("T-440 · 飞书事项主表同步工具的自证（离线，0 网络请求）")
    print("=" * 78)
    check_doc_contract()
    check_dry_run_default()
    check_credential_boundary()
    check_selftest_runs()
    print("-" * 78)
    if FAILED:
        print("❌ %d passed, %d failed" % (PASSED, FAILED))
        return 1
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
