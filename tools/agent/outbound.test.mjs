#!/usr/bin/env node
/**
 * outbound.test.mjs —— outbox（T0-05 / G-2）的判据
 *
 *   node tools/agent/outbound.test.mjs
 *
 * ⚠️ 全部落在临时目录：`SHOUHENG_OUTBOUND_LEDGER`（消息台账）与
 *    `SHOUHENG_OUTBOX_LEDGER`（投递状态机）在文件最上面就被指走（§2.4.4）。
 *
 * ── 为什么每条都要有反面
 *
 * outbox 修的是**同一件事被发两遍**与**该重发的没重发**这两个不对称代价：
 *   · 双重发送 → 群里看到两条一样的回答（比漏发更伤信任，因为它重复且可见）；
 *   · 该重发没重发 → 主动推送永久丢失（漏发不可见，但代价是对方收不到）。
 * 所以决策规则必须**按来源分叉**，而每条断言都配一个「它会不会恒真」的对照。
 *
 * 判据口径（与阶段计划 T0-05 逐字对应）：
 *   R1 同一 logical_delivery_id 发两次只发一次
 *   R2 卡片 + 降级文本两个变体只发一次
 *   R3 reply 崩溃 → 不重发
 *   R4 proactive-* 崩溃 → 重发
 *   R5 pending 超时 → 标 unknown
 *
 * 退出码：0 全过 / 1 有红 / 2 未测（连临时目录都建不出来）。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

let TMP;
try {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'outbound_'));
} catch (e) {
  console.log(`⚠ 未测：建不出临时目录（${e.code ?? e.message}）—— 不是通过`);
  process.exit(2);
}
process.env.SHOUHENG_OUTBOUND_LEDGER = path.join(TMP, 'ws_outbound.jsonl');
process.env.SHOUHENG_OUTBOX_LEDGER = path.join(TMP, 'ws_outbox.jsonl');
process.env.SHOUHENG_OUTBOX_TTL_MS = '300000'; // 5 分钟

const ob = await import('./outbound.mjs');

const results = [];
const T = (id, ok, detail = '') => results.push({ id, ok, detail });

const CHAT = 'oc_test';
const KEY = 'om_test_1';
const ID = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: KEY });
// 模拟「崩溃」：写一条 pid 已死的 begin。用一个大到不可能存在的 pid，
// 这样 outboxState 能区分「在途（pid 活着）」与「崩溃（pid 死了）」。
const DEAD_PID = 2147483647;

function reset() {
  for (const f of [process.env.SHOUHENG_OUTBOUND_LEDGER, process.env.SHOUHENG_OUTBOX_LEDGER]) {
    try { fs.unlinkSync(f); } catch { /* 不存在即可 */ }
  }
}
const ledgerRows = () => ob.readEntries().entries.length;
const outboxLines = () => {
  try { return fs.readFileSync(process.env.SHOUHENG_OUTBOX_LEDGER, 'utf8').trim().split('\n').filter(Boolean).length; }
  catch { return 0; }
};

/* ── R0 纯函数：id 稳定、且同键跨变体相等 ─────────────────────────── */
{
  const a = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: KEY });
  const b = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: KEY });
  const c = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'other' });
  T('R0 logicalDeliveryId 同键同值、异键异值', a === b && a !== c, `${a} / ${c}`);
}

/* ── P1/R1：同一 id 发两次只发一次 ───────────────────────────────── */
{
  reset();
  const b1 = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: '回答一' });
  T('R1a 新 id 决策=send', b1.ok && b1.decision === 'send', JSON.stringify(b1));

  const c1 = ob.confirmSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text',
                              messageIds: ['om_sent_1'], text: '回答一' });
  T('R1b confirm 后消息台账恰好 1 行', c1.ok && ledgerRows() === 1, `rows=${ledgerRows()}`);

  const b2 = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: '回答一' });
  T('R1c 同一 id 第二次决策=skip（只发一次）',
    b2.ok && b2.decision === 'skip' && b2.reason === 'already_confirmed', JSON.stringify(b2));
  T('R1d 第二次 begin 未写消息台账', ledgerRows() === 1, `rows=${ledgerRows()}`);
}

