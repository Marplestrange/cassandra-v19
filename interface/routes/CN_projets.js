/* Projets : /api/pj/* (fiche, portefeuille, équipe, lignes) et /api/itare/projects (V18) -> capacités projets.* du noyau.
   Branché : liste, archives, modèles, contexte, enregistrer, créer, supprimer, corbeille, équipe, invitations, lignes de la fiche, plan de référence.
   Pas encore porté (réponse 501) : l'atelier et le coffre du projet (fichiers par SSH), le navigateur, le fil, le cadrage, le courrier rangé au projet, la présence. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const z = (n) => String(n).padStart(2, "0");
  const ts18 = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()); };
  const PJ = { nom: "name", statut: "status", domaine: "domain", serveur: "server", archive: "archived" };
  const TK = { texte: "text", statut: "status", echeance: "due_at", projet_id: "project_id", fait_le: "done_at", cree: "created_at", alarme: "alarm", priorite: "priority" };
  const EV = { titre: "summary", debut: "start_at", fin: "end_at", journee: "all_day", lieu: "location", alarme: "alarm", projet_id: "project_id" };
  const VERS19 = CASS.inverse(PJ);
  const id = (b) => +(b.id != null ? b.id : b.pid);

  const projet18 = (p) => { const x = CASS.cles(p, PJ); x.created_at = ts18(p.cree); x.updated_at = ts18(p.maj); x.archived = p.archive ? 1 : 0; x.notes = (p.journal || []).map((j) => (j.quand ? j.quand + " " : "") + j.texte).join("\n"); return x; };
  const decision18 = (d) => Object.assign({}, d, { quand: ts18(d.quand) });
  function contexte18(x) {
    return {
      ok: true, projet: projet18(x.projet), modele: x.modele, role: x.role, equipe: x.equipe, n_membres: x.n_membres,
      phases: x.phases, jalons: x.jalons, decisions: (x.decisions || []).map(decision18), taches: CASS.cles(x.taches || [], TK), avancement: x.avancement, glissement: x.glissement,
      evenements: CASS.cles(x.evenements || [], EV), perimetre_in: x.perimetre_in, perimetre_out: x.perimetre_out, reussite: x.reussite, journal: x.journal,
      ancrages: [], infra: {}, activite: { actions: [], findings: [] }, rappels: [], sante: x.sante, compte: x.comptes,
    };
  }
  const ligne18 = (l) => Object.assign({}, CASS.cles(l, PJ), { id: l.id, name: l.nom, status: l.statut, avance: l.avance, ic: l.ic });

  P("/api/pj/liste", "projets.portefeuille", { args: () => ({ archives: false }), sortie: (x) => ok({ projets: (x.projets || []).map(ligne18) }) });
  P("/api/pj/archives", "projets.portefeuille", { args: () => ({ archives: true }), sortie: (x) => ok({ projets: (x.projets || []).filter((p) => p.archive).map(ligne18) }) });
  P("/api/pj/modeles", null, {
    faire: async (req, agir) => {
      const m = await agir("projets.modeles", {});
      return ok({ modeles: m.modeles || [], questions: [], etats_phase: ["À venir", "En cours", "Terminée", "Suspendue"], statuts: ["actif", "en pause", "terminé"], priorites: ["Basse", "Normale", "Haute", "Critique"] });
    },
  });
  P("/api/pj/contexte", "projets.contexte", { args: (r) => ({ id: id(r.body) }), sortie: contexte18 });
  P("/api/pj/tableau", "projets.contexte", { args: (r) => ({ id: id(r.body) }), sortie: contexte18 });

  // Créer et modifier : la même porte V18. Les champs de la V18 sont renommés ; ceux du dossier de fichiers (nature, dossier_vault…) ne sont pas encore portés.
  const CHAMPS = ["nom", "statut", "genre", "modele", "priorite", "debut", "fin", "resume", "objectif", "perimetre_in", "perimetre_out", "reussite", "domaine", "serveur"];
  const champs19 = (b) => { const a = {}; for (const k of Object.keys(b)) { const k19 = VERS19[k] || k; if (CHAMPS.indexOf(k19) >= 0 && b[k] != null) a[k19] = b[k]; } return a; };
  P("/api/pj/save", null, {
    faire: async (req, agir) => {
      const b = req.body, pid = id(b), a = champs19(b);
      if (!pid) { const r = await agir("projets.creer", a); return ok({ id: r.id, cree: true }); }
      if (Object.keys(a).length) await agir("projets.modifier", Object.assign({ id: pid }, a));
      if (b.append_note) await agir("projets.noter", { id: pid, texte: String(b.append_note) });
      if (b.archive != null || b.archived != null) await agir("projets.archiver", { id: pid, archive: !!(b.archive != null ? b.archive : b.archived) });
      return ok({ id: pid, cree: false });
    },
  });
  P("/api/pj/creer", null, {
    faire: async (req, agir) => {
      const b = req.body, a = champs19(b);
      a.nom = a.nom || b.name || "";
      if (!a.modele) a.modele = "vide";
      const r = await agir("projets.creer", a);
      return ok({ id: r.id, cree: true });
    },
  });
  P("/api/pj/supprimer", "projets.supprimer", { args: (r) => ({ id: id(r.body) }), sortie: ok });
  P("/api/pj/refiger", "projets.refiger", { args: (r) => ({ id: id(r.body) }), sortie: ok });
  P("/api/pj/corbeille/restaurer", "projets.restaurer", { args: (r) => ({ id: id(r.body) }), sortie: (x) => ok({ pid: x.id }) });
  P("/api/pj/corbeille/purger", "projets.purger", { args: (r) => ({ id: id(r.body) }), sortie: ok });

  // Les lignes de la fiche : phases, étapes (jalons), décisions.
  const GENRES = { phase: "phase", jalon: "jalon", decision: "decision" };
  P("/api/pj/ligne/save", null, {
    faire: async (req, agir) => {
      const b = req.body, g = GENRES[b.genre];
      if (!g) throw Object.assign(new Error("genre inconnu : " + b.genre), { statut: 400 });
      const r = await agir("projets." + g + "_enregistrer", Object.assign({ id: +b.pid, ligne: b.rid ? +b.rid : undefined }, b.valeurs || {}));
      return ok({ id: r.ligne });
    },
  });
  P("/api/pj/ligne/delete", null, {
    faire: async (req, agir) => {
      const b = req.body, g = GENRES[b.genre];
      if (!g) throw Object.assign(new Error("genre inconnu : " + b.genre), { statut: 400 });
      await agir("projets." + g + "_supprimer", { id: +b.pid, ligne: +b.rid });
      return ok({});
    },
  });

  // L'équipe.
  P("/api/pj/equipe", null, {
    faire: async (req, agir) => {
      const e = await agir("projets.equipe", { id: id(req.body) });
      const moi = (CASS.moi && CASS.moi.compte) || "";
      return ok({ proprietaire: e.proprietaire, membres: e.membres, role: e.mon_role, moi, itare: {}, projet: e.projet, noms: {} });
    },
  });
  P("/api/pj/equipe/comptes", null, {
    faire: async (req, agir) => {
      const [e, l] = await Promise.all([agir("projets.equipe", { id: id(req.body) }), agir("comptes.lister", {})]);
      const deja = new Set([e.proprietaire].concat((e.membres || []).map((m) => m.compte)));
      return ok({ comptes: (l.comptes || []).filter((c) => c.type !== "systeme" && !deja.has(c.compte)).map((c) => ({ compte: c.compte, nom: c.display_name || c.compte })) });
    },
  });
  P("/api/pj/equipe/inviter", "projets.inviter", { args: (r) => ({ id: id(r.body), compte: r.body.compte || "", role: r.body.role || "" }), sortie: ok });
  P("/api/pj/equipe/retirer", "projets.retirer_membre", { args: (r) => ({ id: id(r.body), compte: r.body.compte || "" }), sortie: ok });
  P("/api/pj/invitations", "projets.invitations", { args: () => ({}), sortie: (x) => ok({ invitations: x.invitations || [] }) });
  P("/api/pj/invitations/repondre", "projets.repondre_invitation", { args: (r) => ({ id: id(r.body), accepter: !!r.body.accepter }), sortie: (x) => ok({ accepte: !!x.accepte }) });

  P("/api/itare/projects", "projets.lister", { args: () => ({}), sortie: (x) => ok({ projects: CASS.cles(x.projets || [], PJ) }) });
})();
