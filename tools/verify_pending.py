#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_pending.py —— 「待收清单」的判据（`PMO/待收清单-v1.json`）

## 为什么有这个东西

2026-09-21 我在汇报里说过一句「**她那边两件仍然欠着**」。对账之后：

| 我说的 | 盘上实际是什么 |
|---|---|
| 她欠「对接人统一入口」 | 她原话是**条件句**（「如果需要明确」）且只说「我计划」 |
| 她欠「三条线上两版都没有的内容」 | 她**从未提过**这三条；那是我方的问题 |

「欠」这个字把**我方要问的问题**和**对方说会给的东西**并成了一种东西 ——
这违反本项目那句自检：**「这句话比我的输入大吗？」**（`AGENTS.md` §2.4.1）。

所以这张清单不是台账，是**防止这句话再被说大的判据**：

* **C2**：性质不是「我方待问」的条目，**必须指得出上游原话**（message/file 指针）。
* **C3**：性质是「我方待问」的条目，**不许有任何一条指针被标成上游原话**。
      —— 这两条合起来，正好拦住本轮那句话的形状。

## 第二个作用：到期

`PRD/PRD差异对照-20260921.md` §五 记着上游 09-18 的承诺「其它已跟业务沟通接下来两周
陆续整理提供」（→ 2026-10-02），而同一行下面**它自己写着「到期没人会提醒」**。
本文件与 `tools/agent/prd_baseline.mjs` 的 `checkPending` 就是那个提醒。

## 退出码（口径同 `AGENTS.md` §2.4.2：未测必须与通过与红都长得不一样）

| 码 | 含义 |
|---|---|
| **0** | 结构全过，且**没有**到期未收 |
| **1** | 红：结构违规，**或**有到期未收 |
| **2** | **未测** —— 清单读不出/不是合法 JSON。**不许**当成绿 |

## 用法

```bash
python3 tools/verify_pending.py                 # 人读报告
python3 tools/verify_pending.py --json          # 机器读（给 prd_baseline.mjs 的触发者用）
python3 tools/verify_pending.py --today=2026-10-03   # 注入「今天」，用于到期判据的复现
python3 tools/verify_pending.py --controls      # 离线反向对照：判据两边都要会响
```
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIST_PATH = REPO / "PMO" / "待收清单-v1.json"
EVENT_LOG = REPO / "PMO" / "logs" / "ws_events.jsonl"

BJ = timezone(timedelta(hours=8))

