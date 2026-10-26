#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lark_progress.py — 把「每次改动完成就更新事项主表」变成可执行的东西

## 为什么要有这个工具，而不是每次手点

委托方 2026-10-26 的要求原话是「今后的每次改动完成之后，都要在多维表格的
对应表单里面更新-新增对应的条目以及状态」。

这句话如果不落成一个命令，它就是**一句没有执行点的承诺** ——
而 AGENTS.md §2.4.2 点名的正是这个病：「写下一句承诺，没有任何东西在执行它」。
本项目已经因为「说了会做、但盘上没有一行代码在做」栽过一次（PRD 基线漂移）。

所以本工具做三件事：

  1. **新增/更新一条事项**：按事项编号 upsert（有则更新、无则新增），
     幂等 —— 同一张票跑两次不会产生两条记录。
  2. **默认 dry-run**：不加 `--apply` 只打印将要写什么。
     写入是对外动作，必须先看得见再决定。
  3. **不许冒充已验收**：`验收结论` 只接受表里已有的枚举，
     且「未测」不许被写成「通过」—— 这个判断由 `--verdict` 的取值域守住。

## 与「这张表是什么」的关系（重要，别搞错）

这张表是**内容审核工作台的页面级事项表**（`功能一级分类` 全是 P-01…P-12 与
「跨页面公共能力」），不是票据台账。所以：

* 页面上可见的功能 → 归到对应的 P-xx
* 后端/工程类能力（不支持任何单个页面看）→ 归「跨页面公共能力」，
  `页面路由` 写「全站」—— 表里已有先例（WBPM-0085）。

## 凭据

读 `~/.dsh/credentials/shouheng-lark.json`（与 `tools/lark_*.py` 同一份，
仓外 0700）。本文件不引入第二份凭据路径。

## 用法

    # 看一眼将写什么（默认 dry-run，不发写入请求）
    python3 tools/lark_progress.py --item "T-430 收敛覆盖率声明" \\
        --ticket T-430 --status 已完成 --verdict 通过 ...

    # 真写
    python3 tools/lark_progress.py --apply ...

    # 从一份 JSON 批量（每条都走同一套校验）
    python3 tools/lark_progress.py --apply --file PMO/表格同步/20261026.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

BASE_URL = "https://open.feishu.cn/open-apis"
CRED = os.path.expanduser("~/.dsh/credentials/shouheng-lark.json")

#: 目标表（委托方 2026-10-26 指定）
APP_TOKEN = "LY2ZbeXAcaktSEsVoACcSasKnzb"
TABLE_ID = "tblfZ8z8CGqGfz9c"

#: 表里**已有**的枚举。★ 只许用这里列出的值。
#: 往单选字段写一个不存在的选项，飞书会**静默新建选项** —— 于是表里会出现
#: 一个「看起来正常但没人定义过」的状态，统计立刻失真。所以本工具在写之前
#: 先读真实字段定义（`fetch_fields`），不拿这份清单当唯一真相。
KNOWN = {
    "完成状态": ["待核对", "未开始", "进行中", "待联调", "待验收",
                 "已完成", "已暂停", "已取消"],
    "验收结论": ["未测", "部分通过", "不通过", "通过", "证据冲突"],
    "上线状态": ["未核验", "未上线", "待上线", "试运行", "已上线",
                 "已回滚", "不适用"],
    "阻塞状态": ["待核实", "无阻塞", "已阻塞"],
    "排期确认状态": ["未估算", "建议待确认", "已确认", "需重排"],
    "优先级": ["未定", "P0 发布阻断", "P1 核心闭环", "P2 重要完善", "P3 优化"],
    "交付范围": ["范围待确认", "上线最小集", "产品完整集", "后续候选"],
    "工作类型": ["产品确认", "前端", "后端", "规则与知识库", "模型与解析",
                 "安全权限", "测试验收", "部署运维"],
}


class TableError(RuntimeError):
    """飞书返回非 0 code，或凭据/网络问题。"""


# ──────────────────────────────────────────────────────────────────────
# HTTP：与 tools/lark_find.py 同一形状（本仓既有做法）
# ──────────────────────────────────────────────────────────────────────

def _req(url: str, token: Optional[str] = None,
         payload: Any = None) -> Dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_http": exc.code, "body": exc.read().decode()[:600]}
    except Exception as exc:  # noqa: BLE001
        return {"_err": "%s: %s" % (type(exc).__name__, exc)}


