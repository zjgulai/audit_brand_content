#!/usr/bin/env node
/**
 * inbox.test.mjs —— durable inbox（T0-06 / G-3）的判据
 *
 *   node tools/agent/inbox.test.mjs
 *
 * ⚠️ 全部落在临时目录（`SHOUHENG_INBOX_LEDGER` / `SHOUHENG_INBOX_CURSOR` /
 *    两个 outbox 环境变量在文件最上面就被指走，§2.4.4）。
 *
 * ── 判据（与阶段计划 T0-06 逐字对应）
 *
 *   1. 同一 `event_id` 投两次只处理一次（append 去重 + 游标只进不退）
 *   2. 处理中 kill → 重启从游标续传（游标只在处理**完成后**前进）
 *   3. 不重复回答（与 outbox 合用的那一条：崩溃前已 begin 的 reply，重启后 beginSend 必须 skip）
 *
 * 退出码：0 全过 / 1 有红 / 2 有未测（建不出临时目录、或 kill 测试的 spawn 不可用）。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

let TMP;
try {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'inbox_'));
} catch (e) {
  console.log(`⚠ 未测：建不出临时目录（${e.code ?? e.message}）—— 不是通过`);
  process.exit(2);
}
const INBOX = path.join(TMP, 'events-inbox.jsonl');
const CURSOR = path.join(TMP, 'events-inbox.cursor');
process.env.SHOUHENG_INBOX_LEDGER = INBOX;
process.env.SHOUHENG_INBOX_CURSOR = CURSOR;
process.env.SHOUHENG_OUTBOUND_LEDGER = path.join(TMP, 'ws_outbound.jsonl');
process.env.SHOUHENG_OUTBOX_LEDGER = path.join(TMP, 'ws_outbox.jsonl');

const inbox = await import('./inbox.mjs');
const ob = await import('./outbound.mjs');

const results = [];
const T = (id, ok, detail = '') => results.push({ id, ok, detail });
let untested = 0;

const lines = (f) => { try { return fs.readFileSync(f, 'utf8').trim().split('\n').filter(Boolean).length; } catch { return 0; } };
const reset = () => { for (const f of [INBOX, CURSOR, process.env.SHOUHENG_OUTBOUND_LEDGER, process.env.SHOUHENG_OUTBOX_LEDGER]) { try { fs.unlinkSync(f); } catch {} } };

/* ── 1. 同 event 投两次只处理一次 ────────────────────────────────── */
{
  reset();
  const a = inbox.appendEvent({ eventId: 'ev_1', type: 'message', payload: { text: 'hi' } });
  T('I1a 首次 append ok、seq=1', a.ok && !a.duplicate && a.seq === 1, JSON.stringify(a));

  const b = inbox.appendEvent({ eventId: 'ev_1', type: 'message', payload: { text: 'hi' } });
  T('I1b 同一 event_id 再投 → duplicate=true、不增行',
    b.ok && b.duplicate === true && lines(INBOX) === 1, `dup=${b.duplicate} lines=${lines(INBOX)}`);

  let n = 0;
  const r1 = await inbox.processNext(async () => { n++; });
  const r2 = await inbox.processNext(async () => { n++; });
  T('I1c 只处理一次（第二次无事件）', r1.processed === true && r2.processed === false && n === 1,
    `r1=${r1.processed} r2=${r2.processed} n=${n}`);
  T('I1d 游标前进到 1 并落盘', inbox.loadCursor().seq === 1, JSON.stringify(inbox.loadCursor()));

  // 反向：不同 event_id 不是重复
  const c = inbox.appendEvent({ eventId: 'ev_2', type: 'message', payload: {} });
  T('I1e 反面对照：不同 event_id → duplicate=false、seq=2',
    c.ok && c.duplicate === false && c.seq === 2, JSON.stringify(c));
}

