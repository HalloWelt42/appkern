// Regler des Appkerns: Drehregler, Schieber, Taster, Kippschalter, Wahltasten und Leuchten als eigene Elemente im
// Licht-DOM (ohne Schattenbaum, damit Marken und Vorlagen greifen). Die Teilung bleibt: eine Wahrheit für Werte
// (wert.ts) und eine für Eingaben (bedienen.ts); die Elemente unterscheiden sich nur in der Darstellung. Übernommen aus
// hifi-regler (appkern/instrumente.js, Stand 9a7c0fe vom 09.11.2026, RAD-6).
//
// Beschriftung: die üblichen (meist englischen) Fachbegriffe der Tontechnik; die deutsche Erklärung steht im Merkmal
// "hilfe" und erscheint im Hover.
//
// Für Svelte und andere Rahmenwerke: Werte, die sich zur Laufzeit ändern, sind Eigenschaften (wert, an, stellung) und
// dürfen schon vor dem Einhängen gesetzt werden; sie gelten dann als Startwert. Programmatisch gesetzte Werte melden kein
// "input" (wie bei Eingabefeldern), nur Bedienung durch den Menschen.
import { bedienen, eingabeMelden, type ReglerZiel } from "./bedienen";
import { attr, hilfe, leuchtfarbe, num, sicher } from "./merkmale";
import { Wert, zahl } from "./wert";

// ─── Geometrie der Skala (Koordinaten -50 bis 50, Winkel im Uhrzeigersinn ab oben) ───
const punkt = (r: number, w: number): [number, number] => [r * Math.sin((w * Math.PI) / 180), -r * Math.cos((w * Math.PI) / 180)];
const bogen = (r: number, von: number, bis: number): string => {
  const [x1, y1] = punkt(r, von), [x2, y2] = punkt(r, bis);
  return `M${x1.toFixed(2)} ${y1.toFixed(2)}A${r} ${r} 0 ${bis - von > 180 ? 1 : 0} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
};
const striche = (n: number, innen: number, aussen: number, innenKlein?: number): string =>
  Array.from({ length: n }, (_, i) => {
    const w = -135 + (i * 270) / (n - 1);
    const r1 = innenKlein && i % 2 ? innenKlein : innen;
    const [x1, y1] = punkt(r1, w), [x2, y2] = punkt(aussen, w);
    return `M${x1.toFixed(2)} ${y1.toFixed(2)}L${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }).join("");
const R_BOGEN = 43, R_MOD = 40.2;

const modellAus = (el: HTMLElement): Wert => {
  const raster = el.getAttribute("raster");
  return new Wert({
    min: num(el, "min", 0), max: num(el, "max", 100), schritt: num(el, "schritt", 1), wert: num(el, "wert", undefined),
    vorgabe: num(el, "vorgabe", undefined), kurve: attr(el, "kurve", "lin") === "log" ? "log" : "lin", einheit: attr(el, "einheit", ""),
    raster: raster !== null ? raster.split("|") : null, bipolar: el.hasAttribute("bipolar"),
  });
};

// ─── Grundlage der Regler ───
export abstract class Regler extends HTMLElement {
  modell?: Wert;
  protected wertFeld!: HTMLElement;
  protected mod = 0;

  connectedCallback(): void {
    if (this.modell) return;
    this.modell = modellAus(this);
    this.mod = num(this, "mod", 0);
    this.tabIndex = this.hasAttribute("gesperrt") ? -1 : 0;
    this.setAttribute("role", "slider");
    this.setAttribute("aria-label", attr(this, "name", "Regler"));
    if (this.hasAttribute("gesperrt")) this.setAttribute("aria-disabled", "true");
    const kappe = this.getAttribute("farbe");
    if (kappe) this.style.setProperty("--kappe-farbe", kappe);
    leuchtfarbe(this, "leuchte", "--ak-wert");
    leuchtfarbe(this, "zeiger", "--zeiger-farbe");
    this.bauen(this.modell);
    hilfe(this);
    bedienen(this.ziel(this.modell));
    this.zeigen();
  }

  protected abstract bauen(m: Wert): void;
  protected abstract ziel(m: Wert): ReglerZiel;
  protected abstract zeigen(): void;

