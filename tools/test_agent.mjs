/**
 * test_agent.mjs —— 守衡内核离线测试
 *
 * 用合成事件跑完整链路（解析 → 记忆 → 工具 → LLM → 回复），不依赖真人 @。
 * 为什么必须做这个：入向链路验证时我用「盯日志」等真人动作，连吃两次空测。
 * 内核的正确性不该由别人的手速决定。
 *
 * 用法：node test_agent.mjs [--live]
 *   默认只测纯本地逻辑（不花 token）；--live 额外跑一次真实 LLM 对话。
 */
import assert from 'node:assert';
import * as feishu from './agent/feishu.mjs';
import { executeTool, runtimeContext, TOOL_SCHEMAS } from './agent/tools.mjs';

const LIVE = process.argv.includes('--live');
let pass = 0, fail = 0;
const ok  = (name, extra = '') => { pass++; console.log(`  ✅ ${name}${extra ? '  ' + extra : ''}`); };
const bad = (name, e) => { fail++; console.log(`  ❌ ${name}\n       ${e}`); };
const t = async (name, fn) => { try { await fn(); ok(name); } catch (e) { bad(name, e.message); } };

console.log('\n═══ 1. mention 还原（守衡能不能知道谁在跟它说话）═══');

await t('还原 @ 占位符为真名', () => {
  const raw = '@_user_1 你好，帮我看看';
  const mentions = [{ key: '@_user_1', name: '李倩怡', id: { open_id: 'ou_test_lee' } }];
  const { display, mentions: resolved } = feishu.resolveMentions(raw, mentions);
  assert.strictEqual(display, '@李倩怡 你好，帮我看看', `实际得到 ${display}`);
  assert.strictEqual(resolved[0].name, '李倩怡');
  assert.strictEqual(resolved[0].openId, 'ou_test_lee');
});

await t('多个 @ 同时还原', () => {
  const raw = '@_user_1 @_user_2 你们看下';
  const mentions = [
    { key: '@_user_1', name: '张三', id: { open_id: 'ou_a' } },
    { key: '@_user_2', name: '李四', id: { open_id: 'ou_b' } },
  ];
  const { display } = feishu.resolveMentions(raw, mentions);
  assert.strictEqual(display, '@张三 @李四 你们看下', `实际得到 ${display}`);
});

await t('识别「@ 的是守衡」（决定群聊是否响应）', () => {
  const yes = feishu.resolveMentions('@_user_1 hi', [{ key: '@_user_1', name: '守衡', id: { open_id: 'cli_aa2243de0438dcd7' } }]);
  assert.strictEqual(feishu.isBotMentioned(yes.mentions), true);
  const no = feishu.resolveMentions('@_user_1 hi', [{ key: '@_user_1', name: '李倩怡', id: { open_id: 'ou_x' } }]);
  assert.strictEqual(feishu.isBotMentioned(no.mentions), false);
});

await t('剥掉 @守衡 本身，只留问题', () => {
  const { display, mentions } = feishu.resolveMentions(
    '@_user_1 你是谁？', [{ key: '@_user_1', name: '守衡', id: { open_id: 'cli_aa2243de0438dcd7' } }]);
  assert.strictEqual(feishu.stripBotMention(display, mentions), '你是谁？');
});

await t('@守衡 与其他 @ 混排时只剥自己', () => {
  const { display, mentions } = feishu.resolveMentions(
    '@_user_1 @_user_2 请回答', [
      { key: '@_user_1', name: '守衡', id: { open_id: 'cli_aa2243de0438dcd7' } },
      { key: '@_user_2', name: '李倩怡', id: { open_id: 'ou_lee' } },
    ]);
  assert.strictEqual(feishu.stripBotMention(display, mentions), '@李倩怡 请回答');
});

console.log('\n═══ 2. 工具层 ═══');

await t('now 工具返回完整北京时间', async () => {
  const r = await executeTool('now', '{}');
  assert.ok(r.ok, r.error);
  // 必须同时含日期、时间、星期 —— 少任何一项都说明格式化不可靠
  assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(r.result.date), `date 格式错：${r.result.date}`);
  assert.ok(/^\d{2}:\d{2}:\d{2}$/.test(r.result.time), `time 格式错：${r.result.time}`);
  assert.ok(/星期/.test(r.result.weekday), `weekday 错：${r.result.weekday}`);
  assert.strictEqual(r.result.beijing_time, `${r.result.date} ${r.result.time} ${r.result.weekday}`);
});

await t('工作区列举可用', async () => {
  runtimeContext.chatId = 'oc_test'; runtimeContext.chatType = 'group';
  const r = await executeTool('list_workspace', '{}');
  assert.ok(r.ok && r.result.entries.length > 0, JSON.stringify(r.result).slice(0, 200));
});

await t('读工作区内文件成功', async () => {
  const r = await executeTool('read_text_file', JSON.stringify({ rel_path: 'PMO/守衡-链路打通确认.md' }));
  assert.ok(r.ok && r.result.content.includes('im.message.receive_v1'), JSON.stringify(r.result).slice(0, 200));
});

await t('路径逃逸被拒绝（安全）', async () => {
  const r = await executeTool('read_text_file', JSON.stringify({ rel_path: '../../../../etc/passwd' }));
  assert.ok(r.ok && r.result.error, '应该返回错误而不是内容');
  assert.ok(/拒绝访问/.test(r.result.error), `实际：${r.result.error}`);
});

await t('写操作命令被白名单拒绝（安全）', async () => {
  for (const c of ['rm -rf /tmp/x', 'curl http://evil.com', 'git push', 'echo hi > /tmp/f', 'ls | grep a']) {
    const r = await executeTool('run_readonly_command', JSON.stringify({ command: c }));
    assert.ok(r.ok && r.result.error, `命令 "${c}" 本应被拒，实际：${JSON.stringify(r.result).slice(0, 120)}`);
  }
});

