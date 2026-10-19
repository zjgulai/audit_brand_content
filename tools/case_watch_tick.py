#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/case_watch_tick.py —— case_watch 的执行点（C-51 集成）

**它是什么**：一次「跑一轮 case_watch」的命令行入口。
**它不是什么**：它不调度自己。没有任何 while / sleep / 定时器。

--------------------------------------------------------------------------
★ 调度接入留给阶段 4（Compose scheduler）

    本脚本就是那个调度器的**执行点**：scheduler 每次触发时调一次

        python3 tools/case_watch_tick.py --cases <导出.json> --apply

    在这之前，它可以被 manual 调用、也可以被任何外部定时器（launchd / cron）
    调 —— 但**没有任何东西会替它决定多久跑一次**。
    原因：把周期写死在这里，等于让「多久扫一次」变成一个
    没人能改、也没人知道它在哪里的常量。
    （`base/case_watch.py` 的 8a 断言也钉着「扫描器不自己定时」。）

--------------------------------------------------------------------------
★ 默认 dry-run —— 这条不是谨慎，是**两个不同的动作**

    dry-run  只说「如果现在跑，会升级谁」：不发通知、不写台账、不动任何东西
    --apply  真升级：发通知 + 写台账

    默认 dry-run 的理由与 §2.4.4 同源：**试跑绝不许有副作用**。
    一段「看看会发生什么」的命令如果顺手写掉了台账，
    那么真到期那天反而会被去重挡住 —— 一次查看改掉了将来要发生的事。

--------------------------------------------------------------------------
★ 退出码（这四种必须彼此不同，否则「没事」和「没测到」分不开）

    0  全部 not_due，或 dry-run 下有 due          —— 正常，且没有任何未测
    1  --apply 过程中失败（异常 / 写盘失败）        —— 红
    2  有 untested                                  —— **未测**
    3  参数或输入读不出（文件坏、JSON 坏、now 坏）  —— 没跑起来，也是未测

    ★ 2 与 0 必须分开：一条永远判不出来的案件会被记成 untested。
      如果它对 0，看板上就是「一切正常」，而那条案件**永远不会升级**。

用法
----
    # 只看会发生什么（默认）
    python3 tools/case_watch_tick.py --cases cases.json --now 2026-10-21T09:00:00+08:00

    # 真升级（必须给收件人；不给会全部记成未测并退 2）
    python3 tools/case_watch_tick.py --cases cases.json --now ... --apply \\
        --escalation-recipients u_coord,u_lead \\
        --ledger PMO/shouheng-state/case-watch-ledger.json \\
        --dedup  PMO/shouheng-state/case-watch-dedup.json

    # 自证
    python3 tools/case_watch_tick.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import case_watch as W
    from base import notifications as N
except Exception as e:  # noqa: BLE001
    print(f"⚠ 未测：import 失败（{type(e).__name__}: {e}）", file=sys.stderr)
    sys.exit(3)

# 退出码。**这四个不许合并** —— 见文件头。
RC_OK = 0
RC_FAILED = 1
RC_UNTESTED = 2
RC_BAD_INPUT = 3


