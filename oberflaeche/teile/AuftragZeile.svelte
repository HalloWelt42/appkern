<script lang="ts">
  // Ein Auftrag in der Liste: Titel, Zeit, Schritte, Fortschritt, Fehler, Abbrechen oder Wiederholen.
  import { abbrechen, auftraege, wiederholen } from "../lib/auftraege.svelte";
  import { seit, wann } from "../lib/format";
  import { leisteOeffnen } from "../lib/leiste.svelte";
  import type { Auftrag } from "../lib/typen";
  import Schritte from "./Schritte.svelte";

  let { auftrag: a }: { auftrag: Auftrag } = $props();
  const ZUSTAND: Record<string, string> = {
    wartet: "wartet", laeuft: "läuft", fertig: "fertig", fehler: "Fehler", abgebrochen: "abgebrochen", unterbrochen: "unterbrochen",
  };
  const zeit = $derived(
    a.zustand === "laeuft" ? seit(a.begonnen_am) : a.zustand === "wartet" ? `eingereiht ${wann(a.erstellt_am)}` : wann(a.beendet_am),
  );
  let fehler = $state("");

  async function tun(e: Event, arbeit: () => Promise<void>) {
    e.stopPropagation();
    fehler = "";
    try {
      await arbeit();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  // Wählen zeigt den Auftrag in der Leiste; ist sie eine Tafel (schmale Fenster), fährt sie auf.
  function waehlen() {
    auftraege.gewaehlt = a.id;
    leisteOeffnen();
  }
</script>

<div class="auftrag" class:gewaehlt={auftraege.gewaehlt === a.id} role="button" tabindex="0"
     onclick={() => waehlen()} onkeydown={(e) => e.key === "Enter" && waehlen()}>
  <span class="art"><i class="fa-solid fa-gears"></i></span>
  <div style="min-width:0">
    <div class="titel"><span class="name">{a.titel}</span><span class="wann">{zeit}</span></div>
    <Schritte auftrag={a} />
    {#if a.zustand === "laeuft"}
      <div class="balken"><span style="width:{Math.round((a.fortschritt ?? 0) * 100)}%"></span></div>
      <div class="unterzeile">
        <span>{a.schritt}</span>{#if a.fortschritt != null}<span class="rechts">{Math.round(a.fortschritt * 100)} %</span>{/if}
      </div>
    {:else if a.zustand === "wartet"}
      <div class="unterzeile"><span>{a.zurueckgestellt ? `zurückgestellt: ${a.zurueckgestellt}` : a.schritt || "wartet auf einen freien Platz"}</span></div>
    {/if}
    {#if a.von}<div class="unterzeile"><span>angestoßen von {a.von}</span></div>{/if}
    {#if a.fehler && a.zustand !== "fertig"}<div class="fehlertext">{a.fehler}</div>{/if}
    {#if fehler}<div class="fehlerzeile">{fehler}</div>{/if}
  </div>
  <div class="aktionen">
    <span class="zustand {a.zustand}">{a.zurueckgestellt ? "zurückgestellt" : ZUSTAND[a.zustand]}</span>
    {#if a.zustand === "laeuft" || a.zustand === "wartet"}
      <button class="knopf still" title={a.zustand === "laeuft" ? "Abbrechen (am nächsten Haltepunkt)" : "Abbrechen"}
              disabled={a.abbruch_gewuenscht} onclick={(e) => tun(e, () => abbrechen(a.id))}>
        <i class="fa-solid {a.zustand === 'laeuft' ? 'fa-stop' : 'fa-xmark'}"></i>
      </button>
    {:else if a.zustand !== "fertig"}
      <button class="knopf" title={a.fortsetzbar ? "Setzt am Zwischenstand an" : "Beginnt von vorn"}
              onclick={(e) => tun(e, () => wiederholen(a.id))}><i class="fa-solid fa-rotate-right"></i> Wiederholen</button>
    {/if}
  </div>
</div>
