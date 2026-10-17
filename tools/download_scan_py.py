#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""download_scan_py.py —— Python 下载调用的轻量数据流扫描器。

为什么需要它：
2026-10-17 项目红线从「飞书内容禁止下载」改成「都可以下载」之后，约束变成
「下载物不许进公开仓」。登记表的键要细到调用点（path + symbol + lineno +
col_offset），所以需要把「哪一行、哪一个调用、拼出了哪条下载 URL」认出来。

为什么是「轻量数据流」而不是完整求值：
本模块只在**单文件、单作用域**内跟踪字符串常量与形参流向，不执行代码、不做
跨文件 import 解析。目标是**把该红的都红出来**，漏掉的明着列在下面，而不是用
一个看起来聪明的近似求值假装全覆盖。

已知残余漏洞（明着留着，不假装拦住）：
* 跨文件 wrapper、re-export、别名（`from lark_http import get`、`get = _get`、
  `functools.partial`）—— 本模块没有 import 图；
* 运行时才确定的 URL（配置、环境变量、函数返回值）；
* 绕过 helper 的底层直连（`socket` / `http.client`）—— 三个判定面只认
  helper 名、SDK 方法名与模块内 wrapper，不认自己拼 HTTP 报文的代码；
* 增量拼接 `url += "/download"` —— 见 `_Walker.visit_stmt` 里 AugAssign 的说明；
* 字符串载体：`str(...)` / `"{}".format(...)` / `"%s" % (...)` 已顺手覆盖，
  其余任意 Call 只保留形参依赖，不恢复内容。

退出码：`--selftest` 0 全过 / 1 有红。扫描本身不判绿红，只产出调用点。
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import sys
import textwrap
from pathlib import Path

# 未知片段用 NUL 占位：它既不会出现在正常 URL 里，又能在拼接后保留常量片段，
# 从而让「/download 是否还在」这个判据不被变量打断。
UNKNOWN = "\x00"

# 候选爆炸时退化成未知：轻量扫描的精度本来就不支持大规模分支，硬撑着只会
# 产出看起来精确、实际无法解释的读数。
MAX_CANDIDATES = 8
MAX_STRING = 400

HTTP_HELPERS = {
    "_get", "_post", "_req", "_request", "get", "post", "request",
    "fetch", "urlopen", "urlretrieve",
}
# `_request` / `request` 的惯例是 method 在 URL 前面，其余 helper 的 URL 在首位。
URL_AT_POSITION_ONE = {"_request", "request"}
# 这些名字太常见，属性调用时必须另有旁证，否则 `cfg.get("/download")` 会全红。
GUARDED_ATTR_NAMES = {"get", "post", "request", "fetch", "urlopen", "urlretrieve"}
RECEIVER_HINTS = (
    "request", "session", "client", "conn", "http", "url", "api",
    "feishu", "lark", "sdk", "drive", "files", "medias",
)
URL_KEYWORDS = ("url", "uri", "endpoint")

# 方法名本身就是证据，所以这里必须是精确白名单：子串匹配会把 download_one
# 这类本地函数也算成 SDK 调用。
SDK_METHODS = {
    m.lower() for m in (
        "download", "download_file", "downloadFile", "download_media",
        "downloadMedia", "batch_get_tmp_download_url",
    )
}

DOWNLOAD_MARKERS = (
    "/download",
    "/medias/",
    "batch_get_tmp_download_url",
    "batch_get_tmp_url",
)

# 只由分隔符和未知占位组成的候选串，说明「URL 的实质内容可能全来自形参」。
# 用它把 `_get(u, TOK)`（真 wrapper）与 `_get("/raw?q=" + u)`（只是查询串）
# 区分开；后者的实参即使带 /download 也不该算下载。
STRUCTURAL_CHARS = set("/:?&=._-")

_PERCENT_RE = re.compile(
    r"%(?:%|\([^)]*\)[#0\- +]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa]"
    r"|[#0\- +]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa])"
)
_FORMAT_TOKEN_RE = re.compile(r"(\{\{|\}\}|\{[^{}]*\})")


def _entry(env, name):
    """env 的值允许是 2 元组或 3 元组：外部调用 resolve 时不必知道 shape 这一层。"""
    value = env.get(name)
    if value is None:
        return None
    if len(value) == 3:
        return value
    return (value[0], value[1], "literal")


