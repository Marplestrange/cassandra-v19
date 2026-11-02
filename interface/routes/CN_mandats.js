// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f6a49f
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f6a49f ▼▼▼
/* Les mandats d'envoi : /api/mandat/* (V18) -> capacités mandats.* du noyau.
   L'accord fait trois gestes qui se suivent : autoriser l'envoi (mandats.accord), le faire poster par le courrier (courrier.envoyer_mandat, qui ne reçoit qu'un numéro),
   puis déclarer l'issue (mandats.sortie). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/mandat/liste", "mandats.mandats", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/mandat/plan", "mandats.plan", { args: (r) => ({ mid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/mandat/save", "mandats.save", { args: (r) => r.body || {}, sortie: (x) => ok(x) });
  P("/api/mandat/delete", "mandats.delete", { args: (r) => ({ mid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/mandat/suspendre", "mandats.suspendre", {
    args: (r) => ({ mid: +r.body.id, motif: r.body.motif || "", reprendre: !!r.body.reprendre }),
    sortie: (x) => ok(x),
  });
  P("/api/mandat/envois", "mandats.envois", {
    args: (r) => ({ mid: +(r.body.id || 0), limite: +(r.body.limit || r.body.limite || 100), etat: r.body.etat || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/mandat/essai", "mandats.essai", {
    args: (r) => ({ mandat: String(r.body.mandat || r.body.id || ""), contexte: r.body.ctx || {}, origine: "chat" }),
    sortie: (x) => ok(x),
  });
  P("/api/mandat/annuler", "mandats.annuler", { args: (r) => ({ envoi: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/mandat/accord", null, {
    faire: async (req, agir) => {
      if (!req.body.confirm) return { ok: false, reason: "confirmation requise" };
      const id = +req.body.id;
      const a = await agir("mandats.accord", { envoi: id });
      try {
        const p = await agir("courrier.envoyer_mandat", { envoi: id });
        const mid = (p && (p.message_id || (p.resultat && p.resultat.message_id))) || "";
        await agir("mandats.sortie", { envoi: id, message_id: mid });
        return { ok: true, to: a.a, message_id: mid };
      } catch (e) {
        const raison = (e && e.message) || "envoi impossible";
        try { await agir("mandats.sortie", { envoi: id, erreur: raison }); } catch (e2) {}
        return { ok: false, reason: raison };
      }
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
