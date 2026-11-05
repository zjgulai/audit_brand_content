/**
 * prd53.mjs —— 审查结论抬头与逐条/汇总块规范器（适配生产五标签 + 工作台 case_id）
 *
 * 将 SH-Agent 的 PRD §5.3 结论行机制与本仓生产五标签（BLOCK / REVIEW / PASS / 待自决 / 未审查）
 * 及工作台案件号（case_id）对齐：
 *   · 支持识别 `【审查结论：<标签>】...` 与 `【<标签>】...` 两种结论行；
 *   · 提供 `buildGuardVerdict()`：直接从生产判定结果生成权威结论行 `line` 与问题明细块 `block`
 *     （1–2 条展开逐条位置/原文/控制点/依据；≥3 条先出分类汇总再列前序命中，原文经 mdTextSafe 转义）。
 */
import { mdTextSafe } from './plain.mjs';
import {
  resolveModality, renderFourDimAuditPayload, specFor, classifyAuditState, HUMAN_LABEL,
} from './audit_modality_specs.mjs';

export const STATES = ['BLOCK', 'REVIEW', 'PASS+SUGGEST', 'PASS', '待自决', '未审查'];
export const LEGACY_STATES = ['SUGGEST'];
export const REPORT_LINK_MIN_ISSUES = 3;

export function normState(state) {
  const raw = String(state ?? '').trim();
  if (raw === '待自决' || raw === '未审查') return raw;
  const u = raw.toUpperCase();
  return u === 'SUGGEST' ? 'PASS+SUGGEST' : u;
}

const LINE_RE = /【审查结论：(PASS\+SUGGEST|PASS|REVIEW|BLOCK|SUGGEST|待自决|未审查)】[^\n]*/;
const LINE_RE_SHORT = /【(PASS\+SUGGEST|PASS|REVIEW|BLOCK|SUGGEST|待自决|未审查)】[^\n]*/;

function firstLineMatch(text) {
  const s = String(text ?? '');
  const a = LINE_RE.exec(s);
  const b = LINE_RE_SHORT.exec(s);
  if (!a) return b;
  if (!b) return a;
  return b.index < a.index ? b : a;
}

export function isConclusionLine(text) {
  return firstLineMatch(text) !== null;
}

export function conclusionLine(text) {
  const m = firstLineMatch(text);
  if (!m) return null;
  const token = m[1];
  const state = normState(token);
  return { state, token, line: m[0].trim(), legacy: token !== state };
}

/**
 * 校验一行结论是否符合规范抬头格式。
 */
export function conforms(line) {
  const s = String(line ?? '').trim();
  const headShort = /^【(PASS\+SUGGEST|PASS|REVIEW|BLOCK|SUGGEST|待自决|未审查)】/.exec(s);
  const headFull = /^【审查结论：(PASS\+SUGGEST|PASS|REVIEW|BLOCK|SUGGEST|待自决|未审查)】/.exec(s);
  const head = headFull ?? headShort;
  if (!head) {
    return { ok: false, state: null, why: '缺少【审查结论：<标签>】或【<标签>】前缀' };
  }
  const token = head[1];
  const state = normState(token);
  if (token !== state) {
    return { ok: false, state, why: `旧字面 ${token} 应规范化为 ${state}` };
  }
  return { ok: true, state, why: 'ok' };
}

/**
 * 根据生产判定输出构造权威结论行 `line` 与逐条/汇总块 `block`。
 */
