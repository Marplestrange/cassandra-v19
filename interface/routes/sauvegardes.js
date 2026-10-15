/* Les sauvegardes : /api/sauv/* (V18) -> capacités sauvegardes.* du noyau.
   Différé : plan/run, purger, verifier, restaurer (rclone par le courtier). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/sauv/plans", "sauvegardes.plans", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/sauv/plan/save", "sauvegardes.plan_save", { args: (r) => r.body || {}, sortie: (x) => ok(x) });
  P("/api/sauv/plan/delete", "sauvegardes.plan_delete", { args: (r) => ({ pid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/sauv/historique", "sauvegardes.copies", { args: (r) => ({ plan_id: +(r.body.plan_id || r.body.id || 0) }), sortie: (x) => ok(x) });
  P("/api/sauv/destinations", "sauvegardes.destinations", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/sauv/couverture", "sauvegardes.couverture", { args: () => ({}), sortie: (x) => ok(x) });
})();
