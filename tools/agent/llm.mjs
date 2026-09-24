/**
 * llm.mjs —— DeepSeek 调用层（OpenAI 兼容协议）
 *
 * 只做三件事：发请求、按错误类型重试、把用量记下来。
 * 不做业务判断 —— 业务判断在 agent.mjs。
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { config, LOG_DIR } from './config.mjs';

export const stats = {
  calls: 0, retries: 0, failures: 0,
  promptTokens: 0, completionTokens: 0, cachedTokens: 0,
  byModel: {},
};

/** 可重试的网络/限流错误 */
const RETRYABLE_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504]);

/**
 * 压缩纪要的 token 预算。
 *
 * ★ 为什么单独拎出来当常量、还写这么长一段：`900` 这个值**曾经在这里静默地吃掉历史**。
 *   本机模型是推理模型，`max_tokens` 同时盖住推理与正文；一份六万字的转录上，
 *   900 全被推理烧掉、正文返回空串，而 `summarize()` 把空串当成纪要返回，
 *   `compact()` 于是删掉旧对话、留下空纪要。**改这个数之前先看 `summarize()` 的注释。**
 *
 * 复现（本机，`node -e` 那条探针见 `PMO/守衡-误答登记-20260922.md` §九）：
 *   prompt_tokens=8252 · completion_tokens=900 · reasoning_tokens=900 · finish_reason=length
 */
const SUMMARIZE_MAX_TOKENS = 4000;

/* ─────────────── 「断在哪一层」：失败描述（2026-09-22 加，Q1-1a） ───────────────
 *
 * ★ 为什么必须有这一块。15:29 那次断网，守衡在群里说的是：
 *
 *     我这边调用模型失败了，没法回答这个问题。
 *     失败原因：网络错误: fetch failed
 *
 *   —— 而那句话出自本文件第 83 行那行模板字符串。Node 里 `fetch()` 失败抛的是
 *   **最外层**的一句 `TypeError: fetch failed`，真正的层在 `e.cause` 里。
 *   于是「DNS 挂了」和「对端 502」在群里长得一模一样，而这两者的下一步动作完全不同
 *   （前者查本机/路由器，后者查服务商状态页）。事后想再查一次也查不回来 —— cause 没存。
 *
 * 判据的形状（`AGENTS.md` §2.4.1：「这句话比我的输入大吗？」）：
 *   **层名必须可被机器断言，所以放在串的最前面**，而不是散在句子里等人去读。
 */

/** code → 层名。**封闭集合**，`LAYERS` 是它的值域，落盘/告警都只许出现这几个字。 */
const LAYER_BY_CODE = Object.freeze({
  ENOTFOUND: 'DNS', EAI_AGAIN: 'DNS', ENODATA: 'DNS', EAI_NODATA: 'DNS',
  ECONNREFUSED: 'TCP', ECONNRESET: 'TCP', ETIMEDOUT: 'TCP', EPIPE: 'TCP',
  EHOSTUNREACH: 'TCP', ENETUNREACH: 'TCP', ECONNABORTED: 'TCP', UND_ERR_SOCKET: 'TCP',
  CERT_HAS_EXPIRED: 'TLS', UNABLE_TO_VERIFY_LEAF_SIGNATURE: 'TLS',
  DEPTH_ZERO_SELF_SIGNED_CERT: 'TLS', SELF_SIGNED_CERT_IN_CHAIN: 'TLS',
  ERR_TLS_CERT_ALTNAME_INVALID: 'TLS', ERR_SSL_WRONG_VERSION_NUMBER: 'TLS',
  UND_ERR_CONNECT_TIMEOUT: '超时', UND_ERR_HEADERS_TIMEOUT: '超时',
  UND_ERR_BODY_TIMEOUT: '超时', ABORT_ERR: '超时',
});

export const LAYERS = Object.freeze(['DNS', 'TCP', 'TLS', '超时', 'HTTP', '未知']);

/** 一个 code 属于哪一层；不认识回 `null`（不许硬凑成某一层）。 */
export function layerOfCode(code) {
  return LAYER_BY_CODE[String(code ?? '')] ?? null;
}

