/**
 * outbound.mjs —— 「守衡说出去的话」有没有落下来（台账 + 折进会话记忆）
 *
 * ── 它修的是哪两件事（2026-09-22 一次真实的外部误答之后）
 *
 * | 真空 | 原先的样子 | 现在 |
 * |---|---|---|
 * | **出站无留痕** | 我们发出去的消息**没有任何落账**：`send_once.mjs` 只往 stdout 打一个
 *   `message_id`。于是 T7① 那一问的「发出时刻」是**手记**的，那个号码也进不了
 *   `待收清单` 的指针体系（`kind:message` 查的是**入站**事件日志，实测 0 命中） | 每一条
 *   **真的发出去了**的消息追加一行到 `PMO/logs/ws_outbound.jsonl` |
 * | **出站不进会话记忆** | `memory.append` 只在 `agent.mjs` 的**回复循环**里调，
 *   主动推送（`send_once.mjs`、基线告警、待收提醒、崩溃自报）都不经过那里。
 *   **她回复时，守衡不记得自己问过什么** —— 14:39 那次误答就长在这上面 | 回话前把
 *   「我说过、但记忆里没有的」折进会话（`foldInto`） |
 *
 * ── 为什么不是「发送时直接写会话文件」
 *
 * 因为那会多出一个**跨进程写者**：`send_once.mjs` 是另一个进程，而 daemon 正在
 * `handleMessage` 里握着同一份会话（中间还夹着一次 16 秒的 LLM 调用）。
 * 两个进程各自 `读 → 改 → 写` 同一个 JSON，后写的把先写的**整段抹掉** ——
 * 与 `prd_baseline.mjs` 那次「两个检查共写一份状态文件」是同一个形状（§2.4.3）。
 *
 * 所以这里分成两半，各自**只有一个写者**：
 *   · **台账**（本文件 `recordSend`）：只增不改，谁发谁追加，天然可并发；
 *   · **会话文件**（`foldInto`）：**只有 daemon 写**。它在每次回话前读一遍台账，
 *     把还没进记忆的那几条补上。
 *
 * 代价是「补记」晚了一步 —— 但那一步恰好发生在**最需要它的那一刻**：
 * 对方刚开口、上下文正要拼出来的时候。
 *
 * ── 判据的落点
 *
 * `tools/verify_outbound.py`（A 判据 / B 接线 / C 反向对照 / D 拿真实台账做回归 /
 * E 结论行不许撒谎 / F 全仓不许绕过台账）。**别把那个检查器变绿读成「重启已经做了」**——
 * 代码在盘上不等于在跑，见 `PMO/守衡-误答登记-20260922.md` §7.2 那两条独立读数。
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { LOG_DIR } from './config.mjs';
import * as mem from './memory.mjs';

/* ─────────────────────────── 台账 ─────────────────────────── */

/**
 * 一条外发消息的「性质」。**封闭集合** —— 它决定要不要折进会话记忆，
 * 所以加新的来源时必须同时想清楚「这条该不该进守衡的记忆」。
 *
 * ★ `reply` 是唯一**不折**的一类：回复循环自己已经 `mem.append` 过了，
 *   再折一遍就是同一个回答在记忆里出现两遍。
 *   （曾经想用「正文去重」代替这个判断 —— 不行：走卡片时**存进记忆的是模型的原文、
 *     发出去的是卡片降级文本**，两者本来就不一样，正文匹配一定漏。）
 *   `failed` 也不折：发送失败的消息**没有出现在群里**，折进记忆等于让它
 *   「记得自己说过一句别人根本没看见的话」。
 */
export const SOURCES = Object.freeze([
  'reply',               // daemon 的回复循环（已进记忆，不折）
  'resend',              // ★ 2026-09-22 加：失败之后**补发**的那条（引用原消息，见 retry_queue.mjs）
  'proactive-baseline',  // 上游基线漂移告警
  'proactive-pending',   // 待收清单到期提醒
  'proactive-external',  // ★ 2026-09-22 加：外部标准库漂移告警（见 external_watch.mjs）
  'error-fallback',      // 出错兜底话术 / 内部出错自报
  'greeting',            // 被拉进群的自我介绍
  'manual',              // 人用 send_once.mjs 手发的（T7① 那一问、15:03 更正都是这一类）
  'manual-backfill',     // 补记：修复之前发出去的（从飞书回读，见 outbound_ledger.mjs）
]);

