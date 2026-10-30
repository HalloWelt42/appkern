// Ansichtsprüfung (Lehren 12 und 13 der Transkription): jede Seite der App in allen Breiten, hell und dunkel, in einem
// unsichtbaren Chrome. Misst seitliches Rollen, Überlauf über den rechten Rand, Kontrast von Text und die Verschiebung
// fester Teile beim Zustandswechsel; legt von jeder Ansicht ein Bild ab.
// Am Telefon (375, 390 und 430 Pixel, mit sicheren Rändern und Fingerbedienung wie am iPhone) misst sie zusätzlich den
// Rahmen nach stil/rahmen.css (HELF-13): Seite fest, App schirmhoch, Kopf ganz oben mit Inhalt erst unter dem sicheren
// Rand und in seiner Höhe, Fußleiste ganz unten, nicht verdeckt und nicht zu hoch, Eingaben ab 16 px, keine eigene Regel
// für die Web-App-Ansicht am Rahmen, viewport-fit=cover; dazu Tippen ohne Zoom (HELF-69): jedes Eingabefeld ab 16 px, das
// Zoomen mit zwei Fingern nicht gesperrt; dazu schmale Ränder (HELF-70): der Inhalt nutzt mindestens 90 Prozent der Breite.
// --rahmen prüft nur das (Telefonbreiten, hell) und hält einen
// befundfreien Lauf für den Stand von frontend/ fest; ohne diesen Nachweis rollt das Ausrollen nicht aus. Eine App ohne
// Telefonansicht trägt "rahmen": false in ihre ansicht.json ein.
//
//   node frontend/node_modules/appkern-oberflaeche/oberflaeche/werkzeuge/ansicht.mjs <basis> [--ausgabe ORDNER]
//        [--nur SEITE] [--thema hell|dunkel] [--breiten 1920,1440,1000,390] [--seiten DATEI] [--vorlage NAME] [--rahmen]
//
// im Wurzelordner der App (tools/ansicht.sh). Seiten und Zustandswechsel stehen in frontend/ansicht.json:
//   { "seiten": [ { "name": "start", "pfad": "/" },
//                 { "name": "aufnehmen", "pfad": "/aufnahmen", "nur": [1440, 390],
//                   "wechsel": [ { "klick": "Aufnehmen", "fest": [".rek-leiste"] } ] } ] }
// `klick` ist ein CSS-Selektor oder der Text eines Knopfs, `wischen` ("links" oder "rechts") ein Wischen quer über die
// Mitte; `fest` sind Teile, die sich beim Wechsel nicht bewegen dürfen. `speicher` belegt localStorage vor dem Laden.
// Detailseiten holen ihren Pfad aus einer Abfrage der App (mit der Testanmeldung); {weg.zum.wert} wird gefüllt:
//   { "name": "plan", "abfrage": "/api/v1/plaene?anzahl=1", "pfad": "/vertonen/{eintraege.0.id}" }
// Gibt die Abfrage keinen Wert her, ist das ein Befund (die Seite fehlt sonst still in der Prüfung).
// --vorlage wählt eine Vorlage des Aussehens (lib/vorlage.svelte.ts, etwa futur) wie die App es auf dem Gerät tut; sie
// wirkt nur ab 1000 Pixel, die Bilder tragen ihren Namen. Ohne Angabe gilt Klassisch.
// Entwürfe ohne Backend (Ordner mockups einer App): eigene Seitenliste mit --seiten und darin "anmeldung": false; dann
// fragt die Prüfung die App nicht ab und meldet sich nicht an, das Thema setzt sie wie sonst über appkern_anzeige.
// Angemeldet wird mit dem Testzugang aus backend/.env.test (KELLERWOLKE_KENNUNG, KELLERWOLKE_PASSWORT; gleichnamige
// Variablen der Umgebung gehen vor); die Werte werden nie ausgegeben. Ein Browser-Dialog (alert, confirm, beforeunload) ist selbst ein Befund und wird geschlossen;
// antwortet der Browser nicht binnen 30 Sekunden, ist auch das ein Befund. Ende mit 1, wenn es Befunde gibt.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync, spawn } from "node:child_process";

