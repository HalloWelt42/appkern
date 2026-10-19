"""Verbund: der Zugang gegen eine echte Kellerwolke (Entwicklungsinstanz oder Test-Kellerwolke).

Braucht Adresse und App-Schlüssel, aus der Umgebung oder aus `.env.test` (nicht im Repo):
    KELLERWOLKE_ADRESSE=http://127.0.0.1:22940
    KELLERWOLKE_SCHLUESSEL=kw_app_...
Ohne beides wird übersprungen. Jeder Lauf arbeitet in einem eigenen Ordner im Zweig der App und legt ihn am Ende in
den Papierkorb des Kontos.
"""

import asyncio
import hashlib
import os
import secrets
from pathlib import Path

import pytest

from appkern.testen import kellerwolke_antwortet

from appkern.kellerwolke import (
    Kellerwolke, KeinRecht, NichtGefunden, StandFehlt, StandVeraltet, pfad_aus,
)


def _zugangsdaten() -> tuple[str, str] | None:
    werte = dict(os.environ)
    datei = Path(__file__).resolve().parents[1] / ".env.test"
    if datei.is_file():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            schluessel, _, wert = zeile.partition("=")
            werte.setdefault(schluessel.strip(), wert.strip())
    adresse, schluessel = werte.get("KELLERWOLKE_ADRESSE"), werte.get("KELLERWOLKE_SCHLUESSEL")
    return (adresse, schluessel) if adresse and schluessel and kellerwolke_antwortet(adresse, schluessel) else None


ZUGANG = _zugangsdaten()
pytestmark = pytest.mark.skipif(ZUGANG is None, reason="keine Test-Kellerwolke eingerichtet (.env.test) oder sie antwortet nicht")


@pytest.fixture
async def wolke():
    kw = Kellerwolke(*ZUGANG)
    ich = await kw.ich()
    lauf = await kw.ordner(pfad_aus(ich.zweig, f"lauf-{secrets.token_hex(4)}"))
    yield kw, ich, lauf
    await kw.loeschen(lauf.id)
    await kw.schliessen()


async def test_wer_bin_ich(wolke):
    kw, ich, lauf = wolke
    assert ich.zweig == f"Apps/{ich.app}"
    assert any(r.pfad == ich.zweig and r.recht == "schreiben" for r in ich.rechte)
    assert lauf.ist_ordner and lauf.pfad.startswith(ich.zweig + "/")


async def test_schreiben_lesen_und_staende(wolke):
    kw, ich, lauf = wolke
    pfad = pfad_aus(lauf.pfad, "notiz.txt")
    erst = await kw.schreiben(pfad, "Erster Stand".encode(), nur_neu=True, inhaltstyp="text/plain")
    assert erst.inhaltstyp == "text/plain" and erst.app == ich.app
    assert await kw.lesen_ganz(erst.id) == "Erster Stand".encode()
    with pytest.raises(StandVeraltet):
        await kw.schreiben(pfad, b"nochmal neu", nur_neu=True)
    with pytest.raises(StandFehlt):
        await kw.schreiben(pfad, b"ohne Stand")
    zweit = await kw.schreiben(pfad, "Zweiter Stand".encode(), stand=erst.etag)
    with pytest.raises(StandVeraltet):
        await kw.neue_version(erst.id, b"veraltet", stand=erst.etag)
    dritt = await kw.neue_version(erst.id, "Dritter Stand".encode(), stand=zweit.etag)
    assert dritt.id == erst.id and await kw.lesen_ganz(erst.id) == "Dritter Stand".encode()


async def test_grosse_datei_stroemt_hin_und_zurueck(wolke, tmp_path: Path):
    kw, _, lauf = wolke
    quelle = tmp_path / "gross.bin"
    with open(quelle, "wb") as f:
        for _ in range(30):
            f.write(secrets.token_bytes(1024 * 1024))
    k = await kw.schreiben(pfad_aus(lauf.pfad, "gross.bin"), quelle, nur_neu=True)
    assert k.groesse == quelle.stat().st_size
    ziel = await kw.herunterladen(k.id, tmp_path / "zurueck.bin")
    assert hashlib.sha256(ziel.read_bytes()).digest() == hashlib.sha256(quelle.read_bytes()).digest()
    teil = b"".join([d async for d in kw.lesen(k.id, start=1000, ende=1999)])
    with open(quelle, "rb") as f:
        f.seek(1000)
        assert teil == f.read(1000)


