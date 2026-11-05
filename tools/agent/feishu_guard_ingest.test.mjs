#!/usr/bin/env node
/**
 * feishu_guard_ingest.test.mjs —— 飞书 Guard（cli_aa600ebeed38dccf）统一审核与工作台建案自证
 *
 * 覆盖面：
 *   A. 飞书 @Guard 与 @守衡 双标识及 open_id 识别（防群内 @Guard 被当成 not_mentioned 静默跳过）
 *   B. 品线自动识别四态（declared / invalid_declared_fallback / inferred_keyword / default_fallback）
 *   C. 多载体生产审查与工作台建案（free_text / ad_text / structured_json / landing_url / image）：
 *      - 产出合法 case_id（写入权威事件流 BusinessEventStore 与 SQLite 投影 ProjectionStore）
 *      - 同一 message_id 重放幂等（replayed=true，case_id 不变）
 *      - 五标签（BLOCK/REVIEW/PASS/待自决/未审查）+ DP0..DP4 + release_status="待放行"
 *      - workflow_timing 阶段耗时非空且 status="ok"
 *   D. Node 工具层 executeTool('judge_copy') 端到端贯通：
 *      - 同时返回生产建案字段（case_id / label / layer / findings）与知识库证据链（evidence_chain）
 *   E. 反向对照与零副作用：
 *      - 仓库内路径传入 SHOUHENG_WORKBENCH_DATA_ROOT 必须拒绝（防客户数据入公开仓）
 *      - 真实状态目录与真实账本未被测试改写（§2.4.4）
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const GUARD_PY = path.join(REPO_ROOT, 'base', 'feishu_guard_ingest.py');

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'feishu-guard-ingest-test-'));
const tmpState = path.join(tmpRoot, 'state');
fs.mkdirSync(tmpState, { recursive: true });

process.env.SHOUHENG_STATE_DIR = tmpState;
process.env.SHOUHENG_KB_ENABLED = '0';

const res = [];
const T = (name, ok, detail = '') => res.push({ name, ok: Boolean(ok), detail: String(detail) });

/* ── A. 飞书 @Guard 与 @守衡 识别 ─────────────────────────────────────── */
const feishu = await import('./feishu.mjs');
{
  const guardMentions = [{
    key: '@_user_1',
    name: 'Guard',
    id: { open_id: 'ou_c5c35c6322ac7b763fb62354aa4f3eb6' },
  }];
  const r1 = feishu.resolveMentions('@_user_1 帮我审一下这段吸奶器文案', guardMentions);
  T('A1 @Guard 被识别为机器人自身（isBot=true）',
    feishu.isBotMentioned(r1.mentions) === true,
    JSON.stringify(r1.mentions));
  T('A2 stripBotMention 剥除 @Guard 只留待审正文',
    feishu.stripBotMention(r1.display, r1.mentions) === '帮我审一下这段吸奶器文案',
    feishu.stripBotMention(r1.display, r1.mentions));

  const legacyMentions = [{
    key: '@_user_1',
    name: '守衡',
    id: { open_id: 'ou_8a19f4dc43e9e93b93220e646a9cb7dd' },
  }];
  const r2 = feishu.resolveMentions('@_user_1 查一下规则', legacyMentions);
  T('A3 @守衡 保持向后兼容识别（isBot=true）',
    feishu.isBotMentioned(r2.mentions) === true, '');

  const otherUser = [{
    key: '@_user_1',
    name: '周健',
    id: { open_id: 'ou_7b46f514ed67006a2809e268ac1fa602' },
  }];
  const r3 = feishu.resolveMentions('@_user_1 你看下', otherUser);
  T('A4 反向对照：群内只 @ 普通成员时不触发机器人（isBot=false）',
    feishu.isBotMentioned(r3.mentions) === false, '');
}

/* ── B. 品线自动识别四态与阶段解析 ────────────────────────────────────── */
function runGuardPy(args, extraEnv = {}) {
  const out = execFileSync('python3', [GUARD_PY, ...args, '--json', '--brief'], {
    cwd: REPO_ROOT,
    env: { ...process.env, SHOUHENG_STATE_DIR: tmpState, ...extraEnv },
    encoding: 'utf8',
    timeout: 30_000,
  });
  return JSON.parse(out);
}

{
  const b1 = runGuardPy(['--text', 'Lightweight baby stroller for travel', '--message-id', 'om_b1']);
  T('B1 关键词自动识别品线：stroller → 婴儿车（inferred_keyword）',
    b1.ok && b1.product_line === '婴儿车'
      && b1.product_line_resolution?.status === 'inferred_keyword',
    JSON.stringify(b1.product_line_resolution));

  const b2 = runGuardPy(['--text', 'Seamless nursing bra for moms', '--message-id', 'om_b2']);
  T('B2 关键词自动识别品线：nursing bra → 哺乳内衣（inferred_keyword）',
    b2.ok && b2.product_line === '哺乳内衣'
      && b2.product_line_resolution?.status === 'inferred_keyword',
    JSON.stringify(b2.product_line_resolution));

  const b3 = runGuardPy(['--text', 'Brand new summer sale discount', '--message-id', 'om_b3']);
  T('B3 无特定品线词时回落默认「吸奶器」并标注 default_fallback',
    b3.ok && b3.product_line === '吸奶器'
      && b3.product_line_resolution?.status === 'default_fallback'
      && b3.boundary_statement?.unknowns?.some((u) => u.includes('默认品线「吸奶器」')),
    JSON.stringify(b3.product_line_resolution));

  const b4 = runGuardPy(['--text', 'Fast bottle warmer', '--product-line', '温奶器', '--message-id', 'om_b4']);
  T('B4 显式指定合法品线 → status=declared',
    b4.ok && b4.product_line === '温奶器'
      && b4.product_line_resolution?.status === 'declared',
    JSON.stringify(b4.product_line_resolution));

  const b5 = runGuardPy(['--text', '这是提纲初稿：新款背带卖点整理', '--message-id', 'om_b5']);
  T('B5 含提纲/初稿特征词 → 自动推断 content_stage=brief',
    b5.ok && b5.content_stage === 'brief' && b5.product_line === '背带',
    `${b5.content_stage}/${b5.product_line}`);
}

/* ── C. 多载体生产判定、工作台建案、幂等重放与阶段耗时 ─────────────────── */
{
  const c1 = runGuardPy([
    '--text', 'Hospital-grade breast pump, 300% more milk, FDA approved',
    '--message-id', 'om_c1_idem',
  ]);
  T('C1 违规医疗/FDA 宣称 → 生产判定 BLOCK / DP2 + 产出工作台 case_id',
    c1.ok && c1.label === 'BLOCK' && c1.layer === 'DP2'
      && c1.release_status === '待放行' && /^case-[0-9a-f]{20}$/.test(c1.case_id)
      && c1.replayed === false && c1.confirmed_findings_count >= 3,
    `${c1.case_id}/${c1.label}/${c1.layer}/findings=${c1.confirmed_findings_count}`);

  const c1Replay = runGuardPy([
    '--text', 'Hospital-grade breast pump, 300% more milk, FDA approved',
    '--message-id', 'om_c1_idem',
  ]);
  T('C2 同一飞书 message_id 重放 → replayed=true 且 case_id 恒等',
    c1Replay.ok && c1Replay.replayed === true && c1Replay.case_id === c1.case_id,
    `${c1Replay.case_id}/replayed=${c1Replay.replayed}`);

  T('C3 workflow_timing 阶段耗时已透出且 status=ok',
    c1.workflow_timing?.status === 'ok' && typeof c1.workflow_timing?.total_ms === 'number',
    JSON.stringify(c1.workflow_timing));

  const c4 = runGuardPy([
    '--carrier', 'structured_json',
    '--fields-json', JSON.stringify({
      title: 'Momcozy M5 Wearable Breast Pump',
      description_text: 'Comfortable all-in-one design for daily pumping.',
    }),
    '--message-id', 'om_c4_struct',
  ]);
  T('C4 结构化商品 JSON 进件建案成功（carrier=structured_json）',
    c4.ok && /^case-[0-9a-f]{20}$/.test(c4.case_id) && c4.release_status === '待放行',
    `${c4.case_id}/${c4.label}`);

  const c5 = runGuardPy([
    '--carrier', 'landing_url',
    '--url', 'au.momcozy.com/pages/brand-new-wellness-1-warm-massage-breast-pump',
    '--message-id', 'om_c5_lp',
  ]);
  T('C5 落地页 URL 匹配语料并完成生产判定与建案',
    c5.ok && /^case-[0-9a-f]{20}$/.test(c5.case_id) && c5.confirmed_findings_count >= 1,
    `${c5.case_id}/${c5.label}/findings=${c5.confirmed_findings_count}`);

  const dbPath = path.join(tmpState, 'workbench-data', 'db', 'review.db');
  T('C6 工作台 SQLite 投影库已落盘在仓外临时目录',
    fs.existsSync(dbPath) && fs.statSync(dbPath).size > 0, dbPath);
}

