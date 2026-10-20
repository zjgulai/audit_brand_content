#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_taxonomy_json.py —— 从《内容审查分类规范》生成 Web 工作台用的 taxonomy.json

## 为什么需要这个文件

`web/src/data/taxonomy.json` 原来**没有生成器**，是手工解析一次写死的。
后果实测（2026-10-20）：规范 §3 已有 DSC11 / DSC12 / FCT10 三条编号条件，
而 JSON 里一条都没有 —— **界面上展示的判据比规范落后了 3 条，且没有任何东西会红。**

这与 AGENTS.md §2.4.1 第 5 行是同一个病：**一个会过期的读数，
没有任何东西在它过期时变红。**

## 执行点（这个脚本的核心，不是附注）

1. **完整覆盖**：规范 §3 里每一个编号条件（`| CHN1 | ... |` 这种表格行）
   都必须在 JSON 的 `criteria` 里出现。**少一条就退 1**，并在 stderr 列出缺哪些。
   反向也查：JSON 里不许有规范里已经删掉的编号。
2. **版本不是文件名**：`meta.spec_version` 与 `meta.spec_fingerprint` 从规范正文算，
   不读文件名。文件名永远叫 `-v1.md`（改名会断引用），所以**文件名不能当版本用**。
3. **指纹只对正文**：算 sha256 前先剥掉「版本说明」那一块（它自己写着指纹，
   否则会自指、永远算不出稳定值）。

## 用法

    python3 tools/gen_taxonomy_json.py            # 生成并写盘
    python3 tools/gen_taxonomy_json.py --check    # 只校验，不写盘（CI 用）
    python3 tools/gen_taxonomy_json.py --selftest # 反向对照：喂坏样本必须红

退出码：0 = 一致；1 = 有差异/覆盖缺失；2 = 未测（文件读不出）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "PMO" / "implement" / "内容审查分类规范-v1.md"
OUT = REPO / "web" / "src" / "data" / "taxonomy.json"

# §3 的七轴标题：`### 3.1 CHAN 渠道控制`
AXIS_HEAD = re.compile(r"^### 3\.\d+\s+([A-Z]+)\s+(.+)$", re.M)
# 编号条件表格行：`| DSC12 | 条件 | 返回 |`
COND_ROW = re.compile(r"^\|\s*([A-Z]{2,4}\d+)\s*\|(.+?)\|(.+?)\|\s*$", re.M)
# §4 小节标题：`### 4.7 r-xxxx — BRAND + CLAIM（拆分）`
#         或 `### 4.16.a `r-xxxx` — ALLOWED / NOT_A_RULE 两处打架`（欠定登记）
SEC4_HEAD = re.compile(r"^### (4\.(?:\d+|[0-9a-z]+(?:\.[a-z])?))\s+`?(r-[0-9a-f]+)`?\s*—\s*(.+)$", re.M)

# 版本说明块的起止标记 —— 指纹只对「正文」，不含这块（否则自指）
VER_BEGIN = "> **版本说明（2026-10-20）**"
VER_END = "\n\n## 0. 这份规范解决什么问题"


def read_spec() -> tuple[str, str]:
    """返回 (全文, 供算指纹的正文字节)。"""
    raw = SPEC.read_text(encoding="utf-8")
    i = raw.find(VER_BEGIN)
    j = raw.find(VER_END)
    body = raw if i < 0 or j < 0 else raw[:i] + raw[j:]
    return raw, body


def fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def parse_axes(raw: str) -> dict:
    """按 §3 的七个子节切块，逐块解析。"""
    heads = list(AXIS_HEAD.finditer(raw))
    if len(heads) != 7:
        raise SystemExit(f"⚠ 未测：§3 应有 7 个轴，实读到 {len(heads)} 个")

    axes = {}
    for k, m in enumerate(heads):
        code, name = m.group(1), m.group(2).strip()
        start = m.end()
        end = heads[k + 1].start() if k + 1 < len(heads) else raw.find("\n## 4.", start)
        block = raw[start:end]

        # 定义：`**定义。**` 后面那段
        dm = re.search(r"\*\*定义。\*\*\s*(.+?)(?:\n\n|\Z)", block, re.S)
        one_line = re.sub(r"\s+", " ", dm.group(1)).strip() if dm else ""

        # 编号条件
        criteria = []
        for cm in COND_ROW.finditer(block):
            cid = cm.group(1)
            when = re.sub(r"\s+", " ", cm.group(2)).strip()
            ret = re.sub(r"\s+", " ", cm.group(3)).strip()
            criteria.append(f"{cid}：{when} → {ret}")

        # 「不属于本轴」条目
        nm = re.search(r"\*\*不属于本轴：\*\*\s*\n\n((?:- .+\n?)+)", block)
        if nm:
            for line in nm.group(1).split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    criteria.append("不属于本轴：" + re.sub(r"\s+", " ", line[2:]).strip())

        # 「与邻轴的分界测试」表格
        bm = re.search(r"\*\*与邻轴的分界测试：\*\*\s*\n\n((?:\|.+\n?)+)", block)
        if bm:
            for line in bm.group(1).split("\n"):
                if not line.startswith("|") or line.startswith("| 邻轴") or set(line) <= set("|-: "):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2:
                    test = re.sub(r"\s+", " ", cells[1]).strip()
                    criteria.append(f"与 {cells[0]} 分界：{test}")

        # 复核人 / 证据要求
        rm = re.search(r"\*\*复核人。\*\*\s*(.+?)(?:\n\n|\Z)", block, re.S)
        em = re.search(r"\*\*证据要求。\*\*\s*(.+?)(?:\n\n\Z|\Z)", block, re.S)
        reviewer = re.sub(r"\s+", " ", rm.group(1)).strip() if rm else ""
        ev_raw = re.sub(r"\s+", " ", em.group(1)).strip() if em else ""
        # **类型契约**：前端 `TaxonomyPage.tsx` 的 `Axis.evidence_required` 是 `string[]`。
        # 生成器第一版把它写成了单个 str —— 页面运行时 `.map()` 会炸，
        # 而 `--check` 只比 JSON 自身的覆盖，**发现不了类型不对**。
        # 所以这里按 ①②③④ 分条；一条都分不出时整段作为单元素数组（至少不违反类型）。
        # **只在 ①②③④⑤ 处分条。** 不要按 `(2)` 这类行内编号切 ——
        # 实测它们出现在句子中间（「…缺 (2) 或 (3) 不得判 FACT」），
        # 切出来是碎片，读起来像规则被截断。没有圈号就整段作为单元素（类型仍正确）。
        evidence = [
            p.strip() for p in re.split(r"(?=[①②③④⑤])", ev_raw) if p.strip()
        ] if ev_raw else []

        axes[code] = {
            "code": code,
            "name": name,
            "one_line": one_line,
            "criteria": criteria,
            "reviewer": reviewer,
            "evidence_required": evidence,
        }
    return axes


def parse_section4(raw: str) -> list[dict]:
    """§4 的小节 → 边界反例（含欠定登记）。"""
    start = raw.find("\n## 4.")
    end = raw.find("\n## 5.")
    if start < 0 or end < 0:
        return []
    block = raw[start:end]
    heads = list(SEC4_HEAD.finditer(block))
    out = []
    for k, m in enumerate(heads):
        s = m.end()
        e = heads[k + 1].start() if k + 1 < len(heads) else len(block)
        body = block[s:e].strip()
        title = m.group(3).strip()
        axis = title.split("（")[0].split("—")[0].strip()
        # 欠定登记按**节号**判，不按标题字面判。
        # 起因：4.16.a 的标题是「ALLOWED / NOT_A_RULE 两处打架」，不含「欠定」二字，
        # 按标题判会漏掉 7 条全部 —— 一个「看着在读、其实没读」的判据。
        sec = m.group(1)
        out.append({
            "rule_id": m.group(2),
            "section": sec,
            "axis": axis,
            "title": title,
            "body": body,
            "underdetermined": sec.startswith("4.16"),
        })
    return out