def _cap(candidates, params):
    """超过预算就退化成未知，但形参依赖必须保留，否则 wrapper 链会断。"""
    params = set(params)
    if not candidates:
        return {UNKNOWN}, params
    if len(candidates) > MAX_CANDIDATES:
        return {UNKNOWN}, params
    if any(len(c) > MAX_STRING for c in candidates):
        return {UNKNOWN}, params
    return set(candidates), params


def _combine(left, right):
    out = set()
    for a in left:
        for b in right:
            out.add(a + b)
            if len(out) > MAX_CANDIDATES:
                return {UNKNOWN}
    return out


def _only_structural(candidate):
    if not candidate:
        return False
    return all(ch == UNKNOWN or ch in STRUCTURAL_CHARS for ch in candidate)


def _download_capable(candidates):
    """判断「这个 URL 位置有没有可能承载下载」。

    既认“常量段里已经有下载特征”，也认“整串都还是未知”——后者是
    `_get(u, TOK)` 这种由调用方传 URL 的 wrapper 的必经形态。
    """
    for candidate in candidates:
        for marker in DOWNLOAD_MARKERS:
            if marker in candidate:
                return True
    return any(_only_structural(c) for c in candidates)


def _pick_marker(candidates):
    """返回 (候选串, 命中的特征)。按固定顺序取，读数才可复现。"""
    for marker in DOWNLOAD_MARKERS:
        for candidate in sorted(candidates):
            if marker in candidate:
                return candidate, marker
    return None


def _display(candidate):
    return candidate.replace(UNKNOWN, "<expr>")


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return (base + "." + node.attr) if base else node.attr
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    if isinstance(node, ast.Subscript):
        return _dotted(node.value)
    return ""


def _is_request_call(call):
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr == "Request" and _dotted(func.value).endswith("urllib.request")
    if isinstance(func, ast.Name):
        return func.id == "Request"
    return False


def _is_path_join(call):
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "join":
        return _dotted(func.value) in ("os.path", "posixpath", "ntpath")
    return False


def _is_format_call(call):
    return isinstance(call.func, ast.Attribute) and call.func.attr == "format"


def _is_str_call(call):
    return isinstance(call.func, ast.Name) and call.func.id == "str"


def _apply_percent(template):
    return _PERCENT_RE.sub(
        lambda m: "%" if m.group(0) == "%%" else UNKNOWN, template
    )


def _percent_expand(template, right):
    """单占位符时把右侧候选填回去，`"%s" % url` 这种载体才不会丢内容。

    多占位符继续走旧办法：保留常量段、每个槽位变未知。右侧已经被 resolve
    压成了并集，再猜槽位对应关系只会制造假精度。
    """
    matches = [m for m in _PERCENT_RE.finditer(template) if m.group(0) != "%%"]
    if len(matches) == 1 and right:
        match = matches[0]
        return {
            template[:match.start()] + value + template[match.end():]
            for value in right
        }
    return {_apply_percent(template)}


def _format_expand(template, positional, named):
    """按占位符把实参候选填回模板；无法定位的槽位退化成未知。"""
    tokens = _FORMAT_TOKEN_RE.split(template)
    out = {""}
    position = 0
    for token in tokens:
        if token == "{{":
            values = {"{"}
        elif token == "}}":
            values = {"}"}
        elif token.startswith("{") and token.endswith("}"):
            field = token[1:-1].split("!")[0].split(":")[0].strip()
            if field == "":
                values = positional[position] if position < len(positional) else {UNKNOWN}
                position += 1
            elif field.isdigit():
                index = int(field)
                values = positional[index] if index < len(positional) else {UNKNOWN}
            else:
                values = named.get(field, {UNKNOWN})
        else:
            values = {token}
        combined = set()
        for prefix in out:
            for value in values:
                combined.add(prefix + value)
                if len(combined) > MAX_CANDIDATES:
                    return {UNKNOWN}
        out = combined
    return out


