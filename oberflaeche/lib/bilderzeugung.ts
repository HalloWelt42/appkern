// Bilderzeugung mit den Fähigkeiten je Modell (IMG-6): was ein Bildmodell kann, steht in seinem Bild-Steckbrief bei der
// Leitstelle (Formate, Schritte, Varianten, Bildvorlagen, Lizenzhinweis); hier wird daraus die Wahl, die das Modell
// annimmt, und die Zeitabschätzung. Die Schätzung lernt aus eigenen Läufen (Mittel je Megapixel und Schritt, die eine App
// wie der ImageVault mitliefert); ohne Messung gibt es keine Zahl. Nichts davon ist je Modell fest verdrahtet.

export interface BildGroessen {
  raster: number;
  kante_min: number | null;
  kante_max: number | null;
  pixel_min: number | null;
  pixel_max: number | null;
  vorgabe: string;
  empfohlen: string[];
}

export interface BildSchritte { vorgabe: number | null; kleinste: number; groesste: number | null }

/** Eigene Messungen je Modell: Mittel der letzten Läufe in Millisekunden je Bild, Megapixel und Schritt (ohne bekannte
 *  Schritte je Bild und Megapixel); `laeufe` ist die Grundlage. */
export interface Bildmessung { laeufe: number; ms_je_mp_schritt: number | null; ms_je_mp: number | null }

export interface Bildmodell {
  id: string;                          // Kennung des Dienstes bei der Leitstelle
  name: string;
  zweck: string;
  zustand: string;                     // bereit, startet, aus, schlaeft, nicht_erreichbar
  geladen: boolean;
  kann_bearbeiten: boolean;            // nimmt Bildvorlagen als Stil oder Bezug
  vorlagen_max: number | null;
  lizenz: string;
  lizenz_hinweis: string;              // was die Lizenz für die Nutzung der Bilder heißt
  groessen: BildGroessen | null;       // null: Steckbrief noch nicht gelesen (Dienst lief noch nie)
  schritte: BildSchritte | null;       // null: der Dienst rechnet mit den Schritten seines Ablaufs
  anzahl_max: number;
  ladezeit_s: number | null;           // gemessen von der Leitstelle; null: noch nicht gemessen
  messung: Bildmessung;
  vorgabe: { groesse: string | null; schritte: number | null; anzahl: number | null };   // Vorgaben der App je Modell
}

/** Eine gewählte Stilvorlage: Kennung (etwa im ImageVault), Adresse der Vorschau, Name */
export interface Bildvorlage { id: string; adresse: string; name: string }

export interface Erzeugungswahl { modell: string; groesse: string; schritte: number | null; anzahl: number }
export interface Format { groesse: string; name: string; vorgabe: boolean }

const VERHAELTNISSE: [number, string][] = [[1, "1:1"], [16 / 9, "16:9 quer"], [9 / 16, "9:16 hoch"], [4 / 3, "4:3 quer"], [3 / 4, "3:4 hoch"],
  [3 / 2, "3:2 quer"], [2 / 3, "2:3 hoch"], [21 / 9, "21:9 quer"]];

export function pixel(groesse: string): { b: number; h: number; mp: number } {
  const [b, h] = groesse.split("x").map(Number);
  return { b, h, mp: (b * h) / 1e6 };
}

const ggt = (a: number, b: number): number => (b ? ggt(b, a % b) : a);

/** Name des Seitenverhältnisses ("16:9 quer"), sonst das gekürzte Verhältnis mit Lage ("9:7 quer") */
export function seitenName(groesse: string): string {
  const { b, h } = pixel(groesse);
  const treffer = VERHAELTNISSE.find(([v]) => Math.abs(b / h - v) / v < 0.03);
  if (treffer) return treffer[1];
  const t = ggt(b, h);
  return `${b / t}:${h / t} ${b > h ? "quer" : "hoch"}`;
}

/** Feste Auswahl der Formate: die empfohlenen Größen des Steckbriefs und seine Vorgabe; ohne Steckbrief nur die Vorgabe
 *  der Leitstelle (1024x1024). */
