// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les gestes d'urgence (la cloche et Sécurité › Confiner Cassandra) : /api/urgence/* (V18) -
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ee36c7
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les gestes d'urgence (la cloche et Sécurité › Confiner Cassandra) : /api/urgence/* (V18) -> capacités urgence.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ee36c7 ▼▼▼
/* Les gestes d'urgence (la cloche et Sécurité › Confiner Cassandra) : /api/urgence/* (V18) -> capacités urgence.* du noyau.
   Aucun n'est un outil d'agent. L'adresse de la session ne se lit JAMAIS ici : le noyau la prend sur la connexion (ip_session), quoi que l'écran envoie. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/urgence/etat", "urgence.etat", { args: () => ({}), sortie: (x) => x });
  P("/api/urgence/geler", "urgence.geler", { args: (r) => ({ actif: !!r.body.actif }), sortie: (x) => ok({ actif: x.actif }) });
  P("/api/urgence/envois", "urgence.couper_envois", { args: (r) => ({ actif: !!r.body.actif }), sortie: (x) => ok({ coupes: x.actif }) });
  P("/api/urgence/sessions", "urgence.sessions_revoquer", { args: (r) => ({ courant: r.jeton || "" }), sortie: (x) => ok({ revoquees: x.revoquees }) });
  P("/api/urgence/confiner", "urgence.confiner", {
    args: (r) => ({ niveau: +r.body.niveau, minutes: +(r.body.minutes || 30), mot: String(r.body.mot || ""), motif: String(r.body.motif || ""), courant: r.jeton || "" }),
    sortie: (x) => ok({ niveau: x.niveau, fin: x.fin, faites: x.faites, ip: x.ip }),
  });
  P("/api/urgence/lever", "urgence.lever", { args: () => ({}), sortie: (x) => ok({ defaits: x.defaits }) });
  P("/api/urgence/confirmer", "urgence.confirmer", { args: (r) => ({ minutes: +(r.body.minutes || 240) }), sortie: (x) => ok({ fin: x.fin }) });
  // Lever la crise : l'automatique d'abord (elle ne se lève jamais seule), sinon la crise du noyau.
  P("/api/urgence/crise-lever", null, {
    faire: async (req, agir) => {
      try { return ok(await agir("urgence.crise_auto_lever", { motif: String(req.body.motif || "") })); }
      catch (e) { if (!/aucune crise automatique/.test(e.message)) throw e; return ok(await agir("urgence.crise_lever", {})); }
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
