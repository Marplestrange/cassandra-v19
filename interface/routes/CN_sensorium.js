// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d6c98d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium.* du noyau (le collecteur d'une machine Linux).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d6c98d ▼▼▼
/* Sensorium : /api/metrics, /api/processes (V18) -> capacités sensorium.* du noyau (le collecteur d'une machine Linux).
   Le collecteur rend déjà les noms de la V18 (cpu, ram, disk, load_1m…) ; la santé vient de sensorium.sante. */
(function () {
  CASS.route("GET", "/api/metrics", null, {
    faire: async (req, agir) => {
      const [m, s] = await Promise.all([agir("sensorium.metriques", {}), agir("sensorium.sante", {}).catch(() => ({}))]);
      return Object.assign({}, m, { health_score: s.score == null ? 0 : s.score, health_status: s.statut || "", failed_units: [], ssl_expiring: [], sites: [] });
    },
  });
  CASS.route("GET", "/api/processes", null, { faire: async (req, agir) => (await agir("sensorium.metriques", {})).top_processes || [] });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
