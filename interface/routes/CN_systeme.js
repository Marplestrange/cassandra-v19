// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le système : /api/health, /api/server_info (V18)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #25ccbc
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le système : /api/health, /api/server_info (V18).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=25ccbc ▼▼▼
/* Le système : /api/health, /api/server_info, les tableaux de la machine (ports, sessions, unités, OOM, Docker…), ses gestes, ses pièces jointes (V18). */
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

  // Les tableaux de l'onglet Système (V18 : /api/ports, /sessions, /failed, /oom, /docker, /ssl, /tailscale, /fail2ban, /remotes) : le collecteur du Sensorium les tient déjà
  // sous les mêmes noms d'entité. Un collecteur muet rend une liste vide (l'écran dit « Aucun… »), jamais des chiffres inventés ; la tuile du bandeau, elle, reste vide aussi.
  const entite = (nom, filtre) => ({
    faire: async (req, agir) => {
      try { const d = await agir("sensorium.entite", { nom }); const l = Array.isArray(d) ? d : []; return filtre ? l.filter(filtre) : l; }
      catch (e) { return []; }
    },
  });
  const PUCES = ["●", "•", "○", "*", "-", "✗", "x", "?"];
  CASS.route("GET", "/api/ports", null, entite("open_ports"));
  CASS.route("GET", "/api/sessions", null, entite("active_sessions"));
  CASS.route("GET", "/api/docker", null, entite("docker_containers"));
  CASS.route("GET", "/api/tailscale", null, entite("tailscale_peers"));
  CASS.route("GET", "/api/fail2ban", null, entite("fail2ban_banned_ips"));
  CASS.route("GET", "/api/remotes", null, entite("rclone_remotes"));
  CASS.route("GET", "/api/ssl", null, { faire: async (req, agir) => { const l = await entite("ssl_certificates").faire(req, agir); return l.filter((c) => (c.days_left || 0) > 0).sort((a, b) => a.days_left - b.days_left).slice(0, 20); } });
  CASS.route("GET", "/api/failed", null, entite("failed_units", (u) => u.active_state === "failed" && PUCES.indexOf(u.unit) < 0));
  CASS.route("GET", "/api/oom", null, { faire: async (req, agir) => {
    const l = await entite("oom_events").faire(req, agir), reconnus = await acquittes(agir);
    return l.filter((e) => { const p = String(e.killed_process || "").trim().toLowerCase(); return !((p === "" || p === "?" || p === "unknown") && !e.memory_used_mb) && reconnus.indexOf(e.ts + "_" + String(e.killed_process || "").trim()) < 0; });
  } });
  // Les OOM acquittés se retiennent par signature (date + processus), dans le module securite.
  async function acquittes(agir) {
    try { return ((await agir("securite.oom_acquits", {})) || {}).signatures || []; } catch (e) { return []; }
  }
  const garde = (cap, args, ok) => ({ faire: async (req, agir) => { try { const r = await agir(cap, args(req)); return ok(r, req); } catch (e) { return { success: false, ok: false, error: e.message, reason: e.message }; } } });
  CASS.route("POST", "/api/oom/clear", null, { faire: async (req, agir) => {
    try {
      const l = await entite("oom_events").faire(req, agir), deja = await acquittes(agir);
      const sigs = l.map((e) => e.ts + "_" + String(e.killed_process || "").trim()).filter((x) => deja.indexOf(x) < 0);
      if (sigs.length) await agir("securite.oom_acquitter", { signatures: sigs });
      return { ok: true, acquittes: sigs.length };
    } catch (e) { return { ok: false, error: e.message }; }
  } });
  CASS.route("POST", "/api/failed/reset", null, garde("securite.unites_reinitialiser", () => ({}), () => ({ ok: true, success: true })));
  CASS.route("POST", "/api/session/kill", null, garde("securite.session_fermer", (r) => ({ user: String(r.body.user || ""), ip: String(r.body.ip || "") }), (x) => ({ success: true, ok: true, killed: true, tty: x.tty })));

  // Le bandeau de santé : le score vient de la santé du collecteur, les comptes de ses entités. Source muette : rien d'inventé.
  CASS.route("GET", "/api/dashboard", null, {
    faire: async (req, agir) => {
      const n = async (nom, f) => { try { const d = await agir("sensorium.entite", { nom }); const l = Array.isArray(d) ? d : []; return (f ? l.filter(f) : l).length; } catch (e) { return 0; } };
      const [sites, remotes, ssl, bans, peers, oom, echecs, sante] = await Promise.all([
        n("web_sites", (s) => !s.status || s.status === "active"), n("rclone_remotes"), n("ssl_certificates", (c) => c.days_left > 0 && c.days_left <= 30), n("fail2ban_banned_ips"),
        n("tailscale_peers", (p) => p.online), n("oom_events"), n("failed_units", (u) => u.active_state === "failed" && PUCES.indexOf(u.unit) < 0), agir("sensorium.sante", {}).catch(() => ({})),
      ]);
      const s = sante || {};
      return { sites, remotes, ssl_expiring: ssl, fail2ban_banned: bans, tailscale_peers: peers, oom_events_24h: oom, failed_units: echecs, health_score: s.score == null ? 0 : s.score, health_status: s.statut || "unknown" };
    },
  });

  // ── Les gestes de la machine (V18 : /api/system/*, /api/service/restart/*) : une table fermée, chaque geste sa capacité (droit, preuve, retour). Jamais une commande tapée. ──
  const refus = (statut, corps) => new Response(JSON.stringify(corps), { status: statut, headers: { "Content-Type": "application/json" } });
  CASS.route("GET", "/api/system", null, { faire: async (req, agir) => { try { const m = await agir("sensorium.metriques", {}); return Object.assign({ ok: true }, m && !m.muet ? m : { muet: true, erreur: (m && m.erreur) || "" }); } catch (e) { return { ok: false, error: e.message }; } } });
  const GESTES = { ollama_restart: ["ollama", "restart"], nginx_reload: ["nginx", "reload"] };
  CASS.route("POST", "/api/system/geste", null, { faire: async (req, agir) => {
    const b = req.body, g = String(b.geste || "");
    try {
      if (GESTES[g]) { const r = await agir("securite.systeme_geste", { service: GESTES[g][0], action: GESTES[g][1] }); return { ok: true, unite: r.unite || "", detail: r.detail || "" }; }
      if (g === "journal") { const r = await agir("securite.journal_service", { service: String(b.service || "") }); return { ok: true, service: r.service, texte: r.texte || "" }; }
      if (g === "parasites") return { ok: true, fichiers: 0, retires: 0, detail: "sans objet en V19 : la V19 ne laisse pas de copies parasites de bases à côté de ses données" };
      if (g === "ollama_decharger") return { ok: false, error: "décharger les modèles d'Ollama n'est pas encore porté : Ollama se relance (ollama_restart), ce qui les décharge aussi" };
      return { ok: false, error: "geste inconnu" };
    } catch (e) { return { ok: false, error: e.message }; }
  } });
  // Le reset total efface tout l'état de la machine (bases, mémoire, pièces) : la V19 ne le porte pas comme un bouton. Le retrait propre est CN_desinstaller.sh, lancé à la main.
  CASS.route("POST", "/api/system/wipe", null, { faire: async () => refus(403, { ok: false, error: "le reset total n'existe pas en V19 : il effacerait bases, mémoire et pièces d'un seul geste. Le retrait propre est CN_desinstaller.sh, à lancer à la main sur la machine." }) });
  const COLLECTEUR = { faire: async (req, agir) => { try { const r = await agir("sensorium.redemarrer", { quand: "apres_passe", motif: "demandé depuis l'onglet Système" }); return { success: true, ok: true, output: "Collecteur redémarré (silence : " + (r.silence_s == null ? "?" : r.silence_s) + " s)" }; } catch (e) { return refus(500, { success: false, error: e.message }); } } };
  CASS.route("POST", "/api/service/restart/collector", null, COLLECTEUR);
  CASS.route("POST", "/api/service/restart/agent", null, { faire: async (req, agir) => { try { await agir("securite.systeme_geste", { service: "noyau", action: "restart" }); return { success: true, ok: true, message: "Redémarrage du noyau en cours. Vous allez être déconnecté." }; } catch (e) { return refus(500, { success: false, error: e.message }); } } });
  // La console libre (V18 : exécuter une commande, puis la défaire par instantané des fichiers) : la maison l'a ôtée. Les opérations root passent par le courtier, une commande nommée à la fois.
  const SANS_SHELL = "la console de commandes libres n'existe pas en V19 : chaque opération root passe par une commande nommée du courtier, avec sa preuve et son retour (voir les gestes de Système, Sécurité, Hébergement)";
  CASS.route("POST", "/api/exec", null, { faire: async () => refus(403, { success: false, ok: false, error: SANS_SHELL, output: "" }) });
  CASS.route("POST", "/api/exec/stream", null, { faire: async () => refus(403, { success: false, ok: false, error: SANS_SHELL }) });
  CASS.route("POST", "/api/rollback", null, { faire: async () => refus(400, { success: false, error: "aucun instantané de fichier à restaurer : la V19 ne lance pas de commande libre (donc n'en défait pas)" }) });

  // ── Les pièces jointes du dialogue : le texte se lit ici, une image part telle quelle à la vision ; le PDF et les formats bureautiques demandent un extracteur que la V19 n'a pas encore. ──
  const TEXTES = /\.(txt|md|markdown|csv|tsv|json|ya?ml|toml|ini|conf|cfg|log|xml|html?|css|js|ts|py|sh|sql|php|rb|go|rs|c|h|cpp|java|tex|rst)$/i;
  CASS.route("POST", "/api/upload", null, { faire: async (req) => {
    const b = req.body, nom = String(b.filename || "fichier.bin"), mime = String(b.mime || "application/octet-stream"), data = String(b.data || "");
    const limite = mime.indexOf("image/") === 0 ? 12 * 1024 * 1024 : 4 * 1024 * 1024;
    if (+b.size > limite) return { error: "Fichier trop grand (max " + Math.floor(limite / 1048576) + " Mo)" };
    if (mime.indexOf("image/") === 0) return { success: true, filename: nom, mime, size: b.size, method: "vision", truncated: false, image_b64: data, content_type: "image" };
    if (mime.indexOf("text/") === 0 || /json|xml|yaml|javascript|x-sh|sql/.test(mime) || TEXTES.test(nom)) {
      try {
        const oct = Uint8Array.from(atob(data), (c) => c.charCodeAt(0)), texte = new TextDecoder("utf-8", { fatal: false }).decode(oct), MAX = 120000;
        return { success: true, filename: nom, mime, size: b.size, method: "texte", truncated: texte.length > MAX, text: texte.slice(0, MAX), content_type: "text" };
      } catch (e) { return { error: "Données base64 invalides" }; }
    }
    return { success: false, error: "ce format (" + (mime || nom) + ") n'est pas encore lu : les PDF et documents bureautiques demandent un extracteur de texte que la V19 n'a pas encore ; texte brut et images passent" };
  } });

  // ── La proactivité en V19 n'a plus de « passage » : ses détecteurs tournent en continu dans le noyau. Le bouton lit donc la santé de chaque module à l'instant et en tire la note. ──
  const NOTES = [];
  CASS.route("POST", "/api/pf/scan", null, { faire: async (req, agir) => {
    const t0 = Date.now();
    try {
      const m = await agir("sensorium.modules", {});
      if (m && m.muet) return { ok: false, reason: "la santé des modules n'est pas encore relevée : " + (m.erreur || "pas encore relevée") };
      const brut = m.modules || [], mods = Array.isArray(brut) ? brut : Object.keys(brut).map((k) => Object.assign({ id: k }, brut[k] && typeof brut[k] === "object" ? brut[k] : { verdict: String(brut[k]) })), bons = mods.filter((x) => !x.verdict || x.verdict === "ok" || x.verdict === "sain"), autres = mods.filter((x) => bons.indexOf(x) < 0);
      const n = { ok: true, id: NOTES.length + 1, ts: new Date().toISOString().slice(0, 19).replace("T", " "), duree_ms: Date.now() - t0, declencheur: "manuel", vus: mods.length, muets: 0, trouves: autres.length, nouveaux: 0, resolus: 0, actions: 0,
        resume: mods.length + " module(s) relu(s), " + autres.length + " à regarder" + (autres.length ? " (" + autres.slice(0, 4).map((x) => x.id || x.nom).join(", ") + ")" : ""),
        detail: mods.map((x) => ({ cle: x.id || x.nom, nom: x.nom || x.id, etat: "vu", detail: String(x.verdict || "ok") })), diff: [] };
      NOTES.unshift(n);
      return n;
    } catch (e) { return { ok: false, reason: e.message }; }
  } });
  CASS.route("POST", "/api/pf/scans", null, { faire: async () => ({ ok: true, scans: NOTES.map((n) => ({ id: n.id, ts: n.ts, duree_ms: n.duree_ms, declencheur: n.declencheur, resume: n.resume, vus: n.vus, muets: n.muets, trouves: n.trouves, nouveaux: n.nouveaux, resolus: n.resolus, actions: n.actions })) }) });
  CASS.route("POST", "/api/pf/scan/note", null, { faire: async (req) => { const id = +req.body.id || 0, n = id ? NOTES.find((x) => x.id === id) : NOTES[0]; return n ? n : refus(404, { ok: false, reason: "aucune note de scan : lance un scan (les notes se gardent le temps de la page)" }); } });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