  /** Wert in der Einheit des Reglers; vor dem Einhängen gesetzt gilt er als Startwert */
  get wert(): number | undefined {
    return this.modell ? this.modell.wert : num(this, "wert", undefined);
  }
  set wert(w: number | undefined) {
    if (w === undefined || w === null) return;
    if (!this.modell) { this.setAttribute("wert", String(w)); return; }
    this.modell.wert = this.modell.klemmen(+w);
    this.zeigen();
  }
  /** Stellung von 0 bis 1 über den ganzen Bereich (nach der Kurve) */
  get anteil(): number | undefined {
    return this.modell?.anteil;
  }
  set anteil(a: number | undefined) {
    if (!this.modell || a === undefined) return;
    this.modell.wert = this.modell.klemmen(this.modell.ausAnteil(a));
    this.zeigen();
  }
  /** Wert als Text in seiner Einheit, wie er am Regler steht */
  get text(): string {
    return this.modell?.text ?? "";
  }

  protected zeigenGemeinsam(m: Wert): void {
    this.setAttribute("aria-valuemin", String(m.min));
    this.setAttribute("aria-valuemax", String(m.max));
    this.setAttribute("aria-valuenow", String(m.wert));
    this.setAttribute("aria-valuetext", m.text);
    if (this.wertFeld.textContent !== m.text) this.wertFeld.textContent = m.text;
    this.style.setProperty("--a", m.anteil.toFixed(4));
  }
}

// ─── Drehregler und Drehwahl (mit Raster) ───
export class Drehregler extends Regler {
  private winkelVon = -135;
  private spanne = 270;
  private bogenWert: SVGPathElement | null = null;
  private bogenSchein: SVGPathElement | null = null;
  private bogenMod: SVGPathElement | null = null;
  private punkte: SVGCircleElement[] = [];
  private rastnamen: HTMLElement[] = [];
  /** Rastpunkte rund um die Kappe; der gewählte leuchtet */
  private rastpunkte: SVGCircleElement[] = [];

  protected bauen(m: Wert): void {
    const raster = m.raster;
    const spanne = raster ? Math.min(270, 36 * (raster.length - 1)) : 270;
    this.winkelVon = -spanne / 2;
    this.spanne = spanne;
    const kranz = this.getAttribute("kappe") === "ring"
      ? `<g class="kranz">${Array.from({ length: 15 }, (_, i) => { const [x, y] = punkt(44, -135 + i * (270 / 14)); return `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="2.6"/>`; }).join("")}</g>` : "";
    const rasten = raster ? `<g class="rasten">${raster.map((_, i) => { const [x, y] = punkt(46, this.winkelVon + (i * spanne) / (raster.length - 1)); return `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="1.9"/>`; }).join("")}</g>` : "";
    const namen = raster ? raster.map((r, i) => { const [x, y] = punkt(64, this.winkelVon + (i * spanne) / (raster.length - 1)); return `<span class="ak-dreh-rastname" style="left:${50 + x}%;top:${50 + y}%">${sicher(r)}</span>`; }).join("") : "";
    const grenzen = attr(this, "grenzen", "");
    this.innerHTML = `<div class="ak-dreh-koerper">
        <svg class="ak-dreh-skala" viewBox="-50 -50 100 100" aria-hidden="true">
          ${raster ? "" : `<path class="striche s11" d="${striche(11, 46.5, 49.5)}"/><path class="striche s21" d="${striche(21, 46, 49.8, 47.6)}"/>
          <path class="bahn" d="${bogen(R_BOGEN, -135, 135)}"/><path class="schein" pathLength="100" d="${bogen(R_BOGEN, -135, 135)}"/>
          <path class="wert" pathLength="100" d="${bogen(R_BOGEN, -135, 135)}"/>${this.mod ? `<path class="mod" pathLength="100" d="${bogen(R_MOD, -135, 135)}"/>` : ""}`}
          ${kranz}${rasten}
        </svg>
        <div class="ak-dreh-kappe"><div class="ak-dreh-deckel"></div><div class="ak-dreh-zeiger"></div></div>${namen}
      </div>
      <span class="ak-dreh-name">${sicher(attr(this, "name", ""))}</span><span class="ak-dreh-wert" title="Klicken zum Eintippen"></span>
      ${grenzen ? `<span class="ak-dreh-grenzen">${grenzen.split("|").map((g) => `<span>${sicher(g)}</span>`).join("")}</span>` : ""}`;
    this.wertFeld = this.querySelector<HTMLElement>(".ak-dreh-wert")!;
    this.bogenWert = this.querySelector<SVGPathElement>(".ak-dreh-skala .wert");
    this.bogenSchein = this.querySelector<SVGPathElement>(".ak-dreh-skala .schein");
    this.bogenMod = this.querySelector<SVGPathElement>(".ak-dreh-skala .mod");
    this.punkte = [...this.querySelectorAll<SVGCircleElement>(".kranz circle")];
    this.rastnamen = [...this.querySelectorAll<HTMLElement>(".ak-dreh-rastname")];
    this.rastpunkte = [...this.querySelectorAll<SVGCircleElement>(".rasten circle")];
  }

