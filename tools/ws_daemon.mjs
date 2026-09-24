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

import { config, describeConfig, LOG_DIR, REPO_ROOT, ensureDir, stateDir } from './agent/config.mjs';
import * as feishu from './agent/feishu.mjs';
import { handleMessage, flushSeen, loadedTools, status } from './agent/agent.mjs';
import { toCardOrText } from './reply-cards/envelope.mjs';
import { shapeOf } from './reply-cards/registry.mjs';
import { checkNow, checkPending, resolveChat, LARK_DOC_RE, bjDate, loadState, loadPendingState, saveChatId,
         pickAlertTarget,
         recheckDue as baselineRecheckDue } from './agent/prd_baseline.mjs';
import * as outbound from './agent/outbound.mjs';
import * as retryQueue from './agent/retry_queue.mjs';
import { checkExternal, loadState as loadExternalState, recheckDue as externalRecheckDue } from './agent/external_watch.mjs';

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

/* ─────────── 运行状态（Q2 的 run-state 写方，2026-09-22 加） ───────────
 *
 * ★ 为什么要有这个文件。「守衡现在还在跑吗」原先只能靠在跑的进程上下文去猜：
 *   `ps -o etime=` 在受限环境被拒（`Operation not permitted`），而 launchd 的读数
 *   只说「在不在」，不说「活了多久、心跳还新不新鲜」。自证 E 段因此**恒退 2**。
 *   那不是环境限制，是**选型错误**：进程的生命周期归 launchd 管，而「它自己觉得怎么样」
 *   只有它自己写得出来。所以由守护进程自己写一份**可指得出对象**的读数。
 *
 * ★ 两份读数的分工（都不是孤证）：
 *   · `daemon-run.json` —— 它自己写的：`pid / startedAt / lastBeatAt / 计数`
 *   · launchd `state`+`pid` + `pgrep` + `os.kill(pid,0)` —— 外面看到的
 *   `judge_liveness` 把两边合起来判 `up`/`down`/`stuck`/`untested`（见 verify_shouheng_ops.py）。
 *
 * ★ 心跳过期（>12 分钟没刷新）是**「卡死」**，不是「没在跑」—— 两者要分开，
 *   因为处置不同：前者要重启，后者更要紧（已经在失联了）。
 *
 * ⚠️ 它是**覆盖写**的一份小文件，只有一个写者（本进程）。任何别的检查器都不许写它。
 */
const RUN_STATE_FILE = () => path.join(stateDir(), 'daemon-run.json');
const RUN_STARTED_AT = new Date();
let runStateWrites = 0, runStateFails = 0;

