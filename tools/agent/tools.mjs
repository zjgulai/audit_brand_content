/**
 * tools.mjs —— 守衡的工具层
 *
 * 每个工具 = { schema, run, scope }。
 *   scope: 'read'  —— 只读，随时可调
 *          'write' —— 会对外产生副作用（发消息、改状态），需谨慎
 *
 * 设计取舍：先只给「读了能答得更好」的工具。写类工具（发消息、改文档）等业务场景
 * 明确后再放开 —— 一个会主动往群里发东西的智能体，权限必须一次一点地给。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { REPO_ROOT } from './config.mjs';
import { beijingDateTime } from './timefmt.mjs';
import * as feishu from './feishu.mjs';

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
      description: '列出守衡所在工作区的顶层目录与文件。对方问「你都能看到什么」「项目里有什么」时调用。',
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

register('run_readonly_command', {
  scope: 'read',
  schema: {
    type: 'function',
    function: {
      name: 'run_readonly_command',
      description: '在工作区执行一条**只读** shell 命令并返回输出（例如 git log、wc -l、grep 统计）。' +
                   '只允许白名单里的只读命令；任何写操作、删除、安装、网络请求都会被拒绝。',
      parameters: {
        type: 'object',
        properties: { command: { type: 'string', description: '要执行的命令，例如 "git log --oneline -5"' } },
        required: ['command'],
      },
    },
  },
  run: async ({ command }) => {
    // 白名单：只读命令前缀。宁可少给，不要给错。
    const ALLOW = /^(git\s+(log|status|diff|show|branch|remote|tag)|ls|cat|head|tail|wc|grep|rg|find|file|stat|du|df|date|pwd|echo|node\s+--version|npm\s+ls|python3?\s+--version)\b/;
    const cmd = String(command ?? '').trim();
    if (!ALLOW.test(cmd)) return { error: `命令不在只读白名单内，已拒绝：${cmd.slice(0, 80)}` };
    if (/[;&|><`$]/.test(cmd))  return { error: '命令含管道/重定向/命令替换等元字符，已拒绝' };
    try {
      const { stdout, stderr } = await execFileP('bash', ['-lc', cmd], { cwd: REPO_ROOT, timeout: 15_000, maxBuffer: 1 << 20 });
      return { command: cmd, stdout: stdout.slice(0, 8000), stderr: stderr.slice(0, 2000) };
    } catch (e) {
      return { command: cmd, error: e.message, stdout: String(e.stdout ?? '').slice(0, 2000) };
    }
  },
});

/* ─────────────────────────── 内容合规判定（第 10 个只读工具）─────────────────────────── */

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
        '★ 三条必须照实转述的限制，不要简化掉：\n' +
        '(1) 结论是**建议**，不是决定。工具只补证据，不替人过门 —— 你不能因为返回了 auto_pass 就说「已通过」。\n' +
        '(2) 返回 catch_all（零命中）**不等于合规**，含义是「规则库没有覆盖它」。必须转人工。\n' +
        '(3) 每次都读 boundary_statement.unknowns，那里写的是本判定的覆盖边界；' +
        '通常包含「不按品线过滤」「部分守卫词未接线」「只看文本不看图片视频」。\n' +
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
