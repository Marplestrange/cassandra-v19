// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Notes : /api/notes/* (V18, tout en POST) -> capacités notes
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d8db67
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Notes : /api/notes/* (V18, tout en POST) -> capacités notes.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d8db67 ▼▼▼
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

  // ── Le carnet (V18 : /api/carnet/*) : les mêmes notes, rangées par projet et par étiquette ; chaque geste est une écriture de notes.ecrire.
  const refCa = (b) => String(b.ref || b.id || "");
  const projetDe = async (agir, nom) => {
    const n = String(nom || "").trim();
    if (!n) return null;
    const t = (await agir("projets.trouver", { nom: n })).projet;
    return t && t.nom.trim().toLowerCase() === n.toLowerCase() ? t : null;
  };
  P("/api/carnet/groupes", null, {
    faire: async (req, agir) => {
      const r = await agir("notes.lister", { limite: 1 });
      const g = r.groupes || {};
      return ok({ projets: g.projets || [], etiquettes: g.etiquettes || [], sans: g.sans || 0, postit: 0, total: r.total || 0 });
    },
  });
  P("/api/carnet/lister", "notes.lister", {
    args: (r) => ({ groupe: r.body.groupe || "*", q: r.body.q || "", tri: r.body.tri || "recent", filtre: r.body.filtre || "toutes" }),
    sortie: (x) => ok({ notes: x.notes || [], total: (x.notes || []).length }),
  });
  P("/api/carnet/fiche", "notes.fiche", { args: (r) => ({ ref: refCa(r.body), marquer: false }), sortie: ok });
  P("/api/carnet/ranger", null, {
    faire: async (req, agir) => {
      const b = req.body, a = { ref: refCa(b), motif: "rangée" };
      if (b.etiquettes == null && b.projet == null) return { ok: false, reason: "rien à ranger" };
      if (b.etiquettes != null) a.etiquettes = b.etiquettes;
      if (b.projet != null) a.projet = b.projet;
      const r = await agir("notes.ecrire", a);
      return ok({ id: r.ref || a.ref });
    },
  });
  const rattachements = async (agir, ref, fait) => {
    const f = await agir("notes.fiche", { ref, marquer: false });
    const liste = (f.rattache || []).map((x) => x.brut);
    const neuve = fait(liste);
    if (typeof neuve === "string") return { ok: false, reason: neuve };
    await agir("notes.ecrire", { ref, rattache: neuve.liste, motif: neuve.motif });
    const g = await agir("notes.fiche", { ref, marquer: false });
    return ok({ id: g.id, rattache: g.rattache });
  };
  P("/api/carnet/rattacher", null, {
    faire: (req, agir) => {
      const b = req.body, nature = String(b.nature || "").trim(), cible = String(b.cible || "").trim();
      if (!nature || !cible) return { ok: false, reason: "aucune cible" };
      const t = nature + ":" + cible;
      return rattachements(agir, refCa(b), (l) => (l.includes(t) ? "déjà rattachée" : { liste: l.concat([t]), motif: "rattachée à " + t }));
    },
  });
  P("/api/carnet/detacher", null, {
    faire: (req, agir) => {
      const b = req.body, brut = String(b.brut || "");
      return rattachements(agir, refCa(b), (l) => (l.includes(brut) ? { liste: l.filter((x) => x !== brut), motif: "détachée de " + brut } : "ce rattachement n'existe pas"));
    },
  });
  P("/api/carnet/etat", null, {
    faire: async (req, agir) => {
      const etat = String(req.body.etat || "").trim();
      const r = await agir("notes.ecrire", { ref: refCa(req.body), etat, motif: "état : " + etat });
      return ok({ id: r.ref, etat });
    },
  });
  P("/api/carnet/relire", null, {
    faire: async (req, agir) => {
      const quand = String(req.body.quand || "").trim().slice(0, 10);
      const r = await agir("notes.ecrire", { ref: refCa(req.body), relire: quand, motif: quand ? "relecture au " + quand : "relecture retirée" });
      return ok({ id: r.ref, relire: quand });
    },
  });
  P("/api/carnet/tache", "notes.case_basculer", { args: (r) => ({ ref: refCa(r.body), ligne: +r.body.ligne }), sortie: (x) => ok({ id: x.ref, ligne: x.ligne, faite: x.faite }) });
  P("/api/carnet/taches", null, {
    faire: async (req, agir) => {
      const e = await agir("notes.cases_etat", { ref: refCa(req.body) });
      const p = await projetDe(agir, e.projet);
      return ok(Object.assign({}, e, { projet_id: p ? p.id : null, sans_projet: !e.projet }));
    },
  });
  P("/api/carnet/taches/projeter", null, {
    faire: async (req, agir) => {
      const ref = refCa(req.body), e = await agir("notes.cases_etat", { ref });
      if (!e.projet) return { ok: false, reason: "cette note n'est rattachée à aucun projet" };
      const p = await projetDe(agir, e.projet);
      if (!p) return { ok: false, reason: "aucun projet ne porte le nom « " + e.projet + " »" };
      const creees = [];
      let deja = 0;
      for (const c of e.cases) {
        if (c.tache) { deja++; continue; }
        const t = await agir("taches.creer", { texte: c.texte, projet_id: p.id, source: "note", origine: ref + ":" + c.ligne });
        if (c.faite) await agir("taches.modifier", { id: t.id, statut: "fait" });
        await agir("notes.case_lier", { ref, ligne: c.ligne, tache_id: t.id });
        creees.push(c.texte);
      }
      return ok({ id: ref, creees, deja });
    },
  });
  P("/api/carnet/taches/reprendre", "notes.cases_reprendre", { args: (r) => ({ ref: refCa(r.body) }), sortie: (x) => ok({ id: x.ref, reprises: x.reprises || [], note: x.note }) });
  // Les post-it n'existent pas en V19 (la base repart vide, la note les remplace) : aucun à reprendre, rien à migrer.
  P("/api/carnet/postit", null, { faire: async () => ok({ postit: [], restants: 0 }) });
  P("/api/carnet/postit/reprendre", null, { faire: async () => ({ ok: false, reason: "ce post-it n'existe plus" }) });
  P("/api/carnet/migrer", null, { faire: async () => ok({ migres: [], ignores: [], restants: 0 }) });
  P("/api/notes/migration", null, { faire: async () => ok({ migration: null }) });
  // Un rappel lié à une case : le texte du rappel porte le renvoi vers la note (comme en V18), sans copie ; un rappel déjà posé pour ce texte et ce renvoi n'est pas doublé.
  P("/api/notes/tache/rappel", null, {
    faire: async (req, agir) => {
      const r = ref(req.body), ligne = +req.body.ligne;
      const e = await agir("notes.cases_etat", { ref: r });
      const c = (e.cases || []).find((x) => x.ligne === ligne);
      if (!c) return { ok: false, reason: "cette ligne n'est pas une case à cocher" };
      const texte = c.texte + "  [[note:" + e.id + "]]";
      const deja = ((await agir("agenda.rappels", { inclure_faits: false })) || {}).rappels || [];
      const meme = deja.find((x) => x.texte === texte);
      if (meme) return ok({ deja: true, rappel_id: meme.id });
      const m = await agir("agenda.rappel_enregistrer", { texte, echeance: String(req.body.due || "") || undefined });
      return ok({ rappel_id: m.id, note: e.id, ligne });
    },
  });
  // Ce qui renvoie à une cible : les notes qui la citent. La table générique des liens de la V18 n'est pas portée ; les renvois des notes, eux, le sont.
  P("/api/liens", null, {
    faire: async (req, agir) => {
      const nat = String(req.body.nat || ""), cible = String(req.body.ref || "");
      if (!nat || !cible) return { ok: false, error: "objet inconnu" };
      const d = await agir("notes.de", { kind: nat, ref: cible });
      return ok({ liens: (d.notes || []).map((n) => ({ nat: "note", ref: n.id, nom: n.titre, role: n.inclus ? "inclusion" : "renvoi", sens: "entrant", a_nat: "note", a_ref: n.id, b_nat: nat, b_ref: cible })) });
    },
  });
  P("/api/liens/graphe", null, {
    faire: async (req, agir) => {
      const veut = Array.isArray(req.body.natures) ? new Set(req.body.natures) : null;
      const l = await agir("notes.liens", {});
      const noeuds = {}, aretes = [], vus = new Set();
      const n = (nat, ref, nom) => {
        if (veut && !veut.has(nat)) return false;
        const k = nat + ":" + ref;
        if (!noeuds[k]) noeuds[k] = { nat, ref, nom: nom || ref };
        else if (nom && noeuds[k].nom === ref) noeuds[k].nom = nom;
        return true;
      };
      for (const x of l.liens || []) {
        if (!n("note", x.src, x.src_titre) || !n(x.kind, x.ref, x.existe === false ? x.ref : x.titre)) continue;
        const k = x.src + "|" + x.kind + "|" + x.ref;
        if (vus.has(k)) continue;
        vus.add(k);
        aretes.push({ a: "note:" + x.src, b: x.kind + ":" + x.ref, role: x.inclus ? "inclusion" : "renvoi", fort: false });
      }
      return ok({ noeuds: Object.values(noeuds), aretes });
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
