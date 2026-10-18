#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""send_gateway.py —— 唯一形态决策点与唯一发送兜底点（AGENTS.md §2.5 / L4-4）

**为什么要有这一份 Python 核心**：真正的发送在 Node（`tools/ws_daemon.mjs::replyTo`）。
但「形态怎么定、降级到哪、超限怎么搬」这三件事此前只活在 Node 里，
**没有任何独立可测的判断核心** —— 于是关于它的契约只能靠读那段 200 行注释来理解。

本文件把那三个判断抽成纯函数，可由 Python 直接测。Node 侧保持唯一执行者的身份不变
（形态决策仍然只在 `replyTo` 里做，§2.5 未变）。

--------------------------------------------------------------------------
★ 四条本文件刻意做死的事
--------------------------------------------------------------------------

**一、形态决策是纯函数：同一输入恒定同一形态**

    `decide_mode()` 不读时间、不读随机数、不读环境。
    这是可测的前提，也是「群里格式随机」这类故障的反面。

**二、卡片被拒 → 降级纯文本，不是消失**

    降级链只有一条（与 `replyTo` 一致）：
        有卡片 → 发卡  ──失败──→ 发降级文本（正文 = 卡的降级文本）
        没有卡 → 发文本 ──失败──→ 补发

    ★ 降级目标必须是「同一条引用里的纯文本」，**不是新发一条** ——
      新发会断开引用关系，群里看到的是一段不知道在答谁的话。
      守引用比守卡片重要。

**三、超限内容搬走，不丢字符**

    超过 `MAX_SECTIONS` 的段落搬进折叠区，**一个字符都不丢**。
    「搬是搬，砍是砍」（AGENTS §2.4）—— 丢内容比格式难看严重得多。

**四、群里永不出现 `[[card:` 原始标记**

    卡片的标记是内部传输格式。泄漏一条 `[[card:...]]` 到群里，
    和泄漏一条 `tool_calls` 是同一类故障。
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

from tools.redact import redact

# 与 `tools/reply-cards/envelope.mjs` 对齐的常量。
# ★ 为什么这里要重复一份：Python 核心要做独立可测的判断，不能 import 一个 .mjs。
#   两处一致性由 `verify_send_gateway.py` 的静态对拍断言守住（读 .mjs 里的数值比对）。
CARD_MARK = "[[card:"

# 11 张样例卡顶层 markdown 块数的实测上界（envelope.mjs 的注释口径）
MAX_SECTIONS = 4

VALID_KINDS = frozenset({"verdict", "receipt", "boundary", "status"})


class GatewayError(Exception):
    """形态/降级路径上的硬错误。每条都要说清是哪一步。"""


# ═══════════════════════ ① 形态决策（唯一一处）═══════════════════════

def _minimize_value(value, redactions):
    """递归遮蔽最终外发文本/卡片 payload 里的敏感片段。"""
    if isinstance(value, str):
        safe, findings = redact(value)
        for f in findings:
            redactions.append({
                "kind": f.get("type"),
                "span": [f.get("start"), f.get("end")],
            })
        return safe
    if isinstance(value, list):
        return [_minimize_value(v, redactions) for v in value]
    if isinstance(value, dict):
        return {k: _minimize_value(v, redactions) for k, v in value.items()}
    return value


def _minimize_result(result):
    """唯一外发最小化出口：正文与卡片 payload 都过 redact。"""
    redactions = []
    if isinstance(result, dict):
        if "text" in result:
            result["text"] = _minimize_value(result["text"], redactions)
        if "payload" in result and result["payload"] is not None:
            result["payload"] = _minimize_value(result["payload"], redactions)
        result["redactions"] = redactions
    return result


