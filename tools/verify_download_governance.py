#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_download_governance.py —— 下载治理的唯一执行点（DG-1…DG-6）

## 它为什么存在

2026-10-17 红线改线：飞书内容**可以下载**（委托方原话见 AGENTS.md §2.6），
约束只剩一条：**下载物不许进公开仓**（`audit_brand_content` 是公开仓）。

第一版实现是假绿（`.ua/wf_impl_dg.js` 列了 5 个已实测漏洞）。本文件是**组装层**：
检测逻辑全部来自四个已自证过的子模块，这里一行都不复制 ——
两处就是两套，迟早各自漂移。

| 层 | 文件 | 负责 |
|---|---|---|
| 调用点（Python） | `download_scan_py.py` | AST + 轻量数据流，带 lineno/col_offset |
| 调用点（JS） | `download_scan_js.py` | 最小词法分析 |
| 登记表 | `download_registry.py` | 调用点粒度 + 完整字段 + landing_root |
| 仓内内容 | `download_blobs.py` | magic bytes / PII / 基线 sha256 / 历史提交 |

## 判据（编号与语义保留；底层换成新实现）

| # | 断言 | 底层 |
|---|---|---|
| DG-1 | 每个下载调用点都在 entries 里结构化登记（调用点粒度） | scan_py + scan_js + validate_registry |
| DG-2 | 每个登记项字段合法；landing_root 解析后在仓外且 0700 | validate_registry |
| DG-3 | `git ls-files` 里的受控内容（二进制 / PII）都有来源 | scan_tracked_blobs |
| DG-4 | **反向对照（DG-3）**：未登记二进制必须红；登记正确 sha256 后必须绿 | scan_tracked_blobs |
| DG-5 | **反向对照（DG-2）**：仓内 landing_root 必须红；仓外 0700 必须绿 | validate_registry |
| DG-6 | **反向对照（DG-1）**：未登记调用必须红；且真实扫描器必须接进来 | scan_py/scan_js + validate_registry |

DG-4…DG-6 **每次主检查都真跑**（真建临时目录、真喂样本、真看红不红），
不是文本断言；`--selftest` 另外把四个子模块自己的自证各跑一遍。

## 文件发现：只用 git ls-files

为什么不用 `os.walk`：本机 `.venv-r4` 里有 1202 个 `.py`，真代码只有 150 个
（2026-10-17 实测）。走目录会把依赖当成本仓代码，制造误报并拖慢自证。

索引里有、worktree 里暂时删掉的文件，读**索引内容**来扫 —— 索引才是
下一次提交会带上的那份；读不到才落「未测」。

## 退出码

0 通过 / 1 红 / 2 未测。有红时红优先；**未测绝不当通过**。
`--json` 出机器可读结果，字段与人类输出同源。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent

# 直接运行本文件时 sys.path[0] 就是 tools/；被 verify_feishu_index 导入时
# 不一定，所以显式补一次。四个子模块与验证器必须导入**同一份**代码。
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import download_blobs  # noqa: E402
import download_registry  # noqa: E402
import download_scan_js  # noqa: E402
import download_scan_py  # noqa: E402

DG_IDS = ("DG-1", "DG-2", "DG-3", "DG-4", "DG-5", "DG-6")

PY_EXTS = (".py",)
JS_EXTS = (".js", ".mjs", ".cjs")

# `validate_registry` 返回的是一张合并的红清单。DG-1 与 DG-2 的**整体判决**
# 是同一份（都来自同一次校验），这里只是把红按「调用点覆盖」与「字段/落盘」
# 分开展示，让报告能指出是哪一类。分类只看消息里的固定词，不重新判一次 ——
# 重新判就是第二套逻辑。分不出来的红落 DG-2（fail-closed，宁可多报）。
_DG1_RED_MARKERS = (
    "少登记",
    "多登记",
    "过期登记",
    "调用点没有被任何登记项覆盖",
    "重复登记",
    "缺调用点定位",
    "定位方式必须二选一",
    "ordinal",
    "lineno",
    "col_offset",
    "symbol 与代码不一致",
    "api_kind 与代码实际接口不一致",
    "无法唯一核对",
)


