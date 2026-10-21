/**
 * image_judgment.mjs —— 把下载到本地的图片交给 base 的**官方 file 入口**
 *
 * 这个文件不实现 OCR、不实现判定，也不再自带 Python 适配层：
 *   1. 调 `.venv/bin/python base/media.py --judge-image <PATH> --json`；
 *   2. 把 CLI 的扁平输出归一成 `{unit, judgment}`，再压成模型能读的摘要。
 *
 * ★ 生产判定入口是 `base/judge_entry.py` 的 RuleJudge + Orchestrator，
 *   **不是** `research/governance/skeleton/judge.py`。本模块不碰判定逻辑。
 *
 * ★ 失败图片也返回 judgment（`label=未审查`，`parse_status=failed`，
 *   带 `failure_kind`），不是 None。只有 CLI 子进程真的坏了才 `ok:false`；
 *   这时摘要仍必须说「未审查/DP0」，不能说成「附件不支持」。
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const execFileP = promisify(execFile);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const PYTHON = path.join(REPO_ROOT, '.venv', 'bin', 'python');
const MEDIA_PY = path.join(REPO_ROOT, 'base', 'media.py');

/** OCR + 判定可能比纯文本慢；给足超时，但不要无限等。 */
export const IMAGE_JUDGE_TIMEOUT_MS = 180_000;

/**
 * 调稳定入口 2 的本地包装：`base.media.judge_row(row, page_uri)`。
 *
 * @returns {Promise<{ok:boolean, judgment?:object, unit?:object, row_status?:string,
 *                    elapsed_ms?:number, error?:string, code?:string|null}>}
 */
/**
 * 构造调用 base CLI 的**实际 argv**。纯函数，离线可证。
 *
 * ★ 必须带稳定 URI：`feishu-message:<message_id>`。
 *   不传的话 base 会落本地临时 file://，而临时目录在判定后被删除 —— 审计来源失真。
 *   没有 messageId 时只接受调用方显式给的 pageUri；两个都没有就**拒绝调用**，
 *   不允许回落到 file://。
 */
export function buildImageJudgeArgs({ filePath, messageId = '', pageUri = null } = {}) {
  if (!filePath) return { ok: false, error: '缺少图片路径' };
  const uri = messageId ? `feishu-message:${messageId}` : pageUri;
  if (!uri) {
    return {
      ok: false,
      error: '缺少稳定 URI（messageId / pageUri）—— 不允许回落到本地 file://',
    };
  }
  return {
    ok: true,
    uri: String(uri),
    args: [MEDIA_PY, '--judge-image', String(filePath), '--uri', String(uri), '--json'],
  };
}

/**
 * 调稳定入口：`.venv/bin/python base/media.py --judge-image <PATH> --uri <URI> --json`。
 *
 * @returns {Promise<{ok:boolean, judgment?:object, unit?:object, unit_id?:string,
 *                    uri?:string, elapsed_ms?:number, error?:string, code?:string|null}>}
 */
export async function runImageJudgment({
  filePath, messageId = '', pageUri = null, timeoutMs = IMAGE_JUDGE_TIMEOUT_MS,
  // 测试注入点：用于回读**实际传给子进程的 argv**，默认是 promisify(execFile)。
  exec = execFileP,
} = {}) {
  const built = buildImageJudgeArgs({ filePath, messageId, pageUri });
  if (!built.ok) return built;
  if (!fs.existsSync(PYTHON) || !fs.existsSync(MEDIA_PY)) {
    return { ok: false, error: `未找到 ${PYTHON} 或 ${MEDIA_PY}（base 图片判定需要仓库 venv）` };
  }
  try {
    const { stdout } = await exec(PYTHON, built.args, {
      cwd: REPO_ROOT, timeout: timeoutMs, maxBuffer: 1 << 25,
    });
    const r = JSON.parse(stdout);
    if (!r || typeof r !== 'object' || (!('label' in r) && !('parse_status' in r))) {
      return { ok: false, error: r?.error ?? 'CLI 输出缺 label/parse_status', raw: r ?? null };
    }
    // ★ CLI 输出是**扁平**的；`findings` 是**数量**（明细在 ir），不是数组。
    //   归一成既有 {judgment, unit} 形状，调用方与测试不必知道 CLI 的字段布局。
    const judgment = {
      label: r.label ?? null,
      layer: r.layer ?? null,
      release_status: r.release_status ?? null,
      run_state: r.run_state ?? null,
      findings: r.findings,          // number（CLI）或 array（测试桩）
      ir: r.ir ?? null,
      receipt: r.receipt ?? null,
    };
    const unit = {
      unit_id: r.unit_id ?? null,
      parse_status: r.parse_status ?? 'failed',
      failure_kind: r.failure_kind ?? null,
      reason: r.reason ?? null,
    };
    return {
      ok: true, judgment, unit, unit_id: r.unit_id ?? null,
      uri: built.uri,
      // CLI 不返回 row_status；不要编一个。image_status 在 meta 里会是 null。
      row_status: null, elapsed_ms: r.elapsed_ms ?? null,
    };
  } catch (e) {
    return {
      ok: false,
      error: `${e?.name ?? 'Error'}: ${e?.message ?? e}`,
      code: e?.code ?? null,
      stderr: String(e?.stderr ?? '').slice(0, 1000),
    };
  }
}

