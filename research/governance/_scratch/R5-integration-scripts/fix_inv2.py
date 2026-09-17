# -*- coding: utf-8 -*-
"""R5 integration pass 12: register new materials evidence + final counts."""
import io, sys, os, glob

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- register new materials sources in 11.1 ----------
subs.append((
u"| 42 | **LFGB § 30 Verbot zum Schutz der Gesundheit** |",
u"| 41b | **21 CFR 177.1580 Polycarbonate resins** | §177.1580(d)（逐字；含 `except in infant feeding bottles (baby bottles) and spill-proof cups` 与 `77 FR 41902, July 17, 2012` 修订记录） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.1580 | `_evidence/R5/materials/ecfr-177-1580-polycarbonate-resins.html` |\n"
u"| 41c | **Commission Regulation (EU) 2024/3190（BPA 食品接触材料）** | Art. 1(2)（材质清单，含 `(f) silicones`）、**Art. 3(1) 禁令**、Art. 3(2) 与 Annex II 豁免、Art. 11/12 过渡、**Art. 13 废止 2018/213**、Art. 14 生效、Annex III 合规声明 | CELEX **32024R3190**；OJ L 2024/3190, 2024-12-31 | `_evidence/R5/materials/32024R3190.txt`、`.xhtml` |\n"
u"| 41d | **Regulation (EC) No 1935/2004 Art. 3** | Art. 1(2)（适用判据）、Art. 1(3)（3 项排除，**无医疗器械排除**）、**Art. 3(2) 误导性禁令** | CELEX 32004R1935 | `_evidence/R5/materials/32004R1935.txt`、`.xhtml` |\n"
u"| 42 | **LFGB § 30 Verbot zum Schutz der Gesundheit** |"
))

# ---------- header tally ----------
subs.append((
u"*本文件共引用法规条款与官方文件 **45 项**",
u"*本文件共引用法规条款与官方文件 **48 项**"
))
subs.append((
u"（共 21 条，编号 G1–G19 + G1b、G1c）",
u"（共 22 条，编号 G1–G19 + G1b、G1c、G8b）"
))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:80])); sys.exit(1)
    s = s.replace(a, b)

# ---------- recompute inventory block ----------
base = '/Users/lute/Project/audit_multi_content/research/governance/_evidence/R5'
dirs = ['fda', 'eu', 'uk', 'ftc', 'competitors', 'platforms', 'materials']
rows = []
tot = 0
totsz = 0.0
for d in dirs:
    fs = [f for f in glob.glob(os.path.join(base, d, '**', '*'), recursive=True) if os.path.isfile(f)]
    sz = sum(os.path.getsize(f) for f in fs) / 1048576.0
    rows.append(u"| `_evidence/R5/%s/` | %d | %.1f MB |" % (d, len(fs), sz))
    tot += len(fs); totsz += sz
total_all = tot + 1  # + FINDINGS-ftc-eu-law.md at root
mball = totsz + os.path.getsize(os.path.join(base, 'FINDINGS-ftc-eu-law.md')) / 1048576.0

s = s.replace(u"**证据目录**（`research/governance/_evidence/R5/`，合计 **678 个文件 / 206 MB**）：",
              u"**证据目录**（`research/governance/_evidence/R5/`，合计 **%d 个文件 / %.0f MB**）：" % (total_all, mball))

import re
for d, row in zip(dirs, rows):
    s = re.sub(r"\| `_evidence/R5/%s/` \| \d+ \| [\d.]+ MB \|" % re.escape(d), row, s)

s = re.sub(r"\*\*678 个文件 / 206 MB\*\*（含根目录",
           u"**%d 个文件 / %.0f MB**（含根目录" % (total_all, mball), s)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok: %d files / %.0f MB" % (total_all, mball))
