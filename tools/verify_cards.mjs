#!/usr/bin/env node
/**
 * verify_cards.mjs —— 卡片模版与语域规程的自证器
 *
 * ## 为什么需要它
 *
 * 本项目已经在「文档里的数字复现不出来」上吃过一次亏（ADR-0013 §15.3），
 * 而卡片模版比数字更容易腐烂：写卡片的人改一个 tag、加一个字段，
 * `contract.md` 和 `SKILL.md` 照旧读起来完全正常，**直到某天守衡的回复在群里凭空消失**
 * ——因为 schema V2 里一个不认的 tag 会让整张卡被服务端整体拒绝，不是降级，是丢。
 *
 * 所以本脚本做的是把「模版」「登记表」「文档」三者的**一致性**变成可执行断言：
 *
 *   A 构建   十一个构造器都能建出卡，且都过本地校验
 *   B 登记   REGISTRY 里每个字段真的被构造器读过（写进文档却没人用的字段 = 假槽位）
 *   C 白名单  cards.mjs 的 ALLOWED_TAGS 与探针读数一致；被 V2 移除的 tag 能被拦下
 *   D 降级   每张卡都能降级成纯文本，且降级文本里不出现 JSON、不出现内部记录
 *   E 文档   contract.md / SKILL.md 里出现的每一个 kind 都在登记表里，反之亦然
 *   F 语域   去 AI 味的机械规则本身有效（正例命中、反例不误报）
 *
 * 用法：
 *   node tools/verify_cards.mjs            # 全套
 *   node tools/verify_cards.mjs --verbose
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const CARDS_DIR = path.join(HERE, 'reply-cards');
const PROBE = path.join(ROOT, 'PMO', 'logs', 'card_probe.jsonl');

const VERBOSE = process.argv.includes('--verbose');

const {
  REGISTRY, BY_KIND, BUILDERS, BUILDER_SOURCE_NAME,
  build, validateCard, renderText, shapeOf, sampleCards, lintCopy,
} = await import(path.join(CARDS_DIR, 'index.mjs'));
const cardsSrc = fs.readFileSync(path.join(CARDS_DIR, 'cards.mjs'), 'utf8');
const cardsMod = await import(path.join(CARDS_DIR, 'cards.mjs'));

let pass = 0, fail = 0;
const bad = [];
const ok = (label) => { pass++; if (VERBOSE) console.log(`  ✅ ${label}`); };
const no = (label, why) => { fail++; bad.push(`${label} —— ${why}`); console.log(`  ❌ ${label}\n       ${why}`); };
const head = (t) => console.log(`\n${t}`);

/* ─────────────── A 构建 ─────────────── */
head('A 构建 · 每个类型都能建卡并过本地校验');
const samples = sampleCards();
for (const r of REGISTRY) {
  try {
    const c = samples[r.kind];
    const v = validateCard(c);
    if (!v.ok) no(`A ${r.kind}`, `样例卡校验不过：${v.errors.map((e) => `${e.path}:${e.msg}`).join('; ')}`);
    else ok(`A ${r.kind} → ${shapeOf(c)}`);
  } catch (e) {
    no(`A ${r.kind}`, `构建抛异常：${e.message}`);
  }
}
// 构造器数 = 登记数，不能有孤儿
for (const k of Object.keys(BUILDERS)) {
  if (!BY_KIND.has(k)) no(`A 孤儿构造器 ${k}`, 'BUILDERS 里有，REGISTRY 里没有 —— 没人知道什么时候该用它');
  else ok(`A 构造器 ${k} 已登记`);
}
for (const r of REGISTRY) {
  if (!BUILDERS[r.kind]) no(`A 缺构造器 ${r.kind}`, 'REGISTRY 里有，BUILDERS 里没有');
  // 源文件里函数名要对得上（防止有人改了函数名忘记改登记）
  const src = BUILDER_SOURCE_NAME[r.kind];
  if (!src || !new RegExp(`export function ${src}\\s*\\(`).test(cardsSrc)) {
    no(`A ${r.kind} 函数名`, `BUILDER_SOURCE_NAME 写的 ${src} 在 cards.mjs 里找不到 export function`);
  } else ok(`A ${r.kind} 函数名 ${src} 对得上`);
}

/* ─────────────── B 字段 ─────────────── */
head('B 登记 · 每个登记字段都真的被构造器读过');
for (const r of REGISTRY) {
  const fn = BUILDER_SOURCE_NAME[r.kind];
  const m = cardsSrc.match(new RegExp(`export function ${fn}\\s*\\(d = \\{\\}\\)[\\s\\S]*?\\n\\}`));
  if (!m) { no(`B ${r.kind}`, `找不到函数体 ${fn}`); continue; }
  const body = m[0];
  for (const f of Object.keys(r.fields)) {
    // 出现形式：d.<field>（含 d.fields、d.can、d.columns…）
    if (!new RegExp(`d\\.${f}\\b`).test(body)) {
      no(`B ${r.kind}.${f}`, '登记表里有这个字段，构造器从不读它 —— 假槽位，写进文档只会误导');
    } else ok(`B ${r.kind}.${f} 被读到`);
  }
}

/* ─────────────── C 白名单与探针一致 ─────────────── */
head('C 白名单 · 与探针读数一致，且能拦下 V2 已移除的 tag');
{
  const probeRows = fs.existsSync(PROBE)
    ? fs.readFileSync(PROBE, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l))
    : [];
  if (!probeRows.length) no('C 探针读数', `${PROBE} 不存在或为空 —— 白名单失去了实测依据`);
  else {
    const byProbe = Object.fromEntries(probeRows.map((r) => [r.id, r]));
    const mustPass = ['header_theme', 'markdown_element', 'table_element', 'column_set', 'collapsible', 'v2_fields_columnset', 'v2_button_bare'];
    const mustFail = ['note_fields', 'button_callback'];
    for (const id of mustPass) {
      if (!byProbe[id]) no(`C 探针 ${id}`, '读数缺失：不能声称这个元素可用');
      else if (!byProbe[id].ok) no(`C 探针 ${id}`, `读数是被拒，但白名单当它可用 —— 模版会用上它然后整卡被拒`);
      else ok(`C 探针 ${id} 通过，已在白名单`);
    }
    for (const id of mustFail) {
      if (!byProbe[id]) no(`C 探针 ${id}`, '读数缺失');
      else if (byProbe[id].ok) no(`C 探针 ${id}`, '读数是通过，但代码当它被移除 —— 拒绝的理由已经不成立，该更新');
      else ok(`C 探针 ${id} 被拒（${byProbe[id].error?.error?.ErrCode ?? byProbe[id].error?.code}），已在移除表`);
    }
    // 白名单里不该出现被拒的 tag 名
    for (const tag of Object.keys(cardsMod.REMOVED_IN_V2)) {
      if (cardsMod.ALLOWED_TAGS.has(tag)) no(`C 白名单含 ${tag}`, '同时出现在 ALLOWED_TAGS 与 REMOVED_IN_V2');
      else ok(`C ${tag} 不在白名单，会被拦`);
    }
  }
}
{
  // 校验器真的能拦：造三张坏卡
  const base = samples['query-answer'];
  const clone = () => JSON.parse(JSON.stringify(base));
  const cases = [
    ['note 元素', (c) => c.body.elements.push({ tag: 'note', elements: [] })],
    ['action 容器', (c) => c.body.elements.push({ tag: 'action', actions: [] })],
    ['未知配色', (c) => { c.header.template = 'chartreuse'; }],
    ['表格 rows 写成数组', (c) => c.body.elements.push({ tag: 'table', columns: [{ name: 'a' }], rows: [['x']] })],
    ['表格列名不匹配', (c) => c.body.elements.push({ tag: 'table', columns: [{ name: 'a' }], rows: [{ b: 'x' }] })],
    ['正文放在顶层', (c) => { c.elements = c.body.elements; delete c.body; }],
    ['header.title 用 markdown', (c) => { c.header.title = { tag: 'markdown', content: 'x' }; }],
  ];
  for (const [label, mutate] of cases) {
    const c = clone(); mutate(c);
    const v = validateCard(c);
    if (v.ok) no(`C 拦截「${label}」`, '校验器放过了它 —— 这张卡会被飞书整体拒绝');
    else ok(`C 拦住「${label}」：${v.errors[0].msg.slice(0, 46)}`);
  }
  // 好卡必须过
  if (!validateCard(clone()).ok) no('C 好卡误报', '干净卡被判不合格，校验器过严');
  else ok('C 干净样例卡不被误报');
}