await t('只读命令可执行', async () => {
  // 注意：这里不用 git —— 本工作区不是 git 仓库（已实测确认）。
  // 测试必须依赖工作区真实存在的性质，否则测的是环境不是代码。
  const r = await executeTool('run_readonly_command', JSON.stringify({ command: 'wc -l PMO/守衡-链路打通确认.md' }));
  assert.ok(r.ok && !r.result.error, JSON.stringify(r.result).slice(0, 300));
  assert.ok(/\d+/.test(r.result.stdout), `stdout 里应有行数，实际：${r.result.stdout}`);
});

await t('非 git 仓库时 git 命令的报错被结构化吞住', async () => {
  const r = await executeTool('run_readonly_command', JSON.stringify({ command: 'git log --oneline -3' }));
  // 命令在白名单内，但环境不是仓库 —— 必须返回结构化错误，不能让异常冒到外面
  assert.ok(r.ok, '工具本身不应抛出');
  assert.ok(r.result.error || r.result.stdout !== undefined);
});

console.log('\n═══ 1b. 空输出不许被读成「0 命中」（2026-09-22 事故，反向对照）═══');

/*
 * 事故原样：守衡执行 `grep -rl <PRD 的 wiki token> .` —— 全仓递归，含 node_modules/、
 * .git/、skills/ 下 777 个压缩包。实测**超过 60 秒都跑不完**（我用 harness 的 60 秒上限
 * 复现过，是被 SIGTERM 杀掉的），而工具只有 15 秒 → 被 timezone 杀掉 →
 * 返回体 { error: "Command failed: …", stdout: "" } → **它只读了 stdout 是空的**，
 * 于是对群里说「我用这个 token 搜了一遍，0 命中」。
 * 真值：那个 token 就在工作区两个文件里。
 *
 * 下面每一条都对着那次误判的一个环节。
 */

await t('超时被杀的返回体里**没有 stdout 这个键** —— 空字符串无从被读成「0 命中」', async () => {
  process.env.SHOUHENG_RO_TIMEOUT_MS = '1';   // 1ms：bash 启动本身都超过它，必定超时
  let r;
  try {
    r = await executeTool('run_readonly_command', JSON.stringify({ command: 'grep -rn 守衡 PMO' }));
  } finally {
    delete process.env.SHOUHENG_RO_TIMEOUT_MS;
  }
  assert.ok(r.ok, '工具本身不应抛出');
  assert.strictEqual(r.result.status, 'timeout', `本应判为超时，实际：${JSON.stringify(r.result).slice(0, 200)}`);
  assert.ok(!('stdout' in r.result),
    `超时时返回体里不许有 stdout —— 空 stdout 会被读成「扫完了、没命中」。实际：${JSON.stringify(r.result).slice(0, 200)}`);
  assert.ok(/未测/.test(r.result.note), `note 里必须写出「未测」：${r.result.note}`);
  assert.ok(/不是「0 命中」/.test(r.result.note), 'note 必须明着堵住「0 命中」这个读法');
});

await t('引发事故的那条命令，在跑之前就被护栏拒绝', async () => {
  const r = await executeTool('run_readonly_command',
    JSON.stringify({ command: 'grep -rl NB55wAq8liEOdKkquL2cgtPEnmg .' }));
  assert.ok(r.ok && r.result.status === 'rejected',
    `本应被护栏拒绝，实际：${JSON.stringify(r.result).slice(0, 200)}`);
  // 它必须给出**下一步**，不能只说「不行」
  assert.ok(/search_workspace/.test(r.result.note), '拒绝时必须给替代路径');
});

await t('护栏不许把正常用法也拦掉（点名子目录的 grep 要放行）', async () => {
  const r = await executeTool('run_readonly_command',
    JSON.stringify({ command: 'grep -rn 守衡 PMO/守衡-链路打通确认.md' }));
  assert.ok(r.ok, '工具本身不应抛出');
  assert.notStrictEqual(r.result.status, 'rejected',
    `点名到具体文件不该被拦，实际：${JSON.stringify(r.result).slice(0, 200)}`);
});

await t('白名单只放行 lark_find.py 的**读**子命令，下载类不走只读通道', async () => {
  // 2026-09-22 起守衡能用 `python3 tools/lark_find.py readdoc <token>` 读飞书文档正文。
  // ★ 2026-10-17 委托方改线：下载**也允许**了。但 `run_readonly_command` 是**只读**通道，
  //   下载必须走受控下载调用点并在 tools/download_callers.json 登记（DG-1），
  //   不能从这里放行 —— 否则「只读」这个词就不再成立，且下载会绕过落盘治理。
  for (const c of ['python3 tools/lark_find.py download abc',
                   'python3 tools/lark_find.py medias abc',
                   'python3 tools/lark_find.py export abc']) {
    const r = await executeTool('run_readonly_command', JSON.stringify({ command: c }));
    assert.strictEqual(r.result.status, 'rejected',
      `"${c}" 必须被拒（只读通道不执行下载；下载走受控通道），实际：${JSON.stringify(r.result).slice(0, 200)}`);
  }
});

await t('search_workspace 找得到那个 token（对事故的**真阳性**对照）', async () => {
  const r = await executeTool('search_workspace', JSON.stringify({ keyword: 'NB55wAq8liEOdKkquL2cgtPEnmg' }));
  assert.ok(r.ok && r.result.status === 'ok', JSON.stringify(r.result).slice(0, 200));
  assert.ok(r.result.matches >= 1,
    `那次说「0 命中」，真值是至少 1 —— 实际 ${r.result.matches}（扫了 ${r.result.searched_files} 个文件）`);
  assert.strictEqual(r.result.stopped_early, false, '整仓检索不该被截断，否则「0 命中」不成立');
});

await t('search_workspace：0 命中必须带分母，且分母为 0 时不算数', async () => {
  // 关键词必须**当场生成**：写死的字符串会出现在本测试文件自己里，
  // 于是「一定不存在」变成「一定存在」—— 这正是那类「假阴性/假阳性都在骗人」的坑。
  const ghost = `zz${Date.now()}x${Math.random().toString(36).slice(2)}q`;
  const r = await executeTool('search_workspace', JSON.stringify({ keyword: ghost }));
  assert.ok(r.result.searched_files > 0, '分母必须大于 0，否则「没找到」是未测不是 0');
  assert.strictEqual(r.result.matches, 0, `不该命中，实际 ${r.result.matches}`);
  assert.ok(/分母/.test(r.result.note), `0 命中时要说清分母撑着：${r.result.note}`);
});

