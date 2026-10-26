// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Flotte » du module flotte : ce que dit le parc (verdict, machines par groupe), la fiche d'une machine (courbes, relevés, liens, diagnostics, services), la disponibilité, les événements, le registre et l'engagement.
// Les données viennent des capacités du module (flotte.parc, verdict, machines, historique, disponibilite, evenements, actions, diagnostic, ping, engagement, machine_*, service_agir, oublier, lien_*).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, pill = K.pill, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const SCENES = [["maintenant", "Maintenant"], ["dispo", "Disponibilité"], ["evenements", "Événements"], ["registre", "Registre et engagement"]];
  const ETAT = { ok: ["", "check"], avert: ["al", "warn"], erreur: ["dg", "warn"], retiree: ["", ""], neutre: ["", ""] };
  const NIVEAU = { panne: ["panne", "dg", "warn"], regarder: ["à regarder", "al", "warn"], stable: ["stable", "", "check"], inconnu: ["inconnu", "", ""] };
  const GENRE = { perte: "perdue", retour: "de retour", decouverte: "découverte", disparition: "disparue", controle: "contrôle", action: "action" };
  const STATUTS = [["attendue", "Attendue"], ["intermittente", "Intermittente"], ["retiree", "Retirée"]];
  const NIVEAUX = [["", "Automatique"], ["signal", "Signal"], ["observation", "Observation"], ["ssh", "SSH"]];
  const LIENS = [["project", "Projet"], ["contact", "Contact"], ["domain", "Domaine"], ["note", "Note"]];
  const court = (ts) => String(ts || "").replace("T", " ").slice(0, 16);
  const mesure = (cle, lib, pts) => ({ name: lib, points: pts.filter((p) => p[cle] != null).map((p) => ({ ts: p.ts, v: p[cle] })) });

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.flotte = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("flotte", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "maintenant", parc: null, verdict: null, dispo: null, jours: 30, evts: null, registre: null, actions: null, fiche: null, heures: 24, diag: null, charge: true, erreur: "" };

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { await agir(cap, args); if (ok) dire(ok, "ok"); return true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] && !S.fiche ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0] && !S.fiche) + '">' + esc(s[1]) + "</button>").join("") + "</div>";
    const pastille = (m) => { const e = ETAT[m.etat] || ETAT.neutre; return pill(m.libelle || "", e[0], e[1]); };
    const menu = (nom, liste, val) => '<select class="sel" data-a="' + nom + '" aria-label="' + esc(nom) + '">' + liste.map((x) => '<option value="' + esc(x[0]) + '"' + (x[0] === val ? " selected" : "") + ">" + esc(x[1]) + "</option>").join("") + "</select>";

    function carteMachine(m) {
      const sources = Object.keys(m.sources || {}).map((k) => { const s = m.sources[k]; const e = ETAT[s.etat] || ETAT.neutre; return pill(k + " · " + s.texte, e[0], ""); }).join("");
      return '<div class="li"><div class="sp"><b><a href="#" data-a="fiche" data-k="' + esc(m.nom) + '">' + esc(m.nom) + "</a> " + pastille(m) + (m.hote ? " " + pill("hôte", "", "") : "") + "</b>" +
        '<span class="note">' + esc([m.os, m.ip, "contrôle : " + m.niveau, m.dispo != null ? "disponibilité " + m.dispo + " %" : ""].filter(Boolean).join(" · ")) + "</span>" +
        '<div class="chips">' + sources + "</div></div>" + '<span class="faint mono" style="font-size:11.5px">' + esc(court(m.dernier_contact)) + "</span></div>";
    }
    function maintenant() {
      const v = S.verdict, p = S.parc;
      const n = NIVEAU[v.niveau] || NIVEAU.inconnu;
      const haut = '<div class="carte"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h3 style="flex:1;min-width:200px">' + esc(v.titre || "") + "</h3>" + pill(n[0], n[1], n[2]) + "</div>" + '<p class="note">' + esc(v.sous_titre || "") + "</p>" +
        ((v.lignes || []).length ? '<div class="liste">' + v.lignes.map((l) => '<div class="li"><div class="sp"><b>' + esc(l.titre) + '</b><span class="note">' + esc(l.detail || "") + "</span>" +
          '<div class="chips">' + (l.gestes || []).map((g) => '<button class="p" data-a="vg" data-f="' + esc(g.f) + '" data-k="' + esc(g.a) + '">' + esc(g.lib) + "</button>").join("") + "</div></div>" + pill(l.niveau === "panne" ? "panne" : "à regarder", l.niveau === "panne" ? "dg" : "al", "warn") + "</div>").join("") + "</div>" : "") + "</div>";
      const groupes = {}; (p.machines || []).forEach((m) => { (groupes[m.groupe] = groupes[m.groupe] || []).push(m); });
      const tuiles = '<div class="grille-m">' + [["En ligne", p.compte.en_ligne + " / " + p.compte.declarees], ["Contrôle SSH", p.compte.ssh], ["Mesurées", p.compte.mesurees], ["Disparues", p.compte.disparues]].map((x) => '<div class="carte"><span class="note">' + esc(x[0]) + '</span><div style="font-size:22px;font-weight:600">' + esc(x[1]) + "</div></div>").join("") + "</div>";
      const liste = ["Serveurs", "Postes", "Mobiles", "Retirées", "Disparues"].filter((g) => groupes[g]).map((g) => '<div class="carte"><h3>' + esc(g) + " · " + groupes[g].length + '</h3><div class="liste">' + groupes[g].map(carteMachine).join("") + "</div></div>").join("");
      return haut + tuiles + (liste || '<div class="carte vide">Aucune machine connue.</div>');
    }
    function dispo() {
      const d = S.dispo || { machines: [] };
      const barreJ = '<div class="chips">' + [7, 30, 90].map((j) => '<button class="p ' + (S.jours === j ? "on" : "") + '" data-a="jours" data-j="' + j + '">' + j + " j</button>").join("") + "</div>";
      const lignes = (d.machines || []).map((m) => '<div class="li"><div class="sp"><b>' + esc(m.nom) + '</b><div class="jauge ' + (m.disponibilite < 95 ? "dg" : m.disponibilite < 99 ? "al" : "") + '"><i style="width:' + Math.max(0, Math.min(100, m.disponibilite)) + '%"></i></div><span class="note">' + esc((m.pannes || 0) + " panne(s)" + (m.indispo ? " · " + m.indispo + " d’indisponibilité" : "") + " · " + (m.releves || 0) + " relevés") + "</span></div><b>" + esc(m.disponibilite) + " %</b></div>").join("");
      return '<div class="carte"><h3>Disponibilité sur ' + S.jours + " jours</h3>" + barreJ + (lignes ? '<div class="liste">' + lignes + "</div>" : '<div class="vide">' + esc(d.raison || "Aucune mesure.") + "</div>") + "</div>";
    }
    function evenements() {
      const e = S.evts || [];
      return '<div class="carte"><h3>Derniers événements</h3><div class="liste">' + (e.length ? e.map((x) => '<div class="li"><div class="sp"><b>' + esc(x.nom) + " " + pill(GENRE[x.genre] || x.genre, x.genre === "perte" || x.genre === "disparition" ? "al" : "", "") + '</b><span class="note">' + esc(x.detail || "") + (x.duree_min ? " · " + esc(x.duree_min) + " min" : "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(x.ts)) + "</span></div>").join("") : '<div class="vide">Rien à signaler.</div>') + "</div></div>";
    }
    function registre() {
      const p = S.parc, r = S.registre || [];
      const reg = r.map((m) => '<div class="li"><div class="sp"><b>' + esc(m.nom) + " " + pill(m.type, "", "") + (m.actif ? "" : " " + pill("suspendue", "al", "")) + '</b><span class="note">' + esc([m.hote || m.url, m.utilisateur, m.auth, (m.secrets_poses || []).length ? "secrets : " + m.secrets_poses.join(", ") : ""].filter(Boolean).join(" · ")) + '</span></div><div class="chips"><button class="p" data-a="bascule" data-k="' + esc(m.nom) + '" data-v="' + (m.actif ? 0 : 1) + '">' + (m.actif ? "Suspendre" : "Réactiver") + '</button><button class="p dg" data-a="retire" data-k="' + esc(m.nom) + '">Retirer</button></div></div>').join("");
      const eng = (p.machines || []).filter((m) => !m.disparue).map((m) => '<div class="li"><div class="sp"><b>' + esc(m.nom) + '</b><span class="note">contrôle actuel : ' + esc(m.niveau) + '</span></div><div class="chips">' + menu("statut:" + m.nom, STATUTS, m.statut) + menu("niveau:" + m.nom, NIVEAUX, "") + "</div></div>").join("");
      const form = '<div class="carte"><h3>Déclarer une machine</h3><div class="barre"><input id="fl-nom" placeholder="nom" aria-label="Nom"><input id="fl-hote" placeholder="hôte ou URL" aria-label="Hôte"><select class="sel" id="fl-type" aria-label="Type"><option value="ssh">SSH</option><option value="ping">ping</option><option value="cassandra">autre Cassandra</option></select><select class="sel" id="fl-auth" aria-label="Accès"><option value="tailscale">Tailscale SSH</option><option value="cle">Clé</option><option value="mot_de_passe">Mot de passe</option></select><button class="btn pri" data-a="declarer">Déclarer</button></div><p class="note">La clé ou le mot de passe se posent ensuite depuis la fiche ; ils sont chiffrés et ne ressortent jamais.</p></div>';
      return form + '<div class="carte"><h3>Le registre</h3><div class="liste">' + (reg || '<div class="vide">Aucune machine déclarée : le parc ne vient que de Tailscale.</div>') + "</div></div>" + '<div class="carte"><h3>Engagement</h3><p class="note">Une machine intermittente ne déclenche ni alerte ni malus ; une machine retirée n’est plus attendue.</p><div class="liste">' + eng + "</div></div>";
    }
    function fiche() {
      const F = S.fiche, h = F.h || {}, pts = h.points || [];
      const raccourcis = '<div class="chips">' + [[24, "24 h"], [168, "7 j"], [720, "30 j"]].map((x) => '<button class="p ' + (S.heures === x[0] ? "on" : "") + '" data-a="heures" data-h="' + x[0] + '">' + x[1] + "</button>").join("") + "</div>";
      const acts = (S.actions || []).filter((a) => !a.modifie).map((a) => '<button class="p" data-a="diag" data-c="' + esc(a.cle) + '" title="' + esc(a.description) + '"' + ">" + esc(a.cle) + "</button>").join("");
      const liens = (h.liens || []).map((l) => '<div class="li"><div class="sp"><b>' + esc(l.genre) + "</b><span class=\"note\">" + esc(l.ref) + (l.note ? " — " + esc(l.note) : "") + '</span></div><button class="p" data-a="lien-retire" data-g="' + esc(l.genre) + '" data-r="' + esc(l.ref) + '">Retirer</button></div>').join("");
      const rel = (h.releves_detail || []).map((r) => '<div class="li"><div class="sp"><b>' + esc(r.cle) + " " + (r.gravite === "warning" ? pill("à voir", "al", "warn") : "") + '</b><span class="note">' + esc(r.valeur) + "</span></div></div>").join("");
      const ev = (h.evenements || []).slice(0, 20).map((x) => '<div class="li"><div class="sp"><b>' + esc(GENRE[x.genre] || x.genre) + '</b><span class="note">' + esc(x.detail || "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(x.ts)) + "</span></div>").join("");
      const m = ((S.parc || {}).machines || []).find((x) => x.nom === F.nom) || {};
      return '<div class="carte"><div class="barre"><h3 style="flex:1">' + esc(F.nom) + " " + (m.libelle ? pastille(m) : "") + '</h3><button class="btn" data-a="retour">← Le parc</button></div>' +
        '<p class="note">' + esc([m.os, m.ip, "contrôle : " + m.niveau, h.disponibilite != null ? "disponibilité " + h.disponibilite + " % sur " + (S.heures >= 168 ? S.heures / 24 + " j" : S.heures + " h") : ""].filter(Boolean).join(" · ")) + "</p>" + raccourcis +
        K.courbe([mesure("cpu", "processeur", pts), mesure("ram", "mémoire", pts), mesure("disque", "disque", pts)], { unite: "%", titre: "Ressources" }) + "</div>" +
        '<div class="carte"><h3>Diagnostics</h3><p class="note">Des lectures seulement, par SSH.</p><div class="chips">' + acts + '<button class="p" data-a="ping">ping</button></div>' + (S.diag ? '<pre class="mono note" style="white-space:pre-wrap;max-height:260px;overflow:auto">' + esc(S.diag) + "</pre>" : "") + "</div>" +
        '<div class="carte"><h3>Un service</h3><div class="barre"><input id="fl-svc" placeholder="nom du service" aria-label="Service"><button class="p" data-a="svc" data-c="svc_start">Démarrer</button><button class="p" data-a="svc" data-c="svc_restart">Redémarrer</button><button class="p dg" data-a="svc" data-c="svc_stop">Arrêter</button></div><p class="note">Jamais ce qui coupe le lien (sshd, réseau).</p></div>' +
        '<div class="carte"><h3>Relevés</h3><div class="liste">' + (rel || '<div class="vide">Aucun relevé.</div>') + "</div></div>" +
        '<div class="carte"><h3>Liens</h3><div class="liste">' + (liens || '<div class="vide">Aucun lien.</div>') + '</div><div class="barre">' + menu("genre", LIENS, "project") + '<input id="fl-ref" placeholder="référence" aria-label="Référence"><button class="btn pri" data-a="lien">Lier</button></div></div>' +
        '<div class="carte"><h3>Événements</h3><div class="liste">' + (ev || '<div class="vide">Rien sur cette période.</div>') + "</div></div>" +
        (m.disparue ? '<div class="carte"><button class="btn dg" data-a="oublier" data-k="' + esc(F.nom) + '">Oublier cette machine disparue</button></div>' : "");
    }

    function dessiner() {
      let c;
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (!S.parc) c = '<div class="carte"><h3>La flotte ne répond pas</h3><p class="note">' + esc(S.erreur || "Le module n’a rien rendu.") + "</p></div>";
      else if (S.fiche) c = fiche();
      else c = ({ maintenant: maintenant, dispo: dispo, evenements: evenements, registre: registre }[S.scene] || maintenant)();
      racine.innerHTML = K.titre("Flotte", "Les machines du parc : qui répond, depuis quand, et ce qu'on peut leur demander.") + barre() + c;
    }
    async function chargerParc() {
      const [p, v] = await Promise.all([lire("flotte.parc"), lire("flotte.verdict")]);
      S.parc = p; S.verdict = v || { niveau: "inconnu", titre: "", sous_titre: "", lignes: [] };
    }
    async function ouvrirFiche(nom) {
      S.fiche = { nom: nom, h: null }; S.diag = ""; dessiner();
      if (!S.actions) { const a = await lire("flotte.actions"); S.actions = (a && a.actions) || []; }
      S.fiche.h = await lire("flotte.historique", { nom: nom, heures: S.heures }) || {}; dessiner();
    }
    async function aller(scene) {
      S.scene = scene; S.fiche = null; S.erreur = ""; dessiner();
      if (scene === "dispo") { const d = await lire("flotte.disponibilite", { jours: S.jours }); S.dispo = d; }
      else if (scene === "evenements") { const e = await lire("flotte.evenements", { limite: 100 }); S.evts = (e && e.evenements) || []; }
      else if (scene === "registre") { const r = await lire("flotte.machines"); S.registre = (r && r.machines) || []; }
      else await chargerParc();
      dessiner();
    }
    async function rafraichir() { await chargerParc(); if (S.scene === "registre") { const r = await lire("flotte.machines"); S.registre = (r && r.machines) || []; } if (S.fiche) S.fiche.h = await lire("flotte.historique", { nom: S.fiche.nom, heures: S.heures }) || {}; dessiner(); }

    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a; if (a.tagName === "A") e.preventDefault();
      const nom = a.dataset.k;
      if (k === "fiche") ouvrirFiche(nom);
      else if (k === "retour") { S.fiche = null; dessiner(); }
      else if (k === "vg") {
        const f = a.dataset.f;
        if (f === "machine") ouvrirFiche(nom);
        else if (f === "dispo") aller("dispo");
        else if (f === "declarer_ssh") aller("registre");
        else if (f === "intermittente") { if (await geste("flotte.engagement", { nom: nom, statut: "intermittente" }, nom + " : absence volontaire, l’alerte est éteinte.")) rafraichir(); }
        else if (f === "oublier") a.dataset.a = "oublier", a.click();
      }
      else if (k === "jours") { S.jours = +a.dataset.j; S.dispo = await lire("flotte.disponibilite", { jours: S.jours }); dessiner(); }
      else if (k === "heures") { S.heures = +a.dataset.h; S.fiche.h = await lire("flotte.historique", { nom: S.fiche.nom, heures: S.heures }) || {}; dessiner(); }
      else if (k === "diag") { const r = await lire("flotte.diagnostic", { nom: S.fiche.nom, action: a.dataset.c }); S.diag = r ? (r.sortie || r.resultat || JSON.stringify(r, null, 1)) : S.erreur; dessiner(); }
      else if (k === "ping") { const r = await lire("flotte.ping", { nom: S.fiche.nom }); S.diag = r ? r.latence_ms + " ms" + (r.via ? " (" + r.via + ")" : "") : S.erreur; dessiner(); }
      else if (k === "svc") {
        const svc = ((racine.querySelector("#fl-svc") || {}).value || "").trim(); if (!svc) { dire("Il faut un nom de service.", "err"); return; }
        if (!await confirmer("Agir sur « " + svc + " » ?", '<p class="note">' + esc(S.fiche.nom) + " · " + esc(a.dataset.c.replace("svc_", "")) + ". Le retour remet l’état d’avant.</p>", "Oui, le faire", a.dataset.c === "svc_stop")) return;
        if (await geste("flotte.service_agir", { nom: S.fiche.nom, action: a.dataset.c, service: svc }, "Fait.")) ouvrirFiche(S.fiche.nom);
      }
      else if (k === "lien") { const ref = ((racine.querySelector("#fl-ref") || {}).value || "").trim(); const g = (racine.querySelector('[data-a="genre"]') || {}).value || "project"; if (!ref) return; if (await geste("flotte.lien_enregistrer", { nom: S.fiche.nom, genre: g, ref: ref }, "Lien posé.")) ouvrirFiche(S.fiche.nom); }
      else if (k === "lien-retire") { if (await geste("flotte.lien_retirer", { nom: S.fiche.nom, genre: a.dataset.g, ref: a.dataset.r }, "Lien retiré.")) ouvrirFiche(S.fiche.nom); }
      else if (k === "oublier") { if (!await confirmer("Oublier « " + nom + " » ?", '<p class="note">Ses traces (présence, relevés) s’effacent ; l’historique reste.</p>', "Oublier", true)) return; if (await geste("flotte.oublier", { nom: nom }, "Oubliée.")) { S.fiche = null; rafraichir(); } }
      else if (k === "bascule") { if (await geste("flotte.machine_basculer", { nom: nom, actif: a.dataset.v === "1" }, a.dataset.v === "1" ? "Surveillance reprise." : "Surveillance suspendue.")) rafraichir(); }
      else if (k === "retire") { if (!await confirmer("Retirer « " + nom + " » du registre ?", '<p class="note">Son historique reste.</p>', "Retirer", true)) return; if (await geste("flotte.machine_retirer", { nom: nom }, "Retirée.")) rafraichir(); }
      else if (k === "declarer") {
        const v = (id) => ((racine.querySelector(id) || {}).value || "").trim();
        if (!v("#fl-nom")) { dire("Il faut un nom.", "err"); return; }
        if (await geste("flotte.machine_ajouter", { nom: v("#fl-nom"), type: v("#fl-type"), hote: v("#fl-hote"), auth: v("#fl-auth") }, "Machine déclarée.")) rafraichir();
      }
    });
    racine.addEventListener("change", async (e) => {
      const n = (e.target.dataset && e.target.dataset.a) || ""; const i = n.indexOf(":"); if (i < 0) return;
      const champ = n.slice(0, i), nom = n.slice(i + 1);
      if (await geste("flotte.engagement", Object.assign({ nom: nom }, champ === "statut" ? { statut: e.target.value } : { niveau: e.target.value }), nom + " : engagement posé.")) rafraichir();
    });
    await chargerParc(); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
