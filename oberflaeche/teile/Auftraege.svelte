<script lang="ts">
  // Aufträge: Liste mit Filter und Suche, rechts in der Leiste der gewählte Auftrag.
  import { auftraege, entfernen, laden, mehrLaden, phasenStand, type Filter } from "../lib/auftraege.svelte";
  import { dauer, wann } from "../lib/format";
  import { gehe } from "../lib/navigation.svelte";
  import AuftragZeile from "./AuftragZeile.svelte";

  let { mitLeiste = true }: { mitLeiste?: boolean } = $props();
  let fehler = $state("");
  let suchTakt: ReturnType<typeof setTimeout> | null = null;

  async function neu() {
    fehler = "";
    try {
      await laden();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }
  neu();

  function filtern(f: Filter) {
    auftraege.filter = f;
    auftraege.gewaehlt = null;
    neu();
  }

  function suchen(text: string) {
    auftraege.suche = text;
    if (suchTakt) clearTimeout(suchTakt);
    suchTakt = setTimeout(neu, 300);
  }

  const gewaehlt = $derived(auftraege.liste.find((a) => a.id === auftraege.gewaehlt) ?? null);
  const stand = $derived(gewaehlt ? phasenStand(gewaehlt) : []);
  const ZEICHEN = { fertig: "fa-solid fa-circle-check", jetzt: "fa-solid fa-circle-notch fa-spin", fehler: "fa-solid fa-circle-xmark", offen: "fa-regular fa-circle" } as const;
  const FILTER: [Filter, string][] = [["alle", "Alle"], ["offen", "Offen"], ["fertig", "Fertig"], ["fehler", "Fehler"]];
  const zahl = (f: Filter) => (f === "offen" ? auftraege.laufen + auftraege.warten : f === "fehler" ? auftraege.fehler : 0);
</script>

<section class="seite">
  <div class="seiten-kopf">
    <h1>Aufträge</h1>
    <span class="segment">
      {#each FILTER as [f, titel] (f)}
        <button class:aktiv={auftraege.filter === f} onclick={() => filtern(f)}>{titel}{zahl(f) ? ` ${zahl(f)}` : ""}</button>
      {/each}
    </span>
    <span class="suche"><i class="fa-solid fa-magnifying-glass"></i><input class="eingabe-roh" placeholder="Titel suchen"
          value={auftraege.suche} oninput={(e) => suchen(e.currentTarget.value)} /></span>
  </div>
  <div class="rollfeld">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#each auftraege.liste as a (a.id)}
      <AuftragZeile auftrag={a} />
    {:else}
      <div class="leer">Keine Aufträge {auftraege.filter === "alle" ? "" : `(${FILTER.find(([f]) => f === auftraege.filter)?.[1]})`}</div>
    {/each}
    {#if auftraege.liste.length < auftraege.gesamt}
      <div style="text-align:center"><button class="knopf" onclick={mehrLaden}>Weitere laden ({auftraege.gesamt - auftraege.liste.length})</button></div>
    {/if}
  </div>
</section>

{#if mitLeiste}
  <aside class="leiste">
    {#if gewaehlt}
      <div class="leiste-kopf">
        <h2>{gewaehlt.titel}</h2>
        <span class="zustand {gewaehlt.zustand}">{gewaehlt.zustand === "laeuft" ? "läuft" : gewaehlt.zustand}</span>
        <span class="fassung">{wann(gewaehlt.begonnen_am ?? gewaehlt.erstellt_am)}{#if gewaehlt.beendet_am}, {dauer(gewaehlt.begonnen_am, gewaehlt.beendet_am)}{/if}</span>
      </div>
      <div class="rollfeld">
        {#if gewaehlt.phasen.length}
          <div class="abschnitt">Schritte</div>
          <div class="phasen-liste">
            {#each gewaehlt.phasen as p, i (p.schluessel)}
              <div class="phase {stand[i] === 'offen' ? 'offen' : stand[i]}">
                <i class={ZEICHEN[stand[i]]}></i>{p.titel}
                {#if stand[i] === "jetzt" && gewaehlt.schritt}<span class="dauer">{gewaehlt.schritt}</span>{/if}
              </div>
            {/each}
          </div>
        {/if}
        {#if gewaehlt.fehler}
          <div class="abschnitt">Ursache</div>
          <div class="fehlertext" style="margin-top:0">{gewaehlt.fehler}</div>
        {/if}
        {#if Object.keys(gewaehlt.eingabe).length}
          <div class="abschnitt">Eingabe</div>
          <dl class="werte">
            {#each Object.entries(gewaehlt.eingabe) as [k, v] (k)}<dt>{k}</dt><dd>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>{/each}
          </dl>
        {/if}
        {#if gewaehlt.ergebnis}
          <div class="abschnitt">Ergebnis</div>
          <dl class="werte">
            {#each Object.entries(gewaehlt.ergebnis) as [k, v] (k)}<dt>{k}</dt><dd>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>{/each}
          </dl>
        {/if}
        <div style="display:flex; gap:8px; margin-top:20px; flex-wrap:wrap">
          {#if gewaehlt.zustand !== "laeuft" && gewaehlt.zustand !== "wartet"}
            <button class="knopf still" onclick={() => entfernen(gewaehlt.id)}><i class="fa-solid fa-trash-can"></i> Aus der Liste</button>
          {/if}
          <button class="knopf still" onclick={() => gehe("protokoll")}><i class="fa-solid fa-clock-rotate-left"></i> Protokoll</button>
        </div>
      </div>
    {:else}
      <div class="leer">Einen Auftrag wählen</div>
    {/if}
  </aside>
{/if}
