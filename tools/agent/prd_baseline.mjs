/**
 * prd_baseline.mjs —— 上游 PRD 基线漂移的**触发者**
 *
 * ## 为什么要有这个文件
 *
 * 2026-09-21 11:51 上游在群里说这份 PRD「**我后续会基于评估重新修改**」；
 * 11:52 守衡回她「**改版后得重新拉一次基线并记新指纹**」。当天仓里补出了
 * `tools/verify_prd_baseline.py`（L1 结构 / L2 副本=指纹 / L3 上游=指纹）。
 *
 * 但那只是「**哪一行命令存在**」，不是「**谁在跑**」——
 * **一个没人跑的检查器，和一句没执行点的承诺是同一个形状，只是高了一层。**
 * 本文件就是那一层：把 L3 挂到守衡的常驻链路上。
 *
 * ## 触发规则（两条，各自防一种漏）
 *
 * | 触发 | 防什么 |
 * |---|---|
 * | **群里收到飞书文档/维基链接** | 新推一篇文档（她 10:42 就是这么推 PRD 的） |
 * | **每天一次兜底**（北京时间换日，借心跳检查） | **她悄悄改已经推过的那一篇** —— 这正是她说的「基于评估重新修改」 |
 *
 * 只有第一条的话，第二种情况永远发现不了；而第二种恰恰是她原话描述的那一种。
 *
 * ## 通报规则（**未测必须与通过长得不一样**，`AGENTS.md` §2.4.2）
 *
 * | 结果 | 群里的动作 |
 * |---|---|
 * | 退 0（上游与指纹一致） | 不说。日志记一行 |
 * | 退 1（**漂移**） | **说** —— 同一个漂移指纹只说一次，防刷屏 |
 * | 退 2（**未测**：网络/凭据不可用） | **说**，每天最多一次。**绝不当成绿** |
 * | 从 红/未测 **回到绿** | 说一次 —— 否则群里只看到"未测"，永远看不到它后来怎么了 |
 *
 * 状态机（`enter()`）是纯函数，`--selftest` 对它做离线反向对照：
 * **证明它在该说的时候说、在该闭嘴的时候闭嘴** —— 两边都要证。
 *
 * ## 第二个触发者：待收清单的到期（2026-09-21 加）
 *
 * `PRD/PRD差异对照-20260921.md` §五 记着上游 09-18 的一句承诺
 * （「其它已跟业务沟通接下来两周陆续整理提供」→ 2026-10-02），而**同一行下面它自己写着
 * 「到期没人会提醒」**。判据在 `tools/verify_pending.py`，清单在 `PMO/待收清单-v1.json`；
 * 本文件这一层就是那个「谁在跑」——**没人跑的检查器，和一句没执行点的承诺是同一个形状**。
 *
 * 通报规则与上面那张表同口径：到期**说**（同一批到期每天最多一次）、未测**说**（每天一次）、
 * 恢复**说一次**、其余闭嘴。**不 @ 任何人** —— 那是催办，不是我们该单方面做的动作。
 *
 * ## 形态：主动告警一律**纯文本**
 *
 * `AGENTS.md` §2.5 规定「卡片还是文本」只允许在 `ws_daemon.mjs` 的 `replyTo` 里判。
 * 主动告警不是"回复"，没有可引用的原文，所以它**不做卡片选型**、直接走
 * `feishu.sendMarkdown` —— 这样它不构成第二处形态决策。
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { REPO_ROOT, stateDir, ensureDir } from './config.mjs';

const SCRIPT = path.join(REPO_ROOT, 'tools', 'verify_prd_baseline.py');
const PENDING_SCRIPT = path.join(REPO_ROOT, 'tools', 'verify_pending.py');

/** 两次检查之间的最短间隔（链接可能连着来，别把同一条链路打爆） */
export const COOLDOWN_MS = 30 * 60 * 1000;

/** 飞书文档/维基链接。**只认域名与路径形状，不认标题** —— 标题会变，链接不会。 */
export const LARK_DOC_RE =
  /https?:\/\/[\w.-]*feishu\.cn\/(wiki|docx|docs|sheets|base|file|drive)\/[\w-]+/i;

/** 北京时间的日历日（守衡所有对外时间口径都是 +08:00） */
export function bjDate(now = new Date()) {
  return new Date(now.getTime() + 8 * 3600 * 1000).toISOString().slice(0, 10);
}

/* ─────────────────────── 状态（纯函数，可离线测） ─────────────────────── */

