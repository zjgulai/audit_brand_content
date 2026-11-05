/**
 * standard_cards.mjs —— 全场景「5 + 4」标准化卡片模版矩阵（ADHD 3秒扫读版 · 零未渲染符号）
 *
 * 五张被动回复卡（面向使用者：设计师/运营/文案/复核员）：
 *   R-1 buildAuditResultCard    内容审查结论卡（图文四维 / 视频多模态 / 文案与链接法源）
 *   R-2 buildQuickReceiptCard   长耗时收件回执卡（暖粉 carmine 表头 + carmine-50 底色带）
 *   R-3 buildCaseStatusCard     工作台单号与队列反查卡（原生进度表）
 *   R-4 buildRuleAnswerCard     规则问答与合规替代写法卡
 *   R-5 buildCannotReadCard     无法读取与最快替代路径卡
 *
 * 四张主动巡检/总结推送卡（面向运营者与运维者；全部由 push_policy 硬锁定仅发测试群）：
 *   P-1 buildOpsDigestCard      【运营日报/周报】审核漏斗与高频雷区总结卡
 *   P-2 buildSlaReminderCard    【SLA 催办】待人工复核与待下架超时提醒卡
 *   P-3 buildBaselineInspectCard【法规与基线巡检】外部政策/PRD 变动与待收提醒卡
 *   P-4 buildHealthAlertCard    【运维自检】系统健康、模型额度与链路异常卡
 */
import { build, renderText } from '../reply-cards/registry.mjs';
import { plainify, plainifyCard, hasMdSymbols } from './plain.mjs';
import { TEST_GROUP_CHAT_ID, assertTestGroupTarget } from './push_policy.mjs';
import { resolveModality, renderFourDimAuditPayload, specFor } from './audit_modality_specs.mjs';

const HUMAN_LABEL = {
  BLOCK: '发现违规需修改',
  REVIEW: '需人工确认',
  待自决: '需人工确认',
  PASS: '初筛未见违规',
  'PASS+SUGGEST': '初筛通过（附优化建议）',
  未审查: '素材未能读取',
};

const HUMAN_STATUS = {
  unassigned: '待领单复核',
  claimed: '人工复核中',
  reviewed: '已复核待签发',
  released: '已签发放行',
  closed: '已结案',
};

function clean(s) {
  return plainify(String(s ?? '')).trim();
}

/* ═══════════════════ 一、五张被动回复卡（R-1 ~ R-5） ═══════════════════ */

/**
 * R-1：内容审查结论卡（统一覆盖图片四维、视频、文案/链接/云文档）
 */
export function buildAuditResultCard({ mediaGot = null, textJudgeResult = null } = {}) {
  if (mediaGot) {
    const j = mediaGot.judgment ?? {};
    const rawLabel = j.label ?? 'REVIEW';
    const caseId = mediaGot.case_id ?? j.case_id ?? null;
    const fd = mediaGot.four_dim_audit ?? j.four_dim_audit ?? null;
    const modality = resolveModality(mediaGot);
    const spec = specFor(mediaGot);
    if (!spec) return null;

    if (fd && fd.one_line) {
      return build('evidence', renderFourDimAuditPayload({
        modality: spec.key,
        fd,
        label: rawLabel,
        caseId,
        productLine: mediaGot.product_line ?? j.product_line ?? null,
        productLineNote: mediaGot.product_line_resolution?.note ?? null,
        evChain: mediaGot.evidence_chain,
        cleanFn: clean,
      }));
    }

    const humanLabel = HUMAN_LABEL[rawLabel] || '需人工确认';
    const tone = rawLabel === 'BLOCK' ? 'red' : (rawLabel === 'PASS' ? 'green' : 'orange');
    return build('evidence', {
      audit_modality: spec.key,
      tone,
      title: `【${spec.cardNoun} · ${humanLabel}】${caseId ? `单号 ${caseId}` : '已完成初筛'}`,
      verdict: `【核心结论】${humanLabel}（命中 ${j.findings_total ?? 0} 处规则）`.slice(0, 58),
      reasoning: `${spec.checklistHeading}\n· ① ${spec.dimensions[0].name}：已完成扫描\n· ② 下一步：${spec.nextStep.escalate}`,
      fields: [
        { label: '审查结论', value: humanLabel },
        { label: '下一步', value: rawLabel === 'BLOCK' ? spec.nextStep.rework : spec.nextStep.escalate },
        ...(caseId ? [{ label: '工作台单号', value: caseId }] : []),
      ],
      boundary: spec.boundary,
    });
  }

  if (textJudgeResult && !textJudgeResult.error) {
    const r = textJudgeResult;
    const payload = renderFourDimAuditPayload({
      modality: 'text',
      fd: r.four_dim_audit ?? null,
      label: r.label ?? 'REVIEW',
      caseId: r.case_id ?? null,
      productLine: r.product_line ?? null,
      productLineNote: r.product_line_resolution?.note ?? null,
      evChain: r.evidence_chain,
      findings: Array.isArray(r.findings) ? r.findings.filter((f) => f && f.status !== 'candidate') : [],
      cleanFn: clean,
    });
    return payload ? build('evidence', payload) : null;
  }

  return null;
}

