// Rollen zu einer Stelle (HELF-91), eine Wahrheit für alle Apps: Mitlesen beim Abspielen, Sprünge zu Treffern und
// Abweichungen, die Auswahl im Bearbeiten. Die Stelle landet im oberen Drittel des frei sichtbaren Bereichs, nie hinter
// einem festen Kopf oder einer festen Leiste.
//
// Feste Bereiche melden sich mit `use:fest={"oben"}` bzw. `use:fest={"unten"}` (oder dem Attribut data-fest). Ihre
// Höhe wird gemessen, nie geschätzt: ein ResizeObserver hält am Rollfeld `--fest-oben` und `--fest-unten` aktuell und
// setzt damit `scroll-padding`, sodass auch das Rollen des Browsers (Anker, Fokus, scrollIntoView) sie einhält.
//
// Gerollt wird immer nur das Rollfeld der Stelle selbst, nie die Vorfahren: scrollIntoView rollte bisher jeden
// Vorfahren mit, auch die feste Seite, und richtete lange Beiträge mittig aus, sodass ihr Anfang oben verschwand.

export type Seite = "oben" | "unten";

// Wo die Stelle nach einem Sprung steht: dieser Anteil des freien Bereichs unter dessen oberem Rand
const ZIEL = 0.12;
// Mitlesen rollt erst, wenn die Stelle tiefer läuft als dieser Anteil (oder über den oberen Rand); so springt es nicht
// bei jedem Wort, und die gesprochene Stelle bleibt im oberen Drittel
const BEQUEM = 1 / 3;
// Abstand zu den Rändern des freien Bereichs, in dem eine Stelle noch als verdeckt gilt
const LUFT = 6;
// Höhe einer Zeile, mit der eine lange Stelle (ein ganzer Beitrag) beim Mitlesen zählt
const ZEILE = 40;

const px = (v: string) => parseFloat(v) || 0;

// Das Rollfeld einer Stelle: der nächste Vorfahr, der senkrecht rollt, sonst die Seite
export function rollfeldVon(el: Element): HTMLElement {
  for (let x = el.parentElement; x && x !== document.body; x = x.parentElement) {
    const s = getComputedStyle(x);
    if (/(auto|scroll)/.test(s.overflowY) && x.scrollHeight > x.clientHeight + 1) return x;
  }
  return document.scrollingElement as HTMLElement;
}

// Rollfeld, an dem eine feste Leiste klebt (für sie zählt nur die Art des Überlaufs, nicht ob gerade etwas zu rollen ist)
function klebtAn(el: Element): HTMLElement | null {
  for (let x = el.parentElement; x && x !== document.body; x = x.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(x).overflowY)) return x;
  }
  return null;
}

// Der frei sichtbare Bereich eines Rollfelds in Fensterkoordinaten: sein Kasten im Fenster ohne die festen Bereiche, die
// ihn oben und unten verdecken. Eine klebende Leiste im Rollfeld zählt mit ihrer Höhe dort, wo sie klebt (auch wenn sie
// gerade noch weiter unten steht), eine feste oder andere Leiste mit ihrem Kasten, wenn sie über den Rand reicht.
export function freierBereich(feld: HTMLElement): { oben: number; unten: number } {
  const seite = feld === document.scrollingElement;
  const k = feld.getBoundingClientRect();
  const innenOben = seite ? 0 : k.top + feld.clientTop;
  const innenUnten = seite ? innerHeight : innenOben + feld.clientHeight;
  let oben = Math.max(innenOben, 0);
  let unten = Math.min(innenUnten, innerHeight);
  const links = seite ? 0 : k.left;
  const rechts = seite ? innerWidth : k.right;
  const leisten = [...document.querySelectorAll<HTMLElement>("[data-fest]")]
    .filter((l) => l.getClientRects().length && getComputedStyle(l).visibility !== "hidden")
    .map((l) => ({ l, r: l.getBoundingClientRect(), s: getComputedStyle(l) }))
    .filter(({ r }) => r.width > 0 && r.height > 0 && r.right > links + 1 && r.left < rechts - 1)
    // was im Rollfeld weder klebt noch fest steht, rollt mit dem Inhalt und verdeckt nichts
    .filter(({ l, s }) => !feld.contains(l) || s.position === "sticky" || s.position === "fixed");
  for (const { l, r, s } of leisten.filter((x) => x.l.dataset.fest === "oben").sort((a, b) => a.r.top - b.r.top)) {
    const klebt = s.position === "sticky" && feld.contains(l);
    const boden = klebt ? innenOben + px(s.top) + r.height : r.bottom;
    const kopf = klebt ? innenOben + px(s.top) : r.top;
    if (kopf <= oben + 1 && boden > oben) oben = boden;
  }
  for (const { l, r, s } of leisten.filter((x) => x.l.dataset.fest === "unten").sort((a, b) => b.r.bottom - a.r.bottom)) {
    const klebt = s.position === "sticky" && feld.contains(l);
    const dach = klebt ? innenUnten - px(s.bottom) - r.height : r.top;
    const fuss = klebt ? innenUnten - px(s.bottom) : r.bottom;
    if (fuss >= unten - 1 && dach < unten) unten = dach;
  }
  return { oben, unten: Math.max(unten, oben + 1) };
}

