#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_media_model_lock.py —— 行 120/121 的**机器半边**：读数齐备才允许锁版本

## 行 120/121 的机器可判部分

验收表 `:263`（行 120）与 `:264`（行 121）的原文都写着「断言四项/五项**全部有读数**才允许
在配置里出现选定版本；缺少任一项而配置已锁版本，**即红**」。这是**纯数据判据**：
不需要真跑 OCR/ASR，只需要判断「有没有锁定」与「读数齐不齐」。

| 段 | 断言 | 今天的对象 |
|---|---|---|
| **M1** | Playbook 的 TS-18 / TS-19 仍写「候选」且写着「过门后才锁版本」；**不出现**「已选定 / 已锁定」 | ✅ Playbook:1308-1309 |
| **M2** | `PMO/implement/阶段3-准备评估.md` 的候选矩阵仍标「主选候选 / 基线候选」 | ✅ :76-80 |
| **M3** | **配置里一旦出现选定版本**，该候选的四项（OCR）/五项（ASR）读数必须齐备；缺一项即红 | ⚠️ **今天没有这份配置** |

## M3 为什么今天不是「绿」

全仓**没有任何模型配置文件**（`config/` 只有 `.ua/config.json`；`contracts/*.json` 无模型字段；
`grep -rln '"ocr"|ocr_model|asr_model' --include=*.json` 为 0）。
所以今天的正确读数是「**未锁定 → 门不适用**」，而不是「门验过了」。
本脚本把它打印成事实行，并且**仍然会红**：当仓库里第一次出现锁定字段时，M3 立刻生效。

★ 没有为凑验收去新建一份 `model-selection.json` —— 那会造出一个谁都不读的配置，
   再让断言去验它自己（§2.4 的「名字出现过 ≠ 拦得住」）。

退出码：0 / 1 / 2（文档读不出）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAYBOOK = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"
STAGE3 = ROOT / "PMO" / "implement" / "阶段3-准备评估.md"

LOCK_KEYS = ("selected_version", "locked_version", "model_version",
             "selected_model", "locked_model")
OCR_READOUTS = ("license", "accuracy", "bbox", "latency")
ASR_READOUTS = ("license", "wer", "segments", "latency", "memory")
CANDIDATE_NAMES = ("paddleocr", "tesseract", "faster-whisper", "faster_whisper", "whisper")


class Untested(Exception):
    pass


def read(path: Path) -> str:
    if not path.is_file():
        raise Untested(f"没有这个文件：{path}")
    return path.read_text(encoding="utf-8")


def ts_row(text: str, code: str) -> str:
    m = re.search(rf"^\|\s*\*\*{re.escape(code)}\*\*\s*\|(.*)$", text, re.M)
    return m.group(1) if m else ""


def check_docs(playbook: str, stage3: str) -> list[str]:
    problems = []
    for code in ("TS-18", "TS-19"):
        row = ts_row(playbook, code)
        if not row:
            problems.append(f"M1 Playbook 里找不到 {code} 行 —— 口径可能变了")
            continue
        if "候选" not in row:
            problems.append(f"M1 {code} 行里不再写「候选」：{row[:80]}")
        if "过门后才锁" not in row and "过门后才锁版本" not in row:
            problems.append(f"M1 {code} 行里找不到「过门后才锁」：{row[:80]}")
        for bad in ("已选定", "已锁定", "selected", "locked"):
            if bad in row:
                problems.append(f"M1 {code} 行里出现「{bad}」—— 先锁版本再测评正是 TS-18/19 要防的")
    if "候选" not in stage3:
        problems.append("M2 阶段3-准备评估.md 里不再出现「候选」字样")
    for name in ("PaddleOCR", "Tesseract"):
        if name not in stage3:
            problems.append(f"M2 阶段3-准备评估.md 里找不到候选 {name}")
    return problems


def check_config(obj, *, source="<config>") -> list[str]:
    """M3：一份配置里若锁了 OCR/ASR 版本，读数必须齐备。纯函数，便于喂样本。"""
    problems = []

    def walk(node, path="$"):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in LOCK_KEYS and isinstance(v, str) and v.strip():
                    low = v.lower()
                    if any(n in low for n in CANDIDATE_NAMES):
                        family = "asr" if ("whisper" in low) else "ocr"
                        need = ASR_READOUTS if family == "asr" else OCR_READOUTS
                        # 读数可以放在同级 readouts/evidence 里
                        got = set()
                        for cand in (node.get("readouts"), node.get("evidence"),
                                     node.get("metrics"), node.get("evaluation")):
                            if isinstance(cand, dict):
                                got |= {str(x).lower() for x in cand}
                            elif isinstance(cand, list):
                                got |= {str(x).lower() for x in cand if isinstance(x, str)}
                        missing = [x for x in need if x not in got]
                        if missing:
                            problems.append(
                                f"M3 {source}{path}.{k}={v!r} 已锁 {family.upper()} 版本，"
                                f"但读数缺 {missing}（需 {need}）")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(obj)
    return problems


