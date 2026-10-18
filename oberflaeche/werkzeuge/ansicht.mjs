// Ansichtsprüfung (Lehren 12 und 13 der Transkription): jede Seite der App in allen Breiten, hell und dunkel, in einem
// unsichtbaren Chrome. Misst seitliches Rollen, Überlauf über den rechten Rand, Kontrast von Text und die Verschiebung
// fester Teile beim Zustandswechsel; legt von jeder Ansicht ein Bild ab.
//
//   node frontend/node_modules/appkern-oberflaeche/oberflaeche/werkzeuge/ansicht.mjs <basis> [--ausgabe ORDNER]
//        [--nur SEITE] [--thema hell|dunkel]
//
// im Wurzelordner der App (tools/ansicht.sh). Seiten und Zustandswechsel stehen in frontend/ansicht.json:
//   { "seiten": [ { "name": "start", "pfad": "/" },
//                 { "name": "aufnehmen", "pfad": "/aufnahmen", "nur": [1440, 390],
//                   "wechsel": [ { "klick": "Aufnehmen", "fest": [".rek-leiste"] } ] } ] }
// `klick` ist ein CSS-Selektor oder der Text eines Knopfs; `fest` sind Teile, die sich beim Wechsel nicht bewegen dürfen.
// Angemeldet wird mit dem Testzugang aus backend/.env.test (KELLERWOLKE_KENNUNG, KELLERWOLKE_PASSWORT); die Werte
// werden nie ausgegeben. Ein Browser-Dialog (alert, confirm, beforeunload) ist selbst ein Befund und wird geschlossen;
// antwortet der Browser nicht binnen 30 Sekunden, ist auch das ein Befund. Ende mit 1, wenn es Befunde gibt.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const BREITEN = [[1920, 1080], [1440, 900], [1280, 800], [1100, 800], [900, 800], [390, 844]];
const THEMEN = ["hell", "dunkel"];
const KONTRAST_MIN = 3;          // darunter ist Text auch groß kaum lesbar (WCAG für große Schrift)
const FRIST_MS = 30000;
const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const argumente = process.argv.slice(2);
const basis = argumente.find((a) => !a.startsWith("--") && !argumente[argumente.indexOf(a) - 1]?.startsWith("--"));
const wert = (name) => { const i = argumente.indexOf(name); return i >= 0 ? argumente[i + 1] : undefined; };
if (!basis) { console.error("Aufruf: ansicht.mjs <basis> [--ausgabe ORDNER] [--nur SEITE] [--thema hell|dunkel]"); process.exit(2); }
const ausgabe = wert("--ausgabe") ?? path.join(os.tmpdir(), "ansicht");
const nur = wert("--nur");
const themen = wert("--thema") ? [wert("--thema")] : THEMEN;
const einstellung = JSON.parse(fs.readFileSync("frontend/ansicht.json", "utf8"));
const env = Object.fromEntries((fs.existsSync("backend/.env.test") ? fs.readFileSync("backend/.env.test", "utf8") : "")
  .split("\n").filter((z) => z.includes("=") && !z.trimStart().startsWith("#"))
  .map((z) => [z.split("=")[0].trim(), z.slice(z.indexOf("=") + 1).trim()]));

const app = await (await fetch(`${basis}/api/v1/app`)).json();
const anmeldung = await fetch(`${basis}/api/v1/anmeldung`, { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ kennung: env.KELLERWOLKE_KENNUNG, passwort: env.KELLERWOLKE_PASSWORT }) });
if (!anmeldung.ok) { console.error(`Anmeldung mit dem Testzugang scheitert (${anmeldung.status}); backend/.env.test prüfen`); process.exit(2); }
const token = (await anmeldung.json()).token;

const profil = fs.mkdtempSync(path.join(os.tmpdir(), "ansicht-"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--use-fake-ui-for-media-stream",
  "--use-fake-device-for-media-stream", "--remote-debugging-port=0", "--remote-allow-origins=*", `--user-data-dir=${profil}`,
  "about:blank"], { stdio: "ignore" });
