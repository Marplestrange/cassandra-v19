// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le canvas : /api/canvas/* -> capacités canvas
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #b1628d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le canvas : /api/canvas/* -> capacités canvas.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=b1628d ▼▼▼
/* Le canvas : /api/canvas/* -> capacités canvas.* du noyau.
   Différé : les appels au modèle (amorcer, retoucher, cartes des sources) et la section vivante. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/canvas/departs", "canvas.departs", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canvas/gestes", "canvas.gestes", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canvas/plan/lire", "canvas.plan_lire", { args: (r) => ({ ref: r.body.ref || "" }), sortie: (x) => ok(x) });
  P("/api/canvas/plan/ecrire", "canvas.plan_ecrire", { args: (r) => ({ ref: r.body.ref || "", plan: r.body.plan || {} }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
