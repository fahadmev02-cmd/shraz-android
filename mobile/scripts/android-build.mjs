import { spawnSync } from 'node:child_process';
import { access } from 'node:fs/promises';
import { constants } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { loadSettings } from './settings.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const mode = process.argv[2];
if (!['debug', 'release'].includes(mode)) throw new Error('Choose debug or release.');
const release = mode === 'release';
await loadSettings({ release });

const missing = [];
const java = process.env.JAVA_HOME ? resolve(process.env.JAVA_HOME, 'bin/java') : 'java';
const javac = process.env.JAVA_HOME ? resolve(process.env.JAVA_HOME, 'bin/javac') : 'javac';
const compiler = spawnSync(javac, ['-version'], { encoding: 'utf8' });
if (compiler.error || compiler.status !== 0 || !/^javac 21(?:\.|\s)/.test(compiler.stdout + compiler.stderr)) missing.push('JDK 21 (java, javac, keytool, jarsigner)');
const sdk = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
async function readable(path) { try { await access(path, constants.R_OK); return true; } catch { return false; } }
if (!sdk || !await readable(resolve(sdk, 'platforms/android-36/android.jar'))) missing.push('Android SDK Platform 36');
if (!sdk || !await readable(resolve(sdk, 'build-tools/36.0.0/aapt2'))) missing.push('Android Build Tools 36.0.0');
if (release) {
  for (const key of ['SHRAZ_KEYSTORE_PATH', 'SHRAZ_KEYSTORE_PASSWORD', 'SHRAZ_KEY_ALIAS', 'SHRAZ_KEY_PASSWORD']) {
    if (!process.env[key]) missing.push(`release signing input ${key} (not supplied)`);
  }
  if (!process.env.BUNDLETOOL_JAR || !await readable(process.env.BUNDLETOOL_JAR)) missing.push('bundletool JAR for AAB validation');
}
if (missing.length) {
  console.error('Android build not started. Missing requirements:\n- ' + missing.join('\n- '));
  process.exit(2);
}
function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', env: process.env });
  if (result.error || result.status !== 0) throw new Error('Build step failed. No verified artifact is being reported.');
}
run(process.execPath, ['scripts/prepare-web.mjs', ...(release ? ['--release'] : [])]);
run(process.execPath, ['node_modules/@capacitor/cli/bin/capacitor', 'sync', 'android']);
run('sh', ['gradlew', '--no-daemon', '--max-workers=2', release ? ':app:bundleRelease' : ':app:assembleDebug'], resolve(root, 'android'));
const artifact = resolve(root, release ? 'android/app/build/outputs/bundle/release/app-release.aab' : 'android/app/build/outputs/apk/debug/app-debug.apk');
await access(artifact);
if (release) {
  const jarsigner = process.env.JAVA_HOME ? resolve(process.env.JAVA_HOME, 'bin/jarsigner') : 'jarsigner';
  const verification = spawnSync(jarsigner, ['-J-Duser.language=en', '-verify', artifact], { encoding: 'utf8', env: { ...process.env, LC_ALL: 'C' } });
  if (verification.status !== 0 || !verification.stdout.includes('jar verified.')) throw new Error('AAB signature verification failed.');
  run(java, ['-jar', process.env.BUNDLETOOL_JAR, 'validate', '--bundle=' + artifact]);
} else {
  run(resolve(sdk, 'build-tools/36.0.0/apksigner'), ['verify', artifact]);
  run(resolve(sdk, 'build-tools/36.0.0/aapt2'), ['dump', 'badging', artifact]);
}
console.log(`Generated and verified ${release ? 'signed AAB' : 'debug APK'}: ${artifact}`);
