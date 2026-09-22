#!/usr/bin/env node
/**
 * ws_daemon.mjs —— 守衡 · 常驻入口（v3：接入推理内核）
 *
 * 本文件只做五件事：建立长连接、把事件交给内核、**决定回复用什么形态**、
 * 把回复发出去、管理生命周期。
 * 所有「怎么想」的逻辑都在 agent/ 目录下，怎么「成形」在 reply-cards/ 下，都不在这里。
 *
 * 版本历史：
 *   v1  打印事件 + 写死回复（验证入向链路）
 *   v2  原始事件落盘（为解析层提供真实样本）
 *   v3  接入 agent/: 真理解 + 多轮记忆 + 工具调用
 *
 * 用法：
 *   node ws_daemon.mjs              # 常驻（前台）
 *   node ws_daemon.mjs --probe      # 启动并自检，10 秒后退出
 *   node ws_daemon.mjs --dump-only  # 只落盘原始事件，不回复（排查用）
 */
import * as Lark from '@larksuiteoapi/node-sdk';
import fs from 'node:fs';
import path from 'node:path';

import { config, describeConfig, LOG_DIR, REPO_ROOT, ensureDir } from './agent/config.mjs';
import * as feishu from './agent/feishu.mjs';
import { handleMessage, flushSeen, loadedTools, status } from './agent/agent.mjs';
import { toCardOrText } from './reply-cards/envelope.mjs';
import { shapeOf } from './reply-cards/registry.mjs';
import { checkNow, checkPending, resolveChat, LARK_DOC_RE, bjDate, loadState, loadPendingState, saveState } from './agent/prd_baseline.mjs';

const PROBE     = process.argv.includes('--probe');
const DUMP_ONLY = process.argv.includes('--dump-only');

const EVENT_DUMP = path.join(LOG_DIR, 'ws_events.jsonl');
ensureDir(LOG_DIR);   // 失败只警告：日志目录建不出来不该阻止守衡启动

const T0 = Date.now();
const stamp = () => `[+${((Date.now() - T0) / 1000).toFixed(3).padStart(7)}s]`;
const log = (...a) => console.log(stamp(), ...a);

function dumpRaw(kind, data) {
  try { fs.appendFileSync(EVENT_DUMP, JSON.stringify({ at: new Date().toISOString(), kind, data }) + '\n'); }
  catch (e) { log('⚠ 事件落盘失败:', e.message); }
}

const counters = { events: 0, handled: 0, replied: 0, skipped: 0, failed: 0, uncaught: 0 };

/* ─────────────────────── 事件处理 ─────────────────────── */

