import test from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl, makeTransport } from '../src/transport.mjs';

test('API destinations stay on the configured HTTPS backend', () => {
  assert.equal(apiUrl('/api/workspace?client=4', 'https://backend.example'), 'https://backend.example/api/workspace?client=4');
  for (const path of ['https://other.example/api/x', '//other.example/api/x', '/api/../../secret', '/api/\\evil', '/api/x\n']) {
    assert.throws(() => apiUrl(path, 'https://backend.example'));
  }
  assert.throws(() => apiUrl('/api/session', 'http://backend.example'));
});

test('native API transport preserves JSON payloads and statuses without leaking headers', async () => {
  let sent;
  const fetch = makeTransport(async options => {
    sent = options;
    return { status: 200, data: { ok: true }, headers: { 'Set-Cookie': 'test-fixture-only' } };
  }, 'https://backend.example');
  const result = await fetch('/api/logs', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'water', value: 250 }) });
  assert.equal(sent.url, 'https://backend.example/api/logs');
  assert.deepEqual(sent.data, { kind: 'water', value: 250 });
  assert.equal(sent.disableRedirects, true);
  assert.equal(sent.headers.Origin, undefined);
  assert.equal(sent.headers.Cookie, undefined);
  assert.equal(result.headers, undefined);
  assert.equal(result.ok, true);
  assert.deepEqual(await result.json(), { ok: true });
});

test('unauthorized response still reaches the original sign-in handling', async () => {
  const fetch = makeTransport(async () => ({ status: 401, data: '{"error":"Please sign in."}' }), 'https://backend.example');
  const response = await fetch('/api/workspace');
  assert.equal(response.status, 401);
  assert.equal(response.ok, false);
  assert.equal((await response.json()).error, 'Please sign in.');
});

test('native transport rejects redirects, invalid bodies and manually injected cookies', async () => {
  const fetch = makeTransport(async () => ({ status: 302, data: '' }), 'https://backend.example');
  await assert.rejects(fetch('/api/session'), /redirects/);
  await assert.rejects(fetch('/api/session', { headers: { Cookie: 'test-only' } }), /credentials/);
  await assert.rejects(fetch('/api/session', { method: 'DELETE' }), /method/);
  await assert.rejects(fetch('/api/session', { body: { invalid: true } }), /JSON/);
});

test('connection errors are propagated to the existing reconnect screen', async () => {
  const fetch = makeTransport(async () => { throw new Error('Network unavailable'); }, 'https://backend.example');
  await assert.rejects(fetch('/api/session'), /Network unavailable/);
});