/**
 * ★ 折/不折是 `SOURCES` 的**显式分类**（2026-09-22 加）。
 *
 * 原先判的是 `e.source === 'reply'` 一个字面量 —— 于是「加一个来源」默认落进**会折**那一侧，
 * 而没人需要为此写一行代码。补发（`resend`）正好撞上这个默认值：它由内核重跑产生、
 * 内核自己已经 `mem.append` 过回答，再折一遍就是**同一个回答在记忆里出现两遍**。
 *
 * 现在两侧都是白名单，且 `foldPlan` 对「没分类的来源」**不折、并计数**
 * （`skipped.unclassified`）—— 漏一个不会静默折进去，也不会静默消失。
 */
export const FOLDING = Object.freeze(new Set([
  'proactive-baseline', 'proactive-pending', 'proactive-external',
  'error-fallback', 'greeting', 'manual', 'manual-backfill',
]));
/** 这些来源**不折**：说出去的话由其产生方自己写进记忆（回复循环 / 补发时的内核重跑）。 */
export const NON_FOLDING = Object.freeze(new Set(['reply', 'resend']));

/** 台账路径。**惰性求值** —— 自证必须能把它指到临时目录（§2.4.4：自证不许改真数据）。 */export function ledgerPath() {
  return process.env.SHOUHENG_OUTBOUND_LEDGER
    ? path.resolve(process.env.SHOUHENG_OUTBOUND_LEDGER)
    : path.join(LOG_DIR, 'ws_outbound.jsonl');
}

/**
 * 记一条外发。**不抛**：台账写不进去也必须把消息发出去（与 `dumpRaw` 同一条纪律）。
 *
 * @returns {{ok:boolean, at?:string, error?:string, source?:string}}
 */
export function recordSend({ chatId, chatType = null, messageIds = [], text = '', source, mode = null,
                             replyTo = null, ok = true, error = null, extra = null, at = null }) {
  const now = at ?? new Date().toISOString();
  const known = SOURCES.includes(source);
  const rec = {
    at: now,
    chat_id: chatId ?? null,
    chat_type: chatType ?? null,
    message_ids: (Array.isArray(messageIds) ? messageIds : [messageIds]).filter(Boolean),
    // ★ 不认识的来源**照样记**（丢一条留痕比记一个脏值严重得多），但打上 `unknown:`
    //   前缀 —— 于是「有人加了新的发送路径却忘了在这里登记」会在**真实台账里看得见**，
    //   而不是静默通过。verify_outbound.py 的 H 段会拿真台账断言这一条。
    source: known ? source : `unknown:${source ?? '(未给)'}`,
    mode,
    reply_to: replyTo,
    ok: ok !== false,
    error: error ?? null,
    chars: String(text ?? '').length,
    text: String(text ?? ''),
    ...(extra && typeof extra === 'object' ? { extra } : {}),
  };
  try {
    const f = ledgerPath();
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.appendFileSync(f, JSON.stringify(rec) + '\n');
    return { ok: true, at: now, source: rec.source };
  } catch (e) {
    return { ok: false, at: now, source: rec.source, error: `${e.code ?? e.message}` };
  }
}

/**
 * 读台账。回**四个读数分开**的对象，`missing` / `badLines` / `truncated` 各自独立 ——
 * 「一条都没有」和「我读不出来」必须长得不一样（§2.4.1 最后那句）。
 *
 * ★ **不按会话过滤**（第一版有个 `chatId` 选项，2026-09-22 删掉了）：过滤交给调用方，
 *   否则 `foldPlan` 里那个「不是这个群的」跳过计数**恒为 0** —— 被过滤掉的东西
 *   连计数器都到不了。读全量、谁要谁筛，跳过的理由才数得出来。
 *
 * @param {{maxBytes?:number}} opt
 * @returns {{entries:Array, badLines:number, bytes:number, truncated:boolean,
 *            missing:boolean, error?:string}}
 */
export function readEntries({ maxBytes = 4 * 1024 * 1024 } = {}) {
  const f = ledgerPath();
  let buf;
  let truncated = false;
  try {
    const st = fs.statSync(f);
    if (st.size === 0) return { entries: [], badLines: 0, bytes: 0, truncated: false, missing: false };
    const start = st.size > maxBytes ? st.size - maxBytes : 0;
    truncated = start > 0;
    const fd = fs.openSync(f, 'r');
    try {
      buf = Buffer.alloc(st.size - start);
      fs.readSync(fd, buf, 0, buf.length, start);
    } finally { fs.closeSync(fd); }
  } catch (e) {
    if (e.code === 'ENOENT') return { entries: [], badLines: 0, bytes: 0, truncated: false, missing: true };
    return { entries: [], badLines: 0, bytes: 0, truncated: false, missing: false,
             error: `${e.code ?? e.message}` };
  }

  let text = buf.toString('utf8');
  // 从中间截断时，头一行多半是半截的 —— 丢掉它，并**计入 badLines**，不许静默吞掉。
  if (truncated) text = text.slice(text.indexOf('\n') + 1);

  const entries = [];
  let badLines = 0;
  for (const line of text.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    try {
      const d = JSON.parse(s);
      if (!d || typeof d !== 'object') throw new Error('not object');
      entries.push(d);
    } catch { badLines++; }
  }
  return { entries, badLines, bytes: buf.length, truncated, missing: false };
}

