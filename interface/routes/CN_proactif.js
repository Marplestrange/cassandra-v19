// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La Proactivité : /api/pf/* (V18) -> capacités proactif
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #04f37e
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La Proactivité : /api/pf/* (V18) -> capacités proactif.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=04f37e ▼▼▼
/* La Proactivité : /api/pf/* (V18) -> capacités proactif.* du noyau.
   Différé : tableau, projections, scans (métriques et la porte par domaine/geste). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/pf/autonomie", "proactif.autonomie", { args: () => ({}), sortie: (x) => x });
  P("/api/pf/autonomie/save", "proactif.autonomie_set", { args: (r) => r.body || {}, sortie: (x) => ok({ autonomie: x.autonomie }) });
  P("/api/pf/savoirs", "proactif.savoirs", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/pf/savoir/etat", "proactif.savoir_etat", { args: (r) => ({ signature: r.body.signature || "", etat: r.body.etat || "" }), sortie: (x) => ok(x) });
  P("/api/pf/savoir/accepter", "proactif.savoir_accepter", { args: (r) => ({ signature: r.body.signature || "" }), sortie: (x) => ok(x) });
  P("/api/pf/savoir/ecarter", "proactif.savoir_ecarter", { args: (r) => ({ signature: r.body.signature || "" }), sortie: (x) => ok(x) });
  P("/api/pf/ombre", "proactif.ombre", { args: (r) => ({ limit: +(r.body.limit || 40) }), sortie: (x) => ok(x) });
  P("/api/pf/ombre/avis", "proactif.ombre_avis", { args: (r) => ({ oid: +r.body.id, avis: r.body.avis || "" }), sortie: (x) => ok(x) });
  P("/api/pf/incidents", "proactif.incidents", { args: (r) => ({ limit: +(r.body.limit || 20), tout: !!r.body.tout }), sortie: (x) => ok(x) });
  P("/api/pf/fil", "proactif.fil", { args: (r) => ({ heures: +(r.body.heures || 24), limit: +(r.body.limit || 80) }), sortie: (x) => ok(x) });

  // L'autonomie par domaine et par geste (l'« automatisme ») : /api/autonomie/*
  P("/api/autonomie", null, {
    faire: async (req, agir) => {
      const [cat, reg, disj, gov] = await Promise.all([
        agir("proactif.catalogue", {}), agir("proactif.reglages", {}), agir("proactif.disjoncteurs", {}), agir("proactif.gouvernance", {}),
      ]);
      const pol = await agir("notifications.politique", {}).catch(() => null);            // le récit : par gravité, les canaux de la machine (la cloche reçoit toujours)
      const dec = (pol && pol.canaux) || {};
      return ok({ familles: cat.familles, statuts: cat.statuts, choix: cat.choix, defauts: cat.defauts,
                  reglages: reg.reglages, disjoncteurs: disj.disjoncteurs, gouvernance: gov,
                  recit: pol ? pol.machine : {}, canaux: { mail: !!(dec.mail && dec.mail.declare), telegram: !!(dec.telegram && dec.telegram.declare), webhook: !!(dec.webhook && dec.webhook.declare) } });
    },
  });
  P("/api/autonomie/recit", "notifications.politique_ecrire", { args: (r) => ({ niveau: r.body.niveau || "", canaux: r.body.canaux || [], machine: true }), sortie: (x) => ok({ recit: x.apres }) });
  P("/api/autonomie/regler", "proactif.regler", { args: (r) => ({ cle: r.body.cle || "", reglages: r.body.reglages || {} }), sortie: (x) => ok(x) });
  P("/api/autonomie/remettre", "proactif.remettre", { args: (r) => ({ cle: r.body.cle || "" }), sortie: (x) => ok(x) });
  P("/api/autonomie/debloquer", "proactif.debloquer", { args: (r) => ({ cle: r.body.cle || "" }), sortie: (x) => ok(x) });
  P("/api/autonomie/gouverner", "proactif.gouverner", { args: (r) => r.body.champs || r.body || {}, sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
