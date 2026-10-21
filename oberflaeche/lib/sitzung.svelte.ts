// Wer gerade da ist: App-Angaben, Anmeldung (Kellerwolke-Konto), erste Einrichtung. Antwortet die App beim Start
// nicht, zeigt die Schale das mit "Erneut versuchen"; sobald sie wieder antwortet, geht der Start von selbst weiter.
// Die Anmeldung erscheint an der Adresse, die geöffnet wurde (etwa ein Verweis aus einer anderen App mit Seite und
// Suchbegriff); nach dem Anmelden zeigt die App genau diese Stelle. Meldet sich ein anderer Tab derselben App an, ist
// dieser ohne weiteres Zutun auch angemeldet.
import { ApiFehler, beiTokenWechsel, einrichten, hole, json, setzeToken } from "./api.svelte";
import { beiRueckkehr } from "./erreichbar.svelte";
import { fassungVergleichen } from "./fassung.svelte";
import type { AppInfo, Konto } from "./typen";

export const sitzung = $state<{ geladen: boolean; app: AppInfo | null; angemeldet: boolean; konto: Konto | null }>({
  geladen: false,
  app: null,
  angemeldet: false,
  konto: null,
});

function vorbei(): void {
  sitzung.angemeldet = false;
  sitzung.konto = null;
}

// Wo Menschen die App öffnen, so wie der Browser es sieht; der Server trägt es einmal ein (Öffnen aus der Kellerwolke).
async function adresseMelden(): Promise<void> {
  try {
    await hole("/adresse", { method: "POST", ...json({ adresse: location.origin }) });
  } catch {
    // ohne Adresse fehlt nur das Öffnen aus der Kellerwolke; die Einstellung lässt sich auch von Hand setzen
  }
}

async function lesezugang(): Promise<void> {
  try {
    await hole("/anmeldung/zugang", { method: "POST" });
  } catch {
    // ohne Lesezugang fehlen nur Wiedergabe und Vorschauen
  }
}

let start: Promise<void> | null = null;
let rueckkehrGemeldet = false;

// App-Angaben und Anmeldung holen; nie zweimal gleichzeitig. Bleibt die Antwort aus, bleibt `app` leer.
export function starten(): Promise<void> {
  if (!rueckkehrGemeldet) {
    rueckkehrGemeldet = true;
    beiRueckkehr(() => {
      if (!sitzung.app) void starten();
    });
    beiTokenWechsel((wert) => {
      if (wert && !sitzung.angemeldet) void starten();
      else if (!wert && sitzung.angemeldet) vorbei();
    });
  }
  start ??= anfangen().finally(() => (start = null));
  return start;
}

async function anfangen(): Promise<void> {
  let app: AppInfo | null = null;
  try {
    app = await hole<AppInfo>("/app");
    einrichten(app.kennung, vorbei);
    fassungVergleichen(app, "start");
    if (!app.einrichtung_noetig) {
      const stand = await hole<{ angemeldet: boolean; konto: Konto | null }>("/anmeldung");
      if (stand.angemeldet) {
        await lesezugang();
        void adresseMelden();
      }
      sitzung.konto = stand.konto;
      sitzung.angemeldet = stand.angemeldet;
    }
  } catch (f) {
    if (!(f instanceof ApiFehler)) throw f;
    if (f.ohneAntwort) app = null;             // die Schale zeigt "antwortet nicht" statt einer falschen Anmeldung
  } finally {
    sitzung.app = app;
    sitzung.geladen = true;
  }
}

async function angemeldet(daten: { token: string; konto: Konto }): Promise<void> {
  setzeToken(daten.token);
  await lesezugang();
  void adresseMelden();
  sitzung.konto = daten.konto;
  sitzung.angemeldet = true;
}

export async function anmelden(kennung: string, passwort: string): Promise<void> {
  await angemeldet(await hole("/anmeldung", { method: "POST", ...json({ kennung, passwort }) }));
}

export async function koppeln(code: string, name: string, art: "webapp" | "browser"): Promise<void> {
  await angemeldet(await hole("/anmeldung/koppeln", { method: "POST", ...json({ code, name, art }) }));
}

// Erste Einrichtung; `einrichtungscode` nur von anderswo als dem Rechner der App nötig (er liegt dort in einer Datei).
export async function einrichtenMit(kellerwolke_adresse: string, kellerwolke_schluessel: string,
                                    einrichtungscode = ""): Promise<void> {
  sitzung.app = await hole<AppInfo>("/einrichtung", {
    method: "POST", ...json({ kellerwolke_adresse, kellerwolke_schluessel, einrichtungscode }),
  });
}

// Abmelden; auf einem gekoppelten Gerät heißt das: es trennt sich.
export async function abmelden(): Promise<void> {
  try {
    await hole("/anmeldung/abmelden", { method: "POST" });
  } catch {
    // egal: lokal ist man danach abgemeldet
  }
  setzeToken("");
  vorbei();
}
