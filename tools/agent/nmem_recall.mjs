/**
 * nmem_recall.mjs —— 从 Nowledge Mem 检索与本轮问题相关的持久记忆（决策 / 口径 / 避坑）。
 *
 * ★ 本文件**刻意不接线**。它只提供能力，调用点在 ws_daemon.mjs 里还是空的 ——
 *   接线要重启守衡，而重启窗口会吃掉群消息（AGENTS.md §2.7）。
 *
 * 纪律（每一条都有对应的测试）：
 *
 * 1. **永不阻塞主链路。** 默认 3 秒超时。超时、二进制缺失、JSON 坏掉、
 *    服务离线 —— 一律返回空串，不抛、不 await 到天荒地老。
 *    记忆是「如虎添翼」，绝不成为单点故障。这正是 SOP §五第 4 条「生命线原则」。
 * 2. **空串与「查到了但无关」长得一样，而两者都不该改变主流程。**
 *    所以返回值只有「一段可直接拼进 system prompt 的文本」或「空串」。
 *    调用方不需要判断成功与否 —— 没有失败这个分支。
 * 3. **只读。** 本模块不写任何东西，包括状态文件。
 * 4. **不读凭据。** 只调 nmem CLI，不碰 ~/.dsh / ~/.ssh 等（AGENTS.md §2.6 第 3 条）。
 * 5. **空间显式。** 永远带 --space，不依赖环境默认值 —— 否则会静默查到别的项目的记忆。
 */

import { spawn } from 'node:child_process';

const DEFAULT_SPACE = 'audit-multi-content';
const DEFAULT_TIMEOUT_MS = 3000;
const DEFAULT_LIMIT = 2;
const DEFAULT_MIN_SCORE = 0.5;

/** 可注入的依赖，测试用。生产调用不传第二个参数。 */
function deps(over = {}) {
  return {
    bin: process.env.NMEM_CLI_PATH || 'nmem',
    space: process.env.NMEM_SPACE || DEFAULT_SPACE,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    ...over,
  };
}

/**
 * 跑 nmem 并把 stdout 收齐；超时就 kill 并 reject。
 * 用 spawn 而不是 execSync：execSync 的超时**杀不掉子进程**，会留一个孤儿。
 *
 * ★ bin 必须**由调用方传进来**。第一版这里写的是 deps().bin —— 那是从环境变量
 *   重新推一遍，于是测试注入的 bin 被静默覆盖，`/nonexistent/a` 竟然调到了真 nmem
 *   并返回了记忆内容。依赖注入写成假的，测试就证不了任何失败路径（§2.4.1）。
 */
function runNmem(bin, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      reject(e);
      return;
    }
    let out = '';
    let err = '';
    let settled = false;
    const timer = setTimeout(() => {
      settled = true;
      try { child.kill('SIGKILL'); } catch { /* 已经退了就算了 */ }
      reject(new Error(`nmem 超时 ${timeoutMs}ms`));
    }, timeoutMs);

    child.stdout.on('data', (b) => { out += b.toString('utf8'); });
    child.stderr.on('data', (b) => { err += b.toString('utf8'); });
    child.on('error', (e) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(e);
    });
    child.on('close', (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(`nmem 退出码 ${code}: ${err.trim().slice(0, 200)}`));
        return;
      }
      resolve(out);
    });
  });
}

/** 从 nmem 的 JSON 里取出条目数组。字段名不猜 —— 两种都试（AGENTS.md §2.4.1）。 */
export function pickItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object') return [];
  for (const k of ['items', 'memories', 'results']) {
    if (Array.isArray(payload[k])) return payload[k];
  }
  return [];
}

/**
 * 把检索结果拼成一段可读文本。空结果返回 ''。
 * 纯函数 —— 这样它可以被单独测，不需要起进程。
 */
export function formatRecall(items, { minScore = DEFAULT_MIN_SCORE, limit = DEFAULT_LIMIT } = {}) {
  if (!Array.isArray(items) || items.length === 0) return '';
  const blocks = [];
  for (const m of items) {
    if (blocks.length >= limit) break;
    // ★ 字段名三套并存（REST 用 snake_case，插件用 camelCase），逐个试。
    const score = Number(m?.score ?? m?.similarity ?? 0) || 0;
    if (score < minScore) continue;
    const title = String(m?.title ?? '').trim();
    const content = String(m?.content ?? m?.snippet ?? m?.text ?? '').trim();
    if (!title || !content) continue;
    // 太长的条目截断 —— 它是提示词不是全文，塞爆上下文比不召回更糟。
    const body = content.length > 600 ? `${content.slice(0, 600)}…` : content;
    blocks.push(`- 【${title}】（匹配度 ${score.toFixed(2)}）\n  ${body.replace(/\n/g, '\n  ')}`);
  }
  if (blocks.length === 0) return '';
  return [
    '# 与本轮问题相关的持久记忆（核心口径 / 红线 / 避坑经验）',
    '以下是本仓库已沉淀的判据。**遇到冲突时以它们为准**，并在回答里说明你依据了哪一条。',
    '',
    ...blocks,
  ].join('\n');
}

/**
 * 主入口。成功返回一段文本，任何失败路径都返回 ''。
 *
 * @param {string} query  用户这一轮的问题
 * @param {object} opts   { limit, minScore, timeoutMs, space } —— 只在测试里传
 * @returns {Promise<string>}
 */
export async function recall(query, opts = {}) {
  const q = String(query ?? '').trim();
  if (!q) return '';

  const d = deps(opts);
  const limit = opts.limit ?? DEFAULT_LIMIT;
  const minScore = opts.minScore ?? DEFAULT_MIN_SCORE;
  const timeoutMs = opts.timeoutMs ?? d.timeoutMs;
  const space = opts.space ?? d.space;

  try {
    // 查询词限制长度：CLI 参数太长会被拒，而且长句反而检索不准。
    const stdout = await runNmem(
      d.bin,
      [
        '--json', 'memories', 'search', q.slice(0, 100),
        '--space', space,
        '-n', String(limit),
      ],
      timeoutMs,
    );
    const payload = JSON.parse(stdout);
    return formatRecall(pickItems(payload), { minScore, limit });
  } catch {
    // ★ 刻意吞掉一切：离线、超时、二进制不存在、JSON 坏、权限 —— 全落这里。
    //   不要在 catch 里再调任何东西（包括打日志到可能满的盘）。
    return '';
  }
}

export default { recall, formatRecall, pickItems };
