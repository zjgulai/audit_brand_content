#!/usr/bin/env node
// Reachability from the two real entry points, using the resolved import map.
const fs = require('fs');
const REPO = '/Users/lute/Project/audit_multi_content';
const scan = JSON.parse(fs.readFileSync(REPO + '/.ua/intermediate/scan-result.json', 'utf8'));
const im = scan.importMap;

const tracked = require('child_process').execSync('git ls-files', { cwd: REPO })
  .toString().trim().split('\n');

function reach(entry) {
  const seen = new Set([entry]);
  const q = [entry];
  while (q.length) {
    const cur = q.pop();
    for (const nxt of (im[cur] || [])) {
      if (!seen.has(nxt)) { seen.add(nxt); q.push(nxt); }
    }
  }
  return seen;
}

const daemon = reach('tools/ws_daemon.mjs');
const engine = reach('research/governance/skeleton/judge.py');
const base = reach('base/text_stage.py');

const live = new Set([...daemon, ...engine, ...base]);

const out = [];
const P = (s) => out.push(s);
P('# 运行时可达面（从两个真入口沿 import 图算出）');
P('');
P('入口：`tools/ws_daemon.mjs`（守衡守护进程）、`research/governance/skeleton/judge.py`（判定引擎）、`base/text_stage.py`（基座管道）');
P('');
P('| 入口 | 可达文件数 |');
P('|---|---|');
P('| `tools/ws_daemon.mjs` | ' + daemon.size + ' |');
P('| `research/governance/skeleton/judge.py` | ' + engine.size + ' |');
P('| `base/text_stage.py` | ' + base.size + ' |');
P('| **并集（去重）** | **' + live.size + '** |');
P('| 全部已跟踪文件 | ' + tracked.length + ' |');
P('');
P(`→ 运行时可达标面占全仓 **${(100 * live.size / tracked.length).toFixed(1)}%**；`);
P(`  其余 **${tracked.length - live.size}** 个文件（${(100 * (tracked.length - live.size) / tracked.length).toFixed(1)}%）不在任何运行时路径上。`);
P('');

P('## 守护进程可达集（守衡上线时真正被加载的东西）');
P('');
for (const f of [...daemon].sort()) P('- `' + f + '`');
P('');
P('## 判定引擎可达集');
P('');
for (const f of [...engine].sort()) P('- `' + f + '`');
P('');
P('## 基座管道可达集');
P('');
for (const f of [...base].sort()) P('- `' + f + '`');
P('');

// 不在运行时路径上的 Python/MJS 代码（最值得怀疑的那部分）
const code = tracked.filter(f => /\.(py|mjs|js|sh)$/.test(f));
const dead = code.filter(f => !live.has(f));
P('## 不在任何运行时路径上的**可执行**文件（' + dead.length + ' / ' + code.length + '）');
P('');
const byDir = {};
for (const f of dead) { const d = f.includes('/') ? f.split('/').slice(0, 2).join('/') : f; byDir[d] = (byDir[d] || 0) + 1; }
P('按目录：');
P('');
for (const [d, c] of Object.entries(byDir).sort((a, b) => b[1] - a[1])) P(`- ${c}  \`${d}\``);
P('');
P('<details><summary>逐个列出</summary>');
P('');
for (const f of dead.sort()) P('- `' + f + '`');
P('');
P('</details>');

fs.writeFileSync(REPO + '/.ua/runtime-surface.md', out.join('\n'));
console.log(out.slice(0, 22).join('\n'));