export function formate(m: Bildmodell): Format[] {
  const vorgabe = m.vorgabe.groesse ?? m.groessen?.vorgabe ?? "1024x1024";
  const alle = [...new Set([m.groessen?.vorgabe ?? "1024x1024", ...(m.groessen?.empfohlen ?? [])])];
  // gleiche Verhältnisse nach Größe unterscheiden: das kleinste heißt schlicht, größere "groß" und "sehr groß"
  const zusatz = ["", " groß", " sehr groß"];
  const rang = (g: string) => alle.filter((x) => seitenName(x) === seitenName(g) && pixel(x).mp < pixel(g).mp).length;
  return alle.map((groesse) => ({ groesse, name: seitenName(groesse) + (zusatz[rang(groesse)] ?? ` ${rang(groesse) + 1}`),
                                  vorgabe: groesse === vorgabe }));
}

/** Bereich der Iterationstiefe, oder null, wenn der Dienst mit seinen eigenen Schritten rechnet (oder nur eine Zahl kann) */
export function schrittBereich(m: Bildmodell): { kleinste: number; groesste: number; vorgabe: number } | null {
  const s = m.schritte;
  if (!s || s.groesste === null || s.groesste <= s.kleinste) return null;
  const vorgabe = Math.min(s.groesste, Math.max(s.kleinste, m.vorgabe.schritte ?? s.vorgabe ?? s.kleinste));
  return { kleinste: s.kleinste, groesste: s.groesste, vorgabe };
}

/** Feste Schrittzahl, wenn das Modell nur eine kann (etwa 4), sonst null */
export function festeSchritte(m: Bildmodell): number | null {
  const s = m.schritte;
  return s && s.groesste !== null && s.groesste === s.kleinste ? s.kleinste : null;
}

/** Erste Wahl für ein Modell: die Vorgaben der App, sonst die des Modells */
export function startwahl(m: Bildmodell): Erzeugungswahl {
  return anpassen(m, { modell: m.id, groesse: m.vorgabe.groesse ?? m.groessen?.vorgabe ?? "1024x1024", schritte: null,
                       anzahl: m.vorgabe.anzahl ?? 1 });
}

/** Die Wahl so angepasst, dass das Modell sie annimmt (Format aus der Auswahl, Schritte im Bereich, Varianten bis anzahl_max) */
export function anpassen(m: Bildmodell, wahl: Erzeugungswahl): Erzeugungswahl {
  const liste = formate(m);
  const groesse = liste.some((f) => f.groesse === wahl.groesse) ? wahl.groesse : (liste.find((f) => f.vorgabe) ?? liste[0]).groesse;
  const bereich = schrittBereich(m);
  const schritte = bereich ? Math.min(bereich.groesste, Math.max(bereich.kleinste, wahl.schritte ?? bereich.vorgabe)) : null;
  return { modell: m.id, groesse, schritte, anzahl: Math.min(Math.max(1, wahl.anzahl), Math.max(1, m.anzahl_max)) };
}

export interface Schaetzung { je_bild_s: number | null; laden_s: number | null; gesamt_s: number | null }

/** Zeitabschätzung aus eigenen Messungen; null, wo es keine gibt (nie eine erfundene Zahl) */
export function schaetzung(m: Bildmodell, wahl: Erzeugungswahl): Schaetzung {
  const { mp } = pixel(wahl.groesse);
  const schritte = wahl.schritte ?? festeSchritte(m);
  const je_ms = schritte !== null && m.messung.ms_je_mp_schritt !== null ? m.messung.ms_je_mp_schritt * mp * schritte
    : m.messung.ms_je_mp !== null ? m.messung.ms_je_mp * mp : null;
  const je_bild_s = je_ms === null ? null : je_ms / 1000;
  const laden_s = m.geladen ? 0 : m.ladezeit_s;
  const gesamt_s = je_bild_s === null || laden_s === null ? null : laden_s + je_bild_s * wahl.anzahl;
  return { je_bild_s, laden_s, gesamt_s };
}

export function dauerText(s: number): string {
  const n = s < 90 ? Math.max(1, Math.round(s)) : Math.round(s / 60);
  return s < 90 ? `${n} ${n === 1 ? "Sekunde" : "Sekunden"}` : `${n} ${n === 1 ? "Minute" : "Minuten"}`;
}
