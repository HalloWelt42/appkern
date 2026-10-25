// Dienst im Browser für Mitteilungen einer App des Appkerns (appkern/push). Er zeigt Mitteilungen und führt ein Tippen
// in die App; er hat bewusst keinen fetch-Handler und hält nichts im Zwischenspeicher, die App kommt immer frisch vom
// Server. Ausgeliefert unter /api/v1/push/dienst.js mit dem Kopf Service-Worker-Allowed: /, angemeldet für den Bereich /.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (ereignis) => ereignis.waitUntil(self.clients.claim()));

// Nutzlast vom Server (Mitteilung in appkern/push/dienst.py): titel, text, url, tag, dringend
self.addEventListener("push", (ereignis) => {
  let d = {};
  try {
    d = ereignis.data ? ereignis.data.json() : {};
  } catch {
    d = { text: ereignis.data ? ereignis.data.text() : "" };
  }
  ereignis.waitUntil(
    self.registration.showNotification(d.titel || "Mitteilung", {
      body: d.text || "",
      tag: d.tag || undefined,
      renotify: Boolean(d.tag),
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      lang: "de",
      requireInteraction: Boolean(d.dringend),
      data: { url: d.url || "/" },
    }),
  );
});

// Antippen: ein offenes Fenster der App bekommt das Ziel als Nachricht (sie geht ohne Neuladen dorthin), sonst öffnet
// sich die App an diesem Ziel.
self.addEventListener("notificationclick", (ereignis) => {
  ereignis.notification.close();
  const ziel = new URL(ereignis.notification.data?.url || "/", self.location.origin).href;
  ereignis.waitUntil(
    (async () => {
      const fenster = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const app = fenster[0];
      if (app) {
        app.postMessage({ art: "mitteilung", url: ziel });
        return app.focus();
      }
      return self.clients.openWindow(ziel);
    })(),
  );
});
