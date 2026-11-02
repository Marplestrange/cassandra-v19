// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Centre de notifications : /api/notifs, /api/notif/* (V18) -> capacités notifications
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #1ec270
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Centre de notifications : /api/notifs, /api/notif/* (V18) -> capacités notifications.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=1ec270 ▼▼▼
/* Centre de notifications : /api/notifs, /api/notif/* (V18) -> capacités notifications.* du noyau.
   Le noyau a le cœur (lire, vu, acquitter, résoudre, supprimer, compteurs) ; politique, sourdines, préférences et canaux ne sont pas encore portés. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const z = (n) => String(n).padStart(2, "0");
  const ts18 = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds()); };
  const item = (n) => Object.assign({}, n, { ts: ts18(n.ts), maj: ts18(n.maj), resolue_le: n.resolue_le ? ts18(n.resolue_le) : "", vu: !!n.lu, acquitte: !!n.acquittee, source_nom: n.source, couleur: "", aller: "", actions: [], rouvert: 0, sonde_vue: "" });
  const cpt = (c) => ({ total: c.ouvertes, critiques: c.critiques, non_vues: c.non_lues, a_decider: c.a_decider });

  P("/api/notifs", null, {
    faire: async (req, agir) => {
      const [l, c] = await Promise.all([agir("notifications.lister", { resolues: !!req.body.tout, limite: +(req.body.limit || 40) }), agir("notifications.compteurs", {})]);
      const k = cpt(c);
      return ok({ notifs: (l.notifications || []).map(item), vue: req.body.vue || "", compte: "", admin: true, compteurs: k, battement: {}, sources: {}, urgence: {}, actives: k.total, critiques: k.critiques, non_lues: k.non_vues });
    },
  });
  P("/api/notif/compteurs", "notifications.compteurs", { args: () => ({}), sortie: (c) => ok({ compteurs: cpt(c), battement: {} }) });
  const ids = (b) => (Array.isArray(b.ids) ? b.ids : b.id != null ? [b.id] : []).map(Number);
  const chaque = (cap, extra) => async (req, agir) => { let n = 0; for (const id of ids(req.body)) { await agir(cap, Object.assign({ id }, extra || {})); n++; } return ok({ vues: n, count: n }); };
  P("/api/notif/vu", null, { faire: chaque("notifications.vu") });
  P("/api/notif/lues", null, { faire: chaque("notifications.vu") });
  P("/api/notif/acquitter", null, { faire: chaque("notifications.acquitter") });
  P("/api/notif/resoudre", null, { faire: chaque("notifications.resoudre") });
  P("/api/notif/supprimer", null, { faire: chaque("notifications.supprimer") });

  // ── Les réglages : politique de canaux, heures calmes, sourdines, essai, webhook. Les canaux eux-mêmes n'envoient pas encore ; ce qui est réglé ici les attend.
  const wh = (w) => ({ enabled: !!w.declare, declare: !!w.declare, url: w.url || "", payload_template: w.modele || "", headers: {} });
  P("/api/notif/politique", null, {
    faire: async (req, agir) => {
      const b = req.body || {};
      if (b.set) {
        await agir("notifications.politique_ecrire", { niveau: String(b.niveau || ""), canaux: b.canaux || [], machine: !!b.machine });
        return ok({});
      }
      const r = await agir("notifications.politique", {});
      r.canaux.webhook = Object.assign({}, r.canaux.webhook, wh(r.canaux.webhook || {}));
      return ok(r);
    },
  });
  P("/api/notif/prefs", null, {
    faire: async (req, agir) => {
      const b = req.body || {}, a = {};
      for (const k of ["fuseau", "calmes", "calme_debut", "calme_fin"]) if (k in b) a[k] = b[k];
      await agir("notifications.prefs", a);
      return ok({ prefs: (await agir("notifications.politique", {})).prefs });
    },
  });
  P("/api/notif/sourdine", null, {
    faire: async (req, agir) => {
      const b = req.body || {};
      const r = await agir("notifications.sourdine", { portee: b.portee || "source", cible: String(b.cible || ""), heures: b.heures || 0 });
      return ok({ fin: r.fin ? new Date(r.fin * 1000).toISOString().slice(0, 19).replace("T", " ") : "", levee: r.levee });
    },
  });
  P("/api/notif/sourdines", null, { faire: async (req, agir) => ok({ sourdines: (await agir("notifications.politique", {})).sourdines }) });
  P("/api/notif/essai", null, {
    faire: async (req, agir) => {
      const r = await agir("notifications.essai", { canal: String((req.body || {}).canal || "cloche") });
      return { ok: !!r.ok, canal: r.canal, detail: r.detail, essai: true };
    },
  });
  P("/api/notif/webhook", null, {
    faire: async (req, agir) => {
      const b = req.body || {};
      if (b.set) {
        await agir("notifications.webhook_ecrire", { url: String(b.url || ""), actif: !!b.enabled, modele: String(b.payload_template || "") });
      }
      const w = (await agir("notifications.politique", {})).canaux.webhook || {};
      return ok({ webhook: wh(w) });
    },
  });
  P("/api/notif/sources", null, {
    faire: async (req, agir) => ok(Object.assign({ passe: { ts: "", sondes: 0, muettes: 0, fermees: 0, duree_ms: 0 }, sondes: {} }, await agir("notifications.sources", {}))),
  });
  // Pas de sondes à rejouer en V19 : un détecteur résout lui-même son constat, et la notification se referme avec lui.
  P("/api/notif/passe", null, { faire: async () => ok({ passe: { ts: "", sondes: 0, muettes: 0, fermees: 0, duree_ms: 0, note: "aucune sonde à rejouer : les détecteurs ferment eux-mêmes leurs constats" } }) });
  // Les actions d'une vignette (V18 : redémarrer un service, vider une corbeille…) ne sont pas attachées aux notifications V19.
  P("/api/notif/agir", null, { faire: async () => ({ ok: false, reason: "aucune action n'est attachée à cette notification en V19 : agis depuis l'écran du sujet" }) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
