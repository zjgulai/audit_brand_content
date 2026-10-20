#!/usr/bin/env python3
"""
kb_facts.py —— 需求知识库的**事实数字单一来源**

## 为什么存在

`research/kb/README.md` §一「一页纸现状」是这套知识库的门面：10 个数字，一眼
看完。它同时也是最容易腐烂的东西 —— 数字由人抄，重算一次就发现对不上。

本轮（B3.0）实测到三处，都是同一个病的不同形态：

  ① **逾期数每天自动漂移。** `tools/kb_query.py 2` 用 `load.today()` 当基准日，
     于是 09-16 生成的手册写「逾期 30 条」，09-17 跑同一条命令得到 33 条。
     手册里那条「可复现命令」复现不出手册里的数 —— 而且**没有任何东西会发现**。
     逾期是**数据的属性**，不是提问时刻的属性：基准日必须是快照日。
  ② **同一个数在两处自相矛盾。** README §四.4 与 `tools/kb_materials_lark.py`
     的 docstring 都写「材料 15 条里可读 5 条」，而同一个文件里的实测列算出来是
     4 条 —— 代码打印 4，散文写 5，谁也没红。
  ③ **散文里的数字没有重算入口。** 想核对只能人肉数一遍。

## 本脚本的规矩

**一个数字只写一次，且由脚本算。** README 里那段现状表变成生成块
（`<!-- facts:begin -->` … `<!-- facts:end -->`），散文里不再复述数字，
只指向这里。数字变了而块没重生成 → `--check` 变红。

**基准日 = 快照日。** 见 `load.basis_date()`。这样同一份快照永远算出同一组数，
而「今天的逾期」要靠重新拉快照得到 —— 与 §三.5「v1 不做实时同步」一致。

用法：
  python3 tools/kb_facts.py            # 重算并写回 README 的生成块
  python3 tools/kb_facts.py --check     # 只比对不改盘（退出码非 0 = 块已过期）
"""

import collections
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
import load  # noqa: E402

KB = load.KB
LEDGER = os.path.join(KB, "台账-v1.json")
COVERAGE = os.path.join(KB, "覆盖报告.json")
EVIDENCE = os.path.join(KB, "证据映射.json")
ANALYSIS = os.path.join(KB, "结构分析.json")
README = os.path.join(KB, "README.md")

BEGIN = "<!-- facts:begin -->"
END = "<!-- facts:end -->"

IN_FLIGHT = ("进行中", "未开始", "已停滞")