const warte = (ms) => new Promise((r) => setTimeout(r, ms));
let port;
for (let i = 0; i < 100 && !port; i++) { await warte(100); try { port = fs.readFileSync(path.join(profil, "DevToolsActivePort"), "utf8").split("\n")[0]; } catch { /* noch nicht */ } }
const ws = new WebSocket((await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((z) => z.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let n = 0;
const offen = new Map();
const befunde = [];
let ansicht = "";               // die gerade geprüfte Ansicht, für Befunde aus Ereignissen
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && offen.has(m.id)) { offen.get(m.id)(m); offen.delete(m.id); }
  if (m.method === "Page.javascriptDialogOpening") {
    befunde.push(`${ansicht}: Browser-Dialog (${m.params.type}): ${m.params.message.slice(0, 80)}`);
    ws.send(JSON.stringify({ id: ++n, method: "Page.handleJavaScriptDialog", params: { accept: true } }));
  }
});
const rufe = (method, params = {}) => new Promise((r, f) => {
  const id = ++n;
  const frist = setTimeout(() => { offen.delete(id); f(new Error(`keine Antwort auf ${method} binnen ${FRIST_MS / 1000} s`)); }, FRIST_MS);
  offen.set(id, (m) => { clearTimeout(frist); r(m); });
  ws.send(JSON.stringify({ id, method, params }));
});
const werte = async (ausdruck) => {
  const r = await rufe("Runtime.evaluate", { expression: ausdruck, returnByValue: true, awaitPromise: true });
  if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? "Fehler im Ausdruck");
  return r.result.result?.value;
};

// Messung im Browser: seitliches Rollen, Überlauf rechts (nicht von einem rollenden oder schneidenden Rahmen gefangen),
// kleinster Kontrast von Text gegen seinen tatsächlichen Hintergrund (ohne abgeschaltete oder abgeblendete Teile).
const MESSEN = `(() => {
  const stile = new Map();
  const stil = (e) => { let s = stile.get(e); if (!s) { s = getComputedStyle(e); stile.set(e, s); } return s; };
  const blassMerk = new Map();
  const blass = (e) => { if (!e) return false; if (blassMerk.has(e)) return blassMerk.get(e);
    const b = parseFloat(stil(e).opacity) < 1 || blass(e.parentElement); blassMerk.set(e, b); return b; };
  const grundMerk = new Map();
  const weg = (e) => { const t = []; for (let x = e; x && x !== document.body && t.length < 4; x = x.parentElement)
    t.unshift(x.tagName.toLowerCase() + (x.classList.length ? "." + [...x.classList].slice(0, 2).join(".") : "")); return t.join(" > "); };
  const farbe = (s) => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const t = m[1].split(/[\\s,/]+/).filter(Boolean).map(Number); return { r: t[0], g: t[1], b: t[2], a: t.length > 3 ? t[3] : 1 }; };
  const misch = (o, u) => ({ r: o.r * o.a + u.r * (1 - o.a), g: o.g * o.a + u.g * (1 - o.a), b: o.b * o.a + u.b * (1 - o.a), a: 1 });
  const hell = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const grund = (e) => { if (!e) return { r: 255, g: 255, b: 255, a: 1 }; if (grundMerk.has(e)) return grundMerk.get(e);
    const c = farbe(stil(e).backgroundColor); const unten = c && c.a >= 1 ? null : grund(e.parentElement);
    const g = !c || c.a === 0 ? unten : c.a >= 1 ? c : misch(c, unten); grundMerk.set(e, g); return g; };
  const breite = innerWidth;
  const ueber = []; const kontrast = [];
  for (const e of document.querySelectorAll("body *")) {
    const r = e.getBoundingClientRect(); const s = stil(e);
    if (!r.width || !r.height || s.visibility === "hidden" || s.display === "none") continue;
    if (r.right > breite + 1) {
      let gefangen = false;
      for (let x = e.parentElement; x && x !== document.documentElement; x = x.parentElement) {
        const sx = stil(x); if (sx.overflowX !== "visible" && x.getBoundingClientRect().right <= breite + 1) { gefangen = true; break; } }
      if (!gefangen) ueber.push(weg(e));
    }
    const text = [...e.childNodes].some((k) => k.nodeType === 3 && k.textContent.trim());
    if (!text || e.closest("[disabled], [aria-disabled=true], [aria-hidden=true]")) continue;
    if (blass(e)) continue;
    const vorn = farbe(s.color); if (!vorn) continue;
    const hinten = grund(e); const v = misch(vorn, hinten);
    const [a, b] = [hell(v), hell(hinten)].sort((x, y) => y - x);
    const wert = (a + 0.05) / (b + 0.05);
    if (wert < ${KONTRAST_MIN}) kontrast.push(weg(e) + " (" + wert.toFixed(2) + ": " + e.textContent.trim().slice(0, 30) + ")");
  }
  return { seitlich: document.documentElement.scrollWidth > breite + 1, ueber: [...new Set(ueber)].slice(0, 5), kontrast: [...new Set(kontrast)].slice(0, 5) };
})()`;

