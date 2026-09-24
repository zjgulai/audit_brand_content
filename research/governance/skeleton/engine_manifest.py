#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""engine_manifest.py —— 引擎制品的版本与内容指纹（ADR-0002 / ADR-0005 的前置）

★ 本模块存在的理由：**今天答不了「这条判定是哪版规则算出来的」。**

  盘点实测（`引擎产品化-接口盘点.md` §3）：
    · `rules-v1.json` 只有 `"$schema_version": "rules-v1"` —— 那是**结构版本名**，
      改内容不会改它；三份 JSON 里 `grep` 时间戳/哈希/`generated_at` **零命中**。
    · `rules-v1.json` 顶层连 `source` 块都没有。
    · 本目录**不是 git 仓库**（`git rev-parse` → fatal），外部兜底也没有。
    · 唯一存在的指纹停在上游：`research/live/LATEST.json` 有飞书快照的
      `content_sha256`，但它**没有传下来**。

  结论：可复现性成立（同输入重跑逐字一致），**可追溯性不成立**。
  ADR-0002 硬规则 2 写的是「没有 `snapshot_sha256` 的知识单元**不得进入任何报告
  或 Agent 的判定依据**」—— 三份 JSON 每一份都违反，且它们正是判定依据本身。

★ 一个刻意的区分：**能证明的** 与 **只是声明的**。

  `sha256(local file)` 是我们自己算的，钉死在字节上 —— 这是**证明**。
  「whitelist-v1.json 来自 snapshot-20260916T050845Z.json」写在 `source.snapshot`
  里，但没有任何东西校验过它 —— 这是**声明**。

  两份东西混在一个字段里，等于把声明洗成证明。所以本 manifest 把它们**分开存**：
  `artifacts[].sha256` 是证明（每次 `--check` 重算）；`upstream` 是声明
  （`integrity: "declared"`，且**不参与** `engine_version`）。要把它升级成证明，
  得有可复算的构建链 —— 那是 ADR-0012 的后续项，不是今天假装有。

用法：
  python3 engine_manifest.py --write    # 写 engine-manifest.json
  python3 engine_manifest.py --check    # 校验磁盘现状与 manifest 是否一致（不一致 exit 1）
  python3 engine_manifest.py            # 打印当前指纹（不写盘）

  from engine_manifest import engine_version, artifact_hashes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "engine-manifest.json"

# 判定链上被读取的每一个文件（盘点 §2.4 的完整依赖图，去掉纯构建期脚本）
ARTIFACTS = [
    ("rules", "rules-v1.json", "判险词 + 规则 + 兜底通道（唯一产生命中的来源）"),
    ("whitelist", "whitelist-v1.json", "放行词（豁免目标须落 auto_pass 带）"),
    ("context_guards", "context-guards-v1.json", "语境守卫词（取消/弱化主张，绝不放行）"),
    ("topic_tree", "topic-tree-v1.md", "主题树（Engine._validate_topics 的校验基准）"),
    # ★ 2026-09-16 加：处置分层映射原先**不在** engine_version 里，理由是
    #   「法务改本表即改处置，无需发版」。那句话本身没错，但漏了一半：
    #   它进的是 `verdict.layer` —— **verdict 会被 verdict_digest 钉住，版本号却不动**。
    #   于是法务按 Q2 把 catch_all 从 L3 改到 L4 之后：结论变了（digest 变）、
    #   版本不变（回执照样解析到「同一份配置」）。**digest 证明「结论不同」，
    #   版本却证明不了「为什么不同」。** 分层表是判定语义的一部分，必须进指纹。
    #   加进来不改变「改表不用改代码」：法务照旧直接编辑本文件。
    ("disposition_layers", "disposition-layers-v1.json",
     "处置分层映射（法务所有）：判定之后「谁必须看它」"),
    # ★ 2026-09-16 加：品线取值域进指纹的理由同上一项 —— score.Engine 读它
    #   （未知品线值不再静默过滤），读到的就是判定输入。
    ("product_lines", "product-lines-v1.json",
     "品线取值域（产品所有）与规则→品线归属（待填）"),
]