/**
 * ★ **两个检查各自一份状态文件**（2026-09-21 实测后改的，别合回去）。
 *
 * 原先两个检查共写 `prd-baseline-watch.json`，第一次真跑就丢数据：
 *
 * ```
 * [+0.179s] · 待收检查[startup] 退出码 0     ← 写了 p_* 键
 * [+3.030s] · 基线检查[startup] 退出码 0     ← 用 3 秒前读的旧快照整体覆盖，p_* 没了
 * ```
 *
 * 形状是 **read → 慢操作（跑子进程/等网络）→ write**：读到的快照是旧的，
 * 写回去就把这中间别人写的东西抹掉。后果不响：`p_saidDueKey` 被抹 → 同一条到期
 * 提醒会**反复重发**；`p_saidUntestedDay` 被抹 → 未测也会反复说。
 * 查到它靠的不是自证（自证全绿），是**跑起来之后回读状态**（§2.4.3 记了这一条）。
 */
const STATE_FILE = () => path.join(stateDir(), 'prd-baseline-watch.json');
const PENDING_STATE_FILE = () => path.join(stateDir(), 'prd-pending-watch.json');

export function loadState(file = STATE_FILE()) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return {};
  }
}

export function saveState(s, file = STATE_FILE()) {
  ensureDir(stateDir());
  try { fs.writeFileSync(file, JSON.stringify(s, null, 2)); }
  catch { /* 状态写不进去不该让守衡崩 —— 顶多下次多说一句 */ }
}

/** 待收清单那一份状态（与基线**分文件**，见上面那段实测）。 */
export const loadPendingState = () => loadState(PENDING_STATE_FILE());

/**
 * 状态迁移：给定「上次说过什么」和「这次读到什么」，返回「该不该说、说什么」。
 *
 * ★ 这是纯函数，且 `--selftest` 对它做正反两面的对照 ——
 *   一个恒说（刷屏）或恒不说（等于没有）的告警器都没用，两边都要证。
 *
 * @param {object} prev  上一次的记录（loadState 的形状）
 * @param {object} now   { code, drifted:[{file, old, now}], untested:[file], day }
 * @returns {{state:object, say:string|null, why:string}}
 */
export function enter(prev, now) {
  // ★ 只认 0/1/2。别的（被杀 137、崩了、-1…）一律折成 **2 = 未测** ——
  //   「我没测成」和「我测了是绿的」必须长得不一样（§2.4.2 第 2 条）。
  //   第一版没有这一行，137 会一路落到末尾的绿分支 —— 那正是这个检查器要防的病。
  const code = [0, 1, 2].includes(now.code) ? now.code : 2;
  const day = now.day;
  const st = { ...prev, lastRunAt: new Date().toISOString(), lastDay: day, lastCode: code, rawCode: now.code };

  if (code === 1 && now.drifted.length) {
    // 同一个漂移指纹只说一次；指纹变了（又改了一版）就再说。
    const fp = now.drifted.map((d) => `${d.file}:${d.now}`).sort().join('|');
    if (prev.saidDriftFp === fp) {
      return { state: { ...st, lastState: 'drift' }, say: null, why: '同一个漂移指纹已经说过' };
    }
    const lines = now.drifted.map((d) =>
      `· **${d.file}**\n  旧指纹 \`${String(d.old).slice(0, 16)}…\` → 新指纹 \`${String(d.now).slice(0, 16)}…\``);
    return {
      state: { ...st, lastState: 'drift', saidDriftFp: fp },
      why: '上游改版了（这是本检查存在的理由）',
      say: [
        `⚠️ **上游 PRD 改版了** —— 我手上那份基线已经过期。`,
        ...lines,
        `我读到的还是旧版，**而且不会自己察觉**。请给我一分钟重拉一次基线并记新指纹；`,
        `在那之前，凡是引用这份 PRD 的判断都按旧版算。`,
      ].join('\n'),
    };
  }

  if (code === 2) {
    if (prev.saidUntestedDay === day) {
      return { state: { ...st, lastState: 'untested' }, say: null, why: '今天的「未测」已经说过一次' };
    }
    return {
      state: { ...st, lastState: 'untested', saidUntestedDay: day },
      why: '没测成 —— 报「未测」，不报「没问题」',
      say: [
        `⚠️ **上游基线检查这次没跑成**（拿不到正文或凭据）。`,
        `这不是「没问题」，是**「这次没测」** —— 我此刻无法判断手上那份 PRD 是不是最新版。`,
        `下次触发时会重试。${(now.untested ?? []).length ? `未测：${now.untested.join('、')}` : ''}`,
      ].join('\n'),
    };
  }

  // 退 0：只在上一次是红/未测时说一句"恢复了"，否则闭嘴。
  if (prev.lastState === 'drift' || prev.lastState === 'untested') {
    return {
      state: { ...st, lastState: 'ok', saidDriftFp: null },
      why: '从红/未测恢复 —— 群里之前看到过异常，得看到它结束',
      say: `✅ 上游基线检查恢复了：手上那份 PRD 与指纹一致。`,
    };
  }
  return { state: { ...st, lastState: 'ok', saidDriftFp: null }, say: null, why: '一直是绿的，不刷屏' };
}

