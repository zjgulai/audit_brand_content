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
import { parentIdOf, alreadyInHistory, buildQuoteBlock } from './thread.mjs';
import { foldInto } from './outbound.mjs';

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

/* ─────────────────── 兜底话术：工具循环用尽时说什么 ─────────────────── */

/**
 * 工具循环用尽、模型始终没给出最终答复时，替它说一句实话。
 *
 * ★ 硬约束：**正文里不许出现工具名**（2026-09-22 实测事故，见下）。
 *   这条约束由 `tools/verify_cards.mjs` 的 **L6** 守着 —— 它把本函数喂给
 *   `lintCopy()`，并要求**不说话术本身被自己的检测器拦下**。
 *
 * ── 为什么单独拆成函数
 *
 * 原先这句话术是**内联**在工具循环后面的一行字符串拼接，它长这样：
 *
 * ```js
 * '我查了几轮还是没能得出可靠结论，先把已知的告诉你：'
 *   + `我试过 ${toolTrace.map((t) => t.tool).join('、')}，` + '但信息不足。…'
 * ```
 *
 * 一次工具循环里 `run_readonly_command` 会连出十几次，于是正文变成
 * 「我试过 run_readonly_command、run_readonly_command、…（19 次）」——
 * 而 `internalLeak` 规则判「**连续三次同名工具**」为故障，
 * 它在 `verify_cards.mjs` F 段的**正样本正是这句话的形状**。
 *
 * 也就是说：**这句话术 100% 会被自己的检测器拦下**，`envelope.mjs` 把它降级成
 * 「我这次没能把回答组织好」的拒答。2026-09-22 16:34 实测：上游在私聊里问
 * 「你如何读取我 DSH 上的知识库」，两次都跑满 6 轮工具、两次都撞上这一条，
 * **她问了两次、被拒答两次，而盘上没有任何东西记得她欠一条回答。**
 *
 * 根因不是检测器太严（它抓得对），也不是话术不该说「我查不到」——
 * 是**内部详情被写进了正文**。工具名属于排查材料：它已经在 `toolTrace`
 * （进 `meta`、进日志）里，正文只该说人话。
 *
 * @param {Array<{tool:string, ok:boolean}>} toolTrace 本轮实际调过的工具
 * @returns {string} 面向用户的一段话，**不含任何工具名/函数名/轮次上限**
 */
export function fallbackReply(toolTrace = []) {
  const n = toolTrace.length;
  const nFail = toolTrace.filter((t) => !t.ok).length;
  return '这个问题我没答上来 —— 查了几轮，还是没能得出可靠结论。'
    + (n
        ? `\n\n（我这边翻了 ${n} 处${nFail ? `，其中 ${nFail} 处没读通` : '，都能读到，但没拼出答案'}。`
          + '明细留在我这侧，就不往这里贴了。）'
        : '\n\n（我这轮连一次有效检索都没走完。）')
    + '\n\n你把要查的范围再说细一点，我重新来。';
}

/* ─────────────────── 主处理函数 ─────────────────── */

/**
 * 处理一条飞书消息，返回要发出的回复文本（不负责发送）。
 * @param {object} event  im.message.receive_v1 的 data
 * @returns {Promise<{reply:string|null, reason?:string, sessionKey?:string, meta?:object}>}
 */