def _split_registry_reds(reds):
    dg1, dg2 = [], []
    for item in reds:
        if any(marker in item for marker in _DG1_RED_MARKERS):
            dg1.append(item)
        else:
            dg2.append(item)
    return dg1, dg2


def _split_registry_untested(items):
    """未测也分两类；分不出来就同时挡住两个 DG（不确定就不许说通过）。"""
    dg1, dg2 = [], []
    for item in items:
        # repo_root 本身坏了：两个 DG 都无从核对，谁都不许说通过。
        if "repo_root" in item:
            dg1.append(item)
            dg2.append(item)
            continue
        is_dg1 = ("calls[" in item or "calls 不是数组" in item
                  or "调用点" in item)
        is_dg2 = any(marker in item
                     for marker in ("landing_root", "realpath", "目录", "path"))
        if is_dg1 and not is_dg2:
            dg1.append(item)
        elif is_dg2 and not is_dg1:
            dg2.append(item)
        else:
            dg1.append(item)
            dg2.append(item)
    return dg1, dg2


# ---------------------------------------------------------------- 文件发现

def discover_tracked(repo_root):
    """返回 (tracked 列表, 未测说明 | None)。只用 git ls-files。"""
    try:
        run = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=str(repo_root), capture_output=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "git ls-files 跑不了（%s）—— 文件发现未测，不是通过" % exc
    if run.returncode != 0:
        return None, "git ls-files 退出码 %d —— 文件发现未测，不是通过" % run.returncode
    tracked = [item for item in run.stdout.decode("utf-8", "replace").split("\0")
               if item]
    return tracked, None


def _read_source(repo_root, rel):
    """读一个被跟踪源文件。worktree 缺失时回落到索引内容。

    为什么读索引：`git ls-files` 列的是索引条目，那是下一次提交会带上的内容。
    工作区里的临时删除不该让治理扫描变成「未测」，也不该被当成「没有这段代码」。
    """
    path = Path(repo_root) / rel
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError:
        pass
    try:
        run = subprocess.run(
            ["git", "-c", "core.quotepath=false", "show", ":" + rel],
            cwd=str(repo_root), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "%s: 工作区缺失且读不到索引内容（%s）—— 未测" % (rel, exc)
    if run.returncode != 0:
        return None, ("%s: 工作区缺失且读不到索引内容（rc=%d）—— 未测"
                      % (rel, run.returncode))
    return run.stdout.decode("utf-8", "replace"), "%s: 工作区缺失，按索引内容扫描" % rel


def collect_calls(repo_root=ROOT, tracked=None):
    """用两个扫描器产出调用点。扫描逻辑一行都不在这里。"""
    untested = []
    notes = []
    if tracked is None:
        tracked, note = discover_tracked(repo_root)
        if tracked is None:
            return {"calls": [], "tracked": [], "untested": [note], "notes": []}

    calls = []
    for rel in tracked:
        low = rel.lower()
        if low.endswith(PY_EXTS):
            src, note = _read_source(repo_root, rel)
            if src is None:
                untested.append(note)
                continue
            if note:
                notes.append(note)
            try:
                calls.extend(download_scan_py.scan_python_source(src, rel=rel))
            except (SyntaxError, ValueError) as exc:
                untested.append("%s: Python 解析失败（%s）—— 未测" % (rel, exc))
        elif low.endswith(JS_EXTS):
            src, note = _read_source(repo_root, rel)
            if src is None:
                untested.append(note)
                continue
            if note:
                notes.append(note)
            try:
                calls.extend(download_scan_js.scan_js_source(src, rel=rel))
            except Exception as exc:  # 词法器不该抛；抛了就是未测，不是零命中
                untested.append("%s: JS 词法扫描失败（%s）—— 未测" % (rel, exc))

    calls.sort(key=lambda row: (row["path"], row["lineno"], row["col_offset"],
                                row["sink"], row["api"]))
    return {"calls": calls, "tracked": tracked, "untested": untested,
            "notes": notes}


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, ValueError) as exc:
        return None, "%s 读不出（%s）—— 未测，不是通过" % (path, exc)


