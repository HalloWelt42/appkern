// Ansichtsprüfung (Lehren 12 und 13 der Transkription): jede Seite der App in allen Breiten, hell und dunkel, in einem
// unsichtbaren Chrome. Misst seitliches Rollen, Überlauf über den rechten Rand, Kontrast von Text und die Verschiebung
// fester Teile beim Zustandswechsel; legt von jeder Ansicht ein Bild ab.
//
//   node frontend/node_modules/appkern-oberflaeche/oberflaeche/werkzeuge/ansicht.mjs <basis> [--ausgabe ORDNER]
//        [--nur SEITE] [--thema hell|dunkel] [--breiten 1920,1440,1000,390] [--seiten DATEI] [--vorlage NAME]
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
import { spawn } from "node:child_process";

const VORGABE_BREITEN = [[1920, 1080], [1440, 900], [1280, 800], [1100, 800], [900, 800], [390, 844]];
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
const vorlage = wert("--vorlage");
// eigene Breiten (etwa die eines Entwurfs); die Höhe folgt der Vorgabe: 844 am Telefon, sonst 900. Mit "BxH" (etwa
// 844x390 für ein Telefon quer) gilt die angegebene Höhe.
const BREITEN = wert("--breiten") ? wert("--breiten").split(",").map((z) => z.split("x").map(Number)).filter(([b]) => b > 0)
  .map(([b, h]) => [b, h > 0 ? h : b <= 600 ? 844 : 900])
  : VORGABE_BREITEN;
const einstellung = JSON.parse(fs.readFileSync(wert("--seiten") ?? "frontend/ansicht.json", "utf8"));
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
    for (const seite of einstellung.seiten) {
      if (seite.auslassen || (nur && seite.name !== nur) || (seite.nur && !seite.nur.includes(b))) continue;
      const name = `${seite.name}-${b}${h <= 500 ? `x${h}` : ""}-${thema}${vorlage ? `-${vorlage}` : ""}`;
      ansicht = name;
      try {
      // "speicher": feste Einträge im localStorage vor dem Laden (etwa ein gewähltes Layout), damit jede Seite gleich beginnt
      if (seite.speicher) await werte(`${Object.entries(seite.speicher).map(([k, v]) => `localStorage.setItem(${JSON.stringify(k)}, ${JSON.stringify(v)});`).join("")} true`);
      await rufe("Page.navigate", { url: basis + seite.pfad });
      await warte(seite.warten_ms ?? 1800);
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
for (const b of befunde) console.log(b);
console.log(befunde.length ? `${befunde.length} Befunde; Bilder in ${ausgabe}` : `Keine Befunde; Bilder in ${ausgabe}`);
process.exit(befunde.length ? 1 : 0);
