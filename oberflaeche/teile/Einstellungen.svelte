<script lang="ts">
  // Einstellungen, erzeugt aus der Beschreibung der App: je Gruppe ein Reiter mit eigener Adresse
  // (/einstellungen/<gruppe>), Herkunft je Wert, Geheimnisse verdeckt (das Auge deckt auf, kopieren geht immer),
  // Speichern in einer Leiste über alle Reiter; dazu die Anzeige auf diesem Gerät. Volle Breite; schmal stehen
  // Beschreibung und Eingabe untereinander. Auswahlen mit vielen oder langen Optionen klappen auf. Eigene Reiter der App
  // (`reiter`) stehen zwischen den erzeugten Gruppen und der Anzeige und bringen ihre Seite selbst mit. Antwortet die
  // App nicht, sagt das allein die Schale; sobald sie wieder antwortet, lädt die Seite die Einstellungen neu.
  import { onDestroy } from "svelte";
  import { anzeige, anzeigeSetzen, SCHRIFTEN as SCHRIFT, THEMEN as THEMA } from "../lib/anzeige.svelte";
  import { hole, json, seitenFehler, seitenSignal } from "../lib/api.svelte";
  import { beiRueckkehr } from "../lib/erreichbar.svelte";
  import { gehe, navigation } from "../lib/navigation.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import type { Angebot, EinstellungsReiter, Feld } from "../lib/typen";
  import { kopieren, markieren } from "../lib/zwischenablage";
  import Auswahl from "./Auswahl.svelte";

  let { reiter = [] }: { reiter?: EinstellungsReiter[] } = $props();
  let felder = $state<Feld[]>([]);
  let aenderungen = $state<Record<string, unknown>>({});
  let aufgedeckt = $state<Record<string, string>>({});
  let neuerEintrag = $state<Record<string, string>>({});
  let fehler = $state("");
  let ladeFehler = $state("");
  let laeuft = $state(false);
  let wertFelder: Record<string, HTMLElement> = $state({});
  const signal = seitenSignal();

  async function laden() {
    try {
      felder = await hole<Feld[]>("/einstellungen", { signal });
      ladeFehler = "";
    } catch (f) {
      ladeFehler = seitenFehler(f);
    }
  }
  laden();
  onDestroy(beiRueckkehr(() => void laden()));

  const ANZEIGE = "Anzeige auf diesem Gerät";
  const gruppen = $derived([...new Set(felder.map((f) => f.gruppe ?? sitzung.app!.name)), ...reiter.map((r) => r.titel), ANZEIGE]);
  const eigenerReiter = (g: string) => reiter.find((r) => r.titel === g);
  // Adresse eines Reiters: technischer Bezeichner aus dem Namen der Gruppe (eigene Reiter nennen ihren selbst)
  const schluessel = (g: string) => (g === ANZEIGE ? "anzeige" : eigenerReiter(g)?.schluessel ?? g.toLowerCase().replace(/ä/g, "ae")
    .replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
  const aktiv = $derived(gruppen.find((g) => schluessel(g) === navigation.teile[0]) ?? gruppen[0]);
  const aktivEigen = $derived(eigenerReiter(aktiv));
  const geaendertIn = (g: string) => felder.some((f) => (f.gruppe ?? sitzung.app!.name) === g && f.name in aenderungen);
  // Angebote: Auswahl aus dem System (Dienste der Leitstelle, bekannte Adressen) und was gerade gilt; geholt, sobald
  // ein Reiter sie zeigt. "Eigener Wert" öffnet das Textfeld.
  const EIGEN = "\u0000eigen";
  let angebote = $state<Record<string, Angebot>>({});
  let eigen = $state<Record<string, boolean>>({});

  async function angeboteLaden(g: string) {
    for (const f of felder.filter((x) => x.angebot && (x.gruppe ?? sitzung.app!.name) === g)) {
      try {
        angebote[f.name] = await hole<Angebot>(`/einstellungen/angebot/${f.name}`, { signal });
      } catch {
        angebote[f.name] = { optionen: [], eigener_wert: true, stand: "" };
      }
    }
  }

  $effect(() => {
    if (aktiv && felder.length) void angeboteLaden(aktiv);
  });

  function angebotOptionen(f: Feld) {
    const a = angebote[f.name];
    const jetzt = String(wert(f) ?? "");
    const optionen = (a?.optionen ?? []).map((o) => ({ wert: o.wert, titel: o.titel, hinweis: o.hinweis }));
    if (jetzt && !optionen.some((o) => o.wert === jetzt)) optionen.unshift({ wert: jetzt, titel: jetzt, hinweis: "eingetragen" });
    if (!a || a.eigener_wert) optionen.push({ wert: EIGEN, titel: "Eigener Wert ...", hinweis: "" });
    return optionen;
  }

  // Liste mit Angebot: Mehrfachwahl aus dem, was das System anbietet; Eingetragenes, das nicht mehr angeboten wird, bleibt sichtbar
  function listenOptionen(f: Feld) {
    const gewaehlt = (wert(f) as string[] | null) ?? [];
    const optionen = (angebote[f.name]?.optionen ?? []).map((o) => ({ wert: o.wert, titel: o.titel, hinweis: o.hinweis }));
    for (const w of gewaehlt) if (!optionen.some((o) => o.wert === w)) optionen.push({ wert: w, titel: w, hinweis: "nicht mehr angeboten" });
    return optionen;
  }

  function umschalten(f: Feld, w: string) {
    const gewaehlt = (wert(f) as string[] | null) ?? [];
    setzen(f, gewaehlt.includes(w) ? gewaehlt.filter((x) => x !== w) : [...gewaehlt, w]);
  }

  function angebotWaehlen(f: Feld, w: string) {
    if (w === EIGEN) {
      eigen[f.name] = true;
      return;
    }
    eigen[f.name] = false;
    setzen(f, w);
  }

  // Als Umschalter nur, wenn es wenige und kurze Optionen sind; sonst als Aufklappliste.
  const alsUmschalter = (f: Feld) => f.optionen.length <= 4 && f.optionen.reduce((n, o) => n + (f.beschriftungen?.[o] ?? o).length, 0) <= 36;
  const geaendert = $derived(Object.keys(aenderungen));
  const titel = (name: string) => felder.find((f) => f.name === name)?.titel ?? name;
  const wert = (f: Feld) => (f.name in aenderungen ? aenderungen[f.name] : f.wert);

  function setzen(f: Feld, v: unknown) {
    if (JSON.stringify(v) === JSON.stringify(f.wert) && f.art !== "geheimnis") delete aenderungen[f.name];
    else aenderungen[f.name] = v;
  }

  // Zahlen: auf die Schrittweite gerundet, in den Grenzen, mit Komma angezeigt.
  function stellen(f: Feld): number {
    const teil = String(f.schritt ?? 1).split(".")[1];
    return teil ? teil.length : 0;
  }

  function zahlSetzen(f: Feld, v: number) {
    if (Number.isNaN(v)) return;
    let n = Number(v.toFixed(stellen(f)));
    if (f.kleinste !== null) n = Math.max(f.kleinste, n);
    if (f.groesste !== null) n = Math.min(f.groesste, n);
    setzen(f, n);
  }

  function zahlZeigen(f: Feld): string {
    const v = wert(f);
    return typeof v === "number" ? v.toFixed(stellen(f)).replace(".", ",") : String(v ?? "");
  }

  async function aufdecken(f: Feld): Promise<string> {
    if (!(f.name in aufgedeckt)) aufgedeckt[f.name] = (await hole<{ wert: string }>(`/einstellungen/geheimnis/${f.name}`)).wert;
    return aufgedeckt[f.name];
  }

  // Kopieren muss im Klick geschehen; ist das Geheimnis noch verdeckt, wird es erst geholt. Geht das Kopieren danach
  // nicht mehr (manche Browser), bleibt es aufgedeckt und markiert.
  async function geheimnisKopieren(f: Feld, wertFeld: HTMLElement | undefined) {
    fehler = "";
    const text = f.name in aenderungen ? String(aenderungen[f.name]) : await aufdecken(f);
    if (!(await kopieren(text))) {
      markieren(wertFeld);
      fehler = "Der Browser lässt hier nicht kopieren. Der Wert ist aufgedeckt und markiert: mit Befehlstaste+C oder Strg+C kopieren.";
    }
  }

  async function speichern() {
    fehler = "";
    laeuft = true;
    try {
      felder = await hole<Feld[]>("/einstellungen", { method: "PATCH", ...json({ werte: aenderungen }) });
      aenderungen = {};
      aufgedeckt = {};
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      laeuft = false;
    }
  }

  function verwerfen() {
    aenderungen = {};
    fehler = "";
  }

  function hinzufuegen(f: Feld) {
    const neu = (neuerEintrag[f.name] ?? "").trim();
    const liste = (wert(f) as string[]) ?? [];
    if (neu && !liste.includes(neu)) setzen(f, [...liste, neu]);
    neuerEintrag[f.name] = "";
  }

  const HERKUNFT = { gespeichert: "gespeichert", umgebung: "aus der Umgebung", vorgabe: "Vorgabe" } as const;
</script>

<section class="seite einstellungen">
  <div class="seiten-kopf"><h1>Einstellungen</h1></div>
  <nav class="reiterleiste" aria-label="Gruppen der Einstellungen">
    {#each gruppen as g (g)}
      <button class:aktiv={g === aktiv} aria-current={g === aktiv ? "page" : undefined}
              onclick={() => gehe(`einstellungen/${schluessel(g)}`, true)}>
        {g === ANZEIGE ? "Anzeige" : g}{#if geaendertIn(g)}<span class="reiter-punkt" title="ungespeicherte Änderung"></span>{/if}
      </button>
    {/each}
  </nav>
  <div class="rollfeld">
    {#if ladeFehler}<div class="fehlertext">{ladeFehler}</div>{/if}
    {#if aktivEigen}
      <aktivEigen.seite />
    {:else if aktiv && aktiv !== ANZEIGE}
      <div class="karte breit">
        {#each felder.filter((f) => (f.gruppe ?? sitzung.app!.name) === aktiv) as f (f.name)}
          <div class="feld">
            <div class="was">
              <div class="name">
                {f.titel}
                <span class="herkunft {f.herkunft}" title={f.herkunft === "umgebung" ? "Beim Start aus der Umgebung; hier ändern überschreibt sie" : ""}>{HERKUNFT[f.herkunft]}</span>
                {#if f.herkunft === "gespeichert" && !(f.name in aenderungen)}
                  <button class="zuruecksetzen" onclick={() => (aenderungen[f.name] = null)}>zurücksetzen</button>
                {/if}
                {#if aenderungen[f.name] === null}<span class="zuruecksetzen">wird zurückgesetzt</span>{/if}
              </div>
              {#if f.beschreibung}<div class="beschreibung">{f.beschreibung}</div>{/if}
            </div>
            {#if f.art === "schalter"}
              <button class="schalter" class:an={Boolean(wert(f))} aria-label={f.titel} aria-pressed={Boolean(wert(f))}
                      onclick={() => setzen(f, !wert(f))}></button>
            {:else if f.angebot && f.art === "liste"}
              <div class="angebot">
                <span class="chips">
                  {#each listenOptionen(f) as o (o.wert)}
                    <button class="chip wahl" class:an={((wert(f) as string[] | null) ?? []).includes(o.wert)} title={o.hinweis}
                            aria-pressed={((wert(f) as string[] | null) ?? []).includes(o.wert)} onclick={() => umschalten(f, o.wert)}>
                      <i class="fa-solid {((wert(f) as string[] | null) ?? []).includes(o.wert) ? 'fa-square-check' : 'fa-square'}"></i>{o.titel}</button>
                  {/each}
                </span>
                {#if angebote[f.name]?.stand}
                  <div class="stand" class:gut={angebote[f.name].stand.startsWith("gefunden")}>
                    <i class="fa-solid {angebote[f.name].stand.startsWith('gefunden') ? 'fa-circle-check' : 'fa-circle-info'}"></i>
                    <span>{angebote[f.name].stand}</span></div>
                {/if}
              </div>
            {:else if f.angebot}
              <div class="angebot">
                <Auswahl wert={eigen[f.name] ? EIGEN : String(wert(f) ?? "")} optionen={angebotOptionen(f)} onwahl={(w) => angebotWaehlen(f, w)} />
                {#if eigen[f.name]}
                  <span class="eingabe" class:geaendert={f.name in aenderungen}>
                    <input value={String(wert(f) ?? "")} spellcheck="false" placeholder="eigener Wert" oninput={(e) => setzen(f, e.currentTarget.value)} />
                  </span>
                {/if}
                {#if angebote[f.name]?.stand}
                  <div class="stand" class:gut={angebote[f.name].stand.startsWith("verbunden") || angebote[f.name].stand.startsWith("gefunden")}>
                    <i class="fa-solid {angebote[f.name].stand.startsWith('verbunden') || angebote[f.name].stand.startsWith('gefunden') ? 'fa-circle-check' : 'fa-circle-info'}"></i>
                    <span>{angebote[f.name].stand}</span></div>
                {/if}
              </div>
            {:else if f.art === "auswahl" && alsUmschalter(f)}
              <span class="segment">
                {#each f.optionen as o (o)}<button class:aktiv={wert(f) === o} onclick={() => setzen(f, o)}>{f.beschriftungen?.[o] ?? o}</button>{/each}
              </span>
            {:else if f.art === "auswahl"}
              <span><Auswahl wert={wert(f) as string} optionen={f.optionen.map((o) => ({ wert: o, titel: f.beschriftungen?.[o] ?? o }))}
                             onwahl={(o) => setzen(f, o)} /></span>
            {:else if f.art === "zahl"}
              <span class="zahl-feld">
                <span class="zaehler">
                  <button onclick={() => zahlSetzen(f, Number(wert(f) ?? 0) - (f.schritt ?? 1))} aria-label="weniger">-</button>
                  <input inputmode="decimal" value={zahlZeigen(f)} onchange={(e) => zahlSetzen(f, Number(e.currentTarget.value.replace(",", ".")))} />
                  <button onclick={() => zahlSetzen(f, Number(wert(f) ?? 0) + (f.schritt ?? 1))} aria-label="mehr">+</button>
                </span>
                {#if f.einheit}<span class="einheit">{f.einheit}</span>{/if}
              </span>
            {:else if f.art === "liste"}
              <span class="chips">
                {#each (wert(f) as string[]) ?? [] as eintrag (eintrag)}
                  <span class="chip">{eintrag}<button aria-label="{eintrag} entfernen"
                        onclick={() => setzen(f, (wert(f) as string[]).filter((x) => x !== eintrag))}><i class="fa-solid fa-xmark"></i></button></span>
                {/each}
                <span class="chip"><i class="fa-solid fa-plus"></i><input placeholder="hinzufügen" bind:value={neuerEintrag[f.name]}
                      onkeydown={(e) => e.key === "Enter" && hinzufuegen(f)} onblur={() => hinzufuegen(f)} /></span>
              </span>
            {:else if f.art === "geheimnis"}
              <span class="eingabe" class:geaendert={f.name in aenderungen}>
                {#if f.name in aenderungen}
                  <input type="text" autocomplete="off" spellcheck="false" placeholder="neuer Wert" value={String(aenderungen[f.name] ?? "")}
                         oninput={(e) => (aenderungen[f.name] = e.currentTarget.value)} />
                {:else}
                  <span class="wert" class:markierbar={f.name in aufgedeckt} bind:this={wertFelder[f.name]}>{f.name in aufgedeckt ? aufgedeckt[f.name] : f.gesetzt ? f.wert : "nicht gesetzt"}</span>
                  {#if f.gesetzt}
                    {#if f.name in aufgedeckt}
                      <button class="auge" title="Wieder verdecken" onclick={() => delete aufgedeckt[f.name]}><i class="fa-solid fa-eye-slash"></i></button>
                    {:else}
                      <button class="auge" title="Aufdecken" onclick={() => aufdecken(f)}><i class="fa-solid fa-eye"></i></button>
                    {/if}
                    <button class="auge" title="Kopieren" onclick={() => geheimnisKopieren(f, wertFelder[f.name])}><i class="fa-solid fa-copy"></i></button>
                  {/if}
                  <button class="auge" title="Neuen Wert eintragen" onclick={() => (aenderungen[f.name] = "")}><i class="fa-solid fa-pen"></i></button>
                {/if}
              </span>
            {:else}
              <span class="eingabe" class:geaendert={f.name in aenderungen}>
                <input value={f.art === "wert" ? JSON.stringify(wert(f)) : String(wert(f) ?? "")} spellcheck="false"
                       oninput={(e) => { const v = e.currentTarget.value; if (f.art !== "wert") setzen(f, v); else { try { setzen(f, JSON.parse(v)); } catch { /* erst bei gültigem JSON */ } } }} />
              </span>
            {/if}
          </div>
        {/each}
      </div>
    {:else if aktiv === ANZEIGE}
    <div class="karte breit">
      <p class="karte-unter" style="margin-top:14px">Gilt nur für diesen Browser.</p>
      <div class="feld">
        <div class="was"><div class="name">Schriftgröße</div></div>
        <span class="segment">{#each SCHRIFT as [s, t] (s)}<button class:aktiv={anzeige.schrift === s} onclick={() => anzeigeSetzen({ schrift: s })}>{t}</button>{/each}</span>
      </div>
      <div class="feld">
        <div class="was"><div class="name">Thema</div></div>
        <span class="segment">{#each THEMA as [s, t] (s)}<button class:aktiv={anzeige.thema === s} onclick={() => anzeigeSetzen({ thema: s })}>{t}</button>{/each}</span>
      </div>
    </div>
    {/if}

    {#if geaendert.length || fehler}
      <div class="speicherleiste">
        {#if fehler}
          <i class="fa-solid fa-triangle-exclamation" style="color:var(--gefahr)"></i><span class="fehlerzeile">{fehler}</span>
        {:else}
          <i class="fa-solid fa-pen" style="color:var(--akzent)"></i>
          <span class="was">{geaendert.length} {geaendert.length === 1 ? "Änderung" : "Änderungen"}: {geaendert.map(titel).join(", ")}</span>
        {/if}
        {#if geaendert.length}
          <button class="knopf still" onclick={verwerfen}>Verwerfen</button>
          <button class="knopf primaer" onclick={speichern} disabled={laeuft}><i class="fa-solid fa-check"></i> {laeuft ? "Speichert ..." : "Speichern"}</button>
        {/if}
      </div>
    {/if}
  </div>
</section>
