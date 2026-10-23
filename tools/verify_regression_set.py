#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_regression_set.py —— 验收表行 85 / SEC-6-GS-* · 冻结回归集

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:217`）

> 读取冻结回归集清单，断言条目数在 **50-100** 之间（含端点），49 条或 101 条都红。
> 在回归集里逐条匹配 `Best Seller`、`100% cotton`、`最新`、`first-time mom` 四个字面量，
> 断言四条都存在且都标注为负样本（预期不误杀），缺任一条即红。
> 按 family 统计回归集条数，断言每个有控制点的族至少 3 条；断言空族
> （**以 `control-points-v1.json` 的 `empty_families` 为准**）没有为凑数而加入的条目；
> 有控制点族不足 3 条即红。
> 断言每条样本有指纹字段且可复算；修改一条样本后，断言变更记录中出现**操作人、时间、原因**
> 三项，缺任一项即红。
> 检查 CI/分支保护是否把回归集设为规则文件变更的必需检查；构造一个改规则但不跑回归集的 PR，
> 断言合并被挡住；不跑也能合即红。
> 再在测试分支做一次规则变更，跑回归集，断言产出变更前/后两份读数与差异。

## 断言

  GS-0   回归集文件存在、可解析、结构完整
  GS-SIZE 条目数 50–100（含端点）
  GS-TRAP 四个陷阱字面量各至少 1 条，且该条 `expected.kind` 是负样本类
  GS-FAMILY **运行时读** `control-points-v1.json`：有控制点的族 ≥3 条；
          空族（`empty_families`）必须 **0** 条（不许为凑数加）
  GS-CONSIST  **`control-points-v1.json` 自身必须自洽**：`status_note` 里声称的空族
          与 `empty_families` 的实际条目**不许矛盾**
          （★ 2026-10-22 实测到一处：`status_note` 写「空 4 族（含品牌控制）」，
            而同文件 `empty_families` 只有 3 族 —— 此前没有任何断言能抓到）
  GS-FP   每条样本的指纹可复算且与记录值相等
  GS-CHANGE  `changelog` 每条都有 `operator` / `at` / `reason` 三项且非空
  GS-CHG-PIN **改样本必须留变更痕迹**：GS-FP / GS-CHANGE 各自只查自己那侧
          （改 text 且同步指纹 → GS-FP 绿；changelog 是历史列表 → 不看样本），
          两个方向合起来 0 断言（2026-10-23 变异探针实测 survived）。
          本条两半：①样本数组实算指纹必须等于 `FROZEN_SET_FINGERPRINT`
          （写进本文件的冻结读数，与 acceptance-ratchet.json 地板同模式）；
          ②changelog 记账纪律（初始条目之外不许缺 `after_fingerprint`；
          最新条目若带值必须等于当前实算）。改样本而三者（changelog 条目 /
          冻结读数 / 样本自身指纹）缺一 → 红。
  GS-RULES-FP **规则表与引擎清单对账**：`rules-v1.json` 的 sha256/bytes 必须与
          `skeleton/engine-manifest.json` 记录值相等 —— 直接改规则而不跑
          `engine_manifest.py --write` 的变异，门函数（纯函数）与 CI 断言
          （只看工作流文本）都无感（2026-10-23 变异探针实测 survived）。
          manifest 是本仓唯一的规则版本留痕，judge.py 的 rule_version 从它派生。
  GS-CI-ENFORCE **改规则必须先跑回归集（CI/分支保护通道，配置层）**：
          `.github/workflows/acceptance.yml` 必须同时 (a) 在 `pull_request` 上触发、
          (b) 跑执行器（`tools/verify_acceptance_run.py`）、(c) 用棘轮收口
          （`tools/verify_acceptance_ratchet.py` —— failed=0 的硬门）。
          只断言「门函数对」而不断言「门真的在 PR 通道上跑」，
          与「常量定义了没人用」同形（AGENTS.md §2.4）。
  GS-GATE **规则文件变更的合并门**：`merge_allowed(changed_paths, receipt)` 纯函数 ——
          改规则库文件而无「跑过回归集且通过、指纹一致」的回执 → 拒；
          非规则文件变更 → 放行（反向对照，证明门不是一律拒绝）

## **本文件不证明什么**（结论行必须照抄）

* **CI 在跑 ≠ 远端真的挡住了合并。** GS-CI-ENFORCE 断言的是**本仓内的 CI 配置**
  （`.github/workflows/acceptance.yml`，2026-10-23 已入库）把执行器挂在了
  `pull_request` 通道上；「远端 main 的分支保护真的把这个 check 设成了必需」
  本机读不到（匿名 API `protected=false`；带凭据的详情 401，2026-10-22 实测）。
  配置层与远端强制层是两层，本文件只断言配置层。
* **不证明样本语义正确。** 83 条样本是人工编写的通用广告语
  （`provenance: public_synthetic`），它们的 `expected` 是**建集人的判断**，
  没有经过法务或产品签署。本文件只证明**结构性质**（规模/覆盖/指纹/变更记录），
  不证明「这 83 条真的代表业务分布」。
* **不证明规则变更前后读数一致**（那是行 87 的 `verify_rule_change_regression.py`）。

## 退出码

  0 全过 · 1 有红 · 2 未测（回归集或控制点主表读不出）

## 用法

    python3 tools/verify_regression_set.py
    python3 tools/verify_regression_set.py --controls
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGRESSION = ROOT / "research" / "governance" / "regression-set-v1.json"
CONTROL_POINTS = ROOT / "research" / "governance" / "control-points-v1.json"

# 行 85 逐字点名的四个字面量。**不要改这个列表** —— 它是行原文，不是可调参数。
TRAP_LITERALS = ("Best Seller", "100% cotton", "最新", "first-time mom")

# `expected.kind` 里哪些算「负样本（预期不误杀）」
NEGATIVE_KINDS = ("trap_negative", "correctly_exempted")

# 改这些文件必须带回归回执
RULE_FILES = (
    "research/governance/skeleton/rules-v1.json",
    "research/governance/skeleton/whitelist-v1.json",
    "research/governance/skeleton/context-guards-v1.json",
    "research/governance/skeleton/disposition-layers-v1.json",
    "research/governance/skeleton/product-lines-v1.json",
)

# GS-CI-ENFORCE：CI/分支保护通道的**本仓执行点**（2026-10-23 入库，T-145）。
# 行 85 第 ⑤ 条要的是「改规则但不跑回归集的 PR 合并被挡」——
# 那件事的配置层落在这个工作流文件里：PR 通道 + 执行器 + 棘轮硬门。
# ★ **必须逐字点名**，不许只数条目 —— 条目计数那种判据在重排/改名时恒真。
CI_WORKFLOW = ROOT / ".github" / "workflows" / "acceptance.yml"
CI_PR_CHANNEL = "pull_request:"
CI_EXECUTOR_MARKER = "tools/verify_acceptance_run.py"
CI_RATCHET_MARKER = "tools/verify_acceptance_ratchet.py"

# GS-RULES-FP：规则表与其版本留痕（engine_manifest.py 的产物）。
RULES_FILE = ROOT / "research" / "governance" / "skeleton" / "rules-v1.json"
ENGINE_MANIFEST = ROOT / "research" / "governance" / "skeleton" / "engine-manifest.json"

# GS-CHG-PIN：**冻结读数**（2026-10-24 用 `set_fingerprint()` 实算，83 条样本）。
# 复现：python3 -c "import json,sys; sys.path.insert(0,'tools');
#           from verify_regression_set import set_fingerprint;
#           r=json.load(open('research/governance/regression-set-v1.json'));
#           print(set_fingerprint(r['samples']))"
# ★ 与 `tools/acceptance-ratchet.json` 的 passed_floor 同一个模式：
#   今天的读数钉下来；动它 = 一次有记录的决定（changelog 新条目 + 本值同步更新，
#   同一提交）。改样本而三者缺一，GS-CHG-PIN 红。
FROZEN_SET_FINGERPRINT = (
    "538389f39bc4406dcf56f0a88430af8d3d97438a4c7b78270915c66cd665df2a")


def sample_fingerprint(text: str) -> str:
    """指纹口径：`sha256(json({"text": ...}, sort_keys, ensure_ascii=False))`。

    ★ 用 JSON 而不是裸 `sha256(text.encode())`：前者对字段增删有韧性
      （将来加 `locale` 字段不必重算全部指纹），后者会静默改变全部值。
      口径写在这里，验证器与生成器必须一致 —— 这就是它只许有一处的原因。
    """
    return hashlib.sha256(
        json.dumps({"text": text}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def set_fingerprint(samples) -> str:
    """冻结集整体指纹：`sha256(json(样本数组, sort_keys, ensure_ascii=False))`。

    口径：**全量逐字节等价**（整份样本对象列表，按 JSON 归一化）。
    任何字段变化 —— text、指纹、族、expected —— 都会改变这个值；
    而「重排数组顺序」不改变它（`sort_keys` 归一化的是键，不重排序数组 ——
    所以数组顺序本身也算内容的一部分）。这条口径存在的理由见 GS-CHG-PIN。
    """
    return hashlib.sha256(
        json.dumps(list(samples or []), ensure_ascii=False, sort_keys=True)
        .encode("utf-8")).hexdigest()


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def check_size(samples):
    """GS-SIZE：50–100（含端点）。"""
    n = len(samples)
    if n < 50:
        return ["条目数 %d < 50（太少，覆盖不到尾部）" % n]
    if n > 100:
        return ["条目数 %d > 100（太多，冻结集会失去「可全量重跑」的性质）" % n]
    return []


def check_traps(samples):
    """GS-TRAP：四个字面量各至少 1 条，且都标成负样本。"""
    problems = []
    for lit in TRAP_LITERALS:
        hits = [s for s in samples if lit in (s.get("text") or "")]
        if not hits:
            problems.append("缺陷阱字面量 %r —— 行 85 点名四个，缺一即红" % lit)
            continue
        marked = [s for s in hits
                  if (s.get("expected") or {}).get("kind") in NEGATIVE_KINDS]
        if not marked:
            problems.append("陷阱字面量 %r 有 %d 条样本，但没有一条标成负样本"
                            "（%s）—— 记成正样本等于承认「这个词该判违规」"
                            % (lit, len(hits), NEGATIVE_KINDS))
    return problems


def check_families(samples, control_points):
    """GS-FAMILY：有控制点的族 ≥3 条；空族 0 条。

    ★ 空族**运行时读** `control-points-v1.json` 的 `empty_families`，
      不写死「四族」或「三族」——
      验收表括注写「当前四族」，而盘上实测是 3 族（品牌控制已有 B01–B04）。
      把那个数字抄进断言，就会在本文件里复现同一个过期读数的病（§2.2 第 1 条）。

    ## ★ 口径歧义：这一票必须自己钉死，盘上没有裁定（2026-10-22 取证发现）

    「哪族算**有控制点**」有两种读法，结论不同：

    | 口径 | 宣称 | 事实 | 披露 | 品牌 | 结论 |
    |---|---:|---:|---:|---:|---|
    | **按行计数**（任何 status 都算） | 14 | 3 | 3 | 4 | 四族都 ≥3，绿 |
    | **按 active 计数**（只算 status=active） | 14 | 3 | **2** | **0** | 披露与品牌直接红 |

    差别来源：`U02` 是 `deprecated`，`B01–B04` 全是 `draft`
    （`activation_blocked_by: T10 用词规则误报率未实测`）。

    **本文件采用「按行计数」**，理由是三条，缺一条都不够：
      1. `empty_families` 本身就是按「有没有行」定义的（场景/权利/渠道各 0 行）；
      2. 现有断言 `verify_control_points.py` 的 **EF-1/EF-2** 与
         `verify_pass_reachability.py` 的 **U1** 都按同一个键计数、不看 status；
      3. 行 85 要的是「**回归集有没有覆盖这个族**」，不是「这个族今天有没有可执行规则」。
         后者是**另一件事**，由 B01–B04 的 draft 阻塞原因各自负责。

    ★ 但这意味着：**族覆盖变绿 ≠ 该族有可执行规则。** 品牌控制 4 个点全是 draft，
      回归集给它们各 3 条样本只是「样本齐了」，那 4 条规则**今天不会跑**。
      结论行必须说出这一点，否则「族覆盖成立」会被读成「品牌规则在测」。
    """
    problems = []
    by_family = {}
    for s in samples:
        by_family[s.get("family")] = by_family.get(s.get("family"), 0) + 1

    families = control_points.get("families") or []
    empty_names = {e.get("family") for e in (control_points.get("empty_families") or [])}
    active = [f for f in families if f not in empty_names]

    for fam in active:
        n = by_family.get(fam, 0)
        if n < 3:
            problems.append("有控制点的族 %r 只有 %d 条（要求 ≥3）" % (fam, n))
    for fam in empty_names:
        n = by_family.get(fam, 0)
        if n:
            problems.append("空族 %r 有 %d 条样本 —— 为凑数加入即红"
                            "（该族当前没有控制点，样本无从验证）" % (fam, n))
    unknown = set(by_family) - set(families)
    if unknown:
        problems.append("样本用了不存在的族名：%r（families 里没有）" % sorted(unknown))
    return problems


def check_consistency(control_points):
    """GS-CONSIST：`status_note` 声称的空族 与 `empty_families` 实际条目 不许矛盾。

    ★ 2026-10-22 实测发现：`status_note` 写
      「**空 4 族**（场景控制, 权利控制, 渠道控制, **品牌控制**）」，
      而同一文件的 `empty_families` 只有 **3** 族（品牌控制已有 B01–B04）。
      两个读数在同一个 JSON 里并存，**此前没有任何断言能发现**。
      行 85 原文明令「以 `empty_families` 为准」，所以这里把「status_note 与它矛盾」
      变成一条会红的断言 —— 否则读者永远不知道该信哪个。
    """
    problems = []
    note = str(control_points.get("status_note") or "")
    empty = [e.get("family") for e in (control_points.get("empty_families") or [])]
    m = re.search(r"空\s*(\d+)\s*族", note)
    if m:
        claimed = int(m.group(1))
        if claimed != len(empty):
            problems.append(
                "status_note 声称空 %d 族，但 empty_families 实际是 %d 族 %r —— "
                "同一份文件两个读数，读者不知道该信哪个（行 85 定的是以 "
                "empty_families 为准）" % (claimed, len(empty), empty))
    # 反向：status_note 里点名的族如果已经不在 empty_families 里，也要指出来
    for fam in empty:
        pass
    for fam in re.findall(r"[^\s（(,，]+控制", note):
        if fam in {e.get("family") for e in (control_points.get("empty_families") or [])}:
            continue
        if fam in (control_points.get("families") or []):
            problems.append(
                "status_note 把 %r 当成空族/待签，但它已有控制点 —— 括注过期" % fam)
    return problems


def check_fingerprints(samples):
    """GS-FP：每条指纹可复算且相等；每条都有指纹字段。"""
    problems = []
    for s in samples:
        sid = s.get("id", "?")
        fp = s.get("fingerprint") or {}
        algo = fp.get("algorithm")
        val = fp.get("value")
        if algo != "sha256" or not isinstance(val, str) or len(val) != 64:
            problems.append("%s 指纹字段不合法（algorithm=%r len=%r）"
                            % (sid, algo, len(val) if isinstance(val, str) else None))
            continue
        want = sample_fingerprint(s.get("text") or "")
        if want != val:
            problems.append("%s 指纹对不上：记录 %s… 实算 %s…（改过 text 却没更新指纹）"
                            % (sid, val[:12], want[:12]))
    return problems


def check_changelog(changelog):
    """GS-CHANGE：每条变更记录必须有 operator / at / reason。"""
    problems = []
    if not isinstance(changelog, list) or not changelog:
        return ["changelog 必须是非空数组（否则「谁改的、为什么改」无从追溯）"]
    for i, e in enumerate(changelog):
        if not isinstance(e, dict):
            problems.append("changelog[%d] 不是对象" % i)
            continue
        for k in ("operator", "at", "reason"):
            v = e.get(k)
            if not isinstance(v, str) or not v.strip():
                problems.append("changelog[%d] 缺 %s（三项缺一即红）" % (i, k))
    return problems


def merge_allowed(changed_paths, receipt):
    """GS-GATE：规则文件变更必须带「跑过回归集且通过、指纹一致」的回执。

    ★ 这是**纯函数**，不读盘、不看 git —— 所以它能被 `--controls` 直接喂样本。
      真正的「远端拦住了没有」要 CI + 分支保护，本仓今天两者都没有（见文件头）。

    返回 (allowed: bool, why: str)。
    """
    changed = [str(p) for p in (changed_paths or [])]
    rule_hits = [p for p in changed if p in RULE_FILES]
    if not rule_hits:
        return True, "没有规则文件变更 —— 不要求回归回执"
    if not isinstance(receipt, dict):
        return False, "改了规则文件 %r 却没有回归回执" % rule_hits
    if receipt.get("status") != "pass":
        return False, "回归报告 status=%r 不是 pass" % receipt.get("status")
    if not receipt.get("set_fingerprint"):
        return False, "回归回执缺 set_fingerprint —— 无法证明跑的是不是当前这版集合"
    if receipt.get("rule_snapshot") and receipt.get("rule_snapshot") != receipt.get(
            "current_rule_snapshot"):
        return False, "回执是对旧规则快照跑的（%r ≠ 当前 %r）" % (
            receipt.get("rule_snapshot"), receipt.get("current_rule_snapshot"))
    return True, "规则变更带了通过的回执"


def check_change_pin(samples, changelog):
    """GS-CHG-PIN：改样本必须留下变更痕迹（2026-10-23 补，见本文件头部）。

    抓的是哪种：改了一条样本的 text、把 `fingerprint` 同步重算
    （GS-FP 因此全绿），且 changelog 是历史列表没人回头看样本
    （GS-CHANGE 因此全绿）→ 在两条旧断言上都无感。

    判据两半：

      ① **冻结指纹**：`samples` 的实算整体指纹必须等于 FROZEN_SET_FINGERPRINT ——
        写进本文件的**冻结读数**（与 `tools/acceptance-ratchet.json` 的地板同一个模式：
        今天的读数钉下来，动它必须是一次有记录的决定）。
        「冻结回归集」的「冻结」二字落点就在这里：没有这一条，冻结只是文件名。
        ★ 合法变更的程序：改样本 → changelog 加一条（operator/at/reason/after_fingerprint）
          → 重算 → **同一提交**里更新 FROZEN_SET_FINGERPRINT。少任何一步，本条红。
      ② **记账纪律**：`after_fingerprint` 为空只许出现在 changelog 的**第一条**
        （初始建集时还没有「上一版」可对账）；此后每条都必须带；且**最新一条**若带了，
        必须等于当前实算指纹（记了账就得记对）。历史条目的值不复算 ——
        历史样本状态已不在盘上，硬算就是编造。

    ★ ②单独不够：变异「改样本 + 不加 changelog 条目」在 ② 上无感
      （changelog 原样不动）—— 抓它的只能是 ①。两半缺一不可。
    """
    problems = []
    current = set_fingerprint(samples)
    if current != FROZEN_SET_FINGERPRINT:
        problems.append(
            "冻结集指纹对不上：冻结读数 %s… 实算 %s… —— 回归集已不是上次冻结的那一份。"
            "若是合法变更：changelog 补条目（operator/at/reason/after_fingerprint）"
            "并同一提交更新 verify_regression_set.py 的 FROZEN_SET_FINGERPRINT"
            % (FROZEN_SET_FINGERPRINT[:12], current[:12]))
    if not changelog:
        problems.append("changelog 为空 —— 样本从哪来、谁建的，无从对账")
    else:
        for i, e in enumerate(changelog):
            if not isinstance(e, dict):
                continue
            if e.get("after_fingerprint") is None and i > 0:
                problems.append(
                    "changelog[%d] 缺 after_fingerprint —— 初始建集条目（第 1 条）之外"
                    "不许空：变更之后「改成了哪一版」必须指得出" % i)
        last = changelog[-1]
        if isinstance(last, dict) and last.get("after_fingerprint") is not None \
                and last["after_fingerprint"] != current:
            problems.append(
                "changelog 最新条目 after_fingerprint=%s… ≠ 当前实算冻结集指纹 %s… —— "
                "账记了，但记的不是现在这一版"
                % (str(last["after_fingerprint"])[:12], current[:12]))
    return problems


def check_rules_fp(rules_bytes=None, manifest=None):
    """GS-RULES-FP：规则表与引擎清单对账 —— 「改规则必须留痕」的盘上执行点。

    抓的是哪种：直接编辑 `rules-v1.json` 而不跑 `engine_manifest.py --write`
    —— 门函数 `merge_allowed` 是纯函数（无感）、CI 断言只看工作流文本（无感）、
    GS-FP 只管回归集样本（无感）。从本条起：**规则表的字节与 manifest 记录的
    sha256/bytes 不一致 → 红**。

    manifest 是本仓**唯一**的规则版本留痕（`engine_manifest.py` 的存在理由），
    `judge.py` 的 `versions()` 从它派生 rule_version —— manifest 一过期，
    所有判定回执都答不了「这是哪版规则算的」。合法变更程序：改规则 →
    `engine_manifest.py --write` → 本条转绿。

    `rules_bytes` / `manifest` 可注入（`--controls` 反向对照用，不写真文件，§2.4.4）。
    """
    problems = []
    if rules_bytes is None:
        if not RULES_FILE.exists():
            return ["未测前提：规则表文件不存在 %s" % RULES_FILE]
        rules_bytes = RULES_FILE.read_bytes()
    if manifest is None:
        if not ENGINE_MANIFEST.exists():
            return ["没有引擎清单 %s —— 规则表没有任何版本留痕，"
                    "「改规则必须留痕」无从谈起" % ENGINE_MANIFEST.relative_to(ROOT)]
        try:
            manifest = json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8"))
        except ValueError as exc:
            return ["引擎清单解析失败：%s —— 未测" % exc]
    art = (manifest.get("artifacts") or {}).get("rules") or {}
    rec_sha, rec_bytes = art.get("sha256"), art.get("bytes")
    if not rec_sha:
        return ["引擎清单里没有 rules 制度的 sha256 —— 规则表不在版本留痕内"]
    cur_sha = hashlib.sha256(rules_bytes).hexdigest()
    if cur_sha != rec_sha or len(rules_bytes) != rec_bytes:
        problems.append(
            "规则表与引擎清单对不上：manifest 记录 sha256=%s… bytes=%s，"
            "盘上实算 sha256=%s… bytes=%d —— 改了规则没重算 manifest"
            "（合法程序：python3 engine_manifest.py --write）"
            % (str(rec_sha)[:12], rec_bytes, cur_sha[:12], len(rules_bytes)))
    return problems


def check_ci_enforce(text=None):
    """GS-CI-ENFORCE：改规则必须先跑回归集 —— CI 通道的配置层断言（2026-10-23 补）。

    抓的是哪种：把 `.github/workflows/acceptance.yml` 的 `pull_request` 触发删掉、
    或把执行器/棘轮两步换掉 —— 门函数 `merge_allowed` 是纯函数，照旧全绿；
    从本条起这三种删法各自当场红。行 85 第 ⑤ 条「改规则但不跑回归集的 PR
    合并被挡住」的**配置层执行点**就是这三个标记。

    ★ 逐字点名，不数条目：条目计数那种判据在标记重排/改名时恒真（§2.4）。
    `text` 可注入 —— `--controls` 的反向对照喂打掉的配置文本，
    **不写真文件**（§2.4.4：自证不许有副作用）。
    """
    problems = []
    if text is None:
        if not CI_WORKFLOW.exists():
            return ["没有 CI 工作流文件 %s —— 改规则而不跑回归集的 PR 在配置层无人拦"
                    % CI_WORKFLOW.relative_to(ROOT)]
        text = CI_WORKFLOW.read_text(encoding="utf-8")
    if CI_PR_CHANNEL not in text:
        problems.append("CI 工作流没有 %s 触发 —— 改规则的 PR 不会跑回归集（只有 push/dispatch 时等于没门）"
                        % CI_PR_CHANNEL.rstrip(":"))
    if CI_EXECUTOR_MARKER not in text:
        problems.append("CI 工作流没有跑执行器（%s）—— 「改规则必须先跑验收」没有执行点"
                        % CI_EXECUTOR_MARKER)
    if CI_RATCHET_MARKER not in text:
        problems.append("CI 工作流没有棘轮门（%s）—— 回归集倒退不会挡住合并（failed=0 那条硬判据没人执行）"
                        % CI_RATCHET_MARKER)
    return problems


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 85 / SEC-6-GS-* · 冻结回归集")
    print("=" * 72)

    if not REGRESSION.exists() or not CONTROL_POINTS.exists():
        print("  ⚠ 读不到回归集或控制点主表 —— 未测，不是通过")
        return 2
    try:
        reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
        cp = json.loads(CONTROL_POINTS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("  ⚠ 解析失败：%s —— 未测" % exc)
        return 2

    samples = reg.get("samples") or []
    check("GS-0", bool(samples),
          "回归集可解析，%d 条样本，set_version=%r" % (len(samples), reg.get("set_version"))
          if samples else "samples 为空")

    size = check_size(samples)
    check("GS-SIZE", not size, "条目数 %d 在 50–100 内（含端点）" % len(samples)
          if not size else str(size))

    traps = check_traps(samples)
    check("GS-TRAP", not traps,
          "四个陷阱字面量都在，且都标成负样本（预期不误杀）"
          if not traps else str(traps[:2]))

    fams = check_families(samples, cp)
    n_active = len([f for f in (cp.get("families") or [])
                    if f not in {e.get("family") for e in (cp.get("empty_families") or [])}])
    n_empty = len(cp.get("empty_families") or [])
    check("GS-FAMILY", not fams,
          "族覆盖成立：%d 个有控制点族各 ≥3 条（**按行计数**，draft/deprecated 都算），"
          "%d 个空族各 0 条（运行时读主表）；★ 族覆盖 ≠ 该族规则在测"
          % (n_active, n_empty) if not fams else str(fams[:2]))

    cons = check_consistency(cp)
    check("GS-CONSIST", not cons,
          "控制点主表自洽：status_note 与 empty_families 不矛盾"
          if not cons else str(cons[:2]))

    fps = check_fingerprints(samples)
    check("GS-FP", not fps, "%d 条样本指纹全部可复算且相等" % len(samples)
          if not fps else "%d 条有问题：%s" % (len(fps), fps[:2]))

    chg = check_changelog(reg.get("changelog"))
    check("GS-CHANGE", not chg, "changelog 每条都有 operator / at / reason"
          if not chg else str(chg[:2]))

    pin = check_change_pin(samples, reg.get("changelog") or [])
    check("GS-CHG-PIN", not pin,
          "冻结集指纹 = FROZEN_SET_FINGERPRINT；changelog 记账纪律成立"
          if not pin else str(pin[:2]))

    rfp = check_rules_fp()
    check("GS-RULES-FP", not rfp,
          "规则表字节与 engine-manifest.json 的 sha256/bytes 一致（改规则必须重算 manifest）"
          if not rfp else str(rfp[:2]))

    ci = check_ci_enforce()
    check("GS-CI-ENFORCE", not ci,
          "CI 工作流把执行器与棘轮挂在 pull_request 通道上（配置层）"
          if not ci else str(ci[:2]))

    # GS-GATE：证明门不是一律拒绝，也不是一律放行
    #   ★ 2026-10-22 修一处我自己的错：`merge_allowed` 返回 (allowed, why)，
    #     第一版把 `allowed` 直接当成「被拒绝了」用（变量名写成 deny_rule），
    #     于是「无回执必须拒」在 allowed=False 时被判成 False → 门显示有偏。
    #     名字与语义错位是这一票第 3 次同形（前两次：签名凭印象、漏剥注释）。
    allow_none, _ = merge_allowed(["README.md"], None)
    denied_without_receipt, _ = merge_allowed([RULE_FILES[0]], None)   # True = 被放行
    denied_bad_status, _ = merge_allowed([RULE_FILES[0]],
                                         {"status": "fail", "set_fingerprint": "x"})
    allow_ok, _ = merge_allowed([RULE_FILES[0]], {
        "status": "pass", "set_fingerprint": "x" * 64})
    gate_ok = (allow_none
               and not denied_without_receipt
               and not denied_bad_status
               and allow_ok)
    check("GS-GATE", gate_ok,
          "合并门成对成立：非规则变更放行 / 规则变更无回执拒绝 / "
          "回执 status≠pass 拒绝 / 规则变更带回执放行"
          if gate_ok else
          "门有偏：非规则放行=%s 无回执被拒=%s 坏回执被拒=%s 好回执放行=%s"
          % (allow_none, not denied_without_receipt,
             not denied_bad_status, allow_ok))

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        return 1
    print("  ✅ 全过 —— 只证明：集合规模/陷阱覆盖/族覆盖/指纹/变更记录/"
          "变更对账（冻结指纹）/规则表-清单对账/CI 配置层/合并门判定函数成立。")
    print("     ★ CI 在跑 ≠ 远端真的挡住了合并：分支保护的本机读数 401，")
    print("       「必需检查」那半无法从这台机器证明（2026-10-22 实测 protected=false）。")
    print("     ★ **不证明**样本语义正确（83 条为人工编写的通用广告语，未经法务签署）。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def check_gate(cases, *, expect_allowed):
    """把 `merge_allowed` 的 (allowed, why) 折算成「问题列表」形态。

    ★ 为什么要这层薄封装：`--controls` 里所有 `check_*` 的约定都是
      「返回问题列表，空 = 绿」。而 `merge_allowed` 返回的是 (bool, str) ——
      第一版我在 lambda 里直接用 `[]` / `["拒绝"]` 手搓，`[]` 是假值，
      于是三条预判红的用例全部被读成绿。**约定不同就别硬套**，
      写一层显式转换，让「红 = 非空列表」在任何一条上只成立一次。
    """
    problems = []
    for changed, receipt in cases:
        allowed, why = merge_allowed(changed, receipt)
        if allowed != expect_allowed:
            problems.append(
                "changed=%r receipt=%r → allowed=%s（期望 %s）：%s"
                % (changed, "有" if receipt else "无", allowed,
                   expect_allowed, why))
    return problems


def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出。**"""
    if not REGRESSION.exists() or not CONTROL_POINTS.exists():
        print("  ⚠ 真源缺失 —— 未测")
        return 2
    reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    cp = json.loads(CONTROL_POINTS.read_text(encoding="utf-8"))
    samples = reg.get("samples") or []
    changelog = reg.get("changelog") or []

    def with_n(n):
        return samples[:n]

    d = lambda o: copy.deepcopy(o)  # noqa: E731
    s0 = d(samples[0])

    def after_change():
        """好样本②的形状：走完合法变更程序之后（冻结读数已同步更新）。"""
        new_text = s0["text"] + " v2"
        new_fp = hashlib.sha256(json.dumps(
            {"text": new_text}, ensure_ascii=False,
            sort_keys=True).encode("utf-8")).hexdigest()
        new_samples = [dict(s0, text=new_text,
                            fingerprint={"algorithm": "sha256",
                                         "value": new_fp})] + d(samples)[1:]
        new_pin = set_fingerprint(new_samples)
        saved = FROZEN_SET_FINGERPRINT
        globals()["FROZEN_SET_FINGERPRINT"] = new_pin
        try:
            return check_change_pin(new_samples, changelog + [dict(
                changelog[-1], at="2026-10-24T00:00:00Z",
                after_fingerprint=new_pin)])
        finally:
            globals()["FROZEN_SET_FINGERPRINT"] = saved

    # GS-CI-ENFORCE 反向用例的最小合法配置。★ 放在 cases **之外** ——
    # 写在列表字面量里时，赋值行本身让整个列表在它前面就断成两截
    # （SyntaxError）；就算侥幸不断，紧跟其后的元组也会被吃成
    # 无害表达式语句，用例静默消失。同形错法见 GS-GATE 的注释。
    ci_ok = ("on:\n  pull_request:\n    branches: [main]\n"
             "jobs:\n  acceptance:\n    steps:\n"
             "      - run: .venv/bin/python " + CI_EXECUTOR_MARKER + "\n"
             "      - run: cat acceptance-run.txt | "
             ".venv/bin/python " + CI_RATCHET_MARKER + "\n")

    cases = [
        ("好样本：真实回归集规模", False, lambda: check_size(samples)),
        ("坏样本：49 条", True, lambda: check_size(with_n(49))),
        ("坏样本：101 条（复制补满）",
         True, lambda: check_size(samples + d(samples)[:18])),

        ("好样本：真实陷阱样本", False, lambda: check_traps(samples)),
        ("坏样本：删掉一个陷阱字面量",
         True, lambda: check_traps([s for s in samples if "Best Seller" not in s["text"]])),
        ("坏样本：陷阱样本标成正样本",
         True, lambda: check_traps([
             dict(s, expected={"kind": "should_hit"}) if "Best Seller" in s["text"] else s
             for s in samples])),

        ("好样本：真实族覆盖", False, lambda: check_families(samples, cp)),
        ("坏样本：把某有控制点族抽到只剩 2 条",
         True, lambda: check_families(
             [s for s in samples if s["family"] != "品牌控制"]
             + [s for s in samples if s["family"] == "品牌控制"][:2], cp)),
        ("坏样本：往空族塞 1 条",
         True, lambda: check_families(
             samples + [dict(samples[0], family="场景控制")], cp)),
        ("坏样本：样本用了不存在的族名",
         True, lambda: check_families(
             samples + [dict(samples[0], family="不存在的族")], cp)),

        # ★ 2026-10-22 第二次修正（同一晚）：这一条先写「真实主表带病 → 必须红」，
        #   因为当时 `control-points-v1.json:10` 的 status_note 确实写着「空 4 族」。
        #   随后我把那句改正成「空 3 族」，于是它**转绿** —— 这不是断言坏了，
        #   是**盘上的事实变了**：预判跟着事实走，而不是反过来。
        #   ★ 这条用例的价值就在这里：它同时证明了
        #     ①断言会红（在带病样本上，见下一条）、②断言会绿（在修好之后）。
        #     只有红没有绿的是「恒红」，只有绿没有红的是「恒绿」——两者都骗人。
        ("好样本：真实控制点主表（status_note 已与 empty_families 一致）",
         False, lambda: check_consistency(cp)),
        ("坏样本：status_note 声称空 4 族而实际 3 族",
         True, lambda: check_consistency(dict(
             cp, status_note="结构已闭合；空 4 族（场景控制, 权利控制, 渠道控制, 品牌控制）"))),
        ("好样本：status_note 与 empty_families 一致",
         False, lambda: check_consistency(dict(
             cp, status_note="结构已闭合；空 3 族（场景控制, 权利控制, 渠道控制）"))),

        ("好样本：真实指纹", False, lambda: check_fingerprints(samples)),
        ("坏样本：改 text 不改指纹",
         True, lambda: check_fingerprints(
             [dict(samples[0], text=samples[0]["text"] + " plus")] + samples[1:])),
        ("坏样本：指纹字段缺失",
         True, lambda: check_fingerprints([{k: v for k, v in samples[0].items()
                                            if k != "fingerprint"}])),

        ("好样本：真实 changelog", False, lambda: check_changelog(changelog)),
        ("坏样本：changelog 缺 reason",
         True, lambda: check_changelog([{"operator": "x", "at": "2026-10-22"}])),
        ("坏样本：changelog 为空", True, lambda: check_changelog([])),

        # GS-CHG-PIN 的成对反向对照。坏样本只喂 deepcopy —— 决不写真源（§2.4.4）。
        # 坏样本的形状就是审计里 survived 的那个变异：改 text、把样本自身
        # fingerprint 同步重算（GS-FP 全绿），冻结读数与 changelog 都不动。
        # 好样本②「合法变更后的形状」也一并喂（`after_change`，cases 之外）：
        # 走完程序（changelog 补条目 + 冻结读数同步更新）必须转绿 ——
        # 只有红没有绿的判据会误伤合法变更。
        ("好样本：真实冻结集（= FROZEN_SET_FINGERPRINT）",
         False, lambda: check_change_pin(samples, changelog)),
        ("好样本：合法变更后的形状（读数已同步，见函数体）",
         False, after_change),
        ("坏样本：改 text 且指纹同步、冻结读数没跟",
         True, lambda: check_change_pin(
             [dict(s0, text=s0["text"] + " v2",
                   fingerprint={"algorithm": "sha256",
                                "value": "b" * 64})] + d(samples)[1:],
             changelog)),
        ("坏样本：非首条 changelog 缺 after_fingerprint",
         True, lambda: check_change_pin(samples, changelog + [
             {"operator": "x", "at": "2026-10-24", "reason": "改 GS-001"}])),
        ("坏样本：最新条目 after_fingerprint ≠ 当前实算",
         True, lambda: check_change_pin(
             samples, changelog + [dict(changelog[-1],
                                        after_fingerprint="a" * 64,
                                        at="2026-10-24")])),

        # GS-RULES-FP 的成对反向对照。全部走注入（不写 rules-v1.json / manifest，§2.4.4）。
        ("好样本：真实规则表 × 真实 manifest（字节一致）",
         False, lambda: check_rules_fp()),
        ("坏样本：规则表改一个字节、manifest 没重算",
         True, lambda: check_rules_fp(
             rules_bytes=RULES_FILE.read_bytes() + b" ",
             manifest=json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8")))),
        ("坏样本：manifest 记录值指向别的版本",
         True, lambda: check_rules_fp(
             rules_bytes=RULES_FILE.read_bytes(),
             manifest={"artifacts": {"rules": {
                 "sha256": "a" * 64, "bytes": RULES_FILE.stat().st_size}}})),
        ("坏样本：manifest 里没有 rules 制度",
         True, lambda: check_rules_fp(
             rules_bytes=RULES_FILE.read_bytes(), manifest={"artifacts": {}})),

        # GS-CI-ENFORCE 的成对反向对照。配置文本读进内存再打掉，
        # 决不写 CI_WORKFLOW（§2.4.4：自证不许有副作用）。
        # 反向用例自备最小合法配置（`ci_ok`，cases 之外）：它们要证的是
        # 「判据对这种形状会红」，真文件在不在盘上都不影响这一证明。
        ("好样本：CI 配置三标记齐全", False, lambda: check_ci_enforce(ci_ok)),
        ("坏样本：CI 没有 pull_request 触发",
         True, lambda: check_ci_enforce(ci_ok.replace(CI_PR_CHANNEL, "push:"))),
        ("坏样本：CI 不跑执行器",
         True, lambda: check_ci_enforce(
             ci_ok.replace(".venv/bin/python " + CI_EXECUTOR_MARKER, "echo skipped"))),
        ("坏样本：CI 不跑棘轮",
         True, lambda: check_ci_enforce(
             ci_ok.replace(".venv/bin/python " + CI_RATCHET_MARKER, "echo skipped"))),
        ("坏样本：CI 配置为空（等价于文件缺失）",
         True, lambda: check_ci_enforce("")),

        # ★ 2026-10-22 修三处我自己的错：`check_*` 的约定是「返回问题列表，空 = 绿」。
        #   第一版我把 `[]` 当成「红」写在这三个 lambda 里，而 `[]` 是**假值** ——
        #   于是 `bool([])` → False → 被读成绿，预判红的那三条全部实测绿。
        #   正确写法是让 lambda 返回**非空列表**表示红。
        #   ★ 这已经是同一票里第 4 次「名字/语义错位」：签名凭印象、漏剥注释、
        #     `allowed` 当 `denied`、`[]` 当红。共同形状：**我写的符号不等于我以为的意思。**
        ("好样本：非规则变更放行",
         False, lambda: check_gate([("README.md", None)], expect_allowed=True)),
        ("坏样本：改规则无回执必须拒",
         True, lambda: check_gate([(RULE_FILES[0], None)], expect_allowed=False)),
        ("坏样本：回执 status != pass 必须拒",
         True, lambda: check_gate(
             [(RULE_FILES[0], {"status": "fail", "set_fingerprint": "x"})],
             expect_allowed=False)),
        ("好样本：规则变更 + 通过回执放行",
         False, lambda: check_gate(
             [(RULE_FILES[0], {"status": "pass", "set_fingerprint": "x"})],
             expect_allowed=True)),
    ]

    print("=" * 72)
    print("verify_regression_set · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-48s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 66)
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
        print("  %-48s %-6s %-6s %s%s"
              % (name[:48],
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
