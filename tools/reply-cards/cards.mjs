/**
 * cards.mjs —— 守衡的群回复卡片模版（10 类）
 *
 * ── 这个文件解决什么问题 ────────────────────────────────────────────────
 * 守衡在群里的回复，基线是 786 字（本项目实测中位数），形态是「markdown 标题 + 表格 +
 * 结尾三条边界声明」，全部走 msg_type=text 发出去 —— 飞书把它当纯文本渲染，
 * 竖线表格、`**粗体**`、`## 标题` 原样显示成符号。三个真实故障：
 *   1. 工具循环用尽时把内部记录原样发进群（连列 27 次工具名）——见 sessions 2026-09-17。
 *   2. 同一个问题的回答里，「边界声明」重复长成 5 条，占到全文三分之一。
 *   3. 表格在群里根本不是表格，是一堆 `|`。
 *
 * ── 设计立场 ───────────────────────────────────────────────────────────
 * **不靠模型自觉，靠模版逼。** 人格提示词里已经写了「结论先行」「不确定性显式」，
 * 但它每次都要重新解释一遍，于是变成了复读。模版的作用是把这些变成**槽位**：
 * 结论只有一个格（verdict），边界只有一个格（boundary），没东西就不要写。
 *
 * ── 元素集从哪来 ───────────────────────────────────────────────────────
 * 不是从文档抄的，是 2026-09-18 往测试群真发 10 张探针卡测出来的
 * （读数：PMO/logs/card_probe.jsonl）。探针否掉了两个我们本来打算用的元素：
 *
 *   ❌ note   → 230099 "cards of schema V2 no longer support this capability"
 *   ❌ action → 同上（按钮不能再包一层 action）
 *
 * 这两个如果按文档印象直接写进模版，**整张卡会被服务端整体拒绝**——
 * 表现是守衡的回复凭空消失（不是降级，是丢）。所以下面 ALLOWED_TAGS 是一份
 * **实测白名单**，validateCard() 会拦住越界用法。
 */
import fs from 'node:fs';
import path from 'node:path';

/* ═══════════════════════════ 实测常量 ═══════════════════════════ */

/** header.template 实测可用的取值（探针 1/7 通过的是 turquoise，其余为 V2 常规取值） */
export const TEMPLATES = [
  'blue', 'wathet', 'turquoise', 'green', 'yellow', 'orange',
  'red', 'carmine', 'violet', 'purple', 'indigo', 'grey',
];

/** V2 支持的 tag —— 探针里成功发出去的那些 */
export const ALLOWED_TAGS = new Set([
  'markdown', 'plain_text', 'hr', 'table', 'column_set', 'column',
  'collapsible_panel', 'button', 'code_block', 'standard_icon',
]);

/** V2 **已移除**、写了就整卡被拒的 tag。单独列出来是为了给出可操作的报错。 */
export const REMOVED_IN_V2 = {
  note: 'V2 移除了 note。注脚改用 column_set（background_style: grey）或一行 markdown。',
  action: 'V2 移除了 action 容器。按钮直接裸放 elements 里（探针 10/10 通过）。',
  div: 'V2 移除了 div。正文内容用 markdown。',
  fields: 'V2 移除了 fields。字段排布用 column_set。',
  img: 'V2 移除了 img。图片改由 markdown 的 ![alt](url) 承载。',
  image: 'V2 移除了 image。同上。',
};

/** 卡片头部配色 → 语义。颜色不是装饰，是「这条要不要停下看」的信号。 */
export const TONE = {
  'query-answer': 'blue',        // 常规问答，可以略过
  'correction': 'red',           // 我说错了，必须看
  'capability-boundary': 'grey', // 能力边界，存档性质
  'find-nothing': 'orange',      // 没找到，需要你补信息
  'cannot-read': 'wathet',       // 输入我读不了
  'receipt': 'grey',             // 只确认收到
  'turn-diff': 'violet',         // 同一问题的两次回答不一样
  'evidence': 'green',           // 证据陈列
  'alert': 'carmine',            // 我这侧坏了
  'decision': 'purple',          // 要你做决定
};

