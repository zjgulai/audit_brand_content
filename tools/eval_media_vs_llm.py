#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_media_vs_llm.py —— 本系统 vs 裸大模型：审图的速度与质量对比

## 它回答什么

委托方要求：「配图片/视频的真实样例，测审核速度和质量，基线就是纯大模型审核。」

于是本工具对**同一批真实图片**跑两条路：

| 路径 | 是什么 | 产出 |
|---|---|---|
| **system** | 本项目的规则引擎 + 多模态观察（`judge_entry` 全链路） | findings + decision |
| **llm** | 同一网关的**裸大模型**，只给提示词与图，不给规则库 | 模型自述的观察与问题 |

两者用**同一份 gold**（真人审核结论）评质量，用**同一次墙钟**评速度。

## ★ 为什么基线必须同网关

跨网关比延迟不公平：网络抖动、限流策略、模型规格都不同，那时测出来的是
「两家的服务差异」，不是「有没有规则引擎的差异」。委托方同意的口径是
**同一网关的裸大模型** —— 唯一变量是规则引擎。

## ★ 质量怎么算才算数

直接比「结论对不对」会变成两个模型互相打分。所以用**已有人工标注**的
`~/audit-data/gold/pilot/gold.json`（仓外，10 条真人结论 / 25 张图）：

- gold 的 `原因分类` + `原因文本` 是**人的判断**；
- 两侧的产出各自映射到「这条记录判出了哪些问题」；
- 命中口径沿用 `tools/eval_review_gold.py` 的既有规则（类型一致 + 文本相似），
  **不另造一套** —— 两套匹配规则必然漂移，而漂移的那一套会让结论反过来。

## ★ 先说清楚本系统今天对图片能做到什么（否则读数会被误读）

2026-10-28 实测：

| 能力 | 状态 | 实测读数 |
|---|---|---|
| 图内文字（OCR） | ✅ **可用** | `ensure_ocr()` 会编译/复用 `.tools/bin/ocr`（`base/ocr_vision.m` + `base/build_ocr.sh` 都在）。真图实测：285 字 / 15 段 / `mean_conf=0.667` / 420ms。 |
| 画面语义（多模态） | ❌ 未配凭据 | `MULTIMODAL_*` 四个环境变量全空 → `readiness()` 落 `untested` → `multimodal_note = "未接入多模态分析"`。 |

### ★★★ 真正的边界：**语言**，不是 OCR

gold 的 24 张有字图里，**22 张是拉丁文（德/英），只有 2 张中文**
（`reczz28NIkGoVgYG__s2_*`，而且是设计需求稿、本身不含违规文案）。

而规则库是**中文关键词表**。所以在 22 张拉丁文图上：

    19 条规则全部跑过（control_points_applied 有 19 项）
    findings = 0
    label = REVIEW（覆盖 partial）

**这不是「判得准」，是「规则不认识这些字」。** 这正是本项目反复记的那个病
（AGENTS.md §2.4.1）：**产出看起来正常，没有任何东西会红。**

★ 所以本工具的输出必须把「0 条 finding」与下面这些一起打：
  `ocr_chars`（有没有读到字）、`cjk_ratio`（读到的字是不是中文）、
  `multimodal_note`（有没有看画面）。只报一个数字会被读成「误报少」。

### 更正过一次，两个版本都留着

第一版这里写的是「OCR 引擎依赖的 `base/media_vision.py` 不存在（ImportError）」，
并据此断言「本系统审图什么也看不见」。**那是错的** —— 我当时按文件名猜了一个
不存在的模块（`media_vision`），而真身是 `base/ocr_vision.m` + 编译出的
`.tools/bin/ocr`，它工作正常。

★ 教训：**「我在 import 里没看到它」不等于「它不存在」**。
判据必须是真跑一次（`ocr_file()` 返回什么），不是读一遍 import 列表。

## ★ 三态（不是二态）

| 状态 | 含义 |
|---|---|
| `ok` | 两侧都拿到了产出，指标算得出来 |
| `untested` | 凭据没配 / 模型不可用 / gold 读不出 —— **指标为 null，不是 0** |
| `error` | 拿到了产出但形状坏了 |

退出码：0 有读数 / 1 有红（形状坏了） / 2 全部未测（凭据缺失等）。

**未测不是「差不多」，也不是「两边一样」。** 凭据没配时本工具一条指标都不给。

## 用法

    # 先看能不能跑（不联网）
    python3 tools/eval_media_vs_llm.py --check

    # 真跑（会联网、会把图片发给网关）
    python3 tools/eval_media_vs_llm.py --limit 5 --out /tmp/media-eval.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD_DIR = Path(os.path.expanduser("~/audit-data/gold/pilot"))


