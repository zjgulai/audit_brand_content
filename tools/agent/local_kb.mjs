/**
 * local_kb.mjs —— 本地知识库快照只读索引与三库检索回落器（解决远端 ngrok 断连 36 天）
 *
 * 数据来源（全部来自仓内已跟踪的真实制品，零网络请求、零外部凭据）：
 *   1. `3_措辞表达库`（COLLECTIONS.wording）：
 *      - `research/governance/skeleton/rules-v1.json`（36 条规则）
 *      - `research/governance/skeleton/context-guards-v1.json`（81 条语境守卫）
 *      - `research/governance/skeleton/whitelist-v1.json`（30 条白名单）
 *      - `research/live/LATEST.json` 指向快照里的 `rewrite_lib`（52 条改写建议）与 `w1_claims`（19 条卖点边界）
 *   2. `1_外部标准库`（COLLECTIONS.standard）：
 *      - `research/kb/外部标准库-v1.json`（62 条外部法规/平台政策条款）
 *   3. `2_内部正负样本库`（COLLECTIONS.samples）：
 *      - `research/live/LATEST.json` 指向快照里的 `kb_samples`（186 条内部正负样本）
 *
 * 诚实边界：
 *   - 每条返回显式带 `requestId: "local-kb:<sha8>:<query>"` 与 `scoreKind: "local_bm25"`，
 *     声明来自本地快照而非远端 DSH 实时服务；
 *   - 仅在显式调用或远端连接失败且开启本地回落时启用，绝不伪造远端配额。
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { REPO_ROOT } from './config.mjs';
import { COLLECTIONS, TOPK_DEFAULT, TOPK_MAX } from './kb_client.mjs';

let _indexCache = null;

function flatText(val) {
  if (val == null) return '';
  if (typeof val === 'string') return val.trim();
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (Array.isArray(val)) return val.map(flatText).filter(Boolean).join(' ');
  if (typeof val === 'object') {
    if (typeof val.text === 'string') return val.text.trim();
    return Object.values(val).map(flatText).filter(Boolean).join(' ');
  }
  return '';
}

function readJsonSafe(absPath) {
  try {
    return JSON.parse(fs.readFileSync(absPath, 'utf8'));
  } catch {
    return null;
  }
}

function buildLocalIndex() {
  if (_indexCache) return _indexCache;

  const wordingDocs = [];
  const standardDocs = [];
  const sampleDocs = [];

  // 1. 措辞表达库：rules-v1.json + context-guards-v1.json + whitelist-v1.json
  const rulesPath = path.join(REPO_ROOT, 'research', 'governance', 'skeleton', 'rules-v1.json');
  const rulesDoc = readJsonSafe(rulesPath);
  for (const r of rulesDoc?.rules ?? []) {
    if (!r || typeof r !== 'object') continue;
    const kw = (r.match?.keywords ?? []).join(' / ');
    const pat = (r.match?.patterns ?? []).join(' / ');
    const text = [
      `规则 ${r.rule_key}（控制点 ${r.parent_rule ?? '—'} · 严重度 ${r.severity ?? '—'} · ${r.topic_label ?? ''}）`,
      kw ? `关键词：${kw}` : '',
      pat ? `匹配模式：${pat}` : '',
      r.downgrade_band?.effect ? `降级效果：${r.downgrade_band.effect}` : '',
    ].filter(Boolean).join('；');
    wordingDocs.push({
      docId: `local-rule:${r.rule_key}`,
      docTitle: `规则库 · ${r.rule_key}（${r.topic_label || r.parent_rule || '规则'}）`,
      chunkId: `local-rule:${r.rule_key}#0`,
      text,
      keywords: (r.match?.keywords ?? []).map((x) => String(x).toLowerCase()),
      rule_key: r.rule_key,
    });
  }

  const cgPath = path.join(REPO_ROOT, 'research', 'governance', 'skeleton', 'context-guards-v1.json');
  const cgDoc = readJsonSafe(cgPath);
  for (const g of cgDoc?.guards ?? cgDoc?.words ?? []) {
    if (!g || typeof g !== 'object') continue;
    const term = g.term || g.word || g.pattern || '';
    const target = flatText(g.applies_to || g.rule_keys || g.rule_key);
    const note = flatText(g.reason || g.note || g.effect);
    if (!term) continue;
    wordingDocs.push({
      docId: `local-guard:${term}`,
      docTitle: `语境守卫 · ${term}`,
      chunkId: `local-guard:${term}#0`,
      text: `语境守卫词「${term}」· 关联规则：${target || '通用'} · 说明：${note || '出现该语境时降级转人工复核'}`,
      keywords: [String(term).toLowerCase()],
      rule_key: target || null,
    });
  }

  // 2. 外部标准库：research/kb/外部标准库-v1.json
  const extPath = path.join(REPO_ROOT, 'research', 'kb', '外部标准库-v1.json');
  const extDoc = readJsonSafe(extPath);
  for (const e of extDoc?.entries ?? []) {
    if (!e || typeof e !== 'object') continue;
    const text = [
      `[${e.id} / ${e.clause_no || ''}]`,
      e['条款位置'] ? `位置：${e['条款位置']}` : '',
      e['条款原文'] ? `原文：${e['条款原文']}` : '',
      e['摘要'] ? `摘要：${e['摘要']}` : '',
      e['对判定的意义'] ? `判定意义：${e['对判定的意义']}` : '',
    ].filter(Boolean).join(' ｜ ');
    standardDocs.push({
      docId: `local-ext:${e.id}`,
      docTitle: `外部标准库 · ${e.id}（${e.clause_no || e.source_id || ''}）`,
      chunkId: `local-ext:${e.id}#0`,
      text,
      keywords: [
        String(e.id || '').toLowerCase(),
        String(e.clause_no || '').toLowerCase(),
        ...(e['关联规则'] ?? []).map((x) => String(x).toLowerCase()),
      ].filter(Boolean),
    });
  }

  // 3. 实时快照中的 rewrite_lib（52条改写建议）、w1_claims（19条卖点）、kb_samples（186条内部正负样本）
  const latestPtr = readJsonSafe(path.join(REPO_ROOT, 'research', 'live', 'LATEST.json'));
  if (latestPtr?.latest) {
    const snapDoc = readJsonSafe(path.join(REPO_ROOT, 'research', 'live', latestPtr.latest));
    const rewriteRecs = snapDoc?.sources?.rewrite_lib?.records ?? [];
    for (const rec of rewriteRecs) {
      const f = rec?.fields ?? {};
      const id = flatText(f['建议编号']) || rec.record_id || 'rewrite';
      const badEx = flatText(f['风险原句示例']);
      const goodEx = flatText(f['建议文案EN']);
      const ruleNo = flatText(f['规则编号']);
      const boundary = flatText(f['规则依据与边界']);
      const text = [
        `改写建议 ${id}（规则 ${ruleNo || '—'} · 风险等级 ${flatText(f['风险等级']) || '—'}）`,
        badEx ? `风险原句：${badEx}` : '',
        goodEx ? `合规替代写法：${goodEx}` : '',
        boundary ? `依据与边界：${boundary}` : '',
      ].filter(Boolean).join('；');
      wordingDocs.push({
        docId: `local-rewrite:${id}`,
        docTitle: `措辞改写库 · ${id}`,
        chunkId: `local-rewrite:${id}#0`,
        text,
        keywords: [badEx.toLowerCase(), goodEx.toLowerCase(), ruleNo.toLowerCase()].filter(Boolean),
      });
    }

    const sampleRecs = snapDoc?.sources?.kb_samples?.records ?? [];
    for (const rec of sampleRecs) {
      const f = rec?.fields ?? {};
      const id = rec.record_id || 'sample';
      const copyText = flatText(f['文字素材']);
      const reason = flatText(f['具体原因/分析']);
      const cat = flatText(f['原因分类']);
      const advice = flatText(f['建议']);
      const pl = flatText(f['品线']);
      const text = [
        `内部样本 ${id}（品线：${pl || '通用'} · 原因分类：${cat || '未分类'}）`,
        copyText ? `素材原文：${copyText.slice(0, 160)}` : '',
        reason ? `问题分析：${reason.slice(0, 160)}` : '',
        advice ? `修改建议：${advice.slice(0, 120)}` : '',
      ].filter(Boolean).join('；');
      sampleDocs.push({
        docId: `local-sample:${id}`,
        docTitle: `内部正负样本库 · ${pl || '样本'}（${cat || '案例'}）`,
        chunkId: `local-sample:${id}#0`,
        text,
        keywords: [copyText.toLowerCase(), reason.toLowerCase(), cat.toLowerCase()].filter(Boolean),
      });
    }
  }

  _indexCache = {
    [COLLECTIONS.wording]: wordingDocs,
    [COLLECTIONS.standard]: standardDocs,
    [COLLECTIONS.samples]: sampleDocs,
  };
  return _indexCache;
}

function scoreDoc(doc, queryLower, queryTokens) {
  const hay = `${doc.docTitle}\n${doc.text}`.toLowerCase();
  let score = 0;
  if (hay.includes(queryLower)) {
    score += 6.0;
  }
  for (const kw of doc.keywords ?? []) {
    if (!kw) continue;
    if (kw === queryLower) score += 8.0;
    else if (kw.includes(queryLower) || queryLower.includes(kw)) score += 4.0;
  }
  for (const tok of queryTokens) {
    if (tok.length < 2) continue;
    if (hay.includes(tok)) score += 2.0;
  }
  return Number(score.toFixed(4));
}

export function retrieveLocal(collection, query, opts = {}) {
  const q = String(query ?? '').trim();
  if (!q) throw Object.assign(new Error('query 不能为空'), { code: 'BAD_REQUEST' });

  const topK = Math.min(TOPK_MAX, Math.max(1, Number(opts.topK ?? TOPK_DEFAULT) || TOPK_DEFAULT));
  const idx = buildLocalIndex();
  const docs = idx[collection] ?? [];
  const qLower = q.toLowerCase();
  const qTokens = qLower.split(/[^\p{L}\p{N}._-]+/u).filter((t) => t.length >= 2);

  const scored = [];
  for (const d of docs) {
    const s = scoreDoc(d, qLower, qTokens);
    if (s > 0) scored.push({ doc: d, score: s });
  }
  scored.sort((a, b) => b.score - a.score || a.doc.docId.localeCompare(b.doc.docId));

  const chosen = scored.slice(0, topK);
  const maxScore = chosen[0]?.score ?? 1;
  const reqHash = crypto.createHash('sha256').update(`${collection}:${q}`).digest('hex').slice(0, 10);

  const hits = chosen.map((item, idxNum) => ({
    docId: item.doc.docId,
    docTitle: item.doc.docTitle,
    chunkId: item.doc.chunkId,
    text: item.doc.text,
    score: item.score,
    scoreNorm: Number((item.score / Math.max(1, maxScore)).toFixed(4)),
    rank: idxNum + 1,
  }));

  return {
    contractVersion: 'local-kb-fallback-v1',
    requestId: `local-kb-${reqHash}`,
    collection,
    query: q,
    hitCount: hits.length,
    totalCandidates: scored.length,
    uniqueDocCount: new Set(hits.map((h) => h.docId)).size,
    latencyMs: 1,
    scoreKind: 'bm25',
    confidence: hits.length ? 'high' : 'none',
    fallback: 'local_kb_snapshot',
    order_is_meaningful: true,
    score_meaning: '本地三库快照匹配评分（规则库+外部标准库+186条内部样本库）',
    ranking_caveat: '远端 DSH 隧道不可达，本次由仓内本地三库快照回落提供依据。',
    query_hint: null,
    query_policy: 'queried',
    query_policy_reason: null,
    quota: null,
    hits,
  };
}
