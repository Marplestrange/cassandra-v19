/* Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
   Différé : /api/vault/mine/* (le coffre personnel complet, chiffrement fin). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/vault/status", "coffre.status", { args: () => ({}), sortie: (x) => x });
  P("/api/vault/list", "coffre.list", { args: (r) => ({ prefix: r.body.prefix || "" }), sortie: (x) => ({ names: x.noms || [] }) });
  P("/api/vault/get", "coffre.get", { args: (r) => ({ name: r.body.name || "" }), sortie: (x) => ({ ok: x.valeur !== null && x.valeur !== undefined, value: x.valeur }) });
  P("/api/vault/set", "coffre.set", { args: (r) => ({ name: r.body.name || "", valeur: r.body.value || "" }), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/delete", "coffre.delete", { args: (r) => ({ name: r.body.name || "" }), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/audit", "coffre.journal", { args: (r) => ({ limite: +(r.body.limite || 50) }), sortie: (x) => ok(x) });
})();
