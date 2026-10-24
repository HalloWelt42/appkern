"""Ausrollen einer App auf den Pi, für jede App gleich (Lehren 3 bis 6 der Transkription). Angaben in
`deploy/ausrollen.toml` (oder einer anderen Datei mit `--ziel`, etwa für einen Probestand in eigenem Ordner mit
eigenen Ports); was das Haus angeht (Rechner, Ordner, Adresse, Namen im Zertifikat, Leitstelle), steht nicht im Repo,
sondern kommt mit `--ergaenzung` aus einer privaten Datei und füllt nur, was die Angaben selbst nicht nennen.
Aufgerufen vom Mac aus über `tools/ausrollen.sh`. Bricht beim ersten Fehler ab:

1. nur gepushte Stände, Tests hier grün, Appkern in Oberfläche und Backend auf demselben Commit
2. auf dem Pi: Docker mit Compose; nutzt die App Ton, meldet die Leitstelle den Tondienst (gerechnet wird auf dem Mac,
   der Pi liefert nur Daten; fehlt er, ist das eine Warnung, kein Abbruch: der Mac kann gerade schlafen)
3. Zertifikat der Hausstelle für den Vorschaltdienst, noch mindestens 60 Tage gültig, sonst neu ausgestellt
4. Stand holen, Abbild bauen (der alte Stand läuft weiter)
5. warten, bis die App keinen laufenden Auftrag hat, dann Datenbank sichern (die letzten zehn bleiben) und neu starten;
   der Vorschaltdienst startet jedes Mal neu (geänderte eingehängte Dateien bemerkt Docker nicht).
   Mit `--auslaufen` (für Apps, die tagelang durcharbeiten, Angaben unter [auslaufen] in deploy/ausrollen.toml): statt
   auf eine Lücke zu warten, hält die App an, der laufende Schritt läuft aus (Wartendes bleibt in der Warteschlange),
   dann wird ausgerollt und danach der Zustand von vorher hergestellt und geprüft, dass die Arbeit wieder läuft. Der
   Zustand von vorher liegt bis dahin in deploy/.auslaufen-vorher.json; bricht etwas ab, stellt ihn der nächste Lauf
   mit --auslaufen zuerst wieder her.
6. über HTTPS melden Server, gebaute Oberfläche und version.json dieselbe Fassung; die Seite kommt über HTTP/2; Symbole
   für Tab, Startbildschirm und Web-App sowie das Manifest antworten mit 200 und dem richtigen Typ, die Symbole des
   Startbildschirms sind deckend (sonst zeigt iOS keins)
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from pydantic import BaseModel, model_validator

SCHWELLE_S = 60 * 86400
SYMBOLE = {"favicon.ico": "image/", "favicon-32.png": "image/png", "apple-touch-icon.png": "image/png",
           "icon-192.png": "image/png", "icon-512.png": "image/png", "icon-maskable-512.png": "image/png",
           "site.webmanifest": "application/manifest+json"}
DECKEND = ("icon-192.png", "icon-512.png", "apple-touch-icon.png")


class Ziel(BaseModel):
    kennung: str            # Name des App-Dienstes in compose.pi.yml, der Zertifikate und der Datenbank
    rechner: str            # ssh-Ziel, etwa pi@192.168.1.20
    wurzel: str             # Ordner der App auf dem Pi
    adresse: str            # https://... des Vorschaltdienstes
    repo: str               # woher der Pi den Stand holt
    namen: list[str]        # Namen und Adressen im Zertifikat
    zweig: str = "main"
    compose: str = "compose.pi.yml"    # Compose-Datei im Ordner der App; das Projekt heißt wie der Ordner
    ton: bool = False       # die App nutzt die Tonarbeit über den Tondienst: die Leitstelle muss ihn melden
    leitstelle: str | None = None   # Adresse der Leitstelle, vom Pi aus erreichbar (nötig mit Ton)
    auslaufen: Auslaufen | None = None   # Weg für --auslaufen (Apps, die tagelang durcharbeiten)

    @model_validator(mode="after")
    def _ton_braucht_leitstelle(self) -> "Ziel":
        if self.ton and not self.leitstelle:
            raise ValueError("Mit ton = true braucht das Ziel leitstelle (Prüfung des Tondienstes)")
        return self

    @model_validator(mode="after")
    def _eigener_name(self) -> "Ziel":
        """<kennung>.local steht in jedem Zertifikat: der Vorschaltdienst nimmt ihn als Vorgabe, wenn ein Gerät ohne
        Servernamen anfragt (Zugriff über die Adresse), so steht keine Heimadresse in seiner Einstellung."""
        name = f"{self.kennung}.local"
        if name not in self.namen:
            self.namen = [*self.namen, name]
        return self

    @property
    def einrichtungscode_ort(self) -> str:
        return f"{self.rechner}:{self.wurzel}/daten/einrichtungscode"

    @property
    def datenbank(self) -> str:
        return f"daten/{self.kennung}.sqlite"


class Auslaufen(BaseModel):
    """Befehle im Container der App (docker compose exec) für das Ausrollen mit --auslaufen."""

    anhalten: str           # hält die App an und gibt ihren Zustand davor aus (eine Zeile JSON)
    ruhig: str              # Rückgabe 0, wenn nichts mehr in Arbeit ist; sonst 1 und der Grund
    fortsetzen: str         # liest den Zustand davor von der Eingabe und stellt ihn her
    laeuft: str | None = None   # Rückgabe 0, wenn die Arbeit wieder läuft (geprüft nach dem Fortsetzen)
    hoechstens_s: int = 1800    # so lange darf der laufende Schritt auslaufen


class Abbruch(Exception):
    pass


ZIEL_DATEI = Path("deploy") / "ausrollen.toml"


def laden(wurzel: Path, datei: Path = ZIEL_DATEI, ergaenzung: Path | None = None) -> Ziel:
    """Die Angaben des Ziels; eine Ergänzung (TOML) füllt nur Felder, die die Angaben nicht selbst nennen."""
    roh = tomllib.loads((wurzel / datei).read_text(encoding="utf-8"))
    if ergaenzung is not None:
        for schluessel, wert in tomllib.loads(Path(ergaenzung).read_text(encoding="utf-8")).items():
            roh.setdefault(schluessel, wert)
    return Ziel.model_validate(roh)


def _lauf(befehl: list[str], *, ort: Path | None = None) -> str:
    erg = subprocess.run(befehl, cwd=ort, capture_output=True, text=True)
    if erg.returncode != 0:
        raise Abbruch((erg.stdout + erg.stderr).strip() or f"{befehl[0]} endete mit {erg.returncode}")
    return erg.stdout.strip()


def _ssh(z: Ziel, skript: str) -> str:
    return _lauf(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", z.rechner, skript])


def _schritt(titel: str) -> None:
    print(f"\n== {titel}", flush=True)


def appkern_staende(wurzel: Path) -> tuple[str, str | None]:
    """(Commit der Oberfläche aus package-lock.json, Commit des Backends aus requirements.txt oder None)."""
    lock = json.loads((wurzel / "frontend" / "package-lock.json").read_text())
    oberflaeche = lock["packages"]["node_modules/appkern-oberflaeche"]["resolved"].rsplit("#", 1)[1]
    m = re.search(r"appkern(?:\[[^\]]*\])? @ https://github\.com/HalloWelt42/appkern/archive/([0-9a-f]{7,40})\.tar\.gz",
                  (wurzel / "backend" / "requirements.txt").read_text())
    return oberflaeche, m.group(1) if m else None


def stand_und_tests(z: Ziel, wurzel: Path) -> None:
    _schritt("Stand und Tests")
    if _lauf(["git", "status", "--porcelain"], ort=wurzel):
        raise Abbruch("Erst committen.")
    _lauf(["git", "fetch", "-q", "origin"], ort=wurzel)
    if _lauf(["git", "rev-parse", "HEAD"], ort=wurzel) != _lauf(["git", "rev-parse", f"origin/{z.zweig}"], ort=wurzel):
        raise Abbruch(f"Erst pushen ({z.zweig} ist nicht auf origin).")
    tests = subprocess.run([".venv/bin/python", "-m", "pytest", "-q"], cwd=wurzel / "backend", capture_output=True, text=True)
    print((tests.stdout.strip().splitlines() or [""])[-1])
    if tests.returncode != 0:
        raise Abbruch("Tests nicht grün")
    oberflaeche, backend = appkern_staende(wurzel)
    if backend != oberflaeche:
        raise Abbruch(f"Appkern in Oberfläche ({oberflaeche[:7]}) und Backend ({(backend or 'nicht festgelegt')[:7]}) "
                      "verschieden: tools/appkern.sh ausführen")
    print(f"Appkern {oberflaeche[:7]} in Oberfläche und Backend")


def pi_pruefen(z: Ziel) -> None:
    _schritt("Pi prüfen")
    print(_ssh(z, """set -e
  docker compose version >/dev/null || { echo "Docker Compose fehlt"; exit 1; }
  echo "Docker: $(docker --version)\""""))
    if z.ton:
        print(tondienst(_ssh(z, f"curl -sf -m 15 {shlex.quote(str(z.leitstelle).rstrip('/'))}/v1/models || true")))


