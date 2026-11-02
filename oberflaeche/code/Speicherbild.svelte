<script lang="ts">
  // Speicher nach einer Zeile (aus der Codeschmiede, WIKI-48): je Aufrufrahmen die Namen mit ihren Werten. Einfache
  // Werte als Kasten, Listen und Tupel als Fächerreihe mit Nummern, Wörterbücher als Schubladen, Objekte mit ihren
  // Attributen. Zeigen zwei Namen auf dasselbe Objekt, steht das dabei. Hervorgehoben ist, was sich in diesem Schritt
  // geändert hat. Im Debugger steht die innerste Funktion oben und ist hervorgehoben. In schmalen Spalten rücken
  // Namen und Fächer enger zusammen (Abfrage am Behälter, nicht am Gerät).
  import type { Schritt, Wert } from "./aufzeichnung";

  let { schritt, vorher = null, innenZuerst = false }: {
    schritt: Schritt | null;
    /** voriger Schritt: was sich seitdem geändert hat, leuchtet */
    vorher?: Schritt | null;
    /** innerste Funktion zuerst (Debugger) */
    innenZuerst?: boolean;
  } = $props();

  const rahmenFolge = $derived(schritt ? (innenZuerst ? [...schritt.rahmen].reverse() : schritt.rahmen) : []);

  function geaendert(rahmen: string, name: string, w: Wert): boolean {
    const alt = vorher?.rahmen.find((r) => r.name === rahmen)?.variablen[name];
    return !alt || alt.darstellung !== w.darstellung;
  }

  /** Namen, die auf dasselbe Objekt zeigen wie dieser (Verweis) */
  function teilen(name: string, w: Wert): string[] {
    if (w.kennung == null || !["liste", "tupel", "menge", "woerterbuch", "objekt"].includes(w.art)) return [];
    return (schritt?.rahmen ?? []).flatMap((r) => Object.entries(r.variablen).filter(([n, x]) => n !== name && x.kennung === w.kennung).map(([n]) => n));
  }

  /** Stelle in einer Liste, deren Inhalt der Wert eines einfachen Namens ist (etwa der Schleifenname) */
  function zeigtAuf(w: Wert): number {
    if (!schritt || !w.elemente) return -1;
    for (const r of schritt.rahmen) {
      for (const x of Object.values(r.variablen)) {
        if (x.art !== "text" && x.art !== "zahl") continue;
        const i = w.elemente.findIndex((e) => e.darstellung === x.darstellung);
        if (i >= 0) return i;
      }
    }
    return -1;
  }
</script>