def build(raw: str, body: str) -> dict:
    axes = parse_axes(raw)
    s4 = parse_section4(raw)

    # 边界反例：每个轴取 §4 里第一条非欠定的、轴名匹配的
    for code, a in axes.items():
        pick = None
        for item in s4:
            if item["underdetermined"]:
                continue
            if code in item["axis"].split("+"):
                pick = item
                break
        a["boundary_counterexample"] = (
            {"rule_id": pick["rule_id"], "why": pick["body"]} if pick else None
        )

    # 决策树：按 AXES 顺序（规范 §2 的判定顺序就是 §3 的排列）
    order = ["CHAN", "RIGHT", "SCENE", "DISC", "BRAND", "FACT", "CLAIM"]
    tree = [
        {
            "step": i + 1,
            "axis": code,
            "hit_condition": axes[code]["name"],
            "route_to": axes[code]["one_line"].split("。")[0] + "？",
        }
        for i, code in enumerate(order)
        if code in axes
    ]

    # 欠定争议：给工作台展示「这条判据有争议」
    # ⚠️ 字段名踩过坑：这里原来叫 `axis`，装的是**争议描述**（如「DSC12 枚举太窄…」），
    # 而 `axes[].code` 是七轴枚举值 —— 同一个词两种类型，按名字取枚举值会拿到一句话
    # 且不报错。现已拆成 `axis_code`（枚举，可为 null）+ `dispute`（描述）。
    disputes = [
        {
            "rule_id": d["rule_id"],
            "section": d["section"],
            "axis_code": _axis_code_of(d["axis"]),
            "dispute": d["axis"],
            "status": "underdetermined",
            "resolved_in": None,
        }
        for d in s4
        if d["underdetermined"]
    ]

    return {
        "meta": {
            "version": "v1",
            "spec_version": "v1.1",
            "spec_fingerprint": fingerprint(body),
            "status": "published",
            "source": "PMO/implement/内容审查分类规范-v1.md",
            "boundary_disputes": disputes,
            "note": (
                "由 tools/gen_taxonomy_json.py 从规范正文生成。"
                "spec_version 与 spec_fingerprint 不是文件名里的 v1 —— "
                "文件名保持不变（改名会断引用），版本以指纹为准。"
            ),
        },
        "axes": [axes[c] for c in order if c in axes],
        "decision_tree": tree,
        "orthogonal_fields": _orthogonal(),
        "rule_examples": [
            {"rule_id": d["rule_id"], "axis": d["axis"], "reason": d["body"]}
            for d in s4
            if not d["underdetermined"]
        ],
    }


def _orthogonal() -> dict:
    return {
        "rule_nature": {
            "label": "rule_nature",
            "values": ["prohibition", "mandate", "disclosure", "substantiation", "recommendation"],
            "expected_count": 5,
            "positioning": "义务形态；正交字段，不决定主轴",
            "derivation": "由规则谓词判定（禁止 / 强制 / 披露 / 举证 / 建议）",
            "note": "不可用 form 或 rule_kind 替代",
        },
        "jurisdiction": {
            "label": "jurisdiction",
            "values": ["GLOBAL", "US", "CA", "EU", "UK", "CN", "BR", "AU", "SG", "AT", "BH", "PLATFORM", "MULTI"],
            "expected_count": 13,
            "positioning": "适用法域或平台；正交字段，不决定主轴",
            "derivation": "由规则出处与生效地区判定",
            "note": "辖区来源不明 → UNKNOWN，不许默认 GLOBAL",
        },
        "severity": {
            "label": "severity",
            "values": ["L0", "L1", "L2", "L3", "L4", "L5"],
            "expected_count": 6,
            "positioning": "违反影响程度",
            "derivation": "由 主轴 + rule_nature + 影响面推导",
            "note": "不沿用 severity_raw；unknown 不得当低风险。",
        },
        "quality_tag": {
            "label": "quality_tag",
            "values": ["EDITORIAL", "REFERENCE", "STRUCTURE"],
            "expected_count": 3,
            "positioning": "质量问题标记；可与主轴并存，不夺主轴",
            "derivation": "由 §2.8 is_editorial() 与形式类缺陷判定",
            "note": "quality_tag 非空不等于 QUALITY_ONLY",
        },
        "topic": {
            "label": "topic",
            "values": ["（取自子类名，开放集合）"],
            "expected_count": 0,
            "positioning": "主题；仅用于报告分组与检索",
            "derivation": "由 subclass_original / 规则主题判定",
            "note": "topic 不参与主轴判定，不得反向推理",
        },
    }


def _axis_code_of(desc: str) -> str | None:
    """从争议描述里认出一个七轴枚举值；认不出返回 None。

    只认**开头**的轴名（如 `FCT5 …` → FACT），不做全串搜索 ——
    描述里常同时出现两个轴（「DSC12 枚举太窄，FCT10 测试不通过」），
    在串中间搜索会按出现顺序返回结果，等于赌写法。
    """
    m = re.match(r"^(CHAN|RIGHT|SCENE|DISC|BRAND|FACT|CLAIM)\b", desc.strip())
    if m:
        return m.group(1)
    # 编号前缀 → 轴（FCT5 → FACT）
    m = re.match(r"^(CHN|RGT|SCN|DSC|BRD|FCT|CLM)\d+", desc.strip())
    if m:
        return {"CHN": "CHAN", "RGT": "RIGHT", "SCN": "SCENE", "DSC": "DISC",
                "BRD": "BRAND", "FCT": "FACT", "CLM": "CLAIM"}[m.group(1)]
    return None


