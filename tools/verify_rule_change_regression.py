#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_rule_change_regression.py —— 验收表行 87 / 戊·SEC-6-GS-5·SEC-8-6

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:219`）

> 在测试分支分别做规则**新增、删除、修改各一次**，每次跑冻结回归集（50-100 条），
> 断言输出包含**同一组样本变更前后的指标对比读数与差异**，而不只是变更后的单点数值；
> 只跑一种变更或只出单份读数即红。构造一个改规则但不跑回归集（或回归集失败）的变更 PR，
> 断言合并被挡住；未跑回归集的变更不得合入。

## 这一票是「三层」里的第三层（三层**分开报**，不许互相盖住）

| 层 | 验什么 | 落在哪 | 状态 |
|---|---|---|---|
| 1 | `merge_allowed()` **纯函数**对不对 | `tools/verify_regression_set.py` 的 `GS-GATE`（#85） | 已入库 |
| 2 | **有没有东西在跑**（触发者） | `verify_acceptance_trigger.py` + `acceptance-ratchet.json`（05，`137f87a`） | 已入库 |
| 3 | **真跑一次变更 → 真出两份读数 → 差异真被记下** | **本文件** | 本票 |

★ 用「`GS-GATE` 绿了」盖掉第 3 层，等于说「门写得对」= 「门真的被走过了」。
  两者不同形：前者是判据，后者是行为。

## 断言

  RC-ADD     新增一条规则：before/after 两份读数齐全、样本 ID 集恒等、至少 1 条变化
  RC-DEL     删除一条规则：同上
  RC-MOD     修改一条规则（改 match 关键词）：同上
  RC-SHAPE   三份报告都同时含**每条样本**的 before 与 after 读数（不是只有 after）
  RC-IDSET   每个变更的 before/after 样本 ID 集合**恒等**（少一条即红）
  RC-SINGLE  反向对照：**只给 after 单点**的报告必须红（这是行 87 的原话）
  RC-NOOP    反向对照：变更没改变任何样本 → 红
             （分不清「变更没生效」与「语料碰不到」，只看单点数值时两者同形）
  RC-MANIFEST **「改规则」在真仓里必须留版本痕**：`skeleton/rules-v1.json` 的
             sha256/bytes 必须与 `skeleton/engine-manifest.json` 记录值相等
             （直接改规则而不跑 `engine_manifest.py --write` → 红）。
             2026-10-23 变异探针实测：改一条规则、manifest 不动，本验证器 6 项全过 ——
             tempdir 副本上的流程再严，管不到真仓那份规则表。
             ★ 本文件「重跑 manifest 否则版本号会撒谎」的要求，此前只落在
               tempdir 副本上；这一条把它落回真仓。

## 变更怎么注入（不是「假造一个变更流程」）

规则表是**静态 JSON**、没有变更 API —— 所以「在测试分支做变更」在这个架构下
**没有可调用的对象**。本文件的做法规避开这一层，直接做**引擎层的行为验证**：

  1. `shutil.copytree` 把 `research/governance/skeleton/` 复制到 tempdir
  2. 在**副本**上改一条规则（新增 / 删除 / 修改）
  3. 重跑 `engine_manifest.py --write`（否则版本号会撒谎 —— 这是 `ab_engine_diff.py:99-101` 的教训）
  4. 子进程跑引擎取读数

**从不改仓内的规则文件。** 这是 §2.4.4「自证不许有副作用」的要求。

## **本文件不证明什么**（结论行必须照抄）

* **不证明「测试分支」这件事存在。** CI 的**配置层**已入库
  （`.github/workflows/acceptance.yml`，2026-10-23：PR 通道跑执行器 + 棘轮硬门），
  但「远端真的挡住了合并」本机读不到（无分支保护读数）——
  本文件用 tempdir 副本模拟的是**引擎对规则变更的响应**，
  工作流层与远端强制层各有自己的票。
* **不证明合并被挡住。** 那是第 1 层（`GS-GATE`）与第 2 层（触发者）的事，
  两者各有自己的票与本文件分开报。
* **不证明报告的渲染层。** 本文件产出的是**结构化读数**；把它渲染成人读报告的
  那一跳不在这里（`base/report_store.py` / `report_render.mjs` 各有验证器）。

## 退出码

  0 全过 · 1 有红 · 2 未测（回归集或 skeleton 读不出 / 引擎不可用）

## 用法

    python3 tools/verify_rule_change_regression.py
    python3 tools/verify_rule_change_regression.py --controls
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKEL = ROOT / "research" / "governance" / "skeleton"
REGRESSION = ROOT / "research" / "governance" / "regression-set-v1.json"
ENGINE_MANIFEST = SKEL / "engine-manifest.json"
RULES_FILE = SKEL / "rules-v1.json"

# 三类变更各自要触发的规则。挑的是**回归集里确实会命中**的规则，
# 否则「变更没生效」与「语料碰不到」在读数上同形（行 87 原话点名的那个坑）。
TARGET_RULE = "T1.1.medical-cure"

_CHILD = r'''
import json, sys
sys.path.insert(0, ".")
import judge as J
samples = json.load(open(sys.argv[1], encoding="utf-8"))
out = []
for s in samples:
    r = J.judge(s["text"], origin="test")
    L = r["verdict"].get("layer") or {}
    out.append({
        "id": s["id"],
        "disposition": r["verdict"].get("disposition"),
        "hits": sorted(h.get("rule_key") for h in (r.get("hits") or [])),
        "layer": L.get("id"),
        "escalated": sorted(e.get("id") for e in (L.get("escalated_by") or [])),
        "exempted": sorted(k for e in (L.get("exemptions_applied") or [])
                           for k in (e.get("rule_keys") or [])),
    })
print(json.dumps(out, ensure_ascii=False))
'''


def run_engine(skel_dir: Path, samples: list) -> list:
    """在 `skel_dir` 里跑引擎，返回逐样本读数。

    ★ 样本从**文件**传进去而不是 stdin：`ab_engine_diff.py` 用的是
      `_data/records.json`，而我们这里要喂冻结回归集的 83 条。
    """
    tmp_samples = skel_dir / "_rc_samples.json"
    tmp_samples.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([sys.executable, "-c", _CHILD, str(tmp_samples)],
                       cwd=str(skel_dir), capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError("引擎失败：%s" % (p.stderr or p.stdout)[-600:])
    return json.loads(p.stdout.strip().splitlines()[-1])


def refresh_manifest(skel_dir: Path):
    """改完规则必须重算 manifest，否则版本号会撒谎。

    ★ 这是 `ab_engine_diff.py:99-101` 记下的教训，照抄：
      「改写前引擎需要一份与磁盘一致的 manifest，否则版本号会撒谎」。
    """
    subprocess.run([sys.executable, "engine_manifest.py", "--write"],
                   cwd=str(skel_dir), capture_output=True, text=True)


def make_variant(kind: str) -> Path:
    """复制 skeleton 到 tempdir 并施加一种变更，返回副本目录。

    ★ 三种变更都**只动一条规则**，且都指向 `TARGET_RULE`（回归集里确实会命中的那条）。
    """
    td = Path(tempfile.mkdtemp(prefix="rc-%s-" % kind))
    dst = td / "skeleton"
    shutil.copytree(SKEL, dst)
    rp = dst / "rules-v1.json"
    data = json.loads(rp.read_text(encoding="utf-8"))
    rules = data["rules"]

    if kind == "add":
        # 新增一条**必然命中**的规则：关键词取自回归集里已有的样本。
        # ★ 2026-10-23 修：第一版我编了 `topic: "probe"` —— 主题树里没有这个节点，
        #   引擎直接拒绝（「规则引用了主题树上不存在的节点：RC.probe-added → probe」）。
        #   **这是我这轮的第三次「凭印象编字段」**（前两次：run_benchmark 签名、
        #   probe 返回值）。现在照抄一条真实规则的**完整字段集**，只改必要的四个值，
        #   并复用真实 topic `T1.1`（从 T1.1.medical-cure 那里读出来，不是猜的）。
        new = {
            "rule_key": "T1.1.rc-probe-added",
            "parent_rule": "T1.1.rc-probe-added",
            "topic": "T1.1",                    # ← 真实节点
            "topic_label": "回归验证用新增规则",
            "modality": "text",
            "severity": "L1",
            "disposition": "auto_reject",
            "evaluability": "machine",
            "match": {"keywords": ["breast pump"], "patterns": [], "languages": ["en"]},
            "downgrade_band": None,
            "evidence_required": [],
            "external_ref": [],
            "source_legacy": False,
            "detection_layer": "native",        # ← 照抄真实规则的取值
        }
        rules.append(new)
    elif kind == "delete":
        before = len(rules)
        data["rules"] = [r for r in rules if r.get("rule_key") != TARGET_RULE]
        assert len(data["rules"]) == before - 1, "删除没有生效"
    elif kind == "modify":
        hit = [r for r in rules if r.get("rule_key") == TARGET_RULE]
        assert hit, "要修改的规则不存在"
        m = hit[0].setdefault("match", {})
        kws = list(m.get("keywords") or [])
        # 把关键词换成另一个能让回归集样本命中的词
        m["keywords"] = ["breast pump"]
        m["patterns"] = []
        assert kws != m["keywords"], "修改没有改变关键词"
    else:
        raise ValueError(kind)

    rp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    refresh_manifest(dst)
    return dst


def diff_readings(before: list, after: list):
    """逐条比 before/after。返回 (changed_ids, missing_in_after, extra_in_after)。"""
    b = {r["id"]: r for r in before}
    a = {r["id"]: r for r in after}
    changed = sorted(i for i in (set(b) & set(a)) if b[i] != a[i])
    return changed, sorted(set(b) - set(a)), sorted(set(a) - set(b))


def check_manifest_fresh(rules_bytes=None, manifest=None):
    """RC-MANIFEST：真仓的规则表必须与引擎清单对上账（2026-10-24 补）。

    抓的是哪种：在**真仓**里直接编辑 `rules-v1.json` 而不跑
    `engine_manifest.py --write`。审计里 survived 的正是这个变异
    （`research/governance/skeleton/rules-v1.json` 被改一条规则后，
    本验证器 6 项全过退 0 —— 因为三种变更都只发生在 tempdir 副本里，
    副本上 manifest 重算了，真仓那份没人看）。

    manifest 是判定回执里 rule_version 的唯一来源（`judge.py::versions()`）——
    它一过期，所有已出回执都答不了「这是哪版规则算的」，行 87 的
    「变更前后对比」就没有可信的版本锚点。

    ★ 合法程序：改规则 → `python3 engine_manifest.py --write` → 本条转绿。
      所以这条变异不算「不许改规则」，是「改了必须重算版本号」。
    `rules_bytes` / `manifest` 可注入（--controls 反向对照用，不写真文件，§2.4.4）。
    """
    problems = []
    if rules_bytes is None:
        if not RULES_FILE.exists():
            return ["未测前提：规则表不存在 %s" % RULES_FILE]
        rules_bytes = RULES_FILE.read_bytes()
    if manifest is None:
        if not ENGINE_MANIFEST.exists():
            return ["没有引擎清单 %s —— 规则表没有版本留痕，"
                    "「变更前后」无从对版本" % ENGINE_MANIFEST.relative_to(ROOT)]
        try:
            manifest = json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8"))
        except ValueError as exc:
            return ["引擎清单解析失败：%s —— 未测" % exc]
    art = (manifest.get("artifacts") or {}).get("rules") or {}
    rec_sha, rec_bytes = art.get("sha256"), art.get("bytes")
    if not rec_sha:
        return ["引擎清单里没有 rules 制品的 sha256 —— 规则表不在版本留痕内"]
    cur_sha = hashlib.sha256(rules_bytes).hexdigest()
    if cur_sha != rec_sha or len(rules_bytes) != rec_bytes:
        problems.append(
            "真仓规则表与引擎清单对不上：manifest 记录 sha256=%s… bytes=%s，"
            "盘上实算 sha256=%s… bytes=%d —— 改了规则没重算 manifest"
            "（合法程序：python3 research/governance/skeleton/engine_manifest.py --write）"
            % (str(rec_sha)[:12], rec_bytes, cur_sha[:12], len(rules_bytes)))
    return problems


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def check_report_shape(report):
    """RC-SHAPE：报告必须同时含每条样本的 before 与 after，不能只有 after。"""
    problems = []
    if not isinstance(report, dict):
        return ["报告不是对象"]
    if "before" not in report:
        problems.append("报告没有 before 块 —— 只有 after 单点数值（行 87 明令这是红的）")
    if "after" not in report:
        problems.append("报告没有 after 块")
    if "before" in report and "after" in report:
        b = {r.get("id") for r in (report["before"] or [])}
        a = {r.get("id") for r in (report["after"] or [])}
        if not b:
            problems.append("before 为空 —— 没有可比的基线")
        if b != a:
            problems.append("before/after 样本 ID 集合不等：只在 before 的 %r，只在 after 的 %r"
                            % (sorted(b - a)[:3], sorted(a - b)[:3]))
    return problems


def check_changed(report):
    """RC-NOOP：变更必须至少改变一条样本。"""
    changed = report.get("changed_ids") or []
    if not changed:
        return ["changed_ids 为空 —— 分不清「变更没生效」与「语料碰不到它」"
                "（行 87 原文：只看后测单点数值时，这两件事长得一样）"]
    return []


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 87 / 戊·SEC-6-GS-5·SEC-8-6 · 规则变更前后对比读数")
    print("=" * 72)

    if not SKEL.is_dir() or not REGRESSION.exists():
        print("  ⚠ 读不到 skeleton 或回归集 —— 未测，不是通过")
        return 2
    try:
        reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("  ⚠ 回归集解析失败：%s —— 未测" % exc)
        return 2

    samples = [{"id": s["id"], "text": s["text"]} for s in (reg.get("samples") or [])]
    if not (50 <= len(samples) <= 100):
        print("  ❌ 回归集条数 %d 不在 50–100 —— 本票要求跑冻结集" % len(samples))
        return 1

    # RC-MANIFEST：真仓的「改规则留痕」对账。放在跑引擎**之前**：
    # 真仓规则表与 manifest 对不上时，本票后面一切 before/after 的版本语义都悬空。
    mfp = check_manifest_fresh()
    check("RC-MANIFEST", not mfp,
          "真仓规则表与 engine-manifest.json 一致（改过规则必重算 manifest）"
          if not mfp else str(mfp[:2]))

    # 基线：未改动的 skeleton
    base_td = Path(tempfile.mkdtemp(prefix="rc-base-"))
    try:
        base_dir = base_td / "skeleton"
        shutil.copytree(SKEL, base_dir)
        refresh_manifest(base_dir)
        try:
            baseline = run_engine(base_dir, samples)
        except Exception as exc:  # noqa: BLE001
            print("  ⚠ 基线引擎跑不起来：%s —— 未测" % exc)
            return 2
    finally:
        shutil.rmtree(base_td, ignore_errors=True)

    print("  基线：%d 条样本，%d 条有命中"
          % (len(baseline), sum(1 for r in baseline if r["hits"])))

    reports = {}
    for kind, cid, label in (("add", "RC-ADD", "新增一条规则"),
                             ("delete", "RC-DEL", "删除一条规则"),
                             ("modify", "RC-MOD", "修改一条规则")):
        d = None
        try:
            d = make_variant(kind)
            after = run_engine(d, samples)
        except Exception as exc:  # noqa: BLE001
            check(cid, False, "%s 时引擎失败：%s" % (label, exc))
            continue
        finally:
            if d is not None:
                shutil.rmtree(d.parent, ignore_errors=True)

        changed, missing, extra = diff_readings(baseline, after)
        report = {"kind": kind, "before": copy.deepcopy(baseline),
                  "after": after, "changed_ids": changed,
                  "missing_in_after": missing, "extra_in_after": extra}
        reports[kind] = report

        shape = check_report_shape(report)
        noop = check_changed(report)
        ok = not shape and not noop
        check(cid, ok,
              "%s：before %d 条 / after %d 条，%d 条变化（%r…）"
              % (label, len(baseline), len(after), len(changed), changed[:3])
              if ok else "%s 不合格：%s" % (label, (shape + noop)[:2]))

    # RC-SHAPE / RC-IDSET / RC-SINGLE / RC-NOOP 的成对反向对照
    if reports:
        shapes = [check_report_shape(r) for r in reports.values()]
        check("RC-SHAPE", not any(shapes),
              "三份报告都同时含 before 与 after（不是只有 after 单点）"
              if not any(shapes) else str([s for s in shapes if s][:2]))

        idsets = [check_report_shape(r) for r in reports.values()]
        # ID 集合恒等已含在 check_report_shape 里；这里单独再报一次，便于定位
        bad_ids = [k for k, r in reports.items()
                   if {x["id"] for x in r["before"]} != {x["id"] for x in r["after"]}]
        check("RC-IDSET", not bad_ids,
              "三种变更的 before/after 样本 ID 集合都恒等" if not bad_ids
              else "ID 集合不等的变更：%r" % bad_ids)

        # 反向对照：只给 after 的报告必须红
        single = check_report_shape({"after": baseline, "changed_ids": ["x"]})
        # 反向对照：变更没改变任何样本必须红
        noop = check_changed({"changed_ids": []})
        check("RC-SINGLE", bool(single) and bool(noop),
              "反向对照成对成立：只有 after 单点 → 红；变更没改任何样本 → 红"
              if (single and noop) else
              "对照失效：单点=%r 零变化=%r" % (single, noop))

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 只证明：三种规则变更各跑一次、每次都有 before/after 两份读数、")
    print("     样本 ID 集恒等、每种变更都至少改变了一条样本、真仓规则表与版本留痕对账成立。")
    print("     ★ 「在测试分支做变更」的工作流层已由 `.github/workflows/acceptance.yml`")
    print("       承接（PR 通道跑执行器 + 棘轮）；本文件仍只模拟**引擎对规则变更的响应**，")
    print("       不证明远端真的挡住了合并。")
    print("     ★ **不证明**合并被挡住（那是 GS-GATE 与触发者的两层，各有自己的票）。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出。**"""
    if not REGRESSION.exists():
        print("  ⚠ 回归集缺失 —— 未测")
        return 2
    reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    ids = [s["id"] for s in (reg.get("samples") or [])][:5]
    before = [{"id": i, "disposition": "catch_all"} for i in ids]
    after = [{"id": i, "disposition": "catch_all"} for i in ids]

    cases = [
        ("好样本：完整报告（before+after 同集）",
         False, lambda: check_report_shape(
             {"before": before, "after": after, "changed_ids": [ids[0]]})),
        ("坏样本：只有 after 单点",
         True, lambda: check_report_shape(
             {"after": after, "changed_ids": [ids[0]]})),
        ("坏样本：没有 after",
         True, lambda: check_report_shape({"before": before})),
        ("坏样本：before 为空",
         True, lambda: check_report_shape(
             {"before": [], "after": after, "changed_ids": [ids[0]]})),
        ("坏样本：after 少一条样本",
         True, lambda: check_report_shape(
             {"before": before, "after": after[:-1], "changed_ids": [ids[0]]})),
        ("坏样本：after 多一条样本",
         True, lambda: check_report_shape(
             {"before": before, "after": after + [{"id": "NEW", "disposition": "x"}],
              "changed_ids": [ids[0]]})),

        ("好样本：变更确实改了样本",
         False, lambda: check_changed({"changed_ids": [ids[0]]})),
        ("坏样本：变更没改变任何样本",
         True, lambda: check_changed({"changed_ids": []})),
        ("坏样本：changed_ids 缺失",
         True, lambda: check_changed({})),

        # RC-MANIFEST 的成对反向对照。全部走注入（不写 rules-v1.json /
        # engine-manifest.json，§2.4.4：自证不许有副作用）。
        ("好样本：真实规则表 × 真实 manifest（字节一致）",
         False, lambda: check_manifest_fresh()),
        ("坏样本：规则表改一个字节、manifest 没重算",
         True, lambda: check_manifest_fresh(
             rules_bytes=RULES_FILE.read_bytes() + b" ",
             manifest=json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8")))),
        ("坏样本：manifest 记录值指向别的版本",
         True, lambda: check_manifest_fresh(
             rules_bytes=RULES_FILE.read_bytes(),
             manifest={"artifacts": {"rules": {
                 "sha256": "a" * 64, "bytes": RULES_FILE.stat().st_size}}})),
        ("坏样本：manifest 里没有 rules 制品",
         True, lambda: check_manifest_fresh(
             rules_bytes=RULES_FILE.read_bytes(), manifest={"artifacts": {}})),
    ]

    print("=" * 72)
    print("verify_rule_change_regression · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-46s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 64)
    bad = 0
    for name, want_red, fn in cases:
        try:
            problems = fn()
            got_red = bool(problems)
            note = "" if got_red == want_red else "  ← " + str(problems[:2])[:80]
        except Exception as exc:  # noqa: BLE001
            got_red, note = None, "  对照自身异常：%s" % exc
        ok = (got_red is not None and got_red == want_red)
        bad += int(not ok)
        print("  %-46s %-6s %-6s %s%s"
              % (name[:46],
                 "红" if want_red else "绿",
                 "异常" if got_red is None else ("红" if got_red else "绿"),
                 "✓" if ok else "✗", note))

    print("-" * 72)
    if bad:
        print("❌ %d/%d 与预判不符 —— 差异那几行就是该查的地方" % (bad, len(cases)))
        return 1
    print("✅ %d/%d 预判全部命中" % (len(cases), len(cases)))
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--controls", action="store_true")
    args, unknown = ap.parse_known_args(argv)
    if unknown:
        print("  ⚠ 未知参数 %s —— 未测（不是通过）" % unknown)
        raise SystemExit(2)
    return args


if __name__ == "__main__":
    try:
        a = _parse_args(sys.argv[1:])
        sys.exit(run_controls() if a.controls else main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s: %s" % (type(exc).__name__, exc))
        sys.exit(2)
