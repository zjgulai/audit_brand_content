#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_parse_convergence.py —— 行 11：解析结论集合一致（OCR 半边）

## 行 11 原文与覆盖

行 11 要求：固定 `model_id` / `temperature` / `seed`，同图或同视频跑 ≥3 次，把结论
归一化成 `(control_code, location 签名)` 集合，任意两次对称差为空；正文逐字差异
不许导致误判。

| 要求 | 本文件 | 状态 |
|---|---|---|
| 同图跑 ≥3 次，结论集合两两对称差为空 | **P1**（生产入口 `image_file_row → judge_row`，真跑） | ✅ |
| 正文逐字差异不许导致误判 | **P2**（在 OCR 正文前插空格，签名集合必须不变） | ✅ |
| 位置签名（不是逐字比） | **P0**（`(control_code, rule_key, 同名规则内序号)`，对位移免疫） | ✅ |
| 固定 `model_id` / `temperature` / `seed` | — | ❌ **无对象** |
| 视频半边 | — | ❌ 无解析器（`video_stage()` 恒 `cannot_measure`） |
| VLM 半边 | **P3**（无 provider 时必须落 `untested`，不是假装跑过） | ✅（负向） |

**采样配置为什么无对象（五类通道）**：
1. 直接 import：仓内没有模型客户端被生产模块 import。
2. 传递依赖：`judge_entry` 的 `semantic_judge` 是常量 dict；`multimodal_provider`
   只有抽象层，`register_provider()` 全仓 0 调用点。
3. 代码实现：OCR 走 `base/ocr_vision.m` 的 Vision 常量（`recognitionLevel` /
   `usesLanguageCorrection`），**没有** `model_id / temperature / seed` 三个量。
4. 数据：`~/.cache/magpie/models.json` 0 条含 `seed` 字段。
5. 运行时：`release_gate` 读 `sampling_config_hash`，但全仓没有生产者（测试里是硬编码占位）。

所以 #11 不映射：采样配置这一条没有可断言的对象，写「三次一致」会变成
AGENTS §2.4 点名的「名字出现过 ≠ 拦得住」——OCR 在本机是确定性的，断言恒真。
本文件仍把**能验的**（集合收敛、扰动容忍、VLM 必须 untested）做成执行点，
并配反向对照，等采样层真的建起来时可以直接接。

退出码：0 / 1 / 2（无 OCR 可执行、无图、导入失败 → 未测）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: 判据主体：`base/media.py` 的 `image_file_row()` → `judge_row()`。
IMAGE = ROOT / "research" / "landing" / "_evidence" / "media" / "raw" / "17db0b5cc32f86ce.png"
OCR_BIN = ROOT / ".tools" / "bin" / "ocr"


class Untested(Exception):
    pass


def signature(findings: list) -> list[tuple]:
    """位置签名：`(control_code, rule_key, 同名规则内序号)`。

    ★ 刻意**不含** start/end/quote：OCR 正文差一个字符就会让所有偏移平移，
      拿原始偏移做集合比较会得到「假不收敛」——那正是行 11 要排除的误判。
    """
    seen: dict[tuple, int] = {}
    out = []
    for f in findings:
        key = (f.get("control_code"), f.get("rule_key"))
        seen[key] = seen.get(key, 0) + 1
        out.append((f.get("control_code"), f.get("rule_key"), seen[key]))
    return sorted(out)


def run_once(text_override: str | None = None) -> dict:
    if not OCR_BIN.is_file():
        raise Untested(f"没有 OCR 可执行：{OCR_BIN}（gitignored，可由 base/build_ocr.sh 重建）")
    if not IMAGE.is_file():
        raise Untested(f"没有测试图：{IMAGE}")
    try:
        import base.media as M  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 base.media 失败：{type(e).__name__}: {e}")
    try:
        row = M.image_file_row(str(IMAGE))
        if text_override is not None:
            row = dict(row, ocr_text=text_override)
        judged = M.judge_row(row, "file://" + str(IMAGE))
    except Exception as e:  # noqa: BLE001
        raise Untested(f"跑 OCR 判定链失败：{type(e).__name__}: {e}")
    return {
        "text": row.get("ocr_text") or "",
        "findings": judged["judgment"].get("findings") or [],
    }