/**
 * R-2：长耗时收件回执卡（暖粉 carmine 表头 + carmine-50 底色带）
 */
export function buildQuickReceiptCard({ mediaKind = '图片', fileName = '', receivedAt = '' } = {}) {
  return build('receipt', {
    title: `【已接单】正在审查你的${clean(mediaKind)}`,
    verdict: `已收到${fileName ? `「${clean(fileName)}」` : ''}，正在跑四维审查与建案，约 10 秒出结果。`,
    fields: [
      { label: '素材类型', value: clean(mediaKind) },
      ...(receivedAt ? [{ label: '接收时间', value: clean(receivedAt) }] : []),
      { label: '当前动作', value: '审查完直接回卡片' },
    ],
  });
}

/**
 * R-3：工作台单号与队列反查卡
 */
export function buildCaseStatusCard(queryResult = {}) {
  if (queryResult.mode === 'detail') {
    if (!queryResult.found || !queryResult.case) {
      return build('find-nothing', {
        title: `【单号查询】未找到 ${clean(queryResult.case_id || '该案件')}`,
        paths: [
          { where: '内容审核工作台数据库', how: `按单号 ${clean(queryResult.case_id)} 精确查找`, result: '未找到记录' },
        ],
        nextStep: '请核对单号是否完整（格式如 case-3f0f2b6b4ff819bb1a3a），或在群内直接重新发素材送审。',
      });
    }
    const c = queryResult.case;
    const hLabel = HUMAN_LABEL[c.label] || clean(c.label || '待确认');
    const hStatus = HUMAN_STATUS[c.status] || clean(c.status || '待处理');
    const nextAction = c.status === 'released'
      ? '已完成签发，可正常投放'
      : (c.label === 'BLOCK' ? '需业务修改素材后重新送审' : '待复核员在工作台领单确认');

    return build('data-table', {
      title: `【案件进度】${clean(c.case_id)} · ${hStatus}`,
      subtitle: `品线：${clean(c.product_line || '吸奶器')} ｜ 初筛结论：${hLabel}`,
      verdict: `【当前卡点】该单处于「${hStatus}」，下一步：${nextAction}。`,
      columns: [
        { name: 'k', display_name: '检查项', data_type: 'text' },
        { name: 'v', display_name: '当前状态', data_type: 'text' },
      ],
      rows: [
        ['工作台单号', clean(c.case_id)],
        ['所属品线', clean(c.product_line || '吸奶器')],
        ['内容类型', `${clean(c.content_type || '文本')}（${clean(c.entry_channel || '群消息')}）`],
        ['机器初筛结论', `${hLabel}（命中 ${c.confirmed_findings_count ?? 0} 处）`],
        ['当前流转状态', hStatus],
        ['当前负责人', clean(c.assignee || '暂未领单')],
        ['下一步动作', nextAction],
      ],
      fields: [
        { label: '初筛结论', value: hLabel },
        { label: '流转状态', value: hStatus },
        { label: '命中处数', value: `${c.confirmed_findings_count ?? 0} 处` },
      ],
    });
  }

  const cases = Array.isArray(queryResult.cases) ? queryResult.cases : [];
  const total = queryResult.total ?? cases.length;
  const rows = cases.slice(0, 10).map((c) => [
    clean(c.case_id),
    clean(c.product_line || '吸奶器'),
    HUMAN_LABEL[c.label] || clean(c.label || '待确认'),
    HUMAN_STATUS[c.status] || clean(c.status || '待处理'),
    c.status === 'unassigned' ? '待领单复核' : (c.assignee ? `${clean(c.assignee)} 处理中` : '待流转'),
  ]);

  return build('data-table', {
    title: `【工作台队列】当前共 ${total} 单（展示最近 ${rows.length} 单）`,
    subtitle: '按创建时间倒序 · 零黑话视图',
    verdict: total > 0
      ? `【队列概况】共有 ${total} 单在库，其中 ${cases.filter((x) => x.status === 'unassigned').length} 单待领单复核。`
      : '【队列概况】当前工作台没有积压案件。',
    columns: [
      { name: 'cid', display_name: '工作台单号', data_type: 'text' },
      { name: 'pl', display_name: '品线', data_type: 'text' },
      { name: 'lbl', display_name: '初筛结论', data_type: 'text' },
      { name: 'st', display_name: '流转状态', data_type: 'text' },
      { name: 'todo', display_name: '下一步', data_type: 'text' },
    ],
    rows,
    fields: [
      { label: '总单数', value: `${total} 单` },
      { label: '待领单', value: `${cases.filter((x) => x.status === 'unassigned').length} 单` },
      { label: '需修改', value: `${cases.filter((x) => x.label === 'BLOCK').length} 单` },
    ],
  });
}