def _load_cases(path: str) -> list:
    """
    读案件导出文件。

    接受两种形状，因为导出工具通常是直接 `json.dump(list)`：
      · 顶层就是数组                → 原样用
      · 顶层是 {"cases": [...]}     → 取里面那个

    ★ 读不出就退 3，**不返回空列表**：空列表会让下游报「0 条案件、全部正常」，
      而真相是「我根本没读到」。这正是 K-02 那个形状。
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"读不出案件文件 {path!r}：{type(e).__name__}: {e}") from e
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"案件文件不是合法 JSON：{e}") from e

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data["cases"]
    raise ValueError(
        "案件文件顶层必须是数组，或含 `cases` 数组的对象；"
        f"实际是 {type(data).__name__}")


def _print_report(result: dict, *, applied: bool) -> None:
    mode = "apply" if applied else "dry-run"
    cal = result.get("calendar_coverage")
    hol = result.get("holidays_configured")

    print("=" * 74)
    print(f"case_watch tick（{mode}）")
    print("=" * 74)
    print(f"  日历口径：{cal}"
          + ("（未配置节假日 —— 只跳周末）" if hol is False else ""))
    print(f"  到期 {len(result.get('due', []))} · "
          f"未到期 {len(result.get('not_due', []))} · "
          f"跳过 {len(result.get('skipped', []))} · "
          f"未测 {len(result.get('untested_items', []))} · "
          f"已升级过 {len(result.get('already_escalated', []))}")
    print()

    for d in result.get("due", []):
        tag = "（dry-run，未动手）" if d.get("dry_run") else "→ 已升级"
        print(f"  ⏰ {d.get('case_id')}  到期 {d.get('due_at')}  "
              f"超期 {d.get('overdue_workdays')} 工作日  {tag}")
        print(f"       来源：{d.get('due_source')} · "
              f"升级到：{d.get('escalation_role')} "
              f"{d.get('recipients') or ''}")

    for d in result.get("already_escalated", []):
        print(f"  ↺ {d.get('case_id')}  本次到期事件已经升级过，不重复通知")

    for d in result.get("untested_items", []):
        print(f"  ⚠ {d.get('case_id')}  未测：{d.get('reason')}")

    for d in result.get("skipped", []):
        print(f"  – {d.get('case_id')}  跳过：{d.get('reason')}")
    print()


def run(*, cases_path: str, now: str, apply: bool, ledger_path=None,
        dedup_path=None, threshold_days=W.DEFAULT_THRESHOLD_DAYS,
        escalation_role=W.DEFAULT_ESCALATION_ROLE,
        escalation_recipients=None) -> int:
    """跑一轮。返回退出码。"""
    try:
        cases = _load_cases(cases_path)
    except ValueError as e:
        print(f"⚠ 未测：{e}", file=sys.stderr)
        return RC_BAD_INPUT

    # now 必须先验 —— 读不出就别往下走，否则 scan 会抛
    if W.parse_ts(now) is None:
        print(f"⚠ 未测：--now 读不出时间（{now!r}）", file=sys.stderr)
        return RC_BAD_INPUT

    if apply:
        ledger = W.EscalationLedger(ledger_path) if ledger_path else W.EscalationLedger()
        dedup = N.DedupLedger(dedup_path) if dedup_path else N.DedupLedger()
        outbox = N.NotificationOutbox(dedup=dedup)
    else:
        # ★ dry-run：outbox=None 就是 scan 的 dry-run 分支。
        #   台账照建但**不落盘**（path=None 时 _save 直接返回）——
        #   这样「只看一眼」在盘上一个字节都不写。
        ledger = W.EscalationLedger()
        outbox = None

    try:
        result = W.scan(cases, now, threshold_days=threshold_days,
                        escalation_role=escalation_role,
                        escalation_recipients=escalation_recipients,
                        ledger=ledger, outbox=outbox)
    except W.CaseWatchError as e:
        print(f"⚠ 未测：{e.code}: {e.detail}", file=sys.stderr)
        return RC_BAD_INPUT
    except Exception as e:  # noqa: BLE001
        print(f"✗ 失败：{type(e).__name__}: {e}", file=sys.stderr)
        return RC_FAILED

    _print_report(result, applied=apply)

    # ★ 未测优先于一切：有未测就退 2，哪怕同时也有 due。
    #   「有东西到期了」与「有东西我判不出来」是两件事，
    #   合并成一个退出码会让后者永远被前者盖住。
    if result.get("untested"):
        print(f"⚠ 未测 {len(result.get('untested_items', []))} 条 —— 这些案件"
              f"既不算到期，也不算正常", file=sys.stderr)
        return RC_UNTESTED

    if apply and result.get("untested"):
        return RC_FAILED

    print(f"✅ 正常：全部 {len(result.get('not_due', []))} 条未到期，无未测"
          if not result.get("due") else
          f"✅ 正常：{len(result.get('due', []))} 条已处理，无未测")
    return RC_OK


# ═══════════════════════ 自证 ═══════════════════════

def self_test() -> int:
    """
    自证：dry-run 不许写盘、apply 必须写。

    ★ 这条自证的形状来自 §2.4.4：**跑一次自检，不许改掉它要保护的东西。**
      所以它在临时目录里跑，跑完把两个文件读回来比对。
    """
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def case(cid, **kw):
        base = {"case_id": cid, "status": "in_progress",
                "release_status": "待放行",
                "transferred_at": "2026-10-19T09:00:00+08:00"}   # 周一
        base.update(kw)
        return base

    with tempfile.TemporaryDirectory() as d:
        cases_path = Path(d) / "cases.json"
        ledger_path = Path(d) / "ledger.json"
        dedup_path = Path(d) / "dedup.json"
        cases_path.write_text(json.dumps([
            case("c-due"),                                    # 周三到期 → due
            case("c-fresh", transferred_at="2026-10-21T09:00:00+08:00"),  # 未到期
        ], ensure_ascii=False), encoding="utf-8")

        # ── ① dry-run：一个字节都不许落 ──
        rc = run(cases_path=str(cases_path), now="2026-10-21T09:00:00+08:00",
                 apply=False, ledger_path=str(ledger_path), dedup_path=str(dedup_path))
        ok("S1 dry-run 退出码 0（有 due 但对 dry-run 而言是正常）", rc == RC_OK, f"rc={rc}")
        ok("S2 ★ dry-run 后台账文件不存在", not ledger_path.exists(), "")
        ok("S3 ★ dry-run 后去重账本不存在", not dedup_path.exists(), "")

        # ── ② apply 但**不给收件人**：必须退 2，且不许写台账 ──
        #
        # ★ 这一条是自证跑挂之后补上的：apply 不给 esc recipients 时，
        #   scan 会给每条到期记「解析不出收件人」的未测。
        #   如果它退 0 或写了台账，就是「假装升级成功」—— 那才是要防的。
        rc = run(cases_path=str(cases_path), now="2026-10-21T09:00:00+08:00",
                 apply=True, ledger_path=str(ledger_path), dedup_path=str(dedup_path))
        ok("S4 ★ apply 但不给收件人 → 退 2（不许假装升级成功）",
           rc == RC_UNTESTED, f"rc={rc}")
        ok("S5 ★ 这种情况下台账文件不许出现", not ledger_path.exists(), "")

        # ── ③ apply 给了收件人：必须写 ──
        rc = run(cases_path=str(cases_path), now="2026-10-21T09:00:00+08:00",
                 apply=True, ledger_path=str(ledger_path), dedup_path=str(dedup_path),
                 escalation_recipients=["u_coord"])
        ok("S6 apply（给了收件人）退出码 0", rc == RC_OK, f"rc={rc}")
        ok("S7 ★ apply 后台账文件存在", ledger_path.exists(), "")
        ok("S8 ★ apply 后台账里有一条 c-due 的升级",
           ledger_path.exists()
           and any(e.get("case_id") == "c-due"
                   for e in json.loads(ledger_path.read_text(encoding="utf-8"))), "")
        ok("S9 ★ apply 后去重账本记下了事件",
           dedup_path.exists()
           and bool(json.loads(dedup_path.read_text(encoding="utf-8")).get("events")), "")

        # ── ④ 再 apply 一次：去重生效，不再产生第二条 ──
        before = len(json.loads(ledger_path.read_text(encoding="utf-8")))
        rc = run(cases_path=str(cases_path), now="2026-10-21T09:05:00+08:00",
                 apply=True, ledger_path=str(ledger_path), dedup_path=str(dedup_path),
                 escalation_recipients=["u_coord"])
        after = len(json.loads(ledger_path.read_text(encoding="utf-8"))) if ledger_path.exists() else -1
        ok("S10 ★ 第二次 apply 不新增台账事件（去重生效）",
           rc == RC_OK and after == before, f"before={before} after={after} rc={rc}")

        # ── ④ 读不出的案件文件 → 退 3，不是「0 条、全部正常」──
        bad = Path(d) / "bad.json"
        bad.write_text("{不是 json", encoding="utf-8")
        rc = run(cases_path=str(bad), now="2026-10-21T09:00:00+08:00", apply=False)
        ok("S11 ★ 案件文件坏 → 退 3（不是 0）", rc == RC_BAD_INPUT, f"rc={rc}")

        missing = Path(d) / "nope.json"
        rc = run(cases_path=str(missing), now="2026-10-21T09:00:00+08:00", apply=False)
        ok("S12 ★ 文件不存在 → 退 3", rc == RC_BAD_INPUT, f"rc={rc}")

        empty = Path(d) / "empty.json"
        empty.write_text("[]", encoding="utf-8")
        rc = run(cases_path=str(empty), now="2026-10-21T09:00:00+08:00", apply=False)
        ok("S13 空数组 → 退 0（真的是 0 条，与读不出不同）", rc == RC_OK, f"rc={rc}")

        # ── ⑤ 有 untested → 退 2，哪怕同时有 due ──
        blind = Path(d) / "blind.json"
        blind.write_text(json.dumps([
            case("c-due"),
            {"case_id": "c-blind", "status": "in_progress",
             "release_status": "待放行"},     # 没有 transferred_at / due_at
        ], ensure_ascii=False), encoding="utf-8")
        rc = run(cases_path=str(blind), now="2026-10-21T09:00:00+08:00", apply=False)
        ok("S14 ★ 有未测 → 退 2（哪怕也有 due）", rc == RC_UNTESTED, f"rc={rc}")

        # ── ⑥ --now 读不出 → 退 3 ──
        rc = run(cases_path=str(cases_path), now="不是时间", apply=False)
        ok("S15 ★ --now 读不出 → 退 3", rc == RC_BAD_INPUT, f"rc={rc}")

        # ── ⑦ 顶层 {"cases": [...]} 也认 ──
        wrapped = Path(d) / "wrapped.json"
        wrapped.write_text(json.dumps({"cases": [case("c-w")]}, ensure_ascii=False),
                           encoding="utf-8")
        rc = run(cases_path=str(wrapped), now="2026-10-21T09:00:00+08:00", apply=False)
        ok("S16 顶层 {cases:[...]} 也读得来", rc == RC_OK, f"rc={rc}")

    # ── ⑧ 默认必须是 dry-run（CLI 层）──
    ap = build_parser()
    ns = ap.parse_args(["--cases", "x.json"])
    ok("S17 ★ CLI 默认是 dry-run（不给 --apply 不写盘）",
       getattr(ns, "apply", None) is False, f"apply={getattr(ns, 'apply', None)}")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 74)
    print("case_watch_tick 自证")
    print("=" * 74)
    for name, p, detail in results:
        print(f"  {'✓' if p else '✗'} {name:<50} {detail}")
    print()
    if passed == total:
        print(f"✅ {passed}/{total} 项全过")
        return RC_OK
    print(f"✗ {passed}/{total} 项通过；红项：{[n for n, p, _ in results if not p]}",
          file=sys.stderr)
    return RC_FAILED


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="case_watch 执行点：跑一轮超时扫描（默认 dry-run）")
    ap.add_argument("--cases", help="案件导出 JSON（数组，或 {cases:[...]}）")
    ap.add_argument("--now", help="当前时刻（ISO 8601）；必须显式给")
    ap.add_argument("--apply", action="store_true", default=False,
                    help="真升级（写台账 + 发通知）。不给就是 dry-run")
    ap.add_argument("--ledger", default=None, help="升级台账路径（apply 时用）")
    ap.add_argument("--dedup", default=None, help="去重账本路径（apply 时用）")
    ap.add_argument("--threshold-days", type=int,
                    default=W.DEFAULT_THRESHOLD_DAYS,
                    help=f"阈值工作日数，默认 {W.DEFAULT_THRESHOLD_DAYS}（D-039）")
    ap.add_argument("--escalation-role", default=W.DEFAULT_ESCALATION_ROLE,
                    help=f"升级目标角色，默认 {W.DEFAULT_ESCALATION_ROLE}")
    ap.add_argument("--escalation-recipients", default=None,
                    help="升级接收人，逗号分隔（如 u_coord,u_lead）。"
                         "**不给且 --apply 时，每条到期都会被记成未测并退 2** —— "
                         "这不是 bug：解析不出收件人时不许假装升级成功")
    ap.add_argument("--self-test", action="store_true", default=False,
                    help="跑自证（用临时目录，不碰任何真实状态）")
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    ns = ap.parse_args(argv)

    if ns.self_test:
        return self_test()

    if not ns.cases or not ns.now:
        ap.print_usage(sys.stderr)
        print("⚠ 未测：--cases 与 --now 都是必填", file=sys.stderr)
        return RC_BAD_INPUT

    recipients = None
    if ns.escalation_recipients:
        recipients = [x.strip() for x in ns.escalation_recipients.split(",")
                      if x.strip()]
        if not recipients:
            print("⚠ 未测：--escalation-recipients 给了但是空的", file=sys.stderr)
            return RC_BAD_INPUT

    return run(cases_path=ns.cases, now=ns.now, apply=ns.apply,
               ledger_path=ns.ledger, dedup_path=ns.dedup,
               threshold_days=ns.threshold_days,
               escalation_role=ns.escalation_role,
               escalation_recipients=recipients)


if __name__ == "__main__":
    sys.exit(main())
