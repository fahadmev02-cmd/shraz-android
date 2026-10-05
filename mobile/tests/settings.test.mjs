import test from 'node:test';
import assert from 'node:assert/strict';
import { validateSettings } from '../scripts/settings.mjs';

const baseline = { appId: 'com.shraz.flexibledieting', appName: 'Shraz', backendUrl: '', versionCode: 1, versionName: '0.1.0' };

test('debug source can be generated without guessing a backend address', () => {
  assert.equal(validateSettings(baseline).backendUrl, '');
  assert.throws(() => validateSettings(baseline, { release: true }), /not been configured/);
});

test('release rejects plaintext, placeholder or credential-bearing backend addresses', () => {
  for (const backendUrl of ['http://host.example', 'https://user:password@host.example', 'https://host.example/path', 'https://host.example/?token=not-real', 'https://localhost', 'https://backend.invalid']) {
    assert.throws(() => validateSettings({ ...baseline, backendUrl }, { release: true }));
  }
  assert.equal(validateSettings({ ...baseline, backendUrl: 'https://api.shraz-fitness.com/' }, { release: true }).backendUrl, 'https://api.shraz-fitness.com');
});

test('app identity and version fields are validated before preparing assets', () => {
  assert.throws(() => validateSettings({ ...baseline, appId: 'not-an-id' }));
  assert.throws(() => validateSettings({ ...baseline, versionCode: -1 }));
  assert.throws(() => validateSettings({ ...baseline, versionCode: 1.5 }));
  assert.throws(() => validateSettings({ ...baseline, versionName: 'latest' }));
});
