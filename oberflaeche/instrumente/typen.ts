// Typen der Instrumente für TypeScript und Svelte: Merkmale je Element (im Markup einer Svelte-Komponente geprüft),
// Elementklassen für document.querySelector und das Ereignis "ak-eingabe" am Dokument. Wird mit
// "appkern-oberflaeche/instrumente" geladen; die App braucht dafür keine eigene Angabe.
import type { HTMLAttributes } from "svelte/elements";
import type { EingabeMeldung } from "./bedienen";
import type { Pegel, Schirm, Segmente, Zeiger } from "./anzeigen";
import type { Drehregler, Kippschalter, Leuchte, Schieber, Taster, Wahl } from "./regler";

/** Leuchtfarben (Marken --led-*), in beiden Themen gleich */
export type Leuchtfarbe = "rot" | "gruen" | "bernstein" | "gelb" | "blau" | "weiss" | "tuerkis" | "violett" | "cyan";
type Zahl = number | `${number}`;
type Schalter = boolean | "";

/** Merkmale, die alle Regler mit Wert teilen (Drehregler, Drehwahl, Schieber) */
export interface ReglerMerkmale<T extends EventTarget> extends HTMLAttributes<T> {
  /** Beschriftung: der übliche Fachbegriff */
  name?: string;
  /** Erklärung im Hover und für Vorleser */
  hilfe?: string;
  min?: Zahl;
  max?: Zahl;
  schritt?: Zahl;
  /** Startwert; zur Laufzeit als Eigenschaft (wert) setzen */
  wert?: Zahl;
  vorgabe?: Zahl;
  kurve?: "lin" | "log";
  einheit?: "%" | "dB" | "Hz" | "ms" | "Cent" | "x" | (string & {});
  /** benannte Stellungen, getrennt mit "|" (Drehwahl, Wahlschieber) */
  raster?: string;
  bipolar?: Schalter;
  gesperrt?: Schalter;
  /** Grenzwörter an den Enden, getrennt mit "|" */
  grenzen?: string;
  /** Leuchtfarbe des Wertbogens */
  leuchte?: Leuchtfarbe;
  /** Regler gewählt (etwa im Inspektor): Lichtkegel wie beim Fokus */
  gewaehlt?: Schalter;
}

export interface DrehMerkmale extends ReglerMerkmale<Drehregler> {
  kappe?: "alu" | "lack" | "schwarz" | "ring";
  /** Lackfarbe der Kappe (CSS-Farbe oder Marke) */
  farbe?: string;
  /** Leuchtfarbe des Zeigerstrichs (schwarze Kappe) */
  zeiger?: Leuchtfarbe;
  /** Breite des Modulationsbogens (Anteil 0 bis 1) */
  mod?: Zahl;
}

export interface SchieberMerkmale extends ReglerMerkmale<Schieber> {
  art?: "fader" | "leuchte" | "balken";
  richtung?: "waagrecht" | "senkrecht";
  segmente?: Zahl;
}

export interface TasterMerkmale extends HTMLAttributes<Taster> {
  art?: "flach" | "pille" | "glas" | "fuss";
  modus?: "rasten" | "tasten" | "tippen";
  /** Font-Awesome-Klasse des Symbols, etwa fa-play */
  symbol?: string;
  beschriftung?: string;
  /** Wort unter der Taste */
  text?: string;
  hilfe?: string;
  farbe?: Leuchtfarbe;
  /** Tastenlicht: Leuchte als Lichtschlitz in der oberen Tastenkante (Taste bleibt gleich hoch) */
  licht?: Leuchtfarbe;
  /** Leuchte über der Taste */
  led?: Leuchtfarbe;
  /** eingeschaltet; zur Laufzeit als Eigenschaft (an) setzen */
  an?: boolean;
  gewaehlt?: Schalter;
  ontempo?: (e: CustomEvent<{ tempo: number }>) => void;
}

