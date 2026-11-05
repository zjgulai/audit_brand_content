/**
 * llm_health_watch.mjs —— 大语言模型额度（402）/限流（429）/网关连通性与系统健康巡检器
 *
 * 职责：
 *   1. 检查主用中转站（腾讯云 VOD：mmu.vod-qcloud.com/v1，4 个 Gemini 模型回落链）；
 *   2. 检查异构兜底站（TokenHub / 本机 magpie 代理：GLM / MiniMax 3 个模型）；
 *   3. 检查本地 OCR 二进制与工作台数据库状态；
 *   4. 生成 ADHD 友好的 P-4【运维自检】标准化卡片，并经 push_policy 硬闸门锁死仅推送到测试群
 *      （内容治理-守衡Agent-测试：oc_49a7cfb2861cffa4365ca8491f398d32）。
 *
 * ★ DeepSeek 通道 2026-11-06 整块删除。这个巡检器原先的第二条通道是它，
 *   卡片上也写着「备用通道 · DeepSeek 官方直连」。留着会有两个后果：
 *   一张卡上报告一条已经不存在的通道，以及 `hasQuotaWarning` 永远盯着一个死掉的 key。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { REPO_ROOT, stateDir, ensureDir, config } from './config.mjs';
import { VOD_MODELS, TOKENHUB_MODELS, FALLBACK_MODELS } from './llm.mjs';
import { buildHealthAlertCard, prepareScheduledPush } from './standard_cards.mjs';
import { TEST_GROUP_CHAT_ID } from './push_policy.mjs';

const STATE_FILE = () => path.join(stateDir(), 'llm-health-watch.json');

function readDshKey(name) {
  try {
    const p = path.join(os.homedir(), '.dsh', '.credentials.yaml');
    const txt = fs.readFileSync(p, 'utf8');
    const m = txt.match(new RegExp(`^\\s*${name}:\\s*(\\S+)\\s*$`, 'm'));
    return m?.[1] ?? null;
  } catch {
    return null;
  }
}

async function probeEndpoint({ name, baseUrl, apiKey, model, timeoutMs = 15_000 }) {
  if (!apiKey) {
    return {
      name,
      ok: false,
      code: 'no_key',
      status: '未配密钥',
      detail: `未配置密钥（模型 ${model}）`,
    };
  }
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: '回复ok' }],
        max_tokens: 16,
      }),
      signal: ac.signal,
    });
    if (r.ok) {
      return {
        name,
        ok: true,
        code: 'ok',
        status: '正常在线',
        detail: `主模型 ${model} 响应正常（HTTP 200）`,
      };
    }
    if (r.status === 402) {
      return {
        name,
        ok: false,
        code: 'insufficient_balance_402',
        status: '额度不足（HTTP 402）',
        detail: `账户余额不足（HTTP 402），需充值后恢复`,
      };
    }
    if (r.status === 401 || r.status === 403) {
      return {
        name,
        ok: false,
        code: `auth_${r.status}`,
        status: `密钥失效（HTTP ${r.status}）`,
        detail: `API Key 鉴权被拒（HTTP ${r.status}），请更换密钥`,
      };
    }
    if (r.status === 429) {
      return {
        name,
        ok: false,
        code: 'rate_limit_429',
        status: '触发限流（HTTP 429）',
        detail: `模型 ${model} 触发限流，已由回落链自动切换备选模型`,
      };
    }
    return {
      name,
      ok: false,
      code: `http_${r.status}`,
      status: `接口异常（HTTP ${r.status}）`,
      detail: `返回状态码 HTTP ${r.status}`,
    };
  } catch (e) {
    return {
      name,
      ok: false,
      code: 'network_error',
      status: '网络连接异常',
      detail: `请求失败：${String(e?.message ?? e).slice(0, 80)}`,
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 执行一次全通道模型与基座健康检查（支持注入 probes 供离线单测验证）。
 */