def _load_live_samples():
    """从 `research/live/LATEST.json` 指向的快照里取「正面和负面样本」表。

    返回 `(doc, source)`：`doc` 是整份快照，`source` 是 `sources["kb_samples"]`。
    任何一环缺失都**返回 `(None, None)` 而不是抛异常** —— 调用方要把「没拉到」
    与「拉到了但是 0 条」区分开，这两种情况在报告里必须长得不一样
    （AGENTS.md §2.4.1：空结果与读错了不许混为一谈）。

    ★ 刻意**不复用** `tools/live_snapshot.py` 里的 `SOURCES` 常量：
      那个文件是**写快照**的，本文件是**读快照**的。共用一份常量会让
      「拉取端与消费端同时改错」变成一个静默的巧合，而 E2 需要的正是两套独立实现。
    """
    ptr = os.path.join(load.REPO, "research", "live", "LATEST.json")
    if not os.path.exists(ptr):
        return None, None
    try:
        latest = json.load(open(ptr, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    name = latest.get("latest")
    if not name:
        return None, None
    path = os.path.join(load.REPO, "research", "live", name)
    if not os.path.exists(path):
        return None, None
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    return doc, (doc.get("sources") or {}).get("kb_samples")


def _rows(snap):
    led = json.load(open(LEDGER, encoding="utf-8"))
    rs = [r for r in led["records"] if r["role"] != "excluded"]
    return led, rs, snap


def _n_src(ext_doc, host):
    """来源里 URL 含该主机的个数（缺口 KB-GAP-10–KB-GAP-12 的量从制品算，不手写）。"""
    return sum(1 for s in ext_doc.get("sources", [])
               if host in (s.get("url") or ""))


def _n_ent(ext_doc, host):
    sids = {s["id"] for s in ext_doc.get("sources", [])
            if host in (s.get("url") or "")}
    return sum(1 for e in ext_doc.get("entries", []) if e.get("source_id") in sids)


def _real_rules(rules_p):
    """真规则数 = 规则键数 - catch_all（catch-all 不是规则，是兜底）。"""
    if not os.path.exists(rules_p):
        return 0
    return len([r for r in json.load(open(rules_p, encoding="utf-8"))["rules"]
                if r["rule_key"] != "CATCH-ALL-01"])


def _only_general(ext_doc, rules_p):
    """只有 FTC 举证通则（EXT-039）一条依据的规则数 —— KB-GAP-13 的量。"""
    if not os.path.exists(rules_p):
        return 0
    cov = {}
    for e in ext_doc.get("entries", []):
        for k in (e.get("关联规则") or []):
            cov.setdefault(k, []).append(e.get("id"))
    return len([r for r in json.load(open(rules_p, encoding="utf-8"))["rules"]
                if r["rule_key"] != "CATCH-ALL-01"
                and cov.get(r["rule_key"]) == ["EXT-039"]])


def compute(snap=None):
    """算出全部对外引用的事实数字。**每一个都必须是快照的纯函数。**"""
    if snap is None:
        snap = load.snapshot()
    led, rs, snap = _rows(snap)
    cov = json.load(open(COVERAGE, encoding="utf-8"))
    ev = json.load(open(EVIDENCE, encoding="utf-8"))
    an = json.load(open(ANALYSIS, encoding="utf-8"))

    basis = load.basis_date(snap)

    done = [r for r in rs if r.get("status") == "已完成"]
    free = [r for r in rs if r.get("status") in IN_FLIGHT]
    due = [r for r in rs if r.get("date_due") and r.get("status") != "已完成"]
    over = [r for r in due if load.days_between(r["date_due"], basis) > 0]

    src_records = sum(x["source_records"] for x in cov["coverage"])
    no_ev = sum(r["需求条数"] for r in ev["rows"] if not r["已声明证据数"])
    with_ev = sum(r["需求条数"] for r in ev["rows"] if r["已声明证据数"])

    # 材料可读性：唯一来源是 kb_materials_lark 的实测列
    sys.path.insert(0, os.path.join(load.REPO, "tools"))
    import kb_materials_lark as mat                                   # noqa: PLC0415
    readable = sum(1 for m in mat.MATERIALS if m["可读性"] == "ok")

    start_like = [f"{t.system}/{t.name}:{f}"
                  for t in snap.ledger_tables() for f in (t.fields or [])
                  if any(k in str(f) for k in ("开始", "启动"))]

    # 正负样本：★ 2026-10-20 换源。
    #
    #   在此之前读的是 `_evidence/正负样本.raw.txt`（1.3 KB / 5 条 / 抬头 returned=8），
    #   而云端同表当时已有 **186 条**。也就是说：**管线在读一份 09-16 的旧 dump，
    #   并把「抬头 vs 盘上」的计数矛盾当成样本库的全部问题。**
    #   真相更简单也更难看 —— 不是数据没有，是本地没读。
    #
    #   现在读 `research/live/LATEST.json` 指向的快照（`tools/live_snapshot.py` 产出，
    #   与云端同一次拉取）。★ 这里**仍然独立解析一遍**（不复用 kb_classes 的解析器）：
    #   E2 要在「登记表里写的数」与「重算出来的数」之间比对，两者必须来自不同的实现，
    #   否则那条检查是恒真的 —— 这条理由在换源之后一字未变。
    smp_doc, smp_src = _load_live_samples()
    smp_recs = (smp_src or {}).get("records") or []
    smp_total = (smp_src or {}).get("api_total")
    # 「样例」是旧 dump 里的标记；新快照的备注列已变成自动评分（「价值评分: N」）。
    # 保留这个数，是为了让它**降到 0 并保持 0** 时能被看见：
    # 一旦又有真实记录被手工标成样例，它会重新变正。
    smp_marked = sum(
        1 for it in smp_recs
        if "样例" in str((it.get("fields") or {}).get("备注（如处理结果/建议）") or "")
    )

    # ── 图文对应与正文噪音（2026-10-20 委托方指出后当场量化）──────────────
    #   委托方的原话是「很多『图片素材』和『具体原因/分析』无法对应」以及
    #   「『具体原因/分析』里有很多噪音文本」。这两句都能变成可重算的数，
    #   所以它们是判据，不是印象。
    #
    #   ★ 「无法对应」的成因不是内容没写清楚，而是**结构上不可能对应**：
    #     344 个附件的文件名 **100% 是 `sN_N.png`** —— 占位式重命名，
    #     原始文件名（含时间/序号/素材标识）在采集时就丢了。
    #     于是「这句话说的是第几张图」这件事**没有任何字段承载**。
    _att_re = re.compile(r"^s\d+_\d+\.png$")
    smp_att_names = [a.get("name") or ""
                     for it in smp_recs
                     for a in ((it.get("fields") or {}).get("图片素材") or [])]
    smp_att_renamed = sum(1 for n in smp_att_names if _att_re.match(n))
    # 附件数 vs 原文反馈里 `!Image` 标记数：不等即「贴进群里的图和存下来的图不是同一组」
    smp_att_count_mismatch = 0
    for it in smp_recs:
        f = it.get("fields") or {}
        n_img = len(f.get("图片素材") or [])
        n_mark = len(re.findall(r"!Image|\[图片\]", str(f.get("原文反馈") or "")))
        if n_img != n_mark:
            smp_att_count_mismatch += 1

    def _noise(f):
        """`具体原因/分析` 里属于「聊天转录」而非「审查结论」的特征。

        这些特征不是我们猜的：它们是从正文里数出来的，且**同时出现在多数记录里**，
        说明这一列实际上存的是「把群里那段对话粘过来」，而不是「结构化的判定理由」。
        """
        t = str(f.get("具体原因/分析") or "")
        marks = 0
        marks += 1 if re.search(r"^\s*【审核问题】", t) else 0
        marks += 1 if re.search(r"@[一-龥A-Za-z]{2,6}", t) else 0
        marks += 1 if re.search(r"(麻烦看看|看看呀|麻烦看下|辛苦|姐姐|收到|好的)", t) else 0
        marks += 1 if re.search(r"(\[图片\]|!Image|:YouAreTheBest:|【项目方|【初审|【终审|【复审)", t) else 0
        return marks

    smp_noise_marks = [_noise(it.get("fields") or {}) for it in smp_recs]
    smp_noise_any = sum(1 for m in smp_noise_marks if m > 0)
    smp_noise_heavy = sum(1 for m in smp_noise_marks if m >= 2)

    # ── 更深的一层（2026-10-20 挖掘后）：这张表不是判例库，是设计审核群的聊天转录 ──
    #   两个发现必须成为可重算的数，否则下一个人会拿 `审核人` 字段去统计「谁审得多」，
    #   得到一个完全错的结论。
    #
    #   ① `审核人` 字段 == `来源` 里的名字（都是**把内容转进群的人**），
    #      而**不是**正文 `【终审-@X】` 里被请去审的人。
    #   ② `原文反馈` 的 `【审核】` 段里，很大一部分正文其实是**送审请求**
    #      （`【终审-@X】麻烦看看` + 一段需求简报），不含任何审核结论。
    _req_re = re.compile(r"^\s*【(初审|终审|复审|复核)[^】]*】")
    _src_name_re = re.compile(r"·\s*([^·]+?)\s*$")
    _verdict_re = re.compile(r"(建议|不对|去掉|不合适|应该改|需要改|重新|错误|用错|不要用)")

    def _first_audit_body(text):
        """取第一段 `【审核 …】` 的正文（与 kb_sample_extract 同口径，但独立实现）。"""
        marks = [(m.group(1), m.start(), m.end())
                 for m in re.finditer(r"^【([^】]{1,40})】", text, re.M)]
        for i, (hdr, _s, hend) in enumerate(marks):
            if hdr.strip().startswith("审核"):
                end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
                return text[hend:end].strip()
        return None

    smp_reviewer_is_forwarder = 0   # 审核人字段 == 来源名（即转发者）
    smp_audit_is_request = 0        # 审核段正文实为送审请求
    smp_request_no_verdict = 0      # 送审请求且完全不含判定词
    for it in smp_recs:
        f = it.get("fields") or {}
        who = str(f.get("审核人") or "").strip()
        m = _src_name_re.search(str(f.get("来源") or ""))
        src_name = (m.group(1).strip() if m else "")
        if who and who == src_name:
            smp_reviewer_is_forwarder += 1
        body = _first_audit_body(str(f.get("原文反馈") or ""))
        if body is not None and _req_re.match(body):
            smp_audit_is_request += 1
            if not _verdict_re.search(body):
                smp_request_no_verdict += 1

    # ── 品牌层（2026-10-20）：三个数，全部从制品算，不手写 ─────────────
    #   这一层此前**一条缺口编号都没有**，而它是最高频的问题类别
    #   （讨论稿 33/98；样本表里「品牌一致性」71/186 也是最高频）。
    #   缺编号 = 缺执行点 = 缺了也没人会知道。
    brand = {
        "控制点_品牌族": None,       # 空族即为 0
        "控制点_总数": None,
        "七轴_BRAND_条数": None,
        "引擎品牌规则数": None,      # rules-v1 里 topic 以 BRAND 开头 / 关键词属品牌语境
    }
    cp_p = os.path.join(load.REPO, "research", "governance", "control-points-v1.json")
    if os.path.exists(cp_p):
        cpd = json.load(open(cp_p, encoding="utf-8"))
        fams = cpd.get("families") or []
        # 实测（2026-10-20）：`families` 是**字符串列表**（族名），不是对象列表。
        # 第一版按 `.get("family")` 取，直接 AttributeError —— 记在这里，
        # 免得下一个人又照着「一般是对象数组」的直觉写一遍。
        names = [str(x) for x in fams] if isinstance(fams, list) else (
            list(fams.keys()) if isinstance(fams, dict) else [])
        empty = [e.get("family") for e in (cpd.get("empty_families") or [])]
        brand["控制点_总数"] = len(names) + len(empty)
        brand["控制点_品牌族"] = (
            0 if "品牌控制" in empty else sum(
                1 for n in names if "品牌" in n))
        brand["控制点_空族"] = len(empty)
    mece_p = os.path.join(load.REPO, "research", "governance",
                          "rules-mece-migration-v1.json")
    if os.path.exists(mece_p):
        m = json.load(open(mece_p, encoding="utf-8"))
        asg = m.get("assignments") or m.get("items") or []
        # 实测（2026-10-20）：轴名字段叫 **`primary`**（FACT/CLAIM/DISC/BRAND/…），
        # 不是 `axis`。第一版读 `axis`，得到 0 —— 一个「字段名读错 → 安静产出 0」
        # 的教科书例子（AGENTS.md §2.4.1 第 1 行）。所以这里同时留两个键做兜底，
        # 但以 `primary` 为准。
        brand["七轴_BRAND_条数"] = sum(
            1 for a in asg
            if str(a.get("primary") or a.get("axis") or "").upper().startswith("BRAND"))

    # 品牌资产落盘完整度：manifest 声明了哪些文件、盘上少了几个。
    #   ★ 这个数此前只存在于 `verify_assets_baseline.py` 的退出码里，而该 verifier
    #     没被登记进 AGENTS.md §2.1 的自证表 —— 所以它天天红，没人看见。
    #     放进 kb_facts 之后，E2「缺口量可重算」会顺带守住它。
    brand_asset = {"files": None, "missing": None}
    man_p = os.path.join(load.REPO, "PMO", "audit", "momcozy-assets", "manifest.json")
    if os.path.exists(man_p):
        try:
            man = json.load(open(man_p, encoding="utf-8"))
            files = man.get("files") or []
            brand_asset["files"] = len(files)
            brand_asset["missing"] = sum(
                1 for f in files
                if f.get("dst_path") and not os.path.exists(
                    os.path.join(load.REPO, f["dst_path"])))
        except (json.JSONDecodeError, OSError):
            pass

    ext_p = os.path.join(KB, "外部标准库-v1.json")
    ext_doc = json.load(open(ext_p, encoding="utf-8")) if os.path.exists(ext_p) else {"entries": []}

    # 4 类知识库「有没有货」：四类各自的判据都取自**不同的制品**，
    # 这样这个数就不是某一张表的自述，而是四条独立证据的合计。
    rules_p = os.path.join(load.REPO, "research", "governance", "skeleton", "rules-v1.json")
    n_rules = len(json.load(open(rules_p, encoding="utf-8"))["rules"]) \
        if os.path.exists(rules_p) else 0
    # 品牌：引擎里有没有品牌规则（实测 26 条全是医疗/FDA/竞品/安全/紧迫感，0 条品牌）
    if os.path.exists(rules_p):
        _rs = json.load(open(rules_p, encoding="utf-8"))["rules"]
        brand["引擎品牌规则数"] = sum(
            1 for r in _rs
            if str(r.get("topic") or "").upper().startswith("BRAND")
            or "brand" in str(r.get("rule_key") or "").lower())
    # 存量广告语料（B3.4 演练）：有文案的 / 没文案的 / 没文案却被标绿的
    rec_p = os.path.join(load.REPO, "research", "governance", "skeleton", "_data",
                         "records.json")
    ads = json.load(open(rec_p, encoding="utf-8")) if os.path.exists(rec_p) else {}
    ads = ads.get("records", ads) if isinstance(ads, dict) else ads
    ads = ads or []

    def _spend(x):
        try:
            return float(x.get("_spend") or 0)
        except (TypeError, ValueError):
            return 0.0

    # ★ 2026-09-17（KB-GAP-9 执行）：原来这里只有一句话 ——「没有 Primary Text / Headline
    #   的就是无文案广告」。数出来 59 条。**其中 2 条根本不是广告**：所有身份字段
    #   （广告名称 / 外部广告ID / 广告账号 / 平台）全空，是没读到的空行。
    #   合并计数的后果很具体：「去修拉取管道」与「去改口径」这两件不相干的事
    #   会被记成同一个数。所以「无文案」与「未读到」从今天起分开算。
    _IDENT = ("广告名称", "外部广告ID", "广告账号", "平台")

    def _is_ad(x):
        return any((x.get(f) or "").strip() for f in _IDENT)

    no_text_raw = [x for x in ads
                   if not ((x.get("Primary Text") or "").strip()
                           or (x.get("Headline") or "").strip())]
    no_text = [x for x in no_text_raw if _is_ad(x)]        # 真实广告，载体无文案
    unread = [x for x in no_text_raw if not _is_ad(x)]     # 整行没读到

    # ★ 引擎侧的两个数（规则库够不够得着 / 源表绿标有没有漏放）不在这里手算 ——
    #   它们要跑判定引擎，属于 governance 线。kb_facts 只把它们**转发**出来，
    #   并核对制品自带的输入指纹：源表改了而账没重算 → 这里直接抛，不留一个
    #   没人知道过期了的数字（这正是本文件开头那三个病例的同一个病）。
    rl_p = os.path.join(load.REPO, "research", "governance", "skeleton", "_data",
                        "风险等级-还原.json")
    rl = json.load(open(rl_p, encoding="utf-8")) if os.path.exists(rl_p) else None
    _FIX = "修复：python3 research/governance/audit_risk_label.py"
    if os.path.exists(rec_p) and rl is None:
        # 语料在、账不在 —— 不许静默降级成 None。None 会让 E2 报成
        # 「登记 157 vs 重算 None」，读起来像是数字错了，其实是没有账。
        raise SystemExit(f"❌ 风险等级-还原.json 不存在，而 records.json 在。{_FIX}")
    if rl is not None:
        want = hashlib.sha256(open(rec_p, "rb").read()).hexdigest() \
            if os.path.exists(rec_p) else None
        if rl.get("source_sha256") != want:
            raise SystemExit("❌ 风险等级-还原.json 已过期（源表指纹对不上）。" + _FIX)
    rl_t = (rl or {}).get("totals", {})

    # ★ 迁移保真度对账账本（KB-GAP-15/KB-GAP-16）。与上面同一条纪律：不在这里手算，
    #   只转发 + 核对指纹。它比 风险等级-还原.json 多挂了四个输入
    #   （旧规则集 / 新规则 / 白名单 / 语境守卫），任一改动都会让它过期 ——
    #   而 KB-GAP-15 的结论正是「迁移不保真」，所以账一旦过期，结论就不再可信。
    mf_p = os.path.join(load.REPO, "research", "governance", "skeleton", "_data",
                        "迁移保真度.json")
    mf = json.load(open(mf_p, encoding="utf-8")) if os.path.exists(mf_p) else None
    if mf is None:
        raise SystemExit("❌ 迁移保真度.json 不存在 —— KB-GAP-15/KB-GAP-16 的量没有家。"
                         "修复：python3 research/governance/audit_migration_fidelity.py")
    _skel = os.path.join(load.REPO, "research", "governance", "skeleton")
    for _n, _rel in [("records.json", os.path.join("_data", "records.json")),
                     ("rules_raw.json", os.path.join("_data", "rules_raw.json")),
                     ("rules-v1.json", "rules-v1.json"),
                     ("whitelist-v1.json", "whitelist-v1.json"),
                     ("context-guards-v1.json", "context-guards-v1.json")]:
        _p = os.path.join(_skel, _rel)
        if not os.path.exists(_p):
            continue
        _want = hashlib.sha256(open(_p, "rb").read()).hexdigest()
        if (mf.get("source_sha256") or {}).get(_n) != _want:
            raise SystemExit(f"❌ 迁移保真度.json 已过期（{_n} 指纹对不上）。修复："
                             "python3 research/governance/audit_migration_fidelity.py")
    mf_t = mf.get("totals", {})

    prod_readable = sum(1 for m in mat.MATERIALS
                        if m.get("归属知识库") == "产品描述库" and m["可读性"] == "ok")

    f = {
        "basis_date": basis,
        "snapshot_id": snap.snapshot_id,
        "source_systems": len({x["system"] for x in cov["coverage"]}),
        "source_tables": sum(1 for t in snap.all() if not t.excluded),
        "source_tables_excluded": sum(1 for t in snap.all() if t.excluded),
        "source_tables_in_ledger": sum(1 for x in cov["coverage"] if x["included"]),
        "source_records": src_records,
        "visibility_gaps": len(snap.visibility_gaps()),
        "ledger_total": len(rs),
        "ledger_top": sum(1 for r in rs if r["level"] == "top"),
        "ledger_child": sum(1 for r in rs if r["level"] == "child"),
        "in_flight": len(free),
        "due_dated": len(due),
        "overdue": len(over),
        "done": len(done),
        "done_no_deliverable": sum(1 for r in done if not r.get("deliverable")),
        "cross_table_dups": an["duplicate_summary"]["cross_table_keys"],
        "evidence_items": ev["totals"]["declared_evidence"],
        "lines_with_evidence": ev["totals"]["lines_with_evidence"],
        "lines_total": len(ev["rows"]),
        "demands_with_evidence": with_ev,
        "demands_without_evidence": no_ev,
        "demands_unmapped": ev["totals"]["demands_unmapped"],
        "empty_tables": sum(1 for t in snap.all() if t.kind == "empty"),
        "start_like_fields": len(start_like),
        # ★ 键名刻意不改（samples_on_disk 等）：改名会让「读数变了」与「键名变了」
        #   混在一次 diff 里，而 E2 正是拿这些键做比对的。改的是**取值来源**。
        "samples_on_disk": len(smp_recs),
        "samples_marked_sample": smp_marked,
        "samples_real": len(smp_recs) - smp_marked,
        "samples_header_returned": smp_total if smp_total is not None else None,
        "samples_source": (os.path.basename(
            (smp_doc or {}).get("_file") or "research/live/LATEST.json")),
        "samples_snapshot_at": (smp_doc or {}).get("captured_at_utc"),
        "samples_unclassified": sum(
            1 for it in smp_recs
            if not str((it.get("fields") or {}).get("原因分类") or "").strip()),
        # ── 2026-10-20 委托方指出后当场量化：图文对应 / 正文噪音 ──
        "samples_attachments": len(smp_att_names),
        "samples_att_renamed": smp_att_renamed,
        "samples_att_count_mismatch": smp_att_count_mismatch,
        "samples_noise_any": smp_noise_any,
        "samples_noise_heavy": smp_noise_heavy,
        "samples_positive": sum(
            1 for it in smp_recs
            if (it.get("fields") or {}).get("分类") == "正例"),
        # ── 2026-10-20 挖深：这张表是聊天转录，不是判例库 ──
        "samples_reviewer_is_forwarder": smp_reviewer_is_forwarder,
        "samples_audit_is_request": smp_audit_is_request,
        "samples_request_no_verdict": smp_request_no_verdict,
        # ── 品牌层（2026-10-20）：此前没有任何缺口编号的那一层 ──
        "brand_control_points": brand["控制点_品牌族"],
        "brand_control_empty_families": brand.get("控制点_空族"),
        "brand_axis_rules": brand["七轴_BRAND_条数"],
        "brand_engine_rules": brand["引擎品牌规则数"],
        "brand_asset_files": brand_asset["files"],
        "brand_asset_files_missing": brand_asset["missing"],
        "ext_entries": len(ext_doc.get("entries", [])),
        "ext_ratified": sum(1 for e in ext_doc.get("entries", [])
                            if e.get("status") == "ratified"),
        # ── B3.5：外部标准库落盘后，KB-GAP-10–KB-GAP-14 的「量」也必须能重算 ──
        #   缺口的数字一旦是手写的，它就会和制品脱钩。这里全部从制品算出来。
        "sources_meta": _n_src(ext_doc, "meta.com"),
        "entries_meta": _n_ent(ext_doc, "meta.com"),
        "sources_tiktok": _n_src(ext_doc, "tiktok.com"),
        "entries_tiktok": _n_ent(ext_doc, "tiktok.com"),
        "sources_eu": _n_src(ext_doc, "europa.eu"),
        "sources_uk": _n_src(ext_doc, "gov.uk") + _n_src(ext_doc, "asa.org.uk"),
        "entries_blank": sum(1 for e in ext_doc.get("entries", [])
                             if not (e.get("关联规则") or [])),
        "entries_total": len(ext_doc.get("entries", [])),
        "families": len(ext_doc.get("候选规则族") or []),
        "rules_total": _real_rules(rules_p),
        "rules_only_general": _only_general(ext_doc, rules_p),
        "materials_total": len(mat.MATERIALS),
        "materials_readable": readable,
        "materials_unreadable": len(mat.MATERIALS) - readable,
        "kb_lex_rules": n_rules,
        "kb_prod_readable": prod_readable,
        "ads_total": len(ads),
        "ads_with_text": len(ads) - len(no_text_raw),
        "ads_no_text": len(no_text),
        # 整行没读到（不是「无文案广告」）—— 与上面分开，见 no_text 处的注释
        "ads_unread": len(unread),
        "ads_no_text_marked_green": sum(1 for x in no_text if "绿" in str(x.get("风险等级"))),
        "ads_no_text_spend_usd": round(sum(_spend(x) for x in no_text), 2),
        "ads_total_spend_usd": round(sum(_spend(x) for x in ads), 2),
        # ── KB-GAP-9 扩大口径后要用的键（源表「合规·绿」的真实构成）──────────
        #   数字只有一个家：research/governance/skeleton/_data/风险等级-还原.json。
        #   这里不重算，只转发 —— 重算一遍就是把同一个数写在两处，正是本文件要防的。
        "risk_green": rl_t.get("绿标_条数"),
        "risk_green_spend_usd": rl_t.get("绿标_投放USD"),
        "risk_green_no_text": rl_t.get("绿标_无文案"),
        "risk_green_uncovered": rl_t.get("绿标_规则未覆盖"),
        "risk_green_uncovered_spend_usd": rl_t.get("绿标_规则未覆盖USD"),
        "risk_green_rule_hit": rl_t.get("绿标_规则命中了"),
        "risk_uncovered": rl_t.get("覆盖_未覆盖"),
        "risk_covered": rl_t.get("覆盖_覆盖"),
        "risk_blind_spot_rate": rl_t.get("盲区率"),
        # ── KB-GAP-15/KB-GAP-16 的键（迁移保真度对账）────────────────────────────
        #   同上：数字只有一个家 —— _data/迁移保真度.json，这里只转发。
        "legacy_exception_words": mf_t.get("旧豁免词总数"),
        "exception_self_triggering": mf_t.get("自我触发豁免词"),
        "exception_still_pass": mf_t.get("仍放行"),
        "exception_now_downgrade": mf_t.get("变成降级"),
        "exception_full_severity": mf_t.get("满档判险_无带"),
        "regression_false_positives": mf_t.get("分歧_迁移回归_假阳性"),
        "scan_drift_records": mf_t.get("逐行分歧"),
        "scan_pairs_agree": (mf.get("轴3_逐行对账") or {}).get("两次扫描一致"),
        "orphan_keywords": mf_t.get("无归属关键词"),
        "src_fragments_total": (mf.get("轴4_语料完备性") or {}).get("片段总数"),
        "src_fragments_not_in_corpus": mf_t.get("源表自报片段_语料里找不到"),
        "src_fragments_missing_records": (mf.get("轴4_语料完备性") or {}).get("受影响记录数"),
        "kb_classes_ready": sum([
            len(ext_doc.get("entries", [])) > 0,
            (len(smp_recs) - smp_marked) > 0,
            n_rules > 0,
            prod_readable > 0,
        ]),
        "kb_classes_total": 4,
    }
    f["done_no_deliverable_pct"] = (f["done_no_deliverable"] / f["done"]) if f["done"] else 0.0
    f["no_evidence_pct"] = (f["demands_without_evidence"] /
                            (f["demands_with_evidence"] + f["demands_without_evidence"])
                            if (f["demands_with_evidence"] + f["demands_without_evidence"]) else 0.0)
    return f


def render(f):
    """把事实渲染成 README 的生成块。**散文里不再复述这些数字。**"""
    L = [
        BEGIN,
        "",
        f"> 下表由 `python3 tools/kb_facts.py` 生成，基准日 = 快照日 "
        f"`{f['basis_date']}`（**不是今天**）。"
        "改数字的唯一方式是改数据，然后重跑本脚本。",
        "",
        "| 项 | 读数 |",
        "|---|---|",
        f"| 源系统 | {f['source_systems']} 套（creative / seo），"
        f"{f['source_tables']} 张表（另 {f['source_tables_excluded']} 张含敏感字段整体排除）"
        f"，其中 **{f['source_tables_in_ledger']} 张**进台账 |",
        f"| 源记录 | **{f['source_records']} 条**，可见性缺口 **{f['visibility_gaps']}** |",
        f"| 台账 | **{f['ledger_total']} 条** = 顶层 **{f['ledger_top']}** + "
        f"WBS 子任务 **{f['ledger_child']}** |",
        f"| 在跑 | **{f['in_flight']} 条** |",
        f"| 疑似逾期 | **{f['overdue']} 条**（仅在有计划完成日期的 {f['due_dated']} 条上可算） |",
        f"| 已完成无产出物记录 | **{f['done_no_deliverable']} / {f['done']}**"
        f"（{f['done_no_deliverable_pct']:.0%}） |",
        f"| 跨系统重复 | **{f['cross_table_dups']} 条** |",
        f"| 本地证据覆盖品线 | **{f['lines_with_evidence']} / {f['lines_total']}**"
        f"（只有吸奶器） |",
        f"| 零证据品线需求 | **{f['demands_without_evidence']} 条**"
        f"（{f['no_evidence_pct']:.0%}） |",
        f"| 材料收集可程序读取 | **{f['materials_readable']} / {f['materials_total']}**"
        f"（不可读 {f['materials_unreadable']}） |",
        f"| 4 类知识库有货的 | **{f['kb_classes_ready']} / {f['kb_classes_total']}**"
        f"（外部标准库 {f['ext_entries']} 条 · 真实样本 {f['samples_real']} 条 · "
        f"规则 {f['kb_lex_rules']} 条 · 产品材料可读 {f['kb_prod_readable']} 条） |",
        "",
        END,
    ]
    return "\n".join(L)


def splice(text, block):
    """把生成块换进 README。块不存在时硬失败 —— 不猜该插在哪。"""
    if BEGIN not in text or END not in text:
        raise SystemExit(f"[kb_facts] 硬失败：{os.path.relpath(README, load.REPO)} "
                         f"里找不到生成块标记 {BEGIN} … {END}")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return head + block + tail


def current_block(text):
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    return m.group(0) if m else None


def main():
    check = "--check" in sys.argv
    f = compute()
    block = render(f)
    text = open(README, encoding="utf-8").read()
    on_disk = current_block(text)
    if on_disk == block:
        print(f"✅ README 事实块与重算一致（基准日 {f['basis_date']}）")
        return 0
    if check:
        print("❌ README 事实块与重算不一致 —— 文档里的数字已经和台账脱钩。")
        print("   修复：python3 tools/kb_facts.py")
        if on_disk is None:
            print("   盘上根本没有生成块标记。")
        else:
            import difflib
            for line in list(difflib.unified_diff(on_disk.splitlines(), block.splitlines(),
                                                  "盘上", "重算", lineterm=""))[:40]:
                print("   " + line)
        return 1
    # ★ 先把新全文算出来，再开文件写 —— 顺序反了会**先截断再报错**。
    #   本脚本第一版就是这样：`open(README,"w").write(splice(...))` 里
    #   `open(...,"w")` 先求值（文件当场被截成 0 字节），随后 `splice` 抛
    #   「找不到生成块」，于是 README 被清空且没人报错。见 B3.0 复盘。
    new_text = splice(text, block)
    open(README, "w", encoding="utf-8").write(new_text)
    print(f"✅ 已写回 {os.path.relpath(README, load.REPO)} 的事实块"
          f"（基准日 {f['basis_date']}）")
    for k in ("ledger_total", "in_flight", "overdue", "materials_readable"):
        print(f"   {k} = {f[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