const lage = (fest) => werte(`JSON.stringify(${JSON.stringify(fest)}.map((s) => { const e = document.querySelector(s);
  if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }))`);

const klicken = (ziel) => werte(`(() => { let e = null; try { e = document.querySelector(${JSON.stringify(ziel)}); } catch { /* Text */ }
  e ??= [...document.querySelectorAll("button, a, [role=button]")].find((k) => k.textContent.trim().includes(${JSON.stringify(ziel)}));
  if (!e) return false; e.click(); return true; })()`);

fs.mkdirSync(ausgabe, { recursive: true });
await rufe("Page.enable");
await rufe("Runtime.enable");
await rufe("Page.navigate", { url: `${basis}/` });
await warte(800);
for (const thema of themen) {
  await werte(`localStorage.setItem(${JSON.stringify(`${app.kennung}_sitzung`)}, ${JSON.stringify(token)});
    localStorage.setItem("appkern_anzeige", JSON.stringify({ schrift: "normal", thema: ${JSON.stringify(thema)} })); true`);
  for (const [b, h] of BREITEN) {
    await rufe("Emulation.setDeviceMetricsOverride", { width: b, height: h, deviceScaleFactor: b < 600 ? 2 : 1, mobile: b < 600 });
    for (const seite of einstellung.seiten) {
      if ((nur && seite.name !== nur) || (seite.nur && !seite.nur.includes(b))) continue;
      const name = `${seite.name}-${b}-${thema}`;
      ansicht = name;
      try {
      await rufe("Page.navigate", { url: basis + seite.pfad });
      await warte(seite.warten_ms ?? 1800);
      const m = await werte(MESSEN);
      if (m.seitlich) befunde.push(`${name}: rollt seitlich`);
      for (const u of m.ueber) befunde.push(`${name}: läuft rechts über: ${u}`);
      for (const k of m.kontrast) befunde.push(`${name}: Kontrast unter ${KONTRAST_MIN}: ${k}`);
      const bild = await rufe("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(ausgabe, `${name}.png`), Buffer.from(bild.result.data, "base64"));
      for (const [i, w] of (seite.wechsel ?? []).entries()) {
        const vorher = await lage(w.fest ?? []);
        if (!(await klicken(w.klick))) { befunde.push(`${name}: Wechsel ${i + 1}: "${w.klick}" nicht gefunden`); break; }
        await warte(w.warten_ms ?? 1200);
        const nachher = await lage(w.fest ?? []);
        (w.fest ?? []).forEach((s, j) => {
          if (vorher[j] && nachher[j] && JSON.stringify(vorher[j]) !== JSON.stringify(nachher[j]))
            befunde.push(`${name}: Wechsel ${i + 1} (${w.klick}) verschiebt ${s}: ${vorher[j]} -> ${nachher[j]}`);
        });
        const nach = await rufe("Page.captureScreenshot", { format: "png" });
        fs.writeFileSync(path.join(ausgabe, `${name}-wechsel${i + 1}.png`), Buffer.from(nach.result.data, "base64"));
      }
      } catch (f) {
        befunde.push(`${name}: ${f.message}`);
      }
    }
  }
}
ws.close();
chrome.kill();
for (const b of befunde) console.log(b);
console.log(befunde.length ? `${befunde.length} Befunde; Bilder in ${ausgabe}` : `Keine Befunde; Bilder in ${ausgabe}`);
process.exit(befunde.length ? 1 : 0);