// Telefone wie am iPhone: Breite, Höhe und sichere Ränder oben und unten (Statusleiste mit Kamera-Insel, Home-Balken)
const TELEFONE = [[375, 812, 50, 34], [390, 844, 47, 34], [430, 932, 59, 34]];
const VORGABE_BREITEN = [[1920, 1080], [1440, 900], [1280, 800], [1100, 800], [900, 800], ...TELEFONE.map(([b, h]) => [b, h])];
// Wo ein befundfreier Rahmenlauf festgehalten wird, benannt nach dem Git-Baum von frontend/ (appkern.werkzeuge.ausrollen)
const NUTZBAR_MIN = 0.9;        // so viel der Breite nutzt der Inhalt am Telefon mindestens (HELF-70)
const STEMPEL = path.join(os.homedir(), "Library", "Caches", "Appkern", "rahmen");
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
const nurRahmen = argumente.includes("--rahmen");
const themen = wert("--thema") ? [wert("--thema")] : nurRahmen ? ["hell"] : THEMEN;
const vorlage = wert("--vorlage");
// eigene Breiten (etwa die eines Entwurfs); die Höhe folgt der Vorgabe: 844 am Telefon, sonst 900. Mit "BxH" (etwa
// 844x390 für ein Telefon quer) gilt die angegebene Höhe.
const BREITEN = wert("--breiten") ? wert("--breiten").split(",").map((z) => z.split("x").map(Number)).filter(([b]) => b > 0)
  .map(([b, h]) => [b, h > 0 ? h : TELEFONE.find(([t]) => t === b)?.[1] ?? (b <= 600 ? 844 : 900)])
  : nurRahmen ? TELEFONE.map(([b, h]) => [b, h]) : VORGABE_BREITEN;
const einstellung = JSON.parse(fs.readFileSync(wert("--seiten") ?? "frontend/ansicht.json", "utf8"));
if (nurRahmen && einstellung.rahmen === false) { console.log("Ohne Telefonansicht (ansicht.json: rahmen false); nichts zu prüfen"); process.exit(0); }
const mitAnmeldung = einstellung.anmeldung !== false;
const env = Object.fromEntries((fs.existsSync("backend/.env.test") ? fs.readFileSync("backend/.env.test", "utf8") : "")
  .split("\n").filter((z) => z.includes("=") && !z.trimStart().startsWith("#"))
  .map((z) => [z.split("=")[0].trim(), z.slice(z.indexOf("=") + 1).trim()]));
// die Umgebung geht vor (etwa der Probebetrieb einer App mit nachgestellter Kellerwolke und ihren Testpersonen)
for (const name of ["KELLERWOLKE_KENNUNG", "KELLERWOLKE_PASSWORT"]) if (process.env[name]) env[name] = process.env[name];

let app = { kennung: "entwurf" };
let token = "";
if (mitAnmeldung) {
  app = await (await fetch(`${basis}/api/v1/app`)).json();
  const anmeldung = await fetch(`${basis}/api/v1/anmeldung`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kennung: env.KELLERWOLKE_KENNUNG, passwort: env.KELLERWOLKE_PASSWORT }) });
  if (!anmeldung.ok) { console.error(`Anmeldung mit dem Testzugang scheitert (${anmeldung.status}); backend/.env.test prüfen`); process.exit(2); }
  token = (await anmeldung.json()).token;
}

const profil = fs.mkdtempSync(path.join(os.tmpdir(), "ansicht-"));
// ohne Zwischenspeicher für Zurück: sonst halten verlassene Seiten ihre Ereignisströme offen, bis keine Verbindung frei ist
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--disable-features=BackForwardCache",
  "--use-fake-ui-for-media-stream",
  "--use-fake-device-for-media-stream", "--remote-debugging-port=0", "--remote-allow-origins=*", `--user-data-dir=${profil}`,
  "about:blank"], { stdio: "ignore" });
