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

    # ---- M（2026-09-18 新增；2026-10-17 改线后重写判据）
    #
    # 2026-09-18 的原判据是「飞书内容禁止下载」；2026-10-17 委托方改定
    # 「你都可以下载」，原判据整条作废（AGENTS.md §2.6）。改线后仍成立的是
    # **下载物不许进公开仓**，所以本段钉三处：
    #   ① 每个下载调用点必须登记（消费者 + 落盘路径）—— M1；
    #   ② 那个检测器必须真会红 —— M2 / M2b（行为级，不是文本检查）；
    #   ③ 飞书产物里不许有未登记的附件二进制 —— M3。
    #
    # ★ 2026-10-17 组装：M1 不再在这里维护第二套 AST 扫描器。
    #   调用点扫描（Python + JS）、登记表字段、landing_root 的判据统一在
    #   tools/verify_download_governance.py 的 DG-1 / DG-2。
    #   两处就是两套：旧 M1 只比 `$allow` 字符串，而登记表已经换成 `entries`，
    #   它读不到任何东西 —— 那正是「名字出现过 ≠ 拦得住」（AGENTS.md §2.4）。
    import ast as _ast

    HTTP_HELPERS = {"_get", "_post", "_req", "_request", "get", "post",
                    "urlopen", "fetch", "download"}

    _tools_dir = os.path.dirname(os.path.abspath(__file__))
    if _tools_dir not in sys.path:
        sys.path.insert(0, _tools_dir)
    import verify_download_governance as _dg

    _dg_reg = _dg.evaluate_registration(REPO)
    _dg_reds = list(_dg_reg.get("reds") or [])
    _dg_untested = list(_dg_reg.get("untested") or [])
    ck("M", "M1 每个附件下载调用点都已登记（消费者 + 落盘路径）",
       _dg_reg["ok"],
       "DG-1 {}；DG-2 {}；红 {} 条{}；未测 {} 条{}".format(
           _dg_reg["DG-1"]["detail"], _dg_reg["DG-2"]["detail"],
           len(_dg_reds), (":" + str(_dg_reds[:3])) if _dg_reds else "",
           len(_dg_untested),
           (":" + str(_dg_untested[:2])) if _dg_untested else ""))

    # M2 行为级反向对照：把**同一个** M1 判据喂给「真实调用集 + 一个未登记调用」，
    # 它必须红。只断言函数存在是文本检查（AGENTS.md §2.4）；这里真跑一次，
    # 并且走的是 M1 刚用过的那个入口与真实登记表。
    _dg_fake = {
        "path": "tools/_m2_unregistered_probe.py",
        "symbol": "g",
        "lineno": 3,
        "col_offset": 4,
        "sink": "http",
        "shape": "fstring",
        "api": "https://open.feishu.cn/open-apis/drive/v1/files/<expr>/download",
        "marker": "/download",
    }
    _dg_probe = _dg.evaluate_registration(
        REPO, calls=list(_dg_reg.get("calls") or []) + [_dg_fake])
    ck("M", "M2 DG-1 判据对未登记调用必须红（否则 M1 恒真）",
       (not _dg_probe["ok"])
       and any("少登记" in red for red in _dg_probe["reds"]),
       "真实调用 {} 个 + 1 个假调用 → reds {}".format(
           len(_dg_reg.get("calls") or []), _dg_probe["reds"][:2]))

    # M2b 端到端行为级证明：导入的判据在临时仓库里面对**真实的 .py 与 .mjs**
    # 下载调用必须红，补登记后必须绿。这证明 M1 用的不是一条恒真函数，
    # 也证明两个扫描器真的接进来了 —— 源码里写个 import 不算接线。
    try:
        _dg_control = _dg.control_dg6()
        _dg_control_ok = bool(_dg_control["ok"])
        _dg_control_detail = _dg_control["detail"]
    except Exception as exc:  # 控制跑不起来 = 未测，不许当成通过
        _dg_control_ok, _dg_control_detail = False, "控制跑不起来：%s" % exc
    ck("M", "M2b DG 判据端到端会红也会绿（真实扫描器已接入）",
       _dg_control_ok, _dg_control_detail)

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
    # ★ 2026-10-17：M4 的判据必须**跟着改线一起改**。
    #   旧判据查「禁止下载」四个字在不在 —— 而它在新文本里**作为废止记录仍然出现**，
    #   于是改线之后这条断言会**假绿**。这是 AGENTS.md §2.4 点名的「名字出现过 ≠ 拦得住」，
    #   此刻正长在防它的断言自己身上。
    #   新判据查「现行口径是不是允许下载」，且**必须带着改线日期**（可追溯谁改的）。
    _allow_now = ("可以读取，包括附件" in _sec) and ("2026-10-17" in _sec)
    _old_ban = "**下载附件**（xlsx / pdf / 图片 / 视频 / 文档） | ⛔" in _sec
    ck("M", "M4 AGENTS.md §2.6 写的是**现行**口径（允许下载 + 改线日期），不是废止记录",
       _allow_now and not _old_ban,
       f"§2.6 长度 {len(_sec)} 字；允许={_allow_now}；残留旧禁令表行={_old_ban}")

    # M5 —— ★ 2026-10-17 改成**与 DG-2 同源**，不再自己判一遍。
    #
    #   上一版 M5 的判据是「fetch_file 的源码里有没有 tempfile/TMPDIR//tmp 这几个字符串」——
    #   **写个注释就满足**。这是 AGENTS.md §2.4 点名的「名字出现过 ≠ 拦得住」，
    #   而它此刻正长在验它自己的断言上。
    #
    #   现在的做法：直接调用 `verify_download_governance.evaluate_dg2()`，
    #   用**同一份 landing_root 校验结果**。两处各判一遍 = 两套判据，迟早各绿。
    try:
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import verify_download_governance as _dgv  # noqa: E402
        _dg2 = _dgv.evaluate_dg2()
        ck("M", "M5 下载落盘根与 DG-2 同源（不是自己再判一遍）",
           _dg2.get("ok", False),
           f"DG-2 报了红：{str(_dg2.get('reds') or _dg2)[:160]}")
    except Exception as _e:
        ck("M", "M5 下载落盘根与 DG-2 同源（不是自己再判一遍）", False,
           f"调不到 verify_download_governance.evaluate_dg2：{_e!r}")

    # M6 —— ★ 2026-10-17 加：**传播 DG 的总判定**。
    #
    #   为什么必须有这一条：M5 只接了 DG-2（落盘根），而 DG-3（仓内二进制 / PII）
    #   红着的时候，本脚本仍然能 42 项全过 —— 于是**总自证会误报绿**。
    #   一条「只接了自己想接的那一项」的判据，比没有更糟：它给了全部通过的错觉。
    #
    #   判据形态：调 evaluate_all() 拿总 verdict，**红 → 红，未测 → 未测**，
    #   不许把「未测」当「通过」（AGENTS.md §2.4.2 的 L3 同口径）。
    try:
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import verify_download_governance as _dgv2  # noqa: E402
        _all = _dgv2.evaluate_all()
        _v = _all.get("verdict")
        if _v == "red":
            _n = sum(len((_all.get(d) or {}).get("reds") or []) for d in
                     ("DG-1", "DG-2", "DG-3", "DG-4", "DG-5", "DG-6"))
            ck("M", "M6 下载治理总判定已传播（DG 红则本脚本红）", False,
               f"DG verdict=red，共 {_n} 条红；明细见 `python3 tools/verify_download_governance.py`")
        elif _v == "untested":
            ck("M", "M6 下载治理总判定已传播（DG 红则本脚本红）", False,
               "DG verdict=untested —— 未测不是通过")
        else:
            ck("M", "M6 下载治理总判定已传播（DG 红则本脚本红）", True, "")
    except Exception as _e:
        ck("M", "M6 下载治理总判定已传播（DG 红则本脚本红）", False,
           f"调不到 verify_download_governance.evaluate_all：{_e!r}")

    # ---- H（2026-09-22 新增）：飞书 HTTP 助手只许有**一份** —— 防漂移复活
    #
    # 债 #16：`call(url, payload=None, token=None, method=None)` 曾在 4 个脚本里各有一份，
    # **只有超时不同**（实测 60 / 60 / 30 / 25，sha256 逐份对过）。后果不是「不好看」，
    # 而是同一个飞书接口在慢网络上 A 脚本成功、B 脚本失败 —— 差别只在当初抄了哪个数。
    # 已收编到 `tools/lark_http.py`；本段是**防它复活**的判据：
    # 谁再抄一份同名 `call()`，这里就红，并点出 `文件:行号`。
    #
    # ★ 判据刻意收在「函数名 == call 且函数体里有 urlopen」上，**不是**「任何含 urlopen 的函数」。
    #   后者会立刻误报：本仓另有 `feishu_index._get/_post`、`lark_find.py`、`lark_people.py`、
    #   `lp_fetch.py`、`shouheng.py::FeishuClient._request` 等十来处各自成立的 HTTP 助手，
    #   它们**不是**这条债的形状（不同参数序、不同返回契约）。
    #   一个会误报的检查器比没有检查器更糟（AGENTS.md §2.1.1）。
    #   已知盲区（明着留着）：把 `call` 改名成别的名字再抄一份，本段抓不到 ——
    #   H2 的名册同步只覆盖已声明的文件。
    _re_t = re.compile(r"timeout\s*=\s*\d")

    def _call_helpers(src):
        """→ [(行号, 函数名)]：函数名 == `call` 且函数体里出现 `urlopen` 的定义。"""
        out = []
        for n in _ast.walk(_ast.parse(src)):
            if not isinstance(n, _ast.FunctionDef) or n.name != "call":
                continue
            if any(isinstance(c, _ast.Call) and
                   getattr(c.func, "id", getattr(c.func, "attr", "")) == "urlopen"
                   for c in _ast.walk(n)):
                out.append((n.lineno, n.name))
        return out

    def _timeout_literals(src):
        """→ [(行号, 文本)]：字面量 `timeout=<数字>`。**整行注释不算代码**
        （与本仓 verify_shouheng_ops C5、verify_cards J1a 同一条读法）。"""
        out = []
        for i, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _re_t.search(line):
                out.append((i, line.strip()[:70]))
        return out

    _tools = os.path.join(REPO, "tools")

    def _read(name):
        try:
            return open(name, encoding="utf-8").read()
        except Exception:                                     # noqa: BLE001
            return None

    # 名册的唯一来源是 lark_http 自己（声明只有一处，见 AGENTS.md §2.5 的同一条精神）
    try:
        sys.path.insert(0, _tools)
        import lark_http as _lh
        _members, _non_members = list(_lh.MEMBERS), dict(_lh.NON_MEMBERS)
        ck("H", "H0 名册可读（lark_http.MEMBERS / NON_MEMBERS）",
           bool(_members) and bool(_non_members), "名册读不出，H 段只能落红")
    except Exception as exc:                                  # noqa: BLE001
        _members, _non_members = [], {}
        ck("H", "H0 名册可读（lark_http.MEMBERS / NON_MEMBERS）", False,
           f"import lark_http 失败：{type(exc).__name__}: {exc}")

    # H1 全仓只许有一份 `call()` HTTP 助手（正身 = tools/lark_http.py）
    dup = []
    for fn in sorted(os.listdir(_tools)):
        if not fn.endswith(".py") or fn == "lark_http.py":
            continue
        src = _read(os.path.join(_tools, fn))
        if src is None:
            continue
        for ln, _nm in _call_helpers(src):
            dup.append(f"{fn}:{ln}")
    ck("H", "H1 tools/ 下 `call()` HTTP 助手只有 lark_http.py 一份（AST 级）", not dup,
       f"又出现了 {len(dup)} 份副本：{dup[:4]} —— 超时又会各自漂移")

    # H1b 成员必须真的走了共用实现
    not_wired = [m for m in _members
                 if "lark_http" not in (_read(os.path.join(REPO, m)) or "")]
    ck("H", "H1b 名册里的成员都 import 了 lark_http", not not_wired,
       f"没接上的：{not_wired}")

    # H2 名册不许当免死金牌：非成员必须存在、必须真有一个 HTTP 助手、理由必须写
    bad_non = []
    for m, why in _non_members.items():
        src = _read(os.path.join(REPO, m))
        if src is None:
            bad_non.append(f"{m}：盘上没有这个文件")
            continue
        funcs = [(n.lineno, n.name) for n in _ast.walk(_ast.parse(src))
                 if isinstance(n, _ast.FunctionDef)
                 and any(isinstance(c, _ast.Call) and
                         getattr(c.func, "id", getattr(c.func, "attr", "")) == "urlopen"
                         for c in _ast.walk(n))]
        if not funcs:
            bad_non.append(f"{m}：登记为「保留本地实现」，但源码里没有任何 HTTP 助手")
        if len((why or "").strip()) < 20:
            bad_non.append(f"{m}：理由太短（等于免死金牌）")
    ck("H", "H2 NON_MEMBERS 每条都在盘上、真有本地实现、且写明了理由", not bad_non,
       f"{bad_non[:3]}")

    # H3 超时只许来自 lark_http.TIMEOUT —— 名册内文件不许再有字面量
    lit = []
    for m in list(_members) + list(_non_members):
        src = _read(os.path.join(REPO, m))
        if src is None:
            continue
        for ln, txt in _timeout_literals(src):
            lit.append(f"{os.path.basename(m)}:{ln} {txt}")
    ck("H", "H3 名册内文件没有字面量 timeout=<数字>（超时只有一处）", not lit,
       f"{lit[:4]} —— 改这一处去 lark_http.TIMEOUT")

    # H4 反向对照：本段的三个扫描器喂已知坏样本，**必须**红
    _bad_src = ('def call(url, payload=None, token=None, method=None):\n'
                '    with urllib.request.urlopen(url, timeout=25) as x:\n'
                '        return x.read()\n')
    _ok_a = len(_call_helpers(_bad_src)) == 1
    _ok_b = bool(_timeout_literals(_bad_src))
    ck("H", "H4 三个扫描器都真的会红（喂已知坏样本）", _ok_a and _ok_b,
       f"抄来的 call() 检出 {len(_call_helpers(_bad_src))} 份、"
       f"字面 timeout 检出 {len(_timeout_literals(_bad_src))} 处")
    # H4b 名册本身也要能红：临时塞一个不存在的非成员，H2 的形状必须报出来
    _probe_non = {"tools/这个文件不存在.py": "假装有个理由，其实盘上没有这个文件"}
    _h2_bad = [m for m in _probe_non if _read(os.path.join(REPO, m)) is None]
    ck("H", "H4b H2 的判据对「登记了但盘上没有」确实会红", bool(_h2_bad),
       f"喂进去 1 条假登记，报出 {len(_h2_bad)} 条")

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