export async function handleMessage(event, { force = false } = {}) {
  const msg     = event?.message ?? {};
  const sender  = event?.sender ?? {};
  const chatId  = msg.chat_id;
  const chatType = msg.chat_type;                    // 'group' | 'p2p'
  const senderOpenId = sender?.sender_id?.open_id ?? sender?.sender_id?.user_id ?? '';

  // ── 1. 去重必须**最先**做。
  // 放在类型判断之后是错的：非文本消息（图片/文件）会绕过去重，
  // 服务端重推同一条时会重复回话，用户看到守衡对同一张图说两遍「我读不了」。
  //
  // ★ `force`（2026-09-22 加，Q1-1d）：**补发**要重放同一条消息，而它必然已在去重表里。
  //   所以补发那一路显式绕过去重 —— 但它绕过的**只有这一道**，幂等的另外两道
  //   （台账已答 / 记忆已答）由 `retry_queue.mjs` 自己判，那两道才是防「答两遍」的。
  if (!force && alreadyHandled(msg.message_id)) {
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

    // ── 5.4 把「我说过、但记忆里没有的」补进来（2026-09-22 加）
    //
    // ★ 为什么必须有这一步：`mem.append` 只在**回复循环**里调，而守衡**主动说出的话**
    //   （`send_once.mjs` 手发的、基线告警、待收提醒、崩溃自报）都不经过那里。
    //   后果在 09-22 14:39 变成了对外的：她 14:39:34 回「归我」，而守衡的上下文里
    //   **只有她那句话、没有自己 14:37:55 问过的那一句** —— 它看到的是一句悬空的回答，
    //   往上接到了 27 小时前的话题上，答成「那三条过期内容归你」并发了出去。
    //   台账（`outbound.mjs`）记着那条问话，这一步把它折回记忆。
    //
    // ★ 位置是**判据的一部分**，不能挪：
    //   · 必须在 §5.5 **之前** —— 折进来之后再问「上文在不在历史里」，那条问话就已经在了，
    //     同一个上文不会既进历史又进引用块（两遍就是噪音，还会让模型以为问了两遍）；
    //   · 必须在 `mem.append(sess, { role: 'user', ... })` **之前** —— 它问的话要在
    //     她的回答**上面**，否则模型读到的是「先答后问」。
    //
    // ⚠️ 三种情形在日志里长得不一样（**取不到 ≠ 没有要补的**）：
    //   · 补了 N 条 → 记一行，带上 message_id；
    //   · 没有要补的 → 记一行「无新增」（这是正常的，不是失败）；
    //   · **读数采不到**（台账读不出 / 有坏行 / 只读了尾部）→ 记 **未测**，不许当成「没有」。
    let outboundFold = { folded: 0, plan: { entries: [], untested: null } };
    try {
      outboundFold = foldInto(sess, chatId);
      const p = outboundFold.plan;
      if (outboundFold.folded) {
        const ids = p.entries.map((e) => (e.message_ids ?? []).join('+') || '(无 id)').join(', ');
        console.log(`[agent] ↩ 补记外发 ${outboundFold.folded} 条进会话记忆：${ids}`);
      } else if (p.untested) {
        console.log(`[agent] ⚠️ 补记外发未测：${p.untested}`);
      } else {
        console.log(`[agent] · 补记外发：无新增（台账里没有「我说过但记忆里没有」的话）`);
      }
    } catch (e) {
      // 补记失败不该让这次回话失败 —— 但那一定是**未测**，不能静默。
      console.log(`[agent] ⚠️ 补记外发未测：这一步抛了 ${e?.message ?? e}`);
      outboundFold = { folded: 0, plan: { entries: [], untested: `抛异常：${e?.message ?? e}` } };
    }

    // ── 5.5 「这条消息在回复哪一句」—— 把上文摆到模型面前（2026-09-22 加）
    //
    // ★ 为什么必须有这一步（一次真实的外部误答，不是推演）：
    //   09-22 14:37:55 我方主动推送问了「117 条签核归谁」；她 14:39:34 用**话题回复**答「归我」。
    //   `im.message.receive_v1` 事件里 `parent_id` / `root_id` **都指着我方那条消息** ——
    //   飞书把线索完整送来了。而 `ws_daemon.mjs` 的 `onMessage` 从不读这两个字段，
    //   加上主动推送不进会话记忆（`memory.append` 只在回复循环里调），
    //   模型看到的是一句**悬空的「归我」**，往上接到 27 小时前的话题上，
    //   14:39:51 答成了「那三条过期内容归你」并**发了出去**。
    //
    //   两条根因里，这一条**不碰 import 图、不用改 memory.append** ——
    //   一次回读就能让守衡看见自己问过什么（实测机器人读得回自己发的消息，
    //   含 `send_once.mjs` 发的主动推送，见 PMO/守衡-误答登记-20260922.md §3.2.1）。
    //
    // ⚠️ 三种情形必须在**日志里长得不一样**（取不到 ≠ 没有上文）：
    //   · 不是回复        → 不引（正常）
    //   · 已在会话历史里  → 不引（避免同一个上文出现两遍）
    //   · **读不到**      → 说「未测」，不许当成「没有上文」
    let parentBlock = null;
    const parentId = parentIdOf(msg);
    if (parentId) {
      const parent = await feishu.getMessage(parentId);
      if (parent?.error) {
        // ⚠️ **不能静默降级。** 她很可能正是在答一句我们读不到的话；
        // 这时「装作没有上文」与「以为没有上文」都会重演 14:39 那次误答。
        // 也不能只说一句"读不到"就完 —— 得告诉模型**这时该怎么做**，
        // 否则它仍会自己找一句最近的话接上去（那正是上次发生的事）。
        console.log(`[agent] ⚠️ 引用上文未测：回读 ${parentId} 失败（${parent.error}）`);
        parentBlock = [
          '〔引用上文 · 未测〕对方这条消息是在回复某一条，但**我读不到那一条**。',
          `· 回读 ${parentId} 失败：${parent.error}`,
          '· 所以：**不要在看不见上文的情况下猜她在答什么**，也不要把最近说过的一句当成她答的那一句。',
          '  要接话就先说清"你回复的那条我读不到"，再问她是哪一件事。',
          '〔引用上文结束〕',
        ].join('\n');
      } else if (!alreadyInHistory(sess.messages, parent.text)) {
        parentBlock = buildQuoteBlock({
          from: parent.from,
          text: parent.text,
          at: parent.at,
        });
        console.log(`[agent] ↩ 引用上文 ${parentId}（${parent.from}｜${parent.text.length} 字）`);
      } else {
        console.log(`[agent] · 引用上文跳过：${parentId} 的内容已在会话历史里`);
      }
    }

    const userTurn = chatType === 'group' ? `【${senderName}】${question}` : question;
    const turnContent = parentBlock ? `${parentBlock}\n\n${userTurn}` : userTurn;
    // ★ `force`（补发）时**不重复 append 同一个用户轮**：上一轮失败前已经 append 过一次
    //   （失败发生在工具循环里，用户轮早在它之前就进内存了），再 append 一次会让守衡
    //   「记得她问了两遍」。判据是「最后一条 user 轮与本次逐字相同」，不是「force 就不 append」——
    //   万一上次是在 append 之前就崩了，这一轮必须把问题补进记忆，否则它就真丢了。
    const lastUser = [...(sess.messages ?? [])].reverse().find((m) => m?.role === 'user');
    if (force && lastUser && lastUser.content === turnContent) {
      console.log('[agent] ↩ 补发重放：用户轮已在记忆里，不重复 append');
    } else {
      mem.append(sess, { role: 'user', content: turnContent, name: senderName });
    }

    // ── 6. 工具循环
    const systemPrompt = buildSystemPrompt(
      chatType === 'group'
        ? `\n# 当前场景\n你在群聊「${sess.title ?? chatId}」里，正在回复 ${senderName}。群里其他人也会看到你的回答，所以不要输出私密信息，也不要假设只有一个人在听。`
        : `\n# 当前场景\n你在与 ${senderName} 私聊。`
    );

    const toolTrace = [];
    let reply = null;
    let llmError = null;
    let llmFailure = null;             // ★ 整条失败体（layer/chain/attempts/retryable），不只那句 error
    let truncated = false;
    let toolExhausted = false;         // ★ 走没走兜底话术（决定 reason，`retry_queue` 靠它补发）

    for (let iter = 0; iter < config.llm.maxToolIters; iter++) {
      const messages = mem.toLlmMessages(sess, systemPrompt);
      const r = await llm.chat(messages, { tools: TOOL_SCHEMAS });

      if (!r.ok) { llmError = r.error; llmFailure = r; break; }

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
      toolExhausted = true;
      // 工具循环用尽仍未给出最终答复。文案见 `fallbackReply()` —— 它有一条硬约束
      // （不许出现工具名），由 `verify_cards.mjs` 的 L6 断言。
      reply = fallbackReply(toolTrace);
      // 工具名只进日志：可排查，但**不进正文**（正文那份由上面那个函数产生）。
      console.warn(
        `[agent] ⚠️ 工具循环用尽：上限 ${config.llm.maxToolIters} 轮 / 实调 ${toolTrace.length} 次`
        + `｜工具 ${[...new Set(toolTrace.map((t) => t.tool))].join(',') || '（无）'}`
        + `｜其中失败 ${toolTrace.filter((t) => !t.ok).length} 次`
        + ` → 已改用兜底话术（明细只留在这里）`
      );
      // ★ `tool_exhausted` 是**结构标记**，与 `llm_error` 同一用途：告诉补发队列
      //   「这条 assistant 不是真回答」。没有它，`answeredInMemory()` 会把兜底话术
      //   当成真回答，于是「答不上」就真的变成「永远答不上」——
      //   2026-09-22 她连问两次都得到兜底话术，而队列一条都补不出去。
      mem.append(sess, { role: 'assistant', content: reply, tool_exhausted: true });
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
      const notice = `我这边调用模型失败了，没法回答这个问题。\n\n失败原因：${llmError}\n\n（这是我的问题，不是你的输入有问题。）`;
      // ★ 1c（2026-09-22 加）：**群里看得见的话，记忆里必须也有**。
      //   原先这个分支直接 return，`mem.append` 只在回复循环里调 —— 于是守衡事后想不起
      //   自己说过「答不了」：她 15:40 问「你刚才为什么说答不了」，它的会话里只有
      //   她 15:29 的问题和 15:42 的正常答复，中间那次失败**在它的记忆里不存在**。
      //   `llm_error: true` 是给补发队列看的**结构标记**（不是靠比对那句文案）：
      //   「这条 assistant 不是真回答」。`toLlmMessages` 只取 role/content，不会漏给模型。
      mem.append(sess, { role: 'assistant', content: notice, llm_error: true });
      mem.save(sess);
      return { reply: notice, reason: 'llm_error', sessionKey: key,
               meta: { toolTrace, llm: { layer: llmFailure?.layer ?? '未知',
                                        retryable: llmFailure?.retryable === true,
                                        attempts: llmFailure?.attempts?.length ?? 0,
                                        chain: llmFailure?.chain ?? [] } } };
    }

    return { reply: reply || null,
             reason: reply ? (toolExhausted ? 'tool_exhausted' : 'ok') : 'empty_reply',
             sessionKey: key,
             meta: { toolTrace, compacted, summary_chars: (sess.summary ?? '').length,
                     truncated, turns: sess.messages.length,
                     outbound: { folded: outboundFold.folded, untested: outboundFold.plan.untested } } };
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