async function onMessage(data) {
  counters.events++;
  dumpRaw('im.message.receive_v1', data);

  const msg = data?.message ?? {};
  const chatId = msg.chat_id;

  // 先落一行「收到了」，保证即使后面崩了，日志也能看出事件确实到了
  let preview = '';
  try { preview = JSON.parse(msg.content ?? '{}').text ?? ''; } catch {}
  const mentionNames = (msg.mentions ?? []).map((m) => m.name).filter(Boolean);
  log(`★ 收到消息 chat=${chatId} msg=${msg.message_id}`);
  log(`   type=${msg.message_type} chat_type=${msg.chat_type} mentions=[${mentionNames.join(', ')}]`);
  log(`   原文=${JSON.stringify(preview).slice(0, 200)}`);

  if (DUMP_ONLY) { log('   （--dump-only 模式，不回复）'); return; }

  // 群里被推了飞书文档/维基链接 → 顺手核一次上游基线（**不阻塞回话**）。
  // 为什么挂在这里：她 2026-09-21 10:42 就是这么把 PRD 推进来的 —— 推链接是这条链路上
  // 唯一一个"上游有新东西"的可观测信号。
  if (LARK_DOC_RE.test(preview)) void baselineWatch('link', chatId);

  const t0 = Date.now();
  let result;
  try {
    result = await handleMessage(data);
  } catch (e) {
    counters.failed++;
    log(`   ✗ 内核异常: ${e?.stack ?? e?.message ?? e}`);
    await safeSend(chatId, `我处理这条消息时内部出错了，没能回答。\n\n错误：${e?.message ?? e}\n\n（已记录，这是我的问题。）`);
    return;
  }
  const ms = Date.now() - t0;

  if (!result.reply) {
    counters.skipped++;
    log(`   · 不回复（${result.reason}）`);
    return;
  }

  counters.handled++;
  const trace = result.meta?.toolTrace ?? [];
  if (trace.length) log(`   🔧 工具: ${trace.map((t) => `${t.tool}${t.ok ? '' : '✗'}(${t.ms}ms)`).join(' → ')}`);
  if (result.meta?.compacted) log(`   🗜 历史已压缩（保留 ${result.meta.turns} 轮 + 纪要）`);
  if (result.meta?.truncated) log('   ⚠️ 回复被长度上限截断（已附截断说明，不是完整回答）');

  // ── 形态决策：模型给的是一段话，这里才决定它变成卡还是文本。
  // 决策本身在 reply-cards/envelope.mjs 里，这里只负责记录 ———
  // 「模型选了哪种形态、有没有被搬迁、有没有踩到 AI 味」必须能从日志里回答，
  // 否则调模版就只能靠重跑猜。
  const shaped = toCardOrText(result.reply);
  for (const m of shaped.moved) log(`   ↪ ${m.field} → ${m.to}（${m.why}）`);
  for (const h of shaped.lint) log(`   ${h.level === 'error' ? '❌' : '⚠️ '} 语域 ${h.id} ×${h.count} ${h.sample}`);
  if (shaped.mode === 'card') log(`   🃏 卡片 ${shaped.kind} · ${shapeOf(shaped.card)}`);
  else if (shaped.dropped) log(`   ⚠️ 卡片降级为文本：${shaped.reason}`);
  log(`   💬 回复 ${result.reply.length} 字，耗时 ${ms}ms`);

  const sent = await replyTo(chatId, msg.message_id, shaped.text, shaped.card ?? null);
  if (sent.ok) { counters.replied++; log(`   ✓ 已发送 ${sent.messageIds.filter(Boolean).join(', ')} [${sent.mode}]`); }
  else { counters.failed++; log(`   ✗ 发送失败: ${sent.error}`); }
}

/**
 * 发送一条回复。这是**唯一**的格式决策点。
 *
 * 降级链只有一条，且每一步都有明确的失败原因记录：
 *
 *   有卡片 → reply 卡  ──失败──→ reply 纯文本（正文 = 卡的降级文本）
 *   没有卡 → reply 纯文本 ──失败──→ sendMarkdown 补发
 *
 * ★ 为什么卡片的降级目标也是 reply（而不是 sendCard 新发一条）：
 *   新发一条会断开引用关系 —— 群里看到的是一段悬空的话，不知道在答谁。
 *   守住「引用」比守住「卡片」重要。
 * ★ 为什么每一步都要把原因写进正文：对方看到格式变了，得知道是为什么，
 *   而不是以为守衡改了风格。这是 2026-09-17 那次故障的直接教训 ——
 *   当时它对着一堆内部记录说「✓ 已发送」。
 */
async function replyTo(chatId, messageId, text, card = null) {
  if (card) {
    const rc = await feishu.replyCard(messageId, card);
    if (rc.ok) return { ok: true, messageIds: [rc.messageId], mode: rc.mode };
    log(`   ⚠ 卡片 reply 失败（${rc.error}），退成同一条引用里的纯文本`);
    const rt = await feishu.replyMarkdown(messageId, chatId, text);
    return rt.ok ? { ...rt, mode: `card-failed→${rt.mode}`, error: rc.error } : rt;
  }
  const r = await feishu.replyMarkdown(messageId, chatId, text);
  if (r.ok) return r;
  log(`   ⚠ reply 失败（${r.error}），改为直接发送`);
  return feishu.sendMarkdown(chatId, text);
}

