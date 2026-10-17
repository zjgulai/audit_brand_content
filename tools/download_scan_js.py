#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_scan_js.py —— JavaScript / .mjs 下载调用扫描器

## 为什么单独有这个文件

Python 有 `ast`，JavaScript 没有标准库 AST。下载治理的 Python 侧可以靠 AST 定位
调用点，但本项目真正发下载请求的代码有相当一部分在 `.mjs` / `.js` 里
（SDK 调用、fetch、axios、https.request）。如果因为「没有解析器」就跳过 JS，
治理就会出现一整块结构性盲区 —— 而盲区不会报红，只会安静地漏。

所以这里做一个**最小词法分析**：把源码切成 token，剔除注释，在 token 流上
找「可疑调用 + 附近窗口内的 download 特征」。它不追求 JS 语法全覆盖，只追求
对下载调用这个形状足够敏感，同时不把普通 HTTP、日志、服务端路由误报成下载。

## 判据的边界（明着写，不假装覆盖）

已知残余：

1. **跨函数 / 跨文件传参的动态 URL**。本扫描器只看单文件 token 流。
   `buildUrl()` 在 A 文件、`fetch(u)` 在 B 文件时，下载标记不在窗口内，
   只能靠「所在函数名含 download」兜底。
2. **函数改名后签名兜底失效**。`downloadAttachment` 改成 `pullAsset`，
   且 URL 完全动态时，没有任何标记可依 —— 这是本文件明确接受的漏报面。
3. **计算属性键是变量**（`client[method](...)`）时无法判断是不是 download。
4. **值经多次赋值 / 解构 / 展开传递超过 3 跳**时不做完整数据流；
   3 跳以内用声明窗口递归解析。
5. **参数名本身含 download** 不作为证据：形参叫什么由调用方决定，
   把参数名当证据会在「形参遮蔽模块级同名变量」时误报。
   真要从参数里识别，只能靠函数名兜底。
6. **窗口有界**（16 行 / 260 token）：更远的声明会漏掉；实参里任意位置的
   download 字样都算证据（不区分 URL 位置与 header/body），这是有意偏向召回。
   误报面由「必须同时存在 HTTP sink」这一条兜住。

## 输出

输出字段与 Python 侧保持一致：

    {path, symbol, lineno, col_offset, sink, shape, api, marker}

- `path`       相对仓库根的路径（由 scan_js_files 计算）
- `symbol`     发起调用时所在的函数名；模块级调用为 `<module>`
- `lineno`     调用链起点所在行（1-based，和 Python ast.Call.lineno 同口径）
- `col_offset` 调用链起点所在列（0-based，UTF-8 字节偏移，和 Python
              ast.col_offset 同口径）
- `sink`       实际被判定为「发请求」的调用链
- `shape`      命中的形状，见 SHAPES
- `api`        可重建的接口描述：优先 URL/路径字面量，否则调用链
- `marker`     触发命中的 download 特征

## 自证

文件末尾内嵌 15 个 fixture（8 坏 7 好），另有 8 个「把 download 改掉就应变绿」
的反向对照和 3 个「好样本激活后应变红」的对照。直接运行：

    python3 tools/download_scan_js.py

退出码：0 全过 / 1 有断言失败。
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------- 常量

# 裸标识符调用里，哪些名字算「真的会发 HTTP」。
# 刻意不把任何 download* 放进来：本地工具函数 downloadOne() 必须保持绿色。
HTTP_BARE = {"fetch", "axios", "got", "request", "superagent", "needle", "ky"}

# 成员调用里，接收者（或链上任意一段）出现这些名字才可能是 HTTP 客户端。
HTTP_CARRIERS = {"http", "https", "axios", "got", "ky", "needle", "superagent"}

# 成员调用里，这些属性名是「发请求」的动词。
HTTP_METHOD_PROPS = {"get", "post", "request", "head", "stream"}

# SDK 风格的下载方法名。命中这些属性名本身就算 sink，不需要 URL 字面量。
SDK_DOWNLOAD_PROPS = {
    "download",
    "downloadfile",
    "getfile",
    "batchgettmpdownloadurl",
    "batchgettmpurl",
    "gettmpdownloadurl",
}

# Express / Koa 之类的服务端路由：`app.get("/download", handler)` 是把文件
# 发给客户端，不是从飞书取字节。不排除就会把服务端路由误报成下载。
EXPRESS_RECEIVERS = {"app", "router", "server", "express", "fastify", "koa", "web", "route"}

# `res.download()` / `reply.download()` 同理，是响应侧发送，不是下载侧接收。
RESPONSE_RECEIVERS = {"res", "response", "reply", "ctx"}

# 这些词后面跟 `(` 是控制结构或函数定义，不是调用。
CONTROL_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "with", "do", "else", "return",
    "typeof", "new", "delete", "void", "await", "yield", "function", "class",
    "import", "export", "const", "let", "var", "try", "finally", "throw",
}

JS_KEYWORDS = CONTROL_KEYWORDS | {
    "this", "true", "false", "null", "undefined", "in", "of", "instanceof",
    "break", "continue", "case", "default", "extends", "super", "static",
    "get", "set", "async", "debugger",
}

# 声明 / 赋值语句的结束判断用：在深度 0 遇到这些词，说明上一句没有分号也结束了。
STATEMENT_STARTERS = {
    "const", "let", "var", "function", "class", "export", "import", "async",
    "if", "for", "while", "return", "throw", "try", "switch",
}

# 窗口：要求「跨 5 行以上拼接」也能命中，所以行窗口必须大于 5；
# token 窗口用来防止一个大文件里把很远的同名变量误连起来。
WINDOW_LINES = 16
WINDOW_TOKENS = 260

# 声明递归解析的最大跳数：够覆盖「局部配置对象 -> url 变量 -> 模块级常量」，
# 再深就不是词法扫描器该做的事了。
MAX_RESOLVE_DEPTH = 3

SHAPES = (
    "template_literal",
    "sdk_chain",
    "concat_call",
    "axios_config",
    "optional_chain",
    "request_path",
    "computed_property",
    "func_name_fallback",
    "string_literal",
)


# ---------------------------------------------------------------- 词法

class _Tok:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return "_Tok({!r}, {!r}, {}:{})".format(self.kind, self.value, self.line, self.col)


_MULTI_PUNCT = (
    ">>>=", "===", "!==", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=",
    "...", "?.", "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>", "**",
)


