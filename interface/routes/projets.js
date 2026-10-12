/* Projets : seule la liste légère est branchée (/api/itare/projects). Les écrans de gestion de projet (/api/pj/*) attendent le port complet
   de pj_contexte (santé, ancrages, infrastructure, activité) dans le module des projets. */
(function () {
  const PJ = { nom: "name", statut: "status", domaine: "domain", serveur: "server" };
  CASS.route("POST", "/api/itare/projects", "projets.lister", { args: () => ({}), sortie: (x) => ({ ok: true, projects: CASS.cles(x.projets || [], PJ) }) });
})();
