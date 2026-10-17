/**
 * tools.mjs —— 守衡的工具层
 *
 * 每个工具 = { schema, run, scope }。
 *   scope: 'read'  —— 只读，随时可调
 *          'write' —— 会对外产生副作用（发消息、改状态），需谨慎
 *
 * 设计取舍：先只给「读了能答得更好」的工具。写类工具（发消息、改文档）等业务场景
 * 明确后再放开 —— 一个会主动往群里发东西的智能体，权限必须一次一点地给。
 *
 * ★ 2026-09-22 第一次放开（委托方决定）：新增**多维表格写工具**（建表 / 改字段 /
 *   删记录），实现在 ./lark_write.mjs。触发它的是一件具体的事：
 *   李倩怡 16:02 给了落点与口径、16:06 开了编辑权限并说「请写入」，而守衡
 *   16:04 / 16:06 两次在群里答「我做不到」—— 那句对**这个文件**是真的
 *   （当时 11 个工具全是 scope:'read'），但它听起来像「飞书没给权限」，
 *   于是委托方去查控制台。真正该放开的东西一直在这张表里，不在飞书那侧。
 *
 *   ⚠️ `scope` 这个字段**只是标注，不是闸门** —— 它被 `toolNames()` 拼进
 *   系统提示的工具横幅给模型看，全仓没有任何一行拿它做准入判断。
 *   真正的执行点在 lark_write.mjs 的三条纪律：**留痕 / 回读 / 删除前快照**
 *   （每条在 lark_write.test.mjs 里都有能红的断言）。
 *   别把 `scope: 'write'` 当成「挡得住」—— 它挡不住任何东西。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { REPO_ROOT } from './config.mjs';
import { beijingDateTime } from './timefmt.mjs';
import * as feishu from './feishu.mjs';
import * as lw from './lark_write.mjs';

const execFileP = promisify(execFile);

/** 运行期上下文：由 agent 在处理每条消息时注入，工具通过它感知「现在在哪个群、谁在说话」 */
export const runtimeContext = { chatId: null, chatType: null, senderName: null, senderOpenId: null, messageId: null };

const defs = [];
const register = (name, def) => defs.push({ name, ...def });

/* ─────────────────────────── 只读工具 ─────────────────────────── */

register('now', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'now',
      description: '获取当前日期时间（北京时间）与星期。涉及「今天」「昨天」「还有几天」这类计算时必须先调用。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => {
    // 实现在 timefmt.mjs，与 recent_messages 共用同一份 —— 时间基准只要有两份实现，
    // 就一定会漂移（曾经就是 `now` 给北京时间、`recent_messages` 给 UTC，
    // 导致守衡在群里把 11:12 说成 23:12）。
    return beijingDateTime(new Date());
  },
});

register('current_chat_info', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'current_chat_info',
      description: '获取当前所在会话的信息：群名称、群描述、成员数，以及正在跟你说话的人是谁。不确定自己在哪个群、对方是谁时调用。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => {
    const { chatId, chatType, senderName, senderOpenId } = runtimeContext;
    if (!chatId) return { error: '当前没有会话上下文' };
    const info = chatType === 'p2p' ? { name: '（私聊）' } : await feishu.getChatInfo(chatId);
    return {
      chat_type: chatType === 'p2p' ? '私聊' : '群聊',
      chat_id: chatId,
      chat_name: info?.name ?? null,
      chat_description: info?.description ?? null,
      member_count: info?.memberCount ?? null,
      you_are_talking_to: senderName ?? '(未知)',
      their_open_id: senderOpenId ?? null,
      ...(info?.error ? { error: info.error } : {}),
    };
  },
});

register('list_chat_members', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'list_chat_members',
      description: '列出当前群/会话的成员。需要知道群里有哪些人时调用。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => {
    const { chatId } = runtimeContext;
    if (!chatId) return { error: '当前没有会话上下文' };
    const m = await feishu.listMembers(chatId);
    if (m?.error) return m;
    return { count: m.length, members: m };
  },
});

register('recent_messages', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'recent_messages',
      description: '读取当前群/会话最近的聊天记录，每条带「谁发的」和北京时间。对方提到「刚才」「上面说的」而你不清楚指什么时调用。注意三点：(1) 这里读到的历史包含你自己发过的消息；(2) 最多只能看到最近 50 条，更早的看不到，返回里的 window 字段会告诉你有没有顶到上限；(3) 被撤回的消息只有时间没有内容，撤回了就取不回原文。',
      parameters: {
        type: 'object',
        properties: { limit: { type: 'integer', description: '要读多少条，默认 20，最多 50' } },
        required: [],
      },
    },
  },
  run: async ({ limit = 20 } = {}) => {
    const { chatId } = runtimeContext;
    if (!chatId) return { error: '当前没有会话上下文' };
    const n = Math.max(1, Math.min(50, Number(limit) || 20));
    const msgs = await feishu.listRecentMessages(chatId, n);
    if (msgs?.error) return msgs;
    return {
      count: msgs.length,
      // 窗口边界由 feishu 层给出，不在这里重算 —— 边界是事实，不是推断。
      // 有了它，守衡说「第一次」时才知道自己说的是「本窗口内的第一次」。
      window: msgs.window,
      messages: msgs.map((m) => ({
        at: m.at,
        // 用 feishu 解析好的发送者。原来这里写死 `'用户'`，把接口本来给出的
        // sender.id 丢掉了 —— 守衡于是一致地说「我分辨不出哪条是谁发的」，
        // 而数据一直都在。不要把「有身份的信息」压成「无身份的占位符」。
        from: m.from,
        senderOpenId: m.senderOpenId ?? undefined,
        // 撤回的消息正文取不回，单独标出来。不然它和「一条短消息」长得一样。
        ...(m.recalled ? { recalled: true } : {}),
        text: m.text?.slice(0, 500),
      })),
    };
  },
});

