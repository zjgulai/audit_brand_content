/**
 * audit_modality_specs.mjs —— 图片 / 文案 / 视频三种送审的**唯一**卡片模版规格表
 *
 * ── 这个文件解决什么问题 ────────────────────────────────────────────────
 * 三种模态的四维体检、明细表列名、可复制替换件、下一步措辞、覆盖边界，
 * 原先分别写死在 `prd53.mjs` 与 `standard_cards.mjs` 两个构建器里，各一份。
 * 于是视频被渲染成图片的四维（「对表改图」出现在视频卡上），文案要么被模型
 * 自由发挥，要么退化成一张字面命中表，边界栏还被塞进一句关于品线的话。
 *
 * 现在差异只在这张表里。两个构建器都**遍历**它，不再各自手写字符串：
 * 改一个维度名只改一处，改漏了由模块加载断言与 `verify_cards.mjs` 的 K 段抓住。
 *
 * ── 为什么是纯数据 + 纯函数 ─────────────────────────────────────────────
 * 它不 import 任何构建器（`prd53` 与 `standard_cards` 之间会因为互相 import 成环），
 * 也不 import 卡片层 —— `prd53.mjs` 受 `verify_cards.mjs` L5 约束（内核不许碰卡片）。
 */
import fs from 'node:fs';
import path from 'node:path';

const THREE = ['①', '②', '③', '④'];

const FOUR = (rows) => Object.freeze(rows.map((r, i) => Object.freeze({ no: THREE[i], ...r })));

const COLUMN_NAMES = 'region,issue,fix';

/* ═══════════════════════════ 规格表 ═══════════════════════════ */

