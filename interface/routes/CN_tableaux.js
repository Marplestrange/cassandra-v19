// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les tableaux d'ouverture des onglets V18 : chacun COMPOSE ce que l'écran lit à partir des 
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ccec1a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les tableaux d'ouverture des onglets V18 : chacun COMPOSE ce que l'écran lit à partir des capacités du module concerné.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ccec1a ▼▼▼
/* Les tableaux d'ouverture des onglets V18 : chacun COMPOSE ce que l'écran lit à partir des capacités du module concerné.
   Ce qui n'a pas d'équivalent dans la V19 (acquittements du Sensorium, réparations, relevé de flotte à la demande) n'est pas inventé : il manque, et l'écran le montre vide. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  // ── Proactivité : « Cette nuit » ────────────────────────────────────
  P("/api/pf/tableau", null, {
    faire: async (req, agir) => {
      const [inc, fil, aut] = await Promise.all([agir("proactif.incidents", {}).catch(() => ({})), agir("proactif.fil", { heures: 24, limit: 30 }).catch(() => ({})), agir("proactif.autonomie", {}).catch(() => ({}))]);
      return ok({ incidents: inc.incidents || [], attente: [], fil: (fil.fil || []).slice(0, 30), projections: [], autonomie: aut, faites: fil.par_elle || 0 });
    },
  });

  // ── La vue d'ensemble : composée côté serveur (module vue) ──
  P("/api/vue", "vue.ensemble", { args: () => ({}), sortie: (x) => x });

  // ── Sensorium : le modèle du monde, tel que le collecteur le rend ───
  const lignesDe = (m) => (Array.isArray(m) ? m : (m && (m.rows || m.monde || m.entites || m.lignes)) || []);
  P("/api/sensorium/etat", null, {
    faire: async (req, agir) => {
      const [m, c] = await Promise.all([agir("sensorium.monde", {}), agir("sensorium.changements", {}).catch(() => [])]);
      return ok({ source: "collecteur", rows: lignesDe(m), changes: Array.isArray(c) ? c : (c && (c.changes || c.changements)) || [], correlations: [], collecteur_erreur: "", maintenant: new Date().toISOString().slice(0, 19) + "Z" });
    },
  });
  P("/api/sensorium/historique", null, {
    faire: async (req, agir) => { const h = await agir("sensorium.historique", { cle: String(req.body.wkey || "") }); return ok(Array.isArray(h) ? { points: h } : h || {}); },
  });
  P("/api/sensorium/flotte", null, { faire: async (req, agir) => { await agir("flotte.parc", {}).catch(() => {}); return ok({ lance: true }); } });

  // L avatar du panneau : sans équivalent V19 pour l instant, l écran montre « aucune ».
  P("/api/fp/user/avatar", null, { faire: async () => ({ ok: false }) });

  // ── Le fil du compte Telegram d'Itare et ses cartes : rien à lire tant que le client Telegram n'est pas branché ──
  P("/api/tgc/fils", null, { faire: async () => ok({ turns: [], fils: [] }) });
  P("/api/ita/carte", null, { faire: async () => ok({ turns: [], carte: null }) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
