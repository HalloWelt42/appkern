// Was die Schnittstellen des Appkerns liefern (Spiegel der Pydantic-Modelle) und was eine App der Schale gibt.
import type { Component } from "svelte";

export interface AppInfo {
  name: string;
  kennung: string;
  rolle: string;
  symbol: string;
  fassung: string;
  appkern: string;
  einrichtung_noetig: boolean;
  besitzer: string | null;
  kellerwolke: string;
}

export interface Konto {
  id: string;
  name: string;
  kuerzel: string | null;
  rolle: string;
  geraet: boolean;
}

export interface Verbindung {
  name: string;
  ok: boolean;
  adresse: string;
  meldung: string;
}

export type Zustand = "wartet" | "laeuft" | "fertig" | "fehler" | "abgebrochen" | "unterbrochen";

export interface Phase {
  schluessel: string;
  titel: string;
  symbol: string;
}

export interface Auftrag {
  id: string;
  art: string;
  titel: string;
  zustand: Zustand;
  eingabe: Record<string, unknown>;
  ergebnis: Record<string, unknown> | null;
  fehler: string | null;
  fortschritt: number | null;
  schritt: string;
  phase: string | null;
  phasen: Phase[];
  abbruch_gewuenscht: boolean;
  fortsetzbar: boolean;
  stapel: string | null;
  wiederholung_von: string | null;
  erstellt_am: string;
  begonnen_am: string | null;
  beendet_am: string | null;
}

export interface Seite<T> {
  eintraege: T[];
  gesamt: number;
}

export type FeldArt = "text" | "zahl" | "schalter" | "auswahl" | "geheimnis" | "liste" | "wert";

export interface Feld {
  name: string;
  titel: string;
  beschreibung: string;
  art: FeldArt;
  optionen: string[];
  beschriftungen: Record<string, string>;
  schritt: number | null;
  kleinste: number | null;
  groesste: number | null;
  wert: unknown;
  gesetzt: boolean;
  vorgabe: unknown;
  herkunft: "gespeichert" | "umgebung" | "vorgabe";
  gruppe: string | null;
}

export type Stufe = "info" | "warnung" | "fehler";

export interface ProtokollEintrag {
  id: string;
  zeit: string;
  ereignis: string;
  stufe: Stufe;
  bezug_art: string | null;
  bezug_id: string | null;
  bezug_name: string | null;
  text: string;
  daten: Record<string, unknown> | null;
}

// Ein Bereich der App: eigene Seite in der Navigation (am Telefon als Reiter, wenn `reiter` gesetzt ist).
export interface Bereich {
  schluessel: string;
  titel: string;
  symbol: string;
  seite: Component;
  reiter?: boolean;
}