export const AUDIT_MODALITY_SPECS = Object.freeze({
  image: Object.freeze({
    key: 'image',
    cardNoun: '图片审查',
    receiptNoun: '图片',
    checklistHeading: '【四维快速体检】',
    dimensions: FOUR([
      { name: '图内文字（OCR）', field: 'ocr_summary', statusField: 'ocr_status', empty: '未见明显违规宣传词' },
      { name: '画面语义', field: 'scene_semantics', statusField: 'scene_status', empty: '常规产品展示场景' },
      { name: '视觉符号', field: 'visual_symbols', statusField: 'symbol_status', empty: '未见异常认证图标或高危符号' },
    ]),
    tableHeading: '【④ 区域级画面审计（对表改图）】',
    columns: Object.freeze([
      Object.freeze({ name: 'region', display_name: '画面位置' }),
      Object.freeze({ name: 'issue', display_name: '发现的问题' }),
      Object.freeze({ name: 'fix', display_name: '直接怎么改' }),
    ]),
    emptyRow: Object.freeze(['全图', '未见明显局部违规', '转工作台人工复核']),
    snippetLabel: '【可直接复制给设计的合规免责贴条】',
    nextStep: Object.freeze({ rework: '改图后重审', escalate: '转工作台人工复核' }),
    tags: Object.freeze({ block: '需修改', pass: '初筛通过', review: '需人工确认' }),
    showProductLine: false,
    boundary: '已覆盖：图内文字(OCR) · 画面语义 · 视觉符号 · 区域级画面审计',
    // 判别性词表：只放**这一个模态独有**的说法，用于出站边界闸。
    // 「OCR」「字幕」这类跨模态共有的词不能进来 —— 否则闸会把自己合法的一行删掉。
    discriminators: Object.freeze(['画面语义', '视觉符号', '区域级画面审计', '对表改图', '改图后重审', '只覆盖图内文字']),
  }),

  text: Object.freeze({
    key: 'text',
    cardNoun: '文案审查',
    receiptNoun: '文案',
    checklistHeading: '【文案四维体检】',
    dimensions: FOUR([
      { name: '字面红线与医疗禁用词', field: 'literal_summary', statusField: 'literal_status', empty: '未命中已知字面禁用与医疗红线词' },
      { name: '功效与安全宣称', field: 'claim_summary', statusField: 'claim_status', empty: '未见明显夸大功效或安全承诺表述' },
      { name: '品线与平台特殊规范', field: 'platform_summary', statusField: 'platform_status', empty: '未触及平台特殊条款' },
    ]),
    // 文案与图片共用同一组字段名（python 侧会同时写 ocr_* / scene_* / symbol_*），
    // 于是老数据照样渲染得出，不必为两种键名各写一条分支。
    aliasFields: Object.freeze([
      { field: 'ocr_summary', statusField: 'ocr_status' },
      { field: 'scene_semantics', statusField: 'scene_status' },
      { field: 'visual_symbols', statusField: 'symbol_status' },
    ]),
    tableHeading: '【④ 问题位置与改法（对表改字）】',
    columns: Object.freeze([
      Object.freeze({ name: 'region', display_name: '段落 / 位置' }),
      Object.freeze({ name: 'issue', display_name: '命中的原句与问题' }),
      Object.freeze({ name: 'fix', display_name: '建议替换写法' }),
    ]),
    emptyRow: Object.freeze(['全文扫描', '未命中已知字面违规词', '转工作台人工复核语境后放行']),
    snippetLabel: '【可直接复制的合规替换文案 / 免责贴条】',
    nextStep: Object.freeze({ rework: '改词后重审', escalate: '转工作台人工复核' }),
    tags: Object.freeze({ block: '需修改', pass: '初筛未见违规', review: '需人工确认' }),
    showProductLine: true,
    boundary: '已覆盖：字面红线词 · 功效与安全宣称 · 品线与平台规范 · 法规条款核验（纯文本送审，不含配图与视频）',
    discriminators: Object.freeze(['字面红线', '功效与安全宣称', '品线与平台规范', '对表改字', '替换文案']),
  }),

  video: Object.freeze({
    key: 'video',
    cardNoun: '视频审查',
    receiptNoun: '视频',
    checklistHeading: '【视频四维体检】',
    dimensions: FOUR([
      { name: '画面字幕与花字（OCR）', field: 'ocr_summary', statusField: 'ocr_status', empty: '未读出违规字幕' },
      { name: '口播人声与音频宣称（ASR）', field: 'scene_semantics', statusField: 'scene_status', empty: '口播未读出违规宣称' },
      { name: '音画一致性与动作演示', field: 'visual_symbols', statusField: 'symbol_status', empty: '音画一致，未见危险动作' },
    ]),
    tableHeading: '【④ 时间轴问题定位（对表剪片）】',
    columns: Object.freeze([
      Object.freeze({ name: 'region', display_name: '时间段（秒）' }),
      Object.freeze({ name: 'issue', display_name: '画面 / 口播问题' }),
      Object.freeze({ name: 'fix', display_name: '直接怎么剪 / 改' }),
    ]),
    emptyRow: Object.freeze(['全片', '未见明显局部违规', '转工作台人工复核']),
    snippetLabel: '【可直接复制给剪辑师的合规免责字幕 / 替换口播词】',
    nextStep: Object.freeze({ rework: '剪片后重审', escalate: '转工作台人工复核' }),
    tags: Object.freeze({ block: '需修改', pass: '初筛未见违规', review: '需人工确认' }),
    showProductLine: true,
    boundary: '已覆盖：画面字幕(OCR) · 口播语音(ASR) · 音画一致性 · 时间轴分段审计',
    discriminators: Object.freeze(['音画一致', '时间轴', '对表剪片', '口播词', 'ASR', '剪片后重审']),
  }),
});

/** 模态别名：文案在部分上游字段里叫 `copy`。 */
const ALIASES = Object.freeze({ copy: 'text', ad_text: 'text', free_text: 'text', feishu_doc: 'text', landing_url: 'text', structured_json: 'text' });

/**
 * 从入站结果解出领域模态。纯函数，失败**关闭**（返回 null），不许回落成图片。
 *
 * 判据按可信度排序：
 *   1. 显式 `audit_modality` / `carrier`（python 侧已判定过的领域词汇）
 *   2. `four_dim_audit.media_kind`
 *   3. 飞书线上词汇 `type`（'image'）与 `reason` 前缀
 * 全不中 → null。`type: 'media'` 刻意**不**当作视频：`media` 同时涵盖视频与音频。
 */