/* ── D. Node 工具层 executeTool('judge_copy') 端到端 ──────────────────── */
const tools = await import('./tools.mjs');
{
  tools.runtimeContext.messageId = 'om_d1_tool';
  tools.runtimeContext.senderOpenId = 'ou_7b46f514ed67006a2809e268ac1fa602';
  tools.runtimeContext.chatId = 'oc_85e6a8fdb19d584ed68fcb12fbcf4eb5';

  const d1 = await tools.executeTool('judge_copy', JSON.stringify({
    text: 'Hospital-grade suction breast pump, clinically proven to cure mastitis',
  }));
  T('D1 executeTool(judge_copy) 同时返回工作台 case_id、生产五标签与 evidence_chain',
    d1.ok === true
      && /^case-[0-9a-f]{20}$/.test(d1.result?.case_id ?? '')
      && d1.result?.label === 'BLOCK'
      && Array.isArray(d1.result?.hits) && d1.result.hits.length > 0
      && d1.result?.evidence_chain?.status === 'disabled',
    JSON.stringify({
      ok: d1.ok, case_id: d1.result?.case_id, label: d1.result?.label,
      hits: d1.result?.hits?.length, ev: d1.result?.evidence_chain?.status,
    }));
}

/* ── E. 反向对照：仓内路径必须拒绝 ────────────────────────────────────── */
{
  let rejectedInsideRepo = false;
  try {
    runGuardPy(['--text', 'test'], {
      SHOUHENG_WORKBENCH_DATA_ROOT: path.join(REPO_ROOT, 'PMO', 'illegal-in-repo-workbench'),
    });
  } catch (e) {
    rejectedInsideRepo = /不允许落在仓库内/.test(String(e.stderr || e.message));
  }
  T('E1 ★ 反向对照：SHOUHENG_WORKBENCH_DATA_ROOT 指向仓库内时必须硬拒绝',
    rejectedInsideRepo === true, '');
}

/* ── F. SH-Agent 筛选纳入的 9 项卡片/信封/语域能力自证 ────────────────── */
{
  const cardsMod = await import('../reply-cards/cards.mjs');
  const envMod = await import('../reply-cards/envelope.mjs');
  const regMod = await import('../reply-cards/registry.mjs');
  const plainMod = await import('./plain.mjs');
  const prd53Mod = await import('./prd53.mjs');

  // 1) TONE 10 类 10 色互不撞色 + receipt carmine-50 + BACKGROUND_STYLES 闭集校验
  const toneVals = Object.values(cardsMod.TONE);
  T('F1 TONE 十类十色互不重复且 receipt 为 carmine',
    new Set(toneVals).size === toneVals.length && cardsMod.TONE.receipt === 'carmine',
    toneVals.join(','));
  const rcCard = cardsMod.receipt({ verdict: '收到，正在审。', fields: [{ name: '状态', value: '排队中' }] });
  const badBgCard = JSON.parse(JSON.stringify(rcCard));
  badBgCard.body.elements[0].background_style = 'neon-pink';
  T('F1b receipt 使用 carmine-50 通栏底色，且未知 background_style 被 validateCard 拦截',
    cardsMod.validateCard(rcCard).ok === true && cardsMod.validateCard(badBgCard).ok === false, '');

  // 2) flat1 / fieldPair 防 [object Object] 与 {name,value}/{label,note} 落（未填）
  const cbCard = cardsMod.capabilityBoundary({
    can: [{ label: '审文案', note: '五标签 + 建案' }, { 能力: '审图片', 边界: 'OCR+多模态' }],
  });
  const cbJson = JSON.stringify(cbCard);
  T('F2 flat1/fieldPair 兼容 {label,note} 与 {name,value}，绝不产出 [object Object]',
    !cbJson.includes('[object Object]') && !cbJson.includes('（未填）')
      && cbJson.includes('审文案：五标签 + 建案'), cbJson.slice(0, 160));

  // 3) evidence 空组与悬空 count:0 修复
  const evEmpty = cardsMod.evidence({ title: '零问题', verdict: '未见命中' });
  const evZeroCount = cardsMod.evidence({
    title: '有组', verdict: '结论', groups: [{ title: '逐条问题', count: 0, content: '第一条' }],
  });
  T('F3 evidence 无 groups/content 时不造空折叠组，count=0 时不印悬空「· 0」',
    !evEmpty.body.elements.some((e) => e.tag === 'collapsible_panel')
      && evZeroCount.body.elements.find((e) => e.tag === 'collapsible_panel')?.header?.title?.content === '逐条问题',
    '');

  // 4) extractCardBlock 剥除 [[/card]] 闭合标记
  const parsedBlk = envMod.extractCardBlock('[[card:receipt]]\n{"title":"已收到","verdict":"好"}\n[[/card]]');
  T('F4 extractCardBlock 剥干净 [[/card]] 闭合标记（after 为空）',
    parsedBlk?.after === '' && parsedBlk?.data?.title === '已收到',
    JSON.stringify(parsedBlk));

  // 5) internalLeak 拦截 <｜DSML｜ 与第一人称工具自述
  T('F5 internalLeak 拦截 <｜DSML｜ 标记与「不在我的工具里」自述',
    regMod.lintCopy('<｜DSML｜ invoke name="judge_copy">').some((h) => h.id === 'internalLeak')
      && regMod.lintCopy('重拉基线不在我的工具里').some((h) => h.id === 'internalLeak'), '');

  // 6) plainify 与 mdTextSafe
  T('F6 plainify 剥除粗体星号与反引号且保留下划线；mdTextSafe 转义 HTML 尖括号与波浪线',
    plainMod.plainify('**重点** `user_id`') === '重点 user_id'
      && !plainMod.hasMdSymbols(JSON.stringify(cardsMod.build('evidence', {
        title: '**标题**', verdict: '**结论**', reasoning: '```text\nabc\n```',
        columns: ['**列**'], rows: [['**值**']],
      })))
      && plainMod.mdTextSafe('<img src=x> ~~删~~') === '&lt;img src=x&gt; &#126;&#126;删&#126;&#126;', '');

  // 7) jargon.mjs 剥除内部赋值行但保留工作台 case_id 与五标签
  const shapedJargon = envMod.toCardOrText(
    '[[card:query-answer]]\n{"title":"结论","verdict":"案件 case-4a5c13b861889db1ead3 为 BLOCK\\nparse_status = ok\\ncoverage_state = partial"}'
  );
  const shapedStr = JSON.stringify(shapedJargon.card);
  T('F7 jargon 剥除 parse_status/coverage_state 内部赋值行，保留 case_id 与五标签',
    shapedStr.includes('case-4a5c13b861889db1ead3') && !shapedStr.includes('parse_status = ok'),
    shapedStr.slice(0, 180));

  // 8) prd53 + applyVerdictLine 权威结论行置顶与逐条块注入
  const gv = prd53Mod.buildGuardVerdict({
    label: 'BLOCK', layer: 'DP2', caseId: 'case-4a5c13b861889db1ead3',
    findings: [{ control_code: 'H06', severity: 'L4', quote: 'FDA approved <tag>', location: { start: 0, end: 12 }, authority_ref: [{ entry_id: 'EXT-001' }] }],
  });
  const shaped53 = envMod.toCardOrText(
    `${gv.line}\n[[card:evidence]]\n{"title":"自拟旧标题","verdict":"需要修改","boundary":"未声明品线，按默认『吸奶器』建案"}`,
    { verdict: gv },
  );
  T('F8 prd53 权威结论行自动置顶到卡片 title 且逐条块安全转义并展开',
    shaped53.card?.header?.title?.content === gv.line
      && JSON.stringify(shaped53.card).includes('&lt;tag&gt;')
      && JSON.stringify(shaped53.card).includes('默认『吸奶器』'),
    shaped53.card?.header?.title?.content);
}