async function safeSend(chatId, text) {
  try { await feishu.sendMarkdown(chatId, text); } catch (e) { log('   ✗ 兜底发送也失败:', e.message); }
}

/**
 * 上游 PRD 基线漂移：**触发 + 通报**（`tools/agent/prd_baseline.mjs` 是状态机与判据）。
 *
 * 为什么要在常驻链路里做：2026-09-21 11:52 守衡在群里对上游承诺「改版后得重新拉一次基线
 * 并记新指纹」，当天补出了 `tools/verify_prd_baseline.py` —— 但**那是"命令存在"，
 * 不是"谁在跑"**。没人跑的检查器，和一句没执行点的承诺是同一个形状。
 *
 * 两条纪律写在这里：
 *   1. **不阻塞回话**：调用点全是 `void`，出错只记日志，绝不影响正常回答。
 *   2. **未测不得沉默**：退 2 会说话，且文案里不许出现"没问题"（判据在 prd_baseline 的
 *      `stripNegated` + 离线自测第 6/7/8 条）。
 */
async function baselineWatch(reason, chatId) {
  try {
    if (chatId) saveState({ ...loadState(), lastChatId: chatId });
    const r = await checkNow({ reason });
    if (r.skipped) { log(`   · 基线检查跳过（${r.skipped}）`); return; }
    log(`   · 基线检查[${reason}] 退出码 ${r.code} —— ${r.why}${r.note ? ` · ${r.note}` : ''}`);
    if (!r.say) return;
    const target = chatId ?? await resolveChat();
    if (!target) {
      log('   ⚠ 基线检查有话要说，但还没有可通报的群 —— 只进日志（退 2 不许沉默）');
      return;
    }
    await safeSend(target, r.say);
    log(`   · 基线告警已发到 ${target}`);
  } catch (e) {
    log('   ⚠ 基线检查自身出错（不影响回话）:', e?.message ?? e);
  }
}

/**
 * 待收清单的到期提醒（判据在 `tools/verify_pending.py`，清单在 `PMO/待收清单-v1.json`）。
 *
 * 为什么要在常驻链路里做：`PRD/PRD差异对照-20260921.md` §五 记着上游 09-18 的承诺
 * 「其它已跟业务沟通接下来两周陆续整理提供」（→ 2026-10-02），而同一天那份对照表
 * **自己就写着「到期没人会提醒」**。这一层就是补上那个「谁在跑」。
 *
 * 与 `baselineWatch` 同两条纪律：不阻塞回话（调用点全是 `void`）、**未测不得沉默**。
 * 措辞上有一条额外的：**不 @ 任何人** —— 到期日是我方推算的，那是问一句，不是催办。
 */
async function pendingWatch(reason, chatId) {
  try {
    if (chatId) saveState({ ...loadState(), lastChatId: chatId });
    const r = await checkPending({ reason });
    if (r.skipped) { log(`   · 待收检查跳过（${r.skipped}）`); return; }
    log(`   · 待收检查[${reason}] 退出码 ${r.code} —— ${r.why}${r.note ? ` · ${r.note}` : ''}`);
    if (!r.say) return;
    const target = chatId ?? await resolveChat();
    if (!target) {
      log('   ⚠ 待收检查有话要说，但还没有可通报的群 —— 只进日志（退 2 不许沉默）');
      return;
    }
    await safeSend(target, r.say);
    log(`   · 待收到期提醒已发到 ${target}`);
  } catch (e) {
    log('   ⚠ 待收检查自身出错（不影响回话）:', e?.message ?? e);
  }
}

/* ─────────────────────── 事件注册 ─────────────────────── */

