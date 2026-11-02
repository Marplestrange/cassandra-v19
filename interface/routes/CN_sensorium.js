// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #e30d5c
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium.* du noyau (le collecteur d'une machine Linux).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=e30d5c ▼▼▼
/* Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium.* du noyau (le collecteur d'une machine Linux).
   Le collecteur rend déjà les noms de la V18 (cpu, ram, disk, load_1m…) ; la santé vient de sensorium.sante. */
(function () {
  CASS.route("GET", "/api/metrics", null, {
    faire: async (req, agir) => {
      const [m, s0] = await Promise.all([agir("sensorium.metriques", {}), agir("sensorium.sante", {}).catch(() => ({}))]);
      if (m && m.muet) return { muet: true, erreur: m.erreur || "" };      // source muette : aucune mesure, jamais des zéros
      const s = s0 || {};                                                  // la santé est absente tant que rien n'a été relevé
      return Object.assign({}, m, { health_score: s.score == null ? 0 : s.score, health_status: s.statut || "", failed_units: [], ssl_expiring: [], sites: [] });
    },
  });
  // Les gestes de l'onglet Sensorium (V18 : /api/sensorium/accepter|retirer|reparer|temoin) : les capacités du module les portent.
  CASS.route("POST", "/api/sensorium/accepter", "sensorium.accepter", { args: (r) => ({ wkey: String(r.body.wkey || ""), raison: String(r.body.raison || ""), jours: Number(r.body.jours) || 0 }), sortie: (x) => Object.assign({ ok: true }, x) });
  CASS.route("POST", "/api/sensorium/retirer", "sensorium.retirer_acceptation", { args: (r) => ({ wkey: String(r.body.wkey || "") }), sortie: (x) => Object.assign({ ok: true }, x) });
  CASS.route("POST", "/api/sensorium/reparer", "sensorium.reparer", { args: (r) => ({ wkey: String(r.body.wkey || ""), geste: String(r.body.geste || "") }), sortie: (x) => Object.assign({ ok: true }, x) });
  // Le témoin se pose à la main sur UNE AUTRE machine : la V19 ne s'y connecte pas d'ici, elle rend le dossier et dit où lire le script.
  CASS.route("POST", "/api/sensorium/temoin", null, {
    faire: async (req, agir) => {
      const t = await agir("sensorium.temoin", {});
      if (t && t.manque && t.manque.length) return { ok: false, erreur: "réglage manquant : " + t.manque.join(", ") };
      return { ok: false, erreur: "la V19 ne s'installe pas sur l'autre machine à ta place : pose le script et sa configuration dans " + (t.dossier || "~/.cassandra-temoin") + " (Sensorium › Témoin les donne), puis active l'unité." };
    },
  });
  CASS.route("GET", "/api/processes", null, { faire: async (req, agir) => { const m = await agir("sensorium.metriques", {}); return (m && !m.muet && m.top_processes) || []; } });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
