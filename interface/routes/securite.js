/* La sécurité : /api/securite/* (V18) -> capacités securite.* du noyau.
   Différé : l'état de la machine, direct/geste, le pare-feu FastPanel, les audits rédigés par le modèle. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  // L'état de la machine : composé par le module sur les relevés bruts du courtier (services à l'écoute, pare-feu du noyau, SSH, fail2ban, mises à jour).
  P("/api/securite", "securite.etat", { args: () => ({}), sortie: (x) => x });
  P("/api/securite/gestes", "securite.gestes", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/securite/journal", "securite.journal", { args: (r) => ({ limite: +(r.body.limite || 120) }), sortie: (x) => ok(x) });
  P("/api/securite/audits", "securite.audits", { args: (r) => ({ id: +(r.body.id || 0) }), sortie: (x) => ok(x) });
  // Les gestes de l'onglet : la table fermée de la V18, chacun vers SA capacité (droit, preuve, retour, journal). Le courtier les exécute à root et les vérifie.
  const GESTES = { ssh_mdp: "securite.ssh_mdp", ssh_x11: "securite.ssh_x11", mysql_local: "securite.mysql_local", maj_securite: "securite.maj_securite", maj_auto: "securite.maj_auto", debannir: "securite.debannir" };
  P("/api/securite/geste", null, {
    faire: async (req, agir) => {
      const b = req.body, g = String(b.geste || "");
      try {
        if (g.indexOf("outil:") === 0) {                                            // « outil:installer:clamav », « outil:lancer:lynis » : en arrière-plan, par le courtier
          const [, quoi, nom] = g.split(":");
          if (quoi === "installer" || quoi === "lancer") return ok(await agir("securite.outil_" + quoi, { nom: nom || "" }));
        }
        if (g.indexOf("arret:") === 0) return ok(await agir("securite.arret", { service: g.slice(6) }));
        // Le pare-feu du panneau : validé avant tout envoi, posé à l'essai quand il peut fermer (deux minutes pour le garder), jamais SSH fermé à tous sans Tailscale.
        if (g === "regle_poser") return ok(await agir("fastpanel.parefeu_regle_poser", { id: +(b.id || 0), nom: b.nom || "", ports: b.ports || "", proto: b.proto || "TCP", sens: b.sens || "INPUT", politique: b.politique || "", sources: b.sources || "" }));
        if (g === "regle_retirer") return ok(await agir("fastpanel.parefeu_regle_retirer", { id: +(b.id || 0) }));
        if (g === "politique") return ok(await agir("fastpanel.parefeu_politique", { politique: b.politique || "" }));
        if (GESTES[g]) return ok(await agir(GESTES[g], g === "debannir" ? { jail: String(b.jail || ""), ip: String(b.ip || "") } : {}));
      } catch (e) { return { ok: false, error: e.message }; }
      return { ok: false, error: "ce geste n'est pas encore porté (outils de sécurité)" };
    },
  });
  P("/api/securite/parefeu/trancher", "fastpanel.parefeu_trancher", { args: (r) => ({ jeton: String(r.body.jeton || ""), garder: !!r.body.garder }), sortie: ok });
  P("/api/securite/noter", "securite.noter", {
    args: (r) => ({ geste: r.body.geste || "", cible: r.body.cible || "", detail: r.body.detail || "", ok: r.body.ok !== false, resultat: r.body.resultat || "", defaire: r.body.defaire || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/securite/audit/poser", "securite.audit_poser", { args: (r) => ({ modele: r.body.modele || "", titre: r.body.titre || "", corps: r.body.corps || "" }), sortie: (x) => ok(x) });
})();
