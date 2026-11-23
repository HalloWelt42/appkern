// Übergabe zwischen Geräten (RAD-18, aus TubeVault): jedes Fenster der App meldet sich beim Vermittler
// (appkern/uebergabe, WebSocket) und sieht die anderen Fenster desselben Kontos mit ihrem Zustand. Holen bittet ein
// anderes Gerät, seine Wiedergabe herzugeben; Dorthin gibt die eigene ab. Was ein Zustand und ein Paket sind und was
// beim Annehmen und Abgeben geschieht, sagt die App über ihren Weg (`UebergabeWeg`); dieser Baustein kennt nur die
// Verbindung und die Geräteliste.
import { token } from "./api.svelte";

export type Geraeteart = "rechner" | "telefon" | "tablet";

export interface GeraetInfo<Z> {
  id: string;
  geraet: string;
  name: string;
  art: Geraeteart;
  seit: number;
  aktiv: number;
  zustand: Z | null;
}

/** Was die App beiträgt; der Zustand braucht `laeuft`, damit die Liste weiß, wo etwas spielt */
export interface UebergabeWeg<Z extends { laeuft: boolean }, P> {
  /** die eigene Wiedergabe als Paket (samt Stelle), null: nichts abzugeben */
  paket(): P | null;
  /** ein anderes Gerät gibt seine Wiedergabe hierher: spielen */
  annehmen(paket: P, von: string): void;
  /** die eigene Wiedergabe ist abgegeben: hier anhalten */
  abgegeben(): void;
  /** ein anderes Gerät steuert dieses (RAD-96): welche Aktionen es gibt, bestimmt die App; unbekannte übergehen */
  befehl?(aktion: string, wert: number | null, von: string): void;
}

const PAUSEN_MS = [1000, 2000, 5000, 10000, 30000];
const PING_MS = 25000;

function gemerkt(speicher: Storage | undefined, schluessel: string, neu: () => string): string {
  try {
    const da = speicher?.getItem(schluessel);
    if (da) return da;
    const wert = neu();
    speicher?.setItem(schluessel, wert);
    return wert;
  } catch {
    return neu();
  }
}

function eigeneArt(): Geraeteart {
  const finger = matchMedia("(pointer: coarse)").matches;
  if (!finger) return "rechner";
  return Math.min(screen.width, screen.height) >= 600 ? "tablet" : "telefon";
}

const VORGABE_NAME: Record<Geraeteart, string> = { rechner: "Rechner", telefon: "Telefon", tablet: "Tablet" };

export class Uebergabe<Z extends { laeuft: boolean }, P> {
  geraete = $state<GeraetInfo<Z>[]>([]);
  ichId = $state("");
  verbunden = $state(false);
  /** letzte Meldung des Vermittlers (etwa "Das Gerät ist nicht mehr da"), leer ohne */
  meldung = $state("");

  /** die anderen Geräte, das zuletzt aktive zuerst */
  andere = $derived(this.geraete.filter((g) => g.id !== this.ichId).sort((a, b) => b.aktiv - a.aktiv));
  /** wo außer hier gerade etwas spielt */
  spielenWoanders = $derived(this.andere.filter((g) => g.zustand?.laeuft));
  ich = $derived(this.geraete.find((g) => g.id === this.ichId) ?? null);

  private ws: WebSocket | null = null;
  private weg: UebergabeWeg<Z, P> | null = null;
  private versuch = 0;
  private ping?: ReturnType<typeof setInterval>;
  private zuletztGemeldet = "";
  private beendet = false;
  private hoertSichtbar = false;

  constructor(private readonly pfad = "/api/v1/geraete/ws", private readonly kennung = "app") {}

