#!/usr/bin/env node
/**
 * golden_56_replay.test.mjs —— 2026-11-05 那 56 条真实送审的回归锚点
 *
 * ── 这个文件守的是什么
 *
 * 2026-11-05 群里连着送审了 56 条素材（图片、文案、视频、Office 文档），
 * 当天暴露了六处失真，根因都写在 `WBPM-0158` 里。修完之后这批素材就散在原地了 ——
 * 知识库、规则库、卡片模版任何一处再动一下，**没有任何东西会发现它们变了**。
 *
 * 所以这里把 56 条整理成一份可以逐条回放的样本：
 * 每一条都写明它该落到哪个模态、抬头该带哪个五标签、品类显示对不对、
 * 以及卡片里**不许**出现别的模态的说法。改坏了就红，红在哪一条一眼看得见。
 *
 * ── 刻意不做什么
 *
 *   · 不联网、不调生产判定、不读凭据。这里的 `four_dim_audit` 是从当天真实读数
 *     摘出来的**固定样本**，不是重新跑一遍判定 —— 判定的回归在
 *     `feishu_guard_ingest.test.mjs` 与 `image_judgment.test.mjs`。
 *     本文件管的是**渲染这一跳**：同样的判定结果，卡片说对了没有。
 *   · 不碰真实状态目录（`SHOUHENG_STATE_DIR` 不需要改：这里不写任何盘）。
 *
 * 用法：
 *   node tools/agent/golden_56_replay.test.mjs                # 人读
 *   node tools/agent/golden_56_replay.test.mjs --json-summary # 机器读（56/56）
 *
 * 退出码：0 全过 ｜ 1 有红
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const JSON_SUMMARY = process.argv.includes('--json-summary');

const cardsMod = await import(path.join(HERE, '..', 'reply-cards', 'cards.mjs'));
const plainMod = await import(path.join(HERE, 'plain.mjs'));
const prd53 = await import(path.join(HERE, 'prd53.mjs'));
const std = await import(path.join(HERE, 'standard_cards.mjs'));
const specs = await import(path.join(HERE, 'audit_modality_specs.mjs'));
const envMod = await import(path.join(HERE, '..', 'reply-cards', 'envelope.mjs'));

/* ══════════════ 一、四维样本（当天真实读数的固定副本） ══════════════ */

const PASS_BODY = {
  overall: '初筛未见明显违规',
  literal_status: '正常', literal_summary: '未命中已知字面禁用与医疗红线词',
  ocr_status: '正常', ocr_summary: '画面文字为产品名与容量标注，未见功效承诺',
  claim_status: '未见风险', claim_summary: '未出现医疗级、治疗或奶量倍增类表述',
  scene_status: '正常', scene_semantics: '常规产品静物展示，人物为日常使用场景',
  platform_status: '正常', platform_summary: '未出现绝对化比较或未标明条件的性能数字',
  symbol_status: '正常', visual_symbols: '未见认证徽章、奖项或医疗机构标识',
  region_rows: [],
  copy_paste_snippet: '（本品为日常护理用品，非医疗器械，个体体验存在差异。）',
};

const BLOCK_FEVER = {
  overall: '发现违规需修改',
  literal_status: '有风险', literal_summary: '出现「104.41°F」高烧数值',
  ocr_status: '有风险', ocr_summary: '画面叠加「104.41°F」「High Fever Alert」字样',
  claim_status: '有风险', claim_summary: '以高烧数值暗示可替代医疗监测',
  scene_status: '需注意', scene_semantics: '婴儿床旁设备屏幕显示体温读数',
  platform_status: '需注意', platform_summary: '婴儿监护仪类目：禁止以医疗监测数据作为卖点',
  symbol_status: '需注意', visual_symbols: '体温计图标与警示图标叠加',
  region_rows: [
    { region: '画面右上 · 屏幕区', issue: '显示 104.41°F 高烧数值', fix: '删除体温数值与警示图标，只保留产品外观' },
    { region: '画面下方 · 字幕条', issue: 'High Fever Alert 文案', fix: '改为睡眠看护等非医疗功能描述' },
  ],
  copy_paste_snippet: '（本品为日常看护用品，非医疗器械，不能替代诊断或治疗。）',
};

