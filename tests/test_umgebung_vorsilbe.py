"""Vorsilbe der Umgebungswerte: dieselben Namen in Gerüst, Ausrollen und Vorlage, auch bei einer Kennung mit
Bindestrich (TGA-1: telegram-archiv las sein Hauszertifikat nicht, weil Compose TELEGRAM_ARCHIV_ setzte)."""

from appkern.einstellungen import umgebung_vorsilbe


def test_bindestrich_wird_unterstrich():
    assert umgebung_vorsilbe("telegram-archiv") == "TELEGRAM_ARCHIV"


def test_kennung_ohne_bindestrich_bleibt():
    assert umgebung_vorsilbe("strukturblick") == "STRUKTURBLICK"
