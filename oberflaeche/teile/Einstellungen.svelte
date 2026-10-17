<script lang="ts">
  // Einstellungen, erzeugt aus der Beschreibung der App: Gruppen als Karten, Herkunft je Wert, Geheimnisse verdeckt
  // (das Auge deckt auf, kopieren geht immer), Speichern in einer Leiste; dazu die Anzeige auf diesem Gerät.
  import { anzeige, anzeigeSetzen, type Schrift, type Thema } from "../lib/anzeige.svelte";
  import { hole, json } from "../lib/api.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import type { Feld } from "../lib/typen";
  import { kopieren, markieren } from "../lib/zwischenablage";

  let felder = $state<Feld[]>([]);
  let aenderungen = $state<Record<string, unknown>>({});
  let aufgedeckt = $state<Record<string, string>>({});
  let neuerEintrag = $state<Record<string, string>>({});
  let fehler = $state("");
  let laeuft = $state(false);
  let karten: Record<string, HTMLElement> = {};
  let wertFelder: Record<string, HTMLElement> = $state({});

  async function laden() {
    try {
      felder = await hole<Feld[]>("/einstellungen");
    } catch (f) {
      fehler = (f as Error).message;
    }
  }
  laden();

  const ANZEIGE = "Anzeige auf diesem Gerät";
  const gruppen = $derived([...new Set(felder.map((f) => f.gruppe ?? sitzung.app!.name)), ANZEIGE]);
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
      fehler = (f as Error).message;
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
  const SCHRIFT: [Schrift, string][] = [["normal", "Normal"], ["gross", "Groß"], ["sehr_gross", "Sehr groß"]];
  const THEMA: [Thema, string][] = [["hell", "Hell"], ["dunkel", "Dunkel"], ["system", "wie das System"]];
</script>

<section class="seite">
  <div class="seiten-kopf">
    <h1>Einstellungen</h1>
    <span class="segment">
      {#each gruppen as g (g)}<button onclick={() => karten[g]?.scrollIntoView({ behavior: "smooth", block: "start" })}>{g === ANZEIGE ? "Anzeige" : g}</button>{/each}
    </span>
  </div>
  <div class="rollfeld">
    {#each gruppen.filter((g) => g !== ANZEIGE) as g (g)}
      <div class="karte" bind:this={karten[g]}>
        <h2>{g}</h2>
        {#each felder.filter((f) => (f.gruppe ?? sitzung.app!.name) === g) as f (f.name)}
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
            {:else if f.art === "auswahl"}
              <span class="segment">
                {#each f.optionen as o (o)}<button class:aktiv={wert(f) === o} onclick={() => setzen(f, o)}>{f.beschriftungen?.[o] ?? o}</button>{/each}
              </span>
            {:else if f.art === "zahl"}
              <span class="zaehler">
                <button onclick={() => zahlSetzen(f, Number(wert(f) ?? 0) - (f.schritt ?? 1))} aria-label="weniger">-</button>
                <input inputmode="decimal" value={zahlZeigen(f)} onchange={(e) => zahlSetzen(f, Number(e.currentTarget.value.replace(",", ".")))} />
                <button onclick={() => zahlSetzen(f, Number(wert(f) ?? 0) + (f.schritt ?? 1))} aria-label="mehr">+</button>
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
    {/each}

    <div class="karte" bind:this={karten[ANZEIGE]}>
      <h2>{ANZEIGE}</h2>
      <p class="karte-unter">Gilt nur für diesen Browser.</p>
      <div class="feld">
        <div class="was"><div class="name">Schriftgröße</div></div>
        <span class="segment">{#each SCHRIFT as [s, t] (s)}<button class:aktiv={anzeige.schrift === s} onclick={() => anzeigeSetzen({ schrift: s })}>{t}</button>{/each}</span>
      </div>
      <div class="feld">
        <div class="was"><div class="name">Thema</div></div>
        <span class="segment">{#each THEMA as [s, t] (s)}<button class:aktiv={anzeige.thema === s} onclick={() => anzeigeSetzen({ thema: s })}>{t}</button>{/each}</span>
      </div>
    </div>

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
