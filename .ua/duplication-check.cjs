#!/usr/bin/env node
// Duplication measurement: shared function NAMES across files, plus exact-body duplicates.
// Shared names alone are weak evidence, so we also compare normalised function bodies.
const fs = require('fs');
const cp = require('child_process');
const crypto = require('crypto');
const REPO = '/Users/lute/Project/audit_multi_content';

const tracked = cp.execSync('git ls-files -z', { cwd: REPO }).toString().split('\0').filter(Boolean);
const pyFiles = tracked.filter(f => f.endsWith('.py'));

// Crude but honest function extractor: `def name(...)` at any indent, body = until next def at same/lower indent.
function functions(src) {
  const lines = src.split('\n');
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(\s*)def\s+([A-Za-z_]\w*)\s*\(/);
    if (!m) continue;
    const indent = m[1].length;
    const name = m[2];
    let j = i + 1;
    const body = [];
    while (j < lines.length) {
      if (lines[j].trim() === '') { body.push(''); j++; continue; }
      const ind = lines[j].match(/^\s*/)[0].length;
      if (ind <= indent) break;
      body.push(lines[j].replace(/^\s+/, '').replace(/\s+$/, ''));
      j++;
    }
    out.push({ name, line: i + 1, body: body.join('\n') });
  }
  return out;
}

const byFile = new Map();
const nameIndex = new Map();   // name -> [file]
const bodyIndex = new Map();   // hash -> [{file, name, line, lines}]
for (const f of pyFiles) {
  let src;
  try { src = fs.readFileSync(REPO + '/' + f, 'utf8'); } catch { continue; }
  const fns = functions(src);
  byFile.set(f, fns);
  for (const fn of fns) {
    if (!nameIndex.has(fn.name)) nameIndex.set(fn.name, []);
    nameIndex.get(fn.name).push(f);
    // normalise: strip comments/blank lines so cosmetic edits don't hide duplication
    const norm = fn.body.split('\n').filter(l => l && !l.startsWith('#')).join('\n');
    if (norm.split('\n').length < 4) continue;          // ignore trivial bodies
    const h = crypto.createHash('sha1').update(norm).digest('hex');
    if (!bodyIndex.has(h)) bodyIndex.set(h, []);
    bodyIndex.get(h).push({ file: f, name: fn.name, line: fn.line, lines: norm.split('\n').length });
  }
}

const out = [];
const P = s => out.push(s);
P('# 重复度实测（`tools/` + `research/` 下的 Python）');
P('');
P(`口径：按**函数体逐行相同**判重（去空行、去整行注释、≥4 行才算）。`);
P(`被统计的 .py 文件：${byFile.size}；函数总数：${[...byFile.values()].reduce((a, b) => a + b.length, 0)}`);
P('');

const dupes = [...bodyIndex.entries()].filter(([, v]) => v.length > 1)
  .sort((a, b) => b[1][0].lines * (b[1].length - 1) - a[1][0].lines * (a[1].length - 1));

let wasted = 0;
for (const [, v] of dupes) wasted += v[0].lines * (v.length - 1);
const totalLines = [...byFile.values()].reduce((a, fns) => a + fns.reduce((x, f) => x + f.body.split('\n').length, 0), 0);

P('## 完全相同函数体的组');
P('');
P(`**${dupes.length} 组**，组内重复行数合计 **${wasted}** 行。`);
P('');
if (dupes.length) {
  P('| 函数名 | 行数 | 份数 | 出现在 |');
  P('|---|---:|---:|---|');
  for (const [, v] of dupes.slice(0, 30)) {
    P(`| \`${v[0].name}\` | ${v[0].lines} | ${v.length} | ${v.map(x => '`' + x.file + ':' + x.line + '`').join('<br>')} |`);
  }
  P('');
}

// Shared function NAMES across different top-level families
P('## 同名函数（跨文件重名，弱证据但指向复制粘贴）');
P('');
const multi = [...nameIndex.entries()].filter(([, v]) => new Set(v).size > 1)
  .sort((a, b) => new Set(b[1]).size - new Set(a[1]).size);
P(`**${multi.length}** 个函数名出现在 ≥2 个文件里。Top 25：`);
P('');
P('| 函数名 | 文件数 | 举例 |');
P('|---|---:|---|');
for (const [n, v] of multi.slice(0, 25)) {
  const uniq = [...new Set(v)];
  P(`| \`${n}\` | ${uniq.length} | ${uniq.slice(0, 3).map(x => '`' + x + '`').join('<br>')} |`);
}
P('');

// Family view
P('## 家族视角：每个前缀家族有多少文件、多少函数、多少是同名的');
P('');
const fam = {};
for (const [f, fns] of byFile) {
  const base = f.split('/').pop();
  const m = base.match(/^([a-z]+)_/);
  const key = m ? m[1] + '_*' : base;
  fam[key] = fam[key] || { files: 0, fns: 0 };
  fam[key].files++; fam[key].fns += fns.length;
}
P('| 家族 | 文件数 | 函数数 |');
P('|---|---:|---:|');
for (const [k, v] of Object.entries(fam).sort((a, b) => b[1].files - a[1].files).slice(0, 15)) {
  P(`| \`${k}\` | ${v.files} | ${v.fns} |`);
}
P('');
P('## 复现');
P('');
P('```bash');
P('node .ua/duplication-check.cjs');
P('```');

fs.writeFileSync(REPO + '/.ua/duplication-check.md', out.join('\n'));
console.log('完全相同函数体组数:', dupes.length, '| 重复行数:', wasted);
console.log('跨文件同名函数:', multi.length);
console.log('\n--- 完全相同函数体 Top 12 ---');
for (const [, v] of dupes.slice(0, 12)) {
  console.log(`  ${v[0].name}  (${v[0].lines} 行 × ${v.length})`);
  v.forEach(x => console.log('      ' + x.file + ':' + x.line));
}
