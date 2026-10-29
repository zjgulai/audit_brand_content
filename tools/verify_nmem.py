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


# ★ 2026-10-27：本 space 现在有**两类记忆，两类契约不同**，必须分开验。
#
#   ① 蒸馏语料（source = CORPUS_SOURCE）—— 我写的四层，权重严格按 SOP 映射，
#      「依据」尾注指回**仓内已跟踪文件**。
#   ② 抽取产生（source = library:<src_id>）—— 抽取器自己定的类型与权重
#      （0.65~0.8 都出现过），「依据」指向**飞书材料名**，不是仓内路径。
#
#   拿①的尺子量②，会同时冤枉两边：②被判「权重不对 / 依据解析不了」，
#   而①的真正问题会被②的噪声淹掉。这正是 §2.4.8 那个形状 —— 两类东西共用一个读数。
CORPUS_SOURCE = "audit-multi-content/tools/mem"
EXTRACT_SOURCE_PREFIX = "library:"
# `opencode` 是另一个 agent 会话写进本 space 的 —— 合法来源，但它既不是我的
# 四层语料、也不是 library 抽取，所以单独归类，不参与四层映射。
# `opencode` / `agent` 是**别的 agent 会话**写进本 space 的 —— 合法来源，
# 但它们既不是我的四层语料、也不是 library 抽取，**不受我的四层契约约束**
# （它们没有「依据：」尾注，权重由各自会话定）。2026-10-28 实测：
# 另一个会话一次写入 6 条 `source=agent`（装插件、守衡停令等），
# 若按我的契约判会把 6 条全部报红 —— 那不是它们的错，是我的尺子伸得太远。
OTHER_SOURCES = {"opencode", "agent"}


def _classify(m: dict) -> str:
    src = str(m.get("source") or "")
    if src == CORPUS_SOURCE:
        return "corpus"
    if src.startswith(EXTRACT_SOURCE_PREFIX):
        return "extracted"
    if src in OTHER_SOURCES:
        return "other"
    return "foreign"


def assert_n4_n5_n6(o: dict) -> tuple[list[str], list[str]]:
    """返回 (errs, readings)。四层契约**只对蒸馏语料**成立。"""
    if "memories" not in o:
        return [], ["（未测）"]
    mems = o["memories"]
    counts: dict[str, int] = {}
    errs, foreign = [], []
    for m in mems:
        kind = _classify(m)
        if kind == "foreign":
            foreign.append(f"{m.get('id')}（source={m.get('source')}）")
            continue
        if kind in ("extracted", "other"):
            continue                    # 抽取/外部来源不参与四层映射
        ut = m.get("unit_type")
        counts[ut] = counts.get(ut, 0) + 1
        mid = m.get("id", "?")
        if ut not in EXPECTED:
            errs.append(f"N5 {mid}: unit_type={ut!r} 不在四层映射里")
            continue
        want = EXPECTED[ut]
        got = float(m.get("importance") or 0)
        if abs(got - want) > 1e-9:
            errs.append(f"N5 {mid}: importance={got} ≠ {want}（{ut} 的 SOP 权重）")
        if got < 0.7:
            errs.append(f"N6 {mid}: importance={got} < 0.7 —— 流水条目不许进本 space")
    for ut, bottom in MIN_COUNTS.items():
        if counts.get(ut, 0) < bottom:
            errs.append(f"N4 {ut} 只有 {counts.get(ut, 0)} 条 < 下限 {bottom}")
    if foreign:
        errs.append(f"N4 有 {len(foreign)} 条记忆来源不明（既不是蒸馏语料也不是抽取）：{foreign[:3]}")
    readings = [f"{ut} {counts.get(ut, 0)}" for ut in ("decision", "fact", "learning", "context")]
    n_ex = sum(1 for m in mems if _classify(m) == "extracted")
    if n_ex:
        readings.append(f"抽取 {n_ex}")
    return errs, readings


def _registered_materials() -> set[str]:
    """已登记的 B 档材料标识（key 与落盘文件名），供抽取类记忆的依据校验用。"""
    reg = REPO / "tools" / "feishu_content_materials.json"
    try:
        d = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return set()
    out = set()
    for it in d.get("items") or []:
        if it.get("key"):
            out.add(str(it["key"]))
        if it.get("file"):
            out.add(str(it["file"]))
            out.add(str(it["file"]).split("__at__")[0])
    return out