def say(*args: Any) -> None:
    """打印并**立刻刷出**。

    ★ 为什么不用裸 `print`：本工具单张要 2.5–3.4 分钟（本系统 `scene_semantics`
      83s + `mark_symbol` 11s + baseline 74s），15 张要 40–50 分钟。
      而 Python 在 stdout 被重定向到文件时是**块缓冲**的 —— 裸 `print`
      会让整轮跑完才一次性落盘。

      实测代价（2026-10-29）：`nohup ... > log` 跑了 11 分钟，
      `wc -l log` 是 **0 行** —— 看起来像「卡住了」，实际在正常干活。
      一个长任务让人以为它死了，和它真的死了，处理方式完全不同。
    """
    print(*args, flush=True)

#: 基线模型。★ 取 `tools/multimodal_client.py` 的 `LIVE_PROBE` 里**实测 ok** 的那几个，
#: 不写一个「听起来最强」但没探过的 id —— 那样的基线挂了会被读成「大模型不行」。
BASELINE_MODELS = ("glm-5.3-flash",)

#: 基线单次请求超时（秒）。实测依据见 `run_baseline` 里的注释。
BASELINE_TIMEOUT_S = 120.0

#: 给裸模型的提示词。
#:
#: ★ 关键设计：**不给规则库、不给控制点编号**。给了就成了「本系统的规则 + 模型的眼看」，
#:   而那正是被测对象。基线要的是「一个聪明人只看这张图会说什么」。
#:
#: ★ 但也不能问得太空（「这图有问题吗」会得到「看起来没问题」）。
#:   所以按**人审时会问的角度**问，与 `TASK_PROMPTS` 的 `scene_semantics` 同一取向，
#:   只是不提供任何规则条文 —— 这样两侧的差别才是「规则库」带来的。
BASELINE_PROMPT = (
    "你是一名中文市场广告的合规审核员。看这张广告素材图，回答：\n"
    "① 画面在演示什么使用场景；\n"
    "② 画面是否暗示了具体功效、疗效或安全承诺；\n"
    "③ 画面里有没有违规或需要人工复核的元素（如果有，指出位置与原因）；\n"
    "④ 如果有问题，属于哪一类（医疗宣称 / 绝对化表述 / 资质背书 / 使用场景不当 / 其他）。\n"
    "只描述你确实看到的；看不清就写「看不清」，不要推测。\n"
    '输出一行 JSON：{"findings":[{"category":"...","region":"...","reason":"..."}]}'
)


def _untested(reason: str) -> Dict[str, Any]:
    return {"status": "untested", "reason": reason, "metrics": None}


def images_for_market(records: List[Dict[str, Any]], market: str) -> List[Dict[str, Any]]:
    """按市场筛图。返回 `[{record_id, image, lang, gold_category, ocr_text}]`。

    ★ 必须**先 OCR 再筛**：光看文件名（`recvw7XIUgdDyv__s0_0.png`）看不出语言。
      这就是为什么第一轮我用「前 3 条记录」当样本时，恰好全是德文和中文，
      于是得出了「规则库不认中文、所以整条链路不通」的错误结论 ——
      真实原因是**我筛错了样本**。
    """
    from base import media as M

    out: List[Dict[str, Any]] = []
    for rec in records:
        for img in _images_of(rec):
            try:
                text = (M.ocr_file(img).get("text") or "").strip()
            except Exception:  # noqa: BLE001
                text = ""
            lang = classify_language(text)
            if market == MARKET and lang != "en":
                continue
            out.append({
                "record_id": rec.get("record_id"),
                "image": img,
                "lang": lang,
                "gold_category": rec.get("原因分类"),
                "ocr_text": text,
            })
    return out


def _load_gold() -> Dict[str, Any]:
    """读 gold。★ 读不出就是 untested —— 「没有 gold」与「gold 为空」不同。"""
    p = GOLD_DIR / "gold.json"
    if not p.is_file():
        return {"status": "untested", "reason": "gold 不在盘上：%s" % p, "records": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"status": "until", "reason": "gold 读不出：%s" % (exc,), "records": []}
    if not isinstance(data, list) or not data:
        return {"status": "untested", "reason": "gold 不是非空数组", "records": []}
    return {"status": "ok", "reason": "", "records": data}


#: 市场口径。★ 委托方 2026-10-29：「不用再测中文，我们只关注北美市场」。
#:
#: 这句话直接决定评测集怎么筛：gold 的 25 张里混着德语（3）、中文（3）、
#: 法语（1）、英文（16）—— 那是 Momcozy 各国站点的素材。
#: 拿德语图去评「北美市场的合规判定」，测出来的是规则库的语言覆盖缺口，
#: 而不是北美业务的真实表现。两者混在一起报，读数会被双向误读。
MARKET = "north-america"

