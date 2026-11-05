/**
 * llm.mjs —— 对话层调用（OpenAI 兼容协议）
 *
 * 只做三件事：发请求、按错误类型重试、把用量记下来。
 * 不做业务判断 —— 业务判断在 agent.mjs。
 *
 * 两个中转站共 7 个模型：`vod` 站（Gemini 4 个，五模态全通）为主，
 * `tokenhub` 站（GLM / MiniMax 3 个，无 audio）为异构兜底。DeepSeek 已下线。
 * 地址与 key 的解析只此一处（`resolveModelEndpoint`）。
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {
  config, LOG_DIR, VOD_BASE_URL, MAGPIE_LOCAL_BASE_URL, TOKENHUB_BASE_URL,
} from './config.mjs';

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

async function post(pathname, body, { timeoutMs = 120_000, baseUrl, apiKey } = {}) {
  const url = `${String(baseUrl ?? config.llm.baseUrl).replace(/\/$/, '')}${pathname}`;
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey ?? config.llm.apiKey}` },
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
export async function chat(messages, opts = {}) {
  const {
    tools, model = config.llm.model, maxTokens = config.llm.maxTokens,
    temperature = 0.3, jsonMode = false, maxRetries = null, endpoint = null,
  } = opts;
  const body = { model, messages, max_tokens: maxTokens, temperature };
  if (tools?.length) { body.tools = tools; body.tool_choice = 'auto'; }
  if (jsonMode) body.response_format = { type: 'json_object' };

  // 地址与 key 由模型决定，不由调用点决定 —— 一处解析，两个出口（chat / chatWithFallback）共用。
  const ep = endpoint ?? resolveModelEndpoint(model);
  body.model = ep.model;

  // ★ 回落链里每换一个模型就重试 4 次，等于一次回复最多要等 7×4 个退避周期。
  //   所以 `chatWithFallback` 传 1：单模型只试一次，快失败、快换站。
  const maxAttempt = Number.isFinite(maxRetries) ? Math.max(0, maxRetries) : 3;

  const attempts = [];
  let delay = 800;
  for (let attempt = 0; attempt <= maxAttempt; attempt++) {
    if (attempt > 0) { stats.retries++; await new Promise((r) => setTimeout(r, delay)); delay *= 2; }
    stats.calls++;
    try {
      const res = await post('/chat/completions', body, { baseUrl: ep.baseUrl, apiKey: ep.apiKey });

      if (res.ok && res.json?.choices?.length) {
        recordUsage(body.model, res.json.usage);
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
                               model: body.model, baseUrl: ep.baseUrl });
      }
      if (attempt === maxAttempt) {
        stats.failures++;
        return finishFailure({ error: `重试耗尽 HTTP ${res.status} code=${code}: ${msg}`, layer: 'HTTP',
                               chain: httpChain(res.status, code, msg), attempts, retryable: true,
                               model: body.model, baseUrl: ep.baseUrl });
      }
    } catch (e) {
      const desc = describeError(e);
      const name = e?.name ?? '';
      const isTimeout = name === 'AbortError' || /aborted|timeout/i.test(e?.message ?? '');
      attempts.push({ n: attempt + 1, kind: 'transport', layer: desc.layer, why: desc.why,
                      code: desc.chain.find((h) => h.code)?.code ?? null,
                      error: `${isTimeout ? '请求超时' : '网络错误'}: ${e?.message ?? e}` });
      if (attempt === maxAttempt) {
        stats.failures++;
        return finishFailure({
          // ★ 层名在最前面：`DNS/ENOTFOUND · …`。**不许**再把四种情况写成同一句 `网络错误: fetch failed`。
          error: `${desc.layer} 层失败（${isTimeout ? '请求超时' : '网络错误'}）：${desc.summary}`,
          layer: desc.layer, chain: desc.chain, attempts, retryable: true,
          model: body.model, baseUrl: ep.baseUrl });
      }
    }
  }
  stats.failures++;
  return finishFailure({ error: '未知失败（循环意外退出）', layer: '未知', chain: [], attempts,
                         retryable: false, model: body.model, baseUrl: ep.baseUrl });
}

/** 收口：**一次失败恰好落一行** `llm_failures.jsonl`（原先哪里都不留痕）。 */
function finishFailure({ error, layer, chain, attempts, retryable, model, baseUrl, apiKey }) {
  const out = { ok: false, error, layer, chain, attempts, retryable, model };
  recordFailure({ model, base_url: baseUrl, layer, retryable, n_attempts: attempts.length,
                  attempts, chain, key_fp: keyFingerprint(apiKey ?? config.llm.apiKey) });
  return out;
}