function writeRunState(note = null) {
  const body = {
    pid: process.pid,
    startedAt: RUN_STARTED_AT.toISOString(),
    startedAtBj: new Date(RUN_STARTED_AT.getTime() + 8 * 3600_000).toISOString().replace('Z', '+08:00'),
    startedAtEpoch: Math.floor(RUN_STARTED_AT.getTime() / 1000),
    lastBeatAt: new Date().toISOString(),
    uptimeSeconds: Math.floor((Date.now() - RUN_STARTED_AT.getTime()) / 1000),
    events: counters.events, handled: counters.handled, replied: counters.replied,
    skipped: counters.skipped, failed: counters.failed, uncaught: counters.uncaught,
    llmCalls: status().llm.calls,
    probe: PROBE, dumpOnly: DUMP_ONLY,
    note,
  };
  try {
    const file = RUN_STATE_FILE();
    ensureDir(path.dirname(file));
    const tmp = `${file}.tmp`;      // 先临时再 rename：读的人不会读到半个文件
    fs.writeFileSync(tmp, JSON.stringify(body, null, 2));
    fs.renameSync(tmp, file);
    runStateWrites++;
    return { ok: true };
  } catch (e) {
    runStateFails++;
    // 写不进去**要说出来**（但只在第一次与每 10 次说一次）：静默失败会让 E 段读到一份
    // 过期的 run-state，而它长得像「进程卡死了」。
    if (runStateFails === 1 || runStateFails % 10 === 0) log(`   ⚠ run-state 写不进去（第 ${runStateFails} 次）:`, e.message);
    return { ok: false, error: e.message };
  }
}

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

  // ★ **每条消息都记下「最近来过消息的群」**（2026-09-22 补）。
  //
  // 为什么必须有这一行：`resolveChat()`（主动告警往哪儿发）的语义是
  // 「优先用最近来过消息的那个群，取不到才问一次接口」。而原先 `saveChatId` 只在
  // **检查被触发时**才调（`baselineWatch` / `pendingWatch`），检查一天才跑一次 ——
  // 于是那句「最近来过消息的群」实际是「**最近一次触发检查时所在的群**」，
  // 可能已经是几天前的了，而不匹配时它会**静默回落到接口的第一个群**。
  // 一条主动告警发错群，说出口的话就收不回来（§2.4.2：对外说过的话优先）。
  // 记在这里才是那句话的字面意思，而且它自维护 —— 不依赖谁记得去调。
  saveChatId(chatId);

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
    await safeSend(chatId, `我处理这条消息时内部出错了，没能回答。\n\n错误：${e?.message ?? e}\n\n（已记录，这是我的问题。）`,
                   'error-fallback', msg.chat_type);
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
  if (result.meta?.compacted) {
    // ★ 2026-09-22 改：这块**原先无条件**说「+ 纪要」，而 `meta.summary` 就在手边
    //   （写出来之后**从来没有一个地方读过它** —— §2.4 那个病的又一个实例）。
    //   实测：三个会话的 `summary` 全是 0 长度，而日志里印了 8 次「保留 N 轮 + 纪要」。
    //   真相是压缩把旧对话**删掉了但什么都没留下**，而这句话让人以为留下了。
    //   现在按真实字符数分流：有纪要才说「+ 纪要」，没有就说清「纪要为空」。
    const sc = result.meta.summary_chars ?? 0;
    log(sc > 0
      ? `   🗜 历史已压缩（保留 ${result.meta.turns} 轮 + 纪要 ${sc} 字）`
      : `   🗜 历史已压缩（保留 ${result.meta.turns} 轮）⚠️ 纪要为空 —— `
        + '旧对话已删且未留下摘要，这是故障不是省事，见 PMO/logs');
  }
  if (result.meta?.truncated) log('   ⚠️ 回复被长度上限截断（已附截断说明，不是完整回答）');
  if (result.meta?.outbound?.folded) log(`   ↩ 本轮补记外发 ${result.meta.outbound.folded} 条进会话记忆`);
  if (result.meta?.outbound?.untested) log(`   ⚠️ 补记外发未测：${result.meta.outbound.untested}`);

  // ── 答不上 → 入补发队列（Q1-1d）。
  // 「断在哪一层」由 `llm.mjs` 的 `describeError` 给（`meta.llm.layer`），
  // 这里只负责把它连同「哪条消息、哪个群、问的什么」记下来。
  // **只对可重试类失败入队**：HTTP 4xx（鉴权/参数/配额）补发 5 次也是白试。
  //
  // ★ 两种失败都要入队（2026-09-22 补第二种）：
  //   `llm_error`      —— 模型这一拍没调通；
  //   `tool_exhausted` —— 调通了但工具循环跑满、始终没给出最终答复（走兜底话术）。
  //   第二种原先不入队（`reason` 是 `'ok'`，因为它有 `reply`），于是她连问两次
  //   都只收到兜底话术，而**盘上没有任何东西记得她欠一条回答**。
  if (result.reason === 'llm_error' || result.reason === 'tool_exhausted') {
    const m = result.meta?.llm ?? {};
    const item = retryQueue.itemFromEvent(data, { error: result.reply?.slice(0, 200), layer: m.layer });
    if (!item) log('   ⚠ 失败入队未测：事件里抽不出 message_id/chat_id');
    else {
      // 工具跑满**不是**网络问题：`retryable` 只对 `llm_error` 才由层决定。
      // 兜底话术那次补发值不值得？值得 —— 补发是**换一条路重跑**（`answer` 会重跑内核），
      // 而工具循环是个随机过程：同一句话两次跑满不代表第三次也跑满。
      const retryable = result.reason === 'tool_exhausted' ? true : m.retryable === true;
      const enq = retryQueue.enqueue({ ...item, retryable });
      log(`   ↻ ${result.reason === 'tool_exhausted'
              ? `工具循环跑满（${result.meta?.toolTrace?.length ?? 0} 次调用）`
              : `模型失败（层=${m.layer ?? '未知'}）`}，可重试=${retryable} → `
          + (enq.ok ? `已入补发队列（${enq.size} 条）` : `未入队：${enq.why}`));
    }
  }

  // ── 形态决策**不在这里**。（2026-09-22 改）
  // 原先这一块是 `const shaped = toCardOrText(result.reply)`，然后只把 `shaped.card`
  // 传进 `replyTo` —— 于是「谁能定形态」有两个答案：`AGENTS.md` §2.5 说只在 `replyTo`，
  // 代码却在 `onMessage`。**两处都能定形态，错位的表现是群里格式随机**，
  // 而这正是 §2.5 存在的理由。现在这里只把模型的原文交下去，由 `replyTo` 一处决定。
  log(`   💬 回复 ${result.reply.length} 字，耗时 ${ms}ms`);

  const sent = await replyTo(chatId, msg.message_id, result.reply, msg.chat_type);
  if (sent.ok) { counters.replied++; log(`   ✓ 已发送 ${sent.messageIds.filter(Boolean).join(', ')} [${sent.mode}]`); }
  else { counters.failed++; log(`   ✗ 发送失败: ${sent.error}`); }
}

