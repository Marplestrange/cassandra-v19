// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Automatismes : /api/crons/* et /api/automatismes (V18) -> capacités planifie
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #500749
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Automatismes : /api/crons/* et /api/automatismes (V18) -> capacités planifie.* du noyau. Le noyau parle français (horaire, commande, actif…), l'écran V18 anglais.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=500749 ▼▼▼
/* Automatismes : /api/crons/* et /api/automatismes (V18) -> capacités planifie.* du noyau. Le noyau parle français (horaire, commande, actif…), l'écran V18 anglais. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const T = { utilisateur: "user", horaire: "schedule", commande: "command", actif: "enabled", derniere: "last_run", dernier_statut: "last_status", dernier_code: "last_exit", creee: "created_at",
    enrobee: "wrapped", cibles_manquantes: "missing_targets", humain: "human", prochaine: "next_run", attendue_avant: "expected_prev", projets: "projects", critique: "critical", etat: "state",
    etat_detail: "state_detail", a_historique: "has_history" };
  const z = (n) => String(n).padStart(2, "0");
  const ts = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()); };
  const tache18 = (j) => {
    const x = CASS.cles(j, T);
    x.natural_id = j.id == null ? null : j.id;
    x.created_at = ts(j.creee);
    x.projects = (j.projets || []).map((p) => ({ id: p.id, name: p.nom }));
    return x;
  };
  const run18 = (r) => ({ started_at: r.debut, duration_ms: r.duree_ms, exit_code: r.code, output: r.sortie, trigger: r.declencheur });
  const reg18 = (r) => Object.assign({}, r);
  const refuse = (e) => (/confirmer_destructeur/.test(e.message) ? Object.assign(e, { statut: 409 }) : e);

  P("/api/crons/unified", "planifie.unifiee", {
    args: () => ({}),
    sortie: (x) => ({ success: true, ok: true, jobs: (x.taches || []).map(tache18), counts: x.compteurs, projects: (x.projets || []).map((p) => ({ id: p.id, name: p.nom })), source_systeme: x.source_systeme }),
  });
  P("/api/crons/check", null, { faire: async (req, agir) => { const x = await agir("planifie.unifiee", { forcer: true }); return ok({ signales: (x.taches || []).filter((j) => ["cassé", "échec", "muet"].indexOf(j.etat) >= 0).length }); } });
  P("/api/crons/link", "planifie.lier", { args: (r) => ({ ref: String(r.body.ref || ""), projet_id: +r.body.project_id, libelle: String(r.body.label || "") }), sortie: ok });
  P("/api/crons/unlink", "planifie.delier", { args: (r) => ({ ref: String(r.body.ref || ""), projet_id: +r.body.project_id }), sortie: ok });
  // Enregistrer : une commande destructrice sans accord rend 409 « needs_confirm », comme en V18.
  P("/api/crons/save", null, {
    faire: async (req, agir) => {
      const b = req.body;
      try {
        const r = await agir("planifie.sauver", { description: b.description || "", horaire: b.cron_expr || "", commande: b.command || "", id: b.id || undefined, actif: b.enabled !== false,
          projet_id: b.project_id || undefined, confirmer_destructeur: !!b.confirm_risky, enrobee: b.wrapped !== false });
        return ok({ id: r.id, ref: r.ref, expr: r.horaire, command: r.commande, enabled: r.actif, wrapped: r.enrobee, next: r.prochaines });
      } catch (e) {
        if (/confirmer_destructeur/.test(e.message)) return new Response(JSON.stringify({ ok: false, needs_confirm: true, reason: e.message.replace(/ : confirmer_destructeur.*$/, ""), command: b.command || "" }), { status: 409, headers: { "Content-Type": "application/json" } });
        throw e;
      }
    },
  });
  P("/api/crons/toggle", "planifie.basculer", { args: (r) => ({ id: +r.body.id, actif: r.body.enabled !== false }), sortie: (x) => ok({ enabled: !!x.actif }) });
  P("/api/crons/delete", "planifie.supprimer", { args: (r) => ({ id: +r.body.id }), sortie: ok });
  const lancement = (x) => ok({ exit_code: x.code, duration_ms: x.duree_ms, output: x.sortie, started_at: x.debut, command: x.commande, essai: x.essai, fenetre_depassee: x.fenetre_depassee });
  P("/api/crons/run", "planifie.executer", { args: (r) => ({ id: r.body.id || undefined, ref: String(r.body.ref || "") }), sortie: lancement });
  P("/api/crons/essai", "planifie.executer", { args: (r) => ({ ref: String(r.body.ref || ""), essai: true, delai: +(r.body.timeout || 120) }), sortie: lancement });
  P("/api/crons/history", "planifie.historique", { args: (r) => ({ ref: String(r.body.ref || ""), limite: +(r.body.limit || 20) }), sortie: (x) => ok({ runs: (x.executions || []).map(run18) }) });
  P("/api/crons/critical", "planifie.critique", { args: (r) => ({ ref: String(r.body.ref || ""), critique: r.body.critical !== false, libelle: r.body.label || "" }), sortie: (x) => ok({ critical: x.critique }) });
  P("/api/crons/fiche", "planifie.fiche", {
    args: (r) => ({ ref: String(r.body.ref || "") }),
    sortie: (f) => ok({ job: tache18(f.tache), runs: (f.executions || []).map(run18), reglages: reg18(f.reglages), prochaines: f.prochaines, cibles: f.cibles,
      derive: f.derive && Object.keys(f.derive).length ? { ref: f.tache.ref, avant_ms: f.derive.avant_ms, apres_ms: f.derive.apres_ms, facteur: f.derive.facteur, mesures: f.derive.mesures } : {},
      modifs: f.modifs, duree_moyenne_ms: f.duree_moyenne_ms, intervalle_min: f.intervalle_min, chevauche: f.chevauche, occurrences_touchees: f.occurrences_touchees, lourde: f.lourde, destructive: f.destructive }),
  });
  P("/api/crons/reglages", null, {
    faire: async (req, agir) => {
      const b = req.body;
      if (b.set) { const r = await agir("planifie.reglages_poser", { ref: String(b.ref || ""), fenetre_min: +(b.fenetre_min || 0), verrou: !!b.verrou, essais: +(b.essais || 0), motif_echec: b.motif_echec || "", apres_ref: b.apres_ref || "", apres_si_ok: b.apres_si_ok !== 0 && b.apres_si_ok !== false, nom: b.nom || "" }); return ok({ reglages: reg18(r.reglages) }); }
      return ok({ reglages: reg18((await agir("planifie.reglages", { ref: String(b.ref || "") })).reglages) });
    },
  });
  P("/api/crons/chevauchements", "planifie.chevauchements", { args: () => ({}), sortie: (x) => ok({ chevauchements: (x.chevauchements || []).map((c) => ({ ref: c.ref, label: c.libelle, duree_min: c.duree_min, intervalle_min: c.intervalle_min, verrou: c.verrou })) }) });
  P("/api/crons/maintenance", null, {
    faire: async (req, agir) => {
      const b = req.body;
      if ("actif" in b) { const r = await agir("planifie.maintenance", { actif: !!b.actif, heures: +(b.heures || 4) }); return ok({ actif: r.actif, fin: r.fin, portee: r.portee }); }
      const r = await agir("planifie.maintenance_etat", {});
      return ok({ actif: r.actif, fin: r.fin });
    },
  });
  P("/api/crons/audit", "planifie.audit", {
    args: () => ({}),
    sortie: (x) => ok({ collisions: (x.collisions || []).map((c) => ({ at: c.at, count: c.nombre, jobs: c.taches.map((t) => ({ ref: t.ref, label: t.libelle, natural_id: t.id })), spread: (c.repartition || []).map((s) => ({ ref: s.ref, label: s.libelle, at: s.at })) })),
      missing_backups: (x.sauvegardes_manquantes || []).map((m) => ({ id: m.id, name: m.nom, domain: m.domaine })) }),
  });
  P("/api/crons/preview", null, {
    faire: async (req, agir) => {
      try { const r = await agir("planifie.apercu", { expression: String(req.body.cron_expr || ""), nombre: +(req.body.count || 5) }); return { ok: true, reason: "", human: r.humain, next: r.prochaines }; }
      catch (e) { return { ok: false, reason: e.message, human: "", next: [] }; }
    },
  });
  P("/api/automatismes", null, {
    faire: async (req, agir) => {
      const r = await agir("planifie.resume", {});
      return ok({ familles: [{ cle: "crons", nom: "Tâches planifiées", detail: "crontab du système et tâches de Cassandra", total: r.total, ennuis: r.ennuis, pire: r.pire, etat: r.etat, ou: "" }], maintenance: r.maintenance });
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
