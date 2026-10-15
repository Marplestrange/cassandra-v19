/* La sécurité : /api/securite/* (V18) -> capacités securite.* du noyau.
   Différé : l'état de la machine, direct/geste, le pare-feu FastPanel, les audits rédigés par le modèle. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/securite/gestes", "securite.gestes", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/securite/journal", "securite.journal", { args: (r) => ({ limite: +(r.body.limite || 120) }), sortie: (x) => ok(x) });
  P("/api/securite/audits", "securite.audits", { args: (r) => ({ id: +(r.body.id || 0) }), sortie: (x) => ok(x) });
  P("/api/securite/geste", "securite.noter", {
    args: (r) => ({ geste: r.body.geste || "", cible: r.body.cible || "", detail: r.body.detail || "", ok: r.body.ok !== false, resultat: r.body.resultat || "", defaire: r.body.defaire || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/securite/audit/poser", "securite.audit_poser", { args: (r) => ({ modele: r.body.modele || "", titre: r.body.titre || "", corps: r.body.corps || "" }), sortie: (x) => ok(x) });
})();
