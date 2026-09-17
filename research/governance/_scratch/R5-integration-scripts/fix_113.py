# -*- coding: utf-8 -*-
"""R5 integration pass 7: register all cross-shard deliverables in 11.3."""
import io, sys, os, glob

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

old = u"""### 11.3 本分片产出

- 主文档：`research/governance/R5-category-and-competitors.md`（本文件）
- 证据目录：`research/governance/_evidence/R5/{fda,eu,uk,ftc,competitors,platforms,materials}/`
- 子分项报告：`_evidence/R5/competitors/FINDINGS-medela-lansinoh.md`
"""

base = '/Users/lute/Project/audit_multi_content/research/governance/_evidence/R5'

def count(sub):
    return len([f for f in glob.glob(os.path.join(base, sub, '**', '*'), recursive=True) if os.path.isfile(f)])

def size(sub):
    tot = 0
    for f in glob.glob(os.path.join(base, sub, '**', '*'), recursive=True):
        if os.path.isfile(f):
            tot += os.path.getsize(f)
    return tot / 1024.0 / 1024.0

dirs = ['fda', 'eu', 'uk', 'ftc', 'competitors', 'platforms', 'materials']
rows = []
for d in dirs:
    rows.append(u"| `_evidence/R5/%s/` | %d | %.1f MB |" % (d, count(d), size(d)))
total_files = sum(count(d) for d in dirs)
total_mb = sum(size(d) for d in dirs)

new = u"""### 11.3 本分片产出

**主文档**：`research/governance/R5-category-and-competitors.md`（本文件）

**证据目录**（`research/governance/_evidence/R5/`，合计 **%d 个文件 / %.0f MB**）：

| 子目录 | 文件数 | 体积 |
|---|---|---|
%s

**跨分项报告**（由并行分项作者产出，本文件的对应章节已引用其结论）：

| 文件 | 内容 | 对应章节 |
|---|---|---|
| `_evidence/R5/competitors/FINDINGS-medela-lansinoh.md` | Medela + Lansinoh 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/FINDINGS-spectra-babybuddha-momcozy.md` | Spectra / BabyBuddha / Momcozy 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/FINDINGS-willow-elvie.md` | Willow + Elvie 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/QUOTE-BANK-byte-exact.txt` | 机器生成的逐字引文库（零手工转写） | §7、附录 B |
| **`_evidence/R5/FINDINGS-ftc-eu-law.md`**（130 KB / 1,068 行） | **FTC + EU 法源逐字取证**；33/33 引文经程序化回验；含 EU 注册库全量检索与 3 宗 FTC 执法案卷 | **§4.4、§6.1** |
| **`_evidence/R5/eu/eu-health-claims-register-*.{md,csv,json}`** | **EU 健康声称注册库全量数据集**（2,337 条）+ 泌乳专项检索结论 + 独立复核报告 + API 发现记录 | **§4.4 法源 20** |
| **`_evidence/R5/ftc/enforcement/`** | **3 宗 FTC 执法案卷原文**（NeuroMetrix / BASF-DIEM / Quincy Bioscience，各含 PDF + PDFTEXT） | **§6.1 法源 30b** |
""" % (total_files, total_mb, u"\n".join(rows))

n = s.count(old)
if n != 1:
    sys.stderr.write("MISMATCH count=%d\n" % n); sys.exit(1)
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8').write(s)
print("ok: %d files / %.0f MB" % (total_files, total_mb))
