#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mutprobe.py — 变异探针：证明某个验收器的某条断言**真的拦得住东西**。

## 为什么要这个工具

验收表里的 `passed` 有两种含义，而它们在读数里长得一模一样：

  · 判据有执行点，改坏了会红      ← 真的
  · 验证器跑了、输出也绿，但那条判据根本没被断言 ← 假绿

审计读代码能猜出来，但猜不是证据。**变异是唯一能让「覆盖」这件事可复现的做法**：
把生产代码按判据原文改坏一处，看验证器红不红。

## 三态（与全项目约定一致，但它有五种）

    0  killed    变异被抓住 —— 这条判据有活着的执行点
    1  survived  变异没被抓住 —— **假绿**，该回退
    2  untested  说不清 —— 变异没应用上 / 命令没跑起来 / 红了但不是断言抓的

★ **`crashed` 归在 untested，不归在 killed。** 这是本工具最要紧的一条判据：
  变异把代码改成 `NameError`，验证器当然退非零 —— 但那是**导入/运行时崩溃**，
  不是「断言拦住了」。把它算成 killed，等于用「改坏了会崩」冒充「改坏了会被检出」。
  区分方法：输出里有 `Traceback (most recent call last)` 就不算 killed。
  （本项目已栽过两次同形状：§2.4.4 的自证改写状态、§2.4.6 的跳过无人补跑。）

## 为什么必须只改它声明的那一支

我在本会话里连摔两次：

  · 第一次做 `send_gateway` 变异，正则里 `已通过(?!率)` 与 `通过(?!率)` 两条
    一起被替换掉 → rc=1。**那会让我把真缺口判成「审计员报错了」。**
  · 做第二个变异时把 `kinds` 变量整句删掉 → `NameError`，不是一条红项。

所以 `old` 必须在文件里**恰好出现一次**（`count != 1` → untested），
且改完要**字节级确认真的变了**。两者任一不成立，这个变异不作数。

## 安全：不许在共享工作区里跑

主检出目录的 `.git` 是**目录**；linked worktree 的 `.git` 是**文件**。
本工具只接受后者 —— 传主检出过来直接退 2。
（这保证变异不会污染并行会话正在用的工作区。）
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

KILLED, SURVIVED, UNTESTED = "killed", "survived", "untested"
RC = {KILLED: 0, SURVIVED: 1, UNTESTED: 2}

RE_TRACEBACK = re.compile(r"^Traceback \(most recent call last\)", re.M)


class Untested(Exception):
    """说不清 —— 不等于绿，也不等于红。"""


def _guard(worktree):
    """主检出的 `.git` 是目录 → 拒绝。变异只许在 linked worktree 里做。"""
    wt = os.path.abspath(worktree)
    if not os.path.isdir(wt):
        raise Untested("worktree 不存在: %s" % wt)
    dotgit = os.path.join(wt, ".git")
    if os.path.isdir(dotgit):
        raise Untested(
            "拒绝在共享工作区里跑变异：%s 的 .git 是目录（主检出）。"
            "并行会话正在用它，改这里会让它们收到假红。" % wt)
    if not os.path.isfile(dotgit):
        raise Untested("既不是 git 检出也不是 linked worktree（无 .git）: %s" % wt)
    return wt


def apply_mutation(wt, mut):
    """应用一处变异，返回 (path, original_bytes)。改不动就抛 Untested。

    ★ 三件必须成立，缺一件这个变异就不作数：
      ① `old` 在文件里**恰好出现一次**（出现 0 次=没这个对象；2 次=改宽了）
      ② 写完**字节级确认变了**
      ③ `new` 确实进了文件
    """
    rel = mut.get("file")
    old = mut.get("old")
    new = mut.get("new")
    if not rel or old is None or new is None:
        raise Untested("变异缺少 file/old/new 之一: %r" % (mut,))
    path = os.path.join(wt, rel)
    if not os.path.isfile(path):
        raise Untested("变异目标不存在: %s" % rel)

    with open(path, "rb") as f:
        original = f.read()
    text = original.decode("utf-8")

    n = text.count(old)
    if n != 1:
        raise Untested(
            "`old` 在 %s 里出现 **%d 次**（必须恰好 1 次）：%r\n"
            "  → 0 次 = 这个对象不在那里；多次 = 变异会改宽，验的就不是它声明的那件事。"
            % (rel, n, old[:120]))

    mutated = text.replace(old, new)
    data = mutated.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)

    back = open(path, "rb").read()
    if back == original:
        raise Untested("写完文件字节没变（%s）—— 变异没应用上" % rel)
    if new and new.encode("utf-8") not in back:
        raise Untested("写入后找不到 `new` 片段（%s）—— 变异没应用上" % rel)
    return path, original


