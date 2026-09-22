#!/usr/bin/env node
// Structural diagnosis over the knowledge graph: layer coupling, hubs, orphans, balance.
const fs = require('fs');
const G = JSON.parse(fs.readFileSync('/Users/lute/Project/audit_multi_content/.ua/knowledge-graph.json', 'utf8'));
const byId = new Map(G.nodes.map(n => [n.id, n]));
const layerOf = new Map();
for (const L of G.layers) for (const id of L.nodeIds) layerOf.set(id, L.id);
const short = (id) => id.replace(/^layer:/, '');

const out = [];
const P = (s) => out.push(s);

P('# 图结构诊断（由 knowledge-graph.json 直接算出）');
P('');
P(`节点 ${G.nodes.length} / 边 ${G.edges.length} / 层 ${G.layers.length} / 导览 ${G.tour.length} 步`);
P('');

// ── 1. layer size balance
P('## 1. 层规模分布');
P('');
P('| 层 id | 名称 | 文件级节点 |');
P('|---|---|---|');
for (const L of [...G.layers].sort((a, b) => b.nodeIds.length - a.nodeIds.length)) {
  P(`| \`${L.id}\` | ${L.name} | ${L.nodeIds.length} |`);
}
P('');

// ── 2. cross-layer coupling
P('## 2. 跨层耦合矩阵（行=源层，列=目标层；只列非零）');
P('');
const cross = new Map();
for (const e of G.edges) {
  const a = layerOf.get(e.source), b = layerOf.get(e.target);
  if (!a || !b) continue;
  const k = a + '\u0000' + b;
  cross.set(k, (cross.get(k) || 0) + 1);
}
const totals = {};
for (const [k, v] of cross) {
  const [a, b] = k.split('\u0000');
  totals[a] = (totals[a] || 0) + v;
}
P('| 源层 | 目标层 | 边数 | 占源层出边比 |');
P('|---|---|---|---|');
const rows = [...cross.entries()].sort((x, y) => y[1] - x[1]);
for (const [k, v] of rows.slice(0, 25)) {
  const [a, b] = k.split('\u0000');
  const self = a === b ? ' ←层内' : '';
  P(`| ${short(a)} | ${short(b)}${self} | ${v} | ${(100 * v / totals[a]).toFixed(1)}% |`);
}
P('');
// intra vs inter
let intra = 0, inter = 0;
for (const [k, v] of cross) { const [a, b] = k.split('\u0000'); if (a === b) intra += v; else inter += v; }
P(`层内边 ${intra} / 跨层边 ${inter} → 层内占比 ${(100 * intra / (intra + inter)).toFixed(1)}%`);
P('');

// ── 3. hubs
P('## 3. 枢纽节点（文件级，按出入度）');
P('');
const fwd = {}, rev = {};
for (const e of G.edges) {
  const s = byId.get(e.source), t = byId.get(e.target);
  if (!s || !t) continue;
  const FL = new Set(['file', 'config', 'document', 'service', 'pipeline', 'table', 'schema', 'resource', 'endpoint']);
  if (FL.has(s.type)) fwd[s.id] = (fwd[s.id] || 0) + 1;
  if (FL.has(t.type)) rev[t.id] = (rev[t.id] || 0) + 1;
}
const degree = new Map();
for (const id of new Set([...Object.keys(fwd), ...Object.keys(rev)])) {
  degree.set(id, (fwd[id] || 0) + (rev[id] || 0));
}
P('| 节点 | 层 | 出度 | 入度 | 总度 |');
P('|---|---|---|---|---|');
for (const [id, d] of [...degree.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20)) {
  P(`| \`${id}\` | ${short(layerOf.get(id) || '?')} | ${fwd[id] || 0} | ${rev[id] || 0} | ${d} |`);
}
P('');

// ── 4. orphans
P('## 4. 孤立节点');
P('');
const connected = new Set();
for (const e of G.edges) { connected.add(e.source); connected.add(e.target); }
const orphans = G.nodes.filter(n => !connected.has(n.id));
P(`零边节点 ${orphans.length} / ${G.nodes.length}（${(100 * orphans.length / G.nodes.length).toFixed(1)}%）`);
const byType = {};
for (const n of orphans) byType[n.type] = (byType[n.type] || 0) + 1;
P('');
P('按类型：' + Object.entries(byType).map(([k, v]) => `${k}=${v}`).join(' · '));
P('');
P('文件级孤立节点（前 30）：');
P('');
for (const n of orphans.filter(n => ['file', 'document', 'config', 'table'].includes(n.type)).slice(0, 30)) {
  P(`- \`${n.id}\` — ${(n.summary || '').slice(0, 80)}`);
}
P('');

// ── 5. doc graph shape
P('## 5. 文档子图形态');
P('');
const docs = G.nodes.filter(n => n.type === 'document');
const docIds = new Set(docs.map(n => n.id));
const docEdges = G.edges.filter(e => docIds.has(e.source) || docIds.has(e.target));
const dOut = {}, dIn = {};
for (const e of docEdges) {
  if (docIds.has(e.source)) dOut[e.source] = (dOut[e.source] || 0) + 1;
  if (docIds.has(e.target)) dIn[e.target] = (dIn[e.target] || 0) + 1;
}
const dDeg = new Map();
for (const id of docIds) dDeg.set(id, (dOut[id] || 0) + (dIn[id] || 0));
const connectedDocs = [...dDeg.values()].filter(v => v > 0).length;
P(`文档节点 ${docs.length}，其中有任何边的 ${connectedDocs}（${(100 * connectedDocs / docs.length).toFixed(1)}%）`);
P(`零边文档 ${docs.length - connectedDocs}`);
P('');
P('被引用最多的文档（入度 Top 12）：');
P('');
for (const [id, d] of Object.entries(dIn).sort((a, b) => b[1] - a[1]).slice(0, 12)) {
  P(`- ${d} ← 入度  \`${id}\``);
}
P('');
P('出度最高（引用别人最多）的文档 Top 12：');
P('');
for (const [id, d] of Object.entries(dOut).sort((a, b) => b[1] - a[1]).slice(0, 12)) {
  P(`- ${d} → 出度  \`${id}\``);
}
P('');

// ── 6. function distribution: god files
P('## 6. 函数/类在各文件的分布（Top 20，找上帝模块）');
P('');
const fnPerFile = {};
for (const n of G.nodes) {
  if (n.type === 'function' || n.type === 'class') {
    const p = n.filePath || (n.id.split(':')[1] || '?');
    fnPerFile[p] = (fnPerFile[p] || 0) + 1;
  }
}
P('| 文件 | 函数/类节点数 |');
P('|---|---|');
for (const [p, c] of Object.entries(fnPerFile).sort((a, b) => b[1] - a[1]).slice(0, 20)) P(`| \`${p}\` | ${c} |`);
P('');

// ── 7. edge type mix per layer
P('## 7. 各层的边类型构成（诊断「层之间靠什么连」）');
P('');
for (const L of G.layers) {
  const ids = new Set(L.nodeIds);
  const mix = {};
  for (const e of G.edges) {
    if (ids.has(e.source) || ids.has(e.target)) mix[e.type] = (mix[e.type] || 0) + 1;
  }
  const top = Object.entries(mix).sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([k, v]) => `${k}=${v}`).join(' · ');
  P(`- **${L.name}**：${top}`);
}
P('');

fs.writeFileSync('/Users/lute/Project/audit_multi_content/.ua/graph-diagnosis.md', out.join('\n'));
console.log(out.join('\n'));
