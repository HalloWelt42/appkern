"""Ton mit ffmpeg: Eigenschaften messen, in ein genau beschriebenes Format wandeln, Dauer, Sprechpausen, Ausschneiden,
Wellenform; Ton als Gleitkommawerte lesen, bearbeiten (stauchen) und genau einmal in ein Zielformat schreiben.

Formate sind ein Modell (`Tonformat`), keine verstreuten Schalter: Abtastrate, Kanäle, Kodierung (Codec von ffmpeg) und
bei verlustbehafteten die Bitrate. Gewandelt wird mit dem besten verfügbaren Resampler: soxr, wenn ffmpeg ihn hat (Pi,
Container), sonst der eingebaute mit hohen Qualitätseinstellungen (Homebrew auf dem Mac); welcher, wird einmal gemessen
und ist abfragbar. Jede Ausgabe entsteht erst vollständig unter einem Zwischennamen und rückt dann an ihren Platz.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SUCHORTE = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")
WELLE_DB = 60.0  # so viele Dezibel unter Vollaussteuerung ist die Wellenform leer (wie der Pegel beim Aufnehmen)
_STILLE_BEGINN = re.compile(r"silence_start: (-?[0-9.]+)")
_STILLE_ENDE = re.compile(r"silence_end: (-?[0-9.]+)")
# Resampler: soxr in höchster Präzision; der eingebaute mit langem Filter, falls soxr fehlt
_SOXR = "resampler=soxr:precision=28"
_SWR = "resampler=swr:filter_size=64:phase_shift=10:linear_interp=1:cutoff=0.97"
MP4_ENDUNGEN = (".m4a", ".mp4", ".m4b", ".mov")    # Behälter mit Inhaltsverzeichnis (moov), das vorn stehen soll


class TonFehler(Exception):
    """ffmpeg fehlt oder konnte die Datei nicht lesen oder schreiben."""


class Tonformat(BaseModel):
    """Ziel einer Wandlung. `kodierung` ist der Codec von ffmpeg (pcm_s16le, pcm_f32le, flac, libmp3lame, aac,
    libopus); der Behälter folgt aus der Endung der Zieldatei."""

    model_config = ConfigDict(frozen=True)
    rate: int = Field(ge=8000, le=192000)
    kanaele: int = Field(ge=1, le=8)
    kodierung: str = Field(min_length=2)
    bitrate: str | None = Field(None, pattern=r"^\d+k$", description="nur für verlustbehaftete, etwa 192k")


HOEREN = Tonformat(rate=16000, kanaele=1, kodierung="pcm_s16le")       # was Spracherkennung erwartet
ARBEIT = Tonformat(rate=24000, kanaele=1, kodierung="pcm_f32le")       # Sprachausgabe: Rate der Sprachmodelle, Gleitkomma
ABSPIELEN = Tonformat(rate=44100, kanaele=1, kodierung="pcm_s16le")    # samplegenau springbar im Browser


class Eigenschaften(BaseModel):
    """Gemessen mit ffprobe (erste Tonspur)."""

    dauer_s: float
    rate: int | None = None
    kanaele: int | None = None
    kodierung: str | None = None
    bits: int | None = None
    bitrate: int | None = None
    behaelter: str | None = None
    hat_video: bool = False

    def als_format(self, kodierung: str | None = None, bitrate: str | None = None) -> Tonformat:
        """Das Format dieser Datei als Ziel (zum Zurückwandeln in die Form der Quelle)."""
        if self.rate is None or self.kanaele is None:
            raise TonFehler("Die Datei hat keine Tonspur")
        return Tonformat(rate=self.rate, kanaele=self.kanaele, kodierung=kodierung or self.kodierung or "pcm_s16le",
                         bitrate=bitrate)


class Pause(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: float
    ende: float

    @property
    def mitte(self) -> float:
        return (self.start + self.ende) / 2

    @property
    def laenge(self) -> float:
        return self.ende - self.start


def programm(name: str, eingestellt: str = "") -> str:
    """Pfad zu ffmpeg oder ffprobe: eingestellt, sonst im Suchpfad, sonst an den üblichen Orten."""
    if eingestellt:
        kandidat = Path(eingestellt).expanduser()
        kandidat = kandidat.with_name(name) if kandidat.name in ("ffmpeg", "ffprobe") else kandidat / name
        if kandidat.is_file():
            return str(kandidat)
    gefunden = shutil.which(name) or next((f"{o}/{name}" for o in SUCHORTE if Path(o, name).is_file()), None)
    if not gefunden:
        raise TonFehler(f"{name} nicht gefunden (in den Einstellungen den Ordner von ffmpeg eintragen)")
    return gefunden


async def _ausfuehren(*befehl: str) -> tuple[str, str]:
    prozess = await asyncio.create_subprocess_exec(*befehl, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        aus, fehler = await prozess.communicate()
    except asyncio.CancelledError:
        prozess.kill()
        await prozess.wait()
        raise
    if prozess.returncode != 0:
        letzte = fehler.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise TonFehler(f"{Path(befehl[0]).name} gescheitert: {' '.join(letzte)}")
    return aus.decode("utf-8", "replace"), fehler.decode("utf-8", "replace")


async def _durchleiten(befehl: list[str], eingabe: bytes | None = None) -> bytes:
    """ffmpeg mit Daten über stdin und stdout (rohe Gleitkommawerte statt Zwischendateien)."""
    prozess = await asyncio.create_subprocess_exec(*befehl, stdin=asyncio.subprocess.PIPE if eingabe is not None else None,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        aus, fehler = await prozess.communicate(eingabe)
    except asyncio.CancelledError:
        prozess.kill()
        await prozess.wait()
        raise
    if prozess.returncode != 0:
        letzte = fehler.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise TonFehler(f"{Path(befehl[0]).name} gescheitert: {' '.join(letzte)}")
    return aus


def _zwischen(ziel: Path) -> Path:
    """Zwischenname mit derselben Endung (ffmpeg wählt den Behälter nach ihr)."""
    return ziel.with_name(f".{ziel.stem}.teil{ziel.suffix}")


_RESAMPLER: dict[str, str] = {}


class Ton:
    def __init__(self, ordner: str = "") -> None:
        self.ordner = ordner

    def _ffmpeg(self) -> str:
        return programm("ffmpeg", self.ordner)

    async def resampler(self) -> str:
        """"soxr" oder "swr", einmal je ffmpeg gemessen (eine echte Wandlung, keine Annahme über den Bau)."""
        ffmpeg = self._ffmpeg()
        if ffmpeg not in _RESAMPLER:
            try:
                await _ausfuehren(ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                  "sine=f=440:d=0.1:sample_rate=44100", "-af", f"aresample=24000:{_SOXR}", "-f", "null", "-")
                _RESAMPLER[ffmpeg] = "soxr"
            except TonFehler:
                _RESAMPLER[ffmpeg] = "swr"
        return _RESAMPLER[ffmpeg]

    async def eigenschaften(self, datei: Path) -> Eigenschaften:
        aus, _ = await _ausfuehren(programm("ffprobe", self.ordner), "-v", "error", "-show_streams", "-show_format",
                                   "-of", "json", str(datei))
        try:
            daten = json.loads(aus)
            fmt = daten.get("format", {})
            stroeme = daten.get("streams", [])
            ton = next((s for s in stroeme if s.get("codec_type") == "audio"), None)
            bild = any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in stroeme)

            def zahl(wert) -> int | None:
                try:
                    return int(wert) if wert not in (None, "", "N/A") else None
                except (TypeError, ValueError):
                    return None

            bits = None
            if ton is not None:
                bits = zahl(ton.get("bits_per_raw_sample")) or zahl(ton.get("bits_per_sample")) or None
                if not bits and (sf := ton.get("sample_fmt")):
                    bits = {"u8": 8, "s16": 16, "s16p": 16, "s32": 32, "s32p": 32, "flt": 32, "fltp": 32,
                            "dbl": 64, "dblp": 64}.get(sf)
            return Eigenschaften(
                dauer_s=float(fmt.get("duration") or (ton or {}).get("duration") or 0.0),
                rate=zahl((ton or {}).get("sample_rate")), kanaele=zahl((ton or {}).get("channels")),
                kodierung=(ton or {}).get("codec_name"), bits=bits,
                bitrate=zahl((ton or {}).get("bit_rate")) or zahl(fmt.get("bit_rate")),
                behaelter=fmt.get("format_name"), hat_video=bild)
        except (KeyError, ValueError, TypeError) as f:
            raise TonFehler("Eigenschaften nicht lesbar (keine Ton- oder Videodatei?)") from f

    async def dauer(self, datei: Path) -> float:
        e = await self.eigenschaften(datei)
        if e.dauer_s <= 0:
            raise TonFehler("Dauer nicht lesbar (keine Ton- oder Videodatei?)")
        return e.dauer_s

    async def wandeln(self, quelle: Path, ziel: Path, format: Tonformat, *, beginn: float | None = None,
                      ende: float | None = None) -> Path:
        """Die Tonspur von `quelle` (auch aus Video) genau in `format`, auf Wunsch nur von `beginn` bis `ende`."""
        vorlaeufig = _zwischen(ziel)
        filter_ = f"aresample={format.rate}:{_SOXR if await self.resampler() == 'soxr' else _SWR}"
        befehl = [self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        if beginn is not None:
            befehl += ["-ss", f"{beginn:.3f}"]
        if ende is not None:
            befehl += ["-to", f"{ende:.3f}"]
        befehl += ["-i", str(quelle), "-vn", "-map_metadata", "-1", "-af", filter_, "-ar", str(format.rate),
                   "-ac", str(format.kanaele), "-c:a", format.kodierung]
        if format.bitrate:
            befehl += ["-b:a", format.bitrate]
        await _ausfuehren(*befehl, str(vorlaeufig))
        vorlaeufig.replace(ziel)
        return ziel

    async def ausschneiden(self, datei: Path, beginn: float, ende: float, ziel: Path) -> Path:
        """Ein Stück ohne Umwandlung der Abtastrate (gleiches PCM wie die Quelle, für Abschnitte einer Arbeitsdatei)."""
        vorlaeufig = _zwischen(ziel)
        await _ausfuehren(self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{beginn:.3f}",
                          "-to", f"{ende:.3f}", "-i", str(datei), "-c:a", "pcm_s16le", str(vorlaeufig))
        vorlaeufig.replace(ziel)
        return ziel

    async def pausen(self, datei: Path, *, schwelle_db: float = -35.0, mindestens_s: float = 0.4) -> list[Pause]:
        _, protokoll = await _ausfuehren(self._ffmpeg(), "-nostdin", "-hide_banner", "-i", str(datei),
                                         "-af", f"silencedetect=noise={schwelle_db}dB:d={mindestens_s}", "-f", "null", "-")
        pausen, beginn = [], None
        for zeile in protokoll.splitlines():
            if (b := _STILLE_BEGINN.search(zeile)) is not None:
                beginn = max(0.0, float(b.group(1)))
            elif (e := _STILLE_ENDE.search(zeile)) is not None and beginn is not None:
                pausen.append(Pause(start=beginn, ende=float(e.group(1))))
                beginn = None
        return pausen

    async def wellenform(self, datei: Path, punkte: int = 800) -> list[int]:
        """Lautstärke in `punkte` Abschnitten (0 bis 100) für die Anzeige im Spieler. Aus 2000 Werten je Sekunde: genug
        für die Grundtöne der Stimme und klein genug für Stunden. In Dezibel mit festem Maßstab wie der Pegel beim
        Aufnehmen (0 dB voll, -WELLE_DB leer): leise Sprache bleibt sichtbar, ein Knackser drückt sie nicht flach."""
        import numpy as np

        prozess = await asyncio.create_subprocess_exec(
            self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(datei),
            "-ac", "1", "-ar", "2000", "-f", "s16le", "-", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        roh, fehler = await prozess.communicate()
        if prozess.returncode != 0:
            raise TonFehler(f"ffmpeg gescheitert: {fehler.decode('utf-8', 'replace').strip()[-200:]}")
        werte = np.abs(np.frombuffer(roh, dtype="<i2").astype(np.float64))
        if werte.size == 0:
            return []
        teile = np.array_split(werte, min(punkte, werte.size))
        spitzen = np.array([t.max() for t in teile])
        db = 20 * np.log10(np.maximum(spitzen, 1.0) / 32768.0)
        return [int(round(v)) for v in np.clip(100 * (1 + db / WELLE_DB), 0, 100)]

    # --- Gleitkomma: lesen, bearbeiten, genau einmal schreiben -----------------------------------------------------

    async def lesen(self, datei: Path, rate: int):
        """Die Tonspur als Gleitkommawerte (numpy float32, mono) in `rate`. Aus 16 Bit verlustfrei; nur wenn die Rate
        der Datei abweicht, wird mit dem gemessenen Resampler gewandelt."""
        import numpy as np

        filter_ = f"aresample={rate}:{_SOXR if await self.resampler() == 'soxr' else _SWR}"
        roh = await _durchleiten([self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(datei),
                                  "-vn", "-af", filter_, "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"])
        return np.frombuffer(roh, dtype="<f4").copy()

    async def schreiben(self, werte, rate: int, ziel: Path, format: Tonformat) -> Path:
        """Gleitkommawerte (mono, `rate`) genau einmal in `format`: Rate (gemessener Resampler), Kanäle (Mono in jeden
        Kanal), Kodierung und Bitrate. Werte außerhalb von -1 bis 1 werden nicht abgeschnitten, sondern sind ein Fehler
        des Aufrufers (`TonFehler`), damit nichts unbemerkt verzerrt."""
        import numpy as np

        werte = np.asarray(werte, dtype="<f4")
        if werte.size and float(np.max(np.abs(werte))) > 1.0 + 1e-6:
            raise TonFehler("Ton übersteuert (Werte über 1,0): vor dem Schreiben anpassen")
        vorlaeufig = _zwischen(ziel)
        filter_ = f"aresample={format.rate}:{_SOXR if await self.resampler() == 'soxr' else _SWR}"
        befehl = [self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(rate),
                  "-ac", "1", "-i", "-", "-map_metadata", "-1", "-af", filter_, "-ar", str(format.rate),
                  "-ac", str(format.kanaele), "-c:a", format.kodierung]
        if format.bitrate:
            befehl += ["-b:a", format.bitrate]
        if ziel.suffix.lower() in MP4_ENDUNGEN:
            befehl += ["-movflags", "+faststart"]      # Inhaltsverzeichnis vorn: abspielbar, bevor alles geladen ist
        await _durchleiten([*befehl, str(vorlaeufig)], werte.tobytes())
        vorlaeufig.replace(ziel)
        return ziel

    async def stauchen(self, werte, rate: int, faktor: float):
        """Schneller sprechen um `faktor` (über 1 kürzer, unter 1 länger) bei gleicher Tonhöhe; Gleitkomma rein und raus."""
        import numpy as np

        if not 0.5 <= faktor <= 4.0:
            raise TonFehler(f"Stauchen nur zwischen 0,5 und 4,0, nicht {faktor}")
        if abs(faktor - 1.0) < 1e-4:
            return np.asarray(werte, dtype="<f4").copy()
        roh = await _durchleiten([self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "f32le",
                                  "-ar", str(rate), "-ac", "1", "-i", "-", "-af", f"atempo={faktor:.5f}", "-f", "f32le", "-"],
                                 np.asarray(werte, dtype="<f4").tobytes())
        return np.frombuffer(roh, dtype="<f4").copy()

    async def flac(self, datei: Path, ziel: Path) -> Path:
        """Verlustfrei kleiner (etwa die Hälfte) bei gleicher Rate und gleichen Kanälen."""
        vorlaeufig = _zwischen(ziel)
        await _ausfuehren(self._ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                          "-i", str(datei), "-c:a", "flac", str(vorlaeufig))
        vorlaeufig.replace(ziel)
        return ziel