export function buildGuardVerdict({
  label = 'REVIEW',
  layer = 'DP3',
  caseId = null,
  findings = [],
  factCandidates = [],
} = {}) {
  const state = normState(label);
  const confirmed = Array.isArray(findings)
    ? findings.filter((f) => f && f.status !== 'candidate')
    : [];
  const candidates = Array.isArray(factCandidates) ? factCandidates : [];
  const total = confirmed.length + candidates.length;
  const caseSuffix = caseId ? `（案件 ${caseId}）` : '';

  let line;
  if (state === 'BLOCK') {
    line = `【审查结论：BLOCK】共发现 ${total || 1} 处必须修改${caseSuffix}。`;
  } else if (state === 'REVIEW' || state === '待自决') {
    line = `【审查结论：${state}】共发现 ${total} 处需人工确认${caseSuffix}。`;
  } else if (state === 'PASS+SUGGEST') {
    line = `【审查结论：PASS+SUGGEST】发现 ${total || 1} 处建议优化，待人工复核${caseSuffix}。`;
  } else if (state === 'PASS') {
    line = `【审查结论：PASS】未发现已知底线风险，待人工复核放行${caseSuffix}。`;
  } else {
    line = `【审查结论：未审查】素材未完成解析（${layer || 'DP0'}），需人工处理${caseSuffix}。`;
  }

  const allItems = [...confirmed, ...candidates];
  if (!allItems.length) {
    return { state, line, block: null, total: 0 };
  }

  const formatOne = (f, idx) => {
    const code = f.control_code || f.rule_key || '规则';
    const sev = f.severity ? `/${f.severity}` : '';
    const quote = mdTextSafe(f.quote || f.statement || '');
    const loc = f.location?.start != null && f.location?.end != null
      ? `正文[${f.location.start}:${f.location.end}]`
      : (f.location?.kind || '全文');
    const refs = Array.isArray(f.authority_ref) && f.authority_ref.length
      ? f.authority_ref.slice(0, 2).map((r) => r.entry_id || r.article || r.source).filter(Boolean).join('、')
      : '待核对依据';
    return `${idx + 1}.【${code}${sev}】位置：${loc}｜命中：「${quote}」｜依据：${refs}`;
  };

  let block;
  if (allItems.length < REPORT_LINK_MIN_ISSUES) {
    block = allItems.map(formatOne).join('\n');
  } else {
    const byCode = new Map();
    for (const f of allItems) {
      const k = f.control_code || '候选观察';
      byCode.set(k, (byCode.get(k) || 0) + 1);
    }
    const summaryLines = [...byCode.entries()].map(([k, cnt]) => `· ${k} 类问题：${cnt} 个`);
    const detailLines = allItems.slice(0, 5).map(formatOne);
    block = [...summaryLines, '', ...detailLines].join('\n');
  }

  return { state, line, block, total: allItems.length };
}

/**
 * 本轮审查权威结论行暂存槽：由 judge_copy / 媒体入站写入，由 envelope.toCardOrText 一次性消费。
 * 这样无需改动 ws_daemon.replyTo 的五参数签名（verify_outbound.py B9），也不在 agent.mjs 引入卡片逻辑（verify_cards.mjs L5）。
 */
let _pendingTurnVerdict = null;

export function setPendingTurnVerdict(verdict) {
  if (!verdict || !verdict.line) {
    _pendingTurnVerdict = null;
    return;
  }
  _pendingTurnVerdict = { ...verdict, at: Date.now() };
}

export function consumePendingTurnVerdict(maxAgeMs = 120_000) {
  const cur = _pendingTurnVerdict;
  _pendingTurnVerdict = null;
  if (!cur || !cur.line) return null;
  if (Date.now() - (cur.at ?? 0) > maxAgeMs) return null;
  return cur;
}

/**
 * 当 LLM 润色层不可用（如 HTTP 402 余额不足或超时）时，直接由生产判定引擎结果构造标准卡片块。
 * 保证群内送审 100% 产出结构化 V2 审查卡片与工作台 case_id，不因润色模型故障而退化为报错文本。
 *
 * 三种模态的四维文案、表格列名、替换件小标题、下一步措辞、覆盖边界，
 * 全部来自 `audit_modality_specs.mjs` 那一张表 —— 这里不再手写任何一句模态文案。
 */
export function formatDirectAuditCardReply({ mediaGot = null, textJudgeResult = null } = {}) {
  const openTag = '[' + '[card:evidence]]';
  const closeTag = '[' + '[/card]]';

  if (mediaGot) {
    const j = mediaGot.judgment ?? {};
    const label = j.label ?? '未审查';
    const caseId = mediaGot.case_id ?? j.case_id ?? null;
    const fd = mediaGot.four_dim_audit ?? j.four_dim_audit ?? null;
    const modality = resolveModality(mediaGot);
    const spec = specFor(mediaGot);
    if (!spec) return null;      // 模态不明 → 不生成四维卡（一张错的覆盖声明比没有卡更糟）

    const payload = fd && fd.one_line
      ? renderFourDimAuditPayload({
        modality: spec.key,
        fd,
        label,
        caseId,
        productLine: mediaGot.product_line ?? j.product_line ?? null,
        productLineCategory: mediaGot.product_line_resolution?.display_category
          ?? mediaGot.display_category ?? null,
        productLineNote: mediaGot.product_line_resolution?.note ?? null,
        evChain: mediaGot.evidence_chain,
      })
      : null;
    if (payload) return `${openTag}\n${JSON.stringify(payload)}\n${closeTag}`;

    // 降级卡的抬头也要显式带状态标签 —— 与四维卡同一个判据，不另写一份。
    const { stateTag, isBlock, isPass, isUnreviewed } =
      classifyAuditState(label, mediaGot.judgment?.overall ?? '');
    const humanLabel = isUnreviewed ? `${spec.receiptNoun}未能读取` : (HUMAN_LABEL[stateTag] || '需人工确认');
    const degraded = {
      audit_modality: spec.key,
      // 配色与四维卡同一套：未审查 wathet / 拦截 red / 通过 green / 其余 orange。
      // 不写这一行，信封会给所有降级卡同一个默认色，「要不要停下看」这个信号就没了。
      tone: isUnreviewed ? 'wathet' : (isBlock ? 'red' : (isPass ? 'green' : 'orange')),
      title: `【${spec.cardNoun} · ${isUnreviewed ? '未审查' : `${stateTag} ${humanLabel}`}】${caseId ? `单号 ${caseId}` : '已完成初筛'}`,
      verdict: `结论：${humanLabel}（共命中 ${j.findings_total ?? 0} 条字面规则）`,
      groups: [
        {
          title: '审查详情',
          content: String(mediaGot.summary ?? `已完成${spec.receiptNoun}初筛。`),
          expanded: true,
        },
      ],
      fields: [
        { label: '审查结论', value: humanLabel },
        ...(caseId ? [{ label: '工作台单号', value: caseId }] : []),
      ],
      boundary: spec.boundary,
    };
    return `${openTag}\n${JSON.stringify(degraded)}\n${closeTag}`;
  }

  if (textJudgeResult && !textJudgeResult.error) {
    const r = textJudgeResult;
    const payload = renderFourDimAuditPayload({
      modality: 'text',
      fd: r.four_dim_audit ?? null,
      label: r.label ?? 'REVIEW',
      caseId: r.case_id ?? null,
      productLine: r.product_line ?? null,
      productLineCategory: r.product_line_resolution?.display_category
        ?? r.display_category ?? null,
      productLineNote: r.product_line_resolution?.note ?? null,
      evChain: r.evidence_chain,
      findings: Array.isArray(r.findings) ? r.findings.filter((f) => f && f.status !== 'candidate') : [],
    });
    if (!payload) return null;
    return `${openTag}\n${JSON.stringify(payload)}\n${closeTag}`;
  }

  return null;
}