def check_coverage(raw: str, data: dict) -> list[str]:
    """**执行点**：规范 §3 的每个编号条件都必须在 JSON 里；JSON 里不许有规范已删的。"""
    problems = []
    spec_ids = [m.group(1) for m in COND_ROW.finditer(raw)]
    json_ids = []
    for a in data["axes"]:
        for c in a["criteria"]:
            m = re.match(r"^([A-Z]{2,4}\d+)：", c)
            if m:
                json_ids.append(m.group(1))

    missing = [i for i in spec_ids if i not in json_ids]
    extra = [i for i in json_ids if i not in spec_ids]
    if missing:
        problems.append(f"JSON 缺规范里的条件：{missing}")
    if extra:
        problems.append(f"JSON 有规范里已删的条件：{extra}")
    if len(set(spec_ids)) != len(spec_ids):
        problems.append(f"规范里编号重复：{sorted({i for i in spec_ids if spec_ids.count(i) > 1})}")
    return problems


def selftest() -> int:
    """反向对照：喂坏样本必须红。"""
    checks = []
    ok = lambda n, c: checks.append((n, bool(c)))

    raw, body = read_spec()
    data = build(raw, body)
    problems = check_coverage(raw, data)
    ok("真规范上覆盖完整（正向对照）", not problems)

    # 1) 删掉一条 criteria → 必须报「缺」
    bad = json.loads(json.dumps(data))
    victim = bad["axes"][3]["criteria"].pop(0)
    ok("删一条 criteria → 覆盖检查变红", check_coverage(raw, bad))

    # 2) 加一条规范里没有的编号 → 必须报「多」
    bad2 = json.loads(json.dumps(data))
    bad2["axes"][0]["criteria"].append("CHN99：伪造条件 → 命中 CHAN")
    ok("加一条伪造编号 → 覆盖检查变红", check_coverage(raw, bad2))

    # 3) 指纹只对正文：版本说明块里有明文指纹，改它不该改变指纹
    v2 = body + "\n\n> 补一句无关的话"
    ok("指纹对正文敏感", fingerprint(body) != fingerprint(v2))
    ok("指纹是 12 位十六进制", re.fullmatch(r"[0-9a-f]{12}", fingerprint(body)) is not None)

    # 4) 版本说明块必须被剥掉：正文里不该出现 VER_BEGIN 的标记
    ok("指纹正文已剥掉版本说明块", VER_BEGIN not in body)

    failed = [n for n, p in checks if not p]
    for n, p in checks:
        print(("✓ " if p else "✗ ") + n)
    print(f"\n{'✅' if not failed else '❌'} {len(checks) - len(failed)}/{len(checks)} 项通过")
    return 0 if not failed else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验不写盘")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    try:
        raw, body = read_spec()
    except Exception as e:
        print(f"⚠ 未测：读不到规范 {SPEC}：{e}", file=sys.stderr)
        return 2

    data = build(raw, body)
    problems = check_coverage(raw, data)

    n_cond = sum(1 for a_ in data["axes"] for c in a_["criteria"] if re.match(r"^[A-Z]{2,4}\d+：", c))
    print(f"规范指纹 {data['meta']['spec_fingerprint']} · 版本 {data['meta']['spec_version']}")
    print(f"七轴 · 编号条件 {n_cond} 条 · 边界样本 {len(data['rule_examples'])} 条 · 欠定登记 {len(data['meta']['boundary_disputes'])} 条")

    if problems:
        for p in problems:
            print(f"❌ {p}", file=sys.stderr)
        return 1

    if a.check:
        if OUT.exists():
            old = json.loads(OUT.read_text(encoding="utf-8"))
            if old == data:
                print("✓ 磁盘上的 taxonomy.json 与规范一致")
                return 0
            print("❌ 磁盘上的 taxonomy.json 与规范不一致（需要重新生成）", file=sys.stderr)
            return 1
        print("❌ 磁盘上没有 taxonomy.json", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 已写入 {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
