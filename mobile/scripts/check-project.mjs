import { readFile, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const config = JSON.parse(await readFile(resolve(root, 'capacitor.config.json'), 'utf8'));
const info = JSON.parse(await readFile(resolve(root, 'build-info.json'), 'utf8'));
assert.equal(config.server.url, undefined, 'Remote website loading must not replace the bundled UI.');
assert.equal(config.loggingBehavior, 'none', 'Native session cookies must not appear in Capacitor logs.');
assert.equal(config.server.cleartext, false);
for (const name of ['index.html', 'app.js', 'styles.css', 'icon.svg']) {
  const original = await readFile(resolve(root, '../static', name));
  assert.equal(createHash('sha256').update(original).digest('hex'), info.sourceHashes[name], `Original ${name} changed after asset preparation.`);
  assert.deepEqual(await readFile(resolve(root, 'www', name)), await readFile(resolve(root, 'android/app/src/main/assets/public', name)), `Run cap sync: ${name} is stale.`);
}
for (const name of ['android/gradlew', 'android/gradle/wrapper/gradle-wrapper.jar', 'android/app/src/main/java/com/shraz/flexibledieting/MainActivity.java']) await access(resolve(root, name));
const app = await readFile(resolve(root, 'www/app.js'), 'utf8');
assert.ok(app.includes('data-private-photo='));
assert.ok(!app.includes("navigator.serviceWorker.register"));
const html = await readFile(resolve(root, 'www/index.html'), 'utf8');
assert.ok(html.indexOf('src="/native.js"') < html.indexOf('src="/app.js"'));
const manifest = await readFile(resolve(root, 'android/app/src/main/AndroidManifest.xml'), 'utf8');
assert.ok(manifest.includes('android:allowBackup="false"'));
assert.ok(manifest.includes('android:usesCleartextTraffic="false"'));
assert.ok(!manifest.includes('READ_MEDIA_IMAGES') && !manifest.includes('READ_EXTERNAL_STORAGE'));
console.log('PASS: Capacitor Android structure, original web hashes, synced assets, native adapter ordering, private media wiring and manifest configuration.');
console.log('This validates source/configuration only; it does not verify compilation or device behavior.');
