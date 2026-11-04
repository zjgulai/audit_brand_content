/**
 * llm_health_watch.mjs —— 大语言模型额度（402）/限流（429）/网关连通性与系统健康巡检器
 *
 * 职责：
 *   1. 检查主用中转站（腾讯云 VOD：mmu.vod-qcloud.com/v1，模型回落链 gemini-3.1-flash-lite → 3.5-flash → 3.8-flash）；
 *   2. 检查备用直连通道（DeepSeek 官方：api.deepseek.com，识出 HTTP 402 余额不足等状态）；
 *   3. 检查本地 OCR 二进制与工作台数据库状态；
 *   4. 生成 ADHD 友好的 P-4【运维自检】标准化卡片，并经 push_policy 硬闸门锁死仅推送到测试群
 *      （内容治理-守衡Agent-测试：oc_49a7cfb2861cffa4365ca8491f398d32）。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { REPO_ROOT, stateDir, ensureDir } from './config.mjs';
import { FALLBACK_MODELS } from './llm.mjs';
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
} = {}) {
  const vodKey = process.env.VOD_API_KEY || process.env.MULTIMODAL_VOD_API_TOKEN || readDshKey('VOD_API_KEY');
  const dsKey = process.env.DEEPSEEK_API_KEY || readDshKey('DEEPSEEK_API_KEY');

  let vodRes;
  let dsRes;
  if (typeof probeFn === 'function') {
    ({ vodRes, dsRes } = await probeFn());
  } else {
    [vodRes, dsRes] = await Promise.all([
      probeEndpoint({
        name: '主用网关 · 腾讯云 VOD（多模态+对话）',
        baseUrl: 'https://mmu.vod-qcloud.com/v1',
        apiKey: vodKey,
        model: FALLBACK_MODELS[0],
      }),
      probeEndpoint({
        name: '备用通道 · DeepSeek 官方直连',
        baseUrl: 'https://api.deepseek.com',
        apiKey: dsKey,
        model: 'deepseek-flash',
      }),
    ]);
  }

  const ocrBin = path.join(REPO_ROOT, '.tools', 'bin', 'ocr');
  const ocrOk = fs.existsSync(ocrBin);

  const checks = [
    {
      name: vodRes.name,
      status: vodRes.status,
      detail: `${vodRes.detail}（回落链：${FALLBACK_MODELS.join(' → ')}）`,
    },
    {
      name: dsRes.name,
      status: dsRes.status,
      detail: dsRes.ok
        ? dsRes.detail
        : `${dsRes.detail}（当前已由腾讯云 VOD 主网关全权接管，不影响群内审核）`,
    },
    {
      name: '本地 OCR 与生产规则引擎',
      status: ocrOk ? '正常在线' : '二进制缺失',
      detail: ocrOk ? '19 项控制点 + 本地图片 OCR + 直出卡片兜底就绪' : '请运行 build_ocr.sh',
    },
  ];

  // 主网关 VOD 与本地 OCR 正常时，核心服务整体可用；但若有任意通道 402 余额不足则明确提示运维
  const primaryHealthy = Boolean(vodRes.ok && ocrOk);
  const hasQuotaWarning = vodRes.code === 'insufficient_balance_402' || dsRes.code === 'insufficient_balance_402';

  const title = !primaryHealthy
    ? '主用模型网关异常，已启用本地引擎兜底'
    : (hasQuotaWarning ? '主用 VOD 网关正常（备用 DeepSeek 余额不足）' : '全通道在线（含 3 级模型自动回落）');

  const summary = !primaryHealthy
    ? '主用 VOD 网关暂不可用，群内送审已自动切换为本地生产引擎直出卡片。'
    : (hasQuotaWarning
        ? '主用 VOD 多模态与对话网关正常在线；备用 DeepSeek 账户余额不足（HTTP 402）。'
        : '腾讯云 VOD 主网关、3 级模型回落链与本地生产引擎全部正常。');

  const actionAdvice = !primaryHealthy
    ? '请立即检查 VOD_API_KEY 或网络连通性；期间群内图文与文案初筛由本地引擎兜底。'
    : (hasQuotaWarning
        ? '当前群内四维审图与问答均走腾讯云 VOD 正常服务；如需保留 DeepSeek 备用通道请为其充值。'
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
    deepseek: dsRes,
    ocrOk,
    prepared,
  };
}
