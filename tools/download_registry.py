#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_registry.py —— 下载登记表的调用点粒度核对 + 完整字段校验（漏洞 2 + 漏洞 3）

## 为什么要有这个文件

2026-10-17 红线改成「飞书内容都可以下载」之后，唯一还站得住的约束是
**下载物不许进公开仓**。`tools/download_callers.json` 是这条约束的意图声明：
谁消费、落到哪个根、留多久、什么分级。意图声明必须可校验，否则它只是注释。

原实现有两处已实测的漏洞：

- **漏洞 2（登记键太粗）**：键是 `(path, symbol)`。同一个函数里第二个下载调用
  会被同一条旧登记放行 —— 登记 1 条，2 个调用都算已登记。
  本模块把键升到调用点粒度，并且**双向核对数量**：少登记（代码有、表里没有）
  与多登记 / 过期登记（表里有、代码里没有）都红。
- **漏洞 3（DG-2 只验路径在仓外）**：api / api_kind / consumer / retention /
  data_class / never_tracked / 目录权限 / 未知字段全都没验。本模块逐字段验。

## ★ 必须明着承认的残余（攻击轮指出，不许假装拦住了）

返回值里的 `connection_to_code: "none"` 是一个**常量**，不是算出来的结论：

> **本模块校验的是登记表里的字符串，它与代码实际写到哪里没有任何连接。**

一条登记项写 `landing_root: /tmp/whatever`（目录存在、权限 0700、在仓外），
而代码照旧 `open("research/feishu/x.png", "wb")` 写进仓内，本模块会全绿。
真正的连接需要数据流分析 —— 把「下载字节」和「实际落盘路径」绑在一起，
这不在本文件范围内。本文件能保证的只有两件事：

1. 每条登记项自身字段自洽、且 `landing_root` 这个**字符串**指向仓外一个 0700 目录；
2. 登记项与扫描器报出的调用点在数量与位置上**一一对应**。

把这条残余写进返回值而不是只写注释，是为了让调用方无法把它误当成端到端保证。

## 调用点键的两种形态

- **形态 A**：`lineno` + `col_offset`。精确到列，但代码上方一改行号就漂。
- **形态 B**：`api_kind` + `ordinal`。`ordinal` 是同一 `(path, symbol, api_kind)`
  内按 `(lineno, col_offset)` 排序的 1 基序号。它抗「上方插了别的代码」的行号漂移，
  但不抗「同函数同接口前面又插了一个下载调用」—— 那种情况下序号会指向新调用。
  这是为了可维护性明着接受的缺口，不是没想到。

## 返回

```
{"ok": bool, "reds": [...], "untested": [...], "connection_to_code": "none"}
```

