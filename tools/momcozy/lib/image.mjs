// tools/momcozy/lib/image.mjs
//
// 单图下载器(Node.js + node:https 1.x,不走 npm 包,保证仓库零新增依赖)
//
// 8 条硬边界(来自对方会话合议,本项目 §2.1 + §2.4 + §2.6 综合形)
// 1. host allowlist:
//    - cdn.shopify.com → 仅 path prefix /s/files/
//    - momcozy.com     → 仅 path prefix /cdn/shop/
//    - https only,no userinfo,no IP literal
// 2. 重定向逐跳验 scheme+hostname;跳数 ≤ 5
// 3. 拒绝 IP literal / 私网 / loopback / link-local / 保留地址
// 4. DNS rebinding:每次连接后验 remoteAddress 为公网
//    (本实现走 lookup:true 默认行为,serverAddr 为 -1 时不取;socket.on('connect') 后调 getPeerCertificate 验 chain)
//    简化:用 lookup:'dns.lookup' + 校验解析 IP
// 5. 流式 20MB 上限:req.on('data') 累计,超即 abort
// 6. 魔数:
//    - JPEG: 头 3 = FF D8 FF
//    - PNG:  头 8 = 89 50 4E 47 0D 0A 1A 0A
//    - WebP: 头 4 = 52 49 46 46 (RIFF) AND offset 8–11 = 57 45 42 50 (WEBP)
// 7. 扩展名由魔数 + Content-Type 推导,**不信 URL 后缀**
// 8. 失败文件不进 images/,进 _quarantine/<safe-name>;或 unlink(本实现:unlink,只记 manifest)
//
// 调用方约定:本会话不调用本模块。Playwright MCP 通道负责拿 source_url,
// 本模块是骨架,可被后续 scrape_*.mjs 调用。当前 smoke-test 由 /tmp/dl-smoke 用 curl 验证。

import https from 'node:https';
import { writeFile, unlink, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { lookup } from 'node:dns/promises';
import path from 'node:path';

const ALLOW = Object.freeze({
  'cdn.shopify.com': /^\/s\/files\//,
  'momcozy.com':     /^\/cdn\/shop\//,
});

const MAX_BYTES = 20 * 1024 * 1024;
const MAX_REDIRECTS = 5;
const ALLOWED_HOSTS = Object.keys(ALLOW);

function isPrivateIpv4(ip) {
  const parts = ip.split('.').map(Number);
  if (parts.length !== 4 || parts.some((p) => isNaN(p) || p < 0 || p > 255)) return true;
  const [a, b] = parts;
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 169 && b === 254) return true;
  if (a >= 224) return true;
  return false;
}

function isPrivateIpv6(ip) {
  const lower = ip.toLowerCase();
  if (lower === '::1') return true;
  if (lower.startsWith('fc') || lower.startsWith('fd')) return true;
  if (lower.startsWith('fe8') || lower.startsWith('fe9') || lower.startsWith('fea') || lower.startsWith('feb')) return true;
  if (lower.startsWith('::ffff:')) {
    const v4 = lower.slice(7);
    return isPrivateIpv4(v4);
  }
  return false;
}

async function resolveAndCheck(host) {
  if (!ALLOWED_HOSTS.includes(host)) throw new Error(`host_not_allowed: ${host}`);
  const { address } = await lookup(host, { family: 4 }).catch(async () => {
    const v6 = await lookup(host, { family: 6 });
    return { address: v6.address };
  });
  if (isPrivateIpv4(address) || isPrivateIpv6(address)) {
    throw new Error(`private_ip: ${host} → ${address}`);
  }
  return address;
}

function validateUrl(urlString) {
  const u = new URL(urlString);
  if (u.protocol !== 'https:') throw new Error(`not_https: ${u.protocol}`);
  if (u.username || u.password) throw new Error(`userinfo_present`);
  const host = u.hostname.toLowerCase().replace(/\.$/, '');
  if (!ALLOWED_HOSTS.includes(host)) throw new Error(`host_not_allowed: ${host}`);
  if (!ALLOW[host].test(u.pathname)) throw new Error(`path_not_allowed: ${u.pathname}`);
  return u;
}

function classifyMagic(bytes) {
  if (bytes.length >= 3 && bytes[0] === 0xFF && bytes[1] === 0xD8 && bytes[2] === 0xFF) return 'image/jpeg';
  if (bytes.length >= 8 &&
      bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47 &&
      bytes[4] === 0x0D && bytes[5] === 0x0A && bytes[6] === 0x1A && bytes[7] === 0x0A) return 'image/png';
  if (bytes.length >= 12 &&
      bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
      bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50) return 'image/webp';
  return null;
}

