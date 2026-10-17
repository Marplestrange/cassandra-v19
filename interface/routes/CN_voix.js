// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La voix : /api/voix/* -> capacités voix
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #3e5172
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La voix : /api/voix/* -> capacités voix.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=3e5172 ▼▼▼
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
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
