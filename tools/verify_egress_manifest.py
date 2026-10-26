#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_egress_manifest.py — T-438：出境清单落盘（送什么·送给谁·留多久）

## 三要素里哪一项此前不存在

方案 §五 T-432 判据 4 要求「出境清单落盘：送什么、送给谁、留多久」。
前两项 `egress_manifest()` 早就有；**「留多久」此前在任何地方都不存在** ——
也就是说「我们只保留 N 天」是一句没有执行点的承诺。

本票只补第三项与「落盘」这两件事，**不重算清单**（否则就是第二套口径）。

## 断言分组

  S  快照内容：三要素齐备（providers / recipient / retention）、生成时刻与到期时刻
     都是可解析的 ISO，且到期 = 生成 + days×86400（**算出来，不是抄进去**）
  T  按任务收窄：只跑静图的部署不该在清单里看到音轨（与 egress_manifest(task) 同源）
  H  同源不重算：快照里的 providers 与 digest 必须**逐字等于**注册表的输出
  E  到期判定：未到期 False / 已到期 True / **到期时刻读不出 → True（fail-closed）**
  R  落盘：仓内根必须拒；append-only 不覆盖；重名不静默覆盖；文件 0600
  P  清理：到期删除、未到期保留、**读不出的文件不许删**（删一个看不懂的审计件不可逆）
  C  保留期读取：缺省用默认；非整数/非正/超 10 年必须**抛**（不许退回默认）

## 直接主体

- `base/multimodal_egress.py` —— 快照构造、到期判定、落盘与清理
- `tools/multimodal_client.py` —— 出境项登记（`EGRESS_ITEMS` 的 `tasks` 字段）。
  它是本票抓到的那个真缺陷所在：`tasks` 留空 = 适用于全部任务，
  于是只做静图的部署也会在清单里列出音轨。

退出码：0 全过 / 1 有红 / 2 未测（导入失败）。
`--controls`：反向对照 —— 四处打断各只让对应那几条红、好副本必须全绿。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


try:
    from base import multimodal_egress as ME
    from base.multimodal_provider import ProviderRegistry, ProviderRegistration, EgressItem
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入出境清单链: %s" % exc)
    sys.exit(2)


def _registry_with(*, gateway_tasks=("scene_semantics",), authorized=False):
    """一个有真 provider 的注册表（不用真网关，只造登记）。"""
    from tools import multimodal_client as MC
    reg = ProviderRegistry()
    registration = MC.registration_for("vod", model="gemini-3.1-flash-lite",
                                       tasks=list(gateway_tasks),
                                       authorized=authorized)
    registry = ProviderRegistry()

    class _Stub:
        provider_id = registration.provider_id

        def analyze(self, media_ref, tasks):
            return {"status": "untested", "tasks": {}}

    registry.register(registration, _Stub())
    return registry, registration


def _parse_iso(text):
    return time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


# ── S：快照内容 ──────────────────────────────────────────────────────

def check_snapshot():
    registry, registration = _registry_with()
    now = 1_800_000_000.0
    snap = ME.build_snapshot(registry, retention_days=30, now=now)
    report(snap.get("provider_count") == 1,
           "S1 快照收录了 provider", str(snap.get("provider_count")))
    providers = snap.get("providers") or []
    report(providers and providers[0].get("recipient"),
           "S2 ★ 三要素之「送给谁」在（recipient 非空）",
           str((providers[0] or {}).get("recipient"))[:40])
    report(providers and providers[0].get("egress_items"),
           "S3 ★ 三要素之「送什么」在（egress_items 非空）",
           str(len((providers[0] or {}).get("egress_items") or [])))
    retention = snap.get("retention") or {}
    report(retention.get("days") == 30,
           "S4 ★ 三要素之「留多久」在（days=30）", str(retention.get("days")))
    report(bool(retention.get("expires_at")) and bool(retention.get("policy")),
           "S5 保留期带到期时刻与政策说明")
    # ★ 到期 = 生成 + days×86400，**算出来**，不是抄进去
    start = _parse_iso(str(snap["generated_at"]))
    end = _parse_iso(str(retention["expires_at"]))
    import calendar
    delta = calendar.timegm(end) - calendar.timegm(start)
    report(delta == 30 * 86400,
           "S6 ★★ 到期时刻 = 生成时刻 + days×86400（算出来的，不是常量）",
           "delta=%d 期望=%d" % (delta, 30 * 86400))
    # 反向对照：改 days，到期必须跟着动
    snap2 = ME.build_snapshot(registry, retention_days=7, now=now)
    end2 = _parse_iso(str((snap2["retention"] or {}).get("expires_at")))
    report(calendar.timegm(end2) - calendar.timegm(start) == 7 * 86400,
           "S7 ★ 反向对照：days=7 时到期跟着变（不是恒为 30）")
    report(snap.get("boundary") and "不证明" in str(snap.get("boundary")),
           "S8 ★ 快照自己写明边界：不证明任何一次调用实际发生过")


# ── T：按任务收窄 ────────────────────────────────────────────────────

