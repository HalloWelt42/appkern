# __NAME__

__NAME__ __ROLLE__. Eine App auf dem [Appkern](https://github.com/HalloWelt42/appkern): Dateien in der Kellerwolke
(Zweig `Apps/__NAME__`), KI nur über die Leitstelle, Anmeldung mit dem Kellerwolke-Konto, gestartet vom Stellwerk.

## Einrichten

```bash
./einrichten.sh
```

Legt die Python-Umgebung an, holt die Pakete der Oberfläche und baut sie. Danach im Stellwerk starten (Eintrag
`stellwerk.toml`) und `http://127.0.0.1:__PORT__` öffnen: die erste Einrichtung fragt nach der Adresse der
Kellerwolke und dem App-Schlüssel (in der Kellerwolke unter Einstellungen, Zugänge). Alles Weitere unter Einstellungen.

## Entwickeln

| Teil | Befehl |
|---|---|
| Backend | `cd backend && .venv/bin/uvicorn app.main:app --port __PORT__ --reload` |
| Oberfläche | `cd frontend && npm run dev` (Port __DEVPORT__, leitet `/api` ans Backend) |
| Tests | `cd backend && .venv/bin/python -m pytest` |
| Symbole | `python3 tools/symbole.py` nach einer Änderung an `frontend/public/symbol.svg` |
| Fassung | `tools/version.sh minor` für eine neue Fähigkeit; jeder Commit zählt sonst selbst hoch |
| Appkern | `tools/appkern.sh` hebt Oberfläche und Backend auf denselben neuesten Commit |
| Ausrollen | `tools/ausrollen.sh` (Angaben in `deploy/ausrollen.toml`) |

Der Verbundtest (`tests/test_verbund.py`) spricht mit einer echten Kellerwolke und braucht `backend/.env.test` (nicht
im Repo) mit `KELLERWOLKE_ADRESSE`, `KELLERWOLKE_SCHLUESSEL`, `KELLERWOLKE_KENNUNG`, `KELLERWOLKE_PASSWORT`: ein eigener
Zugang nur für Tests, nicht der der Entwicklungsinstanz. Aufräumen und Zurückziehen der Aktionen kommen aus
`appkern.testen`.

## Prüfungen

Vor jedem Commit (Hook in `tools/git-hooks`, eingerichtet von `einrichten.sh`): Fassung hochzählen, nur gerade
Zeichen, Stil ohne `!important`, ohne einseitige Streifen und ohne Regeln auf Klassen der Schale. Beim Ausrollen: Tests,
gleicher Appkern in Oberfläche und Backend, Fassungen, HTTP/2, deckende Symbole. Von Hand vor dem Vorzeigen:
`docs/ABNAHME.md`.

## Aufbau

| Ort | Inhalt |
|---|---|
| `backend/app/main.py` | baut die App auf dem Gerüst |
| `backend/app/einstellungen.py` | eigene Einstellungen (dazu kommen Kellerwolke, Leitstelle, Konten) |
| `backend/app/arten.py` | Arten von Aufträgen |
| `backend/app/api.py` | eigene Endpunkte |
| `frontend/src/App.svelte` | Bereiche der App in der gemeinsamen Schale |
| `frontend/src/seiten/` | Seiten der Bereiche |