export function resolveModality(input) {
  if (typeof input === 'string') {
    const k = ALIASES[input] ?? input;
    return AUDIT_MODALITY_SPECS[k] ? k : null;
  }
  if (!input || typeof input !== 'object') return null;

  const direct = input.audit_modality ?? input.carrier;
  if (typeof direct === 'string') {
    const k = ALIASES[direct] ?? direct;
    if (AUDIT_MODALITY_SPECS[k]) return k;
  }
  const mk = input.four_dim_audit?.media_kind;
  if (typeof mk === 'string') {
    const k = ALIASES[mk] ?? mk;
    if (AUDIT_MODALITY_SPECS[k]) return k;
  }
  if (input.type === 'image') return 'image';
  const r = String(input.reason ?? '');
  if (r.startsWith('video_')) return 'video';
  if (r.startsWith('image_')) return 'image';
  return null;
}

export const specFor = (input) => AUDIT_MODALITY_SPECS[resolveModality(input) ?? ''] ?? null;

/** 某个模态的「外来说法」= 其余模态全部判别词。出站闸用它，不手写第二份列表。 */
export function foreignTokensFor(key) {
  const spec = AUDIT_MODALITY_SPECS[key];
  if (!spec) return [];
  return Object.values(AUDIT_MODALITY_SPECS)
    .filter((s) => s.key !== spec.key)
    .flatMap((s) => [...s.discriminators]);
}

/* ═══════════════════════════ 渲染 ═══════════════════════════ */

const asText = (x) => (x === null || x === undefined ? '' : String(x).trim());
const IDENTITY = (x) => asText(x);

function badgeOf(fd, statusField, clean) {
  const v = asText(fd?.[statusField]);
  return v ? `【${clean(v)}】` : '';
}

function dimBody(fd, dim, alias, clean) {
  const fromAlias = alias ? asText(fd?.[alias.field]) : '';
  const own = asText(fd?.[dim.field]);
  return clean(own || fromAlias || dim.empty);
}

function kbLineOf(evChain) {
  if (evChain === undefined) return null;
  if (evChain === null) return '· 知识库检索：由本机 19 项控制点与外部法规库核验';
  if (evChain.status === 'found' && evChain.evidence?.[0]) {
    return `· 知识库依据：命中规则文档 ${evChain.evidence[0].docId}（请求号 ${evChain.evidence[0].requestId || '已记账'}）`;
  }
  return `· 知识库检索：${evChain.status ? `状态=${evChain.status}` : '由本机 19 项控制点与外部法规库核验'}`;
}

/**
 * 文案没有 `four_dim_audit` 时的**兜底**四维（python 正常路径总会给出，
 * 这里只防手工构造的输入把卡片打成半张）。
 */
function fallbackTextFd({ findings, productLine, productLineNote }) {
  const rows = Array.isArray(findings) ? findings : [];
  const quotes = rows.slice(0, 3).map((f) => `「${asText(f?.quote)}」`).filter((s) => s !== '「」');
  const total = rows.length;
  return {
    media_kind: 'text',
    overall: total ? '发现违规需修改' : '需人工确认',
    short_title: total ? `命中 ${total} 处字面红线` : '未命中已知字面红线词',
    one_line: total
      ? `文案含 ${quotes.join('、') || '已知禁用表述'} 等 ${total} 处风险，需修改后再投放。`
      : '未命中已知字面禁用语，请人工确认语境（空命中不等于合规）。',
    quick_fix: total
      ? `删掉或替换 ${quotes.join('、') || '命中的表述'}，改为客观功能描述并补充实测条件说明。`
      : '字面规则未命中不等于合规，转工作台人工复核语境。',
    literal_status: total ? '有风险' : '正常',
    literal_summary: total
      ? `命中 ${rows.map((f) => asText(f?.control_code) || '规则').filter(Boolean).join('、')}：${quotes.join('、')}`
      : '未命中已知字面禁用与医疗红线词',
    claim_status: '正常',
    claim_summary: '未见明显夸大功效或安全承诺表述',
    platform_status: '正常',
    platform_summary: productLineNote || `按「${productLine || '通用'}」品线规范核验，未触及特殊条款`,
    region_rows: total
      ? rows.slice(0, 5).map((f, i) => ({
        region: `第 ${i + 1} 处`,
        issue: `命中「${asText(f?.quote)}」（${asText(f?.control_code) || '规则'}）`,
        fix: `删掉「${asText(f?.quote)}」或改为客观事实描述`,
      }))
      : [{ region: '全文扫描', issue: '未命中已知字面违规词', fix: '转工作台人工复核语境后放行' }],
    copy_paste_snippet: total
      ? '本产品为日常护理用品，非医疗器械，不能替代诊断或治疗；个体体验存在差异，请按说明书使用。'
      : '（本次未命中字面红线词，无需替换件；如要补免责说明，可用：本产品为日常护理用品，非医疗器械。）',
  };
}