def tondienst(modelle_json: str) -> str:
    """Meldung zur Tonarbeit aus der Modellliste der Leitstelle (ohne Schlüssel aus dem Heimnetz lesbar)."""
    try:
        daten = json.loads(modelle_json).get("data") or []
    except (ValueError, AttributeError):
        return "WARNUNG: Leitstelle nicht lesbar; ohne Tondienst scheitert jede Tonarbeit der App"
    namen = [m["id"] for m in daten if "ton" in ((m.get("x-leitstelle") or {}).get("faehigkeiten") or [])]
    if not namen:
        return "WARNUNG: die Leitstelle meldet keinen Tondienst (Fähigkeit ton); Tonarbeit scheitert, bis er da ist"
    return f"Tondienst: {', '.join(namen)}"


def zertifikat(z: Ziel) -> None:
    _schritt("Zertifikat")
    pem = f"{z.wurzel}/zertifikate/{z.kennung}.pem"
    gueltig = subprocess.run(["ssh", "-o", "BatchMode=yes", z.rechner,
                              f"test -f {shlex.quote(pem)} && openssl x509 -in {shlex.quote(pem)} -noout -checkend {SCHWELLE_S}"],
                             capture_output=True)
    if gueltig.returncode == 0:
        print("vorhanden, noch mindestens 60 Tage gültig")
        return
    if not shutil.which("mkcert"):
        raise Abbruch("mkcert fehlt auf diesem Mac")
    hausstelle = Path(_lauf(["mkcert", "-CAROOT"])) / "rootCA.pem"
    if not hausstelle.is_file():
        raise Abbruch(f"Die Hausstelle fehlt: {hausstelle}")
    with tempfile.TemporaryDirectory() as arbeit:
        a = Path(arbeit)
        _lauf(["mkcert", "-cert-file", f"{z.kennung}.pem", "-key-file", f"{z.kennung}-schluessel.pem", *z.namen], ort=a)
        shutil.copy(hausstelle, a / "rootCA.pem")
        ordner = f"{z.wurzel}/zertifikate"
        _ssh(z, f"mkdir -p {shlex.quote(ordner)}")
        _lauf(["scp", "-q", str(a / f"{z.kennung}.pem"), str(a / f"{z.kennung}-schluessel.pem"), str(a / "rootCA.pem"),
               f"{z.rechner}:{ordner}/"])
        _ssh(z, f"chmod 644 {shlex.quote(ordner)}/{z.kennung}.pem {shlex.quote(ordner)}/rootCA.pem && "
                f"chmod 640 {shlex.quote(ordner)}/{z.kennung}-schluessel.pem")
        bis = _lauf(["openssl", "x509", "-in", str(a / f"{z.kennung}.pem"), "-noout", "-enddate"]).split("=", 1)[1]
        print(f"ausgestellt, gültig bis {bis}")


