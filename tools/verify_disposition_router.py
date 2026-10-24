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
  A8（#49）**五层「谁接谁结」与规定值逐层恒等**：DP0 投放侧、DP1 文案提交人、
    DP2 机器（工具预审）、DP3 内容审核员、DP4 法务 —— 接与结同层同角色，
    规定值写在验证器里（不从生产 ROLE 常量读，否则常量改了断言跟着绿）。
  C4（#50）**主表 × routing 表全连接**：control-points-v1.json 的全部
    control_code 在 routing 表里各恰有一行 —— 丢一行、一对多都红。
    （P1 只对「表里有的行」自洽，routing 删行时它跟着少查一条且全绿。）
  E4/E5（#53）**静态扫描扩到全部 release_status 生产点**：base/ + api/ 全量
    AST 扫描 —— 常量值只允许五档结局（待放行/已放行/已拒绝/已撤回/已失效），
    人工门结局只许出现在 release_gate.py；标签直连映射任何文件都不许有。
  H（#68）**人工签发的记录必须含正确的签发人**：真实走一遍 release_gate.sign，
    记录 signer_id 与授权 principal.id 对拍（换 principal 记录必须跟着换）；
    机器 patch 写 release_status/status → 拒；人工签发后放行状态才变。
    （B 类断言只看「字段在场」，signer_id 写成常量 "system" 时全仓必须有一处红。）

