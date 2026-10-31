// Geteilter Hintergrund-Browser für Prüfungen, Bildschirmfotos und Hilfsskripte (HELF-76): ein unsichtbarer Chrome für
// alle gleichzeitigen Läufe statt eines eigenen je Lauf. Jeder Lauf bekommt darin einen eigenen Bereich (Browserkontext,
// wie ein privates Fenster: eigene Cookies, eigener Speicher) mit einer Seite. Chrome räumt den Bereich selbst weg,
// sobald die Verbindung des Laufs endet, auch wenn das Skript abstürzt oder hart beendet wird.
// Nichts bleibt ewig im Speicher: ein Wächter (dieselbe Datei mit --waechter) startet den Chrome und hält ihn über eine
// Leitung (--remote-debugging-pipe). Ist eine Weile kein Bereich mehr offen, schließt er ihn und endet; endet der Wächter
// auf irgendeine Weise, geht die Leitung zu und Chrome beendet sich selbst. Der nächste Lauf startet beides neu.
//
//   import { oeffneSeite } from ".../appkern-oberflaeche/oberflaeche/werkzeuge/browser.mjs";
//   const seite = await oeffneSeite();
//   seite.beiEreignis((m) => { if (m.method === "Runtime.exceptionThrown") ... });
//   await seite.rufe("Page.navigate", { url });
//   await seite.schliesse();
//
// Schalter für alle: stumm, Kamera und Mikrofon als Attrappe ohne Rückfrage, ohne Zwischenspeicher für Zurück (verlassene
// Seiten hielten sonst ihre Ereignisströme offen). Umgebung: CHROME (Programm), APPKERN_BROWSER_PROFIL (Profilordner),
// APPKERN_BROWSER_LEERLAUF_S (so viele Sekunden ohne offenen Bereich, dann schließt der Wächter, Vorgabe 120).
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PROFIL = process.env.APPKERN_BROWSER_PROFIL ?? path.join(os.homedir(), "Library", "Caches", "Appkern", "browser");
const LEERLAUF_MS = Number(process.env.APPKERN_BROWSER_LEERLAUF_S ?? 120) * 1000;
const SCHALTER = ["--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run",
  "--disable-features=BackForwardCache", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
  "--remote-debugging-pipe", "--remote-debugging-port=0", "--remote-allow-origins=*", `--user-data-dir=${PROFIL}`,
  "about:blank"];
const START_MS = 30000;
const SPERRE_ALT_MS = 60000;     // eine Startsperre, älter als das, gehört einem abgestürzten Lauf
const FRIST_MS = 30000;          // Vorgabe: so lange wartet ein Aufruf auf seine Antwort
const PRUEF_MS = 5000;           // so oft schaut der Wächter nach offenen Bereichen

const warte = (ms) => new Promise((r) => setTimeout(r, ms));

// Adresse des laufenden geteilten Chrome, oder null
async function adresse() {
  let port;
  try { port = fs.readFileSync(path.join(PROFIL, "DevToolsActivePort"), "utf8").split("\n")[0]; } catch { return null; }
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(2000) });
    return (await r.json()).webSocketDebuggerUrl;
  } catch { return null; }
}

// Startet Wächter und Chrome, falls sie nicht laufen; eine Sperre verhindert, dass zwei Läufe gleichzeitig starten
async function sorgeFuerBrowser() {
  const da = await adresse();
  if (da) return da;
  fs.mkdirSync(PROFIL, { recursive: true });
  const sperre = `${PROFIL}.start`;
  const ende = Date.now() + START_MS;
  while (Date.now() < ende) {
    try { fs.mkdirSync(sperre); break; } catch {
      try { if (Date.now() - fs.statSync(sperre).mtimeMs > SPERRE_ALT_MS) fs.rmSync(sperre, { recursive: true, force: true }); } catch { /* weg */ }
      const nun = await adresse();
      if (nun) return nun;
      await warte(200);
    }
  }
  try {
    const nun = await adresse();
    if (nun) return nun;
    fs.rmSync(path.join(PROFIL, "DevToolsActivePort"), { force: true });
    spawn(process.execPath, [fileURLToPath(import.meta.url), "--waechter"], { detached: true, stdio: "ignore" }).unref();
    while (Date.now() < ende) {
      await warte(100);
      const neu = await adresse();
      if (neu) return neu;
    }
    throw new Error(`der geteilte Browser startet nicht binnen ${START_MS / 1000} s (${CHROME})`);
  } finally {
    fs.rmSync(sperre, { recursive: true, force: true });
  }
}