# ---------------------------------------------------------------- DG-1 / DG-2

def evaluate_registration(repo_root=ROOT, registry=None, registry_path=None,
                          calls=None, tracked=None):
    """DG-1 + DG-2 的联合判据。M 段 M1 直接调用这个函数。

    返回里同时带 `calls`：M 段的反向对照要拿真实调用集再注入一个假调用，
    证明同一个判据真的会红，而不是另写一条恒真断言。
    """
    root = Path(repo_root).resolve()
    scanner_untested = []
    notes = []
    if calls is None:
        collected = collect_calls(root, tracked=tracked)
        calls = collected["calls"]
        tracked = collected["tracked"]
        scanner_untested = collected["untested"]
        notes = collected["notes"]
    else:
        collected = {"tracked": tracked or [], "notes": []}

    if registry is None:
        path = Path(registry_path) if registry_path else (
            Path(root) / "tools" / "download_callers.json")
        registry, load_error = _load_json(path)
        if registry is None:
            scanner_untested.append(load_error)
            registry = {"entries": []}

    result = download_registry.validate_registry(registry, root, calls)
    all_reds = list(result.get("reds") or [])
    all_untested = scanner_untested + list(result.get("untested") or [])

    dg1_reds, dg2_reds = _split_registry_reds(all_reds)
    dg1_untested, dg2_untested = _split_registry_untested(all_untested)

    entries = registry.get("entries") if isinstance(registry, dict) else None
    n_entries = len(entries) if isinstance(entries, list) else 0

    dg1 = {
        "id": "DG-1",
        "ok": not dg1_reds and not dg1_untested,
        "reds": dg1_reds,
        "untested": dg1_untested,
        "detail": "调用点 %d 个 / 登记 %d 项 / 红 %d / 未测 %d"
                  % (len(calls), n_entries, len(dg1_reds), len(dg1_untested)),
    }
    dg2 = {
        "id": "DG-2",
        "ok": not dg2_reds and not dg2_untested,
        "reds": dg2_reds,
        "untested": dg2_untested,
        "detail": "登记 %d 项 / landing_root 与字段 / 红 %d / 未测 %d"
                  % (n_entries, len(dg2_reds), len(dg2_untested)),
    }
    return {
        "ok": dg1["ok"] and dg2["ok"],
        "reds": dg1_reds + dg2_reds,
        "untested": dg1_untested + dg2_untested,
        "DG-1": dg1,
        "DG-2": dg2,
        "calls": calls,
        "tracked": tracked or [],
        "notes": notes,
        "registry_entries": n_entries,
        # ★ download_registry 明着承认的残余：登记表字段与代码实际落盘无连接。
        #   这里原样透传，避免调用方把它误当成端到端保证。
        "connection_to_code": result.get("connection_to_code", "none"),
    }


def evaluate_dg1(*args, **kwargs):
    """只取 DG-1。M 段的反向对照与 DG-6 用。"""
    return evaluate_registration(*args, **kwargs)["DG-1"]


def evaluate_dg2(*args, **kwargs):
    """只取 DG-2。DG-5 的反向对照用。"""
    return evaluate_registration(*args, **kwargs)["DG-2"]


# ---------------------------------------------------------------- DG-3

def evaluate_dg3(repo_root=ROOT, baseline=None, baseline_path=None,
                 tracked=None, include_history=True):
    """仓内受控内容判据。扫描逻辑全部在 download_blobs。"""
    root = Path(repo_root).resolve()
    untested = []
    if tracked is None:
        tracked, note = discover_tracked(root)
        if tracked is None:
            return {"id": "DG-3", "ok": False, "reds": [],
                    "untested": [note], "detail": note, "tracked_files": 0}

    if baseline is None:
        path = Path(baseline_path) if baseline_path else (
            Path(root) / "tools" / "asset_baseline.json")
        baseline, load_error = _load_json(path)
        if baseline is None:
            untested.append(load_error)
            baseline = {"assets": {}}

    result = download_blobs.scan_tracked_blobs(
        root, tracked, baseline, include_history=include_history)
    reds = list(result.get("reds") or [])
    untested += list(result.get("untested") or [])
    return {
        "id": "DG-3",
        "ok": not reds and not untested,
        "reds": reds,
        "untested": untested,
        "detail": "已跟踪 %d 个文件 / 红 %d / 未测 %d"
                  % (len(tracked), len(reds), len(untested)),
        "tracked_files": len(tracked),
    }


