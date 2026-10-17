// Wer gerade da ist: App-Angaben, Anmeldung (Kellerwolke-Konto), erste Einrichtung.
import { ApiFehler, einrichten, hole, json, setzeToken } from "./api.svelte";
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

async function lesezugang(): Promise<void> {
  try {
    await hole("/anmeldung/zugang", { method: "POST" });
  } catch {
    // ohne Lesezugang fehlen nur Wiedergabe und Vorschauen
  }
}

export async function starten(): Promise<void> {
  try {
    sitzung.app = await hole<AppInfo>("/app");
    einrichten(sitzung.app.kennung, vorbei);
    if (!sitzung.app.einrichtung_noetig) {
      const stand = await hole<{ angemeldet: boolean; konto: Konto | null }>("/anmeldung");
      if (stand.angemeldet) await lesezugang();
      sitzung.konto = stand.konto;
      sitzung.angemeldet = stand.angemeldet;
    }
  } catch (f) {
    if (!(f instanceof ApiFehler)) throw f;
  } finally {
    sitzung.geladen = true;
  }
}

async function angemeldet(daten: { token: string; konto: Konto }): Promise<void> {
  setzeToken(daten.token);
  await lesezugang();
  sitzung.konto = daten.konto;
  sitzung.angemeldet = true;
}

export async function anmelden(kennung: string, passwort: string): Promise<void> {
  await angemeldet(await hole("/anmeldung", { method: "POST", ...json({ kennung, passwort }) }));
}

export async function koppeln(code: string, name: string, art: "webapp" | "browser"): Promise<void> {
  await angemeldet(await hole("/anmeldung/koppeln", { method: "POST", ...json({ code, name, art }) }));
}

export async function einrichtenMit(kellerwolke_adresse: string, kellerwolke_schluessel: string): Promise<void> {
  sitzung.app = await hole<AppInfo>("/einrichtung", { method: "POST", ...json({ kellerwolke_adresse, kellerwolke_schluessel }) });
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
