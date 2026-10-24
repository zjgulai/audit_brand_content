#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_lease_release.py —— 行 136：到期释放 / 草稿交接 / 乐观锁

## 行 136 原文的四件事，与本文件的覆盖

| 行 136 要求 | 执行点 | 状态 |
|---|---|---|
| 注入时钟：29 分钟仍独占 / 30 分 01 秒释放 | **L1**（reducer 侧，`now`/`lease_seconds` 可注入） | ✅ |
| 释放**前**草稿已保存、新领取人看得到内容 | **L2**（save_draft → expire → 再 claim，内容仍在） | ✅ |
| 通知只发工作台、飞书发送调用次数为 0 | — | ❌ **生产侧无通知生产者** |
| 两个写者并发改同一 assignment，只有带正确 lease/version 的成功 | **L3**（expected_version 陈旧 → version_conflict） | ✅ |

**通知那半为什么没有对象**（五类通道都查过）：
1. 直接 import：`api/` 里 `outbox` / `NotificationOutbox` 0 命中。
2. 传递依赖：`review_command_service` 只 import `Projector` / `AuthorityConflict`。
3. 代码实现：唯一实现是 `base/notifications.py` 的 `NotificationOutbox`，
   只被 legacy `ReviewsLedger(outbox=…)` 接。
4. 数据：`review_reducer.py:5` 明写「不发通知」；`NOTIFYING_KINDS` 也只有
   `lease_released` / `formal_submit`。
5. 运行时读取：生产 `maintain_once` 只跑 `expire_if_due` + 投影，不碰 outbox。

也就是说：**生产路径今天一条通知都不发**。此时断言「飞书调用次数为 0」是恒真的
（没有发送点），属于 §2.4 的假执行点 —— 所以不写，也不据此映射 #136。

## 主体

判据对象是 `base/review_reducer.py` 的 `reduce_command`（claim / save_draft /
expire_lease）与 `base/reviews_ledger.py` 的租约常量；两套实现的边界差一秒
（ledger `now >= lease_expires` 释放，reducer `now > lease_expires` 才放），
行 136 只要求 29 分钟与 30 分 01 秒两点，两者在这两点上一致。

## 退出码
0 全过 / 1 有红 / 2 未测（导入失败）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEASE = 1800
T0 = 1000.0


class Untested(Exception):
    pass


def _mod():
    try:
        from base import review_reducer as R  # noqa: PLC0415
        return R
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 review_reducer 失败：{type(e).__name__}: {e}")


def claimed(R, actor="alice", now=T0, lease=LEASE):
    st = R.initial_state("case-lease")
    st, _ev, _r = R.reduce_command(
        st, "claim", actor, 0, {"case_id": "case-lease"}, now=now, lease_seconds=lease)
    return st


def check_boundary(R) -> list[str]:
    """L1：29 分钟不释放；30 分 01 秒释放。"""
    problems = []
    st = claimed(R)
    try:
        R.reduce_command(st, "expire_lease", "system", st["version"],
                         {"case_id": "case-lease"}, now=T0 + 29 * 60, lease_seconds=LEASE)
        problems.append("L1 29 分钟就允许了 expire_lease —— 应当仍是 lease_active")
    except R.LedgerConflict as e:
        if e.code != "lease_active":
            problems.append(f"L1 29 分钟被拒的原因不是 lease_active：{e.code}")
    # ★ 2026-10-24：这个调用原先**没有 try/except**。
    #   后果实测（把 reducer 的过期阈值 +10 分钟）：`reduce_command` 抛
    #   `LedgerConflict("lease_active")`，异常一路穿过 assess()，被 main 的
    #   `except Exception` 兜成 **rc=2（未测）**，打印「⚠️ 未测：LedgerConflict」。
    #
    #   **也就是说这一行永远不会红：它只可能绿，或「未测」。**
    #   一条判据如果不能红，它就不是判据 —— 这正是本行此前一直不映射的原因之一。
    #   现在把冲突折成一条红项：生产在 30 分 01 秒仍说「尚未过期」，就是结论错了。
    try:
        st2, _ev, _r = R.reduce_command(
            st, "expire_lease", "system", st["version"], {"case_id": "case-lease"},
            now=T0 + LEASE + 1, lease_seconds=LEASE)
    except R.LedgerConflict as e:
        problems.append("L1 30 分 01 秒未释放：reduce_command 抛 %s（%s）"
                        % (e.code, e))
        return problems
    if st2.get("status") != "released":
        problems.append(f"L1 30 分 01 秒未释放：status={st2.get('status')!r}")
    return problems