def decide_mode(raw_reply: str, *, has_eligible_card: bool = True) -> dict:
    """
    决定这条回复走卡片还是纯文本。**纯函数**：同一输入永远同一输出。

    返回 {"mode": "card"|"text", "kind": str|None, "payload": dict|None, "text": str}

    判定顺序（有先后，不是并列）：
      1. 没有卡片块 → 纯文本
      2. 有卡片块但解析失败 → 纯文本（**且正文里不许残留标记**）
      3. 卡片类型不在白名单 → 纯文本
      4. 其余 → 卡片
    """
    if not isinstance(raw_reply, str):
        raise GatewayError(f"raw_reply 必须是字符串，实际 {type(raw_reply).__name__}")

    card = parse_card_block(raw_reply)
    if card is None:
        out = {"mode": "text", "kind": None, "payload": None,
               "text": strip_card_marks(raw_reply)}
    elif not has_eligible_card:
        # 调用方明确说「这次不收卡片」（例如某条通道不支持）
        out = {"mode": "text", "kind": None, "payload": None,
               "text": strip_card_marks(raw_reply)}
    elif card.get("parse_error"):
        out = {"mode": "text", "kind": None, "payload": None,
               "text": strip_card_marks(raw_reply),
               "dropped_reason": card["parse_error"]}
    elif card.get("kind") not in VALID_KINDS:
        out = {"mode": "text", "kind": None, "payload": None,
               "text": strip_card_marks(raw_reply),
               "dropped_reason": f"卡片类型 {card.get('kind')!r} 不在白名单"}
    else:
        out = {"mode": "card", "kind": card["kind"],
               "payload": card.get("payload"),
               "text": strip_card_marks(raw_reply)}
    return _minimize_result(out)


def parse_card_block(raw_reply: str) -> dict | None:
    """
    从回复里抠出 `[[card:类型]]` + JSON。找不到返回 None。

    ★ 找不到与解析失败是两件事：
      找不到 → None（这条回复本来就没想用卡片）
      解析失败 → {"parse_error": ...}（想用但写坏了，要降级并记原因）
    """
    idx = raw_reply.find(CARD_MARK)
    if idx < 0:
        return None
    rest = raw_reply[idx + len(CARD_MARK):]
    end = rest.find("]]")
    if end < 0:
        return {"parse_error": "卡片标记未闭合"}
    kind = rest[:end].strip()
    body = rest[end + 2:].strip()
    if not body:
        return {"parse_error": "卡片标记后没有 JSON 体"}
    # 尝试解析第一段 JSON
    try:
        payload, _ = json.JSONDecoder().raw_decode(body)
    except ValueError as e:
        return {"parse_error": f"卡片 JSON 解析失败：{e}"}
    if not isinstance(payload, dict):
        return {"parse_error": "卡片 JSON 顶层必须是对象"}
    return {"kind": kind, "payload": payload}


def strip_card_marks(text: str) -> str:
    """
    把任何残留的 `[[card:...]]` 段落剥掉。**群消息里绝不许出现这个标记。**

    这不是「顺手清一下」——它是一条独立判据（L4-6）。
    实现上整块剥掉（标记 + 直到 JSON 结束），而不是只删标记 ——
    只删标记会把内部 JSON 漏进群里，那比原样泄漏更糟。
    """
    if CARD_MARK not in text:
        return text
    out, pos = [], 0
    while True:
        idx = text.find(CARD_MARK, pos)
        if idx < 0:
            out.append(text[pos:])
            break
        out.append(text[pos:idx])
        rest = text[idx + len(CARD_MARK):]
        end = rest.find("]]")
        if end < 0:
            break                      # 未闭合：后面全部丢弃（宁可少，不可漏）
        body = rest[end + 2:]
        stripped = body.lstrip()
        if stripped:
            try:
                _, consumed = json.JSONDecoder().raw_decode(stripped)
                pos = len(text) - len(stripped) + consumed
                continue
            except ValueError:
                pass                   # JSON 坏掉 → 从这里继续找下一个标记
        pos = idx + len(CARD_MARK) + end + 2
    return "".join(out).strip()


# ═══════════════════════ ② 超限搬进折叠区（不丢字符）═══════════════════════