const BLOCK_COUGH = {
  overall: '发现违规需修改',
  literal_status: '有风险', literal_summary: '出现「Cough / 咳」症状图标',
  ocr_status: '有风险', ocr_summary: '图标区出现 Cough 文字与咳嗽示意图标',
  claim_status: '有风险', claim_summary: '以症状识别作为卖点，属医疗功能宣称',
  scene_status: '需注意', scene_semantics: '设备界面列出多种症状名称',
  platform_status: '需注意', platform_summary: '婴儿监护仪类目：症状识别属医疗功能',
  symbol_status: '需注意', visual_symbols: '症状图标组',
  region_rows: [{ region: '画面中部 · 图标组', issue: 'Cough 症状图标', fix: '整组移除症状识别图标' }],
  copy_paste_snippet: '（本品为日常看护用品，非医疗器械，不能替代诊断或治疗。）',
};

const BLOCK_VITALS = {
  overall: '发现违规需修改',
  literal_status: '有风险', literal_summary: '出现「Heart Rate / Breathing」监测字样',
  ocr_status: '有风险', ocr_summary: '界面显示 Heart Rate 与 Breathing 读数',
  claim_status: '有风险', claim_summary: '心率与呼吸监测属医疗监测功能',
  scene_status: '需注意', scene_semantics: '屏幕显示生命体征曲线',
  platform_status: '需注意', platform_summary: '婴儿监护仪类目：禁止生命体征监测宣称',
  symbol_status: '需注意', visual_symbols: '心电波形图标',
  region_rows: [{ region: '画面屏幕区', issue: 'Heart Rate / Breathing 读数', fix: '移除生命体征读数与曲线' }],
  copy_paste_snippet: '（本品为日常看护用品，非医疗器械，不能替代诊断或治疗。）',
};

const REVIEW_TEMP_SENSING = {
  overall: '需人工确认',
  literal_status: '正常', literal_summary: '未命中字面禁用词',
  ocr_status: '需注意', ocr_summary: '出现「TEMP-SENSING」字样',
  claim_status: '需注意', claim_summary: '温度感知功能需核对检测报告后再对外表述',
  scene_status: '正常', scene_semantics: '产品特写，可见温感探头',
  platform_status: '需注意', platform_summary: '功能宣称须可测，需核对检测报告',
  symbol_status: '正常', visual_symbols: '未见认证徽章',
  region_rows: [{ region: '画面下方 · 标签条', issue: 'TEMP-SENSING 宣称', fix: '补充检测报告依据或改为客观描述' }],
  copy_paste_snippet: '（温度感知为产品功能名称，具体精度以检测报告为准。）',
};

const REVIEW_37C = {
  overall: '需人工确认',
  literal_status: '正常', literal_summary: '未命中字面禁用词',
  ocr_status: '需注意', ocr_summary: '屏幕显示「37℃」',
  claim_status: '需注意', claim_summary: '体温读数需核对是否属医疗监测表述',
  scene_status: '正常', scene_semantics: '产品屏幕特写',
  platform_status: '需注意', platform_summary: '体温显示须可测且不得暗示诊断',
  symbol_status: '正常', visual_symbols: '未见认证徽章',
  region_rows: [{ region: '画面屏幕区', issue: '37℃ 显示', fix: '确认是否为环境温度，并加注非医疗用途' }],
  copy_paste_snippet: '（显示数值为环境温度参考，不作医疗诊断依据。）',
};

