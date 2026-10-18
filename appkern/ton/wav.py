"""Datenarbeit an fertigen PCM-WAV-Dateien, ohne Dekodieren und ohne Rechnung (darf auch auf dem Pi laufen): Dauer
aus dem Kopf, ein Zeitbereich als Bytekopie. Alles andere an Ton macht die Tonarbeit (`arbeit.py`)."""

from __future__ import annotations

import wave
from pathlib import Path

from .ton import TonFehler


def dauer(datei: Path) -> float:
    try:
        with wave.open(str(datei), "rb") as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError) as f:
        raise TonFehler(f"Keine PCM-WAV-Datei: {datei.name}") from f


def ausschnitt(datei: Path, beginn_s: float, ende_s: float, ziel: Path) -> Path:
    """Von `beginn_s` bis `ende_s` als eigene WAV-Datei (gleiches PCM), samplegenau; außerhalb wird begrenzt."""
    vorlaeufig = ziel.with_name(f".{ziel.stem}.teil{ziel.suffix}")
    try:
        with wave.open(str(datei), "rb") as q:
            rate, n = q.getframerate(), q.getnframes()
            von = max(0, min(n, round(beginn_s * rate)))
            bis = max(von, min(n, round(ende_s * rate)))
            q.setpos(von)
            daten = q.readframes(bis - von)
            with wave.open(str(vorlaeufig), "wb") as z:
                z.setnchannels(q.getnchannels())
                z.setsampwidth(q.getsampwidth())
                z.setframerate(rate)
                z.writeframes(daten)
    except (wave.Error, EOFError) as f:
        vorlaeufig.unlink(missing_ok=True)
        raise TonFehler(f"Keine PCM-WAV-Datei: {datei.name}") from f
    vorlaeufig.replace(ziel)
    return ziel