  protected ziel(m: Wert): ReglerZiel {
    return { el: this, modell: m, griff: this, wertFeld: this.wertFeld, zeigen: () => this.zeigen() };
  }

  protected zeigen(): void {
    const m = this.modell;
    if (!m) return;
    this.zeigenGemeinsam(m);
    const a = m.anteil;
    this.style.setProperty("--winkel", `${(this.winkelVon + a * this.spanne).toFixed(2)}deg`);
    if (this.bogenWert && this.bogenSchein) {
      const nullpunkt = m.bipolar ? m.zuAnteil(m.vorgabe) : 0;
      const von = Math.min(a, nullpunkt) * 100, laenge = Math.abs(a - nullpunkt) * 100;
      for (const p of [this.bogenWert, this.bogenSchein]) {
        p.style.strokeDasharray = `${laenge.toFixed(2)} 1000`;
        p.style.strokeDashoffset = `${(-von).toFixed(2)}`;
        p.style.visibility = laenge < 0.4 ? "hidden" : "visible";
      }
    }
    if (this.bogenMod) {
      const von = Math.max(0, a - this.mod), bis = Math.min(1, a + this.mod);
      this.bogenMod.style.strokeDasharray = `${((bis - von) * 100).toFixed(2)} 1000`;
      this.bogenMod.style.strokeDashoffset = `${(-von * 100).toFixed(2)}`;
    }
    if (this.punkte.length) {
      const n = this.punkte.length - 1;
      this.punkte.forEach((p, i) => p.classList.toggle("an", i / n <= a + 1e-6 && (a > 0.001 || i === 0)));
    }
    this.rastnamen.forEach((s, i) => s.classList.toggle("an", i === m.wert));
    this.rastpunkte.forEach((p, i) => p.classList.toggle("an", i === m.wert));
  }
}

// ─── Schieber: Bahn, Fader, Leuchtschiene, Leuchtbalken; waagrecht oder senkrecht ───
export class Schieber extends Regler {
  private feld!: HTMLElement;
  private grenzNamen: HTMLElement[] = [];
  private segmente = 0;

  protected bauen(m: Wert): void {
    const grenzen = m.raster ? m.raster : attr(this, "grenzen", "").split("|").filter(Boolean);
    const segmente = num(this, "segmente", 0);
    if (segmente) this.style.setProperty("--seg-w", `${100 / segmente}%`);
    this.innerHTML = `<div class="ak-schieber-kopf"><span class="ak-dreh-name">${sicher(attr(this, "name", ""))}</span><span class="ak-dreh-wert" title="Klicken zum Eintippen"></span></div>
      <div class="ak-schieber-feld"><div class="ak-schieber-bahn"><div class="ak-schieber-fuellung"></div>${segmente ? `<div class="segmente"></div>` : ""}</div><div class="ak-schieber-griff"></div></div>
      ${grenzen.length ? `<div class="ak-schieber-grenzen">${grenzen.map((g) => `<span>${sicher(g)}</span>`).join("")}</div>` : ""}`;
    this.wertFeld = this.querySelector<HTMLElement>(".ak-dreh-wert")!;
    this.feld = this.querySelector<HTMLElement>(".ak-schieber-feld")!;
    this.grenzNamen = m.raster ? [...this.querySelectorAll<HTMLElement>(".ak-schieber-grenzen span")] : [];
    this.segmente = segmente;
    this.setAttribute("aria-orientation", attr(this, "richtung", "waagrecht") === "senkrecht" ? "vertical" : "horizontal");
  }

  protected ziel(m: Wert): ReglerZiel {
    const griff = this.querySelector<HTMLElement>(".ak-schieber-griff")!;
    const senkrecht = attr(this, "richtung", "waagrecht") === "senkrecht";
    return { el: this, modell: m, griff: this.feld, bahn: this.feld, richtung: senkrecht ? "senkrecht" : "waagrecht",
             griffMass: attr(this, "art", "") === "balken" ? 0 : (senkrecht ? griff.offsetHeight : griff.offsetWidth) || 22,
             wertFeld: this.wertFeld, zeigen: () => this.zeigen() };
  }

