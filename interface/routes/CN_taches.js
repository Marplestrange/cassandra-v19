// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Tâches : /api/itare/task* (V18) -> capacités taches
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #1ce833
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Tâches : /api/itare/task* (V18) -> capacités taches.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=1ce833 ▼▼▼
/* Tâches : /api/itare/task* (V18) -> capacités taches.* du noyau. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const T = { texte: "text", statut: "status", echeance: "due_at", projet_id: "project_id", fait_le: "done_at", cree: "created_at", alarme: "alarm", liens: "links", tache: "task", priorite: "priority", nb_sous: "n_sous" };
  const VERS19 = CASS.inverse(T);
  const t18 = (x) => CASS.cles(x, T);

  P("/api/itare/tasks", null, {
    faire: async (req, agir) => {
      const b = req.body;
      const [l, pj] = await Promise.all([
        agir("taches.lister", { projet_id: b.project_id == null ? undefined : b.project_id, inclure_faites: !!b.include_done, limite: +(b.limit || 200), racines_seules: !!b.racines_seules }),
        agir("projets.lister", {}).catch(() => ({ projets: [] })),
      ]);
      return { ok: true, tasks: t18(l.taches || []), projects: (pj.projets || []).map((p) => ({ id: p.id, name: p.nom })) };
    },
  });
  P("/api/itare/task/save", null, {
    faire: async (req, agir) => {
      const b = req.body, a = {};
      for (const k of Object.keys(b)) { if (k === "id" || k === "session") continue; a[k === "due" ? "echeance" : (VERS19[k] || k)] = b[k]; }
      if (b.id) { a.id = +b.id; const r = await agir("taches.modifier", a); return ok({ id: a.id, due_at: r && r.echeance, suivante: r && r.suivante }); }
      const r = await agir("taches.creer", a);
      return ok({ id: r.id });
    },
  });
  P("/api/itare/task/context", "taches.fiche", { args: (r) => ({ id: +r.body.id }), sortie: (x) => ok(t18(x)) });
  P("/api/itare/task/link", "taches.lier", { args: (r) => ({ id: +r.body.id, kind: r.body.kind || "", ref: String(r.body.ref || ""), label: r.body.label || "" }), sortie: ok });
  P("/api/itare/task/unlink", "taches.delier", { args: (r) => ({ id: +r.body.id, kind: r.body.kind || "", ref: String(r.body.ref || "") }), sortie: ok });
  P("/api/itare/task/delete", "taches.supprimer", { args: (r) => ({ id: +r.body.id }), sortie: ok });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