/** 结论行的长度上限（字符）。超过说明结论没提炼出来，退化成正文了。 */
export const VERDICT_MAX = 60;
/** 单行边界声明的长度上限。超过说明又在写段落，不是在写边界。 */
export const BOUNDARY_MAX = 90;
/**
 * 卡片正文里允许出现的**顶层 markdown 块**数上限，防复读。
 *
 * 口径（2026-09-22 定，写在代码里而不是文档里）：
 *   「段落」只数 `body.elements` **顶层**的 `markdown` 块。
 *   `hr` 是分隔线、`collapsible_panel` 是收起区（本来就不占观感）、
 *   `column_set` / 字段排是字段表 —— 都不算段落。
 *
 * 值 = **实测上界**，不是拍出来的：11 张样例卡的顶层 markdown 块数最大是 4
 * （`correction` 与 `find-nothing` 各 4，其余 ≤3），所以取 4。
 * 原值 3 在三种口径下都拦不到东西（顶层块上界 4 / 承载正文块 6 / 全部 elements 7），
 * 而且**整个仓库没有一行代码拿它做比较** —— 正是 §2.4 点名的那个病。
 * 复现：`grep -rn MAX_SECTIONS tools/`，以及 `node tools/verify_cards.mjs` 的 J1。
 *
 * 执行点：`envelope.mjs` 的 `capSections()`，由 `toCardOrText()` 对建好的卡调用；
 * 超出的段落**搬进折叠区**，不丢字符（§2.4「搬是搬，砍是砍」）。
 */
export const MAX_SECTIONS = 4;

/* ═══════════════════════════ 子元素构造器 ═══════════════════════════ */

/** 纯文本节点（header / button 的 text 字段要这个形态，不是字符串） */
export const t = (content) => ({ tag: 'plain_text', content: String(content) });

/** 正文 markdown 块 */
export const md = (content) => ({ tag: 'markdown', content: String(content) });

export const hr = () => ({ tag: 'hr' });

/**
 * 原生表格（探针 3/7 通过）。
 * ★ 这是本次最大的收益：守衡 42% 的回复含数据表，以前只能当纯文本竖线发出去。
 * 注意 rows 的每一项是**对象**不是数组：{列名: 值}，列名须与 columns[].name 一致。
 */
export function table(columns, rows) {
  return {
    tag: 'table',
    columns: columns.map((c) => (typeof c === 'string'
      ? { name: c, display_name: c, data_type: 'text' }
      : { data_type: 'text', ...c })),
    rows: rows.map((r) => (Array.isArray(r)
      ? Object.fromEntries(columns.map((c, i) => [typeof c === 'string' ? c : c.name, r[i] ?? '']))
      : r)),
  };
}

/**
 * 分栏（探针 4/7 通过）。用于「能做 / 做不到」这类对照。
 * background_style: grey 是 note 被移除后的**替代注脚形态**（探针 8/10 通过）。
 */
export function columns(cols, opts = {}) {
  return {
    tag: 'column_set',
    flex_mode: opts.flexMode ?? 'none',
    ...(opts.backgroundStyle ? { background_style: opts.backgroundStyle } : {}),
    ...(opts.horizontalSpacing ? { horizontal_spacing: opts.horizontalSpacing } : {}),
    columns: cols.map((c) => ({
      tag: 'column',
      width: 'weighted',
      weight: c.weight ?? 1,
      elements: [md(c.content)],
    })),
  };
}

/** 一格字段排（用于边界声明：一行放 3–4 个短字段，而不是三句解释） */
export function fieldRow(fields, opts = {}) {
  return columns(
    fields.map((f) => ({ content: `**${f.label}**\n${f.value}` })),
    { backgroundStyle: 'grey', horizontalSpacing: '8px', ...opts },
  );
}