/**
 * 补发队列（Q1-1d）：**答不上，不再等于永远答不上。**
 *
 * 判据与幂等全在 `agent/retry_queue.mjs`（三重：队列键 / 台账已答 / 记忆已答），
 * 这里只做两件它做不了的事：
 *   · `answer` —— **重跑内核**（补发的是答案本身，不是一句预先写好的话）；
 *   · `send`  —— 真发出去，且**只走 `replyTo`**（形态决策一处做，§2.5；
 *                发送者仍是本文件 —— `verify_outbound.py` 那张「谁能发消息」的总表不用加行）。
 *
 * 两条纪律：
 *   · **每拍最多补一条** —— 补发那一步本身就是一次模型调用，网络刚好时几条一起补
 *     是三倍花费，而它们已经等了十几分钟，再等 5 分钟不改变什么；
 *   · **失败绝不往群里灌第二条** —— 补发失败只累加次数，到上限落死信、只在日志说。
 */
let retryBusy = false;
async function retryWatch(reason) {
  if (retryBusy) { log('   · 补发跳过（上一拍还在跑）'); return; }
  retryBusy = true;
  try {
    const r = await retryQueue.runTick({
      log,
      answer: (it) => handleMessage(it.event, { force: true }),
      send: (it, text) => replyTo(it.chat_id, it.message_id, text, it.chat_type, 'resend'),
    });
    if (r.acted) {
      log(`   · 补发[${reason}] ${r.sent ? '✓ 已补发' : `未发出（${r.why ?? '仍需等待'}）`}，队列剩 ${r.left} 条`);
    }
  } catch (e) {
    log('   ⚠ 补发自身出错（不影响回话）:', e?.message ?? e);
  } finally { retryBusy = false; }
}

/**
 * 外部标准库（62 条引文）的上游漂移：**触发 + 通报**（`agent/external_watch.mjs` 是判据）。
 *
 * 为什么要有它：`verify_external.py` 早就能回答「那 62 条在上游还逐字对得上吗」，
 * 也有归档、清单和漂移段 —— **缺的是「谁在跑」**。PRD 那篇改了有人会知道，
 * FDA / Amazon / Meta 的政策页改了，此前**我们不会知道**，而这 62 条是要给法务当依据的。
 * 这是 `AGENTS.md` §2.4.2 那个病的最后一个实例。
 *
 * 与 `baselineWatch` 同两条纪律：不阻塞回话（调用点是 `void`）、**未测不得沉默**。
 * ⚠️ 它**会动盘**（真抓 + 写证据层 + append 清单），所以带 3 小时冷却 —— 重启不重抓。
 */
async function externalWatch(reason, chatId) {
  try {
    if (chatId) saveChatId(chatId);
    const r = await checkExternal({ reason });
    if (r.skipped) { log(`   · 外部标准库检查跳过（${r.skipped}）`); return; }
    log(`   · 外部标准库[${reason}] 退出码 ${r.code} · ${r.verdict} —— ${r.why}`
        + (r.note ? ` · ${r.note}` : ''));
    if (!r.say) return;
    const target = chatId ?? await resolveChat();
    if (!target) {
      log('   ⚠ 外部标准库有话说，但还没有可通报的群 —— 只进日志（退 2 不许沉默）');
      return;
    }
    await safeSend(target, r.say, 'proactive-external');
    log(`   · 外部标准库告警已发到 ${target}`);
  } catch (e) {
    log('   ⚠ 外部标准库检查自身出错（不影响回话）:', e?.message ?? e);
  }
}