class _Lexer:
    """够用的 JS 词法器：注释不产出 token，模板表达式折叠成占位符。"""

    def __init__(self, src):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1
        self.col = 0
        self.tokens = []
        self.last = None

    # ---- 基础游标

    def _peek(self, k=0):
        j = self.i + k
        return self.src[j] if j < self.n else ""

    def _adv(self, k=1):
        for _ in range(k):
            if self.i >= self.n:
                return
            if self.src[self.i] == "\n":
                self.line += 1
                self.col = 0
            else:
                self.col += 1
            self.i += 1

    # ---- 空白与注释

    def _skip_trivia(self):
        while self.i < self.n:
            c = self.src[self.i]
            if c in " \t\r\n\f\v\ufeff":
                self._adv(1)
                continue
            if c == "/" and self._peek(1) == "/":
                self._skip_line_comment()
                continue
            if c == "/" and self._peek(1) == "*":
                self._skip_block_comment()
                continue
            break

    def _skip_line_comment(self):
        while self.i < self.n and self.src[self.i] != "\n":
            self._adv(1)

    def _skip_block_comment(self):
        self._adv(2)
        while self.i < self.n:
            if self.src[self.i] == "*" and self._peek(1) == "/":
                self._adv(2)
                return
            self._adv(1)

    # ---- 转义与原始跳过（模板表达式内部用）

    def _read_escape(self):
        # 当前在反斜杠上。返回值只用于在字符串/模板里找 download 特征，
        # 所以常见转义解码到原字符即可，不追求完整的 Unicode 语义。
        self._adv(1)
        if self.i >= self.n:
            return ""
        c = self.src[self.i]
        mapping = {"n": "\n", "t": "\t", "r": "\r", "b": "\b",
                   "f": "\f", "v": "\v", "0": "\0"}
        if c in mapping:
            self._adv(1)
            return mapping[c]
        if c == "u":
            if self._peek(1) == "{":
                self._adv(2)
                start = self.i
                while self.i < self.n and self.src[self.i] != "}":
                    self._adv(1)
                hexs = self.src[start:self.i]
                self._adv(1)
                try:
                    return chr(int(hexs, 16))
                except ValueError:
                    return ""
            self._adv(1)
            hexs = self.src[self.i:self.i + 4]
            if len(hexs) == 4:
                self._adv(4)
                try:
                    return chr(int(hexs, 16))
                except ValueError:
                    return ""
            return ""
        if c == "x":
            self._adv(1)
            hexs = self.src[self.i:self.i + 2]
            if len(hexs) == 2:
                self._adv(2)
                try:
                    return chr(int(hexs, 16))
                except ValueError:
                    return ""
            return ""
        # 包括 \/ 与 \"：转义后就是那个字符本身
        self._adv(1)
        return c

    def _skip_quoted_raw(self, quote):
        self._adv(1)
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\":
                self._adv(2)
                continue
            self._adv(1)
            if c == quote:
                return

    def _skip_template_raw(self):
        self._adv(1)
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\":
                self._adv(2)
                continue
            if c == "`":
                self._adv(1)
                return
            if c == "$" and self._peek(1) == "{":
                self._adv(2)
                self._skip_template_expr()
                continue
            self._adv(1)

    def _skip_regex_raw(self):
        self._adv(1)
        in_class = False
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\":
                self._adv(2)
                continue
            if c == "\n":
                return
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                self._adv(1)
                while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] in "_$"):
                    self._adv(1)
                return
            self._adv(1)

    def _regex_allowed_at(self, pos):
        """模板表达式内部没有完整 token 流，用前一个非空字符做启发式判断。"""
        j = pos
        while j >= 0 and self.src[j] in " \t\r\n":
            j -= 1
        if j < 0:
            return True
        ch = self.src[j]
        if ch in ")]}":
            return False
        if ch.isalnum() or ch in "_$":
            k = j
            while k >= 0 and (self.src[k].isalnum() or self.src[k] in "_$"):
                k -= 1
            word = self.src[k + 1:j + 1]
            return word in ("return", "typeof", "instanceof", "in", "of", "new",
                            "delete", "void", "throw", "case", "do", "else",
                            "yield", "await")
        return True

    def _skip_template_expr(self):
        # 从 `${` 之后开始，一直跳到与之配对的 `}`。
        depth = 1
        while self.i < self.n:
            c = self.src[self.i]
            if c in "'\"":
                self._skip_quoted_raw(c)
                continue
            if c == "`":
                self._skip_template_raw()
                continue
            if c == "/" and self._peek(1) == "/":
                self._skip_line_comment()
                continue
            if c == "/" and self._peek(1) == "*":
                self._skip_block_comment()
                continue
            if c == "/" and self._regex_allowed_at(self.i - 1):
                self._skip_regex_raw()
                continue
            if c == "{":
                depth += 1
                self._adv(1)
                continue
            if c == "}":
                depth -= 1
                self._adv(1)
                if depth == 0:
                    return
                continue
            self._adv(1)

    # ---- 词法单元

    def _read_string(self, quote):
        line, col = self.line, self.col
        self._adv(1)
        buf = []
        while self.i < self.n:
            c = self.src[self.i]
            if c == quote:
                self._adv(1)
                break
            if c == "\\":
                buf.append(self._read_escape())
                continue
            if c == "\n":
                # 非法 JS，但词法器不能因此吞掉后面整个文件
                buf.append(c)
                self._adv(1)
                continue
            buf.append(c)
            self._adv(1)
        return _Tok("string", "".join(buf), line, col)

    def _read_template(self):
        line, col = self.line, self.col
        self._adv(1)
        parts = []
        buf = []
        while self.i < self.n:
            c = self.src[self.i]
            if c == "`":
                self._adv(1)
                break
            if c == "\\":
                buf.append(self._read_escape())
                continue
            if c == "$" and self._peek(1) == "{":
                # 常量段保留；表达式折叠成 NUL 占位符，避免把表达式里的
                # 标识符误当成 URL 常量的一部分。
                parts.append("".join(buf))
                buf = []
                self._adv(2)
                self._skip_template_expr()
                parts.append("\x00")
                continue
            buf.append(c)
            self._adv(1)
        parts.append("".join(buf))
        return _Tok("template", "".join(parts), line, col)

    def _read_regex(self):
        line, col = self.line, self.col
        start = self.i + 1
        self._adv(1)
        in_class = False
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\":
                self._adv(2)
                continue
            if c == "\n":
                break
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                raw = self.src[start:self.i]
                self._adv(1)
                while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] in "_$"):
                    self._adv(1)
                return _Tok("regex", raw, line, col)
            self._adv(1)
        return _Tok("regex", self.src[start:self.i], line, col)

    def _read_ident(self):
        line, col = self.line, self.col
        start = self.i
        self._adv(1)
        while self.i < self.n:
            c = self.src[self.i]
            if c.isalnum() or c in "_$":
                self._adv(1)
            else:
                break
        return _Tok("ident", self.src[start:self.i], line, col)

    def _read_number(self):
        line, col = self.line, self.col
        start = self.i
        if self.src[self.i] == ".":
            self._adv(1)
        while self.i < self.n:
            c = self.src[self.i]
            if c.isalnum() or c in "._":
                self._adv(1)
            elif c in "+-" and self.i > start and self.src[self.i - 1] in "eE":
                self._adv(1)
            else:
                break
        return _Tok("number", self.src[start:self.i], line, col)

    def _read_punct(self):
        line, col = self.line, self.col
        for p in _MULTI_PUNCT:
            if self.src.startswith(p, self.i):
                # `?.5` 是三元 + 小数，不是可选链
                if p == "?." and self._peek(2).isdigit():
                    break
                self._adv(len(p))
                return _Tok("punct", p, line, col)
        c = self.src[self.i]
        self._adv(1)
        return _Tok("punct", c, line, col)

    def _regex_allowed(self):
        prev = self.last
        if prev is None:
            return True
        if prev.kind == "punct":
            return prev.value not in (")", "]", "}")
        if prev.kind == "ident":
            return prev.value in ("return", "typeof", "instanceof", "in", "of",
                                  "new", "delete", "void", "throw", "case", "do",
                                  "else", "yield", "await")
        return False

    def lex(self):
        while self.i < self.n:
            self._skip_trivia()
            if self.i >= self.n:
                break
            c = self.src[self.i]
            if c in "'\"":
                t = self._read_string(c)
                self.tokens.append(t)
                self.last = t
            elif c == "`":
                t = self._read_template()
                self.tokens.append(t)
                self.last = t
            elif c == "/" and self._regex_allowed():
                t = self._read_regex()
                self.tokens.append(t)
                self.last = t
            elif c.isalpha() or c in "_$":
                t = self._read_ident()
                self.tokens.append(t)
                self.last = t
            elif c.isdigit() or (c == "." and self._peek(1).isdigit()):
                t = self._read_number()
                self.tokens.append(t)
                self.last = t
            else:
                t = self._read_punct()
                self.tokens.append(t)
                self.last = t
        return self.tokens