/**
 * 话题复核执行完之后，回给群里那张回执。
 *
 * ★ 三种结果必须**长得不一样**，因为复核员下一步做的事不同：
 *   成功结案 / 本来就没法结（已结案、找不到单号）/ 我这边跑挂了。
 *   合成一句「已处理」会让第一种掩盖后两种 —— 那正是本仓库反复记的那个病。
 *
 * ★ 用 `receipt` 类型：对方只需要知道「收到了、办没办成」。
 *
 * @param {{caseId:string, action:'confirm'|'overturn'|'revise', result:object|null}} p
 * @returns {string} 卡片块文本
 */
export function buildReceiptReply({ caseId = null, action = 'confirm', result = null } = {}) {
  const openTag = '[' + '[card:receipt]]';
  const closeTag = '[' + '[/card]]';
  const r = result && typeof result === 'object' ? result : null;
  const ok = !!r?.ok;
  const ACTION_ZH = { confirm: '确认放行', overturn: '误报推翻', revise: '要求修改' };
  const verb = ACTION_ZH[action] ?? '复核';
  const id = String(caseId ?? r?.case_id ?? '').trim() || '（无单号）';

  // ★ 不谈配色/不写「已通过」：这几句话会被出站边界闸与语域规则同时检查。
  //   成功了就说「已结案」，失败就照实说**哪一类**失败。
  let verdict;
  if (ok) {
    verdict = action === 'overturn'
      ? `已按「误报推翻」结案：单号 ${id}。机器结论作废，案件记入人工推翻。`
      : `已按「确认放行」结案：单号 ${id}。`;
  } else if (r?.needs_workbench) {
    verdict = `这一句改不了正文：单号 ${id} 需要去工作台改。`;
  } else if (r?.already_closed) {
    verdict = `单号 ${id} 已经结过案了，这一句没有改动任何东西。`;
  } else if (r?.not_found) {
    verdict = `没找到单号 ${id}，这一句没有改动任何东西。`;
  } else {
    verdict = `这条复核没办成（单号 ${id}），原因见下。`;
  }

  const fields = [{ label: '动作', value: verb }, { label: '工作台单号', value: id }];
  if (ok) {
    const q = r?.precedent ?? {};
    // 判例回流只有「入队 / 没入队」两种；`queued` 为 null 或缺失时不硬说成「没有」。
    const prec = q.queued === true ? '已记入判例回流（周报的规则缺口榜会读到）'
      : q.queued === false ? '本次未产生判例回流（人机结论一致，没有分歧可记）'
        : '判例回流未测（队列读不出来）';
    fields.push({ label: '判例回流', value: prec });
  } else if (r?.error) {
    fields.push({ label: '原因', value: String(r.error).slice(0, 120) });
  }

  const note = ok
    ? '如果这条不该结，去工作台把单号重新打开即可。'
    : (r?.next_step ? String(r.next_step).slice(0, 160) : '这次没有改动案件状态，可以补一句再说一次。');

  return `${openTag}\n${JSON.stringify({
    title: ok ? '【复核已落账】' : '【复核没办成】',
    verdict,
    fields,
    note,
  })}\n${closeTag}`;
}
