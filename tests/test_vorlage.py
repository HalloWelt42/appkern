"""Vorlage: eine neue App entsteht vollständig (keine Platzhalter übrig, Symbol aus Font Awesome, Stellwerk-Eintrag,
Abhängigkeiten auf GitHub oder lokal), falsche Angaben werden abgewiesen."""

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from appkern.vorlage import GITHUB_NPM, GITHUB_PY, VorlagenFehler, erzeugen, symbol_svg


def neu(tmp_path: Path, **art) -> Path:
    werte = dict(name="Transkription", kennung="transkription", rolle="macht aus Ton Text", symbol="fa-closed-captioning",
                 port=8601, ziel=tmp_path)
    return erzeugen(**{**werte, **art})


def test_neue_app_vollstaendig(tmp_path: Path):
    ordner = neu(tmp_path)
    for datei in ordner.rglob("*"):
        if datei.is_file() and datei.suffix not in (".png", ".ico"):
            assert not re.search(r"__[A-Z_]+__", datei.read_text(encoding="utf-8")), datei
    assert (ordner / ".gitignore").is_file() and not (ordner / "gitignore").exists()
    eintrag = tomllib.loads((ordner / "stellwerk.toml").read_text(encoding="utf-8"))
    assert eintrag["teile"][0]["port"] == 8601 and eintrag["teile"][0]["ordner"] == f"{ordner}/backend"
    assert GITHUB_PY in (ordner / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert json.loads((ordner / "frontend" / "package.json").read_text())["dependencies"]["appkern-oberflaeche"] == GITHUB_NPM
    assert "port: 9601" in (ordner / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert json.loads((ordner / "frontend" / "public" / "site.webmanifest").read_text())["name"] == "Transkription"
    svg = ET.fromstring((ordner / "frontend" / "public" / "symbol.svg").read_text(encoding="utf-8"))
    assert any(k.tag.endswith("path") for k in svg) and any(k.tag.endswith("rect") for k in svg)
    assert 'kennung="transkription"' in (ordner / "backend" / "app" / "main.py").read_text(encoding="utf-8")


def test_lokaler_appkern(tmp_path: Path):
    ordner = neu(tmp_path, appkern_lokal=tmp_path / "Appkern", devport=5601)
    assert f"-e {(tmp_path / 'Appkern').resolve()}[web]" in (ordner / "backend" / "requirements.txt").read_text()
    assert json.loads((ordner / "frontend" / "package.json").read_text())["dependencies"]["appkern-oberflaeche"].startswith("file:")
    assert "port: 5601" in (ordner / "frontend" / "vite.config.ts").read_text(encoding="utf-8")


@pytest.mark.parametrize("art", [{"kennung": "Gross"}, {"symbol": "closed-captioning"}, {"port": 80}, {"farbe": "blau"}])
def test_falsche_angaben(tmp_path: Path, art):
    with pytest.raises(VorlagenFehler):
        neu(tmp_path, **art)


def test_gibt_es_schon(tmp_path: Path):
    neu(tmp_path)
    with pytest.raises(VorlagenFehler):
        neu(tmp_path)


def test_symbol_ohne_font_awesome_nimmt_den_anfangsbuchstaben(tmp_path: Path):
    svg = symbol_svg("Vertonung", "fa-gibt-es-nicht", "#aa3355", tmp_path)
    assert ">V</text>" in svg and "#aa3355" in svg
