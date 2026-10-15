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
