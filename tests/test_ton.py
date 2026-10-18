"""Ton: Eigenschaften messen, genau wandeln und zurück (Frequenz und Dauer bleiben, Format wie bestellt), aus Video,
Ausschnitt, Pausen, Wellenform. Mit echtem ffmpeg; die Tonsignale entstehen hier."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from appkern.ton import ABSPIELEN, ARBEIT, HOEREN, Ton, TonFehler, Tonformat, programm


async def erzeugen(ziel: Path, *argumente: str) -> Path:
    p = await asyncio.create_subprocess_exec(programm("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", *argumente,
                                             str(ziel))
    assert await p.wait() == 0
    return ziel


def frequenz(datei: Path, rate: int, dtype: str) -> float:
    """Stärkste Frequenz einer rohen Datei (Kopf übersprungen über die Länge des Datenblocks)."""
    roh = np.frombuffer(datei.read_bytes()[-rate * 4 * (2 if dtype == "<f4" else 1):], dtype=dtype).astype(np.float64)
    spektrum = np.abs(np.fft.rfft(roh * np.hanning(roh.size)))
    return float(np.fft.rfftfreq(roh.size, 1 / rate)[np.argmax(spektrum)])


async def test_wandeln_hin_und_zurueck(tmp_path):
    ton = Ton()
    quelle = await erzeugen(tmp_path / "quelle.wav", "-f", "lavfi", "-i", "sine=f=1000:d=3:sample_rate=48000",
                            "-ac", "2", "-c:a", "pcm_s16le")
    e = await ton.eigenschaften(quelle)
    assert (e.rate, e.kanaele, e.kodierung, e.bits) == (48000, 2, "pcm_s16le", 16) and e.dauer_s == pytest.approx(3.0, abs=0.01)

    arbeit = await ton.wandeln(quelle, tmp_path / "arbeit.wav", ARBEIT)
    a = await ton.eigenschaften(arbeit)
    assert (a.rate, a.kanaele, a.kodierung, a.bits) == (24000, 1, "pcm_f32le", 32)
    assert a.dauer_s == pytest.approx(3.0, abs=0.005)
    assert frequenz(arbeit, 24000, "<f4") == pytest.approx(1000, abs=1.5)

    zurueck = await ton.wandeln(arbeit, tmp_path / "zurueck.wav", e.als_format())
    z = await ton.eigenschaften(zurueck)
    assert (z.rate, z.kanaele, z.kodierung) == (48000, 2, "pcm_s16le") and z.dauer_s == pytest.approx(3.0, abs=0.005)

    mp3 = await ton.wandeln(arbeit, tmp_path / "vorlesen.mp3", Tonformat(rate=44100, kanaele=1, kodierung="libmp3lame",
                                                                        bitrate="128k"))
    m = await ton.eigenschaften(mp3)
    assert (m.rate, m.kanaele, m.kodierung) == (44100, 1, "mp3") and 120_000 <= (m.bitrate or 0) <= 136_000
    assert not list(tmp_path.glob(".*teil*"))                                  # keine Zwischendateien übrig
    assert await ton.resampler() in ("soxr", "swr")


async def test_feste_formate_und_video(tmp_path):
    ton = Ton()
    video = await erzeugen(tmp_path / "v.mp4", "-f", "lavfi", "-i", "testsrc=d=2:s=160x120", "-f", "lavfi", "-i",
                           "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac")
    v = await ton.eigenschaften(video)
    assert v.hat_video and v.kodierung == "aac"
    hoeren = await ton.eigenschaften(await ton.wandeln(video, tmp_path / "h.wav", HOEREN))
    assert (hoeren.rate, hoeren.kanaele, hoeren.kodierung, hoeren.hat_video) == (16000, 1, "pcm_s16le", False)
    abspielen = await ton.eigenschaften(await ton.wandeln(video, tmp_path / "a.wav", ABSPIELEN))
    assert (abspielen.rate, abspielen.kanaele) == (44100, 1)
    teil = await ton.wandeln(video, tmp_path / "teil.wav", ARBEIT, beginn=0.5, ende=1.5)
    assert await ton.dauer(teil) == pytest.approx(1.0, abs=0.01)
    with pytest.raises(TonFehler):
        (await ton.eigenschaften(await erzeugen(tmp_path / "stumm.mp4", "-f", "lavfi", "-i", "testsrc=d=1:s=64x48",
                                                "-c:v", "libx264"))).als_format()


async def test_pausen_ausschnitt_wellenform(tmp_path):
    ton = Ton()
    mit_pausen = await erzeugen(tmp_path / "p.wav", "-f", "lavfi", "-i",
                                "aevalsrc='if(lt(mod(t,4),3),0.5*sin(2*PI*300*t),0)':s=16000:d=12", "-c:a", "pcm_s16le")
    pausen = await ton.pausen(mit_pausen)
    assert [round(p.start) for p in pausen][:2] == [3, 7] and all(p.laenge == pytest.approx(1.0, abs=0.1) for p in pausen[:2])
    stueck = await ton.ausschneiden(mit_pausen, 2.0, 5.0, tmp_path / "s.wav")
    assert await ton.dauer(stueck) == pytest.approx(3.0, abs=0.02)
    welle = await ton.wellenform(mit_pausen, punkte=48)           # vier Punkte je Sekunde: mitten in der Pause leer
    assert len(welle) == 48 and min(welle) == 0 and max(welle) > 80


def frequenz_werte(werte: np.ndarray, rate: int) -> float:
    spektrum = np.abs(np.fft.rfft(werte.astype(np.float64) * np.hanning(werte.size)))
    return float(np.fft.rfftfreq(werte.size, 1 / rate)[np.argmax(spektrum)])


async def test_gleitkomma_lesen_stauchen_schreiben(tmp_path):
    """Sprachausgabe: lesen (aus 48 kHz Stereo in 24 kHz Mono), stauchen (kürzer, gleiche Tonhöhe), genau einmal in MP3
    mono 24 kHz und in WAV 48 kHz Stereo schreiben; gemessen werden Frequenz, Dauer und Format."""
    ton = Ton()
    quelle = await erzeugen(tmp_path / "quelle.wav", "-f", "lavfi", "-i", "sine=f=440:d=3:sample_rate=48000",
                            "-ac", "2", "-c:a", "pcm_s16le")
    werte = await ton.lesen(quelle, 24000)
    assert werte.dtype == np.float32 and werte.size == pytest.approx(72000, abs=48)
    assert frequenz_werte(werte, 24000) == pytest.approx(440, abs=1)

    kurz = await ton.stauchen(werte, 24000, 1.25)
    assert kurz.size / 24000 == pytest.approx(2.4, abs=0.02)
    assert frequenz_werte(kurz, 24000) == pytest.approx(440, abs=2)

    mp3 = await ton.schreiben(kurz, 24000, tmp_path / "ergebnis.mp3",
                              Tonformat(rate=24000, kanaele=1, kodierung="libmp3lame", bitrate="128k"))
    e = await ton.eigenschaften(mp3)
    assert (e.rate, e.kanaele, e.kodierung) == (24000, 1, "mp3") and e.dauer_s == pytest.approx(2.4, abs=0.08)
    assert e.bitrate == pytest.approx(128000, rel=0.05)

    wav = await ton.schreiben(kurz, 24000, tmp_path / "wie_quelle.wav", Tonformat(rate=48000, kanaele=2, kodierung="pcm_s16le"))
    w = await ton.eigenschaften(wav)
    assert (w.rate, w.kanaele, w.kodierung) == (48000, 2, "pcm_s16le") and w.dauer_s == pytest.approx(2.4, abs=0.02)
    assert frequenz_werte(await ton.lesen(wav, 48000), 48000) == pytest.approx(440, abs=2)

    with pytest.raises(TonFehler):
        await ton.schreiben(kurz * 10.0, 24000, tmp_path / "zu_laut.wav", ARBEIT)