ALLOWED_性质 = {"承诺", "条件承诺", "我方待问"}
ALLOWED_状态 = {"open", "partial", "done", "dropped"}
ALLOWED_角色 = {"上游原话", "我方提问", "本地旧件", "无"}
ALLOWED_到期日来源 = {"原话明示", "我方推算"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 承诺类必须指得出上游原话；这两组互为反面
承诺类 = {"承诺", "条件承诺"}


def bj_today() -> date:
    return datetime.now(BJ).date()


def _squash(s: str) -> str:
    """去掉全部空白再比 —— 中文文本里空格是排版，不是内容。"""
    return re.sub(r"\s+", "", str(s or ""))


def load_list(path: Path = LIST_PATH):
    """读清单。**读不出就是未测（退 2），不是红** —— 「我没读到」≠「清单有问题」。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, f"清单不存在：{path}"
    except OSError as e:
        return None, f"清单读不出：{e}"
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"清单不是合法 JSON：{e}"
    if not isinstance(d, dict) or not isinstance(d.get("items"), list):
        return None, "清单结构不对：顶层必须是含 items 数组的对象"
    return d, None


# ─────────────────────────── 指针（出处）可核 ───────────────────────────

def message_text(message_id: str):
    """从事件落盘里取一条群消息的正文。取不到回 None。"""
    try:
        with EVENT_LOG.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or message_id not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = (d.get("data") or {}).get("message") or {}
                if m.get("message_id") != message_id:
                    continue
                c = m.get("content") or ""
                try:
                    return json.loads(c).get("text", c)
                except (json.JSONDecodeError, AttributeError):
                    return c
    except OSError:
        return None
    return None


def check_pointer(p: dict) -> str | None:
    """核一条指针。回 None = 通过，回字符串 = 错误说明。**每条都必须能指回盘上的东西。**"""
    if not isinstance(p, dict):
        return "指针不是对象"
    kind = p.get("kind")
    role = p.get("角色")
    if role not in ALLOWED_角色:
        return f"角色非法：{role!r}（只许 {sorted(ALLOWED_角色)}）"

    if kind == "message":
        mid, quote = p.get("message_id"), p.get("quote")
        if not mid or not quote:
            return "message 指针缺 message_id 或 quote"
        text = message_text(mid)
        if text is None:
            return f"消息 {mid} 在 {EVENT_LOG.name} 里查不到"
        if _squash(quote) not in _squash(text):
            return f"quote 不是 {mid} 的逐字内容：{quote[:24]}…"
        return None

    if kind == "file":
        rel, quote = p.get("path"), p.get("quote")
        if not rel or not quote:
            return "file 指针缺 path 或 quote"
        fp = REPO / rel
        if not fp.exists():
            return f"文件不存在：{rel}"
        try:
            body = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"文件读不出：{rel}（{e}）"
        if _squash(quote) not in _squash(body):
            return f"quote 不在 {rel} 里：{quote[:24]}…"
        return None

    if kind == "none":
        if not str(p.get("why") or "").strip():
            return "none 指针必须写 why（为什么这条没有可核出处）"
        return None

    return f"指针 kind 非法：{kind!r}"


# ─────────────────────────── 单条判据 ───────────────────────────

def validate_item(it: dict, ptr_check=check_pointer) -> list[str]:
    """一条的全部结构判据。回错误列表（空 = 通过）。纯函数，可喂假样本。"""
    errs: list[str] = []
    i = it.get("id") or "(无 id)"
    for k in ("id", "事项", "性质", "谁说的", "出处", "状态", "怎么核"):
        if k not in it:
            errs.append(f"{i}: 缺字段 {k}")

    if it.get("性质") not in ALLOWED_性质:
        errs.append(f"{i}: 性质非法 {it.get('性质')!r}")
    if it.get("状态") not in ALLOWED_状态:
        errs.append(f"{i}: 状态非法 {it.get('状态')!r}")

    ptrs = it.get("出处")
    if not isinstance(ptrs, list) or not ptrs:
        errs.append(f"{i}: 出处必须是非空数组")
        ptrs = []
    for p in ptrs:
        e = ptr_check(p)
        if e:
            errs.append(f"{i}: {e}")

    roles = {p.get("角色") for p in ptrs if isinstance(p, dict)}

    # ★ C2 / C3 —— 这一对就是「她欠着」那句话的判据
    if it.get("性质") in 承诺类:
        if "上游原话" not in roles:
            errs.append(f"{i}: 性质是「{it.get('性质')}」，却没有任何一条「上游原话」指针 "
                        f"—— 承诺必须指得出原话")
    elif it.get("性质") == "我方待问":
        bad = [p for p in ptrs if isinstance(p, dict) and p.get("角色") == "上游原话"]
        if bad:
            errs.append(f"{i}: 性质是「我方待问」，却有一条指针被标成「上游原话」"
                        f" —— 不许把我方的问题写成对方的承诺")

    # ★ 到期日：要么有日子，要么明说为什么没有 —— 不许两样都没有
    due = it.get("到期日")
    if due is None:
        if not str(it.get("无到期日原因") or "").strip():
            errs.append(f"{i}: 到期日为 null 却没写「无到期日原因」—— 悬着的项必须说清为什么悬着")
    else:
        if not DATE_RE.match(str(due)):
            errs.append(f"{i}: 到期日格式不对（要 YYYY-MM-DD）：{due!r}")
        if it.get("到期日来源") not in ALLOWED_到期日来源:
            errs.append(f"{i}: 到期日来源非法 {it.get('到期日来源')!r}"
                        f"（必须区分「原话明示」与「我方推算」）")
        if not str(it.get("到期日依据") or "").strip():
            errs.append(f"{i}: 有到期日却没写「到期日依据」—— 日子从哪来的要说得出")

    # ★ 关掉一条也必须带依据，不许手一划就没了
    if it.get("状态") == "done":
        fin = it.get("完成依据")
        if not isinstance(fin, list) or not fin:
            errs.append(f"{i}: 状态是 done 却没有「完成依据」")
        else:
            for p in fin:
                if isinstance(p, dict) and p.get("kind") == "none":
                    errs.append(f"{i}: 完成依据里不许出现 none 指针 —— 关掉一条要有东西可核")
                e = ptr_check(p)
                if e:
                    errs.append(f"{i}: 完成依据 {e}")
    if it.get("状态") == "dropped" and not str(it.get("作废原因") or "").strip():
        errs.append(f"{i}: 状态是 dropped 却没写「作废原因」")

    return errs


def overdue_items(items: list[dict], today: date) -> list[dict]:
    """到期未收的条目。判据三件同时成立：状态未收、有到期日、今天 ≥ 到期日。"""
    out = []
    for it in items:
        if it.get("状态") not in {"open", "partial"}:
            continue
        due = it.get("到期日")
        if not due or not DATE_RE.match(str(due)):
            continue
        d = date.fromisoformat(str(due))
        if today >= d:
            out.append({
                "id": it.get("id"),
                "事项": it.get("事项"),
                "状态": it.get("状态"),
                "到期日": str(due),
                "过期天数": (today - d).days,
                "谁说的": it.get("谁说的"),
                "到期日来源": it.get("到期日来源"),
                "原话": next((p.get("quote") for p in (it.get("出处") or [])
                              if isinstance(p, dict) and p.get("角色") == "上游原话"), None),
                "怎么核": it.get("怎么核"),
            })
    out.sort(key=lambda x: x["到期日"])
    return out


def judge(items: list[dict], today: date, ptr_check=check_pointer) -> dict:
    """整份清单的判定。纯逻辑（除 ptr_check 可能读盘），`--controls` 对它做反向对照。"""
    struct: list[str] = []
    ids = [it.get("id") for it in items if isinstance(it, dict)]
    for dup in {x for x in ids if ids.count(x) > 1}:
        struct.append(f"id 重复：{dup}")
    for it in items:
        if not isinstance(it, dict):
            struct.append("条目不是对象")
            continue
        struct.extend(validate_item(it, ptr_check))
    od = overdue_items(items, today)
    code = 1 if (struct or od) else 0
    return {"code": code, "struct_errors": struct, "overdue": od, "total": len(items)}


# ─────────────────────────── 报告 ───────────────────────────

def report(items: list[dict], today: date, res: dict) -> None:
    print("=" * 72)
    print(f"待收清单 · {LIST_PATH.relative_to(REPO)} · 今天（北京时间）{today}")
    print("=" * 72)

    print("\n── A 段：结构判据 ──")
    if res["struct_errors"]:
        for e in res["struct_errors"]:
            print(f"  ❌ {e}")
    else:
        print(f"  ✅ {res['total']} 条全过（含「承诺必须指得出原话」与「我方待问不许标成上游原话」两侧）")

    print("\n── B 段：条目 ──")
    for it in items:
        due = it.get("到期日") or "无到期日"
        mark = "⏳" if any(o["id"] == it.get("id") for o in res["overdue"]) else "·"
        print(f"  {mark} {it.get('id')}  [{it.get('性质')}/{it.get('状态')}]  到期 {due}")
        print(f"      {it.get('事项')}")
        print(f"      谁说的：{it.get('谁说的')}")

    print("\n── C 段：到期 ──")
    if res["overdue"]:
        for o in res["overdue"]:
            over = "今天到期" if o["过期天数"] == 0 else f"已过 {o['过期天数']} 天"
            print(f"  ⏳ {o['id']} {o['事项']} —— 到期 {o['到期日']}（{over}）")
            if o.get("原话"):
                print(f"      原话：「{o['原话']}」")
            print(f"      到期日来源：{o['到期日来源']}"
                  + ("（**我方推算的日期**，到点是问一句，不是判违约）"
                     if o["到期日来源"] == "我方推算" else ""))
    else:
        print("  ✅ 没有到期未收")

    print("\n" + "-" * 72)
    nxt = [o for o in res["overdue"]]
    if nxt:
        d = min(date.fromisoformat(o["到期日"]) for o in nxt)
        print(f"❌ 退 1：{len(nxt)} 件到期未收（最早 {d}）")
    elif res["struct_errors"]:
        print(f"❌ 退 1：结构有 {len(res['struct_errors'])} 处违规")
    else:
        upcoming = sorted(it["到期日"] for it in items
                          if it.get("到期日") and it.get("状态") in {"open", "partial"})
        tail = f"；最近一个到期日 {upcoming[0]}" if upcoming else ""
        print(f"✅ 退 0：结构全过、没有到期未收{tail}")


# ─────────────────────────── 反向对照 ───────────────────────────

def controls() -> int:
    """判据两边都要会响：该红时红，该绿时绿。**没红过的断言不算验证过它。**"""
    T = date(2026, 9, 21)
    base = load_list()[0]
    p01 = base["items"][0]          # 真实的「条件承诺」样本
    p02 = base["items"][1]          # 真实的「我方待问」样本
    p03 = base["items"][2]          # 真实的「承诺 + 有我方推算到期日」样本

    def cp(o, **kw):
        d = json.loads(json.dumps(o))
        d.update(kw)
        return d

    def raw(o, **kw):
        d = json.loads(json.dumps(o))
        d.update(kw)
        return d

    def no_err(o):
        return validate_item(o) == []

    def has_err(o, needle):
        return any(needle in e for e in validate_item(o))

    fake = lambda p: None  # 不读盘的指针检查器（反向对照只在内存里做）

    cases = [
        ("真实样本 P-01（条件承诺）→ 必须过", lambda: no_err(p01)),
        ("真实样本 P-02（我方待问）→ 必须过", lambda: no_err(p02)),
        ("真实样本 P-03（承诺 + 推算到期日）→ 必须过", lambda: no_err(p03)),

        ("★ 性质=承诺 却只有 none 指针 → 必须红",
         lambda: has_err(cp(p03, 出处=[{"kind": "none", "角色": "无", "why": "我觉得她说过"}]),
                         "承诺必须指得出原话")),
        ("★ 反向对照：同一条把「上游原话」指针加回来 → 必须绿（上面那条不是恒红）",
         lambda: no_err(cp(p03))),
        ("★ 性质=我方待问 却有一条被标成上游原话 → 必须红（**这就是本轮那句「她欠着」的形状**）",
         lambda: has_err(cp(p02, 出处=p02["出处"] + [{"kind": "message", "角色": "上游原话",
                                                      "message_id": "om_x100b643ed45a84a4c3b4fa6f80e9c37",
                                                      "quote": "对接人如果需要明确"}]),
                         "不许把我方的问题写成对方的承诺")),

        ("到期日 null 且没写原因 → 必须红",
         lambda: has_err(cp(p01, 无到期日原因=None), "悬着的项必须说清")),
        ("有到期日却没写「到期日依据」→ 必须红",
         lambda: has_err(cp(p03, 到期日依据=None), "日子从哪来的要说得出")),
        ("有到期日却把来源写成「我猜的」→ 必须红",
         lambda: has_err(cp(p03, 到期日来源="我猜的"), "到期日来源非法")),
        ("到期日写成 2026/10/02 → 必须红",
         lambda: has_err(cp(p03, 到期日="2026/10/02"), "格式不对")),

        ("状态=done 但没有完成依据 → 必须红",
         lambda: has_err(cp(p03, 状态="done"), "却没有「完成依据」")),
        ("状态=done 但完成依据是 none 指针 → 必须红",
         lambda: has_err(cp(p03, 状态="done",
                            完成依据=[{"kind": "none", "角色": "无", "why": "她说收到了"}]),
                         "不许出现 none 指针")),
        ("状态=dropped 但没写作废原因 → 必须红",
         lambda: has_err(cp(p03, 状态="dropped"), "却没写「作废原因」")),
        ("状态=随便写 → 必须红", lambda: has_err(cp(p03, 状态="大概吧"), "状态非法")),

        ("★ 真实消息里把 quote 改一个字 → 指针必须红（拿真盘做反向对照）",
         lambda: (lambda q: check_pointer({"kind": "message", "角色": "上游原话",
                                           "message_id": "om_x100b643ed45a84a4c3b4fa6f80e9c37",
                                           "quote": q}) is not None)(
             p01["出处"][0]["quote"].replace("统一入口", "统一入口页"))),
        ("反向对照：**没改**的真 quote → 必须过（上面那条不是恒红）",
         lambda: check_pointer(p01["出处"][0]) is None),
        ("message_id 不存在 → 必须红",
         lambda: check_pointer({"kind": "message", "角色": "上游原话",
                                "message_id": "om_不存在", "quote": "随便"}) is not None),
        ("file 指针的 quote 不在文件里 → 必须红",
         lambda: check_pointer({"kind": "file", "角色": "本地旧件",
                                "path": "PRD/内容治理需求文档.md",
                                "quote": "这句话在文档里不存在"}) is not None),
        ("file 指针指向不存在的文件 → 必须红",
         lambda: check_pointer({"kind": "file", "角色": "本地旧件",
                                "path": "PRD/没有这个文件.md", "quote": "x"}) is not None),
        ("none 指针没写 why → 必须红",
         lambda: check_pointer({"kind": "none", "角色": "无", "why": ""}) is not None),
        ("角色写成没有的词 → 必须红",
         lambda: check_pointer({"kind": "none", "角色": "好像是上游",
                                "why": "x"}) is not None),

        ("到期判据：open + 到期日=昨天 → 必须进到期表",
         lambda: [o["id"] for o in overdue_items([cp(p03, 到期日="2026-09-20")], T)] == ["P-03"]),
        ("到期判据：**今天**到期 → 必须进（当天就算到期）",
         lambda: [o["id"] for o in overdue_items([cp(p03, 到期日="2026-09-21")], T)] == ["P-03"]),
        ("反向对照：open + 到期日=明天 → 必须不进（上面两条不是恒红）",
         lambda: overdue_items([cp(p03, 到期日="2026-09-22")], T) == []),
        ("反向对照：done + 到期日=昨天 → 必须不进（关掉的条不再提醒）",
         lambda: overdue_items([cp(p03, 到期日="2026-09-20", 状态="done",
                                   完成依据=p03["出处"])], T) == []),
        ("partial + 到期日=昨天 → 必须进（部分收到仍算没齐）",
         lambda: [o["id"] for o in overdue_items([cp(p03, 到期日="2026-09-20", 状态="partial")], T)]
                 == ["P-03"]),
        ("无到期日的条目永远不进到期表（P-01 的现状）",
         lambda: overdue_items([p01], date(2030, 1, 1)) == []),

        ("id 重复 → 必须红",
         lambda: "id 重复" in " ".join(judge([p01, cp(p01)], T, fake)["struct_errors"])),
        ("整份清单干净 + 今天 09-21（未到期）→ 退 0",
         lambda: judge([p01, p02, p03], T, fake)["code"] == 0),
        ("同一份清单 + 今天 10-03（已过期）→ 退 1，且只有 P-03",
         lambda: (lambda r: r["code"] == 1 and [o["id"] for o in r["overdue"]] == ["P-03"])(
             judge([p01, p02, p03], date(2026, 10, 3), fake))),
        ("★ 只要结构违规就退 1（哪怕没有到期未收）",
         lambda: judge([cp(p03, 状态="大概吧")], T, fake)["code"] == 1),
        ("清单读不出 → 必须是「未测」，不是红也不是绿",
         lambda: load_list(REPO / "PMO" / "没有这个清单.json")[1] is not None),
    ]

    print("=" * 72)
    print("verify_pending · 反向对照（离线；只读盘上既有文件，不写盘、不联网、不发消息）")
    print("=" * 72)
    bad = 0
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok = bool(fn())
            err = ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（抛异常 {type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i:2}/{len(cases)}] {name}{err}")
    print("-" * 72)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败 —— 判据有问题，别信它")
        return 1
    print(f"✅ {len(cases)} 项全过（含「该红时红」与「该绿时绿」两侧）")
    return 0


# ─────────────────────────── CLI ───────────────────────────

def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    today = bj_today()
    for a in argv:
        if a.startswith("--today="):
            today = date.fromisoformat(a.split("=", 1)[1])

    data, err = load_list()
    if err:
        # ★ 未测 —— 与「通过」和「红」都长得不一样
        if "--json" in argv:
            print(json.dumps({"code": 2, "reason": err, "overdue": [], "struct_errors": [],
                              "total": 0, "today": str(today)}, ensure_ascii=False))
        else:
            print(f"⚠️ 未测：{err}")
            print("   这不是「没有待收」，是「这次没读成」—— 清单在盘上，去看一眼。")
        return 2

    items = [x for x in data["items"] if isinstance(x, dict)]
    res = judge(items, today)
    res["today"] = str(today)

    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False))
        return res["code"]

    report(items, today, res)
    if res["struct_errors"]:
        print("\n  清单本身有问题，先修 PMO/待收清单-v1.json，再看到期那一段。")
    return res["code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
