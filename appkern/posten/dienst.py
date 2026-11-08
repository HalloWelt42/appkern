"""Anmeldeposten vor Apps ohne eigene Anmeldung (ZUS-10, vorher im Vorbau am Mac): Caddy fragt ihn vor jeder Anfrage an
die App (forward_auth). Gilt die Sitzung im Keks `<kennung>_sitzung`, antwortet er 200 und nennt das Konto im Kopf
`X-<Kennung>-Konto`; sonst schickt er einen Seitenaufruf auf die Anmeldeseite und beantwortet alles andere (Schnittstellen,
Ströme) mit 401. Anmeldeseite und Abmelden liegen unter `/_<kennung>/` auf demselben Port wie die App, damit der Keks für
den Rechner gilt; den Namen der App auf der Anmeldeseite reicht Caddy im Kopf `X-<Kennung>-App` herein.

Programme haben keinen Keks: sie kommen mit dem App-Schlüssel der Kellerwolke ihrer App durch (Kopf
`Authorization: Bearer kw_app_...`, wie überall im Verbund; HELF-169). Es gelten dieselben Konten wie für Menschen
(`erlaubt`), Caddy reicht den Kopf an die App weiter. Ein Programm wird nie auf die Anmeldeseite geschickt.

Genutzt vom Vorbau am Mac und auf dem Pi (Kennung vorbau, alle Apps eines Rechners hinter einer Anmeldung) und von
Zusage auf dem Pi (eigener Posten im Compose der App). Der Posten selbst lauscht nie im Netz, nur Caddy davor.
"""

from __future__ import annotations

import html
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import __version__
from .kellerwolke import APP_PRAEFIX, Kellerwolke, KellerwolkeWeg, Konto

STATISCH = Path(__file__).with_name("statisch")


class Einstellungen(BaseSettings):
    """Über Umgebungsvariablen mit der Vorsilbe POSTEN_ (eine App, die ihn einbettet, nimmt eine eigene Vorsilbe)."""

    model_config = SettingsConfigDict(env_prefix="POSTEN_", env_file=None)

    kennung: str = Field(default="posten", pattern=r"^[a-z][a-z0-9]{1,30}$",
                         description="ergibt Keks, Pfad und Köpfe: <kennung>_sitzung, /_<kennung>, X-<Kennung>-App und -Konto")
    port: int = Field(default=8569, ge=1, le=65535, description="Port am eigenen Rechner (oder im Container)")
    adresse: str = Field(default="127.0.0.1", description="nur dieser Rechner; im Container 0.0.0.0 im eigenen Netz der App")

    kellerwolke: str = Field(description="Adresse der Kellerwolke, etwa https://192.168.178.49:39280")
    ca: str | None = Field(default=None, description="Wurzel der Hausstelle (rootCA.pem), der die Kellerwolke vertraut")
    app: str = Field(default="Posten", description="Name, für den die Kellerwolke die Sitzung ausstellt")
    erlaubt: str = Field(default="", description="Konten, die durch dürfen, durch Komma getrennt; leer heißt: alle mit der Rolle admin")
    merken_s: float = Field(default=60.0, ge=0, description="so lange gilt eine Bestätigung der Kellerwolke ohne Nachfrage")
    gueltig_tage: int = Field(default=30, ge=1, le=365, description="Lebensdauer des Kekses im Browser")
    fehlversuche: int = Field(default=10, ge=1, description="falsche Anmeldungen je Absender in 10 Minuten, danach Pause")

    @property
    def keks(self) -> str:
        return f"{self.kennung}_sitzung"

    @property
    def pfad(self) -> str:
        return f"/_{self.kennung}"

    def kopf(self, was: str) -> str:
        return f"X-{self.kennung.capitalize()}-{was}"


class Bremse:
    """Höchstens `grenze` falsche Anmeldungen je Absender im Fenster; danach wartet er, bis die älteste herausfällt."""

    def __init__(self, grenze: int, fenster_s: float = 600.0, uhr=time.monotonic) -> None:
        self.grenze, self.fenster_s, self._uhr = grenze, fenster_s, uhr
        self._fehler: dict[str, deque[float]] = {}

    def _frisch(self, wer: str) -> deque[float]:
        q = self._fehler.setdefault(wer, deque())
        while q and self._uhr() - q[0] > self.fenster_s:
            q.popleft()
        return q

    def gesperrt_s(self, wer: str) -> float:
        q = self._frisch(wer)
        return self.fenster_s - (self._uhr() - q[0]) if len(q) >= self.grenze else 0.0

    def fehler(self, wer: str) -> None:
        self._frisch(wer).append(self._uhr())

    def gut(self, wer: str) -> None:
        self._fehler.pop(wer, None)