def has_lock(obj) -> bool:
    """这份 JSON 里有没有「已锁定的 OCR/ASR 版本」。"""
    found = False

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            for k, v in node.items():
                if (k in LOCK_KEYS and isinstance(v, str) and v.strip()
                        and any(n in v.lower() for n in CANDIDATE_NAMES)):
                    found = True
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return found


def find_configs() -> list[tuple[str, dict]]:
    """扫仓内 JSON，找出**确实**锁了 OCR/ASR 版本的配置（排除 node_modules / web/dist）。"""
    out = []
    for p in sorted(ROOT.rglob("*.json")):
        parts = set(p.parts)
        if "node_modules" in parts or ".git" in parts or "dist" in parts:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if has_lock(d):
            out.append((str(p.relative_to(ROOT)), d))
    return out


def assess(playbook: str, stage3: str, configs: list[tuple[str, dict]]) -> list[str]:
    problems = check_docs(playbook, stage3)
    for rel, d in configs:
        problems += check_config(d, source=rel)
    return problems


def controls() -> int:
    pb = ("| **TS-18** | **OCR 首轮候选**：PaddleOCR（CPU 主选）+ Tesseract（基线）。"
          "…过门后才锁版本 |\n"
          "| **TS-19** | **ASR 首轮候选**：faster-whisper（CPU 主选）+ Whisper 官方（基线）。"
          "…过门后才锁模型体积与版本 |\n")
    s3 = "| 项 | PaddleOCR（主选候选） | Tesseract（基线候选） |\n"
    good_cfg = {"models": {"ocr": {"selected_version": "paddleocr-4.0",
                                   "readouts": {"license": "Apache-2.0", "accuracy": 0.9,
                                                "bbox": 0.88, "latency": 120}}}}
    bad_cfg = {"models": {"ocr": {"selected_version": "paddleocr-4.0",
                                  "readouts": {"license": "Apache-2.0", "accuracy": 0.9}}}}

    def red(frag, pb_=pb, s3_=s3, cfgs=None):
        return any(frag in p for p in assess(pb_, s3_, cfgs if cfgs is not None else []))

    cases = [
        ("正样本：候选标注 + 未锁版本 → 必须绿", lambda: not assess(pb, s3, [])),
        ("★ M1 坏样本：TS-18 改成「已选定」→ 必须红",
         lambda: red("M1", pb_=pb.replace("**OCR 首轮候选**", "**OCR 已选定 v4.0**"))),
        ("M1 坏样本：删掉「过门后才锁」→ 必须红",
         lambda: red("M1", pb_=pb.replace("过门后才锁版本", "直接锁版本"))),
        ("M2 坏样本：阶段3 文档删掉「候选」→ 必须红",
         lambda: red("M2", s3_="| 项 | PaddleOCR | Tesseract |\n")),
        ("★ M3 坏样本：锁了 OCR 版本但只有两项读数 → 必须红",
         lambda: red("M3", cfgs=[("cfg.json", bad_cfg)])),
        ("反向对照：锁了版本且四项读数齐 → 不许误报",
         lambda: not check_config(good_cfg, source="cfg.json")),
        ("★ M3 坏样本：锁了 ASR 版本但缺 memory → 必须红",
         lambda: red("M3", cfgs=[("cfg.json", {"asr": {
             "model_version": "faster-whisper-large-v3",
             "readouts": {"license": "MIT", "wer": 0.08, "segments": True, "latency": 90}}})])),
    ]
    bad = 0
    print("=" * 78)
    print("行 120/121 机器半边 · 读数齐备才允许锁版本（离线对照）")
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
        pb = read(PLAYBOOK)
        s3 = read(STAGE3)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    configs = find_configs()
    problems = assess(pb, s3, configs)
    print("=" * 78)
    print("行 120/121 机器半边 · 候选标注与版本锁门")
    print("=" * 78)
    print(f"  M1 文档：Playbook TS-18 / TS-19")
    print(f"  M2 文档：PMO/implement/阶段3-准备评估.md")
    print(f"  M3 配置：扫描全部 JSON，命中锁定字段的文件 {len(configs)} 个")
    if not configs:
        print("     · 今天**未锁定任何版本** → 门不适用（这是事实行，不是「门验过了」）")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：文档仍标「候选」且写着「过门后才锁」；仓内没有任何已锁定的 OCR/ASR 版本。")
    print("   ⚠️ 这**不等于**行 120/121 通过：它们的另一半是人工实测（跑两份候选、留四项/五项读数），")
    print("      机器侧只覆盖「未锁 + 锁了必须齐」这一半。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
