import { setTimeout as sleep } from 'node:timers/promises';
import fs from 'node:fs';
const url = process.argv[2];
const waitMs = parseInt(process.argv[3] || '18000', 10);
const out = process.argv[4] || null;
const scriptFile = process.argv[5] || null;
const PORT = process.env.CDP_PORT || '9223';
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
let target = list.find(t => t.type === 'page');
if (!target) { console.error('no page target'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
const send = (method, params={}) => new Promise((res, rej) => { const i = ++id; pending.set(i,{res,rej}); ws.send(JSON.stringify({id:i,method,params})); });
await new Promise(r => ws.onopen = r);
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } };
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url });
await sleep(waitMs);
if (scriptFile) {
  const code = fs.readFileSync(scriptFile, 'utf8');
  try { const r = await send('Runtime.evaluate', { expression: code, awaitPromise: true, returnByValue: true }); console.log('EVAL:', JSON.stringify(r.result?.value).slice(0,500)); } catch(e){ console.error('eval err', e.message); }
  await sleep(parseInt(process.env.EXTRA_WAIT || '6000', 10));
}
const h = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true });
const t = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true });
const html = h.result.value || '';
console.log('TITLE:', t.result.value);
console.log('LEN:', html.length);
if (out) fs.writeFileSync(out, html);
ws.close(); process.exit(0);