/* ─────────────── D 降级 ─────────────── */
head('D 降级 · 卡片发不出去时，纯文本仍然可读');
for (const r of REGISTRY) {
  const c = samples[r.kind];
  const txt = renderText(c, '卡片被拒 code=230099');
  const problems = [];
  if (txt.includes('{"schema"') || txt.includes('"tag"')) problems.push('降级文本里出现了原始 JSON');
  if (!txt.startsWith('【')) problems.push('降级文本没有以标题开头');
  if (!txt.includes('卡片被拒')) problems.push('降级文本没注明降级原因 —— 对方不知道格式为什么变了');
  if (/toolTrace|tool_calls|call_\d|run_readonly_command\(/.test(txt)) problems.push('降级文本里出现了内部调用记录');
  if (txt.length < 8) problems.push('降级文本几乎为空');
  if (problems.length) no(`D ${r.kind}`, problems.join('；'));
  else ok(`D ${r.kind} 降级 ${txt.length} 字：${txt.split('\n')[0]}`);
  // 形状摘要必须非空（空摘要说明卡里没放任何可见元素）
  if (!shapeOf(c)) no(`D ${r.kind} 形状`, '卡片里没有任何可见元素');
}

/* ─────────────── E 文档一致性 ─────────────── */
head('E 文档 · kind 在登记表、contract.md、SKILL.md 三处一致');
{
  const docFiles = [
    path.join(CARDS_DIR, 'contract.md'),
    path.join(ROOT, 'agent-skills', '守衡语域', 'SKILL.md'),
  ];
  for (const f of docFiles) {
    const rel = path.relative(ROOT, f);
    if (!fs.existsSync(f)) { no(`E ${rel}`, '文件不存在'); continue; }
    const md = fs.readFileSync(f, 'utf8');
    for (const r of REGISTRY) {
      if (!md.includes(`\`${r.kind}\``)) no(`E ${rel} 缺 ${r.kind}`, '登记表里有这个类型，文档里没写 —— 用的人不会知道它存在');
      else ok(`E ${rel} 含 ${r.kind}`);
    }
    // 反向：文档里提到的所有 kind 都要在登记表里
    for (const m of md.matchAll(/`([a-z]+(?:-[a-z]+)+)`/g)) {
      const k = m[1];
      const looksLikeKind = /^(query|data|correction|capability|find|cannot|receipt|turn|evidence|alert|decision)-/.test(k);
      if (looksLikeKind && !BY_KIND.has(k)) no(`E ${rel} 提到未知类型 ${k}`, '文档里写了，代码里没有');
    }
  }
  // 白名单数字一致：contract.md 里声称的可用 tag 应与 ALLOWED_TAGS 相同
  const contract = fs.readFileSync(path.join(CARDS_DIR, 'contract.md'), 'utf8');
  const claimed = (contract.match(/`(markdown|plain_text|hr|table|column_set|column|collapsible_panel|button|code_block|standard_icon)`/g) ?? [])
    .map((x) => x.replace(/`/g, ''));
  const missing = [...cardsMod.ALLOWED_TAGS].filter((t) => !claimed.includes(t));
  if (missing.length) no('E contract.md 白名单不全', `缺：${missing.join(', ')}`);
  else ok(`E contract.md 列出了全部 ${cardsMod.ALLOWED_TAGS.size} 个可用 tag`);
}

/* ─────────────── F 语域规则本身有效 ─────────────── */
head('F 语域 · 去 AI 味的机械规则：正例命中、反例不误报');
{
  const { COPY_RULES } = await import(path.join(CARDS_DIR, 'registry.mjs'));
  const positives = [
    ['chatbotResidue', '好问题！让我来看看这个文件。'],
    ['chatbotResidue', '希望这对你有帮助。'],
    ['conclusionTail', '综上所述，这个方案是可行的。'],
    ['padding', '我们需要先对这个目录进行分析，然后予以处理。'],
    ['hedgeStack', '这个可能是编码问题，或许也许是压缩存储，大概如此。'],
    ['padding', '对这条需求做出决定之前，需要对它进行确认。'],
    // 结构级：那条 434 字故障输出的真实形态
    ['internalLeak', '我查了几轮还是没能得出可靠结论，先把已知的告诉你：我试过 list_files、list_files、list_files，但信息不足。'],
    ['internalLeak', 'trace: run_readonly_command(53ms) → run_readonly_command(1194ms)'],
    ['internalLeak', '"role": "tool", "tool_call_id": "call_00_xT8wRM60iidlhia0CyIw4532"'],
  ];
  for (const [id, text] of positives) {
    const hits = lintCopy(text);
    if (!hits.some((h) => h.id === id)) no(`F 正例 ${id}`, `「${text}」没命中 ${id}`);
    else ok(`F 正例 ${id} 命中`);
  }
  // 短语表里**每一条**都要真的能被自己命中 —— 防止写进去一条永远匹配不到的短语
  for (const r of COPY_RULES) {
    if (!r.phrases) continue;
    const dead = r.phrases.filter((p) => !lintCopy(`前一句。${p}。后一句。`).some((h) => h.id === r.id));
    if (dead.length) no(`F ${r.id} 死短语`, `这些短语永远匹配不到自己：${dead.join(' / ')}`);
    else ok(`F ${r.id} 的 ${r.phrases.length} 条短语全部可命中`);
  }
  const negatives = [
    ['单个连词是正常的', '此外，还有一个文件没读。'],
    ['正式语域不是 AI 味', '依据 `PMO/守衡-架构说明.md` 第四节第 4 条，九个工具全只读。'],
    ['单个限定词是正常的', '这个可能是编码问题。'],
    ['三顿号并列是正常的', '顶层是 ADR、PMO、PRD、base 四个目录。'],
    ['表格不算排比', '| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |'],
    // 正常回复会提到工具名，这**不是**泄漏；泄漏是「连续同名」或「栈帧/内部字段名」
    ['正常回复里出现一次工具名', '我用 `list_files` 找了一遍，没找到。'],
    ['正常回复里出现两次不同工具名', '先 `list_files` 找，再 `read_text_file` 读，都没有。'],
    ['正常回复里说「我试过 grep 和 wc」', '我在工作区里试过 grep 和 wc，零命中。'],
  ];
  for (const [label, text] of negatives) {
    const hits = lintCopy(text).filter((h) => h.level === 'error');
    if (hits.length) no(`F 反例「${label}」`, `被误报为 error：${hits.map((h) => h.id).join(',')} —— 过度纠正本身是另一种指纹`);
    else ok(`F 反例「${label}」不误报`);
  }
}

/* ─────────────── G stdout 干净（管道能用） ─────────────── */
head('G stdout · CLI 的 JSON 输出不被日志污染');
{
  // 这条不是洁癖：`sample --json | validate -` 是这个模版对外的主要用法，
  // 而飞书 SDK 默认往 stdout 打一行 `[info]: client ready`，
  // 会让整条管道拿到一段不是 JSON 的开头。2026-09-18 实测踩到过。
  const { execFileSync } = await import('node:child_process');
  const cli = path.join(CARDS_DIR, 'cli.mjs');
  let out = '';
  try {
    out = execFileSync(process.execPath, [cli, 'sample', 'receipt', '--json'], { encoding: 'utf8' });
  } catch (e) { no('G sample --json', `执行失败：${e.message}`); }
  if (out) {
    try { JSON.parse(out); ok('G sample --json 的 stdout 是纯 JSON（无日志前缀）'); }
    catch (e) { no('G sample --json', `stdout 不是纯 JSON：${e.message}；开头是「${out.slice(0, 60)}」`); }
  }
  // 校验器的退出码要能当闸用
  const { spawnSync } = await import('node:child_process');
  const r1 = spawnSync(process.execPath, [cli, 'validate', '-'],
    { input: JSON.stringify(samples.receipt), encoding: 'utf8' });
  if (r1.status !== 0) no('G validate 好卡退出码', `应为 0，实际 ${r1.status}`);
  else ok('G validate 好卡退出码 0');
  const r2 = spawnSync(process.execPath, [cli, 'validate', '-'],
    { input: '{"schema":"1.0"}', encoding: 'utf8' });
  if (r2.status === 0) no('G validate 坏卡退出码', '坏卡也返回 0 —— 这个校验器没法当闸用');
  else ok('G validate 坏卡退出码非 0');
}

/* ─────────────── H 规程文件真的会入库 ─────────────── */
head('H 入库 · 规程文件不在 .gitignore 里');
{
  // 这条是被真实踩到后才加的：本项目 .gitignore 第 39 行是 `skills/`，
  // 注释写明「第三方技能库与克隆」。项目**自有**的规程放进 skills/ 不会入库，
  // 写完之后 `git status` 一片干净，看起来像什么都没发生。
  // 所以自证要能把「写了但没入库」变成红的。
  const { spawnSync } = await import('node:child_process');
  const skill = path.join(ROOT, 'agent-skills', '守衡语域', 'SKILL.md');
  if (!fs.existsSync(skill)) no('H 规程文件存在', `${path.relative(ROOT, skill)} 不存在`);
  else {
    const r = spawnSync('git', ['check-ignore', '-q', skill], { cwd: ROOT });
    if (r.status === 0) no('H 规程可入库', `${path.relative(ROOT, skill)} 被 .gitignore 忽略 —— 它不会进版本库`);
    else ok('H 规程文件可入库（未被 .gitignore 忽略）');
  }
  for (const f of ['tools/reply-cards/contract.md', 'tools/reply-cards/cards.mjs', 'tools/verify_cards.mjs']) {
    const r = spawnSync('git', ['check-ignore', '-q', path.join(ROOT, f)], { cwd: ROOT });
    if (r.status === 0) no(`H ${f} 可入库`, '被 .gitignore 忽略');
    else ok(`H ${f} 可入库`);
  }
}

/* ─────────────── J 信封 · 模型输出 → 卡片，且内部标记永不出现在群里 ─────────────── */
head('J 信封 · 解析、上限执行、以及「标记不许漏进群」');
{
  const { toCardOrText, extractCardBlock, enforceLimits, leaksInternalMark, publicTextOf, CARD_MARK } =
    await import(path.join(CARDS_DIR, 'envelope.mjs'));

  // J1 三个上限：**不查名字，查它真的会拦。**
  //
  // 旧版这里是 `new RegExp('\\b'+k+'\\b').test(envSrc)` —— 一个**源码文本存在性测试**：
  // 只要常量名在 envelope.mjs 里出现过（哪怕只出现在 import 行或 ENFORCED 字面量里）
  // 就算过。实测它当时正在它本该抓的缺陷上变绿：`MAX_SECTIONS = 3` 全仓
  // 没有任何一行拿它做比较，J1 却是 ✅ —— AGENTS.md §2.4 点名的那个病，
  // 在它自己的执行点断言里活了下来。
  //
  // 现在分三层，缺一层都不算：
  //   J1a 源码级 —— 常量必须出现在一个**能改变行为的表达式**里（排除注释/import/export）
  //   J1b 行为级 —— 喂一个超限样本，必须真的被拦下，且**内容一个字符不丢**
  //   J1c 相容级 —— 现有 11 张样例卡都不许超限（否则是「上限与模版不相容」，病因同 MAX_SECTIONS=3）
  const envSrc = fs.readFileSync(path.join(CARDS_DIR, 'envelope.mjs'), 'utf8');
  const envLines = envSrc.split('\n');
  const isComment = (l) => {
    const t = l.trim();
    return t.startsWith('*') || t.startsWith('//') || t.startsWith('/*');
  };
  const { capSections } = await import(path.join(CARDS_DIR, 'envelope.mjs'));
  const cardsMod2 = await import(path.join(CARDS_DIR, 'cards.mjs'));
  const { md, MAX_SECTIONS: MS } = cardsMod2;
  const cp = (x) => [...String(x)].length;

  // J1a 的判据：常量必须**真的到达一个比较**，而不是只被转口。
  //   排除的正是 MAX_SECTIONS=3 当时的形状 —— 只在 import 行与 ENFORCED 字面量里出现。
  //   允许**一层默认值绑定**：`capSections(card, max = MAX_SECTIONS)` 里 `max` 被比较，
  //   常量确实决定了行为，算数。这不是为了迁就写法 —— 是为了不逼着代码
  //   为了过检查而写成更差的样子（教考试）。
  const reachesComparison = (k) => {
    const code = envLines.filter((l) => !isComment(l));
    const cmp = (l) => /[<>]=?|Math\.(min|max)/.test(l);
    if (code.some((l) => new RegExp(`\\b${k}\\b`).test(l) && cmp(l))) return '直接比较';
    const binders = [];
    for (const l of code) {
      const m = l.match(new RegExp(`([A-Za-z_$][\\w$]*)\\s*=\\s*${k}\\b`));
      if (m) binders.push(m[1]);
    }
    for (const b of binders) {
      if (code.some((l) => new RegExp(`\\b${b}\\b`).test(l) && cmp(l))) return `经绑定 ${b}`;
    }
    return null;
  };

  for (const k of ['VERDICT_MAX', 'BOUNDARY_MAX', 'MAX_SECTIONS']) {
    const how = reachesComparison(k);
    if (!how) {
      const seen = envLines.filter((l) => !isComment(l) && new RegExp(`\\b${k}\\b`).test(l));
      no(`J1a ${k} 有执行点`,
        `${k} 在 envelope.mjs 里没有任何一条非注释语句拿它做比较 —— ` +
        `只出现在 ${seen.length} 行里（${seen.map((l) => l.trim().slice(0, 40)).join(' | ') || '一行都没有'}），` +
        `上限又变回注释了`);
    } else {
      ok(`J1a ${k} 到达了比较（${how}）`);
    }
  }

  // J1b：行为级 —— 每个上限都要有一个「喂超限样本 → 真被拦下」的实证
  {
    // ① 结论超长
    const vLong = '结'.repeat(300);
    const r1 = enforceLimits('query-answer', { title: 't', verdict: vLong }, []);
    const vAfter = r1.data.verdict ?? '';
    if (cp(vAfter) > 60) no('J1b VERDICT_MAX 真的拦', `喂 300 字结论，出来还是 ${cp(vAfter)} 字`);
    else ok(`J1b VERDICT_MAX 真的拦：300 → ${cp(vAfter)} 字`);

    // ② 边界超长
    const bLong = '边'.repeat(400);
    const r2 = enforceLimits('query-answer', { title: 't', verdict: '短结论', boundary: bLong }, []);
    const bAfter = r2.data.boundary ?? '';
    if (cp(bAfter) > 90) no('J1b BOUNDARY_MAX 真的拦', `喂 400 字边界，出来还是 ${cp(bAfter)} 字`);
    else ok(`J1b BOUNDARY_MAX 真的拦：400 → ${cp(bAfter)} 字`);

    // ③ 段落超限 —— 造一张比 MAX_SECTIONS 多两段的卡
    const n = MS + 2;
    const over = {
      schema: '2.0', config: { update_multi: true },
      header: { title: { tag: 'plain_text', content: 'T' }, template: 'orange' },
      body: { elements: Array.from({ length: n }, (_, i) => md(`第${i + 1}段`)) },
    };
    const beforeTxt = JSON.stringify(over.body.elements);
    const capped = capSections(over);
    const afterMd = capped.card.body.elements.filter((e) => e.tag === 'markdown').length;
    const folded = capped.card.body.elements.find((e) => e.tag === 'collapsible_panel');
    if (afterMd > MS) {
      no('J1b MAX_SECTIONS 真的拦', `喂 ${n} 段，顶层还剩 ${afterMd} 段（上限 ${MS}）`);
    } else if (!folded || folded.elements.length !== n - MS) {
      no('J1b MAX_SECTIONS 真的拦', `${n} 段里只折叠了 ${folded ? folded.elements.length : 0} 段，其余不知去向`);
    } else {
      // 搬是搬，砍是砍：每一段的原文都必须还在
      const afterTxt = JSON.stringify(capped.card.body.elements);
      const lost = Array.from({ length: n }, (_, i) => `第${i + 1}段`).filter((t) => !afterTxt.includes(t));
      if (lost.length) no('J1b MAX_SECTIONS 不丢内容', `搬走后找不到：${lost.join('、')}`);
      else ok(`J1b MAX_SECTIONS 真的拦：${n} 段 → 顶层 ${afterMd} 段 + 折叠 ${folded.elements.length} 段，内容一个没丢`);
    }

    // J1c：现有模版必须都不超限 —— 否则是上限与模版不相容（MAX_SECTIONS=3 就是这么废的）
    let worst = 0, worstKind = '';
    for (const r of REGISTRY) {
      const c = samples[r.kind];
      if (!c) continue;
      const m = (c.body?.elements ?? []).filter((e) => e.tag === 'markdown').length;
      if (m > worst) { worst = m; worstKind = r.kind; }
    }
    if (worst > MS) {
      no('J1c 上限与模版相容',
        `「${worstKind}」顶层有 ${worst} 段，超过 MAX_SECTIONS=${MS} —— ` +
        `上限比模版还小，等于每次都要搬，和当初 MAX_SECTIONS=3 是同一个病`);
    } else {
      ok(`J1c 上限与模版相容：11 张样例卡最紧的一张是「${worstKind}」${worst} 段 ≤ ${MS}`);
    }
  }

  // J2 ★ 最要紧的一条：要发出去的**文本**里，任何输入都不许留下 [[card: 或内部记录。
  // 第一版这里漏了 ——「坏 JSON」那条会把 [[card:receipt]] 和半截 JSON 原样发进群。
  const leakCases = [
    ['纯文本', '就是一句话，没有卡片。'],
    ['正常卡', `${CARD_MARK}query-answer]]\n{"title":"11 条","verdict":"**11 条**。"}`],
    ['带 json 围栏', `${CARD_MARK}receipt]]\n\`\`\`json\n{"title":"已收到","verdict":"收到。"}\n\`\`\``],
    ['块前后有正文', `先说明一下。\n\n${CARD_MARK}receipt]]\n{"title":"已收到","verdict":"收到。"}\n\n补充一句。`],
    ['未知类型', `${CARD_MARK}nope]]\n{"title":"T"}`],
    ['JSON 截断', `${CARD_MARK}receipt]]\n{"title":`],
    ['JSON 截断且后面有正文', `${CARD_MARK}receipt]]\n{"title":\n\n顺便说一句，日志我看过了。`],
    ['只有标记', `${CARD_MARK}receipt]]`],
    ['标记后没有对象', `${CARD_MARK}receipt]] 然后呢`],
    ['括号不配平', `${CARD_MARK}query-answer]]\n{"title":"T","verdict":"V","evidence":["a"`],
    ['字段名全错', `${CARD_MARK}receipt]]\n{"标题":"乱写","结论":"乱写"}`],
    ['嵌套花括号', `${CARD_MARK}decision]]\n{"title":"定一下","ask":"选哪个？","options":[{"label":"A","cost":"x"}]}`],
    // ★ 下面三条是本轮补的。原表 13 条里**没有一条是「含内部标记的纯文本」**，
    //   而 2026-09-17 那条真事故（连列 19 次 list_files 的 434 字故障输出）
    //   **正是纯文本** —— 断言没喂到那个形状，纯文本路径就一直没有执行点。
    ['★ 纯文本 + tool_calls', '查完了。tool_calls=[] finishReason=stop'],
    ['★ 纯文本 + 连列同名工具（2026-09-17 那条的形状）',
     '我查了几轮还是没能得出可靠结论。我试过 list_files、list_files、list_files、list_files，call_abc1234567890'],
    ['★ 纯文本 + 栈帧', '出错了。\n at handler (/Users/x/a.mjs:12:34)'],
  ];
  for (const [name, txt] of leakCases) {
    let r;
    try { r = toCardOrText(txt); }
    catch (e) { no(`J2 ${name}`, `toCardOrText 抛异常：${e.message}`); continue; }
    if (typeof r.text !== 'string' || !r.text.length) { no(`J2 ${name}`, '产出的文本是空的 —— 降级不许变成不答'); continue; }
    if (leaksInternalMark(r.text)) no(`J2 ${name}`, `要发出去的文本里还留着内部标记：${JSON.stringify(r.text.slice(0, 120))}`);
    else ok(`J2 ${name} → ${r.mode}，文本无标记残留`);
  }

  // J2b 公开格（对方一眼能看到的格子）里不许有内部标识 —— 折叠区里允许，
  // 那正是 alert 这个类型存在的理由。
  {
    const r = toCardOrText(`${CARD_MARK}alert]]\n{"title":"坏了","what":"tool_calls 有 27 次","impact":"没答上"}`);
    if (r.mode !== 'card') no('J2b 内部记录被搬进折叠区', `没有建出卡：${r.reason}`);
    else {
      const pub = publicTextOf(r.card);
      const folded = JSON.stringify(r.card).includes('tool_calls');
      if (leaksInternalMark(pub)) no('J2b 公开格干净', `公开格里有内部标识：${JSON.stringify(pub.slice(0, 120))}`);
      else if (!folded) no('J2b 内部记录没有被丢弃', '搬走之后内部详情整个不见了 —— 拦住和丢掉是两回事');
      else ok('J2b 内部记录被搬进折叠区，公开格干净');
    }
  }

  // J3 结论超长必须**搬走**而不是**砍掉**：一个字符都不许丢。
  {
    const long = '这是一句很长的结论。'.repeat(12);
    const { data, moved } = enforceLimits('query-answer', { verdict: long });
    const rejoined = [...data.verdict, ...(data.boundary ?? ''), ...(data.evidence ?? []).join('')].join('');
    const lost = [...long].filter((ch) => !rejoined.includes(ch)).length;
    if (moved.length === 0) no('J3 超长结论被搬迁', '超过 60 字却没有产生任何搬迁记录');
    else if (lost) no('J3 超长结论零丢失', `搬迁后丢了 ${lost} 个字符 —— 搬是搬，砍是砍，不能混`);
    else ok(`J3 超长结论搬迁且零丢失（${moved.length} 条搬迁记录）`);
  }

  // J4 块之外还有正文时，正文要进折叠区，不能凭空消失
  {
    const r = toCardOrText(`前面这句要说。\n\n${CARD_MARK}receipt]]\n{"title":"已收到","verdict":"收到。"}`);
    const inCard = JSON.stringify(r.card ?? {});
    if (!inCard.includes('前面这句要说')) no('J4 块外正文并入折叠区', '块外的话被丢掉了');
    else ok('J4 块外正文并入折叠区');
  }

  // J5 没有块时必须是原样透传 —— 信封不许改写正常回答
  {
    const plain = '这是一条普通回复，带 `代码` 和 **粗体**。\n\n| a | b |\n|---|---|\n| 1 | 2 |';
    const r = toCardOrText(plain);
    if (r.mode !== 'text' || r.text !== plain) no('J5 无块时原样透传', `mode=${r.mode}，文本被改动了`);
    else ok('J5 无块时原样透传');
  }
}

