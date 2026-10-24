# Gestaltung

> Erzeugt aus `oberflaeche/stil/marken.css` und `oberflaeche/gestaltung/katalog.json` im Appkern (`python -m appkern.werkzeuge gestaltung`, bei jedem Commit des Appkerns). Dort ändern, nicht hier.

Marken des Appkerns: die eine Wahrheit für Farben, Schriften, Schriftgrößen, Abstände, Ecken und Schatten aller eigenen Apps (Grunddesign, Nutzer 24.10.2026: "Appkern, alle ziehen um"; "Nur Marken, Ausnahme begründet"). Der Stil einer App nutzt nur diese Marken; eine neue Farbe kommt zuerst hierher (python -m appkern.werkzeuge pruefen meldet feste Werte). Jede Marke trägt ihren Zweck als Kommentar; daraus entstehen die Seite Gestaltung in jeder App und die Seite im Handbuch (python -m appkern.werkzeuge gestaltung). Themen: hell ist die Vorgabe, dunkel über data-theme="dunkel" am Wurzelelement (html) oder an einem Teil der Seite. Schriftstufen: dicht ist die Vorgabe (Schale des Appkerns, Nutzer 20.10.2026: eine feste, dichte Schrift); klein, mittel und gross über data-schrift für Apps mit eigener Schale und Schriftstufen (Leitstelle, Fundus; Groß ist dort die Vorgabe). Wie die Themen gilt eine Stufe auch für einen Teil der Seite.

In jeder App steht dieselbe Seite unter Einstellungen, Gestaltung: alle Bausteine echt gerendert, hell und dunkel nebeneinander.

## So nutzt eine App die Gestaltung

- Apps in der Schale laden `import "appkern-oberflaeche/stil.css"` (Schriften, Symbole, Marken, Schale, Bausteine) und schreiben nur, was ihnen eigen ist, in einen eigenen Stil mit eigenen Klassen.
- Apps, die ihre Schale selbst zeichnen (Leitstelle, Fundus), laden `appkern-oberflaeche/leitstand.css` (Schriften, Marken und Bausteine des Leitstands) und setzen `data-schrift` am `<html>` (Vorgabe `gross`).
- Farben, Schriften und Schriftgrößen kommen nur aus den Marken (`var(--...)`); Mischungen mit `color-mix(in srgb, var(--gefahr) var(--toenung), transparent)`, Größen mit Marken oder relativ (`em`, `%`). Eine neue Farbe kommt zuerst in die Marken des Appkerns.
- Ausnahme nur mit Kommentar und Grund in derselben Zeile, darüber oder über der Regel: `/* Ausnahme: <Grund in mindestens drei Wörtern> */`, im Markup `<!-- Ausnahme: ... -->`.
- Prüfen: `python -m appkern.werkzeuge marken` zeigt alle Befunde; der Haken jeder App prüft bei jedem Commit, `gestaltung.toml` (`marken = "scharf"`) lässt ihn scheitern.
- Die Seite Gestaltung steht in jeder App unter Einstellungen; Apps mit eigener Schale binden sie mit `import Gestaltung from "appkern-oberflaeche/gestaltung"` ein.

## Muster mit Grund

| Muster | Grund |
|---|---|
| Nur Marken: Farben, Schriften und Schriftgrößen aus den Marken des Appkerns, nie feste Werte im Stil einer App. | Eine Wahrheit: alle Apps sehen gleich aus, Thema und Schriftstufe wirken überall, eine Änderung an einer Stelle reicht (Nutzer 24.10.2026: "Nur Marken, Ausnahme begründet"). |
| Wort und Farbe, nie Farbe allein: Zustände, Fähigkeiten und Zonen tragen immer ein Wort oder Symbol. | Die Bedeutung bleibt lesbar, auch für schwache Augen, in Graustufen und auf schlechten Bildschirmen. |
| Bernstein nur für die eine Hauptsache einer Ansicht (Hauptknopf) und für das, was gerade läuft. | Das Auge findet sofort, was zählt; ein Akzent überall ist keiner. |
| Keine einseitigen Streifen: hervorheben mit Fläche, Rahmen rundum oder einem Punkt, nie mit einem Rand an einer Seite. | Nutzer: einseitige Ränder wirken unruhig und "hässlich"; die Prüfung erlaubt nur 1-Pixel-Trennlinien in der Randfarbe. |
| Kein !important; Konflikte über Spezifität, Reihenfolge und eigene Klassen lösen. | Die Kaskade bleibt nachvollziehbar, spätere Änderungen brauchen keine weiteren Holzhämmer. |
| Eigene Klassen für eigene Regeln: eine App ändert keine Klasse der Schale, sie erweitert sie höchstens (`.knopf.klein`). | Sonst ändert eine App die Schale mit (so lief einmal die Statuszeile der Einstellungen über). |
| Die Seite rollt nie, nur ihre Felder; Kopf und Fußleiste stehen fest. | Bedienung und Lage bleiben immer sichtbar; lange Listen rollen in sich. |
| Keine seitliche Rollerei in keiner Breite (von 1920 bis 375 Pixel): Raster mit `minmax(0, 1fr)`, Text in Flex- und Rasterkindern mit `min-width: 0`, lange Wörter umbrechen. | `1fr` allein läuft mit langem Inhalt über; was seitlich rollt, ist am Telefon nicht bedienbar. |
| Zahlen, Zeiten und Zähler in der Zahlenschrift (`--schrift-zahl`). | Werte sind als Werte erkennbar, Ziffern stehen gleich breit und springen beim Zählen nicht. |
| Fokus nur bei Tastatur sichtbar, als Ring in Akzent. | Mit Maus und Finger stört der Ring, mit Tastatur ist er nötig. |
| Keine Browser-Dialoge (alert, confirm, prompt): Rückfrage im Ablauf, direkt an der Stelle. | Kein Bruch im Ablauf, am Telefon bedienbar, gleich gestaltet; die Ansichtsprüfung zählt jeden Dialog als Befund. |
| Aufklappliste statt nativer Auswahl; keine nativen Farbwähler und Datumsfelder. | Native Felder sehen je Browser anders aus und sind teils amerikanisch (Datum); die eigene Liste sieht überall gleich aus. |
| Kurze Texte, stabile Knöpfe: beim Zustandswechsel verschiebt sich nichts. | Ein Knopf, der springt, wird verfehlt; die Ansichtsprüfung misst die Verschiebung fester Teile. |
| Schrift in Stufen: die Schale ist dicht (15, klein 13, Etiketten 12 Pixel), Apps mit eigener Schale bieten Stufen (Vorgabe groß, 18 Pixel); nichts unter der Marke für Etiketten. | Nutzer 20.10.2026: in der Schale eine feste, dichte Schrift; Leitstelle und Fundus groß, weil kleine Schrift schlecht lesbar ist. |
| Kontrast: Schrift mindestens 4,5 : 1 auf ihrer Fläche; Akzent als Schrift getrennt von der Akzentfläche. | Bernstein auf Weiß ist als Fläche schön, als Schrift aber zu blass; darum zwei Marken. |
| Am Telefon eine eigene Ansicht mit Reitern, keine verkleinerte Rechneransicht; oben Luft unter der Uhr, unten nichts über dem Home-Balken. | Jede App wird auch vom Startbildschirm des iPhone genutzt; dort fängt das System oben Berührungen ab. |
| Hilfe im Ablauf: Fachbegriffe erklären sich beim Überfahren, Hinweise stehen in Leisten statt in Fenstern. | Erklärung dort, wo die Frage entsteht, ohne den Ablauf zu verlassen. |

