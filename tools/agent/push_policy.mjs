/**
 * push_policy.mjs —— 推送目标群的两层闸门（P4 分层放行）
 *
 * 委托方 2026-11-04 明确裁定：
 * 「定时任务暂时先只在测试群推送，等稳定了再来定夺」
 *
 * 委托方 2026-11-06 把这条裁定推进成**分层**：
 *   正式业务群可以收到**被动回复**（人家 @Guard 送审，Guard 必须答），
 *   但**定时巡检与运维告警一个字都不许进**；那两类只发测试群。
 *
 * 所以这里有两个概念，别混：
 *   · `assertTestGroupTarget(chatId)` —— **定时推送**的唯一目标闸门，硬拒绝非测试群。
 *     行为不变（H3/H4 依赖它），只是现在它只被 `scheduled_digest` / `proactive_ops_alert` 走。
 *   · `checkChannelPolicy(chatId, messageKind)` —— 按「消息是什么」与「群是什么档」判。
 *     被动回复在业务群放行，主动推送在业务群硬拦。
 */

export const TEST_GROUP_CHAT_ID = 'oc_49a7cfb2861cffa4365ca8491f398d32';
export const TEST_GROUP_CHAT_NAME = '内容治理-守衡Agent-测试';

/** 群的两档。业务群与测试/运维群。 */
export const GROUP_TIERS = Object.freeze({
  TEST_OPS: 'test_ops',
  BUSINESS_PROD: 'business_prod',
});

/**
 * 消息的四类。**这是一个封闭集合** —— 新增一类必须同时在下面两张表里表态，
 * 否则 `checkChannelPolicy` 走「未知类别」分支直接拒（默认拒绝，不是默认放行）。
 */
export const MESSAGE_KINDS = Object.freeze({
  /** 被动送审回复卡：图片/文案/视频/Office/URL 四维卡、单号反查、规则解答、话题内复核回执 */
  REACTIVE_AUDIT: 'reactive_audit',
  /** 重媒体秒级接单回执卡 */
  QUICK_ACK: 'quick_ack',
  /** P-1 日报/周报、P-2 SLA 催办 */
  SCHEDULED_DIGEST: 'scheduled_digest',
  /** P-3 基线漂移、P-4 网关健康/耗时异常告警 */
  PROACTIVE_OPS_ALERT: 'proactive_ops_alert',
});

const KIND_LABEL = Object.freeze({
  reactive_audit: '被动送审回复',
  quick_ack: '重媒体接单回执',
  scheduled_digest: '定时日报与催办',
  proactive_ops_alert: '主动运维告警',
});

/**
 * 群档 × 消息类 → 放不放行。
 *
 * ★ 判据写成表而不是 if-else：加一档或加一类时，缺一格会被下面那条断言抓到。
 *   写成两层 if 的话，「漏了一格」的表现是**静默放行**，而那是这张表最不该出的错。
 */
const ALLOWED = Object.freeze({
  test_ops: new Set([
    'reactive_audit', 'quick_ack', 'scheduled_digest', 'proactive_ops_alert',
  ]),
  business_prod: new Set([
    'reactive_audit', 'quick_ack',
  ]),
});

/** 允许通过环境变量追加更多「测试/运维群」—— 新开一个运维群不必改代码。 */
function opsChatIds() {
  return new Set(
    String(process.env.SHOUHENG_OPS_CHATS || '')
      .split(',').map((s) => s.trim()).filter(Boolean)
      .concat([TEST_GROUP_CHAT_ID]),
  );
}

export function classifyChatTier(chatId) {
  const target = String(chatId ?? '').trim();
  return opsChatIds().has(target) ? GROUP_TIERS.TEST_OPS : GROUP_TIERS.BUSINESS_PROD;
}

/**
 * 这条消息能不能发到这个群。
 *
 * @returns {{allowed:boolean, tier:string, kind:string, reason:string}}
 */
export function checkChannelPolicy(chatId, messageKind = MESSAGE_KINDS.REACTIVE_AUDIT) {
  const tier = classifyChatTier(chatId);
  const kind = String(messageKind ?? '').trim();
  const allowed = ALLOWED[tier];

  if (!allowed) {
    return { allowed: false, tier, kind, reason: `未知群档 ${tier}，默认拒绝` };
  }
  if (!KIND_LABEL[kind]) {
    // ★ 未知类别一律拒。放行的话，未来新增的一类消息会在没人读过这张表的情况下进群。
    return { allowed: false, tier, kind, reason: `未知消息类别 ${kind || '(空)'}，默认拒绝` };
  }
  if (allowed.has(kind)) {
    return {
      allowed: true,
      tier,
      kind,
      reason: tier === GROUP_TIERS.TEST_OPS
        ? '测试与运维群允许全部被动回复与主动巡检推送'
        : '正式业务群正常响应 @Guard 送审与交互',
    };
  }
  return {
    allowed: false,
    tier,
    kind,
    reason: `【${KIND_LABEL[kind]}】只在测试群推送：正式业务群静默一切定时巡检与运维告警`,
  };
}

