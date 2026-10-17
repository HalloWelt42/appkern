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
| Appkern | die Bausteine, aus denen jede App ihren Zugang zu all dem baut |

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