def resolve(expr, env):
    """把表达式解成 (候选字符串集合, 依赖的形参名集合)。

    候选里未知片段一律是 UNKNOWN。env 的值是 (candidates, params[, shape])。
    """
    if expr is None:
        return {UNKNOWN}, set()

    if isinstance(expr, ast.Constant):
        if isinstance(expr.value, str):
            # 单串预算在这里也要执行：直接写字面量是最常见的形态，
            # 漏掉这一支等于上限只对拼接生效。
            return _cap({expr.value}, set())
        return {UNKNOWN}, set()

    if isinstance(expr, ast.JoinedStr):
        parts = []
        params = set()
        for value in expr.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append(UNKNOWN)
                if isinstance(value, ast.FormattedValue):
                    _, inner_params = resolve(value.value, env)
                    params |= inner_params
        return _cap({"".join(parts)}, params)

    if isinstance(expr, ast.BinOp):
        if isinstance(expr.op, ast.Add):
            left, left_params = resolve(expr.left, env)
            right, right_params = resolve(expr.right, env)
            return _cap(_combine(left, right), left_params | right_params)
        if isinstance(expr.op, ast.Mod):
            left, left_params = resolve(expr.left, env)
            right, right_params = resolve(expr.right, env)
            expanded = set()
            for template in left:
                expanded |= _percent_expand(template, right)
            return _cap(expanded, left_params | right_params)
        # 其他运算符不猜语义，但形参依赖要保留，否则 wrapper 链会在这里断掉。
        _, left_params = resolve(expr.left, env)
        _, right_params = resolve(expr.right, env)
        return {UNKNOWN}, left_params | right_params

    if isinstance(expr, ast.Name):
        entry = _entry(env, expr.id)
        if entry is None:
            return {UNKNOWN}, set()
        return set(entry[0]), set(entry[1])

    if isinstance(expr, ast.Attribute):
        # 属性可能指向配置或对象字段，单文件静态扫描无从得知。
        return {UNKNOWN}, set()

    if isinstance(expr, ast.IfExp):
        body, body_params = resolve(expr.body, env)
        orelse, else_params = resolve(expr.orelse, env)
        return _cap(body | orelse, body_params | else_params)

    if isinstance(expr, (ast.Tuple, ast.List)):
        candidates = set()
        params = set()
        for element in expr.elts:
            values, deps = resolve(element, env)
            candidates |= values
            params |= deps
            if len(candidates) > MAX_CANDIDATES:
                return {UNKNOWN}, params
        return _cap(candidates, params)

    if isinstance(expr, ast.BoolOp):
        candidates = set()
        params = set()
        for value in expr.values:
            values, deps = resolve(value, env)
            candidates |= values
            params |= deps
        return _cap(candidates, params)

    if isinstance(expr, ast.Call):
        func = expr.func
        if _is_request_call(expr):
            if expr.args:
                return resolve(expr.args[0], env)
            for keyword in expr.keywords:
                if keyword.arg in URL_KEYWORDS:
                    return resolve(keyword.value, env)
            return {UNKNOWN}, set()

        if _is_path_join(expr):
            params = set()
            segments = []
            for arg in expr.args:
                values, deps = resolve(arg, env)
                segments.append(values)
                params |= deps
            candidates = {""}
            for values in segments:
                combined = set()
                for prefix in candidates:
                    for value in values:
                        combined.add(posixpath.join(prefix, value))
                        if len(combined) > MAX_CANDIDATES:
                            return {UNKNOWN}, params
                candidates = combined
            return _cap(candidates, params)

        if _is_format_call(expr):
            receiver, params = resolve(func.value, env)
            params = set(params)
            positional = []
            named = {}
            for arg in expr.args:
                values, deps = resolve(arg, env)
                positional.append(values)
                params |= deps
            for keyword in expr.keywords:
                values, deps = resolve(keyword.value, env)
                params |= deps
                if keyword.arg is not None:
                    named[keyword.arg] = values
            expanded = set()
            for template in receiver:
                expanded |= _format_expand(template, positional, named)
            return _cap(expanded, params)

        if _is_str_call(expr):
            if expr.args:
                return resolve(expr.args[0], env)
            return {UNKNOWN}, set()

        # 任意 Call 的内容不可知，但实参里的形参依赖仍是真实数据流。
        params = set()
        for arg in expr.args:
            _, deps = resolve(arg, env)
            params |= deps
        for keyword in expr.keywords:
            _, deps = resolve(keyword.value, env)
            params |= deps
        return {UNKNOWN}, params

    if isinstance(expr, ast.Starred):
        return resolve(expr.value, env)

    return {UNKNOWN}, set()


def _shape_of(expr, env):
    if isinstance(expr, ast.Constant):
        return "literal"
    if isinstance(expr, ast.JoinedStr):
        return "fstring"
    if isinstance(expr, ast.BinOp):
        return "concat"
    if isinstance(expr, (ast.IfExp, ast.Tuple, ast.List, ast.BoolOp)):
        return "concat"
    if isinstance(expr, ast.Name):
        entry = _entry(env, expr.id)
        return entry[2] if entry else "literal"
    if isinstance(expr, ast.Call):
        if _is_request_call(expr):
            return "request-object"
        if _is_str_call(expr) and expr.args:
            return _shape_of(expr.args[0], env)
        if _is_path_join(expr) or _is_format_call(expr):
            return "concat"
        return "literal"
    return "literal"