<div class="speicher">
  <div class="titel"><span>Speicher</span>{#if schritt}<span>nach Zeile <b class="zahl">{schritt.zeile}</b></span>{/if}</div>
  {#if !schritt}
    <span class="leise">Noch nichts im Speicher.</span>
  {:else}
    {#each rahmenFolge as r, n (n)}
      {#if schritt.rahmen.length > 1}<div class="gruppe" class:innen={innenZuerst && n === 0}>{r.name === "Modul" ? "Hauptprogramm" : `in ${r.name}()`}</div>{/if}
      {#each Object.entries(r.variablen) as [name, w] (name)}
        {@const neu = geaendert(r.name, name, w)}
        {@const geteilt = teilen(name, w)}
        <div class="zeile">
          <span class="name">{name}</span>
          <div>
            {#if w.elemente && (w.art === "liste" || w.art === "tupel" || w.art === "menge")}
              {@const zeigt = zeigtAuf(w)}
              <div class="faecher" class:neu>
                {#each w.elemente as e, i (i)}
                  <div class="fach" class:zeigt={i === zeigt}><span>{e.darstellung}</span>{#if w.art !== "menge"}<small>{i}</small>{/if}</div>
                {/each}
                {#if w.elemente.length === 0}<span class="kasten leer">leer</span>{/if}
                {#if w.gekuerzt}<span class="leise">...</span>{/if}
              </div>
            {:else if w.paare}
              <div class="schubladen">
                {#each w.paare as [k, v] (k.darstellung)}
                  <div class="schublade"><span class="etikett">{k.darstellung}</span><span class="inhalt">{v.darstellung}</span></div>
                {/each}
                {#if w.paare.length === 0}<span class="kasten leer">leer</span>{/if}
              </div>
            {:else if w.attribute}
              <div class="objekt"><b>{w.darstellung}</b>
                {#each Object.entries(w.attribute) as [a, v] (a)}<span><span class="name">{a}</span> {v.darstellung}</span>{/each}
              </div>
            {:else}
              <span class="kasten" class:neu>{w.darstellung}</span>
            {/if}
            {#if geteilt.length}<small class="verweis"><i class="fa-solid fa-arrow-right-arrow-left" aria-hidden="true"></i> dasselbe wie {geteilt.join(", ")}</small>{/if}
          </div>
        </div>
      {/each}
    {/each}
    {#if schritt.rueckgabe}
      <div class="zeile"><span class="name">return</span><span class="kasten neu">{schritt.rueckgabe.darstellung}</span></div>
    {/if}
  {/if}
</div>

<style>
  .speicher { container-type: inline-size; border: 1px solid var(--rand); background: var(--flaeche); padding: var(--a3); display: flex; flex-direction: column; gap: var(--a3); font-family: var(--schrift); color: var(--text); }
  .titel { font-size: var(--marke); text-transform: uppercase; letter-spacing: .06em; color: var(--text-2); display: flex; justify-content: space-between; }
  .zahl { font-family: var(--schrift-zahl); font-variant-numeric: tabular-nums; }
  .leise { color: var(--text-2); font-size: var(--klein); }
  .gruppe { font-size: var(--marke); text-transform: uppercase; letter-spacing: .08em; color: var(--text-3); }
  .gruppe.innen { color: var(--akzent); }
  .zeile { display: grid; grid-template-columns: 82px minmax(0, 1fr); gap: var(--a2); align-items: center; }
  .name { font-family: var(--schrift-code); font-size: var(--klein); color: var(--ed-feld); text-align: right; overflow-wrap: anywhere; }

  .kasten { display: inline-flex; align-items: center; min-height: 36px; padding: 0 var(--a3); border: 2px solid var(--ed-speicher-wert); border-radius: var(--r3); background: color-mix(in srgb, var(--ed-speicher-wert) 12%, var(--flaeche)); font-family: var(--schrift-code); font-size: var(--gross); color: var(--text); transition: background var(--ruhig); overflow-wrap: anywhere; }
  .kasten.neu { background: color-mix(in srgb, var(--ed-geaendert) 30%, var(--flaeche)); border-color: var(--ed-geaendert); }
  .kasten.leer { border-style: dashed; color: var(--text-3); font-style: italic; font-family: var(--schrift); }

  .faecher { display: flex; gap: 0; flex-wrap: wrap; }
  .fach { display: flex; flex-direction: column; align-items: center; }
  .fach span { min-width: 64px; height: 36px; display: grid; place-items: center; padding: 0 var(--a2); border: 2px solid var(--ed-speicher-reihe); margin-left: -2px; background: color-mix(in srgb, var(--ed-speicher-reihe) 10%, var(--flaeche)); font-family: var(--schrift-code); font-size: var(--klein); }
  .fach:first-child span { margin-left: 0; border-radius: var(--r3) 0 0 var(--r3); }
  .fach:last-child span { border-radius: 0 var(--r3) var(--r3) 0; }
  .fach small { font-family: var(--schrift-zahl); font-size: var(--marke); color: var(--text-3); margin-top: 2px; }
  .fach.zeigt span { background: color-mix(in srgb, var(--ed-geaendert) 30%, var(--flaeche)); border-color: var(--ed-geaendert); position: relative; z-index: 1; }
  .fach.zeigt small { color: var(--ed-geaendert); }
  .faecher.neu .fach span { border-color: var(--ed-geaendert); }

  .schubladen { display: flex; flex-direction: column; gap: 3px; }
  .schublade { display: grid; grid-template-columns: auto minmax(0, 1fr); border: 2px solid var(--ed-speicher-reihe); border-radius: var(--r3); font-family: var(--schrift-code); font-size: var(--klein); }
  .schublade .etikett { padding: 2px var(--a2); background: color-mix(in srgb, var(--ed-speicher-reihe) 22%, var(--flaeche)); }
  .schublade .inhalt { padding: 2px var(--a2); overflow-wrap: anywhere; }
  .objekt { display: flex; flex-direction: column; gap: 2px; padding: var(--a1) var(--a2); border: 2px solid var(--ed-speicher-wert); border-radius: var(--r3); font-family: var(--schrift-code); font-size: var(--klein); }
  .verweis { display: block; margin-top: 2px; color: var(--text-2); font-size: var(--marke); }

  /* schmale Spalte (Debugger neben dem Editor, Telefon) */
  @container (max-width: 420px) {
    .zeile { grid-template-columns: 64px minmax(0, 1fr); }
    .fach span { min-width: 40px; }
  }
</style>
