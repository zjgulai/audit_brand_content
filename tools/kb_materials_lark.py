#!/usr/bin/env python3
"""
kb_materials_lark.py —— 把「4 类知识库定义 + 材料收集 + 收集任务」落到飞书

业务侧在自己的知识库 Base 里已经**定义好了 4 类知识库**（含建议字段、负责人、
需向对接人收集的问题），但只填了 15 条材料、其中 11 条没有分类、正负样本 8 条里 7 条是样例。
本脚本把这份定义**实例化**到 app 自有的「需求知识库」Base，让它可被枚举、可被追踪。

三张表：
  · 知识库分类 —— 4 类的定义 + 本地现状（每类现在到底有没有货）
  · 材料收集   —— 15 条材料 + 逐条的**实测可读性**（这是本表最有价值的一列）
  · 收集任务   —— 把业务侧写好的「需向对接人收集的问题」变成带负责人和状态的待办

★ 实测可读性为什么重要：15 条材料里只有 5 条能被以程序方式读取。
  材料收集表原本只记了「链接」，没记「这条链接我到底读不读得到」——
  于是看起来收集了 15 条，实际可用 5 条。**这个差必须被显示出来。**

用法：
  python3 tools/kb_materials_lark.py            # 预演
  python3 tools/kb_materials_lark.py --apply    # 建表 + 写入
  python3 tools/kb_materials_lark.py --apply --force
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "research" / "kb"
CRED = os.path.expanduser("~/.dsh/credentials/shouheng-lark.json")
API = "https://open.feishu.cn/open-apis"

T_TEXT = 1
STATE = KB / "_evidence" / "feishu-base.json"
TABLES = KB / "_evidence" / "feishu-tables.json"


def call(url, payload=None, token=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    r.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            return json.loads(x.read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "body": e.read().decode()[:400]}
    except Exception as e:                                    # noqa: BLE001
        return {"_err": f"{type(e).__name__}: {e}"}


def token():
    c = json.loads(Path(CRED).read_text())
    r = call(f"{API}/auth/v3/tenant_access_token/internal",
             {"app_id": c["app_id"], "app_secret": c["app_secret"]})
    return r["tenant_access_token"]


def txt(n):
    return {"field_name": n, "type": T_TEXT}


# ── 一、4 类知识库定义（逐字取自业务侧「知识库分类说明」表）+ 本地现状 ──
CATEGORIES = [
    {
        "知识库": "外部标准库",
        "要包含什么": "美国法规、平台政策、行业标准、医学共识、本地常识",
        "建议字段材料": "官方链接/PDF、条款、内部合规摘要、适用产品线、生效日期",
        "负责人": "法务 Sharon、专家 Emma、北美待定",
        "待收集问题": "已有政策/合规摘要？需覆盖哪些平台？哪些医学结论需专家确认？",
        "本地现有条目": "0 条结构化；仅有调研稿 R1-platform-policy-taxonomy（未结构化）",
        "状态": "空白",
        "缺口说明": "research/governance/R1 做了平台政策分类学研究，但没有产出可被工具调用的条款级条目",
    },
    {
        "知识库": "内部正面与负面样本库",
        "要包含什么": "正面：已通过且合规的优秀内容；负面：投诉、下架、警告、返工、达人争议、审核争议",
        "建议字段材料": "样本 ID、产品线、渠道、内容类型、原文/截图/视频、问题/亮点、风险等级、依据、处理结果、修改前后、是否可规则化",
        "负责人": "品牌张丽敏、吸奶器银舒涵、喂养 William、法务",
        "待收集问题": "各品线已有多少正/负样本？是否可外发？是否可脱敏？",
        "本地现有条目": "8 条，其中 7 条备注写「样例」→ 实质为 0 条真实样本",
        "状态": "空白",
        "缺口说明": "这是 Agent 训练素材的核心来源，也是最贵的一块。现有 8 条是模板示范，不是数据",
    },
    {
        "知识库": "措辞表达库",
        "要包含什么": "Do not say / Say this instead；禁用、慎用、推荐表达；中英对照；适用场景",
        "建议字段材料": "表达、类型、场景、依据、风险等级、替代表达、语言",
        "负责人": "品牌、法务、北美、专家",
        "待收集问题": "已有禁用词/推荐话术？哪些表达易被平台误判？",
        "本地现有条目": "规则 21 条 + 白名单 26 词 + 语境守卫 89 词 + 改写建议 52 条",
        "状态": "已有货但只覆盖 1 个品线",
        "缺口说明": "全部适用产品为吸奶器型号（W1/M5/M6/M9/Air1）。其余 7 个品线 0 条",
    },
    {
        "知识库": "产品描述库",
        "要包含什么": "功能边界、型号差异、允许/禁止描述、适用人群、使用场景、认证参数、常见误解",
        "建议字段材料": "产品线、型号、卖点、边界、禁止表述、认证、FAQ",
        "负责人": "吸奶器 Misty/银舒涵、喂养 William、品牌 Daisy/张丽敏、专家 Emma",
        "待收集问题": "各品线已有产品手册/卖点/认证？哪些描述容易越界？",
        "本地现有条目": "4 条材料已登记（吸奶器/婴幼儿/喂养产品信息汇总、婴幼儿基础信息）",
        "状态": "材料不可读",
        "缺口说明": "4 条材料**全部无法以程序方式读取**（131006/131005/1340213 权限错误），等于 0",
    },
]

# ── 二、材料收集 15 条 + 实测可读性 ──────────────────────────────────
# readability: ok=读得到 / perm=有对象但无权限 / bad=token 无效
MATERIALS = [
    {"编号": "1", "材料": "MOMCOZY吸奶器产品信息内容汇总", "类型": "wiki云文档",
     "token": "CUMOwJyo9iWNB7kfQMpc2LOSnAe", "来源人": "Emma",
     "归属": "产品描述库", "可读性": "perm", "说明": "wiki 节点存在但无权限"},
    {"编号": "2", "材料": "MOMCOZY婴幼儿品线产品信息内容汇总", "类型": "wiki云文档",
     "token": "EL1nw9zdyinX2iklXfLco216niM", "来源人": "Emma",
     "归属": "产品描述库", "可读性": "perm", "说明": "131006"},
    {"编号": "16", "材料": "MOMCOZY喂养品线产品信息内容汇总", "类型": "wiki云文档",
     "token": "F44LwhbAqiD0TVkaNqYcXeF2n5P", "来源人": "Emma",
     "归属": "产品描述库", "可读性": "perm", "说明": "131006"},
    {"编号": "4", "材料": "W1卖点匹配证据库_检索阅读版_0827更新", "类型": "wiki云文档",
     "token": "EsCdw2A7tiz67Rk8LgMce2TAnEh", "来源人": "Emma",
     "归属": "产品描述库", "可读性": "perm", "说明": "131006"},
    {"编号": "5", "材料": "吸奶器广告文案·品线内容边界风控", "类型": "多维表格",
     "token": "Lk3Qb8y2QaVyZns6gprcVNE9nA0", "来源人": "Misty",
     "归属": "措辞表达库", "可读性": "ok", "说明": "4 表 383 条，已提取至 PRD"},
    {"编号": "6", "材料": "【IMC跟进】W1再营销整合营销方案", "类型": "电子表格",
     "token": "BX0QshqWThhY6HtDEFCcnMpsnRc", "来源人": "Misty",
     "归属": "待分类", "可读性": "perm", "说明": "1310213 无查看权限"},
    {"编号": "7", "材料": "202608 营销内容生命周期内容合规审核规范建设-需求框架整理",
     "类型": "云文档(docx)", "token": "W2KodnZP3orVrAxxn5OcbmKtnxh", "来源人": "钱撷羽（Sharon）",
     "归属": "需求框架", "可读性": "ok",
     "说明": "★ 764 行，法务侧写给大数据与算法团队的完整需求框架，已存 materials/"},
    {"编号": "8", "材料": "【创意】需求排期与任务管理", "类型": "多维表格",
     "token": "OShmbLBaPam6YSsCzP0cNOyBn6f", "来源人": "Roxie",
     "归属": "任务系统", "可读性": "ok", "说明": "11 表 428 条，已进需求台账"},
    {"编号": "9", "材料": "广告创意跟进", "类型": "未知", "token": "XkSkfY4vkl0ARpdvRxNcyhYlnpd",
     "来源人": "Roxie", "归属": "任务系统", "可读性": "bad",
     "说明": "token 无效（131002），需重新取链接"},
    {"编号": "10", "材料": "品线SEO任务管理系统", "类型": "多维表格",
     "token": "DXJ6b5cKtaXPQasoayEc74SUnog", "来源人": "林建纯（Rikka）",
     "归属": "任务系统", "可读性": "ok", "说明": "7 表 2860 条，已进需求台账"},
    {"编号": "11", "材料": "英语站站点blog全表", "类型": "多维表格",
     "token": "shrcnxQyCVyh2NjffnaJf85dKLe", "来源人": "林建纯（Rikka）",
     "归属": "内容资产", "可读性": "bad", "说明": "token 无效（91402），需重新取链接"},
    {"编号": "12", "材料": "Breast Pump MarComms Claim Guidelines_CN-EN", "类型": "未知",
     "token": "LDIIsI5SIl4ZumdW8XgcUIn8nTg", "来源人": "Misty",
     "归属": "措辞表达库", "可读性": "bad", "说明": "131005，token 无效或已迁移"},
    {"编号": "13", "材料": "Breast Pump MarComms Claim Guidelines_EN", "类型": "未知",
     "token": "PtNesZDDdlMSc4dtczlcxPh6nAg", "来源人": "Misty",
     "归属": "措辞表达库", "可读性": "bad", "说明": "131005"},
    {"编号": "14", "材料": "婴幼儿品线_产品基础信息汇总", "类型": "电子表格",
     "token": "KzQ1sLVCbhFCIktRkdec9Onen6e", "来源人": "（未填）",
     "归属": "产品描述库", "可读性": "perm", "说明": "1310213 无查看权限"},
    {"编号": "15", "材料": "（空行）", "类型": "—", "token": "—", "来源人": "（未填）",
     "归属": "待分类", "可读性": "bad", "说明": "源表里的空行，无链接无内容"},
]

# ── 三、收集任务：把业务侧写好的问题变成带负责人和状态的待办 ──────────
TASKS = [
    ("外部标准库", "已有政策/合规摘要？需覆盖哪些平台？哪些医学结论需专家确认？",
     "法务 Sharon、专家 Emma、北美待定", "未启动",
     "本地 R1-platform-policy-taxonomy 有分类学研究，但没有条款级条目"),
    ("内部正面与负面样本库", "各品线已有多少正/负样本？是否可外发？是否可脱敏？",
     "品牌张丽敏、吸奶器银舒涵、喂养 William、法务", "未启动",
     "★ 优先级最高：8 条现有记录全是样例，这是 Agent 训练素材的核心来源"),
    ("措辞表达库", "已有禁用词/推荐话术？哪些表达易被平台误判？",
     "品牌、法务、北美、专家", "部分完成",
     "吸奶器已有 21 规则 + 26 白名单 + 89 语境守卫 + 52 改写建议；其余 7 品线为 0"),
    ("产品描述库", "各品线已有产品手册/卖点/认证？哪些描述容易越界？",
     "吸奶器 Misty/银舒涵、喂养 William、品牌 Daisy/张丽敏、专家 Emma", "未启动",
     "4 条材料已登记但全部不可读；且只覆盖吸奶器/婴幼儿/喂养，缺 5 个品线"),
    ("（跨类）权限", "材料收集表 15 条中 10 条无法以程序方式读取，需补授权或重取链接",
     "Roxie、Rikka、Misty、Emma", "未启动",
     "可读 5 条 / 不可读 10 条。材料表原本只记链接不记可读性，导致「收集了 15 条」的错觉"),
]

CAT_FIELDS = [txt("知识库"), txt("要包含什么"), txt("建议字段材料"), txt("负责人"),
              txt("待收集问题"), txt("本地现有条目"), txt("状态"), txt("缺口说明")]
MAT_FIELDS = [txt("编号"), txt("材料"), txt("类型"), txt("token"), txt("来源人"),
              txt("归属"), txt("可读性"), txt("说明")]
TASK_FIELDS = [txt("目标知识库"), txt("待收集问题"), txt("负责人"), txt("状态"), txt("备注")]


def ensure_table(T, app, name, fields, drop):
    r = call(f"{API}/bitable/v1/apps/{app}/tables?page_size=100", None, T)
    if r.get("code") != 0:
        raise SystemExit(f"❌ 列不出表：{r}")
    ex = {x["name"]: x["table_id"] for x in r["data"]["items"]}
    if name in ex:
        if not drop:
            print(f"   ↷ 表「{name}」已存在，沿用")
            return ex[name]
        call(f"{API}/bitable/v1/apps/{app}/tables/{ex[name]}", None, T, "DELETE")
        print(f"   ✕ 表「{name}」已删除（--force）")
    res = call(f"{API}/bitable/v1/apps/{app}/tables",
               {"table": {"name": name, "default_view_name": "表格", "fields": fields}}, T)
    if res.get("code") != 0:
        raise SystemExit(f"❌ 建表「{name}」失败：{json.dumps(res, ensure_ascii=False)[:400]}")
    print(f"   ✅ 建表「{name}」→ {res['data']['table_id']}")
    return res["data"]["table_id"]


def write(T, app, tid, rows, label):
    res = call(f"{API}/bitable/v1/apps/{app}/tables/{tid}/records/batch_create",
               {"records": [{"fields": r} for r in rows]}, T)
    n = len(res["data"]["records"]) if res.get("code") == 0 else 0
    print(f"   {'✅' if n == len(rows) else '⚠️ '} {label} {n}/{len(rows)} 行"
          + ("" if n == len(rows) else f"  {json.dumps(res, ensure_ascii=False)[:160]}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    ok = sum(1 for m in MATERIALS if m["可读性"] == "ok")
    print(f"将写入 知识库分类 {len(CATEGORIES)} 行 ／ 材料收集 {len(MATERIALS)} 行 ／ "
          f"收集任务 {len(TASKS)} 行")
    print(f"材料可读性：可读 {ok} / 不可读 {len(MATERIALS) - ok}\n")
    if not a.apply:
        print("（未加 --apply，未写任何东西）")
        return 0

    T = token()
    app = json.load(open(STATE, encoding="utf-8"))["app_token"]
    tabs = json.load(open(TABLES, encoding="utf-8"))

    t1 = ensure_table(T, app, "知识库分类", CAT_FIELDS, a.force) if a.force else \
        ensure_table(T, app, "知识库分类", CAT_FIELDS, False)
    t2 = ensure_table(T, app, "材料收集", MAT_FIELDS, a.force)
    t3 = ensure_table(T, app, "收集任务", TASK_FIELDS, a.force)

    write(T, app, t1, CATEGORIES, "知识库分类")
    write(T, app, t2, MATERIALS, "材料收集")
    write(T, app, t3, [{"目标知识库": x[0], "待收集问题": x[1], "负责人": x[2],
                        "状态": x[3], "备注": x[4]} for x in TASKS], "收集任务")

    tabs.update({"知识库分类": t1, "材料收集": t2, "收集任务": t3})
    json.dump(tabs, open(TABLES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n→ https://momcozy-in.feishu.cn/base/{app}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
