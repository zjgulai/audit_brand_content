/**
 * agent.mjs —— 守衡的推理内核（消息进来 → 想 → 用工具 → 出话）
 *
 * 处理一条消息的完整链路：
 *   去重 → 解析 mention → 装上下文 → 载记忆 → 工具循环 → 存记忆（必要时压缩）→ 返回回复
 *
 * 三个容易被忽略但必须做对的地方：
 *   1. 同一会话串行：群里两条消息几乎同时到达时，并发写同一个记忆文件会互相覆盖。
 *   2. 已处理消息去重：长连接重连后服务端可能重推，不做去重会重复回话。
 *   3. 工具循环有上限：模型可能反复调同一个工具，必须有硬闸。
 */
import fs from 'node:fs';
import path from 'node:path';
import { config, stateDir } from './config.mjs';
import { buildSystemPrompt } from './persona.mjs';
import * as llm from './llm.mjs';
import * as mem from './memory.mjs';
import * as feishu from './feishu.mjs';
import { TOOL_SCHEMAS, executeTool, runtimeContext, toolNames } from './tools.mjs';
import { detectTruncation, annotateTruncation, tailOf } from './truncate.mjs';

/* ─────────────────── 去重：见过的事件不再处理 ─────────────────── */
// 惰性求值：测试需要把状态目录指到不可写路径来验证失败分支，
// 写成模块常量就再也改不动了（且失效是静默的）。
const seenFile = () => path.join(stateDir(), 'seen-messages.json');
const SEEN_MAX = 500;

function loadSeen() {
  try { return new Set(JSON.parse(fs.readFileSync(seenFile(), 'utf8'))); } catch { return new Set(); }
}
let seen = loadSeen();
let seenDirty = false;
let seenFlushFailed = 0;   // 连续落盘失败次数，用于「只报第一次、恢复时报一次」

export function alreadyHandled(messageId) {
  if (!messageId) return false;
  if (seen.has(messageId)) return true;
  seen.add(messageId);
  seenDirty = true;
  if (seen.size > SEEN_MAX) {                       // 只保留最近的，避免文件无限增长
    const arr = [...seen].slice(-SEEN_MAX);
    seen = new Set(arr);
  }
  return false;
}
export function flushSeen() {
  if (!seenDirty) return;
  try {
    // 写入点自己保证父目录存在：配置加载时的那次 mkdir 是「尽力而为」，
    // 目录若在运行中被删掉，这里补建，而不是让每次落盘都失败。
    fs.mkdirSync(path.dirname(seenFile()), { recursive: true });
    fs.writeFileSync(seenFile(), JSON.stringify([...seen]));
    seenDirty = false;
    if (seenFlushFailed) {            // 恢复后报一次，避免故障期间刷屏
      console.warn(`[seen] 去重表恢复落盘（曾在 ${seenFlushFailed} 次写入失败后成功）`);
      seenFlushFailed = 0;
    }
  } catch (e) {
    // 重要：失败时不能清 seenDirty。
    // 清了就再也不会重写，而这个表决定「重启后是否重复回话」——
    // 它一旦静默丢失，表现是守衡对着同一条消息回两次，且没有任何线索。
    seenFlushFailed++;
    if (seenFlushFailed === 1) {
      console.warn(`[seen] 去重表落盘失败（第 1 次）：${e.code ?? e.message} —— 本次运行仍按内存去重，但重启后可能重复回话`);
    }
  }
}

/* ─────────────────── 串行化：每个会话一把锁 ─────────────────── */
const locks = new Map();
/** 同一 sessionKey 上排队执行，保证记忆文件不会被并发覆盖 */
function withLock(key, fn) {
  const prev = locks.get(key) ?? Promise.resolve();
  const next = prev.then(fn, fn);                   // 前一个失败也要继续排队
  locks.set(key, next.catch(() => {}));
  return next;
}

/* ─────────────────── 主处理函数 ─────────────────── */

/**
 * 处理一条飞书消息，返回要发出的回复文本（不负责发送）。
 * @param {object} event  im.message.receive_v1 的 data
 * @returns {Promise<{reply:string|null, reason?:string, sessionKey?:string, meta?:object}>}
 */
