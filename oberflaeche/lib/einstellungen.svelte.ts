// Einstellungen der App als Entwurf für Apps mit eigener Schale (Leitstand): die Wahrheit bleibt GET /einstellungen,
// geänderte Werte stehen im Entwurf, bis sie gespeichert werden. Die Zeile je Einstellung zeichnet
// teile/EinstellungsZeile.svelte; Seite, Gruppen und die Leiste zum Speichern baut die App (wie Fundus und Pinnwand).
import { hole, json } from "./api.svelte";
import type { Angebot, Feld } from "./typen";

export const einstellungen = $state<{ felder: Feld[]; entwurf: Record<string, unknown>; laedt: boolean }>({
  felder: [], entwurf: {}, laedt: false,
});

export const einstellungsFeld = (name: string): Feld | undefined => einstellungen.felder.find((f) => f.name === name);

/** Der Wert, wie er nach dem Speichern gälte: aus dem Entwurf, sonst der gespeicherte */
export const einstellungsWert = (name: string): unknown =>
  name in einstellungen.entwurf ? einstellungen.entwurf[name] : einstellungsFeld(name)?.wert;

/** Liest die Einstellungen neu; wirft, wenn die App nicht antwortet */
export async function einstellungenLaden(): Promise<void> {
  einstellungen.laedt = true;
  try {
    einstellungen.felder = await hole<Feld[]>("/einstellungen");
  } finally {
    einstellungen.laedt = false;
  }
}

/** Trägt einen Wert in den Entwurf ein; derselbe Wert wie gespeichert nimmt ihn wieder heraus */
export function einstellungSetzen(name: string, wert: unknown): void {
  const neu = { ...einstellungen.entwurf };
  if (JSON.stringify(wert) === JSON.stringify(einstellungsFeld(name)?.wert) && einstellungsFeld(name)?.art !== "geheimnis") delete neu[name];
  else neu[name] = wert;
  einstellungen.entwurf = neu;
}

/** Speichert den Entwurf und gibt zurück, wie viele Werte es waren; wirft mit dem Grund der App */
export async function einstellungenSpeichern(): Promise<number> {
  const n = Object.keys(einstellungen.entwurf).length;
  einstellungen.felder = await hole<Feld[]>("/einstellungen", { method: "PATCH", ...json({ werte: einstellungen.entwurf }) });
  einstellungen.entwurf = {};
  return n;
}

export function einstellungenVerwerfen(): void {
  einstellungen.entwurf = {};
}

/** Was für ein Feld zur Wahl steht und was gerade gilt */
export const einstellungsAngebot = (name: string): Promise<Angebot> => hole<Angebot>(`/einstellungen/angebot/${name}`);

/** Deckt ein Geheimnis auf (verdeckt ist es nur in der Anzeige) */
export const einstellungsGeheimnis = async (name: string): Promise<string> =>
  (await hole<{ name: string; wert: string }>(`/einstellungen/geheimnis/${name}`)).wert;
