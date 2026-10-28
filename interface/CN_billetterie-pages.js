// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Billetterie : les pages du titulaire (vue d'ensemble, événements et leur fiche, ventes, pe
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #3dde24
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Billetterie : les pages du titulaire (vue d'ensemble, événements et leur fiche, ventes, personnes, argent).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=3dde24 ▼▼▼
// Billetterie : les pages du titulaire (vue d'ensemble, événements et leur fiche, ventes, personnes, argent).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, confirmer = K.confirmer, dire = K.dire;
  const B = CASS.billetterie, H = B.aides, P = B.pages, ENT = B.ENT;
  const { eur, jour, jourCourt, quand, puce, puceEvt, puceCmd, MOYENS, cellule } = H;
  B.choix = B.choix || {};

  const tuile = (n, lib, mod, cible) => '<' + (cible ? 'button class="tuile cl' : 'div class="tuile') + (mod ? " " + mod : "") + '"' + (cible ? ' data-a="va" data-c="' + cible + '"' : "") + "><b>" + esc(n) + "</b><span>" + esc(lib) + "</span></" + (cible ? "button" : "div") + ">";
  const jauge = (n, max) => { const p = max ? Math.min(100, Math.round(100 * n / max)) : 0; return '<div class="jauge' + (p >= 100 ? " dg" : p >= 85 ? " al" : "") + '"><i style="width:' + p + '%"></i></div>'; };
  const tableau = (cols, lignes, vide) => '<div class="tw"><table><thead><tr>' + cols.map((c) => '<th class="' + (c[2] === "n" || c[2] === "eur" ? "n" : "") + '">' + esc(c[1]) + "</th>").join("") + "</tr></thead><tbody>" + (lignes.length ? lignes.join("") : '<tr><td colspan="' + cols.length + '" class="vide">' + esc(vide || "Rien pour l’instant.") + "</td></tr>") + "</tbody></table></div>";
  const ouvrir = (ecran, choix) => { if (choix) Object.assign(B.choix, choix); if (CASS.ouvrirEcran) CASS.ouvrirEcran("billetterie:" + ecran, "Billetterie"); };

  // Les listes déroulantes d'un formulaire qui dépendent des données : « formules:artiste,cachet », « salles », « revendeurs », « artistes ».
  async function resoudre(S, champs) {
    const sortie = [];
    for (const c of champs) {
      if (typeof c.opts !== "string") { sortie.push(c); continue; }
      const [quoi, filtre] = c.opts.split(":");
      const r = await S.lire(quoi) || {};
      let l = r[quoi] || [];
      if (filtre) l = l.filter((x) => filtre.split(",").indexOf(x.role) >= 0);
      sortie.push(Object.assign({}, c, { opts: [["", "— aucune —"]].concat(l.map((x) => [x.id, x.nom || x.scene])) }));
    }
    return sortie;
  }
  // Ce qu'on envoie : les cases en 0/1, les nombres vides omis, les listes vides à vide.
  const charge = (champs, v) => { const o = {}; champs.forEach((c) => { if (c.t === "note" || !(c.n in v)) return; let x = v[c.n]; if (c.t === "check") x = x ? 1 : 0; else if (c.t === "number" && x === "") return; o[c.n] = x; }); return o; };

  async function editer(S, cle, ligne, plus) {
    const E = ENT[cle], champs = await resoudre(S, E.champs);
    const v = await B.formulaire(ligne ? "Modifier · " + (ligne.nom || ligne.scene || ligne.code) : E.nouv, champs, ligne || {}, "Enregistrer");
    if (!v) return false;
    const args = Object.assign(charge(champs, v), plus || {});
    if (ligne) args.id = ligne.id;
    return !!(await S.geste(E.save, args, "Enregistré."));
  }
  async function supprimer(S, cle, ligne) {
    const E = ENT[cle];
    if (!(await confirmer("Supprimer « " + (ligne.nom || ligne.scene || ligne.code) + " » ?", "<p>Si cet élément est déjà utilisé, la suppression est refusée. L’action peut être défaite depuis le journal des gestes.</p>", "Supprimer", true))) return false;
    return !!(await S.geste(E.del, { id: ligne.id }, "Supprimé."));
  }
  // un tableau d'entité avec ses boutons
  async function crud(S, cle, zone) {
    const E = ENT[cle], r = await S.lire(E.pl) || {}, l = r[E.pl] || [];
    S.entites = S.entites || {}; S.entites[cle] = l;
    zone.innerHTML = '<div class="row" style="margin-bottom:10px"><span class="sp hint">' + l.length + " " + esc(l.length > 1 ? E.titre.toLowerCase() : E.un) + '</span><button class="btn pri" data-a="ent-nouveau" data-e="' + cle + '">+ ' + esc(E.nouv) + "</button></div>" +
      tableau(E.cols.concat([["", ""]]), l.map((x) => "<tr>" + E.cols.map((c) => cellule(c, x)).join("") + '<td class="n" style="white-space:nowrap">' + (cle === "revendeur" || cle === "artiste" ? '<button class="btn sm" data-a="profil-vu" data-e="' + cle + '" data-id="' + x.id + '">Profil</button> ' : "") + (cle === "artiste" ? '<button class="btn sm" data-a="adherent" data-id="' + x.id + '" title="Écrire cet artiste comme adhérent dans Dolibarr (si le pont est relié)">Adhérent Dolibarr</button> ' : "") + '<button class="btn sm" data-a="ent-modifier" data-e="' + cle + '" data-id="' + x.id + '">Modifier</button> <button class="btn sm dng" data-a="ent-supprimer" data-e="' + cle + '" data-id="' + x.id + '">Supprimer</button></td></tr>'), "Aucun élément.");
  }
  const clicEntite = async (S, a) => {
    const k = a.dataset.a, cle = a.dataset.e, ligne = ((S.entites || {})[cle] || []).find((x) => String(x.id) === a.dataset.id);
    if (k === "ent-nouveau") return await editer(S, cle, null);
    if (k === "ent-modifier") return await editer(S, cle, ligne);
    if (k === "ent-supprimer") return await supprimer(S, cle, ligne);
    return undefined;
  };

  // ═══ VUE D'ENSEMBLE ═══
  P.vue = async (S) => {
    const R = S.racine;
    const [ev, ret, cf, cour, att, vir] = await Promise.all([S.lire("evenements"), S.lire("retraits", { etat: "demandee" }), S.lire("conflits", { etat: "a_arbitrer" }), S.lire("courriels", { etat: "echec" }), S.lire("attente_liste", { etat: "attente" }), S.lire("commandes", { etat: "en_attente" })]);
    const evts = ((ev && ev.evenements) || []).filter((e) => e.statut !== "terminé" && e.statut !== "annulé").sort((a, b) => String(a.date_iso).localeCompare(String(b.date_iso)));
    const cartes = [];
    let vendus = 0, ca = 0;
    for (const e of evts.slice(0, 8)) {
      const [st, cm] = await Promise.all([S.lire("stock", { evenement_id: e.id }), S.lire("commandes", { evenement_id: e.id, etat: "payee", limite: 1000 })]);
      const total = ((cm && cm.commandes) || []).reduce((n, c) => n + c.total, 0);
      vendus += st ? st.vendus : 0; ca += total;
      cartes.push('<button class="carte evt" data-a="evt" data-id="' + e.id + '"><div class="row"><b style="font-size:14px">' + esc(e.nom) + '</b><span class="sp"></span>' + puceEvt(e.statut) + '</div><div class="hint">' + esc(jour(e.date_iso)) + "</div>" +
        (st ? jauge(st.vendus + st.retenus, st.quota) + '<div class="row"><span>' + st.vendus + " / " + st.quota + " vendus" + (st.retenus ? " · " + st.retenus + " réservés" : "") + '</span><span class="sp"></span><b>' + eur(total) + "</b></div>" : "") + "</button>");
    }
    const alertes = [];
    const nr = ((ret && ret.retraits) || []).length, nc = ((cf && cf.conflits) || []).length, ne = ((cour && cour.courriels) || []).length, nv = ((vir && vir.commandes) || []).length;
    if (nr) alertes.push(["Demandes de retrait à traiter : " + nr, "argent", "Traiter"]);
    if (nv) alertes.push(["Virements attendus : " + nv, "ventes", "Voir"]);
    if (nc) alertes.push(["Entrées en double à arbitrer : " + nc, "controle", "Arbitrer"]);
    if (ne) alertes.push(["Courriels en échec : " + ne, "argent", "Voir"]);
    R.innerHTML = S.entetes("Billetterie", "L’essentiel de tes événements, de tes ventes et de ce qui attend une décision.", '<button class="btn pri" data-a="nouvel-evt">+ Nouvel événement</button>') +
      '<div class="tuiles">' + tuile(evts.length, "événements à venir", "", "evenements") + tuile(vendus, "billets vendus", "", "ventes") + tuile(eur(ca), "encaissé", "", "ventes") + tuile(nr, "retraits à traiter", nr ? "al" : "", "argent") + tuile(((att && att.attente) || []).length, "en liste d’attente", "") + "</div>" +
      (alertes.length ? alertes.map((a) => '<div class="alerte"><span class="sp">' + esc(a[0]) + '</span><button class="btn sm" data-a="va" data-c="' + a[1] + '">' + a[2] + "</button></div>").join("") : "") +
      (S.erreur ? '<div class="carte" style="color:var(--danger)">' + esc(S.erreur) + "</div>" : "") +
      (cartes.length ? '<div class="grille">' + cartes.join("") + "</div>" : '<div class="carte vide">Aucun événement à venir. Crée le premier : une date, une salle, un nombre de places, un prix.</div>');
    S.clic = async (k, a) => {
      if (k === "evt") ouvrir("b_evenements", { evenement: Number(a.dataset.id) });
      else if (k === "va") ouvrir({ evenements: "b_evenements", ventes: "b_ventes", argent: "b_argent", controle: "b_controle" }[a.dataset.c] || "b_vue");
      else if (k === "nouvel-evt") { if (await editerEvenement(S, null)) S.rendre(); }
    };
  };

  async function editerEvenement(S, e) {
    const champs = (await resoudre(S, [{ n: "nom", l: "Nom de l’événement" }, { n: "date_iso", l: "Date", t: "date" }, { n: "salle_id", l: "Salle", t: "select", opts: "salles" }, { n: "conf", l: "Configuration", t: "select", opts: [["debout", "Debout"], ["assis", "Assis"]] },
      { n: "quota", l: "Places en vente", t: "number" }, { n: "prix", l: "Prix plein tarif (€)", t: "eur" }, { n: "type", l: "Type (concert, soirée…)" }, { n: "accroche", l: "Accroche (une phrase)" }, { n: "description", l: "Description", t: "textarea" }, { n: "tags", l: "Mots-clés" },
      { n: "portes", l: "Ouverture des portes", t: "time" }, { n: "debut", l: "Début", t: "time" }, { n: "fin", l: "Fin", t: "time" }, { n: "age", l: "Public" }, { n: "responsable", l: "Responsable" }, { n: "pause", l: "Pause entre deux passages (min)", t: "number" },
      { n: "achat", l: "Achat en ligne", t: "select", opts: [["general", "Selon le réglage général"], ["obligatoire", "Compte obligatoire"], ["libre", "Sans compte possible"]] }]));
    const v = await B.formulaire(e ? "Modifier l’événement" : "Nouvel événement", champs, e || {}, "Enregistrer");
    if (!v) return false;
    const args = charge(champs, v);
    if (e) args.id = e.id;
    return await S.geste("evenement_save", args, "Événement enregistré.");
  }

  // ═══ ÉVÉNEMENTS ═══
  P.evenements = async (S) => {
    S.onglet = S.onglet || "resume";
    const id = B.choix.evenement;
    if (id) return await fiche(S, id);
    const R = S.racine, r = await S.lire("evenements"), l = (r && r.evenements) || [];
    R.innerHTML = S.entetes("Événements", "Crée, mets en vente, suis tes événements.", '<button class="btn pri" data-a="nouveau">+ Nouvel événement</button>') + (S.erreur ? '<div class="carte" style="color:var(--danger)">' + esc(S.erreur) + "</div>" : "") +
      tableau([["nom", "Événement"], ["date", "Date"], ["statut", "État"], ["quota", "Places", "n"], ["prix", "Prix", "n"]], l.sort((a, b) => String(b.date_iso).localeCompare(String(a.date_iso))).map((e) => '<tr class="cl" data-a="ouvrir" data-id="' + e.id + '"><td><b>' + esc(e.nom) + "</b></td><td>" + esc(jour(e.date_iso)) + "</td><td>" + puceEvt(e.statut) + '</td><td class="n">' + e.quota + '</td><td class="n">' + eur(e.prix) + "</td></tr>"), "Aucun événement.");
    S.clic = async (k, a) => { if (k === "ouvrir") { B.choix.evenement = Number(a.dataset.id); S.onglet = "resume"; S.rendre(); } else if (k === "nouveau" && await editerEvenement(S, null)) S.rendre(); };
  };

  async function fiche(S, id) {
    const R = S.racine, [f, st, rent] = await Promise.all([S.lire("evenement_fiche", { id: id }), S.lire("stock", { evenement_id: id }), S.lire("evenement_rentabilite", { evenement_id: id })]);
    if (!f) { delete B.choix.evenement; R.innerHTML = '<div class="carte vide">Cet événement n’existe plus.</div>'; return; }
    const e = f.evenement, ong = S.onglet;
    const TABS = [["resume", "Résumé"], ["billets", "Billets"], ["programme", "Programme"], ["revendeurs", "Revendeurs"], ["invitations", "Invitations"], ["ventes", "Ventes"], ["attente", "Liste d’attente"]];
    let corps = "";
    if (ong === "resume") {
      const j = f.jauge || {}, vend = e.statut === "brouillon";
      corps = '<div class="g carte"><dl class="kv"><dt>Date</dt><dd>' + esc(jour(e.date_iso)) + (e.ancienne_date ? ' <span class="hint">(reportée, était le ' + esc(jourCourt(e.ancienne_date)) + ")</span>" : "") + "</dd><dt>Salle</dt><dd>" + esc(f.salle ? f.salle.nom : "—") + "</dd><dt>Horaires</dt><dd>portes " + esc(e.portes) + " · début " + esc(e.debut) + " · fin " + esc(e.fin) + "</dd><dt>Jauge</dt><dd>" + (j.total || 0) + " (vente " + (j.quota || 0) + " + invitations " + (j.invitations || 0) + ") pour " + (j.capacite || "?") + " places" + (j.depasse ? " " + puce("dépassée", "dg") : "") + "</dd><dt>Prix</dt><dd>" + eur(e.prix) + "</dd>" +
        (e.motif_annulation ? "<dt>Annulation</dt><dd>" + esc(e.motif_annulation) + "</dd>" : "") + "</dl></div>" +
        (st ? '<div class="carte"><h3>Ventes</h3>' + jauge(st.vendus + st.retenus, st.quota) + '<p class="sub" style="margin:6px 0 10px">' + st.vendus + " vendus · " + st.retenus + " réservés · " + st.restant + " restants sur " + st.quota + "</p>" +
          tableau([["t", "Billet"], ["v", "Vendus", "n"], ["r", "Réservés", "n"], ["q", "Restant", "n"]], st.types.map((t) => "<tr><td>" + esc(t.nom) + '</td><td class="n">' + t.vendus + '</td><td class="n">' + t.retenus + '</td><td class="n">' + (t.restant == null ? "illimité" : t.restant) + "</td></tr>")) + "</div>" : "") +
        (rent && rent.couts_fixes ? '<div class="carte"><h3>Rentabilité</h3><div class="tuiles" style="margin-bottom:8px">' + tuile(eur(rent.couts_fixes), "coûts fixes (salle " + eur(rent.couts_salle) + ", artistes " + eur(rent.couts_artistes) + ")", "") + tuile(eur(rent.recettes), "recettes (" + rent.vendus + " places)", "") +
          tuile(rent.seuil_places == null ? "—" : rent.seuil_places, "places pour s’équilibrer", "") + tuile(eur(rent.resultat), "résultat à ce jour", rent.resultat < 0 ? "al" : "") + "</div><p class=\"" + (rent.decision_due && rent.sous_le_seuil ? "erreur" : "doux") + "\">" + esc(rent.conseil) + "</p></div>" : "") +
        '<div class="row">' + (vend ? '<button class="btn pri" data-a="publier">Mettre en vente</button>' : "") + (e.statut === "en vente" || e.statut === "complet" ? '<button class="btn" data-a="depublier">Retirer de la vente</button>' : "") +
        '<button class="btn" data-a="modifier">Modifier</button>' + (["brouillon", "en vente", "complet"].indexOf(e.statut) >= 0 ? '<button class="btn" data-a="reporter">Reporter…</button><button class="btn dng" data-a="annuler">Annuler l’événement…</button>' : "") +
        (vend ? '<button class="btn dng" data-a="supprimer">Supprimer</button>' : "") + (e.projet_ref ? '<span class="bp ok">Projet dans le bureau</span>' : (e.date_iso && ["brouillon", "en vente", "complet"].indexOf(e.statut) >= 0 ? '<button class="btn" data-a="projet">Créer le projet dans le bureau</button>' : "")) + "</div>";
    } else if (ong === "billets") {
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">Les billets que l’on peut acheter.</span><button class="btn pri" data-a="type-nouveau">+ Billet</button></div>' +
        tableau([["n", "Billet"], ["p", "Prix", "n"], ["q", "Quota", "n"], ["e", "Entrées", "n"], ["v", "Visible"], ["", ""]], f.types.map((t) => "<tr><td><b>" + esc(t.nom) + '</b><div class="hint">' + esc(t.description) + '</div></td><td class="n">' + eur(t.prix) + '</td><td class="n">' + (t.quota || "illimité") + '</td><td class="n">' + t.entrees + "</td><td>" + (t.visible ? puce("oui", "ok") : puce("masqué", "")) + '</td><td class="n" style="white-space:nowrap"><button class="btn sm" data-a="type-modifier" data-id="' + t.id + '">Modifier</button> <button class="btn sm dng" data-a="type-supprimer" data-id="' + t.id + '">Supprimer</button></td></tr>'));
    } else if (ong === "programme") {
      const p = f.programme;
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">L’ordre de passage. Pause entre deux passages : ' + e.pause + ' min.</span><button class="btn pri" data-a="passage-nouveau">+ Passage</button></div>' +
        tableau([["o", "#", "n"], ["a", "Artiste"], ["d", "Durée", "n"], ["", ""]], p.map((x, i) => '<tr><td class="n">' + x.ordre + "</td><td><b>" + esc(x.scene) + '</b></td><td class="n">' + x.duree + ' min</td><td class="n" style="white-space:nowrap"><button class="btn sm" data-a="monter" data-i="' + i + '"' + (i ? "" : " disabled") + '>↑</button> <button class="btn sm" data-a="descendre" data-i="' + i + '"' + (i < p.length - 1 ? "" : " disabled") + '>↓</button> <button class="btn sm" data-a="passage-modifier" data-id="' + x.id + '">Durée</button> <button class="btn sm dng" data-a="passage-supprimer" data-id="' + x.id + '">Retirer</button></td></tr>'));
    } else if (ong === "revendeurs") {
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">Qui vend pour cet événement, avec quelle formule et jusqu’à combien de places.</span><button class="btn pri" data-a="aff-nouvelle">+ Affecter un revendeur</button></div>' +
        tableau([["r", "Revendeur"], ["f", "Formule"], ["q", "Quota", "n"], ["", ""]], f.affectations.map((a) => "<tr><td><b>" + esc(a.revendeur) + '</b> <span class="hint">' + esc(a.code) + "</span></td><td>" + esc(a.formule) + '</td><td class="n">' + (a.quota || "—") + '</td><td class="n" style="white-space:nowrap"><button class="btn sm" data-a="aff-modifier" data-id="' + a.id + '">Modifier</button> <button class="btn sm dng" data-a="aff-supprimer" data-id="' + a.id + '">Retirer</button></td></tr>'));
    } else if (ong === "invitations") {
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">Les invitations sortent du quota de vente ; elles comptent dans la jauge de la salle.</span><button class="btn pri" data-a="inv-nouvelle">+ Catégorie</button></div>' +
        tableau([["c", "Catégorie"], ["q", "Quota", "n"], ["e", "Émises", "n"], ["", ""]], f.invitations.map((i) => "<tr><td><b>" + esc(i.categorie) + '</b></td><td class="n">' + i.quota + '</td><td class="n">' + i.emises + '</td><td class="n" style="white-space:nowrap"><button class="btn sm pri" data-a="inv-emettre" data-c="' + esc(i.categorie) + '">Émettre</button> <button class="btn sm" data-a="inv-modifier" data-id="' + i.id + '">Modifier</button> <button class="btn sm dng" data-a="inv-supprimer" data-id="' + i.id + '">Supprimer</button></td></tr>'));
    } else if (ong === "ventes") {
      const c = await S.lire("commandes", { evenement_id: e.id });
      corps = tableau([["r", "Commande"], ["n", "Acheteur"], ["s", "État"], ["t", "Total", "n"]], ((c && c.commandes) || []).map((x) => '<tr class="cl" data-a="cmd" data-ref="' + esc(x.ref) + '"><td><b>' + esc(x.ref) + '</b></td><td>' + esc(x.nom || "—") + "</td><td>" + puceCmd(x.etat) + '</td><td class="n">' + eur(x.total) + "</td></tr>"), "Aucune vente pour cet événement.");
    } else if (ong === "attente") {
      const a = await S.lire("attente_liste", { evenement_id: e.id });
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">Les places libérées sont proposées dans l’ordre d’inscription.</span><button class="btn" data-a="proposer">Proposer les places libres maintenant</button></div>' +
        tableau([["n", "Nom"], ["m", "Courriel"], ["q", "Places", "n"], ["e", "État"]], ((a && a.attente) || []).map((x) => "<tr><td>" + esc(x.nom) + "</td><td>" + esc(x.mail) + '</td><td class="n">' + x.quantite + "</td><td>" + puce({ attente: "en attente", offerte: "offre faite", convertie: "achetée", expiree: "expirée", retiree: "retirée" }[x.etat] || x.etat, x.etat === "offerte" ? "al" : x.etat === "convertie" ? "ok" : "") + "</td></tr>"), "Personne n’attend.");
    }
    R.innerHTML = S.entetes(e.nom, jour(e.date_iso), '<span>' + puceEvt(e.statut) + '</span><button class="btn" data-a="retour">← Tous les événements</button>') +
      '<div class="onglets">' + TABS.map((t) => '<button class="' + (t[0] === ong ? "on" : "") + '" data-a="onglet" data-o="' + t[0] + '">' + t[1] + "</button>").join("") + "</div>" + (S.erreur ? '<div class="carte" style="color:var(--danger)">' + esc(S.erreur) + "</div>" : "") + "<div>" + corps + "</div>";

    const recharger = () => S.rendre();
    const parId = (liste, i) => (liste || []).find((x) => String(x.id) === String(i));
    S.clic = async (k, a) => {
      const i = a.dataset.id;
      if (k === "retour") { delete B.choix.evenement; S.onglet = "resume"; return S.rendre(); }
      if (k === "onglet") { S.onglet = a.dataset.o; return recharger(); }
      if (k === "cmd") { ouvrir("b_ventes", { commande: a.dataset.ref }); return; }
      if (k === "modifier") { if (await editerEvenement(S, e)) recharger(); }
      else if (k === "publier") { if (await S.geste("evenement_publier", { id: e.id }, "Mis en vente.")) recharger(); }
      else if (k === "depublier") { if (await S.geste("evenement_depublier", { id: e.id }, "Retiré de la vente.")) recharger(); }
      else if (k === "projet") {
        const r = await S.geste("evenement_projet", { evenement_id: e.id });
        if (r && r.racontee) await confirmer("Projet non créé", "<p>" + esc(r.message) + "</p>", "Compris");
        else if (r) { dire("Projet créé avec " + r.taches.length + " tâche(s).", "ok"); recharger(); }
      } else if (k === "supprimer") { if (await confirmer("Supprimer l’événement ?", "<p>Seul un brouillon sans vente peut être supprimé.</p>", "Supprimer", true) && await S.geste("evenement_delete", { id: e.id }, "Supprimé.")) { delete B.choix.evenement; recharger(); } }
      else if (k === "annuler" || k === "reporter") { if (await procedure(S, e, k)) recharger(); }
      else if (k === "type-nouveau" || k === "type-modifier") {
        const t = k === "type-modifier" ? parId(f.types, i) : null;
        const champs = [{ n: "nom", l: "Nom du billet" }, { n: "description", l: "Description" }, { n: "prix", l: "Prix (€)", t: "eur" }, { n: "quota", l: "Quota de ce billet (0 = illimité)", t: "number" }, { n: "entrees", l: "Entrées par billet", t: "number", def: 1 }, { n: "visible", l: "Visible dans la boutique", t: "check", def: true }, { n: "ouverture", l: "Ouverture de la vente", t: "date" }, { n: "fermeture", l: "Fermeture de la vente", t: "date" }];
        const v = await B.formulaire(t ? "Modifier le billet" : "Nouveau billet", champs, t || {}, "Enregistrer");
        if (v) { const args = charge(champs, v); args.evenement_id = e.id; if (t) args.id = t.id; if (await S.geste("type_billet_save", args, "Billet enregistré.")) recharger(); }
      } else if (k === "type-supprimer") { if (await confirmer("Supprimer ce billet ?", "<p>Refusé s’il a déjà été vendu.</p>", "Supprimer", true) && await S.geste("type_billet_delete", { id: Number(i) }, "Supprimé.")) recharger(); }
      else if (k === "passage-nouveau") {
        const champs = await resoudre(S, [{ n: "artiste_id", l: "Artiste", t: "select", opts: "artistes" }, { n: "duree", l: "Durée (minutes)", t: "number", def: 30 }]);
        const v = await B.formulaire("Ajouter un passage", champs, {}, "Ajouter");
        if (v && v.artiste_id && await S.geste("passage_save", { evenement_id: e.id, artiste_id: Number(v.artiste_id), duree: v.duree || 30 }, "Passage ajouté.")) recharger();
      } else if (k === "passage-modifier") {
        const p = parId(f.programme, i), v = await B.formulaire("Durée du passage de " + p.scene, [{ n: "duree", l: "Durée (minutes)", t: "number" }], { duree: p.duree }, "Enregistrer");
        if (v && await S.geste("passage_save", { id: p.id, duree: v.duree }, "Enregistré.")) recharger();
      } else if (k === "passage-supprimer") { if (await S.geste("passage_delete", { id: Number(i) }, "Passage retiré.")) recharger(); }
      else if (k === "monter" || k === "descendre") {
        const ordre = f.programme.map((x) => x.id), n = Number(a.dataset.i), m = k === "monter" ? n - 1 : n + 1;
        [ordre[n], ordre[m]] = [ordre[m], ordre[n]];
        if (await S.geste("programme_ordonner", { evenement_id: e.id, passages: ordre })) recharger();
      } else if (k === "aff-nouvelle" || k === "aff-modifier") {
        const x = k === "aff-modifier" ? parId(f.affectations, i) : null;
        const champs = await resoudre(S, [{ n: "revendeur_id", l: "Revendeur", t: "select", opts: "revendeurs" }, { n: "formule_id", l: "Formule", t: "select", opts: "formules:independant" }, { n: "quota", l: "Quota de places (0 = sans limite)", t: "number" }]);
        const v = await B.formulaire(x ? "Modifier l’affectation" : "Affecter un revendeur", champs, x || {}, "Enregistrer");
        if (v) { const args = { evenement_id: e.id, revendeur_id: Number(v.revendeur_id), formule_id: Number(v.formule_id), quota: v.quota || 0 }; if (x) args.id = x.id; if (await S.geste("affectation_save", args, "Enregistré.")) recharger(); }
      } else if (k === "aff-supprimer") { if (await S.geste("affectation_delete", { id: Number(i) }, "Affectation retirée.")) recharger(); }
      else if (k === "inv-nouvelle" || k === "inv-modifier") {
        const x = k === "inv-modifier" ? parId(f.invitations, i) : null, champs = [{ n: "categorie", l: "Catégorie (Presse, Artistes, Partenaires…)" }, { n: "quota", l: "Nombre d’invitations", t: "number" }];
        const v = await B.formulaire(x ? "Modifier la catégorie" : "Nouvelle catégorie", champs, x || {}, "Enregistrer");
        if (v) { const args = { evenement_id: e.id, categorie: v.categorie, quota: v.quota || 0 }; if (x) args.id = x.id; if (await S.geste("invitation_save", args, "Enregistré.")) recharger(); }
      } else if (k === "inv-supprimer") { if (await S.geste("invitation_delete", { id: Number(i) }, "Catégorie supprimée.")) recharger(); }
      else if (k === "inv-emettre") {
        const v = await B.formulaire("Émettre une invitation « " + a.dataset.c + " »", [{ n: "nom", l: "Nom de l’invité" }, { n: "mail", l: "Courriel (pour lui envoyer le billet)" }], {}, "Émettre");
        if (v && await S.geste("invitation_emettre", { evenement_id: e.id, categorie: a.dataset.c, nom: v.nom, mail: v.mail }, "Invitation émise.")) recharger();
      } else if (k === "proposer") { const r = await S.geste("attente_proposer", { evenement_id: e.id }); if (r) { dire(((r.offres || []).length) + " offre(s) faite(s).", "ok"); recharger(); } }
    };
    S.saisie = null; S.change = null;
  }

  // annuler / reporter : on annonce les chiffres, puis on confirme
  async function procedure(S, e, geste) {
    const im = await S.lire("evenement_impact", { id: e.id });
    if (!im) return false;
    const pm = Object.keys(im.par_moyen || {}).map((m) => (MOYENS[m] || m) + " : " + im.par_moyen[m].commandes + " commande(s), " + eur(im.par_moyen[m].montant)).join(" · ");
    const resume = '<p><b>' + im.commandes_payees + " commande(s) payée(s)</b> pour " + eur(im.a_rembourser) + (pm ? " (" + esc(pm) + ")" : "") + ". " + im.commandes_en_cours + " réservation(s) en cours, " + im.invitations + " invitation(s), " + im.artistes.length + " artiste(s) et " + im.revendeurs.length + " revendeur(s) à prévenir.</p>";
    if (geste === "annuler") {
      const sal = im.salle && im.salle.acompte ? "<p>⚠ Acompte versé à la salle : " + eur(im.salle.acompte) + ". Conditions : " + esc(im.salle.annulation || "à vérifier avec la salle") + "</p>" : "";
      const v = await B.formulaire("Annuler « " + e.nom + " »", [{ n: "n1", t: "note", l: resume + "<p>Toutes les commandes payées seront remboursées (billets annulés, places rendues, commissions reprises). Le remboursement par carte ou virement reste à faire chez le prestataire ou à la main : la liste t’est donnée ensuite.</p>" + sal }, { n: "motif", l: "Motif (envoyé aux acheteurs)", t: "textarea" }], {}, "Annuler l’événement", true);
      if (!v || !v.motif) { if (v) dire("Le motif est obligatoire.", "err"); return false; }
      const r = await S.geste("evenement_annuler", { id: e.id, motif: v.motif, confirme: true }, "Événement annulé.");
      if (r && r.reste_a_faire && r.reste_a_faire.length) await confirmer("Remboursements à faire", "<p>" + esc(String(r.reste_a_faire.length)) + " remboursement(s) sont à effectuer :</p><ul class=\"lst\">" + r.reste_a_faire.map((x) => "<li>" + esc(x.commande) + " · " + eur(x.montant) + " · " + esc(MOYENS[x.moyen] || x.moyen) + (x.chez_le_prestataire ? " (depuis le tableau de bord du prestataire)" : " (à la main)") + "</li>").join("") + "</ul>", "Compris");
      return !!r;
    }
    const v = await B.formulaire("Reporter « " + e.nom + " »", [{ n: "n1", t: "note", l: resume + "<p>Les billets restent valables à la nouvelle date. Les acheteurs, artistes et revendeurs sont prévenus ; un acheteur qui ne peut pas venir est remboursé sur demande. Les commissions ne seront retirables qu’après la nouvelle date.</p>" }, { n: "nouvelle_date", l: "Nouvelle date", t: "date" }, { n: "motif", l: "Motif (envoyé aux acheteurs)", t: "textarea" }], {}, "Reporter");
    if (!v) return false;
    return !!(await S.geste("evenement_reporter", { id: e.id, nouvelle_date: v.nouvelle_date, motif: v.motif, confirme: true }, "Événement reporté."));
  }

  // ═══ VENTES ═══
  P.ventes = async (S) => {
    const R = S.racine;
    S.f = S.f || { evenement: "", etat: "", q: "" };
    const [ev, r] = await Promise.all([S.lire("evenements"), S.lire("commandes", { evenement_id: S.f.evenement ? Number(S.f.evenement) : 0, etat: S.f.etat, q: S.f.q, limite: 300 })]);
    const evts = (ev && ev.evenements) || [], noms = {}; evts.forEach((e) => { noms[e.id] = e.nom; });
    const l = (r && r.commandes) || [];
    let detail = "";
    const ref = B.choix.commande;
    if (ref) {
      const [d, bl] = await Promise.all([S.lire("commande", { ref: ref }), S.lire("billets", { q: "" })]);
      if (d) {
        const c = d.commande, mes = ((bl && bl.billets) || []).filter((b) => b.commande_id === c.id);
        S.billets = mes;
        detail = '<div class="carte"><div class="row"><h2>' + esc(c.ref) + "</h2>" + puceCmd(c.etat) + '<span class="sp"></span><button class="btn sm" data-a="fermer">Fermer</button></div>' +
          '<dl class="kv"><dt>Événement</dt><dd>' + esc(noms[c.evenement_id] || "") + "</dd><dt>Acheteur</dt><dd>" + esc(c.nom || "—") + " " + esc(c.mail || "") + "</dd><dt>Canal</dt><dd>" + esc(c.canal) + " · " + esc(MOYENS[c.moyen] || c.moyen || "—") + "</dd><dt>Total</dt><dd><b>" + eur(c.total) + "</b>" + (c.remise ? " (remise " + eur(c.remise) + ")" : "") + (c.don ? " dont don " + eur(c.don) : "") + (c.frais ? " dont frais " + eur(c.frais) : "") + "</dd>" + (c.attribution ? "<dt>Attribution</dt><dd>" + esc(c.attribution) + "</dd>" : "") + (c.note ? "<dt>Note</dt><dd>" + esc(c.note) + "</dd>" : "") + "</dl>" +
          tableau([["n", "Billet"], ["p", "Pour"], ["e", "État"], ["", ""]], mes.map((b) => "<tr><td><b>" + esc(b.numero) + "</b></td><td>" + esc(b.nom || "—") + "</td><td>" + puce(b.etat === "valide" ? (b.entrees_faites ? "entré" : "valide") : "annulé", b.etat === "valide" ? "ok" : "dg") + '</td><td class="n" style="white-space:nowrap">' + (b.etat === "valide" ? '<button class="btn sm" data-a="qr" data-n="' + esc(b.numero) + '">QR</button> <button class="btn sm" data-a="reemettre" data-n="' + esc(b.numero) + '">Réémettre</button> <button class="btn sm" data-a="transferer" data-n="' + esc(b.numero) + '">Transférer</button>' : "") + "</td></tr>"), "Pas encore de billet.") +
          '<div class="row">' + (c.etat === "retenue" || c.etat === "en_attente" ? '<button class="btn pri" data-a="encaisser">Marquer payée…</button><button class="btn dng" data-a="annuler-cmd">Annuler la réservation</button>' : "") + (c.etat === "payee" ? '<button class="btn" data-a="pdf">Billets en PDF</button><button class="btn dng" data-a="rembourser">Rembourser…</button>' : "") + (c.etat === "payee" && c.don > 0 ? '<button class="btn" data-a="recu">Reçu fiscal du don…</button>' : "") + "</div></div>";
        S.commande = c;
      }
    }
    R.innerHTML = S.entetes("Ventes", "Toutes les commandes : boutique, caisse, revendeurs, ventes à la main.", '<button class="btn pri" data-a="nouvelle-vente">+ Nouvelle vente</button>') +
      '<div class="carte"><div class="row"><input type="search" id="bv-q" placeholder="Référence, nom, courriel…" value="' + esc(S.f.q) + '" style="max-width:260px"><select id="bv-evt" style="max-width:240px" aria-label="Événement"><option value="">Tous les événements</option>' + evts.map((e) => '<option value="' + e.id + '"' + (String(e.id) === String(S.f.evenement) ? " selected" : "") + ">" + esc(e.nom) + "</option>").join("") + '</select><select id="bv-etat" style="max-width:200px" aria-label="État"><option value="">Tous les états</option>' + Object.keys({ retenue: 1, en_attente: 1, payee: 1, remboursee: 1, annulee: 1, expiree: 1 }).map((x) => '<option value="' + x + '"' + (x === S.f.etat ? " selected" : "") + ">" + esc((ETAT_LIB[x] || x)) + "</option>").join("") + "</select></div></div>" + detail +
      tableau([["r", "Commande"], ["n", "Acheteur"], ["e", "Événement"], ["s", "État"], ["m", "Moyen"], ["t", "Total", "n"]], l.map((x) => '<tr class="cl" data-a="cmd" data-ref="' + esc(x.ref) + '"><td><b>' + esc(x.ref) + "</b><div class=\"hint\">" + esc(quand(x.cree_le)) + "</div></td><td>" + esc(x.nom || "—") + "</td><td>" + esc(noms[x.evenement_id] || "") + "</td><td>" + puceCmd(x.etat) + "</td><td>" + esc(MOYENS[x.moyen] || x.moyen || "—") + '</td><td class="n">' + eur(x.total) + "</td></tr>"), "Aucune commande.");
    const refaire = () => S.rendre();
    S.saisie = (ev) => { if (ev.target.id === "bv-q") { S.f.q = ev.target.value; clearTimeout(S.t); S.t = setTimeout(async () => { const p = ev.target.selectionStart; await refaire(); const n = R.querySelector("#bv-q"); if (n) { n.focus(); n.setSelectionRange(p, p); } }, 350); } };
    S.change = (ev) => { if (ev.target.id === "bv-evt") { S.f.evenement = ev.target.value; refaire(); } if (ev.target.id === "bv-etat") { S.f.etat = ev.target.value; refaire(); } };
    S.clic = async (k, a) => {
      const c = S.commande;
      if (k === "cmd") { B.choix.commande = a.dataset.ref; return refaire(); }
      if (k === "fermer") { delete B.choix.commande; return refaire(); }
      if (k === "nouvelle-vente") { if (await nouvelleVente(S, evts)) refaire(); }
      else if (k === "encaisser") {
        const v = await B.formulaire("Marquer « " + c.ref + " » payée", [{ n: "moyen", l: "Reçu par", t: "select", opts: [["virement", "Virement"], ["especes", "Espèces"], ["carte_terminal", "Terminal carte"], ["carte_declaree", "Carte (déclarée)"], ["stripe", "Carte en ligne"], ["offert", "Offert"]] }, { n: "reference_externe", l: "Référence (n° de virement, de transaction)" }], { moyen: c.moyen || "virement" }, "Marquer payée");
        if (v && await S.geste("commande_encaisser", { ref: c.ref, moyen: v.moyen, reference_externe: v.reference_externe }, "Commande payée : les billets sont émis.")) refaire();
      } else if (k === "annuler-cmd") { if (await confirmer("Annuler la réservation ?", "<p>Les places retenues sont rendues.</p>", "Annuler la réservation", true) && await S.geste("commande_annuler", { ref: c.ref }, "Réservation annulée.")) refaire(); }
      else if (k === "rembourser") {
        const v = await B.formulaire("Rembourser « " + c.ref + " »", [{ n: "n", t: "note", l: "<p>Les billets sont annulés, les places rendues, la commission du revendeur reprise.</p>" + (["stripe", "helloasso", "paypal"].indexOf(c.moyen) >= 0 ? "<p><b>Le remboursement chez le prestataire reste à faire</b> depuis son tableau de bord.</p>" : "<p>Le remboursement de " + eur(c.total) + " est à faire à la main.</p>") }, { n: "motif", l: "Motif", t: "textarea" }], {}, "Rembourser", true);
        if (v && await S.geste("commande_rembourser", { ref: c.ref, motif: v.motif }, "Commande remboursée.")) refaire();
      } else if (k === "pdf") {
        const r = await S.lire("commande_pdf", { ref: c.ref });
        if (r) { const bin = atob(r.pdf), oct = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) oct[i] = bin.charCodeAt(i); const l = document.createElement("a"); l.href = URL.createObjectURL(new Blob([oct], { type: "application/pdf" })); l.download = r.nom; document.body.appendChild(l); l.click(); l.remove(); }
      } else if (k === "qr") {
        const x = await S.lire("billet", { numero: a.dataset.n }), bl = (S.billets || []).find((y) => y.numero === a.dataset.n) || {};
        if (x) await confirmer("Billet " + a.dataset.n, B.billetQr({ numero: a.dataset.n, qr: x.qr, code_controle: x.code_controle, nom: bl.nom }) + '<p class="hint">Ce QR code est celui que l’ouvreur scanne ; le code de contrôle se saisit à la main si le scan échoue.</p>', "Fermer");
      } else if (k === "reemettre") { if (await confirmer("Réémettre le billet ?", "<p>L’ancien QR code ne passera plus ; un nouveau est émis.</p>", "Réémettre") && await S.geste("billet_reemettre", { numero: a.dataset.n }, "Billet réémis.")) refaire(); }
      else if (k === "transferer") {
        const v = await B.formulaire("Transférer le billet " + a.dataset.n, [{ n: "nom", l: "Nouveau titulaire" }, { n: "mail", l: "Son courriel" }], {}, "Transférer");
        if (v && await S.geste("billet_transferer", { numero: a.dataset.n, nom: v.nom, mail: v.mail }, "Billet transféré.")) refaire();
      } else if (k === "recu") {
        const v = await B.formulaire("Reçu fiscal du don", [{ n: "adresse", l: "Adresse postale du donateur" }, { n: "nom", l: "Nom du donateur", def: c.nom }], {}, "Émettre le reçu");
        const r = v && await S.geste("recu_fiscal_emettre", { commande: c.ref, adresse: v.adresse, nom: v.nom || c.nom }, "Reçu émis.");
        if (r) dire("Reçu " + r.numero + (r.deja ? " (déjà émis)." : "."), "ok");
      }
    };
  };
  const ETAT_LIB = { retenue: "Réservée", en_attente: "Virement attendu", payee: "Payée", remboursee: "Remboursée", annulee: "Annulée", expiree: "Expirée" };

  async function nouvelleVente(S, evts) {
    const ouverts = evts.filter((e) => e.statut === "en vente" || e.statut === "complet");
    if (!ouverts.length) { dire("Aucun événement n’est en vente.", "err"); return false; }
    const c1 = await B.formulaire("Nouvelle vente", [{ n: "evenement_id", l: "Événement", t: "select", opts: ouverts.map((e) => [e.id, e.nom + " · " + jourCourt(e.date_iso)]) }], {}, "Suivant");
    if (!c1) return false;
    const f = await S.lire("evenement_fiche", { id: Number(c1.evenement_id) });
    if (!f) return false;
    const champs = f.types.map((t) => ({ n: "t" + t.id, l: t.nom + " · " + eur(t.prix), t: "number", def: 0 })).concat([{ n: "nom", l: "Nom de l’acheteur" }, { n: "mail", l: "Courriel (pour envoyer les billets)" }, { n: "code_promo", l: "Code promo" }, { n: "don", l: "Don (€)", t: "eur" },
      { n: "moyen", l: "Paiement", t: "select", opts: [["", "Pas encore payé (réserve les places)"], ["especes", "Espèces"], ["carte_terminal", "Terminal carte"], ["carte_declaree", "Carte (déclarée)"], ["offert", "Offert"]] }]);
    const v = await B.formulaire("Vente · " + f.evenement.nom, champs, {}, "Valider la vente");
    if (!v) return false;
    const lignes = f.types.map((t) => ({ type_billet_id: t.id, quantite: Number(v["t" + t.id]) || 0 })).filter((x) => x.quantite > 0);
    const args = { evenement_id: f.evenement.id, lignes: lignes, nom: v.nom, mail: v.mail, don: v.don || 0, moyen: v.moyen, encaisser: !!v.moyen };
    if (v.code_promo) args.code_promo = v.code_promo;
    const r = await S.geste("commande_creer", args, "Vente enregistrée.");
    if (r && r.ref) B.choix.commande = r.ref;
    return !!r;
  }

  // ═══ PERSONNES ═══
  P.personnes = async (S) => {
    const R = S.racine, TABS = [["revendeur", "Revendeurs"], ["artiste", "Artistes"], ["formule", "Formules"], ["salle", "Salles"], ["promo", "Codes promo"], ["legal", "Textes légaux"]];
    S.onglet = TABS.some((t) => t[0] === S.onglet) ? S.onglet : "revendeur";
    R.innerHTML = S.entetes("Personnes et bases", "Revendeurs, artistes, formules de rémunération, salles et codes promo.") + '<div class="onglets">' + TABS.map((t) => '<button class="' + (t[0] === S.onglet ? "on" : "") + '" data-a="onglet" data-o="' + t[0] + '">' + t[1] + "</button>").join("") + '</div><div id="bz"></div>';
    if (S.onglet === "legal") await legalOnglet(S, R.querySelector("#bz"));
    else await crud(S, S.onglet, R.querySelector("#bz"));
    if (S.onglet === "revendeur" || S.onglet === "artiste") R.querySelector("#bz").insertAdjacentHTML("beforeend", '<div class="row" style="margin-top:10px"><button class="btn" data-a="repertoire">Mettre tout le monde dans le répertoire du bureau</button><span class="hint">Un contact par artiste et par revendeur ; ceux qui y sont déjà ne sont pas doublés.</span></div>');
    if (S.onglet === "revendeur") R.querySelector("#bz").insertAdjacentHTML("beforeend", '<p class="hint" style="margin-top:8px">Un artiste qui vend lui-même apparaît aussi ici : il naît de sa fiche d’artiste (case « vend lui-même »).</p>');
    S.clic = async (k, a) => {
      if (k === "onglet") { S.onglet = a.dataset.o; return S.rendre(); }
      if (k === "repertoire") {
        const r = await S.geste("repertoire_synchroniser", {});
        if (r && r.racontee) await confirmer("Répertoire non modifié", "<p>" + esc(r.message) + "</p>", "Compris");
        else if (r) await confirmer("Répertoire", "<p>" + r.crees.length + " contact(s) créé(s), " + r.deja + " déjà là.</p>" + (r.refuses.length ? '<p class="note">À regarder :</p><ul class="lst">' + r.refuses.map((x) => "<li>" + esc(x.fiche) + " — " + esc(x.raison) + "</li>").join("") + "</ul>" : ""), "Fermer");
        return undefined;
      }
      if (k === "profil-vu") {
        const r = await S.lire("profil_vu", { porteur: a.dataset.e, id: Number(a.dataset.id) });
        if (r) await confirmer("Profil · " + r.nom, '<p>' + (r.complet ? "Profil complet : on peut payer et facturer." : "<b>Il manque :</b> " + r.manque.map(esc).join(" ; ") + ".") + '</p><dl class="kv"><dt>Courriel</dt><dd>' + esc(r.mail || "—") + "</dd><dt>SIRET</dt><dd>" + esc(r.siret || "—") + "</dd><dt>IBAN</dt><dd>" + esc(r.iban_masque || "non renseigné") + "</dd>" + (r.mode_facturation ? "<dt>Commission</dt><dd>" + (r.mode_facturation === "mandat" ? "auto-facture établie par le titulaire" : "facturée par le revendeur") + "</dd>" : "") + "</dl>", "Fermer");
        return undefined;
      }
      if (k === "adherent") { const r = await S.geste("dolibarr_adherent", { artiste_id: Number(a.dataset.id) }); if (r) dire(r.deja ? "Déjà dans la file de Dolibarr." : "Écriture empilée : Dolibarr la fera en arrière-plan (onglet Argent › Comptabilité).", "ok"); return undefined; }
      if (k === "legal-modele") { const r = await S.lire("legal_modele", { cle: a.dataset.cle }); if (r) { const z = R.querySelector("#lg-" + a.dataset.cle); if (!z.value.trim() || confirm("Remplacer le texte par le squelette ?")) z.value = r.texte; } return undefined; }
      if (k === "legal-save") { if (await S.geste("legal_page_save", { cle: a.dataset.cle, texte: R.querySelector("#lg-" + a.dataset.cle).value }, "Texte enregistré.")) S.rendre(); return undefined; }
      if (await clicEntite(S, a)) S.rendre();
    };
  };

  // les textes légaux de la boutique : un cadre par texte, un squelette à compléter, la version qui monte
  async function legalOnglet(S, zone) {
    const r = await S.lire("legal_pages"), l = (r && r.pages) || [];
    zone.innerHTML = '<p class="sub">Les conditions de vente, les mentions légales et la politique de confidentialité s’affichent en pied de la boutique. Dès que les conditions de vente sont publiées, l’acheteur doit les accepter pour commander, et la commande garde la version acceptée. Le squelette n’est pas un avis juridique : à compléter et à faire relire.</p>' +
      l.map((p) => '<div class="carte" style="margin-bottom:12px"><div class="row"><h3 style="margin:0">' + esc(p.titre) + '</h3>' + (p.publiee ? puce("publié · version " + p.version, "ok") : puce("non publié", "")) + '<span class="sp"></span><button class="btn sm" data-a="legal-modele" data-cle="' + p.cle + '">Partir d’un squelette</button><button class="btn sm pri" data-a="legal-save" data-cle="' + p.cle + '">Enregistrer</button></div><textarea id="lg-' + p.cle + '" style="min-height:160px;margin-top:8px">' + esc(p.texte) + "</textarea></div>").join("");
  }

  // ═══ ARGENT ═══
  P.argent = async (S) => {
    const R = S.racine, TABS = [["retraits", "Retraits"], ["portefeuilles", "Portefeuilles"], ["recus", "Reçus fiscaux"], ["compta", "Comptabilité"], ["courriels", "Courriels"]];
    S.onglet = TABS.some((t) => t[0] === S.onglet) ? S.onglet : "retraits";
    let corps = "";
    if (S.onglet === "retraits") {
      const r = await S.lire("retraits"), l = (r && r.retraits) || [];
      const ETAT = { demandee: ["À traiter", "al"], validee: ["À payer", "ac"], payee: ["Payée", "ok"], refusee: ["Refusée", ""] };
      corps = tableau([["r", "Demande"], ["p", "Pour"], ["m", "Montant", "n"], ["e", "État"], ["", ""]], l.map((x) => "<tr><td><b>" + esc(x.ref) + '</b><div class="hint">' + esc(quand(x.demande_le)) + "</div></td><td>" + esc(x.porteur) + " " + x.porteur_id + '</td><td class="n">' + eur(x.montant) + "</td><td>" + puce((ETAT[x.etat] || [x.etat])[0], (ETAT[x.etat] || [])[1]) + (x.motif ? '<div class="hint">' + esc(x.motif) + "</div>" : "") + '</td><td class="n" style="white-space:nowrap">' +
        (x.etat === "demandee" ? '<button class="btn sm pri" data-a="valider" data-id="' + x.id + '">Valider</button> <button class="btn sm dng" data-a="refuser" data-id="' + x.id + '">Refuser</button>' : "") + (x.etat === "validee" ? '<button class="btn sm pri" data-a="payer" data-id="' + x.id + '">Marquer payée…</button> <button class="btn sm dng" data-a="refuser" data-id="' + x.id + '">Refuser</button>' : "") + "</td></tr>"), "Aucune demande de retrait.");
    } else if (S.onglet === "portefeuilles") {
      const [rv, ar] = await Promise.all([S.lire("revendeurs"), S.lire("artistes")]);
      const lignes = [];
      for (const [genre, liste] of [["revendeur", (rv && rv.revendeurs) || []], ["artiste", (ar && ar.artistes) || []]]) {
        for (const p of liste) { const w = await S.lire("portefeuille", { porteur: genre, porteur_id: p.id }); if (w) lignes.push('<tr><td><b>' + esc(p.nom || p.scene) + '</b> <span class="hint">' + genre + '</span></td><td class="n">' + eur(w.disponible) + '</td><td class="n">' + eur(w.en_attente) + '</td><td class="n">' + eur(w.retraits_en_cours) + '</td><td class="n">' + eur(w.verse) + '</td><td class="n"><button class="btn sm" data-a="provision" data-g="' + genre + '" data-id="' + p.id + '">Ajuster…</button></td></tr>'); }
      }
      corps = '<p class="sub">Ce que l’organisateur DOIT à chacun. Cassandra ne détient aucun fonds : le versement se fait par virement, puis s’enregistre ici.</p>' + tableau([["p", "Porteur"], ["d", "Retirable", "n"], ["a", "En attente de date", "n"], ["c", "Retrait demandé", "n"], ["v", "Déjà versé", "n"], ["", ""]], lignes, "Aucun revendeur ni artiste.");
    } else if (S.onglet === "recus") {
      const r = await S.lire("recus_fiscaux"), l = (r && r.recus) || [];
      corps = '<div class="row" style="margin-bottom:10px"><span class="sp hint">' + (l.length ? "Total des reçus en vigueur : " + eur(r.total_emis) : "Aucun reçu émis.") + '</span><button class="btn" data-a="export">Exporter l’année (CSV)</button></div>' +
        tableau([["n", "Reçu"], ["d", "Donateur"], ["m", "Montant", "n"], ["e", "État"], ["", ""]], l.map((x) => "<tr><td><b>" + esc(x.numero) + '</b><div class="hint">' + esc(x.date_don) + "</div></td><td>" + esc(x.nom) + '</td><td class="n">' + eur(x.montant) + "</td><td>" + puce(x.etat === "emis" ? "en vigueur" : "annulé", x.etat === "emis" ? "ok" : "dg") + (x.motif ? '<div class="hint">' + esc(x.motif) + "</div>" : "") + '</td><td class="n">' + (x.etat === "emis" ? '<button class="btn sm dng" data-a="annuler-recu" data-n="' + esc(x.numero) + '">Annuler</button>' : "") + "</td></tr>"), "Aucun reçu.");
    } else if (S.onglet === "compta") {
      const e = await S.lire("dolibarr_etat") || {}, f = await S.lire("dolibarr_file", { limite: 50 }), l = (f && f.file) || [];
      const ETAT = { a_faire: ["à faire", "al"], fait: ["fait", "ok"], echec: ["échec", "dg"], ignore: ["ignorée", ""] }, DOM = { tiers: "tiers clients", factures: "factures", paiements: "règlements", avoirs: "avoirs", commissions: "versements de commissions" };
      corps = '<p class="sub">Le pont facultatif vers Dolibarr (comptabilité) : une écriture par vente, remboursement ou versement, faite en arrière-plan, jamais pendant un paiement. Sans Dolibarr, la billetterie fonctionne seule.</p>' +
        '<div class="tuiles">' + tuile(e.relie ? "relié" : "non relié", "pont Dolibarr", e.relie ? "" : "al") + tuile(e.a_faire || 0, "écritures à faire", (e.a_faire ? "al" : "")) + tuile(e.faits || 0, "écritures faites", "") + tuile(e.echecs || 0, "en échec", (e.echecs ? "al" : "")) + "</div>" +
        '<div class="row" style="margin:10px 0"><button class="btn" data-a="reglages-pont">Réglages du pont…</button><button class="btn" data-a="tester-pont">Tester la connexion</button><button class="btn pri" data-a="rattraper"' + (e.relie ? "" : " disabled") + ">Faire les écritures maintenant</button><span class=\"sp\"></span>" +
        Object.keys(e.domaines || {}).map((k) => puce(DOM[k] || k, e.domaines[k] ? "ok" : "")).join(" ") + "</div>" +
        tableau([["c", "Écriture"], ["e", "État"], ["x", "Essais", "n"], ["r", "Dernière raison"], ["", ""]], l.map((x) => "<tr><td><b>" + esc(x.cle) + '</b><div class="hint">' + esc(quand(x.cree_le)) + "</div></td><td>" + puce((ETAT[x.etat] || [x.etat])[0], (ETAT[x.etat] || [])[1]) + '</td><td class="n">' + x.essais + "</td><td>" + esc(x.erreur || x.resultat || "") + '</td><td class="n">' + (x.etat === "echec" ? '<button class="btn sm" data-a="relancer-dol" data-id="' + x.id + '">Relancer</button>' : "") + "</td></tr>"), e.relie ? "Aucune écriture pour l’instant." : "Pont non relié : rien n’est écrit.");
    } else {
      const [r, es] = await Promise.all([S.lire("courriels", { limite: 100 }), S.lire("courriels_etat")]), l = (r && r.courriels) || [], e = es || {};
      corps = '<p class="sub">Les courriels préparés par la billetterie (billets, annulations, offres de la liste d’attente, liens de connexion). Un envoi qui échoue est retenté plus tard et ne perd jamais la commande.</p>' +
        '<div class="alerte' + (e.actif && e.serveur_regle ? "" : " dg") + '"><span class="sp">' + (e.actif ? (e.serveur_regle ? "Envoi activé : " + (e.a_envoyer || 0) + " à envoyer, " + (e.envoyes || 0) + " envoyés, " + (e.echecs || 0) + " en échec." : "Envoi activé mais le serveur n’est pas réglé : rien ne part.") : "Envoi désactivé : rien ne part. Renseignez le serveur d’envoi (SMTP) dans les réglages du module, puis activez-le.") + (e.frein_envois ? " Le frein « envois » est posé." : "") + '</span><button class="btn sm" data-a="reglages-pont">Réglages…</button><button class="btn sm pri" data-a="envoyer-courriels"' + (e.actif && e.serveur_regle ? "" : " disabled") + ">Envoyer maintenant</button></div>" +
        tableau([["d", "Quand"], ["a", "À"], ["o", "Objet"], ["e", "État"], ["", ""]], l.map((x) => "<tr><td>" + esc(quand(x.cree_le)) + "</td><td>" + esc(x.a) + "</td><td>" + esc(x.objet) + (x.joindre ? ' <span class="hint">· billets en PDF joints</span>' : "") + "</td><td>" + puce({ a_envoyer: "à envoyer", envoye: "envoyé", echec: "échec" }[x.etat] || x.etat, x.etat === "echec" ? "dg" : x.etat === "envoye" ? "ok" : "al") + (x.erreur ? '<div class="hint">' + esc(x.erreur) + "</div>" : "") + '</td><td class="n">' + (x.etat === "echec" ? '<button class="btn sm" data-a="relancer-courriel" data-id="' + x.id + '">Relancer</button>' : "") + "</td></tr>"), "Aucun courriel.");
    }
    R.innerHTML = S.entetes("Argent", "Retraits, portefeuilles, reçus de dons, courriels.") + '<div class="onglets">' + TABS.map((t) => '<button class="' + (t[0] === S.onglet ? "on" : "") + '" data-a="onglet" data-o="' + t[0] + '">' + t[1] + "</button>").join("") + "</div>" + (S.erreur ? '<div class="carte" style="color:var(--danger)">' + esc(S.erreur) + "</div>" : "") + corps;
    S.clic = async (k, a) => {
      const id = Number(a.dataset.id);
      if (k === "onglet") { S.onglet = a.dataset.o; return S.rendre(); }
      if (k === "valider") { if (await S.geste("retrait_valider", { id: id }, "Demande validée.")) S.rendre(); }
      else if (k === "payer") { const v = await B.formulaire("Retrait versé", [{ n: "reference_virement", l: "Référence du virement" }], {}, "Marquer payée"); if (v && await S.geste("retrait_payer", { id: id, reference_virement: v.reference_virement }, "Retrait enregistré comme versé.")) S.rendre(); }
      else if (k === "refuser") { const v = await B.formulaire("Refuser la demande", [{ n: "motif", l: "Motif" }], {}, "Refuser", true); if (v && await S.geste("retrait_refuser", { id: id, motif: v.motif }, "Demande refusée : la réserve revient au portefeuille.")) S.rendre(); }
      else if (k === "provision") {
        const v = await B.formulaire("Ajuster le portefeuille", [{ n: "nature", l: "Nature", t: "select", opts: [["ajustement", "Ajustement (peut être négatif)"], ["commission", "Commission"], ["forfait", "Forfait"], ["fixe", "Fixe"]] }, { n: "montant", l: "Montant (€, négatif pour reprendre)", t: "text" }, { n: "note", l: "Note" }], {}, "Enregistrer");
        if (v) { const m = Math.round(parseFloat(String(v.montant).replace(",", ".")) * 100); if (!m) { dire("Montant invalide.", "err"); return; } if (await S.geste("provision", { porteur: a.dataset.g, porteur_id: id, nature: v.nature, montant: m, note: v.note }, "Écriture ajoutée au registre.")) S.rendre(); }
      } else if (k === "annuler-recu") { const v = await B.formulaire("Annuler le reçu " + a.dataset.n, [{ n: "motif", l: "Motif" }], {}, "Annuler le reçu", true); if (v && await S.geste("recu_fiscal_annuler", { numero: a.dataset.n, motif: v.motif }, "Reçu annulé : son numéro est conservé.")) S.rendre(); }
      else if (k === "reglages-pont") { if (CASS.ouvrirConsole) CASS.ouvrirConsole("billetterie", "Billetterie", "reglages"); }
      else if (k === "tester-pont") {
        const r = await S.lire("dolibarr_tester");
        if (r) await confirmer("Test de Dolibarr · " + (r.ok ? "tout est prêt" : "il manque quelque chose"), '<p class="note">Version ' + esc(r.version || "?") + " — " + esc((r.societe || {}).name || "société non renseignée") + '</p><ul class="lst">' + r.points.map((p) => "<li>" + (p.ok ? "✓ " : "✗ <b>") + esc(p.libelle) + (p.ok ? "" : "</b>") + (p.detail ? " — " + esc(p.detail) : "") + "</li>").join("") + "</ul>", "Fermer");
        else dire(S.erreur || "Dolibarr n’a pas répondu.", "err");
      } else if (k === "rattraper") { const r = await S.geste("dolibarr_rattraper", {}); if (r) { dire(r.faits + " faite(s), " + r.reportes + " reportée(s), " + r.echecs + " en échec" + (r.raison ? " — " + r.raison : "") + ".", r.echecs || r.reportes ? "err" : "ok"); S.rendre(); } }
      else if (k === "relancer-dol") { if (await S.geste("dolibarr_relancer", { id: id }, "Écriture remise dans la file.")) S.rendre(); }
      else if (k === "envoyer-courriels") { const r = await S.geste("courriels_envoyer", {}); if (r) { dire(r.envoyes + " envoyé(s), " + r.reportes + " reporté(s), " + r.echecs + " en échec" + (r.raison ? " — " + r.raison : "") + ".", r.echecs || r.reportes ? "err" : "ok"); S.rendre(); } }
      else if (k === "relancer-courriel") { if (await S.geste("courriel_relancer", { id: id }, "Courriel remis dans la boîte d’envoi.")) S.rendre(); }
      else if (k === "export") {
        const r = await S.lire("recus_export", { annee: String(new Date().getFullYear()) });
        if (r) { const lien = document.createElement("a"); lien.href = URL.createObjectURL(new Blob(["﻿" + r.csv], { type: "text/csv;charset=utf-8" })); lien.download = "recus-fiscaux-" + new Date().getFullYear() + ".csv"; document.body.appendChild(lien); lien.click(); lien.remove(); }
      }
    };
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
