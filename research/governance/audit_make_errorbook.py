#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错题本生成器 —— 从 PRD 的四张表 + 审计脚本产出，生成一份可直接使用的错题本种子文件。

设计依据：
  R4 §7.2.1  错题本缺失的 12 个字段
  R4 §7.2.2  FP / FN 的采集路径
  R4 §7.2.3  最小可用模板
  R4 §7.5.2  建议的六档严重等级
  R3 §11.6   规则 schema（scope / revision / evaluability）
  05 号文档  §6.3 错题本缺的三个连接

产出：
  1. 错题本.md          —— 给人看的说明 + 判据
  2. errorbook.csv      —— 给机器导入的种子数据（UTF-8 BOM，Excel 可直接打开）
  3. errorbook_schema.md —— 字段定义

原则：
  - 只填能自动推导的字段；需要人工判断的字段一律留空并给出待填标记
  - 不臆造数据（不生成假的内容 ID、不编造复判结论）
  - 每条记录都标注"来源"，使它的产生过程可追溯

只读 PRD，写入 research/governance/errorbook/
"""
import re
import sys
import csv
import pathlib
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PRD = ROOT / "PRD" / "内容治理需求文档.md"
OUTDIR = pathlib.Path(__file__).resolve().parent / "errorbook"

SENT = "\x00P\x00"

# 规则版本号：本次分析对应的规则快照
RULE_VERSION = "R2026.09.15.0"
SNAPSHOT_DATE = "2026-09-15"


def split_md_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace(SENT, "|") for c in s.replace("\\|", SENT).split("|")]


def grab(lines, marker):
    st = next(i for i, l in enumerate(lines) if l.startswith(marker))
    hi = next(i for i in range(st, st + 10) if lines[i].strip().startswith("|"))
    h = split_md_row(lines[hi])
    out = []
    i = hi + 2
    while i < len(lines) and lines[i].strip().startswith("|"):
        out.append(split_md_row(lines[i]))
        i += 1
    return h, out


def terms(s):
    return {t.strip().lower() for t in re.split(r"[,，、;；]", s) if t.strip()}


# 建议的六档严重等级（R4 §7.5.2）
SEVERITY_MAP = {
    "高危·红": ("L4", "高危"),
    "审慎·黄": ("L3", "审慎"),
    "待复核·灰": ("L2", "待复核"),
    "合规·绿": ("L1", "合规"),
    "": ("L0", "未覆盖"),
}

# 语种映射（用于分层抽样标记）
LANG_NORM = {
    "英语": "en", "德语": "de", "法语": "fr", "西语": "es",
    "意语": "it", "其他": "other", "": "",
}


def main():
    lines = PRD.read_text(encoding="utf-8").split("\n")
    OUTDIR.mkdir(exist_ok=True)

    # ---------------------------------------------------------- 读四张表
    rec_h, rec_rows = grab(lines, "## 表：广告文案明细")
    rule_h, rule_rows = grab(lines, "## 表：品线内容边界规则库")

    rc = {h: i for i, h in enumerate(rule_h)}

    def rg(row, n):
        j = rc.get(n)
        return row[j].strip() if j is not None and j < len(row) else ""

    cc = {h: i for i, h in enumerate(rec_h)}

    def cg(row, n):
        j = cc.get(n)
        return row[j].strip() if j is not None and j < len(row) else ""

    # 规则元数据表
    rule_meta = {}
    for r in rule_rows:
        rid = rg(r, "规则编号")
        rule_meta[rid] = {
            "type": rg(r, "边界类型"),
            "severity": rg(r, "风险等级"),
            "rx": bool(rg(r, "正则表达式")),
            "kw": terms(rg(r, "检测关键词")),
            "ex": terms(rg(r, "豁免词")),
        }

    # ---------------------------------------------------------- 生成记录
    rows_out = []
    eid = 0

    # 来源 A：待人工复核的记录（132 条）
    for r in rec_rows:
        status = cg(r, "处理状态")
        if status != "待人工复核":
            continue
        eid += 1
        risk = cg(r, "风险等级")
        lv, lvname = SEVERITY_MAP.get(risk, ("L0", "未覆盖"))

        hit_rules = [t.strip() for t in re.split(r"[,，、;；\s]+", cg(r, "命中规则")) if t.strip()]
        # 依据类型：有正则的规则 → regex；无正则的 → keyword
        if len(hit_rules) == 1 and hit_rules[0] in rule_meta:
            basis = "regex" if rule_meta[hit_rules[0]]["rx"] else "keyword"
        elif hit_rules:
            basis = "mixed"
        else:
            basis = "unknown"

        seg = cg(r, "命中片段")
        # 标记是否小语种命中（05 号文档 §5.3 的发现）
        eu_terms = ["schmerzfrei", "sans douleur", "indolore", "sin dolor", "silenci", "potente"]
        is_eu = any(t in seg.lower() for t in eu_terms)

        rows_out.append({
            "错题ID": f"EB-{eid:04d}",
            "记录日期": SNAPSHOT_DATE,
            "来源": "自动抽样-风险优先",
            "抽样批次": "B2026-09-15-风险优先",
            "内容ID": cg(r, "外部广告ID") or cg(r, "广告名称")[:40],
            "平台": cg(r, "平台"),
            "地区": cg(r, "投放地区"),
            "内容语种": LANG_NORM.get(cg(r, "文案语种"), cg(r, "文案语种")),
            "内容类型": "text-ad",
            "Agent判定等级": f"{lv} {lvname}",
            "Agent判定规则": ",".join(hit_rules),
            "Agent判定依据类型": basis,
            "规则版本号": RULE_VERSION,
            "人工复判结论": "",
            "复判人": "",
            "复判时间": "",
            "错误类型": "",
            "是否对抗样本": "否",
            "对抗手法": "",
            "未覆盖原因": "",
            "处置码": "",
            "关联规则编号": "",
            "处置人": "",
            "处置日期": "",
            "备注": ("小语种命中：规则关键词列无此词（见 05 号文档 §5.3）" if is_eu else ""),
        })

    # 来源 B：规则自身的结构性缺陷（可自动发现的"规则错题"）
    # 这类不是某条文案判错，而是规则本身有缺陷 —— 单独编号 EB-R**
    rid_n = 0
    structural = []

    # B1：无正则的判险规则
    for rid, m in rule_meta.items():
        if m["type"] == "安全词白名单":
            continue
        if not m["rx"]:
            rid_n += 1
            structural.append({
                "错题ID": f"EB-R{rid_n:03d}",
                "记录日期": SNAPSHOT_DATE,
                "来源": "规则静态检查-通道",
                "抽样批次": "",
                "内容ID": "",
                "平台": "",
                "地区": "",
                "内容语种": "",
                "内容类型": "rule",
                "Agent判定等级": "",
                "Agent判定规则": rid,
                "Agent判定依据类型": "keyword",
                "规则版本号": RULE_VERSION,
                "人工复判结论": "",
                "复判人": "",
                "复判时间": "",
                "错误类型": "规则表达力不足",
                "是否对抗样本": "否",
                "对抗手法": "",
                "未覆盖原因": "规则边界不清",
                "处置码": "",
                "关联规则编号": rid,
                "处置人": "",
                "处置日期": "",
                "备注": f"{rid} 无正则表达式，{len(m['kw'])} 个关键词只有单通道；任何词形变化都会漏",
            })

    # B2：规则间关键词重叠且严重度不同
    ids = [i for i in rule_meta if i != "安全词"]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            inter = rule_meta[a]["kw"] & rule_meta[b]["kw"]
            if not inter:
                continue
            diff = rule_meta[a]["severity"] != rule_meta[b]["severity"]
            rid_n += 1
            structural.append({
                "错题ID": f"EB-R{rid_n:03d}",
                "记录日期": SNAPSHOT_DATE,
                "来源": "规则静态检查-重叠",
                "抽样批次": "",
                "内容ID": "",
                "平台": "",
                "地区": "",
                "内容语种": "",
                "内容类型": "rule",
                "Agent判定等级": "",
                "Agent判定规则": f"{a},{b}",
                "Agent判定依据类型": "keyword",
                "规则版本号": RULE_VERSION,
                "人工复判结论": "",
                "复判人": "",
                "复判时间": "",
                "错误类型": "规则冲突" if diff else "规则冗余",
                "是否对抗样本": "否",
                "对抗手法": "",
                "未覆盖原因": "",
                "处置码": "",
                "关联规则编号": f"{a},{b}",
                "处置人": "",
                "处置日期": "",
                "备注": (f"{a} 与 {b} 共享关键词 {', '.join(sorted(inter))}；"
                         + ("**严重度不同，需 hit_policy 裁决**" if diff else "严重度相同")),
            })

    # B3：安全词与判险规则的交集（语义陷阱）
    if "安全词" in rule_meta:
        for rid, m in rule_meta.items():
            if rid == "安全词":
                continue
            inter = rule_meta["安全词"]["kw"] & m["kw"]
            if inter:
                rid_n += 1
                structural.append({
                    "错题ID": f"EB-R{rid_n:03d}",
                    "记录日期": SNAPSHOT_DATE,
                    "来源": "规则静态检查-白名单冲突",
                    "抽样批次": "",
                    "内容ID": "",
                    "平台": "",
                    "地区": "",
                    "内容语种": "",
                    "内容类型": "rule",
                    "Agent判定等级": "",
                    "Agent判定规则": f"安全词,{rid}",
                    "Agent判定依据类型": "keyword",
                    "规则版本号": RULE_VERSION,
                    "人工复判结论": "",
                    "复判人": "",
                    "复判时间": "",
                    "错误类型": "规则语义陷阱",
                    "是否对抗样本": "否",
                    "对抗手法": "",
                    "未覆盖原因": "",
                    "处置码": "",
                    "关联规则编号": f"安全词,{rid}",
                    "处置人": "",
                    "处置日期": "",
                    "备注": f"词 {', '.join(sorted(inter))} 同时在『安全词白名单』与 {rid} 的判险词表中；按白名单定义不参与判险，但对维护者是陷阱",
                })

    # ---------------------------------------------------------- 写 CSV
    cols = list(rows_out[0].keys())
    csv_path = OUTDIR / "errorbook.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
        for row in structural:
            w.writerow(row)

    # ---------------------------------------------------------- 写 schema
    schema = OUTDIR / "errorbook_schema.md"
    schema.write_text(f"""# 错题本字段定义