  protected zeigen(): void {
    const m = this.modell;
    if (!m) return;
    this.zeigenGemeinsam(m);
    // Leuchtbalken: nur ganze Segmente leuchten
    if (this.segmente) this.style.setProperty("--a", (Math.round(m.anteil * this.segmente) / this.segmente).toFixed(4));
    this.grenzNamen.forEach((s, i) => s.classList.toggle("an", i === m.wert));
  }
}

// ─── Taster: rasten (an und aus), tasten (an, solange gedrückt), tippen (Tempo aus dem Abstand der Tipps) ───
// Leuchten: "licht" setzt eine Leuchte als Lichtschlitz in die obere Kante der Taste (Tastenlicht: die Taste bleibt so
// hoch wie ohne, hervorgehoben wird nur über Licht und Farbe, Nutzer 16.11.2026); "led" eine Leuchte über die Taste.
export class Taster extends HTMLElement {
  private knopf?: HTMLButtonElement;
  private leuchten: Element[] = [];
  private tipps: number[] = [];
  /** Schläge je Minute aus dem Abstand der letzten Tipps (Modus tippen) */
  tempo?: number;

  connectedCallback(): void {
    if (this.knopf) return;
    const art = attr(this, "art", "flach"), modus = attr(this, "modus", "rasten");
    leuchtfarbe(this);
    const symbol = this.getAttribute("symbol");
    const beschriftung = sicher(attr(this, "beschriftung", ""));
    const innen = art === "fuss" ? `<span class="ak-taster-mutter"></span>` : art === "flach" ? `<span class="ak-taster-streifen"></span><span>${beschriftung}</span>`
      : symbol ? `<i class="fa-solid ${sicher(symbol)}" aria-hidden="true"></i>` : `<span>${beschriftung}</span>`;
    const ueber = this.hasAttribute("led") ? `<ak-led farbe="${sicher(attr(this, "led", ""))}" groesse="${art === "fuss" ? "mittel" : "klein"}"></ak-led>` : "";
    const schlitz = this.hasAttribute("licht") ? `<ak-led art="schlitz" farbe="${sicher(attr(this, "licht", ""))}"></ak-led>` : "";
    const text = attr(this, "text", "");
    this.innerHTML = `${ueber}<button class="ak-taster-knopf" type="button" aria-label="${sicher(text || attr(this, "beschriftung", ""))}">${schlitz}${innen}</button>${text ? `<span class="ak-taster-text">${sicher(text)}</span>` : ""}`;
    const knopf = this.querySelector<HTMLButtonElement>("button")!;
    this.knopf = knopf;
    this.leuchten = [...this.querySelectorAll("ak-led")];
    hilfe(this, knopf);
    if (modus === "rasten") knopf.setAttribute("aria-pressed", String(this.hasAttribute("an")));
    const druecken = (an: boolean) => { this.classList.toggle("gedrueckt", an); if (modus === "tasten") this.setzen(an); };
    knopf.addEventListener("pointerdown", () => druecken(true));
    knopf.addEventListener("pointerup", () => druecken(false));
    knopf.addEventListener("pointerleave", () => druecken(false));
    knopf.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) druecken(true); });
    knopf.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") druecken(false); });
    knopf.addEventListener("click", () => {
      if (modus === "rasten") this.setzen(!this.hasAttribute("an"));
      if (modus === "tippen") this.tippen();
    });
    this.zeigen(this.hasAttribute("an"));
  }

  /** eingeschaltet (rasten) oder gedrückt (tasten); gesetzt ohne Meldung */
  get an(): boolean {
    return this.hasAttribute("an");
  }
  set an(an: boolean) {
    if (this.knopf) this.zeigen(!!an);
    else this.toggleAttribute("an", !!an);
  }

  private zeigen(an: boolean): void {
    this.toggleAttribute("an", an);
    if (this.knopf?.hasAttribute("aria-pressed")) this.knopf.setAttribute("aria-pressed", String(an));
    for (const l of this.leuchten) l.setAttribute("zustand", an ? "an" : "aus");
  }

  /** Bedienung: schalten und melden */
  setzen(an: boolean): void {
    this.zeigen(an);
    eingabeMelden(this, { name: attr(this, "text", attr(this, "beschriftung", "")), text: an ? "an" : "aus", art: "Taster" });
  }

  private tippen(): void {
    const t = performance.now();
    this.tipps = [...this.tipps.filter((x) => t - x < 2500), t].slice(-5);
    for (const l of this.leuchten) l.setAttribute("zustand", "an");
    setTimeout(() => { for (const l of this.leuchten) l.setAttribute("zustand", "aus"); }, 90);
    if (this.tipps.length >= 2) {
      const abstand = (this.tipps[this.tipps.length - 1] - this.tipps[0]) / (this.tipps.length - 1);
      const tempo = 60000 / abstand;
      this.tempo = tempo;
      this.dispatchEvent(new CustomEvent<{ tempo: number }>("tempo", { bubbles: true, detail: { tempo } }));
      document.dispatchEvent(new CustomEvent("ak-eingabe", { detail: { name: "Tippen", text: `${zahl(tempo, 1)} Schläge je Minute`, art: "Taster" } }));
    }
  }
}

