// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : ▼▼▼ BORNE CN version=0
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #5ce992
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=5ce992 ▼▼▼
// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Utilisateurs et groupes » : les comptes (profil, administrateur, groupes), les groupes (membres), la matrice des droits façon Dolibarr (hérité / accordé / refusé, par utilisateur ou par groupe, avec le droit effectif), la corbeille.
// Les données viennent des capacités comptes.* (lister, creer, modifier, supprimer, creer_jeton, corbeille, restaurer, regles_mdp) et droits.* (etat, catalogue, mes_droits, regler, groupe, membre, admin).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, pill = K.pill, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const SCENES = [["utilisateurs", "Utilisateurs"], ["groupes", "Groupes"], ["droits", "Droits"], ["corbeille", "Corbeille"]];
  const VALEURS = [["herite", "Hérite"], ["accorde", "Accordé"], ["refuse", "Refusé"]];
  const initiales = (c) => String(c.display_name || c.compte || "?").trim().split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((x) => x[0].toUpperCase()).join("") || "?";
  const nomDe = (c) => c.display_name || c.compte;
  const court = (t) => (typeof t === "number" ? new Date(t * 1000).toISOString().slice(0, 10) : String(t || "").slice(0, 10));

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.comptes = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("comptes", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "utilisateurs", comptes: [], etat: { admins: [], groupes: [], accords: [] }, catalogue: [], corbeille: null, q: "", fiche: "", nouveau: false, regles: "", sujet: "", effectifs: null, qd: "", jeton: null, moi: "", charge: true, erreur: "" };
    const val = (id) => ((racine.querySelector(id) || {}).value || "").trim();

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { await agir(cap, args); if (ok) dire(ok, "ok"); return true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] && !S.fiche ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0] && !S.fiche) + '">' + esc(s[1]) + "</button>").join("") + "</div>";
    const estAdmin = (c) => S.etat.admins.indexOf(c) >= 0;
    const groupesDe = (c) => S.etat.groupes.filter((g) => g.membres.indexOf(c) >= 0);
    const compteDe = (c) => S.comptes.find((x) => x.compte === c) || { compte: c };
    const fiche = (titre, note, cote) => '<div class="li"><div class="sp"><b>' + titre + "</b>" + (note ? '<span class="note">' + esc(note) + "</span>" : "") + "</div>" + (cote || "") + "</div>";
    const rond = (c) => '<span class="ico sm" aria-hidden="true" style="font:650 12px Inter,sans-serif">' + esc(initiales(c)) + "</span>";

    // ── Utilisateurs ─────────────────────────────────────────────────────
    function utilisateurs() {
      const q = S.q.toLowerCase();
      const l = S.comptes.filter((c) => !q || [c.compte, c.display_name, c.role_label].some((x) => String(x || "").toLowerCase().indexOf(q) >= 0));
      const form = S.nouveau ? '<div class="carte"><h3>Nouvel utilisateur</h3><div class="barre"><input id="cp-mail" type="email" placeholder="prenom@exemple.com" aria-label="Adresse e-mail"><input id="cp-mdp" type="password" placeholder="Mot de passe" aria-label="Mot de passe" autocomplete="new-password"></div>' +
        (S.regles ? '<p class="note">' + esc(S.regles) + "</p>" : "") + '<div class="barre"><button class="btn pri" data-a="creer">Créer</button><button class="btn" data-a="annuler-nouveau">Annuler</button></div></div>' : "";
      return '<div class="barre"><input type="search" id="cp-q" placeholder="Chercher un utilisateur (Entrée)…" value="' + esc(S.q) + '" aria-label="Chercher"><button class="btn pri" data-a="nouveau">+ Nouvel utilisateur</button></div>' + form +
        ligneCompte(l.filter((c) => !c.type || c.type === "humain"), "Utilisateurs", "Aucun utilisateur.") +
        (l.some((c) => c.type && c.type !== "humain") ? ligneCompte(l.filter((c) => c.type && c.type !== "humain"), "Comptes de service (agents, système)", "") : "");
    }
    function ligneCompte(l, titre, vide) {
      return '<div class="carte"><h3>' + esc(titre) + " · " + l.length + '</h3><div class="liste">' + (l.length ? l.map((c) => { const gs = groupesDe(c.compte);
        return '<div class="li">' + rond(c) + '<div class="sp"><b><a href="#" data-a="fiche" data-k="' + esc(c.compte) + '">' + esc(String(nomDe(c)).slice(0, 60)) + "</a> " + (estAdmin(c.compte) ? pill("administrateur", "ac", "") : "") + (c.type && c.type !== "humain" ? " " + pill(c.type, "", "") : "") + "</b>" +
          '<span class="note">' + esc([c.compte !== nomDe(c) ? c.compte : "", c.role_label, gs.map((g) => g.libelle || g.groupe).join(", ")].filter(Boolean).join(" · ").slice(0, 140)) + "</span></div></div>"; }).join("") : '<div class="vide">' + esc(vide) + "</div>") + "</div></div>";
    }
    function detailUtilisateur() {
      const c = compteDe(S.fiche), moi = S.moi === c.compte;
      const champ = (cle, lib, type) => '<label class="note" style="display:flex;flex-direction:column;gap:3px;min-width:200px;flex:1">' + esc(lib) + '<input id="cp-f-' + cle + '" type="' + (type || "text") + '" value="' + esc(c[cle] || "") + '" aria-label="' + esc(lib) + '"></label>';
      const chips = S.etat.groupes.length ? '<div class="chips">' + S.etat.groupes.map((g) => '<button class="p ' + (g.membres.indexOf(c.compte) >= 0 ? "ac" : "") + '" data-a="membre" data-g="' + esc(g.groupe) + '" data-p="' + (g.membres.indexOf(c.compte) >= 0 ? 0 : 1) + '" aria-pressed="' + (g.membres.indexOf(c.compte) >= 0) + '">' + esc(g.libelle || g.groupe) + "</button>").join("") + "</div>" : '<p class="note">Aucun groupe : crée-en dans l’onglet Groupes.</p>';
      return '<div class="carte"><div class="barre"><h3 style="flex:1">' + esc(nomDe(c)) + " " + (estAdmin(c.compte) ? pill("administrateur", "ac", "") : "") + '</h3><button class="btn" data-a="retour">← Les utilisateurs</button></div><p class="note">' + esc([c.compte, c.cree ? "créé le " + court(c.cree) : ""].filter(Boolean).join(" · ")) + "</p></div>" +
        '<div class="carte"><h3>Profil</h3><div class="barre">' + champ("display_name", "Nom affiché") + champ("role_label", "Fonction") + "</div><div class=\"barre\">" + champ("contact_email", "Courriel de contact", "email") + champ("phone", "Téléphone", "tel") + champ("lang", "Langue") + '</div><div class="barre"><button class="btn pri" data-a="profil">Enregistrer</button></div></div>' +
        '<div class="carte"><h3>Administrateur</h3><p class="note">Un administrateur a tous les droits, sans exception ; les droits du tableau ne s’appliquent pas à lui.</p><div class="barre"><button class="btn ' + (estAdmin(c.compte) ? "dng" : "pri") + '" data-a="admin" data-v="' + (estAdmin(c.compte) ? 0 : 1) + '">' + (estAdmin(c.compte) ? "Retirer le rôle d’administrateur" : "Nommer administrateur") + "</button></div></div>" +
        '<div class="carte"><h3>Groupes</h3>' + chips + "</div>" +
        '<div class="carte"><h3>Droits</h3><p class="note">Ce que cet utilisateur peut faire, droit par droit, hérité de ses groupes ou posé pour lui seul.</p><div class="barre"><button class="btn" data-a="voir-droits" data-t="compte" data-k="' + esc(c.compte) + '">Voir et régler ses droits</button></div></div>' +
        '<div class="carte"><h3>Accès</h3><div class="barre"><button class="btn" data-a="jeton" data-k="' + esc(c.compte) + '">Créer un lien de mise en place du mot de passe</button></div>' +
        (S.jeton && S.jeton.compte === c.compte ? '<p class="note">À donner à la personne (valable 72 h, un seul usage) :</p><pre class="mono" style="white-space:pre-wrap;word-break:break-all;margin:0">' + esc(S.jeton.jeton) + "</pre>" : "") + "</div>" +
        '<div class="carte"><h3>Supprimer</h3><p class="note">Le compte part à la corbeille ; il se restaure depuis l’onglet Corbeille.</p><div class="barre"><button class="btn dng" data-a="supprimer" data-k="' + esc(c.compte) + '"' + (moi ? " disabled" : "") + ">Supprimer ce compte</button>" + (moi ? '<span class="note">Tu ne peux pas supprimer ton propre compte.</span>' : "") + "</div></div>";
    }

    // ── Groupes ──────────────────────────────────────────────────────────
    function groupes() {
      const l = S.etat.groupes;
      return '<div class="carte"><h3>Nouveau groupe</h3><div class="barre"><input id="cp-gid" placeholder="identifiant (ex : compta)" aria-label="Identifiant"><input id="cp-glib" placeholder="nom affiché (ex : Comptabilité)" aria-label="Nom affiché"><button class="btn pri" data-a="groupe-creer">Créer</button></div></div>' +
        '<div class="carte"><div class="liste">' + (l.length ? l.map((g) => fiche(esc(g.libelle || g.groupe) + " " + pill(g.membres.length + " membre" + (g.membres.length > 1 ? "s" : ""), "", ""),
          [g.groupe, g.membres.map((m) => nomDe(compteDe(m))).join(", ")].filter(Boolean).join(" · "),
          '<div class="chips"><button class="p" data-a="voir-droits" data-t="groupe" data-k="' + esc(g.groupe) + '">Droits</button><button class="p" data-a="groupe-renommer" data-k="' + esc(g.groupe) + '">Renommer</button><button class="p dg" data-a="groupe-supprimer" data-k="' + esc(g.groupe) + '">Supprimer</button></div>')).join("") : '<div class="vide">Aucun groupe. Un groupe rassemble des utilisateurs pour leur donner les mêmes droits d’un coup.</div>') + "</div></div>";
    }

    // ── Droits : la matrice ──────────────────────────────────────────────
    function accordDe(type, sujet, droit) { const a = S.etat.accords.find((x) => x.sujet_type === type && x.sujet === sujet && x.droit === droit); return a ? (a.accord ? "accorde" : "refuse") : "herite"; }
    function droits() {
      const [type, sujet] = S.sujet ? S.sujet.split("|") : ["", ""];
      const options = '<option value="">Choisis un utilisateur ou un groupe…</option><optgroup label="Utilisateurs">' + S.comptes.map((c) => '<option value="compte|' + esc(c.compte) + '"' + (S.sujet === "compte|" + c.compte ? " selected" : "") + ">" + esc(nomDe(c)) + "</option>").join("") + '</optgroup><optgroup label="Groupes">' + S.etat.groupes.map((g) => '<option value="groupe|' + esc(g.groupe) + '"' + (S.sujet === "groupe|" + g.groupe ? " selected" : "") + ">" + esc(g.libelle || g.groupe) + "</option>").join("") + "</optgroup>";
      const tete = '<div class="barre"><select class="sel" data-a="sujet" aria-label="Sujet">' + options + '</select><input type="search" id="cp-qd" placeholder="Filtrer les droits…" value="' + esc(S.qd) + '" aria-label="Filtrer"></div>';
      if (!type) return tete + '<div class="carte vide">Choisis un utilisateur ou un groupe pour voir et régler ses droits.</div>';
      const admin = type === "compte" && estAdmin(sujet);
      const q = S.qd.toLowerCase();
      const cat = S.catalogue.filter((d) => !q || [d.droit, d.libelle, d.module].some((x) => String(x || "").toLowerCase().indexOf(q) >= 0));
      const parMod = {}; cat.forEach((d) => { (parMod[d.module] = parMod[d.module] || []).push(d); });
      const eff = S.effectifs;
      const tableaux = Object.keys(parMod).sort().map((m) => '<div class="carte"><h3>' + esc(m) + " · " + parMod[m].length + '</h3><div class="liste">' + parMod[m].map((d) => {
        const v = accordDe(type, sujet, d.droit);
        const effectif = admin ? true : eff ? eff.indexOf(d.droit) >= 0 : null;
        const seg = '<div class="seg" role="radiogroup" aria-label="' + esc(d.droit) + '">' + VALEURS.map((x) => '<button role="radio" aria-checked="' + (v === x[0]) + '" class="' + (v === x[0] ? "on" : "") + '" data-a="regler" data-d="' + esc(d.droit) + '" data-v="' + x[0] + '"' + (admin ? " disabled" : "") + ">" + x[1] + "</button>").join("") + "</div>";
        return '<div class="li"><div class="sp"><b>' + esc(d.libelle || d.droit) + (d.sensible ? " " + pill("sensible", "al", "warn") : "") + '</b><span class="note mono" style="font-size:11.5px">' + esc(d.droit) + " · par défaut : " + (d.defaut ? "accordé" : "refusé") + "</span></div>" +
          (type === "compte" ? pill(effectif === null ? "…" : effectif ? "peut" : "ne peut pas", effectif ? "ok" : effectif === false ? "dg" : "", "") : "") + seg + "</div>"; }).join("") + "</div></div>").join("");
      return tete + (admin ? '<div class="alerte in"><div class="sp"><b>' + esc(nomDe(compteDe(sujet))) + "</b> est administrateur : il a tous les droits, rien ne se règle ici pour lui.</div></div>" : "") +
        '<p class="note">Hérite : le droit suit les groupes puis la valeur par défaut. Accordé ou Refusé : posé ici, il l’emporte (un refus de groupe l’emporte sur un accord).</p>' + (tableaux || '<div class="carte vide">Aucun droit ne correspond.</div>');
    }
    function corbeille() {
      const l = S.corbeille || [];
      return '<div class="carte"><h3>Comptes supprimés</h3><div class="liste">' + (l.length ? l.map((x) => fiche(esc(x.compte), "supprimé le " + court(x.ts), '<button class="p" data-a="restaurer" data-id="' + x.id + '">Restaurer</button>')).join("") : '<div class="vide">La corbeille est vide.</div>') + "</div></div>";
    }

    function dessiner() {
      let c;
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (S.erreur && !S.comptes.length) c = '<div class="carte"><h3>La gestion des utilisateurs ne répond pas</h3><p class="note">' + esc(S.erreur) + "</p></div>";
      else if (S.fiche) c = detailUtilisateur();
      else c = ({ utilisateurs: utilisateurs, groupes: groupes, droits: droits, corbeille: corbeille }[S.scene] || utilisateurs)();
      racine.innerHTML = K.titre("Utilisateurs et groupes", "Qui a un compte, dans quels groupes, et ce que chacun a le droit de faire.") + barre() + c;
    }
    async function chargerBase() {
      const [l, e, c, m] = await Promise.all([lire("comptes.lister"), lire("droits.etat"), lire("droits.catalogue"), lire("comptes.moi")]);
      S.comptes = (l && l.comptes) || []; S.etat = e || { admins: [], groupes: [], accords: [] }; S.catalogue = (c && c.droits) || []; S.moi = (m && (m.compte || (m.profil && m.profil.compte))) || "";
    }
    async function effectifs() { const [t, s] = S.sujet ? S.sujet.split("|") : []; S.effectifs = null; if (t === "compte") { const r = await lire("droits.mes_droits", { compte: s }); S.effectifs = r ? r.droits || [] : null; } }
    async function recharger() { await chargerBase(); if (S.scene === "droits") await effectifs(); if (S.scene === "corbeille") S.corbeille = ((await lire("comptes.corbeille")) || {}).corbeille || []; dessiner(); }
    async function aller(scene) { S.scene = scene; S.fiche = ""; S.erreur = ""; if (scene === "corbeille") { const r = await lire("comptes.corbeille"); S.corbeille = (r && r.corbeille) || []; } if (scene === "droits") await effectifs(); dessiner(); }
    async function demanderNom(titre, defaut) { return new Promise((fin) => { const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999; const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.innerHTML = "<h2>" + esc(titre) + '</h2><input id="cp-nom" value="' + esc(defaut || "") + '" style="padding:9px 12px;border:1px solid var(--line-strong);border-radius:10px;background:var(--surface-solid);color:var(--txt);font:14px Inter,sans-serif"><div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn pri" data-c="oui">Valider</button></div>'; const clore = (r) => { const t = m.querySelector("#cp-nom").value.trim(); v.remove(); m.remove(); fin(r ? t : null); }; v.addEventListener("click", () => clore(false)); m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) clore(b.dataset.c === "oui"); }); document.body.appendChild(v); document.body.appendChild(m); m.querySelector("#cp-nom").focus(); }); }

    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a, cle = a.dataset.k; if (a.tagName === "A") e.preventDefault();
      if (k === "fiche") { S.fiche = cle; S.jeton = null; dessiner(); }
      else if (k === "retour") { S.fiche = ""; dessiner(); }
      else if (k === "nouveau") { S.nouveau = true; if (!S.regles) { const r = await lire("comptes.regles_mdp"); S.regles = r ? r.legende || "" : ""; } dessiner(); }
      else if (k === "annuler-nouveau") { S.nouveau = false; dessiner(); }
      else if (k === "creer") { const m = val("#cp-mail"), p = val("#cp-mdp"); if (!m || !p) { dire("Il faut une adresse et un mot de passe.", "err"); return; } if (await geste("comptes.creer", { compte: m, mot_de_passe: p }, "Utilisateur créé.")) { S.nouveau = false; recharger(); } }
      else if (k === "profil") { const d = { compte: S.fiche }; ["display_name", "role_label", "contact_email", "phone", "lang"].forEach((c) => { d[c] = val("#cp-f-" + c); }); if (await geste("comptes.modifier", d, "Profil enregistré.")) recharger(); }
      else if (k === "admin") { const nommer = a.dataset.v === "1"; if (!await confirmer((nommer ? "Nommer " : "Retirer le rôle d’administrateur à ") + nomDe(compteDe(S.fiche)) + " ?", '<p class="note">' + (nommer ? "Il aura tous les droits, sans exception." : "Il retombe sous les droits des tableaux.") + "</p>", nommer ? "Nommer" : "Retirer", !nommer)) return; if (await geste("droits.admin", { compte: S.fiche, admin: nommer }, "Fait.")) recharger(); }
      else if (k === "membre") { if (await geste("droits.membre", { compte: S.fiche, groupe: a.dataset.g, present: a.dataset.p === "1" })) recharger(); }
      else if (k === "voir-droits") { S.sujet = a.dataset.t + "|" + cle; S.fiche = ""; await aller("droits"); }
      else if (k === "jeton") { const r = await lire("comptes.creer_jeton", { compte: cle, heures: 72 }); if (r) { S.jeton = r; dessiner(); } else dire(S.erreur, "err"); }
      else if (k === "supprimer") { if (!await confirmer("Supprimer " + nomDe(compteDe(cle)) + " ?", '<p class="note">Le compte part à la corbeille ; tu pourras le restaurer.</p>', "Supprimer", true)) return; if (await geste("comptes.supprimer", { compte: cle }, "Compte supprimé.")) { S.fiche = ""; recharger(); } }
      else if (k === "restaurer") { if (await geste("comptes.restaurer", { corbeille: +a.dataset.id }, "Compte restauré.")) recharger(); }
      else if (k === "groupe-creer") { const id = val("#cp-gid"), lib = val("#cp-glib"); if (!id || !lib) { dire("Il faut un identifiant et un nom.", "err"); return; } if (await geste("droits.groupe", { groupe: id, libelle: lib }, "Groupe créé.")) recharger(); }
      else if (k === "groupe-renommer") { const g = S.etat.groupes.find((x) => x.groupe === cle); const n = await demanderNom("Renommer le groupe", g ? g.libelle : ""); if (n && await geste("droits.groupe", { groupe: cle, libelle: n }, "Groupe renommé.")) recharger(); }
      else if (k === "groupe-supprimer") { if (!await confirmer("Supprimer le groupe « " + cle + " » ?", '<p class="note">Ses membres n’en font plus partie et ses accords disparaissent.</p>', "Supprimer", true)) return; if (await geste("droits.groupe", { groupe: cle, supprimer: true }, "Groupe supprimé.")) recharger(); }
      else if (k === "regler") { const [t, s] = S.sujet.split("|"); if (await geste("droits.regler", { sujet_type: t, sujet: s, droit: a.dataset.d, valeur: a.dataset.v })) { await chargerBase(); await effectifs(); dessiner(); } }
    });
    racine.addEventListener("change", async (e) => { if (e.target.dataset && e.target.dataset.a === "sujet") { S.sujet = e.target.value; await effectifs(); dessiner(); } });
    racine.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (e.target.id === "cp-q") { e.preventDefault(); S.q = e.target.value.trim(); dessiner(); const i = racine.querySelector("#cp-q"); if (i) { i.focus(); i.setSelectionRange(S.q.length, S.q.length); } }
      else if (e.target.id === "cp-qd") { e.preventDefault(); S.qd = e.target.value.trim(); dessiner(); const i = racine.querySelector("#cp-qd"); if (i) { i.focus(); i.setSelectionRange(S.qd.length, S.qd.length); } }
    });
    await chargerBase(); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
