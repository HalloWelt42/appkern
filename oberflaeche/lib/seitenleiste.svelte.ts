// Seitenleiste des Leitstands: breit mit Namen oder schmal als Symbolleiste. Ohne Wahl richtet sie sich nach der
// Breite des Fensters (bis 1240 Pixel schmal); wer umschaltet, wählt für dieses Gerät, gemerkt im Browser. Wirksam über
// das Merkmal data-seitenleiste an der Wurzel ("schmal" oder "breit"), auf das leitstand.css hört; Apps ohne diesen
// Baustein behalten das Einklappen nach der Breite allein.
const SCHLUESSEL = "appkern_seitenleiste";
const ENG = "(max-width: 1240px)";

export type Seitenwahl = "breite" | "auf" | "zu";

export const seitenleiste = $state<{ wahl: Seitenwahl; schmal: boolean }>({ wahl: "breite", schmal: false });

function anwenden(): void {
  seitenleiste.schmal = seitenleiste.wahl === "zu" || (seitenleiste.wahl === "breite" && matchMedia(ENG).matches);
  document.documentElement.dataset.seitenleiste = seitenleiste.schmal ? "schmal" : "breit";
}

/** Einmal beim Start der Oberfläche: liest die Wahl dieses Geräts und folgt danach der Breite des Fensters */
export function seitenleisteStarten(): void {
  try {
    const wahl = localStorage.getItem(SCHLUESSEL);
    if (wahl === "auf" || wahl === "zu") seitenleiste.wahl = wahl;
  } catch {
    // ohne Speicher gilt die Breite
  }
  anwenden();
  matchMedia(ENG).addEventListener("change", anwenden);
}

/** Klappt ein oder aus und merkt die Wahl auf diesem Gerät */
export function seitenleisteUmschalten(): void {
  seitenleiste.wahl = seitenleiste.schmal ? "auf" : "zu";
  try {
    localStorage.setItem(SCHLUESSEL, seitenleiste.wahl);
  } catch {
    // gilt dann bis zum Neuladen
  }
  anwenden();
}
