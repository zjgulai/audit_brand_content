#!/usr/bin/env node
/**
 * attachment_ingest.test.mjs —— 群附件入站（Q4-①）的执行点。
 *
 * ── 这条测试要守住的三件事
 *
 *   A. **政策话术已经清掉**：2026-09-18 的「飞书内容禁止下载」已于 2026-10-17 被推翻。
 *      今天如果说「不取」，只能是**能力**没接上，不能是**规矩**不允许。
 *      `agent.mjs` / `feishu.mjs` 里任何「按规矩不取」「公司不让下载」都是引用废止条款。
 *   B. **状态分得开**：ingested / empty / binary / too_large / download_failed /
 *      unsupported_type / bad_content 七档，**不许合并成一句「读不到」**。
 *      「没取到」与「文件里没有内容」在对方那里引出的下一步完全不同。
 *   C. **落盘不出仓、不留存**：下载根必须在仓外，且处理完立即删除（run-scoped）。
 *      AGENTS.md §2.6 改线后仍然有效的那条约束就是它。
 *
 * 全部离线：SDK 的 `messageResource.get` 被打桩，不碰真飞书；落盘根指到临时目录。
 *
 * 用法：node tools/agent/attachment_ingest.test.mjs
 * 退出码：0 全过 ｜ 1 有红
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

const res = [];
const T = (name, ok, detail) => res.push({ name, ok, detail });

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'attachment-test-'));
const tmpState = path.join(tmpRoot, 'state');
const tmpAttach = path.join(tmpRoot, 'attachments');
fs.mkdirSync(tmpState, { recursive: true });

process.env.SHOUHENG_STATE_DIR = tmpState;
process.env.SHOUHENG_ATTACHMENT_DIR = tmpAttach;
process.env.SHOUHENG_ATTACHMENT_LEDGER = path.join(tmpRoot, 'attachment_lifecycle.jsonl');
process.env.SHOUHENG_REQUIRE_MENTION = '1';     // E 段要验「不 @ 不下载」

const feishu = await import('./feishu.mjs');
const agent = await import('./agent.mjs');
const lifecycle = await import('./attachment_lifecycle.mjs');

// ★ 与 base ContentUnit/ReviewIR 的合法域同步：图片侧**合成**的 failure_kind
//   只允许这四个值。自由值（too_large / empty_file / runner_error / download_failed）
//   会让下游契约校验直接拒绝。这个集合只用于测试，防止未来再写自由值。
const LEGAL_FAILURE_KINDS = new Set(['fetch_error', 'parse_error', 'empty', 'unsupported']);
const imageFailureResults = [];
const legalKind = (r) => LEGAL_FAILURE_KINDS.has(r.failure_kind);

const origGet = feishu.client.im.v1.messageResource.get;
const setGet = (impl) => { feishu.client.im.v1.messageResource.get = impl; };
const restoreGet = () => { feishu.client.im.v1.messageResource.get = origGet; };

const fileMsg = (name = 'ad.txt', key = 'fk-1') => ({
  message_id: 'om_test_attach',
  message_type: 'file',
  content: JSON.stringify({ file_key: key, file_name: name }),
});
const imageMsg = () => ({
  message_id: 'om_test_image',
  message_type: 'image',
  content: JSON.stringify({ image_key: 'ik-1' }),
});

/* ── A. 解析与类型判定（纯函数）──────────────────────────────────────── */
{
  const a = feishu.parseAttachment(fileMsg('ad.csv'));
  T('A1 file 消息 → file_key / file_name 都取到',
    a.isAttachment && a.fileKey === 'fk-1' && a.fileName === 'ad.csv', JSON.stringify(a));
  const img = feishu.parseAttachment(imageMsg());
  T('A2 image 消息 → image_key 当 file_key 用',
    img.isAttachment && img.fileKey === 'ik-1', JSON.stringify(img));
  T('A3 text 消息 → 不是附件',
    feishu.parseAttachment({ message_type: 'text', content: '{"text":"hi"}' }).isAttachment === false, '');
  T('A4 坏 JSON → content 为空对象，不抛',
    feishu.parseAttachment({ message_type: 'file', content: '{oops' }).fileKey === null, '');

  T('A5 文本类扩展名：.md / .csv / .JSON 都认',
    feishu.isTextAttachment('a.md') && feishu.isTextAttachment('a.csv')
      && feishu.isTextAttachment('a.JSON'), '');
  T('A6 非文本类：.pdf / .docx / 无扩展名 → false（不猜）',
    !feishu.isTextAttachment('a.pdf') && !feishu.isTextAttachment('a.docx')
      && !feishu.isTextAttachment('a') && !feishu.isTextAttachment(null), '');
}

