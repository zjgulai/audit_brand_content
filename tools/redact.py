#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""redact.py —— 外发最小化：把「不该说出去的东西」替换成类型标记（T0-09 / G-6）

## 为什么是「替换」而不是「拦截」

外发消息（群回复、报告、错误自报）里混进凭据 / 个人信息时，正确动作是
**把那一小段换成标记后照常发送**，不是整条不发 —— 整条不发会让对方以为
「守衡没反应」，而回复里其余部分是有效的。所以接口是 `redact(text)` 返回
**可发送的文本** + **findings 列表**，不是抛异常。

## 判据在哪

`tools/verify_redact.py`：A 必拦 / B 必放（防「全拦」）/ C 规则承重（禁用一条 → 对应样本必须红）。

## 口径与已知边界（照实写）

  - **纯函数、纯标准库**：不联网、不读盘、不写盘。
  - **只认文本形态**（正则），不是语义判断。因此：
    * 手机号 / 外部链接里的数字：**URL 内部的号码不拦** —— `B3` 反向对照要求
      「URL 里的商品 ID 不得被误拦」，而 11 位商品 ID 与手机号形态可以完全相同。
      代价照实说：**一个被写进 URL 的手机号不会被脱敏**。电话通常出现在正文，
      这个取舍把误拦（业务不可用）换成了窄口径漏拦（已记录、可后续按上下文收紧）。
    * 护照只认 `[EG]` + 8 位（中国因私/因公常见形态），不追求全语种覆盖。
    * 身份证只认 18 位（含 X 尾），不认 15 位旧号。
  - finding **不带原文**：只有 `type / start / end / sha256[:16]`。
    `sha256` 是对**原文切片**的哈希，用于对账与去重，不可逆推短文本以外的内容。
  - `disabled` 参数只给判据用（验证「某条规则是否承重」），生产调用不要传。
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

# ── 规则表：**顺序 = 优先级**（先匹配到的先占位，后匹配的重叠段被丢弃）──────────
# 更具体的形态（sk- / wbk_ / Bearer / 栈帧）排在泛化的键值规则之前，
# 否则 `key=sk-…` 会被 credential_kv 整段吃掉，类型就报错了。
RULES = [
    # 凭据形态（具体令牌）
    ("api_key_sk", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), 0),
    ("feishu_wbk", re.compile(r"\bwbk_[A-Za-z0-9_\-]{10,}\b"), 0),
    ("bearer", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_\-\.=]{8,})"), 1),
    # 个人信息
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), 0),
    ("cn_id", re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"), 0),
    ("passport", re.compile(r"\b[EG]\d{8}\b"), 0),
    # E.164 放前面：`+14155552671` 也能被 phone_cn 的子串规则命中，
    # 先匹配更长的国际号，类型才不会被报成国内手机。
    ("phone_e164", re.compile(r"(?<![\w+])\+[1-9]\d{6,14}(?!\d)"), 0, {"no_url": True}),
    ("phone_cn", re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"), 0, {"no_url": True}),
    # 内部路径与调试痕迹
    ("stack_frame_file", re.compile(r'(?m)^\s*File\s+"([^"\n]+)",\s*line\s+\d+'), 1),
    ("stack_frame_at", re.compile(r"(?m)^\s+at\s+[^\n(]*\(([^()\n]+):\d+:\d+\)"), 1),
    ("abs_path", re.compile(r"""(?<![\w])(?:/Users|/home|/private/var|/var/folders)/[^\s"'`<>)]+"""), 0),
    ("home_secret_path", re.compile(r"""~/(?:\.dsh|\.ssh|\.aws|\.config/gh)(?:/[^\s"'`<>)]*)?"""), 0),
    ("tool_call_id", re.compile(r"(?i)\btool_call_id\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{8,}"), 0),
    ("tool_call_id", re.compile(r"\bcall_[A-Za-z0-9]{12,}\b"), 0),
    # 泛化的键值凭据（放最后：只兜住前面没接住的形态）
    ("credential_kv", re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?key|secret|token|password|passwd|pwd|"
        r"app[_-]?secret|client[_-]?secret)\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.\+/=]{8,})"), 1),
]

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


def _rule_parts(rule):
    """兼容 3 元 / 4 元规则写法。"""
    typ, pat, grp = rule[0], rule[1], rule[2]
    opt = rule[3] if len(rule) > 3 else {}
    return typ, pat, grp, opt


def _inside(span, spans) -> bool:
    s, e = span
    return any(s < b and e > a for a, b in spans)


def redact(text: str, *, disabled: Iterable[str] = ()) -> tuple[str, list[dict]]:
    """把敏感片段替换成 `[REDACTED:<type>]`。

    Args:
        text: 待外发文本。
        disabled: 仅判据使用 —— 禁用的规则类型集合（验证规则承重）。

    Returns:
        (safe_text, findings)。findings 每项：`type / start / end / sha256[:16]`，
        **不含原文**。
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    off = set(disabled or ())
    url_spans = [m.span() for m in URL_RE.finditer(text)]

    chosen: list[tuple[int, int, str]] = []
    for rule in RULES:
        typ, pat, grp, opt = _rule_parts(rule)
        if typ in off:
            continue
        for m in pat.finditer(text):
            if grp and m.lastindex and m.lastindex >= grp and m.group(grp) is not None:
                s, e = m.span(grp)
            else:
                s, e = m.span()
            if s >= e:
                continue
            if opt.get("no_url") and _inside((s, e), url_spans):
                continue
            if _inside((s, e), [(a, b) for a, b, _ in chosen]):
                continue
            chosen.append((s, e, typ))

    chosen.sort(key=lambda x: x[0])
    out: list[str] = []
    findings: list[dict] = []
    last = 0
    for s, e, typ in chosen:
        out.append(text[last:s])
        out.append("[REDACTED:%s]" % typ)
        findings.append({
            "type": typ,
            "start": s,
            "end": e,
            "sha256": hashlib.sha256(text[s:e].encode("utf-8")).hexdigest()[:16],
        })
        last = e
    out.append(text[last:])
    return "".join(out), findings


def redact_text(text: str) -> str:
    """只要安全文本的便捷包装（调用方不关心 findings 时用）。"""
    return redact(text)[0]
