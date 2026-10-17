// Wo man in der App ist, als echter Pfad in der Adresse (/transkripte/<kennung>), damit Links, Lesezeichen und
// Zurück und Vor im Browser funktionieren. Der erste Teil wählt den Bereich (`seite`), die übrigen (`teile`) lesen die
// Seiten selbst. Das Backend liefert für jeden Pfad außerhalb von /api die Oberfläche aus. Alte Anker (#/seite)
// werden beim Start in Pfade umgeschrieben.
import { vielleichtNeuLaden } from "./fassung.svelte";

// `titel`: setzt eine Seite, die einen Teil zeigt (etwa ein Transkript), für den Kopf am Telefon; jeder Ortswechsel
// leert ihn wieder.
export const navigation = $state<{ seite: string; teile: string[]; titel: string }>({ seite: "", teile: [], titel: "" });

function zerlegen(pfad: string): string[] {
  return pfad
    .split("/")
    .filter(Boolean)
    .map((t) => {
      try {
        return decodeURIComponent(t);
      } catch {
        return t;
      }
    });
}

function lesen(): void {
  const [seite = "", ...teile] = zerlegen(location.pathname);
  if (seite !== navigation.seite || teile.join("/") !== navigation.teile.join("/")) navigation.titel = "";
  navigation.seite = seite;
  navigation.teile = teile;
}

export function adresse(ziel: string): string {
  return "/" + zerlegen(ziel).map(encodeURIComponent).join("/");
}

function zurueckVor(): void {
  lesen();
  vielleichtNeuLaden("seitenwechsel");
}

export function navigationStarten(): () => void {
  if (location.hash.startsWith("#/")) history.replaceState(null, "", adresse(decodeURIComponent(location.hash.slice(2))));
  lesen();
  addEventListener("popstate", zurueckVor);
  return () => removeEventListener("popstate", zurueckVor);
}

// Zu einem Ort gehen ("transkripte" oder "transkripte/<kennung>"); `ersetzen` legt keinen neuen Eintrag in den
// Verlauf (etwa wenn eine Seite ihre Adresse nur genauer macht).
export function gehe(ziel: string, ersetzen = false): void {
  const neu = adresse(ziel);
  if (neu !== location.pathname) {
    if (ersetzen) history.replaceState(null, "", neu);
    else history.pushState(null, "", neu);
  }
  lesen();
  if (!ersetzen) vielleichtNeuLaden("seitenwechsel");
}
