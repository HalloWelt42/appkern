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
| Schreiben | `ordner` (Pfad mit allen Teilen), `schreiben` (aus Bytes, Datei oder Strom, ohne Gesamtpuffer), `neue_version`, `felder_setzen`, `umziehen` (verschieben und umbenennen, Begleiter ziehen mit), `loeschen` (in den Papierkorb des Kontos) |
| Zusammenarbeit | `sperren` und `entsperren` für lange Arbeiten, `herkunft_setzen`, `herkunft`, `herkunft_entfernen`, `suchen` nach Feldern |
| Änderungen | `aenderungen` (seit einem Stand), `ereignisse` (eine Verbindung), `beobachten` (verbindet sich nach einem Abbruch neu und setzt am letzten Stand fort) |
| Versionen | `versionen` (neueste zuerst, aktuelle markiert), `version_lesen` (Strom, auch Bereiche), `version_ganz`; zurückholen heißt: alten Inhalt als `neue_version` schreiben |
| Begleitdateien | `begleiter` (einer Hauptdatei), `begleiter_schreiben` (je Rolle; den Namen aus Stamm und Zusatz vergibt die Kellerwolke: `Runde.wav` mit `.transkript.json` ergibt `Runde.transkript.json`), `begleiter_anhaengen` (vorhandene Datei kommt neben die Hauptdatei), `begleiter_loesen` (wird eine gewöhnliche Datei) |
| Anfragen | `aktionen_melden`, `anfragen_holen` (lange Abfrage), `anfrage`, `anfrage_annehmen`, `anfrage_melden`, `weitergeben`; `mit_anfrage(id)` ist derselbe Zugang mit dem Recht genau dieser Anfrage (die angefragte Datei lesen, ihre Begleiter schreiben) |
| Dateiwahl | `wahl` und `waehlen` mit der Anmeldung des Menschen an dieser App: blättern zeigt nur Namen, die Wahl stellt eine Anfrage |

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
| Werkzeuge | `tools` geht als Option mit; die Antwort trägt `werkzeugaufrufe` (im Strom zusammengesetzt in `Ende`), Ergebnisse gehen als `Nachricht.ergebnis(aufruf_id, text)` zurück, die Antwort des Modells als `Nachricht.assistent(text, werkzeugaufrufe)` |
| Lage | `lage` an Antwort, `Ende` und `Einbettungen` (Kopf `X-Leitstelle-Lage`: ruhig, angespannt, engpass); Stapelarbeit startet bei angespannt oder engpass nichts Neues |
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
| Schnittstelle | `GET /api/v1/auftraege` (seitenweise, Filter), `GET .../zahlen` (Zahl je Zustand in einer Abfrage), `GET .../{id}`, `POST .../{id}/abbrechen`, `POST .../{id}/wiederholen`, `DELETE .../{id}`, `GET .../ereignisse` (Server-Sent Events) |

Ein erwarteter, fachlicher Fehlschlag (die Quelle antwortet 404, die Datei passt nicht) geht als `AuftragFehler` oder
eine eigene Art davon (`raise QuelleWeg("Die Seite gibt es nicht mehr (404)") from f`): der Auftrag endet mit genau
dieser Meldung, im Log steht eine Warnung ohne Spur. Jeder andere Fehler gilt als unerwartet und steht mit Spur im Log
und im Auftrag.

Die Datenbank schreibt nacheinander über eine Verbindung (`ausfuehren`, `transaktion`, `einrichten`) und liest über
eigene Verbindungen, die nur lesen dürfen (`zeile`, `zeilen`; `leser`, Vorgabe 4). Im WAL-Modus sieht jedes Lesen den
zuletzt bestätigten Stand: eine lange Abfrage hält weder andere Seiten noch das Schreiben auf, eine laufende
Schreibtransaktion kein Lesen. Wer nicht mehr wartet, bricht sein Lesen in SQLite ab. Schreiben über `zeile` scheitert
laut. Im Speicher (`":memory:"`, Tests) geht alles über eine Verbindung.

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
    sprache: Literal["de", "en"] = Field("de", title="Sprache",
                                         json_schema_extra={"beschriftungen": {"de": "Deutsch", "en": "Englisch"}})
    schwelle: float = Field(0.7, ge=0, le=1, title="Schwelle", json_schema_extra={"schritt": 0.05})

