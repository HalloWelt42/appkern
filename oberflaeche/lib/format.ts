// Zeiten und Mengen in Worten.
const MINUTE = 60_000;

function tag(d: Date): string {
  return d.toLocaleDateString("de-DE", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function uhr(d: Date): string {
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

// "heute 14:16", "gestern 21:52", "12.10.2026 08:03"
export function wann(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const heute = new Date();
  const gestern = new Date(heute.getTime() - 24 * 3600 * 1000);
  if (tag(d) === tag(heute)) return `heute ${uhr(d)}`;
  if (tag(d) === tag(gestern)) return `gestern ${uhr(d)}`;
  return `${tag(d)} ${uhr(d)}`;
}

// "seit 6 Min", "seit 2 Std 5 Min"
export function seit(iso: string | null): string {
  if (!iso) return "";
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / MINUTE));
  if (min < 1) return "gerade begonnen";
  if (min < 60) return `seit ${min} Min`;
  return `seit ${Math.floor(min / 60)} Std ${min % 60} Min`;
}

// Dauer zwischen zwei Zeitpunkten: "4 Min 12 s"
export function dauer(von: string | null, bis: string | null): string {
  if (!von || !bis) return "";
  const s = Math.max(0, Math.round((new Date(bis).getTime() - new Date(von).getTime()) / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} Min ${s % 60} s`;
  return `${Math.floor(s / 3600)} Std ${Math.floor((s % 3600) / 60)} Min`;
}

export function isoTag(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// "17.10.2026" zu "2026-10-17"; leer bei ungültiger Eingabe
export function tagAusText(text: string): string {
  const t = text.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!t) return "";
  const d = new Date(Number(t[3]), Number(t[2]) - 1, Number(t[1]));
  return d.getDate() === Number(t[1]) ? isoTag(d) : "";
}
