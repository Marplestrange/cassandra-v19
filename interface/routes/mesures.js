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
