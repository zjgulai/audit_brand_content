#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_solution_meta.py —— 技术方案头部那些数字，必须与文档实况一致

存在的理由：方案头曾写「12 条 critical，见 §8」，
而文档**根本没有 §8**、实际 critical 只有 9 条。
那是 AGENTS.md §2.2 第 1 条的病：**文档里的数字要算出来，不能写进去**。

判据：
  M-1  头部声称的模块数 == 实际表中的模块行数
  M-2  头部声称的判据归属行 == 实际
  M-3  头部声称的 critical 数 == 实际 `### [critical]` 标题数
  M-4  头部声称的 high 数 == 实际
  M-5  头部引用的基线 hash == Playbook 的真实 hash（前 8 位）
  M-5b 三方绑定：技术方案头记的验收表 hash == 验收表真实 hash，
       且验收表头记的 Playbook 指纹 == Playbook 真实 hash（全 64 位）
       —— 这是 §8 B-1 的第③条。原先只做了方案↔Playbook 两方对拍，
       验收表那一方根本没有断言（2026-10-18 补）。
  M-8  §8 每题必须有 `状态` 列（open/closed），且头部声称的 open/closed 数 == 实际
  M-9  owner 表不许有重复行（set 相等抓不到重复，必须显式数一遍）
  M-6  owner 表行数 == Playbook 里的加粗编号判据数（不许再写死 82）
  M-7  每条编号判据都能在 owner 表里找到（无主判据必须为 0）

★ M-6/M-7 是 2026-10-18 补的，起因是一次**静默漂移**：§4.3.2 的 `M1–M4` 与 §3.3.4.1 的
  `M1–M3` 撞号，改名成 `MSG-1…4` 时只改了 Playbook，owner 表与抽取规则都没跟 ——
  4 条判据从此无主，而当时所有检查器**全绿**（owner 行数被当作 82 写死在断言里，
  所以「少 4 条」永远不会被发现）。一个把数字写在断言里的检查器，只能证明它自己。