einstellungen = Einstellungen(db, AppEinstellungen, umgebung_praefix="TRANSKRIPTION_")
await einstellungen.starten()
einstellungen.bei_aenderung(lambda stand, geaendert: ...)   # etwa den Leitstellen-Zugang neu aufbauen
app.include_router(einstellungs_router(einstellungen, abhaengigkeiten=[Depends(anmeldung)]))
```

Geändert wird alles oder nichts (`aendern` prüft die Werte zusammen; `None` setzt zurück, ein leeres Geheimnis bleibt
unverändert). Geheimnisse (`SecretStr`) gehen nur verdeckt hinaus, bis auf die letzten vier Zeichen;
`GET /api/v1/einstellungen/geheimnis/{name}` deckt eines auf (das Auge in der Oberfläche). Auswahlfelder zeigen ihre
`beschriftungen` (nie den Schlüssel), Zahlen gehen in `schritt` und bleiben in den Grenzen aus `ge` und `le`, mit
`einheit` hinter dem Wert. Was das System selbst kennt, ist kein Textfeld: `einstellungen.anbieten(name, anbieter)`
liefert live eine Auswahl (`Angebot` mit `Option`en aus Wert, Name und Hinweis) und was gerade gilt (`stand`), etwa
"verbunden: Apps/Transkription" oder "gefunden: /opt/homebrew/bin/ffmpeg"; "Eigener Wert" bleibt möglich. Das Gerüst
bietet Adressen und Zertifikatsstelle selbst an und hilft mit `geruest.leitstelle_angebot("hoeren")` (Dienste und
Modelle der Leitstelle mit dieser Fähigkeit, lesbar benannt). In der Oberfläche ist jede Gruppe ein Reiter mit eigener
Adresse (`/einstellungen/<gruppe>`), in voller Breite.

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

## Ton

Gerechnet wird an genau einem Ort (Nutzer 18.10.2026: "pi ist nur datenlieferant"): die Apps auf dem Pi nutzen die
**Tonarbeit** über den **Tondienst** auf dem Mac (Dienst `klangwerk-ton` im Maschinenraum, über die Leitstelle wie die
Sprachdienste); ffmpeg gibt es in ihren Containern nicht. `appkern.ton` (Zusatz `appkern[ton]`):

- `Tonarbeit` mit drei Arbeitsschritten, jeder nimmt seine Dateien mit und schreibt seine Ergebnisse an Orte, die der
  Aufrufer nennt:
  - `aufbereiten(quelle, Aufbereiten(ausgaben=[...], messen=Messen(...)), ziele)`: eine Datei (auch Video), beliebig
    viele `Ausgabe`n (Format, Behälter, Zeitbereich; auf Wunsch begrenzt, an den Rändern geblendet, mit Vor- und
    Nachlauf) und Messungen (Eigenschaften immer; Pausen, Wellenform, Pegelverlauf je Rahmen, laute Spanne);
  - `blenden(dateien, Blenden(stuecke=[Stueck(datei, von_s, bis_s)], ...), ziel)`: mit Gleichleistungsblende zu einem;
  - `legen(dateien, Legen(lagen=[Lage(datei, beginn_s, stauchung)], mindestens_s=, spitze=, format=, wellenform=), ziel)`:
    an ihre Zeiten, gestaucht, mit glatten Rändern, begrenzt, genau einmal ins Zielformat.
  - dazu `eigenschaften`, `dauer`, `wandeln` als häufige Fälle von `aufbereiten`.
- `TonDienst(leitstelle, name)`: die Tonarbeit der Apps über die Leitstelle; Tonfehler des Dienstes kommen als
  `TonFehler` an. `GeduldigeTonarbeit(ton, melden=, pruefen=)` wiederholt jeden Schritt, solange die Leitstelle sagt,
  dass es gerade nicht geht (`appkern.leitstelle.geduldig`: Halt, Dienst weg oder noch nicht gemeldet, nicht
  erreichbar; nach Retry-After, höchstens so lange, wie die Einstellung "Geduld bei Ausfall" der App sagt, Vorgabe
  30 Minuten; schläft der Rechner mit dem Dienst, ohne Grenze, bis er wach ist). `TonHier` rechnet selbst (ffmpeg und numpy) und läuft nur im Tondienst und in Tests; seine Routen
  stehen in `appkern.ton.gegenseite` (Zusatz `appkern[tondienst]`, Wirt ist das Klangwerk).
- `Tonformat(rate, kanaele, kodierung, bitrate)`: ein Ziel als Modell; feste Formate `HOEREN` (16 kHz mono PCM16, für
  die Spracherkennung), `ARBEIT` (24 kHz mono Gleitkomma) und `ABSPIELEN` (44,1 kHz mono PCM16, samplegenau springbar).
- `Abspielfassungen`: Zwischenspeicher je Quelle und Stand mit Obergrenze, erzeugt über die Tonarbeit oder aus einer
  Ausgabe derselben Aufbereitung übernommen (`uebernehmen`).
- `wav.dauer`, `wav.ausschnitt`: reine Datenarbeit an fertigen PCM-WAV-Dateien (Bytekopie, kein Dekodieren); das darf
  auf dem Pi laufen.
- `Ton` ist die ffmpeg-Schicht unter `TonHier` (Resampling mit soxr, wenn ffmpeg es hat, sonst dem eingebauten in hoher
  Qualität; Ausgaben entstehen unter einem Zwischennamen; mp4-Behälter mit dem Inhaltsverzeichnis vorn).

Die Tests wandeln echte Töne hin und zurück und messen Frequenz, Dauer und Format; dieselben Aufträge laufen einmal
hier und einmal über das Protokoll (TonDienst gegen die Routen, über eine Leitstelle im Prozess) und müssen gleich
ausgehen.

## Anfragen aus der Kellerwolke

Was eine App mit Dateien kann, meldet sie der Kellerwolke als Aktion; das Dateimenü der Kellerwolke bietet es an, das
Ergebnis landet als Begleitdatei neben der Datei. Jedes Angebot nennt die Art des Auftrags, die es ausführt; das
Gerüst meldet die Aktionen beim Start, holt Anfragen ab (auch aus der Dateiwahl in der App), reiht sie als Aufträge ein
und meldet Fortschritt und Ende zurück. Die Arbeit liest und schreibt nur mit dem Recht ihrer Anfrage:

```python
from appkern.anfragen import Angebot, AnfrageEingabe
from appkern.kellerwolke import Aktion

