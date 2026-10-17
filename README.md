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

## Einbinden

In der `pyproject.toml` einer App:

```toml
dependencies = ["appkern @ https://github.com/HalloWelt42/appkern/archive/refs/heads/main.tar.gz"]
```

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
