import { setTimeout as sleep } from 'node:timers/promises';
const url = process.argv[2];
const waitMs = parseInt(process.argv[3] || '20000', 10);
const out = process.argv[4] || null;
const fs = await import('node:fs');

const list = await (await fetch('http://127.0.0.1:' + (process.env.CDP_PORT||'9222') + '/json/list')).json();
let target = list.find(t => t.type === 'page');
if (!target) { console.error('no page target'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
const send = (method, params={}) => new Promise((res, rej) => { const i = ++id; pending.set(i,{res,rej}); ws.send(JSON.stringify({id:i,method,params})); });
await new Promise(r => ws.onopen = r);
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } };
await send('Page.enable');
await send('Runtime.enable');
const PORT = process.env.CDP_PORT || '9222';
try {
await send('Network.enable');
await send('Network.setUserAgentOverride', { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36', acceptLanguage: 'en-US,en;q=0.9', platform: 'MacIntel' });
await send('Emulation.setUserAgentMetadata', { brands: [{brand:'Chromium',version:'153'},{brand:'Google Chrome',version:'153'},{brand:'Not?A_Brand',version:'24'}], fullVersion: '153.0.8010.37', platform: 'macOS', platformVersion: '15.0.0', architecture: 'arm', model: '', mobile: false });
} catch(e){ console.error('ua override failed', e.message); }
await send('Page.navigate', { url });
await sleep(waitMs);
let title = '', html = '';
for (let attempt = 0; attempt < 8; attempt++) {
  const t = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true });
  title = t.result.value || '';
  const h = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true });
  html = h.result.value || '';
  if (!/just a moment|请稍候|attention required|checking your browser/i.test(title) && html.length > 20000) break;
  await sleep(6000);
}
console.log('TITLE:', title);
console.log('LEN:', html.length);
if (out) fs.writeFileSync(out, html);
else console.log(html.slice(0, 3000));
ws.close();
process.exit(0);