def cap_sections(sections: Sequence[dict], *, max_sections: int = MAX_SECTIONS) -> dict:
    """
    顶层段落超过上限时，**把超出的搬进折叠区**，不是截断。

    返回 {"kept": [...], "folded": [...], "moved_chars": int, "fold_text": str}

    ★ 判据：`sum(len(kept)) + sum(len(folded)) == sum(len(original))` —— 一个字符都不许丢。
      这条由 verify 的「字符守恒」断言守护。
    """
    if not isinstance(sections, (list, tuple)):
        raise GatewayError("sections 必须是列表")
    secs = [dict(s) for s in sections]
    if len(secs) <= max_sections:
        return {"kept": secs, "folded": [], "moved_chars": 0, "fold_text": ""}

    kept = secs[:max_sections]
    folded = secs[max_sections:]
    fold_text = "\n\n".join(
        f"**{s.get('title', '（无标题）')}**\n{s.get('body', '')}" for s in folded)
    return {
        "kept": kept,
        "folded": folded,
        "moved_chars": sum(len(str(s.get("body", ""))) for s in folded),
        "fold_text": fold_text,
    }


def chars_conserved(original: Sequence[dict], result: dict) -> bool:
    """字符守恒判据：搬走的 + 留下的 == 原来的。搬是搬，砍是砍。"""
    def total(seq):
        return sum(len(str(s.get("body", ""))) + len(str(s.get("title", ""))) for s in seq)

    kept = result.get("kept") or []
    folded = result.get("folded") or []
    return total(original) == total(kept) + total(folded)


# ═══════════════════════ ③ 降级链（唯一一处兜底）═══════════════════════

def degrade(send_results: Iterable[dict]) -> dict:
    """
    沿降级链判定最终结果。**唯一的兜底判断**。

    输入是依次尝试的发送结果（每项 {"ok": bool, "mode": str, "error": str|None}）。
    规则：
      · 第一个 ok 的就停（不再尝试后面的）
      · 全部失败 → {"ok": False, "exhausted": True, ...}
      · 卡片失败但文本成功 → 结果里必须**带上降级原因**，否则对方不知道为什么格式变了

    ★ 不许内建第二次兜底：本函数只会按传入的链走一遍。
      如果调用方在外面再套一层 `try: send() except: send()`，那就是第二处兜底 ——
      AGENTS §2.5 明令禁止（同一个回答会在群里出现两次）。
    """
    tries = []
    for i, r in enumerate(send_results):
        tries.append(dict(r))
        if r.get("ok"):
            out = {"ok": True, "attempts": tries, "mode": r.get("mode")}
            # 卡片失败过 → 带上原因
            failed_card = [t for t in tries[:-1] if not t.get("ok")]
            if failed_card:
                out["degraded"] = True
                out["degraded_reason"] = failed_card[0].get("error") or "卡片发送失败"
            else:
                out["degraded"] = False
            return out
    return {"ok": False, "attempts": tries, "exhausted": True,
            "degraded": bool(tries), "mode": None}


def build_degrade_plan(mode: str) -> list[str]:
    """
    给定形态，返回降级链的步骤名。**这是「兜底只有一处」的声明式表达。**

    card → ["replyCard", "replyMarkdown"]        （发卡失败 → 同一条引用里发纯文本）
    text → ["replyMarkdown", "sendMarkdown"]     （回复失败 → 直接发送）
    """
    if mode == "card":
        return ["replyCard", "replyMarkdown"]
    if mode == "text":
        return ["replyMarkdown", "sendMarkdown"]
    raise GatewayError(f"未知形态 {mode!r}")


# ═══════════════════════ ④ 群消息洁净度 ═══════════════════════

def assert_clean_for_group(text: str) -> None:
    """群消息发出前的最后一道闸：不许有卡片标记、不许有 tool_calls 之类内部串。"""
    if CARD_MARK in text:
        raise GatewayError("群消息里出现了 `[[card:` 原始标记 —— L4-6 禁止")
    for banned in ("tool_calls", "\"tool_use\"", "<function_call>"):
        if banned in text:
            raise GatewayError(f"群消息里出现了内部串 {banned!r}")