#: 判定「这张图是英文素材」的口径。
#:
#: ★ 不用 OCR 语言识别库（没有、也不该为这个装一个）。
#:   用**功能词**判：德语/法语各有极高频的功能词（der/die/und、le/la/des），
#:   而英文的功能词集合与它们几乎不重叠。三条以上才算，避免把
#:   「德语品牌名 + 英文文案」误判。
_DE_WORDS = re.compile(
    r"\b(der|die|das|und|nicht|dein|deine|für|mit|ist|ein|eine|braucht|"
    r"gefühl|sicherheit|mehr|kann|wenn|dein)\b", re.I)
_FR_WORDS = re.compile(
    r"\b(le|la|les|des|une|un|est|pour|avec|votre|nous|dans|plus|"
    r"vous|sur|par)\b", re.I)


def classify_language(text: str) -> str:
    """判断一段 OCR 文字主要是什么语言。返回 `en` / `de` / `fr` / `zh` / `unk`。

    ★ 这是**粗判**，只用来筛评测集，不用于任何判定。
      判错的后果是「某张图进/出评测集」，不是「结论错了」——
      所以不用更精细的模型，用功能词就够。
    """
    if not isinstance(text, str) or not text.strip():
        return "unk"
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk > latin * 0.3 and cjk >= 5:
        return "zh"
    de = len(_DE_WORDS.findall(text))
    fr = len(_FR_WORDS.findall(text))
    if de >= 3 and de >= fr:
        return "de"
    if fr >= 3 and fr > de:
        return "fr"
    if latin >= 20:
        return "en"
    return "unk"


def _images_of(record: Dict[str, Any]) -> List[Path]:
    out = []
    for img in record.get("images") or []:
        if not img.get("ok"):
            continue
        p = GOLD_DIR / "images" / str(img.get("file") or "")
        if p.is_file():
            out.append(p)
    return out


# ─────────────────────────────────────────────── 凭据读数

def check_env() -> Dict[str, Any]:
    """只读环境变量，**不读凭据文件**（AGENTS.md §2.6 第 3 条）。"""
    from tools.multimodal_client import GATEWAY_ENV

    rows = {}
    for gw, (base_env, key_env) in GATEWAY_ENV.items():
        base = (os.environ.get(base_env) or "").strip()
        key = (os.environ.get(key_env) or "").strip()
        rows[gw] = {
            "base_set": bool(base),
            "key_set": bool(key),
            # ★ 只报「配没配」，绝不打印值本身。
            "ready": bool(base and key),
            "missing": [n for n, v in ((base_env, base), (key_env, key)) if not v],
        }
    return rows


# ─────────────────────────────────────────────── 两条路径

def _cjk_ratio(text: str) -> Optional[float]:
    """中文字符占「有意义的字」的比例。★ 空格/标点/数字不计入分母。

    为什么需要它：规则库是**中文关键词表**。一段德语文案照样能读出 285 个字，
    OCR 是成功的、规则也全跑了，但一个词都命不中 —— 那时「0 条 finding」
    与「合规通过」长得一模一样。这个比例就是用来分开这两者的。

    ★ 分母为 0（读不到字）时返回 None，不是 0.0 ——
      「没有字可判」与「有字但一个中文都没有」是两件事。
    """
    if not isinstance(text, str):
        return None
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        return None
    return round(cjk / total, 3)


#: 评测用 principal。★ 只用于 `prepare()` 的权限上下文，不写入任何存储。
EVAL_PRINCIPAL = {
    "id": "eval-runner", "tenant": "t1", "roles": ["dp3"],
    "product_lines": ["pump", "wearable", "feeding", "skincare"],
}

_INGESTOR = None


def _ingestor():
    """评测用的 `SubmissionIngestor`（单例）。

    ★ `media_roots` 设成 gold 图片目录：进件层会校验「路径在允许根内」，
      不设就会拒（那是安全边界，不是可选项）。
      这也让评测走上与生产**完全一致**的路径校验。
    """
    global _INGESTOR
    if _INGESTOR is None:
        from base.submission_service import SubmissionIngestor

        roots = sorted({str(p.parent) for rec in (_load_gold().get("records") or [])
                        for p in _images_of(rec)})
        # ★ 媒体进件开关必须显式打开。生产里它由 `REVIEW_MEDIA_INGEST` 控制，
        #   而判据**只读环境变量**（`ingest_media_enabled()`，不设模块常量 ——
        #   那种写法下「自证测的开关」与「生产读的开关」会变成两个东西）。
        #
        #   ★ 本工具在这里 setdefault 而不是硬设：如果调用方显式关了它，
        #     那应当尊重（评测跑不了媒体，会带着原因落 untested）。
        #     但评测**本来就要审图片**，不打开就什么都测不了，
        #     所以缺省打开是这里唯一合理的行为。
        os.environ.setdefault("REVIEW_MEDIA_INGEST", "1")
        _INGESTOR = SubmissionIngestor(media_roots=roots)
    return _INGESTOR