// ─── Kippschalter: zwei oder drei Stellungen ───
export type Stellung = "oben" | "mitte" | "unten";

export class Kippschalter extends HTMLElement {
  static observedAttributes = ["stellung"];
  private knopf?: HTMLButtonElement;
  private stellungen: Stellung[] = ["oben", "unten"];
  private namen: string[] = [];

  connectedCallback(): void {
    if (this.knopf) return;
    const namen = attr(this, "beschriftung", "An|Aus").split("|");   // oben|unten oder oben|mitte|unten
    this.stellungen = namen.length === 3 ? ["oben", "mitte", "unten"] : ["oben", "unten"];
    this.namen = namen;
    if (!this.hasAttribute("stellung")) this.setAttribute("stellung", this.stellungen[this.stellungen.length - 1]);
    const mitte = namen.length === 3 ? `<span class="ak-kipp-text mitte">${sicher(namen[1])}</span>` : "";
    const name = this.getAttribute("name");
    this.innerHTML = `<span class="ak-kipp-text oben">${sicher(namen[0])}</span>
      <button class="ak-kipp-knopf" type="button"><span class="ak-kipp-mutter"></span><span class="ak-kipp-hebel"></span></button>
      <span class="ak-kipp-text unten">${sicher(namen[namen.length - 1])}</span>${mitte}${name !== null ? `<span class="ak-etikett">${sicher(name)}</span>` : ""}`;
    const knopf = this.querySelector<HTMLButtonElement>("button")!;
    this.knopf = knopf;
    if (namen.length === 3) { knopf.setAttribute("role", "slider"); knopf.setAttribute("aria-valuemin", "0"); knopf.setAttribute("aria-valuemax", "2"); }
    else knopf.setAttribute("role", "switch");
    knopf.setAttribute("aria-label", attr(this, "name", namen.join(" oder ")));
    hilfe(this, knopf);
    knopf.addEventListener("click", (e) => {
      const r = knopf.getBoundingClientRect();
      if (e.detail === 0) { this.wechseln(1); return; }        // Tastatur: detail 0
      const lage = (e.clientY - r.top) / r.height;
      if (this.stellungen.length === 3) this.stellen(lage < 0.36 ? "oben" : lage > 0.64 ? "unten" : "mitte");
      else this.stellen(lage < 0.5 ? "oben" : "unten");
    });
    knopf.addEventListener("keydown", (e) => {
      if (e.key === "ArrowUp" || e.key === "ArrowRight") { e.preventDefault(); this.wechseln(-1, false); }
      if (e.key === "ArrowDown" || e.key === "ArrowLeft") { e.preventDefault(); this.wechseln(1, false); }
    });
    this.zeigen();
  }

  attributeChangedCallback(): void {
    if (this.knopf) this.zeigen();
  }

  /** Stellung; gesetzt ohne Meldung */
  get stellung(): Stellung {
    return (this.getAttribute("stellung") as Stellung | null) ?? this.stellungen[this.stellungen.length - 1];
  }
  set stellung(s: Stellung) {
    this.setAttribute("stellung", s);
  }

  private wechseln(richtung: number, rundum = true): void {
    const i = this.stellungen.indexOf(this.stellung);
    let j = i + richtung;
    if (rundum) j = (j + this.stellungen.length) % this.stellungen.length;
    this.stellen(this.stellungen[Math.min(this.stellungen.length - 1, Math.max(0, j))]);
  }

  /** Bedienung: stellen und melden */
  stellen(s: Stellung): void {
    this.setAttribute("stellung", s);
    eingabeMelden(this, { name: attr(this, "name", "Kippschalter"), text: this.namen[this.stellungen.indexOf(s)] ?? s, art: "Kippschalter" });
  }

