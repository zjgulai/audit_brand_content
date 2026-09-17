#!/usr/bin/env python3
"""
lark_people.py —— 「责任人 → 投递地址」解析器（只读）

背景（为什么需要这个工具）
    路由表里写的是**姓名**，发送要的是 **open_id**。这两者之间的桥，之前是靠人工从
    知识库人员字段里抄一次。一旦出现一个新责任人（如 Rikka），就得重新找一遍，
    而且找不到时**没法证明「真的找不到」** —— 2026-09-16 我就写过一次恒真扫描：
    用 created_by/last_modified_by 找她，扫了 6000+ 条记录「零命中」，
    后来才发现那个字段在 list records 响应里**恒为 null**，扫描根本没有输入。

    所以本工具的核心不是检索，而是**先证明自己看得见，再回答看不见**：
      · 字典为空 / 锚点找不到  → 退出码 1「无法作答」，绝不说「查无此人」
      · 锚点找得到、目标找不到 → 退出码 2「本应用确实看不见她」，并附边界证据
      · 目标找得到            → 退出码 0，打印可用地址

本应用（cli_aa2243de0438dcd7 守衡）的能力边界（2026-09-16 逐条实测）
    ✗ contact/v3/users（列成员）             99991672 缺 contact:contact.base:readonly
    ✗ contact/v3/departments/0/children      99991672 同上
    ✗ contact/v3/users/{open_id}（id→姓名）  99991672 同上
    ✗ contact/v3/users/batch_get_id（邮箱→id）99991672 同上
    ✗ search/v1/user（按姓名搜人）            99991634 需 user_access_token
    ✗ im/v1/chats → 只有 1 个群、3 人（刘华丽 / 李倩怡 / 周健），没有她
    ✗ created_by / last_modified_by          响应里恒为 null（字段不可用）
    ✗ drive/v1/metas 的 owner_id            只有 id、没有姓名，无法反查
    ✓ **人员字段（bitable 里 type=11 的值）** —— 唯一同时给出 姓名+邮箱+open_id 的通道
      → 字典规模 31 人。她不在其中；她只出现在**文本**字段（材料收集表「来源人」）。

    ⇒ 结论：**本应用没有「按姓名找人」的能力**。要让新责任人可送达，只有两条路：
      (a) 一次性授权通讯录只读（下面 URL 由飞书自己给出，管理员点一次，永久解决）；
      (b) 让本人产生一次可观测信号（给机器人发一句话 / 被拉进机器人所在的群）。

用法
    python3 tools/lark_people.py                  # 盘点 + 自检（阳性对照）
    python3 tools/lark_people.py --find 林建纯     # 解析一个责任人（0 可送达 / 2 不可解析 / 1 无法作答）
    python3 tools/lark_people.py --dump           # 打印全部可见人员
    python3 tools/lark_people.py --selftest       # 只跑阳性对照

退出码
    0 = 解析成功（打印地址）   2 = 本应用看不见此人（附边界证据）
    1 = 无法作答（字典空 / 锚点丢失 / 网络失败）—— ★ 绝不在这种状态下说「查无此人」
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRED = Path(os.path.expanduser("~/.dsh/credentials/shouheng-lark.json"))
OUT = ROOT / "research" / "governance" / "skeleton" / "_data" / "lark-visible-people.csv"
BASE = "https://open.feishu.cn/open-apis"

# 阳性对照锚点：这个人必须能被解析出来，否则说明"字典是空的"，任何"查无此人"都不作数。
# 证据：account-owners.csv（Roxie 一行）与 research/kb/_evidence/.../creative__*.json
#      字段 需求人[0] = {name: 余玉珊, email: r***@rootglobal.net, id: ou_dd3f...}
ANCHOR = {"name": "余玉珊", "open_id": "ou_dd3f9a2e79d23eecaf7c963659d6149a"}
MIN_PEOPLE = 20          # 字典小于这个规模就不足以支撑"查无此人"的结论

# 已知可读的底座（app_token）——只读；新增底座请追加，不要删旧的
APPS = [
    ("DXJ6b5cKtaXPQasoayEc74SUnog", "品线SEO任务管理系统"),
    ("A437bIdQfax7dbsyrAncPpbNnjh", "需求知识库"),
    ("B1oabL2veaFKbKs2hVAcvyKKnEe", "语境守卫词库"),
    ("GnRZbIuXraCzf0sGr2UcmZ62nfc", "内容治理-知识库"),
    ("Lk3Qb8y2QaVyZns6gprcVNE9nA0", "吸奶器广告文案·品线内容边界风控"),
    ("OShmbLBaPam6YSsCzP0cNOyBn6f", "【创意】需求排期与任务管理"),
    ("S35xbhN9TaYp9JspgC0cM6T2nNc", "KPI-绩效评价系统"),
    ("L88os37wThD5OEtajQEcqzbdnIS", "AAA外部需求池"),
]
MAX_RECORDS_PER_TABLE = 3000     # 与其它盘点工具一致的上限，避免失控


def _req(url, token=None, payload=None, timeout=45):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"_http": e.code, **json.loads(e.read())}
        except Exception:
            return {"_http": e.code}
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def token():
    c = json.load(open(CRED, encoding="utf-8"))
    r = _req(f"{BASE}/auth/v3/tenant_access_token/internal", None,
             {"app_id": c["app_id"], "app_secret": c["app_secret"]})
    if r.get("code") != 0:
        raise SystemExit(f"❌ 取 token 失败：{json.dumps(r, ensure_ascii=False)[:300]}")
    return r["tenant_access_token"], c["app_id"]


# ───────────────────────── 采集 ─────────────────────────

def _harvest_values(x, where, out):
    """递归找「人员形状」的值：带 ou_ id 或 email 的 dict。不猜字段类型。"""
    if isinstance(x, dict):
        if str(x.get("id", "")).startswith("ou_") or x.get("email"):
            key = (x.get("name") or x.get("en_name") or "", x.get("email") or "")
            if key[0] or key[1]:
                prev = out.get(key)
                rec = {"姓名": key[0], "en_name": x.get("en_name") or "",
                       "邮箱": key[1], "open_id": x.get("id") or "", "出处": where}
                # 同一人可能出现在多处：保留 id 更完整的一条，出处合并计数
                if prev:
                    if not prev.get("open_id") and rec["open_id"]:
                        rec["出处"] = prev["出处"] + " · " + where
                        out[key] = rec
                    elif where not in prev["出处"]:
                        prev["出处"] = prev["出处"] + " · " + where
                else:
                    out[key] = rec
        for v in x.values():
            _harvest_values(v, where, out)
    elif isinstance(x, list):
        for v in x:
            _harvest_values(v, where, out)


def harvest(tok):
    """扫全部可见底座的人员字段 → 字典。返回 (人, 统计)。"""
    people, tables_read, records_read = {}, 0, 0
    for app, appname in APPS:
        tabs = _req(f"{BASE}/bitable/v1/apps/{app}/tables?page_size=100", tok)
        if tabs.get("code") != 0:
            continue                                  # 单个底座不可读不致命，但要计数
        for t in tabs.get("data", {}).get("items", []):
            tid, tname = t["table_id"], t.get("name", "?")
            tables_read += 1
            page, n = "", 0
            while n < MAX_RECORDS_PER_TABLE:
                url = f"{BASE}/bitable/v1/apps/{app}/tables/{tid}/records?page_size=500"
                if page:
                    url += "&page_token=" + page
                r = _req(url, tok)
                if r.get("code") != 0:
                    break
                items = r.get("data", {}).get("items", [])
                for it in items:
                    _harvest_values(it.get("fields", {}), f"{appname}/{tname}", people)
                n += len(items)
                records_read += len(items)
                if not r.get("data", {}).get("has_more"):
                    break
                page = r.get("data", {}).get("page_token", "")
    return list(people.values()), {"底座": len(APPS), "数据表": tables_read, "记录": records_read}


# ───────────────────────── 纯逻辑（可被验收脚本直接调用，不联网）─────────

def verify_resolver(people, anchor=ANCHOR, min_people=MIN_PEOPLE):
    """阳性对照：解析器必须**先证明自己看得见**，否则一切「查无此人」都不作数。"""
    if not people:
        return False, "字典为空 —— 采集没有输入，此时任何『查无此人』都是恒真结论"
    if len(people) < min_people:
        return False, f"字典只有 {len(people)} 人（<{min_people}）—— 规模不足以支撑否定结论"
    hit = [p for p in people if p["姓名"] == anchor["name"]]
    if not hit:
        return False, f"锚点 {anchor['name']} 不在字典里 —— 字典来源变了，否定结论不可信"
    if hit[0]["open_id"] != anchor["open_id"]:
        return False, (f"锚点 {anchor['name']} 的 open_id 与已知值不符"
                       f"（{hit[0]['open_id']} ≠ {anchor['open_id']}）")
    return True, f"锚点 {anchor['name']} 可解析，字典 {len(people)} 人"


def resolve(query, people, verified=True, why=""):
    """query → {status: found|not_found|unverifiable}。verified=False 时拒绝给否定结论。"""
    q = (query or "").strip()
    if not q:
        return {"status": "error", "why": "空查询"}
    exact = [p for p in people
             if q in (p["姓名"], p["en_name"], p["邮箱"])]
    if exact:
        return {"status": "found", "person": exact[0], "match": "精确"}
    # 姓名里带英文名是常态（"Rikka（林建纯）"），所以再放宽一层：去括号后再比
    bare = q.split("（")[0].split("(")[0].strip()
    loose = [p for p in people
             if bare and (bare in p["姓名"] or bare in p["en_name"] or
                          p["姓名"] in q or (p["en_name"] and p["en_name"] in q))]
    if loose:
        return {"status": "found", "person": loose[0], "match": f"包含匹配（{bare}）"}
    # ★ 结构性防线：字典为空时**无论调用方怎么说**都不给否定结论。
    #   不信赖调用方传进来的 verified —— 否则这个门就成了"检查验证自己"。
    if not people:
        return {"status": "unverifiable",
                "why": "字典为空 —— 此时「查无此人」恒为真，拒绝作答"}
    if not verified:
        return {"status": "unverifiable", "why": why}     # ★ 不返回 not_found
    return {"status": "not_found", "why": why}


# ───────────────────────── 人读输出 ─────────────────────────

def _write_csv(people, app_id, stat):
    import csv
    import datetime
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# 由 tools/lark_people.py 生成（只读采集）",
                    f"harvested_at={stamp}", f"app={app_id}（守衡）",
                    f"底座={stat['底座']}", f"数据表={stat['数据表']}",
                    f"记录={stat['记录']}", f"人数={len(people)}",
                    "口径=bitable 里所有人员形状的值（即本应用唯一能同时拿到 姓名+邮箱+open_id 的通道）"])
        w.writerow(["姓名", "en_name", "邮箱", "open_id", "出处"])
        for p in sorted(people, key=lambda x: x["姓名"]):
            w.writerow([p["姓名"], p["en_name"], p["邮箱"], p["open_id"], p["出处"]])
    return stamp


BOUNDARY = """\
★ 这不是「搜了一下没搜到」，是本应用**结构性看不见人**。逐条实测（2026-09-16）：
    contact/v3/users（列成员）               → 99991672 缺 contact:contact.base:readonly
    contact/v3/departments/0/children        → 99991672 同上
    contact/v3/users/{open_id}（id→姓名）    → 99991672 同上
    contact/v3/users/batch_get_id（邮箱→id） → 99991672 同上
    search/v1/user（按姓名搜人）              → 99991634 需 user_access_token
    im/v1/chats                              → 仅 1 个群 3 人，不含此人
    created_by / last_modified_by            → 响应里恒为 null（字段不可用）
    drive/v1/metas 的 owner_id               → 只有 id 没有姓名，无法反查
  唯一可用通道是**人员字段**（bitable type=11），字典规模见上；此人不在其中，
  说明她只出现在**文本**字段里 —— 文本字段没有 id。"""

ROUTES = """\
★ 让它可送达，四条路（按代价排序）：
    A. 授权通讯录只读（一次性、永久解决，之后任何姓名都能解析）—— 飞书自己给出的申请链接：
       https://open.feishu.cn/app/cli_aa2243de0438dcd7/auth?q=contact:contact.base:readonly
    B. 本人在飞书里给机器人（守衡）发一句话 —— 事件回调带回 sender open_id，零权限
    C. 本人被拉进机器人所在的群「内容治理-守衡Agent-测试」—— 读群成员即得 open_id，零权限
    D. 提供**企业邮箱**（本租户域名 rootglobal.net）—— 发送接口支持 receive_id_type=email
       （实测一个不存在的地址返回 230001 invalid receive_id，**不是**权限错），但此路尚未验证"""


def main():
    ap = argparse.ArgumentParser(description="责任人 → 投递地址 解析器（只读）")
    ap.add_argument("--find", metavar="姓名|邮箱", help="解析一个责任人")
    ap.add_argument("--dump", action="store_true", help="打印全部可见人员")
    ap.add_argument("--selftest", action="store_true", help="只跑阳性对照")
    ap.add_argument("--no-write", action="store_true", help="不写 CSV 产物")
    a = ap.parse_args()

    tok, app_id = token()
    people, stat = harvest(tok)
    ok, why = verify_resolver(people)

    if not a.no_write:
        stamp = _write_csv(people, app_id, stat)
    else:
        stamp = "(未写)"
    print(f"可见人员字典：{len(people)} 人 · 底座 {stat['底座']} · 数据表 {stat['数据表']} · "
          f"记录 {stat['记录']} · 采集于 {stamp}")
    print(f"阳性对照：{'✅ ' if ok else '❌ '}{why}")

    if a.dump:
        for p in sorted(people, key=lambda x: x["姓名"]):
            print(f"  {p['姓名']:10s} {p['en_name']:12s} {p['邮箱']:34s} {p['open_id']}")
    if a.selftest:
        return 0 if ok else 1
    if not a.find:
        if not ok:
            print("\n★ 字典不可信 —— 任何「查无此人」都不作数。先修采集，再下结论。")
            return 1
        return 0

    r = resolve(a.find, people, verified=ok, why=why)
    print()
    if r["status"] == "found":
        p = r["person"]
        print(f"✅ 可送达：{a.find} → {p['姓名']}（{p['en_name']}）"
              f"\n   邮箱    {p['邮箱']}\n   open_id {p['open_id']}"
              f"\n   匹配方式 {r['match']} · 出处 {p['出处']}")
        return 0
    if r["status"] == "unverifiable":
        print(f"⚠ 无法作答：{a.find}\n   原因：{r['why']}\n"
              f"   ★ 拒绝给出「查无此人」—— 阴性结论必须建立在阳性对照之上。")
        return 1
    print(f"❌ 本应用看不见 {a.find}（退出码 2）\n")
    print(BOUNDARY)
    print()
    print(ROUTES)
    return 2


if __name__ == "__main__":
    sys.exit(main())
