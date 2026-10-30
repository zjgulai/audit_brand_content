#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_principal_auto.py — 自动登记（「放行所有人员飞书登录」）的判据。

## 它守的是什么

2026-10-30 委托方要求「我要放行所有人员的飞书登陆」。原状是登录必须
`principals.json` 里先有你的 open_id，否则 `403 principal_not_authorized`
—— 实测刘华丽（`ou_af95e2a4…`）就卡在这里。

当时有两条路，选的是**加一层自动登记**而不是「把全公司逐人抄进 JSON」：
后者每来一个人就要改一次只读挂载文件 + 人工对齐 open_id，而 open_id
靠人抄必然出错，出错了症状又与「没登记」完全一样。

## 三条规则，每条都要有反向对照

| # | 规则 | 不加会怎样 |
|---|---|---|
| 1 | 显式层优先，**且显式 revoked 不许被自动复活** | 撤人 = 撤了个寂寞，他来扫一次码就回来了 |
| 2 | 自动层不许给 signer / it / machine | 一次「方便登录」顺手把签发权和平台管理散给全租户 |
| 3 | 没配 = 关，行为与加这一层之前逐字相同 | 既有部署在升级那一刻悄悄开了口子 |

★ 三态：`0` 通过 / `1` 有红 / `2` 未测。**未测 ≠ 通过。**

## 它验的那两个主体（逐字点名，`verify_coverage.py` 的 C 段据此对账）

- `base/principal_directory.py` —— 两层名单（显式 / 自动）、三条规则、落盘与审计
- `api/production_app.py` —— `REVIEW_PRINCIPAL_AUTO_GRANT` +
  `REVIEW_PRINCIPAL_DIRECTORY_AUTO` 两个开关，以及 `/auth/callback` 里那一跳

复现：`python3 tools/verify_principal_auto.py`
反向对照：`python3 tools/verify_principal_auto.py --controls`
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base.principal_directory import (  # noqa: E402
    AUTO_FORBIDDEN_ROLES, PrincipalDirectory, PrincipalDirectoryError)

PASSED: list[str] = []
FAILED: list[str] = []
UNMEASURED: list[str] = []


def ok(name, detail=""):
    PASSED.append("%s %s" % (name, detail))


def bad(name, detail=""):
    FAILED.append("%s %s" % (name, detail))


def untested(name, why):
    UNMEASURED.append("%s [未测] %s" % (name, why))


def check(name, cond, detail=""):
    (ok if cond else bad)(name, detail)
    return bool(cond)


class Fixture:
    def __init__(self, tmp, *, explicit=(), auto_grant=None):
        self.tmp = tmp
        self.explicit_path = os.path.join(tmp, "principals.json")
        self.auto_path = os.path.join(tmp, "principals-auto.json")
        self.audit_path = os.path.join(tmp, "audit.jsonl")
        with open(self.explicit_path, "w", encoding="utf-8") as fh:
            json.dump({"principals": list(explicit)}, fh, ensure_ascii=False)
        self.auto_grant = auto_grant

    def open(self, **kw):
        return PrincipalDirectory(
            self.explicit_path,
            auto_grant=kw.pop("auto_grant", self.auto_grant),
            auto_store_path=kw.pop("auto_store_path", self.auto_path),
            audit_path=kw.pop("audit_path", self.audit_path),
            **kw)


def _row(pid, open_id, **over):
    row = {"id": pid, "tenant_id": "t1", "open_id": open_id,
           "roles": ["dp3"], "product_lines": ["吸奶器"],
           "capabilities": ["case.review"], "product_line": "吸奶器",
           "authz_version": "v1"}
    row.update(over)
    return row


GRANT = {"roles": ["dp3"], "product_lines": ["吸奶器"]}


