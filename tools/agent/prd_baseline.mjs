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
 * 通报规则与上面那张表同口径，但**多一行**（2026-09-22 补）：
 *
 * | 结果 | 群里的动作 |
 * |---|---|
 * | 退 0（没有到期未收） | 不说（除非上一次是异常） |
 * | 退 1 且**有到期明细** | **说** —— 同一批到期每天最多一次 |
 * | **退 1 但明细为空**（清单自己结构坏了） | **说**，每天最多一次。**绝不当成「没有到期」** |
 * | 退 2（未测：清单读不出） | **说**，每天最多一次 |
 * | 从 到期/未测/清单坏了 **回到绿** | 说一次 |
 *
 * 第三行是 2026-09-22 补的：`verify_pending.py` 的退 1 **有两个来源**
 * （`code = 1 if (struct or od) else 0`），而这里原先只认`od`那一个 ——
 * 清单坏了会掉进绿分支，群里收到「✅ 现在没有到期未收」。见 `enterPending` 里那段注释。
 *
 * **不 @ 任何人** —— 那是催办，不是我们该单方面做的动作。
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

/**
 * ★ 第三个文件：「最近来过消息的群」。**2026-09-22 加的，别再合回去。**
 *
 * 原先它叫 `lastChatId`，住在**基线那份状态文件**里，而写它的是四条互不相干的路径：
 * `baselineWatch` / `pendingWatch`（`ws_daemon.mjs:158/187`）、`resolveChat`（本文件下面的
 * `:236`）、以及基线检查自己（`runCheckNow`）。后果实测到了，两个：
 *
 * 1. **待收那条链路在写基线那份文件。** `saveState` 的默认目标就是基线那份，于是
 *    `pendingWatch` 每次触发都往它里面盖一个 `lastChatId`；而它靠 `{ ...loadState() }`
 *    把文件里一切原样带下去 —— 包括早已作废的 `p_lastCode` 那 5 个 `p_*` 键。
 *    现场读数：`prd-baseline-watch.json` 里 `p_lastDay` = `2026-09-21`，而正确的
 *    `prd-pending-watch.json` 里是 `2026-09-22` —— **同一个键两个文件两个值**。
 * 2. **它住在别人的 read→慢→write 窗口里。** `runCheckNow` 的形状是
 *    「读状态 → 跑子进程（最长 90 秒）→ 整体写回」，窗口内任何人写的 `lastChatId`
 *    都会被那份 90 秒前的旧快照抹掉。
 *
 * 所以它**不该住在任何一个检查的状态文件里** —— 它不是检查的状态，是「往哪儿说话」。
 * 拆出来之后：**一个文件同时只有一个写者**这句话对三份文件各自都成立。
 */
const CHAT_FILE = () => path.join(stateDir(), 'last-chat.json');

export function loadState(file = STATE_FILE()) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return {};
  }
}

/**
 * 「最近来过消息的群」。
 *
 * 读到**旧位置**（基线状态文件里的 `lastChatId`）时只用一次、不再写回 ——
 * 那是历史残留，新的记账只进 `last-chat.json`。不这么写的话，只要有人读它，
 * `{ ...prev }` 就会把它永远带下去，残留就死不掉。
 */
export function loadChatId() {
  try {
    const v = JSON.parse(fs.readFileSync(CHAT_FILE(), 'utf8'))?.chatId;
    if (v) return v;
  } catch { /* 没有就用旧位置那一份 */ }
  return loadState().lastChatId ?? null;
}

export function saveChatId(chatId) {
  if (!chatId) return;
  ensureDir(stateDir());
  try { fs.writeFileSync(CHAT_FILE(), JSON.stringify({ chatId }, null, 2)); }
  catch { /* 同理：记不住群不该让守衡崩，顶多下次多问一次接口 */ }
}

export function saveState(s, file = STATE_FILE()) {
  ensureDir(stateDir());
  try { fs.writeFileSync(file, JSON.stringify(s, null, 2)); }
  catch { /* 状态写不进去不该让守衡崩 —— 顶多下次多说一句 */ }
}

/** 待收清单那一份状态（与基线**分文件**，见上面那段实测）。 */
export const loadPendingState = () => loadState(PENDING_STATE_FILE());

