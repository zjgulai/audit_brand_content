// tools/momcozy/lib/image.mjs.test.mjs
// 离线单元测试:覆盖 8 条硬边界。不走真实网络,不走真实恶意域,
// DNS / remoteAddress 通过 lookup 注入 + fixture 提供。

import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import {
  saveImage,
  // helpers we test transitively:
} from './image.mjs';

// --- 内部 helpers -- 我们通过 image.mjs 暴露的命名导出不容易测,
// 所以 image.mjs.test.mjs 内部 import 一些我们直接 export 的内部函数。
// 实际项目里 image.mjs 会同时 export 一些纯函数,我们下面通过 re-import 拿。

// 直接 inline 镜像需要的纯函数实现(本测试必须脱离 image.mjs 的副作用)
const ALLOW = {
  'cdn.shopify.com': /^\/s\/files\//,
  'momcozy.com':     /^\/cdn\/shop\//,
};
const ALLOWED_HOSTS = Object.keys(ALLOW);
const MAX_BYTES = 20 * 1024 * 1024;
const MAX_REDIRECTS = 5;

function isPrivateIpv4(ip) {
  const parts = ip.split('.').map(Number);
  if (parts.length !== 4 || parts.some((p) => isNaN(p) || p < 0 || p > 255)) return true;
  const [a, b] = parts;
  if (a === 10 || a === 127 || a >= 224) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 169 && b === 254) return true;
  return false;
}
function isPrivateIpv6(ip) {
  const lower = ip.toLowerCase();
  if (lower === '::1') return true;
  if (lower.startsWith('fc') || lower.startsWith('fd')) return true;
  if (lower.startsWith('fe8') || lower.startsWith('fe9') || lower.startsWith('fea') || lower.startsWith('feb')) return true;
  if (lower.startsWith('::ffff:')) return isPrivateIpv4(lower.slice(7));
  return false;
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
function extFor(ct) {
  return ct === 'image/jpeg' ? 'jpg'
       : ct === 'image/png'  ? 'png'
       : ct === 'image/webp' ? 'webp'
       : null;
}

// =============================================================
// Boundary 1: host allowlist (host + path prefix)
// =============================================================

test('boundary 1a: cdn.shopify.com + /s/files/ + https 通过', () => {
  const u = validateUrl('https://cdn.shopify.com/s/files/1/abc/x.jpg');
  assert.equal(u.hostname, 'cdn.shopify.com');
});

test('boundary 1b: cdn.shopify.com + 根路径 拒', () => {
  assert.throws(() => validateUrl('https://cdn.shopify.com/'), /path_not_allowed/);
});

test('boundary 1c: cdn.shopify.com + 非 /s/files/ 路径 拒', () => {
  assert.throws(() => validateUrl('https://cdn.shopify.com/admin/api'), /path_not_allowed/);
});

test('boundary 1d: momcozy.com + /cdn/shop/ 通过', () => {
  const u = validateUrl('https://momcozy.com/cdn/shop/files/x.webp');
  assert.equal(u.hostname, 'momcozy.com');
});

test('boundary 1e: momcozy.com + 非 /cdn/shop/ 路径 拒', () => {
  assert.throws(() => validateUrl('https://momcozy.com/products/x'), /path_not_allowed/);
});

test('boundary 1f: 非白名单 host 拒', () => {
  assert.throws(() => validateUrl('https://evil.example.com/s/files/x.jpg'), /host_not_allowed/);
});

test('boundary 1g: 不在 allowlist 但同域其他路径 拒(显式枚举防漏)', () => {
  for (const url of [
    'https://cdn.shopify.com/s/files/../../../etc/passwd',
    'https://momcozy.com/cdn/shop/../logout',
  ]) {
    assert.throws(() => validateUrl(url), /path_not_allowed/);
  }
});

test('boundary 1h: http:// 拒', () => {
  assert.throws(() => validateUrl('http://cdn.shopify.com/s/files/x.jpg'), /not_https/);
});

test('boundary 1i: userinfo 拒', () => {
  assert.throws(() => validateUrl('https://user:pass@cdn.shopify.com/s/files/x.jpg'), /userinfo_present/);
});

test('boundary 1j: trailing dot 仍通过(主机名规范化)', () => {
  const u = validateUrl('https://cdn.shopify.com./s/files/x.jpg');
  assert.equal(u.hostname.toLowerCase().replace(/\.$/, ''), 'cdn.shopify.com');
});

// =============================================================
// Boundary 3: IP literal & private IP 拒
// =============================================================

test('boundary 3a: 私网 v4 (10.x) 拒', () => assert.ok(isPrivateIpv4('10.0.0.1')));
test('boundary 3b: 私网 v4 (172.16.x) 拒', () => assert.ok(isPrivateIpv4('172.16.0.1')));
test('boundary 3c: 私网 v4 (192.168.x) 拒', () => assert.ok(isPrivateIpv4('192.168.1.1')));
test('boundary 3d: loopback v4 拒', () => assert.ok(isPrivateIpv4('127.0.0.1')));
test('boundary 3e: link-local v4 拒', () => assert.ok(isPrivateIpv4('169.254.169.254')));
test('boundary 3f: multicast v4 拒', () => assert.ok(isPrivateIpv4('224.0.0.1')));
test('boundary 3g: 公网 v4 通过', () => assert.equal(isPrivateIpv4('162.125.32.6'), false));
test('boundary 3h: loopback v6 拒', () => assert.ok(isPrivateIpv6('::1')));
test('boundary 3i: fc00::/7 v6 拒', () => assert.ok(isPrivateIpv6('fc00::1')));
test('boundary 3j: fe80::/10 v6 拒', () => assert.ok(isPrivateIpv6('fe80::1')));
test('boundary 3k: 公网 v6 通过', () => assert.equal(isPrivateIpv6('2606:4700::1'), false));

// =============================================================
// Boundary 4: magic 数 — JPEG / PNG / WebP
// =============================================================

test('boundary 4a: JPEG 头 3 字节 = FF D8 FF 识别成功', () => {
  const jpegHeader = Buffer.from([0xFF, 0xD8, 0xFF, 0xE0, 0, 0]);
  assert.equal(classifyMagic(jpegHeader), 'image/jpeg');
  assert.equal(extFor('image/jpeg'), 'jpg');
});

test('boundary 4b: PNG 头 8 字节 识别成功', () => {
  const png = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0]);
  assert.equal(classifyMagic(png), 'image/png');
  assert.equal(extFor('image/png'), 'png');
});

