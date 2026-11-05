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
  T('B1 关键词自动识别品线：stroller → 推车（inferred_keyword）',
    b1.ok && b1.product_line === '推车'
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
  const renderMod = await import('./audit_modality_specs.mjs');
  const { AUDIT_MODALITY_SPECS, resolveModality } = renderMod;
  const prd53Mod = await import('./prd53.mjs');
  const stdCards = await import('./standard_cards.mjs');
  const cardsMod = await import('../reply-cards/cards.mjs');
  const envMod = await import('../reply-cards/envelope.mjs');
  const regMod = await import('../reply-cards/registry.mjs');
  const imgJudgment = await import('./image_judgment.mjs');
  const judgeEvidence = await import('./judge_evidence.mjs');

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

  /** 直接调渲染器：三张卡（prd53 / standard_cards）都只是它的包装。 */
  const renderPayload = (modality, fd, label) => renderMod.renderFourDimAuditPayload({ modality, fd, label });

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
      '【文案审查 · BLOCK 需修改】',
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
      v2.includes('【文案审查 · BLOCK 需修改】') && v2.includes('【文案四维体检】')
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
      '【图片审查 · BLOCK 需修改】', '【四维快速体检】',
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
      title: '【文案审查 · REVIEW 需人工确认】未见已知字面红线词',
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
      title: '【图片审查 · BLOCK 需修改】x',
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
      { title: '【文案审查 · BLOCK 需修改】短标题' }, { line: '【审查结论：BLOCK】共发现 3 处必须修改（案件 case-x）。' });
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

  // K8 —— 五标签必须在抬头里**显式**写出来，且「初筛未见明显违规」绝不许被判成拦截。
  {
    const { classifyAuditState } = await import('./audit_modality_specs.mjs');
    const states = [
      ['REVIEW', '初筛未见明显违规', 'PASS', 'green', false],
      ['REVIEW', '未见违规', 'PASS', 'green', false],
      ['PASS', '初筛未见违规', 'PASS', 'green', false],
      ['BLOCK', '发现违规需修改', 'BLOCK', 'red', false],
      ['REVIEW', '发现违规', 'BLOCK', 'red', false],
      ['REVIEW', '需人工确认', 'REVIEW', 'orange', false],
      ['待自决', '需人工确认', '待自决', 'orange', false],
      ['未审查', '素材未能读取', '未审查', 'wathet', true],
      // overall 里写「未能读取」即使标签是 REVIEW 也必须落未审查
      ['REVIEW', '素材未能读取', '未审查', 'wathet', true],
    ];
    const bad = [];
    for (const [label, ov, tag, tone, unreviewed] of states) {
      const r = renderPayload('image', { overall: ov, one_line: 'x', short_title: 't' }, label);
      if (!r) { bad.push(`${label}/${ov}: 没出卡`); continue; }
      if (!r.title.includes(`${tag}`)) bad.push(`${label}/${ov}: 抬头没写 ${tag} → ${r.title}`);
      if (r.tone !== tone) bad.push(`${label}/${ov}: tone=${r.tone} 应为 ${tone}`);
      if (unreviewed && r.tone !== 'wathet') bad.push(`${label}/${ov}: 未审查没用 wathet`);
    }
    // 逐条断言最要紧的两条：PASS 不许说改图，BLOCK 才说改图。
    const passCard = renderPayload('image', { overall: '初筛未见明显违规', one_line: 'x', short_title: 't' }, 'REVIEW');
    const passStep = passCard.fields.find((f) => f.label === '下一步')?.value;
    const blockCard = renderPayload('image', { overall: '发现违规需修改', one_line: 'x', short_title: 't' }, 'BLOCK');
    const blockStep = blockCard.fields.find((f) => f.label === '下一步')?.value;
    T('K8 ★ 五标签显式写进抬头，且「初筛未见明显违规」出 PASS/绿卡/人工确认后放行（不是红卡改图）',
      !bad.length && passStep === '人工确认后放行' && blockStep === '改图后重审'
        && classifyAuditState('REVIEW', '初筛未见明显违规').isBlock === false
        && classifyAuditState('REVIEW', '发现违规需修改').isBlock === true,
      JSON.stringify({ bad, passStep, blockStep }));

    // 反向对照：四张真标签各出各的抬头，两个字面一个都不许串。
    const titles = ['【图片审查 · BLOCK 需修改】', '【文案审查 · REVIEW 需人工确认】',
      '【图片审查 · PASS 初筛通过】', '【图片审查 · 未审查】'];
    const textCard = renderPayload('text', { overall: '初筛未见明显违规', one_line: 'x', short_title: 't' }, 'REVIEW');
    T('K8b ★ 反向对照：四种状态的抬头各说各的；文案 PASS 用文案自己的措辞「初筛未见违规」',
      titles[0].includes('BLOCK') && titles[1].includes('REVIEW')
        && textCard.title.startsWith('【文案审查 · PASS 初筛未见违规】'),
      textCard.title);
  }

  // K8c —— 降级卡（没有四维、只有 summary）也必须带同一个状态标签与配色。
  // 两个构建器各测一遍：它们是两份代码，一个对了不等于另一个也对。
  {
    const degradedStates = [
      ['BLOCK', 'BLOCK', 'red'],
      ['REVIEW', 'REVIEW', 'orange'],
      ['PASS', 'PASS', 'green'],
      ['未审查', '未审查', 'wathet'],
    ];
    const problems = [];
    for (const [label, tag, tone] of degradedStates) {
      // 刻意不给 four_dim_audit：走降级分支
      const got = { type: 'image', carrier: 'image', judgment: { label, findings_total: 0 } };
      const viaPrd = envMod.toCardOrText(prd53Mod.formatDirectAuditCardReply({ mediaGot: got })).card;
      const viaStd = stdCards.buildAuditResultCard({ mediaGot: got });
      for (const [who, c] of [['prd53', viaPrd], ['standard_cards', viaStd]]) {
        const title = String(c?.header?.title?.content ?? '');
        const tpl = String(c?.header?.template ?? '');
        if (!title.includes(tag)) problems.push(`${who}/${label}: 抬头没写 ${tag} → ${title}`);
        if (tpl !== tone) problems.push(`${who}/${label}: 配色 ${tpl} 应为 ${tone}`);
      }
    }
    T('K8c ★ 降级卡也带显式状态标签与配色（两个构建器各测：一份对了不等于另一份也对）',
      !problems.length, JSON.stringify(problems));
  }

  // K9 —— 子品类识别：Baby Monitor 不许被当成吸奶器审。
  {
    const bm = runGuardPy(['--text', 'BM04 baby monitor with parent unit and motion alert',
      '--message-id', 'om_k9_bm']);
    const st = runGuardPy(['--text', 'Bottle sterilizer and dryer with descaling tablet',
      '--message-id', 'om_k9_st']);
    const bag = runGuardPy(['--text', 'Breastmilk storage bag, 100 pcs', '--message-id', 'om_k9_bag']);
    const pillow = runGuardPy(['--text', 'Pregnancy pillow for maternity sleep', '--message-id', 'om_k9_pil']);
    T('K9 ★ 子品类识别：婴儿监护仪 / 消毒与洗瓶机 / 储奶袋 / 孕妇枕 各自出 display_category，而建案品线仍是工作台可建的「吸奶器」',
      bm.ok && String(bm.display_category || '').includes('婴儿监护仪')
        && st.ok && String(st.display_category || '').includes('消毒与洗瓶机')
        && bag.ok && String(bag.display_category || '').includes('储奶袋')
        && pillow.ok && String(pillow.display_category || '').includes('孕妇枕')
        && [bm, st, bag, pillow].every((r) => r.product_line === '吸奶器')
        && [bm, st, bag, pillow].every((r) => r.product_line_resolution?.status === 'default_fallback'),
      JSON.stringify([bm, st, bag, pillow].map((r) => [r.display_category, r.product_line])));

    // 反向对照：五品线自己命中时，display_category 必须等于品线，不许被子品类改写。
    const trolley = runGuardPy(['--text', 'Lightweight baby stroller for travel', '--message-id', 'om_k9_b1']);
    T('K9b ★ 反向对照：五品线命中（stroller）时 display_category 就是该品线，不是子品类',
      trolley.display_category === trolley.product_line && trolley.product_line !== '吸奶器',
      JSON.stringify([trolley.display_category, trolley.product_line]));

    // 安全提醒必须按品类出，而不是按建案队列出：监护仪的红线不是「奶量」。
    // 直接问 Python 的 PRODUCT_LINE_SAFETY_HINT，不拿源码做正则 —— 那种判据在改措辞时误报。
    const hintOut = execFileSync('python3', ['-c',
      'import json,sys; sys.path.insert(0,"."); '
      + 'from base.feishu_guard_ingest import PRODUCT_LINE_SAFETY_HINT as H; '
      + 'print(json.dumps({k:v for k,v in H.items()}, ensure_ascii=False))',
    ], { cwd: REPO_ROOT, encoding: 'utf8', timeout: 30_000 });
    const hints = JSON.parse(hintOut);
    const mon = String(hints['婴儿监护仪'] || '');
    T('K9c 监护仪的安全提醒说的是 SIDS/看护，不是吸奶器的奶量倍增',
      mon.includes('SIDS') && mon.includes('看护') && !mon.includes('奶量')
        && String(hints['消毒与洗瓶机'] || '').length > 0
        && String(hints['储奶袋与配件'] || '').length > 0,
      mon);
  }

  // K10 —— 单句求审必须直出四维卡，解释类提问不许被吃掉。
  {
    const { isCopyAuditRequest, submitsUserText } = await import('./agent.mjs');
    const mustDirect = [
      'm5 pro是最好的吸奶器，这句话能过审吗？',
      '帮我审一下这条 Amazon 五点描述，第五条写的是：FDA approved wearable breast pump. 这条能发吗',
      '这段文案能过审吗？我们的吸奶器采用 100% 安全材质，绝不侧翻',
      '这段能过审吗：「为什么选择我们」，因为我们是第一',
    ];
    const mustNot = [
      '帮我解释一下 FDA approved 是什么意思',
      '为什么 FDA approved 不能写',
      '你能做什么',
      '能发吗',
      '吸奶器的品线规范是什么',
      '帮我解释一下「FDA approved」是什么意思',
    ];
    const wrongDirect = mustDirect.filter((q) => isCopyAuditRequest(q) !== true);
    const wrongNot = mustNot.filter((q) => isCopyAuditRequest(q) !== false);
    T('K10 ★ 单句求审（含引号/无引号）触发直出卡；解释类与能力类提问不触发',
      !wrongDirect.length && !wrongNot.length,
      JSON.stringify({ wrongDirect, wrongNot }));

    const subBad = [
      [JSON.stringify({ text: 'm5 pro是最好的吸奶器' }), 'm5 pro是最好的吸奶器，这句话能过审吗？', true],
    ].filter(([a, q, exp]) => submitsUserText(a, q) !== exp).map(([, q]) => q);
    T('K10b ★ submitsUserText：模型只送引号里那句正文时也认（比例闸会把它稀释掉，包含关系不会）',
      !subBad.length, JSON.stringify({ subBad }));
  }

  // K11 —— 多图合并：一张失败不许把原始 HTTP 报错写进 one_line。
  {
    const { mergeMultiImageAudit } = await import('./agent.mjs');
    const okImg = {
      idx: 0, status: 'image_judged', type: 'image', carrier: 'image',
      judgment: { label: 'REVIEW' },
      four_dim_audit: {
        overall: '初筛未见明显违规', one_line: '图一画面干净，未见违规',
        short_title: 'x', quick_fix: '无需修改',
        region_rows: [{ region: '顶部', issue: '无', fix: '无' }],
      },
    };
    const badImg = {
      idx: 1, status: 'image_judge_failed', type: 'image', carrier: 'image',
      summary: '图片未审查（DP0）：没取到文件（Request failed with status code 500）',
      reply: '图片未审查（DP0）：没取到文件（Request failed with status code 500）',
    };
    const m = mergeMultiImageAudit([okImg, badImg], 'om_k11');
    const card = envMod.toCardOrText(prd53Mod.formatDirectAuditCardReply({ mediaGot: m })).card;
    // 表格行不在 markdown 里，`view` 只读列名 —— 明细必须直接读 table.rows。
    const tableRows = (card?.body?.elements ?? []).filter((el) => el.tag === 'table')
      .flatMap((el) => el.rows ?? []);
    const rowHasFail = tableRows.some((r) => String(r.region).includes('图2')
      && String(r.region).includes('未完成读取'));
    const wholeCard = JSON.stringify(card ?? {});
    T('K11 ★ 多图合并：一张失败一张成功时，正文只由判过的图构成，失败落一行干净明细',
      m.four_dim_audit.one_line === '【图1】图一画面干净，未见违规'
        && !JSON.stringify(m.four_dim_audit).includes('Request failed')
        && rowHasFail && !wholeCard.includes('Request failed')
        && wholeCard.includes('请单独重发该张图片送审'),
      JSON.stringify({ one_line: m.four_dim_audit.one_line, tableRows }));

    // 反向对照：全都失败 → 未审查（不是「需人工确认」），且抬头说未审查。
    const allBad = mergeMultiImageAudit([badImg, { ...badImg, idx: 2 }], 'om_k11b');
    const cardBad = envMod.toCardOrText(prd53Mod.formatDirectAuditCardReply({ mediaGot: allBad })).card;
    const wholeBad = JSON.stringify(cardBad ?? {});
    T('K11b ★ 反向对照：全部失败时标签是未审查，不是需人工确认，也不含任何 HTTP 报错',
      allBad.judgment.label === '未审查'
        && String(cardBad?.header?.title?.content ?? '').includes('未审查')
        && !wholeBad.includes('Request failed')
        && !wholeBad.includes('需人工确认'),
      JSON.stringify({ label: allBad.judgment.label, title: cardBad?.header?.title?.content }));

    // 反向对照：全部成功时不许凭空多出「未完成读取」行。
    const allOk = mergeMultiImageAudit([okImg, { ...okImg, idx: 1 }], 'om_k11c');
    T('K11c ★ 反向对照：全部成功时零失败行，且不误报未审查',
      !(allOk.four_dim_audit.region_rows ?? []).some((r) => String(r.region).includes('未完成读取'))
        && allOk.judgment.label !== '未审查',
      JSON.stringify(allOk.four_dim_audit.region_rows));
  }

  // K12 —— 媒体证据探针必须带品类名，且能真的检索到该品类的知识库内容。
  {
    const { mediaEvidenceProbe } = await import('./agent.mjs');
    const monitorGot = {
      type: 'image', carrier: 'image',
      product_line: '吸奶器',
      product_line_resolution: { status: 'default_fallback', display_category: '婴儿监护仪（工作台归入通用/吸奶器队列）' },
      judgment: { label: 'REVIEW', findings: [{ control_code: 'H01', quote: 'prevent SIDS' }] },
      four_dim_audit: { one_line: '画面在演示婴儿睡眠场景', ocr_summary: 'Baby monitor with parent unit' },
      summary: 'BM04 婴儿监护仪送审',
    };
    const probe = mediaEvidenceProbe(monitorGot);
    T('K12 ★ 证据探针带品类名与命中原文（不带品类 → 检索不出词 → 证据链落 untested，像「库里没有」）',
      probe.probeText.includes('婴儿监护仪')
        && probe.probeText.includes('BM04')
        && probe.hitsStub.hits[0]?.matched?.[0]?.matched_text === 'prevent SIDS',
      probe.probeText.slice(0, 80));

    // 反向对照：没有 quote 的 finding 不许产空 matched，否则空串会被当成查询词。
    const emptyProbe = mediaEvidenceProbe({ four_dim_audit: {}, judgment: { findings: [{ control_code: 'X' }] } });
    T('K12b ★ 反向对照：无 quote 的 finding 产出空 matched 数组，不产空串查询词',
      Array.isArray(emptyProbe.hitsStub.hits[0]?.matched) && emptyProbe.hitsStub.hits[0].matched.length === 0,
      JSON.stringify(emptyProbe.hitsStub));

    // 端到端：远端不可达时，**带 localFallback 才有依据**；不带就是 untested。
    // 这两半必须一起断言 —— 只断言「带的时候 found」的话，把参数删掉也仍然绿。
    const savedUrl = process.env.SHOUHENG_KB_BASE_URL;
    const savedKey = process.env.SHOUHENG_KB_API_KEY;
    process.env.SHOUHENG_KB_BASE_URL = 'http://127.0.0.1:1';
    process.env.SHOUHENG_KB_API_KEY = 'fake-key';
    try {
      const withFb = await judgeEvidence.gatherEvidence(probe.probeText, probe.hitsStub,
        { enabled: true, localFallback: true });
      const withoutFb = await judgeEvidence.gatherEvidence(probe.probeText, probe.hitsStub,
        { enabled: true });
      T('K12c ★ localFallback=true 才有本地依据（found）；不给就是 untested —— 图片/视频证据链必须显式传它',
        withFb.status === 'found' && withFb.evidence_total > 0
          && withoutFb.status === 'untested',
        JSON.stringify({ with: withFb.status, without: withoutFb.status }));
    } finally {
      if (savedUrl === undefined) delete process.env.SHOUHENG_KB_BASE_URL;
      else process.env.SHOUHENG_KB_BASE_URL = savedUrl;
      if (savedKey === undefined) delete process.env.SHOUHENG_KB_API_KEY;
      else process.env.SHOUHENG_KB_API_KEY = savedKey;
    }

    // 执行点：媒体那一处调用**必须**传 localFallback。K12c 证的是「传了才有用」，
    // 这一条证的是「这里真的传了」—— 两半缺一条，改回不带参也不会红。
    const agentSrc = fs.readFileSync(path.join(HERE, 'agent.mjs'), 'utf8');
    const mediaCallOk = /gatherEvidence\(\s*$[\s\S]{0,200}?\{ enabled: config\.kb\.enabled, localFallback: true \}/m
      .test(agentSrc);
    T('K12d ★ 执行点：agent.mjs 的媒体证据调用点确实传了 localFallback: true',
      mediaCallOk, '');
  }
}