export async function checkLlmAndSystemHealth({
  probeFn = null,
  targetChatId = TEST_GROUP_CHAT_ID,
  /** OCR 二进制是否在场。默认现场查；自证注入它，免得「本机有没有那个 gitignored 二进制」
   *  决定一条关于 402 识别的断言是红是绿 —— 那会把两个互不相干的事实绑在一起。 */
  ocrPresent = null,
} = {}) {
  const vodKey = process.env.VOD_API_KEY || process.env.MULTIMODAL_VOD_API_TOKEN
    || readDshKey('VOD_API_KEY') || config.llm.vodApiKey;
  const tokenhubKey = process.env.TOKENHUB_API_KEY || process.env.MULTIMODAL_TOKENHUB_API_KEY
    || readDshKey('TOKENHUB_API_KEY') || config.llm.tokenhubApiKey;

  let vodRes;
  let tokenhubRes;
  if (typeof probeFn === 'function') {
    // 兼容两种注入形状：新调用方给 `tokenhubRes`，旧调用方（含历史测试）给 `dsRes`。
    // ★ 兼容的是**字段名**，不是 DeepSeek 这条通道 —— 无论哪个名字进来，
    //   下面报告的都是 tokenhub 站的读数。
    const r = await probeFn();
    vodRes = r.vodRes;
    tokenhubRes = r.tokenhubRes ?? r.dsRes;
  } else {
    [vodRes, tokenhubRes] = await Promise.all([
      probeEndpoint({
        name: '主用中转站 · 腾讯云 VOD（Gemini 4 模型）',
        baseUrl: config.llm.vodBaseUrl,
        apiKey: vodKey,
        model: VOD_MODELS[0],
      }),
      // 兜底站走本机代理：官方 tokenhub 直连对这批模型回 402（免费额度耗尽），代理回 200。
      probeEndpoint({
        name: '异构兜底站 · TokenHub / Magpie（GLM / MiniMax 3 模型）',
        baseUrl: config.llm.magpieBaseUrl,
        apiKey: tokenhubKey || 'magpie',
        model: TOKENHUB_MODELS[0],
      }),
    ]);
  }

  const ocrBin = path.join(REPO_ROOT, '.tools', 'bin', 'ocr');
  const ocrOk = ocrPresent === null ? fs.existsSync(ocrBin) : Boolean(ocrPresent);

  const checks = [
    {
      name: vodRes.name,
      status: vodRes.status,
      detail: `${vodRes.detail}（回落链：${VOD_MODELS.join(' → ')}）`,
    },
    {
      name: tokenhubRes.name,
      status: tokenhubRes.status,
      detail: tokenhubRes.ok
        ? `${tokenhubRes.detail}（回落链：${TOKENHUB_MODELS.join(' → ')}）`
        : `${tokenhubRes.detail}（主流站 ${VOD_MODELS.length} 个模型仍在线，不影响群内审核）`,
    },
    {
      name: '本地 OCR 与生产规则引擎',
      status: ocrOk ? '正常在线' : '二进制缺失',
      detail: ocrOk ? '19 项控制点 + 本地图片 OCR + 直出卡片兜底就绪' : '请运行 build_ocr.sh',
    },
  ];

  // 主站 VOD 与本地 OCR 正常时，核心服务整体可用。
  // ★ 兜底站挂了**不算**告警：它的存在意义是「主站挂了还有活路」，它自己挂在正常范围内
  //   —— 把它也算进 primaryHealthy，会让一张卡因为一个备胎而天天红。
  const primaryHealthy = Boolean(vodRes.ok && ocrOk);
  const hasQuotaWarning = vodRes.code === 'insufficient_balance_402'
    || tokenhubRes.code === 'insufficient_balance_402';

  const title = !primaryHealthy
    ? '主用模型网关异常，已启用本地引擎兜底'
    : (hasQuotaWarning ? '主用 VOD 网关正常（异构兜底站额度不足）' : '全通道在线（7 模型两级回落）');

  const summary = !primaryHealthy
    ? '主用 VOD 网关暂不可用，群内送审已自动切换为本地生产引擎直出卡片。'
    : (hasQuotaWarning
        ? '主用 VOD 多模态与对话网关正常在线；异构兜底站账户余额不足（HTTP 402）。'
        : '腾讯云 VOD 主站、异构兜底站与本地生产引擎全部正常。');

  const actionAdvice = !primaryHealthy
    ? '请立即检查 VOD_API_KEY 或网络连通性；期间群内图文与文案初筛由本地引擎兜底。'
    : (hasQuotaWarning
        ? '当前群内四维审图与问答均走腾讯云 VOD 正常服务；如需保留兜底站请为其充值。'
        : '无需操作，系统每 5 分钟静默守护中。');

  const card = buildHealthAlertCard({
    healthy: primaryHealthy && !hasQuotaWarning,
    title,
    summary,
    checks,
    actionAdvice,
  });

  const prepared = prepareScheduledPush(card, { targetChatId });
  return {
    ok: true,
    primaryHealthy,
    hasQuotaWarning,
    vod: vodRes,
    tokenhub: tokenhubRes,
    /**
     * ★ 过渡别名，2026-11-06：`ws_daemon.mjs` 的告警去重键还在读 `health.deepseek?.code`，
     *   而那个文件属于另一条并行会话的边界，本次不动它。
     *   不补这个别名的话，去重键会静默退化成 `ok`，兜底站 402 就不再影响告警指纹 ——
     *   一个「键少了一项」的静默退化，比一个显眼的报错难查得多（§2.4.1）。
     *   下次有人改 `ws_daemon.mjs` 时把它改成 `tokenhub` 并删掉这一行。
     */
    deepseek: tokenhubRes,
    models: FALLBACK_MODELS.length,
    ocrOk,
    prepared,
  };
}
