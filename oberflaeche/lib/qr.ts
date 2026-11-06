// Werte aus einem gescannten QR-Code für die Einstellungen (KW-2): der Code trägt ein JSON-Objekt mit Text-Werten,
// etwa der QR eines App-Zugangs der Kellerwolke {"kellerwolke": Adresse, "schluessel": App-Schlüssel}. Jedes Feld mit
// passendem `qr` übernimmt seinen Wert. Liefert null, wenn der Code kein solches Objekt ist.
export function qrWerte(text: string): Record<string, string> | null {
  try {
    const d: unknown = JSON.parse(text);
    if (!d || typeof d !== "object" || Array.isArray(d)) return null;
    const werte = Object.fromEntries(Object.entries(d).filter(([, w]) => typeof w === "string" && w.trim()).map(([k, w]) => [k, (w as string).trim()]));
    return Object.keys(werte).length ? werte : null;
  } catch {
    return null;
  }
}
