<script lang="ts">
  // Seite Gestaltung: das Grunddesign der eigenen Apps, aus der einen Wahrheit im Appkern (Marken in stil/marken.css,
  // Katalog in gestaltung/katalog.json, zusammen erzeugt nach gestaltung/marken.json). Marken und Bausteine stehen echt
  // gerendert hell und dunkel nebeneinander, mit Zweck, wann und warum; dazu die Muster mit Grund. In der Schale unter
  // Einstellungen, Gestaltung; Apps mit eigener Schale binden sie mit `familie="leitstand"` ein.
  import daten from "../gestaltung/marken.json";

  type Familie = "schale" | "leitstand";
  let { familie = "schale" }: { familie?: Familie } = $props();

  type Marke = { name: string; art: string; zweck: string; werte: Record<string, string> };
  type Gruppe = { name: string; text: string; marken: Marke[] };
  type Baustein = { familie: string; name: string; klassen: string[]; wann: string; warum: string; html: string; svelte?: string };
  type Muster = { regel: string; grund: string };
  const gruppen = daten.gruppen as Gruppe[];
  const STUFEN = daten.stufen as { name: string; text: string }[];
  const THEMEN = [["hell", "Hell"], ["dunkel", "Dunkel"]] as const;
  const ABSCHNITTE = [["bausteine", "Bausteine"], ["farben", "Farben"], ["schrift", "Schrift"], ["masse", "Maße"],
                      ["muster", "Muster"], ["nutzen", "So nutzt eine App sie"]] as const;
  let abschnitt = $state<(typeof ABSCHNITTE)[number][0]>("bausteine");

  const farbGruppen = gruppen.filter((g) => g.marken.some((m) => m.art === "farbe" || m.art === "schatten"));
  const schrift = gruppen.find((g) => g.name === "Schriften")?.marken ?? [];
  const groessen = gruppen.find((g) => g.name === "Schriftgrößen")?.marken ?? [];
  const masse = gruppen.filter((g) => g.marken.some((m) => m.art === "mass" || m.art === "zeit"));
  const bausteine = $derived((daten.bausteine as Baustein[]).filter((b) => b.familie === familie));
  const muster = daten.muster as Muster[];
  const nutzen = daten.nutzen as string[];

  // Wert einer Marke in einem Zusammenhang, wie er in den Marken steht (der Browser zeigt ihn daneben gerendert)
  function wert(m: Marke, kontext: string): string {
    if (kontext.startsWith("stufe:") && kontext !== "stufe:dicht") return m.werte[kontext] ?? m.werte.alle ?? "";
    return m.werte[kontext] ?? m.werte.alle ?? "";
  }
  const zweiThemen = (m: Marke) => "hell" in m.werte || "dunkel" in m.werte;
  // Schatten zeigt ein Feld mit diesem Schatten, der Schleier ein Feld in seiner Farbe
  const schattenVon = (m: Marke) => (m.name === "--schleier" ? "none" : `var(${m.name})`);
  const flaecheVon = (m: Marke) => (m.name === "--schleier" ? `var(${m.name})` : "var(--flaeche)");
  // Text mit `Code` in Stücke: Code erscheint als <code>, der Rest als Text
  const stuecke = (z: string) => z.split("`").map((text, i) => ({ text, code: i % 2 === 1 }));
</script>