const warte = (ms) => new Promise((r) => setTimeout(r, ms));
let port;
for (let i = 0; i < 900 && !port; i++) { await warte(100); try { port = fs.readFileSync(path.join(profil, "DevToolsActivePort"), "utf8").split("\n")[0]; } catch { /* noch nicht */ } }
const ws = new WebSocket((await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((z) => z.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let n = 0;
const offen = new Map();
const befunde = [];
let ansicht = "";               // die gerade geprüfte Ansicht, für Befunde aus Ereignissen
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && offen.has(m.id)) { offen.get(m.id)(m); offen.delete(m.id); }
  // Fehler in der Konsole und im Netz (nicht geladene Dateien) sind Befunde der gerade geprüften Ansicht
  if (m.method === "Runtime.exceptionThrown") {
    befunde.push(`${ansicht}: Fehler in der Konsole: ${(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text ?? "").split("\n")[0].slice(0, 160)}`);
  }
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
    befunde.push(`${ansicht}: console.error: ${m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 160)}`);
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    befunde.push(`${ansicht}: ${m.params.entry.source}: ${m.params.entry.text.slice(0, 120)} ${m.params.entry.url ?? ""}`.trim());
  }
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

// Messung im Browser: seitliches Rollen, Überlauf rechts (angeschnitten, also teils sichtbar, und nicht von einem
// rollenden oder schneidenden Rahmen gefangen; ganz draußen liegen eingeschobene Tafeln),
// kleinster Kontrast von Text gegen seinen tatsächlichen Hintergrund (ohne abgeschaltete oder abgeblendete Teile).
const MESSEN = `(() => {
  const stile = new Map();
  const stil = (e) => { let s = stile.get(e); if (!s) { s = getComputedStyle(e); stile.set(e, s); } return s; };
  const blassMerk = new Map();
  const blass = (e) => { if (!e) return false; if (blassMerk.has(e)) return blassMerk.get(e);
    const b = parseFloat(stil(e).opacity) < 1 || blass(e.parentElement); blassMerk.set(e, b); return b; };
  const weg = (e) => { const t = []; for (let x = e; x && x !== document.body && t.length < 4; x = x.parentElement)
    t.unshift(x.tagName.toLowerCase() + (x.classList.length ? "." + [...x.classList].slice(0, 2).join(".") : "")); return t.join(" > "); };
  const farbe = (s) => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const t = m[1].split(/[\\s,/]+/).filter(Boolean).map(Number); return { r: t[0], g: t[1], b: t[2], a: t.length > 3 ? t[3] : 1 }; };
  const misch = (o, u) => ({ r: o.r * o.a + u.r * (1 - o.a), g: o.g * o.a + u.g * (1 - o.a), b: o.b * o.a + u.b * (1 - o.a), a: 1 });
  const hell = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  // Hintergrund unter dem Text: die eigene Fläche und die der Vorfahren, deren Kasten die Mitte des Texts wirklich enthält.
  // Ein Vorfahr, unter dem der Text gar nicht liegt (etwa eine 2 Pixel breite Linie mit absolut gesetzter Beschriftung
  // daneben), malt nicht hinter ihm und zählt nicht.
  // Ein rollender Rahmen malt seinen Hintergrund unter seinen ganzen Inhalt (auch was gerade herausgerollt ist), die Wurzel
  // unter alles.
  const flaeche = (e) => { const k = e.getBoundingClientRect(); const s = stil(e);
    if (e === document.documentElement || e === document.body) return { l: -Infinity, o: -Infinity, r: Infinity, u: Infinity };
    if (s.overflowX === "visible" && s.overflowY === "visible") return { l: k.left, o: k.top, r: k.right, u: k.bottom };
    const l = k.left - e.scrollLeft, o = k.top - e.scrollTop;
    return { l, o, r: l + Math.max(k.width, e.scrollWidth), u: o + Math.max(k.height, e.scrollHeight) }; };
  const grund = (e, x, y) => { if (!e) return { r: 255, g: 255, b: 255, a: 1 };
    const k = flaeche(e); const darunter = x >= k.l && x <= k.r && y >= k.o && y <= k.u;
    const c = darunter ? farbe(stil(e).backgroundColor) : null;
    if (c && c.a >= 1) return c;
    const unten = grund(e.parentElement, x, y);
    return !c || c.a === 0 ? unten : misch(c, unten); };
  const breite = innerWidth;
  const ueber = []; const kontrast = [];
  for (const e of document.querySelectorAll("body *")) {
    const r = e.getBoundingClientRect(); const s = stil(e);
    if (!r.width || !r.height || s.visibility === "hidden" || s.display === "none") continue;
    if (r.right > breite + 1 && r.left < breite - 1) {
      let gefangen = false;
      for (let x = e.parentElement; x && x !== document.documentElement; x = x.parentElement) {
        const sx = stil(x); if (sx.overflowX !== "visible" && x.getBoundingClientRect().right <= breite + 1) { gefangen = true; break; } }
      if (!gefangen) ueber.push(weg(e));
    }
    const text = [...e.childNodes].some((k) => k.nodeType === 3 && k.textContent.trim());
    if (!text || e.closest("[disabled], [aria-disabled=true], [aria-hidden=true]")) continue;
    if (blass(e)) continue;
    const vorn = farbe(s.color); if (!vorn) continue;
    const hinten = grund(e, r.left + r.width / 2, r.top + r.height / 2); const v = misch(vorn, hinten);
    const [a, b] = [hell(v), hell(hinten)].sort((x, y) => y - x);
    const wert = (a + 0.05) / (b + 0.05);
    if (wert < ${KONTRAST_MIN}) kontrast.push(weg(e) + " (" + wert.toFixed(2) + ": " + e.textContent.trim().slice(0, 30) + ")");
  }
  // Inhalt breiter als sein schneidender Rahmen (etwa eine Tabelle, deren rechte Spalten im Rollfeld verschwinden); Kürzen mit
  // Auslassungspunkten ist gewollt und zählt nicht
  const geschnitten = [];
  for (const e of document.querySelectorAll("body *")) {
    const s = stil(e);
    // Eingabefelder rollen ihren Text selbst; das ist kein Überlauf der Seite
    if (s.display === "none" || s.overflowX === "visible" || s.textOverflow === "ellipsis" || ["INPUT", "TEXTAREA", "SELECT"].includes(e.tagName)) continue;
    if (e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0) {
      // was am weitesten hinausragt (ohne den Rahmen selbst), damit der Befund die Ursache nennt
      const rand = e.getBoundingClientRect().left + e.clientWidth;
      let weitest = null, mass = 0;
      for (const k of e.querySelectorAll("*")) { const r = k.getBoundingClientRect(); if (r.width && r.right - rand > mass) { mass = r.right - rand; weitest = k; } }
      geschnitten.push(weg(e) + " (" + e.scrollWidth + " statt " + e.clientWidth + (weitest ? "; am weitesten: " + weg(weitest) + " '" + (weitest.textContent || "").trim().slice(0, 30) + "'" : "") + ")");
    }
  }
  return { seitlich: document.documentElement.scrollWidth > breite + 1, ueber: [...new Set(ueber)].slice(0, 5), kontrast: [...new Set(kontrast)].slice(0, 5),
           geschnitten: [...new Set(geschnitten)].slice(0, 5) };
})()`;

// Rahmen am Telefon (stil/rahmen.css): die Sollwerte (Kopf- und Fußhöhe) liest die Messung aus der Seite selbst, die
// sicheren Ränder aus env() wie das Gerät sie meldet.
const RAHMEN = `(() => {
  const b = [];
  const px = (v) => parseFloat(v) || 0;
  const weg = (e) => { const t = []; for (let x = e; x && x !== document.body && t.length < 3; x = x.parentElement)
    t.unshift(x.tagName.toLowerCase() + (x.classList.length ? "." + [...x.classList].slice(0, 2).join(".") : "")); return t.join(" > "); };
  const probe = document.createElement("div");
  probe.style.cssText = "position:fixed;visibility:hidden;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)";
  document.body.append(probe);
  const oben = px(getComputedStyle(probe).paddingTop);
  probe.remove();
  const meta = (n) => document.querySelector('meta[name="' + n + '"]')?.getAttribute("content") ?? null;
  if (!/viewport-fit\\s*=\\s*cover/.test(meta("viewport") ?? "")) b.push("index.html: viewport ohne viewport-fit=cover");
  if (meta("apple-mobile-web-app-status-bar-style") === "black-translucent") b.push("index.html: Statusleiste black-translucent");
  if (meta("apple-mobile-web-app-capable") !== "yes") b.push("index.html: apple-mobile-web-app-capable fehlt");
  const wurzeln = [...document.querySelectorAll('[data-rahmen="app"]')].filter((e) => e.getClientRects().length);
  if (wurzeln.length !== 1) { b.push(wurzeln.length ? "mehr als ein Rahmen (data-rahmen=app)" : "keine Telefonansicht mit data-rahmen=app"); return b; }
  const app = wurzeln[0];
  const H = innerHeight;
  const soll = (n) => px(getComputedStyle(document.documentElement).getPropertyValue(n));
  if (!soll("--rahmen-kopf")) { b.push("stil/rahmen.css nicht geladen (keine Marke --rahmen-kopf)"); return b; }
  for (const e of [document.documentElement, document.body]) {
    const s = getComputedStyle(e);
    if (s.overflowY !== "hidden") b.push(e.tagName.toLowerCase() + " kann rollen (overflow " + s.overflowY + "); die Seite muss fest stehen");
  }
  if (document.scrollingElement.scrollHeight > H + 1) b.push("Seite höher als der Schirm (" + document.scrollingElement.scrollHeight + " statt " + H + " px)");
  const a = app.getBoundingClientRect();
  if (Math.abs(a.top) > 1 || Math.abs(a.bottom - H) > 1) b.push("App nicht schirmhoch (" + Math.round(a.top) + " bis " + Math.round(a.bottom) + " statt 0 bis " + H + " px)");
  const kopf = app.querySelector('[data-rahmen="kopf"]');
  if (!kopf) b.push("kein Kopf mit data-rahmen=kopf");
  else {
    const k = kopf.getBoundingClientRect();
    const hoehe = soll("--rahmen-kopf") + oben;
    if (Math.abs(k.top) > 1) b.push("Kopf beginnt " + Math.round(k.top) + " px unter dem oberen Rand (seine Fläche gehört unter die Statusleiste)");
    if (Math.abs(px(getComputedStyle(kopf).paddingTop) - oben) > 1) b.push("Kopf: Abstand oben " + getComputedStyle(kopf).paddingTop + " statt des sicheren Rands " + oben + " px");
    if (k.height > hoehe + 1) b.push("Kopf zu hoch (" + Math.round(k.height) + " statt " + hoehe + " px)");
    if (k.height < hoehe - 1) b.push("Kopf zu niedrig (" + Math.round(k.height) + " statt " + hoehe + " px)");
    for (const e of kopf.querySelectorAll("*")) {
      const r = e.getBoundingClientRect();
      if (!r.width || !r.height || getComputedStyle(e).visibility === "hidden") continue;
      if (r.top < oben - 1) { b.push("Kopf unter der Statusleiste: " + weg(e) + " beginnt bei " + Math.round(r.top) + " px, sicherer Rand " + oben + " px"); break; }
      if (r.bottom > k.bottom + 1) { b.push("Kopf: " + weg(e) + " ragt " + Math.round(r.bottom - k.bottom) + " px unter den Kopf"); break; }
    }
    const t = document.elementFromPoint(k.left + k.width / 2, oben + (k.bottom - oben) / 2);
    if (t && !kopf.contains(t)) b.push("Kopf verdeckt von " + weg(t));
  }
  const fuss = app.querySelector('[data-rahmen="fuss"]');
  if (fuss && fuss.getClientRects().length) {
    const f = fuss.getBoundingClientRect();
    if (f.bottom > H + 1) b.push("Fußleiste verdeckt: ragt " + Math.round(f.bottom - H) + " px unter den Schirm");
    if (f.bottom < H - 1) b.push("Fußleiste zu hoch: " + Math.round(H - f.bottom) + " px Luft darunter");
    if (px(getComputedStyle(fuss).paddingBottom) > 0) b.push("Fußleiste: Abstand unten " + getComputedStyle(fuss).paddingBottom + " (unten gehört nichts hin)");
    if (f.height > soll("--rahmen-fuss") + 1) b.push("Fußleiste zu hoch (" + Math.round(f.height) + " statt " + soll("--rahmen-fuss") + " px)");
    for (const e of fuss.children) {
      const r = e.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (t && !fuss.contains(t)) { b.push("Fußleiste verdeckt von " + weg(t)); break; }
    }
  }
  // Nutzbare Breite (HELF-70): der breiteste sichtbare Teil des Inhalts (Fläche mit Grund, Rand oder Schatten, Text,
  // Eingabe) gegen die Schirmbreite; Seitenrand plus Kartenrand plus Innenrand darf nicht zu viel verschenken
  const inhalt = app.querySelector('[data-rahmen="inhalt"]');
  if (!inhalt) b.push("kein Inhalt mit data-rahmen=inhalt");
  else {
    const W = innerWidth;
    let breitest = 0, welches = null;
    for (const e of inhalt.querySelectorAll("*")) {
      const s = getComputedStyle(e);
      const r = e.getBoundingClientRect();
      if (!r.width || !r.height || s.visibility === "hidden" || r.bottom < 0 || r.top > H) continue;
      const flaeche = (s.backgroundColor !== "rgba(0, 0, 0, 0)" && s.backgroundColor !== "transparent") || s.boxShadow !== "none"
        || px(s.borderLeftWidth) > 0 || px(s.borderRightWidth) > 0;
      const text = [...e.childNodes].some((k) => k.nodeType === 3 && k.textContent.trim());
      const feld = ["INPUT", "TEXTAREA", "SELECT", "IMG", "CANVAS", "VIDEO"].includes(e.tagName);
      if (!flaeche && !text && !feld) continue;
      // eine Fläche zählt mit ihrem Kasten; Text und Felder mit dem Platz, den ihr Behälter ihnen gibt (ein kurzer,
      // mittig gesetzter Hinweis verschenkt keine Breite)
      let links = r.left, rechts = r.right;
      if (!flaeche && e.parentElement && e.parentElement !== inhalt.parentElement) {
        const v = e.parentElement, vs = getComputedStyle(v), vr = v.getBoundingClientRect();
        links = vr.left + px(vs.borderLeftWidth) + px(vs.paddingLeft);
        rechts = vr.right - px(vs.borderRightWidth) - px(vs.paddingRight);
      }
      const w = Math.min(rechts, W) - Math.max(links, 0);
      if (w > breitest) { breitest = w; welches = e; }
    }
    if (welches && breitest / W < ${NUTZBAR_MIN}) b.push("Inhalt nutzt nur " + Math.round(breitest / W * 100) + " Prozent der Breite (" + Math.round(breitest)
      + " von " + W + " px, breitester Teil " + weg(welches) + "); Seitenrand nur einmal (--rahmen-rand), Karten ohne Außenrand");
  }
  const teile = [...document.querySelectorAll("[data-rahmen]")];
  const passt = (sel) => teile.some((t) => { try { return t.matches(sel); } catch { return false; } });
  const durch = (regeln) => { for (const r of regeln) {
    const bedingung = r.conditionText ?? r.media?.mediaText ?? "";
    if (r.cssRules && /display-mode/.test(bedingung)) {
      for (const i of r.cssRules) if (i.selectorText && passt(i.selectorText)) b.push("eigene Regel für die Web-App-Ansicht am Rahmen: @media " + bedingung + " { " + i.selectorText + " }");
    } else if (r.cssRules) durch(r.cssRules);
  } };
  for (const s of document.styleSheets) { try { durch(s.cssRules); } catch { /* fremde Datei */ } }
  return [...new Set(b)];
})()`;

// Tippen am Telefon ohne Zoom (HELF-69): jedes Eingabefeld (auch Auswahl, Textfläche, bearbeitbare Flächen wie der
// Code-Editor) mindestens 16 px, sonst vergrößert iOS beim Tippen die Seite; Zoomen mit zwei Fingern bleibt erlaubt.
const TIPPEN = `(() => {
  const b = [];
  const weg = (e) => { const t = []; for (let x = e; x && x !== document.body && t.length < 3; x = x.parentElement)
    t.unshift(x.tagName.toLowerCase() + (x.classList.length ? "." + [...x.classList].slice(0, 2).join(".") : "")); return t.join(" > "); };
  const viewport = document.querySelector('meta[name="viewport"]')?.getAttribute("content") ?? "";
  if (/maximum-scale|user-scalable\\s*=\\s*(no|0)/.test(viewport)) b.push("index.html: viewport sperrt das Zoomen (" + viewport + ")");
  const ohne = ["checkbox", "radio", "range", "hidden", "file", "color", "button", "submit", "reset", "image"];
  const felder = [...document.querySelectorAll("input, textarea, select, [contenteditable]:not([contenteditable=false])")]
    .filter((e) => !ohne.includes(e.type));
  const klein = felder.map((e) => [e, parseFloat(getComputedStyle(e).fontSize)]).filter(([, g]) => g < 16);
  for (const [e, g] of klein.slice(0, 3)) b.push("Eingabe " + weg(e) + " mit " + g + " px (unter 16 vergrößert iOS beim Tippen die Seite)");
  if (klein.length > 3) b.push("... und " + (klein.length - 3) + " weitere Eingaben unter 16 px");
  return b;
})()`;

// Telefon wie am iPhone: sichere Ränder und Fingerbedienung; am Rechner beides aus
const geraetSetzen = async (b, h) => {
  const telefon = TELEFONE.find(([tb, th]) => tb === b && th === h);
  await rufe("Emulation.setSafeAreaInsetsOverride", { insets: { top: telefon?.[2] ?? 0, bottom: telefon?.[3] ?? 0, left: 0, right: 0 } });
  await rufe("Emulation.setTouchEmulationEnabled", { enabled: !!telefon, maxTouchPoints: telefon ? 5 : 1 });
  return !!telefon;
};

// Den befundfreien Rahmenlauf für den Stand von frontend/ festhalten (nur ohne ungesicherte Änderungen dort)
const stempeln = () => {
  try {
    if (execFileSync("git", ["status", "--porcelain", "--", "frontend"], { encoding: "utf8" }).trim()) {
      console.log("Rahmen nicht festgehalten: frontend/ hat ungesicherte Änderungen (erst committen, dann prüfen)");
      return;
    }
    const baum = execFileSync("git", ["rev-parse", "HEAD:frontend"], { encoding: "utf8" }).trim();
    fs.mkdirSync(STEMPEL, { recursive: true });
    fs.writeFileSync(path.join(STEMPEL, `${baum}.json`), JSON.stringify({ app: app.kennung, basis, zeit: new Date().toISOString(),
      telefone: TELEFONE, befunde: 0 }, null, 2));
    console.log(`Rahmen für frontend ${baum.slice(0, 7)} festgehalten`);
  } catch (f) {
    console.log(`Rahmen nicht festgehalten: ${f.message.split("\n")[0]}`);
  }
};

const lage = (fest) => werte(`JSON.stringify(${JSON.stringify(fest)}.map((s) => { const e = document.querySelector(s);
  if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }))`);

const klicken = (ziel) => werte(`(() => { let e = null; try { e = document.querySelector(${JSON.stringify(ziel)}); } catch { /* Text */ }
  e ??= [...document.querySelectorAll("button, a, [role=button]")].find((k) => k.textContent.trim().includes(${JSON.stringify(ziel)}));
  if (!e) return false; e.click(); return true; })()`);

// Wischen quer über die Mitte ("links" oder "rechts"), als Maus mit gedrückter Taste: kommt als Pointer-Ereignisse an
const wischen = async (richtung, breite, hoehe) => {
  const [von, nach] = richtung === "links" ? [0.7, 0.3] : [0.3, 0.7];
  const y = Math.round(hoehe / 2);
  const maus = (type, x) => rufe("Input.dispatchMouseEvent", { type, x: Math.round(x * breite), y, button: "left", buttons: 1, clickCount: 1 });
  await maus("mousePressed", von);
  for (let s = 1; s <= 5; s++) await maus("mouseMoved", von + (nach - von) * (s / 5));
  await maus("mouseReleased", nach);
};

fs.mkdirSync(ausgabe, { recursive: true });
await rufe("Page.enable");
await rufe("Runtime.enable");
await rufe("Page.navigate", { url: `${basis}/` });
await warte(800);
for (const seite of einstellung.seiten.filter((s) => s.abfrage)) {
  try {
    const antwort = await fetch(basis + seite.abfrage, { headers: { "X-Kellerwolke-Sitzung": token } });
    if (!antwort.ok) throw new Error(`Antwort ${antwort.status}`);
    const daten = await antwort.json();
    seite.pfad = seite.pfad.replace(/\{([^}]+)\}/g, (_, weg) => {
      const w = weg.split(".").reduce((o, k) => o?.[k], daten);
      if (w == null) throw new Error(`kein Wert für {${weg}}`);
      return encodeURIComponent(String(w));
    });
  } catch (f) {
    befunde.push(`${seite.name}: Pfad aus ${seite.abfrage} nicht ermittelbar (${f.message})`);
    seite.auslassen = true;
  }
}
await rufe("Runtime.enable");
await rufe("Log.enable");
// Apps mit eigenem Schlüssel für das Thema (statt appkern_anzeige): "thema": {"schluessel": "...", "hell": "...", "dunkel": "..."}
const eigenesThema = einstellung.thema;
for (const thema of themen) {
  if (eigenesThema?.schluessel) {
    await werte(`localStorage.setItem(${JSON.stringify(eigenesThema.schluessel)}, ${JSON.stringify(eigenesThema[thema] ?? thema)}); true`);
  }
  await werte(`${token ? `localStorage.setItem(${JSON.stringify(`${app.kennung}_sitzung`)}, ${JSON.stringify(token)});` : ""}
    localStorage.setItem("appkern_anzeige", JSON.stringify({ schrift: "normal", thema: ${JSON.stringify(thema)} }));
    ${vorlage ? `localStorage.setItem("appkern_vorlage", ${JSON.stringify(vorlage)});` : `localStorage.removeItem("appkern_vorlage");`} true`);
  for (const [b, h] of BREITEN) {
    const telefon = b < 600 || h <= 500;   // auch ein Telefon quer
    await rufe("Emulation.setDeviceMetricsOverride", { width: b, height: h, deviceScaleFactor: telefon ? 2 : 1, mobile: telefon });
    const iphone = await geraetSetzen(b, h);
    for (const seite of einstellung.seiten) {
      if (seite.auslassen || (nur && seite.name !== nur) || (seite.nur && !seite.nur.includes(b))) continue;
      const name = `${seite.name}-${b}${h <= 500 ? `x${h}` : ""}-${thema}${vorlage ? `-${vorlage}` : ""}`;
      ansicht = name;
      try {
      // "speicher": feste Einträge im localStorage vor dem Laden (etwa ein gewähltes Layout), damit jede Seite gleich beginnt
      if (seite.speicher) await werte(`${Object.entries(seite.speicher).map(([k, v]) => `localStorage.setItem(${JSON.stringify(k)}, ${JSON.stringify(v)});`).join("")} true`);
      await rufe("Page.navigate", { url: basis + seite.pfad });
      await warte(seite.warten_ms ?? 1800);
      if (iphone && einstellung.rahmen !== false) for (const r of await werte(RAHMEN)) befunde.push(`${name}: Rahmen: ${r}`);
      if (iphone) for (const r of await werte(TIPPEN)) befunde.push(`${name}: Tippen: ${r}`);
      const m = await werte(MESSEN);
      if (m.seitlich) befunde.push(`${name}: rollt seitlich`);
      for (const u of m.ueber) befunde.push(`${name}: läuft rechts über: ${u}`);
      for (const k of m.kontrast) befunde.push(`${name}: Kontrast unter ${KONTRAST_MIN}: ${k}`);
      for (const g of m.geschnitten) befunde.push(`${name}: breiter als sein Rahmen: ${g}`);
      const bild = await rufe("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(ausgabe, `${name}.png`), Buffer.from(bild.result.data, "base64"));
      for (const [i, w] of (seite.wechsel ?? []).entries()) {
        const vorher = await lage(w.fest ?? []);
        if (w.wischen) await wischen(w.wischen, b, h);
        else if (!(await klicken(w.klick))) { befunde.push(`${name}: Wechsel ${i + 1}: "${w.klick}" nicht gefunden`); break; }
        await warte(w.warten_ms ?? 1200);
        const nachher = await lage(w.fest ?? []);
        (w.fest ?? []).forEach((s, j) => {
          if (vorher[j] && nachher[j] && JSON.stringify(vorher[j]) !== JSON.stringify(nachher[j]))
            befunde.push(`${name}: Wechsel ${i + 1} (${w.klick}) verschiebt ${s}: ${vorher[j]} -> ${nachher[j]}`);
        });
        const mw = await werte(MESSEN);
        if (mw.seitlich) befunde.push(`${name}-wechsel${i + 1}: rollt seitlich`);
        for (const u of mw.ueber) befunde.push(`${name}-wechsel${i + 1}: läuft rechts über: ${u}`);
        for (const k of mw.kontrast) befunde.push(`${name}-wechsel${i + 1}: Kontrast unter ${KONTRAST_MIN}: ${k}`);
        for (const g of mw.geschnitten) befunde.push(`${name}-wechsel${i + 1}: breiter als sein Rahmen: ${g}`);
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
if (nurRahmen && !befunde.length && !nur) stempeln();
for (const b of befunde) console.log(b);
console.log(befunde.length ? `${befunde.length} Befunde; Bilder in ${ausgabe}` : `Keine Befunde; Bilder in ${ausgabe}`);
process.exit(befunde.length ? 1 : 0);
