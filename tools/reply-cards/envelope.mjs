/**
 * envelope.mjs —— 把「模型写的一段话」变成「一张卡」
 *
 * ── 为什么要有这一层，而不是让模型直接吐卡片 JSON ────────────────────────
 * 两个理由，第二个更要紧：
 *
 * 1. 让模型写完整的 V2 卡片 JSON，等于把「schema 2.0」「header.template 白名单」
 *    「V2 移除了 note」这些知识塞进每一次推理。它会在这些细节上犯错，
 *    而犯错的代价不是样式难看 —— 是**整条消息被服务端拒掉，回复凭空消失**。
 *
 * 2. 模版的真正作用是**约束内容**，不是换皮。`verdict` 只有一个格、
 *    `boundary` 只有一个格、没东西就空着 —— 这些是槽位，不是建议。
 *    所以这一层必须真的把上限**执行**掉，而不是在注释里写「≤60 字」。
 *
 * ── 实测：上限原来一处在读吗 ───────────────────────────────────────────
 * 没有。cards.mjs 里 `VERDICT_MAX = 60`、`BOUNDARY_MAX = 90`、`MAX_SECTIONS = 3`
 * 三个常量定义完之后，**整个仓库没有任何代码引用它们**（grep 只有定义行）。
 * 也就是说「结论 ≤60 字」此前是一句注释，模型写 300 字也照发。
 * 这一层就是它们唯一的执行点。
 *
 * ── 超长怎么处理：搬，不是砍 ───────────────────────────────────────────
 * 结论超过 60 字时**不截断**。截断会丢内容，而丢内容比格式难看严重得多。
 * 做法是把超出部分的整句搬到 boundary 格 —— 内容一个字不少，只是从
 * 「结论」那一格挪到了「边界」那一格。真搬不动了才降级成纯文本，
 * 并且降级理由写进正文（对方要能看出格式为什么变了）。
 */
import {
  BUILDERS, VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS, collapsible,
  build, validateCard, renderText,
} from './registry.mjs';
import { lintCopy } from './registry.mjs';

/** 卡片块的开头标记。选这个形态是因为它在 markdown 里不构成任何语法，误触概率低。 */
export const CARD_MARK = '[[card:';

const s = (x) => (x === null || x === undefined ? '' : String(x));

/** 长度按**字符**算，不是字节。中文一个字就是一个字。 */
const len = (x) => [...s(x)].length;

/* ═══════════════ ① 找块 ═══════════════ */

/**
 * 从回复里切出卡片块。
 *
 * 容错三件事，都是实测会遇到的：
 *   - 模型可能把整块包进 ```json 围栏
 *   - 块前后可能有多余空行或一句「（已整理成卡片）」
 *   - **块后面还有正文** —— 这是最危险的一种：如果只把标记去掉、正文留着，
 *     群里的表现就是「一张卡 + 一段重复的话」。所以前后文一律不信，
 *     只在块**就在回复里**的前提下，把前后文当作要并进折叠区的补充内容。
 *
 * ★ 坏 JSON 也必须报 `found`。
 *   第一版这里直接 return null，于是 `[[card:receipt]]\n{"title":` 这种
 *   截断输出会**原样漏进群里** —— 标记和半截 JSON 一起显示出来。
 *   实测用例逮到过（envelope 自测「坏 JSON」那条）。所以：只要看见标记，
 *   就算解析失败，也要把标记到结尾这段的位置报出来，供调用方剥干净。
 *
 * @returns {{kind:string, data:object|null, before:string, after:string,
 *            blockStart:number, blockEnd:number, error:string|null}|null}
 *          data 为 null 表示找到了块但解析失败，error 说明原因。
 */
