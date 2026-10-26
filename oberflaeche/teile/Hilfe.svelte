<script lang="ts">
  // Das Hilfefenster: schwebt frei über der App (nicht im Aufbau der Seite), am Kopf verschiebbar, am Griff unten rechts
  // in der Größe veränderbar, minimierbar auf den Kopf, groß über die ganze Seite. Oben Thema und Abschnitt, darunter
  // die Suche über alle Themen oder nur das gezeigte; Treffer sind markiert, der aktive steht in der Mitte. Verweise
  // `hilfe:thema/anker` springen im Fenster. Einmal in der Schale der App einhängen; gesteuert wird es über `hilfe`.
  import { tick, untrack } from "svelte";
  import { hilfe } from "../lib/hilfe.svelte";

  const thema = $derived(hilfe.aktuell);
  let artikel = $state<HTMLElement | null>(null);
  let feld = $state<HTMLElement | null>(null);

  /** Markiert die Treffer im gezeigten Thema Textknoten für Textknoten; die alten Markierungen lösen sich vorher auf */
  function markieren(wo: HTMLElement, nadel: string, aktiv: number): void {
    for (const m of wo.querySelectorAll("mark.hilfe-treffer")) m.replaceWith(document.createTextNode(m.textContent ?? ""));
    wo.normalize();
    if (!nadel) return;
    const n = nadel.toLowerCase();
    const gaenger = document.createTreeWalker(wo, NodeFilter.SHOW_TEXT);
    const liste: Text[] = [];
    while (gaenger.nextNode()) liste.push(gaenger.currentNode as Text);
    let zaehler = 0;
    for (const knoten of liste) {
      const text = knoten.nodeValue ?? "";
      const klein = text.toLowerCase();
      if (!klein.includes(n)) continue;
      const teil = document.createDocumentFragment();
      let pos = 0;
      for (let i = klein.indexOf(n); i >= 0; i = klein.indexOf(n, pos)) {
        if (i > pos) teil.append(text.slice(pos, i));
        const mark = document.createElement("mark");
        mark.className = zaehler === aktiv ? "hilfe-treffer aktiv" : "hilfe-treffer";
        mark.textContent = text.slice(i, i + n.length);
        teil.append(mark);
        zaehler++;
        pos = i + n.length;
      }
      if (pos < text.length) teil.append(text.slice(pos));
      knoten.replaceWith(teil);
    }
    wo.querySelector("mark.hilfe-treffer.aktiv")?.scrollIntoView({ block: "center" });
  }

  $effect(() => {
    const nadel = hilfe.suche.trim();
    void hilfe.thema; void hilfe.nr; void hilfe.treffer;
    if (artikel) markieren(artikel, nadel, hilfe.aktivLokal());
  });

  // Sprung zum Abschnitt, sobald das Thema gezeichnet ist (auch erneut zum selben Abschnitt)
  $effect(() => {
    void hilfe.sprung;
    const anker = hilfe.anker;
    const wo = artikel;
    if (!wo || hilfe.suche.trim()) return;
    void tick().then(() => {
      const ziel = anker ? wo.querySelector(`[data-anker="${anker}"]`) : null;
      if (ziel) ziel.scrollIntoView({ block: "start" });
      else if (feld) feld.scrollTop = 0;
    });
  });

  // Bedienelemente immer erreichbar: beim Öffnen und bei jeder Änderung der Fenstergröße prüfen
  $effect(() => {
    if (!hilfe.offen) return;
    const pruefen = () => hilfe.sichtSchuetzen();
    addEventListener("resize", pruefen);
    untrack(pruefen);
    return () => removeEventListener("resize", pruefen);
  });

  function sucheTaste(e: KeyboardEvent): void {
    if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) hilfe.voriger();
      else hilfe.naechster();
    } else if (e.key === "Escape") {
      hilfe.sucheSetzen("");
    }
  }

  /** Verweise der Form hilfe:thema/anker bleiben im Fenster */
  function verweis(e: MouseEvent): void {
    const a = (e.target as HTMLElement).closest("a");
    const ziel = a?.getAttribute("href") ?? "";
    if (!ziel.startsWith("hilfe:")) return;
    e.preventDefault();
    const [kennung, anker] = ziel.slice(6).split("/");
    hilfe.zeigen(kennung, anker);
  }

  function ziehen(e: PointerEvent, art: "lage" | "groesse"): void {
    if (hilfe.maximiert || (e.target as HTMLElement).closest("button")) return;
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY;
    const ox = hilfe.x, oy = hilfe.y, ob = hilfe.breite, oh = hilfe.hoehe;
    const bewegen = (ev: PointerEvent): void => {
      if (art === "lage") hilfe.verschieben(ox + ev.clientX - sx, oy + ev.clientY - sy);
      else hilfe.groesse(ob + ev.clientX - sx, oh + ev.clientY - sy);
    };
    const los = (): void => {
      hilfe.fertig();
      removeEventListener("pointermove", bewegen);
      removeEventListener("pointerup", los);
    };
    addEventListener("pointermove", bewegen);
    addEventListener("pointerup", los);
  }

  const lage = $derived(hilfe.maximiert ? ""
    : `left: ${hilfe.x}px; top: ${hilfe.y}px; width: ${hilfe.breite}px; height: ${hilfe.minimiert ? "auto" : `${hilfe.hoehe}px`};`);
