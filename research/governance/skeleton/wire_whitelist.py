#!/usr/bin/env python3
"""wire_whitelist.py —— 白名单与规则的接线校验（ADR-0008 的实现）

## 自证入口（离线；2026-09-22 加）

    python3 research/governance/skeleton/wire_whitelist.py --controls

7 项，**全程在 tempfile 的临时目录里做，一个字节都不落进仓库**：
  C1 正样本（T9 已是纯主题）→ 必须**不写回、不备份**
  C2 坏样本（T9 有词 + 预置一个已存在的 `rules-v1.json.bak`）→ 必须写回，且**必须产生
     一份带时间戳的新备份**，且那份备份的**内容 == 运行前的 rules-v1.json**，
     且那份**旧的 `.bak` 一个字节都不许动**（这正是旧实现恒假的那道门）
  C3 连跑第二次 → 不许再写、不许再备份（量出来的「重跑会发生什么」）
  C4 同一秒内备份两次 → 两个路径必须不同（不许互相覆盖）
  C5 写回后：**外部 `stat` 的大小 == 真实大小**（无填充）—— 样本用 `.md` 后缀，
     因为**只有 `.md`/`.sh` 会被这个环境填充**（见 tools/depad.py 的实测矩阵）
  C6 反向对照：把 depad 关掉，C5 必须红；若本机根本没复现填充，则落**未测（退 2）**
     而不是通过 —— 一个证不了的断言不许报绿

不带 `--controls` 才是真的跑接线校验（那时**可能写回** `rules-v1.json`）。

修的是事故 B：现网白名单没有程序化通道，靠人把词抄进各规则的 `豁免词`。
26 词只有 10 个抄到了，14 个孤儿；抄漏的 `reduces pain` 直接变成 EB-R011。

★ 设计修正（本人第一版写错了，记录在此）：
  第一版新建了一个并行的 `exempt_band` 字段，结果撞出 8 处「同一词既放行又降级」。
  查证后发现**骨架本来就是自洽的** —— `downgrade_band` 一个字段承担两条通道，
  由 `effect` 字符串的**箭头右侧**决定落点：
      "auto_reject → auto_pass"      落点 auto_pass    （真放行）
      "manual_review → auto_pass"    落点 auto_pass    （真放行）
      "auto_reject → manual_review"  落点 manual_review（真降级）
  10 个手抄白名单词全部落在 auto_pass 带里，4 个隔离词落在 manual_review 带里 —— 无冲突。
  所以正确的动作是**校验**既有结构，不是新建重复字段。

  （顺带：`downgrade_band` 这个名字让通道语义藏在字符串里，是「同一字段装两种机制」
    的第三处实例，与 `安全词`、`豁免词` 同病。改名会让 score.py 的
    in_downgrade_band 失效，属独立变更，此处只标注不动手。）

本脚本做两件事：
  1. 把 T9.objective-parameter 的 `match.keywords` 清空，还原成纯主题节点。
     设计文档 §2.2.1 原话：「T9 是一个主题，不是一张白名单」。
  2. 校验：白名单每个 active 词的豁免目标，确实落在 effect 指向 auto_pass 的带里。

## ★ 重跑到底会发生什么 —— 2026-09-22 逐条实测，替换掉原先那句「幂等：重复运行结果一致」

原先那句写得像「随便跑，没有副作用」。实测下来它**只对了一半**：

1. **第一次运行确实是「写」**：T9 还持有白名单词时，它清空 `match.keywords` 并
   **覆盖写回** `rules-v1.json`
   （实测：41656B → 41130B，sha256 `ad67c9bd…` → `03bc25bf…`）。
2. **第二次起是「只读校验」**：`match.keywords` 已是 `[]` 时 `changed == 0`，
   于是**不写回、也不产生备份**，只跑 ②③④ 三段校验
   （实测：第二次打印 `match.keywords: 0 → 0`，且**没有**「已写回」那一行，
   `rules-v1.json` 的 sha256 前后不变）。

所以准确的说法是：**「写回」这一步是幂等的（第一次之后就不会再有第二次），
但「运行」本身在第一次是有副作用的。「结果一致」指的是文件内容，不是「什么都没发生」。**

## ★ 备份这道门原先**恒假**（2026-09-22 修）

旧代码是 `if not BAK.exists(): <备份>`，而 `rules-v1.json.bak`
**已经被 git 跟踪入库**（`git ls-files` 的输出里有它），所以 `BAK.exists()` 永远为真 ——
**备份永远不会发生，而且一声不响**。实测两次：

* 把 `.bak` 换成一个 37 字节的哨兵，跑一次**会写回**的运行：
  `rules-v1.json` 的 sha256 从 `ad67c9bd…` 变成 `03bc25bf…`，
  `.bak` 的 sha256 **一个字节没动**（还是 `0d30ad04…`），输出里**没有**「备份 →」那一行。
* 把 `.bak` 删掉再跑：第一次运行生成了备份；**第二次运行又改了 `rules-v1.json`
  （`d91a3a1b…` → `04b30a95…`）而 `.bak` 没有被刷新**（停在 `99da09c9…`）。
  ——「唯一备份」是用一次就作废的。

现在的判据（**这一行在拦它**）：`backup_before_write()` ——
**只在「真的要覆盖文件」的那一刻调用，而每次调用都必然产生一个带时间戳的新文件**；
不需要写回时**明说**为什么没有备份，不再静默跳过。
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE / "rules-v1.json"
WL = HERE / "whitelist-v1.json"
# 注意：**没有** `BAK = HERE / "rules-v1.json.bak"` 这个常量了。
# 旧版就是拿它做备份门的（`if not BAK.exists()`），而那个文件已被 git 跟踪、永远存在 ——
# 于是一道看起来有保护、实际恒假的门。备份的落点现在由 backup_before_write() 现算。


def _tools_dir(start):
    """从本文件往上找 `tools/depad.py` —— 不写死层级，挪目录也不会静默失效。"""
    for p in [start] + list(start.parents):
        if (p / "tools" / "depad.py").exists():
            return str(p / "tools")
    raise SystemExit(
        "❌ 找不到 tools/depad.py（从 %s 逐级往上都没有）—— 本脚本要在仓库里跑；\n"
        "   如果它被复制到了仓库外，请把 tools/depad.py 一起带上。" % start)


sys.path.insert(0, _tools_dir(HERE))
from depad import depad, external_size, sha256  # noqa: E402

TOPIC_ONLY_KEY = "T9.objective-parameter"


def band_target(rule):
    """`downgrade_band.effect` 的箭头右侧 = 该带真正的落点通道。"""
    eff = str((rule.get("downgrade_band") or {}).get("effect") or "").strip()
    if "→" in eff:
        return eff.split("→")[-1].strip()
    if eff in ("none", ""):
        return "none"
    return eff


def backup_before_write(rules_path, now=None):
    """写回**之前**留一份**带时间戳**的备份。**每一次调用都真的产生一个新文件。**

    ★ 这里是那道曾经恒假的门的执行点。旧写法 `if not BAK.exists()` 的病不在「判断写错了」，
    而在**判据的对象选错了**：它问的是「某个固定文件在不在」，而 `rules-v1.json.bak`
    早就被 git 跟踪入库了 —— 于是**第一次运行之前门就是关着的**，而且关得没有声音。
    正确的判据是「**这一次写回之前，有没有留下这一份内容**」，答案只能是「留」。
    """
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    dst = rules_path.with_name("%s.%s.bak" % (rules_path.name, stamp))
    n = 1
    while dst.exists():          # 同一秒里连跑两次也不许覆盖
        n += 1
        dst = rules_path.with_name("%s.%s-%d.bak" % (rules_path.name, stamp, n))
    shutil.copy2(str(rules_path), str(dst))
    return dst


def run(rules_path=None, wl_path=None, out=print, do_write=True, depad_fn=None):
    """跑一次接线校验。返回 dict（`rc` / `changed` / `wrote` / `backup` / …）。

    `depad_fn` 与 `out` 可注入 —— `--controls` 靠前者做反向对照、靠后者把输出吞掉。
    """
    rules_path = Path(RULES if rules_path is None else rules_path)
    wl_path = Path(WL if wl_path is None else wl_path)
    depad_fn = depad if depad_fn is None else depad_fn

    wl = json.loads(wl_path.read_text())
    doc = json.loads(rules_path.read_text())
    rules = {r["rule_key"]: r for r in doc["rules"]}

    res = {"changed": 0, "wrote": False, "backup": None, "depad_err": None,
           "keep": [], "old_n": 0, "missing": [], "mismatched": [], "ok": [],
           "bad_q": [], "rc": 0}

    # ── 1. T9 还原成纯主题节点 ────────────────────────────────────
    out("")
    out("① T9 还原为纯主题节点（设计文档 §2.2.1：T9 是主题，不是白名单）")
    t9 = rules.get(TOPIC_ONLY_KEY)
    if t9 is None:
        out("   ⚠ 找不到 %s" % TOPIC_ONLY_KEY)
    else:
        wl_lower = {e["word"].lower() for e in wl["words"]}
        old_kw = list((t9.get("match") or {}).get("keywords") or [])
        keep = [k for k in old_kw if k.lower() not in wl_lower]
        if old_kw:
            t9.setdefault("match", {})["keywords"] = keep
            res["changed"] += 1
        t9["topic_only"] = True
        t9["$topic_only_note"] = [
            "★ ADR-0008：本节点是**主题**，不持有词表，不产生命中。",
            f"原 {len(old_kw)} 个白名单词已迁出至 whitelist-v1.json（独立表）。",
            "设计文档 §2.2.1：「T9 是一个主题，不是一张白名单」。",
            "此前用 is_modifier 在运行时兜住 —— 那是开关不是结构：词仍在同表同字段，",
            "任何 `SELECT 检测关键词` 仍会取到它们，本项目 56/57 条误报即由此而来。",
        ]
        t9.pop("$is_modifier_note", None)
        out("   match.keywords: %d → %d" % (len(old_kw), len(keep)))
        res["old_n"], res["keep"] = len(old_kw), keep
        if keep:
            out("   ⚠ 仍有非白名单词残留（需人工确认归属）：%s" % (keep,))

    if res["changed"] and do_write:
        bak = backup_before_write(rules_path)
        res["backup"] = str(bak)
        out("")
        out("备份 → %s（带时间戳；每次写回都留一份，不因为「已有 .bak」就跳过）"
            % bak.name)
        rules_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        # 见 tools/depad.py：Python 写出的 .md/.sh 会被环境 +4096 填充成 read 工具打不开。
        # 本文件写的是 .json（实测不会被填充），这一步是**按规矩做的保险**，不是复现过的故障。
        res["depad_err"] = depad_fn(str(rules_path))
        if res["depad_err"]:
            out("   ⚠ %s" % res["depad_err"])
        res["wrote"] = True
        out("")
        out("已写回 %s（%d 处变更）" % (rules_path.name, res["changed"]))
    elif res["changed"]:
        out("")
        out("   （只校验：判定需要写回 %d 处，但**没有落盘、也没有备份**）" % res["changed"])
    else:
        out("   无变更 → **不写回、不备份**（备份只在真要覆盖文件的那一刻产生）")

    # ── 2. 接线校验：豁免目标必须落在 auto_pass 带 ──────────────────
    out("")
    out("② 接线校验：每个 active 白名单词的豁免目标，须落在 effect→auto_pass 的带里")
    for e in wl["words"]:
        if e["status"] != "active":
            continue
        targets = e.get("exempts_rule_keys") or []
        if not targets:
            res["missing"].append(e["word"])
            continue
        for rk in targets:
            r = rules.get(rk)
            if r is None:
                res["mismatched"].append((e["word"], rk, "规则不存在"))
                continue
            band_kw = {k.lower() for k in (r.get("downgrade_band") or {}).get("keywords", [])}
            tgt = band_target(r)
            if e["word"].lower() not in band_kw:
                res["mismatched"].append(
                    (e["word"], rk, "不在该规则的带里（带=%s）" % sorted(band_kw)))
            elif tgt != "auto_pass":
                res["mismatched"].append((e["word"], rk, "落在 %s 带，不是 auto_pass" % tgt))
            else:
                res["ok"].append((e["word"], rk))

    for w, rk in res["ok"]:
        out("   ✅ %-22s → %s（auto_pass）" % (w, rk))
    for w, rk, why in res["mismatched"]:
        out("   ❌ %-22s → %s：%s" % (w, rk, why))

    # ── 3. 隔离词的落点核对 ────────────────────────────────────────
    out("")
    out("③ 隔离词落点核对（不得落在 auto_pass 带）")
    for e in wl["words"]:
        if e["status"] != "quarantined":
            continue
        w = e["word"].lower()
        for rk, r in rules.items():
            band_kw = {k.lower() for k in (r.get("downgrade_band") or {}).get("keywords", [])}
            if w in band_kw:
                tgt = band_target(r)
                flag = "❌" if tgt == "auto_pass" else "✅"
                if tgt == "auto_pass":
                    res["bad_q"].append((e["word"], rk))
                out("   %s %-12s → %s（%s）" % (flag, e["word"], rk, tgt))

    # ── 4. 无受益人的豁免（交给法务）────────────────────────────────
    out("")
    out("④ ⚠ 无受益人的豁免 —— %d 词豁免了不存在的规则（需法务定夺，非代码可解）"
        % len(res["missing"]))
    out("   %s" % (res["missing"],))
    out("   两种可能，必须由法务选：")
    out("     (a) 该词本就不需要豁免 → 应从白名单删除")
    out("     (b) 该词豁免的规则缺失  → 应补一条判定规则")
    out("   现状是 (a)(b) 都不做，词躺在白名单里给人「已经处理过」的错觉。")

    out("")
    if res["mismatched"] or res["bad_q"]:
        out("结论：❌ 接线不一致 %d 处、隔离失效 %d 处"
            % (len(res["mismatched"]), len(res["bad_q"])))
        res["rc"] = 1
    else:
        out("结论：✅ 接线全部一致（%d 处）；%d 词待法务定性"
            % (len(res["ok"]), len(res["missing"])))
        res["rc"] = 0
    return res


# ═══════════════════════════════════════════════════════════════════════
#  --controls：离线反向对照（喂坏样本必须红，喂正样本必须绿）
# ═══════════════════════════════════════════════════════════════════════

def _quiet(*_a, **_k):
    pass


def _active_words(n=3):
    wl = json.loads(WL.read_text())
    return [e["word"] for e in wl["words"] if e["status"] == "active"][:n]


def _fixture(tmp, t9_keywords, suffix=".json"):
    """临时骨架目录：whitelist 用仓库里真实那份，rules 用真实那份 + 把 T9 的词塞回去。"""
    doc = json.loads(RULES.read_text())
    rules = {r["rule_key"]: r for r in doc["rules"]}
    t9 = rules[TOPIC_ONLY_KEY]
    t9.setdefault("match", {})["keywords"] = list(t9_keywords)
    t9.pop("topic_only", None)
    t9.pop("$topic_only_note", None)
    rp = Path(tmp) / ("rules-v1" + suffix)
    rp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    wp = Path(tmp) / "whitelist.json"
    shutil.copy(str(WL), str(wp))
    return rp, wp


def controls():
    """→ (n_pass, fails, untested)。全部在临时目录里做。"""
    import inspect
    import os
    import tempfile

    fails, untested, npass = [], [], 0
    gate = "backup_before_write"
    try:
        gate_line = inspect.getsourcelines(backup_before_write)[1]
    except Exception:                                     # noqa: BLE001
        gate_line = -1
    print("备份门的执行点：%s:%d %s()" % (Path(__file__).name, gate_line, gate))

    # ── C1 正样本：T9 已是纯主题 → 不许写、不许备份 ─────────────────
    d = tempfile.mkdtemp(prefix="wwctl-c1-")
    rp, wp = _fixture(d, [])
    pre = sha256(str(rp))
    r = run(rp, wp, out=_quiet)
    if r["changed"] == 0 and not r["wrote"] and not r["backup"] and r["rc"] == 0 \
            and sha256(str(rp)) == pre:
        npass += 1
        print("  ✅ C1 正样本（T9 已还原）→ 不写回、不备份、文件未动")
    else:
        fails.append(("C1", "T9 已还原却仍然写回/备份了：changed=%s wrote=%s backup=%s"
                      % (r["changed"], r["wrote"], r["backup"])))

    # ── C2 坏样本：预置一个已存在的 .bak + T9 有词 → 备份**必须**发生 ──
    d = tempfile.mkdtemp(prefix="wwctl-c2-")
    rp, wp = _fixture(d, _active_words())
    legacy = rp.with_name(rp.name + ".bak")
    legacy.write_text("SENTINEL-LEGACY-BACKUP-MUST-NOT-BE-TOUCHED\n")
    legacy_before = sha256(str(legacy))
    pre_content = rp.read_text()
    r = run(rp, wp, out=_quiet)
    bak = Path(r["backup"]) if r["backup"] else None
    if not r["wrote"]:
        fails.append(("C2", "T9 有白名单词却没写回：changed=%s" % r["changed"]))
    elif bak is None or not bak.exists():
        fails.append(("C2", "写回了却没有产生备份 —— 这正是旧实现恒假的那道门（%s:%d）"
                      % (Path(__file__).name, gate_line)))
    elif bak.read_text() != pre_content:
        fails.append(("C2", "新备份的内容 != 运行前的 rules-v1.json —— 备份的不是它要保护的东西"))
    elif sha256(str(legacy)) != legacy_before:
        fails.append(("C2", "那份历史 .bak 被改动了（它不该是备份的落点）"))
    else:
        npass += 1
        print("  ✅ C2 坏样本（.bak 已存在）→ 仍产生新备份 %s，内容 == 运行前；"
              "历史 .bak 未动" % bak.name)

    # ── C3 连跑第二次：不许再写、不许再备份 ────────────────────────
    d = tempfile.mkdtemp(prefix="wwctl-c3-")
    rp, wp = _fixture(d, _active_words())
    _quiet_r1 = run(rp, wp, out=_quiet)
    after1 = sha256(str(rp))
    r2 = run(rp, wp, out=_quiet)
    if r2["changed"] == 0 and not r2["wrote"] and not r2["backup"] and sha256(str(rp)) == after1:
        npass += 1
        print("  ✅ C3 第二次运行 → changed=0、不写回、不备份（「重跑会发生什么」是量出来的）")
    else:
        fails.append(("C3", "第二次运行仍然写了：changed=%s wrote=%s backup=%s"
                      % (r2["changed"], r2["wrote"], r2["backup"])))

    # ── C4 同一秒内备份两次 → 路径不许相同 ─────────────────────────
    d = tempfile.mkdtemp(prefix="wwctl-c4-")
    p = Path(d) / "x.json"
    p.write_text("A")
    now = datetime(2026, 9, 22, 14, 15, 16)
    b1 = backup_before_write(p, now=now)
    b2 = backup_before_write(p, now=now)
    if b1 != b2 and b1.exists() and b2.exists():
        npass += 1
        print("  ✅ C4 同秒内备份两次 → %s / %s（不覆盖）" % (b1.name, b2.name))
    else:
        fails.append(("C4", "同秒内两次备份落到同一个路径 —— 后一次把前一次覆盖了：%s" % b1))

    # ── C5 写回后不许有填充（样本必须用 .md：只有 .md/.sh 会被填充）──
    d = tempfile.mkdtemp(prefix="wwctl-c5-")
    rp, wp = _fixture(d, _active_words(), suffix=".md")
    r = run(rp, wp, out=_quiet)
    ext = external_size(str(rp))
    real = os.path.getsize(str(rp))
    if not r["wrote"]:
        fails.append(("C5", "样本没触发写回，这一项没测到东西"))
    elif ext is None:
        untested.append("C5：外部 stat 取不到读数（不是通过，也不是红）")
    elif ext != real:
        fails.append(("C5", "写回后仍被填充：外部 stat %sB / 真实 %sB（depad 没生效）"
                      % (ext, real)))
    else:
        npass += 1
        print("  ✅ C5 写回 .md 样本后无填充（外部 stat %sB == 真实 %sB）" % (ext, real))

        # ── C6 反向对照：把 depad 关掉，C5 必须红；红不了就是未测 ──
        d = tempfile.mkdtemp(prefix="wwctl-c6-")
        rp2, wp2 = _fixture(d, _active_words(), suffix=".md")
        run(rp2, wp2, out=_quiet, depad_fn=lambda _p: None)
        ext2 = external_size(str(rp2))
        real2 = os.path.getsize(str(rp2))
        if ext2 is None:
            untested.append("C6：外部 stat 取不到读数")
        elif ext2 == real2 + 4096:
            npass += 1
            print("  ✅ C6 关掉 depad 后样本确实被填充（stat %sB = 真实 %sB + 4096）"
                  "→ C5 不是恒真的" % (ext2, real2))
        else:
            untested.append(
                "C6：本机没有复现 +4096 填充（关掉 depad 后 stat %sB / 真实 %sB）—— "
                "C5 在当前环境下**证不了自己会红**，按 §2.4.2 落未测，不报绿" % (ext2, real2))
    return npass, fails, untested


def main():
    if "--controls" in sys.argv:
        print("=" * 72)
        print("wire_whitelist 自证 · 离线反向对照（全部在临时目录里做，不动仓库）")
        print("=" * 72)
        npass, fails, untested = controls()
        print("-" * 72)
        print("通过 %d 项 · 不通过 %d 项 · 未测 %d 项" % (npass, len(fails), len(untested)))
        for label, why in fails:
            print("  ❌ [%s] %s" % (label, why))
        for why in untested:
            print("  ⚠ 未测：%s" % why)
        if fails:
            print("\n❌ 备份门 / depad 的行为与文档对不上。")
            return 1
        if untested:
            print("\n⚠ 有读数没取到 —— 这不是通过（退 2，与 §2.4.2 同口径）。")
            return 2
        print("\n✅ 备份每次都发生且内容正确；重跑不写；同秒不覆盖；写回后无填充。")
        return 0

    res = run()
    return res["rc"]


if __name__ == "__main__":
    raise SystemExit(main())
