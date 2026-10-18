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


def run_row(row):
    if not row["test_id"] or not row["fixture"] or not row["command"]:
        return "untested", "缺 test_id/fixture/command"
    if not os.path.exists(row["fixture"]):
        return "untested", "fixture 不存在: %s" % row["fixture"]
    # 命令经 T0-08 沙箱运行：临时 cwd / env 白名单 / rlimit / 墙钟超时 / 禁网包装。
    code = ("import subprocess,sys\n"
            "sys.exit(subprocess.call(%r, shell=True))" % row["command"])
    try:
        res = run_untrusted(
            code, timeout=10, cpu_seconds=5,
            memory_bytes=512 * 1024 * 1024,
            file_size_bytes=10 * 1024 * 1024)
    except Exception as exc:  # noqa: BLE001
        return "untested", "sandbox 无法执行: %s" % exc
    if res["timed_out"] or res["limit_hit"]:
        return "failed", "sandbox timed_out=%s limit_hit=%s" % (
            res["timed_out"], res["limit_hit"])
    if res["exit_code"] == 0:
        return "passed", ""
    return "failed", "exit=%s" % res["exit_code"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    args = ap.parse_args()

    if not os.path.isfile(args.table):
        print("UNTESTED: 验收表不存在: %s" % args.table)
        return 2
    try:
        rows = parse_table(args.table)
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收表读不出: %s" % exc)
        return 2

    counts = {"passed": 0, "failed": 0, "untested": 0}
    for row in rows:
        status, detail = run_row(row)
        counts[status] += 1
        if status != "passed":
            print("%s #%s %s %s" % (status.upper(), row["n"], row["action"], detail))
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
