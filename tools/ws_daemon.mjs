#!/usr/bin/env node
/**
 * ws_daemon.mjs —— 守衡 · 常驻入口（v3：接入推理内核）
 *
 * 本文件只做四件事：建立长连接、把事件交给内核、把回复发出去、管理生命周期。
 * 所有「怎么想」的逻辑都在 agent/ 目录下，不在这里。
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

const counters = { events: 0, handled: 0, replied: 0, skipped: 0, failed: 0 };

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
  log(`   💬 回复 ${result.reply.length} 字，耗时 ${ms}ms`);

  const sent = await replyTo(chatId, msg.message_id, result.reply);
  if (sent.ok) { counters.replied++; log(`   ✓ 已发送 ${sent.messageIds.filter(Boolean).join(', ')} [${sent.mode}]`); }
  else { counters.failed++; log(`   ✗ 发送失败: ${sent.error}`); }
}

/** 回复失败时退化为普通发送；再失败就只记日志，不静默吞掉 */
async function replyTo(chatId, messageId, text) {
  const r = await feishu.replyMarkdown(messageId, chatId, text);
  if (r.ok) return r;
  log(`   ⚠ reply 失败（${r.error}），改为直接发送`);
  return feishu.sendMarkdown(chatId, text);
}

async function safeSend(chatId, text) {
  try { await feishu.sendMarkdown(chatId, text); } catch (e) { log('   ✗ 兜底发送也失败:', e.message); }
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
  log(`本次统计：事件 ${counters.events} / 已回答 ${counters.handled} / 已发送 ${counters.replied} / 跳过 ${counters.skipped} / 失败 ${counters.failed}`);
  try { await ws.stop?.(); } catch {}
  process.exit(0);
}
process.on('SIGINT',  () => shutdown('Ctrl-C'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('unhandledRejection', (e) => log('⚠ unhandledRejection:', e?.stack ?? e?.message ?? e));
process.on('uncaughtException',  (e) => log('⚠ uncaughtException:',  e?.stack ?? e?.message ?? e));

await ws.start({ eventDispatcher: dispatcher });
log('✓ 长连接已启动，等待事件（断线由 SDK 自动重连）');

// 每 5 分钟打一次心跳，方便判断进程是活着还是卡死
const hb = setInterval(() => {
  log(`· 心跳 事件 ${counters.events} 已回答 ${counters.handled} 失败 ${counters.failed} | LLM 调用 ${status().llm.calls}`);
  rotateLogIfHuge();
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