/* ─────────────── K 提示词 · registry 与 persona 不许漂移 ─────────────── */
head('K 提示词 · 模型看到的类型清单必须与登记表一致');
{
  const { buildSystemPrompt, cardContract } = await import(path.join(HERE, 'agent', 'persona.mjs'));
  const prompt = buildSystemPrompt();

  // K1 十一个 kind 逐个出现在提示词里。少一个，模型就永远用不了它；
  // 多一个不存在的，模型调用它 → 整卡被拒 → 回复消失。
  for (const r of REGISTRY) {
    if (!prompt.includes(`\`${r.kind}\``)) no(`K1 ${r.kind} 出现在提示词里`, '模型不知道有这个类型');
    else ok(`K1 ${r.kind} 在提示词里`);
  }

  // K2 反向：提示词里的每个 kind 都必须是真的 —— 从卡片块形态里抠出来逐个核
  {
    const mentioned = new Set([...prompt.matchAll(/`([a-z][a-z-]+)`/g)].map((m) => m[1]));
    const looksLikeKind = [...mentioned].filter((k) => k.includes('-') || BY_KIND.has(k));
    const ghosts = looksLikeKind.filter((k) => !BY_KIND.has(k) && !['card-failed', 'reply-card', 'text-fallback', 'json', 'zhe'].includes(k));
    // 只对「形态像 kind 且出现在类型清单那一节」的做断言，避免误伤普通词
    const section = prompt.slice(prompt.indexOf('## 十一个类型'), prompt.indexOf('## 各类型的字段'));
    const ghostsInList = ghosts.filter((k) => section.includes(`\`${k}\``));
    if (ghostsInList.length) no('K2 清单里没有不存在的类型', `提示词里的类型清单含未知 kind：${ghostsInList.join(', ')}`);
    else ok('K2 清单里没有不存在的类型');
  }

  // K3 三条硬约束必须在提示词里逐字出现 —— 它们是模版存在的理由，不能只活在文档里
  const musts = [
    ['结论 ≤60 字', /不超过 60 个字符/],
    ['边界 ≤90 字', /不超过 90 个字符/],
    ['内部记录只进折叠区', /只能进折叠区/],
    ['块外不要重复写正文', /块之外不要重复写正文/],
    ['不套卡的反向指引', /一句话能答完的，就一句话答完/],
    ['结论要写事实不写排版', /结论是你查到的事实，不是你打算怎么排版/],
  ];
  for (const [name, re] of musts) {
    if (!re.test(prompt)) no(`K3 ${name}`, '提示词里找不到这条硬约束');
    else ok(`K3 ${name} 已写进提示词`);
  }

  // K4 字段名清单要与登记表一致（模型才知道该填什么）
  for (const r of REGISTRY) {
    const line = prompt.split('\n').find((l) => l.startsWith(`- \`${r.kind}\`：`));
    if (!line) { no(`K4 ${r.kind} 字段行`, '提示词里没有这个类型字段行'); continue; }
    const missing = Object.keys(r.fields).filter((f) => !line.includes(f));
    if (missing.length) no(`K4 ${r.kind} 字段齐全`, `提示词漏了字段：${missing.join(', ')}`);
    else ok(`K4 ${r.kind} 字段齐全（${Object.keys(r.fields).length} 个）`);
  }

  // K5 提示词长度要有个上限意识：它进的是每一次调用的前缀
  {
    const n = [...prompt].length;
    if (n > 8000) no('K5 提示词长度', `${n} 字符，太长了；卡片段应保持精炼`);
    else ok(`K5 提示词 ${n} 字符（卡片段 ${[...cardContract()].length}）`);
  }
}