## Marken

### Schriften

Barlow liest sich ruhig und breit; Zahlen stehen in Chakra Petch, damit Werte, Zeiten und Zähler als solche erkennbar sind und Ziffern gleich breit stehen; Code in der Schrift des Systems mit fester Breite.

| Marke | Wert | Zweck |
|---|---|---|
| `--schrift` | `"Barlow", system-ui, sans-serif` | Grundschrift aller Texte |
| `--schrift-zahl` | `"Chakra Petch", "Barlow", ui-monospace, monospace` | Zahlen, Zeiten, Zähler, Fassungen |
| `--schrift-code` | `ui-monospace, "SF Mono", Menlo, monospace` | Code, Pfade, Ereignisnamen, Kopplungscodes |

### Schriftgrößen

Stufe dicht (Vorgabe der Schale): Grundschrift 15, klein 13, Etiketten 12 Pixel. Größer wird nur über eine Stufe, nie über feste Werte in einer App; data-schrift="dicht" stellt sie für einen Teil der Seite her.

| Marke | dicht | klein | mittel | gross | Zweck |
|---|---|---|---|---|---|
| `--gross` | `15px` | `16px` | `17px` | `18px` | Grundschrift: Fließtext, Eingaben, Listen |
| `--klein` | `13px` | `14px` | `15px` | `16px` | Nebenangaben, Knöpfe, Beschreibungen |
| `--marke` | `12px` | `13px` | `15px` | `15px` | Etiketten, Zähler, Versalien-Überschriften: nie kleiner |
| `--titel` | `17px` | `19px` | `21px` | `22px` | Überschrift einer Karte, Leiste oder Gruppe |
| `--seitentitel` | `20px` | `27px` | `30px` | `32px` | Überschrift einer Seite |
| `--kennzahl` | `24px` | `24px` | `27px` | `30px` | große Zahlen und Codes zum Ablesen (Kennzahlen, Kopplungscode) |
| `--appname` | `18px` | `21px` | `21px` | `21px` | Name der App im Kopf |

### Maße

Feste Höhen und Breiten der Rahmen, je Schriftstufe (oben bei den Stufen); die Seite selbst rollt nie, nur ihre Felder.

| Marke | dicht | klein | mittel | gross | Zweck |
|---|---|---|---|---|---|
| `--kopf-hoehe` | `50px` | `58px` | `62px` | `62px` | Kopf mit Marke, Rolle und Verbindungen |
| `--nav-breite` | `232px` | `232px` | `248px` | `264px` | Seitenleiste mit Bereichen |
| `--fuss-hoehe` | `30px` | `44px` | `44px` | `44px` | Fußleiste mit Verbindungen und laufender Arbeit |
| `--zeile` | `34px` | `34px` | `34px` | `34px` | Eintrag der Seitenleiste |
| `--knopf-hoehe` | `32px` | `42px` | `42px` | `42px` | Knöpfe, Suche, runde Knöpfe |

### Abstände

Eine Leiter für Lücken und Innenabstände; ungerade Werte nur, wo ein Rahmen sie ausgleicht.

| Marke | Wert | Zweck |
|---|---|---|
| `--a1` | `4px` | zwischen Symbol und Wort |
| `--a2` | `8px` | zwischen Teilen einer Zeile |
| `--a3` | `12px` | Innenabstand kleiner Flächen |
| `--a4` | `16px` | Innenabstand von Karten und Feldern |
| `--a5` | `24px` | Abstand zwischen Abschnitten |
| `--a6` | `32px` | Rand großer Seiten |
| `--a7` | `48px` | große Leerräume |

### Ecken

Kantig wie die Leitstelle: kleine Rundungen wirken ruhig und technisch.

| Marke | Wert | Zweck |
|---|---|---|
| `--r1` | `2px` | Marken, Segmente, kleine Flächen |
| `--r2` | `3px` | Knöpfe, Eingaben, Pillen |
| `--r3` | `4px` | Karten, Leisten, Tafeln |

### Bewegung

Kurz und ruhig; nie länger, als das Auge folgt.

| Marke | Wert | Zweck |
|---|---|---|
| `--schnell` | `120ms` | Überfahren, Schalter |
| `--ruhig` | `320ms` | Balken, Ein- und Ausblenden |

### Feste Farben

Gelten in beiden Themen.

