<script lang="ts">
  // Seite Schnittstelle (WIKI-78, Entwurf nachschlag mockups/schnittstelle.html): alle Wege der App nach Bereich, aus dem
  // OpenAPI-Schema der App selbst (/api/v1/schnittstelle, nur angemeldet). Links die Wege mit Filter, rechts ein Weg:
  // Zweck, Parameter mit Typ und Beschreibung, Eingabe und Antwort als Felder, Aufruf als curl (kopierbar) und für GET
  // Ausprobieren mit dem eigenen Zugang. Oben die Abdeckung: wie viele Wege beschrieben sind. Am Telefon erst die Liste,
  // dann der Weg. Der Weg steht in der Adresse (/schnittstelle/<kennung>). Klassen mit si-.
  import { onMount } from "svelte";
  import { hole } from "../lib/api.svelte";
  import { geraet } from "../lib/geraet.svelte";
  import { gehe, navigation } from "../lib/navigation.svelte";
  import { kopieren } from "../lib/zwischenablage";

  type Schema = { type?: string; $ref?: string; items?: Schema; anyOf?: Schema[]; enum?: unknown[]; properties?: Record<string, Schema>;
                  required?: string[]; description?: string; title?: string; default?: unknown; format?: string;
                  additionalProperties?: Schema | boolean; minimum?: number; maximum?: number };
  type Parameter = { name: string; in: string; required?: boolean; schema?: Schema; description?: string };
  type Operation = { operationId?: string; summary?: string; description?: string; tags?: string[]; parameters?: Parameter[];
                     requestBody?: { content?: Record<string, { schema?: Schema }> };
                     responses?: Record<string, { description?: string; content?: Record<string, { schema?: Schema }> }> };
  type Weg = { kennung: string; methode: string; pfad: string; op: Operation; bereich: string; beschrieben: boolean };

  const METHODEN = ["get", "post", "put", "patch", "delete"];
  let schema = $state.raw<{ paths: Record<string, Record<string, Operation>>; components?: { schemas?: Record<string, Schema> } } | null>(null);
  let fehler = $state("");
  let filter = $state("");

  onMount(async () => {
    try {
      schema = await hole("/schnittstelle");
    } catch (f) {
      fehler = (f as Error).message;
    }
  });

  const wege = $derived.by<Weg[]>(() => {
    if (!schema) return [];
    const aus: Weg[] = [];
    for (const [pfad, ops] of Object.entries(schema.paths)) {
      for (const m of METHODEN) {
        const op = ops[m];
        if (!op) continue;
        aus.push({ kennung: op.operationId ?? `${m}_${pfad}`, methode: m.toUpperCase(), pfad, op,
                   bereich: op.tags?.[0] ?? (pfad.split("/")[3] || "app"), beschrieben: !!(op.description || op.summary) });
      }
    }
    return aus.sort((a, b) => a.bereich.localeCompare(b.bereich, "de") || a.pfad.localeCompare(b.pfad) || a.methode.localeCompare(b.methode));
  });
  const f = $derived(filter.trim().toLowerCase());
  const sichtbar = $derived(f ? wege.filter((w) => `${w.methode} ${w.pfad} ${w.op.summary ?? ""} ${w.bereich}`.toLowerCase().includes(f)) : wege);
  const bereiche = $derived([...new Set(sichtbar.map((w) => w.bereich))]);
  const beschrieben = $derived(wege.filter((w) => w.beschrieben).length);
  const gewaehlt = $derived(wege.find((w) => w.kennung === navigation.teile[0]) ?? null);
  $effect(() => {
    navigation.titel = gewaehlt ? `${gewaehlt.methode} ${gewaehlt.pfad}` : "Schnittstelle";
  });

  // --- Schemata lesbar machen ---
  function aufloesen(s: Schema | undefined): Schema | undefined {
    if (s?.$ref) return schema?.components?.schemas?.[s.$ref.split("/").pop()!];
    return s;
  }
  function typ(s: Schema | undefined): string {
    if (!s) return "";
    if (s.$ref) return s.$ref.split("/").pop()!;
    if (s.anyOf) return s.anyOf.map(typ).filter((t) => t !== "null").join(" | ") + (s.anyOf.some((x) => x.type === "null") ? " | null" : "");
    if (s.enum) return s.enum.map((e) => JSON.stringify(e)).join(" | ");
    if (s.type === "array") return `${typ(s.items)}[]`;
    return s.type ?? "";
  }
  const felder = (s: Schema | undefined) => {
    const d = aufloesen(s);
    const inner = d?.type === "array" ? aufloesen(d.items) : d;
    return Object.entries(inner?.properties ?? {}).map(([name, p]) => ({ name, typ: typ(p), pflicht: inner?.required?.includes(name) ?? false,
                                                                       text: p.description ?? p.title ?? "" }));
  };
  const modellName = (s: Schema | undefined) => (s?.$ref ? s.$ref.split("/").pop() : s?.type === "array" && s.items?.$ref ? `${s.items.$ref.split("/").pop()}[]` : typ(s));
  const json = (c?: Record<string, { schema?: Schema }>) => c?.["application/json"]?.schema;
  /** Die Standardtexte des Rahmens auf Deutsch; eigene Beschreibungen bleiben, wie sie sind */
  const STANDARD: Record<string, string> = { "Successful Response": "Erfolg", "Validation Error": "Eingabe ungültig" };
  const antworttext = (t: string | undefined) => (t ? STANDARD[t] ?? t : "");

  // --- Aufruf und Ausprobieren ---
  let werte = $state<Record<string, string>>({});
  let antwort = $state("");
  let laeuft = $state(false);
  $effect(() => {
    void gewaehlt?.kennung;
    werte = {};
    antwort = "";
  });
  function adresse(w: Weg): string {
    let p = w.pfad;
    const q = new URLSearchParams();
    for (const par of w.op.parameters ?? []) {
      const v = werte[par.name] ?? "";
      if (par.in === "path") p = p.replace(`{${par.name}}`, encodeURIComponent(v || `{${par.name}}`));
      else if (par.in === "query" && v) q.append(par.name, v);
    }
    const s = q.toString();
    return p + (s ? `?${s}` : "");
  }
  const curl = (w: Weg) => `curl -s ${w.methode !== "GET" ? `-X ${w.methode} ` : ""}"${location.origin}${adresse(w)}" \\\n  -H "Authorization: Bearer $APP_SCHLUESSEL"`;
  async function probieren(w: Weg) {
    laeuft = true;
    try {
      antwort = JSON.stringify(await hole(adresse(w).replace(/^\/api\/v1/, "")), null, 2);
    } catch (e) {
      antwort = `Fehler: ${(e as Error).message}`;
    } finally {
      laeuft = false;
    }
  }
  let kopiert = $state(false);
  async function aufrufKopieren(w: Weg) {
    await kopieren(curl(w));
    kopiert = true;
    setTimeout(() => (kopiert = false), 1500);
  }