/**
 * R-4：规则问答与合规替代写法卡
 */
export function buildRuleAnswerCard({
  title = '【规则解答】合规用词说明',
  verdict = '',
  reasoning = '',
  replacement = '',
  fields = [],
  evidenceList = [],
  boundary = '',
} = {}) {
  return build('evidence', {
    tone: 'blue',
    title: clean(title),
    verdict: clean(verdict).slice(0, 58),
    reasoning: clean(reasoning),
    ...(replacement ? { snippet: clean(replacement) } : {}),
    ...(evidenceList.length
      ? { groups: [{ title: '法规与规则依据明细', content: clean(evidenceList.join('\n')), expanded: false }] }
      : {}),
    fields: fields.slice(0, 4),
    boundary: clean(boundary).slice(0, 88),
  });
}

/**
 * R-5：无法读取与最快替代路径卡
 */
export function buildCannotReadCard({
  title = '【无法读取】这份素材暂时没读出来',
  kind = '文件',
  from = '群成员',
  at = '刚刚',
  why = '该格式暂未接通直接解析通道',
  alternative = '请直接截图发到群里并 @Guard，或转成飞书云文档发链接给我。',
} = {}) {
  return build('cannot-read', {
    title: clean(title),
    verdict: `【原因】${clean(why)}`.slice(0, 58),
    item: { kind: clean(kind), from: clean(from), at: clean(at), content: '未读取' },
    why: clean(why),
    alternative: clean(alternative),
  });
}

/* ═══════════════════ 二、四张主动巡检与总结推送卡（P-1 ~ P-4） ═══════════════════ */

/**
 * P-1：【运营日报/周报】审核漏斗与高频雷区总结卡（面向运营负责人 / 合规PM）
 * 支持注入耗时趋势（timingTrend）与判例回流「规则缺口榜」（ruleGapRanking / gapUnattributed）。
 */
