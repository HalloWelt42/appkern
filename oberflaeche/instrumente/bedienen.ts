// Eingaben der Regler an einer Stelle: Ziehen, Mausrad, Tasten, Doppelklick, Doppeltipp, Feinschritt und Werteingabe.
// Übernommen aus hifi-regler (appkern/instrumente.js, Stand 9a7c0fe vom 09.11.2026, RAD-6).
//
// Bedienung aller Regler:
//   Ziehen hoch und runter (Schieber: entlang der Bahn), Mausrad, Pfeiltasten, Bild auf und ab (zehnmal), Pos1 und Ende;
//   Umschalttaste hält: ein Zehntel (fein); Doppelklick oder Doppeltipp: Vorgabe; Entf: Vorgabe; Klick auf den Wert oder
//   Eingabetaste: Wert eintippen. Jede Eingabe meldet sich als "input" am Element (beim Loslassen "change") und als
//   Ereignis "ak-eingabe" am Dokument (für Anzeigen der Seite).
import type { Wert } from "./wert";

const FEIN = 0.1;            // Umschalttaste: ein Zehntel
const ZIEH_PX = 240;         // Ziehen: so viele Pixel für den ganzen Bereich
const RAD_JE_PX = 0.0002;    // Mausrad: Anteil je Pixel Drehung (eine Raste von 100 Pixel = 2 Prozent)
const RAD_RASTE_PX = 60;     // Mausrad bei Rastern: so viel Drehung für eine Raste
const DOPPEL_MS = 330;       // Doppeltipp: höchstens so lange und
const DOPPEL_PX = 14;        //   so weit auseinander
const ROLLPAUSE_MS = 450;    // so lange nach dem Rollen der Seite dreht das Rad keinen Regler (kein Kapern beim Rollen)

/** Inhalt des Ereignisses "ak-eingabe" am Dokument: welches Instrument, welcher Wert, auf welchem Weg */
export interface EingabeMeldung {
  name: string;
  text: string;
  art: string;
  fein?: boolean;
}

/** Ein Regler, wie ihn die Bedienung braucht */
export interface ReglerZiel {
  el: HTMLElement;
  modell: Wert;
  /** neu zeichnen nach einer Änderung des Werts */
  zeigen: () => void;
  /** Element für das Ziehen */
  griff: HTMLElement;
  /** Element für die Lage (nur Schieber): Klick auf die Bahn setzt den Wert absolut */
  bahn?: HTMLElement;
  richtung?: "senkrecht" | "waagrecht";
  griffMass?: number;
  /** Element mit dem Wert als Text; ein Klick darauf öffnet die Werteingabe */
  wertFeld: HTMLElement;
}

let zuletztGerollt = 0;
let rollenBeobachtet = false;
function rollenBeobachten(): void {
  if (rollenBeobachtet) return;
  rollenBeobachtet = true;
  document.addEventListener("scroll", () => { zuletztGerollt = performance.now(); }, { capture: true, passive: true });
}

/** Eingabe melden: am Element ("input", sprudelt) und am Dokument ("ak-eingabe") */
export function eingabeMelden(el: HTMLElement, meldung: EingabeMeldung): void {
  el.dispatchEvent(new CustomEvent("input", { bubbles: true }));
  document.dispatchEvent(new CustomEvent<EingabeMeldung>("ak-eingabe", { detail: meldung }));
}

const TASTENNAME: Record<string, string> = { ArrowUp: "hoch", ArrowRight: "rechts", ArrowDown: "runter", ArrowLeft: "links", PageUp: "Bild auf",
  PageDown: "Bild ab", Home: "Pos1", End: "Ende" };