# ---------------------------------------------------------------- token 工具

def _is_p(t, value):
    return t.kind == "punct" and t.value == value


def _match_pair(tokens, open_idx):
    """返回与 open_idx 处开括号配对的闭括号下标。"""
    open_v = tokens[open_idx].value
    close_v = {"(": ")", "[": "]", "{": "}"}[open_v]
    depth = 0
    for k in range(open_idx, len(tokens)):
        t = tokens[k]
        if t.kind == "punct":
            if t.value == open_v:
                depth += 1
            elif t.value == close_v:
                depth -= 1
                if depth == 0:
                    return k
    return len(tokens) - 1


def _match_pair_back(tokens, close_idx):
    close_v = tokens[close_idx].value
    open_v = {")": "(", "]": "[", "}": "{"}[close_v]
    depth = 0
    for k in range(close_idx, -1, -1):
        t = tokens[k]
        if t.kind == "punct":
            if t.value == close_v:
                depth += 1
            elif t.value == open_v:
                depth -= 1
                if depth == 0:
                    return k
    return 0


def _statement_end(tokens, start):
    """返回语句结束 token 的下标（不含）。用于声明 RHS 的范围。"""
    depth = 0
    prev = None
    for k in range(start, len(tokens)):
        t = tokens[k]
        if t.kind == "punct":
            v = t.value
            if v in "([{":
                depth += 1
            elif v in ")]}":
                if depth == 0:
                    return k
                depth -= 1
            elif v == ";" and depth == 0:
                return k
        if (depth == 0 and prev is not None and t.line > prev.line
                and t.kind == "ident" and t.value in STATEMENT_STARTERS):
            return k
        prev = t
    return len(tokens)


# ---------------------------------------------------------------- 作用域

class _FuncRange:
    __slots__ = ("name", "start", "body_start", "body_end", "params")

    def __init__(self, name, start, body_start, body_end, params):
        self.name = name
        self.start = start
        self.body_start = body_start
        self.body_end = body_end
        self.params = params


def _collect_binding_names(seg):
    """从一个逗号分隔的形参片段里取绑定名。

    只取 `=` 之前的标识符，且跳过 `{ url: ... }` 里的属性键。
    多取一个默认值里的名字会错误地扩大遮蔽范围，所以这里宁可少取。
    """
    out = []
    depth = 0
    for idx, t in enumerate(seg):
        if t.kind == "punct":
            if t.value in "([{":
                depth += 1
            elif t.value in ")]}":
                depth -= 1
            elif t.value == "=" and depth == 0:
                break
            continue
        if t.kind != "ident" or t.value in JS_KEYWORDS:
            continue
        if idx + 1 < len(seg) and _is_p(seg[idx + 1], ":"):
            continue
        out.append(t.value)
        if depth == 0 and len(out) >= 1:
            # 普通形参只取第一个；解构形参才继续收
            if not any(_is_p(x, "{") or _is_p(x, "[") for x in seg[:idx + 1]):
                break
    return out


def _extract_params(tokens, lparen, rparen):
    params = set()
    segs = []
    seg = []
    depth = 0
    for k in range(lparen + 1, rparen):
        t = tokens[k]
        if t.kind == "punct" and t.value in "([{":
            depth += 1
        elif t.kind == "punct" and t.value in ")]}":
            depth -= 1
        if depth == 0 and t.kind == "punct" and t.value == ",":
            segs.append(seg)
            seg = []
        else:
            seg.append(t)
    segs.append(seg)
    for s in segs:
        params.update(_collect_binding_names(s))
    return params


