#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_intent_infer.py — T-455 内容阶段推断的执行点

## 它守的是什么

上游 PRD `内容审查Agent-PRD-v1.0.md:137` 写着「Agent 自动识别内容类型和内容阶段」。
本仓实测：

| 字段 | 真实状态 |
|---|---|
| `content_type` | **已经确定性推导**（`_SOURCE_KIND_CONTENT_TYPE`），传错直接 422 |
| `content_stage` | 四维校验必填，但**没有任何东西会推断它** —— 调用方不填就是 422 |

本文件守的是「推断器不撒谎」：不覆盖调用方、不默认成任何一档、推断不出就说不出。

## ★★ 它同时守一条更重要的读数：推断值**今天不改变任何判定**

`research/governance/skeleton/rules-v1.json` 的 36 条规则里
`content_stage` / `brief` / `final_content` 各出现 **0 次**
（正向对照：`severity` 39 次、`layer` 38 次）。

这条读数写进 G 组，且**带正向对照**：若正向对照也是 0，结论落 `untested`
而不是「没有消费者」—— 因为那说明扫描对象不是我以为的那份文件。

没有这一组，「意图识别做完了」会在表里被读成「这个能力生效了」，
而本项目已有三个同形先例（`due_at` / 工作流耗时 / `semantic_judge` 桩）。

## 分组