function extFor(contentType) {
  return contentType === 'image/jpeg' ? 'jpg'
       : contentType === 'image/png'  ? 'png'
       : contentType === 'image/webp' ? 'webp'
       : null;
}

export async function downloadImage(sourceUrl, { destDir }) {
  await mkdir(destDir, { recursive: true });
  let urlString = sourceUrl;
  let redirectsLeft = MAX_REDIRECTS;
  let lastErr;

  while (redirectsLeft-- >= 0) {
    const u = validateUrl(urlString);
    const ip = await resolveAndCheck(u.hostname);
    const result = await fetchOnce(u.hostname, ip, u.pathname + u.search);
    if (result.kind === 'redirect') {
      urlString = result.location;
      continue;
    }
    return result; // {kind:'ok', body, contentType, finalUrl} | {kind:'fail', reason}
  }
  return { kind: 'fail', reason: 'too_many_redirects', lastErr };

  function fetchOnce(host, ip, pathAndQuery) {
    return new Promise((resolve) => {
      const chunks = [];
      let total = 0;
      const req = https.request({
        host: ip,
        servername: host,
        port: 443,
        path: pathAndQuery,
        method: 'GET',
        headers: {
          'User-Agent': 'curl/7.79.1',
          'Accept': '*/*',
          'Accept-Encoding': 'identity',
        },
      }, (res) => {
        if ([301, 302, 303, 307, 308].includes(res.statusCode)) {
          res.resume();
          return resolve({ kind: 'redirect', location: res.headers.location });
        }
        if (res.statusCode !== 200) {
          res.resume();
          return resolve({ kind: 'fail', reason: `http_${res.statusCode}` });
        }
        res.on('data', (chunk) => {
          total += chunk.length;
          if (total > MAX_BYTES) {
            req.destroy(new Error('size_limit_exceeded'));
            return;
          }
          chunks.push(chunk);
        });
        res.on('end', () => {
          if (req.destroyed) return resolve({ kind: 'fail', reason: 'size_limit_exceeded' });
          const body = Buffer.concat(chunks);
          const contentType = (res.headers['content-type'] || '').split(';')[0].trim();
          resolve({ kind: 'ok', body, contentType, finalUrl: `https://${host}${pathAndQuery}` });
        });
      });
      req.on('error', (err) => resolve({ kind: 'fail', reason: err.message }));
      req.end();
    });
  }
}

export async function saveImage(sourceUrl, { destDir, prefix }) {
  const result = await downloadImage(sourceUrl, { destDir });
  if (result.kind !== 'ok') {
    return {
      source_url: sourceUrl,
      saved: false,
      fail_reason: result.reason,
    };
  }
  const { body, contentType, finalUrl } = result;
  const magic = classifyMagic(body);
  // 信魔数 + Content-Type,不信 URL 后缀
  const detected = magic && extFor(magic);
  const ctMatch = extFor(contentType);
  if (!detected || !ctMatch || detected !== ctMatch) {
    return {
      source_url: sourceUrl,
      saved: false,
      fail_reason: 'magic_or_ct_mismatch',
      magic_content_type: magic,
      header_content_type: contentType,
      body_size: body.length,
    };
  }
  const sha256 = createHash('sha256').update(body).digest('hex');
  const local_filename = `${prefix}-${sha256.slice(0, 8)}.${detected}`;
  const local_path = path.join(destDir, local_filename);
  if (!prefix) {
    // default: <sha256>.<ext>
    const default_name = `${sha256}.${detected}`;
    const final_path = path.join(destDir, default_name);
    await writeFile(final_path, body);
    return {
      source_url: sourceUrl,
      saved: true,
      local_filename: default_name,
      sha256,
      bytes: body.length,
      content_type: magic,
      source_origin: 'shopify-public-cdn',
      license_status: 'unknown',
      usage_scope: 'internal-review-only',
      retrieved_at: new Date().toISOString(),
    };
  }
  await writeFile(local_path, body);
  return {
    source_url: sourceUrl,
    saved: true,
    local_filename,
    sha256,
    bytes: body.length,
    content_type: magic,
    source_origin: 'shopify-public-cdn',
    license_status: 'unknown',
    usage_scope: 'internal-review-only',
    retrieved_at: new Date().toISOString(),
  };
}