def _build_func_ranges(tokens):
    """收集函数体范围与函数名。

    这里不追求完整 JS 语义，只需要两件事：
    1. 调用点归属哪个函数（`symbol`，以及函数名兜底）；
    2. 参数集合（形参遮蔽判据）。
    """
    ranges = []
    n = len(tokens)

    # function foo(...) { ... }
    for i, t in enumerate(tokens):
        if t.kind == "ident" and t.value == "function":
            j = i + 1
            if j < n and _is_p(tokens[j], "*"):
                j += 1
            name = "<anonymous>"
            if j < n and tokens[j].kind == "ident":
                name = tokens[j].value
                j += 1
            if j >= n or not _is_p(tokens[j], "("):
                continue
            rp = _match_pair(tokens, j)
            k = rp + 1
            while k < n and not _is_p(tokens[k], "{"):
                if _is_p(tokens[k], ";"):
                    break
                k += 1
            if k < n and _is_p(tokens[k], "{"):
                be = _match_pair(tokens, k)
                ranges.append(_FuncRange(name, i, k, be,
                                         _extract_params(tokens, j, rp)))

    # const name = (...) => { ... } / name => expr
    for i, t in enumerate(tokens):
        if not _is_p(t, "=>"):
            continue
        j = i + 1
        if j < n and _is_p(tokens[j], "{"):
            body_start = j
            body_end = _match_pair(tokens, j)
        else:
            body_start = j
            body_end = max(j, _statement_end(tokens, j) - 1)

        params = set()
        pstart = None
        if i > 0 and _is_p(tokens[i - 1], ")"):
            lp = _match_pair_back(tokens, i - 1)
            pstart = lp
            params = _extract_params(tokens, lp, i - 1)
        elif i > 0 and tokens[i - 1].kind == "ident":
            pstart = i - 1
            params = {tokens[i - 1].value}

        name = "<anonymous>"
        k = (pstart if pstart is not None else i) - 1
        if k >= 0 and tokens[k].kind == "ident" and tokens[k].value == "async":
            k -= 1
        if k >= 0 and _is_p(tokens[k], "="):
            k -= 1
            if k >= 0 and tokens[k].kind == "ident":
                name = tokens[k].value
        elif k >= 0 and _is_p(tokens[k], ":"):
            k -= 1
            if k >= 0 and tokens[k].kind == "ident":
                name = tokens[k].value
        ranges.append(_FuncRange(name, i, body_start, body_end, params))

    # 对象 / 类里的方法简写：name(...) { ... }
    for i, t in enumerate(tokens):
        if not _is_p(t, "(") or i == 0 or tokens[i - 1].kind != "ident":
            continue
        name = tokens[i - 1].value
        if name in CONTROL_KEYWORDS:
            continue
        rp = _match_pair(tokens, i)
        if rp + 1 >= n or not _is_p(tokens[rp + 1], "{"):
            continue
        prev = tokens[i - 2] if i >= 2 else None
        defined = prev is None
        if prev is not None:
            if prev.kind == "punct" and prev.value in ("{", ",", ";", "}"):
                defined = True
            elif prev.kind == "ident" and prev.value in ("static", "async", "get", "set"):
                defined = True
            elif prev.kind == "punct" and prev.value == "*":
                defined = True
        if defined:
            be = _match_pair(tokens, rp + 1)
            ranges.append(_FuncRange(name, i - 1, rp + 1, be,
                                     _extract_params(tokens, i, rp)))
    return ranges


def _scope_of(ranges, idx):
    best = None
    for r in ranges:
        if r.body_start <= idx <= r.body_end:
            if best is None or r.body_start > best.body_start:
                best = r
    return best


def _containing_ranges(ranges, idx):
    out = [r for r in ranges if r.body_start <= idx <= r.body_end]
    out.sort(key=lambda r: r.body_start, reverse=True)
    return out


def _symbol_at(ranges, idx):
    # 匿名箭头（Promise executor、map 回调等）没有名字，把它当成符号会让
    # `symbol` 字段变成 <anonymous>，治理登记表里没法定位。这里跳过匿名
    # 范围，落到最近的有名函数；整条链都匿名时才算模块级。
    best = None
    for r in ranges:
        if r.name == "<anonymous>":
            continue
        if r.body_start <= idx <= r.body_end:
            if best is None or r.body_start > best.body_start:
                best = r
    return best.name if best is not None else "<module>"


# ---------------------------------------------------------------- 声明与解析

def _build_declarations(tokens, ranges):
    decls = []
    n = len(tokens)
    for i, t in enumerate(tokens):
        if t.kind != "ident":
            continue
        if t.value in ("const", "let", "var"):
            j = i + 1
            # 解构声明不做完整绑定分析：这里只服务值追踪，不追求全覆盖。
            if j < n and tokens[j].kind == "ident":
                name = tokens[j].value
                if j + 1 < n and _is_p(tokens[j + 1], "="):
                    rhs_start = j + 2
                    rhs_end = _statement_end(tokens, rhs_start)
                    decls.append({"name": name, "idx": j, "rhs_start": rhs_start,
                                  "rhs_end": rhs_end, "scope": _scope_of(ranges, j)})
        elif t.value not in JS_KEYWORDS and i + 1 < n and _is_p(tokens[i + 1], "="):
            prev = tokens[i - 1] if i > 0 else None
            if prev is None or (prev.kind == "punct" and prev.value in (";", "{", "}")):
                rhs_start = i + 2
                rhs_end = _statement_end(tokens, rhs_start)
                decls.append({"name": t.value, "idx": i, "rhs_start": rhs_start,
                              "rhs_end": rhs_end, "scope": _scope_of(ranges, i)})
    return decls


def _resolve_ident(tokens, decls, ranges, name, ref_idx):
    """返回 ("param", None) / ("decl", decl) / ("free", None)。

    形参优先于外层声明：形参遮蔽模块级同名变量时，模块级那个下载 URL
    不能拿来给形参作证 —— 这正是 G7 要守住的误报面。
    """
    containing = _containing_ranges(ranges, ref_idx)
    if containing and name in containing[0].params:
        return "param", None

    ref_line = tokens[ref_idx].line
    best = None
    for d in decls:
        if d["name"] != name or d["idx"] >= ref_idx:
            continue
        sc = d["scope"]
        if sc is not None and not (sc.body_start <= ref_idx <= sc.body_end):
            continue
        if ref_line - tokens[d["idx"]].line > WINDOW_LINES:
            continue
        if ref_idx - d["idx"] > WINDOW_TOKENS:
            continue
        if best is None or d["idx"] > best["idx"]:
            best = d
    if best is not None:
        return "decl", best

    # 内层没有声明，再看外层形参；参数名本身仍不算下载证据。
    for r in containing[1:]:
        if name in r.params:
            return "param", None
    return "free", None


# ---------------------------------------------------------------- 标记

class _Evidence:
    __slots__ = ("marker", "source", "idx")

    def __init__(self, marker, source, idx):
        self.marker = marker
        self.source = source
        self.idx = idx