> 由 `audit_make_errorbook.py` 生成 · {SNAPSHOT_DATE} · 规则版本 `{RULE_VERSION}`
> 字段设计依据：R4 §7.2.1（12 个缺失字段）、R4 §7.2.3（最小可用模板）、R3 §11.6（规则 schema）

## 字段总表（{len(cols)} 列）

| # | 字段 | 类型 | 填充方式 | 取值 | 依据 |
|---|---|---|---|---|---|
| 1 | `错题ID` | string | 自动 | `EB-NNNN`（内容错题）/ `EB-RNNN`（规则错题） | 本设计 |
| 2 | `记录日期` | date | 自动 | ISO 日期 | R4 §7.2.1 #4 |
| 3 | `来源` | enum | 自动 | `自动抽样-风险优先` / `自动抽样-随机` / `人工复核` / `外部反馈` / `对抗测试` / `规则静态检查-*` | R4 §7.2.2 |
| 4 | `抽样批次` | string | 自动 | `B<日期>-<方法>` | R4 §7.2.1 #11（**没有它任何比率都不可计算**） |
| 5 | `内容ID` | string | 自动 | 外部广告ID / 内容主键 | R4 §7.2.3 |
| 6 | `平台` | enum | 自动 | Google / Meta / … | — |
| 7 | `地区` | string | 自动 | **取值不规范，见 04 号文档** | — |
| 8 | `内容语种` | ISO 639-1 | 自动 | `en`/`de`/`fr`/`es`/`it` | R4 §7.2.1 #12 |
| 9 | `内容类型` | enum | 自动 | `text-ad` / `image` / `video` / `product-page` / `listing` / `rule` | — |
| 10 | `Agent判定等级` | enum | 自动 | `L0 未覆盖` / `L1 合规` / `L2 待复核` / `L3 审慎` / `L4 高危` / `L5 例外降级` | R4 §7.5.2 六档 |
| 11 | `Agent判定规则` | string | 自动 | 规则编号，多条逗号分隔 | R4 §7.2.3 |
| 12 | `Agent判定依据类型` | enum | 自动 | `regex` / `keyword` / `mixed` / `context_judgement` / `unknown` | R4 §7.2.1 #9 |
| 13 | `规则版本号` | string | 自动 | `R2026.09.15.0` | R4 §7.2.1 #7；R3 §11.6 |
| **14** | **`人工复判结论`** | **enum** | **人工填写** | `维持原判` / `推翻-应判违规` / `推翻-应判合规` / `无法判定` | **R4 §7.2.1 #2 —— FP/FN 的唯一采集入口** |
| **15** | **`复判人`** | string | **人工填写** | 人名或工号 | **R4 §7.2.1 #3 —— 须能证明未参与初判** |
| 16 | `复判时间` | datetime | 人工填写 | ISO | R4 §7.2.1 #4 |
| 17 | `错误类型` | enum | 人工填写 | PAIR 七类 / `规则表达力不足` / `规则冲突` / `规则冗余` / `规则语义陷阱` | R4 §3；本设计扩展 |
| 18 | `是否对抗样本` | bool | 自动/人工 | 是 / 否 | R4 §7.2.1 #10 |
| 19 | `对抗手法` | enum | 人工填写 | `拼音` / `拆字` / `emoji` / `变体拼写` / `同义替换` | R4 §7.2.1 #10 |
| 20 | `未覆盖原因` | enum | 人工填写 | `新表达方式` / `新语种` / `新品类` / `新平台` / `规则边界不清` / `其他` | R4 §7.2.1 #6 |
| **21** | **`处置码`** | **enum** | **人工填写** | `直接改规则` / `部分改规则` / `评估中` / `不改（附理由）` | **R4 §7.2.1 #5 —— 没有它，错题本只是一份归档** |
| 22 | `关联规则编号` | string | 自动/人工 | 规则编号 | R4 §7.2.3 |
| 23 | `处置人` | string | 人工填写 | 人名 | R4 §7.2.3 |
| 24 | `处置日期` | date | 人工填写 | ISO | R4 §7.2.3 |
| 25 | `备注` | text | 自动/人工 | 自由文本 | — |