`ok = 无红且无未测`。**未测绝不能当通过**：目录还不存在时字段本身允许，
但「目录权限 0700」这一条没法验，所以整体 `ok` 必须是 False，
让调用方走「未测」而不是「通过」（本项目退出码 2 与 0、1 都不同）。
"""

from __future__ import annotations

import os
import re
import stat
import sys
import tempfile
from pathlib import Path

__all__ = ["validate_registry"]

# 已知的飞书下载接口。登记表的 api 字段必须落在这里面。
# 用正则而不是精确字符串，是因为 token 段在不同脚本里写法不同（{t} / <expr> / :file_token）。
#
# ★ 2026-10-21 扩第三族 `im_message_resource`：守衡的群附件入站
#   （tools/agent/feishu.mjs 的 downloadMessageResource）走的是
#   `im/v1/messages/{message_id}/resources/{file_key}` —— 它是下载，不是普通读消息。
#   JS 扫描器本来就能认出它（shape=request_path），但登记表只认两族，于是
#   「代码里有调用、登记表里无族可归」会变成一条无法消除的红。
#   扩族必须同时改 `_api_kind_of_registry_api` 与 `_call_api_kind`，
#   并且登记项要过 landing_root 的仓外 + 0700 判据（DG-2）。
_RE_DRIVE_FILE_API = re.compile(
    r"drive/v1/files/[^/\s]+/download(?:$|[?#\s])", re.I)
_RE_MEDIA_TMP_API = re.compile(
    r"medias/batch_get_tmp_download_url(?:$|[?#\s])", re.I)
_RE_IM_RESOURCE_API = re.compile(
    r"im/v1/messages/[^/\s]+/resources/[^/\s]+(?:$|[?#\s])", re.I)

KNOWN_API_KINDS = ("drive_file", "media_tmp_url", "im_message_resource")
RETENTIONS = ("run-scoped", "24h", "7d", "30d", "1y")
DATA_CLASSES = ("public", "internal", "confidential", "pii")

# 占位词等于没回答「谁消费」。只收真正无信息量的词，不做模糊匹配 ——
# 本项目踩过「模糊匹配 secret|token|key 把 ctokens.py 也拦了」的坑（AGENTS.md §2.1.1）。
PLACEHOLDER_CONSUMERS = {
    "系统", "todo", "tbd", "-", "—", "n/a", "na", "待定", "待补", "?",
}

# 调用点定位字段也在白名单里：它们是键的一部分，不是未知字段。
ALLOWED_ENTRY_FIELDS = {
    "path", "symbol", "api", "api_kind", "consumer", "landing_root",
    "retention", "data_class", "never_tracked",
    "ordinal", "lineno", "col_offset",
}


def _result(reds, untested):
    return {
        "ok": not reds and not untested,
        "reds": list(reds),
        "untested": list(untested),
        # ★ 攻击轮结论：这个字段是常量，提醒调用方不要把它当成端到端保证。
        "connection_to_code": "none",
    }


def _norm_path(value):
    """把 path 统一成仓内相对路径的写法，避免 ./ 与反斜杠造成假红/假绿。"""
    s = str(value or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def _is_int(value):
    # bool 是 int 的子类；`True` 当 ordinal/lineno 会悄悄变成 1。
    return isinstance(value, int) and not isinstance(value, bool)


def _within(child, parent):
    """child 是否等于 parent 或位于其下（两边都应是 realpath 绝对路径）。"""
    child = os.path.normpath(child)
    parent = os.path.normpath(parent)
    if child == parent:
        return True
    return child.startswith(parent.rstrip(os.sep) + os.sep)


def _api_kind_of_registry_api(api):
    """登记表 api 字段属于哪一族；不属于任何一族返回 None。"""
    s = str(api or "").strip()
    if _RE_MEDIA_TMP_API.search(s):
        return "media_tmp_url"
    if _RE_DRIVE_FILE_API.search(s):
        return "drive_file"
    if _RE_IM_RESOURCE_API.search(s):
        return "im_message_resource"
    return None


def _call_api_kind(call):
    """从扫描器的一条调用记录推断接口族。

    推断只是为了让 ordinal 键能分组；推断不出来时调用方仍可用 lineno/col_offset
    定位。宁可返回 None，也不要猜一个族 —— 猜错会让两条不同的调用被当成同一族。
    """
    explicit = str(call.get("api_kind") or "").strip()
    if explicit in KNOWN_API_KINDS:
        return explicit

    text = " ".join(str(call.get(k) or "") for k in ("api", "marker", "sink", "shape",
                                                      "method"))
    low = text.lower()
    if ("batch_get_tmp_download_url" in low or "batch_get_tmp_url" in low
            or "download_media" in low or "downloadmedia" in low):
        return "media_tmp_url"
    # 群附件入站：SDK 方法名 client.im.v1.messageResource.get，
    # JS 扫描器把它记成 shape=request_path、marker=func:downloadMessageResource。
    # 必须放在 drive_file 的兜底之前 —— 否则「download」这个词会把它误归成 drive_file。
    if "messageresource" in low or ("im/v1/messages" in low and "/resources/" in low):
        return "im_message_resource"
    if ("drive/v1/files/" in low and "download" in low
            or "downloadfile" in low or "download_file" in low
            or "files.download" in low):
        return "drive_file"
    # SDK 只给方法名、没有 URL 字面量时，download 系列按 drive_file 归族。
    if str(call.get("sink") or "") == "sdk" and "download" in low:
        return "drive_file"
    return None


def _normalize_calls(calls, untested):
    """把扫描器输出收敛成可核对的最小记录；坏记录落「未测」而不是被静默跳过。"""
    out = []
    seen = set()
    for i, raw in enumerate(calls):
        if not isinstance(raw, dict):
            untested.append("calls[%d] 不是对象，无法核对（未测，不是通过）" % i)
            continue
        path = _norm_path(raw.get("path"))
        symbol = str(raw.get("symbol") or "").strip()
        if not path or not symbol:
            untested.append(
                "calls[%d] 缺 path/symbol，无法定位到调用点（未测，不是通过）" % i)
            continue
        lineno = raw.get("lineno")
        col = raw.get("col_offset")
        if not _is_int(lineno) or lineno < 1 or not _is_int(col) or col < 0:
            # 扫描器契约要求带 lineno + col_offset；缺了就无法做调用点粒度核对。
            # 静默丢弃会让「少登记」漏报，所以必须显式落未测。
            untested.append(
                "calls[%d] %s::%s 缺合法 lineno/col_offset，调用点粒度无法核对"
                "（未测，不是通过）" % (i, path, symbol))
            continue
        kind = _call_api_kind(raw)
        dedupe = (path, symbol, lineno, col, str(raw.get("api") or ""), kind or "")
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({
            "path": path,
            "symbol": symbol,
            "lineno": lineno,
            "col_offset": col,
            "api_kind": kind,
            "api": str(raw.get("api") or ""),
            "_i": len(out),
        })
    return out


def _check_landing_root(raw, label, repo_real, reds, untested):
    """landing_root 的完整校验。

    ★ 攻击轮指出的残余在这里最该被记住：这一整段验的只是**登记表里的字符串**。
    代码完全可以在登记 /tmp/whatever 的同时，用另一个路径写进仓内 —— 本函数
    看不见代码，也看不见运行时的 open()。所以它绿了不等于「下载物没进仓」。
    """
    if not isinstance(raw, str) or not raw.strip():
        reds.append(label + " landing_root 为空或不是字符串")
        return

    s = raw.strip()
    if s.startswith("env:"):
        var = s[4:].strip()
        if not var:
            reds.append(label + " landing_root 的 env: 后没有变量名")
            return
        value = os.environ.get(var)
        if value is None or not str(value).strip():
            # 「必须已设置」是登记表成立的前提；取不到就无法证明落在仓外。
            reds.append(label + " landing_root 引用的环境变量 %s 未设置（必须已设置）"
                        % var)
            return
        s = str(value).strip()

    expanded = os.path.expanduser(s)
    if not os.path.isabs(expanded):
        reds.append(label + " landing_root 必须是绝对路径或 env:VAR: %r" % raw)
        return

    try:
        real = os.path.realpath(expanded)
    except OSError as exc:
        untested.append(label + " landing_root realpath 失败（%s）—— 未测，不是通过"
                        % exc)
        return

    # 用 realpath 而不是 abspath：landing_root 的祖先可能是一条指向仓内的 symlink，
    # 只看字面路径会把它判成仓外。
    if _within(real, repo_real):
        reds.append(label + " landing_root 经 realpath 解析后在仓内"
                    "（symlink 祖先也算）: %s" % real)
        return

    if not os.path.exists(real):
        # 目录还没建是允许的，但权限这一条没验 —— 只能说未测，不能说通过。
        untested.append(label + " landing_root 目录尚不存在，权限这一条无法验证"
                        "（未测，不是通过）: %s" % real)
        return

    if not os.path.isdir(real):
        reds.append(label + " landing_root 存在但不是目录: %s" % real)
        return

    try:
        mode = stat.S_IMODE(os.stat(real).st_mode)
    except OSError as exc:
        untested.append(label + " landing_root 权限读不到（%s）—— 未测，不是通过"
                        % exc)
        return
    if mode != 0o700:
        reds.append(label + " landing_root 目录权限是 %04o，必须是 0700: %s"
                    % (mode, real))


def _validate_entry(entry, idx, repo_real, reds, untested):
    """逐字段校验一条登记项，返回可用于匹配的规范化信息。"""
    tag = "entry[%d]" % idx
    if not isinstance(entry, dict):
        reds.append(tag + " 不是对象")
        return None

    # 未知字段必须红：`landing_roots` 这类拼错如果被静默忽略，
    # 这条登记就会以「看起来写了落盘根」的样子通过。
    for key in entry:
        if key not in ALLOWED_ENTRY_FIELDS:
            reds.append("%s 未知字段 %r —— 拼写错误会被静默忽略，所以必须红"
                        % (tag, key))

    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        reds.append(tag + " path 为空或不是字符串")
        path = ""
    else:
        path = _norm_path(raw_path)
        if os.path.isabs(path):
            reds.append(tag + " path 不是仓内相对路径: %r" % raw_path)
        elif ".." in path.split("/"):
            reds.append(tag + " path 含 '..'，不是仓内相对路径: %r" % raw_path)
        else:
            abs_path = os.path.join(repo_real, path)
            try:
                real_path = os.path.realpath(abs_path)
            except OSError as exc:
                untested.append(tag + " path realpath 失败（%s）—— 未测，不是通过"
                                % exc)
                real_path = ""
            if real_path and not _within(real_path, repo_real):
                reds.append(tag + " path 解析后跑到仓外: %s" % real_path)
            elif real_path and not os.path.isfile(real_path):
                reds.append(tag + " path 指向的文件不存在: %s" % path)

    raw_symbol = entry.get("symbol")
    if not isinstance(raw_symbol, str) or not raw_symbol.strip():
        reds.append(tag + " symbol 为空或不是字符串")
        symbol = ""
    else:
        symbol = raw_symbol.strip()

    label = "%s (%s::%s)" % (tag, path or "?", symbol or "?")

    raw_api = entry.get("api")
    api_kind_raw = entry.get("api_kind")
    api_kind = api_kind_raw.strip() if isinstance(api_kind_raw, str) else None
    kind_from_api = None
    if not isinstance(raw_api, str) or not raw_api.strip():
        reds.append(label + " api 为空或不是字符串")
    else:
        kind_from_api = _api_kind_of_registry_api(raw_api)
        if kind_from_api is None:
            reds.append(label + " api 不是已知飞书下载接口（只认 drive_file / "
                        "media_tmp_url 两族）: %r" % raw_api)
    if api_kind not in KNOWN_API_KINDS:
        reds.append(label + " api_kind 非法（允许: drive_file / media_tmp_url）: %r"
                    % (api_kind_raw,))
    elif kind_from_api is not None and api_kind != kind_from_api:
        reds.append(label + " api_kind 与 api 不一致: api_kind=%r，但 api 属于 %r"
                    % (api_kind, kind_from_api))

    consumer = entry.get("consumer")
    if not isinstance(consumer, str) or not consumer.strip():
        reds.append(label + " consumer 为空或不是字符串")
    elif consumer.strip().lower() in PLACEHOLDER_CONSUMERS:
        reds.append(label + " consumer 是占位词（等于没回答「谁消费」）: %r"
                    % consumer)

    _check_landing_root(entry.get("landing_root"), label, repo_real, reds, untested)

    retention = entry.get("retention")
    if not isinstance(retention, str) or retention not in RETENTIONS:
        reds.append(label + " retention 非法（允许: %s）: %r"
                    % (" / ".join(RETENTIONS), retention))

    data_class = entry.get("data_class")
    if not isinstance(data_class, str) or data_class not in DATA_CLASSES:
        reds.append(label + " data_class 非法（允许: %s）: %r"
                    % (" / ".join(DATA_CLASSES), data_class))

    if entry.get("never_tracked") is not True:
        reds.append(label + " never_tracked 必须为 true（布尔 true，不是字符串/1）: %r"
                    % (entry.get("never_tracked"),))

    return {"path": path, "symbol": symbol, "api_kind": api_kind}


def _locator(entry, label, reds):
    """返回 ('ordinal', n) / ('position', line, col) / None。"""
    has_ordinal = "ordinal" in entry
    has_lineno = "lineno" in entry
    has_col = "col_offset" in entry

    if has_ordinal and (has_lineno or has_col):
        reds.append(label + " 定位方式必须二选一：ordinal 与 lineno/col_offset "
                    "不能同时出现")
        return None

    if has_ordinal:
        ordinal = entry.get("ordinal")
        if not _is_int(ordinal) or ordinal < 1:
            reds.append(label + " ordinal 必须是 >=1 的整数: %r" % (ordinal,))
            return None
        return ("ordinal", ordinal)

    if has_lineno or has_col:
        if not has_lineno or not has_col:
            reds.append(label + " lineno 与 col_offset 必须成对出现")
            return None
        lineno = entry.get("lineno")
        col = entry.get("col_offset")
        if not _is_int(lineno) or lineno < 1:
            reds.append(label + " lineno 必须是 >=1 的整数: %r" % (lineno,))
            return None
        if not _is_int(col) or col < 0:
            reds.append(label + " col_offset 必须是 >=0 的整数: %r" % (col,))
            return None
        return ("position", lineno, col)

    # 旧的 (path, symbol) 键正是漏洞 2 的来源，不能再放过。
    reds.append(label + " 缺调用点定位：必须是 ordinal 或 lineno+col_offset"
                "（(path, symbol) 键不够用）")
    return None


def validate_registry(registry: dict, repo_root: Path, calls: list[dict]) -> dict:
    """校验登记表与扫描器调用点是否一一对应，并逐字段校验每条登记项。

    `calls` 的每条记录至少要有 path / symbol / lineno / col_offset；
    api / marker / sink / shape 用来推断接口族（推断不出时可用位置键定位）。
    """
    reds = []
    untested = []

    try:
        repo = Path(repo_root)
    except (TypeError, ValueError) as exc:
        return _result(reds, ["repo_root 无法解析（%s）—— 未测，不是通过" % exc])

    try:
        repo_real = os.path.realpath(str(repo))
    except OSError as exc:
        return _result(reds, ["repo_root realpath 失败（%s）—— 未测，不是通过"
                             % exc])
    if not os.path.isdir(repo_real):
        return _result(reds, ["repo_root 不存在或不是目录（%s）—— 未测，不是通过"
                             % repo_real])

    if not isinstance(registry, dict):
        return _result(reds, ["registry 不是对象 —— 未测，不是通过"])

    # 顶层只允许 entries 与 $ 开头的元信息；`entires` 这种拼错若被忽略，
    # 整个表会以「空登记」的样子通过，比一条字段拼错更危险。
    # ★ 必须放在 entries 存在性判断**之前**：拼错恰恰会让 entries 读不到，
    #   而这时只剩一条「未测」，拼错本身反而没人报。
    for key in registry:
        if key != "entries" and not str(key).startswith("$"):
            reds.append("registry 顶层未知字段 %r —— 拼写错误会被静默忽略，"
                        "所以必须红" % (key,))

    entries = registry.get("entries")
    if not isinstance(entries, list):
        return _result(reds, ["registry.entries 缺失或不是数组 —— 未测，不是通过"])
    if not isinstance(calls, list):
        return _result(reds, ["calls 不是数组 —— 未测，不是通过"])

    call_records = _normalize_calls(calls, untested)

    calls_by_symbol = {}
    for call in call_records:
        calls_by_symbol.setdefault((call["path"], call["symbol"]), []).append(call)

    # 数量核对按 (path, symbol) 做：扫描器报 N 个，登记表也必须有 N 条。
    # 这条同时覆盖「漏了一个新调用」和「旧调用删了但登记没删」两个方向。
    entry_counts = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (_norm_path(entry.get("path")),
               str(entry.get("symbol") or "").strip())
        entry_counts[key] = entry_counts.get(key, 0) + 1

    for key in sorted(set(calls_by_symbol) | set(entry_counts)):
        n_calls = len(calls_by_symbol.get(key, []))
        n_entries = entry_counts.get(key, 0)
        path, symbol = key
        if n_calls > n_entries:
            reds.append("少登记 %s::%s：扫描器报 %d 个调用，登记表只有 %d 条"
                        % (path or "?", symbol or "?", n_calls, n_entries))
        elif n_entries > n_calls:
            reds.append("多登记/过期登记 %s::%s：登记表有 %d 条，代码里只有 %d 个调用"
                        % (path or "?", symbol or "?", n_entries, n_calls))

    claimed = set()
    for idx, entry in enumerate(entries):
        info = _validate_entry(entry, idx, repo_real, reds, untested)
        if info is None:
            continue
        label = "entry[%d] (%s::%s)" % (idx, info["path"] or "?",
                                        info["symbol"] or "?")
        locator = _locator(entry, label, reds)
        if locator is None:
            continue

        if locator[0] == "position":
            _, lineno, col = locator
            candidates = [c for c in call_records
                          if c["path"] == info["path"]
                          and c["lineno"] == lineno
                          and c["col_offset"] == col]
            if not candidates:
                reds.append(label + " 登记了但代码里没有这个调用（过期登记）: "
                            "%s:%d:%d" % (info["path"], lineno, col))
                continue
            if len(candidates) > 1:
                reds.append(label + " 同一 lineno/col_offset 上有 %d 条调用，"
                            "无法唯一核对" % len(candidates))
                continue
            call = candidates[0]
            if call["symbol"] != info["symbol"]:
                reds.append(label + " symbol 与代码不一致：登记 %r，代码是 %r"
                            % (info["symbol"], call["symbol"]))
            if (info["api_kind"] in KNOWN_API_KINDS and call["api_kind"]
                    and info["api_kind"] != call["api_kind"]):
                reds.append(label + " api_kind 与代码实际接口不一致：登记 %r，"
                            "代码推断为 %r" % (info["api_kind"], call["api_kind"]))
        else:
            ordinal = locator[1]
            same_symbol = calls_by_symbol.get((info["path"], info["symbol"]), [])
            kind_calls = [c for c in same_symbol
                          if c["api_kind"] == info["api_kind"]]
            kind_calls.sort(key=lambda c: (c["lineno"], c["col_offset"], c["_i"]))
            if ordinal > len(kind_calls):
                reds.append(label + " ordinal=%d 超出范围：该函数同接口只有 %d 个调用"
                            % (ordinal, len(kind_calls)))
                continue
            call = kind_calls[ordinal - 1]

        if call["_i"] in claimed:
            reds.append(label + " 与另一条登记指向同一个调用点（重复登记）: "
                        "%s::%s %d:%d"
                        % (call["path"], call["symbol"], call["lineno"],
                           call["col_offset"]))
        else:
            claimed.add(call["_i"])

    # 即使数量对得上，也可能两条登记挤在同一个调用点上、另一个调用没人认领；
    # 「调用点未被覆盖」必须单独报，不能只靠数量差。
    for call in call_records:
        if call["_i"] not in claimed:
            reds.append("少登记：调用点没有被任何登记项覆盖 %s::%s %d:%d api=%s"
                        % (call["path"], call["symbol"], call["lineno"],
                           call["col_offset"], call["api"] or "?"))

    return _result(reds, untested)


# ------------------------------------------------------------------ 自证 fixtures
#
# 19 个 fixture（15 坏 / 4 好）。每个用例都在自己的临时目录里造仓库与落盘根，
# 不碰真仓库、不碰真环境变量（AGENTS.md §2.4.4：自证不许改它要保护的东西）。

_DRIVE_CALL_API = ("https://open.feishu.cn/open-apis/drive/v1/files/"
                   "<expr>/download")
_MEDIA_CALL_API = ("https://open.feishu.cn/open-apis/medias/"
                   "batch_get_tmp_download_url?file_tokens=<expr>")
_REG_DRIVE_API = "drive/v1/files/{file_token}/download"
_REG_MEDIA_API = "medias/batch_get_tmp_download_url"


def _make_workspace(base):
    """造一套 fixture 公用的目录：仓内/仓外/0755/指向仓内的 symlink。"""
    repo = base / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "probe.py").write_text(
        "def f():\n    pass\n", encoding="utf-8")

    inside = repo / "inside"
    inside.mkdir()
    os.chmod(str(inside), 0o700)
    (inside / "landing").mkdir()
    os.chmod(str(inside / "landing"), 0o700)

    outside = base / "outside"
    outside.mkdir()
    os.chmod(str(outside), 0o700)

    outside_0755 = base / "outside_0755"
    outside_0755.mkdir()
    os.chmod(str(outside_0755), 0o755)

    link_inside = base / "link_inside"
    link_inside.symlink_to(inside)

    return repo, outside, outside_0755


def _build_cases(base, repo, outside, outside_0755):
    env_name = "DSH_DL_REG_FIXTURE_LANDING"
    unset_name = "DSH_DL_REG_FIXTURE_UNSET"
    os.environ[env_name] = str(outside)
    os.environ.pop(unset_name, None)

    def entry(**overrides):
        e = {
            "path": "tools/probe.py",
            "symbol": "f",
            "api": _REG_DRIVE_API,
            "api_kind": "drive_file",
            "consumer": "momcozy.image_download",
            "landing_root": str(outside),
            "retention": "run-scoped",
            "data_class": "internal",
            "never_tracked": True,
            "ordinal": 1,
        }
        e.update(overrides)
        return e

    def entry_pos(**overrides):
        e = entry(**overrides)
        e.pop("ordinal", None)
        return e

    def call(**overrides):
        c = {
            "path": "tools/probe.py",
            "symbol": "f",
            "lineno": 3,
            "col_offset": 4,
            "sink": "http",
            "shape": "literal",
            "api": _DRIVE_CALL_API,
            "marker": "/download",
        }
        c.update(overrides)
        return c

    def case(name, entries, calls, want_ok, reds=(), untested=(),
             no_reds=False, no_untested=False):
        return {
            "name": name,
            "registry": {"entries": entries},
            "calls": calls,
            "want_ok": want_ok,
            "want_reds": list(reds),
            "want_untested": list(untested),
            "no_reds": no_reds,
            "no_untested": no_untested,
        }

    cases = []

    # ---- 4 个好 fixture ----

    # 漏洞 2 的正面对照：同函数两个同族调用，必须靠 ordinal 1/2 区分。
    # 旧键 (path, symbol) 在只有 1 条登记时会把两个调用都放行。
    cases.append(case(
        "good-ordinal-two-same-kind",
        [entry(ordinal=1), entry(ordinal=2)],
        [call(lineno=3, col_offset=4), call(lineno=4, col_offset=4)],
        want_ok=True, no_reds=True, no_untested=True))

    # 两种定位形态可以混用：一条行号精确、一条 ordinal。
    cases.append(case(
        "good-positional-mixed",
        [entry_pos(lineno=10, col_offset=8), entry(ordinal=2)],
        [call(lineno=10, col_offset=8), call(lineno=11, col_offset=8)],
        want_ok=True, no_reds=True, no_untested=True))

    # ordinal 是按 api_kind 分别计数的：两个不同族的调用各自都是 1。
    # 同时验证 env:VAR 能解析到仓外 0700 目录。
    cases.append(case(
        "good-per-kind-ordinal-env",
        [entry(ordinal=1, landing_root="env:" + env_name),
         entry(ordinal=1, api=_REG_MEDIA_API, api_kind="media_tmp_url",
               landing_root="env:" + env_name)],
        [call(lineno=5, col_offset=4),
         call(lineno=6, col_offset=4, api=_MEDIA_CALL_API,
              marker="batch_get_tmp_download_url")],
        want_ok=True, no_reds=True, no_untested=True))

    # 空表 + 无调用：校验器不许无中生有。
    cases.append(case(
        "good-empty",
        [], [],
        want_ok=True, no_reds=True, no_untested=True))

    # ---- 15 个坏 fixture ----

    typo = entry()
    typo["landing_roots"] = typo.pop("landing_root")
    cases.append(case(
        "bad-unknown-field-typo", [typo], [call()],
        want_ok=False, reds=("未知字段", "landing_roots"),
        no_untested=True))

    # 两个方向各一条，共用一次断言：绝对路径与「相对但文件不存在」都必须红。
    cases.append(case(
        "bad-path-absolute-and-missing",
        [entry(path=str(repo / "tools" / "probe.py")),
         entry(path="tools/ghost.py")],
        [call()],
        want_ok=False, reds=("不是仓内相对路径", "文件不存在"), no_untested=True))

    # 旧键形态 (path, symbol) 正是漏洞 2 的来源：没有调用点定位就必须红，
    # 否则同函数第二个调用永远无法被区分。
    old_key_entry = entry()
    old_key_entry.pop("ordinal")
    cases.append(case(
        "bad-missing-locator",
        [old_key_entry], [call()],
        want_ok=False, reds=("缺调用点定位",), no_untested=True))

    cases.append(case(
        "bad-symbol-consumer",
        [entry(symbol="   ", consumer="系统")], [call()],
        want_ok=False, reds=("symbol 为空", "占位词"), no_untested=True))

    cases.append(case(
        "bad-api-unknown",
        [entry(api="https://open.feishu.cn/open-apis/drive/v1/metas/batch_query")],
        [call()],
        want_ok=False, reds=("不是已知飞书下载接口",), no_untested=True))

    cases.append(case(
        "bad-api-kind-mismatch",
        [entry(api=_REG_DRIVE_API, api_kind="media_tmp_url")], [call()],
        want_ok=False, reds=("api_kind 与 api 不一致",), no_untested=True))

    cases.append(case(
        "bad-landing-inside-repo",
        [entry(landing_root=str(repo / "inside" / "landing"))], [call()],
        want_ok=False, reds=("仓内",), no_untested=True))

    # 字面路径在仓外，但 link_inside 是指向仓内的 symlink；只查 abspath 会漏。
    cases.append(case(
        "bad-landing-symlink-ancestor",
        [entry(landing_root=str(base / "link_inside" / "landing"))], [call()],
        want_ok=False, reds=("realpath", "仓内"), no_untested=True))

    cases.append(case(
        "bad-landing-mode",
        [entry(landing_root=str(outside_0755))], [call()],
        want_ok=False, reds=("0700",), no_untested=True))

    cases.append(case(
        "bad-landing-env-unset",
        [entry(landing_root="env:" + unset_name)], [call()],
        want_ok=False, reds=("未设置",), no_untested=True))

    cases.append(case(
        "bad-retention-data-class",
        [entry(retention="forever", data_class="secret")], [call()],
        want_ok=False, reds=("retention 非法", "data_class 非法"),
        no_untested=True))

    cases.append(case(
        "bad-never-tracked",
        [entry(never_tracked="true")], [call()],
        want_ok=False, reds=("never_tracked 必须为 true",), no_untested=True))

    # 漏洞 2 的核心反向对照：2 个调用只登记 1 条必须红（旧实现会放行）。
    # 匹配「扫描器报」是为了钉住**数量核对**本身，而不是被「调用点未覆盖」兜住。
    cases.append(case(
        "bad-under-registration",
        [entry(ordinal=1)],
        [call(lineno=3, col_offset=4), call(lineno=4, col_offset=4)],
        want_ok=False, reds=("扫描器报",), no_untested=True))

    # 反方向：1 个调用登记 2 条，多出来的那条是过期登记。
    cases.append(case(
        "bad-over-registration-stale",
        [entry(ordinal=1), entry(ordinal=2)],
        [call(lineno=3, col_offset=4)],
        want_ok=False, reds=("登记表有",), no_untested=True))

    # 目录尚不存在：不是红，但也绝不是通过 —— 必须落「未测」。
    cases.append(case(
        "bad-missing-dir-untested",
        [entry(landing_root=str(base / "not_created_yet"))], [call()],
        want_ok=False, untested=("未测",), no_reds=True))

    return cases


def _selftest():
    failures = 0
    total = 0
    with tempfile.TemporaryDirectory(prefix="download_registry_selftest_") as td:
        base = Path(td)
        repo, outside, outside_0755 = _make_workspace(base)
        saved_env = {}
        for name in ("DSH_DL_REG_FIXTURE_LANDING", "DSH_DL_REG_FIXTURE_UNSET"):
            saved_env[name] = os.environ.get(name)
        try:
            cases = _build_cases(base, repo, outside, outside_0755)

            # 设计定稿是 19 个（15 坏 / 4 好）。数字必须从这里算出来，
            # 否则删掉一个 fixture 后总结行仍会写着 19（§2.2 第 1 条）。
            n_good = sum(1 for item in cases
                         if item["name"].startswith("good-"))
            n_bad = sum(1 for item in cases
                        if item["name"].startswith("bad-"))
            if (n_good, n_bad) != (4, 15) or n_good + n_bad != len(cases):
                failures += 1
                print("❌ fixture 数量：算得 %d 好 / %d 坏 / 共 %d，设计是 4 好 / "
                      "15 坏 / 共 19" % (n_good, n_bad, len(cases)))

            for item in cases:
                total += 1
                result = validate_registry(item["registry"], repo, item["calls"])
                problems = []

                if result.get("connection_to_code") != "none":
                    problems.append("connection_to_code 必须是 'none'")

                if bool(result.get("ok")) != item["want_ok"]:
                    problems.append("ok=%r，期望 %r" % (result.get("ok"),
                                                        item["want_ok"]))
                if item["no_reds"] and result.get("reds"):
                    problems.append("不期望红，实际红了 %d 条：%s"
                                    % (len(result["reds"]),
                                       result["reds"][:2]))
                if item["no_untested"] and result.get("untested"):
                    problems.append("不期望未测，实际有 %d 条：%s"
                                    % (len(result["untested"]),
                                       result["untested"][:2]))
                for needle in item["want_reds"]:
                    if not any(needle in r for r in result.get("reds", [])):
                        problems.append("红里找不到 %r；实际红：%s"
                                        % (needle, result.get("reds", [])[:4]))
                for needle in item["want_untested"]:
                    if not any(needle in u for u in result.get("untested", [])):
                        problems.append("未测里找不到 %r；实际未测：%s"
                                        % (needle,
                                           result.get("untested", [])[:4]))

                if problems:
                    failures += 1
                    print("❌ %s" % item["name"])
                    for problem in problems:
                        print("     - %s" % problem)
                else:
                    print("✅ %s" % item["name"])
        finally:
            for name, old in saved_env.items():
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old

    if failures:
        print("\n✗ 自证失败：%d 处问题，跑了 %d 个 fixture" % (failures, total))
        return 1
    print("\n✅ %d 个 fixture 全过（%d 坏 / %d 好）" % (total, n_bad, n_good))
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