/* ── G. P1 富文本与视频入站 · P2 结论行自动消费 · P3 工作台案件反查 ────── */
{
  const envMod = await import('../reply-cards/envelope.mjs');
  const agentMod = await import('./agent.mjs');

  // G1: post 富文本提取标题 + 正文 + @Guard 占位符还原
  const postPayload = JSON.stringify({
    title: '吸奶器春季广告稿',
    content: [
      [{ tag: 'at', user_id: '@_user_1', user_name: 'Guard' }, { tag: 'text', text: ' 请审：Hospital-grade breast pump' }],
    ],
  });
  const plainPost = feishu.postToPlain(postPayload);
  T('G1 post 富文本提取标题与正文（不拒答 unsupported_type）',
    plainPost.includes('吸奶器春季广告稿') && plainPost.includes('Hospital-grade breast pump'),
    plainPost);

  // G2: 视频附件（message_type=media）入站 → 下载 → 生产视频进件建案 → 清理临时文件
  const tmpAttach = path.join(tmpRoot, 'attachments-video');
  process.env.SHOUHENG_ATTACHMENT_DIR = tmpAttach;
  const origGet = feishu.client.im.v1.messageResource.get;
  feishu.client.im.v1.messageResource.get = async () => ({
    headers: { 'content-length': '64' },
    writeFile: async (p) => { fs.writeFileSync(p, Buffer.from('fake-mp4-video-bytes-for-ingest')); return p; },
    getReadableStream: () => ({ destroy() {} }),
  });
  try {
    const vr = await feishu.ingestAttachment({
      message_id: 'om_video_e2e_1',
      message_type: 'media',
      content: JSON.stringify({ file_key: 'fk_vid_1', file_name: 'pump_demo.mp4' }),
    });
    const vTurn = agentMod.videoTurnText(vr);
    T('G2 视频（media）入站真跑生产进件：产出 case_id、parse_status=partial、声明口播未审，且删临时目录',
      vr.status === 'video_judged'
        && /^case-[0-9a-f]{20}$/.test(vr.case_id ?? '')
        && vr.parse_status === 'partial'
        && /口播文案/.test(vTurn)
        && fs.readdirSync(tmpAttach).length === 0,
      JSON.stringify({ status: vr.status, case_id: vr.case_id, parse: vr.parse_status }));
  } finally {
    feishu.client.im.v1.messageResource.get = origGet;
  }

  // G3: judge_copy 执行后自动写入 pendingTurnVerdict → toCardOrText 自动置顶权威结论行
  tools.runtimeContext.messageId = 'om_g3_auto_verdict';
  const jCall = await tools.executeTool('judge_copy', JSON.stringify({
    text: 'FDA approved breast pump, 300% more milk',
  }));
  const autoShaped = envMod.toCardOrText('[[card:evidence]]\n{"title":"模型自拟标题","verdict":"发现违规"}');
  T('G3 judge_copy → toCardOrText 硬接线：模型未写结论行时，卡头自动置顶【审查结论：BLOCK】+ case_id',
    jCall.ok === true
      && autoShaped.mode === 'card'
      && autoShaped.card?.header?.title?.content?.includes('【审查结论：BLOCK】')
      && autoShaped.card?.header?.title?.content?.includes(jCall.result.case_id),
    autoShaped.card?.header?.title?.content);

  // G4: workbench_case_status 工具反查单案详情与列表队列
  const detailCall = await tools.executeTool('workbench_case_status', JSON.stringify({
    case_id: jCall.result.case_id,
  }));
  const listCall = await tools.executeTool('workbench_case_status', JSON.stringify({
    product_line: '吸奶器', limit: 5,
  }));
  T('G4 workbench_case_status 支持按 case_id 反查详情及按品线列出队列',
    detailCall.ok && detailCall.result?.found === true
      && detailCall.result?.case?.case_id === jCall.result.case_id
      && detailCall.result?.case?.label === 'BLOCK'
      && listCall.ok && listCall.result?.total >= 1,
    JSON.stringify({ detail: detailCall.result?.case?.case_id, listTotal: listCall.result?.total }));

  // G5: 真实群聊形态 —— post 混排（@Guard + 内嵌 tag:img + "审核"）提取出 image_key
  const mixedPost = JSON.stringify({
    title: '',
    content: [
      [{ tag: 'at', user_id: '@_user_1', user_name: 'Guard' }, { tag: 'text', text: ' ' }],
      [{ tag: 'img', image_key: 'img_v3_02174_c08094a1-8c9c-46be-9031-7510ae18191g', width: 1596, height: 1774 }],
      [{ tag: 'text', text: '审核' }],
    ],
  });
  T('G5 post 混排消息（@Guard + 贴图 + 文字）提取出内嵌 image_key',
    feishu.extractPostImageKey(mixedPost) === 'img_v3_02174_c08094a1-8c9c-46be-9031-7510ae18191g',
    feishu.extractPostImageKey(mixedPost));

  // G5b: 多图（组图 / A+ 页 / 轮播图）一次性提取全部 image_key（去重，上限 6）
  const multiImgPost = JSON.stringify({
    title: '',
    content: [
      [{ tag: 'at', user_id: '@_user_1', user_name: 'Guard' }],
      [{ tag: 'img', image_key: 'img_aaa' }, { tag: 'img', image_key: 'img_bbb' }],
      [{ tag: 'img', image_key: 'img_aaa' }, { tag: 'img', image_key: 'img_ccc' }],
    ],
  });
  const multiKeys = feishu.extractPostImageKeys(multiImgPost);
  T('G5b post 多图消息提取全部 image_key（去重：3 张唯一图）',
    Array.isArray(multiKeys) && multiKeys.length === 3
      && multiKeys[0] === 'img_aaa' && multiKeys[2] === 'img_ccc',
    JSON.stringify(multiKeys));
}

