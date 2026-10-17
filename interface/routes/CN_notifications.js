// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Centre de notifications : /api/notifs, /api/notif/* (V18) -> capacités notifications
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d7e914
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Centre de notifications : /api/notifs, /api/notif/* (V18) -> capacités notifications.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d7e914 ▼▼▼
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
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
