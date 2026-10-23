#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_send_gateway.py —— send_gateway 的契约验收（AGENTS §2.5 / L4-4 / L4-5 / L4-6）

五条必须成立，且每条都要能红：
  1. 唯一形态决策：同一输入恒定同一形态
  2. 卡片被拒 → 必须降级纯文本（不得消失）
  3. 超限内容搬进折叠区（不丢字符）
  4. 群里永不出现 `[[card:` 原始标记
  5. 发送兜底只此一处（不内建第二次兜底）—— 静态扫描

退出码：0 全绿 / 1 有红 / 2 未测（import 不到或对拍的 .mjs 读不到）
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.send_gateway import (  # noqa: E402
        CARD_MARK, MAX_SECTIONS, VALID_KINDS, GatewayError,
        decide_mode, parse_card_block, strip_card_marks,
        cap_sections, chars_conserved, degrade, build_degrade_plan,
        assert_clean_for_group,
    )
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import send_gateway 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(2)

ENVELOPE = ROOT / "tools" / "reply-cards" / "envelope.mjs"
WS_DAEMON = ROOT / "tools" / "ws_daemon.mjs"


# ═══════════════════════════════════════════════════════════════════════
# JS 噪声剥离（5c-b 用）：抹掉**注释**，字符串/模板串**逐字保留**，其余原样。
# 为什么不许用「裸文本存在性」：
#   §2.4 那条（「名字出现过 ≠ 拦得住」）+ 2026-10-24 实测 —— 变异 64-0b 把降级目标
#   改成 `sent = { ok: true, mode: \`card-failed→${rc.mode}\`, ... }`（发不出去的
#   原样结果），裸文本检查 `card-failed→` 依然命中，34/34 依旧全绿。
# 为什么字符串/模板串逐字保留而不是抹成空格：5c-b 的判据之一正是**模板串里的
#   mode 来源**（`${rt.mode}` 合法 / `${rc.mode}` 是 64-0b 的骗法），抹掉内容判据就没了。
#   字符串/模板串要消费（而不是当普通字符放过）的原因：里面的 `//`（URL）不许被当成注释。
# 已知盲区明说（§2.1.1：会误报的检查器比没有更糟，会漏报的也要明着留）：
#   ① 字符串/模板串/正则字面量的**内容**对 5c-b3 的标记检查可见 —— 把降级标记藏进
#     字符串常量能骗过 5c-b3（但骗不过 5c-b1/5c-b2 的调用结构检查）；
#   ② 不处理正则字面量（有意的：启始判定是启发式，误判会把真代码抹掉）；
#     正则体内不可能出现未转义的 `/`，所以不会误触发注释分支。
def _strip_js_noise(src: str) -> str:
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":                      # 行注释
            while i < n and src[i] != "\n":
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        if c == "/" and nxt == "*":                      # 块注释（保换行）
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
            continue
        if c in ("'", '"', "`"):                         # 字符串 / 模板串：逐字保留
            q = c
            out.append(q)
            i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == q:
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _branch_spans(src: str):
    """从已剥噪声的源码里找出 replyTo 的降级链，返回 (行列表, 起点0基, 终点0基含)。

    branch_spans = [(名字, 起行0基, 止行0基含)]；找不到链 → None。
    """
    lines = src.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"^async function replyTo\s*\(", ln)), None)
    if start is None:
        return None, None, None
    depth, end = 0, None
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if i > start and depth == 0:
            end = i
            break
    if end is None:
        return None, None, None
    blk = lines[start:end + 1]
    chain_re = re.compile(r"\}\s*else\s*\{")
    chain = next((k for k, ln in enumerate(blk) if chain_re.search(ln)), None)
    if chain is None:
        return None, None, None
    branch_re = re.compile(r"^  if\s*\(")
    marks = [(k, "else" if chain_re.search(ln) else "if")
             for k, ln in enumerate(blk) if chain_re.search(ln) or branch_re.match(ln)]
    spans = []
    for idx, (k, name) in enumerate(marks):
        stop = (marks[idx + 1][0] - 1) if idx + 1 < len(marks) else len(blk) - 1
        spans.append((f"{name}@{k}", k, stop))
    return spans, start, end


def _branch_text(spans, start, end, lines):
    return [(name, "\n".join(lines[start + a:start + b + 1])) for name, a, b in spans]