/**
 * 把**被拦下没发出去**的原文落到 `PMO/logs/dropped/`。
 *
 * 存在理由只有一条：拒答话术对用户说「原始内容留在 PMO/logs」——
 * 这句话必须是真的。见 `replyTo` 里那段注释。
 *
 * 落盘配方按 `AGENTS.md` §2.1：**用 Node 写**（不是 Python），所以不会进
 * 「stat 比真实内容多 4096 字节」的填充态；`.md` / `.sh` 那两格才需要 `depad` 往返，
 * 这里写的是 `.txt`，本就在安全格内。
 *
 * 失败**不许**影响回话：写不进去就只记日志（已经没发出去的东西，不能再拖垮发送）。
 */
function dumpDropped({ messageId, chatId, source, reason, raw }) {
  try {
    const dir = path.join(LOG_DIR, 'dropped');
    ensureDir(dir);
    const at = new Date().toISOString();
    const name = `${at.replace(/[:.]/g, '-')}-${String(messageId ?? 'nomsg').replace(/[^\w-]/g, '')}.txt`;
    fs.writeFileSync(path.join(dir, name),
      `# 被拦下没发出去的原文\n`
      + `at: ${at}\nmessage_id: ${messageId ?? '(无)'}\nchat_id: ${chatId ?? '(无)'}\n`
      + `source: ${source ?? '(无)'}\n原因: ${reason ?? '(无)'}\n`
      + `${'─'.repeat(60)}\n${raw ?? ''}\n`);
    log(`   📥 原文已留证：PMO/logs/dropped/${name}（${[...String(raw ?? '')].length} 字）`);
  } catch (e) {
    log(`   ⚠ 原文留证失败（不影响回话）：${e?.message ?? e}`);
  }
}

