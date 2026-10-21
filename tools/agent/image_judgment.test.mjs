#!/usr/bin/env node
/**
 * image_judgment.test.mjs —— base 图片判定入口的**真实**接线自证（2026-10-21）
 *
 * 与 attachment_ingest.test.mjs 的分工：
 *   · 那边用桩证明「ingestAttachment 真的把本地路径交给了 judgeImage」；
 *   · 这边**真跑** `.venv/bin/python base/media.py --judge-image <PATH> --json`，
 *     证明适配层确实走 `base.media.judge_row`（RuleJudge+Orchestrator），
 *     并且失败图片返回的是**未审查/DP0**，不是 None、也不是「附件不支持」。
 *
 * 合成样本（10×10 白图 / 伪装成 .img 的文本），不含客户素材或个人信息。
 * 如果 `.venv/bin/python` 不存在，本测试退 **2（未测）**，不是通过。
 *
 * 用法：node tools/agent/image_judgment.test.mjs
 * 退出码：0 全过 ｜ 1 有红 ｜ 2 未测（venv 缺失）
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const PYTHON = path.join(REPO_ROOT, '.venv', 'bin', 'python');

const res = [];
const T = (name, ok, detail) => res.push({ name, ok, detail });

if (!fs.existsSync(PYTHON)) {
  console.log('⚠ 未测：找不到 .venv/bin/python —— base 图片判定入口无法实跑（退 2，不是通过）');
  process.exit(2);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'image-judgment-test-'));
// 10×10 纯白 PNG（手写，避免依赖 ImageMagick）
{
  const zlib = await import('node:zlib');
  const w = 10, h = 10;
  const raw = Buffer.concat(Array.from({ length: h }, () => Buffer.concat([
    Buffer.from([0]), Buffer.alloc(w * 3, 0xff),
  ])));
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(td) >>> 0);
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
  ]);
  fs.writeFileSync(path.join(tmp, 'white.png'), png);
}
fs.writeFileSync(path.join(tmp, 'not-an-image.img'), '这不是图片，只有文本字节。');

const { runImageJudgment, summarizeImageJudgment, compactJudgment } =
  await import('./image_judgment.mjs');

/* ── D. 真实链路：image message → 下载 → **默认** judgeImage → base 入口 ──
   前置：不注入 judgeImage，走 feishu.ingestAttachment 的默认值。
   证明「真实 image message 会让 base 入口被调用」，而不是只有单测里接上了。 */
const tmpAttach = path.join(tmp, 'attachments');
process.env.SHOUHENG_STATE_DIR = path.join(tmp, 'state');
process.env.SHOUHENG_ATTACHMENT_DIR = tmpAttach;
process.env.SHOUHENG_ATTACHMENT_LEDGER = path.join(tmp, 'attachment_lifecycle.jsonl');
const feishu = await import('./feishu.mjs');
const pngBytes = fs.readFileSync(path.join(tmp, 'white.png'));
{
  let downloaded = false;
  feishu.client.im.v1.messageResource.get = async () => {
    downloaded = true;
    return {
      headers: { 'content-length': String(pngBytes.length) },
      writeFile: async (p) => { fs.writeFileSync(p, pngBytes); return p; },
      getReadableStream: () => ({ destroy() {} }),
    };
  };
  const r = await feishu.ingestAttachment({
    message_id: 'om_e2e_image', message_type: 'image',
    content: JSON.stringify({ image_key: 'ik-e2e' }),
  });
  T('D1 真实链路：image message → 下载 → 默认 judgeImage 真跑到 base 入口',
    downloaded === true && r.status === 'image_judge_failed'
      && r.parse_status === 'failed'
      && typeof r.failure_kind === 'string' && r.failure_kind.length > 0,
    JSON.stringify({ downloaded, status: r.status, parse: r.parse_status,
                     failure: r.failure_kind }));
  T('D2 真实链路失败仍返回未审查/DP0（不是「附件不支持」）',
    /未审查（DP0）/.test(r.summary) && /不是「附件不支持」/.test(r.summary),
    String(r.summary).slice(0, 180));
  T('D3 真实链路处理完仍删除临时目录',
    fs.readdirSync(tmpAttach).length === 0, fs.readdirSync(tmpAttach).join(','));
}