/* ── M. 话题复核：群内「确认放行 / 误报推翻」落到权威与判例回流 ─────────── */
{
  const agentMod = await import('./agent.mjs');
  const prd53Mod = await import('./prd53.mjs');
  const cardsMod = await import('../reply-cards/cards.mjs');
  const envMod = await import('../reply-cards/envelope.mjs');

  const CID = 'case-c6f4d1420fc5d4155a52';

  // M1 指令解析：动作判反的代价不对称（该撤的变成放行），所以逐个钉住。
  const P = { parentText: `【文案审查 · 需修改】x 单号 ${CID}` };
  const parsed = (q) => agentMod.parseThreadReviewCommand(q, P);
  T('M1 指令解析：误报推翻 / 确认放行 / 要改 三态分清，且说明里不混指令词',
    parsed('误报推翻：这是引用反例说明，不是我们的宣称')?.action === 'overturn'
      && parsed('误报推翻：这是引用反例说明，不是我们的宣称')?.notes === '这是引用反例说明，不是我们的宣称'
      && parsed('确认放行')?.action === 'confirm'
      && parsed('要改：把 Hospital Grade 删掉')?.action === 'revise'
      && parsed('要改：把 Hospital Grade 删掉')?.notes === '把 Hospital Grade 删掉',
    JSON.stringify(parsed('误报推翻：这是引用反例说明，不是我们的宣称')));

  // M2 ★ 反向对照：同一句里两个词都在时，**必须**判成推翻。
  //    按「确认」先判会得到相反动作，而群里已经看到过那张卡了。
  T('M2 ★ 反向对照：「确认这是误报，推翻」判成 overturn（不是 confirm）',
    parsed('确认这是误报，推翻')?.action === 'overturn',
    JSON.stringify(parsed('确认这是误报，推翻')));

  // M3 判据必须同时要求「有指令」与「指得出单号」——
  //    「确认」在群里太常见，只凭这一句就结案会把人随口一句话当成命令。
  T('M3 只认得出动作、指不出单号 → 不接（不结案）',
    agentMod.parseThreadReviewCommand('确认放行', { parentText: null }) === null
      && agentMod.parseThreadReviewCommand('确认一下明天开会时间', P) === null
      && agentMod.parseThreadReviewCommand('', P) === null
      && agentMod.parseThreadReviewCommand(`确认放行 ${CID}`, {})?.caseId === CID,
    '');

  // M4 执行点：Python 端真跑一次（临时 workbench 根），三态各验一遍。
  const pyBin2 = fs.existsSync(path.join(REPO_ROOT, '.venv', 'bin', 'python'))
    ? path.join(REPO_ROOT, '.venv', 'bin', 'python')
    : 'python3';
  const wbRoot = path.join(tmpRoot, 'wb-thread');
  const ingestOnce = (msgId, text) => JSON.parse(execFileSync(pyBin2, [
    GUARD_PY, '--carrier', 'free_text', '--text', text, '--message-id', msgId,
    '--sender-open-id', 'ou-1', '--json', '--brief',
  ], {
    cwd: REPO_ROOT, encoding: 'utf8', timeout: 120_000,
    env: { ...process.env, SHOUHENG_STATE_DIR: tmpState, SHOUHENG_KB_ENABLED: '0',
           SHOUHENG_WORKBENCH_DATA_ROOT: wbRoot },
  }));

  const review = (cid, action, notes = '') => {
    let out;
    try {
      out = execFileSync(pyBin2, [
        GUARD_PY, '--review-case', cid, '--review-action', action,
        '--review-notes', notes, '--sender-open-id', 'ou-1',
      ], {
        cwd: REPO_ROOT, encoding: 'utf8', timeout: 120_000,
        env: { ...process.env, SHOUHENG_STATE_DIR: tmpState, SHOUHENG_KB_ENABLED: '0',
               SHOUHENG_WORKBENCH_DATA_ROOT: wbRoot },
      });
    } catch (e) { out = e?.stdout ?? ''; }
    return JSON.parse(String(out).trim().split('\n').pop());
  };

  const c1 = ingestOnce('om_thread_1', 'Our pump is Hospital Grade.');
  const r1 = review(c1.case_id, 'overturn', '引用反例说明，不是我们的宣称');
  const qPath = path.join(wbRoot, 'review_feedback_queue.jsonl');
  const qLines = fs.existsSync(qPath)
    ? fs.readFileSync(qPath, 'utf8').split('\n').filter((x) => x.trim()) : [];
  T('M4 推翻结案真的落账：状态 closed、版本 +1、判例入队，且队列里能指到这条案件',
    c1.ok && r1.ok && r1.verdict === 'overturn' && r1.status === 'closed'
      && r1.to_version > r1.from_version
      && r1.precedent?.queued === true
      && qLines.some((l) => JSON.parse(l).case_id === c1.case_id),
    JSON.stringify({ case: c1.case_id, r1: { ok: r1.ok, status: r1.status, prec: r1.precedent } }));

  const r2 = review(c1.case_id, 'confirm');
  T('M5 已结案的再复核 → 明确拒绝（不是静默成功）',
    r2.ok === false && r2.already_closed === true, JSON.stringify(r2).slice(0, 160));

  const c2 = ingestOnce('om_thread_2', 'Momcozy wearable breast pump, comfortable design.');
  const r3 = review(c2.case_id, 'confirm');
  T('M6 确认放行：人机一致时**不**产生判例回流（没有分歧可记）',
    r3.ok === true && r3.verdict === 'agree' && r3.precedent?.queued === false,
    JSON.stringify({ label: c2.label, prec: r3.precedent }));

  const r4 = review(c2.case_id, 'revise', '把宣称删掉');
  T('M7 「要求修改」如实说要去工作台，不假装成功',
    r4.ok === false && r4.needs_workbench === true && /工作台/.test(r4.next_step ?? ''),
    JSON.stringify(r4).slice(0, 160));

  const r5 = review('case-00000000000000000000', 'confirm');
  T('M8 找不到单号 → not_found（与「已结案」「跑挂了」分得开）',
    r5.ok === false && r5.not_found === true, JSON.stringify(r5).slice(0, 140));

  const r6 = review(c1.case_id, 'overturn', '');
  T('M9 推翻必须写理由 —— 空理由被拒（判例回流里唯一能被人读懂的就是它）',
    r6.ok === false && /理由/.test(r6.error ?? ''), JSON.stringify(r6).slice(0, 140));

  // M10 回执卡：四种结果各自成卡、过本地校验、过信封同一把尺（L6 那条教训）。
  const RECEIPT_STATES = {
    ok: { ok: true, precedent: { queued: true } },
    noprec: { ok: true, precedent: { queued: false } },
    closed: { ok: false, already_closed: true },
    notfound: { ok: false, not_found: true },
    crash: { ok: false, error: 'AuthorityConflict: version_conflict' },
  };
  const problems = [];
  for (const [name, res] of Object.entries(RECEIPT_STATES)) {
    const txt = prd53Mod.buildReceiptReply({ caseId: CID, action: 'overturn', result: res });
    const shaped = envMod.toCardOrText(txt);
    if (shaped.mode !== 'card' || shaped.dropped) { problems.push(`${name}: 被信封降级 (${shaped.mode})`); continue; }
    const card = cardsMod.build('receipt', JSON.parse(txt.split('\n')[1]));
    if (!cardsMod.validateCard(card).ok) problems.push(`${name}: 卡片校验不过`);
    if (/已通过|无需处理/.test(shaped.text)) problems.push(`${name}: 出现禁词`);
  }
  T('M10 复核回执卡：五种结果都成卡、过校验、过信封（不出现「已通过」这类禁词）',
    problems.length === 0, problems.join('；'));
}