/* ── 2. 处理中 kill → 重启从游标续传 ─────────────────────────────── */
{
  reset();
  inbox.appendEvent({ eventId: 'ev_kill', type: 'message', payload: { text: 'kill-me' } });

  const marker = path.join(TMP, 'marker.txt');
  const child = path.join(TMP, 'child.mjs');
  const inboxUrl = pathToFileURL(path.resolve('tools/agent/inbox.mjs')).href;
  const outUrl = pathToFileURL(path.resolve('tools/agent/outbound.mjs')).href;
  fs.writeFileSync(child, `
import fs from 'node:fs';
const inbox = await import(${JSON.stringify(inboxUrl)});
const ob = await import(${JSON.stringify(outUrl)});
const marker = ${JSON.stringify(marker)};
const r = await inbox.processNext(async (ev) => {
  fs.appendFileSync(marker, 'attempt\\n');
  // 崩溃点：已 begin、未 confirm、handler 永不返回 → 游标不得前进
  ob.beginSend({ logicalDeliveryId: ev.event_id, source: 'reply', chatId: 'oc', mode: 'text', text: 'x' });
  process.kill(process.pid, 'SIGKILL');
});
process.exit(r.processed ? 10 : 11);
`, 'utf8');

  const sp = spawnSync(process.execPath, [child], { env: process.env, timeout: 20000 });
  if (sp.error && sp.error.code === 'ENOENT') {
    // 未测 ≠ 红（文件头声明的退出码 2）：不许 push 一条失败断言把它变成 1
    untested++;
    results.push({ id: 'I2 kill 测试（未测：spawn 不可用）', ok: true, skipped: true, detail: String(sp.error) });
  } else {
    T('I2a 子进程被 SIGKILL 杀死（模拟处理中崩溃）',
      sp.signal === 'SIGKILL', `signal=${sp.signal} status=${sp.status}`);
    T('I2b 崩溃后游标**没有**前进（仍是 0）', inbox.loadCursor().seq === 0, JSON.stringify(inbox.loadCursor()));

    // 重启：父进程重新处理同一条
    let processed = 0; let begin2 = null;
    const r = await inbox.processNext(async (ev) => {
      processed++;
      fs.appendFileSync(marker, 'attempt\n');
      begin2 = ob.beginSend({ logicalDeliveryId: ev.event_id, source: 'reply', chatId: 'oc', mode: 'text', text: 'x' });
    });
    T('I2c 重启后事件被续传处理一次', r.processed === true && processed === 1, JSON.stringify(r));
    T('I2d 续传后游标前进到 1', inbox.loadCursor().seq === 1, JSON.stringify(inbox.loadCursor()));
    T('I2e 不重复回答：崩溃前已 begin 的 reply，重启后 beginSend 必须 skip',
      begin2?.ok === true && begin2.decision === 'skip' && begin2.reason === 'uncertain_reply_no_resend',
      JSON.stringify(begin2));
    T('I2f 消息台账 0 行（两次尝试都没有 confirm）', ob.readEntries().entries.length === 0,
      `rows=${ob.readEntries().entries.length}`);
  }
}

/* ── 4. 并发 processNext 单飞：同一条事件不许处理两遍 ───────────── */
{
  reset();
  inbox.appendEvent({ eventId: 'ev_conc', type: 'message', payload: {} });
  let calls = 0;
  const h = async () => { calls++; await new Promise((r) => setTimeout(r, 20)); };
  const [a, b] = await Promise.all([inbox.processNext(h), inbox.processNext(h)]);
  T('I4 两个并发 processNext → handler 只调用一次',
    calls === 1 && [a.processed, b.processed].filter(Boolean).length === 1,
    `calls=${calls} a=${a.processed} b=${b.processed}`);
}

/* ── 5. 坏行 / 重复 seq / 游标领先 → 未测，不许越过 ─────────────── */
{
  reset();
  inbox.appendEvent({ eventId: 'ev_ok', type: 'message', payload: {} });
  fs.appendFileSync(INBOX, '{半截\n', 'utf8');
  const cur0 = inbox.loadCursor().seq;
  const r = await inbox.processNext(async () => {});
  T('I5 有坏行 → 未测且不推进游标', r.ok === false && Boolean(r.untested) && inbox.loadCursor().seq === cur0,
    JSON.stringify(r));
}
{
  reset();
  fs.writeFileSync(INBOX,
    JSON.stringify({ seq: 1, at: new Date().toISOString(), event_id: 'ev_a', type: 'x', payload: null }) + '\n' +
    JSON.stringify({ seq: 1, at: new Date().toISOString(), event_id: 'ev_b', type: 'x', payload: null }) + '\n', 'utf8');
  const r = await inbox.processNext(async () => {});
  T('I6 重复 seq → 未测（不许静默跳过一个）', r.ok === false && Boolean(r.untested), JSON.stringify(r));
}
{
  reset();
  inbox.appendEvent({ eventId: 'ev_ahead', type: 'message', payload: {} });
  inbox.saveCursor({ seq: 5, eventId: 'x' });
  const r = await inbox.processNext(async () => {});
  T('I7 游标领先日志末序号 → 未测（防日志轮转后永久跳过）',
    r.ok === false && r.cursorAhead === true, JSON.stringify(r));
}
{
  reset();
  fs.writeFileSync(INBOX,
    JSON.stringify({ seq: 1, at: new Date().toISOString(), event_id: 'ev_dup', type: 'x', payload: null }) + '\n' +
    JSON.stringify({ seq: 2, at: new Date().toISOString(), event_id: 'ev_dup', type: 'x', payload: null }) + '\n', 'utf8');
  const r = await inbox.processNext(async () => {});
  T('I8 同一 event_id 两行 → 未测（不许处理两次）', r.ok === false && Boolean(r.untested), JSON.stringify(r));
}

