#!/usr/bin/env node
/**
 * query_policy.test.mjs —— 「同一个 trigram 事实，两套策略」的执行点（2026-10-21）
 *
 * ── 这条测试守的是什么
 *
 * 「查询词不足 3 字，trigram 拿不到真 BM25」是**同一个事实**，但两个模块的处理**故意相反**：
 *   · `judge_evidence.mjs` —— **丢弃**短词（`drop_short_for_evidence`），
 *     不拿词频序当判定依据；丢弃的记进 `dropped_short_queries`。
 *   · `kb_client.mjs` —— **照查**短词（`queried_short`），
 *     并在返回里声明 positional / 词频序 / 顺序不可当相关性。
 *
 * 两种都成立，因为契约不同：一个产出「证据」，一个产出「通用检索结果」。
 * 风险不在差异本身，而在**下游看不出走的是哪条**。所以两边的返回都必须带
 * `query_policy`，本文件把这件事钉住：
 *
 *   A. 两个纯函数在同一个 2 字输入上给出**不同**策略；
 *   B. `judge_evidence` 的返回带 `query_policy` + `dropped_short_queries`；
 *   C. `kb_client.retrieve`（喂假的 positional 响应，**不是真实 KB**）带 `query_policy`；
 *   D. **反向对照**：把 `judge_evidence` 的阈值从 3 改成 2，A/B 的断言必须红。
 *
 * ★ 真实 KB 的 positional 输出本轮**未测**（2026-10-21 ping 超时）；C 段是构造响应，
 *   只证明客户端契约，不证明真实服务端行为。
 *
 * 用法：node tools/agent/query_policy.test.mjs
 * 退出码：0 全过 ｜ 1 有红
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'query-policy-test-'));
const tmpState = path.join(tmpRoot, 'state');
fs.mkdirSync(tmpState, { recursive: true });

const res = [];
const T = (name, ok, detail) => res.push({ name, ok, detail });

/* ── 假 KB：只用于验客户端对 positional 响应的处理（不是真实读数）──────── */
const server = http.createServer((req, resp) => {
  const q = new URL(req.url, 'http://127.0.0.1').searchParams.get('q') ?? '';
  const body = {
    collection: { id: '3_措辞表达库' },
    requestId: 'req-query-policy-test',
    hitCount: 1,
    totalCandidates: 1,
    scoreKind: 'positional',
    confidence: null,
    quota: { limitPerMinute: 60, limitPerDay: 1000, usedPerMinute: 1, usedPerDay: 1 },
    hits: [{ docId: 'cg-r-test', docTitle: '测试规则', chunkId: 'c1',
             text: `测试片段：${q}`, score: 2, scoreNorm: null, rank: 1 }],
  };
  resp.writeHead(200, { 'content-type': 'application/json' });
  resp.end(JSON.stringify(body));
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));

process.env.SHOUHENG_STATE_DIR = tmpState;
process.env.SHOUHENG_KB_BASE_URL = `http://127.0.0.1:${server.address().port}`;
process.env.SHOUHENG_KB_API_KEY = 'test-key-not-real';

const kb = await import('./kb_client.mjs');
const je = await import('./judge_evidence.mjs');

const text = '这款吸奶器可以治疗乳腺炎';
const jr = { hits: [{ rule_key: 'T1.1.medical-cure', matched: [{ matched_text: '治疗' }] }] };

/* ── A. 事实与两个纯函数 ─────────────────────────────────────────────── */
T('A1 trigram 门槛是 3（两模块共用这一个常量）',
  kb.MIN_TRIGRAM_CHARS === 3, String(kb.MIN_TRIGRAM_CHARS));
T('A2 queryLengthHint(治疗) 明说 2 字会回退 positional',
  /2 个字符/.test(String(kb.queryLengthHint('治疗'))) && /positional/.test(String(kb.queryLengthHint('治疗'))),
  String(kb.queryLengthHint('治疗')).slice(0, 100));
T('A3 queryLengthHint(吸奶器) = null（3 字够长）',
  kb.queryLengthHint('吸奶器') === null, '');

const shortPolicy = kb.queryPolicy('治疗');
const longPolicy = kb.queryPolicy('吸奶器');
T('A4 ★ kb_client 的短词策略 = queried_short（照查 + 声明 caveat）',
  shortPolicy.policy === 'queried_short' && shortPolicy.chars === 2
    && /positional/.test(String(shortPolicy.reason)), JSON.stringify(shortPolicy));
T('A5 kb_client 的 ≥3 字策略 = queried（没有 caveat）',
  longPolicy.policy === 'queried' && longPolicy.reason === null, JSON.stringify(longPolicy));

/* ── B. judge_evidence 的策略与查询计划 ─────────────────────────────── */
const picked = je.pickKeyPhrases(text, jr);
T('B1 ★ judge_evidence 的短词策略 = drop_short_for_evidence（丢弃）',
  picked.query_policy === 'drop_short_for_evidence'
    && /2 字词丢弃/.test(String(picked.query_policy_note)),
  `${picked.query_policy}/${picked.query_policy_note}`);