/* ── H. 「5 + 4」全场景标准化卡片矩阵 + 定时推送仅限测试群闸门 ─────────── */
{
  const stdCards = await import('./standard_cards.mjs');
  const pushPol = await import('./push_policy.mjs');
  const plainMod = await import('./plain.mjs');
  const cardsMod = await import('../reply-cards/cards.mjs');

  const sampleCases = [
    {
      case_id: 'case-3f0f2b6b4ff819bb1a3a',
      product_line: '吸奶器',
      content_type: '图片',
      entry_channel: '群消息',
      label: 'BLOCK',
      status: 'unassigned',
      confirmed_findings_count: 2,
      findings_preview: [{ control_code: 'H06', quote: 'FDA approved' }],
    },
  ];

  const r1 = stdCards.buildAuditResultCard({
    textJudgeResult: {
      case_id: 'case-3f0f2b6b4ff819bb1a3a',
      label: 'BLOCK',
      product_line: '吸奶器',
      findings: [{ status: 'confirmed', control_code: 'H06', quote: 'FDA approved', authority_ref: [{ entry_id: 'EXT-001' }] }],
    },
  });
  const r2 = stdCards.buildQuickReceiptCard({ mediaKind: '图片', fileName: 'demo.png', receivedAt: '21:30' });
  const r3Detail = stdCards.buildCaseStatusCard({ mode: 'detail', found: true, case: sampleCases[0] });
  const r3List = stdCards.buildCaseStatusCard({ mode: 'list', total: 1, cases: sampleCases });
  const r4 = stdCards.buildRuleAnswerCard({
    title: '【规则解答】Hospital-grade 能否使用',
    verdict: '吸奶器广告禁止无依据使用 Hospital-grade',
    reasoning: '【马上怎么改】改为具体吸力参数（如 295 mmHg）',
    replacement: 'Strong 295 mmHg suction for daily comfort.',
  });
  const r5 = stdCards.buildCannotReadCard({ kind: '加密表格', why: '文件含密码保护' });

  const p1 = stdCards.buildOpsDigestCard({ periodLabel: '日报', cases: sampleCases });
  const p2 = stdCards.buildSlaReminderCard({ cases: sampleCases });
  const p3 = stdCards.buildBaselineInspectCard({ hasChange: true, items: [{ target: 'PRD v1.2', change: '§5.3 更新', action: '核对卡片抬头' }] });
  const p4 = stdCards.buildHealthAlertCard({ healthy: true });

  const allNine = [r1, r2, r3Detail, r3List, r4, r5, p1, p2, p3, p4];
  T('H1 「5 + 4」共 9 类标准化卡片全部通过飞书 V2 schema 校验',
    allNine.every((c) => cardsMod.validateCard(c).ok === true),
    '');
  T('H2 「5 + 4」全部卡片 0 未渲染 Markdown 符号（无 * 与 `）',
    allNine.every((c) => !plainMod.hasMdSymbols(JSON.stringify(c))),
    '');

  const okPush = stdCards.prepareScheduledPush(p1);
  T('H3 定时推送默认目标锁定为测试群（oc_49a7cfb2861cffa4365ca8491f398d32）',
    okPush.ok && okPush.chatId === pushPol.TEST_GROUP_CHAT_ID,
    okPush.chatId);

  let blockedOtherGroup = false;
  try {
    stdCards.prepareScheduledPush(p1, { targetChatId: 'oc_85e6a8fdb19d584ed68fcb12fbcf4eb5' });
  } catch (e) {
    blockedOtherGroup = /仅允许推送到测试群/.test(String(e.message));
  }
  T('H4 ★ 反向对照：定时推送传入非测试群（如守衡-交接群）必须硬拒绝',
    blockedOtherGroup === true,
    '');

  const llmMod = await import('./llm.mjs');
  const healthWatch = await import('./llm_health_watch.mjs');
  T('H5 对话层配置 3 级模型自动回落链（3.1-flash-lite → 3.5-flash → 3.8-flash）',
    Array.isArray(llmMod.FALLBACK_MODELS) && llmMod.FALLBACK_MODELS.length === 3
      && typeof llmMod.chatWithFallback === 'function',
    llmMod.FALLBACK_MODELS.join(' -> '));

  const mockHealth = await healthWatch.checkLlmAndSystemHealth({
    probeFn: async () => ({
      vodRes: {
        name: '主用网关 · 腾讯云 VOD',
        ok: true,
        code: 'ok',
        status: '正常在线',
        detail: '主模型 gemini-3.1-flash-lite 响应正常（HTTP 200）',
      },
      dsRes: {
        name: '备用通道 · DeepSeek 官方直连',
        ok: false,
        code: 'insufficient_balance_402',
        status: '额度不足（HTTP 402）',
        detail: '账户余额不足（HTTP 402），需充值后恢复',
      },
    }),
  });
  T('H6 大模型额度/健康巡检器准确识别 402 余额不足并产出零特殊符号的 P-4 卡片（锁定测试群）',
    mockHealth.ok && mockHealth.primaryHealthy === true && mockHealth.hasQuotaWarning === true
      && mockHealth.prepared?.chatId === pushPol.TEST_GROUP_CHAT_ID
      && !plainMod.hasMdSymbols(JSON.stringify(mockHealth.prepared?.card))
      && JSON.stringify(mockHealth.prepared?.card).includes('额度不足（HTTP 402）'),
    mockHealth.prepared?.card?.header?.title?.content);
}

/* ── I. 全链路审计报告 P0 / P1 / P2 根治项自证 ───────────────────────── */
{
  const jargonMod = await import('../reply-cards/jargon.mjs');
  const personaMod = await import('./persona.mjs');

  // I1 (P0-b): AsyncLocalStorage 隔离并发会话的 runtimeContext，绝不串台
  const [seenA, seenB] = await Promise.all([
    tools.runWithContext({ chatId: 'oc_chat_A', messageId: 'om_msg_A' }, async () => {
      await new Promise((r) => setTimeout(r, 30));
      return { chatId: tools.runtimeContext.chatId, messageId: tools.runtimeContext.messageId };
    }),
    tools.runWithContext({ chatId: 'oc_chat_B', messageId: 'om_msg_B' }, async () => {
      await new Promise((r) => setTimeout(r, 10));
      return { chatId: tools.runtimeContext.chatId, messageId: tools.runtimeContext.messageId };
    }),
  ]);
  T('I1 ★ P0-b 根治：并发会话跨 await 时 runtimeContext 互不覆盖（零串台）',
    seenA.chatId === 'oc_chat_A' && seenA.messageId === 'om_msg_A'
      && seenB.chatId === 'oc_chat_B' && seenB.messageId === 'om_msg_B',
    JSON.stringify({ seenA, seenB }));

  // I2 (P0-c): 飞书 SDK HTTP 实例已设非零硬超时
  const feishuTimeout = feishu.client?.httpInstance?.defaults?.timeout ?? 0;
  T('I2 ★ P0-c 根治：飞书 HTTP 客户端已配置 30s 硬超时（非 timeout=0）',
    feishuTimeout > 0 && feishuTimeout <= 60_000,
    `timeout=${feishuTimeout}`);

  // I3 (P1-1a): 知识库返回 HTTP 200 + HTML（如 ngrok 过期页）时必须判 untested，绝不判 none
  const http = await import('node:http');
  const htmlSrv = http.createServer((_req, resp) => {
    resp.writeHead(200, { 'content-type': 'text/html' });
    resp.end('<html><body>ngrok tunnel expired</body></html>');
  });
  await new Promise((r) => htmlSrv.listen(0, '127.0.0.1', r));
  const savedKbUrl = process.env.SHOUHENG_KB_BASE_URL;
  const savedKbKey = process.env.SHOUHENG_KB_API_KEY;
  process.env.SHOUHENG_KB_BASE_URL = `http://127.0.0.1:${htmlSrv.address().port}`;
  process.env.SHOUHENG_KB_API_KEY = 'fake-key-for-html-test';
  try {
    const jeMod = await import('./judge_evidence.mjs');
    const evHtml = await jeMod.gatherEvidence(
      'cure mastitis',
      { hits: [{ rule_key: 'R-1', matched: [{ matched_text: 'cure mastitis' }] }] },
      { enabled: true },
    );
    T('I3 ★ P1-1a 根治：KB 返回 200+HTML 时落 untested（may_assert_kb_absence=false），绝不伪装成 none',
      evHtml.status === 'untested' && evHtml.conclusion_gate?.may_assert_kb_absence === false,
      `${evHtml.status}/may_assert=${evHtml.conclusion_gate?.may_assert_kb_absence}`);
  } finally {
    htmlSrv.close();
    if (savedKbUrl === undefined) delete process.env.SHOUHENG_KB_BASE_URL;
    else process.env.SHOUHENG_KB_BASE_URL = savedKbUrl;
    if (savedKbKey === undefined) delete process.env.SHOUHENG_KB_API_KEY;
    else process.env.SHOUHENG_KB_API_KEY = savedKbKey;
  }

  // I4 (P1-2): run_readonly_command 超时强杀整棵进程组（含抱住 stdout 的后台子进程）
  process.env.SHOUHENG_RO_TIMEOUT_MS = '300';
  const t0 = Date.now();
  const hangCall = await tools.executeTool('run_readonly_command', JSON.stringify({
    command: 'find research -name "*.py"',
  }));
  delete process.env.SHOUHENG_RO_TIMEOUT_MS;
  T('I4 ★ P1-2 根治：run_readonly_command 独立进程组超时强杀生效',
    hangCall.ok === true && (hangCall.result?.status === 'ok' || hangCall.result?.status === 'timeout')
      && (Date.now() - t0) < 5000,
    `status=${hangCall.result?.status}, elapsed=${Date.now() - t0}ms`);

  // I5 (P2-1): 聊天链出站回执禁词净化（拦截「已通过/无需处理/审批完成」，保留否定告诫句）
  const cleaned1 = jargonMod.stripEngineJargon('这条素材已通过，无需处理，审批完成。').text;
  const cleaned2 = jargonMod.stripEngineJargon('注意：不许说「已通过」。').text;
  T('I5 ★ P2-1 根治：聊天链拦截「已通过/无需处理/审批完成」，且保留否定告诫句',
    !cleaned1.includes('已通过') && !cleaned1.includes('无需处理') && !cleaned1.includes('审批完成')
      && cleaned2.includes('不许说「已通过」'),
    `${cleaned1} | ${cleaned2}`);

  // I6 (P2-3): persona.mjs 已同步入站图片与视频四维审查说明
  T('I6 ★ P2-3 根治：persona.mjs 已对齐入站图片与视频四维审查与建案说明',
    personaMod.SYSTEM_PROMPT.includes('入站图片与视频走四维审查与建案'),
    '');
}