def assert_n7(o: dict) -> list[str]:
    """依据可解析 —— **两类记忆各按自己的口径**。

    · 蒸馏语料：尾注里的路径必须能在 `git ls-files` 里找到（指回仓内原文）。
    · 抽取产生：尾注里必须出现**已登记材料**的 key 或文件名
      （指回仓外那份飞书材料；它本来就不会是仓内路径）。
    """
    if "memories" not in o:
        return []
    errs = []
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    ).stdout.decode("utf-8", "replace").split("\0")
    tracked = {t for t in tracked if t}
    materials = _registered_materials()

    for m in o["memories"]:
        mid = m.get("id", "?")
        kind = _classify(m)
        if kind == "other":
            continue          # 别的 agent 会话写的，不受我的「依据」约定约束
        text = _mem_text(m)
        if "依据：" not in text:
            errs.append(f"N7 {mid}: 正文里没有「依据：」尾注")
            continue
        # ★ 取**最后一处**「依据：」。2026-10-27 实测：正文里本来就可能出现
        #   「依据：<一句论证>」这种行文句式（抽取产生的记忆尤其多），
        #   而尾注是**追加在最后**的。取第一处会把行文句式当成尾注，误报。
        #   （同一条记忆里有两处：「依据：不要求负责人…」+「依据：meeting-20260915 …」。）
        tail = text.rsplit("依据：", 1)[1].split("\n", 1)[0]
        if kind == "extracted":
            # 抽取类：依据里要点名一份**已登记**的材料
            if not any(mat and mat in tail for mat in materials):
                errs.append(f"N7 {mid}（抽取类）: 依据里没有任何已登记材料 —— {tail[:80]}")
            continue
        found = False
        for seg in tail.split(";"):
            seg = seg.strip().split("⟵")[0].strip()
            if seg and seg in tracked:
                found = True
                break
        if not found:
            errs.append(f"N7 {mid}: 依据里的路径一个都不在 git ls-files 里 —— {tail[:80]}")
    return errs


# ★ 2026-10-28：N8 原先**只有下限的一半** —— 它验「已有的条目是否 indexed」，
#   却**不验「该有的条目还在不在」**。于是 8 份仓内真源被误删时它一声不响：
#   `library list` 返回 12 条（全是飞书材料），每条都 indexed，N8 全绿。
#   删掉的是我自己 —— 调试 MIME 时写了一个「清掉探针」的循环，
#   而那个循环遍历的是**该 space 的全部条目**，不是只删探针。
#   所以补上这个名单：这 8 份是「仓内真源」，缺任何一份就红。
REQUIRED_REPO_SOURCES = (
    "AGENTS.md",
    "README.md",                      # ADR/README.md 与 base/README.md 同名，按 basename 判会撞
    "内容审查Agent-常犯坑点与硬约束-v1.md",
    "上线交付说明-20261024.md",
    "内容审查Agent-知识库与工作流-深度分析-20261021.md",
    "填充态-环境特性-实测史.md",
    "同一个量两个口径与跳过重排-实测史.md",
)
# 上面 7 个名字里 README.md 出现两次（ADR/ 与 base/），所以数量下限按 8 算。
MIN_REPO_SOURCES = 8


def assert_n8(o: dict) -> list[str]:
    if "library" not in o:
        return []
    errs = []
    lib = o["library"]
    if not lib:
        return ["N8 Library 是空的（真源一份都没归档）"]
    # ── 下限：仓内真源必须都在（2026-10-28 补，理由见上面注释）
    names = [str(s.get("original_name") or "") for s in lib]
    for want in REQUIRED_REPO_SOURCES:
        if not any(n == want or n.startswith(want) for n in names):
            errs.append(f"N8 仓内真源 {want!r} **不在 Library 里** —— 被删了或被移走了")
    n_readme = sum(1 for n in names if n == "README.md")
    if n_readme < 2:
        errs.append(f"N8 README.md 只有 {n_readme} 份，应为 2 份（ADR/ 与 base/ 各一）")
    if len(lib) < MIN_REPO_SOURCES:
        errs.append(f"N8 Library 只有 {len(lib)} 份 < 下限 {MIN_REPO_SOURCES}")
    for s in lib:
        st = s.get("lifecycle_state")
        # `extracted` 是 indexed **之后**的一步（抽取跑过了），也是成功态。
        if st not in ("indexed", "extracted"):
            errs.append(
                f"N8 {s.get('original_name')}: state={st!r} err={s.get('error_message')}"
            )
        if not s.get("chunk_count"):
            errs.append(f"N8 {s.get('original_name')}: chunk_count=0（解析出来了但没切片）")
    return errs


