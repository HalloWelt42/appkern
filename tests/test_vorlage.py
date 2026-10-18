"""Vorlage: eine neue App entsteht vollständig (keine Platzhalter übrig, Symbol aus Font Awesome, Stellwerk-Eintrag,
Abhängigkeiten auf GitHub oder lokal), falsche Angaben werden abgewiesen."""

import json
import os
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from appkern.vorlage import GITHUB_NPM, GITHUB_PY, PLATZHALTER, VorlagenFehler, erzeugen, symbol_svg
from appkern.werkzeuge import stil_pruefen, zeichen_pruefen


def neu(tmp_path: Path, **art) -> Path:
    werte = dict(name="Transkription", kennung="transkription", rolle="macht aus Ton Text", symbol="fa-closed-captioning",
                 port=8601, ziel=tmp_path)
    return erzeugen(**{**werte, **art})


def test_neue_app_vollstaendig(tmp_path: Path):
    ordner = neu(tmp_path)
    for datei in ordner.rglob("*"):
        if datei.is_file() and datei.suffix not in (".png", ".ico"):
            inhalt = datei.read_text(encoding="utf-8")
            assert not any(p in inhalt for p in PLATZHALTER), datei
    assert (ordner / ".gitignore").is_file() and not (ordner / "gitignore").exists()
    eintrag = tomllib.loads((ordner / "stellwerk.toml").read_text(encoding="utf-8"))
    assert eintrag["teile"][0]["port"] == 8601 and eintrag["teile"][0]["ordner"] == f"{ordner}/backend"
    assert GITHUB_PY.format(extras="web") in (ordner / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert json.loads((ordner / "frontend" / "package.json").read_text())["dependencies"]["appkern-oberflaeche"] == GITHUB_NPM
    vite = (ordner / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert "port: 9601" in vite and "__APP_FASSUNG__" in vite and "fassung={__APP_FASSUNG__}" in \
        (ordner / "frontend" / "src" / "App.svelte").read_text(encoding="utf-8")
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


def test_ohne_ton(tmp_path: Path):
    ordner = neu(tmp_path)
    for datei in ("Dockerfile", "compose.pi.yml"):
        text = (ordner / datei).read_text(encoding="utf-8")
        assert "ton:" not in text and "ffmpeg" not in text and "TRANSKRIPTION_DATEN" in text, datei
    assert not (ordner / "deploy" / "ffmpeg-vom-pi").exists()
    ziel = tomllib.loads((ordner / "deploy" / "ausrollen.toml").read_text(encoding="utf-8"))
    assert ziel["ton"] is False and ziel["kennung"] == "transkription" and ziel["adresse"].endswith(":8601")
    assert "TRANSKRIPTION_DATEN" in (ordner / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert (ordner / ".dockerignore").is_file() and not (ordner / "dockerignore").exists()
    for werkzeug in ("tools/version.sh", "tools/appkern.sh", "tools/ausrollen.sh", "tools/git-hooks/pre-commit", "einrichten.sh"):
        assert os.access(ordner / werkzeug, os.X_OK), werkzeug


def test_mit_ton(tmp_path: Path):
    ordner = neu(tmp_path, ton=True)
    docker = (ordner / "Dockerfile").read_text(encoding="utf-8")
    compose = (ordner / "compose.pi.yml").read_text(encoding="utf-8")
    assert "ton:" not in docker + compose and "ffmpeg-vom-pi /usr/local/bin/ffprobe" in docker and "/host/usr/bin/ffmpeg" in compose
    assert os.access(ordner / "deploy" / "ffmpeg-vom-pi", os.X_OK)
    assert "appkern[web,ton] @" in (ordner / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert tomllib.loads((ordner / "deploy" / "ausrollen.toml").read_text(encoding="utf-8"))["ton"] is True


def test_neue_app_besteht_die_eigenen_pruefungen(tmp_path: Path):
    ordner = neu(tmp_path, ton=True)
    dateien = [d for d in ordner.rglob("*") if d.is_file()]
    assert zeichen_pruefen(dateien, ordner) == [] and stil_pruefen(dateien, ordner) == []


def test_hook_zaehlt_hoch_und_haelt_auf(tmp_path: Path):
    """Der Hook der neuen App: ein sauberer Commit zählt die Fassung hoch, `!important` hält den Commit auf."""
    ordner = neu(tmp_path)
    (ordner / "backend" / ".venv" / "bin").mkdir(parents=True)
    python = ordner / "backend" / ".venv" / "bin" / "python"      # steht für die Umgebung der App
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(0o755)
    git = ["git", "-c", "user.name=Probe", "-c", "user.email=probe@example.org"]
    subprocess.run(["git", "init", "-q"], cwd=ordner, check=True)
    subprocess.run(["git", "config", "core.hooksPath", "tools/git-hooks"], cwd=ordner, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ordner, check=True)
    erst = subprocess.run([*git, "commit", "-q", "-m", "Anfang"], cwd=ordner, capture_output=True, text=True)
    assert erst.returncode == 0, erst.stderr
    fassung = json.loads((ordner / "version.json").read_text())
    assert fassung["version"] == "0.1.0" and fassung["voll"].startswith("v0.1.0-")   # vorgemerkt: nur neue Kennung
    (ordner / "README.md").write_text("geändert\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ordner, check=True)
    assert subprocess.run([*git, "commit", "-q", "-m", "Text"], cwd=ordner).returncode == 0
    assert json.loads((ordner / "version.json").read_text())["version"] == "0.1.1"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=ordner, capture_output=True, text=True).stdout == ""
    (ordner / "frontend" / "src" / "eigen.css").write_text(".eigen { color: red !important; }\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ordner, check=True)
    zweit = subprocess.run([*git, "commit", "-q", "-m", "Stil"], cwd=ordner, capture_output=True, text=True)
    assert zweit.returncode != 0 and "!important" in zweit.stderr