await t('search_workspace：扫不完时必须说「未测」，不许下「没找到」的结论', async () => {
  const ghost = `zz${Date.now()}x${Math.random().toString(36).slice(2)}q`;
  const r = await executeTool('search_workspace', JSON.stringify({ keyword: ghost, max_files: 3 }));
  assert.strictEqual(r.result.stopped_early, true, '上限这么小必须被截断');
  assert.ok(/未测/.test(r.result.note), `截断时 note 必须说未测：${r.result.note}`);
  // 判据用的是**扫完时才出现的那句话**，而不是「0 命中」三个字 ——
  // 后者会出现在「不许说成 0 命中」这句提示语里，拿它当判据等于自己判自己。
  assert.ok(!/有分母撑着/.test(r.result.note),
    `截断时不许给出「0 命中」的结论句：${r.result.note}`);
});

await t('未知工具给出结构化错误而非崩溃', async () => {
  const r = await executeTool('no_such_tool', '{}');
  assert.strictEqual(r.ok, false);
  assert.ok(/未知工具/.test(r.error));
});

await t('坏 JSON 参数不崩溃', async () => {
  const r = await executeTool('now', '{bad json');
  assert.strictEqual(r.ok, false);
  assert.ok(/JSON/.test(r.error));
});

console.log('\n═══ 3. markdown → 飞书富文本 ═══');

await t('代码块被识别为 code_block（不是一堆星号）', () => {
  const nodes = feishu.__test_mdToPostNodes('说明：\n```js\nconst a = 1;\n```\n结束');
  const flat = JSON.stringify(nodes);
  assert.ok(flat.includes('code_block'), flat.slice(0, 300));
  assert.ok(flat.includes('const a = 1;'), flat.slice(0, 300));
});

await t('粗体与行内代码转成样式节点', () => {
  const nodes = feishu.__test_mdToPostNodes('这是 **重点** 和 `code`');
  const flat = JSON.stringify(nodes);
  assert.ok(flat.includes('"bold"'), flat.slice(0, 300));
  assert.ok(flat.includes('code_inline'), flat.slice(0, 300));
});

await t('未闭合的代码块不吞内容', () => {
  const nodes = feishu.__test_mdToPostNodes('前\n```\n没闭合的内容');
  assert.ok(JSON.stringify(nodes).includes('没闭合的内容'));
});

console.log('\n═══ 4. 记忆压缩的切点安全性（防 API 400）═══');

await t('压缩切点不拆散 tool_calls 与其结果', async () => {
  const mem = await import('./agent/memory.mjs');
  // 构造一段含工具调用的历史：user → assistant(tool_calls) → tool → assistant
  const sess = { key: 'test_boundary', messages: [], summary: '', messageCount: 0 };
  for (let i = 0; i < 6; i++) {
    sess.messages.push({ role: 'user', content: `问题 ${i}` });
    sess.messages.push({ role: 'assistant', content: '', tool_calls: [{ id: `c${i}`, type: 'function', function: { name: 'now', arguments: '{}' } }] });
    sess.messages.push({ role: 'tool', tool_call_id: `c${i}`, content: '{"ok":true}' });
    sess.messages.push({ role: 'assistant', content: `回答 ${i}` });
  }
  const compacted = await mem.compact(sess, async () => '摘要', 5, 5);  // 保留 5 轮 / 超过 5 条触发
  assert.strictEqual(compacted, true, '本应发生压缩');
  // 留下部分的第一条必须是 user —— 否则说明切在了 tool_calls/工具结果中间
  assert.strictEqual(sess.messages[0].role, 'user',
    `切点错误，留首条是 ${sess.messages[0].role}；应回退到 user 边界`);
  // 且留下的序列里，每个 assistant(tool_calls) 后面必须紧跟同数量 tool
  for (let i = 0; i < sess.messages.length; i++) {
    const m = sess.messages[i];
    if (m.role === 'assistant' && m.tool_calls?.length) {
      for (let k = 0; k < m.tool_calls.length; k++) {
        assert.strictEqual(sess.messages[i + 1 + k]?.role, 'tool',
          `第 ${i} 条 assistant(tool_calls) 之后第 ${k + 1} 条不是 tool`);
      }
    }
  }
});

await t('无法回退到边界时放弃压缩而非产生坏序列', async () => {
  const mem = await import('./agent/memory.mjs');
  const sess = { key: 'test_noboundary', messages: [], summary: '', messageCount: 0 };
  // 全是 tool 消息，没有 user 可作为切点
  for (let i = 0; i < 40; i++) sess.messages.push({ role: 'tool', tool_call_id: `t${i}`, content: 'x' });
  const compacted = await mem.compact(sess, async () => '摘要', 5, 5);  // 保留 5 轮 / 超过 5 条触发
  assert.strictEqual(compacted, false, '找不到安全切点时应放弃压缩');
  assert.strictEqual(sess.messages.length, 40, '放弃压缩时不应丢消息');
});

