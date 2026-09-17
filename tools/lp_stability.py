#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lp_stability.py —— 落地页「正文指纹」的**复现性**实测（B2 · 回答 V4 抛出的那一问）

## 这个脚本为什么存在

`tools/verify_landing.py` 的 **V4** 默认重抓 3 个 URL 做抽检，本轮的运行结果：

    ❌ 提取后正文指纹也在变：一致 2 / 变化 1
       正文级指纹不稳会动摇 ADR-0002，需先查清原因

V4 的问法是对的，但它**只负责把灯点亮，不负责说出原因**（3 个样本也说不出来）。
本脚本把那一问接过来，做三件事：

1. **放大样本**：重抓 N 个 URL，分别比 ① 原始 HTML 的 sha256 ② 提取后正文的 sha256。
2. **定位分歧点**：对每一处不一致，逐字符找出**第一个分歧位置**，并把两侧上下文打出来。
   —— 不满足于「变了」，要说出**变的是哪几个字**。
3. **归因到可枚举的形态**：把分歧片段匹配到一组**波动形态**（评论数 / 价格 / 促销码 / 库存 …）。

## 这一问为什么重要（不是洁癖）

ADR-0002 定的口径是：原始 HTML 的 sha256 会因每次请求唯一的 reqid 与埋点脚本而变，
所以「内容指纹」要建立在**提取后的正文**上。这条推理没错，但它推出的是一个**假设**：

    假设：提取后的正文 → 重抓不变。

本轮实测**推翻了这个假设**：变化的不是 reqid，是**评论数**（`1,835` → `1,836`）。
于是 `ContentUnit.content_key`（契约里写着「只吃正文指纹 —— 页面重渲染后它不变」）
对这类页面**每次观测都会给出一个新的 key**，而它本该回答的是
「这两次看到的是不是同一个东西」。

★ 这不是「指纹算错了」，是**一个从未被实测过的断言**。本项目已出过三次同一形态的事：
  断言写在文档里、代码也按它写了，但**没有一条检查问过它是否成立**。

## 用法

    python3 tools/lp_stability.py                # 重抓 20 个（默认），落盘证据
    python3 tools/lp_stability.py -n 6           # 小样本
    python3 tools/lp_stability.py --analyze-only # 不联网，只对盘上已有证据归因

★ 节流沿批次 C 的结论：**全局 6s 间隔**。第一遍抓取用 1.2s 同域名间隔 → 30.4% 成功；
  续抓改成全局 6s → 100%。这里的样本是故意的联网动作，**不许**为了快而调小。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from lp_extract import CLAIM_RE  # noqa: E402  唯一词形定义，不重复维护
import lp_extract as X          # noqa: E402
import lp_fetch as F            # noqa: E402

LAND = ROOT / "research" / "landing"
OUT = LAND / "_evidence" / "stability.json"

# ------------------------------------------------------------------ 波动形态

# ★ 这一组不是「猜」出来的，是把实测分歧片段归类后**收敛**出来的形态。
#   每一条都要能指名道姓地说出「它会随什么而变」。
VOLATILE_FORMS = [
    ("评论数", r"Rated\s+[\d.]+\s+out of 5 stars\s*\n?\s*([\d,]+)",
     "买家评价条数 —— 每多一条评价就 +1，与合规判定无关"),
    ("价格", r"(?:US)?\$\s?([\d,]+\.\d{2})",
     "售价 —— 促销/汇率/区域定价变动"),
    ("折扣码", r"[Cc]ode:\s*([A-Z0-9]{3,})",
     "促销码与折扣幅度 —— 营销活动排期"),
    ("库存/余量", r"(\d+)\s+left in stock", "库存余量"),
    ("销量/热度", r"([\d,]+)\+?\s+(?:sold|Sold|bought)", "销量计数"),
    ("倒计时", r"\b(\d{1,2}:\d{2}:\d{2})\b", "页面内倒计时"),
]