def check_convergence(runs: list[dict]) -> list[str]:
    problems = []
    sigs = [signature(r["findings"]) for r in runs]
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            if sigs[i] != sigs[j]:
                problems.append(f"P1 第 {i+1} 次与第 {j+1} 次的结论集合不同："
                                f"仅在前者={sorted(set(sigs[i])-set(sigs[j]))[:3]}；"
                                f"仅在后者={sorted(set(sigs[j])-set(sigs[i]))[:3]}")
    if not sigs[0]:
        problems.append("P1 三次运行都没有命中 —— 这张图不能作为收敛样本（换一张能命中 ≥1 条规则的）")
    texts = {r["text"] for r in runs}
    if len(texts) > 1:
        # 逐字差异本身不判红（行 11 允许），但必须**记录**
        print(f"  · 提示：三次 OCR 正文不完全相同（{len(texts)} 种），签名集合仍相等 —— 符合行 11 的容忍要求")
    return problems


def check_perturbation(base_run: dict, perturbed: dict) -> list[str]:
    problems = []
    if perturbed["text"] == base_run["text"]:
        problems.append("P2 扰动没生效（正文没变）—— 这条断言会恒真")
    if not perturbed["text"].startswith(" ") and not base_run["text"].startswith(" "):
        problems.append("P2 扰动不是「在正文前插空格」—— 请检查样本构造")
    if signature(base_run["findings"]) != signature(perturbed["findings"]):
        problems.append("P2 正文插一个空格后结论集合变了 —— 逐字差异导致了误判")
    return problems


def check_vlm_untested() -> list[str]:
    """P3：没有 provider 时，多模态分析必须落 untested，不许静默当成 ok。"""
    try:
        from base import multimodal_provider as MP  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return [f"P3 导入 multimodal_provider 失败：{type(e).__name__}: {e}"]
    try:
        # 任务名是封闭枚举（scene_semantics / mark_symbol / av_alignment）
        out = MP.analyze({"kind": "image", "uri": "inline:verify", "bytes": b"x"},
                         ["scene_semantics"])
    except Exception as e:  # noqa: BLE001
        return [f"P3 analyze() 抛了异常（应返回 untested）：{type(e).__name__}: {e}"]
    status = (out or {}).get("status")
    if status != "untested":
        return [f"P3 无 provider 时 analyze() 的 status={status!r}，预期 untested ——"
                " 不许把「没跑」当成「跑过了」"]
    return []


def assess(runs: list[dict], perturbed: dict) -> list[str]:
    return (check_convergence(runs) + check_perturbation(runs[0], perturbed)
            + check_vlm_untested())


def controls() -> int:
    def f(code, key):
        return {"control_code": code, "rule_key": key, "location": {"kind": "text_span", "start": 0, "end": 1}}

    good = [f("U01", "T3.2"), f("U01", "T3.2")]
    cases = [
        ("P0 签名对偏移免疫：同一批结论不同 start → 签名相同",
         lambda: signature([dict(good[0], location={"kind": "text_span", "start": 9, "end": 10})])
         == signature([good[0]])),
        ("★ P1 反向对照：删掉一条 finding → 签名集合必须不同",
         lambda: signature(good) != signature(good[:1])),
        ("★ P1 反向对照：改掉 control_code → 签名集合必须不同",
         lambda: signature(good) != signature([dict(good[0], control_code="H01"), good[1]])),
        ("P0 同一规则命中两次 → 序号区分，不会互相吞掉",
         lambda: len(signature(good)) == 2),
    ]
    bad = 0
    print("=" * 78)
    print("行 11 · 结论集合签名（离线纯函数对照）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    try:
        runs = [run_once() for _ in range(3)]
        perturbed = run_once(" " + runs[0]["text"])
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        print("   这不是「结论一致」，是**这次没跑成** —— 退 2（未测 ≠ 通过 ≠ 红）。")
        return 2
    problems = assess(runs, perturbed)
    print("=" * 78)
    print("行 11 · 同图跑 3 次（真实 OCR + 真实判定链）")
    print("=" * 78)
    print(f"  样本：{IMAGE.relative_to(ROOT)}")
    print(f"  正文：{len(runs[0]['text'])} 字；findings：{[len(r['findings']) for r in runs]}")
    print(f"  签名：{signature(runs[0]['findings'])[:3]} …")
    print()
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：三次结论集合两两相同；插入空格后仍相同；无 provider 时 VLM 落 untested。")
    print("   ⚠️ 行 11 的『固定 model_id/temperature/seed』**没有对象**（OCR 是 Vision 编译期常量），")
    print("      所以 #11 不映射；本脚本只覆盖有对象的那三件。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
