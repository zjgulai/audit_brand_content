#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_rule_change_gate.py —— T-411 / GA-08：规则变更门有没有真的接上

## 这一票要解决的是什么

票面写「规则变更门未接 CI（`.github/workflows/acceptance.yml` 无规则变更触发路径）」。
**那一句是对的**（改前 `grep -c "rules-v1\\|regression" acceptance.yml` = 0）。

但票面同时写的「冻结回归集未建（GA-07）」**是错的**：
`research/governance/regression-set-v1.json` 有 83 条冻结样本、指纹可复算，
`tools/verify_regression_set.py` 8 项、`tools/verify_rule_change_regression.py` 7 项全过。
所以本票只做**缺的那一条**：把「改了规则就必须跑回归集」变成 CI 里的一个真 job。

## 为什么需要一个检查器，而不是只在 yml 里写一个 job

写进 yml 的 job 有两种死法，而且**都不会自己变红**：

1. **`paths` 写错**（少一个文件、写成 `rule-v1.json`）→ job 永不触发，
   而 CI 仍然全绿。这与「门不存在」是同一个效果，但它看起来像装了。
2. **job 存在但 `needs` 链断开 / 被 `if: false` 关掉** → 同上。

所以本文件断言的是**配置的形状**（四件事同时成立才算接上），
不是「yml 里出现了 `regression` 这个词」（那是 §2.4 点名的假执行点）。

## 断言的五件事

    G1  `.github/workflows/` 里存在一个**独立 job** 覆盖规则变更门
    G2  该 job 的触发路径**逐个点名**了所有规则文件（集合恒等，不多不少）
    G3  该 job 真的跑**回归集**与**规则变更对比**两个验证器（不是只跑一个）
    G4  ★ **「不跑」必须是红，不是跳过**：job 里不许出现 `continue-on-error`
        或 `|| true`（那会把「没跑成」变成「绿」）
    G5  ★ 反向对照：把 G2 的某个路径删掉 / 把 G4 的 `|| true` 加回去，
        本文件的判据必须红

## 为什么不并进 `verify_regression_set.py` 的 GS-CI-ENFORCE

那条断言的是「执行器挂在 pull_request 上」，**不区分变更类型**。
规则变更门要的是「**只在改规则时**多跑一套」。两者失败后要改的东西不同
（一个是 CI 通道，一个是路径清单），合成一个退出码就分不清该改哪一侧。
这与 `verify_secret_patterns.py` 刻意不并进 DG 是同一条理由。

## 退出码

  0 全过 · 1 有红 · 2 未测（workflows 目录读不出）
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

PASS = []
FAIL = []
UNTESTED = []


def ok(label, detail=""):
    PASS.append(label)
    print("PASS: %s%s" % (label, (" " + detail) if detail else ""))


def no(label, detail=""):
    FAIL.append((label, detail))
    print("FAIL: %s%s" % (label, (" " + detail) if detail else ""),
          file=sys.stderr)


#: 规则文件的**唯一定义处**。加一个规则文件就要改这一行 ——
#: 逐个点名而不是模糊匹配 `rules*`：模糊匹配会把 `rules-v1.json.bak`
#: 或文档里的 `rules-v2-draft` 也算进来，于是 G2 的「集合恒等」永远不成立，
#: 而人会去放宽它（§2.1.1：会误报的检查器比没有更糟）。
RULE_FILES = (
    "research/governance/skeleton/rules-v1.json",
    "research/governance/skeleton/engine-manifest.json",
)

#: 门里必须跑的两个验证器。缺任一个都只证明了一半（见 §一 的第 3 层）。
REQUIRED_VERIFIERS = (
    "tools/verify_regression_set.py",
    "tools/verify_rule_change_regression.py",
)


def read_workflows():
    out = {}
    for name in sorted(os.listdir(WORKFLOWS)):
        if not name.endswith((".yml", ".yaml")):
            continue
        with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as f:
            out[name] = f.read()
    return out