export function buildOpsDigestCard({
  periodLabel = '今日总结',
  cases = [],
  topPitfalls = [],
  timingTrend = null,
  ruleGapRanking = null,
  gapUnattributed = null,
} = {}) {
  const total = cases.length;
  const blockCount = cases.filter((c) => c.label === 'BLOCK').length;
  const reviewCount = cases.filter((c) => c.label === 'REVIEW' || c.label === '待自决').length;
  const passCount = cases.filter((c) => c.label === 'PASS').length;
  const pendingClaim = cases.filter((c) => c.status === 'unassigned').length;

  const byLine = new Map();
  for (const c of cases) {
    const pl = clean(c.product_line || '吸奶器');
    const cur = byLine.get(pl) || { total: 0, block: 0, pending: 0 };
    cur.total += 1;
    if (c.label === 'BLOCK') cur.block += 1;
    if (c.status === 'unassigned') cur.pending += 1;
    byLine.set(pl, cur);
  }
  const lineRows = [...byLine.entries()].map(([pl, st]) => [
    pl,
    `${st.total} 单`,
    `${st.block} 单`,
    `${st.pending} 单`,
  ]);
  if (!lineRows.length) {
    lineRows.push(['全部品线', '0 单', '0 单', '0 单']);
  }

  const ruleCount = new Map();
  for (const c of cases) {
    for (const f of c.findings_preview || []) {
      const k = `${clean(f.control_code || '规则')}（例：「${clean(f.quote || '').slice(0, 14)}」）`;
      ruleCount.set(k, (ruleCount.get(k) || 0) + 1);
    }
  }
  const pitfalls = topPitfalls.length
    ? topPitfalls.map(clean)
    : [...ruleCount.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([k, cnt], i) => `第 ${i + 1} 名：${k} —— 共踩雷 ${cnt} 次`);
  if (!pitfalls.length) {
    pitfalls.push('本期暂未触发高危字面红线词，图片医疗数值暗示（如高烧度数）仍需重点关注。');
  }

  const reasoningLines = [
    '【本期高频踩雷榜（可直接转发提醒设计/运营）】',
    ...pitfalls.map((p) => `· ${p}`),
  ];

  if (timingTrend && Array.isArray(timingTrend.rows) && timingTrend.rows.length > 0) {
    reasoningLines.push('', '【各通道耗时趋势（对比上一周期）】');
    for (const r of timingTrend.rows.slice(0, 4)) {
      const p50 = r.p50_ms != null ? `${r.p50_ms}ms` : '无读数';
      const p90 = r.p90_ms != null ? `${r.p90_ms}ms` : '无读数';
      const delta = r.p90_delta_ms != null
        ? (r.p90_delta_ms > 0 ? `+${r.p90_delta_ms}ms` : `${r.p90_delta_ms}ms`)
        : '持平';
      reasoningLines.push(
        `· ${clean(r.carrier)}（${r.n_current ?? 0} 单）：P50=${p50} · P90=${p90}（较上期 ${delta}）`
      );
    }
  }

  if (Array.isArray(ruleGapRanking)) {
    reasoningLines.push('', '【规则缺口榜（人工复核与机器五标签分歧）】');
    if (ruleGapRanking.length === 0) {
      reasoningLines.push('· 本期暂无人工推翻或改判记录');
    } else {
      const dirLabel = {
        over_strict: '机器偏严/误报',
        under_strict: '机器偏松/漏报',
        capability_gap: '解析盲区',
        unknown: '方向待定',
      };
      for (const item of ruleGapRanking.slice(0, 3)) {
        const dText = dirLabel[item.direction] || '分歧';
        const sample = item.sample_quote ? `（例：「${clean(item.sample_quote).slice(0, 14)}」）` : '';
        reasoningLines.push(
          `· 第 ${item.rank} 名：${clean(item.control_code)} —— 分歧 ${item.count} 次（${dText}）${sample}`
        );
      }
    }
    if (gapUnattributed && Number(gapUnattributed.n) > 0) {
      reasoningLines.push(`· 另有 ${gapUnattributed.n} 条分歧待归因控制点`);
    }
  }

  reasoningLines.push('', '【各品线送审与积压分布】');

  const tone = pendingClaim >= 5 || blockCount >= 5 ? 'orange' : 'green';
  return build('evidence', {
    tone,
    title: `【审核${clean(periodLabel)}】共审 ${total} 单 · 需修改 ${blockCount} 单 · 待复核 ${pendingClaim} 单`,
    verdict: `【一句话盘点】本期送审 ${total} 单，拦截违规 ${blockCount} 单，待人工确认 ${reviewCount} 单。`.slice(0, 58),
    reasoning: reasoningLines.join('\n'),
    columns: [
      { name: 'pl', display_name: '品线', data_type: 'text' },
      { name: 'tot', display_name: '送审总数', data_type: 'text' },
      { name: 'blk', display_name: '违规需改', data_type: 'text' },
      { name: 'pend', display_name: '待领单复核', data_type: 'text' },
    ],
    rows: lineRows,
    fields: [
      { label: '送审总数', value: `${total} 单` },
      { label: '需修改', value: `${blockCount} 单` },
      { label: '需人工确认', value: `${reviewCount} 单` },
      { label: '初筛通过', value: `${passCount} 单` },
    ],
    boundary: '统计范围：内容审核工作台实时投影库（仅推送至测试群）',
  });
}