/**
 * 发送一条回复。这是**唯一**的格式决策点 —— 也是**唯一**的形态决策点。
 *
 * ★ 形态决策（卡 vs 纯文本）在这里做，参数收的是**模型的原文**，不是已经定好形态的结果。
 *   `AGENTS.md` §2.5：「这个判断只允许在 `replyTo` 里做」。2026-09-22 之前它其实在
 *   `onMessage` 里（`toCardOrText` 在那边调），`replyTo` 只收 `card` —— 两处都碰形态。
 *   现在 `onMessage` 只记一行日志，形态的输入与输出都收在本函数内。
 *   「模型选了哪种形态、有没有被搬迁、有没有踩到 AI 味」仍然全部进日志 ——
 *   否则调模版就只能靠重跑猜。
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
async function replyTo(chatId, messageId, rawReply, chatType = null, source = 'reply') {
  const shaped = toCardOrText(rawReply);
  for (const m of shaped.moved) log(`   ↪ ${m.field} → ${m.to}（${m.why}）`);
  for (const h of shaped.lint) log(`   ${h.level === 'error' ? '❌' : '⚠️ '} 语域 ${h.id} ×${h.count} ${h.sample}`);
  if (shaped.mode === 'card') log(`   🃏 卡片 ${shaped.kind} · ${shapeOf(shaped.card)}`);
  else if (shaped.dropped) log(`   ⚠️ 卡片降级为文本：${shaped.reason}`);

  // ★ 被拦下的原文落盘（2026-09-22 加）。
  //   为什么必须有这一步：拒答话术里写着「**原始内容留在 PMO/logs**」，
  //   而那句话说出去的时候，**盘上什么都没有** —— 实测 16:34 那次，
  //   `PMO/logs/` 里没有任何新文件，那句话是一句假承诺（§2.4.2 的形状：
  //   承诺里出现的每个名词都要指得出哪一行在做它）。
  //   现在它有了执行点：本条分支就是那一行。原文还留在会话记忆里，但记忆会被压缩，
  //   日志会轮转，只有这里的落盘是「按事故留证」的。
  //   `verify_cards.mjs` 的 **L7** 断言这一步真的接在 `dropped` 分支上。
  if (shaped.dropped) dumpDropped({ messageId, chatId, source, reason: shaped.reason, raw: rawReply });

  const text = shaped.text;
  const card = shaped.card ?? null;

  // ★ 2026-09-22 改成「先把结果收进 `sent`、出口只有一个」。
  //   原先每个分支各自 `return`，于是**留痕要写在四个地方**，漏一处就是一条消息
  //   在台账里查不到 —— 而漏掉的那一处不会有任何东西变红。
  //   现在无论走哪条降级链，出口只有一个，`recordOutbound` 只可能被调一次、
  //   也不可能被跳过（`verify_outbound.py` 的 F 段扫这一段的结构）。
  let sent;
  if (card) {
    const rc = await feishu.replyCard(messageId, card);
    if (rc.ok) {
      sent = { ok: true, messageIds: [rc.messageId], mode: rc.mode };
    } else {
      log(`   ⚠ 卡片 reply 失败（${rc.error}），退成同一条引用里的纯文本`);
      const rt = await feishu.replyMarkdown(messageId, chatId, text);
      sent = rt.ok ? { ...rt, mode: `card-failed→${rt.mode}`, error: rc.error } : rt;
    }
  } else {
    const r = await feishu.replyMarkdown(messageId, chatId, text);
    if (r.ok) {
      sent = r;
    } else {
      log(`   ⚠ reply 失败（${r.error}），改为直接发送`);
      sent = await feishu.sendMarkdown(chatId, text);
    }
  }

  // 留痕。**发失败也记**（`ok:false`）—— 台账要能回答「我们试过没有」，
  // 而不只是「成功过没有」；折进会话记忆的那一步会跳过 `ok:false`（见 outbound.mjs）。
  //
  // ★ `source`（2026-09-22 加）默认 `reply`，补发那一路传 `resend`。为什么必须有这个参数：
  //   「谁答的」在台账里要分得出来 —— `resend` 是**晚十几分钟的补答**，它还要参与
  //   补发队列的三重幂等（`retry_queue.mjs` 的 ②）。两种来源在折记忆时都不折
  //   （见 outbound.mjs 的 `NON_FOLDING`），但它们在台账里必须长得不一样。
  recordOutbound(chatId, sent, { text, source, replyTo: messageId, chatType });
  return sent;
}

/**
 * 主动发送（不属于「回答某一条」的那些话）：基线告警、待收到期提醒、崩溃自报、
 * 进群自我介绍、出错兜底。
 *
 * @param {string} source  这条外发的**性质**，封闭集合见 `agent/outbound.mjs` 的 `SOURCES`。
 *                         刻意**不给默认值** —— 少传一个参数会记成 `unknown:`，
 *                         那在台账里看得见；给个默认值则会静默记成别的东西。
 */
async function safeSend(chatId, text, source, chatType = null) {
  try {
    const sent = await feishu.sendMarkdown(chatId, text);
    recordOutbound(chatId, sent, { text, source, chatType });
  } catch (e) { log('   ✗ 兜底发送也失败:', e.message); }
}

/**
 * 记一条外发到台账（`PMO/logs/ws_outbound.jsonl`，判据在 `agent/outbound.mjs`）。
 *
 * ★ 为什么这件事必须做，而且必须在这里做：
 *   2026-09-22 14:39 那次误答的直接成因之一，是**守衡不记得自己问过什么** ——
 *   而它 14:37:55 问的那一句，是 `send_once.mjs` 手发的，**盘上没有任何痕迹**
 *   （只有 stdout 里一个 `message_id`，以及我事后手抄进文档的时刻）。
 *   于是「她答的是哪一句」在盘上根本无从判起。
 *
 * ★ 台账写不进去**不许影响发送**（与 `dumpRaw` 同一条纪律：日志坏掉不该让服务坏掉），
 *   但也不许静默 —— 它一定要在日志里留一行，因为那意味着**这条消息在台账里查不到**。
 */
