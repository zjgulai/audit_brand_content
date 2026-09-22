#!/usr/bin/env node
// Phase 4/5 normalization + Phase 6 assembly for the Understand-Anything pipeline.
// Follows SKILL.md "After the subagent completes, read ... and normalize it" steps in order.
const fs = require('fs');

const UA = '/Users/lute/Project/audit_multi_content/.ua';
const INTER = UA + '/intermediate';

const graph = JSON.parse(fs.readFileSync(INTER + '/assembled-graph.json', 'utf8'));
const scan = JSON.parse(fs.readFileSync(INTER + '/scan-result.json', 'utf8'));

const nodeIds = new Set(graph.nodes.map((n) => n.id));
const FILE_LEVEL = new Set(['file', 'config', 'document', 'service', 'pipeline', 'table',
  'schema', 'resource', 'endpoint', 'step', 'module']);
const fileLevelIds = new Set(graph.nodes.filter((n) => FILE_LEVEL.has(n.type)).map((n) => n.id));

const report = [];

// ── Phase 4 normalization ────────────────────────────────────────────────
let layersRaw = JSON.parse(fs.readFileSync(INTER + '/layers.json', 'utf8'));
if (!Array.isArray(layersRaw)) { layersRaw = layersRaw.layers || []; report.push('unwrapped layers envelope'); }

const PREFIXES = new Set(['file:', 'config:', 'document:', 'service:', 'pipeline:', 'table:',
  'schema:', 'resource:', 'endpoint:', 'step:', 'module:', 'function:', 'class:']);

const kebab = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');

const layers = [];
const assigned = new Map();
for (const L of layersRaw) {
  const name = L.name || L.title || '未命名层';
  const id = L.id || 'layer:' + kebab(name);
  let ids = L.nodeIds || L.nodes || [];
  if (Array.isArray(ids) && ids.length && typeof ids[0] === 'object') {
    ids = ids.map((x) => x && x.id).filter(Boolean);
    report.push(`layer ${id}: extracted ids from object entries`);
  }
  const fixed = [];
  for (let v of ids) {
    if (typeof v !== 'string') continue;
    if (!PREFIXES.has(v.split(':')[0] + ':')) {
      // Step 4: convert bare file paths
      const cand = 'file:' + v;
      report.push(`layer ${id}: bare path ${v} -> ${cand}`);
      v = cand;
    }
    if (!nodeIds.has(v)) { report.push(`layer ${id}: dropped dangling ${v}`); continue; }
    if (assigned.has(v)) { report.push(`layer ${id}: DUP ${v} already in ${assigned.get(v)}`); continue; }
    assigned.set(v, id);
    fixed.push(v);
  }
  layers.push({ id, name, description: L.description || '', nodeIds: fixed });
}

// Every file-level node must be in exactly one layer (inline validator treats it as an ISSUE).
const orphans = [...fileLevelIds].filter((id) => !assigned.has(id));
if (orphans.length) {
  const byType = {};
  for (const id of orphans) {
    const n = graph.nodes.find((x) => x.id === id);
    (byType[n.type] = byType[n.type] || []).push(id);
  }
  report.push(`UNASSIGNED file-level nodes: ${orphans.length} -> ${JSON.stringify(Object.fromEntries(
    Object.entries(byType).map(([k, v]) => [k, v.length])))}`);
  let misc = layers.find((l) => l.id === 'layer:unassigned');
  if (!misc) { misc = { id: 'layer:unassigned', name: '未分层（自动补齐）', description: '架构分析未分配到任何层的文件级节点；由编排器按类型补齐，供复核。', nodeIds: [] }; layers.push(misc); }
  for (const id of orphans) { misc.nodeIds.push(id); assigned.set(id, misc.id); }
}

// ── Phase 5 normalization ────────────────────────────────────────────────
let tourRaw = JSON.parse(fs.readFileSync(INTER + '/tour.json', 'utf8'));
if (!Array.isArray(tourRaw)) { tourRaw = tourRaw.steps || []; report.push('unwrapped tour envelope'); }

const tour = [];
for (const s of tourRaw) {
  let ids = s.nodeIds || s.nodesToInspect || [];
  if (!Array.isArray(ids)) ids = [];
  const fixed = [];
  for (let v of ids) {
    if (typeof v !== 'string') continue;
    if (!PREFIXES.has(v.split(':')[0] + ':')) v = 'file:' + v;
    if (!nodeIds.has(v)) { report.push(`tour "${s.title}": dropped dangling ${v}`); continue; }
    if (!fixed.includes(v)) fixed.push(v);
  }
  const step = {
    order: s.order != null ? s.order : tour.length + 1,
    title: s.title || '未命名步骤',
    description: s.description || s.whyItMatters || '',
    nodeIds: fixed,
  };
  if (s.languageLesson) step.languageLesson = s.languageLesson;
  tour.push(step);
}
tour.sort((a, b) => a.order - b.order);
tour.forEach((s, i) => { s.order = i + 1; });

// ── Phase 6 assembly ─────────────────────────────────────────────────────
const meta = JSON.parse(fs.readFileSync(UA + '/intermediate/.commit.json', 'utf8'));
const out = {
  version: '1.0.0',
  project: {
    name: 'audit_multi_content',
    languages: scan.languages,
    frameworks: [],
    description: scan.description.replace(/ Note: this project has over 100 source files[\s\S]*$/, ''),
    analyzedAt: new Date().toISOString(),
    gitCommitHash: meta.commit,
  },
  nodes: graph.nodes,
  edges: graph.edges,
  layers,
  tour,
};

fs.writeFileSync(INTER + '/assembled-graph.json', JSON.stringify(out, null, 2));

console.log('layers:', layers.length, '| tour steps:', tour.length);
console.log('nodes:', out.nodes.length, '| edges:', out.edges.length);
console.log('\n--- normalization report (' + report.length + ' entries) ---');
const counts = {};
for (const r of report) { const k = r.replace(/:.*/, ''); counts[k] = (counts[k] || 0) + 1; }
for (const [k, v] of Object.entries(counts)) console.log('  ' + String(v).padStart(5) + '  ' + k);
console.log('\nlayers:');
for (const l of layers) console.log(`  ${String(l.nodeIds.length).padStart(4)}  ${l.id}  ${l.name}`);