# ★ 本体播种的真相（2026-10-27 实测，见 PMO/audit/裁定-nmem图谱不适用-20261027.md）
#   声明的 9 个对象类型**实体数全为 0**：extraction.gate = "disabled"，
#   而 CLI 里没有任何一条命令能启用它（entities 没有 create；ontology 的
#   字段白名单里没有 extraction 项；policy 改成 guide、agenticKgExtraction
#   改成 true 都试过，gate 一动不动）。
#   所以「本体已生效」这句话是**假的** —— 它只说明词汇表存在，不说明有东西按它标出来。
#
#   本常量就是那条「显式声明未播种」：**要停止这个声明，必须先在库里真的播种实体**，
#   否则 N9 会红。反过来说，只要声明在，N9 就不许拿「9 个类型存在」当通过。
# ★ 2026-10-27 终局：**已播种，本表清空**。
#
#   这条注释记的是本表短短一天里的四个版本，因为每一版都曾是「当时以为的结论」：
#     ① gate 打不开、无路径            → 错（路径在 HTTP 路由 /settings/ontology/extraction）
#     ② gate 打开了、被预算挡住        → 对，但只是当时的读数
#     ③ 部分播种（5/9 类）             → 按类型逐条声明 pending
#     ④ **全部 9 类都有实体**          → 本版：清空
#
#   最终读数（2026-10-27 实测）：406 个实体 / 269+ 条关系，9 类最低的 RELEASEGATE 也有 1 个。
#   现在 N9 走状态 A：**任一类型掉到 0 就红** —— 因为「已经全播过」这件事一旦成立，
#   再掉回 0 就是回退，不是「还没开始」。
SEED_PENDING = {}


def assert_n9(o: dict) -> list[str]:
    """本体：词汇表可以声明而不播种，但**不许冒充已播种**。

    两条互斥的合法状态：
      A 已播种：每个声明的类型都 ≥1 个实体
      B 声明未播种：SEED_PENDING 在，且**确实一个实体都没有**
         —— 若此时有实体，说明声明过期了（有人在播种但没撤声明），也红。
    两者都不满足（声明了、有部分实体、又写着未播种）→ 红。
    """
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
    # ★ 2026-10-28 收紧：原先这一条是 `if store.get("global")` —— **任何** global 内容
    #   都报污染。但平台自己会用默认种子写 global（实测只有一个 `CONCEPT` +
    #   `openWorld`，来自 `seedFromDefaults`），那不是我们的污染。
    #   真正的风险只有一个：**本项目的类型被写进了 global**，从而泄漏到别的 space。
    g = store.get("global") or {}
    g_keys = {str(t.get("key")) for t in (g.get("objectTypes") or [])}
    leaked = sorted(g_keys & {str(t.get("key")) for t in ot})
    if leaked:
        errs.append(f"N9 本项目的对象类型泄漏到了 global 范围：{leaked} —— "
                    f"global 对**所有 space** 生效，写进去等于改别人的图谱")
    eff = d.get("effective") or {}
    if not eff.get("configured"):
        errs.append("N9 effective.configured 为假 —— 本体没生效")

    # ── 实体覆盖：这是原先缺的那一半
    tc = (d.get("stats") or {}).get("typeCounts") or {}
    mine = [t.get("key") for t in ot]
    seeded = {k: tc.get(k, 0) for k in mine}
    n_seeded = sum(1 for v in seeded.values() if v > 0)
    total_in_mine = sum(seeded.values())

    # ── 逐类型判定（2026-10-27 第三版）
    #    每类只有两种合法状态，且都必须**被声明**：
    #      · 有实体      → 已播种，过
    #      · 零实体 + 在 pending_types 里且写了理由 → 声明未播种，过
    #      · 零实体 + 不在表里                       → 红（凭空缺一类）
    #      · 有实体 + 仍在表里                       → 红（**声明过期**，C6 守这条）
    pending = (SEED_PENDING or {}).get("pending_types") or {}
    for k, v in seeded.items():
        if v > 0 and k in pending:
            errs.append(
                f"N9 {k} 已有 {v} 个实体，却仍挂在 pending_types 里 —— "
                f"声明过期了，必须删掉那条（否则它会一直替一个已经做完的事写理由）")
        elif v == 0 and k not in pending:
            errs.append(
                f"N9 {k} 实体数为 0，且没有在 pending_types 里声明理由 —— "
                f"要么补材料让它长出来，要么写明为什么还没有")
        elif v == 0 and not str(pending.get(k) or "").strip():
            errs.append(f"N9 {k} 在 pending_types 里但理由为空 —— 空白豁免等于无理由豁免")
    for k in pending:
        if k not in seeded:
            errs.append(f"N9 pending_types 里的 {k} 不是已声明的对象类型 —— 声明与盘上不符")
    if len(ot) != SEED_PENDING.get("object_types", len(ot)):
        errs.append(f"N9 声明 {SEED_PENDING.get('object_types')} 个 objectTypes，"
                    f"实际 {len(ot)} 个 —— 与盘上不符")

    o["_n9"] = {"seeded": n_seeded, "total": len(mine), "entities": total_in_mine}
    return errs