def check_draft_handoff(R) -> list[str]:
    """L2：释放前保存的草稿，释放后仍在新领取人看得到的状态里。"""
    problems = []
    st = claimed(R)
    st, _ev, _r = R.reduce_command(
        st, "save_draft", "alice", st["version"],
        {"case_id": "case-lease", "notes": "已核 3 条", "form": {"severity": "L4"},
         "evidence_selections": ["E-1"]},
        now=T0 + 60, lease_seconds=LEASE)
    # ★ 同 L1：这一处也缺 try/except（2026-10-24 一并修）。
    #   否则「该释放却没释放」会以「⚠️ 未测」的形式溜走，而不是一条红项。
    try:
        st, _ev, _r = R.reduce_command(
            st, "expire_lease", "system", st["version"], {"case_id": "case-lease"},
            now=T0 + LEASE + 1, lease_seconds=LEASE)
    except R.LedgerConflict as e:
        problems.append("L2 30 分 01 秒未释放：reduce_command 抛 %s（%s）"
                        % (e.code, e))
        return problems
    drafts = st.get("drafts") or []
    if not drafts:
        problems.append("L2 释放后 drafts 为空 —— 交接内容丢了")
    else:
        last = drafts[-1]
        if last.get("notes") != "已核 3 条":
            problems.append(f"L2 释放后草稿内容不是保存的那份：{last.get('notes')!r}")
    # 新领取人：bob claim 后 drafts 仍在
    st2, _ev, _r = R.reduce_command(
        st, "claim", "bob", st["version"], {"case_id": "case-lease"},
        now=T0 + LEASE + 10, lease_seconds=LEASE)
    if st2.get("assignee") != "bob":
        problems.append(f"L2 新领取人没拿到案件：assignee={st2.get('assignee')!r}")
    if not st2.get("drafts"):
        problems.append("L2 新领取人看不到释放前的草稿")
    return problems


def check_optimistic_lock(R) -> list[str]:
    """L3：陈旧 version 必须被拒。

    ★ 判据落在 `reduce_command` 的 **expected_version 守卫**上，不是「传两份 state」——
      reducer 是纯函数，传旧 state 本身就是一次合法历史重放；真正的并发 CAS 在
      service / projection 层（verify_projection_store 已覆盖）。
    """
    problems = []
    st = claimed(R)                       # version = 1
    try:
        R.reduce_command(
            st, "save_draft", "alice", st["version"] - 1,   # 陈旧 version
            {"case_id": "case-lease", "notes": "B"}, now=T0 + 20, lease_seconds=LEASE)
        problems.append("L3 陈旧 expected_version 的写入成功了 —— 乐观锁没生效")
    except R.LedgerConflict as e:
        if e.code != "version_conflict":
            problems.append(f"L3 陈旧 version 被拒的原因不是 version_conflict：{e.code}")
    st2, _ev, _r = R.reduce_command(
        st, "save_draft", "alice", st["version"],
        {"case_id": "case-lease", "notes": "A"}, now=T0 + 10, lease_seconds=LEASE)
    if st2.get("version") == st.get("version"):
        problems.append("L3 成功写入没有推进 version")
    return problems


def assess(R) -> list[str]:
    return check_boundary(R) + check_draft_handoff(R) + check_optimistic_lock(R)


def controls() -> int:
    R = _mod()
    base = assess(R)
    bad_lease = claimed(R, lease=1900)
    try:
        R.reduce_command(bad_lease, "expire_lease", "system", bad_lease["version"],
                         {"case_id": "case-lease"}, now=T0 + LEASE + 1, lease_seconds=1900)
        reversed_red = False          # 1900 秒租约下 1801 秒不该释放
    except R.LedgerConflict:
        reversed_red = True
    cases = [
        ("正样本：边界 / 草稿 / 乐观锁 全绿", lambda: not base),
        ("★ L1 反向对照：把租约改成 1900 秒，1801 秒时不许释放",
         lambda: reversed_red is True),
        ("L3 反向对照：带正确 version 的写入必须成功（不是恒拒）",
         lambda: _second_write_ok(R)),
    ]
    bad = 0
    print("=" * 78)
    print("行 136 · 到期释放 / 草稿交接 / 乐观锁（内存样本，不写盘）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def _second_write_ok(R) -> bool:
    st = claimed(R)
    st2, _ev, _r = R.reduce_command(st, "save_draft", "alice", st["version"],
                                    {"case_id": "case-lease", "notes": "A"},
                                    now=T0 + 10, lease_seconds=LEASE)
    st3, _ev, _r = R.reduce_command(st2, "save_draft", "alice", st2["version"],
                                    {"case_id": "case-lease", "notes": "B"},
                                    now=T0 + 20, lease_seconds=LEASE)
    return st3["version"] > st2["version"]


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        try:
            return controls()
        except Untested as e:
            print(f"⚠️ 未测：{e}")
            return 2
    try:
        R = _mod()
        problems = assess(R)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 136 · 到期释放（29 分钟独占 / 30 分 01 秒释放）")
    print("=" * 78)
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：29 分钟仍独占、30 分 01 秒释放；释放前草稿在、新领取人看得到；陈旧 version 被拒。")
    print("   ⚠️ 只覆盖 reducer 一侧；ledger 的边界是 `now >= lease_expires`（与 reducer 的 `>` 差一秒），")
    print("      这是已知差异，行 136 未要求两者一致，本脚本不替代裁定。")
    print("   ⚠️ 通知那半没有对象（生产无通知生产者），未断言、未映射。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
