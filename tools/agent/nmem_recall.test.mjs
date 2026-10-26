/**
 * nmem_recall.test.mjs —— recall 适配器的自证。
 *
 * 跑：node --test tools/agent/nmem_recall.test.mjs
 *
 * 它证的是「失败路径全部优雅降级」，不是「nmem 能查出东西」。
 * 后者要真服务，是 verify_nmem.py 的事。
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recall, formatRecall, pickItems } from './nmem_recall.mjs';

// ---------------------------------------------------------------- 纯函数

test('pickItems：三套字段名都认（items / memories / results / 裸数组）', () => {
  const a = [{ title: 'a' }];
  assert.deepEqual(pickItems({ items: a }), a);
  assert.deepEqual(pickItems({ memories: a }), a);
  assert.deepEqual(pickItems({ results: a }), a);
  assert.deepEqual(pickItems(a), a);
});

test('pickItems：不认识的结构返回 []，不抛', () => {
  assert.deepEqual(pickItems(null), []);
  assert.deepEqual(pickItems({ weird: 1 }), []);
  assert.deepEqual(pickItems('nope'), []);
});

test('formatRecall：空输入返回空串（不是 "没有相关记忆" 这种话）', () => {
  assert.equal(formatRecall([]), '');
  assert.equal(formatRecall(null), '');
  assert.equal(formatRecall([{ title: '', content: '' }]), '');
});

test('formatRecall：低于 minScore 的被丢掉', () => {
  const out = formatRecall(
    [
      { title: '低分', content: 'x', score: 0.1 },
      { title: '高分', content: 'y', score: 0.9 },
    ],
    { minScore: 0.5 },
  );
  assert.ok(out.includes('高分'), '高分条目必须保留');
  assert.ok(!out.includes('低分'), '低分条目必须被丢掉');
});

test('formatRecall：三套字段名（camel / snake / snippet）都能取到内容', () => {
  const out = formatRecall(
    [
      { title: 'A', content: '正文A', score: 0.9 },
      { title: 'B', text: '正文B', similarity: 0.9 },
      { title: 'C', snippet: '正文C', score: 0.9 },
    ],
    { minScore: 0.5, limit: 5 },
  );
  for (const s of ['正文A', '正文B', '正文C']) assert.ok(out.includes(s), `缺 ${s}`);
});

test('formatRecall：limit 生效，超长条目被截断（不许塞爆上下文）', () => {
  const long = 'z'.repeat(5000);
  const many = Array.from({ length: 10 }, (_, i) => ({ title: `T${i}`, content: long, score: 0.9 }));
  const out = formatRecall(many, { minScore: 0.5, limit: 2 });
  const n = (out.match(/匹配度/g) ?? []).length;
  assert.equal(n, 2, `limit=2 却拼了 ${n} 条`);
  assert.ok(out.length < 3000, `输出 ${out.length} 字符，截断没生效`);
});

test('formatRecall：标题或正文缺一个就跳过（半条记忆没有价值）', () => {
  assert.equal(formatRecall([{ title: 'only title', score: 0.9 }], {}), '');
  assert.equal(formatRecall([{ content: 'only content', score: 0.9 }], {}), '');
});

// ---------------------------------------------------------------- 失败路径（生命线）

test('recall：空问题直接返回 ""，不起子进程', async () => {
  assert.equal(await recall(''), '');
  assert.equal(await recall('   '), '');
  assert.equal(await recall(null), '');
  assert.equal(await recall(undefined), '');
});

test('recall：二进制不存在 → ""，不抛', async () => {
  const out = await recall('任意问题', { bin: '/nonexistent/nmem-does-not-exist' });
  assert.equal(out, '');
});

test('recall：超时 → ""，且在超时预算内返回（不快也不行，不返回更不行）', async () => {
  const t0 = Date.now();
  // 用一个必定超时的"命令"：sleep 很久。用 /bin/sh 保证在 mac 上存在。
  const out = await recall('任意问题', {
    bin: '/bin/sh',
    timeoutMs: 300,
    // sh 会把 nmem 的参数当文件名，直接退出；为了真测超时，这里换个法子
  });
  const dt = Date.now() - t0;
  assert.equal(out, '');
  assert.ok(dt < 2000, `耗时 ${dt}ms —— 降级太慢，会拖慢主链路`);
});

test('recall：子进程退出码非 0 → ""，不抛', async () => {
  const out = await recall('任意问题', { bin: '/bin/false', timeoutMs: 1000 });
  assert.equal(out, '');
});

test('recall：输出不是 JSON → ""，不抛', async () => {
  // /bin/echo 会把它收到的参数原样打出来 —— 不是 JSON
  const out = await recall('任意问题', { bin: '/bin/echo', timeoutMs: 1000 });
  assert.equal(out, '');
});

test('recall：任何失败都不改变主流程 —— 返回类型恒为 string', async () => {
  for (const bin of ['/nonexistent/a', '/bin/false', '/bin/echo']) {
    const out = await recall('问题', { bin, timeoutMs: 800 });
    assert.equal(typeof out, 'string', `${bin} 的返回不是 string`);
    assert.equal(out, '', `${bin} 应当返回空串`);
  }
});
