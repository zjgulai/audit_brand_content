#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_acceptance_run.py — T0-10 验收执行器（只读验收表）

解析验收表的每一行，要求同时具备：
  test_id: <id>; fixture: <path>; command: <shell command>
缺任一、或 fixture 不存在 → untested。
command 退出 0 → passed；非 0 → failed。

退出码（三态）：
  0 = 全部 passed（untested=0, failed=0）
  1 = 有 failed
  2 = 未测（无 failed，但有 untested）—— 未测 ≠ 通过 ≠ 红

不读不写验收表本身；只读解析。
"""

import argparse
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.sandbox import run_untrusted
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.sandbox: %s" % exc)
    sys.exit(2)

DEFAULT_TABLE = os.path.join(
    REPO_ROOT, "PMO", "audit",
    "验收表-v3-覆盖全部判据-20261017.md")
DEFAULT_MAP = os.path.join(
    REPO_ROOT, "tests", "acceptance", "verifier_map.json")

RE_TEST_ID = re.compile(r"test_id\s*[:=]\s*([A-Za-z0-9_.-]+)")
RE_FIXTURE = re.compile(r"fixture\s*[:=]\s*([^\s;<>]+)")
RE_COMMAND = re.compile(r"command\s*[:=]\s*(.+?)(?:;|$|<br\s*/?>)", re.I)


def parse_table(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.rstrip("\n").split("|")]
            if len(parts) < 7:
                continue
            # parts: ['', '#', 动作, 判据, 怎么验, 可验性, '']
            if not re.match(r"^\d+$", parts[1]):
                continue
            method = parts[4]
            test_id = RE_TEST_ID.search(method)
            fixture = RE_FIXTURE.search(method)
            command = RE_COMMAND.search(method)
            rows.append({
                "n": int(parts[1]),
                "action": parts[2],
                "criteria": parts[3],
                "method": method,
                "test_id": test_id.group(1) if test_id else None,
                "fixture": fixture.group(1) if fixture else None,
                "command": command.group(1).strip().strip("`") if command else None,
            })
    return rows


def load_mapping(path=DEFAULT_MAP):
    """加载「验收表行号 → 可执行验证器」映射。缺失/坏文件 → 空映射（仍三态）。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows") if isinstance(data, dict) else None
        return rows if isinstance(rows, dict) else {}
    except (OSError, ValueError):
        return {}


def _render(value):
    venv_python = os.path.join(REPO_ROOT, ".venv", "bin", "python")
    return (str(value)
            .replace("{root}", REPO_ROOT)
            .replace("{venv}", venv_python)
            .replace("{python}", sys.executable))


def apply_mapping(rows, mapping):
    """只填空缺的执行字段；行号 + criteria 必须双重匹配，避免表漂移后误接。"""
    for row in rows:
        if row.get("test_id") or row.get("fixture") or row.get("command"):
            continue
        item = mapping.get(str(row["n"]))
        if not isinstance(item, dict):
            continue
        if item.get("criteria") and item["criteria"] != row["criteria"]:
            continue
        row["test_id"] = item.get("test_id")
        row["fixture"] = _render(item.get("fixture") or "")
        row["command"] = _render(item.get("command") or "")
        # ★ 单行可覆盖沙箱上限（只在**确实需要**时用，见 run_row 的注释）
        if isinstance(item.get("timeout"), (int, float)):
            row["timeout"] = int(item["timeout"])
        if isinstance(item.get("cpu_seconds"), (int, float)):
            row["cpu_seconds"] = int(item["cpu_seconds"])
    return rows


def run_row(row):
    if not row["test_id"] or not row["fixture"] or not row["command"]:
        return "untested", "缺 test_id/fixture/command"
    if not os.path.exists(row["fixture"]):
        return "untested", "fixture 不存在: %s" % row["fixture"]
    # 命令经 T0-08 沙箱运行：临时 cwd / env 白名单 / rlimit / 墙钟超时 / 禁网包装。
    code = ("import subprocess,sys\n"
            "sys.exit(subprocess.call(%r, shell=True))" % row["command"])
    try:
        # ★ 超时按行可配：默认 10 秒，但有的验证器**全量**就是 11 秒
        #   （`verify_engine_contract.py` 实测 11.2s：226 条断言 + 三次 Node 子进程）。
        #   把默认调大不是好办法 —— 那会让真的卡死的行也多等；
        #   所以在映射里对单行声明 `timeout`，由本函数读。
        res = run_untrusted(
            code, timeout=row.get("timeout") or 10, cpu_seconds=row.get("cpu_seconds") or 5,
            memory_bytes=512 * 1024 * 1024,
            file_size_bytes=10 * 1024 * 1024)
    except Exception as exc:  # noqa: BLE001
        return "untested", "sandbox 无法执行: %s" % exc
    if res["timed_out"] or res["limit_hit"]:
        # ★ 超时 = 没测完，不是「验不过」。
        #   记成 failed 会让「跑太久」与「断言不成立」共用同一个读数，
        #   而这两件事的下一步动作完全不同（前者调 timeout / 拆断言，后者改代码）。
        return "untested", "sandbox timed_out=%s limit_hit=%s" % (
            res["timed_out"], res["limit_hit"])
    if res["exit_code"] == 0:
        return "passed", ""
    # ★ exit 2 = 未测（三态退出码的全项目约定：0 过 / 1 红 / 2 未测）。
    #   把它记成 failed 会重演「未测被报成失败」——本执行器自己的 docstring
    #   第一句就写着「未测 ≠ 通过 ≠ 红」，这里必须一致。
    if res["exit_code"] == 2:
        return "untested", "命令退 2（未测）"
    return "failed", "exit=%s" % res["exit_code"]


