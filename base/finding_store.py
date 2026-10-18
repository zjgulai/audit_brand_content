#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""finding_store.py —— 唯一 finding 存储：append-only + 三要素准入 + 白名单

DraftFinding → (evidence_sync enrich) → ValidatedFinding → **只收这个**
    ↑ 生产者写，只在内存里传        ↑ 首次落盘，分配 finding_id

--------------------------------------------------------------------------
★ 四条本文件刻意做死的事（每一条都对应一次真实踩过的坑）
--------------------------------------------------------------------------

**一、append-only 不是「不改字段」，是「不改判断内容」**

    Playbook §3.3.4.2 的准确说法：一条 finding 的**判断内容**永不改
    （control_code / severity / location / quote / detected_by / produced_by / authority_ref），
    **唯一允许的变化是 status → superseded**。

    所以本文件把「旧条变 superseded」建模成**一条新事件**（`supersede`），
    而不是就地改字段 —— 这样账本本身仍是纯追加的，
    而「其余字段不动」由构造保证（supersede 事件只带 id）。

    ★ 2026-10-18 实测过一次：把「superseded 后沿用同一 finding_id」写进设计，
      与 Playbook「所有实质变化一律新建一条、新 id」相反。本轮已纠正。

**二、三要素是合取，缺一拒收；且「缺字段」与「字段值为未测」不是一回事**

    准入 = control_code ∧ authority_ref ∧ location 三者都在。
    但 `authority_ref: []`（真的没有依据）与 `authority_ref` 字段不存在（还没算过）
    **必须长得不一样**：前者合法（落 missing 状态），后者是 DraftFinding，拒收。

**三、`confirmed` 必须有 `authority_state`；其余三态不要求**

    DraftFinding 的样子就是「status=confirmed 但没有 authority_state」。
    用一个字段的**存在性**判它，而不是用某个占位值 —— 占位值会让
    「还没 enrich」与「enrich 了但没查到」混成一个。

**四、`finding_id` 全局唯一，重启/重放不得碰撞**

    账本按行读回时会校验唯一性；写新记录时碰撞即拒。
    这不是防御性编程 —— 重放一份账本是本项目验证的常规动作。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

# ── Playbook §3.3.4.1 的白名单（表外组合一律拒收）────────────────
# rule:     不能 candidate（规则命中即确认）
# semantic: 可以 candidate；confirmed 仅限「明确规则类」（C1–C4）
# human:    不能 candidate（人可直接新建 confirmed / 驳回 / 撤销）
ALLOWED: dict[str, frozenset[str]] = {
    "rule": frozenset({"confirmed", "rejected", "superseded"}),
    "semantic": frozenset({"candidate", "confirmed", "rejected", "superseded"}),
    "human": frozenset({"confirmed", "rejected", "superseded"}),
}

VALID_STATUS = frozenset({"candidate", "confirmed", "rejected", "superseded"})
VALID_PRODUCED_BY = frozenset(ALLOWED)
VALID_AUTHORITY_STATE = frozenset({"ok", "missing", "expired", "conflict"})
VALID_SEVERITY = frozenset({"L0", "L1", "L2", "L3", "L4", "L5"})
VALID_DETECTED_BY = frozenset({"P0", "P1", "P2", "P3"})

# 三要素：缺任一即拒收
ADMISSION_KEYS = ("control_code", "authority_ref", "location")

# 判断内容：一旦落盘永不改（supersede 事件也不碰它们）
JUDGEMENT_KEYS = (
    "control_code", "severity", "location", "quote",
    "detected_by", "produced_by", "authority_ref", "authority_state",
)

REQUIRED_KEYS = (
    "finding_id", "control_code", "detected_by", "authority_ref",
    "authority_state", "severity", "status", "location", "quote",
    "produced_by", "derived_from",
)


class FindingRejected(Exception):
    """拒收。**每一条拒收都必须说清是哪个字段、为什么** —— 只说「不合规」等于没说。"""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _is_absent(rec: dict, key: str) -> bool:
    return key not in rec


