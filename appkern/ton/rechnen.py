"""Rechnen auf Tonwerten (numpy, Gleitkomma, mono, eine Rate): blenden, Ränder glätten, laute Spanne finden, begrenzen,
an Zeiten legen, Pegelverlauf. Läuft nur dort, wo gerechnet wird (Tondienst auf dem Mac, Tests); die Apps nutzen es über
die Tonarbeit (`arbeit.py`). Die Verfahren stammen aus der Vertonung (Fügen und Referenzsuche, 18.10.2026)."""

from __future__ import annotations

import numpy as np


def blenden(teile: list[np.ndarray], rate: int, blende_ms: float) -> np.ndarray:
    """Hintereinander mit Gleichleistungsblende (cos und sin): die Lautheit bleibt über die Naht gleich."""
    teile = [np.asarray(t, dtype=np.float32) for t in teile if np.asarray(t).size]
    if not teile:
        return np.zeros(0, dtype=np.float32)
    aus = teile[0]
    for t in teile[1:]:
        n = min(int(rate * blende_ms / 1000), aus.size, t.size)
        if n == 0:
            aus = np.concatenate([aus, t])
            continue
        x = np.linspace(0.0, np.pi / 2, n, dtype=np.float32)
        naht = aus[-n:] * np.cos(x) + t[:n] * np.sin(x)
        aus = np.concatenate([aus[:-n], naht, t[n:]])
    return aus.astype(np.float32)


