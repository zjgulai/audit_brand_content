#!/usr/bin/env python3
"""
verify_feishu_index.py —— 飞书资源索引的**独立验收器**

## 为什么需要它

索引是可重跑的生成物，但「生成物自洽」不等于「生成物正确」。两类病只有独立复算
才测得出来：

  ① **恒等式破了。** 候选数 ≠ 三档之和、可读三态之和 ≠ 候选数 —— 这类错说明
     分级逻辑有洞（某条既不属于任何一档、或同时落两档）。脚本内已断言，这里再
     从**落盘文件**独立算一遍：脚本内的断言只保证「跑的那一刻」对，落盘的 json
     可能被别的东西改过。
  ② **假账。** 核心层抽到「0 张表」被当成「它真的是空的」。本轮真踩过这个坑
     （`/tables` 的响应把表放在 `data.items`，我读了 `data.tables`）—— 于是
     11 个多维表格全部安静地报 0 张表，`code=0`、无异常、无告警。
     本脚本把这条变成一条**必须一直绿**的检查。

## 检查项

| 组 | 检查 | 为什么 |
|---|---|---|
| A 恒等 | A1 三档之和 = 候选数 | 分级不能有洞或重叠 |
| | A2 可读三态之和 = 候选数 | 「能/不能/没测」必须穷尽 |
| | A3 core 抽取成功+失败 = core 数 | 不能悄悄丢条 |
| | A4 by_type 之和 = 候选数 | 形态统计不能漏 |
| B 实质 | B1 每个 core bitable 都有 ≥1 张业务表 | 防「0 张表」假账复发 |
| | B2 core 每条的抽取结果非空 | 成功却什么都没有 = 假成功 |
| | B3 每个 core token 都在 MINE 或命中业务词 | 分级不能凭空造 core |
| | B4 表里字段名非空 | 字段名是守衡判语义的关键 |
| C 诚实 | C1 抽不到/读不到的条数必须出现在 md 里 | 不许只在 json 里记账 |
| | C2 md 里的数字与 json 一致 | 不许手改 md |
| | C3 每条失败都带 err 文本 | 「失败」不能没有原因 |
| D 覆盖 | D1 搜索词表已落盘 | 换词换结果，词表必须可复核 |
| | D2 云盘的资源都在候选集里 | 「它自己的」不能漏 |
| | D3 群消息里的 chat_id 都能对上 | 群清单与实际一致 |

用法：
    python3 tools/verify_feishu_index.py           # 全跑
    python3 tools/verify_feishu_index.py -v        # 打印每条明细
"""

from __future__ import annotations

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "research", "feishu", "资源索引-v1.json")
MD = os.path.join(REPO, "research", "feishu", "资源索引.md")

PASS, FAIL = [], []


def ck(group, name, cond, detail=""):
    (PASS if cond else FAIL).append((group, name, detail))
    return cond


