// Vorlauf beim Vorlesen (HELF-34, Nutzer: "mit leichtem Vorlauf für flüssiges Vorlesen, bei Auslastung des Rechners mehr
// Vorlauf einplanen"). Der Vorleser spielt erst, wenn so viele Sekunden Ton bereitliegen, wie der Vorlauf verlangt, oder
// der Text zu Ende gesprochen ist. Wie ausgelastet der Sprechdienst ist, wird gemessen statt geraten: kommt der Ton
// schneller als Echtzeit, reicht der kleine Vorlauf; kommt er langsamer, wächst der Vorlauf mit dem Abstand. Reißt der
// Ton trotzdem ab (der nächste Satz war nicht rechtzeitig da), wartet der Vorleser, bis wieder genug da ist, und merkt
// sich den größeren Vorlauf für das nächste Mal; ein Lauf ohne Abriss nimmt ihn langsam wieder zurück.

/** Kleinster Vorlauf in Sekunden Ton (ein kurzer Satz), auch ohne Last */
export const VORLAUF_MIN_S = 1.5;
/** Größter Vorlauf: länger wartet niemand gern auf den ersten Ton */
export const VORLAUF_MAX_S = 20;
/** So viel schneller als Echtzeit gilt der Sprechdienst als frei (dann genügt der kleinste Vorlauf) */
const FREI_FAKTOR = 1.5;

export class Vorlauf {
  /** Gemerkter Vorlauf aus den letzten Läufen (wächst nach einem Abriss, sinkt nach Läufen ohne) */
  gemerktS = VORLAUF_MIN_S;
  #beginn = 0;
  #tonS = 0;
  #abriss = false;

  /** Ein neuer Lauf beginnt (die Anfrage geht gerade los); `jetzt` in Sekunden */
  beginnen(jetzt: number): void {
    this.#beginn = jetzt;
    this.#tonS = 0;
    this.#abriss = false;
  }

  /** Ein Satz ist angekommen: so viele Sekunden Ton */
  angekommen(dauerS: number): void {
    this.#tonS += dauerS;
  }

  /** Wie schnell der Sprechdienst liefert: Sekunden Ton je Sekunde Wartezeit (über 1: schneller als Echtzeit) */
  tempo(jetzt: number): number {
    const vergangen = Math.max(0.001, jetzt - this.#beginn);
    return this.#tonS / vergangen;
  }

  /** Der Vorlauf für diesen Augenblick: der gemerkte, bei langsamem Sprechdienst mehr (je langsamer, desto mehr) */
  noetigS(jetzt: number): number {
    const t = this.tempo(jetzt);
    const last = t >= FREI_FAKTOR ? 1 : FREI_FAKTOR / Math.max(t, 0.1);
    return Math.min(VORLAUF_MAX_S, Math.max(VORLAUF_MIN_S, this.gemerktS * last));
  }

  /** Darf es losgehen? Genug Ton bereit (`bereitS`) oder der Text ist zu Ende gesprochen */
  genug(bereitS: number, jetzt: number, fertig: boolean): boolean {
    return fertig || bereitS >= this.noetigS(jetzt);
  }

  /** Der Ton ist abgerissen: der nächste Satz kam zu spät. Mehr Vorlauf, für jetzt und für das nächste Mal */
  abgerissen(): void {
    this.#abriss = true;
    this.gemerktS = Math.min(VORLAUF_MAX_S, this.gemerktS * 1.5 + 1);
  }

  /** Der Lauf ist zu Ende: ohne Abriss sinkt der gemerkte Vorlauf langsam wieder */
  beenden(): void {
    if (!this.#abriss) this.gemerktS = Math.max(VORLAUF_MIN_S, this.gemerktS * 0.8);
  }
}
