// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran Réglages de la V18 : ses lectures et ses écritures sur les modules V19 (comptes, m
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d25c47
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran Réglages de la V18 : ses lectures et ses écritures sur les modules V19 (comptes, modèles, courrier, webauthn, coffre, mémoire, proactif).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d25c47 ▼▼▼
/* L'écran Réglages de la V18 : ses lectures et ses écritures sur les modules V19 (comptes, modèles, courrier, webauthn, coffre, mémoire, proactif).
   Ce que la V18 rangeait dans UN config.json, la V19 le range par module (reglages.*) : cette table traduit, et dit « non porté » quand un réglage n'a
   pas (ou plus) d'équivalent, au lieu d'écrire dans le vide. Les réglages de chaque module sont aussi dans Réglages › Modules (modules-ui.js). */
(function () {
  const G = (c, cap, o) => CASS.route("GET", c, cap, o);
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const regle = (rg, cle) => { const x = (rg || []).find((y) => y.cle === cle); return x ? x.valeur : undefined; };
  const lireReg = async (agir, module) => ((await agir("reglages.lire", module ? { module } : {})) || {}).reglages || [];

  // ── Utilisateurs ────────────────────────────────────────────────────
  G("/api/users", null, {
    faire: async (req, agir) => {
      const l = ((await agir("comptes.lister", {})) || {}).comptes || [];
      const hum = l.filter((c) => c.type !== "systeme" && c.type !== "agent");
      return { users: hum.map((c) => c.compte).sort(), records: hum.map((c) => ({ email: c.compte, role: c.admin ? "admin" : "user", sites: c.sites || [], display_name: c.display_name || "", role_label: c.role_label || "" })) };
    },
  });
  P("/api/mdp/regles", "comptes.regles_mdp", { args: () => ({}), sortie: (x) => ok(x) });

  // ── Fournisseur et modèles (V18 : « provider / model / key » ; V19 : un registre de modèles liés à des rôles) ──
  G("/api/settings", null, {
    faire: async (req, agir) => {
      const [l, f] = await Promise.all([agir("modeles.lister", {}), agir("modeles.fournisseurs", {}).catch(() => ({}))]);
      const fourn = Array.isArray(f) ? f : f.fournisseurs || [];
      const modeles = l.modeles || [], roles = l.roles || {};
      const de = (role) => modeles.find((m) => m.id === roles[role]) || {};
      const p = de("principal"), s = de("itare_citadelle"), v = de("vision");
      return {
        provider: p.fournisseur || "", model: p.nom || "", base_url: p.base_url || "", key_set: !!p.cle_posee || !!p.cle, key_masked: p.cle_posee || p.cle ? "••••••••" : "",
        providers: fourn.map((x) => x.id || x), default_models: {}, itare_provider: s.fournisseur || "", itare_base_url: s.base_url || "", itare_model: s.nom || "",
        itare_citadelle_provider: s.fournisseur || "", itare_citadelle_base_url: s.base_url || "", itare_citadelle_model: s.nom || "",
        itare_vision_provider: v.fournisseur || "", itare_vision_model: v.nom || "", itare_vision_base_url: v.base_url || "", itare_vision_key_set: !!(v.cle_posee || v.cle), vision_key_set: !!(s.cle_posee || s.cle),
        secondary_providers: fourn.map((x) => x.id || x), secondary_default_models: {},
      };
    },
  });
  // Le modèle d'un compte (V18 : liste de modèles locaux + un choix) : le choix de modèle de la conversation, par le registre.
  P("/api/itare/modele", null, {
    faire: async (req, agir) => {
      const l = await agir("modeles.lister", {});
      if (req.body.modele !== undefined || req.body.fournisseur !== undefined) {
        const id = (l.modeles || []).find((m) => m.nom === req.body.modele || m.id === req.body.modele);
        await agir("modeles.choisir", { modele_id: id ? id.id : "" });
        return ok({});
      }
      const nom = (id) => ((l.modeles || []).find((m) => m.id === id) || {}).nom || "";
      return ok({ modeles: (l.modeles || []).map((m) => m.nom), modele: nom(l.choix), maison: nom((l.roles || {}).principal), distant: false });
    },
  });
  // L'état d'Ollama et des modèles locaux (le labo de la V18).
  P("/api/lab/status", null, {
    faire: async (req, agir) => {
      const l = await agir("modeles.lister", {});
      const loc = l.locaux || [];
      return ok({ ollama: loc.length > 0, models: loc.map((m) => (typeof m === "string" ? { name: m } : m)), resources: {}, model: "", pulling: {}, config: {} });
    },
  });
  P("/api/lab/history", null, { faire: async () => ok({ turns: [] }) });                           // l'historique du labo n'existe plus : la conversation d'Itare est dans le fil des agents

  // ── Mémoire et Proactivité : les clés V18 qui ont un équivalent V19 ──
  const CLES_MEMOIRE = { chatlab_persona: "agents.persona_itare" };
  P("/api/memory/config", null, {
    faire: async (req, agir) => {
      if (req.body.update) {
        const refus = [];
        for (const [k, v] of Object.entries(req.body.update)) {
          if (CLES_MEMOIRE[k]) await agir("reglages.regler", { cle: CLES_MEMOIRE[k], valeur: String(v || "") });
          else refus.push(k);
        }
        return refus.length ? { ok: false, error: "pas encore porté : " + refus.join(", ") } : ok({});
      }
      const rg = await lireReg(agir, "agents");
      return ok({ config: { chatlab_persona: regle(rg, "agents.persona_itare") || "", searxng_url: "", plex_url: "", plex_token_set: false } });
    },
  });
  P("/api/proactive/config", null, {
    faire: async (req, agir) => {
      if (req.body.update) return { ok: false, error: "la Proactivité se règle dans Proactivité › Autonomie (palier par domaine et par geste)" };
      const rg = await lireReg(agir, "proactif");
      return ok({ config: { proactive_paused: !!regle(rg, "proactif.pause") } });
    },
  });

  // ── Courrier : l'état du SMTP et de la boîte (par compte) ───────────
  const smtpDe = async (agir) => {
    const rg = await lireReg(agir, "courrier");
    return { smtp_host: regle(rg, "courrier.smtp_hote") || "", smtp_port: regle(rg, "courrier.smtp_port") || 587, smtp_user: regle(rg, "courrier.smtp_identifiant") || "", from_addr: regle(rg, "courrier.smtp_expediteur") || "" };
  };
  P("/api/mail/status", null, {
    faire: async (req, agir) => { const s = await smtpDe(agir); return ok({ configured: !!s.smtp_host, app_url: location.origin, weekly_recap: false, recap_day: 0, recap_hour: 8 }); },
  });
  P("/api/mail/smtp", null, {
    faire: async (req, agir) => {
      const b = req.body;
      if (b.save) {
        const poser = (cle, valeur) => agir("reglages.regler", { cle: "courrier." + cle, valeur });
        await poser("smtp_hote", String(b.smtp_host || "")); await poser("smtp_port", +(b.smtp_port || 587));
        await poser("smtp_identifiant", String(b.smtp_user || "")); await poser("smtp_expediteur", String(b.from_addr || ""));
        if (b.smtp_pass) await agir("reglages.regler_secret", { cle: "courrier.smtp_mot_de_passe", valeur: String(b.smtp_pass) });
        return ok({});
      }
      return Object.assign({ ok: true, to_addrs: "", smtp_tls: true, enabled: true }, await smtpDe(agir));
    },
  });

  // ── Mon compte : préférences, clés, coffre, activité ────────────────
  P("/api/me/email_pref", null, { faire: async (req) => ok({ enabled: false }) });
  P("/api/me/notifs", null, {
    faire: async (req, agir) => {
      const moi = (await agir("comptes.moi", {})) || {};
      const rg = await lireReg(agir, "courrier");
      return ok({ genres: {}, notifs: {}, destinataire: moi.contact_email || moi.compte || "", smtp: !!regle(rg, "courrier.smtp_hote") });
    },
  });
  P("/api/me/cles", null, {
    faire: async (req, agir) => { const e = (await agir("webauthn.etat", {})) || {}; return ok({ cles: e.cles || [], exigee: !!e.exigee, disponible: e.disponible !== false, erreur: e.erreur || "", secours: e.secours_restants || 0, secours_restants: e.secours_restants || 0 }); },
  });
  // L'enregistrement d'une clé de sécurité : défi -> navigateur -> enregistrer ; les codes de secours viennent avec la première clé exigée.
  P("/api/me/cle/defi", "webauthn.defi_creer", { args: () => ({}), sortie: (x) => ok({ defi: x.defi, rp: x.rp_id, compte: x.compte, exclure: x.exclure || [] }) });
  P("/api/me/cle/enregistrer", null, {
    faire: async (req, agir) => {
      const b = req.body;
      const r = await agir("webauthn.enregistrer", { defi: b.defi || "", client_data: b.client || "", attestation: b.attestation || "", libelle: b.libelle || "" });
      const e = (await agir("webauthn.etat", {})) || {};
      const sortie = ok({ id: r.id, libelle: r.libelle, cles: r.cles });
      if (!e.secours_restants && (r.cles || 1) === 1) { try { sortie.secours = (await agir("webauthn.secours_regenerer", {})).secours; } catch (x) {} }     // la première clé : les codes de secours, vus une fois
      return sortie;
    },
  });
  P("/api/me/cle/supprimer", "webauthn.supprimer", { args: (r) => ({ court: String(r.body.id || "") }), sortie: (x) => ok({ id: x.court }) });
  P("/api/me/cle/exiger", "webauthn.exiger", { args: (r) => ({ exiger: !!r.body.exiger }), sortie: (x) => ok({ exigee: x.exigee, secours: x.secours }) });
  P("/api/me/cle/secours", "webauthn.secours_regenerer", { args: () => ({}), sortie: (x) => ok({ codes: x.secours }) });
  P("/api/me/bitwarden", null, {
    faire: async (req, agir) => {
      try { const s = (await agir("coffre.status", {})) || {}; return ok({ server_url: s.url || s.server_url || "", email: s.email || "" }); }
      catch (e) { return { ok: false, error: e.message }; }
    },
  });
  P("/api/me/activity", null, {
    faire: async (req, agir) => {
      try {
        const m = (CASS.moi && CASS.moi.compte) || "";
        const x = (await agir("journal.flux_recent", { limite: 30 })) || {};
        const l = x.lignes || x.flux || x.evenements || [];
        return ok({ events: l.slice(0, 30).map((e) => ({ ts: e.ts || e.date || "", who: e.acteur && e.acteur !== "humain" ? "agent" : "user", action: e.action || e.type || "", detail: e.detail || e.resume || "" })), compte: m });
      } catch (e) { return ok({ events: [] }); }
    },
  });
  P("/api/fp/users/links", null, {
    faire: async (req, agir) => {
      const l = ((await agir("comptes.lister", {})) || {}).comptes || [];
      return ok({ comptes: l.filter((c) => c.type === "humain").map((c) => ({ email: c.compte, fp_account: c.fp_account || "", sites: c.sites || [], role: c.admin ? "admin" : "user" })), fp_users: [] });
    },
  });

  // ── Agenda distant, Telegram, canaux ────────────────────────────────
  P("/api/me/agenda", null, {
    faire: async (req, agir) => {
      const b = req.body;
      if (b.save || b.url !== undefined) {
        await agir("reglages.regler", { cle: "agenda.caldav_url", valeur: String(b.url || "") }).catch(() => {});
        await agir("reglages.regler", { cle: "agenda.caldav_identifiant", valeur: String(b.user || "") });
        if (b.password) await agir("reglages.regler_secret", { cle: "agenda.caldav_mot_de_passe", valeur: String(b.password) });
        return ok({});
      }
      const e = (await agir("agenda.caldav_etat", {})) || {};
      return ok({ url: e.url || "", user: e.identifiant || "", configuree: !!e.configuree });
    },
  });
  P("/api/me/telegram", null, { faire: async (req, agir) => ok((await agir("telegram.etat", {})) || {}) });
  P("/api/tgc/etat", null, {
    faire: async (req, agir) => { const e = (await agir("canaux.etat", {})) || {}; return ok({ dispo: !!e.client, relie: !!e.connecte, attente: false, identifiants: false, raison: e.detail || "", qui: "" }); },
  });

  // ── Ce qui n'a pas (encore) d'équivalent : une réponse VIDE et honnête, jamais un état inventé ──
  P("/api/ita/etat", null, { faire: async () => ({ ok: false }) });                                   // le compte Telegram d'Itare : voir Canaux
  G("/api/reglages/veille", null, { faire: async () => ok({ reglages: [] }) });                         // les interrupteurs de surveillance : portés par les détecteurs de chaque module
  P("/api/alerts/config", null, { faire: async () => ({ thresholds: {}, thresholds_defaut: {} }) });
  P("/api/system/sauvegardes", null, { faire: async () => ok({ depots: [], bases: [] }) });           // les dépôts de deploy.sh : propres à la V18
  P("/api/ged/montages", null, { faire: async () => ({ ok: true, montages: [] }) });
  P("/api/ged/diag", null, { faire: async () => ({ ok: false }) });
  P("/api/fp/websocket", null, { faire: async () => ({ ok: true, conforme: false, vhosts: [], reason: "La connexion poussée (WebSocket) n'est pas portée dans cette version : l'écran se met à jour par lecture." }) });
  P("/api/service/status", null, { faire: async () => ({ statuses: {} }) });                           // l'état des services système passera par le courtier (systemd), pas par l'écran
  P("/api/notif/politique", null, { faire: async () => ({ ok: false }) });
  P("/api/notif/sources", null, { faire: async () => ({ ok: false }) });

  // ── La santé des réglages et le verdict de chaque famille ───────────
  const NOMS = { "moi-identite": "Identité", "moi-boite": "Ma boîte mail", "moi-agenda": "Mon agenda", "moi-itare": "Mon Itare", "moi-alertes": "Ce que je reçois", "moi-securite": "Sécurité", users: "Utilisateurs", agents: "Agents IA", tiers: "Services tiers", veille: "Surveillances", systeme: "Système", maintenance: "Maintenance", donnees: "Données", canaux: "Canaux", danger: "Danger" };
  async function sante(agir) {
    const f = { agents: [], tiers: [], users: [], veille: [], systeme: [], maintenance: [], donnees: [], canaux: [] };
    const [m, rg, c] = await Promise.all([agir("modeles.lister", {}).catch(() => null), lireReg(agir, ""), agir("comptes.lister", {}).catch(() => null)]);
    if (m && !(m.modeles || []).length) f.agents.push("aucun modèle enregistré — l'agent ne peut pas répondre (Réglages › Modèles)");
    else if (m && !(m.roles || {}).principal) f.agents.push("aucun modèle lié au rôle principal");
    if (!regle(rg, "fastpanel.url") && !regle(rg, "fastpanel.base_panneau")) f.tiers.push("panneau d'hébergement non renseigné");
    if (c) { const sans = (c.comptes || []).filter((x) => x.type === "humain" && !x.admin && !(x.sites || []).length && !x.fp_account); if (sans.length) f.users.push(sans.length + " compte(s) sans aucun domaine"); }
    if (regle(rg, "proactif.pause")) f.systeme.push("proactivité en pause"); f.maintenance = f.systeme;
    return f;
  }
  G("/api/reglages/sante", null, {
    faire: async (req, agir) => {
      const f = await sante(agir), fam = {};
      let total = 0;
      for (const [k, l] of Object.entries(f)) { fam[k] = { alertes: l, etat: l.length ? (k === "veille" || k === "systeme" ? "info" : "warn") : "ok" }; total += l.length; }
      return ok({ familles: fam, total });
    },
  });
  G("/api/reglages/verdict", null, {
    faire: async (req, agir) => {
      const fam = req.query.famille || "", f = await sante(agir);
      const lignes = (f[fam] || []).map((a) => ({ niveau: "regarder", titre: a[0].toUpperCase() + a.slice(1), detail: "", gestes: [] }));
      return ok({ famille: fam, nom: NOMS[fam] || fam, lignes, titre: lignes.length ? NOMS[fam] || fam : "Tout est réglé ici.", resume: lignes.length ? lignes.length + " point(s) à regarder" : "Tout est réglé ici." });
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
