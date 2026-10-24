#!/usr/bin/env bash
# Einrichten des Appkerns (Unterbau der Apps, kein eigener Dienst). Schritte und Proben stehen in docs/handbuch.md.
#
#   ./einrichten.sh                                       Entwicklung: .venv mit allen Extras und den Testpaketen, Pakete
#                                                         der Oberfläche (npm ci), Git-Haken
#   ./einrichten.sh --probe --ziel DIR --port-versatz N   Probelauf des Handbuchs: dieselbe Einrichtung in DIR, dann eine
#                                                         App aus der Vorlage (python -m appkern.vorlage mit dem Appkern
#                                                         aus DIR), deren eigene Einrichtung (Python-Umgebung, Bau der
#                                                         Oberfläche) und ihr Start bis "antwortet", nur an 127.0.0.1
#   ./einrichten.sh --probe --ziel DIR --abbauen          beendet die App aus der Vorlage
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBE_PORT=8600            # Port der App aus der Vorlage vor dem Versatz
PROBE_KENNUNG="probelauf"
WARTEN_S=60

entwicklung() {
  cd "$1"
  [ -x .venv/bin/python ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e ".[web,ton,tondienst,test]"
  npm ci --no-audit --no-fund --silent
  # Haken nur, wenn dieser Ordner selbst das Repo ist
  if [ "$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" = "$1" ]; then
    git -C "$1" config core.hooksPath tools/git-hooks
  fi
}

probe_aufbauen() {
  local ziel="$1" versatz="$2" port app
  port=$(( PROBE_PORT + versatz ))
  app="$ziel/apps/$PROBE_KENNUNG"
  entwicklung "$ziel"
  "$ziel/.venv/bin/python" -m appkern.vorlage --name Probelauf --kennung "$PROBE_KENNUNG" --rolle "prüft die Vorlage" \
    --symbol fa-flask --port "$port" --ziel "$ziel/apps" --appkern-lokal "$ziel"
  "$app/einrichten.sh"
  cd "$app/backend"
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$port" > "$ziel/app.log" 2>&1 &
  echo $! > "$ziel/app.pid"
  local ende=$(( $(date +%s) + WARTEN_S ))
  while [ "$(date +%s)" -lt "$ende" ]; do
    if curl -sf "http://127.0.0.1:$port/api/v1/app" >/dev/null && curl -sf -o /dev/null "http://127.0.0.1:$port/"; then
      echo "ANTWORTET http://127.0.0.1:$port/api/v1/app"
      return 0
    fi
    sleep 1
  done
  echo "Die App aus der Vorlage antwortet nach $WARTEN_S s nicht" >&2
  tail -n 40 "$ziel/app.log" >&2 || true
  return 1
}

probe_abbauen() {
  local pid
  if [ -f "$1/app.pid" ]; then
    pid="$(cat "$1/app.pid")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$1/app.pid"
  fi
}

probe=0; abbauen=0; ziel=""; versatz=""
while [ $# -gt 0 ]; do
  case "$1" in
    --probe) probe=1 ;;
    --abbauen) abbauen=1 ;;
    --ziel) ziel="${2:?--ziel braucht einen Ordner}"; shift ;;
    --port-versatz) versatz="${2:?--port-versatz braucht eine Zahl}"; shift ;;
    *) echo "unbekannte Angabe: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$probe" = 0 ]; then
  entwicklung "$HIER"
  echo "Appkern eingerichtet. Tests: .venv/bin/python -m pytest"
elif [ -z "$ziel" ] || [ ! -d "$ziel" ]; then
  echo "--probe braucht --ziel mit einem vorhandenen Ordner" >&2; exit 2
elif [ "$abbauen" = 1 ]; then
  probe_abbauen "$(cd "$ziel" && pwd)"
else
  probe_aufbauen "$(cd "$ziel" && pwd)" "${versatz:?--port-versatz fehlt}"
fi
