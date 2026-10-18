#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_disposition_router.py —— `base/disposition_router.py` 的判据（T1-10）

## 它验什么

  A **五档路由**：BLOCK→DP2（可终结裁定但不可放行）、REVIEW→DP3/DP4、
    未审查→DP0、待自决→DP1、PASS→DP1；五档 release_status 全部「待放行」。
  B **不重算**：输出 state/layer 必须等于输入；obligations 原样透传，
    不许增删改（含自定义义务）。
  C **补齐字段**：owner / finalizer / can_finalize / release_status /
    appeal_channel / due_at 都有值；案件号 = receipt_id，申诉通道含案件号。
  D **一致性守卫**：state 与 layer 不匹配 → 拒；冲突样本（any_authority_conflict /
    rule_conflict / max_sev_authority=conflict）落 DP3 → 拒；未知 control_code → 拒。
  E **静态扫描**：源码里 `release_status` 只允许常量「待放行」；不存在
    标签→发布状态/已放行的直连映射。
  F **反向对照**：输入带「已放行」也必须被覆盖回「待放行」；ERROR 输入拒路由。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）
"""
from __future__ import annotations

import ast
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from disposition_router import DispositionRouter
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/disposition_router.py 失败：%s" % e)
    sys.exit(1)

FIVE = ["BLOCK", "REVIEW", "未审查", "待自决", "PASS"]


def dec(state="BLOCK", layer="DP2", obligations=None, **over):
    d = {
        "run_state": "OK",
        "state": state,
        "layer": layer,
        "obligations": [] if obligations is None else obligations,
        "max_sev": "none",
        "max_sev_authority": "n/a",
        "any_authority_conflict": False,
        "rule_conflict": False,
    }
    d.update(over)
    return d


def main():
    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    router = DispositionRouter()
    RECEIPT = "rcpt_20261019_0001"

    # ── A 五档路由 ──────────────────────────────────────────────────
    cases = [
        ("A1 BLOCK→DP2", dec("BLOCK", "DP2"), "DP2", "机器"),
        ("A2 REVIEW→DP3", dec("REVIEW", "DP3"), "DP3", "审核员"),
        ("A3 REVIEW→DP4", dec("REVIEW", "DP4", any_authority_conflict=True), "DP4", "法务"),
        ("A4 未审查→DP0", dec("未审查", "DP0"), "DP0", "投放"),
        ("A5 待自决→DP1", dec("待自决", "DP1"), "DP1", "文案"),
        ("A6 PASS→DP1", dec("PASS", "DP1"), "DP1", "文案"),
    ]
    for cid, d, layer, owner_kw in cases:
        try:
            r = router.route(d, RECEIPT, now="2026-10-19T02:00:00Z")
        except Exception as e:  # noqa: BLE001
            # 缺 owner 等回归必须落成红断言，而不是让验证器自己崩掉
            r = {"error": "%s: %s" % (type(e).__name__, e)}
        T("%s：state/layer 原样" % cid,
          r.get("state") == d["state"] and r.get("layer") == layer == d["layer"], str(r))
        T("%s：owner 非空且匹配层角色" % cid,
          isinstance(r.get("owner"), str) and owner_kw in r["owner"], str(r.get("owner")))
        T("%s：finalizer 非空且 can_finalize=true" % cid,
          isinstance(r.get("finalizer"), str) and r["finalizer"] and r.get("can_finalize") is True, str(r))
        T("%s：release_status=待放行" % cid, r.get("release_status") == "待放行", str(r.get("release_status")))
        T("%s：case_id=receipt_id" % cid,
          r.get("case_id") == RECEIPT and r.get("receipt_id") == RECEIPT, str(r))
        T("%s：appeal_channel 含案件号" % cid,
          isinstance(r.get("appeal_channel"), str) and RECEIPT in r["appeal_channel"], str(r.get("appeal_channel")))
        T("%s：due_at 是 ISO-Z" % cid,
          isinstance(r.get("due_at"), str) and r["due_at"].endswith("Z") and "T" in r["due_at"], str(r.get("due_at")))

    # ── B 不重算 state/layer、不重生成 obligations ──────────────────
    obs = ["pending_candidate", "partial_coverage", "evidence_gap", "自定义义务"]
    d_b = dec("BLOCK", "DP2", obligations=list(obs))
    r_b = router.route(d_b, RECEIPT, now="2026-10-19T02:00:00Z")
    T("B1 BLOCK 的 obligations 原样透传（顺序/内容一致）",
      r_b.get("obligations") == obs, str(r_b.get("obligations")))
    T("B2 不新增义务（长度相同）", len(r_b.get("obligations", [])) == len(obs), str(r_b.get("obligations")))
    r_b2 = router.route(dec("REVIEW", "DP4", any_authority_conflict=True), RECEIPT)
    T("B3 REVIEW/DP4 原样保留（不被重算成 DP3）", r_b2.get("layer") == "DP4", str(r_b2.get("layer")))
    r_b3 = router.route(dec("未审查", "DP0"), RECEIPT)
    T("B4 未审查/DP0 原样保留", r_b3.get("layer") == "DP0", str(r_b3.get("layer")))

    # ── C 补齐字段 ──────────────────────────────────────────────────
    for k in ("owner", "finalizer", "can_finalize", "release_status",
              "appeal_channel", "due_at", "case_id"):
        T("C1 输出字段 %s 存在且非空" % k,
          k in r_b and r_b[k] not in (None, ""), str(r_b.get(k)))
    T("C2 五档 release_status 全部待放行",
      all(router.route(d, RECEIPT)["release_status"] == "待放行" for _, d, _, _ in cases), "")

    # ── D 一致性守卫 ────────────────────────────────────────────────
    def must_raise(cid, fn):
        try:
            fn()
            T(cid, False, "未拒")
        except Exception:  # noqa: BLE001
            T(cid, True, "")

    must_raise("D1 BLOCK 落 DP3 → 拒", lambda: router.route(dec("BLOCK", "DP3"), RECEIPT))
    must_raise("D2 未审查落 DP2 → 拒", lambda: router.route(dec("未审查", "DP2"), RECEIPT))
    must_raise("D3 PASS 落 DP2 → 拒", lambda: router.route(dec("PASS", "DP2"), RECEIPT))
    must_raise("D4 DP4 冲突样本落 DP3 → 拒",
               lambda: router.route(dec("REVIEW", "DP3", any_authority_conflict=True), RECEIPT))
    must_raise("D4b rule_conflict 样本落 DP3 → 拒",
               lambda: router.route(dec("REVIEW", "DP3", rule_conflict=True), RECEIPT))
    must_raise("D4c max_sev_authority=conflict 落 DP3 → 拒",
               lambda: router.route(dec("REVIEW", "DP3", max_sev_authority="conflict"), RECEIPT))
    r_conf = router.route(dec("REVIEW", "DP4", any_authority_conflict=True), RECEIPT)
    T("D4d 冲突样本落 DP4 → 通过", r_conf.get("layer") == "DP4", str(r_conf.get("layer")))
    must_raise("D5 未知 control_code → 拒",
               lambda: router.route(dec("BLOCK", "DP2"), RECEIPT, control_code="ZZZ"))
    r_h01 = router.route(dec("BLOCK", "DP2"), RECEIPT, control_code="H01")
    T("D6 已知 control_code 不改变输入 layer（H01 仍 DP2）",
      r_h01.get("layer") == "DP2", str(r_h01.get("layer")))

    # ── E 静态扫描：唯一释放状态、无直连发布映射 ────────────────────
    src = open(os.path.join(ROOT, "base", "disposition_router.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    release_consts = []
    label_maps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    if k.value == "release_status":
                        release_consts.append(v.value)
                    if k.value in FIVE and isinstance(v.value, str) and not v.value.startswith("DP"):
                        label_maps.append((k.value, v.value))
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) \
                        and t.slice.value == "release_status" and isinstance(node.value, ast.Constant):
                    release_consts.append(node.value.value)
    T("E1 源码里 release_status 只允许常量「待放行」",
      release_consts != [] and all(x == "待放行" for x in release_consts), str(release_consts))
    T("E2 不存在标签→发布状态/已放行的直连映射",
      label_maps == [], str(label_maps))
    T("E3 源码不出现「已放行」/published 释放路径字面量",
      ("已放行" not in src) and ("published" not in src.lower()), "")

    # ── F 反向对照：输入说已放行也必须被覆盖 ────────────────────────
    r_f = router.route(dec("BLOCK", "DP2", release_status="已放行"), RECEIPT)
    T("F1 输入 release_status=已放行 → 输出仍是待放行",
      r_f.get("release_status") == "待放行", str(r_f.get("release_status")))
    must_raise("F2 run_state=ERROR → 拒路由",
               lambda: router.route(dict(dec("BLOCK", "DP2"), run_state="ERROR"), RECEIPT))
    must_raise("F3 空 receipt_id → 拒", lambda: router.route(dec("BLOCK", "DP2"), ""))
    must_raise("F4 未知 state → 拒", lambda: router.route(dec("ALLOW", "DP2"), RECEIPT))
    must_raise("F5 未知 layer → 拒", lambda: router.route(dec("BLOCK", "DP9"), RECEIPT))

    # ── G due_at：按工作日计算且可注入 ──────────────────────────────
    r_g1 = router.route(dec("BLOCK", "DP2"), RECEIPT, now="2026-10-19T02:00:00Z")
    T("G1 周一 +2 工作日 = 周三", r_g1.get("due_at") == "2026-10-21T02:00:00Z", str(r_g1.get("due_at")))
    r_g2 = router.route(dec("BLOCK", "DP2"), RECEIPT, now="2026-10-24T09:30:00Z")
    T("G2 周六 +2 工作日 = 下周二（跳过周日）",
      r_g2.get("due_at") == "2026-10-27T09:30:00Z", str(r_g2.get("due_at")))
    T("G3 同一输入两次 due_at 相同（确定性）",
      router.route(dec("BLOCK", "DP2"), RECEIPT, now="2026-10-19T02:00:00Z")["due_at"]
      == r_g1["due_at"], "")

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_disposition_router %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
