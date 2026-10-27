#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_skill_registry.py — T-453 skill 加载器的执行点

## 它守的是什么

回执里有 `skill_id` / `skill_version` / `skill_hash`。2026-10-27 实测：
**生产链路一个都没传**，于是 `base/judge_entry.py:181-182` 的默认值生效，
回执永远写着 `content-review / 1 / local` —— 而 `"local"` 是硬编码字面量。

**"local" 比"没实现"更该修**：它让回执**声称**一个自己并不知道的版本。
这个文件守的是「那个字段从此指得出真实文件，且指纹等于文件字节的 sha256」。

## 分组

| 组 | 验什么 |
|---|---|
| A 注册表本身 | 能读、字段齐、id 唯一、触发词不重叠 |
| B 双向完整 | 登记了必须存在 / 存在了必须登记（**两个方向各自能红**） |
| C 指纹 | 等于真实文件 sha256；改一个字节必须变 |
| D 接线 | 回执里的 skill_hash 不再恒为 "local"，且等于注册表算出的值 |
| E 反向对照 | 每个判据喂一次坏样本必须红、好样本必须绿 |

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from base import skill_registry as SR  # noqa: E402

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


# ─────────────────────────────────────────────────────────── A 注册表本身


def group_a(reg):
    report(isinstance(reg.get("skills"), list) and reg["skills"],
           "A1 注册表有 skills 且非空", repr(len(reg.get("skills") or [])))
    problems = SR.validate(reg)
    report(problems == [], "A2 注册表校验全过", repr(problems[:3]))

    ids = [s.get("id") for s in reg["skills"] if isinstance(s, dict)]
    report(len(ids) == len(set(ids)), "A3 id 唯一", repr(ids))

    # 已知的两个 skill 必须在册（不然「登记完整」这句话没对象）
    for want in ("content-review", "shouheng-tone"):
        report(want in ids, "A4 在册：%s" % want, repr(ids))

    # 每条都要有 not_for（说清它不干什么）—— 只写"能干什么"的规程容易越界
    missing = [s.get("id") for s in reg["skills"]
               if isinstance(s, dict) and not (s.get("not_for") or [])]
    report(missing == [], "A5 每条都写了 not_for（边界不是可选项）", repr(missing))


# ─────────────────────────────────────────────────────────── B 双向完整


def group_b(reg):
    # B1 登记了但文件不在 → 校验器必须报
    bad = json.loads(json.dumps(reg))
    bad["skills"][0]["path"] = "agent-skills/不存在的目录/SKILL.md"
    problems = SR.validate(bad)
    report(any("文件不在盘上" in p for p in problems),
           "B1 ★★ 登记了但文件不在 → 红（一个方向）", repr(problems[:2]))

    # B2 ★ 文件在但没登记 → 校验器必须报
    bad2 = json.loads(json.dumps(reg))
    bad2["skills"] = [s for s in bad2["skills"] if s.get("id") != "shouheng-tone"]
    problems2 = SR.validate(bad2)
    report(any("没登记" in p for p in problems2),
           "B2 ★★ 盘上有规程但没登记 → 红（另一个方向，缺它上面那条会漏）",
           repr(problems2[:2]))

    # B3 id 重复 → 红
    bad3 = json.loads(json.dumps(reg))
    bad3["skills"].append(dict(bad3["skills"][0]))
    report(any("登记了 2 次" in p for p in SR.validate(bad3)),
           "B3 ★ id 重复 → 红")

    # B4 触发词抢同一个词 → 红
    bad4 = json.loads(json.dumps(reg))
    bad4["skills"][1]["trigger_words"] = list(bad4["skills"][0]["trigger_words"])
    report(any("同时属于" in p for p in SR.validate(bad4)),
           "B4 ★ 触发词重叠 → 红（否则「该用哪个」无解）")


# ─────────────────────────────────────────────────────────── C 指纹


