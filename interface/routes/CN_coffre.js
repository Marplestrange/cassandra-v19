// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #863e86
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=863e86 ▼▼▼
/* Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
   Différé : /api/vault/mine/* (le coffre personnel complet, chiffrement fin). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  const esp = (r) => ({ espace: r.body.espace || "" });          // vide : le coffre personnel de celui qui agit
  P("/api/vault/status", "coffre.status", { args: () => ({}), sortie: (x) => x });
  P("/api/vault/list", "coffre.list", { args: (r) => Object.assign({ prefix: r.body.prefix || "" }, esp(r)), sortie: (x) => ({ names: x.noms || [], secrets: x.secrets || [], espace: x.espace, role: x.role }) });
  P("/api/vault/get", "coffre.get", { args: (r) => Object.assign({ name: r.body.name || "" }, esp(r)), sortie: (x) => ({ ok: x.valeur !== null && x.valeur !== undefined, value: x.valeur }) });
  P("/api/vault/set", "coffre.set", { args: (r) => Object.assign({ name: r.body.name || "", valeur: r.body.value || "", collection: r.body.collection || "" }, esp(r)), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/delete", "coffre.delete", { args: (r) => Object.assign({ name: r.body.name || "" }, esp(r)), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/audit", "coffre.journal", { args: (r) => Object.assign({ limite: +(r.body.limite || 50) }, esp(r)), sortie: (x) => ok(x) });
  // les espaces : le sien, puis ceux de société où l'on est membre ; les accès d'un espace de société
  P("/api/vault/espaces", "coffre.espaces", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/vault/membres", "coffre.membres", { args: (r) => esp(r), sortie: (x) => ok(x) });
  P("/api/vault/accorder", "coffre.accorder", { args: (r) => ({ espace: r.body.espace || "", utilisateur: r.body.utilisateur || "", role: r.body.role || "membre", collections: r.body.collections === undefined ? null : r.body.collections, expire: r.body.expire || "" }), sortie: (x) => ok(x) });
  P("/api/vault/retirer", "coffre.retirer", { args: (r) => ({ espace: r.body.espace || "", utilisateur: r.body.utilisateur || "" }), sortie: (x) => ok(x) });
  P("/api/vault/regler", "coffre.regler", { args: (r) => ({ espace: r.body.espace || "", mode: r.body.mode || "interne", url: r.body.url || "" }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