register('lookup_user', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'lookup_user',
      description: '用 open_id 查这个人的显示名。优先在当前群成员里找，找不到才查通讯录。',
      parameters: {
        type: 'object',
        properties: { open_id: { type: 'string', description: '用户的 open_id，形如 ou_xxx' } },
        required: ['open_id'],
      },
    },
  },
  run: async ({ open_id }) => {
    // 带上当前群的 chatId：同群的人走群成员列表即可命中，不需要通讯录权限
    const chatId = runtimeContext.chatId ?? null;
    const { name, source, reason } = await feishu.getUserName(open_id, chatId);
    if (name) return { open_id, name, source };
    return {
      open_id,
      error: '查不到该用户的显示名',
      reason,
      hint: '如实说明你知道对方 open_id 但拿不到姓名，不要猜测或编造称呼。',
    };
  },
});

register('list_workspace', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'list_workspace',
      description: '列出守衡所在工作区的顶层目录与文件。对方问「你都能看到什么」「项目里有什么」时调用。' +
                   '★ 特别提醒：**上游飞书文档的逐字副本就在 `PRD/feishu/` 下**' +
                   '（`内容审查Agent-PRD-v1.0.md`、`美国市场内容治理项目-一页纸计划书.md`、`索引-v1.json`）。' +
                   '别人发来一个飞书文档链接时，先 `list_files` / `search_workspace` 在工作区里找它的副本，' +
                   '**再**决定要不要说「读不到」。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => {
    const entries = fs.readdirSync(REPO_ROOT, { withFileTypes: true })
      .filter((e) => !e.name.startsWith('.'))
      .map((e) => ({ name: e.name, type: e.isDirectory() ? 'dir' : 'file' }));
    return { root: REPO_ROOT, entries };
  },
});

register('read_text_file', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'read_text_file',
      description: '读取工作区内一个文本文件的内容。路径必须是工作区内的相对路径。文件很长时只返回开头部分。',
      parameters: {
        type: 'object',
        properties: {
          rel_path: { type: 'string', description: '相对工作区根目录的路径，例如 PMO/守衡-链路打通确认.md' },
          max_bytes: { type: 'integer', description: '最多读多少字节，默认 20000' },
        },
        required: ['rel_path'],
      },
    },
  },
  run: async ({ rel_path, max_bytes = 20000 }) => {
    const abs = path.resolve(REPO_ROOT, rel_path);
    // 路径逃逸防护：解析后必须仍在工作区内
    if (!abs.startsWith(REPO_ROOT + path.sep) && abs !== REPO_ROOT) {
      return { error: `拒绝访问工作区之外的路径：${rel_path}` };
    }
    if (!fs.existsSync(abs)) return { error: `文件不存在：${rel_path}` };
    const st = fs.statSync(abs);
    if (st.isDirectory()) return { error: `${rel_path} 是目录，不是文件` };
    const cap = Math.max(100, Math.min(200_000, Number(max_bytes) || 20000));
    const buf = fs.readFileSync(abs);
    const slice = buf.subarray(0, cap).toString('utf8');
    return { rel_path, bytes: st.size, truncated: st.size > cap, content: slice };
  },
});

register('list_files', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'list_files',
      description: '按文件名模式在指定目录下查找文件（大小写不敏感的模糊匹配）。想找某个文件但不确定路径时用。',
      parameters: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: '文件名包含的关键词，例如 "审核" 或 ".md"' },
          sub_dir: { type: 'string', description: '在哪个子目录里找，默认整个工作区' },
          limit: { type: 'integer', description: '最多返回多少条，默认 40' },
        },
        required: ['pattern'],
      },
    },
  },
  run: async ({ pattern, sub_dir = '', limit = 40 }) => {
    const base = sub_dir ? path.resolve(REPO_ROOT, sub_dir) : REPO_ROOT;
    if (!base.startsWith(REPO_ROOT)) return { error: '拒绝访问工作区之外的路径' };
    const needle = String(pattern).toLowerCase();
    const hits = [];
    const walk = (dir, depth) => {
      if (depth > 6 || hits.length >= limit) return;
      let ents = [];
      try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
      for (const e of ents) {
        if (hits.length >= limit) return;
        if (e.name.startsWith('.') || e.name === 'node_modules') continue;
        const full = path.join(dir, e.name);
        if (e.isDirectory()) walk(full, depth + 1);
        else if (e.name.toLowerCase().includes(needle)) hits.push(path.relative(REPO_ROOT, full));
      }
    };
    walk(base, 0);
    return { pattern, matches: hits.length, files: hits };
  },
});

/* ── 全工作区文本检索：它存在的理由就是「给得出分母」 ─────────────────────────
 *
 * 它替掉的是 `grep -rl <词> .` 那条路（2026-09-22 事故，见下一段注释）。三点不同，
 * 每一点都对应一次真实误判：
 *   ① **在 Node 里走 fs，不起子进程** —— 没有 15 秒超时，也就没有被杀掉之后
 *      留下一片空白、被读成「没命中」的可能；
 *   ② **报分母**：`searched_files` / `skipped` / `stopped_early` 必须一起看 ——
 *      「0 命中」只有在 `stopped_early === false` 且 `searched_files > 0` 时才成立
 *      （AGENTS.md §2.4.1：否定结论的输入不能只是「我采的那条通道里没有」）；
 *   ③ 自己剪枝 node_modules / .git / skills 这些大目录，不靠调用方记得。
 */

const SEARCH_SKIP_DIRS = new Set([
  'node_modules', '.git', '.ua', '.vendor', 'dist', 'build', 'skills', '__pycache__',
]);
const SEARCH_TEXT_EXT = new Set([
  '.md', '.json', '.jsonl', '.mjs', '.js', '.ts', '.py', '.sh', '.txt',
  '.csv', '.yml', '.yaml', '.toml', '.plist', '.html', '.css', '.log',
]);