/* ── B. 七档状态 ────────────────────────────────────────────────────── */
const writeStub = (content, headers = { 'content-length': String(Buffer.byteLength(content)) }) =>
  async () => ({
    headers,
    writeFile: async (p) => { fs.writeFileSync(p, content); return p; },
    getReadableStream: () => ({ destroy() {} }),
  });

{
  setGet(writeStub('hello'));
  const r = await feishu.ingestAttachment(fileMsg());
  T('B1 ingested：文本附件 → 正文取到，状态与回复一致',
    r.status === 'ingested' && r.text === 'hello' && r.size === 5, JSON.stringify(r));
  T('B2 ★ 处理完立即删除：落盘根下没有残留目录（run-scoped）',
    fs.readdirSync(tmpAttach).length === 0, fs.readdirSync(tmpAttach).join(','));
}

{
  setGet(writeStub('hello'));
  const r = await feishu.ingestAttachment(fileMsg(), { maxChars: 3 });
  T('B3 截断必须显式标出（不许静默把半篇当全文）',
    r.status === 'ingested' && r.truncated === true && r.text === 'hel' && r.chars === 3,
    JSON.stringify({ t: r.text, truncated: r.truncated, chars: r.chars }));
}

{
  setGet(writeStub(''));
  const r = await feishu.ingestAttachment(fileMsg());
  T('B4 empty：0 字节 → 说「空的」，不是「读不到」、也不是「没取到」',
    r.status === 'empty' && r.reason === 'attachment_empty', r.status);
}

{
  setGet(writeStub(Buffer.from([0x68, 0x00, 0x69])));
  const r = await feishu.ingestAttachment(fileMsg('fake.txt'));
  T('B5 binary：扩展名像文本但含 NUL → 按二进制处理，不产出乱码假正文',
    r.status === 'binary' && r.reason === 'attachment_binary', r.status);
}

{
  let destroyed = false;
  setGet(async () => ({
    headers: { 'content-length': String(999 * 1024 * 1024) },
    writeFile: async () => { throw new Error('不该落盘'); },
    getReadableStream: () => ({ destroy() { destroyed = true; } }),
  }));
  const r = await feishu.ingestAttachment(fileMsg());
  T('B6 too_large：先读 Content-Length 再决定，绝不先写满盘',
    r.status === 'too_large' && destroyed === true, `${r.status}/destroyed=${destroyed}`);
}

{
  let destroyed = false;
  setGet(async () => ({
    headers: { 'content-length': String(999 * 1024 * 1024) },
    writeFile: async () => { throw new Error('不该落盘'); },
    getReadableStream: () => ({ destroy() { destroyed = true; } }),
  }));
  const r = await feishu.ingestAttachment(imageMsg());
  imageFailureResults.push(r);
  T('B6b ★ 图片超限：failure_kind=fetch_error（合法域），reason=image_too_large',
    r.status === 'image_judge_failed' && r.failure_kind === 'fetch_error'
      && r.reason === 'image_too_large' && destroyed === true && legalKind(r),
    JSON.stringify({ status: r.status, kind: r.failure_kind, reason: r.reason, destroyed }));
}

{
  setGet(async () => { throw new Error('模拟隧道断开'); });
  const r = await feishu.ingestAttachment(fileMsg());
  T('B7 download_failed：说「没取到」，不是「文件没内容」',
    r.status === 'download_failed' && /没取到/.test(r.reply) && /不是.*没有内容/.test(r.reply),
    r.status);
}

{
  setGet(async () => { throw new Error('模拟隧道断开'); });
  const r = await feishu.ingestAttachment(imageMsg());
  imageFailureResults.push(r);
  T('B7b ★ 图片下载失败：failure_kind=fetch_error，reason=image_download_failed',
    r.status === 'image_judge_failed' && r.failure_kind === 'fetch_error'
      && r.reason === 'image_download_failed' && legalKind(r),
    `${r.status}/${r.failure_kind}/${r.reason}`);
}

