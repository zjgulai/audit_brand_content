#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_waivers.py —— 砍掉项的书面 waiver：**到期即红**

## 为什么要有这个文件

T-230 之前的「砍掉项」只活在**散文里** —— 十一二处文档各写一段「本批不做」，
没有任何东西会在它们到期、或有人想把它们悄悄捡回来时说话。一张没有到期日的
砍掉清单，三个月后只剩「当初为什么砍的？」这个问题，而那时没人答得上来。

本脚本把那张清单变成**可判据的台账**：`PMO/audit/waiver-v1.json` 每条必须指得出
`owner`（谁承接）、`到期日`（什么时候必须重做一次决定）、`理由`（为什么这次不做）、
`ticket`（将来靠哪张票收回）、`approved_by`（哪次决定批准的）、`出处`（逐字引用）。

## 它守的那些病（都能在本仓找到原形）

| 病 | 在这里怎么被拦住 |
|---|---|
| **免死金牌**：到期日一栏空着 / 写成「顺延」「自动续期」 | W2 / W9 直接红 —— 没有到期日的豁免等于永久有效 |
| **无人承接**：`owner: 未定` 或一条挂两个人 | W6 红 —— 到期了没人会去收 |
| **空口豁免**：登记的项指不到任何被砍掉的东西 | W8 红 —— `出处` 的 path 必须在盘上，quote 必须非空 |
| **重复豁免**：同一义务拆成两条，先到期那条失效后另一条还撑着 | W3（id 唯一）+ W12（与权威清单逐名对账） |
| **一边豁免一边说不豁免** | W11 红 —— `不豁免` 段的 id 不许与 `items` 重叠 |
| **偷换口径**：清单新增了一项，台账没跟上 | W12 从 ticket 清单**现场解析**砍掉项全集；解析不出 → **未测（退 2）**，不是绿 |

## 本脚本**不判断**什么（明着留着）

* 它**不判**「这条理由写得对不对」。理由好不好是人的判断，脚本只断言它非空且来自
  一次写下来的决定（`approved_by`）。
* 它**没有触发者**。`tools/agent/`（守衡链）是 8a 独占、改动要重启（AGENTS.md §2.7），
  本脚本不往那里挂。**到期是否能被发现，取决于有人跑它** —— 这一条写进台账的
  `读法.触发点` 字段，报告最后一并念出来，不假装已经接上。

## 断言

| 段 | 断言 |
|---|---|
| W1 | 顶层 `schema` / `items` 结构可读；`items` 非空 |
| W2 | 每条 `id/item/owner/到期日/理由/ticket/approved_by/到期日依据/出处` 九个字段非空 |
| W3 | `id` 唯一 |
| W4 | `到期日` 是 `YYYY-MM-DD` 且可解析 |
| W5 | `状态 ∈ {active, closed, revoked}`；`revoked` 必须写 `撤销原因` |
| W6 | `owner` 具名且**恰好一个**（不许「未定 / 待定 / TBD」，不许 `+` `、` `和` 并联） |
| W7 | **到期即红**：`active` 且 北京时间今天 ≥ `到期日` |
| W8 | `出处` 非空；`kind ∈ {file, ticket, doc}`；`path` 指向的文件在盘上；`quote` 非空 |
| W9 | `到期日依据` 非空，且不含「顺延 / 自动续期 / 永久」——那是免死金牌的形状 |
| W10 | `到期日` 距今天不超过 **180 天**（waiver 不是长期授权） |
| W11 | `不豁免` 段每条有 `id/item/为什么不能豁免/依据`，且 id 不与 `items` 重叠、不带 `到期日` |
| W12 | **逐名对账**：ticket 清单解析出的每个砍掉项，都必须出现在 `items` 或 `不豁免` 里 |

退出码：全过 **0** ／ 有红 **1** ／ 读不出（台账或清单读不出、解析不出）**2**
（未测 ≠ 通过 ≠ 红，AGENTS.md §2.4.2）。

复现：
    python3 tools/verify_waivers.py
    python3 tools/verify_waivers.py --controls
    python3 tools/verify_waivers.py --today=2026-12-01      # 注入日只读，不落状态
    python3 tools/verify_waivers.py --json
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from bj_time import bj_today  # noqa: E402