// Ob die Stelle ganz im freien Bereich ihres Rollfelds steht
export function stelleFrei(el: Element): boolean {
  const f = freierBereich(rollfeldVon(el));
  const r = el.getBoundingClientRect();
  return r.top >= f.oben && r.bottom <= f.unten;
}

// Rollt das Rollfeld der Stelle so, dass sie im oberen Drittel des freien Bereichs steht. `nurWennNoetig`: nur wenn sie
// nicht schon ganz frei sichtbar ist (etwa die Auswahl im Bearbeiten). Gerollt wird nur dieses Rollfeld.
export function zuStelle(el: Element | null | undefined, { sanft = false, nurWennNoetig = false } = {}): void {
  if (!el) return;
  const feld = rollfeldVon(el);
  merken(feld);
  const f = freierBereich(feld);
  const r = el.getBoundingClientRect();
  if (nurWennNoetig && r.top >= f.oben + LUFT && r.bottom <= f.unten - LUFT) return;
  const ziel = f.oben + Math.max(LUFT, (f.unten - f.oben) * ZIEL);
  feld.scrollTo({ top: feld.scrollTop + r.top - ziel, behavior: sanft ? "smooth" : "auto" });
}

// Mitlesen: rollt nur, wenn die Stelle aus dem bequemen Bereich läuft (über den oberen Rand oder unter das obere
// Drittel), dann sanft wieder nach oben ins Drittel
export function stelleFolgen(el: Element | null | undefined): void {
  if (!el) return;
  const feld = rollfeldVon(el);
  const f = freierBereich(feld);
  const r = el.getBoundingClientRect();
  // die Stelle ist ihre erste Zeile: ein langer Beitrag ohne Wortzeiten zählt mit seinem Anfang
  const zeile = Math.min(r.bottom, r.top + ZEILE);
  if (r.top >= f.oben + LUFT && zeile <= f.oben + (f.unten - f.oben) * BEQUEM) return;
  zuStelle(el, { sanft: true });
}

// Folgt der Wiedergabe, außer man rollt selbst (Rad, Wischen): dann ruht es `ruheMs` lang
export class Mitrollen {
  an = $state(true);
  #pause: ReturnType<typeof setTimeout> | undefined;
  #ruheMs: number;

  constructor(ruheMs = 8000) {
    this.#ruheMs = ruheMs;
  }

  selbstGerollt = () => {
    this.an = false;
    clearTimeout(this.#pause);
    this.#pause = setTimeout(() => (this.an = true), this.#ruheMs);
  };

  folgen = () => {
    clearTimeout(this.#pause);
    this.an = true;
  };

  // Der gesprochenen Stelle folgen, wenn das Mitrollen gerade an ist
  folge(el: Element | null | undefined): void {
    if (this.an) stelleFolgen(el);
  }
}

// --- Gemessene Höhe der festen Bereiche am Rollfeld ------------------------------------------------------------

const felder = new Set<HTMLElement>();
let geplant = false;
let beobachter: ResizeObserver | null = null;
const beobachten = () => (beobachter ??= new ResizeObserver(planen));

function merken(feld: HTMLElement): void {
  if (feld === document.scrollingElement || felder.has(feld)) return;
  felder.add(feld);
  beobachten().observe(feld);
  planen();
}

// Am Rollfeld --fest-oben und --fest-unten setzen, dazu scroll-padding (Rollen des Browsers hält sie dann ein)
function pflegen(): void {
  geplant = false;
  for (const feld of felder) {
    if (!feld.isConnected) {
      felder.delete(feld);
      beobachter?.unobserve(feld);
      continue;
    }
    const k = feld.getBoundingClientRect();
    const f = freierBereich(feld);
    const oben = Math.max(0, Math.round(f.oben - Math.max(k.top + feld.clientTop, 0)));
    const unten = Math.max(0, Math.round(Math.min(k.top + feld.clientTop + feld.clientHeight, innerHeight) - f.unten));
    feld.style.setProperty("--fest-oben", `${oben}px`);
    feld.style.setProperty("--fest-unten", `${unten}px`);
    feld.style.scrollPaddingTop = `${oben}px`;
    feld.style.scrollPaddingBottom = `${unten}px`;
  }
}

function planen(): void {
  if (geplant) return;
  geplant = true;
  requestAnimationFrame(pflegen);
}

// Svelte-Aktion: ein fester Bereich (Kopf, klebende Leiste, Spieler) meldet sich an; seine Höhe zählt ab jetzt für
// jedes Rollen zu einer Stelle in dem Rollfeld, das er verdeckt
export function fest(node: HTMLElement, seite: Seite = "oben") {
  node.dataset.fest = seite;
  beobachten().observe(node);
  const feld = klebtAn(node);
  if (feld) merken(feld);
  planen();
  return {
    update(neu: Seite) {
      node.dataset.fest = neu;
      planen();
    },
    destroy() {
      beobachter?.unobserve(node);
      delete node.dataset.fest;
      planen();
    },
  };
}