/* ─────────────────────── 执行 ─────────────────────── */

/** 跑一次 verify_prd_baseline.py，把退出码与关键行解析出来。**超时也算未测（退 2）。** */
export function runChecker({ timeoutMs = 90_000, offline = false } = {}) {
  return new Promise((resolve) => {
    const args = [SCRIPT, ...(offline ? ['--offline'] : [])];
    let out = '';
    let done = false;
    const child = spawn('python3', args, { cwd: REPO_ROOT });
    const finish = (code, note) => {
      if (done) return;
      done = true;
      resolve({ code, out, note });
    };
    const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch {} finish(2, '超时 —— 按未测处理'); }, timeoutMs);
    child.stdout.on('data', (b) => { out += b.toString(); });
    child.stderr.on('data', (b) => { out += b.toString(); });
    child.on('error', (e) => { clearTimeout(timer); finish(2, `起不来：${e.message}`); });
    child.on('close', (code) => { clearTimeout(timer); finish(code === null ? 2 : code); });
  });
}

/** 从输出里抠出「哪份文件、旧指纹、新指纹」。抠不到不算漂移 —— 退 1 但没指纹时走兜底文案。 */
export function parseDrift(out) {
  const drifted = [];
  const re = /★★ 上游改版了：(.+)\n\s*索引指纹 ([0-9a-f]{64})\n\s*现场指纹 ([0-9a-f]{64})/g;
  let m;
  while ((m = re.exec(out)) !== null) drifted.push({ file: m[1].trim(), old: m[2], now: m[3] });
  return drifted;
}

export function parseUntested(out) {
  const m = /⚠️\s+L3 未测：(.+?) ——/.exec(out);
  return m ? m[1].split(/,\s*/).map((s) => s.trim()).filter(Boolean) : [];
}

/**
 * 去掉**否定域**：`这不是「没问题」，是「这次没测」` 里的「没问题」不算违规。
 *
 * ★ 为什么需要它：本项目的 `verify_engine_contract.py` **V25b** 踩过一模一样的坑 ——
 *   禁用语检查把否定句也算成命中。本文件离线自测第 6 条就是这么误报的。
 *   **一个会误报的检查器比没有检查器更糟**，所以判据要能区分「说」和「否认」。
 */
export function stripNegated(s) {
  return String(s ?? '')
    .replace(/(不是|不算|并非|而非)\s*[「『"'][^」』"']*[」』"']/g, '')
    .replace(/(不是|不算|并非|而非)[^\n，。；]{0,12}/g, '');
}

/**
 * 告警发到哪个群：优先用状态里记的（最近来过消息的群），否则问一次接口。
 *
 * ★ `feishu` 用**动态 import**：静态 import 会在加载时就构造 Lark Client（要凭据），
 *   那会让 `--selftest` 变成一个需要联网/凭据的东西 —— 而它必须是随时可跑的。
 */
export async function resolveChat() {
  const st = loadState();
  if (st.lastChatId) return st.lastChatId;
  try {
    const feishu = await import('./feishu.mjs');
    const r = await feishu.client.im.chat.list({ params: { page_size: 20 } });
    const items = r?.data?.items ?? [];
    const g = items.find((c) => c.chat_mode === 'group') ?? items[0];
    if (g?.chat_id) { saveState({ ...st, lastChatId: g.chat_id }); return g.chat_id; }
  } catch { /* 取不到就让调用方走"只进日志"那条路 */ }
  return null;
}

/**
 * 触发一次检查（含冷却与去重），必要时返回要发的话。
 *
 * @param {object} o
 * @param {'link'|'daily'} o.reason
 * @param {boolean} o.force 跳过冷却（`--selftest` 与手动用）
 * @param {string}  o.day   注入用（默认现算）
 */