| Marke | Wert | Zweck |
|---|---|---|
| `--licht` | `#ffffff` | reines Licht: Schimmer über Balken, Grundlage von auf-farbe |
| `--auf-farbe` | `var(--licht)` | Schrift und Symbole auf satten Farbflächen (App-Farbe, Gefahr) |
| `--schattenfarbe` | `#0a121c` | Grundton für Schatten und Schleier, gemischt mit Durchsicht |
| `--app-farbe` | `#2f7ce0` | Flächenfarbe der App im Symbol; die Schale setzt die Farbe der App |
| `--app-farbe-tief` | `#6a5ae0` | zweite Farbe des Verlaufs im Symbol |
| `--symbol-flaeche` | `linear-gradient(135deg, var(--app-farbe), var(--app-farbe-tief))` | Fläche hinter dem Symbol der App |
| `--s1` | `#12938a` | Sprecherfarbe 1: in beiden Themen unterscheidbar (Transkription, Vertonung) |
| `--s2` | `#c2410c` | Sprecherfarbe 2 |
| `--s3` | `#7c3aed` | Sprecherfarbe 3 |
| `--s4` | `#2f7ce0` | Sprecherfarbe 4 |
| `--s5` | `#b45309` | Sprecherfarbe 5 |
| `--s6` | `#db2777` | Sprecherfarbe 6 |

### Flächen

Mildes Hell (Vorgabe): blaugrau von hinten nach vorn. Die Schale nutzt flaeche und flaeche-2, die Bausteine des Leitstands (Apps mit eigener Schale) bereich und karte bis karte-3.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--hg` | `#e4eaf2` | `#16202c` | Seitengrund |
| `--leiste` | `#f2f5f9` | `#101822` | Kopf, Seitenleiste, Fußleiste |
| `--flaeche` | `#ffffff` | `#1d2937` | Karten und Felder der Schale |
| `--flaeche-2` | `#e8edf4` | `#243344` | abgehobene Fläche: Knöpfe, Segmente, Pillen |
| `--mulde` | `#d2dbe6` | `#0c121a` | eingelassen: Fortschritt, Diagrammgrund, Code |
| `--bereich` | `#f7f9fc` | `#1d2937` | Bereich im Leitstand: Filter, Felder um Karten |
| `--karte` | `#ffffff` | `#243344` | Karte und Eingabe im Leitstand |
| `--karte-2` | `#e8edf4` | `#2c3d50` | Knopf und gewählter Eintrag im Leitstand |
| `--karte-3` | `#d9e2ec` | `#35485d` | überfahren und gedrückt im Leitstand |

### Schrift und Ränder

Drei Abstufungen der Schrift, Ränder nur als feine Linie oder Rahmen rundum.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--text` | `#16222e` | `#f1f5fa` | Haupttext |
| `--text-2` | `#42566b` | `#b4c2d3` | Nebentext |
| `--text-3` | `#5d7187` | `#8296ab` | schwacher Text, Etiketten, Symbole in Ruhe |
| `--rand` | `rgba(22, 34, 46, 0.12)` | `rgba(255, 255, 255, 0.09)` | Trennlinien und Rahmen |
| `--rand-stark` | `rgba(22, 34, 46, 0.2)` | `rgba(255, 255, 255, 0.16)` | Rahmen von Knöpfen und schwebenden Teilen im Leitstand |
| `--diagrammlinie` | `rgba(22, 34, 46, 0.09)` | `rgba(255, 255, 255, 0.07)` | Hilfslinien in Diagrammen |

### Akzent

Bernstein: Fläche und Schrift getrennt, damit der Kontrast in beiden Themen stimmt; nur für die eine Hauptsache einer Ansicht und für das, was gerade läuft.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--akzent` | `#9a5800` | `#ffb31a` | Bernstein als Schrift, 5,6 : 1 auf Weiß |
| `--akzent-weich` | `rgba(255, 164, 0, 0.2)` | `rgba(255, 164, 0, 0.16)` | Hinterlegung von Aktivem und Laufendem |
| `--akzent-flaeche` | `#ffa400` | `#ffa400` | Füllung der Hauptknöpfe und Schalter |
| `--auf-akzent` | `#1f1200` | `#1f1200` | Schrift auf der Akzentfläche, 9,2 : 1 |

### Bedeutung

Immer mit Wort, nie Farbe allein: gut, Warnung, Gefahr, Hinweis; je eine weiche Hinterlegung.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--gut` | `#0b7a52` | `#22e39a` | fertig, verbunden, erfolgreich |
| `--gut-weich` | `rgba(15, 155, 106, 0.14)` | `rgba(34, 227, 154, 0.14)` |  |
| `--warn` | `#b54708` | `#ff9a62` | Warnung, unterbrochen, Auslaufen |
| `--warn-weich` | `rgba(217, 83, 15, 0.13)` | `rgba(255, 122, 31, 0.16)` |  |
| `--gefahr` | `#c8243f` | `#ff5c74` | Fehler, Löschen, Halt |
| `--gefahr-weich` | `rgba(224, 30, 69, 0.12)` | `rgba(255, 59, 92, 0.16)` |  |
| `--info` | `#1f55d6` | `#3a7dff` | Hinweis, wartet (Königsblau) |
| `--toenung` | `20%` | `26%` | Stärke farbiger Hinterlegungen im Leitstand (color-mix mit transparent) |

### Palette