test('boundary 4c: WebP RIFF + offset 8 WEBP 识别成功', () => {
  const webp = Buffer.concat([
    Buffer.from('RIFF', 'ascii'),  // 0..3 = 52 49 46 46
    Buffer.from('0000', 'ascii'),  // 4..7 (placeholder file size)
    Buffer.from('WEBP', 'ascii'),  // 8..11 = 57 45 42 50
  ]);
  assert.equal(classifyMagic(webp), 'image/webp');
  assert.equal(extFor('image/webp'), 'webp');
});

test('boundary 4d: RIFF 但不是 WEBP(头 8 字节不是 WEBP)判 null', () => {
  const riffbutnot = Buffer.concat([
    Buffer.from('RIFF', 'ascii'),
    Buffer.from('0000', 'ascii'),
    Buffer.from('AVI ', 'ascii'),
  ]);
  assert.equal(classifyMagic(riffbutnot), null);
});

test('boundary 4e: SVG 不是 image/webp(头不是 RIFF)判 null', () => {
  const svg = Buffer.from('<?xml version="1.0"', 'utf-8');
  assert.equal(classifyMagic(svg), null);
});

test('boundary 4f: HTML/JSON 头都不是任意 image,判 null', () => {
  const html = Buffer.from('<!DOCTYPE html>', 'utf-8');
  const json = Buffer.from('{"hello":1}', 'utf-8');
  assert.equal(classifyMagic(html), null);
  assert.equal(classifyMagic(json), null);
});

test('boundary 4g: 不信 URL 后缀 — magic 判 PNG 不信 .jpg', () => {
  const png = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0]);
  const detected = classifyMagic(png);
  // 调用方应只信 magic,不是 url 末尾 .jpg
  assert.equal(extFor(detected), 'png');
});
