#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_auth_session.py — T0-07 切片 1：会话与 step-up

覆盖：
  C0 cookie 只含 opaque id，服务端可解析 principal
  C1 idle 30m / absolute 8h；活动只续 idle，不续 absolute
  C2 撤销立即失效
  C3 step-up TTL 5m、single-use、绑定 principal+case+action+nonce
  C4 跨案/跨动作/错 principal/错 nonce 拒绝
  C5 step-up 过期拒绝
  C6 session DB 丢失 → 全部 session + step-up 失效
  R1 去掉 single-use → 第二次使用必须被放行（反向对照）
  R2 去掉 absolute → 8h 后仍有效（反向对照）
  R3 cookie 塞 tenant → 必须红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
全部使用 mktemp 临时 SQLite，不碰真实 session DB。
"""

import os
import shutil
import sys
import tempfile

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
        report(is_opaque_cookie(cookie), "C0 cookie 只含 opaque id", "cookie=%r" % cookie)
        report("ou_alice" not in cookie and "t1" not in cookie,
               "C0 cookie 不含身份/tenant", "cookie=%r" % cookie)
        sess = store.get_session(cookie, now=1001)
        report(sess and sess.get("principal") == "ou_alice",
               "C0 服务端解析 principal", "got=%r" % (sess,))

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

        # C2 revoke
        c3 = store.create_session("ou_dave", tenant="t1", now=4000)
        store.revoke_session(c3)
        report(store.get_session(c3, now=4001) is None,
               "C2 撤销立即失效", "")

        # C3 step-up single-use
        t1 = store.issue_step_up("ou_alice", "case-1", "sign", "nonce-1", now=5000)
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

        # R1 reverse: no single-use -> second use allowed
        t5 = store2.issue_step_up("ou_alice", "case-1", "sign", "nonce-5", now=8000)
        store2.consume_step_up(t5, "ou_alice", "case-1", "sign", "nonce-5", now=8001)
        report(store2.consume_step_up(t5, "ou_alice", "case-1", "sign", "nonce-5",
                                      now=8002, bad_mode="no_single_use"),
               "R1 去掉 single-use → 第二次被放行（反向对照成立）", "")

        # R2 reverse: no absolute -> still valid after 8h
        c5 = store2.create_session("ou_grace", tenant="t1", now=9000)
        _advance(store2, c5, 9000, 9000 + ABSOLUTE_SECONDS - 100)
        report(store2.get_session(c5, now=9000 + ABSOLUTE_SECONDS + 1,
                                  bad_mode="no_absolute") is not None,
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


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