/** 折叠面板（探针 5/7 通过）。长证据默认收起——这是「中位数 791 字」的直接解法。 */
export function collapsible(title, inner, expanded = false) {
  return {
    tag: 'collapsible_panel',
    expanded,
    header: {
      title: md(title),
      vertical_align: 'center',
      icon: { tag: 'standard_icon', token: 'down-small-ccm_outlined', size: '16px 16px' },
      icon_position: 'right',
      icon_expanded_angle: -180,
    },
    elements: inner.map((e) => (typeof e === 'string' ? md(e) : e)),
  };
}

/**
 * 按钮（探针 10/10：裸放，不要 action 容器）。
 * ★ 诚实声明：**回执没接住**。ws_daemon 收到 card.action.trigger 只记日志，
 * 不做任何事。所以 value 里带上明确意图，等回调真的接通了再谈交互。
 */
export function button(label, value = {}, type = 'default') {
  return { tag: 'button', text: t(label), type, value };
}

/* ═══════════════════════════ 十类模版 ═══════════════════════════ */

/**
 * 每个构造器都是纯函数：吃一个 data 对象，吐一张卡。
 * 缺字段不抛异常——该出现的位置显示「（未填）」占位，让缺什么在群里看得见，
 * 而不是静默省略（静默省略正是那条「等于没答」的 434 字回复的成因）。
 */
const NA = '（未填）';
const s = (v) => (v === undefined || v === null || v === '' ? NA : String(v));

const card = (template, title, subtitle, elements) => ({
  schema: '2.0',
  config: { update_multi: true },
  header: { title: t(title), ...(subtitle ? { subtitle: t(subtitle) } : {}), template },
  body: { elements },
});

/** 01 问答 · 一问一答，结论在标题里 */
export function queryAnswer(d = {}) {
  const els = [md(s(d.verdict))];
  if (d.reasoning) els.push(md(s(d.reasoning)));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  if (d.evidence?.length) els.push(collapsible(`证据 · ${d.evidence.length} 条`, [s(d.evidence.join('\n'))]));
  if (d.boundary) els.push(hr(), md(`*${s(d.boundary)}*`));
  return card(TONE['query-answer'], s(d.title ?? d.verdict), d.subtitle, els);
}

/** 02 数据 · 行是记录，列是字段 */
export function dataTable(d = {}) {
  const els = [];
  if (d.verdict) els.push(md(s(d.verdict)));
  if (d.columns?.length && d.rows?.length) els.push(table(d.columns, d.rows));
  else els.push(md(`*（没有可列的行 —— 这次查询返回 0 条，不是我没画）*`));
  if (d.note) els.push(md(s(d.note)));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  return card(TONE['query-answer'], s(d.title), d.subtitle, els);
}

/** 03 更正 · 我说错了，第一行就是错在哪 */
export function correction(d = {}) {
  const els = [md(`**错在哪**：${s(d.wrong)}`), md(`**正确的是**：${s(d.right)}`)];
  if (d.cause) els.push(md(`**为什么错**：${s(d.cause)}`));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  if (d.boundary) els.push(hr(), md(`*${s(d.boundary)}*`));
  return card(TONE['correction'], s(d.title ?? '我上一条说错了'), d.subtitle, els);
}

/** 04 能力边界 · 「你能做什么」的固定应答 */
export function capabilityBoundary(d = {}) {
  const els = [md(s(d.verdict ?? '按「能做 / 受限 / 做不到」三栏给，不解释原因。'))];
  const cols = [];
  if (d.can?.length) cols.push({ content: `**能做**\n${d.can.map((x) => `- ${x}`).join('\n')}` });
  if (d.limited?.length) cols.push({ content: `**受限**\n${d.limited.map((x) => `- ${x}`).join('\n')}` });
  if (d.cannot?.length) cols.push({ content: `**做不到**\n${d.cannot.map((x) => `- ${x}`).join('\n')}` });
  if (cols.length) els.push(columns(cols));
  if (d.evidence) els.push(collapsible('依据', [s(d.evidence)]));
  if (d.boundary) els.push(hr(), md(`*${s(d.boundary)}*`));
  return card(TONE['capability-boundary'], s(d.title ?? '我能做什么'), d.subtitle, els);
}

