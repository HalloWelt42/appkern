// Ob die App selbst antwortet, an einer Stelle für die ganze Schale. Jede Anfrage meldet hierher, wie sie ausging.
// Bleibt die Antwort aus (kein Netz, der Vorschaltdienst findet die App nicht), fragt eine einzige Probe nach
// (`/api/v1/app`, ohne Anmeldung) mit wachsender Pause: 2 s, dann doppelt so lange, höchstens 60 s. Antwortet die App
// wieder, laufen die Rückkehr-Hörer (Abfragen nachholen, Seiten neu laden). Eine überschrittene Zeitgrenze allein heißt
// noch nicht "weg" (eine einzelne Abfrage kann langsam sein): dann fragt die Probe sofort, und erst wenn auch sie
// keine Antwort bekommt, gilt die App als nicht antwortend.

const ERSTE_PAUSE_MS = 2000;
const LAENGSTE_PAUSE_MS = 60000;

// `ok`: die App antwortet; `meldung`: warum nicht; `prueft`: die Probe läuft gerade.
export const verbindung = $state<{ ok: boolean; meldung: string; prueft: boolean }>({ ok: true, meldung: "", prueft: false });

export const KEINE_VERBINDUNG = "Keine Verbindung zur App";
export const ANTWORTET_NICHT = "Die App antwortet nicht";

let zeitgrenzeMs = 20000;
let pause = ERSTE_PAUSE_MS;
let wecker: ReturnType<typeof setTimeout> | null = null;
let probe: Promise<boolean> | null = null;
const hoerer = new Set<() => void>();

// Zeitgrenze jeder Anfrage an die App (auch der Probe); 0 heißt ohne Grenze.
export function zeitgrenze(): number {
  return zeitgrenzeMs;
}

export function zeitgrenzeSetzen(ms: number): void {
  zeitgrenzeMs = Math.max(0, ms);
}

// Antworten, die nicht von der App kommen: der Vorschaltdienst meldet, dass er sie nicht erreicht (ohne JSON der App).
export function vomVorschaltdienst(antwort: Response): boolean {
  return antwort.status >= 502 && antwort.status <= 504 && !(antwort.headers.get("content-type") ?? "").includes("json");
}

// Die App hat geantwortet (gleich mit welchem Status).
export function geantwortet(): void {
  pause = ERSTE_PAUSE_MS;
  if (wecker) clearTimeout(wecker);
  wecker = null;
  if (verbindung.ok) return;
  verbindung.ok = true;
  verbindung.meldung = "";
  for (const fn of [...hoerer]) {
    try {
      fn();
    } catch {
      // ein Hörer darf die anderen nie aufhalten
    }
  }
}

// Keine Antwort: die App gilt als weg, bis die Probe sie wieder erreicht.
export function nichtErreicht(meldung = KEINE_VERBINDUNG): void {
  verbindung.ok = false;
  verbindung.meldung = meldung;
  planen();
}

// Eine Anfrage brauchte zu lange: sofort nachsehen, ob die App überhaupt antwortet.
export function zuLangsam(): void {
  void pruefen();
}

function planen(): void {
  if (wecker || probe) return;
  wecker = setTimeout(() => {
    wecker = null;
    void pruefen();
  }, pause);
  pause = Math.min(pause * 2, LAENGSTE_PAUSE_MS);
}

// Die Probe, nie zweimal gleichzeitig; auch für den Knopf "Erneut versuchen". Liefert, ob die App antwortet.
export function pruefen(): Promise<boolean> {
  if (probe) return probe;
  if (wecker) clearTimeout(wecker);
  wecker = null;
  verbindung.prueft = true;
  probe = (async () => {
    const steuerung = new AbortController();
    const uhr = zeitgrenzeMs > 0 ? setTimeout(() => steuerung.abort(), zeitgrenzeMs) : null;
    let meldung = KEINE_VERBINDUNG;
    try {
      const antwort = await fetch("/api/v1/app", { signal: steuerung.signal, cache: "no-store" });
      await antwort.arrayBuffer();
      if (vomVorschaltdienst(antwort)) {
        meldung = ANTWORTET_NICHT;
        throw new Error(meldung);
      }
      probe = null;
      geantwortet();
      return true;
    } catch {
      probe = null;
      nichtErreicht(steuerung.signal.aborted ? ANTWORTET_NICHT : meldung);
      return false;
    } finally {
      if (uhr) clearTimeout(uhr);
      probe = null;
      verbindung.prueft = false;
    }
  })();
  return probe;
}

// `fn` läuft jedes Mal, wenn die App nach einem Ausfall wieder antwortet; zurück kommt das Abmelden.
export function beiRueckkehr(fn: () => void): () => void {
  hoerer.add(fn);
  return () => hoerer.delete(fn);
}

// Erfüllt, sobald die App antwortet (sofort, wenn sie es schon tut), oder wenn `signal` abbricht.
export function rueckkehr(signal?: AbortSignal): Promise<void> {
  if (verbindung.ok || signal?.aborted) return Promise.resolve();
  return new Promise((fertig) => {
    const ende = () => {
      weg();
      signal?.removeEventListener("abort", ende);
      fertig();
    };
    const weg = beiRueckkehr(ende);
    signal?.addEventListener("abort", ende, { once: true });
  });
}