def stand_holen(z: Ziel) -> None:
    _schritt("Stand holen")
    w, k = shlex.quote(z.wurzel), z.kennung
    print(_ssh(z, f"""set -e
  mkdir -p {w}
  cd {w}
  if [ ! -d .git ]; then git clone -q {shlex.quote(z.repo)} /tmp/{k}-klon && cp -a /tmp/{k}-klon/. . && rm -rf /tmp/{k}-klon; fi
  git pull --ff-only -q
  echo "Stand: $(git log --oneline -1)\""""))


def sichern(z: Ziel) -> None:
    """Die Datenbank so, wie sie unmittelbar vor dem Neustart ist (die letzten zehn Sicherungen bleiben)."""
    _schritt("Datenbank sichern")
    w, db, k = shlex.quote(z.wurzel), shlex.quote(z.datenbank), z.kennung
    print(_ssh(z, f"""set -e
  cd {w}
  mkdir -p daten sicherungen
  if [ -f {db} ]; then
    ziel=sicherungen/{k}-$(date +%Y%m%d-%H%M%S).sqlite
    python3 -c 'import sqlite3, sys; q = sqlite3.connect(sys.argv[1]); z = sqlite3.connect(sys.argv[2]); q.backup(z); z.close(); q.close()' {db} "$ziel"
    echo "gesichert: $ziel"
    ls -1t sicherungen/{k}-*.sqlite | tail -n +11 | xargs -r rm --
  else
    echo 'noch keine Datenbank'
  fi"""))