/* ── R2：卡片 + 降级文本只发一次 ─────────────────────────────────── */
{
  reset();
  // 同一逻辑投递：先尝试卡片，replyCard 失败后由 daemon 降级为纯文本。
  // 两个变体**共用一个 logical_delivery_id**（key 来自原消息，不是正文）。
  const ID2 = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'om_test_2' });
  ob.beginSend({ logicalDeliveryId: ID2, source: 'reply', chatId: CHAT, mode: 'card', text: '卡片内容' });
  // 卡片失败 → 降级文本发出 → confirm 记的是实际发出的变体
  ob.confirmSend({ logicalDeliveryId: ID2, source: 'reply', chatId: CHAT, mode: 'text',
                   messageIds: ['om_sent_2'], text: '降级文本' });

  const b = ob.beginSend({ logicalDeliveryId: ID2, source: 'reply', chatId: CHAT, mode: 'card', text: '卡片内容' });
  T('R2a 卡片+降级文本共用一个 id → 第二次 skip', b.ok && b.decision === 'skip', JSON.stringify(b));

  // 反向：如果两个变体用了**不同** id（错误做法），就会发两次 —— 这里断言纯函数不会给出同一个 id 之外的魔法，
  // 而是暴露「调用方必须传同一个 key」。用不同 key 演示确实会发第二次。
  const ID2b = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'om_test_2:fallback' });
  const b2 = ob.beginSend({ logicalDeliveryId: ID2b, source: 'reply', chatId: CHAT, mode: 'text', text: '降级文本' });
  T('R2b 反面对照：不同 key → 会被当成另一次投递（证明 R2a 不是恒真）',
    b2.ok && b2.decision === 'send', JSON.stringify(b2));
  ob.confirmSend({ logicalDeliveryId: ID2b, source: 'reply', chatId: CHAT, mode: 'text',
                   messageIds: ['om_sent_2b'], text: '降级文本' });
  T('R2c 台账最终 2 行（本对照自身也落账）', ledgerRows() === 2, `rows=${ledgerRows()}`);
}

/* ── R3：reply 崩溃 → 不重发 ─────────────────────────────────────── */
{
  reset();
  const ID3 = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'om_test_3' });
  // 崩溃：begin 的 pid 已死（模拟进程被杀/重启后旧 pid 不存在）
  ob.beginSend({ logicalDeliveryId: ID3, source: 'reply', chatId: CHAT, mode: 'text', text: '答到一半', pid: DEAD_PID });
  const again = ob.beginSend({ logicalDeliveryId: ID3, source: 'reply', chatId: CHAT, mode: 'text', text: '答到一半' });
  T('R3 reply 崩溃后重启 → skip（不重发）',
    again.ok && again.decision === 'skip' && again.reason === 'uncertain_reply_no_resend', JSON.stringify(again));
  T('R3b 消息台账 0 行（崩溃未 confirm）', ledgerRows() === 0, `rows=${ledgerRows()}`);
}

/* ── R4：proactive 崩溃 → 重发 ───────────────────────────────────── */
{
  reset();
  const ID4 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'alert_1' });
  ob.beginSend({ logicalDeliveryId: ID4, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '基线告警', pid: DEAD_PID });
  const again = ob.beginSend({ logicalDeliveryId: ID4, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '基线告警' });
  T('R4 proactive 崩溃后重启 → send（重发）',
    again.ok && again.decision === 'send' && again.reason === 'uncertain_proactive_resend', JSON.stringify(again));

  // 反向：已 confirm 的 proactive 不许再发（重发只在“不确定”时）
  ob.confirmSend({ logicalDeliveryId: ID4, source: 'proactive-baseline', chatId: CHAT, mode: 'text',
                   messageIds: ['om_sent_4'], text: '基线告警' });
  const third = ob.beginSend({ logicalDeliveryId: ID4, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '基线告警' });
  T('R4b 反面对照：已 confirm 的 proactive 也必须 skip（重发不越过确定态）',
    third.ok && third.decision === 'skip' && third.reason === 'already_confirmed', JSON.stringify(third));
}

