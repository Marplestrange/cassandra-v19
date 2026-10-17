// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le système : /api/health, /api/server_info (V18)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #99238b
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le système : /api/health, /api/server_info (V18).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=99238b ▼▼▼
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
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
