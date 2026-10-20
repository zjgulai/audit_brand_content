/**
 * feishu.mjs —— 飞书侧能力封装
 *
 * 两个关键转换在这里：
 *   1. mention 还原：飞书把 @ 渲染成 `@_user_N` 占位符，LLM 读到的是乱码。
 *      必须对照 message.mentions 还原成真名，否则守衡不知道谁在跟它说话。
 *   2. markdown → 飞书富文本(post)：LLM 天然输出 markdown，直接塞给飞书会显示成一堆星号。
 */
import * as Lark from '@larksuiteoapi/node-sdk';
import fs from 'node:fs';
import path from 'node:path';
import { config, attachmentDir } from './config.mjs';
import { appendLifecycle } from './attachment_lifecycle.mjs';
import { beijingString } from './timefmt.mjs';

export const client = new Lark.Client({
  appId: config.lark.appId,
  appSecret: config.lark.appSecret,
  // ★ loggerLevel 显式降到 warn。
  // 默认是 info，SDK 会在构造时往 **stdout** 打一行 `[info]: [ 'client ready' ]`。
  // 后果不是刷屏，是**把 stdout 弄脏**：任何 `node xxx.mjs --json | 下一步` 的管道
  // 都会拿到一段不是 JSON 的开头。2026-09-18 实测：
  // `cli.mjs sample receipt --json | cli.mjs validate -` 因此报「不是合法 JSON」。
  // 守衡自己的日志走 ws_daemon 的 log()，不依赖 SDK 这一行。
  loggerLevel: Lark.LoggerLevel.warn,
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

/* ─────────────── 读回正文：post / interactive 也要读得出来 ─────────────── */

/**
 * ★ 2026-09-22 新增。**在它之前，守衡读自己的历史是瞎的。**
 *
 * 实测（当天 15:35 拿真实群历史跑了一遍 `listRecentMessages`）：
 *
 * ```
 * 2026-09-18 12:40:20 interactive 守衡(你自己)  （interactive 类型，正文为空 —— 我没法看到里面的内容。）
 * 2026-09-22 14:39:52 interactive 守衡(你自己)  （interactive 类型，正文为空 —— 我没法看到里面的内容。）
 * 2026-09-22 15:32:16 post        守衡(你自己)  （post 类型，正文为空 —— 我没法看到里面的内容。）
 * ```
 *
 * 而**内容就在 payload 里** —— 那条 post 的 `body.content` 逐字是
 * `{"title":"","content":[[{"tag":"text","text":"我这边调用模型失败了，没法回答这个问题。"}],…]}`。
 * 我们只是按 `JSON.parse(content).text` 去读了，而 post / interactive **没有 `text` 这个字段**。
 *
 * 这是 §2.4.1 的**第 4 行**（否定结论比输入大）：工具说的是「**我读不了**」，
 * 真相是「**我没去读对地方**」。后果与 14:39 那次误答同源 ——
 * `sendMarkdown` 发的都是 **post**、卡片回复都是 **interactive**，
 * 于是**守衡读群历史时看不见自己说过的绝大多数话**，只看得见 `send_once.mjs`
 * 手发的那几条 `text`。它问「我先前说过什么」时，答案是结构性地缺的。
 *
 * 判据在 `tools/verify_outbound.py` 的 **G 段**：拿这几条**真实 payload** 做回归。
 */

/** post（富文本）的 content JSON → 纯文本。读不出来回 `null`（**不是空串**）。 */
export function postToPlain(contentJson) {
  let d;
  try { d = JSON.parse(contentJson ?? '{}'); } catch { return null; }
  // 飞书同时给 content 与 content_v2（实测同值）；取不到第一个才用第二个。
  const blocks = Array.isArray(d?.content) ? d.content : (Array.isArray(d?.content_v2) ? d.content_v2 : null);
  if (!blocks) return null;
  const lines = [];
  for (const para of blocks) {
    if (!Array.isArray(para)) continue;
    lines.push(para.map((n) => {
      const tag = n?.tag;
      if (tag === 'a') return n.text ?? n.href ?? '';
      if (tag === 'at') return `@${n.user_name ?? n.user_id ?? ''}`;
      if (tag === 'img') return '[图片]';
      if (tag === 'media') return '[媒体]';
      return typeof n?.text === 'string' ? n.text : '';
    }).join(''));
  }
  return lines.join('\n');
}

/**
 * 卡片（interactive）的 JSON → 文字**重建**。回 `{title, lines, stub}`。
 *
 * ⚠️ **实测（2026-09-22，拿 14:39:52 那张真卡跑了一遍）**：`im/v1/messages` 对 interactive
 * 消息**不返回卡片正文**，只回一句占位：
 *
 * ```json
 * {"title":"已收到","elements":[[{"tag":"img",…},{"tag":"text","text":"请升级至最新版本客户端，以查看内容"}]]}
 * ```
 *
 * 所以「卡片读得回来」是**假的**。能读到的只有**标题**（上面这个是「已收到」）。
 * 这一条必须写进返回值，否则 `bodyToText` 会把那句占位文案当成卡片内容交出去 ——
 * 那比原先的「我看不到」更坏：**它看起来像内容**。
 */
function cardToPlain(contentJson) {
  let d;
  try { d = JSON.parse(contentJson ?? '{}'); } catch { return { title: null, lines: [], stub: false, bad: true }; }
  if (!d || typeof d !== 'object') return { title: null, lines: [], stub: false, bad: true };

  const lines = [];
  const seen = new Set();
  const walk = (node) => {
    if (node == null) return;
    if (Array.isArray(node)) { for (const x of node) walk(x); return; }
    if (typeof node !== 'object') return;
    for (const [k, v] of Object.entries(node)) {
      if (typeof v === 'string' && (k === 'text' || k === 'content')) {
        if (v.trim() && !seen.has(v)) { seen.add(v); lines.push(v); }
        continue;
      }
      if (v && typeof v === 'object') walk(v);
    }
  };
  walk(d);

  const title = typeof d.title === 'string' ? d.title
              : (typeof d?.header?.title?.content === 'string' ? d.header.title.content : null);
  const stub = lines.some((s) => /请升级至最新版本客户端/.test(s));
  return { title, lines: lines.filter((s) => !/请升级至最新版本客户端/.test(s)), stub, bad: false };
}

/**
 * 把一条消息的 `body.content` 读成**人话**。两个读取入口（`getMessage` / `listRecentMessages`）
 * 都走这里 —— 两处各写一份解析，就是「同一个形状有两个实现」，
 * 而这两份一定会漂移（一份修了另一份没修，表现是「有时候读得到有时候读不到」）。
 *
 * @returns {{text:string|null, parsed:boolean, note?:string}}
 *   `text` 为 `null` 表示**没解析出内容**（`note` 说明是哪种没解析出来）——
 *   与「解析出来是空的」必须分得开（§2.4.1 第 1 行那个「0 张表」）。
 */
export function bodyToText(msgType, contentJson) {
  if (msgType === 'text') {
    let t = null;
    try { t = JSON.parse(contentJson ?? '{}').text ?? null; } catch { t = null; }
    if (typeof t === 'string') return { text: t, parsed: true };
    return { text: null, parsed: false, note: 'text 类型但解析不出 `.text` 字段' };
  }
  if (msgType === 'post') {
    const t = postToPlain(contentJson);
    if (t !== null) return { text: t, parsed: true };
    return { text: null, parsed: false, note: 'post 类型但 `content` / `content_v2` 都不是段落数组' };
  }
  if (msgType === 'interactive') {
    const c = cardToPlain(contentJson);
    const title = c.title ? `「${c.title}」` : '（连标题都没有）';
    if (c.bad) return { text: null, parsed: false, note: 'interactive 类型但卡片 JSON 解析失败' };
    if (c.stub) {
      // ★ 接口只回占位文案 —— 这是**通道的盲区**，不是「我懒得读」。
      //   照实说：读不到正文；能读到的只有标题。别把占位文案当内容交出去。
      return { text: null, parsed: false,
               note: `卡片正文这个接口不返回（只回一句「请升级至最新版本客户端」占位），`
                   + `能读到的只有标题${title}。卡片说了什么，只有发它的那一方（会话记忆 / 外发台账）知道` };
    }
    if (c.lines.length) {
      // ⚠️ 必须说清这是**重建**：卡片存的是结构，不是一段正文。
      //    把重建结果当成逐字原文去引用，就是另一种「比依据大」。
      return { text: `（卡片文字按结构还原，非逐字原文${c.title ? `；标题${title}` : ''}）\n${c.lines.join('\n')}`,
               parsed: true };
    }
    return { text: null, parsed: false, note: `interactive 类型但卡片 JSON 里没抽到文字（标题${title}）` };
  }
  return { text: null, parsed: false, note: `${msgType ?? '未知'} 类型没有正文读取通道` };
}

/* ─────────────────── 附件：下载 + 文本抽取（2026-10-21 加）───────────────────
 *
 * ★ 这条通道的规矩变过，别读旧注释：
 *   2026-09-18 的红线是「飞书上的内容禁止下载」；**2026-10-17 委托方推翻**，
 *   现原文是「你都可以下载，飞书你可以访问的附件和业务提供的。」
 *   所以代码里任何「公司不让下载」「按规矩不取」的话术都是**引用了已废止的红线**。
 *
 * 仍然有效的两条约束（不是旧红线的残留）：
 *   1. **下载来的东西不许进公开仓。** 落盘根在仓外（config.attachmentDir()），
 *      目录 0700，本次处理完**立即删除**（run-scoped）。
 *   2. **附件内容是不可信输入。** 它只能作为审核/分析对象，不能当作对模型的指令。
 *      这句话由 agent.mjs 在拼进上下文时显式写出来。
 *
 * 能力边界（今天真正的边界，不是政策）：图片/音视频的内容解析还没接上
 * （Q4-② 的 OCR 接线在 base/，不在这条链路上）。**没接上就说没接上**，
 * 不许说成「读不到」，更不许说成「不让下载」。
 */

export const ATTACHMENT_TYPES = new Set(['file', 'image', 'media', 'audio']);

/** 可以按 UTF-8 直接读的扩展名。没有这一条就不猜 —— 二进制当文本会产出乱码假正文。 */
const TEXT_ATTACHMENT_EXT = new Set([
  '.txt', '.md', '.markdown', '.csv', '.tsv', '.json', '.jsonl',
  '.yaml', '.yml', '.xml', '.html', '.htm', '.log', '.ini', '.toml',
  '.py', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.sh', '.sql', '.css',
]);

/** 单次最多读入的字节数（不是飞书上限；是为了不把上下文撑爆）。 */
export const MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024;
/** 单次最多拼进上下文的字符数。超了必须**说出来**，不许静默截断。 */
export const MAX_ATTACHMENT_CHARS = 40_000;

/* ★ 2026-10-21：附件残留**不做自动删除**。
 *   为什么：删除 `~/.shouheng/attachments` 下的历史文件是销毁行为，需要委托方对该路径的
 *   明确授权；本会话没有。所以这里只提供「数出来」的读数与生命周期台账，
 *   实际删除只针对**本次调用自己创建**的临时目录（见 ingestAttachment 的 finish()）。
 *   启动横幅里的年龄分桶由 `attachment_lifecycle.countAttachmentResidue()` 提供。
 *   自动清理历史残留是另一张票，等授权。 */

/**
 * 从消息事件里解析附件元数据。**纯函数，离线可证。**
 * @returns {{isAttachment:boolean, type:string|null, fileKey:string|null,
 *            fileName:string|null, content:object}}
 */
export function parseAttachment(msg) {
  const type = msg?.message_type ?? null;
  let content = {};
  try { content = JSON.parse(msg?.content ?? '{}') ?? {}; } catch { content = {}; }
  return {
    isAttachment: ATTACHMENT_TYPES.has(type),
    type,
    fileKey: content.file_key ?? content.image_key ?? null,
    fileName: content.file_name ?? content.name ?? null,
    content,
  };
}

/** 扩展名是不是「可以直接按 UTF-8 读」的那一类。名字缺失 → false（不猜）。 */
export function isTextAttachment(fileName) {
  const ext = path.extname(String(fileName ?? '')).toLowerCase();
  return TEXT_ATTACHMENT_EXT.has(ext);
}

/**
 * 下载消息里的资源文件。**这是本仓库新增的飞书下载调用点**，
 * 已在 `tools/download_callers.json` 登记（DG-1），落盘根必须在仓外（DG-2）。
 *
 * @param {{messageId:string,fileKey:string,type:string,destPath:string,maxBytes?:number}} p
 * @returns {Promise<{written:boolean, skipped?:string, size?:number|null}>}
 */
export async function downloadMessageResource({
  messageId, fileKey, type, destPath, maxBytes = MAX_ATTACHMENT_BYTES,
}) {
  const r = await client.im.v1.messageResource.get({
    path: { message_id: messageId, file_key: fileKey },
    // 飞书这个接口只认 image / file 两档：图片走 image，其余（文件/语音/视频）走 file。
    params: { type: type === 'image' ? 'image' : 'file' },
  });
  if (!r || typeof r.writeFile !== 'function') {
    throw new Error('SDK 没有返回可写流（messageResource.get 的响应形状变了）');
  }
  const len = Number(r.headers?.['content-length'] ?? NaN);
  if (Number.isFinite(len) && len > maxBytes) {
    // 先读头再决定要不要落盘：一个 80MB 的视频不该先写满盘再说「太大」。
    try { r.getReadableStream()?.destroy?.(); } catch { /* 流已关也无妨 */ }
    return { written: false, skipped: 'too_large', size: len };
  }
  await r.writeFile(destPath);
  try { fs.chmodSync(destPath, 0o600); } catch { /* 目录已是 0700；这一步是双保险 */ }
  const size = (() => { try { return fs.statSync(destPath).size; } catch { return null; } })();
  return { written: true, size };
}

/**
 * 处理一条附件消息：只对**文本类附件**下载并抽正文；其余类型如实说「还没接解析」。
 *
 * 返回的 `status` 必须与 `reply` 对得上，且这些状态互不冒充：
 *   ingested / empty / unsupported_type / too_large / binary / download_failed / bad_content
 *
 * ★ 这里**不抛异常**：附件处理失败不该让整条消息处理崩掉；失败要变成一句说得出口的话。
 *
 * @returns {Promise<{status:string, reason?:string, reply?:string, text?:string,
 *                    truncated?:boolean, size?:number|null, name?:string, type?:string}>}
 */
export async function ingestAttachment(msg, {
  maxBytes = MAX_ATTACHMENT_BYTES, maxChars = MAX_ATTACHMENT_CHARS,
} = {}) {
  const a = parseAttachment(msg);
  const name = a.fileName || (a.type === 'image' ? '（图片）' : '（未命名附件）');
  const baseMeta = { name, type: a.type, size: null };
  const root = attachmentDir();
  let dir = null;
  let ledgerError = null;

  /**
   * 终态：清理**本次自己创建**的临时目录 + 写生命周期台账。
   *
   * ★ 只删 `dir`，绝不扫父目录删历史残留 —— 销毁历史文件需要委托方对该路径的明确授权。
   *   `deleted` 是**实际结果**：rmSync 抛异常时是 false，不是「我以为删了」。
   *   台账写不进去时，返回里带 `lifecycle_ledger_error`，不静默吞掉。
   */
  const finish = (status, extra = {}) => {
    let deleted = null;
    let cleanupError = null;
    if (dir) {
      try {
        fs.rmSync(dir, { recursive: true, force: true });
        deleted = true;
      } catch (e) {
        deleted = false;
        cleanupError = e.code ?? e.message;
      }
    }
    const led = appendLifecycle({
      status,
      file_token: a.fileKey,
      message_id: msg?.message_id ?? null,
      type: a.type,
      created: !!dir,
      deleted,
      ...(extra.size != null ? { size: extra.size } : {}),
      ...(cleanupError ? { cleanup_error: cleanupError } : {}),
      ...(extra.error ? { error: String(extra.error) } : {}),
    });
    if (!led.ok && !ledgerError) ledgerError = led.error;
    return {
      status,
      ...extra,
      ...(cleanupError ? { cleanup_error: cleanupError } : {}),
      ...(ledgerError ? { lifecycle_ledger_error: ledgerError } : {}),
    };
  };

  if (!a.isAttachment) {
    return finish('bad_content', { reason: 'attachment_bad_content',
             reply: `这条消息标成「${a.type ?? '未知'}」，但它不是可处理的附件类型。` });
  }
  if (!a.fileKey) {
    return finish('bad_content', { reason: 'attachment_bad_content', ...baseMeta,
             reply: `附件「${name}」的消息里没有 file_key —— 我拿不到下载地址。`
                  + '这是这条事件的内容问题，不是权限问题。' });
  }
  if (!isTextAttachment(a.fileName)) {
    return finish('unsupported_type', { reason: 'attachment_type_unparsed', ...baseMeta,
             reply: `附件「${name}」我收到了，但这类文件的内容解析**这条链路还没接上**。`
                  + '这是能力边界，不是权限问题，也不是「不让下载」—— 下载是允许的。\n'
                  + '要看内容，把关键文字贴过来，或转成飞书云文档发我（云文档我能直接读）。' });
  }

  // ★ 下载前先记 started：进程被 SIGKILL 时，台账里只会留下这一行，
  //   配合启动横幅的年龄分桶，「被 kill」与「正常收尾」就长得不一样了。
  const started = appendLifecycle({
    status: 'started', file_token: a.fileKey, message_id: msg?.message_id ?? null,
    type: a.type, created: false, deleted: null,
  });
  if (!started.ok && !ledgerError) ledgerError = started.error;

  try {
    fs.mkdirSync(root, { recursive: true, mode: 0o700 });
    try { fs.chmodSync(root, 0o700); } catch { /* 改不动权限时仍继续；DG-2 会报 */ }
    // mkdtemp 默认 0700；文件名不用用户给的名字（避免路径穿越），只保留扩展名。
    dir = fs.mkdtempSync(path.join(root, 'msg-'));
    const dest = path.join(dir, `attachment${path.extname(a.fileName).toLowerCase()}`);
    const got = await downloadMessageResource({
      messageId: msg.message_id, fileKey: a.fileKey, type: a.type, destPath: dest, maxBytes,
    });
    if (!got.written) {
      return finish('too_large', { reason: 'attachment_too_large', ...baseMeta, size: got.size ?? null,
               reply: `附件「${name}」有 ${got.size ?? '（大小未知）'} 字节，超过我这次能读入的上限 `
                    + `${maxBytes} 字节。**我没有读它**，也没有截断后冒充全文。`
                    + '要审的话，请给一段更小的文件，或只把关键部分贴过来。' });
    }
    if (!got.size) {
      return finish('empty', { reason: 'attachment_empty', ...baseMeta,
               reply: `附件「${name}」取到了，但文件是空的（0 字节）。` });
    }
    const buf = fs.readFileSync(dest);
    if (buf.includes(0)) {
      // 扩展名像文本，字节里却有 NUL —— 这是二进制。当成文本读会产出乱码假正文。
      return finish('binary', { reason: 'attachment_binary', ...baseMeta, size: got.size,
               reply: `附件「${name}」的扩展名像文本，但内容含 NUL 字节，按二进制处理。`
                    + '**我没有把乱码当正文读**。要看内容，请贴文字或转云文档。' });
    }
    let text = buf.toString('utf8');
    const truncated = [...text].length > maxChars;
    if (truncated) text = [...text].slice(0, maxChars).join('');
    return finish('ingested', {
      reason: 'attachment_text_ingested', ...baseMeta,
      size: got.size, chars: [...text].length, truncated, text,
    });
  } catch (e) {
    return finish('download_failed', { reason: 'attachment_download_failed', ...baseMeta,
             error: e?.message ?? String(e),
             reply: `附件「${name}」我这边**没取到**（${e?.message ?? e}）。\n`
                  + '这是「没取到」，不是「文件里没有内容」，也不是「不让下载」—— 下载是允许的。'
                  + '可以稍后重发，或把文字贴过来。' });
  }
}

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

/**
 * 回复某条消息，内容是一张卡片（msg_type=interactive）。
 *
 * 为什么单独一个函数、不复用 replyCard（reply-cards/index.mjs 里那个）：
 * 那个版本失败时自己会去 sendCard 兜底，而 daemon 需要的是
 * 「reply 失败 → 由调用方决定退成什么」。两处兜底叠加的后果是
 * 同一个回答在群里出现两次。所以这一层**只做一次尝试**，失败如实返回。
 *
 * @returns {Promise<{ok:boolean, messageId?:string, mode:string, error?:string}>}
 */
export async function replyCard(messageId, card) {
  try {
    const r = await client.im.message.reply({
      path: { message_id: messageId },
      data: { msg_type: 'interactive', content: JSON.stringify(card) },
    });
    return { ok: true, messageId: r?.data?.message_id ?? null, mode: 'reply-card' };
  } catch (e) {
    const d = e?.response?.data;
    return { ok: false, mode: 'reply-card-failed',
             error: d ? `code=${d.code} ${String(d.msg ?? '').slice(0, 140)}` : String(e?.message ?? e) };
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
      // ★ 2026-09-22：改走 `bodyToText`。原先这里只认 `JSON.parse(content).text`，
      //   而 **post（`sendMarkdown` 发的）与 interactive（卡片）没有 `text` 字段** ——
      //   于是守衡读群历史时，**自己发出去的话全部显示成「我没法看到里面的内容」**。
      //   实测那三行读数与根因写在 `bodyToText` 上面。
      const parsed = bodyToText(it.msg_type, it.body?.content);
      const raw = parsed.text ?? '';
      // 撤回的消息，飞书把正文换成一句英文占位符，原文在任何接口都取不回。
      // 必须把它和「正常但很短的消息」区分开：前者是**内容没了**，后者是**本来就这么短**。
      // 混在一起时，守衡会把「撤回」读成「有一条我看不懂的消息」，进而低估自己漏了多少东西。
      const recalled = /^This message was recalled$/i.test(raw.trim());
      // 附件（file/image/media/audio）：**历史回读不取内容**，只标出它存在。
      // ★ 这不是政策 —— 下载已于 2026-10-17 放开（AGENTS.md §2.6）。
      //   这是「recent_messages 只回读正文」这条路径的能力边界；
      //   入站消息里的文本类附件由 `ingestAttachment()` 单独抽取。
      //   旧文案写的是「飞书内容禁止下载」，引用的是一条已废止的红线。
      const text = recalled
        ? '（原文已在飞书端撤回，撤回后任何接口都不返回内容）'
        : (raw || (ATTACHMENT_TYPES.has(it.msg_type)
            ? '（这是附件：历史回读不取内容，只标出它存在；入站时的文本类附件会被单独抽取。）'
            // ★ 这一句原先对 post / interactive 也这么说过（「正文为空 —— 我没法看到里面的内容」），
            //   而那是**假否定**：内容就在 payload 里，是我们没去读对地方。
            //   现在只有**真的没解析出来**才落到这里，并把「是哪种没解析出来」写出来 ——
            //   **「没解析出来」和「内容为空」是两件事**，读的人要能分开。
            : `（${it.msg_type ?? '未知'} 类型：我没能解析出正文 —— ${parsed.note ?? '未知原因'}）`));
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

/**
 * 按 `message_id` 回读**单条**消息。回 `{ error }` 而**不抛** —— 与 `listRecentMessages` 同风格。
 *
 * ★ 存在的理由（2026-09-22）：她被 @ 时用**话题回复**答话，
 *   而 `im.message.receive_v1` 事件里 `parent_id` / `root_id` 指着我方那条消息。
 *   两个字段原先没人读 → 守衡看到一句悬空的回答，接到了别的话题上，误答并外发。
 *   判据（什么时候该读、读哪一条）在 `agent/thread.mjs`，**这里只管把那一读做出来**。
 *
 * ★ 实测（2026-09-22，只读探针，见 PMO/守衡-误答登记-20260922.md §3.2.1）：
 *   机器人**读得回自己发出去的消息** —— 包括 `tools/send_once.mjs` 发的主动推送
 *   （`om_x100b64166aff2ca8b487459d2f76acb` 实测读得到，`sender_type=app`）。
 *   所以「守衡看不见自己问过什么」这一半，靠这一次回读就能补上，
 *   **不需要动 import 图、不需要给 memory.append 加调用点**。
 *
 * @returns {Promise<{text:string, from:string, senderType:string, senderOpenId:string|null,
 *                    at:string|null, msgType:string, recalled:boolean, parentId:string|null,
 *                    rootId:string|null}|{error:string}>}
 */
export async function getMessage(messageId) {
  try {
    const r = await client.im.message.get({ path: { message_id: messageId } });
    const items = r?.data?.items ?? [];
    if (!items.length) {
      // ⚠️ `code=0` 但 items 为空 —— 必须与「读到了空消息」长得不一样（§2.4.1 第 1 行那个坑）。
      return { error: `消息 ${messageId} 回读成功但 items 为空（code=0）—— 这是「读不到」，不是「内容是空的」` };
    }
    const it = items[0];

    // ★ 2026-09-22：改走 `bodyToText`（与 `listRecentMessages` 同一份解析）。
    //   原先这里也只认 `.text` —— 后果具体到本轮：`outbound_ledger.mjs --backfill`
    //   会给一条 **post** 消息写进**空正文**的台账记录，而空正文在折记忆时会被跳过，
    //   于是「补记了」和「没补记」在表面上完全一样。补记的正是守衡自己发的话，
    //   而它自己发的**绝大多数是 post**（`sendMarkdown` 走富文本）。
    const parsed = bodyToText(it.msg_type, it.body?.content);
    const raw = parsed.text ?? '';

    // 撤回：飞书把正文换成一句英文占位符，原文任何接口都取不回。
    // 必须与「正常但很短的消息」分开 —— 前者是**内容没了**，后者是**本来就这么短**。
    const recalled = /^This message was recalled$/i.test(raw.trim());

    const senderType = it.sender?.sender_type;       // user | app
    const senderOpenId = senderType === 'user' ? (it.sender?.id ?? null) : null;

    // 发信人的显示名：机器人直接说「你自己」，用户才去查名。
    // 查不到就如实写 open_id，**不编一个称呼**（把 id 写出来至少能比对）。
    let from = senderType === 'app' ? `${BOT_NAME}(你自己)` : null;
    if (!from && senderOpenId) {
      const looked = await getUserName(senderOpenId, it.chat_id ?? null);
      from = looked?.name ?? `用户(${senderOpenId})`;
    }

    return {
      text: recalled ? '（原文已在飞书端撤回，撤回后任何接口都不返回内容）' : raw,
      from: from ?? String(senderType ?? '(未知发送者)'),
      senderType: senderType ?? null,
      senderOpenId,
      // ★ 2026-09-22 补：`chat_id` 原先没有带出去。补记外发（`tools/outbound_ledger.mjs
      //   --backfill`）要把一条历史消息写进台账，而台账是按 `chat_id` 折进会话记忆的 ——
      //   取不到它，「这条是发到哪个群的」就只能靠调用方猜，而猜错的表现是
      //   **折进了另一个群（或谁都折不进）**，两边都不报错。
      chatId: it.chat_id ?? null,
      at: it.create_time ? beijingString(Number(it.create_time)) : null,
      createTime: it.create_time ? Number(it.create_time) : null,
      msgType: it.msg_type ?? null,
      recalled,
      // ★ 解析出来了没有 —— 与 `text` 是空串分得开。调用方（补记台账）据此决定
      //   「这条读回来了」还是「这条我读不出来」，不许把后者当成前者。
      parsed: parsed.parsed,
      parseNote: parsed.note ?? null,
      parentId: it.parent_id ?? null,
      rootId: it.root_id ?? null,
    };
  } catch (e) {
    // 已知会走到这里的一种情形：消息被删除 / 不在本应用可见范围。
    // 这不是「没有上文」，是「读不到上文」—— 调用方必须能分辨（见 thread.mjs 头注）。
    return { error: `回读消息失败 code=${e?.response?.data?.code} msg=${e?.response?.data?.msg ?? e.message}` };
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