def first_diff(a: str, b: str) -> dict:
    """★ 把两侧的差异**收窄到最小变更段**，而不是「从某一点起全都不一样」。

    第一版只找「第一个不同的字符」，然后把两侧各 90/110 字符的窗口打出来 ——
    实测下来 20 个样本里有 **9 个归不了因**，因为真正变的那几个字在窗口之外，
    窗口里显示的是**没变**的上下文。这不是归因能力不够，是**取证方法不对**：

        共同前缀 + 共同后缀 一剪，剩下的就是**逐字变掉的那一段**。

    本函数回三段：`只在新版出现` / `只在旧版出现`（两者之一常为空，即纯增删），
    以及它们在两侧的位置。**不猜形态，先把事实钉死。**
    """
    n, m = len(a), len(b)
    p = 0
    while p < n and p < m and a[p] == b[p]:
        p += 1
    s = 0
    while s < n - p and s < m - p and a[n - 1 - s] == b[m - 1 - s]:
        s += 1
    old_seg = a[p:n - s] if s else a[p:]
    new_seg = b[p:m - s] if s else b[p:]
    return {
        "at": p,
        "只在新版出现": new_seg[:400],
        "只在旧版出现": old_seg[:400],
        "新段长": len(new_seg), "旧段长": len(old_seg),
        "len_old": n, "len_new": m, "delta": m - n,
        "前缀相同": p, "后缀相同": s,
        # 保留原窗口：收窄后的段若仍然很长（结构性改动），窗口能给出上下文
        "old_ctx": a[max(0, p - 60):p + 160],
        "new_ctx": b[max(0, p - 60):p + 160],
    }


def _tokens(s: str) -> list[str]:
    return re.findall(r"[\w\u00c0-\u024f\u4e00-\u9fff$#%.,:/-]+", s or "")