/** Bedienung eines Reglers einrichten (einmal je Element) */
export function bedienen(ziel: ReglerZiel): void {
  rollenBeobachten();
  const { el, modell } = ziel;
  let zieht: { id: number; x: number; y: number; roh: number } | null = null;
  let letzterTipp: { t: number; x: number; y: number } | null = null;
  let radRest = 0;
  const gesperrt = () => el.getAttribute("aria-disabled") === "true";
  const melden = (art: string, fein: boolean) =>
    eingabeMelden(el, { name: el.getAttribute("name") ?? "", text: modell.text, art, fein });
  const setzenAnteil = (a: number, art: string, fein: boolean) => {
    const vorher = modell.wert;
    modell.wert = modell.klemmen(modell.ausAnteil(a));
    ziel.zeigen();
    if (modell.wert !== vorher) melden(art, fein);
  };
  const vorgabe = (art: string) => { modell.wert = modell.klemmen(modell.vorgabe); ziel.zeigen(); melden(art, false); };

  // Ziehen: relativ (Drehregler, Griff) oder absolut (Klick auf die Bahn, danach relativ weiter)
  ziel.griff.addEventListener("pointerdown", (e) => {
    const quelle = e.target as Element;
    if (gesperrt() || e.button > 0 || quelle.closest(".ak-eingabe")) return;
    if (quelle === ziel.wertFeld) return;      // Klick auf den Wert öffnet die Eingabe
    e.preventDefault();
    el.focus({ preventScroll: true });
    // Doppeltipp und Doppelklick: Vorgabe (eigene Erkennung, weil dblclick bei Fingern unzuverlässig kommt)
    const jetzt = performance.now();
    if (letzterTipp && jetzt - letzterTipp.t < DOPPEL_MS && Math.hypot(e.clientX - letzterTipp.x, e.clientY - letzterTipp.y) < DOPPEL_PX) {
      letzterTipp = null;
      vorgabe(e.pointerType === "touch" ? "Doppeltipp" : "Doppelklick");
      return;
    }
    letzterTipp = { t: jetzt, x: e.clientX, y: e.clientY };
    let roh = modell.anteil;
    if (ziel.bahn && !quelle.closest(".ak-schieber-griff")) {
      const r = ziel.bahn.getBoundingClientRect(), g = ziel.griffMass ?? 0;
      roh = ziel.richtung === "senkrecht" ? 1 - (e.clientY - r.top - g / 2) / (r.height - g) : (e.clientX - r.left - g / 2) / (r.width - g);
      roh = Math.min(1, Math.max(0, roh));
      setzenAnteil(roh, "Klick auf die Bahn", false);
    }
    zieht = { id: e.pointerId, x: e.clientX, y: e.clientY, roh };
    el.setPointerCapture?.(e.pointerId);
    el.classList.add("zieht");
  });
  el.addEventListener("pointermove", (e) => {
    if (!zieht || e.pointerId !== zieht.id) return;
    const dx = e.clientX - zieht.x, dy = e.clientY - zieht.y;
    zieht.x = e.clientX;
    zieht.y = e.clientY;
    const laenge = ziel.bahn ? (ziel.richtung === "senkrecht" ? ziel.bahn.clientHeight : ziel.bahn.clientWidth) : ZIEH_PX;
    const weg = ziel.bahn ? (ziel.richtung === "senkrecht" ? -dy : dx) : -dy + dx;
    zieht.roh = Math.min(1, Math.max(0, zieht.roh + (weg / Math.max(60, laenge)) * (e.shiftKey ? FEIN : 1)));
    setzenAnteil(zieht.roh, "Ziehen", e.shiftKey);
  });
  const ende = (e: PointerEvent) => {
    if (!zieht || e.pointerId !== zieht.id) return;
    zieht = null;
    el.classList.remove("zieht");
    el.dispatchEvent(new CustomEvent("change", { bubbles: true }));
  };
  el.addEventListener("pointerup", ende);
  el.addEventListener("pointercancel", ende);

  // Mausrad: nur wenn die Seite nicht gerade rollt; Umschalttaste fein (macOS schickt dann deltaX)
  el.addEventListener("wheel", (e) => {
    if (gesperrt() || performance.now() - zuletztGerollt < ROLLPAUSE_MS) return;
    e.preventDefault();
    const delta = (e.deltaY || e.deltaX) * (e.deltaMode === 1 ? 33 : 1);
    if (modell.raster) {
      radRest += delta;
      if (Math.abs(radRest) < RAD_RASTE_PX) return;
      const n = Math.sign(radRest);
      radRest = 0;
      setzenAnteil(modell.anteil - n * modell.tastenAnteil(false), "Mausrad", false);
      return;
    }
    setzenAnteil(modell.anteil - delta * RAD_JE_PX * (e.shiftKey ? FEIN : 1), "Mausrad", e.shiftKey);
  }, { passive: false });

  // Tasten
  el.addEventListener("keydown", (e) => {
    if (gesperrt() || (e.target as Element).closest(".ak-eingabe")) return;
    const s = modell.tastenAnteil(e.shiftKey);
    const a = modell.anteil;
    const tasten: Record<string, number> = {
      ArrowUp: a + s, ArrowRight: a + s, ArrowDown: a - s, ArrowLeft: a - s,
      PageUp: a + (modell.raster ? s : 0.1), PageDown: a - (modell.raster ? s : 0.1), Home: 0, End: 1,
    };
    if (e.key in tasten) { e.preventDefault(); setzenAnteil(tasten[e.key], `Taste ${TASTENNAME[e.key]}`, e.shiftKey); return; }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); vorgabe("Taste Entf"); return; }
    if (e.key === "Enter") { e.preventDefault(); eintippen(ziel); }
  });
  el.addEventListener("dblclick", (e) => e.preventDefault());
  ziel.wertFeld.addEventListener("click", () => { if (!gesperrt()) eintippen(ziel); });
}

// Wert eintippen: ein Eingabefeld an der Stelle des Werts, Eingabetaste übernimmt, Escape bricht ab
function eintippen(ziel: ReglerZiel): void {
  const { el, modell, wertFeld } = ziel;
  if (el.querySelector(".ak-eingabe")) return;
  const feld = document.createElement("input");
  feld.className = "ak-eingabe";
  feld.value = modell.text;
  feld.setAttribute("aria-label", `${el.getAttribute("name") || "Wert"} eintippen`);
  feld.inputMode = modell.raster ? "text" : "decimal";
  wertFeld.hidden = true;
  wertFeld.after(feld);
  feld.focus();
  feld.select();
  let fertig = false;
  const schliessen = (uebernehmen: boolean) => {
    if (fertig) return;
    fertig = true;
    if (uebernehmen) {
      const w = modell.lesen(feld.value);
      if (w !== null && !Number.isNaN(w)) {
        modell.wert = modell.klemmen(w);
        eingabeMelden(el, { name: el.getAttribute("name") ?? "", text: modell.text, art: "Eingetippt", fein: false });
      }
    }
    feld.remove();
    wertFeld.hidden = false;
    ziel.zeigen();
    el.focus({ preventScroll: true });
  };
  feld.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); schliessen(true); }
    if (e.key === "Escape") { e.preventDefault(); schliessen(false); }
    e.stopPropagation();
  });
  feld.addEventListener("blur", () => schliessen(true));
}