  private zeigen(): void {
    const knopf = this.knopf;
    if (!knopf) return;
    const s = this.stellung;
    const i = this.stellungen.indexOf(s);
    if (this.stellungen.length === 3) { knopf.setAttribute("aria-valuenow", String(i)); knopf.setAttribute("aria-valuetext", this.namen[i] ?? s); }
    else knopf.setAttribute("aria-checked", String(i === 0));
    this.querySelectorAll(".ak-kipp-text").forEach((t) => t.classList.toggle("an", t.classList.contains(s)));
  }
}

// ─── Wahltasten und Schiebeschalter: genau eine Wahl, Pfeiltasten wandern ───
export class Wahl extends HTMLElement {
  private knoepfe: HTMLButtonElement[] = [];
  private optionen: string[] = [];
  private gebaut = false;

  connectedCallback(): void {
    if (this.gebaut) return;
    this.gebaut = true;
    const optionen = attr(this, "optionen", "I|II").split("|");
    leuchtfarbe(this);
    const name = attr(this, "name", "");
    this.innerHTML = `${name ? `<span class="ak-etikett">${sicher(name)}</span>` : ""}<div class="ak-wahl-reihe" role="radiogroup" aria-label="${sicher(name || "Wahl")}" style="--n:${optionen.length}">
      ${this.getAttribute("art") === "schiebe" ? `<span class="ak-wahl-schieber"></span>` : ""}${optionen.map((o) => `<button type="button" role="radio">${sicher(o)}</button>`).join("")}</div>`;
    this.knoepfe = [...this.querySelectorAll<HTMLButtonElement>("button")];
    this.optionen = optionen;
    hilfe(this, this.querySelector(".ak-wahl-reihe")!);
    this.knoepfe.forEach((k, i) => {
      k.addEventListener("click", () => this.waehlen(i));
      k.addEventListener("keydown", (e) => {
        const n = ({ ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 } as Record<string, number>)[e.key];
        if (!n) return;
        e.preventDefault();
        const j = (i + n + optionen.length) % optionen.length;
        this.waehlen(j);
        this.knoepfe[j].focus();
      });
    });
    this.waehlen(Math.max(0, optionen.indexOf(attr(this, "wert", optionen[0]))), true);
  }

  /** gewählte Option (ihr Text); gesetzt ohne Meldung */
  get wert(): string {
    return attr(this, "wert", this.optionen[0] ?? "");
  }
  set wert(w: string) {
    if (!this.gebaut) { this.setAttribute("wert", w); return; }
    const i = this.optionen.indexOf(w);
    if (i >= 0) this.waehlen(i, true);
  }

  private waehlen(i: number, still = false): void {
    this.setAttribute("wert", this.optionen[i]);
    this.style.setProperty("--i", String(i));
    this.querySelector<HTMLElement>(".ak-wahl-schieber")?.style.setProperty("--i", String(i));
    this.knoepfe.forEach((k, j) => { k.setAttribute("aria-checked", String(i === j)); k.tabIndex = i === j ? 0 : -1; });
    if (!still) eingabeMelden(this, { name: attr(this, "name", "Wahl"), text: this.optionen[i], art: "Wahl" });
  }
}

// ─── Leuchte; art="schlitz" ist das Tastenlicht (Lichtschlitz in der oberen Kante einer Taste) ───
export type Leuchtzustand = "an" | "aus" | "blinkt" | "atmet" | "flackert";
const ZUSTAENDE: Record<string, string> = { an: "an", aus: "aus", blinkt: "blinkt", atmet: "pulsiert", flackert: "flackert" };

export class Leuchte extends HTMLElement {
  static observedAttributes = ["zustand", "farbe"];

  connectedCallback(): void {
    if (!this.firstElementChild) {
      const text = attr(this, "text", "");
      this.innerHTML = `<span class="ak-led-licht"></span>${text ? `<span class="ak-led-text">${sicher(text)}</span>` : ""}`;
    }
    this.setAttribute("role", "img");
    hilfe(this);
    this.attributeChangedCallback();
  }

  attributeChangedCallback(): void {
    leuchtfarbe(this);
    const z = attr(this, "zustand", "aus");
    this.setAttribute("aria-label", `${attr(this, "text", "Leuchte")}: ${ZUSTAENDE[z] ?? z}`);
  }
}