def _fake_ontology(seeded_type: str | None, count: int, all_zero: bool = False) -> dict:
    """造一个最小本体响应：9 个类型，其中 seeded_type 有 count 个实体。"""
    keys = ["DECISIONRECORD", "VERIFIER", "FAILUREPATTERN", "SUBSYSTEM", "CONTRACT",
            "RELEASEGATE", "TICKET", "REDLINE", "INCIDENT"]
    tc = {k: 0 for k in keys}
    if seeded_type:
        tc[seeded_type] = count
    return {
        "store": {"global": {}, "spaces": {SPACE: {
            "objectTypes": [{"key": k, "displayName": k} for k in keys],
            "linkTypes": [{"key": f"L{i}", "displayName": f"L{i}"} for i in range(8)],
        }}},
        "effective": {"configured": True},
        "stats": {"typeCounts": tc},
    }


def _n9_all_pending(o: dict) -> list[str]:
    """把 pending_types 临时补成**九类全覆盖**再跑 N9 —— 证「全零但都声明了」会闭嘴。"""
    global SEED_PENDING
    saved = SEED_PENDING
    keys = [t["key"] for t in o["ontology"]["store"]["spaces"][SPACE]["objectTypes"]]
    SEED_PENDING = {**saved, "object_types": len(keys),
                    "pending_types": {k: "controls 造的理由" for k in keys}}
    try:
        return assert_n9(o)
    finally:
        SEED_PENDING = saved


def _n9_as_seeded(o: dict) -> list[str]:
    """把 SEED_PENDING 临时摘掉再跑 N9 —— 用来证明「已播种」那一支真的会红。"""
    global SEED_PENDING
    saved = SEED_PENDING
    SEED_PENDING = {}          # type: ignore[assignment]
    try:
        return assert_n9(o)
    finally:
        SEED_PENDING = saved   # type: ignore[assignment]


# ---------------------------------------------------------------- 反向对照

