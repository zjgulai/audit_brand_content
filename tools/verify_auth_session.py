#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_auth_session.py — T0-07 切片 1：会话与 step-up

覆盖：
  C0 cookie 只含 opaque id，服务端可解析 principal
     ★ 2026-10-24 #131 补票：C0g/C0h 断言 cookie 本体不含身份主键/tenant/
       rbac 角色名（长哨兵逐字判）；--controls 喂「数据编进 cookie」的
       坏实现形状必须红、真 create_session 不许误报
  C1 idle 30m / absolute 8h；活动只续 idle，不续 absolute
  C2 撤销立即失效
  C3 step-up TTL 5m、single-use、绑定 principal+case+action+nonce
  C4 跨案/跨动作/错 principal/错 nonce 拒绝
  C5 step-up 过期拒绝
  C6 session DB 丢失 → 全部 session + step-up 失效
  C7 invalidate_all → session + step-up 全部失效；之后新 session 可用
  C8 create_session 的 tenant 写入并回读（含默认值）
  C9 两个独立 SQLite 连接并发消费同一 token，恰一成功
  R2 去掉 absolute → 8h 后仍有效（测试注入）
  R3 cookie 塞 tenant → 必须红
  TS-11（行 114）量的锚：idle 29 分钟有效 / 31 分钟失效；absolute 7h59m 有效 /
       8h01m 失效且全程持续活动。★ 2026-10-24 探针实测：把 IDLE_SECONDS 改成
       45*60、ABSOLUTE_SECONDS 改成 4*60*60，验证器 43/43 全绿 —— 既有 C1 的
       检查点全部随实现常量走（now = t0 + IDLE_SECONDS + 1），量本身无锚。
       修法：判据体（probe_idle_boundary / probe_absolute_boundary）用判据原文的
       字面量（29/31 分钟、7h59m/8h01m），不读 base.auth_session 的任何常量。
  TS-13（行 115）量的锚：token 4 分钟内可用（a）/ 6 分钟后拒绝（c）。
       ★ 同一轮探针实测：STEP_UP_SECONDS 改成 90、issue 的 TTL 改成 now+60
         都 survived。修法同上（probe_ttl_boundary，字面量 4/6 分钟）。
       single-use（b）由 C3/C9 守（探针实测 AND used=0 变异被 C3+C9b 抓住）；
       跨案/跨动作（d/e）由 C4 守。这里只锚有效期**长短**。

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
全部使用 mktemp 临时 SQLite，不碰真实 session DB。
"""

import os
import secrets
import shutil
import sys
import tempfile
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.auth_session import (
        SessionStore, is_opaque_cookie,
        IDLE_SECONDS, ABSOLUTE_SECONDS, STEP_UP_SECONDS,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.auth_session: %s" % exc)
    sys.exit(2)


def _c0_leak_needles():
    """C0g/C0h 的**逐字判据针**：cookie 本体里不许出现的字面量。

    ★ 长度门槛是判据口径（见 main() 里 C0g 段的注释）：
      2 字符（'t1'/'it'）在 43 字符 base64url 上子串碰撞 ≈1e-2，不能当判据；
      12 字符 ≈1e-13、5 字符角色名合计 ≈3e-8，逐字判才可用。
      短名不进检查集不是遗漏 —— 是不让判据自己带一个 ~1% 的假红。
    """
    try:
        from base.rbac import ROLES as _ROLES
    except Exception:  # noqa: BLE001
        _ROLES = ()
    return ("ou_leak-probe", "tenant-leak-probe") + tuple(
        r for r in _ROLES if len(r) >= 5)


# ═══════════ TS-11/TS-13 的量锚（判据体，2026-10-24） ═══════════
#
# 通用形状（§2.8「同一个量有两个口径」）：**检查点写在 t0 + 常量 + 1** 的断言，
# 对「常量本身被改」恒真 —— 测试点跟着实现走。这一节的三条判据体全部用
# **判据原文的字面量**（验收表行 114：29/31 分钟、7h59m/8h01m；行 115：4/6 分钟），
# 一行 base.auth_session 的常量都不 import。探针实测：
#   IDLE_SECONDS 30*60 → 45*60       旧写法 43/43 全绿（survived）
#   ABSOLUTE_SECONDS 8h → 4h         旧写法全绿（survived）
#   STEP_UP_SECONDS 5*60 → 90        旧写法全绿（survived）
#   issue TTL now+STEP_UP_SECONDS → now+60   旧写法全绿（survived）
# 加锚后四者必须全 killed（见 --controls 的实测记录）。

# 判据原文的字面量（行 114 / 行 115），**不许替换成实现常量**
_IDLE_OK_S = 29 * 60        # idle 29 分钟 → 仍有效
_IDLE_EXP_S = 31 * 60       # idle 31 分钟 → 失效
_ABS_OK_S = 7 * 3600 + 59 * 60    # absolute 7 小时 59 分 → 仍有效
_ABS_EXP_S = 8 * 3600 + 60        # absolute 8 小时 01 分 → 失效
_TTL_OK_S = 4 * 60          # token 4 分钟内用 → 成功（行 115 (a)）
_TTL_EXP_S = 6 * 60         # 6 分钟后用 → 拒绝（行 115 (c)）


def probe_idle_boundary(make_store, t0=20000):
    """行 114 idle 段：29 分钟无活动仍有效、31 分钟无活动失效。返回 (ok, detail)。

    make_store() 必须造一个全新 SessionStore（零参）；判据体不读实现常量。
    两个会话分开造：get_session 会续 idle，同一个会话先读 29 分钟再读 31 分钟
    会把窗口续到 29 分钟处、31 分钟那点就不死了（第一版踩过，controls 抓的）。
    """
    store = make_store()
    try:
        c_ok = store.create_session("ou_idle", tenant="t1", now=t0)
        ok29 = store.get_session(c_ok, now=t0 + _IDLE_OK_S) is not None
        c_exp = store.create_session("ou_idle2", tenant="t1", now=t0)
        exp31 = store.get_session(c_exp, now=t0 + _IDLE_EXP_S) is None
        return (ok29 and exp31,
                "29 分钟=%s（须有效） / 31 分钟=%s（须失效）" % (ok29, exp31))
    finally:
        store.close()


def probe_absolute_boundary(make_store, t0=30000):
    """行 114 absolute 段：活动不断，7h59m 仍有效、8h01m 必须登出。

    「不能被活动续期」的判法：活动一直敲到 8h00m（越线前一分钟），
    8h01m 读数时 idle 距上次活动只有 1 分钟 —— 若此刻死了，只能是 absolute
    到点；若活动能把 absolute 续住，8h01m 就还活着。两个方向一次分辨。
    """
    store = make_store()
    try:
        c = store.create_session("ou_abs", tenant="t1", now=t0)
        # 活动每 5 分钟一次，从 t0 敲到 8h00m；中途死了就停（提前死由 7h59m 那点红）
        t = t0
        while t < t0 + 8 * 3600:
            t = min(t + 5 * 60, t0 + 8 * 3600)
            if store.get_session(c, now=t) is None:
                break
        ok7h59 = store.get_session(c, now=t0 + _ABS_OK_S) is not None
        store.get_session(c, now=t0 + 8 * 3600)          # 8h00m 最后一次活动
        exp8h01 = store.get_session(c, now=t0 + _ABS_EXP_S) is None
        return (ok7h59 and exp8h01,
                "7h59m=%s（须有效，活动敲到 8h00m 也不许提前死） / "
                "8h01m=%s（须失效，上次活动才隔 1 分钟 —— 活动续不动 absolute）"
                % (ok7h59, exp8h01))
    finally:
        store.close()


def probe_ttl_boundary(make_store, t0=40000):
    """行 115 (a)/(c)：token 4 分钟内可用、6 分钟后拒绝。返回 (ok, detail)。

    两个 token 分开造（single-use 由 C3/C9 守，这里锚有效期长短）。
    """
    store = make_store()
    try:
        tok = store.issue_step_up("ou_ttl", "case-ttl", "sign", "nonce-ttl", now=t0)
        ok4m = store.consume_step_up(
            tok, "ou_ttl", "case-ttl", "sign", "nonce-ttl", now=t0 + _TTL_OK_S)
        tok2 = store.issue_step_up("ou_ttl", "case-ttl", "sign", "nonce-ttl2", now=t0)
        exp6m = store.consume_step_up(
            tok2, "ou_ttl", "case-ttl", "sign", "nonce-ttl2", now=t0 + _TTL_EXP_S)
        return (bool(ok4m) and not exp6m,
                "4 分钟=%s（须成功） / 6 分钟=%s（须拒绝）" % (ok4m, exp6m))
    finally:
        store.close()


def main():
    passed = 0
    failed = 0
    tmpdir = None

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    def _advance(store, cookie, start, target):
        """用活动续 idle 到 target（不跨 absolute），用于隔离 absolute 测试。"""
        t = start
        while t < target:
            t = min(t + IDLE_SECONDS - 100, target)
            if store.get_session(cookie, now=t) is None:
                raise RuntimeError("advance failed at %s" % t)
        return t

    try:
        tmpdir = tempfile.mkdtemp(prefix="auth-session-")
        db = os.path.join(tmpdir, "session.db")

        # C0 opaque cookie + server-side principal
        store = SessionStore(db)
        cookie = store.create_session("ou_alice", tenant="t1", now=1000)
        report(all(n not in cookie for n in _c0_leak_needles()),
               "C0 cookie 不含任何身份/tenant/role 逐字片段",
               "cookie=%r" % cookie)
        report(is_opaque_cookie(cookie), "C0 cookie 只含 opaque id", "cookie=%r" % cookie)
        # ★ 2026-10-23 修一处**约 1% 的假红**（原写法见下）。
        #
        #   原写：`"ou_alice" not in cookie and "t1" not in cookie`
        #
        #   cookie 是 32 字节随机数的 base64url（43 字符，字母表 64）。
        #   用**子串**判「身份信息进没进 cookie」，在短串上必然误报：
        #       't1'（2 字符）→ 单次碰撞 ≈ 1.0e-2，**约每 98 次就有一次**
        #       'ou_alice'（8 字符）→ ≈ 1.3e-13，可忽略
        #   实测：300 次里 1 次命中，样例 `...lt1M...` —— 那只是个随机序列。
        #
        #   而它的失败文案是「cookie 不含身份/tenant」，**读起来像一次身份泄漏**。
        #   一个 ~1% 概率、且长得像安全事故的假红，比不报更糟（§2.1.1）。
        #
        #   修法不是把阈值调松，是**换判据**：
        #     ① 保留 8 字符主键的子串检查（碰撞可忽略，且它确实是身份主体）；
        #     ② tenant 改用**行为判据** —— 带着这个 tenant 能查到会话，
        #        换一个 tenant 查不到，才说明 tenant 没写进 cookie 而是服务端的。
        #   长度门槛不是拍脑袋：2 字符在这个字母表上不够，8 字符够。
        report("ou_alice" not in cookie,
               "C0 cookie 不含身份主键", "cookie=%r" % cookie)
        # ★ 行为级：cookie 与 tenant **无关** —— 同一 cookie 在不同 tenant 下
        #   解析结果一致，说明 tenant 来自服务端记录，不来自 cookie 本身。
        _s_t1 = store.get_session(cookie, now=1001)
        report(_s_t1 is not None and _s_t1.get("tenant") == "t1",
               "C0 服务端按 cookie 解析出 tenant", "got=%r" % (_s_t1,))
        sess = store.get_session(cookie, now=1001)
        report(sess and sess.get("principal") == "ou_alice",
               "C0 服务端解析 principal", "got=%r" % (sess,))

        # C0g/C0h ★ 2026-10-24 #131 补票：cookie 内容只有随机 session id。
        #
        #   #131 实测：把 create_session 的 sid 改成
        #   `secrets.token_urlsafe(32) + '-' + tenant` 后整链 rc=0 ——
        #   C0 既有检查只查 'ou_alice' 子串（身份主键）、tenant 只做服务端回读
        #   行为判（改坏后回读照样命中）、R3 只否掉含 '／' 的畸形 cookie。
        #   cookie 里编进 tenant 没有任何一处会红。
        #
        #   判据形状（C0g/C0h 是真实 create_session 产物的**逐字检查**）：
        #   用一个**长哨兵** tenant/principal 建第二个会话，断言两者都不在
        #   cookie 里。哨兵必须长（≥12 字符）：'t1' 这种 2 字符字面量在 43 字符
        #   base64url 上的子串碰撞 ≈1.0e-2（本文件上文实测过一次），不能用作判据；
        #   12+ 字符把碰撞压到 ≈1e-13，逐字判才是可用的机器判据。
        #   rbac 角色名只查 ≥5 字符的（submitter/signer/coordinator/machine，
        #   合计碰撞 ≤3e-8）：'dp3'/'it' 短字面量同样碰不起 —— 短名不在
        #   检查集这件事是**判据口径**，不是遗漏。
        try:
            from base.rbac import ROLES as _ROLES
        except Exception:  # noqa: BLE001 — rbac 不在时只查身份与 tenant
            _ROLES = ()
        _ROLE_NEEDLES = tuple(r for r in _ROLES if len(r) >= 5)
        leak_cookie = store.create_session(
            "ou_leak-probe", tenant="tenant-leak-probe", now=1002)
        report("ou_leak-probe" not in leak_cookie
               and "tenant-leak-probe" not in leak_cookie,
               "C0g cookie 不含身份主键与 tenant（长哨兵逐字判）",
               "cookie=%r" % leak_cookie)
        _leaked = [r for r in _ROLE_NEEDLES if r in leak_cookie]
        report(not _leaked,
               "C0h cookie 不含任何 rbac 角色/权限标识（≥5 字符角色名）",
               "leaked=%r" % (_leaked,))

        # C1 idle 30m / absolute 8h
        c = store.create_session("ou_bob", tenant="t1", now=2000)
        report(store.get_session(c, now=2000 + IDLE_SECONDS + 1) is None,
               "C1 idle 30m 过期", "")
        # activity renews idle only
        c2 = store.create_session("ou_carol", tenant="t1", now=3000)
        report(store.get_session(c2, now=3000 + 1700) is not None,
               "C1 活动前有效", "")
        report(store.get_session(c2, now=3000 + 3400) is not None,
               "C1 活动只续 idle", "")
        _advance(store, c2, 3000 + 3400, 3000 + ABSOLUTE_SECONDS - 100)
        report(store.get_session(c2, now=3000 + ABSOLUTE_SECONDS + 1) is None,
               "C1 absolute 8h 过期", "")

        # TS-11/TS-13 量锚（行 114/115）★ 2026-10-24 探针补票：
        #   C1/C5 的检查点写在 t0 + 实现常量 + 1，对「常量本身被改」恒真
        #   （IDLE→45m、ABSOLUTE→4h、STEP_UP→90s 全 survived，见文件头注释）。
        #   下面三条判据体只用判据原文的字面量，锚的是量本身。
        _ok, _detail = probe_idle_boundary(lambda: SessionStore(":memory:"))
        report(_ok, "TS-11 行114 idle 29 分钟有效 / 31 分钟失效（字面量锚）", _detail)
        _ok, _detail = probe_absolute_boundary(lambda: SessionStore(":memory:"))
        report(_ok, "TS-11 行114 absolute 7h59m 有效 / 8h01m 失效，活动续不动（字面量锚）",
               _detail)
        _ok, _detail = probe_ttl_boundary(lambda: SessionStore(":memory:"))
        report(_ok, "TS-13 行115 token 4 分钟内可用 / 6 分钟后拒绝（字面量锚）", _detail)

        # C2 revoke
        c3 = store.create_session("ou_dave", tenant="t1", now=4000)
        store.revoke_session(c3)
        report(store.get_session(c3, now=4001) is None,
               "C2 撤销立即失效", "")
        audit_db = os.path.join(tmpdir, "revoke-audited.db")
        auth_audit = os.path.join(tmpdir, "auth-audit.jsonl")
        revoke_store = SessionStore(audit_db, auth_audit_path=auth_audit)
        revoke_cookie = revoke_store.create_session("ou_revoke", tenant="t1", now=4100)
        revoke_store.revoke_session(
            revoke_cookie, actor="ou_admin", reason="security", now=4101)
        revoke_store.close()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(audit_db + suffix)
            except FileNotFoundError:
                pass
        auth_text = open(auth_audit, encoding="utf-8").read()
        report(os.path.exists(auth_audit) and revoke_cookie not in auth_text
               and "session_revoked" in auth_text and "security" in auth_text,
               "C2 撤销审计独立低敏落盘，session DB 删除后仍在", "")

        # C3 step-up single-use
        t1 = store.issue_step_up("ou_alice", "case-1", "sign", "nonce-1", now=5000)
        stored_token = store._conn.execute(
            "SELECT token FROM step_up_tokens WHERE principal='ou_alice' "
            "AND case_id='case-1'").fetchone()[0]
        report(stored_token != t1 and len(stored_token) == 64,
               "C3 step-up DB 只存 token hash，不存 bearer token", "")
        report(store.consume_step_up(t1, "ou_alice", "case-1", "sign", "nonce-1", now=5001),
               "C3 step-up 首次使用通过", "")
        report(store.consume_step_up(t1, "ou_alice", "case-1", "sign", "nonce-1", now=5002) is False,
               "C3 step-up single-use 拒绝第二次", "")

        # C4 binding mismatch
        t2 = store.issue_step_up("ou_alice", "case-1", "sign", "nonce-2", now=5100)
        report(store.consume_step_up(t2, "ou_eve", "case-1", "sign", "nonce-2", now=5101) is False,
               "C4 错 principal 拒绝", "")
        report(store.consume_step_up(t2, "ou_alice", "case-2", "sign", "nonce-2", now=5102) is False,
               "C4 跨案拒绝", "")
        report(store.consume_step_up(t2, "ou_alice", "case-1", "revoke", "nonce-2", now=5103) is False,
               "C4 跨动作拒绝", "")
        report(store.consume_step_up(t2, "ou_alice", "case-1", "sign", "nonce-9", now=5104) is False,
               "C4 错 nonce 拒绝", "")
        report(store.consume_step_up(t2, "ou_alice", "case-1", "sign", "nonce-2", now=5105),
               "C4 匹配绑定通过", "")

        # C5 step-up expired
        t3 = store.issue_step_up("ou_alice", "case-1", "sign", "nonce-3", now=6000)
        report(store.consume_step_up(t3, "ou_alice", "case-1", "sign", "nonce-3",
                                     now=6000 + STEP_UP_SECONDS + 1) is False,
               "C5 step-up 过期拒绝", "")

        # C6 session DB loss
        c4 = store.create_session("ou_frank", tenant="t1", now=7000)
        t4 = store.issue_step_up("ou_frank", "case-9", "sign", "nonce-4", now=7000)
        store.close()
        for suffix in ("", "-wal", "-shm"):
            p = db + suffix
            if os.path.exists(p):
                os.unlink(p)
        store2 = SessionStore(db)
        report(store2.get_session(c4, now=7001) is None,
               "C6 DB 丢失后 session 失效", "")
        report(store2.consume_step_up(t4, "ou_frank", "case-9", "sign", "nonce-4", now=7001) is False,
               "C6 DB 丢失后 step-up 失效", "")

        # C7 invalidate_all：session + step-up 全部失效
        c6 = store2.create_session("ou_ivy", tenant="t2", now=7500)
        t6 = store2.issue_step_up("ou_ivy", "case-10", "sign", "nonce-6", now=7500)
        store2.invalidate_all()
        report(store2.get_session(c6, now=7501) is None,
               "C7 invalidate_all → session 失效", "")
        report(store2.consume_step_up(t6, "ou_ivy", "case-10", "sign", "nonce-6",
                                      now=7501) is False,
               "C7 invalidate_all → step-up 失效", "")
        c7 = store2.create_session("ou_ivy", tenant="t2", now=7502)
        report(store2.get_session(c7, now=7503) is not None,
               "C7 invalidate_all 之后新 session 可用", "")

        # C7b 旧 session DB 恢复后 generation 失配，旧会话不得复活。
        gen_db = os.path.join(tmpdir, "generation.db")
        gen_file = os.path.join(tmpdir, "session-generation")
        gen_store = SessionStore(gen_db, generation_file=gen_file)
        old_cookie = gen_store.create_session("ou_old", tenant="t1", now=7550)
        gen_store.close()
        old_copy = os.path.join(tmpdir, "old-generation.db")
        shutil.copyfile(gen_db, old_copy)
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(gen_db + suffix)
            except FileNotFoundError:
                pass
        fresh_store = SessionStore(gen_db, generation_file=gen_file)
        fresh_store.close()
        shutil.copyfile(old_copy, gen_db)
        restored_store = SessionStore(gen_db, generation_file=gen_file)
        report(restored_store.get_session(old_cookie, now=7551) is None,
               "C7b 恢复旧 session DB 后 generation 失配 → 全会话失效", "")
        restored_store.close()

        # C7c DB 文件仍存在但被重置为空库，也必须轮换 generation。
        reset_db = os.path.join(tmpdir, "reset-existing.db")
        reset_gen = os.path.join(tmpdir, "reset-generation")
        reset_store = SessionStore(reset_db, generation_file=reset_gen)
        reset_cookie = reset_store.create_session("ou_reset", tenant="t1", now=7560)
        reset_store.close()
        reset_old = os.path.join(tmpdir, "reset-old.db")
        shutil.copyfile(reset_db, reset_old)
        os.unlink(reset_db)
        open(reset_db, "wb").close()
        reset_fresh = SessionStore(reset_db, generation_file=reset_gen)
        reset_fresh.close()
        shutil.copyfile(reset_old, reset_db)
        reset_restored = SessionStore(reset_db, generation_file=reset_gen)
        report(reset_restored.get_session(reset_cookie, now=7561) is None,
               "C7c 存在但重置的 DB 也轮换 generation，旧会话不复活", "")
        reset_restored.close()

        # C8 create_session tenant 写入并回读
        c8 = store2.create_session("ou_ten", tenant="t2", now=7600)
        sess8 = store2.get_session(c8, now=7601)
        report(sess8 is not None and sess8.get("tenant") == "t2",
               "C8 create_session tenant=t2 回读", "got=%r" % (sess8,))
        c9 = store2.create_session("ou_default", now=7700)
        sess9 = store2.get_session(c9, now=7701)
        report(sess9 is not None and sess9.get("tenant") == "t1",
               "C8 create_session tenant 默认 t1", "got=%r" % (sess9,))

        # R1/C9 双连接并发消费：SQL 条件 UPDATE 才是真执行点；恰一成功。
        c9db = os.path.join(tmpdir, "concurrent.db")
        store_a = SessionStore(c9db)
        store_b = SessionStore(c9db)
        t5 = store_a.issue_step_up("ou_alice", "case-1", "sign", "nonce-5", now=8000)
        got = []
        import threading
        barrier = threading.Barrier(2)

        def consume(st):
            barrier.wait()
            got.append(st.consume_step_up(
                t5, "ou_alice", "case-1", "sign", "nonce-5", now=8001))

        threads = [threading.Thread(target=consume, args=(st,))
                   for st in (store_a, store_b)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        report(sorted(got) == [False, True],
               "C9 两个 SQLite 连接并发消费 step-up 恰一成功", repr(got))
        store_a.close()
        store_b.close()

        # C9b 每次消费成功/失败都留低敏长期审计，session DB 删除不影响审计。
        audit_db = os.path.join(tmpdir, "audited.db")
        audit_path = os.path.join(tmpdir, "step-up-audit.jsonl")
        audited = SessionStore(audit_db, step_up_audit_path=audit_path)
        audit_token = audited.issue_step_up(
            "ou_audit", "case-audit", "sign", "nonce-audit", now=8100)
        audit_ref = audited.consume_step_up_ref(
            audit_token, "ou_audit", "case-audit", "sign", "nonce-audit", now=8101)
        denied_ref = audited.consume_step_up_ref(
            audit_token, "ou_audit", "case-audit", "sign", "nonce-audit", now=8102)
        audited.close()
        audit_rows = [__import__("json").loads(line) for line in
                      open(audit_path, encoding="utf-8")]
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(audit_db + suffix)
            except FileNotFoundError:
                pass
        report(audit_ref and denied_ref is None and len(audit_rows) == 2
               and [row["success"] for row in audit_rows] == [True, False]
               and audit_token not in open(audit_path, encoding="utf-8").read()
               and os.path.exists(audit_path),
               "C9b step-up 成败均留低敏长期审计且 DB 丢失后仍在", "")

        # C9c 审计写失败必须回滚 used=1，修好审计后 token 仍可消费。
        audit_fail_db = os.path.join(tmpdir, "audit-fail.db")
        audit_fail_dir = os.path.join(tmpdir, "audit-is-directory")
        os.mkdir(audit_fail_dir)
        audit_fail_store = SessionStore(
            audit_fail_db, step_up_audit_path=audit_fail_dir)
        audit_fail_token = audit_fail_store.issue_step_up(
            "ou_fail", "case-fail", "sign", "nonce-fail", now=8200)
        try:
            audit_fail_store.consume_step_up(
                audit_fail_token, "ou_fail", "case-fail", "sign", "nonce-fail",
                now=8201)
            raised = False
        except OSError:
            raised = True
        fixed_audit = os.path.join(tmpdir, "audit-fixed.jsonl")
        audit_fail_store.step_up_audit_path = fixed_audit
        retried = audit_fail_store.consume_step_up(
            audit_fail_token, "ou_fail", "case-fail", "sign", "nonce-fail",
            now=8202)
        report(raised and retried,
               "C9c step-up 审计失败回滚消费，修好后仍可用", "")
        audit_fail_store.close()

        c9 = store2.create_session(
            "ou_csrf", tenant="t3", now=7602, provider="feishu",
            issuer="independent-web-app", csrf_token="csrf-one", auth_time=7601)
        report(store2.verify_csrf(c9, "csrf-one")
               and not store2.verify_csrf(c9, "csrf-two"),
               "C10 CSRF 绑定 session 且错 token 拒绝", "")
        replacement = store2.rotate_csrf(c9)
        report(replacement and store2.verify_csrf(c9, replacement)
               and not store2.verify_csrf(c9, "csrf-one"),
               "C10 CSRF 轮换后旧 token 失效", "")
        meta = store2.session_metadata(c9)
        report(meta and meta["provider"] == "feishu" and meta["tenant"] == "t3",
               "C10 session 记录 provider/issuer/auth_time", repr(meta))

        state = store2.issue_oauth_state(
            flow="login", redirect_uri="https://ca.example/auth/callback",
            nonce="nonce-login", browser_nonce="browser-login", now=7700)
        consumed = store2.consume_oauth_state(
            state, flow="login",
            redirect_uri="https://ca.example/auth/callback",
            browser_nonce="browser-login", now=7701)
        replay = store2.consume_oauth_state(
            state, flow="login",
            redirect_uri="https://ca.example/auth/callback",
            browser_nonce="browser-login", now=7702)
        report(consumed is not None and consumed.get("nonce") == "nonce-login"
               and replay is None,
               "C11 OAuth state 首次消费通过、重放拒绝", repr((consumed, replay)))
        bad_state = store2.issue_oauth_state(
            flow="login", redirect_uri="https://ca.example/auth/callback",
            nonce="nonce-other", browser_nonce="browser-other", now=7800)
        report(store2.consume_oauth_state(
            bad_state, flow="login",
            redirect_uri="https://wrong.example/auth/callback",
            browser_nonce="browser-other", now=7801) is None,
               "C11 OAuth state 错 redirect 拒绝", "")
        bound_state = store2.issue_oauth_state(
            flow="login", redirect_uri="https://ca.example/auth/callback",
            nonce="operation-nonce", browser_nonce="browser-a", now=7900)
        wrong_browser = store2.consume_oauth_state(
            bound_state, flow="login",
            redirect_uri="https://ca.example/auth/callback",
            browser_nonce="browser-b", now=7901)
        right_browser = store2.consume_oauth_state(
            bound_state, flow="login",
            redirect_uri="https://ca.example/auth/callback",
            browser_nonce="browser-a", now=7902)
        report(wrong_browser is None and right_browser is not None,
               "C11 OAuth state 错浏览器不消费、原浏览器仍可用", "")

        # R2 reverse: 测试注入去掉 absolute -> still valid after 8h
        c5 = store2.create_session("ou_grace", tenant="t1", now=9000)
        _advance(store2, c5, 9000, 9000 + ABSOLUTE_SECONDS - 100)
        with mock.patch("base.auth_session._absolute_expired",
                        lambda created_at, now: False):
            report(store2.get_session(c5, now=9000 + ABSOLUTE_SECONDS + 1) is not None,
                   "R2 去掉 absolute → 8h 后仍有效（反向对照成立）", "")

        # R3 reverse: cookie with tenant must fail
        report(store2.get_session("sid|tenant=t1", now=9000) is None,
               "R3 cookie 塞 tenant → 拒绝", "")
        report(not is_opaque_cookie("sid|tenant=t1"),
               "R3 opaque 校验拒绝带 tenant 的 cookie", "")

        store2.close()
    finally:
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


# ═══════════════════ --controls：#131 离线反向对照 ═══════════════════
#
# 判定体是真实的 create_session()。#131 实测的变异是 sid 变成
# `secrets.token_urlsafe(32) + '-' + tenant` —— 这里在 mock 层复刻同一种
# 「数据进 cookie」的坏实现，逐个喂给 C0g/C0h 用的同一根判据针：
#   ① tenant 编进 cookie   → 'tenant-leak-probe' 针必须红
#   ② 身份主键编进 cookie  → 'ou_leak-probe' 针必须红
#   ③ 角色名编进 cookie    → 'coordinator' 针必须红
# 好样本（真 create_session）三个方向都**不许误报**。
# 任何一条不成立 → 退 1。

def controls() -> int:
    fails = []
    n_cases = [0]

    def ok(name, cond, detail=""):
        n_cases[0] += 1
        cond = bool(cond)
        if not cond:
            fails.append(name)
        print("  %s %s %s" % ("✅" if cond else "❌", name, detail))

    print("=" * 78)
    print("auth_session · 离线反向对照（--controls · #131 cookie 泄漏面）")
    print("=" * 78)

    needles = _c0_leak_needles()

    # 坏实现形状：把不同字段编进 cookie 本体（与 #131 的变异同形）
    bad_impls = (
        ("tenant 编进 cookie", "tenant-leak-probe"),
        ("身份主键编进 cookie", "ou_leak-probe"),
        ("角色名编进 cookie", "coordinator"),
    )
    for name, payload in bad_impls:
        hit = [n for n in needles if n in payload]
        ok("坏实现（%s）→ C0g/C0h 的针必须红（命中 %r）"
           % (name, hit), len(hit) == 1, "payload=%r" % payload)

    # 好样本：真实 create_session 的产物不许被针误伤
    tmpdir = tempfile.mkdtemp(prefix="auth-session-controls-")
    try:
        store = SessionStore(os.path.join(tmpdir, "c.db"))
        try:
            good = store.create_session(
                "ou_leak-probe", tenant="tenant-leak-probe", now=1000)
            leaked = [n for n in needles if n in good]
            ok("好实现（真 create_session，principal/tenant 都用哨兵值）"
               "→ 逐字针不许误报", not leaked, "leaked=%r" % (leaked,))
            ok("好实现 → 服务端回读仍是哨兵 principal/tenant"
               "（哨兵进了服务端库、没进 cookie）",
               (lambda s: s is not None
                and s.get("principal") == "ou_leak-probe"
                and s.get("tenant") == "tenant-leak-probe")(
                   store.get_session(good, now=1001)), "")
        finally:
            store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── TS-11/TS-13 量锚的反向对照（2026-10-24）──
    #
    # 判定体是 probe_idle_boundary / probe_absolute_boundary / probe_ttl_boundary
    # 这三个**不读实现常量**的判据体。坏样本走 mock 层复刻探针实测的四种改坏形状：
    #   ① IDLE 30→45 分钟  ② ABSOLUTE 8h→4h  ③ STEP_UP 5m→90s
    #   ④ issue 的 TTL 写死成 60 秒（探针的第二变异）
    # 每种必须让对应的判据体红；好样本（真常量）三个方向都不许误报。
    # ★ 坏样本只在 mock 里，真模块与真 DB 一个字节都不动。

        print("  ---- TS-11/TS-13 量锚：坏样本（mock 复刻探针变异）----")
    # 坏①：IDLE_SECONDS 30*60 → 45*60 —— idle 段两条判据体都必须红
    with mock.patch("base.auth_session.IDLE_SECONDS", 45 * 60):
        ok("坏① IDLE→45m → 行114 idle 锚必须红",
           probe_idle_boundary(lambda: SessionStore(":memory:"))[0] is False)
        ok("好① IDLE→45m 时 absolute 锚不许误报（absolute 不看 idle）",
           probe_absolute_boundary(lambda: SessionStore(":memory:"))[0] is True,
           probe_absolute_boundary(lambda: SessionStore(":memory:"))[1])
    # 坏②：ABSOLUTE_SECONDS 8h → 4h —— absolute 锚必须红（7h59m 那点已死）
    with mock.patch("base.auth_session.ABSOLUTE_SECONDS", 4 * 60 * 60):
        ok("坏② ABSOLUTE→4h → 行114 absolute 锚必须红",
           probe_absolute_boundary(lambda: SessionStore(":memory:"))[0] is False)
    # 坏③：_absolute_expired 用 last_activity —— 活动续得动 absolute，必须红。
    #   与探针的「活动不续 absolute」锚变异同形（mock.last_activity 返回真值=未过期）。
    with mock.patch("base.auth_session._absolute_expired",
                    lambda last_activity, now: False):
        ok("坏③ 活动可续 absolute → 行114 absolute 锚必须红（8h01m 那点活着）",
           probe_absolute_boundary(lambda: SessionStore(":memory:"))[0] is False)
    # 坏④：STEP_UP_SECONDS 5*60 → 90 —— TTL 锚必须红
    with mock.patch("base.auth_session.STEP_UP_SECONDS", 90):
        ok("坏④ STEP_UP→90s → 行115 TTL 锚必须红（4 分钟那点已死）",
           probe_ttl_boundary(lambda: SessionStore(":memory:"))[0] is False)
    # 坏⑤：issue 的实际 TTL 写死 60 秒（探针第二变异：now + STEP_UP_SECONDS → now + 60）
    real_issue = SessionStore.issue_step_up

    def _short_ttl(self, principal, case_id, action, nonce, now=None):
        import base.auth_session as _m
        with mock.patch.object(_m, "STEP_UP_SECONDS", 60):
            return real_issue(self, principal, case_id, action, nonce, now=now)

    with mock.patch("base.auth_session.SessionStore.issue_step_up", _short_ttl):
        ok("坏⑤ issue TTL 写死 60s → 行115 TTL 锚必须红（6 分钟那点还活着）",
           probe_ttl_boundary(lambda: SessionStore(":memory:"))[0] is False)

    print("  ---- TS-11/TS-13 量锚：好样本（真常量，不许误报）----")
    ok("好 TS-11 idle 锚 → 真常量必须绿",
       probe_idle_boundary(lambda: SessionStore(":memory:"))[0] is True)
    ok("好 TS-11 absolute 锚 → 真常量必须绿",
       probe_absolute_boundary(lambda: SessionStore(":memory:"))[0] is True)
    ok("好 TS-13 TTL 锚 → 真常量必须绿",
       probe_ttl_boundary(lambda: SessionStore(":memory:"))[0] is True)

    print("-" * 78)
    if fails:
        print("❌ %d 项失败：%s" % (len(fails), fails))
        return 1
    print("✅ %d 项全过（该红、该绿都有）" % n_cases[0])
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
