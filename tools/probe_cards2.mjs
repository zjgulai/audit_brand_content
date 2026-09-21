/**
 * probe_cards2.mjs —— 第二路探针：把第一路被拒的两个元素换成 schema 2.0 的写法再试
 *
 * 第一路的实测结论（PMO/logs/card_probe.jsonl）：
 *   ✅ header(template/subtitle) · markdown · table · column_set · collapsible_panel
 *   ❌ note   → 230099 "cards of schema V2 no longer support this capability"
 *   ❌ action → 230099 同上
 *
 * 被拒不是因为写错，是 **schema V2 移除了这两个 tag**。所以第二路要回答的是：
 *   1. 注脚该用什么代替？候选：column_set（V2 的 fields 形态）· 纯 markdown 小字
 *   2. 按钮该用什么代替？候选：裸 button 直接放 elements 里
 *
 * 一张卡只测一个候选，成败即读数。
 */
import fs from 'node:fs';
import path from 'node:path';
import { client } from './agent/feishu.mjs';
import { LOG_DIR, ensureDir } from './agent/config.mjs';

const CHAT_ID = process.env.PROBE_CHAT_ID || 'oc_49a7cfb2861cffa4365ca8491f398d32';
const RESULT_FILE = path.join(LOG_DIR, 'card_probe.jsonl');

const H = (t, c) => ({ title: { tag: 'plain_text', content: t }, template: c });

const PROBES = [
  {
    id: 'v2_fields_columnset',
    asks: '替代 note 的「注脚/字段」在 V2 里是不是 column_set 打底？',
    card: {
      schema: '2.0',
      config: { update_multi: true },
      header: H('探针 8/10 · V2 字段形态', 'grey'),
      body: {
        elements: [
          { tag: 'markdown', content: '候选 A：用 `column_set` 排一行小字段（边界声明打算画在这里）。' },
          {
            tag: 'column_set',
            flex_mode: 'none',
            background_style: 'grey',
            horizontal_spacing: '8px',
            columns: [
              { tag: 'column', width: 'weighted', weight: 1, elements: [{ tag: 'markdown', content: '**置信度**\n查到' }] },
              { tag: 'column', width: 'weighted', weight: 1, elements: [{ tag: 'markdown', content: '**窗口**\n顶到上限' }] },
              { tag: 'column', width: 'weighted', weight: 1, elements: [{ tag: 'markdown', content: '**证据**\n3 条' }] },
            ],
          },
        ],
      },
    },
  },
  {
    id: 'v2_note_markdown',
    asks: '注脚退化为纯 markdown 小字，视觉上够不够用？',
    card: {
      schema: '2.0',
      config: { update_multi: true },
      header: H('探针 9/10 · 注脚退路', 'grey'),
      body: {
        elements: [
          { tag: 'markdown', content: '候选 B：注脚退化成一行 markdown，靠 `~~删除线~~` / 斜体 / 字号做弱化。' },
          { tag: 'hr' },
          { tag: 'markdown', content: '*置信度 查到 · 窗口 顶到上限 · 证据 3 条*' },
        ],
      },
    },
  },
  {
    id: 'v2_button_bare',
    asks: 'V2 里按钮能不能裸放 elements？回调还接得住吗？',
    card: {
      schema: '2.0',
      config: { update_multi: true },
      header: H('探针 10/10 · 裸按钮（勿点）', 'red'),
      body: {
        elements: [
          { tag: 'markdown', content: '候选 C：按钮直接放 elements 里，不要 `action` 包一层。**请忽略，不要点。**' },
          { tag: 'button', text: { tag: 'plain_text', content: '回调测试（勿点）' }, type: 'default', value: { probe: 'button_bare' } },
        ],
      },
    },
  },
];

function digestError(e) {
  const d = e?.response?.data;
  if (!d) return { message: e?.message ?? String(e) };
  return { code: d.code, msg: d.msg, error: d.error };
}

async function main() {
  for (const p of PROBES) {
    try {
      const r = await client.im.message.create({
        params: { receive_id_type: 'chat_id' },
        data: { receive_id: CHAT_ID, msg_type: 'interactive', content: JSON.stringify(p.card) },
      });
      const entry = { at: new Date().toISOString(), id: p.id, asks: p.asks, ok: true, messageId: r?.data?.message_id ?? null };
      ensureDir(LOG_DIR); fs.appendFileSync(RESULT_FILE, JSON.stringify(entry) + '\n');
      console.log(`✅ ${p.id} — 通过，message_id=${entry.messageId}`);
    } catch (e) {
      const err = digestError(e);
      const entry = { at: new Date().toISOString(), id: p.id, asks: p.asks, ok: false, error: err };
      ensureDir(LOG_DIR); fs.appendFileSync(RESULT_FILE, JSON.stringify(entry) + '\n');
      console.log(`❌ ${p.id} — 被拒：${JSON.stringify(err)}`);
    }
    await new Promise((r) => setTimeout(r, 600));
  }
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
