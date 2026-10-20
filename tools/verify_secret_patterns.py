#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_secret_patterns.py —— 仓内文本凭据形态扫描

**为什么需要它**：现有三道闸都管不到「已跟踪文本文件里写进凭据形态」——
`tools/agent/tools.mjs` 的 secretGuard 只管 agent 运行时 shell；
`verify_download_governance.py` 的 DG-3 管已跟踪二进制/PII；
`verify_depad.py` 只管 +4096 填充。

**判据：按形态扫，不按名字扫。**
`app_secret` 这类配置键名在已跟踪文件里大量存在；按名字扫会大面积误报。
本文件只认四种可执行形态：

  1. 完整私钥块（BEGIN 到同标签 END；只有 BEGIN 不算）
  2. 云密钥：AKIA… / ghp_… / sk-…
  3. Bearer 后接 ≥24 位随机串
  4. ~/.dsh/credentials 的读取操作（cat / open( / read_text(）

**没有 allowlist。** 误报只用行内上下文排除，不做文件级豁免。

退出码：
  0 全过（或 --controls 全过）
  1 有红
  2 未测（git 不可用 / 0 个文本文件 / 扫描器自身异常）

用法：
  python3 tools/verify_secret_patterns.py
  python3 tools/verify_secret_patterns.py --controls
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = (".git/", ".venv/", "node_modules/", ".vendor/")

# 1) 完整私钥块：BEGIN 与 END 必须同标签，且成块出现。
PRIVATE_KEY = re.compile(
    r"-----BEGIN ([A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?)-----"
    r"[\s\S]*?"
    r"-----END \1-----"
)
# 2) 云密钥
CLOUD_PATTERNS = (
    ("aws_access_key", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("github_token", re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9])")),
    ("sk_token", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}")),
)
# 3) Bearer ≥24 位随机串；排除明显的模板占位。
BEARER = re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{24,})")
BEARER_PLACEHOLDER = re.compile(
    r"(\$\{|<|>|REDACTED|PLACEHOLDER|YOUR_|TOKEN|\.\.\.|\*{3,})", re.I)
# 4) 读凭据路径
CRED_PATH = r"(?:~|/Users/[^/\s]+)/\.dsh/credentials"
CRED_READ = (
    ("shell_read", re.compile(
        r"\b(?:cat|less|more|head|tail|grep|sed|awk|cp|scp|rsync)\b[^\n]*"
        + CRED_PATH, re.I)),
    ("python_read", re.compile(
        r"\b(?:open|read_text|read_bytes)\s*\([^)\n]*" + CRED_PATH, re.I)),
)


def _mask(value, head=4, tail=2):
    """不在报告里复述完整凭据。"""
    s = str(value)
    if len(s) <= head + tail:
        return "*" * len(s)
    return s[:head] + "…" + s[-tail:]


# 行内上下文：文档在讲「不要/不许读」时，命令本身不是执行点。
NEGATIVE_CONTEXT = re.compile(
    r"没有任何一行代码(?:在)?拦住?|不许读|禁止|不要写|红线|策略边界|白名单|未治理|缺口",
    re.I)
# 行内上下文：测试夹具有意放入的假样本（不是文件级豁免）。
FIXTURE_CONTEXT = re.compile(
    r"POSITIVE\s*=|NEGATIVE\s*=|fixture|test sample|测试样本", re.I)


def _context_skips(lines, idx):
    line = lines[idx]
    if NEGATIVE_CONTEXT.search(line):
        return True
    window = "\n".join(lines[max(0, idx - 5):idx + 1])
    return bool(FIXTURE_CONTEXT.search(window))


def scan_text(text, *, path="<text>"):
    """扫描一段文本，返回 [{path,line,kind,sample}]。"""
    findings = []
    if not isinstance(text, str):
        return findings
    lines = text.splitlines()
    for m in PRIVATE_KEY.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        findings.append({"path": path, "line": line, "kind": "private_key",
                         "sample": "完整 %s 块" % m.group(1)})
    for idx, line in enumerate(lines):
        if _context_skips(lines, idx):
            continue
        for kind, pat in CLOUD_PATTERNS:
            for m in pat.finditer(line):
                findings.append({"path": path, "line": idx + 1,
                                 "kind": kind,
                                 "sample": _mask(m.group(0))})
        for m in BEARER.finditer(line):
            token = m.group(1)
            if BEARER_PLACEHOLDER.search(token):
                continue
            findings.append({"path": path, "line": idx + 1,
                             "kind": "bearer_token",
                             "sample": _mask(token)})
        for kind, pat in CRED_READ:
            if pat.search(line):
                findings.append({"path": path, "line": idx + 1,
                                 "kind": kind,
                                 "sample": "读取 ~/.dsh/credentials"})
    return findings


def git_ls_files():
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    files = out.stdout.decode("utf-8", "replace").split("\0")
    return [f for f in files if f]


def _is_skipped(rel):
    return any(rel.startswith(d) or ("/" + d) in ("/" + rel) for d in SKIP_DIRS)


def scan_repo():
    files = git_ls_files()
    if files is None:
        return None, [], 0
    scanned = 0
    findings = []
    for rel in files:
        if _is_skipped(rel):
            continue
        full = os.path.join(ROOT, rel)
        try:
            with open(full, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        if b"\x00" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        findings.extend(scan_text(text, path=rel))
    return files, findings, scanned


def controls():
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # ★ 夹具**运行时拼装**，文件里不留完整形态 —— 否则扫描器会扫到自己。
    #   这不是豁免：拼出来的字符串与真私钥块**逐字相同**，对照组照样会红。
    #   第一次提交时它还是 untracked（`git ls-files` 看不见），所以 0 红；
    #   入库后开始扫自己，5 条全中 —— 一个把自己的夹具当成真凭据的扫描器，
    #   会让人立刻开始忽略它（AGENTS.md §2.1.1）。
    _B, _E = "-----BEGIN ", "-----END "
    _K = "RSA PRIVATE KEY-----"
    fake_key = (_B + _K + "\n"
                "MIIBOgIBAAJBAKfakefakefakefakefakefakefakefakefakefakefake\n"
                + _E + _K + "\n")
    f = scan_text(fake_key)
    ok("正样本：完整私钥块 → 红", any(x["kind"] == "private_key" for x in f), str(f))

    clean_config = 'app_secret: "<redacted>"\nclient_secret: ""\n'
    ok("负样本：配置键名无值 → 绿", scan_text(clean_config) == [], str(scan_text(clean_config)))

    ok("负样本：文件名含 token 但内容干净 → 绿（只扫内容）",
       scan_text("VALUE = 1\n", path="pycparser/ply/ctokens.py") == [], "")

    doc = "文档说明：不要写 " + _B + "PRIVATE KEY" + _K + " 这种块。\n"
    ok("负样本：文档提到 BEGIN PRIVATE KEY 但无 END → 绿",
       scan_text(doc) == [], str(scan_text(doc)))

    cloud = "AKIA" + "ABCDEFGHIJKLMNOP" + "\n"
    ok("正样本：AKIA + 16 位 → 红",
       any(x["kind"] == "aws_access_key" for x in scan_text(cloud)), "")

    bearer = "Authorization: Bearer " + "abcdefghijklmnopqrstuvwx" + "\n"
    ok("正样本：Bearer + 24 位 → 红",
       any(x["kind"] == "bearer_token" for x in scan_text(bearer)), "")

    # 同上：夹具运行时拼装，文件里不留可照抄的命令形态。
    cred = "cat " + "~/.dsh/" + "credentials" + "/lark.json\n"
    ok("正样本：cat 读 credentials → 红",
       any(x["kind"] == "shell_read" for x in scan_text(cred)), "")

    placeholder = "Authorization: Bearer ${TOKEN_PLACEHOLDER}\n"
    ok("负样本：Bearer 模板占位 → 绿", scan_text(placeholder) == [], "")

    failed = [c for c in checks if not c[1]]
    for name, good, detail in checks:
        print("%s %s%s" % ("✓" if good else "✗", name,
                           "" if good else " —— " + detail))
    print("\n%s %d/%d 项通过"
          % ("✅" if not failed else "❌", len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main():
    if "--controls" in sys.argv:
        return controls()

    result = scan_repo()
    if result is None:
        print("⚠ 未测 · git ls-files 不可用，无法确定扫描范围；未测不是通过",
              file=sys.stderr)
        return 2
    files, findings, scanned = result
    if scanned == 0:
        print("⚠ 未测 · git ls-files 返回 0 个可读文本文件；未测不是通过",
              file=sys.stderr)
        return 2

    print("扫描 %d 个已跟踪文本文件（git ls-files 共 %d）" % (scanned, len(files)))
    if findings:
        for f in findings:
            print("  ❌ %s:%d [%s] %s"
                  % (f["path"], f["line"], f["kind"], f["sample"]))
        print("\n❌ 有 %d 条凭据形态命中" % len(findings))
        return 1
    print("✅ 0 条凭据形态命中")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("⚠ 未测 · 扫描器自身异常：%s: %s"
              % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(2)