register('search_workspace', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'search_workspace',
      description: '在守衡的工作区里做**全文检索**（不联网、不起子进程、自己剪掉大目录）。' +
                   '想问「某个词/某个 token 在不在工作区里」时用这个，**不要用 `grep -r` 扫全仓**。\n\n' +
                   '★ 返回值必须连着三个数一起读：`searched_files`（真扫了几个文件）、' +
                   '`skipped`、`stopped_early`。**只有当 `stopped_early === false` 且 ' +
                   '`searched_files > 0` 时，「0 命中」才是一句能说的话**；' +
                   '否则那是「未测」，不许说成「没有」。',
      parameters: {
        type: 'object',
        properties: {
          keyword: { type: 'string', description: '要找的文字，区分大小写，按原样子串匹配' },
          sub_dir: { type: 'string', description: '只在哪个子目录里找，例如 PRD 或 PMO；默认整个工作区' },
          limit: { type: 'integer', description: '最多返回多少个命中文件，默认 30' },
          max_files: { type: 'integer', description: '最多扫多少个文件，默认 5000。到顶会明说「没扫完」（不是「没找到」）' },
        },
        required: ['keyword'],
      },
    },
  },
  run: async ({ keyword, sub_dir = '', limit = 30, max_files = 5000 }) => {
    const kw = String(keyword ?? '');
    if (!kw) {
      return { keyword: kw, status: 'untested',
               note: '没给关键词 —— 未测，不是「没有」。' };
    }
    const base = sub_dir ? path.resolve(REPO_ROOT, sub_dir) : REPO_ROOT;
    if (base !== REPO_ROOT && !base.startsWith(REPO_ROOT + path.sep)) {
      return { keyword: kw, status: 'rejected', note: '拒绝访问工作区之外的路径（未测）。' };
    }
    const MAX_FILES = Math.max(1, Math.min(20000, Number(max_files) || 5000));
    const MAX_FILE_BYTES = 2_000_000;
    let searched = 0, skipped = 0, bytes = 0, stoppedEarly = false, matchesCapped = false;
    const hits = [];

    const walk = (dir, depth) => {
      if (stoppedEarly || depth > 8) return;
      let ents = [];
      try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { skipped++; return; }
      for (const e of ents) {
        if (stoppedEarly) return;
        const full = path.join(dir, e.name);
        if (e.isDirectory()) {
          if (e.name.startsWith('.') || SEARCH_SKIP_DIRS.has(e.name)) { skipped++; continue; }
          walk(full, depth + 1);
          continue;
        }
        if (!e.isFile() || !SEARCH_TEXT_EXT.has(path.extname(e.name).toLowerCase())) { skipped++; continue; }
        if (searched >= MAX_FILES) { stoppedEarly = true; return; }
        let st, text;
        try {
          st = fs.statSync(full);
          if (st.size > MAX_FILE_BYTES) { skipped++; continue; }
          text = fs.readFileSync(full, 'utf8');
        } catch { skipped++; continue; }
        if (text.includes('\u0000')) { skipped++; continue; }   // 其实是二进制
        searched++; bytes += st.size;
        if (!text.includes(kw)) continue;
        const lines = [];
        text.split('\n').forEach((ln, i) => {
          if (lines.length < 3 && ln.includes(kw)) lines.push({ line: i + 1, text: ln.trim().slice(0, 200) });
        });
        if (hits.length < limit) hits.push({ file: path.relative(REPO_ROOT, full), lines });
        else matchesCapped = true;
      }
    };
    walk(base, 0);

    const denom = `已扫 ${searched} 个文件、跳过 ${skipped} 个（大目录 / 二进制 / 超大文件）`;
    return {
      keyword: kw, status: 'ok',
      searched_files: searched, skipped, bytes_scanned: bytes,
      stopped_early: stoppedEarly, matches_capped: matchesCapped,
      matches: hits.length, files: hits,
      note: stoppedEarly
        ? `⚠️ 这次**没扫完**（到 ${MAX_FILES} 个文件上限就停了，还有没走到的地方）：${denom}。`
          + `所以「没找到」在这半张图上不成立 —— 这是**未测**，不许说成「0 命中」。`
          + `换一个更小的 sub_dir 重试。`
        : `${denom}。`
          + (hits.length === 0
              ? '**0 命中 —— 这一句现在有分母撑着**（范围走完了，不是被截断的）。'
              : `命中 ${hits.length} 个文件${matchesCapped ? '（只列了前若干个，实际不止）' : ''}。`),
    };
  },
});

/* ── 只读 shell：状态的措辞是硬的，别改回去 ─────────────────────────────────
 *
 * ★ 2026-09-22 事故（这一整段的结构就是为它改的）：
 *   守衡执行 `grep -rl NB55wAq8liEOdKkquL2cgtPEnmg .` —— 全仓递归，含 node_modules/、
 *   .git/、skills/ 下 777 个压缩包，**15 秒被 timeout 杀掉**。它拿到的返回体是：
 *       { error: "Command failed: bash -lc grep -rl ...", stdout: "" }
 *   **error 字段是满的，它只读了 stdout 是空的**，于是说「我用这个 token 在整个工作区
 *   搜了一遍，0 命中」—— 而那个 token 就在工作区两个文件里（`PRD/feishu/索引-v1.json`、
 *   `PRD/PRD差异对照-20260921.md`）。
 *
 *   形状与 AGENTS.md §2.2 第 5 条（macOS 没有 `timeout`，空输出 + rc=127 被读成
 *   「0 命中」）**完全相同**，只是机制从「命令不存在」换成了「命令被超时杀掉」。
 *
 * ★ 契约（三条缺一不可）：
 *   ① 每次返回都带 `status`：`ok` / `rejected` / `timeout` / `failed`；
 *   ② **status !== 'ok' 时，返回体里根本没有 `stdout` 这个键** ——
 *      没有空字符串可读，就不可能被读成「扫完了、没命中」；
 *   ③ status !== 'ok' 时带 `note`，把「未测」两个字直接写出来。
 *   ④ 病态的递归扫描**在跑之前**就被挡掉（`scanGuard`）——
 *      把超时标成「未测」只是止血，**这条命令本来就不该跑**。
 */

/** 递归扫描的目标里出现这些，就是「会扫穿整个仓库」 */
const HEAVY_TARGET = /^(\.|\.\/|\/|node_modules|\.git|skills|\.ua|dist|build|\.vendor)(\/|$)/;

/**
 * 递归扫描护栏 → 返回拒绝理由，或 null 表示放行。
 *
 * 判据**只看目标**，不看 `--include`：`--include` 过滤的是文件，不剪枝目录遍历，
 * 所以 `grep -rn X --include=*.md .` 一样会扫穿 node_modules。
 */
/* ─────────────────── 凭据路径：一律不许读 ─────────────────── */