def _string_marker(text):
    """在字符串 / 模板常量段里找下载特征。

    长串优先，保证 marker 字段报出来的是最具体的那一个，而不是笼统的
    `download`。
    """
    low = text.lower()
    for m in ("batch_get_tmp_download_url", "batch_get_tmp_url",
              "gettmpdownloadurl", "/medias/", "/download", "download"):
        if m in low:
            return m
    return None


def _skip_arrow_expr(tokens, start, end):
    """跳过无大括号的箭头函数体，避免回调里的日志文案被当成 URL 证据。"""
    j = start
    depth = 0
    while j < end:
        t = tokens[j]
        if t.kind == "punct":
            v = t.value
            if v in "([{":
                depth += 1
            elif v in ")]}":
                if depth == 0:
                    return j
                depth -= 1
            elif v in (",", ";") and depth == 0:
                return j
        j += 1
    return j


def _collect_markers(tokens, start, end, decls, ranges, depth, visited):
    """扫描一段 token，返回 (证据列表, 形状标志)。

    这段既可能是调用的实参，也可能是某个变量的声明 RHS。递归解析
    `const cfg = { url: attachmentUrl }` 这种一跳以上的间接引用。
    """
    ev = []
    flags = {"concat": False, "url_key": False, "path_key": False}
    k = start
    while k < end:
        t = tokens[k]

        # 回调函数体不是这个调用的 URL，跳过，避免日志文案误报
        if t.kind == "ident" and t.value == "function":
            j = k + 1
            while j < end and not _is_p(tokens[j], "{"):
                j += 1
            if j < end:
                k = _match_pair(tokens, j) + 1
                continue
        if _is_p(t, "=>"):
            j = k + 1
            if j < end and _is_p(tokens[j], "{"):
                k = _match_pair(tokens, j) + 1
                continue
            k = _skip_arrow_expr(tokens, j, end)
            continue

        if t.kind in ("string", "template"):
            m = _string_marker(t.value)
            if m:
                ev.append(_Evidence(m, t.kind, k))
            k += 1
            continue

        if t.kind == "regex":
            k += 1
            continue

        if _is_p(t, "+"):
            flags["concat"] = True
            k += 1
            continue

        if t.kind == "ident":
            name = t.value
            prev = tokens[k - 1] if k > start else None
            nxt = tokens[k + 1] if k + 1 < end else None

            is_key = (nxt is not None and _is_p(nxt, ":")
                      and prev is not None and prev.kind == "punct"
                      and prev.value in ("{", ","))
            if is_key:
                if name in ("url", "path"):
                    flags[name + "_key"] = True
                k += 1
                continue

            # 对象简写 { url } / { path }
            if (prev is not None and prev.kind == "punct" and prev.value in ("{", ",")
                    and nxt is not None and nxt.kind == "punct"
                    and nxt.value in (",", "}")):
                if name in ("url", "path"):
                    flags[name + "_key"] = True

            if name in JS_KEYWORDS:
                k += 1
                continue

            # 属性访问 obj.downloadUrl：名字里的 download 仍是弱证据
            if prev is not None and prev.kind == "punct" and prev.value in (".", "?."):
                if "download" in name.lower():
                    ev.append(_Evidence(name, "ident", k))
                k += 1
                continue

            kind, d = _resolve_ident(tokens, decls, ranges, name, k)
            # 形参名不算证据（G7 的误报面）；其余绑定的名字含 download 时，
            # 即使值在窗口外也先记一条弱证据 —— URL 完全动态的下载函数
            # 往往只能靠这种弱证据被看见。
            if kind != "param" and "download" in name.lower():
                ev.append(_Evidence(name, "ident", k))
            if kind == "decl" and depth < MAX_RESOLVE_DEPTH:
                key = (name, d["idx"])
                if key not in visited:
                    visited.add(key)
                    sub_ev, sub_flags = _collect_markers(
                        tokens, d["rhs_start"], d["rhs_end"],
                        decls, ranges, depth + 1, visited)
                    ev.extend(sub_ev)
                    for f in flags:
                        flags[f] = flags[f] or sub_flags[f]
            k += 1
            continue

        k += 1
    return ev, flags


# ---------------------------------------------------------------- 调用解析

def _parse_callee(tokens, open_idx):
    """从 `(` 往回解析调用链，返回 (components, optional, computed, start_idx)。

    component 是 (值, 是否计算属性, token 下标)。计算属性只保留字符串键，
    变量键记成 <name>，这样 `client["drive"]["files"]["download"]` 与
    `client[method]` 在输出里能区分开。
    """
    j = open_idx - 1
    if j < 0:
        return None
    comps = []
    optional = False
    computed = False
    just_computed = False
    while True:
        t = tokens[j]
        if t.kind == "ident":
            comps.append((t.value, False, j))
            j -= 1
            just_computed = False
        elif t.kind == "punct" and t.value == "]":
            depth = 1
            k = j - 1
            inner = []
            while k >= 0:
                tk = tokens[k]
                if tk.kind == "punct" and tk.value == "]":
                    depth += 1
                elif tk.kind == "punct" and tk.value == "[":
                    depth -= 1
                    if depth == 0:
                        break
                inner.append(tk)
                k -= 1
            if depth != 0:
                return None
            inner.reverse()
            if len(inner) == 1 and inner[0].kind == "string":
                val = inner[0].value
            elif len(inner) == 1 and inner[0].kind == "ident":
                val = "<" + inner[0].value + ">"
            else:
                val = "<expr>"
            comps.append((val, True, k))
            computed = True
            just_computed = True
            j = k - 1
        else:
            break

        # 计算属性之间可以不写点：client["a"]["b"]；
        # 计算属性前面也可以直接跟基对象：client["a"]。
        if j >= 0 and tokens[j].kind == "punct" and tokens[j].value in (".", "?."):
            if tokens[j].value == "?.":
                optional = True
            j -= 1
            continue
        if just_computed and j >= 0 and tokens[j].kind == "ident":
            continue
        if j >= 0 and tokens[j].kind == "punct" and tokens[j].value == "]":
            continue
        break

    if not comps:
        return None
    comps.reverse()
    return comps, optional, computed, comps[0][2]


def _chain_text(comps):
    out = ""
    for value, is_computed, _ in comps:
        if is_computed:
            if value.startswith("<") and value.endswith(">"):
                out += "[" + value + "]"
            else:
                out += '["' + value + '"]'
        else:
            out += ("." if out else "") + value
    return out


