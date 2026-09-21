/**
 * index.mjs —— 卡片模版的公共出口 + 发送（带降级）
 *
 * 发送这件事只有一条硬规则：**卡片发不出去时不许不答。**
 * 降级链是 卡片 → 纯文本，且降级后要在正文末尾注明原因 ——
 * 对方看到格式变了，得知道是为什么，而不是以为守衡改风格了。
 */
import { client } from '../agent/feishu.mjs';
import {
  REGISTRY, BY_KIND, BUILDERS, BUILDER_SOURCE_NAME,
  build, validateCard, renderText, shapeOf, sampleCards, lintCopy,
} from './registry.mjs';

export {
  build, validateCard, renderText, shapeOf, sampleCards, lintCopy,
  REGISTRY, BY_KIND, BUILDERS, BUILDER_SOURCE_NAME,
};

/**
 * 发一张卡到会话。
 * @returns {Promise<{ok:boolean, mode:string, messageId?:string, error?:string, text:string}>}
 */
export async function sendCard(chatId, kind, data) {
  const card = build(kind, data);
  const text = renderText(card);
  try {
    const r = await client.im.message.create({
      params: { receive_id_type: 'chat_id' },
      data: { receive_id: chatId, msg_type: 'interactive', content: JSON.stringify(card) },
    });
    return { ok: true, mode: 'card', messageId: r?.data?.message_id ?? null, text };
  } catch (e) {
    const d = e?.response?.data;
    const why = d
      ? `卡片被拒 code=${d.code} ${String(d.msg ?? '').slice(0, 120)}`
      : `卡片发送异常 ${e?.message ?? e}`;
    // 降级：纯文本。注意这里**不用 post**（post 转换器 mdToPostNodes 不认表格），
    // 直接用 text —— 竖线表格在 text 里至少每行还是独立一行。
    try {
      const r2 = await client.im.message.create({
        params: { receive_id_type: 'chat_id' },
        data: { receive_id: chatId, msg_type: 'text', content: JSON.stringify({ text: renderText(card, why) }) },
      });
      return { ok: true, mode: 'text-fallback', messageId: r2?.data?.message_id ?? null, error: why, text };
    } catch (e2) {
      return { ok: false, mode: 'none', error: `${why} ／ 降级也失败：${e2?.response?.data?.code ?? e2.message}`, text };
    }
  }
}

/** 回复某条消息（形成引用）。卡片不支持 reply 时退化为普通发送。 */
export async function replyCard(messageId, chatId, kind, data) {
  const card = build(kind, data);
  try {
    const r = await client.im.message.reply({
      path: { message_id: messageId },
      data: { msg_type: 'interactive', content: JSON.stringify(card) },
    });
    return { ok: true, mode: 'reply-card', messageId: r?.data?.message_id ?? null, text: renderText(card) };
  } catch (e) {
    const d = e?.response?.data;
    return { ...(await sendCard(chatId, kind, data)),
             mode: `reply-card-failed→fallback`,
             error: d ? `reply code=${d.code}` : String(e?.message ?? e) };
  }
}

/** 供 agent 决策用的一行清单（塞进提示词） */
export function menuForPrompt() {
  return REGISTRY.map((r) => `- \`${r.kind}\`（${r.zh}）：${r.when.split('反例')[0].trim()}`).join('\n');
}