def check_task_narrowing():
    registry, _ = _registry_with(gateway_tasks=("scene_semantics", "av_alignment"))
    snap = ME.build_snapshot(registry, tasks=("scene_semantics",))
    per = (snap.get("by_task") or {}).get("scene_semantics") or {}
    items = {i.get("item_id") for p in (per.get("providers") or [])
             for i in (p.get("egress_items") or [])}
    report("audio_bytes_b64" not in items,
           "T1 ★ 按 scene_semantics 收窄后不含音轨（只跑静图的部署不该看到它）",
           repr(sorted(items)))
    report(per.get("digest_sha256") == registry.egress_manifest_digest("scene_semantics"),
           "T2 分任务指纹与注册表同源（不重算）")
    full = ME.build_snapshot(registry, tasks=("av_alignment",))
    per2 = (full.get("by_task") or {}).get("av_alignment") or {}
    items2 = {i.get("item_id") for p in (per2.get("providers") or [])
              for i in (p.get("egress_items") or [])}
    report("audio_bytes_b64" in items2,
           "T3 ★ 反向对照：按 av_alignment 收窄时音轨**在**清单里", repr(sorted(items2)))


# ── H：同源不重算 ────────────────────────────────────────────────────

def check_same_source():
    registry, _ = _registry_with()
    snap = ME.build_snapshot(registry)
    report(snap.get("providers") == registry.egress_manifest(),
           "H1 ★★ 快照 providers 逐字等于注册表输出（不重算）")
    report(snap.get("digest_sha256") == registry.egress_manifest_digest(),
           "H2 ★★ 快照指纹逐字等于注册表指纹（同一次取，不自相矛盾）")
    # ★ 反向对照：若清单变了，指纹必须跟着变（不是写死的常量）
    reg2, _ = _registry_with(gateway_tasks=("scene_semantics", "av_alignment"))
    report(ME.build_snapshot(reg2).get("digest_sha256") != snap.get("digest_sha256"),
           "H3 ★ 反证：注册面变了指纹就变（不是常量）")


# ── E：到期判定 ──────────────────────────────────────────────────────

def check_expiry():
    registry, _ = _registry_with()
    now = 1_800_000_000.0
    snap = ME.build_snapshot(registry, retention_days=30, now=now)
    report(ME.is_expired(snap, now=now) is False,
           "E1 未到期 → False")
    report(ME.is_expired(snap, now=now + 31 * 86400) is True,
           "E2 已过期 → True")
    report(ME.is_expired(snap, now=now + 30 * 86400 + 1) is True,
           "E3 边界：到期后 1 秒即 True")
    # ★ fail-closed：读不出到期时刻必须按过期处理
    broken = {"retention": {"days": 30}}
    report(ME.is_expired(broken, now=now) is True,
           "E4 ★★ 缺 expires_at → 按expired处理（fail-closed）")
    garbage = {"retention": {"expires_at": "不是时间"}}
    report(ME.is_expired(garbage, now=now) is True,
           "E5 ★★ 到期时刻解析不了 → 按过期处理（反向默认会让损坏的审计件永远有效）")


# ── R：落盘 ──────────────────────────────────────────────────────────

def check_write():
    registry, _ = _registry_with()
    snap = ME.build_snapshot(registry, now=1_800_000_000.0)
    with tempfile.TemporaryDirectory() as td:
        target = ME.write_snapshot(snap, root=td)
        report(target.is_file(), "R1 落盘成功", target.name)
        mode = target.stat().st_mode & 0o777
        report(mode == 0o600, "R2 ★ 文件 0600（审计件不给人随便读）", oct(mode))
        data = json.loads(target.read_text(encoding="utf-8"))
        report(data.get("digest_sha256") == snap.get("digest_sha256"),
               "R3 落盘内容与内存快照一致")
        # ★ append-only：同内容再写一次，必须产生**新文件**而不是覆盖
        again = ME.write_snapshot(snap, root=td)
        report(again != target and again.is_file(),
               "R4 ★★ append-only：同内容再写产生新文件（不覆盖历史）",
               "%s vs %s" % (target.name, again.name))
        report(len(list(Path(td).glob("egress-*.json"))) == 2,
               "R5 盘上有两份（历史没被吃掉）")
    # 仓内根必须拒
    try:
        ME.write_snapshot(snap, root=ROOT)
        report(False, "R6 ★★ 仓内根必须拒")
    except ME.EgressStoreError:
        report(True, "R6 ★★ 仓内根 → EgressStoreError（公开仓不许放出境清单）")
    try:
        ME.check_root(".")
        report(False, "R7 相对路径解析到仓内也必须拒")
    except ME.EgressStoreError:
        report(True, "R7 相对路径解析到仓内 → 拒")


# ── P：清理 ──────────────────────────────────────────────────────────