def _classify_sink(comps):
    """返回 (kind, chain_text) 或 None。kind: bare / http / sdk。"""
    lows = [c[0].lower() for c in comps]
    last = lows[-1]
    text = _chain_text(comps)

    if last in SDK_DOWNLOAD_PROPS:
        # res.download / reply.download 是响应侧发送文件，不是取字节
        if last == "download" and lows[0] in RESPONSE_RECEIVERS:
            return None
        return "sdk", text

    if len(lows) == 1:
        if last in HTTP_BARE:
            return "bare", text
        return None

    if last in HTTP_METHOD_PROPS:
        # Express 路由不是出站下载
        if lows[0] in EXPRESS_RECEIVERS:
            return None
        if any(v in HTTP_CARRIERS for v in lows[:-1]):
            return "http", text
        if lows[0] in ("client", "api"):
            return "http", text
        return None
    return None


def _first_arg_range(tokens, open_idx, close_idx):
    start = open_idx + 1
    if start >= close_idx:
        return start, start
    depth = 0
    k = start
    while k < close_idx:
        t = tokens[k]
        if t.kind == "punct":
            if t.value in "([{":
                depth += 1
            elif t.value in ")]}":
                depth -= 1
            elif t.value == "," and depth == 0:
                return start, k
        k += 1
    return start, close_idx


def _object_prop_range(tokens, start, end, key):
    if start >= end or not _is_p(tokens[start], "{"):
        return None
    k = start + 1
    depth = 1
    while k < end:
        t = tokens[k]
        if t.kind == "punct":
            if t.value in "([{":
                depth += 1
            elif t.value in ")]}":
                depth -= 1
                if depth == 0:
                    break
        if depth == 1 and t.kind == "ident" and t.value == key:
            nxt = tokens[k + 1] if k + 1 < end else None
            if nxt is not None and _is_p(nxt, ":"):
                vstart = k + 2
                vend = vstart
                d = 0
                while vend < end:
                    tv = tokens[vend]
                    if tv.kind == "punct":
                        if tv.value in "([{":
                            d += 1
                        elif tv.value in ")]}":
                            if d == 0:
                                break
                            d -= 1
                        elif tv.value == "," and d == 0:
                            break
                    vend += 1
                return vstart, vend
            if nxt is not None and nxt.kind == "punct" and nxt.value in (",", "}"):
                return k, k + 1
        k += 1
    return None


def _preview(tokens, start, end, limit=120):
    parts = []
    for t in tokens[start:end]:
        if t.kind in ("string", "template"):
            parts.append('"' + t.value.replace("\x00", "${…}") + '"')
        else:
            parts.append(t.value)
    return " ".join(parts)[:limit]


def _api_text(tokens, open_idx, close_idx, chain):
    start, end = _first_arg_range(tokens, open_idx, close_idx)
    if start < end:
        if end == start + 1 and tokens[start].kind in ("string", "template"):
            return tokens[start].value.replace("\x00", "${…}")[:160]
        for key in ("url", "path"):
            rng = _object_prop_range(tokens, start, end, key)
            if rng is not None:
                return (chain + " " + key + "=" + _preview(tokens, rng[0], rng[1]))[:160]
    return chain[:160]


def _shape_of(sink_kind, comps, optional, computed, flags, evidences):
    if computed:
        return "computed_property"
    if optional:
        return "optional_chain"
    if sink_kind == "sdk":
        return "sdk_chain"
    if sink_kind == "bare" and comps[-1][0].lower() == "axios" and flags["url_key"]:
        return "axios_config"
    if sink_kind == "http" and flags["path_key"]:
        return "request_path"
    # 函数名兜底不携带 URL 形状：`client.basePath + token` 里虽然有 `+`，
    # 但它没有 download 特征，不能因此把兜底误标成 concat_call。
    concrete = [e for e in evidences if e.source != "func"]
    if any(e.source == "template" for e in concrete):
        return "template_literal"
    if flags["concat"] and concrete:
        return "concat_call"
    if evidences and all(e.source == "func" for e in evidences):
        return "func_name_fallback"
    return "string_literal"


def _byte_col(src, line, char_col):
    """把词法器的字符列号换成 Python ast 同口径的 UTF-8 字节列号。

    词法器按字符推进（中文在源码里是 1 个字符、3 个字节），而 Python 的
    ast.col_offset 是 UTF-8 字节偏移。两者只在列前有非 ASCII 字符时不同；
    这里统一成字节口径，避免下游按 `path:line:col` 对不上。
    """
    start = 0
    for _ in range(line - 1):
        nl = src.find("\n", start)
        if nl < 0:
            return char_col
        start = nl + 1
    end = src.find("\n", start)
    if end < 0:
        end = len(src)
    prefix = src[start:min(start + char_col, end)]
    return len(prefix.encode("utf-8"))


def scan_js_source(src: str, rel: str = "<probe>") -> list[dict]:
    """扫描一段 JS/ESM 源码，返回可疑下载调用列表。"""
    if src.startswith("\ufeff"):
        src = src[1:]
    tokens = _Lexer(src).lex()
    ranges = _build_func_ranges(tokens)
    decls = _build_declarations(tokens, ranges)

    hits = []
    for i, t in enumerate(tokens):
        if not _is_p(t, "("):
            continue
        parsed = _parse_callee(tokens, i)
        if parsed is None:
            continue
        comps, optional, computed, start_idx = parsed

        # 函数定义 / 方法定义不是调用：`function fetch(...) {` 不能因名字像
        # HTTP 助手就被当成一次请求。
        prev = tokens[start_idx - 1] if start_idx > 0 else None
        if prev is not None and prev.kind == "ident" and prev.value in ("function", "class"):
            continue
        if comps[0][0] in CONTROL_KEYWORDS:
            continue
        close_idx = _match_pair(tokens, i)
        if len(comps) == 1 and close_idx + 1 < len(tokens) \
                and _is_p(tokens[close_idx + 1], "{"):
            continue

        classified = _classify_sink(comps)
        if classified is None:
            continue
        sink_kind, sink_text = classified

        evidences = []
        for value, is_computed, idx in comps:
            low = value.lower()
            if "download" in low or low in ("getfile", "batchgettmpurl", "gettmpdownloadurl"):
                evidences.append(_Evidence(value, "chain", idx))

        arg_ev, flags = _collect_markers(
            tokens, i + 1, close_idx, decls, ranges, 0, set())
        evidences.extend(arg_ev)

        symbol = _symbol_at(ranges, start_idx)
        if not evidences:
            # URL 完全动态时，函数名是最后一根拐杖。往上找而不只看最内层：
            # 真实的下载入口常是 `downloadImage()`，真正发请求的是它内嵌的
            # `fetchOnce()`；只看最内层会让这个形状整块漏掉。
            for r in _containing_ranges(ranges, start_idx):
                if r.name not in ("<module>", "<anonymous>") \
                        and "download" in r.name.lower():
                    evidences.append(_Evidence("func:" + r.name, "func", start_idx))
                    break

        if not evidences:
            continue

        shape = _shape_of(sink_kind, comps, optional, computed, flags, evidences)
        marker = evidences[0].marker
        hits.append({
            "path": rel,
            "symbol": symbol,
            "lineno": tokens[start_idx].line,
            "col_offset": _byte_col(src, tokens[start_idx].line, tokens[start_idx].col),
            "sink": sink_text,
            "shape": shape,
            "api": _api_text(tokens, i, close_idx, sink_text),
            "marker": marker,
        })

    hits.sort(key=lambda h: (h["lineno"], h["col_offset"], h["sink"]))
    return hits


