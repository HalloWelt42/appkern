# Lehren aus den Apps

Jeder Fehler, der in einer App aufgefallen ist, bekommt hier eine Gegenmaßnahme an einer Stelle, die jede weitere App
von selbst erbt: eine Prüfung (schlägt beim Commit oder Ausrollen an), einen Baustein im Appkern oder eine Datei der
Vorlage. Eine Regel ohne Prüfung ist die schwächste Form und nur dort erlaubt, wo sich nichts prüfen lässt.

Neue Lehren kommen hier hinein, bevor die nächste App beginnt. Erledigt heißt: die Gegenmaßnahme ist gebaut und eine
frisch erzeugte App hat sie.

## Aus der Transkription (17.10.2026)

| Nr | Was geschah | Ursache | Gegenmaßnahme | Art | Stand |
|---|---|---|---|---|---|
| 1 | Auswahl als einseitiger Streifen (`box-shadow: inset 3px 0 0`), vom Nutzer schon immer verboten | Gewohnheit | Stilprüfung lehnt einseitige Rahmen und Schatten sowie `!important` ab | Prüfung (Commit) | offen |
| 2 | Die App-Klasse `.stand` überschrieb die gleichnamige Klasse der Schale, die Statuszeile der Einstellungen lief über | Klassennamen ohne Abgleich | Stilprüfung schneidet die Klassen der App mit denen der Schale; erlaubt sind nur Erweiterungen wie `.knopf.klein` | Prüfung (Commit) | offen |
| 3 | iPhone-Startbildschirm ohne Symbol | iOS nimmt die Symbole aus dem Manifest, diese waren durchsichtig | Symbole des Manifests deckend auf der App-Farbe (`tools/symbole.py`), Ausrollen prüft die Deckkraft | Vorlage, Prüfung (Ausrollen) | Symbole erledigt (0.14.2), Prüfung offen |
| 4 | Ursache des fehlenden Symbols mehrfach geraten (Zertifikat, TLS im App-Server) | Kein Zugriffsprotokoll, also nichts zu messen | Vorne immer ein Caddy mit HTTP/2, TLS aus der Hausstelle und JSON-Zugriffsprotokoll; erst messen, dann ändern | Vorlage (deploy) | offen |
| 5 | Korrekturen im Appkern kamen im Docker-Bau nie an | `appkern @ .../main.tar.gz` ändert sich nie, Docker nahm die alte Schicht | `tools/appkern.sh` bindet Oberfläche und Backend an denselben Commit, Ausrollen prüft die Gleichheit | Vorlage, Prüfung (Ausrollen) | offen |
| 6 | Geänderte Caddy-Konfiguration wirkte nicht | Docker bemerkt Änderungen an eingebundenen Dateien nicht | Ausrollen startet den vorderen Dienst jedes Mal neu | Vorlage (Ausrollen) | offen |
| 7 | Versionssprung und Zeichenprüfung fehlten anfangs | Vorlage ohne `tools/version.sh` und Git-Hooks | beides in die Vorlage | Vorlage | offen |
| 8 | Telefon: Spieler nicht unten, Leiste ohne Gestaltung | Jede App baut die Ansicht mit Fußleiste selbst; Gestaltung hing an `.leiste` statt am Inhalt | Schale bietet die Telefonansicht mit fester Fußleiste und gestaltet den Leisteninhalt selbst | Baustein (Schale) | offen |
| 9 | Löschen fehlte (Aufnahmen, am Telefon), Verwerfen beim Aufnehmen fehlte | Kein Durchgang je Objektart | Abnahmeliste der Vorlage: je Objektart anlegen, ansehen, umbenennen, löschen in den Papierkorb, verwerfen, am Rechner und am Telefon | Vorlage (Abnahme) | offen |
| 10 | Rückfragen fehlten oder drohten als Browser-Dialog | Kein gemeinsamer Baustein | `Rueckfrage` (in der Fläche, mit Schalter und Hinweis) in die Oberfläche des Appkern | Baustein | offen |
| 11 | Liste nach Löschen in der Detailansicht veraltet | Liste lud nur beim ersten Öffnen | Listen laden bei Rückkehr und hören auf Ereignisse (`beiAuftrag`, Journal) | Regel, Muster in der Vorlage | offen |
| 12 | Markierung des gesprochenen Worts verschob den Text, im Dunkeln unlesbar | Hervorhebung mit `padding`, Farbe nur hell geprüft | Ansichtsprüfung: jede Seite in allen Breiten (1920, 1440, 1280, 1100, 900, 390), hell und dunkel; misst seitliches Rollen, Überlauf, Kontrast und Verschiebung beim Zustandswechsel | Prüfung (Werkzeug der Vorlage) | offen |
| 13 | Zustandswechsel beim Aufnehmen ließ das Bild wackeln | Meldungen als Text mit wechselnder Länge | Zustände als Symbole fester Größe mit Erklärung per Klick; die Ansichtsprüfung misst die Verschiebung | Regel, Prüfung | offen |
| 14 | Pegel flach, Wellenform flach | AudioContext außerhalb des Klicks, ohne Verstärkungsregelung; Wellenform linear statt in dB | Rekorder, Spieler, Wellenform und Abspielfassung als gemeinsame Bausteine (`appkern.ton`, Oberfläche) | Baustein | offen |
| 15 | Übernahme scheiterte an der echten alten App | Schein-Gegenstelle nach Annahme gebaut, die echte liefert JSON als Text | Erst eine echte Antwort aufzeichnen, die Schein-Gegenstelle antwortet mit genau dieser | Regel (Testgerüst) | offen |
| 16 | Halbe Übernahme als fertig angezeigt | Ein Kennzeichen für zwei Zustände | Mehrstufige Vorgänge kennzeichnen angefangen und fertig getrennt und lassen sich fortsetzen | Regel (Aufträge) | offen |
| 17 | Transkripte in Unterordnern fielen still aus dem Abgleich | Abgleich verglich nur die oberste Ebene | Test mit Unterordnern in jeder Ablage; künftig ein Baum mit Begleitdateien | Test, Verbund V5 | Abgleich erledigt (0.8.0) |
| 18 | Testordner blieben in der Entwicklungs-Kellerwolke liegen | Aufräumen löschte Ordner vor Dateien | Testgerüst der Vorlage räumt Dateien vor Ordnern und wiederholt | Vorlage (Tests) | offen |
| 19 | Öffnen aus der Kellerwolke fehlte in der echten App, alle Tests grün | Die App trug ihre Adresse beim Aufruf von `/ich` ein; den rief nur der Test, die Oberfläche nie | Die Oberfläche meldet ihre Adresse selbst (`POST /api/v1/adresse` mit `location.origin`, 0.17.1); Verbundtests gehen nur Wege, die auch die Oberfläche geht, und jede neue Fähigkeit wird einmal in der echten Oberfläche geklickt | Baustein, Regel (Tests) | Adresse erledigt (0.17.1) |
| 20 | Nach jedem Testlauf fehlte "Öffnen" in der Entwicklungsinstanz | Tests und Entwicklungsinstanz nutzten denselben Zugang der Kellerwolke; der Testlauf meldete die Aktionen ohne Adresse neu | Tests haben einen eigenen Zugang (nur in `.env.test`) und ziehen ihre Aktionen am Ende zurück; das Testgerüst der Vorlage legt beides an | Vorlage (Tests) | Transkription erledigt (0.9.0), Vorlage offen |
| 21 | Die Übernahme legte Doppel an: Aufnahmen, die schon in eigenen Ordnern lagen, und Stimmen, deren Originalaufnahme gleich der Referenz war | Geplant wurde nur aus der Quelle, nicht gegen den ganzen Bestand des Ziels | Jede Übernahme gleicht vorher per Prüfsumme gegen alles im Ziel ab (auch frühere Versionen) und legt keine Doppel an; was schon da ist, wird verknüpft (Ergebnis als Begleiter neben das Vorhandene); Nutzer: "keine Duplikate anlegen" | Regel (Übernahme), Werkzeug | Bereinigt (Kellerwolke 0.84.2), Abgleich vorab offen |
| 22 | Zwei gleich aussehende Dateien in einem Ordner, Suche fand "grün" nicht | macOS liefert Dateinamen zerlegt (NFD), gespeichert wurde ungleich | Namen an einer Stelle in NFC (Kellerwolke `app/namen.py`, Repository und Suche), Bestand umgestellt; jede App, die Namen speichert oder vergleicht, macht es ebenso | Baustein | Kellerwolke erledigt (0.84.0) |
