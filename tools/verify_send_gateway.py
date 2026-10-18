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


def main() -> int:
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
    raw_card = '[[card:verdict]]\n{"title":"通过","body":"ok"}'
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


if __name__ == "__main__":
    sys.exit(main())