# ---------------------------------------------------------------- 行为级反向对照
#
# DG-4…DG-6 每次主检查都跑。每个对照都同时喂坏样本与好样本：
# 只证明「会红」不够，还要证明「该绿时真会绿」—— 否则一个永远报红的
# 检查器也能骗过反向对照（AGENTS.md §2.1.1：误报比不报更糟）。

# 固定 PNG 头 + 少量字节：magic 嗅探只需要头部，不依赖 Pillow。
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 24

_DRIVE_ENTRY_API = "drive/v1/files/{file_token}/download"
_DRIVE_CALL_API = ("https://open.feishu.cn/open-apis/drive/v1/files/"
                   "<expr>/download")


def _temp_repo(base, files):
    """建一个只有 index、没有 commit 的临时仓库。git ls-files 认 add 过的文件。"""
    repo = Path(base) / "repo"
    repo.mkdir(parents=True)
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    run = subprocess.run(["git", "init", "-q"], cwd=str(repo),
                         capture_output=True)
    if run.returncode != 0:
        raise RuntimeError("git init 失败：%s"
                           % run.stderr.decode("utf-8", "replace")[:200])
    run = subprocess.run(["git", "add", "-A"], cwd=str(repo),
                         capture_output=True)
    if run.returncode != 0:
        raise RuntimeError("git add 失败：%s"
                           % run.stderr.decode("utf-8", "replace")[:200])
    return repo


def _valid_entry(path, symbol, landing_root, ordinal=1):
    return {
        "path": path,
        "symbol": symbol,
        "api": _DRIVE_ENTRY_API,
        "api_kind": "drive_file",
        "consumer": "selftest.consumer",
        "landing_root": str(landing_root),
        "retention": "run-scoped",
        "data_class": "internal",
        "never_tracked": True,
        "ordinal": ordinal,
    }


def _valid_call(path, symbol, lineno=3, col_offset=4):
    return {
        "path": path,
        "symbol": symbol,
        "lineno": lineno,
        "col_offset": col_offset,
        "sink": "http",
        "shape": "literal",
        "api": _DRIVE_CALL_API,
        "marker": "/download",
    }


def control_dg4():
    """DG-4（DG-3 的反向对照）：未登记二进制必须红；登记 sha256 后必须绿。"""
    with tempfile.TemporaryDirectory(prefix="dg4_") as temp:
        root = Path(temp)
        (root / "evil.txt").write_bytes(_PNG_BYTES)
        (root / "ok.txt").write_text("hello world\n", encoding="utf-8")

        bad = download_blobs.scan_tracked_blobs(
            root, ["evil.txt"], {"assets": {}}, include_history=False)
        good = download_blobs.scan_tracked_blobs(
            root, ["ok.txt"], {"assets": {}}, include_history=False)
        approved = download_blobs.scan_tracked_blobs(
            root, ["evil.txt"],
            {"assets": {"evil.txt": {
                "source": "自证固定样本",
                "approved_by": "自证",
                "sha256": hashlib.sha256(_PNG_BYTES).hexdigest(),
            }}},
            include_history=False)

        red_ok = any("evil.txt" in r and "未在 asset_baseline.json 登记" in r
                     for r in bad["reds"])
        green_ok = not good["reds"] and not good["untested"]
        approved_ok = not approved["reds"] and not approved["untested"]
        ok = red_ok and green_ok and approved_ok
        detail = ("未登记 PNG→红 %d 条；纯文本→红 %d；登记 sha256 后→红 %d"
                  % (len(bad["reds"]), len(good["reds"]),
                     len(approved["reds"])))
        return {"id": "DG-4", "ok": ok, "detail": detail,
                "reds": [] if ok else [detail],
                "untested": []}


