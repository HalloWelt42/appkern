/*
 * Aufzeichnung eines Laufs: je ausgeführter Zeile des eigenen Codes der Speicher danach. Speicherbild und Debugger
 * zeigen sie; die Wahrheit dieser Typen ist die Aufzeichnung in der Sandbox der Codeschmiede
 * (backend/src/codeschmiede/aufzeichnung/), die auch andere Apps über ihre Schnittstelle bekommen.
 * Leere Felder können fehlen: der Debugger lässt sie weg, damit lange Aufzeichnungen klein bleiben.
 */

/** Ein Wert im Speicherbild; gleiche `kennung` heißt: dasselbe Objekt (Pfeil). */
export interface Wert {
  art: "zahl" | "text" | "wahrheit" | "nichts" | "liste" | "tupel" | "menge" | "woerterbuch" | "funktion" | "klasse" | "objekt" | "sonst";
  darstellung: string;
  kennung?: number | null;
  elemente?: Wert[] | null;
  paare?: [Wert, Wert][] | null;
  attribute?: Record<string, Wert> | null;
  gekuerzt?: boolean;
}

export interface Rahmen {
  name: string;
  variablen: Record<string, Wert>;
}

export interface Schritt {
  zeile: number;
  rahmen: Rahmen[];
  ausgabe: string;
  rueckgabe?: Wert | null;
}

export interface Aufzeichnung {
  art: "python" | "javascript";
  schritte: Schritt[];
  ausgabe: string;
  fehler?: string | null;
  fehlerzeile?: number | null;
  gekuerzt: boolean;
  zeitueberschreitung: boolean;
  laufzeit_ms: number;
}

/** Lauf im Debugger einer Aufgabe; bei Funktionsaufgaben mit der Rückgabe des Aufrufs. */
export interface Debuglauf extends Aufzeichnung {
  rueckgabe?: Wert | null;
}
