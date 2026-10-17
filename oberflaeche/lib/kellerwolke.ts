// Dateiwahl und Anfragen der Kellerwolke aus der Oberfläche einer App (Schnittstelle des Gerüsts unter
// /api/v1/kellerwolke). Blättern zeigt nur Namen und Eckdaten; die Wahl stellt eine Anfrage, erst dann darf die App die
// Datei lesen, und nur solange die Anfrage offen ist.
import { hole } from "./api.svelte";
import { gehe } from "./navigation.svelte";
import { sitzung } from "./sitzung.svelte";
import type { Anfrage, WahlSeite } from "./typen";

export function wahl(ordner: string | null = null): Promise<WahlSeite> {
  return hole<WahlSeite>(`/kellerwolke/wahl${ordner ? `?ordner=${encodeURIComponent(ordner)}` : ""}`);
}

// Gewählt: Anfrage an diese App; bei Aktionen im Hintergrund nennt `auftrag_id` den Auftrag, der sie ausführt.
export function waehlen(knotenId: string, aktion: string): Promise<{ anfrage: Anfrage; auftrag_id: string | null }> {
  return hole(`/kellerwolke/wahl`, { method: "POST", body: JSON.stringify({ knoten_id: knotenId, aktion }) });
}

// Stand einer Anfrage (etwa die Frist einer aus der Kellerwolke geöffneten Datei).
export function anfrage(anfrageId: string): Promise<Anfrage> {
  return hole<Anfrage>(`/kellerwolke/anfragen/${encodeURIComponent(anfrageId)}`);
}

// Die Kellerwolke hat den Browser mit dieser Anfrage geschickt (Adresse /anfrage/<id>): annehmen.
export function anfrageOeffnen(anfrageId: string): Promise<Anfrage> {
  return hole<Anfrage>(`/kellerwolke/anfragen/${encodeURIComponent(anfrageId)}/oeffnen`, { method: "POST" });
}

// Ton und Video erkennt die Wahl am Inhaltstyp.
export function istMedium(inhaltstyp: string | null): boolean {
  return !!inhaltstyp && (inhaltstyp.startsWith("audio/") || inhaltstyp.startsWith("video/"));
}

// Symbol einer Zeile der Dateiwahl nach Art und Inhaltstyp.
export function dateiSymbol(typ: "ordner" | "datei", inhaltstyp: string | null): string {
  const t = inhaltstyp ?? "";
  if (typ === "ordner") return "fa-folder";
  if (t.startsWith("video/")) return "fa-file-video";
  if (t.startsWith("audio/")) return "fa-file-audio";
  if (t.startsWith("image/")) return "fa-file-image";
  return t.startsWith("text/") ? "fa-file-lines" : "fa-file";
}

// --- Herkunft: Dateien aus der Kellerwolke (einzige Stelle für Adressen dorthin) ------------------------------------

// Die Datei in der Kellerwolke: ihr Ordner, die Datei darin gezeigt; leer, solange die App die Adresse nicht kennt.
export function inKellerwolke(pfad: string): string {
  const kw = sitzung.app?.kellerwolke;
  return kw ? `${kw}/dateien/${pfad.split("/").filter(Boolean).map(encodeURIComponent).join("/")}` : "";
}

// Zurück, woher die Datei kam: aus der Dateiwahl der App oder aus der Kellerwolke im selben Fenster über den Verlauf;
// in einem eigenen Fenster in die Kellerwolke zu der Datei; ohne Adresse an den Ort `sonst` der App.
export function zurueckZurKellerwolke(pfad: string, sonst: string): void {
  const ziel = inKellerwolke(pfad);
  if (history.length > 1) history.back();
  else if (ziel) location.assign(ziel);
  else gehe(sonst);
}

// Rollen der Begleitdateien zum Lesen, in dieser Reihenfolge ("Transkript und Untertitel daneben"); unbekannte zählen
// nicht. Die Rollen der eigenen Apps stehen hier, damit jede App sie gleich benennt.
export const ROLLEN: Record<string, string> = {
  transkript: "Transkript", text: "Text", markdown: "Markdown", untertitel: "Untertitel", untertitel_vtt: "Untertitel",
  daten: "Daten", dokument: "Dokument", protokoll: "Protokoll", zusammenfassung: "Zusammenfassung", aufgaben: "Aufgaben",
  sprache: "Sprachausgabe", vertonung: "Vertonungsplan", quelltext: "Quelltext", stimme: "Stimmangaben", quelle: "Originalaufnahme",
};

export function daneben(rollen: (string | null)[]): string {
  const da = new Set(rollen);
  const namen = [...new Set(Object.keys(ROLLEN).filter((r) => da.has(r)).map((r) => ROLLEN[r]))];
  if (!namen.length) return "";
  return `${namen.length > 1 ? `${namen.slice(0, -1).join(", ")} und ${namen.at(-1)}` : namen[0]} daneben`;
}