def token() -> str:
    if not os.path.exists(CRED):
        raise TableError(
            "凭据不存在：%s（仓外 0700；本工具不读别的路径）" % CRED)
    cred = json.load(open(CRED))
    got = _req(BASE_URL + "/auth/v3/tenant_access_token/internal", None,
               {"app_id": cred["app_id"], "app_secret": cred["app_secret"]})
    if got.get("code") != 0:
        raise TableError("取 token 失败：%r" % (got,))
    return got["tenant_access_token"]


def fetch_fields(tok: str) -> Dict[str, Dict[str, Any]]:
    """读真实字段定义。返回 {字段名: 字段对象}。

    ★ 必须读真值而不是用 `KNOWN` 常量：那张常量是我抄的，
      而表可以被别人改。用常量判「选项合法」等于拿旧地图找新路。
    """
    got = _req("%s/bitable/v1/apps/%s/tables/%s/fields?page_size=100"
               % (BASE_URL, APP_TOKEN, TABLE_ID), tok)
    if got.get("code") != 0:
        raise TableError("读字段失败：%r" % (got,))
    out = {}
    for field in (got.get("data") or {}).get("items") or []:
        out[field.get("field_name")] = field
    return out


def fetch_records(tok: str, *, page_size: int = 500) -> List[Dict[str, Any]]:
    """拉全表记录（本表 94 条，远小于上限，一次拉完）"""
    items: List[Dict[str, Any]] = []
    page_token = ""
    while True:
        url = ("%s/bitable/v1/apps/%s/tables/%s/records?page_size=%d"
               % (BASE_URL, APP_TOKEN, TABLE_ID, page_size))
        if page_token:
            url += "&page_token=" + page_token
        got = _req(url, tok)
        if got.get("code") != 0:
            raise TableError("读记录失败：%r" % (got,))
        data = got.get("data") or {}
        items.extend(data.get("items") or [])
        page_token = data.get("page_token") or ""
        if not data.get("has_more") or not page_token:
            break
    return items


# ──────────────────────────────────────────────────────────────────────
# 校验
# ──────────────────────────────────────────────────────────────────────

def validate(item: Dict[str, Any],
             fields: Dict[str, Dict[str, Any]]) -> List[str]:
    """写之前逐项校验。返回问题清单（空 = 可写）。

    ★ 这里不许有「拿不准就放过」。飞书对单选字段写未知值会**静默新建选项**，
      所以每一条取值都要对着**真实字段定义**核一遍。
    """
    problems: List[str] = []
    name = (item.get("事项名称") or "").strip()
    if not name:
        problems.append("缺「事项名称」（表的主字段，必填）")
    if not (item.get("事项编号") or "").strip():
        problems.append("缺「事项编号」（upsert 的键，必填）")
    # ★ 功能一级分类是这张表的归类主轴，缺了它这一行就落不到任何页面维度上。
    #   第一版写成 `not in fields`（即「表里没有这个字段」），
    #   而实际要判的是「这一条**没填**这个字段」—— 两件事完全不同。
    if not (item.get("功能一级分类") or "").strip():
        problems.append("缺「功能一级分类」—— 这张表靠它归类，不许空")

    for key, value in item.items():
        if value is None or value == "" or value == []:
            continue
        field = fields.get(key)
        if field is None:
            problems.append("表里没有字段 %r —— 拼写错了？" % key)
            continue
        # 单选 / 多选：逐值核真实选项
        if field.get("type") in (3, 4):
            opts = {o["name"] for o in
                    ((field.get("property") or {}).get("options") or [])}
            values = value if isinstance(value, list) else [value]
            for one in values:
                if one not in opts:
                    problems.append(
                        "%s 的取值 %r 不在该字段已有选项里（写进去会静默新建选项）"
                        % (key, one))
        # 数字
        if field.get("type") == 2 and not isinstance(value, (int, float)):
            problems.append("%s 必须是数字，收到 %r" % (key, value))
        # 复选框
        if field.get("type") == 7 and not isinstance(value, bool):
            problems.append("%s 必须是布尔，收到 %r" % (key, value))

    # ★ 语义校验：「未测」不许配「已完成」。
    #   这不是格式问题：一条「验收结论=未测」的事项被标成「已完成」，
    #   表就读成了「做完了且没问题」，而实际上没人验收过。
    status = item.get("完成状态")
    verdict = item.get("验收结论")
    if status == "已完成" and verdict in ("未测", None):
        problems.append(
            "完成状态=已完成 但验收结论=%r —— 没验收过的事不许标已完成"
            "（要么补证据把结论写清，要么把完成状态降成待验收）" % (verdict,))
    return problems


# ──────────────────────────────────────────────────────────────────────
# upsert
# ──────────────────────────────────────────────────────────────────────

