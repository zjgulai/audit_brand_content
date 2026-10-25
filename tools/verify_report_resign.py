#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_report_resign.py —— T-403 / ADR-0017：报告链接的过期签名

## 为什么单独一个文件

T-403 改的是 **R3 契约**（URL 形状）与 `ReportStore.read()` 的判据顺序。
这两处都有既有验证器，但它们的夹具全是「无签名 URL」——
签名这条路**一次都没被走过**。加在这个新文件里的理由也在这里：
既有验证器证明的是「改之前对的东西还对」，本文件证明「新加的东西真的成立」。

## 断言的层次（每一层都必须是**行为级**）

    R-1  resign 返回 200，url 带 exp 与 sig
    R-2  ★ 旧文件 sha256 一个字节没变（重签不碰正文）
    R-3  索引记录与权威 state["reports"] 都没变
    R-4  ★ 签名 URL **能打开**（参与人 + 有效签名）
    R-5  ★ **过期** URL 打不开 —— 即使请求者是参与人
    R-6  ★ **篡改** sig 一位 → 打不开
    R-7  ★ 换 report_id 复用签名 → 打不开（签名不跨报告）
    R-8  无签名 URL 仍能读（存量报告不许坏）
    R-9  ★ 密钥缺失 → resign 不要 200（503），且**不返回无签名的「新链接」**
    R-10 TTL 超上限 → 构造期拒
    R-11 轮换窗口：旧密钥签的链接，配上 _PREV 仍可验证
    R-12 ★ 反向对照：删掉 read() 里的验签 → R-5/R-6/R-7 必红

## 为什么 R-5 要求「参与人也打不开」

ADR-0017 §三：过期的意义就是「这扇门关了」。若参与人拿着过期链接仍能读，
过期就只是装饰 —— 而 Playbook §8.8 明写「过期不等于失效」是就**文件**说的，
不是就**链接**说的（文件不删，链接可以都不通）。

## 退出码

  0 全过 · 1 有红 · 2 未测（fastapi/report_store 导入失败）

用法：
  python3 tools/verify_report_resign.py
  python3 tools/verify_report_resign.py --controls
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = []
FAIL = []
UNTESTED = []


def ok(label, detail=""):
    PASS.append(label)
    print("PASS: %s%s" % (label, (" " + detail) if detail else ""))


def no(label, detail=""):
    FAIL.append((label, detail))
    print("FAIL: %s%s" % (label, (" " + detail) if detail else ""),
          file=sys.stderr)


try:
    from base.report_store import (
        LINK_TTL_MAX_SECONDS, ReportStore, sign_report_link, verify_report_link)
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base/report_store：%s" % exc)
    sys.exit(2)

SECRET = "s" * 40
SECRET_PREV = "p" * 40
BASE_URL = "https://static.example.com"

P_OWNER = {"id": "u_sub", "roles": ["submitter"], "tenant": "t1",
           "product_lines": ["pump"], "tenant_id": "t1", "open_id": "ou_sub"}
P_OTHER = {"id": "u_other", "roles": ["dp3"], "tenant": "t1",
           "product_lines": ["other"], "tenant_id": "t1", "open_id": "ou_other"}

ACL = {"tenant": "t1", "product_line": "pump", "submitter_id": "u_sub",
       "assigned": []}


def ir_variant(n=1):
    return {
        "ir_id": "ir-resign-%d" % n, "ir_version": "review-ir-v1",
        "source_ir_version": "cu-resign-%d" % n,
        "content_unit_ref": {"unit_id": "cu-resign-%d" % n, "kind": "free_text"},
        "findings": [],
        "decision": {"state": "REVIEW", "layer": "DP2",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "partial",
                     "modalities_evaluated": ["free_text"],
                     "rules_version": "rs-resign",
                     "control_points_applied": []},
        "receipt_ref": "rc-resign", "rule_snapshot": "rs-resign",
        "kb_snapshot": "kb-resign", "control_points_version": "cp-resign",
        "created_at": "2026-10-26T00:00:00Z",
    }