/**
 * P-2：【SLA 催办】待人工复核与待下架超时提醒卡（面向复核员 / 签发人 / 统筹）
 */
export function buildSlaReminderCard({ cases = [] } = {}) {
  const actionable = cases.filter((c) => c.status === 'unassigned' || c.status === 'claimed');
  const blockPending = actionable.filter((c) => c.label === 'BLOCK').length;
  const rows = actionable.slice(0, 8).map((c) => [
    clean(c.case_id),
    clean(c.product_line || '吸奶器'),
    HUMAN_LABEL[c.label] || clean(c.label || '待确认'),
    HUMAN_STATUS[c.status] || '待领单',
    c.label === 'BLOCK' ? '高优复核或退回改图' : '去工作台领单确认',
  ]);
  if (!rows.length) {
    rows.push(['无积压', '—', '—', '全部已处理', '无需操作']);
  }

  return build('evidence', {
    tone: blockPending > 0 ? 'red' : (actionable.length > 0 ? 'orange' : 'green'),
    title: `【待办催办】当前有 ${actionable.length} 单等待人工复核（含高危 ${blockPending} 单）`,
    verdict: actionable.length > 0
      ? `【马上处理】有 ${actionable.length} 单停在待复核队列，请相关复核员前往工作台领单。`.slice(0, 58)
      : '【队列清空】当前所有送审案件均已处理完毕。',
    reasoning: '【待处理案件清单（优先处理「发现违规需修改」单）】',
    columns: [
      { name: 'cid', display_name: '工作台单号', data_type: 'text' },
      { name: 'pl', display_name: '品线', data_type: 'text' },
      { name: 'lbl', display_name: '初筛结论', data_type: 'text' },
      { name: 'st', display_name: '当前状态', data_type: 'text' },
      { name: 'act', display_name: '需要你做什么', data_type: 'text' },
    ],
    rows,
    fields: [
      { label: '待处理总数', value: `${actionable.length} 单` },
      { label: '高危需改单', value: `${blockPending} 单` },
      { label: '工作台入口', value: 'ca.luteos.com' },
    ],
    boundary: '定时催办当前仅推送到测试群，稳定后再扩群',
  });
}

/**
 * P-3：【法规与基线巡检】外部政策/PRD 变动与待收提醒卡（面向合规PM / 法务）
 */
