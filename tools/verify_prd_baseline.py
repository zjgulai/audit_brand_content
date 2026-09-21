#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_prd_baseline.py —— 上游 PRD 基线漂移检测（只读）

## 为什么需要它（2026-09-21）

2026-09-21 11:51 上游在群里明确说《内容审查 Agent PRD》v1.0
**「我后续会基于评估重新修改」**。也就是说：

> **这份基线会漂，是一件已经被预告的事，不是假设。**

而当时仓库里有的是：

| 有什么 | 在哪 |
|---|---|
| 拉正文的命令 | `python3 tools/lark_find.py readdoc <docx_token>` |
| 记了指纹的文件 | `PRD/feishu/索引-v1.json`（token / 字数 / sha256 / 字节数） |
| **会在它改版时变红的东西** | **没有** —— 那两个 sha256 全仓零消费者（grep 只命中它自己） |

所以「改版后重新拉一次基线并记新指纹」当时是一句**没有执行点的承诺**
（`AGENTS.md` §2.4：写进文档的每一条约束，必须能指出是哪一行在拦它）。
本脚本就是那一行。

## 三层判据，且**未测与通过必须长得不一样**（§2.4.1 第 4 行）

| 层 | 判据 | 要联网 | 红了说明什么 |
|---|---|---|---|
| **L1 结构** | 索引可解析、字段齐、副本存在 | 否 | 索引本身坏了/被改残了 |
| **L2 副本 = 指纹** | 落盘文件的 sha256 / 字节数 / 正文字数 == 索引读数 | 否 | **本地这一份被人动过**（或被 +4096 填充，见 §2.1） |
| **L3 上游 = 指纹** | 重拉 `raw_content` 的 sha256 == 索引读数 | 是 | **上游改版了** ← 本脚本存在的理由 |

**退出码**：`0` 全绿（含 L3 已测）· `1` 有红 · `2` **L3 未测**（网络/凭据不可用）。
`2` 不是通过 —— 把「我没测」报成「没问题」，正是 §2.4.1 那张表第 4 行的病。

## ★ 本脚本**只报不改**

红的动作是**人去重拉并记新指纹**，不是脚本自己把索引改成新值。
自动改写等于把「漂移」这件事抹掉 —— 而漂移本身就是本脚本要交出来的那个事实
（同 `verify_depad.py` 的 `--fix` 不同：那里的修复不销毁证据，这里会）。

## ★ 本脚本的盲区（写出来，免得它被当成「基线没问题」的全部证据）

它比的是**内容**（sha256 / 字数 / 字节数）。而本环境还有另一类故障是**内容对、视图不对**：
用 **Python 写出**的文件，shell 侧（`ls -l` / `wc -c` / `stat -f %z`）报的字节数会比
Python 实读的多 **4096**，`read` 工具据此判成 `binary file` —— **正文一个字读不出来**（§2.1）。
**B1–B3 对这类文件全是绿的**，因为字节确实没变。

**实测（2026-09-21，本脚本自己的反向对照干出来的）**：为了验证 B1 会红，我用
`Path.write_bytes()` 把 `PRD/feishu/内容审查Agent-PRD-v1.0.md` 改一个字节再改回来。
sha256 复原了、本脚本全绿 —— **但那个文件已经变成填充态**：

```
ls -l : 18710    wc -c : 18710    stat -f %z : 18710
python open().read() : 14614      索引 size_bytes : 14614      sha256 一致
```

是 `verify_depad.py` 抓到的，不是本脚本。**所以：动过 `PRD/feishu/` 之后必须另跑
`python3 tools/verify_depad.py`。**（更稳的做法：反向对照只在内存里做 —— `--controls` 就是
这么设计的；非要动盘就用 shell 的 `cp`/`sed`，别用 Python。）

用法：
  python3 tools/verify_prd_baseline.py              # L1 + L2 + L3
  python3 tools/verify_prd_baseline.py --offline    # 只 L1 + L2（不联网；**退出码 2**，L3 未测）
  python3 tools/verify_prd_baseline.py --controls   # 离线反向对照：断言每条判据真会红
  python3 tools/verify_prd_baseline.py -v           # 逐条打印通过项
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT / "PRD" / "feishu"
INDEX = BASE_DIR / "索引-v1.json"
CRED = Path(os.path.expanduser("~/.dsh/credentials/shouheng-lark.json"))
API = "https://open.feishu.cn/open-apis"

REQUIRED_FIELDS = ("file", "obj_token", "sha256", "chars", "size_bytes")


# ─────────────────────────── 纯判据（可离线喂样本，controls 靠它） ───────────────────────────

