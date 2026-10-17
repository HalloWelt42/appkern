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
  oberflaeche: string | null;
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
  einheit: string;
  angebot: boolean;
  wert: unknown;
  gesetzt: boolean;
  vorgabe: unknown;
  herkunft: "gespeichert" | "umgebung" | "vorgabe";
  gruppe: string | null;
}

export interface Option {
  wert: string;
  titel: string;
  hinweis: string;
}

export interface Angebot {
  optionen: Option[];
  eigener_wert: boolean;
  stand: string;
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

// --- Kellerwolke: Dateiwahl und Anfragen (Gerüst mit Angeboten, Kellerwolke ab 0.81) -----------------------------

export interface WahlEintrag {
  id: string;
  name: string;
  typ: "ordner" | "datei";
  groesse: number | null;
  inhaltstyp: string | null;
  geaendert_am: string;
  kinder_anzahl: number | null;
  haupt_id: string | null; // ein Begleiter: seine Hauptdatei
  rolle: string | null;
  begleiter_anzahl: number;
}

export interface WahlSeite {
  kette: { id: string | null; name: string }[]; // vom Konto bis zum gezeigten Ordner
  eintraege: WahlEintrag[];
}

export type AnfrageZustand = "wartet" | "laeuft" | "fertig" | "fehler" | "abgebrochen";

// Eine Anfrage der Kellerwolke an diese App: Aktion auf einer Datei; solange sie offen ist, darf die App genau diese
// Datei lesen und ihre Begleiter schreiben.
export interface Anfrage {
  id: string;
  app: string;
  aktion: string;
  titel: string;
  art: "hintergrund" | "oeffnen";
  knoten_id: string;
  knoten_name: string;
  von: string;
  zustand: AnfrageZustand;
  fortschritt: number | null;
  meldung: string | null;
  ergebnis_id: string | null;
  ergebnis_name: string | null;
  erstellt_am: string;
  gueltig_bis: string;
}