| 组 | 验什么 |
|---|---|
| A 三态 | 推断得出 / 推断不出 / 调用方已给值 —— 三态互不相同 |
| B ★ 不覆盖 | 调用方给值一律采信；推断只在缺失时补；`dict` 改动不污染入参 |
| C ★ 不默认 | 两边都没命中 → `untested`，**不许**默认成某个值 |
| D ★ 幂等 | 补值必须发生在算哈希之前，两处哈希必须恒等（实测踩过真缺陷） |
| E 证据 | 每条推断都指得出命中的词，不是「模型认为」 |
| F 反向对照 | 每个判据喂坏样本必须红、好样本必须绿 |
| G ★★ 消费情况 | 规则文件里有没有人消费 `content_stage`（带正向对照） |
"""

from __future__ import annotations

import json
import os
import sys
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


#: brief 形状的正文 —— 命令式、交付要求、字数约束
BRIEF_TEXT = ("需求：写一条吸奶器详情页文案。需包含 3 个卖点，不超过 200 字，"
              "不要出现 best 这类绝对化用语。")

#: 终稿形状的正文 —— 成品话术、促销、行动号召
FINAL_TEXT = "Momcozy 官方旗舰店 限时到手价 299 元，立即抢购™。"

#: 两边都不命中的正文
NEUTRAL_TEXT = "吸奶器"


# ─────────────────────────────────────────────────────── A 三态

def group_a():
    from base import intent_infer as II

    brief = II.infer_stage(BRIEF_TEXT)
    final = II.infer_stage(FINAL_TEXT)
    none_ = II.infer_stage(NEUTRAL_TEXT)
    declared = II.infer_stage(BRIEF_TEXT, declared="final_content")

    report(brief["status"] == II.STATUS_INFERRED and brief["value"] == "brief",
           "A1 brief 形状 → inferred / brief", repr((brief["status"], brief["value"])))
    report(final["status"] == II.STATUS_INFERRED
           and final["value"] == "final_content",
           "A2 终稿形状 → inferred / final_content",
           repr((final["status"], final["value"])))
    report(none_["status"] == II.STATUS_UNTESTED and none_["value"] is None,
           "A3 ★ 两边都不命中 → untested（不产值）",
           repr((none_["status"], none_["value"])))
    report(declared["status"] == II.STATUS_ABSENT,
           "A4 调用方已给值 → absent（不推断）", repr(declared["status"]))

    states = {(brief["status"], brief["value"]),
              (none_["status"], none_["value"]),
              (declared["status"], declared["value"])}
    report(len(states) == 3, "A5 ★★ 三态互不相同（不许混成一档）", repr(states))
    report(brief["判据"] == II.JUDGE,
           "A6 结果带判据名（结论离开判据就没意义）", repr(brief["判据"]))
    report(final["value"] in II.stages() and brief["value"] in II.stages(),
           "A7 推断值都在 contract.CONTENT_STAGES 取值域内", repr(II.stages()))


# ─────────────────────────────────────────────────────── B 不覆盖

def group_b():
    from base import intent_infer as II
    from base import submission_service as S

    # B1 调用方给了值 → 一律采信，补齐后值不变
    sub = {"text": BRIEF_TEXT, "content_stage": "final_content"}
    out, inf = S.apply_stage_inference(sub)
    report(out.get("content_stage") == "final_content",
           "B1 ★★★ 调用方给 final_content → 一律采信（不许被推断改成 brief）",
           repr(out.get("content_stage")))
    report(inf["status"] == II.STATUS_ABSENT and inf["value"] is None,
           "B2 采信时不留推断值（避免下游以为有两个来源）", repr(inf["status"]))

    # B3 ★ 缺失时补上
    out2, inf2 = S.apply_stage_inference({"text": BRIEF_TEXT})
    report(out2.get("content_stage") == "brief",
           "B3 ★ 缺 content_stage → 补上推断值", repr(out2.get("content_stage")))
    report(inf2["status"] == II.STATUS_INFERRED,
           "B4 ★ 补值时观察必须是 inferred（不许写成 absent）", repr(inf2["status"]))

    # B5 ★★ 不许原地改入参 —— 上游还要用原对象算幂等哈希
    original = {"text": BRIEF_TEXT}
    snapshot = dict(original)
    S.apply_stage_inference(original)
    report(original == snapshot,
           "B5 ★★★ 不许原地改入参（上游要用原对象算幂等哈希）", repr(original))

    # B6 推断不出 → 不补，也不删已有的键
    out3, inf3 = S.apply_stage_inference({"text": NEUTRAL_TEXT})
    report("content_stage" not in out3 and inf3["status"] == II.STATUS_UNTESTED,
           "B6 ★★ 推断不出 → 不补（让四维校验照原样报缺字段）",
           repr(out3.get("content_stage")))


# ─────────────────────────────────────────────────────── C 不默认

def group_c():
    from base import intent_infer as II

    # ★★★ 这一组是整份文件最要紧的：不许默认。
    r = II.infer_stage(NEUTRAL_TEXT)
    report(r["value"] is None,
           "C1 ★★★ 没命中任何信号 → value 为 None（不许默认成某一档）",
           repr(r["value"]))
    report("不默认" in (r.get("reason") or ""),
           "C2 ★ reason 里明说不默认（读的人要知道这不是「判定为未知」）",
           (r.get("reason") or "")[:56])

    # 空正文同样不许默认
    for bad, label in ((None, "None"), ("", "空串"), ("   ", "全空白")):
        rr = II.infer_stage(bad)
        report(rr["status"] == II.STATUS_UNTESTED and rr["value"] is None,
               "C3 ★ 正文为 %s → untested（不许默认）" % label,
               repr((rr["status"], rr["value"])))

    # ★ 反向对照：若某天有人加了「默认 final_content」的兜底，C1 必红。
    #   这里直接断言「两档都不是默认值」这件事对**未命中**样本成立。
    report(r["value"] not in ("brief", "final_content"),
           "C4 ★★ 未命中样本的 value 不在两档之内（默认兜底会立刻违反本条）")


# ─────────────────────────────────────────────────────── D ★ 幂等

def group_d():
    """★★★ 这一组守的是一个**实测踩到的真缺陷**。

    `review_command_service.execute_submission()` 在调 `prepare()` **之前**就用
    `submission_hash()` 算幂等哈希，而那个哈希包含 `content_stage`。
    第一版只把推断写在 `prepare()` 里，于是：
        重放时 service 侧算的哈希（缺 stage） ≠ payload 里存的哈希（已补 stage）
    → 同 key 重放被误判成 `idempotency_conflict`。
    """
    from base.submission_service import SubmissionIngestor, apply_stage_inference

    ing = SubmissionIngestor()
    principal = {"user_id": "u-d1", "id": "u-d1", "roles": ["reviewer"],
                 "tenant": "t1", "product_lines": ["吸奶器"],
                 "capabilities": ["submit"]}
    submission = {"submission_id": "s-d1", "content_type": "文本",
                  "entry_channel": "群消息", "source": {"kind": "free_text"},
                  "product_line": "吸奶器", "text": BRIEF_TEXT}

    # 模拟 execute_submission 的真实顺序：先补值 → 再算哈希 → 再 prepare
    sub2, inf = apply_stage_inference(submission)
    h_service = ing.submission_hash(sub2, principal=principal)
    prepared = ing.prepare(sub2, principal=principal, known_inference=inf)
    h_payload = prepared["payload"]["submission_hash"]

    report(h_service == h_payload,
           "D1 ★★★ service 侧算的幂等哈希 == payload 里存的哈希"
           "（不等就会在重放时误报 idempotency_conflict）",
           "%s vs %s" % (h_service[:12], h_payload[:12]))

    # D2 ★★ 推断记录必须保留 —— 上游补过之后 prepare() 不许把它判成 absent
    got = prepared["payload"].get("intent_inference") or {}
    report(got.get("status") == "inferred" and got.get("value") == "brief",
           "D2 ★★★ 推断记录随案件走（不许因为上游补过就变成 absent）",
           repr((got.get("status"), got.get("value"))))

    # D3 ★★ 反向对照：不传 known_inference 时它会退化成 absent ——
    #    这证明 D2 抓的是真东西（否则 D2 对任何实现都恒真）
    prepared2 = ing.prepare(sub2, principal=principal)
    got2 = prepared2["payload"].get("intent_inference") or {}
    report(got2.get("status") == "absent",
           "D3 ★★ 反向对照：不传 known_inference 时退化 absent"
           "（证明 D2 不是恒真）", repr(got2.get("status")))

    # D4 ★★★ 真跑 `execute_submission` 两次（同一 key）—— 必须**不**报
    #     idempotency_conflict。这是本组的**行为级**判据。
    #
    #   ★ 为什么必须有这一条：D1 是「手工模拟 service 的顺序」，
    #     它证明的是"如果照我写的顺序做，两个哈希相等"。
    #     而真实的 `execute_submission` 是不是照那个顺序做，D1 管不着 ——
    #     实测过：把 service 里「算哈希前补值」那行删掉，D1/D2 全绿。
    #     一个只在"我以为的顺序"下成立的判据，等于没有。
    _drive_real_service()


class _FakeAuthority:
    """保留给「只测哈希比对」的最轻替身。**D4 不用它**（见 `_drive_real_service`）。"""

    def __init__(self):
        self._by_key = {}

    def idempotent(self, actor, key):
        return self._by_key.get((actor.get("principal_id"), key))

    def execute(self, *, aggregate_id, command, actor, expected_version,
                payload, idempotency_key):
        from base.business_event_store import AuthorityConflict
        k = (actor.get("principal_id"), idempotency_key)
        existing = self._by_key.get(k)
        if existing is not None:
            state = (existing.get("events") or [{}])[0].get("state") or {}
            if state.get("submission_hash") != payload.get("submission_hash"):
                raise AuthorityConflict("idempotency_conflict",
                                        "同 key 已绑定不同的 submission")
            return {"batch": existing, "replayed": True}
        batch = {"batch_id": "b-%d" % (len(self._by_key) + 1),
                 "events": [{"state": dict(payload, case_id=aggregate_id)}]}
        self._by_key[k] = batch
        return {"batch": batch, "replayed": False}


def _drive_real_service():
    """★★★ 用**真实的** `BusinessEventStore` + `ReviewCommandService` 跑两次。

    ★ 为什么不用桩：桩的 `execute()` 是我照真实实现抄的，两处必然漂移
      （§2.4.8）。而这里要证的是「真实的 service 顺序下，同 key 重放不会
      误报 idempotency_conflict」—— 用桩等于自己证明自己。

    ★ 被验的两个主体（覆盖登记表 C 段要求文件名在本文件里逐字出现）：
      · `base/review_command_service.py` 的 `ReviewCommandService.execute_submission`
        —— 它在算幂等哈希**之前**补 content_stage 的那一行，是本组要钉的对象
      · `base/submission_service.py` 的 `SubmissionIngestor.prepare` / `submission_hash`
        —— `submission_hash()` 的 body 里含 content_stage，两处必须同源
    """
    import tempfile

    from base.business_event_store import BusinessEventStore, WriterLease
    from base.review_command_service import ReviewCommandService
    from base.submission_service import SubmissionIngestor

    ing = SubmissionIngestor()
    principal = {"user_id": "u-d4", "id": "u-d4", "roles": ["reviewer"],
                 "tenant": "t1", "product_lines": ["吸奶器"],
                 "capabilities": ["submit"]}
    submission = {"submission_id": "s-d4", "content_type": "文本",
                  "entry_channel": "群消息", "source": {"kind": "free_text"},
                  "product_line": "吸奶器", "text": BRIEF_TEXT}

    root = tempfile.mkdtemp(prefix="intent-d4-")
    try:
        lease = WriterLease(os.path.join(root, "writer.lock"))
        lease.acquire()
        store = BusinessEventStore(root, lease=lease)
        # ★ `projection=None` 时 `_respond` 的 `Projector(...)` 会抛，
        #   落进它自己的 202 分支 —— 那条分支是**真实代码路径**，
        #   而且本组只关心"有没有 idempotency_conflict"，不关心投影追平。
        svc = ReviewCommandService(store, None)
        try:
            svc.execute_submission(ingestor=ing, submission=submission,
                                   principal=principal, idempotency_key="k-d4")
        except Exception as exc:  # noqa: BLE001
            untested("D4 真跑 execute_submission",
                     "首次调用失败：%s: %s" % (type(exc).__name__, exc))
            return
        report(True, "D4a 首次 execute_submission 成功（真实 store + 真 lease）")

        # ★★★ 同 key 同输入重放 —— 不许报 idempotency_conflict
        try:
            svc.execute_submission(ingestor=ing, submission=submission,
                                   principal=principal, idempotency_key="k-d4")
            conflicted = False
            detail = ""
        except Exception as exc:  # noqa: BLE001
            conflicted = "idempotency_conflict" in str(exc)
            detail = "%s: %s" % (type(exc).__name__, str(exc)[:60])
        report(not conflicted,
               "D4 ★★★ 同 key 重放**不许**报 idempotency_conflict"
               "（把 service 里「算哈希前补值」那行删掉，本行即红）",
               detail or "无冲突")
    finally:
        try:
            lease.release()
        except Exception:  # noqa: BLE001
            pass
        import shutil
        shutil.rmtree(root, ignore_errors=True)


# ─────────────────────────────────────────────────────── E 证据

def group_e():
    from base import intent_infer as II

    r = II.infer_stage(BRIEF_TEXT)
    report(bool(r["evidence"]),
           "E1 ★ 推断 brief 必须给出证据", "%d 条" % len(r["evidence"]))
    ok_shape = all(isinstance(e, dict) and e.get("pattern")
                   and e.get("hit") and e.get("why") for e in r["evidence"])
    report(ok_shape,
           "E2 ★★ 每条证据都有 pattern/hit/why（不许只有一句「模型认为」）",
           repr(r["evidence"][:1]))

    # E3 命中的词必须真的在正文里
    all_in = all(e["hit"] in BRIEF_TEXT for e in r["evidence"])
    report(all_in, "E3 ★★ 证据里的 hit 必须逐字出现在正文里")

    # E4 置信度：两条以上 brief 信号 → high
    report(r["confidence"] == "high",
           "E4 命中 %d 条 brief 信号 → confidence=high" % len(r["evidence"]),
           repr(r["confidence"]))

    # E5 ★ 只有一条信号 → low（一条可能是巧合）
    one = II.infer_stage("需求：随便写点")
    report(one["status"] == II.STATUS_INFERRED and one["confidence"] == "low",
           "E5 ★ 只命中一条信号 → confidence=low（不冒充高置信）",
           repr((one["status"], one["confidence"])))


# ─────────────────────────────────────────────────────── F 反向对照

def group_f():
    from base import intent_infer as II
    from base import submission_service as S

    # F1 好样本必须绿（否则上面的红全是恒红）
    good = II.infer_stage(BRIEF_TEXT)
    report(good["status"] == II.STATUS_INFERRED,
           "F1 ★ 好样本必须绿（否则上面全是恒红）")

    # F2 ★ 变异：若「调用方已给值」分支被删，这里会从 absent 变成 inferred
    r = II.infer_stage(BRIEF_TEXT, declared="final_content")
    report(r["status"] == II.STATUS_ABSENT,
           "F2 ★★ 已给值时必 absent（去掉那个分支会变成 inferred，本行即红）",
           repr(r["status"]))

    # F3 ★ 变异：若「推断不出就不补」被改成默认值，B6/C1 会红；
    #    这里再用 apply_stage_inference 复算一次，证明缺字段确实保持缺
    out, _ = S.apply_stage_inference({"text": NEUTRAL_TEXT})
    report("content_stage" not in out,
           "F3 ★★★ 推断不出时不许补任何默认值（补了就会盖上「人填的」印象）")

    # F4 compare() 的三个返回值必须各不同：True / False / None
    a = II.compare("brief", {"value": "brief"})
    b = II.compare("final_content", {"value": "brief"})
    c = II.compare(None, {"value": "brief"})
    report({a["agree"], b["agree"], c["agree"]} == {True, False, None},
           "F4 ★★ compare 三态互不相同（一致 / 分歧 / 无法比较）",
           repr((a["agree"], b["agree"], c["agree"])))
    report("以调用方为准" in b["note"],
           "F5 ★ 有分歧时明说「以调用方为准」（不阻断、不覆盖）", b["note"][:40])


def _verdict_from_counts(counts, controls, rule_count=36):
    """转调 `intent_infer` 里**唯一**的判定函数。

    ★ 第一版本文件自己又实现了一份，而 G8 断言「抽出的函数与
      `rule_consumer_status()` 结论逐字相同」—— 那等于拿两个**必然不同**的
      实现去比，迟早红（或者更糟：为了让 G8 绿，去把两处措辞改成一样）。
      正确做法是这里直接转调，让"只有一个判定点"成为事实而不是断言。
    """
    from base import intent_infer as II
    return II._stage_consumption_verdict(counts, controls, rule_count)


# ─────────────────────────────────────────────────────── G ★★ 消费情况

def group_g():
    """★★★ 如实报出：推断值今天有没有规则消费它。"""
    from base import intent_infer as II

    st = II.rule_consumer_status()
    if st["status"] == "untested":
        untested("G 组", st.get("reason") or "读不出")
        return

    report(st["status"] == "measured",
           "G1 规则消费情况被真实测量（不是猜的）", repr(st["status"]))
    report(all(v > 0 for v in st["controls"].values()),
           "G2 ★★ 正向对照非零（severity/layer 都在）—— 证明扫描对象是对的",
           repr(st["controls"]))
    report(isinstance(st["rule_count"], int) and st["rule_count"] > 0,
           "G3 数到了规则条数", repr(st["rule_count"]))

    # ★★★ 这一条是本组的全部意义：如实说「没有规则消费」
    report(st["consumed_by_rules"] is False,
           "G4 ★★★ 如实报告：**没有任何规则消费 content_stage**"
           "（推断值今天不改变任何判定）", repr(st["counts"]))
    report("不改变任何判定" in st["conclusion"],
           "G5 ★ 结论句里明说不改变判定（不许含糊成「已支持」）",
           st["conclusion"][:56])

    # ★★★ G6/G7 —— 反向对照：判定逻辑必须**两个方向都会翻**
    #   只断言「真实文件里是 0」，对「永远数出 0 的实现」也成立（恒真）。
    #   所以这里直接喂正反两组读数给同一个判定函数。
    fake_consumed = _verdict_from_counts(
        {"content_stage": 3, "brief": 1, "final_content": 0},
        {"severity": 39, "layer": 38})
    report(fake_consumed["consumed_by_rules"] is True
           and "有规则消费" in fake_consumed["conclusion"],
           "G6 ★★ 反向对照：非零计数必须翻成「有消费」"
           "（否则 G4 可能是无条件报没有）", fake_consumed["conclusion"])

    fake_absent = _verdict_from_counts(
        {"content_stage": 0, "brief": 0, "final_content": 0},
        {"severity": 39, "layer": 38})
    report(fake_absent["consumed_by_rules"] is False,
           "G7 ★ 零计数必须报「没有消费」（与真实文件的读数一致）")

    # G8 ★★ 判据只许有一处实现 —— 这一条不能靠「两个函数比结果」，
    #   因为自证里那个函数现在就是转调（比出来必然相等，恒真）。
    #   改成查源码：判定函数只能定义一次，且必须真的被 `rule_consumer_status()` 调用。
    #   ★ 第一版找的是 `consumed_by_rules = ...` 赋值行 —— 一个都找不到，
    #     因为它是**字典的键**不是赋值（`"consumed_by_rules": ...`）。
    #     那条断言对任何实现恒红，等于把一条真判据写成了噪声。
    src = (ROOT / "base" / "intent_infer.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    defs = [ln for ln in code.splitlines()
            if ln.lstrip().startswith("def _stage_consumption_verdict")]
    calls = [ln for ln in code.splitlines()
             if "_stage_consumption_verdict(" in ln
             and not ln.lstrip().startswith("def ")]
    report(len(defs) == 1 and len(calls) >= 1,
           "G8 ★★ 判定函数只定义一次、且真的被调用（两处必然各自漂移）",
           "defs=%d calls=%d" % (len(defs), len(calls)))


def main():
    print("=" * 74)
    print("intent_infer · T-455 执行点（content_stage 建议值推断）")
    print("=" * 74)
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    group_f()
    group_g()
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
