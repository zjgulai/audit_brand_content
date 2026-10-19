#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_review_gold.py —— 审查结论 gold 评测（阶段 3 试点）

输入
====
  --gold  gold.json
      由真人审核意见整理的 gold。每条记录至少含：
        record_id / 品线 / 分类 / 原因文本 / 建议 / 图片名 / sha256
      可选 `findings` 数组（一条记录多个结论）；每个 finding 用
      `control_code`（或 `分类`）与 `quote`（或 `原因文本`）描述。

  --pred  model_findings.json
      模型输出，字段与 `base/semantic_judge.py` 的 finding 对齐：
        control_code / severity / quote / location
      支持三种形状：
        1. [{"record_id": "...", "control_code": "...", "quote": "..."}, ...]
        2. {"records": {"<record_id>": [finding, ...], ...}}
        3. {"records": [{"record_id": "...", "findings": [...]}, ...]}

匹配规则（写死，可复核）
========================
  同一 record_id 下，一条模型 finding 与 gold 结论算 hit，当且仅当：
    1. 问题类型一致：两边 `control_code`/`分类` 归一化后完全相同；
    2. 关键文本片段匹配：两边 `quote`/`原因文本` 归一化（NFKC、小写、去空白）后
       互为子串，或字符二元组 Jaccard 相似度 >= TEXT_MATCH_THRESHOLD (0.5)。
  匹配是一对一的贪心：每条 gold 结论只认一条模型 finding，剩下的模型 finding
  全部记 false_positive；gold 结论没被认领记 miss（= false_negative）。

指标
====
  hit / miss / false_positive 按记录给出，同时汇总：
    accuracy = hit / (hit + miss + false_positive)
    recall   = hit / (hit + miss)
    precision= hit / (hit + false_positive)
    classification_consistency
             = 有 gold 的记录中，至少有一条模型 finding 类型匹配的记录数 / 有 gold 的记录数
  分母为 0 时指标为 null，不写 0 冒充「测过了」。

退出码
======
  0  评测完成（指标好坏不影响退出码）
  1  输入格式错误 / 写盘失败
  2  未测：缺 --gold 或 --pred 文件（真实模型未接入时不伪造读数）

  `--self-test` 只跑合成样本，不读真实模型；0 全过 / 1 有红。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter

TEXT_MATCH_THRESHOLD = 0.5
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
GOLD_REQUIRED = ("record_id", "品线", "分类", "原因文本", "建议", "图片名", "sha256")


class Untested(Exception):
    """缺输入文件：这是未测，不是失败。"""


class BadInput(Exception):
    """输入存在但不可用：这是红，不是未测。"""


def _norm_text(value):
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", "", s)


def _bigrams(text):
    return Counter(text[i:i + 2] for i in range(max(0, len(text) - 1)))


def text_similarity(a, b):
    """归一化后的子串命中或字符二元组 Jaccard。"""
    a, b = _norm_text(a), _norm_text(b)
    if not a or not b:
        return 1.0 if a == b else 0.0
    if a in b or b in a:
        return 1.0
    ba, bb = _bigrams(a), _bigrams(b)
    union = sum((ba | bb).values())
    if union == 0:
        return 1.0 if a == b else 0.0
    return sum((ba & bb).values()) / float(union)


def _norm_type(value):
    return str(value or "").strip().lower()


def _gold_findings(record):
    raw = record.get("findings")
    if raw is None:
        raw = [{"control_code": record.get("分类"),
                "quote": record.get("原因文本")}]
    if not isinstance(raw, list) or not raw:
        raise BadInput("%s.findings 必须是非空数组" % record.get("record_id"))
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise BadInput("%s.findings[%d] 不是对象" % (record.get("record_id"), i))
        typ = item.get("control_code") or item.get("分类") or item.get("category")
        text = item.get("quote") if item.get("quote") is not None else item.get("原因文本")
        if not _norm_type(typ):
            raise BadInput("%s.findings[%d] 缺 control_code/分类" % (record.get("record_id"), i))
        if not isinstance(text, str) or not text.strip():
            raise BadInput("%s.findings[%d] 缺 quote/原因文本" % (record.get("record_id"), i))
        out.append({"type": typ, "text": text, "advice": item.get("建议")})
    return out