def judge(rec, disk, live):
    """纯函数：给定「索引读数 rec / 落盘字节 disk / 现场正文 live」，逐条判定。

    ★ 为什么拆成纯函数：反向对照要能在**不联网、不动盘**的前提下把已知坏样本喂进来，
      证明每条判据真会红。一个不会红的断言不算验证过它（§2.4.1）。
      `disk=None` = 副本不存在；`live=None` = 没测（未测 ≠ 通过）。
    """
    out = []          # (组, 断言名, ok, 详情)

    # ── L1 结构
    out.append(("L1", "A1 索引项有 obj_token", bool(rec.get("obj_token")),
                f"obj_token={rec.get('obj_token')!r}"))
    out.append(("L1", "A2 索引项有非空 sha256",
                isinstance(rec.get("sha256"), str) and len(rec.get("sha256") or "") == 64,
                f"sha256={str(rec.get('sha256'))[:16]}…"))
    out.append(("L1", "A3 索引项字段齐",
                all(k in rec for k in REQUIRED_FIELDS),
                "缺：" + (", ".join(k for k in REQUIRED_FIELDS if k not in rec) or "无")))
    out.append(("L1", "A4 副本存在", disk is not None, "PRD/feishu/" + str(rec.get("file"))))

    dsha = hashlib.sha256(disk).hexdigest() if disk is not None else None

    # ── L2 副本 = 指纹（离线）
    out.append(("L2", "B1 副本 sha256 = 索引指纹", disk is not None and dsha == rec.get("sha256"),
                f"索引 {str(rec.get('sha256'))[:16]}… / 落盘 {(dsha or '—')[:16]}…"))
    out.append(("L2", "B2 副本字节数 = size_bytes",
                disk is not None and len(disk) == rec.get("size_bytes"),
                f"索引 {rec.get('size_bytes')} / 落盘 {len(disk) if disk is not None else '—'}"
                "（差 4096 = §2.1 的填充病）"))
    n_chars = None
    if disk is not None:
        try:
            n_chars = len(disk.decode("utf-8"))
        except UnicodeDecodeError as e:
            n_chars = f"解码失败：{e}"
    out.append(("L2", "B3 正文字数 = chars", isinstance(n_chars, int) and n_chars == rec.get("chars"),
                f"索引 {rec.get('chars')} / 落盘 {n_chars}"))

    # ── L3 上游 = 指纹（在线）；live=None 表示没测，这里**不产出通过项**
    if live is not None:
        lsha = hashlib.sha256(live.encode("utf-8")).hexdigest()
        out.append(("L3", "C2 重拉正文非空", len(live) > 0, f"{len(live)} 字"))
        out.append(("L3", "C3 上游 sha256 = 索引指纹", lsha == rec.get("sha256"),
                    f"索引 {str(rec.get('sha256'))[:16]}… / 现场 {lsha[:16]}…"))
        out.append(("L3", "C4 上游字数 = chars", len(live) == rec.get("chars"),
                    f"索引 {rec.get('chars')} / 现场 {len(live)}"))
    return out


# ─────────────────────────── 网络（只有 L3 用） ───────────────────────────