#: 台账与权威清单都写成模块级常量：`tools/verify_coverage.py` 的 **C 段**要求
#: subjects 的文件名 + 至少一个父目录段在源码里**逐字出现**（这里出现 waiver-v1.json 与 PMO/audit）。
WAIVERS = REPO / "PMO" / "audit" / "waiver-v1.json"
TICKETS = REPO / "PMO" / "上线Ticket清单-20261022.md"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_STATUS = ("active", "closed", "revoked")
ALLOWED_KIND = ("file", "ticket", "doc")
REQUIRED_FIELDS = ("id", "item", "owner", "到期日", "理由", "ticket", "approved_by", "到期日依据", "出处")
NOT_WAIVABLE_FIELDS = ("id", "item", "为什么不能豁免", "依据")
PERMANENT_HINTS = ("顺延", "自动续期", "永久")
NOT_NAMED = ("未定", "待定", "TBD", "tbd")
MULTI_OWNER = ("+", "、", "和", "/")

#: waiver 不是长期授权：离今天超过半年的一律红。
MAX_DAYS = 180

#: 同一件事在两份权威文件里用了不同措辞时才登记在这里 —— 不是模糊匹配。
ALIAS = {"282 ID": "282 ID 映射"}


class Unreadable(Exception):
    """读不出 —— 落未测（退 2），不许当成「没有砍掉项」。"""


# ─────────────────────────── 读 ───────────────────────────


def read_registry(path: Path | None = None) -> dict:
    p = Path(path) if path is not None else WAIVERS
    if not p.is_file():
        raise Unreadable(f"没有这个文件：{p}")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Unreadable(f"{p} 不是合法 JSON：{type(e).__name__}: {e}")
    if not isinstance(d, dict):
        raise Unreadable(f"{p} 顶层不是对象（读到 {type(d).__name__}）")
    items = d.get("items")
    if not isinstance(items, list) or not items:
        raise Unreadable(f"{p} 的 `items` 读不出或为空 —— 口径可能改了，按未测处理")
    if not isinstance(d.get("不豁免", []), list):
        raise Unreadable(f"{p} 的 `不豁免` 不是数组")
    return d


def _norm(name: str) -> str:
    s = str(name).replace("`", "").replace("*", "").strip().strip("。；;，,")
    s = re.sub(r"\s+", " ", s)
    return ALIAS.get(s, s)


def _split_names(raw: str) -> list[str]:
    raw = raw.replace("`", "").replace("*", "")
    return [_norm(p) for p in re.split(r"\s*/\s*", raw) if _norm(p)]


def parse_ticket_items(path: Path | None = None) -> tuple[list[str], str]:
    """从权威 ticket 清单现场解析「砍掉项全集」。

    两个来源：`T-230` 那行括号里的 6 项、`### W3` 下面那一行的 15 项。
    解析出的名字少于 5 个 → 抛 `Unreadable`（口径变了，按未测处理，不许当成绿）。
    """
    p = Path(path) if path is not None else TICKETS
    if not p.is_file():
        raise Unreadable(f"没有权威清单：{p}")
    lines = p.read_text(encoding="utf-8").splitlines()

    t230 = w3 = None
    for i, line in enumerate(lines):
        if t230 is None and line.startswith("| **T-230**"):
            m = re.search(r"waiver（([^）]+)）", line)
            if m:
                t230 = m.group(1)
        if w3 is None and line.startswith("### W3"):
            for j in range(i + 1, min(i + 6, len(lines))):
                if " / " in lines[j]:
                    w3 = lines[j]
                    break

    names: list[str] = []
    if t230:
        names += _split_names(t230)
    if w3:
        names += _split_names(w3)
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    if len(out) < 5:
        raise Unreadable(
            f"从 {p.name} 只解析出 {len(out)} 个砍掉项（T-230={t230!r} / W3={w3!r}）——"
            " 清单格式变了，按未测处理"
        )
    n230 = len(_split_names(t230)) if t230 else 0
    nw3 = len(_split_names(w3)) if w3 else 0
    return out, f"T-230 {n230} 项 + W3 {nw3} 项"


# ─────────────────────────── 判 ───────────────────────────


