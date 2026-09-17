#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_landing.py —— 批次 C 验收器

对应 `research/landing/方案.md` §六 的六条验收。**可重复运行，任何人重跑得同一结论。**

  V1 URL 清单完整      204 条广告引用全部有归属；唯一 URL 数与独立重算一致
  V2 分母诚实          成功率分母 = URL 总数；每个 URL 恰好归入一个档；失败项逐条在案
  V3 可复算            指标可由 抓取结果 + 要素提取 重算；要素可由 _evidence 的 gz 重算
  V4 指纹稳定          抽样重抓，内容指纹一致（需网络；--offline 可跳过）
  V5 边界显式          报告必须含「本批次做不到的事」一节
  V6 无越界判定        产物中不得出现「合规/不合规」类结论

**V5 与 V6 是硬门**：本项目已确立「声明 GAP 算通过，静默略过算失败」的验收风格。

用法：
  python3 tools/verify_landing.py                 # 全部（含网络抽检 3 个）
  python3 tools/verify_landing.py --offline       # 跳过 V4 的网络部分
  python3 tools/verify_landing.py --recheck 6     # 抽检 6 个 URL
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAND = ROOT / "research/landing"
LIVE = ROOT / "research/live/snapshot-20260916T050845Z.json"
REPORT = LAND / "内容获取实测报告.md"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

ok_n = fail_n = skip_n = 0
def ok(m, d=""):
    global ok_n; ok_n += 1
    print(f"  ✅ {m}" + (f"\n       {d}" if d else ""))
def bad(m, d=""):
    global fail_n; fail_n += 1
    print(f"  ❌ {m}" + (f"\n       {d}" if d else ""))
def skip(m, d=""):
    global skip_n; skip_n += 1
    print(f"  ⊘  {m}" + (f"\n       {d}" if d else ""))