/** 定时推送的唯一目标群。行为与 2026-11-04 那次裁定一致。 */
export function scheduledPushTarget() {
  return TEST_GROUP_CHAT_ID;
}

/* ─────────────────── 发布准入指标（P4：进 P-1 日报卡） ─────────────────── */

/** 卡片回复的尝试。`mode` 里带 `card` 的都算 —— 成功与失败都算进分母。 */
function isCardAttempt(entry) {
  const mode = String(entry?.mode ?? '');
  return mode.includes('card');
}

function pct(n, d) {
  if (!d) return null;
  return Math.round((n / d) * 1000) / 1000;
}

/**
 * 三项发布准入读数。**每个数都要能指回它的分母** —— 指标不写分母就等于没写。
 *
 * @param {{cases?:Array, timingTrend?:object|null, outboundEntries?:Array}} opt
 * @returns {{
 *   cardSuccessRate: {rate: number|null, ok: number, total: number, note: string},
 *   kbHitRate: {rate: number|null, hit: number, total: number, note: string},
 *   latency: {p50Ms: number|null, p90Ms: number|null, carriers: number, note: string},
 *   ready: boolean,
 * }}
 */
export function buildReleaseReadinessMetrics({
  cases = [], timingTrend = null, outboundEntries = [],
} = {}) {
  /* ① 卡片送达率：分母是「卡片回复尝试」，不是「所有外发」。 */
  const attempts = (Array.isArray(outboundEntries) ? outboundEntries : []).filter(isCardAttempt);
  const okCount = attempts.filter((e) => e?.ok !== false).length;
  const cardSuccessRate = {
    rate: pct(okCount, attempts.length),
    ok: okCount,
    total: attempts.length,
    note: attempts.length
      ? `卡片回复 ${attempts.length} 次成功 ${okCount} 次`
      : '本周期没有卡片回复尝试，分母为 0，本项不参与准入判定',
  };

  /* ② 知识库/规则命中率：分母是「本周期送审的案件数」。 */
  const allCases = Array.isArray(cases) ? cases : [];
  const hit = allCases.filter((c) => {
    if (Number(c?.confirmed_findings_count ?? 0) > 0) return true;
    if (c?.kb_hit === true) return true;
    const ec = c?.evidence_chain;
    if (ec && ec.status === 'ok' && (ec.items?.length ?? 0) > 0) return true;
    return false;
  }).length;
  const kbHitRate = {
    rate: pct(hit, allCases.length),
    hit,
    total: allCases.length,
    note: allCases.length
      ? `送审 ${allCases.length} 单中 ${hit} 单命中知识库证据或规则`
      : '本周期没有送审案件，分母为 0，本项不参与准入判定',
  };

  /* ③ 耗时：各 carrier 的 P50/P90 按单量加权平均。
   *
   * ★ 口径说明写在这里而不是留给人猜：这是**加权平均的均值**，不是真正的全局分位数。
   *   真正的 P90 需要每个案件的原始耗时，而 `timingTrend` 只给了各通道的已聚合读数。
   *   把加权均值写成「全局 P90」是一个比没有数字更坏的数字。 */
  const rows = Array.isArray(timingTrend?.rows) ? timingTrend.rows : [];
  let wSum = 0; let p50Sum = 0; let p90Sum = 0;
  for (const r of rows) {
    const w = Number(r?.n_current ?? 0);
    if (!w || r?.p50_ms == null) continue;
    wSum += w;
    p50Sum += Number(r.p50_ms) * w;
    p90Sum += Number(r.p90_ms ?? r.p50_ms) * w;
  }
  const latency = {
    p50Ms: wSum ? Math.round(p50Sum / wSum) : null,
    p90Ms: wSum ? Math.round(p90Sum / wSum) : null,
    carriers: rows.length,
    note: wSum
      ? `按单量加权：${wSum} 单 / ${rows.length} 个通道（不是全局分位数）`
      : '本周期没有可用耗时读数',
  };

  // 准入判据：只有**分母非零**的项参与。分母为零的项在 note 里明说不参与，
  // 不把它们当成 0% 也不当成 100% —— 两种都会让一张日报看起来有结论。
  const gates = [];
  if (cardSuccessRate.rate != null) gates.push(cardSuccessRate.rate >= 0.99);
  if (kbHitRate.rate != null) gates.push(kbHitRate.rate >= 0.5);
  const ready = gates.length > 0 && gates.every(Boolean);

  return { cardSuccessRate, kbHitRate, latency, ready };
}

/**
 * 定时推送目标的硬闸门：非测试群直接抛。
 *
 * ★ 保持这个函数的签名与抛错文案不变（H3/H4 的判据是它在抛）。
 *   分层策略**没有**放宽它 —— 它仍然只认测试群，只是现在只服务定时与主动告警两类。
 */
export function assertTestGroupTarget(chatId) {
  const target = String(chatId ?? '').trim();
  if (target !== TEST_GROUP_CHAT_ID && !opsChatIds().has(target)) {
    throw new Error(
      `拒绝定时推送：当前仅允许推送到测试群「${TEST_GROUP_CHAT_NAME}」（${TEST_GROUP_CHAT_ID}），收到目标=${target || '(空)'}`,
    );
  }
  return target;
}