export async function handleMessage(event) {
  const msg     = event?.message ?? {};
  const sender  = event?.sender ?? {};
  const chatId  = msg.chat_id;
  const chatType = msg.chat_type;                    // 'group' | 'p2p'
  const senderOpenId = sender?.sender_id?.open_id ?? sender?.sender_id?.user_id ?? '';

  // ── 1. 去重必须**最先**做。
  // 放在类型判断之后是错的：非文本消息（图片/文件）会绕过去重，
  // 服务端重推同一条时会重复回话，用户看到守衡对同一张图说两遍「我读不了」。
  if (alreadyHandled(msg.message_id)) {
    return { reply: null, reason: 'duplicate', meta: { message_id: msg.message_id } };
  }

  // ── 2. 只处理文本。附件类明确说「按规矩不取」，不装懂、也**不把规矩说成能力**。
  //
  // 依据 AGENTS.md §2.6 红线：飞书上的内容禁止下载。
  // 这里曾经写的是「我现在只能读文本消息 …… 我看不到里面的内容」——
  // 那句话把**策略**说成了**能力/权限**问题：对方会以为还差一个开关没打开，
  // 于是去申请权限、去找文件主人。全是白跑。规矩就该照直说，并给出走得通的路。
  if (msg.message_type !== 'text') {
    const ATTACHMENT_TYPES = new Set(['file', 'image', 'media', 'audio']);
    if (ATTACHMENT_TYPES.has(msg.message_type)) {
      return { reply: '附件我不取 —— 飞书上的内容公司不让下载，附件只有下载这一条通道。\n'
                    + '要审的话，把里面的文字贴过来；或者存成飞书云文档发我，云文档我能直接读。',
               reason: 'attachment_not_taken', meta: { message_type: msg.message_type } };
    }
    return { reply: `这条是「${msg.message_type}」，它的正文我读不了 —— 需要的话请把它转成文字发我。`,
             reason: 'unsupported_type', meta: { message_type: msg.message_type } };
  }

  // ── 3. 解析正文与 mention
  let rawText = '';
  try { rawText = JSON.parse(msg.content ?? '{}').text ?? ''; } catch {}
  const { display, mentions } = feishu.resolveMentions(rawText, msg.mentions);
  const botMentioned = feishu.isBotMentioned(mentions);
  const question = botMentioned ? feishu.stripBotMention(display, mentions) : display.trim();

  // ── 4. 群聊里「不 @ 不理」，避免刷屏；私聊一律响应
  if (chatType === 'group' && config.requireMentionInGroup && !botMentioned) {
    return { reply: null, reason: 'not_mentioned' };
  }
  if (config.allowedChats.length && !config.allowedChats.includes(chatId)) {
    return { reply: null, reason: 'chat_not_allowed', meta: { chatId } };
  }

  // 已知名字的三条来源，按可信度与代价排序：
  //   1) 消息 mentions 里带的名字（零成本，但只覆盖「被 @ 的人」）
  //   2) 群成员列表（已有权限，覆盖同群所有人）
  //   3) 通讯录单查（需额外权限，未开通则失败）
  let senderName = mentions.find((m) => m.openId === senderOpenId)?.name || null;
  let senderNameSource = senderName ? 'mention' : null;
  let senderNameReason = null;
  if (!senderName && senderOpenId) {
    const looked = await feishu.getUserName(senderOpenId, chatId);
    senderName = looked.name;
    senderNameSource = looked.source;
    if (!senderName) {
      // 查不到就如实告诉模型，别让它编一个称呼
      senderName = '(未知名)';
      senderNameSource = 'unresolved';
      senderNameReason = looked.reason;
    }
  }
  const senderNameKnown = senderNameSource !== 'unresolved';

  // ── 5. 会话与记忆
  const key = mem.sessionKey({ chatId, chatType, senderOpenId });
  return withLock(key, async () => {
    const sess = mem.load(key);
    if (!sess.title && chatType === 'group') {
      const info = await feishu.getChatInfo(chatId);
      mem.setTitle(sess, info?.name ?? null);
    } else if (!sess.title && chatType === 'p2p') {
      mem.setTitle(sess, `${senderName} 的私聊`);
    }

    // 注入运行期上下文，工具据此知道「现在在哪、跟谁说话」
    // senderNameKnown=false 时，senderName 是「(未知名)」占位符而非真名，
    // 一并告知模型，避免它把这个占位符当成真名去称呼对方。
    Object.assign(runtimeContext, {
      chatId, chatType, senderName, senderOpenId, messageId: msg.message_id,
      senderNameKnown,
      ...(senderNameKnown ? {} : { senderNameUnavailableReason: senderNameReason }),
    });

    const userTurn = chatType === 'group' ? `【${senderName}】${question}` : question;
    mem.append(sess, { role: 'user', content: userTurn, name: senderName });

    // ── 6. 工具循环
    const systemPrompt = buildSystemPrompt(
      chatType === 'group'
        ? `\n# 当前场景\n你在群聊「${sess.title ?? chatId}」里，正在回复 ${senderName}。群里其他人也会看到你的回答，所以不要输出私密信息，也不要假设只有一个人在听。`
        : `\n# 当前场景\n你在与 ${senderName} 私聊。`
    );

    const toolTrace = [];
    let reply = null;
    let llmError = null;
    let truncated = false;

    for (let iter = 0; iter < config.llm.maxToolIters; iter++) {
      const messages = mem.toLlmMessages(sess, systemPrompt);
      const r = await llm.chat(messages, { tools: TOOL_SCHEMAS });

      if (!r.ok) { llmError = r.error; break; }

      const m = r.message ?? {};
      const toolCalls = m.tool_calls ?? [];

      if (toolCalls.length === 0) {
        reply = (m.content ?? '').trim();

        // 截断检查：拿到 finishReason 却不用，半句话就会被当成完整回答发出去。
        // 真实事故：779 字回复停在「…里「未做」，日志却记「✓ 已发送」。
        const cut = detectTruncation({ finishReason: r.finishReason, text: reply });
        if (cut.cut) {
          const reasoning = r.usage?.completion_tokens_details?.reasoning_tokens ?? null;
          console.warn(
            `[agent] ⚠️ 回复被截断：${cut.reason}` +
            `｜正文 ${reply.length} 字｜reasoning ${reasoning ?? '?'} tok` +
            `｜结尾「${tailOf(reply)}」`
          );
          reply = annotateTruncation(reply, { reason: cut.reason });
          truncated = true;
        }

        mem.append(sess, { role: 'assistant', content: reply });
        break;
      }

      // 有工具调用：把 assistant 的 tool_calls 存进历史，再逐个执行
      mem.append(sess, { role: 'assistant', content: m.content ?? '', tool_calls: toolCalls });

      for (const tc of toolCalls) {
        const name = tc.function?.name;
        const t0 = Date.now();
        const out = await executeTool(name, tc.function?.arguments);
        toolTrace.push({ tool: name, ok: out.ok, ms: Date.now() - t0,
                         args: String(tc.function?.arguments ?? '').slice(0, 300),
                         error: out.ok ? undefined : out.error });
        mem.append(sess, {
          role: 'tool',
          tool_call_id: tc.id,
          content: JSON.stringify(out.ok ? out.result : { error: out.error }).slice(0, 60_000),
        });
      }
      // 循环继续：让模型看到工具结果后决定是继续查还是作答
    }

    if (reply === null && !llmError) {
      // 工具循环用尽仍未给出最终答复
      reply = '我查了几轮还是没能得出可靠结论，先把已知的告诉你：' +
              (toolTrace.length ? `我试过 ${toolTrace.map((t) => t.tool).join('、')}，` : '') +
              '但信息不足。你能否补充一下具体要查什么？';
      mem.append(sess, { role: 'assistant', content: reply });
    }

    // ── 7. 压缩与落盘
    let compacted = false;
    try { compacted = await mem.compact(sess, llm.summarize); }
    catch (e) { console.error('[agent] 压缩异常', e?.message ?? e); }
    mem.save(sess);
    // 去重表必须**立即**落盘：只在退出时写的话，进程被 kill -9 时这次消息不在表里，
    // launchd 拉起后服务端若重推同一条，守衡会重复回话。
    flushSeen();

    if (llmError) {
      return { reply: `我这边调用模型失败了，没法回答这个问题。\n\n失败原因：${llmError}\n\n（这是我的问题，不是你的输入有问题。）`,
               reason: 'llm_error', sessionKey: key, meta: { toolTrace } };
    }

    return { reply: reply || null, reason: reply ? 'ok' : 'empty_reply', sessionKey: key,
             meta: { toolTrace, compacted, truncated, turns: sess.messages.length, summary: !!sess.summary } };
  });
}

/* ─────────────────── 供外部查询的运行时信息 ─────────────────── */

export function status() {
  return {
    model: config.llm.model,
    llm: llm.stats,
    tools: toolNames(),
    sessions: mem.listSessions(),
    maxTurns: config.llm.maxTurns,
    maxToolIters: config.llm.maxToolIters,
  };
}

/** 供 daemon 在启动时打印，确认工具与模型都装载成功 */
export function loadedTools() { return toolNames(); }