{
  let called = false, sawPath = false;
  setGet(writeStub(Buffer.from([0x89, 0x50, 0x4e, 0x47])));
  const r = await feishu.ingestAttachment(imageMsg(), {
    judgeImage: async ({ filePath }) => {
      called = true;
      sawPath = fs.existsSync(filePath);
      return {
        ok: true, row_status: 'ok',
        unit: { parse_status: 'ok' },
        judgment: {
          label: 'REVIEW', layer: 'L1', release_status: '待放行', run_state: 'OK',
          findings: [{ control_code: 'CP-1' }],
        },
      };
    },
  });
  T('B8 ★ 图片：下载后把本地路径交给 base 入口（调用发生且文件在判定时存在）',
    r.status === 'image_judged' && called === true && sawPath === true,
    `${r.status}/called=${called}/path=${sawPath}`);
  T('B9 图片摘要保留 OCR 边界与「不许说已通过」',
    /只覆盖\*\*图内文字/.test(r.summary) && /不许说「已通过」/.test(r.summary),
    String(r.summary).slice(0, 140));
  T('B9b 图片临时目录判定完仍删除', fs.readdirSync(tmpAttach).length === 0,
    fs.readdirSync(tmpAttach).join(','));
}
{
  setGet(writeStub(Buffer.from([0x89, 0x50, 0x4e, 0x47])));
  const r = await feishu.ingestAttachment(imageMsg(), {
    judgeImage: async () => ({
      ok: true, row_status: 'ok',
      unit: {
        parse_status: 'failed', failure_kind: 'empty',
        reason: 'OCR 成功完成，但没有识别出可读正文',
      },
      judgment: { label: '未审查', layer: 'L0', release_status: '待放行', run_state: 'OK', findings: [] },
    }),
  });
  imageFailureResults.push(r);
  T('B10 ★ 图片 OCR 失败 → image_judge_failed + 未审查/DP0，不是「附件不支持」',
    r.status === 'image_judge_failed' && r.failure_kind === 'empty' && legalKind(r)
      && /未审查（DP0）/.test(r.summary) && /failure_kind=empty/.test(r.summary)
      && /不是「附件不支持」/.test(r.summary),
    `${r.status}/${r.failure_kind}/${r.summary}`.slice(0, 200));
}
{
  setGet(writeStub(Buffer.from([0x89, 0x50, 0x4e, 0x47])));
  const r = await feishu.ingestAttachment(imageMsg(), {
    judgeImage: async () => ({ ok: false, error: '模拟入口坏了' }),
  });
  imageFailureResults.push(r);
  T('B11 ★ 图片判定入口坏了 → 未审查/DP0，failure_kind=parse_error（合法域）',
    r.status === 'image_judge_failed' && r.failure_kind === 'parse_error' && legalKind(r)
      && /未审查（DP0）/.test(r.summary) && /不是「附件不支持」/.test(r.summary),
    `${r.status}/${r.failure_kind}/${r.summary}`.slice(0, 200));
}

/* ── B12 反向对照：断开 judgeImage 调用，B8 的断言必须红 ─────────────── */
{
  const srcPath = path.join(HERE, 'feishu.mjs');
  const src = fs.readFileSync(srcPath, 'utf8');
  const needle = '        judged = await judgeImage({ filePath: dest, messageId: msg.message_id });';
  const mutantPath = path.join(HERE, `.mutant-image-${process.pid}.mjs`);
  if (!src.includes(needle)) {
    T('B12a ★ 反向对照自身有效：找得到 judgeImage 调用', false,
      '找不到 judgeImage 调用 —— 接线写法变了，本反向对照已失效');
  } else {
    T('B12a ★ 反向对照自身有效：找得到 judgeImage 调用', true, '');
    fs.writeFileSync(mutantPath,
      src.replace(needle, "        judged = { ok: false, error: 'DISCONNECTED' };"), 'utf8');
    try {
      const mutant = await import(`${pathToFileURL(mutantPath).href}?v=${Date.now()}`);
      let mCalled = false;
      // ★ 变异体是**另一份模块实例**，它有自己的 client；必须打桩到它身上，
      //   否则会拿假 message_id 去真飞书要资源（实测会打出一条 400）。
      mutant.client.im.v1.messageResource.get = writeStub(Buffer.from([0x89, 0x50, 0x4e, 0x47]));
      const mr = await mutant.ingestAttachment(imageMsg(), {
        judgeImage: async () => { mCalled = true; return { ok: true }; },
      });
      T('B12 ★ 断开调用后 base 入口不再被调用（B8 会红，证明它拦得住）',
        mCalled === false && mr.status === 'image_judge_failed' && legalKind(mr),
        `${mr.status}/${mr.failure_kind}/called=${mCalled}`);
      imageFailureResults.push(mr);
    } finally {
      try { fs.unlinkSync(mutantPath); } catch { /* 清理失败不影响断言 */ }
    }
  }
}

