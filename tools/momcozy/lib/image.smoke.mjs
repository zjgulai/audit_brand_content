// tools/momcozy/lib/image.smoke.mjs
// 集成 smoke-test:1 张 V1 Pro 主图,真实网络 + 真实 socket
// 用法: node tools/momcozy/lib/image.smoke.mjs
// 退出码 0 成功,1 失败

import { saveImage } from './image.mjs';
import path from 'node:path';
import os from 'node:os';
import { mkdir, rm } from 'node:fs/promises';

const url = 'https://cdn.shopify.com/s/files/1/0559/2321/2486/files/lQDPJws-Zh7cFX_NBdrNBLCwLR71U5WToVIG-TXf9_H4AA_1200_1498.jpg?v=1755159282';

// ★★ 2026-10-21：落盘根从**仓内** `PMO/audit/momcozy-catalog/_smoke` 改到**仓外**
//   `~/audit-data/momcozy-catalog/_smoke`。
//   为什么必须改：本仓是**公开**的（AGENTS.md §2.6），而下载来的是客户产品图。
//   原来靠 `.gitignore` 挡着 —— 但那正是 DG-2 反复说的那句话：**`.gitignore` 不是边界，
//   `git add -f` 照样能进**。一个「把客户素材写进仓内」的采集器，与红线直接冲突。
//   改法同时让 `download_callers.json` 能按 DG-2 登记一个**仓外 0700** 的 landing_root。
const destDir = process.env.MOMCOZY_CATALOG_ROOT
  || path.join(os.homedir(), 'audit-data', 'momcozy-catalog', '_smoke');

// 仓外守卫：realpath 后在仓内 → 直接拒。
const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../..');
const real = path.resolve(destDir);
if (real === REPO || real.startsWith(REPO + path.sep)) {
  console.error(JSON.stringify({
    ok: false,
    reason: 'landing_in_repo',
    dest_dir: real,
    why: '落盘根经 realpath 解析后在仓内 —— 本仓是公开仓，客户素材不许写入（AGENTS.md §2.6）',
  }, null, 2));
  process.exit(2);
}

await mkdir(destDir, { recursive: true, mode: 0o700 });
const r = await saveImage(url, { destDir });

if (!r.saved) {
  console.error(JSON.stringify({ ok: false, reason: r.fail_reason, ...r }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({
  ok: true,
  source_url: r.source_url,
  saved: r.saved,
  local_filename: r.local_filename,
  sha256: r.sha256,
  bytes: r.bytes,
  content_type: r.content_type,
  retrieved_at: r.retrieved_at,
  license_status: r.license_status,
  usage_scope: r.usage_scope,
}, null, 2));
process.exit(0);