class _FuncInfo(object):
    __slots__ = ("node", "qualname", "in_class", "pos_params", "kw_params", "url_params")

    def __init__(self, node, qualname, in_class, pos_params, kw_params):
        self.node = node
        self.qualname = qualname
        self.in_class = in_class
        self.pos_params = pos_params
        self.kw_params = kw_params
        self.url_params = set()


def _collect_functions(body, prefix, in_class, out):
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional = [a.arg for a in getattr(node.args, "posonlyargs", [])]
            positional += [a.arg for a in node.args.args]
            if in_class and positional and positional[0] in ("self", "cls"):
                positional = positional[1:]
            keyword_only = [a.arg for a in node.args.kwonlyargs]
            info = _FuncInfo(node, prefix + node.name, in_class, positional, keyword_only)
            out.append(info)
            _collect_functions(node.body, info.qualname + ".", False, out)
            continue
        if isinstance(node, ast.ClassDef):
            _collect_functions(node.body, prefix + node.name + ".", True, out)
            continue
        # 函数/类可能藏在 if/try 里，漏掉它们会让 wrapper 固定点少一层。
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(node, field, None)
            if isinstance(nested, list) and nested and isinstance(nested[0], ast.stmt):
                _collect_functions(nested, prefix, in_class, out)
        for handler in getattr(node, "handlers", []) or []:
            _collect_functions(handler.body, prefix, in_class, out)


def _param_env(info):
    env = {}
    positional = list(getattr(info.node.args, "posonlyargs", [])) + list(info.node.args.args)
    for index, arg in enumerate(positional):
        if info.in_class and index == 0 and arg.arg in ("self", "cls"):
            env[arg.arg] = ({UNKNOWN}, set(), "literal")
        else:
            env[arg.arg] = ({UNKNOWN}, {arg.arg}, "literal")
    for arg in info.node.args.kwonlyargs:
        env[arg.arg] = ({UNKNOWN}, {arg.arg}, "literal")
    for arg in (info.node.args.vararg, info.node.args.kwarg):
        if arg is not None:
            env[arg.arg] = ({UNKNOWN}, set(), "literal")
    return env


def _build_wrapper_table(funcs):
    by_qual = {}
    bare_funcs = {}
    bare_methods = {}
    for info in funcs:
        if not info.url_params:
            continue
        entry = {
            "pos": list(info.pos_params),
            "url": frozenset(info.url_params),
        }
        by_qual[info.qualname] = entry
        if info.in_class:
            bare_methods.setdefault(info.node.name, entry)
        else:
            bare_funcs.setdefault(info.node.name, entry)
    return {"by_qual": by_qual, "funcs": bare_funcs, "methods": bare_methods}


def _match_wrapper(call, table):
    func = call.func
    if isinstance(func, ast.Name):
        return table["by_qual"].get(func.id) or table["funcs"].get(func.id)
    if isinstance(func, ast.Attribute):
        return table["by_qual"].get(_dotted(func)) or table["methods"].get(func.attr)
    return None


def _wrapper_url_args(call, entry):
    out = []
    url_names = entry["url"]
    positional = entry["pos"]
    # 出现 *args 后位置映射不再可信，只保留关键字那条路。
    if not any(isinstance(arg, ast.Starred) for arg in call.args):
        for index, arg in enumerate(call.args):
            if index >= len(positional):
                break
            if positional[index] in url_names:
                out.append(arg)
    for keyword in call.keywords:
        if keyword.arg is not None and keyword.arg in url_names:
            out.append(keyword.value)
    return out


