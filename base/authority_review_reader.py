#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/authority_review_reader.py —— 从 authority state 读「复核台账摘要」

## 它为什么存在

`GET /api/v1/cases/{id}` 的 `review` 段原本只有两个来源：

| 场景 | `review_read_store` | 读的是 |
|---|---|---|
| 生产 | `projection_proxy` | 投影读模型（由 authority 投影而来） |
| 只读开发装配 | `None` → `ReviewsLedger()` | **内存账本**（进程内，与 authority 无关） |
| 接了写路径的开发装配 | **本模块** | authority state（`web/scripts/review_api_dev.py` 里接线） |

第三行是那个坑：一旦开发装配启用了 `review_command_service`（写路径接通），
`claim` 会写进 **authority**，而 `review` 摘要仍从**内存账本**读 ——
两份数据就此分叉。实测（2026-10-28）：

    POST /cases/{id}/claim  →  200, version=1
    GET  /cases/{id}        →  review.status="unassigned", version=0

于是界面显示「请求已接受，但台账回读未完成」。这**不是时序问题** ——
它在同一次请求之后立刻发生，而且永远发生。

## ★ 它只做读取，不复制状态机

本模块**不判断**「claim 成不成立」「lease 过期没」。那些是
`base/review_reducer.py` 的事，而且已经在写路径上发生过一次。
这里只把 authority state 上**已经有**的字段按 `_review_summary` 认得的
形状摆出来。任何在这里新写的判定都会变成第二个状态机（§2.5）。

## ★ 它不许「补默认值」把缺失装成有值

`state` 上取不到的键给 `None`，不给 `"unassigned"` / `0` / `[]`。
一个不存在的案件在本模块里返回 `None`（由调用方决定 404），
而不是一个全 `None` 的摘要 —— 后者会让「案件不存在」与
「案件存在但台账为空」长得一样。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AuthorityReviewReader:
    """把一个 `BusinessEventStore` 当作「复核台账摘要」的只读来源。

    ★ 接口只实现 `get_case` / `list_drafts` 两个 —— 那是
      `api/review_api._review_summary()` 会调到的全部。
      多实现一个方法就等于多一处会与 `ReviewsLedger` 漂移的口径。
    """

    def __init__(self, authority):
        self._authority = authority

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """读一个案件的复核摘要。**取不到 state 时返回 `None`**，不是空摘要。"""
        state = self._authority.state(case_id)
        if not isinstance(state, dict):
            return None
        return _summary_from_state(case_id, state)

    def list_drafts(self, case_id: str):
        """草稿快照列表。authority 上是 `drafts`（列表，元素是 dict）。"""
        state = self._authority.state(case_id)
        if not isinstance(state, dict):
            return []
        drafts = state.get("drafts")
        return drafts if isinstance(drafts, list) else []


def _summary_from_state(case_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """把 authority state 摆成 `_review_summary` 认得的形状。

    ## 为什么逐个点名键

    与 `_review_summary` 的白名单**成对**：那边只挑这几个键，这边只给这几个。
    多给不会出错（会被丢掉），但少给会让界面显示「未读」——
    而「未读」与「确实没有」在界面上长得一样，那正是本模块要避免的。

    ★ 注意 `assignee` vs `assignee_id`：authority state 上用 `assignee`
      （见 `review_reducer.state.update`），而 `ReviewSummary` 用 `assignee`。
      开发装配此前另一处写的是 `assignee_id`（`AuthorityCaseSource._case`），
      那是给**案件列表**的形状用的，不是给台账摘要用的。两处不同名不是笔误。
    """
    drafts = state.get("drafts")
    return {
        "case_id": case_id,
        "status": state.get("status"),
        "assignee": state.get("assignee"),
        "version": state.get("version"),
        "claimed_at": state.get("claimed_at"),
        "last_activity": state.get("last_activity"),
        "lease_expires": state.get("lease_expires"),
        "released_at": state.get("released_at"),
        "released_draft_id": state.get("released_draft_id"),
        "primary_draft_id": state.get("primary_draft_id"),
        "drafts": drafts if isinstance(drafts, list) else [],
        "fragment_references": (
            state.get("fragment_references")
            if isinstance(state.get("fragment_references"), list) else []
        ),
    }