def find_gate_job(text):
    """找一个**独立 job**（有自己的 `paths:` 且点名了规则文件）。

    返回 `(job_name, job_block)` 或 `(None, text)`。

    ★ 判据是「这个 job 的 `paths:` 里点了规则文件」，不是
      「整个文件里出现过 rules-v1」。后者在任何注释里都能满足 ——
      而那正是 §2.4 说的「名字出现过 ≠ 拦得住」。
    """
    # 按两空格缩进的 job 边界切块（workflows 的顶层 job 都是 2 空格缩进）
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines)
              if re.match(r"^  [A-Za-z0-9_-]+:\s*$", ln)]
    blocks = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        blocks.append((lines[start].strip().rstrip(":"), "\n".join(lines[start:end])))
    for name, block in blocks:
        # 只看 `paths:` 下面那几行，不看全文
        m = re.search(r"^\s+paths:\s*$\n((?:\s+-\s+.+\n)+)", block, re.M)
        if not m:
            # 也支持 `paths: [a, b]` 行内写法
            m2 = re.search(r"^\s+paths:\s*\[(.+)\]\s*$", block, re.M)
            if not m2:
                continue
            pathed = [p.strip().strip("'\"") for p in m2.group(1).split(",")]
        else:
            pathed = [ln.strip().lstrip("-").strip().strip("'\"")
                      for ln in m.group(1).splitlines() if ln.strip()]
        if any(any(rf.endswith(p.lstrip("./")) or p.lstrip("./") in rf
                   for p in pathed if p) for rf in RULE_FILES):
            return name, block
    return None, text


