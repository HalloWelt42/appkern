// Hilfe jeder App: ein freischwebendes Fenster über der Oberfläche (teile/Hilfe.svelte), gesteuert von genau einem
// Zustand (`hilfe`). Die App bringt ihre Themen als Markdown-Dateien mit Kopf (titel, untertitel, bereich, symbol) und
// meldet sie einmal mit `hilfeThemen` an; Abschnitte heißen `## Überschrift {#anker}` und sind die Ziele der
// Hilfepunkte (teile/Hilfepunkt.svelte) und der Verweise `[Text](hilfe:thema/anker)`. Die Suche sucht in allen Themen
// oder nur im gezeigten; gezählt wird Textknoten für Textknoten, genau wie das Fenster markiert. Lage, Größe, Zustand,
// Thema und Abschnitt merkt sich der Browser.
//
// Sicherheit: die Themen sind Dateien der App, mitgebündelt, kein Inhalt von Nutzern; nur darum darf das Fenster ihr
// HTML unverändert zeigen.
import { Marked } from "marked";

export interface HilfeAbschnitt {
  anker: string;
  titel: string;
}

export interface HilfeThema {
  kennung: string;
  titel: string;
  untertitel: string;
  bereich: string;
  symbol: string;
  html: string;
  abschnitte: HilfeAbschnitt[];
}

export interface HilfeTreffer {
  thema: string;
  /** der wievielte Treffer im Thema (für die Markierung dort) */
  lokal: number;
}

