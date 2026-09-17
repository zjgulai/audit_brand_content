# -*- coding: utf-8 -*-
"""R5 integration pass 8: correct final inventory numbers (authoritative count)."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

subs.append((u"| `_evidence/R5/fda/` | 82 | 2.4 MB |", u"| `_evidence/R5/fda/` | 82 | 2.4 MB |"))

# per-dir table numbers
subs.append((u"**证据目录**（`research/governance/_evidence/R5/`，合计 **669 个文件 / 206 MB**）：",
             u"**证据目录**（`research/governance/_evidence/R5/`，合计 **678 个文件 / 206 MB**）："))
subs.append((u"| `_evidence/R5/eu/` | 49 | 30.7 MB |", u"| `_evidence/R5/eu/` | 49 | 30.7 MB |"))
subs.append((u"| `_evidence/R5/uk/` | 4 | 0.5 MB |", u"| `_evidence/R5/uk/` | 4 | 0.5 MB |"))
subs.append((u"| `_evidence/R5/ftc/` | 27 | 16.0 MB |", u"| `_evidence/R5/ftc/` | 27 | 16.0 MB |"))
subs.append((u"| `_evidence/R5/competitors/` | 261 | 74.7 MB |", u"| `_evidence/R5/competitors/` | 261 | 74.7 MB |"))
subs.append((u"| `_evidence/R5/platforms/` | 186 | 72.6 MB |", u"| `_evidence/R5/platforms/` | 186 | 72.6 MB |"))
subs.append((u"| `_evidence/R5/materials/` | 68 | 9.4 MB |", u"| `_evidence/R5/materials/` | 68 | 9.4 MB |"))

# header counts
subs.append((u"| **原始证据** | `research/governance/_evidence/R5/` — **669 个文件 / 206 MB**，分 7 个子目录",
             u"| **原始证据** | `research/governance/_evidence/R5/` — **678 个文件 / 206 MB**（含根目录 `FINDINGS-ftc-eu-law.md`），分 7 个子目录"))

for a, b in subs:
    if a == b:
        continue
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:80])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
