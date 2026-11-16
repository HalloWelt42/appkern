// Instrumente des Appkerns (RAD-6, aus hifi-regler): Regler und Anzeigen als eigene Elemente im Licht-DOM, nutzbar aus
// jeder Svelte-Komponente wie gewöhnliches Markup (<ak-dreh>, <ak-taster>, <ak-led>, <ak-segmente> ...). Eigener
// Eingang (appkern-oberflaeche/instrumente), damit Apps ohne Instrumente nichts davon laden. Das Einbinden meldet die
// Elemente an (einmal, auch bei mehrfachem Import); die Gestaltung kommt aus appkern-oberflaeche/instrumente.css, das
// Material aus einer Vorlage (etwa HiFi).
//
//   import "appkern-oberflaeche/instrumente.css";
//   import { instrumente } from "appkern-oberflaeche/instrumente";   // oder nur: import "appkern-oberflaeche/instrumente";
//
// Typen: die Merkmale je Element prüft svelte-check im Markup (typen.ts), document.querySelector("ak-dreh") liefert die
// Klasse Drehregler, das Ereignis "ak-eingabe" am Dokument trägt eine EingabeMeldung.
import { Pegel, Schirm, Segmente, Zeiger } from "./anzeigen";
import { Drehregler, Kippschalter, Leuchte, Schieber, Taster, Wahl } from "./regler";

/** Die eigenen Elemente mit ihren Namen im Markup; die eine Liste für das Anmelden */
export const instrumente = {
  "ak-dreh": Drehregler,
  "ak-schieber": Schieber,
  "ak-taster": Taster,
  "ak-kipp": Kippschalter,
  "ak-wahl": Wahl,
  "ak-led": Leuchte,
  "ak-segmente": Segmente,
  "ak-zeiger": Zeiger,
  "ak-pegel": Pegel,
  "ak-schirm": Schirm,
} as const;

function anmelden(): void {
  if (typeof customElements === "undefined") return;   // ohne Browser (Bau, Prüfung) nichts anmelden
  for (const [name, klasse] of Object.entries(instrumente)) {
    if (!customElements.get(name)) customElements.define(name, klasse);
  }
}
anmelden();

export { Drehregler, Kippschalter, Leuchte, Regler, Schieber, Taster, Wahl, type Leuchtzustand, type Stellung } from "./regler";
export { anzeigeTakt, beispielsignal, Pegel, Schirm, Segmente, Zeiger, type Pegelart, type Schirmart, type Segmentart, type Signalstand,
         type Taktteilnehmer, type Zeigerart } from "./anzeigen";
export { Wert, zahl, type Einheit, type Kurve, type WertOptionen } from "./wert";
export { bedienen, eingabeMelden, type EingabeMeldung, type ReglerZiel } from "./bedienen";
export type { DrehMerkmale, KippMerkmale, Leuchtfarbe, LeuchteMerkmale, PegelMerkmale, ReglerMerkmale, SchieberMerkmale, SchirmMerkmale,
              SegmenteMerkmale, TasterMerkmale, WahlMerkmale, ZeigerMerkmale } from "./typen";