/**
 * 把一份 `four_dim_audit` 渲染成三种构建器共用的卡片数据。
 *
 * @param {object} p
 * @param {string} p.modality  'image' | 'text' | 'video'（'copy' 视同 text）
 * @param {object|null} p.fd   生产侧的四维结果
 * @param {string} p.label     五标签
 * @param {string|null} p.caseId
 * @param {string|null} p.productLine
 * @param {string|null} p.productLineNote
 * @param {object|undefined} p.evChain  证据链；`undefined` = 不适用（不出一行），`null` = 取不到
 * @param {Array} p.findings
 * @param {(x:any)=>string} p.cleanFn
 * @returns {object|null}
 */
export function renderFourDimAuditPayload({
  modality,
  fd = null,
  label = 'REVIEW',
  caseId = null,
  productLine = null,
  productLineNote = null,
  evChain,
  findings = [],
  cleanFn = IDENTITY,
} = {}) {
  const spec = AUDIT_MODALITY_SPECS[ALIASES[modality] ?? modality];
  if (!spec) return null;
  const clean = typeof cleanFn === 'function' ? cleanFn : IDENTITY;

  let data = fd && typeof fd === 'object' ? fd : null;
  if (!data && spec.key === 'text') data = fallbackTextFd({ findings, productLine, productLineNote });
  if (!data) return null;

  const overall = clean(data.overall || HUMAN_LABEL[label] || '需人工确认');
  const isBlock = overall.includes('修改') || overall.includes('违规');
  const isPass = overall.includes('未见') && !overall.includes('确认');
  const tone = isBlock ? 'red' : (isPass ? 'green' : 'orange');
  const tagLabel = isBlock ? spec.tags.block : (isPass ? spec.tags.pass : spec.tags.review);

  const oneLine = clean(data.one_line || overall);
  const shortTitle = asText(data.short_title) ? clean(data.short_title).slice(0, 18) : oneLine.slice(0, 18);
  const quickFix = clean(data.quick_fix || data.action_advice || `请按下方${spec.key === 'video' ? '时间轴' : '明细'}表格修改后重审`);

  const aliasPerDim = spec.aliasFields ?? [];
  const dimLines = spec.dimensions.map((d, i) => {
    const badge = badgeOf(data, d.statusField, clean);
    return `· ${d.no} ${d.name}${badge}：${dimBody(data, d, aliasPerDim[i], clean)}`;
  });
  const kbLine = kbLineOf(evChain);

  const reasoning = [
    `【马上怎么改】${quickFix}`,
    '',
    spec.checklistHeading,
    ...dimLines,
    ...(kbLine ? [kbLine] : []),
    '',
    spec.tableHeading,
  ].join('\n');

  const rawRows = Array.isArray(data.region_rows) ? data.region_rows.filter((r) => r && (r.region || r.issue))
    : (Array.isArray(data.region_audit) ? data.region_audit.map((line) => {
      const [left, ...rest] = String(line).split(/[：:]/);
      return { region: (left || '').trim(), issue: rest.join('：').trim() || String(line), fix: quickFix.slice(0, 24) };
    }) : []);
  const rows = rawRows.length
    ? rawRows.map((r) => [
      clean(r.region || spec.columns[0].display_name),
      clean(r.issue || '—'),
      clean(r.fix || '—'),
    ])
    : [spec.emptyRow.map((c, i) => (i === 2 ? clean(c) : c))];

  const fields = [{ label: '审查结论', value: overall }];
  if (spec.showProductLine) {
    const pl = asText(productLine);
    fields.push({
      label: '识别品线',
      value: pl ? clean(pl) : clean(productLineNote || '未能识别（按通用规则审查）'),
    });
  }
  fields.push({ label: '下一步', value: isBlock ? spec.nextStep.rework : spec.nextStep.escalate });
  if (caseId) fields.push({ label: '工作台单号', value: caseId });

  const snippet = asText(data.copy_paste_snippet);

  return {
    audit_modality: spec.key,
    tone,
    title: `【${spec.cardNoun} · ${tagLabel}】${shortTitle}`,
    verdict: `【核心卡点】${oneLine}`.slice(0, 58),
    reasoning,
    columns: spec.columns.map((c) => ({ name: c.name, display_name: c.display_name, data_type: 'text' })),
    rows,
    ...(snippet ? { snippet: clean(snippet), snippetLabel: spec.snippetLabel } : {}),
    fields,
    boundary: spec.boundary,
  };
}

