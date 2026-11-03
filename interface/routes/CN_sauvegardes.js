// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les sauvegardes : /api/sauv/* (V18) -> capacités sauvegardes
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #9104e4
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les sauvegardes : /api/sauv/* (V18) -> capacités sauvegardes.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=9104e4 ▼▼▼
/* Les sauvegardes : /api/sauv/* (V18) -> capacités sauvegardes.* du noyau.
   Purger, vérifier, restaurer : rclone par le courtier (commandes « purger », « lister », « copier »). */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/sauv/plans", "sauvegardes.plans", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/sauv/plan/save", "sauvegardes.plan_save", { args: (r) => r.body || {}, sortie: (x) => ok(x) });
  P("/api/sauv/plan/delete", "sauvegardes.plan_delete", { args: (r) => ({ pid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/sauv/historique", "sauvegardes.copies", { args: (r) => ({ plan_id: +(r.body.plan_id || r.body.id || 0) }), sortie: (x) => ok(x) });
  P("/api/sauv/destinations", "sauvegardes.destinations", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/sauv/couverture", "sauvegardes.couverture", { args: () => ({}), sortie: (x) => ok(x) });
  // Lancer un plan : à blanc pour essayer, sinon pour de bon (l'écran a demandé confirmation).
  P("/api/sauv/plan/run", "sauvegardes.plan_run", { args: (r) => ({ pid: +r.body.id, blanc: !!r.body.blanc }), sortie: (x) => ok(x) });

  // La rotation, la vérification, la restauration (rclone par le courtier). Restaurer écrase : à blanc par défaut, « à côté » par défaut, sur place avec accord.
  const confirmer = (req, raison) => (req.body.confirm ? null : new Response(JSON.stringify({ ok: false, needs_confirm: true, reason: raison, error: raison }), { status: 409, headers: { "Content-Type": "application/json" } }));
  const echec = (e) => ({ ok: false, reason: (e && e.message) || String(e), error: (e && e.message) || String(e) });
  P("/api/sauv/purger", null, { faire: async (req, agir) => {
    const c = confirmer(req, "Supprime de la destination les copies datées au-delà de celles que le plan garde.");
    if (c) return c;
    try { return ok(await agir("sauvegardes.purger", { pid: +req.body.id })); } catch (e) { return echec(e); }
  } });
  P("/api/sauv/verifier", null, { faire: async (req, agir) => { try { return ok(await agir("sauvegardes.verifier", { copie_id: +req.body.id })); } catch (e) { return echec(e); } } });
  P("/api/sauv/restaurer", null, { faire: async (req, agir) => {
    const b = req.body, blanc = b.blanc !== false, a_cote = b.a_cote !== false;
    if (!blanc && !a_cote) { const c = confirmer(req, "Restaurer SUR PLACE écrase l'original."); if (c) return c; }
    else if (!blanc && !b.confirm) { const c = confirmer(req, "Restaure la copie dans un dossier daté à côté de l'original."); if (c) return c; }
    try { return ok(await agir("sauvegardes.restaurer", { copie_id: +b.id, blanc, a_cote })); } catch (e) { return echec(e); }
  } });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