RUHE_HOECHSTENS_S = 4 * 3600     # so lange wartet das Ausrollen höchstens auf laufende Aufträge
# Auf dem Pi: jede Sekunde die Zahl laufender Aufträge der App; antwortet sie nicht, gibt es nichts zu verlieren
RUHE_SKRIPT = """zaehlen() { curl -sf -m 10 --cacert %(ca)s %(adresse)s | python3 -c 'import sys, json; print(int(json.load(sys.stdin).get("auftraege_laufend") or 0))' 2>/dev/null || echo 0; }
n=$(zaehlen)
if [ "$n" = 0 ]; then echo "Keine laufenden Aufträge"; exit 0; fi
echo "$n Aufträge laufen, warte auf eine Lücke ..."
ende=$(( $(date +%%s) + %(hoechstens)d ))
while [ "$(zaehlen)" != 0 ]; do
  if [ "$(date +%%s)" -gt "$ende" ]; then echo "noch nicht ruhig"; exit 3; fi
  sleep 1
done
echo "Ruhig"
"""


def ruhe_abwarten(z: Ziel, sofort: bool) -> None:
    """Nie laufende Aufträge abschießen (Lehre 29): warten, bis die App auf dem Pi keinen mehr hat, und zwar nach dem
    Bauen, unmittelbar vor dem Neustart (sonst beginnt während des Bauens ein neuer). Geprüft wird auf dem Pi selbst
    jede Sekunde: Aufträge, die dicht aufeinander folgen (etwa KI-Transkripte), lassen nur kurze Lücken. Die Zahl steht
    öffentlich in /api/v1/app."""
    if sofort:
        return
    _schritt("Laufende Aufträge abwarten")
    skript = RUHE_SKRIPT % {"ca": shlex.quote(f"{z.wurzel}/zertifikate/rootCA.pem"),
                            "adresse": shlex.quote(f"{z.adresse}/api/v1/app"), "hoechstens": RUHE_HOECHSTENS_S}
    try:
        print(_ssh(z, skript))
    except Abbruch as f:
        raise Abbruch(f"Nach {RUHE_HOECHSTENS_S // 3600} Stunden laufen noch Aufträge; mit --sofort trotzdem ausrollen") from f


VORHER = Path("deploy") / ".auslaufen-vorher.json"
NACHLAUF_S = 180                 # so lange darf die Arbeit nach dem Fortsetzen brauchen, bis sie wieder läuft