Zwischenfarben zwischen Blau und Bernstein für Arten und Zonen (Fähigkeiten, Modelle, Reihen in Diagrammen); immer mit Wort. Kräftig und Königsblau (Nutzer 16.10.2026).

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--himmel` | `#1f55d6` | `#3a7dff` | Text und Chat |
| `--petrol` | `#0a8aa3` | `#10b3c9` | Einbettung und Suche |
| `--tuerkis` | `#0a9e94` | `#14d8c8` | Übersetzung |
| `--minze` | `#0f9b6a` | `#22e39a` | Hören, Transkription |
| `--flieder` | `#5b45e6` | `#8f7bff` | Bild: beschreiben und erzeugen |
| `--violett` | `#8e2fe0` | `#c45cff` | Musik |
| `--rose` | `#e0186e` | `#ff3f8e` | Stimme: sprechen und klonen |
| `--koralle` | `#e04a1a` | `#ff6a3d` | Zone extern, Kosten |
| `--honig` | `#c79a00` | `#ffd21f` | wartet, angehalten, Vorwarnung |
| `--sand` | `#9a7a2e` | `#e2b96a` | passiv, Reserve, Werkzeug |
| `--stahl` | `#4f6d93` | `#8aa9c9` | Zone Heimnetz, neutral |

### Codehervorhebung

Farben für Code in Antworten und Belegen (Assistent): wie verbreitete Editoren, je Thema lesbar; Kommentare in --text-3.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--code-schluesselwort` | `#8839ef` | `#c4a7ff` | Schlüsselwörter und eingebaute Namen |
| `--code-zeichenkette` | `#2e7d32` | `#8ee3a0` | Zeichenketten und Attribute |
| `--code-zahl` | `#c2410c` | `#ffb38a` | Zahlen und feste Werte |
| `--code-titel` | `#1d64c8` | `#7cc0ff` | Namen von Funktionen und Abschnitten |

### Schatten und Schleier

Karten heben sich leicht ab; Schwebendes (Fenster, Menüs, Meldungen) deutlich.

| Marke | hell | dunkel | Zweck |
|---|---|---|---|
| `--schatten` | `0 1px 2px rgba(22, 34, 46, 0.06), 0 4px 14px rgba(22, 34, 46, 0.07)` | `0 1px 0 rgba(255, 255, 255, 0.03), 0 6px 18px rgba(0, 0, 0, 0.28)` | Karten der Schale |
| `--schatten-schwebend` | `0 16px 40px rgba(22, 34, 46, 0.16), 0 2px 6px rgba(22, 34, 46, 0.1)` | `0 16px 40px rgba(0, 0, 0, 0.42), 0 2px 6px rgba(0, 0, 0, 0.3)` | Fenster, Meldungen, Menüs |
| `--schleier` | `rgba(255, 255, 255, 0.78)` | `rgba(6, 11, 18, 0.74)` | hinter Dialogen des Leitstands |

### Schriftstufen

| Stufe | Wofür |
|---|---|
| dicht | Vorgabe der Schale: eine feste, dichte Schrift |
| klein | kleinste Stufe der Leitstelle; Etiketten unterschreiten dort bewusst 14 Pixel |
| mittel | Grundschrift 17 Pixel, nichts unter 15 |
| gross | Grundschrift 18 Pixel (Vorgabe von Leitstelle und Fundus, Nutzer 16.10.2026: "das was jetzt normal ist, sollte das größte sein"), Etiketten 15 Pixel wie in Fundus |

## Bausteine

Zwei Sätze Bausteine auf denselben Marken: die Schale (Apps in `<Schale>`, dicht) und der Leitstand (Apps, die ihre Schale selbst zeichnen, mit Schriftstufen). Das Markup unten ergibt mit dem Stil des Appkerns genau den Baustein; Svelte-Teile sind als solche genannt.

### Schale

#### Knöpfe

Klassen: `knopf`, `knopf primaer`, `knopf still`, `knopf gefahr`, `knopf klein`

Wann: Primär nur für die eine Hauptsache einer Ansicht; still für Nebensachen in Listen; Gefahr für Löschen und Abbrechen.

Warum: Ein Hauptknopf je Ansicht führt das Auge; gleiche Höhe und Rundung überall.

```html
<div class="knopfzeile"><button class="knopf primaer"><i class="fa-solid fa-play"></i> Starten</button>
<button class="knopf"><i class="fa-solid fa-rotate-right"></i> Wiederholen</button>
<button class="knopf still">Abbrechen</button>
<button class="knopf gefahr"><i class="fa-solid fa-trash-can"></i> Löschen</button></div>
```

#### Runde Knöpfe

Klassen: `rund`, `rund aktiv`

Wann: Werkzeuge mit Symbol allein (Kopf, Spieler, Leiste); immer mit title.

Warum: Wenig Platz, klar als Knopf erkennbar; aktiv in Akzent.

```html
<div class="knopfzeile"><button class="rund" title="Zurück"><i class="fa-solid fa-rotate-left"></i></button>
<button class="rund aktiv" title="Aktiv"><i class="fa-solid fa-microphone"></i></button></div>
```

#### Pillen im Kopf

Klassen: `pille`, `pille warn`, `pille aktiv`, `punkt`

Wann: Zustand der Verbindungen und laufende Arbeit im Kopf.

Warum: Ein Blick sagt, ob alles verbunden ist; nur Bedeutsames bekommt eine Pille.

```html
<div class="knopfzeile"><span class="pille"><span class="punkt"></span>alles verbunden</span>
<span class="pille warn"><span class="punkt"></span>Leitstelle gestört</span>
<span class="pille aktiv"><i class="fa-solid fa-gears"></i> 2 laufen</span></div>
```

#### Zustände

Klassen: `zustand laeuft`, `zustand wartet`, `zustand fertig`, `zustand fehler`, `zustand unterbrochen`

Wann: Zustand eines Auftrags oder Eintrags, immer als Wort.

Warum: Wort und Farbe zugleich; gleiche Farben für gleiche Bedeutung in allen Apps.

```html
<div class="knopfzeile"><span class="zustand laeuft">läuft</span><span class="zustand wartet">wartet</span>
<span class="zustand fertig">fertig</span><span class="zustand fehler">Fehler</span><span class="zustand unterbrochen">unterbrochen</span></div>
```

#### Stand als Pille

Klassen: `stand-pille fertig`, `stand-pille laeuft`, `stand-pille offen`, `stand-pille warn`

Wann: Stand einer Datei in Listen (transkribiert, läuft, offen).

