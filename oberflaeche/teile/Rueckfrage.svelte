<script lang="ts">
  // Rückfrage vor dem Löschen oder Verwerfen, im Ablauf statt als Fenster (nie ein Browser-Dialog). Mit `schalter` eine
  // zusätzliche Wahl (etwa: das Transkript dazu auch), ab Werk an.
  let {
    frage,
    hinweis = "",
    knopf,
    schalter = "",
    beschaeftigt = false,
    onabbrechen,
    onja,
  }: {
    frage: string;
    hinweis?: string;
    knopf: string;
    schalter?: string;
    beschaeftigt?: boolean;
    onabbrechen: () => void;
    onja: (mitSchalter: boolean) => void;
  } = $props();

  let an = $state(true);
</script>

<div class="rueckfrage" role="alertdialog" aria-label={frage}>
  <span class="frage">{frage}</span>
  {#if hinweis}<span>{hinweis}</span>{/if}
  {#if schalter}
    <label style="display:flex; align-items:center; gap:8px"><button class="schalter" class:an aria-label={schalter} aria-pressed={an}
           onclick={() => (an = !an)}></button>{schalter}</label>
  {/if}
  <span class="aktionen">
    <button class="knopf still" onclick={onabbrechen} disabled={beschaeftigt}>Abbrechen</button>
    <button class="knopf gefahr" onclick={() => onja(an)} disabled={beschaeftigt}>
      <i class="fa-solid {beschaeftigt ? 'fa-circle-notch fa-spin' : 'fa-trash-can'}"></i> {knopf}</button>
  </span>
</div>