def scan_js_files(paths: list[Path]) -> list[dict]:
    """扫描一组文件。paths 是文件路径；目录遍历由调用方负责。

    读不了的文件不静默跳过：让它抛出去，由调用方按「未测 ≠ 通过」处理。
    """
    root = Path(__file__).resolve().parent.parent
    out = []
    for raw in paths:
        p = Path(raw)
        try:
            rel = p.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = p.as_posix()
        src = p.read_text(encoding="utf-8", errors="replace")
        out.extend(scan_js_source(src, rel))
    out.sort(key=lambda h: (h["path"], h["lineno"], h["col_offset"]))
    return out


# ---------------------------------------------------------------- fixture

def _src(text):
    return textwrap.dedent(text).strip("\n")


_B1 = _src("""
    // B1 模板字符串 + fetch
    export async function pull(token) {
      return fetch(
        `https://open.feishu.cn/open-apis/drive/v1/files/${token}/download`
      );
    }
""")

_B2 = _src("""
    // B2 SDK 方法链（无 URL 字面量）
    async function fetchAttachment(client, fileToken) {
      return client.drive.v1.files.download({ file_token: fileToken });
    }
""")

_B3 = _src("""
    // B3 变量拼接 + http.get，跨 5 行以上
    const API_BASE = "https://open.feishu.cn/open-apis";

    const fileUrl =
      API_BASE +
      "/drive/v1/files/" +
      process.env.TOKEN +
      "/download";

    function grab() {
      return http.get(fileUrl, onDone);
    }
""")

_B4 = _src("""
    // B4 axios 配置对象里的 url 变量
    const attachmentUrl =
      baseUrl + "/drive/v1/files/" + token + "/download";

    async function pullOne(token) {
      const cfg = { url: attachmentUrl, method: "GET" };
      return axios(cfg);
    }
""")

_B5 = _src("""
    // B5 可选链
    async function pullOpt(client, fileToken) {
      return client?.drive?.files?.downloadFile({ file_token: fileToken });
    }
""")

_B6 = _src("""
    // B6 https.request 配置对象 path 跨行拼接
    function requestFile(token) {
      const path =
        "/open-apis/drive/v1/files/" +
        token +
        "/download";
      const options = { path, method: "GET" };
      return https.request(options, onResponse);
    }
""")

_B7 = _src("""
    // B7 计算属性访问
    function pullComputed(client, fileToken) {
      return client["drive"]["files"]["download"]({ file_token: fileToken });
    }
""")

_B8 = _src("""
    // B8 URL 完全动态，靠函数名兜底
    async function downloadAttachment(client, token) {
      const u = client.basePath + token;
      return fetch(u);
    }
""")

_G1 = _src("""
    // G1 注释与 JSDoc 里的下载写法
    /**
     * 下载附件：fetch(`/drive/v1/files/${token}/download`)
     * 也调用 client.drive.v1.files.download({ file_token })
     */
    export function noop(token) {
      /* http.get("/open-apis/drive/v1/files/" + token + "/download") */
      return token;
    }
""")

_G2 = _src("""
    // G2 变量名/函数名含 download，但没有调用
    const downloadUrl = "/drive/v1/files/placeholder";
    function downloadHelper() {
      return downloadUrl;
    }
    export const downloadConfig = { retries: 2 };
""")

_G3 = _src("""
    // G3 真发 HTTP，但只读元数据
    async function readMeta(client, tokens) {
      const metaUrl = `${client.baseUrl}/open-apis/drive/v1/metas/batch_query`;
      return fetch(metaUrl, { method: "POST", body: JSON.stringify(tokens) });
    }
""")

_G4 = _src(r"""
    // G4 正则字面量与日志文案含 download
    const downloadPath = /\/drive\/v1\/files\/[^/]+\/download/;
    function logIt(name) {
      console.log("download finished: " + name);
      return downloadPath.test(name);
    }
""")

_G5 = _src("""
    // G5 本地 download 前缀函数被调用
    function downloadOne(name) {
      return cache[name] || null;
    }
    export function getLocal(name) {
      return downloadOne(name);
    }
""")

_G6 = _src("""
    // G6 Express 服务端路由
    export function mount(app, handler) {
      app.get("/download", handler);
      app.get("/open-apis/drive/v1/metas/batch_query", handler);
      return app;
    }
""")

_G7 = _src("""
    // G7 形参遮蔽模块级同名变量
    const downloadUrl =
      "https://open.feishu.cn/open-apis/drive/v1/files/real/download";

    export function readMeta(downloadUrl) {
      return fetch(downloadUrl + "/open-apis/drive/v1/metas/batch_query");
    }
""")