Warum: Rund und weich, damit er neben Zuständen von Aufträgen unterscheidbar bleibt.

```html
<div class="knopfzeile"><span class="stand-pille fertig">fertig</span><span class="stand-pille laeuft">läuft</span>
<span class="stand-pille offen">offen</span><span class="stand-pille warn">veraltet</span></div>
```

#### Segment

Klassen: `segment`, `aktiv`

Wann: Filter und Umschalter mit zwei bis fünf Möglichkeiten.

Warum: Alle Möglichkeiten sichtbar, das Gewählte hebt sich als Fläche ab (keine Unterstreichung).

```html
<span class="segment"><button class="aktiv">Alle</button><button>Laufend</button><button>Fehler</button></span>
```

#### Reiterleiste

Klassen: `reiterleiste`, `aktiv`, `reiter-punkt`

Wann: Gruppen einer Seite mit eigener Adresse (etwa Einstellungen).

Warum: Der aktive Reiter hebt sich als Fläche mit Schatten ab, nie mit einseitiger Linie; ein Punkt zeigt Ungespeichertes.

```html
<nav class="reiterleiste"><button class="aktiv">Verbindungen</button><button>Zugang<span class="reiter-punkt"></span></button><button>Anzeige</button></nav>
```

#### Suche

Klassen: `suche`

Wann: Suchfeld über Listen.

Warum: Gleiche Höhe wie Knöpfe, Symbol vorn erklärt das Feld ohne Beschriftung.

```html
<label class="suche"><i class="fa-solid fa-magnifying-glass"></i><input class="eingabe-roh" placeholder="Suchen"></label>
```

#### Eingabe

Klassen: `eingabe`, `eingabe geaendert`, `auge`

Wann: Werte in Einstellungen und Formularen; geändert mit Akzentrahmen, Geheimnisse verdeckt mit Auge.

Warum: Was geändert, aber nicht gespeichert ist, fällt auf; Schlüssel stehen nie offen.

```html
<div class="eingabe"><input value="http://192.168.1.20:8530"></div>
<div class="eingabe geaendert" style="margin-top:8px"><span class="wert">kw_app_••••3f9a</span><button class="auge" title="Zeigen"><i class="fa-solid fa-eye"></i></button></div>
```

#### Schalter und Zähler

Klassen: `schalter`, `schalter an`, `zaehler`

Wann: Ein und aus; kleine Zahlen mit Schritten.

Warum: Ein Schalter zeigt den Zustand ohne Wort daneben nur zusammen mit seiner Beschriftung; der Zähler bleibt in seinen Grenzen.

```html
<div class="knopfzeile"><button class="schalter" aria-label="aus"></button><button class="schalter an" aria-label="an"></button>
<span class="zaehler"><button>-</button><input value="4"><button>+</button></span></div>
```

#### Chips

Klassen: `chips`, `chip`, `chip wahl`, `chip wahl an`

Wann: Listen kleiner Werte (Konten, Sprachen) und Mehrfachwahl.

Warum: Kompakt, jeder Wert einzeln entfernbar oder wählbar.

```html
<div class="chips"><span class="chip">Deutsch <button><i class="fa-solid fa-xmark"></i></button></span>
<button class="chip wahl an"><i class="fa-solid fa-check"></i> Text</button><button class="chip wahl">Bild</button></div>
```

#### Karte mit Feldern

Klassen: `karte`, `feld`, `was`, `name`, `beschreibung`, `herkunft`

Wann: Einstellungen und Gruppen von Werten: links was und warum, rechts der Wert.

Warum: Jeder Wert erklärt sich selbst; die Herkunft (gespeichert, Umgebung, Vorgabe) ist sichtbar.

```html
<div class="karte"><h2><i class="fa-solid fa-plug"></i> Verbindungen</h2>
<div class="feld"><div class="was"><div class="name">Leitstelle <span class="herkunft gespeichert">gespeichert</span></div>
<div class="beschreibung">Wohin die App ihre KI-Aufträge schickt.</div></div>
<div class="eingabe"><input value="http://192.168.1.20:8530"></div></div></div>
```

#### Auftrag

Klassen: `auftrag`, `art`, `titel`, `schritte`, `schritt`, `balken`, `unterzeile`, `zustand`; Svelte: `AuftragZeile`

Wann: Lange Arbeit mit Phasen: Schritte, Balken, Zustand und Aktion.

Warum: Was läuft, wie weit und was als Nächstes kommt, steht an einer Stelle; Abbrechen ist ein Klick.

```html
<div class="auftrag"><span class="art"><i class="fa-solid fa-gears"></i></span><div style="min-width:0">
<div class="titel"><span class="name">Folge 12 transkribieren</span><span class="wann">vor 2 Min.</span></div>
<div class="schritte"><span class="schritt fertig"><i class="fa-solid fa-check"></i> Hören</span><span class="linie"></span><span class="schritt jetzt"><i class="fa-solid fa-circle-notch fa-spin"></i> Schreiben</span><span class="linie"></span><span class="schritt">Ablegen</span></div>
<div class="balken"><span style="width:62%"></span></div><div class="unterzeile"><span>Abschnitt 31 von 50</span><span class="rechts">62 %</span></div></div>
<div class="aktionen"><span class="zustand laeuft">läuft</span><button class="knopf still" title="Abbrechen"><i class="fa-solid fa-stop"></i></button></div></div>
```

#### Zeile einer Liste

Klassen: `zeile`, `art`, `name`, `meta`, `stand-pille`

Wann: Dateien und Einträge in Listen, gewählt mit Akzentrahmen rundum.

Warum: Symbol, Name, Eckdaten und Stand in fester Ordnung; lange Namen enden mit Auslassung.

```html
<div class="zeile gewaehlt"><span class="art"><i class="fa-solid fa-file-audio"></i></span><div style="min-width:0"><div class="name">Hausversammlung Oktober.m4a</div><div class="meta">42 Min. · 38 MB</div></div><span class="stand-pille fertig">fertig</span><span></span></div>
```