def raender(werte: np.ndarray, rate: int, rand_ms: float) -> np.ndarray:
    """Kurz ein- und ausblenden, damit kein Knacks entsteht."""
    werte = np.array(werte, dtype=np.float32)
    n = min(int(rate * rand_ms / 1000), werte.size // 2)
    if n:
        rampe = np.linspace(0.0, 1.0, n, dtype=np.float32)
        werte[:n] *= rampe
        werte[-n:] *= rampe[::-1]
    return werte


def laute_spanne(werte: np.ndarray, rate: int, schwelle_db: float, rand_ms: float) -> tuple[int, int]:
    """Erster und letzter Wert über der Schwelle, samt kleinem Rand (Indizes, Ende ausschließlich); (0, 0) bei Stille.
    Damit kürzt man Stille am Anfang und Ende, damit Pausen und Zeitlage vom Plan kommen."""
    if werte.size == 0:
        return 0, 0
    laut = np.flatnonzero(np.abs(werte) > 10 ** (schwelle_db / 20))
    if laut.size == 0:
        return 0, 0
    rand = int(rate * rand_ms / 1000)
    return max(0, int(laut[0]) - rand), min(werte.size, int(laut[-1]) + rand + 1)


def spitze(werte: np.ndarray) -> float:
    return float(np.max(np.abs(werte))) if werte.size else 0.0


def begrenzen(werte: np.ndarray, hoechstens: float) -> np.ndarray:
    """Liegt die Spitze darüber, wird das Ganze leiser; nie abgeschnitten, nie verzerrt."""
    hoch = spitze(werte)
    return (werte * (hoechstens / hoch)).astype(np.float32) if hoch > hoechstens else werte


def legen(stuecke: list[tuple[np.ndarray, float]], rate: int, *, mindestens_s: float, rand_ms: float) -> np.ndarray:
    """Jedes Stück mit glatten Rändern an seinen Beginn (Sekunden); mindestens `mindestens_s` lang. Überlappungen
    addieren sich."""
    ende = max([b + w.size / rate for w, b in stuecke] + [mindestens_s])
    aus = np.zeros(int(np.ceil(ende * rate)), dtype=np.float32)
    for werte, beginn in stuecke:
        a = int(round(beginn * rate))
        w = raender(werte, rate, rand_ms)
        aus[a:a + w.size] += w[:max(0, aus.size - a)]
    return aus


class Pegelrechner:
    """Pegelverlauf in festen Rahmen (Effektivwert und Spitze je Rahmen), stückweise gefüttert: so bleibt der Speicher
    auch bei Stunden klein. Ein angefangener letzter Rahmen zählt nicht."""

    def __init__(self, rate: int, rahmen_ms: int) -> None:
        self.n = max(1, int(rate * rahmen_ms / 1000))
        self._rest = np.zeros(0, dtype=np.float32)
        self.rms: list[float] = []
        self.spitzen: list[float] = []

    def fuettern(self, werte: np.ndarray) -> None:
        werte = np.concatenate([self._rest, np.asarray(werte, dtype=np.float32)])
        ganz = werte.size // self.n * self.n
        if ganz:
            rahmen = werte[:ganz].reshape(-1, self.n).astype(np.float64)
            self.rms += np.sqrt(np.mean(rahmen ** 2, axis=1) + 1e-12).tolist()
            self.spitzen += np.max(np.abs(rahmen), axis=1).tolist()
        self._rest = werte[ganz:]


class Klangrechner:
    """Klang einer Datei (Plattenschrank, PLAT-2): echte Bandbreite, Übersteuerung, Dynamik und Aussetzer, stückweise
    gefüttert wie der Pegelrechner. Die Bitrate sagt nur, was übertragen wurde; eine hochgerechnete Datei bricht im
    Spektrum dort ab, wo ihre Vorlage abbrach, ein Aussetzer ist digitale Stille mitten im Titel.

    - Bandbreite: gemitteltes Leistungsspektrum (Fenster `fft`, Hann), höchste Frequenz, deren geglätteter Pegel nicht
      mehr als `abstand_db` unter dem Bezug (Mittel von 1 bis 6 kHz) liegt.
    - Übersteuerung: Anteil der Werte in Läufen von mindestens `lauf` Werten am Anschlag (`anschlag`).
    - Dynamik: Abstand zwischen dem 95. und dem 10. Perzentil der Effektivwerte in Rahmen von `rahmen_ms`, ohne Stille.
    - Aussetzer: Stille unter `still_db` ab `aussetzer_s`, nicht in den ersten und letzten `rand_s`.
    """

    def __init__(self, rate: int, *, fft: int = 4096, abstand_db: float = 50.0, glaettung_hz: float = 300.0,
                 anschlag: float = 0.999, lauf: int = 3, rahmen_ms: int = 400, still_db: float = -70.0,
                 aussetzer_s: float = 0.3, rand_s: float = 1.0) -> None:
        self.rate, self.fft, self.abstand_db, self.glaettung_hz = rate, fft, abstand_db, glaettung_hz
        self.anschlag, self.lauf = anschlag, lauf
        self.rahmen = max(1, int(rate * rahmen_ms / 1000))
        self.still = 10 ** (still_db / 20)
        self.aussetzer_n, self.rand_n = int(rate * aussetzer_s), int(rate * rand_s)
        self._fenster = np.hanning(fft).astype(np.float64)
        self._spektrum = np.zeros(fft // 2 + 1)
        self._spektren = 0
        self._rest = np.zeros(0, dtype=np.float32)
        self._rms: list[float] = []
        self._am_anschlag = 0
        self._lauf_jetzt = 0
        self._still_seit: int | None = None
        self._stillen: list[tuple[int, int]] = []
        self.gezaehlt = 0

    def fuettern(self, werte: np.ndarray) -> None:
        werte = np.asarray(werte, dtype=np.float32)
        self._anschlag_zaehlen(werte)
        self._stille_verfolgen(werte)
        self.gezaehlt += werte.size
        alles = np.concatenate([self._rest, werte])
        ganz = alles.size // self.fft * self.fft
        if ganz:
            stuecke = alles[:ganz].reshape(-1, self.fft).astype(np.float64)
            self._spektrum += np.sum(np.abs(np.fft.rfft(stuecke * self._fenster, axis=1)) ** 2, axis=0)
            self._spektren += stuecke.shape[0]
            rahmen = alles[:ganz // self.rahmen * self.rahmen].reshape(-1, self.rahmen) if ganz >= self.rahmen else None
            if rahmen is not None:
                self._rms += np.sqrt(np.mean(rahmen.astype(np.float64) ** 2, axis=1) + 1e-12).tolist()
        self._rest = alles[ganz:]

    def _anschlag_zaehlen(self, werte: np.ndarray) -> None:
        """Läufe am Anschlag zählen; ein Lauf kann über die Grenze zum vorigen Block reichen (`_lauf_jetzt`)."""
        am = np.abs(werte) >= self.anschlag
        kante = np.diff(np.concatenate([[0], am.astype(np.int8), [0]]))
        anfaenge, enden = np.flatnonzero(kante == 1), np.flatnonzero(kante == -1)
        uebertrag = self._lauf_jetzt
        self._lauf_jetzt = 0
        for a, e in zip(anfaenge, enden):
            davor = uebertrag if a == 0 else 0
            if e - a + davor >= self.lauf:
                # der Teil aus dem vorigen Block zählt jetzt mit, wenn er dort allein zu kurz war
                self._am_anschlag += e - a + (davor if davor < self.lauf else 0)
            if e == werte.size:
                self._lauf_jetzt = e - a + davor

    def _stille_verfolgen(self, werte: np.ndarray) -> None:
        """Stille Strecken als (Anfang, Ende) in Werten seit Beginn; eine Strecke kann über Blockgrenzen reichen."""
        start = self.gezaehlt
        laut = np.flatnonzero(np.abs(werte) >= self.still)
        if laut.size == 0:
            if self._still_seit is None:
                self._still_seit = start
            return
        if self._still_seit is not None:
            self._stillen.append((self._still_seit, start + int(laut[0])))
            self._still_seit = None
        elif laut[0] > 0:
            self._stillen.append((start, start + int(laut[0])))
        for i in np.flatnonzero(np.diff(laut) > self.aussetzer_n):
            self._stillen.append((start + int(laut[i]) + 1, start + int(laut[i + 1])))
        if laut[-1] < werte.size - 1:
            self._still_seit = start + int(laut[-1]) + 1

    def bandbreite_hz(self) -> float | None:
        if not self._spektren:
            return None
        db = 10 * np.log10(self._spektrum / self._spektren + 1e-20)
        hz = np.fft.rfftfreq(self.fft, 1 / self.rate)
        breite = max(1, int(self.glaettung_hz / (hz[1] - hz[0])))
        # an den Rändern mit dem Randwert fortsetzen: Nullen wären hier 0 dB, also laut, und täuschten Bandbreite vor
        halb = breite // 2
        glatt = np.convolve(np.pad(db, (halb, breite - 1 - halb), mode="edge"), np.ones(breite) / breite, mode="valid")
        bezug = glatt[(hz >= 1000) & (hz <= 6000)]
        if bezug.size == 0:
            return None
        ueber = np.flatnonzero(glatt >= np.mean(bezug) - self.abstand_db)
        return float(hz[ueber[-1]]) if ueber.size else 0.0

    def uebersteuert_anteil(self) -> float:
        return self._am_anschlag / self.gezaehlt if self.gezaehlt else 0.0

    def dynamik_db(self) -> float | None:
        rms = np.asarray(self._rms)
        laut = rms[rms > self.still]
        if laut.size < 3:
            return None
        db = 20 * np.log10(laut)
        return float(np.percentile(db, 95) - np.percentile(db, 10))

    def aussetzer(self) -> list[tuple[float, float]]:
        """Stille Stellen mitten im Titel (Sekunden); Ränder und kurze Pausen zählen nicht."""
        ende = self.gezaehlt
        return [(a / self.rate, b / self.rate) for a, b in self._stillen
                if b - a >= self.aussetzer_n and a >= self.rand_n and b <= ende - self.rand_n]
