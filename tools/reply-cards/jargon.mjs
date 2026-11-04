/**
 * jargon.mjs —— 剥除模型在正文或卡片字段里裸露的内部引擎赋值黑话与残留信封标记（纯函数）
 *
 * 边界（适配内容审核工作台五标签与建案体系）：
 *   · 拦截内部变量赋值形态：`parse_status = ok`、`coverage = partial`、`does_not_cover = ...`、
 *     `machine_may_finalize = ...`、`rule_keys_hit = ...`、`boundary_statement = ...` 等；
 *   · 拦截模型误写进字段内部的 `[[card:...]]` / `[[/card]]` 信封标记；
 *   · 放行工作台正式案件号（`case-...`）、五标签结论（`BLOCK / REVIEW / PASS / 待自决 / 未审查`）
 *     及正常业务说明。
 */

const INTERNAL_ASSIGN_KEYS = [
  'parse_status',
  'does_not_cover',
  'machine_may_finalize',
  'rule_keys_hit',
  'boundary_statement',
  'risk_items',
  'source_chain',
  'citations',
  'run_state',
  'coverage_state',
].join('|');

const ASSIGN_RE = new RegExp(
  `(^|[\\s（(、，,；;：:|｜/／]\`?)(?:${INTERNAL_ASSIGN_KEYS})\`?\\s*=\\s*`,
  'i',
);

const CARD_MARK_RE = /\[\[\/?card(?::[^\]\n]*)?(?:\]\])?/g;

/**
 * 聊天链出站回执禁词净化（与 base/send_gateway.py::FORBIDDEN_RECEIPT_WORDS 同源）：
 * 机器只做初筛与补证据，绝不替人输出「已通过 / 无需处理 / 审批完成」。
 * 保留「不是『已通过』」「不许说『已通过』」这类否定告诫句不变。
 */
export function sanitizeForbiddenReceiptWords(text) {
  return String(text ?? '')
    .replace(/(?<![不未非「『"'])已通过(?!率)/g, '初筛未见违规（待人工复核）')
    .replace(/(?<![不未非「『"'])无需处理/g, '待人工复核确认')
    .replace(/(?<![不未非「『"'])审批完成/g, '已建案待人工签发');
}

/** 判断单行是否为裸露的内部引擎变量赋值行。 */
export function isJargonLine(line) {
  const t = String(line ?? '');
  if (!t.trim()) return false;
  return ASSIGN_RE.test(t);
}

/** 摘除文本中的内部引擎赋值行、残留 `[[card:...]]` / `[[/card]]` 标记，并净化替人过门禁词。 */
export function stripEngineJargon(text) {
  const src = String(text ?? '');
  const removed = [];
  const kept = [];
  for (const line of src.split('\n')) {
    if (isJargonLine(line)) {
      removed.push(line.trim());
      continue;
    }
    kept.push(sanitizeForbiddenReceiptWords(line.replace(CARD_MARK_RE, '')));
  }
  return { text: kept.join('\n').replace(/\n{3,}/g, '\n\n'), removed };
}

/** 递归清洗卡片数据对象中的内部黑话行与信封标记残留（返回新对象，不改原对象）。 */
export function scrubCardData(value, sink = []) {
  if (typeof value === 'string') {
    const r = stripEngineJargon(value);
    sink.push(...r.removed);
    return r.text;
  }
  if (Array.isArray(value)) return value.map((v) => scrubCardData(v, sink));
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = scrubCardData(v, sink);
    return out;
  }
  return value;
}
