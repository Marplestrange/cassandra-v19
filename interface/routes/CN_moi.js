// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Mon compte : /api/me/* (V18) -> capacités comptes
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f6deee
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Mon compte : /api/me/* (V18) -> capacités comptes.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f6deee ▼▼▼
/* Mon compte : /api/me/* (V18) -> capacités comptes.* du noyau. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  P("/api/me", "comptes.moi", {
    args: () => ({}),
    sortie: (m) => ({ ok: true, user: m.compte, role: m.admin ? "admin" : "utilisateur", is_admin: !!m.admin, sites: m.sites || [], fp_account: m.fp_account || "", sites_herites: [],
      display_name: m.display_name || "", role_label: m.role_label || "", contact_email: m.contact_email || "", phone: m.phone || "", lang: m.lang || "fr", photo: !!m.fiche }),                                   // un humain peut avoir un portrait : /api/me/photo le dit (image propre, Dolibarr, FastPanel), sinon ses initiales
  });
  P("/api/me/photo", null, {                                                      // le portrait résolu : une adresse de données, ou rien (alors l'écran garde les initiales)
    faire: async (req, agir) => {
      if (req.body.retirer) { await agir("comptes.portrait_retirer", {}); return { ok: true }; }                  // retirer ou téléverser son image propre ; rien d'autre n'est écrit ici
      if (req.body.data) {
        const m = /^data:image\/[a-z+.-]+;base64,(.+)$/i.exec(String(req.body.data));
        if (!m) return { ok: false, error: "image illisible" };
        await agir("comptes.portrait_poser", { image: m[1] });
      }
      try {
        const p = (await agir("comptes.portrait", {})) || {};
        return p.present ? { ok: true, photo: "data:" + p.type + ";base64," + p.base64, source: p.source } : { ok: false };
      } catch (e) { return { ok: false }; }
    },
  });
  P("/api/me/deverrouiller", null, {                                                // l'écran de veille : le mot de passe de la session, confirmé par la passerelle
    faire: async (req) => {
      const r = await fetch("/api/confirmer", { method: "POST", body: JSON.stringify({ mot_de_passe: String(req.body.password || "") }) });
      return r.status === 200 ? { ok: true } : { ok: false, error: "Mot de passe incorrect." };
    },
  });
  P("/api/me/profile", "comptes.modifier_moi", { args: (r) => ({ display_name: r.body.display_name, role_label: r.body.role_label, contact_email: r.body.contact_email, phone: r.body.phone, lang: r.body.lang }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/password", "comptes.changer_mon_mot_de_passe", { args: (r) => ({ actuel: r.body.current, nouveau: r.body.new, courant: r.jeton }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions", "comptes.mes_sessions", { args: (r) => ({ courant: r.jeton }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions/revoke", "comptes.revoquer_session", { args: (r) => ({ court: r.body.id }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions/revoke_others", "comptes.revoquer_autres_sessions", { args: (r) => ({ courant: r.jeton }), sortie: (x) => Object.assign({ ok: true }, x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