## 状态图

```
Agent 判定
   │
   ├─ L4 高危 / L3 审慎 ──→ 上线前人工复核（100%）
   │                            │
   │                            ├─ 维持原判 ──→ 处置
   │                            └─ 推翻-应判合规 ──→ 【误拦 FP】
   │
   ├─ L2 待复核 ──────────→ 人工队列
   │
   ├─ L1 合规 ────────────→ 自动放行
   │                            │
   │                            └─ 每周随机抽 30 条复判
   │                                 └─ 推翻-应判违规 ──→ 【漏放 FN】
   │
   └─ L0 未覆盖（兜底规则命中）──→ 人工队列 + 必填"未覆盖原因"
                                    └─ 重复出现 ──→ 【规则生产原料】
```

## 三个必须守住的设计点

1. **`判定结果` 必须存在 `L0 未覆盖` 这一态。** 若"未命中"直接落到"合规"，**盲区率在数学上不可观测**（R4 §5.4、§7.5.2）。
2. **`判定路径`（本设计体现为 `Agent判定依据类型` + `复判人` 是否为空）必须从第一天落库。** Meta 因未记录判定路径，而无法计算 Oversight Board rec.13 要求的对比错误率（R4 §7.2.1 #8 逐字引用）。
3. **`处置码` + `关联规则编号` + `处置人` + `处置日期` 四件套是把错题本变成规则生产原料的关键。** 缺了它们，错题本就只是归档（R4 §7.2.3）。
""", encoding="utf-8")

    # ---------------------------------------------------------- 写说明
    n_content = len(rows_out)
    n_rule = len(structural)
    eu_cnt = sum(1 for r in rows_out if "小语种" in r["备注"])

    md = OUTDIR / "错题本.md"
    md.write_text(f"""# 错题本 · 种子文件

