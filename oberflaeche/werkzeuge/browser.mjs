// Unsichtbarer Chrome für Prüfungen, Bildschirmfotos und Hilfsskripte (HELF-76), so gestartet, dass nichts liegen bleibt:
// Jeder Lauf hat seinen eigenen Chrome mit Wegwerfprofil, verbunden über eine Leitung (--remote-debugging-pipe) statt über
// einen Port. Endet der Lauf auf irgendeine Weise, auch hart beendet oder abgestürzt, geht die Leitung zu und Chrome beendet
// sich mit all seinen Helfern selbst. Beim regulären Ende, bei Strg+C und SIGTERM beendet der Lauf ihn sofort und löscht
// das Profil; Profile hart beendeter Läufe löscht der nächste Lauf (der Ordnername trägt die Prozessnummer des Laufs).
//
//   import { oeffneSeite } from ".../appkern-oberflaeche/oberflaeche/werkzeuge/browser.mjs";
//   const seite = await oeffneSeite();
//   seite.beiEreignis((m) => { if (m.method === "Runtime.exceptionThrown") ... });
//   await seite.rufe("Page.navigate", { url });
//   await seite.schliesse();
//
// Schalter: stumm, Abspielen ohne vorheriges Antippen (Prüfungen klicken per Skript), Kamera und Mikrofon als Attrappe
// ohne Rückfrage, ohne Zwischenspeicher für Zurück (verlassene Seiten hielten sonst ihre Ereignisströme offen).
// Umgebung: CHROME (Programm).
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PRAEFIX = "appkern-browser-";
const SCHALTER = ["--headless=new", "--hide-scrollbars", "--mute-audio", "--autoplay-policy=no-user-gesture-required", "--no-first-run",
  "--disable-features=BackForwardCache", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
  "--remote-debugging-pipe"];
const FRIST_MS = 30000;          // Vorgabe: so lange wartet ein Aufruf auf seine Antwort

// Löschen darf einen Lauf nie scheitern lassen; was bleibt, löscht der nächste Lauf
const loesche = (ordner) => { try { fs.rmSync(ordner, { recursive: true, force: true, maxRetries: 5 }); } catch { /* später */ } };
const lebt = (pid) => { try { process.kill(pid, 0); return true; } catch (f) { return f.code === "EPERM"; } };

// Profile von Läufen, die es nicht mehr gibt
function raeumeAlteProfile() {
  for (const name of fs.readdirSync(os.tmpdir())) {
    const pid = Number(name.startsWith(PRAEFIX) && name.slice(PRAEFIX.length).split("-")[0]);
    if (pid && !lebt(pid)) loesche(path.join(os.tmpdir(), name));
  }
}

// Alles, was dieser Prozess gestartet hat; beim Ende des Prozesses abgeräumt
const gestartet = new Set();
function raeumeAb(eintrag) {
  // die ganze Gruppe: Chrome und seine Helfer
  try { process.kill(-eintrag.chrome.pid, "SIGKILL"); } catch { /* schon weg */ }
  loesche(eintrag.profil);
  gestartet.delete(eintrag);
}
let abraeumenEingerichtet = false;
function richteAbraeumenEin() {
  if (abraeumenEingerichtet) return;
  abraeumenEingerichtet = true;
  process.on("exit", () => { for (const e of [...gestartet]) raeumeAb(e); });
  for (const [signal, code] of [["SIGINT", 130], ["SIGTERM", 143], ["SIGHUP", 129]]) {
    process.on(signal, () => process.exit(code));
  }
}

// Öffnet einen eigenen Chrome mit einer leeren Seite
export async function oeffneSeite({ frist = FRIST_MS } = {}) {
  raeumeAlteProfile();
  richteAbraeumenEin();
  const profil = fs.mkdtempSync(path.join(os.tmpdir(), `${PRAEFIX}${process.pid}-`));
  const chrome = spawn(CHROME, [...SCHALTER, `--user-data-dir=${profil}`, "about:blank"],
    { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"], detached: true });   // eigene Gruppe, siehe raeumeAb
  const beendet = new Promise((r) => chrome.once("exit", r));
  const eintrag = { chrome, profil };
  gestartet.add(eintrag);
  const [hin, her] = [chrome.stdio[3], chrome.stdio[4]];
  let n = 0;
  let rest = "";
  const offen = new Map();
  const beobachter = [];
  let sitzung;
  her.on("data", (d) => {
    const teile = (rest + d.toString()).split("\0");
    rest = teile.pop();
    for (const t of teile) {
      const m = JSON.parse(t);
      if (m.id && offen.has(m.id)) { offen.get(m.id)(m); offen.delete(m.id); continue; }
      if (m.method && m.sessionId === sitzung) for (const b of beobachter) b(m);
    }
  });
  hin.on("error", () => { /* Chrome ist weg; offene Aufrufe laufen in ihre Frist */ });
  const sende = (method, params = {}, sessionId) => new Promise((r, f) => {
    const id = ++n;
    const uhr = setTimeout(() => { offen.delete(id); f(new Error(`keine Antwort auf ${method} binnen ${frist / 1000} s`)); }, frist);
    offen.set(id, (m) => { clearTimeout(uhr); r(m); });
    hin.write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + "\0");
  });
  const pruefe = (m, was) => { if (m.error) throw new Error(`${was}: ${m.error.message}`); return m.result; };
  try {
    const { targetId } = pruefe(await sende("Target.createTarget", { url: "about:blank" }), "Seite anlegen");
    sitzung = pruefe(await sende("Target.attachToTarget", { targetId, flatten: true }), "Seite verbinden").sessionId;
  } catch (f) { raeumeAb(eintrag); throw f; }
  return {
    // Antwort wie im Protokoll ({ result } oder { error }); Ereignisse kommen nur von dieser Seite
    rufe: (method, params) => sende(method, params, sitzung),
    beiEreignis: (b) => { beobachter.push(b); },
    // Chrome selbst schließen lassen und warten, bis er samt Helfern weg ist; erst dann das Profil löschen
    schliesse: async () => {
      sende("Browser.close").catch(() => { /* geht mit Chrome zu */ });
      await Promise.race([beendet, new Promise((r) => setTimeout(r, 5000))]);
      raeumeAb(eintrag);
    },
  };
}