{
  setGet(async () => { throw new Error('不该被调用'); });
  const r = await feishu.ingestAttachment({
    message_id: 'om_bad', message_type: 'file', content: JSON.stringify({ file_name: 'x.txt' }),
  });
  T('B13 bad_content：有 file_name 没 file_key → 说拿不到下载地址，不瞎猜',
    r.status === 'bad_content' && /file_key/.test(r.reply), r.status);
}

/* ── B13b. 图片 failure_kind 枚举：不许再出现自由值 ─────────────────── */
T('B13b ★ 图片失败 failure_kind 全部落在合法枚举（fetch_error/parse_error/empty/unsupported）',
  imageFailureResults.length >= 5 && imageFailureResults.every(legalKind),
  imageFailureResults.map((r) => r.failure_kind).join(','));

/* ── B14–B19. 残留读数与生命周期台账（只数不删）─────────────────────── */
{
  const stale = path.join(tmpAttach, 'msg-stale-case');
  const fresh = path.join(tmpAttach, 'msg-fresh-case');
  fs.mkdirSync(stale, { recursive: true });
  fs.mkdirSync(fresh, { recursive: true });
  fs.writeFileSync(path.join(stale, 'a.txt'), 'x');
  const old = new Date(Date.now() - 2 * 60 * 60 * 1000);
  fs.utimesSync(stale, old, old);
  const c = lifecycle.countAttachmentResidue({ root: tmpAttach });
  T('B14 年龄分桶：2h 前的进 1to24h，刚建的在 lt1h',
    c.buckets['1to24h'] >= 1 && c.buckets.lt1h >= 1 && c.status === 'ok',
    JSON.stringify(c));
  T('B15 ★ 只数不删：统计完两个目录都还在（删除历史文件需要授权）',
    fs.existsSync(stale) && fs.existsSync(fresh), `${fs.existsSync(stale)}/${fs.existsSync(fresh)}`);
  fs.rmSync(stale, { recursive: true, force: true });
  fs.rmSync(fresh, { recursive: true, force: true });

  const absent = lifecycle.countAttachmentResidue({
    root: path.join(tmpRoot, 'does-not-exist'),
  });
  T('B16 落盘根不存在 → status=absent，不抛异常',
    absent.status === 'absent' && absent.dirs === 0, JSON.stringify(absent));

  // 启动横幅：两个数都必须出现，且 absent / untested 不许写成「0 个正常」。
  const fmt = lifecycle.formatResidue(absent);
  T('B16b 启动横幅读数含「残留 N 个 / 清理失败 M 个」且带 status',
    /attachments 残留 0 个 \/ 清理失败 0 个/.test(fmt) && /status=absent/.test(fmt), fmt);

  const rootIsFile = path.join(tmpRoot, 'root-is-file');
  fs.writeFileSync(rootIsFile, 'x');
  const unt = lifecycle.countAttachmentResidue({ root: rootIsFile });
  T('B16c ★ 落盘根读不到 → status=untested、failed=1（不许当成 0 个）',
    unt.status === 'untested' && unt.failed === 1, JSON.stringify(unt));

  // ★ 执行点：每次 ingestAttachment 都写 started + 终态；删除只针对本次自己创建的目录。
  const stale2 = path.join(tmpAttach, 'msg-stale-wired');
  fs.mkdirSync(stale2, { recursive: true });
  fs.utimesSync(stale2, old, old);
  setGet(writeStub('hello'));
  const before = fs.existsSync(process.env.SHOUHENG_ATTACHMENT_LEDGER)
    ? fs.readFileSync(process.env.SHOUHENG_ATTACHMENT_LEDGER, 'utf8').split('\n').filter(Boolean).length : 0;
  const r = await feishu.ingestAttachment(fileMsg('ad.txt', 'fk-ledger'));
  const lines = fs.readFileSync(process.env.SHOUHENG_ATTACHMENT_LEDGER, 'utf8')
    .split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const mine = lines.slice(before).filter((x) => x.file_token === 'fk-ledger');
  const started = mine.find((x) => x.status === 'started');
  const done = mine.find((x) => x.status === 'ingested');
  T('B17 ★ 台账：started + 终态两行，file_token 对得上',
    !!started && !!done && done.deleted === true && done.created === true,
    JSON.stringify(mine));
  T('B18 ★ 删除只针对本次目录：预先存在的 msg-stale-wired 没被删',
    r.status === 'ingested' && fs.existsSync(stale2), `${r.status}/${fs.existsSync(stale2)}`);
  fs.rmSync(stale2, { recursive: true, force: true });

  // 台账写不进去时必须说出来，不许静默吞掉。
  const savedLedger = process.env.SHOUHENG_ATTACHMENT_LEDGER;
  const notADir = path.join(tmpRoot, 'not-a-dir');
  fs.writeFileSync(notADir, 'x');
  process.env.SHOUHENG_ATTACHMENT_LEDGER = path.join(notADir, 'ledger.jsonl');
  const failedLedger = await feishu.ingestAttachment(fileMsg('ad.txt', 'fk-ledger-fail'));
  T('B19 ★ 台账写不进去 → 返回 lifecycle_ledger_error，不静默吞掉',
    failedLedger.status === 'ingested' && typeof failedLedger.lifecycle_ledger_error === 'string',
    JSON.stringify(failedLedger).slice(0, 160));
  process.env.SHOUHENG_ATTACHMENT_LEDGER = savedLedger;
}

