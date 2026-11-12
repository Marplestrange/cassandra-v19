// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La sécurité : /api/securite/* (V18) -> capacités securite
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #39365d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La sécurité : /api/securite/* (V18) -> capacités securite.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=39365d ▼▼▼
/* La sécurité : /api/securite/* (V18) -> capacités securite.* du noyau.
   Les gestes directs rares de la V18 (bannir, fermer un chemin d'un site, robots) ne sont pas encore portés : dits tels quels. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  async function viaRoute(agir, fonction, args) {
    const r = await agir("paneldetect.route", { fonction: fonction });
    if (!r || !r.capacite) throw new Error("aucun panneau d'hébergement ne sert « " + fonction + " »");
    return agir(r.capacite, args || {});
  }

  const ok = (x) => Object.assign({ ok: true }, x);

  // L'état de la machine : composé par le module sur les relevés bruts du courtier (services à l'écoute, pare-feu du noyau, SSH, fail2ban, mises à jour).
  P("/api/securite", "securite.etat", { args: () => ({}), sortie: (x) => x });
  P("/api/securite/images", "securite.images", { args: () => ({}), sortie: (x) => x });
  P("/api/securite/gestes", "securite.gestes", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/securite/journal", "securite.journal", { args: (r) => ({ limite: +(r.body.limite || 120) }), sortie: (x) => ok(x) });
  // Les audits : la liste, et celui qu'on lit (le dernier, ou celui demandé) avec son texte sous le nom que l'écran lit (html). La rédaction, longue, tourne en arrière-plan.
  const AUDIT = { en_cours: false, depuis: 0, erreur: "" };
  P("/api/securite/audits", null, {
    faire: async (req, agir) => {
      try {
        const id = +(req.body.id || 0), l = ((await agir("securite.audits", {})) || {}).audits || [];
        const cible = id || (l[0] && l[0].id) || 0;
        let courant = null;
        if (cible) { const a = ((await agir("securite.audits", { id: cible })) || {}).audit; if (a) courant = { id: a.id, ts: a.ts, modele: a.modele, titre: a.titre, html: a.corps }; }
        return ok({ audits: l, courant, en_cours: AUDIT.en_cours && Date.now() - AUDIT.depuis < 600000, erreur: AUDIT.erreur });
      } catch (e) { return { ok: false, error: e.message }; }
    },
  });
  // Rédiger un audit : le modèle de l'administrateur relit les mesures (le verdict est déjà calculé : il l'éclaire, il ne le contredit pas) ; le travail part en arrière-plan, l'écran relit la liste.
  P("/api/securite/audit/rediger", null, {
    faire: async (req, agir) => {
      if (AUDIT.en_cours && Date.now() - AUDIT.depuis < 600000) return ok({ en_cours: true, deja: true });
      Object.assign(AUDIT, { en_cours: true, depuis: Date.now(), erreur: "" });
      (async () => {
        try {
          const d = await agir("securite.etat", {});
          const mesures = {}; ["machine", "exposition", "parefeu", "ssh", "comptes", "cles_fichiers", "fail2ban", "maj", "cage", "confinement", "verdict", "ailleurs"].forEach((k) => { if (d[k] !== undefined) mesures[k] = d[k]; });
          const consigne = "Tu relis les MESURES de sécurité d'un serveur Linux et tu les commentes pour son administrateur, en français, en le vouvoyant. Le verdict est déjà calculé à partir des mesures : tu ne le contredis pas et tu ne notes pas sur 100. "
            + "Tu éclaires : pourquoi chaque point compte, dans quel ordre s'en occuper, ce qui est déjà bien. Quand l'onglet Sécurité propose le geste, dis-le (« Garder MySQL sur la machine », « Arrêter rpcbind », « Couper les mots de passe SSH », « Couper le transfert X11 », « Appliquer les mises à jour », « Activer les mises à jour automatiques », « Débannir ») plutôt que de donner une commande. "
            + "N'invente rien qui ne soit pas dans les mesures. Fragment HTML seulement (h3, p, ul, li, b, code), sans <html> ni <style> ; classes .ok, .warning, .critical sur les titres de points. 600 mots au plus.\n\nMESURES :\n" + JSON.stringify(mesures).slice(0, 60000);
          const r = await agir("modeles.completer", { messages: [{ role: "user", content: consigne }], max_tokens: 8000, temperature: 0.3, timeout: 240 });
          const texte = String((r && (r.texte || r.contenu || r.reponse)) || "").replace(/^```(?:html)?\s*|\s*```$/g, "").trim();
          if (!texte) throw new Error((r && r.erreur) || "le modèle a rendu une réponse vide");
          await agir("securite.audit_poser", { modele: String(r.modele || ""), titre: "Audit de sécurité", corps: texte });
        } catch (e) { AUDIT.erreur = e.message; } finally { AUDIT.en_cours = false; }
      })();
      return ok({ en_cours: true });
    },
  });
  // Les gestes directs (V18 : securite_direct) vers SA capacité. Ce que la V19 ne fait pas encore (bannir une adresse, un pays, fermer un chemin d'un site, freiner un robot) est dit tel quel.
  const DIRECT = {
    debannir: (b) => ["securite.debannir", { jail: String(b.jail || "sshd"), ip: String(b.ip || "") }],
    service_arreter: (b) => ["securite.arret", { service: String(b.unite || "") }],
    scan: (b) => ["securite.outil_lancer", { nom: String(b.outil || "") }],
  };
  const PAS_ENCORE = { bannir: "bannir une adresse", bannir_pays: "bannir un pays", debannir_pays: "débannir un pays", liste_blanche: "la liste blanche", retirer_liste_blanche: "la liste blanche", fermer_chemin: "fermer un chemin d'un site", rouvrir_chemin: "rouvrir un chemin d'un site",
    robot_bloquer: "bloquer un robot", robot_freiner: "freiner un robot", robot_liberer: "libérer un robot", service_demarrer: "redémarrer un service", maj_image: "mettre à jour une image" };
  P("/api/securite/direct", null, {
    faire: async (req, agir) => {
      const b = req.body, g = String(b.geste || "");
      if (PAS_ENCORE[g]) return new Response(JSON.stringify({ ok: false, error: "« " + PAS_ENCORE[g] + " » n'est pas encore porté : il demande une commande racine (pare-feu du noyau, nginx) que le courtier n'a pas." }), { status: 400, headers: { "Content-Type": "application/json" } });
      if (!DIRECT[g]) return new Response(JSON.stringify({ ok: false, error: "geste inconnu" }), { status: 400, headers: { "Content-Type": "application/json" } });
      try {
        const [cap, args] = DIRECT[g](b), r = await agir(cap, args);
        await agir("securite.noter", { geste: g, cible: args.ip || args.service || args.nom || "", detail: "", ok: true, resultat: "ok", defaire: g === "debannir" ? JSON.stringify({ geste: "debannir", avec: { jail: args.jail, ip: args.ip } }) : "" }).catch(() => {});
        return ok(Object.assign({ libelle: g, detail: "" }, r));
      } catch (e) { return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 400, headers: { "Content-Type": "application/json" } }); }
    },
  });
  // Défaire un geste du journal : sa ligne dit comment (le geste et ce qu'il avait rendu) ; le courtier le fait et le vérifie.
  P("/api/securite/defaire", null, {
    faire: async (req, agir) => {
      try {
        const id = +(req.body.id || 0), l = ((await agir("securite.journal", { limite: 500 })) || {}).journal || [];
        const ligne = l.find((x) => x.id === id);
        let inv = null; try { inv = ligne && ligne.defaire ? JSON.parse(ligne.defaire) : null; } catch (e) {}
        if (!inv || !inv.geste) return new Response(JSON.stringify({ ok: false, error: "rien à défaire pour ce geste" }), { status: 400, headers: { "Content-Type": "application/json" } });
        return ok(await agir("securite.annuler", { geste: String(inv.geste), avec: inv.avec || {} }));
      } catch (e) { return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 400, headers: { "Content-Type": "application/json" } }); }
    },
  });
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
        if (g === "regle_poser") return ok(await viaRoute(agir, "parefeu_regle_poser", { id: +(b.id || 0), nom: b.nom || "", ports: b.ports || "", proto: b.proto || "TCP", sens: b.sens || "INPUT", politique: b.politique || "", sources: b.sources || "" }));
        if (g === "regle_retirer") return ok(await viaRoute(agir, "parefeu_regle_retirer", { id: +(b.id || 0) }));
        if (g === "politique") return ok(await viaRoute(agir, "parefeu_politique", { politique: b.politique || "" }));
        if (GESTES[g]) return ok(await agir(GESTES[g], g === "debannir" ? { jail: String(b.jail || ""), ip: String(b.ip || "") } : {}));
      } catch (e) { return { ok: false, error: e.message }; }
      return { ok: false, error: "ce geste n'est pas encore porté (outils de sécurité)" };
    },
  });
  CASS.route("POST", "/api/securite/parefeu/trancher", null, { faire: async (r, agir) => ok(await viaRoute(agir, "parefeu_trancher", { jeton: String(r.body.jeton || ""), garder: !!r.body.garder })) });
  P("/api/securite/noter", "securite.noter", {
    args: (r) => ({ geste: r.body.geste || "", cible: r.body.cible || "", detail: r.body.detail || "", ok: r.body.ok !== false, resultat: r.body.resultat || "", defaire: r.body.defaire || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/securite/audit/poser", "securite.audit_poser", { args: (r) => ({ modele: r.body.modele || "", titre: r.body.titre || "", corps: r.body.corps || "" }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
