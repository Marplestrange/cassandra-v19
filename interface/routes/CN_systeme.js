/* Le système : /api/health, /api/server_info (V18). */
(function () {
  // Le bandeau « le dialogue est désactivé » : vrai quand le rôle principal est lié à un modèle (sans session, on ne dit rien).
  CASS.route("GET", "/api/health", null, {
    faire: async (req, agir) => {
      const l = await agir("modeles.lister", {});
      const lie = !!(l.roles && l.roles.principal);
      return { ok: true, agent_pret: lie || (l.modeles || []).length > 0 || (l.locaux || []).length > 0 };
    },
  });
  // L'heure du serveur se lit sur l'en-tête Date de sa réponse ; le temps de marche n'est pas encore exposé par le noyau.
  CASS.route("GET", "/api/server_info", null, {
    faire: async (req) => {
      const r = await fetch("/api/moi", { headers: { "X-Session-Token": req.jeton } });
      const t = Date.parse(r.headers.get("Date") || "");
      return { ok: true, server_time: isNaN(t) ? Date.now() / 1000 : t / 1000, cassandra_uptime_secs: null, hostname: "", os: "", kernel: "", ip: "", cpu_cores: 0, uptime_secs: 0 };
    },
  });
})();