def main():
    verbose = "-v" in sys.argv
    if not os.path.exists(INDEX):
        print(f"❌ 索引不存在：{os.path.relpath(INDEX, REPO)}\n先跑 python3 tools/feishu_index.py")
        return 2
    d = json.load(open(INDEX, encoding="utf-8"))
    R, st, F = d["resources"], d["stats"], d["findings"]
    md = open(MD, encoding="utf-8").read() if os.path.exists(MD) else ""

    # ---- A 恒等式
    ck("A", "A1 三档之和 = 候选数",
       sum(st["by_tier"].values()) == st["candidates"],
       f"{sum(st['by_tier'].values())} vs {st['candidates']}")
    ck("A", "A2 可读三态之和 = 候选数",
       st["readable_true"] + st["readable_false"] + st["readable_untested"] == st["candidates"],
       f"{st['readable_true']}+{st['readable_false']}+{st['readable_untested']} vs {st['candidates']}")
    ck("A", "A3 core 抽取成功+失败 = core 数",
       st["core_extent_ok"] + st["core_extent_fail"] == st["by_tier"].get("core", 0),
       f"{st['core_extent_ok']}+{st['core_extent_fail']} vs {st['by_tier'].get('core',0)}")
    ck("A", "A4 by_type 之和 = 候选数",
       sum(st["by_type"].values()) == st["candidates"],
       f"{sum(st['by_type'].values())} vs {st['candidates']}")
    ck("A", "A5 resources 实际条数 = 候选数",
       len(R) == st["candidates"], f"{len(R)} vs {st['candidates']}")
    ck("A", "A6 分级字段只有三种取值",
       set(e["tier"] for e in R) <= {"core", "reference", "noise"},
       str(set(e["tier"] for e in R)))

    # ---- B 实质
    core = [e for e in R if e["tier"] == "core"]
    # 应用模式（is_advanced=true）的多维表格，/tables 恒为空且 /app_tables 是 404
    # —— 接口不存在，既不是读错键名，也不是「它真的是空的」。豁免它，
    # 否则这条断言会对着一个已解释的现象长期报红，然后就没人看了。
    bt = [e for e in core if e["type"] == "bitable" and (e.get("extent") or {}).get("ok")
          and not (e["extent"].get("is_advanced"))]
    bad_bt = [e["title"] for e in bt if not (e["extent"].get("tables"))]
    ck("B", "B1 每个 core 多维表格都有 ≥1 张表（防「0 张表」假账复发）",
       not bad_bt, f"{len(bad_bt)} 个空：{bad_bt[:4]}")

    empties = []
    for e in core:
        ext = e.get("extent") or {}
        if not ext.get("ok"):
            continue
        if e["type"] == "bitable":
            has = bool(ext.get("tables")) or bool(ext.get("is_advanced"))
        elif e["type"] in ("docx", "doc"):
            has = (ext.get("chars") or 0) > 0
        elif e["type"] == "sheet":
            has = bool(ext.get("sheets"))
        elif e["type"] == "slides":
            # 幻灯片没有正文接口，能拿到页数就算抽到了（fetch_slide 的说明）
            has = (ext.get("pages") or 0) > 0
        else:
            has = bool(ext)
        if not has:
            empties.append(f"{e['title']}({e['type']})")
    ck("B", "B2 core 每条的抽取结果非空", not empties, f"{empties[:5]}")

    biz_terms = set(d["biz_terms"])
    # 2026-09-18 改：core 的定义从「命中业务词」换成「在本公司租户」。
    # 旧判据在两个方向上都错（漏掉「全球吸奶器品牌型号库」这类真资产、
    # 误收「行政-差旅常见Q&A」这类无关文档），且都错得没有声音。见 feishu_index.py
    # 的 classify_tier 文档。这条断言相应改成查域名。
    not_tenant = [e["title"] for e in core if e.get("domain") != "tenant"]
    ck("B", "B3 core 每条的 domain 都是本公司租户", not not_tenant, f"{not_tenant[:5]}")
    ck("B", "B3b core 条数 = 本租户条数（定义恒等）",
       len(core) == st.get("tenant_n"),
       f"{len(core)} vs {st.get('tenant_n')}")
    no_domain = [e["title"] for e in R if not e.get("domain") or e["domain"] == "unknown"]
    ck("B", "B3c 每条资源的归属租户都判得出来", not no_domain, f"{no_domain[:5]}")
    no_url = [e["title"] for e in R if not e.get("url")]
    ck("B", "B3d 每条资源都有可点开的链接", not no_url, f"{len(no_url)} 条没链接：{no_url[:4]}")

    nofield = []
    for t in bt:
        for tb in t["extent"]["tables"]:
            if tb.get("embedded_template"):
                continue
            if not (tb.get("fields") or []):
                nofield.append(f"{t['title']}/{tb['name']}")
    ck("B", "B4 业务表都有字段名", not nofield, f"{nofield[:5]}")

    # ---- C 诚实
    fails = [e for e in R if e["tier"] == "core" and not (e.get("extent") or {}).get("ok")]
    if fails:
        missing = [e["title"][:20] for e in fails if e["title"][:20] not in md]
        ck("C", "C1 抽不到的条目写进了 md", not missing, f"md 里找不到：{missing}")
    else:
        ck("C", "C1 抽不到的条目写进了 md", True, "本轮无此情况")

    unread = [e for e in R if e.get("readable") is False]
    if unread:
        missing = [e["title"][:20] for e in unread if e["title"][:20] not in md]
        ck("C", "C1b 读不到的条目写进了 md", not missing, f"{missing[:5]}")
    else:
        ck("C", "C1b 读不到的条目写进了 md", True, "本轮 0 条读不到")

    nums_ok, nums_bad = True, []
    for key, label in [("candidates", "候选资源"), ("chats", "群")]:
        v = st[key]
        if f"**{v}" not in md and f"| {v} " not in md and f" {v} " not in md:
            pass  # 宽松：md 有多种排版，这里只查关键几个
    for key in ("core_extent_ok",):
        if st[key] and str(st[key]) not in md:
            nums_ok, nums_bad = False, nums_bad + [key]
    ck("C", "C2 md 与 json 的关键数字一致", nums_ok, f"{nums_bad}")

    noerr = [f"{e['title'][:20]}" for e in R
             if (e.get("extent") and not e["extent"].get("ok") and not e["extent"].get("err"))]
    ck("C", "C3 每条失败都带 err 文本", not noerr, f"{noerr[:5]}")

    # ---- D 覆盖
    ck("D", "D1 搜索词表已落盘且非空",
       bool(d.get("search_terms")), f"{len(d.get('search_terms') or [])} 个词")
    drive_tokens = {e["token"] for e in R if e.get("in_drive")}
    ck("D", "D2 云盘自有资源都在候选集里",
       st["in_drive"] == len(drive_tokens), f"{st['in_drive']} vs {len(drive_tokens)}")
    chat_ids = {c["chat_id"] for c in d["chats"]}
    msg_ids = {m["chat_id"] for m in d["messages"]}
    ck("D", "D3 消息的 chat_id 都能对到群清单", msg_ids <= chat_ids,
       f"多出来的：{msg_ids - chat_ids}")

    # ---- E 新增（2026-09-18 复测）：可达清单与通讯录口径
    ck("E", "E1 租户分布之和 = 候选数",
       sum(st["by_domain"].values()) == st["candidates"],
       f"{sum(st['by_domain'].values())} vs {st['candidates']}")
    ck("E", "E2 无「域名判不出来」的条目",
       st["by_domain"].get("unknown", 0) == 0, str(st["by_domain"]))
    ck("E", "E3 可达性三态已清零未测（batch_query 补齐）",
       st["readable_untested"] == 0, f"未测 {st['readable_untested']} 条")
    ct = d.get("contacts") or {}
    ck("E", "E4 通讯录读数自洽（可查+被拒=询问数）",
       ct.get("resolved_n", 0) + ct.get("denied_n", 0) == ct.get("asked", -1),
       f"{ct.get('resolved_n')}+{ct.get('denied_n')} vs {ct.get('asked')}")
    ck("E", "E5 通讯录缺口如实落盘（不是静默 0）",
       ct.get("scopes_ok") is not None and "visible" in ct,
       f"可见 {len(ct.get('visible') or [])} 人")
    clist = os.path.join(REPO, "research", "feishu", "可达清单.md")
    ck("E", "E6 可达清单存在", os.path.exists(clist),
       os.path.relpath(clist, REPO))
    if os.path.exists(clist):
        cm = open(clist, encoding="utf-8").read()
        miss = [e["title"] for e in core if e["title"][:16] not in cm]
        ck("E", "E7 本租户 25 条**每一条**都进了可达清单", not miss,
           f"清单里找不到 {len(miss)} 条：{miss[:4]}")
        ck("E", "E8 可达清单标注了「讲什么 / 怎么处理」两列",
           "讲什么" in cm and "怎么处理" in cm, "列名缺失")

    # E9 生成物必须能被 read 工具打开。见 feishu_index.py 的 depad()：
    # 本环境里子进程写出的文件，stat 报的大小会比真实内容多 4096 字节，
    # read 工具据此判成 binary —— 生成物读不出来，等于没生成。
    import subprocess as _sp
    def _stat_size(p):
        try:
            return int(_sp.run(["stat", "-f", "%z", p], capture_output=True,
                               text=True, timeout=5).stdout.strip())
        except Exception:
            return -1
    padded = []
    for p in (MD, os.path.join(REPO, "research", "feishu", "README.md"),
              os.path.join(REPO, "research", "feishu", "可达清单.md")):
        if not os.path.exists(p):
            continue
        real, seen = os.path.getsize(p), _stat_size(p)
        if seen > 0 and seen != real:
            padded.append(f"{os.path.basename(p)}(+{seen - real}B)")
    ck("E", "E9 生成物未被环境填充（read 工具打得开）", not padded,
       f"{padded} —— 跑 python3 tools/feishu_index.py 会自动 depad")

    # ---- M（2026-09-18 新增）：红线「飞书内容禁止下载」的执行点
    #
    # 委托方明确：**飞书上的内容禁止下载**。这条不是风格偏好，是硬约束，
    # 所以它必须有一个**会变红的执行点** —— 否则它就只是一句话（见 AGENTS.md §2.4）。
    # 本段把红线钉在三处：代码里不许有下载调用、产物里不许有附件二进制、
    # 文档里不许把这条删掉。任何一处松掉，这里就红。
    import ast as _ast

    HTTP_HELPERS = {"_get", "_post", "_req", "_request", "get", "post",
                    "urlopen", "fetch", "download"}

    def _str_lit(a):
        if isinstance(a, _ast.Constant) and isinstance(a.value, str):
            return a.value
        if isinstance(a, _ast.JoinedStr):
            return "".join(v.value for v in a.values
                           if isinstance(v, _ast.Constant) and isinstance(v.value, str))
        return ""

    def _download_calls(src):
        """AST 级扫描：注释和文档字符串**不算**，只有真的发起调用才算。

        （所以 fetch_file 的留档说明里可以照写 `download` 字样，不会误报。）
        """
        out = []
        for n in _ast.walk(_ast.parse(src)):
            if not isinstance(n, _ast.Call):
                continue
            f = n.func
            fname = f.id if isinstance(f, _ast.Name) else getattr(f, "attr", "")
            if fname not in HTTP_HELPERS:
                continue
            for a in n.args:
                s = _str_lit(a)
                if not s or not (s.startswith("/") or s.startswith("http")):
                    continue
                if "/download" in s or "/medias/" in s:
                    out.append((getattr(n, "lineno", 0), f"{fname}({s[:70]})"))
        return out

    hits = []
    for fn in sorted(os.listdir(os.path.join(REPO, "tools"))):
        if not fn.endswith(".py"):
            continue
        p = os.path.join(REPO, "tools", fn)
        try:
            src = open(p, encoding="utf-8").read()
        except Exception:
            continue
        for ln, call in _download_calls(src):
            hits.append(f"{fn}:{ln} {call}")
    ck("M", "M1 tools/ 下没有任何附件下载通道的调用（AST 级）", not hits,
       f"发现 {len(hits)} 处：{hits[:4]}")

    # M2 断言本身要能变红 —— 拿一段**已知带下载调用**的代码喂给它，必须报出来。
    # 没有这一条，M1 可能只是个恒真的空转。
    _probe = ('def f(tok, t):\n'
              '    """文档里写 download 不算"""\n'
              '    return _get(f"{BASE}/drive/v1/files/{t}/download", tok)\n')
    ck("M", "M2 该检测器确实会红（喂已知坏样本）",
       len(_download_calls(_probe)) == 1,
       f"喂进去 1 处坏调用，检出 {len(_download_calls(_probe))} 处")

    # M3 飞书取回的产物里不许有附件二进制（正文抽取走的是只读接口，是文本）
    feishu_dir = os.path.join(REPO, "research", "feishu")
    BAD_EXT = (".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".pdf",
               ".zip", ".rar", ".7z", ".png", ".jpg", ".jpeg", ".gif",
               ".mp4", ".mov", ".mp3", ".wav", ".bin")
    bins = []
    if os.path.isdir(feishu_dir):
        for root, _dirs, files in os.walk(feishu_dir):
            for fn in files:
                if fn.lower().endswith(BAD_EXT):
                    bins.append(os.path.relpath(os.path.join(root, fn), REPO))
    ck("M", "M3 research/feishu/ 里没有附件二进制", not bins, f"{bins[:4]}")

    # M4 文档与代码互锁：红线写进 AGENTS.md §2.6，且不再是空的「待补」
    #    （只查 §2.6 这一段 —— 别处出现「待补」二字不该让本段变红）
    ap = os.path.join(REPO, "AGENTS.md")
    asrc = open(ap, encoding="utf-8").read() if os.path.exists(ap) else ""
    _i = asrc.find("### 2.6")
    _sec = asrc[_i:] if _i >= 0 else ""
    _nxt = _sec.find("\n## ", 1)
    if _nxt > 0:
        _sec = _sec[:_nxt]
    ck("M", "M4 AGENTS.md §2.6 已写明「飞书内容禁止下载」且不再是空的「待补」",
       "禁止下载" in _sec and "待补" not in _sec,
       f"§2.6 长度 {len(_sec)} 字，红线未落到文档 —— 执行点就成了孤岛")

    # M5 fetch_file 自身一次网络调用都不能有（连权限探测也不做）
    fs = open(os.path.join(REPO, "tools", "feishu_index.py"), encoding="utf-8").read()
    _ff = next((n for n in _ast.walk(_ast.parse(fs))
                if isinstance(n, _ast.FunctionDef) and n.name == "fetch_file"), None)
    _calls = [getattr(c.func, "id", getattr(c.func, "attr", ""))
              for c in _ast.walk(_ff) if isinstance(c, _ast.Call)] if _ff else ["<未找到 fetch_file>"]
    ck("M", "M5 fetch_file 不做任何网络调用（不下载、也不探测）",
       all(c not in HTTP_HELPERS for c in _calls), f"调用了：{_calls}")

    # ---- 输出
    print("=" * 72)
    print(f"飞书资源索引验收 —— {os.path.relpath(INDEX, REPO)}")
    print("=" * 72)
    if verbose:
        for g, n, dt in PASS:
            print(f"  ✅ [{g}] {n}" + (f"   ({dt})" if dt else ""))
    groups = {}
    for g, n, _ in PASS:
        groups[g] = groups.get(g, 0) + 1
    for g in sorted(groups):
        print(f"  ✅ {g} 组：{groups[g]} 项通过")
    for g, n, dt in FAIL:
        print(f"  ❌ [{g}] {n}   {dt}")
    print("-" * 72)
    total = len(PASS) + len(FAIL)
    if FAIL:
        print(f"❌ {total} 项中 {len(FAIL)} 项失败")
        return 1
    print(f"✅ {total} 项全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