/* ─────────────── L 发送链 · daemon 只有一个格式决策点 ─────────────── */
head('L 发送链 · 降级链完整且不重复投递');
{
  const daemon = fs.readFileSync(path.join(HERE, 'ws_daemon.mjs'), 'utf8');

  // L1 卡片降级的目标必须是**同一条引用**里的纯文本，不是新发一条。
  // 新发一条会断开引用，而且和 replyMarkdown 自己的补发叠加 → 群里出现两份回答。
  if (!/replyCard\(messageId, card\)/.test(daemon)) no('L1 卡片走 reply', 'daemon 里没有 replyCard 调用');
  else ok('L1 卡片走 reply');

  if (!/card-failed→/.test(daemon)) no('L1 卡片失败降级到 reply 纯文本', '找不到 card-failed 降级分支');
  else ok('L1 卡片失败降级到同一条引用里的纯文本');

  // L2 feishu.replyCard 只尝试一次、不自己兜底 —— 兜底只能有一处，
  // 两处叠加的表现是同一个回答在群里出现两次。
  const feishuSrc = fs.readFileSync(path.join(HERE, 'agent', 'feishu.mjs'), 'utf8');
  const replyCardBody = feishuSrc.slice(feishuSrc.indexOf('export async function replyCard'), feishuSrc.indexOf('export async function sendTyping'));
  if (/sendMarkdown|sendCard|message\.create/.test(replyCardBody)) {
    no('L2 replyCard 只尝试一次', 'replyCard 自己做了兜底发送，与调用方的兜底叠加会重复投递');
  } else ok('L2 feishu.replyCard 只尝试一次，兜底只有 daemon 一处');

  // L2b 「兜底只能有一处」的另一半：`replyCard` 全仓只许有**一个实现**。
  // ★ 为什么需要它（2026-09-22 诊断 #14）：L2 只扫 `agent/feishu.mjs` **一个文件**，
  //   而 `tools/reply-cards/index.mjs` 同名同形地导出了**第二个** `replyCard`，
  //   它失败时自己会去 `sendCard` **新发一条** —— 正是 L2 要拦的形状，
  //   却因为「它在另一个文件里」而从来没被扫到。两份同名实现，一份合规一份不合规。
  //   判据是**唯一性**，不是「名字出现过」：`length !== 1` 同时挡住「多了一个」和
  //   「一个都没有」（后者是改名/搬走之后判据恒绿的形状 —— §2.4 那个病）。
  const exporterFiles = [];
  for (const dir of ['.', 'agent', 'reply-cards']) {
    let names = [];
    try { names = fs.readdirSync(path.join(HERE, dir)); } catch { continue; }
    for (const n of names) {
      if (!n.endsWith('.mjs')) continue;
      const src = fs.readFileSync(path.join(HERE, dir, n), 'utf8');
      // ★ 必须**行首锚定**（`^\s*export`，m 标志），不能只查子串。
      //   第一版写的是 `/export async function replyCard\b/`，于是这条判据**自己**
      //   把三个文件报了出来：`verify_cards.mjs`（判据自己那行正则字面量）、
      //   `reply-cards/index.mjs`（我刚写的解释它为什么被删的注释）、
      //   以及真正的实现。**「名字出现过」在这里第三次骗人** ——
      //   前两次是 J1（常量名出现在 import 里）和 §2.4.4 的 `dryRun: true` 计数。
      //   行首锚定要求的是**一条真的导出语句**，注释与正则字面量都到不了行首。
      if (/^\s*export\s+async\s+function\s+replyCard\b/m.test(src)) {
        exporterFiles.push(dir === '.' ? n : `${dir}/${n}`);
      }
    }
  }
  if (exporterFiles.length !== 1 || exporterFiles[0] !== 'agent/feishu.mjs') {
    no('L2b replyCard 全仓只有一个实现',
       `导出 replyCard 的文件有 ${exporterFiles.length} 个：${exporterFiles.join('、') || '（一个都没有）'} —— 兜底只能有一处`);
  } else ok('L2b replyCard 全仓只有一个实现（agent/feishu.mjs）');

  // L3 形态决策**只能在一处**：`replyTo` 里过信封，`onMessage` 里不许碰。
  // ★ 2026-09-22 改。原先这里断言的是 `toCardOrText(result.reply)` 出现在 daemon 里、
  //   外加 `shaped.card ?? null` —— 那是在**描述当时的实现**（`onMessage` 过信封、
  //   `replyTo` 只收 `card`），而 `AGENTS.md` §2.5 写的是「只允许在 `replyTo` 里做」。
  //   **断言与规范指的是两个地方，而断言是绿的。**
  //   现在两条一起断言：**该在的地方必须在，不该在的地方必须不在** —— 这才叫「只允许一处」。
  // ★ 扫之前先剥注释：`onMessage` 里那段解释「原先 `toCardOrText` 在这里调」的注释，
  //   第一版把这条判据**自己**绊红了（注释里写着函数名）。同 J1a / C5：
  //   **注释不算代码**。剥注释这个动作本身也可能误伤（字符串里的 `//`），
  //   已知盲区明着留着 —— 这里两个函数体里没有那种字符串。
  const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  const rtBody = stripComments(daemon.slice(daemon.indexOf('async function replyTo'), daemon.indexOf('async function safeSend')));
  const omBody = stripComments(daemon.slice(daemon.indexOf('async function onMessage'), daemon.indexOf('async function replyTo')));
  if (!/toCardOrText\(/.test(rtBody)) no('L3 形态决策在 replyTo 里', 'replyTo 没有过信封 —— §2.5 说这个判断只允许在那里做');
  else ok('L3 形态决策在 replyTo 一处过信封');
  if (!/if \(card\)/.test(rtBody)) no('L3 卡片真的传给了发送', 'replyTo 里没有「有卡走卡」的分支');
  else ok('L3 卡片真的传给了发送');
  if (/toCardOrText|shaped\./.test(omBody)) {
    no('L3 onMessage 不碰形态', 'onMessage 里也在碰形态（toCardOrText / shaped.*）—— 两处定形态，群里格式会随机');
  } else ok('L3 onMessage 只记日志，不碰形态');

  // L4 形态与搬迁必须落到日志里 —— 否则调模版只能靠重跑猜
  for (const [name, re] of [['卡片形态', /🃏 卡片/], ['搬迁记录', /↪ /], ['语域命中', /语域 /], ['降级原因', /卡片降级为文本/]]) {
    if (!re.test(daemon)) no(`L4 ${name} 记进日志`, '日志里看不到这一项，出问题无法归因');
    else ok(`L4 ${name} 记进日志`);
  }

  // L5 内核不许自己拼卡片 —— 形态决策只能在发送层一处。
  // 两处都能定形态，就会出现「内核按 A 想、发送层按 B 发」的错位。
  const agentSrc = fs.readFileSync(path.join(HERE, 'agent', 'agent.mjs'), 'utf8');
  if (/reply-cards|toCardOrText|\[\[card:/.test(agentSrc)) {
    no('L5 内核不碰卡片', 'agent.mjs 里出现了卡片逻辑；形态决策必须只在 ws_daemon 一处');
  } else ok('L5 形态决策只在发送层一处');
}

/* ─────────────── L6/L7 内核自己的文案也要过同一把尺 ─────────────── */
head('L6/L7 内核文案 · 兜底话术不许被自己的检测器拦下 + 拒答的留证承诺要有执行点');
{
  // ★ 这两条守的是 2026-09-22 那次**真实事故**（上游在私聊里连问两次都没得到回答）。
  //
  //   链条：模型跑满 6 轮工具 → `agent.mjs` 的兜底话术把 `toolTrace` 里**所有**工具名
  //   拼进正文（`run_readonly_command、run_readonly_command、…` ×19）
  //   → `internalLeak` 判「连续三次同名工具」为故障 → `envelope.mjs` 降级成拒答
  //   → 她收到「我这次没能把回答组织好」，问第二次，一模一样。
  //
  //   两处各自都是对的：话术想说「我查过但没查到」，检测器想拦「内部记录漏进正文」。
  //   **合起来 100% 撞车** —— 这正是 §2.5「同一件事只能有一处判据」的反面：
  //   内核产出文案、信封判定文案，两边各自为政，谁都不知道对方的约束。
  //
  //   所以这条断言的形状是：**把内核的产出真的喂给信封的那把尺**。
  //   不是「源码里出现过 lintCopy」（那是 §2.4 里那个恒真的名字测试），
  //   而是**真的调用一次**。
  let fallbackReply = null;
  try {
    ({ fallbackReply } = await import(path.join(HERE, 'agent', 'agent.mjs')));
  } catch (e) {
    no('L6 能加载内核的兜底话术', `import agent/agent.mjs 失败：${e.message}`);
  }

  if (fallbackReply) {
    // 真实形状：一次工具循环里同名工具会连出十几次（实测 19 次 run_readonly_command）。
    const trace = [
      ...Array.from({ length: 19 }, () => ({ tool: 'run_readonly_command', ok: true, ms: 40 })),
      { tool: 'read_text_file', ok: true, ms: 1 },
      { tool: 'run_readonly_command', ok: false, ms: 12 },
    ];
    const t = String(fallbackReply(trace) ?? '');

    if (!t.trim()) no('L6 兜底话术非空', '拿到了空串 —— 对方会收到一条空回复');
    else ok('L6 兜底话术非空');

    const hits = lintCopy(t).filter((h) => h.level === 'error');
    if (hits.length) {
      no('L6 兜底话术过得了他自己的检测器',
         `喂 20 次真实形状的工具调用后，被拦下：${hits.map((h) => `${h.id}×${h.count}`).join('、')}`
         + `\n       —— 这句话术会被信封降级成拒答，对方等于没收到回答。原文：${JSON.stringify(t.slice(0, 120))}`);
    } else ok('L6 兜底话术过得了他自己的检测器（喂 20 次真实形状的工具调用）');

    // 三种形状都要过：一次没调、全成功、全失败。
    for (const [name, sample] of [
      ['空 trace（一次都没调）', []],
      ['全成功', [{ tool: 'run_readonly_command', ok: true }, { tool: 'grep_workspace', ok: true }]],
      ['全失败', [{ tool: 'run_readonly_command', ok: false }, { tool: 'run_readonly_command', ok: false }]],
    ]) {
      const s = String(fallbackReply(sample) ?? '');
      const h = lintCopy(s).filter((x) => x.level === 'error');
      if (!s.trim()) no(`L6 ${name} 非空`, '空串');
      else if (h.length) no(`L6 ${name} 不被拦`, `命中 ${h.map((x) => x.id).join('、')}`);
      else ok(`L6 ${name} 不被拦`);
    }

    // 反向对照：**旧话术必须被判红**。
    // 没有这一条，上面那些绿都证明不了什么 —— 万一 lintCopy 今天对什么都闭嘴，
    // 它们照样全绿（§2.4.1：一个从没红过的断言不算验证过它）。
    const OLD = '我查了几轮还是没能得出可靠结论，先把已知的告诉你：'
              + `我试过 ${trace.map((x) => x.tool).join('、')}，但信息不足。你能否补充一下具体要查什么？`;
    const oldHits = lintCopy(OLD).filter((h) => h.id === 'internalLeak');
    if (!oldHits.length) {
      no('L6 反向对照：旧话术必须被拦',
         '旧版那句（把工具名拼进正文）**没有**被 internalLeak 判红 —— '
         + '那么这条断言证明不了它修的是真问题，检测器可能已经失效');
    } else ok(`L6 反向对照成立：旧话术被 internalLeak 判红（×${oldHits[0].count}）`);
  }

  // L7 拒答话术说「原文留在 PMO/logs/dropped/」—— 那一行得真的存在。
  // 2026-09-22 之前它是**假的**：话说出去了，盘上什么都没有。
  //
  // ★ 这一条的**第一版是错的，而且错成本节要防的那个形状**：它用
  //   `envSrc.match(/PMO\/logs\/[\w\/.-]*/)` 从**源码文本**里抓路径 ——
  //   抓到的是注释里那半句（`PMO/logs`），而且 daemon 那边匹配到了**第一条**
  //   `path.join(LOG_DIR, …)`（那是早就存在的 `EVENT_DUMP`）。两侧都比错了地方，
  //   而比较还因为「解析出来是空串」被静默跳过 → **印出一个绿**。
  //   一个证明不了任何东西的绿，比红更糟（§2.4.1）。
  //
  //   现在两边都改成**能指出对象的读数**：
  //     说的 —— 真的调一次 `toCardOrText()`，从**产出的话术**里取路径；
  //     写的 —— 从 `dumpDropped` 的**函数体**里取，不看文件里别处。
  const { toCardOrText } = await import(path.join(CARDS_DIR, 'envelope.mjs'));
  const daemonSrc = fs.readFileSync(path.join(HERE, 'ws_daemon.mjs'), 'utf8');

  // 造一段**一定会被判 internalLeak** 的纯文本，逼出那条拒答话术。
  const LEAKY = '我试过 run_readonly_command、run_readonly_command、run_readonly_command，但信息不足。';
  const refusal = toCardOrText(LEAKY);
  if (!refusal.dropped || refusal.mode !== 'text') {
    no('L7 能逼出拒答话术', `喂一段必被拦的文本，拿到的是 mode=${refusal.mode} dropped=${refusal.dropped} —— 后面的断言都无从谈起`);
  } else ok('L7 能逼出拒答话术（喂 run_readonly_command ×3）');

  const claimed = (refusal.text.match(/PMO\/logs\/[\w.-]+(?:\/[\w.-]+)*\/?/) ?? [])[0] ?? null;
  if (!claimed) {
    no('L7 拒答话术说得出留证位置',
       `话术里没有落点路径，那「原文我留在…」就是一句没法核对的话。实际话术：${JSON.stringify(refusal.text)}`);
  } else ok(`L7 拒答话术承诺的落点：${claimed}`);

  // ① 执行点必须**接在 dropped 分支上**（不是别处随便调一次）
  if (!/if \(shaped\.dropped\)\s*dumpDropped\(/.test(daemonSrc)) {
    no('L7 留证有执行点', 'daemon 里没有 `if (shaped.dropped) dumpDropped(...)` —— '
       + '那句「原文留在 PMO/logs」就是一句没有执行点的承诺（§2.4.2）');
  } else ok('L7 留证接在 dropped 分支上');

  // ② 从 `dumpDropped` **函数体**里取落点，不看文件里别处
  const fnStart = daemonSrc.indexOf('function dumpDropped(');
  if (fnStart < 0) no('L7 落盘函数存在', '找不到 dumpDropped');
  else {
    // 函数体到下一个顶层 `function`/`async function` 之前
    const rest = daemonSrc.slice(fnStart);
    const nextTop = rest.slice(1).search(/\n(?:async )?function\s/);
    const body = nextTop > 0 ? rest.slice(0, nextTop + 1) : rest;

    if (!/writeFileSync/.test(body)) no('L7 落盘函数真的写盘', 'dumpDropped 里没有 writeFileSync');
    else ok('L7 dumpDropped 真的写盘');

    const wroteDir = (body.match(/path\.join\(LOG_DIR,\s*'([\w.-]+)'\)/) ?? [])[1] ?? null;
    if (!wroteDir) {
      no('L7 取得到落盘目录', 'dumpDropped 函数体里找不到 `path.join(LOG_DIR, …)` —— 取不到就说不了「说的与写的同一处」');
    } else {
      const claimedDir = (claimed ?? '').replace(/^PMO\/logs\/?/, '').replace(/\/$/, '');
      if (claimed && claimedDir !== wroteDir) {
        no('L7 说的与写的同一处',
           `话术说 PMO/logs/${claimedDir}，daemon 的 dumpDropped 写在 PMO/logs/${wroteDir} —— 两处会各自漂移`);
      } else if (!claimed) {
        no('L7 说的与写的同一处', '话术里没写落点，无从核对');
      } else ok(`L7 说的与写的同一处（PMO/logs/${wroteDir}/）`);
    }

    // ③ 落盘目录必须真的能被日志引用出来 —— 对方按话术去找，找得到才算数
    if (!/PMO\/logs\/dropped\//.test(body)) {
      no('L7 日志里印出的是同一个落点', 'dumpDropped 打的日志行里没有 `PMO/logs/dropped/`，'
         + '排查的人会去错的地方找');
    } else ok('L7 日志里印出的是同一个落点');
  }
}

/* ─────────────── N 附件 · 2026-10-17 改线后的判据 ─────────────── */
head('N 附件 · 旧红线已废止，话术必须是能力边界');
{
  // ★ 这一段的判据**变过**，两个日期都留着：
  //   2026-09-18：「飞书上的内容禁止下载」→ 附件按规矩**不取**，
  //     所以当时守的是「不取」不许被说成「看不到 / 没权限」。
  //   2026-10-17：委托方推翻 ——「你都可以下载，飞书你可以访问的附件和业务提供的。」
  //     于是「按规矩不取」这句话本身**成了错的**。今天真正的边界是能力：
  //       · 文本类附件（txt/md/csv/json…）→ 下载、抽正文、作为不可信输入交给模型；
  //       · 图片/音视频 → 解析还没接上，说「能力边界」，并给出替代路径；
  //       · 任何地方都不许再引用「禁止下载 / 公司不让下载」。
  //   所以本段从「守不取」改成「守不把能力不足说成规矩不许」，并**反向**检查旧话术已清掉。
  const BANNED = [
    [/看到里面的内容/, '把没解析说成「看不到」'],
    [/只能读文本消息/, '把能力边界说成「只能读文本」'],
    [/能力还没做|工具集里没有/, '把能力边界说成「能力还没做」'],
    [/没权限|权限不足/, '把能力边界说成权限问题'],
  ];
  const DEAD_POLICY = /禁止下载|公司不让下载|附件我不取|附件只有下载这一条通道/;
  const hitsOf = (t) => BANNED.filter(([re]) => re.test(t)).map(([, why]) => why);

  // N1/N2 内核分支（agent.mjs）—— 群里第一眼看到的就是它
  const agent = fs.readFileSync(path.join(HERE, 'agent', 'agent.mjs'), 'utf8');
  const a0 = agent.indexOf("if (msg.message_type !== 'text')");
  const a1 = agent.indexOf('const question = botMentioned', a0);
  const branch = a0 >= 0 && a1 > a0 ? agent.slice(a0, a1) : '';
  if (!branch) no('N1 找到附件分支', 'agent.mjs 里找不到附件分支 —— 断言落空比断言失败更危险');
  else {
    const h = hitsOf(branch);
    if (h.length) no('N1 内核分支话术', `附件分支里还留着「${h.join('、')}」`);
    else ok('N1 内核分支没说成「看不到 / 没权限 / 能力还没做」');
    if (!/feishu\.ingestAttachment\(/.test(branch)) {
      no('N2 内核分支真的走下载/抽取', '附件分支里没有 ingestAttachment(...) —— 接线断了');
    } else if (!/attachmentTurnText\(/.test(branch)) {
      no('N2 内核分支把附件原文交给模型', '抽取到了却没有拼进用户轮');
    } else ok('N2 内核分支把文本类附件交给 ingestAttachment 并拼进用户轮');
  }

  // N3 卡片模版 cannot-read 的**示例**——
  //   只查 sample，不查 when/fields：那两处是给模型的**告诫**，
  //   它们必须能说出「别写成没权限 / 能力还没做」，把告诫本身判成违规就成了自伤。
  const cr = BY_KIND.get('cannot-read');
  const hc = cr ? hitsOf(JSON.stringify(cr.sample)) : ['找不到 cannot-read'];
  if (hc.length) no('N3 cannot-read 模版示例', `示例里还有「${hc.join('、')}」`);
  else ok('N3 cannot-read 模版示例说的是「没解析」');

  // N4 群历史占位（feishu.mjs）—— 历史回读不取附件内容，是**能力边界**，不是旧政策。
  const fe = fs.readFileSync(path.join(HERE, 'agent', 'feishu.mjs'), 'utf8');
  const f0 = fe.indexOf('这是附件：历史回读');
  const seg = f0 >= 0 ? fe.slice(f0, f0 + 200) : '';
  if (!seg) no('N4 找到附件占位', 'feishu.mjs 里找不到「这是附件：历史回读…」这一句');
  else if (DEAD_POLICY.test(seg)) no('N4 群历史占位', '占位文案里还在引用已废止的下载禁令');
  else if (!/不取内容/.test(seg)) no('N4 附件占位要写明能力边界',
    '占位文案没说「历史回读不取内容」，读的人会以为附件被读过');
  else ok('N4 群历史占位说的是「历史回读不取内容」');

  // N5 旧话术必须已清掉 + 检测器自证（喂旧文案必须命中）
  const OLD_AGENT = '附件我不取 —— 飞书上的内容公司不让下载';
  const OLD_FE = '（这是附件：飞书内容禁止下载，附件只有下载这一条通道，所以我不取它的内容。）';
  if (!DEAD_POLICY.test(OLD_AGENT) || !DEAD_POLICY.test(OLD_FE)) {
    no('N5 检测器自证', '喂 2026-09-18 的旧话术没命中 —— DEAD_POLICY 是空转的');
  } else if (agent.includes(OLD_AGENT) || fe.includes(OLD_FE)) {
    no('N5 旧话术已清掉', 'agent.mjs / feishu.mjs 里还留着已废止的红线话术');
  } else ok('N5 旧话术已清掉，且检测器喂旧文案会命中');
}

/* ─────────────── I 文档里的自证数不能是写死的 ─────────────── */
head('I 数字 · 文档里写的自证项数必须等于实际项数');
{
  // 本项目第一号坑就是「文档里的数字复现不出来」（ADR-0013 §15.3）。
  // 所以文档里凡出现「N 项全过」，那 N 必须是**当前**的实测值。
  // 这一轮已经踩过一次：加了 G/H 两段之后文档里还写着 158。
  // 与其每次记得改，不如让它红。
  const docs = [
    'tools/reply-cards/README.md',
    'tools/reply-cards/contract.md',
    'PMO/守衡-回复卡片模版与语域规程.md',
  ];

  // ★ 期望值是**在本段开头一次性算出来的常量**，不是循环里边跑边读的 `pass`。
  //
  //   旧版写的是 `Math.abs(n - pass) > 12`（±12 容差），有两个毛病：
  //   ① `pass` 每轮 ok() 都在涨，于是三份文档被拿去比的是**三个不同的基准**
  //      （实测 229 / 230 / 231）—— 同一条断言自己跟自己不一致；
  //   ② 容差 ±12 让「必须等于」变成「差一个数量级也行」，而段标题与
  //      `contract.md:293` 的说明都写着「必须等于实际项数」。**断言比它声称的弱。**
  //
  //   现在：`docs.length` 是常量（每份文档无论走 ok 还是 no 都恰好贡献 1 条断言），
  //   所以 `passBeforeI + docs.length` 是确定的终值 —— 与本段自己的判定无关，不自指。
  const passBeforeI = pass;
  const expected = passBeforeI + docs.length;

  for (const rel of docs) {
    const f = path.join(ROOT, rel);
    if (!fs.existsSync(f)) { no(`I ${rel}`, '文件不存在'); continue; }
    const md = fs.readFileSync(f, 'utf8');
    const claims = [...md.matchAll(/(\d+)\s*项(?:全过|通过)/g)].map((m) => Number(m[1]));
    if (!claims.length) { ok(`I ${rel} 未写死项数`); continue; }
    const wrong = claims.filter((n) => n !== expected);
    if (wrong.length) {
      no(`I ${rel}`, `写着 ${wrong.join('/')} 项，本脚本实际是 ${expected} 项`);
    } else {
      ok(`I ${rel} 的 ${claims.join('/')} == 实测 ${expected}`);
    }
  }
}

/* ─────────────── 汇总 ─────────────── */
console.log(`\n${'═'.repeat(64)}`);
console.log(`通过 ${pass} 项 · 不通过 ${fail} 项`);
if (fail) {
  console.log('\n不通过明细：');
  for (const b of bad) console.log(`  · ${b}`);
  console.log('\n❌ 卡片模版与文档还不一致，别拿去发群。');
  process.exit(1);
}
console.log('✅ 十一个类型建得出、字段都真的被用、白名单与探针一致、降级可读、文档同步、语域规则正反都对');