def _exists(path_raw: str) -> bool:
    """`path` 允许写成 `file:line`；判存在时把行号剥掉。"""
    s = str(path_raw).strip()
    m = re.match(r"^(.*?):\d+$", s)
    if m:
        s = m.group(1)
    return (REPO / s).exists()


def _strip_line(path_raw: str) -> str:
    s = str(path_raw).strip()
    m = re.match(r"^(.*?):\d+$", s)
    return m.group(1) if m else s


def _flat(s: str) -> str:
    """比引文时忽略空白与 markdown 强调符 —— 它们不是内容差异。"""
    return re.sub(r"\s+", "", str(s).replace("*", "").replace("`", ""))


def _quote_in(path_raw: str, quote: str) -> bool | None:
    """引文是否**逐字**在该文件里。读不出返回 None（落未测，不当成红也不当成绿）。"""
    p = REPO / _strip_line(path_raw)
    if not p.is_file():
        return False
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return _flat(quote) in _flat(text)


def judge(items: list, not_waivable: list, today: dt.date,
          required_names: list | None = None) -> dict:
    """纯函数：`--controls` 直接喂内存样本（反向对照不落盘、不联网）。"""
    problems: list[str] = []
    untested: list[str] = []
    rows: list[dict] = []

    ids: dict[str, int] = {}
    for it in items:
        if not isinstance(it, dict):
            problems.append(f"W1 条目不是对象（读到 {type(it).__name__}）")
            continue
        iid = str(it.get("id") or "?")

        # W2 必填
        for k in REQUIRED_FIELDS:
            v = it.get(k)
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v):
                problems.append(f"W2 {iid}：缺 `{k}` —— 这一栏空着，豁免就不成立")

        # W3 唯一
        ids[iid] = ids.get(iid, 0) + 1

        # W4 日期
        due = None
        raw_due = it.get("到期日")
        if raw_due not in (None, ""):
            if not DATE.match(str(raw_due)):
                problems.append(f"W4 {iid}：`到期日` = {raw_due!r} 不是 YYYY-MM-DD —— 算不出到期")
            else:
                try:
                    due = dt.date.fromisoformat(str(raw_due))
                except ValueError:
                    problems.append(f"W4 {iid}：`到期日` = {raw_due!r} 解析不了")

        # W5 状态
        status = it.get("状态", "active")
        if status not in ALLOWED_STATUS:
            problems.append(f"W5 {iid}：`状态` = {status!r} 不在 {list(ALLOWED_STATUS)} 里")
        if status == "revoked" and not str(it.get("撤销原因") or "").strip():
            problems.append(f"W5 {iid}：状态是 revoked 却没写 `撤销原因` —— 撤销得说清为什么")

        # W6 owner
        owner = str(it.get("owner") or "")
        if any(h in owner for h in NOT_NAMED):
            problems.append(f"W6 {iid}：`owner` = {owner!r} —— 到期了没人会去收")
        if any(s in owner for s in MULTI_OWNER):
            problems.append(f"W6 {iid}：`owner` = {owner!r} 挂了多个 —— 必须**恰好一个**具名承接人")

        # W8 出处
        refs = it.get("出处")
        if isinstance(refs, list):
            if not refs:
                problems.append(f"W8 {iid}：`出处` 是空的 —— 这条豁免指不到任何被砍掉的东西")
            for k, ref in enumerate(refs):
                if not isinstance(ref, dict):
                    problems.append(f"W8 {iid}：出处[{k}] 不是对象")
                    continue
                kind = ref.get("kind")
                if kind not in ALLOWED_KIND:
                    problems.append(f"W8 {iid}：出处[{k}].kind = {kind!r} 不在 {list(ALLOWED_KIND)} 里")
                quote = str(ref.get("quote") or "")
                if not quote.strip():
                    problems.append(f"W8 {iid}：出处[{k}] 没有 `quote` —— 指不出原话就只是转述")
                rp = ref.get("path")
                if not rp:
                    problems.append(f"W8 {iid}：出处[{k}] 没有 `path`")
                elif not _exists(str(rp)):
                    problems.append(f"W8 {iid}：出处[{k}].path = {rp!r} 在盘上不存在")
                elif quote.strip():
                    # ★ 引文必须**逐字**在该文件里：这是防「出处是转述」的那一条。
                    hit = _quote_in(str(rp), quote)
                    if hit is False:
                        problems.append(
                            f"W8 {iid}：出处[{k}] 的 quote 在 {rp} 里找不到逐字匹配 ——"
                            f" 引文对不上（读到的 quote：{quote[:40]!r}…）"
                        )
                    elif hit is None:
                        untested.append(f"W8 {iid}：出处[{k}].path = {rp!r} 读不出，引文没法核对")

        # W9 到期日依据
        basis = str(it.get("到期日依据") or "")
        for hint in PERMANENT_HINTS:
            if hint in basis:
                problems.append(
                    f"W9 {iid}：`到期日依据` 含「{hint}」—— 那是永久免死金牌的形状；"
                    " 到期后必须重做一次书面决定，不许自动续期"
                )

        # W10 到期上限
        if due is not None:
            days = (due - today).days
            if days > MAX_DAYS:
                problems.append(f"W10 {iid}：到期日 {due} 距今天 {days} 天 > {MAX_DAYS} —— waiver 不是长期授权")

        rows.append({
            "id": iid, "item": str(it.get("item") or ""), "owner": owner,
            "due": str(raw_due or ""), "days": (due - today).days if due else None,
            "status": status, "ticket": str(it.get("ticket") or ""),
        })

    for iid, n in ids.items():
        if n > 1:
            problems.append(f"W3 {iid}：id 出现 {n} 次 —— 两条豁免撞在同一个编号上")

    # W11 不豁免段
    nw_ids = set()
    for k, it in enumerate(not_waivable or []):
        if not isinstance(it, dict):
            problems.append(f"W11 不豁免[{k}] 不是对象")
            continue
        nid = str(it.get("id") or f"不豁免[{k}]")
        nw_ids.add(nid)
        for f in NOT_WAIVABLE_FIELDS:
            if not str(it.get(f) or "").strip():
                problems.append(f"W11 {nid}：缺 `{f}` —— 「不豁免」也要说清依据，否则只是另一句散文")
        if "到期日" in it:
            problems.append(f"W11 {nid}：`不豁免` 段不许带 `到期日` —— 它没有豁免效力，带了会误导")
        if nid in ids:
            problems.append(f"W11 {nid}：同一编号同时出现在 `items` 与 `不豁免` —— 一边豁免一边说不豁免")

    # W12 逐名对账
    if required_names is not None:
        have = {_norm(r["item"]) for r in rows} | {_norm(it.get("item", "")) for it in (not_waivable or []) if isinstance(it, dict)}
        for name in required_names:
            if _norm(name) not in have:
                problems.append(
                    f"W12 权威清单里的「{name}」在台账里找不到 ——"
                    " 它既没被豁免、也没被写进「不豁免」；要么补登，要么在 `不豁免` 段说明"
                )

    rows.sort(key=lambda r: (r["days"] is None, r["days"] if r["days"] is not None else 0, r["id"]))
    expired = [r for r in rows if r["status"] == "active" and r["days"] is not None and r["days"] <= 0]
    for r in expired:
        problems.append(
            f"W7 {r['id']}：「{r['item']}」到期日 {r['due']} 已到（剩 {r['days']} 天）——"
            f" 到期即红：请 owner {r['owner']} 重做一次书面决定（续期要写新理由与新日期）"
        )

    return {"problems": problems, "untested": untested, "rows": rows, "expired": expired, "n": len(rows)}


