// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #3fa857
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=3fa857 ▼▼▼
/* Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats.* du noyau.
   Différé : l'essai, l'accord, l'annulation et l'envoi réel (courrier). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/mandat/liste", "mandats.mandats", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/mandat/plan", "mandats.plan", { args: (r) => ({ mid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/mandat/save", "mandats.save", { args: (r) => r.body || {}, sortie: (x) => ok(x) });
  P("/api/mandat/delete", "mandats.delete", { args: (r) => ({ mid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/mandat/suspendre", "mandats.suspendre", {
    args: (r) => ({ mid: +r.body.id, motif: r.body.motif || "", reprendre: !!r.body.reprendre }),
    sortie: (x) => ok(x),
  });
  P("/api/mandat/envois", "mandats.envois", { args: (r) => ({ mid: +(r.body.id || 0), limite: +(r.body.limite || 100) }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
