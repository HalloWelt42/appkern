<script lang="ts">
  // Protokoll: Stufe, Zeitraum und Suche fest oben, Einträge seitenweise; am Telefon als Liste statt Tabelle.
  import { hole } from "../lib/api.svelte";
  import { isoTag, tagAusText, wann } from "../lib/format";
  import type { ProtokollEintrag, Seite, Stufe } from "../lib/typen";

  let { kompakt = false }: { kompakt?: boolean } = $props();
  const GROESSE = 100;
  type Zeitraum = "heute" | "gestern" | "woche" | "alle" | "tag";

  let stufe = $state<Stufe | "">("");
  let zeitraum = $state<Zeitraum>("woche");
  let tagText = $state("");
  let suche = $state("");
  let versatz = $state(0);
  let seite = $state<Seite<ProtokollEintrag>>({ eintraege: [], gesamt: 0 });
  let fehler = $state("");
  let takt: ReturnType<typeof setTimeout> | null = null;

  async function laden() {
    const p = new URLSearchParams({ grenze: String(GROESSE), versatz: String(versatz) });
    if (stufe) p.set("stufe", stufe);
    const jetzt = new Date();
    if (zeitraum === "heute") p.set("tag", isoTag(jetzt));
    if (zeitraum === "gestern") p.set("tag", isoTag(new Date(jetzt.getTime() - 864e5)));
    if (zeitraum === "woche") p.set("ab", isoTag(new Date(jetzt.getTime() - 6 * 864e5)));
    if (zeitraum === "tag") {
      const t = tagAusText(tagText);
      if (!t) return;
      p.set("tag", t);
    }
    if (suche.trim()) p.set("suche", suche.trim());
    fehler = "";
    try {
      seite = await hole<Seite<ProtokollEintrag>>(`/protokoll?${p}`);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }
  laden();

  function neu(spaeter = false) {
    versatz = 0;
    if (takt) clearTimeout(takt);
    if (spaeter) takt = setTimeout(laden, 300);
    else laden();
  }

  function blaettern(richtung: number) {
    versatz = Math.max(0, versatz + richtung * GROESSE);
    laden();
  }

  const STUFEN: [Stufe | "", string][] = [["", "Alle"], ["info", "Info"], ["warnung", "Warnung"], ["fehler", "Fehler"]];
  const ZEITRAEUME: [Zeitraum, string][] = [["heute", "Heute"], ["gestern", "Gestern"], ["woche", "7 Tage"], ["alle", "Alle"], ["tag", "Tag"]];
  const ZEICHEN = { info: "fa-circle-info", warnung: "fa-triangle-exclamation", fehler: "fa-circle-xmark" } as const;
</script>

<section class="seite">
  <div class="seiten-kopf">
    <h1>Protokoll</h1>
    <span class="segment">{#each STUFEN as [s, t] (s)}<button class:aktiv={stufe === s} onclick={() => ((stufe = s), neu())}>{t}</button>{/each}</span>
    <span class="segment">{#each ZEITRAEUME as [z, t] (z)}<button class:aktiv={zeitraum === z} onclick={() => ((zeitraum = z), neu())}>{t}</button>{/each}</span>
    {#if zeitraum === "tag"}
      <span class="suche" style="min-width:150px"><i class="fa-solid fa-calendar-day"></i>
        <input class="eingabe-roh" placeholder="TT.MM.JJJJ" bind:value={tagText} oninput={() => neu(true)} /></span>
    {/if}
    <span class="suche"><i class="fa-solid fa-magnifying-glass"></i>
      <input class="eingabe-roh" placeholder="Name oder Text" bind:value={suche} oninput={() => neu(true)} /></span>
  </div>
  <div class="rollfeld">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#if kompakt}
      <div class="t-liste">
        {#each seite.eintraege as e (e.id)}
          <div class="t-zeile">
            <i class="fa-solid {ZEICHEN[e.stufe]} stufe {e.stufe}" style="font-size:18px"></i>
            <div class="t-text"><div class="t-name">{e.bezug_name ?? e.ereignis}</div><div class="t-meta">{wann(e.zeit)} · {e.text || e.ereignis}</div></div>
          </div>
        {:else}<div class="leer">Nichts im gewählten Zeitraum</div>{/each}
      </div>
    {:else}
      <table class="tabelle">
        <thead><tr><th style="width:160px">Zeit</th><th style="width:44px"></th><th style="width:220px">Ereignis</th><th style="width:280px">Bezug</th><th>Text</th></tr></thead>
        <tbody>
          {#each seite.eintraege as e (e.id)}
            <tr>
              <td class="zeit">{wann(e.zeit)}</td>
              <td class="stufe {e.stufe}"><i class="fa-solid {ZEICHEN[e.stufe]}" title={e.stufe}></i></td>
              <td class="ereignis"><code>{e.ereignis}</code></td>
              <td>{e.bezug_name ?? ""}</td>
              <td>{e.text}</td>
            </tr>
          {:else}<tr class="leer"><td colspan="5">Nichts im gewählten Zeitraum</td></tr>{/each}
        </tbody>
      </table>
    {/if}
    {#if seite.gesamt > 0}
      <div class="seitenzeile">
        <span>{versatz + 1} bis {Math.min(versatz + GROESSE, seite.gesamt)} von {seite.gesamt.toLocaleString("de-DE")}</span>
        <button class="knopf" aria-label="Zurück" disabled={versatz === 0} onclick={() => blaettern(-1)}><i class="fa-solid fa-chevron-left"></i></button>
        <button class="knopf" disabled={versatz + GROESSE >= seite.gesamt} onclick={() => blaettern(1)}>Weiter <i class="fa-solid fa-chevron-right"></i></button>
      </div>
    {/if}
  </div>
</section>