class _Walker(object):
    def __init__(self, rel, symbol, env, wrappers, emit, keep_params):
        self.rel = rel
        self.symbol = symbol
        self.env = env
        self.wrappers = wrappers
        self.emit = emit
        self.keep_params = set(keep_params)
        self.findings = []
        self.url_params = set()

    # ------------------------------------------------------------ 语句

    def visit_body(self, body):
        for statement in body:
            self.visit_stmt(statement)

    def visit_stmt(self, statement):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in statement.decorator_list:
                self._scan_expr(decorator)
            self._scan_defaults(statement.args)
            return

        if isinstance(statement, ast.ClassDef):
            for decorator in statement.decorator_list:
                self._scan_expr(decorator)
            for base in statement.bases:
                self._scan_expr(base)
            for keyword in statement.keywords:
                self._scan_expr(keyword.value)
            self.visit_body(statement.body)
            return

        if isinstance(statement, ast.Assign):
            # 先用赋值前的 env 扫本语句里的调用，再绑定；否则
            # `url = url + "/download"` 会拿新值解释旧调用。
            self._scan_expr(statement.value)
            self._bind_value(statement.targets, statement.value)
            return

        if isinstance(statement, ast.AnnAssign):
            if statement.value is not None:
                self._scan_expr(statement.value)
                self._bind_value([statement.target], statement.value)
            return

        if isinstance(statement, ast.AugAssign):
            self._scan_expr(statement.value)
            # 已知残余：增量拼接故意不追。把它当未知，比“看起来追到了”
            # 更诚实；追一半会让人以为这条漏洞已经封住。
            self._bind_unknown(statement.target)
            return

        if isinstance(statement, ast.If):
            self._scan_expr(statement.test)
            self.visit_body(statement.body)
            self.visit_body(statement.orelse)
            return

        if isinstance(statement, (ast.For, ast.AsyncFor)):
            self._scan_expr(statement.iter)
            self._bind_unknown(statement.target)
            self.visit_body(statement.body)
            self.visit_body(statement.orelse)
            return

        if isinstance(statement, ast.While):
            self._scan_expr(statement.test)
            self.visit_body(statement.body)
            self.visit_body(statement.orelse)
            return

        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                self._scan_expr(item.context_expr)
                if item.optional_vars is not None:
                    self._bind_unknown(item.optional_vars)
            self.visit_body(statement.body)
            return

        if isinstance(statement, ast.Try):
            self.visit_body(statement.body)
            for handler in statement.handlers:
                if handler.type is not None:
                    self._scan_expr(handler.type)
                if handler.name:
                    self.env.pop(handler.name, None)
                self.visit_body(handler.body)
            self.visit_body(statement.orelse)
            self.visit_body(statement.finalbody)
            return

        # 其余语句只扫表达式，不猜控制流。
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.stmt):
                self.visit_stmt(child)
            elif isinstance(child, ast.expr):
                self._scan_expr(child)
            else:
                self._scan_expr(child)

    def _scan_defaults(self, args):
        for default in args.defaults:
            self._scan_expr(default)
        for default in args.kw_defaults:
            if default is not None:
                self._scan_expr(default)

    # ------------------------------------------------------------ 绑定

    def _bind_value(self, targets, value):
        candidates, params = resolve(value, self.env)
        shape = _shape_of(value, self.env)
        for target in targets:
            self._bind_target(target, candidates, params, shape)

    def _bind_target(self, target, candidates, params, shape):
        if isinstance(target, ast.Name):
            self.env[target.id] = (set(candidates), set(params), shape)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._bind_target(element, {UNKNOWN}, set(), "literal")
            return
        if isinstance(target, ast.Starred):
            self._bind_target(target.value, {UNKNOWN}, set(), "literal")

    def _bind_unknown(self, target):
        self._bind_target(target, {UNKNOWN}, set(), "literal")

    # ------------------------------------------------------------ 表达式

    def _scan_expr(self, node):
        if node is None:
            return
        if isinstance(node, ast.NamedExpr):
            self._scan_expr(node.value)
            candidates, params = resolve(node.value, self.env)
            self._bind_target(
                node.target, candidates, params, _shape_of(node.value, self.env)
            )
            return
        if isinstance(node, ast.Lambda):
            self._scan_defaults(node.args)
            self._scan_expr(node.body)
            return
        if isinstance(node, ast.Call):
            self._handle_call(node)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                continue
            self._scan_expr(child)

    # ------------------------------------------------------------ sink 判定

    def _handle_call(self, call):
        func = call.func

        if isinstance(func, ast.Attribute) and func.attr.lower() in SDK_METHODS:
            if self.emit:
                self.findings.append(self._finding(
                    call, sink="sdk", shape="sdk-method",
                    api=_dotted(func), marker=func.attr,
                ))
            return

        wrapper = _match_wrapper(call, self.wrappers)
        if wrapper is not None:
            for expr in _wrapper_url_args(call, wrapper):
                candidates, params = resolve(expr, self.env)
                if self.emit:
                    hit = _pick_marker(candidates)
                    if hit is not None:
                        candidate, marker = hit
                        self.findings.append(self._finding(
                            call, sink="wrapper", shape="wrapper",
                            api=_display(candidate), marker=marker,
                        ))
                        return
                else:
                    # 转发进另一个 wrapper 的 url 形参时，形参依赖无条件成立：
                    # 那个 wrapper 已经被证明能到下载 sink，前缀是什么不影响
                    # 「这个实参决定了 URL 的一段」这个事实。
                    self.url_params |= (params & self.keep_params)
            return

        selection = _http_url_expr(call)
        if selection is None:
            return
        expr, from_keyword = selection
        candidates, params = resolve(expr, self.env)
        if self.emit:
            hit = _pick_marker(candidates)
            if hit is None:
                return
            candidate, marker = hit
            shape = "kwarg" if from_keyword else _shape_of(expr, self.env)
            self.findings.append(self._finding(
                call, sink="http", shape=shape,
                api=_display(candidate), marker=marker,
            ))
        else:
            if _download_capable(candidates):
                self.url_params |= (params & self.keep_params)

    def _finding(self, call, sink, shape, api, marker):
        return {
            "path": self.rel,
            "symbol": self.symbol,
            "lineno": getattr(call, "lineno", 0),
            "col_offset": getattr(call, "col_offset", 0),
            "sink": sink,
            "shape": shape,
            "api": api,
            "marker": marker,
        }


