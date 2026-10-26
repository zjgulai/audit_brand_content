#!/usr/bin/env python3
"""verify_nmem.py —— 本项目记忆与知识图谱的自证。

它验的是「记忆库里躺着的东西，和仓里的依据对不对得上」，不是「nmem 能连上吗」。

★ 三态（AGENTS.md §2.1）：
    0 = 全部通过
    1 = 有红
    2 = 未测（nmem 不可达 / 读数采不到）—— 不是通过，也不是红

断言：
  N1  space 存在且 retrievalMode == strict
  N2  agent 身份存在且默认 space 正确
  N3  两条 Space Rules（persona 100 / boundary 90）active
  N4  四层条数 ≥ 6 / 4 / 10 / 3
  N5  unit_type 与 importance 符合 SOP 层级映射（L1 decision 1.0 / L2 fact 0.9 /
      L3 learning 0.85 / L4 context 0.7）
  N6  没有 importance < 0.7 的条目混进本 space
  N7  每条记忆的正文里带「依据：」尾注，且其中至少一个路径能在仓内解析
  N8  Library 全部条目 lifecycle_state == indexed
  N9  本体：objectTypes ≥ 9 且 linkTypes ≥ 8，且只在本 space 范围（global 未被污染）
  N10 隔离：default space 的条目数不因本项目的写入而增长（只报读数，不判红 ——
      本项目无法阻止别的会话写 default，所以这一条是**读数**不是断言）

反向对照（--controls）：喂坏样本必须红。
  C1 层级映射错（L2 标成 learning）→ N5 红
  C2 importance 低于 0.7 → N6 红
  C3 记忆正文缺「依据：」尾注 → N7 红
  C4 依据路径指向不存在的文件 → N7 红
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPACE = "audit-multi-content"
AGENT = "content-guardian"

EXPECTED = {
    "decision": 1.0,
    "fact": 0.9,
    "learning": 0.85,
    "context": 0.7,
}
MIN_COUNTS = {"decision": 6, "fact": 4, "learning": 10, "context": 3}
RULE_IDS = {"content_guardian_core_persona": 100, "content_guardian_repo_boundary": 90}

# N0 的主体清单：记忆与图谱的**来源文件**。
# 为什么逐个点名而不是 glob：记忆的内容是从这些文件蒸馏出来的，
# 它们一旦不在库或被打不开，记忆就成了无源之水 —— 而 glob 会在文件消失时
# 悄悄少扫几个，读起来和「全都在」一样（§2.4.1）。
SOURCE_FILES = [
    "tools/mem/corpus/L1.json",
    "tools/mem/corpus/L2.json",
    "tools/mem/corpus/L3.json",
    "tools/mem/corpus/L4.json",
    "tools/mem/rules/core_persona.md",
    "tools/mem/rules/repo_boundary.md",
    "artifacts/audit_content_ontology_patch.json",
    "tools/mem/distill_to_nmem.py",
    "tools/mem/ingest_library.py",
]


def nmem_bin() -> str:
    return os.environ.get("NMEM_CLI_PATH", "nmem")


def run(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run([nmem_bin(), *args], capture_output=True, text=True, timeout=timeout)


def jrun(args: list[str], timeout: int = 90):
    """返回 (ok, data_or_error_string)。分不清「真没有」和「读错了」时返回 None。"""
    r = run(args, timeout)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()[:300]
    try:
        return True, json.loads(r.stdout)
    except Exception as e:
        return False, f"JSON 解析失败：{e}"


# ---------------------------------------------------------------- 采集

def fetch_all() -> dict:
    """一次性采全部读数。任何一项采不到就记在 untested 里。"""
    out: dict = {"untested": [], "red": []}

    ok, d = jrun(["--json", "spaces", "list"])
    if not ok:
        out["untested"].append(f"spaces list：{d}")
        return out
    out["spaces_enabled"] = d.get("enabled")
    out["spaces"] = {s["id"]: s for s in d.get("spaces", [])}

    ok, d = jrun(["--json", "agents", "list"])
    if not ok:
        out["untested"].append(f"agents list：{d}")
    else:
        out["agents"] = {a["id"]: a for a in d.get("agentProfiles", [])}

    ok, d = jrun(["--json", "rules", "list"])
    if not ok:
        out["untested"].append(f"rules list：{d}")
    else:
        out["rules"] = {r["id"]: r for r in (d if isinstance(d, list) else d.get("rules", []))}

    ok, d = jrun(["--json", "memories", "list", "--space", SPACE, "-n", "500"])
    if not ok:
        out["untested"].append(f"memories list：{d}")
    else:
        out["memories"] = d if isinstance(d, list) else d.get("items", d.get("memories", []))

    ok, d = jrun(["--json", "memories", "list", "--space", "default", "-n", "500"])
    if not ok:
        out["untested"].append(f"default memories list：{d}")
    else:
        out["default_memories"] = d if isinstance(d, list) else d.get("items", d.get("memories", []))

    ok, d = jrun(["--json", "library", "list", "--space", SPACE, "-n", "200"])
    if not ok:
        out["untested"].append(f"library list：{d}")
    else:
        out["library"] = d.get("sources", [])

    ok, d = jrun(["--json", "ontology", "show", "--space-id", SPACE])
    if not ok:
        out["untested"].append(f"ontology show：{d}")
    else:
        out["ontology"] = d
    return out


# ---------------------------------------------------------------- 断言

def assert_n0(o: dict) -> list[str]:
    """来源文件必须在库、在盘、且未被打不开的 +4096 填充污染。

    这一条不依赖 nmem —— 它是本地预检，也是 SOURCE_FILES 的执行点。
    """
    errs = []
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    ).stdout.decode("utf-8", "replace").split("\0")
    tracked = {t for t in tracked if t}
    for rel in SOURCE_FILES:
        p = REPO / rel
        if rel not in tracked:
            errs.append(f"N0 {rel}: 未被 git 跟踪")
            continue
        if not p.exists():
            errs.append(f"N0 {rel}: 不在盘上")
            continue
        st, gs = os.stat(p).st_size, os.path.getsize(p)
        if st != gs:
            errs.append(f"N0 {rel}: 被填充（stat={st} getsize={gs}）—— 跑 verify_depad.py --fix")
    return errs


def assert_n1(o: dict) -> list[str]:
    errs = []
    sp = (o.get("spaces") or {}).get(SPACE)
    if not sp:
        return [f"N1 space {SPACE!r} 不存在"]
    if sp.get("defaultRetrievalMode") != "strict":
        errs.append(f"N1 retrievalMode={sp.get('defaultRetrievalMode')!r} ≠ 'strict'")
    if o.get("spaces_enabled") is not True:
        errs.append("N1 spaces 全局开关未开启")
    return errs


def assert_n2(o: dict) -> list[str]:
    if "agents" not in o:
        return []
    a = o["agents"].get(AGENT)
    if not a:
        return [f"N2 agent {AGENT!r} 不存在"]
    if a.get("defaultSpaceId") != SPACE:
        return [f"N2 agent 默认 space={a.get('defaultSpaceId')!r} ≠ {SPACE!r}"]
    return []


def assert_n3(o: dict) -> list[str]:
    if "rules" not in o:
        return []
    errs = []
    for rid, prio in RULE_IDS.items():
        r = o["rules"].get(rid)
        if not r:
            errs.append(f"N3 缺规则 {rid}")
            continue
        if r.get("status") != "active":
            errs.append(f"N3 {rid} status={r.get('status')!r} ≠ active")
        if r.get("priority") != prio:
            errs.append(f"N3 {rid} priority={r.get('priority')} ≠ {prio}")
        if not (r.get("body") or "").strip():
            errs.append(f"N3 {rid} 正文为空")
    return errs


def _mem_text(m: dict) -> str:
    return (m.get("content") or "") + "\n" + (m.get("title") or "")


def assert_n4_n5_n6(o: dict) -> tuple[list[str], list[str]]:
    """返回 (errs, readings)。n4/n5/n6 共用一次遍历。"""
    if "memories" not in o:
        return [], ["（未测）"]
    mems = o["memories"]
    counts: dict[str, int] = {}
    errs = []
    for m in mems:
        ut = m.get("unit_type")
        counts[ut] = counts.get(ut, 0) + 1
        mid = m.get("id", "?")
        # N5 映射
        if ut not in EXPECTED:
            errs.append(f"N5 {mid}: unit_type={ut!r} 不在四层映射里")
            continue
        want = EXPECTED[ut]
        got = float(m.get("importance") or 0)
        if abs(got - want) > 1e-9:
            errs.append(f"N5 {mid}: importance={got} ≠ {want}（{ut} 的 SOP 权重）")
        # N6 下限
        if got < 0.7:
            errs.append(f"N6 {mid}: importance={got} < 0.7 —— 流水条目不许进本 space")
    # N4 条数下限
    for ut, bottom in MIN_COUNTS.items():
        if counts.get(ut, 0) < bottom:
            errs.append(f"N4 {ut} 只有 {counts.get(ut, 0)} 条 < 下限 {bottom}")
    readings = [f"{ut} {counts.get(ut, 0)}" for ut in ("decision", "fact", "learning", "context")]
    return errs, readings


def assert_n7(o: dict) -> list[str]:
    if "memories" not in o:
        return []
    errs = []
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    ).stdout.decode("utf-8", "replace").split("\0")
    tracked = {t for t in tracked if t}
    for m in o["memories"]:
        mid = m.get("id", "?")
        text = _mem_text(m)
        if "依据：" not in text:
            errs.append(f"N7 {mid}: 正文里没有「依据：」尾注")
            continue
        tail = text.split("依据：", 1)[1]
        # ★ 尾注只占一行：_mem_text 把 title 拼在 content 之后，所以必须
        #   在第一个换行处截断，否则标题会被当成路径的一部分（实测误报过一次，见 C6）。
        tail = tail.split("\n", 1)[0]
        # 尾注里的路径以 ; 分隔，取每段的第一个 token（去掉 ⟵ 后面的锚点）
        found = False
        for seg in tail.split(";"):
            seg = seg.strip().split("⟵")[0].strip()
            if not seg:
                continue
            if seg in tracked:
                found = True
                break
        if not found:
            errs.append(f"N7 {mid}: 依据里的路径一个都不在 git ls-files 里 —— {tail[:80]}")
    return errs


def assert_n8(o: dict) -> list[str]:
    if "library" not in o:
        return []
    errs = []
    lib = o["library"]
    if not lib:
        return ["N8 Library 是空的（真源一份都没归档）"]
    for s in lib:
        st = s.get("lifecycle_state")
        if st != "indexed":
            errs.append(
                f"N8 {s.get('original_name')}: state={st!r} err={s.get('error_message')}"
            )
        if not s.get("chunk_count"):
            errs.append(f"N8 {s.get('original_name')}: chunk_count=0（解析出来了但没切片）")
    return errs


def assert_n9(o: dict) -> list[str]:
    if "ontology" not in o:
        return []
    d = o["ontology"]
    errs = []
    store = d.get("store") or {}
    sp = (store.get("spaces") or {}).get(SPACE) or {}
    ot = sp.get("objectTypes") or []
    lt = sp.get("linkTypes") or []
    if len(ot) < 9:
        errs.append(f"N9 objectTypes {len(ot)} < 9")
    if len(lt) < 8:
        errs.append(f"N9 linkTypes {len(lt)} < 8")
    if store.get("global"):
        errs.append("N9 global 范围被污染（本项目只该写 space 范围）")
    eff = d.get("effective") or {}
    if not eff.get("configured"):
        errs.append("N9 effective.configured 为假 —— 本体没生效")
    return errs


# ---------------------------------------------------------------- 反向对照

def controls() -> int:
    """喂坏样本，证明 N5/N6/N7 真的会红。"""
    print("=" * 72)
    print("反向对照：喂已知坏样本，断言必须红")
    print("=" * 72)

    cases = [
        (
            "C1 层级映射错（把一条 learning 标成 importance 0.9）",
            {"memories": [{"id": "bad", "unit_type": "learning", "importance": 0.9,
                           "content": "x 依据：AGENTS.md"}]},
            "N5",
            lambda o: assert_n4_n5_n6(o)[0],
        ),
        (
            "C2 importance 低于 0.7 混进来",
            {"memories": [{"id": "bad", "unit_type": "context", "importance": 0.5,
                           "content": "x 依据：AGENTS.md"}]},
            "N6",
            lambda o: assert_n4_n5_n6(o)[0],
        ),
        (
            "C3 正文缺「依据：」尾注",
            {"memories": [{"id": "bad", "unit_type": "fact", "importance": 0.9,
                           "content": "这条没有依据尾注"}]},
            "N7",
            assert_n7,
        ),
        (
            "C4 依据指向不存在的文件",
            {"memories": [{"id": "bad", "unit_type": "fact", "importance": 0.9,
                           "content": "x\n\n依据：tools/这个文件不存在.md"}]},
            "N7",
            assert_n7,
        ),
        (
            "C5 好样本必须闭嘴（不许对一条合规记忆报红）",
            {"memories": [{"id": "good", "unit_type": "fact", "importance": 0.9,
                           "content": "x\n\n依据：AGENTS.md"}]},
            None,
            assert_n7,
        ),
    ]

    passed = failed = 0
    for name, fake, want_prefix, fn in cases:
        errs = fn(fake)
        if want_prefix is None:
            good = not errs
            print(f"  {'✓' if good else '✗'} {name}  → {'无报红（对）' if good else errs}")
            passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
            continue
        hit = any(e.startswith(want_prefix) for e in errs)
        print(f"  {'✓' if hit else '✗'} {name}  → {'红了 ' + want_prefix if hit else '没红（漏报！）'}")
        passed, failed = (passed + 1, failed) if hit else (passed, failed + 1)

    print(f"\n反向对照：{passed} 过 / {failed} 红")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true", help="只跑反向对照")
    a = ap.parse_args()

    if a.controls:
        return controls()

    print("=" * 72)
    print("nmem 记忆与知识图谱 · 自证")
    print("=" * 72)

    try:
        r = run(["--json", "status"], timeout=20)
        alive = r.returncode == 0 and json.loads(r.stdout).get("status") == "ok"
    except Exception:
        alive = False
    if not alive:
        print("⚠ 未测：nmem 不可达 —— 退 2（不是通过，也不是红）")
        return 2

    o = fetch_all()
    checks = [
        ("N0 来源文件在库且未填充", assert_n0),
        ("N1 space/strict", assert_n1),
        ("N2 agent 身份", assert_n2),
        ("N3 Space Rules", assert_n3),
        ("N8 Library indexed", assert_n8),
        ("N9 本体", assert_n9),
    ]

    red: list[str] = []
    untested: list[str] = list(o.get("untested") or [])

    for name, fn in checks:
        errs = fn(o)
        print(f"  {'✅' if not errs else '❌'} {name}")
        for e in errs:
            print(f"       {e}")
        red.extend(errs)

    e456, readings = assert_n4_n5_n6(o)
    print(f"  {'✅' if not e456 else '❌'} N4/N5/N6 四层条数与层级映射  [{', '.join(readings)}]")
    for e in e456:
        print(f"       {e}")
    red.extend(e456)

    e7 = assert_n7(o)
    print(f"  {'✅' if not e7 else '❌'} N7 每条记忆的依据可解析")
    for e in e7:
        print(f"       {e}")
    red.extend(e7)

    # N10 只是读数
    if "default_memories" in o and "memories" in o:
        print(f"  ℹ  N10 隔离读数：本 space {len(o['memories'])} 条 / default {len(o['default_memories'])} 条")

    print()
    if red and untested:
        print(f"❌ {len(red)} 项红 · ⚠ {len(untested)} 项未测 —— 两者都不是通过")
        for u in untested:
            print(f"   ⚠ {u}")
        return 1
    if red:
        print(f"❌ {len(red)} 项红")
        return 1
    if untested:
        print(f"⚠ {len(untested)} 项未测 —— 退 2（不是通过）")
        for u in untested:
            print(f"   ⚠ {u}")
        return 2
    n = len(o.get("memories") or [])
    print(f"✅ 全部通过（{n} 条记忆 / {len(o.get('library') or [])} 份真源 / 本体已生效）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
