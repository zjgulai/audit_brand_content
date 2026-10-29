#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_cn_media_samples.py —— 合成中文媒体样例（图片 / 海报）

## 它为什么存在

2026-10-28/29 实测：**这个项目今天没有任何中文图片素材**。

| 来源 | 数量 | 中文为主 |
|---|---|---|
| 仓内已跟踪图片 | 6 | 0（全是插件图标） |
| 落地页抓取素材 | 131（61 张有字） | **0** |
| 飞书表图片直链 | 72 | **0**（指向 cdn.shopify.com 的海外站素材） |
| gold pilot | 25 | **2**（设计需求稿，不是待审广告） |

而规则库是**中文关键词表**。所以在真实素材上，本系统对图片的规则命中
永远是 0 —— 那不是「判得准」，是「规则不认识这些字」。

本工具用**真实中文字体**把待审文案渲染成 PNG，让「OCR → 规则」这条链路
第一次能在中文上被验证。

## ★★ 它能验什么、不能验什么（必须写清）

**能验**：
· OCR 在中文上的识别质量（含标点、数字、百分比、换行）；
· 规则引擎对中文文案的命中（极限词 / 临床宣称 / 资质背书…）；
· 「命中之后判定怎么走」整条链路。

**不能验**（这些是合成素材的固有边界）：
· 真实设计素材的**画面复杂度**（排版、配色、人物、场景、图标）；
· 多模态的**画面语义**能力（合成图只有纯文字，没有画面可看）；
· OCR 在复杂背景上的鲁棒性（白底黑字是最容易的一档）。

★ 所以**不许把本工具产出的命中率当成「图片审核准确率」往上报**。
  它验的是「中文文本 → 规则」这一环，而这一环此前完全没有被验证过。

## 红线（AGENTS.md §2.6）

产出**落在仓外**（默认 `~/audit-data/cn-samples`），不进公开仓。
本工具**不下载任何东西**，只写本地渲染结果，因此不在
`tools/download_callers.json` 的登记范围里。

## 依赖

只用 macOS 自带工具：
· `qlmanage -t`（Quick Look 渲染 HTML → PNG），字体走系统 PingFang SC；
· 不装 PIL / ImageMagick / Swift 工具链 —— 本机 clang 与 SDK 27 不匹配，
  Swift 也编不过（实测），而 `qlmanage` 可用。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_OUT = Path.home() / "audit-data" / "cn-samples"

#: 合成的样例集。
#:
#: ★ 每条都写清「为什么它必须在这里」—— 这些不是随便凑的文案，
#:   每一条都对准规则库里**确实存在**的一类判定。
#:   加一条就要说明它覆盖哪类，否则集合会慢慢变成「想写什么写什么」。
SAMPLES: List[Dict[str, Any]] = [
    {
        "key": "hyperbole",
        "label": "绝对化极限词",
        "text": "母婴行业唯一同时获得三项资质的产品，效果最佳，全场第一。",
        "expect": "应有命中（极限词/绝对化）",
    },
    {
        "key": "clinical",
        "label": "医疗与临床宣称",
        "text": "经三甲医院产科临床观察，连续使用四周后92.6%的受试者泌乳量显著提升。",
        "expect": "应有命中（医疗/临床宣称）",
    },
    {
        "key": "medical-device",
        "label": "医疗器械级宣称",
        "text": "采用医用级硅胶材质，达到医疗器械生产标准，可辅助治疗乳腺堵塞。",
        "expect": "应有命中（医疗术语）",
    },
    {
        "key": "endorse-fda",
        "label": "权威认证背书",
        "text": "本品已获FDA认证，并通过CE、SGS双重检测，品质达到国际标准。",
        "expect": "应有命中（资质背书）",
    },
    {
        "key": "safety-claim",
        "label": "绝对安全承诺",
        "text": "100%安全无副作用，绝对不含任何有害成分，婴幼儿可放心长期使用。",
        "expect": "应有命中（绝对安全）",
    },
    {
        "key": "clean-product",
        "label": "完全合规的产品说明",
        "text": "本品为食品级硅胶材质，可高温消毒，建议每日清洗后自然晾干，存放于阴凉干燥处。",
        "expect": "不应命中任何规则（合规文案）",
    },
    {
        "key": "neutral",
        "label": "无商业诉求的日常文字",
        "text": "记录一个普通妈妈的清晨，喂奶、换尿布、再睡一会儿。",
        "expect": "不应命中任何规则（中性文字）",
    },
]

