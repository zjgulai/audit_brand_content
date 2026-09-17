#!/usr/bin/env python3
"""
lark_find.py —— 用应用身份在飞书里「检索 + 读取」（只读）

发现：应用 tenant_access_token 竟然能调用 suite/docs-api/search/object，
      并且能看到 owner 是真人（周健）的文档。这是本次整合的关键通道。

用法：
  python3 tools/lark_find.py search "关键词" [count]
  python3 tools/lark_find.py read <docs_token> <docs_type>
  python3 tools/lark_find.py readdoc <docx_token>          # 直接读正文
  python3 tools/lark_find.py tables <bitable_token>        # 列出多维表格的数据表
  python3 tools/lark_find.py fields <bitable_token> <table_id>
  python3 tools/lark_find.py records <bitable_token> <table_id> [page_size]
  python3 tools/lark_find.py wiki <wiki_token>             # 解析 wiki 节点真实 obj_token
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

CRED = os.path.expanduser("~/.dsh/credentials/shouheng-lark.json")
BASE = "https://open.feishu.cn/open-apis"


def _req(url, token, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "body": e.read().decode()[:600]}
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def token():
    c = json.load(open(CRED))
    r = _req(f"{BASE}/auth/v3/tenant_access_token/internal", None,
             {"app_id": c["app_id"], "app_secret": c["app_secret"]})
    if r.get("code") != 0:
        raise SystemExit(f"取 token 失败：{r}")
    return r["tenant_access_token"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    t = token()

    if cmd == "search":
        q = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        r = _req(f"{BASE}/suite/docs-api/search/object", t, {"search_key": q, "count": n})
        if r.get("code") != 0:
            print("❌", json.dumps(r, ensure_ascii=False)[:600]); return 1
        ents = r["data"].get("docs_entities", [])
        print(f"命中 {r['data'].get('total')} 条，返回 {len(ents)} 条：\n")
        for i, e in enumerate(ents, 1):
            print(f"{i:3d}. [{e.get('docs_type')}] {e.get('title')}")
            print(f"     token={e.get('docs_token')}  owner={e.get('owner_id')}")
        return 0

    if cmd == "read":
        dt, typ = sys.argv[2], sys.argv[3]
        if typ == "docx":
            r = _req(f"{BASE}/docx/v1/documents/{dt}/raw_content", t)
            print(json.dumps(r, ensure_ascii=False)[:8000])
        elif typ == "bitable":
            r = _req(f"{BASE}/bitable/v1/apps/{dt}", t)
            print(json.dumps(r, ensure_ascii=False)[:3000])
        elif typ == "wiki":
            r = _req(f"{BASE}/wiki/v2/spaces/get_node?token={dt}", t)
            print(json.dumps(r, ensure_ascii=False)[:3000])
        else:
            print(json.dumps(_req(f"{BASE}/wiki/v2/spaces/get_node?token={dt}", t), ensure_ascii=False)[:3000])
        return 0

    if cmd == "readdoc":
        r = _req(f"{BASE}/docx/v1/documents/{sys.argv[2]}/raw_content", t)
        if r.get("code") != 0:
            print("❌", json.dumps(r, ensure_ascii=False)[:500]); return 1
        print(r["data"].get("content", ""))
        return 0

    if cmd == "tables":
        bt = sys.argv[2]
        r = _req(f"{BASE}/bitable/v1/apps/{bt}/tables?page_size=100", t)
        if r.get("code") != 0:
            print("❌", json.dumps(r, ensure_ascii=False)[:500]); return 1
        for it in r["data"].get("items", []):
            print(f"  table_id={it['table_id']}  name={it.get('name')}  "
                  f"records={it.get('revision')}")
        return 0

    if cmd == "fields":
        bt, tb = sys.argv[2], sys.argv[3]
        r = _req(f"{BASE}/bitable/v1/apps/{bt}/tables/{tb}/fields?page_size=100", t)
        if r.get("code") != 0:
            print("❌", json.dumps(r, ensure_ascii=False)[:500]); return 1
        for it in r["data"].get("items", []):
            print(f"  {it['field_name']}  (type={it['type']}, id={it['field_id']})")
        return 0

    if cmd == "records":
        bt, tb = sys.argv[2], sys.argv[3]
        ps = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        url = (f"{BASE}/bitable/v1/apps/{bt}/tables/{tb}/records"
               f"?page_size={ps}")
        r = _req(url, t)
        if r.get("code") != 0:
            print("❌", json.dumps(r, ensure_ascii=False)[:500]); return 1
        d = r["data"]
        print(f"total={d.get('total')} has_more={d.get('has_more')} "
              f"returned={len(d.get('items', []))}")
        for it in d.get("items", [])[:5]:
            f = it.get("fields", {})
            print("  ---")
            for k, v in list(f.items())[:12]:
                sv = json.dumps(v, ensure_ascii=False)
                print(f"    {k} = {sv[:160]}")
        return 0

    if cmd == "wiki":
        r = _req(f"{BASE}/wiki/v2/spaces/get_node?token={sys.argv[2]}", t)
        print(json.dumps(r, ensure_ascii=False)[:2000])
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