/** 05 没找到 · 「查不到」必须带上查了哪里，否则等于没说 */
export function findNothing(d = {}) {
  const els = [md(`**结论**：没找到。不是「可能没有」，是**在我查过的范围内一条都没有**。`)];
  if (d.paths?.length) {
    els.push(md(`**查过的地方**（${d.paths.length} 处）`));
    els.push(table(['位置', '怎么查的', '结果'], d.paths.map((p) => [p.where, p.how, p.result ?? '0 命中'])));
  }
  if (d.tried) els.push(collapsible('检索动作明细', [s(d.tried)]));
  if (d.nextStep) els.push(md(`**需要你补什么**：${s(d.nextStep)}`));
  if (d.boundary) els.push(hr(), md(`*${s(d.boundary)}*`));
  return card(TONE['find-nothing'], s(d.title ?? '没找到'), d.subtitle, els);
}

/** 06 读不了 · 非文字输入、已撤回、窗口之外 */
export function cannotRead(d = {}) {
  const els = [md(s(d.verdict))];
  if (d.item) {
    els.push(table(['项', '值'], [
      ['类型', s(d.item.kind)],
      ['谁发的', s(d.item.from)],
      ['什么时候', s(d.item.at)],
      ['内容', d.item.content ?? '**取不到**'],
    ]));
  }
  if (d.why) els.push(md(`**为什么**：${s(d.why)}`));
  if (d.alternative) els.push(md(`**你可以**：${s(d.alternative)}`));
  return card(TONE['cannot-read'], s(d.title ?? '这条我读不了'), d.subtitle, els);
}

/** 07 回执 · 只确认，不解释。越短越好 */
export function receipt(d = {}) {
  const els = [md(s(d.verdict ?? '收到了。'))];
  if (d.fields?.length) els.push(fieldRow(d.fields));
  if (d.note) els.push(md(s(d.note)));
  return card(TONE['receipt'], s(d.title ?? '已收到'), d.subtitle, els);
}

/** 08 对比 · 同一问题两次回答不一样时，把差异摆出来 */
export function turnDiff(d = {}) {
  const els = [md(`**差异**：${s(d.verdict)}`)];
  const rows = [];
  if (d.before !== undefined) rows.push(['上一次', s(d.before)]);
  if (d.after !== undefined) rows.push(['这一次', s(d.after)]);
  if (rows.length) els.push(table(['项', '值'], rows));
  if (d.cause) els.push(md(`**为什么变**：${s(d.cause)}`));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  return card(TONE['turn-diff'], s(d.title ?? '跟上一次答得不一样'), d.subtitle, els);
}

/** 09 证据 · 结论很短，证据很长 —— 默认收起 */
export function evidence(d = {}) {
  const els = [];
  if (d.verdict) els.push(md(s(d.verdict)));
  const groups = d.groups?.length ? d.groups : [{ title: '证据', content: s(d.content) }];
  for (const g of groups) {
    els.push(collapsible(`${g.title} · ${g.count ?? ''}`.trim(), [s(g.content)], g.expanded ?? false));
  }
  if (d.fields?.length) els.push(fieldRow(d.fields));
  if (d.boundary) els.push(hr(), md(`*${s(d.boundary)}*`));
  return card(TONE['evidence'], s(d.title ?? '证据'), d.subtitle, els);
}

/** 10 告警 · 我这侧坏了。绝不允许把内部记录当内容发出去 */
export function alert(d = {}) {
  // what 给默认值，理由和 impact 一样：`envelope.mjs` 发现 what 里写了工具名时
  // 会把它整段搬进 internal（那正是我们要的），搬完 what 就空了。
  // 不给默认值的话，群里会出现一张「发生了什么：（未填）」的卡 ——
  // 把内部记录拦住，却把话说成半句，等于换了一种坏法。
  const els = [md(`**发生了什么**：${s(d.what ?? '刚才那条回复是故障输出，等于没答。')}`)];
  els.push(md(`**对你有什么影响**：${s(d.impact ?? '这次的问题没答上。')}`));
  if (d.internal) els.push(collapsible('内部详情（排查用）', [s(d.internal)]));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  if (d.retry) els.push(md(`**你可以**：${s(d.retry)}`));
  return card(TONE['alert'], s(d.title ?? '我这侧出故障了'), d.subtitle, els);
}

