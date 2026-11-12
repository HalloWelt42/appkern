<script lang="ts">
  // Erzeugen mit den Fähigkeiten je Modell (IMG-6), ein Baustein für alle Apps, die Bilder erzeugen lassen (ImageVault,
  // Redaktion): Modellkarten mit dem, was das Modell kann, und seinem Lizenzhinweis; die Stilvorlage erscheint nur bei
  // Modellen, die Bildvorlagen annehmen (nur zeigen, was geht); Format als feste Auswahl, Iterationstiefe im Bereich des
  // Modells, Varianten bis zur Höchstzahl, Zeitabschätzung aus eigenen Messungen. Woher Vorlagen kommen (Ziehen, Auswahl
  // aus dem ImageVault), sagt die App über ihre Rückrufe.
  import { anpassen, dauerText, endformat, endformatAusVerhaeltnis, festeSchritte, flaechenBereich, formate, pixel, schaetzung,
           schrittBereich, startwahl, type Bildmodell, type Bildvorlage, type Erzeugungswahl } from "../lib/bilderzeugung";

  let { modelle, wahl = $bindable(), vorlagen = $bindable([]), ondateien, onwaehlen }: {
    modelle: Bildmodell[];
    wahl: Erzeugungswahl;
    vorlagen?: Bildvorlage[];
    ondateien?: (dateien: File[]) => void;   // Bilder als Stilvorlage hierher gezogen
    onwaehlen?: () => void;                  // Stilvorlage aus dem ImageVault wählen
  } = $props();

  const modell = $derived(modelle.find((m) => m.id === wahl.modell) ?? modelle[0]);
  const bereich = $derived(modell ? schrittBereich(modell) : null);
  const fest = $derived(modell ? festeSchritte(modell) : null);
  const zeit = $derived(modell ? schaetzung(modell, wahl) : null);
  const schritteJetzt = $derived(wahl.schritte ?? fest);
  let ueber = $state(false);

  // Eigenes Format (Endformat): beliebige Maße oder Seitenverhältnis mit Fläche; gerechnet wird im nächsten erlaubten Maß
  // des Modells, danach verkleinert der Server auf das Endformat und schneidet bei Bedarf mittig zu
  const flaeche = $derived(modell ? flaechenBereich(modell) : null);
  const vorgeschlagen = $derived(modell ? !wahl.ende && formate(modell).some((f) => f.groesse === wahl.groesse) : true);
  const ergebnis = $derived(modell && !vorgeschlagen ? endformat(modell, pixel(wahl.ende ?? wahl.groesse).b, pixel(wahl.ende ?? wahl.groesse).h) : null);
  const lesbar = (g: string) => g.replace("x", " × ");
  const eigenKachel = $derived(kachel(vorgeschlagen ? "1600x900" : (wahl.ende ?? wahl.groesse)));
  let eigenOffen = $state(false);
  let eingabe = $state<"masse" | "verhaeltnis">("masse");
  let breite = $state(1500);
  let hoehe = $state(900);
  let verhaeltnis = $state("21:9");
  let megapixel = $state(1);
  let ungueltig = $state(false);

  function eigenesFormat() {
    if (!modell) return;
    const e = eingabe === "masse" ? endformat(modell, breite, hoehe) : endformatAusVerhaeltnis(modell, verhaeltnis, megapixel);
    ungueltig = !e;
    if (e) wahl = { ...wahl, groesse: e.rechnen, ende: e.ende === e.rechnen ? null : e.ende };
  }
  function eigenOeffnen() {
    eigenOffen = true;
    if (flaeche) megapixel = Math.round(flaeche.vorgabe * 10) / 10;
    eigenesFormat();
  }
  // beim Wechsel des Modells bleibt ein eigenes Endformat; das Rechenformat bestimmt das neue Modell
  function modellWaehlen(m: Bildmodell) {
    if (m.id === modell?.id) return;
    const ende = vorgeschlagen ? null : (wahl.ende ?? wahl.groesse);
    wahl = ende ? anpassen(m, { ...startwahl(m), ende }) : startwahl(m);
  }

  // jede Wahl so, dass das gewählte Modell sie annimmt; Vorlagen nur so viele, wie es lesen kann
  $effect(() => {
    if (!modell) return;
    const neu = anpassen(modell, wahl);
    if (JSON.stringify(neu) !== JSON.stringify(wahl)) wahl = neu;
    const hoechstens = modell.kann_bearbeiten ? modell.vorlagen_max ?? 4 : 0;
    if (vorlagen.length > hoechstens) vorlagen = vorlagen.slice(0, hoechstens);
  });

  function kachel(groesse: string): { breite: number; hoehe: number } {
    const { b, h } = pixel(groesse);
    return { breite: Math.round(26 * Math.min(1, b / h)), hoehe: Math.round(26 * Math.min(1, h / b)) };
  }

  function ablegen(e: DragEvent) {
    e.preventDefault();
    ueber = false;
    const dateien = [...(e.dataTransfer?.files ?? [])].filter((d) => d.type.startsWith("image/"));
    if (dateien.length) ondateien?.(dateien);
  }
