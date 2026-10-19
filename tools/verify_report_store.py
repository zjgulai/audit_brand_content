#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_report_store.py —— `base/report_store.py` 的判据（T1-12）

## 它验什么

  A **发布**：report_id 内容寻址；静态文件落盘；URL 指向静态 .md 对象；
    索引只追加；同内容重复发布不重复追加。
  B **R2**：IR 版本变 → 新 report_id；旧文件不修改、不删除。
  C **L4-2 重建**：`rebuild(ir, renderer)` 必须得到同一 report_id / 同一内容；
    删掉文件后仍可重建，并可恢复。
  D **R1**：渲染文本必须含 `source_ir_version` 与 `source_ir_fingerprint`；
    缺一或指纹不符 → 拒发布。
  E **ACL 回读**：无权限 → `{ok:false,url:null}`，不得返回 URL。
  F **完整性**：旧报告被改 / 索引重复 → 读与校验必须红。
  G **静态链接**：URL 不含 /api/ 或 render；构造器拒绝渲染服务 base。
  H **反向对照**：删掉任一守卫（变异由外部执行）→ 上述断言必须红。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from report_store import ReportStore
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/report_store.py 失败：%s" % e)
    sys.exit(1)

ACL = {"tenant": "t1", "product_line": "p1", "submitter_id": "u1", "assigned": ["u2"]}
P_SUB_OWN = {"id": "u1", "role": "submitter", "tenant": "t1", "product_line": "p1"}
P_SUB_OTHER = {"id": "u9", "role": "submitter", "tenant": "t1", "product_line": "p1"}
P_DP3 = {"id": "u2", "role": "DP3", "tenant": "t1", "product_line": "p1"}
P_DP3_OTHER_TENANT = {"id": "u2", "role": "DP3", "tenant": "t2", "product_line": "p1"}
P_DP3_WRONG_PL = {"id": "u2", "role": "DP3", "tenant": "t1", "product_line": "p2"}
P_DP3_UNASSIGNED = {"id": "u3", "role": "DP3", "tenant": "t1", "product_line": "p1"}
P_COORD = {"id": "u4", "role": "coordinator", "tenant": "t1", "product_line": "p1"}
P_COORD_OTHER = {"id": "u4", "role": "coordinator", "tenant": "t2", "product_line": "p1"}
P_IT = {"id": "u5", "role": "IT", "tenant": "t1", "product_line": "p1"}


def ir(version=1, body="A"):
    return {"ir_id": "ir_1", "ir_version": version, "body": body,
            "source_ir_version": "cu-test", "findings": [],
            "decision": {"state": "PASS"}}