/** 给测试与调用方看的：这一跳里哪些字段有意义（不认识的字段不许自己发明）。 */
const HOP_FIELDS = ['name', 'code', 'errno', 'syscall', 'hostname', 'address', 'port', 'message'];

/** 建一跳。**只保留白名单字段** —— 免得把 `headers` / `request` 那种大对象写进日志。 */
function hopOf(e, via) {
  const h = { via };
  for (const f of HOP_FIELDS) {
    const v = e?.[f];
    if (v === undefined || v === null || v === '') continue;
    h[f] = f === 'message' ? String(v).slice(0, 200) : (typeof v === 'object' ? String(v) : v);
  }
  return h;
}

/**
 * 沿 `cause` 链走到最深，把每一跳都收下来。
 *
 * 四条纪律：
 *   · **上限 6 跳 + 环检测** —— `cause` 是别人塞的，自引用的链会把这里变成死循环；
 *   · **`AggregateError.errors` 也要展开** —— 双栈（IPv6+IPv4）失败时 Node 抛的正是它，
 *     只看 `.cause` 会漏掉真正那一跳；
 *   · **链按「由深到浅」排** —— `chain[0]` 恒是断掉的那一层。这不只是好看：
 *     判据从此有一个**恒定的落点**（`chain[0].layer`），不必每轮扫全表猜哪个才是真因。
 *     最外层那句 `TypeError: fetch failed` 排在最末 —— 它是四种情况**共用**的一句话，
 *     信息量最低，本来就不该占着第一格。
 *   · 回的是**结构**（`chain`），不是一句话 —— 判据要比内容，不能比「文本里出现过」。
 */
export function describeError(e) {
  const hops = [];
  const seen = new Set();
  const queue = [{ e, via: 'root' }];
  while (queue.length && hops.length < 6) {
    const { e: cur, via } = queue.shift();
    if (!cur || typeof cur !== 'object' || seen.has(cur)) continue;
    seen.add(cur);
    hops.push(hopOf(cur, via));
    const subs = Array.isArray(cur.errors) ? cur.errors : [];
    if (subs.length) {
      for (const s of subs.slice(0, 4)) queue.push({ e: s, via: 'aggregate' });
      continue;                       // 有 errors 就不再往下走 cause：真正的那一跳在 errors 里
    }
    if (cur.cause && typeof cur.cause === 'object') queue.push({ e: cur.cause, via: 'cause' });
  }
  const chain = hops.reverse();       // ← 由深到浅

  // 每一跳自己能说清的层名；`chain[0]` 一格都不会空（它是结论的落点）。
  for (const h of chain) {
    const l = h.code ? layerOfCode(h.code) : null;
    if (l) h.layer = l;
  }
  const timedOut = chain.some((h) => h.name === 'AbortError' || /abort|timeout/i.test(h.message ?? ''));
  const deep = chain[0] ?? {};
  const layer = deep.layer ?? (timedOut ? '超时' : '未知');
  if (!deep.layer) deep.layer = layer;            // 兜底：chain[0].layer 必须有值
  const why = deep.code ?? deep.name ?? '无 code';

  const tail = [deep.syscall, deep.hostname, deep.address].filter(Boolean).join(' ');
  const summary = `${layer}/${why} · ${chain.length} 跳`
    + (tail ? ` · ${tail}` : '')
    + (deep.message ? ` :: ${deep.message}` : '');
  return { layer, why, hops: chain.length, chain, summary };
}

/** HTTP 层的失败也走同一条 `chain` 形状 —— 上层不必分两种情况读。`chain[0].layer` 恒有值。 */
export function httpChain(status, code, msg) {
  return [{ via: 'http', name: 'HTTPError', code: String(code ?? status), status, layer: 'HTTP',
            message: String(msg ?? '').slice(0, 200) }];
}

/** 一次失败的落点。★ **不写进外发台账** —— 台账的语义是「我说过什么」，不是「我坏过什么」。 */
export function failuresPath() {
  return process.env.SHOUHENG_LLM_FAILURES
    ? path.resolve(process.env.SHOUHENG_LLM_FAILURES)
    : path.join(LOG_DIR, 'llm_failures.jsonl');
}