#### Optionen über einer Liste

Klassen: `optionen`, `titel`

Wann: Einstellungen, die für die folgende Arbeit gelten.

Warum: Weich hinterlegt, damit sie nicht mit Inhalt verwechselt werden.

```html
<div class="optionen"><span class="titel">Für die Auswahl</span><label><button class="schalter an" aria-label="an"></button> Sprecher trennen</label></div>
```

#### Hinweisband

Klassen: `hinweis-band`, `knopfzeile`

Wann: Ein Hinweis zu dieser Seite mit Handlung (etwa eine aus der Kellerwolke geöffnete Datei).

Warum: Steht im Ablauf statt in einem Fenster und lässt sich gleich erledigen.

```html
<div class="hinweis-band"><i class="fa-solid fa-cloud"></i><span>Geöffnet aus der <b>Kellerwolke</b>, die Anfrage gilt noch 10 Minuten.</span><span class="knopfzeile"><button class="knopf">Zurück</button></span></div>
```

#### Rückfrage

Klassen: `rueckfrage`, `frage`, `aktionen`; Svelte: `Rueckfrage`

Wann: Vor dem Löschen und anderen Schritten ohne Rückweg, direkt an der Stelle.

Warum: Kein Browser-Dialog; die Frage steht dort, wo geklickt wurde.

```html
<div class="rueckfrage"><span class="frage">Aufnahme in den Papierkorb legen?</span><span class="aktionen"><button class="knopf still">Abbrechen</button><button class="knopf gefahr"><i class="fa-solid fa-trash-can"></i> Löschen</button></span></div>
```

#### Band unter dem Kopf

Klassen: `band`

Wann: Eine Verbindung fehlt oder die App antwortet nicht.

Warum: Steht über allem, ohne den Inhalt zu verdecken; die Handlung ist im Band.

```html
<div class="band"><i class="fa-solid fa-plug-circle-xmark"></i><span><b>Leitstelle</b> nicht erreichbar; Aufträge warten.</span><button class="knopf">Erneut versuchen</button></div>
```

#### Fehler und Leere

Klassen: `fehlertext`, `fehlerzeile`, `leer`

Wann: Fehlermeldung mit Ursache; leere Listen mit einem Satz, was zu tun ist.

Warum: Ein Fehler nennt immer die Ursache, eine leere Liste nie nur "nichts da".

```html
<div class="fehlertext">Die Kellerwolke antwortet mit 503: der Dienst startet gerade.</div>
<div class="leer">Noch keine Aufnahmen. Oben rechts aufnehmen oder eine Datei aus der Kellerwolke wählen.</div>
```

#### Tabelle

Klassen: `tabelle`, `zeit`, `stufe`

Wann: Protokoll und andere Listen mit vielen Spalten am Rechner (schmal als Liste).

Warum: Kopf in Versalien, Zeilen mit feiner Trennlinie; Zeiten schwach, Stufen mit Symbol und Farbe.

```html
<table class="tabelle"><thead><tr><th>Zeit</th><th>Ereignis</th><th>Text</th></tr></thead><tbody>
<tr><td class="zeit">10:42</td><td class="ereignis"><span class="stufe info"><i class="fa-solid fa-circle-info"></i></span> <code>auftrag.fertig</code></td><td>Folge 12 transkribiert</td></tr>
<tr><td class="zeit">10:40</td><td class="ereignis"><span class="stufe warnung"><i class="fa-solid fa-triangle-exclamation"></i></span> <code>leitstelle.halt</code></td><td>Leitstelle hält Aufträge an</td></tr></tbody></table>
```

#### Aufklappliste

Klassen: `auswahl`, `auswahl-knopf`, `auswahl-liste`; Svelte: `Auswahl`

Wann: Auswahl aus mehreren Möglichkeiten, statt des nativen Auswahlfelds.

Warum: Sieht in jedem Browser gleich aus, zeigt Hinweise je Möglichkeit, nie den technischen Schlüssel.

```html
<div class="auswahl"><button class="auswahl-knopf"><i class="fa-solid fa-microphone"></i><span class="auswahl-text">Stimme Zeit</span><i class="fa-solid fa-chevron-down auswahl-pfeil"></i></button></div>
```

#### Etiketten und Zahlen

Klassen: `abschnitt`, `zahl`

Wann: Kleine Überschrift über Gruppen; Zahlen in der Zahlenschrift.

Warum: Versalien gliedern ohne Gewicht; Zahlen bleiben als Werte erkennbar.

```html
<div class="abschnitt">Phasen</div><p>Dauer <span class="zahl">00:42:17</span>, <span class="zahl">1.284</span> Wörter</p>
```

### Leitstand

#### Knöpfe

Klassen: `knopf`, `knopf haupt`, `knopf ohne`, `knopf gefahr`, `knopf gefahr-voll`, `knopf klein`, `knopf symbol`

Wann: Haupt nur für die eine Hauptsache einer Ansicht; ohne für Nebensachen; gefahr-voll nur für den harten Schnitt (Halt).

Warum: Alle Knöpfe gleich gebaut und gleich hoch; die Fläche sagt, was wichtig ist.

```html
<div style="display:flex; flex-wrap:wrap; gap:8px"><button class="knopf haupt"><i class="fa-solid fa-play"></i> Starten</button>
<button class="knopf"><i class="fa-solid fa-rotate-right"></i> Wiederholen</button>
<button class="knopf ohne">Abbrechen</button>
<button class="knopf gefahr">Entfernen</button>
<button class="knopf gefahr-voll"><i class="fa-solid fa-hand"></i> Halt</button>
<button class="knopf symbol klein" title="Mehr"><i class="fa-solid fa-ellipsis"></i></button></div>
```

#### Zähler und Pillen

Klassen: `zaehler`, `zaehler pille`, `zaehler warnung`, `zaehler gefahr`, `zaehler akzent`