</script>

{#if hilfe.offen}
  <section class="hilfe-fenster" class:gross={hilfe.maximiert} class:minimiert={hilfe.minimiert} style={lage} aria-label="Hilfe">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <header class="hilfe-kopf" onpointerdown={(e) => ziehen(e, "lage")} ondblclick={() => hilfe.maximieren()}>
      <i class="fa-solid {thema?.symbol ?? 'fa-circle-question'}"></i>
      <div class="hilfe-titel"><b>{thema?.titel ?? "Hilfe"}</b>{#if thema?.untertitel}<span>{thema.untertitel}</span>{/if}</div>
      <button type="button" title={hilfe.minimiert ? "Wieder aufklappen" : "Auf den Kopf verkleinern"} onclick={() => hilfe.minimieren()}>
        <i class="fa-solid {hilfe.minimiert ? 'fa-window-maximize' : 'fa-window-minimize'}"></i></button>
      <button type="button" title={hilfe.maximiert ? "Wieder als Fenster" : "Groß über die ganze Seite"} onclick={() => hilfe.maximieren()}>
        <i class="fa-solid {hilfe.maximiert ? 'fa-compress' : 'fa-expand'}"></i></button>
      <button type="button" title="Hilfe schließen" onclick={() => hilfe.schliessen()}><i class="fa-solid fa-xmark"></i></button>
    </header>

    {#if !hilfe.minimiert}
      <div class="hilfe-leiste">
        <div class="hilfe-wahl">
          <select class="eingabe" aria-label="Thema" value={thema?.kennung} onchange={(e) => hilfe.themaWaehlen(e.currentTarget.value)}>
            {#each hilfe.themen as t (t.kennung)}<option value={t.kennung}>{t.bereich}: {t.titel}</option>{/each}
          </select>
          {#if thema?.abschnitte.length}
            <select class="eingabe" aria-label="Abschnitt" value={hilfe.anker ?? ""} onchange={(e) => hilfe.abschnittWaehlen(e.currentTarget.value)}>
              <option value="">Zum Anfang</option>
              {#each thema.abschnitte as a (a.anker)}<option value={a.anker}>{a.titel}</option>{/each}
            </select>
          {/if}
        </div>
        <div class="hilfe-suchzeile">
          <div class="hilfe-bereich" role="group" aria-label="Wo suchen">
            <button type="button" class:an={hilfe.bereich === "alle"} title="In allen Themen suchen" onclick={() => hilfe.bereichSetzen("alle")}>Alle</button>
            <button type="button" class:an={hilfe.bereich === "thema"} title="Nur in diesem Thema suchen" onclick={() => hilfe.bereichSetzen("thema")}>Thema</button>
          </div>
          <label class="suche">
            <i class="fa-solid fa-magnifying-glass"></i>
            <input placeholder={hilfe.bereich === "alle" ? "In allen Themen suchen" : "In diesem Thema suchen"} value={hilfe.suche}
                   oninput={(e) => hilfe.sucheSetzen(e.currentTarget.value)} onkeydown={sucheTaste} aria-label="In der Hilfe suchen" />
            {#if hilfe.suche.trim()}
              <span class="hilfe-zaehler">{hilfe.treffer.length ? hilfe.nr + 1 : 0} von {hilfe.treffer.length}</span>
              <button type="button" class="hilfe-mini" title="Voriger Treffer (Umschalt und Enter)" onclick={() => hilfe.voriger()}><i class="fa-solid fa-chevron-up"></i></button>
              <button type="button" class="hilfe-mini" title="Nächster Treffer (Enter)" onclick={() => hilfe.naechster()}><i class="fa-solid fa-chevron-down"></i></button>
              <button type="button" class="leeren" title="Suche leeren" aria-label="Suche leeren" onclick={() => hilfe.sucheSetzen("")}><i class="fa-solid fa-xmark"></i></button>
            {/if}
          </label>
        </div>
        {#if hilfe.bereich === "alle" && hilfe.suche.trim() && hilfe.treffer.length && thema}
          <div class="hilfe-hinweis">Treffer in <b>{thema.titel}</b>; die Pfeile führen durch alle Themen.</div>
        {/if}
      </div>

      <div class="hilfe-inhalt" bind:this={feld}>
        {#if thema}
          {#key thema.kennung}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
            <article class="hilfe-text" bind:this={artikel} onclick={verweis}>{@html thema.html}</article>
          {/key}
        {:else}
          <p class="hilfe-leer">Diese App hat keine Hilfethemen angemeldet.</p>
        {/if}
      </div>
      {#if !hilfe.maximiert}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="hilfe-griff" title="Größe ändern" onpointerdown={(e) => ziehen(e, "groesse")}></div>
      {/if}
    {/if}
  </section>
{/if}