/**
 * 主流梯队（本机 magpie 的 `vod` 站：五模态全通，text/image/audio/video/pdf + tool_call）。
 *
 * ★ 顺序 = 回落顺序。前两个是日常主力（快、便宜），3.7/3.8 是「前两个都 429 时的备胎」。
 */
export const VOD_MODELS = Object.freeze([
  'gemini-3.1-flash-lite',
  'gemini-3.5-flash',
  'gemini-3.7-flash',
  'gemini-3.8-flash',
]);

/**
 * 异构兜底梯队（tokenhub / magpie 站：text/image/video + tool_call，**不含 audio**）。
 *
 * ★ 「异构」是这一梯队存在的理由：主流四个全是同一家 Gemini，同一次上游故障会一起挂。
 *   GLM 与 MiniMax 是另一家，故障面不重合。
 * ★ 不含 audio 是硬事实，不是偏好：`glm-5.3-flash` 在清单里 `audio: 0`。
 *   所以视频的音画对齐**只能**走 VOD —— 见 `base/feishu_guard_ingest.py` 的 `VIDEO_FOUR_DIM_CHAIN`。
 */
export const TOKENHUB_MODELS = Object.freeze([
  'glm-5.3-flash',
  'minimax-m3.1-flash',
  'glm-5.3-flashx',
]);

/**
 * 完整 7 模型主备回落链：主流 4 个 VOD Gemini → 兜底 3 个 GLM / MiniMax。
 *
 * ★ DeepSeek 已彻底废弃（2026-11-06）。它不是「暂时不用」，是从这条链上删除：
 *   链上留一个已停用的模型，等于每次回落都先浪费一次超时。
 */
export const FALLBACK_MODELS = Object.freeze([
  ...VOD_MODELS,
  ...TOKENHUB_MODELS,
]);

/** 一个模型属于哪一站。`null` = 不认识的模型（不许猜站，猜错就是一次 404）。 */
export function stationOf(model) {
  const m = String(model ?? '').trim();
  const bare = m.includes('/') ? m.slice(m.indexOf('/') + 1) : m;
  if (m.startsWith('vod/') || VOD_MODELS.includes(bare) || bare.startsWith('gemini-')) return 'vod';
  if (m.startsWith('tokenhub/') || TOKENHUB_MODELS.includes(bare)
      || bare.startsWith('glm-') || bare.startsWith('minimax-')) return 'tokenhub';
  return null;
}

/**
 * 「主站地址是否由人接管」。
 *
 * ★ 读**当前值**，不读加载时冻结的 `config.llm.baseUrlOverridden`。两者差一次事故：
 *   那个标志在 import 期就固定了，而测试与运维脚本是在**运行期**改 `config.llm.baseUrl`
 *   把请求指向本机回环的。用冻结标志判，改过的 baseUrl 会被当成「未接管」，
 *   于是请求被重新分派到 VOD 真地址 —— 而现场看起来像「回环假服务器没被访问到」。
 *
 * ★ 比的是**模块常量**，不是 `cfg.vodBaseUrl` / `cfg.magpieBaseUrl`。后者是各站的
 *   **路由目标**，会被调用方按站改写（自证把某站指到回环假服务器就是这么做的）；
 *   拿可变字段当「默认值」比，改写一个站就会被误判成「有人接管了主站」，
 *   于是全部模型挤到同一个地址 —— 分站逻辑静默失效，而整条链看起来还在跑。
 */
function isBaseUrlOverridden(cfg) {
  if (cfg.baseUrlOverridden) return true;
  const cur = String(cfg.baseUrl ?? '').replace(/\/$/, '');
  if (!cur) return false;
  const stationDefaults = [VOD_BASE_URL, MAGPIE_LOCAL_BASE_URL, TOKENHUB_BASE_URL]
    .map((u) => String(u ?? '').replace(/\/$/, ''));
  return !stationDefaults.includes(cur);
}

/**
 * 模型 → `{ baseUrl, apiKey, model }`。**纯函数**，不碰网络、不读环境变量。
 *
 * 三条规则：
 *   1. 调方显式指定了 `SHOUHENG_LLM_BASE_URL` → 全部走它（有人接管，就不再分站）；
 *   2. `vod` 站有 key → 直连 VOD；没 key → 走本机 magpie 代理，模型名加 `vod/` 前缀
 *      （代理靠前缀选上游站）；
 *   3. `tokenhub` 站有 key 且**显式要直连**才走官方地址；默认走本机 magpie 代理由带裸模型名。
 *      理由是实测：官方直连今天对 `glm-5.3-flash` 回 402（免费额度耗尽），代理回 200。
 *
 * ★ 为什么「没 key 时不发请求」也算一条规则：`Authorization: Bearer ` 空串换回来的
 *   永远是 401，而 401 会让整条链在第一个模型就停下 —— 看起来像「所有模型都坏了」。
 */