def control_dg5():
    """DG-5（DG-2 的反向对照）：仓内 landing_root 必须红；仓外 0700 必须绿。"""
    with tempfile.TemporaryDirectory(prefix="dg5_") as temp:
        base = Path(temp)
        repo = _temp_repo(base, {"tools/probe.py": "def f():\n    pass\n"})
        outside = base / "outside"
        outside.mkdir()
        os.chmod(str(outside), 0o700)
        inside = repo / "tmp"
        inside.mkdir()
        os.chmod(str(inside), 0o700)
        call = [_valid_call("tools/probe.py", "f")]

        bad = evaluate_dg2(
            repo, registry={"entries": [_valid_entry(
                "tools/probe.py", "f", inside)]}, calls=call)
        good = evaluate_dg2(
            repo, registry={"entries": [_valid_entry(
                "tools/probe.py", "f", outside)]}, calls=call)

        red_ok = any("仓内" in r for r in bad["reds"])
        ok = (not bad["ok"]) and red_ok and good["ok"]
        detail = "仓内 landing_root→红 %d 条；仓外 0700→红 %d 条" % (
            len(bad["reds"]), len(good["reds"]))
        if bad["untested"] or good["untested"]:
            ok = False
            detail += "；未测 %d/%d" % (len(bad["untested"]),
                                        len(good["untested"]))
        return {"id": "DG-5", "ok": ok, "detail": detail,
                "reds": [] if ok else [detail + "；" + str(bad["reds"][:2])],
                "untested": []}


def control_dg6():
    """DG-6（DG-1 的反向对照）：真实扫描器必须接进来；未登记调用必须红。

    刻意不注入 calls：让 evaluate_dg1 自己走 git ls-files → scan_py/scan_js。
    如果组装层忘了接扫描器，bad 会是绿，这条立刻红。
    """
    with tempfile.TemporaryDirectory(prefix="dg6_") as temp:
        base = Path(temp)
        repo = _temp_repo(base, {
            "probe.py": (
                'TOK = "tok"\n'
                'def f(t):\n'
                '    return _get(f"https://open.feishu.cn/open-apis/drive/v1/'
                'files/{t}/download", TOK)\n'
            ),
            "probe.mjs": (
                "export async function pull(token) {\n"
                "  return fetch(`https://open.feishu.cn/open-apis/drive/v1/"
                "files/${token}/download`);\n"
                "}\n"
            ),
        })
        outside = base / "outside"
        outside.mkdir()
        os.chmod(str(outside), 0o700)

        empty_registry = repo / "empty-registry.json"
        empty_registry.write_text('{"entries": []}', encoding="utf-8")

        bad = evaluate_dg1(repo, registry_path=empty_registry)
        good = evaluate_dg1(repo, registry={"entries": [
            _valid_entry("probe.py", "f", outside, ordinal=1),
            _valid_entry("probe.mjs", "pull", outside, ordinal=1),
        ]})

        # 两个文件都必须被扫描器认出来，且都必须是「少登记」这一类的红。
        red_paths = [r for r in bad["reds"]
                     if "probe.py" in r or "probe.mjs" in r]
        red_ok = (not bad["ok"]) and len(red_paths) >= 2
        ok = red_ok and good["ok"]
        detail = ("两个真实样本（.py + .mjs）未登记→红 %d 条；补登记后→红 %d 条"
                  % (len(bad["reds"]), len(good["reds"])))
        if bad["untested"] or good["untested"]:
            ok = False
            detail += "；未测 %d/%d" % (len(bad["untested"]),
                                        len(good["untested"]))
        return {"id": "DG-6", "ok": ok, "detail": detail,
                "reds": [] if ok else [detail + "；" + str(red_kind(bad))],
                "untested": []}


def red_kind(result):
    """控制失败时给报告留一点可读线索，而不是只有一句 False。"""
    return (result.get("reds") or [])[:2] + (result.get("untested") or [])[:1]


