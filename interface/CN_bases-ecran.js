// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : bases-ecran.js
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #9a11be
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : bases-ecran.js
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=9a11be ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir;
  // La feuille de style : celle de la maquette validée (docs/CN_maquette-panel-detect.html, page « Bases de données »), réduite à ce que la page emploie, portée par .bd.
  const CSS = ".sh-scene:has(>.sh-corps>.bd){width:100%}.bd{color:var(--txt);font:15px/1.5 Inter,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:6px 4px 48px;max-width:1140px;margin:0 auto}.bd *{box-sizing:border-box}" +
    ".bd .mono{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace}.bd button{font:inherit;color:inherit;cursor:pointer}.bd .carte{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);backdrop-filter:blur(18px)}" +
    ".bd .fil{font-size:13px;color:var(--txt-faint);margin:2px 0 6px}.bd h1{font-size:26px;margin:0 0 4px;color:var(--txt-strong,var(--txt));letter-spacing:-.2px}.bd .tete{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}.bd .tete .meta{font-size:13px;color:var(--txt-faint);margin-right:auto;flex:1 1 320px}" +
    ".bd .btn{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:4px 10px;font-size:13px;color:var(--txt-strong,var(--txt))}.bd .btn:hover{border-color:var(--accent)}" +
    ".bd .sec{padding:16px 18px;margin-bottom:16px}.bd .sec h2{font-size:16px;margin:0;color:var(--txt-strong,var(--txt))}.bd .sh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}.bd .sh .meta{font-size:12.5px;color:var(--txt-faint)}.bd .sh .dr{margin-left:auto;display:flex;gap:6px;align-items:center}" +
    ".bd .verdict{display:flex;gap:14px;align-items:stretch}.bd .vm{width:5px;border-radius:4px;background:var(--ok);flex:none}.bd .vm.w{background:var(--warn)}.bd .vm.d{background:var(--danger)}.bd .vm.n{background:var(--line-strong,var(--line))}.bd .verdict p{margin:0}.bd .vt{font-size:19px;font-weight:700;color:var(--txt-strong,var(--txt))}.bd .vs{color:var(--txt-soft);font-size:14px;margin-top:2px!important}" +
    ".bd .pl{display:inline-flex;align-items:center;gap:5px;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--line);color:var(--txt-soft);white-space:nowrap}.bd .pl::before{content:\"\";width:6px;height:6px;border-radius:50%;background:currentColor}.bd .pl.ok{background:color-mix(in srgb,var(--ok) 12%,transparent);color:var(--ok)}.bd .pl.w{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.bd .pl.i{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent))}" +
    ".bd .rows{display:grid;gap:6px}.bd .row{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1.5fr) auto;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px 13px}.bd .row .nm{min-width:0}.bd .row .nm b{display:block;color:var(--txt-strong,var(--txt));font-weight:650}.bd .row .nm small{color:var(--txt-faint);font-size:12.5px;display:block}.bd .row .mil{font-size:13px;color:var(--txt-soft);min-width:0;overflow-wrap:anywhere}.bd .row .cote{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}" +
    "@media (max-width:760px){.bd .row{grid-template-columns:1fr}.bd .row .cote{justify-content:flex-start}}.bd .pv{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px}.bd .pv .ok{color:var(--ok);font-weight:700}.bd .pv .ko{color:var(--txt-faint)}.bd .pv small{color:var(--txt-faint);font-size:12.5px;display:block;overflow-wrap:anywhere}" +
    ".bd .note{font-size:12.5px;color:var(--txt-faint);margin:10px 0 0}.bd .vide{color:var(--txt-faint);font-size:14px;padding:6px 0}.bd .err{color:var(--danger)}" +
    ".bd .btn.p{background:var(--accent,#2a6df4);border-color:transparent;color:#fff}.bd .btn.d{color:var(--danger);border-color:var(--danger)}.bd .btn[disabled]{opacity:.5;cursor:not-allowed}.bd input,.bd select{font:inherit;color:inherit;background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:9px;padding:6px 9px;min-width:0}" +
    ".bd .form{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}.bd .secret{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace;user-select:all;background:var(--line);border-radius:8px;padding:3px 8px}.bd .danger{color:var(--danger)}";

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.bases = async function (corps) {
    K.injecter();
    if (!document.getElementById("bd-css")) { const st = document.createElement("style"); st.id = "bd-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "bd"; corps.appendChild(racine);
    const S = { d: null, erreur: "", forme: false, retrait: null, resultat: null, occupe: false };
    const sec = (titre, meta, corpsHtml, droite) => '<section class="carte sec"><div class="sh"><h2>' + titre + '</h2><span class="meta">' + meta + '</span><span class="dr">' + (droite || "") + "</span></div>" + corpsHtml + "</section>";
    const ligne = (nm, sous, mil, cote) => '<div class="row"><div class="nm"><b>' + nm + "</b><small>" + sous + '</small></div><div class="mil">' + mil + '</div><div class="cote">' + cote + "</div></div>";
    const taille = (mo) => (mo === null || mo === undefined || mo === "") ? "taille inconnue" : (Number(mo) >= 1024 ? (Number(mo) / 1024).toFixed(1).replace(".", ",") + " Go" : Number(mo).toFixed(1).replace(".", ",") + " Mo");
    const msg = (e) => (e && e.message) || String(e);
    // Un geste s'appelle sur la capacité que Panel Detect donne pour la fonction : l'écran ne nomme aucun panneau.
    async function viaRoute(fonction, args) {
      const r = await agir("paneldetect.route", { fonction: fonction });
      if (!r || !r.capacite) throw new Error("aucun panneau d'hébergement ne sert cette fonction");
      return agir(r.capacite, args || {});
    }

    function liste(d) {
      const L = d.bases || [];
      if (d.etat === "absent") return '<p class="vide">Aucun panneau d’hébergement ne sert les bases de données sur cette machine.</p><p class="note">Le panneau s’installe avant Cassandra ; Panel Detect (Paramètres) dit lequel est reconnu et si un module le pilote.</p>';
      if (d.etat === "muet") return '<p class="vide err">Le panneau ne répond pas : ce n’est pas « aucune base ». Réessaie, ou regarde Panel Detect.</p>';
      if (!L.length) return '<p class="vide">Aucune base sur le panneau · lecture réussie.</p>';
      return '<div class="rows">' + L.map((b) => {
        const lien = b.site ? "liée à " + esc(b.site) : "sans site";
        const copie = b.copiee ? "copiée " + esc(String(b.derniere_copie).slice(0, 10)) : '<span class="danger">jamais copiée</span>';
        const bt = (d.adresse ? '<button class="btn" data-a="pma" data-n="' + esc(b.nom) + '">phpMyAdmin</button>' : "") +
          (d.gestes && d.gestes.supprimer && b.id !== null && b.id !== undefined ? '<button class="btn d" data-a="suppr" data-i="' + esc(String(b.id)) + '">Supprimer</button>' : "");
        return ligne('<span class="mono">' + esc(b.nom) + "</span>", esc((b.utilisateurs || []).join(", ") || "sans utilisateur") + " · " + lien, esc(taille(b.taille_mo)) + " · " + copie, bt);
      }).join("") + "</div>";
    }
    function retrait(d) {
      const b = (d.bases || []).find((x) => String(x.id) === String(S.retrait));
      if (!b) return "";
      return '<section class="carte sec"><div class="sh"><h2>Supprimer « ' + esc(b.nom) + ' »</h2></div><p>La base et toutes ses données disparaissent du serveur. <b>Aucun retour automatique</b> : ' +
        (b.copiee ? "la dernière copie du panneau date du " + esc(String(b.derniere_copie).slice(0, 10)) + " et la contient." : '<span class="danger">elle n’a jamais été copiée : rien ne la ramènera.</span>') +
        '</p><div class="form"><input id="bd-conf" style="min-width:290px" placeholder="tape « ' + esc(b.nom) + ' » pour confirmer" autocomplete="off" aria-label="Nom de la base à supprimer"><button class="btn d" data-a="suppr-go" data-i="' + esc(String(b.id)) + '" disabled>Supprimer pour de bon</button><button class="btn" data-a="suppr-non">Annuler</button></div></section>';
    }
    function formulaire(d) {
      if (!S.forme) return "";
      const U = d.utilisateurs || [], C = d.comptes || [];
      return '<section class="carte sec"><div class="sh"><h2>Créer une base</h2><span class="meta">elle est créée par le panneau : elle entre dans ses sauvegardes et ses quotas</span></div>' +
        '<div class="form"><input id="bd-nom" placeholder="nom de la base" autocomplete="off" aria-label="Nom de la base">' +
        '<select id="bd-user" aria-label="Utilisateur"><option value="">nouvel utilisateur…</option>' + U.map((u) => '<option value="' + esc(u) + '">' + esc(u) + "</option>").join("") + "</select>" +
        '<input id="bd-new" placeholder="identifiant du nouvel utilisateur (défaut : le nom de la base)" autocomplete="off" aria-label="Nouvel utilisateur" style="min-width:260px">' +
        (C.length > 1 ? '<select id="bd-owner" aria-label="Compte propriétaire">' + C.map((c) => '<option value="' + esc(c) + '">pour ' + esc(c) + "</option>").join("") + "</select>" : "") +
        '<button class="btn p" data-a="creer-go">Créer</button><button class="btn" data-a="creer-non">Annuler</button></div></section>';
    }
    function secret() {
      const r = S.resultat;
      if (!r) return "";
      return '<section class="carte sec"><div class="sh"><h2>' + esc(r.titre) + "</h2></div>" +
        (r.mot_de_passe ? '<p>Mot de passe de « ' + esc(r.utilisateur || "") + ' » : <span class="secret">' + esc(r.mot_de_passe) + '</span></p><p class="note">Montré une seule fois, ni journalisé ni renvoyé ailleurs : range-le dans le coffre avant de fermer.</p>' : "") +
        '<button class="btn" data-a="fermer">Fermer</button></section>';
    }
    function dessiner() {
      const d = S.d;
      const tete = '<p class="fil">Parc › Bases de données</p><div class="tete"><h1>Bases de données</h1><span class="meta">via le panneau détecté</span></div>';
      if (S.erreur) { racine.innerHTML = tete + '<section class="carte sec"><p class="err">' + esc(S.erreur) + "</p></section>"; return; }
      if (!d) { racine.innerHTML = tete + '<section class="carte sec"><p class="vide">Lecture…</p></section>'; return; }
      const n = (d.bases || []).length;
      const meta = d.etat === "ok" ? n + " base" + (n > 1 ? "s" : "") + " · " + taille(d.total_mo) + (d.sans_copie ? " · " + d.sans_copie + " jamais copiée" + (d.sans_copie > 1 ? "s" : "") : "") : "";
      const creer = d.etat === "ok" && d.gestes && d.gestes.creer ? '<button class="btn p" data-a="creer">Créer une base</button>' : "";
      racine.innerHTML = tete + secret() + formulaire(d) + retrait(d) + sec("Les bases", meta, liste(d), creer) +
        '<p class="note">Créer et supprimer passent par le panneau, au nom de ta personne et avec ta confirmation ; la liste, elle, vient de Panel Detect.</p>';
    }
    async function lire() {
      try { S.d = await agir("bases.lister", {}); S.erreur = ""; } catch (e) { S.erreur = msg(e); }
      dessiner();
    }
    async function creer() {
      const v = (id) => ((racine.querySelector("#" + id) || {}).value || "").trim();
      const nom = v("bd-nom"), user = v("bd-user");
      if (!nom) { K.dire("Indique un nom de base.", "err"); return; }
      const nouveau = user ? "" : v("bd-new");
      const oui = await K.confirmer("Créer la base « " + nom + " » ?", "<p>Elle est créée dans le serveur de bases du panneau avec " +
        (user ? "l’utilisateur « " + esc(user) + " »." : "un nouvel utilisateur" + (nouveau ? " « " + esc(nouveau) + " »" : " du même nom") + " (son mot de passe ne sera montré qu’une fois).") + "</p>", "Créer", false);
      if (!oui) return;
      S.occupe = true;
      try {
        const r = await viaRoute("base_creer", { nom: nom, serveur_id: "", utilisateur_id: user, nouvel_utilisateur: nouveau, proprietaire_id: v("bd-owner") });
        S.forme = false; S.resultat = { titre: "Base « " + ((r && r.nom) || nom) + " » créée", utilisateur: r && r.utilisateur, mot_de_passe: r && r.mot_de_passe };
        K.dire("Base créée.", "ok"); await lire();
      } catch (e) { K.dire("Échec : " + msg(e), "err"); }
      S.occupe = false;
    }
    async function supprimer(id) {
      S.occupe = true;
      try {
        const r = await viaRoute("base_supprimer", { id: Number(id) || 0 });
        S.retrait = null; K.dire("Base « " + ((r && r.nom) || id) + " » supprimée.", "ok"); await lire();
      } catch (e) { K.dire("Échec : " + msg(e), "err"); }
      S.occupe = false;
    }
    racine.addEventListener("input", (ev) => {
      if (ev.target.id === "bd-conf") {
        const b = (S.d.bases || []).find((x) => String(x.id) === String(S.retrait));
        const go = racine.querySelector("[data-a=suppr-go]"); if (go) go.disabled = !b || ev.target.value.trim() !== b.nom;
      }
      if (ev.target.id === "bd-user") { const n = racine.querySelector("#bd-new"); if (n) n.hidden = !!ev.target.value; }
    });
    racine.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-a]"); if (!b || S.occupe) return;
      const a = b.dataset.a;
      if (a === "creer") { S.forme = true; S.retrait = null; dessiner(); const i = racine.querySelector("#bd-nom"); if (i) i.focus(); }
      else if (a === "creer-non") { S.forme = false; dessiner(); }
      else if (a === "creer-go") creer();
      else if (a === "suppr") { S.retrait = b.dataset.i; S.forme = false; dessiner(); const i = racine.querySelector("#bd-conf"); if (i) i.focus(); }
      else if (a === "suppr-non") { S.retrait = null; dessiner(); }
      else if (a === "suppr-go") supprimer(b.dataset.i);
      else if (a === "fermer") { S.resultat = null; dessiner(); }
      else if (a === "pma") window.open(S.d.adresse.replace(/\/+$/, "") + "/phpmyadmin/index.php?db=" + encodeURIComponent(b.dataset.n), "_blank", "noopener");
    });
    dessiner(); await lire();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