def controls() -> int:
    """喂坏样本，证明 N5/N6/N7 真的会红。"""
    print("=" * 72)
    print("反向对照：喂已知坏样本，断言必须红")
    print("=" * 72)

    cases = [
        (
            "C1 层级映射错（把一条 learning 标成 importance 0.9）",
            {"memories": [{"id": "bad", "source": CORPUS_SOURCE, "unit_type": "learning",
                           "importance": 0.9, "content": "x 依据：AGENTS.md"}]},
            "N5",
            lambda o: assert_n4_n5_n6(o)[0],
        ),
        (
            "C2 importance 低于 0.7 混进来",
            {"memories": [{"id": "bad", "source": CORPUS_SOURCE, "unit_type": "context",
                           "importance": 0.5, "content": "x 依据：AGENTS.md"}]},
            "N6",
            lambda o: assert_n4_n5_n6(o)[0],
        ),
        (
            "C3 正文缺「依据：」尾注",
            {"memories": [{"id": "bad", "source": CORPUS_SOURCE, "unit_type": "fact",
                           "importance": 0.9, "content": "这条没有依据尾注"}]},
            "N7",
            assert_n7,
        ),
        (
            "C4 依据指向不存在的文件",
            {"memories": [{"id": "bad", "source": CORPUS_SOURCE, "unit_type": "fact",
                           "importance": 0.9, "content": "x\n\n依据：tools/这个文件不存在.md"}]},
            "N7",
            assert_n7,
        ),
        (
            "C5 好样本必须闭嘴（不许对一条合规记忆报红）",
            {"memories": [{"id": "good", "source": CORPUS_SOURCE, "unit_type": "fact",
                           "importance": 0.9, "content": "x\n\n依据：AGENTS.md"}]},
            None,
            assert_n7,
        ),
        # ── N9 的两面：这正是本条改之前的形状 ────────────────────────────
        (
            "C6 seed_pending 声明了，但库里其实有实体 → 声明过期，必须红",
            {"ontology": _fake_ontology(seeded_type="VERIFIER", count=3)},
            "N9",
            assert_n9,
        ),
        (
            "C7 撤掉 seed_pending 后，声明的类型里有一个实体为 0 → 必须红"
            "（改之前这条恒绿，因为只查了词汇表长度）",
            {"ontology": _fake_ontology(seeded_type=None, count=0)},
            "N9",
            _n9_as_seeded,
        ),
        (
            "C8 逐类型 pending：九类全零但九类都写了理由 → 必须闭嘴",
            {"ontology": _fake_ontology(seeded_type=None, count=0)},
            None,
            _n9_all_pending,
        ),
        (
            "C9 九类全零、但只有 4 类写了理由 → 必须红（另外 5 类凭空缺）",
            {"ontology": _fake_ontology(seeded_type=None, count=0)},
            "N9",
            assert_n9,
        ),
        (
            "C10 抽取类记忆的依据没点名任何已登记材料 → 必须红",
            {"memories": [{"id": "bad", "source": "library:src_fake",
                           "unit_type": "learning", "importance": 0.7,
                           "content": "x\n\n依据：某份没登记的材料"}]},
            "N7",
            assert_n7,
        ),
        (
            "C14 Library 少了一份仓内真源 → 必须红（2026-10-28 真被误删过 8 份，当时全绿）",
            {"library": [{"original_name": "AGENTS.md", "lifecycle_state": "indexed",
                          "chunk_count": 89},
                         {"original_name": "README.md", "lifecycle_state": "indexed",
                          "chunk_count": 27}]},
            "N8",
            assert_n8,
        ),
        (
            "C15 本项目类型泄漏到 global → 必须红",
            {"ontology": {**_fake_ontology(seeded_type="VERIFIER", count=2),
                          "store": {"global": {"objectTypes": [{"key": "VERIFIER"}]},
                                    "spaces": _fake_ontology(seeded_type="VERIFIER",
                                                             count=2)["store"]["spaces"]}}},
            "N9",
            assert_n9,
        ),
        (
            "C12 别的会话写的 agent 记忆（无「依据」尾注）→ **不该**红（不属我的契约）",
            {"memories": [{"id": "ag", "source": "agent", "unit_type": "event",
                           "importance": 0.7, "content": "装了个插件，没有依据尾注"}]},
            None,
            lambda o: [e for e in (assert_n7(o) + assert_n4_n5_n6(o)[0])
                       if "ag" in e],
        ),
        (
            "C13 来源不明的记忆（source=totally-unknown）→ 必须红（分流留了口子）",
            {"memories": [{"id": "unk", "source": "totally-unknown",
                           "unit_type": "fact", "importance": 0.9,
                           "content": "x\n\n依据：AGENTS.md"}]},
            "N4",
            lambda o: [e for e in assert_n4_n5_n6(o)[0] if e.startswith("N4")],
        ),
        (
            "C11 抽取类权重 0.65（不合四层）→ **不该**被四层判据红（分流生效）",
            {"memories": [{"id": "ex", "source": "library:src_fake",
                           "unit_type": "learning", "importance": 0.65,
                           "content": "x\n\n依据：meeting-20260915"}]},
            None,
            # 只看 N5/N6 —— N4 的条数下限对「只有一条假样本」的集合必然红，
            # 那是 N4 在正确工作，不是分流失效。
            lambda o: [e for e in assert_n4_n5_n6(o)[0] if e.startswith(("N5", "N6"))],
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
    n9 = o.get("_n9") or {}
    pending_n = len((SEED_PENDING or {}).get("pending_types") or {})
    onto_note = (f"本体 {n9.get('seeded', '?')}/{n9.get('total', '?')} 类已播种，"
                 f"另有 {pending_n} 类**声明未播种**（实体共 {n9.get('entities', 0)} 个）")
    print(f"✅ 全部通过（{n} 条记忆 / {len(o.get('library') or [])} 份真源 / {onto_note}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