/** 11 征询 · 要你做决定。一次只问一件（AGENTS.md 第一节就是这条） */
export function decision(d = {}) {
  const els = [md(`**要你定的事**：${s(d.ask)}`)];
  if (d.options?.length) {
    els.push(table(['选项', '代价 / 影响'], d.options.map((o) => [o.label, o.cost ?? '—'])));
  }
  if (d.recommend) els.push(md(`**我的建议**：${s(d.recommend)}`));
  if (d.fields?.length) els.push(fieldRow(d.fields));
  return card(TONE['decision'], s(d.title ?? '有一件事要你定'), d.subtitle, els);
}

/* ═══════════════════════════ 校验器 ═══════════════════════════ */

/**
 * 本地校验：飞书要发的卡片，先在这里过一遍。
 *
 * 为什么必须本地做：`cardkit.v1.card.create`（官方的卡片校验入口）被权限挡住 ——
 * 实测 code=99991672，缺 `cardkit:card:write` scope，而且它的权限检查在 schema
 * 校验**之前**，所以拿不到 schema 诊断（2026-09-18 实测三种卡片，一律同一个权限错）。
 * 在拿到那个 scope 之前，本地白名单是唯一能提前拦住「整卡被拒 = 回复丢失」的闸。
 *
 * @returns {{ok:boolean, errors:Array<{path:string,msg:string}>, warnings:Array}}
 */
export function validateCard(c) {
  const errors = [];
  const warnings = [];
  const E = (p, m) => errors.push({ path: p, msg: m });
  const W = (p, m) => warnings.push({ path: p, msg: m });

  if (!c || typeof c !== 'object') return { ok: false, errors: [{ path: '', msg: '不是对象' }], warnings };
  if (c.schema !== '2.0') E('schema', `必须是 '2.0'（现在是 ${JSON.stringify(c.schema)}）`);
  if (!c.config) W('config', '缺 config；建议 { update_multi: true } 以便后续原地更新');
  if (!c.header?.title?.content) E('header.title.content', '缺卡片标题');

  const tpl = c.header?.template;
  if (tpl !== undefined && !TEMPLATES.includes(tpl)) {
    E('header.template', `未知配色 ${JSON.stringify(tpl)}；实测可用：${TEMPLATES.join(', ')}`);
  }
  if (c.header?.title?.tag && c.header.title.tag !== 'plain_text') {
    // 实测：header.title 只吃 plain_text。用 markdown 会整卡被拒。
    E('header.title.tag', `header 的 title/subtitle 只接受 plain_text，收到 ${c.header.title.tag}`);
  }
  if (!Array.isArray(c.body?.elements)) {
    E('body.elements', '缺 body.elements（V2 的正文在 body 下，不是顶层 elements）');
    return { ok: errors.length === 0, errors, warnings };
  }

  const walk = (els, p) => {
    if (!Array.isArray(els)) { E(p, '应为数组'); return; }
    els.forEach((el, i) => {
      const q = `${p}[${i}]`;
      if (!el || typeof el !== 'object') { E(q, '不是对象'); return; }
      const tag = el.tag;
      if (!tag) { E(q, '缺 tag'); return; }
      if (REMOVED_IN_V2[tag]) { E(`${q}.tag`, `V2 已移除该元素：${REMOVED_IN_V2[tag]}`); return; }
      if (!ALLOWED_TAGS.has(tag)) { E(`${q}.tag`, `不在实测白名单里：${tag}。白名单：${[...ALLOWED_TAGS].join(', ')}`); return; }

      if (tag === 'markdown' && typeof el.content !== 'string') E(`${q}.content`, 'markdown 的 content 必须是字符串');
      if (tag === 'collapsible_panel') {
        if (!el.header?.title?.content) E(`${q}.header.title`, '折叠面板缺标题');
        if (!Array.isArray(el.elements)) E(`${q}.elements`, '折叠面板缺 elements');
        else walk(el.elements, `${q}.elements`);
      }
      if (tag === 'column_set') {
        if (!Array.isArray(el.columns) || el.columns.length === 0) E(`${q}.columns`, 'column_set 缺 columns');
        else el.columns.forEach((col, j) => {
          if (col.tag !== 'column') E(`${q}.columns[${j}].tag`, `column_set 的下级必须是 column，收到 ${col.tag}`);
          if (!Array.isArray(col.elements)) E(`${q}.columns[${j}].elements`, 'column 缺 elements');
          else walk(col.elements, `${q}.columns[${j}].elements`);
        });
        if (el.columns?.length > 4) W(`${q}.columns`, `${el.columns.length} 栏，手机上会挤；建议 ≤3`);
      }
      if (tag === 'table') {
        if (!Array.isArray(el.columns) || !el.columns.length) E(`${q}.columns`, 'table 缺 columns');
        if (!Array.isArray(el.rows)) E(`${q}.rows`, 'table 的 rows 必须是数组');
        else {
          const names = new Set((el.columns ?? []).map((x) => x.name));
          el.rows.forEach((r, j) => {
            if (Array.isArray(r)) E(`${q}.rows[${j}]`, 'rows 的每一项必须是对象 {列名: 值}；传数组会被服务端拒绝');
            else for (const k of Object.keys(r)) if (!names.has(k)) E(`${q}.rows[${j}].${k}`, `列名 ${k} 不在 columns 里（${[...names].join('/')}）`);
          });
        }
        if (el.rows?.length > 30) W(`${q}.rows`, `${el.rows.length} 行，群消息里过长；建议拆卡或折叠`);
      }
      if (tag === 'button') {
        if (el.text?.tag !== 'plain_text') E(`${q}.text`, '按钮文字必须是 { tag: "plain_text", content }');
        // 探针 7/7 的实测：包一层 action 会被整卡拒绝，所以这里明确要求裸放
        W(`${q}`, '按钮回调在 ws_daemon 里只记日志、未接住（诚实声明，别让模版假装能交互）');
      }
    });
  };
  walk(c.body.elements, 'body.elements');
  return { ok: errors.length === 0, errors, warnings };
}