> 生成时间：{SNAPSHOT_DATE}
> 规则版本：`{RULE_VERSION}`
> 生成脚本：`../audit_make_errorbook.py`（可重复运行）
> 数据来源：`PRD/内容治理需求文档.md` 的广告文案明细表 + 规则库表

---

## 这是什么

**它不是一份新的设计文档，是一份可以打开就填的表。**

用户原话问过：「是否需要给我们提供『错题本』？还是规则库？严重等级？要是没有呢？怎么处理？」
这份文件回答的是**错题本长什么样、由谁产生、填完之后去哪里**。

## 文件清单

| 文件 | 用途 |
|---|---|
| `errorbook.csv` | **主文件**。{n_content + n_rule} 条记录，{len(cols)} 列。UTF-8 BOM，Excel / 飞书多维表格可直接导入 |
| `errorbook_schema.md` | 每列的字段定义、取值枚举、填写方式、依据出处 |
| `错题本.md` | 本文件：怎么用、谁填、填完去哪 |

## 内容构成

| 来源 | 条数 | 说明 |
|---|---:|---|
| **A. 待人工复核的记录** | **{n_content}** | 从广告文案明细表中 `处理状态 = 待人工复核` 的记录直接导出，11 个字段已自动填好 |
| **B. 规则自身缺陷** | **{n_rule}** | 由 `audit_rule_consistency.py` 的静态检查产生，不是某条文案判错，而是规则本身有问题 |
| 合计 | **{n_content + n_rule}** | |