def run_cmd(wt, cmd, timeout):
    # ★★ 必须关掉字节码缓存 —— 这里是本项目踩过的老坑，而且**变异工具会把它放大**。
    #
    #   pyc 的失效判据是 `(mtime, size)` 这一对。而变异最典型的形式恰恰是
    #   **等长、同秒**的替换（`return 1 + 1` → `return 1 + 3`，10 字节 → 10 字节）。
    #   两个数都撞上 → Python 认定缓存有效 → **继续执行变异前的字节码** →
    #   命令退 0 → 本工具判 `survived` → **我把一条真有断言的行判成假绿**，
    #   然后去回退它。这是「误报」里最坏的一种：它会让人删掉真的东西。
    #
    #   这不是假设：本工具的自证 S1 第一次跑就是这个结果（rc=0、survived），
    #   而我一开始以为是自己判据写错了。
    #
    #   两道一起上：
    #     ① `PYTHONDONTWRITEBYTECODE=1` —— 不写新的 pyc
    #     ② `PYTHONPYCACHEPREFIX` 指向每次运行独立的空目录 —— **读不到旧的 pyc**
    #   ★ 只有 ① 不够：`-B` 与 `PYTHONDONTWRITEBYTECODE` 都**只禁写、不禁读**。
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="mutprobe-pyc-")
    try:
        r = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True,
                           text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise Untested("命令超时 %ss —— 没测完，不是红" % timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


RE_FILE_FRAME = re.compile(r'^\s+File "([^"]+)", line \d+', re.M)


def _last_frame(output):
    """Traceback 里**最后一个** File 帧 —— 也就是真正抛异常的那一处。"""
    frames = RE_FILE_FRAME.findall(output)
    return frames[-1] if frames else None


def judge(rc, output, mutated_paths=()):
    """命令结果 → 三态。**崩溃不算抓住。**

    ★ 这里有个我一开始写错的地方，值得留在这里：
      `Traceback` 这个形状本身分不出三种完全不同的情况 ——
        ① 验收器的 `assert` 失败了          → 这是 killed（我们的目标）
        ② 变异把生产代码改崩了（NameError） → 这不是 killed
        ③ 变异写出语法错误（SyntaxError）   → 这也不是 killed
      三者的输出**都以 `Traceback (most recent call last)` 开头**。
      所以判据不能是「有没有 Traceback」，而是**最后一帧落在哪个文件**：
        · 落在被变异的文件里 → 那是②③，变异自己崩了，不算抓住
        · 落在别处（验收器/harness）→ 那是①，验收器发现不对了，算 killed
    """
    if rc == 0:
        return SURVIVED, "变异后命令仍退 0 —— 这条判据没有活着的执行点"
    if not RE_TRACEBACK.search(output):
        # 绝大多数验收器是「打印 ✗ 再 exit 1」，根本不抛异常。
        return KILLED, "变异后命令退 %d 且无 Traceback —— 有断言拦住了它" % rc
    frame = _last_frame(output)
    if frame and mutated_paths and any(
            os.path.realpath(frame) == os.path.realpath(p) for p in mutated_paths):
        return UNTESTED, ("变异后命令退 %d，但崩溃点在**被变异的文件**里（%s）—— "
                          "那是改崩了，不是断言抓住了。不算 killed。" % (rc, frame))
    return KILLED, ("变异后命令退 %d，崩溃点在验收器一侧（%s）—— "
                    "是它自己的断言抓住了" % (rc, frame or "未知"))


def probe(wt, muts, cmd, timeout):
    wt = _guard(wt)
    # ★ 先跑基线：验收器本来就得是绿的，否则变异后的红说明不了任何事。
    base_rc, base_out = run_cmd(wt, cmd, timeout)
    if base_rc != 0:
        raise Untested(
            "基线（未变异）就跑不通，退出 %d —— 变异后的红无法归因于变异。输出尾部：\n%s"
            % (base_rc, "\n".join(base_out.strip().splitlines()[-8:])))

    restore = []
    mutated_paths = []
    try:
        for m in muts:
            path, original = apply_mutation(wt, m)
            restore.append((path, original))
            mutated_paths.append(path)
        rc, out = run_cmd(wt, cmd, timeout)
        return judge(rc, out, mutated_paths) + (out[-2000:], rc)
    finally:
        for path, original in restore:
            with open(path, "wb") as f:
                f.write(original)
            if open(path, "rb").read() != original:
                print("⚠️ 恢复失败，磁盘与原始字节不一致: %s" % path, file=sys.stderr)


# ───────────────────────── 自证（反向对照）─────────────────────────
#
# ★ 四条，缺一条就有一个方向恒真：
#   S1 真变异 → killed      （正向：它抓得住真变异）
#   S2 无关变异 → survived  （反向：它不会把「没抓到」也算 killed）
#   S3 old 不存在 → untested（反向：改不动的变异不许算数）
#   S4 old 出现两次 → untested（反向：改宽的变异不许算数 —— 我今晚就栽在这）
#   S5 变异导致崩溃 → untested（反向：崩溃不许冒充「断言抓住了」—— 我今晚也栽在这）

def selftest():
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    tmp = tempfile.mkdtemp(prefix="mutprobe-selftest-")
    with open(os.path.join(tmp, ".git"), "w") as f:
        f.write("gitdir: /nonexistent\n")          # 伪装成 linked worktree
    with open(os.path.join(tmp, "mod.py"), "w") as f:
        f.write("def f():\n    return 1 + 1\n"     # 可被 S5 改崩
                "def g():\n    return 2\n"
                "DUP = 'x'\nDUP = 'x'\n")
    checker = os.path.join(tmp, "check.sh")
    with open(checker, "w") as f:
        f.write("#!/bin/sh\npython3 -c 'import mod; assert mod.f()==3'\n")
    os.chmod(checker, 0o755)
    cmd = "python3 -c 'import mod; assert mod.f()==2, \"f() 变了\"'"

    def go(muts):
        try:
            return probe(tmp, muts, cmd, 60)[0]
        except Untested as exc:
            return "Untested: %s" % exc

    ok("S1 真变异（1+1 → 1+3）→ killed",
       go([{"file": "mod.py", "old": "return 1 + 1", "new": "return 1 + 3"}]) == KILLED)

    ok("S2 无关变异（g 改成 9，判据不看 g）→ survived",
       go([{"file": "mod.py", "old": "return 2", "new": "return 9"}]) == SURVIVED)

    ok("S3 old 不存在 → untested（不许算绿也不许算红）",
       str(go([{"file": "mod.py", "old": "return 42", "new": "return 1"}])).startswith("Untested"))

    ok("S4 ★ old 出现两次 → untested（改宽的变异不作数）",
       str(go([{"file": "mod.py", "old": "DUP = 'x'", "new": "DUP = 'y'"}])).startswith("Untested"))

    # S5：变异让模块崩掉 → 命令退非零，但那是 Traceback，不是断言
    crashed = go([{"file": "mod.py", "old": "def g():", "new": "def g(:"}])
    ok("S5 ★ 变异导致崩溃 → untested（崩溃不许冒充「断言抓住了」）",
       crashed == UNTESTED, str(crashed))

    ok("S6 ★ 主检出目录（.git 是目录）→ 拒绝",
       _expect_refuse() == "refused")

    passed = sum(1 for _, p, _ in results if p)
    print("=" * 70)
    print("mutprobe · 变异探针自证（反向对照）")
    print("=" * 70)
    for name, p, detail in results:
        print("  %s %-56s %s" % ("✓" if p else "✗", name, detail))
    print()
    if passed == len(results):
        print("✅ %d/%d 项全过" % (passed, len(results)))
        return 0
    print("✗ %d/%d 项通过" % (passed, len(results)), file=sys.stderr)
    return 1


def _expect_refuse():
    """对「主检出」的拒绝必须是机械的：造一个 .git 是目录的路径，看它拒不拒。"""
    fake = tempfile.mkdtemp(prefix="mutprobe-maincheck-")
    os.makedirs(os.path.join(fake, ".git"))
    try:
        _guard(fake)
        return "allowed"          # 没拒 → S6 红
    except Untested:
        return "refused"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", help="linked worktree 路径（**不许是主检出**）")
    ap.add_argument("--spec", help="变异 JSON 文件，或 - 从 stdin 读")
    ap.add_argument("--cmd", help="要跑的验收命令")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--label", default="")
    ap.add_argument("--json", action="store_true", help="输出一行 JSON")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not (a.worktree and a.spec and a.cmd):
        ap.error("需要 --worktree / --spec / --cmd（或用 --selftest）")

    raw = sys.stdin.read() if a.spec == "-" else open(a.spec, encoding="utf-8").read()
    spec = json.loads(raw)
    muts = spec if isinstance(spec, list) else [spec]

    try:
        verdict, detail, tail, rc = probe(a.worktree, muts, a.cmd, a.timeout)
    except Untested as exc:
        verdict, detail, tail, rc = UNTESTED, str(exc), "", None

    if a.json:
        print(json.dumps({"label": a.label, "verdict": verdict,
                          "detail": detail, "rc": rc}, ensure_ascii=False))
    else:
        print("【%s】%s" % (a.label or "mutprobe", verdict))
        print("  %s" % detail)
        if tail:
            print("  —— 命令输出尾部 ——")
            print("\n".join("  " + x for x in tail.strip().splitlines()[-12:]))
    return RC[verdict]


if __name__ == "__main__":
    sys.exit(main())