<div class="gs">
  <div class="gs-einleitung">
    <p>Alle eigenen Apps teilen eine Gestaltung: Farben, Schriften und Größen stehen als Marken im Appkern, die
      Bausteine bauen nur darauf. Diese Seite zeigt sie echt gerendert, hell und dunkel nebeneinander; dieselbe Seite
      steht im Handbuch.</p>
    <span class="gs-quelle"><i class="fa-solid fa-code-branch"></i> Appkern, <code>{daten.quelle}</code></span>
  </div>

  <div class="gs-wahl" role="tablist" aria-label="Teile der Gestaltung">
    {#each ABSCHNITTE as [k, titel] (k)}
      <button role="tab" aria-selected={abschnitt === k} class:gs-an={abschnitt === k} onclick={() => (abschnitt = k)}>{titel}</button>
    {/each}
  </div>

  {#if abschnitt === "bausteine"}
    <p class="gs-satz">{familie === "schale" ? "Bausteine der Schale: dicht, für Apps in der gemeinsamen Schale."
      : "Bausteine des Leitstands: für Apps, die ihre Schale selbst zeichnen, in ihrer Schriftstufe."}</p>
    {#each bausteine as b (b.name)}
      <section class="gs-baustein">
        <div class="gs-baustein-kopf">
          <h3>{b.name}</h3>
          <div class="gs-klassen">{#each b.klassen as k (k)}<code>.{k.replaceAll(" ", ".")}</code>{/each}
            {#if b.svelte}<span class="gs-svelte">Svelte: {b.svelte}</span>{/if}</div>
        </div>
        <dl class="gs-grund"><dt>Wann</dt><dd>{b.wann}</dd><dt>Warum</dt><dd>{b.warum}</dd></dl>
        <div class="gs-paar">
          {#each THEMEN as [t, titel] (t)}
            <div class="gs-probe" data-theme={t} aria-label="{b.name}, {titel}">
              <span class="gs-thema">{titel}</span>
              <!-- eigener Inhalt aus dem Katalog des Appkerns -->
              {@html b.html}
            </div>
          {/each}
        </div>
      </section>
    {/each}
  {:else if abschnitt === "farben"}
    {#each farbGruppen as g (g.name)}
      <section class="gs-gruppe">
        <h3>{g.name}</h3>
        <p class="gs-satz">{g.text}</p>
        <div class="gs-farben">
          <span class="gs-spalte">Marke</span>
          {#each THEMEN as [, titel] (titel)}<span class="gs-spalte">{titel}</span>{/each}
          <span class="gs-spalte gs-zweck-spalte">Zweck</span>
          {#each g.marken as m (m.name)}
            <code class="gs-name">{m.name}</code>
            {#each THEMEN as [t] (t)}
              <div class="gs-probe gs-muster" data-theme={t}>
                {#if m.art === "schatten"}
                  <span class="gs-schatten-feld" style="box-shadow: {schattenVon(m)}; background: {flaecheVon(m)}"></span>
                {:else}
                  <span class="gs-feld" style="background: var({m.name})"></span>
                {/if}
                <code class="gs-wert">{zweiThemen(m) ? wert(m, t) : wert(m, "alle")}</code>
              </div>
            {/each}
            <span class="gs-zweck">{m.zweck}</span>
          {/each}
        </div>
      </section>
    {/each}
  {:else if abschnitt === "schrift"}
    <section class="gs-gruppe">
      <h3>Schriften</h3>
      {#each schrift as m (m.name)}
        <div class="gs-schrift-zeile">
          <code class="gs-name">{m.name}</code>
          <span class="gs-schrift-probe" style="font-family: var({m.name})">Grüße aus dem Keller: 0123456789, 42 Min., Il1 O0</span>
          <span class="gs-zweck">{m.zweck}</span>
        </div>
      {/each}
    </section>
    <section class="gs-gruppe">
      <h3>Schriftgrößen je Stufe</h3>
      <p class="gs-satz">Die Schale ist dicht und fest; Apps mit eigener Schale bieten die Stufen klein, mittel und groß
        (Vorgabe groß). Größer wird nur über eine Stufe, nie über feste Werte.</p>
      <div class="gs-stufen">
        <span class="gs-spalte">Marke</span>
        {#each STUFEN as s (s.name)}<span class="gs-spalte" title={s.text}>{s.name}</span>{/each}
        {#each groessen as m (m.name)}
          <code class="gs-name" title={m.zweck}>{m.name}</code>
          {#each STUFEN as s (s.name)}
            <div class="gs-stufe" data-schrift={s.name}>
              <span class="gs-stufe-name">{s.name}</span>
              <span class="gs-stufe-probe" style="font-size: var({m.name})">Aa</span>
              <code class="gs-wert">{wert(m, "stufe:" + s.name)}</code>
            </div>
          {/each}
        {/each}
      </div>
      <dl class="gs-grund gs-stufen-text">
        {#each STUFEN as s (s.name)}<dt>{s.name}</dt><dd>{s.text}</dd>{/each}
      </dl>
    </section>
  {:else if abschnitt === "masse"}
    {#each masse as g (g.name)}
      <section class="gs-gruppe">
        <h3>{g.name}</h3>
        <p class="gs-satz">{g.text}</p>
        {#each g.marken as m (m.name)}
          <div class="gs-mass-zeile">
            <code class="gs-name">{m.name}</code>
            {#if g.name === "Ecken"}
              <span class="gs-ecke" style="border-radius: var({m.name})"></span>
            {:else if m.art === "mass" && g.name === "Abstände"}
              <span class="gs-abstand" style="width: var({m.name})"></span>
            {:else}
              <span></span>
            {/if}
            <code class="gs-wert">{wert(m, "alle")}{#if m.werte["stufe:gross"]} (gross {m.werte["stufe:gross"]}){/if}</code>
            <span class="gs-zweck">{m.zweck}</span>
          </div>
        {/each}
      </section>
    {/each}
  {:else if abschnitt === "muster"}
    <section class="gs-gruppe">
      <h3>Muster mit Grund</h3>
      <dl class="gs-muster-liste">
        {#each muster as m (m.regel)}<dt>{m.regel}</dt><dd>{m.grund}</dd>{/each}
      </dl>
    </section>
  {:else}
    <section class="gs-gruppe">
      <h3>So nutzt eine App die Gestaltung</h3>
      <ul class="gs-liste">
        {#each nutzen as z (z)}<li>{#each stuecke(z) as s, i (i)}{#if s.code}<code>{s.text}</code>{:else}{s.text}{/if}{/each}</li>{/each}
      </ul>
    </section>
  {/if}
</div>