## --controls（反向对照）

  好样本必须闭嘴、坏样本必须各自红（§2.4.1：没红过的断言不算验证过它）：
    C-1/C-2/C-3   五层角色判定器：真实路由闭嘴；DP4 finalizer=项目统筹红；DP3 owner=法务红
    C-4/C-5/C-6   全连接判定器：真实表闭嘴；routing 丢 H09 红；H01 两行（一对多）红
    C-7/C-8/C-9/C-10  release_status 扫描器：真实源码闭嘴；decision_table 写「放行」红；
                  release_gate 之外写「已放行」红；标签直连映射红
    C-11/C-12/C-13  签发人身份判定器：真实签发闭嘴；signer_id=system 红；signer_id=别人红

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）
"""
from __future__ import annotations

import ast
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from disposition_router import DispositionRouter
    from auth_session import SessionStore
    from release_gate import ReleaseGate, MachineWriteDenied
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/disposition_router.py / release_gate.py 失败：%s" % e)
    sys.exit(1)

FIVE = ["BLOCK", "REVIEW", "未审查", "待自决", "PASS"]

# ── #49：五层「谁接/谁结」的规定值（判据原文，不从生产 ROLE 常量读）────────
SPEC_ROLES = {
    "DP0": ("投放侧", "投放侧"),
    "DP1": ("文案提交人", "文案提交人"),
    "DP2": ("机器（工具预审）", "机器（工具预审）"),
    "DP3": ("内容审核员", "内容审核员"),
    "DP4": ("法务", "法务"),
}


def _role_mismatches(routed):
    """A8 判定器：routed = {layer: route() 输出}。五层 owner/finalizer 必须与
    判据规定的「谁接/谁结」逐层恒等；返回不匹配清单（空 = 通过）。"""
    bad = []
    for layer, want in SPEC_ROLES.items():
        r = routed.get(layer)
        got = (r.get("owner"), r.get("finalizer")) if isinstance(r, dict) else (None, None)
        if got != want:
            bad.append("%s: owner=%r/finalizer=%r, 规定 %r/%r"
                       % ((layer,) + got + want))
    return bad


# ── #50：主表 × routing 表全连接 ─────────────────────────────────────────
def _collect_codes(node, out=None):
    """递归收集主表里全部 control_code（主表结构变化时不漏）。"""
    if out is None:
        out = []
    if isinstance(node, dict):
        v = node.get("control_code")
        if isinstance(v, str) and v:
            out.append(v)
        for x in node.values():
            _collect_codes(x, out)
    elif isinstance(node, list):
        for x in node:
            _collect_codes(x, out)
    return out


def _load_cp_codes():
    """主表 control_code 清单；读不出返回 (None, 原因) —— 未测，不许当绿。"""
    p = os.path.join(ROOT, "research", "governance", "control-points-v1.json")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        return None, "control-points-v1.json 读不出（%s）" % e
    return _collect_codes(data), ""


def _routing_gaps(cp_codes, route_rows):
    """C4 判定器：主表 × routing 表全连接。
    missing = 主表有、routing 没有（#50 变异形状：routing 丢行）；
    dup = 一对多（同一 control_code 两行）。"""
    seen = []
    dup = set()
    for row in route_rows or []:
        code = row.get("control_code") if isinstance(row, dict) else None
        if not (isinstance(code, str) and code):
            continue
        if code in seen:
            dup.add(code)
        else:
            seen.append(code)
    missing = [c for c in cp_codes if c not in seen]
    return {"missing": missing, "dup": sorted(dup), "routed": len(seen)}


# ── #53 / #68：release_status 生产点全量扫描 ────────────────────────────
RELEASE_OUTCOMES = ("待放行", "已放行", "已拒绝", "已撤回", "已失效")
# T-310b（2026-10-25）：人工门状态机的权威住址搬进 review_reducer.py
# （签发进权威），release_gate.py 保留开发装配的内存路径 —— 两处是同一台
# 状态机的两个落点（施工单 §T-310c），**第三个文件出现仍然红**。
HUMAN_GATE_FILES = frozenset({
    os.path.join("base", "release_gate.py"),
    os.path.join("base", "review_reducer.py"),
})
RELEASE_PRODUCERS = ("base/disposition_router.py", "base/decision_table.py",
                     "base/judge_entry.py", "base/media.py",
                     "base/release_gate.py", "base/case_watch.py",
                     "api/review_api.py", "api/write_api.py")


def _const_write_sites(tree):
    """release_status 常量写入点：dict 字面量 / 下标赋值 / 关键字实参。"""
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "release_status" \
                        and isinstance(v, ast.Constant):
                    sites.append(v.value)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) \
                        and t.slice.value == "release_status" \
                        and isinstance(node.value, ast.Constant):
                    sites.append(node.value.value)
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "release_status" and isinstance(kw.value, ast.Constant):
                    sites.append(kw.value.value)
    return sites


def _scan_release_writes(sources):
    """E4 判定器：多文件 release_status 常量扫描（#53 / #68）。
    sources = {相对路径: 源码文本} → 违规清单（空 = 通过）。
      ① 常量值只允许五档结局；
      ② 人工门结局（非「待放行」）只许出现在 HUMAN_GATE_FILES
        （release_gate.py 内存路径 + review_reducer.py 权威路径，T-310b）。
    ★ 结局清单来自判据原文，不从被扫文件读 —— 常量改了断言不会跟着绿。"""
    bad = []
    for rel in sorted(sources):
        try:
            tree = ast.parse(sources[rel])
        except SyntaxError as e:
            bad.append("%s: 语法解析失败 %s" % (rel, e))
            continue
        for v in _const_write_sites(tree):
            if v is None:
                continue        # ERROR 骨架里的占位 None
            if v not in RELEASE_OUTCOMES:
                bad.append("%s: release_status 常量 %r 不在五档结局内" % (rel, v))
            elif v != "待放行" and rel not in HUMAN_GATE_FILES:
                bad.append("%s: 人工门结局 %r 出现在人工门状态机文件之外"
                           % (rel, v))
    return bad


def _label_maps(sources):
    """E5 判定器：任何生产文件不得出现 五档标签 → 释放状态 的直连映射。"""
    bad = []
    for rel in sorted(sources):
        try:
            tree = ast.parse(sources[rel])
        except SyntaxError:
            continue            # 语法错由 E4 报
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value in FIVE \
                            and isinstance(v, ast.Constant) \
                            and isinstance(v.value, str) and not v.value.startswith("DP"):
                        bad.append("%s: %r → %r 直连映射" % (rel, k.value, v.value))
    return bad


def _load_producer_sources():
    """base/*.py + api/*.py 全量读入（相对路径 → 源码文本）。"""
    srcs = {}
    for d in ("base", "api"):
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if fn.endswith(".py"):
                rel = "%s/%s" % (d, fn)
                with open(os.path.join(dp, fn), encoding="utf-8") as f:
                    srcs[rel] = f.read()
    return srcs


# ── #68：签发身份样本（真实走一遍 release_gate.sign）────────────────────
SIGN_CASE = {
    "case_id": "case-h", "case_version": 1,
    "ir_id": "ir-1", "ir_version": "review-ir-v1",
    "raw_sha256": "1" * 64, "text_sha256": "2" * 64,
    "rule_snapshot": {"version": "rs-1", "hash": "3" * 64},
    "kb_snapshot": {"version": "kb-1", "hash": "4" * 64},
    "used_authority_refs": [{"ref_id": "E1", "version": "v1"}],
    "conflict_table_version": "ct-1",
    "media_fingerprints": [],
    "frame_manifest_hash": "f" * 64, "keyframe_set_hash": "e" * 64,
    "ocr_output_hash": "d" * 64, "asr_output_hash": "c" * 64,
    "model_config_hash": "b" * 64, "sampling_config_hash": "a" * 64,
    "submitter_id": "u1", "final_reviewer_id": "u2",
    "tenant": "t1", "product_line": "p1",
}


def _sign_case(tmpdir, principal_id="u3", case_id="case-h", now=1000):
    """真实签发一件案子，返回 (sig, principal, gate)。"""
    sessions = SessionStore(os.path.join(tmpdir, "sess_%s.db" % case_id))
    gate = ReleaseGate(sessions=sessions)
    principal = {"id": principal_id, "tenant": "t1", "product_line": "p1",
                 "capabilities": ["release.sign"]}
    case = dict(SIGN_CASE)
    case["case_id"] = case_id
    token = sessions.issue_step_up(principal_id, case_id, "sign", "n1", now=now)
    sig = gate.sign(case, principal, token, "n1", reason="ctl", now=now + 1)
    return sig, principal, gate


def _signer_mismatch(sig, principal):
    """H1 判定器：签发记录的 signer_id 必须等于**本次授权** principal 的 id。"""
    pid = principal.get("id") if isinstance(principal, dict) else None
    if isinstance(pid, str) and pid and sig.get("signer_id") == pid:
        return []
    return ["signer_id=%r != 授权 principal.id=%r" % (sig.get("signer_id"), pid)]


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


def decision_for_layer(layer):
    return {
        "DP0": dec("未审查", "DP0"),
        "DP1": dec("待自决", "DP1"),
        "DP2": dec("BLOCK", "DP2"),
        "DP3": dec("REVIEW", "DP3"),
        "DP4": dec("REVIEW", "DP4", any_authority_conflict=True),
    }[layer]


def expected_due(now, due_text):
    """独立复算 business-day due_at，不 import 被测模块的私有函数。"""
    dt = datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
    n = int(re.search(r"(\d+)\s*个工作日", due_text or "").group(1))
    added = 0
    while added < n:
        dt = dt + datetime.timedelta(days=1)
        if dt.weekday() < 5:
            added += 1
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    fails = []
    untested = []
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

    # ── A8 五层「谁接/谁结」与规定值恒等（#49）────────────────────────
    #   A3 只断言 finalizer 非空 —— DP4 finalizer 从「法务」改成「项目统筹」时
    #   105 项全绿（#49 变异实测）。这里拿判据原文的规定值逐层对拍。
    routed = {}
    for layer in ("DP0", "DP1", "DP2", "DP3", "DP4"):
        routed[layer] = router.route(decision_for_layer(layer), RECEIPT,
                                     now="2026-10-19T02:00:00Z")
    role_bad = _role_mismatches(routed)
    T("A8 五层 owner/finalizer 与规定值逐层恒等（DP4=法务、DP3=内容审核员…）",
      role_bad == [], "; ".join(role_bad))
    T("A8b 每次路由只产出唯一一个处置层（无多层并存/无层可落）",
      all(r.get("layer") in ("DP0", "DP1", "DP2", "DP3", "DP4") for r in routed.values()),
      str({k: r.get("layer") for k, r in routed.items()}))

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
              "appeal_channel", "due_at", "case_id", "escalation",
              "routing_version"):
        T("C1 输出字段 %s 存在且非空" % k,
          k in r_b and r_b[k] not in (None, ""), str(r_b.get(k)))
    T("C2 五档 release_status 全部待放行",
      all(router.route(d, RECEIPT)["release_status"] == "待放行" for _, d, _, _ in cases), "")

    # ── P routing-v1 逐条一致：owner / due_at / escalation ──────────
    NOW = "2026-10-19T02:00:00Z"
    routing = json.load(open(router.path, encoding="utf-8"))
    rows = routing.get("routes") or []
    T("P0 routing 表非空且每条含 owner/due/escalation",
      bool(rows) and all(
          isinstance(r.get("owner"), str) and r.get("owner")
          and isinstance(r.get("due"), str) and r.get("due")
          and isinstance(r.get("escalation"), str) and r.get("escalation")
          for r in rows), "rows=%d" % len(rows))
    for row in rows:
        code = row.get("control_code")
        r = router.route(decision_for_layer(row.get("layer")), RECEIPT,
                         control_code=code, now=NOW)
        T("P1 %s owner/due_at/escalation 与 routing-v1 一致" % code,
          r.get("owner") == row.get("owner")
          and r.get("escalation") == row.get("escalation")
          and r.get("due_at") == expected_due(NOW, row.get("due"))
          and r.get("routing_version") == routing.get("routing_version"),
          "got owner=%r due=%r escalation=%r version=%r; want owner=%r due=%r escalation=%r"
          % (r.get("owner"), r.get("due_at"), r.get("escalation"),
             r.get("routing_version"), row.get("owner"),
             expected_due(NOW, row.get("due")), row.get("escalation")))

    # 临时 routing 表：row 的 owner/due/escalation 必须真的覆盖默认值。
    tmpdir = tempfile.mkdtemp(prefix="disposition_routing_")
    try:
        custom_path = os.path.join(tmpdir, "routing.json")
        with open(custom_path, "w", encoding="utf-8") as f:
            json.dump({
                "routing_version": "routing-custom-v1",
                "routes": [{
                    "control_code": "X1", "layer": "DP4",
                    "owner": "自定义 owner", "due": "5 个工作日",
                    "escalation": "自定义升级",
                }],
            }, f, ensure_ascii=False)
        custom = DispositionRouter(custom_path)
        rc = custom.route(dec("REVIEW", "DP4", any_authority_conflict=True),
                          RECEIPT, control_code="X1", now=NOW)
        T("P2 临时 routing 表 owner 覆盖默认角色",
          rc.get("owner") == "自定义 owner", repr(rc.get("owner")))
        T("P2 临时 routing 表 due 覆盖默认期限",
          rc.get("due_at") == expected_due(NOW, "5 个工作日"),
          "%r vs %r" % (rc.get("due_at"), expected_due(NOW, "5 个工作日")))
        T("P2 临时 routing 表 escalation 覆盖默认升级",
          rc.get("escalation") == "自定义升级", repr(rc.get("escalation")))
        T("P2 临时 routing 表 routing_version 透传",
          rc.get("routing_version") == "routing-custom-v1",
          repr(rc.get("routing_version")))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── C4 主表 × routing 表全连接（#50）────────────────────────────
    #   P1 只对「routing 表里有的行」自洽：routing 删掉 H09 那行时它少查一条
    #   且全绿（#50 变异实测）。全连接以主表 control-points-v1.json 为基准。
    cp_codes, cp_err = _load_cp_codes()
    if cp_codes is None:
        print("  ⚠ C4 未测：%s" % cp_err)
        untested.append("C4 " + cp_err)
    else:
        gaps = _routing_gaps(cp_codes, rows)
        T("C4 主表全部 %d 个 control_code 在 routing 表各有恰一行（缺/重都红）"
          % len(cp_codes),
          gaps["missing"] == [] and gaps["dup"] == [],
          "missing=%s dup=%s routed=%d" % (gaps["missing"], gaps["dup"], gaps["routed"]))
        T("C4b routing 表无未登记的孤儿行",
          all(isinstance(row.get("control_code"), str)
              and row.get("control_code") in set(cp_codes) for row in rows),
          str([row.get("control_code") for row in rows
               if row.get("control_code") not in set(cp_codes)]))

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

    # ── E4/E5 静态扫描扩到全部 release_status 生产点（#53 / #68）────
    #   旧扫描只读 disposition_router.py 一个文件：decision_table.py:337
    #   写「放行」时 105 项全绿（#53 变异实测）。
    srcs = _load_producer_sources()
    if not srcs:
        print("  ⚠ E4/E5 未测：base/ api/ 读不出源码")
        untested.append("E4/E5 base/ api/ 读不出源码")
    else:
        e4 = _scan_release_writes(srcs)
        T("E4 release_status 常量写入点全量扫描（base/ + api/ 共 %d 个文件）只许五档结局，人工门结局只在 release_gate.py"
          % len(srcs), e4 == [], "; ".join(e4))
        e5 = _label_maps(srcs)
        T("E5 任何生产文件不得有 五档标签→释放状态 直连映射", e5 == [], "; ".join(e5))

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

    # ── H 人工签发才改变放行状态、签发记录含正确的签发人（#68）──────
    #   旧验证器 0 处提到 签发/signer：signer_id 写成常量 "system" 时
    #   verify_release_gate 62 项也全绿（#68 变异实测）—— 它只断言字段在场
    #   与 SoD 权限，从不把记录与授权 principal 身份对拍。
    tmpdir_h = tempfile.mkdtemp(prefix="disposition_sign_")
    try:
        sig_h, principal_h, gate_h = _sign_case(tmpdir_h)
        mism = _signer_mismatch(sig_h, principal_h)
        T("H1 签发记录 signer_id 必须等于本次授权 principal 的 id", mism == [],
          "; ".join(mism))
        T("H2 签发记录含签发时间与 step-up ref（记录可追溯到人）",
          isinstance(sig_h.get("signed_at"), str) and sig_h["signed_at"]
          and isinstance(sig_h.get("step_up_ref"), str) and sig_h["step_up_ref"],
          "signed_at=%r step_up_ref=%r" % (sig_h.get("signed_at"), sig_h.get("step_up_ref")))
        st_h = gate_h.state("case-h")
        T("H3 人工签发后放行状态才改变（sign → 已放行）",
          st_h["status"] == "signed" and st_h["release_status"] == "已放行", str(st_h))
        # 反向对照（进程内）：换一个授权人签发，记录必须跟着换 —— 防「死常量」断言。
        sig_b, principal_b, _ = _sign_case(tmpdir_h, principal_id="u9",
                                           case_id="case-h2", now=2000)
        T("H4 换授权人签发 → signer_id 跟着换（不是写死的常量）",
          sig_b["signer_id"] == "u9" and sig_b["signer_id"] != sig_h["signer_id"],
          "%r vs %r" % (sig_b["signer_id"], sig_h["signer_id"]))
        # 机器 patch 写 release_status/status → 拒（#68：机器标签不可写放行）。
        try:
            gate_h.apply_machine_patch("case-h", {"release_status": "已放行"})
            T("H5 机器 patch 写 release_status → 拒", False, "未拒")
        except MachineWriteDenied:
            T("H5 机器 patch 写 release_status → 拒", True, "")
        try:
            gate_h.apply_machine_patch("case-h", {"status": "signed"})
            T("H6 机器 patch 写 status → 拒", False, "未拒")
        except MachineWriteDenied:
            T("H6 机器 patch 写 status → 拒", True, "")
    finally:
        shutil.rmtree(tmpdir_h, ignore_errors=True)

    for f in fails:
        print("  ❌ " + f)
    for u in untested:
        print("  ⚠ 未测：" + u)
    verdict = "❌" if fails else ("⚠" if untested else "✅")
    print("\n%s verify_disposition_router %d 项检查 · %d 项红 · %d 项未测"
          % (verdict, checks, len(fails), len(untested)))
    if fails:
        return 1
    if untested:
        return 2
    return 0


def run_controls():
    """--controls：好样本必须闭嘴，坏样本必须各自红（§2.4.1）。

    每组判定器都是「拿真实产物跑一遍」的好样本 + 判据原文里的坏样本形状，
    全部进程内构造，不改任何盘上文件。
    """
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    tmpdir = tempfile.mkdtemp(prefix="disposition_ctl_")
    try:
        router = DispositionRouter()

        # ── A8 五层角色判定器 ──────────────────────────────────────
        routed = {layer: router.route(decision_for_layer(layer), "rcpt_ctl",
                                      now="2026-10-19T02:00:00Z")
                  for layer in ("DP0", "DP1", "DP2", "DP3", "DP4")}
        ok("C-1 好样本（真实五层路由）→ 角色判定器闭嘴",
           _role_mismatches(routed) == [], str(_role_mismatches(routed)))
        # C-2 = #49 变异形状：DP4 finalizer 掉包成「项目统筹」
        bad_dp4 = dict(routed)
        bad_dp4["DP4"] = dict(routed["DP4"], finalizer="项目统筹")
        ok("C-2 DP4 finalizer=项目统筹 → 红", _role_mismatches(bad_dp4) != [],
           str(_role_mismatches(bad_dp4)))
        # C-3 反向：换一层（DP3 owner=法务）也必须红 —— 不许只认 DP4 一个形状
        bad_dp3 = dict(routed)
        bad_dp3["DP3"] = dict(routed["DP3"], owner="法务")
        ok("C-3 DP3 owner=法务（掉包另一层）→ 红",
           _role_mismatches(bad_dp3) != [], str(_role_mismatches(bad_dp3)))

        # ── C4 全连接判定器 ────────────────────────────────────────
        routing = json.load(open(router.path, encoding="utf-8"))
        rows = routing.get("routes") or []
        cp_codes, cp_err = _load_cp_codes()
        if cp_codes is None:
            ok("C-4…C-6 全连接未测：%s" % cp_err, False)
        else:
            ok("C-4 好样本（真实 routing 表）→ 全连接判定器闭嘴",
               _routing_gaps(cp_codes, rows) == {"missing": [], "dup": [], "routed": len(cp_codes)},
               str(_routing_gaps(cp_codes, rows)))
            # C-5 = #50 变异形状：routing 表丢一行 H09
            rows_missing = [r for r in rows if r.get("control_code") != "H09"]
            ok("C-5 routing 表丢 H09 → 红",
               _routing_gaps(cp_codes, rows_missing)["missing"] == ["H09"],
               str(_routing_gaps(cp_codes, rows_missing)))
            # C-6 反向：一对多（H01 两行）也必须红
            rows_dup = list(rows) + [dict(rows[0])]
            ok("C-6 H01 出现两行（一对多）→ 红",
               _routing_gaps(cp_codes, rows_dup)["dup"] == ["H01"],
               str(_routing_gaps(cp_codes, rows_dup)))

        # ── E4/E5 release_status 扫描器 ────────────────────────────
        srcs = _load_producer_sources()
        ok("C-7 好样本（真实 base/ + api/ 源码）→ 扫描器闭嘴",
           srcs and _scan_release_writes(srcs) == [] and _label_maps(srcs) == [],
           "%s / %s" % (_scan_release_writes(srcs), _label_maps(srcs)))
        # C-8 = #53 变异形状：decision_table.py 写「放行」
        src_bad = dict(srcs)
        src_bad["base/decision_table.py"] = srcs["base/decision_table.py"].replace(
            '"release_status": "待放行",', '"release_status": "放行",', 1)
        ok("C-8 decision_table.py 写「放行」→ 红",
           _scan_release_writes(src_bad) != [], str(_scan_release_writes(src_bad)))
        # C-9 反向：release_gate.py 之外写人工门结局也必须红
        #   （case_watch.py 里混进一个 release_status="已放行" 的字面量写入点）
        src_bad2 = dict(srcs)
        src_bad2["base/case_watch.py"] = srcs["base/case_watch.py"] + \
            '\n\n_WATCH_BAD = {"release_status": "已放行"}\n'
        ok("C-9 release_gate.py 之外写「已放行」→ 红",
           any("case_watch" in x for x in _scan_release_writes(src_bad2)),
           str(_scan_release_writes(src_bad2)))
        # C-10 = E5 形状：标签直连映射
        src_bad3 = dict(srcs)
        src_bad3["api/review_api.py"] = srcs["api/review_api.py"] + \
            '\n\n_LABEL_MAP = {"PASS": "已放行"}\n'
        ok("C-10 PASS→已放行 直连映射 → 红",
           _label_maps(src_bad3) != [], str(_label_maps(src_bad3)))

        # ── H1 签发身份判定器 ──────────────────────────────────────
        sig_h, principal_h, _ = _sign_case(tmpdir, case_id="ctl-good")
        ok("C-11 好样本（真实签发）→ 身份判定器闭嘴",
           _signer_mismatch(sig_h, principal_h) == [], str(_signer_mismatch(sig_h, principal_h)))
        # C-12 = #68 变异形状：signer_id 写成常量 "system"
        sig_sys = dict(sig_h, signer_id="system")
        ok("C-12 signer_id=system（不是授权人）→ 红",
           _signer_mismatch(sig_sys, principal_h) != [],
           str(_signer_mismatch(sig_sys, principal_h)))
        # C-13 反向：换成另一个真实用户也必须红（不许只认 "system" 一个串）
        sig_other = dict(sig_h, signer_id="u77")
        ok("C-13 signer_id=u77（不是授权人）→ 红",
           _signer_mismatch(sig_other, principal_h) != [],
           str(_signer_mismatch(sig_other, principal_h)))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    passed = sum(1 for _, p, _ in results if p)
    for name, p, detail in results:
        print("  %s %s  %s" % ("✓" if p else "✗", name, detail))
    print("\n%s verify_disposition_router --controls %d/%d"
          % ("✅" if passed == len(results) else "✗", passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run_controls() if "--controls" in sys.argv[1:] else main())