def _fallback_checks(raw_src: str):
    """5c-b 三条判据（输入 = **未剥离**的 daemon 源码文本）。

    判据读法（★ 一处都不能松，三处都各有变异骗过它）：
      · 定位 replyTo 体内 `if (card) { ... } else { ... }` 的**两个 span**；
      · card span：必须调用 feishu.replyCard；
      · fallback span = **card span 的下一个 span**（`} else {` 起的那支）——
        ① 必须有 `= await feishu.replyMarkdown(`（一次调用 = 一条真到群的消息；
          `sent = rc` 没有调用 → 变异 64-0 在这里红）；
        ② 该 span 里必须出现 `sent =`，且补发结果被收进 sent（出口留痕唯一）；
        ③ 降级标记 `card-failed→` 必须落在**这个 span**（replyTo 体内），且 mode
          取自补发那次（`${rt.mode}` / `${r.mode}` / 'text-fallback'）——
          `${rc.mode}` 是变异 64-0b 的骗法（它在台账里把补发记成卡片）；
          标记出现在别的 span 或注释性文本里都不算（后者见 --controls 坏样本 3）。

    返回 (ok, fails, detail)；fails 是红项键列表，空 = 全过。
    main 与 --controls 共用同一份判据 —— 对照喂的坏样本必须让**这同一份**判据红。
    """
    wd_src = _strip_js_noise(raw_src)
    wd_lines = wd_src.splitlines()
    spans, b0, _b1 = _branch_spans(wd_src)
    if spans is None:
        return False, ["chain"], "replyTo 函数体或 `} else {` 降级链扫描不到 —— 判据落空"
    call_re = re.compile(r"\bfeishu\.(replyCard|replyMarkdown|sendMarkdown)\s*\(")

    def _txt(i):
        nm, a, b = spans[i]
        return nm, "\n".join(wd_lines[b0 + a:b0 + b + 1])

    card_i = next((i for i in range(len(spans))
                   if "replyCard" in call_re.findall(_txt(i)[1])), None)
    if card_i is None:
        return False, ["card"], "card 分支（调用 replyCard 的那支）扫描不到"
    fb_i = card_i + 1
    if fb_i >= len(spans):
        return False, ["no_replyMarkdown"], "card 分支之后没有 else 支 —— 没有补发"
    fb_nm, fb_tx = _txt(fb_i)
    fb_calls = call_re.findall(fb_tx)
    fb_span_all = "\n".join(wd_lines[b0 + spans[fb_i][1]:])  # fallback span 起到函数尾

    # 降级标记：补发那次的 mode（rt/r）或封闭集合 text-fallback；
    # rc/card 那几次的 mode **不算** —— 那是变异 64-0b 的骗法
    guard_re = re.compile(
        r"card-failed\s*→\s*(?:\$\{\s*(?:rt|r)\s*\.\s*mode\s*\}|['\"]text-fallback['\"])")
    raw_re = re.compile(r"card-failed\s*→\s*\$\{\s*(?:rc|card)\s*\.\s*mode\s*\}")

    c5a = fb_calls == ["replyMarkdown"]
    c5b = (c5a and re.search(r"=\s*await\s+feishu\.replyMarkdown\s*\(", fb_tx)
           and re.search(r"\bsent\s*=", fb_tx))
    mark_m = guard_re.search(fb_span_all)
    raw_m = raw_re.search(fb_span_all)
    c5c = mark_m is not None and raw_m is None
    fails = []
    if not c5a:
        fails.append("no_replyMarkdown")
    if not c5b:
        fails.append("sent_missing")
    if not c5c:
        # raw_rc_mode 优先：骗法（`${rc.mode}`）在场时红在这一项，
        # 好让 --controls 能证明判据「看见了」那个骗法，而不是碰巧红
        fails.append("raw_rc_mode" if raw_m is not None else "mark")
    detail = (f"card分支={spans[card_i][0]} 补发分支={fb_nm}（calls={fb_calls or '无'}）；"
              f"标记{'在(' + mark_m.group(0) + ')' if mark_m else '缺'}；"
              f"rc.mode 骗法{'在' if raw_m else '无'}")
    return (not fails), fails, detail


# --controls 的坏样本：直接复用探针阶段两份真实变异（内存字符串，不碰盘上文件）
_BAD_64_0 = (
    "      const rt = await feishu.replyMarkdown(messageId, chatId, text);\n"
    "      sent = rt.ok ? { ...rt, mode: `card-failed→${rt.mode}`, error: rc.error } : rt;",
    "      sent = rc;")