TREE_NODE_RE = re.compile(r"\*\*(T\d(?:\.\d){0,2})\*\*")

# ★ 判定引擎的**代码**制品。
#
#   为什么代码要单独指纹：ADR-0005 约束 5 把回执字段列成
#   `run_id / input_sha256 / rule_snapshot_sha256 / agent_version / model` ——
#   **`rule_snapshot_sha256` 与 `agent_version` 是两个字段**，不是一个。
#   批次 A 第一版只做了前者：改 judge.py 一行，`engine_version` 纹丝不动，
#   回执因此证明不了「哪版代码判的」。而契约字段的形状、聚合次序、
#   边界声明的措辞全在代码里 —— 代码变了，「同一条判定」的含义就变了。
#
#   所以两者都进版本，但**保持分离**：
#     engine_version  = 数据（规则 + 词表 + 主题树）→ 对应 rule_snapshot_sha256
#     code_version    = 代码（下面这 6 个文件）      → 对应 agent_version
#   一个回执带两个，才答得了「谁、用哪版规则、跑哪版代码，判了什么」。
CODE_FILES = ["matcher.py", "score.py", "judge.py", "vocab.py", "severity.py",
              "engine_manifest.py",
              # ★ T19（2026-09-23）：`evidence_origin.py` 决定**一条判定能不能到 PASS**
              #   （`may_finalize_pass`）。它改一个字节，判定结果就可能不同 ——
              #   所以它必须进代码指纹，否则「改了放行规矩但 code_version 没变」
              #   会让 `--check` 说出「一切正常」。
              "evidence_origin.py",
              # ★ T4（2026-09-23）：`clause_ref.py` 决定回执里**引用了哪几条条款**
              #   （`evidence_block()`）。它不改判定档位 —— 但它改**回执的证据链**，
              #   而「谁、用哪版规则、跑哪版代码，判了什么」里的最后一问，
              #   现在包含「依据《外部标准库》第 X 条」。它不进指纹的话，
              #   同一个 code_version 会对应两种不同的引用集，而 `--check` 照样说正常。
              "clause_ref.py"]

# 上游快照台账：本地制品与飞书快照之间的声明式引用，不是证明。见模块 docstring。
UPSTREAM_LATEST = HERE.parents[2] / "research" / "live" / "LATEST.json"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def _counts(key: str, path: Path) -> dict:
    """每个制品的**结构计量**。哈希变了但计量没变 = 大概率是改了一个词；两者都变 = 结构动了。

    计量不进 `engine_version`（哈希已经覆盖字节），它进 manifest 是为了**给人读**：
    法务看「26 条规则 / 92 个守卫词」比看 64 位十六进制有意义。
    """
    if key == "topic_tree":
        return {"nodes": len(set(TREE_NODE_RE.findall(path.read_text(encoding="utf-8"))))}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if key == "rules":
        rules = doc.get("rules", [])
        return {
            "rules": len(rules),
            "enabled": sum(1 for r in rules if r.get("enabled", True)),
            "is_modifier": sum(1 for r in rules if r.get("is_modifier")),
            "with_escalation": sum(1 for r in rules if "escalation" in r),
            "catch_all": 1 if doc.get("catch_all") else 0,
        }
    if key == "whitelist":
        words = doc.get("words", [])
        return {
            "words": len(words),
            "active": sum(1 for w in words if w.get("status") == "active"),
            "quarantined": sum(1 for w in words if w.get("status") == "quarantined"),
        }
    if key == "product_lines":
        vals = doc.get("values") or []
        asg = {k: v for k, v in (doc.get("assignments") or {}).items()
               if not str(k).startswith("$")}
        return {
            "status": doc.get("status"),
            "values": len(vals),
            "placeholders": len(doc.get("$placeholders_excluded") or []),
            "rules_scoped": len(asg),
        }
    if key == "disposition_layers":
        mp = doc.get("mapping") or {}
        esc = doc.get("escalate_if") or []
        return {
            "status": doc.get("status"),
            "layers": len(doc.get("layers") or []),
            "mappings": len(mp),
            "escalations": len(esc),
            "escalations_enabled": sum(1 for e in esc if e.get("$enabled")),
        }
    if key == "context_guards":
        words = doc.get("words", [])
        return {
            "words": len(words),
            "active": sum(1 for w in words if w.get("status") == "active"),
            "wired": sum(1 for w in words if w.get("wired")),
            "pending": sum(1 for w in words if w.get("status") == "pending"),
        }
    return {}