_FIXTURES = [
    {"id": "B1", "kind": "bad", "why": "模板字符串 + fetch",
     "src": _B1, "lines": [3], "shapes": ["template_literal"]},
    {"id": "B2", "kind": "bad", "why": "SDK 方法链，无 URL 字面量",
     "src": _B2, "lines": [3], "shapes": ["sdk_chain"]},
    {"id": "B3", "kind": "bad", "why": "变量拼接 + http.get，跨 5 行以上",
     "src": _B3, "lines": [11], "shapes": ["concat_call"]},
    {"id": "B4", "kind": "bad", "why": "axios 配置对象里的 url 变量",
     "src": _B4, "lines": [7], "shapes": ["axios_config"]},
    {"id": "B5", "kind": "bad", "why": "可选链",
     "src": _B5, "lines": [3], "shapes": ["optional_chain"]},
    {"id": "B6", "kind": "bad", "why": "https.request 的 path 跨行拼接",
     "src": _B6, "lines": [8], "shapes": ["request_path"]},
    {"id": "B7", "kind": "bad", "why": "计算属性访问",
     "src": _B7, "lines": [3], "shapes": ["computed_property"]},
    {"id": "B8", "kind": "bad", "why": "URL 完全动态，函数名兜底",
     "src": _B8, "lines": [4], "shapes": ["func_name_fallback"]},

    {"id": "G1", "kind": "good", "why": "注释与 JSDoc 里的下载写法",
     "src": _G1, "lines": [], "shapes": []},
    {"id": "G2", "kind": "good", "why": "变量名/函数名含 download 但没有调用",
     "src": _G2, "lines": [], "shapes": []},
    {"id": "G3", "kind": "good", "why": "真发 HTTP 但只读元数据",
     "src": _G3, "lines": [], "shapes": []},
    {"id": "G4", "kind": "good", "why": "正则字面量与日志文案含 download",
     "src": _G4, "lines": [], "shapes": []},
    {"id": "G5", "kind": "good", "why": "本地 download 前缀函数被调用",
     "src": _G5, "lines": [], "shapes": []},
    {"id": "G6", "kind": "good", "why": "Express 服务端路由",
     "src": _G6, "lines": [], "shapes": []},
    {"id": "G7", "kind": "good", "why": "形参遮蔽模块级同名变量",
     "src": _G7, "lines": [], "shapes": []},
]

# 坏样本的调用起点都在两格缩进 + `return ` 之后，列固定 9。
# 把列也断言上：调用链前缀解析一旦丢了 base（比如把 `client["drive"]…`
# 的 client 漏掉），行号仍然对，只有 col_offset 会漂。
for _f in _FIXTURES:
    _f["cols"] = [9] * len(_f["lines"]) if _f["kind"] == "bad" else []

# 好样本「激活」对照：证明它们绿是因为没有下载特征，而不是因为扫描器
# 根本没认出里面的 HTTP 调用。每条都只改一处，改完必须恰好 1 命中。
_ACTIVATIONS = [
    {"id": "G3+", "why": "元数据 URL 换成下载 URL 后必须红",
     "src": _G3.replace("metas/batch_query", "files/x/download"),
     "lines": [4]},
    {"id": "G6+", "why": "app.get 换成 https.get 后必须红",
     "src": _G6.replace("app.get", "https.get"),
     "lines": [3]},
    {"id": "G7+", "why": "去掉形参遮蔽后，模块级下载 URL 必须被认出来",
     "src": _G7.replace("function readMeta(downloadUrl)", "function readMeta(name)")
              .replace('fetch(downloadUrl + "/open-apis/drive/v1/metas/batch_query")',
                       "fetch(downloadUrl)"),
     "lines": [6]},
]

_REQUIRED_KEYS = ("path", "symbol", "lineno", "col_offset", "sink", "shape", "api", "marker")


def _run_fixture(f, path):
    hits = scan_js_source(f["src"], path)
    lines = [h["lineno"] for h in hits]
    cols = [h["col_offset"] for h in hits]
    shapes = [h["shape"] for h in hits]
    problems = []
    if lines != f["lines"]:
        problems.append("行号 {} != 期望 {}".format(lines, f["lines"]))
    if cols != f["cols"]:
        problems.append("列号 {} != 期望 {}".format(cols, f["cols"]))
    if shapes != f["shapes"]:
        problems.append("形状 {} != 期望 {}".format(shapes, f["shapes"]))
    for h in hits:
        for key in _REQUIRED_KEYS:
            if key not in h:
                problems.append("缺字段 {}".format(key))
        if h["shape"] not in SHAPES:
            problems.append("未知 shape {}".format(h["shape"]))
        if not isinstance(h["lineno"], int) or h["lineno"] < 1:
            problems.append("lineno 非法 {}".format(h["lineno"]))
        if not isinstance(h["col_offset"], int) or h["col_offset"] < 0:
            problems.append("col_offset 非法 {}".format(h["col_offset"]))
        if not h["sink"] or not h["marker"] or not h["path"]:
            problems.append("sink/marker/path 为空")
    return hits, problems


def _selftest():
    checks = []

    for f in _FIXTURES:
        hits, problems = _run_fixture(f, f["id"])
        ok = not problems
        detail = "{} 命中 @ {} {}".format(
            len(hits), [h["lineno"] for h in hits],
            ",".join(sorted(set(h["shape"] for h in hits))) or "-")
        checks.append((f["id"], f["why"], ok, detail + ("" if ok else "；" + "；".join(problems))))

    # 反向对照 1：把每个坏样本里的 download 改成 metadata，必须全绿。
    # 这证明命中不是「只要有 fetch 就红」，而是 download 特征真的在起作用。
    for f in _FIXTURES:
        if f["kind"] != "bad":
            continue
        neg = f["src"].replace("download", "metadata").replace("Download", "Metadata")
        hits = scan_js_source(neg, f["id"] + "-neg")
        ok = len(hits) == 0
        checks.append((f["id"] + "-", "去掉 download 特征后必须绿", ok,
                       "{} 命中".format(len(hits))))

    # 反向对照 2：好样本激活。证明 G3/G6/G7 的绿不是因为 sink 没被识别。
    for a in _ACTIVATIONS:
        hits = scan_js_source(a["src"], a["id"])
        lines = [h["lineno"] for h in hits]
        ok = lines == a["lines"]
        checks.append((a["id"], a["why"], ok,
                       "行号 {} != 期望 {}".format(lines, a["lines"]) if not ok
                       else "{} 命中 @ {}".format(len(hits), lines)))

    total = len(checks)
    passed = sum(1 for _, _, ok, _ in checks if ok)
    print("=" * 72)
    print("download_scan_js.py 自证 · {} 项（15 fixtures = 8 坏 + 7 好，另加 11 条反向对照）".format(total))
    print("=" * 72)
    for cid, why, ok, detail in checks:
        print("  {} {:<5} {:<34} {}".format("✅" if ok else "❌", cid, why, detail))
    print("-" * 72)
    if passed == total:
        print("✅ {} 项全过".format(total))
        return 0
    print("❌ {}/{} 项通过，{} 项失败".format(passed, total, total - passed))
    return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "--selftest" in argv:
        return _selftest()
    if argv[0] == "--json":
        hits = scan_js_files([Path(a) for a in argv[1:]])
        print(json.dumps(hits, ensure_ascii=False, indent=1))
        return 0
    hits = scan_js_files([Path(a) for a in argv])
    for h in hits:
        print("{}:{}:{}  {} [{}] marker={} api={}".format(
            h["path"], h["lineno"], h["col_offset"],
            h["sink"], h["shape"], h["marker"], h["api"]))
    print("共 {} 个可疑下载调用".format(len(hits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
