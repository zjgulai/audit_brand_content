#!/usr/bin/env node
/**
 * judge_evidence_wiring.test.mjs —— 「证据链真的接进了 judge_copy」这件事的执行点。
 *
 * ── 为什么需要它（AGENTS.md §2.4：名字出现过 ≠ 拦得住）
 *
 * 2026-10-21 之前，`judge_evidence.mjs` 有 465 行、实现了完整的 BM25 检索与六档状态，
 * `persona.mjs` 也已经对模型承诺「judge_copy 自己会去查知识库，把依据挂在 evidence_chain 里」——
 * 但 `grep -rn judge_evidence tools base api` **零命中**。话说了，接线没做。
 *
 * 所以本文件不验「函数写得对不对」（它自己有自己的判据），只验四件事：
 *
 *   A. **判据本身**：`pickKeyPhrases` 的档位（engine_matched / mixed / probe）
 *      与 2 字中文词的处理。2 字词是这条链路已知的盲区（trigram 要求 ≥3 字），
 *      **跳过 ≠ 库里没有**，必须显式说出来。
 *   B. **六档状态分得开**：用本地假 KB 服务逐个喂 found / none / probe_empty /
 *      partial / untested。尤其 `none`（可以说「库里没有」）与 `probe_empty`
 *      （只能说「没试到」）**不许长得一样**。
 *   C. **接线是行为级的**：用假 `python3` 跑真实的 `executeTool('judge_copy')`，
 *      断言返回里**确实有** `evidence_chain`。这不是源码文本断言 ——
 *      把接线删掉，C1 会红。
 *   D. **反向对照**：把接线那一行临时改成 `return r`，同一套断言**必须**变红。
 *      只证明「接上了」不够，还要证明「断开能被发现」（分工台账 20261021 的交付要求）。
 *   E. **没有副作用**：状态目录指到临时目录，跑完回读真实 `kb_quota.json` 没被动过
 *      （AGENTS.md §2.4.4：自证不许改掉它要保护的东西）。
 *
 * 全部离线：假 KB 服务在本机 127.0.0.1，假 python3 在临时目录，**不碰真飞书/真 KB/真回执**。
 *
 * 用法：node tools/agent/judge_evidence_wiring.test.mjs
 * 退出码：0 全过 ｜ 1 有红
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const res = [];
const T = (name, ok, detail) => res.push({ name, ok, detail });

/* ── 0. 先把所有会落盘的东西指到临时目录（§2.4.4）───────────────────── */
const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'judge-evidence-test-'));
const tmpState = path.join(tmpRoot, 'state');
fs.mkdirSync(tmpState, { recursive: true });

// 假 python3：judge_copy 会 execFile('python3', ...)，这里让它回一份固定的判定结果。
// 它**不写回执**，所以本测试不会往生产账本里塞测试记录。
const fakeBin = path.join(tmpRoot, 'bin');
fs.mkdirSync(fakeBin, { recursive: true });
const fakePy = path.join(fakeBin, 'python3');
fs.writeFileSync(fakePy, `#!/bin/sh
cat <<'JSON'
{"verdict":{"disposition":"review","severity":"P1","rules_hit":["R-TEST"]},
 "hits":[{"rule_key":"R-TEST","matched":[{"matched_text":"cure mastitis"}]}],
 "receipt":{"evidence_ref":[]}}
JSON
`, { mode: 0o755 });

// 真实状态文件：跑前记一次 mtime/size，跑完回读（E 段）
const realQuota = path.join(REPO_ROOT, 'PMO', 'shouheng-state', 'kb_quota.json');
const beforeReal = (() => {
  try { const s = fs.statSync(realQuota); return { mtimeMs: s.mtimeMs, size: s.size }; }
  catch { return null; }
})();

// ★ 必须在**动态 import 之前**设好：config.mjs 在 import 期就读这些值。
process.env.SHOUHENG_STATE_DIR = tmpState;
process.env.SHOUHENG_KB_ENABLED = '0';       // C 段走 disabled；B 段显式传 enabled:true
process.env.PATH = `${fakeBin}${path.delimiter}${process.env.PATH}`;

/* ── 1. 本地假 KB 服务 ──────────────────────────────────────────────── */
const MODE = {
  'found phrase': 'hit',
  'none phrase': 'empty',
  'partial one': 'empty',
  'partial two': 'boom',
  'untested phrase': 'boom',
};

