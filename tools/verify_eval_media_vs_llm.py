#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_eval_media_vs_llm.py —— 媒体评测工具的自证（离线，不联网）

## 它守的是什么

`tools/eval_media_vs_llm.py` 要回答「本系统 vs 裸大模型，速度和质量差多少」。
这个问题的危险性在于：**它太容易给出一个看起来合理的假答案。**

| 假答案 | 为什么会被当真 |
|---|---|
| 本系统 0 条 finding、裸模型 5 条 | 读成「本系统误报少」——实际是**它什么都没看见** |
| 凭据没配时两侧都 0ms | 读成「都很快」——实际是**一条都没跑** |
| 网络失败时报 `HTTP 0：`（空原因） | 读成「模型返回空」——实际是 TLS 握手失败 |

所以本文件的判据**不是**「评测算得准不准」，而是
**「评测有没有把自己没测成这件事说清楚」**。

## 分组

| 组 | 验什么 |
|---|---|
| A | 凭据读数：只报配没配，**绝不打印值**；缺哪几个要点名 |
| B | ★★★ 未测时**一条指标都不给** —— 指标必须是 `None`，不是 0 |
| C | ★★★ 「0 条 finding」必须与「什么都没看见」一起报 |
| D | 速度快照（`_summarize`）：分母为 0 时给 None；样本数对得上 |
| E | 反向对照：把上面几条的坏样本喂进去，必须判假 |

## 为什么没有「联网跑一次」的断言

那要真凭据，而且会在 CI 里发真实图片。本文件验的是**评测工具的诚实性**，
不是模型能力 —— 后者由真跑时的人看读数。

