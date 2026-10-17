// Hochladen mit Fortschritt (fetch meldet beim Senden keinen Fortschritt, darum XMLHttpRequest). `uploads.liste` zeigt
// die laufenden; solange einer läuft, lädt die App nicht neu. Die Adresse bestimmt die App (ihr eigener Weg), die
// Antwort ist, was ihr Backend liefert.
import { token } from "./api.svelte";
import { arbeit } from "./arbeit.svelte";

export interface Upload {
  id: string;
  name: string;
  groesse: number;
  gesendet: number;
  fehler: string;
  fertig: boolean;
}

export const uploads = $state<{ liste: Upload[] }>({ liste: [] });

export function hochladen<T>(adresse: string, daten: Blob, name: string, erfolg = 201): Promise<T> {
  const eintrag: Upload = { id: crypto.getRandomValues(new Uint32Array(2)).join("-"), name, groesse: daten.size, gesendet: 0,
    fehler: "", fertig: false };
  uploads.liste = [eintrag, ...uploads.liste];
  const u = uploads.liste[0];
  arbeit.hochladen += 1;
  return new Promise<T>((fertig, fehlgeschlagen) => {
    const x = new XMLHttpRequest();
    x.open("POST", adresse);
    x.setRequestHeader("X-Kellerwolke-Sitzung", token());
    x.setRequestHeader("Content-Type", daten.type || "application/octet-stream");
    x.upload.onprogress = (e) => (u.gesendet = e.loaded);
    const ende = () => (arbeit.hochladen = Math.max(0, arbeit.hochladen - 1));
    x.onload = () => {
      ende();
      if (x.status === erfolg) {
        u.fertig = true;
        u.gesendet = u.groesse;
        setTimeout(() => (uploads.liste = uploads.liste.filter((z) => z.id !== u.id)), 4000);
        fertig(JSON.parse(x.responseText) as T);
      } else {
        let meldung = `Fehler ${x.status}`;
        try {
          meldung = JSON.parse(x.responseText).detail ?? meldung;
        } catch {
          // Text bleibt
        }
        u.fehler = meldung;
        fehlgeschlagen(new Error(meldung));
      }
    };
    x.onerror = () => {
      ende();
      u.fehler = "Verbindung abgebrochen";
      fehlgeschlagen(new Error(u.fehler));
    };
    x.send(daten);
  });
}

export function uploadEntfernen(id: string): void {
  uploads.liste = uploads.liste.filter((u) => u.id !== id);
}
