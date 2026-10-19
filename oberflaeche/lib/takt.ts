// Regelmäßige Abfrage der Schale (Verbindungen, Fassung): nie zwei Läufe gleichzeitig. Solange die App nicht
// antwortet, ruht sie; dann fragt nur die Probe in erreichbar.svelte.ts mit wachsender Pause nach, und sobald die App
// wieder antwortet, läuft die Abfrage sofort.
import { beiRueckkehr, verbindung } from "./erreichbar.svelte";

export interface Takt {
  jetzt: () => Promise<void>;    // sofort (läuft schon einer, dieser)
  stoppen: () => void;
}

// `arbeit` alle `abstandMs` nach dem Ende des letzten Laufs; mit `sofort` auch gleich zu Beginn.
export function takt(arbeit: () => Promise<unknown>, abstandMs: number, { sofort = true } = {}): Takt {
  let lauf: Promise<void> | null = null;
  let wecker: ReturnType<typeof setTimeout> | null = null;
  let aus = false;

  function planen(): void {
    if (wecker) clearTimeout(wecker);
    wecker = !aus && verbindung.ok ? setTimeout(jetzt, abstandMs) : null;
  }

  function jetzt(): Promise<void> {
    if (lauf) return lauf;
    if (wecker) clearTimeout(wecker);
    wecker = null;
    lauf = (async () => {
      try {
        await arbeit();
      } catch {
        // ob die App antwortet, zeigt die Schale; die nächste Runde kommt nach Plan oder mit der Rückkehr
      } finally {
        lauf = null;
        planen();
      }
    })();
    return lauf;
  }

  const abmelden = beiRueckkehr(() => void jetzt());
  if (sofort) void jetzt();
  else planen();
  return {
    jetzt,
    stoppen: () => {
      aus = true;
      if (wecker) clearTimeout(wecker);
      abmelden();
    },
  };
}
