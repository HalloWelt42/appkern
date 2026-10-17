// Anfragen an das Backend der eigenen App. Der Token der Kellerwolke liegt im Gerät (localStorage) und geht im Kopf
// X-Kellerwolke-Sitzung mit; endet die Sitzung (401), meldet sich die Anmeldung. Ereignisströme laufen über fetch,
// damit auch dort der Kopf mitgeht.

export class ApiFehler extends Error {
  status: number;
  constructor(status: number, nachricht: string) {
    super(nachricht);
    this.status = status;
  }
}

export const verbindung = $state({ ok: true });

let schluessel = "app_sitzung";
let beiSitzungsende: (() => void) | null = null;

export function einrichten(kennung: string, sitzungsende: () => void): void {
  schluessel = `${kennung}_sitzung`;
  beiSitzungsende = sitzungsende;
}

export function token(): string {
  try {
    return localStorage.getItem(schluessel) ?? "";
  } catch {
    return "";
  }
}

export function setzeToken(wert: string): void {
  try {
    if (wert) localStorage.setItem(schluessel, wert);
    else localStorage.removeItem(schluessel);
  } catch {
    // ohne Speicher gilt die Anmeldung nur für diese Seite
  }
}

async function fehlerAus(antwort: Response): Promise<ApiFehler> {
  let text = antwort.statusText;
  try {
    const daten = await antwort.json();
    if (typeof daten.detail === "string") text = daten.detail;
  } catch {
    // Text bleibt
  }
  return new ApiFehler(antwort.status, text);
}

export async function hole<T>(pfad: string, init: RequestInit = {}): Promise<T> {
  let antwort: Response;
  try {
    antwort = await fetch(`/api/v1${pfad}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Kellerwolke-Sitzung": token(), ...(init.headers ?? {}) },
    });
  } catch {
    verbindung.ok = false;
    throw new ApiFehler(0, "Keine Verbindung zur App");
  }
  verbindung.ok = true;
  if (antwort.status === 401 && token()) {
    setzeToken("");
    beiSitzungsende?.();
  }
  if (!antwort.ok) throw await fehlerAus(antwort);
  if (antwort.status === 204) return undefined as T;
  return (await antwort.json()) as T;
}

export const json = (daten: unknown): RequestInit => ({ body: JSON.stringify(daten) });

// Server-Sent Events über fetch: liefert je Ereignis (Art, Daten); endet mit der Verbindung oder dem Abbruchsignal.
export async function* ereignisse(pfad: string, signal: AbortSignal): AsyncGenerator<{ art: string; daten: string }> {
  const antwort = await fetch(`/api/v1${pfad}`, { headers: { "X-Kellerwolke-Sitzung": token() }, signal });
  if (!antwort.ok || !antwort.body) throw await fehlerAus(antwort);
  const leser = antwort.body.pipeThrough(new TextDecoderStream()).getReader();
  let puffer = "";
  while (true) {
    const { value, done } = await leser.read();
    if (done) return;
    puffer += value;
    let ende: number;
    while ((ende = puffer.indexOf("\n\n")) >= 0) {
      const block = puffer.slice(0, ende);
      puffer = puffer.slice(ende + 2);
      let art = "message";
      const daten: string[] = [];
      for (const zeile of block.split("\n")) {
        if (zeile.startsWith("event: ")) art = zeile.slice(7);
        else if (zeile.startsWith("data: ")) daten.push(zeile.slice(6));
      }
      if (daten.length) yield { art, daten: daten.join("\n") };
    }
  }
}