/** 构建 + 校验，一步到位。校验不过直接抛，别把坏卡发出去。 */
export function build(kind, data) {
  const fn = BUILDERS[kind];
  if (!fn) throw new Error(`未知卡片类型：${kind}；可选：${Object.keys(BUILDERS).join(', ')}`);
  const c = fn(data);
  const v = validateCard(c);
  if (!v.ok) {
    const msg = v.errors.map((e) => `  ${e.path}: ${e.msg}`).join('\n');
    throw new Error(`卡片 ${kind} 校验不过（共 ${v.errors.length} 处）：\n${msg}`);
  }
  return c;
}

/** 类型 → 构造器。键名同时是 CLI 的 --type 取值。 */
export const BUILDERS = {
  'query-answer': queryAnswer,
  'data-table': dataTable,
  'correction': correction,
  'capability-boundary': capabilityBoundary,
  'find-nothing': findNothing,
  'cannot-read': cannotRead,
  'receipt': receipt,
  'turn-diff': turnDiff,
  'evidence': evidence,
  'alert': alert,
  'decision': decision,
};

/** 构建器名 → 源文件里的函数名，verify_cards 用它核对登记表没写错 */
export const BUILDER_SOURCE_NAME = {
  'query-answer': 'queryAnswer',
  'data-table': 'dataTable',
  'correction': 'correction',
  'capability-boundary': 'capabilityBoundary',
  'find-nothing': 'findNothing',
  'cannot-read': 'cannotRead',
  'receipt': 'receipt',
  'turn-diff': 'turnDiff',
  'evidence': 'evidence',
  'alert': 'alert',
  'decision': 'decision',
};

export const __dirname = path.dirname(new URL(import.meta.url).pathname);
export const readSelf = () => fs.readFileSync(path.join(__dirname, 'cards.mjs'), 'utf8');
