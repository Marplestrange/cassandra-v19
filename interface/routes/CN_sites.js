// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sites : /api/sites/* (V18) -> capacités sites
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #266826
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Sites : /api/sites/* (V18) -> capacités sites.* du noyau. Le module garde les formes de la V18 (sites, vigilances, portée) :
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=266826 ▼▼▼
/* Sites : /api/sites/* (V18) -> capacités sites.* du noyau. Le module garde les formes de la V18 (sites, vigilances, portée) :
   la lecture passe telle quelle ; les gestes rendent {ok, reason} comme l'écran les lit.
   /api/sites/act : vérifier (la dernière mesure de la sonde) et renouveler le certificat (par le panneau, confirmation exigée) ; redémarrer et journaux demandent la racine du panneau : dits tels quels.
   Toutes les heures rendues à l'écran sont à l'heure du serveur (ts) : une seule horloge sur la page. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const dom = (b) => String(b.domain || "").trim();

  // Le module parle français (domaine, code, ms, ssl_jours), l'écran V18 anglais (domain, http_code, response_ms, ssl_days).
  const SITE = { domaine: "domain", code: "http_code", ms: "response_ms", ssl_jours: "ssl_days", ssl_etat: "ssl_state", proprietaire_panneau: "fp_compte", mesure: "sonde_ts" };
  // La disponibilité : le module dit {disponibilite, pannes, indisponible}, l'écran lit {pct, outages, downtime}. Sans cette traduction l'écran affichait « pas encore de sonde ».
  const dispo18 = (d) => (d ? { pct: d.disponibilite, outages: d.pannes || 0, downtime: d.indisponible_min ? d.indisponible : "", mesures: d.mesures, en_panne: !!d.en_panne } : null);
  // L'heure de la mesure part déjà mise en forme : l'écran la découpe comme un texte (un nombre de secondes y devenait « 81413.58034 »).
  const site18 = (x) => { const o = CASS.cles(x, SITE); o.sonde = { up: x.up, http_code: x.code, response_ms: x.ms, ssl_days: o.ssl_days, ts: ts(x.mesure) }; o.dispo30 = dispo18(x.dispo30); return o; };
  // Les gestes des vigilances : le module dit « repondre_demande », l'écran attend « demande » pour offrir « Adossé, c'est fait » et « Refuser ».
  const vig18 = (v) => Object.assign({}, v, { geste: v.geste === "repondre_demande" ? "demande" : v.geste });
  // La portée : l'écran lit « comptes » (combien de comptes ont un site) et « panneau_ok ».
  const portee18 = (x) => { const cs = new Set(); (x.sites || []).forEach((s) => (s.comptes || []).forEach((c) => cs.add(c))); return Object.assign({}, x.portee || {}, { comptes: cs.size, panneau_ok: (x.portee || {}).panneau_lu !== false }); };
  // L'heure comme l'écran la lit (le module date en secondes depuis 1970).
  const z = (n) => String(n).padStart(2, "0");
  const ts = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds()); };
  P("/api/sites/mine", "sites.vue", { args: () => ({}), sortie: (x) => ok(Object.assign({}, x, { sites: (x.sites || []).map(site18), vigilances: (x.vigilances || []).map(vig18), portee: portee18(x), releve: ts(Date.now() / 1000) })) });
  // Une ligne de journal : l'écran range « ecran » (un geste) et connaît « link_save / link_delete » ; le module dit « geste », « lien », « delie ».
  const VERBE18 = { lien: "link_save", delie: "link_delete" };
  const ligne18 = (l) => Object.assign({}, l, { ts: ts(l.ts), site: l.domaine, verbe: VERBE18[l.verbe] || l.verbe, source: l.source === "geste" ? "ecran" : l.source });
  // Ce que l'écran peut offrir sur la fiche. Il n'active un bouton que s'il est dans « seul » (sans confirmation) ou « confirm », et dit la raison de « refuses » :
  // sans ces listes, tous les boutons restaient grisés « indisponible », y compris vérifier et renouveler qui existent.
  const PAS_PORTE = "demande la racine du panneau : pas encore porté en V19";
  const gestes18 = (x) => {
    const g = x.gestes || {}, seul = ["status"], confirm = [], refuses = {};
    if (x.hors_panneau) ["ssl_renew", "restart", "logs", "scan", "sauvegarde", "restaurer"].forEach((a) => { refuses[a] = "hors panneau : ce geste n'existe pas pour un site déclaré à la main"; });
    else {
      confirm.push("ssl_renew");
      refuses.restart = "redémarrer " + PAS_PORTE + " (le service se relance depuis Hébergement › Services)";
      refuses.logs = "lire les journaux " + PAS_PORTE;
      refuses.scan = "l'analyse antivirus " + PAS_PORTE + " (Sécurité › ClamAV analyse le serveur)";
      refuses.sauvegarde = "lancer la sauvegarde " + PAS_PORTE + " (elle se fait par un plan, dans Sauvegardes)";
      if (x.mien || x.accord) confirm.push("restaurer"); else refuses.restaurer = "accord du propriétaire requis : il l'autorise depuis sa fiche, pour 24 h";
    }
    return Object.assign({}, g, { seul, confirm, refuses, accord: !!g.accorder });
  };
  P("/api/site/journal", "sites.journal", { args: (r) => ({ domaine: String(r.body.domain || ""), limite: +(r.body.limite || 60) }), sortie: (x) => ok({ lignes: (x.lignes || []).map(ligne18) }) });
  P("/api/site/fiche", "sites.fiche", {
    args: (r) => ({ domaine: dom(r.body) }),
    sortie: (x) => {
      const h = x.histoire || {};
      return ok({
        domain: x.domaine, site: site18(x.site), mien: x.mien, admin_autrui: x.admin_autrui, hors_panneau: x.hors_panneau, quota: {}, bases: null,
        histoire: { availability: h.disponibilite, response_avg_ms: h.reponse_moy_ms, response_max_ms: h.reponse_max_ms, samples: h.mesures, evenements: (h.evenements || []).map((e) => Object.assign({}, e, { ts: ts(e.ts) })) },
        liens: (x.liens || []).map((l) => ({ kind: l.genre, ref: l.ref, note: l.note, ts: ts(l.ts) })), journal: (x.journal || []).map(ligne18),
        demande: x.demande ? Object.assign({}, x.demande, { ts: ts(x.demande.ts) }) : x.demande,
        accord: x.accord ? Object.assign({}, x.accord, { jusqu_a: ts(x.accord.jusqu_a) }) : x.accord,
        // « bases », « dns » et « courrier » ne sont pas lus par la V19 : null (et non une liste vide) pour que l'écran dise « pas lu » plutôt que « aucun ».
        dns: null, courrier: null, non_lu: ["bases", "dns", "courrier", "disque", "cms"],
        gestes: gestes18(x),
      });
    },
  });
  P("/api/sites/declarer", "sites.declarer", { args: (r) => ({ domaine: dom(r.body) }), sortie: ok });
  P("/api/sites/retirer", "sites.retirer", { args: (r) => ({ domaine: dom(r.body) }), sortie: ok });
  P("/api/sites/attribuer", "sites.attribuer", { args: (r) => ({ domaine: dom(r.body), compte: String(r.body.compte || "").trim() }), sortie: ok });
  P("/api/sites/transferer", "sites.transferer", { args: (r) => ({ domaine: dom(r.body), vers: String(r.body.vers || "").trim() }), sortie: ok });
  P("/api/sites/demander", "sites.demander", { args: (r) => ({ domaine: dom(r.body), message: String(r.body.message || "") }), sortie: ok });
  P("/api/sites/demande/repondre", "sites.repondre_demande", { args: (r) => ({ id: +r.body.id, decision: String(r.body.decision || ""), reponse: String(r.body.reponse || "") }), sortie: ok });

  // L'accord de restauration (le propriétaire autorise un administrateur pour quelques heures) et les rattachements d'un site (projet, contact, client…).
  const quand = (t) => (t ? ts(t) : "");
  P("/api/site/accord", "sites.accorder", { args: (r) => ({ domaine: dom(r.body), geste: String(r.body.geste || "restaurer"), heures: +(r.body.heures || 24) }), sortie: (x) => ok(Object.assign({}, x, { jusqu_a: quand(x.jusqu_a) })) });
  P("/api/site/link/save", "sites.lier", { args: (r) => ({ domaine: dom(r.body), genre: String(r.body.kind || ""), ref: String(r.body.ref || ""), note: String(r.body.note || "") }), sortie: ok });
  P("/api/site/link/delete", "sites.delier", { args: (r) => ({ domaine: dom(r.body), genre: String(r.body.kind || ""), ref: String(r.body.ref || "") }), sortie: ok });

  // ── les gestes lourds d'un site du panneau : copies, restauration, rapport, vérifier, renouveler le certificat ──────────
  const echec = (e) => ({ ok: false, reason: (e && e.message) || String(e) });
  const confirmer = (req, raison, plus) => (req.body.confirm ? null : new Response(JSON.stringify(Object.assign({ ok: false, needs_confirm: true, reason: raison }, plus || {})), { status: 409, headers: { "Content-Type": "application/json" } }));
  const RACINE = "demande la racine du panneau (sa commande mogwai) : le courtier de la V19 n'a pas cette commande. La sauvegarde d'un site se fait par un plan (Sauvegardes), l'analyse d'un serveur par Sécurité › ClamAV.";
  // La fiche dit si le site est au panneau, à qui, et si le propriétaire a donné son accord (la même règle que la V18 : propriétaire, ou administrateur avec accord).
  async function viaRoute(agir, fonction, args) {
    const r = await agir("paneldetect.route", { fonction: fonction });
    if (!r || !r.capacite) throw new Error("aucun panneau d'hébergement ne sert « " + fonction + " »");
    return agir(r.capacite, args || {});
  }
  async function sitePanneau(agir, d) {
    const f = await agir("sites.fiche", { domaine: d });
    if (f.hors_panneau) throw new Error("site hors panneau : aucune copie");
    return f;
  }
  async function planDuCompte(agir, compte) {
    const plans = ((await viaRoute(agir, "plans", {})) || []);
    if (!plans.length) throw new Error("aucun plan de sauvegarde dans le panneau");
    const c = String(compte || "").toLowerCase();
    const sien = plans.find((p) => String(p.user_name || p.username || "").toLowerCase() === c);
    return { plan: sien || plans[0], sien: !!sien };
  }
  // Les copies de CE compte du panneau, et elles seules. Dans son propre plan, une copie sans compte nommé est la sienne ; dans le plan commun
  // (aucun plan à son nom), seules celles qui le nomment : sinon la fiche d'un site montrerait, et laisserait restaurer, les copies d'un autre compte.
  async function copiesDuCompte(agir, compte) {
    const c = String(compte || "").toLowerCase();
    if (!c) throw new Error("propriétaire du panneau inconnu pour ce site : aucune copie ne peut lui être rattachée");
    const { plan, sien } = await planDuCompte(agir, c);
    const r = await viaRoute(agir, "copies_du_plan", { plan_id: +plan.id });
    const copies = (r.copies || []).filter((x) => (x.compte ? String(x.compte).toLowerCase() === c : sien));
    return { plan, copies };
  }
  P("/api/site/copies", null, { faire: async (req, agir) => {
    const d = dom(req.body);
    try {
      if (!d) return { ok: false, reason: "domaine requis" };
      const f = await sitePanneau(agir, d), compte = (f.site && f.site.proprietaire_panneau) || "";
      const { plan, copies } = await copiesDuCompte(agir, compte);
      return ok({ copies, plan: { id: plan.id, name: plan.name } });
    } catch (e) { return echec(e); }
  } });
  P("/api/site/restaurer", null, { faire: async (req, agir) => {
    const d = dom(req.body), b = req.body;
    try {
      if (!d) return { ok: false, reason: "domaine requis" };
      const f = await sitePanneau(agir, d), compte = (f.site && f.site.proprietaire_panneau) || "";
      if (!f.mien && !f.accord) return new Response(JSON.stringify({ ok: false, reason: "accord du propriétaire requis : il l'autorise depuis sa fiche, pour 24 h" }), { status: 403, headers: { "Content-Type": "application/json" } });
      const copie = String(b.copie || "").trim();
      if (!copie) return { ok: false, reason: "copie requise" };
      // L'identifiant vient du navigateur : il doit être l'une des copies de ce compte, pas celle d'un autre.
      const { copies } = await copiesDuCompte(agir, compte);
      if (!copies.some((x) => String(x.id) === copie)) return new Response(JSON.stringify({ ok: false, reason: "cette copie n'est pas l'une de celles de ce compte du panneau" }), { status: 403, headers: { "Content-Type": "application/json" } });
      const c = confirmer(req, "Restaure la copie " + copie + " sur le compte " + (compte || "?") + " du panneau : les fichiers et bases actuels de CE COMPTE (tous ses sites) sont remplacés par ceux de la copie.");
      if (c) return c;
      const r = await viaRoute(agir, "copie_restaurer", { copie_id: copie, compte, forcer: !!b.force_clear });
      return ok({ copie: r.copie, compte: r.compte });
    } catch (e) { return echec(e); }
  } });
  P("/api/site/sauvegarde", null, { faire: async () => ({ ok: false, reason: "lancer le plan de sauvegarde du panneau " + RACINE }) });
  P("/api/site/scan", null, { faire: async () => ({ ok: false, reason: "l'analyse antivirus d'un site " + RACINE }) });
  // L'aperçu du site est une vignette que FastPanel fabrique sur son disque (root) : la V19 ne la sert pas encore.
  P("/api/site/thumb", null, { faire: async () => ({ ok: false, reason: "la vignette est un fichier du panneau, à root : la V19 ne la sert pas" }) });
  // Le rapport du mois : la sonde, les coupures et les sauvegardes du compte, composés de ce que les modules savent.
  P("/api/site/rapport", null, { faire: async (req, agir) => {
    const d = dom(req.body);
    try {
      if (!d) return { ok: false, reason: "domaine requis" };
      if (req.body.envoyer) return { ok: false, reason: "l'envoi du rapport par courrier n'est pas encore porté : le rapport s'affiche ici" };
      const mois = String(req.body.mois || "").slice(0, 7) || ts(Date.now() / 1000).slice(0, 7);
      if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(mois)) return { ok: false, reason: "mois illisible : AAAA-MM" };
      // Les chiffres sont ceux DU MOIS demandé (du 1er au 1er suivant, ou jusqu'à maintenant s'il est en cours), pas ceux des trente et un derniers jours.
      const an = +mois.slice(0, 4), m = +mois.slice(5, 7);
      const debut = new Date(an, m - 1, 1).getTime() / 1000, fin = Math.min(new Date(an, m, 1).getTime() / 1000, Date.now() / 1000);
      if (debut >= fin) return { ok: false, reason: "ce mois n'a pas commencé" };
      const h = await agir("sites.historique", { domaine: d, debut, fin });
      const ev = (h.evenements || []).filter((e) => ts(e.ts).slice(0, 7) === mois);
      let sauvegardes = [];
      try {
        const f = await agir("sites.fiche", { domaine: d }), compte = String((f.site && f.site.proprietaire_panneau) || "").toLowerCase();
        if (compte) sauvegardes = ((await viaRoute(agir, "copies", {})) || []).filter((s) => String(s.compte || "").toLowerCase() === compte && String(s.debut || "").slice(0, 7) === mois).map((s) => ({ at: s.debut, status: s.etat === "reussie" ? "success" : s.etat, size_mb: s.envoye_mo }));
      } catch (e) {}
      const pannes = ev.filter((e) => e.genre === "panne").length, retours = ev.filter((e) => e.genre === "retour");
      const dispo = h.disponibilite;
      const reussies = sauvegardes.filter((s) => s.status === "success").length;
      return ok({ domain: d, mois, sonde: { mesures: h.mesures, disponibilite: dispo, reponse_moy_ms: h.reponse_moy_ms, reponse_max_ms: h.reponse_max_ms },
        coupures: ev.map((e) => ({ ts: ts(e.ts), kind: e.genre, detail: e.detail, duree_min: e.duree_min })), pannes, retours: retours.length, indisponible_min: retours.reduce((a, e) => a + (e.duree_min || 0), 0),
        gestes: {}, sauvegardes, analyses: [],
        phrase: d + " en " + mois + " : " + (dispo == null ? "pas de sonde" : dispo.toFixed(2) + " % de disponibilité") + " sur " + (h.mesures || 0) + " mesures, " + pannes + " coupure(s) commencée(s), " + reussies + " sauvegarde(s) réussie(s)." });
    } catch (e) { return echec(e); }
  } });
  // Les gestes d'un site : vérifier (la dernière mesure de la sonde dit l'état), renouveler le certificat (par le panneau, confirmation exigée : le quota de l'autorité s'épuise).
  P("/api/sites/act", null, { faire: async (req, agir) => {
    const d = dom(req.body), a = String(req.body.action || "").trim();
    try {
      if (!d) return { ok: false, error: "domaine requis" };
      const f = await agir("sites.fiche", { domaine: d });
      if (a === "status") {
        // « ok » dit que le site est en ligne selon la sonde, pas seulement qu'il a rendu un code : un 500 répond, il ne marche pas.
        const s = f.site || {};
        return { ok: s.up === true, message: d + (s.code ? " répond " + s.code + " en " + (s.ms == null ? "?" : s.ms) + " ms" : " ne répond pas") + (s.ssl_jours != null ? " · certificat : " + s.ssl_jours + " j" : ""), sonde: { code: s.code, ms: s.ms, ssl_days: s.ssl_jours } };
      }
      if (f.hors_panneau) return new Response(JSON.stringify({ ok: false, error: "hors panneau : ce geste n'existe pas pour un site déclaré à la main" }), { status: 400, headers: { "Content-Type": "application/json" } });
      if (a === "ssl_renew") {
        const c = confirmer(req, "Réémet le certificat SSL. L'autorité n'autorise qu'un nombre limité d'émissions par domaine et par semaine.");
        if (c) return c;
        const r = await viaRoute(agir, "ssl_renouveler", { domaine: d });
        return { ok: true, message: "Certificat renouvelé pour " + (r.domaine || d) + "." };
      }
      if (a === "restart") return { ok: false, error: "redémarrer le backend d'un site demande la racine du panneau : le courtier de la V19 n'a pas cette commande (le service concerné se relance depuis Hébergement › Services)" };
      if (a === "logs") return { ok: false, error: "les journaux d'un site sont des fichiers de root : la V19 ne les lit pas encore" };
      return new Response(JSON.stringify({ ok: false, error: "Action inconnue" }), { status: 400, headers: { "Content-Type": "application/json" } });
    } catch (e) { return { ok: false, error: e.message }; }
  } });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