def load_gold(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise Untested("gold 不存在：%s" % path)
    except (OSError, ValueError) as exc:
        raise BadInput("gold 读不出：%s" % exc)
    if isinstance(data, dict) and "records" in data:
        records = data["records"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        raise BadInput("gold 顶层必须是对象、数组或 {records:[...]}")
    if not isinstance(records, list) or not records:
        raise BadInput("gold.records 必须是非空数组")
    out = []
    seen = set()
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise BadInput("gold.records[%d] 不是对象" % i)
        missing = [k for k in GOLD_REQUIRED if k not in rec]
        if missing:
            raise BadInput("gold.records[%d] 缺字段 %r" % (i, missing))
        rid = rec.get("record_id")
        if not isinstance(rid, str) or not rid.strip():
            raise BadInput("gold.records[%d].record_id 必须是非空字符串" % i)
        if rid in seen:
            raise BadInput("gold.record_id 重复：%s" % rid)
        seen.add(rid)
        if not isinstance(rec.get("品线"), str) or not rec["品线"].strip():
            raise BadInput("%s.品线 必须是非空字符串" % rid)
        if not isinstance(rec.get("分类"), str) or not rec["分类"].strip():
            raise BadInput("%s.分类 必须是非空字符串" % rid)
        if not isinstance(rec.get("原因文本"), str) or not rec["原因文本"].strip():
            raise BadInput("%s.原因文本 必须是非空字符串" % rid)
        if not isinstance(rec.get("建议"), str):
            raise BadInput("%s.建议 必须是字符串" % rid)
        if not isinstance(rec.get("图片名"), str) or not rec["图片名"].strip():
            raise BadInput("%s.图片名 必须是非空字符串" % rid)
        if not isinstance(rec.get("sha256"), str) or not SHA256_RE.match(rec["sha256"]):
            raise BadInput("%s.sha256 必须是 64 位十六进制" % rid)
        out.append({
            "record_id": rid,
            "品线": rec["品线"],
            "分类": rec["分类"],
            "原因文本": rec["原因文本"],
            "建议": rec["建议"],
            "图片名": rec["图片名"],
            "sha256": rec["sha256"].lower(),
            "findings": _gold_findings(rec),
        })
    return out


def _finding_from_pred(item, record_id=None):
    if not isinstance(item, dict):
        raise BadInput("pred finding 不是对象")
    rid = record_id or item.get("record_id")
    if not isinstance(rid, str) or not rid.strip():
        raise BadInput("pred finding 缺 record_id")
    typ = item.get("control_code") or item.get("category") or item.get("分类")
    quote = item.get("quote") if item.get("quote") is not None else item.get("原因文本")
    if not _norm_type(typ):
        raise BadInput("%s 的 pred finding 缺 control_code/category" % rid)
    if not isinstance(quote, str):
        raise BadInput("%s 的 pred finding.quote 必须是字符串" % rid)
    return {"record_id": rid, "type": typ, "quote": quote,
            "severity": item.get("severity"),
            "location": item.get("location")}


def load_pred(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise Untested("pred 不存在：%s" % path)
    except (OSError, ValueError) as exc:
        raise BadInput("pred 读不出：%s" % exc)
    grouped = {}
    if isinstance(data, list):
        for item in data:
            f = _finding_from_pred(item)
            grouped.setdefault(f["record_id"], []).append(f)
    elif isinstance(data, dict) and isinstance(data.get("records"), dict):
        for rid, items in data["records"].items():
            if not isinstance(items, list):
                raise BadInput("pred.records[%r] 必须是数组" % rid)
            for item in items:
                f = _finding_from_pred(item, record_id=rid)
                grouped.setdefault(rid, []).append(f)
    elif isinstance(data, dict) and isinstance(data.get("records"), list):
        for row in data["records"]:
            if not isinstance(row, dict):
                raise BadInput("pred.records 的条目必须是对象")
            rid = row.get("record_id")
            items = row.get("findings") or []
            if not isinstance(items, list):
                raise BadInput("pred.records[%r].findings 必须是数组" % rid)
            for item in items:
                f = _finding_from_pred(item, record_id=rid)
                grouped.setdefault(f["record_id"], []).append(f)
    elif isinstance(data, dict) and isinstance(data.get("findings"), list):
        for item in data["findings"]:
            f = _finding_from_pred(item)
            grouped.setdefault(f["record_id"], []).append(f)
    else:
        raise BadInput("pred 顶层必须是数组、{records:{...}}、{records:[...]} 或 {findings:[...]}")
    return grouped


def _ratio(num, den):
    return (num / float(den)) if den else None


def evaluate_records(gold_records, pred_groups):
    """纯函数：返回 per_record + summary。"""
    per_record = []
    total_hit = total_miss = total_fp = 0
    total_pred = 0
    type_consistent_records = 0
    records_with_gold = 0
    for rec in gold_records:
        rid = rec["record_id"]
        gold_findings = rec["findings"]
        preds = list(pred_groups.get(rid, []))
        records_with_gold += 1
        used = set()
        hits = misses = 0
        for g in gold_findings:
            best = None
            for i, p in enumerate(preds):
                if i in used or _norm_type(p["type"]) != _norm_type(g["type"]):
                    continue
                score = text_similarity(g["text"], p["quote"])
                if best is None or score > best[0]:
                    best = (score, i)
            if best is not None and best[0] >= TEXT_MATCH_THRESHOLD:
                used.add(best[1])
                hits += 1
            else:
                misses += 1
        fps = len(preds) - len(used)
        type_match = any(_norm_type(p["type"]) == _norm_type(g["type"])
                         for p in preds for g in gold_findings)
        if type_match:
            type_consistent_records += 1
        total_hit += hits
        total_miss += misses
        total_fp += fps
        total_pred += len(preds)
        per_record.append({
            "record_id": rid,
            "品线": rec["品线"],
            "图片名": rec["图片名"],
            "sha256": rec["sha256"],
            "gold_findings": len(gold_findings),
            "pred_findings": len(preds),
            "hit": hits,
            "miss": misses,
            "false_positive": fps,
            "type_consistent": bool(type_match),
        })

    # gold 里没有的 record_id：模型只要产出 finding，就全部是 FP。
    gold_ids = {r["record_id"] for r in gold_records}
    for rid, preds in pred_groups.items():
        if rid in gold_ids or not preds:
            continue
        total_fp += len(preds)
        total_pred += len(preds)
        per_record.append({
            "record_id": rid,
            "品线": None,
            "图片名": None,
            "sha256": None,
            "gold_findings": 0,
            "pred_findings": len(preds),
            "hit": 0,
            "miss": 0,
            "false_positive": len(preds),
            "type_consistent": False,
        })

    summary = {
        "records": len(gold_records),
        "gold_findings": sum(len(r["findings"]) for r in gold_records),
        "pred_findings": total_pred,
        "hit": total_hit,
        "miss": total_miss,
        "false_positive": total_fp,
        "accuracy": _ratio(total_hit, total_hit + total_miss + total_fp),
        "recall": _ratio(total_hit, total_hit + total_miss),
        "precision": _ratio(total_hit, total_hit + total_fp),
        "classification_consistency": _ratio(type_consistent_records,
                                              records_with_gold),
        "text_match_threshold": TEXT_MATCH_THRESHOLD,
    }
    return {"summary": summary, "records": per_record}


def write_json(payload, out_path):
    if not out_path:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    parent = os.path.dirname(os.path.abspath(out_path))
    try:
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".eval_review_gold.", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, out_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:
        raise BadInput("写盘失败：%s" % exc)


def self_test():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    gold = [
        {"record_id": "r1", "品线": "pump", "分类": "H01",
         "原因文本": "宝宝存在窒息风险", "建议": "删除",
         "图片名": "r1.png", "sha256": "a" * 64},
        {"record_id": "r2", "品线": "pump", "分类": "M01",
         "原因文本": "未标注适用年龄", "建议": "补充",
         "图片名": "r2.png", "sha256": "b" * 64},
        {"record_id": "r3", "品线": "pump", "分类": "U01",
         "原因文本": "未提供检测报告", "建议": "下架",
         "图片名": "r3.png", "sha256": "c" * 64},
        {"record_id": "r5", "品线": "pump", "分类": "H01",
         "原因文本": "产品缺少警示标识", "建议": "补充",
         "图片名": "r5.png", "sha256": "d" * 64},
    ]
    pred = {
        "r1": [{"record_id": "r1", "type": "H01",
                "quote": "宝宝存在窒息风险（高风险）"}],
        # 类型错：文本相同也不能算 hit；该 finding 还要记 FP
        "r2": [{"record_id": "r2", "type": "H01",
                "quote": "未标注适用年龄"}],
        # gold r3 无 pred → miss；r4 没有 gold → FP
        "r4": [{"record_id": "r4", "type": "U01",
                "quote": "gold 里不存在的记录"}],
        # 类型相同但文本不匹配 → miss + FP
        "r5": [{"record_id": "r5", "type": "H01",
                "quote": "这一段与警示完全无关"}],
    }
    out = evaluate_records(load_gold_from_objects(gold), pred)
    s = out["summary"]
    check("自测 hit=1", s["hit"] == 1, str(s))
    check("自测 miss=3", s["miss"] == 3, str(s))
    check("自测 false_positive=3", s["false_positive"] == 3, str(s))
    check("自测 accuracy=1/7", s["accuracy"] == 1.0 / 7.0, str(s["accuracy"]))
    check("自测 recall=1/4", s["recall"] == 0.25, str(s["recall"]))
    check("自测 precision=1/4", s["precision"] == 0.25, str(s["precision"]))
    check("自测 分类一致率=2/4", s["classification_consistency"] == 0.5,
          str(s["classification_consistency"]))
    by_id = {r["record_id"]: r for r in out["records"]}
    check("自测 r1 记录级 hit=1/fp=0",
          by_id["r1"]["hit"] == 1 and by_id["r1"]["false_positive"] == 0,
          str(by_id["r1"]))
    check("自测 r2 类型错 → miss=1/fp=1",
          by_id["r2"]["miss"] == 1 and by_id["r2"]["false_positive"] == 1,
          str(by_id["r2"]))
    check("自测 r3 无 pred → miss=1", by_id["r3"]["miss"] == 1,
          str(by_id["r3"]))
    check("自测 r5 同类型文本不匹配 → miss=1/fp=1",
          by_id["r5"]["miss"] == 1 and by_id["r5"]["false_positive"] == 1,
          str(by_id["r5"]))
    check("自测 文本完全相同 → 相似度 1",
          text_similarity("未标注适用年龄", "未标注适用年龄") == 1.0, "")
    check("自测 文本无关 → 相似度 < 阈值",
          text_similarity("产品缺少警示标识", "这一段与警示完全无关") < TEXT_MATCH_THRESHOLD, "")
    try:
        load_pred("/definitely/not/exist/pred.json")
        check("自测 缺 pred → Untested", False, "没有抛 Untested")
    except Untested:
        check("自测 缺 pred → Untested", True, "")
    except BadInput as exc:
        check("自测 缺 pred → Untested", False, "抛了 BadInput: %s" % exc)

    for name, ok, detail in results:
        print(("✓ " if ok else "✗ ") + name + (("  " + detail) if not ok else ""))
    passed = sum(1 for _, ok, _ in results if ok)
    print("----")
    print(("✅" if passed == len(results) else "❌") +
          " eval_review_gold self-test %d/%d" % (passed, len(results)))
    return 0 if passed == len(results) else 1


def load_gold_from_objects(records):
    """自测用：复用 load_gold 的字段校验，但不读盘。"""
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json",
                                      delete=False)
    try:
        json.dump(records, tmp, ensure_ascii=False)
        tmp.close()
        return load_gold(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="审查结论 gold 评测")
    ap.add_argument("--gold", help="gold.json")
    ap.add_argument("--pred", help="model_findings.json；缺失 → 未测（rc=2）")
    ap.add_argument("--out", help="结果 JSON 输出路径；缺省写 stdout")
    ap.add_argument("--self-test", action="store_true",
                    help="只跑合成样本，不读真实模型")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.gold:
        print("未测：缺 --gold；未测不是通过", file=sys.stderr)
        return 2
    if not args.pred:
        print("未测：缺 --pred（真实模型未接入）；未测不是通过", file=sys.stderr)
        return 2

    try:
        gold = load_gold(args.gold)
        pred = load_pred(args.pred)
        result = evaluate_records(gold, pred)
        write_json(result, args.out)
        return 0
    except Untested as exc:
        print("未测：%s；未测不是通过" % exc, file=sys.stderr)
        return 2
    except BadInput as exc:
        print("❌ 输入不可用：%s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