export function resolveModelEndpoint(model, cfg = config.llm) {
  const raw = String(model ?? '').trim() || String(cfg.model ?? '').trim();
  if (isBaseUrlOverridden(cfg)) {
    return { baseUrl: cfg.baseUrl, apiKey: cfg.apiKey, model: raw, station: stationOf(raw) };
  }
  const station = stationOf(raw);
  const bare = raw.includes('/') ? raw.slice(raw.indexOf('/') + 1) : raw;

  if (station === 'tokenhub') {
    if (cfg.tokenhubApiKey) {
      return { baseUrl: cfg.tokenhubBaseUrl, apiKey: cfg.tokenhubApiKey, model: bare, station };
    }
    return { baseUrl: cfg.magpieBaseUrl, apiKey: 'magpie', model: bare, station };
  }
  // 认不出的模型按主流站处理：默认站是 VOD，把模型名原样交给它比拒答更有用。
  if (cfg.vodApiKey) {
    return { baseUrl: cfg.vodBaseUrl, apiKey: cfg.vodApiKey, model: bare, station: station ?? 'vod' };
  }
  return { baseUrl: cfg.magpieBaseUrl, apiKey: 'magpie', model: `vod/${bare}`, station: station ?? 'vod' };
}

/**
 * 全链回落：7 个模型按 `FALLBACK_MODELS` 顺序试，第一个成功的胜出。
 *
 * ── ★ 这里原先有一个把整条链掐断的分支，2026-11-06 删掉
 *
 * 原代码在每次失败后读最后一次尝试的 HTTP 状态，`401/402/403` 时直接 `break`，
 * 注释写的是「整把 Key 没钱或失效，换同网关另一个模型也一样」。
 * 那句话在**单网关**时代成立；换成两站 7 模型之后它就不成立了，而且是**反的**：
 *
 *   · `vod` 直连 402（这一站余额耗尽）时，`tokenhub/magpie` 那三个模型**完全可用**；
 *   · 那个 `break` 让它们一次都没被试过，整条链在第一个模型就返回失败，
 *     上层于是走本地引擎兜底 —— 群里看到的是「模型全挂了」，而实际上有 3 个活的。
 *
 * 所以现在的判据是**按站**而不是按状态码：一站被判死就跳过该站剩下的模型，
 * 继续下一站。换站这件事必须发生，否则「异构兜底」只是配置里的一句装饰。
 *
 * ★ 跨站成功时 `modelUsed` / `stationUsed` / `fallbackFrom` 三个字段都要留：
 *   没有它们，「这次结论是哪一版模型给的」在报告里查不出来。
 */
export async function chatWithFallback(messages, opts = {}) {
  const primary = opts.model || config.llm.model;
  const chain = [primary, ...FALLBACK_MODELS.filter((m) => m !== primary)];
  let lastRes = null;
  const deadStations = new Set();     // 401/402/403 = 凭据/额度层面，换同站模型不会好
  const tried = [];

  for (const model of chain) {
    const ep = resolveModelEndpoint(model, config.llm);
    const station = ep.station ?? stationOf(model) ?? 'unknown';
    if (deadStations.has(station)) {
      tried.push({ model, station, skipped: 'station_dead' });
      continue;
    }
    const r = await chat(messages, { ...opts, model, endpoint: ep, maxRetries: 1 });
    tried.push({ model, station, ok: r.ok, status: r.attempts?.[r.attempts.length - 1]?.status ?? null });
    if (r.ok) {
      return { ...r, modelUsed: model, stationUsed: station, fallbackFrom: tried.slice(0, -1) };
    }
    lastRes = r;
    const status = r.attempts?.[r.attempts.length - 1]?.status;
    if (status === 401 || status === 402 || status === 403) deadStations.add(station);
  }
  return { ...lastRes, triedAll: tried };
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
      `你在为「Guard」这个飞书智能体维护对话记忆。把给定的对话压成简洁纪要。\n` +
      `硬性要求：\n` +
      `1. 只记录对话中**确实出现过**的事实、决定、承诺、待办、以及对方的偏好。不要推测，不要补充。\n` +
      `2. 保留具体标识：人名、群名、文件路径、ID、时间、数字，原样抄录，不要概括成「某个文件」。\n` +
      `3. 如果 Guard 在对话中承认过错误或做过承诺，必须保留 —— 这是最不能丢的部分。\n` +
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