def _http_url_expr(call):
    """返回 (URL 表达式, 是否来自关键字)；不是 HTTP helper 或应防误报时返回 None。"""
    func = call.func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return None
    if name not in HTTP_HELPERS:
        return None

    keyword_expr = None
    for keyword in call.keywords:
        if keyword.arg in URL_KEYWORDS:
            keyword_expr = keyword.value
            break

    if isinstance(func, ast.Attribute) and name in GUARDED_ATTR_NAMES and not name.startswith("_"):
        chain = _dotted(func.value).lower()
        receiver_ok = any(hint in chain for hint in RECEIVER_HINTS)
        if keyword_expr is None and not receiver_ok:
            # `cfg.get("/download")` 这类普通字典/配置读取，不是网络调用。
            return None

    if keyword_expr is not None:
        return keyword_expr, True

    position = 1 if name in URL_AT_POSITION_ONE else 0
    if len(call.args) <= position:
        return None
    argument = call.args[position]
    if isinstance(argument, ast.Starred):
        return None
    return argument, False


def _analyze_function(info, wrappers):
    walker = _Walker(
        "<probe>", info.qualname, _param_env(info), wrappers, emit=False,
        keep_params=set(info.pos_params) | set(info.kw_params),
    )
    walker.visit_body(info.node.body)
    return walker.url_params


def _compute_wrappers(funcs):
    wrappers = _build_wrapper_table(funcs)
    # 固定点：一个 wrapper 的 URL 形参可能经另一层 wrapper 才到达下载 sink。
    # url_params 每轮只增不减，轮数上界就是全体形参数，不会无限转。
    budget = 1 + sum(len(i.pos_params) + len(i.kw_params) for i in funcs)
    for _ in range(budget):
        changed = False
        for info in funcs:
            found = _analyze_function(info, wrappers)
            new = found - info.url_params
            if new:
                info.url_params |= new
                changed = True
        wrappers = _build_wrapper_table(funcs)
        if not changed:
            break
    return wrappers


def scan_python_source(src, rel="<probe>"):
    """扫描一段源码。零 IO，便于自证与在内存里喂样本。"""
    tree = ast.parse(src)

    funcs = []
    _collect_functions(tree.body, "", False, funcs)
    wrappers = _compute_wrappers(funcs)

    findings = []
    module_walker = _Walker(rel, "<module>", {}, wrappers, emit=True, keep_params=set())
    module_walker.visit_body(tree.body)
    findings.extend(module_walker.findings)

    for info in funcs:
        walker = _Walker(
            rel, info.qualname, _param_env(info), wrappers, emit=True,
            keep_params=set(info.pos_params) | set(info.kw_params),
        )
        walker.visit_body(info.node.body)
        findings.extend(walker.findings)

    findings.sort(key=lambda row: (
        row["lineno"], row["col_offset"], row["sink"], row["api"],
    ))
    return findings


def scan_python_files(paths):
    """读取给定文件（或目录下的 .py）并汇总调用点。"""
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.py") if p.is_file()))
        else:
            files.append(path)

    findings = []
    for path in files:
        src = path.read_text(encoding="utf-8")
        findings.extend(scan_python_source(src, rel=path.as_posix()))
    findings.sort(key=lambda row: (
        row["path"], row["lineno"], row["col_offset"], row["sink"], row["api"],
    ))
    return findings