const handlers = {
  'im.message.receive_v1': onMessage,

  'im.chat.member.bot.added_v1': async (d) => {
    counters.events++; dumpRaw('im.chat.member.bot.added_v1', d);
    log(`★ 被拉进群 chat=${d?.chat_id}`);
    const info = await feishu.getChatInfo(d?.chat_id);
    await safeSend(d?.chat_id,
      `我是守衡，已加入「${info?.name ?? '本群'}」。\n\n` +
      `我会在这个群里做的事：回答问题、查工作区里的资料、记住我们聊过的上下文。\n` +
      `@我 就能叫我。不 @ 我不会插话。`);
  },

  'im.chat.member.bot.deleted_v1': async (d) => {
    counters.events++; dumpRaw('im.chat.member.bot.deleted_v1', d);
    log(`★ 被移出群 chat=${d?.chat_id}`);
  },

  'card.action.trigger': async (d) => {
    counters.events++; dumpRaw('card.action.trigger', d);
    log(`★ 卡片交互 ${JSON.stringify(d).slice(0, 400)}`);
    // 卡片交互的回调应答需要返回 toast，这里先只记录；
    // 等真正做出交互卡片的业务场景时再接（不预先写没有调用方的代码）。
  },
};

/* ─────────────────────── 启动 ─────────────────────── */

log('='.repeat(74));
log('守衡 · 常驻入口 v3');
for (const [k, v] of Object.entries(describeConfig())) log(`  ${k.padEnd(24)} = ${v}`);
log(`  tools                 = ${loadedTools().join(', ')}`);
log(`  事件落盘              = ${path.relative(REPO_ROOT, EVENT_DUMP)}`);
if (DUMP_ONLY) log('  ⚠ --dump-only：只落盘，不回复');
log('='.repeat(74));

const dispatcher = new Lark.EventDispatcher({}).register(handlers);
const ws = new Lark.WSClient({
  appId: config.lark.appId, appSecret: config.lark.appSecret, loggerLevel: Lark.LoggerLevel.info,
});

let shuttingDown = false;
async function shutdown(sig) {
  if (shuttingDown) return;
  shuttingDown = true;
  log(`\n收到 ${sig}，正在收尾…`);
  flushSeen();                                  // 把去重表落盘，重启后不会重复回话
  log(`本次统计：事件 ${counters.events} / 已回答 ${counters.handled} / 已发送 ${counters.replied} / 跳过 ${counters.skipped} / 失败 ${counters.failed} / 未捕获 ${counters.uncaught}`);
  try { await ws.stop?.(); } catch {}
  process.exit(0);
}
/* ─────────── 未捕获异常：计数 + 越线在群里自报（**不退出**） ─────────── */

/**
 * ★ 为什么这两条钩子不能只记日志。
 *
 * 原先它们只 `log(...)`。后果是：进程带着**未知状态**继续在群里答话，
 * 而 launchd **永远不会**重启它 —— `KeepAlive{SuccessfulExit:false}` 只在
 * **非零退出**时拉起，而这两条钩子恰恰不退出。
 * 于是「我已经处于未定义状态」这件事唯一痕迹是一行 stdout，
 * 而它**和「一切正常」长得一模一样**（与 §2.7 记的
 * 「`kill -TERM` → `exit 0` → 不拉起」是同一个后果面）。
 *
 * 处置选的是「继续服务，但让未知状态被看见」，而**不是**退出交给 launchd：
 * 若异常是确定性的（每次启动就抛），退出会变成**重启风暴**，
 * 而重启窗口里的群消息会被吃掉且事后补不回来 —— 正是 §2.7 要防的那件事。
 *
 * 窗口：同一分钟内累计到 `UNCAUGHT_REPORT_AT` 自报一次，之后每满一个窗口
 * 再自报一次（不是只报第一次）—— 一条持续报错既不刷屏，也不会报过一次就永远闭嘴。
 */
const UNCAUGHT_REPORT_AT = 3;
const UNCAUGHT_WINDOW_MS = 60_000;
let crashWindow = { start: 0, n: 0 };

function noteCrash(kind, e) {
  counters.uncaught++;
  log(`⚠ ${kind}:`, e?.stack ?? e?.message ?? e);

  const now = Date.now();
  if (now - crashWindow.start > UNCAUGHT_WINDOW_MS) crashWindow = { start: now, n: 0 };
  crashWindow.n++;

  if (crashWindow.n % UNCAUGHT_REPORT_AT === 0) void selfReportCrash(kind, crashWindow.n);
}