/**
 * 记一行失败。**不抛** —— 记不上日志也必须让上层拿到 `ok:false` 继续走。
 * 密钥只留指纹（sha256 前 8 位），**正文里不许出现原文**。
 */
export function recordFailure(rec) {
  const rec2 = { at: new Date().toISOString(), ...rec };
  try {
    const f = failuresPath();
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.appendFileSync(f, JSON.stringify(rec2) + '\n');
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `${e.code ?? e.message}` };
  }
}

/** 密钥指纹：够用来分辨「换过 key 没有」，不够用来还原 key。 */
export function keyFingerprint(key = config.llm.apiKey) {
  return crypto.createHash('sha256').update(String(key ?? '')).digest('hex').slice(0, 8);
}

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
 *
 * ★ 失败体（2026-09-22 加，Q1-1a/1b）：`{ ok:false, error, layer, chain, attempts, retryable }`
 *   · `layer`      —— `DNS` / `TCP` / `TLS` / `超时` / `HTTP` / `未知`，**串在最前面**
 *   · `chain`      —— 沿 `cause` 走到的每一跳（上限 6），不是一句话
 *   · `attempts`   —— **每一次**尝试的错都留着，不只最后一次（原先前三次的 `e` 出了作用域就没了）
 *   · `retryable`  —— 只对可重试类入补发队列（HTTP 4xx 不入，见 `retry_queue.mjs` 的 C7）
 *   成功体**一个字段都不加** —— 正常路径不许产出 `error`/`chain`（闭嘴也是一种断言）。
 *
 * @returns {Promise<{ok:boolean, message?:object, finishReason?:string, usage?:object,
 *                    error?:string, layer?:string, chain?:Array, attempts?:Array, retryable?:boolean}>}
 */
export async function chat(messages, { tools, model = config.llm.model, maxTokens = config.llm.maxTokens,
                                       temperature = 0.3, jsonMode = false } = {}) {
  const body = { model, messages, max_tokens: maxTokens, temperature };
  if (tools?.length) { body.tools = tools; body.tool_choice = 'auto'; }
  if (jsonMode) body.response_format = { type: 'json_object' };

  const attempts = [];
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

      const code = res.json?.error?.code ?? res.status;
      const msg  = res.json?.error?.message ?? res.raw?.slice(0, 300) ?? `HTTP ${res.status}`;
      const retryable = RETRYABLE_STATUS.has(res.status);
      attempts.push({ n: attempt + 1, kind: 'http', status: res.status, code: String(code),
                      layer: 'HTTP', error: `HTTP ${res.status} code=${code}` });
      if (!retryable) {
        // 不可重试 → 立刻返回结构化错误，让上层能说清楚为什么失败
        stats.failures++;
        return finishFailure({ error: `HTTP ${res.status} code=${code}: ${msg}`, layer: 'HTTP',
                               chain: httpChain(res.status, code, msg), attempts, retryable: false,
                               model, baseUrl: config.llm.baseUrl });
      }
      if (attempt === 3) {
        stats.failures++;
        return finishFailure({ error: `重试耗尽 HTTP ${res.status} code=${code}: ${msg}`, layer: 'HTTP',
                               chain: httpChain(res.status, code, msg), attempts, retryable: true,
                               model, baseUrl: config.llm.baseUrl });
      }
    } catch (e) {
      const desc = describeError(e);
      const name = e?.name ?? '';
      const isTimeout = name === 'AbortError' || /aborted|timeout/i.test(e?.message ?? '');
      attempts.push({ n: attempt + 1, kind: 'transport', layer: desc.layer, why: desc.why,
                      code: desc.chain.find((h) => h.code)?.code ?? null,
                      error: `${isTimeout ? '请求超时' : '网络错误'}: ${e?.message ?? e}` });
      if (attempt === 3) {
        stats.failures++;
        return finishFailure({
          // ★ 层名在最前面：`DNS/ENOTFOUND · …`。**不许**再把四种情况写成同一句 `网络错误: fetch failed`。
          error: `${desc.layer} 层失败（${isTimeout ? '请求超时' : '网络错误'}）：${desc.summary}`,
          layer: desc.layer, chain: desc.chain, attempts, retryable: true,
          model, baseUrl: config.llm.baseUrl });
      }
    }
  }
  stats.failures++;
  return finishFailure({ error: '未知失败（循环意外退出）', layer: '未知', chain: [], attempts,
                         retryable: false, model, baseUrl: config.llm.baseUrl });
}

