#!/usr/bin/env node
// Honest reference census: for every tracked executable file, count how many OTHER tracked
// files mention its basename at all (import, spawn, shell call, or prose). This distinguishes
// "not import-reachable" from "referenced by nothing".
const fs = require('fs');
const cp = require('child_process');
const REPO = '/Users/lute/Project/audit_multi_content';

// NOTE: `git ls-files` (no -z) QUOTES paths containing non-ASCII bytes, e.g.
// "ADR/ADR-0009-\350\257\255..." — reading those paths fails and the file is silently
// skipped, which would understate every reference count. Use -z and split on NUL.
const tracked = cp.execSync('git ls-files -z', { cwd: REPO }).toString()
  .split('\0').filter(Boolean);
const exe = tracked.filter(f => /\.(py|mjs|js|sh|plist)$/.test(f));

// Read all tracked text files once (skip binaries).
const text = new Map();
let skipped = [];
for (const f of tracked) {
  try {
    const buf = fs.readFileSync(REPO + '/' + f);
    if (buf.includes(0)) { skipped.push(['binary', f]); continue; }   // binary
    text.set(f, buf.toString('utf8'));
  } catch (e) { skipped.push([e.code || 'ERR', f]); }
}
if (skipped.length) {
  console.error('⚠ 未能纳入统计的文件 ' + skipped.length + ' 个（若含中文名文件说明 -z 修复失效）:');
  for (const [why, f] of skipped.slice(0, 10)) console.error('   ' + why + '  ' + f);
}

const rows = [];
for (const f of exe) {
  const base = f.split('/').pop();
  const refs = [];
  for (const [g, body] of text) {
    if (g === f) continue;
    if (body.includes(base)) refs.push(g);
  }
  rows.push({ file: f, base, n: refs.length, refs });
}

const zero = rows.filter(r => r.n === 0);
const one = rows.filter(r => r.n === 1);

const out = [];
const P = s => out.push(s);
P('# 引用普查：每个可执行文件被多少个其它已跟踪文件提到过');
P('');
P(`已跟踪可执行文件 ${exe.length} 个（.py/.mjs/.js/.sh/.plist）。对每个文件，统计**其它**已跟踪文本文件里出现其文件名 basename 的个数。`);
P('');
P('> 口径说明：这一步**只证「有没有人提到它」**，不证「它是否是活的」。');
P('> 被 mention 也可能只是散文里提了一句；0 次 mention 则是更强的信号 ——');
P('> 它既不被 import、也不被 spawn、也不在文档里出现。');
P('');
P('| 档位 | 个数 |');
P('|---|---|');
P(`| 0 次被提及 | ${zero.length} |`);
P(`| 1 次 | ${one.length} |`);
P(`| ≥2 次 | ${rows.length - zero.length - one.length} |`);
P('');
P('## 0 次被提及（最强的死代码候选）');
P('');
for (const r of zero.sort((a, b) => a.file.localeCompare(b.file))) P('- `' + r.file + '`');
P('');
P('## 恰 1 次被提及（只在一处出现）');
P('');
for (const r of one.sort((a, b) => a.file.localeCompare(b.file))) {
  P('- `' + r.file + '`  ← 仅 `' + r.refs[0] + '`');
}
P('');
P('## 被提及最多的 25 个');
P('');
P('| 文件 | 被提及次数 |');
P('|---|---|');
for (const r of [...rows].sort((a, b) => b.n - a.n).slice(0, 25)) P(`| \`${r.file}\` | ${r.n} |`);

fs.writeFileSync(REPO + '/.ua/reference-census.md', out.join('\n'));
console.log('0 次被提及:', zero.length);
console.log('1 次被提及:', one.length);
console.log('总可执行文件:', exe.length);
console.log('\n--- 0 次被提及 ---');
zero.forEach(r => console.log('  ' + r.file));