def compute() -> dict:
    """重算当前磁盘状态。**不含** `generated_at`，因此本函数是纯函数、可复现。"""
    arts = {}
    lines = []
    for key, rel, why in ARTIFACTS:
        p = HERE / rel
        if not p.exists():
            raise SystemExit(f"❌ 缺制品：{p} —— 判定链不完整，拒绝产出 manifest。")
        b = p.read_bytes()
        h = sha256_bytes(b)
        arts[key] = {
            "file": rel,
            "bytes": len(b),
            "sha256": h,
            "why": why,
            "counts": _counts(key, p),
        }
        lines.append(f"{key}\t{h}")

    # engine_version = 四个制品指纹的确定性折叠。
    # ★ 只吃 sha256，不吃文件名顺序、不吃 generated_at、不吃计量 ——
    #   任何一项进来都会让「同样内容算出不同版本号」。
    engine_version = sha256_bytes("\n".join(sorted(lines)).encode("utf-8"))[:16]

    # 代码指纹：与数据指纹同法，但**不合并进 engine_version** —— 见 CODE_FILES 的说明。
    code = {}
    clines = []
    for rel in CODE_FILES:
        f = HERE / rel
        if not f.exists():
            continue
        h = sha256_file(f)
        code[rel] = {"sha256": h, "bytes": f.stat().st_size}
        clines.append(f"{rel}\t{h}")
    code_version = sha256_bytes("\n".join(sorted(clines)).encode("utf-8"))[:16]

    up = {"integrity": "declared", "note": (
        "以下上游引用**未经校验**：whitelist/context-guards 里有 source.snapshot 文件名，"
        "rules-v1.json 连文件名都没有。把它们当证明用等于把声明洗成证明。"
        "升级为证明需要可复算的构建链（ADR-0012 后续项）。"
    )}
    if UPSTREAM_LATEST.exists():
        try:
            latest = json.loads(UPSTREAM_LATEST.read_text(encoding="utf-8"))
            up["snapshot"] = latest.get("latest")
            up["captured_at_utc"] = latest.get("captured_at_utc")
            up["feishu_content_sha256"] = {
                k: v.get("content_sha256") for k, v in (latest.get("sources") or {}).items()
            }
            up["_found"] = True
        except (json.JSONDecodeError, OSError) as e:
            up["_error"] = f"LATEST.json 读取失败：{e}"
            up["_found"] = True
    else:
        up["_found"] = False
        up["_note"] = "未找到 research/live/LATEST.json，上游引用整体缺失。"

    return {"engine_version": engine_version, "code_version": code_version,
            "artifacts": arts, "code": code, "upstream": up}


HISTORY_PATH = HERE / "_data" / "manifest-history.jsonl"