_BAD_64_0B = (
    "      const rt = await feishu.replyMarkdown(messageId, chatId, text);\n"
    "      sent = rt.ok ? { ...rt, mode: `card-failed→${rt.mode}`, error: rc.error } : rt;",
    "      sent = { ok: true, mode: `card-failed→${rc.mode}`, error: rc.error };")
_BARE = "本次审批通过，请你查收。"
_BAD_TEXT = "本次审批已通过，无需处理。"


def _bare_hit(hits):
    """7d 的判定核心：hits 里有没有 裸「通过」@4:6 这一条。main 与 --controls 共用。"""
    return next((h for h in (hits or [])
                 if h.get("word") == "通过" and h.get("start") == 4
                 and h.get("end") == 6), None)


def _main() -> int:
    results = []

    def ok(name, cond, detail):
        results.append((name, bool(cond), detail))

    def reject(name, fn, want_code=None):
        try:
            fn()
        except GatewayError as e:
            ok(name, True, f"拒收：{e}")
        except Exception as e:  # noqa: BLE001
            ok(name, False, f"抛了非 GatewayError：{type(e).__name__}: {e}")
        else:
            ok(name, False, "**没有拒收** —— 这条断言是假的")

    # ═══════ 1. 形态决策：同一输入恒定 ═══════
    raw_card = '[[card:verdict]]\n{"title":"已核验","body":"ok"}'
    d1 = decide_mode(raw_card)
    d2 = decide_mode(raw_card)
    ok("1a 同一输入两次 → 同一形态", d1 == d2, f"{d1['mode']} vs {d2['mode']}")
    ok("1b 有卡片块 → card", d1["mode"] == "card", f"mode={d1['mode']} kind={d1['kind']}")

    d3 = decide_mode("就是一段普通文本")
    ok("1c 无卡片块 → text", d3["mode"] == "text", f"mode={d3['mode']}")

    # 1d：纯函数性 —— 不读时间/随机。用两次不同时刻调用无法从外部验证，
    #     改为断言「同一输入 100 次结果全同」（若有隐藏随机源会散开）
    same = {decide_mode(raw_card)["mode"] for _ in range(100)}
    ok("1d 100 次调用结果唯一（无隐藏随机源）", len(same) == 1, f"distinct={same}")

    # 1e：卡片类型不在白名单 → text + 记原因
    d4 = decide_mode('[[card:nonsense]]\n{"a":1}')
    ok("1e 未知卡片类型 → 降级 text 且记原因",
       d4["mode"] == "text" and d4.get("dropped_reason"),
       f"mode={d4['mode']} reason={d4.get('dropped_reason')}")

    # 1f：卡片 JSON 坏掉 → text + 记原因
    d5 = decide_mode('[[card:verdict]]\n{不是 json')
    ok("1f 卡片 JSON 坏 → 降级 text 且记原因",
       d5["mode"] == "text" and d5.get("dropped_reason"),
       f"mode={d5['mode']} reason={d5.get('dropped_reason')}")

    # 1g：解析函数：找不到 vs 解析失败要长得不一样
    _none_case = parse_card_block("没有卡片")
    _bad_case = parse_card_block('[[card:x]]\n{bad') or {}
    ok("1g 找不到卡片 → None；解析失败 → parse_error",
       _none_case is None and _bad_case.get("parse_error") is not None,
       f"none={_none_case} bad={_bad_case.get('parse_error')}")

    # ═══════ 2. 卡片被拒 → 降级纯文本 ═══════
    r = degrade([
        {"ok": False, "mode": "replyCard", "error": "卡片被拒 230001"},
        {"ok": True, "mode": "replyMarkdown"},
    ])
    ok("2a 卡片失败 → 文本成功，且带降级原因",
       r["ok"] and r.get("degraded") and "230001" in str(r.get("degraded_reason")),
       f"ok={r['ok']} degraded={r.get('degraded')} reason={r.get('degraded_reason')}")

    r2 = degrade([{"ok": True, "mode": "replyCard"}])
    ok("2b 卡片一次成功 → 不降级", r2["ok"] and not r2.get("degraded"), f"{r2}")

    r3 = degrade([
        {"ok": False, "mode": "replyMarkdown", "error": "x"},
        {"ok": False, "mode": "sendMarkdown", "error": "y"},
    ])
    ok("2c 全链失败 → exhausted 且 ok=False",
       (not r3["ok"]) and r3.get("exhausted"), f"{r3}")

    # 2d：降级链只有一条，且方向对
    ok("2d 降级链：card→[replyCard, replyMarkdown] / text→[replyMarkdown, sendMarkdown]",
       build_degrade_plan("card") == ["replyCard", "replyMarkdown"]
       and build_degrade_plan("text") == ["replyMarkdown", "sendMarkdown"],
       f"card={build_degrade_plan('card')} text={build_degrade_plan('text')}")

    # 2e：未知形态不许静默通过
    reject("2e 未知形态 → 拒", lambda: build_degrade_plan("magic"))

    # ═══════ 3. 超限搬进折叠区（不丢字符）═══════
    secs = [{"title": f"节{i}", "body": "正文" * 10} for i in range(MAX_SECTIONS + 3)]
    capped = cap_sections(secs)
    ok("3a 超限 → kept 恰好等于上限",
       len(capped["kept"]) == MAX_SECTIONS, f"kept={len(capped['kept'])}")
    ok("3b 超限 → folded 非空且搬走了字符", len(capped["folded"]) > 0 and capped["moved_chars"] > 0,
       f"folded={len(capped['folded'])} chars={capped['moved_chars']}")
    ok("3c ★ 字符守恒：搬走的 + 留下的 == 原来的",
       chars_conserved(secs, capped),
       f"conserved={chars_conserved(secs, capped)}")

    # 3d：不超限 → 不搬
    few = secs[:MAX_SECTIONS]
    capped2 = cap_sections(few)
    ok("3d 不超限 → 原样保留、folded 为空",
       len(capped2["kept"]) == MAX_SECTIONS and not capped2["folded"]
       and chars_conserved(few, capped2), f"{capped2}")

    # 3e：反向对照 —— 截断式实现（丢掉 folded）必须被 chars_conserved 判死
    bad = {"kept": capped["kept"], "folded": [], "moved_chars": 0}
    ok("3e ★ 截断式实现被判不守恒（反向对照）",
       chars_conserved(secs, bad) is False, f"conserved={chars_conserved(secs, bad)}")

    # ═══════ 4. 群消息永不出现 [[card: ═══════
    dirty = '前缀 [[card:verdict]]\n{"title":"x"} 后缀'
    clean = strip_card_marks(dirty)
    ok("4a 剥标记后不含 [[card:", CARD_MARK not in clean, f"clean={clean!r}")
    ok("4b ★ 剥标记时不许把内部 JSON 漏进正文",
       '"title"' not in clean and "{'" not in clean, f"clean={clean!r}")
    reject("4c 群消息含卡片标记 → 拒", lambda: assert_clean_for_group(dirty))
    reject("4d 群消息含 tool_calls → 拒",
           lambda: assert_clean_for_group('{"tool_calls": []}'))
    # 4e：干净消息不许被误拒
    try:
        assert_clean_for_group("这是一句正常的话。")
        ok("4e 正常群消息放行（防误报）", True, "通过")
    except GatewayError as e:
        ok("4e 正常群消息放行（防误报）", False, f"误拒：{e}")

    # ═══════ 5. 兜底只此一处（静态扫描）═══════
    # 5a：envelope.mjs 里的 CARD_MARK 必须与本文件一致
    if not ENVELOPE.exists():
        print(f"⚠ 未测：{ENVELOPE} 不存在，5a 无法对拍", file=sys.stderr)
        return 2
    ev = ENVELOPE.read_text(encoding="utf-8")
    m_mark = re.search(r"^export const CARD_MARK\s*=\s*['\"](.+?)['\"]", ev, re.M)
    ok("5a CARD_MARK 与 envelope.mjs 一致",
       bool(m_mark) and m_mark.group(1) == CARD_MARK,
       f"envelope={m_mark.group(1) if m_mark else None!r} python={CARD_MARK!r}")

    # 5b：MAX_SECTIONS 的**真值在 cards.mjs**（envelope.mjs 只是 import 它）。
    # ★ 2026-10-19 实测：原先扫 envelope.mjs，命中的是它第 16 行的**旧注释**
    #   「MAX_SECTIONS = 3」—— 注释不是代码（AGENTS §2.4 那条）。真值是 cards.mjs:90 的 4。
    CARDS = ROOT / "tools" / "reply-cards" / "cards.mjs"
    if not CARDS.exists():
        print(f"⚠ 未测：{CARDS} 不存在，5b 无法对拍", file=sys.stderr)
        return 2
    cd_src = CARDS.read_text(encoding="utf-8")
    m_sec = re.search(r"^export const MAX_SECTIONS\s*=\s*(\d+)", cd_src, re.M)
    ok("5b MAX_SECTIONS 与 cards.mjs 的实际导出一致（不读注释）",
       bool(m_sec) and int(m_sec.group(1)) == MAX_SECTIONS,
       f"cards.mjs={m_sec.group(1) if m_sec else None} python={MAX_SECTIONS}")

    # 5c：兜底只一处 —— 按**调用点所在函数**去重，而不是数裸调用点。
    # ★ 2026-10-19 实测：原先要求裸调用点 ≤2，而 replyTo 内部本身就有降级链的三处调用
    #   （replyCard / replyMarkdown / sendMarkdown），于是正确实现被判红。
    #   正确的判据是：所有发送调用都必须落在**少数几个具名函数**里，
    #   且这些函数构成允许集合 {replyTo, safeSend}；出现第三个函数在发消息即红。
    if WS_DAEMON.exists():
        wd_lines = WS_DAEMON.read_text(encoding="utf-8").splitlines()
        call_re = re.compile(r"feishu\.(sendMarkdown|replyMarkdown|replyCard)\s*\(")
        fn_re = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
        enclosing, cur = {}, None
        for line in wd_lines:
            mfn = fn_re.match(line.strip())
            if mfn:
                cur = mfn.group(1)
            if call_re.search(line) and cur:
                enclosing.setdefault(cur, 0)
                enclosing[cur] += 1
        allowed = {"replyTo", "safeSend"}
        extra = sorted(set(enclosing) - allowed)
        ok("5c 所有发送调用都落在 replyTo / safeSend 内（兜底只一处）",
           bool(enclosing) and not extra,
           f"发送函数={enclosing}；越界函数={extra or '无'}")
    else:
        results.append(("5c ws_daemon.mjs 不存在 → 跳过", True, "文件不在"))

    # 5c-b：卡片被拒 → **真的补发一条纯文本**（行为级，不只查文本存在）。
    # ★ 2026-10-24 实测：变异 64-0（`sent = rc;` —— 卡片失败后把**发不出去的原样
    #   结果**当发送结果）之后 34/34 仍全绿，`verify_cards.mjs` 的 L1 也只查
    #   `card-failed→` 这串字在不在 —— 「最终仍有一条纯文本到达群里」在发送链上
    #   0 断言。变异 64-0b 更阴：保留 `card-failed→` 字样（骗过 L1），但 mode 记的
    #   是 `rc.mode`（卡片那次，不是补发那次）。判据见 `_fallback_checks` 的 docstring
    #   （main 与 --controls 共用同一份，对照喂的坏样本红在**同一份**判据上）。
    if WS_DAEMON.exists():
        f_ok, f_fails, f_detail = _fallback_checks(
            WS_DAEMON.read_text(encoding="utf-8"))
        fails = set(f_fails)
        structural = {"chain", "card"}          # 链都扫不到 → 三条全红，不许静默绿
        subs = [
            ("5c-b1 卡片被拒 → 有一次**新的** replyMarkdown 调用（真补发）",
             "no_replyMarkdown"),
            ("5c-b2 补发结果必须落进 sent（出口留痕唯一）", "sent_missing"),
            ("5c-b3 sent.mode 带降级标记、且 mode 取自补发那次（不许 `${rc.mode}`）",
             None),   # mark / raw_rc_mode 任一在即红
        ]
        for name, key in subs:
            bad = bool(fails & structural)
            if key:
                bad = bad or key in fails
            else:
                bad = bad or ("mark" in fails) or ("raw_rc_mode" in fails)
            ok(name, not bad, f_detail)
    else:
        results.append(("5c-b ws_daemon.mjs 不存在 → 跳过", True, "文件不在"))

    # ═══════ 6. 外发最小化（G-6）：唯一出口 decide_mode ═══════
    pos = "联系 13800138000，身份证 11010519491231002X，路径 /Users/lute/secret.txt"
    out = decide_mode(pos)
    redactions = out.get("redactions") or []
    ok("6a 正样本：手机号/身份证/内部路径原值不出现",
       all(x not in out["text"] for x in
           ("13800138000", "11010519491231002X", "/Users/lute/secret.txt")),
       f"text={out['text']!r}")
    ok("6b 正样本：redactions 非空且含 kind/span",
       bool(redactions) and all({"kind", "span"} <= set(r) for r in redactions),
       f"redactions={redactions}")
    ok("6c 正样本：命中 phone_cn/cn_id/abs_path",
       {r["kind"] for r in redactions} >= {"phone_cn", "cn_id", "abs_path"},
       f"kinds={sorted({r['kind'] for r in redactions})}")

    card_out = decide_mode(
        '[[card:verdict]]\n{"title":"联系 13800138000","body":"ok"}')
    ok("6d 卡片正文也过 redact",
       card_out["mode"] == "card"
       and "13800138000" not in (card_out.get("text") or "")
       and "13800138000" not in str(card_out.get("payload"))
       and bool(card_out.get("redactions")),
       f"payload={card_out.get('payload')!r} text={card_out.get('text')!r}")

    degraded = decide_mode('[[card:verdict]]\n{坏 JSON 联系 13800138000')
    ok("6e 降级文本也过 redact",
       degraded["mode"] == "text"
       and "13800138000" not in (degraded.get("text") or "")
       and bool(degraded.get("redactions")),
       f"text={degraded.get('text')!r} redactions={degraded.get('redactions')}")

    neg = "订单号 2026101801，详见 https://example.com/item/13800138000"
    neg_out = decide_mode(neg)
    ok("6f 负样本：10 位订单号与 URL 内数字不被误遮",
       neg_out["text"] == neg and neg_out.get("redactions") == [],
       f"text={neg_out.get('text')!r} redactions={neg_out.get('redactions')}")

    # ═══════ 7. 回执禁词闸（L3-4）═══════
    bad_text = "本次审批已通过，无需处理。"
    bad = decide_mode(bad_text)
    hits = ((bad.get("error") or {}).get("hits") or [])
    report_ok = (bad.get("ok") is False and bad.get("blocked") is True
                 and bad.get("text") is None
                 and (bad.get("error") or {}).get("code") == "receipt_forbidden_word"
                 and {"已通过", "无需处理"} <= {h.get("word") for h in hits}
                 and all(isinstance(h.get("start"), int)
                         and isinstance(h.get("end"), int) for h in hits)
                 and "已通过" in (bad.get("error") or {}).get("message", ""))
    results.append(("7a 回执含禁词 → 阻断并报词/位置", report_ok, repr(bad)))

    bad_card = decide_mode(
        '[[card:receipt]]\n{"title":"审批完成","body":"ok"}')
    report_ok = (bad_card.get("ok") is False and bad_card.get("blocked") is True
                 and bad_card.get("payload") is None
                 and any(h.get("path", "").endswith("payload.title")
                         and h.get("word") == "审批完成"
                         for h in ((bad_card.get("error") or {}).get("hits") or [])))
    results.append(("7b 卡片回执禁词 → 阻断（text/payload 置空）", report_ok, repr(bad_card)))

    neg = "本周审核通过率为 98%，请查看详情。"
    neg_out = decide_mode(neg)
    report_ok = (neg_out.get("ok") is True and neg_out.get("blocked") is False
                 and neg_out.get("text") == neg
                 and neg_out.get("redactions") == [])
    results.append(("7c 正常文案含「通过率」→ 不误拦", report_ok, repr(neg_out)))

    # 7d：**裸「通过」**必须拦（L3-4 四词之一）。
    # ★ 2026-10-24 实测：把 FORBIDDEN_RECEIPT_WORDS 的 `通过(?!率)` 分支删掉后
    #   34/34 仍全绿 —— 7a 只含「已通过/无需处理」、7b 只有「审批完成」、7c 只证
    #   「通过率」不误拦，四词清单里这一词实际未被验（变异 65-0 survived）。
    bare = _BARE
    bare_out = decide_mode(bare)
    bare_hits = ((bare_out.get("error") or {}).get("hits") or [])
    bare_hit = _bare_hit(bare_hits)
    bare_ok = (bare_out.get("blocked") is True and bare_out.get("text") is None
               and bare_out.get("payload") is None
               and (bare_out.get("error") or {}).get("code") == "receipt_forbidden_word"
               and bare_hit is not None)
    results.append(("7d 裸「通过」（不带率）→ 阻断", bare_ok,
                    "hits=" + repr(bare_hits) + " —— 裸「通过」分支没拦，65-0 缺口未闭"
                    if not bare_ok else
                    f"blocked=True，命中={[h.get('word') for h in bare_hits]}"))

    # 7e：反向对照 —— 裸「通过」分支被换成「永不匹配」的 (?!) 之后，7d 必须变红。
    # 机制：把正则换成变异 65-0 的形状（`通过(?!率)|` → `(?!)|`，其余三支原样保留）
    # 后在**函数对象克隆**上重扫原句 —— 不改盘上 base/（探针只读）；克隆共享
    # _forbidden_hits 的字节码，函数内的递归调用仍落在同一对象里，行为等同真变异。
    # 断言三件事：① 坏表下「通过@4:6」这条命中**消失**（7d 的红真的来自那个分支，
    # 不是常量巧合）；② 坏表下其余分支照旧命中（对照自己活着 —— 全空说明探针坏了）；
    # ③ 真表下「通过@4:6」仍在（没有误伤、双向都对）。
    try:
        import base.send_gateway as _sg
        _clone = types.ModuleType("_fg_probe")
        _clone.__dict__.update(_sg.__dict__)
        _clone.FORBIDDEN_RECEIPT_WORDS = re.compile(
            r"(?:已通过(?!率)|(?!)|无需处理|审批完成)")
        _scan = types.FunctionType(_sg._forbidden_hits.__code__, _clone.__dict__,
                                   "_forbidden_hits", _sg._forbidden_hits.__defaults__)

        def _has(hits, word, s, e):
            return any(h.get("word") == word and h.get("start") == s
                       and h.get("end") == e for h in hits)

        _probe_bare = _scan(bare, "text", [])        # 坏表 × 裸「通过」句
        _probe_7a = _scan(bad_text, "text", [])      # 坏表 × 7a 原句（其余分支须活着）
        _live_bare = _sg._forbidden_hits(bare, "text", [])   # 真表 × 裸「通过」句
        ctrl_ok = (not _has(_probe_bare, "通过", 4, 6)
                   and _has(_probe_7a, "已通过", 4, 7)
                   and _has(_probe_7a, "无需处理", 8, 12)
                   and _has(_live_bare, "通过", 4, 6))
        results.append(("7e 反向对照：裸「通过」分支换成 (?!) → 7d 的命中必须消失；"
                        "其余分支与真表照旧", ctrl_ok,
                        f"坏表×裸通过句 hits={[h.get('word') for h in _probe_bare]}"
                        f"（不许有 通过）；坏表×7a句 hits="
                        f"{[h.get('word') for h in _probe_7a]}（必须有 已通过/无需处理）；"
                        f"真表×裸通过句 hits={[h.get('word') for h in _live_bare]}"
                        f"（必须有 通过）"))
    except Exception as e:  # noqa: BLE001
        results.append(("7e 反向对照：裸「通过」分支换成 (?!) → 7d 的命中必须消失；"
                        "其余分支与真表照旧",
                        False, f"对照自身跑不起来：{type(e).__name__}: {e}"))

    # ── 汇总 ──
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 70)
    print("send_gateway 契约验收")
    print("=" * 70)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<46} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return 0
    print(f"✗ {passed}/{total} 项通过；红项：{[n for n, p, _ in results if not p]}")
    return 1