export function buildBaselineInspectCard({
  kind = '法规与基线巡检',
  hasChange = false,
  summary = '上游 PRD 与 62 条外部法规库指纹一致，未见漂移',
  items = [],
  actionAdvice = '当前规则基线稳定，无需人工干预。',
} = {}) {
  const rows = items.length
    ? items.map((it) => [
        clean(it.target || '基线文档'),
        clean(it.change || '检测到内容更新'),
        clean(it.action || '请核对并更新规则指纹'),
      ])
    : [['PRD 与 62 条外部法规库', '内容指纹完全一致', '无需操作']];

  return build('evidence', {
    tone: hasChange ? 'purple' : 'green',
    title: `【${clean(kind)}】${hasChange ? '检测到上游规则/文档更新' : '基线核对一致'}`,
    verdict: `【巡检结论】${clean(summary)}`.slice(0, 58),
    reasoning: `【下一步建议】${clean(actionAdvice)}\n\n【巡检明细表】`,
    columns: [
      { name: 't', display_name: '巡检对象', data_type: 'text' },
      { name: 'c', display_name: '巡检结果', data_type: 'text' },
      { name: 'a', display_name: '处理动作', data_type: 'text' },
    ],
    rows,
    fields: [
      { label: '巡检状态', value: hasChange ? '发现变动需核对' : '基线一致' },
      { label: '变动项数', value: `${items.length} 项` },
    ],
    boundary: '每日自动巡检一次（仅推送至测试群）',
  });
}

/**
 * P-4：【运维自检】系统健康、模型额度与链路异常卡（面向系统运维 / 开发者）
 */
export function buildHealthAlertCard({
  healthy = true,
  title = '系统四条核心通道全部正常',
  summary = '飞书长连接、多模态审图网关、本地 OCR 与工作台数据库均在线。',
  checks = [],
  actionAdvice = '系统运行正常，无需人工介入。',
} = {}) {
  const rows = checks.length
    ? checks.map((c) => [
        clean(c.name || '模块'),
        clean(c.status || '正常'),
        clean(c.detail || '—'),
      ])
    : [
        ['飞书长连接（Guard）', '正常在线', 'WebSocket 实时监听中'],
        ['多模态视觉大模型（VOD）', '正常在线', 'gemini-3.1-flash-lite 四维审图就绪'],
        ['本地 OCR 引擎', '正常在线', 'Vision 二进制就绪'],
        ['工作台权威账本与投影库', '正常在线', '读写与幂等锁正常'],
      ];

  return build('evidence', {
    tone: healthy ? 'green' : 'red',
    title: `【运维自检 · ${healthy ? '全部正常' : '发现异常'}】${clean(title)}`,
    verdict: `【系统状态】${clean(summary)}`.slice(0, 58),
    reasoning: `【运维处理建议】${clean(actionAdvice)}\n\n【各通道实测读数】`,
    columns: [
      { name: 'comp', display_name: '核心通道', data_type: 'text' },
      { name: 'st', display_name: '当前状态', data_type: 'text' },
      { name: 'dt', display_name: '实测读数', data_type: 'text' },
    ],
    rows,
    fields: [
      { label: '整体状态', value: healthy ? '全部正常' : '存在故障通道' },
      { label: '在线服务', value: 'Guard (cli_aa600ebeed38dccf)' },
    ],
    boundary: '运维巡检卡片当前仅推送到测试群',
  });
}

/**
 * 定时与主动巡检卡片唯一打包闸门：强制校验目标群必须是测试群（oc_49a7cfb2861cffa4365ca8491f398d32），
 * 并确保卡片零 Markdown 未渲染符号（* 或 `）。实际网络发送统一走 reply-cards/index.mjs 或 ws_daemon.mjs。
 */
export function prepareScheduledPush(card, {
  targetChatId = TEST_GROUP_CHAT_ID,
} = {}) {
  const verifiedChatId = assertTestGroupTarget(targetChatId);
  const cleanCard = plainifyCard(card);
  if (hasMdSymbols(JSON.stringify(cleanCard))) {
    throw new Error('卡片中仍残留未渲染的 Markdown 符号（* 或 `），已阻断发送');
  }
  const text = renderText(cleanCard);
  return { ok: true, chatId: verifiedChatId, card: cleanCard, text };
}