def archive_previous() -> str | None:
    """把**正要被覆盖**的 manifest 追加到历史账本。返回归档的 engine_version。

    ★ 为什么必须有这一步：回执里写着 `engine_version`，而 manifest 只有一个文件。
      重新固化一次，所有旧回执就指向一份**已经不存在**的规则集 ——
      「这条判定是哪版算出来的」会从「能答」退化成「曾经能答」。
      归档把「指向不存在」变成「指向历史里的一次快照」。

    幂等：与历史最后一条同版本则不再追加（重复跑 --write 不产生噪声）。
    """
    if not MANIFEST_PATH.exists():
        return None
    old = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    last = None
    if HISTORY_PATH.exists():
        lines = [ln for ln in HISTORY_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            try:
                last = json.loads(lines[-1])
            except json.JSONDecodeError:
                last = None
    if last and (last.get("engine_version"), last.get("code_version")) == (
            old.get("engine_version"), old.get("code_version")):
        return None
    from datetime import datetime, timezone

    rec = dict(old)
    rec["$archived_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return old.get("engine_version")


def resolve_version(engine_version: str, code_version: str | None = None, *,
                    manifest_path=None, history_path=None) -> dict:
    """反查「当时那份规则集」。**默认口径是 (engine_version, code_version) 成对匹配。**

    ★ 2026-09-23（Q43 = 选项 A）—— 本函数此前的实现是**只按 engine_version 单键**回查、
      并**正序取第一条命中**，而归档（`archive_previous()`）是按**成对**判、成对写的：
      两者不对称。实测已踩到两次 —— 同一个 `engine_version` 在历史里并存两条不同
      `code_version`（`a3218e7f…` 一次、`b990f681…` 一次），此后按单键反查会取到
      **旧的那条**，而返回的东西看起来完全正常：`code_version` 悄悄是错的。

    ★ 它**永不返回 None**：「查到几条」与「账本读没读得出」是**三件不同的事**
      （有 / 没有 / **未测**），混进同一个 `None` 就等于把「未测」写成「没有」
      （`AGENTS.md` §2.7 的 E1 口径：取不到的读数必须说「未测」，不许空着也不许当 0）。

    ★ 调用点：`tools/push_receipts.py` 的 `traceability()` —— 每条**待送**回执送出去之前
      核一次「当时那份规则集还查得到吗」。没有那个调用点，`--check` 失败时那段
      「重新固化不会让旧回执失效」的提示就只是一句**没有任何东西在跑**的话（§2.4.2）。

    返回：
      match              成对命中**唯一**那条；0 条或多条都是 None
      matches            全部命中（成对口径通常 0/1 条；单键口径可能多条）
      sources            与 matches 对齐的 `"current"` / `"history"`
      n                  len(matches)
      key                `"pair"` | `"engine_only"`
      ambiguous          命中 > 1 条 → True。★ 此时一律**不许挑第一条**
      history_readable   归档账本读得出吗。False = **未测**，不是「没有」
      note               人读的一句话（含坏行数 / 歧义说明）
    """
    mp = Path(manifest_path) if manifest_path else MANIFEST_PATH
    hp = Path(history_path) if history_path else HISTORY_PATH
    rows: list = []                      # [(where, record)]
    notes: list = []
    history_readable = True

    try:
        if mp.exists():
            rows.append(("current", json.loads(mp.read_text(encoding="utf-8"))))
        else:
            notes.append("当前 manifest 不存在")
    except (OSError, ValueError) as e:                                   # noqa: BLE001
        history_readable = False
        notes.append(f"当前 manifest 读不出：{e}")

    bad_lines = 0
    try:
        if hp.exists():
            for ln in hp.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                try:
                    rows.append(("history", json.loads(ln)))
                except json.JSONDecodeError:
                    bad_lines += 1
        else:
            # ★「不存在」不等于「空」：账本是本机唯一副本（.gitignore），`receipts.LOSS.md`
            #   记过一次真丢 —— 所以这里落未测，不落「查过了，没有」。
            history_readable = False
            notes.append("归档账本不存在（可能从未归档过，也可能是丢了 —— 那是本机唯一副本）")
    except OSError as e:                                                 # noqa: BLE001
        history_readable = False
        notes.append(f"归档账本读不出：{e}")

    if bad_lines:
        # 有解析不了的行 → 我不能声称「历史我都查过了」，这就是未测。
        history_readable = False
        notes.append(f"归档账本有 {bad_lines} 行解析不了")

    key = "pair" if code_version else "engine_only"
    pairs = [(w, r) for w, r in rows if r.get("engine_version") == engine_version
             and (code_version is None or r.get("code_version") == code_version)]
    hits = [r for _, r in pairs]
    sources = [w for w, _ in pairs]

    n = len(hits)
    ambiguous = n > 1
    match = hits[0] if n == 1 else None
    if ambiguous:
        cvs = "、".join(sorted({str(h.get("code_version"))[:8] + "…" for h in hits}))
        notes.append(
            f"命中 {n} 条，各有不同的 code_version（{cvs}）—— ★ 旧实现在这里会**静默返回"
            f"最早那一条**，于是 code_version 是错的；现在返回 match=None + ambiguous=True，"
            f"要哪一条就把 code_version 一起传进来"
        )
    elif key == "engine_only":
        notes.append("单键口径：本次恰好只命中 1 条 —— 但成对口径才是默认，"
                     "回执里就带着 code_version，调用方应当把它一起传进来")
    if n == 0:
        notes.append("一条都没命中")

    return {"match": match, "matches": hits, "sources": sources, "n": n, "key": key,
            "ambiguous": ambiguous, "history_readable": history_readable,
            "note": "；".join(notes)}


def write_manifest(computed: dict | None = None, generated_at: str | None = None) -> dict:
    """写盘。`generated_at` 是**唯一**的非确定性字段，且不参与 `engine_version`。"""
    from datetime import datetime, timezone

    doc = computed or compute()
    out = {
        "$schema_version": "engine-manifest-v1",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_version": doc["engine_version"],
        "code_version": doc["code_version"],
        "artifacts": doc["artifacts"],
        "code": doc["code"],
        "upstream": doc["upstream"],
    }
    archive_previous()
    MANIFEST_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out


def load_manifest() -> dict:
    """读 manifest。**不存在即硬失败** —— 静默返回空 dict 会让引擎以为自己是 v0。"""
    if not MANIFEST_PATH.exists():
        raise SystemExit(
            "❌ 找不到 engine-manifest.json。判定引擎不能在没有版本指纹的情况下产出结论"
            "（ADR-0002 硬规则 2）。先跑：python3 engine_manifest.py --write"
        )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def engine_version() -> str:
    return load_manifest()["engine_version"]


def artifact_hashes() -> dict:
    return {k: v["sha256"] for k, v in load_manifest()["artifacts"].items()}


def check() -> tuple[bool, list[str]]:
    """磁盘现状 vs manifest。返回 (是否一致, 人读的差异行)。"""
    diffs: list[str] = []
    if not MANIFEST_PATH.exists():
        return False, ["manifest 不存在"]
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cur = compute()
    for key, a in cur["artifacts"].items():
        old = (m.get("artifacts") or {}).get(key)
        if old is None:
            diffs.append(f"{key}: manifest 里没有这个制品")
            continue
        if old.get("sha256") != a["sha256"]:
            diffs.append(
                f"{key}: sha256 不符 manifest={old.get('sha256','?')[:12]}… "
                f"disk={a['sha256'][:12]}…（{old.get('bytes','?')}B → {a['bytes']}B）"
            )
        elif (old.get("counts") or {}) != (a.get("counts") or {}):
            diffs.append(f"{key}: 字节相同但计量不同（不可能，除非 manifest 被手改）")
    if m.get("engine_version") != cur["engine_version"]:
        diffs.append(
            f"engine_version 不符 manifest={m.get('engine_version')} disk={cur['engine_version']}"
        )

    # ★ 2026-09-17 补：`code_version` 此前**只写不校**。
    #
    #   改一个判定链上的 .py（本文件自己也是 6 个之一），`code_version` 立刻过期，
    #   而 `--check` 照旧 exit 0 —— manifest 于是把「哪版代码判的」（agent_version）
    #   记成假话，且没有任何东西会红。这正是 ADR-0012 §166 要防的那件事
    #   （「改一行 judge.py，engine_version 纹丝不动」），只防住了一半：
    #   版本分离做了，校验只做了数据那一半。
    if m.get("code_version") != cur["code_version"]:
        stale = [rel for rel, v in cur["code"].items()
                 if (m.get("code") or {}).get(rel, {}).get("sha256") != v["sha256"]]
        diffs.append(
            f"code_version 不符 manifest={m.get('code_version')} disk={cur['code_version']}"
            + (f"（变了的：{'、'.join(stale)}）" if stale else "")
        )
    return (not diffs), diffs


def main() -> int:
    ap = argparse.ArgumentParser(description="引擎制品版本与内容指纹")
    ap.add_argument("--write", action="store_true", help="写 engine-manifest.json")
    ap.add_argument("--check", action="store_true", help="校验磁盘现状与 manifest 一致")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.write:
        out = write_manifest()
        print(f"✓ 已写 {MANIFEST_PATH.relative_to(HERE.parents[2])}")
        print(f"  engine_version = {out['engine_version']}   （数据：规则+词表+主题树）")
        print(f"  code_version   = {out['code_version']}   （代码：{len(out['code'])} 个文件）")
        for k, v in out["artifacts"].items():
            print(f"  {k:16s} {v['sha256'][:16]}…  {v['bytes']:>7d}B  {v['counts']}")
        return 0

    if a.check:
        ok, diffs = check()
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
        if a.json:
            print(json.dumps({"ok": ok, "diffs": diffs,
                              "manifest_engine_version": m.get("engine_version"),
                              "disk_engine_version": compute()["engine_version"]},
                             ensure_ascii=False, indent=2))
        elif ok:
            print(f"✓ 一致  engine_version = {m.get('engine_version')} · "
                  f"code_version = {m.get('code_version')}（生成于 {m.get('generated_at','?')}）")
        else:
            print("✗ 磁盘上的判定制品已偏离 manifest：", file=sys.stderr)
            for d in diffs:
                print(f"    {d}", file=sys.stderr)
            # ★ 这段提示原文写的是「重新固化会让所有引用旧 engine_version 的回执指向
            #   一份已不存在的规则集——这是特性，不是麻烦」，**与 archive_previous()
            #   的实现直接矛盾**：--write 正是先把「正要被覆盖的」manifest 追加进
            #   `_data/manifest-history.jsonl`，resolve_version() 再按
            #   **(engine_version, code_version) 成对**反查。ADR-0012 §6.1 在 2026-09-16
            #   就记过这一条，并实测过 5 条旧回执在四次重新固化后仍可逐条解析。
            #   ★ 2026-09-23（Q43）补：这段提示原先只承诺「可按 engine_version 反查」，
            #     而那个口径在历史里并存两条同 ev 记录时会取到旧的那条；且
            #     resolve_version() 当时**一个调用点都没有** —— 一句对外说过的话
            #     没有任何东西在跑它（AGENTS.md §2.4.2）。现在键与调用点都补上了。
            #   这句话 2026-09-17 改正 —— 它的代价是可量的：它让「该不该重新固化」
            #   看起来像一次有损操作，于是**没人敢固化**，漂移就这么留了下来。
            print("\n  处置：确认改动是有意的 → 跑 --write 重新固化；否则回滚制品。\n"
                  "  ★ 重新固化**不会**让旧回执失效：--write 先把「正要被覆盖的」manifest\n"
                  "    追加进 _data/manifest-history.jsonl，旧回执可按\n"
                  "    **(engine_version, code_version) 成对**反查历史（ADR-0012 §6.1）。\n"
                  "  ★ 这句话的执行点：`resolve_version()` 的调用点在 tools/push_receipts.py\n"
                  "    —— 每条待送回执送出去之前核一次「当时那份规则集还查得到吗」。\n"
                  "    ★ 只给 engine_version 的单键口径，在历史里并存两条同 ev 记录时\n"
                  "      **返回 ambiguous、不挑第一条** —— 那正是 Q43 修掉的错读数。\n"
                  "  ★ 但那份账本目前**不在版本控制内**（.gitignore）—— 归档是本机唯一副本；\n"
                  "    读不到时落**未测**，而不是「查过了，没有」。\n"
                  "    详见 ADR-0013 §十七 与 _data/receipts.LOSS.md。", file=sys.stderr)
        return 0 if ok else 1

    cur = compute()
    if a.json:
        print(json.dumps(cur, ensure_ascii=False, indent=2))
    else:
        print(f"engine_version = {cur['engine_version']}   （数据）")
        print(f"code_version   = {cur['code_version']}   （代码）")
        for k, v in cur["artifacts"].items():
            print(f"  {k:16s} {v['sha256'][:16]}…  {v['bytes']:>7d}B  {v['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
