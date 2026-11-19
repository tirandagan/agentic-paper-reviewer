// Deterministic frame capture: node render.mjs <outDir> [t1,t2,...]   (no times => all frames)
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const OUT = process.argv[2]; const TIMES = process.argv[3];
const FPS = 30, DUR = 25, W = 1920, H = 1080, PORT = 9555, HTTP = 8765;
mkdirSync(OUT, { recursive: true });

const MIME = { '.html': 'text/html', '.css': 'text/css', '.png': 'image/png', '.woff2': 'font/woff2', '.js': 'text/javascript' };
const srv = createServer((q, r) => { const f = join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!f.startsWith(ROOT) || !existsSync(f)) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'content-type': MIME[extname(f)] || 'application/octet-stream' }); r.end(readFileSync(f)); }).listen(HTTP, '127.0.0.1');

const prof = join(ROOT, 'chrome-profile'); rmSync(prof, { recursive: true, force: true });
const chrome = spawn('google-chrome', ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`, '--hide-scrollbars', '--force-device-scale-factor=1', `--window-size=${W},${H}`, '--disable-gpu', '--no-first-run', '--mute-audio', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let list; for (let i = 0; i < 60; i++) { try { list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (list.find(x => x.type === 'page')) break; } catch { } await sleep(250); }
const page = list.find(x => x.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(); const evs = [];
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } else evs.push(d); };
const cdp = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, d => d.error ? rej(new Error(method + ': ' + JSON.stringify(d.error))) : res(d.result)); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };

await cdp('Page.enable'); await cdp('Runtime.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
await cdp('Page.navigate', { url: `http://127.0.0.1:${HTTP}/index.html` });
for (let i = 0; i < 80 && !(await ev('typeof window.ready==="function"').catch(() => false)); i++) await sleep(100);
const fonts = await ev('window.ready()');
console.log('fonts loaded:', fonts);
if (!fonts.every(Boolean)) { console.error('FONT CHECK FAILED'); process.exit(2); }

const times = TIMES ? TIMES.split(',').map(Number) : Array.from({ length: FPS * DUR }, (_, i) => i / FPS);
let n = 0;
for (const t of times) {
  await ev(`window.seek(${t});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))`);
  const { data } = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, clip: { x: 0, y: 0, width: W, height: H, scale: 1 } });
  const name = TIMES ? `t${t.toFixed(2)}.png` : `f${String(n).padStart(4, '0')}.png`;
  writeFileSync(join(OUT, name), Buffer.from(data, 'base64')); n++;
  if (!TIMES && n % 75 === 0) console.log(`${n}/${times.length}`);
}
console.log('wrote', n, 'frames to', OUT);
ws.close(); chrome.kill(); srv.close(); process.exit(0);