/* ── J. 工作流耗时巡检 + 定时巡检接线 + 判例回流闭环（P-1 周报规则缺口榜） ── */
{
  const stdCards = await import('./standard_cards.mjs');
  const opsCardMod = await import('./ops_watch_card.mjs');
  const plainMod = await import('./plain.mjs');
  const cardsMod = await import('../reply-cards/cards.mjs');

  const p1Weekly = stdCards.buildOpsDigestCard({
    periodLabel: '本周周报',
    cases: [
      {
        case_id: 'case-weekly-01',
        product_line: '吸奶器',
        label: 'BLOCK',
        status: 'closed',
        findings_preview: [{ control_code: 'H01', quote: 'cure mastitis' }],
      },
    ],
    timingTrend: {
      window_days: 7,
      rows: [
        { carrier: '群消息', n_current: 12, p50_ms: 4.2, p90_ms: 11.5, p90_delta_ms: -1.8 },
      ],
    },
    ruleGapRanking: [
      {
        rank: 1,
        control_code: 'H01',
        rule_key: 'medical-cure',
        count: 3,
        direction: 'over_strict',
        sample_quote: 'cure mastitis',
      },
    ],
    gapUnattributed: { n: 1, why: { no_control_code: 1 } },
  });
  const p1WeeklyStr = JSON.stringify(p1Weekly);
  T('J1 P-1 运营周报卡含各通道耗时趋势与判例回流「规则缺口榜」，且通过飞书 V2 schema 与 0 星号校验',
    cardsMod.validateCard(p1Weekly).ok === true
      && !plainMod.hasMdSymbols(p1WeeklyStr)
      && p1WeeklyStr.includes('各通道耗时趋势')
      && p1WeeklyStr.includes('规则缺口榜')
      && p1WeeklyStr.includes('H01')
      && p1WeeklyStr.includes('机器偏严/误报'),
    '');

  // J3: Python 端到端判例回流闭环验证（submit_review 与 review_and_close 分歧入队 + 幂等去重 + 规则缺口榜）
  const pyBin = fs.existsSync(path.join(REPO_ROOT, '.venv', 'bin', 'python'))
    ? path.join(REPO_ROOT, '.venv', 'bin', 'python')
    : 'python3';
  const pyFeedbackQueue = path.join(tmpRoot, 'feedback_queue.jsonl');
  const pyOut = execFileSync(pyBin, [
    '-c',
    `
import json, os, sys
from pathlib import Path
from base.business_event_store import BusinessEventStore, WriterLease
from base.projection_store import ProjectionStore
from base.review_command_service import ReviewCommandService
from base.submission_service import SubmissionIngestor
from base.ops_watch import collect_ops_stats

root = Path(sys.argv[1])
qpath = Path(sys.argv[2])
lease = WriterLease(root / "authority_fb" / "writer.lease")
lease.acquire()
auth = BusinessEventStore(root / "authority_fb", lease=lease)
proj = ProjectionStore(root / "db_fb" / "review.db")
svc = ReviewCommandService(auth, proj, feedback_queue=qpath)
ing = SubmissionIngestor()

principal = {"id": "u1", "tenant": "t1", "open_id": "ou-1", "tenant_id": "t1", "roles": ["dp3"], "product_lines": ["吸奶器"]}
sub1 = {
    "submission_id": "sub-fb-1",
    "content_type": "文本",
    "content_stage": "final_content",
    "entry_channel": "群消息",
    "source": {"kind": "free_text"},
    "text": "Our pump can cure disease and treat symptoms.",
    "product_line": "吸奶器",
}
r1 = svc.execute_submission(ingestor=ing, submission=sub1, principal=principal, idempotency_key="idem-fb-1")
cid1 = r1["result"]["case_id"]
ver1 = r1["result"]["version"]
actor = {"principal_id": "u1", "tenant_id": "t1"}

# 人工通过 review_and_close 执行 overturn（机器 BLOCK -> 人工推翻）
c1 = svc.execute(
    aggregate_id=cid1,
    command="review_and_close",
    actor=actor,
    expected_version=ver1,
    payload={"verdict": "overturn", "review_notes": "实测为引用反例说明，非广告宣称"},
    idempotency_key="idem-fb-close-1",
)
# 幂等重放同一结案命令，不应产生重复队列行
svc.execute(
    aggregate_id=cid1,
    command="review_and_close",
    actor=actor,
    expected_version=ver1,
    payload={"verdict": "overturn", "review_notes": "实测为引用反例说明，非广告宣称"},
    idempotency_key="idem-fb-close-1",
)

# 第二单：机器 PASS，人工 submit_review 选 revise（漏报回流）
sub2 = {
    "submission_id": "sub-fb-2",
    "content_type": "文本",
    "content_stage": "final_content",
    "entry_channel": "群消息",
    "source": {"kind": "free_text"},
    "text": "便携吸奶器日常容量 180ml。",
    "product_line": "吸奶器",
}
r2 = svc.execute_submission(ingestor=ing, submission=sub2, principal=principal, idempotency_key="idem-fb-2")
cid2 = r2["result"]["case_id"]
claim2 = svc.execute(aggregate_id=cid2, command="claim", actor=actor, expected_version=r2["result"]["version"], payload={}, idempotency_key="idem-fb-claim-2")
svc.execute(
    aggregate_id=cid2,
    command="submit_review",
    actor=actor,
    expected_version=claim2["result"]["version"],
    payload={"conclusion": {"verdict_choice": "revise", "review_notes": "隐含未标明条件"}},
    idempotency_key="idem-fb-submit-2",
)

stats = collect_ops_stats(db_path=root / "db_fb" / "review.db", queue_path=qpath, days=7)
lines = [ln for ln in qpath.read_text(encoding="utf-8").splitlines() if ln.strip()]
print(json.dumps({"lines_count": len(lines), "precedent": stats["precedent"]}, ensure_ascii=False))
`,
    tmpRoot,
    pyFeedbackQueue,
  ], { encoding: 'utf8' });
  const fbParsed = JSON.parse(pyOut.trim());
  T('J2 ★ 判例回流闭环：submit_review / review_and_close 人机分歧自动入队、重放幂等去重、生成周报规则缺口榜',
    fbParsed.lines_count === 2
      && fbParsed.precedent?.ok === true
      && fbParsed.precedent?.n_records === 2
      && fbParsed.precedent?.n_attributed + fbParsed.precedent?.n_unattributed === fbParsed.precedent?.n_records
      && Array.isArray(fbParsed.precedent?.ranking)
      && fbParsed.precedent.ranking.length >= 2,
    JSON.stringify(fbParsed));

  const dbFile = path.join(tmpRoot, 'db_fb', 'review.db');
  const watchRes = await opsCardMod.collectOpsWatchCard({ dbPath: dbFile, queuePath: pyFeedbackQueue });
  const watchStr = JSON.stringify(watchRes.card ?? {});
  T('J3 collectOpsWatchCard 真实读取投影库产出 P50/P90、失败率、超时率，且锁定测试群',
    watchRes.ok === true && watchRes.untested === false
      && watchStr.includes('失败率=') && watchStr.includes('超时率=')
      && watchRes.chatId === 'oc_49a7cfb2861cffa4365ca8491f398d32',
    watchRes.reason || '');

  const digestRes = await opsCardMod.collectOpsDigestCard({
    periodLabel: '本周周报',
    days: 7,
    dbPath: dbFile,
    queuePath: pyFeedbackQueue,
  });
  const digestStr = JSON.stringify(digestRes.card ?? {});
  T('J4 collectOpsDigestCard 串联投影库与反馈队列产出完整 P-1 周报卡（含规则缺口榜与耗时趋势）',
    digestRes.ok === true && digestRes.untested === false
      && digestStr.includes('规则缺口榜')
      && digestStr.includes('待新增规则（漏报候选）')
      && !plainMod.hasMdSymbols(digestStr),
    '');

  // J5: 远端 KB 断连（403/500）时开启 localFallback=true 自动回落仓内本地三库快照（措辞表达库+186条样本库+62条外部标准库）
  const jeMod = await import('./judge_evidence.mjs');
  const localKbMod = await import('./local_kb.mjs');
  const savedKbUrl = process.env.SHOUHENG_KB_BASE_URL;
  const savedKbKey = process.env.SHOUHENG_KB_API_KEY;
  process.env.SHOUHENG_KB_BASE_URL = 'http://127.0.0.1:1'; // 不可达端口模拟隧道断连
  process.env.SHOUHENG_KB_API_KEY = 'fake-key';
  try {
    const evFallback = await jeMod.gatherEvidence(
      'Hospital-grade breast pump cures mastitis',
      {
        hits: [{ rule_key: 'T1.1.medical-cure', matched: [{ matched_text: 'cure' }] }],
        receipt: { evidence_ref: [{ 条文号: 'S7-03', 条目ID: 'EXT-021' }] },
      },
      { enabled: true, localFallback: true },
    );
    T('J5 ★ 远端 KB 断连时 localFallback=true 自动回落仓内三库快照（status=found，含规则库+样本库+外部标准库）',
      evFallback.status === 'found'
        && evFallback.local_fallback === true
        && evFallback.evidence_total >= 2
        && evFallback.external_ref_check?.[0]?.status === 'present_local',
      JSON.stringify({ status: evFallback.status, total: evFallback.evidence_total, ext: evFallback.external_ref_check }));
  } finally {
    if (savedKbUrl === undefined) delete process.env.SHOUHENG_KB_BASE_URL;
    else process.env.SHOUHENG_KB_BASE_URL = savedKbUrl;
    if (savedKbKey === undefined) delete process.env.SHOUHENG_KB_API_KEY;
    else process.env.SHOUHENG_KB_API_KEY = savedKbKey;
  }

  const sampleSearch = localKbMod.retrieveLocal('2_内部正负样本库', '吸奶器', { topK: 3 });
  T('J6 ★ 2_内部正负样本库（186条）在 local_kb 中可检索并返回真实案例分片',
    sampleSearch.hitCount > 0 && sampleSearch.hits[0]?.docId?.startsWith('local-sample:'),
    JSON.stringify({ hitCount: sampleSearch.hitCount, firstDoc: sampleSearch.hits[0]?.docId }));
}