# ─────────────────────────── 反向对照 ───────────────────────────


def _good_item() -> dict:
    return {
        "id": "WV-TEST",
        "item": "12 页工作台",
        "owner": "audit-multi-content-1d",
        "到期日": "2026-11-22",
        "理由": "本批只落 5 个页面（T-230）",
        "ticket": "T-230",
        "approved_by": "T-230（2026-10-22）",
        "到期日依据": "上线日 + 30 天；上线日未定，取占位日 2026-11-22",
        "状态": "active",
        "出处": [{"kind": "ticket", "path": "PMO/上线Ticket清单-20261022.md:66",
                  "quote": "砍掉项的书面 waiver（12 页工作台 / 技术栈迁移 / 638 MECE / 282 ID / 视频 / 品牌 T10）"}],
    }


def controls() -> int:
    T = dt.date(2026, 10, 22)
    good = _good_item()

    def judge1(item=None, nw=None, names=None):
        return judge([item or good], nw if nw is not None else [], T, names)

    def red(item=None, nw=None, names=None) -> bool:
        return bool(judge1(item, nw, names)["problems"])

    def red_named(frag: str, item=None, nw=None, names=None) -> bool:
        return any(frag in p for p in judge1(item, nw, names)["problems"])

    cases = [
        ("正样本：齐备且未到期 → 必须绿", lambda: not red()),
        ("★ 到期即红：到期日=昨天 → 必须红且点名（W7）",
         lambda: red_named("W7", {**good, "到期日": "2026-10-21"})),
        ("★ 反向对照：到期日=明天 → 必须重新变绿（上面那条不是恒红）",
         lambda: not red({**good, "到期日": "2026-10-23"})),
        ("边界：到期日=今天 → 必须红（当天就算到期）",
         lambda: red_named("W7", {**good, "到期日": "2026-10-22"})),
        ("坏样本：缺 `owner` → 必须红（W2）", lambda: red_named("W2", {**good, "owner": ""})),
        ("坏样本：`owner` = 未定 → 必须红（W6）", lambda: red_named("W6", {**good, "owner": "未定"})),
        ("坏样本：一条挂两个 owner → 必须红（W6）",
         lambda: red_named("W6", {**good, "owner": "audit-multi-content-1d + production-backend-assembly"})),
        ("坏样本：缺 `理由` → 必须红（W2）", lambda: red_named("W2", {**good, "理由": "  "})),
        ("坏样本：缺 `ticket` → 必须红（W2）", lambda: red_named("W2", {**good, "ticket": ""})),
        ("坏样本：缺 `approved_by` → 必须红（W2）", lambda: red_named("W2", {**good, "approved_by": ""})),
        ("坏样本：缺 `到期日依据` → 必须红（W2）", lambda: red_named("W2", {**good, "到期日依据": ""})),
        ("★ 免死金牌：`到期日依据` 写「材料未到则顺延」→ 必须红（W9）",
         lambda: red_named("W9", {**good, "到期日依据": "其余 7 品线材料到齐后；材料未到则顺延"})),
        ("坏样本：到期日写成 2026/11/22 → 必须红（W4）",
         lambda: red_named("W4", {**good, "到期日": "2026/11/22"})),
        ("坏样本：到期日超过 180 天 → 必须红（W10）",
         lambda: red_named("W10", {**good, "到期日": "2027-12-31"})),
        ("坏样本：revoked 没写撤销原因 → 必须红（W5）",
         lambda: red_named("W5", {**good, "状态": "revoked"})),
        ("坏样本：状态写成「大概吧」→ 必须红（W5）",
         lambda: red_named("W5", {**good, "状态": "大概吧"})),
        ("坏样本：出处 path 指向盘上不存在的文件 → 必须红（W8）",
         lambda: red_named("W8", {**good, "出处": [{"kind": "file", "path": "PMO/audit/没有这个文件.md:1", "quote": "x"}]})),
        ("反向对照：把出处换回真实文件 → 必须重新变绿（上面那条不是恒红）",
         lambda: not red({**good, "出处": [{"kind": "file", "path": "PMO/上线Ticket清单-20261022.md:66",
                                            "quote": "砍掉项的书面 waiver（12 页工作台 / 技术栈迁移 / 638 MECE / 282 ID / 视频 / 品牌 T10）"}]})),
        ("★ 坏样本：出处 quote 在该文件里逐字找不到 → 必须红（W8，防「出处是转述」）",
         lambda: red_named("W8", {**good, "出处": [{"kind": "file", "path": "PMO/上线Ticket清单-20261022.md:66",
                                                   "quote": "这句话在文件里根本不存在"}]})),
        ("坏样本：出处没有 quote → 必须红（W8）",
         lambda: red_named("W8", {**good, "出处": [{"kind": "ticket", "path": "PMO/上线Ticket清单-20261022.md:66", "quote": ""}]})),
        ("坏样本：两条同 id → 必须红（W3）",
         lambda: any("W3" in p for p in judge([good, good], [], T, None)["problems"])),
        ("坏样本：`不豁免` 缺依据 → 必须红（W11）",
         lambda: red_named("W11", nw=[{"id": "NW-1", "item": "census 棘轮", "为什么不能豁免": "它现在是红的"}])),
        ("坏样本：`不豁免` 段带了 `到期日` → 必须红（W11）",
         lambda: red_named("W11", nw=[{"id": "NW-1", "item": "x", "为什么不能豁免": "y", "依据": "z", "到期日": "2026-11-22"}])),
        ("坏样本：同一 id 同时在 `items` 与 `不豁免` → 必须红（W11）",
         lambda: red_named("W11", nw=[{"id": "WV-TEST", "item": "x", "为什么不能豁免": "y", "依据": "z"}])),
        ("★ 口径漂移：权威清单里的一项既没豁免也没写不豁免 → 必须红（W12）",
         lambda: red_named("W12", names=["12 页工作台", "监控告警"])),
        ("反向对照：清单项全都在台账里 → 必须绿（上面那条不是恒红）",
         lambda: not red(names=["12 页工作台"])),
        ("★ 未测：台账不存在 → 必须抛 Unreadable（退 2，不是红也不是绿）",
         lambda: _raises_unreadable(REPO / "PMO" / "audit" / "__没有这个台账__.json")),
        ("★ 未测：台账不是合法 JSON → 必须抛 Unreadable",
         lambda: _raises_unreadable_json()),
    ]

    bad = 0
    print("=" * 78)
    print("砍掉项 waiver · 反向对照（离线；只在内存里做，不写盘、不联网）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（抛异常 {type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败 —— 判据有问题，别信它")
        return 1
    print(f"✅ {len(cases)} 项全过（含「该红时红」「该绿时绿」「该未测时未测」三侧）")
    return 0


