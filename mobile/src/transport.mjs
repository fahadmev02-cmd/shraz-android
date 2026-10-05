export function apiUrl(path, backendUrl) {
  if (typeof path !== 'string' || !path.startsWith('/api/') || path.includes('\\') || /[\r\n]/.test(path)) {
    throw new Error('Only Shraz API paths are allowed through the native transport.');
  }
  const base = new URL(backendUrl);
  const target = new URL(path, base);
  if (base.protocol !== 'https:' || target.origin !== base.origin || !target.pathname.startsWith('/api/')) {
    throw new Error('Invalid API destination.');
  }
  return target.href;
}

export function makeTransport(request, backendUrl) {
  return async function nativeFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const method = String(options.method || 'GET').toUpperCase();
    if (!['GET', 'POST'].includes(method)) throw new Error('Unsupported Shraz API method.');
    let data;
    if (options.body !== undefined) {
      if (typeof options.body !== 'string') throw new Error('Shraz requests must contain JSON.');
      data = JSON.parse(options.body);
    }
    // Native HTTP uses Android's cookie manager. Never copy cookies into JS storage,
    // and do not send the local WebView Origin as the remote server Origin.
    const nativeHeaders = { Accept: 'application/json' };
    if (data !== undefined) nativeHeaders['Content-Type'] = 'application/json';
    if (headers.has('Authorization') || headers.has('Cookie')) throw new Error('Manually supplied credentials are not supported.');
    const result = await request({
      url: apiUrl(path, backendUrl), method, headers: nativeHeaders,
      ...(data === undefined ? {} : { data }),
      responseType: 'json', connectTimeout: 15000, readTimeout: 20000,
      disableRedirects: true
    });
    if (result.status >= 300 && result.status < 400) throw new Error('API redirects are not supported; configure the final HTTPS backend origin.');
    if (result.status < 100) throw new Error('The server could not be reached. Check your connection.');
    // Do not expose response headers (including Set-Cookie) to application code.
    return {
      ok: result.status >= 200 && result.status < 300,
      status: result.status,
      json: async () => typeof result.data === 'string' ? JSON.parse(result.data) : result.data
    };
  };
}