const REVIEW_MILD_SAFE = {
  overall: '需人工确认',
  literal_status: '正常', literal_summary: '未命中字面禁用词',
  ocr_status: '需注意', ocr_summary: '出现「Mild & Safe」字样',
  claim_status: '需注意', claim_summary: '安全类表述属绝对化，需可测依据',
  scene_status: '正常', scene_semantics: '产品与婴儿同框',
  platform_status: '需注意', platform_summary: '安全宣称须有检测报告',
  symbol_status: '正常', visual_symbols: '未见认证徽章',
  region_rows: [{ region: '画面标题区', issue: 'Mild & Safe 宣称', fix: '改为客观材质描述并附检测依据' }],
  copy_paste_snippet: '（材质通过 XX 检测，具体报告编号见包装。）',
};

const REVIEW_NIPPLE_TOOL = {
  overall: '需人工确认',
  literal_status: '正常', literal_summary: '未命中字面禁用词',
  ocr_status: '正常', ocr_summary: '出现「NIPPLE MEASURE TOOL」字样',
  claim_status: '需注意', claim_summary: '量具类描述需核对是否涉及医疗用途',
  scene_status: '正常', scene_semantics: '量具与配件平铺展示',
  platform_status: '需注意', platform_summary: '需说明非医疗器械用途',
  symbol_status: '正常', visual_symbols: '未见认证徽章',
  region_rows: [{ region: '画面左侧 · 产品名', issue: 'NIPPLE MEASURE TOOL', fix: '加注非医疗用途说明' }],
  copy_paste_snippet: '（本品为日常护理辅助工具，非医疗器械。）',
};

const UNREVIEWED_IMAGE = {
  status: 'failed', one_line: '', overall: '', region_rows: [],
};

/**
 * 把样本补齐成**生产侧真实传给构建器的形状**。三件事，逐条都有来由：
 *
 *   · `label` 落在 `judgment` 里 —— `ingestAttachment` 走的是
 *     `judgment: compactJudgment(judged.judgment)`，构建器读 `mediaGot.judgment.label`。
 *     放在顶层构建器读不到，卡片会给一个默认 REVIEW，而样本表里写着别的期望值。
 *   · 文案类样本带品线 —— 生产侧就是这么传的，不带的话卡片按设计不显示品类。
 *   · 其余原样。
 */
function withProvenance(got, { category, modality }) {
  const out = { ...got, judgment: { ...(got.judgment ?? {}), label: got.label } };
  if (category && modality === 'text') {
    out.product_line = category;
    out.product_line_resolution = { display_category: category };
  }
  return out;
}

/** 一条图片样本的默认字段，样本里只覆盖要变的那些。 */
const img = (label, over = {}) => ({
  judgment: { label, findings_total: 0 },
  four_dim_audit: { ...PASS_BODY, media_kind: 'image', ...over },
  carrier: 'image',
});

/* ══════════════ 二、文案与视频四维样本 ══════════════ */

const textFd = (oneLine, overall, regions = [], extra = {}) => ({
  media_kind: 'text',
  overall,
  short_title: oneLine.slice(0, 18),
  one_line: oneLine,
  quick_fix: '删掉或替换命中的表述，改为客观功能描述并补充实测条件说明。',
  literal_status: '有风险', literal_summary: '命中字面红线或医疗宣称',
  ocr_status: '正常', ocr_summary: '未命中已知字面禁用与医疗红线词',
  claim_status: '有风险', claim_summary: oneLine,
  scene_status: '正常', scene_semantics: '文本送审，无画面语义',
  platform_status: '需注意', platform_summary: '吸奶器属母婴用品：禁止医疗级/治疗/奶量倍增等承诺，性能须可测。',
  symbol_status: '正常', visual_symbols: '文本送审，无视觉符号',
  region_rows: regions,
  copy_paste_snippet: '（本产品为日常护理用品，非医疗器械，不能替代诊断或治疗；个体体验存在差异。）',
  ...extra,
});