/**
 * ★ 2026-09-22 加。**它堵的是一个已经被说出口的能力边界。**
 *
 * 起因：守衡自己对外承认过一句话 ——
 *   「我读得到那个凭据文件但不输出其内容 —— **这是策略边界，不是能力边界**。」
 * 那句话是诚实的，也正是问题：`run_readonly_command` 的白名单放行 `cat`，
 * 于是 `cat ~/.dsh/credentials/*.json` **没有任何一行代码在拦**，
 * 挡住它的只有模型的当场判断。§2.4 点名的那个病，长在凭据上。
 *
 * ── 为什么判据是「指得出对象的路径」，而不是模糊文件名匹配
 *
 * 第一版我打算写 `/(secret|token|credential|key)/i` 扫文件名。**实测否掉了**：
 * 仓里有一个 `research/governance/_evidence/R2/_tools/pylibs/pycparser/ply/ctokens.py` ——
 * 它含 `token`，但它是 pycparser 的词法表。一个会误报的检查器比没有检查器更糟
 * （§2.1.1），尤其当它拦的是守衡**自己证据层**里的文件。
 *
 * 所以名单是**逐个点名**的，每一条都指得出这台机器上的真实对象：
 *   `~/.dsh/credentials/shouheng-lark.json`            飞书应用密钥
 *   `~/.dsh/credentials/tencent-cloud-zhoujian-secretkey.csv`  腾讯云密钥
 *   `~/.dsh/.credentials.yaml`                         DSH 凭据
 *   `~/.ssh/`                                         私钥
 *
 * ── 一个必须写下来的**已知边界**（不许当成已经堵死）
 *
 * `read_text_file` / `list_files` / `search_workspace` 三个通道**已经**被
 * `REPO_ROOT` 前缀断言挡住了，而上面这些落点全在仓外 —— 所以真正需要这道闸门的
 * **只有 `run_readonly_command` 一条**。这个结论**不是读代码读出来的，是采出来的**：
 * `tools/agent/secret_path.test.mjs` 对四条通道各喂一个仓外凭据路径，
 * 断言**四条全部拒绝**（一条活着不给另一条作证 —— §2.4.1 第 4 行）。
 */
const HOME_DIR = os.homedir();

/** 不许进入的目录/文件（**逐个点名，不做模糊匹配**） */
const SECRET_PATHS = [
  path.join(HOME_DIR, '.dsh', 'credentials'),
  path.join(HOME_DIR, '.dsh', '.credentials.yaml'),
  path.join(HOME_DIR, '.ssh'),
  path.join(HOME_DIR, '.aws'),
  path.join(HOME_DIR, '.config', 'gh'),
];

/** 按**文件名**拦的（这些名字本身就是凭据，放哪都一样） */
const SECRET_BASENAMES = new Set([
  '.credentials.yaml', '.credentials.yml', '.env',
  '.netrc', '.git-credentials', '.npmrc', '.pypirc',
  'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
]);

/**
 * 一个 token 是不是指向凭据。命中返回「命中的那个对象」，否则 null。
 *
 * `$HOME` / 反引号 / `;` 这些在 `run_readonly_command` 里**已经被元字符检查挡掉**，
 * 所以这里只需要处理 `~`。通配符（`cred*`）取**第一颗 `*` 之前**那段当静态前缀，
 * 并要求「静态前缀与某个禁入目录**互为前缀**」—— 这样 `~/.dsh/cred*` 也会被拦。
 */