退出码：0 通过 / 1 不一致 / 2 读不到（未测）
"""
from __future__ import annotations
import hashlib, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOL = ROOT / "Playbook" / "技术解决方案-v1.md"
PB = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"
TAB = ROOT / "PMO" / "audit" / "验收表-v3-覆盖全部判据-20261017.md"


def main() -> int:
    if not SOL.exists() or not PB.exists() or not TAB.exists():
        print("✗ 读不到文件 —— 未测，不是通过", file=sys.stderr)
        return 2
    s = SOL.read_text(encoding="utf-8")
    head = s[:4000]

    actual = {
        "模块数": len(re.findall(r"^\| \d+ \| `", s, re.M)),
        "判据归属行": len(re.findall(r"^\| `[A-Z][A-Za-z0-9\-]+` \| `[a-z_]+` \|", s, re.M)),
        "critical": len(re.findall(r"^### \[critical\]", s, re.M)),
        "high": len(re.findall(r"^### \[high\]", s, re.M)),
    }
    claimed = {}
    for k, pat in (("模块数", r"\|\s*模块数\s*\|\s*\*\*(\d+)\*\*"),
                   ("判据归属行", r"\|\s*判据归属行\s*\|\s*\*\*(\d+)\*\*"),
                   ("critical", r"标注的 critical\s*\|\s*\*\*(\d+)\*\*"),
                   ("high", r"另 high\s*(\d+)\s*条")):
        m = re.search(pat, head)
        claimed[k] = int(m.group(1)) if m else None

    pb_h = hashlib.sha256(PB.read_bytes()).hexdigest()
    # 认 8–64 位，但**比的是实际长度**：头部记 8 位就只证明了 8 位，
    # 所以下面会对「头部是否够长」单独断言（M-5c），不许用短指纹冒充全 hash。
    m = re.search(r"基于的 Playbook \| `([0-9a-f]{8,64})", head)
    claimed_hash = m.group(1) if m else None

    bad = []
    print("=" * 58)
    print("方案头读数对拍")
    print("=" * 58)
    for k in actual:
        c, a = claimed.get(k), actual[k]
        ok = (c == a)
        print(f"  {'✅' if ok else '❌'} {k:10s} 头部 {c} / 实际 {a}")
        if not ok:
            bad.append(k)
    # 比到「头部记了多长」为止 —— 8 位头部配 8 位比较，64 位头部配 64 位比较。
    # ★ 但另有一条 M-5c 断言头部必须记满 64 位：只记 8 位却声称「三方 hash 绑定」，
    #   那是短指纹，不是 hash 绑定。两条必须成对存在，缺一条另一个方向就恒真。
    ok_h = claimed_hash is not None and pb_h.startswith(claimed_hash)
    print(f"  {'✅' if ok_h else '❌'} 基线 hash   头部 {(claimed_hash or 'None')[:16]} / 实际 {pb_h[:16]}")
    if not ok_h:
        bad.append("基线hash")

    # ---- M-6 / M-7：判据 ↔ owner 双向对拍 ----
    # 抽取口径必须与 tools/verify_acceptance_index.py 的 ID_PATTERN 一致；
    # 直接 import 它，不在这里抄第二份正则（两处就是两套，AGENTS.md §2.5 同一条纪律）。
    sys.path.insert(0, str(ROOT / "tools"))
    from verify_acceptance_index import extract_doc_ids  # noqa: E402
    pb_text = PB.read_text(encoding="utf-8")
    doc_ids = extract_doc_ids(pb_text)
    owner_ids = set(re.findall(r"^\| `([A-Z][A-Za-z0-9\-]+)` \| `[a-z_]+` \|", s, re.M))
    no_owner = sorted(doc_ids - owner_ids)
    orphan = sorted(owner_ids - doc_ids)

    ok6 = (actual["判据归属行"] == len(doc_ids))
    print(f"  {'✅' if ok6 else '❌'} M-6 owner 行数 == 判据数  {actual['判据归属行']} / {len(doc_ids)}")
    if not ok6:
        bad.append("M-6")
    ok7 = (not no_owner and not orphan)
    print(f"  {'✅' if ok7 else '❌'} M-7 无主 / 孤儿判据  {len(no_owner)} / {len(orphan)}")
    if no_owner:
        print(f"      无主：{no_owner}")
    if orphan:
        print(f"      孤儿（owner 表有、Playbook 无）：{orphan}")
    if not ok7:
        bad.append("M-7")

    # ---- M-5b：三方绑定 ----
    tab_text = TAB.read_text(encoding="utf-8")
    pb_full = hashlib.sha256(PB.read_bytes()).hexdigest()
    tab_full = hashlib.sha256(TAB.read_bytes()).hexdigest()

    m = re.search(r"\|\s*验收表\s*\|\s*`([0-9a-f]{8,64})", head)
    sol_tab_h = m.group(1) if m else None
    ok_tab = sol_tab_h is not None and tab_full.startswith(sol_tab_h)
    print(f"  {'✅' if ok_tab else '❌'} M-5b 方案头↔验收表  头部 {(sol_tab_h or 'None')[:16]} / 实际 {tab_full[:16]}")
    if not ok_tab:
        bad.append("M-5b(方案头↔验收表)")

    # 两种措辞都认：DRAFT 期叫「当前指纹」，RATIFIED 后叫「冻结指纹」。
    # 断言只认位置和值，不认措辞 —— 否则改一个词就把检查器弄瞎了（这次就是这么瘸的）。
    m = re.search(r"\*\*(?:冻结|当前)指纹\*\*：`([0-9a-f]{64})`", tab_text)
    m2 = re.search(r"\*\*(?:冻结|当前)指纹\*\*：`([0-9a-f]{64})`[^\n]*?（(\d+) 行）", tab_text)
    tab_pb_h = m.group(1) if m else None
    ok_tabpb = (tab_pb_h == pb_full)
    print(f"  {'✅' if ok_tabpb else '❌'} M-5b 验收表↔Playbook 头部 {(tab_pb_h or 'None')[:8]} / 实际 {pb_full[:8]}")
    if not ok_tabpb:
        bad.append("M-5b(验收表↔Playbook)")
    if m2:
        claimed_lines = int(m2.group(2))
        real_lines = len(PB.read_text(encoding="utf-8").splitlines())
        ok_lines = (claimed_lines == real_lines)
        print(f"  {'✅' if ok_lines else '❌'} M-5b 验收表记的 Playbook 行数 {claimed_lines} / 实际 {real_lines}")
        if not ok_lines:
            bad.append("M-5b(行数)")

    # ---- M-8：§8 阻断门的状态列 + 头部 open/closed 计数 ----
    # 存在理由：门清单只有「有/没有」时，清掉一条与没清掉在文档上长得一样 ——
    # 头部写「19 条」而实际 4 条已清，读的人会以为 19 条全没动。
    gates = re.findall(r"^\| \*\*([BSGPA]-\d+)\*\* \|.*\| `(open|closed)` \|", s, re.M)
    n_open = sum(1 for _, v in gates if v == "open")
    n_closed = sum(1 for _, v in gates if v == "closed")
    hdr_open = re.search(r"共 (\d+) 条 —— \*\*open (\d+) / closed (\d+)\*\*", head)
    ok8 = bool(gates) and hdr_open is not None and \
          (int(hdr_open.group(1)) == len(gates)
           and int(hdr_open.group(2)) == n_open
           and int(hdr_open.group(3)) == n_closed)
    print(f"  {'✅' if ok8 else '❌'} M-8 §8 门 共 {len(gates)} / open {n_open} / closed {n_closed}"
          + ("" if hdr_open else "  ← 头部没有 open/closed 声称"))
    if not ok8:
        bad.append("M-8")
        untagged = len(re.findall(r"^\| \*\*[BSGPA]-\d+\*\* \|", s, re.M)) - len(gates)
        if untagged:
            print(f"      有 {untagged} 行没有状态列")

    # ---- M-9：owner 表重复行 ----
    # set() 相等是「集合相等」，两条一模一样的 owner 行会被并成一条 —— 集合仍相等。
    # 所以行数相等 + 集合相等两条都过了，重复仍然可能静默存在。必须显式数。
    owner_rows = re.findall(r"^\| `([A-Z][A-Za-z0-9\-]+)` \| `[a-z_]+` \|", s, re.M)
    dup = sorted({i for i in owner_rows if owner_rows.count(i) > 1})
    ok9 = not dup
    print(f"  {'✅' if ok9 else '❌'} M-9 owner 表重复行 {len(dup)} 个")
    if dup:
        print(f"      重复：{dup}")
        bad.append("M-9")

    # ---- M-5c：头部指纹必须记满 64 位 ----
    short = [n for n, v in (("Playbook", claimed_hash), ("验收表", sol_tab_h))
             if v is not None and len(v) < 64]
    ok5c = not short
    print(f"  {'✅' if ok5c else '❌'} M-5c 头部指纹长度   {len(claimed_hash or '')}/{len(sol_tab_h or '')}（须 64）")
    if not ok5c:
        print(f"      太短：{short} —— 短指纹不是 hash 绑定，不许这么叫")
        bad.append("M-5c")

    # ---- M-5d：Playbook 自指纹（掩码哈希）----
    # 为什么是掩码：指纹填进文件后文件就变了，自己算不出自己的 hash。
    # 把那一行换成 <SELF> 再算，就能自证 —— 代价是它只证明「其余部分没变」，
    # 而这个代价是可接受的：指纹行本身就在被这条断言核。
    pb_text = PB.read_text(encoding="utf-8")
    m = re.search(r"\| \*\*基线指纹\*\* \| `([0-9a-f]{64})`", pb_text)
    claimed_self = m.group(1) if m else None
    masked = re.sub(r"\| \*\*基线指纹\*\* \| .*? \|", "| **基线指纹** | `<SELF>` |", pb_text)
    real_self = hashlib.sha256(masked.encode("utf-8")).hexdigest()
    ok5d = (claimed_self == real_self)
    print(f"  {'✅' if ok5d else '❌'} M-5d Playbook 自指纹  {(claimed_self or 'None')[:16]} / 实际 {real_self[:16]}")
    if not ok5d:
        print("      Playbook 改过但没重算自指纹 —— 或者那个值根本不是掩码哈希")
        bad.append("M-5d")

    # ---- M-5e：签名区必须写清谁签了 ----
    # 状态改成 RATIFIED 但签名区不写「谁没签」，等于一句含糊的「已批准」。
    has_sig = "签名区" in pb_text
    unsigned_marked = ("⛔ **未签**" in pb_text) or ("已签" in pb_text and "未签" not in pb_text)
    ok5e = has_sig
    print(f"  {'✅' if ok5e else '❌'} M-5e 签名区存在" + ("" if ok5e else "  ← 写了 RATIFIED 却没有签名区"))
    if not ok5e:
        bad.append("M-5e")

    if bad:
        print(f"\n✗ {len(bad)} 项不一致：{bad}")
        return 1
    print("\n✅ 头部数字与文档实况一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
