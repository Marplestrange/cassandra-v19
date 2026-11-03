// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Mon robot Telegram : /api/me/telegram/* (V18) -> capacités telegram.*
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #750744
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Mon robot Telegram : /api/me/telegram/* (V18) -> capacités telegram.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=750744 ▼▼▼
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

  // Les correspondants du robot qui n'ont pas encore de fiche : un pseudo, le dernier message, combien. La fiche ne naît que sur demande (adopter), avec la source « telegram ».
  P("/api/telegram/proposes", null, {
    faire: async (req, agir) => {
      const msgs = ((await agir("telegram.fil", { limite: 500 })) || {}).messages || [];
      const connus = new Set((((await agir("contacts.lister", { limite: 500 }).catch(() => ({}))) || {}).contacts || []).map((c) => String(c.display_name || "").trim().toLowerCase()));
      const par = {};
      for (const m of msgs) {
        const p = String(m.expediteur || "").trim();
        if (m.sens !== "recu" || !p || p === "?") continue;
        const x = par[p] || (par[p] = { pseudo: p, dernier: 0, messages: 0 });
        x.dernier = Math.max(x.dernier, +m.ts || 0);
        x.messages++;
      }
      const z = (n) => String(n).padStart(2, "0");
      const quand = (t) => { if (!t) return ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()); };
      const proposes = Object.values(par).filter((x) => !connus.has(x.pseudo.toLowerCase())).sort((a, b) => b.dernier - a.dernier).slice(0, 50)
        .map((x) => ({ pseudo: x.pseudo, dernier: quand(x.dernier), messages: x.messages }));
      return ok({ proposes });
    },
  });
  P("/api/telegram/adopter", null, {
    faire: async (req, agir) => {
      const p = String(req.body.pseudo || "").trim();
      if (!p) return { ok: false, error: "pseudo requis" };
      const r = await agir("contacts.creer", { display_name: p.slice(0, 120), notes: "Correspondant Telegram.", source: "telegram" });
      return ok({ id: r.id });
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