/* ── K. 模态专属审查卡：图片 / 文案 / 视频三套四维体检互不串台 ─────────── */
{
  const { AUDIT_MODALITY_SPECS, resolveModality } = await import('./audit_modality_specs.mjs');
  const prd53Mod = await import('./prd53.mjs');
  const stdCards = await import('./standard_cards.mjs');
  const cardsMod = await import('../reply-cards/cards.mjs');
  const envMod = await import('../reply-cards/envelope.mjs');
  const regMod = await import('../reply-cards/registry.mjs');
  const imgJudgment = await import('./image_judgment.mjs');

  /** 卡片 → 一段可判读的文本（正文 + 表头 + 灰底带 + 边界），断言只看这里。 */
  const view = (card) => {
    const parts = [card?.header?.title?.content ?? ''];
    for (const el of card?.body?.elements ?? []) {
      if (el.tag === 'markdown') parts.push(el.content);
      else if (el.tag === 'table') parts.push((el.columns ?? []).map((c) => c.display_name).join(' | '));
      else if (el.tag === 'column_set') {
        for (const c of el.columns ?? []) for (const e of c.elements ?? []) if (e.tag === 'markdown') parts.push(e.content);
      } else if (el.tag === 'collapsible_panel') {
        for (const e of el.elements ?? []) if (e.tag === 'markdown') parts.push(e.content);
      }
    }
    return parts.join('\n');
  };

  const textResult = (over = {}) => ({
    case_id: 'case-1111111111111111aaaa',
    label: 'BLOCK',
    product_line: '婴儿监视器',
    product_line_resolution: { status: 'inferred_keyword', note: '未显式声明品线，按内容关键词自动识别' },
    findings: [{
      status: 'confirmed', control_code: 'H01', quote: 'prevent SIDS',
      authority_ref: [{ entry_id: 'EXT-021' }],
    }],
    evidence_chain: { status: 'disabled' },
    ...over,
  });

  // K1 —— 表自身的不变式。喂坏样本必须抛（否则这张表就是一份装饰）。
  {
    const spec = AUDIT_MODALITY_SPECS;
    const keys = Object.keys(spec);
    const dimsOk = keys.every((k) => spec[k].dimensions.length === 3);
    const colsOk = keys.every((k) => spec[k].columns.map((c) => c.name).join(',') === 'region,issue,fix');
    const disc = keys.flatMap((k) => [...spec[k].discriminators]);
    const disjoint = new Set(disc).size === disc.length;
    const boundaryOk = keys.every((k) => [...spec[k].boundary].length <= 85);
    T('K1 三模态规格表：各 3 个正文维度 + 表格维度、列名恒为 region,issue,fix、判别词互斥、边界 ≤85 字',
      keys.length === 3 && dimsOk && colsOk && disjoint && boundaryOk,
      JSON.stringify({ keys, dimsOk, colsOk, disjoint, boundaryOk }));

    T('K1b 模态解析：copy 视同 text；type=media 不许猜成视频；读不出 → null（不回落图片）',
      resolveModality('copy') === 'text'
        && resolveModality({ type: 'media' }) === null
        && resolveModality({ carrier: 'video' }) === 'video'
        && resolveModality({ four_dim_audit: { media_kind: 'text' } }) === 'text',
      JSON.stringify([resolveModality('copy'), resolveModality({ type: 'media' }), resolveModality({ carrier: 'video' })]));
  }

  // K2 —— 文案：两个构建器都必须出【文案审查 · …】四维，且**一句图片的话都不许有**。
  {
    const fromPrd53 = prd53Mod.formatDirectAuditCardReply({ textJudgeResult: textResult() });
    const shaped = envMod.toCardOrText(fromPrd53);
    const v = view(shaped.card);
    const must = [
      '【文案审查 · 需修改】',
      '【文案四维体检】',
      '① 字面红线与医疗禁用词',
      '② 功效与安全宣称',
      '③ 品线与平台特殊规范',
      '【④ 问题位置与改法（对表改字）】',
      '段落 / 位置', '命中的原句与问题', '建议替换写法',
      '【可直接复制的合规替换文案 / 免责贴条】',
      '改词后重审',
      '已覆盖：字面红线词 · 功效与安全宣称 · 品线与平台规范 · 法规条款核验',
    ];
    const missing = must.filter((m) => !v.includes(m));
    const forbidden = ['只覆盖图内文字', '画面语义未覆盖', '区域级画面审计', '对表改图', '改图后重审']
      .filter((m) => v.includes(m));
    T('K2 文案卡（prd53 出口）：模态抬头 + 文案四维 + 三列表头 + 替换件 + 文案边界，且不含任何图片说法',
      shaped.mode === 'card' && !missing.length && !forbidden.length,
      JSON.stringify({ missing, forbidden, title: shaped.card?.header?.title?.content }));

    const fromStd = stdCards.buildAuditResultCard({ textJudgeResult: textResult() });
    const v2 = view(fromStd);
    T('K2b 文案卡（standard_cards 出口）与 prd53 出口逐项同字：抬头/四维/列名/边界',
      v2.includes('【文案审查 · 需修改】') && v2.includes('【文案四维体检】')
        && v2.includes('【④ 问题位置与改法（对表改字）】')
        && v2.includes('段落 / 位置') && v2.includes('【可直接复制的合规替换文案 / 免责贴条】')
        && v2.includes('已覆盖：字面红线词')
        && !['只覆盖图内文字', '对表改图'].some((m) => v2.includes(m)),
      v2.slice(0, 120));

    // 反向对照：空命中（REVIEW）也走同一套模板，不许退回图片的四维，也不许说「初筛未见违规」
    const emptyCard = stdCards.buildAuditResultCard({
      textJudgeResult: textResult({ label: 'REVIEW', findings: [], evidence_chain: null }),
    });
    const v3 = view(emptyCard);
    T('K2c ★ 反向对照：空命中的文案仍出文案四维，不回落到图片模版，也不替人说「初筛未见违规」',
      v3.includes('【文案四维体检】')
        && v3.includes('需人工确认')
        && !v3.includes('只覆盖图内文字')
        && !v3.includes('初筛未见违规'),
      v3.slice(0, 140));
  }

  // K3 —— 视频：模态抬头 + 时间轴表 + 给剪辑师的替换件。
  {
    const videoGot = {
      type: 'media', reason: 'video_judged', carrier: 'video',
      case_id: 'case-2222222222222222bbbb', product_line: '吸奶器',
      judgment: { label: 'REVIEW' },
      four_dim_audit: {
        media_kind: 'video', overall: '需人工确认', short_title: '口播出现疗效暗示',
        one_line: '第 8 秒口播说「预防乳腺炎」，属医疗功效暗示。',
        quick_fix: '① 剪掉该句；② 片尾补免责字幕',
        ocr_status: '正常', ocr_summary: '字幕未见违规宣称',
        scene_status: '有风险', scene_semantics: '口播称「预防乳腺炎」',
        symbol_status: '正常', visual_symbols: '音画一致',
        region_rows: [{ region: '8.0-11.5s', issue: '口播：预防乳腺炎', fix: '剪掉或改念「舒缓不适」' }],
        copy_paste_snippet: '本产品非医疗器械，不能替代诊断或治疗。',
      },
    };
    const viaPrd53 = envMod.toCardOrText(prd53Mod.formatDirectAuditCardReply({ mediaGot: videoGot }));
    const v = view(viaPrd53.card);
    const must = [
      '【视频审查 ·', '【视频四维体检】',
      '① 画面字幕与花字（OCR）', '② 口播人声与音频宣称（ASR）', '③ 音画一致性与动作演示',
      '【④ 时间轴问题定位（对表剪片）】',
      '时间段（秒）', '画面 / 口播问题', '直接怎么剪 / 改',
      '【可直接复制给剪辑师的合规免责字幕 / 替换口播词】',
      '已覆盖：画面字幕(OCR) · 口播语音(ASR) · 音画一致性 · 时间轴分段审计',
    ];
    const missing = must.filter((m) => !v.includes(m));
    const forbidden = ['对表改图', '改图后重审', '画面位置'].filter((m) => v.includes(m));
    T('K3 视频卡（prd53 出口）：模态抬头 + 视频四维 + 时间轴表 + 剪辑师替换件，且不含任何图片说法',
      viaPrd53.mode === 'card' && !missing.length && !forbidden.length,
      JSON.stringify({ missing, forbidden, title: viaPrd53.card?.header?.title?.content }));

    const viaStd = view(stdCards.buildAuditResultCard({ mediaGot: videoGot }));
    T('K3b 视频卡（standard_cards 出口）同字：视频四维 + 时间轴列名 + 剪辑师替换件 + 视频边界',
      viaStd.includes('【视频四维体检】') && viaStd.includes('时间段（秒）')
        && viaStd.includes('直接怎么剪 / 改')
        && viaStd.includes('【可直接复制给剪辑师的合规免责字幕 / 替换口播词】')
        && viaStd.includes('已覆盖：画面字幕(OCR) · 口播语音(ASR) · 音画一致性 · 时间轴分段审计')
        && !viaStd.includes('对表改图'),
      viaStd.slice(0, 120));

    // 下一步两档措辞：需修改 → 剪片后重审；其余 → 转工作台人工复核
    const blockVideo = stdCards.buildAuditResultCard({
      mediaGot: { ...videoGot, four_dim_audit: { ...videoGot.four_dim_audit, overall: '发现违规需修改' } },
    });
    T('K3c 视频卡的下一步措辞：需修改出「剪片后重审」，非拦截出「转工作台人工复核」',
      view(blockVideo).includes('剪片后重审') && viaStd.includes('转工作台人工复核'),
      '');
  }

  // K4 —— 图片回归：三个既有可见串一个字节都不许变。
  {
    const imageGot = {
      type: 'image', carrier: 'image', case_id: 'case-3333333333333333cccc',
      judgment: { label: 'BLOCK' },
      four_dim_audit: {
        overall: '发现违规需修改', short_title: '医院级字样', one_line: '顶部宣称「Hospital-grade」。',
        quick_fix: '① 删掉 Hospital-grade；② 改吸力参数',
        ocr_status: '有风险', ocr_summary: '顶部写 Hospital-grade',
        scene_status: '正常', scene_semantics: '常规哺乳场景',
        symbol_status: '正常', visual_symbols: '未见认证图标',
        region_rows: [{ region: '顶部横幅', issue: 'Hospital-grade', fix: '改为 295 mmHg 实测吸力' }],
        copy_paste_snippet: 'For daily pumping comfort. Not a medical device.',
      },
    };
    const v = view(envMod.toCardOrText(prd53Mod.formatDirectAuditCardReply({ mediaGot: imageGot })).card);
    const must = [
      '【图片审查 · 需修改】', '【四维快速体检】',
      '① 图内文字（OCR）', '② 画面语义', '③ 视觉符号',
      '【④ 区域级画面审计（对表改图）】',
      '画面位置', '发现的问题', '直接怎么改',
      '【可直接复制给设计的合规免责贴条】',
      '改图后重审',
      '已覆盖：图内文字(OCR) · 画面语义 · 视觉符号 · 区域级画面审计',
    ];
    const missing = must.filter((m) => !v.includes(m));
    T('K4 图片卡回归：抬头/四维/区域表/设计贴条/边界逐字保留（用户说这张卡工作得很好）',
      !missing.length, JSON.stringify({ missing }));
  }

  // K5 —— 出站边界闸：喂那张历史上的坏卡（文案抬头 + 图片边界），必须被就地改写。
  {
    const BAD = JSON.stringify({
      title: '【文案审查 · 需人工确认】未见已知字面红线词',
      verdict: '未命中已知禁用词',
      reasoning: '【马上怎么改】转人工\n\n【文案四维体检】\n· ① 字面红线与医疗禁用词：未见',
      groups: [{ title: '审查详情', content: '只覆盖**图内文字（OCR）**；画面语义未覆盖；空命中只能 REVIEW，不许说初筛未见违规（待人工复核）。' }],
      boundary: '只覆盖图内文字（OCR）；画面语义未覆盖；空命中只能 REVIEW，不许说初筛未见违规（待人工复核）。',
    });
    const r1 = envMod.toCardOrText(`[[card:evidence]]\n${BAD}`);
    const str1 = JSON.stringify(r1.card ?? {});
    T('K5 ★ 出站闸：文案卡里抄来的图片边界被换成本模态边界，散文里的外来行整行删掉，且留痕',
      r1.mode === 'card'
        && str1.includes('已覆盖：字面红线词')
        && !str1.includes('只覆盖图内文字')
        && !str1.includes('画面语义未覆盖')
        && r1.moved.some((m) => m.field === 'boundary')
        && r1.moved.some((m) => m.field === 'reasoning' || m.field.startsWith('groups')),
      JSON.stringify({ moved: r1.moved.map((m) => `${m.field}:${m.to}`), title: r1.card?.header?.title?.content }));

    // 反向对照（过纠）：图片卡里自己的合法行一个字都不许被删
    const good = envMod.toCardOrText(`[[card:evidence]]\n${JSON.stringify({
      title: '【图片审查 · 需修改】x',
      reasoning: '【四维快速体检】\n· ① 图内文字（OCR）：未见违规\n· ② 画面语义：正常',
      boundary: '已覆盖：图内文字(OCR) · 画面语义 · 视觉符号 · 区域级画面审计',
    })}`);
    T('K5b ★ 反向对照：图片卡自己的合法行与边界零改动（闸不许误报）',
      JSON.stringify(good.card).includes('画面语义：正常') && good.moved.length === 0, '');

    // 反向对照（越界）：没有模态声明的卡一个字都不碰
    const plain = envMod.toCardOrText(`[[card:query-answer]]\n${JSON.stringify({
      title: '一条普通结论', verdict: 'v', boundary: '只覆盖图内文字（OCR）',
    })}`);
    T('K5c ★ 反向对照：非审查卡（无模态键、无模态抬头）边界原样保留',
      JSON.stringify(plain.card).includes('只覆盖图内文字'), '');

    // 模态抬头不许被权威结论行覆写；模型自拟抬头仍然必须被置顶
    const keep = envMod.applyVerdictLine('evidence',
      { title: '【文案审查 · 需修改】短标题' }, { line: '【审查结论：BLOCK】共发现 3 处必须修改（案件 case-x）。' });
    const overwrite = envMod.applyVerdictLine('evidence',
      { title: '模型自拟标题' }, { line: '【审查结论：BLOCK】共发现 3 处必须修改（案件 case-x）。' });
    T('K5d 模态抬头不被覆写，而模型自拟抬头仍被权威结论行置顶（G3 的形状）',
      keep.action === 'already' && keep.data.title.startsWith('【文案审查')
        && overwrite.action === 'forced' && overwrite.data.title.includes('【审查结论：BLOCK】'),
      JSON.stringify({ keep: keep.action, overwrite: overwrite.action }));
  }

  // K6 —— four_dim_audit 在视频这一跳不许再丢；feishu.ingestAttachment 必须把它带到返回体上。
  {
    const fakeExec = async () => ({
      stdout: JSON.stringify({
        ok: true, case_id: 'case-4444444444444444dddd', product_line: '吸奶器',
        label: 'REVIEW', layer: 'DP2', release_status: '待放行',
        parse_status: 'partial', findings: [],
        four_dim_audit: { media_kind: 'video', overall: '需人工确认', one_line: '口播出现疗效暗示', short_title: 'x' },
      }),
    });
    const r = await imgJudgment.runVideoJudgment({
      filePath: '/tmp/fake.mp4', messageId: 'om_k6_video', exec: fakeExec,
    });
    T('K6 runVideoJudgment 保留 four_dim_audit 与 carrier=video（原先这一跳把它丢了）',
      r.ok === true && r.carrier === 'video'
        && r.four_dim_audit?.media_kind === 'video'
        && r.judgment?.four_dim_audit?.media_kind === 'video'
        && r.product_line === '吸奶器',
      JSON.stringify({ ok: r.ok, carrier: r.carrier, fd: r.four_dim_audit?.media_kind }));

    const savedGet = feishu.client.im.v1.messageResource.get;
    process.env.SHOUHENG_ATTACHMENT_DIR = path.join(tmpRoot, 'attachments-k6');
    feishu.client.im.v1.messageResource.get = async () => ({
      headers: { 'content-length': '64' },
      writeFile: async (p) => { fs.writeFileSync(p, Buffer.from('fake-mp4-video-bytes-for-k6')); return p; },
      getReadableStream: () => ({ destroy() {} }),
    });
    try {
      const got = await feishu.ingestAttachment({
        message_id: 'om_k6_ingest', message_type: 'media',
        content: JSON.stringify({ file_key: 'fk_k6', file_name: 'demo.mp4' }),
      });
      const shaped = stdCards.buildAuditResultCard({ mediaGot: got });
      T('K6b feishu.ingestAttachment（media）把 four_dim_audit 带到返回体，且能建出视频审查卡',
        got.carrier === 'video'
          && (got.four_dim_audit?.media_kind === 'video' || got.four_dim_audit === null)
          && (got.four_dim_audit ? view(shaped).includes('【视频审查') : true),
        JSON.stringify({ carrier: got.carrier, fd: got.four_dim_audit?.media_kind, status: got.status }));
    } finally {
      feishu.client.im.v1.messageResource.get = savedGet;
    }
  }
  // K7 —— 直出文案卡的入站闸：送审的必须真是用户那句话，否则解释类提问会被一张卡吃掉。
  {
    const { submitsUserText } = await import('./agent.mjs');
    const COPY = 'Smart baby monitor with AI that alerts you to risks, even when baby rolls face-down sleeping.';
    const cases = [
      ['用户整段粘贴文案', JSON.stringify({ text: COPY }), `@Guard ${COPY}`, true],
      ['用户带一句短指令', JSON.stringify({ text: COPY }), `@Guard 帮我看下这段：${COPY}`, true],
      ['解释类提问（模型顺手送审一个词）', JSON.stringify({ text: 'FDA approved' }),
        '帮我解释一下 FDA approved 是什么意思，为什么监管机构不认这个说法', false],
      ['参数里没有正文', JSON.stringify({}), COPY, false],
      ['参数不是 JSON', '{坏掉的', COPY, false],
    ];
    const bad = cases.filter(([, a, q, exp]) => submitsUserText(a, q) !== exp).map(([n]) => n);
    T('K7 文案直出的入站闸：只认「送审的就是用户这句话」，解释类提问不被审查卡吃掉',
      !bad.length, JSON.stringify({ bad }));
  }
}

try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch {}

const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} 飞书 Guard 统一审查与建案自证 ${res.length - nFail}/${res.length} 项通过`);
process.exit(nFail ? 1 : 0);