const HUMAN_LABEL = Object.freeze({
  BLOCK: '发现违规需修改',
  REVIEW: '需人工确认',
  待自决: '需人工确认',
  PASS: '初筛未见违规',
  'PASS+SUGGEST': '初筛未见违规（附优化建议）',
  未审查: '素材未能读取',
});

/* ═══════════════════════════ 模块加载断言 ═══════════════════════════
 * 一个会误报的检查器比没有检查器更糟，而这张表是那道出站边界闸的**唯一**判据：
 * 判别词一旦在两个模态之间重叠，闸就会把本模态合法的自己人删掉。
 * 所以这几条不是洁癖，是那道闸的前提条件。
 */
{
  const entries = Object.entries(AUDIT_MODALITY_SPECS);
  const fail = (msg) => { throw new Error(`audit_modality_specs 不变式失败：${msg}`); };

  if (entries.length !== 3) fail(`应有 3 个模态，实际 ${entries.length}`);
  for (const [k, s] of entries) {
    if (s.key !== k) fail(`${k} 的 key 字段是 ${s.key}`);
    if (s.dimensions.length !== 3) fail(`${k} 应有 3 个正文维度 + 1 个表格维度`);
    if (s.dimensions.map((d) => d.no).join('') !== '①②③') fail(`${k} 的维度编号不是 ①②③`);
    if (s.columns.map((c) => c.name).join(',') !== COLUMN_NAMES) fail(`${k} 的列名不是 ${COLUMN_NAMES}`);
    if (!s.checklistHeading || !s.tableHeading) fail(`${k} 缺标题`);
    if (!s.snippetLabel) fail(`${k} 缺替换件小标题`);
    if (!s.nextStep?.rework || !s.nextStep?.escalate) fail(`${k} 缺下一步措辞`);
    if ([...s.boundary].length > 85) fail(`${k} 的边界句 ${[...s.boundary].length} 字，超过 85（BOUNDARY_MAX=90 要留余量）`);
    if (!s.boundary.startsWith('已覆盖：')) fail(`${k} 的边界句必须以「已覆盖：」开头`);
  }

  const all = entries.flatMap(([, s]) => [...s.discriminators]);
  const dup = all.filter((t, i) => all.indexOf(t) !== i);
  if (dup.length) fail(`判别词跨模态重叠：${[...new Set(dup)].join('、')} —— 出站闸会把合法行删掉`);

  // 每个模态的边界句必须**含**自己的维度说法，且**不含**别人的判别词。
  for (const [, s] of entries) {
    const foreign = Object.values(AUDIT_MODALITY_SPECS)
      .filter((o) => o.key !== s.key)
      .flatMap((o) => [...o.discriminators])
      .filter((t) => s.boundary.includes(t));
    if (foreign.length) fail(`${s.key} 的边界句里混进了别模态的说法：${foreign.join('、')}`);
  }
}

/** 供自证用的常量转出（避免测试自己再写一份字符串）。 */
export const MODALITY_KEYS = Object.freeze(Object.keys(AUDIT_MODALITY_SPECS));
export const __dirname = path.dirname(new URL(import.meta.url).pathname);
export const readSelf = () => fs.readFileSync(path.join(__dirname, 'audit_modality_specs.mjs'), 'utf8');