# ── A 组：三条规则的正向 ────────────────────────────────────────────────────
def group_a(tmp):
    def t(fn):
        d = tempfile.mkdtemp(dir=tmp)
        try:
            fn(d)
        except Exception:  # noqa: BLE001
            bad("A-异常", "%s\n%s" % (fn.__name__,
                                     traceback.format_exc(limit=2)))

    def a1(d):
        fx = Fixture(d, explicit=[_row("u-explicit", "ou_ex")], auto_grant=GRANT)
        pd = fx.open()
        row = pd.by_identity("t1", "ou_ex")
        check("A1 显式层命中时用显式那条",
              row and row["id"] == "u-explicit" and row["source"] == "explicit",
              repr(row and (row["id"], row["source"])))

    def a2(d):
        fx = Fixture(d, explicit=[_row("u-rev", "ou_rev", status="revoked")],
                     auto_grant=GRANT)
        pd = fx.open()
        row = pd.by_identity("t1", "ou_rev")
        check("A2 ★ 显式 revoked 不被自动登记复活", row is None, repr(row))
        # 反向对照：同样的目录，去掉那条 revoked（换成不认识的人）→ 必被登记。
        # 没有这一条，A2 在「自动登记整个没生效」时也恒真。
        row2 = pd.by_identity("t1", "ou_other")
        check("A2b 反向对照：换个人同样的目录就必须被自动登记",
              row2 is not None and row2["source"] == "auto", repr(row2))

    def a3(d):
        fx = Fixture(d, auto_grant=GRANT)
        pd = fx.open()
        check("A3 显式表为空时 ready() 仍为真（全员扫码即进的常态）",
              pd.ready() is True)
        row = pd.by_identity("t1", "ou_newone", "刘华丽")
        check("A3b 陌生 open_id 被自动登记且拿到配置的角色",
              row is not None and row["roles"] == ["dp3"]
              and row["product_lines"] == ["吸奶器"],
              repr(row and (row["roles"], row["product_lines"])))
        check("A3c 能力由角色矩阵推导，不是配置里抄的",
              row is not None and row["capabilities"]
              == ["appeal.handle", "case.review"],
              repr(row and row["capabilities"]))
        check("A3d 姓名只留痕、进记录",
              row is not None and row.get("name") == "刘华丽",
              repr(row and row.get("name")))

    def a3e(d):
        # ★★ 生产形状用的是 require_authz_version=True，本地那一支覆盖不到
        #   （缺字段时本地会自动补算，生产直接拒）。2026-10-30 实测踩过：
        #   第一个真人扫码就 500 principal_field: authz_version。
        fx = Fixture(d, auto_grant=GRANT)
        pd = fx.open(require_authz_version=True)
        try:
            row = pd.by_identity("t1", "ou_strict", "刘华丽")
        except PrincipalDirectoryError as exc:
            bad("A3e ★ 生产形状 require_authz_version=True 下也必须能自动登记",
                "实际 code=%r —— 本地 False 那一支覆盖不到这一条" % (exc.code,))
            return
        except Exception as exc:  # noqa: BLE001
            bad("A3e ★ 生产形状 require_authz_version=True 下也必须能自动登记",
                repr(exc))
            return
        check("A3e ★ 生产形状 require_authz_version=True 下也能自动登记",
              row is not None and row["authz_version"])
        # 反向对照：同样形状下，缺 authz_version 的显式记录仍必须被拒
        # （不许为了「让人能进」把这条校验放松掉）
        fx2 = Fixture(d, explicit=[{"id": "u-nover", "tenant_id": "t1",
                                    "open_id": "ou_nover", "roles": ["dp3"],
                                    "product_lines": ["吸奶器"]}])
        try:
            fx2.open(require_authz_version=True)
        except PrincipalDirectoryError as exc:
            check("A3f ★ 反向对照：显式记录缺 authz_version 仍然被拒（校验没被放松）",
                  exc.code == "principal_field", "实际 code=%r" % (exc.code,))
        except Exception as exc:  # noqa: BLE001
            bad("A3f ★ 反向对照：显式记录缺 authz_version 仍然被拒", repr(exc))
        else:
            bad("A3f ★ 反向对照：显式记录缺 authz_version 仍然被拒", "被接受了")

    def a4(d):
        fx = Fixture(d, auto_grant=GRANT)
        pd = fx.open()
        row = pd.by_identity("t1", "ou_newone")
        back = pd.by_id(row["id"], "t1")
        check("A4 ★ by_id 也查得到自动层（否则登录成功、之后每个请求都 401）",
              back is not None and back["id"] == row["id"],
              repr(back and back["id"]))
        check("A4b 自动层的人可作为案件合格领取人",
              pd.eligible_assignee(row["id"], {"tenant": "t1",
                                              "product_line": "吸奶器"}) is True)
        check("A4c ★ 品线不匹配时不许领（自动登记不是通配）",
              pd.eligible_assignee(row["id"], {"tenant": "t1",
                                              "product_line": "喂养"}) is False)

    def a5(d):
        fx = Fixture(d, auto_grant=GRANT)
        pd = fx.open()
        row = pd.by_identity("t1", "ou_persist")
        on_disk = json.load(open(fx.auto_path, encoding="utf-8"))
        check("A5 ★ 登记立刻落盘（重启后还认得他）",
              [r["open_id"] for r in on_disk["principals"]] == ["ou_persist"],
              repr([r["open_id"] for r in on_disk["principals"]]))
        check("A5b 落盘文件权限 0600（里面有 open_id，属个人信息）",
              (os.stat(fx.auto_path).st_mode & 0o777) == 0o600,
              oct(os.stat(fx.auto_path).st_mode & 0o777))
        audit = [json.loads(x) for x in
                 open(fx.audit_path, encoding="utf-8").read().splitlines() if x]
        check("A5c 留痕一行，且 ok=true",
              len(audit) == 1 and audit[0].get("ok") is True
              and audit[0].get("open_id") == "ou_persist", repr(audit))
        # 重启：新目录对象读同一份盘
        pd2 = fx.open()
        again = pd2.by_identity("t1", "ou_persist")
        check("A5d ★ 重启后同一个人仍是同一条记录（id 稳定，不重复登记）",
              again is not None and again["id"] == row["id"],
              repr(again and again["id"]))

    def a6(d):
        # 并发首登：两次都写，不该丢任何一条
        fx = Fixture(d, auto_grant=GRANT)
        pd = fx.open()
        pd.by_identity("t1", "ou_a")
        pd.by_identity("t1", "ou_b")
        names = sorted(r["open_id"] for r in
                       json.load(open(fx.auto_path, encoding="utf-8"))["principals"])
        check("A6 ★ 连续两个陌生人首登，两条都在盘上（没有互相覆盖）",
              names == ["ou_a", "ou_b"], repr(names))

    def a7(d):
        # 落盘路径不可写：**构造期**就要拒，不许等到第一个陌生人扫码时才炸
        fx = Fixture(d, auto_grant=GRANT)
        blocked = os.path.join(d, "blocked")
        open(blocked, "w").close()  # 用文件占住目录名 → mkdir 必失败
        try:
            PrincipalDirectory(
                fx.explicit_path, auto_grant=GRANT,
                auto_store_path=os.path.join(blocked, "principals-auto.json"),
                audit_path=fx.audit_path)
        except PrincipalDirectoryError as exc:
            check("A7 ★ 落盘目录不可写 → 构造期就拒（不是等真人扫码时才 500）",
                  exc.code == "principal_auto_store_unwritable",
                  "实际 code=%r" % (exc.code,))
        except Exception as exc:  # noqa: BLE001
            bad("A7 ★ 落盘目录不可写 → 构造期就拒", repr(exc))
        else:
            bad("A7 ★ 落盘目录不可写 → 构造期就拒", "构造成功了，故障会被推到扫码那一刻")

        # 运行期真写不进去（构造之后目录被改坏）：必须**抛**，不许静默放行
        # ★ 只把**落盘目录**改坏，审计目录保持可写 —— 否则 A7c 测不到
        #   （两个文件同目录时，一句 chmod 就同时证明了「写不进」和「留不了痕」，
        #   而后者是另一件事：审计写不进去本身就是允许的）。
        d2 = tempfile.mkdtemp(dir=d)
        store_dir = os.path.join(d2, "store")
        os.makedirs(store_dir)
        fx2 = Fixture(d2, auto_grant=GRANT)
        pd = PrincipalDirectory(
            fx2.explicit_path, auto_grant=GRANT,
            auto_store_path=os.path.join(store_dir, "principals-auto.json"),
            audit_path=fx2.audit_path)
        os.chmod(store_dir, 0o500)
        try:
            pd.by_identity("t1", "ou_nodisk")
        except PrincipalDirectoryError as exc:
            check("A7b ★ 运行期写不进去 → 抛，不许「登录成功但盘上没记」",
                  exc.code == "principal_auto_store_unwritable",
                  "实际 code=%r" % (exc.code,))
        except Exception as exc:  # noqa: BLE001
            bad("A7b ★ 运行期写不进去 → 抛", repr(exc))
        else:
            bad("A7b ★ 运行期写不进去 → 抛", "被静默放行了 —— 重启后他就进不来，且没人知道为什么")
        finally:
            os.chmod(store_dir, 0o700)
        audit = [json.loads(x) for x in
                 open(fx2.audit_path, encoding="utf-8").read().splitlines() if x]
        check("A7c 写失败也要留痕 ok=false（抛之外再留一条可查的）",
              audit and audit[-1].get("ok") is False and audit[-1].get("error"),
              repr(audit))
        # 反向对照：目录恢复可写之后，同一个人必须登记成功
        row = pd.by_identity("t1", "ou_nodisk")
        check("A7d ★ 反向对照：目录修好后必须真的记上（A7b 不是「永远抛」）",
              row is not None and os.path.exists(
                  os.path.join(store_dir, "principals-auto.json")),
              repr(row and row["id"]))

    for fn in (a1, a2, a3, a3e, a4, a5, a6, a7):
        t(fn)


