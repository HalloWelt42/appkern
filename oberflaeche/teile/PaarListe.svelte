<script lang="ts">
  // Liste von Paaren in den Einstellungen (Feld mit `paar`): je Eintrag zwei Auswahlen, etwa "App" und "Stimme", der
  // zweite Teil leer heißt `paar.leer` (etwa "alle Stimmen"). Gespeichert wird wie bisher als Text je Eintrag:
  // "erster" oder "erster<trenner>zweiter". Die Optionen kommen aus dem Angebot des Systems (optionen, zweite);
  // Eingetragenes, das nicht mehr angeboten wird, bleibt sichtbar und lässt sich entfernen. Unten eine Zeile zum
  // Hinzufügen; doppelte Einträge fallen weg.
  import type { Option, Paar } from "../lib/typen";
  import Auswahl from "./Auswahl.svelte";

  let { paar, wert, erste, zweite, titel = "", onaendern }: {
    paar: Paar; wert: string[]; erste: Option[]; zweite: Option[]; titel?: string; onaendern: (liste: string[]) => void;
  } = $props();

  const zerlegen = (eintrag: string): [string, string] => {
    const i = eintrag.indexOf(paar.trenner);
    return i < 0 ? [eintrag, ""] : [eintrag.slice(0, i), eintrag.slice(i + paar.trenner.length)];
  };
  const fuegen = (a: string, b: string): string => (b ? `${a}${paar.trenner}${b}` : a);
  const eintraege = $derived(wert.map(zerlegen));

  // Angebotenes und alles Eingetragene, damit jede Zeile ihren Namen zeigt
  const ersteOptionen = $derived.by((): Option[] => {
    const liste = [...erste];
    for (const [a] of eintraege) if (a && !liste.some((o) => o.wert === a)) liste.push({ wert: a, titel: a, hinweis: "nicht mehr angeboten" });
    return liste;
  });
  const zweiteOptionen = $derived.by((): Option[] => {
    const liste: Option[] = [{ wert: "", titel: paar.leer, hinweis: "" }, ...zweite];
    for (const [, b] of eintraege) if (b && !liste.some((o) => o.wert === b)) liste.push({ wert: b, titel: "nicht mehr vorhanden", hinweis: b });
    return liste;
  });

  function aendern(liste: string[]): void {
    onaendern([...new Set(liste)]);
  }
  function setzen(i: number, a: string, b: string): void {
    aendern(eintraege.map(([x, y], j) => (j === i ? fuegen(a, b) : fuegen(x, y))));
  }

  let neuErst = $state("");
  let neuZweit = $state("");
  const neu = $derived(neuErst ? fuegen(neuErst, neuZweit) : "");
  function hinzufuegen(): void {
    if (!neu || wert.includes(neu)) return;
    aendern([...wert, neu]);
    neuErst = "";
    neuZweit = "";
  }
</script>

<div class="paarliste">
  {#each eintraege as [a, b], i (fuegen(a, b))}
    <div class="paar-zeile">
      <Auswahl wert={a} optionen={ersteOptionen} titel={paar.erstes} onwahl={(w) => setzen(i, w, b)} />
      <Auswahl wert={b} optionen={zweiteOptionen} titel={paar.zweites} onwahl={(w) => setzen(i, a, w)} />
      <button type="button" class="paar-knopf" title="Eintrag entfernen" aria-label="Eintrag entfernen"
              onclick={() => aendern(wert.filter((_, j) => j !== i))}><i class="fa-solid fa-xmark"></i></button>
    </div>
  {:else}
    <div class="paar-leer">Noch kein Eintrag{titel ? ` für ${titel}` : ""}.</div>
  {/each}
  <div class="paar-zeile neu">
    <Auswahl wert={neuErst} optionen={erste} titel={paar.erstes} platzhalter="{paar.erstes} wählen" onwahl={(w) => (neuErst = w)} />
    <Auswahl wert={neuZweit} optionen={[{ wert: "", titel: paar.leer, hinweis: "" }, ...zweite]} titel={paar.zweites}
             onwahl={(w) => (neuZweit = w)} />
    <button type="button" class="paar-knopf dazu" title="Hinzufügen" aria-label="Hinzufügen" disabled={!neu || wert.includes(neu)}
            onclick={hinzufuegen}><i class="fa-solid fa-plus"></i></button>
  </div>
</div>
