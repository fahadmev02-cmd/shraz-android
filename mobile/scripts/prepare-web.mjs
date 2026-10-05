import { build } from 'esbuild';
import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { loadSettings } from './settings.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = resolve(root, '../static');
const output = resolve(root, 'www');
const settings = await loadSettings({ release: process.argv.includes('--release') });
await mkdir(output, { recursive: true });
const hashes = {};
for (const name of ['index.html', 'app.js', 'styles.css', 'icon.svg']) {
  const data = await readFile(resolve(source, name));
  hashes[name] = createHash('sha256').update(data).digest('hex');
}

let html = await readFile(resolve(source, 'index.html'), 'utf8');
html = html.replace('<script defer src="/app.js"></script>', '<script defer src="/native.js"></script>\n  <script defer src="/app.js"></script>');
html = html.replace('<link rel="manifest" href="/manifest.webmanifest">', '');
html = html.replace('<title>', '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\' blob: data:; connect-src \'self\'; object-src \'none\'; base-uri \'none\'; form-action \'self\'">\n  <title>');
await writeFile(resolve(output, 'index.html'), html);

let app = await readFile(resolve(source, 'app.js'), 'utf8');
const serviceWorker = "if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});";
const privatePhoto = 'src="/api/photo/${p.id}?client=${state.client}"';
if (!app.includes(serviceWorker) || !app.includes(privatePhoto)) throw new Error('Web entry points changed. Review the Android adapter before rebuilding.');
app = app.replace(serviceWorker, '// Android serves bundled assets; no PWA service worker.');
app = app.replace(privatePhoto, 'data-private-photo="/api/photo/${p.id}?client=${state.client}"');
await writeFile(resolve(output, 'app.js'), app);
await copyFile(resolve(source, 'icon.svg'), resolve(output, 'icon.svg'));
await copyFile(resolve(source, 'styles.css'), resolve(output, 'styles.css'));
await build({ entryPoints: [resolve(root, 'src/native.mjs')], bundle: true, outfile: resolve(output, 'native.js'), format: 'iife', target: 'chrome100', define: { __SHRAZ_SETTINGS__: JSON.stringify({ backendUrl: settings.backendUrl }) }, legalComments: 'none' });

const configPath = resolve(root, 'capacitor.config.json');
const config = JSON.parse(await readFile(configPath, 'utf8'));
config.appId = settings.appId;
config.appName = settings.appName;
delete config.server.url; // Always bundle UI. Never substitute remote live-reload.
await writeFile(configPath, JSON.stringify(config, null, 2) + '\n');
await writeFile(resolve(root, 'build-info.json'), JSON.stringify({ appId: settings.appId, appName: settings.appName, versionCode: settings.versionCode, versionName: settings.versionName, backendConfigured: Boolean(settings.backendUrl), releaseValidated: process.argv.includes('--release'), sourceHashes: hashes }, null, 2) + '\n');
console.log(`Android web assets prepared; backend ${settings.backendUrl ? 'configured' : 'not configured (debug shell only)'}. Original web files were read, not changed.`);