# ── B 组：配置校验（规则 2）────────────────────────────────────────────────
def group_b(tmp):
    def expect_reject(name, cfg, code_prefix, **kw):
        d = tempfile.mkdtemp(dir=tmp)
        fx = Fixture(d)
        try:
            if kw.get("open_only_grant"):
                PrincipalDirectory(fx.explicit_path, auto_grant=cfg)
            else:
                fx.open(auto_grant=cfg)
        except PrincipalDirectoryError as exc:
            check(name, str(exc.code).startswith(code_prefix),
                  "实际 code=%r" % (exc.code,))
        except Exception as exc:  # noqa: BLE001
            bad(name, "抛的不是 PrincipalDirectoryError：%r" % (exc,))
        else:
            bad(name, "坏配置被接受了")

    for role in sorted(AUTO_FORBIDDEN_ROLES):
        expect_reject("B1 ★ 自动登记不许给 %r" % role,
                      {"roles": ["dp3", role], "product_lines": ["吸奶器"]},
                      "principal_auto_grant_role_forbidden")
    d = tempfile.mkdtemp(dir=tmp)
    fx = Fixture(d)
    try:
        fx.open(auto_grant={"roles": ["dp4"], "product_lines": ["吸奶器"]})
        ok("B1b ★ 反向对照：dp4 的模板必须被接受（B1 不是「什么都拒」）")
    except Exception as exc:  # noqa: BLE001
        bad("B1b ★ 反向对照：dp4 的模板必须被接受", repr(exc))

    expect_reject("B2 空品线不许当通配",
                  {"roles": ["dp3"], "product_lines": []},
                  "principal_auto_grant_product_lines")
    expect_reject("B3 未知角色拒绝",
                  {"roles": ["admin"], "product_lines": ["吸奶器"]},
                  "principal_auto_grant_role_unknown")
    expect_reject("B4 ★ capabilities 与角色推导不一致时拒绝（防「以为给了、实际没给」）",
                  {"roles": ["dp3"], "product_lines": ["吸奶器"],
                   "capabilities": ["release.sign"]},
                  "principal_auto_grant_capabilities_mismatch")
    expect_reject("B5 拼错的键拒绝（role 而非 roles）",
                  {"role": ["dp3"], "product_lines": ["吸奶器"]},
                  "principal_auto_grant_unknown_key")
    expect_reject("B6 ★ 开了自动登记却没给落盘路径 → 拒绝",
                  {"roles": ["dp3"], "product_lines": ["吸奶器"]},
                  "principal_auto_store_missing", open_only_grant=True)