def _im_container(z: Ziel, befehl: str, eingabe: str | None = None) -> subprocess.CompletedProcess:
    """Ein Befehl im Container der App; Rückgabe und Ausgabe kommen zurück, ohne abzubrechen."""
    c = shlex.quote(z.compose)
    skript = f"cd {shlex.quote(z.wurzel)} && docker compose -f {c} exec -T {shlex.quote(z.kennung)} sh -c {shlex.quote(befehl)}"
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", z.rechner, skript], input=eingabe,
                          capture_output=True, text=True)


def fortsetzen(z: Ziel, wurzel: Path) -> None:
    """Den Zustand von vor dem Auslaufen herstellen und prüfen, dass die Arbeit wieder läuft."""
    a = z.auslaufen
    datei = wurzel / VORHER
    if a is None or not datei.exists():
        return
    _schritt("Fortsetzen wie vorher")
    erg = _im_container(z, a.fortsetzen, datei.read_text())
    print((erg.stdout + erg.stderr).strip())
    if erg.returncode != 0:
        raise Abbruch(f"Fortsetzen ging nicht; der Zustand von vorher liegt in {VORHER}, der nächste Lauf mit --auslaufen stellt ihn her")
    datei.unlink()
    if a.laeuft:
        ende = time.monotonic() + NACHLAUF_S
        while True:
            erg = _im_container(z, a.laeuft)
            if erg.returncode == 0 or time.monotonic() > ende:
                break
            time.sleep(10)
        print((erg.stdout + erg.stderr).strip())
        if erg.returncode != 0:
            print(f"Warnung: nach {NACHLAUF_S} s arbeitet die App noch nicht wieder (siehe oben); bitte nachsehen")


def auslaufen(z: Ziel, wurzel: Path) -> None:
    """Anhalten und den laufenden Schritt auslaufen lassen; der Zustand davor bleibt in deploy/.auslaufen-vorher.json."""
    a = z.auslaufen
    if a is None:
        raise Abbruch("--auslaufen braucht [auslaufen] in deploy/ausrollen.toml (anhalten, ruhig, fortsetzen)")
    _schritt("Anhalten und auslaufen lassen")
    datei = wurzel / VORHER
    if not datei.exists():
        erg = _im_container(z, a.anhalten)
        if erg.returncode != 0:
            raise Abbruch(f"Anhalten ging nicht: {(erg.stdout + erg.stderr).strip()}")
        datei.write_text(erg.stdout.strip().splitlines()[-1] if erg.stdout.strip() else "{}")
    print(f"Zustand vorher: {datei.read_text().strip()}")
    ende = time.monotonic() + a.hoechstens_s
    zuletzt = ""
    while True:
        erg = _im_container(z, a.ruhig)
        grund = (erg.stdout + erg.stderr).strip()
        if erg.returncode == 0:
            print(grund or "nichts mehr in Arbeit")
            return
        if grund != zuletzt:
            print(f"läuft aus: {grund}", flush=True)
            zuletzt = grund
        if time.monotonic() > ende:
            fortsetzen(z, wurzel)
            raise Abbruch(f"Nach {a.hoechstens_s // 60} Minuten ist noch etwas in Arbeit ({grund}); nichts ausgerollt, "
                          "der Zustand von vorher ist wieder hergestellt")
        time.sleep(5)


def bauen(z: Ziel) -> None:
    """Das neue Abbild entsteht, während der alte Stand weiterläuft."""
    _schritt("Bauen")
    _ssh(z, f"cd {shlex.quote(z.wurzel)} && docker compose -f {shlex.quote(z.compose)} build --quiet")


def starten(z: Ziel) -> None:
    """Startet mit dem Ort des Einrichtungscodes in der Umgebung (die Compose-Datei nennt ihn nicht, er gehört dem Haus)."""
    _schritt("Starten")
    c = shlex.quote(z.compose)
    ort = shlex.quote(z.einrichtungscode_ort)
    _ssh(z, f"cd {shlex.quote(z.wurzel)} && EINRICHTUNGSCODE_ORT={ort} docker compose -f {c} up -d --remove-orphans && "
            f"docker compose -f {c} restart vorne")


