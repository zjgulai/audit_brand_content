/**
 * config.mjs —— 守衡的配置与凭据装载
 *
 * 凭据来源（按优先级）：
 *   1. 环境变量
 *   2. ~/.dsh/credentials/shouheng-lark.json   （飞书应用）
 *   3. ~/.dsh/.credentials.yaml                （DSH 凭据库，取其 LLM key）
 *
 * 设计原则：凭据只在内存中流转，任何日志、任何落盘都不打印明文。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  attachmentRoot, countAttachmentResidue, formatResidue,
} from './attachment_lifecycle.mjs';

export const AGENT_DIR = path.dirname(fileURLToPath(import.meta.url));
export const TOOLS_DIR = path.resolve(AGENT_DIR, '..');
export const REPO_ROOT = path.resolve(TOOLS_DIR, '..');
export const LOG_DIR   = path.join(REPO_ROOT, 'PMO', 'logs');
// 状态目录：惰性解析，让 SHOUHENG_STATE_DIR 在测试里改了就能生效。
// 写成 import 时常量的话，一旦别的模块先加载了本文件，
// 后面再改环境变量就不会有任何效果 —— 而这种失效是静默的。
export function stateDir() {
  return process.env.SHOUHENG_STATE_DIR
    ? path.resolve(process.env.SHOUHENG_STATE_DIR)
    : path.join(REPO_ROOT, 'PMO', 'shouheng-state');
}
export const STATE_DIR = stateDir();   // 兼容既有引用；需要可覆盖语义时用 stateDir()

/**
 * 附件落盘根（2026-10-21 加）。
 *
 * ★ 必须在**仓外**，且目录权限 0700 —— 这是 AGENTS.md §2.6 改线后仍然有效的约束：
 *   下载允许了，但**下载来的东西不许进公开仓**（仓库是公开的，附件里可能有客户素材、
 *   个人信息）。判据在 `tools/verify_download_governance.py` 的 DG-2；
 *   `tools/download_callers.json` 里本调用点的 `landing_root` 指的就是这个目录。
 *
 * 惰性解析，理由与 stateDir() 相同：测试要把根指到临时目录时，改环境变量就得生效。
 * 默认 `~/.shouheng/attachments`，可用 SHOUHENG_ATTACHMENT_DIR 覆盖。
 */
export function attachmentDir() {
  // 路径解析收在 attachment_lifecycle.mjs 一处：启动横幅与附件处理必须看同一个根，
  // 两份实现一定会漂移（本项目已经记过这个病）。
  return attachmentRoot();
}

/**
 * 确保目录存在。失败只警告，不抛。
 *
 * 原来这里是 import 期无保护的 `fs.mkdirSync(...)`：只要状态目录的路径被一个
 * 同名**文件**占住（残留、误创建、磁盘异常都可能），mkdirSync 抛 EEXIST，
 * 整个进程在加载配置时就直接死掉 —— 守衡会彻底起不来，
 * 而报错指向 config.mjs，跟真实原因（一个占了位的文件）毫无关系。
 *
 * 目录建不出来不该阻止「读取配置」这件只读的事。
 * 真正需要写入的地方（flushSeen）会自己再 mkdir 一次，那里的失败是局部的、可报的。
 */
export function ensureDir(dir) {
  try {
    fs.mkdirSync(dir, { recursive: true });
    return true;
  } catch (e) {
    if (e.code !== 'EEXIST') {
      console.warn(`[cfg] 目录不可用（${dir}）：${e.code ?? e.message}`);
    }
    return false;
  }
}

ensureDir(LOG_DIR);
ensureDir(STATE_DIR);

/** 从 DSH 凭据库取一个 ref 的值（形如 `  KEY: value`） */
function readDshCredential(name) {
  const p = path.join(os.homedir(), '.dsh', '.credentials.yaml');
  let txt;
  try {
    txt = fs.readFileSync(p, 'utf8');
  } catch (e) {
    // 只有「文件不存在」才算正常的「这里没有」。
    // 权限错误、路径是目录等异常必须冒出来 —— 否则会被伪装成
    // 「Key 没配」，而真正的原因是读不到，排查方向会被带偏。
    if (e.code === 'ENOENT') return null;
    throw new Error(`读取凭据文件失败（${p}）：${e.code ?? e.message}`);
  }
  const m = txt.match(new RegExp(`^\\s*${name}:\\s*(\\S+)\\s*$`, 'm'));
  return m?.[1] ?? null;
}