# ── C 组：没配 = 关（规则 3）───────────────────────────────────────────────
def group_c(tmp):
    d = tempfile.mkdtemp(dir=tmp)
    fx = Fixture(d, explicit=[_row("u-explicit", "ou_ex")])
    pd = PrincipalDirectory(fx.explicit_path)  # 不开自动
    check("C1 没配自动登记 → 陌生人一律 None（与加这一层之前逐字相同）",
          pd.by_identity("t1", "ou_stranger") is None)

    # C3：主应用层的开关 —— 两件都给才开
    try:
        import api.production_app as P
    except ModuleNotFoundError as exc:
        # ★ 缺 fastapi 是**测法错**，不是被测代码错（验收报告 §附 同一条）。
        #   自动换成项目 venv 重跑自己一次，而不是落「未测」——
        #   否则这个 verifier 在系统 python3 下永远退 2，等于没人跑得动它。
        if exc.name == "fastapi" and not os.environ.get("_VPA_REEXEC"):
            return _reexec(tmp)
        untested("C3 生产配置读取", "import 失败：%r" % (exc,))
        return
    except Exception as exc:  # noqa: BLE001
        untested("C3 生产配置读取", "import 失败：%r" % (exc,))
        return
    check("C3 ★ REVIEW_PRINCIPAL_AUTO_GRANT 未配 → None（默认关）",
          P._auto_grant_from_env({}) is None)
    got = P._auto_grant_from_env(
        {"REVIEW_PRINCIPAL_AUTO_GRANT": json.dumps(GRANT, ensure_ascii=False)})
    check("C3b 配了就原样读出来（校验只在 PrincipalDirectory 里做一次）",
          got == GRANT, repr(got))
    try:
        P._auto_grant_from_env({"REVIEW_PRINCIPAL_AUTO_GRANT": "{不是 json"})
    except P.SettingsError as exc:
        ok("C3c 坏 JSON 在构造期就拒（不静默当成没配）", str(exc))
    except Exception as exc:  # noqa: BLE001
        bad("C3c 坏 JSON 在构造期就拒（不静默当成没配）", repr(exc))
    else:
        bad("C3c 坏 JSON 在构造期就拒（不静默当成没配）", "被接受了")


