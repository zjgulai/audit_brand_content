/**
 * llm.mjs —— DeepSeek 调用层（OpenAI 兼容协议）
 *
 * 只做三件事：发请求、按错误类型重试、把用量记下来。
 * 不做业务判断 —— 业务判断在 agent.mjs。
 */
import { config } from './config.mjs';

export const stats = {
  calls: 0, retries: 0, failures: 0,
  promptTokens: 0, completionTokens: 0, cachedTokens: 0,
  byModel: {},
};

/** 可重试的网络/限流错误 */
const RETRYABLE_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504]);

async function post(pathname, body, { timeoutMs = 120_000 } = {}) {
  const url = `${config.llm.baseUrl.replace(/\/$/, '')}${pathname}`;
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${config.llm.apiKey}` },
      body: JSON.stringify(body),
      signal: ac.signal,
    });
    const text = await r.text();
    let json = null;
    try { json = JSON.parse(text); } catch { /* 非 JSON 响应 */ }
    return { status: r.status, ok: r.ok, json, raw: text };
  } finally { clearTimeout(timer); }
}

function recordUsage(model, usage) {
  if (!usage) return;
  stats.promptTokens     += usage.prompt_tokens ?? 0;
  stats.completionTokens += usage.completion_tokens ?? 0;
  stats.cachedTokens     += usage.prompt_cache_hit_tokens ?? usage.prompt_tokens_details?.cached_tokens ?? 0;
  stats.byModel[model] ??= { calls: 0, promptTokens: 0, completionTokens: 0 };
  stats.byModel[model].calls++;
  stats.byModel[model].promptTokens     += usage.prompt_tokens ?? 0;
  stats.byModel[model].completionTokens += usage.completion_tokens ?? 0;
}

/**
 * 一次对话补全。失败按指数退避重试 3 次，仅对可重试错误重试。
 * @returns {Promise<{ok:boolean, message?:object, finishReason?:string, usage?:object, error?:string}>}
 */
export async function chat(messages, { tools, model = config.llm.model, maxTokens = config.llm.maxTokens,
                                       temperature = 0.3, jsonMode = false } = {}) {
  const body = { model, messages, max_tokens: maxTokens, temperature };
  if (tools?.length) { body.tools = tools; body.tool_choice = 'auto'; }
  if (jsonMode) body.response_format = { type: 'json_object' };

  let delay = 800;
  for (let attempt = 0; attempt <= 3; attempt++) {
    if (attempt > 0) { stats.retries++; await new Promise((r) => setTimeout(r, delay)); delay *= 2; }
    stats.calls++;
    try {
      const res = await post('/chat/completions', body);

      if (res.ok && res.json?.choices?.length) {
        recordUsage(model, res.json.usage);
        const choice = res.json.choices[0];
        return { ok: true, message: choice.message, finishReason: choice.finish_reason, usage: res.json.usage };
      }

      // 不可重试 → 立刻返回结构化错误，让上层能说清楚为什么失败
      const code = res.json?.error?.code ?? res.status;
      const msg  = res.json?.error?.message ?? res.raw?.slice(0, 300) ?? `HTTP ${res.status}`;
      if (!RETRYABLE_STATUS.has(res.status) && attempt >= 0 && !RETRYABLE_STATUS.has(res.status)) {
        stats.failures++;
        return { ok: false, error: `HTTP ${res.status} code=${code}: ${msg}` };
      }
      if (attempt === 3) { stats.failures++; return { ok: false, error: `重试耗尽 HTTP ${res.status} code=${code}: ${msg}` }; }
    } catch (e) {
      const name = e?.name ?? '';
      const isTimeout = name === 'AbortError' || /aborted|timeout/i.test(e?.message ?? '');
      if (attempt === 3) {
        stats.failures++;
        return { ok: false, error: `${isTimeout ? '请求超时' : '网络错误'}: ${e?.message ?? e}` };
      }
    }
  }
  stats.failures++;
  return { ok: false, error: '未知失败（循环意外退出）' };
}

/** 便捷：纯文本问答，无工具 */
export async function ask(prompt, { system, maxTokens = 800, model = config.llm.model } = {}) {
  const messages = [];
  if (system) messages.push({ role: 'system', content: system });
  messages.push({ role: 'user', content: prompt });
  const r = await chat(messages, { model, maxTokens, temperature: 0.2 });
  return r.ok ? (r.message?.content ?? '') : `〔LLM 调用失败〕${r.error}`;
}

/**
 * 把旧对话压成纪要。这是记忆层 compact() 的默认实现。
 * 刻意用低温度 + 明确格式要求，避免纪要本身产生幻觉 ——
 * 纪要一旦失真，守衡会「确信地记错」，比忘记更糟。
 */
export async function summarize(oldMessages, existingSummary = '') {
  const transcript = oldMessages.map((m) => {
    const who = m.name ? `${m.role}(${m.name})` : m.role;
    const body = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
    return `${who}: ${String(body).slice(0, 1200)}`;
  }).join('\n');

  const r = await chat([
    { role: 'system', content:
      `你在为「守衡」这个飞书智能体维护对话记忆。把给定的对话压成简洁纪要。\n` +
      `硬性要求：\n` +
      `1. 只记录对话中**确实出现过**的事实、决定、承诺、待办、以及对方的偏好。不要推测，不要补充。\n` +
      `2. 保留具体标识：人名、群名、文件路径、ID、时间、数字，原样抄录，不要概括成「某个文件」。\n` +
      `3. 如果守衡在对话中承认过错误或做过承诺，必须保留 —— 这是最不能丢的部分。\n` +
      `4. 用中文，条目式，不要寒暄。\n` +
      `5. 若已有旧纪要，把它与新内容合并成一份，不要出现两段重复的纪要。` },
    { role: 'user', content:
      `${existingSummary ? `【已有纪要】\n${existingSummary}\n\n` : ''}【需要压缩的对话】\n${transcript}` },
  ], { maxTokens: 900, temperature: 0 });

  if (!r.ok) throw new Error(r.error);
  return r.message?.content ?? '';
}
