/**
 * ops_watch_card.mjs — 工作流稳定性与耗时巡检卡（P-4）+ 运营日报/周报卡（P-1）组装器
 *
 * 调 base/ops_watch.py 读投影库与判例回流队列真实读数：
 *   1. collectOpsWatchCard：组 P-4【运维自检】卡（含各 carrier 的 P50/P90、失败率、超时率与积压告警）
 *   2. collectOpsDigestCard：组 P-1【运营日报/周报】卡（含审核漏斗、各阶段耗时趋势、判例回流「规则缺口榜」）
 * 全部经 prepareScheduledPush 硬锁测试群后返回 {ok, chatId, card, text, stats}。
 */
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import {
  buildHealthAlertCard,
  buildOpsDigestCard,
  prepareScheduledPush,
} from './standard_cards.mjs';
import { TEST_GROUP_CHAT_ID, buildReleaseReadinessMetrics } from './push_policy.mjs';
import { readEntries as readOutboundEntries } from './outbound.mjs';

const execFileP = promisify(execFile);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');

const PYTHON = (() => {
  const venv = path.join(REPO_ROOT, '.venv', 'bin', 'python');
  return fs.existsSync(venv) ? venv : 'python3';
})();

function humanMs(ms) {
  if (ms == null) return '无读数';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function humanPct(rate) {
  if (rate == null) return '0%';
  return `${(Number(rate) * 100).toFixed(1)}%`;
}

async function runOpsWatchPython({ dbPath = null, queuePath = null, days = 7, timeoutMs = 30_000 } = {}) {
  const args = [path.join(REPO_ROOT, 'base', 'ops_watch.py'), '--days', String(days)];
  if (dbPath) args.push('--db', String(dbPath));
  if (queuePath) args.push('--queue', String(queuePath));
  const { stdout } = await execFileP(PYTHON, args, {
    cwd: REPO_ROOT,
    timeout: timeoutMs,
    maxBuffer: 1 << 22,
  });
  return JSON.parse(stdout);
}

export async function collectOpsWatchCard({
  targetChatId = TEST_GROUP_CHAT_ID,
  dbPath = null,
  queuePath = null,
  timeoutMs = 30_000,
} = {}) {
  let stats;
  try {
    stats = await runOpsWatchPython({ dbPath, queuePath, timeoutMs });
  } catch (e) {
    return { ok: false, untested: true, reason: `巡检脚本执行失败：${e?.message ?? e}` };
  }

  if (!stats.ok) {
    const card = buildHealthAlertCard({
      healthy: false,
      title: '工作台投影库读不到 —— 耗时巡检未测',
      summary: `巡检器没能读投影库：${stats.untested_reason}。这是「未测」，不是「一切正常」。`,
      checks: [{ name: '工作台投影库（review.db）', status: '读不到', detail: stats.untested_reason }],
      actionAdvice: '检查工作台数据目录与 review.db 是否存在；期间耗时巡检停摆。',
    });
    const prepared = prepareScheduledPush(card, { targetChatId });
    return { ok: true, untested: true, healthy: false, ...prepared, stats };
  }

  const carriers = Object.entries(stats.by_carrier ?? {});
  const checks = carriers.map(([name, s]) => ({
    name: `审核链路 · ${name}（${s.n} 单）`,
    status: (s.failure_rate > 0 || s.timeout_rate > 0) ? '有需关注项' : '正常在线',
    detail: `P50=${humanMs(s.p50_ms)} · P90=${humanMs(s.p90_ms)} · 失败率=${humanPct(s.failure_rate)} · 超时率=${humanPct(s.timeout_rate)}`
      + (s.slowest_step ? ` · 最慢步骤=${s.slowest_step}` : ''),
  }));
  if (!checks.length) {
    checks.push({ name: '审核链路', status: '尚无案件', detail: '投影库在线但还没有已建案记录' });
  }
  checks.push({
    name: '失败与积压',
    status: (stats.failures.parse_failed || stats.failures.stuck_unassigned_gt_hours) ? '有需关注项' : '全部正常',
    detail: `解析失败 ${stats.failures.parse_failed ?? 0} 单 · 待领单超 24h ${stats.failures.stuck_unassigned_gt_hours ?? 0} 单`,
  });

  const healthy = (stats.breaches ?? []).length === 0;
  const summary = healthy
    ? `共 ${stats.total} 单：各通道 P50/P90 耗时、失败率、超时率均在阈值内，无积压。`
    : `${stats.breaches.length} 项超阈值：${stats.breaches[0]}`;
  const card = buildHealthAlertCard({
    healthy,
    title: healthy ? '审核工作流全通道正常' : '审核工作流有指标超阈值',
    summary,
    checks,
    actionAdvice: healthy ? '无需操作，巡检每日持续运行。' : '请按超阈值项排查对应通道；详见对照表。',
  });
  const prepared = prepareScheduledPush(card, { targetChatId });
  return { ok: true, untested: false, healthy, ...prepared, stats };
}

export async function collectOpsDigestCard({
  periodLabel = '今日日报',
  days = 7,
  targetChatId = TEST_GROUP_CHAT_ID,
  dbPath = null,
  queuePath = null,
  timeoutMs = 30_000,
} = {}) {
  let stats;
  try {
    stats = await runOpsWatchPython({ dbPath, queuePath, days, timeoutMs });
  } catch (e) {
    return { ok: false, untested: true, reason: `运营汇总脚本执行失败：${e?.message ?? e}` };
  }

  if (!stats.ok) {
    return { ok: false, untested: true, reason: stats.untested_reason || '投影库未测', stats };
  }

  const precedent = stats.precedent ?? {};
  const cases = stats.cases ?? [];

  // 发布准入指标：卡片送达率读外发台账，命中率读本周期案件，耗时读已聚合的趋势行。
  // ★ 台账读不到时 `readEntries` 回 `missing:true` 而不是抛；此时分母为 0，
  //   指标自己会写明「本项不参与准入判定」，不会伪装成 100%。
  let outboundEntries = [];
  let outboundNote = '';
  try {
    const led = readOutboundEntries();
    outboundEntries = led.entries ?? [];
    if (led.missing) outboundNote = '（外发台账不存在，送达率本项不参与判定）';
    else if (led.truncated) outboundNote = '（台账过大只读了尾部，送达率按尾部窗口计）';
  } catch (e) {
    outboundNote = `（外发台账读不出：${e?.message ?? e}，送达率本项不参与判定）`;
  }

  const releaseReadiness = buildReleaseReadinessMetrics({
    cases,
    timingTrend: stats.trend ?? null,
    outboundEntries,
  });

  const card = buildOpsDigestCard({
    periodLabel,
    cases,
    timingTrend: stats.trend ?? null,
    ruleGapRanking: precedent.ok ? (precedent.ranking ?? []) : [],
    gapUnattributed: precedent.ok ? (precedent.unattributed ?? null) : null,
    releaseReadiness,
  });
  const prepared = prepareScheduledPush(card, { targetChatId });
  return { ok: true, untested: false, ...prepared, stats, releaseReadiness, outboundNote };
}
