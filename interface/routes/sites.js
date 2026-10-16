/* Sites : /api/sites/* (V18) -> capacités sites.* du noyau. Le module garde les formes de la V18 (sites, vigilances, portée) :
   la lecture passe telle quelle ; les gestes rendent {ok, reason} comme l'écran les lit.
   /api/sites/act (redémarrer, vider le cache… un site, par FastPanel) attend le module fastpanel : il répond « pas encore porté ». */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const dom = (b) => String(b.domain || "").trim();

  // Le module parle français (domaine, code, ms, ssl_jours), l'écran V18 anglais (domain, http_code, response_ms, ssl_days).
  const SITE = { domaine: "domain", code: "http_code", ms: "response_ms", ssl_jours: "ssl_days", ssl_etat: "ssl_state", proprietaire_panneau: "fp_compte", mesure: "sonde_ts" };
  const site18 = (x) => { const o = CASS.cles(x, SITE); o.sonde = { up: x.up, http_code: x.code, response_ms: x.ms, ssl_days: o.ssl_days, ts: x.mesure }; return o; };
  P("/api/sites/mine", "sites.vue", { args: () => ({}), sortie: (x) => ok(Object.assign({}, x, { sites: (x.sites || []).map(site18), releve: new Date().toISOString().slice(0, 19).replace("T", " ") })) });
  P("/api/sites/declarer", "sites.declarer", { args: (r) => ({ domaine: dom(r.body) }), sortie: ok });
  P("/api/sites/retirer", "sites.retirer", { args: (r) => ({ domaine: dom(r.body) }), sortie: ok });
  P("/api/sites/attribuer", "sites.attribuer", { args: (r) => ({ domaine: dom(r.body), compte: String(r.body.compte || "").trim() }), sortie: ok });
  P("/api/sites/transferer", "sites.transferer", { args: (r) => ({ domaine: dom(r.body), vers: String(r.body.vers || "").trim() }), sortie: ok });
  P("/api/sites/demander", "sites.demander", { args: (r) => ({ domaine: dom(r.body), message: String(r.body.message || "") }), sortie: ok });
  P("/api/sites/demande/repondre", "sites.repondre_demande", { args: (r) => ({ id: +r.body.id, decision: String(r.body.decision || ""), reponse: String(r.body.reponse || "") }), sortie: ok });
})();