T('B2 ★ 2 字词被记进 dropped_short，且**不**出现在查询词里',
  picked.dropped_short.includes('治疗')
    && !picked.queries.some((q) => q.phrase === '治疗'),
  JSON.stringify(picked.queries));
T('B3 引擎没命中够长表述时，改用 ≥3 字的试探词（basis=probe）',
  picked.basis === 'probe' && picked.queries.length > 0
    && picked.queries.every((q) => [...q.phrase].length >= 3),
  JSON.stringify(picked.queries));

const longPick = je.pickKeyPhrases('...', {
  hits: [{ rule_key: 'R', matched: [{ matched_text: '吸奶器' }] }],
});
T('B4 3 字引擎表述 → 照用（query_policy 仍是 drop 策略，但没有 dropped）',
  longPick.query_policy === 'drop_short_for_evidence'
    && longPick.dropped_short.length === 0
    && longPick.queries.some((q) => q.phrase === '吸奶器'),
  JSON.stringify(longPick));

T('B5 ★ 同一个 2 字输入：两边的策略**不同**，且各自都声明了 policy',
  shortPolicy.policy !== picked.query_policy
    && shortPolicy.policy === 'queried_short'
    && picked.query_policy === 'drop_short_for_evidence',
  `${shortPolicy.policy} vs ${picked.query_policy}`);

/* ── C. gatherEvidence 把策略透传到 evidence_chain（禁网）───────────── */
{
  const got = await je.gatherEvidence(text, jr, { enabled: false });
  T('C1 evidence_chain 带 query_policy（disabled 早退也要带）',
    got.query_policy === 'drop_short_for_evidence'
      && Array.isArray(got.dropped_short_queries)
      && got.dropped_short_queries.includes('治疗'),
    JSON.stringify({ policy: got.query_policy, dropped: got.dropped_short_queries }));
}

/* ── D. kb_client.retrieve 面对 positional 响应（构造响应，不是真实 KB）── */
{
  const r = await kb.retrieve('3_措辞表达库', '治疗', { topK: 3 });
  T('D1 ★ 短词照查时返回 query_policy=queried_short',
    r.query_policy === 'queried_short' && r.query_chars === 2,
    JSON.stringify({ policy: r.query_policy, chars: r.query_chars }));
  T('D2 ★ positional 响应必须标成 order_is_meaningful=false，且 caveat 说「词频不是相关性」',
    r.order_is_meaningful === false && /词频/.test(String(r.ranking_caveat)),
    String(r.ranking_caveat).slice(0, 100));
  T('D3 它仍然返回 hits（照查的取舍是「有比没有好」，不是静默丢弃）',
    Array.isArray(r.hits) && r.hits.length === 1, String(r.hits?.length));
}

/* ── E. 反向对照：把阈值 3 改成 2，B2/B5 的断言必须红 ───────────────── */
{
  const srcPath = path.join(HERE, 'judge_evidence.mjs');
  const src = fs.readFileSync(srcPath, 'utf8');
  const needle = 'const MIN_QUERY_CHARS = kb.MIN_TRIGRAM_CHARS;';
  const mutantPath = path.join(HERE, `.mutant-query-policy-${process.pid}.mjs`);
  if (!src.includes(needle)) {
    T('E0 ★ 反向对照自身有效：找得到阈值那一行', false,
      '找不到 const MIN_QUERY_CHARS = kb.MIN_TRIGRAM_CHARS; —— 反向对照已失效');
  } else {
    T('E0 ★ 反向对照自身有效：找得到阈值那一行', true, '');
    fs.writeFileSync(mutantPath, src.replace(needle, 'const MIN_QUERY_CHARS = 2;'), 'utf8');
    try {
      const mutant = await import(`${pathToFileURL(mutantPath).href}?v=${Date.now()}`);
      const m = mutant.pickKeyPhrases(text, jr);
      T('E1 ★ 阈值改成 2 后，2 字词不再被丢弃 —— B2 会红（证明它拦得住）',
        !m.dropped_short.includes('治疗')
          && m.queries.some((q) => q.phrase === '治疗' && q.source === 'engine_matched'),
        JSON.stringify({ dropped: m.dropped_short, queries: m.queries }));
    } finally {
      try { fs.unlinkSync(mutantPath); } catch { /* 清理失败不影响断言 */ }
    }
  }
}

/* ── 出口 ───────────────────────────────────────────────────────────── */
server.close();
try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch { /* 临时目录清不掉不影响断言 */ }
const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} 查询策略自证 ${res.length - nFail}/${res.length} 项通过`);
console.log('   （D 段是构造的 positional 响应；真实 KB 的 positional 输出本轮未测）');
process.exit(nFail ? 1 : 0);
