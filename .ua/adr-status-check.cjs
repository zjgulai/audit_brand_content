#!/usr/bin/env node
// Cross-check ADR status: the index table in ADR/README.md vs each ADR file's own 状态 field.
const fs = require('fs');
const cp = require('child_process');
const REPO = '/Users/lute/Project/audit_multi_content';

const files = cp.execSync('git ls-files -z ADR', { cwd: REPO }).toString()
  .split('\0').filter(f => /^ADR\/ADR-\d+.*\.md$/.test(f)).sort();

const STATES = ['proposed', 'accepted', 'superseded', 'rejected'];

function stateFromBody(s) {
  // first line mentioning 状态 in the header block
  const head = s.split('\n').slice(0, 12).join('\n');
  const line = head.split('\n').find(l => l.includes('状态'));
  if (!line) return null;
  for (const st of STATES) if (line.includes(st)) return st;
  return '(未识别: ' + line.trim().slice(0, 60) + ')';
}

const readme = fs.readFileSync(REPO + '/ADR/README.md', 'utf8');
const rows = [];
for (const f of files) {
  const id = f.match(/ADR-(\d+)/)[1];
  const own = stateFromBody(fs.readFileSync(REPO + '/' + f, 'utf8'));
  // find this ADR's row in the index table
  const re = new RegExp('\\|\\s*\\[ADR-' + id + '\\][^\\n]*', 'g');
  const m = readme.match(re);
  let table = null;
  if (m) {
    const cells = m[0].split('|').map(c => c.trim());
    const stCell = cells.find(c => STATES.some(s => c.includes(s)));
    if (stCell) table = STATES.find(s => stCell.includes(s));
  }
  rows.push({ id, file: f, own, table, ok: own === table });
}

const bad = rows.filter(r => !r.ok);
const out = [];
const P = s => out.push(s);
P('# ADR 状态双源对照：`ADR/README.md` 索引表 vs 每个 ADR 文件自己的 `状态` 字段');
P('');
P(`口径：ADR 文件取头部 12 行内第一条含「状态」的行里的枚举值；索引表取该 ADR 行内出现枚举值的单元格。`);
P(`枚举：${STATES.join(' / ')}`);
P('');
P('| ADR | 文件自述 | 索引表 | 一致 |');
P('|---|---|---|---|');
for (const r of rows) {
  P(`| ADR-${r.id} | \`${r.own}\` | \`${r.table}\` | ${r.ok ? '✅' : '❌ **不一致**'} |`);
}
P('');
P(`## 结论：${rows.length} 个 ADR 中 **${bad.length} 个两处不一致**`);
P('');
if (bad.length) {
  P('不一致清单：');
  P('');
  for (const r of bad) {
    P(`- **ADR-${r.id}** — 文件自述 \`${r.own}\`，索引表写 \`${r.table}\`（\`${r.file}\` vs \`ADR/README.md\`）`);
  }
  P('');
  P('> 影响：`ADR/README.md` 的「当前决策台账」是读者与 agent 查「哪条决策已生效」的**主要入口**');
  P('> （它不在 143 个不可达文档里 —— 它可达）。表与文件冲突时，没有任何东西会红。');
}
P('');
P('## 复现');
P('');
P('```bash');
P('node .ua/adr-status-check.cjs');
P('```');

fs.writeFileSync(REPO + '/.ua/adr-status-check.md', out.join('\n'));
console.log(out.join('\n'));
