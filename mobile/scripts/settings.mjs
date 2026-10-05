import { readFile } from 'node:fs/promises';

export function validateSettings(settings, { release = false } = {}) {
  if (!/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$/.test(settings.appId || '')) {
    throw new Error('appId must be a lowercase Android application ID, such as com.shraz.flexibledieting.');
  }
  if (!settings.appName || typeof settings.appName !== 'string' || settings.appName.length > 60) {
    throw new Error('Set a short appName.');
  }
  if (!Number.isSafeInteger(settings.versionCode) || settings.versionCode < 1 || settings.versionCode > 2100000000) {
    throw new Error('versionCode must be a positive Android version integer.');
  }
  if (!/^\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?$/.test(settings.versionName || '')) {
    throw new Error('Use a versionName such as 0.1.0.');
  }
  const backendUrl = String(settings.backendUrl || '').trim();
  if (!backendUrl) {
    if (release) throw new Error('Release blocked: backendUrl has not been configured.');
    return { ...settings, backendUrl: '' };
  }
  let url;
  try { url = new URL(backendUrl); } catch { throw new Error('backendUrl must be an HTTPS origin.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('backendUrl must be an HTTPS origin, without credentials, path, query or fragment.');
  }
  if (release && (/^(localhost|127\..*|0\.0\.0\.0|\[::1\])$/i.test(url.hostname) || /\.(invalid|test|example|localhost)$/i.test(url.hostname))) {
    throw new Error('Release blocked: backendUrl is a development or placeholder address.');
  }
  return { ...settings, backendUrl: url.origin };
}

export async function loadSettings(options = {}) {
  const settings = JSON.parse(await readFile(new URL('../mobile.settings.json', import.meta.url), 'utf8'));
  // This value is a public service address, never a credential.
  if (process.env.SHRAZ_BACKEND_URL) settings.backendUrl = process.env.SHRAZ_BACKEND_URL;
  return validateSettings(settings, options);
}