def find_by_number(records: List[Dict[str, Any]],
                   number: str) -> Optional[Dict[str, Any]]:
    for rec in records:
        if (rec.get("fields") or {}).get("事项编号") == number:
            return rec
    return None


def next_number(records: List[Dict[str, Any]]) -> str:
    """下一个 WBPM-xxxx。★ 从**现有最大号 +1**，不数条数 ——
    删过一条之后按条数算会撞号。"""
    best = 0
    for rec in records:
        raw = (rec.get("fields") or {}).get("事项编号") or ""
        if not str(raw).startswith("WBPM-"):
            continue
        try:
            best = max(best, int(str(raw).split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return "WBPM-%04d" % (best + 1)


def upsert(tok: str, item: Dict[str, Any], *,
           records: List[Dict[str, Any]], dry_run: bool) -> Dict[str, Any]:
    """有则更新、无则新增。返回 {action, number, record_id?}。"""
    number = item["事项编号"]
    existing = find_by_number(records, number)
    if existing:
        if dry_run:
            return {"action": "would_update", "number": number,
                    "record_id": existing.get("record_id")}
        got = _req("%s/bitable/v1/apps/%s/tables/%s/records/%s"
                   % (BASE_URL, APP_TOKEN, TABLE_ID, existing["record_id"]),
                   tok, {"fields": item})
        if got.get("code") != 0:
            raise TableError("更新失败：%r" % (got,))
        return {"action": "updated", "number": number,
                "record_id": existing.get("record_id")}
    if dry_run:
        return {"action": "would_create", "number": number}
    got = _req("%s/bitable/v1/apps/%s/tables/%s/records"
               % (BASE_URL, APP_TOKEN, TABLE_ID), tok, {"fields": item})
    if got.get("code") != 0:
        raise TableError("新增失败：%r" % (got,))
    record = (got.get("data") or {}).get("record") or {}
    return {"action": "created", "number": number,
            "record_id": record.get("record_id")}


def _text(item: Dict[str, Any]) -> str:
    """dry-run 的可读预览（只列非空字段，按字段顺序）。"""
    lines = []
    for key in ("事项编号", "事项名称", "功能一级分类", "功能二级分类",
                "功能三级分类", "工作类型", "完成状态", "验收结论",
                "上线状态", "阻塞状态", "页面路由", "关联执行票",
                "状态依据", "验收标准", "下一步行动"):
        if key in item and item[key] not in (None, "", []):
            value = item[key]
            if isinstance(value, list):
                value = "、".join(str(v) for v in value)
            lines.append("    %-8s %s" % (key, value))
    return "\n".join(lines)


def _usage():
    print("用法：")
    print("  python3 tools/lark_progress.py --selftest     # 离线自证（不联网、不读凭据）")
    print("  python3 tools/lark_progress.py --file <json> [--apply]")
    print("  python3 tools/lark_progress.py --item <名称> --category <分类> ...")


# ──────────────────────────────────────────────────────────────────────
# --selftest：离线自证（§2.4 要求「上限必须有执行点」，这里给判据本身执行点）
#
# ★ 为什么必须有这一段：`lark_progress.py` 是「每次改动完成就同步表格」这条
#   承诺的**唯一执行点**。而它自己如果写错了 —— 比如把「未测」放行成
#   「已完成」、或者写一个不存在的选项进单选字段 —— 后果是**表里出现假的进度**，
#   而表是共享的、别人会照着它排期。
#
# ★ 这段**一次网络都不发、一次凭据都不读**：所有判据喂的是手造的字段定义与记录。
#   与 `verify_multimodal_client` 同一条规矩：验收动作本身不许有副作用（§2.4.4）。
# ──────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    ok = bad = 0

    def C(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            bad += 1
            print("  ❌ %s  %s" % (name, detail))

    # 手造字段定义（与真实表的形状一致：type 3=单选、4=多选、2=数字、7=复选框）
    fields = {
        "事项名称": {"field_name": "事项名称", "type": 1},
        "事项编号": {"field_name": "事项编号", "type": 1},
        "功能一级分类": {"field_name": "功能一级分类", "type": 3,
                        "property": {"options": [{"name": "跨页面公共能力"},
                                                 {"name": "P-01 提交内容审查"}]}},
        "工作类型": {"field_name": "工作类型", "type": 4,
                     "property": {"options": [{"name": "后端"}, {"name": "前端"}]}},
        "完成状态": {"field_name": "完成状态", "type": 3,
                     "property": {"options": [{"name": "进行中"},
                                              {"name": "待验收"},
                                              {"name": "已完成"}]}},
        "验收结论": {"field_name": "验收结论", "type": 3,
                     "property": {"options": [{"name": "未测"}, {"name": "通过"},
                                              {"name": "部分通过"}]}},
        "预估工作量（人日）": {"field_name": "预估工作量（人日）", "type": 2},
        "验收清单已确认": {"field_name": "验收清单已确认", "type": 7},
    }
    base = {"事项名称": "某事项", "事项编号": "WBPM-0001",
            "功能一级分类": "跨页面公共能力", "完成状态": "待验收",
            "验收结论": "未测"}

    # ── 正向：合法条目必须通过 ────────────────────────────────────
    C("S1 合法条目 → 0 问题", validate(dict(base), fields) == [],
      repr(validate(dict(base), fields)))

    # ── 反向：每条判据各喂一个坏样本 ──────────────────────────────
    cases = (
        ("S2 ★ 缺事项名称 → 红",
         {k: v for k, v in base.items() if k != "事项名称"}),
        ("S3 ★ 缺事项编号 → 红",
         {k: v for k, v in base.items() if k != "事项编号"}),
        ("S4 ★ 缺功能一级分类 → 红（这张表靠它归类）",
         {k: v for k, v in base.items() if k != "功能一级分类"}),
        ("S5 ★★ 单选写不存在的选项 → 红（会静默新建选项）",
         dict(base, 完成状态="已搞定")),
        ("S6 ★★ 多选里混一个不存在的选项 → 红",
         dict(base, 工作类型=["后端", "不存在的工种"])),
        ("S7 ★ 字段名拼错 → 红（否则会静默丢弃）",
         dict(base, **{"完成壮态": "待验收"})),
        ("S8 ★★ 验收结论=未测 却标已完成 → 红（没验收过不许说完成）",
         dict(base, 完成状态="已完成", 验收结论="未测")),
        ("S9 ★ 已完成但验收结论缺失 → 红",
         {k: v for k, v in dict(base, 完成状态="已完成").items()
          if k != "验收结论"}),
        ("S10 数字字段给字符串 → 红",
         dict(base, **{"预估工作量（人日）": "八天"})),
        ("S11 复选框给字符串 → 红",
         dict(base, 验收清单已确认="yes")),
    )
    for name, item in cases:
        problems = validate(item, fields)
        C(name, bool(problems), "0 问题（判据没抓住）")

    # ── 反向对照：证明上面不是恒红 ────────────────────────────────
    C("S12 ★ 反证：已完成 + 验收结论=通过 → 不许红",
      validate(dict(base, 完成状态="已完成", 验收结论="通过"), fields) == [],
      repr(validate(dict(base, 完成状态="已完成", 验收结论="通过"), fields)))
    C("S13 ★ 反证：已完成 + 部分通过 → 也不许红（部分通过是验收过的）",
      validate(dict(base, 完成状态="已完成", 验收结论="部分通过"), fields) == [])

    # ── 编号分配：从最大号 +1，不按条数 ──────────────────────────
    recs = [{"fields": {"事项编号": "WBPM-0003"}},
            {"fields": {"事项编号": "WBPM-0009"}},
            {"fields": {"事项编号": "WBPM-0001"}}]
    C("S14 ★ 下一个编号 = 最大号 +1（不是条数 +1）",
      next_number(recs) == "WBPM-0010", next_number(recs))
    # ★ 删过一条之后按条数算会撞号 —— 这一条是那个坑的执行点
    C("S15 ★★ 删掉中间一条后仍取最大号 +1（按条数算会撞号）",
      next_number([{"fields": {"事项编号": "WBPM-0003"}},
                   {"fields": {"事项编号": "WBPM-0009"}},
                   {"fields": {"事项编号": "WBPM-0008"}}]) == "WBPM-0010")

    # ── upsert：有则更新、无则新增 ────────────────────────────────
    existing = [{"record_id": "rec-1", "fields": {"事项编号": "WBPM-0001"}}]
    plan = upsert(None, dict(base), records=existing, dry_run=True)
    C("S16 ★ 编号已存在 → would_update（幂等，不产生第二条）",
      plan["action"] == "would_update" and plan["record_id"] == "rec-1",
      repr(plan))
    plan2 = upsert(None, dict(base, 事项编号="WBPM-9999"),
                   records=existing, dry_run=True)
    C("S17 编号不存在 → would_create", plan2["action"] == "would_create",
      repr(plan2))
    # ★ dry-run 不许有副作用：token 传 None，真发请求一定炸 —— 没炸就证明没发
    C("S18 ★★ dry-run 不发请求（token=None 也不炸，证明真的没发）",
      plan["action"].startswith("would_"))

    print("-" * 74)
    if bad:
        print("❌ %d 过 · %d 红" % (ok, bad))
        return 1
    print("✅ %d/%d 全过（离线，0 网络请求、0 凭据读取）" % (ok, ok))
    return 0


def main(argv: Sequence[str]) -> int:
    if "--selftest" in argv:
        print("=" * 74)
        print("lark_progress.py · 离线自证（不联网、不读凭据）")
        print("=" * 74)
        return _selftest()

    ap = argparse.ArgumentParser(
        description="把一条改动同步进飞书「事项主表」（默认 dry-run）")
    ap.add_argument("--file", help="JSON：单条对象或对象数组")
    ap.add_argument("--item", help="事项名称")
    ap.add_argument("--number", help="事项编号（不给则自动取下一个）")
    ap.add_argument("--ticket", help="关联执行票，如 T-430")
    ap.add_argument("--category", help="功能一级分类")
    ap.add_argument("--sub2", help="功能二级分类")
    ap.add_argument("--sub3", help="功能三级分类")
    ap.add_argument("--work-types", help="工作类型，逗号分隔")
    ap.add_argument("--status", help="完成状态")
    ap.add_argument("--verdict", help="验收结论")
    ap.add_argument("--release", help="上线状态")
    ap.add_argument("--blocker", help="阻塞状态")
    ap.add_argument("--route", help="页面路由")
    ap.add_argument("--detail", help="事项明细")
    ap.add_argument("--basis", help="状态依据")
    ap.add_argument("--acceptance", help="验收标准")
    ap.add_argument("--next-step", help="下一步行动")
    ap.add_argument("--blocker-reason", help="阻塞原因")
    ap.add_argument("--apply", action="store_true",
                    help="真写（不加则只打印将写什么）")
    args = ap.parse_args(argv)

    # 收集待写条目
    if args.file:
        raw = json.load(open(args.file, encoding="utf-8"))
        items = raw if isinstance(raw, list) else [raw]
    else:
        if not args.item:
            ap.print_help()
            return 1
        one: Dict[str, Any] = {"事项名称": args.item}
        pairs = (
            ("事项编号", args.number), ("关联执行票", args.ticket),
            ("功能一级分类", args.category), ("功能二级分类", args.sub2),
            ("功能三级分类", args.sub3), ("完成状态", args.status),
            ("验收结论", args.verdict), ("上线状态", args.release),
            ("阻塞状态", args.blocker), ("页面路由", args.route),
            ("事项明细", args.detail), ("状态依据", args.basis),
            ("验收标准", args.acceptance), ("下一步行动", args.next_step),
            ("阻塞原因", args.blocker_reason),
        )
        for key, value in pairs:
            if value:
                one[key] = value
        if args.work_types:
            one["工作类型"] = [w.strip() for w in args.work_types.split(",")
                              if w.strip()]
        items = [one]

    try:
        tok = token()
        fields = fetch_fields(tok)
        records = fetch_records(tok)
    except TableError as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 2

    print("=" * 74)
    print("飞书事项主表同步 · %s" % ("**真写**" if args.apply else "dry-run（不写）"))
    print("  Base: %s  表: %s（%d 条现有记录）"
          % (APP_TOKEN, TABLE_ID, len(records)))
    print("=" * 74)

    problems_all: List[str] = []
    planned: List[Tuple[Dict[str, Any], str]] = []
    for item in items:
        item = dict(item)
        if not item.get("事项编号"):
            # ★ 自动编号只在本批**第一条**没有编号时发生；多条时逐条递增，
            #   避免同批撞号（先按现有最大号分配，再在内存里递增记下已分配）。
            item["事项编号"] = next_number(
                records + [{"fields": {"事项编号": n}} for _, n in planned])
        issues = validate(item, fields)
        problems_all.extend(issues)
        planned.append((item, item["事项编号"]))
        print("\n  [%s] %s" % (item["事项编号"], item.get("事项名称")))
        print(_text(item))
        if issues:
            for issue in issues:
                print("    ❌ %s" % issue)

    if problems_all:
        print("\n❌ 有 %d 项校验问题 —— 一条都不写" % len(problems_all))
        return 1

    results = []
    for item, _number in planned:
        try:
            results.append(upsert(tok, item, records=records,
                                   dry_run=not args.apply))
        except TableError as exc:
            print("\n❌ 写入失败：%s" % exc, file=sys.stderr)
            return 2

    print("\n" + "-" * 74)
    for res in results:
        print("  %-14s %s  %s" % (res["action"], res["number"],
                                  res.get("record_id") or ""))
    if not args.apply:
        print("\n  ★ 这是 dry-run。确认无误后加 --apply 真写。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
