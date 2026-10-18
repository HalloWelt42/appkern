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