/**
 * 在群里自报「我这边内部出错了」。
 * 找不到可通报的群时**必须说清楚只进了日志** —— 不许沉默（§2.4.2：未测不许与通过长得一样）。
 */
async function selfReportCrash(kind, n) {
  try {
    const target = await resolveChat();
    if (!target) {
      log('   ⚠ 内部出错要自报，但还没有可通报的群 —— 只进日志（不许沉默）');
      return;
    }
    await safeSend(target,
      `⚠ 我这边内部出错了 ${n} 次（最近一次：${kind}），**可能答得不可靠**。\n`
      + '已经记录下来；接下来的回答请以我重新查证过的为准。');
    log(`   · 内部出错自报已发到 ${target}`);
  } catch (e) {
    log('   ⚠ 内部出错自报也失败了:', e?.message ?? e);
  }
}

process.on('SIGINT',  () => shutdown('Ctrl-C'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('unhandledRejection', (e) => noteCrash('unhandledRejection', e));
process.on('uncaughtException',  (e) => noteCrash('uncaughtException',  e));

await ws.start({ eventDispatcher: dispatcher });
log('✓ 长连接已启动，等待事件（断线由 SDK 自动重连）');

// 启动即核一次上游基线：重启后第一时间知道手上那份 PRD 是不是最新版
// （`--dump-only` 不跑 —— 那个模式是排查用，不该产生任何对外动作）
if (!DUMP_ONLY) void baselineWatch('startup');
// 启动也核一次待收清单：**到期这件事和基线一样，重启后才该被想起来**
if (!DUMP_ONLY) void pendingWatch('startup');

// 每 5 分钟打一次心跳，方便判断进程是活着还是卡死
const hb = setInterval(() => {
  log(`· 心跳 事件 ${counters.events} 已回答 ${counters.handled} 失败 ${counters.failed} 未捕获 ${counters.uncaught} | LLM 调用 ${status().llm.calls}`);
  rotateLogIfHuge();
  // 每日兜底：**她"基于评估重新修改"已经推过的那一篇时，群里不会有新链接** ——
  // 这正是「只在收到链接时跑」漏掉的那一种，也是她原话描述的那一种。
  if (!DUMP_ONLY && loadState().lastDay !== bjDate()) void baselineWatch('daily');
  // 待收清单同理换日兜底：到期日的比较对象就是「今天」，而今天只有换日时才会变。
  // ★ 读的是**待收那一份**状态文件（`prd-pending-watch.json`）—— 两个检查共写一份
  //   会互相覆盖：基线那次是「读 → 等网络 3 秒 → 写」，写回去的是旧快照。
  if (!DUMP_ONLY && loadPendingState().p_lastDay !== bjDate()) void pendingWatch('daily');
}, 5 * 60_000);
hb.unref?.();

/**
 * 日志自轮转。
 * 为什么必须做：launchd 把 stdout 无条件追加到 ws_daemon.log，不轮转的话
 * 这个文件会一直长，几个月后能把磁盘撑满 —— 而且出问题的时候正好是最需要日志的时候。
 * 只在超过阈值时切一次，保留上一份，不做复杂的分代。
 */
const SELF_LOG = process.env.SHOUHENG_SELF_LOG || path.join(LOG_DIR, 'ws_daemon.log');
const MAX_LOG_BYTES = 20 * 1024 * 1024;   // 20MB
let rotating = false;
function rotateLogIfHuge() {
  if (rotating) return;
  try {
    if (!fs.existsSync(SELF_LOG)) return;
    if (fs.statSync(SELF_LOG).size < MAX_LOG_BYTES) return;
    rotating = true;
    fs.renameSync(SELF_LOG, `${SELF_LOG}.1`);   // 旧的覆盖上一份 .1
    rotating = false;
  } catch { rotating = false; }
}

if (PROBE) {
  setTimeout(async () => {
    log('--probe 自检结束，退出。');
    const s = status();
    log('LLM 统计:', JSON.stringify(s.llm));
    await shutdown('probe 完成');
  }, 10_000);
}
