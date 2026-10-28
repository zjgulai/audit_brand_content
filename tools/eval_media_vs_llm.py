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

2026-10-28 实测，**两条能力都不可用**：

| 能力 | 状态 | 实测读数 |
|---|---|---|
| 图内文字（OCR） | ❌ | `DEFAULT_OCR_ENGINE = "host_vision"`，而它依赖的 `base/media_vision.py` **不存在**（ImportError）。`image_file_row()` 产出的 `ocr_text` 恒为空串 —— 不是「识别出 0 个字」，是**没有识别这回事**。 |
| 画面语义（多模态） | ❌ 未配凭据 | `MULTIMODAL_*` 四个环境变量全空 → `readiness()` 落 `untested` → `judge_entry` 收到 `multimodal_analyze=None` → `multimodal_note = "未接入多模态分析"`。 |

合起来：**本系统今天审一张图，什么也看不见。** 所以：

- 它在这批 gold 图上的 findings 恒为 0 —— 这不是「判得准」，是**没看**；
- 判定仍是 `REVIEW`（覆盖 partial，三族没有控制点），**看起来像在正常工作**。

★ 这正是本项目反复记的那个病（AGENTS.md §2.4.1）：**产出看起来正常，没有任何东西会红。**
所以本工具的输出必须把「0 条 finding」与 `multimodal_note` 一起打出来，
不许只报一个数字。

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
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD_DIR = Path(os.path.expanduser("~/audit-data/gold/pilot"))

#: 基线模型。★ 取 `tools/multimodal_client.py` 的 `LIVE_PROBE` 里**实测 ok** 的那几个，
#: 不写一个「听起来最强」但没探过的 id —— 那样的基线挂了会被读成「大模型不行」。
BASELINE_MODELS = ("glm-5.3-flash",)

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

def run_system(image: Path, *, clock=time.perf_counter) -> Dict[str, Any]:
    """本系统：规则引擎 + 多模态观察全链路。返回产出与墙钟毫秒。"""
    from base import judge_entry

    raw = image.read_bytes()
    import hashlib
    sha = hashlib.sha256(raw).hexdigest()
    unit = {
        "unit_id": "u-" + sha[:12],
        "kind": "image",
        "text": "",
        "has_text": False,
        "source": {"kind": "image", "uri": str(image)},
        "fingerprint": {"raw_sha256": sha, "text_sha256": sha},
        "_media_local_path": str(image),
    }
    t0 = clock()
    try:
        out = judge_entry.judge_unit(unit, clock=time.time)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "%s: %s" % (type(exc).__name__, exc),
                "ms": None, "findings": [], "decision": None}
    ms = (clock() - t0) * 1000.0
    return {
        "status": "ok",
        "reason": "",
        "ms": round(ms, 3),
        "findings": [
            {"control_code": f.get("control_code"), "severity": f.get("severity"),
             "quote": f.get("quote")}
            for f in (out.get("findings") or [])
        ],
        "decision": out.get("label"),
        "observations": len(out.get("multimodal_observations") or []),
        "multimodal_note": out.get("multimodal_note"),
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
        client = GatewayClient.from_env("tokenhub", model=model, env=env)
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
            # ★ 只有 system 侧有：它「有没有真的看见东西」。
            #   缺这一个字段，读数的读者会以为 0 条 finding = 判得准。
            "saw_nothing": (
                sum(1 for r in ok_rows
                    if not (r[key].get("observations") or 0)
                    and "未接入" in (r[key].get("multimodal_note") or ""))
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
        n_img = sum(len(_images_of(r)) for r in gold["records"])
        print("\n可以跑：%d 条记录 / %d 张图。" % (len(gold["records"]), n_img))
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

    records = gold["records"] if not args.limit else gold["records"][: args.limit]
    rows: List[Dict[str, Any]] = []
    for rec in records:
        rid = rec.get("record_id")
        for img in _images_of(rec):
            print("\n── %s / %s ──" % (rid, img.name))
            sys_out = run_system(img)
            base_out = run_baseline(img, model=args.model)
            rows.append({"record_id": rid, "image": img.name,
                         "gold_category": rec.get("原因分类"),
                         "system": sys_out, "baseline": base_out})
            print("   system  : %-8s %s ms · findings=%d"
                  % (sys_out["status"],
                     sys_out["ms"] if sys_out["ms"] is not None else "—",
                     len(sys_out.get("findings") or [])))
            print("   baseline: %-8s %s ms · findings=%d"
                  % (base_out["status"],
                     base_out["ms"] if base_out["ms"] is not None else "—",
                     len(base_out.get("findings") or [])))
            if base_out.get("status") != "ok" and base_out.get("reason"):
                print("     · %s" % base_out["reason"][:110])

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

    # ★★ 必须单独说：本系统的 0 条 finding **不是「判得准」**。
    #   实测原因是两条能力都不可用（OCR 引擎依赖的模块不存在 + 多模态未配凭据）。
    #   不说这一句，「本系统 0 条 / 裸模型 N 条」会被读成「本系统更少误报」。
    saw_nothing = summary["system"].get("saw_nothing")
    if saw_nothing:
        print("\n★★★ 本系统在 %d 张图上**什么都没看见**"
              "（multimodal_note = 「未接入多模态分析」，且 OCR 引擎不可用）。" % saw_nothing)
        print("    所以它的 0 条 finding 不是「判得准」，是「没看」。")
        print("    这一格的对比**不成立** —— 要先配好多模态凭据才谈得上比。")

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
        "gold_records": len(records),
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