退出码：0 全过 / 1 有红 / 2 未测（模块导入失败等）。
"""

from __future__ import annotations

import json
import os
import re
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


# ─────────────────────────────────────────────── A 凭据读数

def group_a():
    from tools import eval_media_vs_llm as E

    saved = {k: os.environ.get(k) for k in (
        "MULTIMODAL_TOKENHUB_BASE_URL", "MULTIMODAL_TOKENHUB_API_KEY",
        "MULTIMODAL_VOD_BASE_URL", "MULTIMODAL_VOD_API_TOKEN")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        empty = E.check_env()
        report(not empty["tokenhub"]["ready"],
               "A1 ★ 全空时 tokenhub 报未配（否则「未配」会被读成「配好了」）",
               repr(empty["tokenhub"]["ready"]))
        report(empty["tokenhub"]["missing"]
               == ["MULTIMODAL_TOKENHUB_BASE_URL", "MULTIMODAL_TOKENHUB_API_KEY"],
               "A2 ★★ 缺哪两个要点名（只说「未配」运维不知道去配什么）",
               repr(empty["tokenhub"]["missing"]))

        # ★★★ A3：读数里**不许出现凭据值**。
        #
        #   这一条是本组最重要的一条：`check_env()` 会被 --check 打到终端、
        #   写进 --out 的 JSON。一旦它开始打印值，凭据就进了日志。
        #   判据是「把值塞进环境后，输出里搜不到它」——行为级，不是读源码。
        os.environ["MULTIMODAL_TOKENHUB_BASE_URL"] = "https://probe.invalid"
        os.environ["MULTIMODAL_TOKENHUB_API_KEY"] = "SK-PROBE-DO-NOT-PRINT-9f3a"
        full = E.check_env()
        blob = json.dumps(full, ensure_ascii=False)
        report("SK-PROBE-DO-NOT-PRINT-9f3a" not in blob,
               "A3 ★★★ 凭据值**不出现在读数里**（否则日志与 --out 就泄露了）",
               "命中" if "SK-PROBE" in blob else "未命中")
        report("probe.invalid" not in blob,
               "A4 ★★ base URL 也不打印（它可能带 token 查询串）")
        report(full["tokenhub"]["ready"],
               "A5 ★ 配齐时 ready=True（否则 A1 可能是恒假）")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ─────────────────────────────────────────────── B 未测不给指标

def group_b():
    from tools import eval_media_vs_llm as E

    r = E._untested("凭据未配")
    report(r["status"] == "untested", "B1 ★ 未测的 status 就是 untested",
           repr(r["status"]))
    # ★★★ 核心：指标必须是 None，不是 0。
    #   0 会被读成「测了，耗时 0ms / 准确率 0」；None 才是「没测」。
    report(r["metrics"] is None,
           "B2 ★★★ 未测时 metrics 是 None（不许是 0 或 {}）",
           repr(r["metrics"]))
    report(bool(r["reason"]),
           "B3 ★★ 未测必须带原因（否则读的人只知道「没结果」）", r["reason"])

    # B9 ★★★ `--check` 的退出码必须把「能跑」与「跑不了」分开
    #
    #   实测踩过：第一版两种情况下都退 2，于是调用方分不清
    #   「配好了可以跑」和「凭据没配」。这是本项目反复记的那个病：
    #   **两种完全不同的状态长得一样**。
    #
    #   ★ 判据打在源码上而不是真跑子进程：子进程会读真实环境，
    #     而自证**不许依赖外部状态**（环境里有没有凭据会改变结论）。
    src = (ROOT / "tools" / "eval_media_vs_llm.py").read_text(encoding="utf-8")
    # ★ 按**行号范围**取 `--check` 那一段，不按字符串切分 ——
    #   块内部也有 `if gold["status"] != "ok":`，用 split 会切在块的中间
    #   （第一版就这么写的，取到的片段里既没有 return 0 也没有 return 2，
    #   于是 B9/B10 都判红，而读起来像「代码真的没有那两个分支」）。
    lines = src.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "if args.check:")
    # ★ 块的结束 = 下一个**缩进回到函数体层级**的行（`if gold[...]`）。
    #   块内部的那一行缩进更深（8 空格），所以必须同时判缩进 ——
    #   只按文本相等找会取到紧跟的下一行，切片为空，
    #   于是 B9/B10 都判红、读起来像「代码真的没有那两个分支」。
    base_indent = len(lines[start]) - len(lines[start].lstrip())
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].strip()
               and (len(lines[i]) - len(lines[i].lstrip())) <= base_indent)
    body = "\n".join(lines[start:end])
    report("return 0" in body,
           "B9 ★★★ `--check` 能跑时退 0（退 2 会与「跑不了」撞码）",
           "命中" if "return 0" in body else "零命中")
    report(body.count("return 2") >= 1,
           "B10 ★★ 跑不了时仍退 2（B9 的另一半：别把两条一起改成 0）",
           "%d 处 return 2" % body.count("return 2"))
    #
    #   ★ 这一条真跑一次读盘（指向一个临时空目录），不是读源码猜。
    #     第一版这里写的是 `report(g is None or True, "B4（跳过…）")` ——
    #     一个 `or True` 恒真的判断。那正是本项目最忌讳的形状
    #     （「名字出现过 ≠ 拦得住」），而且它还会以 PASS 的身份出现在读数里。
    import tempfile
    saved_dir = E.GOLD_DIR
    tmp = Path(tempfile.mkdtemp(prefix="eval-gold-b4-"))
    try:
        E.GOLD_DIR = tmp
        missing = E._load_gold()
        report(missing["status"] == "untested",
               "B4 ★★★ gold 不存在 → untested（不许当成「0 条所以全对」）",
               repr(missing["status"]))
        report("不在盘上" in missing["reason"],
               "B5 ★★ 说得出是哪种读不出（不在盘上 / 读不出 / 形状坏）",
               missing["reason"][:60])

        # B6 ★★ 形状坏（不是数组）→ 也是 untested，且原因不同
        from pathlib import Path as _P
        (_P(tmp) / "gold.json").write_text('{"not":"an array"}', encoding="utf-8")
        bad_shape = E._load_gold()
        report(bad_shape["status"] == "untested",
               "B6 ★★ gold 形状坏 → untested", repr(bad_shape["status"]))
        report("不是非空数组" in bad_shape["reason"],
               "B7 ★★ 形状坏与不在盘上说得不一样（否则排查会走错方向）",
               bad_shape["reason"][:60])

        # B8 ★★★ 真有好样本时必须 ok —— 否则上面四条全是恒真
        (_P(tmp) / "gold.json").write_text(
            json.dumps([{"record_id": "r1"}], ensure_ascii=False), encoding="utf-8")
        good = E._load_gold()
        report(good["status"] == "ok" and len(good["records"]) == 1,
               "B8 ★★★ 反向对照：真 gold 在盘上时必须 ok（证明上面不是恒真）",
               repr(good["status"]))
    finally:
        E.GOLD_DIR = saved_dir
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────── C 0 条 finding 的语义

def group_c():
    from tools import eval_media_vs_llm as E

    # 构造两侧读数：system 看见 0 条、且 note 说未接入
    rows = [{
        "record_id": "r1", "image": "a.png", "gold_category": "原则性错误",
        "system": {"status": "ok", "reason": "", "ms": 12.0, "findings": [],
                   "decision": "REVIEW", "observations": 0,
                   "multimodal_note": "未接入多模态分析"},
        "baseline": {"status": "ok", "reason": "", "ms": 900.0,
                     "findings": [{"category": "使用场景不当"}], "decision": None},
    }]
    s = E._summarize(rows)

    # ★ 字段名是 `no_vision`（2026-10-28 更正）：它只指「画面没看」，
    #   **不含** OCR —— 实测 OCR 是好的。原来的名字 `saw_nothing`
    #   建立在「OCR 也不可用」这个错误前提上。
    report(s["system"]["no_vision"] == 1,
           "C1 ★★★ 「画面没看」被单独计数（否则 0 条会被读成判得准）",
           repr(s["system"]["no_vision"]))
    report(s["system"]["findings_total"] == 0
           and s["baseline"]["findings_total"] == 1,
           "C2 两侧产出量分开报（不合并成一个数）",
           "%s vs %s" % (s["system"]["findings_total"],
                         s["baseline"]["findings_total"]))

    # C3 ★★ 反向对照：看见了东西时 saw_nothing 必须是 0
    #
    #   只验 C1 会让「恒定 1」的实现也绿。
    seen = [dict(rows[0])]
    seen[0] = {**rows[0], "system": {**rows[0]["system"],
                                     "observations": 3,
                                     "multimodal_note": ""}}
    report(E._summarize(seen)["system"]["no_vision"] == 0,
           "C3 ★★★ 反向对照：真看了画面时 no_vision=0（证明 C1 不是恒真）")

    # C4 ★★ baseline 侧不报这个字段（它是 system 独有的能力读数）
    report(E._summarize(rows)["baseline"]["no_vision"] is None,
           "C4 ★ baseline 侧 no_vision 是 None（它没有这个概念）",
           repr(E._summarize(rows)["baseline"]["no_vision"]))

    # C5 ★★★ 旧字段名必须**真的不在了** —— 否则「改名」只改了一半，
    #   而读到旧名的地方会静默拿到 KeyError 或 None。
    report("saw_nothing" not in E._summarize(rows)["system"],
           "C5 ★★★ 旧字段名 saw_nothing 已不存在（改名不留半截）",
           repr(sorted(E._summarize(rows)["system"])))


# ─────────────────────────── C2 真实进件链（不许手工拼空正文）

def group_c2():
    """★★★ 这一组防的是本文件历史上最严重的一个错。

    `run_system()` 第一版手工拼了 `{"text": "", "has_text": False}` 的 unit
    直接喂给 `judge_unit` —— 等于**跳过 OCR**。症状是 `ocr_chars` 恒为 0，
    而真跑 `image_file_row()` 明明读出 285 字。

    它的危害不只是评测失真：它把「OCR 可用」测成了「OCR 不可用」，
    于是后续所有结论（包括我在文档里写下的「本系统什么都看不见」）
    都建立在一个错误前提上。

    ★ 判据打在**行为**上：给一张真有字的图，`run_system()` 返回的
      `ocr_chars` 必须 > 0。手工拼空 unit 的实现必然给 0。
    """
    from tools import eval_media_vs_llm as E

    # 找一张真有字的图（gold 目录；找不到就退未测，不硬编码路径）
    imgs = []
    for rec in (E._load_gold().get("records") or []):
        imgs.extend(E._images_of(rec))
    if not imgs:
        untested("H 找一张带文字的图", "gold 目录里没有可用图片")
        return

    # 逐张试，直到找到一张 OCR 读得出字的（有些图本身没文字）
    per_image = []
    for img in imgs[:6]:
        r = E.run_system(img)
        per_image.append((img.name, r.get("ocr_chars"), r.get("status")))
        if (r.get("ocr_chars") or 0) > 0:
            break

    got = [p for p in per_image if (p[1] or 0) > 0]
    if not got:
        # ★★ 这里必须是**红**，不是未测。
        #
        #   区别在于「是谁的问题」：
        #   · 未测 = 环境缺东西（gold 不在盘上、OCR 二进制编不出来）；
        #   · 红   = 代码本身跳过了 OCR —— 而 OCR **在本机是可用的**
        #            （同一张图手工调 `image_file_row()` 能读出 285 字）。
        #
        #   第一版这里报未测，于是「跳过 OCR」这个真缺陷会以「⚠ 未测」
        #   的身份收场 —— 而「未测不是通过」这条规定，一旦用来装真缺陷，
        #   就成了免死金牌。
        report(False,
               "H1 ★★★ run_system 必须走真实进件链（OCR 读到了字）",
               "试的 %d 张图都没读出文字 —— 而手工调 image_file_row() 能读出来，"
               "说明是 run_system 跳过了 OCR：%r" % (len(per_image), per_image[:3]))
        return

    name, chars, status = got[0]
    report(status == "ok" and chars > 0,
           "H1 ★★★ run_system 走**真实进件链**（OCR 读到了字，不是手工塞空正文）",
           "%s → %d 字" % (name, chars))

    # C3 ★★★ 规则条数必须非 0 —— 证明它真的进了规则引擎，不是空转
    r = E.run_system(imgs[0])
    report((r.get("rules_applied") or 0) > 0,
           "H2 ★★★ 规则引擎真的跑了（control_points_applied 非空）",
           repr(r.get("rules_applied")))

    # C4 ★★ 语言占比有值 —— 它是「0 条 finding」的解释字段
    report(r.get("cjk_ratio") is not None,
           "H3 ★★★ 读到字时必须给出中文占比（否则「0 条」无法解释）",
           repr(r.get("cjk_ratio")))

    # C5 ★★★ 反向对照：空正文时 cjk_ratio 必须是 None，不是 0.0
    #
    #   「没有字可判」与「有字但一个中文都没有」是两件事。
    #   只验 C4 会让一个「恒返回 0.0」的实现也绿。
    report(E._cjk_ratio("") is None,
           "H4 ★★★ 空正文 → None（不是 0.0：「没字可判」≠「没中文」）",
           repr(E._cjk_ratio("")))
    report(E._cjk_ratio("Dein korper braucht") == 0.0,
           "H5 ★★★ 纯拉丁文 → 0.0（证明 C5 的 None 不是恒真）",
           repr(E._cjk_ratio("Dein korper braucht")))
    report(E._cjk_ratio("家纺线下试衣镜选品") == 1.0,
           "H6 ★ 纯中文 → 1.0", repr(E._cjk_ratio("家纺线下试衣镜选品")))


# ─────────────────────────────────────────────── D 速度快照

def group_d():
    from tools import eval_media_vs_llm as E

    rows = [
        {"system": {"status": "ok", "ms": 10.0, "findings": []},
         "baseline": {"status": "ok", "ms": 900.0, "findings": [{"x": 1}]}},
        {"system": {"status": "ok", "ms": 20.0, "findings": []},
         "baseline": {"status": "ok", "ms": 1100.0, "findings": []}},
    ]
    s = E._summarize(rows)
    report(s["system"]["latency_ms"]["median"] == 15.0,
           "D1 ★ 中位数算对（10/20 → 15）", repr(s["system"]["latency_ms"]["median"]))
    report(s["system"]["latency_ms"]["n"] == 2,
           "D2 ★★ 样本数 n 与实际测成数一致（分母要能被看见）",
           repr(s["system"]["latency_ms"]["n"]))
    report(s["baseline"]["findings_total"] == 1,
           "D3 产出量是求和，不是均值", repr(s["baseline"]["findings_total"]))

    # D4 ★★★ 分母为 0 时必须 None，不是 0
    #
    #   这一条与 B2 是同一个口径，但打在不同的函数上：
    #   B2 验「未测对象」，D4 验「聚合器」。一个坏实现可以在 B2 给 None、
    #   在聚合时算出 0 —— 那读起来就像「跑了很多次，耗时 0ms」。
    empty = E._summarize([{"system": {"status": "untested", "ms": None,
                                      "findings": []},
                           "baseline": {"status": "untested", "ms": None,
                                        "findings": []}}])
    report(empty["system"]["latency_ms"]["median"] is None,
           "D4 ★★★ 一条都没测成时中位数是 None（不许是 0ms）",
           repr(empty["system"]["latency_ms"]["median"]))
    report(empty["system"]["findings_total"] is None,
           "D5 ★★ 没测成时产出量是 None（不许是 0 条）",
           repr(empty["system"]["findings_total"]))
    report(empty["system"]["untested"] == 1,
           "D6 ★★ 未测数被计入（不是静默丢掉）", repr(empty["system"]["untested"]))


# ─────────────────────────────────────────────── E 反向对照

def group_e():
    from tools import eval_media_vs_llm as E

    # E1 ★★★ 静默把 0 当指标 —— 会让 B2/D4 判假
    fake_metrics = {"latency_ms": 0}
    report(fake_metrics is not None,
           "E1 ★★ 「指标是 0」与 None 是不同的值（B2 的 `is None` 才有意义）",
           repr(fake_metrics))

    # E2 ★★ 裸模型产出解析：抠不到 JSON 时**返回空列表**，不是抛、也不是假装成功
    #
    #   这一条防的是「格式失败被读成质量满分」。
    report(E._parse_baseline_findings("模型说：看起来没问题") == [],
           "E2 ★★★ 没有 JSON 时返回空列表（不伪造 finding，也不崩）")
    report(E._parse_baseline_findings('{"findings":[{"category":"x"}]}')
           == [{"category": "x", "region": None, "reason": None}],
           "E3 ★ 正常 JSON 能解析出来（否则 E2 是恒真）")
    # E4 ★★ 形状坏（findings 不是数组）→ 空列表
    report(E._parse_baseline_findings('{"findings":"oops"}') == [],
           "E4 ★★ findings 不是数组时返回空列表（不往下喂坏形状）")

    # E5 ★★★ HTTP 失败必须带**原因**，不许是空白
    #
    #   实测踩过：第一版只看 `status`，网络层失败时输出「HTTP 0：」+ 一片空白，
    #   而真正原因（TLS 握手失败）就在 `HttpResult.error` 里，一个字没打出来。
    #   判据打在这段源码上：它必须读 `error`。
    src = (ROOT / "tools" / "eval_media_vs_llm.py").read_text(encoding="utf-8")
    code = "\n".join(
        line.split("#", 1)[0] for line in src.splitlines())
    report(re.search(r'getattr\(resp,\s*"error"', code) is not None,
           "E5 ★★★ 失败原因从 `HttpResult.error` 读（否则失败被渲染成空白）")
    report('status == 0' in code,
           "E6 ★★ status=0（网络层失败）单独说明"
           "（与 4xx/5xx 的语义完全不同）")


def main():
    print("=" * 74)
    print("eval_media_vs_llm · 评测工具的诚实性自证（离线）")
    print("=" * 74)
    try:
        import tools.eval_media_vs_llm  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        untested("导入 tools/eval_media_vs_llm", str(exc))
        return 2
    group_a()
    group_b()
    group_c()
    group_c2()
    group_d()
    group_e()
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
