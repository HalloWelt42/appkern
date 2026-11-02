/*
 * Eine Sitzung des Debuggers: der aufgezeichnete Lauf, der Code, aus dem er stammt, und wie aufgezeichnet wird. Die
 * Sitzung kennt keine Schnittstelle; wer sie startet, gibt die Funktion mit, die einen Lauf aufzeichnet (Codeschmiede:
 * die Aufgabe mit ihrer Eingabe, Nachschlag: der Probelauf über die Codeschmiede). Ändert sich der Code danach, ist die
 * Aufzeichnung veraltet; "neu" zeichnet auf dieselbe Weise noch einmal auf. Die Haltepunkte gehören dem Editor und
 * überdauern die Sitzung.
 */
import type { Debuglauf } from "../aufzeichnung";

/** zeichnet den Lauf eines Codes auf; ein Fehler (etwa nicht erreichbar) wird zur Meldung der Sitzung */
export type Aufzeichner = (code: string) => Promise<Debuglauf>;

export class DebugSitzung {
  lauf = $state<Debuglauf | null>(null);
  /** Code, aus dem der Lauf stammt */
  code = $state("");
  /** Aufruf wie im Probelauf, etwa nur_gerade([1, 2]); bei Programmen null */
  aufruf = $state<string | null>(null);
  laeuft = $state(false);
  fehler = $state<string | null>(null);
  haltepunkte = $state<number[]>([]);
  /** zählt die Läufe; ein neuer beginnt am ersten Haltepunkt */
  nummer = $state(0);
  private aufzeichner: Aufzeichner | null = null;

  get aktiv(): boolean {
    return this.lauf !== null || this.laeuft || this.fehler !== null;
  }

  veraltet(code: string): boolean {
    return this.lauf !== null && code !== this.code;
  }

  async starten(code: string, aufzeichner: Aufzeichner, aufruf: string | null = null): Promise<void> {
    this.aufzeichner = aufzeichner;
    this.aufruf = aufruf;
    await this.neu(code);
  }

  async neu(code: string): Promise<void> {
    if (!this.aufzeichner) return;
    this.laeuft = true;
    this.fehler = null;
    try {
      this.lauf = await this.aufzeichner(code);
      this.code = code;
      this.nummer += 1;
    } catch (e) {
      this.lauf = null;
      this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      this.laeuft = false;
    }
  }

  beenden(): void {
    this.lauf = null;
    this.fehler = null;
  }
}