const cleanTextFd = (oneLine) => ({
  media_kind: 'text',
  overall: '初筛未见明显违规',
  short_title: oneLine.slice(0, 18),
  one_line: oneLine,
  quick_fix: '无需修改，人工确认后即可放行。',
  literal_status: '正常', literal_summary: '未命中已知字面禁用与医疗红线词',
  ocr_status: '正常', ocr_summary: '未命中已知字面禁用与医疗红线词',
  claim_status: '未见风险', claim_summary: '未出现需可测依据的性能数字或医疗级表述',
  scene_status: '正常', scene_semantics: '文本送审，无画面语义',
  platform_status: '正常', platform_summary: '未出现绝对化比较或未标明条件的性能宣称',
  symbol_status: '正常', visual_symbols: '文本送审，无视觉符号',
  region_rows: [],
  copy_paste_snippet: '（本产品为日常护理用品，非医疗器械，个体体验存在差异。）',
});

const videoFd = (oneLine, overall, regions = []) => ({
  media_kind: 'video',
  overall,
  short_title: oneLine.slice(0, 18),
  one_line: oneLine,
  quick_fix: '按时间轴删改对应片段的口播与字幕后重审。',
  literal_status: '有风险', literal_summary: oneLine,
  ocr_status: '正常', ocr_summary: '画面字幕未见禁用词',
  claim_status: '有风险', claim_summary: oneLine,
  scene_status: '需注意', scene_semantics: '产品演示场景，含真人使用画面',
  platform_status: '需注意', platform_summary: '吸奶器属母婴用品：禁止医疗级/奶量倍增承诺。',
  symbol_status: '正常', visual_symbols: '未见认证徽章',
  region_rows: regions,
  copy_paste_snippet: '（本产品为日常护理用品，非医疗器械，个体体验存在差异。）',
});

/* ══════════════ 三、56 条样本表 ══════════════ */

/**
 * 每条：{ id, modality, expect: 'BLOCK'|'REVIEW'|'PASS'|'未审查',
 *         category?, got, titlePrefix }
 *
 * `category` 是期望卡片上「识别品线」那一格显示的文字；
 * 不给就表示这一条不检查品类（例如视频与 Office 文档）。
 */