def control_discovery():
    """文件发现的反向对照：未跟踪的 .venv-r4 文件不许进扫描集合。"""
    with tempfile.TemporaryDirectory(prefix="dg_discover_") as temp:
        base = Path(temp)
        repo = _temp_repo(base, {"main.py": "print('x')\n"})
        hidden = repo / ".venv-r4"
        hidden.mkdir()
        (hidden / "big.py").write_text("print('dependency')\n", encoding="utf-8")
        tracked, note = discover_tracked(repo)
        ok = note is None and tracked == ["main.py"]
        detail = "git ls-files → %r（未跟踪的 .venv-r4/big.py 必须不在）" % (tracked,)
        return {"id": "discover", "ok": ok, "detail": detail,
                "reds": [] if ok else [detail], "untested": []}


# ---------------------------------------------------------------- 汇总

def _evaluate_controls():
    out = {}
    for fn in (control_dg4, control_dg5, control_dg6):
        try:
            result = fn()
        except Exception as exc:  # 控制自己跑不起来 = 未测，不是红也不是绿
            result = {"id": fn.__name__, "ok": False, "reds": [],
                      "untested": ["反向对照运行失败（%s）—— 未测" % exc],
                      "detail": "反向对照运行失败（%s）" % exc}
        out[result["id"]] = result
    return out


def evaluate_all(repo_root=ROOT, include_history=True, registry_path=None,
                 baseline_path=None):
    """跑 DG-1…DG-6 并汇总。返回 {verdict, exit_code, DG-x, ...}。"""
    root = Path(repo_root).resolve()
    registration = evaluate_registration(root, registry_path=registry_path)
    tracked, tracked_note = discover_tracked(root)
    if tracked is None:
        dg3 = {"id": "DG-3", "ok": False, "reds": [],
               "untested": [tracked_note], "detail": tracked_note,
               "tracked_files": 0}
    else:
        dg3 = evaluate_dg3(root, baseline_path=baseline_path, tracked=tracked,
                           include_history=include_history)

    results = {
        "DG-1": registration["DG-1"],
        "DG-2": registration["DG-2"],
        "DG-3": dg3,
    }
    results.update(_evaluate_controls())

    reds, untested = [], []
    for dg in DG_IDS:
        reds.extend(results[dg].get("reds") or [])
        untested.extend(results[dg].get("untested") or [])

    if reds:
        verdict, exit_code = "red", 1
    elif untested:
        verdict, exit_code = "untested", 2
    else:
        verdict, exit_code = "pass", 0

    n_tracked = len(tracked or [])
    return {
        "verdict": verdict,
        "exit_code": exit_code,
        "repo": str(root),
        "counts": {
            "tracked_files": n_tracked,
            "download_calls": len(registration.get("calls") or []),
            "registry_entries": registration.get("registry_entries", 0),
        },
        "DG-1": results["DG-1"],
        "DG-2": results["DG-2"],
        "DG-3": results["DG-3"],
        "DG-4": results["DG-4"],
        "DG-5": results["DG-5"],
        "DG-6": results["DG-6"],
        "registration": {
            "connection_to_code": registration.get("connection_to_code", "none"),
            "notes": registration.get("notes") or [],
        },
        "residual": [
            "登记表字段与代码实际落盘无连接（download_registry.connection_to_code=none）："
            "登记写 /tmp/x、代码写仓内，本器仍可能全绿。",
            "Python 扫描器不做跨文件 import 图；JS 扫描器只看单文件 token 流。",
            "PII 只认常见格式；base64/hex 载荷与文本头+尾部二进制不在检测范围。",
        ],
    }


# ---------------------------------------------------------------- 自证

_SUBMODULE_SELFTESTS = (
    ("download_scan_py", ("download_scan_py.py", "--selftest")),
    ("download_scan_js", ("download_scan_js.py", "--selftest")),
    ("download_registry", ("download_registry.py",)),
    ("download_blobs", ("download_blobs.py", "--selftest")),
)