export function secretPathHit(token) {
  const raw = String(token ?? '').trim().replace(/^["']|["',]+$/g, '');
  if (!raw) return null;
  const expanded = raw.startsWith('~/') ? path.join(HOME_DIR, raw.slice(2))
    : raw === '~' ? HOME_DIR
    : raw;
  const globAt = expanded.search(/[*?[]/);
  const staticPart = globAt >= 0 ? expanded.slice(0, globAt) : expanded;
  const abs = path.resolve(REPO_ROOT, staticPart);
  for (const p of SECRET_PATHS) {
    const under = abs === p || abs.startsWith(p + path.sep);
    // 通配符那一侧：`staticPrefix*` 能匹配到的**任何**路径，都是 `startsWith(staticPart)` 的路径。
    // 所以「这颗通配符有没有可能落进禁入目录」= 「禁入目录是否以静态前缀开头」。
    // ★ 第一版我写成 `p.startsWith(abs + path.sep)`，**当场被 A7 抓到**：
    //   前缀 `…/.dsh/cred` 加一个斜杠就成了 `…/.dsh/cred/`，而 `credentials` 不以它开头 ——
    //   于是一个明明会被 glob 展开到凭据目录的写法被判成安全。**判据比要拦的东西弱了一格。**
    const couldGlobIn = globAt >= 0 && p.startsWith(abs);
    if (under || couldGlobIn) return `${p}${path.sep}`;
  }
  if (globAt < 0 && SECRET_BASENAMES.has(path.basename(abs))) return path.basename(abs);
  return null;
}

/** 扫整条命令的每个 token。命中就返回一句要发回去的拒绝话术。 */
function secretGuard(cmd) {
  for (const token of String(cmd ?? '').split(/\s+/)) {
    const hit = secretPathHit(token);
    if (hit) {
      return '🔒 已拒绝：这条命令指向**凭据文件**（' + hit + '）。\n'
        + '这是**策略边界**，不是「我读不到」—— 白名单主动挡住了它，所以本次结论是「未测」，'
        + '不是「文件不存在」，也不是「里面没有」。\n'
        + '要读的话走另一条路：把**非凭据**的内容放到工作区或飞书文档里。';
    }
  }
  return null;
}

function scanGuard(cmd) {
  const parts = cmd.split(/\s+/).filter(Boolean);
  const [bin, ...rest] = parts;
  const flags = rest.filter((p) => p.startsWith('-'));
  const bare = rest.filter((p) => !p.startsWith('-'));

  const isGrep = bin === 'grep' || bin === 'rg';
  const isFind = bin === 'find';
  const isLs = bin === 'ls';
  if (!isGrep && !isFind && !isLs) return null;

  const recursive = bin === 'rg' || isLs
    ? flags.some((f) => /^-[a-zA-Z]*[rR]/.test(f) || f === '--recursive')
    : flags.some((f) => /^-[a-zA-Z]*[rR]/.test(f) || f === '--recursive');
  const bounded = flags.some((f) => /^-maxdepth/.test(f));

  // grep/rg 的第一个非选项是 pattern，其余才是路径；find / ls 的非选项全是路径
  const targets = isGrep ? bare.slice(1) : bare;
  if (isLs && !recursive) return null;
  if (!recursive && !isFind) return null;

  const unbounded = targets.length === 0 || targets.some((t) => HEAVY_TARGET.test(t));
  if (!unbounded || bounded) return null;

  return '⚠️ 已拒绝：这条命令会递归整个工作区（含 node_modules/、.git/、'
       + 'skills/ 下 777 个压缩包），15 秒必然超时 —— **而超时后 stdout 是空的，'
       + '空输出不等于没命中。** 改用下面任一种（都能给得出「扫了多少」这个分母）：\n'
       + '  · `search_workspace` —— 专为「这段文字在不在工作区」造的，自己限范围、报分母；\n'
       + '  · 点名子目录：`grep -rn \'关键词\' PMO PRD tools research`；\n'
       + '  · `find <子目录> -maxdepth 3 -name \'*.md\'`。';
}

register('run_readonly_command', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'run_readonly_command',
      description: '在工作区执行一条**只读** shell 命令并返回输出（例如 git log、wc -l、grep 统计）。' +
                   '只允许白名单里的只读命令；任何写操作、删除、安装、网络请求都会被拒绝。\n\n' +
                   '★ 读返回值的规矩，别搞错：**只有 `status === "ok"` 且 `stdout` 为空，' +
                   '才是「命令跑完了、没有命中」。** 其它 status 下一律**没有 stdout 字段**，' +
                   '那是「我没测到」，不是「0 命中」—— 请照 `note` 里的提示换一条命令重试，' +
                   '**不要拿这个结果去下否定结论。**',
      parameters: {
        type: 'object',
        properties: { command: { type: 'string', description: '要执行的命令，例如 "git log --oneline -5"' } },
        required: ['command'],
      },
    },
  },
  run: async ({ command }) => {
    // 白名单：只读命令前缀。宁可少给，不要给错。
    const ALLOW = /^(git\s+(log|status|diff|show|branch|remote|tag)|ls|cat|head|tail|wc|grep|rg|find|file|stat|du|df|date|pwd|echo|node\s+--version|npm\s+ls|python3?\s+--version|python3?\s+tools\/lark_find\.py\s+(search|read|readdoc|tables|fields|records|wiki))\b/;
    const cmd = String(command ?? '').trim();
    if (!ALLOW.test(cmd)) {
      return { command: cmd, status: 'rejected',
               error: `命令不在只读白名单内，已拒绝：${cmd.slice(0, 80)}`,
               note: '白名单以外的东西我没有执行过 —— 所以对你问的事，'
                   + '这次的答案是「未测」，不是「没有」。' };
    }
    if (/[;&|><`$]/.test(cmd)) {
      return { command: cmd, status: 'rejected',
               error: '命令含管道/重定向/命令替换等元字符，已拒绝',
               note: '未执行 —— 这次的答案是「未测」。' };
    }
    const guard = scanGuard(cmd);
    if (guard) return { command: cmd, status: 'rejected', error: guard, note: guard };

    // ★ 凭据路径：**在 scanGuard 之后、execFile 之前**，而且与它分开写 ——
    //   两条规则拦的是完全不同的东西（一条怕超时，一条怕泄漏），混在一个函数里
    //   会让两边都难读，也会让「哪条规则红了」说不清。
    const secret = secretGuard(cmd);
    if (secret) return { command: cmd, status: 'rejected', error: secret, note: secret };

    // ★ 测试缝：超时那条路必须能被真跑一遍，否则它只是「构造上应该对」。
    //   生产不设这个环境变量，就是 15 秒。
    const budget = Number(process.env.SHOUHENG_RO_TIMEOUT_MS) > 0
      ? Number(process.env.SHOUHENG_RO_TIMEOUT_MS) : 15_000;
    try {
      const { stdout, stderr } = await execFileP('bash', ['-lc', cmd],
        { cwd: REPO_ROOT, timeout: budget, maxBuffer: 1 << 20 });
      return { command: cmd, status: 'ok', stdout: stdout.slice(0, 8000), stderr: stderr.slice(0, 2000) };
    } catch (e) {
      // 超时被 SIGTERM 杀掉 / 输出超过 maxBuffer —— 两种都**没有**完整输出
      const killed = e?.killed === true || e?.signal != null;
      const overflow = e?.code === 'ERR_CHILD_PROCESS_STDIO_MAXBUFFER';
      const why = killed ? `命令在 ${Math.round(budget / 1000)} 秒内没跑完，已被杀掉`
                : overflow ? `命令输出超过 1MB 上限，已被截断`
                : `命令非零退出：${String(e?.message ?? e).slice(0, 300)}`;
      // ★ 故意**不带 stdout** —— 见本段顶部契约 ②
      return {
        command: cmd, status: killed ? 'timeout' : 'failed',
        error: why,
        bytes_captured: String(e?.stdout ?? '').length,
        note: `⚠️ 未测：${why}。**这次没有可用的输出，所以「有没有命中」我答不了 —— `
            + `这不是「0 命中」，也不是「没有」。** 请换一条范围更小的命令重试，`
            + `或改用 search_workspace（它会报扫了多少个文件）。`,
        stderr: String(e?.stderr ?? '').slice(0, 1500),
      };
    }
  },
});

/* ─────────────────────────── 内容合规判定（只读工具之一）─────────────────────────── */

const JUDGE_PY = path.join(REPO_ROOT, 'research', 'governance', 'skeleton', 'judge.py');

register('judge_copy', {
  // ★ scope 定为 read 的理由必须写下来，否则下一个人会以为是标错了：
  //   本工具不碰任何业务数据 —— 不改记录状态、不发消息、不写飞书。
  //   它唯一产生的持久副作用是往本地追加一条**回执**（append-only 的 jsonl），
  //   而那条回执是 ADR-0005 约束 5 强制要求的：「没有 receipt 的判定不算发生过」。
  //   所以「写回执」不是副作用，是这个工具的**定义的一部分**；关掉它，判定就不存在。
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'judge_copy',
      description:
        '对一段广告文案做内容合规判定。返回：判定档位、命中的规则编号、命中的**原文位置与片段**、' +
        '降级/放行证据、规则与词表版本、边界声明（这条判定判断不了什么）、以及处置层。\n' +
        '什么时候用：有人贴一段文案问「这个能不能发」「有没有问题」「判一下」。\n' +
        '★ 四条必须照实转述的限制，不要简化掉：\n' +
        '(1) 结论是**建议**，不是决定。工具只补证据，不替人过门 —— 你不能因为返回了 auto_pass 就说「已通过」。\n' +
        '(2) 返回 catch_all（零命中）**不等于合规**，含义是「规则库没有覆盖它」。必须转人工。\n' +
        '(3) 每次都读 boundary_statement.unknowns，那里写的是本判定的覆盖边界；' +
        '通常包含「不按品线过滤」「部分守卫词未接线」「只看文本不看图片视频」。\n' +
        '(4) 回执里的 `unconfirmed_notice` 不为 null 时**必须转述出去** —— 它说的是' +
        '「这次引用的外部标准还没经过法务确认，所以这是研究结论、不是法务裁定」。' +
        '62 条外部标准今天**全部**是研究稿，所以这句话现在每次都会出现；' +
        '省掉它，一次研究就会被读成一次法务裁定（Q22 要防的正是这个）。' +
        '回执里还带 `evidence_ref`（依据《外部标准库》第几条、可点开的链接）与 `ratified`。\n' +
        '每次调用都会留下一条回执（run_id），可以在返回里引用它。',
      parameters: {
        type: 'object',
        properties: {
          text: { type: 'string', description: '要判定的文案原文（Primary Text 与 Headline 拼起来即可）。必须逐字传入，不要改写或翻译。' },
          product_line: { type: 'string', description: '品线，例如「吸奶器」。注意：当前规则库没有品线字段，它只进回执，不改变判定。' },
          locale: { type: 'string', description: '文案语种代码，例如 en / zh / de / fr / es。非 en/zh 时工具会在边界声明里提示词表覆盖不均。' },
          platform: { type: 'string', description: '投放平台，例如 Meta / TikTok。' },
          ad_id: { type: 'string', description: '外部广告 ID（如果是在审某条已有记录）。' },
        },
        required: ['text'],
      },
    },
  },
  run: async ({ text, product_line, locale, platform, ad_id } = {}) => {
    const body = String(text ?? '');
    if (!body.trim()) return { error: '文案为空，无法判定' };
    const tmp = path.join(
      os.tmpdir(),
      `judge-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.txt`,
    );
    try {
      // 走临时文件而不是 --text：文案可能很长（落地页正文），也可能含引号与换行。
      // 走 argv 会同时碰到长度上限和转义问题，走文件两个都没有。
      fs.writeFileSync(tmp, body, 'utf8');
      const args = [JUDGE_PY, '--text-file', tmp, '--json', '--brief', '--receipt',
                    '--origin', 'shouheng'];
      if (product_line) args.push('--product-line', String(product_line));
      if (locale)       args.push('--locale', String(locale));
      if (platform)     args.push('--platform', String(platform));
      if (ad_id)        args.push('--ad-id', String(ad_id));
      const { stdout } = await execFileP('python3', args, {
        cwd: REPO_ROOT, timeout: 30_000, maxBuffer: 1 << 24,
      });
      const r = JSON.parse(stdout);
      // 引擎的硬断言（词表通道不变量 / 主题树漂移）失败时是 exit 2/3 且带 stderr，
      // 那种情况下 stdout 不是 JSON，上面的 JSON.parse 会抛，由 executeTool 兜住。
      return r;
    } catch (e) {
      const stderr = String(e.stderr ?? '').trim();
      return {
        error: `判定引擎执行失败：${e.message}`,
        ...(stderr ? { stderr: stderr.slice(0, 2000) } : {}),
        ...(e.code === 2 || e.code === 3
          ? { hint: '这是引擎的使用点硬断言（词表通道不变量 / 主题树校验）失败，不是你的输入问题。' +
                  '按 ADR-0008/0009，此时**本次评测结论不可用**，不要去猜判定结果。' }
          : {}),
      };
    } finally {
      try { fs.unlinkSync(tmp); } catch { /* 临时文件清理失败不该影响判定结果 */ }
    }
  },
});

/* ─────────────────── 多维表格：读（2026-09-22 加）─────────────────── */

/** app_token 从哪来 —— 每个写工具的 description 都要重复说一遍，因为这个参数
 *  是模型最容易编的东西（编出来的 token 会得到 404，而不是「你没权限」）。 */
const TOKEN_HINT =
  'app_token 从飞书链接里取：`https://xxx.feishu.cn/base/<app_token>?table=<table_id>`。' +
  '不确定有哪些 Base 时先调 lark_base_known。**不要凭印象编 token** —— 编出来的会 404。';

const TBL_HINT = 'table 可以给**表名**（如「规则库」），也可以给 table_id（tbl 开头）。给错名字会返回该 Base 里实际有哪些表。';

register('lark_base_known', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_known',
      description: '列出我们记录过的业务 Base（名称 + app_token + 用途）。对方只说「规则库」而没给链接时，先调这个。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => ({ bases: lw.KNOWN_BASES, note: '这里只有我们记过的。对方给了别的链接就用链接里的 token。' }),
});

register('lark_base_tables', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_tables',
      description: `列出某个 Base 里的所有数据表及各自的记录数。\n${TOKEN_HINT}`,
      parameters: { type: 'object', properties: { app_token: { type: 'string' } }, required: ['app_token'] },
    },
  },
  run: async ({ app_token }) => lw.listTables(app_token),
});

register('lark_base_fields', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_fields',
      description: `列出某张表的字段（列）定义：名称、类型、单选/多选的选项。\n写记录前**必须先看这个**，否则字段名对不上会静默写空。\n${TOKEN_HINT}\n${TBL_HINT}`,
      parameters: {
        type: 'object',
        properties: { app_token: { type: 'string' }, table: { type: 'string' } },
        required: ['app_token', 'table'],
      },
    },
  },
  run: async ({ app_token, table }) => lw.listFields(app_token, table),
});