</script>

{#if modell}
  <div class="ez-tafel">
    <div class="ez-feld">
      <span class="ez-name">Modell<small>was das Modell kann, steht an der Karte</small></span>
      <div class="ez-modelle">
        {#each modelle as m (m.id)}
          {@const b = schrittBereich(m)}
          {@const f = festeSchritte(m)}
          <button type="button" class="ez-modell" class:an={m.id === modell.id} onclick={() => modellWaehlen(m)}>
            <span class="ez-modell-kopf"><b>{m.name}</b>
              <span class="etikett" class:gut={m.geladen}>{m.geladen ? "geladen" : m.ladezeit_s !== null ? `nicht geladen, Laden etwa ${dauerText(m.ladezeit_s)}` : "nicht geladen"}</span></span>
            {#if m.zweck}<span class="ez-leise">{m.zweck}</span>{/if}
            <span class="ez-kann">
              {#if m.kann_bearbeiten}<span class="ja"><i class="fa-solid fa-image"></i>Stilvorlage, bis {m.vorlagen_max ?? 4} Bilder</span>{/if}
              <span><i class="fa-solid fa-crop-simple"></i>{formate(m).length} {formate(m).length === 1 ? "Format" : "Formate"}</span>
              {#if b}<span><i class="fa-solid fa-stairs"></i>Schritte {b.kleinste} bis {b.groesste}</span>
              {:else if f}<span><i class="fa-solid fa-stairs"></i>{f} Schritte fest</span>{/if}
              <span><i class="fa-solid fa-clone"></i>bis {m.anzahl_max} {m.anzahl_max === 1 ? "Variante" : "Varianten"}</span>
            </span>
            {#if m.lizenz_hinweis || m.lizenz}
              <span class="ez-lizenz"><i class="fa-solid fa-scale-balanced"></i>{m.lizenz_hinweis || `Lizenz ${m.lizenz}`}</span>
            {/if}
          </button>
        {/each}
      </div>
    </div>

    {#if modell.kann_bearbeiten}
      <div class="ez-feld">
        <span class="ez-name">Stilvorlage<small>Begleitbilder, an deren Stil sich das Modell hält, bis {modell.vorlagen_max ?? 4}</small></span>
        {#if vorlagen.length}
          <div class="ez-vorlagen">
            {#each vorlagen as v (v.id)}
              <figure class="ez-vorlage"><img src={v.adresse} alt={v.name} />
                <button type="button" class="ez-weg" title="Vorlage entfernen" onclick={() => (vorlagen = vorlagen.filter((x) => x.id !== v.id))}><i class="fa-solid fa-xmark"></i></button></figure>
            {/each}
          </div>
        {/if}
        {#if vorlagen.length < (modell.vorlagen_max ?? 4)}
          <div class="ez-ablage" class:ueber role="region" aria-label="Stilvorlage ablegen"
               ondragover={(e) => { e.preventDefault(); ueber = true; }} ondragleave={() => (ueber = false)} ondrop={ablegen}>
            <i class="fa-solid fa-image"></i><span>Bild als Stilvorlage hierher ziehen</span>
            {#if onwaehlen}<button type="button" class="knopf klein" onclick={onwaehlen}><i class="fa-solid fa-images"></i>Aus dem ImageVault wählen</button>{/if}
          </div>
        {/if}
      </div>
    {/if}

    <div class="ez-feld">
      <span class="ez-name">Format<small>{modell.groessen ? `Kanten durch ${modell.groessen.raster}${modell.groessen.kante_min && modell.groessen.kante_max ? `, ${modell.groessen.kante_min} bis ${modell.groessen.kante_max} Pixel` : ""}` : "Vorgabe der Leitstelle, bis das Modell einmal lief"}</small></span>
      <div class="ez-formate">
        {#each formate(modell) as f (f.groesse)}
          {@const k = kachel(f.groesse)}
          {@const p = pixel(f.groesse)}
          <button type="button" class="ez-format" class:an={vorgeschlagen && f.groesse === wahl.groesse} onclick={() => { eigenOffen = false; wahl = { ...wahl, groesse: f.groesse, ende: null }; }}>
            <span class="ez-rahmen"><span style:width="{k.breite}px" style:height="{k.hoehe}px"></span></span>
            <span class="ez-format-text"><b>{f.name}</b><span>{p.b} × {p.h}{f.vorgabe ? ", Vorgabe" : ""}</span></span>
          </button>
        {/each}
        <button type="button" class="ez-format" class:an={!vorgeschlagen || eigenOffen} onclick={eigenOeffnen}>
          <span class="ez-rahmen eigen"><span style:width="{eigenKachel.breite}px" style:height="{eigenKachel.hoehe}px"></span></span>
          <span class="ez-format-text"><b>Eigenes Format</b><span>{vorgeschlagen ? "beliebige Maße" : lesbar(wahl.ende ?? wahl.groesse)}</span></span>
        </button>
      </div>
      {#if eigenOffen || !vorgeschlagen}
        <div class="ez-eigen">
          <div class="segment ez-eingabeart">
            <button type="button" class:aktiv={eingabe === "masse"} onclick={() => { eingabe = "masse"; eigenesFormat(); }}>Breite und Höhe</button>
            <button type="button" class:aktiv={eingabe === "verhaeltnis"} onclick={() => { eingabe = "verhaeltnis"; eigenesFormat(); }}>Seitenverhältnis und Größe</button>
          </div>
          {#if eingabe === "masse"}
            <div class="ez-masse">
              <label>Breite<input name="breite" type="number" inputmode="numeric" min="1" bind:value={breite} onchange={eigenesFormat} /></label>
              <span class="ez-mal">×</span>
              <label>Höhe<input name="hoehe" type="number" inputmode="numeric" min="1" bind:value={hoehe} onchange={eigenesFormat} /></label>
              <span class="ez-leise">Pixel, auch kleiner als das Modell rechnet (etwa 16 × 16)</span>
            </div>
          {:else}
            <div class="ez-masse">
              <label>Seitenverhältnis<input name="verhaeltnis" type="text" bind:value={verhaeltnis} placeholder="etwa 21:9, 3:2, 4:5" onchange={eigenesFormat} /></label>
              {#if flaeche}
                <label class="ez-groesse">Größe <span class="ez-wert-klein">{megapixel.toLocaleString("de-DE", { maximumFractionDigits: 2 })} Megapixel</span>
                  <input name="megapixel" type="range" min={flaeche.kleinste} max={flaeche.groesste} step="0.01" bind:value={megapixel} oninput={eigenesFormat} /></label>
              {/if}
            </div>
          {/if}
          {#if ungueltig}<div class="ez-ergebnis"><span class="ez-leise">Seitenverhältnis wie 21:9 angeben.</span></div>
          {:else if ergebnis}
            <div class="ez-ergebnis"><b>{ergebnis.hinweis}</b>
              {#if ergebnis.angepasst.length}<span class="ez-leise">{ergebnis.angepasst.join(", ")}</span>{/if}</div>
          {/if}
        </div>
      {/if}
    </div>

    <div class="ez-feld">
      {#if bereich}
        <span class="ez-name">Iterationstiefe<small>{bereich.kleinste} bis {bereich.groesste} Schritte, Vorgabe {bereich.vorgabe}</small></span>
        <div class="ez-regler">
          <input name="iterationstiefe" type="range" min={bereich.kleinste} max={bereich.groesste} value={wahl.schritte ?? bereich.vorgabe} aria-label="Iterationstiefe"
                 oninput={(e) => (wahl = { ...wahl, schritte: Number(e.currentTarget.value) })} />
          <span class="ez-wert">{wahl.schritte ?? bereich.vorgabe}</span>
        </div>
        <span class="ez-leise">Mehr Schritte: feinere Einzelheiten, längere Rechnung.</span>
      {:else}
        <span class="ez-name">Iterationstiefe</span>
        <div class="ez-fest"><i class="fa-solid fa-lock"></i><span>{fest ? `${fest} Schritte, mehr oder weniger nimmt das Modell nicht an.` : "Das Modell rechnet mit den Schritten seines Ablaufs."}</span></div>
      {/if}
    </div>

    {#if modell.anzahl_max > 1}
      <div class="ez-feld">
        <span class="ez-name">Varianten<small>gleiche Beschreibung, verschiedene Startwerte</small></span>
        <div class="ez-zahlen">
          {#each Array.from({ length: modell.anzahl_max }, (_, i) => i + 1) as n (n)}
            <button type="button" class="ez-zahl" class:an={n === wahl.anzahl} onclick={() => (wahl = { ...wahl, anzahl: n })}>{n}</button>
          {/each}
        </div>
      </div>
    {/if}

    {#if zeit}
      {#if zeit.gesamt_s !== null && zeit.je_bild_s !== null}
        <div class="ez-zeit"><i class="fa-regular fa-clock"></i><span class="ez-zeit-summe">etwa {dauerText(zeit.gesamt_s)}</span>
          <span class="ez-zeit-teile">
            {#if zeit.laden_s}<span>Laden des Modells etwa {dauerText(zeit.laden_s)}</span>{/if}
            <span>{wahl.anzahl} × {dauerText(zeit.je_bild_s)} je Variante ({pixel(wahl.groesse).mp.toFixed(2).replace(".", ",")} Megapixel{schritteJetzt ? `, ${schritteJetzt} Schritte` : ""})</span>
          </span>
          <span class="ez-leise">Geschätzt aus {modell.messung.laeufe} eigenen {modell.messung.laeufe === 1 ? "Lauf" : "Läufen"} dieses Modells.</span>
        </div>
      {:else}
        <div class="ez-zeit offen"><i class="fa-regular fa-clock"></i>
          <span><b>{zeit.je_bild_s === null ? "Rechenzeit noch ohne Messung." : `Je Variante etwa ${dauerText(zeit.je_bild_s)}.`}</b>
            {#if zeit.laden_s === null && !modell.geladen}Dazu kommt das Laden des Modells, dessen Dauer noch nicht gemessen ist. {/if}
            {#if zeit.je_bild_s === null}Die erste Erzeugung misst die Dauer; danach schätzt die Tafel mit dem Mittel der letzten Läufe je Megapixel und Schritt.{/if}</span>
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .ez-tafel { display: flex; flex-direction: column; gap: var(--a4); min-width: 0; }
  .ez-feld { display: flex; flex-direction: column; gap: var(--a2); min-width: 0; }
  .ez-name { font-weight: 600; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px var(--a2); }
  .ez-name small { font-weight: 400; font-size: var(--marke); color: var(--text-3); }
  .ez-leise { font-size: var(--marke); color: var(--text-3); }
  .ez-modelle { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--a2); }
  .ez-modell { display: flex; flex-direction: column; gap: 6px; text-align: left; padding: var(--a3); border: 0; border-radius: var(--r3); cursor: pointer;
               background: var(--flaeche); box-shadow: 0 0 0 1px var(--rand-stark); color: var(--text); font: inherit; min-width: 0; }
  .ez-modell.an { box-shadow: 0 0 0 2px var(--akzent-flaeche), var(--schatten); }
  .ez-modell-kopf { display: flex; flex-wrap: wrap; align-items: center; gap: var(--a2); }
  .ez-modell-kopf b { font-size: var(--gross); }
  .ez-kann { display: flex; flex-wrap: wrap; gap: 4px; }
  .ez-kann span { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: var(--r2); background: var(--flaeche-2); font-size: var(--marke); color: var(--text-2); }
  .ez-kann span.ja { background: var(--gut-weich); color: var(--gut); }
  .ez-lizenz { display: flex; gap: 6px; align-items: baseline; font-size: var(--marke); color: var(--text-2); }
  .ez-lizenz i { color: var(--text-3); }
  .ez-ablage { display: flex; flex-wrap: wrap; align-items: center; gap: var(--a3); padding: var(--a3) var(--a4); border-radius: var(--r3);
               border: 2px dashed var(--rand-stark); color: var(--text-2); font-size: var(--klein); }
  .ez-ablage.ueber { border-color: var(--akzent-flaeche); background: var(--akzent-weich); }
  .ez-ablage > i { font-size: var(--titel); color: var(--akzent); }
  .ez-ablage span { flex: 1; min-width: 160px; }
  .ez-vorlagen { display: flex; flex-wrap: wrap; gap: var(--a2); }
  .ez-vorlage { position: relative; margin: 0; width: 88px; height: 88px; border-radius: var(--r2); overflow: hidden; background: var(--flaeche-2); }
  .ez-vorlage img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .ez-weg { position: absolute; top: 4px; right: 4px; width: 24px; height: 24px; border: 0; border-radius: var(--r2); background: var(--flaeche); color: var(--text);
            cursor: pointer; display: grid; place-items: center; box-shadow: var(--schatten); }
  .ez-formate { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px; }
  .ez-format { display: flex; align-items: center; gap: var(--a2); padding: 8px 10px; border: 0; border-radius: var(--r2); cursor: pointer; text-align: left;
               background: var(--flaeche-2); color: var(--text); font: inherit; min-width: 0; }
  .ez-format.an { background: var(--akzent-weich); box-shadow: inset 0 0 0 2px var(--akzent-flaeche); }
  .ez-rahmen { width: 30px; height: 30px; flex: none; display: grid; place-items: center; }
  .ez-rahmen span { display: block; border-radius: 2px; box-shadow: inset 0 0 0 2px var(--text-2); }
  .ez-format.an .ez-rahmen span { box-shadow: inset 0 0 0 2px var(--akzent); }
  .ez-format-text { display: flex; flex-direction: column; min-width: 0; font-size: var(--klein); line-height: 1.3; }
  .ez-format-text span { color: var(--text-2); font-family: var(--schrift-zahl); font-size: var(--marke); }
  .ez-rahmen.eigen span { box-shadow: inset 0 0 0 2px var(--text-3); border: 0; }
  .ez-eigen { display: flex; flex-direction: column; gap: var(--a2); padding: var(--a3); border-radius: var(--r3); background: var(--flaeche-2); }
  .ez-eingabeart { align-self: flex-start; flex-wrap: wrap; max-width: 100%; }
  .ez-masse { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--a2) var(--a3); }
  .ez-masse label { display: flex; flex-direction: column; gap: 4px; font-size: var(--klein); color: var(--text-2); }
  .ez-masse input[type="number"], .ez-masse input[type="text"] { width: 130px; height: var(--knopf-hoehe); padding: 0 10px; border: 0; border-radius: var(--r2);
    background: var(--flaeche); box-shadow: inset 0 0 0 1px var(--rand-stark); font: inherit; font-size: var(--gross); color: var(--text); }
  .ez-masse input[type="number"] { font-family: var(--schrift-zahl); }
  .ez-mal { padding-bottom: 8px; color: var(--text-3); }
  .ez-groesse { flex: 1; min-width: 180px; }
  .ez-groesse input { width: 100%; accent-color: var(--akzent-flaeche); }
  .ez-wert-klein { font-family: var(--schrift-zahl); color: var(--text); }
  .ez-ergebnis { display: flex; flex-wrap: wrap; gap: 4px var(--a3); align-items: baseline; font-size: var(--klein); }
  .ez-ergebnis b { font-family: var(--schrift-zahl); }
  .ez-regler { display: flex; align-items: center; gap: var(--a3); }
  .ez-regler input { flex: 1; min-width: 0; accent-color: var(--akzent-flaeche); }
  .ez-wert { min-width: 3ch; text-align: right; font-family: var(--schrift-zahl); font-size: var(--titel); font-weight: 600; }
  .ez-fest { display: flex; gap: var(--a2); align-items: baseline; font-size: var(--klein); color: var(--text-2); }
  .ez-fest i { color: var(--text-3); }
  .ez-zahlen { display: flex; gap: 6px; }
  .ez-zahl { width: 44px; height: var(--knopf-hoehe); border: 0; border-radius: var(--r2); background: var(--flaeche-2); color: var(--text); font-family: var(--schrift-zahl);
             font-size: var(--gross); cursor: pointer; }
  .ez-zahl.an { background: var(--akzent-flaeche); color: var(--auf-akzent); font-weight: 600; }
  .ez-zeit { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px var(--a3); padding: var(--a3) var(--a4); border-radius: var(--r3); background: var(--akzent-weich); }
  .ez-zeit > i { color: var(--akzent); }
  .ez-zeit-summe { font-family: var(--schrift-zahl); font-size: var(--titel); font-weight: 600; }
  .ez-zeit-teile { display: flex; flex-wrap: wrap; gap: 4px var(--a3); font-size: var(--klein); color: var(--text-2); }
  .ez-zeit .ez-leise { flex-basis: 100%; }
  .ez-zeit.offen { background: var(--flaeche-2); color: var(--text-2); font-size: var(--klein); }
  .ez-zeit.offen > i { color: var(--text-3); }
  @media (max-width: 600px) {
    .ez-formate { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .ez-modelle { grid-template-columns: minmax(0, 1fr); }
  }
</style>
