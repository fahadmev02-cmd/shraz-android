import { Capacitor, CapacitorHttp } from '@capacitor/core';
import { App } from '@capacitor/app';
import { apiUrl, makeTransport } from './transport.mjs';

const settings = __SHRAZ_SETTINGS__;
const native = Capacitor.isNativePlatform();
const browserFetch = window.fetch.bind(window);
const transport = settings.backendUrl ? makeTransport(options => CapacitorHttp.request(options), settings.backendUrl) : null;

window.fetch = (path, options) => {
  if (typeof path === 'string' && path.startsWith('/api/')) {
    if (!native) return Promise.reject(new Error('This is the Android asset bundle. Run the original web app in a browser.'));
    if (!transport) return Promise.reject(new Error('This Android build has no backend configured. The app publisher must set backendUrl and rebuild.'));
    return transport(path, options);
  }
  return browserFetch(path, options);
};

// <img> requests do not pass through fetch. Retrieve private photos through the
// same authenticated native channel, and only keep temporary in-memory blobs.
const blobs = new Map();
async function loadPrivatePhoto(image, path) {
  if (!native || !settings.backendUrl) return;
  image.dataset.nativePhoto = path;
  image.removeAttribute('src');
  try {
    const response = await CapacitorHttp.request({
      url: apiUrl(path, settings.backendUrl), method: 'GET',
      responseType: 'arraybuffer', connectTimeout: 15000, readTimeout: 20000,
      disableRedirects: true
    });
    if (response.status !== 200) throw new Error('Photo access failed.');
    const type = Object.entries(response.headers || {}).find(([key]) => key.toLowerCase() === 'content-type')?.[1]?.split(';')[0];
    if (!['image/png', 'image/jpeg'].includes(type)) throw new Error('Unsupported photo type.');
    if (typeof response.data !== 'string' || response.data.length > 2800000) throw new Error('Photo payload is invalid.');
    const bytes = Uint8Array.from(atob(response.data), char => char.charCodeAt(0));
    if (!image.isConnected) return;
    const blob = URL.createObjectURL(new Blob([bytes], { type }));
    blobs.set(image, blob);
    image.src = blob;
  } catch {
    if (image.isConnected) image.alt = 'Photo unavailable. Refresh after checking your connection or signing in again.';
  }
}

const observer = new MutationObserver(() => {
  for (const [image, blob] of blobs) {
    if (!image.isConnected) { URL.revokeObjectURL(blob); blobs.delete(image); }
  }
  for (const image of document.querySelectorAll('img[data-private-photo]:not([data-native-photo])')) {
    void loadPrivatePhoto(image, image.dataset.privatePhoto);
  }
});
observer.observe(document.documentElement, { childList: true, subtree: true });

if (native) {
  // Tabs use replaceState, so handle Android Back explicitly.
  App.addListener('backButton', () => {
    const dialog = document.querySelector('dialog[open]');
    if (dialog) { dialog.close(); return; }
    const active = document.querySelector('.mobile-nav [aria-current="page"]');
    if (active && active.dataset.tab !== 'home') {
      document.querySelector('.mobile-nav [data-tab="home"]')?.click();
    } else {
      void App.minimizeApp();
    }
  });
}