</script>

<div class="si" class:si-telefon={geraet.mobil} class:si-mit-weg={!!gewaehlt}>
  <aside class="si-liste">
    <div class="si-kopf">
      <label class="suchfeld"><i class="fa-solid fa-filter"></i><input type="search" bind:value={filter} placeholder="Weg suchen" aria-label="Weg suchen" /></label>
      {#if wege.length}<span class="si-abdeckung" class:voll={beschrieben === wege.length}>
        <i class="fa-solid {beschrieben === wege.length ? 'fa-circle-check' : 'fa-circle-exclamation'}"></i>{beschrieben} von {wege.length} Wegen beschrieben</span>{/if}
    </div>
    <div class="si-rollen">
      {#if fehler}<p class="si-leise">{fehler}</p>{/if}
      {#each bereiche as b (b)}
        <div class="si-bereich">{b}</div>
        {#each sichtbar.filter((w) => w.bereich === b) as w (w.kennung)}
          <a class="si-weg" class:hier={gewaehlt?.kennung === w.kennung} class:offen={!w.beschrieben} href="/schnittstelle/{w.kennung}"
             onclick={(e) => { e.preventDefault(); gehe(`schnittstelle/${w.kennung}`); }}>
            <span class="si-methode {w.methode.toLowerCase()}">{w.methode}</span><code>{w.pfad.replace(/^\/api\/v1/, "")}</code></a>
        {/each}
      {/each}
    </div>
  </aside>

  <section class="si-seite">
    {#if gewaehlt}
      {@const w = gewaehlt}
      <div class="si-rollen si-inhalt">
        {#if geraet.mobil}<button class="knopf still" onclick={() => gehe("schnittstelle")}><i class="fa-solid fa-arrow-left"></i>Alle Wege</button>{/if}
        <h1><span class="si-methode {w.methode.toLowerCase()}">{w.methode}</span><code>{w.pfad}</code></h1>
        {#if w.op.summary}<p class="si-zweck">{w.op.summary}</p>{/if}
        {#if w.op.description}<p class="si-text">{w.op.description}</p>{/if}
        {#if !w.beschrieben}<p class="si-leise"><i class="fa-solid fa-circle-exclamation"></i> Dieser Weg ist noch nicht beschrieben.</p>{/if}

        {#if w.op.parameters?.length}
          <h2>Parameter</h2>
          <div class="si-tabelle-rahmen"><table class="si-tabelle">
            <thead><tr><th>Name</th><th>Ort</th><th>Typ</th><th>Beschreibung</th>{#if w.methode === "GET"}<th>Ausprobieren</th>{/if}</tr></thead>
            <tbody>
              {#each w.op.parameters as p (p.in + p.name)}
                <tr><td><code>{p.name}</code>{#if p.required}<span class="si-pflicht">Pflicht</span>{/if}</td><td>{p.in === "path" ? "Pfad" : p.in === "query" ? "Abfrage" : p.in}</td>
                  <td class="si-typ">{typ(p.schema)}</td>
                  <td>{p.description ?? p.schema?.description ?? ""}{#if p.schema?.default !== undefined} <span class="si-leise">Vorgabe {JSON.stringify(p.schema.default)}</span>{/if}</td>
                  {#if w.methode === "GET"}<td><input class="si-wert" bind:value={werte[p.name]} aria-label="Wert für {p.name}" /></td>{/if}</tr>
              {/each}
            </tbody>
          </table></div>
        {/if}

        {#if json(w.op.requestBody?.content)}
          {@const s = json(w.op.requestBody?.content)}
          <h2>Eingabe <span class="si-leise">{modellName(s)}</span></h2>
          {@render feldliste(felder(s))}
        {/if}

        <h2>Antwort</h2>
        {#each Object.entries(w.op.responses ?? {}) as [code, r] (code)}
          {@const s = json(r.content)}
          <div class="si-antwort"><span class="si-code" class:gut={code.startsWith("2")}>{code}</span><span>{antworttext(r.description)}{#if s}<span class="si-leise si-modell">{modellName(s)}</span>{/if}</span></div>
          {#if s && code.startsWith("2") && felder(s).length}{@render feldliste(felder(s))}{/if}
        {/each}

        <h2>Aufruf</h2>
        <div class="si-kasten"><div class="si-kasten-kopf"><span>curl</span>
          <button class="knopf still" onclick={() => aufrufKopieren(w)}><i class="fa-{kopiert ? 'solid fa-check' : 'regular fa-copy'}"></i>Kopieren</button></div>
          <pre>{curl(w)}</pre></div>
        {#if w.methode === "GET"}
          <div class="si-zeile"><button class="knopf" disabled={laeuft} onclick={() => probieren(w)}><i class="fa-solid fa-play"></i>Ausprobieren</button>
            <span class="si-leise">mit deinem Zugang; nur Lesen</span></div>
          {#if antwort}<div class="si-kasten"><pre>{antwort}</pre></div>{/if}
        {/if}
      </div>
    {:else if !geraet.mobil}
      <div class="si-rollen si-inhalt"><h1>Schnittstelle</h1>
        <p class="si-text">Alle Wege der App unter <code>/api/v1</code>, nach Bereich. Die eigene Oberfläche nutzt nur diese Wege; andere Apps
          und eigene Werkzeuge rufen sie mit einem App-Schlüssel auf. Links einen Weg wählen.</p></div>
    {/if}
  </section>
</div>

{#snippet feldliste(liste: { name: string; typ: string; pflicht: boolean; text: string }[])}
  {#if liste.length}
    <dl class="si-felder">
      {#each liste as x (x.name)}<dt><code>{x.name}</code>{#if x.pflicht}<span class="si-pflicht">Pflicht</span>{/if}<span class="si-typ">{x.typ}</span></dt><dd>{x.text}</dd>{/each}
    </dl>
  {/if}
{/snippet}

<style>
  .si { display: grid; grid-template-columns: 320px minmax(0, 1fr); height: 100%; min-height: 0; }
  .si-liste { display: flex; flex-direction: column; min-height: 0; border-right: 1px solid var(--rand); }
  .si-kopf { display: flex; flex-direction: column; gap: var(--a2); padding: var(--a3); }
  .si-rollen { overflow-y: auto; min-height: 0; flex: 1; }
  .si-abdeckung { font-size: var(--klein); color: var(--warn); display: inline-flex; gap: 6px; align-items: center; }
  .si-abdeckung.voll { color: var(--gut); }
  .si-bereich { padding: var(--a3) var(--a3) 4px; font-size: var(--marke); text-transform: uppercase; letter-spacing: .06em; color: var(--text-3); font-weight: 600; }
  .si-weg { display: flex; gap: var(--a2); align-items: center; padding: 4px var(--a3); color: var(--text-2); text-decoration: none; font-size: var(--klein); }
  .si-weg code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .si-weg:hover { background: var(--flaeche); }
  .si-weg.hier { background: var(--flaeche); color: var(--text); box-shadow: inset 3px 0 0 var(--akzent); border-radius: 0; }
  .si-weg.offen code { color: var(--warn); }
  .si-methode { flex: none; min-width: 3.6em; text-align: center; font-size: var(--marke); font-weight: 700; padding: 1px 4px; border-radius: var(--r1);
                background: var(--flaeche-2); color: var(--text-2); }
  .si-methode.get { color: var(--gut); }
  .si-methode.post, .si-methode.put, .si-methode.patch { color: var(--akzent); }
  .si-methode.delete { color: var(--gefahr); }
  .si-seite { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
  .si-inhalt { padding: var(--a4) var(--a5) var(--a6); display: flex; flex-direction: column; gap: var(--a3); max-width: 1000px; }
  .si-inhalt h1 { margin: 0; font-size: var(--titel); display: flex; gap: var(--a2); align-items: center; overflow-wrap: anywhere; }
  .si-inhalt h2 { margin: var(--a3) 0 0; font-size: var(--gross); display: flex; gap: var(--a2); align-items: baseline; }
  .si-zweck { margin: 0; font-weight: 600; }
  .si-text { margin: 0; color: var(--text-2); white-space: pre-line; }
  .si-leise { color: var(--text-3); font-size: var(--klein); font-weight: 400; }
  .si-tabelle-rahmen { overflow-x: auto; }
  .si-tabelle { border-collapse: collapse; width: 100%; font-size: var(--klein); }
  .si-tabelle th, .si-tabelle td { text-align: left; padding: 6px var(--a2); border-bottom: 1px solid var(--rand); vertical-align: top; }
  .si-tabelle th { color: var(--text-3); font-weight: 600; }
  .si-typ { font-family: var(--schrift-code, monospace); color: var(--text-3); font-size: var(--klein); margin-left: var(--a2); }
  .si-pflicht { margin-left: 6px; font-size: var(--marke); color: var(--warn); }
  .si-wert { width: 100%; min-width: 8em; font: inherit; padding: 4px 6px; border: 1px solid var(--rand); border-radius: var(--r1); background: var(--hg); color: var(--text); }
  .si-felder { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px var(--a3); margin: 0; font-size: var(--klein); }
  .si-felder dt { display: flex; align-items: baseline; flex-wrap: wrap; }
  .si-felder dd { margin: 0; color: var(--text-2); }
  .si-antwort { display: flex; gap: var(--a2); align-items: baseline; font-size: var(--klein); }
  .si-code { font-family: var(--schrift-zahl, monospace); font-weight: 700; color: var(--warn); }
  .si-code.gut { color: var(--gut); }
  .si-modell { margin-left: var(--a2); }
  .si-kasten { background: var(--flaeche); border-radius: var(--r2); overflow: hidden; }
  .si-kasten-kopf { display: flex; justify-content: space-between; align-items: center; padding: 4px var(--a3); font-size: var(--klein); color: var(--text-3);
                    border-bottom: 1px solid var(--rand); }
  .si-kasten pre { margin: 0; padding: var(--a3); overflow-x: auto; font-size: var(--klein); max-height: 60vh; }
  .si-zeile { display: flex; flex-wrap: wrap; gap: var(--a3); align-items: center; }
  /* Telefon: erst die Liste, mit gewähltem Weg nur der Weg; Code rollt im Kasten, nie die Seite */
  .si-telefon { grid-template-columns: minmax(0, 1fr); height: auto; }
  .si-telefon .si-liste { border-right: 0; }
  .si-telefon.si-mit-weg .si-liste, .si-telefon:not(.si-mit-weg) .si-seite { display: none; }
  .si-telefon .si-inhalt { padding-inline: var(--a3); }
</style>
