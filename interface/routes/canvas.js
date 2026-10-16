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