async function verbinde(frist) {
  const ws = new WebSocket(await sorgeFuerBrowser());
  await new Promise((r, f) => { ws.addEventListener("open", r); ws.addEventListener("error", () => f(new Error("keine Verbindung zum geteilten Browser"))); });
  let n = 0;
  const offen = new Map();
  const beobachter = [];
  let sitzung;
  ws.addEventListener("message", (e) => {
    const m = JSON.parse(e.data);
    if (m.id && offen.has(m.id)) { offen.get(m.id)(m); offen.delete(m.id); return; }
    if (m.method && m.sessionId === sitzung) for (const b of beobachter) b(m);
  });
  const sende = (method, params = {}, sessionId) => new Promise((r, f) => {
    const id = ++n;
    const uhr = setTimeout(() => { offen.delete(id); f(new Error(`keine Antwort auf ${method} binnen ${frist / 1000} s`)); }, frist);
    offen.set(id, (m) => { clearTimeout(uhr); r(m); });
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const pruefe = (m, was) => { if (m.error) throw new Error(`${was}: ${m.error.message}`); return m.result; };
  try {
    // disposeOnDetach: Chrome räumt den Bereich weg, sobald diese Verbindung endet
    const { browserContextId } = pruefe(await sende("Target.createBrowserContext", { disposeOnDetach: true }), "Bereich anlegen");
    const { targetId } = pruefe(await sende("Target.createTarget", { url: "about:blank", browserContextId }), "Seite anlegen");
    sitzung = pruefe(await sende("Target.attachToTarget", { targetId, flatten: true }), "Seite verbinden").sessionId;
    return {
      // Antwort wie im Protokoll ({ result } oder { error }); Ereignisse kommen nur von dieser Seite
      rufe: (method, params) => sende(method, params, sitzung),
      beiEreignis: (b) => { beobachter.push(b); },
      schliesse: async () => {
        try { await sende("Target.disposeBrowserContext", { browserContextId }); } catch { /* endet mit der Verbindung ohnehin */ }
        ws.close();
      },
    };
  } catch (f) { ws.close(); throw f; }
}

// Öffnet einen eigenen Bereich mit einer leeren Seite im geteilten Chrome. Schließt der Wächter den Chrome genau
// zwischen Anmelden und Bereich, startet der zweite Versuch ihn neu.
export async function oeffneSeite({ frist = FRIST_MS } = {}) {
  try { return await verbinde(frist); } catch { return await verbinde(frist); }
}

// Wächter: startet Chrome an der Leitung und schließt ihn nach LEERLAUF_MS ohne offenen Bereich
async function waechter() {
  const chrome = spawn(CHROME, SCHALTER, { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
  chrome.on("exit", () => process.exit(0));
  const [hin, her] = [chrome.stdio[3], chrome.stdio[4]];
  let n = 0;
  let rest = "";
  const offen = new Map();
  her.on("data", (d) => {
    const teile = (rest + d.toString()).split("\0");
    rest = teile.pop();
    for (const t of teile) { const m = JSON.parse(t); offen.get(m.id)?.(m); offen.delete(m.id); }
  });
  const sende = (method) => new Promise((r) => { const id = ++n; offen.set(id, r); hin.write(JSON.stringify({ id, method }) + "\0"); });
  let zuletzt = Date.now();
  for (;;) {
    await warte(PRUEF_MS);
    const m = await Promise.race([sende("Target.getBrowserContexts"), warte(FRIST_MS)]);
    if (!m?.result) break;                                   // Chrome antwortet nicht mehr
    if (m.result.browserContextIds.length) zuletzt = Date.now();
    else if (Date.now() - zuletzt > LEERLAUF_MS) break;
  }
  await Promise.race([sende("Browser.close"), warte(5000)]);
  chrome.kill("SIGKILL");
  process.exit(0);
}

if (process.argv[2] === "--waechter" && process.argv[1] === fileURLToPath(import.meta.url)) await waechter();