export interface KippMerkmale extends HTMLAttributes<Kippschalter> {
  /** Namen der Stellungen oben|unten oder oben|mitte|unten */
  beschriftung?: string;
  name?: string;
  hilfe?: string;
  stellung?: "oben" | "mitte" | "unten";
  gewaehlt?: Schalter;
}

export interface WahlMerkmale extends HTMLAttributes<Wahl> {
  art?: "tasten" | "schiebe";
  /** Optionen, getrennt mit "|" */
  optionen?: string;
  name?: string;
  hilfe?: string;
  farbe?: Leuchtfarbe;
  /** gewählte Option; zur Laufzeit als Eigenschaft (wert) setzen */
  wert?: string;
  gewaehlt?: Schalter;
}

export interface LeuchteMerkmale extends HTMLAttributes<Leuchte> {
  farbe?: Leuchtfarbe;
  zustand?: "an" | "aus" | "blinkt" | "atmet" | "flackert";
  groesse?: "klein" | "mittel" | "gross";
  /** schlitz: Tastenlicht in der oberen Kante einer Taste (Leuchte als erstes Kind der Taste) */
  art?: "schlitz";
  text?: string;
  hilfe?: string;
}

export interface SegmenteMerkmale extends HTMLAttributes<Segmente> {
  art?: "7" | "14" | "punkt";
  stellen?: Zahl;
  text?: string;
  /** Lauftext: Millisekunden je Zeichen, wenn der Text länger ist als die Stellen */
  lauf?: Zahl;
  farbe?: Leuchtfarbe;
  hilfe?: string;
}

export interface ZeigerMerkmale extends HTMLAttributes<Zeiger> {
  art?: "vu" | "stimmen";
  kanal?: "links" | "rechts";
  /** Wert in dB (VU) oder Cent (Stimmgerät); ohne Wert das Beispielsignal */
  wert?: Zahl;
  beschriftung?: string;
  spitze?: Schalter;
  hilfe?: string;
}

export interface PegelMerkmale extends HTMLAttributes<Pegel> {
  art?: "kette" | "balken" | "gr";
  kanaele?: Zahl;
  richtung?: "waagrecht" | "senkrecht";
  segmente?: Zahl;
  von?: Zahl;
  bis?: Zahl;
  /** Pegel in dB; ohne Wert das Beispielsignal */
  wert?: Zahl;
  /** Beschriftung der Skala, getrennt mit "|" */
  skala?: string;
  beschriftung?: string;
  farbe?: Leuchtfarbe;
  hilfe?: string;
}

export interface SchirmMerkmale extends HTMLAttributes<Schirm> {
  art?: "welle" | "lfo" | "spektrum" | "linie" | "huelle" | "take";
  verhaeltnis?: string;
  fuss?: string;
  beschriftung?: string;
  farbe?: Leuchtfarbe;
  /** LFO: Selektor des Reglers für Tempo und Tiefe */
  tempo?: string;
  tiefe?: string;
  hilfe?: string;
}

declare global {
  interface HTMLElementTagNameMap {
    "ak-dreh": Drehregler;
    "ak-schieber": Schieber;
    "ak-taster": Taster;
    "ak-kipp": Kippschalter;
    "ak-wahl": Wahl;
    "ak-led": Leuchte;
    "ak-segmente": Segmente;
    "ak-zeiger": Zeiger;
    "ak-pegel": Pegel;
    "ak-schirm": Schirm;
  }
  interface DocumentEventMap {
    "ak-eingabe": CustomEvent<EingabeMeldung>;
  }
}

declare module "svelte/elements" {
  export interface SvelteHTMLElements {
    "ak-dreh": DrehMerkmale;
    "ak-schieber": SchieberMerkmale;
    "ak-taster": TasterMerkmale;
    "ak-kipp": KippMerkmale;
    "ak-wahl": WahlMerkmale;
    "ak-led": LeuchteMerkmale;
    "ak-segmente": SegmenteMerkmale;
    "ak-zeiger": ZeigerMerkmale;
    "ak-pegel": PegelMerkmale;
    "ak-schirm": SchirmMerkmale;
  }
}