  /** einmal beim Start der App; meldet danach jeden Zustand über `melden` */
  starten(weg: UebergabeWeg<Z, P>): void {
    this.weg = weg;
    this.beendet = false;
    this.verbinden();
    if (!this.hoertSichtbar) {
      this.hoertSichtbar = true;
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") this.senden({ typ: "aktiv" });
      });
    }
  }

  beenden(): void {
    this.beendet = true;
    clearInterval(this.ping);
    this.ws?.close();
    this.ws = null;
    this.geraete = [];
    this.verbunden = false;
  }

  /** was hier spielt, für die anderen (null: nichts); gleiche Meldungen gehen nur einmal hinaus */
  melden(zustand: Z | null): void {
    const text = JSON.stringify(zustand);
    if (text === this.zuletztGemeldet) return;
    this.zuletztGemeldet = text;
    this.senden({ typ: "zustand", zustand });
  }

  /** die Wiedergabe von dort hierher holen */
  holen(id: string): void {
    this.senden({ typ: "befehl", an: id, aktion: "abgeben" });
  }

  /** die eigene Wiedergabe dorthin geben; hier hält sie an */
  dorthin(id: string): boolean {
    const paket = this.weg?.paket();
    if (!paket) return false;
    this.geben(id, paket);
    this.weg?.abgegeben();
    return true;
  }

  /** ein Paket auf dem anderen Gerät spielen lassen; hier ändert sich nichts */
  geben(id: string, paket: P): void {
    this.senden({ typ: "uebergabe", an: id, paket });
  }

  /** das andere Gerät steuern (RAD-96): Aktion der App, bei Bedarf mit einer Zahl */
  befehlen(id: string, aktion: string, wert: number | null = null): void {
    this.senden({ typ: "befehl", an: id, aktion, wert });
  }

  umbenennen(name: string): void {
    try { localStorage.setItem(`${this.kennung}.uebergabe.name`, name); } catch { /* nur für diese Sitzung */ }
    this.senden({ typ: "name", name });
  }

  private verbinden(): void {
    if (this.beendet) return;
    const adresse = new URL(this.pfad, location.href);
    adresse.protocol = adresse.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(adresse);
    this.ws = ws;
    const art = eigeneArt();
    ws.onopen = () => {
      ws.send(JSON.stringify({
        typ: "anmelden", token: token(), art,
        id: gemerkt(globalThis.sessionStorage, `${this.kennung}.uebergabe.fenster`, () => crypto.randomUUID()),
        geraet: gemerkt(globalThis.localStorage, `${this.kennung}.uebergabe.geraet`, () => crypto.randomUUID()),
        name: gemerkt(globalThis.localStorage, `${this.kennung}.uebergabe.name`, () => VORGABE_NAME[art]),
      }));
      clearInterval(this.ping);
      this.ping = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), PING_MS);
    };
    ws.onmessage = (e) => {
      if (e.data === "pong") return;
      try { this.empfangen(JSON.parse(e.data)); } catch { /* nicht verstanden: übergehen */ }
    };
    ws.onclose = (e) => {
      clearInterval(this.ping);
      this.verbunden = false;
      if (this.ws !== ws || this.beendet) return;
      // abgewiesen (nicht angemeldet): erst nach einer Weile wieder, sonst mit wachsender Pause
      const pause = e.code === 4401 ? PAUSEN_MS[PAUSEN_MS.length - 1] : PAUSEN_MS[Math.min(this.versuch++, PAUSEN_MS.length - 1)];
      setTimeout(() => this.verbinden(), pause);
    };
  }

  private empfangen(n: Record<string, unknown>): void {
    switch (n.typ) {
      case "willkommen":
        this.verbunden = true;
        this.versuch = 0;
        this.ichId = (n.du as GeraetInfo<Z>).id;
        this.geraete = n.geraete as GeraetInfo<Z>[];
        if (this.zuletztGemeldet) this.senden({ typ: "zustand", zustand: JSON.parse(this.zuletztGemeldet) });
        break;
      case "geraete":
        this.geraete = n.geraete as GeraetInfo<Z>[];
        break;
      case "zustand":
        this.geraete = this.geraete.map((g) => (g.id === n.id ? { ...g, zustand: n.zustand as Z | null } : g));
        break;
      case "befehl":
        if (n.aktion === "abgeben") this.dorthin(n.von as string);
        else this.weg?.befehl?.(String(n.aktion), typeof n.wert === "number" ? n.wert : null, String(n.von_name ?? ""));
        break;
      case "uebergabe":
        this.weg?.annehmen(n.paket as P, n.von_name as string);
        break;
      case "fehler":
        this.meldung = String(n.text ?? "");
        break;
    }
  }

  private senden(nachricht: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(nachricht));
  }
}
