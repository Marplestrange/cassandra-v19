/* La voix : /api/voix/* -> capacités voix.* du noyau.
   Différé : l'écoute (transcription), la parole (synthèse) et le téléchargement des voix. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/voix/dispo", "voix.dispo", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/voix/catalogue", "voix.catalogue", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/voix/reglages", "voix.reglages", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/voix/choisir", "voix.choisir", {
    args: (r) => ({ voix_nom: r.body.voix_nom || "", voix_locuteur: r.body.voix_locuteur || "", voix_auto: r.body.voix_auto, voix_debit: r.body.voix_debit || "", voix_mode: r.body.voix_mode }),
    sortie: (x) => ok(x),
  });
})();
