#!/usr/bin/env node
// Documentation reachability: starting from README.md and from AGENTS.md, follow markdown
// links / path mentions and count how many of the tracked docs are reachable.
const fs = require('fs');
const cp = require('child_process');
const path = require('path');
const REPO = '/Users/lute/Project/audit_multi_content';

const tracked = cp.execSync('git ls-files -z', { cwd: REPO }).toString().split('\0').filter(Boolean);
const docs = tracked.filter(f => /\.(md|mdx|rst|txt)$/.test(f));

const bodies = new Map();
for (const f of tracked) {
  try {
    const b = fs.readFileSync(REPO + '/' + f);
    if (!b.includes(0)) bodies.set(f, b.toString('utf8'));
  } catch {}
}

// Extract referenced repo paths from a markdown body.
function refs(from, body) {
  const out = new Set();
  const dir = path.dirname(from);
  // markdown links [..](target) and bare backticked/path-like tokens
  const cands = new Set();
  for (const m of body.matchAll(/\]\(([^)\s]+)\)/g)) cands.add(m[1]);
  for (const m of body.matchAll(/`([^`\n]+\.(?:md|json|py|mjs|sh|csv|jsonl|yml|yaml|plist))`/g)) cands.add(m[1]);
  for (const m of body.matchAll(/(?:^|\s)((?:ADR|PMO|PRD|research|tools|base|kb2agent-research|agent-skills|skills-inventory|x-recovery|dsh-browser-ext)\/[A-Za-z0-9_./\u4e00-\u9fff-]+\.(?:md|json|py|mjs|sh|csv|jsonl|yml|yaml|plist))/g)) cands.add(m[1]);
  for (let c of cands) {
    c = c.split('#')[0].replace(/^\.\//, '');
    let p = null;
    if (tracked.includes(c)) p = c;
    else {
      const rel = path.normalize(path.join(dir, c));
      if (tracked.includes(rel)) p = rel;
    }
    if (p && p !== from) out.add(p);
  }
  return out;
}

function bfs(seeds) {
  const seen = new Set(seeds.filter(s => tracked.includes(s)));
  const q = [...seen];
  while (q.length) {
    const cur = q.shift();
    const body = bodies.get(cur);
    if (!body) continue;
    for (const r of refs(cur, body)) {
      if (!seen.has(r)) { seen.add(r); q.push(r); }
    }
  }
  return seen;
}

const fromReadme = bfs(['README.md']);
const fromAgents = bfs(['AGENTS.md']);
const both = new Set([...fromReadme, ...fromAgents]);
const reachableDocs = docs.filter(d => both.has(d));
const unreachableDocs = docs.filter(d => !both.has(d));

const out = [];
const P = s => out.push(s);
P('# 文档可达性（从 README.md 与 AGENTS.md 出发，沿链接/路径引用做闭包）');
P('');
P(`已跟踪文档（.md/.mdx/.rst/.txt）：**${docs.length}**`);
P(`已跟踪文件总数：${tracked.length}`);
P('');
P('| 起点 | 闭包内文件数 | 其中文档数 |');
P('|---|---|---|');
P(`| \`README.md\` | ${fromReadme.size} | ${docs.filter(d => fromReadme.has(d)).length} |`);
P(`| \`AGENTS.md\` | ${fromAgents.size} | ${docs.filter(d => fromAgents.has(d)).length} |`);
P(`| 两者并集 | ${both.size} | ${reachableDocs.length} |`);
P('');
P(`## 结论：**${unreachableDocs.length} / ${docs.length} 个文档无法从 README 或 AGENTS.md 到达**（${(100 * unreachableDocs.length / docs.length).toFixed(1)}%）`);
P('');
P('也就是说：一个新人（或一个 agent）读完入口两件之后，仍然只能看到 ' +
  `${reachableDocs.length} 个文档，剩下 ${unreachableDocs.length} 个**没有任何入口**。`);
P('');
P('### 可达的文档（' + reachableDocs.length + '）');
P('');
for (const d of reachableDocs.sort()) P('- `' + d + '`');
P('');
P('### 不可达的文档（' + unreachableDocs.length + '，按目录归并）');
P('');
const byDir = {};
for (const d of unreachableDocs) {
  const parts = d.split('/');
  const k = parts.length > 1 ? parts.slice(0, 2).join('/') : d;
  (byDir[k] = byDir[k] || []).push(d);
}
for (const [k, v] of Object.entries(byDir).sort((a, b) => b[1].length - a[1].length)) {
  P(`<details><summary><b>${k}</b> — ${v.length} 个</summary>`);
  P('');
  for (const d of v.sort()) P('- `' + d + '`');
  P('');
  P('</details>');
  P('');
}

fs.writeFileSync(REPO + '/.ua/doc-reachability.md', out.join('\n'));
console.log('文档总数:', docs.length);
console.log('README 可达文档:', docs.filter(d => fromReadme.has(d)).length, '(闭包', fromReadme.size, '个文件)');
console.log('AGENTS 可达文档:', docs.filter(d => fromAgents.has(d)).length, '(闭包', fromAgents.size, '个文件)');
console.log('并集可达文档:', reachableDocs.length);
console.log('不可达文档:', unreachableDocs.length);