await t('纪要为空时必须放弃压缩（不许「删了历史、什么都没留」）', async () => {
  // ★ 2026-09-22 真事故：`summarize()` 在推理预算被吃光时返回空串，
  //   `compact()` 把它当成纪要写下去，**然后把旧对话全删了**。
  //   盘上的读数：三个会话的 `summary` 全是 0 长度，而日志印了 8 次「保留 N 轮 + 纪要」。
  //   代价不是「这次没压缩」，是「守衡确信地不记得」—— 下一轮它看到的是断头的历史。
  //
  //   这一条守的是**最后一道闸**：它与 summarize 的行为无关，故意的。
  //   喂三个空法（空串 / 纯空白 / undefined），一个都不许通过。
  const mem = await import('./agent/memory.mjs');
  for (const [name, empty] of [['空串', ''], ['纯空白', '\n\n   \t\n'], ['undefined', undefined]]) {
    const sess = { key: `test_emptysummary_${name}`, messages: [], summary: '', messageCount: 0 };
    for (let i = 0; i < 12; i++) {
      sess.messages.push({ role: 'user', content: `问题 ${i}` });
      sess.messages.push({ role: 'assistant', content: `回答 ${i}` });
    }
    const before = sess.messages.length;
    const compacted = await mem.compact(sess, async () => empty, 5, 5);
    assert.strictEqual(compacted, false, `返回${name}时应放弃压缩，实际 compacted=${compacted}`);
    assert.strictEqual(sess.messages.length, before, `返回${name}时不许丢消息（原 ${before} 条）`);
    assert.strictEqual(sess.summary, '', `返回${name}时不许把空白写进纪要`);
  }
  // 反面：非空纪要**必须**照常压缩 —— 否则上面那条可能是「压缩整个坏了」而全绿。
  const sess2 = { key: 'test_emptysummary_ok', messages: [], summary: '', messageCount: 0 };
  for (let i = 0; i < 12; i++) {
    sess2.messages.push({ role: 'user', content: `问题 ${i}` });
    sess2.messages.push({ role: 'assistant', content: `回答 ${i}` });
  }
  const okCompacted = await mem.compact(sess2, async () => '真的纪要', 5, 5);
  assert.strictEqual(okCompacted, true, '有纪要时必须照常压缩（反向对照）');
  assert.strictEqual(sess2.summary, '真的纪要', '纪要应写进去');
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. 查名字的降级链
//
// 背景：2026-09-16 真实群聊里，守衡收到消息却查不出「谁在说话」——
// 它走的是通讯录接口，而本应用没开 contact 权限，返回 99991672。
// 原来的 getUserName 用 `catch { return null }` 把这个原因吃掉了，
// 上层只能看到「查不到」，无法区分「人不在可见范围」还是「接口没权限」。
//
// 本组测试打的是真飞书接口（用真凭证），因为只有真接口才会暴露权限边界：
// 假 mock 会永远返回成功，测不出这个 bug。
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n═══ 5. 查名字的降级链（真接口，验权限边界）═══');

let liveChatId = null;
{
  const { config } = await import('./agent/config.mjs');
  liveChatId = config.allowedChats?.[0] ?? null;
  if (!liveChatId) {
    // 配置里是「不限」时没有群 id，但降级链必须有真群才能验证。
    // 这里让测试自己通过 API 发现群，而不是硬编码一个 id：
    // 硬编码的 id 在换群/换环境后会静默失效，测试会假装通过。
    try {
      const r = await feishu.client.im.chat.list({ params: { page_size: 50 } });
      const chats = r?.data?.items ?? [];
      const pick = chats.find((c) => /守衡|内容治理/.test(c.name ?? '')) ?? chats[0];
      liveChatId = pick?.chat_id ?? null;
      if (liveChatId) console.log(`  （自动发现群：${pick.name ?? '(无名)'} → ${liveChatId}）`);
    } catch (e) {
      console.log(`  （自动发现群失败：${e?.response?.data?.msg ?? e.message}）`);
    }
  }
}
if (!liveChatId) {
  console.log('  ⚠ 找不到任何群，第 5 组无法验证真接口 —— 这不算通过，请检查应用是否在群里');
}

await t('群成员接口可用（降级链的第一条路）', async () => {
  if (!liveChatId) throw new Error('没有配置 allowedChats，跳过真接口验证');
  const members = await feishu.listMembers(liveChatId, 100);
  assert.ok(Array.isArray(members), `期望数组，实际 ${JSON.stringify(members).slice(0, 200)}`);
  assert.ok(members.length > 0, '群成员列表为空，无法验证后续降级');
  assert.ok(members.every((m) => m.name && m.openId), '成员项必须同时有 name 和 openId');
});

await t('带 chatId 时，同群成员能查到真名（不需要通讯录权限）', async () => {
  if (!liveChatId) throw new Error('没有配置 allowedChats，跳过');
  const members = await feishu.listMembers(liveChatId, 100);
  const someone = members[0];
  const r = await feishu.getUserName(someone.openId, liveChatId);
  assert.strictEqual(r.name, someone.name, `期望 ${someone.name}，实际 ${r.name}`);
  assert.strictEqual(r.source, 'chat_member', `应命中群成员这条路，实际 source=${r.source}`);
});

await t('不带 chatId 且通讯录无权限时，如实返回原因而不是静默 null', async () => {
  const r = await feishu.getUserName('ou_00000000000000000000000000000000', null);
  assert.strictEqual(r.name, null, '不存在的 open_id 不应查到名字');
  assert.strictEqual(r.source, 'none');
  // 关键：reason 必须非空。若这里是 null/undefined，说明又退回了静默吞异常。
  assert.ok(r.reason, `必须带出失败原因，实际 reason=${r.reason}`);
  assert.ok(
    /权限|code=|通讯录/.test(r.reason),
    `原因应可读且指向真实原因，实际：${r.reason}`,
  );
});

await t('lookup_user 工具能返回 source，并带上「别编称呼」的提示', async () => {
  const { executeTool, runtimeContext } = await import('./agent/tools.mjs');
  if (!liveChatId) throw new Error('没有配置 allowedChats，跳过');
  const members = await feishu.listMembers(liveChatId, 100);
  runtimeContext.chatId = liveChatId;               // 模拟真实处理时的注入
  const r = await executeTool('lookup_user', JSON.stringify({ open_id: members[0].openId }));
  assert.ok(r.ok, JSON.stringify(r).slice(0, 200));
  assert.strictEqual(r.result.name, members[0].name);
  assert.strictEqual(r.result.source, 'chat_member', `实际 source=${r.result.source}`);
  runtimeContext.chatId = null;
});

await t('查不到时，工具返回的提示明确禁止模型编造称呼', async () => {
  const { executeTool, runtimeContext } = await import('./agent/tools.mjs');
  runtimeContext.chatId = null;                     // 强制走通讯录那条失败路
  const r = await executeTool('lookup_user', JSON.stringify({ open_id: 'ou_00000000000000000000000000000000' }));
  assert.ok(r.ok, '工具本身不应抛出');
  assert.ok(r.result.error, '应返回 error 字段');
  assert.ok(r.result.reason, '应带出 reason');
  assert.ok(/不要猜测|不要编造/.test(r.result.hint ?? ''), `hint 缺失或未禁止编造：${r.result.hint}`);
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. 去重表落盘失败时的行为
//
// 背景：flushSeen 原来写成 `catch {}` —— 写盘失败被完全吞掉。
// 这个表决定「重启后是否重复回话」，它一旦静默丢失，表现是守衡对同一条消息
// 回两次，且日志里没有任何线索。
// 这段必须能注入路径才测得了，所以 STATE_DIR 支持 SHOUHENG_STATE_DIR 覆盖。
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n═══ 6. 去重表落盘失败不静默 ═══');

await t('写盘失败时不清 seenDirty，并打出一条警告', async () => {
  const fs = await import('node:fs');
  const os = await import('node:os');
  const p = await import('node:path');

  // 让 STATE_DIR 指向一个「存在但不可写」的目录：
  // 用文件冒充目录，任何写入都会 ENOTDIR —— 比 chmod 更可靠，且不受 root 影响。
  const tmp = fs.mkdtempSync(p.join(os.tmpdir(), 'shouheng-test-'));
  const fakeDir = p.join(tmp, 'not-a-dir');
  fs.writeFileSync(fakeDir, 'x');
  process.env.SHOUHENG_STATE_DIR = fakeDir;

  const warnings = [];
  const origWarn = console.warn;
  console.warn = (...a) => warnings.push(a.join(' '));

  let mod;
  try {
    // 带 cache-buster，确保重新读取 SHOUHENG_STATE_DIR
    mod = await import(`./agent/agent.mjs?failtest=${Date.now()}`);
    mod.alreadyHandled('om_test_flush_fail_1');
    mod.flushSeen();                 // 第一次：应失败并报一次
    mod.flushSeen();                 // 第二次：不应重复刷屏
  } finally {
    console.warn = origWarn;
    delete process.env.SHOUHENG_STATE_DIR;
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const seenWarnings = warnings.filter((w) => w.includes('[seen]'));
  assert.strictEqual(seenWarnings.length, 1,
    `应恰好报 1 次（不刷屏），实际 ${seenWarnings.length} 次：${JSON.stringify(seenWarnings)}`);
  assert.ok(/落盘失败/.test(seenWarnings[0]), `警告内容不对：${seenWarnings[0]}`);
  assert.ok(/重复回话/.test(seenWarnings[0]), `警告应说明后果：${seenWarnings[0]}`);
});

await t('恢复可写后重新落盘，并报一次恢复', async () => {
  const fs = await import('node:fs');
  const os = await import('node:os');
  const p = await import('node:path');

  const tmp = fs.mkdtempSync(p.join(os.tmpdir(), 'shouheng-test2-'));
  const fakeDir = p.join(tmp, 'not-a-dir');
  fs.writeFileSync(fakeDir, 'x');
  process.env.SHOUHENG_STATE_DIR = fakeDir;

  const warnings = [];
  const origWarn = console.warn;
  console.warn = (...a) => warnings.push(a.join(' '));

  try {
    const mod = await import(`./agent/agent.mjs?recover=${Date.now()}`);
    mod.alreadyHandled('om_test_recover_1');
    mod.flushSeen();                                  // 失败
    fs.rmSync(fakeDir, { force: true });              // 清掉障碍，让路径可写
    fs.mkdirSync(fakeDir, { recursive: true });
    mod.flushSeen();                                  // 应成功并报恢复
  } finally {
    console.warn = origWarn;
    delete process.env.SHOUHENG_STATE_DIR;
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const fail = warnings.filter((w) => w.includes('[seen]'));
  assert.ok(fail.some((w) => /落盘失败/.test(w)), '应报过失败');
  assert.ok(fail.some((w) => /恢复落盘/.test(w)),
    `恢复后应报一次，实际警告：${JSON.stringify(fail)}`);
});

await t('状态目录被同名文件占位时，进程仍能启动（不许 EEXIST/ENOTDIR 崩掉）', async () => {
  // 必须在子进程里测：修复前这个场景会直接杀掉进程，
  // 在本进程里测的话「崩溃」会被误读成「测试没通过」，而不是「产品起不来」。
  const { spawnSync } = await import('node:child_process');
  const fs = await import('node:fs');
  const os = await import('node:os');
  const p = await import('node:path');

  const tmp = fs.mkdtempSync(p.join(os.tmpdir(), 'shouheng-boot-'));
  const fakeDir = p.join(tmp, 'not-a-dir');
  fs.writeFileSync(fakeDir, 'x');           // 用文件占住「状态目录」这个路径

  const r = spawnSync(process.execPath, ['--input-type=module', '-e',
    // 用绝对路径：原来写的是 './tools/agent/agent.mjs'，那是相对 cwd 的，
    // 于是这个测试**只在仓库根目录下运行才成立** —— 在 tools/ 里跑就会
    // 报 ERR_MODULE_NOT_FOUND（找不到 tools/tools/agent/agent.mjs）。
    // 子进程加载哪个文件是测试的固有属性，不该取决于你从哪敲的命令。
    `await import(${JSON.stringify(new URL('./agent/agent.mjs', import.meta.url).href)}); console.log('BOOT_OK');`,
  ], {
    cwd: process.cwd(),
    env: { ...process.env, SHOUHENG_STATE_DIR: fakeDir },
    encoding: 'utf8',
    timeout: 30000,
  });
  fs.rmSync(tmp, { recursive: true, force: true });

  assert.strictEqual(r.status, 0,
    `进程应正常退出，实际 status=${r.status}\n stderr: ${(r.stderr || '').slice(-500)}`);
  assert.ok((r.stdout || '').includes('BOOT_OK'),
    `应到达 import 之后的代码，实际 stdout: ${(r.stdout || '').slice(-300)}`);
  assert.ok(!/EEXIST|ENOTDIR: not a directory, mkdir/.test(r.stderr || ''),
    `不应把目录创建失败升级成崩溃：${(r.stderr || '').slice(-300)}`);
});

if (LIVE) {
  console.log('\n═══ 4. 真实 LLM 全链路（会消耗 token）═══');
  const { handleMessage } = await import('./agent/agent.mjs');
  const evt = (text, id) => ({
    sender: { sender_id: { open_id: 'ou_test_lee' }, sender_type: 'user' },
    message: {
      message_id: id, chat_id: 'oc_test_offline', chat_type: 'group', message_type: 'text',
      content: JSON.stringify({ text }),
      mentions: [{ key: '@_user_1', name: '守衡', id: { open_id: 'cli_aa2243de0438dcd7' } },
                 { key: '@_user_2', name: '李倩怡', id: { open_id: 'ou_test_lee' } }],
    },
  });

  for (const [i, q] of [
    '@_user_1 @_user_2 你是谁？用两句话回答。',
    '@_user_1 @_user_2 我刚才问了你什么？',
    '@_user_1 @_user_2 现在几点？',
  ].entries()) {
    const r = await handleMessage(evt(q, `om_test_${Date.now()}_${i}`));
    console.log(`\n  Q${i + 1}: ${q}`);
    console.log(`  A${i + 1}: ${r.reply ?? '（无回复 / ' + r.reason + '）'}`);
    if (r.meta?.toolTrace?.length) console.log(`  工具: ${r.meta.toolTrace.map((t) => t.tool).join(', ')}`);
  }
  const { status } = await import('./agent/agent.mjs');
  console.log('\n  LLM 用量:', JSON.stringify(status().llm, null, 2));
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. 时间基准一致性
//
// 背景（真实事故，不是假想）：`now` 工具返回北京时间，而 `recent_messages`
// 曾经返回 `toISOString()`，也就是 UTC。两种基准并存时，模型会自己再做一次
// 换算 —— 真实的 11:12 被守衡在群里说成「23:12」，一次错 12 小时。
//
// 这类错误必须由测试兜住，因为它在生产里**完全静默**：
// 没有异常、没有报错、日志干净，只是守衡对外说了错的时间。
// 唯一可靠的判据是「格式本身不许出现 UTC 的样子」。
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n═══ 7. 时间基准一致性（北京，不是 UTC）═══');

// 形如 `2026-09-16 12:26:20 星期三`；UTC ISO 那种 `...T04:26:20.117Z` 必须不被接受。
const BEIJING_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} 星期[日一二三四五六]$/;

await t('守衡格式化的时间不带 UTC 标识（Z / T）', async () => {
  const { beijingDateTime, beijingString } = await import('./agent/timefmt.mjs');
  const s = beijingString(Date.parse('2026-09-16T04:26:20.400Z'));
  assert.ok(BEIJING_RE.test(s), `应为「YYYY-MM-DD HH:mm:ss 星期X」，实际：${s}`);
  assert.ok(!s.includes('Z') && !s.includes('T'),
    `不得混入 UTC 标识（这正是让模型二次换算的诱因）：${s}`);

  const full = beijingDateTime(Date.parse('2026-09-16T04:26:20.400Z'));
  assert.strictEqual(full.date, '2026-09-16');
  assert.strictEqual(full.time, '12:26:20', `UTC 04:26 应为北京 12:26，实际 ${full.time}`);
  assert.strictEqual(full.iso, '2026-09-16T04:26:20.400Z', 'iso 应保留同一瞬间，便于核对');
});

await t('now 工具与 timefmt 同源，且偏移按真实时区计算', async () => {
  const { executeTool } = await import('./agent/tools.mjs');
  const r = await executeTool('now', {});
  assert.strictEqual(r.ok, true, `now 工具失败：${r.error}`);
  assert.ok(BEIJING_RE.test(r.result.beijing_time),
    `now.beijing_time 格式应为「YYYY-MM-DD HH:mm:ss 星期X」，实际：${r.result.beijing_time}`);
  // 不硬编码 +8：将来时区规则若变化，这里会自己发现，而不是继续悄悄算错。
  assert.strictEqual(r.result.timezone, 'Asia/Shanghai (UTC+08:00)',
    `时区标注不对：${r.result.timezone}`);
});

await t('午夜不产生 24:xx 这种非法时刻', async () => {
  const { beijingDateTime } = await import('./agent/timefmt.mjs');
  // 北京时间 00:00–00:59 对应 UTC 前一天 16:xx。
  // en-CA + hour12:false 在午夜可能给出 hour='24'，不归一就会输出「24:05」。
  for (const h of [0, 1, 5, 23]) {
    const utc = Date.UTC(2026, 8, 15, h, 5, 0);   // 北京 = h+8
    const { time } = beijingDateTime(utc);
    const hh = Number(time.slice(0, 2));
    assert.ok(hh >= 0 && hh <= 23, `时刻越界：${time}（UTC ${h}:05）`);
    assert.ok(!time.startsWith('24'), `出现了非法的 24 时：${time}`);
  }
});

await t('时间戳损坏时不抛异常，而是给出可读的占位', async () => {
  const { beijingString } = await import('./agent/timefmt.mjs');
  // 一条坏消息的时间戳不该让整个工具调用失败 —— 那是把局部数据问题升级成功能故障。
  const s = beijingString('not-a-date');
  assert.ok(typeof s === 'string' && s.length > 0, `应返回可读占位，实际：${s}`);
  assert.ok(s.includes('时间未知'), `应说明时间未知，实际：${s}`);
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. 群历史必须能分辨「谁发的」
//
// 背景（真实事故）：群历史接口**是**返回 sender.id 的（实测有值），但工具层
// 把它丢掉、一律显示「用户」。守衡于是看到 7 条消息全是「用户」，
// 据此回答「我分辨不出哪条是谁发的」—— 一个听上去非常合理、但完全错误的结论。
//
// 这类缺陷的性质：**不是能力不足，是自己把信息扔了**。守衡会自信地宣称
// 自己做不到，而数据一直躺在返回值里。所以必须有测试锁住「占位符不许回来」。
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n═══ 8. 群历史能分辨发送者 ═══');

await t('app 消息与 user 消息都被正确归类', async () => {
  const { resolveSender } = await import('./agent/feishu.mjs');
  const map = new Map([['ou_me', '周健'], ['ou_other', '李倩怡']]);

  assert.strictEqual(resolveSender({ senderType: 'app', senderId: 'cli_x' }, map).from, '守衡(你自己)',
    'app 消息应标成守衡自己');
  assert.strictEqual(resolveSender({ senderType: 'user', senderId: 'ou_me' }, map).from, '周健',
    '已知成员应解析出姓名');
  assert.strictEqual(resolveSender({ senderType: 'user', senderId: 'ou_other' }, map).from, '李倩怡',
    '不同成员必须能区分开');
});

await t('未知成员退化为 open_id，而不是「用户」这种无法区分的占位符', async () => {
  const { resolveSender } = await import('./agent/feishu.mjs');
  const map = new Map();   // 空成员表：模拟「拉不到成员列表」

  const r = resolveSender({ senderType: 'user', senderId: 'ou_unknown_person' }, map);
  assert.ok(!/^用户$/.test(r.from),
    `退回无法区分人的「用户」等于重新制造这次的 bug：${r.from}`);
  assert.ok(r.from.includes('ou_unknown_person'),
    `应保留 open_id 以便比对：${r.from}`);
  // 关键：即使解析不出姓名，也必须留下可比对的身份，让「两条是不是同一个人」仍然可判
  assert.strictEqual(r.senderOpenId, 'ou_unknown_person', 'senderOpenId 必须一并带出');
});

await t('接口没给发送者身份时，如实说明，不伪装成普通「用户」', async () => {
  const { resolveSender } = await import('./agent/feishu.mjs');
  const r = resolveSender({ senderType: 'user', senderId: undefined }, new Map());
  assert.ok(r.from.includes('未返回'), `应如实标注接口未返回身份：${r.from}`);
  assert.strictEqual(r.senderOpenId, null);
});

await t('真实群里用户消息解析出姓名（不是 ou_ 开头）', async () => {
  const { executeTool, runtimeContext } = await import('./agent/tools.mjs');
  const feishuMod = await import('./agent/feishu.mjs');
  runtimeContext.chatId = 'oc_49a7cfb2861cffa4365ca8491f398d32';
  runtimeContext.chatType = 'group';

  const members = await feishuMod.listMembers(runtimeContext.chatId);
  const names = new Set((Array.isArray(members) ? members : []).map((u) => u.name));

  const r = await executeTool('recent_messages', { limit: 20 });
  assert.strictEqual(r.ok, true, `recent_messages 失败：${r.error}`);
  const msgs = r.result.messages;
  assert.ok(msgs.length > 0, '应至少取到一条历史消息');

  const userMsgs = msgs.filter((m) => !String(m.from).includes('守衡'));
  assert.ok(userMsgs.length > 0, '本群应有用户消息可供验证');
  for (const m of userMsgs) {
    assert.ok(!/^用户$/.test(m.from), `不得退回「用户」占位符：${JSON.stringify(m).slice(0, 120)}`);
    assert.ok(names.has(m.from),
      `发送者「${m.from}」应是本群成员之一（${[...names].join('、')}）—— 解析不出姓名说明成员表没接上`);
  }

  // 顺带确认时间与身份是同一份数据里出来的，不是拼凑的
  assert.ok(/星期[日一二三四五六]$/.test(msgs[0].at), `时间格式不对：${msgs[0].at}`);
  runtimeContext.chatId = null;
});

// ─────────────────────────────────────────────────────────────────────────────
// 第 9 组：截断守卫。真实事故 —— 779 字回复停在「…里「未做」，
// 守护进程却记「✓ 已发送」。半句话被当成完整回答，用户无从知道它是断的。
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n═══ 9. 截断必须可见（不许把半句话当完整回答发出去）═══');

await t('finish_reason=length 必须被判为截断（哪怕正文看着像正常结尾）', async () => {
  const { detectTruncation } = await import('./agent/truncate.mjs');

  const r = detectTruncation({ finishReason: 'length', text: '这是一段看起来已经写完的话。' });
  assert.strictEqual(r.cut, true, 'finish_reason 是权威信号，不能被文本启发式推翻');
  assert.ok(/length/.test(r.reason), `原因里应包含 length：${r.reason}`);

  const ok = detectTruncation({ finishReason: 'stop', text: '正常收尾的回答。' });
  assert.strictEqual(ok.cut, false, '正常收尾不应误报');
});

await t('回归：事故原文必须被拦住', async () => {
  const { detectTruncation } = await import('./agent/truncate.mjs');

  // 逐字来自 2026-09-16 那条真实回复的结尾
  const incident = '**怎么变好的：** 刚查时工具已经修好并重启了，我重新读了一次历史，发送者字段就出来了。这条也算那份记录里「未做';
  const r = detectTruncation({ finishReason: 'length', text: incident });
  assert.strictEqual(r.cut, true, '这条必须被判为截断');

  // 即使 finish_reason 丢了，文本启发式也要能兜住
  const noFinish = detectTruncation({ finishReason: undefined, text: incident });
  assert.strictEqual(noFinish.cut, true,
    '『未做』这种悬空结尾即使没有 finish_reason 也必须拦住 —— 不能只依赖一个信号');
});

await t('悬空标点与空回复都要拦住', async () => {
  const { detectTruncation } = await import('./agent/truncate.mjs');

  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '我想说的是，' }).cut, true, '逗号结尾应拦');
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '补充说明（' }).cut, true, '左括号结尾应拦');
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '空回复应拦' }).cut, false, '有收尾的中文不该拦');
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '' }).cut, true, '空回复应拦');
  // 短句不误报：短内容本来就可能没有句号
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '好' }).cut, false, '短回答不该误报');
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: '收到' }).cut, false, '两字回复不该误报');
  // 表格/列表结尾不该误报（Markdown 里本来就常无句号）
  const table = '| # | 时间 | 说的 |\n|---|---|---|\n| 1 | 22:38 | 你是做什么的 |';
  assert.strictEqual(detectTruncation({ finishReason: 'stop', text: table }).cut, false, '表格结尾不该误报');
});