/* ── 6. 事件 id 类型 / 日志轮转 / 游标写失败 ───────────────────── */
{
  reset();
  const r = inbox.appendEvent({ eventId: 1729000000000, type: 'message', payload: {} });
  T('I9 非字符串 event_id → 拒绝（不许写出 reader 判坏的日志）',
    r.ok === false && String(r.error).startsWith('bad_event_id'), JSON.stringify(r));
  T('I9b 拒绝后日志仍为空', lines(INBOX) === 0, `lines=${lines(INBOX)}`);
}
{
  reset();
  inbox.appendEvent({ eventId: 'ev_rot_1', type: 'message', payload: {} });
  await inbox.processNext(async () => {});
  const curBefore = inbox.loadCursor();
  // 模拟轮转：删掉旧日志，新日志从 seq=1 重新长起来
  fs.unlinkSync(INBOX);
  inbox.appendEvent({ eventId: 'ev_rot_2', type: 'message', payload: {} });
  const r = await inbox.processNext(async () => {});
  T('I10 日志轮转（ino 变化）→ 未测（即使新 seq 已超过旧游标）',
    r.ok === false && Boolean(r.untested) && curBefore.seq === 1, JSON.stringify(r));
}
{
  reset();
  inbox.appendEvent({ eventId: 'ev_cursor_fail', type: 'message', payload: {} });
  const real = process.env.SHOUHENG_INBOX_CURSOR;
  const curFile = path.join(TMP, 'cursor_ro');
  fs.writeFileSync(curFile, JSON.stringify({ seq: 0, event_id: null, log_ino: null }) + '\n', 'utf8');
  // 让 writeAtomic 的临时路径撞上一个目录：读游标正常，写游标必失败（无需 chmod）。
  fs.mkdirSync(`${curFile}.tmp.${process.pid}`);
  let calls = 0;
  let r;
  let threw = null;
  try {
    process.env.SHOUHENG_INBOX_CURSOR = curFile;
    r = await inbox.processNext(async () => { calls++; });
  } catch (e) {
    threw = e; // ★ 回归时抛异常也落成一条红断言，而不是让测试进程死得只剩 stack
  } finally {
    process.env.SHOUHENG_INBOX_CURSOR = real;
    try { fs.rmdirSync(`${curFile}.tmp.${process.pid}`); } catch {}
  }
  T('I11 游标写失败 → {ok:false, processed:true, untested} 而不是抛异常',
    threw === null && r.ok === false && r.processed === true && Boolean(r.untested) && calls === 1,
    threw ? `threw: ${threw.code ?? threw.message}` : JSON.stringify(r));
}

/* ── 7. handler 超时 / seq 缺号 / 游标 event_id 不一致 ──────────── */
{
  reset();
  inbox.appendEvent({ eventId: 'ev_timeout', type: 'message', payload: {} });
  const hang = () => new Promise(() => {}); // 永不 settle
  const r = await inbox.processNext(hang, { timeoutMs: 60 });
  T('I12 handler 永不返回 → 超时未测、游标不动', r.ok === false && r.timedOut === true && inbox.loadCursor().seq === 0,
    JSON.stringify(r));
  // 链必须恢复：下一次正常调用仍能处理
  const r2 = await inbox.processNext(async () => {});
  T('I12b 超时后链恢复，事件仍可被处理', r2.ok === true && r2.processed === true, JSON.stringify(r2));
}
{
  reset();
  fs.writeFileSync(INBOX,
    JSON.stringify({ seq: 1, at: new Date().toISOString(), event_id: 'ev_g1', type: 'x', payload: null }) + '\n' +
    JSON.stringify({ seq: 3, at: new Date().toISOString(), event_id: 'ev_g3', type: 'x', payload: null }) + '\n', 'utf8');
  const r1 = await inbox.processNext(async () => {});
  const r2 = await inbox.processNext(async () => {});
  T('I13 seq 缺号（1→3）→ 处理完 1 后判未测，不许跳过 2',
    r1.processed === true && r2.ok === false && r2.seqGap === true, JSON.stringify({ r1, r2 }));
}
{
  reset();
  inbox.appendEvent({ eventId: 'ev_curid', type: 'message', payload: {} });
  await inbox.processNext(async () => {});
  const cur = inbox.loadCursor();
  inbox.saveCursor({ seq: cur.seq, eventId: 'someone_else', logIno: cur.log_ino });
  const r = await inbox.processNext(async () => {});
  T('I14 游标 seq 的 event_id 对不上 → 未测', r.ok === false && Boolean(r.untested), JSON.stringify(r));
}

