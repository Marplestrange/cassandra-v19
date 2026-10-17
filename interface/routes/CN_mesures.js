// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'historique (onglet « Historique ») : /api/mesures/* (V18) -> capacités mesures
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #5f78c4
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'historique (onglet « Historique ») : /api/mesures/* (V18) -> capacités mesures.* du noyau. Le module rend déjà les mots de l'écran (key, label, points, baseline…).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=5f78c4 ▼▼▼
/* L'historique (onglet « Historique ») : /api/mesures/* (V18) -> capacités mesures.* du noyau. Le module rend déjà les mots de l'écran (key, label, points, baseline…).
   Les marqueurs d'événements posés sur les courbes et l'impact des évolutions ne sont pas portés : l'écran les montre vides. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  P("/api/mesures/sources", "mesures.sources", { args: () => ({}), sortie: ok });
  P("/api/mesures/series", "mesures.serie", { args: (r) => ({ cle: r.body.key || "", periode: r.body.period || "24h", top: +(r.body.top || 6) }), sortie: ok });
  P("/api/mesures/profile", "mesures.profil", { args: (r) => ({ cle: r.body.key || "" }), sortie: ok });
  P("/api/mesures/deviations", "mesures.ecarts", { args: (r) => ({ seuil: +(r.body.threshold || 60) }), sortie: ok });
  P("/api/mesures/forecast", "mesures.prevision", { args: (r) => ({ cle: r.body.key || "disk" }), sortie: ok });
  P("/api/mesures/verdict", "mesures.verdict", { args: () => ({}), sortie: ok });
  P("/api/mesures/events", null, { faire: async () => ok({ events: [] }) });
  P("/api/mesures/evolutions", null, { faire: async () => ok({ evolutions: [] }) });
  P("/api/mesures/evolution", null, { faire: async () => ({ ok: false, reason: "l'impact des évolutions n'est pas porté dans cette version" }) });
  P("/api/mesures/tache", null, { faire: async () => ({ ok: false, reason: "la tâche de mesure du disque n'est pas portée dans cette version" }) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