/* ── R5：pending 超时 → 标 unknown ───────────────────────────────── */
{
  reset();
  const ID5 = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'om_test_5' });
  ob.beginSend({ logicalDeliveryId: ID5, source: 'reply', chatId: CHAT, mode: 'text', text: '超时样本' });
  T('R5a 新鲜 begin（pid 活着）状态=pending', ob.outboxState(ID5).state === 'pending', ob.outboxState(ID5).state);

  // 时间前拨 10 分钟（不改真实时钟）：outboxState 的 now 可注入
  const FUTURE = Date.now() + 10 * 60 * 1000;
  T('R5a2 前拨后状态=unknown（timeout）',
    ob.outboxState(ID5, { now: FUTURE }).state === 'unknown', ob.outboxState(ID5, { now: FUTURE }).state);

  const before = outboxLines();
  const dry = ob.reconcilePending({ now: FUTURE, ttlMs: 5 * 60 * 1000, apply: false });
  T('R5b dry-run 不写盘', outboxLines() === before && dry.unknown.includes(ID5), JSON.stringify(dry.unknown));

  const rec = ob.reconcilePending({ now: FUTURE, ttlMs: 5 * 60 * 1000, apply: true });
  T('R5c apply 后状态=unknown', rec.unknown.includes(ID5) && ob.outboxState(ID5).state === 'unknown',
    `unknown=${JSON.stringify(rec.unknown)} state=${ob.outboxState(ID5).state}`);

  const again = ob.beginSend({ logicalDeliveryId: ID5, source: 'reply', chatId: CHAT, mode: 'text', text: '超时样本' });
  T('R5d unknown 的 reply 仍不重发', again.decision === 'skip', JSON.stringify(again));

  // 反向：未超时的 pending 不会被标 unknown
  const ID5b = ob.logicalDeliveryId({ source: 'proactive-pending', chatId: CHAT, key: 'fresh_1' });
  ob.beginSend({ logicalDeliveryId: ID5b, source: 'proactive-pending', chatId: CHAT, mode: 'text', text: '新提醒' });
  const rec2 = ob.reconcilePending({ now: Date.now(), ttlMs: 5 * 60 * 1000, apply: false });
  T('R5e 反面对照：未超时的 pending 不进 unknown', !rec2.unknown.includes(ID5b), JSON.stringify(rec2.unknown));
}

/* ── R7：在途（pid 活着）→ 任何来源都不重发 ─────────────────────── */
{
  reset();
  const ID7 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'in_flight_1' });
  // 默认 pid = 本进程（活着）
  ob.beginSend({ logicalDeliveryId: ID7, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '正在发' });
  const again = ob.beginSend({ logicalDeliveryId: ID7, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '正在发' });
  T('R7 反面对照：另一进程还在发（pid 活着）→ proactive 也 skip',
    again.ok && again.decision === 'skip' && again.reason === 'in_flight', JSON.stringify(again));
}

/* ── R8：旧 unknown 不许压过之后的新 begin（崩溃恢复） ───────────── */
{
  reset();
  const ID8 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'recover_1' });
  ob.beginSend({ logicalDeliveryId: ID8, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '告警', pid: DEAD_PID });
  ob.reconcilePending({ now: Date.now(), ttlMs: 5 * 60 * 1000, apply: true }); // → 显式 unknown
  const b1 = ob.beginSend({ logicalDeliveryId: ID8, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '告警' });
  const b2 = ob.beginSend({ logicalDeliveryId: ID8, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '告警' });
  T('R8a 崩溃后第一次重发=send', b1.decision === 'send', JSON.stringify(b1));
  T('R8b 重发在途时第二次=skip（旧 unknown 不遮新 begin）',
    b2.decision === 'skip' && b2.reason === 'in_flight', JSON.stringify(b2));
}

/* ── R9：reply 借道 resend 也不许重发 ────────────────────────────── */
{
  reset();
  const ID9 = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'om_test_9' });
  ob.beginSend({ logicalDeliveryId: ID9, source: 'reply', chatId: CHAT, mode: 'text', text: '答', pid: DEAD_PID });
  const r = ob.beginSend({ logicalDeliveryId: ID9, source: 'resend', chatId: CHAT, mode: 'text', text: '答' });
  T('R9 reply 崩溃后用 source=resend 重试 → 仍 skip',
    r.decision === 'skip' && r.reason === 'uncertain_reply_no_resend', JSON.stringify(r));

  const ID9b = ob.logicalDeliveryId({ source: 'resend', chatId: CHAT, key: 'resend_1' });
  ob.beginSend({ logicalDeliveryId: ID9b, source: 'resend', chatId: CHAT, mode: 'text', text: '补发', pid: DEAD_PID });
  const r2 = ob.beginSend({ logicalDeliveryId: ID9b, source: 'resend', chatId: CHAT, mode: 'text', text: '补发' });
  T('R9b resend 自身崩溃后也不重发（at-most-once）',
    r2.decision === 'skip' && r2.reason === 'uncertain_reply_no_resend', JSON.stringify(r2));
}

/* ── R10：outbox 读不出 → refuse（不许当成 absent 再发） ─────────── */
{
  reset();
  const real = process.env.SHOUHENG_OUTBOX_LEDGER;
  let r;
  try {
    process.env.SHOUHENG_OUTBOX_LEDGER = TMP; // 指向目录 → EISDIR
    r = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: 'x' });
  } finally {
    process.env.SHOUHENG_OUTBOX_LEDGER = real;
  }
  T('R10 outbox 不可读 → refuse(outbox_untested) 而不是 send',
    r.ok === false && r.decision === 'refuse' && r.reason === 'outbox_untested', JSON.stringify(r));
}