def _reexec(tmp):
    """用项目 venv 重跑自己一次（只在「系统 python3 缺 fastapi」时走这条）。

    ★ 不许静默跳过：这条路径本身要**说出来**。既报一行提示，
      也把子进程的退出码带回来 —— 否则「重跑失败」会表现成「0 项通过」。
    ★ 用 `_VPA_REEXEC` 防递归：venv 里再缺 fastapi 就落未测，
      不会无限自我 exec。
    """
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("· 系统解释器缺 fastapi，改用项目 venv 重跑（测法修正，不是被测代码问题）")
    env = dict(os.environ, _VPA_REEXEC="1")
    try:
        proc = subprocess.run(
            ["uv", "run", "--no-sync", "python", os.path.abspath(__file__)],
            cwd=root, env=env)
    except OSError as exc:
        untested("C3 生产配置读取", "venv 重跑失败：%r" % (exc,))
        return 2
    if proc.returncode == 0:
        # 子进程已经把全套跑完了，这里不重复打印（它自己的输出在上面）。
        sys.exit(0)
    untested("C3 生产配置读取",
             "venv 下仍未能读取生产配置（子进程 rc=%d）" % proc.returncode)
    return proc.returncode or 2


def group_c2(tmp):
    d = tempfile.mkdtemp(dir=tmp)
    p = os.path.join(d, "empty.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"principals": []}, fh)
    check("C2 没配自动登记 → 显式表为空时 ready() 为假（旧口径不变）",
          PrincipalDirectory(p).ready() is False)


# ── D 组：与既有纪律的一致性 ────────────────────────────────────────────────
def group_d(tmp):
    d = tempfile.mkdtemp(dir=tmp)
    fx = Fixture(d, auto_grant=GRANT)
    pd = fx.open()
    row = pd.by_identity("t1", "ou_d")
    check("D1 ★ 自动登记的角色里没有 signer / it / machine",
          not (set(row["roles"]) & AUTO_FORBIDDEN_ROLES), repr(row["roles"]))
    check("D2 ★ 自动登记的能力里没有签发/下线/授权（那三条走人级名单或平台角色）",
          not (set(row["capabilities"]) &
               {"release.sign", "release.revoke",
                "takedown.execute", "takedown.waive",
                "admin.grant.execute", "admin.grant.approve"}),
          repr(row["capabilities"]))
    check("D3 自动登记的 authz_version 是稳定字符串（不是随机值）",
          isinstance(row.get("authz_version"), str) and row["authz_version"],
          repr(row.get("authz_version")))
    same = fx.open().by_identity("t1", "ou_d")
    check("D4 ★ 同一个人再取一次，authz_version 不变"
          "（变了会让已登录的人立刻被判「授权已变化」）",
          same["authz_version"] == row["authz_version"],
          "%r vs %r" % (row["authz_version"], same["authz_version"]))


def main():
    tmp = tempfile.mkdtemp(prefix="verify-principal-auto-")
    try:
        group_a(tmp)
        group_b(tmp)
        group_c(tmp)
        group_c2(tmp)
        group_d(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 68)
    print("自动登记（放行全员飞书登录）· 自证")
    print("=" * 68)
    for line in PASSED:
        print("PASS:", line)
    for line in FAILED:
        print("FAIL:", line)
    for line in UNMEASURED:
        print("UNTESTED:", line)
    print("-" * 68)
    if FAILED:
        print("❌ %d 红 / %d 通过 / %d 未测" %
              (len(FAILED), len(PASSED), len(UNMEASURED)))
        return 1
    if UNMEASURED:
        print("⚠ %d 项未测 / %d 通过 —— 未测不是通过" %
              (len(UNMEASURED), len(PASSED)))
        return 2
    print("✅ %d 项全过" % len(PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