/**
 * ★ 状态只保留**白名单里的键** —— 不再用 `{ ...prev }`。
 *
 * 为什么不用展开：`{ ...prev }` 把文件里**一切**原样带下去，包括别人写错的、
 * 以及早已作废的键。实测到的后果就是 `prd-baseline-watch.json` 里一直含着 5 个
 * `p_*` 键，值停在 09-21，而 `prd-pending-watch.json` 里同一批键是 09-22 ——
 * **同一个键在两个文件里两个值，其中一个永远是旧快照。**
 *
 * 判据不是「把那 5 个键清掉」（清完下一次 `{ ...prev }` 又带回来），
 * 而是「状态文件的键集合**恰好**在这张表里」—— 残留**由构造不可能**，不靠清理。
 * 两边各一张表，`--selftest` 里有一条断言它们互不越界。
 */
const KEEP_BASELINE = ['lastState', 'saidDriftFp', 'saidUntestedDay'];
const KEEP_PENDING = ['p_lastState', 'p_saidDueKey', 'p_saidDueDay', 'p_saidUntestedDay', 'p_saidBrokenDay'];
const pick = (prev, keys) =>
  Object.fromEntries(keys.filter((k) => prev?.[k] !== undefined).map((k) => [k, prev[k]]));

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
  const st = { ...pick(prev, KEEP_BASELINE), lastRunAt: new Date().toISOString(), lastDay: day, lastCode: code, rawCode: now.code };

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
  const known = loadChatId();
  if (known) return known;
  try {
    const feishu = await import('./feishu.mjs');
    const r = await feishu.client.im.chat.list({ params: { page_size: 20 } });
    const items = r?.data?.items ?? [];
    const g = items.find((c) => c.chat_mode === 'group') ?? items[0];
    /**
     * ★ **猜出来的群不落盘。**（2026-09-22 加）
     *
     * 这里挑的是「接口返回的第一个群」—— 它通常就是最近活跃的那个，但**那是接口的排序**，
     * 不是我们的依据；而我们没有查过「这个群是不是我们该说话的地方」。
     * 原先这里会 `saveChatId(...)` 把它**持久化**：一次猜测从此变成事实，
     * 之后每次告警都往那儿发，而没有任何东西会质疑它。
     *
     * 不落盘之后的行为：每次没有已知群时才问一次接口，而调用方那条
     * 「…已发到 <目标>」的日志**每次都打**，所以目标是猜的这件事在日志里看得见。
     * 真正的「最近来过消息的群」由 `ws_daemon.onMessage` 每条消息调 `saveChatId` 记下
     * —— 那才是这句语义的字面意思，且自维护。
     */
    if (g?.chat_id) return g.chat_id;
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

async function runCheckNow({ reason = 'daily', force = false, day = bjDate(), run = runChecker,
                            dryRun = false, stateFile = null } = {}) {
  // ★ `stateFile` 可注入：存在的理由是**自证** —— `--selftest` 要能证明
  //   「`dryRun` 下真的一个字节都没落盘」，而这句话只有在能指定文件时才证得了。
  //   默认仍是那份真状态文件，生产路径不受影响。
  const file = stateFile ?? STATE_FILE();
  const prev = loadState(file);
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
  /**
   * ★ `dryRun` 时必须**一个字节都不落盘**。（2026-09-22 加的，代价是一次实测）
   *
   * 原先这里无条件 `saveState(state)`，而 `--selftest` 的两个用例
   * （「单飞」「两把锁互相独立」）走的正是这条 `checkNow({ force: true, run: 假的 })`。
   * 于是**跑一次自证就改了真状态**，实测读数：
   *
   * ```
   * before.lastRunAt = 2026-09-22T06:12:23.208Z   ← 真的那次检查
   * after .lastRunAt = 2026-09-22T06:12:57.104Z   ← 自证写的
   * after .lastState = ok                          ← 原来是 drift 也会被抹成 ok
   * ```
   *
   * 两个后果都对外：
   * ① `lastRunAt` 被顶到现在 → **30 分钟冷却被一次自证用掉**，这半小时里真出现漂移
   *    会被 `skipped` 掉，群里什么都不会收到；
   * ② `lastState` 被抹成 `ok` → 「上一次是红的/未测」这条记忆没了，
   *    真恢复时那句「✅ 已恢复」也不会发。
   *
   * 而 `AGENTS.md` §2.1 的表里**正把 `--selftest` 列为应该常跑的自证命令** ——
   * 也就是：照着文档做，就会把告警静音半小时。
   * 判据（§2.4）：写进文档的每条命令，都要能指出它会不会改状态；指不出来就别写。
   */
  if (!dryRun) saveState(state, file);
  return { code, note, say, why, reason, out, ...(dryRun ? { dryRun: '注入/自证 —— 未落状态' } : {}) };
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
  const struct = now.structErrors ?? [];
  const st = { ...pick(prev, KEEP_PENDING), p_lastRunAt: new Date().toISOString(), p_lastDay: day, p_lastCode: code, p_rawCode: now.code };

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
        // 同时坏了的时候也要说 —— 不然「到期那批」看着完整，其实清单可能还漏了别的条目
        struct.length ? `⚠️ 另外，这份清单本身还有 ${struct.length} 处结构错误（下面那条到期明细未必是全的）。` : null,
        `清单在 \`PMO/待收清单-v1.json\`；收到之后把那条改成 done 并记完成依据，我就不会再提。`,
      ].filter(Boolean).join('\n'),
    };
  }

  /**
   * ★ **退 1 但明细为空 = 清单自己坏了，不是「没有到期」。**（2026-09-22 修）
   *
   * `tools/verify_pending.py:275` 是 `code = 1 if (struct or od) else 0` ——
   * **退 1 有两个来源**，到期明细（`od`）只是其中一个。另一个是结构错误
   * （id 重复 / 缺原话 / 指针指不到上游原话…）。
   *
   * 修之前这里**没有这一支**，于是「清单坏了」一路落到末尾的绿分支：状态记 `ok`、
   * 不发言；如果上一次是 `due`/`untested`，群里还会收到一句
   * **「✅ 待收清单：现在没有到期未收。」** —— 那是一句对外假话。
   *
   * 为什么基线那条链路没这个问题：`runCheckNow` 早就有兜底
   * （`code === 1 && !now.drifted.length` 时造一条占位漂移，「宁可说，不可沉默」）。
   * 待收这条**不对称地少了一半** —— 同一个病在同一份文件里活了两个版本。
   */
  if (code === 1) {
    if (prev.p_saidBrokenDay === day) {
      return { state: { ...st, p_lastState: 'broken' }, say: null, why: '今天的「清单坏了」已经说过一次' };
    }
    return {
      state: { ...st, p_lastState: 'broken', p_saidBrokenDay: day },
      why: `退 1 但到期明细为空 —— 清单结构有 ${struct.length} 处错误`,
      say: [
        `⏳ **待收清单这次读出来是坏的** —— 退 1，但**一条到期明细都没给出**。`,
        ...struct.slice(0, 5).map((s) => `· ${s}`),
        struct.length > 5 ? `· …另有 ${struct.length - 5} 处，见 \`python3 tools/verify_pending.py\`` : null,
        `这不是「没有到期未收」，是**「这份清单现在不可信」** —— 它可能漏掉了已经到期的条目。`,
        `清单在 \`PMO/待收清单-v1.json\`；修好之后我会再核一次。`,
      ].filter(Boolean).join('\n'),
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

  // 退 0：到这里**才**能说这句「没有到期未收」——
  // 上面两支（到期 / 清单坏了 / 未测）都到不了这里，所以这句话不会被拿去冒充别的结论。
  if (prev.p_lastState === 'due' || prev.p_lastState === 'untested' || prev.p_lastState === 'broken') {
    return {
      // ★ 两个去重键都要清：`p_saidDueKey` 清了，`p_saidBrokenDay` 也必须清 ——
      //   否则「坏了 → 修好 → 当天又坏了」会因为是同一天而被吞掉，
      //   而这次坏是**修好之后新发生的**，不是「今天已经说过的那一次」。
      state: { ...st, p_lastState: 'ok', p_saidDueKey: null, p_saidBrokenDay: null },
      why: '从到期/未测/清单坏了 恢复 —— 群里之前看到过异常，得看到它结束',
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
    // ★ 结构错误要一起带下去：`verify_pending.py` 的退 1 **有两个来源**（`struct or od`），
    //   只带 `overdue` 的话，「清单坏了但一条到期都没有」在状态机眼里和「没有问题」一样。
    structErrors: data?.struct_errors ?? [],
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
    /* ── ★ 状态键白名单：两边的键不许互相串（2026-09-22；原先这条断言把病当成了正确）── */
    ['★ 待收状态**不许**带上基线那套键',
      // 这条**原来是反的**：它断言 `s.lastState === 'ok' && s.saidDriftFp === 'x'`，
      // 也就是「待收的状态里应当保留基线那两个键」。那是 `{ ...prev }` 的产物，
      // 而正是这个展开让基线文件里那 5 个 `p_*` 键活了两个版本。
      // 断言把污染写成了期望 —— 它是绿的，病就在它下面。
      () => { const s = enterPending({ lastState: 'ok', saidDriftFp: 'x' }, pdue(1)).state;
              return s.lastState === undefined && s.saidDriftFp === undefined && s.p_lastState === 'due'; }],
    ['★ 基线状态**不许**带 `p_*` 与 `lastChatId`（现场：基线文件里 `p_lastDay` 停在 09-21，待收那份是 09-22）',
      () => { const s = enter({ lastState: 'ok', p_lastDay: '2026-09-21', lastChatId: 'oc_x', saidDriftFp: null },
                              { code: 0, day: D, drifted: [], untested: [] }).state;
              return !Object.keys(s).some((k) => k.startsWith('p_') || k === 'lastChatId'); }],
    ['反向对照：喂一批白名单外的键 → 一个都不许留下（上面两条不是恒真）',
      () => { const s = enterPending({ p_lastState: 'ok', 陈年残留: 1, lastCode: 7 }, { code: 0, day: D, overdue: [] }).state;
              return !('陈年残留' in s) && !('lastCode' in s) && s.p_lastState === 'ok'; }],

    /* ── ★ 退 1 但明细为空 = 清单坏了（2026-09-22 修；此前它会掉进绿分支）── */
    ['★ 待收：退 1 但**明细为空**（清单自己结构坏了）→ 必须说，不许沉默',
      () => { const r = enterPending({ p_lastState: 'ok' }, { code: 1, day: D, overdue: [], structErrors: ['id 重复：P-03'] });
              return typeof r.say === 'string' && r.state.p_lastState === 'broken'; }],
    ['★ 待收：清单坏了**不许**说成「没有到期未收」（修之前群里收到的就是这句）',
      // 两个形状都要挡住：
      //   ① `p_lastState: 'ok'` 时修前是**沉默**（`say === null`，stripNegated 之后是空串，
      //      光看「不许出现那句话」会**误判成通过** —— 沉默也是一种撒谎）；
      //   ② `p_lastState: 'due'` 时修前会真的发出「✅ 待收清单：现在没有到期未收。」
      () => { const broken = (prev) => enterPending(prev, { code: 1, day: D, overdue: [], structErrors: ['x'] });
              const a = broken({ p_lastState: 'ok' }), b = broken({ p_lastState: 'due' });
              return typeof a.say === 'string'
                  && !/没有到期未收/.test(stripNegated(a.say))
                  && !/没有到期未收/.test(stripNegated(b.say)); }],
    ['待收：清单坏了要把结构错误打出来（否则读者不知道该修什么）',
      () => /id 重复：P-03/.test(enterPending({}, { code: 1, day: D, overdue: [], structErrors: ['id 重复：P-03'] }).say)],
    ['待收：同一天第二次「清单坏了」→ 闭嘴；第二天仍坏 → **再说**',
      () => enterPending({ p_lastState: 'broken', p_saidBrokenDay: D }, { code: 1, day: D, overdue: [], structErrors: ['x'] }).say === null
         && typeof enterPending({ p_lastState: 'broken', p_saidBrokenDay: '2026-09-20' },
                                { code: 1, day: D, overdue: [], structErrors: ['x'] }).say === 'string'],
    ['待收：从「清单坏了」回到绿 → **必须说**（群里看到过异常，得看到它结束）',
      () => { const r = enterPending({ p_lastState: 'broken' }, { code: 0, day: D, overdue: [] });
              return typeof r.say === 'string' && /没有到期未收/.test(r.say); }],
    ['反向对照：退 1 **有**明细时仍走「到期」那条，别被 broken 分支抢走',
      () => enterPending({ p_lastState: 'ok' }, pdue(1)).state.p_lastState === 'due'],
    ['反向对照：绿（退 0）时**不许**误报「清单坏了」',
      () => enterPending({ p_lastState: 'ok' }, { code: 0, day: D, overdue: [] }).state.p_lastState === 'ok'],
    ['反向对照：从 broken 恢复之后，去重键要清掉（否则「坏了→修好→当天又坏」会被吞掉）',
      () => !enterPending({ p_lastState: 'broken', p_saidBrokenDay: '2026-09-20' }, { code: 0, day: D, overdue: [] })
              .state.p_saidBrokenDay],
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
        const first = checkNow({ force: true, dryRun: true, run: slow });
        const second = await checkNow({ force: true, dryRun: true, run: slow });
        release(); await first;
        return typeof second.skipped === 'string';
      }],
    ['★ 两把锁**互相独立**：待收在跑，不许挡住基线（否则一个卡住会拖停另一个）',
      async () => {
        let release; const gate = new Promise((r) => { release = r; });
        const slowP = async () => { await gate; return { code: 0, note: '', data: { overdue: [] } }; };
        const p = checkPending({ force: true, today: '2026-10-03', run: slowP });
        const b = await checkNow({ force: true, dryRun: true, run: async () => ({ code: 0, out: '', note: '' }) });
        release(); await p;
        return b === undefined || typeof b.skipped !== 'string' || !/待收/.test(b.skipped);
      }],

    /* ── ★ 自证不许改真状态（2026-09-22 实测：跑一次 --selftest 就把 30 分钟冷却用掉了）── */
    ['★ `dryRun` 下 checkNow 一个字节都不许落盘（否则跑一次自证 = 告警静音 30 分钟 + 擦掉「上次是红的」）',
      async () => {
        const f = path.join(stateDir(), '_selftest-tmp-state.json');
        try {
          fs.writeFileSync(f, JSON.stringify({ lastRunAt: '2020-01-01T00:00:00.000Z', lastDay: '2020-01-01',
                                               lastState: 'drift', saidDriftFp: 'x' }));
          const before = fs.readFileSync(f, 'utf8');
          const r = await checkNow({ force: true, dryRun: true, stateFile: f,
                                     run: async () => ({ code: 0, out: '', note: '' }) });
          return fs.readFileSync(f, 'utf8') === before && r.dryRun !== undefined;
        } finally { try { fs.unlinkSync(f); } catch { /* 已经没了就算了 */ } }
      }],
    ['反向对照：**不带** `dryRun` 时必须落盘，且真的把状态改掉（上面那条不是恒真）',
      async () => {
        const f = path.join(stateDir(), '_selftest-tmp-state.json');
        try {
          fs.writeFileSync(f, JSON.stringify({ lastRunAt: '2020-01-01T00:00:00.000Z', lastDay: '2020-01-01',
                                               lastState: 'drift', saidDriftFp: 'x' }));
          const before = fs.readFileSync(f, 'utf8');
          await checkNow({ force: true, stateFile: f, run: async () => ({ code: 0, out: '', note: '' }) });
          const after = fs.readFileSync(f, 'utf8');
          return after !== before && JSON.parse(after).lastState === 'ok';
        } finally { try { fs.unlinkSync(f); } catch { /* 已经没了就算了 */ } }
      }],
    ['★ 自证里的每一个 `checkNow` 都不许落到**真状态文件**上（`dryRun` 或 `stateFile` 二选一）',
      /**
       * 这条断言**写了三版，前两版都是错的**，两版错在同一个病上：**判据比它声称的弱。**
       *
       * 第一版比的是两个「文本出现过」的计数。实测：把某一处 `dryRun: true` 删掉，
       * **它照样全绿** —— 因为那个字面量在这段源码里到处都是（连判据自己的正则里都有一次）。
       * 一个「名字出现过」的判据，在有注释、有台账、有自指正则的地方**恒真**。
       *
       * 第二版要求**每一个**调用点都带 `dryRun: true` —— 而下面那条反向对照
       * （「不带 dryRun 时必须落盘」）本来就是故意不带的，于是真身直接变红。
       * **一个会误报的检查器比没有检查器更糟**（§2.1.1），它会让人开始不看报告。
       *
       * 第三版（现在这版）**在自己身上又撞了一次**：它把每个调用点的实参文本切出来判，
       * 而这段解释文字里就写着这个函数的调用形状（`checkNow` 后跟一对花括号），
       * 被自己的扫描器当成一个不合规的调用点 → 真身又红了。
       * 修法是给扫描器**统一**一条读法：**注释不算代码**（与 `verify_shouheng_ops.py`
       * 的 C5、`verify_cards.mjs` 的 J1a 同一条规矩），而不是把注释改写得更绕。
       *
       * 判据本身：每个真实调用点要么 `dryRun: true`、要么 `stateFile:` 指向注入的文件 ——
       * **没有第三条路能落到真文件上**。这是「到达」而不是「出现过」。
       * 截断（实参里嵌了 `}`）只会更严，不会更松。
       * 反向保证：`calls.length >= 2` —— 改名之后它会因为「一次都没匹配到」而红。
       */
      () => {
        const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
        const src = strip(selftest.toString());
        const calls = [...src.matchAll(/checkNow\(\{([^}]*)\}/g)].map((m) => m[1]);
        const dry = (a) => /dryRun:\s*true/.test(a);
        const inj = (a) => /stateFile:/.test(a);
        return calls.length >= 2
            && calls.every((a) => dry(a) || inj(a))
            && calls.some(dry) && calls.some(inj);
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