/* ── R11：坏 at（epoch 毫秒/垃圾）→ refuse，不许写成 NaN 行 ───────── */
{
  reset();
  const r1 = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: 'x', at: 'not-a-date' });
  T('R11 无法解析的 at → refuse(bad_at)', r1.ok === false && r1.reason === 'bad_at', JSON.stringify(r1));
  const r2 = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: 'x', at: Date.now() });
  T('R11b epoch 毫秒 at 被规范成 ISO', r2.ok === true && r2.decision === 'send', JSON.stringify(r2));
  const st = ob.outboxState(ID);
  T('R11c 落盘的 begin.at 是合法 ISO', st.state === 'pending' || st.state === 'unknown',
    JSON.stringify(st));
}

/* ── R12：跨来源同 id（reply → resend 必须算出同一个 id） ─────────── */
{
  const a = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: 'same_key' });
  const b = ob.logicalDeliveryId({ source: 'resend', chatId: CHAT, key: 'same_key' });
  T('R12 source 不参与 id 计算（reply 与 resend 同 id）', a === b, `${a} / ${b}`);
}

/* ── R13：reconcile 必须报出 untested，不许静默丢掉 ───────────────── */
{
  reset();
  const bad = { at: 'not-a-date', type: 'begin', logical_delivery_id: 'badat',
                source: 'proactive-baseline', pid: DEAD_PID };
  fs.writeFileSync(process.env.SHOUHENG_OUTBOX_LEDGER, JSON.stringify(bad) + '\n');
  const rec = ob.reconcilePending({ now: Date.now(), apply: false });
  T('R13 bad_begin_at → reconcile ok:false 且列出 untestedIds',
    rec.ok === false && (rec.untestedIds ?? []).some((x) => x.id === 'badat'), JSON.stringify(rec));
}

/* ── R14：outbox 未测时 confirm 重试不许重复写消息台账 ───────────── */
{
  reset();
  const real = process.env.SHOUHENG_OUTBOX_LEDGER;
  let c1, c2;
  try {
    process.env.SHOUHENG_OUTBOX_LEDGER = TMP; // 目录 → untested
    const ID14 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'untested_1' });
    c1 = ob.confirmSend({ logicalDeliveryId: ID14, source: 'proactive-baseline', chatId: CHAT, mode: 'text', messageIds: [], text: '同一条提醒' });
    c2 = ob.confirmSend({ logicalDeliveryId: ID14, source: 'proactive-baseline', chatId: CHAT, mode: 'text', messageIds: [], text: '同一条提醒' });
  } finally {
    process.env.SHOUHENG_OUTBOX_LEDGER = real;
  }
  T('R14 两次 confirm 只落 1 行台账', ledgerRows() === 1, `rows=${ledgerRows()} c1=${c1.ok} c2=${c2.ok}`);
}

/* ── R15：跨进程锁——多个进程同时 begin 同一 id，只能有一个 send ──── */
{
  reset();
  const child = path.join(TMP, 'child_send.mjs');
  const obUrl = pathToFileURL(path.resolve('tools/agent/outbound.mjs')).href;
  fs.writeFileSync(child, `
const ob = await import(${JSON.stringify(obUrl)});
const id = 'cross_proc_id';
const r = ob.beginSend({ logicalDeliveryId: id, source: 'proactive-baseline', chatId: 'oc', mode: 'text', text: 'x' });
if (r.decision === 'send') {
  await new Promise((res) => setTimeout(res, 40));
  ob.confirmSend({ logicalDeliveryId: id, source: 'proactive-baseline', chatId: 'oc', mode: 'text', messageIds: ['om_cp'], text: 'x' });
}
console.log(r.decision);
process.exit(0);
`, 'utf8');

  const runChild = () => new Promise((res) => {
    const p = spawn(process.execPath, [child], { env: process.env, stdio: 'ignore' });
    p.on('exit', (code) => res(code));
  });
  await Promise.all([runChild(), runChild(), runChild(), runChild()]);
  const rows = ob.readOutbox().records;
  const begins = rows.filter((x) => x.type === 'begin' && x.logical_delivery_id === 'cross_proc_id').length;
  T('R15 四个并发进程 → 只有 1 次 begin、1 行消息台账', begins === 1 && ledgerRows() === 1,
    `begins=${begins} rows=${ledgerRows()}`);
}

