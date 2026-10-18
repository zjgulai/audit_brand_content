#!/usr/bin/env node
/**
 * inbox.mjs —— durable inbox（T0-06 / G-3）
 *
 * ── 它修的是哪件事
 *
 * 飞书事件从长连接推进来，进程一死，事件就丢了，事后再连也补不回来
 * （`AGENTS.md` §2.7 对重启窗口的那条描述，对崩溃同样成立）。
 * 所以收到的每一条事件必须**先落盘、再处理**；处理完才移动游标。
 *
 * ── 三个设计决定，以及为什么
 *
 * ① **append + fsync，不是 writeFileSync。**
 *    进程被 SIGKILL 时，内核缓冲里没落盘的行会一起消失；`fsync` 是「写进介质」与
 *    「写进页缓存」的分界线。代价是每条事件一次系统调用 —— 事件率是每分钟几条，无所谓。
 *
 * ② **按 `event_id` 去重，不是按时间窗。**
 *    飞书会重投（断线重连、超时重试）。时间窗会漏（重投间隔不确定），
 *    内容哈希会把「同一文本的两条不同消息」误合并 —— `event_id` 是唯一稳的键。
 *
 * ③ **游标只在处理完成后前进，且原子写（tmp → fsync → rename）。**
 *    处理到一半被杀 → 游标没动 → 重启后同一条会**再处理一次**（at-least-once）。
 *    这是刻意选的：跳过一条不可逆，重放一条可以用下游幂等（outbox 的
 *    `logical_delivery_id`，T0-05）挡住重复回答。
 *
 * ── 它与 outbox 的分工
 *
 * inbox 保证「事件不丢」；outbox 保证「同一条事件不会回答两次」。
 * 两者合起来才是 exactly-once 的**效果**，单靠任何一个都做不到。
 *
 * ── 已知边界（照实写，不假装是 exactly-once 存储）
 *
 * **去重是「读—判—写」三步，没有跨进程锁。** 单写者（daemon）下成立；
 * 若将来有**两个进程同时 append 同一个 `event_id`**，两边都可能读到「不存在」
 * 并各写一行 —— 那时靠消费侧按 `event_id` 去重仍然只处理一次（游标只进不退），
 * 但日志里会有两条同 id 记录。要根除得加 `.lock` 或 O_EXCL 声明文件，
 * 那是另一张 ticket；本轮不假装已经解决。
 *
 * **游标是 at-least-once。** 处理完成后、写游标前崩溃 → 重启会重放同一条。
 * 这是刻意的选择（跳过不可逆，重放可用下游幂等挡住）。
 *
 * 判据见 `tools/agent/inbox.test.mjs`（含 kill 重启的进程级对照）。
 */
import fs from 'node:fs';
import path from 'node:path';
import { LOG_DIR } from './config.mjs';

/** 事件日志路径（可被环境变量指走 —— 自证必须落在临时目录，§2.4.4）。 */
export function inboxPath() {
  return process.env.SHOUHENG_INBOX_LEDGER
    ? path.resolve(process.env.SHOUHENG_INBOX_LEDGER)
    : path.join(LOG_DIR, 'events-inbox.jsonl');
}

/** 游标路径。默认与事件日志同目录、同名 + `.cursor`。 */
export function cursorPath() {
  return process.env.SHOUHENG_INBOX_CURSOR
    ? path.resolve(process.env.SHOUHENG_INBOX_CURSOR)
    : `${inboxPath()}.cursor`;
}

