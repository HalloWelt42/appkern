<script lang="ts">
  // Hinweis über einer Datei, die aus der Kellerwolke geöffnet wurde: woher sie
  // kommt und bis wann die App sie bearbeiten darf (Recht nur für diese Datei und ihre Begleiter, solange die Anfrage
  // offen ist). "In der Kellerwolke zeigen" öffnet ihren Ordner dort.
  import { onMount } from "svelte";
  import { geraet } from "../lib/geraet.svelte";
  import { anfrage as anfrageHolen, inKellerwolke } from "../lib/kellerwolke";

  let { anfrage, pfad }: { anfrage: string; pfad: string } = $props();
  let bis = $state("");

  // "heute 23:40", "morgen 11:10" oder "19.10. 11:10"
  function frist(zeitpunkt: string): string {
    const d = new Date(zeitpunkt);
    const uhr = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    const tag = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const abstand = Math.round((tag(d) - tag(new Date())) / 86400000);
    if (abstand === 0) return `heute ${uhr}`;
    if (abstand === 1) return `morgen ${uhr}`;
    return `${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} ${uhr}`;
  }

  onMount(() => {
    void anfrageHolen(anfrage).then((a) => (bis = frist(a.gueltig_bis)), () => {});
  });

  const ort = $derived(["Meine Dateien", ...pfad.split("/").filter(Boolean)].join(" / "));
  const zeigen = $derived(inKellerwolke(pfad));
</script>

<div class="hinweis-band">
  <i class="fa-solid fa-cloud"></i>
  {#if geraet.mobil}
    <span><b>Aus der Kellerwolke</b>, nur diese Datei{bis ? `, bearbeitbar bis ${bis}` : ""}</span>
  {:else}
    <span><b>Aus der Kellerwolke:</b> {ort}. Die App darf nur diese Datei und ihre Begleiter bearbeiten{bis ? `, bis ${bis}` : ""};
      danach wieder aus der Kellerwolke öffnen.</span>
    {#if zeigen}
      <span class="knopfzeile"><a class="knopf still" href={zeigen} target="_blank" rel="noopener">
        <i class="fa-solid fa-folder-open"></i> In der Kellerwolke zeigen</a></span>
    {/if}
  {/if}
</div>
