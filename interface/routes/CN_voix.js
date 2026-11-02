// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La voix : /api/voix/* -> capacités voix
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #9df717
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La voix : /api/voix/* -> capacités voix.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=9df717 ▼▼▼
/* La voix : /api/voix/* -> capacités voix.* du noyau.
   La parole (/api/voix/parler) rend le son (WAV) de la voix choisie par le compte ; le modèle de dictée et le lexique (/api/voix/machine) sont des réglages du module. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/voix/dispo", "voix.dispo", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/voix/catalogue", "voix.catalogue", { args: () => ({}), sortie: (x) => ok(x) });
  // L'écran V18 lit la voix du compte à plat : voix posées, voix choisie, locuteur, débit, lecture automatique, mode vocal, modèle de dictée et lexique.
  P("/api/voix/reglages", "voix.reglages", {
    args: () => ({}),
    sortie: (x) => {
      const g = x.reglages || {}, cat = x.catalogue || [];
      return ok({ posees: cat.filter((v) => v.pose), catalogue: cat, choix: g.voix_nom || "", locuteur: g.voix_locuteur || "", debit: g.voix_debit || "", auto: !!g.voix_auto, mode: !!g.voix_mode,
                  modeles: x.modeles || [], modele: x.modele || "small", lexique: x.lexique || "", dossier: x.dossier || "" });
    },
  });
  P("/api/voix/ecouter", "voix.ecouter", { args: (r) => ({ audio_b64: String(r.body.audio || "").split(",").pop(), langue: r.body.langue || "fr" }), sortie: (x) => ok(x) });
  P("/api/voix/etat", null, {
    faire: async (req, agir) => {
      const [d, g] = await Promise.all([agir("voix.dispo", {}), agir("voix.reglages", {}).catch(() => ({}))]);
      return ok({ ecoute: !!d.ecoute, parle: !!d.parle, mode: !!((g.reglages || {}).voix_mode), auto: !!((g.reglages || {}).voix_auto), quoi: d.quoi || [] });
    },
  });
  P("/api/voix/parler", null, {
    faire: async (req, agir) => {
      const texte = String(req.body.texte || "").trim();
      if (!texte) throw Object.assign(new Error("texte requis"), { statut: 400 });
      const g = ((await agir("voix.reglages", {})) || {}).reglages || {};
      if (!g.voix_nom) throw Object.assign(new Error("aucune voix choisie : choisissez-en une dans les réglages de la voix"), { statut: 400 });
      const r = await agir("voix.parler", { texte, voix: g.voix_nom, locuteur: g.voix_locuteur || "", debit: g.voix_debit || "" });
      const oct = Uint8Array.from(atob(r.audio_b64), (c) => c.charCodeAt(0));
      return new Response(oct, { status: 200, headers: { "Content-Type": "audio/wav" } });
    },
  });
  P("/api/voix/machine", null, {
    faire: async (req, agir) => {
      const modele = String(req.body.modele || "").trim(), lexique = String(req.body.lexique || "");
      if (modele) await agir("reglages.regler", { cle: "voix.modele_dictee", valeur: modele });
      await agir("reglages.regler", { cle: "voix.lexique", valeur: lexique });
      return ok({});
    },
  });
  P("/api/voix/poser", "voix.telecharger", { args: (r) => ({ voix_id: String(r.body.ref || "") }), sortie: (x) => ok(x) });
  P("/api/voix/choisir", "voix.choisir", {
    args: (r) => ({ voix_nom: r.body.voix_nom || "", voix_locuteur: r.body.voix_locuteur || "", voix_auto: r.body.voix_auto, voix_debit: r.body.voix_debit || "", voix_mode: r.body.voix_mode }),
    sortie: (x) => ok(x),
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