register('lark_base_records', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_records',
      description: `读某张表的记录（默认 20 条，每次最多 500 条）。\n${TOKEN_HINT}\n${TBL_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          limit: { type: 'number', description: '要读多少条，默认 20，上限 500' },
          page_token: { type: 'string', description: '翻页游标（上一页返回的）' },
        },
        required: ['app_token', 'table'],
      },
    },
  },
  run: async ({ app_token, table, limit, page_token }) =>
    lw.listRecords(app_token, table, { limit, pageToken: page_token }),
});

/* ─────────────────── 多维表格：写（2026-09-22 委托方决定放开）─────────────────── */

/**
 * 写工具的 description 里有三段是**必须**转述的（写在这里、也在 lark_write.test.mjs 里断言过）：
 *   · 结果里有 readback 字段：consistent / mismatch / untested
 *   · **untested 和 mismatch 都不许说成「做好了」** —— 照实说「我没验成」
 *   · 结果里 record_ids 要留着，因为那是「下一步改哪条」的唯一凭据
 * 原因见 AGENTS.md §2.4.2：这个仓库今天刚发过一条把「字节变了」说成「上游改了」的假警报。
 */
const WRITE_HINT =
  '\n★ 返回值里一定有 `readback`：`consistent`（写进去并读回来比对一致）/ ' +
  '`mismatch`（读回来对不上）/ `untested`（回读失败，**没验成**）。\n' +
  '`mismatch` 和 `untested` **都不许说成「做好了」** —— 照实说哪一条没对上、或者"我没验成"。\n' +
  '返回值里还有 `ledger`（有没有留痕）与 `ledger_path`。留痕失败也要说出来。';

/**
 * 删除类工具的专用说明（2026-09-22 委托方定「两段式」后加）。
 * ★ 这里写的不是建议，是**代码已经这么做了**：`delete*` 三个函数在没带 `confirmed`
 *   时一律走 `proposeDelete()`，**一个删除请求都不发**。说明与行为的对应关系
 *   由 lark_write.test.mjs 的 D 段断言守着。
 */
const PROPOSE_HINT =
  '\n★ **它只提议、不执行。** 返回 `will`（一句人话，说明将要删掉什么）与 `pending: true`。\n' +
  '你要做的只有一件：**把 `will` 那句原样发出去**，然后等。\n' +
  '对方在**下一条消息**里明确确认之后，才调 `lark_base_confirm_delete`。\n' +
  '⚠️ 不要在同一次回答里既提议又确认 —— 确认只有在**另一条消息**里才算数，\n' +
  '同一条消息自我确认会被拒（`same_message`），而且那等于把两段式白做了。';

register('lark_base_create_table', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_create_table',
      description:
        '在 Base 里新建一张数据表。\n' +
        '★ 该 Base 里已有同名表时会**直接拒绝**（不会建出第二张同义表）—— 那是保护，不是错误。\n' +
        '字段类型 type 可以给数字也可以给中文名：文本 1 / 数字 2 / 单选 3 / 多选 4 / 日期 5 / ' +
        '复选框 7 / 人员 11 / 电话 13 / URL 15 / 附件 17 / 单向关联 18。' +
        '**类型不认识时会拒绝，不会默认成文本**（默认成文本的字段能建出来，但存进去的全变字符串，且没有任何东西会红）。\n' +
        `单选项用 options 传候选值数组。\n${TOKEN_HINT}${WRITE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' },
          name: { type: 'string', description: '新表的名字' },
          fields: {
            type: 'array',
            description: '字段定义数组',
            items: {
              type: 'object',
              properties: {
                name: { type: 'string' }, type: { type: ['string', 'number'] },
                options: { type: 'array', items: { type: 'string' }, description: '单选/多选的候选值' },
              },
              required: ['name', 'type'],
            },
          },
        },
        required: ['app_token', 'name', 'fields'],
      },
    },
  },
  run: async ({ app_token, name, fields }) => lw.createTable(runtimeContext, app_token, name, fields),
});

