/**
 * feishu.mjs —— 飞书侧能力封装
 *
 * 两个关键转换在这里：
 *   1. mention 还原：飞书把 @ 渲染成 `@_user_N` 占位符，LLM 读到的是乱码。
 *      必须对照 message.mentions 还原成真名，否则守衡不知道谁在跟它说话。
 *   2. markdown → 飞书富文本(post)：LLM 天然输出 markdown，直接塞给飞书会显示成一堆星号。
 */
import * as Lark from '@larksuiteoapi/node-sdk';
import { config } from './config.mjs';
import { beijingString } from './timefmt.mjs';

export const client = new Lark.Client({
  appId: config.lark.appId,
  appSecret: config.lark.appSecret,
});

/** 机器人显示名（名字匹配用）。集中定义，避免多处硬编码写成不一致的字面量 */
export const BOT_NAME = '守衡';

/* ─────────────────────────── mention 还原 ─────────────────────────── */

/**
 * 把消息里的 `@_user_N` 占位符还原成真实姓名。
 * @param {string} text  原始文本，含占位符
 * @param {Array}  mentions  飞书 message.mentions 数组
 * @returns {{display:string, mentions:Array<{key:string,name:string,openId:string,isBot:boolean,tenantKey?:string}>}}
 */
export function resolveMentions(text, mentions = []) {
  const resolved = (mentions ?? []).map((m) => {
    // id 字段在飞书不同事件版本里有三种形态：字符串、{open_id}、{union_id}。
    // 只认 open_id 是不安全的 —— 拿不到时会静默变成空字符串，
    // 后面「按 open_id 找发送者姓名」就永远匹配不上，且不报错。
    const idRaw = m.id;
    const openId  = typeof idRaw === 'object' && idRaw !== null ? (idRaw.open_id ?? '') : (idRaw ?? '');
    const unionId = typeof idRaw === 'object' && idRaw !== null ? (idRaw.union_id ?? '') : '';
    const userId  = typeof idRaw === 'object' && idRaw !== null ? (idRaw.user_id ?? '') : '';
    return {
      key:    m.key ?? '',
      name:   m.name ?? '(未知)',
      openId, unionId, userId,
      // 三者都没有时留原始值，便于排查而不是丢信息
      rawId:  openId || unionId || userId || (typeof idRaw === 'string' ? idRaw : JSON.stringify(idRaw ?? null)),
      isBot:  openId === config.lark.appId || m.name === BOT_NAME,
      tenantKey: m.tenant_key,
    };
  });

  let display = text ?? '';
  for (const m of resolved) {
    if (!m.key) continue;
    // 占位符在文本里就是 @_user_1 这个字面量，全局替换成 @真名
    display = display.split(m.key).join(`@${m.name}`);
  }
  return { display, mentions: resolved };
}

/**
 * 这条消息是否 @ 了守衡？
 * 双判据：open_id 等于自己的 app_id（权威），或显示名等于机器人名。
 * 只用 open_id 会有风险 —— 某些事件形态下 open_id 拿不到；只用名字也有风险（重名）。
 */
export function isBotMentioned(resolvedMentions = []) {
  return resolvedMentions.some((m) => m.isBot);
}

/**
 * 去掉 @守衡 本身，留下真正的问题。
 * 群聊里用户习惯写「@守衡 帮我查下 X」，模型不需要看到那个 @守衡。
 */
export function stripBotMention(display, resolvedMentions = []) {
  let out = display;
  for (const m of resolvedMentions.filter((x) => x.isBot)) {
    out = out.split(`@${m.name}`).join('');
  }
  // 清掉多余的空白，但保留换行结构
  return out.split('\n').map((l) => l.replace(/[ \t]{2,}/g, ' ').trim()).join('\n').trim();
}

/* ───────────────────── markdown → 飞书富文本(post) ───────────────────── */

/**
 * 极简 markdown → 飞书 post 节点转换。
 * 支持：``` 代码块 ```、**粗体**、`行内代码`、普通段落。
 * 不做完整 markdown 解析 —— 只覆盖 LLM 实际会用的那几种，够用且不会有惊喜。
 */