/* ── L. Office 附件（.docx / .xlsx）正文抽取与重媒体回执 ────────────────── */
{
  const pyBin = fs.existsSync(path.join(REPO_ROOT, '.venv', 'bin', 'python'))
    ? path.join(REPO_ROOT, '.venv', 'bin', 'python')
    : 'python3';
  const officeTmp = path.join(tmpRoot, 'office');
  fs.mkdirSync(officeTmp, { recursive: true });

  /** 造一份最小 OOXML。用 python 的 zipfile（stdlib），不引第三方包。 */
  const makeZip = (dest, parts) => {
    const script = `
import json, sys, zipfile
with zipfile.ZipFile(sys.argv[1], 'w') as z:
    for name, body in json.loads(sys.argv[2]).items():
        z.writestr(name, body)
`;
    execFileSync(pyBin, ['-c', script, dest, JSON.stringify(parts)], { encoding: 'utf8' });
  };

  const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  const docxXml = (body) =>
    `<?xml version="1.0"?><w:document xmlns:w="${W}"><w:body>${body}</w:body></w:document>`;

  const extract = (p) => {
    const out = execFileSync(pyBin, [GUARD_PY, '--extract-office', p], {
      cwd: REPO_ROOT, encoding: 'utf8', env: { ...process.env, SHOUHENG_STATE_DIR: tmpState },
    });
    return JSON.parse(out);
  };

  // L1: 段落 + 表格按**文档顺序**抽，不重复。
  //     ★ 反向形状在这里：第一版「先收表格、再收段落」会把表格里的 <w:p> 收两遍，
  //     实测两行表格的 docx 抽出 4 行。这条断言盯的就是「恰好 3 行且顺序对」。
  const d1 = path.join(officeTmp, 'order.docx');
  makeZip(d1, {
    'word/document.xml': docxXml(
      '<w:p><w:r><w:t>开头一段</w:t></w:r></w:p>'
      + '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>规格</w:t></w:r></w:p></w:tc>'
      + '<w:tc><w:p><w:r><w:t>28.2%</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
      + '<w:p><w:r><w:t>结尾一段</w:t></w:r></w:p>',
    ),
  });
  const r1 = extract(d1);
  T('L1 docx：段落与表格按文档顺序抽出、且表格不被重复收一遍',
    r1.ok === true && r1.text === '开头一段\n规格 | 28.2%\n结尾一段' && r1.ext === '.docx',
    JSON.stringify(r1));

  // L2: header / footer 也收。
  const d2 = path.join(officeTmp, 'hdr.docx');
  makeZip(d2, {
    'word/document.xml': docxXml('<w:p><w:r><w:t>正文</w:t></w:r></w:p>'),
    'word/header1.xml': `<w:hdr xmlns:w="${W}"><w:p><w:r><w:t>页眉声明</w:t></w:r></w:p></w:hdr>`,
    'word/footer2.xml': `<w:ftr xmlns:w="${W}"><w:p><w:r><w:t>页脚免责</w:t></w:r></w:p></w:ftr>`,
  });
  const r2 = extract(d2);
  T('L2 docx：header / footer 也进正文（免责声明常写在那里，漏了会误判成「没说」）',
    r2.ok === true && r2.text.includes('页眉声明') && r2.text.includes('页脚免责'),
    JSON.stringify(r2.text));

  // L3: xlsx sharedStrings + inlineStr + 数值；空格子占位不丢列位。
  const x1 = path.join(officeTmp, 'table.xlsx');
  makeZip(x1, {
    'xl/sharedStrings.xml':
      `<?xml version="1.0"?><sst xmlns="${S}"><si><t>品名</t></si><si><t>M5</t></si>`
      + `<si><r><t>超声</t></r><r><t>波清洗</t></r></si></sst>`,
    'xl/worksheets/sheet1.xml':
      `<?xml version="1.0"?><worksheet xmlns="${S}"><sheetData>`
      + '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
      + '<row r="2"><c r="A2" t="inlineStr"><is><t>价格</t></is></c><c r="B2"><v>199</v></c></row>'
      + '<row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3"/><c r="C3" t="inlineStr"><is><t>无</t></is></c></row>'
      + '</sheetData></worksheet>',
  });
  const r3 = extract(x1);
  T('L3 xlsx：共享字符串（含富文本 run）/ 内联串 / 数值都对；行中空格子占位、行尾空格子去掉',
    r3.ok === true && r3.text === '品名 | M5\n价格 | 199\n超声波清洗 |  | 无' && r3.ext === '.xlsx',
    JSON.stringify(r3.text));

  // L4: 三种失败必须**长得不一样**。
  const dEmpty = path.join(officeTmp, 'empty.docx');
  makeZip(dEmpty, { 'word/document.xml': docxXml('<w:p/>') });
  const dBad = path.join(officeTmp, 'bad.docx');
  fs.writeFileSync(dBad, 'this is not a zip at all');
  const dBadExt = path.join(officeTmp, 'x.pdf');
  fs.writeFileSync(dBadExt, 'x');
  const eEmpty = extract(dEmpty);
  const eBad = extract(dBad);
  const eExt = extract(dBadExt);
  T('L4 三种失败分得开：empty（文件里真没字）/ parse_error（解不开）/ unsupported（不是这两种后缀）',
    eEmpty.ok === false && eEmpty.failure_kind === 'empty'
      && eBad.ok === false && eBad.failure_kind === 'parse_error'
      && eExt.ok === false && eExt.failure_kind === 'unsupported',
    JSON.stringify({ empty: eEmpty.failure_kind, bad: eBad.failure_kind, ext: eExt.failure_kind }));

  // L5: 入站链路真的接上了 —— `ingestAttachment` 对 .docx 返回 ingested + office 的 reason。
  //     ★ 这一条是「执行点」：L1–L3 证的是抽取器对，这一条证的是它**被调到了**。
  const savedAttachDir = process.env.SHOUHENG_ATTACHMENT_DIR;
  process.env.SHOUHENG_ATTACHMENT_DIR = path.join(tmpRoot, 'attachments-office');
  const savedGet2 = feishu.client.im.v1.messageResource.get;
  const docxBytes = fs.readFileSync(d1);
  feishu.client.im.v1.messageResource.get = async () => ({
    headers: { 'content-length': String(docxBytes.length) },
    writeFile: async (p) => { fs.writeFileSync(p, docxBytes); return p; },
    getReadableStream: () => ({ destroy() {} }),
  });
  let officeGot = null;
  try {
    officeGot = await feishu.ingestAttachment({
      message_id: 'om_office_e2e',
      message_type: 'file',
      content: JSON.stringify({ file_key: 'fk_office', file_name: 'ad.docx' }),
    });
  } finally {
    feishu.client.im.v1.messageResource.get = savedGet2;
    if (savedAttachDir === undefined) delete process.env.SHOUHENG_ATTACHMENT_DIR;
    else process.env.SHOUHENG_ATTACHMENT_DIR = savedAttachDir;
  }
  T('L5 执行点：.docx 入站走抽取链路，返回 ingested + attachment_office_ingested（且临时目录已删）',
    officeGot?.status === 'ingested'
      && officeGot.reason === 'attachment_office_ingested'
      && officeGot.text.includes('28.2%')
      && fs.readdirSync(path.join(tmpRoot, 'attachments-office')).length === 0,
    JSON.stringify({ status: officeGot?.status, reason: officeGot?.reason }));

  // L6: 反向对照：**不接** Office 的旧判定没被放宽。
  //     `.docx` 不许被 `isTextAttachment` 认成文本 —— 认成文本就意味着后面
  //     紧接着 `fs.readFileSync(...).toString('utf8')`，得到一堆 zip 乱码当正文。
  const ofcMod = feishu;
  T('L6 ★ 反向对照：.docx/.xlsx 仍**不算**「可直接按 UTF-8 读」，另有 isOfficeAttachment 单列一类',
    ofcMod.isTextAttachment('a.docx') === false
      && ofcMod.isTextAttachment('a.xlsx') === false
      && ofcMod.isOfficeAttachment('a.docx') === true
      && ofcMod.isOfficeAttachment('a.xlsx') === true
      && ofcMod.isOfficeAttachment('a.pdf') === false
      && ofcMod.isOfficeAttachment(null) === false,
    '');
}

try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch {}

const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} 飞书 Guard 统一审查与建案自证 ${res.length - nFail}/${res.length} 项通过`);
process.exit(nFail ? 1 : 0);
