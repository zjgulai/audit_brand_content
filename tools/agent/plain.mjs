/**
 * plain.mjs —— 出站文本与卡片的符号净化及安全转义（纯函数，单一真源）
 *
 * 解决两类真实渲染故障：
 *   1. `replyMarkdown` 走飞书 `msg_type: 'text'` 时，飞书不解析 `**粗体**` 与行首 `###`，
 *      导致群里直接露出字面星号 `*`。`plainify()` 成对摘除星号与标题井号，保留下划线标识符。
 *   2. 审核命中的原文片段若含 `<img ...>` / `<table>` 等原始 HTML 标签或 `~~` 删除线，
 *      嵌入卡片/报告 markdown 时会导致飞书解析失败或整段被划掉。`mdTextSafe()` 统一转义。
 */

/** 成对摘除 markdown 星号、反引号围栏与行首标题井号；保留下划线（避免破坏 user_id / rule_key 等标识符）。 */
export function plainify(text) {
  return String(text ?? '')
    .replace(/```[a-zA-Z0-9_-]*\n?([\s\S]*?)```/g, '$1')
    .replace(/```/g, '')
    .replace(/\*\*([^*\n]+)\*\*/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/\*([^*\n]+)\*/g, '$1')
    .replace(/\*/g, '')
    .replace(/`([^`\n]+)`/g, '$1')
    .replace(/`/g, '')
    .replace(/^[ \t]*#{1,6}[ \t]+/gm, '');
}

/** 检测文本中是否仍残留字面星号 `*` 或反引号 `` ` ``。 */
export function hasMdSymbols(text) {
  return /[*`]/.test(String(text ?? ''));
}

const CARD_TEXT_KEYS = {
  markdown: ['content'],
  plain_text: ['content'],
  lark_md: ['content'],
  text: ['content'],
  button: ['text'],
  table: [],
};

/**
 * 递归摘除卡片对象所有可见文本与表格单元格中的 Markdown 特殊符号（* / ** / ` / ``` / #）。
 * 作为 cards.mjs::build() 的唯一出口守卫，确保卡片上永不出现未渲染的 Markdown 符号。
 */
export function plainifyCard(card) {
  const walk = (node) => {
    if (Array.isArray(node)) return node.map(walk);
    if (!node || typeof node !== 'object') return node;
    const out = {};
    if (node.tag === 'table' && Array.isArray(node.columns) && Array.isArray(node.rows)) {
      out.columns = node.columns.map((c) => ({
        ...c,
        ...(typeof c.name === 'string' ? { name: plainify(c.name) } : {}),
        ...(typeof c.display_name === 'string' ? { display_name: plainify(c.display_name) } : {}),
      }));
      out.rows = node.rows.map((r) => Object.fromEntries(Object.entries(r)
        .map(([k, v]) => [plainify(k), typeof v === 'string' ? plainify(v) : v])));
    }
    for (const [k, v] of Object.entries(node)) {
      if (out[k] !== undefined && (k === 'columns' || k === 'rows')) continue;
      if (typeof v === 'string') {
        const keys = CARD_TEXT_KEYS[node.tag];
        out[k] = (keys && keys.includes(k)) ? plainify(v) : v;
      } else if (typeof v === 'object' && v !== null) {
        out[k] = walk(v);
      } else {
        out[k] = v;
      }
    }
    return out;
  };
  return walk(card);
}

/** 出站纯文本通道（msg_type=text）发送前清理 markdown 星号。 */
export function plainifyForSend(text, { where = '未命名调用点' } = {}) {
  const src = String(text ?? '');
  const out = plainify(src);
  const before = (src.match(/\*/g) ?? []).length;
  const changed = out !== src;
  return { text: out, changed, before, where };
}

/**
 * 将命中原文安全转义为可嵌入飞书 markdown 的字面文本（防 HTML 标签报错与 `~~` 误触发删除线）。
 */
export function mdTextSafe(s) {
  return String(s ?? '')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/~/g, '&#126;');
}