export function extractCardBlock(text) {
  const src = s(text);
  const at = src.indexOf(CARD_MARK);
  if (at < 0) return null;

  const afterMark = src.slice(at + CARD_MARK.length);
  const close = afterMark.indexOf(']]');
  if (close < 0) return null;                     // 连 `]]` 都没有 → 不是块，是普通文字
  const kind = afterMark.slice(0, close).trim();

  let rest = afterMark.slice(close + 2);
  rest = rest.replace(/^\s*```[a-zA-Z]*\s*/, '');        // 容忍 ```json 围栏
  const b0 = rest.indexOf('{');
  if (b0 < 0) {
    return { kind, data: null, before: src.slice(0, at).trim(), after: '',
             blockStart: at, blockEnd: src.length, error: '标记后没有对象' };
  }

  // 从 `{` 起做括号配对扫描。不能直接 indexOf('}')：
  // 卡片数据里几乎一定有 `{...}`（option、item、表头对象），会切在半路。
  let depth = 0, inStr = false, esc = false, end = -1;
  for (let i = b0; i < rest.length; i++) {
    const ch = rest[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') { inStr = true; continue; }
    if (ch === '{') depth++;
    else if (ch === '}') { depth--; if (depth === 0) { end = i; break; } }
  }

  // 括号没配上（截断输出）→ 块一直延伸到文本结尾
  if (end < 0) {
    return { kind, data: null, before: src.slice(0, at).trim(), after: '',
             blockStart: at, blockEnd: src.length, error: '对象括号没配平（多半是输出被截断）' };
  }

  let data;
  try { data = JSON.parse(rest.slice(b0, end + 1)); }
  catch (e) { data = null; if (!e) throw e; }

  const tail = rest.slice(end + 1).replace(/\s*```\s*$/, '').trim();
  const blockEnd = at + CARD_MARK.length + close + 2 + end + 1;
  if (data === null || typeof data !== 'object' || Array.isArray(data)) {
    return { kind, data: null, before: src.slice(0, at).trim(), after: tail,
             blockStart: at, blockEnd, error: '对象不是合法 JSON 或不是对象' };
  }
  return { kind, data, before: src.slice(0, at).trim(), after: tail,
           blockStart: at, blockEnd, error: null };
}

/* ═══════════════ ② 执行上限 ═══════════════ */

/**
 * 每个类型的折叠区在哪个字段。
 *
 * 这个表必须按**构造器实际读的字段**来定，不能想当然填 `evidence` ——
 * 第一版就是一律填 `evidence`，结果 `cannot-read`/`decision`/`data-table`
 * 根本没有这个字段，塞进去的内容**静默消失**（J4 用例逮到）。
 * 「写了但没人读的字段 = 假槽位」，这条规矩对信封层同样成立。
 *
 * `null` 表示这个类型没有折叠区，只能落回正文格（见 foldIn）。
 */
const FOLD_FIELD = {
  'query-answer': 'evidence',
  'evidence': 'evidence',              // groups 是主体，额外内容进 boundary 之外的正文格
  'capability-boundary': 'evidence',
  'find-nothing': 'tried',
  'alert': 'internal',
  'data-table': 'note',
  'receipt': 'note',
  'turn-diff': null,                   // 没有折叠区
  'correction': null,
  'cannot-read': null,
  'decision': null,
};

/** 没有折叠区时，退回哪个正文格。都是「本来就在说补充信息」的格子。 */
const FALLBACK_SLOT = {
  'turn-diff': 'cause',
  'correction': 'cause',
  'cannot-read': 'why',
  'decision': 'ask',
  'receipt': 'note',
  'data-table': 'note',
};

/**
 * 把一段没有专属格子的内容塞进这张卡。
 * 返回 [新 data, 实际落到的字段名 | null]。落到 null 表示确实没地方放。
 */
function foldIn(kind, d, text) {
  const field = FOLD_FIELD[kind];
  if (field) {
    if (Array.isArray(d[field])) return [{ ...d, [field]: [...d[field], text] }, field];
    return [{ ...d, [field]: d[field] ? `${d[field]}\n${text}` : text }, field];
  }
  const slot = FALLBACK_SLOT[kind];
  if (!slot) return [d, null];
  const cur = s(d[slot]);
  return [{ ...d, [slot]: cur ? `${cur}\n\n（补充）${text}` : `（补充）${text}` }, slot];
}

/**
 * 正文格里的内部记录：搬到折叠区。
 *
 * 为什么必须做这一步，而不是只靠 lint 报警：
 * `alert` 的 `what` / `impact` 是**公开展示**的格子，而默认的 what 文案
 * 是「刚才那条回复是故障输出」—— 模型把工具名写进 `what` 是很自然的事。
 * 2026-09-17 那条连列 27 次工具名的回复就是这么出来的。
 * 报警只能让维护者看见，搬走才能让对方看不见。
 *
 * 优先级：有折叠区就搬进去；没有折叠区（alert 一定有 internal）就交给调用方降级。
 */
const PUBLIC_FIELDS = [
  'title', 'verdict', 'reasoning', 'wrong', 'right', 'cause', 'what', 'impact',
  'ask', 'recommend', 'note', 'nextStep', 'boundary', 'why', 'alternative', 'before', 'after',
];

function scrubInternal(kind, d) {
  const moved = [];
  let out = { ...d };
  for (const f of PUBLIC_FIELDS) {
    if (!out[f]) continue;
    // 只认「机械可判」的内部标识，不猜语气
    if (!/(tool_calls|tool_call_id|finishReason|reasoning_tokens|call_[0-9a-zA-Z]{10,})/.test(out[f])) continue;
    const folded = out[f];
    const hit = foldIn(kind, { ...out, [f]: '' }, `（内部详情，排查用）\n${folded}`);
    if (hit[1] === null) continue;                       // 没地方放 → 留给降级处理
    out = hit[0];
    moved.push({ field: f, to: hit[1], chars: len(folded), why: `正文格 ${f} 里出现了内部标识，已搬进折叠区` });
  }
  return { data: out, moved };
}

/**
 * 把字段搬到它该在的格子里。返回改过的 data 和一份搬迁记录。
 *
 * 只处理「搬得动」的情况。搬不动的（比如 correction 的 wrong 太长）
 * 就原样留着 —— 那是模型说错了话，不是格式问题，硬掰只会掩盖。
 *
 * @param {string} kind
 * @param {object} data
 * @param {string[]} extra 卡片块之外的正文。不会丢，也不会重复出现在群里：
 *                         有折叠区就进折叠区，没有就进本类型的「补充」格。
 */
export function enforceLimits(kind, data, extra = []) {
  let d = { ...data };
  const moved = [];

  // 结论超长：按句切，前 VERDICT_MAX 字留结论，其余进 boundary。
  if (d.verdict && len(d.verdict) > VERDICT_MAX) {
    const chars = [...s(d.verdict)];
    // 优先在句号处断开，退而在上限处断 —— 但都要保证不丢字
    let cut = -1;
    for (let i = Math.min(VERDICT_MAX, chars.length - 1); i > VERDICT_MAX * 0.5; i--) {
      if ('。；！？\n'.includes(chars[i])) { cut = i + 1; break; }
    }
    if (cut < 0) cut = VERDICT_MAX;
    const head = chars.slice(0, cut).join('').trim();
    const spill = chars.slice(cut).join('').trim();
    if (spill) {
      d.verdict = head;
      d.boundary = d.boundary ? `${spill} ${d.boundary}` : spill;
      moved.push({ field: 'verdict', to: 'boundary', chars: len(spill), why: `结论超过 ${VERDICT_MAX} 字` });
    }
  }

  // 边界超长：搬进折叠区（有 evidence 就并进去，没有就退到本类型的补充格）
  if (d.boundary && len(d.boundary) > BOUNDARY_MAX) {
    const chars = [...s(d.boundary)];
    let cut = -1;
    for (let i = Math.min(BOUNDARY_MAX, chars.length - 1); i > BOUNDARY_MAX * 0.4; i--) {
      if ('。；\n'.includes(chars[i])) { cut = i + 1; break; }
    }
    if (cut < 0) cut = BOUNDARY_MAX;
    const head = chars.slice(0, cut).join('').trim();
    const spill = chars.slice(cut).join('').trim();
    if (spill) {
      d.boundary = head;
      const [next, to] = foldIn(kind, d, spill);
      d = next;
      moved.push({ field: 'boundary', to: to ?? '(无格可放)', chars: len(spill), why: `单行边界超过 ${BOUNDARY_MAX} 字` });
    }
  }

  // 字段数超限：多出来的字段进折叠区，不丢
  const cap = { 'query-answer': 4, 'receipt': 3, 'data-table': 6 }[kind] ?? 6;
  if (Array.isArray(d.fields) && d.fields.length > cap) {
    const extraFields = d.fields.slice(cap);
    d.fields = d.fields.slice(0, cap);
    const [next, to] = foldIn(kind, d, extraFields.map((f) => `${f.label}：${f.value}`).join('\n'));
    d = next;
    moved.push({ field: 'fields', to: to ?? '(无格可放)', chars: extraFields.length, why: `字段超过 ${cap} 个` });
  }

  // 卡片块之外的正文：一条都不丢。
  for (const text of extra.filter(Boolean)) {
    const [next, to] = foldIn(kind, d, text);
    d = next;
    moved.push({
      field: '块外正文', to: to ?? '(无格可放)', chars: len(text),
      why: to ? `卡片块之外的正文已并入 ${to}` : '卡片块之外有正文，但这个类型没有能承载它的格子（已在日志记录，未发进群）',
    });
  }

  // 正文格里的内部记录 → 折叠区。放在最后，保证前面几轮搬进来的内容也被查一遍。
  const scrubbed = scrubInternal(kind, d);
  d = scrubbed.data;
  moved.push(...scrubbed.moved);

  return { data: d, moved };
}

/* ═══════════════ ②b 段落数上限 —— MAX_SECTIONS 的执行点 ═══════════════ */

/**
 * 卡片**顶层 markdown 块**超过 `MAX_SECTIONS` 时，把多出来的段落搬进折叠区。
 *
 * ★ 为什么在这里、而不在 `enforceLimits` 里：
 *   `enforceLimits` 作用在**数据**上（verdict / boundary 这些格子），
 *   而「顶层 markdown 块有几个」是**建出来的卡**才有的性质 ——
 *   同一个字段在不同卡片类型里可能进正文、也可能进字段表或折叠区。
 *   所以只能在 `build()` 之后数。
 *
 * ★ 口径（与 `cards.mjs` 里 `MAX_SECTIONS` 的注释同源 —— 改一处必须改两处）：
 *   只数 `body.elements` **顶层**的 `markdown`。
 *   `hr` 是分隔线、`collapsible_panel` 是收起区、`column_set` / 字段排是字段表，都不算段落。
 *
 * ★ 搬是搬，砍是砍：搬走的段落**一个字都不改**，整段进折叠区（§2.4）。
 *   丢内容比格式难看严重得多。
 *
 * @param {object} card 已建好的卡
 * @param {number} [max] 上限，默认取 MAX_SECTIONS
 * @returns {{card: object, moved: Array}} 未被改动时 `moved` 为空数组
 */
export function capSections(card, max = MAX_SECTIONS) {
  const els = card && card.body && card.body.elements;
  if (!Array.isArray(els)) return { card, moved: [] };

  const mdIdx = els
    .map((e, i) => (e && e.tag === 'markdown' ? i : -1))
    .filter((i) => i >= 0);
  if (mdIdx.length <= max) return { card, moved: [] };

  const overflowIdx = new Set(mdIdx.slice(max));
  const overflow = els.filter((_, i) => overflowIdx.has(i));
  const kept = els.filter((_, i) => !overflowIdx.has(i));
  kept.push(collapsible(`其余 ${overflow.length} 段（已折叠 · 防复读）`, overflow));

  return {
    card: { ...card, body: { ...card.body, elements: kept } },
    moved: overflow.map((e) => ({
      field: 'sections',
      to: 'collapsible',
      chars: len(e.content || ''),
      why: `顶层段落超过 ${max} 段，第 ${max + 1} 段起搬进折叠区`,
    })),
  };
}

/* ═══════════════ ③ 主入口 ═══════════════ */

/**
 * 回复文本 → 该发什么。
 *
 * 返回的 `mode` 只有两种，语义是**确定**的：
 *   'card' —— 有一张通过校验的卡，去发卡
 *   'text' —— 没有块（正常纯文本回复）、或块不可用。`reason` 说明是哪种。
 *
 * ★ 无论走哪条路，**mark 之后的内容永远不进正文**。
 *   泄漏一条 `[[card:...]]` 到群里，和泄漏一条 tool_calls 是同一类故障。
 *
 * @param {string} reply 模型给的回复原文
 * @returns {{mode:'card'|'text', card?:object, data?:object, kind?:string,
 *            text:string, reason:string|null, moved:Array, lint:Array, dropped:boolean}}
 */
export function toCardOrText(reply) {
  const raw = s(reply);
  const blk = extractCardBlock(raw);

  if (!blk) {
    return { mode: 'text', text: raw, reason: null, moved: [], lint: lintCopy(raw), dropped: false };
  }

  // 找到了标记但数据不可用 → 剥掉整块（含标记与半截 JSON），只留可读的话。
  // 这一步是硬要求：`[[card:...]]` 出现在群里 = 内部格式泄漏，和泄漏 tool_calls 同类。
  if (!blk.data) {
    const text = [blk.before, blk.after].filter(Boolean).join('\n\n').trim()
      || `我这次没能把回答组织成卡片（${blk.error}），上面这条就是我能给出的全部。`;
    return {
      mode: 'text', text, reason: `卡片块不可用：${blk.error}`,
      moved: [], lint: lintCopy(text), dropped: true,
    };
  }

  // 块前后还有正文：不是丢弃，是并进这张卡里该放它的格子。
  // 模型多写的话通常是有用的补充，但**不能留在块外** ——
  // 留在块外，群里看到的就是「一张卡 + 一段重复的话」。
  const extra = [blk.before, blk.after].filter(Boolean);
  const built = (() => {
    const { data, moved } = enforceLimits(blk.kind, blk.data, extra);
    try {
      // 先按数据把长度上限执行掉、再建卡，最后按**建出来的卡**数顶层段落。
      // 顺序不能颠倒：段落数只有卡建出来才存在。
      const capped = capSections(build(blk.kind, data));
      if (capped.moved.length) moved.push(...capped.moved);
      return { card: capped.card, data, moved, err: null };
    } catch (e) {
      return { card: null, data, moved, err: e.message };
    }
  })();

  if (!built.card) {
    // 降级：剥掉整块，只发可读的话。不把坏 JSON 吐进群 —— 那是 2026-09-17 那条故障的同类。
    const text = [blk.before, blk.after].filter(Boolean).join('\n\n').trim()
      || `我本想用「${blk.kind}」卡片回答，但这张卡没通过本地校验，所以这条只能以纯文本发出。`;
    return {
      mode: 'text', text,
      reason: `卡片 ${blk.kind} 构建失败：${built.err.split('\n')[0]}`,
      moved: built.moved, lint: lintCopy(text), dropped: true,
    };
  }

  const text = renderText(built.card);
  return {
    mode: 'card', card: built.card, data: built.data, kind: blk.kind,
    text, reason: null, moved: built.moved, lint: lintCopy(text), dropped: false,
  };
}

/**
 * 自证用：一段输出里到底有没有残留内部标记。
 *
 * 两种泄漏必须分开判，因为**修法完全不同**：
 *
 *   文本层 —— 要发出去的正文（含降级文本）里出现 `[[card:` 或 `tool_calls` 之类，
 *             就是故障，一个字符都不许有。这是 2026-09-17 那条回复的同类。
 *   JSON 层 —— 卡片结构里出现内部标识，只有一种情况允许：它**在折叠面板内部**。
 *             折叠区是 `alert` 这个类型存在的理由 —— 内部详情必须有个地方放，
 *             否则模型只能往正文里写。判据是「公开格干净」，不是「整张卡干净」。
 *
 * @param {string} text 要发出去的文本
 */
export function leaksInternalMark(text) {
  const src = s(text);
  return /\[\[card:/.test(src)
      || /tool_calls|tool_call_id|finishReason|reasoning_tokens/.test(src)
      || /"role"\s*:\s*"tool"/.test(src);
}

/** 公开格（非折叠区）的文本。自证用它断言「对方一眼能看到的地方」是干净的。 */
export function publicTextOf(card) {
  const out = [];
  const walk = (els, insideCollapse) => {
    for (const el of els ?? []) {
      if (el.tag === 'collapsible_panel') { walk(el.elements, true); continue; }
      if (insideCollapse) continue;
      if (el.tag === 'markdown') out.push(el.content ?? '');
      else if (el.tag === 'table') {
        out.push((el.columns ?? []).map((c) => c.display_name ?? c.name).join(' '));
        for (const r of el.rows ?? []) out.push(Object.values(r).join(' '));
      } else if (el.tag === 'column_set') for (const c of el.columns ?? []) walk(c.elements, false);
      else if (el.tag === 'code_block') out.push(el.text ?? '');
      else if (el.tag === 'plain_text') out.push(el.content ?? '');
    }
  };
  walk(card?.body?.elements, false);
  return [card?.header?.title?.content ?? '', card?.header?.subtitle?.content ?? '', ...out].join('\n');
}

/** 供 verify 与 CLI 用：哪些常量真的被读了 */
export const ENFORCED = { VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS, KINDS: Object.keys(BUILDERS), validateCard, capSections };