Wann: Zahl dort, wo etwas Bedeutsames passiert (Seitenleiste, Reiter); Farbe nach Bedeutung.

Warum: Nie Gesamtzahlen als Pille: nur was Aufmerksamkeit braucht, fällt auf.

```html
<div style="display:flex; gap:8px; align-items:center"><span class="zaehler">12</span><span class="zaehler pille warnung">3</span>
<span class="zaehler pille gefahr">1</span><span class="zaehler akzent">2 laufen</span><span class="zaehler pille honig">4</span></div>
```

#### Zustände

Klassen: `zustand laeuft`, `zustand wartet`, `zustand fertig`, `zustand fehler`, `zustand pausiert`, `zustand auslaufend`, `zustand aus`

Wann: Zustand eines Auftrags, Dienstes oder Rechners, immer mit Wort.

Warum: Wort und Farbe zugleich; die Hinterlegung mischt die Farbe der Bedeutung mit der Marke `--toenung`.

```html
<div style="display:flex; flex-wrap:wrap; gap:8px"><span class="zustand laeuft"><i class="fa-solid fa-circle-notch dreht"></i> läuft</span><span class="zustand wartet">wartet</span>
<span class="zustand fertig">fertig</span><span class="zustand fehler">Fehler</span><span class="zustand pausiert">angehalten</span>
<span class="zustand auslaufend">läuft aus</span><span class="zustand aus">aus</span></div>
```

#### Fähigkeiten und Zonen

Klassen: `faehigkeit text`, `faehigkeit einbettung`, `faehigkeit hoeren`, `faehigkeit bild`, `faehigkeit stimme`, `zone heim`, `zone extern`

Wann: Art einer Arbeit (Fähigkeit) und wo sie läuft (Zone).

Warum: Die Farben der Palette unterscheiden Arten; das Wort steht immer dabei.

```html
<div style="display:flex; flex-wrap:wrap; gap:8px"><span class="faehigkeit text"><i class="fa-solid fa-comment-dots"></i> Text</span><span class="faehigkeit einbettung"><i class="fa-solid fa-diagram-project"></i> Einbettung</span>
<span class="faehigkeit hoeren"><i class="fa-solid fa-ear-listen"></i> Hören</span><span class="faehigkeit bild"><i class="fa-solid fa-image"></i> Bild</span><span class="faehigkeit stimme"><i class="fa-solid fa-microphone-lines"></i> Stimme</span>
<span class="zone heim"><i class="fa-solid fa-house"></i> Heimnetz</span><span class="zone extern"><i class="fa-solid fa-cloud"></i> extern</span></div>
```

#### Filter und Chips

Klassen: `filter`, `etikett`, `chip`, `chip aktiv`, `trenner`

Wann: Filterleiste über Listen: Etikett, Chips zum Umschalten, rechts die Suche.

Warum: Was gefiltert ist, bleibt sichtbar; aktive Chips in Akzent.

```html
<div class="filter"><span class="etikett">Zustand</span><button class="chip aktiv">Läuft <span class="zaehler">2</span></button>
<button class="chip">Wartet</button><span class="trenner"></span><button class="chip">Fehler</button></div>
```

#### Eingaben

Klassen: `eingabe`, `suche`

Wann: Werte und Suchfelder.

Warum: Gleiche Höhe wie Knöpfe; Fokus mit ruhigem Bernstein-Rahmen.

```html
<div style="display:flex; flex-direction:column; gap:8px"><input class="eingabe" value="http://192.168.1.20:8530">
<label class="suche"><i class="fa-solid fa-magnifying-glass"></i><input placeholder="Suchen"></label></div>
```

#### Bereich und Karten

Klassen: `bereich`, `karte`, `karte klickbar`, `karte gewaehlt`

Wann: Bereich gruppiert Karten; Karten tragen je einen Gegenstand, klickbar mit Fläche beim Überfahren.

Warum: Drei Flächenstufen (Bereich, Karte, Knopf) ordnen von hinten nach vorn.

```html
<div class="bereich"><div class="karte"><h3><i class="fa-solid fa-server"></i> Mac Studio <span class="rechts">128 GB</span></h3><p class="leise">Läufer und Dienste dieses Rechners.</p></div>
<div class="karte klickbar gewaehlt"><h3><i class="fa-solid fa-microchip"></i> Pi</h3><p class="leise">gewählt</p></div></div>
```

#### Reiter

Klassen: `reiter`, `aktiv`

Wann: Teile einer Ansicht mit gleichem Gegenstand.

Warum: Der aktive Reiter ist eine Fläche mit Rahmen rundum, nie eine Linie an einer Seite.

```html
<div class="reiter"><button class="aktiv"><i class="fa-solid fa-list"></i> Laufend <span class="zaehler pille">2</span></button><button>Fertig</button><button>Fehler</button></div>
```

#### Hinweise

Klassen: `hinweis`, `hinweis warnung`, `hinweis gefahr`, `hinweis erfolg`

Wann: Hinweis im Ablauf mit Bedeutung; rechts die Handlung.

Warum: Steht dort, wo er gilt, statt in einem Fenster.

```html
<div style="display:flex; flex-direction:column; gap:8px"><div class="hinweis"><i class="fa-solid fa-circle-info"></i><span>Der Mac schläft; Aufträge warten, bis er wach ist.</span></div>
<div class="hinweis warnung"><i class="fa-solid fa-triangle-exclamation"></i><span>Speicher knapp: 4 GB frei.</span></div>
<div class="hinweis gefahr"><i class="fa-solid fa-circle-xmark"></i><span>Dienst nicht erreichbar.</span><span class="rechts"><button class="knopf klein">Prüfen</button></span></div></div>
```

#### Bestätigung auf der Seite

Klassen: `bestaetigen`, `rechts`

Wann: Vor Schritten ohne Rückweg, direkt an der Stelle.

Warum: Kein Browser-Dialog; die Folgen stehen in der Frage.

