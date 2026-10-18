"""Gegenseite des Tondienstes (Protokoll in `dienst.py`): die Routen, die im Tondienst auf dem Mac laufen (Wirt:
Klangwerk, Dienst `ton`). Nimmt die Dateien an, lässt `TonHier` rechnen und hält erzeugte Dateien bis zum Abholen."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.background import BackgroundTask

from .arbeit import Aufbereiten, Aufbereitet, Blenden, Datei, Gelegt, Legen, TonHier
from .dienst import EINGANG, ERGEBNIS, GRUND, VERFALL_S, typ
from .ton import TonFehler


def routen(hier: TonHier, ablage: Path, *, gleichzeitig: int = 4):
    """Die Routen des Tondienstes. `ablage` hält erzeugte Dateien bis zum Abholen."""
    ablage.mkdir(parents=True, exist_ok=True)
    sperre = asyncio.Semaphore(gleichzeitig)
    r = APIRouter(prefix="/ton", tags=["ton"])

    def fehler(code: int, grund: str, meldung: str) -> JSONResponse:
        return JSONResponse(status_code=code, content={"error": {"code": grund, "message": meldung[:500]}})

    def verfallene_weg() -> None:
        grenze = time.time() - VERFALL_S
        for p in ablage.iterdir():
            with contextlib.suppress(OSError):
                if p.stat().st_mtime < grenze:
                    p.unlink()

    def neues_ziel(endung: str) -> Path:
        return ablage / f"{uuid.uuid4().hex}{endung}"

    async def annehmen(datei: UploadFile, ordner: Path, nr: int) -> Path:
        endung = Path(datei.filename or "").suffix.lower()
        ziel = ordner / f"eingang-{nr}{endung if EINGANG.match(endung) else '.bin'}"
        with open(ziel, "wb") as aus:
            while stueck := await datei.read(1024 * 1024):
                aus.write(stueck)
        if ziel.stat().st_size == 0:
            raise TonFehler("Leere Datei")
        return ziel

    async def arbeiten(dateien: list[UploadFile], auftrag_json: str, art: type[BaseModel], tun):
        try:
            auftrag = art.model_validate_json(auftrag_json)
        except ValidationError as f:
            return fehler(422, "ungueltig", f"Auftrag nicht lesbar: {f.errors()[0]['msg']}")
        verfallene_weg()
        ordner = Path(tempfile.mkdtemp(prefix="tondienst-"))
        try:
            pfade = [await annehmen(d, ordner, i) for i, d in enumerate(dateien)]
            async with sperre:
                return await tun(pfade, auftrag)
        except TonFehler as f:
            return fehler(422, GRUND, str(f))
        except ValueError as f:
            return fehler(422, "ungueltig", str(f))
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    @r.post("/aufbereiten", response_model=Aufbereitet)
    async def aufbereiten(datei: UploadFile = File(...), auftrag: str = Form("{}")):
        async def tun(pfade: list[Path], a: Aufbereiten):
            ziele = [neues_ziel(x.endung) for x in a.ausgaben]
            erg = await hier.aufbereiten(pfade[0], a, ziele)
            for d, z in zip(erg.ausgaben, ziele, strict=True):
                d.name = z.name
            return erg
        return await arbeiten([datei], auftrag, Aufbereiten, tun)

    @r.post("/blenden", response_model=Datei)
    async def blenden(dateien: list[UploadFile] = File(...), auftrag: str = Form(...)):
        async def tun(pfade: list[Path], a: Blenden):
            ziel = neues_ziel(a.endung)
            d = await hier.blenden(pfade, a, ziel)
            d.name = ziel.name
            return d
        return await arbeiten(dateien, auftrag, Blenden, tun)

    @r.post("/legen", response_model=Gelegt)
    async def legen(dateien: list[UploadFile] = File(...), auftrag: str = Form(...)):
        async def tun(pfade: list[Path], a: Legen):
            ziel = neues_ziel(a.endung)
            g = await hier.legen(pfade, a, ziel)
            g.datei.name = ziel.name
            return g
        return await arbeiten(dateien, auftrag, Legen, tun)

    @r.get("/ergebnis/{name}")
    async def ergebnis(name: str):
        """Einmal abholen; danach ist die Datei weg."""
        pfad = ablage / name
        if not ERGEBNIS.match(name) or not pfad.is_file():
            raise HTTPException(404, "Ergebnis nicht (mehr) da")
        return FileResponse(pfad, media_type=typ(pfad), background=BackgroundTask(pfad.unlink, missing_ok=True))

    return r
