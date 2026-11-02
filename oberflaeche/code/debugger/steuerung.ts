/*
 * Steuerung des Debuggers auf einer Aufzeichnung: wohin ein Knopf springt. Der Lauf ist schon fertig, darum geht
 * alles auch rückwärts. Ein Schritt ist eine ausgeführte Zeile mit dem Speicher danach; seine Tiefe ist die Zahl der
 * Aufrufrahmen (Hauptprogramm 1, darin eine Funktion 2, ...).
 *
 * Haltepunkt: Ein Aufruf zeichnet seine Zeile zweimal auf, beim Eintritt in die Funktion und nach der Rückkehr. Der
 * Debugger hält nur beim ersten Mal, sonst bliebe er an jeder Zeile mit Aufruf doppelt stehen.
 */
import type { Schritt } from "../aufzeichnung";

export type Ziel = "anfang" | "zurueckHalt" | "zurueck" | "hinein" | "ueber" | "hinaus" | "weiterHalt" | "ende";

export const tiefe = (s: Schritt): number => s.rahmen.length;

/** Rückkehr aus einem Aufruf: die Zeile lief schon, als der Aufruf begann. */
export function istRueckkehr(schritte: readonly Schritt[], k: number): boolean {
  return k > 0 && tiefe(schritte[k]) < tiefe(schritte[k - 1]);
}

/** Eintritt in eine Funktion: der Schritt trägt noch die Zeile des Aufrufs, die Funktion hat noch nichts ausgeführt. */
export function istEintritt(schritte: readonly Schritt[], k: number): boolean {
  return k > 0 && tiefe(schritte[k]) > tiefe(schritte[k - 1]);
}

export function istHalt(schritte: readonly Schritt[], k: number, haltepunkte: ReadonlySet<number>): boolean {
  return haltepunkte.has(schritte[k].zeile) && !istRueckkehr(schritte, k);
}

/** Nächster passender Schritt in einer Richtung; ohne Treffer der letzte (vorwärts) oder erste (rückwärts). */
function suche(schritte: readonly Schritt[], von: number, richtung: 1 | -1, passt: (k: number) => boolean): number {
  for (let k = von + richtung; k >= 0 && k < schritte.length; k += richtung) if (passt(k)) return k;
  return richtung > 0 ? schritte.length - 1 : 0;
}

/** Schritt, auf den ein Knopf von Schritt `i` aus springt. */
export function springe(ziel: Ziel, schritte: readonly Schritt[], i: number, haltepunkte: ReadonlySet<number>): number {
  const letzter = schritte.length - 1;
  const halt = (k: number) => istHalt(schritte, k, haltepunkte);
  switch (ziel) {
    case "anfang": return 0;
    case "ende": return letzter;
    case "zurueck": return Math.max(0, i - 1);
    case "hinein": return Math.min(letzter, i + 1);
    // über Aufrufe hinweg: der nächste Schritt, der nicht tiefer liegt
    case "ueber": return suche(schritte, i, 1, (k) => tiefe(schritte[k]) <= tiefe(schritte[i]));
    // bis die Funktion zurückgekehrt ist
    case "hinaus": return suche(schritte, i, 1, (k) => tiefe(schritte[k]) < tiefe(schritte[i]));
    case "weiterHalt": return suche(schritte, i, 1, halt);
    case "zurueckHalt": return suche(schritte, i, -1, halt);
  }
}

/** Erster Halt eines neuen Laufs: der erste Haltepunkt, ohne Haltepunkte die erste Zeile; wird keiner erreicht, das Ende. */
export function start(schritte: readonly Schritt[], haltepunkte: ReadonlySet<number>): number {
  if (haltepunkte.size === 0) return 0;
  const k = schritte.findIndex((_, n) => istHalt(schritte, n, haltepunkte));
  return k >= 0 ? k : schritte.length - 1;
}

export interface Stapeleintrag {
  name: string;
  /** innerster Rahmen: die gerade ausgeführte Zeile; sonst die Zeile, in der der Rahmen auf seinen Aufruf wartet;
   * null bei einer gerade aufgerufenen Funktion und beim Hauptprogramm hinter einem angehängten Aufruf */
  zeile: number | null;
}

/**
 * Aufrufstapel bei Schritt `k`, innerster Rahmen zuerst. Die Zeile eines wartenden Rahmens steht im Schritt, mit dem
 * der Aufruf darüber begann (dort ist die Tiefe zuletzt über ihn hinausgegangen). Bei Funktionsaufgaben ruft eine
 * angehängte, unsichtbare Zeile die Funktion auf; dort bleibt die Zeile des Hauptprogramms offen (`angehaengt`).
 */
export function aufrufstapel(schritte: readonly Schritt[], k: number, angehaengt: boolean): Stapeleintrag[] {
  const s = schritte[k];
  const stapel: Stapeleintrag[] = [{ name: s.rahmen[s.rahmen.length - 1].name, zeile: istEintritt(schritte, k) ? null : s.zeile }];
  let j = k;
  for (let ebene = s.rahmen.length - 1; ebene >= 1; ebene--) {
    while (j > 0 && tiefe(schritte[j - 1]) > ebene) j--;
    const sichtbar = !(angehaengt && ebene === 1) && (j > 0 || tiefe(schritte[0]) <= ebene);
    stapel.push({ name: s.rahmen[ebene - 1].name, zeile: sichtbar ? schritte[j].zeile : null });
  }
  return stapel;
}