def _multimodal_for(unit: Dict[str, Any]):
    """给 unit 造多模态注入点。**与生产同一条路**（`media_analyze.build_analyze`）。

    ★ 不在本文件里判断「凭据配没配」—— 那是 `build_analyze` 的职责。
      它未配时返回 None，`judge_entry` 据此落「未接入多模态分析」；
      这里若再判一次，就成了两个判据（改一处必漂另一处）。
    """
    try:
        from base import media_analyze as MA

        local = unit.get("_media_local_path")
        if not isinstance(local, str) or not local.strip():
            return None
        return MA.build_analyze(resolve_path=lambda ref: Path(local))
    except Exception:  # noqa: BLE001
        # 接线层自己坏了 → 不注入。判定层会落未接入，
        # **不会**被读成「没有问题」。
        return None


def run_system(image: Path, *, clock=time.perf_counter) -> Dict[str, Any]:
    """本系统：**真实进件链**（OCR → unit → 规则引擎 → 判定）。

    ★★ 第一版这里手工拼了一个 `{"text": "", "has_text": False}` 的 unit
      直接喂给 `judge_unit` —— 那等于**跳过 OCR**，测出来的是
      「本系统在空正文上判得如何」，不是「本系统审这张图判得如何」。
      实测症状：`ocr_chars` 恒为 0，而真跑 `image_file_row()` 明明读出 285 字。

      这不只是评测失真：它把「OCR 可用」这件事测成了不可用，
      会让后续所有结论建立在错误前提上。

    ★ 现在走 `row_to_unit(image_file_row(...))` —— 与生产进件**同一条路**。
      OCR 的耗时也算进本系统的墙钟里（否则速度对比对本系统有利而无理）。
    """
    from base import judge_entry, media as M

    t0 = clock()
    try:
        # ★★★ 走**完整**进件链，不是「row_to_unit 拼一半」。
        #
        #   实测踩过两次，都栽在这里：
        #   ① 第一版手工拼 `{"text": "", "has_text": False}` → 跳过 OCR；
        #   ② 第二版改用 `row_to_unit(image_file_row(...))` → OCR 对了，
        #      但 `_media_local_path` 是 None（那个字段由
        #      `SubmissionIngestor._build_media_unit` 写），于是多模态
        #      **永远注入不进去**，`multimodal_note` 恒为「未接入多模态分析」——
        #      而凭据明明配好了。
        #
        #   `prepare()` 是生产的完整进件链：OCR → unit → 回填本地路径 →
        #   校验 → 组装 payload。它**不写 authority**（那是 execute 的事），
        #   所以拿它做评测不会污染数据。
        ing = _ingestor()
        prepared = ing.prepare(
            {
                "submission_id": "eval-" + image.stem,
                "content_type": "图片",
                "content_stage": "final_content",
                "entry_channel": "上传文件",
                "source": {"kind": "image", "uri": str(image)},
                "product_line": "pump",
            },
            principal=EVAL_PRINCIPAL,
        )
        unit = prepared["payload"]["content"]
        # ★★ 必须注入多模态 —— 否则测的是**降级版系统**。
        #
        #   实测踩过：第一版没有这一行，于是 `multimodal_note` 全是
        #   「未接入多模态分析」，而凭据明明是配好的。症状读起来像
        #   「系统能力不行」，实际是**评测工具少传了一个参数**。
        #
        #   ★ 与生产同一条路（`submission_service._multimodal_analyze` 也是
        #     `MA.build_analyze(resolve_path=...)`），不另写一套。
        #   ★ 不在这里判断凭据 —— `build_analyze` 未配时返回 None，
        #     `judge_entry` 据此落「未接入多模态分析」。两个判据必然漂移。
        analyze = _multimodal_for(unit)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error",
                "reason": "进件失败：%s: %s" % (type(exc).__name__, exc),
                "ms": None, "findings": [], "decision": None,
                "ocr_chars": 0, "cjk_ratio": None, "rules_applied": 0}
    try:
        out = judge_entry.judge_unit(
            unit, multimodal_analyze=analyze, clock=time.time)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "%s: %s" % (type(exc).__name__, exc),
                "ms": None, "findings": [], "decision": None}
    ms = (clock() - t0) * 1000.0
    text = unit.get("text") or ""
    return {
        "status": "ok",
        "reason": "",
        "ms": round(ms, 3),
        # ★★ `status` 与 `produced_by` 必须一起落盘。
        #
        #   实测代价（2026-10-29）：第一版只存 control_code/severity/quote，
        #   于是「规则命中（confirmed）」与「事实类 candidate」在输出里
        #   **长得完全一样** —— 读数上看到 2 条 finding，读不出它们是
        #   哪一种，也就答不了「自动升级到底产出了几条」。
        #   那正是本文件反复记的那个形状：存了读数，读不出它说的是什么。
        "findings": [
            {"control_code": f.get("control_code"), "severity": f.get("severity"),
             "status": f.get("status"), "produced_by": f.get("produced_by"),
             "fact_label": f.get("fact_label"),
             "quote": f.get("quote")}
            for f in (out.get("findings") or [])
        ],
        # 单独报一份事实类候选的条数 —— 与规则命中分开数，
        # 否则「自动升级有没有生效」这件事会混进总数里看不出来。
        "fact_candidates": len(out.get("fact_candidates") or []),
        "decision": out.get("label"),
        "observations": len(out.get("multimodal_observations") or []),
        # ★★ 观察**原文**必须一起落盘，不只是条数。
        #
        #   实测代价（2026-10-29）：第一版只存了 `observations` 的条数，
        #   于是跑完 5 张之后想做「观察质量对照」时，手上只有「13 条」这个数字，
        #   一条原文都没有 —— 只能重跑 40 分钟。
        #   ★ 这又是那个形状：**存了一个读数，但读不出它说的是什么。**
        #
        #   条数保留（摘要用），原文另存（复核用）。两者都要。
        "observation_texts": [
            {"task": o.get("task"), "statement": o.get("statement"),
             "status": o.get("status"), "reason": o.get("reason")}
            for o in (out.get("multimodal_observations") or [])
        ][:40],
        "multimodal_note": out.get("multimodal_note"),
        # ★★ 下面三个是「0 条 finding」的**解释字段**，不是装饰。
        #    OCR 读到多少字、其中多少是中文、规则跑了几条 ——
        #    缺了它们，「0 条」会被读成「判得准」。
        "ocr_chars": len(text.strip()),
        "cjk_ratio": _cjk_ratio(text),
        "rules_applied": len(
            (out.get("ir") or {}).get("coverage", {}).get("control_points_applied") or []),
    }


