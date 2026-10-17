// Text in die Zwischenablage. Die Schnittstelle des Browsers gibt es nur in sicheren Umgebungen (HTTPS oder dieser
// Rechner); im Heimnetz über http fehlt sie. Dann über ein unsichtbares Textfeld kopieren. Beides muss direkt im
// Klick geschehen, deshalb vorher nichts abwarten.

export async function kopieren(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // weiter mit dem Textfeld
    }
  }
  const feld = document.createElement("textarea");
  feld.value = text;
  feld.setAttribute("readonly", "");
  feld.style.position = "fixed";
  feld.style.opacity = "0";
  feld.style.pointerEvents = "none";
  document.body.appendChild(feld);
  feld.select();
  feld.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  feld.remove();
  return ok;
}

// Den Inhalt eines Elements markieren, damit man ihn selbst kopieren kann.
export function markieren(element: HTMLElement | null | undefined): void {
  if (!element) return;
  const bereich = document.createRange();
  bereich.selectNodeContents(element);
  const auswahl = getSelection();
  auswahl?.removeAllRanges();
  auswahl?.addRange(bereich);
}
