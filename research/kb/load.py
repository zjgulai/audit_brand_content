#!/usr/bin/env python3
"""
需求知识库 · 唯一装载层（single loader）

所有读取快照的脚本**必须**经过本模块。禁止在别处直接 `json.load(快照)`。

三条硬规则（见 `research/kb/需求知识库-建设方案.md` §4.2）：

  1. **路径与结构异常一律硬失败**（SystemExit），绝不降级为"空数据继续跑"。
     知识库的消费者是人，一个静默算错的数字比一次崩溃危险得多。

  2. **时间戳一律按 Asia/Shanghai 解读**。飞书存的是「北京零点」对应的 UTC 偏移
     （实测 `1785340800000` → UTC `2026-07-29 16:00` / +08 `2026-07-30 00:00`）。
     用 UTC 读会让所有日期整体早一天 —— 这是本项目最容易踩且最难发现的坑。

  3. **可见性缺口必须显式暴露**。应用身份读到的是被权限过滤后的子集；
     `reported_total != fetched` 时导出 `visibility_gaps()`，调用方必须处理，
     不得当成"数据就是这些"。

用法：
    import sys; sys.path.insert(0, "research/kb")
    import load
    snap = load.snapshot()                 # 最近一次快照
    for t in snap.demand_tables(): ...     # 需求类表
    load.flat(rec["fields"].get("品线"))
    load.as_date(rec["fields"].get("提需日期"))
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# research/kb/load.py → 上溯三层才是仓库根
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(REPO, "research", "kb")
EVIDENCE = os.path.join(KB, "_evidence")
LATEST = os.path.join(EVIDENCE, "LATEST.json")

CST = timezone(timedelta(hours=8))

# 表性质分类。这里只放**结构性事实**（这张表是什么），不放业务判断。
# 单张表的纳入/排除与字段映射写在 schema-v1.json 里，便于评审。
KIND = {
    ("creative", "【视频】日常需求看板"): "demand",
    ("creative", "【平面】日常需求看板"): "demand",
    ("creative", "【创意支持】项目需求"): "demand",
    ("creative", "【创意UGC】提需表"): "demand",
    ("creative", "【红人&社媒】支持"): "empty",
    ("creative", "国庆前后 考勤值班计划"): "admin",
    ("creative", "产品字典"): "dimension",
    ("creative", "优质素材-语言拓展"): "empty",
    ("creative", "样品库"): "asset",
    ("creative", "产品x品线资料整理"): "empty",
    ("seo", "品线SEO任务管理系统"): "demand",
    ("seo", "英语站站内blog全表"): "content",
    ("seo", "英语站集合页及重要产品页"): "content",
    ("seo", "PSEO专家审核总表"): "review",
    ("seo", "UK站内容审核"): "review",
    ("seo", "费用结算管理"): "finance",
    ("seo", "infinity+adsy"): "finance",
}

# 需求台账的构成：需求 + 审核。审核是"外部专家要做的任务"，与内部需求同构。
LEDGER_KINDS = ("demand", "review")


def _die(msg: str):
    raise SystemExit(f"[load] 硬失败：{msg}")


# ───────────────────────── 标量归一 ─────────────────────────

def flat(v):
    """把飞书的字段值压成可读标量。

    飞书字段类型差异极大（文本 / 单选 / 多选 / 人员 / 日期 / 关联 / 附件），
    下游只关心「有没有值、值是什么」，所以统一压平：
      多选 → "; " 连接；对象 → 取 text/name/value/link；空串 → None
    """
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s or None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, list):
        out = [flat(x) for x in v]
        out = [x for x in out if x not in (None, "")]
        return "; ".join(str(x) for x in out) if out else None
    if isinstance(v, dict):
        for k in ("text", "name", "value", "link", "en_name"):
            if k in v and v[k] not in (None, ""):
                return flat(v[k])
        return json.dumps(v, ensure_ascii=False, sort_keys=True)[:200]
    return str(v)


def link_of(v):
    """解析飞书关联字段 → (父记录 id, 父记录标题)；无父返回 (None, None)。

    飞书关联字段的形态：`[{"record_ids": [...], "table_id": "...", "text": "父标题", ...}]`
    顶层记录（没有父）拿到的是 `[{"table_id": "...", "text_arr": [], "type": "text"}]` ——
    **字段填充率 100%，但它是空的**。只看填充率会把顶层项目误判成"都有父"，
    这是本项目已经踩过一次的坑（见 ADR-0010 §三）。
    """
    if not isinstance(v, list) or not v:
        return None, None
    for it in v:
        if not isinstance(it, dict):
            continue
        ids = it.get("record_ids") or it.get("link_record_ids") or []
        txt = it.get("text") or (it.get("text_arr") or [None])[0]
        if ids or txt:
            return (ids[0] if ids else None), (str(txt) if txt else None)
    return None, None


def as_date(v):
    """毫秒时间戳 → 'YYYY-MM-DD'（Asia/Shanghai）。非日期返回 None。"""
    if not isinstance(v, (int, float)) or v <= 0:
        return None
    # 10 位当秒、13 位当毫秒
    ms = v * 1000 if v < 1e11 else v
    try:
        return datetime.fromtimestamp(ms / 1000, CST).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def today():
    return datetime.now(CST).strftime("%Y-%m-%d")


def basis_date(snap=None):
    """**判据的基准日 = 快照日**，不是墙钟今天。

    为什么必须这样（B3.0 实测）：`q2` 原本用 `today()` 当基准日，于是同一条
    「可复现命令」在 09-16 打印「逾期 30 条」、在 09-17 打印「逾期 33 条」——
    手册里写的那个数，第二天就复现不出来了，而且没有任何东西会发现。

    区分两件事：
      · **快照**回答「数据长什么样」—— 是数据的属性，与何时提问无关；
      · **今天**回答「现在几点」—— 想知道今天的逾期，就重新拉一次快照。
    把两者混在一起，任何依赖日期的判据都会悄悄漂移，而漂移是单向的、不会自愈。

    本函数取快照 MANIFEST 的 `taken_at_utc`，按 Asia/Shanghai 落到日。
    快照时间戳缺失/不可解析 → 硬失败（宁可崩，也不要一个"看起来对"的基准日）。
    """
    if snap is None:
        snap = snapshot()
    try:
        dt = datetime.fromisoformat(str(snap.taken_at).replace("Z", "+00:00"))
    except ValueError:
        _die(f"快照 {snap.snapshot_id} 的 taken_at_utc 不可解析：{snap.taken_at!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CST).strftime("%Y-%m-%d")


def days_between(d1: str, d2: str):
    """两个 'YYYY-MM-DD' 之间的天数（d2 - d1）。"""
    a = datetime.strptime(d1, "%Y-%m-%d")
    b = datetime.strptime(d2, "%Y-%m-%d")
    return (b - a).days


# ───────────────────────── 快照 ─────────────────────────

class Table:
    __slots__ = ("system", "system_label", "name", "table_id", "fields", "records",
                 "reported_total", "fetched", "pages", "error", "sha256", "excluded", "reason")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def kind(self):
        return KIND.get((self.system, self.name), "unknown")

    @property
    def visibility_gap(self):
        """声明条数 - 实读条数。非 0 表示有看不见的记录。"""
        if self.reported_total is None:
            return None
        return self.reported_total - (self.fetched or 0)

    def values(self, field):
        return [flat(r["fields"].get(field)) for r in self.records]

    def nonempty(self, field):
        return [v for v in self.values(field) if v not in (None, "")]

    def fill(self, field):
        n = len(self.records)
        return (len(self.nonempty(field)) / n) if n else 0.0

    def __repr__(self):
        return f"<Table {self.system}:{self.name} {self.fetched}条 kind={self.kind}>"


class Snapshot:
    def __init__(self, dirpath):
        self.dir = dirpath
        self.manifest = json.load(open(os.path.join(dirpath, "MANIFEST.json"), encoding="utf-8"))
        self.snapshot_id = self.manifest["snapshot_id"]
        self.taken_at = self.manifest["taken_at_utc"]
        self.tables = {}
        for src in self.manifest["sources"]:
            for t in src["tables"]:
                if not t.get("included", True):
                    tb = Table(system=src["system"], system_label=src["label"], name=t["name"],
                               table_id=t["table_id"], fields=t.get("fields_seen", []),
                               records=[], reported_total=None, fetched=0, pages=0,
                               error=None, sha256=None, excluded=True, reason=t.get("reason"))
                    self.tables[(src["system"], t["name"])] = tb
                    continue
                f = os.path.join(dirpath, t["file"])
                if not os.path.exists(f):
                    _die(f"MANIFEST 指向的表文件不存在：{t['file']}")
                payload = json.load(open(f, encoding="utf-8"))
                if payload.get("records_sha256") != t.get("records_sha256"):
                    _die(f"表文件与 MANIFEST 指纹不符：{t['file']}（快照可能被改动过）")
                tb = Table(system=src["system"], system_label=src["label"], name=t["name"],
                           table_id=t["table_id"], fields=payload["fields"],
                           records=payload["records"], reported_total=t.get("reported_total"),
                           fetched=t.get("fetched"), pages=t.get("pages"),
                           error=t.get("error"), sha256=t.get("records_sha256"),
                           excluded=False, reason=None)
                self.tables[(src["system"], t["name"])] = tb

    def __getitem__(self, key):
        if isinstance(key, str):
            hits = [t for k, t in self.tables.items() if k[1] == key]
            if len(hits) != 1:
                _die(f"表名 {key!r} 命中 {len(hits)} 张表，请用 (system, name) 消歧")
            return hits[0]
        return self.tables[key]

    def all(self):
        return list(self.tables.values())

    def by_kind(self, *kinds):
        return [t for t in self.tables.values() if t.kind in kinds]

    def ledger_tables(self):
        return self.by_kind(*LEDGER_KINDS)

    def visibility_gaps(self):
        out = []
        for t in self.tables.values():
            if t.excluded:
                continue
            if t.error:
                out.append((t, f"读取失败：{t.error}"))
            elif t.visibility_gap:
                out.append((t, f"声明 {t.reported_total} 条，只读到 {t.fetched} 条"))
        return out


def snapshot(dirpath=None):
    """装载最近一次（或指定）快照。任何异常都硬失败。"""
    if dirpath is None:
        if not os.path.exists(LATEST):
            _die(f"找不到 {LATEST}。先跑：python3 tools/kb_snapshot.py")
        latest = json.load(open(LATEST, encoding="utf-8"))
        dirpath = os.path.join(REPO, latest["dir"])
    if not os.path.isdir(dirpath):
        _die(f"快照目录不存在：{dirpath}")
    if not os.path.exists(os.path.join(dirpath, "MANIFEST.json")):
        _die(f"快照目录缺少 MANIFEST.json：{dirpath}")
    return Snapshot(dirpath)


if __name__ == "__main__":
    s = snapshot()
    print(f"快照 {s.snapshot_id}  取于 {s.taken_at}")
    print(f"目录 {os.path.relpath(s.dir, REPO)}\n")
    for t in sorted(s.all(), key=lambda x: (x.system, x.name)):
        if t.excluded:
            print(f"  ⛔ {t.system:<9} {t.name:<26} 排除：{t.reason}")
        else:
            print(f"  {'✅'} {t.system:<9} {t.name:<26} {t.fetched:>5} 条  kind={t.kind}")
    gaps = s.visibility_gaps()
    print(f"\n可见性缺口：{len(gaps)} 处" + ("" if not gaps else ""))
    for t, why in gaps:
        print(f"  ⚠️ {t.name}: {why}")
