// Wertmodell der Regler: Bereich, Schritt, Kurve, Vorgabe, Einheit und Raster an einer Stelle. Die Regler unterscheiden
// sich nur in der Darstellung; was ein Wert ist und wie er als Text erscheint, steht hier. Übernommen aus hifi-regler
// (appkern/instrumente.js, Stand 9a7c0fe vom 09.11.2026, RAD-6).

/** Zahl deutsch mit fester Zahl Nachkommastellen */
export const zahl = (x: number, stellen: number): string =>
  x.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });

const stellenFuer = (schritt: number): number => (schritt >= 1 ? 0 : Math.min(3, Math.round(-Math.log10(schritt))));

export type Einheit = "%" | "dB" | "Hz" | "ms" | "Cent" | "x" | "" | (string & {});
export type Kurve = "lin" | "log";

const EINHEITEN: Record<string, (w: number, s: number) => string> = {
  "%": (w, s) => `${zahl(w, s)} %`,
  dB: (w, s) => `${w > 0 ? "+" : ""}${zahl(w, s)} dB`,
  Hz: (w) => (w >= 1000 ? `${zahl(w / 1000, w >= 10000 ? 1 : 2)} kHz` : `${zahl(w, w < 10 ? 2 : w < 100 ? 1 : 0)} Hz`),
  ms: (w) => (w >= 1000 ? `${zahl(w / 1000, 2)} s` : `${zahl(w, w < 10 ? 1 : 0)} ms`),
  Cent: (w, s) => `${w > 0 ? "+" : ""}${zahl(w, s)} Cent`,
  x: (w, s) => `${zahl(w, s)} ×`,
  "": (w, s) => zahl(w, s),
};

export interface WertOptionen {
  min?: number;
  max?: number;
  schritt?: number;
  kurve?: Kurve;
  einheit?: Einheit;
  /** benannte Stellungen (Drehwahl); dann ist der Wert der Index */
  raster?: string[] | null;
  /** zweipolig: Vorgabe in der Mitte, Füllung ab der Mitte */
  bipolar?: boolean;
  vorgabe?: number;
  wert?: number;
}

export class Wert {
  min: number;
  max: number;
  schritt: number;
  kurve: Kurve;
  einheit: Einheit;
  raster: string[] | null;
  bipolar: boolean;
  vorgabe: number;
  wert: number;

  constructor(o: WertOptionen = {}) {
    this.min = o.min ?? 0;
    this.max = o.max ?? 100;
    this.schritt = o.schritt ?? 1;
    this.kurve = o.kurve ?? "lin";
    this.einheit = o.einheit ?? "";
    this.raster = o.raster ?? null;
    this.bipolar = o.bipolar ?? false;
    if (this.raster) Object.assign(this, { min: 0, max: this.raster.length - 1, schritt: 1 });
    this.vorgabe = o.vorgabe === undefined || Number.isNaN(o.vorgabe) ? (this.bipolar ? (this.min + this.max) / 2 : this.min) : o.vorgabe;
    this.wert = this.klemmen(o.wert === undefined || Number.isNaN(o.wert) ? this.vorgabe : o.wert);
  }

  klemmen(w: number): number {
    w = Math.min(this.max, Math.max(this.min, w));
    if (this.schritt) w = this.min + Math.round((w - this.min) / this.schritt) * this.schritt;
    return +w.toFixed(6);
  }

  zuAnteil(w: number): number {
    if (this.kurve === "log") return Math.log(w / this.min) / Math.log(this.max / this.min);
    return (w - this.min) / (this.max - this.min);
  }

  ausAnteil(a: number): number {
    a = Math.min(1, Math.max(0, a));
    return this.kurve === "log" ? this.min * Math.pow(this.max / this.min, a) : this.min + a * (this.max - this.min);
  }

  get anteil(): number {
    return this.zuAnteil(this.wert);
  }

  get text(): string {
    if (this.raster) return this.raster[this.wert] ?? "";
    const f = EINHEITEN[this.einheit] ?? ((w: number, s: number) => `${zahl(w, s)} ${this.einheit}`);
    return f(this.wert, stellenFuer(this.schritt));
  }

  /** Schritt der Tasten als Anteil: ein Raster, sonst ein Prozent des Bereichs, nie feiner als der Schritt */
  tastenAnteil(fein: boolean): number {
    if (this.raster) return 1 / this.max;
    const minimal = this.kurve === "log" ? 0.001 : this.schritt / (this.max - this.min);
    return Math.max(minimal, fein ? 0.001 : 0.01);
  }

  /** Eingetippten Text lesen: "1,2 k" = 1200, "-3 dB" = -3, bei Rastern auch der Name */
  lesen(text: string): number | null {
    const t = text.trim().toLowerCase();
    if (this.raster) {
      const i = this.raster.findIndex((r) => r.toLowerCase().startsWith(t));
      if (i >= 0) return i;
    }
    const m = t.replace(",", ".").match(/^([+-]?\d*\.?\d+)\s*(k)?/);
    if (!m) return null;
    let w = parseFloat(m[1]) * (m[2] ? 1000 : 1);
    if (this.einheit === "ms" && /\ds\b|\d\s*s$/.test(t) && !t.includes("ms")) w *= 1000;
    return this.raster ? Math.round(w) - 1 : w;
  }
}