await t('被截断的回复必须带出可见的截断标记，且不留在半句话上', async () => {
  const { annotateTruncation } = await import('./agent/truncate.mjs');

  const incident = '**怎么变好的：** 刚查时工具已经修好并重启了。这条也算那份记录里「未做';
  const out = annotateTruncation(incident, { reason: 'finish_reason=length（额度耗尽）' });

  assert.ok(out.includes('截断'), '必须明说被截断了，用户才知道这不是全部');
  assert.ok(out.includes('接着说'), '要给出可执行的下一步');
  assert.ok(!out.includes('「未做\n'), '不能把半句话原样留在正文里');
  assert.ok(out.startsWith('**怎么变好的：**'), '完整部分应保留');

  // 超长必须被收住，不能一条消息刷屏
  const huge = '一。'.repeat(5000);
  const capped = annotateTruncation(huge, { maxChars: 500 });
  assert.ok(capped.length < 900, `应被长度上限收住，实际 ${capped.length} 字`);
});

await t('配置的 maxTokens 必须留得下思维链（实测 1600 会被吃光）', async () => {
  const { config } = await import('./agent/config.mjs');
  assert.ok(config.llm.maxTokens >= 4000,
    `maxTokens=${config.llm.maxTokens} 太小：DeepSeek 的额度同时覆盖思维链，实测 1600/4000 时 reasoning 会全部吃光、正文 0 字`);
});

