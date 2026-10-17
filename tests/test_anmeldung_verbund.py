"""Verbund: Anmeldung gegen eine echte Kellerwolke (Entwicklungsinstanz). Braucht in `.env.test` (nicht im Repo)
zusätzlich `KELLERWOLKE_KENNUNG` und `KELLERWOLKE_PASSWORT` eines Testkontos; ohne wird übersprungen. Jede Sitzung und
jedes Testgerät wird am Ende wieder beendet."""

import os
from pathlib import Path

import httpx
import pytest

from appkern.anmeldung import Abgelehnt, Anmeldung, NichtErlaubt


def _werte() -> dict[str, str]:
    werte = dict(os.environ)
    datei = Path(__file__).resolve().parents[1] / ".env.test"
    if datei.is_file():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            k, _, w = zeile.partition("=")
            werte.setdefault(k.strip(), w.strip())
    return werte


W = _werte()
pytestmark = pytest.mark.skipif(not all(W.get(k) for k in ("KELLERWOLKE_ADRESSE", "KELLERWOLKE_KENNUNG", "KELLERWOLKE_PASSWORT")),
                                reason="keine Test-Kellerwolke mit Konto eingerichtet (.env.test)")


async def test_passwort_kopplung_und_trennen():
    adresse, kennung, passwort = W["KELLERWOLKE_ADRESSE"], W["KELLERWOLKE_KENNUNG"], W["KELLERWOLKE_PASSWORT"]
    a = Anmeldung(adresse, lambda: {kennung}, merken_s=0.0)
    token, konto = await a.anmelden(kennung, passwort)
    try:
        assert konto.name.lower() == kennung.lower() and (await a.pruefen(token)).id == konto.id
        with pytest.raises(Abgelehnt):
            await a.anmelden(kennung, passwort + "-falsch")
        async with httpx.AsyncClient() as c:
            code = (await c.post(f"{adresse}/api/v1/geraete/kopplung", headers={"X-Kellerwolke-Sitzung": token})).json()["code"]
        schluessel, geraet_konto = await a.koppeln(code, "Appkern-Verbundtest", "browser")
        assert geraet_konto.geraet and (await a.pruefen(schluessel)).id == konto.id
        await a.abmelden(schluessel)                                   # trennt das Testgerät
        assert await a.pruefen(schluessel) is None
        fremd = Anmeldung(adresse, lambda: {"niemand-sonst"})
        with pytest.raises(NichtErlaubt):
            await fremd.anmelden(kennung, passwort)                   # dessen Sitzung ist sofort wieder beendet
        await fremd.schliessen()
    finally:
        await a.abmelden(token)
        assert await a.pruefen(token) is None
        await a.schliessen()
