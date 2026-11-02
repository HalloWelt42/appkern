# Zugänge der Apps beim Ausrollen (HELF-77)

Kein Schlüssel zwischen Apps wird mehr von Hand eingetragen oder kopiert. Das Ausrollen einer App besorgt ihre
Zugänge zur Leitstelle und zur Kellerwolke selbst und legt sie in die Geheimnisdatei der App auf dem Pi (Rechte 600).
Angezeigt wird kein Schlüssel, weder im Ausrollen noch in einer Oberfläche.

## Entscheidungen des Nutzers (Dialog vom 02.11.2026)

| Frage | Entscheidung |
|---|---|
| Weg | Beim Ausrollen: fehlt der Zugang, legt das Ausrollen ihn an und schreibt den Schlüssel in die Geheimnisdatei der App |
| Rechte | Was die App erklärt: jede App nennt in ihrer Ausrollbeschreibung die Fähigkeiten, die sie braucht (etwa Text, Einbettung, Bild); genau die legt die Leitstelle an, mehr nur, wenn die App es später erklärt |
| Schlüssel bei weiteren Ausrollvorgängen | Bleibt; erneuert wird nur mit einem Schalter beim Ausrollen (etwa bei Verdacht), der alte gilt dann sofort nicht mehr |
| Apps mit eingetragenem Schlüssel | Alle umstellen: beim nächsten Ausrollen den vorhandenen Zugang übernehmen, den Schlüssel in die Geheimnisdatei; die Einstellungen zeigen die Verbindung nur noch zum Ansehen ("vom Ausrollen gesetzt") |
| Kellerwolke | Gleich behandelt: derselbe Schritt besorgt auch den Zugang zur Kellerwolke (über ihr Werkzeug app_zugang) |
| Reihenfolge | Baustein im Ausrollen des Appkerns, Pilot Nachschlag; nach Freigabe des Nutzers alle übrigen Apps |

## Bauplan

1. Ausrollbeschreibung der App (deploy/ausrollen.toml): Abschnitt `[zugaenge]` mit den Fähigkeiten für die Leitstelle
   und dem Namen der App in der Kellerwolke.
2. Schritt "Zugänge" im Ausrollen (appkern.werkzeuge.ausrollen), vor dem Start: Zugang in der Leitstelle suchen
   (Verwaltung, nur aus dem Heimnetz), fehlt er, anlegen mit den erklärten Fähigkeiten; Fähigkeiten nachziehen, wenn
   die App mehr erklärt; Kellerwolke über app_zugang auf ihrem Rechner. Schlüssel nur per SSH in die Geheimnisdatei,
   nie in die Ausgabe. Schalter `--zugaenge-erneuern`.
3. Das Gerüst der App liest die Schlüssel aus der Geheimnisdatei; ist sie da, gilt sie vor den Einstellungen, und die
   Einstellungen zeigen die Verbindung nur zum Ansehen.
4. Übernahme bestehender Zugänge: gibt es die App in der Leitstelle schon, wird ihr Zugang übernommen; der Schlüssel
   wechselt dabei nur, wenn die Leitstelle ihn nicht noch einmal herausgeben kann (dann einmalig neu, ohne Anzeige).
5. Prüfung: Tests im Appkern mit nachgestellter Leitstelle und Kellerwolke; Pilot Nachschlag im Betrieb.
