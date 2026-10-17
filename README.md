# Appkern

Gemeinsame Bausteine der eigenen Apps. Jede App hält ihre Dateien in der
[Kellerwolke](https://github.com/HalloWelt42/kellerwolke) und holt KI über die
[Leitstelle](https://github.com/HalloWelt42/leitstelle); der Appkern bietet beides einmal, getestet, für alle. So
schreibt keine App ihren eigenen Zugang, und eine Änderung an der Kellerwolke oder der Leitstelle wird an einer
Stelle nachgezogen.

## Rollen

| Programm | Aufgabe |
|---|---|
| Kellerwolke | hält die Dateien: ablegen, ausliefern, versionieren, suchen; je App ein eigener Zweig `Apps/<App>` |
| Leitstelle | verteilt Aufträge an die KI-Dienste |
| [Maschinenraum](https://github.com/HalloWelt42/maschinenraum) | regelt die KI-Dienste eines Rechners |
| [Stellwerk](https://github.com/HalloWelt42/stellwerk) | startet die Apps |
| Appkern | die Bausteine, aus denen jede App ihren Zugang zu all dem baut: Kellerwolke, Leitstelle, Anmeldung, Aufträge, Einstellungen, Protokoll, App-Verzeichnis |

## Kellerwolke-Zugang

Eine App bekommt in der Kellerwolke unter Einstellungen, Zugänge einen Schlüssel. Er erlaubt Schreiben im eigenen
Zweig, Lesen unter `Apps` und alles, was das Konto zusätzlich freigibt (etwa einen gemeinsamen Arbeitsordner).

```python
from pathlib import Path
from appkern.kellerwolke import Kellerwolke, StandVeraltet, pfad_aus

async with Kellerwolke("http://192.168.178.49:39277", schluessel) as kw:
    ich = await kw.ich()                                   # App, Konto, freigegebene Ordner
    ordner = await kw.ordner(pfad_aus(ich.zweig, "Aufnahmen"))
    ton = await kw.schreiben(pfad_aus(ordner.pfad, "termin.wav"), Path("termin.wav"), nur_neu=True)
    text = await kw.schreiben(pfad_aus(ordner.pfad, "termin.txt"), "Hallo".encode(), nur_neu=True)
    await kw.herkunft_setzen(text.id, ton.id, "transkript_zu")
    await kw.felder_setzen(text.id, {"sprache": "de"})

    try:
        await kw.neue_version(text.id, "Neu".encode(), stand=text.etag)
    except StandVeraltet:
        ...                                                 # jemand war schneller: neu lesen, dann schreiben

    async for stand in kw.beobachten(ordner.id):            # neue und geänderte Dateien, ohne Abfrageschleife
        for e in stand.eintraege:
            ...
```

| Bereich | Inhalt |
|---|---|
| Lesen | `ich`, `knoten`, `pfad`, `finden`, `kinder`, `alle_kinder` (seitenweise), `lesen` (Strom, auch Bereiche), `lesen_ganz`, `herunterladen` (nie halb) |
| Schreiben | `ordner` (Pfad mit allen Teilen), `schreiben` (aus Bytes, Datei oder Strom, ohne Gesamtpuffer), `neue_version`, `felder_setzen`, `loeschen` (in den Papierkorb des Kontos) |
| Zusammenarbeit | `sperren` und `entsperren` für lange Arbeiten, `herkunft_setzen`, `herkunft`, `herkunft_entfernen`, `suchen` nach Feldern |
| Änderungen | `aenderungen` (seit einem Stand), `ereignisse` (eine Verbindung), `beobachten` (verbindet sich nach einem Abbruch neu und setzt am letzten Stand fort) |
| Versionen | `versionen` (neueste zuerst, aktuelle markiert), `version_lesen` (Strom, auch Bereiche), `version_ganz`; zurückholen heißt: alten Inhalt als `neue_version` schreiben |

Überschreiben geht nur mit dem zuletzt gelesenen Stand (`stand=knoten.etag`); so gewinnt von zwei gleichzeitigen
Schreibern genau einer. Fehler kommen als eigene Arten: `NichtErreichbar` (später erneut versuchen),
`SchluesselUngueltig`, `KeinRecht`, `NichtGefunden`, `Konflikt`, `StandVeraltet`, `StandFehlt`, `Gesperrt`,
`ZuGross`, `Ungueltig`. Der Schlüssel erscheint in keiner Ausgabe.

## Leitstellen-Zugang

Eine App bekommt in der Leitstelle unter Anwendungen einen Schlüssel. Sprachmodelle gehen über die Fassade im
OpenAI-Format, Dienste mit eigener Schnittstelle (Sprechen, Hören, Bild) über `/v1/dienste/<name>/...`; die Leitstelle
wählt Dienst, Modell und Rechner. Jeder Auftrag trägt den Namen der App und einen Titel.

```python
from pathlib import Path
from appkern.leitstelle import Ende, Halt, Leitstelle, Nachricht, Stueck, Wartet

async with Leitstelle("http://192.168.178.49:8530", schluessel, "Transkription") as ls:
    antwort = await ls.chat([Nachricht.system("Korrigiere nur Rechtschreibung."), text], titel="Korrektur")

    async for e in ls.chat_strom([frage], titel="Zusammenfassung", prioritaet="hintergrund"):
        if isinstance(e, Wartet): ...                    # "Modell wird geladen, etwa 40 s" zeigen
        if isinstance(e, Stueck): ...                    # Text anhängen
        if isinstance(e, Ende) and e.abgebrochen: ...    # in der Leitstelle abgebrochen: Teiltext behalten

    hoeren = ls.dienst("klangwerk-hoeren")
    with open("termin.wav", "rb") as datei:
        ergebnis = await hoeren.json("POST", "/stt", titel="Folge 12", data={"language": "de"},
                                     files={"file": ("termin.wav", datei, "audio/wav")})
```

| Bereich | Inhalt |
|---|---|
| Sprachmodelle | `chat` (am Stück), `chat_strom` (`Stueck`, `Wartet`, `Ende`), `einbetten`, `modelle` (lädt nichts, auch als Gesundheitsprüfung) |
| Dienste | `dienst(name)` mit `anfrage`, `json`, `strom`, `herunterladen` (nie halb) |
| Aufträge | Titel `"<App>: <Titel>"`, Priorität `hintergrund`, `normal`, `hoch`, `dringend` (senkt die Vorgabe der App, hebt sie nie) |

Was der Zugang bewusst nicht tut: keine Lese-Zeitgrenze für Arbeit (nur 10 s für den Verbindungsaufbau), keine
Wiederholung von selbst, kein Laden oder Entladen von Modellen. Fehler kommen nach dem Grundwort der Leitstelle als
eigene Arten: `SchluesselUngueltig`, `NichtErlaubt`, `KeinModell`, `Gesperrt` und `Halt` (mit `nochmal_in` aus
`Retry-After`), `DienstWeg`, `DienstFehler`, `Abgebrochen`, `Ungueltig`, `NichtGefunden`, `NichtErreichbar`. Die Tests
laufen gegen eine nachgestellte Fassade, nie gegen die echte Leitstelle.

## Aufträge

Lange Arbeit einer App (Transkribieren, Vertonen, Stapel) läuft als Auftrag: persistent in der eigenen Datenbank der
App (`appkern.datenbank`, eine SQLite-Datei), mit Phasen für die Schrittanzeige, Fortschritt als Ereignisstrom,
Abbruch, Wiederholen und Fortsetzen nach einem Neustart.

```python
from pydantic import BaseModel
from appkern.auftraege import Art, Auftraege, Kontext, Phase
from appkern.auftraege.api import auftrags_router
from appkern.datenbank import Datenbank

class Eingabe(BaseModel):
    datei: str

async def transkribieren(k: Kontext):
    await k.fortschritt(0.0, "Hören", phase="hoeren")
    for n, abschnitt in enumerate(abschnitte(k.eingabe.datei)):
        if n < k.zwischenstand.get("fertig", 0):
            continue                                   # nach Fehler oder Neustart: schon erledigt
        await k.pruefen()                              # Haltepunkt für den Abbruch
        ...
        await k.merken(fertig=n + 1)
        await k.fortschritt((n + 1) / gesamt, f"Abschnitt {n + 1}")
    return {"woerter": 1234}

db = await Datenbank("daten/app.sqlite").oeffnen()
auftraege = Auftraege(db, [Art("transkribieren", "Transkribieren", transkribieren, eingabe=Eingabe,
                                phasen=[Phase(schluessel="hoeren", titel="Hören", symbol="ear-listen")],
                                fortsetzbar=True, nach_neustart="fortsetzen")])
await auftraege.starten()                              # im Lebenszyklus; beim Beenden auftraege.stoppen()
app.include_router(auftrags_router(auftraege, abhaengigkeiten=[Depends(anmeldung)]))
await auftraege.einreihen("transkribieren", {"datei": "Apps/Transkription/Folge 12.wav"}, titel="Folge 12")
```

| Teil | Inhalt |
|---|---|
| Zustände | `wartet`, `laeuft`, `fertig`, `fehler` (mit Ursache, nie leer), `abgebrochen`, `unterbrochen` |
| Kontext | `eingabe` (Modell der Art), `fortschritt` (gedrosselt, Phasenwechsel immer), `merken` (Zwischenstand), `pruefen` (Abbruch) |
| Neustart | je Art `nach_neustart="fortsetzen"` (wieder einreihen, Zwischenstand bleibt) oder `"anhalten"` (unterbrochen, Wiederholen ist ein Klick) |
| Schnittstelle | `GET /api/v1/auftraege` (seitenweise, Filter), `GET .../{id}`, `POST .../{id}/abbrechen`, `POST .../{id}/wiederholen`, `DELETE .../{id}`, `GET .../ereignisse` (Server-Sent Events) |

Abgebrochen wird gemeinsam an Haltepunkten, nie mit einer Uhr. Wie viele Aufträge gleichzeitig laufen, sagt
`gleichzeitig` (Vorgabe 1); beendete Aufträge räumt `aufraeumen` nach `aufbewahren_tage` aus der Liste. Die
Schnittstelle braucht den Zusatz `appkern[web]` (FastAPI).

## Einstellungen

Jede App beschreibt ihre Einstellungen als Pydantic-Modell; die Oberfläche baut ihre Seite aus `felder()`, alles ist
dort änderbar. Ein Wert kommt aus der Datenbank der App (in der Oberfläche gesetzt), sonst aus der Umgebung
(`<PRAEFIX><FELD>`, etwa für den ersten Start), sonst aus der Vorgabe.

```python
from typing import Literal
from pydantic import BaseModel, Field, SecretStr
from appkern.einstellungen import Einstellungen
from appkern.einstellungen.api import einstellungs_router

class AppEinstellungen(BaseModel):
    leitstelle_adresse: str = Field("http://192.168.178.49:8530", title="Leitstelle", json_schema_extra={"gruppe": "Verbindungen"})
    leitstelle_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel der Leitstelle")
    sprache: Literal["de", "en"] = Field("de", title="Sprache")

einstellungen = Einstellungen(db, AppEinstellungen, umgebung_praefix="TRANSKRIPTION_")
await einstellungen.starten()
einstellungen.bei_aenderung(lambda stand, geaendert: ...)   # etwa den Leitstellen-Zugang neu aufbauen
app.include_router(einstellungs_router(einstellungen, abhaengigkeiten=[Depends(anmeldung)]))
```

Geändert wird alles oder nichts (`aendern` prüft die Werte zusammen; `None` setzt zurück, ein leeres Geheimnis bleibt
unverändert). Geheimnisse (`SecretStr`) gehen nur verdeckt hinaus, bis auf die letzten vier Zeichen;
`GET /api/v1/einstellungen/geheimnis/{name}` deckt eines auf (das Auge in der Oberfläche).

## Protokoll

Was in der App geschah, mit Ereignis (`auftrag.fertig`, `datei.hochgeladen`), Stufe (`info`, `warnung`, `fehler`),
Bezug und Text; seitenweise, nach Ereignisanfang, Stufe, Bezug, Tag und Text filterbar. Eintragen wirft nie.
`Auftraege(..., protokoll=protokoll)` trägt jedes Ende eines Auftrags ein. Schnittstelle: `protokoll_router`
(`GET /api/v1/protokoll`).

## App-Verzeichnis

Wo die Schnittstelle einer anderen App liegt, ohne fest verdrahtete Adresse: eine in den Einstellungen eingetragene
Adresse geht vor, sonst fragt `Verzeichnis` das Stellwerk dieses Rechners (Teil `backend` der App, Antwort 30 s
gemerkt; ist das Stellwerk kurz weg, gilt der letzte Stand).

```python
from appkern.verzeichnis import Verzeichnis

verzeichnis = Verzeichnis(eingetragen={"stimmenausgabe": "http://studio:8611"})
adresse = await verzeichnis.adresse("transkription")      # etwa http://127.0.0.1:8601
```

## Anmeldung

Die Apps haben keine eigenen Konten: man meldet sich mit dem Kellerwolke-Konto an, mit Passwort oder als gekoppeltes
Gerät (Code aus der Kellerwolke, Einstellungen, Geräte). Die App reicht beides an die Kellerwolke weiter und prüft
jede Anfrage mit deren Token (kurz gemerkt). Nutzen darf die App das Konto, dem ihr App-Schlüssel gehört, dazu weitere
aus den Einstellungen; ein anderes Konto wird abgewiesen und seine eben entstandene Sitzung sofort beendet.

```python
from appkern.anmeldung import Anmeldung
from appkern.anmeldung.api import angemeldet, anmeldungs_router

ich = await kellerwolke.ich()                                   # Konto des App-Schlüssels
anmeldung = Anmeldung("https://192.168.178.49:39280", lambda: {ich.konto, *einstellungen.stand.weitere_konten})
app.include_router(anmeldungs_router(anmeldung))               # POST /api/v1/anmeldung, .../koppeln, .../abmelden, .../zugang
pflicht = Depends(angemeldet(anmeldung))                       # für alle eigenen Endpunkte
lesen = Depends(angemeldet(anmeldung, cookie=True))           # für Inhaltsadressen unter /api/v1/inhalt
```

Auf dem iPhone hat jede Web-App vom Home-Bildschirm ihren eigenen Speicher; ein Telefon wird deshalb je App einmal
gekoppelt, immer mit dem Kellerwolke-Konto.

Andere Apps sprechen eine App mit ihrem App-Schlüssel der Kellerwolke an (`Authorization: Bearer kw_app_...`). Die App
fragt die Kellerwolke, wem der Schlüssel gehört, und lässt dieselben Konten zu wie in der Oberfläche; `konto.app` nennt
dann die rufende App. Was nur in die Oberfläche gehört (Einstellungen mit Geheimnissen, das Inhalts-Cookie), schützt
`angemeldet(anmeldung, nur_menschen=True)`; das Gerüst bietet dafür `geruest.mensch` neben `geruest.pflicht`.

## Gerüst einer App

`appkern.app.Geruest` verdrahtet alle Bausteine einmal; eine App schreibt danach nur noch ihr Fachliches.

```python
from pathlib import Path
from pydantic import Field
from appkern.app import Geruest, Grundeinstellungen

class TranskriptionEinstellungen(Grundeinstellungen):      # Kellerwolke, Leitstelle, weitere Konten sind schon da
    sprache: str = Field("de", title="Sprache")

geruest = Geruest(name="Transkription", kennung="transkription", rolle="macht aus Ton Text", fassung="0.1.0",
                  symbol="fa-closed-captioning", daten=Path("daten"), einstellungen=TranskriptionEinstellungen,
                  arten=[...], oberflaeche=Path("../frontend/dist"))
app = geruest.fastapi()
app.include_router(eigener_router)                          # Endpunkte mit dependencies=[geruest.pflicht]
geruest.oberflaeche_ausliefern(app)                         # zuletzt
```

| Teil | Inhalt |
|---|---|
| Einstellungen | `Grundeinstellungen` (Kellerwolke, Leitstelle, Zertifikatsstelle, weitere Konten) plus die der App; Zugänge werden nach jeder Änderung neu aufgebaut |
| Erste Einrichtung | `POST /api/v1/einrichtung` mit Kellerwolke und App-Schlüssel, nur vom Rechner der App und nur, solange nichts eingetragen ist |
| Anmeldung | Besitzer ist das Konto des App-Schlüssels; Anmelden, Koppeln, Abweisungen und Abmelden stehen im Protokoll |
| Schnittstellen | `/api/v1/app`, `/api/v1/ich`, `/api/v1/verbindungen`, Anmeldung, Aufträge, Einstellungen, Protokoll |
| Betrieb | Datenbank `daten/<kennung>.sqlite`, tägliches Aufräumen, Auslieferung der gebauten Oberfläche |

Im Gerüst stehen `geruest.kellerwolke`, `geruest.leitstelle`, `geruest.auftraege`, `geruest.protokoll`,
`geruest.einstellungen.stand` und `geruest.verzeichnis` bereit.

## Oberfläche

Die Oberflächen der Apps teilen Gestaltung und Schale aus einer Quelle, dem npm-Paket `appkern-oberflaeche` in diesem
Repo (Ordner `oberflaeche`, Entwurf in `oberflaeche/mockups`, freigegeben am 17.10.2026). Die Schale bringt mit:
erste Einrichtung, Anmeldung mit dem Kellerwolke-Konto (Passwort oder Code), Kopf mit Rolle, Verbindungen und
laufenden Aufträgen, Band bei fehlender Verbindung, Navigation, Aufträge mit Schritten und Leiste, erzeugte
Einstellungen (Geheimnisse verdeckt mit Auge), Protokoll, Schriftgröße und Thema je Gerät, eine eigene Ansicht fürs
Telefon mit Reitern. Barlow und die Symbole kommen über npm.

```svelte
<script lang="ts">
  import { Schale, type Bereich } from "appkern-oberflaeche";
  import Aufnahmen from "./seiten/Aufnahmen.svelte";
  const bereiche: Bereich[] = [{ schluessel: "aufnahmen", titel: "Aufnahmen", symbol: "fa-microphone-lines", seite: Aufnahmen, reiter: true }];
</script>

<Schale {bereiche} />
```

In `package.json` der App: `"appkern-oberflaeche": "github:HalloWelt42/appkern"`; im Einstieg
`import "appkern-oberflaeche/stil.css"`. Die Schale bekommt die Fassung, mit der die Oberfläche gebaut wurde
(`<Schale {bereiche} fassung={__APP_FASSUNG__} />`, eingebaut über `define` in `vite.config.ts` aus `version.json`).
Meldet der Server eine andere, lädt die Seite von selbst neu: beim Start sofort, sonst beim nächsten Seitenwechsel
oder wenn das Fenster wieder nach vorn kommt, je Fassung nur einmal; solange `ruhig()` der App nein sagt (etwa
während einer Aufnahme), wartet es. Kein Nutzer muss nach dem Ausrollen selbst neu laden. Für eigene Seiten stehen `hole`, `json`, `gehe`, `sitzung`, `auftraege`,
`AuftragZeile` und `Schritte` bereit.

## Neue App aus der Vorlage

```bash
.venv/bin/python -m appkern.vorlage --name Transkription --kennung transkription --rolle "macht aus Ton Text" \
    --symbol fa-closed-captioning --port 8601 --ziel ~/Entwicklung/Apps
```

Es entsteht eine lauffähige App: Backend auf dem Gerüst mit einem Probeauftrag, Oberfläche in der Schale,
Symbolsatz für alle Geräte (aus dem Font-Awesome-Symbol auf der App-Farbe, auch für den iPhone-Startbildschirm),
`stellwerk.toml`, `einrichten.sh`, Test und Verbundtest. `--appkern-lokal .` lässt Backend und Oberfläche auf diese
Arbeitskopie zeigen statt auf GitHub.

## Einbinden

In der `pyproject.toml` einer App:

```toml
dependencies = ["appkern[web] @ https://github.com/HalloWelt42/appkern/archive/refs/heads/main.tar.gz"]
```

Ohne `[web]` fehlen nur die FastAPI-Schnittstellen; die Zugänge und die Aufträge selbst gehen auch ohne.

## Tests

```bash
.venv/bin/python -m pytest
```

Die Einheitstests laufen gegen eine nachgestellte Schnittstelle. Der Verbundtest spricht mit einer echten Kellerwolke
(Entwicklungsinstanz) und braucht dafür eine Datei `.env.test`, die nicht ins Repo gehört:

```
KELLERWOLKE_ADRESSE=http://127.0.0.1:22940
KELLERWOLKE_SCHLUESSEL=kw_app_...
```

Ohne sie wird er übersprungen. Jeder Testlauf arbeitet in eigenen Ordnern im Zweig der Test-App und legt sie danach in
den Papierkorb des Kontos; endgültig leert ihn das Konto selbst.

## Lizenz

Nicht-kommerzielle Lizenz, siehe [LICENSE](LICENSE).
