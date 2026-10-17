// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Modèles : /api/modeles* (V18, administrateur) -> capacités modeles
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #a287c7
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Modèles : /api/modeles* (V18, administrateur) -> capacités modeles.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=a287c7 ▼▼▼
/* Modèles : /api/modeles* (V18, administrateur) -> capacités modeles.* du noyau. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/modeles", null, {
    faire: async (req, agir) => {
      const [l, f] = await Promise.all([agir("modeles.lister", {}), agir("modeles.fournisseurs", {}).catch(() => ({}))]);
      const fournisseurs = Array.isArray(f) ? f : f.fournisseurs || [];
      return ok({ modeles: l.modeles || [], roles: l.roles || {}, locaux: l.locaux || [], ollama: (l.locaux || []).length > 0, pull: {}, fournisseurs, choix: l.choix || "" });
    },
  });
  P("/api/modeles/ajouter", "modeles.instance_ajouter", { args: (r) => ({ fournisseur: r.body.fournisseur || "", nom: r.body.nom || "", cle: r.body.cle || "", base_url: r.body.base_url || "" }), sortie: ok });
  P("/api/modeles/essai", "modeles.instance_essayer", { args: (r) => ({ id: String(r.body.id || "") }), sortie: ok });
  P("/api/modeles/retirer", "modeles.instance_retirer", { args: (r) => ({ id: String(r.body.id || "") }), sortie: ok });
  P("/api/modeles/role", "modeles.role_lier", { args: (r) => ({ role: r.body.role || "", modele_id: String(r.body.id || "") }), sortie: ok });
  P("/api/modeles/ollama/installer", "modeles.ollama_telecharger", { args: (r) => ({ nom: r.body.nom || "" }), sortie: ok });
  P("/api/modeles/ollama/supprimer", "modeles.ollama_supprimer", { args: (r) => ({ nom: r.body.nom || "" }), sortie: ok });
  // Le ton d'un compte : le réglage « ton » du module des modèles, par compte.
  P("/api/itare/persona", null, {
    faire: async (req, agir) => {
      if ("persona" in req.body) { await agir("reglages.regler", { cle: "modeles.ton", valeur: String(req.body.persona || "") }); return ok({}); }
      const l = await agir("modeles.lister", {});
      return ok({ persona: l.ton || "", maison: false });
    },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