const server = http.createServer((req, resp) => {
  const q = new URL(req.url, 'http://127.0.0.1').searchParams.get('q') ?? '';
  const mode = MODE[q] ?? 'empty';
  if (mode === 'boom') {
    resp.writeHead(500, { 'content-type': 'application/json' });
    resp.end(JSON.stringify({ error: { code: 'BOOM', message: '假的 500' } }));
    return;
  }
  const body = {
    collection: { id: '3_措辞表达库' },
    requestId: `req-test-${encodeURIComponent(q)}`,
    hitCount: mode === 'hit' ? 1 : 0,
    totalCandidates: mode === 'hit' ? 1 : 0,
    scoreKind: 'bm25',
    confidence: mode === 'hit' ? 0.9 : null,
    quota: { limitPerDay: 1000, usedPerDay: 10 },
    hits: mode === 'hit'
      ? [{ docId: 'cg-r-test', docTitle: '测试规则', chunkId: 'c1',
           text: `规则正文：${q}`, score: 1.2, scoreNorm: 0.8, rank: 1 }]
      : [],
  };
  resp.writeHead(200, { 'content-type': 'application/json' });
  resp.end(JSON.stringify(body));
});

await new Promise((r) => server.listen(0, '127.0.0.1', r));
process.env.SHOUHENG_KB_BASE_URL = `http://127.0.0.1:${server.address().port}`;
process.env.SHOUHENG_KB_API_KEY = 'test-key-not-real';

/* ── 2. 动态 import（此时环境变量已就位）────────────────────────────── */
const je = await import('./judge_evidence.mjs');
const kb = await import('./kb_client.mjs');

const hit = (phrase) => ({ rule_key: 'R-TEST', matched: [{ matched_text: phrase }] });
const judgeWith = (...phrases) => ({ hits: phrases.map((p) => hit(p)) });

/* ── A. 判据本身 ────────────────────────────────────────────────────── */
{
  const p = je.pickKeyPhrases('...', judgeWith('cure mastitis'));
  T('A1 引擎命中的 ≥3 字表述 → basis=engine_matched',
    p.basis === 'engine_matched' && p.queries.length === 1, JSON.stringify(p).slice(0, 160));
  T('A2 查询词带出处（哪条规则命中的它）',
    p.queries[0]?.source === 'engine_matched' && p.queries[0]?.rule_key === 'R-TEST', '');

  // ★ 2 字中文词：trigram 检索不到。**必须**落进 dropped_short，不许假装查过。
  const short = je.pickKeyPhrases('...', judgeWith('无菌', '冰冷'));
  T('A3 ★ 2 字中文表述 → 落进 dropped_short（trigram 硬要求 ≥3 字）',
    short.dropped_short.includes('无菌') && short.dropped_short.includes('冰冷'),
    JSON.stringify(short.dropped_short));
  T('A4 ★ 2 字词没有被拿去冒充查询词',
    short.queries.every((q) => !['无菌', '冰冷'].includes(q.phrase)),
    JSON.stringify(short.queries));
  T('A5 只剩 2 字词时 → basis=probe（最低档，不许说「库里没有」）',
    short.basis === 'probe', short.basis);

  // engine 不够 3 个 → 用试探词补齐，basis 降为 mixed
  const mixed = je.pickKeyPhrases('Clinically proven to relieve discomfort', judgeWith('cure mastitis'));
  T('A6 引擎命中不足 3 个 → 试探词补齐，basis=mixed',
    mixed.basis === 'mixed' && mixed.queries.some((q) => q.source === 'probe'),
    JSON.stringify(mixed.queries.map((q) => [q.phrase, q.source])));
}

/* ── B. 六档状态：喂假 KB，逐档确认「长得不一样」────────────────────── */
const ev = async (phrases, text = '...') =>
  je.gatherEvidence(text, judgeWith(...phrases), { enabled: true });

const bFound = await ev(['found phrase']);
T('B1 found：至少一条命中 → evidence_usable=true',
  bFound.status === 'found' && bFound.conclusion_gate.evidence_usable === true,
  `${bFound.status}/${bFound.evidence_total}`);

const bNone = await ev(['none phrase']);
T('B2 none：引擎表述 + 全部查成 + 全 0 → **才**允许说「库里没有」',
  bNone.status === 'none' && bNone.conclusion_gate.may_assert_kb_absence === true,
  `${bNone.status}/${bNone.basis}`);

const bProbe = await ev([], 'Clinically proven relief');
T('B3 ★ probe_empty：查询词是试出来的、全 0 → **不许**说「库里没有」',
  bProbe.status === 'probe_empty' && bProbe.conclusion_gate.may_assert_kb_absence === false,
  `${bProbe.status}/${bProbe.basis}/${bProbe.queries.length}`);

const bPartial = await ev(['partial one', 'partial two']);
T('B4 ★ partial：有的查成、有的没查成 → 必须披露失败，不许当 0 命中',
  bPartial.status === 'partial' && bPartial.conclusion_gate.must_disclose_failure === true,
  `${bPartial.status}/failed=${bPartial.failures?.length}`);