def run_baseline(image: Path, *, model: str, env=None,
                 clock=time.perf_counter) -> Dict[str, Any]:
    """裸大模型：只给提示词与图。不注入任何规则。"""
    try:
        from tools.multimodal_client import GatewayClient
    except Exception as exc:  # noqa: BLE001
        return {"status": "untested", "reason": "客户端不可用：%s" % (exc,),
                "ms": None, "findings": [], "raw": ""}

    try:
        # ★ 超时与重试必须按**图片**调，不能用客户端默认值。
        #
        #   实测（2026-10-28，tokenhub + glm-5.3-flash）：
        #     · 纯文本请求      2.4s
        #     · 缩到 36KB 的图  6.9s
        #     · 原图 2.3MB     10.4s
        #   而 gold 里有 4.8MB 的图，base64 后近 5MB。
        #   默认 60s × 3 次重试 = 最长 180s/张，25 张就是 75 分钟，
        #   而超时后**拿不到任何读数** —— 那比慢更糟。
        #
        #   所以：单次 120s（够 5MB 图 + 抖动），重试 1 次（失败就是失败，
        #   重试一次仍失败说明不是抖动）。总上界 240s/张。
        client = GatewayClient.from_env(
            "tokenhub", model=model, env=env,
            timeout=BASELINE_TIMEOUT_S, retry_attempts=1)
    except Exception as exc:  # noqa: BLE001
        return {"status": "untested", "reason": "凭据未配：%s" % (exc,),
                "ms": None, "findings": [], "raw": ""}

    # ★ 复用客户端的 HTTP 层，但**自定义提示词**：`analyze_task` 用的是
    #   `TASK_PROMPTS`（那是本系统的提示词，带「为合规审核做观察」的取向），
    #   用来当基线会把本系统的口径混进基线。所以这里自己发一次请求。
    import base64
    payload_bits = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": BASELINE_PROMPT},
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(
                        image.read_bytes()).decode("ascii"),
                }},
            ],
        }],
        "temperature": 0,
    }
    t0 = clock()
    try:
        resp = client.transport(
            client.endpoint(),
            {"Content-Type": "application/json",
             "Authorization": "Bearer " + client.api_key},
            json.dumps(payload_bits, ensure_ascii=False).encode("utf-8"),
            client.timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "%s: %s" % (type(exc).__name__, exc),
                "ms": None, "findings": [], "raw": ""}
    ms = (clock() - t0) * 1000.0

    # ★ `HttpResult` 的字段是 `status` / `body`(**str**) / `error`(**str**)。
    #   第一版按 `body: bytes` 读、并且只看 `status`，于是网络层失败时
    #   status=0、body 为空 —— 输出成「HTTP 0：」加一片空白，而真正的原因
    #   （连接被拒 / DNS 失败 / 超时）就在 `error` 里，一个字都没打出来。
    #   这正是本项目最忌讳的形状：**失败被渲染成空白**。
    status = getattr(resp, "status", None)
    body = getattr(resp, "body", "") or ""
    text = body if isinstance(body, str) else str(body)
    err = (getattr(resp, "error", "") or "").strip()
    if status != 200:
        # ★ 429 是限流（重试就好），不是「模型不行」—— 两者必须报得不一样。
        kind = "untested" if status in (401, 403, 404, 429) else "error"
        detail = err or text[:200]
        if status == 0:
            detail = "网络层失败（status=0）：%s" % (err or "传输层没有给出原因")
        return {"status": kind, "reason": detail[:200],
                "ms": round(ms, 3), "findings": [], "raw": (err or text)[:400]}

    try:
        doc = json.loads(text)
        content = doc["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        return {"status": "error", "reason": "响应不是 OpenAI 形状",
                "ms": round(ms, 3), "findings": [], "raw": text[:400]}

    return {
        "status": "ok",
        "reason": "",
        "ms": round(ms, 3),
        "findings": _parse_baseline_findings(content),
        "decision": None,
        "raw": content[:600],
    }


