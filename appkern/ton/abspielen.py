"""Abspielfassungen: der Spieler spielt nie das Original, sondern eine von der Tonarbeit dekodierte PCM-WAV (44,1 kHz,
mono, 16 Bit) derselben Quelle, aus der auch der Hördienst seinen Ton bekommt (am besten in derselben Aufbereitung,
siehe `uebernehmen`). So laufen Wortzeiten und Wiedergabe ohne
Versatz: WAV springt im Browser samplegenau, MP3 mit variabler Bitrate oder Aufnahmen aus dem Browser (WebM ohne
Index) nicht. Bewährtes Verfahren der alten txt2voice (dieselben ffmpeg-Parameter).

Die Fassungen sind abgeleitet und jederzeit neu erzeugbar; sie liegen darum nicht in der Kellerwolke, sondern im
Zwischenspeicher der App (etwa `daten/abspielen`), je Quelle und Stand eine Datei, daneben ihre Wellenform. Wird der Speicher
voller als erlaubt, gehen die am längsten nicht gespielten zuerst.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from uuid import UUID

from appkern.kellerwolke import Kellerwolke, Knoten

from .arbeit import Aufbereiten, Ausgabe, Messen, Tonarbeit
from .ton import ABSPIELEN

WELLE_PUNKTE = 800


class Abspielfassungen:
    def __init__(self, ordner: Path, arbeit: Callable[[], Tonarbeit], hoechstens_gb: Callable[[], float]) -> None:
        self.ordner = ordner
        self._arbeit = arbeit
        self._hoechstens_gb = hoechstens_gb
        self._sperren: dict[str, asyncio.Lock] = {}

    def pfad(self, quelle: Knoten) -> Path:
        return self.ordner / f"{quelle.id}-{quelle.etag or 'ohne'}.wav"

    def vorhanden(self, quelle: Knoten) -> Path | None:
        p = self.pfad(quelle)
        return p if p.is_file() else None

    async def aus_datei(self, quelle: Knoten, roh: Path) -> Path:
        """Aus einer schon geholten Originaldatei."""
        async with self._sperre(quelle):
            if (p := self.vorhanden(quelle)) is not None:
                return p
            return await self._erzeugen(quelle, roh)

    async def uebernehmen(self, quelle: Knoten, fassung: Path, wellenform: list[int] | None) -> Path:
        """Eine schon erzeugte Fassung (Ausgabe ABSPIELEN derselben Aufbereitung, etwa beim Transkribieren) an ihren
        Platz; die Wellenform dazu, wenn sie mitkam."""
        async with self._sperre(quelle):
            self._fruehere_weg(quelle)
            ziel = self.pfad(quelle)
            fassung.replace(ziel)
            if wellenform is not None:
                ziel.with_suffix(".welle.json").write_text(json.dumps(wellenform))
            self.aufraeumen()
            return ziel

    async def holen(self, quelle: Knoten, kw: Kellerwolke) -> Path:
        """Die Fassung zur Quelle; fehlt sie, wird das Original geholt und gewandelt."""
        async with self._sperre(quelle):
            if (p := self.vorhanden(quelle)) is not None:
                os.utime(p)                          # zuletzt gespielt: bleibt beim Aufräumen länger
                return p
            self.ordner.mkdir(parents=True, exist_ok=True)
            roh = self.ordner / f".{quelle.id}.roh{PurePosixPath(quelle.name).suffix.lower() or '.bin'}"
            try:
                await kw.herunterladen(quelle.id, roh)
                return await self._erzeugen(quelle, roh)
            finally:
                roh.unlink(missing_ok=True)

    async def wellenform(self, quelle: Knoten, kw: Kellerwolke) -> list[int]:
        """Lautstärke für den Spieler, aus der Abspielfassung (eine Quelle für jede Ansicht, auch ohne Transkript)."""
        merker = self.pfad(quelle).with_suffix(".welle.json")
        if merker.is_file():
            return json.loads(merker.read_text())
        fassung = await self.holen(quelle, kw)
        erg = await self._arbeit().aufbereiten(fassung, Aufbereiten(messen=Messen(wellenform=WELLE_PUNKTE)), [],
                                               titel="Wellenform", prioritaet="hintergrund")
        werte = erg.messwerte.wellenform or []
        merker.write_text(json.dumps(werte))
        return werte

    def vergessen(self, quelle_id: UUID | str) -> None:
        """Fassungen und Wellenformen einer Quelle entfernen (etwa wenn die Aufnahme in den Papierkorb geht)."""
        for p in [*self.ordner.glob(f"{quelle_id}-*.wav"), *self.ordner.glob(f"{quelle_id}-*.welle.json")]:
            p.unlink(missing_ok=True)

    def _sperre(self, quelle: Knoten) -> asyncio.Lock:
        return self._sperren.setdefault(str(quelle.id), asyncio.Lock())

    def _fruehere_weg(self, quelle: Knoten) -> None:
        self.ordner.mkdir(parents=True, exist_ok=True)
        for alt in [*self.ordner.glob(f"{quelle.id}-*.wav"), *self.ordner.glob(f"{quelle.id}-*.welle.json")]:
            alt.unlink(missing_ok=True)

    async def _erzeugen(self, quelle: Knoten, roh: Path) -> Path:
        self._fruehere_weg(quelle)
        ziel = self.pfad(quelle)
        erg = await self._arbeit().aufbereiten(roh, Aufbereiten(ausgaben=[Ausgabe(format=ABSPIELEN)],
                                                                messen=Messen(wellenform=WELLE_PUNKTE)),
                                               [ziel], titel=f"Abspielfassung {quelle.name}")
        ziel.with_suffix(".welle.json").write_text(json.dumps(erg.messwerte.wellenform or []))
        self.aufraeumen()
        return ziel

    def aufraeumen(self) -> None:
        if not self.ordner.is_dir():
            return
        grenze = self._hoechstens_gb() * 1024 ** 3
        dateien = sorted((p for p in self.ordner.glob("*.wav")), key=lambda p: p.stat().st_mtime)
        summe = sum(p.stat().st_size for p in dateien)
        jetzt = time.time()
        for p in dateien[:-1]:                       # die neueste bleibt immer
            if summe <= grenze:
                break
            if jetzt - p.stat().st_mtime < 60:       # gerade erst erzeugt oder gespielt
                continue
            summe -= p.stat().st_size
            p.unlink(missing_ok=True)
            p.with_suffix(".welle.json").unlink(missing_ok=True)