console.log('\n═══ 10. 群历史的「看不见」必须由工具给，不由模型推 ═══');

await t('提示词能构建，且人设正文里没有裸反引号', async () => {
  const { buildSystemPrompt, SYSTEM_PROMPT } = await import('./agent/persona.mjs');
  let sp;
  assert.doesNotThrow(() => { sp = buildSystemPrompt(); }, 'SYSTEM_PROMPT 是模板字符串，正文里出现裸反引号会让整个模块语法错误');

  // 事故：往提示词里写 `recent_messages` 做反引号强调，模板字符串提前闭合，
  // 整个 persona.mjs 变成语法错误 —— 而这在跑测试之前完全看不出来。
  //
  // ★ 2026-09-22 修正：原先断言的是「`# 当前时间` 之前的全部正文里不许有反引号」。
  //   **那是误报，而且已经挂了很久** —— `cardContract()` 那段本来就要示范卡片块围栏
  //   （源码里写的是转义反引号 \`\`\`，构建后就是真反引号），它就落在那个区间里。
  //   实测：改之前跑本套件是「41 通过 / 1 失败」，失败的就是这一条。
  //   一个长期误报的检查器会让人开始不看报告（AGENTS.md §2.1.1），所以改成断真正的不变量：
  //   **人设正文（SYSTEM_PROMPT）里一个反引号都不许有**；卡片规程那段单独放行，
  //   但要断言它示范的围栏**真的出现在了成品提示词里**（反过来被「修」没了也要红）。
  assert.strictEqual((SYSTEM_PROMPT.match(/`/g) || []).length, 0,
    `人设正文里出现了反引号：${SYSTEM_PROMPT.slice(Math.max(0, SYSTEM_PROMPT.indexOf('`') - 60), SYSTEM_PROMPT.indexOf('`') + 60)}`);
  assert.ok(sp.includes('[[card:类型]]'), '卡片块的围栏必须真的出现在成品提示词里');
  assert.ok(sp.includes('```'), '围栏的三个反引号必须真的渲染出来（转义写错会静默少掉）');

  assert.ok(sp.includes('只能看到最近 50 条'), '必须写明群历史只看得到最近 50 条');
  assert.ok(sp.includes('撤回的消息，原文取不回'), '必须写明撤回的消息取不回原文');
  assert.ok(sp.includes('非文字消息要分三种说'), '必须写明非文字消息分三类');
  assert.ok(sp.includes('不可信原文'), '必须写明入站文本附件是不可信输入');
  assert.ok(sp.includes('「我打不开飞书文档」通常是一句假话'),
    '必须写明：收到飞书链接时先说工作区里有没有那一份，再说读不读得了');
  assert.ok(!/我记不清/.test(sp.replace(/不要用「我记不清」/g, '')),
    '不许把「看不到」说成「记不清」——那是两种不同的东西');
});

await t('recent_messages 返回值必须带窗口边界，且顶到上限时明说', async () => {
  const { listRecentMessages } = await import('./agent/feishu.mjs');
  const msgs = await listRecentMessages('oc_49a7cfb2861cffa4365ca8491f398d32', 5);
  if (msgs?.error) return; // 离线时不联网断言，避免测试依赖网络

  assert.ok(msgs.window, '必须带 window 字段：否则守衡说「第一次」时不知道自己只看到了一截');
  assert.strictEqual(msgs.window.returned, msgs.length);
  assert.strictEqual(msgs.window.atLimit, msgs.length >= 5);
  assert.ok(msgs.window.oldestAt, '必须给出窗口最早一条的时间');

  if (msgs.window.atLimit) {
    assert.ok(/第一次/.test(msgs.window.note), '顶到上限时必须提示「第一次」只在本窗口内成立');
  }

  // 撤回的消息必须带 recalled 标记，否则它和「一条短消息」长得一模一样
  const recalled = msgs.filter((m) => m.recalled);
  for (const m of recalled) {
    assert.ok(!/This message was recalled/.test(m.text), '英文占位符要换成人能读懂的说明');
    assert.ok(/撤回/.test(m.text), '撤回的消息要说明原文取不回');
  }
});

// 汇总必须放在所有分组之后：
// 之前它在第 5 组后就打印，报出的数字不含第 6 组 —— 一个会骗人的计数。
console.log(`\n═══ 合计：通过 ${pass} / 失败 ${fail} ═══`);
process.exit(fail > 0 ? 1 : 0);
