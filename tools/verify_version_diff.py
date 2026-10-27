#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_version_diff.py — T-454 两版比对端点的执行点

## 它守的是什么

`base/change_detect.py`（判据 `claim-set-v1`）早就有三值结论与自证（16 项），
但它一直是**分析侧的工具** —— `tools/lp_stability.py` 和 `tools/verify_landing.py`
在用，生产链路一次都没调过。T-454 把它接进 `POST /api/v1/version-diff`。

这个文件守三件不同的事，缺一件这一票就没做成：

| 组 | 守什么 | 为什么它不能由别的自证代做 |
|---|---|---|
| A/B 三值 | 三值结论不许互相混 | `change_detect` 自己的自证测的是**函数**，不是端点 |
| C 端点口径 | 端点返回的结论与 `change_detect` **逐字相同** | 防止端点里「顺手改写一下措辞」，那会让两处口径分叉 |
| D ★ 不写 | 真跑两次，authority 的案件数/报告数一个没变 | 「只读」是一句声明；**数得出来才算数** |
| E 反向对照 | 每个判据喂坏样本必须红、好样本必须绿 | §2.4.1 |

## ★ 为什么 D 组是这一票最重要的地方

`POST` 在 S8 那条判据里等于「写端点」，而这条端点其实只读。豁免它的理由
写在 `verify_openapi_spec.py` 的 `READONLY_POST_ALLOWED` 注释里，但**理由不是证据**。
D 组真跑请求、真数 state —— 若哪天有人在里面加了 `authority.apply(...)`，
D1/D2 立刻红。

## 已知边界（写在这里，因为不说就等于隐瞒）

声明词表**只有英文**（`medical` 只认 `hospital-grade` / `clinically` 这类），
中文「治疗堵奶」抽不出来。所以本文件的用例**全部用英文样本** ——
用中文样本会「绿」，而那绿是假的（它其实什么都没抽到，只是恰好两边都空）。
中文词表属判定规则内容，另票处理。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


# ─────────────────────────────────────────────────────── 夹具

#: 三组样本。★ 全部用**英文**声明词 —— 中文抽不到（见文件头「已知边界」）。
#: 如果这里换成中文，三条断言会「绿」，但那个绿是「两边都抽到空集」的假绿。
CASE_SAME = ("hospital-grade pump, 30% faster", "hospital-grade pump, 30% faster")
CASE_MOVED = ("hospital-grade pump", "hospital-grade pump, 30% faster")
CASE_CHANGED = ("hospital-grade pump", "clinically proven pump")


def _app():
    """建一个 dev 装配 + 一个登录会话。返回 (app, token, repo)。"""
    from api.review_api import create_app
    from base.auth_session import SessionStore

    class _Repo:
        def __init__(self):
            self.cases = []
            self.reports = []
            self.appeals = []
            self.metrics = {}

        def get_case(self, case_id):
            return next((c for c in self.cases if c.get("case_id") == case_id), None)

        def list_cases(self):
            return list(self.cases)

        def list_reports(self):
            return list(self.reports)

        def get_report(self, report_id):
            return next((r for r in self.reports if r.get("report_id") == report_id), None)

    principals = {"u_vd": {"open_id": "ou_vd", "tenant_id": "t1",
                           "roles": ["coordinator"], "product_lines": ["pump"]}}
    store = SessionStore(":memory:")
    token = store.create_session("u_vd", tenant="t1", now=time.time())
    repo = _Repo()
    app = create_app(session_store=store, repository=repo, principals=principals)
    return app, token, repo


