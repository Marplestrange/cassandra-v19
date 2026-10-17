// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Aujourd'hui : /api/bureau/jour (V18) -> jour
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d0378b
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Aujourd'hui : /api/bureau/jour (V18) -> jour.aujourdhui, qui assemble les signaux déclarés par les modules.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d0378b ▼▼▼
/* Aujourd'hui : /api/bureau/jour (V18) -> jour.aujourdhui, qui assemble les signaux déclarés par les modules. */
(function () {
  CASS.route("POST", "/api/bureau/jour", "jour.aujourdhui", { args: () => ({}), sortie: (x) => Object.assign({ ok: true }, x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
