// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'atelier des projets : /api/pj/* (V18) -> capacités projets.*
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #69d17c
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'atelier des projets : /api/pj/* (V18) -> capacités projets.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=69d17c ▼▼▼
/* L'atelier des projets : /api/pj/* (V18) -> capacités projets.* du noyau.
   Branché ici : l'atelier (fiche, importer, note, sources, verser), le cadrage, le dossier de fichiers (coffre) et le choix du dossier, les commentaires, le fil, le courrier rangé au projet,
   la présence, les suites proposées et le navigateur partagé.
   Les gestes qui touchent deux modules (importer, verser, pièce de courrier, note du Carnet) passent d'abord par la porte « projets.garde » : le rôle est vérifié avant tout.
   Pas portés (réponse 200 {ok:false, reason}) : l'image, le clic, le défilement et la frappe du navigateur — il lit les pages en texte, il ne les dessine pas. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const pid = (b) => +(b.pid != null ? b.pid : b.id);
  const sain = (t, d) => String(t || d).replace(/[\\/:*?"<>|#^\[\]]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 100) || d;
  const rien = (raison) => ({ faire: async () => ({ ok: false, reason: raison }) });

  // ── le dossier de fichiers (coffre) ────────────────────────────────────────────────────────
  const F = (chemin, cap, o) => P("/api/pj/coffre/" + chemin, "projets." + cap, o);
  F("lister", "coffre_lister", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("lire", "coffre_lire", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("etat", "coffre_etat", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("fichier", "coffre_fichier", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", apercu: r.body.apercu !== false }), sortie: ok });
  F("index", "coffre_index", { args: (r) => ({ id: pid(r.body) }), sortie: ok });
  F("versions", "coffre_versions", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("version", "coffre_version", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", n: +r.body.n || 0 }), sortie: ok });
  F("ecrire", "coffre_ecrire", {
    args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", texte: r.body.texte || "", empreinte: r.body.empreinte || "", creer: !!r.body.creer }),
    sortie: (x) => (x.conflit ? Object.assign({ ok: false }, x) : ok(x)),
  });
  F("deplacer", "coffre_deplacer", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", vers: r.body.vers || "" }), sortie: ok });
  F("dossier", "coffre_dossier", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("retirer", "coffre_retirer", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  F("remettre", "coffre_remettre", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", n: +r.body.n || 0 }), sortie: ok });

  // ── choisir le dossier d'un projet ─────────────────────────────────────────────────────────
  P("/api/pj/dossier/parcourir", "projets.dossier_parcourir", { args: (r) => ({ machine: r.body.machine || "", chemin: r.body.chemin || "" }), sortie: ok });
  P("/api/pj/dossier/creer", "projets.dossier_creer", { args: (r) => ({ machine: r.body.machine || "", chemin: r.body.chemin || "/", nom: r.body.nom || "" }), sortie: ok });
  P("/api/pj/dossier/corbeille", "projets.dossier_corbeille", { args: (r) => ({ machine: r.body.machine || "", chemin: r.body.chemin || "/" }), sortie: ok });
  P("/api/pj/dossier/local", "projets.dossier_local", { args: (r) => ({ id: pid(r.body) }), sortie: ok });

  // ── l'atelier : fiche d'un document, sources, import, note du Carnet, versement ─────────────
  P("/api/pj/atelier/fiche", "projets.atelier_fiche", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  P("/api/pj/atelier/sources", "projets.atelier_sources", { args: (r) => ({ id: pid(r.body) }), sortie: ok });
  P("/api/pj/atelier/importer", null, {
    faire: async (req, agir) => {
      const b = req.body, id = pid(b);
      const g = await agir("projets.garde", { id, geste: "ecrire" });
      const s = await agir("ged.sources", {});
      if (!s.defaut) throw Object.assign(new Error("aucun espace de documents pour ce compte"), { statut: 400 });
      const d = await agir("ged.deposer", { source: s.defaut, chemin: "", nom: b.nom || "document", contenu_b64: b.contenu || "" });
      await agir("ged.lien", { fid: d.id, kind: "project", ref: String(id), label: g.nom });
      return ok({ id: d.id, nom: d.nom });
    },
  });
  P("/api/pj/atelier/note", null, {
    faire: async (req, agir) => {
      const b = req.body;
      await agir("projets.garde", { id: pid(b), geste: "ecrire" });
      const r = await agir("notes.ecrire", { ref: String(b.ref || ""), corps: String(b.contenu || ""), motif: "modifiée dans l'Atelier" });
      return ok(r);
    },
  });
  P("/api/pj/atelier/verser", null, {
    faire: async (req, agir) => {
      const b = req.body, id = pid(b);
      await agir("projets.garde", { id, geste: "ecrire" });
      const f = await agir("notes.fiche", { ref: String(b.ref || ""), marquer: false });
      const titre = sain(f.titre, String(b.ref || "note"));
      const etq = (f.etiquettes || []).map(String).filter((x) => x.trim());
      const texte = "---\ncarnet: " + (f.id || b.ref) + "\n" + (etq.length ? "tags: [" + etq.join(", ") + "]\n" : "") + "---\n\n" + String(f.corps || "");
      const d = String(b.dossier || "Notes").trim().replace(/^\/+|\/+$/g, "") || "Notes";
      try { await agir("projets.coffre_dossier", { id, chemin: d }); } catch (e) { /* il existe déjà */ }
      for (let k = 1; k < 9; k++) {
        const ch = d + "/" + titre + (k === 1 ? "" : " (" + k + ")") + ".md";
        try {
          const w = await agir("projets.coffre_ecrire", { id, chemin: ch, texte, creer: true });
          try { await agir("notes.supprimer", { ref: f.id || b.ref }); } catch (e) { /* le fichier est écrit : la note reste à la main */ }
          return ok({ chemin: w.chemin || ch });
        } catch (e) {
          if (!/existe déjà/.test(e.message || "")) throw e;
        }
      }
      throw Object.assign(new Error("trop de notes de ce nom dans " + d), { statut: 400 });
    },
  });

  // ── le cadrage ─────────────────────────────────────────────────────────────────────────────
  P("/api/pj/cadrage/proposer", "projets.cadrage_proposer", { args: (r) => ({ id: pid(r.body), reponses: r.body.reponses || {} }), sortie: ok });
  P("/api/pj/cadrage/appliquer", null, {
    faire: async (req, agir) => {
      const b = req.body, id = pid(b);
      let ecrits = 0, entete = {};
      const refus = [];
      for (const p of b.propositions || []) {
        const v = p.valeurs || {};
        if (p.genre === "entete") { for (const k of ["objectif", "perimetre_out", "reussite"]) if (k in v) entete[k] = v[k]; }
        else if (p.genre === "jalon" || p.genre === "phase" || p.genre === "decision") {
          try { await agir("projets." + p.genre + "_enregistrer", Object.assign({ id }, v)); ecrits++; } catch (e) { refus.push(p.genre + " : " + e.message); }
        } else refus.push("genre inconnu : " + p.genre);
      }
      if (Object.keys(entete).length) {
        try { await agir("projets.modifier", Object.assign({ id }, entete)); ecrits += Object.keys(entete).length; } catch (e) { refus.push("en-tête : " + e.message); }
      }
      await agir("projets.noter", { id, texte: "Cadrage renseigné — " + ecrits + " élément(s) posés depuis l'entretien." + (refus.length ? " Refusés : " + refus.join(" ; ") : "") });
      return ok({ ecrits, refus });
    },
  });
  P("/api/pj/proposer", "projets.proposer", { args: (r) => ({ id: pid(r.body) }), sortie: (x) => ok({ en_cours: false, items: x.items }) });

  // ── commentaires en marge, présence ────────────────────────────────────────────────────────
  P("/api/pj/commentaires", "projets.commentaires", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });
  P("/api/pj/commenter", "projets.commenter", {
    args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "", citation: r.body.citation || "", texte: r.body.texte || "", parent: +r.body.parent || 0 }),
    sortie: (x) => ok({ id: x.cid, mentions: x.mentions, itare: x.itare }),
  });
  P("/api/pj/commentaire/resoudre", "projets.commentaire_resoudre", { args: (r) => ({ id: pid(r.body), cid: +r.body.id, resolu: r.body.resolu !== false }), sortie: ok });
  P("/api/pj/presence", "projets.presence", { args: (r) => ({ id: pid(r.body), chemin: r.body.chemin || "" }), sortie: ok });

  // ── le fil ─────────────────────────────────────────────────────────────────────────────────
  P("/api/pj/fil", "projets.fil", { args: (r) => ({ id: pid(r.body), limite: +r.body.limite || 200 }), sortie: ok });
  P("/api/pj/fil/publier", "projets.fil_publier", {
    args: (r) => ({ id: pid(r.body), genre: r.body.genre || "message", texte: r.body.texte || "", parent: +r.body.parent || 0 }),
    sortie: (x) => ok({ id: x.fid, mentions: x.mentions, itare: x.itare }),
  });
  P("/api/pj/fil/avis", "projets.fil_avis", { args: (r) => ({ id: pid(r.body), fid: +r.body.fid, avis: r.body.avis || "" }), sortie: () => ok({}) });
  P("/api/pj/fil/trancher", "projets.fil_trancher", {
    args: (r) => ({ id: pid(r.body), fid: +r.body.fid, issue: r.body.issue || "", raison: r.body.raison || "", seuil: r.body.seuil || "" }), sortie: () => ok({}),
  });
  P("/api/pj/fil/relire", "projets.fil_relire", { args: (r) => ({ id: pid(r.body), fid: +r.body.fid, action: r.body.action || "" }), sortie: () => ok({}) });

  // ── le courrier rangé au projet ────────────────────────────────────────────────────────────
  P("/api/pj/courrier", "projets.courrier", { args: (r) => ({ id: pid(r.body), q: r.body.q || "", boite: !!r.body.boite, limite: r.body.boite ? 200 : 80 }), sortie: ok });
  P("/api/pj/courrier/ranger", "projets.courrier_ranger", {
    args: (r) => ({ id: pid(r.body), folder: r.body.folder || "", uid: String(r.body.uid || ""), mode: r.body.mode || "" }), sortie: (x) => ok({ cle: x.cle, mode: x.mode }),
  });
  P("/api/pj/courrier/piece", null, {
    faire: async (req, agir) => {
      const b = req.body, id = pid(b);
      const g = await agir("projets.garde", { id, geste: "ecrire" });
      const piece = await agir("courrier.piece", { uid: String(b.uid || ""), index: +b.index || 0, dossier: b.folder || "INBOX" });
      const s = await agir("ged.sources", {});
      if (!s.defaut) throw Object.assign(new Error("aucun espace de documents pour ce compte"), { statut: 400 });
      const d = await agir("ged.deposer", { source: s.defaut, chemin: "", nom: piece.nom || "piece", contenu_b64: piece.donnees_b64 });
      await agir("ged.lien", { fid: d.id, kind: "project", ref: String(id), label: g.nom });
      return ok({ id: d.id, nom: d.nom || piece.nom || "" });
    },
  });

  // ── le navigateur partagé : il LIT les pages (module web), il ne les dessine pas ───────────
  P("/api/pj/nav/aller", "projets.nav_aller", { args: (r) => ({ url: r.body.url || "" }), sortie: ok });
  P("/api/pj/nav/retour", "projets.nav_retour", { args: () => ({}), sortie: ok });
  P("/api/pj/nav/fermer", "projets.nav_fermer", { args: () => ({}), sortie: ok });
  P("/api/pj/nav/clipper", "projets.nav_clipper", { args: (r) => ({ id: pid(r.body), dossier: r.body.dossier || "Clips" }), sortie: ok });
  P("/api/pj/nav/image", null, rien("le navigateur partagé lit les pages en texte : il n'en dessine pas l'image"));
  P("/api/pj/nav/clic", null, rien("le navigateur partagé lit les pages en texte : on n'y clique pas"));
  P("/api/pj/nav/defiler", null, rien("le navigateur partagé lit les pages en texte : il n'y a rien à défiler"));
  P("/api/pj/nav/texte", null, rien("le navigateur partagé lit les pages en texte : on n'y tape pas"));
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