# ------------------------------------------------------------------ 自证

def _fx(src):
    return textwrap.dedent(src).strip("\n") + "\n"


FIXTURES = [
    {
        "name": "bad-01 字面量 f-string",
        "src": _fx('''
            BASE = "https://open.feishu.cn/open-apis"
            TOK = "tok"
            def f(t):
                return _get(f"{BASE}/drive/v1/files/{t}/download", TOK)
        '''),
        "want": [("http", 4, "fstring", "f")],
    },
    {
        "name": "bad-02 变量拼接",
        "src": _fx('''
            BASE = "https://open.feishu.cn/open-apis"
            TOK = "tok"
            def f(t):
                url = BASE + "/drive/v1/files/" + t + "/download"
                return _get(url, TOK)
        '''),
        "want": [("http", 5, "concat", "f")],
    },
    {
        "name": "bad-03 SDK 方法两处",
        "src": _fx('''
            def f(client, file_token, fileToken):
                client.drive.v1.files.download(file_token=file_token)
                client.drive.file.download(fileToken=fileToken)
        '''),
        "want": [
            ("sdk", 2, "sdk-method", "f"),
            ("sdk", 3, "sdk-method", "f"),
        ],
    },
    {
        "name": "bad-04 关键字 url",
        "src": _fx('''
            import requests
            def f(headers):
                return requests.get(url="https://open.feishu.cn/open-apis/drive/v1/files/x/download", headers=headers)
        '''),
        "want": [("http", 3, "kwarg", "f")],
    },
    {
        "name": "bad-05 单层封装",
        "src": _fx('''
            TOK = "tok"
            def dl(u):
                return _get(u, TOK)
            def f():
                return dl("https://open.feishu.cn/open-apis/drive/v1/files/x/download")
        '''),
        "want": [("wrapper", 5, "wrapper", "f")],
    },
    {
        "name": "bad-06 两层封装 + 调用点拼接",
        "src": _fx('''
            TOK = "tok"
            def dl(u):
                return _get(u, TOK)
            def fetch_bytes(v):
                return dl(v)
            def f():
                return fetch_bytes("https://open.feishu.cn/open-apis/drive/v1/files/x/download")
        '''),
        "want": [("wrapper", 7, "wrapper", "f")],
    },
    {
        "name": "bad-07 Request 对象载体",
        "src": _fx('''
            import urllib.request
            def f():
                req = urllib.request.Request("https://open.feishu.cn/open-apis/drive/v1/files/x/download")
                return urllib.request.urlopen(req)
        '''),
        "want": [("http", 4, "request-object", "f")],
    },
    {
        "name": "bad-08 request 的 URL 在第 2 位",
        "src": _fx('''
            import requests
            def f():
                return requests.request("GET", "https://open.feishu.cn/open-apis/drive/v1/files/x/download")
        '''),
        "want": [("http", 3, "literal", "f")],
    },
    {
        "name": "good-01 普通文档读取 + download 声明 + cfg.get",
        "src": _fx('''
            TOK = "tok"
            cfg = {}
            def download_report(doc_token):
                return _get(f"/open-apis/docx/v1/documents/{doc_token}/raw_content", TOK)
            def f():
                return cfg.get("/download")
        '''),
        "want": [],
    },
    {
        "name": "good-02 wrapper 实参运行时未知",
        "src": _fx('''
            TOK = "tok"
            def dl(u):
                return _get(u, TOK)
            def f(dynamic):
                return dl(dynamic)
        '''),
        "want": [],
    },
    {
        "name": "good-03 wrapper 转发的是非下载接口",
        "src": _fx('''
            TOK = "tok"
            def read_doc(token):
                return _get(f"/open-apis/docx/v1/documents/{token}/raw_content", TOK)
            def f():
                return read_doc("doc123")
        '''),
        "want": [],
    },
    {
        "name": "good-04 注释与 docstring",
        "src": _fx('''
            def f():
                """_get("https://x/download")"""
                # _get("https://x/download")
                return None
        '''),
        "want": [],
    },
]


