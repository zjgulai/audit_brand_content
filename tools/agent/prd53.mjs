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
 */
export function formatDirectAuditCardReply({ mediaGot = null, textJudgeResult = null } = {}) {
  const openTag = '[' + '[card:evidence]]';
  const closeTag = '[' + '[/card]]';

  if (mediaGot) {
    const j = mediaGot.judgment ?? {};
    const label = j.label ?? '未审查';
    const caseId = mediaGot.case_id ?? j.case_id ?? null;
    const fd = mediaGot.four_dim_audit ?? j.four_dim_audit ?? null;

    const kindName = mediaGot.type === 'media' || String(mediaGot.reason || '').startsWith('video') ? '视频审查' : '图片审查';
    if (fd && fd.one_line) {
      const overall = fd.overall || (label === 'BLOCK' ? '发现违规需修改' : '需人工确认');
      const isBlock = overall.includes('修改') || overall.includes('违规');
      const isPass = overall.includes('未见') && !overall.includes('确认');
      const tone = isBlock ? 'red' : (isPass ? 'green' : 'orange');
      const tagLabel = isBlock ? '需修改' : (isPass ? '初筛未见违规' : '需人工确认');
      const shortTitle = fd.short_title || fd.one_line.replace(/\*\*/g, '').slice(0, 18);

      const quickFix = fd.quick_fix || fd.action_advice || '请按下方区域表格修改后重审';
      const ocrBadge = fd.ocr_status ? `【${fd.ocr_status}】` : '';
      const sceneBadge = fd.scene_status ? `【${fd.scene_status}】` : '';
      const symBadge = fd.symbol_status ? `【${fd.symbol_status}】` : '';
      const evChain = mediaGot.evidence_chain;
      const kbLine = evChain?.status === 'found' && evChain.evidence?.[0]
        ? `· 知识库依据：命中规则文档 ${evChain.evidence[0].docId}（请求号 ${evChain.evidence[0].requestId || '已记账'}）`
        : `· 知识库检索：${evChain?.status ? `状态=${evChain.status}` : '由本机 19 项控制点与外部法规库核验'}`;

      const checkListMd = [
        `【马上怎么改】${quickFix}`,
        '',
        '【四维快速体检】',
        `· ① 图内文字（OCR）${ocrBadge}：${fd.ocr_summary || '未见明显违规宣传词'}`,
        `· ② 画面语义${sceneBadge}：${fd.scene_semantics || '常规产品展示场景'}`,
        `· ③ 视觉符号${symBadge}：${fd.visual_symbols || '未见异常认证图标或高危符号'}`,
        kbLine,
        '',
        '【④ 区域级画面审计（对表改图）】',
      ].join('\n');

      const regionRows = Array.isArray(fd.region_rows) && fd.region_rows.length
        ? fd.region_rows.map((r) => [
            r.region || '画面区域',
            r.issue || '—',
            r.fix || '—',
          ])
        : (Array.isArray(fd.region_audit) && fd.region_audit.length
            ? fd.region_audit.map((line) => {
                const [left, ...rest] = String(line).split(/[：:]/);
                return [
                  (left || '区域').trim(),
                  rest.join('：').trim() || String(line),
                  quickFix.slice(0, 24),
                ];
              })
            : [['全图', '未见明显局部违规', '转工作台人工复核']]);

      const payload = {
        tone,
        title: `【${kindName} · ${tagLabel}】${shortTitle}`,
        verdict: `【核心卡点】${fd.one_line}`.slice(0, 58),
        reasoning: checkListMd,
        columns: [
          { name: 'region', display_name: '画面位置', data_type: 'text' },
          { name: 'issue', display_name: '发现的问题', data_type: 'text' },
          { name: 'fix', display_name: '直接怎么改', data_type: 'text' },
        ],
        rows: regionRows,
        ...(fd.copy_paste_snippet ? { snippet: fd.copy_paste_snippet } : {}),
        fields: [
          { label: '审查结论', value: overall },
          { label: '下一步', value: isBlock ? '改图后重审' : '转工作台人工复核' },
          ...(caseId ? [{ label: '工作台单号', value: caseId }] : []),
        ],
        boundary: '已覆盖：图内文字(OCR) · 画面语义 · 视觉符号 · 区域级画面审计',
      };
      return `${openTag}\n${JSON.stringify(payload)}\n${closeTag}`;
    }

    const humanLabel = label === 'BLOCK' ? '发现违规需修改' : (label === '未审查' ? '图片未能读取' : '需人工确认');
    const payload = {
      title: `【${kindName}：${humanLabel}】${caseId ? `单号 ${caseId}` : '已完成初筛'}`,
      verdict: `结论：${humanLabel}（共命中 ${j.findings_total ?? 0} 条字面规则）`,
      groups: [
        {
          title: '审查详情',
          content: String(mediaGot.summary ?? '已完成图片初筛。'),
          expanded: true,
        },
      ],
      fields: [
        { label: '审查结论', value: humanLabel },
        ...(caseId ? [{ label: '工作台单号', value: caseId }] : []),
      ],
      boundary: '机器只做风险筛查，需人工最终复核',
    };
    return `${openTag}\n${JSON.stringify(payload)}\n${closeTag}`;
  }

  if (textJudgeResult && !textJudgeResult.error) {
    const r = textJudgeResult;
    const rawLabel = r.label ?? 'REVIEW';
    const isBlock = rawLabel === 'BLOCK';
    const isPass = rawLabel === 'PASS';
    const tone = isBlock ? 'red' : (isPass ? 'green' : 'orange');
    const humanLabel = isBlock ? '发现违规需修改' : (isPass ? '初筛未见违规' : '需人工确认');
    const tagLabel = isBlock ? '需修改' : (isPass ? '初筛未见违规' : '需人工确认');
    const caseId = r.case_id ?? null;
    const findings = Array.isArray(r.findings)
      ? r.findings.filter((f) => f && f.status !== 'candidate')
      : [];
    const total = findings.length;
    const firstQuotes = findings.slice(0, 2).map((f) => `「${mdTextSafe(f.quote || '')}」`).join('、');
    const shortTitle = total > 0
      ? `命中${firstQuotes}等${total}处风险`.slice(0, 18)
      : '未见已知字面红线词';
    const oneLine = total > 0
      ? `【核心卡点】文案含${firstQuotes}，触碰合规红线，需修改后再投放。`.slice(0, 58)
      : '【核心结论】未命中已知禁用词，请转人工确认语境。';
    const quickFix = total > 0
      ? `请删掉或替换${firstQuotes}，改为客观功能描述并补充实测条件说明。`
      : '文案字面初筛未见违规，转工作台人工复核即可。';
    const evChain = r.evidence_chain;
    const kbLine = evChain?.status === 'found' && evChain.evidence?.[0]
      ? `\n\n【知识库依据】docId=${evChain.evidence[0].docId}（requestId=${evChain.evidence[0].requestId || '已记账'}）`
      : (evChain?.status ? `\n\n【知识库状态】status=${evChain.status}` : '');

    const rows = total > 0
      ? findings.slice(0, 5).map((f, idx) => {
          const quote = mdTextSafe(f.quote || '问题片段');
          const code = f.control_code || f.rule_key || `第${idx + 1}处`;
          const ref = Array.isArray(f.authority_ref) && f.authority_ref[0]
            ? (f.authority_ref[0].entry_id || f.authority_ref[0].source || '平台广告规范')
            : '平台合规规范';
          return [
            `第 ${idx + 1} 处（${code}）`,
            `出现禁用/高危表述「${quote}」（依据：${ref}）`,
            `删掉「${quote}」或改为客观事实描述`,
          ];
        })
      : [['全文扫描', '未命中字面违规词', '转工作台人工确认语境']];

    const payload = {
      tone,
      title: `【文案审查 · ${tagLabel}】${shortTitle}`,
      verdict: oneLine,
      reasoning: `【马上怎么改】${quickFix}${kbLine}\n\n【问题位置与改法对照表】`,
      columns: [
        { name: 'region', display_name: '位置与规则', data_type: 'text' },
        { name: 'issue', display_name: '发现的问题', data_type: 'text' },
        { name: 'fix', display_name: '直接怎么改', data_type: 'text' },
      ],
      rows,
      fields: [
        { label: '审查结论', value: humanLabel },
        { label: '品线', value: `${r.product_line ?? '吸奶器'}` },
        { label: '命中处数', value: `${total} 处` },
        ...(caseId ? [{ label: '工作台单号', value: caseId }] : []),
      ],
      boundary: (r.product_line_resolution?.note || '已覆盖：19项活跃控制点与外部法规库').slice(0, 88),
    };
    return `${openTag}\n${JSON.stringify(payload)}\n${closeTag}`;
  }

  return null;
}