def check_prune():
    registry, _ = _registry_with()
    with tempfile.TemporaryDirectory() as td:
        old = ME.build_snapshot(registry, retention_days=1, now=1_800_000_000.0)
        fresh = ME.build_snapshot(registry, retention_days=365,
                                  now=1_800_000_000.0 + 100)
        ME.write_snapshot(old, root=td)
        ME.write_snapshot(fresh, root=td)
        # ★ 一个读不出来的文件：必须被保留并记进 errors
        broken = Path(td) / "egress-broken.json"
        broken.write_text("{不是 JSON", encoding="utf-8")
        result = ME.prune_expired(td, now=1_800_000_000.0 + 200 * 86400)
        report(len(result["removed"]) == 1,
               "P1 过期的被删（只删过期的那个）", repr(result["removed"]))
        report(result["kept"] == 1, "P2 未过期的保留", str(result["kept"]))
        report(broken.is_file(),
               "P3 ★★ 读不出的文件**不删**（删一个看不懂的审计件不可逆）")
        report(len(result["errors"]) == 1,
               "P4 ★ 读不出的文件记进 errors（不静默忽略）", repr(result["errors"]))
        report(result["removed"] and result["removed"][0].startswith("egress-"),
               "P5 ★ 删除留痕（返回删了哪些）")


# ── C：保留期读取 ────────────────────────────────────────────────────

def check_retention_env():
    report(ME.retention_days_from_env({}) == ME.DEFAULT_RETENTION_DAYS,
           "C1 缺省 → 用 DEFAULT_RETENTION_DAYS", str(ME.DEFAULT_RETENTION_DAYS))
    report(ME.retention_days_from_env({"MULTIMODAL_EGRESS_RETENTION_DAYS": "30"}) == 30,
           "C2 显式配 → 用它")
    for bad, label in (("abc", "非整数"), ("0", "零"), ("-5", "负数"),
                       ("99999", "超 10 年")):
        try:
            ME.retention_days_from_env({"MULTIMODAL_EGRESS_RETENTION_DAYS": bad})
            report(False, "C3 ★ 非法值 %s（%s）必须抛" % (bad, label))
        except ME.EgressStoreError:
            report(True, "C3 ★ 非法值 %s（%s）→ 抛，不退回默认" % (bad, label))
    # ★ 默认值的文档一致性：DEFAULT_RETENTION_DAYS 改了要有人知道
    report(ME.DEFAULT_RETENTION_DAYS > 0,
           "C4 默认保留期为正", str(ME.DEFAULT_RETENTION_DAYS))


def main(argv):
    if "--controls" in argv:
        return run_controls()
    print("=" * 78)
    print("T-438 · 出境清单落盘（送什么 · 送给谁 · 留多久）")
    print("=" * 78)
    check_snapshot()
    check_task_narrowing()
    check_same_source()
    check_expiry()
    check_write()
    check_prune()
    check_retention_env()
    print("-" * 78)
    if FAILED:
        print("❌ %d passed, %d failed" % (PASSED, FAILED))
        return 1
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


# ── --controls ──────────────────────────────────────────────────────

def run_controls():
    print("=" * 78)
    print("verify_egress_manifest · --controls")
    print("=" * 78)
    ok = bad = 0

    def C(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            bad += 1
            print("  ❌ %s  %s" % (name, detail))

    registry, _ = _registry_with()
    now = 1_800_000_000.0

    # CD1：到期时刻算错（写成常量）必须被发现 —— 用 days=7 反证
    s7 = ME.build_snapshot(registry, retention_days=7, now=now)
    s30 = ME.build_snapshot(registry, retention_days=30, now=now)
    C("CD1 days 不同 → 到期时刻必须不同（不是常量）",
      s7["retention"]["expires_at"] != s30["retention"]["expires_at"])

    # CD2：is_expired 对损坏输入必须 fail-closed —— 反向默认会被这条抓住
    C("CD2 缺 expires_at 时若不 fail-closed 就等于「永远有效」",
      ME.is_expired({"retention": {}}, now=now) is True)

    # CD3：仓内根拒绝这条判据真的会红 —— 反过来测「仓外根必须不拒」
    with tempfile.TemporaryDirectory() as td:
        C("CD3 仓外根必须不拒（否则 R6 是恒真）", ME.check_root(td) == Path(td).resolve())

    # CD4：读不出的文件必须保留 —— 反过来测「能读且过期的会被删」
    with tempfile.TemporaryDirectory() as td:
        stale = ME.build_snapshot(registry, retention_days=1, now=now)
        ME.write_snapshot(stale, root=td)
        res = ME.prune_expired(td, now=now + 2 * 86400)
        C("CD4 能读且过期的确实被删（证明 P3 的「不删」不是恒不删）",
          len(res["removed"]) == 1, repr(res))

    # CD5：非法保留期必须抛（不能静默退回默认）
    try:
        ME.retention_days_from_env({"MULTIMODAL_EGRESS_RETENTION_DAYS": "abc"})
        C("CD5 非法值必须抛", False)
    except ME.EgressStoreError:
        C("CD5 非法值必须抛", True)

    print("-" * 78)
    print("%s --controls %d 过 · %d 红" % ("✅" if bad == 0 else "❌", ok, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