def group_c(reg):
    desc, why = SR.resolve("content-review")
    if desc is None:
        untested("C1-C3 指纹", why)
        return
    real = SR.fingerprint(ROOT / desc["path"])
    report(desc["skill_hash"] == real,
           "C1 ★★ skill_hash = 真实文件字节的 sha256", desc["skill_hash"][:16])
    report(len(desc["skill_hash"]) == 64 and
           all(c in "0123456789abcdef" for c in desc["skill_hash"]),
           "C2 指纹形态是 64 位小写十六进制", desc["skill_hash"][:12])
    report(desc["skill_version"] == "1.0.0",
           "C3 version 是规程文档的版本（不是引擎版本）", repr(desc["skill_version"]))

    # C4 ★ 改一个字节指纹必须变（证明它真的是内容指纹，不是路径/时间）
    tmp = Path(tempfile.mkdtemp(prefix="skill-fp-"))
    try:
        src = ROOT / desc["path"]
        copy = tmp / "SKILL.md"
        shutil.copy2(src, copy)
        fp_before = SR.fingerprint(copy)
        copy.write_bytes(copy.read_bytes() + b"\n")
        fp_after = SR.fingerprint(copy)
        report(fp_before != fp_after,
               "C4 ★★★ 加一个字节 → 指纹变（证明是内容指纹，不是 mtime/size）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────── D 接线


def group_d():
    """★ 这一组才是本票的关键：回执里那个字段是否**真的**指得出文件。"""
    # D1 源码级：`skill_hash="local"` 的默认值必须已经不再是「假装知道」
    src = (ROOT / "base" / "judge_entry.py").read_text(encoding="utf-8")
    report('skill_hash="local"' not in src,
           "D1 ★★★ judge_entry 里不再有 skill_hash=\"local\" 这个硬编码默认值",
           "仍有" if 'skill_hash="local"' in src else "已去掉")

    # D2 行为级：真跑一次判定，回执里的 skill_hash 必须是真指纹
    try:
        from base.judge_entry import judge_unit
        result = judge_unit({
            "text": "这是一段用于验证 skill 指纹的测试文案，含 best 这类绝对化用语",
            "content_type": "ad_text", "content_stage": "final_content",
            "skill_id": "content-review", "product_line": "吸奶器",
            "channel": "TikTok",
        })
    except Exception as exc:  # noqa: BLE001
        untested("D2-D4 回执接线", "判定失败：%s" % exc)
        return

    receipt = result.get("receipt") or {}
    got = receipt.get("skill_hash")
    want, why = SR.receipt_fields("content-review")
    report(got != "local",
           "D2 ★★★ 回执里的 skill_hash 不再是 \"local\"", repr(got))
    report(got == want.get("skill_hash"),
           "D3 ★★★ 回执里的 skill_hash = 注册表算出的真指纹",
           "%r vs %r" % (got, want.get("skill_hash")[:16] if want else why))
    report(receipt.get("skill_version") == "1.0.0",
           "D4 ★★ 回执里的 skill_version 来自注册表（不是 \"1\"）",
           repr(receipt.get("skill_version")))

    # D5 ★ 反向对照：注册表算不出时，回执不许编一个好看的默认值
    fields, why5 = SR.receipt_fields("no-such-skill")
    report(fields == {} and why5,
           "D5 ★★ 取不到 skill 时 receipt_fields 返回空 dict + 原因（不编默认值）",
           repr(why5[:40]))

    # D6 ★★★ 生产链路真的传了 skill_id —— 这是本票最该钉住的一条。
    #   ★ 为什么必须查**行为**而不是源码里有没有 "skill_id"：
    #     字符串 `skill_id` 在那个文件里到处都是（函数参数、默认值、回执组装），
    #     一条文本存在性检查恒真（§2.4 那个病）。
    #     所以这里真跑一次 prepare()，看回执里的 version/hash 是不是来自注册表。
    #
    #   ★ 被验的主体是 `base/submission_service.py` 的 `SubmissionIngestor.prepare()` ——
    #     生产链路上唯一会调判定函数的地方。这一行就是为了让覆盖登记表的
    #     C 段（「文件名要在本文件源码里出现」）能指得出对象。
    try:
        from base.submission_service import SubmissionIngestor
        ing = SubmissionIngestor()
        principal = {"user_id": "u-d6", "roles": ["reviewer"], "tenant": "t1",
                     "product_lines": ["吸奶器"], "capabilities": ["submit"]}
        out = ing.prepare({
            "submission_id": "s-d6", "content_type": "文本",
            "content_stage": "final_content", "entry_channel": "群消息",
            "source": {"kind": "free_text"}, "text": "测试文案 best",
            "product_line": "吸奶器"}, principal=principal)
        rec = ((out.get("payload") or {}).get("judgment") or {}).get("receipt") or {}
        report(rec.get("skill_hash") == want.get("skill_hash"),
               "D6 ★★★ 生产链路（SubmissionIngestor）回执里的 skill_hash = 真指纹",
               "%r" % (str(rec.get("skill_hash"))[:20],))
        report(rec.get("skill_version") == "1.0.0",
               "D6b ★★ 生产链路回执里的 skill_version = 注册表版本",
               repr(rec.get("skill_version")))

        # ★★★ D7 必须验「调用方**真的把参数传下去了**」，不能只看结果值。
        #   实测教训：D6 曾经抓不住「把 skill_id 那行删掉」的变异 ——
        #   因为 judge_entry 的默认值**恰好也是 content-review**，
        #   于是「没传」与「传了」产出同一个回执。
        #   一个抓不住真实变异的判据等于没有（§2.4.1：「什么变异让它红」）。
        #   所以这里直接观察 judge_fn 收到了什么。
        seen = {}

        def _spy(unit, **kwargs):
            seen.update(kwargs)
            from base.judge_entry import judge_unit as _real
            return _real(unit, **kwargs)

        ing2 = SubmissionIngestor(judge_fn=_spy)
        ing2.prepare({
            "submission_id": "s-d7", "content_type": "文本",
            "content_stage": "final_content", "entry_channel": "群消息",
            "source": {"kind": "free_text"}, "text": "测试文案 best",
            "product_line": "吸奶器"}, principal=principal)
        report(seen.get("skill_id") == "content-review",
               "D7 ★★★ 生产链路**把 skill_id 传给了判定函数**（不是靠默认值）",
               "传给 judge 的 skill_id=%r" % (seen.get("skill_id"),))
    except Exception as exc:  # noqa: BLE001
        untested("D6 生产链路回执", "%s: %s" % (type(exc).__name__, exc))


# ─────────────────────────────────────────────────────────── E 反向对照


def group_e(reg):
    # E1 好样本必须绿（否则上面的红全是恒红）
    report(SR.validate(reg) == [], "E1 ★ 好样本必须绿")

    # E2 拿掉一个必需字段必须红
    bad = json.loads(json.dumps(reg))
    bad["skills"][0].pop("version", None)
    report(any("version" in p for p in SR.validate(bad)),
           "E2 ★ 缺 version → 红")

    # E3 resolve 对坏 id 的行为
    d, why = SR.resolve("")
    report(d is None and why, "E3 ★ 空 id → None + 原因", repr(why))
    d2, _ = SR.resolve("content-review")
    report(d2 is not None, "E4 ★ 反向对照：合法 id 必须取得到（否则 E3 恒真）")

    # E5 注册表读不出时抛而不是返回空表
    tmp = Path(tempfile.mkdtemp(prefix="skill-bad-"))
    try:
        p = tmp / "registry.json"
        p.write_text("{ this is not json", encoding="utf-8")
        try:
            SR.load_registry(p)
            report(False, "E5 ★★ 坏 JSON 必须抛（返回空表会让「零个 skill」与「读不出」同形）")
        except SR.SkillRegistryError:
            report(True, "E5 ★★ 坏 JSON 抛 SkillRegistryError")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 74)
    print("skill_registry · T-453 执行点")
    print("=" * 74)
    try:
        reg = SR.load_registry()
    except SR.SkillRegistryError as exc:
        print("UNTESTED: 注册表读不出 —— %s" % exc)
        return 2
    group_a(reg)
    group_b(reg)
    group_c(reg)
    group_d()
    group_e(reg)
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