async def transkribieren(k: Kontext):
    zugang = geruest.kellerwolke.mit_anfrage(k.eingabe.anfrage_id)   # nur diese Datei und ihre Begleiter
    ...
    b = await zugang.begleiter_schreiben(k.eingabe.knoten_id, "transkript", ".transkript.json", daten)
    return {"ergebnis_id": str(b.id)}                                # die Kellerwolke zeigt den Begleiter als Ergebnis

geruest = Geruest(..., arten=[Art("aus_anfrage", "Transkribieren", transkribieren, eingabe=AnfrageEingabe,
                                  nach_neustart="fortsetzen")],
                  angebote=[Angebot(Aktion(kennung="transkribieren", titel="Transkribieren", titel_erneut="Neu transkribieren",
                                           symbol="fa-closed-captioning", typen=("audio/*", "video/*"), rolle="transkript"),
                                    auftrag="aus_anfrage"),
                            Angebot(Aktion(kennung="oeffnen", titel="In Transkription öffnen", symbol="fa-up-right-from-square",
                                           typen=("audio/*", "video/*"), art="oeffnen", rolle="transkript"))])
```

Mit Angeboten bekommt die App `GET` und `POST /api/v1/kellerwolke/wahl` (Dateiwahl), `GET
/api/v1/kellerwolke/anfragen/{id}` (Stand und Frist) und `POST /api/v1/kellerwolke/anfragen/{id}/oeffnen` (die
Kellerwolke führt den Browser zu `<adresse>/anfrage/<id>`; die Adresse der App steht in den Einstellungen und wird beim
ersten Öffnen nach der Anmeldung eingetragen). Die Schale nimmt eine solche Anfrage auf dem Weg `/anfrage/<id>` an und
fragt die App über `oeffnen`, welche ihrer Ansichten die Datei zeigt (`<Schale {bereiche} {oeffnen} />`, etwa
`` (a) => `aufnahmen/${a.knoten_id}/anfrage/${a.id}` ``). In der Oberfläche stehen dafür `wahl`, `waehlen`, `anfrage`
und `istMedium` bereit. Bricht der Mensch die Anfrage in der Kellerwolke ab, bricht der Auftrag ab; ist die App aus,
wartet die Anfrage.

## Anmeldung

Die Apps haben keine eigenen Konten: man meldet sich mit dem Kellerwolke-Konto an, mit Passwort oder als gekoppeltes
Gerät (Code aus der Kellerwolke, Einstellungen, Geräte). Die App reicht beides an die Kellerwolke weiter und prüft
jede Anfrage mit deren Token (kurz gemerkt). Nutzen darf die App das Konto, dem ihr App-Schlüssel gehört, dazu weitere
aus den Einstellungen; ein anderes Konto wird abgewiesen und seine eben entstandene Sitzung sofort beendet.

Die Anmeldung gilt nur für diese App (Kellerwolke ab 0.81): das Gerüst nennt beim Anmelden und Koppeln den Namen ihres
Zugangs, und die Kellerwolke gibt mit einer solchen Sitzung keine Dateien heraus. An Dateien kommt die App nur über
ihren App-Schlüssel und offene Anfragen. Eine Sitzung, die nicht für diese App gilt (etwa eine ältere volle), beendet
die App sofort; dann meldet man sich einmal neu an.

```python
from appkern.anmeldung import Anmeldung
from appkern.anmeldung.api import angemeldet, anmeldungs_router