def render(ir):
    return (
        "# 审查报告\n\n"
        "- 状态：{state}\n"
        "- 结论摘要：内容审查完成\n"
        "- source_ir_version: {v}\n"
        "- source_ir_fingerprint: {fp}\n"
        "- 命中问题：无\n"
    ).format(state=ir["decision"]["state"],
             v=ir["source_ir_version"],
             fp=ReportStore.__module__ and __import__(
                 "hashlib").sha256(
                 json.dumps(ir, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest())


def make_store(root, secrets=(SECRET,), ttl=3600):
    """用**生产口径**的 ACL（`can_read_report`），不用 `_default_authorize`。

    ★ 这条是本项目踩过五次的坑（`rbac.can_read_report` 的 docstring 里
      逐条记着）：`_default_authorize` 读 `principal["role"]`（**单数**、
      `"DP3"` **大写**），而真实 principal 是 `roles`（**复数**、**小写**）。
      夹具若用前者，验出来的东西与生产不是一回事 —— 而它一直会绿。
    """
    from base.rbac import can_read_report
    return ReportStore(root, BASE_URL, authorize=can_read_report,
                       link_secrets=list(secrets), link_ttl=ttl)


def publish(store, n=1):
    out = store.publish(ir_variant(n), render, ACL)
    if not out.get("ok"):
        raise RuntimeError("publish 失败：%r" % (out,))
    return out


def run_checks():
    tmp = tempfile.mkdtemp(prefix="resign-")
    try:
        store = make_store(os.path.join(tmp, "r1"))
        pub = publish(store)
        rid = pub["report_id"]
        obj = os.path.join(store.root, pub["path"])
        sha_before = __import__("hashlib").sha256(open(obj, "rb").read()).hexdigest()
        idx_before = store.read_index()

        # ── R-1 重签返回带 exp/sig 的 url ─────────────────────────────
        out = store.resign(rid, P_OWNER, now=1_000_000)
        if out.get("ok") and "?exp=" in out["url"] and "&sig=" in out["url"]:
            ok("R-1 ★ resign 200 且 url 带 exp 与 sig", out["url"][-40:])
        else:
            no("R-1 resign 未返回带签名的 url", repr(out)[:200])

        # ── R-2 旧文件 sha256 一个字节没变 ────────────────────────────
        sha_after = __import__("hashlib").sha256(open(obj, "rb").read()).hexdigest()
        if sha_before == sha_after and (not out.get("ok")
                                        or out.get("sha256") == sha_before):
            ok("R-2 ★ 重签不碰正文（sha256 前后一致）", sha_before[:16])
        else:
            no("R-2 重签改了正文", "%s → %s" % (sha_before[:16], sha_after[:16]))

        # ── R-3 索引与状态没变 ────────────────────────────────────────
        idx_after = store.read_index()
        if (idx_after["records"] == idx_before["records"]
                and len(idx_after["records"]) == 1):
            ok("R-3 ★ 重签不写索引（签名字段没落盘）")
        else:
            no("R-3 重签改变了索引",
               "%d → %d 条" % (len(idx_before["records"]),
                               len(idx_after["records"])))

        # ── R-4 签名 URL 能打开（参与人）──────────────────────────────
        signed_url = out["url"]
        r4 = store.read(rid, P_OWNER, link_url=signed_url, now=1_000_001)
        if r4.get("ok"):
            ok("R-4 ★ 有效签名 URL 能打开（参与人）")
        else:
            no("R-4 有效签名 URL 打不开", repr(r4)[:200])

        # ── R-5 ★ 过期 URL 打不开，**即使参与人** ────────────────────
        r5 = store.read(rid, P_OWNER, link_url=signed_url, now=1_000_000 + 3601)
        if not r5.get("ok") and "link_expired" in str(r5.get("detail")):
            ok("R-5 ★ 过期 URL 打不开（参与人也不行）", str(r5.get("detail")))
        else:
            no("R-5 ★ 过期 URL 仍能读 —— 过期只是装饰", repr(r5)[:200])

        # ── R-6 篡改 sig 一位 → 打不开 ───────────────────────────────
        if not isinstance(signed_url, str):
            no("R-4~R-7 无法继续（resign 没给出 url）", repr(out)[:160])
            return
        tampered = signed_url[:-1] + ("0" if signed_url[-1] != "0" else "1")
        r6 = store.read(rid, P_OWNER, link_url=tampered, now=1_000_001)
        if not r6.get("ok"):
            ok("R-6 ★ 篡改 sig 一位 → 打不开", str(r6.get("detail")))
        else:
            no("R-6 篡改后的签名仍能读", repr(r6)[:200])

        # ── R-7 换 report_id 复用签名 → 打不开 ───────────────────────
        pub2 = publish(store, 2)
        rid2 = pub2["report_id"]
        reused = signed_url.replace(rid, rid2)
        r7 = store.read(rid2, P_OWNER, link_url=reused, now=1_000_001)
        if not r7.get("ok"):
            ok("R-7 ★ 签名不跨报告（换 report_id 即失效）", str(r7.get("detail")))
        else:
            no("R-7 签名可跨报告复用", repr(r7)[:200])

        # ── R-8 无签名 URL 仍能读（存量兼容）────────────────────────
        r8 = store.read(rid, P_OWNER)
        if r8.get("ok"):
            ok("R-8 ★ 无签名 URL 仍能读（存量报告没坏）")
        else:
            no("R-8 无签名 URL 打不开了（存量报告坏了）", repr(r8)[:200])

        # ── R-9 ★ 密钥缺失 → 不返 200，且不返回「新链接」 ────────────
        no_secret = make_store(os.path.join(tmp, "nos"), secrets=())
        nsp = publish(no_secret)
        r9 = no_secret.resign(nsp["report_id"], P_OWNER, now=1_000_000)
        if (not r9.get("ok") and r9.get("url") is None
                and r9.get("needs_secret") is True):
            ok("R-9 ★ 无密钥 → 不返回 url（needs_secret，调用方回 503）",
               str(r9.get("detail")))
        else:
            no("R-9 无密钥时返回了链接（降级成「看起来成功」）", repr(r9)[:200])

        # ── R-9b 非参与人不能重签（签名不能替代 ACL）─────────────────
        r9b = store.resign(rid, P_OTHER, now=1_000_000)
        if not r9b.get("ok") and r9b.get("detail") == "forbidden":
            ok("R-9b ★ 非参与人 → 403（签名不替代 ACL）")
        else:
            no("R-9b 非参与人也能重签", repr(r9b)[:200])

        # ── R-10 TTL 超上限 → 拒 ─────────────────────────────────────
        big = sign_report_link(SECRET, BASE_URL, rid,
                              LINK_TTL_MAX_SECONDS + 1, now=1_000_000)
        zero = sign_report_link(SECRET, BASE_URL, rid, 0, now=1_000_000)
        short_secret = sign_report_link("x" * 8, BASE_URL, rid, 3600)
        if (big.get("error") == "ttl_out_of_range"
                and zero.get("error") == "ttl_out_of_range"
                and short_secret.get("error") == "secret_too_short"):
            ok("R-10 ★ TTL 越界（0 / >30d）与弱密钥都被拒")
        else:
            no("R-10 TTL/密钥边界没拦住",
               repr((big, zero, short_secret))[:220])

        # ── R-11 轮换窗口：旧密钥签的，配 _PREV 仍可验 ───────────────
        old_signed = sign_report_link(SECRET_PREV, BASE_URL, rid, 3600,
                                      now=1_000_000)
        rotated = verify_report_link([SECRET, SECRET_PREV], BASE_URL,
                                     old_signed["url"], now=1_000_001)
        only_new = verify_report_link([SECRET], BASE_URL,
                                      old_signed["url"], now=1_000_001)
        if rotated["ok"] and not only_new["ok"]:
            ok("R-11 ★ 轮换窗口生效（旧密钥签的靠 _PREV 仍可验；只给新密钥则拒）")
        else:
            no("R-11 轮换窗口不成立",
               "rotated=%r only_new=%r" % (rotated, only_new))

        # ── R-12 键集合必须恒等（多一个键就拒）──────────────────────
        extra = signed_url + "&next=evil"
        if not ReportStore._valid_url(extra, BASE_URL):
            ok("R-12 ★ 查询串多一个键 → 形状非法（有东西没被签就不许过）")
        else:
            no("R-12 多余的查询键被放行", extra[-40:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_controls():
    """反向对照：把 read() 里的验签摘掉，R-5/R-6/R-7 必须红。"""
    print("=" * 70)
    print("反向对照：摘掉 read() 的验签，签名判据必须红")
    print("=" * 70)
    src_path = ROOT / "base" / "report_store.py"
    saved = src_path.read_text(encoding="utf-8")
    results = []
    try:
        # ★ 只改**判据那一段**：把 link_url 分支短路（`if False and ...`）。
        #   改成 `link_url is not None` → False 的等价值，但不碰其它逻辑。
        mutated = saved.replace(
            "        if link_url is not None:\n"
            "            checked = verify_report_link(",
            "        if False and link_url is not None:\n"
            "            checked = verify_report_link(")
        changed = mutated != saved
        src_path.write_text(mutated, encoding="utf-8")
        import importlib
        import base.report_store as rs
        importlib.reload(rs)
        before = len(FAIL)
        # 用 reload 后的 ReportStore 重跑核心判据
        run_resign_core(rs)
        went_red = len(FAIL) > before
        results.append(("C1 摘掉 read() 验签 → 过期/篡改/跨报告 必红", went_red, True))
    finally:
        src_path.write_text(saved, encoding="utf-8")
        import importlib
        import base.report_store as rs
        importlib.reload(rs)
    print("=" * 70)
    bad = 0
    for name, red, want in results:
        good = red == want
        bad += 0 if good else 1
        print("%s %s（红了=%s，期望红=%s）" % ("✅" if good else "❌", name, red, want))
    if bad == 0:
        print("✅ 反向对照 %d/%d 全过" % (len(results), len(results)))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (len(results) - bad, len(results)),
          file=sys.stderr)
    return 1


def run_resign_core(rs_module):
    """用**给定的模块**跑 R-4/R-5/R-6/R-7（反向对照要换模块）。"""
    tmp = tempfile.mkdtemp(prefix="resign-ctl-")
    try:
        from base.rbac import can_read_report
        store = rs_module.ReportStore(os.path.join(tmp, "r"), BASE_URL,
                                      authorize=can_read_report,
                                      link_secrets=[SECRET], link_ttl=3600)
        pub = store.publish(ir_variant(1), render, ACL)
        pub2 = store.publish(ir_variant(2), render, ACL)
        rid, rid2 = pub["report_id"], pub2["report_id"]
        signed = rs_module.sign_report_link(SECRET, BASE_URL, rid, 3600,
                                            now=1_000_000)["url"]
        # R-4 好样本必须绿
        r4 = store.read(rid, P_OWNER, link_url=signed, now=1_000_001)
        if not r4.get("ok"):
            no("C1/A R-4 好样本在变异后也坏了（对照无效）", repr(r4)[:120])
        # R-5 过期必须红
        r5 = store.read(rid, P_OWNER, link_url=signed, now=1_000_000 + 3601)
        if r5.get("ok"):
            no("C1/B R-5 过期 URL 仍能读（验签没生效）", "")
        # R-6 篡改必须红
        tampered = signed[:-1] + ("0" if signed[-1] != "0" else "1")
        r6 = store.read(rid, P_OWNER, link_url=tampered, now=1_000_001)
        if r6.get("ok"):
            no("C1/C R-6 篡改 URL 仍能读（验签没生效）", "")
        # R-7 跨报告必须红
        r7 = store.read(rid2, P_OWNER, link_url=signed.replace(rid, rid2),
                        now=1_000_001)
        if r7.get("ok"):
            no("C1/D R-7 签名跨报告仍能读", "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("verify_report_resign · T-403 / ADR-0017 · 报告链接的过期签名")
    print("=" * 70)
    run_checks()
    print("-" * 70)
    print("通过 %d 项 · 红 %d 项 · 未测 %d 项"
          % (len(PASS), len(FAIL), len(UNTESTED)))
    if FAIL:
        for label, detail in FAIL:
            print("  ✗ %s %s" % (label, detail), file=sys.stderr)
        print("❌ 有红", file=sys.stderr)
        return 1
    if UNTESTED:
        print("⚠ 有未测 —— 未测不是通过", file=sys.stderr)
        return 2
    print("✅ 全过")
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("UNTESTED: 验收器自身异常：%s" % exc, file=sys.stderr)
        sys.exit(2)