function recordOutbound(chatId, sent, { text, source, replyTo = null, chatType = null }) {
  const ids = sent?.messageIds ?? (sent?.messageId ? [sent.messageId] : []);
  const r = outbound.recordSend({
    chatId, chatType, messageIds: ids, text, source,
    mode: sent?.mode ?? null, replyTo,
    ok: sent?.ok !== false, error: sent?.error ?? null,
  });
  if (!r.ok) log(`   ⚠ 外发留痕失败（${r.error}）—— 这条消息在台账里查不到`);
  return r;
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
    // ★ `saveChatId`，不是 `saveState({ ...loadState(), lastChatId })` —— 后者有两个毛病：
    //   ① `saveState` 默认写的是**基线那份状态文件**，而这里连待收那条链路也走同一个调用，
    //      于是「待收」在写「基线」的文件，还靠 `{ ...loadState() }` 把陈年 `p_*` 键一路带下去；
    //   ② 它住在基线检查的 read→跑子进程（最长 90 秒）→write 窗口里，会被旧快照抹掉。
    if (chatId) saveChatId(chatId);
    /**
     * ★ **目标群在跑检查之前就定下来，并作为 `chatId` 传进状态机。**（2026-09-22 加）
     *
     * 原先的顺序是「先跑检查、之后才 `chatId ?? await resolveChat()`」，于是：
     *   · `[link]` 触发的告警发到**链接所在的那个群**；
     *   · 几十分钟后的收尾走 `resolveChat()`，而它读的是「**最近来过消息的群**」——
     *     这中间群里正常问答过，那个值早就翻页了。
     * 实测后果就是两个群各收到一半：`oc_49a7…` 收到「请给我一分钟重拉一次基线」却
     * **永远收不到收尾**；`oc_7775…` 从没收到过告警，却收到一句「✅ 恢复了」。
     * 详见 `prd_baseline.mjs` 里 `alertChat` 那段。
     *
     * 现在把「这次要说给哪个群」在**说话之前**定下来，让状态机把它连同「说过什么」一起记住；
     * 收尾时状态机用 `sayTo` 把地址还回来，优先级高于 `target` **也高于** `resolveChat()`。
     */
    const target = chatId ?? await resolveChat();
    const r = await checkNow({ reason, chatId: target });
    if (r.skipped) { log(`   · 基线检查跳过（${r.skipped}）`); return; }
    log(`   · 基线检查[${reason}] 退出码 ${r.code} —— ${r.why}${r.note ? ` · ${r.note}` : ''}`);
    if (!r.say) return;
    // ★ `sayTo` ＝「当初那条告警去过哪个群」。即使 `target` 取不到，收尾也回得去。
    // ★ 优先级只在 `pickAlertTarget` 里判一次（收尾地址 > 触发群 > 默认群）。
    const to = pickAlertTarget({ sayTo: r.sayTo, triggerChat: target });
    if (!to) {
      log('   ⚠ 基线检查有话要说，但还没有可通报的群 —— 只进日志（退 2 不许沉默）');
      return;
    }
    await safeSend(to, r.say, 'proactive-baseline');
    log(`   · 基线告警已发到 ${to}${r.sayTo ? '（收尾 —— 回到当初告警的那个群）' : ''}`);
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
    if (chatId) saveChatId(chatId);   // 理由同 `baselineWatch`：这里原先写的是**基线**那份状态文件
    // ★ 目标群先定、后跑检查 —— 与 `baselineWatch` 同一个理由（见那里那段）。
    //   这条今天是「将来时」：到期提醒的首次触发在 2026-10-02，而收尾若发到另一个群，
    //   那边的人会看到一句「现在没有到期未收」而不知道在说什么。同一个形状，一次修两处。
    const target = chatId ?? await resolveChat();
    const r = await checkPending({ reason, chatId: target });
    if (r.skipped) { log(`   · 待收检查跳过（${r.skipped}）`); return; }
    log(`   · 待收检查[${reason}] 退出码 ${r.code} —— ${r.why}${r.note ? ` · ${r.note}` : ''}`);
    if (!r.say) return;
    const to = pickAlertTarget({ sayTo: r.sayTo, triggerChat: target });
    if (!to) {
      log('   ⚠ 待收检查有话要说，但还没有可通报的群 —— 只进日志（退 2 不许沉默）');
      return;
    }
    await safeSend(to, r.say, 'proactive-pending');
    log(`   · 待收到期提醒已发到 ${to}${r.sayTo ? '（收尾 —— 回到当初告警的那个群）' : ''}`);
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
      `@我 就能叫我。不 @ 我不会插话。`, 'greeting', 'group');
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
      + '已经记录下来；接下来的回答请以我重新查证过的为准。', 'error-fallback');
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
// 外部标准库（62 条）同样在启动时核一次 —— 它带 3 小时冷却，重启不会变成抓取风暴。
// **不传 chatId**：它不知道是哪个群把它叫起来的，往「最近来过消息的群」发才不唐突。
if (!DUMP_ONLY) void externalWatch('startup');
// ★ run-state 第一次落盘**必须在 `ws.start()` 之后**：这份读数的语义是
//   「长连接起来了、我开始接事件了」，写在启动之前会把「正在连」报成「已在跑」。
writeRunState('startup');

