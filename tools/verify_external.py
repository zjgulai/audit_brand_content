#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部标准库条款原文 · 独立复核（不信研究稿的自述）

背景：研究稿交付时声明「62 条条款原文逐条用脚本比对过当天真实抓取的页面
文本，0 条失配」，但仓库里只留下成品 JSON —— **没有任何页面文本留档**。
那是一句没有物证的过程声明：换个人、换一天，无法重跑，也无法反驳。

本脚本把它变成可重算的东西：
  1. 自己按来源清单抓一遍，页面文本钉成快照
     research/kb/_evidence/外部标准库/S{n}.txt（含 url / UA / http / 长度 / 取法）
     ★ 该目录按 ADR-0013 §三属证据层（`**/_evidence/` 不入 git），
       所以「新克隆的仓库」没有快照 —— 那时跑默认模式（现场抓）而不是 --offline。
  2. 逐条核对「条款原文」是否为该来源快照的去空白子串
  3. 抓不到或没快照的来源 → 其条目记 UNVERIFIABLE，**不计入命中**

★ 实测到的环境事实（写下来，因为它们互相矛盾，猜不出来）：
  · FDA  朴素 UA → 200；**伪装浏览器 UA → 404（10 字节）**
  · FTC  朴素 UA → 403；**伪装浏览器 UA → 200**
  · Meta 两种 UA 都 200，但正文不在 HTML 里 —— 只剥标签仅得 41 字符；
         正文在 Next.js 内嵌数据块里
  所以抓取序列是「先浏览器 UA、文本太薄再退朴素 UA」，并把**实际生效的
  UA 写进快照抬头**。取法不按来源记录，逐字核对就不可复现 —— 这正是本
  脚本要修的那个洞。

命中还分两级，避免「在一大堆内嵌字符串里凑上」被当成可见正文：
  visible  = 命中剥标签后的 HTML 正文
  embedded = 只在内嵌数据块（window.__scV2Content / __NEXT_DATA__ 等）里命中

用法：
  python3 tools/verify_external.py              # 抓取 + 核对（默认，落快照）
  python3 tools/verify_external.py --offline    # 只用已钉快照，不联网
  python3 tools/verify_external.py --only S11,S12
