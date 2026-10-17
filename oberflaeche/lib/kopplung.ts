// Koppeln mit einem Code aus der Kellerwolke: Code lesen und zeigen, Art und Namensvorschlag des Geräts.
export const CODE_LAENGE = 8;
const LINK_MARKE = "koppeln=";

export function codeNormal(text: string): string {
  return text.replace(/[^0-9a-z]/gi, "").toUpperCase().slice(0, CODE_LAENGE);
}

// Kam die Seite über einen Koppel-Link (#koppeln=CODE), den Code einmal herausnehmen und aus der Adresse entfernen.
export function codeAusLinkNehmen(): string {
  const marke = location.hash.slice(1);
  if (!marke.startsWith(LINK_MARKE)) return "";
  history.replaceState(null, "", location.pathname + location.search);
  return codeNormal(marke.slice(LINK_MARKE.length));
}

// Als Web-App vom Home-Bildschirm gestartet oder im Browser; auf dem iPhone haben beide getrennte Speicher.
export function geraeteArt(): "webapp" | "browser" {
  const eigen = matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
  return eigen ? "webapp" : "browser";
}

export function namensvorschlag(): string {
  const ua = navigator.userAgent;
  if (/iPad|Tablet/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "Tablet";
  if (/iPhone|Mobile/i.test(ua)) return "Telefon";
  if (/Android/i.test(ua)) return "Tablet";
  return "Rechner";
}