async def test_felder_herkunft_und_suche(wolke):
    kw, _, lauf = wolke
    ton = await kw.schreiben(pfad_aus(lauf.pfad, "aufnahme.wav"), b"RIFF0000", nur_neu=True)
    text = await kw.schreiben(pfad_aus(lauf.pfad, "aufnahme.txt"), b"Hallo", nur_neu=True)
    marke = secrets.token_hex(6)
    k = await kw.felder_setzen(text.id, {"sprache": "de", "lauf": marke})
    assert k.felder == {"sprache": "de", "lauf": marke}
    assert [t.id for t in await kw.suchen({"lauf": marke})] == [text.id]
    bezuege = await kw.herkunft_setzen(text.id, ton.id, "transkript_zu")
    assert [(b.von_id, b.zu_id, b.art) for b in bezuege] == [(ton.id, text.id, "transkript_zu")]
    await kw.herkunft_entfernen(text.id, ton.id, "transkript_zu")
    assert await kw.herkunft(text.id) == []


async def test_seitenweise_und_sperre(wolke):
    kw, _, lauf = wolke
    for i in range(7):
        await kw.schreiben(pfad_aus(lauf.pfad, f"d{i}.txt"), b"x", nur_neu=True)
    namen = [k.name async for k in kw.alle_kinder(lauf.id)]
    assert namen == [f"d{i}.txt" for i in range(7)]
    d0 = await kw.pfad(pfad_aus(lauf.pfad, "d0.txt"))
    sperre = await kw.sperren(d0.id, 60, "Test")
    assert sperre.grund == "Test" and (await kw.knoten(d0.id)).sperre is not None
    await kw.entsperren(d0.id)
    assert (await kw.knoten(d0.id)).sperre is None


async def test_beobachten_sieht_neue_datei(wolke):
    kw, _, lauf = wolke
    gesehen: asyncio.Queue = asyncio.Queue()

    async def beobachter():
        async for stand in kw.beobachten(lauf.id):
            for e in stand.eintraege:
                await gesehen.put(e)

    aufgabe = asyncio.create_task(beobachter())
    try:
        await asyncio.sleep(0.5)
        neu = await kw.schreiben(pfad_aus(lauf.pfad, "neu.txt"), b"x", nur_neu=True)
        while True:
            e = await asyncio.wait_for(gesehen.get(), timeout=10)
            if e.knoten_id == neu.id:
                assert e.typ == "erstellt"
                break
    finally:
        aufgabe.cancel()


async def test_fremdes_bleibt_fremd(wolke):
    kw, ich, _ = wolke
    with pytest.raises(NichtGefunden):
        await kw.pfad("Privat-gibt-es-fuer-Apps-nicht/x.txt")
    with pytest.raises((KeinRecht, NichtGefunden)):
        await kw.schreiben("Apps/Fremde-App-ohne-Recht/x.txt", b"x", nur_neu=True)
    anker = await kw.pfad(ich.zweig)
    with pytest.raises(KeinRecht):
        await kw.loeschen(anker.id)


async def test_versionen_lesen_und_zurueckholen(wolke):
    kw, ich, lauf = wolke
    erst = await kw.schreiben(pfad_aus(lauf.pfad, "stand.json"), b'{"v": 1}', nur_neu=True)
    zweit = await kw.neue_version(erst.id, b'{"v": 2}', stand=erst.etag)
    versionen = await kw.versionen(erst.id)
    assert [v.aktuell for v in versionen] == [True, False] and versionen[1].groesse == 8
    alt = await kw.version_ganz(erst.id, versionen[1].id)
    assert alt == b'{"v": 1}'
    assert b"".join([d async for d in kw.version_lesen(erst.id, versionen[1].id, start=1, ende=3)]) == b'"v"'
    await kw.neue_version(erst.id, alt, stand=zweit.etag)                    # zurückholen = neue Version
    assert await kw.lesen_ganz(erst.id) == b'{"v": 1}' and len(await kw.versionen(erst.id)) == 3
    assert ich.konto_id is not None


async def test_app_schluessel_meldet_sich_bei_einer_anderen_app_an(wolke):
    """Eine andere App (hier dieser Testzugang) meldet sich mit ihrem App-Schlüssel an; die Kellerwolke sagt, wem er
    gehört."""
    from appkern.anmeldung import Anmeldung

    kw, ich, _ = wolke
    a = Anmeldung(ZUGANG[0], lambda: {ich.konto}, merken_s=0.0)
    konto = await a.pruefen(ZUGANG[1])
    assert konto is not None and konto.app == ich.app and konto.name == ich.konto and konto.id == str(ich.konto_id)
    fremd = Anmeldung(ZUGANG[0], lambda: {"niemand-sonst"})
    assert await fremd.pruefen(ZUGANG[1]) is None
    assert await a.pruefen("kw_app_gibt_es_nicht") is None
    await a.schliessen()
    await fremd.schliessen()
