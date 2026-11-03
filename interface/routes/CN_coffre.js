// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #6e265d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=6e265d ▼▼▼
/* Le coffre Vaultwarden : /api/vault/* (V18) -> capacités coffre.* du noyau.
   Mon coffre-fort (/api/vault/mine/*) : l'espace personnel du compte, ses fiches typées, son TOTP, son historique, son journal. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  const esp = (r) => ({ espace: r.body.espace || "" });          // vide : le coffre personnel de celui qui agit
  P("/api/vault/status", "coffre.status", { args: () => ({}), sortie: (x) => x });
  P("/api/vault/list", "coffre.list", { args: (r) => Object.assign({ prefix: r.body.prefix || "" }, esp(r)), sortie: (x) => ({ names: x.noms || [], secrets: x.secrets || [], espace: x.espace, role: x.role }) });
  P("/api/vault/get", "coffre.get", { args: (r) => Object.assign({ name: r.body.name || "" }, esp(r)), sortie: (x) => ({ ok: x.valeur !== null && x.valeur !== undefined, value: x.valeur }) });
  P("/api/vault/set", "coffre.set", { args: (r) => Object.assign({ name: r.body.name || "", valeur: r.body.value || "", collection: r.body.collection || "" }, esp(r)), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/delete", "coffre.delete", { args: (r) => Object.assign({ name: r.body.name || "" }, esp(r)), sortie: (x) => ok({ name: x.name }) });
  P("/api/vault/audit", "coffre.journal", { args: (r) => Object.assign({ limite: +(r.body.limite || 50) }, esp(r)), sortie: (x) => ok(x) });
  // les espaces : le sien, puis ceux de société où l'on est membre ; les accès d'un espace de société
  P("/api/vault/espaces", "coffre.espaces", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/vault/membres", "coffre.membres", { args: (r) => esp(r), sortie: (x) => ok(x) });
  P("/api/vault/accorder", "coffre.accorder", { args: (r) => ({ espace: r.body.espace || "", utilisateur: r.body.utilisateur || "", role: r.body.role || "membre", collections: r.body.collections === undefined ? null : r.body.collections, expire: r.body.expire || "" }), sortie: (x) => ok(x) });
  P("/api/vault/retirer", "coffre.retirer", { args: (r) => ({ espace: r.body.espace || "", utilisateur: r.body.utilisateur || "" }), sortie: (x) => ok(x) });
  // ── Mon coffre-fort : /api/vault/mine/* (V18, un coffre par personne) -> l'espace personnel du compte qui agit (u:<compte>), jamais celui d'un autre.
  const vue = (r) => { let f = {}; try { f = r.fiche ? JSON.parse(r.fiche) : {}; } catch (e) { f = {}; } return { name: r.nom, kind: f.kind || "note", username: f.username || "", uri: f.uri || "", favorite: !!f.favorite, revision: r.maj || "", creation: r.cree || "", agent: !!f.agent, totp: !!f.totp, champs: f.champs || 0, mdp_age: f.mdp_maj ? Math.max(0, Math.floor((Date.now() - Date.parse(f.mdp_maj)) / 86400000)) : null, doublon: false }; };
  const nom = (r) => String((r.body || {}).name || "").trim();
  const urlPublique = async (agir) => {
    const rg = ((await agir("reglages.lire", { module: "coffre" })) || {}).reglages || [];
    const x = rg.find((y) => y.cle === "coffre.url_publique");
    return (x && x.valeur) || "";
  };
  P("/api/vault/mine/status", null, {
    faire: async (req, agir) => {
      const s = await agir("coffre.status", {});
      const dispo = !!s.available && s.status === "unlocked";
      return { available: dispo, provisioned: dispo, account: (CASS.moi && CASS.moi.compte) || s.email || null, server_url: (await urlPublique(agir)) || s.server || "", etat: s.status || "", joignable: !!s.available, detail: String(s.error || "").slice(0, 200), cle_api: false, ouverture: "" };
    },
  });
  P("/api/vault/mine/list", null, {
    faire: async (req, agir) => {
      const r = await agir("coffre.list", {});
      const items = (r.secrets || []).map(vue);
      return { user: (CASS.moi && CASS.moi.compte) || "", items, names: items.map((x) => x.name), ok: true, error: null };
    },
  });
  P("/api/vault/mine/get", null, {
    faire: async (req, agir) => {
      const d = (await agir("coffre.fiche", { name: nom(req), motif: (req.body || {}).motif || "reveal" })).detail;
      return { ok: !!d, detail: d, value: d ? (d.kind === "note" ? d.value : d.password) : null };
    },
  });
  const existe = async (agir, n) => ((await agir("coffre.list", {})).noms || []).includes(n);
  P("/api/vault/mine/set", null, {
    faire: async (req, agir) => {
      const b = req.body || {}, n = nom(req), kind = String(b.kind || "note").toLowerCase();
      if (!n) return { ok: false, error: "nom requis" };
      if (kind === "login") {
        const v = { username: b.username || "", password: b.password || "", uri: b.uri || "", totp: b.totp || "" };
        if (await existe(agir, n)) await agir("coffre.fiche_ecrire", { name: n, patch: v });
        else await agir("coffre.fiche_ecrire", { name: n, kind: "login", valeurs: v, creer: true });
      } else await agir("coffre.set", { name: n, valeur: String(b.value || "") });
      return { ok: true, error: null };
    },
  });
  P("/api/vault/mine/creer", null, {
    faire: async (req, agir) => {
      const b = req.body || {};
      const r = await agir("coffre.fiche_ecrire", { name: nom(req), kind: String(b.kind || "login").toLowerCase(), valeurs: b.valeurs || {}, creer: true });
      return { ok: true, name: r.name };
    },
  });
  P("/api/vault/mine/update", null, {
    faire: async (req, agir) => {
      const r = await agir("coffre.fiche_ecrire", { name: nom(req), patch: (req.body || {}).patch || {} });
      return { ok: true, name: r.name };
    },
  });
  P("/api/vault/mine/delete", null, { faire: async (req, agir) => { await agir("coffre.delete", { name: nom(req) }); return { ok: true, error: null }; } });
  P("/api/vault/mine/totp", null, { faire: async (req, agir) => Object.assign({ ok: true }, await agir("coffre.totp", { name: nom(req) })) });
  P("/api/vault/mine/historique", null, { faire: async (req, agir) => Object.assign({ ok: true }, await agir("coffre.historique", { name: nom(req) })) });
  P("/api/vault/mine/trace", null, { faire: async (req, agir) => { await agir("coffre.trace", { name: nom(req), action: String((req.body || {}).action || "").toLowerCase() }); return { ok: true }; } });
  P("/api/vault/mine/audit", null, {
    faire: async (req, agir) => {
      const n = nom(req), j = (await agir("coffre.journal", { limite: n ? 400 : 60 })).journal || [];
      const ev = j.map((x) => ({ ts: x.ts, action: x.action, secret_name: x.secret_name }));
      return { events: n ? ev.filter((x) => x.secret_name === n || x.secret_name.startsWith(n + " ")).slice(0, 60) : ev };
    },
  });
  // Le coffre de chaque personne n'a plus de clé d'API propre : une seule session sert tous les espaces, et l'isolement est fait par le module.
  P("/api/vault/mine/cle_api", null, { faire: async () => ({ ok: false, error: "plus de clé d'API personnelle en V19 : le coffre s'ouvre par une session unique, isolée par espace" }) });
  P("/api/vault/mine/url", null, {
    faire: async (req, agir) => {
      const u = String((req.body || {}).url || "").trim();
      if (u && !/^https?:\/\//i.test(u)) return { ok: false, error: "l'adresse doit commencer par http:// ou https://" };
      await agir("reglages.regler", { cle: "coffre.url_publique", valeur: u });
      return { ok: true, url: u };
    },
  });
  P("/api/vault/mine/qr", null, {
    faire: async (req, agir) => {
      const u = (await urlPublique(agir)) || ((await agir("coffre.status", {})).server || "");
      if (!u) return { ok: false, error: "aucune adresse de coffre" };
      if (!(window.CASS && CASS.qr)) return { ok: false, error: "générateur de QR indisponible" };
      return { ok: true, svg: CASS.qr.svg(u, { taille: 160, marge: 2 }) };
    },
  });
  P("/api/vault/regler", "coffre.regler", { args: (r) => ({ espace: r.body.espace || "", mode: r.body.mode || "interne", url: r.body.url || "" }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
