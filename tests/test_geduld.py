"""Geduldig mit stellbarer Uhr: der Schlaf eines Rechners wartet ohne Grenze und zählt nicht zur Geduld, andere
Ausfälle nur so lange, wie die App es einstellt; jede Meldung einmal, Abbrechen jede Sekunde."""

from __future__ import annotations

import pytest

from appkern.leitstelle import DienstWeg, Halt, RechnerSchlaeft, geduld, geduld_setzen, geduldig
from appkern.leitstelle.geduld import GEDULD_S


class Uhr:
    def __init__(self) -> None:
        self.s = 0.0
        self.schritt = 1.0            # so viel vergeht je Sekunde Pause; 3600: eine Stunde je Sekunde

    def __call__(self) -> float:
        return self.s

    async def schlafen(self, s: float) -> None:
        self.s += s * self.schritt


def schlaf() -> RechnerSchlaeft:
    return RechnerSchlaeft("Mac Studio schläft; der Auftrag kann erst laufen, wenn er wach ist.", 503, "rechner_schlaeft", 60, ["Mac Studio"])


@pytest.fixture(autouse=True)
def geduld_zuruecksetzen():
    yield
    geduld_setzen(GEDULD_S)


async def test_zwoelf_stunden_schlaf_bei_einer_minute_geduld():
    """Geduld 60 s, der Rechner schläft zwölf Stunden: es wird gewartet. Danach ist der Dienst kurz weg (startet), das
    zählt von vorn und liegt in der Geduld; dann klappt es. Gemeldet wird jede Art einmal."""
    uhr, meldungen, pruefungen = Uhr(), [], []
    uhr.schritt = 12 * 3600 / (60 * 12)        # zwölf Antworten zu je 60 s Pause ergeben zwölf Stunden
    ablauf = [schlaf()] * 12 + [DienstWeg("startet", 503, "dienst_nicht_erreichbar", 1)] * 2

    async def aufruf():
        if ablauf:
            raise ablauf.pop(0)
        return "fertig"

    async def melden(text):
        meldungen.append(text)

    async def pruefen():
        pruefungen.append(uhr())
    geduld_setzen(60)
    assert await geduldig(aufruf, was="Hören", melden=melden, pruefen=pruefen, uhr=uhr, schlafen=uhr.schlafen) == "fertig"
    assert uhr() >= 12 * 3600
    assert meldungen == ["Hören: wartet, bis Mac Studio wach ist", "Hören: startet; neuer Versuch in 1 s"]
    assert len(pruefungen) == 12 * 60 + 2                         # jede Sekunde der Pause darf abgebrochen werden


async def test_geduld_zaehlt_nur_andere_ausfaelle_und_beginnt_nach_dem_schlaf_neu():
    uhr = Uhr()
    ablauf = [Halt("Halt", 503, "halt", 30)] * 2 + [schlaf()] + [Halt("Halt", 503, "halt", 30)] * 2

    async def aufruf():
        if ablauf:
            raise ablauf.pop(0)
        return "da"
    # je 30 s Halt: 60 s vor dem Schlaf, 60 s danach; mit 70 s Geduld reicht es nur, weil der Schlaf neu beginnen lässt
    assert await geduldig(aufruf, was="x", geduld_s=70, uhr=uhr, schlafen=uhr.schlafen) == "da"

    ablauf[:] = [Halt("Halt", 503, "halt", 30)] * 4
    with pytest.raises(Halt):
        await geduldig(aufruf, was="x", geduld_s=70, uhr=uhr, schlafen=uhr.schlafen)


async def test_schlaf_wird_auch_ohne_dienstweg_in_der_liste_abgewartet():
    """Wo die App nur bei Halt wartet (Ausweg vorhanden), wartet sie trotzdem auf einen schlafenden Rechner."""
    uhr = Uhr()
    ablauf = [schlaf()]

    async def aufruf():
        if ablauf:
            raise ablauf.pop(0)
        return "da"
    assert await geduldig(aufruf, was="x", warten_bei=(Halt,), uhr=uhr, schlafen=uhr.schlafen) == "da"

    async def weg():
        raise DienstWeg("weg")
    with pytest.raises(DienstWeg):
        await geduldig(weg, was="x", warten_bei=(Halt,), uhr=uhr, schlafen=uhr.schlafen)


async def test_abbrechen_waehrend_des_schlafs():
    uhr = Uhr()

    class Abgebrochen(Exception):
        pass

    async def aufruf():
        raise schlaf()

    async def pruefen():
        if uhr() >= 600:
            raise Abgebrochen()
    with pytest.raises(Abgebrochen):
        await geduldig(aufruf, was="x", pruefen=pruefen, uhr=uhr, schlafen=uhr.schlafen)


def test_geduld_der_app_und_vorgabe():
    assert geduld() == GEDULD_S == 30 * 60
    geduld_setzen(5 * 60)
    assert geduld() == 300
