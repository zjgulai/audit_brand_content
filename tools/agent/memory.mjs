/**
 * memory.mjs —— 守衡的记忆层
 *
 * 记忆按「会话」隔离：每个群一个文件，每个人私聊一个文件。
 * 会话变长时，旧轮次交给 LLM 压成一段纪要，而不是硬截断 —— 硬截断会让守衡
 * 忘记「刚才答应过什么」，那比忘记闲聊内容严重得多。
 *
 * 文件格式（PMO/shouheng-state/sessions/<key>.json）：
 * {
 *   key, kind, title, createdAt, updatedAt, messageCount,
 *   summary: "旧轮次压缩纪要",
 *   messages: [ {role, content, at, name?}, ... ]   // 只存未压缩的近期轮次
 * }
 */
import fs from 'node:fs';
import path from 'node:path';
import { stateDir, ensureDir, config } from './config.mjs';

// 惰性求值：与 seenFile 同理，写死成 import 期常量后无法在测试里重定向，
// 且 import 期裸 mkdirSync 会在目录被同名文件占位时让整个进程起不来。
const sessDir = () => path.join(stateDir(), 'sessions');
ensureDir(sessDir());

/** 会话键：群聊 `chat_<id>`，私聊 `dm_<openId>` */
export function sessionKey({ chatId, chatType, senderOpenId }) {
  return chatType === 'p2p' ? `dm_${senderOpenId}` : `chat_${chatId}`;
}

const fileOf = (key) => path.join(sessDir(), `${key.replace(/[^\w.-]/g, '_')}.json`);

export function load(key) {
  const f = fileOf(key);
  if (!fs.existsSync(f)) {
    return { key, kind: key.startsWith('dm_') ? 'dm' : 'chat', title: null,
             createdAt: new Date().toISOString(), updatedAt: null, messageCount: 0,
             summary: '', messages: [] };
  }
  try { return JSON.parse(fs.readFileSync(f, 'utf8')); }
  catch (e) {                                      // 文件损坏不应让守衡整个挂掉
    const bak = `${f}.corrupt-${Date.now()}`;
    try { fs.renameSync(f, bak); } catch {}
    return { key, kind: 'chat', title: null, createdAt: new Date().toISOString(),
             updatedAt: null, messageCount: 0, summary: '', messages: [],
             recoveredFrom: path.basename(bak) };
  }
}

export function save(sess) {
  sess.updatedAt = new Date().toISOString();
  const f = fileOf(sess.key);
  const tmp = `${f}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(sess, null, 2));   // 先写临时文件再 rename，
  fs.renameSync(tmp, f);                                  // 避免进程被杀时留下半个文件
  return f;
}

/** 追加一条消息 */
export function append(sess, msg) {
  sess.messages.push({ at: new Date().toISOString(), ...msg });
  sess.messageCount = (sess.messageCount ?? 0) + 1;
}

/** 记录群/人的展示名，方便日志里看懂是谁 */
export function setTitle(sess, title) {
  if (title && sess.title !== title) sess.title = title;
}

/* ─────────────────────── 上下文压缩 ─────────────────────── */

/**
 * 把过长的历史压成纪要。调用方需传入一个 summarize(messages) -> string 函数
 * （通常绑定到 LLM），这样记忆层不直接依赖 LLM 模块，便于测试。
 *
 * 两个参数是**独立**的：
 *   keepTurns —— 保留最近几轮原文（保留量）
 *   triggerAt —— 超过多少条才启动压缩（触发线）
 * 之前我把触发线写死成 config.maxTurns，等于让「保留量」既当保留又当触发，
 * 调用方传 keepTurns 却不生效 —— 测试因此测不到真实行为。
 *
 * 关键约束：切点必须落在「一轮用户消息之前」，不能在 assistant(tool_calls) 与
 * 它对应的 tool 结果之间切开 —— OpenAI 兼容协议要求 tool_calls 后面必须紧跟
 * 同数量的 tool 消息，切开会让下一次请求直接被 API 拒绝（400）。
 *
 * 返回值：是否发生了压缩。
 */
export async function compact(sess, summarize, keepTurns = config.llm.maxTurns, triggerAt = config.llm.maxTurns) {
  if (sess.messages.length <= triggerAt) return false;

  // 从末尾往前数 keepTurns 个「用户消息」，切在最后数到的那个之前。
  //
  // 按「轮」定位而不是按「条数」：一轮问答可能包含 assistant(tool_calls) + 若干 tool
  // 结果，条数不定。按条数算会把工具调用也算进保留量，留下的比 keepTurns 还多。
  //
  // 数够之后必须**原地停住**，让 cut 指着那个边界下标。
  // 写成「数够了再 break、但 cut 仍在递减」是错的：cut 会一路退到 0 附近，
  // 把几乎整段历史都当成待压缩内容，等于每轮只保留最后一条。踩过这个坑。
  const n = sess.messages.length;
  let seenUsers = 0;
  let cut = 0;
  for (let i = n - 1; i >= 0; i--) {
    if (sess.messages[i]?.role === 'user') {
      seenUsers++;
      if (seenUsers === keepTurns) { cut = i; break; }   // 切在第 keepTurns 个 user 之前
    }
  }

  // cut 为 0 有两种情况，都不能压缩：
  //   a) 整段里没有用户消息（找不到边界）
  //   b) 用户消息不足 keepTurns 轮
  // 强行压缩会破坏 tool_calls 配对，宁可长着也不要发坏请求。
  if (cut <= 0) return false;

  const old = sess.messages.slice(0, cut);
  const keep = sess.messages.slice(cut);
  if (old.length === 0) return false;

  let digest;
  try {
    digest = await summarize(old, sess.summary);
  } catch (e) {
    // 压缩失败不能丢消息 —— 只做安全截断，并留下痕迹
    digest = `${sess.summary}\n（提示：本段压缩失败 ${e.message}，以下为原始截断）\n` +
             old.map((m) => `${m.role}: ${String(m.content).slice(0, 200)}`).join('\n');
  }

  sess.summary = String(digest ?? '').trim();
  sess.messages = keep;
  return true;
}

/** 构造发给 LLM 的 messages 数组 */
export function toLlmMessages(sess, systemPrompt) {
  const out = [{ role: 'system', content: systemPrompt }];
  if (sess.summary) {
    out.push({
      role: 'system',
      content: `# 本会话早前内容的纪要（更早的对话已压缩，以下是可靠摘要）\n${sess.summary}`,
    });
  }
  for (const m of sess.messages) {
    if (m.role === 'user' || m.role === 'assistant' || m.role === 'tool' || m.role === 'system') {
      out.push({ role: m.role, content: m.content, ...(m.tool_calls ? { tool_calls: m.tool_calls } : {}),
                 ...(m.tool_call_id ? { tool_call_id: m.tool_call_id } : {}) });
    }
  }
  return out;
}

/** 会话列表（给「/status」之类用途） */
export function listSessions() {
  return fs.readdirSync(sessDir()).filter((f) => f.endsWith('.json')).map((f) => {
    try { const s = JSON.parse(fs.readFileSync(path.join(sessDir(), f), 'utf8'));
          return { key: s.key, title: s.title, messages: s.messages?.length ?? 0,
                   total: s.messageCount ?? 0, updatedAt: s.updatedAt, hasSummary: !!s.summary }; }
    catch { return { key: f, error: 'unreadable' }; }
  });
}
