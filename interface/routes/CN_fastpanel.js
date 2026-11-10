// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'onglet Hébergement (V18 : /api/fp/*) -> capacités fastpanel
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #72a30a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'onglet Hébergement (V18 : /api/fp/*) -> capacités fastpanel.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=72a30a ▼▼▼
/* L'onglet Hébergement (V18 : /api/fp/*) -> capacités fastpanel.* du noyau.
   Le module parle français (domaine, proprietaire, quota_go…), l'écran V18 anglais (domain, user, disk_quota_gb…) : ce fichier traduit, il n'invente rien.
   Une source qui ne répond pas rend {ok:false, reason} — l'écran en fait « Source injoignable », pas une liste vide.
   Ce que le module ne porte pas (versions PHP, crons du panneau, analyses antivirus, statistiques du panneau, actions libres) répond vide ou « pas porté », et /api/modules dit
   à l'écran quelles sections ce panneau porte (capacités) : les autres s'affichent « non prises en charge ». */
(function () {
  const G = (c, o) => CASS.route("GET", c, null, o);
  const P = (c, o) => CASS.route("POST", c, null, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const echec = (e) => ({ ok: false, reason: (e && e.message) || String(e) });
  const lire = (cap, f) => ({ faire: async (req, agir) => { try { return f(await agir(cap, {}), req); } catch (e) { return echec(e); } } });
  const en = (x, ...cles) => cles.reduce((o, k) => (x[k] !== undefined ? Object.assign(o, { [k]: x[k] }) : o), {});

  // ── les listes ──────────────────────────────────────────────────────
  const ssl_actif = (s) => s && (s.etat === "actif" || s.etat === "proche");
  const domaine18 = (s) => ({
    domain: s.domaine, user: s.proprietaire, status: s.statut, php_version: s.php || "", php_handler: s.gestionnaire || "", php_source: "panneau",
    ssl_enabled: ssl_actif(s.ssl) ? 1 : 0, ssl_days_left: s.ssl ? s.ssl.jours : null, ssl_expiry: s.ssl ? s.ssl.echeance : "", ssl_source: "panneau", ssl_state: s.ssl ? s.ssl.etat : "",
    files_mb: s.fichiers_mo, db_mb: s.bases_mo, error_count: s.erreurs || 0, http_code: s.code_http,
  });
  G("/api/fp/domains", lire("fastpanel.sites", (x) => x.map(domaine18)));
  G("/api/fp/users", lire("fastpanel.utilisateurs", (x) => x.map((u) => ({ username: u.compte, email: u.courriel, roles: u.roles, ssh_access: u.ssh ? 1 : 0, sites_count: u.sites, databases_count: u.bases,
    disk_quota_gb: u.quota_go, status: u.statut, home_dir: u.dossier, created_at: u.cree }))));
  G("/api/fp/databases", lire("fastpanel.bases", (x) => x.map((b) => ({ id: b.id, name: b.nom, site: b.site, db_user: b.utilisateurs, size_mb: b.taille_mo, db_type: b.moteur, owner: b.proprietaire, dump_at: b.derniere_copie, charset: b.jeu, created_at: b.cree }))));
  G("/api/fp/mail", lire("fastpanel.mail", (x) => x.map((m) => ({ email: m.adresse, domain: m.domaine, quota_mb: m.quota_mo, used_mb: m.utilise_mo, status: m.statut }))));
  G("/api/fp/ftp", lire("fastpanel.ftp", (x) => x.map((f) => ({ login: f.compte, site: f.site, home_dir: f.dossier, owner: f.proprietaire, status: f.statut, created_at: f.cree }))));
  G("/api/fp/backups", lire("fastpanel.sauvegardes", (x) => x.map((s) => ({ type: s.plan, status: s.etat === "reussie" ? "success" : s.etat, size_mb: s.envoye_mo, source_mb: s.source_mo, duration: s.duree_min, files: s.fichiers,
    compte: s.compte, owner: s.proprietaire, bases: (s.bases || []).join(", "), destination: s.destination, created_at: s.debut, error: s.erreur, partial: s.partielle }))));
  G("/api/fp/dns", lire("fastpanel.dns", (x) => x.map((r) => ({ zone: r.zone, type: r.type, name: r.nom, value: r.valeur, ttl: r.ttl }))));
  G("/api/fp/services", lire("fastpanel.services", (x) => x.map((s) => ({ name: s.nom, status: s.etat, active: s.actif, version: "", alias: s.alias }))));
  // ce que le module ne porte pas : une liste vide et honnête (la section est d'ailleurs marquée « non prise en charge » par /api/modules)
  G("/api/fp/php", { faire: async () => [] });
  G("/api/fp/crons", { faire: async () => [] });
  G("/api/fp/scans", { faire: async () => [] });
  G("/api/fp/ssl", lire("fastpanel.sites", (x) => x.map(domaine18)));

  // ── le résumé : des comptes, sans rien inventer ───────────────────────
  G("/api/fp/summary", {
    faire: async (req, agir) => {
      const noms = ["utilisateurs", "sites", "bases", "mail", "ftp", "dns", "sauvegardes", "services"];
      const r = await Promise.allSettled(noms.map((n) => agir("fastpanel." + n, {})));
      const v = {}, manques = [];
      r.forEach((x, i) => { if (x.status === "fulfilled") v[noms[i]] = x.value; else manques.push(noms[i]); });
      if (manques.length === noms.length) return echec(new Error((r[0].reason && r[0].reason.message) || "le panneau ne répond pas"));
      const n = (k) => (v[k] || []).length;
      const copies = v.sauvegardes || [];
      return ok({
        users_count: n("utilisateurs"), domains_count: n("sites"), databases_count: n("bases"), mail_count: n("mail"), ftp_count: n("ftp"), dns_count: n("dns"), services_count: n("services"),
        services_down: (v.services || []).filter((s) => !s.actif).length, backups_count: copies.filter((c) => c.etat === "reussie").length, backups_failed: copies.filter((c) => c.etat !== "reussie").length,
        crons_count: 0, scans_count: 0, php_count: 0, source_erreur: manques.length ? "partielle : " + manques.join(", ") : "",
      });
    },
  });
  G("/api/fp/panel", {
    faire: async (req, agir) => {
      const rg = ((await agir("reglages.lire", { module: "fastpanel" })) || {}).reglages || [];
      const val = (c) => (rg.find((x) => x.cle === "fastpanel." + c) || {}).valeur || "";
      return ok({ url: val("base_panneau") || val("url") });
    },
  });

  // ── l'audit : ce qui demande un geste, dans les mots de l'écran ───────
  P("/api/fp/audit", lire("fastpanel.audit", (a) => {
    const c = a.certificats || {}, p = a.php || {}, b = a.sauvegardes || {};
    return ok({
      backups: { missing: b.sans || [], stale: (b.perimees || []).map((x) => ({ domain: x.domaine, last: x.derniere })), threshold_days: b.seuil_j, total: (c.total != null ? c.total : undefined), erreur: b.erreur },
      php: { eol: (p.fin_de_support || []).map((x) => ({ domain: x.domaine, php: x.php, eol: x.fin })), soon: (p.bientot || []).map((x) => ({ domain: x.domaine, php: x.php, eol: x.fin })),
             unknown: (p.version_non_lue || []).map((x) => ({ domain: x.domaine, source: x.gestionnaire })) },
      ssl: { missing: c.sans || [], expired: c.echus || [], soon: (c.proches || []).map((x) => ({ domain: x.domaine, days: x.jours, expiry: x.echeance })), inconnu: c.inconnus || [], total: c.total, ssl_active: c.actifs },
      renew: {},
    });
  }));
  P("/api/fp/actions", { faire: async () => ok({ actions: [], excluded: [] }) });                  // le catalogue d'actions libres de la V18 n'est pas porté : chaque geste a sa capacité
  G("/api/fp/stats/cpu", { faire: async () => ({ ok: false, reason: "les statistiques propres au panneau ne sont pas portées : voir Historique" }) });
  G("/api/fp/stats/la", { faire: async () => ({ ok: false, reason: "voir Historique" }) });
  G("/api/fp/stats/memory", { faire: async () => ({ ok: false, reason: "voir Historique" }) });
  G("/api/fp/stats/disk", { faire: async () => ({ ok: false, reason: "voir Historique" }) });

  // ── les gestes : la demande de confirmation de la V18 (409 needs_confirm) est gardée ──
  const exiger = (req, raison) => (req.body.confirm ? null : new Response(JSON.stringify({ ok: false, needs_confirm: true, reason: raison }), { status: 409, headers: { "Content-Type": "application/json" } }));
  P("/api/fp/service/action", {
    faire: async (req, agir) => {
      const nom = String(req.body.name || ""), a = String(req.body.action || "");
      if (["start", "restart", "stop"].indexOf(a) < 0) return { ok: false, reason: "action inconnue (start, restart, stop)" };
      const c = a === "stop" ? exiger(req, "Arrêter « " + nom + " » coupe ce qu'il sert (sites, bases, courrier) jusqu'au prochain démarrage.") : null;
      if (c) return c;
      try {
        const r = a === "stop" ? await agir("fastpanel.service_arreter", { service: nom }) : await agir("fastpanel.service_relancer", { service: nom, action: a });
        return ok({ output: a + " : " + nom, state: { state: a === "stop" ? "inactive" : "active", name: nom }, resultat: r });
      } catch (e) { return echec(e); }
    },
  });
  P("/api/fp/db/create", {
    faire: async (req, agir) => {
      const b = req.body, c = exiger(req, "Crée la base « " + (b.name || "") + " » avec son utilisateur dans le serveur de bases du panneau (le mot de passe n'est montré qu'une fois).");
      if (c) return c;
      try {
        const r = await agir("fastpanel.base_creer", { nom: String(b.name || ""), serveur_id: String(b.server_id || ""), utilisateur_id: String(b.user_id || ""), nouvel_utilisateur: String(b.new_user || ""), proprietaire_id: String(b.owner_id || "") });
        return ok({ output: "Base « " + r.nom + " » créée.", utilisateur: r.utilisateur, mot_de_passe: r.mot_de_passe });
      } catch (e) { return echec(e); }
    },
  });
  P("/api/fp/backup/storage/create", {
    faire: async (req, agir) => {
      const b = req.body, c = exiger(req, "Déclare le dossier « " + (b.path || "") + " » comme stockage de sauvegarde du panneau.");
      if (c) return c;
      try { const r = await agir("fastpanel.stockage_local_creer", { nom: String(b.name || ""), chemin: String(b.path || "") }); return ok({ output: "Stockage « " + (r.nom || b.name) + " » déclaré." }); }
      catch (e) { return echec(e); }
    },
  });
  P("/api/fp/backup/plan/create", {
    faire: async (req, agir) => {
      const b = req.body;
      if (!b.stockage) { try { const st = await agir("fastpanel.stockages", {}); if (!(st || []).length) return { ok: false, needs_storage: true, reason: "Déclarez d'abord un stockage de sauvegarde." }; } catch (e) { return echec(e); } }
      const c = exiger(req, "Crée le plan « " + (b.name || "") + " » : une copie, jour « " + (b.day || "*") + " » à " + (b.hour || "4") + " h, " + (b.garder || 7) + " copies gardées.");
      if (c) return c;
      try { const r = await agir("fastpanel.plan_creer", { nom: String(b.name || ""), stockage: String(b.stockage || ""), garder: +(b.garder || 7), heure: String(b.hour || "4"), jours: String(b.day || "*") }); return ok({ output: "Plan « " + (r.nom || b.name) + " » créé." }); }
      catch (e) { return echec(e); }
    },
  });
  P("/api/fp/backup/plans", {
    faire: async (req, agir) => {
      try {
        const [p, s] = await Promise.all([agir("fastpanel.plans", {}), agir("fastpanel.stockages", {}).catch(() => [])]);
        return ok({ plans: p || [], stockages: s || [] });
      } catch (e) { return echec(e); }
    },
  });
  P("/api/fp/ssl/check", {
    faire: async (req, agir) => {
      try {
        const r = await agir("fastpanel.ssl_sonder", { domaine: String(req.body.domain || "") });
        return r.ok ? ok({ days_left: r.jours, expiry: r.echeance, issuer: r.emetteur, names: r.noms || [], domain: r.domaine }) : { ok: false, reason: r.erreur || "aucun certificat exploitable" };
      } catch (e) { return echec(e); }
    },
  });
  P("/api/fp/ssl/issue", {
    faire: async (req, agir) => {
      const d = String(req.body.domain || ""), c = exiger(req, "Demande à l'autorité un nouveau certificat pour « " + d + " » (le quota hebdomadaire de Let's Encrypt s'applique).");
      if (c) return c;
      try { const r = await agir("fastpanel.ssl_renouveler", { domaine: d }); return ok({ output: "Certificat renouvelé pour " + (r.domaine || d) + "." }); }
      catch (e) { return echec(e); }
    },
  });

  // ── la suite de l'onglet (V18) : l'accès, le contexte d'un domaine, les bases, les clés SSH, les analyses ────
  const pas_porte = (raison) => ({ faire: async () => ({ ok: false, reason: raison }) });
  const dom = (r) => String(r.body.domain || "").trim().toLowerCase();
  // L'épreuve de l'accès : l'API répond-elle, la base du panneau se lit-elle. Les secrets ne repassent jamais dans la réponse.
  P("/api/fp/api/test", { faire: async (req, agir) => {
    try {
      const s = await agir("fastpanel.sante", {}), a = s.api || {}, b = s.base_panneau || {};
      if (a.ok) return ok({ endpoint: a.chemin, detail: "connexion établie sur " + a.chemin + " (" + a.elements + " élément(s)) ; base du panneau " + (b.ok ? "lue" : "illisible : " + (b.erreur || "?")) });
      return { ok: false, reason: a.erreur || "le panneau ne répond pas", attempts: a.essais || [] };
    } catch (e) { return echec(e); }
  } });
  // Les identifiants du panneau vont aux réglages (le jeton et le mot de passe sont des secrets : jamais relus, jamais renvoyés).
  P("/api/fp/api/creds", { faire: async (req, agir) => {
    const b = req.body, ou = [];
    try {
      if (String(b.token || "").trim()) { await agir("reglages.regler_secret", { cle: "fastpanel.jeton", valeur: String(b.token) }); ou.push("token → réglages (secret)"); }
      if (String(b.user || "").trim()) { await agir("reglages.regler", { cle: "fastpanel.utilisateur", valeur: String(b.user) }); ou.push("user → réglages"); }
      if (String(b.password || "")) { await agir("reglages.regler_secret", { cle: "fastpanel.mot_de_passe", valeur: String(b.password) }); ou.push("password → réglages (secret)"); }
      return ok({ ranges: ou });
    } catch (e) { return echec(e); }
  } });
  // Tout ce qu'on sait d'un domaine : sa ligne du panneau, sa fiche (liens, journal, accord).
  P("/api/fp/domain/context", { faire: async (req, agir) => {
    const d = dom(req);
    if (!d) return { ok: false, reason: "domaine requis" };
    let site = {}, fiche = null;
    try { site = (await agir("fastpanel.sites", {})).find((s) => String(s.domaine).toLowerCase() === d) || {}; } catch (e) {}
    try { fiche = await agir("sites.fiche", { domaine: d }); } catch (e) {}
    const liens = (fiche && fiche.liens) || [];
    const g = (k) => liens.filter((l) => l.genre === k || l.kind === k);
    return ok({ domain: d, site: site.domaine ? domaine18(site) : {}, project: g("project")[0] || g("projet")[0] || null, contacts: g("contact"), tasks: g("tache"), crons: [], notes: g("note"), machines: g("machine"), backups: [], journal: (fiche && fiche.journal) || [] });
  } });
  // Rattacher un domaine à un projet : c'est un lien de la fiche du site.
  P("/api/fp/domain/attach", { faire: async (req, agir) => {
    const b = req.body, d = dom(req);
    try {
      if (!d) return { ok: false, reason: "domaine requis" };
      const ref = String(b.project_id || b.project_name || "").trim();
      if (!ref) return { ok: false, reason: "projet requis" };
      await agir("sites.lier", { domaine: d, genre: "project", ref, note: String(b.note || "") });        // le genre que Sites connaît (« projet » était refusé : le rattachement échouait)
      return ok({ domain: d, project: ref });
    } catch (e) { return echec(e); }
  } });
  // Les bases : leurs utilisateurs viennent des lectures du panneau ; la suppression est un geste à part (élevé, sans retour).
  P("/api/fp/db/users", { faire: async (req, agir) => {
    try {
      const [b, u] = await Promise.all([agir("fastpanel.bases", {}), agir("fastpanel.utilisateurs", {})]);
      const vus = {}; (b || []).forEach((x) => String(x.utilisateurs || "").split(",").map((n) => n.trim()).filter(Boolean).forEach((n) => { vus[n] = (vus[n] || 0) + 1; }));
      return ok({ serveurs: [], utilisateurs: Object.keys(vus).map((n) => ({ login: n, bases: vus[n] })), comptes: (u || []).map((x) => ({ id: x.compte, username: x.compte })) });
    } catch (e) { return echec(e); }
  } });
  const exigerConfirm = (req, raison) => (req.body.confirm ? null : new Response(JSON.stringify({ ok: false, needs_confirm: true, reason: raison }), { status: 409, headers: { "Content-Type": "application/json" } }));
  P("/api/fp/db/delete", { faire: async (req, agir) => {
    const c = exigerConfirm(req, "SUPPRIME définitivement la base " + (req.body.id || "") + " et toutes ses données. Aucun retour possible sans sauvegarde.");
    if (c) return c;
    try { const r = await agir("fastpanel.base_supprimer", { id: +req.body.id || 0 }); return ok({ output: "Base « " + (r.nom || req.body.id) + " » supprimée." }); } catch (e) { return echec(e); }
  } });
  P("/api/fp/user/ssh", { faire: async (req, agir) => {
    try { const r = await agir("fastpanel.utilisateur_cles", { compte: String(req.body.username || "") }); return ok({ username: r.compte, keys: r.cles || [] }); } catch (e) { return echec(e); }
  } });
  // Le diagnostic d'un service : son état est celui que le panneau en dit ; le journal et la vérification de configuration demandent la racine.
  P("/api/fp/service/diagnose", { faire: async (req, agir) => {
    const nom = String(req.body.name || "").trim();
    try {
      const l = await agir("fastpanel.services", {}), s = (l || []).find((x) => x.nom === nom || x.alias === nom);
      if (!s) return { ok: false, reason: "service inconnu du panneau" };
      return ok({ service: nom, state: { name: s.nom, state: s.etat, active: s.actif }, config_check: {}, recent_errors: [], logs: "", reason: "le journal du service et la vérification de sa configuration ne sont pas lus d'ici : ils demandent une commande racine que le courtier n'a pas" });
    } catch (e) { return echec(e); }
  } });
  // Les analyses antivirus du panneau : la liste des sites vient de sa base ; lancer ou configurer une analyse (mogwai) et lire les rapports (fichiers de root) demandent la racine.
  P("/api/fp/scans/targets", { faire: async (req, agir) => {
    try {
      const r = await agir("fastpanel.scans_cibles", {});
      const sites = (r.sites || []).map((x) => ({ domain: x.domaine, site_id: x.site_id, config_id: x.config_id, enabled: x.actif, planning: x.planning, email: x.courriel, last_scan: x.dernier, reports: x.rapports }));
      return ok({ sites, unconfigured: sites.filter((x) => !x.config_id).map((x) => x.domain) });
    } catch (e) { return echec(e); }
  } });
  const RACINE = "Lancer, configurer ou relire une analyse du panneau demande la racine (la commande mogwai et les rapports sont à root) : le courtier de ce module n'a pas cette commande. La V19 lance l'analyse d'un serveur par « Sécurité › ClamAV » (securite.outil_lancer).";
  P("/api/fp/scans/run", pas_porte(RACINE));
  P("/api/fp/scans/configure", pas_porte(RACINE));
  P("/api/fp/scans/reports", { faire: async () => ok({ rapports: [], total: 0, racine: "", reason: RACINE }) });
  P("/api/fp/scans/report", pas_porte(RACINE));
  // Les actions libres de la V18 (mogwai) : la V19 les a remplacées par un geste nommé chacune, jamais une ligne de commande tapée.
  P("/api/fp/act", pas_porte("le catalogue d'actions libres de la V18 n'existe plus : chaque geste a sa capacité (services, SSL, bases, sauvegardes, pare-feu) et passe par la garde de l'administrateur"));
  P("/api/fp/websocket/apply", pas_porte("la modification de la configuration nginx du panneau (proxy WebSocket) demande la racine : le courtier de ce module n'a pas cette commande"));
  // La liaison d'un compte de l'application à un compte du panneau : le champ fp_account de sa fiche.
  P("/api/fp/users/link", { faire: async (req, agir) => {
    const b = req.body;
    try { await agir("comptes.modifier", { compte: String(b.user || ""), fp_account: String(b.fp_account || "").trim() }); return ok({ output: "Compte lié." }); } catch (e) { return echec(e); }
  } });
  P("/api/fp/stats", pas_porte("les statistiques propres au panneau ne sont pas portées : voir Historique"));
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
