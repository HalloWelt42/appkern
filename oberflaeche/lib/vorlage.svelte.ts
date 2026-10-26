// Vorlage des Aussehens: Klassisch (das Grunddesign) oder eine Vorlage aus stil/vorlagen.css. Eine Vorlage ändert das
// ganze Aussehen der Apps im Leitstand, nicht nur Farben, und wirkt nur auf dem Rechner (ab 1000 Pixel, das regeln ihre
// Stile; am Telefon bleibt das Grunddesign). Gewählt je Gerät, gemerkt im Browser, wirksam über das Merkmal
// data-vorlage an der Wurzel. Diese Liste ist die eine Wahrheit der wählbaren Vorlagen: eine neue kommt mit ihren
// Stilen in stil/vorlagen.css und mit ihrem Eintrag hierher. Entwürfe zeigt oberflaeche/mockups/vorlagen.html.
const SCHLUESSEL = "appkern_vorlage";
const GRUNDDESIGN = "klassisch";

export interface Vorlage {
  id: string;
  name: string;
  /** was sie ausmacht, in einem Satz für die Wahl */
  text: string;
  symbol: string;
}

export const VORLAGEN: readonly Vorlage[] = [
  { id: GRUNDDESIGN, name: "Klassisch", text: "Das Grunddesign: ruhig, dicht und überall gleich", symbol: "fa-table-columns" },
  { id: "futur", name: "Futur", text: "Tiefe Flächen, ein leuchtender Akzent, feine Linien und technische Schrift", symbol: "fa-satellite" },
];

export const vorlage = $state<{ wahl: string }>({ wahl: GRUNDDESIGN });

function bekannt(id: string | null): id is string {
  return VORLAGEN.some((v) => v.id === id);
}

function anwenden(): void {
  const wurzel = document.documentElement;
  if (vorlage.wahl === GRUNDDESIGN) delete wurzel.dataset.vorlage;
  else wurzel.dataset.vorlage = vorlage.wahl;
}

/** Einmal beim Start der Oberfläche: liest die Wahl dieses Geräts (eine nicht mehr angebotene gilt als Klassisch) */
export function vorlageStarten(): void {
  try {
    const gemerkt = localStorage.getItem(SCHLUESSEL);
    if (bekannt(gemerkt)) vorlage.wahl = gemerkt;
  } catch {
    // ohne Speicher gilt das Grunddesign
  }
  anwenden();
}

/** Wählt eine Vorlage für dieses Gerät; sie gilt sofort für die ganze Seite */
export function vorlageSetzen(id: string): void {
  if (!bekannt(id)) return;
  vorlage.wahl = id;
  try {
    localStorage.setItem(SCHLUESSEL, id);
  } catch {
    // gilt dann bis zum Neuladen
  }
  anwenden();
}