# ───────────────────────── 自测（三态映射）─────────────────────────
#
# ★ 这一组验的是**执行器自己的语义**，不是被验收的代码：
#   子命令退出码怎么落进 passed/failed/untested。
#
#   起因（2026-10-19，cleanup 实测）：行 69 的条件执行点退 2，
#   而 runner 把它记成 failed —— 「未测」被读成「验不过」。
#   那会让「还没测」与「测了没通过」共用同一个读数，
#   而下一步动作完全不同：前者去补环境/拆断言，后者去改代码。

def self_test() -> int:
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    here = os.path.dirname(os.path.abspath(__file__))
    probe = os.path.join(here, "verify_acceptance_run.py")

    def row_with(cmd, timeout=None, cpu=None):
        r = {"n": 999, "action": "selftest", "test_id": "selftest",
             "fixture": probe, "command": cmd}
        if timeout:
            r["timeout"] = timeout
        if cpu:
            r["cpu_seconds"] = cpu
        return r

    st, detail = run_row(row_with("python3 -c 'raise SystemExit(0)'"))
    ok("S1 退 0 → passed", st == "passed", f"{st} {detail}")

    st, detail = run_row(row_with("python3 -c 'raise SystemExit(1)'"))
    ok("S2 退 1 → failed", st == "failed", f"{st} {detail}")

    # ★ 本次修的那条
    st, detail = run_row(row_with("python3 -c 'raise SystemExit(2)'"))
    ok("S3 ★ 退 2 → untested（不是 failed）", st == "untested", f"{st} {detail}")

    st, detail = run_row(row_with("python3 -c 'raise SystemExit(3)'"))
    ok("S4 退 3 → failed（只有 2 是未测，别的非零都是红）",
       st == "failed", f"{st} {detail}")

    # ★ 超时也算未测，不算失败
    st, detail = run_row(row_with("python3 -c 'import time; time.sleep(30)'",
                                  timeout=1, cpu=1))
    ok("S5 ★ 超时 → untested（不是 failed）",
       st == "untested" and "timed_out" in detail, f"{st} {detail}")

    # fixture 不存在 / 字段缺失仍是未测
    r = row_with("true")
    r["fixture"] = os.path.join(here, "__no_such_file__.py")
    st, _ = run_row(r)
    ok("S6 fixture 不存在 → untested", st == "untested", st)

    r = row_with("true")
    r["command"] = ""
    st, _ = run_row(r)
    ok("S7 缺 command → untested", st == "untested", st)

    # ★ 单行 timeout 覆盖生效（反向对照：不给 timeout 时用默认值）
    ok("S8 映射里的 timeout 会被 apply_mapping 带进 row",
       (lambda: (
           (lambda rows: [x for x in rows if x["n"] == 78][0].get("timeout"))
           (apply_mapping(parse_table(DEFAULT_TABLE), load_mapping()))
           or 0) >= 10)(), "")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 62)
    print("verify_acceptance_run · 三态映射自测")
    print("=" * 62)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<44} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return 0
    print(f"✗ {passed}/{total} 项通过", file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--self-test", action="store_true", default=False,
                    help="跑三态映射自测（不碰验收表）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not os.path.isfile(args.table):
        print("UNTESTED: 验收表不存在: %s" % args.table)
        return 2
    try:
        rows = parse_table(args.table)
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收表读不出: %s" % exc)
        return 2

    rows = apply_mapping(rows, load_mapping())
    mapped = sum(1 for r in rows
                 if r.get("test_id") and r.get("fixture") and r.get("command"))
    counts = {"passed": 0, "failed": 0, "untested": 0}
    for row in rows:
        status, detail = run_row(row)
        counts[status] += 1
        if status != "passed":
            print("%s #%s %s %s" % (status.upper(), row["n"], row["action"], detail))
    print("mapped=%d" % mapped)
    print("passed=%d failed=%d untested=%d" % (
        counts["passed"], counts["failed"], counts["untested"]))

    if counts["failed"]:
        return 1
    if counts["untested"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 执行器自身异常: %s" % exc)
        sys.exit(2)