/**
 * ★ **单飞（single-flight）**：同一时刻只允许一次检查在跑。
 *
 * 为什么必须有：检查体是 **read 状态 → 跑子进程/等网络（最长 90 秒）→ write 状态**。
 * 两个触发同时来（比如启动即核 + 群里刚推了链接，或心跳兜底撞上手动 `--check`），
 * 后写的那个用的是**更旧的快照**，会把先写的抹掉 —— 表现就是同一条告警反复重发。
 * 与「两个检查各用一份状态文件」是同一件事的两半：**一个文件同时只能有一个写者。**
 */
let baselineInFlight = null;
let pendingInFlight = null;

export async function checkNow(opts = {}) {
  if (baselineInFlight) return { skipped: '上一次基线检查还在跑' };
  baselineInFlight = runCheckNow(opts);
  try { return await baselineInFlight; } finally { baselineInFlight = null; }
}

async function runCheckNow({ reason = 'daily', force = false, day = bjDate(), run = runChecker } = {}) {
  const prev = loadState();
  const last = prev.lastRunAt ? Date.parse(prev.lastRunAt) : 0;
  if (!force && Date.now() - last < COOLDOWN_MS) {
    return { skipped: `冷却中（上次 ${prev.lastRunAt}，不足 ${COOLDOWN_MS / 60000} 分钟）` };
  }

  const { code, out, note } = await run({});
  const now = {
    code,
    day,
    drifted: code === 1 ? parseDrift(out) : [],
    untested: code === 2 ? parseUntested(out) : [],
  };
  // 退 1 但抠不出指纹：也要说，只是文案退化（宁可说，不可沉默）
  if (code === 1 && !now.drifted.length) {
    now.drifted = [{ file: '（输出里没抠到具体文件，见 PMO/logs）', old: '', now: '' }];
  }
  const { state, say, why } = enter(prev, now);
  saveState(state);
  return { code, note, say, why, reason, out };
}

/* ─────────────────── 待收清单：到期提醒（`PMO/待收清单-v1.json`） ─────────────────── */

/**
 * 跑一次 `verify_pending.py --json`。**输出不是合法 JSON ⇒ 未测（退 2）** ——
 * 「我读不出来」和「没有到期」必须长得不一样（`AGENTS.md` §2.4.2 第 2 条）。
 */
export function runPendingChecker({ timeoutMs = 30_000, today = null } = {}) {
  return new Promise((resolve) => {
    let out = '';
    let done = false;
    // `today` 只是把「今天」注入给 python，**不参与要不要发的决定** ——
    // 它让「到期那天群里会收到什么」现在就能看一遍（同 restart_shouheng.sh 的 --since）。
    const args = [PENDING_SCRIPT, '--json', ...(today ? [`--today=${today}`] : [])];
    const child = spawn('python3', args, { cwd: REPO_ROOT });
    const finish = (code, note, data) => {
      if (done) return;
      done = true;
      resolve({ code, note, data, out });
    };
    const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch {} finish(2, '超时 —— 按未测处理', null); }, timeoutMs);
    child.stdout.on('data', (b) => { out += b.toString(); });
    child.stderr.on('data', (b) => { out += b.toString(); });
    child.on('error', (e) => { clearTimeout(timer); finish(2, `起不来：${e.message}`, null); });
    child.on('close', (code) => {
      clearTimeout(timer);
      let data = null;
      try { data = JSON.parse(out.trim().split('\n').filter(Boolean).pop()); } catch { /* 下面按未测处理 */ }
      const raw = code === null ? 2 : code;
      const c = [0, 1, 2].includes(raw) && data ? raw : 2;
      finish(c, data ? '' : '输出不是合法 JSON —— 按未测处理', data);
    });
  });
}

/**
 * 待收清单的通报状态机（纯函数，`--selftest` 对它做正反两面）。
 *
 * ★ 为什么「同一批到期**每天**最多说一次」而不是「只说一次」：
 *   只说一次 = 说过之后就永久沉默，而那件事还悬着 —— 等于没有告警器。
 *   每天一次与上面「未测每天一次」同口径，也是本项目已有的尺度。
 *
 * @param {object} prev  loadState() 的形状（本节的键统一用 `p_` 前缀，不碰基线那套）
 * @param {object} now   { code, day, overdue:[{id,事项,到期日,过期天数,原话,到期日来源}] }
 */
