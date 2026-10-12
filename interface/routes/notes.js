/* Notes : /api/notes/* (V18, tout en POST) -> capacités notes.* du noyau.
   Le noyau a gardé les formes de la V18 (titre, corps, refs…) ; il manque surtout `ok` et quelques noms d'arguments. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const ref = (b) => String(b.ref || "");

  P("/api/notes/lister", "notes.lister", { args: (r) => ({ q: r.body.q || "", tri: r.body.tri || "recent", filtre: r.body.filtre || "toutes", etiquette: r.body.etiquette || "", projet: r.body.projet || "" }), sortie: ok });
  P("/api/notes/fiche", "notes.fiche", { args: (r) => ({ ref: ref(r.body) }), sortie: ok });
  P("/api/notes/creer", "notes.creer", {
    args: (r) => ({ titre: r.body.titre || "", corps: r.body.contenu || "", etiquettes: r.body.etiquettes || [], projet: r.body.projet || "", source: r.body.source || "", etat: r.body.vivante ? "vivante" : undefined }),
    sortie: (x) => ok({ id: x.ref, fichier: x.ref, num: x.num }),
  });
  P("/api/notes/ecrire", "notes.ecrire", {
    args: (r) => ({ ref: ref(r.body), corps: r.body.contenu, titre: r.body.titre, etiquettes: r.body.etiquettes, projet: r.body.projet, epinglee: r.body.epinglee, motif: r.body.motif || "" }),
    sortie: (x) => ok({ id: x.ref || x.id, fichier: x.ref || x.id }),
  });
  P("/api/notes/corbeille", "notes.supprimer", { args: (r) => ({ ref: ref(r.body) }), sortie: ok });
  P("/api/notes/restaurer", "notes.restaurer", { args: (r) => ({ ref: ref(r.body) || String(r.body.fichier || "").replace(/\.md$/, "") }), sortie: ok });
  P("/api/notes/corbeille/vider", "notes.vider_corbeille", { args: () => ({}), sortie: ok });
  P("/api/notes/version", "notes.version_lire", { args: (r) => ({ ref: ref(r.body), version: +r.body.version || 0 }), sortie: ok });
  P("/api/notes/revenir", "notes.revenir", { args: (r) => ({ ref: ref(r.body), version: +r.body.version || 0 }), sortie: ok });
  P("/api/notes/fusionner", "notes.fusionner", { args: (r) => ({ refs: r.body.refs || [], titre: r.body.titre || "" }), sortie: ok });
  P("/api/notes/exporter", "notes.exporter", { args: (r) => ({ ref: ref(r.body), format: r.body.format || "md" }), sortie: ok });
  P("/api/notes/archive", "notes.archive", { args: (r) => ({ portee: r.body.portee || "tout", dossier: r.body.dossier || "", refs: r.body.refs || [] }), binaire: (a) => ({ b64: a.contenu_b64, type: a.mime, nom: a.nom }) });
  P("/api/notes/taches", "notes.cases", { args: (r) => ({ ouvertes_seules: !!r.body.ouvertes_seules }), sortie: ok });
  P("/api/notes/tache/basculer", "notes.case_basculer", { args: (r) => ({ ref: ref(r.body), ligne: +r.body.ligne }), sortie: ok });
  P("/api/notes/jour", (r) => (r.body.creer ? "notes.jour_ouvrir" : "notes.jour"), { args: (r) => ({ jour: r.body.jour || "" }), sortie: ok });
  P("/api/notes/mentions", "notes.mentions", { args: (r) => ({ ref: ref(r.body) }), sortie: ok });
  P("/api/notes/partage/creer", "notes.partage_creer", { args: (r) => ({ ref: ref(r.body), format: r.body.format || "html", jours: r.body.jours, mdp: r.body.mdp || "" }), sortie: ok });
  P("/api/notes/partages", "notes.partages", { args: () => ({}), sortie: ok });
  P("/api/notes/partage/retirer", "notes.partage_retirer", { args: (r) => ({ jeton: r.body.jeton || "" }), sortie: ok });
  P("/api/notes/cibles", "notes.cibles", { args: (r) => ({ q: r.body.q || "", limite: +(r.body.limite || 300) }), sortie: ok });
  P("/api/notes/liens", "notes.resoudre", { args: (r) => (Array.isArray(r.body.textes) ? { textes: r.body.textes } : { texte: r.body.texte || "" }), sortie: ok });
  P("/api/notes/ranger", "notes.ecrire", { args: (r) => ({ ref: ref(r.body), dossier: r.body.dossier || "" }), sortie: (x) => ok({ fichier: x.ref || x.id, dossier: x.dossier }) });
  P("/api/notes/inventaire", "notes.liens", { args: () => ({}), sortie: ok });
  P("/api/notes/de", "notes.de", { args: (r) => ({ kind: r.body.kind || "", ref: ref(r.body) }), sortie: ok });
  P("/api/notes/dossiers", "notes.dossiers", { args: () => ({}), sortie: ok });
  P("/api/notes/dossier/creer", "notes.dossier_creer", { args: (r) => ({ chemin: r.body.chemin || "" }), sortie: ok });
  P("/api/notes/dossier/renommer", "notes.dossier_renommer", { args: (r) => ({ chemin: r.body.chemin || "", nom: r.body.nom || r.body.nouveau || "" }), sortie: ok });
  P("/api/notes/dossier/supprimer", "notes.dossier_supprimer", { args: (r) => ({ chemin: r.body.chemin || "" }), sortie: ok });
  P("/api/notes/menage", "notes.menage", { args: () => ({}), sortie: ok });
})();