const IMAGE_SPECS = [
  // 9 条干净产品展示 → PASS
  ['图-01', 'PASS', '吸奶器', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-02', 'PASS', '吸奶器', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-03', 'PASS', '婴儿监护仪', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-04', 'PASS', '婴儿监护仪', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-05', 'PASS', '奶瓶清洗机', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-06', 'PASS', '储奶袋与配件', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-07', 'PASS', '婴儿监护仪', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-08', 'PASS', '吸奶器', img('PASS', { overall: '初筛未见明显违规' })],
  ['图-09', 'PASS', '推车', img('PASS', { overall: '初筛未见明显违规' })],
  // 4 条硬拦截
  ['图-10', 'BLOCK', '婴儿监护仪', img('BLOCK', { ...BLOCK_FEVER })],
  ['图-11', 'BLOCK', '婴儿监护仪', img('BLOCK', { ...BLOCK_COUGH })],
  ['图-12', 'BLOCK', '婴儿监护仪', img('BLOCK', { ...BLOCK_VITALS })],
  ['图-13', 'BLOCK', '婴儿监护仪', img('BLOCK', { ...BLOCK_FEVER })],
  // 5 条需人工确认
  ['图-14', 'REVIEW', '婴儿监护仪', img('REVIEW', { ...REVIEW_TEMP_SENSING })],
  ['图-15', 'REVIEW', '婴儿监护仪', img('REVIEW', { ...REVIEW_37C })],
  ['图-16', 'REVIEW', '婴儿监护仪', img('REVIEW', { ...REVIEW_MILD_SAFE })],
  ['图-17', 'REVIEW', '储奶袋与配件', img('REVIEW', { ...REVIEW_NIPPLE_TOOL })],
  ['图-18', 'REVIEW', '吸奶器', img('REVIEW', { ...REVIEW_MILD_SAFE })],
].map(([id, expect, category, got]) => ({
  // ★ 图片卡按设计**不显示**「识别品线」那一格（`showProductLine: false`）：
  //   图片审查读的是画面，而「这条属于哪个品线」对改图没有帮助。
  //   所以这一列只做样本台账，不进断言 —— 断言它反而会把正确实现判红。
  id, modality: 'image', expect, category: null, expectCategoryOnCard: false, got,
  titlePrefix: '【图片审查 · ',
}));

/** 32 条文案。`verdict` 是生产侧的五标签，`text` 是原句。 */
const TEXT_SPECS = [
  ['文-01', 'BLOCK', '婴儿监护仪', 'Baby monitor that covers face or face-down sleeping detection.', 'covered face or face-down sleeping'],
  ['文-02', 'BLOCK', '婴儿监护仪', 'The best baby monitor, AI-powered sleep tracking.', 'best baby monitor / AI-powered'],
  ['文-03', 'BLOCK', '吸奶器', 'V1 Pro: Hospital Grade breast pump for NICU moms.', 'Hospital Grade'],
  ['文-04', 'BLOCK', '吸奶器', 'Top Rated breast pump chosen by 1M mothers.', 'Top Rated'],
  ['文-05', 'BLOCK', '吸奶器', 'Boosting pumping efficiency by 28.2% in clinical use.', 'boosting pumping efficiency by 28.2%'],
  ['文-06', 'BLOCK', '吸奶器', 'Pump 30% faster than any other wearable pump.', '30% faster'],
  ['文-07', 'BLOCK', '吸奶器', 'Best-selling wearable pump with strong suction.', 'best-selling / strong suction'],
  ['文-08', 'BLOCK', '吸奶器', 'FDA approved wearable breast pump.', 'FDA approved'],
  ['文-09', 'BLOCK', '婴儿监护仪', 'The safest baby monitor you can buy.', 'The safest baby monitor you can buy'],
  ['文-10', 'BLOCK', '吸奶器', 'Whisper-quiet motor you will never hear.', 'Whisper-quiet'],
  ['文-11', 'BLOCK', '吸奶器', 'IBCLC-recommended wearable breast pump.', 'IBCLC-recommended'],
  ['文-12', 'BLOCK', '吸奶器', 'Helps treat engorgement and mastitis.', 'treat engorgement'],
  ['文-13', 'BLOCK', '吸奶器', 'FDA certified closed-system pump.', 'FDA certified'],
  ['文-14', 'BLOCK', '婴儿监护仪', 'NICU-grade monitoring quality for home use.', 'NICU-grade'],
  ['文-15', 'BLOCK', '吸奶器', 'Clinically proven to increase milk supply.', 'clinically proven'],
  ['文-16', 'BLOCK', '吸奶器', 'Zero risk. Zero pain. Pump without any discomfort.', 'Zero risk. Zero pain'],
  ['文-17', 'BLOCK', '吸奶器', 'm5 pro是最好的吸奶器，这句话能过审吗？', 'm5 pro 是最好的吸奶器'],
  ['文-18', 'BLOCK', '吸奶器', 'Hospital Grade pump, guaranteed results.', 'Hospital Grade'],
  ['文-19', 'BLOCK', '吸奶器', 'FDA approved, doctors recommend it.', 'FDA approved'],
  ['文-20', 'BLOCK', '推车', 'The safest stroller ever built, zero accidents.', 'The safest stroller'],
  ['文-21', 'BLOCK', '哺乳内衣', 'Clinically proven to prevent back pain.', 'Clinically proven'],
  ['文-22', 'BLOCK', '温奶器', 'Medical grade bottle warmer kills 99.9% bacteria.', 'Medical grade'],
  // 干净文案 → PASS
  ['文-23', 'PASS', '储奶袋与配件', 'Replacement valve and membrane set for M5 pumps.', null],
  ['文-24', 'PASS', '储奶袋与配件', 'Food-grade silicone duckbill valves, 3 pack.', null],
  ['文-25', 'PASS', '奶瓶清洗机', 'Bottle sterilizer and dryer with 6-minute cycle.', null],
  ['文-26', 'PASS', '婴儿监护仪', 'Long-range baby monitor with 1080p video and night vision.', null],
  ['文-27', 'PASS', '吸奶器', 'Silicone flange insert, 3 sizes included.', null],
  ['文-28', 'PASS', '储奶袋与配件', 'Replacement pump parts, dishwasher safe.', null],
  // 元提问：解释类，不该被判审正文吃掉
  ['文-29', 'PASS', '吸奶器', '帮我解释一下 FDA approved 是什么意思', null],
  ['文-30', 'PASS', '吸奶器', '帮我解释一下 Hospital Grade 是什么意思', null],
  // 需人工确认（可测但缺依据）
  ['文-31', 'REVIEW', '吸奶器', 'Up to 300 mmHg suction, adjustable in 9 levels.', null],
  ['文-32', 'REVIEW', '婴儿监护仪', 'TEMP-SENSING technology with 0.1 degree accuracy.', null],
].map(([id, expect, category, text, oneLine]) => ({
  id,
  modality: 'text',
  expect,
  category,
  expectCategoryOnCard: true,
  text,
  got: {
    carrier: 'text',
    label: expect,
    product_line: category,
    product_line_resolution: { display_category: category },
    four_dim_audit: expect === 'PASS'
      ? cleanTextFd(oneLine ?? text)
      : textFd(oneLine ?? text, expect === 'BLOCK' ? '发现违规需修改' : '需人工确认', [
        { region: `正文 · 「${oneLine ?? text}」`, issue: `命中「${oneLine ?? text}」`, fix: '删掉或改为客观功能描述并补实测条件' },
      ]),
  },
  titlePrefix: '【文案审查 · ',
}));

const MEDIA_SPECS = [
  // 2 视频
  ['媒-01', 'video', 'BLOCK', null, {
    carrier: 'video',
    label: 'BLOCK',
    four_dim_audit: videoFd('口播出现 Hospital-grade 与 300% more milk', '发现违规需修改', [
      { region: '00:03-00:07 · 口播', issue: 'Hospital-grade 宣称', fix: '删掉医疗级措辞，改为客观功能描述' },
      { region: '00:12-00:18 · 字幕', issue: '300% more milk', fix: '删除未标明条件的奶量倍增数字' },
    ]),
  }],
  ['媒-02', 'video', 'PASS', null, {
    carrier: 'video',
    label: 'PASS',
    four_dim_audit: videoFd('产品装配与清洗演示，未见违规宣称', '初筛未见明显违规', []),
  }],
  ['媒-03', 'video', '未审查', null, {
    carrier: 'video',
    label: '未审查',
    four_dim_audit: { media_kind: 'video', status: 'failed', one_line: '', overall: '', region_rows: [] },
  }],
  // 2 个 Office 附件 → 抽出正文后走文案四维
  ['媒-04', 'text', 'BLOCK', '吸奶器', {
    carrier: 'text',
    label: 'BLOCK',
    four_dim_audit: textFd('文档正文出现 Hospital Grade 与 28.2% 效率提升', '发现违规需修改', [
      { region: '文档第 1 段', issue: 'Hospital Grade 宣称', fix: '删掉医疗级措辞' },
      { region: '文档表格', issue: '28.2% 效率提升', fix: '补检测报告与实测条件' },
    ]),
  }],
  ['媒-05', 'text', 'REVIEW', '储奶袋与配件', {
    carrier: 'text',
    label: 'REVIEW',
    four_dim_audit: textFd('产品表含温度耐受范围，需核对检测依据', '需人工确认', [
      { region: '表格 · 温度列', issue: '温度耐受范围', fix: '补检测报告编号' },
    ]),
  }],
  // 1 条跨模态边界：视频卡里不许出现图片的「对表改图」与文案的「替换文案」
  ['媒-06', 'video', 'REVIEW', null, {
    carrier: 'video',
    label: 'REVIEW',
    four_dim_audit: videoFd('画面出现认证徽章，需核对授权', '需人工确认', [
      { region: '00:20 · 徽章区', issue: '第三方认证徽章', fix: '补充授权证明或移除' },
    ]),
  }],
].map(([id, modality, expect, category, got]) => ({
  id, modality, expect,
  category,
  expectCategoryOnCard: Boolean(category),
  got: withProvenance(got, { category, modality }),
  titlePrefix: modality === 'video' ? '【视频审查 · ' : '【文案审查 · ',
}));

const ALL = [...IMAGE_SPECS, ...TEXT_SPECS, ...MEDIA_SPECS];

/* ══════════════ 四、逐条回放 ══════════════ */

const res = [];
const T = (name, ok, detail = '') => res.push({ name, ok: Boolean(ok), detail: String(detail) });

/** 卡片 → 一段可判读的文本（正文 + 表头 + 灰底带 + 边界）。 */
function view(card) {
  const parts = [card?.header?.title?.content ?? ''];
  for (const el of card?.body?.elements ?? []) {
    if (el.tag === 'markdown') parts.push(el.content);
    else if (el.tag === 'table') parts.push((el.columns ?? []).map((c) => c.display_name).join(' | '));
    else if (el.tag === 'column_set') {
      for (const c of el.columns ?? []) {
        for (const e of c.elements ?? []) if (e.tag === 'markdown') parts.push(e.content);
      }
    } else if (el.tag === 'collapsible_panel') {
      for (const e of el.elements ?? []) if (e.tag === 'markdown') parts.push(e.content);
    } else if (el.tag === 'button') parts.push(el.text?.content ?? '');
  }
  return parts.join('\n');
}

/** 状态标签落在抬头里的哪一种说法。 */
const STATE_TEXT = {
  BLOCK: 'BLOCK', REVIEW: 'REVIEW', PASS: 'PASS', 未审查: '未审查',
};

const failuresByCase = [];

for (const c of ALL) {
  const problems = [];

  // 1) 模态与抬头前缀
  const resolved = specs.resolveModality(c.got);
  if (resolved !== c.modality) problems.push(`模态判成 ${resolved}，应为 ${c.modality}`);

  const card = std.buildAuditResultCard({ mediaGot: c.got });
  if (!card) {
    problems.push('没建出卡片');
    failuresByCase.push({ id: c.id, problems });
    continue;
  }
  const v = view(card);
  if (!v.includes(c.titlePrefix)) problems.push(`抬头不是 ${c.titlePrefix}…`);

  // 2) 五标签显式写在抬头里
  const want = STATE_TEXT[c.expect];
  if (!v.includes(want)) problems.push(`抬头没写 ${want}`);

  // 3) PASS 必须是绿头（不是红、不是「需修改」）
  if (c.expect === 'PASS') {
    if (card.header?.template !== 'green') problems.push(`PASS 却用了 ${card.header?.template} 头，应为 green`);
    // ★ `需修改` 是 `无需修改` 的子串 —— 直接判子串会把一句正确的
    //   「无需修改」判成违规动作。所以先摘掉否定式再看。
    if (/需修改/.test(v.replace(/无需修改/g, ''))) problems.push('PASS 卡里出现「需修改」');
    if (!/人工确认后放行/.test(v)) problems.push('PASS 卡的下一步不是「人工确认后放行」');
  }
  // 4) BLOCK 必须是红头
  if (c.expect === 'BLOCK' && card.header?.template !== 'red') {
    problems.push(`BLOCK 却用了 ${card.header?.template} 头，应为 red`);
  }
  // 5) 未审查必须是蓝灰头，且不许说成「通过」或「附件不支持」
  if (c.expect === '未审查') {
    if (card.header?.template !== 'wathet') problems.push(`未审查却用了 ${card.header?.template} 头，应为 wathet`);
    if (/已通过|合规/.test(v)) problems.push('未审查卡里说成了通过');
  }

  // 6) 品类显示（图片卡不显示，见样本表的注释）
  if (c.expectCategoryOnCard && c.category && !v.includes(c.category)) {
    problems.push(`没显示品类 ${c.category}`);
  }

  // 7) 跨模态词零泄漏
  const foreign = specs.foreignTokensFor(c.modality).filter((t) => v.includes(t));
  if (foreign.length) problems.push(`混进别模态的说法：${foreign.join('、')}`);

  // 8) 卡片过本地校验 + 不含未渲染 markdown 符号
  const valid = cardsMod.validateCard(card);
  if (!valid.ok) problems.push(`卡片校验不过：${valid.errors.map((e) => e.path).join(',')}`);
  if (plainMod.hasMdSymbols(JSON.stringify(card))) problems.push('卡片里残留未渲染 markdown 符号');

  // 9) 直出路径（prd53）与构建器同源：两条路径都得建得出卡，且过信封
  const direct = prd53.formatDirectAuditCardReply({ mediaGot: c.got });
  if (!direct) problems.push('prd53 直出路径没���出卡片块');
  else {
    const shaped = envMod.toCardOrText(direct);
    if (shaped.mode !== 'card' || shaped.dropped) problems.push(`直出块被信封降级 (${shaped.mode})`);
    const block = direct.split('\n')[1];
    let parsed = null;
    try { parsed = JSON.parse(block); } catch { problems.push('直出块的 JSON 解析不了'); }
    if (parsed) {
      const fromBlock = cardsMod.build('evidence', parsed);
      const fv = view(fromBlock);
      const fForeign = specs.foreignTokensFor(c.modality).filter((t) => fv.includes(t));
      if (fForeign.length) problems.push(`直出块混进别模态说法：${fForeign.join('、')}`);
    }
  }

  T(`${c.id} · ${c.modality} · ${c.expect}`, problems.length === 0, problems.join('；'));
  if (problems.length) failuresByCase.push({ id: c.id, problems });
}

/* ══════════════ 五、总量断言 ══════════════ */

T('总量：56 条样本齐全（18 图 + 32 文案 + 6 媒体）',
  IMAGE_SPECS.length === 18 && TEXT_SPECS.length === 32 && MEDIA_SPECS.length === 6
    && ALL.length === 56,
  `图 ${IMAGE_SPECS.length} / 文案 ${TEXT_SPECS.length} / 媒体 ${MEDIA_SPECS.length}`);

// ★ 反向对照：这批样本里必须**同时**有 PASS、BLOCK、REVIEW、未审查四种。
//   少了哪一类，上面那些断言对那一类就一条都没跑过，而总数照样是 56。
{
  const seen = new Set(ALL.map((c) => c.expect));
  const missing = ['PASS', 'BLOCK', 'REVIEW', '未审查'].filter((x) => !seen.has(x));
  T('★ 反向对照：四类结论在样本里都出现过（少一类就等于那一类一条都没验过）',
    missing.length === 0, missing.length ? `缺：${missing.join('、')}` : '四类齐全');
}

/* ══════════════ 六、出口 ══════════════ */

const nFail = res.filter((x) => !x.ok).length;
const pass = res.length - nFail;

if (JSON_SUMMARY) {
  console.log(JSON.stringify({
    total: res.length,
    pass,
    fail: nFail,
    cases: ALL.length,
    failures: failuresByCase,
  }, null, 2));
} else {
  for (const x of res) {
    if (!x.ok) console.log(`  ❌ ${x.name}  ← ${x.detail}`);
  }
  console.log(`\n${nFail ? '❌' : '✅'} 56 条真实送审回放 ${pass}/${res.length} 项通过（失败样本 ${failuresByCase.length} 条）`);
  if (!nFail) console.log('   （离线渲染回归：不联网、不跑生产判定、不写盘）');
}
process.exit(nFail ? 1 : 0);
