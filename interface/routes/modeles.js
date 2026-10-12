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
})();