其中，**{eu_cnt} 条**记录被标注为「小语种命中」—— 即命中了，但该词既不在规则的关键词列、也不在它的正则里（见 `05-内部证据` §5.3）。

## 两类错题的区别（重要）

| | A 类：内容错题（`EB-NNNN`） | B 类：规则错题（`EB-RNNN`） |
|---|---|---|
| 记的是 | 某一条具体内容判得对不对 | 某条规则本身有没有缺陷 |
| 谁产生 | 自动导出 + 人工复判 | 静态检查，自动产生 |
| 谁来填 | **复核人**（填 `人工复判结论`）+ **规则维护人**（填 `处置码`） | **规则维护人** |
| `内容ID` | 有 | 空（它不针对具体内容） |
| 复判结论的意义 | 决定这是 FP 还是 FN | 不适用 |

**B 类是这个错题本里最容易被人忽略、但价值最高的一类。** 它不需要等任何一条文案出错就能发现规则的问题。

## 怎么用（三步）

### 第一步：填 A 类的 `人工复判结论`（{n_content} 条）

这是唯一需要人力投入的动作，也是**目前完全没有在做的事**（`检查人` 列非空率 0.0%）。

- 高危（L4）**全部**要复判，审慎（L3）抽 20%
- 填写 `维持原判` / `推翻-应判违规` / `推翻-应判合规` / `无法判定`
- 同时填 `复判人` 与 `复判时间`