def _darf(e: Einstellungen, konto: Konto) -> bool:
    namen = {n.strip().lower() for n in e.erlaubt.split(",") if n.strip()}
    return konto.name.lower() in namen if namen else konto.rolle == "admin"


def _app_schluessel(request: Request) -> str:
    """Der App-Schlüssel der Kellerwolke aus dem Kopf Authorization, sonst leer (ein anderer Kopf bleibt Sache der App)."""
    art, _, wert = request.headers.get("authorization", "").partition(" ")
    wert = wert.strip()
    return wert if art.lower() == "bearer" and wert.startswith(APP_PRAEFIX) else ""


def _ziel(roh: str | None, pfad: str) -> str:
    """Nur Pfade auf demselben Port, nie eine fremde Adresse (kein // und kein Schema)."""
    if not roh or not roh.startswith("/") or roh.startswith("//") or roh.startswith(pfad):
        return "/"
    return roh


def _absender(request: Request) -> str:
    # Caddy setzt X-Forwarded-For; der Posten selbst ist nur an 127.0.0.1 erreichbar
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()


def anmeldeseite(pfad: str, app: str, ziel: str, meldung: str = "", kennung: str = "") -> str:
    m = f'<p class="meldung" role="alert">{html.escape(meldung)}</p>' if meldung else ""
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Anmelden: {html.escape(app)}</title>
<style>
  @font-face {{ font-family: "Barlow"; font-weight: 400; src: url("{pfad}/statisch/barlow-latin-400-normal.woff2") format("woff2"); }}
  @font-face {{ font-family: "Barlow"; font-weight: 600; src: url("{pfad}/statisch/barlow-latin-600-normal.woff2") format("woff2"); }}
  :root {{ --hg: #e4eaf2; --karte: #ffffff; --text: #16202c; --text-2: #4a5a6d; --rand: #c5d0dd; --akzent: #a8650a; --knopf: #ffb52e; --fehler: #b3261e; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --hg: #16202c; --karte: #1f2c3b; --text: #e8eef5; --text-2: #b4c2d3; --rand: #34465a; --akzent: #ffb52e; --knopf: #ffb52e; --fehler: #ff8a80; }} }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100dvh; display: grid; place-items: center; background: var(--hg); color: var(--text);
         font: 17px/1.45 "Barlow", system-ui, sans-serif; padding: calc(env(safe-area-inset-top) + 16px) 16px 16px; }}
  main {{ width: min(420px, 100%); background: var(--karte); border-radius: 3px; padding: 28px 24px; }}
  h1 {{ margin: 0 0 4px; font-size: 26px; font-weight: 600; overflow-wrap: anywhere; }}
  p.zweck {{ margin: 0 0 20px; color: var(--text-2); font-size: 15px; }}
  label {{ display: block; margin: 14px 0 6px; font-weight: 600; font-size: 15px; }}
  input {{ width: 100%; font: inherit; font-size: 17px; padding: 10px 12px; border: 1px solid var(--rand); border-radius: 3px;
          background: var(--hg); color: var(--text); }}
  input:focus {{ outline: 2px solid var(--akzent); outline-offset: 0; }}
  button {{ margin-top: 22px; width: 100%; font: inherit; font-weight: 600; font-size: 17px; padding: 11px; border: 0; border-radius: 3px;
           background: var(--knopf); color: #16202c; cursor: pointer; }}
  .meldung {{ margin: 16px 0 0; color: var(--fehler); font-size: 15px; }}
</style></head>
<body><main>
  <h1>{html.escape(app)}</h1>
  <p class="zweck">Anmelden mit dem Konto der Kellerwolke</p>
  <form method="post" action="{pfad}/anmelden">
    <input type="hidden" name="ziel" value="{html.escape(ziel)}">
    <label for="kennung">Name</label>
    <input id="kennung" name="kennung" autocomplete="username" required value="{html.escape(kennung)}" autofocus>
    <label for="passwort">Passwort</label>
    <input id="passwort" name="passwort" type="password" autocomplete="current-password" required>
    {m}
    <button type="submit">Anmelden</button>
  </form>
</main></body></html>"""


def _kopf_text(wert: str) -> str:
    """Köpfe liest der Server als Latin-1, der Vorschaltdienst schickt den Namen der App aber als UTF-8 (etwa das ü in
    BücherFreunde); so wird aus den Bytes wieder der Name. Reiner Latin-1-Text bleibt, wie er ist."""
    try:
        return wert.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return wert


def erstellen(e: Einstellungen | None = None, kellerwolke: Kellerwolke | None = None) -> FastAPI:
    e = e or Einstellungen()
    kw = kellerwolke or Kellerwolke(e.kellerwolke, e.ca, e.app, merken_s=e.merken_s)
    bremse = Bremse(e.fehlversuche)

    @asynccontextmanager
    async def lebenslauf(_app: FastAPI):
        try:
            yield
        finally:
            await kw.schliessen()

    pfad, keks = e.pfad, e.keks
    app = FastAPI(title=f"Posten {e.kennung}", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lebenslauf)

    def name_der_app(request: Request) -> str:
        return _kopf_text(request.headers.get(e.kopf("App")) or "") or e.app

    @app.get(f"{pfad}/pruefen")
    async def pruefen(request: Request) -> Response:
        app_schluessel = _app_schluessel(request)
        try:
            konto = await kw.pruefen(request.cookies.get(keks, ""))
            if (konto is None or not _darf(e, konto)) and app_schluessel:
                konto = await kw.app_pruefen(app_schluessel)
        except KellerwolkeWeg:
            return JSONResponse({"detail": "Die Kellerwolke ist nicht erreichbar; anmelden geht gerade nicht."}, status_code=503)
        if konto is not None and _darf(e, konto):
            return Response(status_code=200, headers={e.kopf("Konto"): quote(konto.name)})
        if app_schluessel:
            return JSONResponse({"detail": "Dieser App-Schlüssel gilt hier nicht"}, status_code=401)
        seite = request.headers.get("x-forwarded-method", "GET") == "GET" and "text/html" in request.headers.get("accept", "")
        if seite:
            ziel = _ziel(request.headers.get("x-forwarded-uri"), pfad)
            return RedirectResponse(f"{pfad}/anmelden?ziel={quote(ziel, safe='')}", status_code=302)
        return JSONResponse({"detail": "Anmeldung nötig"}, status_code=401)

    @app.get(f"{pfad}/anmelden")
    async def seite(request: Request, ziel: str = "/") -> HTMLResponse:
        return HTMLResponse(anmeldeseite(pfad, name_der_app(request), _ziel(ziel, pfad)), headers={"Cache-Control": "no-store"})

    @app.post(f"{pfad}/anmelden")
    async def anmelden(request: Request, kennung: str = Form(""), passwort: str = Form(""), ziel: str = Form("/")) -> Response:
        app_name, ziel, wer = name_der_app(request), _ziel(ziel, pfad), _absender(request)

        def zurueck(meldung: str, status: int) -> HTMLResponse:
            return HTMLResponse(anmeldeseite(pfad, app_name, ziel, meldung, kennung), status_code=status, headers={"Cache-Control": "no-store"})

        if (warten := bremse.gesperrt_s(wer)) > 0:
            return zurueck(f"Zu viele falsche Anmeldungen. Bitte in {int(warten // 60) + 1} Minuten noch einmal.", 429)
        try:
            ergebnis = await kw.anmelden(kennung.strip(), passwort)
        except KellerwolkeWeg:
            return zurueck("Die Kellerwolke ist gerade nicht erreichbar. Bitte gleich noch einmal.", 503)
        if ergebnis is None:
            bremse.fehler(wer)
            return zurueck("Name oder Passwort stimmen nicht.", 401)
        token, konto = ergebnis
        if not _darf(e, konto):
            await kw.abmelden(token)
            return zurueck(f"Das Konto {konto.name} ist hier nicht zugelassen.", 403)
        bremse.gut(wer)
        antwort = RedirectResponse(ziel, status_code=303)
        antwort.set_cookie(keks, token, max_age=e.gueltig_tage * 86400, path="/", secure=True, httponly=True, samesite="lax")
        return antwort

    @app.post(f"{pfad}/abmelden")
    async def abmelden(request: Request) -> Response:
        await kw.abmelden(request.cookies.get(keks, ""))
        antwort = RedirectResponse(f"{pfad}/anmelden", status_code=303)
        antwort.delete_cookie(keks, path="/", secure=True, httponly=True, samesite="lax")
        return antwort

    @app.get(f"{pfad}/statisch/{{datei}}")
    async def statisch(datei: str) -> Response:
        pfad = (STATISCH / datei).resolve()
        if not pfad.is_relative_to(STATISCH.resolve()) or not pfad.is_file():
            return Response(status_code=404)
        return FileResponse(pfad, headers={"Cache-Control": "public, max-age=604800"})

    @app.get(f"{pfad}/gesundheit")
    async def gesundheit() -> dict:
        return {"dienst": e.kennung, "fassung": __version__}

    return app