def _raises_unreadable(path: Path) -> bool:
    try:
        read_registry(path)
    except Unreadable:
        return True
    return False


def _raises_unreadable_json() -> bool:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "broken.json"
        p.write_text("{not json", encoding="utf-8")
        try:
            read_registry(p)
        except Unreadable:
            return True
    return False


# ─────────────────────────── 报 ───────────────────────────


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    today = bj_today()
    for a in argv:
        if a.startswith("--today="):
            try:
                today = dt.date.fromisoformat(a.split("=", 1)[1])
            except ValueError:
                print(f"⚠️ 未测：`--today=` 的值解析不了：{a}")
                return 2

    try:
        reg = read_registry()
        required, scope = parse_ticket_items()
    except Unreadable as e:
        print(f"⚠️ 未测：{e}")
        print("   这不是「没有砍掉项」，是**这次没读成** —— 退 2（未测 ≠ 通过 ≠ 红）。")
        return 2

    items = reg.get("items", [])
    not_waivable = reg.get("不豁免", [])
    r = judge(items, not_waivable, today, required)

    if "--json" in argv:
        code = 1 if r["problems"] else (2 if r["untested"] else 0)
        print(json.dumps({
            "today": today.isoformat(),
            "scope": scope,
            "required": required,
            "n_items": r["n"],
            "expired": [x["id"] for x in r["expired"]],
            "problems": r["problems"],
            "untested": r["untested"],
            "code": code,
        }, ensure_ascii=False, indent=2))
        return code

    print("=" * 78)
    print(f"砍掉项 waiver · 基准日 {today}（北京时间；`--today=` 可注入，注入不落状态）")
    print("=" * 78)
    print(f"  台账：{WAIVERS.relative_to(REPO)}   权威清单：{TICKETS.relative_to(REPO)}")
    print(f"  豁免 {r['n']} 条 · 不豁免 {len(not_waivable)} 条 · 对账范围：{scope}")
    print()
    for row in r["rows"]:
        if row["days"] is None:
            tail = "剩【未测】"
        elif row["days"] < 0:
            tail = f"**已过期 {-row['days']} 天**"
        elif row["days"] == 0:
            tail = "**今天到期**"
        else:
            tail = f"剩 {row['days']} 天"
        mark = "❌" if (row["status"] == "active" and row["days"] is not None and row["days"] <= 0) else "·"
        print(f"  {mark} {row['id']:<10} {row['item']}  →  {row['due']}（{tail}）  owner={row['owner']}")
    if not_waivable:
        print()
        print("  ── 不豁免（只记录，无豁免效力）──")
        for it in not_waivable:
            print(f"    · {it.get('id')} {it.get('item')}：{str(it.get('为什么不能豁免', ''))[:60]}")
    print()
    print("  ⚠️ 触发点：**没有守护进程会自动跑本脚本**（`tools/agent/` 归 8a、改动要重启）。")
    print("      到期是否能被发现，取决于有人跑它 —— 这一条是未闭项，不是已兑现的承诺。")
    print()

    # ── `--expiry-warn-only`：把「到期」与「结构性错误」分开 ────────────────
    #   ★ 2026-10-23 加，**为挂进 CI 而加**（T-230 收口）。
    #
    #   为什么不能直接把本脚本挂进 CI：
    #     一到期，本脚本退 1，而 CI 里退 1 就是失败。那时只有两条路 ——
    #     改到期日（等于作弊）或让 CI 长期红着（永远红的 CI 会被无视，§2.1.1）。
    #
    #   所以这里把两类问题分开：
    #     · **结构性错误**（字段缺失、日期解析不出、owner 未定…）→ **仍然退 1，阻断**
    #     · **到期**（W7）→ **不阻断**，但**必须大声打出来**并计数
    #
    #   ★ 这是在**换判据，不是放宽判据**（与 `verify_acceptance_trigger.py --scope ci`
    #     同一个思路）：CI 能保证的是「台账结构没烂、读数算得出」；
    #     「到期了该怎么办」是一次书面决定，不是 CI 能替人做的。
    warn_only = any(a in ("--expiry-warn-only",) for a in argv)
    w7 = [p for p in r["problems"] if str(p).startswith("W7 ")]
    rest = [p for p in r["problems"] if not str(p).startswith("W7 ")]

    if warn_only:
        print("  ── `--expiry-warn-only`：到期不阻断，结构性错误照旧阻断 ──")
        if w7:
            print(f"  ⚠️ **{len(w7)} 条豁免已到期**（不阻断 CI，但必须有人处理）：")
            for p in w7:
                print(f"     ⚠️ {p}")
            print("     → 处置：owner 做一次书面决定（续期要写新理由与新日期，或转 closed/revoked）。")
        else:
            print(f"  ✅ 无到期项（{r['n']} 条 active 全部未到期）。")
        if rest:
            print()
            print(f"  ❌ 结构性错误 {len(rest)} 处 —— **这些仍然阻断**：")
            for p in rest:
                print(f"     ❌ {p}")
            print()
            print(f"❌ 退 1：{len(rest)} 处结构性问题（到期 {len(w7)} 条，已按 --expiry-warn-only 降为告警）")
            return 1
        if r["untested"]:
            print()
            print(f"  ⚠️ 未测 {len(r['untested'])} 处（**没测成**，不是通过）：")
            for u in r["untested"]:
                print(f"     ⚠️ {u}")
            print()
            print("⚠️ 退 2：有未测 —— 未测 ≠ 通过")
            return 2
        print()
        print(f"✅ 退 0（expiry-warn-only）：台账结构完整、读数算得出；"
              f"到期 {len(w7)} 条已告警，处置由 owner 做书面决定。")
        return 0

    if r["problems"]:
        print(f"── 有问题 {len(r['problems'])} 处 ──")
        for p in r["problems"]:
            print(f"  ❌ {p}")
        if r["untested"]:
            print(f"── 另有未测 {len(r['untested'])} 处（**这次没测成**，不是通过）──")
            for u in r["untested"]:
                print(f"  ⚠️ {u}")
        print()
        print(f"❌ 退 1：{len(r['problems'])} 处不成立（含到期 {len(r['expired'])} 条）"
              + (f"，另有 {len(r['untested'])} 处未测" if r["untested"] else ""))
        return 1
    if r["untested"]:
        print(f"── 未测 {len(r['untested'])} 处 ──")
        for u in r["untested"]:
            print(f"  ⚠️ {u}")
        print()
        print(f"⚠️ 退 2：断言没有红，但有 {len(r['untested'])} 处**没测成** —— 未测 ≠ 通过")
        return 2
    print(f"✅ 退 0：{r['n']} 条豁免都指得出 owner / 到期日 / 理由 / ticket / 批准人 / 出处，且未到期")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