/* ── A. 白图：OCR 成功但没有可读文字 → 未审查/DP0 ───────────────────── */
{
  const r = await runImageJudgment({
    filePath: path.join(tmp, 'white.png'), messageId: 'om_test_white',
    pageUri: 'feishu:message:om_test_white',
  });
  T('A1 真跑 base 入口 → ok=true，返回 judgment（不是 None）',
    r.ok === true && !!r.judgment && !!r.unit, JSON.stringify({ ok: r.ok, error: r.error }));
  T('A2 白图无可读文字 → parse_status=failed + failure_kind',
    r.unit?.parse_status === 'failed' && typeof r.unit?.failure_kind === 'string',
    `${r.unit?.parse_status}/${r.unit?.failure_kind}`);
  T('A3 失败图片的 label 是「未审查」',
    r.judgment?.label === '未审查', String(r.judgment?.label));
  const sum = summarizeImageJudgment(r);
  T('A4 摘要写明未审查/DP0，并明确不是「附件不支持」',
    /未审查（DP0）/.test(sum) && /不是「附件不支持」/.test(sum), sum.slice(0, 180));
  T('A5 摘要保留图片覆盖边界（只覆盖图内文字 + 不许说已通过）',
    /只覆盖\*\*图内文字/.test(sum) && /不许说「已通过」/.test(sum), sum.slice(-120));
  const c = compactJudgment(r.judgment);
  T('A6 压缩结果只留 label/layer/release_status/findings，不塞整份 IR',
    c && c.label === '未审查' && !('ir' in c), JSON.stringify(c));
}

/* ── B. 非图片字节：OCR 失败也必须返回未审查，不是「附件不支持」────── */
{
  const r = await runImageJudgment({
    filePath: path.join(tmp, 'not-an-image.img'), messageId: 'om_test_bad',
  });
  T('B1 坏图也返回 judgment（parse_status=failed），不是 None',
    r.ok === true && !!r.judgment && r.unit?.parse_status === 'failed',
    JSON.stringify({ ok: r.ok, parse: r.unit?.parse_status, error: r.error }));
  T('B2 坏图的 label 仍是「未审查」',
    r.judgment?.label === '未审查', String(r.judgment?.label));
  const sum = summarizeImageJudgment(r);
  T('B3 坏图摘要不许说成「附件不支持」',
    /未审查（DP0）/.test(sum) && !/附件不支持/.test(sum.replace(/不是「附件不支持」/g, '')),
    sum.slice(0, 180));
}

/* ── C. 入口真的坏了：ok=false，但摘要仍说未审查 ───────────────────── */
{
  const sum = summarizeImageJudgment({ ok: false, error: '模拟入口坏了' });
  T('C1 入口异常 → 摘要说未审查/DP0，不是附件不支持',
    /未审查（DP0）/.test(sum) && /不是「附件不支持」/.test(sum), sum);
}

try { fs.rmSync(tmp, { recursive: true, force: true }); } catch { /* 清理失败不影响断言 */ }
const nFail = res.filter((x) => !x.ok).length;
for (const x of res) {
  console.log(`  ${x.ok ? '✅' : '❌'} ${x.name}${x.ok || !x.detail ? '' : `  ← ${x.detail}`}`);
}
console.log(`\n${nFail ? '❌' : '✅'} 图片判定入口自证 ${res.length - nFail}/${res.length} 项通过`);
console.log('   （真跑 .venv/bin/python base/media.py --judge-image；合成样本，不含客户素材）');
process.exit(nFail ? 1 : 0);
