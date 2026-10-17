// Lesbare Namen der Ereignisse im Protokoll (der Schlüssel erscheint nie in der Oberfläche). Die Schale kennt ihre
// eigenen; eine App meldet ihre mit `ereignisseBenennen` an. Unbekannte werden aus dem Schlüssel gebildet.
const NAMEN: Record<string, string> = {
  "auftrag.fertig": "Auftrag fertig",
  "auftrag.fehler": "Auftrag gescheitert",
  "auftrag.abgebrochen": "Auftrag abgebrochen",
  "auftrag.unterbrochen": "Auftrag unterbrochen",
  "anmeldung.angemeldet": "Angemeldet",
  "anmeldung.gekoppelt": "Gerät gekoppelt",
  "anmeldung.abgewiesen": "Anmeldung abgewiesen",
  "anmeldung.abgemeldet": "Abgemeldet",
  "einstellung.geaendert": "Einstellungen geändert",
  "app.eingerichtet": "App eingerichtet",
  "app.oberflaeche_veraltet": "Oberfläche nicht neu gebaut",
};

export function ereignisseBenennen(namen: Record<string, string>): void {
  Object.assign(NAMEN, namen);
}

export function ereignisName(schluessel: string): string {
  if (NAMEN[schluessel]) return NAMEN[schluessel];
  const text = schluessel.replace(/[._]+/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