def _curl(z: Ziel, *args: str) -> str:
    hausstelle = Path(_lauf(["mkcert", "-CAROOT"])) / "rootCA.pem"
    return _lauf(["curl", "-s", "--cacert", str(hausstelle), *args])


def _deckend(daten: bytes) -> bool:
    """Ohne durchsichtige Stellen; gerechnet mit dem Python des Systems (Pillow gehört nicht ins Abbild der App)."""
    pruefung = ("import io, sys\nfrom PIL import Image\nb = Image.open(io.BytesIO(sys.stdin.buffer.read())).convert('RGBA')\n"
                "sys.exit(0 if b.getchannel('A').getextrema()[0] == 255 else 1)")
    return subprocess.run(["python3", "-c", pruefung], input=daten, capture_output=True).returncode == 0


def pruefen(z: Ziel, wurzel: Path) -> None:
    _schritt("Prüfen")
    w = shlex.quote(z.wurzel)
    _ssh(z, f"cd {w} && for i in $(seq 1 30); do curl -sf --cacert zertifikate/rootCA.pem {shlex.quote(z.adresse)}/api/v1/app "
            ">/dev/null && exit 0; sleep 2; done; echo 'Die App antwortet nicht'; exit 1")
    info = json.loads(_ssh(z, f"curl -sf --cacert {w}/zertifikate/rootCA.pem {shlex.quote(z.adresse)}/api/v1/app"))
    fassung = json.loads((wurzel / "version.json").read_text())["version"]
    print(f"Server {info['fassung']}, Oberfläche {info.get('oberflaeche')}, version.json {fassung}, Appkern {info['appkern']}")
    if not info["fassung"] == fassung == info.get("oberflaeche"):
        raise Abbruch("Fassungen passen nicht zusammen")
    if _curl(z, "-o", "/dev/null", "-w", "%{http_version}", "--http2", f"{z.adresse}/") != "2":
        raise Abbruch(f"Die Seite kommt nicht über HTTP/2: Vorschaltdienst prüfen (docker compose -f {z.compose} logs vorne)")
    for pfad, typ in SYMBOLE.items():
        antwort = _curl(z, "-o", "/dev/null", "-w", "%{http_code} %{content_type}", f"{z.adresse}/{pfad}")
        if not antwort.startswith(f"200 {typ}"):
            raise Abbruch(f"Symbol {pfad}: {antwort} (erwartet 200 {typ})")
    hausstelle = Path(_lauf(["mkcert", "-CAROOT"])) / "rootCA.pem"
    for pfad in DECKEND:
        daten = subprocess.run(["curl", "-s", "--cacert", str(hausstelle), f"{z.adresse}/{pfad}"], capture_output=True).stdout
        if not _deckend(daten):
            raise Abbruch(f"Symbol {pfad} hat durchsichtige Stellen (iOS zeigt dann keins): python3 tools/symbole.py")
    print("HTTP/2 über den Vorschaltdienst, Symbole deckend, Manifest in Ordnung")


def ausrollen(wurzel: Path, sofort: bool = False, datei: Path = ZIEL_DATEI, auslaufen_lassen: bool = False,
              ergaenzung: Path | None = None) -> int:
    try:
        z = laden(wurzel, datei, ergaenzung)
    except (OSError, ValueError) as f:
        print(f"\nAbbruch: Ziel nicht lesbar: {f}", file=sys.stderr)
        return 1
    try:
        stand_und_tests(z, wurzel)
        pi_pruefen(z)
        zertifikat(z)
        stand_holen(z)
        bauen(z)
        if auslaufen_lassen:
            auslaufen(z, wurzel)
        else:
            ruhe_abwarten(z, sofort)
        sichern(z)
        starten(z)
        pruefen(z, wurzel)
        fortsetzen(z, wurzel)
    except Abbruch as f:
        print(f"\nAbbruch: {f}", file=sys.stderr)
        return 1
    print(f"\nAusgerollt: {z.adresse}")
    return 0