/** 把 judgment 压成小对象；不要把整份 IR 塞进模型上下文。 */
export function compactJudgment(j) {
  if (!j || typeof j !== 'object') return null;
  const raw = j.findings;
  const findings = Array.isArray(raw) ? raw : [];
  const total = Array.isArray(raw) ? raw.length : (typeof raw === 'number' ? raw : 0);
  return {
    label: j.label ?? null,
    layer: j.layer ?? null,
    release_status: j.release_status ?? null,
    run_state: j.run_state ?? null,
    // CLI 的 findings 是数量；测试桩是数组。两种都收，明细不塞上下文。
    findings_total: total,
    findings: findings.slice(0, 10).map((f) => ({
      control_code: f?.control_code ?? null,
      rule_key: f?.rule_key ?? f?.rule_id ?? null,
      severity: f?.severity ?? null,
    })),
    receipt_ref: j.receipt?.receipt_id ?? j.receipt?.id ?? j.ir?.receipt_ref ?? null,
  };
}

/**
 * 给模型看的摘要。**纯函数，离线可证。**
 *
 * 三条不能省：
 *   1. 失败 = 未审查/DP0，**不是**「附件不支持」，也不是「图片里没有内容」；
 *   2. 图片只覆盖**图内文字（OCR）**，画面语义/视觉符号/区域级审计 does_not_cover；
 *   3. coverage partial + 空命中 → 只能 REVIEW，不许说「已通过/合规」。
 */
export function summarizeImageJudgment(result) {
  if (!result?.ok) {
    return `图片判定**未完成**：${result?.error ?? '未知错误'}。\n`
      + '这是**未审查（DP0）**，不是「附件不支持」，也不是「图片里没有内容」。\n'
      + '不许给出合规结论；照实说这次没判成。';
  }
  const j = result.judgment ?? {};
  const u = result.unit ?? {};
  const parse = u.parse_status ?? 'unknown';
  const head = `判定：label=${j.label ?? '未知'} / layer=${j.layer ?? '未知'} / `
    + `release_status=${j.release_status ?? '未知'}`
    + (j.run_state ? ` / run_state=${j.run_state}` : '')
    + `；parse_status=${parse}`;
  const fail = parse === 'failed'
    ? `\n未审查（DP0）：failure_kind=${u.failure_kind ?? 'unknown'}`
      + (u.reason ? `；${u.reason}` : '') + '。\n'
      + '**没有进入 RuleJudge**；这是未审查，不是「附件不支持」。'
    : '';
  const raw = j.findings;
  const n = Array.isArray(raw) ? raw.length : (typeof raw === 'number' ? raw : 0);
  const listed = Array.isArray(raw) && raw.length
    ? raw.slice(0, 5).map((f) => f?.control_code ?? f?.rule_key ?? f?.rule_id ?? '?').join('、')
    : null;
  const hits = n
    ? `\n命中 ${n} 条${listed ? `：${listed}${raw.length > 5 ? '…' : ''}` : '（明细在 ir）'}。`
    : '\n命中：0 条（空命中不等于合规）。';
  return `${head}${fail}${hits}\n`
    + '覆盖边界：只覆盖**图内文字（OCR）**；画面语义、视觉符号、区域级画面审计 '
    + '**does_not_cover**；coverage partial，空命中/证据不足只能 REVIEW。'
    + '**不许说「已通过」或「合规」。**';
}