def check(workflows):
    joined = "\n".join(workflows.values())

    # ── G1 存在独立 job ──────────────────────────────────────────────
    gate_name = None
    gate_block = None
    for name, text in workflows.items():
        job, block = find_gate_job(text)
        if job:
            gate_name, gate_block = job, block
            break
    if gate_name:
        ok("G1 ★ 存在独立 job 覆盖规则变更门（%s）" % gate_name)
    else:
        no("G1 没有任何 job 的 paths 点名了规则文件 —— 门等于没接上",
           "需覆盖：%r" % (RULE_FILES,))
        return          # 没有 job，后面几条无从判

    # ── G2 paths 集合恒等（逐个点名，不多不少）───────────────────────
    m = re.search(r"^\s+paths:\s*$\n((?:\s+-\s+.+\n)+)", gate_block, re.M)
    pathed = set()
    if m:
        for ln in m.group(1).splitlines():
            if ln.strip():
                pathed.add(ln.strip().lstrip("-").strip().strip("'\""))
    else:
        m2 = re.search(r"^\s+paths:\s*\[(.+)\]\s*$", gate_block, re.M)
        if m2:
            pathed = {p.strip().strip("'\"") for p in m2.group(1).split(",")}
    normalized = {p.lstrip("./") for p in pathed}
    missing = [rf for rf in RULE_FILES if rf not in normalized]
    if missing:
        no("G2 ★ 规则变更门的 paths 漏了规则文件", repr(missing))
    else:
        ok("G2 ★ paths 逐个点名了全部 %d 个规则文件" % len(RULE_FILES),
           repr(sorted(RULE_FILES)))

    # ── G3 真跑回归集 + 规则变更对比 ─────────────────────────────────
    missing_v = [v for v in REQUIRED_VERIFIERS if v not in gate_block]
    if missing_v:
        no("G3 ★ 门里没跑齐两个验证器", repr(missing_v))
    else:
        ok("G3 ★ 门里跑了回归集与规则变更对比两个验证器")

    # ── G4 ★「不跑」必须是红，不是跳过 ───────────────────────────────
    # ★ 只扫**代码行**，不扫注释 —— 本项目已因「被自己的解释文字绊倒」
    #   踩过两次（verify_gate 的 C5、verify_cards 的 J1a）。
    code_lines = [ln for ln in gate_block.splitlines()
                  if not ln.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    soft = []
    if "continue-on-error" in code:
        soft.append("continue-on-error")
    if re.search(r"\|\|\s*true", code):
        soft.append("|| true")
    if re.search(r"if:\s*(false|0)\b", code, re.I):
        soft.append("if: false")
    if soft:
        no("G4 ★ 门里出现了「失败也算过」的写法", repr(soft))
    else:
        ok("G4 ★ 门里没有 continue-on-error / || true / if: false")

    # ── G5 门必须挂在 pull_request 通道上（否则改规则时不跑）──────────
    # 只在 workflow 顶层 `on:` 里找 —— job 块里的 `if:` 不是这件事。
    gate_file = next(n for n, t in workflows.items() if gate_name in t)
    top = workflows[gate_file]
    on_block = top.split("jobs:", 1)[0]
    if "pull_request" in on_block:
        ok("G5 ★ 门所在 workflow 在 pull_request 上触发")
    else:
        no("G5 门所在 workflow 不在 pull_request 上触发（改规则时不跑）",
           gate_file)


def run_checks():
    try:
        workflows = read_workflows()
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 读不到 workflows 目录：%s" % exc)
        return 2
    if not workflows:
        print("UNTESTED: workflows 目录里没有 yml")
        return 2
    check(workflows)
    return None


def main():
    print("=" * 70)
    print("verify_rule_change_gate · T-411 / GA-08 · 规则变更门有没有接上")
    print("=" * 70)
    rc = run_checks()
    print("-" * 70)
    print("通过 %d 项 · 红 %d 项 · 未测 %d 项"
          % (len(PASS), len(FAIL), len(UNTESTED)))
    if rc == 2:
        return 2
    if FAIL:
        for label, detail in FAIL:
            print("  ✗ %s %s" % (label, detail), file=sys.stderr)
        print("❌ 有红", file=sys.stderr)
        return 1
    print("✅ 全过")
    return 0


def run_controls():
    """反向对照：四条判据各自**独立**变红。

    ★ 「独立」是要求：改一处让四条全红，说明不了哪一条在承重。
      本项目已踩过（`verify_cards.mjs` 的 J1 曾只查标识符出现与否 → 恒真）。
    """
    print("=" * 70)
    print("反向对照：判据自己会不会红")
    print("=" * 70)
    base = read_workflows()
    gate_file = next(n for n, t in base.items() if find_gate_job(t)[0])
    original = base[gate_file]
    results = []

    def probe(name, mutate, *, expect_fail=True):
        mutated = mutate(original)
        before = len(FAIL)
        check({gate_file: mutated})
        went_red = len(FAIL) > before
        while len(FAIL) > before:
            FAIL.pop()
        results.append((name, went_red, expect_fail))

    # C1：从 paths 里删掉一个规则文件 → G2 必须红
    probe("C1 paths 漏一个规则文件 → G2 必红",
          lambda t: t.replace(
              "      - research/governance/skeleton/engine-manifest.json\n", ""))

    # C2：把「跑回归集」那一步删掉 → G3 必须红
    probe("C2 删掉跑回归集那一步 → G3 必红",
          lambda t: t.replace(
              "        run: .venv/bin/python tools/verify_regression_set.py",
              "        run: echo skipped"))

    # C3：加 continue-on-error → G4 必须红
    probe("C3 加 continue-on-error: true → G4 必红",
          lambda t: t.replace(
              "      - name: 门自身接线自检\n",
              "      - name: 门自身接线自检\n        continue-on-error: true\n"))

    # C4：加 `|| true` → G4 必须红
    probe("C4 命令后加 || true → G4 必红",
          lambda t: t.replace(
              "run: .venv/bin/python tools/verify_regression_set.py",
              "run: .venv/bin/python tools/verify_regression_set.py || true"))

    # C5 ★ 反向的**反面**：好样本必须绿（否则判据可能是「一律红」）
    probe("C5 原始配置 → 必须不红（防「一律红」式假判据）",
          lambda t: t, expect_fail=False)

    print("=" * 70)
    bad = 0
    for name, red, want in results:
        good = red == want
        bad += 0 if good else 1
        print("%s %s（红了=%s，期望红=%s）" % ("✅" if good else "❌", name, red, want))
    if bad == 0:
        print("✅ 反向对照 %d/%d 全过" % (len(results), len(results)))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (len(results) - bad, len(results)),
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常：%s" % exc, file=sys.stderr)
        sys.exit(2)