function loadLarkCred() {
  const p = path.join(os.homedir(), '.dsh', 'credentials', 'shouheng-lark.json');
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (!j.app_id || !j.app_secret) throw new Error('飞书凭据不完整：缺少 app_id / app_secret');
  return { appId: j.app_id, appSecret: j.app_secret };
}

function loadLlmKey() {
  return process.env.DEEPSEEK_API_KEY
      || readDshCredential('DEEPSEEK_API_KEY')
      || (() => { throw new Error('未找到 DEEPSEEK_API_KEY（环境变量与 DSH 凭据库均无）'); })();
}

export const config = {
  lark: loadLarkCred(),
  llm: {
    apiKey: loadLlmKey(),
    baseUrl: process.env.SHOUHENG_LLM_BASE_URL || 'https://api.deepseek.com',
    // deepseek-flash：快且便宜，适合群聊高频对话；复杂任务可切 deepseek-v4-pro
    model: process.env.SHOUHENG_LLM_MODEL || 'deepseek-flash',
    /** 单会话保留的最大历史轮数（超出后由记忆层压缩） */
    maxTurns: Number(process.env.SHOUHENG_MAX_TURNS || 24),
    /**
     * 单次回复上限。
     * 注意：DeepSeek 的 max_tokens 同时覆盖**思维链 + 正文**（usage.completion_tokens_details.reasoning_tokens）。
     * 实测 1600/4000 会被思维链吃光 —— finish_reason=length 且正文 0 字。
     * 所以这个值必须给足，且必须配合 finishReason 检查（见 truncate.mjs）。
     */
    maxTokens: Number(process.env.SHOUHENG_MAX_TOKENS || 8000),
    /** 工具循环最多迭代几次（防失控） */
    maxToolIters: Number(process.env.SHOUHENG_MAX_TOOL_ITERS || 6),
  },
  /**
   * 知识库（另一台机器上的 DSH 内容治理知识库，走 ngrok 只读 OpenAPI）。
   *
   * ★ 这里**只放一个开关，不在这里加载凭据**，有两个理由：
   *   1. 它是可降级的外部依赖 —— 对端关机、隧道过期、ngrok 换域名都会让它不可用，
   *      而那是**正常运行状态之一**，不该让守衡整个起不来。凭据装载与失败话术
   *      都在 kb_client.mjs 里，由真正的调用点转成人话。
   *   2. 在 config.mjs 里 import kb_client 会绕成环（kb_client 要 import REPO_ROOT/STATE_DIR）。
   *
   * 设 SHOUHENG_KB_ENABLED=0 可以整块关掉。凭据见 ~/.dsh/credentials/shouheng-kb.json。
   */
  kb: {
    enabled: process.env.SHOUHENG_KB_ENABLED !== '0',
    // ★ 这里**故意没有** quotaPerDay。日上限的唯一真值源是服务端：
    //   检索响应里的 quota.limitPerDay（实测 1000）。本地再配一份，
    //   就是给「余额」造了第二个真值源 —— 上一版正是这么把 used=41
    //   报成余额的（服务端真值 292）。余额一律读 kb_client.quotaState()。
  },
  /** 允许守衡响应的群（空数组 = 不限制）。目前只放打通验证过的那个群。 */
  allowedChats: (process.env.SHOUHENG_ALLOWED_CHATS || '').split(',').map(s => s.trim()).filter(Boolean),
  /** 被 @ 才响应（群聊里避免刷屏）；私聊一律响应 */
  requireMentionInGroup: process.env.SHOUHENG_REQUIRE_MENTION !== '0',
};

/** 安全摘要，任何日志都可放心调用 */
export function describeConfig() {
  return {
    larkAppId: config.lark.appId,
    llmModel: config.llm.model,
    llmBaseUrl: config.llm.baseUrl,
    llmKeyLen: config.llm.apiKey.length,
    allowedChats: config.allowedChats.length ? config.allowedChats : '(不限)',
    requireMentionInGroup: config.requireMentionInGroup,
    maxTurns: config.llm.maxTurns,
    // maxTokens 必须进启动横幅：它是「回复被腰斩」的直接成因，
    // 之前 1600 这个值无处可见，事故发生时没人能一眼看出来。
    maxTokens: config.llm.maxTokens,
    // ★ 2026-10-21：附件落盘的年龄分桶。只读、不删。
    //   如果 >24h 桶不是 0，说明「处理完立即删」没有在所有路径上生效 ——
    //   这件事必须自己显形，而不是靠人记得去扫目录。
    attachmentResidue: formatResidue(countAttachmentResidue()),
  };
}
