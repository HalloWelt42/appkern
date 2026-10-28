---
zweck: "Der gemeinsame Unterbau der Apps des Verbunds: Anmeldung mit dem Kellerwolke-Konto, Zugang zu Kellerwolke und Leitstelle, Aufträge, Einstellungen, Protokoll, Tonarbeit, die Oberflächen-Schale und die Vorlage für neue Apps."
geraet: [mac]
abhaengigkeiten: []
daten:
  - "keine eigenen Daten: Code und Vorlage liegen im Repo, die Apps beziehen den Appkern als Archiv eines Commits von GitHub (Backend) und als npm-Paket (Oberfläche)"
sicherung:
  - "nichts zu sichern außer dem Repo auf GitHub"
schluessel_orte:
  - "Mac: `.env.test` im Klon (nicht im Repo): Adresse und App-Schlüssel des Testzugangs AppkernTest an der Kellerwolke der Entwicklung, nur für den Verbundtest"
einrichten: einrichten.sh
stand: 9fcdb82
---

# Appkern

## Zweck

Der Appkern ist kein Dienst, sondern der Unterbau, auf dem die Neubau-Apps stehen ([[Fundus]], [[Assistent]],
[[Vertonung]], [[Transkription]] und weitere). Er bringt die Bausteine, die jede App gleich braucht: Anmeldung mit dem
Konto der [[Kellerwolke]], Zugang zur Ablage mit App-Schlüssel, die Fassade zur [[Leitstelle]], Aufträge mit Phasen
und Fortsetzung nach einem Neustart, Einstellungen mit verdeckten Schlüsseln, Protokoll, die Sicherung der Datenbank
nach einer Regel für alle Apps (wöchentlich, vor dem Ausrollen nur nach 24 Stunden, nie ohne Änderung, höchstens drei
Stände; die Werte stellt jede App unter Einstellungen, Sicherung ein), Tonarbeit über den Tondienst
des [[Klangwerk]], das Gerüst einer App, die Oberflächen-Schale mit der gemeinsamen Gestaltung und die Werkzeuge für
Commit und Ausrollen (`python -m appkern.werkzeuge`).

Mit der Vorlage (`python -m appkern.vorlage`) entsteht eine neue App, die all das schon mitbringt, dazu Dockerfile,
`compose.pi.yml` mit Vorschaltdienst, Ausrollen, Git-Haken und ein Einrichtungsskript mit Probemodus für das Handbuch
(`deploy/probelauf.compose.yml`: eigene Namen, abgeschottetes Netz, Port nur an 127.0.0.1).

Die Apps legen den Appkern auf einen Commit fest (`tools/appkern.sh` in der App), in Backend und Oberfläche gleich;
das Ausrollen bricht ab, wenn beide verschieden sind. Was beim Ausrollen dem Haus gehört (Rechner, Ordner, Adresse,
Namen im Zertifikat, Leitstelle), steht nicht in den Repos: `tools/ausrollen.sh` einer App holt es mit
`handbuch ziel <app> --toml` aus der privaten Wahrheit im Handbuch und gibt es dem Ausrollen als `--ergaenzung`.

Der Appkern ist auch die eine Wahrheit der Gestaltung aller Apps: die Marken (`oberflaeche/stil/marken.css`: Farben,
Schriften, Größen, Abstände) und die Bausteine. Daraus entstehen die Seite Gestaltung in jeder App (Einstellungen,
Gestaltung) und die Seite [[Gestaltung]] in diesem Handbuch; der Haken jeder App lässt im Stil nur Marken zu.

## Was sie braucht

- Mac nach [[Grundlage Mac]]: Python ab 3.11, Node.js für die Schale und die Vorlage; für den Symbolsatz neuer Apps
  ein Python mit cairosvg und Pillow (das Python 3.13 aus Homebrew).
- Das Repo auf GitHub: die Apps holen den Appkern beim Bau von dort.
- Für den Verbundtest eine Kellerwolke der Entwicklung mit einem Testzugang (sonst wird er übersprungen).

## Neu einrichten

Der Appkern hat keine Daten; ein Weg genügt. Aus der Sicherung kommt höchstens `.env.test` zurück, sonst den
Testzugang in der Kellerwolke der Entwicklung neu anlegen.

### 1. Klon und Entwicklungsumgebung

```
git clone {{repo}} {{ordner}}
cd {{ordner}} && ./einrichten.sh
```

`./einrichten.sh` legt `.venv` mit allen Extras und den Testpaketen an, holt die Pakete der Oberfläche (`npm ci`) und
setzt die Git-Haken (Fassung hochzählen, Zeichen und Stil prüfen).

Probe: `.venv/bin/python -m pytest -q` ist grün (der Verbundtest ist ohne `.env.test` übersprungen).

### 2. Testzugang für den Verbundtest

Nur für die Arbeit am Appkern selbst: in der Kellerwolke der Entwicklung einen App-Schlüssel "AppkernTest" anlegen und
mit ihrer Adresse in `.env.test` schreiben (`KELLERWOLKE_ADRESSE`, `KELLERWOLKE_SCHLUESSEL`, Modus 0600).

Probe: `.venv/bin/python -m pytest -q tests/test_kellerwolke_verbund.py` läuft, statt übersprungen zu werden.

### 3. Eine App aus der Vorlage

```
.venv/bin/python -m appkern.vorlage --name <Name> --kennung <kennung> --rolle "<macht etwas>" \
    --symbol fa-<symbol> --port <port> --ziel <ordner> [--ton]
```

Danach in der neuen App `./einrichten.sh`; ihre Seite für das Handbuch legt `handbuch anlegen <app>` an.

Probe: die neue App startet mit `backend/.venv/bin/uvicorn app.main:app --port <port>` und antwortet auf
`/api/v1/app`; so prüft es auch der Probelauf des Handbuchs.

## Sicherung und Rückspielen

Es gibt nichts zu sichern außer dem Repo; jeder Stand, den eine App nutzt, liegt als Commit auf GitHub. Zurückspielen
heißt klonen (Schritt 1). `.env.test` enthält nur einen Testzugang zur Kellerwolke der Entwicklung und lässt sich neu
anlegen.

## Wenn etwas klemmt

- Das Ausrollen einer App bricht mit "Appkern in Oberfläche und Backend verschieden" ab: in der App `tools/appkern.sh`
  laufen lassen, committen, pushen.
- Eine App baut mit einem alten Appkern: sie nennt den Zweig statt eines Commits; `tools/appkern.sh` legt den Commit fest.
- Das Ausrollen einer App bricht bei "Datenbank sichern" ab: die Zeile darüber nennt den Grund (meist Platz oder Rechte);
  der Ordner `sicherungen` im Ordner der App auf dem Pi muss dem Nutzer `pi` gehören. Ohne Fehler, aber ohne neue
  Sicherung: die Zeile nennt, warum keine nötig war (jüngste jünger als 24 Stunden oder Datenbank unverändert).
- Nach dem Ausrollen steht "Warnung: Aufräumen ging nicht": ausgerollt ist trotzdem; verwaiste Abbilder und Baucache
  räumt das nächste Ausrollen weg, von Hand `docker image prune -f` und `docker builder prune -f --max-used-space 20GB`.
- Der Symbolsatz einer neuen App fehlt: kein Python mit cairosvg und Pillow gefunden; `python3 tools/symbole.py` in der
  App mit dem Python 3.13 aus Homebrew.
- Der Commit bricht mit einer Zeichen- oder Stilprüfung ab: `python -m appkern.werkzeuge pruefen <datei>` nennt die
  Stelle.