def _parse_baseline_findings(content: str) -> List[Dict[str, Any]]:
    """从模型自由文本里抠 JSON。抠不到返回空列表并**保留原文**。

    ★ 不许因为「没解析出 JSON」就当成「模型说没问题」——
      那是把格式失败读成质量满分。原文由调用方一并留存。
    """
    if not isinstance(content, str):
        return []
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        doc = json.loads(content[start:end + 1])
    except Exception:  # noqa: BLE001
        return []
    items = doc.get("findings")
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append({
            "category": it.get("category"),
            "region": it.get("region"),
            "reason": it.get("reason"),
        })
    return out


# ─────────────────────────────────────────────── 指标

def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """把逐条读数聚合成两侧的速度与产出统计。

    ★ 分母为 0 时给 `None`，不写 0 ——「一个样本都没测成」与「测了但耗时 0ms」
      必须长得不一样。
    """
    def side(key: str) -> Dict[str, Any]:
        ms = [r[key]["ms"] for r in rows
              if r[key] and isinstance(r[key].get("ms"), (int, float))]
        ok_rows = [r for r in rows if r[key] and r[key].get("status") == "ok"]
        n_findings = [len(r[key].get("findings") or []) for r in ok_rows]
        return {
            "tested": len(ok_rows),
            "untested": sum(1 for r in rows
                            if r[key] and r[key].get("status") == "untested"),
            "error": sum(1 for r in rows
                         if r[key] and r[key].get("status") == "error"),
            "latency_ms": {
                "median": round(statistics.median(ms), 1) if ms else None,
                "mean": round(statistics.fmean(ms), 1) if ms else None,
                "min": round(min(ms), 1) if ms else None,
                "max": round(max(ms), 1) if ms else None,
                "n": len(ms),
            },
            "findings_total": sum(n_findings) if n_findings else None,
            "findings_per_image": (
                round(statistics.fmean(n_findings), 2) if n_findings else None),
            # ★ 拆开数：规则命中 vs 事实类 candidate。
            #
            #   合并成一个总数会让「自动升级有没有生效」看不见 ——
            #   而这一轮的全部改动就是为了让 candidate 出现。
            "by_status": {
                st: sum(1 for r in ok_rows
                        for f in (r[key].get("findings") or [])
                        if f.get("status") == st)
                for st in ("confirmed", "candidate", "untested")
            } if key == "system" else None,
            "by_produced_by": {
                pb: sum(1 for r in ok_rows
                        for f in (r[key].get("findings") or [])
                        if f.get("produced_by") == pb)
                for pb in ("rule", "verifiable-fact", "semantic")
            } if key == "system" else None,
            # ★ 只有 system 侧有：**画面**有没有被看过（OCR 是另一件事）。
            #   缺这一个字段，读数的读者会以为 0 条 finding = 判得准。
            #
            #   ★ 2026-10-28 更正：这个字段原来叫「什么都没看见」，
            #     而那时我误以为 OCR 也不可用。实测 OCR 是好的
            #     （285 字 / 15 段 / 420ms），所以它现在精确地只指
            #     **画面语义没看**（多模态未接入）。文字是看得到的。
            "no_vision": (
                sum(1 for r in ok_rows
                    if not (r[key].get("observations") or 0)
                    and "未接入" in (r[key].get("multimodal_note") or ""))
                if key == "system" else None),
            # ★ 规则命中不了却又**读到了字**的张数 —— 即「有字但判不了」。
            #   它才是「0 条 finding」最危险的那一格的读数：
            #   OCR 成功、规则全跑、一条不中（因为语言或词表不覆盖）。
            "read_but_no_match": (
                sum(1 for r in ok_rows
                    if (r[key].get("ocr_chars") or 0) > 0
                    and not (r[key].get("findings") or []))
                if key == "system" else None),
            # ★ 读到的字里，中文占比的均值。低 = 规则库不认识这些字。
            "cjk_ratio_mean": (
                round(statistics.fmean(
                    [r[key]["cjk_ratio"] for r in ok_rows
                     if isinstance(r[key].get("cjk_ratio"), (int, float))]), 3)
                if any(isinstance(r[key].get("cjk_ratio"), (int, float))
                       for r in ok_rows) else None
                if key == "system" else None),
        }

    return {"system": side("system"), "baseline": side("baseline")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="只跑前 N 条（0 = 全部）")
    ap.add_argument("--model", default=BASELINE_MODELS[0],
                    help="基线模型（默认 %s）" % BASELINE_MODELS[0])
    ap.add_argument("--out", default="")
    ap.add_argument("--check", action="store_true",
                    help="只读配置与 gold，不联网")
    args = ap.parse_args()

    print("=" * 74)
    print("图片审核 · 本系统 vs 裸大模型")
    print("=" * 74)

    env_rows = check_env()
    tokenhub = env_rows["tokenhub"]
    print("凭据（只报配没配，不打印值）：")
    for gw, row in env_rows.items():
        print("  %-9s %s%s" % (gw, "已配" if row["ready"] else "未配",
                               "" if row["ready"] else "（缺 %s）" % "、".join(row["missing"])))

    gold = _load_gold()
    print("gold：%s%s" % (gold["status"],
                          (" · %d 条记录" % len(gold["records"]))
                          if gold["status"] == "ok" else " · " + gold["reason"]))

    if args.check:
        if gold["status"] != "ok":
            print("\n⚠ 未测：gold 读不出，没有可评的对象。")
            return 2
        if not tokenhub["ready"]:
            print("\n⚠ 未测：tokenhub 凭据未配 —— 基线跑不了。")
            print("   配好 MULTIMODAL_TOKENHUB_BASE_URL / MULTIMODAL_TOKENHUB_API_KEY 后重跑。")
            return 2
        # ★ 只检查「能不能跑」，不假装跑过。
        #   ★ 这里必须报**筛完之后**的张数，不是 gold 的总数 ——
        #     报 25 而实际跑 15，读的人会以为漏了 10 张。
        picked = images_for_market(gold["records"], MARKET)
        from collections import Counter as _C
        dist = dict(_C(p["lang"] for p in picked))
        print("\n市场口径 %s：%d 条记录 / **%d 张**可评（语言 %s）"
              % (MARKET, len({p["record_id"] for p in picked}), len(picked), dist))
        print("   （gold 总计 %d 条 / %d 张，其中非英文素材不在此市场口径内）"
              % (len(gold["records"]),
                 sum(len(_images_of(r)) for r in gold["records"])))
        print("★ 这是 --check 读数，**没有一条指标** —— 指标要真跑才有。")
        # ★ 退出码语义：--check 只回答「能不能跑」。
        #   能跑 = 0；跑不了（缺凭据/缺 gold）= 2。
        #
        #   ★ 第一版这里也退 2，与「跑不了」撞了同一个码 —— 于是调用方
        #     分不清「配好了可以跑」和「凭据没配」。那正是本项目反复记的
        #     那个病：**两种完全不同的状态长得一样**。
        #     （`--check` 本身不产出指标，所以退 0 不会被读成「测过了」。）
        return 0

    if gold["status"] != "ok":
        print("\n⚠ 未测：gold 读不出。")
        return 2
    if not tokenhub["ready"]:
        print("\n⚠ 未测：tokenhub 凭据未配。")
        print("   ★ 不给任何指标 —— 没有基线就没有对比，"
              "而「0ms / 0 条发现」会被读成「跑得很好」。")
        return 2

    # ★★ 先按市场筛图，再跑。
    #
    #   第一轮我没有这一步，直接用 `records[:3]` —— 那 3 条恰好是德语和中文，
    #   于是得出「规则库不认中文所以整条链路不通」的结论，而真实原因
    #   是**我筛错了样本**。25 张里 16 张是英文，正好是北美要评的那批。
    picked = images_for_market(gold["records"], MARKET)
    if args.limit:
        picked = picked[: args.limit]
    if not picked:
        print("\n⚠ 未测：按市场 %r 筛完一张图都不剩。" % MARKET)
        print("   ★ 这不是「没有违规」——是筛完没有可评对象。")
        return 2

    from collections import Counter
    lang_dist = Counter(p["lang"] for p in picked)
    print("市场口径：%s · 筛出 %d 张 · 语言分布 %s"
          % (MARKET, len(picked), dict(lang_dist)))

    rows: List[Dict[str, Any]] = []
    for item in picked:
        rid, img = item["record_id"], item["image"]
        if True:
            say("\n── %s / %s ──" % (rid, img.name))
            sys_out = run_system(img)
            base_out = run_baseline(img, model=args.model)
            rows.append({"record_id": rid, "image": img.name,
                         "gold_category": item["gold_category"],
                         "lang": item["lang"],
                         "system": sys_out, "baseline": base_out})
            say("   system  : %-8s %s ms · findings=%d"
                  % (sys_out["status"],
                     sys_out["ms"] if sys_out["ms"] is not None else "—",
                     len(sys_out.get("findings") or [])))
            say("   baseline: %-8s %s ms · findings=%d"
                  % (base_out["status"],
                     base_out["ms"] if base_out["ms"] is not None else "—",
                     len(base_out.get("findings") or [])))
            if base_out.get("status") != "ok" and base_out.get("reason"):
                say("     · %s" % base_out["reason"][:110])

    summary = _summarize(rows)
    print("\n" + "─" * 74)
    print("速度（墙钟，同一网关、同一批图）：")
    for side, label in (("system", "本系统"), ("baseline", "裸大模型")):
        s = summary[side]
        lat = s["latency_ms"]
        print("  %-8s 测成 %d / 未测 %d / 出错 %d · 中位 %s ms · 均 %s ms（n=%d）"
              % (label, s["tested"], s["untested"], s["error"],
                 lat["median"], lat["mean"], lat["n"]))
    print("产出：本系统 %s 条 finding · 裸模型 %s 条"
          % (summary["system"]["findings_total"], summary["baseline"]["findings_total"]))
    # ★ 拆开报。合并成一个数读不出「自动升级有没有生效」。
    bs = summary["system"].get("by_status") or {}
    bp = summary["system"].get("by_produced_by") or {}
    say("   本系统拆分：按状态 %s · 按来源 %s" % (bs, bp))

    # ★★ 必须单独说：本系统的 0 条 finding **不是「判得准」**。
    #   两件不同的事都要报：画面没看 / 读到了字但规则不认。
    no_vision = summary["system"].get("no_vision")
    read_no_match = summary["system"].get("read_but_no_match")
    cjk = summary["system"].get("cjk_ratio_mean")
    if no_vision:
        print("\n★ 本系统在 %d 张图上**没看画面**"
              "（multimodal_note = 「未接入多模态分析」）。" % no_vision)
        print("  画面类问题（构图、暗示疗效、品牌调性）它答不了 —— 说话的是 OCR 正文那一路。")
    if read_no_match:
        print("\n★★★ 本系统在 %d 张图上**读到了字、规则也全跑了，却一条都没命中**。"
              % read_no_match)
        if isinstance(cjk, (int, float)):
            print("    这些图读到文字的中文占比均值 = %.3f"
                  "（规则库是**中文关键词表**）。" % cjk)
            if cjk < 0.5:
                print("    → 主因是**语言**：读出来的字大部分不是中文，规则表不覆盖。")
                print("      这不是「判得准」，是「规则不认识这些字」。")
        print("    ★ 这一格的对比**不成立** —— 除非把规则表扩到对应语言，")
        print("      或者只在中文字样上比。")

    if summary["system"]["tested"] == 0 and summary["baseline"]["tested"] == 0:
        print("\n⚠ 未测：两侧一条都没测成。")
        return 2

    print("\n★ 质量指标（对 gold 的 hit/miss/false_positive）本轮**未计算** ——")
    print("  那需要把两侧产出映射到 gold 的问题类型，而映射表要人工确认。")
    print("  本文件先给**速度**与**产出量**，质量留给 eval_review_gold.py 的既有口径，")
    print("  不在这里另造一套匹配规则（两套必然漂移）。")

    doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_model": args.model,
        "credentials": env_rows,
        "market": MARKET,
        "images_evaluated": len(picked),
        "language_distribution": dict(lang_dist),
        "summary": summary,
        "rows": rows,
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n读数已写：%s" % args.out)

    if any(r["system"] and r["system"].get("status") == "error" for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