export function enterPending(prev, now) {
  const code = [0, 1, 2].includes(now.code) ? now.code : 2;   // 137 被杀等一律折成未测
  const day = now.day;
  const st = { ...prev, p_lastRunAt: new Date().toISOString(), p_lastDay: day, p_lastCode: code, p_rawCode: now.code };

  if (code === 1 && (now.overdue ?? []).length) {
    const key = now.overdue.map((o) => `${o.id}@${o.到期日}`).sort().join('|');
    if (prev.p_saidDueKey === key && prev.p_saidDueDay === day) {
      return { state: { ...st, p_lastState: 'due' }, say: null, why: '同一批到期今天已经说过一次' };
    }
    const lines = now.overdue.map((o) => {
      const over = o.过期天数 === 0 ? '今天到期' : `已过 ${o.过期天数} 天`;
      const why = o.到期日来源 === '我方推算'
        ? `（这个日子是我方按原话推出来的，**不是对方给的日期** —— 所以是问一句，不是催办）` : '';
      return [
        `· **${o.事项}** —— 到期 ${o.到期日}（${over}）`,
        o.原话 ? `  原话：「${o.原话}」` : null,
        why ? `  ${why}` : null,
      ].filter(Boolean).join('\n');
    });
    return {
      state: { ...st, p_lastState: 'due', p_saidDueKey: key, p_saidDueDay: day },
      why: `待收清单有 ${now.overdue.length} 件到期未收`,
      say: [
        `⏳ **上游有承诺到期了，还没收到**（${now.overdue.length} 件）`,
        ...lines,
        `清单在 \`PMO/待收清单-v1.json\`；收到之后把那条改成 done 并记完成依据，我就不会再提。`,
      ].join('\n'),
    };
  }

  if (code === 2) {
    if (prev.p_saidUntestedDay === day) {
      return { state: { ...st, p_lastState: 'untested' }, say: null, why: '今天的「未测」已经说过一次' };
    }
    return {
      state: { ...st, p_lastState: 'untested', p_saidUntestedDay: day },
      why: '没读成 —— 报「未测」，不报「没有待收」',
      say: [
        `⚠️ **待收清单这次没读成**${now.reason ? `（${now.reason}）` : ''}。`,
        `这不是「没有到期未收」，是**「这次没测」** —— 我此刻不知道有没有承诺已经到期。`,
        `下次触发时会重试。`,
      ].join('\n'),
    };
  }

  if (prev.p_lastState === 'due' || prev.p_lastState === 'untested') {
    return {
      state: { ...st, p_lastState: 'ok', p_saidDueKey: null },
      why: '从到期/未测恢复 —— 群里之前看到过异常，得看到它结束',
      say: `✅ 待收清单：现在没有到期未收。`,
    };
  }
  return { state: { ...st, p_lastState: 'ok' }, say: null, why: '没有到期未收，不刷屏' };
}

/** 触发一次待收检查（含换日去重）。与 `checkNow` 同一条单飞纪律，理由见那里。 */
export async function checkPending(opts = {}) {
  if (pendingInFlight) return { skipped: '上一次待收检查还在跑' };
  pendingInFlight = runCheckPending(opts);
  try { return await pendingInFlight; } finally { pendingInFlight = null; }
}

async function runCheckPending({ reason = 'daily', force = false, day = null, today = null, run = runPendingChecker } = {}) {
  const prev = loadPendingState();
  const D = day ?? today ?? bjDate();
  if (!force && prev.p_lastDay === D) {
    return { skipped: `今天（${D}）已经跑过` };
  }
  const { code, note, data } = await run({ today });
  const now = {
    code,
    day: D,
    overdue: data?.overdue ?? [],
    reason: data?.reason ?? note ?? '',
  };
  const { state, say, why } = enterPending(prev, now);
  // ★ `today` 被注入时**不落状态** —— 那是一次「看一遍」，不是一次真跑。
  //   落了会很阴：state 里记下「10-03 已经说过」之后，**真正的 10-03 到了反而会闭嘴**，
  //   而群里什么都没收到。一次查看不该改掉将来要发生的事。
  if (today) return { code, note, say, why, reason, overdue: now.overdue, dryRun: `注入日 ${today} —— 未落状态` };
  saveState(state, PENDING_STATE_FILE());
  return { code, note, say, why, reason, overdue: now.overdue };
}

/* ─────────────────────── 反向对照（离线，不动盘不联网） ─────────────────────── */

/**
 * 证明这套告警**两边都对**：该说的时候说，该闭嘴的时候闭嘴。
 * 只证一边的都是坏检查器 —— 恒说的刷屏，恒不说的等于没有。
 */