function mdToPostNodes(markdown) {
  const lines = String(markdown ?? '').split('\n');
  const paragraphs = [];
  let codeBuf = null;   // 非 null 表示正在收集代码块

  const inlineToNodes = (s) => {
    const nodes = [];
    const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
    let last = 0, m;
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) nodes.push({ tag: 'text', text: s.slice(last, m.index) });
      const tok = m[0];
      if (tok.startsWith('**')) nodes.push({ tag: 'text', text: tok.slice(2, -2), style: ['bold'] });
      else                      nodes.push({ tag: 'text', text: tok.slice(1, -1), style: ['code_inline'] });
      last = m.index + tok.length;
    }
    if (last < s.length) nodes.push({ tag: 'text', text: s.slice(last) });
    return nodes.length ? nodes : [{ tag: 'text', text: ' ' }];
  };

  for (const raw of lines) {
    const fence = raw.match(/^\s*```(\w*)\s*$/);
    if (fence) {
      if (codeBuf === null) {
        codeBuf = { lang: fence[1] || 'text', lines: [] };       // 进入代码块
      } else {
        paragraphs.push([{ tag: 'code_block', language: codeBuf.lang, text: codeBuf.lines.join('\n') }]);
        codeBuf = null;                                          // 离开代码块
      }
      continue;
    }
    if (codeBuf !== null) { codeBuf.lines.push(raw); continue; }  // 代码块内的行原样收集
    paragraphs.push(inlineToNodes(raw));
  }
  if (codeBuf !== null) {  // 未闭合的代码块也要发出去，不能吞内容
    paragraphs.push([{ tag: 'code_block', language: codeBuf.lang || 'text', text: codeBuf.lines.join('\n') }]);
  }
  return paragraphs;
}

/** 测试出口：让 test_agent.mjs 能单独验证转换逻辑，不必真发消息 */
export const __test_mdToPostNodes = mdToPostNodes;
export const __test_chunkText = chunkText;

/* ─────────────────────────── 发送 ─────────────────────────── */

const MAX_TEXT_LEN = 8000;   // 飞书文本消息安全上限

/** 超长文本切块（优先在换行处切，避免把句子劈开） */
function chunkText(text, size = MAX_TEXT_LEN) {
  const out = [];
  let rest = String(text);
  while (rest.length > size) {
    let cut = rest.lastIndexOf('\n', size);
    if (cut < size * 0.5) cut = size;      // 找不到合适换行就硬切
    out.push(rest.slice(0, cut));
    rest = rest.slice(cut).replace(/^\n+/, '');
  }
  if (rest) out.push(rest);
  return out;
}

/**
 * 发送 markdown 消息到指定会话。
 * 先尝试富文本（保留代码块与粗体），失败则退化为纯文本。
 * @returns {Promise<{ok:boolean, messageIds:string[], mode:string, error?:string}>}
 */
export async function sendMarkdown(chatId, markdown) {
  const chunks = chunkText(markdown);
  const messageIds = [];
  let mode = 'post';

  for (const chunk of chunks) {
    // 1) 尝试富文本
    try {
      const r = await client.im.message.create({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: chatId,
          msg_type: 'post',
          content: JSON.stringify({ zh_cn: { title: '', content: mdToPostNodes(chunk) } }),
        },
      });
      messageIds.push(r?.data?.message_id);
      continue;
    } catch (e) {
      const code = e?.response?.data?.code;
      mode = 'text';
      // 富文本失败（常见：内容里有飞书不认的节点），落回纯文本
      try {
        const r2 = await client.im.message.create({
          params: { receive_id_type: 'chat_id' },
          data: { receive_id: chatId, msg_type: 'text', content: JSON.stringify({ text: chunk }) },
        });
        messageIds.push(r2?.data?.message_id);
      } catch (e2) {
        return { ok: false, messageIds, mode, error: `post code=${code} / text code=${e2?.response?.data?.code} msg=${e2?.response?.data?.msg ?? e2.message}` };
      }
    }
  }
  return { ok: true, messageIds, mode };
}

/**
 * 回复某条消息（形成引用关系，群里更清楚在答谁）。
 * 失败时自动退化为普通发送，保证「答不上」不会变成「不答」。
 */
export async function replyMarkdown(messageId, chatId, markdown) {
  const text = chunkText(markdown)[0];   // 回复只发首块，其余走 sendMarkdown 补发
  try {
    const r = await client.im.message.reply({
      path: { message_id: messageId },
      data: { msg_type: 'text', content: JSON.stringify({ text }) },
    });
    if (markdown.length > text.length) {
      const rest = await sendMarkdown(chatId, markdown.slice(text.length).replace(/^\n+/, ''));
      return { ok: true, messageIds: [r?.data?.message_id, ...rest.messageIds], mode: 'reply+send' };
    }
    return { ok: true, messageIds: [r?.data?.message_id], mode: 'reply' };
  } catch (e) {
    const fallback = await sendMarkdown(chatId, markdown);
    return { ...fallback, mode: `reply-failed→${fallback.mode}`, error: `reply code=${e?.response?.data?.code}` };
  }
}

/** 发一条「正在处理」提示，返回其 message_id 以便后续撤回或更新 */
export async function sendTyping(chatId, text = '（守衡正在处理…）') {
  try {
    const r = await client.im.message.create({
      params: { receive_id_type: 'chat_id' },
      data: { receive_id: chatId, msg_type: 'text', content: JSON.stringify({ text }) },
    });
    return r?.data?.message_id ?? null;
  } catch { return null; }
}

/** 撤回消息（用于清掉「正在处理」提示） */
export async function recallMessage(messageId) {
  if (!messageId) return false;
  try { await client.im.message.delete({ path: { message_id: messageId } }); return true; }
  catch { return false; }
}

/* ─────────────────────────── 读取 ─────────────────────────── */

/** 把群历史里的发送者 open_id 解析成姓名 */
function buildSenderMap(members) {
  const m = new Map();
  for (const u of members ?? []) {
    if (u?.openId && u?.name) m.set(u.openId, u.name);
  }
  return m;
}/**
 * 给一条群历史消息判定「谁发的」。
 *
 * 为什么必须有这个函数：群历史接口**是**返回 sender.id 的（群内发送者都有值，
 * 实测 5/5 条都有），但上层工具曾经把它丢掉、一律显示「用户」，
 * 于是守衡看到 7 条用户消息全是「用户」，据此**误判成「我不知道是谁发的」**。
 * 数据一直都在，是我们在中间丢的 —— 这类「不是能力不足、是自己扔了信息」的
 * 缺陷最难发现，因为守衡会给出一个听上去很合理的「我查不到」。
 *
 * 原则：宁可显示 open_id，也不显示「用户」这种无法区分人的占位符。
 */
export function resolveSender(msg, senderMap) {
  if (msg?.senderType === 'app') return { from: `${BOT_NAME}(你自己)`, senderOpenId: msg.senderId ?? null };
  if (msg?.senderType !== 'user') return { from: String(msg?.senderType ?? '未知'), senderOpenId: msg.senderId ?? null };

  const id = msg.senderId;
  if (!id) return { from: '用户(接口未返回发送者身份)', senderOpenId: null };

  const name = senderMap?.get(id);
  return name
    ? { from: name, senderOpenId: id }                        // 姓名是确定的，直接用
    : { from: `用户(${id})`, senderOpenId: id };              // 退而求其次：open_id 仍可用于比对
}

/** 拉取群最近消息，作为上下文补充 */
export async function listRecentMessages(chatId, pageSize = 20, memberMap = null) {
  try {
    const r = await client.im.message.list({
      params: { container_id_type: 'chat', container_id: chatId, sort_type: 'ByCreateTimeDesc', page_size: pageSize },
    });
    // 没传成员表就自己拉一份：消息列表能否辨认发送者，不该取决于调用方是否记得多传一个参数。
    // 注意 listMembers 返回的是**数组**；曾经这里写成 `?.members`，
    // 于是 map 永远为空、姓名永远解析不出来，而 `?? {}` / `?.` 让这件事完全没有声音。
    // 取错形状必须吵出来，不能静默降级 —— 那正是这个文件里反复出现的病根。
    let map = memberMap;
    if (!map) {
      const members = await listMembers(chatId);
      if (!Array.isArray(members)) {
        console.warn(`[feishu] listMembers 返回的不是数组（${typeof members}），本次无法解析发送者姓名`);
        map = new Map();
      } else {
        map = buildSenderMap(members);
      }
    }
    const items = r?.data?.items ?? [];
    const out = items.map((it) => {
      let raw = ''; try { raw = JSON.parse(it.body?.content ?? '{}').text ?? ''; } catch { raw = it.body?.content ?? ''; }
      // 撤回的消息，飞书把正文换成一句英文占位符，原文在任何接口都取不回。
      // 必须把它和「正常但很短的消息」区分开：前者是**内容没了**，后者是**本来就这么短**。
      // 混在一起时，守衡会把「撤回」读成「有一条我看不懂的消息」，进而低估自己漏了多少东西。
      const recalled = /^This message was recalled$/i.test(raw.trim());
      const text = recalled
        ? '（原文已在飞书端撤回，撤回后任何接口都不返回内容）'
        : (raw || `（${it.msg_type ?? '未知'} 类型，正文为空 —— 我没法看到里面的内容）`);
      const sender = {
        messageId: it.message_id,
        // 北京时间，不是 UTC。原来这里是 toISOString()，而 `now` 工具给的是北京时间，
        // 两个基准并存导致模型又减了 8 小时：真实 11:12 被说成 23:12。
        // 所有对外可见的时间都必须走 timefmt，保持单一基准。
        at: beijingString(Number(it.create_time)),
        senderType: it.sender?.sender_type,     // user | app
        senderId: it.sender?.id,
        msgType: it.msg_type,
        recalled,
        text,
      };
      return { ...sender, ...resolveSender(sender, map) };
    }).reverse();

    // 把「我看不到什么」做成显式字段，而不是让守衡自己意识到。
    // 真实事故（2026-09-16）：本群消息已顶到 50 条上限，守衡在表格里写「第 1 次」，
    // 同时补了一句「不一定是真正的第一次」—— 它意识到了，但这不该靠它自觉。
    // 窗口边界是事实，事实就该由工具给，不由模型推。
    out.window = {
      returned: out.length,
      pageSize,
      atLimit: out.length >= pageSize,
      oldestAt: out[0]?.at ?? null,
      note: out.length >= pageSize
        ? `只返回最近 ${out.length} 条（已顶到 ${pageSize} 条上限，且本工具不分页）：更早的消息我看不到，我也不会知道自己漏了。表里/结论里的「第一次」只能是「本窗口内的第一次」。`
        : `返回最近 ${out.length} 条（未顶到 ${pageSize} 条上限，这已是全部可见历史）。`,
    };
    return out;
  } catch (e) {
    return { error: `拉取消息失败 code=${e?.response?.data?.code} msg=${e?.response?.data?.msg ?? e.message}` };
  }
}

/** 群信息（名称等），用于让守衡知道自己在哪个群 */
export async function getChatInfo(chatId) {
  try {
    const r = await client.im.chat.get({ path: { chat_id: chatId } });
    return { name: r?.data?.name, description: r?.data?.description, memberCount: r?.data?.user_count };
  } catch (e) {
    return { error: `获取群信息失败 code=${e?.response?.data?.code} msg=${e?.response?.data?.msg ?? e.message}` };
  }
}

/** 群成员列表 */
export async function listMembers(chatId, pageSize = 50) {
  try {
    const r = await client.im.chatMembers.get({
      path: { chat_id: chatId },
      params: { member_id_type: 'open_id', page_size: pageSize },
    });
    return (r?.data?.items ?? []).map((m) => ({ name: m.name, openId: m.member_id }));
  } catch (e) {
    return { error: `获取群成员失败 code=${e?.response?.data?.code} msg=${e?.response?.data?.msg ?? e.message}` };
  }
}

/**
 * 用 open_id 查用户显示名。
 *
 * 两条路，按可靠性排序：
 *  1) 群成员列表（im:chat 权限）—— 本应用已有权限，且天然只返回「同群可见」的人
 *  2) 通讯录单查（contact 权限）—— 需要额外开通，未开通会返回 99991672
 *
 * 传了 chatId 就先走 1)；没传或查不到再退到 2)。
 * 两条都失败时返回 { name: null, source: 'none', reason } —— 把原因带出去，
 * 不再静默返回 null，否则上层无法区分「这个人不在可见范围」和「接口没权限」。
 */
const _memberNameCache = new Map(); // chatId -> Map<openId, name>

export async function getUserName(openId, chatId = null) {
  if (!openId) return { name: null, source: 'none', reason: '未提供 open_id' };

  // 路 1：群成员列表
  if (chatId) {
    try {
      let cached = _memberNameCache.get(chatId);
      if (!cached) {
        const members = await listMembers(chatId, 100);
        if (Array.isArray(members)) {
          cached = new Map(members.filter((m) => m.name && m.openId).map((m) => [m.openId, m.name]));
          _memberNameCache.set(chatId, cached);
        }
      }
      if (cached?.has(openId)) return { name: cached.get(openId), source: 'chat_member' };
    } catch { /* 落空，继续走通讯录 */ }
  }

  // 路 2：通讯录单查
  try {
    const r = await client.contact.user.get({ path: { user_id: openId }, params: { user_id_type: 'open_id' } });
    const name = r?.data?.user?.name ?? null;
    if (name) return { name, source: 'contact' };
    return { name: null, source: 'none', reason: '通讯录返回空' };
  } catch (e) {
    const code = e?.response?.data?.code;
    const reason = code === 99991672
      ? '缺少通讯录权限（需开通 contact:contact.base:readonly 等任一），且该人不在本群成员列表中'
      : `通讯录查询失败 code=${code} msg=${e?.response?.data?.msg ?? e.message}`;
    return { name: null, source: 'none', reason };
  }
}

/** 发一条带 @ 的文本消息：文本里写 <at user_id="ou_xxx"></at> 即可触发飞书 @ */
export async function sendTextWithMentions(chatId, text) {
  return client.im.message.create({
    params: { receive_id_type: 'chat_id' },
    data: { receive_id: chatId, msg_type: 'text', content: JSON.stringify({ text }) },
  });
}
