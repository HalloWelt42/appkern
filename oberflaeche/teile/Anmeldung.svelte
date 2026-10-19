<script lang="ts">
  // Anmeldung mit dem Kellerwolke-Konto: Passwort oder Code vom Rechner (Kellerwolke, Einstellungen, Geräte).
  import { CODE_LAENGE, codeAusLinkNehmen, codeNormal, geraeteArt, namensvorschlag } from "../lib/kopplung";
  import { anmelden, koppeln, sitzung } from "../lib/sitzung.svelte";

  const ausLink = codeAusLinkNehmen();
  const app = $derived(sitzung.app!);
  let modus = $state<"passwort" | "code">(ausLink ? "code" : "passwort");
  let kennung = $state("");
  let passwort = $state("");
  let code = $state(ausLink);
  let name = $state(namensvorschlag());
  let fokus = $state(false);
  let fehler = $state("");
  let laeuft = $state(false);

  async function los(e: Event, arbeit: () => Promise<void>) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      await arbeit();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laeuft = false;
    }
  }
</script>

<div class="anmeldung" style="height:100vh; height:100dvh">
  {#if modus === "passwort"}
    <form class="anmelde-karte" onsubmit={(e) => los(e, () => anmelden(kennung, passwort))}>
      <div class="marke"><span class="symbol"><i class="fa-solid {app.symbol}"></i></span> {app.name}</div>
      <div class="rolle"><i class="fa-solid fa-wave-square"></i>{app.rolle}</div>
      <div class="hinweis-kw">
        <i class="fa-solid fa-cloud"></i>
        <span>Anmelden mit deinem Konto der Kellerwolke unter <b>{app.kellerwolke}</b>.{#if app.besitzer}{" "}Diese App gehört
          dem Konto <b>{app.besitzer}</b>.{/if}</span>
      </div>
      <label>Name oder Kürzel<span class="eingabe"><input bind:value={kennung} autocomplete="username" /></span></label>
      <label>Passwort<span class="eingabe"><input type="password" bind:value={passwort} autocomplete="current-password" /></span></label>
      {#if fehler}<div class="fehlerzeile">{fehler}</div>{/if}
      <button class="knopf primaer breit" type="submit" disabled={laeuft || !kennung || !passwort}>{laeuft ? "Anmelden ..." : "Anmelden"}</button>
      <div class="oder">oder</div>
      <button class="knopf zweit breit" type="button" onclick={() => ((modus = "code"), (fehler = ""))}>
        <i class="fa-solid fa-link"></i> Mit Code koppeln
      </button>
      <p class="fassung" style="text-align:center; margin:0">Den Code zeigt diese Kellerwolke unter Einstellungen, Geräte.</p>
    </form>
  {:else}
    <form class="anmelde-karte" onsubmit={(e) => los(e, () => koppeln(code, name.trim(), geraeteArt()))}>
      <div class="kopf-zeile">
        <button class="rund" type="button" title="Zurück zur Anmeldung" onclick={() => ((modus = "passwort"), (fehler = ""))}>
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <h1>Gerät koppeln</h1>
      </div>
      <p class="fassung" style="margin:0; font-size:var(--klein); color:var(--text-2)">
        Tipp den Code aus der Kellerwolke unter <b>{app.kellerwolke}</b> ein (dort Einstellungen, Geräte); ein Code aus
        einer anderen Kellerwolke gilt hier nicht. Danach bleibt dieses Gerät bei {app.name} angemeldet, bis du es
        trennst; ein Passwort wird hier nicht gespeichert.
      </p>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      <label class="code-feld">
        <span class="kaestchen" aria-hidden="true">
          {#each Array.from({ length: CODE_LAENGE }) as _, i (i)}
            {#if i === CODE_LAENGE / 2}<span class="luecke"></span>{/if}
            <span class="k" class:aktiv={fokus && i === Math.min(code.length, CODE_LAENGE - 1)}>{code[i] ?? ""}</span>
          {/each}
        </span>
        <input aria-label="Kopplungscode" value={code} autocomplete="one-time-code" autocapitalize="characters" spellcheck="false"
               oninput={(e) => { code = codeNormal(e.currentTarget.value); e.currentTarget.value = code; }}
               onfocus={() => (fokus = true)} onblur={() => (fokus = false)} />
      </label>
      <label>Name des Geräts<span class="eingabe"><input bind:value={name} maxlength="60" /></span></label>
      <button class="knopf primaer breit" type="submit" disabled={laeuft || code.length !== CODE_LAENGE || !name.trim()}>
        <i class="fa-solid fa-link"></i> {laeuft ? "Koppeln ..." : "Koppeln"}
      </button>
    </form>
  {/if}
</div>