export async function selftest() {
  const D = '2026-09-21';
  const drift = (fp) => ({ code: 1, day: D, untested: [], drifted: [{ file: 'A.md', old: 'a'.repeat(64), now: fp }] });
  /** 待收清单的假样本：n 件到期未收（用的是 P-03 的真实字段形状） */
  const pdue = (n) => ({
    code: 1, day: D,
    overdue: Array.from({ length: n }, (_, i) => ({
      id: `P-0${i + 1}`, 事项: '其余品线的规则库（吸奶器之外）', 到期日: '2026-10-02',
      过期天数: 0, 原话: '其它已跟业务沟通接下来两周陆续整理提供', 到期日来源: '我方推算',
    })),
  });
  const dueKey = (n) => Array.from({ length: n }, (_, i) => `P-0${i + 1}@2026-10-02`).sort().join('|');
  const cases = [
    ['绿 → 绿：不许刷屏', () => enter({ lastState: 'ok' }, { code: 0, day: D, drifted: [], untested: [] }).say === null],
    ['第一次漂移 → **必须说**', () => typeof enter({ lastState: 'ok' }, drift('b'.repeat(64))).say === 'string'],
    ['同一个漂移再说一次 → 闭嘴（防刷屏）',
      () => enter({ lastState: 'drift', saidDriftFp: `A.md:${'b'.repeat(64)}` }, drift('b'.repeat(64))).say === null],
    ['漂移指纹变了一个字符 → **必须再说**（又改了一版）',
      () => typeof enter({ lastState: 'drift', saidDriftFp: `A.md:${'b'.repeat(64)}` }, drift('c'.repeat(64))).say === 'string'],
    ['未测 → **必须说**，且文案里要出现「没测」/「未测」',
      () => { const r = enter({ lastState: 'ok' }, { code: 2, day: D, drifted: [], untested: ['A.md'] });
              return typeof r.say === 'string' && /没测|未测/.test(r.say); }],
    ['★ 未测**不许**被说成「没问题」/「正常」（否定域不算，同 V25b）',
      () => { const r = enter({ lastState: 'ok' }, { code: 2, day: D, drifted: [], untested: ['A.md'] });
              return !/没问题|一切正常|正常/.test(stripNegated(r.say)); }],
    ['反向对照：换成一句真的「一切正常」→ 上面那条判据必须红（否则它恒真）',
      () => /没问题|一切正常|正常/.test(stripNegated('检查完成：上游一切正常，没问题'))],
    ['反向对照：`这不是「没问题」` 必须被剥掉；而裸的 `没问题` 必须留下',
      () => stripNegated('这不是「没问题」') === '' || !/没问题/.test(stripNegated('这不是「没问题」'))
            ? /没问题/.test(stripNegated('上游没问题')) : false],
    ['同一天第二次未测 → 闭嘴（每天最多一次）',
      () => enter({ lastState: 'untested', saidUntestedDay: D }, { code: 2, day: D, drifted: [], untested: [] }).say === null],
    ['第二天仍未测 → **再说**（昨天的通报不算今天的）',
      () => typeof enter({ lastState: 'untested', saidUntestedDay: '2026-09-20' },
                         { code: 2, day: D, drifted: [], untested: [] }).say === 'string'],
    ['从漂移回到绿 → **必须说**（群里看到过异常，得看到它结束）',
      () => typeof enter({ lastState: 'drift' }, { code: 0, day: D, drifted: [], untested: [] }).say === 'string'],
    ['从未测回到绿 → **必须说**', () => typeof enter({ lastState: 'untested' }, { code: 0, day: D, drifted: [], untested: [] }).say === 'string'],
    ['漂移也算一种「说过」：进入 drift 后 lastState 必须是 drift',
      () => enter({}, drift('d'.repeat(64))).state.lastState === 'drift'],
    ['★ 不认识的退出码（137 被杀）→ 必须落进 untested，**不许当绿**',
      () => enter({ lastState: 'ok' }, { code: 137, day: D, drifted: [], untested: [] }).state.lastState === 'untested'],
    ['反向对照：未测状态下退出码 0 必须回 ok（上面那条不是恒真）',
      () => enter({ lastState: 'untested' }, { code: 0, day: D, drifted: [], untested: [] }).state.lastState === 'ok'],
    ['链接识别：认 wiki/docx/base/sheets，不认普通网页',
      () => LARK_DOC_RE.test('见 https://momcozy-in.feishu.cn/wiki/NB55wAq8liEOdKkquL2cgtPEnmg')
            && LARK_DOC_RE.test('https://x.feishu.cn/base/HPiqbafDTaJV0vsCqD0c3m0UnAe?from=auth_notice')
            && !LARK_DOC_RE.test('https://example.com/wiki/abc')],
    ['从输出里抠漂移指纹（喂本次真实的输出形状）',
      () => { const o = '★★ 上游改版了：A.md\n   索引指纹 ' + '1'.repeat(64) + '\n   现场指纹 ' + '2'.repeat(64) + '\n';
              const d = parseDrift(o); return d.length === 1 && d[0].file === 'A.md' && d[0].now === '2'.repeat(64); }],
    ['抠不到指纹时 parseDrift 回空数组（**不许**凭空造一个）', () => parseDrift('随便一段话').length === 0],

    /* ── 待收清单的到期提醒（enterPending）── */
    ['待收：无到期 → 不许刷屏', () => enterPending({ p_lastState: 'ok' }, { code: 0, day: D, overdue: [] }).say === null],
    ['待收：第一次到期 → **必须说**', () => typeof enterPending({ p_lastState: 'ok' }, pdue(1)).say === 'string'],
    ['待收：同一天同一批再说一次 → 闭嘴（防刷屏）',
      () => enterPending({ p_lastState: 'due', p_saidDueKey: dueKey(1), p_saidDueDay: D }, pdue(1)).say === null],
    ['待收：第二天仍未收到 → **必须再说**（昨天说过不算今天）',
      () => typeof enterPending({ p_lastState: 'due', p_saidDueKey: dueKey(1), p_saidDueDay: '2026-09-20' }, pdue(1)).say === 'string'],
    ['待收：到期集合变了（多了一件）→ **必须再说**',
      () => typeof enterPending({ p_lastState: 'due', p_saidDueKey: dueKey(1), p_saidDueDay: D }, pdue(2)).say === 'string'],
    ['★ 待收：到期文案里不许出现「没问题/正常」（否定域不算，同 V25b）',
      () => !/没问题|一切正常|正常/.test(stripNegated(enterPending({}, pdue(1)).say))],
    ['★ 待收：文案必须带原话 + 说明那个日子是我方推算的 —— 否则读者会以为日期是对方给的',
      () => { const s = enterPending({}, pdue(1)).say;
              return s.includes('其它已跟业务沟通') && s.includes('不是对方给的日期'); }],
    ['待收：未测 → **必须说**，且文案里要出现「没测/未测」',
      () => { const r = enterPending({ p_lastState: 'ok' }, { code: 2, day: D, overdue: [], reason: '清单读不出' });
              return typeof r.say === 'string' && /没测|未测/.test(r.say); }],
    ['★ 待收：未测**不许**被说成「没有到期未收」',
      () => !/没有到期未收/.test(stripNegated(enterPending({}, { code: 2, day: D, overdue: [], reason: 'x' }).say))],
    ['反向对照：一句真的「没有到期未收」→ 上面那条判据必须能抓到（否则它恒真）',
      () => /没有到期未收/.test(stripNegated('待收清单：现在没有到期未收。'))],
    ['待收：同一天第二次未测 → 闭嘴（每天最多一次）',
      () => enterPending({ p_lastState: 'untested', p_saidUntestedDay: D }, { code: 2, day: D, overdue: [] }).say === null],
    ['待收：从到期回到 0 → **必须说**（群里看到过异常，得看到它结束）',
      () => typeof enterPending({ p_lastState: 'due' }, { code: 0, day: D, overdue: [] }).say === 'string'],
    ['待收：不认识的退出码（137 被杀）→ 必须落进 untested，**不许当绿**',
      () => enterPending({ p_lastState: 'ok' }, { code: 137, day: D, overdue: [] }).state.p_lastState === 'untested'],
    ['待收：反向对照 —— 未测状态下退出码 0 必须回 ok（上面那条不是恒真）',
      () => enterPending({ p_lastState: 'untested' }, { code: 0, day: D, overdue: [] }).state.p_lastState === 'ok'],
    ['待收：只写 p_ 前缀，不许污染基线那套状态键',
      () => { const s = enterPending({ lastState: 'ok', saidDriftFp: 'x' }, pdue(1)).state;
              return s.lastState === 'ok' && s.saidDriftFp === 'x' && s.p_lastState === 'due'; }],
    ['待收：过期天数要出现在文案里（「今天到期」/「已过 N 天」）',
      () => { const r = enterPending({}, { code: 1, day: D, overdue: [{ ...pdue(1).overdue[0], 过期天数: 3 }] });
              return /已过 3 天/.test(r.say); }],

    /* ── ★ 单飞：两个检查不许同时写状态（2026-09-21 真跑时丢过一次数据）── */
    ['★ 单飞：上一次还在跑时，第二次必须立刻跳过（否则后写的旧快照会抹掉先写的）',
      async () => {
        let release; const gate = new Promise((r) => { release = r; });
        const slow = async () => { await gate; return { code: 0, note: '', data: { overdue: [] } }; };
        const first = checkPending({ force: true, today: '2026-10-03', run: slow });
        const second = await checkPending({ force: true, today: '2026-10-03', run: slow });
        release(); await first;
        return typeof second.skipped === 'string';
      }],
    ['反向对照：第一次跑完之后再调 → **不许** skip（上面那条不是恒真）',
      async () => {
        const r = await checkPending({ force: true, today: '2026-10-03',
                                        run: async () => ({ code: 0, note: '', data: { overdue: [] } }) });
        return !r.skipped && r.code === 0;
      }],
    ['★ 单飞：基线那条同样成立（两条链路各有一把锁）',
      async () => {
        let release; const gate = new Promise((r) => { release = r; });
        const slow = async () => { await gate; return { code: 0, out: '', note: '' }; };
        const first = checkNow({ force: true, run: slow });
        const second = await checkNow({ force: true, run: slow });
        release(); await first;
        return typeof second.skipped === 'string';
      }],
    ['★ 两把锁**互相独立**：待收在跑，不许挡住基线（否则一个卡住会拖停另一个）',
      async () => {
        let release; const gate = new Promise((r) => { release = r; });
        const slowP = async () => { await gate; return { code: 0, note: '', data: { overdue: [] } }; };
        const p = checkPending({ force: true, today: '2026-10-03', run: slowP });
        const b = await checkNow({ force: true, run: async () => ({ code: 0, out: '', note: '' }) });
        release(); await p;
        return b === undefined || typeof b.skipped !== 'string' || !/待收/.test(b.skipped);
      }],
  ];

  let bad = 0;
  console.log('='.repeat(72));
  console.log('prd_baseline 触发器 · 反向对照（离线；不动盘、不联网、不发消息）');
  console.log('='.repeat(72));
  for (const [i, [name, fn]] of cases.entries()) {
    let ok = false, err = '';
    // `await`：用例可以是同步的，也可以是异步的（并发那两条）——两者都收
    try { ok = Boolean(await fn()); } catch (e) { err = `（抛异常 ${e.message}）`; }
    if (!ok) bad++;
    console.log(`  ${ok ? '✅' : '❌'} [${String(i + 1).padStart(2)}/${cases.length}] ${name}${err}`);
  }
  console.log('-'.repeat(72));
  if (bad) { console.log(`❌ ${cases.length} 项中 ${bad} 项失败 —— 告警器有问题，别信它会响`); return 1; }
  console.log(`✅ ${cases.length} 项全过（含「该闭嘴时闭嘴」与「该说时必说」两侧）`);
  return 0;
}

/* ─────────────────────── CLI ─────────────────────── */

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv.includes('--selftest')) process.exit(await selftest());
  if (process.argv.includes('--check')) {
    const r = await checkNow({ reason: 'manual', force: true, run: (o) => runChecker({ ...o, offline: process.argv.includes('--offline') }) });
    console.log(JSON.stringify({ code: r.code, note: r.note, why: r.why, say: r.say, skipped: r.skipped }, null, 2));
    process.exit(r.code ?? 0);
  }
  if (process.argv.includes('--pending')) {
    const t = process.argv.find((a) => a.startsWith('--today='))?.slice(8) ?? null;
    const r = await checkPending({ reason: 'manual', force: true, today: t });
    console.log(JSON.stringify({ code: r.code, why: r.why, say: r.say, skipped: r.skipped,
                                 dryRun: r.dryRun, overdue: r.overdue ?? [] }, null, 2));
    process.exit(r.code ?? 0);
  }
  if (process.argv.includes('--state')) { console.log(JSON.stringify(loadState(), null, 2)); process.exit(0); }
  console.log('用法：node tools/agent/prd_baseline.mjs --selftest | --check [--offline] | --pending [--today=YYYY-MM-DD] | --state');
  process.exit(0);
}
