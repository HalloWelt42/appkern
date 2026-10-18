// Immer nur ein Ton auf einmal: beginnt ein Ton- oder Videoelement zu spielen, halten alle anderen der Seite an. Gilt
// für jede App der Schale; Spieler, Abschnitt und Probe laufen so nie übereinander.
export function nurEinTon(): () => void {
  const beimSpielen = (e: Event) => {
    const quelle = e.target;
    if (!(quelle instanceof HTMLMediaElement)) return;
    for (const m of document.querySelectorAll<HTMLMediaElement>("audio, video")) {
      if (m !== quelle && !m.paused) m.pause();
    }
  };
  document.addEventListener("play", beimSpielen, true);      // "play" steigt nicht auf: nur im Einfangen sichtbar
  return () => document.removeEventListener("play", beimSpielen, true);
}