/* ── R16：消息台账写失败 → 不许写 confirm；恢复重试后补上 ─────────── */
{
  reset();
  const ID16 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'ledger_fail' });
  ob.beginSend({ logicalDeliveryId: ID16, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: 'x' });
  const realLedger = process.env.SHOUHENG_OUTBOUND_LEDGER;
  let c1;
  try {
    process.env.SHOUHENG_OUTBOUND_LEDGER = TMP; // 目录 → recordSend 失败
    c1 = ob.confirmSend({ logicalDeliveryId: ID16, source: 'proactive-baseline', chatId: CHAT, mode: 'text', messageIds: [], text: 'x' });
  } finally {
    process.env.SHOUHENG_OUTBOUND_LEDGER = realLedger;
  }
  const confirmsAfterFail = ob.readOutbox().records.filter((x) => x.type === 'confirm' && x.logical_delivery_id === ID16).length;
  T('R16a 台账写失败 → ok:false、state=unconfirmed、且**不写** confirm 行',
    c1.ok === false && c1.state === 'unconfirmed' && confirmsAfterFail === 0, JSON.stringify({ c1, confirmsAfterFail }));
  const c2 = ob.confirmSend({ logicalDeliveryId: ID16, source: 'proactive-baseline', chatId: CHAT, mode: 'text', messageIds: [], text: 'x' });
  const confirmsAfter = ob.readOutbox().records.filter((x) => x.type === 'confirm' && x.logical_delivery_id === ID16).length;
  T('R16b 恢复后重试成功，台账 1 行、confirm 1 行',
    c2.ok === true && ledgerRows() === 1 && confirmsAfter === 1, JSON.stringify({ c2, rows: ledgerRows(), confirmsAfter }));
}

/* ── R17：outbox 有坏行 → refuse（不许把坏行当 absent 再发） ──────── */
{
  reset();
  fs.writeFileSync(process.env.SHOUHENG_OUTBOX_LEDGER, '{半截\n', 'utf8');
  const r = ob.beginSend({ logicalDeliveryId: ID, source: 'reply', chatId: CHAT, mode: 'text', text: 'x' });
  T('R17 outbox 有坏行 → refuse(outbox_untested)',
    r.ok === false && r.reason === 'outbox_untested', JSON.stringify(r));
}

/* ── R18：begin.at 来自未来 → untested（不许静默推迟超时窗口） ───── */
{
  reset();
  const ID18 = ob.logicalDeliveryId({ source: 'proactive-baseline', chatId: CHAT, key: 'future_at' });
  const future = new Date(Date.now() + 10 * 60 * 1000).toISOString();
  ob.beginSend({ logicalDeliveryId: ID18, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: 'x', at: future });
  const st = ob.outboxState(ID18);
  T('R18 future begin.at → state=untested', st.state === 'untested' && st.error === 'future_begin_at',
    JSON.stringify(st));
}

/* ── R19：begin 记录的 source 参与判定（reply 不许借 proactive 重发）── */
{
  reset();
  const K = 'cross_source_reply';
  const idReply = ob.logicalDeliveryId({ source: 'reply', chatId: CHAT, key: K });
  ob.beginSend({ logicalDeliveryId: idReply, source: 'reply', chatId: CHAT, mode: 'text', text: '答', pid: DEAD_PID });
  // 用同一个 id（同 key 算出）但换成 proactive 来源重试：必须仍 skip
  const r = ob.beginSend({ logicalDeliveryId: idReply, source: 'proactive-baseline', chatId: CHAT, mode: 'text', text: '答' });
  T('R19 reply 的 begin 记录阻止 proactive 重发（beginSource 分支承重）',
    r.decision === 'skip' && r.reason === 'uncertain_reply_no_resend', JSON.stringify(r));
}

/* ── R6：缺 logical_delivery_id → 明确拒绝（不许静默发） ──────────── */
{
  reset();
  const r = ob.beginSend({ source: 'reply', chatId: CHAT, mode: 'text', text: '无 id' });
  T('R6 缺 id → refuse（不静默发送）',
    r.ok === false && r.decision === 'refuse' && r.reason === 'missing_logical_delivery_id', JSON.stringify(r));
  T('R6b 缺 id 不落台账', ledgerRows() === 0, `rows=${ledgerRows()}`);
}

const nFail = results.filter((r) => !r.ok).length;
for (const r of results) console.log(`  ${r.ok ? '✅' : '❌'} ${r.id}${r.ok ? '' : `  ← ${r.detail}`}`);
console.log(`\n${nFail ? '❌' : '✅'} outbound/outbox ${results.length - nFail}/${results.length} 项通过`
            + `（临时目录 ${path.basename(TMP)}；**一条真消息都没发**）`);
process.exit(nFail ? 1 : 0);