const SCHLUESSEL = "appkern_hilfe";
const ANKER = /^(.*?)\s*\{#([a-z0-9-]+)\}\s*$/;
const KOPF_HOEHE = 48;

const knoten = new Map<string, string[]>();

/** Trennt den Kopf (--- schluessel: wert ---) vom Rumpf einer Datei */
function kopfUndRumpf(quelle: string): { kopf: Record<string, string>; rumpf: string } {
  const m = quelle.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return { kopf: {}, rumpf: quelle };
  const kopf: Record<string, string> = {};
  for (const zeile of m[1].split(/\r?\n/)) {
    const i = zeile.indexOf(":");
    if (i > 0) kopf[zeile.slice(0, i).trim()] = zeile.slice(i + 1).trim().replace(/^["']|["']$/g, "");
  }
  return { kopf, rumpf: m[2] };
}

/** Ein Thema aus seiner Datei: Abschnitte mit Anker bekommen data-anker, ihre Titel stehen in `abschnitte` */
function thema(kennung: string, quelle: string): HilfeThema {
  const { kopf, rumpf } = kopfUndRumpf(quelle);
  const abschnitte: HilfeAbschnitt[] = [];
  const leser = new Marked({ gfm: true, breaks: false });
  leser.use({
    renderer: {
      heading({ text, depth }) {
        const [, ohne, anker] = text.match(ANKER) ?? [text, text, ""];
        const inhalt = leser.parseInline(ohne) as string;
        if (anker && depth === 2) abschnitte.push({ anker, titel: ohne.replace(/[*_`]/g, "") });
        return `<h${depth}${anker ? ` data-anker="${anker}"` : ""}>${inhalt}</h${depth}>\n`;
      },
    },
  });
  return {
    kennung,
    titel: kopf.titel ?? kennung,
    untertitel: kopf.untertitel ?? "",
    bereich: kopf.bereich ?? "Allgemein",
    symbol: kopf.symbol ?? "fa-circle-info",
    html: leser.parse(rumpf) as string,
    abschnitte,
  };
}

/** Meldet die Themen der App an: Dateien wie aus `import.meta.glob("./hilfe/*.md", { query: "?raw", import: "default",
 *  eager: true })`, die Kennung ist der Dateiname. `reihenfolge` nennt Kennungen in ihrer Folge, der Rest folgt nach
 *  Titel. */
export function hilfeThemen(dateien: Record<string, string>, reihenfolge: string[] = []): void {
  const alle = Object.entries(dateien).map(([pfad, quelle]) => thema(pfad.replace(/^.*\//, "").replace(/\.md$/, ""), quelle));
  const stelle = (t: HilfeThema) => {
    const i = reihenfolge.indexOf(t.kennung);
    return i < 0 ? reihenfolge.length : i;
  };
  knoten.clear();
  hilfe.themen = alle.sort((a, b) => stelle(a) - stelle(b) || a.titel.localeCompare(b.titel, "de"));
}

/** Die Texte der Textknoten eines Themas, einmal aus losgelöstem HTML gelesen: so zählt die Suche genau, was das
 *  Fenster markieren kann */
function texteVon(kennung: string): string[] {
  const da = knoten.get(kennung);
  if (da) return da;
  const t = hilfe.themen.find((x) => x.kennung === kennung);
  if (!t) return [];
  const el = document.createElement("div");
  el.innerHTML = t.html;
  const gaenger = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const texte: string[] = [];
  while (gaenger.nextNode()) texte.push(gaenger.currentNode.nodeValue ?? "");
  knoten.set(kennung, texte);
  return texte;
}

function anzahl(kennung: string, nadel: string): number {
  const n = nadel.toLowerCase();
  let treffer = 0;
  for (const text of texteVon(kennung)) {
    const klein = text.toLowerCase();
    for (let i = klein.indexOf(n); i >= 0; i = klein.indexOf(n, i + n.length)) treffer++;
  }
  return treffer;
}

interface Gemerkt {
  x: number;
  y: number;
  breite: number;
  hoehe: number;
  offen: boolean;
  minimiert: boolean;
  maximiert: boolean;
  thema: string | null;
  anker: string | null;
}

function gemerkt(): Partial<Gemerkt> {
  try {
    return JSON.parse(localStorage.getItem(SCHLUESSEL) ?? "{}") as Partial<Gemerkt>;
  } catch {
    return {};
  }
}

class Hilfe {
  /** Alle Themen der App in ihrer Folge */
  themen = $state<HilfeThema[]>([]);
  offen = $state(false);
  thema = $state<string | null>(null);
  /** Abschnitt, zu dem das Fenster springt (und der zuletzt gewählte) */
  anker = $state<string | null>(null);
  /** zählt jeden Sprung, damit derselbe Anker ein zweites Mal springt */
  sprung = $state(0);
  suche = $state("");
  bereich = $state<"alle" | "thema">("alle");
  treffer = $state<HilfeTreffer[]>([]);
  nr = $state(0);
  x = $state(0);
  y = $state(0);
  breite = $state(520);
  hoehe = $state(560);
  minimiert = $state(false);
  maximiert = $state(false);
  #eingerichtet = false;

  /** Das gezeigte Thema */
  get aktuell(): HilfeThema | null {
    return this.themen.find((t) => t.kennung === this.thema) ?? this.themen[0] ?? null;
  }

  #einrichten(): void {
    if (this.#eingerichtet) return;
    this.#eingerichtet = true;
    const g = gemerkt();
    this.breite = g.breite ?? this.breite;
    this.hoehe = g.hoehe ?? this.hoehe;
    this.x = g.x ?? Math.max(16, innerWidth - this.breite - 32);
    this.y = g.y ?? Math.max(16, innerHeight - this.hoehe - 72);
    this.minimiert = g.minimiert ?? false;
    this.maximiert = g.maximiert ?? false;
    this.thema = g.thema ?? null;
    this.anker = g.anker ?? null;
  }

  /** Öffnet die Hilfe an einem Thema und Abschnitt (ohne Angabe: wo man zuletzt war) */
  zeigen(thema?: string, anker?: string): void {
    this.#einrichten();
    if (thema) {
      this.thema = thema;
      this.anker = anker ?? null;
      this.suche = "";
      this.#neuSuchen();
    }
    this.offen = true;
    this.minimiert = false;
    this.sprung++;
    this.#merken();
  }

  /** Öffnet ein Thema und sucht darin gleich einen Begriff */
  finden(thema: string, begriff: string): void {
    this.zeigen(thema);
    this.bereich = "thema";
    this.suche = begriff;
    this.#neuSuchen();
  }

  /** Der Knopf Hilfe: auf, wo man zuletzt war, oder zu */
  umschalten(): void {
    if (this.offen) this.schliessen();
    else this.zeigen();
  }

  schliessen(): void {
    this.offen = false;
    this.#merken();
  }

  /** Thema wählen; in laufender Suche über alle Themen zum ersten Treffer dort */
  themaWaehlen(kennung: string): void {
    this.thema = kennung;
    this.anker = null;
    if (this.bereich === "alle" && this.suche.trim()) {
      const i = this.treffer.findIndex((t) => t.thema === kennung);
      if (i >= 0) this.nr = i;
    } else {
      this.suche = "";
      this.#neuSuchen();
    }
    this.sprung++;
    this.#merken();
  }

  abschnittWaehlen(anker: string): void {
    this.anker = anker;
    this.sprung++;
    this.#merken();
  }

  sucheSetzen(text: string): void {
    this.suche = text;
    this.nr = 0;
    this.#neuSuchen();
  }

  bereichSetzen(bereich: "alle" | "thema"): void {
    this.bereich = bereich;
    this.nr = 0;
    this.#neuSuchen();
  }

  naechster(): void {
    if (!this.treffer.length) return;
    this.nr = (this.nr + 1) % this.treffer.length;
    this.#folgen();
  }

  voriger(): void {
    if (!this.treffer.length) return;
    this.nr = (this.nr - 1 + this.treffer.length) % this.treffer.length;
    this.#folgen();
  }

  /** Der aktive Treffer im gezeigten Thema (für die Markierung), sonst -1 */
  aktivLokal(): number {
    const t = this.treffer[this.nr];
    return t && t.thema === this.thema ? t.lokal : -1;
  }

  minimieren(): void {
    this.minimiert = !this.minimiert;
    if (this.minimiert) this.maximiert = false;
    this.#merken();
  }

  maximieren(an = !this.maximiert): void {
    this.maximiert = an;
    if (an) this.minimiert = false;
    else this.einpassen();
    this.#merken();
  }

  /** Hält Lage und Größe ganz im Fenster */
  einpassen(): void {
    this.breite = Math.min(this.breite, Math.max(320, innerWidth - 24));
    this.hoehe = Math.min(this.hoehe, Math.max(240, innerHeight - 24));
    this.x = Math.min(Math.max(0, this.x), Math.max(0, innerWidth - this.breite));
    this.y = Math.min(Math.max(0, this.y), Math.max(0, innerHeight - this.hoehe));
  }

  /** Liegen die Bedienelemente des Fensters nicht mehr ganz im Bild, wird es groß: dort ist alles erreichbar */
  sichtSchuetzen(): void {
    if (!this.offen || this.maximiert) return;
    if (innerWidth < 700) return this.maximieren(true);           // am Telefon immer groß
    const unten = this.minimiert ? this.y + KOPF_HOEHE : this.y + this.hoehe;
    if (this.x < 0 || this.y < 0 || this.x + this.breite > innerWidth || unten > innerHeight) this.maximieren(true);
  }

  verschieben(x: number, y: number): void {
    this.x = Math.min(Math.max(0, x), Math.max(0, innerWidth - this.breite));
    this.y = Math.min(Math.max(0, y), Math.max(0, innerHeight - KOPF_HOEHE));
  }

  groesse(breite: number, hoehe: number): void {
    this.breite = Math.min(Math.max(340, breite), innerWidth - this.x);
    this.hoehe = Math.min(Math.max(240, hoehe), innerHeight - this.y);
  }

  /** Nach Ziehen und Größe ändern */
  fertig(): void {
    this.#merken();
  }

  #neuSuchen(): void {
    const nadel = this.suche.trim();
    const liste: HilfeTreffer[] = [];
    if (nadel) {
      const wo = this.bereich === "alle" ? this.themen.map((t) => t.kennung) : this.thema ? [this.thema] : [];
      for (const kennung of wo) {
        const n = anzahl(kennung, nadel);
        for (let i = 0; i < n; i++) liste.push({ thema: kennung, lokal: i });
      }
    }
    this.treffer = liste;
    if (this.nr >= liste.length) this.nr = 0;
    this.#folgen();
  }

  #folgen(): void {
    const t = this.treffer[this.nr];
    if (t && t.thema !== this.thema) this.thema = t.thema;
  }

  #merken(): void {
    const daten: Gemerkt = {
      x: this.x, y: this.y, breite: this.breite, hoehe: this.hoehe, offen: this.offen, minimiert: this.minimiert,
      maximiert: this.maximiert, thema: this.thema, anker: this.anker,
    };
    try {
      localStorage.setItem(SCHLUESSEL, JSON.stringify(daten));
    } catch {
      // gilt dann nur bis zum Neuladen
    }
  }
}

export const hilfe = new Hilfe();
