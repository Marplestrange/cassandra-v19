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
})();