def _extra_controls():
    """12 个 fixture 之外的判据反向对照：每条都喂会红/会闭嘴的样本。"""
    results = []

    tree = ast.parse('x = ("a", "b", "c", "d", "e", "f", "g", "h", "i")')
    candidates, params = resolve(tree.body[0].value, {})
    results.append((
        "候选超 8 条退化成未知",
        candidates == {UNKNOWN} and not params,
        "候选 {} 条".format(len(candidates)),
    ))

    long_source = 'x = "' + ("a" * (MAX_STRING + 1)) + '"'
    tree = ast.parse(long_source)
    candidates, _ = resolve(tree.body[0].value, {})
    results.append((
        "单串超 400 字符退化成未知",
        candidates == {UNKNOWN},
        "候选长度 {}".format(len(next(iter(candidates)))),
    ))

    count = len(scan_python_source(_fx('''
        def f(client):
            client.file.download_one()
    ''')))
    results.append(("SDK 精确白名单不误伤 download_one", count == 0, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f(cfg):
            return cfg.get("/download")
    ''')))
    results.append(("cfg.get 防误报", count == 0, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f(t):
            return _get(os.path.join(BASE, "drive/v1/files", t, "download"), TOK)
    ''')))
    results.append(("os.path.join 拼接必须能认出", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f(t):
            return _get("%s/drive/v1/files/%s/download" % (BASE, t), TOK)
    ''')))
    results.append(("% 格式化必须能认出", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f(t):
            return _get("{}/drive/v1/files/{}/download".format(BASE, t), TOK)
    ''')))
    results.append(("str.format 必须能认出", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f():
            return _get("{}".format("https://x/drive/v1/files/y/download"), TOK)
    ''')))
    results.append(("整串来自实参的 format 载体", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f():
            return _get("%s" % "https://x/drive/v1/files/y/download", TOK)
    ''')))
    results.append(("% 载体把右侧内容填回模板", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        def f():
            return _get(str("https://x/drive/v1/files/y/download"), TOK)
    ''')))
    results.append(("str(...) 载体顺手覆盖", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        TOK = "tok"
        def read_doc(u):
            return _get("https://x/open-apis/docx/v1/documents/raw?token=" + u, TOK)
        def f():
            return read_doc("https://x/drive/v1/files/y/download")
    ''')))
    results.append((
        "非下载 URL 的查询参不算 wrapper（防误报）",
        count == 0,
        "命中 {} 条".format(count),
    ))

    count = len(scan_python_source(_fx('''
        TOK = "tok"
        def dl(u):
            return _get(u, TOK)
        def f():
            return dl("https://x/drive/v1/files/y/download")
    ''')))
    results.append(("整串未知的 wrapper 必须能认出", count == 1, "命中 {} 条".format(count)))

    count = len(scan_python_source(_fx('''
        TOK = "tok"
        def dl(u):
            return _get(u, TOK)
        def wrap(v):
            return dl("https://x/drive" + v)
        def f():
            return wrap("/v1/files/y/download")
    ''')))
    results.append((
        "带常量前缀的 wrapper 转发也要能认出",
        count == 1,
        "命中 {} 条".format(count),
    ))

    return results


def _selftest():
    print("=" * 66)
    print("download_scan_py · 自证（12 个 fixture + 反向对照）")
    print("=" * 66)

    failures = 0
    for fixture in FIXTURES:
        got = scan_python_source(fixture["src"])
        got_key = sorted(
            (row["sink"], row["lineno"], row["shape"], row["symbol"])
            for row in got
        )
        want_key = sorted(fixture["want"])
        path_ok = all(row["path"] == "<probe>" for row in got)
        ok = (got_key == want_key) and path_ok
        if not ok:
            failures += 1
        print("  {} {}   期望 {} / 实得 {}".format(
            "✅" if ok else "❌", fixture["name"], want_key, got_key,
        ))

    controls = _extra_controls()
    for name, ok, detail in controls:
        if not ok:
            failures += 1
        print("  {} 反向对照：{}   {}".format("✅" if ok else "❌", name, detail))

    print("-" * 66)
    print("  fixture {} 个 / 反向对照 {} 个 / 失败 {}".format(
        len(FIXTURES), len(controls), failures,
    ))
    if failures:
        print("✗ 自证未通过")
        return 1
    print("✅ 自证全过")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Python 下载调用的轻量数据流扫描器",
    )
    parser.add_argument("--selftest", action="store_true", help="跑内嵌 fixture 与反向对照")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出扫描结果")
    parser.add_argument("paths", nargs="*", help="要扫描的 .py 文件或目录")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.paths:
        parser.print_help()
        return 2

    findings = scan_python_files([Path(p) for p in args.paths])
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=1))
    else:
        for row in findings:
            print("{path}:{lineno}:{col_offset} {symbol} {sink}/{shape} {api} [{marker}]".format(**row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