ich = await kellerwolke.ich()                                   # Konto des App-Schlüssels
anmeldung = Anmeldung("https://192.168.178.49:39280", lambda: {ich.konto, *einstellungen.stand.weitere_konten})
app.include_router(anmeldungs_router(anmeldung))               # POST /api/v1/anmeldung, .../koppeln, .../abmelden, .../zugang
pflicht = Depends(angemeldet(anmeldung))                       # für alle eigenen Endpunkte
lesen = Depends(angemeldet(anmeldung, cookie=True))           # für Inhaltsadressen unter /api/v1/inhalt
```

Ist die Kellerwolke gerade nicht erreichbar, gilt eine Anmeldung, die sie früher bestätigt hat, aus dem Merker weiter,
bis "Anmeldung bei Ausfall" (Einstellungen, Zugang, Vorgabe 24 Stunden, 0 schaltet es ab) nach der letzten Bestätigung;
nachgefragt wird dann im Hintergrund, keine Anfrage wartet darauf. Das gilt ebenso für App-Schlüssel anderer Apps. So
bleibt die App bedienbar, und eine falsche Adresse der Kellerwolke lässt sich in den Einstellungen berichtigen; die
Verbindungen zeigen die Kellerwolke dabei als nicht erreichbar. Neue Anmeldungen und nie bestätigte Token brauchen die
Kellerwolke (503). Der Merker lebt im Speicher der App, ein Neustart leert ihn.

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
| Einstellungen | `Grundeinstellungen` (Kellerwolke, Leitstelle, Zertifikatsstelle, weitere Konten, Anmeldung bei Ausfall) plus die der App; Zugänge werden nach jeder Änderung neu aufgebaut |
| Erste Einrichtung | `POST /api/v1/einrichtung` mit Kellerwolke und App-Schlüssel, nur solange nichts eingetragen ist. Vom Rechner der App geht sie ohne weiteres; von anderswo (anderes Gerät, hinter einem Vorschaltdienst, in Docker) mit dem einmaligen Einrichtungscode aus einer Datei am Rechner (Modus 0600, je Start neu, `<KENNUNG>_EINRICHTUNGSCODE_DATEI`, Vorgabe `<daten>/einrichtungscode`; wie man sie am Rechner findet: `<KENNUNG>_EINRICHTUNGSCODE_ORT`). App-Angaben (`einrichtungscode`), Protokoll und die Einrichtung der Schale nennen nur den Ort, nie den Code; fünf falsche Codes sperren zehn Minuten, nach der Einrichtung ist die Datei weg (Lehre 34) |
| Anmeldung | Besitzer ist das Konto des App-Schlüssels; Anmelden, Koppeln, Abweisungen und Abmelden stehen im Protokoll |
| Schnittstellen | `/api/v1/app`, `/api/v1/ich`, `/api/v1/verbindungen` (Kellerwolke und Leitstelle nebeneinander geprüft, jede höchstens 10 s), Anmeldung, Aufträge, Einstellungen, Protokoll |
| Schnittstellendoku | `/docs`, `/redoc` und `/openapi.json` nur in der Entwicklung mit `<KENNUNG>_SCHNITTSTELLEN_DOKU=1`; sonst zeigt die App ihren Aufbau niemandem ohne Anmeldung. `app.openapi()` liefert das Schema im Code immer |
| Betrieb | Datenbank `daten/<kennung>.sqlite` (Lesen neben dem Schreiben, `leseverbindungen`, Vorgabe 4), tägliches Aufräumen, Auslieferung der gebauten Oberfläche |
| Begleiter | Hintergrundarbeit der App (`Begleiter` mit `starten`, `verbunden` nach jedem Aufbau der Zugänge, `stoppen`), angemeldet mit `geruest.begleiter_anmelden` vor dem Start; läuft vor den Aufträgen an und nach ihnen aus |

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
`import "appkern-oberflaeche/stil.css"`.

Eine App mit eigener Gestaltung (Fundus in der Gestaltung der Leitstelle) nimmt statt der Schale ihre Bausteine und
zeichnet selbst; die Logik bleibt im Appkern: `sitzungStarten`, `anmelden`, `koppeln`, `einrichtenMit`, `abmelden`,
`auftraegeVerfolgen`, `auftragAbbrechen`, `auftragWiederholen`, `fassungVerfolgen`, `navigationStarten`,
`verbindungen` mit `verbindungenVerfolgen` und `verbindungenPruefen`, `takt`, die Hilfen zum Koppeln und die Texte
`KEINE_VERBINDUNG` und `ANTWORTET_NICHT`. Sie lädt dann `stil.css` nicht. Die Schale bekommt die Fassung, mit der die Oberfläche gebaut wurde
(`<Schale {bereiche} fassung={__APP_FASSUNG__} />`, eingebaut über `define` in `vite.config.ts` aus `version.json`).
Meldet der Server eine andere, lädt die Seite von selbst neu: beim Start sofort, sonst beim nächsten Seitenwechsel
oder wenn das Fenster wieder nach vorn kommt, je Fassung nur einmal; solange `ruhig()` der App nein sagt (etwa
während einer Aufnahme), wartet es. Kein Nutzer muss nach dem Ausrollen selbst neu laden.

Die Adresse im Browser ist ein echter Pfad: der erste Teil wählt den Bereich (`/transkripte`), weitere Teile liest die
Seite aus `navigation.teile` (`/transkripte/<kennung>`); Zurück und Vor im Browser funktionieren, das Backend liefert
für jeden Pfad außerhalb von `/api` die Oberfläche aus, nur nie für eine fehlende Datei: ein Weg mit Dateiendung (etwa
`/manifest.webmanifest`) bekommt 404, Zahlen wie `/transkripte/<kennung>/12.5` bleiben Seiten. Eine Seite, die einen Teil zeigt, setzt `navigation.titel`;
am Telefon steht er im Kopf, mit einem Knopf zurück zum Bereich, und daneben auf Wunsch `navigation.kennzeichen`
(`{ symbol, text }`, etwa woher das Gezeigte kommt). Für eigene Seiten stehen `hole`, `json`, `gehe`,
`adresse`, `navigation`, `sitzung`, `geraet`, `auftraege`, `beiAuftrag` (Ereignisse der Aufträge mithören),
`AuftragZeile`, `Schritte`, `Auswahl` (Aufklappliste statt nativer Auswahlfelder), `Leiste` mit `leisteOeffnen` und
`ereignisseBenennen` (lesbare Namen eigener Protokollereignisse) bereit.

Jede Anfrage (`hole`) hat eine Zeitgrenze (Vorgabe 20 s; für die ganze Oberfläche `anfragenEinstellen({ zeitgrenzeMs })`
im Einstieg, je Anfrage `{ zeitgrenzeMs }`, 0 heißt ohne). Gleiche GET-Anfragen, die schon unterwegs sind, gehen nur
einmal hinaus. Eine Seite holt im Skript mit `seitenSignal()` ein Signal, das beim Verlassen abbricht, und gibt es mit
(`hole(pfad, { signal })`); so wartet keine verlassene Seite auf ihre Antworten. Ob die App selbst antwortet, führt die
Schale an einer Stelle: bleibt die Antwort aus (kein Netz, der Vorschaltdienst meldet 502 bis 504, oder nach einer
überschrittenen Zeitgrenze kommt auch die Probe nicht durch), steht im Kopf "Keine Verbindung zur App" oder "Die App
antwortet nicht" statt der Verbindungen und darunter ein Band mit "Erneut versuchen". Eine Probe fragt dann mit
wachsender Pause nach (2 s, jeweils doppelt so lange, höchstens 60 s); die regelmäßigen Abfragen der Schale
(Verbindungen alle 30 s, Fassung jede Minute, nie zwei gleichzeitig) ruhen so lange, und die Zahlen der Aufträge holt
eine Anfrage höchstens einmal je Sekunde. Sobald die App wieder antwortet, holen Kopf, Aufträge, Protokoll und
Einstellungen von selbst nach, eigene Seiten mit `beiRueckkehr(fn)`. Antwortet die App schon beim Start nicht, zeigt
die Schale das mit "Erneut versuchen" und macht weiter, sobald sie antwortet. Seiten zeigen diesen Zustand nicht noch
einmal: `seitenFehler(f)` ist der Text eines Fehlers für die Seite, leer, wenn die App nicht antwortete
(`ApiFehler.ohneAntwort`) oder die Seite selbst abgebrochen hat. Dazu stehen `verbindung` (`ok`, `meldung`, `prueft`)
und `verbindungPruefen()` bereit.

Breiten: ab 1280 Pixel wie im Entwurf (Navigation mit Text, Leiste daneben); darunter wird die Leiste eine Tafel, die
über den Inhalt fährt (Schleier, Knopf zum Schließen, Escape); unter 1000 Pixel wird die Navigation eine Symbolleiste;
bis 600 Pixel gilt die eigene Telefonansicht (mit dem Finger bis 760 Pixel oder flach im Querformat; ein schmales oder
vergrößertes Fenster am Rechner behält die Rechneransicht). Das Protokoll wird bei wenig Platz eine Liste. Die Fassung der gebauten
Oberfläche steht als Meta `app-fassung` in ihrer Startseite (eingesetzt in `vite.config.ts`); der Server meldet sie in
`/api/v1/app` (`oberflaeche`), und ein Tab vergleicht sich mit ihr. Ist die Oberfläche nach einer neuen Fassung nicht
neu gebaut, steht das als Warnung im Protokoll.

Eigene Reiter in den Einstellungen (`<Schale {bereiche} einstellungen={[{ schluessel, titel, seite }]} />`) stehen
zwischen den erzeugten Gruppen und der Anzeige, für Einstellungen mit eigener Verwaltung (etwa Zugänge mit Schlüsseln
je Gerät).

Gemeinsame Bausteine (Stile in `stil/bausteine.css`, kommen mit `stil.css`): `Spieler` (Wellenform, Sprecherspur,
Marker, Tempo, Tasten; `kompakt` für das Telefon), `Rueckfrage` (vor dem Löschen, im Ablauf statt als Fenster),
`AnfrageBand` (Herkunft und Frist einer aus der Kellerwolke geöffneten Datei), `hochladen` mit Fortschritt (`uploads`),
`arbeit` (Wiedergabe, Aufnahme, Hochladen, ungespeichert: die Schale lädt dann nicht neu), Zeit und Größe zum Lesen
(`marke`, `genau`, `lesen`, `groesse`, `SPRACHEN`, Sprecherfarben `farbe`), Adressen in die Kellerwolke
(`inKellerwolke`, `zurueckZurKellerwolke`) und die Namen der Begleiter-Rollen (`ROLLEN`, `daneben`).

`Dateiwahl` blättert durch die Kellerwolke und lässt Dateien für Aufträge der App wählen; was wählbar ist, woran ein
laufender Auftrag und ein fertiges Ergebnis zu erkennen sind, die Wörter und das Starten beschreibt die App als
`WahlZweck`, ihre Einstellungen reicht sie als Snippet `optionen` herein. `Rekorder` nimmt im Browser auf (Pegel, Marker,
Mikrofon wechseln, Live-Mitschrift, jedes Stück sofort im Gerätespeicher); die App richtet das Aufnehmen einmal mit
`aufnahmeEinrichten({ app, hoeren, name })` ein, legt eine fertige Aufnahme über `ablegen` ab und bietet im Snippet
`danach` an, was damit geschehen soll. Liegengebliebene Aufnahmen holt `gespeicherteAufnahmen` und `aufnahmeAlsDatei`.
Dazu die Listenstile (`.zeile`, `.stand-pille`, `.optionen`, `.knopfzeile`).

## Neue App aus der Vorlage

```bash
.venv/bin/python -m appkern.vorlage --name Transkription --kennung transkription --rolle "macht aus Ton Text" \
    --symbol fa-closed-captioning --port 8601 --ziel ~/Entwicklung/Apps [--ton]