def run_selftest(verbose=False):
    """跑四个子模块的自证 + 本组装层的四条行为级对照。"""
    checks = []
    for name, args in _SUBMODULE_SELFTESTS:
        cmd = [sys.executable, str(TOOLS_DIR / args[0])] + list(args[1:])
        stdout = stderr = ""
        try:
            run = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                                 text=True, timeout=600)
            stdout, stderr = run.stdout or "", run.stderr or ""
            ok = run.returncode == 0
            lines = [line for line in stdout.splitlines() if line.strip()]
            tail = lines[-1] if lines else "(无输出)"
            if not ok:
                tail += " | " + ((stderr.strip().splitlines() or [""])[-1])
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok, tail = False, "跑不起来：%s" % exc
        checks.append((name, ok, tail))
        if verbose:
            print("\n--- %s ---\n%s%s" % (name, stdout, stderr))

    for fn in (control_discovery, control_dg4, control_dg5, control_dg6):
        try:
            result = fn()
        except Exception as exc:
            result = {"id": fn.__name__, "ok": False,
                      "detail": "运行失败：%s" % exc}
        checks.append((result["id"], result["ok"], result.get("detail", "")))

    print("=" * 74)
    print("verify_download_governance · 组装层自证")
    print("=" * 74)
    for name, ok, detail in checks:
        print("  %s %-22s %s" % ("✅" if ok else "❌", name, detail))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print("-" * 74)
    print("  %d 项 / 失败 %d" % (len(checks), failed))
    if failed:
        print("✗ 自证未通过")
        return 1
    print("✅ 自证全过")
    return 0


# ---------------------------------------------------------------- CLI

def _print_human(result):
    print("=" * 74)
    print("下载治理 · DG-1…DG-6")
    print("=" * 74)
    counts = result["counts"]
    print("  仓库                 %s" % result["repo"])
    print("  已跟踪文件           %5d 个（扫描器只看索引内容）"
          % counts["tracked_files"])
    print("  下载调用点           %5d 个" % counts["download_calls"])
    print("  登记项               %5d 项" % counts["registry_entries"])
    print()
    for dg in DG_IDS:
        item = result[dg]
        if item["ok"]:
            mark = "✅"
        elif item.get("reds"):
            mark = "❌"
        else:
            mark = "⚠"
        print("  %s %-5s %s" % (mark, dg, item.get("detail", "")))
        for red in (item.get("reds") or [])[:10]:
            print("        - %s" % red)
        for note in (item.get("untested") or [])[:10]:
            print("        ⚠ %s" % note)
        if len(item.get("reds") or []) > 10:
            print("        … 另有 %d 条红" % (len(item["reds"]) - 10))
        if len(item.get("untested") or []) > 10:
            print("        … 另有 %d 条未测" % (len(item["untested"]) - 10))
    print()
    for note in result["registration"].get("notes") or []:
        print("  说明：%s" % note)
    print()
    if result["verdict"] == "pass":
        print("✅ 下载治理全过")
    elif result["verdict"] == "red":
        print("✗ 下载治理有红（退出码 1）")
    else:
        print("⚠ 下载治理有未测（退出码 2，不是通过）")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="下载治理验证器 DG-1…DG-6（组装 download_scan_py/js/registry/blobs）")
    parser.add_argument("--selftest", action="store_true",
                        help="跑四个子模块自证 + 本层行为级反向对照")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--repo", default=str(ROOT), help="仓库根（默认本文件上一级）")
    parser.add_argument("--registry", default=None,
                        help="登记表路径（默认 <repo>/tools/download_callers.json）")
    parser.add_argument("--baseline", default=None,
                        help="资产基线路径（默认 <repo>/tools/asset_baseline.json）")
    parser.add_argument("--no-history", action="store_true",
                        help="DG-3 跳过历史提交扫描（更快，但少了历史泄漏面）")
    parser.add_argument("--verbose", action="store_true",
                        help="--selftest 时打印子模块完整输出")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest(verbose=args.verbose)

    result = evaluate_all(Path(args.repo).resolve(),
                          include_history=not args.no_history,
                          registry_path=args.registry,
                          baseline_path=args.baseline)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    else:
        _print_human(result)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
