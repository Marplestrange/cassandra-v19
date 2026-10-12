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
