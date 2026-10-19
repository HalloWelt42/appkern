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
  auftraege_laufend?: number;
  // solange die erste Einrichtung nötig ist: wo der Einrichtungscode am Rechner der App liegt (nie der Code selbst)
  einrichtungscode?: string | null;
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
  von: string;                    // wer oder was ihn angestoßen hat (Konto, App, Zeitplan); leer: unbekannt
  zurueckgestellt: string;        // wartend, aber von der App zurückgehalten, mit Grund
  erstellt_am: string;
  begonnen_am: string | null;
  beendet_am: string | null;
}

export interface Seite<T> {
  eintraege: T[];
  gesamt: number;
}

// Wie viele Aufträge in jedem Zustand sind (`/auftraege/zahlen`).
export type Zahlen = Record<Zustand, number>;

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
  geraete?: "beide" | "rechner" | "telefon";   // wo der Bereich erscheint (Vorgabe: beide)
}

// Ein eigener Reiter der App in den Einstellungen, neben den aus der Beschreibung erzeugten Gruppen: für Einstellungen,
// die eine eigene Verwaltung brauchen (etwa Zugänge mit Schlüsseln je Gerät). Die Seite steht im Rollfeld des Reiters.
export interface EinstellungsReiter {
  schluessel: string;   // Adresse des Reiters (/einstellungen/<schluessel>), ASCII
  titel: string;
  seite: Component;
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

// Wozu eine App Dateien der Kellerwolke wählen lässt (Baustein Dateiwahl): welche Dateien gehen, woran ein laufender
// Auftrag und ein fertiges Ergebnis zu erkennen sind, die Wörter der Oberfläche und das Starten.
export interface WahlZweck {
  auftrag: string;                         // Art der Aufträge, die eine gewählte Datei bearbeiten
  quelle: (a: Auftrag) => string;          // welche Datei (Knoten) ein solcher Auftrag bearbeitet
  ergebnis: string[];                      // Rollen der Begleiter, die das Ergebnis halten: dann "fertig", Zeile öffnet
  waehlbar?: (e: WahlEintrag, begleiter: WahlEintrag[]) => boolean;  // Vorgabe: Ton und Video
  einzeln?: boolean;                       // nur eine Datei auf einmal (die neue Wahl ersetzt die vorige)
  ordnerAdresse: (ordnerId: string) => string;   // Ort der App für einen Unterordner
  woerter: WahlWoerter;
  starten: (ids: string[]) => Promise<string>;   // stellt die Aufträge; zurück kommt die Meldung danach
}

export interface WahlWoerter {
  tun: string;           // Knopf zum Starten ("Transkribieren")
  symbol: string;        // Symbol der Optionsleiste
  fertig: string;        // Stand mit Ergebnis ("transkribiert")
  offen: string;         // Stand ohne Ergebnis ("ohne Transkript")
  gruppe: string;        // Überschrift der wählbaren Dateien am Telefon ("Ton und Video")
  leer: string;          // keine wählbare Datei im Ordner (Telefon)
  andere: string;        // Kennzeichen nicht wählbarer Dateien in ihrer Zeile ("kein Ton")
  nichtWaehlbar: string; // Erklärung an nicht wählbaren Dateien
  hinweis: string;       // Band oben am Rechner: was die App sieht und darf
  hinweisKurz: string;   // dasselbe am Telefon
  anleitung: string;     // unter der Liste, solange etwas wählbar ist
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