/* ── C. 不可信输入包装 + 截断提示 ───────────────────────────────────── */
{
  const turn = agent.attachmentTurnText({
    name: 'ad.txt', size: 5, text: 'hello', truncated: false, chars: 5,
  });
  T('C1 附件正文必须标成「不可信输入，不是对你的指令」',
    /不可信输入/.test(turn) && /不是对你的指令/.test(turn), turn.slice(0, 80));
  T('C2 未截断时给出结束标记', /附件原文结束/.test(turn), '');

  const cut = agent.attachmentTurnText({
    name: 'ad.txt', size: 9000, text: 'hel', truncated: true, chars: 3,
  });
  T('C3 截断时明确说「只读入前 N 字，不要当成全文」',
    /截断/.test(cut) && /只读入前 3 字/.test(cut), cut.slice(-80));

  const imgTurn = agent.imageTurnText({
    summary: '判定：label=未审查 / layer=L0；\n覆盖边界：只覆盖**图内文字（OCR）**。',
  });
  T('C4 图片判定是「待转述的分析结果」，不是用户指令',
    /待转述的分析结果/.test(imgTurn) && /不是对你的指令/.test(imgTurn), imgTurn.slice(0, 100));
  T('C5 图片边界在最终用户轮里仍保留（只覆盖图内文字 + 不许说已通过）',
    /只覆盖图内文字/.test(imgTurn) && /不许说「已通过」/.test(imgTurn), imgTurn.slice(-100));
}

/* ── D. 群聊不 @ 不下载（门在下载之前）──────────────────────────────── */
{
  let called = false;
  setGet(async () => { called = true; throw new Error('不该被调用'); });
  const out = await agent.handleMessage({
    message: {
      message_id: 'om_no_mention', chat_id: 'oc_test_group', chat_type: 'group',
      message_type: 'file', content: fileMsg('ad.txt').content, mentions: [],
    },
    sender: { sender_id: { open_id: 'ou_test' } },
  });
  T('D1 群里没 @ 的附件 → 不回话，也**不下载**',
    out.reply === null && out.reason === 'not_mentioned' && called === false,
    `${out.reason}/downloaded=${called}`);
}

/* ── E. 落盘根在仓外 ───────────────────────────────────────────────── */
{
  const { attachmentDir } = await import('./config.mjs');
  const root = attachmentDir();
  const repo = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..');
  T('E1 落盘根不在仓库内（AGENTS.md §2.6 改线后仍有效）',
    !!root && !path.resolve(root).startsWith(repo + path.sep), String(root));
}

/* ── 出口 ───────────────────────────────────────────────────────────── */
restoreGet();
try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch { /* 临时目录清不掉不影响断言 */ }
const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} 附件入站自证 ${res.length - nFail}/${res.length} 项通过`);
console.log('   （SDK 打桩、落盘根临时目录；不碰真飞书、不读真附件）');
process.exit(nFail ? 1 : 0);