def _post(app, cookie, old, new):
    """按仓内既有约定发一次 POST（`body` 必须是 bytes，不是 dict）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_vra_helper", str(ROOT / "tools" / "verify_review_api.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    body = json.dumps({"old_text": old, "new_text": new}).encode("utf-8")
    return mod.call(app, "POST", "/api/v1/version-diff", cookie=cookie, body=body)


# ─────────────────────────────────────────────────────── A 三值

def group_a():
    try:
        from base import change_detect as CD
    except Exception as exc:  # noqa: BLE001
        untested("A 组", "change_detect 导入失败：%s" % (exc,))
        return

    same = CD.judge(*CASE_SAME)
    moved = CD.judge(*CASE_MOVED)
    changed = CD.judge(*CASE_CHANGED)

    report(same["结论"] == CD.V_SAME,
           "A1 逐字节相同 → ① 同一版正文", same["结论"])
    report(moved["结论"] == CD.V_NEW_NO_CLAIM,
           "A2 ★ 换版但声明未变 → ②（把噪声滤掉的就是这一档）", moved["结论"])
    report(changed["结论"] == CD.V_NEW_CLAIM,
           "A3 ★ 声明已变 → ③", changed["结论"])
    report(len({same["结论"], moved["结论"], changed["结论"]}) == 3,
           "A4 ★★ 三个结论互不相同（不许混成一档）",
           repr(sorted({same["结论"], moved["结论"], changed["结论"]})))
    report(changed["是否触及合规表述"] is True
           and same["是否触及合规表述"] is False
           and moved["是否触及合规表述"] is False,
           "A5 「是否触及合规表述」与三值一致")

    # ★ 判定必须能说出「用哪套词形判的」，否则词表改了旧结论无法复算
    src = same.get("词形来源") or {}
    report(src.get("判据") == "claim-set-v1" and src.get("指纹"),
           "A6 结果带判据名与词表指纹（结论离开判据就没意义）",
           repr((src.get("判据"), str(src.get("指纹"))[:12])))


# ─────────────────────────────────────────────────────── B 反向对照（判据层）

def group_b():
    """★★ 这几条是「判据不会撒谎」的核心，全部是反向的。"""
    try:
        from base import change_detect as CD
    except Exception as exc:  # noqa: BLE001
        untested("B 组", str(exc))
        return

    # B1 两次完全相同的文本 → 必须判「同版」，不许因"调用时间不同"就判「已变」
    r = CD.judge("hospital-grade pump", "hospital-grade pump")
    report(r["结论"] == CD.V_SAME and r["是否触及合规表述"] is False,
           "B1 ★★★ 两次完全相同的文本必须判「同版」（不许因时间不同判已变）",
           r["结论"])

    # B2 空词表必须被拒绝 —— 否则每条都判「声明未变」，一个恒假的判据
    try:
        CD.judge("a", "b", claims={})
        report(False, "B2 ★★★ 空词表必须报错（否则每条都判「声明未变」）")
    except ValueError as exc:
        report("词形表为空" in str(exc),
               "B2 ★★★ 空词表报错并点名（一个恒假的判据不许存在）",
               str(exc)[:44])

    # B3 结论里的差集是「几个词」，不是整段正文
    r2 = CD.judge("hospital-grade pump", "clinically proven pump")
    keys = set(r2.get("消失的声明") or {}) | set(r2.get("新增的声明") or {})
    report(r2["差集词数"] >= 1 and all(
        isinstance(v, list) for v in
        list((r2.get("消失的声明") or {}).values())
        + list((r2.get("新增的声明") or {}).values())),
        "B3 ★ 差集是可数个词，不是 17,585 字符的整段",
        "差集词数=%r" % (r2.get("差集词数"),))


# ─────────────────────────────────────────────────────── C 端点口径

def group_c(app, cookie):
    from base import change_detect as CD

    for name, (old, new), want in (
            ("同版", CASE_SAME, CD.V_SAME),
            ("换版未变", CASE_MOVED, CD.V_NEW_NO_CLAIM),
            ("声明已变", CASE_CHANGED, CD.V_NEW_CLAIM)):
        st, body = _post(app, cookie, old, new)
        body = body or {}
        report(st == 200 and body.get("结论") == want,
               "C1 端点 %s → %s" % (name, want), "%s %r" % (st, body.get("结论")))
        # ★ 端点必须**原样转发**判据的结果，不许自己改写措辞。
        #   ★★ 用 `_same_as_local()` 而不是在这里重写一遍比较 ——
        #     重写一遍的话，E 组证的是「另一个函数的灵敏度」，与本条无关。
        local = CD.judge(old, new)
        report(_same_as_local(body, local),
               "C2 ★★ 端点结论与 change_detect 逐字相同（两处口径不许分叉）",
               repr(body.get("判据")))

    # C3 未登录 → 401（不是 200，也不是 500）
    st, _ = _post(app, None, *CASE_SAME)
    report(st == 401, "C3 未登录 → 401", repr(st))

    # C4 缺字段 → 422（不是 500）
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_vra2", str(ROOT / "tools" / "verify_review_api.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    st, _ = mod.call(app, "POST", "/api/v1/version-diff", cookie=cookie,
                     body=json.dumps({"old_text": "x"}).encode("utf-8"))
    report(st == 422, "C4 缺 new_text → 422（说清是请求坏了，不是服务坏了）", repr(st))


# ─────────────────────────────────────────────────────── D ★ 不写

def group_d(app, cookie, repo):
    """★★★ 这一组的全部内容：**证明这条端点没有写，而且这个证明抓得住写**。

    ★ 第一版写错了，记在这里因为它是最容易犯的错：
      当时的断言是 `len(repo.cases) == before_cases`，而仓库是空的 ——
      读数 `0 → 0`。**一个空仓库不管调用什么都不会变**，
      这条断言对任何实现都恒真，等于什么都没测（§2.4）。

      修法分两步，缺一步都还是恒真：
      ① **先往仓库里放东西**（有案件、有报告）—— 让「不变」成为一个可能的失败；
      ② **正向对照**：先证明这个计数器**会动**（读接口一次就 +N），
         再看 version-diff 一次都不动它。只做①，计数器坏掉时照样绿。

    ★ 判据从「条数」升级成「**一个 repo 方法都没被调用过**」：
      条数不变只能说"没增加"，而直接 `repo.cases.clear()` 或改一个字段
      都不会让条数变。调用次数为 0 是更强的陈述，且同样可证伪（见正向对照）。
    """
    from base import change_detect as CD

    # ① 先让仓库有东西 —— 空仓库的「不变」没有信息量
    repo.cases.append({"case_id": "case-seed-1",
                       "ir": {"decision": {"state": "REVIEW"}},
                       "content": {"text": "hospital-grade pump"}})
    repo.reports.append({"report_id": "rep-seed-1", "case_id": "case-seed-1"})
    seeded_cases = len(repo.cases)
    seeded_reports = len(repo.reports)
    report(seeded_cases == 1 and seeded_reports == 1,
           "D0 ★ 仓库里先放了一条案件 + 一份报告（否则「不变」恒真）",
           "%d / %d" % (seeded_cases, seeded_reports))

    # ② 装一个计数器
    calls = {"n": 0, "names": []}

    def _wrap(name, fn):
        def _inner(*a, **kw):
            calls["n"] += 1
            calls["names"].append(name)
            return fn(*a, **kw)
        return _inner

    for meth in ("get_case", "list_cases", "list_reports", "get_report"):
        setattr(repo, meth, _wrap(meth, getattr(repo, meth)))

    # ★ 正向对照：读接口必须先让计数器动起来。
    #   若这一步计数器还是 0，说明**探针坏了**，后面「0 次调用」就没有意义。
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_vra_d", str(ROOT / "tools" / "verify_review_api.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    st, _ = mod.call(app, "GET", "/api/v1/cases", cookie=cookie)
    probe_calls = calls["n"]
    report(st == 200 and probe_calls > 0,
           "D1 ★★★ 正向对照：读接口会让计数器动（证明探针活着）",
           "GET /cases → %s，调用 %d 次 %r" % (st, probe_calls, calls["names"][:3]))

    # ③ 现在测 version-diff：一次 repo 方法都不许调
    calls["n"] = 0
    calls["names"] = []
    before_json = json.dumps({"cases": repo.cases, "reports": repo.reports},
                             sort_keys=True, default=str)

    for old, new in (CASE_SAME, CASE_MOVED, CASE_CHANGED):
        _post(app, cookie, old, new)

    after_json = json.dumps({"cases": repo.cases, "reports": repo.reports},
                            sort_keys=True, default=str)
    report(calls["n"] == 0,
           "D2 ★★★ 三次 version-diff 一次都没碰 repo（它不读也不写案件）",
           "调用 %d 次 %r" % (calls["n"], calls["names"][:4]))
    report(len(repo.cases) == seeded_cases and len(repo.reports) == seeded_reports,
           "D3 ★★ 案件数与报告数不变",
           "%d/%d → %d/%d" % (seeded_cases, seeded_reports,
                              len(repo.cases), len(repo.reports)))
    report(before_json == after_json,
           "D4 ★★ 整个 repo 的 JSON 逐字相同（不只是条数对）")

    # D5 ★ 无会话的请求同样不许写 —— 否则「拒绝」也会留副作用
    calls["n"] = 0
    st, _ = _post(app, None, *CASE_CHANGED)
    report(st == 401 and calls["n"] == 0 and len(repo.cases) == seeded_cases,
           "D5 ★★ 无会话被拒且同样不碰 repo（拒绝不许有副作用）", repr(st))

    # D6 ★★★ 长正文（2 万字符）能判对 —— 这是选 POST 而不是 GET 的全部理由。
    #
    #   ★★ 这一条最初写错了，记下来因为它正是本节要防的形状：
    #     第一版拿两段「声明词都出现在最前面」的长文本去测（`hospital-grade…x20000`
    #     vs `clinically…x20000`）。把实现改成「截断到 2000 字符」做变异 ——
    #     **照样全绿**。因为两边的声明词都在前 20 个字符里，截断根本没影响到它们。
    #     一条抓不住它所声称那件事的判据，就是一句注释。
    #
    #   ★ 修法：把**唯一有差异的那个声明词**放到 2 万字符**之后**。
    #     于是「截断」与「不截断」会给出不同的结论，判据才有对象：
    #       不截断 → ③ 声明已变（末尾多了 clinically）
    #       截断   → ② 声明未变（末尾那段根本没读）
    #     而这两种结果读起来都「很正常」—— 这正是截断最危险的地方。
    filler = "x" * 20000
    tail_old = "hospital-grade pump " + filler + " hospital-grade"
    tail_new = "hospital-grade pump " + filler + " clinically"
    st6, body6 = _post(app, cookie, tail_old, tail_new)
    report(st6 == 200 and (body6 or {}).get("结论") == CD.V_NEW_CLAIM,
           "D6 ★★★ 差异只出现在 2 万字符之后的正文仍被判对"
           "（改成 GET 截断后会静默判成「声明未变」）",
           "%s %r" % (st6, (body6 or {}).get("结论")))

    # D6b ★★ 反向对照：同一对长文本，若把尾部差异抹掉，必须判「声明未变」。
    #   没有这一条，D6 可能是「不管内容都判 ③」的实现也能过。
    st6b, body6b = _post(app, cookie, tail_old, tail_old)
    report(st6b == 200 and (body6b or {}).get("结论") == CD.V_SAME,
           "D6b ★★ 反向对照：同一段长文本与自己比 → ①（否则 D6 可能是恒判 ③）",
           "%s %r" % (st6b, (body6b or {}).get("结论")))


# ─────────────────────────────────────────────────────── E 反向对照（端点层）

#: C2 的判据本体 —— **抽成函数**，这样 E 组可以对它做变异。
#:
#: ★ 为什么要抽：E 组最初直接写 `tampered["结论"] != local["结论"]`，
#:   拿两个自己构造的 dict 相比 —— 那是**恒真**（我把字符串改成"已变更"，
#:   它当然不等于原值）。它证明的是"我改了一个值"，不是"C2 抓得住改写"。
#:   真正要证的是：**C2 用的那个比较函数**对好样本返回 True、对坏样本返回 False。
_EQ_FIELDS = ("结论", "判据", "消失的声明", "新增的声明", "是否触及合规表述")


def _same_as_local(body, local):
    """端点返回是否与 `change_detect` 的结论逐字一致。C 组与 E 组共用这一个。"""
    if not isinstance(body, dict):
        return False
    return all(body.get(k) == local.get(k) for k in _EQ_FIELDS)


def group_e(app, cookie):
    """★ 证明 C2 用的比较器**既不会恒真、也不会恒假**。"""
    from base import change_detect as CD

    _, body = _post(app, cookie, *CASE_CHANGED)
    body = body or {}
    local = CD.judge(*CASE_CHANGED)

    # E1 好样本：真端点返回必须被判「一致」（否则 C2 是恒红，也就没有信息量）
    report(_same_as_local(body, local) is True,
           "E1 ★★ 好样本：真端点返回判为一致（否则 C2 恒红）")

    # E2 ★★★ 端点的结论被改写 → 比较器必须返回 False
    tampered = dict(body, 结论="已变更")
    report(_same_as_local(tampered, local) is False,
           "E2 ★★★ 结论措辞被改写 → 比较器判不一致（C2 抓得住这种改写）")

    # E3 ★★ 端点的差集被丢掉 → 比较器必须返回 False
    stripped = dict(body, 消失的声明={})
    report(_same_as_local(stripped, local) is False,
           "E3 ★★ 差集被丢掉 → 比较器判不一致")

    # E4 ★★ 判据名被换掉 → 必须判不一致（结论离开判据就没意义）
    report(_same_as_local(dict(body, 判据="claim-set-v2"), local) is False,
           "E4 ★★ 判据名被换 → 比较器判不一致（判据是结论的一部分）")

    # E5 ★ 端点返回 None / 非 dict → 必须判不一致，不许当成"没有差异"
    report(_same_as_local(None, local) is False
           and _same_as_local({}, local) is False,
           "E5 ★ 返回为空 → 判不一致（空与一致不许同形）")


def main():
    print("=" * 74)
    print("version_diff · T-454 执行点（POST /api/v1/version-diff）")
    print("=" * 74)

    group_a()
    group_b()

    try:
        app, token, repo = _app()
    except Exception as exc:  # noqa: BLE001
        untested("C/D/E 端点组", "装配失败：%s: %s" % (type(exc).__name__, exc))
        return _summary()

    group_c(app, token)
    # ★ 顺序要紧：D 组会往 repo 里放种子数据并装计数器，
    #   所以它必须**排在 C/E 之后** —— 否则 C 的读请求会先动计数器。
    group_d(app, token, repo)
    group_e(app, token)
    return _summary()


def _summary():
    print("-" * 74)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