/* ── 3. 游标原子写：半截文件不会被读成合法游标 ───────────────────── */
{
  reset();
  fs.writeFileSync(CURSOR, '{半截', 'utf8');
  const cur = inbox.loadCursor();
  T('I3 损坏的游标文件 → 保守回退到 0（宁可重放，不跳过）', cur.seq === 0, JSON.stringify(cur));
}

/* ── 8. 跨进程 append 的锁真的在拦（不是只靠单进程顺序） ─────────── */
{
  reset();
  const inboxUrl2 = pathToFileURL(path.resolve('tools/agent/inbox.mjs')).href;
  const child2 = path.join(TMP, 'appender.mjs');
  fs.writeFileSync(child2, `
const inbox = await import(${JSON.stringify(inboxUrl2)});
const tag = process.argv[2];
const r = inbox.appendEvent({ eventId: 'ev_cp_' + tag, type: 'message', payload: { tag } });
process.exit(r.ok ? 0 : 3);
`, 'utf8');
  const { spawn } = await import('node:child_process');
  const run = (tag) => new Promise((resolve) => {
    const p = spawn(process.execPath, [child2, tag], { env: process.env });
    p.on('exit', (code) => resolve(code));
  });
  // 8 个进程并发各写一条不同事件
  const codes = await Promise.all(Array.from({ length: 8 }, (_, i) => run(String(i))));
  const r = inbox.readEvents();
  const seqs = r.events.map((e) => e.seq).sort((a, b) => a - b);
  T('I15a 8 进程并发 append → 全部成功、seq 恰为 1..8、无重复',
    codes.every((c) => c === 0) && seqs.length === 8 && seqs.every((s, i) => s === i + 1) && r.duplicates.length === 0,
    `codes=${codes} seqs=${seqs} dup=${r.duplicates.length}`);
  // 同一 id 并发 6 次：只许 1 行
  await Promise.all(Array.from({ length: 6 }, () => run('same')));
  const r2 = inbox.readEvents();
  T('I15b 同 event_id 6 进程并发 → 只落 1 行',
    r2.events.filter((e) => e.event_id === 'ev_cp_same').length === 1,
    `n=${r2.events.filter((e) => e.event_id === 'ev_cp_same').length}`);
}

/* ── 9. stats() 必须与 processNext 同口径（缺号 / 轮转） ─────────── */
{
  reset();
  fs.writeFileSync(INBOX,
    JSON.stringify({ seq: 1, at: new Date().toISOString(), event_id: 'ev_s1', type: 'x', payload: null }) + '\n' +
    JSON.stringify({ seq: 3, at: new Date().toISOString(), event_id: 'ev_s3', type: 'x', payload: null }) + '\n', 'utf8');
  T('I16a stats().seqGap 报出缺号（不许读成健康）', inbox.stats().seqGap === 1, JSON.stringify(inbox.stats()));
}
{
  reset();
  inbox.appendEvent({ eventId: 'ev_stat_rot', type: 'message', payload: {} });
  await inbox.processNext(async () => {});
  fs.unlinkSync(INBOX);
  inbox.appendEvent({ eventId: 'ev_stat_rot2', type: 'message', payload: {} });
  T('I16b stats().rotated 报出日志轮转', inbox.stats().rotated === true, JSON.stringify(inbox.stats()));
}

const nFail = results.filter((r) => !r.ok).length;
for (const r of results) console.log(`  ${r.ok ? '✅' : '❌'} ${r.id}${r.ok ? '' : `  ← ${r.detail}`}`);
const verdict = nFail ? '❌' : (untested ? '⚠' : '✅');
console.log(`\n${verdict} inbox ${results.length - nFail}/${results.length} 项通过`
            + `（临时目录 ${path.basename(TMP)}；未测 ${untested} 项）`);
process.exit(nFail ? 1 : (untested ? 2 : 0));