退出码：0 = 全部条目命中；1 = 有失配，或有条目不可复核。
"""
import argparse
import html as _html
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "research/kb/外部标准库-v1.json")
SNAPDIR = os.path.join(ROOT, "research/kb/_evidence/外部标准库")
# 仓内已钉住的证据树：抬头带 `URL:` 的抓取件可按下述方式复用
PIN_ROOTS = ("research/governance/_evidence",)
PIN_URL = re.compile(r"^(?:Source URL|URL|SOURCE_URL)\s*:\s*(\S+)", re.M)
PIN_DATE = re.compile(r"^(?:Fetch date|FETCH_DATE|FETCHED)\s*:\s*(\S+)", re.M)
BUA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PLAIN = "curl/8"
# 内嵌数据块的变量名（Amazon 用 scV2Content，Meta 用 __NEXT_DATA__）
BLOBS = ("window.__scV2Content", "__NEXT_DATA__", "__APOLLO_STATE__",
         "__NUXT__", "application/json")


# ---------- 内嵌数据块 ----------

def _brace_slice(s, start):
    """从 s[start] == '{' 起做括号配平（跳过字符串与转义），返回完整 JSON 文本。"""
    depth, i, n, instr, esc = 0, start, len(s), False, False
    while i < n:
        c = s[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        i += 1
    return None


def _leaves(o, out):
    if isinstance(o, dict):
        for v in o.values():
            _leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            _leaves(v, out)
    elif isinstance(o, str):
        out.append(o)


def embedded_text(body):
    """页面内嵌 JSON 数据块里的全部叶子字符串。"""
    out = []
    for name in BLOBS:
        for m in re.finditer(re.escape(name), body):
            b = body.find("{", m.end())
            if b < 0:
                continue
            blob = _brace_slice(body, b)
            if not blob:
                continue
            try:
                leaves = []
                _leaves(json.loads(blob), leaves)
                out.extend(leaves)
            except Exception:
                pass
    if not out:  # 退路：任何 <script type="application/json"> 块
        for m in re.finditer(r'(?is)<script[^>]+application/json[^>]*>(.*?)</script>', body):
            try:
                leaves = []
                _leaves(json.loads(m.group(1).strip()), leaves)
                out.extend(leaves)
            except Exception:
                pass
    return out


# ---------- 取页面 ----------

def _curl(url, ua):
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "45", "-A", ua,
                        "-w", "\n__HTTP__%{http_code}", url],
                       capture_output=True, text=True, errors="replace")
    body, code = r.stdout, ""
    m = re.search(r"__HTTP__(\d{3})\s*$", body)
    if m:
        code, body = m.group(1), body[:m.start()]
    return code, body


def fetch(url):
    """先浏览器 UA，文本太薄再退朴素 UA —— 两种来源的要求正好相反。"""
    tried = []
    for ua, label in ((BUA, "browser-UA"), (PLAIN, "plain-UA")):
        code, body = _curl(url, ua)
        tried.append("%s:%s" % (label, code))
        if code == "200" and len(body) > 20000:
            return code, body, label, "; ".join(tried)
        time.sleep(0.6)
    return code, body, label, "; ".join(tried)


def _strip_markup(s):
    """去标记，且不引入原文没有的空格。

    ★ 两个坑，都会把「引文逐字正确」误判成失配（本脚本第一版两个都踩了）：
      · 把**所有**标签都换成空格 → `"<em>Decreases` 变成 `" Decreases`
      · 不删 HTML 注释 → Next.js 在相邻文本节点间插 `<!-- -->`，
        `Contain<!-- -->s` 于是卡在第 8 个字符上
    所以：注释删掉；块级标签换空格（保住词间边界）；行内标签换空串。
    """
    s = re.sub(r"(?s)<!--.*?-->", "", s)
    s = re.sub(r"(?is)</?(?:p|div|li|ul|ol|br|tr|td|th|h[1-6]|section|article"
               r"|table|blockquote|dd|dt|dl|hr)\b[^>]*>", " ", s)
    return re.sub(r"(?s)<[^>]+>", "", s)


def extract(body):
    """HTML → (可见正文, 内嵌数据块叶子串)"""
    vis = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
    return _strip_markup(vis), _strip_markup(" \n ".join(embedded_text(body)))


# ---------- 仓内已钉证据 ----------
# ★ 为什么需要这条腿：Meta 的 policy 页是纯客户端 SPA（正文走 /api/graphql/），
#   今天在本机**没有任何匿名取法**能拿到正文（实测：朴素/浏览器 UA、无斜杠、
#   _fb_noscript、en-gb、print、amp、Firecrawl 渲染、浏览器桥 —— 全部只得到
#   标题与 JS bundle）。但这类页面**早就以证据件形式钉在仓里**了。
#   「今天抓不到」不等于「不可复核」：对着钉住的抓取件核，反而比对着会变的
#   线上页核更硬 —— 只要抬头写明 URL 与抓取日，且 URL 与引用来源一致。

def pin_index():
    """→ {规范URL: [(相对路径, 抓取日), ...]}"""
    idx = {}
    for r in PIN_ROOTS:
        for dp, _dn, fn in os.walk(os.path.join(ROOT, r)):
            for f in fn:
                p = os.path.join(dp, f)
                try:
                    if os.path.getsize(p) > 4_000_000:
                        continue
                    head = open(p, encoding="utf-8", errors="replace").read(3000)
                except Exception:
                    continue
                m = PIN_URL.search(head)
                if not m:
                    continue
                url = m.group(1).rstrip(".,);").rstrip("/")
                d = PIN_DATE.search(head)
                idx.setdefault(url, []).append(
                    (os.path.relpath(p, ROOT), d.group(1) if d else "?"))
    return idx


_PIN_CACHE = {}


def pin_texts(path):
    if path not in _PIN_CACHE:
        body = open(os.path.join(ROOT, path), encoding="utf-8", errors="replace").read()
        vis = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
        _PIN_CACHE[path] = norm(_strip_markup(vis))
    return _PIN_CACHE[path]


# ---------- 比对 ----------

def norm(s):
    s = _html.unescape(s)
    for a, b in (("\u00a0", " "), ("\u2009", " "), ("\u202f", " "),
                 ("\u200b", ""), ("\ufeff", "")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def fold(s):
    """把排版形态折叠成 ASCII —— 用于区分「逐字命中」与「只差弯引号」。"""
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'),
                 ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-"),
                 ("\u2026", "..."), ("\u02bc", "'")):
        s = s.replace(a, b)
    return s


def ws_fold(s):
    """再折一层**空格位置**。

    ★ 抓取侧剥标签时为保住词间边界，常把标签换成空格；转录时若照抄，
    就会在标点前留下原文没有的空格（`Comparative claims :`、`as “ tests`）。
    这是转录杂质，不是内容差异 —— 但要**报出来让人改**，不能悄悄放过。
    """
    s = fold(s)
    s = re.sub(r"\s+([:;,.)\]])", r"\1", s)
    # ★ 只认**无歧义**的左引号。直引号 " 与 ' 既可能是左也可能是右，
    #   第一版把它们一并当左引号，于是把 `condition" is not` 的空格也删了
    #   —— 那恰好是一次**自伤**：把一个本来逐字正确的引文改成了错的。
    return re.sub(r"([(\[\u201c\u2018])\s+", r"\1", s)


# ---------- 主流程 ----------

def verdict(n_live, n_miss, n_unver, n_pun, n_wsq, n_hit, n_total):
    """把结论行拆成纯函数 —— 好让 `--controls` 直接断言**这句话本身**不许撒谎。

    与 `verify_prd_baseline.verdict` / `verify_shouheng_ops.verdict` 同口径，
    三种退出码语义互不相同：

    | 码 | 含义 | 它**不**代表 |
    |---:|---|---|
    | 0 | 全部条目**逐字**命中，且今天真抓过上游 | —— |
    | 1 | 有失配 / 不可复核 / 只差排版形态 | —— |
    | 2 | **未测**：今天 0 个来源被真抓（`--offline`，或全部走了已钉快照） | **不等于通过** |

    为什么「0 个来源被真抓」必须是 2 而不是 0：逐字命中在**快照**上验过，
    不等于在**上游**验过。`--offline` 报 ✅ 会说出一句当天确定错误的话
    （「今日抓取」）—— 这正是 §2.4.1 那句自检「这句话比我的输入大吗？」。

    有红且未测时，红优先（与 `verify_shouheng_ops.py` 的 H7 一致：
    **有红时也必须把未测说出来**，否则只看最后一行的人会以为其余都验过了）。
    """
    untested_note = ""
    if n_live == 0:
        untested_note = ("；**另有未测**：今日 0 个来源被真抓，"
                         "逐字命中只在快照上验过、没在上游验过")
    if n_miss or n_unver or n_pun or n_wsq:
        return 1, ("❌ 未通过：失配 %d / 不可复核 %d / 仅差排版形态 %d / 空位形态不齐 %d%s"
                   % (n_miss, n_unver, n_pun, n_wsq, untested_note))
    if n_live == 0:
        return 2, ("⚠️  今日 0 个来源被真抓（`--offline`，或全部走了已钉快照）—— "
                   "**未测**：逐字命中只在快照上验过，没在上游验过。退 2，不是通过。")
    return 0, ("✅ %d/%d 条在该来源快照中**逐字**命中（无形态差、无空位差）"
               % (n_hit, n_total))


def controls():
    """反向对照：把已知形状喂进 `verdict()`，断言结论行**不许撒谎**。

    这是 §2.4.1「没红过的断言不算验证过它」的直接落实 ——
    结论行本身也是断言，所以它也要被喂坏样本。
    全部在内存里做，不落盘、不联网（§2.1：反向对照只在内存里做）。
    """
    cases = [
        # (名称, 参数, 期望退出码, 结论行必须含, 结论行必须不含)
        ("全过（今日真抓过）", (17, 0, 0, 0, 0, 62, 62), 0, ["逐字", "命中"], ["未测", "❌"]),
        ("★ --offline：0 个来源被真抓，其余全过",
         (0, 0, 0, 0, 0, 62, 62), 2, ["未测"], ["✅", "今日抓取"]),
        ("有失配", (17, 1, 0, 0, 0, 61, 62), 1, ["失配 1"], ["✅"]),
        ("只差排版形态（punct）", (17, 0, 0, 3, 0, 59, 62), 1, ["排版形态 3"], ["✅"]),
        ("★ 又红又未测：红优先，但必须报出未测",
         (0, 1, 0, 0, 0, 61, 62), 1, ["失配 1", "另有未测"], ["✅"]),
    ]
    n_ok = 0
    for name, args, want_code, must, must_not in cases:
        code, line = verdict(*args)
        bad = []
        if code != want_code:
            bad.append("退出码 %d ≠ 期望 %d" % (code, want_code))
        for m in must:
            if m not in line:
                bad.append("结论行里没有 %r" % m)
        for m in must_not:
            if m in line:
                bad.append("结论行里不该有 %r" % m)
        if bad:
            print("  ❌ %s\n       %s\n       → %s" % (name, "；".join(bad), line))
        else:
            print("  ✅ %s → 退 %d" % (name, code))
            n_ok += 1
    print("\n反向对照 %d 项全过（含「原样必须全绿」这一条）" % n_ok)
    return 0 if n_ok == len(cases) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="只用已钉快照，不联网")
    ap.add_argument("--only", default="", help="只处理这些来源，如 S11,S12")
    ap.add_argument("--controls", action="store_true",
                    help="只跑结论行的反向对照（离线，不读清单、不联网）")
    a = ap.parse_args()

    if a.controls:
        return controls()

    d = json.load(open(DRAFT, encoding="utf-8"))
    srcs = {s["id"]: s for s in d["sources"]}
    entries = d["entries"]
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    os.makedirs(SNAPDIR, exist_ok=True)

    snap, meta = {}, {}
    for sid in sorted(srcs, key=lambda x: int(x[1:])):
        if only and sid not in only:
            continue
        path = os.path.join(SNAPDIR, sid + ".txt")
        if a.offline:
            if not os.path.exists(path):
                meta[sid] = ("(无快照)", 0, "offline")
                continue
            hdr, _, body = open(path, encoding="utf-8").read().partition("\n---\n")
            vis, _, emb = body.partition("\n===EMBEDDED===\n")
            snap[sid] = (vis, emb)
            meta[sid] = ("cached", len(vis) + len(emb), "offline")
            continue
        code, body, ua, tried = fetch(srcs[sid]["url"])
        vis, emb = extract(body)
        vis, emb = norm(vis), norm(emb)
        if code == "200" and len(vis) + len(emb) > 2000:
            snap[sid] = (vis, emb)
            meta[sid] = (code, len(vis) + len(emb), ua + "  [" + tried + "]")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# url: %s\n# http: %s\n# ua: %s\n# tried: %s\n"
                        "# visible=%d  embedded=%d\n# fetched: %s\n---\n%s"
                        "\n===EMBEDDED===\n%s"
                        % (srcs[sid]["url"], code, ua, tried, len(vis), len(emb),
                           time.strftime("%Y-%m-%dT%H:%M:%S"), vis, emb))
        else:
            meta[sid] = (code or "ERR", len(vis) + len(emb), ua + "  [" + tried + "]")
        time.sleep(0.8)

    # 今天**真抓过**的来源数：`--offline` 下 17 行来源表全是 `offline`，这里就是 0。
    # 「逐字命中」在快照上成立，不等于在上游成立 —— 所以 0 是**未测**，不是通过。
    n_offline = len([1 for m in meta.values() if str(m[2]) == "offline"])
    n_live = len(meta) - n_offline

    hit, miss, unver = [], [], []
    pidx = pin_index()
    for e in entries:
        sid, q = e["source_id"], norm(e.get("条款原文") or "")
        cands = []
        if sid in snap:
            vis, emb = snap[sid]
            if vis:
                cands.append(("visible", vis))
            if emb:
                cands.append(("embedded", emb))
        for path, date in pidx.get(srcs[sid]["url"].rstrip("/"), []):
            cands.append(("pin:%s@%s" % (path, date), pin_texts(path)))
        if not cands:
            unver.append((e["id"], sid, "无快照(%s)" % meta.get(sid, ("?",))[0]))
            continue
        got = None
        for where, txt in cands:
            if q and q in txt:
                got = (where, "exact")
                break
            if q and fold(q) in fold(txt):
                got = (where, "punct")
                break
            if q and ws_fold(q) in ws_fold(txt):
                got = (where, "ws")
                break
        if got:
            hit.append((e["id"], sid) + got)
        else:
            miss.append((e["id"], sid, q, None))

    print("=" * 80)
    print("来源抓取")
    print("=" * 80)
    for sid in sorted(srcs, key=lambda x: int(x[1:])):
        if only and sid not in only:
            continue
        code, ln, note = meta.get(sid, ("-", 0, "-"))
        n = len([e for e in entries if e["source_id"] == sid])
        print("%s%-4s http=%-5s text=%-8d 条目=%-3d %s"
              % ("OK " if sid in snap else "!! ", sid, code, ln, n, note[:62]))
    print()
    n_vis = len([h for h in hit if h[2] == "visible"])
    n_emb = len([h for h in hit if h[2] == "embedded"])
    n_pin = len([h for h in hit if h[2].startswith("pin:")])
    n_pun = len([h for h in hit if h[3] == "punct"])
    print("=" * 80)
    # ★ 口径必须自己说出来：`--offline` 下写「今日抓取」是一句**当天确定错误**的话。
    src_desc = ("今日抓取" if n_live else
                "**已钉快照（今日 0 个来源被真抓 —— 上游本次未测）**")
    print("逐条核对：命中 %d（%s：可见正文 %d / 仅内嵌数据块 %d；仓内钉住证据 %d）"
          "  失配 %d  不可复核 %d  —— 共 %d 条"
          % (len(hit), src_desc, n_vis, n_emb, n_pin, len(miss), len(unver), len(entries)))
    print("=" * 80)
    if n_pin:
        print("\n· 靠仓内钉住证据命中的（今日无匿名取法拿到正文，改对钉住抓取件核）：")
        for eid, sid, where, _ in [h for h in hit if h[2].startswith("pin:")]:
            print("    %-8s %-3s %s" % (eid, sid, where[4:]))
    wsq = [h for h in hit if h[3] == "ws"]
    if wsq:
        print("\n· 空位形态不齐（标点前/引号后多了原文没有的空格）—— 属转录杂质，应改：")
        for eid, sid, where, _ in wsq:
            print("    %s（%s，%s）" % (eid, sid, where))
    pun = [h for h in hit if h[3] == "punct"]
    if pun:
        print("\n· 仅差排版形态（页面是弯引号，引文写成直引号）—— 逐字引用应当改回页面形态：")
        for eid, sid, where, _ in pun:
            print("    %s（%s，%s）" % (eid, sid, where))
    if miss:
        print("\n❌ 失配明细（最长可匹配前缀 = 引文在快照中真实存在的部分）")
        for eid, sid, q, _ in miss:
            vis, emb = snap.get(sid, ("", ""))
            txt = (vis or "") + " " + (emb or "")
            for path, _d in pidx.get(srcs[sid]["url"].rstrip("/"), []):
                txt += " " + pin_texts(path)
            lo, hi = 0, len(q)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if q[:mid] in txt:
                    lo = mid
                else:
                    hi = mid - 1
            print("\n  %s（%s）" % (eid, sid))
            print("    引文：%s" % q[:160])
            print("    快照中能对上的只到：%r" % q[:lo][-70:])
    if unver:
        print("\n⚠ 不可复核（来源未取到快照）")
        for eid, sid, why in unver:
            print("    %s（%s）%s" % (eid, sid, why))
    print()
    # ★ 门必须能红：`punct` / `ws` 是**诊断层**，不是通过层。
    #   第一版把它们算作命中，于是在同一轮里掩盖了我自己造成的一次回归
    #   （批量空格正则删掉了右引号后的空格，条目从 exact 掉到 ws，而 exit 仍是 0）。
    #   逐字引用是这库的全部价值 —— 差一个字符就该红，并且要红得说明差在哪一层。
    #
    # ★ 第二版修的（2026-09-22）：**`--offline` 下 0 个来源被真抓，却退 0 报 ✅**，
    #   汇总行还写着「今日抓取：可见正文 38」。这与 `AGENTS.md` §2.4.2 记的那次事故
    #   是同一个形状 —— 那个脚本第一次运行就把「一次网络都没发」报成了「16 项全过」。
    #   同一个病活在同一个仓库的另一个检查器里。修法同款：结论行拆成纯函数，
    #   让反向对照能**直接断言这句话本身不许撒谎**。
    code, line = verdict(n_live, len(miss), len(unver), len(pun), len(wsq),
                         len(hit), len(entries))
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