#: 画布尺寸。★ 800×400 与落地页常见的广告图比例接近，
#: 且 OCR 在这个尺寸上实测可读（真跑过：41 字全读出）。
CANVAS = (800, 400)


def _html_for(text: str, *, title: str = "") -> str:
    """把文案包成一张「广告图」样式的 HTML。

    ★ 刻意做成白底黑字 + 大字：这是 OCR 最容易的一档。
      用复杂背景会让「识别失败」与「规则不命中」混在一起，
      而本工具要验的是后者。
    """
    w, h = CANVAS
    return """<!doctype html>
<html><head><meta charset="utf-8"><style>
  html,body{{margin:0;padding:0;width:{w}px;height:{h}px;overflow:hidden}}
  body{{background:#ffffff;font-family:"PingFang SC","Hiragino Sans GB",sans-serif;
        color:#111111;padding:44px 48px;box-sizing:border-box;
        display:flex;flex-direction:column;justify-content:center}}
  .brand{{font-size:20px;letter-spacing:2px;color:#8a8a8a;margin-bottom:18px}}
  .body{{font-size:38px;line-height:1.45;font-weight:600}}
  .foot{{margin-top:22px;font-size:16px;color:#9a9a9a}}
</style></head><body>
  <div class="brand">momcozy</div>
  <div class="body">{text}</div>
  <div class="foot">{foot}</div>
</body></html>""".format(w=w, h=h, text=html.escape(text), foot=html.escape(title))


def render(text: str, out_png: Path, *, title: str = "", workdir: Path) -> Dict[str, Any]:
    """渲染一条文案成 PNG。返回 {ok, path, reason}。"""
    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / (out_png.stem + ".html")
    src.write_text(_html_for(text, title=title), encoding="utf-8")

    # ★ `qlmanage -t` 会生成 `<stem>.html.png`，放在 -o 指定的目录里。
    #   它的退出码不可靠（有时成功仍返非 0），所以判据是**文件出没出来**。
    try:
        subprocess.run(
            ["qlmanage", "-t", "-s", str(CANVAS[0]), "-o", str(workdir), str(src)],
            capture_output=True, timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": "qlmanage 调用失败：%s" % (type(exc).__name__,)}

    produced = workdir / (src.name + ".png")
    if not produced.is_file() or produced.stat().st_size == 0:
        return {"ok": False, "reason": "qlmanage 没有产出 PNG"}
    out_png.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(produced, out_png)
    return {"ok": True, "reason": "", "bytes": out_png.stat().st_size}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="合成中文媒体样例（图片/海报）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录（必须在仓外）")
    ap.add_argument("--json", default="", help="同时写一份清单 JSON")
    args = ap.parse_args(argv)

    out = Path(args.out).expanduser().resolve()
    repo_root = Path(__file__).resolve().parent.parent.resolve()
    # ★ 红线：产出不许进仓（§2.6）。这里在**写之前**断言，不是写之后再检查。
    if str(out).startswith(str(repo_root) + os.sep):
        print("❌ 输出目录在仓内：%s（下载/合成物不进公开仓）" % out, file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    work = out / "_html"
    rows = []
    for s in SAMPLES:
        target = out / (s["key"] + ".png")
        r = render(s["text"], target, title=s["label"], workdir=work)
        rows.append({
            "key": s["key"], "label": s["label"], "text": s["text"],
            "expect": s["expect"], "path": str(target) if r["ok"] else None,
            "bytes": r.get("bytes"), "ok": r["ok"], "reason": r.get("reason", ""),
        })
        status = "✅" if r["ok"] else "❌"
        print("%s %-16s %-22s %s" % (
            status, s["key"], s["label"],
            ("%d B" % r["bytes"]) if r["ok"] else r.get("reason", "")))

    ok_n = sum(1 for r in rows if r["ok"])
    print("\n生成 %d / %d 张 → %s" % (ok_n, len(rows), out))

    if args.json:
        Path(args.json).write_text(
            json.dumps({"out": str(out), "samples": rows}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print("清单：%s" % args.json)

    # ★ 退出码：全部生成成功才是 0。少一张就没法拿它当评测集用。
    return 0 if ok_n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