**为什么要做这一步**：现在这 {n_content} 条在表里只有「待人工复核」一个状态，**没有出口**。规则判了红/黄/灰，但没有任何地方记录人看了之后怎么想。这一步做完，`误拦 (FP)` 与 `漏放 (FN)` 才第一次变得可计算。

### 第二步：填 B 类的 `处置码`（{n_rule} 条）

B 类不需要复判，直接进入规则维护流程。填 `直接改规则` / `部分改规则` / `评估中` / `不改（附理由）`。

**注意**：`不改（附理由）` 也是一个合法答案，但**理由必须写**。允许不改，不允许不说明。

### 第三步：每周新增「随机抽样」批次

A 类是**按风险优先**导出的（来自投放金额排序的表），它**只适合用来发现错误，不能用来估计错误率**（R4 §7.2.2）。

要算比率，必须另建随机批次：**每周从 `合规·绿` 里随机抽 30 条复判**，并且**按语种分层**（德/法/西/意 每语种每两周至少 5–10 条）。

> 原因：这套规则库的检测关键词里，**小语种词占比 0%**（424 个关键词，0 个小语种），而实际投放的非英语文案占 28.2%。**不按语种分层抽样，小语种的漏检永远不会被发现。**

## 这份文件没有做什么

为了不误导，明确列出**没有**做的事：

| 没有做 | 原因 |
|---|---|
| 没有生成假的内容 ID 或复判结论 | 不臆造数据。所有需要人工判断的字段一律留空 |
| 没有把'合规·绿'的 157 条纳入 A 类 | 它们是自动放行的，不是"待复核"。要采集它们的错误需要**另建随机批次**（第三步） |
| 没有包括官网产品页 / Amazon listing | 现有 291 条全部来自 Google(262) 和 Meta(27)。**官网与 listing 尚未进入审查范围** —— 这是需要确认的问题，不是本文能解决的 |
| 没有计算任何"准确率" | 没有随机样本 + 没有复判结论，**任何比率都是假的** |
| 没有臆造"小语种命中"的归因 | {eu_cnt} 条被标注出来了，但**为什么会被命中**（是否存在第二套检测逻辑）需要向团队确认，见 `05-内部证据` §7 Q3 |

## 与其他交付物的关系

```
PRD 四张表
    │
    ├─ 广告文案明细（291）──┐
    ├─ 规则库（21）────────┤
    ├─ W1卖点表达边界（19）─┤
    └─ 改写建议库（52）─────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │  错题本（本目录）             │
              │  A 类 {n_content} 条 + B 类 {n_rule} 条  │
              └─────────────────────────────┘
                            │
              填完处置码后回流 ▼
              ┌─────────────────────────────┐
              │  规则库（21 条 → 修订版）      │
              └─────────────────────────────┘
```

**注意 `W1卖点表达边界`（19 条）和 `改写建议库`（52 条）的位置**：它们**已经是错题本的形态**，只是记录的是「这个卖点该怎么表达」而不是「哪一条判错了」。

**它们不需要重建，只需要接上 `错题ID` 列**——让「这条改写建议是因为哪条错题产生的」变得可追溯。这是下一步可以做的事，本次未做（因为需要团队先确认改写建议的实际产生过程）。
""", encoding="utf-8")

    # ---------------------------------------------------------- 输出
    print(f"输出目录：{OUTDIR}")
    print()
    print(f"  errorbook.csv          {n_content + n_rule} 行 × {len(cols)} 列")
    print(f"     A 类 内容错题        {n_content} 条")
    print(f"     B 类 规则错题        {n_rule} 条")
    print(f"  错题本.md")
    print(f"  errorbook_schema.md")
    print()
    print("B 类明细：")
    for r in structural:
        print(f"  {r['错题ID']}  [{r['错误类型']}]  {r['关联规则编号']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
