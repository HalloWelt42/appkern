// Wiedergabe in der Schale. Zwei Regeln, die vor allem am iPhone zählen:
// 1. Immer nur ein Ton auf einmal: beginnt ein Ton- oder Videoelement zu spielen, halten alle anderen der Seite an.
// 2. Kurze Wiedergaben (Abschnitt, Probe, Ergebnis in einer Liste) laufen über einen gemeinsamen Ton, der direkt im
//    Tippen startet und ausdrücklich angehalten wird. Ein erst nach dem Tippen eingefügtes <audio autoplay> bleibt am
//    iPhone stumm, und ein aus der Seite entferntes Tonelement spielt dort weiter, ohne dass es jemand anhalten kann.

class Einzelton {
  /** Was gerade spielt (Kennung, die die App vergibt), sonst null. */
  kennung = $state<string | null>(null);
  #ton: HTMLAudioElement | null = null;

  /** Spielt `adresse` unter `kennung`; spielt dieselbe Kennung schon, hält es an. Im Klick aufrufen. */
  umschalten(kennung: string, adresse: string): void {
    if (this.kennung === kennung) this.anhalten();
    else this.spielen(kennung, adresse);
  }

  spielen(kennung: string, adresse: string): void {
    const ton = this.#element();
    ton.src = adresse;
    this.kennung = kennung;
    ton.play().catch(() => {
      if (this.kennung === kennung) this.kennung = null;
    });
  }

  anhalten(): void {
    this.#ton?.pause();
    this.kennung = null;
  }

  #element(): HTMLAudioElement {
    if (this.#ton) return this.#ton;
    const ton = document.createElement("audio");
    ton.preload = "auto";
    ton.hidden = true;
    ton.addEventListener("ended", () => (this.kennung = null));
    ton.addEventListener("pause", () => (this.kennung = null));
    document.body.append(ton);        // im Dokument, damit auch er unter "nur ein Ton" fällt
    return (this.#ton = ton);
  }
}

export const einzelton = new Einzelton();

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
