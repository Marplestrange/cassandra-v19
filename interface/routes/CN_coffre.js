// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #a3129d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=a3129d ▼▼▼
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
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