def _req(url, payload=None, tok=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    r.add_header("Content-Type", "application/json; charset=utf-8")
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return json.loads(x.read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "body": e.read().decode()[:300]}
    except Exception as e:                                    # noqa: BLE001
        return {"_err": f"{type(e).__name__}: {e}"}


def tenant_token():
    """取 tenant_access_token。失败返回 (None, 原因) —— 调用方据此报「未测」。"""
    try:
        c = json.loads(CRED.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return None, f"凭据不可读（{CRED}）：{type(e).__name__}"
    r = _req(f"{API}/auth/v3/tenant_access_token/internal",
             {"app_id": c.get("app_id"), "app_secret": c.get("app_secret")})
    if r.get("code") != 0:
        return None, f"取 token 失败：{json.dumps(r, ensure_ascii=False)[:200]}"
    return r["tenant_access_token"], None


def fetch_raw(token, obj_token):
    """重拉 docx 正文（只读：raw_content）。附件类接口一次都不碰 —— AGENTS.md §2.6 红线。"""
    r = _req(f"{API}/docx/v1/documents/{obj_token}/raw_content", tok=token)
    if r.get("code") != 0:
        return None, f"raw_content 失败：{json.dumps(r, ensure_ascii=False)[:200]}"
    return (r.get("data") or {}).get("content", ""), None


# ─────────────────────────── 结论行（纯函数，好让 controls 断言它不撒谎） ───────────────────────────

def verdict(n_pass, n_fail, untested):
    """把「测了几项 / 红了几项 / 哪些没测」压成 (退出码, 结论一句话)。

    ★ 为什么单独拆出来：**第一版在 `--offline` 下打印了
      「✅ 16 项全过（含 L3：上游与指纹一致）」，而那一轮一次网络都没发。**
      也就是说 —— 这个为「别把没测报成没问题」而写的脚本，第一次运行就犯了那个病。
      拆成纯函数之后，`--controls` 可以直接断言**这句话本身**不会撒谎。
    """
    if n_fail:
        return 1, f"❌ {n_pass + n_fail} 项中 {n_fail} 项失败"
    if untested:
        return 2, (f"⚠️  已测 {n_pass} 项全过，但 L3 **未测**（{len(untested)} 份："
                   f"{', '.join(untested)}）—— 退出码 2，**不是通过**")
    return 0, f"✅ {n_pass} 项全过（含 L3：上游与指纹一致）"


# ─────────────────────────── 反向对照（离线） ───────────────────────────

def controls():
    """把已知坏样本喂进 judge()，断言它**真会红**；再喂原样，断言它**真的是绿的**。

    第 8 条不是凑数：一个恒红的检查器和恒绿的检查器一样没用 ——
    两边都要证明。
    """
    rec = {
        "file": "样本.md", "obj_token": "Tok" + "x" * 20,
        "sha256": hashlib.sha256(b"good").hexdigest(),
        "chars": 4, "size_bytes": 4,
    }
    good_disk, good_live = b"good", "good"

    def failed(res, name):
        """名字里含 name 的断言是否**存在且为假**。"""
        hits = [t for t in res if name in t[1]]
        return bool(hits) and not any(t[2] for t in hits)

    cases = [
        ("基线原样 → 必须全绿（证明判据不是恒红的）",
         lambda: all(t[2] for t in judge(rec, good_disk, good_live))),
        ("索引 sha256 改一位 → B1 红",
         lambda: failed(judge({**rec, "sha256": "0" * 64}, good_disk, good_live), "B1")),
        ("size_bytes +1 → B2 红",
         lambda: failed(judge({**rec, "size_bytes": 5}, good_disk, good_live), "B2")),
        ("chars +1 → B3 红",
         lambda: failed(judge({**rec, "chars": 5}, good_disk, good_live), "B3")),
        ("副本被改一个字 → B1 红",
         lambda: failed(judge(rec, b"gooD", None), "B1")),
        ("副本被 +4096 填充 → B2 红",
         lambda: failed(judge(rec, b"good" + b"\x00" * 4096, None), "B2")),
        ("副本不存在 → A4 红",
         lambda: failed(judge(rec, None, None), "A4")),
        ("obj_token 空 → A1 红",
         lambda: failed(judge({**rec, "obj_token": ""}, good_disk, None), "A1")),
        ("缺 size_bytes 字段 → A3 红",
         lambda: failed(judge({k: v for k, v in rec.items() if k != "size_bytes"}, good_disk, None), "A3")),
        ("★ 上游改版（现场正文多一个字）→ C3 红",
         lambda: failed(judge(rec, good_disk, "good!"), "C3")),
        ("没测 L3（live=None）→ **不产出任何 L3 通过项**",
         lambda: not any(t[0] == "L3" for t in judge(rec, good_disk, None))),
        # ★ 下面三条是这次真事故的回填：第一版 --offline 打印「含 L3：上游与指纹一致」
        ("★ --offline 的结论里**不许**出现「含 L3」",
         lambda: verdict(16, 0, ["a.md"]) == (2, verdict(16, 0, ["a.md"])[1])
         and "含 L3" not in verdict(16, 0, ["a.md"])[1]),
        ("L3 测过且全绿 → 退出码 0 且明说含 L3",
         lambda: verdict(23, 0, [])[0] == 0 and "含 L3" in verdict(23, 0, [])[1]),
        ("有红 → 退出码 1（哪怕同时有未测）",
         lambda: verdict(20, 3, ["a.md"])[0] == 1),
    ]

    print("=" * 72)
    print("verify_prd_baseline · 反向对照（离线，不联网、不动盘）")
    print("=" * 72)
    bad = 0
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok = bool(fn())
        except Exception as e:                                # noqa: BLE001
            ok, name = False, f"{name}（抛异常 {type(e).__name__}: {e}）"
        print(f"  {'✅' if ok else '❌'} [{i:2d}/{len(cases)}] {name}")
        bad += 0 if ok else 1
    print("-" * 72)
    if bad:
        print(f"❌ 反向对照 {len(cases)} 项中 {bad} 项失败 —— 判据有问题，别信它的绿")
        return 1
    print(f"✅ 反向对照 {len(cases)} 项全过（含「原样必须全绿」这一条）")
    return 0


# ─────────────────────────── 主流程 ───────────────────────────

def main():
    ap = argparse.ArgumentParser(description="上游 PRD 基线漂移检测（只读）")
    ap.add_argument("--offline", action="store_true", help="只跑 L1+L2，不联网")
    ap.add_argument("--controls", action="store_true", help="离线反向对照")
    ap.add_argument("-v", "--verbose", action="store_true", help="逐条打印通过项")
    args = ap.parse_args()

    if args.controls:
        return controls()

    PASS, FAIL = [], []

    def add(group, name, ok, detail):
        (PASS if ok else FAIL).append((group, name, detail))

    # ── L1 读索引
    try:
        idx = json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        add("L1", "A0 索引可解析", False, f"{INDEX.relative_to(ROOT)}：{type(e).__name__}: {e}")
        idx = None
    if idx is not None:
        add("L1", "A0 索引可解析", True, str(INDEX.relative_to(ROOT)))
        docs = idx.get("docs") or []
        add("L1", "A5 docs 非空", len(docs) > 0, f"{len(docs)} 份")
    else:
        docs = []

    # ── L3 取数（一次 token，逐份重拉）；失败/跳过 = 未测，不是通过
    live = {}
    untested = []
    if args.offline:
        # ★ 必须在这里就把 untested 填上。第一版是直接跳过整个块、untested 留空，
        #   于是末尾那行按「测过了」的口径打印 —— 未测被报成了通过。
        untested = [str(d.get("file")) for d in docs]
    elif not docs:
        pass
    else:
        tok, err = tenant_token()
        if tok is None:
            untested = [d.get("file") for d in docs]
            add("L3", "C1 取 tenant_access_token", False, err)
        else:
            add("L3", "C1 取 tenant_access_token", True, "ok")
            for d in docs:
                txt, err = fetch_raw(tok, d.get("obj_token"))
                if txt is None:
                    untested.append(d.get("file"))
                    add("L3", f"C0 重拉 {d.get('file')}", False, err)
                else:
                    live[d.get("file")] = txt

    # ── 逐份判定
    for d in docs:
        f = d.get("file")
        p = BASE_DIR / str(f)
        disk = p.read_bytes() if p.exists() else None
        res = judge(d, disk, live.get(f))
        for g, n, ok, det in res:
            add(g, f"{n} · {f}", ok, det)
        # ★ 这里**不**再补一条「见下方动作」的失败项：FAIL 里只能有真断言，
        #   合成一条凑数的失败会让「几项失败」这个数变成假的（§2.2 第 1 条）。

    # ── 输出
    print("=" * 72)
    print("上游 PRD 基线漂移检测 —— PRD/feishu/索引-v1.json")
    print(f"  索引抓取于 {idx.get('fetched_at') if idx else '—'}")
    print("=" * 72)
    if args.verbose:
        for g, n, det in PASS:
            print(f"  ✅ [{g}] {n}" + (f"   ({det})" if det else ""))
    groups = {}
    for g, n, _ in PASS:
        groups[g] = groups.get(g, 0) + 1
    for g in sorted(groups):
        print(f"  ✅ {g} 组：{groups[g]} 项通过")
    for g, n, det in FAIL:
        print(f"  ❌ [{g}] {n}   {det}")
    if untested:
        print(f"  ⚠️  L3 未测：{', '.join(str(x) for x in untested)} —— 未测不是通过")
    print("-" * 72)

    drifted = [d.get("file") for d in docs
               if d.get("file") in live
               and hashlib.sha256(live[d["file"]].encode("utf-8")).hexdigest() != d.get("sha256")]
    if drifted:
        for d in docs:
            if d.get("file") not in drifted:
                continue
            print(f"\n★★ 上游改版了：{d['file']}")
            print(f"   索引指纹 {d['sha256']}")
            print(f"   现场指纹 {hashlib.sha256(live[d['file']].encode('utf-8')).hexdigest()}")
            print("   动作（**别只改 sha256**，要重拉正文并重记全部读数）：")
            print(f"     python3 tools/lark_find.py readdoc {d['obj_token']} > "
                  f"'PRD/feishu/{d['file']}'")
            print("       ★ 用 shell 重定向落盘 —— Python 写盘会被 +4096 填充（AGENTS.md §2.1）")
            print("     # 再更新 索引-v1.json 的 sha256 / chars / size_bytes / obj_edit_time_bj")
            print("     python3 tools/verify_prd_baseline.py      # 复绿")
            print("     python3 tools/verify_depad.py            # 顺带确认没被填充")

    code, line = verdict(len(PASS), len(FAIL), untested)
    print("\n" + line)
    print("   （盲区：本脚本只看**内容**漂移。动过 PRD/feishu/ 之后另跑 "
          "`python3 tools/verify_depad.py` —— 填充态它结构性看不见）")
    return code


if __name__ == "__main__":
    sys.exit(main())