def check_record(rec: dict, *, require_authority_state: bool | None = None) -> None:
    """
    校验单条记录。抛 FindingRejected。

    `require_authority_state`：
        None  → 按 status 自动判（confirmed 要求，其余不要求）
        True  → 强制要求（DraftFinding 的拒收断言用它反向对照）
        False → 强制不要求
    """
    if not isinstance(rec, dict):
        raise FindingRejected("E_TYPE", f"记录必须是对象，实际 {type(rec).__name__}")

    # ── ① 三要素合取 ────────────────────────────────────────
    # ★ 用「字段是否出现」判，不用「值是否为空」判 ——
    #   authority_ref=[] 是合法状态（真的没有依据），字段缺失才是 draft。
    for k in ADMISSION_KEYS:
        if _is_absent(rec, k):
            raise FindingRejected(
                "E_ADMISSION", f"缺三要素之一 `{k}`（准入是合取：缺一即拒收）")

    # ── ② finding_id 必须存在且非空 ────────────────────────
    fid = rec.get("finding_id")
    if not isinstance(fid, str) or not fid.strip():
        raise FindingRejected("E_ID", f"finding_id 必须是非空字符串，实际 {fid!r}")

    # ── ②b 必填键齐全（quote / derived_from / …）──────────
    # ★ FS-ADV1：`REQUIRED_KEYS` 原先定义了但**从未被迭代** —— 一个死常量。
    #   后果是「缺 quote」「缺 derived_from」两条都能过。现在真的逐键检查。
    #   `authority_state` 不在三要素里、也不在本表的无条件必填里 —— 它由 ⑤ 按 status 条件要求。
    for k in REQUIRED_KEYS:
        if _is_absent(rec, k):
            if k == "authority_state":
                continue  # 由 ⑤ 按 status 判（candidate/rejected 不要求）
            raise FindingRejected("E_REQUIRED", f"缺必填键 `{k}`")
    quote = rec.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        raise FindingRejected("E_REQUIRED", f"quote 必须是非空字符串，实际 {quote!r}")

    # ── ③ 枚举校验 ─────────────────────────────────────────
    pb = rec.get("produced_by")
    if pb not in VALID_PRODUCED_BY:
        raise FindingRejected("E_ENUM", f"produced_by={pb!r} 不在 {sorted(VALID_PRODUCED_BY)}")

    st = rec.get("status")
    if st not in VALID_STATUS:
        raise FindingRejected("E_ENUM", f"status={st!r} 不在 {sorted(VALID_STATUS)}")

    sev = rec.get("severity")
    if sev not in VALID_SEVERITY:
        raise FindingRejected("E_ENUM", f"severity={sev!r} 不在 L0–L5")

    db = rec.get("detected_by")
    if db not in VALID_DETECTED_BY:
        raise FindingRejected("E_ENUM", f"detected_by={db!r} 不在 P0–P3（检测层）")

    # ── ④ produced_by × status 白名单 ──────────────────────
    if st not in ALLOWED[pb]:
        raise FindingRejected(
            "E_WHITELIST",
            f"`{pb}` × `{st}` 是表外组合（允许：{sorted(ALLOWED[pb])}）")

    # ── ⑤ confirmed 必须有 authority_state（DF-2）──────────
    need_as = (st == "confirmed") if require_authority_state is None else require_authority_state
    if need_as:
        if _is_absent(rec, "authority_state"):
            raise FindingRejected(
                "E_DRAFT",
                f"`{st}` 缺 `authority_state` —— 这是 DraftFinding，不许进 store"
                f"（evidence_sync enrich 之后才允许落盘）")
        if rec.get("authority_state") not in VALID_AUTHORITY_STATE:
            raise FindingRejected(
                "E_ENUM",
                f"authority_state={rec.get('authority_state')!r} 不在 {sorted(VALID_AUTHORITY_STATE)}")

    # ── ⑥ derived_from 类型 ────────────────────────────────
    df = rec.get("derived_from", "__absent__")
    if df != "__absent__" and df is not None and not isinstance(df, str):
        raise FindingRejected("E_TYPE", f"derived_from 必须是 string|null，实际 {type(df).__name__}")

    # ── ⑦ M1：semantic 直接 confirmed 必须带 confirmed_by_rule_class=true ──
    # 技术方案 §3 把 M1 唯一归属给 finding_store。Playbook §3.3.4.1：
    # 「只有同时满足 C1–C4 且 rule_class_registry 开关开启时才可直接 confirmed」，
    # 报告里要能一眼分出「人确认的」与「模型按明确规则确认的」——
    # 所以这个标记必须显式为 true，**不许缺省**（缺省当 false，那就不该是 confirmed）。
    if pb == "semantic" and st == "confirmed":
        if rec.get("confirmed_by_rule_class") is not True:
            raise FindingRejected(
                "E_M1",
                "semantic 直接 confirmed 必须带 `confirmed_by_rule_class: true`"
                f"（实际 {rec.get('confirmed_by_rule_class')!r}）—— M1")


