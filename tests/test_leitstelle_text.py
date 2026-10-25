"""Text eines Sprachmodells: gerade Zeichen ohne Verlust der Umlaute, nachsichtiges Lesen von JSON, Antwortform."""

import pytest

from appkern.leitstelle import antwortform, gerade, json_lesen, saeubern


def zeichen(*codepunkte: int) -> list[str]:
    return [chr(c) for c in codepunkte]


def test_gerade_zeichen():
    halb, ganz, minus, unten, oben, links, rechts, auf, zu, punkte, schmal = zeichen(
        0x2013, 0x2014, 0x2212, 0x201E, 0x201C, 0x00BB, 0x00AB, 0x2018, 0x2019, 0x2026, 0x00A0)
    krumm = f"Grüße {halb} {unten}Schön{oben}, {links}gut{rechts}, {auf}ja{zu} {ganz} 1{minus} 2{punkte}{schmal}Ende"
    assert gerade(krumm) == "Grüße - \"Schön\", \"gut\", 'ja' - 1- 2... Ende"
    assert gerade("Straße, Größe, Übung") == "Straße, Größe, Übung"
    assert saeubern({"text": f"a {halb} b", "punkte": [f"{unten}x{oben}", 3], halb: None}) == \
        {"text": "a - b", "punkte": ['"x"', 3], halb: None}


@pytest.mark.parametrize("roh", [
    '{"text": "ok"}',
    '```json\n{"text": "ok"}\n```',
    'Hier ist die Antwort:\n{"text": "ok"}\nGern geschehen.',
])
def test_json_nachsichtig(roh):
    assert json_lesen(roh) == {"text": "ok"}


def test_json_unlesbar():
    for roh in ("", "kein json", '{"text": '):
        with pytest.raises(ValueError):
            json_lesen(roh)


def test_antwortform():
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    assert antwortform("zusammenfassung", schema) == {
        "type": "json_schema", "json_schema": {"name": "zusammenfassung", "strict": True, "schema": schema}}