register('lark_base_create_field', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_create_field',
      description: `给已有的表加一列。类型取值同 lark_base_create_table。\n${TOKEN_HINT}\n${TBL_HINT}${WRITE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          field: {
            type: 'object',
            properties: {
              name: { type: 'string' }, type: { type: ['string', 'number'] },
              options: { type: 'array', items: { type: 'string' } },
            },
            required: ['name', 'type'],
          },
        },
        required: ['app_token', 'table', 'field'],
      },
    },
  },
  run: async ({ app_token, table, field }) => lw.createField(runtimeContext, app_token, table, field),
});

register('lark_base_update_field', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_update_field',
      description:
        '改一个已有字段（改名 / 改类型）。改之前旧定义会先落进留痕文件。\n' +
        '⚠️ 改类型可能让已有数据失配 —— 改完一定要看 readback。\n' +
        `\n${TOKEN_HINT}\n${TBL_HINT}${WRITE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          field_name: { type: 'string', description: '要改的字段现在的名字' },
          patch: {
            type: 'object',
            properties: { name: { type: 'string' }, type: { type: ['string', 'number'] } },
            description: '要改成什么；至少给一个',
          },
        },
        required: ['app_token', 'table', 'field_name', 'patch'],
      },
    },
  },
  run: async ({ app_token, table, field_name, patch }) =>
    lw.updateField(runtimeContext, app_token, table, field_name, patch),
});