class FindingStore:
    """
    append-only 账本 + 只读投影。

    账本（JSONL）里只有两种事件：
        {"op": "append",   "record": {...}}
        {"op": "supersede","id": "..."}

    ★ 为什么 supersede 也走事件：Playbook 说旧条「只把 status 改成 superseded」。
      如果把这条做成「就地改一行」，账本就不再是 append-only 了。
      做成事件之后，**账本纯追加**，而「其余字段不动」由构造保证。
    """

    def __init__(self, path: str | os.PathLike | None = None,
                 id_factory: Callable[[], str] | None = None):
        self.path = Path(path) if path is not None else None
        self._id_factory = id_factory or (lambda: f"f-{uuid.uuid4().hex}")
        self._events: list[dict] = []
        self._view: dict[str, dict] = {}
        self._order: list[str] = []
        if self.path is not None and self.path.exists():
            self._load()

    # ── 读 ────────────────────────────────────────────────
    def _load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError as e:
                    raise FindingRejected("E_LEDGER", f"第 {lineno} 行不是 JSON：{e}")
                self._apply(ev)

    def _apply(self, ev: dict) -> None:
        op = ev.get("op")
        if op == "append":
            rec = ev.get("record")
            if not isinstance(rec, dict):
                raise FindingRejected("E_LEDGER", "append 事件缺 record")
            fid = rec.get("finding_id")
            if fid in self._view:
                raise FindingRejected("E_DUP_ID", f"账本里 finding_id={fid!r} 重复（重放也不许碰撞）")
            self._view[fid] = json.loads(json.dumps(rec))  # 深拷贝：外部改不动账本
            self._order.append(fid)
        elif op == "supersede":
            fid = ev.get("id")
            if fid not in self._view:
                raise FindingRejected("E_LEDGER", f"supersede 指向不存在的 id={fid!r}")
            # ★ 只改 status，其余字段一个都不动
            self._view[fid]["status"] = "superseded"
        else:
            raise FindingRejected("E_LEDGER", f"未知事件 op={op!r}")
        self._events.append(ev)

    def _write(self, ev: dict) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # ── 写 ────────────────────────────────────────────────
    def new_id(self) -> str:
        fid = self._id_factory()
        if fid in self._view:
            raise FindingRejected("E_DUP_ID", f"生成的 finding_id={fid!r} 已存在（重放碰撞）")
        return fid

    def insert(self, rec: dict, *, assign_id: bool = False) -> dict:
        """
        追加一条新 finding。

        `assign_id=True` 时不要求调用方给 id —— 内部生成（首次落盘就这一次）。

        ★ 返回的是**账本里的副本**，不是调用方传进来的那个对象。
          这样「调用方后来改了 dict」不会污染账本（原地改 severity 那条反向对照靠它）。
        """
        rec = dict(rec)  # 浅拷贝顶层，避免调用方后续改 key
        if assign_id:
            rec["finding_id"] = self.new_id()
        check_record(rec)
        if rec["finding_id"] in self._view:
            raise FindingRejected("E_DUP_ID", f"finding_id={rec['finding_id']!r} 已存在（全局唯一）")
        ev = {"op": "append", "record": rec}
        self._apply(ev)
        self._write(ev)
        return self._view[rec["finding_id"]]

    def transition(self, old_id: str, *, new_status: str, **changes: Any) -> dict:
        """
        实质状态变化：**新建一条**，`derived_from` 指旧 id，旧条标 superseded。

        `changes` 只能改非判断字段之外的元信息；判断内容要改就必须新建（本来就新建了），
        所以这里直接把它们放进新记录 —— 但**旧记录一个字段也不动**。

        返回值是新记录。
        """
        if old_id not in self._view:
            raise FindingRejected("E_NOT_FOUND", f"找不到 finding_id={old_id!r}")

        old = self._view[old_id]
        if old["status"] == "superseded":
            raise FindingRejected(
                "E_ALREADY_SUPERSEDED",
                f"{old_id!r} 已被取代，不能再从它派生（derived_from 不许指向已死条目）")

        # 新记录 = 旧记录 + 显式改动；id 新分配；derived_from 指旧 id
        new = {k: v for k, v in old.items() if k != "finding_id"}
        new.update(changes)
        new["status"] = new_status
        new["derived_from"] = old_id
        new["finding_id"] = self.new_id()

        check_record(new)

        # 先追加新条，再标旧的 —— 顺序保证：
        # 如果中途崩溃，最多留下「新条已在、旧条还没标 superseded」，
        # 那是一个可见的不一致（两条都是活的）；反过来会得到「旧的死了、新的没有」，那才是丢数据。
        ev_new = {"op": "append", "record": new}
        self._apply(ev_new)
        self._write(ev_new)

        ev_sup = {"op": "supersede", "id": old_id}
        self._apply(ev_sup)
        self._write(ev_sup)

        return self._view[new["finding_id"]]

    # ── 查询 ──────────────────────────────────────────────
    def get(self, finding_id: str) -> dict | None:
        rec = self._view.get(finding_id)
        return json.loads(json.dumps(rec)) if rec is not None else None

    def active(self) -> list[dict]:
        """参与状态计算的条目：confirmed + candidate（superseded / rejected 不参与）。"""
        return [json.loads(json.dumps(self._view[i])) for i in self._order
                if self._view[i]["status"] in ("confirmed", "candidate")]

    def all_ids(self) -> list[str]:
        return list(self._order)

    def events(self) -> list[dict]:
        return json.loads(json.dumps(self._events))
