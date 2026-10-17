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
})();
