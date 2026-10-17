// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Mémoire : /api/memoire/* (V18, tout en POST) -> capacités memoire
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ae7d9e
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Mémoire : /api/memoire/* (V18, tout en POST) -> capacités memoire.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ae7d9e ▼▼▼
/* Mémoire : /api/memoire/* (V18, tout en POST) -> capacités memoire.* du noyau. */
(function () {
  const ok = (o) => Object.assign({ ok: true }, o);
  const P = (chemin, cap, opt) => CASS.route("POST", chemin, cap, opt);
  const G = (chemin, cap, opt) => CASS.route("GET", chemin, cap, opt);
  const lecture = (chemin, cap, opt) => { P(chemin, cap, opt); G(chemin, cap, opt); };

  lecture("/api/memoire/etat", "memoire.etat", { args: () => ({}), sortie: (r) => ok(Object.assign(r, { destinataires: ["partage"] })) });
  lecture("/api/memoire/liste", "memoire.lister", { args: (r) => ({ statut: r.body.statut || r.query.statut || "actif", categorie: r.body.categorie || r.query.categorie || null, limite: +(r.body.limite || r.query.limite || 200) }), sortie: ok });
  lecture("/api/memoire/chercher", "memoire.chercher", { args: (r) => ({ question: r.body.q || r.query.q || "", statut: r.body.statut || "actif", limite: +(r.body.limite || 40) }), sortie: ok });
  lecture("/api/memoire/fiche", "memoire.lire", { args: (r) => ({ id: +(r.body.id || r.query.id || 0) }), sortie: ok });
  lecture("/api/memoire/rappel", "memoire.rappeler", { args: (r) => ({ question: r.body.q || r.query.q || "" }) });
  lecture("/api/memoire/perception", "memoire.perception", { args: (r) => ({ question: r.body.q || "" }), sortie: (x) => ok({ bloc: typeof x === "string" ? x : (x && x.bloc) || "" }) });
  lecture("/api/memoire/doutes", "memoire.doutes", { args: (r) => ({ statut: r.body.statut || "ouvert" }), sortie: ok });
  lecture("/api/memoire/journal", "memoire.journal", { args: (r) => ({ limite: +(r.body.limite || 100), verbe: r.body.verbe || null }), sortie: (x) => ok({ lignes: x.journal || [] }) });
  lecture("/api/memoire/episodes", "memoire.episodes", { args: (r) => ({ limite: +(r.body.limite || 20) }), sortie: ok });
  lecture("/api/memoire/rappels", "memoire.rappels", { args: () => ({}), sortie: (x) => ok({ rappels: x.rappels || [], metriques: ["disk_pct", "ram_pct", "cpu_pct", "load1", "swap_pct"] }) });
  lecture("/api/memoire/moteurs", "memoire.moteurs", { args: () => ({}), sortie: ok });
  lecture("/api/memoire/chaine", "memoire.chaine_verifier", { args: () => ({}) });
  lecture("/api/memoire/export", "memoire.exporter", { args: () => ({}) });

  P("/api/memoire/doute/resoudre", "memoire.douter_resoudre", { args: (r) => ({ id: +r.body.id, choix: r.body.choix || "", note: r.body.note || "" }) });
  P("/api/memoire/rappel/poser", "memoire.rappel_poser", { args: (r) => ({ cle: r.body.cle || "", metrique: r.body.metrique || "", op: r.body.op || "", seuil: r.body.seuil, message: r.body.message || "" }) });
  P("/api/memoire/rappel/oter", "memoire.rappel_oter", { args: (r) => ({ id: +r.body.id }) });
  P("/api/memoire/don", "memoire.donner", { args: (r) => ({ id: +r.body.id, destinataire: r.body.destinataire || "", type_don: r.body.type || "don", jours: r.body.jours }) });
  P("/api/memoire/don/retirer", "memoire.don_retirer", { args: (r) => ({ copie_id: +r.body.id }) });

  // Les gestes : un seul point d'entrée V18, une capacité par geste côté noyau.
  const gestes = {
    oublier: ["memoire.oublier", (b) => ({ id: +b.id, raison: b.raison || "oubli sur ordre de l'utilisateur" })],
    restaurer: ["memoire.restaurer", (b) => ({ id: +b.id })],
    purger_secret: ["memoire.purger_secret", (b) => ({ id: +b.id })],
    corriger: ["memoire.corriger", (b) => ({ id: +b.id, valeur: b.valeur || "" })],
    epingler: ["memoire.forcer", (b) => ({ id: +b.id, force: b.force === false ? 0.0 : 1.0 })],
    ecrire: ["memoire.ecrire", (b) => ({ categorie: b.categorie || "fact", cle: String(b.cle || "").slice(0, 120), valeur: b.valeur || "", provenance: b.provenance || "dit", confiance: +(b.confiance || 0.9), declencheur: "manuel", nature: b.nature, sonde: b.sonde, sonde_args: b.sonde_args })],
  };
  P("/api/memoire/geste", (r) => (gestes[r.body.geste] || ["memoire.oublier"])[0], {
    args: (r) => { const g = gestes[r.body.geste]; return g ? g[1](r.body) : { id: -1 }; },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