def attribute(d: dict) -> list[dict]:
    """把收窄后的变更段归因到波动形态。

    ★ 两级归因，**第二级不能省**：
      ① 已知形态（评论数 / 价格 / 折扣码 …）—— 给人看的标签；
      ② **逐词差集**（旧段有哪些词、新段有哪些词）—— 给不知道形态的那些用。
      第一版只有 ①，于是「未归因」成了垃圾桶。② 让每一条都至少说得出
      「少了一个 X、多了一个 Y」，哪怕 X 的形态是本次第一次见。
    """
    old_seg, new_seg = d.get("只在旧版出现", ""), d.get("只在新版出现", "")
    out = []
    for name, rx, why in VOLATILE_FORMS:
        mo, mn = re.search(rx, old_seg), re.search(rx, new_seg)
        if mo and mn and mo.group(0) != mn.group(0):
            out.append({"形态": name, "旧": mo.group(0).strip()[:70],
                        "新": mn.group(0).strip()[:70], "$为什么会变": why})
    if out:
        return out

    # ── ② 逐词差集：不依赖形态表 ──────────────────────────────────
    to, tn = _tokens(old_seg), _tokens(new_seg)
    gone = [t for t in to if t not in tn]
    came = [t for t in tn if t not in to]
    if not (gone or came):
        return []
    # 数字型差异单列 —— 它是「会随时间变」的最强信号
    num = [x for x in (gone + came) if re.fullmatch(r"[\d.,$#%]+", x)]
    return [{
        "形态": "数字/计数" if num and len(num) >= max(1, (len(gone) + len(came)) // 2)
                else "文本片段",
        "旧段": old_seg[:120], "新段": new_seg[:120],
        "少了的词": gone[:8], "多了的词": came[:8],
        "$为什么会变": ("**本次未命中已知波动形态**，但两段逐词差集是可核的。"
                        "若同一形态反复出现，应把它补进 `VOLATILE_FORMS` —— "
                        "形态表是长出来的，不是一次想全的。"),
    }]


# ------------------------------------------------------------------ 掩码与合规相关性

# ★★ 这一节回答的是「所以呢」。
#
#   「正文变了 68%」本身不构成一个可执行的结论 —— 法务真正要问的是：
#     **变的是不是合规相关的东西？**
#   两个可能的答案，处置完全相反：
#     · 变的全是评论数/价格/促销码 → **指纹该修**（加一层掩码），业务无感知
#     · 变里含合规相关表述        → **指纹是对的**，这是真的内容改动，必须报
#   不做这一问就报「68% 不可复现」，等于把一个**工具缺陷**说成**业务风险**。

def masked(text: str) -> str:
    """把**已知会随时间变、且与合规判定无关**的片段替换成占位符。

    ★ 口径要写死：只掩**形态明确**的那几类（评论数 / 库存 / 倒计时）。
      **价格与折扣码不掩** —— 它们看起来像噪声，但促销幅度本身就是一条
      可能被判定为「绝对化 / 比较性」的表述（`SAVE 20%`）。把价格掩掉，
      就等于让「本周降价了」这件事对合规审查隐身。这个取舍必须写出来。
    """
    t = text or ""
    t = re.sub(r"(Rated\s+[\d.]+\s+out of 5 stars\s*\n?\s*)[\d,]+", r"\g<1><REVIEWS>", t)
    t = re.sub(r"\d+\s+left in stock", "<STOCK> left in stock", t)
    t = re.sub(r"\b\d{1,2}:\d{2}:\d{2}\b", "<TIMER>", t)
    return t


def _claims(text: str) -> dict[str, set]:
    out = {}
    for k, rx in CLAIM_RE.items():
        m = {x.group(0).lower() for x in rx.finditer(text or "")}
        if m:
            out[k] = m
    return out


def claim_relevance(old_bt: str, new_bt: str) -> dict:
    """★★ 合规相关表述**有没有真的变** —— 这一问才是「所以呢」。

    ★ 第一版问的是「**变更段里含不含**合规词形」，实测下来它几乎恒为真：
      最小变更段可能很长，段里的 `45db` / `FSA` 在**新旧两版里都出现**，
      于是「段里有」被误读成「这条声明变了」。**这是一个会天天报假警的判据。**

    正确的问法是在**完整的两版正文**上各抽一次声明集合，再取差集：

        消失了什么（旧有新无）  —— 才是「页面把某条声明撤了」
        新增了什么（新有旧无）  —— 才是「页面新加了一条声明」

    词表仍来自 `lp_extract`，不在这里重写第二份。
    """
    co, cn = _claims(old_bt), _claims(new_bt)
    gone = {k: sorted(co[k] - cn.get(k, set())) for k in co if co[k] - cn.get(k, set())}
    came = {k: sorted(cn[k] - co.get(k, set())) for k in cn if cn[k] - co.get(k, set())}
    return {"消失的声明": gone, "新增的声明": came,
            "是否触及合规表述": bool(gone or came),
            "$口径": "在**完整正文**上抽声明后取差集；不是「变更段里含不含词形」。"}


def volatile_exposure(rows: list[dict]) -> dict:
    """**盘上快照**里有多少页面含波动片段 —— 静态暴露面，不是实测不稳定率。

    ★ 两个数不能互相冒充：
      · 本函数 = 「**有多少页面暴露在这种风险下**」（分母 92，一次算完）
      · 重抓实测 = 「**实际变了几个**」（分母 N，依赖抽到的页面与抓取间隔）
      把前者当后者报，会得出「一半以上的页面不可复现」这种没有测过的结论。
    """
    n_hit, per_form = 0, {}
    for r in rows:
        bt = ((r.get("html") or {}).get("body_text") or "")
        hit = [name for name, rx, _ in VOLATILE_FORMS if re.search(rx, bt)]
        for h in hit:
            per_form[h] = per_form.get(h, 0) + 1
        if hit:
            n_hit += 1
    return {"分母": len(rows), "含波动片段的页面": n_hit,
            "占比_pct": round(100.0 * n_hit / len(rows), 1) if rows else None,
            "逐形态": per_form,
            "$口径": ("**这是暴露面，不是实测不稳定率。** 「页面里有会变的片段」"
                      "与「重抓时它真的变了」是两件事：价格一个月不动，"
                      "两次抓取之间就不会产生分歧。")}


# ------------------------------------------------------------------ 重抓

def refetch(n: int, global_gap: float) -> dict:
    fetch = json.loads((LAND / "抓取结果.json").read_text(encoding="utf-8"))
    ext = {e["url_key"]: e for e in
           json.loads((LAND / "要素提取.json").read_text(encoding="utf-8"))["results"]}
    pacer = F.Pacer(global_gap=global_gap, domain_gap=1.5)
    cache: dict = {}

    cand = [r for r in fetch["results"] if r["tier_raw"].startswith("ok")]
    # ★ 抽样口径：**等距取**，不是取前 N 个。前 N 个全落在同一个域名/同一种页面上，
    #   会让「变了几个」变成「au.momcozy.com 变了几个」。
    step = max(1, len(cand) // max(1, n))
    picked = cand[::step][:n]

    rows, t0 = [], time.time()
    print("重抓 %d 个 URL（全局间隔 %.1fs，预计 %.0fs）—— 沿批次 C 的节流结论\n"
          % (len(picked), global_gap, len(picked) * global_gap))
    for i, r in enumerate(picked, 1):
        at = next((x for x in r["attempts"] if x["label"] == "html" and x.get("sha256")), None)
        e = ext.get(r["url_key"])
        if not at or not e or not (e.get("html") or {}).get("body_text"):
            continue
        dom = urllib.parse.urlparse(r["url"]).netloc
        pacer.wait(dom)
        st, fin, body, hdr, el, err = F.http_get(r["url"])
        pacer.hit(dom)
        row = {"url_key": r["url_key"], "url": r["url"], "status": st, "error": err,
               "bytes": len(body), "fetch_ms": el, "pacer_gap": round(pacer.global_gap, 1)}
        if err or st != 200 or not body:
            row["verdict"] = "refetch_failed"
            rows.append(row)
            print("  [%2d/%2d] ✗ %-58s %s" % (i, len(picked), r["url_key"][:58], err or st))
            continue
        raw_same = hashlib.sha256(body).hexdigest() == at["sha256"]
        old_bt = e["html"]["body_text"]
        new_bt = X.analyze_html(body)["body_text"]
        txt_same = hashlib.sha256(new_bt.encode()).hexdigest() == \
            hashlib.sha256(old_bt.encode()).hexdigest()
        row.update(raw_same=raw_same, text_same=txt_same,
                   old_len=len(old_bt), new_len=len(new_bt))
        if not txt_same:
            d = first_diff(old_bt, new_bt)
            row["diff"] = d
            row["归因"] = attribute(d)
            # ★ 两问：① 变更段里有合规相关词吗 ② 掩掉波动片段后还一样吗
            row["合规相关性"] = claim_relevance(old_bt, new_bt)
            row["掩码后一致"] = (hashlib.sha256(masked(new_bt).encode()).hexdigest()
                                 == hashlib.sha256(masked(old_bt).encode()).hexdigest())
        row["verdict"] = "same" if txt_same else "text_changed"
        rows.append(row)
        mark = "=" if txt_same else "≠"
        print("  [%2d/%2d] %s 正文%s  原始HTML%s  %+d 字" % (
            i, len(picked), mark, "一致" if txt_same else "**变了**",
            "同" if raw_same else "异", len(new_bt) - len(old_bt)), flush=True)
        if not txt_same:
            for a in row["归因"]:
                if "旧" in a:
                    print("         ← %s：%r → %r" % (a["形态"], a["旧"], a["新"]))
                else:
                    print("         ← %s：−%s  +%s" % (a["形态"],
                                                      a.get("少了的词"), a.get("多了的词")))
            if not row["归因"]:
                print("         ← **未归因**（逐词差集也空 —— 差异只在标点/空白）")

    # ★ 联网只负责把网页取回来；**汇总在 summarize() 里，可以单独对盘上的行跑**
    #   （`--analyze-only`）。判据改了不必重抓，这是抽出来的全部理由。
    return summarize(rows, {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "snapshot": (fetch.get("manifest") or {}).get("snapshot"),
        "global_gap_s": global_gap,
        "elapsed_s": round(time.time() - t0, 1),
        "picked_n": len(picked),
        "exposure": volatile_exposure(list(ext.values())),
        "mask_note": ("掩 `Rated … out of 5 stars <N>` / `N left in stock` / `HH:MM:SS`。"
                      "**价格与折扣码不掩** —— 促销幅度本身可能是被判定的表述。"),
    })


def summarize(rows: list[dict], meta: dict) -> dict:
    """★ 汇总**必须能对盘上已有的行单独跑**。

    第一版把汇总写死在 `refetch()` 里，后果实测过两次：
      · `size_class()` 的 `len()` bug 在**一轮 20 个抓完之后**才抛 —— 166 秒白做；
      · 判据改了（「变更段含词形」→「声明集合取差集」）之后，**旧证据没法用新口径重算**，
        只能再花 166 秒重抓一遍。

    抽出来之后，判据怎么改都能对**已落盘的行**重算，联网只做一件事：把网页取回来。
    """
    ok_rows = [r for r in rows if r.get("verdict") in ("same", "text_changed")]

    same = [r for r in ok_rows if r["text_same"]]
    raw_same = [r for r in ok_rows if r.get("raw_same")]
    forms = {}
    for r in ok_rows:
        for a in r.get("归因") or []:
            forms[a["形态"]] = forms.get(a["形态"], 0) + 1
    changed = [r for r in ok_rows if r["verdict"] == "text_changed"]
    masked_same = [r for r in ok_rows
                   if r["verdict"] == "same" or r.get("掩码后一致")]
    compliance = [r for r in changed if (r.get("合规相关性") or {}).get("是否触及合规表述")]

    def span_class(r):
        """按**变更跨度**分档 —— 首个分歧点与最后一个分歧点之间的距离。

        ★★ 第一版这里叫「变更规模」，是个**误导的名字**，改名的理由值得写下来：
          实测 14 处正文变化里 **12 处跨度 >500 字符**，其中一处在 Δ 只有 −301 字
          的情况下跨度是 **17,585 字符**。那不是「改动很大」，是**页面被重排了** ——
          首尾分歧之间夹着大量根本没变的内容。

          ⇒ 正确读法不是「改得多」，而是「**改动无法被表达成一个小 diff**」。
            这直接决定处置方式：想在界面上给法务指「这里变了」，做不到
            （要标 17,585 个字符）。**能给人看的是声明集合的差集 —— 4 个词。**

        ★ `新段长`/`旧段长` 是字符数（int），第一版对它写了 `len()` ——
          在第一轮 20 个样本跑完之后才抛 `TypeError`，**一整轮的联网抓取白做**。
          教训不是「小心 len」，是**聚合阶段不该在抓取之后才第一次被执行**。
          这也是 `summarize()` 被从 `refetch()` 里抽出来的直接原因。
        """
        d = r.get("diff") or {}
        n = max(d.get("新段长") or 0, d.get("旧段长") or 0)
        return ("① 跨度 ≤30 字（局部替换）" if n <= 30 else
                "② 跨度 31–500 字" if n <= 500 else
                "③ 跨度 >500 字（**页面重排，diff 无法表达**）")
    spans = {}
    for r in changed:
        spans[span_class(r)] = spans.get(span_class(r), 0) + 1
    return {
        "measured_at": meta.get("measured_at"),
        "snapshot": meta.get("snapshot"),
        "global_gap_s": meta.get("global_gap_s"),
        "elapsed_s": meta.get("elapsed_s"),
        "样本": {"取": meta.get("picked_n"), "可判": len(ok_rows),
                 "重抓失败": len(rows) - len(ok_rows)},
        "原始 HTML sha256 一致": len(raw_same),
        "提取后正文 sha256 一致": len(same),
        "正文变化": len(ok_rows) - len(same),
        "正文可复现率_pct": round(100.0 * len(same) / len(ok_rows), 1) if ok_rows else None,
        "变化归因": forms,
        "★ 掩码后一致": len(masked_same),
        "★ 掩码后可复现率_pct": round(100.0 * len(masked_same) / len(ok_rows), 1) if ok_rows else None,
        "★ 变更跨度分档": spans,
        "★ 变更触及合规表述": len(compliance),
        "★ 变更触及合规表述的页面": [
            {"url_key": r["url_key"],
             "命中": {"消失的声明": r["合规相关性"]["消失的声明"],
                      "新增的声明": r["合规相关性"]["新增的声明"]}}
            for r in compliance],
        "逐条": rows,
        "静态暴露面": meta.get("exposure"),
        "掩码定义": meta.get("mask_note"),
        "$这一组数的读法": (
            "★ **分母是「本次抽到并可判的 URL 数」，不是 92。** 重抓是联网的时间点动作，"
            "它的结论只对「这个间隔、这批页面」成立。要外推到 92 个页面，"
            "得先假设它们与抽样同分布 —— 本脚本不替调用方做这个假设。\n"
            "★ 两个不同的数必须分开：`正文可复现率` 是**实测**；`静态暴露面` 是"
            "**有多少页面处于风险下**。把后者当前者，会得出没测过的结论。"),
    }


def _aggregate(runs: list[dict]) -> dict:
    """多轮合并读数 —— **单轮的 30% 与三轮合并的 30% 不是同一个结论**，
    后者才谈得上「这个口径大约多久失效一次」。"""
    if not runs:
        return {}
    j = sum(r["样本"]["可判"] for r in runs)
    s = sum(r["提取后正文 sha256 一致"] for r in runs)
    raw = sum(r["原始 HTML sha256 一致"] for r in runs)
    mk = sum(r.get("★ 掩码后一致") or 0 for r in runs)
    cp = sum(r.get("★ 变更触及合规表述") or 0 for r in runs)
    forms = {}
    for r in runs:
        for k, v in (r.get("变化归因") or {}).items():
            forms[k] = forms.get(k, 0) + v
    return {"轮数": len(runs), "可判合计": j,
            "原始 HTML 一致": "%d/%d" % (raw, j),
            "正文一致": "%d/%d" % (s, j),
            "正文可复现率_pct": round(100.0 * s / j, 1) if j else None,
            "★ 掩码后可复现率_pct": round(100.0 * mk / j, 1) if j else None,
            "★ 变更触及合规表述": cp,
            "变化归因合计": forms,
            "$读法": ("★ **合并的是「同一快照、不同时间点」的多次观测。** 每次重抓都是"
                      "一次独立的对照：拿快照日的正文与「今天」的正文比。"
                      "所以轮数越多，「两个时间点之间正文会变的页面占多少」估得越准 —— "
                      "而它衡量的仍然是**这一点时间跨度内**的变化，不是「永远」。")}


def main() -> int:
    ap = argparse.ArgumentParser(description="落地页正文指纹复现性实测（B2）")
    ap.add_argument("-n", type=int, default=20, help="重抓多少个 URL（默认 20）")
    ap.add_argument("--global-gap", type=float, default=6.0, help="全局节流间隔秒（别调小）")
    ap.add_argument("--analyze-only", action="store_true", help="不联网，只读盘上证据")
    a = ap.parse_args()

    if a.analyze_only:
        if not OUT.exists():
            print("盘上还没有 stability.json，先跑一次联网版。")
            return 1
        raw = json.loads(OUT.read_text(encoding="utf-8"))
        # ★ 用**当前判据**对盘上已有的行重算 —— 判据改过之后旧证据仍可用。
        #   这正是把 summarize() 从 refetch() 里抽出来的全部理由：
        #   联网只负责把网页取回来，怎么算与取不取是两件事。
        meta = {k: raw.get(k) for k in ("measured_at", "snapshot", "global_gap_s",
                                        "elapsed_s")}
        meta["picked_n"] = (raw.get("样本") or {}).get("取")
        meta["exposure"] = raw.get("静态暴露面")
        meta["mask_note"] = raw.get("掩码定义")
        d = summarize(raw["逐条"], meta)
        # ★ `runs` 是**每轮观测**的历史，重算不动它，只改**顶层汇总**。
        #   若在这里再 append 一次，同一批观测会被算两遍（40 个变 60 个）——
        #   一个只在「多跑一次 analyze」时才出现的错。
        d["runs"] = raw.get("runs") or []
        d["累计"] = raw.get("累计") or _aggregate(d["runs"])
        d["reanalyzed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        d["reanalyzed_note"] = ("★ 顶层汇总由 `--analyze-only` 用**当前判据**重算；"
                                "`逐条`（原始观测）没有被改动。")
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        d = refetch(a.n, a.global_gap)
        # ★ 多轮累积：单轮 20 个的分母太小，说不出「可复现率大约是多少」。
        #   每一轮都是独立的时间点观测，合起来才够。**不覆盖、只追加。**
        if OUT.exists():
            try:
                prev = json.loads(OUT.read_text(encoding="utf-8"))
                d["runs"] = (prev.get("runs") or []) + [{
                    k: d[k] for k in ("measured_at", "样本", "原始 HTML sha256 一致",
                                      "提取后正文 sha256 一致", "正文可复现率_pct",
                                      "★ 掩码后一致", "★ 掩码后可复现率_pct",
                                      "★ 变更触及合规表述",
                                      "变化归因", "elapsed_s")}]
                d["runs"] = d["runs"][-10:]
            except Exception:                                  # noqa: BLE001
                d["runs"] = []
        else:
            d["runs"] = []
        agg = _aggregate(d["runs"] + [{k: d[k] for k in (
            "measured_at", "样本", "原始 HTML sha256 一致", "提取后正文 sha256 一致",
            "正文可复现率_pct", "★ 掩码后一致", "★ 掩码后可复现率_pct",
            "★ 变更触及合规表述", "变化归因", "elapsed_s")}])
        d["累计"] = agg
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 78)
    print("落地页正文指纹复现性（快照 %s）" % d["snapshot"])
    print("=" * 78)
    s = d["样本"]
    print("\n重抓 %d 个，可判 %d 个，失败 %d 个  用时 %.0fs（全局间隔 %.1fs）" % (
        s["取"], s["可判"], s["重抓失败"], d["elapsed_s"], d["global_gap_s"]))
    print("\n  原始 HTML sha256  一致 %d/%d" % (d["原始 HTML sha256 一致"], s["可判"]))
    print("  提取后正文 sha256 一致 %d/%d  → **可复现率 %s%%**" % (
        d["提取后正文 sha256 一致"], s["可判"], d["正文可复现率_pct"]))
    agg = d.get("累计") or {}
    if agg.get("轮数", 0) > 1:
        print("\n  ★ 累计（%d 轮独立观测合并 —— 单轮分母太小，说不出「大约多少」）：" % agg["轮数"])
        print("    原始 HTML 一致 %s · 正文一致 %s → **正文可复现率 %s%%**" % (
            agg["原始 HTML 一致"], agg["正文一致"], agg["正文可复现率_pct"]))
        print("    变化归因合计：%s" % agg["变化归因合计"])
        print("    " + agg["$读法"])
    if d["变化归因"]:
        print("\n  变化归因：")
        for k, v in sorted(d["变化归因"].items(), key=lambda x: -x[1]):
            print("    %-10s %d 次" % (k, v))
    if d.get("★ 掩码后可复现率_pct") is not None:
        print("\n  ★ 所以呢（这一节才是可执行的结论）：")
        print("    ① 假设检验：把「评论数/库存/倒计时」掩成占位符后再比指纹 ——")
        print("       一致 %s/%s → **掩码后可复现率 %s%%**（未掩码 %s%%）" % (
            d["★ 掩码后一致"], s["可判"], d["★ 掩码后可复现率_pct"],
            d["正文可复现率_pct"]))
        if d["★ 掩码后一致"] == d["提取后正文 sha256 一致"]:
            print("       ✗ **假设被否**：掩码一个也没救回来。"
                  "「变化都是评论数那种小计数器」这个想法**不成立** ——")
            print("         变化里包含**真的内容改动**（促销横幅换版）。见下面的规模分档。")
        print("    ② 变更跨度分档（首个分歧 → 最后一个分歧之间的距离）：")
        for k, v in sorted((d.get("★ 变更跨度分档") or {}).items()):
            print("         %-28s %d 处" % (k, v))
        print("    ③ **合规相关表述真的变了吗**（在完整正文上抽声明后取差集）：%s 处" % (
            d["★ 变更触及合规表述"]))
        for x in (d.get("★ 变更触及合规表述的页面") or [])[:6]:
            print("         %s" % x["url_key"][:56])
            print("            消失 %s / 新增 %s" % (x["命中"]["消失的声明"], x["命中"]["新增的声明"]))
        if not d["★ 变更触及合规表述"]:
            print("       ★ **本次 %d 处变更里，声明集合一处都没变。**" % (
                s["可判"] - d["提取后正文 sha256 一致"]))
            print("         读法：这些「变化」对法务是噪声 —— 而当前口径会把它报成「正文变了」。")
    exp = d["静态暴露面"]
    print("\n  静态暴露面（另一件事，别与上面的率混读）：")
    print("    92 个页面里含波动片段的：%d/%d = %s%%" % (
        exp["含波动片段的页面"], exp["分母"], exp["占比_pct"]))
    for k, v in sorted(exp["逐形态"].items(), key=lambda x: -x[1]):
        print("      %-10s %d 页" % (k, v))
    print("\n" + d["$这一组数的读法"])
    print("→ %s" % OUT.relative_to(ROOT))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