/* ─────────────────────── outbox：投递状态机（T0-05 / G-2） ─────────────────────── */

/**
 * outbox 状态文件路径。**与消息台账分开**：
 *   · 消息台账（`ws_outbound.jsonl`）回答「我说过什么」——只增不改，折叠进记忆读它；
 *   · outbox（`ws_outbox.jsonl`）回答「这次投递走到哪一步」——begin/confirm/unknown 状态机。
 * 混在一起会让 `readEntries` 把 begin 行当成一条消息折进记忆。
 */
export function outboxPath() {
  return process.env.SHOUHENG_OUTBOX_LEDGER
    ? path.resolve(process.env.SHOUHENG_OUTBOX_LEDGER)
    : path.join(LOG_DIR, 'ws_outbox.jsonl');
}

/** pending 超过这个时长还没 confirm → 视为未知（默认 5 分钟，可覆盖）。 */
export function outboxTtlMs() {
  const n = Number(process.env.SHOUHENG_OUTBOX_TTL_MS);
  return Number.isFinite(n) && n > 0 ? n : 5 * 60 * 1000;
}

/**
 * 稳定投递 id。**卡片与降级文本必须共用同一个 id** ——
 * 它们是一次逻辑投递的两个变体，不是两次投递。
 * `key` 由调用方给（原消息 id / event_id / 告警键），**不要用正文**：
 * 卡片存进记忆的是模型原文、发出去的是降级文本，两者本来就不一样。
 */
export function logicalDeliveryId({ source, chatId = '', key } = {}) {
  if (!key) return null;
  // ★ **不要把 `source` 算进哈希。** 否则 reply 崩溃后用 `source='resend'` 重试会算出
  //   另一个 id，beginSend 判 absent → 再发一次（实测过）。同一条原消息 / 同一个
  //   event_id 就是同一次逻辑投递，来源只是它的标签，不是它的身份。
  //   `source` 参数保留，仅为调用方签名兼容（不参与计算）。
  void source;
  return crypto.createHash('sha256')
    .update(`${chatId}\n${key}`)
    .digest('hex').slice(0, 24);
}

/** 把底层 I/O 错误分成可读的拒绝原因，别一律报成 outbox_locked。 */
function lockFailReason(e) {
  const code = e?.code;
  if (code === 'ELOCKED') return 'outbox_locked';
  if (code === 'EACCES' || code === 'EPERM' || code === 'EROFS' || code === 'ENOSPC' || code === 'EDQUOT') {
    return 'outbox_unwritable';
  }
  return 'outbox_error';
}

/** 同步睡（锁重试用；Node 没有 sleepSync）。 */
function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}

/**
 * outbox 的跨进程建议锁：`O_EXCL` 建锁文件，做完删除；>30s 的锁视为陈旧。
 * 没有它，两个进程会同时读到 absent 并各发一次（T0-05 的重复发送防线在并发下失效）。
 */
function withOutboxLock(fn) {
  const lock = `${outboxPath()}.lock`;
  fs.mkdirSync(path.dirname(lock), { recursive: true });
  for (let i = 0; i < 200; i++) {
    try {
      const fd = fs.openSync(lock, 'wx');
      const myIno = (() => { try { return fs.fstatSync(fd).ino; } catch { return null; } })();
      try {
        // 锁里写 pid：崩溃留下的锁可以**立即**判死并清理，不必等 30 秒。
        try { fs.writeSync(fd, String(process.pid)); } catch { /* 尽力而为 */ }
        return fn();
      } finally {
        fs.closeSync(fd);
        // ★ 只删**自己的**锁：若锁已被别人当陈旧锁抢走，这里再删就会删掉新持有者的锁，
        //   出现两个进程同时持锁（复验实测过）。用 inode 比对。
        try {
          const cur = fs.statSync(lock);
          if (myIno == null || cur.ino === myIno) fs.unlinkSync(lock);
        } catch { /* 已删 */ }
      }
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      // pid 已死 → 陈旧锁，立即清掉重试。**pid 活着就绝不按 mtime 抢**。
      let pid = null;
      try { pid = Number(fs.readFileSync(lock, 'utf8').trim()); } catch { /* 读不到 */ }
      if (Number.isInteger(pid) && pid > 0) {
        let alive = true;
        try { process.kill(pid, 0); } catch (err) { alive = err.code === 'EPERM'; }
        if (!alive) { try { fs.unlinkSync(lock); } catch { /* 竞态 */ } continue; }
        // 活着：只等，不抢（即使 mtime 很旧 —— 可能只是慢 fsync/被 SIGSTOP）。
        sleepSync(5);
        continue;
      }
      // pid 读不到（空锁/旧格式）：才退回 mtime 判陈旧。
      try {
        const st = fs.statSync(lock);
        if (Date.now() - st.mtimeMs > 30_000) { fs.unlinkSync(lock); continue; }
      } catch { /* 锁刚被删，重试 */ }
      sleepSync(5);
    }
  }
  throw Object.assign(new Error('lock_timeout'), { code: 'ELOCKED' });
}

