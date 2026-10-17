// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La GED : /api/ged/* (V18) -> capacités ged
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #cfa805
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La GED : /api/ged/* (V18) -> capacités ged.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=cfa805 ▼▼▼
/* La GED : /api/ged/* (V18) -> capacités ged.* du noyau.
   Différé : distants rclone/OAuth, montages, OCR/vignettes, extraction des pièces jointes, diag complet. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/ged/config", "ged.config", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/config/save", "ged.config_set", { args: (r) => r.body || {}, sortie: (x) => ok(x.config) });
  P("/api/ged/racines/etat", "ged.racines_etat", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/comptes", "ged.comptes", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/sources", "ged.sources", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/lister", "ged.lister", {
    args: (r) => ({ source: r.body.source || "", chemin: r.body.chemin || "", query: r.body.query || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/fiche", "ged.fiche", {
    args: (r) => ({ fid: r.body.id || null, source: r.body.source || "", chemin: r.body.chemin || "", abs_path: r.body.abs || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/deposer", "ged.deposer", {
    args: (r) => ({ source: r.body.source || "", chemin: r.body.chemin || "", nom: r.body.nom || "", contenu_b64: r.body.contenu || r.body.contenu_b64 || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/telecharger", "ged.telecharger", {
    args: (r) => ({ fid: r.body.id || null, source: r.body.source || "", chemin: r.body.chemin || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/voir", "ged.voir", {
    args: (r) => ({ fid: r.body.id || null, source: r.body.source || "", chemin: r.body.chemin || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/corbeille", "ged.corbeille", { args: (r) => ({ fid: +r.body.id, confirme: !!r.body.confirm }), sortie: (x) => ok(x) });
  P("/api/ged/corbeille/restaurer", "ged.corbeille_restaurer", {
    args: (r) => ({ chemins: r.body.chemins || r.body.abs || [], confirme: !!r.body.confirm }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/corbeille/lister", "ged.corbeille_lister", { args: (r) => ({ query: r.body.query || "" }), sortie: (x) => ok(x) });
  P("/api/ged/regles", "ged.regles", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/regle/save", "ged.regle_save", { args: (r) => r.body || {}, sortie: (x) => ok(x) });
  P("/api/ged/regle/delete", "ged.regle_delete", { args: (r) => ({ rid: +r.body.id }), sortie: (x) => ok(x) });
  P("/api/ged/regles/test", "ged.regles_test", { args: (r) => ({ pieces: r.body.pieces || [] }), sortie: (x) => ok(x) });
  P("/api/ged/lien", "ged.lien", { args: (r) => ({ fid: +r.body.id, kind: r.body.kind || "", ref: r.body.ref || "", label: r.body.label || "" }), sortie: (x) => ok(x) });
  P("/api/ged/delien", "ged.delien", { args: (r) => ({ fid: +r.body.id, kind: r.body.kind || "", ref: r.body.ref || "" }), sortie: (x) => ok(x) });
  P("/api/ged/ecrire", "ged.ecrire", {
    args: (r) => ({ fid: r.body.id || null, source: r.body.source || "", chemin: r.body.chemin || "", texte: r.body.texte || "", confirme: !!r.body.confirm }),
    sortie: (x) => ok(x),
  });
  P("/api/ged/occupation", "ged.occupation", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/ged/dossier/creer", "ged.dossier_creer", { args: (r) => ({ compte: r.body.compte || "" }), sortie: (x) => ok(x) });
  P("/api/ged/public/creer", "ged.public_creer", { args: () => ({}), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
