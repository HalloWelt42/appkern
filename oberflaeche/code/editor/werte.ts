/*
 * Werte beim Überfahren (Nachschlag WIKI-53): steht der Debugger auf einem Schritt, zeigt der Editor beim Überfahren
 * eines Namens dessen Wert in diesem Schritt, zuerst aus dem innersten Rahmen, sonst aus den äußeren (dann mit dem
 * Rahmen dazu). Bei PHP gehört das $ zum Namen. Die Komponente setzt die Rahmen mit werteSetzen; null nimmt sie weg
 * (kein Lauf, oder der Code passt nicht mehr zum Lauf). Aussehen im Farbschema des Editors (schema.ts).
 */
import { StateEffect, StateField } from "@codemirror/state";
import { EditorView, hoverTooltip, type Tooltip } from "@codemirror/view";
import type { Rahmen, Wert } from "../aufzeichnung";

/** so viele Einträge zeigt das Feld; alle stehen im Speicherbild */
const HOECHSTENS = 12;

const ARTEN: Record<Wert["art"], string> = {
  zahl: "Zahl", text: "Text", wahrheit: "Wahrheitswert", nichts: "nichts", liste: "Liste", tupel: "Tupel", menge: "Menge",
  woerterbuch: "Wörterbuch", funktion: "Funktion", klasse: "Klasse", objekt: "Objekt", sonst: "",
};

const setzen = StateEffect.define<readonly Rahmen[] | null>();

const rahmenFeld = StateField.define<readonly Rahmen[] | null>({
  create: () => null,
  update: (rahmen, tr) => tr.effects.reduce<readonly Rahmen[] | null>((r, e) => (e.is(setzen) ? e.value : r), rahmen),
});

export function werteSetzen(view: EditorView, rahmen: readonly Rahmen[] | null): void {
  if (view.state.field(rahmenFeld, false) !== rahmen) view.dispatch({ effects: setzen.of(rahmen) });
}

interface Fund {
  name: string;
  wert: Wert;
  /** Rahmen, aus dem der Wert stammt, wenn es nicht der innerste ist */
  aussen: Rahmen | null;
}

function finden(rahmen: readonly Rahmen[], namen: readonly string[]): Fund | null {
  for (let n = rahmen.length - 1; n >= 0; n--) {
    for (const name of namen) {
      if (Object.hasOwn(rahmen[n].variablen, name)) {
        return { name, wert: rahmen[n].variablen[name], aussen: n === rahmen.length - 1 ? null : rahmen[n] };
      }
    }
  }
  return null;
}

function teil(tag: string, klasse: string, text = ""): HTMLElement {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  el.textContent = text;
  return el;
}

/** Einträge eines Werts als Paare (Index, Schlüssel oder Attribut und Wert); null bei einfachen Werten */
function eintraege(w: Wert): [string, string][] | null {
  if (w.elemente) return w.elemente.map((e, i) => [w.art === "menge" ? "" : String(i), e.darstellung]);
  if (w.paare) return w.paare.map(([k, v]) => [k.darstellung, v.darstellung]);
  if (w.attribute) return Object.entries(w.attribute).map(([a, v]) => [a, v.darstellung]);
  return null;
}

function feld({ name, wert, aussen }: Fund): HTMLElement {
  const zeilen = eintraege(wert);
  const dom = teil("div", "cm-wert");
  const art = [ARTEN[wert.art], zeilen && wert.art !== "objekt" ? `(${zeilen.length}${wert.gekuerzt ? "+" : ""})` : "",
               aussen ? (aussen.name === "Modul" ? "im Hauptprogramm" : `in ${aussen.name}()`) : ""].filter(Boolean).join(" ");
  const kopf = teil("div", "cm-wert-kopf");
  kopf.append(teil("b", "", name), teil("span", "", art));
  dom.append(kopf);
  if (!zeilen || wert.art === "objekt") dom.append(teil("div", "cm-wert-inhalt", wert.darstellung));
  if (zeilen?.length) {
    const liste = teil("div", "cm-wert-zeilen");
    for (const [schluessel, inhalt] of zeilen.slice(0, HOECHSTENS)) liste.append(teil("span", "", schluessel), teil("span", "", inhalt));
    dom.append(liste);
  }
  if (zeilen && (zeilen.length > HOECHSTENS || wert.gekuerzt)) dom.append(teil("div", "cm-wert-rest", "mehr im Speicherbild"));
  return dom;
}

const anzeige = hoverTooltip((view, pos): Tooltip | null => {
  const rahmen = view.state.field(rahmenFeld);
  const wort = rahmen?.length ? view.state.wordAt(pos) : null;
  if (!rahmen || !wort) return null;
  const doc = view.state.doc;
  const davor = doc.sliceString(Math.max(0, wort.from - 2), wort.from);
  if (davor.endsWith(".") || davor === "->") return null;            // Attribut eines Objekts, keine Variable
  const name = doc.sliceString(wort.from, wort.to);
  const mitDollar = !name.startsWith("$") && davor.endsWith("$");
  const fund = finden(rahmen, mitDollar ? [`$${name}`, name] : [name]);
  if (!fund) return null;
  return { pos: mitDollar ? wort.from - 1 : wort.from, end: wort.to, above: true, create: () => ({ dom: feld(fund) }) };
});

/** Für erstelleEditor: das Feld mit den Rahmen und die Anzeige beim Überfahren */
export const werteAnzeige = [rahmenFeld, anzeige];
