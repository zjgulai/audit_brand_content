/**
 * attachment_lifecycle.mjs —— 附件落盘的生命周期读数与台账（2026-10-21 加）
 *
 * ── 这个文件只做两件事：**数出来**、**记下来**
 *
 * 它**不删任何历史文件**。删除 `~/.shouheng/attachments` 下的历史残留是销毁行为，
 * 需要委托方对该路径的明确授权；本模块没有这个授权，也不假装有。
 *
 * 能回答的三个问题：
 *   1. 现在落盘根里有什么？按年龄分桶（<1h / 1–24h / >24h）——给启动横幅。
 *      如果 >24h 桶不是 0，说明「处理完立即删」这条没有在所有路径上生效，
 *      **这件事会自己显形**，而不是靠人记得去扫。
 *   2. 本次处理走到了哪一步？`started` 与终态各写一行台账。
 *      进程被 kill 时只留下 `started`，没有终态 —— 这正是「被 kill」的可读形状。
 *   3. 本次自己创建的临时目录删没删？终态行带 `deleted: true/false`；
 *      失败时带 `cleanup_error`。删除只针对**本次调用自己创建的目录**。
 *
 * ★ 为什么单独一个模块：`config.mjs` 要在启动横幅里调它，而 `feishu.mjs` 要写台账。
 *   如果把它放进 config，feishu → config 会绕成环；如果放进 feishu，config → feishu 也会。
 *   所以它只依赖 node 内置模块，路径解析自己负责。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');

/** 附件落盘根。默认 ~/.shouheng/attachments；可用 SHOUHENG_ATTACHMENT_DIR 覆盖。 */
export function attachmentRoot() {
  return process.env.SHOUHENG_ATTACHMENT_DIR
    ? path.resolve(process.env.SHOUHENG_ATTACHMENT_DIR)
    : path.join(os.homedir(), '.shouheng', 'attachments');
}

/** 生命周期台账。默认 PMO/logs/attachment_lifecycle.jsonl（已 gitignore）；测试可覆盖。 */
export function lifecycleLedgerPath() {
  return process.env.SHOUHENG_ATTACHMENT_LEDGER
    ? path.resolve(process.env.SHOUHENG_ATTACHMENT_LEDGER)
    : path.join(REPO_ROOT, 'PMO', 'logs', 'attachment_lifecycle.jsonl');
}

/** 递归数一个目录下的普通文件数；读不到就抛，由调用方落 partial/untested。 */
function countFiles(dir) {
  let n = 0;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isFile()) n += 1;
    else if (e.isDirectory()) n += countFiles(path.join(dir, e.name));
  }
  return n;
}

/**
 * 按年龄分桶统计落盘根里的 `msg-*` 目录。**只读，不删。**
 *
 * @returns {{status:'ok'|'partial'|'untested'|'absent', dirs:number, files:number,
 *            buckets:{lt1h:number, '1to24h':number, gt24h:number},
 *            oldest_age_ms:number|null, error:string|null}}
 */
export function countAttachmentResidue({ root = attachmentRoot(), now = Date.now() } = {}) {
  const out = {
    status: 'ok', dirs: 0, files: 0, failed: 0,
    buckets: { lt1h: 0, '1to24h': 0, gt24h: 0 },
    oldest_age_ms: null, error: null,
  };
  let entries;
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch (e) {
    if (e.code === 'ENOENT') { out.status = 'absent'; return out; }
    // ★ 读不到 ≠ 0 个。落 untested，横幅里必须看得出来。
    out.status = 'untested';
    out.failed += 1;
    out.error = e.code ?? e.message;
    return out;
  }
  for (const ent of entries) {
    if (!ent.isDirectory() || !ent.name.startsWith('msg-')) continue;
    out.dirs += 1;
    const p = path.join(root, ent.name);
    let age;
    try {
      age = now - fs.statSync(p).mtimeMs;
    } catch (e) {
      out.status = 'partial';
      out.failed += 1;
      out.error = e.code ?? e.message;
      continue;
    }
    if (out.oldest_age_ms === null || age > out.oldest_age_ms) out.oldest_age_ms = age;
    if (age < 60 * 60 * 1000) out.buckets.lt1h += 1;
    else if (age < 24 * 60 * 60 * 1000) out.buckets['1to24h'] += 1;
    else out.buckets.gt24h += 1;
    try { out.files += countFiles(p); }
    catch (e) { out.status = 'partial'; out.failed += 1; out.error = e.code ?? e.message; }
  }
  return out;
}

/** 启动横幅用的一行读数。未测/部分失败必须与原样读数长得不一样。 */
export function formatResidue(c = countAttachmentResidue()) {
  const head = `attachments 残留 ${c.dirs} 个 / 清理失败 ${c.failed} 个`
    + `（status=${c.status} files=${c.files} lt1h=${c.buckets.lt1h} `
    + `1to24h=${c.buckets['1to24h']} >24h=${c.buckets.gt24h}`;
  const age = c.oldest_age_ms == null ? 'oldest=n/a' : `oldest=${Math.round(c.oldest_age_ms / 60000)}min`;
  return `${head} ${age}${c.error ? ` error=${c.error}` : ''}）`;
}

/**
 * 追加一行生命周期台账。**不抛异常**；失败返回 {ok:false,error}，由调用方透传。
 *
 * 行形状：`{ts, pid, status, file_token, message_id, type, created, deleted,
 *           cleanup_error?, error?}`
 *   · `started`  —— 下载前写；进程被 kill 时只会有这一行
 *   · 终态       —— ingested / empty / binary / too_large / download_failed /
 *                   unsupported_type / bad_content
 *   · `deleted`  —— 本次自己创建的临时目录是否删除；`created:false` 时为 null
 */
export function appendLifecycle(entry, { ledgerPath = lifecycleLedgerPath(), now = new Date() } = {}) {
  const line = {
    ts: now.toISOString(),
    pid: process.pid,
    ...entry,
  };
  try {
    fs.mkdirSync(path.dirname(ledgerPath), { recursive: true });
    fs.appendFileSync(ledgerPath, `${JSON.stringify(line)}\n`, 'utf8');
    return { ok: true, path: ledgerPath };
  } catch (e) {
    return { ok: false, error: `${e.code ?? e.name}: ${e.message}`, path: ledgerPath };
  }
}