/** 收口：**一次失败恰好落一行** `llm_failures.jsonl`（原先哪里都不留痕）。 */
function finishFailure({ error, layer, chain, attempts, retryable, model, baseUrl }) {
  const out = { ok: false, error, layer, chain, attempts, retryable };
  recordFailure({ model, base_url: baseUrl, layer, retryable, n_attempts: attempts.length,
                  attempts, chain, key_fp: keyFingerprint() });
  return out;
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
 *
 * ── ★ 2026-09-22：这个函数的**失败方式**比它的成功方式更值得写下来
 *
 * 它原先写的是 `return r.message?.content ?? ''` —— 于是当上游返回一个**空 content**
 * 时，它安安静静地返回 `''`，`compact()` 把这当成一份「纪要」写进 `sess.summary`，
 * **然后把整天旧对话删掉**。盘上的证据：三个会话的 `summary` 全是 0 长度，
 * 而日志里印了 8 次「保留 N 轮 **+ 纪要**」。
 *
 * 空 content 是怎么来的（本机实测，不是推断）：
 *
 * ```
 * prompt_tokens=8252  completion_tokens=900  reasoning_tokens=900  ← 全部
 * finish_reason="length"      content 长度 = 0
 * ```
 *
 * 本机模型是**推理模型**，`max_tokens` 同时盖住推理与正文。`900` 对一份
 * 六万字的转录来说太紧：推理把它烧光，正文一个字都没轮上。而 `chat()` 看的是
 * `res.ok && choices.length` —— **HTTP 通、choice 在，就算成功**，
 * `finish_reason` 根本没人读。
 *
 * 同一个输入连跑两次，一次返回 0 字、一次返回 245 字 —— 这是一个
 * **在 token 边界上不确定的静默失败**，正是 §2.4.1 那个形状：
 * 接口通了、`code=0`、没报错，而产出的是假数据（这里是「一份空纪要」，比假数据更坏，
 * 因为它的代价是**旧对话被删掉**）。
 *
 * 三处一起改，缺一处都还会丢：
 *   ① 预算 `900 → 4000`（推理 + 正文都要装得下）；
 *   ② **空的 = 失败**，抛错而不是返回 `''`；
 *   ③ `finish_reason === 'length'` 单独说清楚，别与「模型就是没话说」混为一谈。
 * 最后一道闸在 `memory.mjs` 的 `compact()`（纪要空就不许删历史）—— 那是**独立**的，
 * 因为「宁可长着，也不要丢」这条判据不该依赖 summarize 的行为。
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
      `5. 若已有旧纪要，把它与新内容合并成一份，不要出现两段重复的纪要。\n` +
      `6. 这段对话若确实没有任何可记的内容，就回一行「（本段无可记内容）」—— **不要**返回空。` },
    { role: 'user', content:
      `${existingSummary ? `【已有纪要】\n${existingSummary}\n\n` : ''}【需要压缩的对话】\n${transcript}` },
  ], { maxTokens: SUMMARIZE_MAX_TOKENS, temperature: 0 });

  if (!r.ok) throw new Error(r.error);

  const text = String(r.message?.content ?? '').trim();
  if (!text) {
    // ★ 不许返回空串。空串是「压缩成功但什么都没留下」—— 调用方会把旧对话删掉。
    const rt = r.usage?.completion_tokens_details?.reasoning_tokens ?? '?';
    throw new Error(
      r.finishReason === 'length'
        ? `纪要为空：预算 ${SUMMARIZE_MAX_TOKENS} token 被推理吃光（reasoning ${rt}），正文没轮上`
        : `纪要为空：模型返回了空 content（finish_reason=${r.finishReason ?? '?'}）`
    );
  }
  return text;
}