register('lark_base_delete_field', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_delete_field',
      description:
        '**提议**删掉一列。★ 这个工具**不会真删** —— 它只把「要删哪一列、那列有多少条非空」摆出来，\n' +
        '并把这件事挂起等着。要把 `will` 那句话原样说给对方，等他**在另一条消息里**说确认，\n' +
        '再调 `lark_base_confirm_delete`。删列会连带那一列的全部数据。\n' +
        `${TOKEN_HINT}\n${TBL_HINT}${PROPOSE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          field_name: { type: 'string' },
        },
        required: ['app_token', 'table', 'field_name'],
      },
    },
  },
  run: async ({ app_token, table, field_name }) => lw.deleteField(runtimeContext, app_token, table, field_name),
});

register('lark_base_delete_table', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_delete_table',
      description:
        '**提议**删掉整张表。★ 这个工具**不会真删** —— 它只把「哪张表、几列、几条记录」摆出来并挂起等待。\n' +
        '要把 `will` 那句话原样说给对方，等他**在另一条消息里**说确认，再调 `lark_base_confirm_delete`。\n' +
        '真删之前会把「表 + 全部字段 + 最多 500 条记录」完整搬进留痕；搬不全就拒绝执行。\n' +
        `${TOKEN_HINT}\n${TBL_HINT}${PROPOSE_HINT}`,
      parameters: {
        type: 'object',
        properties: { app_token: { type: 'string' }, table: { type: 'string' } },
        required: ['app_token', 'table'],
      },
    },
  },
  run: async ({ app_token, table }) => lw.deleteTable(runtimeContext, app_token, table),
});

register('lark_base_create_records', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_create_records',
      description:
        '往表里批量新增记录。records 是**字段名 → 值**的对象数组，字段名必须和 lark_base_fields 返回的一致。\n' +
        '多选字段传字符串数组；日期传毫秒时间戳（数字）；URL 字段传 `{"link":"https://…","text":"显示文字"}`。\n' +
        '一次最多 500 条，超了会**拒绝**（不会静默截断 —— 截断会让人以为全写进去了）。\n' +
        '写完会按返回的 record_id 逐条读回来比对，`record_ids` 要留着（后面改哪条靠它）。\n' +
        `${TOKEN_HINT}\n${TBL_HINT}${WRITE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          records: { type: 'array', items: { type: 'object' }, description: '每条是 {字段名: 值}' },
        },
        required: ['app_token', 'table', 'records'],
      },
    },
  },
  run: async ({ app_token, table, records }) => lw.createRecords(runtimeContext, app_token, table, records),
});

register('lark_base_update_records', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_update_records',
      description:
        '批量改已有记录。每条要带 record_id（lark_base_records 或 create 的返回值里拿）。\n' +
        '改之前旧值会先落进留痕文件。一次最多 500 条。\n' +
        `${TOKEN_HINT}\n${TBL_HINT}${WRITE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          records: {
            type: 'array', items: { type: 'object' },
            description: '每条是 {record_id, fields:{字段名: 新值}}',
          },
        },
        required: ['app_token', 'table', 'records'],
      },
    },
  },
  run: async ({ app_token, table, records }) => lw.updateRecords(runtimeContext, app_token, table, records),
});

register('lark_base_delete_records', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_delete_records',
      description:
        '**提议**按 record_id 删记录。★ 这个工具**不会真删** —— 它只把「哪几条、那几条长什么样」摆出来并挂起等待。\n' +
        '要把 `will` 那句话原样说给对方，等他**在另一条消息里**说确认，再调 `lark_base_confirm_delete`。\n' +
        '真删之前会把这几条的完整内容先搬进留痕；读不回旧值、或读回条数对不上，一律拒绝执行。\n' +
        `${TOKEN_HINT}\n${TBL_HINT}${PROPOSE_HINT}`,
      parameters: {
        type: 'object',
        properties: {
          app_token: { type: 'string' }, table: { type: 'string' },
          record_ids: { type: 'array', items: { type: 'string' }, description: '要删的 record_id 列表' },
        },
        required: ['app_token', 'table', 'record_ids'],
      },
    },
  },
  run: async ({ app_token, table, record_ids }) => lw.deleteRecords(runtimeContext, app_token, table, record_ids),
});

/* ─────────────── 两段式第二步：确认 / 取消（2026-09-22 委托方定）─────────────── */

register('lark_base_confirm_delete', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_confirm_delete',
      description:
        '执行上一条**已提议**的删除。★ 只有在对方**在另一条消息里**明确说「确认 / 删吧 / 好」之后才调它。\n' +
        '三种情况会被拒，拒了就是没删：`no_pending`（没有待确认的）/ `expired`（提议过了 15 分钟）/\n' +
        '`same_message`（**在发起删除的那一条消息里自我确认** —— 那不算确认，重新等对方回一句）。\n' +
        '被拒时**不要换个说法再试**，把拒的理由告诉对方就行。\n' +
        '执行之后同样返回 `readback` 三态；`mismatch`/`untested` 不许说成「删好了」。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => lw.confirmDelete(runtimeContext),
});

register('lark_base_cancel_delete', {
  scope: 'write',
  schema: {
    type: 'function',
    function: {
      name: 'lark_base_cancel_delete',
      description:
        '取消上一条已提议但还没确认的删除（对方说「算了 / 不用了 / 先别删」时用；同一条消息里也可以取消）。\n' +
        '返回 `cancelled: true` 与 `what`（被取消的是哪一件事）。',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  run: async () => lw.cancelDelete(runtimeContext),
});

/* ─────────────────────────── 对外暴露 ─────────────────────────── */

export const TOOL_SCHEMAS = defs.map((d) => d.schema);

const byName = new Map(defs.map((d) => [d.name, d]));

export function toolNames() { return defs.map((d) => `${d.name}(${d.scope})`); }

/**
 * 执行一个工具调用。任何异常都被兜住并转成结构化错误 ——
 * 工具炸掉不应该让整条回复消失，守衡应当能告诉用户「我查这个失败了」。
 */
export async function executeTool(name, argsJson) {
  const def = byName.get(name);
  if (!def) return { tool: name, ok: false, error: `未知工具：${name}` };

  let args = {};
  if (argsJson && typeof argsJson === 'string') {
    try { args = JSON.parse(argsJson); }
    catch { return { tool: name, ok: false, error: `参数不是合法 JSON：${argsJson.slice(0, 200)}` }; }
  } else if (argsJson && typeof argsJson === 'object') { args = argsJson; }

  try {
    const result = await def.run(args);
    return { tool: name, ok: true, result };
  } catch (e) {
    return { tool: name, ok: false, error: `${e?.name ?? 'Error'}: ${e?.message ?? e}` };
  }
}