const bUntested = await ev(['untested phrase']);
T('B5 ★ untested：一次都没查成 → 未测 ≠ 没有命中 ≠ 库里没有',
  bUntested.status === 'untested' && bUntested.conclusion_gate.must_disclose_failure === true,
  bUntested.status);

T('B6 六档文案互不相同（none / probe_empty / partial / untested 四句不许合并）',
  new Set([bNone.notice, bProbe.notice, bPartial.notice, bUntested.notice]).size === 4,
  '');

// 2 字词在**整条 gatherEvidence**里的表现：一次检索都不发，落 untested，不是 none
const bShort = await je.gatherEvidence('...', judgeWith('无菌'), { enabled: true });
T('B7 ★ 只有 2 字词 → status=untested（未测），不是 none（库里没有）',
  bShort.status === 'untested', bShort.status);
T('B8 ★ 2 字词被跳过这件事必须写在返回里',
  /不是「库里没有这些词」/.test(String(bShort.dropped_short_note ?? '')),
  String(bShort.dropped_short_note ?? '').slice(0, 100));

/* ── C. 接线是行为级的：真跑 executeTool('judge_copy') ───────────────── */
const tools = await import('./tools.mjs');
const call = await tools.executeTool('judge_copy',
  JSON.stringify({ text: 'Clinically proven to cure mastitis.' }));
T('C1 ★ judge_copy 的返回里**确实有** evidence_chain（删掉接线这条会红）',
  call.ok === true && !!call.result?.evidence_chain,
  JSON.stringify(call).slice(0, 160));
T('C2 开关关掉时 → status=disabled（不是「没有证据」这一档）',
  call.result?.evidence_chain?.status === 'disabled',
  String(call.result?.evidence_chain?.status));
T('C3 disabled 必须带 must_disclose_failure=true（不许静默省略）',
  call.result?.evidence_chain?.conclusion_gate?.must_disclose_failure === true, '');
T('C4 判定本身没有被证据链改写（disposition / hits 原样返回）',
  call.result?.verdict?.disposition === 'review' && Array.isArray(call.result?.hits), '');

/* ── D. 反向对照：把接线改掉，同一套断言必须红 ───────────────────────── */
{
  const srcPath = path.join(HERE, 'tools.mjs');
  const src = fs.readFileSync(srcPath, 'utf8');
  const needle = 'return { ...r, evidence_chain: evidenceChain };';
  const mutantPath = path.join(HERE, `.mutant-${process.pid}.mjs`);
  if (!src.includes(needle)) {
    T('D0 ★ 反向对照自身有效：tools.mjs 里找得到接线那一行', false,
      '找不到 return { ...r, evidence_chain: evidenceChain }; —— 接线写法变了，本反向对照已失效');
  } else {
    T('D0 ★ 反向对照自身有效：tools.mjs 里找得到接线那一行', true, '');
    fs.writeFileSync(mutantPath,
      src.replace(needle, 'return r; // MUTANT: 故意断开证据链接线'), 'utf8');
    try {
      const mutant = await import(`${pathToFileURL(mutantPath).href}?v=${Date.now()}`);
      const mCall = await mutant.executeTool('judge_copy',
        JSON.stringify({ text: 'Clinically proven to cure mastitis.' }));
      T('D1 ★ 断开接线后 → evidence_chain 消失（C1 会红，证明它拦得住）',
        !mCall.result?.evidence_chain, JSON.stringify(mCall.result ?? mCall).slice(0, 120));
    } finally {
      try { fs.unlinkSync(mutantPath); } catch { /* 清理失败不影响断言 */ }
    }
  }
}

/* ── E. 没有副作用：状态目录在临时区，真实状态文件没被动过 ───────────── */
T('E1 配额快照路径落在临时状态目录（不是仓内 PMO/shouheng-state）',
  kb.quotaPath().startsWith(tmpState), kb.quotaPath());
{
  const after = (() => {
    try { const s = fs.statSync(realQuota); return { mtimeMs: s.mtimeMs, size: s.size }; }
    catch { return null; }
  })();
  const same = JSON.stringify(beforeReal) === JSON.stringify(after);
  T('E2 ★ 自证不落真状态：PMO/shouheng-state/kb_quota.json 一个字节没动',
    same, `${JSON.stringify(beforeReal)} → ${JSON.stringify(after)}`);
}

/* ── 出口 ───────────────────────────────────────────────────────────── */
server.close();
const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} judge_evidence 接线自证 ${res.length - nFail}/${res.length} 项通过`);
console.log('   （假 KB / 假 python3 / 临时状态目录；不碰真飞书、真 KB、真回执）');
process.exit(nFail ? 1 : 0);
