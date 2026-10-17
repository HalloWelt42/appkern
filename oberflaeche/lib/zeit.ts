// Zeiten, Größen, Sprachen und Sprecherfarben zum Lesen (gleich in allen Apps).

// Zeitmarke: "04:12", ab einer Stunde "1:02:05".
export function marke(sekunden: number): string {
  const s = Math.max(0, Math.floor(sekunden));
  const h = Math.floor(s / 3600);
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const r = String(s % 60).padStart(2, "0");
  return h ? `${h}:${m}:${r}` : `${m}:${r}`;
}

// Zeitmarke mit Zehnteln zum Bearbeiten: "4:12,5".
export function genau(sekunden: number): string {
  return `${marke(sekunden)},${Math.floor((sekunden % 1) * 10)}`;
}

// "4:12,5", "1:02:05" oder "252,5" zurück in Sekunden; null, wenn es nicht passt.
export function lesen(text: string): number | null {
  const teile = text.trim().replace(",", ".").split(":");
  if (!teile.length || teile.some((t) => t === "" || Number.isNaN(Number(t)))) return null;
  return teile.reduce((summe, t) => summe * 60 + Number(t), 0);
}

export function groesse(bytes: number | null): string {
  if (bytes == null) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${Math.round(bytes / 1024 ** 2)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1).replace(".", ",")} GB`;
}

export const SPRACHEN: Record<string, string> = {
  de: "Deutsch",
  en: "Englisch",
  fr: "Französisch",
  es: "Spanisch",
  it: "Italienisch",
  nl: "Niederländisch",
  auto: "Erkennen",
};

export function sprache(code: string): string {
  return SPRACHEN[code] ?? code.toUpperCase();
}

// Sprecherfarbe nach Kennung (s1, s2 ...), gleich in Wellenform, Text und Leiste.
export function farbe(kennung: string | null | undefined): string {
  const n = Number((kennung ?? "").replace(/\D/g, "")) || 0;
  return n ? `var(--s${((n - 1) % 6) + 1})` : "var(--rand)";
}
