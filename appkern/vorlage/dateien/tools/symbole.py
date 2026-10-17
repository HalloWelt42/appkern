#!/usr/bin/env python3
"""Leitet aus frontend/public/symbol.svg den Symbolsatz für Browser-Tabs, Startbildschirm und PWA ab.

Einzige Quelle ist symbol.svg: ein Rechteck über die ganze Fläche als Grund, danach das Motiv. Die Hintergrundfarbe
der App kommt aus site.webmanifest (background_color). Erzeugt in frontend/public:
  favicon.svg                                   Kopie der Quelle für moderne Browser
  favicon.ico                                   16, 32 und 48 in einer Datei
  favicon-32.png, icon-192.png, icon-512.png    wie die Quelle, mit durchsichtigen Ecken (purpose any)
  icon-maskable-192.png, icon-maskable-512.png  Grund randlos, Motiv in der sicheren Zone (purpose maskable)
  apple-touch-icon.png                          180, ohne Durchsichtigkeit auf der Hintergrundfarbe der App

Die Bilder liegen im Repo und werden nie zur Laufzeit erzeugt. Nach einer Änderung an symbol.svg neu erzeugen:
  python3 tools/symbole.py
Braucht cairosvg und Pillow, nur auf dem Rechner, der die Bilder erzeugt.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg
from PIL import Image

OEFFENTLICH = Path(__file__).resolve().parent.parent / "frontend" / "public"
QUELLE = OEFFENTLICH / "symbol.svg"
SVG = "http://www.w3.org/2000/svg"
# Anteil des Motivs am maskierbaren Symbol: alles bleibt im Kreis mit 80 % Durchmesser, den kein Gerät beschneidet
SICHERE_ZONE = 0.66


def rastern(svg: bytes, groesse: int) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg, output_width=groesse, output_height=groesse)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def flach(bild: Image.Image, farbe: str) -> Image.Image:
    """Ohne Durchsichtigkeit: iOS füllt durchsichtige Stellen sonst schwarz."""
    return Image.alpha_composite(Image.new("RGBA", bild.size, farbe), bild).convert("RGB")


def maskierbar(svg: bytes) -> bytes:
    """Grund randlos über die ganze Fläche, Motiv um die Mitte auf SICHERE_ZONE verkleinert."""
    ET.register_namespace("", SVG)
    wurzel = ET.fromstring(svg)
    _, _, breite, hoehe = (float(z) for z in wurzel.get("viewBox", "").split())
    grund = next((k for k in wurzel if k.tag == f"{{{SVG}}}rect" and float(k.get("width", 0)) == breite
                  and float(k.get("height", 0)) == hoehe), None)
    if grund is None:
        sys.exit(f"{QUELLE}: Rechteck über die ganze Fläche (Grund) fehlt")
    grund.attrib.pop("rx", None)
    grund.attrib.pop("ry", None)
    motiv = [k for k in wurzel if k is not grund and k.tag != f"{{{SVG}}}defs"]
    x, y = breite / 2, hoehe / 2
    gruppe = ET.SubElement(wurzel, f"{{{SVG}}}g", transform=f"translate({x:g} {y:g}) scale({SICHERE_ZONE}) translate({-x:g} {-y:g})")
    for k in motiv:
        wurzel.remove(k)
        gruppe.append(k)
    return ET.tostring(wurzel)


def main() -> None:
    quelle = QUELLE.read_bytes()
    farbe = json.loads((OEFFENTLICH / "site.webmanifest").read_text(encoding="utf-8"))["background_color"]
    shutil.copyfile(QUELLE, OEFFENTLICH / "favicon.svg")

    ico = [rastern(quelle, g) for g in (48, 32, 16)]
    ico[0].save(OEFFENTLICH / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico[1:])
    for name, groesse in (("favicon-32.png", 32), ("icon-192.png", 192), ("icon-512.png", 512)):
        rastern(quelle, groesse).save(OEFFENTLICH / name, optimize=True)
    rand = maskierbar(quelle)
    for groesse in (192, 512):
        rastern(rand, groesse).save(OEFFENTLICH / f"icon-maskable-{groesse}.png", optimize=True)
    flach(rastern(quelle, 180), farbe).save(OEFFENTLICH / "apple-touch-icon.png", optimize=True)
    print(f"Symbolsatz aus {QUELLE.name} erzeugt in {OEFFENTLICH}")


if __name__ == "__main__":
    main()
