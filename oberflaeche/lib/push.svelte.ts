// Mitteilungen aufs Gerät (Web Push) für jede App des Appkerns (Gegenstück zu appkern/push). Geht nur in einem sicheren
// Kontext (HTTPS oder localhost) und auf dem iPhone nur aus der App auf dem Home-Bildschirm. Der Dienst im Browser kommt
// vom Server (/api/v1/push/dienst.js); ein Tippen auf eine Mitteilung führt über die Navigation an ihr Ziel. Die App
// zeichnet die Bedienung selbst, die Logik bleibt hier.
import { hole, json } from "./api.svelte";
import { gehe } from "./navigation.svelte";

export type PushLage = "geht" | "unsicher" | "heimbildschirm" | "nicht-unterstuetzt" | "verweigert";

export interface PushGeraet {
  id: string;
  name: string;
  angelegt: string;
  zuletzt?: string | null;
}

export interface PushVersand {
  zugestellt: number;
  entfernt: number;
  fehler: number;
}

const DIENST = "/api/v1/push/dienst.js";

/** Stand dieses Geräts: ob es Mitteilungen bekommt (null: noch nicht geprüft) */
export const push = $state<{ an: boolean | null }>({ an: null });

function istIos(): boolean {
  return /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function vomHeimbildschirm(): boolean {
  return matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/** Kann dieses Gerät Mitteilungen bekommen, und wenn nicht, warum */
export function pushLage(): PushLage {
  if (!isSecureContext) return "unsicher";
  if (istIos() && !vomHeimbildschirm()) return "heimbildschirm";
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return "nicht-unterstuetzt";
  if (Notification.permission === "denied") return "verweigert";
  return "geht";
}

/** Name dieses Geräts für die Liste der Geräte ("iPhone, Web-App") */
export function pushGeraetName(): string {
  const ua = navigator.userAgent;
  const art = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) || (istIos() && !/iPhone/.test(ua)) ? "iPad" : /Android/.test(ua) ? "Android"
    : /Macintosh/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "Gerät";
  return vomHeimbildschirm() ? `${art}, Web-App` : `${art}, Browser`;
}

function bytes(base64url: string): Uint8Array<ArrayBuffer> {
  const b64 = base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4);
  const roh = atob(b64);
  const ergebnis = new Uint8Array(new ArrayBuffer(roh.length));
  for (let i = 0; i < roh.length; i++) ergebnis[i] = roh.charCodeAt(i);
  return ergebnis;
}

function gleicherSchluessel(abo: PushSubscription, schluessel: Uint8Array): boolean {
  const vorhanden = abo.options.applicationServerKey;
  if (!vorhanden) return false;
  const a = new Uint8Array(vorhanden);
  return a.length === schluessel.length && a.every((b, i) => b === schluessel[i]);
}

async function serverSchluessel(): Promise<Uint8Array<ArrayBuffer>> {
  return bytes((await hole<{ schluessel: string }>("/push/schluessel")).schluessel);
}

async function dienst(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register(DIENST, { scope: "/" });
  return navigator.serviceWorker.ready;
}

/** Beim Start der App: ein Tippen auf eine Mitteilung führt an ihr Ziel, und der Stand dieses Geräts wird geprüft
 *  (bekommt es Mitteilungen mit dem Schlüssel dieses Servers?). Ein Abo mit altem Schlüssel gilt als aus. */
export async function pushStarten(): Promise<void> {
  if (pushLage() === "unsicher" || !("serviceWorker" in navigator)) {
    push.an = false;
    return;
  }
  navigator.serviceWorker.addEventListener("message", (e: MessageEvent) => {
    if (e.data?.art === "mitteilung" && typeof e.data.url === "string") {
      const ziel = new URL(e.data.url, location.origin);
      gehe(ziel.pathname + ziel.search);
    }
  });
  try {
    const reg = await navigator.serviceWorker.getRegistration("/");
    const abo = await reg?.pushManager.getSubscription();
    push.an = !!abo && Notification.permission === "granted" && gleicherSchluessel(abo, await serverSchluessel());
  } catch {
    push.an = false;
  }
}

/** Mitteilungen auf diesem Gerät einschalten. Im Tippen aufrufen: die Erlaubnis muss die erste Frage nach der Berührung
 *  sein (iPhone). Ergebnis: ok, verweigert (vom Gerät) oder fehler (Grund im Protokoll der Konsole). */
export async function pushEinschalten(name = pushGeraetName()): Promise<"ok" | "verweigert" | "fehler"> {
  const erlaubnis = await Notification.requestPermission();
  if (erlaubnis !== "granted") return "verweigert";
  try {
    const reg = await dienst();
    const schluessel = await serverSchluessel();
    let abo = await reg.pushManager.getSubscription();
    if (abo && !gleicherSchluessel(abo, schluessel)) {
      await abo.unsubscribe();
      abo = null;
    }
    abo ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: schluessel });
    await hole("/push/abo", { method: "POST", ...json({ abo: abo.toJSON(), geraet: name }) });
    push.an = true;
    return "ok";
  } catch (f) {
    console.warn("Mitteilungen ließen sich nicht einschalten", f);
    return "fehler";
  }
}

/** Mitteilungen auf diesem Gerät ausschalten: das Abo geht beim Browser und beim Server */
export async function pushAusschalten(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration("/");
  const abo = await reg?.pushManager.getSubscription();
  if (abo) {
    await hole("/push/abo/entfernen", { method: "POST", ...json({ endpunkt: abo.endpoint }) });
    await abo.unsubscribe();
  }
  push.an = false;
}

/** Geräte der angemeldeten Person, die Mitteilungen bekommen */
export function pushGeraete(): Promise<PushGeraet[]> {
  return hole<PushGeraet[]>("/push/geraete");
}

/** Ein Gerät aus der Liste nehmen (es bekommt danach keine Mitteilungen mehr) */
export async function pushGeraetEntfernen(id: string): Promise<void> {
  await hole(`/push/geraete/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** Eine Probe an alle Geräte der Person */
export function pushProbe(): Promise<PushVersand> {
  return hole<PushVersand>("/push/probe", { method: "POST" });
}