def fp(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def render(x):
    return ("# 报告\n\nsource_ir_version: %s\nsource_ir_fingerprint: %s\n"
            "- 状态：%s\n\n正文 %s\n"
            % (x.get("source_ir_version") or x["ir_version"], fp(x),
               x.get("decision", {}).get("state", "PASS"), x.get("body", "")))


def render_missing_version(x):
    return ("# 报告\n\nsource_ir_fingerprint: %s\n- 状态：%s\n\n正文 %s\n"
            % (fp(x), x.get("decision", {}).get("state", "PASS"), x.get("body", "")))


def render_bad_fp(x):
    return ("# 报告\n\nsource_ir_version: %s\nsource_ir_fingerprint: %s\n"
            "- 状态：%s\n\n正文\n"
            % (x.get("source_ir_version") or x["ir_version"], "0" * 64,
               x.get("decision", {}).get("state", "PASS")))


def render_forbidden(x):
    return ("# 报告\n\nsource_ir_version: %s\nsource_ir_fingerprint: %s\n"
            "- 状态：%s\n\n本次审批已通过，无需处理。\n"
            % (x.get("source_ir_version") or x["ir_version"], fp(x),
               x.get("decision", {}).get("state", "PASS")))


def render_ratio(x):
    return ("# 报告\n\nsource_ir_version: %s\nsource_ir_fingerprint: %s\n"
            "- 状态：%s\n\n本周审核通过率为 98%%。\n"
            % (x.get("source_ir_version") or x["ir_version"], fp(x),
               x.get("decision", {}).get("state", "PASS")))


def main():
    fails = []
    checks = 0
    try:
        TMP = tempfile.mkdtemp(prefix="reportstore_")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    base_url = "https://static.example.com"
    store = ReportStore(os.path.join(TMP, "data"), base_url)

    # ── A 发布 / 索引 / URL ─────────────────────────────────────────
    r1 = store.publish(ir(1, "A"), render, ACL, now="2026-10-19T00:00:00Z")
    T("A1 发布成功", r1.get("ok") is True, str(r1))
    rid = r1.get("report_id")
    T("A2 report_id 形如 rp+16 hex",
      isinstance(rid, str) and rid.startswith("rp") and len(rid) == 18
      and all(c in "0123456789abcdef" for c in rid[2:]), str(rid))
    T("A3 URL 指向静态 .md 对象",
      isinstance(r1.get("url"), str) and r1["url"].startswith(base_url + "/reports/")
      and r1["url"].endswith("/%s.md" % rid) and "/api/" not in r1["url"]
      and "render" not in r1["url"].lower(), str(r1.get("url")))
    path = os.path.join(TMP, "data", r1["path"])
    T("A4 静态文件存在且内容 == 渲染文本",
      os.path.isfile(path) and open(path, "rb").read() == render(ir(1, "A")).encode(), path)
    idx = store.read_index()
    T("A5 索引恰好一条且字段齐全", len(idx["records"]) == 1
      and idx["records"][0]["report_id"] == rid
      and idx["records"][0]["source_ir_version"] == 1
      and idx["records"][0]["sha256"] == hashlib.sha256(render(ir(1, "A")).encode()).hexdigest(), str(idx))
    r1b = store.publish(ir(1, "A"), render, ACL, now="2026-10-19T00:00:01Z")
    T("A6 同内容重复发布 → duplicate，不追加索引",
      r1b.get("ok") is True and r1b.get("duplicate") is True
      and len(store.read_index()["records"]) == 1, str(r1b))

    # ── B R2：IR 变 → 新 id、旧文件不动 ────────────────────────────
    old_bytes = open(path, "rb").read()
    idx_path_b = os.path.join(TMP, "data", "reports", "index.jsonl")
    idx_prefix = open(idx_path_b, "rb").read()
    r2 = store.publish(ir(2, "B"), render, ACL)
    T("B0 索引只追加（旧字节是新索引的前缀）",
      open(idx_path_b, "rb").read().startswith(idx_prefix), "")
    T("B1 IR 版本变 → 新 report_id", r2.get("ok") and r2["report_id"] != rid, str(r2))
    T("B2 旧文件字节不变", open(path, "rb").read() == old_bytes, "")
    T("B3 索引两条（只追加）", len(store.read_index()["records"]) == 2, str(len(store.read_index()["records"])))
    # 渲染文本相同但 IR 版本不同 → 仍必须新 id（R2）
    same_text = ("# 报告\n\nsource_ir_version: %s\nsource_ir_fingerprint: %s\n"
                 "- 状态：%s\n\n正文 X\n")
    rr = store.publish(ir(3, "X"),
                       lambda x: same_text % (x["source_ir_version"], fp(x), "PASS"), ACL)
    rr2 = store.publish(ir(4, "X"),
                        lambda x: same_text % (x["source_ir_version"], fp(x), "PASS"), ACL)
    T("B4 渲染文本相同、IR 版本不同 → 不同 id",
      rr.get("ok") and rr2.get("ok") and rr["report_id"] != rr2["report_id"], "%s / %s" % (rr, rr2))

    # ── C L4-2 重建 / 删文件后可复现 ───────────────────────────────
    rb = store.rebuild(ir(1, "A"), render, expected_report_id=rid)
    T("C1 rebuild 得到同一 id / 同一内容",
      rb.get("ok") is True and rb.get("report_id") == rid
      and rb.get("text") == render(ir(1, "A")), str(rb)[:200])
    os.unlink(path)
    T("C2 删文件后 read 不给 URL",
      store.read(rid, P_SUB_OWN).get("ok") is False
      and store.read(rid, P_SUB_OWN).get("url") is None, str(store.read(rid, P_SUB_OWN)))
    rb2 = store.rebuild(ir(1, "A"), render, expected_report_id=rid)
    T("C3 删文件后仍能从 IR 重建同内容", rb2.get("ok") is True and rb2.get("text") == render(ir(1, "A")), str(rb2)[:200])
    rr3 = store.publish(ir(1, "A"), render, ACL)
    T("C4 用 IR 重新 publish 可恢复静态文件",
      rr3.get("ok") is True and os.path.isfile(path) and open(path, "rb").read() == old_bytes, str(rr3))
    T("C5 重建内容不同 → 必须拒",
      store.rebuild(ir(1, "A"), lambda x: render(x) + "X", expected_report_id=rid).get("ok") is False, "")

    # ── D R1：渲染文本必须记 source_ir_version + 指纹 ──────────────
    for cid, fn in (("D1 缺 source_ir_version", render_missing_version),
                    ("D2 指纹不符", render_bad_fp)):
        r = store.publish(ir(9, "Z"), fn, ACL)
        T(cid + " → 拒发布", r.get("ok") is False and r.get("url") is None, str(r))

    # ── D3–D5 回执禁词闸：拒发布/拒重建，且不落盘、不进 index ─────
    fs = ReportStore(os.path.join(TMP, "forbidden"), base_url)
    files_before = os.listdir(os.path.join(fs.root, "reports"))
    rf = fs.publish(ir(20, "F"), render_forbidden, ACL)
    T("D3 回执禁词 → 拒发布 + code/detail/hits",
      rf.get("ok") is False and rf.get("url") is None
      and rf.get("code") == "receipt_forbidden_word"
      and "receipt_forbidden_word" in (rf.get("detail") or "")
      and {"已通过", "无需处理"} <= {h.get("word") for h in (rf.get("hits") or [])},
      str(rf))
    T("D4 禁词拒绝 → 无文件落盘、index 为空",
      os.listdir(os.path.join(fs.root, "reports")) == files_before
      and fs.read_index()["records"] == [], str(fs.read_index()))
    rbf = fs.rebuild(ir(20, "F"), render_forbidden)
    T("D5 rebuild 同样拒禁词",
      rbf.get("ok") is False and rbf.get("code") == "receipt_forbidden_word", str(rbf))
    rn = fs.publish(ir(21, "R"), render_ratio, ACL)
    T("D6 负样本「通过率」正常发布",
      rn.get("ok") is True and "通过率" in open(
          os.path.join(fs.root, rn.get("path", "")), encoding="utf-8").read(), str(rn))

    # ── E ACL 回读 ─────────────────────────────────────────────────
    allowed = [("E1 提交人本人", P_SUB_OWN), ("E2 DP3 已指派同品线", P_DP3),
               ("E3 项目统筹同租户", P_COORD)]
    denied = [("E4 提交人他人", P_SUB_OTHER), ("E5 DP3 跨租户", P_DP3_OTHER_TENANT),
              ("E6 DP3 跨品线", P_DP3_WRONG_PL), ("E7 DP3 未指派", P_DP3_UNASSIGNED),
              ("E8 项目统筹跨租户", P_COORD_OTHER), ("E9 IT 读内容", P_IT)]
    for cid, p in allowed:
        r = store.read(rid, p)
        T(cid + " → 给 URL", r.get("ok") is True and r.get("url") == r1["url"], str(r))
    for cid, p in denied:
        r = store.read(rid, p)
        T(cid + " → 无 URL", r.get("ok") is False and r.get("url") is None, str(r))

    # ── F 完整性：改旧报告 / 索引重复 ──────────────────────────────
    with open(path, "ab") as f:
        f.write(b"TAMPER")
    rt = store.read(rid, P_SUB_OWN)
    T("F1 旧报告被改 → read 拒绝且不给 URL",
      rt.get("ok") is False and rt.get("url") is None and rt.get("detail") == "integrity", str(rt))
    T("F2 verify_integrity 报错", store.verify_integrity() != [], str(store.verify_integrity())[:200])
    # 修复文件后索引重复
    open(path, "wb").write(old_bytes)
    idx_path = os.path.join(TMP, "data", "reports", "index.jsonl")
    with open(idx_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(store.read_index()["records"][0], ensure_ascii=False) + "\n")
    T("F3 read_index 报出重复", store.read_index()["duplicates"] != [], str(store.read_index()["duplicates"]))
    rd = store.read(rid, P_SUB_OWN)
    T("F4 索引重复 → read 拒绝且不给 URL", rd.get("ok") is False and rd.get("url") is None, str(rd))
    T("F5 索引重复 → publish 拒绝", store.publish(ir(5, "Q"), render, ACL).get("ok") is False, "")

    # ── G 静态链接守卫 ─────────────────────────────────────────────
    for bad in ("https://api.example.com/render", "https://x.example.com/api/v1/reports"):
        try:
            ReportStore(os.path.join(TMP, "bad_" + str(len(fails))), bad)
            T("G1 渲染服务 base 必须拒：%s" % bad, False, "未拒")
        except Exception:  # noqa: BLE001
            T("G1 渲染服务 base 必须拒：%s" % bad, True, "")
    try:
        ReportStore(os.path.join(ROOT, "reports_inside_repo"), base_url)
        T("G2 数据根在仓内 → 拒", False, "未拒")
    except Exception:  # noqa: BLE001
        T("G2 数据根在仓内 → 拒", True, "")

    # 源码静态扫描：所有 URL 字面量不得指向 /api/ 或渲染服务
    src = open(os.path.join(ROOT, "base", "report_store.py"), encoding="utf-8").read()
    urls = [n.value for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and "://" in n.value]
    T("G3 源码 URL 字面量不含 /api/ 或 render",
      all("/api/" not in u.lower() and "render" not in u.lower() for u in urls), str(urls))

    # ── H 反向对照（变异由外部执行；这里守住输入坏样本） ───────────
    T("H1 输入带 renderer 但内容不符 → 重建必须拒",
      store.rebuild(ir(1, "A"), lambda x: render(x) + "DIFF", expected_report_id=rid).get("ok") is False, "")
    T("H2 未授权 principal 永远拿不到 url",
      all(store.read(rid, p).get("url") is None for _, p in denied), "")

    shutil.rmtree(TMP, ignore_errors=True)
    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_report_store %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