/** 原子写 + fsync。先写 tmp，再 rename —— rename 在同一文件系统内是原子的。 */
function writeAtomic(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp.${process.pid}`;
  const fd = fs.openSync(tmp, 'w');
  try {
    const n = fs.writeSync(fd, text);
    // ★ 短写会让 rename 后的游标是截断的 JSON —— 必须当场报错，不许当成功。
    if (n !== Buffer.byteLength(text)) throw new Error(`short_write ${n}/${Buffer.byteLength(text)}`);
    fs.fsyncSync(fd);
  } catch (e) {
    // 短写失败时不要留下半截 tmp 文件。
    try { fs.unlinkSync(tmp); } catch { /* 尽力 */ }
    throw e;
  } finally {
    fs.closeSync(fd);
  }
  fs.renameSync(tmp, file);
  // 目录项也要落盘，否则 rename 本身可能留在页缓存里。失败不致命（有些平台不支持目录 fsync）。
  try {
    const dfd = fs.openSync(path.dirname(file), 'r');
    try { fs.fsyncSync(dfd); } finally { fs.closeSync(dfd); }
  } catch { /* best-effort */ }
}

/** 追加一行并 fsync。**短写必须报错**（半截行会被读成 badLines）。 */
function appendLine(file, line) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const text = line + '\n';
  const fd = fs.openSync(file, 'a');
  const before = (() => { try { return fs.fstatSync(fd).size; } catch { return null; } })();
  try {
    const n = fs.writeSync(fd, text);
    if (n !== Buffer.byteLength(text)) {
      // ★ 短写会把半截行留在文件尾，之后每次读都 badLines → 永久停摆。
      //   回滚到追加前的大小，让这次失败不污染日志。
      try { if (before != null) fs.ftruncateSync(fd, before); } catch { /* 尽力回滚 */ }
      throw new Error(`short_write ${n}/${Buffer.byteLength(text)}`);
    }
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

/** 同步睡（仅用于锁重试；Node 没有 sleepSync）。 */
function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}

/**
 * 跨进程建议锁：`O_EXCL` 建锁文件，做完删除。
 * 锁过期（>30s）视为陈旧锁并清理 —— 进程被 SIGKILL 时锁文件会留下。
 */
function withLock(lockPath, fn) {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  for (let i = 0; i < 200; i++) {
    try {
      const fd = fs.openSync(lockPath, 'wx');
      const myIno = (() => { try { return fs.fstatSync(fd).ino; } catch { return null; } })();
      try {
        // 锁里写 pid：崩溃留下的锁可以**立即**判死并清理，不必让新进程白等 30 秒。
        try { fs.writeSync(fd, String(process.pid)); } catch { /* 尽力而为 */ }
        return fn();
      }
      finally {
        fs.closeSync(fd);
        // ★ 只删自己的锁（inode 比对），理由同 outbound.mjs 的 withOutboxLock。
        try {
          const cur = fs.statSync(lockPath);
          if (myIno == null || cur.ino === myIno) fs.unlinkSync(lockPath);
        } catch { /* 已删 */ }
      }
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let pid = null;
      try { pid = Number(fs.readFileSync(lockPath, 'utf8').trim()); } catch { /* 读不到 */ }
      if (Number.isInteger(pid) && pid > 0) {
        let alive = true;
        try { process.kill(pid, 0); } catch (err) { alive = err.code === 'EPERM'; }
        if (!alive) { try { fs.unlinkSync(lockPath); } catch { /* 竞态 */ } continue; }
        sleepSync(5);
        continue;   // pid 活着：只等，不按 mtime 抢
      }
      try {
        const st = fs.statSync(lockPath);
        if (Date.now() - st.mtimeMs > 30_000) { fs.unlinkSync(lockPath); continue; }
      } catch { /* 锁刚被删，重试 */ }
      sleepSync(5);
    }
  }
  throw Object.assign(new Error('lock_timeout'), { code: 'ELOCKED' });
}

/**
 * 读全部事件。
 * `missing` / `badLines` / `error` **分开返回** ——「一条都没有」与「我读不出来」
 * 必须长得不一样（§2.4.1 最后那句）。
 */
export function readEvents({ afterSeq = 0, limit = Infinity } = {}) {
  const f = inboxPath();
  let text;
  let ino = null;
  try {
    text = fs.readFileSync(f, 'utf8');
    try { ino = fs.statSync(f).ino; } catch { ino = null; }
  } catch (e) {
    if (e.code === 'ENOENT') return { events: [], badLines: 0, duplicates: [], lastSeq: 0, ino: null, missing: true, error: null, seqGap: 0 };
    return { events: [], badLines: 0, duplicates: [], lastSeq: 0, ino: null, missing: false, error: `${e.code ?? e.message}`, seqGap: 0 };
  }
  const events = [];
  let badLines = 0;
  const seenSeq = new Set();
  const seenId = new Set();
  const duplicates = [];
  let lastSeq = 0;
  for (const line of text.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    try {
      const d = JSON.parse(s);
      if (!d || typeof d !== 'object' || typeof d.event_id !== 'string' || !Number.isInteger(d.seq)) {
        throw new Error('bad shape');
      }
      lastSeq = Math.max(lastSeq, d.seq);
      // ★ 重复 seq / 重复 event_id 是**日志损坏**的信号，不是「两条不同事件」。
      //   静默跳过其中一条会让它永久不被处理；所以只记录，由 processNext 判未测。
      if (seenSeq.has(d.seq) || seenId.has(d.event_id)) duplicates.push({ seq: d.seq, event_id: d.event_id });
      seenSeq.add(d.seq);
      seenId.add(d.event_id);
      if (d.seq > afterSeq) events.push(d);
    } catch { badLines++; }
  }
  events.sort((a, b) => a.seq - b.seq);
  // ★ 缺号数：只在日志干净（无坏行/重复）时才有意义；否则是损坏，不是缺号。
  const seqGap = (badLines === 0 && duplicates.length === 0 && lastSeq > 0)
    ? lastSeq - seenSeq.size : 0;
  return { events: limit === Infinity ? events : events.slice(0, limit),
           badLines, duplicates, lastSeq, ino, missing: false, error: null, seqGap };
}

/**
 * 收一条事件。**同 `event_id` 再投 → duplicate=true，不增行。**
 *
 * 读不出日志时**拒绝写入**（返回 `ok:false`）：去重靠扫描既有事件，
 * 扫不了就没法保证不重复 —— 宁可报错，也不静默写第二条。
 */
export function appendEvent({ eventId, type = 'event', payload = null, at = null } = {}) {
  if (!eventId) return { ok: false, error: 'missing_event_id' };
  // ★ 必须显式要求 string：写入 number/Symbol 会让 reader 判成 badLine，
  //   于是一次调用就能把 inbox 变成「以后所有 append 都被拒绝」的状态（复验实测过）。
  if (typeof eventId !== 'string') return { ok: false, error: 'bad_event_id:not_string' };
  try {
    // ★ 「读—判—写」必须在一把跨进程锁里：否则两个进程可以同时判「不存在」并各写一行，
    //   而且会拿到**同一个 seq**，消费端从此永久跳过其中一条。
    return withLock(`${inboxPath()}.lock`, () => {
      const r = readEvents();
      if (r.error) return { ok: false, error: `inbox 读不出（${r.error}）—— 无法安全去重，拒绝写入` };
      if (r.badLines > 0) return { ok: false, error: `inbox 有 ${r.badLines} 行坏行 —— 拒绝在损坏日志上追加` };
      if (r.duplicates.length > 0) return { ok: false, error: 'inbox 日志有重复 seq/event_id —— 拒绝追加，需先修复' };

      const dup = r.events.find((e) => e.event_id === eventId);
      if (dup) return { ok: true, duplicate: true, seq: dup.seq };

      const seq = (r.lastSeq ?? 0) + 1;
      const rec = { seq, at: at ?? new Date().toISOString(), event_id: eventId, type, payload };
      appendLine(inboxPath(), JSON.stringify(rec));
      return { ok: true, duplicate: false, seq };
    });
  } catch (e) {
    return { ok: false, error: `${e.code ?? e.message}` };
  }
}

/**
 * 读游标。**读不出/损坏 → 回 0**（重放，不跳过）。
 * 一个损坏的游标被当成「已经处理到很后面」，就是静默丢事件。
 */
export function loadCursor() {
  const f = cursorPath();
  let text;
  try {
    text = fs.readFileSync(f, 'utf8');
  } catch (e) {
    // ★ 只有 ENOENT 才是「没有游标」；EACCES/EISDIR/EIO 是**读故障**，必须报未测，
    //   否则会被当成「从 0 开始」——全量重放，且读数看起来一切正常。
    if (e.code === 'ENOENT') return { seq: 0, event_id: null, missing: true };
    return { seq: 0, event_id: null, missing: false, error: `${e.code ?? e.message}` };
  }
  try {
    const d = JSON.parse(text);
    if (!d || !Number.isInteger(d.seq) || d.seq < 0) throw new Error('bad');
    return { seq: d.seq, event_id: d.event_id ?? null, log_ino: d.log_ino ?? null, missing: false };
  } catch {
    return { seq: 0, event_id: null, corrupt: true };
  }
}

/** 原子写游标。 */
export function saveCursor({ seq, eventId = null, at = null, logIno = null } = {}) {
  if (!Number.isInteger(seq) || seq < 0) return { ok: false, error: 'bad_seq' };
  let ino = logIno;
  if (ino == null) {
    try { ino = fs.statSync(inboxPath()).ino; } catch { ino = null; }
  }
  try {
    writeAtomic(cursorPath(),
      JSON.stringify({ seq, event_id: eventId, at: at ?? new Date().toISOString(), log_ino: ino }) + '\n');
    return { ok: true, seq };
  } catch (e) {
    // ★ 写失败必须返回结构化失败，不许抛 —— 否则 processNext 的「未测」契约形同虚设。
    return { ok: false, seq, error: `${e.code ?? e.message}` };
  }
}

/**
 * 取下一条未处理事件，交给 `handler`；**handler 成功返回后才前进游标**。
 *
 * - handler 抛错 → 游标不动，返回 `{ok:false, processed:false}`（下次重试同一事件）；
 * - 没有事件 → `{ok:true, processed:false, reason:'empty'}`；
 * - 事件日志读不出 → `{ok:false, untested}` —— 未测，不是「没有事件」。
 */
async function _processNext(handler, { afterSeq = null, timeoutMs = 120_000 } = {}) {
  const cur = loadCursor();
  if (cur.error) {
    return { ok: false, processed: false, untested: `游标读不出（${cur.error}）—— 未测`, cursor: 0 };
  }
  const from = afterSeq ?? cur.seq;
  // ★ 读全量：除了取「下一条」，还要核对**游标那一条**是否还在、event_id 是否一致，
  //   以及 seq 是否连续。只读 afterSeq 之后的会把「中间缺号」漏成健康。
  const r = readEvents({ afterSeq: 0 });
  if (r.error) {
    return { ok: false, processed: false, untested: `inbox 读不出（${r.error}）—— 未测`, cursor: from };
  }
  // ★ 坏行 / 重复 seq / 重复 event_id：**不许越过**继续处理后面的 seq。
  //   越过就等于把坏行里的事件永久丢掉，而读数还是「健康」。
  if (r.badLines > 0) {
    return { ok: false, processed: false, untested: `inbox 有 ${r.badLines} 行坏行 —— 未测`,
             cursor: from, badLines: r.badLines };
  }
  if (r.duplicates.length > 0) {
    return { ok: false, processed: false, untested: 'inbox 有重复 seq/event_id —— 未测',
             cursor: from, duplicates: r.duplicates };
  }
  // ★ 日志身份变了（被轮转/重建）：游标记的是旧日志的 inode。
  //   只比 lastSeq 会漏掉「新日志已经长过旧游标」的情形（复验实测过）。
  if (cur.seq > 0) {
    if (r.missing) {
      return { ok: false, processed: false, untested: 'inbox 日志不见了但游标 > 0 —— 未测',
               cursor: from, cursorAhead: true };
    }
    if (cur.log_ino != null && r.ino != null && cur.log_ino !== r.ino) {
      return { ok: false, processed: false,
               untested: `inbox 日志已更换（ino ${cur.log_ino} → ${r.ino}）—— 未测`,
               cursor: from, cursorAhead: true };
    }
  }
  // ★ 日志被截断/轮转：游标前于所有新 seq → 新事件会被永久跳过。
  if (r.lastSeq < from && (r.lastSeq > 0 || r.missing === false)) {
    return { ok: false, processed: false,
             untested: `游标(${from}) 领先于日志末序号(${r.lastSeq}) —— 日志可能被重置，未测`,
             cursor: from, cursorAhead: true };
  }

  // ★ 游标那一条必须仍在，且 event_id 一致（游标里记了 id，却一直没人读它）。
  if (cur.seq > 0 && cur.event_id) {
    const at = r.events.find((e) => e.seq === cur.seq);
    if (at && at.event_id !== cur.event_id) {
      return { ok: false, processed: false,
               untested: `游标 seq=${cur.seq} 的 event_id 对不上（游标 ${cur.event_id} / 日志 ${at.event_id}）—— 未测`,
               cursor: from, cursorAhead: true };
    }
  }

  const ev = r.events.find((e) => e.seq > from);
  if (!ev) return { ok: true, processed: false, reason: 'empty', cursor: from, badLines: 0 };
  // ★ seq 必须连续：中间缺号意味着有事件被删/漏写，不许当健康继续。
  if (ev.seq !== from + 1) {
    return { ok: false, processed: false,
             untested: `inbox seq 不连续（游标 ${from} → 下一条 ${ev.seq}）—— 未测`,
             cursor: from, seqGap: true };
  }

  // ★ handler 必须有 deadline：一个永不 settle 的 handler 会永久占住 promise 链，
  //   让整个 inbox 停摆（复验实测过）。超时后游标不动，事件会重放（下游 outbox 幂等）。
  let timer;
  try {
    const timeout = new Promise((_, rej) => {
      // ★ 不要 unref：否则事件循环里没有别的 handle 时 Node 会在超时前退出，
      //   留下一个永不 settle 的 top-level await（实测过）。
      timer = setTimeout(() => rej(Object.assign(new Error('handler_timeout'), { code: 'ETIMEDOUT' })), timeoutMs);
    });
    await Promise.race([handler(ev), timeout]);
  } catch (e) {
    return { ok: false, processed: false, event: ev, cursor: from,
             timedOut: e?.code === 'ETIMEDOUT',
             error: `${e?.code ?? e?.message ?? e}` };
  } finally {
    if (timer) clearTimeout(timer);
  }

  const saved = saveCursor({ seq: ev.seq, eventId: ev.event_id });
  if (!saved.ok) {
    // 处理已完成但游标没落盘 → 下次会重放。必须如实报未测，不许报 processed:true。
    return { ok: false, processed: true, event: ev, cursor: from,
             untested: `游标写不进去（${saved.error}）—— 下次会重放` };
  }
  return { ok: true, processed: true, event: ev, cursor: ev.seq, badLines: 0 };
}

// ★ **进程内单飞**：两个并发 processNext 会读到同一个游标与同一个 events[0]，
//   把同一条事件处理两遍（实测过）。用一条 promise 链串行化；跨进程仍靠锁/单消费者约定。
let _chain = Promise.resolve();

export function processNext(handler, opts = {}) {
  const run = _chain.then(() => _processNext(handler, opts));
  _chain = run.then(() => undefined, () => undefined);
  return run;
}

/** 连续处理直到没有新事件（或达到 `max`）。 */
export async function processAll(handler, { max = Infinity } = {}) {
  const done = [];
  for (let i = 0; i < max; i++) {
    const r = await processNext(handler);
    if (!r.processed) return { ok: r.ok, processed: done.length, events: done, last: r };
    done.push(r.event);
  }
  return { ok: true, processed: done.length, events: done, last: null, capped: true };
}

/** 只读读数：供 CLI / 自证打印，不推进游标。 */
export function stats() {
  const r = readEvents();
  const cur = loadCursor();
  const lastSeq = r.lastSeq ?? 0;
  return {
    events: r.events.length,
    lastSeq,
    cursor: cur.seq,
    backlog: Math.max(0, lastSeq - cur.seq),
    // ★ 以下四项分开报：读故障、坏行、重复、游标领先，任何一项非零都**不是健康**。
    error: r.error ?? null,
    cursorError: cur.error ?? null,
    badLines: r.badLines,
    duplicates: r.duplicates.length,
    cursorAhead: cur.seq > lastSeq && (lastSeq > 0 || r.missing === false),
    // ★ 与 processNext 同口径：缺号 / 日志轮转 也是「未测」，不许在统计里读成健康。
    seqGap: r.seqGap ?? 0,
    rotated: Boolean(cur.log_ino != null && r.ino != null && cur.log_ino !== r.ino),
    missing: r.missing,
    cursorCorrupt: Boolean(cur.corrupt),
    path: inboxPath(),
  };
}
