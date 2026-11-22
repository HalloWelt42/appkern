<script lang="ts" generics="Z extends { laeuft: boolean }, P">
  // Geräte der Übergabe (RAD-18): je anderes Gerät Name, was dort läuft, Holen (spielt dort etwas) und Dorthin (spielt
  // hier etwas). Kopf mit dem eigenen Namen (antippen benennt um) und Schließen. Die Zeile zum Zustand liefert die App.
  import type { Geraeteart, Uebergabe } from "../lib/uebergabe.svelte";

  const DEUTSCH = {
    titel: "Geräte", hier: "hier", diesesGeraet: "dieses Gerät", umbenennen: "Dieses Gerät umbenennen", name: "Name dieses Geräts",
    schliessen: "Schließen", holen: "Holen", holenHilfe: "Den Ton von dort hierher holen, an derselben Stelle",
    dorthin: "Dorthin", dorthinHilfe: "Was hier läuft, dort weiterspielen; hier hält es an",
    keins: "Kein anderes Gerät offen. Öffne die App auf einem zweiten Gerät.", verbindet: "Verbindung zu den Geräten wird aufgebaut ...",
  };
  let { uebergabe, zeile, hierSpielt, telefon = false, texte = {}, onzu }: {
    uebergabe: Uebergabe<Z, P>;
    /** eigene Texte (Sprache der App); fehlende auf Deutsch */
    texte?: Partial<typeof DEUTSCH>;
    /** Text zu einem Zustand, etwa "spielt: MANGORADIO" */
    zeile: (zustand: Z | null) => string;
    /** spielt hier gerade etwas (sonst kein Dorthin) */
    hierSpielt: boolean;
    telefon?: boolean;
    onzu: () => void;
  } = $props();

  const tx = $derived({ ...DEUTSCH, ...texte });
  const SYMBOL: Record<Geraeteart, string> = { rechner: "fa-desktop", telefon: "fa-mobile-screen", tablet: "fa-tablet-screen-button" };
  let benennen = $state(false);
  let entwurf = $state("");

  function namenSpeichern() {
    if (entwurf.trim()) uebergabe.umbenennen(entwurf.trim());
    benennen = false;
  }
  function tun(f: () => void) {
    f();
    onzu();
  }
</script>

<div class="ak-geraete" class:telefon role="dialog" aria-label={tx.titel}>
  <div class="ak-geraete-kopf">
    <i class="fa-solid fa-tower-broadcast" aria-hidden="true"></i><b>{tx.titel}</b>
    {#if benennen}
      <!-- svelte-ignore a11y_autofocus -->
      <input class="ak-geraete-name" bind:value={entwurf} maxlength="40" autofocus aria-label={tx.name}
        onkeydown={(e) => { if (e.key === "Enter") namenSpeichern(); if (e.key === "Escape") benennen = false; }} onblur={namenSpeichern} />
    {:else}
      <button type="button" class="ak-geraete-hier" title={tx.umbenennen}
        onclick={() => { entwurf = uebergabe.ich?.name ?? ""; benennen = true; }}>{tx.hier}: {uebergabe.ich?.name ?? tx.diesesGeraet}</button>
    {/if}
    <button type="button" class="ak-geraete-zu" aria-label={tx.schliessen} onclick={onzu}><i class="fa-solid fa-xmark"></i></button>
  </div>
  {#each uebergabe.andere as g (g.id)}
    <div class="ak-geraete-zeile" class:spielt={g.zustand?.laeuft}>
      <i class="fa-solid {SYMBOL[g.art]}" aria-hidden="true"></i>
      <span class="ak-geraete-text"><b>{g.name}</b><span>{zeile(g.zustand)}</span></span>
      <span class="ak-geraete-knoepfe">
        {#if g.zustand}
          <button type="button" class="holen" title={tx.holenHilfe} onclick={() => tun(() => uebergabe.holen(g.id))}>
            <i class="fa-solid fa-hand-holding"></i>{tx.holen}</button>
        {/if}
        {#if hierSpielt}
          <button type="button" title={tx.dorthinHilfe} onclick={() => tun(() => uebergabe.dorthin(g.id))}>
            <i class="fa-solid fa-share"></i>{tx.dorthin}</button>
        {/if}
      </span>
    </div>
  {:else}
    <p class="ak-geraete-leer">{uebergabe.verbunden ? tx.keins : tx.verbindet}</p>
  {/each}
</div>

<style>
  .ak-geraete { inline-size: min(380px, calc(100vw - 24px)); padding: 10px; border-radius: var(--r2, 10px); display: grid; gap: 6px;
    background: var(--flaeche); color: var(--text); border: 1px solid var(--rand); box-shadow: var(--schatten-schwebend);
    font-size: var(--klein); }
  .ak-geraete.telefon { inline-size: 100%; border-radius: 18px 18px 0 0; border: 0; font-size: var(--gross);
    padding: 12px 12px calc(16px + env(safe-area-inset-bottom)); }
  .ak-geraete-kopf { display: flex; align-items: center; gap: 8px; padding: 2px 4px 6px; border-bottom: 1px solid var(--rand); }
  .ak-geraete-kopf > b { flex: 1; font-size: calc(var(--marke) * .95); letter-spacing: .08em; text-transform: uppercase; }
  .ak-geraete-hier { border: 0; background: none; color: var(--text-3); font: inherit; cursor: pointer; padding: 4px; }
  .ak-geraete-hier:hover { color: var(--text); text-decoration: underline; }
  .ak-geraete-name { inline-size: 12em; font: inherit; padding: 4px 6px; border-radius: 6px; border: 1px solid var(--rand); background: var(--flaeche-2); color: var(--text); }
  .ak-geraete-zu { border: 0; background: none; color: var(--text-3); cursor: pointer; font-size: var(--gross); padding: 4px 6px; }
  .ak-geraete-zeile { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 6px 4px; border-radius: 8px; }
  .ak-geraete-zeile:hover { background: var(--flaeche-2); }
  .ak-geraete-zeile > i { text-align: center; color: var(--text-3); font-size: 18px; }
  .ak-geraete-zeile.spielt > i { color: var(--akzent); }
  .ak-geraete-text { min-inline-size: 0; display: grid; }
  .ak-geraete-text b { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ak-geraete-text span { color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ak-geraete-knoepfe { display: flex; gap: 4px; }
  .ak-geraete-knoepfe button { display: inline-flex; align-items: center; gap: 6px; min-block-size: 34px; padding: 0 10px; border-radius: 8px;
    cursor: pointer; border: 1px solid var(--rand); background: var(--flaeche-2); color: var(--text); font: inherit; }
  .telefon .ak-geraete-knoepfe button { min-block-size: 44px; }
  .ak-geraete-knoepfe button.holen { background: var(--akzent-flaeche); color: var(--auf-akzent); border-color: transparent; font-weight: 600; }
  .ak-geraete-leer { margin: 6px 4px; color: var(--text-3); }
</style>