# ═══════════════════════════════════════════════════════════════════════
# --controls：坏样本必须红、好样本必须绿（反向对照；探针只读，不碰盘上生产文件）
def run_controls() -> int:
    print("verify_send_gateway · --controls（5c-b 与 7d 的反证）")
    bad_flags, good_flags = [], []

    # ── 坏样本 1：变异 64-0（sent = rc；补发没了）→ 5c-b1/b2 必须红 ──
    if not WS_DAEMON.exists():
        print("⚠ 未测：ws_daemon.mjs 不存在，--controls 对拍不了", file=sys.stderr)
        return 2
    wd = WS_DAEMON.read_text(encoding="utf-8")
    bad0 = wd.replace(*_BAD_64_0)
    if bad0 == wd:
        bad_flags.append("64-0 未应用上（old 片段找不到）")
    else:
        f_ok, f_fails, _d = _fallback_checks(bad0)
        if f_ok or not ({"no_replyMarkdown", "sent_missing"} & set(f_fails)):
            bad_flags.append(f"64-0（sent=rc）没让 5c-b 红：fails={f_fails}")

    # ── 坏样本 2：变异 64-0b（保留 card-failed→ 字样、mode 用 rc.mode）→ 必须红 ──
    #   骗法只改了标记的 mode 来源，补发调用还在；判据必须在 raw_rc_mode 这一项上红
    #   （若红在 no_replyMarkdown，说明判据根本没看见那个骗法 —— 检查照样算红，但没验到点）
    bad0b = wd.replace(*_BAD_64_0B)
    if bad0b == wd:
        bad_flags.append("64-0b 未应用上（old 片段找不到）")
    else:
        f_ok, f_fails, _d = _fallback_checks(bad0b)
        if f_ok or "raw_rc_mode" not in f_fails:
            bad_flags.append(f"64-0b（`${{rc.mode}}` 骗法）没让 5c-b3 红：fails={f_fails}")

    # ── 坏样本 3：**只**把标记藏进注释、发的那路改成 text-fallback 常量 ──
    #   replyCard 失败后仍有一次真的 replyMarkdown 调用（b1/b2 该绿），
    #   但 span 里没有任何活的 `card-failed→` —— b3 必须红。
    #   这一针专门证「注释不算代码」：裸文本检查（verify_cards L1 那种）会被注释骗绿。
    commented = wd.replace(
        "      const rt = await feishu.replyMarkdown(messageId, chatId, text);\n"
        "      sent = rt.ok ? { ...rt, mode: `card-failed→${rt.mode}`, error: rc.error } : rt;",
        "      const rt = await feishu.replyMarkdown(messageId, chatId, text);\n"
        "      // mode: `card-failed→${rt.mode}` —— 这行是注释\n"
        "      sent = rt.ok ? { ...rt, mode: `text-fallback`, error: rc.error } : rt;")
    if commented == wd:
        bad_flags.append("注释藏标记样本未应用上")
    else:
        f_ok, f_fails, _d = _fallback_checks(commented)
        if f_ok or "mark" not in f_fails:
            bad_flags.append(f"注释里的标记不该算数（必须红在 mark）：fails={f_fails}")

    # ── 坏样本 4：禁词表裸「通过」分支 → 7d 判定核心必须说「没拦住」 ──
    #   （真变异由 mutprobe 对盘上 base/ 做；这里是同一判定的只读对照：
    #    把「拦截成功」的好样本换成 (?!) 坏表的预期结果，判定核心必须认得出）
    import base.send_gateway as _sg2
    _probe = _scan_with_regex(r"(?:已通过(?!率)|(?!)|无需处理|审批完成)")
    if _probe is None:
        bad_flags.append("7d 坏表探针跑不起来")
    elif _bare_hit(_probe(_BARE, "text", [])) is not None:
        bad_flags.append("坏表（(?!)）下裸「通过」仍被算成命中 —— 判定核心是假的")

    # ── 好样本 1：真 daemon → 三条 5c-b 全绿 ──
    f_ok, f_fails, _d = _fallback_checks(wd)
    if not f_ok:
        good_flags.append(f"未变异 daemon 被判红：fails={f_fails}")

    # ── 好样本 2：真禁词表 → 裸「通过」@4:6 命中 ──
    _live = _sg2._forbidden_hits(_BARE, "text", [])
    if _bare_hit(_live) is None:
        good_flags.append(f"真表连裸「通过」都没命中：{_live}")

    # ── 好样本 3：7c 的「通过率」句 → 裸「通过」判定不许误命中 ──
    _neg = _sg2._forbidden_hits("本周审核通过率为 98%。", "text", [])
    if any(h.get("word") == "通过" for h in _neg):
        good_flags.append(f"「通过率」被裸「通过」误命中：{_neg}")

    print()
    if bad_flags or good_flags:
        for f in bad_flags:
            print(f"  ✗ 坏样本没红：{f}")
        for f in good_flags:
            print(f"  ✗ 好样本误红：{f}")
        print(f"❌ --controls 有对照不符（坏未红 {len(bad_flags)} / 好误红 {len(good_flags)}）")
        return 1
    print("  ✓ 坏样本红：64-0（sent=rc）→ 5c-b1/b2；64-0b（rc.mode）与注释藏标记 → 5c-b3；"
          "(?!) 坏表 → 7d 判定核心")
    print("  ✓ 好样本绿：真 daemon 三条全过；真表命中裸「通过」；「通过率」不误命中")
    print("✅ --controls 全过：好样本绿；坏样本各自红")
    return 0


def _scan_with_regex(pattern: str):
    """拿一个正则造一个 _forbidden_hits 形状的扫描函数（不改盘上模块）。"""
    import base.send_gateway as _sg
    try:
        _clone = types.ModuleType("_fg_ctrl")
        _clone.__dict__.update(_sg.__dict__)
        _clone.FORBIDDEN_RECEIPT_WORDS = re.compile(pattern)
        return types.FunctionType(_sg._forbidden_hits.__code__, _clone.__dict__,
                                  "_forbidden_hits", _sg._forbidden_hits.__defaults__)
    except Exception:  # noqa: BLE001
        return None


def main(argv=None) -> int:
    if argv is not None and "--controls" in argv:
        return run_controls()
    return _main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