def jload(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--recheck", type=int, default=3)
    args = ap.parse_args()

    need = ["urls.json", "抓取结果.json", "要素提取.json", "指标.json", "一致性分析.json"]
    missing = [f for f in need if not (LAND / f).exists()]
    if missing:
        print(f"✗ 缺产物 {missing}，先把流程跑完", file=sys.stderr)
        return 2
    U, F, E, M, C = (jload(LAND / f) for f in need)
    ext = {r["url_key"]: r for r in E["results"]}
    sys.path.insert(0, str(ROOT / "tools"))
    import lp_extract                      # V3 与 V4 都要用，提到前面避免局部导入失效
    print(f"批次 C 验收 · 快照 {E['snapshot']}\n")

    # ── V1 URL 清单完整
    print("V1 URL 清单完整")
    live = jload(LIVE)

    def landing_url(fields):
        """与 tools/ 建清单时同一口径：字段可能是 str / list[dict] / dict。"""
        x = fields.get("落地页URL")
        if isinstance(x, list):
            return "".join((y.get("link") or y.get("text") or "")
                           for y in x if isinstance(y, dict)).strip()
        if isinstance(x, dict):
            return (x.get("link") or x.get("text") or "").strip()
        return (x or "").strip()

    real_refs = sum(1 for r in live["sources"]["ad_copy"]["records"]
                    if landing_url(r["fields"]))
    if U["total_ad_refs"] == 204 and real_refs == 204:
        ok(f"广告引用 204 条（独立重算 {real_refs}）")
    else:
        bad(f"广告引用数不符：清单 {U['total_ad_refs']} / 重算 {real_refs}")
    if U["unique_urls"] == len(U["urls"]) and len(U["urls"]) == len(F["results"]):
        ok(f"唯一 URL {len(U['urls'])} 个，清单与抓取结果逐条对齐")
    else:
        bad(f"唯一 URL 数不一致：urls {len(U['urls'])} / results {len(F['results'])}")
    refs_sum = sum(u["ad_refs"] for u in U["urls"])
    if refs_sum == 204:
        ok(f"每条 URL 的 ad_refs 求和 = 204（无引用被丢弃）")
    else:
        bad(f"ad_refs 求和 = {refs_sum} ≠ 204")

    # ── V2 分母诚实
    print("\nV2 分母诚实")
    rows = M["逐URL"]
    N = len(rows)
    if M["指标1_内容获取成功率"]["分母"] == N == len(F["results"]):
        ok(f"成功率分母 = URL 总数 = {N}（不是「成功数」）")
    else:
        bad("分母 != URL 总数")
    tiers = {}
    for r in rows:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    if sum(tiers.values()) == N:
        ok(f"每个 URL 恰好归入一个档：{tiers}")
    else:
        bad(f"分档计数 {sum(tiers.values())} ≠ {N}")
    fails = M["指标1_内容获取成功率"]["失败明细"]
    bad_rows = [r for r in rows if r["tier"] not in ("ok", "ok_structured")]
    if len(fails) == len(bad_rows):
        ok(f"失败项逐条在案：{len(fails)} 条（与逐URL 重算一致）")
    else:
        bad(f"失败明细 {len(fails)} ≠ 重算 {len(bad_rows)}")
    suc = sum(v for k, v in tiers.items() if k in ("ok", "ok_structured"))
    declared = M["指标1_内容获取成功率"]["成功"]
    if suc == declared:
        ok(f"成功数一致：{suc}/{N}")
    else:
        bad(f"成功数不一致：分档 {suc} / 声明 {declared}")

    # ── V3 可复算
    print("\nV3 可复算")
    try:
        evdir = LAND / "_evidence" / E["snapshot"]
        sample = [r for r in E["results"] if r.get("html")][:8]
        drift = []
        for r in sample:
            stored = next((a["stored"] for fr in F["results"] if fr["url_key"] == r["url_key"]
                           for a in fr["attempts"] if a["label"] == "html" and a.get("stored")), None)
            if not stored:
                continue
            with gzip.open(evdir / stored, "rb") as f:
                body = f.read()
            again = lp_extract.analyze_html(body)
            if again["body_chars"] != r["html"]["body_chars"] or again["title"] != r["html"]["title"]:
                drift.append((r["url_key"], r["html"]["body_chars"], again["body_chars"]))
        if not drift:
            ok(f"从 _evidence 重算 {len(sample)} 个页面的正文长度与标题，逐条一致")
        else:
            bad(f"{len(drift)} 个页面重算不一致", str(drift[:3]))
    except Exception as e:
        bad("重算失败", f"{type(e).__name__}: {e}")

    # 指纹与文件对应关系
    stored_refs = [a["stored"] for r in F["results"] for a in r["attempts"] if a.get("stored")]
    absent = [s for s in stored_refs if not (LAND / "_evidence" / E["snapshot"] / s).exists()]
    if not absent:
        ok(f"{len(stored_refs)} 个 stored 路径全部真实存在（无悬空引用）")
    else:
        bad(f"{len(absent)} 个 stored 路径找不到文件", str(absent[:3]))

    # ── V4 指纹稳定
    print("\nV4 内容指纹稳定")
    print("    口径：原始 HTML 的 sha256 会因为内嵌的每次请求唯一 reqid / 埋点脚本而变化，"
          "\n          所以「内容指纹」必须建立在**提取后的正文**上（ADR-0002）。两种都测。")
    if args.offline or args.recheck <= 0:
        skip("--offline，跳过重抓抽检")
    else:
        cand = [r for r in F["results"] if r["tier_raw"].startswith("ok")][:args.recheck]
        raw_same = raw_diff = err = 0
        txt_same = txt_diff = 0
        for r in cand:
            a = next((x for x in r["attempts"] if x["label"] == "html" and x.get("sha256")), None)
            e = ext.get(r["url_key"])
            if not a or not e or not e.get("html"):
                continue
            try:
                req = urllib.request.Request(r["url"], headers={"User-Agent": UA}, method="GET")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    b = resp.read(6 * 1024 * 1024)
            except Exception as ex:
                err += 1
                print(f"       ! {r['url_key'][:70]} {type(ex).__name__}")
                continue
            if hashlib.sha256(b).hexdigest() == a["sha256"]:
                raw_same += 1
            else:
                raw_diff += 1
            again = lp_extract.analyze_html(b)["body_text"]
            if hashlib.sha256(again.encode()).hexdigest() == \
               hashlib.sha256(e["html"]["body_text"].encode()).hexdigest():
                txt_same += 1
            else:
                txt_diff += 1
        if txt_same and txt_diff == 0:
            ok(f"抽检 {txt_same} 个 URL，**提取后正文的指纹逐字节一致**"
               f"（其中原始 HTML 指纹变化 {raw_diff} 个 —— 属预期，见口径说明）")
        elif txt_diff:
            bad(f"提取后正文指纹也在变：一致 {txt_same} / 变化 {txt_diff}",
                "正文级指纹不稳会动摇 ADR-0002，需先查清原因")
        else:
            skip(f"抽检未能完成（网络错误 {err}）")

    # ── V5 边界显式
    print("\nV5 边界显式")
    if not REPORT.exists():
        bad(f"报告不存在：{REPORT.relative_to(ROOT)}")
    else:
        txt = REPORT.read_text(encoding="utf-8")
        marks = ["本批次做不到", "做不到的事", "边界"]
        if any(m in txt for m in marks):
            ok("报告含「本批次做不到的事 / 边界」一节")
        else:
            bad("报告缺少边界声明（硬门：声明 GAP 算通过，静默略过算失败）")
        for kw in ["分母", "复现", "python3 tools/"]:
            if kw in txt:
                ok(f"报告含「{kw}」")
            else:
                bad(f"报告缺少「{kw}」")

    # ── V6 无越界判定
    print("\nV6 无越界判定")
    verdict_pat = re.compile(r"(该内容|此文案|页面)\s*(属于|构成|判定为|认定为)\s*(违规|合规)|"
                             r"判定结果\s*[:：]\s*(违规|合规)")
    hits = []
    for f in ["指标.json", "一致性分析.json", "要素提取.json"]:
        t = (LAND / f).read_text(encoding="utf-8")
        for m in verdict_pat.finditer(t):
            hits.append((f, m.group(0)))
    if not hits:
        ok("机器产物中未出现「合规/违规」的结论性判定")
    else:
        bad(f"发现 {len(hits)} 处越界判定", str(hits[:3]))
    # 报告允许出现「是否合规由法务判断」这类**否定式**免责，但要确认它声明了
    if REPORT.exists():
        rt = REPORT.read_text(encoding="utf-8")
        if "不判定" in rt or "只呈现事实" in rt or "由法务" in rt:
            ok("报告声明了「只呈现事实、不替代判断」")
        else:
            bad("报告未声明不越界（ADR-0005）")

    print(f"\n{'='*58}\n通过 {ok_n} · 失败 {fail_n} · 跳过 {skip_n}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(main())