```

Es entsteht eine lauffähige App: Backend auf dem Gerüst mit einem Probeauftrag, Oberfläche in der Schale,
Symbolsatz für alle Geräte (aus dem Font-Awesome-Symbol auf der App-Farbe, auch für den iPhone-Startbildschirm),
`stellwerk.toml`, `einrichten.sh`, Test und Verbundtest mit eigenem Testzugang. Dazu alles, was die Lehren aus den
bisherigen Apps verlangen (`docs/LEHREN.md`): Git-Hook mit Fassung und Prüfungen, `tools/appkern.sh`,
`tools/ausrollen.sh` mit `deploy/ausrollen.toml`, Dockerfile und `compose.pi.yml` mit Caddy davor, Ansichtsprüfung
(`tools/ansicht.sh`, Seiten in `frontend/ansicht.json`) und die Abnahmeliste `docs/ABNAHME.md`. `--ton` gibt der App die
Tonarbeit über den Tondienst (Einstellung `dienst_ton`, kein ffmpeg im Container); das Ausrollen prüft, ob die
Leitstelle den Tondienst meldet. `--appkern-lokal .` lässt Backend und Oberfläche auf diese
Arbeitskopie zeigen statt auf GitHub.

## Werkzeuge der Entwicklung

`python -m appkern.werkzeuge` im Wurzelordner einer App (aus ihrem Backend) oder des Appkerns:

| Befehl | Was |
|---|---|
| `vor-dem-commit` | Fassung hochzählen (nur neue Kennung, wenn `version.json` schon vorgemerkt ist), vormerken, vorgemerkte Dateien prüfen; aufgerufen vom Hook `tools/git-hooks/pre-commit` |
| `pruefen [PFAD ...]` | nur gerade Zeichen; Stil ohne `!important`, ohne einseitige Streifen (erlaubt nur 1px-Trennlinien in `var(--rand)`), ohne Regeln, die nur Klassen der Schale treffen (Svelte-Blöcke nur mit `:global`) |
| `fassung [patch\|minor\|major\|id]` | `version.json` hochzählen |
| `appkern` | Appkern in Oberfläche (package-lock) und Backend (requirements, Archiv des Commits) auf denselben neuesten Commit |
| `ausrollen` | auf den Pi nach `deploy/ausrollen.toml`, mit allen Prüfungen (Ablauf in `appkern/werkzeuge/ausrollen.py`) |

`appkern.testen` hilft den Tests der Apps: Werte des eigenen Testzugangs aus `backend/.env.test`, `aufraeumen`
(Dateien vor Ordnern, mit Wiederholung) und `aktionen_zurueckziehen`. Die Ansichtsprüfung liegt bei der Oberfläche
(`oberflaeche/werkzeuge/ansicht.mjs`).

## Einbinden

In der `pyproject.toml` einer App:

```toml
dependencies = ["appkern[web] @ https://github.com/HalloWelt42/appkern/archive/<commit>.tar.gz"]
```

Ohne `[web]` fehlen nur die FastAPI-Schnittstellen; die Zugänge und die Aufträge selbst gehen auch ohne. `[ton]` bringt
die Tonarbeit mit, `[tondienst]` die Gegenseite für den Wirt des Tondienstes. Immer einen Commit nennen (`tools/appkern.sh` in der App), nie den Zweig: das Archiv eines Zweigs
ändert seinen Namen nie, und Docker baut dann mit dem alten Stand weiter.

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