/** 追加一条 outbox 记录。**fsync** —— 状态机必须在崩溃后仍然可读。 */
function appendOutbox(rec) {
  const f = outboxPath();
  fs.mkdirSync(path.dirname(f), { recursive: true });
  const line = JSON.stringify(rec) + '\n';
  const fd = fs.openSync(f, 'a');
  const before = (() => { try { return fs.fstatSync(fd).size; } catch { return null; } })();
  try {
    const n = fs.writeSync(fd, line);
    // ★ 短写必须报错：半截 JSON 行会被读成 badLines，从而把一个可恢复的投递变成「未测」。
    if (n !== Buffer.byteLength(line)) {
      // 并回滚到追加前的大小 —— 否则一次瞬时 I/O 错误会留下永久坏行。
      try { if (before != null) fs.ftruncateSync(fd, before); } catch { /* 尽力回滚 */ }
      throw new Error(`short_write ${n}/${Buffer.byteLength(line)}`);
    }
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

/** 读 outbox。读不出必须与「一条都没有」分开（§2.4.1 最后那句）。 */
export function readOutbox() {
  const f = outboxPath();
  let text;
  try {
    text = fs.readFileSync(f, 'utf8');
  } catch (e) {
    if (e.code === 'ENOENT') return { records: [], badLines: 0, missing: true };
    return { records: [], badLines: 0, missing: false, error: `${e.code ?? e.message}` };
  }
  const records = [];
  let badLines = 0;
  for (const line of text.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    try {
      const d = JSON.parse(s);
      if (!d || typeof d !== 'object' || typeof d.type !== 'string') throw new Error('bad');
      records.push(d);
    } catch { badLines++; }
  }
  return { records, badLines, missing: false };
}

/** pid 还活着吗？`EPERM` = 存在但无权限 → 也算活着。未知（无 pid）返回 null。 */
function pidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return null;
  try { process.kill(pid, 0); return true; }
  catch (e) { return e.code === 'EPERM'; }
}

/**
 * 一次逻辑投递现在处于哪一态。**纯函数**（可选 `records` 注入，离线可测）。
 *
 * 状态优先级：confirmed > unknown（显式或推断）> pending > absent。
 * 「崩溃」的判据是 **begin 记录里的 pid 已死**；「超时」是 age > ttl。
 * 两者都落 `unknown` —— 含义相同：**我们不知道它发出去没有**。
 */
export function outboxState(logicalDeliveryId, opt = {}) {
  const id = logicalDeliveryId;
  const r = opt.records ? { records: opt.records, badLines: 0 } : readOutbox();
  // ★ 读不出 / 有坏行 ≠ 没有记录：后者会让 beginSend 判 absent 并再发一次。
  //   未测必须单独成一态（§2.4.1 最后那句）。
  if (r.error || (r.badLines ?? 0) > 0) {
    return { state: 'untested', begin: null, confirm: null, unknown: null,
             error: r.error ?? `bad_lines=${r.badLines}` };
  }
  const mine = (r.records ?? []).filter((x) => x.logical_delivery_id === id);

  // ★ **按记录顺序判定，不是按类型优先级。** outbox 是 append-only 日志：
  //   · confirm 永远最高（它是对「已发出」的确定声明）；
  //   · 否则以**最后一条** begin/unknown 为准 —— 后写的 begin 覆盖更早的 unknown。
  //     固定优先级（unknown > begin）会让崩溃恢复后的重发永远被旧 unknown 拖住：
  //     第二次 beginSend 仍判 unknown → 再发 → 群里两遍。
  let confirm = null;
  let lastBegin = null, lastBeginIdx = -1;
  let lastUnknown = null, lastUnknownIdx = -1;
  for (let i = 0; i < mine.length; i++) {
    const x = mine[i];
    if (x.type === 'confirm') confirm = x;
    else if (x.type === 'begin') { lastBegin = x; lastBeginIdx = i; }
    else if (x.type === 'unknown') { lastUnknown = x; lastUnknownIdx = i; }
  }
  if (confirm) return { state: 'confirmed', begin: lastBegin, confirm, unknown: lastUnknown };
  if (lastUnknown && lastUnknownIdx > lastBeginIdx) {
    return { state: 'unknown', begin: lastBegin, confirm: null, unknown: lastUnknown,
             reason: lastUnknown.reason ?? 'explicit' };
  }
  if (!lastBegin) return { state: 'absent', begin: null, confirm: null, unknown: lastUnknown };

  const begin = lastBegin;
  const now = opt.now ?? Date.now();
  const ttlMs = opt.ttlMs ?? outboxTtlMs();
  const parsed = Date.parse(begin.at);
  if (!Number.isFinite(parsed)) {
    // at 坏了：不能当 pending（NaN 比较恒 false → 永远在途），也不能当 absent（会重发）。
    return { state: 'untested', begin, confirm: null, unknown: lastUnknown, error: 'bad_begin_at' };
  }
  const ageMs = now - parsed;
  if (ageMs < -60 * 1000) {
    // 明显来自未来（时钟回拨/脏数据）：判未测，不静默推迟超时窗口。
    return { state: 'untested', begin, confirm: null, unknown: lastUnknown, error: 'future_begin_at' };
  }
  const alive = pidAlive(begin.pid);
  if (alive === false) {
    return { state: 'unknown', begin, confirm: null, unknown: null, reason: 'crash', ageMs };
  }
  if (Number.isFinite(ttlMs) && ageMs > ttlMs) {
    return { state: 'unknown', begin, confirm: null, unknown: null, reason: 'timeout', ageMs };
  }
  return { state: 'pending', begin, confirm: null, unknown: null, ageMs };
}

/**
 * 崩溃后**不确定**时，哪些来源允许重发。
 * `reply` 绝不重发（重复回答比漏答更伤）；`resend` 是补发队列的来源，契约是 at-most-once
 * （Playbook §1ter.7：再重试就是三发）—— 所以它也绝不重发。
 */
const NO_RESEND_ON_UNCERTAIN = Object.freeze(new Set(['reply', 'resend']));

/**
 * 声明「我要发这件事」。返回**决策**，调用方只在 `send` 时真的发。
 *
 * ★ **每个逻辑投递只调一次 beginSend。** 卡片失败后改发降级文本，是**同一次投递的
 *   变体切换** —— 调用方自己决定发哪个，发完只调一次 `confirmSend`。
 *   若为降级文本再调一次 `beginSend`，同一进程内会被判成 `in_flight` 而**吞掉降级**。
 *   这不是「少发一条」的保守，而是**丢消息**；所以这条纪律必须写在 API 旁边。
 *
 * @returns {{ok:boolean, decision:'send'|'skip'|'refuse', reason:string, state:string, id?:string}}
 */
export function beginSend({ logicalDeliveryId: id, source, chatId = null, mode = null,
                            text = '', at = null, ttlMs = null, pid = null,
                            allowUntested = false } = {}) {
  if (!id) return { ok: false, decision: 'refuse', reason: 'missing_logical_delivery_id', state: 'absent' };

  // `at` 统一规范成 ISO；传 epoch 毫秒 / Date 都接受，解析不了就**拒绝**（不许写成 NaN 行）。
  let atIso = null;
  if (at != null) {
    const d = new Date(at);
    if (Number.isNaN(d.getTime())) {
      return { ok: false, decision: 'refuse', reason: 'bad_at', state: 'absent' };
    }
    atIso = d.toISOString();
  }
  const nowMs = atIso ? Date.parse(atIso) : Date.now();
  try {
    return withOutboxLock(() => {
      const st = outboxState(id, { now: nowMs, ttlMs: ttlMs ?? undefined });

      if (st.state === 'untested' && !allowUntested) {
        // 未测不许当成「从未发过」——否则会盲目重发。调用方要发必须显式 allowUntested。
        return { ok: false, decision: 'refuse', reason: 'outbox_untested', state: 'untested', error: st.error };
      }

      let decision = 'send';
      let reason = 'new';
      if (st.state === 'confirmed') { decision = 'skip'; reason = 'already_confirmed'; }
      else if (st.state === 'pending') { decision = 'skip'; reason = 'in_flight'; }
      else if (st.state === 'unknown') {
        // ★ 按**两侧来源**判：本次 source 与 begin 行记录的 source，任一属于「不重发」就 skip。
        //   否则 reply 崩溃后可以借道 `resend` 重发（实测过）。
        const beginSource = st.begin?.source;
        const denies = NO_RESEND_ON_UNCERTAIN.has(source) ||
                       (beginSource != null && NO_RESEND_ON_UNCERTAIN.has(beginSource));
        if (denies) { decision = 'skip'; reason = 'uncertain_reply_no_resend'; }
        else { decision = 'send'; reason = 'uncertain_proactive_resend'; }
      }

      if (decision === 'send') {
        appendOutbox({
          at: atIso ?? new Date(nowMs).toISOString(),
          type: 'begin',
          logical_delivery_id: id,
          source: source ?? null,
          chat_id: chatId,
          mode,
          chars: String(text ?? '').length,
          pid: pid ?? process.pid,
        });
      }
      return { ok: true, decision, reason, state: st.state, id };
    });
  } catch (e) {
    // 锁超时：拒绝，不盲发（另一个进程正在判同一条投递）。
    return { ok: false, decision: 'refuse', reason: lockFailReason(e), error: `${e.code ?? e.message}` };
  }
}

/**
 * 确认这条投递真的发出去了。**幂等**：同一 id 重复 confirm 不会写第二行台账，
 * 也不会让消息台账多一条（卡片+降级两个变体共用 id，只能落一次）。
 */
export function confirmSend({ logicalDeliveryId: id, source, chatId = null, mode = null,
                              messageIds = [], text = '', at = null } = {}) {
  if (!id) return { ok: false, deduped: false, error: 'missing_logical_delivery_id' };
  let atIso = null;
  if (at != null) {
    const d = new Date(at);
    if (Number.isNaN(d.getTime())) return { ok: false, deduped: false, error: 'bad_at' };
    atIso = d.toISOString();
  }
  try {
    return withOutboxLock(() => {
      const st = outboxState(id);
      const now = atIso ?? new Date().toISOString();
      const ids = (Array.isArray(messageIds) ? messageIds : [messageIds]).filter(Boolean);
      const ledgerHas = () => (readEntries().entries ?? [])
        .some((e) => e?.extra?.logical_delivery_id === id);

      if (st.state === 'confirmed') {
        // ★ 已 confirmed 但消息台账缺这一行（上次 recordSend 失败）：补记一次，
        //   否则折进会话记忆时永远缺这条（复验实测过的「重试看起来成功」）。
        const rec = (ledgerHas() || !String(text ?? '').trim())
          ? { ok: true, skipped: 'already_recorded' }
          : recordSend({ chatId, text, source: source ?? 'unknown:confirmSend', mode,
                         messageIds: ids, at: now, extra: { logical_delivery_id: id } });
        return { ok: true, deduped: true, state: 'confirmed', record: rec };
      }

      // ★ outbox 未测时：只记一次消息台账（按 logical_delivery_id 去重），
      //   否则调用方每次重试都会多一行，foldPlan 会把同一条折进记忆两遍（实测过）。
      if (st.state === 'untested') {
        const rec = ledgerHas() ? { ok: true, skipped: 'already_recorded' }
          : recordSend({ chatId, text, source: source ?? 'unknown:confirmSend', mode,
                         messageIds: ids, at: now, extra: { logical_delivery_id: id } });
        return { ok: false, deduped: false, state: 'untested', error: st.error,
                 record: rec, warning: 'outbox 未测：消息台账最多记一次，但去重不可靠' };
      }

      // ★ 先确认**消息台账写成功**，再写 confirm 行。反过来会出现「outbox 已 confirmed、
      //   消息台账缺行」，而重试因 deduped 直接返回成功 —— 那条话永远进不了记忆。
      const rec = recordSend({ chatId, text, source: source ?? 'unknown:confirmSend', mode,
                               messageIds: ids, at: now, extra: { logical_delivery_id: id } });
      if (rec.ok === false) {
        return { ok: false, deduped: false, state: 'unconfirmed',
                 error: `ledger_write_failed:${rec.error ?? 'unknown'}`, record: rec };
      }
      appendOutbox({
        at: now, type: 'confirm', logical_delivery_id: id,
        source: source ?? null, chat_id: chatId, mode, message_ids: ids,
      });
      return { ok: true, deduped: false, state: 'confirmed', record: rec };
    });
  } catch (e) {
    return { ok: false, deduped: false, error: `${lockFailReason(e)}:${e.code ?? e.message}` };
  }
}

/**
 * 扫一遍所有投递，把「崩溃/超时」的 pending **显式落成 unknown**。
 *
 * `apply:false` 是 dry-run（不写盘）—— 供查看与自证使用（§2.4.4：查看不许改状态）。
 * 读不出时返回 `untested`，**不许当成「没有 pending」**。
 */
export function reconcilePending({ now = Date.now(), ttlMs = null, apply = true } = {}) {
  try {
    // ★ 整段「读快照 → 判定 → 追加 unknown」必须在锁内：否则期间落进的新 begin
    //   会被随后的 unknown 按记录顺序压过，proactive 会二次发送（复验实测过）。
    return withOutboxLock(() => {
      const r = readOutbox();
      if (r.error || (r.badLines ?? 0) > 0) {
        const why = r.error ?? `有 ${r.badLines} 行读不出来`;
        return { ok: false, untested: `outbox ${why} —— 「有没有未知投递」未测`,
                 pending: [], unknown: [], confirmed: [], applied: [], untestedIds: [] };
      }
      const ids = [...new Set(r.records.map((x) => x.logical_delivery_id).filter(Boolean))];
      const pending = [], unknown = [], confirmed = [], applied = [], untestedIds = [];
      for (const id of ids) {
        const st = outboxState(id, { now, ttlMs: ttlMs ?? undefined, records: r.records });
        if (st.state === 'confirmed') confirmed.push(id);
        else if (st.state === 'unknown') {
          unknown.push(id);
          // 只把**推断出来**的 unknown 落盘；已有显式 unknown 行就不重复写。
          if (apply && !st.unknown) {
            try {
              appendOutbox({ at: new Date(now).toISOString(), type: 'unknown',
                             logical_delivery_id: id, reason: st.reason ?? 'timeout' });
              applied.push(id);
            } catch (e) {
              // 写失败 → 未测，不许报成「已处理」。
              untestedIds.push({ id, error: `unknown_append_failed:${e.code ?? e.message}` });
            }
          }
        } else if (st.state === 'pending') pending.push(id);
        else if (st.state === 'untested') untestedIds.push({ id, error: st.error });
      }
      // ★ 有 untested 时 ok=false：未测必须与「没有未知投递」长得不一样。
      const ok = untestedIds.length === 0;
      return { ok, pending, unknown, confirmed, applied, untestedIds,
               untested: ok ? null : `有 ${untestedIds.length} 条投递状态未测`,
               missing: r.missing, badLines: r.badLines };
    });
  } catch (e) {
    return { ok: false, untested: `outbox 锁不可用（${e.code ?? e.message}）—— 未测`,
             pending: [], unknown: [], confirmed: [], applied: [], untestedIds: [] };
  }
}

/* ─────────────────────── 折进会话记忆（判据，纯函数部分） ─────────────────────── */

/** 去空白再比 —— 与 `thread.mjs` 的 `squash()`、`verify_pending.py` 的 `_squash()` 同一口径。 */
function squash(s) { return String(s ?? '').replace(/\s+/g, ''); }

/**
 * 这句话**是不是已经在会话记忆里了**？
 *
 * ★ 与 `thread.mjs` 的 `alreadyInHistory` **刻意不同**，两处判据不一样是有理由的：
 *   那边是「要不要再引一次上文」，判错了一边是冗余、一边是**看不见上文**，
 *   所以它**宁可重复**，匹配放宽（群里的 `【名字】正文`、私聊的 `正文`、assistant 的前缀）。
 *   这边是「要不要往记忆里塞一条」，判错了一边是冗余、一边是**记忆被污染**
 *   （把别的东西误判成「我说过」会让模型以为自己对某句话负过责）。
 *   所以这里**只认逐字相等**，不做前缀/后缀。
 *
 * 代价说清楚：一条外发若被后端改写过一个字，这里就认不出、会重复折一次。
 * 那种情况下**重复**是安全的一侧 —— 与事故本身（看不见）相比，它可接受。
 */
export function alreadySaid(messages, text) {
  const sq = squash(text);
  if (!sq) return true;                       // 没有正文 → 没什么可折的
  if (!Array.isArray(messages)) return false;
  return messages.some((m) => (m?.role === 'assistant') && squash(m.content) === sq);
}

/** 这条会话记忆里，是不是已经带着这个 `message_id` 折过一次了？ */
function foldedIds(messages) {
  const s = new Set();
  for (const m of messages ?? []) {
    for (const id of m?.outbound?.message_ids ?? []) s.add(id);
  }
  return s;
}

/**
 * 该把台账里哪几条补进这份会话？**纯函数**（除了台账读取），可离线喂样本。
 *
 * 折的条件（**四条必须同时成立**，每条都对应一次想清楚过的不折）：
 *   ① 是**这个群/这个人**的（`chat_id` 相等）—— 别的会话的推送不该进这里；
 *   ② 来源不在 `NON_FOLDING` 里 —— 回复循环已经 append 过（见 `SOURCES` 的注释）；
 *   ③ `ok !== false` —— 发失败的消息没出现在群里，不能进记忆；
 *   ④ 正文非空、且逐字不在记忆里、且 `message_id` 没折过。
 *
 * ★ 顺序按台账**文件顺序**（= 时间顺序）追加，并**接在这一轮用户消息之前**。
 *   不做「按时间插进历史中间」：那会切进 `assistant(tool_calls)` 与它对应的 `tool` 结果
 *   之间，下一次请求会被 API 直接拒掉（`memory.compact` 头注里那个 400）。
 *   代价是历史里可能有一处时序不严格 —— 那一侧是安全的。
 */
export function foldPlan(sess, chatId, opt = {}) {
  const messages = sess?.messages ?? [];
  // ★ **不**把 `chatId` 交给 `readEntries` 去过滤。第一版交给它了，于是下面那个
  //   `skipped.notThisChat` **恒为 0** —— 别的群的消息在读进来之前就被丢掉了，
  //   而计数器还在那儿显示「这一类跳过 0 条」。一个永远为 0 的计数器不是读数，
  //   是 §2.4 那个病（名字在、拦不住）。现在过滤在这一层做，跳过的理由列得出来。
  const r = readEntries({ ...opt });
  const skipped = { notThisChat: 0, isReply: 0, unclassified: 0, failed: 0, empty: 0, alreadySaid: 0, alreadyFolded: 0 };
  const entries = [];
  const seenIds = foldedIds(messages);
  // ★ 同一逻辑投递重试时 message_ids 可能为空 / 不同；用 logical_delivery_id 补一层去重，
  //   否则同一条提醒会被折进会话两遍（复验实测过）。
  const seenLogical = new Set(
    messages.map((m) => m?.outbound?.logical_delivery_id).filter(Boolean));

  for (const e of r.entries) {
    if (chatId && e.chat_id !== chatId) { skipped.notThisChat++; continue; }
    if (NON_FOLDING.has(e.source)) { skipped.isReply++; continue; }
    // ★ 没在 `FOLDING` 里的来源（新加的、忘了分类的、台账里那些 `unknown:` 值）：
    //   **照样折** —— 它确实发到群里了，记忆就必须记得（14:39 那次误答的另一半正是这里）。
    //   但要**计数**：漏分类既不静默通过，也不静默丢记忆。D/H 段拿真台账断言它是 0。
    if (!FOLDING.has(e.source)) skipped.unclassified++;
    if (e.ok === false) { skipped.failed++; continue; }
    const t = String(e.text ?? '');
    if (!t.trim()) { skipped.empty++; continue; }
    const ids = e.message_ids ?? [];
    if (ids.some((id) => seenIds.has(id))) { skipped.alreadyFolded++; continue; }
    const logical = e?.extra?.logical_delivery_id;
    if (logical && seenLogical.has(logical)) { skipped.alreadyFolded++; continue; }
    if (alreadySaid(messages, t)) { skipped.alreadySaid++; continue; }
    entries.push(e);
    for (const id of ids) seenIds.add(id);      // 同一批里的重复 id 也不折第二遍
    if (logical) seenLogical.add(logical);      // 重试产生的第二条同投递也不再折
  }

  // ⚠️ 读数采不到时必须**说成未测**，不许当成「没有要补的」—— 后者正是 14:39 那次误答的形状。
  let untested = null;
  if (r.error) untested = `台账读不出（${r.error}）—— 这次「有没有漏补的外发」**未测**`;
  else if (r.badLines) untested = `台账有 ${r.badLines} 行读不出来 —— 可能漏补，**未测**`;
  else if (r.truncated) untested = `台账只读了尾部（>${opt.maxBytes ?? 4 * 1024 * 1024} 字节）—— 更早的没看，**未测**`;

  return {
    entries, skipped, untested, missing: r.missing, ledger: ledgerPath(),
    // 把两个原始读数一并带出去：`untested` 是**结论**，这两个是**依据**。
    // 只回结论的话，调用方（与自证）就只能相信那句中文，而验不了它凭什么这么说。
    truncated: r.truncated, badLines: r.badLines,
  };
}

/**
 * 把台账里「我说过、记忆里没有的」补进这份会话。**daemon 是会话文件的唯一写者**，
 * 所以这个函数只许在 `handleMessage` 的锁里调（`agent.mjs` §5.6）。
 *
 * @returns {{folded:number, plan:object}}
 */
export function foldInto(sess, chatId, opt = {}) {
  const plan = foldPlan(sess, chatId, opt);
  for (const e of plan.entries) {
    mem.append(sess, {
      role: 'assistant',
      content: String(e.text ?? ''),
      at: e.at,                                  // 用**发出那一刻**，不是现在
      outbound: {                                // 折过的痕迹：下次不再折一遍，且可审计
        message_ids: e.message_ids ?? [],
        source: e.source,
        chat_id: e.chat_id ?? null,
        sent_at: e.at ?? null,
      },
    });
  }
  return { folded: plan.entries.length, plan };
}
