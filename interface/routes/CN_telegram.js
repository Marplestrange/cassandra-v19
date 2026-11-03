// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Mon robot Telegram : /api/me/telegram/* (V18) -> capacités telegram.*
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f4da7a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Mon robot Telegram : /api/me/telegram/* (V18) -> capacités telegram.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f4da7a ▼▼▼
/* Mon robot Telegram : /api/me/telegram/* (V18) -> capacités telegram.* du noyau.
   Le jeton collé à l'écran part dans le réglage secret du compte (telegram.jeton) : il n'est jamais renvoyé, et c'est le module qui le lit.
   Le destinataire d'un envoi est celui du lien du compte : jamais celui de la requête. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const echec = (msg) => { const e = new Error(msg); e.statut = 400; return e; };

  P("/api/me/telegram", null, {
    faire: async (req, agir) => {
      const e = (await agir("telegram.etat", {})) || {};
      return ok({ robot: !!e.robot, lie: !!e.robot, nom_robot: e.nom_robot || "", chat_id: e.chat_id || "", actif: !!e.actif, depuis: e.depuis || "", dernier: e.dernier || "", messages: e.messages || 0,
                  cible: e.cible || "", destinataire: e.destinataire || "", origine: e.origine || "", propose: "", url: String(e.webhook || "").replace(/\/api\/public\/telegram\.recevoir$/, "") });
    },
  });
  P("/api/me/telegram/brancher", null, {
    faire: async (req, agir) => {
      const jeton = String(req.body.jeton || "").trim(), url = String(req.body.url || "").trim();
      if (jeton) await agir("reglages.regler_secret", { cle: "telegram.jeton", valeur: jeton });
      if (url) await agir("reglages.regler", { cle: "telegram.url_publique", valeur: url }).catch(() => {});        // un réglage de la société : un compte ordinaire ne le change pas
      return ok(await agir("telegram.brancher", {}));
    },
  });
  P("/api/me/telegram/detacher", "telegram.detacher", { args: () => ({}), sortie: ok });
  P("/api/me/telegram/fil", "telegram.fil", { args: (r) => ({ limite: +(r.body.limite || 100) }), sortie: ok });
  P("/api/me/telegram/cible", null, {
    faire: async (req, agir) => ok(await agir("telegram.cible_poser", { valeur: String(req.body.cible || "") })),
  });
  P("/api/me/telegram/envoyer", null, {
    faire: async (req, agir) => {
      const r = (await agir("telegram.envoyer", { texte: String(req.body.texte || "") })) || {};
      if (r.ok === false) throw echec(r.erreur || "envoi impossible");
      return ok(r);
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
