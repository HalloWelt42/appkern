// Dateiwahl und Anfragen der Kellerwolke aus der Oberfläche einer App (Schnittstelle des Gerüsts unter
// /api/v1/kellerwolke). Blättern zeigt nur Namen und Eckdaten; die Wahl stellt eine Anfrage, erst dann darf die App die
// Datei lesen, und nur solange die Anfrage offen ist.
import { hole } from "./api.svelte";
import type { Anfrage, WahlSeite } from "./typen";

export function wahl(ordner: string | null = null): Promise<WahlSeite> {
  return hole<WahlSeite>(`/kellerwolke/wahl${ordner ? `?ordner=${encodeURIComponent(ordner)}` : ""}`);
}

// Gewählt: Anfrage an diese App; bei Aktionen im Hintergrund nennt `auftrag_id` den Auftrag, der sie ausführt.
export function waehlen(knotenId: string, aktion: string): Promise<{ anfrage: Anfrage; auftrag_id: string | null }> {
  return hole(`/kellerwolke/wahl`, { method: "POST", body: JSON.stringify({ knoten_id: knotenId, aktion }) });
}

// Die Kellerwolke hat den Browser mit dieser Anfrage geschickt (Adresse /anfrage/<id>): annehmen.
export function anfrageOeffnen(anfrageId: string): Promise<Anfrage> {
  return hole<Anfrage>(`/kellerwolke/anfragen/${encodeURIComponent(anfrageId)}/oeffnen`, { method: "POST" });
}

// Ton und Video erkennt die Wahl am Inhaltstyp.
export function istMedium(inhaltstyp: string | null): boolean {
  return !!inhaltstyp && (inhaltstyp.startsWith("audio/") || inhaltstyp.startsWith("video/"));
}
