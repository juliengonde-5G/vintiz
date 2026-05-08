/**
 * Vintiz back-office service worker.
 *
 * Scope (M2): minimal — install/activate skip-waiting + Web Push handler
 * + notification click router. No precaching of app shell yet (Next.js
 * already ships hashed asset names so the browser cache is enough).
 *
 * Why a SW now (M2 hardware migration):
 *  - Web Push works on Chrome Android out of the box ; iOS Safari only
 *    started shipping it in 16.4 (HomeScreen-installed PWAs only). The
 *    Lenovo Idea Tab Pro 13" + Galaxy Tab S11 Ultra unlock realtime
 *    alerts that iPad-first Vintiz couldn't deliver.
 *  - Installing this empty SW now means the front client picks it up
 *    automatically the day push subscriptions are wired in, no re-deploy.
 *
 * Future extensions (separate sprints):
 *  - Push subscriptions stored back-end side, VAPID key handshake.
 *  - Background sync for the offline-queue (currently in-page only).
 *  - Asset precaching for the POS page so it boots if the Wi-Fi blips
 *    during a sale.
 */

self.addEventListener('install', (event) => {
  // Activate immediately on first install — the back-office is a single
  // tab, no tab-coordination penalty.
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

/**
 * Web Push handler.
 *
 * Server is expected to push a JSON payload of the shape:
 *   { title: string, body: string, url?: string, tag?: string }
 *
 * Falls back to a generic Vintiz notification when the payload is empty
 * or malformed (some push providers send "ping" packets to keep the
 * subscription warm).
 */
self.addEventListener('push', (event) => {
  let payload = { title: 'Vintiz', body: 'Nouvelle notification', url: '/' };
  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch (_e) {
      // Plain-text payload — surface as the body.
      payload.body = event.data.text() || payload.body;
    }
  }

  const options = {
    body: payload.body,
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: payload.tag || 'vintiz',
    data: { url: payload.url || '/' },
  };

  event.waitUntil(self.registration.showNotification(payload.title, options));
});

/**
 * Notification click — focus an existing back-office tab (matched by
 * pathname prefix), or open a new one on the target URL. Avoids spawning
 * duplicate tabs when the cashier already has Vintiz open.
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          // Same origin ? Bring it to front and navigate if needed.
          if (client.url && 'focus' in client) {
            const url = new URL(client.url);
            const target = new URL(targetUrl, self.location.origin);
            if (url.origin === target.origin) {
              client.navigate(target.pathname + target.search);
              return client.focus();
            }
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      }),
  );
});