```html
<div class="bestaetigen"><i class="fa-solid fa-trash-can"></i><span>Quelle entfernen? Ihre Abschnitte verschwinden aus der Suche.</span><span class="rechts"><button class="knopf ohne">Abbrechen</button><button class="knopf gefahr">Entfernen</button></span></div>
```

#### Kennzahlen

Klassen: `kennzahlen`, `kennzahl`, `kennzahl laeuft`, `kennzahl fehler`

Wann: Wenige große Zahlen oben auf einer Übersicht.

Warum: In der Zahlenschrift, die Farbe nur für Bedeutsames.

```html
<div class="kennzahlen"><div class="kennzahl laeuft"><b>2</b><span>Läuft</span></div><div class="kennzahl wartet"><b>5</b><span>Wartet</span></div>
<div class="kennzahl erfolg"><b>128</b><span>Heute fertig</span></div><div class="kennzahl fehler"><b>1</b><span>Fehler heute</span></div></div>
```

#### Fortschritt und Ablauf

Klassen: `balken`, `balken fertig`, `balken lebt`, `kette`, `schritt`, `pfeil`

Wann: Fortschritt einer Arbeit; Schritte eines Ablaufs als Kette.

Warum: Der laufende Teil lebt sichtbar, Erledigtes ist grün, Offenes blass.

```html
<div style="display:flex; flex-direction:column; gap:12px"><div class="balken lebt"><b style="width:62%"></b></div><div class="balken fertig"><b style="width:100%"></b></div>
<div class="kette"><span class="schritt erledigt"><i class="fa-solid fa-check"></i> Lesen</span><span class="pfeil erledigt"></span><span class="schritt jetzt"><i class="fa-solid fa-circle-notch dreht"></i> Einbetten</span><span class="pfeil laeuft"></span><span class="schritt offen">Ablegen</span></div></div>
```

#### Einstellung mit Schalter und Stufen

Klassen: `einstellung`, `name`, `erklaerung`, `wert`, `schalter`, `stufen`

Wann: Einstellungen: links was und warum, rechts das Bedienelement in fester Spalte.

Warum: Werte stehen immer an derselben Stelle; Stufen für kleine Wertebereiche statt Auswahlfeld.

```html
<div><div class="einstellung"><div><div class="name">Hintergrund erlaubt</div><div class="erklaerung">Stapelarbeit läuft nur, wenn nichts anderes wartet.</div></div><div class="wert"><button class="schalter an" aria-label="an"></button></div></div>
<div class="einstellung"><div><div class="name">Schriftgröße</div><div class="erklaerung">Gilt auf diesem Gerät.</div></div><div class="wert"><span class="stufen"><button>Mittel</button><button class="an">Groß</button></span></div></div></div>
```

#### Tabelle

Klassen: `tabelle`, `zahl`

Wann: Listen mit vielen Spalten.

Warum: Kopf in Versalien und fest beim Rollen; Zahlen rechts in der Zahlenschrift.

```html
<table class="tabelle"><thead><tr><th>Modell</th><th class="zahl">Größe</th><th>Zustand</th></tr></thead><tbody>
<tr><td>Qwen 80B</td><td class="zahl">46 GB</td><td><span class="zustand fertig">geladen</span></td></tr>
<tr><td>Einbettung</td><td class="zahl">1,2 GB</td><td><span class="zustand laeuft">lädt</span></td></tr></tbody></table>
```

#### Tabelle, die schmal Karten wird

Klassen: `tabellen-raum`, `tabelle karten`, `data-titel`

Wann: Tabellen mit vielen Spalten in Spalten, die schmal werden können (neben einer Leiste, am Tablet).

Warum: Unter 900 Pixeln Breite des Raums wird jede Zeile eine Karte mit Etiketten aus data-titel: nichts wird abgeschnitten, nichts rollt seitlich.

```html
<div class="tabellen-raum" style="max-width: 420px"><table class="tabelle karten"><thead><tr><th>Dienst</th><th>Rechner</th><th>Zustand</th><th>Plätze</th></tr></thead><tbody>
<tr><td><b>Modell-Läufer</b></td><td data-titel="Rechner">Mac Studio</td><td data-titel="Zustand"><span class="zustand fertig">bereit</span></td><td data-titel="Plätze" class="zahl">2</td></tr></tbody></table></div>
```

#### Etikett und Punkt

Klassen: `etikett`, `punkt`, `punkt warnung`, `punkt lebt`, `leise`, `schwach`

Wann: Kleine Überschrift über Gruppen; Punkt für den Zustand einer Verbindung.

Warum: Versalien gliedern ohne Gewicht; der Punkt lebt nur, wenn etwas läuft.

```html
<div><div class="etikett">Wo was läuft</div><p><span class="punkt lebt"></span>Pi <span class="schwach">immer an</span></p><p><span class="punkt warnung"></span>Mac Studio <span class="schwach">schläft</span></p></div>
```

#### Leerer Zustand

Klassen: `leer`

Wann: Leere Liste oder fehlende Verbindung, mit einem Satz, was zu tun ist.

Warum: Nie nur "nichts da": der nächste Schritt steht dabei.

```html
<div class="leer"><i class="fa-solid fa-satellite-dish"></i><h2>Noch keine Dienste</h2><p>Unter Anschluss einen Rechner und seinen Dienst eintragen.</p></div>
```

## Prüfung

Der Haken jeder App prüft bei jedem Commit die vorgemerkten Dateien; `python -m appkern.werkzeuge marken` zeigt alle Befunde eines Repos. Befunde: feste Farbe (auch als Rückfall `var(--x, #fff)` und in `fill`/`stroke`), feste Schrift, feste Schriftgröße (Symbole auf `i`, `svg`, `.fa-...` ausgenommen), überschriebene Marke. Dazu wie bisher: keine einseitigen Streifen, kein `!important`, keine Regeln auf Klassen der Schale, nur gerade Zeichen. Entwürfe (`mockups`, `docs`) zählen nicht.