// 每 5 分钟打一次心跳，方便判断进程是活着还是卡死
const hb = setInterval(() => {
  log(`· 心跳 事件 ${counters.events} 已回答 ${counters.handled} 失败 ${counters.failed} 未捕获 ${counters.uncaught} | LLM 调用 ${status().llm.calls}`);
  writeRunState();                       // Q2：心跳刷新 lastBeatAt（E1d 靠新鲜度判「卡死」）
  rotateLogIfHuge();
  // 每日兜底：**她"基于评估重新修改"已经推过的那一篇时，群里不会有新链接** ——
  // 这正是「只在收到链接时跑」漏掉的那一种，也是她原话描述的那一种。
  if (!DUMP_ONLY && loadState().lastDay !== bjDate()) void baselineWatch('daily');
  // 待收清单同理换日兜底：到期日的比较对象就是「今天」，而今天只有换日时才会变。
  // ★ 读的是**待收那一份**状态文件（`prd-pending-watch.json`）—— 两个检查共写一份
  //   会互相覆盖：基线那次是「读 → 等网络 3 秒 → 写」，写回去的是旧快照。
  if (!DUMP_ONLY && loadPendingState().p_lastDay !== bjDate()) void pendingWatch('daily');
  // ★ 外部标准库换日兜底（Q4-4d）：**状态文件必须独立**（`external-watch.json`，第三份）。
  //   上游会不会在我们不看的时刻改 —— 这一层把发现窗口缩到 1 天，缩不到 0；
  //   边界写在状态里（`lastRunAt`），不是写在谁脑子里。
  if (!DUMP_ONLY && loadExternalState().lastDay !== bjDate()) void externalWatch('daily');
  /**
   * ── ★ 被跳过的那次检查，冷却一过就补回来（2026-09-22 加，`…误答登记…` §十三）──────
   *
   * 上面那三个 `daily` 兜底只解决「换日」，**不解决「跳过」**：
   * `checkNow` / `checkExternal` 在冷却期内的行为是 `return { skipped }`，
   * 而**冷却是「跳过」，不是「重排」** —— 原先没有任何一行在冷却过期后补跑。
   *
   * 实测代价（§十三 13.3）：一次落在冷却窗口里的重启，让基线检查被推到换日，
   * 漂移发现窗口从 30 分钟被撑到约 24 小时；更要紧的是这期间状态文件一直写着
   * `lastState: "drift"`，**而基线其实早已转绿** —— 一个会过期的读数，
   * 没有任何东西在它过期时变红。
   *
   * ★ 判据不在这一行：`recheckDue()` 是两处各自的**纯函数**（`prd_baseline.mjs` /
   *   `external_watch.mjs`），各有正反两条断言。这一行只回答「谁在跑它」——
   *   `AGENTS.md` §2.4.2 那两层，缺一层都不算兑现。
   *
   * ★ **它不会变成轮询**：`recheckDue` 的第一条就是「没有 `staleSince` 就返回 null」，
   *   而 `staleSince` **只在真的跳过过一次时才被写下**、真跑一次就清空。
   *   所以这一行的触发条件是「本次进程里确实欠了一次检查，且现在允许补了」 ——
   *   不是「距离上次检查过了多久」。（反面对照见两处 `--selftest`。）
   */
  if (!DUMP_ONLY) {
    const due = baselineRecheckDue(loadState());
    if (due) { log(`   ↻ 基线检查补跑（${due}）`); void baselineWatch('deferred'); }
    const edue = externalRecheckDue(loadExternalState());
    if (edue) { log(`   ↻ 外部标准库补跑（${edue}）`); void externalWatch('deferred'); }
  }
  // ★ 补发队列每拍一次（Q1-1d）：「网络恢复了没有」不用另做探针 ——
  //   补发那一次尝试本身就是探针（计划 §1.5）。队列空时它立刻返回，零成本。
  if (!DUMP_ONLY) void retryWatch('tick');
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
